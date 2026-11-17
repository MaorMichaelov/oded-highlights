#!/usr/bin/env python3
"""Precise in/out points for a clip. Word timestamps from Whisper are only good to ~100-300 ms, so a cut placed on a word boundary can still clip a syllable or leave an awkward fraction of the next word.
We combine (a) the gaps between words and (b) the real audio energy (10 ms RMS in dB) and cut INSIDE a pause:
  START: the pause just before the first word -> start 180 ms before that word (never inside a word, never more than 600 ms of dead air).
  END:   the pause just after the last word  -> end 300 ms after that word (a laugh/breath tail is kept only if it is part of the word list), never inside a word.
Boundary check: energy at both cut points must be within 8 dB of the local noise floor, otherwise the point slides to the quietest frame within +-150 ms.
API: energy_db(path) -> (env, hop);  snap_start(t, words, env, hop, t0);  snap_end(t, words, env, hop, t0);  check_boundaries(...)"""
import re, subprocess
import numpy as np
def energy_db(path, sr=16000, hop=0.01):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"], capture_output=True).stdout
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0; n = int(sr * hop); m = len(x) // n
    if m == 0: return np.zeros(1), hop
    rms = np.sqrt((x[:m * n].reshape(m, n) ** 2).mean(1) + 1e-10); return 20 * np.log10(rms), hop
def _clamp(words, mx=1.4):
    """Whisper sometimes stretches a word across a pause or music (seen: last word 'ending' 11 s late): cap a word's length"""
    return [dict(w, end=min(w["end"], w["start"] + mx)) if w["end"] - w["start"] > mx else w for w in words]
def _gaps(words, lo, hi, min_gap=0.10):
    ws = sorted((w for w in words if w["end"] > lo - 2 and w["start"] < hi + 2), key=lambda w: w["start"]); out = []
    for a, b in zip(ws, ws[1:]):
        if b["start"] - a["end"] >= min_gap: out.append((a["end"], b["start"]))
    return out
def _inside_word(t, words): return any(w["start"] + 0.03 < t < w["end"] - 0.03 for w in words)
def _floor(env): return float(np.percentile(env, 10)) if len(env) else -60.0
def _at(env, hop, t0, t): i = int(round((t - t0) / hop)); return float(env[min(max(i, 0), len(env) - 1)])
def _quiet(env, hop, t0, t, floor, r=0.15):
    """slide a boundary to the quietest frame within +-r s if it sits on loud audio"""
    if _at(env, hop, t0, t) <= floor + 8: return t
    i0 = int(round((t - r - t0) / hop)); i1 = int(round((t + r - t0) / hop)); i0 = max(i0, 0); i1 = min(i1, len(env) - 1)
    if i1 <= i0: return t
    return t0 + (i0 + int(np.argmin(env[i0:i1 + 1]))) * hop
def _onset(env, hop, t0, lo, hi, floor, thr=10, sustain=0.06):
    """first time in [lo, hi] where the energy stays > floor+thr dB for `sustain` seconds (real speech onset), else None"""
    n = max(1, int(sustain / hop)); i0 = max(0, int(round((lo - t0) / hop))); i1 = min(len(env) - n, int(round((hi - t0) / hop)))
    for i in range(i0, i1 + 1):
        if (env[i:i + n] > floor + thr).all(): return t0 + i * hop
    return None
def _offset(env, hop, t0, lo, hi, floor, thr=10, sustain=0.06):
    """last time in [lo, hi] where the energy is > floor+thr dB (sustained), i.e. the real end of the last sound, else None"""
    n = max(1, int(sustain / hop)); i0 = max(0, int(round((lo - t0) / hop))); i1 = min(len(env) - n, int(round((hi - t0) / hop)))
    for i in range(i1, i0 - 1, -1):
        if (env[i:i + n] > floor + thr).all(): return t0 + (i + n) * hop
    return None
def snap_start(t, words, env, hop, t0, lead=0.18):
    """t = the first word start the LLM/sentence logic chose (absolute seconds)."""
    words = _clamp(words)
    first = min((w for w in words if abs(w["start"] - t) < 0.6), key=lambda w: abs(w["start"] - t), default=None)
    ft = first["start"] if first else t
    s = ft - lead
    for a, b in _gaps(words, ft - 1.5, ft + 0.1):   # the pause that ends at this first word
        if abs(b - ft) < 0.25 and b - a > lead + 0.02: s = max(ft - lead, a + 0.02) if b - a < 0.8 else ft - lead; break
    fl = _floor(env); on = _onset(env, hop, t0, ft - 0.5, ft + 0.3, fl)
    if on is not None and ft - 0.5 <= on <= ft + 0.3 and (on - 0.5 * lead) < s + 0.6: s = on - 0.15   # real onset found: start 150 ms before it (ASR starts are often early: never trust them alone)
    while _inside_word(s, words) and s > ft - 1.0: s -= 0.03
    return _quiet(env, hop, t0, s, fl)
def snap_end(t, words, env, hop, t0, tail=0.30):
    """t = the last word end (absolute seconds)."""
    words = _clamp(words)
    last = min((w for w in words if abs(w["end"] - t) < 1.6), key=lambda w: abs(w["end"] - t), default=None)
    lt = last["end"] if last else t
    e = lt + tail
    for a, b in _gaps(words, lt - 0.1, lt + 1.5):   # the pause that starts at this last word
        if abs(a - lt) < 0.25:
            e = min(lt + tail, b - 0.02) if b - a < 0.9 else lt + tail; break
    fl = _floor(env); off = _offset(env, hop, t0, lt - 1.0, lt + 0.9, fl)
    if off is not None and off >= lt - 1.0: e = (off + 0.25) if off < lt - 0.3 else (max(e, off + 0.25) if off <= lt + 0.5 else lt + tail)   # off well before the word end = the word was stretched over silence: trust the audio   # real end of the last sound + 250 ms (a laugh/breath tail up to 0.5 s is kept)
    nxt = min((w["start"] for w in words if w["start"] > lt + 0.05), default=None)
    if nxt is not None and e > nxt - 0.04: e = max(lt + 0.1, nxt - 0.04)
    while _inside_word(e, words) and e < lt + 1.2: e += 0.03
    return _quiet(env, hop, t0, e, fl)
def check_boundaries(s, e, env, hop, t0):
    fl = _floor(env); return {"start_db_over_floor": round(_at(env, hop, t0, s) - fl, 1), "end_db_over_floor": round(_at(env, hop, t0, e) - fl, 1), "ok": _at(env, hop, t0, s) <= fl + 10 and _at(env, hop, t0, e) <= fl + 10}
# ---------------------------------------------------------------- sentence-aware spans (added 17 Nov: the LLM's start/end seconds are only roughly right, they often fall in the middle of a sentence)
END_PUNCT = re.compile(r"[.!?…]['\"”’)]*$")
def _ws(words): return _clamp(sorted(words, key=lambda w: w["start"]))
def sentence_breaks(words, pause=0.45, last=True):
    """indices i such that a sentence ENDS after words[i]: the word ends with . ! ? (when the ASR gives punctuation) or the next word starts >= `pause` s later. The last word counts as an end unless last=False (the transcript stops there, the sentence may go on)."""
    ws = _ws(words); out = []
    for i, w in enumerate(ws):
        if i == len(ws) - 1: brk = last or bool(END_PUNCT.search(w["word"].strip()))
        else: brk = ws[i + 1]["start"] - w["end"] >= pause or bool(END_PUNCT.search(w["word"].strip()))
        if brk: out.append(i)
    return out
def sentence_start_near(t, words, back=5.0, fwd=2.5, pause=0.45):
    """start time of the sentence start nearest to t: a sentence that begins at or up to `back` s before t is preferred (the setup must stay in), else the first one up to `fwd` s after t. None when the words do not reach t."""
    ws = _ws(words)
    if not ws: return None
    br = set(sentence_breaks(ws, pause)); starts = [0] + [i + 1 for i in sorted(br) if i + 1 < len(ws)]
    before = [i for i in starts if t - back <= ws[i]["start"] <= t + 0.05]; after = [i for i in starts if t + 0.05 < ws[i]["start"] <= t + fwd]
    if before: return ws[before[-1]]["start"]   # the closest sentence start at or before t
    if after: return ws[after[0]]["start"]
    return None
def sentence_end_near(t, words, back=1.5, fwd=5.0, pause=0.45, last=True, before_win=4.0):
    """end time of the sentence end nearest to t: the first sentence end at or after t-back (finish the sentence the LLM ended inside), up to `fwd` s later; else the last one before. None when nothing is in reach."""
    ws = _ws(words)
    if not ws: return None
    ends = sentence_breaks(ws, pause, last); after = [i for i in ends if t - back <= ws[i]["end"] <= t + fwd]; before = [i for i in ends if t - back - before_win <= ws[i]["end"] < t - back]
    if after: return ws[after[0]]["end"]
    if before: return ws[before[-1]]["end"]
    return None
def align_span(s, e, words, min_len=20.0, max_len=58.0, pause=0.45):
    """Tries sentence boundaries at `pause` (0.45 s) first; fast talkers who never pause that long get phrase boundaries (0.30 s) when the result would not fit min_len..max_len. See _align_span."""
    r = _align_span(s, e, words, min_len, max_len, pause)
    if (r[2].get("aligned") and min_len <= r[1] - r[0] <= max_len) or pause <= 0.30: return r
    r2 = _align_span(s, e, words, min_len, max_len, 0.30); r2[2]["phrase_level"] = True
    return r2 if r2[2].get("aligned") and min_len <= r2[1] - r2[0] <= max_len else r
def _align_span(s, e, words, min_len, max_len, pause):
    """LLM start/end seconds -> (first word start, last word end, info) aligned to sentence boundaries: start on a sentence start (setup kept), end after the sentence that holds the punchline.
    Too long -> the end moves back to the previous sentence end that fits; too short -> the end extends over following sentences (<= max_len), then the start goes back by whole sentences."""
    ws = _ws(words)
    if not ws: return s, e, {"aligned": False}
    s2 = sentence_start_near(s, ws, 5.0, 2.5, pause); e2 = sentence_end_near(e, ws, 1.5, 5.0, pause); info = {"aligned": s2 is not None and e2 is not None}
    if s2 is None: s2 = min((w["start"] for w in ws if w["start"] >= s - 0.2), default=s)
    if e2 is None: e2 = max((w["end"] for w in ws if w["end"] <= e + 0.3), default=e)
    ends = [ws[i]["end"] for i in sentence_breaks(ws, pause)]
    if e2 - s2 > max_len:
        fit = [x for x in ends if s2 + min_len <= x <= s2 + max_len]
        if fit: e2 = fit[-1]; info["end_pulled_back"] = True
    if e2 - s2 < min_len:
        more = [x for x in ends if e2 < x <= s2 + max_len]
        for x in more:
            e2 = x
            if e2 - s2 >= min_len: break
        info["end_extended"] = True
    if e2 - s2 < min_len:
        st = [ws[0]["start"]] + [ws[i + 1]["start"] for i in sentence_breaks(ws, pause) if i + 1 < len(ws)]
        for x in sorted((x for x in st if x < s2), reverse=True):
            if e2 - x > max_len: break
            s2 = x; info["start_extended"] = True
            if e2 - s2 >= min_len: break
    return s2, e2, info
def pause_after(words, t, look=1.5):
    """length of the silence (no word) after time t, capped at `look`; used to prefer natural pauses when several sentence ends are possible"""
    nxt = min((w["start"] for w in words if w["start"] > t + 0.02), default=t + look); return min(look, max(0.0, nxt - t))
def trim_dead_air(a, b, words, env, hop, t0, max_lead=0.6, max_tail=0.6):
    """[a, b] = planned cut. If more than max_lead/max_tail seconds of near-silence (energy < floor+10 dB, no word) precede the first / follow the last sound, pull the cut in so that at most ~0.25 s of it remains. Never moves inside a word."""
    ws = _ws(words); fl = _floor(env)
    first = min((w for w in ws if w["end"] > a), key=lambda w: w["start"], default=None); last = max((w for w in ws if w["start"] < b), key=lambda w: w["end"], default=None)
    on = _onset(env, hop, t0, a, b, fl); off = _offset(env, hop, t0, a, b, fl)
    if on is not None and on - a > max_lead and (first is None or first["start"] - a > max_lead): a = on - 0.25
    if off is not None and b - off > max_tail and (last is None or b - last["end"] > max_tail): b = off + 0.25
    return a, b

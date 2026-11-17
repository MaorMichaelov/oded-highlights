#!/usr/bin/env python3
"""Precise in/out points for a clip. Word timestamps from Whisper are only good to ~100-300 ms, so a cut placed on a word boundary can still clip a syllable or leave an awkward fraction of the next word.
We combine (a) the gaps between words and (b) the real audio energy (10 ms RMS in dB) and cut INSIDE a pause:
  START: the pause just before the first word -> start 180 ms before that word (never inside a word, never more than 600 ms of dead air).
  END:   the pause just after the last word  -> end 300 ms after that word (a laugh/breath tail is kept only if it is part of the word list), never inside a word.
Boundary check: energy at both cut points must be within 8 dB of the local noise floor, otherwise the point slides to the quietest frame within +-150 ms.
API: energy_db(path) -> (env, hop);  snap_start(t, words, env, hop, t0);  snap_end(t, words, env, hop, t0);  check_boundaries(...)"""
import subprocess
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

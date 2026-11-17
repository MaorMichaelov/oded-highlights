#!/usr/bin/env python3
"""CUT PRECISION BENCHMARK on REAL speech (runs on a GitHub runner, needs the VOD): how often does a cut land on a clean word boundary?
For K random sentence ends / starts of a VOD window we compute the cut point with several strategies (current cutsnap defaults and variants), cut the audio there and TRANSCRIBE the cut piece again:
  END ok = the last word heard is the intended last word (complete); cut = the last word is truncated or lost; late = a fragment of the next word is heard.
  START ok = the first word heard is the intended first word; cut = it is truncated; early = a fragment of the previous word is heard.
usage: probe_cut.py --slug n3on --vod 137878318 --from-min 40 --to-min 45 [--k 24] [--platform kick|twitch] [--local]   (Groq whisper first, local faster-whisper fallback; --local = local only)
Writes state/probe/<slug>_<vod>_<from>.json and prints a table; the numbers are used to choose the defaults in cutsnap.py / vod_shorts.py."""
import argparse, difflib, json, os, random, re, sys, tempfile, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import vod_shorts as V, cutsnap as CS
def norm(w): return re.sub(r"[^a-z0-9']", "", w.lower())
def asr(path, local):
    for _ in range(2):
        try: return V.local_whisper(path, "en") if local else V.whisper(path, "en")
        except Exception as e: print("asr failed:", str(e)[:100]); time.sleep(3)
    return []
def classify_end(intended, prev, got):
    if not got: return "lost"
    last = norm(got[-1]["word"]); it = norm(intended)
    if last == it or difflib.SequenceMatcher(None, last, it).ratio() >= 0.9: return "ok"
    if it.startswith(last) and len(last) < len(it): return "cut"
    if last == norm(prev): return "lost"
    if it in [norm(x["word"]) for x in got[-3:]]: return "late"
    return "other"
def classify_start(intended, nxt, got):
    if not got: return "lost"
    first = norm(got[0]["word"]); it = norm(intended)
    if first == it or difflib.SequenceMatcher(None, first, it).ratio() >= 0.9: return "ok"
    if it.endswith(first) and len(first) < len(it): return "cut"
    if first == norm(nxt): return "lost"
    if it in [norm(x["word"]) for x in got[:3]]: return "early"
    return "other"
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--slug", required=True); ap.add_argument("--vod", default="auto"); ap.add_argument("--from-min", type=float, required=True); ap.add_argument("--to-min", type=float, required=True); ap.add_argument("--k", type=int, default=24); ap.add_argument("--platform", default="kick"); ap.add_argument("--local", action="store_true"); a = ap.parse_args()
    if a.platform == "twitch": tv = V.twitch_pick(a.slug, a.vod); vid = str(tv["id"]); AUDIO, VIDEO = V.twitch_urls(vid)
    else: v = V.pick_vod(a.slug, a.vod); base = v["source"].rsplit("/master.m3u8", 1)[0]; vid = str(v["id"]); AUDIO, VIDEO = f"{base}/480p30/playlist.m3u8", f"{base}/1080p60/playlist.m3u8"
    t0 = a.from_min * 60; dur = (a.to_min - a.from_min) * 60; tmp = tempfile.mkdtemp(); win = f"{tmp}/win.wav"
    r = V.sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{t0:.1f}", "-t", f"{dur:.1f}", "-i", AUDIO, "-vn", "-ac", "1", "-ar", "16000", win]); assert not r.returncode, r.stderr[-300:]
    words = []
    for c0 in np.arange(0, dur, 300):
        mp3 = f"{tmp}/c{int(c0)}.mp3"; V.sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{c0:.1f}", "-t", f"{min(300, dur - c0):.1f}", "-i", win, "-c:a", "libmp3lame", "-b:a", "48k", mp3])
        words += [{"word": w["word"], "start": c0 + w["start"], "end": c0 + w["end"]} for w in asr(mp3, a.local)]   # times relative to the window (t0 = 0)
    print(len(words), "words in", int(dur), "s", flush=True)
    env, hop = CS.energy_db(win); ws = CS._clamp(sorted(words, key=lambda w: w["start"])); br = CS.sentence_breaks(ws, 0.45)
    ends = [i for i in br if 3 <= i < len(ws) - 3 and i >= 3 and ws[i]["end"] > 8 and ws[i]["end"] < dur - 8 and ws[i + 1]["start"] - ws[i]["end"] >= 0.45 and i - (br[br.index(i) - 1] if br.index(i) else -1) >= 4]
    starts = [i + 1 for i in br if i + 4 < len(ws) and ws[i]["end"] > 8 and ws[i + 1]["start"] < dur - 12 and ws[i + 1]["start"] - ws[i]["end"] >= 0.45]
    rnd = random.Random(7); rnd.shuffle(ends); rnd.shuffle(starts); ends = ends[:a.k]; starts = starts[:a.k]
    # strategies: name -> function(i) -> cut time (window seconds)
    def end_cur(i, **kw): return CS.snap_end(ws[i]["end"], ws, env, hop, 0.0, **kw)
    def end_plain(i, pad): nx = ws[i + 1]["start"] if i + 1 < len(ws) else 1e9; return min(ws[i]["end"] + pad, nx - 0.04)
    ES = {"end_current": lambda i: end_cur(i), "end_tail45_after35": lambda i: end_cur(i, tail=0.45, after=0.35), "end_tail60_after45": lambda i: end_cur(i, tail=0.60, after=0.45), "end_plain_0.30": lambda i: end_plain(i, 0.30), "end_plain_0.45": lambda i: end_plain(i, 0.45), "end_plain_0.60": lambda i: end_plain(i, 0.60)}
    def st_cur(i, **kw): return CS.snap_start(ws[i]["start"], ws, env, hop, 0.0, **kw)
    SS = {"start_current": lambda i: st_cur(i), "start_lead30_pre25": lambda i: st_cur(i, lead=0.30, pre=0.25), "start_lead45_pre35": lambda i: st_cur(i, lead=0.45, pre=0.35), "start_plain_0.18": lambda i: max(ws[i]["start"] - 0.18, ws[i - 1]["end"] + 0.02), "start_plain_0.30": lambda i: max(ws[i]["start"] - 0.30, ws[i - 1]["end"] + 0.02)}
    res = {"vod": vid, "window": [t0, t0 + dur], "words": len(ws), "end": {}, "start": {}, "lag": None, "detail": []}
    try:
        ea, _ = CS.energy_db_seek(AUDIO, t0, 60); ev, _ = CS.energy_db_seek(VIDEO, t0, 60); lag, conf = CS.estimate_lag(ea, ev, hop); res["lag"] = {"ms": round(lag * 1000), "confidence": round(conf, 2)}; print("480p->1080p audio offset", res["lag"], flush=True)
    except Exception as e: print("lag estimate failed:", str(e)[:100])
    def cutpiece(a_, b_, name):
        f = f"{tmp}/{name}.wav"; V.sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0, a_):.3f}", "-t", f"{b_ - a_:.3f}", "-i", win, f]); return f
    for name, fn in ES.items():
        cnt = {}
        for n, i in enumerate(ends):
            e = fn(i); got = asr(cutpiece(e - 6.0, e, f"e{n}"), a.local); c = classify_end(ws[i]["word"], ws[i - 1]["word"], got); cnt[c] = cnt.get(c, 0) + 1
            res["detail"].append({"kind": name, "word": ws[i]["word"], "t": round(ws[i]["end"], 2), "cut": round(e, 2), "after_word_ms": round((e - ws[i]["end"]) * 1000), "res": c, "heard": " ".join(x["word"] for x in got[-3:])})
        res["end"][name] = cnt; print(name, cnt, flush=True)
    for name, fn in SS.items():
        cnt = {}
        for n, i in enumerate(starts):
            s = fn(i); got = asr(cutpiece(s, s + 6.0, f"s{n}"), a.local); c = classify_start(ws[i]["word"], ws[i + 1]["word"], got); cnt[c] = cnt.get(c, 0) + 1
            res["detail"].append({"kind": name, "word": ws[i]["word"], "t": round(ws[i]["start"], 2), "cut": round(s, 2), "before_word_ms": round((ws[i]["start"] - s) * 1000), "res": c, "heard": " ".join(x["word"] for x in got[:3])})
        res["start"][name] = cnt; print(name, cnt, flush=True)
    os.makedirs("state/probe", exist_ok=True); json.dump(res, open(f"state/probe/{a.slug}_{vid}_{int(a.from_min)}.json", "w"), indent=1, ensure_ascii=False)
if __name__ == "__main__": main()

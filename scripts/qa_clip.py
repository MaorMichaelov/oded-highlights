#!/usr/bin/env python3
"""QA of a finished draft. Two layers:
 1. OBJECTIVE GRADE (always, no network): scripts/cutqa.grade(): A/V sync and duration, dead air at both ends, audio chopped at the end / start inside a loud sound, loudness vs target, word cut (when word times exist), caption overflow (.ass), title truth (names / numbers / quotes of the title that never occur in the transcript).
    Result -> `qa` (score, fail, warn) + `qa_fail: true` in the draft's json when it FAILS, so upload_shorts.py skips it (QA_OVERRIDE=1 uploads anyway).
 2. GEMINI WATCH (only with GEMINI_API_KEY): Gemini WATCHES a short excerpt (first 75 s + 75 s from the middle, 480p) and reports defects (hook, captions, layout, sting, dead air, mid-sentence start, hard lines) -> <clip>/qa.txt (+ an event with the score). Never blocks the pipeline.
usage: qa_clip.py state/clips/<id>            Hebrew clip dir (final.mp4 + meta.json + cuts.json)   -> <clip>/qa.json, meta.json qa/qa_fail
       qa_clip.py state/<slug>/shorts/x.mp4   (or .../long/x.mp4) English draft with its x.json (+ x.words.json, x.ass)   -> x.json qa/qa_fail
       qa_clip.py --no-gemini ...              objective grade only          exit code 0 always (the caller decides), prints GRADE PASS/FAIL"""
import json, os, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "stations"))
import cutqa as CQ
args = [x for x in sys.argv[1:] if not x.startswith("--")]; NOGEM = "--no-gemini" in sys.argv
target = os.path.abspath(args[0]); DIRMODE = os.path.isdir(target)
fin = os.path.join(target, "final.mp4") if DIRMODE else target; clip = target if DIRMODE else os.path.dirname(target); cid = os.path.basename(target.rstrip("/")) if DIRMODE else os.path.basename(target)[:-4]
meta_f = os.path.join(target, "meta.json") if DIRMODE else target[:-4] + ".json"
def objective():
    """-> grade dict (also stored in the draft json)"""
    meta = json.load(open(meta_f, encoding="utf-8")) if os.path.exists(meta_f) else {}; kind = "short" if (not DIRMODE and "/long/" not in target.replace(os.sep, "/") and not os.path.basename(target).startswith("long_")) else "long"
    words = CQ.load_words(target[:-4] + ".words.json") if not DIRMODE else []; text = ""; skip = 0.0; ass = target[:-4] + ".ass" if not DIRMODE and os.path.exists(target[:-4] + ".ass") else None; extra = str((meta.get("source") or {}).get("vod_title") or ""); ign = [str((meta.get("source") or {}).get("slug") or "")]
    if DIRMODE:   # Hebrew clip: the transcript window comes from the cut ranges in the VOD transcript
        try:
            import eval_cuts as E
            c = json.load(open(os.path.join(clip, "cuts.json"))); segs = CQ.load_segments(E.tr_path("oded", c.get("vod"))); text = " ".join(CQ.window_text(segs, a - 3, b + 3) for p in c["pieces"] for a, b in p["keep"]); ign = E.IGN
        except Exception as e: print("no transcript context:", str(e)[:100])
    elif words:
        sk = float((meta.get("source") or {}).get("bumper_s") or 0.0) if kind == "long" else 0.0; skip = sk; text = CQ.words_text(words); words = [{"word": w["word"], "start": w["start"] + sk, "end": w["end"] + sk} for w in words]
    g = CQ.grade(fin, kind, title=meta.get("title"), words=words or None, window_text_=text, ass=ass, skip_head=skip, ignore_names=ign + ["N3on", "Kai", "Cenat", "ClipGlobe", "Kick", "Twitch"], extra_text=extra)
    q = {"score": g["score"], "fail": g["fail"], "warn": g["warn"]}
    if DIRMODE: json.dump(dict(q, metrics=g["metrics"]), open(os.path.join(clip, "qa.json"), "w"), indent=1, ensure_ascii=False, default=str)
    if os.path.exists(meta_f):
        meta["qa"] = q
        if q["fail"]: meta["qa_fail"] = True
        elif meta.get("qa_fail") and not meta.get("qa_fail_manual"): meta.pop("qa_fail", None)   # a re-grade that passes clears an earlier automatic flag
        json.dump(meta, open(meta_f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("GRADE", "FAIL" if q["fail"] else "PASS", json.dumps(q, ensure_ascii=False)); return q
if not os.path.exists(fin): sys.exit("qa: no video at " + fin)
q = objective()
if NOGEM or not os.environ.get("GEMINI_API_KEY") or not DIRMODE: sys.exit(0)   # the Gemini watcher is tuned for the Hebrew long clips (opening / sting / popup)
def sh(c): return subprocess.run(c, capture_output=True, text=True)
dur = float(sh(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", fin]).stdout.strip() or 0)
ex = f"/tmp/qa_{cid}.mp4"; segs = [(0, min(75, dur))] + ([(dur / 2, min(75, dur / 2))] if dur > 240 else [])
fl = "".join(f"[0:v]trim=start={a:.1f}:duration={d:.1f},setpts=PTS-STARTPTS,scale=-2:480[v{i}];[0:a]atrim=start={a:.1f}:duration={d:.1f},asetpts=PTS-STARTPTS[a{i}];" for i, (a, d) in enumerate(segs)) + "".join(f"[v{i}][a{i}]" for i in range(len(segs))) + f"concat=n={len(segs)}:v=1:a=1[v][a]"
r = sh(["ffmpeg", "-v", "error", "-y", "-i", fin, "-filter_complex", fl, "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "28", "-preset", "veryfast", "-c:a", "aac", "-b:a", "96k", ex])
if r.returncode: sys.exit("qa: excerpt failed " + r.stderr[-200:])
Q = ("QUALITY CHECK of OUR OWN automatically edited YouTube highlight clip (Hebrew streamer; the file is an excerpt: the first 75 s and 75 s from the middle). Report in Hebrew, concise: "
     "(a) the opening: is there a hook of the 3 strongest moments, a green-captioned intro, a sting, a subscribe pop-up, are they readable and not cut off; (b) captions/layout: readable, synced, nothing cut; (c) does the content start at the beginning of a sentence; "
     "(d) dead air or silence stretches; (e) any hard/offensive line (slurs, racism, self-harm) heard or shown; (f) audio level and clipping; (g) interest score 1-10 with a reason; (h) a numbered list of concrete defects. Start the answer with 'SCORE: n/10'.")
r = sh([sys.executable, os.path.join(HERE, "watch_video.py"), ex, Q]); out = "\n".join(l[6:] for l in r.stdout.splitlines() if l.startswith("WATCH|") and not l.startswith("WATCH|available"))
open(os.path.join(clip, "qa.txt"), "w", encoding="utf-8").write(out)
m = re.search(r"SCORE:\s*(\d+)", out)
sys.path.insert(0, os.path.join(HERE, "stations"))
from events import event
event("qa", f"בדיקת איכות אוטומטית (Gemini צפה בקטע מהקליפ): ציון {m.group(1) if m else '?'}/10" + (" – יש ליקויים, ראה qa.txt" if re.search(r"ליקוי|defect", out, re.I) else ""), clip=cid)
print(out[:1500])

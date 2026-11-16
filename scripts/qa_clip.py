#!/usr/bin/env python3
"""QA of a rendered clip: Gemini WATCHES a short excerpt (first 75 s + 75 s from the middle, 480p) and reports defects (hook, captions, layout, sting, dead air, mid-sentence start, hard lines).
usage: qa_clip.py state/clips/<id>      env: GEMINI_API_KEY      output: <clip>/qa.txt (+ an event with the score)       Never blocks the pipeline."""
import os, re, subprocess, sys
clip = os.path.abspath(sys.argv[1]); fin = os.path.join(clip, "final.mp4"); cid = os.path.basename(clip.rstrip("/"))
HERE = os.path.dirname(os.path.abspath(__file__))
if not os.path.exists(fin) or not os.environ.get("GEMINI_API_KEY"): sys.exit("qa: no final.mp4 or no GEMINI_API_KEY")
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

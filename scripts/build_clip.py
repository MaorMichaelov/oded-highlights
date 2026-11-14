#!/usr/bin/env python3
"""Build the BODY of a clip from a Kick VOD: download only the needed 1080p60 segments, then render
each `keep` range with trim/atrim (never -ss on a concat of .ts) and join them.
usage: build_clip.py BASE_URL CUTS.json WORKDIR [quality=1080p60] [preset=veryfast]
BASE_URL is the VOD hls base (…/media/hls). CUTS.json = {"pieces":[{"keep":[[a,b],...],"ch":"chapter"}]} in VOD seconds.
Writes WORKDIR/body.mp4 and WORKDIR/chapters.json (chapter start times inside body)."""
import json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
base, cuts_f, work = sys.argv[1], sys.argv[2], Path(sys.argv[3])
Q = sys.argv[4] if len(sys.argv) > 4 else "1080p60"
PRESET = sys.argv[5] if len(sys.argv) > 5 else "veryfast"
work.mkdir(parents=True, exist_ok=True); (work / "seg").mkdir(exist_ok=True); (work / "parts").mkdir(exist_ok=True)
pl = subprocess.run(["curl", "-sS", "-A", UA, "-m", "60", f"{base}/{Q}/playlist.m3u8"], capture_output=True, text=True).stdout.splitlines()
segs = []; cum = 0.0; d = None
for l in pl:
    if l.startswith("#EXTINF:"): d = float(l[8:].split(",")[0])
    elif l and not l.startswith("#") and d is not None: segs.append((l, cum, d)); cum += d; d = None
C = json.load(open(cuts_f))
def files(a, b): return [s for s in segs if s[1] + s[2] > a and s[1] < b]
need = {}
for p in C["pieces"]:
    for a, b in p["keep"]:
        for s in files(a, b): need[s[0]] = s
def dl(s):
    f = work / "seg" / s[0]
    if f.exists() and f.stat().st_size > 1000: return
    subprocess.run(["curl", "-sS", "-A", UA, "-m", "120", "--retry", "3", "-o", str(f), f"{base}/{Q}/{s[0]}"])
print(f"downloading {len(need)} segments ({Q})", flush=True)
with ThreadPoolExecutor(8) as ex: list(ex.map(dl, need.values()))
lst = []; i = 0; t = 0.0; chapters = []
for p in C["pieces"]:
    if p.get("ch"): chapters.append({"t": round(t, 2), "ch": p["ch"]})
    for a, b in p["keep"]:
        fs = files(a, b); s0 = fs[0][1]; x = a - s0; dur = b - a
        out = work / "parts" / f"p{i:03d}.mp4"; i += 1
        if not out.exists():
            inp = "concat:" + "|".join(str(work / "seg" / n) for n, _, _ in fs)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", inp, "-map", "0:v:0", "-map", "0:a:0",
              "-vf", f"trim=start={x:.3f}:duration={dur:.3f},setpts=PTS-STARTPTS,fps=60,format=yuv420p,setsar=1",
              "-af", f"atrim=start={x:.3f}:duration={dur:.3f},asetpts=PTS-STARTPTS,aresample=48000,afade=t=in:d=0.02,afade=t=out:st={max(0, dur-0.04):.3f}:d=0.04",
              "-c:v", "libx264", "-preset", PRESET, "-b:v", "12M", "-maxrate", "16M", "-bufsize", "24M", "-g", "120", "-keyint_min", "120", "-sc_threshold", "0", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", str(out)], check=True)
        lst.append(out); t += dur
        print(f"part {i} done ({t:.0f}s so far)", flush=True)
(work / "list.txt").write_text("".join(f"file '{x}'\n" for x in lst))
subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(work / "list.txt"), "-c", "copy", "-movflags", "+faststart", str(work / "body.mp4")], check=True)
json.dump(chapters, open(work / "chapters.json", "w"), ensure_ascii=False, indent=1)
print("BODY READY", round(t, 1), "s")

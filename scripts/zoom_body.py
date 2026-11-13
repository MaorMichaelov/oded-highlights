#!/usr/bin/env python3
"""Low-memory punch-in zooms. Renders each piece separately (trim on a single input), then joins with stream copy.
usage: zoom_body.py IN.mp4 OUT.mp4 START:END [START:END ...]   (zoom ranges in seconds, scale 1.18)"""
import subprocess, sys, json, os, tempfile
from pathlib import Path
src, out = sys.argv[1], sys.argv[2]
Z = sorted(tuple(map(float, a.split(":"))) for a in sys.argv[3:])
dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", src], capture_output=True, text=True).stdout)
pieces = []; t = 0.0
for a, b in Z:
    if a > t: pieces.append((t, a, False))
    pieces.append((a, b, True)); t = b
if t < dur: pieces.append((t, dur, False))
tmp = Path(tempfile.mkdtemp()); lst = []
for i, (a, b, zoom) in enumerate(pieces):
    f = tmp / f"p{i}.mp4"; d = b - a
    vf = f"trim=start={a:.3f}:duration={d:.3f},setpts=PTS-STARTPTS"
    if zoom: vf += ",scale=iw*1.18:ih*1.18,crop=1920:1080:(iw-1920)/2:(ih-1080)/2"
    vf += ",setsar=1,fps=60,format=yuv420p"
    af = f"atrim=start={a:.3f}:duration={d:.3f},asetpts=PTS-STARTPTS,aresample=48000"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vf", vf, "-af", af, "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-g", "120", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", str(f)], check=True)
    lst.append(f); print("piece", i, "zoom" if zoom else "", round(d, 1), flush=True)
(tmp / "l.txt").write_text("".join(f"file '{f}'\n" for f in lst))
subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(tmp / "l.txt"), "-c", "copy", "-movflags", "+faststart", out], check=True)
print("ZOOM DONE", out)

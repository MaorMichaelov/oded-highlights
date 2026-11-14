#!/usr/bin/env python3
"""STATION 4 - EDIT: word timings (Groq whisper) -> 3-shot cold open with green captions at 80 percent height -> green logo sting -> subscribe popup (4 s into the body), only the first ~30 s are composited,
the rest is joined by stream copy (no second encode), then quality gate (1920x1080 60 fps, > 8 Mbps) and A/V sync check.
In : work/body.mp4 (from cut) + spec.json   Out: final.mp4 + meta.json (chapters, draft brief)     usage: edit.py state/clips/<id>"""
import os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); from common import Timer
clip = os.path.abspath(sys.argv[1])
if not os.path.exists(os.path.join(clip, "work", "body.mp4")): sys.exit("cut station has not produced work/body.mp4")
with Timer(clip, "edit"):
    subprocess.run([sys.executable, os.path.join(os.path.dirname(HERE), "render_clip.py"), clip]).check_returncode()

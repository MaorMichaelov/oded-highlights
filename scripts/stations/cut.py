#!/usr/bin/env python3
"""STATION 3 - CUT: downloads only the needed 1080p60 segments of the VOD (8 parallel curl), trims every keep-range exactly (trim/atrim, never -ss on concat), one 12 Mbps encode.
In : state/clips/<id>/cuts.json    Out: state/clips/<id>/work/body.mp4 + chapters.json     usage: cut.py state/clips/<id>"""
import json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); from common import Timer
clip = os.path.abspath(sys.argv[1]); work = os.path.join(clip, "work"); os.makedirs(work, exist_ok=True)
cuts = json.load(open(os.path.join(clip, "cuts.json"))); base = cuts.get("base") or json.load(open(os.path.join(os.path.dirname(os.path.dirname(HERE)), "state", "ingest_state.json")))["_vod_base"]
with Timer(clip, "cut"):
    if not os.path.exists(os.path.join(work, "body.mp4")):
        r = subprocess.run([sys.executable, os.path.join(os.path.dirname(HERE), "build_clip.py"), base, os.path.join(clip, "cuts.json"), work, "1080p60", "superfast"]); r.check_returncode()
    print("CUT OK", os.path.getsize(os.path.join(work, "body.mp4")) // 1_000_000, "MB")

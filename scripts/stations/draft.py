#!/usr/bin/env python3
"""STATION 5 - DRAFT: uploads final.mp4 to ODED HIGHLIGHTS as a PRIVATE draft (full Hebrew title/description/chapters/brief, no thumbnail unless assets/thumbs_override/<id>_c.jpg exists).
Never publishes. In: final.mp4 + meta.json   Out: upload.log, status.json {draft: url}     usage: draft.py state/clips/<id>"""
import os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); from common import Timer, mark
ROOT = os.path.dirname(os.path.dirname(HERE)); clip = os.path.abspath(sys.argv[1]); cid = os.path.basename(clip.rstrip("/"))
thumb = os.path.join(ROOT, "assets", "thumbs_override", f"{cid}_c.jpg")
with Timer(clip, "draft"):
    cmd = [sys.executable, os.path.join(os.path.dirname(HERE), "yt_upload.py"), os.path.join(clip, "final.mp4"), os.path.join(clip, "meta.json")] + ([thumb] if os.path.exists(thumb) else [])
    r = subprocess.run(cmd, capture_output=True, text=True); open(os.path.join(clip, "upload.log"), "w").write(r.stdout + r.stderr); print(r.stdout[-300:])
    url = [l for l in r.stdout.splitlines() if l.startswith("https://youtu.be/")]
    if r.returncode or not url: sys.exit("upload failed: " + (r.stdout + r.stderr)[-400:])
    mark(clip, "draft", "done", url=url[-1])

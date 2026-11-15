#!/usr/bin/env python3
"""STATION 5 - DRAFT: uploads final.mp4 to ODED HIGHLIGHTS as a PRIVATE draft (full Hebrew title/description/chapters/brief, no thumbnail unless assets/thumbs_override/<id>_c.jpg exists).
Never publishes. In: final.mp4 + meta.json   Out: upload.log, status.json {draft: url}     usage: draft.py state/clips/<id>"""
import os, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); from common import Timer, mark
from events import event
ROOT = os.path.dirname(os.path.dirname(HERE)); clip = os.path.abspath(sys.argv[1]); cid = os.path.basename(clip.rstrip("/"))
thumb = os.path.join(ROOT, "assets", "thumbs_override", f"{cid}_c.jpg")
QW = None
with Timer(clip, "draft"):
    cmd = [sys.executable, os.path.join(os.path.dirname(HERE), "yt_upload.py"), os.path.join(clip, "final.mp4"), os.path.join(clip, "meta.json")] + ([thumb] if os.path.exists(thumb) else [])
    r = subprocess.run(cmd, capture_output=True, text=True); open(os.path.join(clip, "upload.log"), "w").write(r.stdout + r.stderr); print(r.stdout[-300:])
    url = [l for l in r.stdout.splitlines() if l.startswith("https://youtu.be/")]
    if r.returncode or not url:
        err = r.stdout + r.stderr
        if re.search(r"quota|uploadLimitExceeded|rateLimitExceeded", err, re.I): QW = err[-200:]   # YouTube daily upload quota used up: the monitor re-renders + uploads after the reset (08:00 UTC)
        else: sys.exit("upload failed: " + err[-400:])
    else:
        mark(clip, "draft", "done", url=url[-1])
        import json as _j; _t = _j.load(open(os.path.join(clip, "meta.json")))["title"]; event("draft", f"עלתה טיוטה: {_t}", url=url[-1], clip=cid)
if QW:
    mark(clip, "draft", "quota_wait"); event("problem", f"מכסת ההעלאות היומית של YouTube נגמרה. הקליפ {cid} ייעלה אוטומטית אחרי איפוס המכסה (בערך 10:00 בבוקר שעון ישראל).")
    sys.exit("quota_wait: " + QW)

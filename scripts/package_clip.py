#!/usr/bin/env python3
"""Package a finished clip: thumbnails (2 versions A/B for YouTube Test & compare, QA-checked) + metadata -> optional private upload.
Clip folder (state/clips/<id>/) needs: spec.json  and (for upload) final.mp4
spec.json = {"title": "...", "description": "...", "tags": [...], "preset": "phone_call", "head": "מתקשר", "accent": "לעמית שיבר!", "refs": "shock,smirk,excited"}
usage: package_clip.py state/clips/<id> [--upload] [--seeds 2]      (upload needs the YouTube refresh token, see yt_upload.py)"""
import argparse, json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
ap = argparse.ArgumentParser(); ap.add_argument("clip"); ap.add_argument("--upload", action="store_true"); ap.add_argument("--seeds", type=int, default=2); a = ap.parse_args()
spec = json.load(open(os.path.join(a.clip, "spec.json"))); cid = os.path.basename(os.path.normpath(a.clip))
cmd = [sys.executable, os.path.join(HERE, "make_scene_thumb.py"), "--slug", cid, "--preset", spec["preset"], "--head", spec["head"], "--accent", spec.get("accent", ""), "--refs", spec.get("refs", "shock,excited,smirk"), "--seeds", str(a.seeds)]
r = subprocess.run(cmd, capture_output=True, text=True); print(r.stdout.strip()); 
cands = []
for s in range(1, a.seeds + 1):
    f = os.path.join(ROOT, "assets", "final_thumbs", f"{cid}_s{s}.jpg")
    if os.path.exists(f): cands.append(f)
ok = [l for l in r.stdout.splitlines() if "overlap_ok=True" in l]
print(f"{len(cands)} thumbnails, {len(ok)} passed QA")
req = f"""בקשה לתמנל ל-ODED HIGHLIGHTS (שני תמנלים שונים: C ו-D)
כותרת הסרטון: {spec['title']}
כותרת על התמנל: שורה 1 "{spec['head']}" + שורה 2 "{spec.get('accent', '')}"
סצנה לפי הנושא: סגנון {spec['preset']} (רקע חי, אובייקט גיבור אחד גדול ומפורט, עודד קרוב עם הבעה חזקה ותאורה בהירה על הפנים, בלי טקסט עברי בתמונה, מקום פנוי לכותרת).
ייחוס: 3-5 פריימים אמיתיים של עודד מ-1080p, פנים נקיות.
שמות קבצים: assets/thumbs_override/{cid}_c.jpg ו-{cid}_d.jpg (1280x720)
"""
open(os.path.join(a.clip, "grok_request.md"), "w").write(req)
meta = {"title": spec["title"], "description": spec["description"], "tags": spec.get("tags", []), "privacy": "private"}
json.dump(meta, open(os.path.join(a.clip, "meta.json"), "w"), ensure_ascii=False, indent=1)
json.dump({"candidates": [os.path.relpath(c, ROOT) for c in cands], "status": "thumbnails_ready_pick_one"}, open(os.path.join(a.clip, "package.json"), "w"), indent=1)
if a.upload:
    video = os.path.join(a.clip, "final.mp4"); thumb = cands[0] if cands else None
    if not os.path.exists(video): sys.exit("final.mp4 missing")
    cmd = [sys.executable, os.path.join(HERE, "yt_upload.py"), video, os.path.join(a.clip, "meta.json")] + ([thumb] if thumb else [])
    print(subprocess.run(cmd, capture_output=True, text=True).stdout.strip())

#!/usr/bin/env python3
"""Edit title/description of one of OUR PRIVATE drafts (never public videos, never privacy/deletion). usage: yt_edit.py VIDEO_ID "title" "description"   (env YT_REFRESH_TOKEN/YT_CLIENT_ID/YT_CLIENT_SECRET)"""
import json, os, subprocess, sys, urllib.parse
vid, title, desc = sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else ""
def sh(c, **k): return subprocess.run(c, capture_output=True, text=True, **k).stdout
data = ["-d", "grant_type=refresh_token", "--data-urlencode", "refresh_token=" + os.environ["YT_REFRESH_TOKEN"], "-d", "client_id=" + os.environ["YT_CLIENT_ID"], "-d", "client_secret=" + os.environ["YT_CLIENT_SECRET"]]
at = json.loads(sh(["curl", "-sS", "-X", "POST", "https://oauth2.googleapis.com/token"] + data))["access_token"]; H = ["-H", "Authorization: Bearer " + at]
v = json.loads(sh(["curl", "-sS", f"https://www.googleapis.com/youtube/v3/videos?part=snippet,status&id={urllib.parse.quote(vid)}"] + H))["items"]
if not v: sys.exit("video not found")
v = v[0]
if v["status"]["privacyStatus"] != "private": sys.exit("refused: only private drafts can be edited from the app")
sn = v["snippet"]; sn["title"] = title or sn["title"]; sn["description"] = desc or sn["description"]
r = sh(["curl", "-sS", "-X", "PUT", "https://www.googleapis.com/youtube/v3/videos?part=snippet", "-H", "Content-Type: application/json"] + H + ["-d", json.dumps({"id": vid, "snippet": {"title": sn["title"], "description": sn["description"], "categoryId": sn.get("categoryId", "24"), "tags": sn.get("tags", []), "defaultLanguage": sn.get("defaultLanguage", "he")}}, ensure_ascii=False)])
print("edited" if '"id"' in r else "FAILED " + r[:300])
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "stations")); from events import event
if '"id"' in r: event("edit", f"עודכנה טיוטה: {sn['title']}", url=f"https://youtu.be/{vid}")

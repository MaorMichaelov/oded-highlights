#!/usr/bin/env python3
"""Resumable YouTube upload. usage: yt_upload.py VIDEO.mp4 META.json [THUMB.jpg]
META.json: {"title","description","tags":[],"privacy":"private|unlisted|public","publishAt":optional}
Auth: env YT_REFRESH_FILE (json with refresh_token) -> access token via oauth2 token endpoint.
Client credentials (client_id/secret) are injected by the environment proxy locally, or passed as
YT_CLIENT_ID / YT_CLIENT_SECRET in CI."""
import json, os, subprocess, sys, urllib.parse
video, meta_f = sys.argv[1], sys.argv[2]; thumb = sys.argv[3] if len(sys.argv) > 3 else None
meta = json.load(open(meta_f))
rt = json.load(open(os.environ["YT_REFRESH_FILE"]))["refresh_token"] if os.environ.get("YT_REFRESH_FILE") else os.environ["YT_REFRESH_TOKEN"]
def run(cmd, **kw): return subprocess.run(cmd, capture_output=True, text=True, **kw)
data = ["-d", "grant_type=refresh_token", "--data-urlencode", f"refresh_token={rt}"]
if os.environ.get("YT_CLIENT_ID"): data += ["-d", f"client_id={os.environ['YT_CLIENT_ID']}", "-d", f"client_secret={os.environ['YT_CLIENT_SECRET']}"]
tok = json.loads(run(["curl", "-sS", "-m", "30", "-X", "POST", "https://oauth2.googleapis.com/token"] + data).stdout)
at = tok.get("access_token")
if not at: print("token error:", {k: v for k, v in tok.items() if k != "access_token"}); sys.exit(1)
body = {"snippet": {"title": meta["title"], "description": meta["description"], "tags": meta.get("tags", []), "categoryId": "24", "defaultLanguage": "he", "defaultAudioLanguage": "he"},
        "status": {"privacyStatus": meta.get("privacy", "private"), "selfDeclaredMadeForKids": False}}
if meta.get("publishAt"): body["status"]["publishAt"] = meta["publishAt"]
size = os.path.getsize(video)
hdr = run(["curl", "-sS", "-i", "-m", "60", "-X", "POST", "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
           "-H", f"Authorization: Bearer {at}", "-H", "Content-Type: application/json; charset=UTF-8", "-H", "X-Upload-Content-Type: video/mp4",
           "-H", f"X-Upload-Content-Length: {size}", "-d", json.dumps(body, ensure_ascii=False)]).stdout
loc = [l.split(":", 1)[1].strip() for l in hdr.splitlines() if l.lower().startswith("location:")]
if not loc: print("init failed:", hdr[:600]); sys.exit(1)
print("uploading", round(size / 1e6), "MB ...", flush=True)
r = run(["curl", "-sS", "-m", "1800", "-X", "PUT", loc[0], "-H", "Content-Type: video/mp4", "--data-binary", f"@{video}"])
try: res = json.loads(r.stdout)
except Exception: print("upload response:", r.stdout[:500], r.stderr[:300]); sys.exit(1)
if "id" not in res: print("upload error:", json.dumps(res)[:600]); sys.exit(1)
print("VIDEO_ID", res["id"], "| status:", res.get("status", {}).get("uploadStatus"), res.get("status", {}).get("privacyStatus"))
if thumb:
    t = run(["curl", "-sS", "-m", "120", "-X", "POST", f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={res['id']}", "-H", f"Authorization: Bearer {at}", "-H", "Content-Type: image/jpeg", "--data-binary", f"@{thumb}"])
    print("thumbnail:", t.stdout[:200])
print("https://youtu.be/" + res["id"])

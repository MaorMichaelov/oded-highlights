#!/usr/bin/env python3
"""Read-only: full metadata (title, description, tags, duration, stats, thumbnail) of the latest uploads of OUR channel, so the pick/meta stations can learn from what the other bot (Grok) publishes. Writes state/yt_research/own_full.json."""
import json, os, subprocess, urllib.parse
def sh(c): return subprocess.run(c, capture_output=True, text=True).stdout
data = ["-d", "grant_type=refresh_token", "--data-urlencode", "refresh_token=" + os.environ["YT_REFRESH_TOKEN"], "-d", "client_id=" + os.environ["YT_CLIENT_ID"], "-d", "client_secret=" + os.environ["YT_CLIENT_SECRET"]]
at = json.loads(sh(["curl", "-sS", "-X", "POST", "https://oauth2.googleapis.com/token"] + data))["access_token"]; H = ["-H", "Authorization: Bearer " + at]
def api(path, **q): return json.loads(sh(["curl", "-sS", "-m", "40", f"https://www.googleapis.com/youtube/v3/{path}?" + urllib.parse.urlencode(q)] + H))
ch = api("channels", part="contentDetails", mine="true")["items"][0]; up = ch["contentDetails"]["relatedPlaylists"]["uploads"]
ids = [x["snippet"]["resourceId"]["videoId"] for x in api("playlistItems", part="snippet", playlistId=up, maxResults=50).get("items", [])]
out = []
for i in range(0, len(ids), 50):
    for v in api("videos", part="snippet,contentDetails,statistics,status", id=",".join(ids[i:i + 50])).get("items", []):
        sn = v["snippet"]; out.append({"id": v["id"], "title": sn["title"], "description": sn.get("description", ""), "tags": sn.get("tags", []), "published": sn["publishedAt"], "privacy": v["status"]["privacyStatus"], "duration": v["contentDetails"]["duration"], "views": int(v["statistics"].get("viewCount", 0)), "likes": int(v["statistics"].get("likeCount", 0)), "thumb": (sn.get("thumbnails", {}).get("maxres") or sn.get("thumbnails", {}).get("high") or {}).get("url")})
os.makedirs("state/yt_research", exist_ok=True); json.dump(out, open("state/yt_research/own_full.json", "w"), ensure_ascii=False, indent=1); print(len(out), "videos")

for v in out: print("YTV|" + json.dumps(v, ensure_ascii=False))

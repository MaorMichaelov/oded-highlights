#!/usr/bin/env python3
"""YouTube research for the topic judge. usage:
  yt_research.py own                  -> titles of ODED HIGHLIGHTS uploads (dedupe)
  yt_research.py search "query" [n]   -> existing videos on the topic (other Oded clip channels): title, channel, views
Writes state/yt_research/<kind>.json. Quota: own ~3 units, search 100 units (daily cap 10000; use sparingly)."""
import json, os, subprocess, sys, time, urllib.parse
rt = json.load(open(os.environ["YT_REFRESH_FILE"]))["refresh_token"] if os.environ.get("YT_REFRESH_FILE") else os.environ["YT_REFRESH_TOKEN"]
def sh(c): return subprocess.run(c, capture_output=True, text=True).stdout
data = ["-d", "grant_type=refresh_token", "--data-urlencode", f"refresh_token={rt}"]
if os.environ.get("YT_CLIENT_ID"): data += ["-d", f"client_id={os.environ['YT_CLIENT_ID']}", "-d", f"client_secret={os.environ['YT_CLIENT_SECRET']}"]
at = json.loads(sh(["curl", "-sS", "-m", "30", "-X", "POST", "https://oauth2.googleapis.com/token"] + data)).get("access_token")
if not at: sys.exit("token error")
def api(path, **q):
    return json.loads(sh(["curl", "-sS", "-m", "40", f"https://www.googleapis.com/youtube/v3/{path}?" + urllib.parse.urlencode(q), "-H", f"Authorization: Bearer {at}"]))
os.makedirs("state/yt_research", exist_ok=True)
kind = sys.argv[1]
if kind == "own":
    ch = api("channels", part="contentDetails,snippet", mine="true")
    it = ch["items"][0]; up = it["contentDetails"]["relatedPlaylists"]["uploads"]
    r = api("playlistItems", part="snippet", playlistId=up, maxResults=50)
    out = {"channel": it["snippet"]["title"], "videos": [{"id": x["snippet"]["resourceId"]["videoId"], "title": x["snippet"]["title"], "at": x["snippet"]["publishedAt"]} for x in r.get("items", [])]}
else:
    q = sys.argv[2]; n = sys.argv[3] if len(sys.argv) > 3 else "15"
    r = api("search", part="snippet", q=q, type="video", maxResults=n, order="relevance", relevanceLanguage="he")
    ids = ",".join(x["id"]["videoId"] for x in r.get("items", []))
    st = api("videos", part="statistics", id=ids) if ids else {"items": []}
    views = {x["id"]: int(x["statistics"].get("viewCount", 0)) for x in st.get("items", [])}
    out = {"query": q, "videos": [{"id": x["id"]["videoId"], "title": x["snippet"]["title"], "channel": x["snippet"]["channelTitle"], "at": x["snippet"]["publishedAt"], "views": views.get(x["id"]["videoId"], 0)} for x in r.get("items", [])]}
    if "error" in r: out["error"] = r["error"]
json.dump(out, open(f"state/yt_research/{kind}.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1)[:3000])

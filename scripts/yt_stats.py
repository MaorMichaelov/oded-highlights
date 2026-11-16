#!/usr/bin/env python3
"""Reads the channel's videos + statistics (views/likes/comments) into state/yt_stats.json and learns: a video that disappeared (owner deleted a draft) or a weak performer becomes a LESSON for the pick station.
Runs at most every 30 min (age check). Needs YT_REFRESH_TOKEN/YT_CLIENT_ID/YT_CLIENT_SECRET (Actions) or YT_REFRESH_FILE + proxy credentials (local)."""
import json, os, subprocess, sys, time, urllib.parse
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "stations")); from events import ST, lesson
f = os.path.join(ST, "yt_stats.json"); old = json.load(open(f)) if os.path.exists(f) else {}
if old and time.time() - old.get("fetched_epoch", 0) < 1800 and "--force" not in sys.argv: sys.exit(0)
rt = json.load(open(os.environ["YT_REFRESH_FILE"]))["refresh_token"] if os.environ.get("YT_REFRESH_FILE") else os.environ.get("YT_REFRESH_TOKEN")
if not rt: sys.exit("no YouTube credentials")
def sh(c): return subprocess.run(c, capture_output=True, text=True).stdout
data = ["-d", "grant_type=refresh_token", "--data-urlencode", f"refresh_token={rt}"]
if os.environ.get("YT_CLIENT_ID"): data += ["-d", f"client_id={os.environ['YT_CLIENT_ID']}", "-d", f"client_secret={os.environ['YT_CLIENT_SECRET']}"]
at = json.loads(sh(["curl", "-sS", "-m", "30", "-X", "POST", "https://oauth2.googleapis.com/token"] + data)).get("access_token")
if not at: sys.exit("token error")
def api(path, **q): return json.loads(sh(["curl", "-sS", "-m", "40", f"https://www.googleapis.com/youtube/v3/{path}?" + urllib.parse.urlencode(q), "-H", f"Authorization: Bearer {at}"]))
ch = api("channels", part="contentDetails,statistics,snippet", mine="true")["items"][0]
up = ch["contentDetails"]["relatedPlaylists"]["uploads"]; ids = []; tok = None
for _ in range(4):
    r = api("playlistItems", part="contentDetails", playlistId=up, maxResults=50, **({"pageToken": tok} if tok else {}))
    ids += [i["contentDetails"]["videoId"] for i in r.get("items", [])]; tok = r.get("nextPageToken")
    if not tok: break
vids = []
for i in range(0, len(ids), 50):
    for v in api("videos", part="snippet,statistics,status,contentDetails", id=",".join(ids[i:i + 50])).get("items", []):
        s = v["statistics"]; vids.append({"id": v["id"], "title": v["snippet"]["title"], "published": v["snippet"]["publishedAt"], "privacy": v["status"]["privacyStatus"], "duration": v["contentDetails"]["duration"],
                                          "views": int(s.get("viewCount", 0)), "likes": int(s.get("likeCount", 0)), "comments": int(s.get("commentCount", 0))})
mine = set()   # public repo: keep only public videos + our own pipeline drafts (not other private uploads of the owner)
ip = os.path.join(ST, "index.json")
if os.path.exists(ip): mine = {(c.get("draft") or "").rsplit("/", 1)[-1] for c in json.load(open(ip))}
all_n = len(vids); vids = [v for v in vids if v["privacy"] == "public" or v["id"] in mine]
out = {"fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "fetched_epoch": time.time(), "channel": {"title": ch["snippet"]["title"], "subscribers": int(ch["statistics"].get("subscriberCount", 0)), "views": int(ch["statistics"].get("viewCount", 0)), "videos": int(ch["statistics"].get("videoCount", 0))}, "videos": vids, "total_uploads_incl_private": all_n}
# learning: deleted drafts and weak performers
now = {v["id"] for v in vids}
for v in old.get("videos", []):
    if v["id"] not in now and v.get("privacy") == "private": lesson(f"הבעלים מחק טיוטה: \"{v['title']}\". הנושא או הכותרת לא התאימו, אל תחזור על זה.", "deleted_draft")
pub = [v for v in vids if v["privacy"] == "public" and (time.time() - time.mktime(time.strptime(v["published"][:19], "%Y-%m-%dT%H:%M:%S"))) > 7 * 86400]
if len(pub) >= 8:
    med = sorted(v["views"] for v in pub)[len(pub) // 2]
    for v in pub:
        if v["views"] < med * 0.4: lesson(f"סרטון חלש ({v['views']} צפיות מול חציון {med}): \"{v['title']}\". אל תבחר נושאים כאלה.", "weak_performance")
        if v["views"] > med * 2.5: lesson(f"סרטון חזק ({v['views']} צפיות מול חציון {med}): \"{v['title']}\". חפש יותר נושאים כאלה.", "strong_performance")
hp = os.path.join(ST, "yt_history.jsonl")   # hourly snapshots: lets the app answer "views in the last N hours" exactly
with open(hp, "a") as hf: hf.write(json.dumps({"t": out["fetched_at"], "views": out["channel"]["views"], "subs": out["channel"]["subscribers"]}) + "\n")
with open(os.path.join(ST, "yt_video_history.jsonl"), "a") as vf:   # per-video snapshots (public/unlisted): the data the prediction station fits growth curves on
    vf.write(json.dumps({"t": out["fetched_at"], "v": {v["id"]: [v["views"], v.get("likes", 0), v.get("comments", 0)] for v in vids if v["privacy"] != "private"}}) + "\n")
json.dump(out, open(f, "w"), ensure_ascii=False, indent=1); print("stats:", len(vids), "videos")
try: subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "stations", "predict.py")], timeout=120)
except Exception as e: print("predict failed:", e)

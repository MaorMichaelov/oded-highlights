#!/usr/bin/env python3
"""ONE iteration of the release-day Shorts loop for a streamer who is live (or whose newest VOD is still growing): takes the next 30-minute window of the current VOD that is not processed yet, cuts the best 2 Shorts (vod_shorts.py: peaks + LLM + precise edges + 9:16 + logo) and optionally uploads them as private drafts to the English channel.
State: state/<slug>/live_state.json {vod, done_to_min}.  usage: live_shorts.py --slug kaicenat --platform twitch --credit "Kai Cenat" [--upload --max-upload 2] [--focus "GTA 6 first reactions"] [--force]
--force: ignore the live check and treat the newest VOD as current (tests / backfill)."""
import argparse, json, os, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import vod_shorts as V
def newest(slug, platform):
    if platform == "twitch":
        r = V.sh(["yt-dlp", "--flat-playlist", "--playlist-end", "1", "--print", "%(id)s|%(title)s", f"https://www.twitch.tv/{slug}/videos?filter=archives&sort=time"]).stdout.strip().split("|", 1)
        if not r[0]: return None
        vid = r[0].lstrip("v"); au, _ = V.twitch_urls(vid); return {"vod": vid, "title": r[1] if len(r) > 1 else "", "audio": au}
    d = V.jget(f"https://kick.com/api/v2/channels/{slug}/videos")
    if not d or not d[0].get("source"): return None
    base = d[0]["source"].rsplit("/master.m3u8", 1)[0]; return {"vod": str(d[0]["id"]), "title": d[0].get("session_title") or "", "audio": f"{base}/480p30/playlist.m3u8"}
def is_live(slug, platform):
    if platform == "twitch": return V.sh(["yt-dlp", "--simulate", "--print", "%(is_live)s", f"https://www.twitch.tv/{slug}"]).stdout.strip() == "True"
    try: return bool(V.jget(f"https://kick.com/api/v2/channels/{slug}").get("livestream"))
    except Exception: return False
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--slug", required=True); ap.add_argument("--platform", default="kick"); ap.add_argument("--credit", default=""); ap.add_argument("--upload", action="store_true"); ap.add_argument("--max-upload", type=int, default=2); ap.add_argument("--focus", default=""); ap.add_argument("--force", action="store_true"); ap.add_argument("--window", type=int, default=30); a = ap.parse_args()
    if not a.force and not is_live(a.slug, a.platform): print("offline"); return 0
    cur = newest(a.slug, a.platform)
    if not cur: print("no VOD yet"); return 0
    r = V.sh(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", cur["audio"]]); dur = float(r.stdout.strip() or 0) / 60
    sf = f"state/{a.slug}/live_state.json"; st = json.load(open(sf)) if os.path.exists(sf) else {}
    if st.get("vod") != cur["vod"]: st = {"vod": cur["vod"], "done_to_min": max(0, int(dur) - a.window) if not a.force else 0}   # a new stream: start with the latest window, not the whole past
    a_, b_ = st["done_to_min"], st["done_to_min"] + a.window
    if b_ > dur - 2: print(f"stream at {dur:.0f} min, next window {a_}-{b_} not complete yet"); return 0
    env = dict(os.environ, **({"SHORTS_FOCUS": a.focus} if a.focus else {}))
    print(f"processing {a.slug} VOD {cur['vod']} window {a_}-{b_} (stream length {dur:.0f} min)", flush=True)
    p = subprocess.run([sys.executable, "-u", os.path.join(HERE, "vod_shorts.py"), "--slug", a.slug, "--platform", a.platform, "--vod", cur["vod"], "--from-min", str(a_), "--to-min", str(b_), "--n", "2", "--credit", a.credit or a.slug], env=env)
    st["done_to_min"] = b_; os.makedirs(f"state/{a.slug}", exist_ok=True); json.dump(st, open(sf, "w"))
    if a.upload: subprocess.run([sys.executable, os.path.join(HERE, "upload_shorts.py"), a.slug, str(a.max_upload)], env=dict(os.environ, CHANNEL_YT="en"))
    return 0
if __name__ == "__main__": sys.exit(main())

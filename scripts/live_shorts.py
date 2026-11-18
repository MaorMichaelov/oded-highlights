#!/usr/bin/env python3
"""ONE iteration of the release-day Shorts loop for a streamer who is live (or whose newest VOD is still growing): takes the next 30-minute window of the current VOD that is not processed yet, cuts the best 2 Shorts (vod_shorts.py: peaks + LLM + precise edges + 9:16 + logo) and optionally uploads them as private drafts to the English channel.
State: state/<slug>/live_state.json {vod, done_to_min}.  usage: live_shorts.py --slug kaicenat --platform twitch --credit "Kai Cenat" [--upload --max-upload 2] [--focus "GTA 6 first reactions"] [--force]
--force: ignore the live check and treat the newest VOD as current (tests / backfill)."""
import argparse, json, os, re, subprocess, sys, time
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
def media_minutes(url):
    """Length of the (possibly still growing) stream in minutes. A live HLS playlist has no duration for ffprobe ("N/A"), so fall back to the sum of its #EXTINF segment lengths."""
    r = V.sh(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", url])
    try: return float(r.stdout.strip()) / 60
    except Exception: pass
    txt = V.sh(["curl", "-sS", "-m", "40", "-L", url]).stdout
    return sum(float(x) for x in re.findall(r"#EXTINF:([0-9.]+)", txt)) / 60
def is_live(slug, platform):
    if platform == "twitch": return V.sh(["yt-dlp", "--simulate", "--print", "%(is_live)s", f"https://www.twitch.tv/{slug}"]).stdout.strip() == "True"
    try: return bool(V.jget(f"https://kick.com/api/v2/channels/{slug}").get("livestream"))
    except Exception: return False
def dispatch_long(a, cur, f, t):
    """Start the long-video workflow for minutes f..t of the running VOD (a finished chunk of the stream), upload as private draft if --upload."""
    c = ["gh", "api", f"repos/{os.environ.get('GITHUB_REPOSITORY', 'MaorMichaelov/oded-highlights')}/actions/workflows/long-video.yml/dispatches", "-f", "ref=main", "-f", f"inputs[slug]={a.slug}", "-f", f"inputs[platform]={a.platform}", "-f", f"inputs[vod]={cur['vod']}", "-f", f"inputs[from_min]={f}", "-f", f"inputs[to_min]={t}", "-f", f"inputs[credit]={a.credit or a.slug}", "-f", f"inputs[title_hint]={a.focus or cur.get('title', '')}", "-f", f"inputs[upload]={'true' if a.upload else 'false'}"]
    r = subprocess.run(c, capture_output=True, text=True); print(f"long video {f}-{t} min dispatched" if r.returncode == 0 else "long dispatch failed: " + r.stderr[:200], flush=True)
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--slug", required=True); ap.add_argument("--platform", default="kick"); ap.add_argument("--credit", default=""); ap.add_argument("--upload", action="store_true"); ap.add_argument("--max-upload", type=int, default=2); ap.add_argument("--focus", default=""); ap.add_argument("--force", action="store_true"); ap.add_argument("--window", type=int, default=30); ap.add_argument("--long-every", type=int, default=0, help="also start a LONG video (long-video workflow, private draft) for every N finished minutes of the stream (0 = off)"); a = ap.parse_args()
    if not a.force and not is_live(a.slug, a.platform): print("offline"); return 0
    cur = newest(a.slug, a.platform)
    if not cur: print("no VOD yet"); return 0
    dur = media_minutes(cur["audio"])
    sf = f"state/{a.slug}/live_state.json"; st = json.load(open(sf)) if os.path.exists(sf) else {}
    if st.get("vod") != cur["vod"]: st = {"vod": cur["vod"], "done_to_min": max(0, int(dur) - a.window) if not a.force else 0}   # a new stream: start with the latest window, not the whole past
    a_, b_ = st["done_to_min"], st["done_to_min"] + a.window
    if b_ > dur - 2: print(f"stream at {dur:.0f} min, next window {a_}-{b_} not complete yet"); return 0
    env = dict(os.environ, **({"SHORTS_FOCUS": a.focus} if a.focus else {}))
    print(f"processing {a.slug} VOD {cur['vod']} window {a_}-{b_} (stream length {dur:.0f} min)", flush=True)
    p = subprocess.run([sys.executable, "-u", os.path.join(HERE, "vod_shorts.py"), "--slug", a.slug, "--platform", a.platform, "--vod", cur["vod"], "--from-min", str(a_), "--to-min", str(b_), "--n", "2", "--credit", a.credit or a.slug], env=env)
    if a.long_every and b_ - st.get("long_to_min", st.get("start_min", a_)) >= a.long_every:
        lf = st.get("long_to_min", st.get("start_min", a_)); dispatch_long(a, cur, lf, b_); st["long_to_min"] = b_
    st.setdefault("start_min", a_)
    st["done_to_min"] = b_; os.makedirs(f"state/{a.slug}", exist_ok=True); json.dump(st, open(sf, "w"))
    if a.upload: subprocess.run([sys.executable, os.path.join(HERE, "upload_shorts.py"), a.slug, str(a.max_upload)], env=dict(os.environ, CHANNEL_YT="en"))
    return 0
if __name__ == "__main__": sys.exit(main())

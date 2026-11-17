#!/usr/bin/env python3
"""Top audience-made CLIPS of the last N days (Kick: /api/v2/channels/<slug>/clips sorted by views; Twitch: yt-dlp clips list, no key) -> English Shorts (9:16, blurred fill, captions, hook title) for the English channel.
The audience already voted with views: ready-made highlight candidates. usage: clips_to_shorts.py --platform kick --slug n3on --days 14 --n 6 --credit N3on [--out state/n3on/shorts]
Score = 2*log10(views) (e.g. 130k views -> 10.2) so upload_shorts.py uploads the strongest first."""
import argparse, datetime as dt, json, math, os, re, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "stations"))
import vod_shorts as V
def list_kick(slug, days):
    out = []; cut = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    for tm in ("week", "month"):
        try: d = V.jget(f"https://kick.com/api/v2/channels/{slug}/clips?sort=view&time={tm}")
        except Exception as e: print("kick clips failed", e); continue
        for c in d.get("clips", []):
            try: created = dt.datetime.fromisoformat(c["created_at"].replace("Z", "+00:00"))
            except Exception: continue
            dur = float(c.get("duration") or 0)
            if created >= cut and 8 <= dur <= 120 and not any(x["id"] == c["id"] for x in out): out.append({"id": c["id"], "title": c.get("title") or "", "views": int(c.get("view_count") or 0), "dur": dur, "src": c.get("clip_url") or c.get("video_url"), "created": c["created_at"][:10]})
    return sorted(out, key=lambda x: -x["views"])
def list_twitch(login, days):
    rng = "7d" if days <= 7 else "30d"; out = []
    r = V.sh(["yt-dlp", "--flat-playlist", "--playlist-end", "25", "--print", "%(id)s|%(url)s|%(duration)s|%(view_count)s|%(title)s", f"https://www.twitch.tv/{login}/clips?filter=clips&range={rng}"])
    for l in r.stdout.splitlines():
        p = l.split("|", 4)
        if len(p) < 5: continue
        try: dur = float(p[2]); views = int(float(p[3]))
        except Exception: continue
        if 8 <= dur <= 120: out.append({"id": p[0], "title": p[4], "views": views, "dur": dur, "src": p[1], "created": ""})
    return sorted(out, key=lambda x: -x["views"])
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--platform", default="kick"); ap.add_argument("--slug", required=True); ap.add_argument("--days", type=int, default=14); ap.add_argument("--n", type=int, default=6); ap.add_argument("--credit", default=""); ap.add_argument("--out", default=None); a = ap.parse_args()
    out = a.out or f"state/{a.slug}/shorts"; os.makedirs(out, exist_ok=True); credit = a.credit or a.slug; import shorts as SH
    cands = list_twitch(a.slug, a.days) if a.platform == "twitch" else list_kick(a.slug, a.days)
    print(f"{len(cands)} candidate clips in the last {a.days} days; top views:", [c["views"] for c in cands[:8]], flush=True); made = 0; tmp = tempfile.mkdtemp()
    for c in cands:
        if made >= a.n: break
        if V.GAMBLING.search(c["title"]): continue
        mp4 = f"{tmp}/{c['id']}.mp4"
        r = V.sh(["yt-dlp", "-o", mp4, c["src"]]) if a.platform == "twitch" else V.sh(["ffmpeg", "-v", "error", "-y", "-i", c["src"], "-c", "copy", mp4])
        if not os.path.exists(mp4) or os.path.getsize(mp4) < 100000: print("download failed", c["id"], r.stderr[-150:]); continue
        mp3 = f"{tmp}/{c['id']}.mp3"; V.sh(["ffmpeg", "-v", "error", "-y", "-i", mp4, "-vn", "-ac", "1", "-ar", "16000", "-c:a", "libmp3lame", "-b:a", "48k", mp3])
        words = V.whisper(mp3, None)
        if len(words) < 6: print("no usable speech, skipped:", c["title"]); continue
        txt = " ".join(w["word"].strip() for w in words)[:2500]
        j = V.llm(f"You edit YouTube Shorts for an English fan channel of the streamer {credit}. This audience-made clip ({int(c['dur'])} s, {c['views']} views, original clip title: '{c['title']}') has this transcript (automatic, may contain errors, may not be English):\n{txt}\n\nReturn JSON only: {{\"title\":\"English YouTube Shorts title 40-70 chars, hook first, put the streamer's name ({credit}) in it when natural, ends with ! or ?, NO profanity, never invent facts\",\"hook\":\"3-6 word on-screen text, English\",\"reject\":false,\"why\":\"\"}}. Set reject=true for gambling/promo talk, hate speech, slurs, sexual content, self-harm, minors, or if the clip is not understandable without context.")
        if not j or j.get("reject"): print("rejected:", c["title"], (j or {}).get("why")); continue
        ass = f"{out}/clip_{c['id']}.ass"; dur = float(V.sh(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", mp4]).stdout.strip() or c["dur"])
        SH.make_ass([{"word": w["word"], "start": w["start"], "end": w["end"]} for w in words], 0.0, dur, ass)
        t_ = open(ass, encoding="utf-8").read().replace("&H0028E678", "&H0000E6FF"); open(ass, "w", encoding="utf-8").write(t_)
        dest = f"{out}/clip_{c['id']}.mp4"
        if not V.render2(mp4, 0.0, dur, ass, dest, j.get("hook", ""), None): print("render failed", c["id"]); continue
        title = j["title"].strip()[:90]; where = ("Twitch (https://twitch.tv/" if a.platform == "twitch" else "Kick (https://kick.com/") + f"{a.slug})"
        meta = {"title": title + " #Shorts", "hook": j.get("hook", ""), "score": round(2 * math.log10(max(c["views"], 10)), 1), "source": {"slug": a.slug, "platform": a.platform, "clip": c["id"], "views": c["views"], "created": c["created"]},
                "description": f"{title}\n\nClip from {credit}'s live stream on {where}. Unofficial fan channel, not affiliated.\n#Shorts #{a.slug.replace('-', '')} #ClipGlobe"}
        json.dump(meta, open(dest[:-4] + ".json", "w"), ensure_ascii=False, indent=1); made += 1; print(f"SHORT {made}: {c['views']} views | {title}", flush=True)
    if not made: sys.exit("no short produced")
if __name__ == "__main__": main()

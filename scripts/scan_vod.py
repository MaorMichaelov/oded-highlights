#!/usr/bin/env python3
"""FIND LONG VIDEOS in a streamer's VOD (Kick or Twitch, English channel): samples 60 s of speech every N minutes (cheap: ~1/10 of the audio), lets the LLM label what is happening, then plans up to K
LONG-VIDEO candidates (20-60 min each): reactions to videos/news/trailers/songs, games and challenges, guest conversations, big events, real stories - like the long videos of the Oded channel.
Output: state/<slug>/scan_<vod>.json (samples + plan); with --dispatch it starts the long-video workflow for every candidate (needs GH_TOKEN).
usage: scan_vod.py --slug n3on --platform kick --vod ID --from-min 0 --to-min 190 --credit N3on --k 3 [--dispatch] [--upload]"""
import argparse, json, os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import vod_shorts as V
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--slug", required=True); ap.add_argument("--platform", default="kick"); ap.add_argument("--vod", default="auto"); ap.add_argument("--from-min", type=float, default=0); ap.add_argument("--to-min", type=float, default=240)
    ap.add_argument("--step", type=int, default=10); ap.add_argument("--credit", default=""); ap.add_argument("--k", type=int, default=3); ap.add_argument("--dispatch", action="store_true"); ap.add_argument("--upload", action="store_true"); a = ap.parse_args()
    credit = a.credit or a.slug
    if a.platform == "twitch":
        tv = V.twitch_pick(a.slug, a.vod); vid = str(tv["id"]); AUDIO, _ = V.twitch_urls(vid); vtitle = tv["title"]; vdur = tv["dur_s"] / 60
    else:
        v = V.pick_vod(a.slug, a.vod); base = v["source"].rsplit("/master.m3u8", 1)[0]; vid = str(v["id"]); AUDIO = f"{base}/480p30/playlist.m3u8"; vtitle = v.get("session_title") or ""; vdur = (v.get("duration") or 0) / 60000
    end = min(a.to_min, vdur or a.to_min); tmp = tempfile.mkdtemp(); samples = []
    for m in range(int(a.from_min), int(end) - 1, a.step):
        mp3 = f"{tmp}/s{m}.mp3"
        r = V.sh(["ffmpeg", "-v", "error", "-y", "-ss", str((m + 1) * 60), "-t", "60", "-i", AUDIO, "-vn", "-ac", "1", "-ar", "16000", "-c:a", "libmp3lame", "-b:a", "48k", mp3])
        if r.returncode: print("sample failed at", m, r.stderr[-120:]); continue
        txt = " ".join(w["word"].strip() for w in V.whisper(mp3, "en"))[:380]; samples.append({"min": m, "text": txt}); print(f"sample {m} min: {len(txt)} chars", flush=True)
    if len(samples) < 4: sys.exit("too few samples")
    body = "\n".join(f"[{s['min']} min] {s['text']}" for s in samples)
    plan = V.llm(f"{credit} streams live (English). Stream title: '{vtitle}'. Below: a 60-second speech sample every {a.step} minutes of one stream (automatic transcript, may contain errors), minute marks are from the stream start. Plan up to {a.k} LONG highlight videos (20-60 minutes each, "
                 "from_min and to_min multiples of 5, not overlapping) for a YouTube clips channel. GOOD: the streamer reacting to a video/news/trailer/song/other streamer, a game or challenge session, a conversation with a guest, a big event or real story with a beginning and an end. BAD: gambling/casino/promo talk, empty chatter, long silences, music-only stretches, anything sexual or hateful. "
                 "Return JSON only: {\"plan\":[{\"from_min\":m,\"to_min\":m,\"type\":\"reaction|game|guest|event|story\",\"why\":\"one sentence\",\"hint\":\"short description for the title writer, only facts from the samples\"}],\"notes\":\"\"}. Empty plan if nothing qualifies.\n\n" + body)
    pl = [p for p in (plan or {}).get("plan", []) if 15 <= float(p["to_min"]) - float(p["from_min"]) <= 75][:a.k]
    out = {"slug": a.slug, "platform": a.platform, "vod": vid, "title": vtitle, "samples": samples, "plan": pl, "notes": (plan or {}).get("notes", "")}
    os.makedirs(f"state/{a.slug}", exist_ok=True); json.dump(out, open(f"state/{a.slug}/scan_{vid}.json", "w"), ensure_ascii=False, indent=1)
    for p in pl: print(f"PLAN {p['type']}: {p['from_min']}-{p['to_min']} min | {p.get('why')} | {p.get('hint')}")
    if a.dispatch:
        for p in pl:
            c = ["gh", "api", f"repos/{os.environ.get('GITHUB_REPOSITORY', 'MaorMichaelov/oded-highlights')}/actions/workflows/long-video.yml/dispatches", "-f", "ref=main", "-f", f"inputs[slug]={a.slug}", "-f", f"inputs[platform]={a.platform}", "-f", f"inputs[vod]={vid}",
                 "-f", f"inputs[from_min]={int(p['from_min'])}", "-f", f"inputs[to_min]={int(p['to_min'])}", "-f", f"inputs[credit]={credit}", "-f", f"inputs[title_hint]={p.get('type', '')}: {p.get('hint', '')}"[:300], "-f", f"inputs[upload]={'true' if a.upload else 'false'}"]
            r = subprocess.run(c, capture_output=True, text=True); print("dispatched long video", p["from_min"], p["to_min"], r.returncode, r.stderr[-120:])
    if not pl: print("no long-video candidate found in this stretch")
if __name__ == "__main__": main()

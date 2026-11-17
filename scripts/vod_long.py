#!/usr/bin/env python3
"""LONG English video from a window of a Kick/Twitch VOD (WORLD CLIPS / ClipGlobe): one complete session or reaction, kept continuous (owner rule: great sessions stay whole), 1080p60, precise start/end.
usage: vod_long.py --slug n3on --platform kick --vod ID --from-min 70 --to-min 100 --credit N3on [--out state/n3on/long]
Steps: Groq whisper (English, word times) over the window -> LLM writes title / description / chapters from the real transcript (Gemini first, Groq fallback) -> start/end snapped into pauses with cutsnap
-> re-encode the window (libx264 veryfast crf 19, source frame rate/size, AAC 192k, -movflags +faststart) -> <out>/long_<vod>_<start>.mp4 + .json (private draft meta). Upload separately with scripts/upload_shorts.py (it uploads every mp4+json pair)."""
import argparse, json, os, re, subprocess, sys, tempfile, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import vod_shorts as V, cutsnap as CS
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--slug", required=True); ap.add_argument("--platform", default="kick"); ap.add_argument("--vod", default="auto"); ap.add_argument("--from-min", type=float, required=True); ap.add_argument("--to-min", type=float, required=True); ap.add_argument("--credit", default=""); ap.add_argument("--out", default=None); ap.add_argument("--title-hint", default=""); a = ap.parse_args()
    out = a.out or f"state/{a.slug}/long"; os.makedirs(out, exist_ok=True); credit = a.credit or a.slug
    if a.platform == "twitch":
        tv = V.twitch_pick(a.slug, a.vod); vid = str(tv["id"]); AUDIO, VIDEO = V.twitch_urls(vid); vtitle = tv["title"]
    else:
        v = V.pick_vod(a.slug, a.vod); base = v["source"].rsplit("/master.m3u8", 1)[0]; vid = str(v["id"]); AUDIO, VIDEO = f"{base}/480p30/playlist.m3u8", f"{base}/1080p60/playlist.m3u8"; vtitle = v.get("session_title") or ""
    t0 = a.from_min * 60; dur = (a.to_min - a.from_min) * 60; tmp = tempfile.mkdtemp(); words = []; envs = []
    for c0 in np.arange(0, dur, 600):
        d = min(600, dur - c0); mp3 = f"{tmp}/a{int(c0)}.mp3"
        r = V.sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{t0 + c0:.1f}", "-t", f"{d:.1f}", "-i", AUDIO, "-vn", "-ac", "1", "-ar", "16000", "-c:a", "libmp3lame", "-b:a", "48k", mp3])
        if r.returncode: print("audio chunk failed", r.stderr[-200:]); continue
        cw = []
        for _try in range(3):   # a failed chunk silently cut a 30 min window to 20 min (16 Nov bug): retry, and say so loudly if it still fails
            cw = V.whisper(mp3)
            if cw: break
            print("whisper returned nothing for chunk", int(c0 / 60), "- retrying", flush=True); time.sleep(8)
        if not cw: print("WARNING: chunk", int(c0 / 60), "has no transcript", flush=True)
        for w in cw: words.append({"word": w["word"], "start": t0 + c0 + w["start"], "end": t0 + c0 + w["end"]})
        envs.append((t0 + c0, mp3)); print(f"chunk {int(c0 / 60)}-{int((c0 + d) / 60)} min: {len(words)} words", flush=True); time.sleep(2)
    if len(words) < 200: sys.exit("too little speech in the window")
    # the plan comes from coarse samples (+-5 min): let the LLM find where the session really starts/ends inside the transcript of the first and last 8 minutes
    try:
        def lines_of(lo, hi): return "\n".join(f"[{int(w0)}] " + " ".join(x["word"].strip() for x in grp) for w0, grp in _groups(words, lo, hi))
        def _groups(ws, lo, hi):
            out_, cur_, t_ = [], [], None
            for w in ws:
                if not (lo <= w["start"] < hi): continue
                if t_ is None: t_ = w["start"]
                cur_.append(w)
                if w["end"] - t_ >= 8: out_.append((t_, cur_)); cur_, t_ = [], None
            if cur_: out_.append((t_, cur_))
            return out_
        head = lines_of(t0, t0 + 480); tail = lines_of(t0 + dur - 480, t0 + dur)
        rj = V.llm(f"A long highlight video was planned from the streamer {credit}'s stream; the topic hint is: '{a.title_hint}'. The planned window may start a few minutes too early or end a few minutes too late. Below are the first and the last 8 minutes of the window as [absolute second] text. "
                   "Return JSON only: {\"start_second\": the absolute second where the real session/topic begins (the first sentence that belongs to it; skip greetings, unrelated chatter and waiting before it), \"end_second\": the absolute second where it really ends (the end of the last sentence that belongs to it; skip goodbyes and unrelated chatter after it), \"why\": \"\"}. Keep the whole window if it is already right.\n\nSTART:\n" + head[:4500] + "\n\nEND:\n" + tail[:4500])
        if rj:
            ns, ne = float(rj["start_second"]), float(rj["end_second"])
            if t0 - 1 <= ns <= t0 + 540 and t0 + dur - 540 <= ne <= t0 + dur + 1 and ne - ns >= 600:
                print(f"LLM edge refinement: start {t0:.0f}->{ns:.0f}, end {t0 + dur:.0f}->{ne:.0f} ({rj.get('why')})"); words = [w for w in words if ns - 2 <= w["start"] <= ne + 2]; t0, dur = ns, ne - ns
    except Exception as e: print("edge refinement skipped:", e)
    # edges: the first and last audio chunk give the energy envelope around the cut points
    s0 = max(t0, min(w["start"] for w in words)); e0 = max(w["end"] for w in words); s1, e1 = s0 - 0.2, min(t0 + dur, e0 + 0.4)
    try:
        env, hop = CS.energy_db(envs[0][1]); first = [w for w in words if w["start"] >= t0][0]; s1 = CS.snap_start(first["start"], words, env, hop, envs[0][0])
        env2, hop2 = CS.energy_db(envs[-1][1]); last_end = min(max(w["end"] for w in words), t0 + dur - 0.3); e1 = CS.snap_end(min(last_end, [w for w in words if w["end"] <= last_end][-1]["start"] + 1.4), words, env2, hop2, envs[-1][0])
        print(f"edge snap: start {t0:.2f}->{s1:.2f}  end {t0 + dur:.2f}->{e1:.2f}")
    except Exception as e: print("edge snap failed, keeping the window edges:", e)
    s1 = max(s1, t0 - 0.5); e1 = max(e1, s1 + 60)
    # LLM metadata from the real transcript (evenly sampled lines with [seconds from the clip start])
    lines = []; cur = []; ts = None
    for w in words:
        if ts is None: ts = w["start"]
        cur.append(w["word"].strip())
        if w["end"] - ts >= 20: lines.append(f"[{int(ts - s1)}] " + " ".join(cur)[:170]); cur, ts = [], None   # 170 chars per 20 s line, spread over the WHOLE window (a 9000-char cut used to show only the first 6 minutes of a 20 min clip: wrong chapters)
    step = max(1, len(lines) // 80); sample = "\n".join(lines[::step])[:15000]
    prompt = (f"You write the YouTube metadata of a LONG highlight video cut from {credit}'s live stream (platform: {a.platform}); the clip is one continuous session of {int((e1 - s1) / 60)} minutes. The transcript is automatic and may contain errors; never invent facts, people or quotes. Stream title: '{vtitle}'. {a.title_hint}\n"
              "Return JSON only: {\"title\":\"English, 50-85 chars, literal and specific (only what really happens, NEVER invent facts, reveals, surprises or hype words), name the streamer, put the streamer's name in it, what really happens, no profanity, no ALL CAPS shouting, ends without a period\",\"description\":\"3 English sentences with specifics (who, what, key moments)\",\"hashtags\":[\"#" + a.slug.replace('-', '') + "\", ...4 more],\"tags\":[...8 keywords],"
              "\"chapters\":[{\"second\":n,\"title\":\"<=6 specific words\"}] (8-14 entries IN ORDER, the first at 0, spread over the whole clip, seconds from the clip start taken from the transcript lines),\"reject\":false,\"why\":\"\"}. Set reject=true (and explain in why) if the clip is mostly gambling/casino/promo talk, hate speech, sexual content, or empty chatter.\n\nTranscript (lines are [seconds from the clip start] text):\n" + sample)
    HYPE = re.compile(r"epic|wild|shock|insane|crazy|you won't believe|unbelievable|mind-?blow|exposed|leaked|teaser|reveal|surprise", re.I)   # titles/descriptions must state only what really happens
    j = V.llm(prompt)
    if j and not j.get("reject") and HYPE.search(j.get("title", "")): j = V.llm(prompt + "\n\nYour previous title used hype words or invented details. Be strictly literal: only what is really said in the transcript, plain words, no 'epic', 'reveal', 'surprise', 'shocking'. Do not mention anything that is not in the transcript lines.")
    if j and HYPE.search(j.get("title", "")): j["title"] = HYPE.sub("", j["title"]).replace("  ", " ").strip(" -:,")
    if not j or j.get("reject"): sys.exit("metadata step rejected the window: " + str((j or {}).get("why")))
    # cut + encode
    dd = e1 - s1; mp4 = f"{out}/long_{vid}_{int(s1)}.mp4"
    import brand
    main_mp4 = mp4[:-4] + "_main.mp4"   # the clip with the owner's logo as a corner watermark; the logo bumper is prepended below
    r = V.sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{s1:.3f}", "-t", f"{dd:.3f}", "-i", VIDEO, "-loop", "1", "-i", brand.LOGO, "-filter_complex", "[1:v]format=rgba,scale=120:-1,colorchannelmixer=aa=0.85[wm];[0:v][wm]overlay=W-w-32:H-h-32:shortest=1,format=yuv420p[v]",
              "-map", "[v]", "-map", "0:a:0", "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", "-af", "afade=t=in:d=0.02,afade=t=out:st=%.3f:d=0.05" % (dd - 0.05), "-t", f"{dd:.3f}", "-movflags", "+faststart", main_mp4])
    if r.returncode: sys.exit("encode failed: " + r.stderr[-400:])
    pr = V.sh(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate", "-of", "csv=p=0", main_mp4]).stdout.strip().split(",")
    bw, bh = int(pr[0]), int(pr[1]); fn, fd = pr[2].split("/"); bfps = round(float(fn) / float(fd), 3); BUMP = 2.5
    bump = mp4[:-4] + "_bump.mp4"; brand.make_bumper(bump, bw, bh, bfps, BUMP)
    open(mp4[:-4] + "_list.txt", "w").write(f"file '{os.path.abspath(bump)}'\nfile '{os.path.abspath(main_mp4)}'\n")
    r = V.sh(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", mp4[:-4] + "_list.txt", "-c", "copy", "-movflags", "+faststart", mp4])
    if r.returncode: sys.exit("join failed: " + r.stderr[-400:])
    for f_ in (main_mp4, bump, mp4[:-4] + "_list.txt"): os.remove(f_)
    dd += BUMP   # the published video is 2.5 s longer than the cut window
    def mmss(sec): sec = int(max(0, sec)); return f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}" if sec >= 3600 else f"{sec // 60:02d}:{sec % 60:02d}"
    ch = sorted({int(c["second"]): str(c["title"]).strip()[:50] for c in (j.get("chapters") or []) if str(c.get("title", "")).strip()}.items()); ch = [(t, n) for t, n in ch if 0 <= t < dd - 20]
    if ch: ch[0] = (0, ch[0][1])
    chap = "\n".join(f"{mmss(t + (2.5 if t > 0 else 0))} {n}" for t, n in ch) if len(ch) >= 3 else ""
    hs = list(dict.fromkeys([h for h in (j.get("hashtags") or []) if isinstance(h, str) and h.startswith("#")][:6] + ["#" + a.slug.replace("-", ""), "#" + ("Twitch" if a.platform == "twitch" else "Kick"), "#ClipGlobe"]))
    src_line = ("Twitch (https://twitch.tv/" if a.platform == "twitch" else "Kick (https://kick.com/") + f"{a.slug})"
    desc = f"Clips from {credit}'s live streams on {src_line} | Unofficial fan channel, not affiliated.\n{j.get('description', '').strip()}\n" + (f"\nChapters:\n{chap}\n" if chap else "") + f"\nClip from the live stream: {src_line}\nThis is an unofficial fan channel: all clips are taken from {credit}'s streams. It is not {credit}'s official channel.\n\n" + " ".join(hs)
    meta = {"title": j["title"].strip()[:98], "description": desc, "tags": (j.get("tags") or [])[:12] + [credit, "highlights"], "privacy": "private", "score": 100, "source": {"slug": a.slug, "platform": a.platform, "vod": vid, "start_s": round(s1), "end_s": round(e1), "minutes": round(dd / 60, 1)}}
    json.dump(meta, open(mp4[:-4] + ".json", "w"), ensure_ascii=False, indent=1); print(f"LONG READY {mp4} ({dd / 60:.1f} min, {os.path.getsize(mp4) // 1_000_000} MB) | {meta['title']}")
if __name__ == "__main__": main()

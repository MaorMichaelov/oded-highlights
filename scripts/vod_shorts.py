#!/usr/bin/env python3
"""VOD -> SHORTS for any Kick streamer (English). Built from the research in docs/SHORTS_RESEARCH.md.
usage: vod_shorts.py --slug n3on [--vod ID|auto] [--from-min 0] [--to-min 60] [--n 3] [--out state/n3on/shorts]
Steps: pick a VOD (skips gambling/giveaway streams) -> audio of the window -> Groq whisper (English, word times) -> per-second signals (audio energy + words/s) -> robust z-score peaks
-> free LLM scores each peak window (setup sentence .. payoff sentence, rejects gambling/promo/hard lines) -> snap to word boundaries (20-58 s) -> cut 1080p60 from Kick HLS
-> 9:16 render (blurred fill + centred stream, big captions, -14 LUFS) via scripts/stations/shorts.py. No chat signal for past VODs (Kick keeps no chat replay): live runs add chat spikes later.
env: GROQ_API_KEY"""
import argparse, json, os, re, subprocess, sys, tempfile, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, os.path.join(HERE, "stations")); sys.path.insert(0, HERE)
GAMBLING = re.compile(r"jack\.?com|gambl|giveaway|casino|stake\.|slots?\b|roulette|promo code|use code|sportsbook|betting|\bbets?\b|18\+", re.I)
def sh(c, **k): return subprocess.run(c, capture_output=True, text=True, **k)
def jget(url): return json.loads(sh(["curl", "-sS", "-m", "40", "-A", "Mozilla/5.0", url]).stdout)
def groq(model, messages, mx=1200):
    key = os.environ["GROQ_API_KEY"]
    r = sh(["curl", "-sS", "-m", "120", "https://api.groq.com/openai/v1/chat/completions", "-H", "Authorization: Bearer " + key, "-H", "Content-Type: application/json", "-d", json.dumps({"model": model, "messages": messages, "max_tokens": mx, "reasoning_effort": "low"})])
    d = json.loads(r.stdout)
    if "choices" not in d: raise RuntimeError(str(d.get("error", d))[:160])
    return d["choices"][0]["message"]["content"]
def gemini(prompt):
    key = os.environ.get("GEMINI_API_KEY")
    if not key: return None
    for model in ("gemini-flash-latest", "gemini-3.5-flash"):
        r = sh(["curl", "-sS", "-m", "120", f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent", "-H", "x-goog-api-key: " + key, "-H", "Content-Type: application/json", "-d", json.dumps({"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1500, "responseMimeType": "application/json"}})])
        try: return json.loads(json.loads(r.stdout)["candidates"][0]["content"]["parts"][0]["text"])
        except Exception as e: print("gemini", model, "failed:", r.stdout[:160])
    return None
def llm(prompt):   # Gemini first (the free Groq key is shared with the live loop and often rate-limited), then Groq with model rotation
    g = gemini(prompt)
    if g: return g
    for rnd in range(3):
        for m in ("openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3-32b"):
            try:
                txt = groq(m, [{"role": "user", "content": prompt}]); return json.loads(re.search(r"\{.*\}", re.sub(r"<think>.*?</think>", "", txt, flags=re.S), re.S).group(0))
            except Exception as e: print("llm", m, "failed:", str(e)[:140])
        time.sleep(20)
    return None
def pick_vod(slug, vid):
    vs = jget(f"https://kick.com/api/v2/channels/{slug}/videos")
    for v in vs:
        title = v.get("session_title") or ""
        if str(v["id"]) == str(vid) or (vid == "auto" and (v.get("duration") or 0) > 25 * 60000 and not GAMBLING.search(title)): return v
    sys.exit("no suitable VOD")
def twitch_pick(login, vid):
    """Twitch VOD list WITHOUT an API key (yt-dlp works from a GitHub runner, probed 17 Nov): returns {"id","title","dur_s"}"""
    r = sh(["yt-dlp", "--flat-playlist", "--playlist-end", "12", "--print", "%(id)s|%(duration)s|%(title)s", f"https://www.twitch.tv/{login}/videos?filter=archives&sort=time"])
    for l in r.stdout.splitlines():
        p = l.split("|", 2)
        if len(p) < 3: continue
        i_, d_, t_ = p[0].lstrip("v"), (float(p[1]) if p[1] not in ("NA", "None", "") else 0), p[2]
        if str(i_) == str(vid) or (vid == "auto" and d_ > 25 * 60 and not GAMBLING.search(t_)): return {"id": i_, "title": t_, "dur_s": d_}
    sys.exit("no suitable Twitch VOD")
def twitch_urls(vod_id):
    """direct HLS playlist URLs (signed, valid for hours): source-quality video and audio-only"""
    a = sh(["yt-dlp", "-g", "-f", "audio_only/worstaudio/worst", f"https://www.twitch.tv/videos/{vod_id}"]).stdout.split()
    v = sh(["yt-dlp", "-g", "-f", "best", f"https://www.twitch.tv/videos/{vod_id}"]).stdout.split()
    if not a or not v: sys.exit("could not resolve Twitch playlist URLs")
    return a[0], v[0]
def whisper(path, lang="en"):   # Groq whisper large-v3-turbo, word timestamps (free tier: 7200 audio-seconds/hour)
    r = sh(["curl", "-sS", "-m", "300", "https://api.groq.com/openai/v1/audio/transcriptions", "-H", "Authorization: Bearer " + os.environ["GROQ_API_KEY"], "-F", f"file=@{path}", "-F", "model=whisper-large-v3-turbo"] + (["-F", "language=" + lang] if lang else []) + ["-F", "response_format=verbose_json", "-F", "timestamp_granularities[]=word"])
    return json.loads(r.stdout).get("words", [])
def render2(body, s, e, ass, out, hook, peak):
    """9:16 render with the research rules: blurred fill + centred stream, hook text on frame 0 (0-1.8 s), one punch-in (100->112%) at the peak, an impact SFX at the peak (assets/sfx/boom.wav, quiet), burned-in captions, -14 LUFS."""
    import shorts as SH
    fonts = [os.path.join(d, f) for d in SH.FONTS for f in (os.listdir(d) if os.path.isdir(d) else []) if f.lower().endswith(".ttf") and ("black" in f.lower() or "bold" in f.lower())]
    ff = fonts[0] if fonts else "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    safe = re.sub(r"[^A-Za-z0-9 !?']", "", (hook or "")).upper().replace("'", "")[:40]
    if len(safe) > 16:   # QA by Gemini (16 Nov): a 22+ char hook ran off both edges at 80 px; wrap into two centred lines and size to fit the safe width (~900 px)
        w_ = safe.split(); a_, b_ = [], []
        for x_ in w_: (a_ if len(" ".join(a_ + [x_])) <= max(12, len(safe) // 2 + 2) else b_).append(x_)
        safe = " ".join(a_) + "|" + " ".join(b_) if b_ else " ".join(a_)
    P = max(0.0, peak - s); fr = int(P * 30)
    z = f"if(between(on,{fr},{fr + 7}),1+0.07*(on-{fr})/7,if(between(on,{fr + 7},{fr + 30}),1.07-0.07*(on-{fr + 7})/23,1))" if peak else "1"
    dt = "".join(f",drawtext=fontfile={ff}:text='{ln}':fontsize=64:fontcolor=white:borderw=6:bordercolor=black:x=(w-text_w)/2:y={300 + 84 * k}:enable='lt(t,1.8)'" for k, ln in enumerate([x for x in safe.split("|") if x.strip()]))
    vf = ("[0:v]split=2[a][b];[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=28:4,eq=brightness=-0.12[bg];[b]scale=1080:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2[v0];"
          f"[v0]zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1080x1920:fps=30[v1];[v1]subtitles={ass.replace(':', chr(92) + ':')}" + (":fontsdir=" + SH.FONTS[0] if SH.FONTS else "") + dt + "[v]")
    sfx = os.path.join(ROOT, "assets", "sfx", "boom.wav"); have = peak and os.path.exists(sfx) and os.environ.get("SHORTS_SFX") == "1"   # research 16 Nov: the Shorts/clips that travel on Kai/N3on are raw single takes; SFX/zoom spam reads as AI slop, so SFX is off by default
    cmd = ["ffmpeg", "-v", "error", "-y", "-ss", f"{s:.3f}", "-i", body] + (["-i", sfx] if have else []) + ["-t", f"{e - s:.3f}", "-filter_complex"]
    af = (f"[1:a]adelay={int(P * 1000)}|{int(P * 1000)},volume=-9dB[sx];[0:a][sx]amix=inputs=2:normalize=0:duration=first,loudnorm=I=-14:TP=-1.5:LRA=7,aresample=48000[aud]" if have else "[0:a]loudnorm=I=-14:TP=-1.5:LRA=7,aresample=48000[aud]")
    cmd += [vf + ";" + af, "-map", "[v]", "-map", "[aud]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out]
    r = sh(cmd)
    if r.returncode: print("render2 failed:", r.stderr[-700:]); return False
    return True
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--slug", required=True); ap.add_argument("--vod", default="auto"); ap.add_argument("--from-min", type=float, default=0); ap.add_argument("--to-min", type=float, default=60); ap.add_argument("--n", type=int, default=3); ap.add_argument("--out", default=None); ap.add_argument("--platform", default="kick"); ap.add_argument("--credit", default=""); a = ap.parse_args()
    out = a.out or f"state/{a.slug}/shorts"; os.makedirs(out, exist_ok=True)
    if a.platform == "twitch":
        tv = twitch_pick(a.slug, a.vod); vid = str(tv["id"]); v = {"id": vid, "session_title": tv["title"], "duration": tv["dur_s"] * 1000}; AUDIO_SRC, VIDEO_SRC = twitch_urls(vid)
    else:
        v = pick_vod(a.slug, a.vod); base = v["source"].rsplit("/master.m3u8", 1)[0]; vid = str(v["id"]); AUDIO_SRC, VIDEO_SRC = f"{base}/480p30/playlist.m3u8", f"{base}/1080p60/playlist.m3u8"
    CREDIT_NAME = a.credit or a.slug
    print("VOD", vid, v.get("session_title"), round((v.get("duration") or 0) / 60000), "min"); t0 = a.from_min * 60; dur = (a.to_min - a.from_min) * 60
    tmp = tempfile.mkdtemp(); words = []; en = []
    # 1. audio in 10-minute chunks -> words (absolute VOD seconds) + energy per second
    for c0 in np.arange(0, dur, 600):
        d = min(600, dur - c0); mp3 = f"{tmp}/a{int(c0)}.mp3"
        r = sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{t0 + c0:.1f}", "-t", f"{d:.1f}", "-i", AUDIO_SRC, "-vn", "-ac", "1", "-ar", "16000", "-c:a", "libmp3lame", "-b:a", "48k", mp3])
        if r.returncode: print("audio chunk failed", r.stderr[-200:]); continue
        for w in whisper(mp3): words.append({"word": w["word"], "start": t0 + c0 + w["start"], "end": t0 + c0 + w["end"]})
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", mp3, "-f", "s16le", "-ac", "1", "-ar", "8000", "-"], capture_output=True).stdout; x = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
        n = len(x) // 8000; en += list(np.sqrt((x[:n * 8000].reshape(n, 8000) ** 2).mean(1)) + 1e-3)
        print(f"chunk {int(c0 / 60)}-{int((c0 + d) / 60)} min: {len(words)} words total"); time.sleep(2)
    N = int(dur); e = np.zeros(N); e[:min(N, len(en))] = np.array(en[:N]); wps = np.zeros(N)
    for w in words:
        i = int(w["start"] - t0)
        if 0 <= i < N: wps[i] += 1
    def rz(s):
        k = 600; z = np.zeros(len(s))
        for i in range(0, len(s), 60):
            seg = s[max(0, i - k):i + k]; med = np.median(seg); mad = np.median(np.abs(seg - med)) + 1e-6; z[i:i + 60] = (s[i:i + 60] - med) / (1.4826 * mad)
        return np.clip(z, -3, 6)
    sm = lambda z: np.convolve(z, np.ones(5) / 5, mode="same")
    S = sm(0.6 * rz(np.log(e + 1e-3)) + 0.4 * rz(wps)); order = np.argsort(-S); peaks = []
    for i in order:
        if S[i] < 0.9: break
        if all(abs(i - p) >= 60 for p in peaks): peaks.append(int(i))
        if len(peaks) >= a.n * 4: break
    print("S max/p99:", round(float(S.max()), 2), round(float(np.percentile(S, 99)), 2), "n", len(S))
    print("peaks:", [(int(p + t0) // 60, round(float(S[p]), 1)) for p in peaks])
    # 2. LLM scoring of every peak window
    cands = []
    for p in peaks:
        pk = t0 + p; ws = [w for w in words if pk - 45 <= w["start"] <= pk + 20]
        if len(ws) < 15: continue
        txt = " ".join(f"[{w['start']:.0f}]{w['word'].strip()}" for w in ws)[:5500]
        j = llm("You edit YouTube Shorts from a live stream of a big streamer. Below: words with [second] for the window around an audio/speech peak at second %d. Decide if it is a clip-worthy moment (funny, shocking, dramatic, a story with a punchline). REJECT (reject=true) gambling/casino/giveaway/promo-code talk, unreleased or leaked game footage, close-up graphic violence, sponsored reads, slurs, sexual content, self-harm, minors, or random chatter. Return JSON only: {\"score\":1-10,\"start\":second where the SETUP sentence starts (8-25 s before the peak, a sentence start),\"end\":second where the PAYOFF/reaction sentence ends (+0.4 s allowed),\"title\":\"English YouTube Shorts title 40-70 chars, hook first, put the streamer's display name in it when natural (e.g. Kai Cenat / N3on), quote the funniest line only if it is clean, ends with ! or ?\",\"hook\":\"3-6 word on-screen text\",\"reject\":false,\"why\":\"\"}\n\n%s" % (pk, txt))
        if j and not j.get("reject") and float(j.get("score", 0)) >= 6: cands.append((float(j["score"]) + float(S[p]) / 3, pk, j))
    cands.sort(reverse=True); made = []
    # 3. cut + 9:16 render
    import shorts as SH
    for sc, pk, j in cands:
        if len(made) >= a.n: break
        try: s = float(j["start"]); e_ = float(j["end"])
        except Exception: continue
        s = max(s, pk - 25); e_ = min(max(e_, pk + 3), s + 58)
        s0 = max([w["start"] for w in words if w["start"] <= s], default=s) - 0.2; e0 = min([w["end"] for w in words if w["end"] >= e_], default=e_) + 0.45
        if e0 - s0 < 20:   # the model often picks only the punchline (15-19 s): give it lead-in context (60%) and a short tail (40%) up to ~24 s, snapped to word starts
            need = 24 - (e0 - s0); s0 = max([w["start"] for w in words if w["start"] <= s0 - need * 0.6], default=s0) - 0.2; e0 = min([w["end"] for w in words if w["end"] >= e0 + need * 0.4], default=e0) + 0.45
        if not (20 <= e0 - s0 <= 59) or any(s0 < y and x < e0 for x, y in [(m[2], m[3]) for m in made]): print("rejected", round(s0), round(e0), j.get("title")); continue
        body = f"{tmp}/b{int(s0)}.mp4"; pad = 2.0; body_t0 = s0 - pad
        r = sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{s0 - pad:.2f}", "-t", f"{e0 - s0 + 2 * pad:.2f}", "-i", VIDEO_SRC, "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "aac", "-b:a", "192k", body])
        if r.returncode: print("cut failed", r.stderr[-300:]); continue
        # PRECISION (research 17 Nov): refine the in/out points with the real audio energy of the cut body (Whisper word times are only good to ~100-300 ms and often early)
        try:
            import cutsnap as CS
            env, hop = CS.energy_db(body); t0b = s0 - pad
            wi = [w for w in words if s0 - 0.05 <= w["start"] <= e0 + 0.05]
            if wi:
                s1 = CS.snap_start(wi[0]["start"], words, env, hop, t0b); e1 = CS.snap_end(min(wi[-1]["end"], wi[-1]["start"] + 1.4), words, env, hop, t0b); chk = CS.check_boundaries(s1, e1, env, hop, t0b)
                print(f"snap: start {s0:.2f}->{s1:.2f}  end {e0:.2f}->{e1:.2f}  boundary check {chk}")
                if not chk["ok"]:   # boundary still on loud audio (game sound/music): look for a quieter frame up to 0.8 s away and keep it only if it is really better
                    fl_ = CS._floor(env); e2 = CS._quiet(env, hop, t0b, e1, fl_, 0.8); s2 = CS._quiet(env, hop, t0b, s1, fl_, 0.4); chk2 = CS.check_boundaries(s2, e2, env, hop, t0b)
                    if chk2["end_db_over_floor"] + chk2["start_db_over_floor"] < chk["end_db_over_floor"] + chk["start_db_over_floor"]: s1, e1, chk = s2, e2, chk2; print("snap: moved to quieter boundaries", chk)
                if 18 <= e1 - s1 <= 60: s0, e0 = s1, e1
        except Exception as e_: print("cutsnap failed (keeping word-based points):", e_)
        rel = [{"word": w["word"], "start": w["start"] - body_t0, "end": w["end"] - body_t0} for w in words if body_t0 <= w["start"] <= e0 + pad]
        ass = f"{out}/short_{vid}_{int(s0)}.ass"; mp4 = f"{out}/short_{vid}_{int(s0)}.mp4"; SH.make_ass(rel, s0 - body_t0, e0 - body_t0, ass)
        txt = open(ass, encoding="utf-8").read().replace("&H0028E678", "&H0007C1FF").replace("Heebo Black", "Heebo Black"); open(ass, "w", encoding="utf-8").write(txt)
        if not (render2(body, s0 - body_t0, e0 - body_t0, ass, mp4, j.get("hook", ""), pk - body_t0) or SH.render(body, s0 - body_t0, e0 - body_t0, ass, mp4)): continue
        PROF = re.compile(r"fuck|shit|bitch|nigg|fag|retard|cunt|dick|pussy|whore|slut", re.I)   # research: profanity in a title earns no ad revenue; drop the quoted part instead of publishing it
        if PROF.search(j["title"]):
            t2 = re.sub(r"\s*[-–:]?\s*[\"“”'‘’][^\"“”'‘’]*[\"“”'‘’]\s*", " ", j["title"]).strip(" -–:")
            t2 = t2 if t2 and t2[-1] in "!?" else t2 + "!"
            if len(t2) < 18 or PROF.search(t2): print("title has profanity, skipped:", j["title"]); made_skip = True; continue
            j["title"] = t2
        meta = {"title": j["title"][:90] + " #Shorts", "hook": j.get("hook", ""), "source": {"slug": a.slug, "platform": a.platform, "vod": vid, "start_s": round(s0), "end_s": round(e0), "vod_title": v.get("session_title")}, "score": round(sc, 1), "why": j.get("why", ""),
                "description": f"{j['title']}\n\nClip from {CREDIT_NAME}'s live stream on " + ("Twitch (https://twitch.tv/" if a.platform == "twitch" else "Kick (https://kick.com/") + f"{a.slug}). Unofficial fan channel, not affiliated.\n#Shorts #{a.slug.replace('-', '')}"}
        json.dump(meta, open(mp4.replace(".mp4", ".json"), "w"), ensure_ascii=False, indent=1); made.append((mp4, meta, s0, e0)); print(f"SHORT {len(made)}: {int(s0 // 60)}:{int(s0 % 60):02d}-{int(e0 // 60)}:{int(e0 % 60):02d} ({e0 - s0:.0f}s) score {sc:.1f} | {j['title']}")
    if not made: sys.exit("no short produced")
if __name__ == "__main__": main()

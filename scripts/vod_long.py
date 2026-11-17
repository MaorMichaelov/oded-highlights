#!/usr/bin/env python3
"""LONG English video from a window of a Kick/Twitch VOD (WORLD CLIPS / ClipGlobe): one complete session or reaction, kept continuous (owner rule: great sessions stay whole), 1080p60, precise start/end.
usage: vod_long.py --slug n3on --platform kick --vod ID --from-min 70 --to-min 100 --credit N3on [--out state/n3on/long]
Steps: Groq whisper (English, word times) over the window -> LLM writes title / description / chapters from the real transcript (Gemini first, Groq fallback) -> start/end snapped into pauses with cutsnap
-> re-encode the window (libx264 veryfast crf 19, source frame rate/size, AAC 192k, -movflags +faststart) -> <out>/long_<vod>_<start>.mp4 + .json (private draft meta). Upload separately with scripts/upload_shorts.py (it uploads every mp4+json pair)."""
import argparse, json, os, re, subprocess, sys, tempfile, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import vod_shorts as V, cutsnap as CS, cutqa as Q
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--slug", required=True); ap.add_argument("--platform", default="kick"); ap.add_argument("--vod", default="auto"); ap.add_argument("--from-min", type=float, required=True); ap.add_argument("--to-min", type=float, required=True); ap.add_argument("--credit", default=""); ap.add_argument("--out", default=None); ap.add_argument("--title-hint", default=""); ap.add_argument("--style", default=None, help="editing style name (config/styles/<name>.json) or path; default env STYLE; none = classic"); a = ap.parse_args()
    if a.style: os.environ["STYLE"] = a.style
    import styles as _S; ST = V.style_active("long"); STN = _S.name_of(os.environ["STYLE"]) if ST else None; PC = ST or _S.resolve(None, "long"); LANG, LANGN = PC["language"]["code"], PC["language"]["name"]   # PC = parameters in force (classic defaults = the old behaviour)
    if ST == _S.resolve(None, "long"): ST = None   # a style equal to the classic defaults (signature) runs the classic code path unchanged
    if STN: print("STYLE", STN, "| captions", PC["captions"]["enabled"], "| dead-air cut", PC["pace"]["dead_air_trim_s"], "| loudness", PC["loudness"]["enabled"], "| bumper", PC["intro"]["bumper_s"], flush=True)
    out = a.out or f"state/{a.slug}/long"; os.makedirs(out, exist_ok=True); credit = a.credit or a.slug
    if a.platform == "twitch":
        tv = V.twitch_pick(a.slug, a.vod); vid = str(tv["id"]); AUDIO, VIDEO = V.twitch_urls(vid); vtitle = tv["title"]
    else:
        v = V.pick_vod(a.slug, a.vod); base = v["source"].rsplit("/master.m3u8", 1)[0]; vid = str(v["id"]); AUDIO, VIDEO = f"{base}/480p30/playlist.m3u8", f"{base}/1080p60/playlist.m3u8"; vtitle = v.get("session_title") or ""
    t0 = a.from_min * 60; dur = (a.to_min - a.from_min) * 60; tmp = tempfile.mkdtemp(); words = []; envs = []; pre_chunk = None
    PRE = min(12.0, t0)   # 17 Nov quality pass: 12 s of context before the window, so the first sentence of the window can be recognised as complete or cut (words/energy only used at the start edge)
    if PRE >= 4:
        try:
            mp3p = f"{tmp}/pre.mp3"; rp = V.sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{t0 - PRE:.1f}", "-t", f"{PRE:.1f}", "-i", AUDIO, "-vn", "-ac", "1", "-ar", "16000", "-c:a", "libmp3lame", "-b:a", "48k", mp3p])
            if not rp.returncode:
                pre_chunk = (t0 - PRE, mp3p); pw = V.whisper(mp3p, LANG); words += [{"word": w["word"], "start": t0 - PRE + w["start"], "end": t0 - PRE + w["end"]} for w in pw]
        except Exception as e_: print("pre-roll context skipped:", str(e_)[:100])
    for c0 in np.arange(0, dur, 600):
        d = min(600, dur - c0); mp3 = f"{tmp}/a{int(c0)}.mp3"
        r = V.sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{t0 + c0:.1f}", "-t", f"{d:.1f}", "-i", AUDIO, "-vn", "-ac", "1", "-ar", "16000", "-c:a", "libmp3lame", "-b:a", "48k", mp3])
        if r.returncode: print("audio chunk failed", r.stderr[-200:]); continue
        cw = []
        for _try in range(3):   # a failed chunk silently cut a 30 min window to 20 min (16 Nov bug): retry, and say so loudly if it still fails
            cw = V.whisper(mp3, LANG)
            if cw: break
            print("whisper returned nothing for chunk", int(c0 / 60), "- retrying", flush=True); time.sleep(8)
        if not cw: print("WARNING: chunk", int(c0 / 60), "has no transcript", flush=True)
        for w in cw: words.append({"word": w["word"], "start": t0 + c0 + w["start"], "end": t0 + c0 + w["end"]})
        envs.append((t0 + c0, mp3)); print(f"chunk {int(c0 / 60)}-{int((c0 + d) / 60)} min: {len(words)} words", flush=True); time.sleep(2)
    if len(words) < 200: sys.exit("too little speech in the window")
    allwords = list(words)   # incl. the pre-roll context; `words` is cut down to the refined window below
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
    # edges (17 Nov quality pass): start on the first complete sentence of the topic, end after its last sentence, then snap into the pause with the real audio energy of the chunk that holds the point
    _envc = {}
    def env_for(t):
        for c_, p_ in ([pre_chunk] if pre_chunk else []) + envs:
            if p_ not in _envc: _envc[p_] = CS.energy_db(p_)
            e_, h_ = _envc[p_]
            if c_ - 0.01 <= t < c_ + len(e_) * h_ - 0.3 or p_ == (envs[-1][1] if envs else None): return e_, h_, c_
        raise RuntimeError("no audio chunk for %.1f" % t)
    allw = sorted(allwords, key=lambda w: w["start"]); s_win, e_win = t0, t0 + dur
    s0 = max(t0, min(w["start"] for w in words)); e0 = max(w["end"] for w in words); s1, e1 = s0 - 0.2, min(t0 + dur, e0 + 0.4)
    try:
        st = CS.sentence_start_near(s_win, allw, back=1.5, fwd=12.0); st = st if st is not None else [w for w in words if w["start"] >= t0][0]["start"]
        env, hop, c_ = env_for(st); s1 = CS.snap_start(st, allw, env, hop, c_)
        open_end = not any(w["end"] > e_win + 1.0 for w in allw)   # the transcript stops at the window end: the last sentence there may be unfinished, back up to the previous complete one
        en = CS.sentence_end_near(e_win, allw, back=1.0, fwd=6.0, last=not open_end, before_win=14.0)
        if en is None: last_end = min(max(w["end"] for w in words), e_win - 0.3); en = min(last_end, [w for w in words if w["end"] <= last_end][-1]["start"] + 1.4)
        env2, hop2, c2 = env_for(en); e1 = CS.snap_end(en, allw, env2, hop2, c2)
        print(f"edge snap: start {t0:.2f}->{s1:.2f} (sentence start {st:.2f})  end {t0 + dur:.2f}->{e1:.2f} (sentence end {en:.2f}{', window end was open' if open_end else ''})")
    except Exception as e: print("edge snap failed, keeping the window edges:", e)
    s1 = max(s1, t0 - 1.7); e1 = max(e1, s1 + 60)
    if os.environ.get("ALLOW_DUP") != "1":   # 17 Nov: never render the same stretch of a VOD twice (set ALLOW_DUP=1 for a deliberate re-render)
        du = [x for x in Q.existing_ranges(a.slug, vid, kinds=("long",)) if Q.overlap(s1, e1, x["start"], x["end"]) >= 0.5]
        if du: print(f"DUPLICATE: {s1:.0f}-{e1:.0f} overlaps the existing long video {du[0]['id']} ({du[0]['start']:.0f}-{du[0]['end']:.0f}); not rendering (ALLOW_DUP=1 overrides)"); sys.exit(0)
    # LLM metadata from the real transcript (evenly sampled lines with [seconds from the clip start])
    lines = []; cur = []; ts = None; line_t = []   # line_t[i] = absolute start second of line i: chapters are chosen by LINE NUMBER, never by seconds written by the LLM (17 Nov: LLM seconds put 8 chapters into the first 5 min of a 12 min video, 7 of them describing other moments)
    for w in words:
        if w["start"] < s1 - 0.3 or w["start"] > e1 + 0.3: continue
        if ts is None: ts = w["start"]
        cur.append(w["word"].strip())
        if w["end"] - ts >= 20: lines.append(f"L{len(lines)} [{int(ts - s1)}s] " + " ".join(cur)[:170]); line_t.append(ts); cur, ts = [], None   # 170 chars per 20 s line, spread over the WHOLE window (a 9000-char cut used to show only the first 6 minutes of a 20 min clip: wrong chapters)
    step = max(1, len(lines) // 90); sample = "\n".join(lines[::step])[:16000]
    L = (lambda t: t) if LANGN == "English" else (lambda t: t.replace("English", LANGN))
    prompt = (f"You write the YouTube metadata of a LONG highlight video cut from {credit}'s live stream (platform: {a.platform}); the clip is one continuous session of {int((e1 - s1) / 60)} minutes. The transcript is automatic and may contain errors; never invent facts, people or quotes. Stream title: '{vtitle}'. {a.title_hint}\n"
              "Return JSON only: {\"title\":\"English, 50-85 chars, literal and specific (only what really happens, NEVER invent facts, reveals, surprises or hype words), name the streamer, put the streamer's name in it, what really happens, no profanity, no ALL CAPS shouting, ends without a period\",\"description\":\"3 English sentences with specifics (who, what, key moments)\",\"hashtags\":[\"#" + a.slug.replace('-', '') + "\", ...4 more],\"tags\":[...8 keywords],"
              "\"chapters\":[{\"line\":n,\"title\":\"<=6 specific words\"}] (8-14 entries IN ORDER, the first one is line 0, spread over the whole clip; \"line\" = the number n of the transcript line L<n> where that topic BEGINS, copied from the transcript, never a time),\"reject\":false,\"why\":\"\"}. Set reject=true (and explain in why) if the clip is mostly gambling/casino/promo talk, hate speech, sexual content, or empty chatter.\n\nTranscript (lines are L<number> [seconds from the clip start] text):\n" + sample)
    HYPE = re.compile(r"epic|wild|shock|insane|crazy|you won't believe|unbelievable|mind-?blow|exposed|leaked|teaser|reveal|surprise", re.I)   # titles/descriptions must state only what really happens
    prompt = L(prompt); j = V.llm(prompt)
    if j and not j.get("reject") and HYPE.search(j.get("title", "")): j = V.llm(prompt + "\n\nYour previous title used hype words or invented details. Be strictly literal: only what is really said in the transcript, plain words, no 'epic', 'reveal', 'surprise', 'shocking'. Do not mention anything that is not in the transcript lines.")
    if j and HYPE.search(j.get("title", "")): j["title"] = HYPE.sub("", j["title"]).replace("  ", " ").strip(" -:,")
    if not j or j.get("reject"): sys.exit("metadata step rejected the window: " + str((j or {}).get("why")))
    _cw = [w for w in words if s1 - 0.3 <= w["start"] <= e1 + 0.3]   # the words that are really in the video
    j["title"], _tt, _tok = V.truthful_title(j["title"], _cw, [credit, a.slug], vtitle or "", f"{LANGN}, 50-85 chars, literal and specific, names the streamer, no period at the end", vtitle or "", credit)   # titles must be true: names / numbers / quotes have to occur in the transcript
    # cut + encode
    dd = e1 - s1; mp4 = f"{out}/long_{vid}_{int(s1)}.mp4"
    import brand
    main_mp4 = mp4[:-4] + "_main.mp4"   # the clip with the owner's logo as a corner watermark; the logo bumper is prepended below
    cuts = []
    if ST:   # editing style: optional dead-air cuts (real silences of the 480p audio chunks), burned subtitles, loudness, music, watermark from the style
        import style_render as SR
        ass = mp4[:-4] + ".ass"
        if float(PC["pace"]["dead_air_trim_s"]) > 0:
            for c0_, mp3_ in envs:
                lo_, hi_ = max(s1, c0_), min(s1 + dd, c0_ + 600)
                if hi_ - lo_ > 5: cuts += [(a_ + lo_ - s1, b_ + lo_ - s1) for a_, b_ in SR.dead_air_cuts(mp3_, lo_, hi_, words, PC["pace"], offset=c0_)]
            cuts.sort(); print(f"style: {len(cuts)} dead-air cuts, {sum(b_ - a_ for a_, b_ in cuts) / 60:.1f} min removed")
        if PC["captions"]["enabled"]: _S.make_ass(words, s1, s1 + dd, ass, PC["captions"], 1920, 1080, _S.make_remap(cuts) if cuts else None)
        cmd_ = SR.long_encode_cmd(PC, VIDEO, s1, dd, ass if PC["captions"]["enabled"] else None, cuts, brand.LOGO, main_mp4)
    else: cmd_ = None
    r = V.sh(cmd_) if cmd_ else V.sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{s1:.3f}", "-t", f"{dd:.3f}", "-i", VIDEO, "-loop", "1", "-i", brand.LOGO, "-filter_complex", "[1:v]format=rgba,scale=120:-1,colorchannelmixer=aa=0.85[wm];[0:v][wm]overlay=W-w-32:H-h-32:shortest=1,format=yuv420p[v]",
              "-map", "[v]", "-map", "0:a:0", "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", "-af", "afade=t=in:d=0.02,afade=t=out:st=%.3f:d=0.05" % (dd - 0.05), "-t", f"{dd:.3f}", "-movflags", "+faststart", main_mp4])
    if r.returncode: sys.exit("encode failed: " + r.stderr[-400:])
    pr = V.sh(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate", "-of", "csv=p=0", main_mp4]).stdout.strip().split(",")
    bw, bh = int(pr[0]), int(pr[1]); fn, fd = pr[2].split("/"); bfps = round(float(fn) / float(fd), 3); BUMP = float(PC["intro"]["bumper_s"])   # 2.5 s classic
    if BUMP > 0:
        bump = mp4[:-4] + "_bump.mp4"; brand.make_bumper(bump, bw, bh, bfps, BUMP)
        open(mp4[:-4] + "_list.txt", "w").write(f"file '{os.path.abspath(bump)}'\nfile '{os.path.abspath(main_mp4)}'\n")
        r = V.sh(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", mp4[:-4] + "_list.txt", "-c", "copy", "-movflags", "+faststart", mp4])
        if r.returncode: sys.exit("join failed: " + r.stderr[-400:])
        for f_ in (main_mp4, bump, mp4[:-4] + "_list.txt"): os.remove(f_)
    else: os.replace(main_mp4, mp4)
    dd -= sum(b_ - a_ for a_, b_ in cuts); remap_ = _S.make_remap(cuts) if cuts else (lambda t_: t_)   # style dead-air cuts shorten the video; chapter seconds are re-timed below
    def _rc(x_): x_ = float(x_); r_ = remap_(x_); return r_ if r_ is not None else (remap_(max(0.0, x_ - 3)) or 0)   # a chapter that fell into a cut pause moves to the cut
    dd += BUMP   # the published video is longer than the cut window by the bumper
    def _chapters(raw):
        """LLM chapters (by line number) -> [{"second": from the clip start, "title"}]: the time is the real start of that transcript line moved to the nearest sentence start, a chapter whose title has no support in the transcript right there is dropped, minimum spacing 25 s"""
        out_ = []; last_ = -1e9
        for c in (raw or []):
            t_ = str(c.get("title", "")).strip()
            if not t_: continue
            try: ta = line_t[int(c["line"])] if c.get("line") is not None else s1 + float(c["second"])
            except Exception: continue
            ta2 = CS.sentence_start_near(ta, allw, back=1.0, fwd=9.0); ta = ta2 if ta2 is not None else ta; sec_ = max(0.0, ta - s1)
            toks = [Q._stem(x) for x in Q.tokens(t_) if x not in Q.EN_STOP and x not in Q.GENERIC and len(x) > 2]; sup = {Q._stem(x) for x in Q.tokens(Q.words_text(allw, ta - 8, ta + 75))}
            if toks and sum(1 for x in toks if x in sup) / len(toks) < 0.34 and len(sup) > 20 and LANGN == "English": print("chapter dropped (no support in the transcript at that time):", int(sec_), t_); continue
            if sec_ - last_ < 25 and out_: continue
            out_.append({"second": round(sec_, 2), "title": t_}); last_ = sec_
        return out_
    j["chapters"] = _chapters(j.get("chapters"))
    def mmss(sec): sec = int(max(0, sec)); return f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}" if sec >= 3600 else f"{sec // 60:02d}:{sec % 60:02d}"
    ch = sorted({int(_rc(c["second"]) + 0.5): str(c["title"]).strip()[:50] for c in (j.get("chapters") or []) if str(c.get("title", "")).strip()}.items()); ch = [(t, n) for t, n in ch if 0 <= t < dd - 20]
    if ch: ch[0] = (0, ch[0][1])
    chap = "\n".join(f"{mmss(t + (BUMP if t > 0 else 0))} {n}" for t, n in ch) if len(ch) >= 3 else ""
    hs = list(dict.fromkeys([h for h in (j.get("hashtags") or []) if isinstance(h, str) and h.startswith("#")][:6] + ["#" + a.slug.replace("-", ""), "#" + ("Twitch" if a.platform == "twitch" else "Kick"), "#ClipGlobe"]))
    src_line = ("Twitch (https://twitch.tv/" if a.platform == "twitch" else "Kick (https://kick.com/") + f"{a.slug})"
    desc = f"Clips from {credit}'s live streams on {src_line} | Unofficial fan channel, not affiliated.\n{j.get('description', '').strip()}\n" + (f"\nChapters:\n{chap}\n" if chap else "") + f"\nClip from the live stream: {src_line}\nThis is an unofficial fan channel: all clips are taken from {credit}'s streams. It is not {credit}'s official channel.\n\n" + " ".join(hs)
    meta = {"title": j["title"].strip()[:98], "description": desc, "tags": (j.get("tags") or [])[:12] + [credit, "highlights"], "privacy": "private", "score": 100, "source": {"slug": a.slug, "platform": a.platform, "vod": vid, "start_s": round(s1), "end_s": round(e1), "start_exact": round(s1, 2), "end_exact": round(e1, 2), "bumper_s": BUMP, "vod_title": vtitle, "minutes": round(dd / 60, 1)}}
    try:   # automatic grade of the finished draft (17 Nov): sync, dead air / abrupt end at both ends, loudness, word cut, title truth; a failing draft gets qa_fail=true and upload_shorts.py skips it
        if not cuts: Q.save_words(mp4[:-4] + ".words.json", _cw, s1)
        g = Q.grade(mp4, "long", title=meta["title"], words=None if cuts else [{"word": w["word"], "start": w["start"] - s1 + BUMP, "end": w["end"] - s1 + BUMP} for w in _cw], window_text_=Q.words_text(_cw), skip_head=BUMP, ignore_names=[credit, a.slug], extra_text=vtitle or "", expected_dur=dd)
        meta["qa"] = {"score": g["score"], "fail": g["fail"], "warn": g["warn"]}
        if not _tok: meta["qa"]["fail"].append("title not supported by the transcript (rewrite failed)")
        if meta["qa"]["fail"]: meta["qa_fail"] = True
        print("QA", meta["qa"], flush=True)
    except Exception as e_: print("qa grade failed (draft kept as is):", str(e_)[:150])
    json.dump(meta, open(mp4[:-4] + ".json", "w"), ensure_ascii=False, indent=1)
    if os.environ.get("THUMB_PRO") == "1":   # opt-in only: the owner does not want auto-designed thumbnails
      try:   # pro thumbnail from a real face frame (thumb_pro.py): 2-4 literal words
          tj = V.llm(f"Give a 2 to 4 word YouTube thumbnail hook for a video titled '{meta['title']}'. Literal and true to the title, no hype words, no profanity, no clickbait claims. Return JSON {{\"text\": \"...\"}}")
          tt = (tj or {}).get("text") or " ".join(meta["title"].split()[:3])
          if HYPE.search(tt): tt = " ".join(meta["title"].split()[:3])
          r_ = subprocess.run([sys.executable, os.path.join(HERE, "thumb_pro.py"), mp4, mp4[:-4] + ".jpg", "--text", tt, "--hint", meta["title"]], capture_output=True, text=True); print("thumb:", (r_.stdout + r_.stderr)[-200:].strip())
      except Exception as e: print("thumbnail skipped:", str(e)[:120])
    print(f"LONG READY {mp4} ({dd / 60:.1f} min, {os.path.getsize(mp4) // 1_000_000} MB) | {meta['title']}")
if __name__ == "__main__": main()

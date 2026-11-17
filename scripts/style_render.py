#!/usr/bin/env python3
"""Renders with an editing style (see scripts/styles.py). Used by scripts/vod_shorts.py (render2) and scripts/vod_long.py ONLY when a style is selected (env STYLE / --style).
With the built-in defaults every function here produces the same ffmpeg command as the pre-style code (checked by scripts/test_styles.py), so a style that only restates defaults changes nothing.
Public: shorts_captions(st, words, s, e, ass, hook, cuts)  render_shorts(body, s, e, ass, out, hook, peak, st)  dead_air_cuts(media, s, e, words, pace)  long_parts(st, ...)  hook_text(hook, hk, lang)"""
import json, os, re, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "stations"))
import styles as ST
SIZES = {"9:16": (1080, 1920), "1:1": (1080, 1080), "4:5": (1080, 1350), "16:9": (1920, 1080)}
NON_LATIN = {"he", "ar", "fa", "ru", "uk", "el", "hi", "th", "ja", "ko", "zh", "bg", "sr"}
def sh(c, **k): return subprocess.run(c, capture_output=True, text=True, **k)
def _n(x): return ("%g" % x)
def fonts_dirs():
    import shorts as SH
    return SH.FONTS
def fontsdir_for(st):
    """libass font directory: the classic one when the style only uses Heebo, else a temp dir with symlinks to the classic fonts + assets/fonts (so Anton / Bangers / Bebas Neue / Montserrat resolve by family name)"""
    base = fonts_dirs(); fonts = {st["captions"]["font"]} if st.get("captions") else set()
    if all(f.lower().startswith("heebo") for f in fonts) and base: return base[0]
    d = tempfile.mkdtemp(prefix="stfonts")
    for src in list(base) + [os.path.join(ROOT, "assets", "fonts")]:
        if os.path.isdir(src):
            for f in os.listdir(src):
                if f.lower().endswith((".ttf", ".otf")) and not os.path.exists(os.path.join(d, f)):
                    try: os.symlink(os.path.join(src, f), os.path.join(d, f))
                    except OSError: pass
    return d
def hook_font(hk):
    f = hk.get("font", "auto")
    if f and f != "auto":
        p = f if os.path.isabs(f) else os.path.join(ROOT, "assets", "fonts", f)
        if os.path.exists(p): return p
    fonts = [os.path.join(d, x) for d in fonts_dirs() for x in (os.listdir(d) if os.path.isdir(d) else []) if x.lower().endswith(".ttf") and ("black" in x.lower() or "bold" in x.lower())]
    return fonts[0] if fonts else "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
def hook_text(hook, hk, lang="en"):
    """sanitised hook with '|' where the line breaks (same rules as the classic render2: Latin letters only unless the language is non-Latin)"""
    keep = r"[^\w !?']" if lang in NON_LATIN else r"[^A-Za-z0-9 !?']"
    safe = re.sub(keep, "", hook or ""); safe = (safe.upper() if hk.get("uppercase", True) else safe).replace("'", "")[:int(hk["max_chars"])]
    if len(safe) > int(hk["wrap_chars"]):
        w_ = safe.split(); a_, b_ = [], []
        for x_ in w_: (a_ if len(" ".join(a_ + [x_])) <= max(12, len(safe) // 2 + 2) else b_).append(x_)
        safe = " ".join(a_) + "|" + " ".join(b_) if b_ else " ".join(a_)
    return safe
# ---- dead-air cuts ------------------------------------------------------------------------------------------------------------------------------------------------------
def dead_air_cuts(media, s, e, words, pace, offset=0.0):
    """silences >= pace.dead_air_trim_s inside [s, e] of `media` (seconds in the media's own timeline) -> [(a, b)] relative to s that can be removed.
    Each cut leaves pace.keep_pause_s of the pause, never overlaps a transcribed word, never touches the first/last 0.4 s. words are in the same timeline as `media`; `offset` is added to silence times (for an audio chunk that starts at `offset`)."""
    thr = float(pace.get("dead_air_trim_s") or 0)
    if thr <= 0: return []
    r = sh(["ffmpeg", "-nostats", "-hide_banner", "-v", "info", "-ss", f"{s - offset:.3f}", "-t", f"{e - s:.3f}", "-i", media, "-vn", "-af", f"silencedetect=n={_n(pace['silence_db'])}dB:d={thr}", "-f", "null", "-"]).stderr
    st = [float(v) for v in re.findall(r"silence_start: (-?[\d.]+)", r)]; en = [float(v) for v in re.findall(r"silence_end: ([\d.]+)", r)]
    keep = float(pace["keep_pause_s"]); out = []
    for i, a in enumerate(st):
        b = en[i] if i < len(en) else (e - s)
        a = max(a, 0.0); ca, cb = a + keep / 2, b - keep / 2
        if cb - ca < 0.2 or ca < 0.4 or cb > (e - s) - 0.4: continue
        if any(w["end"] - s > ca and w["start"] - s < cb for w in words): continue   # a word lives inside: not silence
        out.append((round(ca, 3), round(cb, 3)))
    return out
def _sel(cuts): return "not(" + "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in cuts) + ")"
# ---- Shorts ------------------------------------------------------------------------------------------------------------------------------------------------------
def shorts_captions(st, words, s, e, ass, hook, cuts=()):
    """writes the ASS (captions + hook for non-Latin languages) and a sidecar <ass>.json with the caption group times and the cuts (read by render_shorts). Returns the groups."""
    W, H = SIZES[st["layout"]["aspect"]]; lang = st["language"]["code"]; remap = ST.make_remap(cuts) if cuts else None
    hk = st["hook"]; ht = hook_text(hook, hk, lang) if hk["enabled"] and hook else ""
    in_ass = bool(ht) and lang in NON_LATIN
    spans = ST.make_ass(words if st["captions"]["enabled"] else [], s, e, ass, st["captions"], W, H, remap, ht if in_ass else None, hk if in_ass else None) if st["captions"]["enabled"] or in_ass else []
    json.dump({"spans": spans, "cuts": [list(c) for c in cuts], "hook_in_ass": in_ass}, open(ass + ".json", "w"))
    return spans
def _pulse(F, S, A, D, first=False):
    if first: return f"if(between(on,{F},{F + A}),1+{_n(S)}*(on-{F})/{A},if(between(on,{F + A},{F + A + D}),{_n(round(1 + S, 4))}-{_n(S)}*(on-{F + A})/{D},1))"
    return f"if(between(on,{F},{F + A}),{_n(S)}*(on-{F})/{A},if(between(on,{F + A},{F + A + D}),{_n(S)}*(1-(on-{F + A})/{D}),0))"
def zoom_expr(zm, fps, peak_t, extra_times):
    """z expression for zoompan. One pulse at the peak = the classic expression. peak_t/extra_times are seconds in the OUTPUT timeline (after cuts)."""
    A, D, S = int(zm["attack_frames"]), int(zm["decay_frames"]), float(zm["strength"]); ps = []
    if peak_t is not None and S > 0: ps.append((int(peak_t * fps), S, A, D))
    for t in extra_times: ps.append((int(t * fps), float(zm["extra_strength"]), max(3, A - 2), D))
    if not ps: return "1"
    if len(ps) == 1: return _pulse(ps[0][0], ps[0][1], ps[0][2], ps[0][3], True)
    return "1+" + "+".join(_pulse(F, S_, A_, D_) for F, S_, A_, D_ in ps)
def extra_pulse_times(zm, spans, dur, peak_t):
    every = float(zm["extra_every_s"])
    if not zm["enabled"] or every <= 0: return []
    out = []; t = max(2.0, every * 0.6); starts = [a for a, b in spans]
    while t < dur - 1.2 and len(out) < int(zm["max_extra"]):
        c = min(starts, key=lambda x: abs(x - t)) if starts else t
        c = c if abs(c - t) <= every * 0.4 else t
        if peak_t is None or abs(c - peak_t) > 1.5:
            if not out or c - out[-1] > 1.0: out.append(round(c, 2))
        t += every
    return out
def make_bumper_fit(out, w, h, fps, dur):
    """ClipGlobe logo bumper that fits any frame (brand.make_bumper sizes the logo by height: too big in portrait). Logo only scaled/faded, as the owner requires."""
    import brand
    if w >= h: return brand.make_bumper(out, w, h, fps, dur)
    side = int(min(w, h) * 0.62) // 2 * 2
    fc = (f"[1:v]format=rgba,scale=w='trunc({side}*(0.88+0.12*min(t/0.8\\,1))/2)*2':h=-2:eval=frame,fade=t=in:st=0:d=0.5:alpha=1[lg];[0:v][lg]overlay=(W-w)/2:(H-h)/2:eval=frame:shortest=0,format=yuv420p[v];"
          f"[2:a]aformat=sample_rates=48000:channel_layouts=stereo,apad,atrim=0:{dur},volume=-4dB[a]")
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=black:s={w}x{h}:r={fps}:d={dur}", "-loop", "1", "-t", str(dur), "-i", brand.LOGO, "-i", brand.WHOOSH, "-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-t", str(dur),
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", "-r", str(fps), "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", out]
    r = sh(cmd)
    if r.returncode: raise RuntimeError("bumper failed: " + r.stderr[-300:])
    return out
def music_path(mu):
    f = mu.get("file") or ""
    for p in (f, os.path.join(ROOT, "assets", "music", f)):
        if f and os.path.isfile(p): return p
    return None
def _wm_pos(wm):
    mx, my = int(wm["margin_x"]), int(wm["margin_y"]); c = wm["corner"]
    return ("W-w-" if c in ("tr", "br") else "") + f"{mx}" + ":" + ("H-h-" if c in ("bl", "br") else "") + f"{my}"
def build_shorts_cmd(body, s, e, ass, out, hook, peak, st, side=None, env=None):
    """the full ffmpeg command. side = the sidecar written by shorts_captions (spans/cuts)."""
    env = os.environ if env is None else env; side = side or {}
    W, H = SIZES[st["layout"]["aspect"]]; lay, cap, hk, zm, sfx, mu, wm, ld, ex = (st[k] for k in ("layout", "captions", "hook", "zoom", "sfx", "music", "watermark", "loudness", "export"))
    fps = int(ex["fps"]); cuts = [tuple(c) for c in side.get("cuts", [])]; spans = [tuple(x) for x in side.get("spans", [])]; remap = ST.make_remap(cuts) if cuts else (lambda t: t)
    P = max(0.0, (peak or 0) - s); Pm = remap(P) if peak else None
    if peak and Pm is None: Pm = remap(P - 0.01) or 0.0   # peak fell into a removed pause: use the pause start
    clip_len = (e - s) - ST.total_cut(cuts)
    # video
    src = "[0:v]"; pre = ""
    if cuts: pre = f"[0:v]select='{_sel(cuts)}',setpts=N/FRAME_RATE/TB[sv];"; src = "[sv]"
    if lay["mode"] == "blur_fill":
        fg = f"scale={W}:-2" if lay["fg_fit"] == "width" else f"scale={W}:{H}:force_original_aspect_ratio=decrease"
        v0 = (f"{src}split=2[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur={int(lay['blur_radius'])}:{int(lay['blur_power'])},eq=brightness={_n(lay['bg_brightness'])}[bg];[b]{fg}[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2[v0];")
    elif lay["mode"] == "crop_fill": v0 = f"{src}scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}:(in_w-{W})*{_n(lay['crop_x'])}:0[v0];"
    else: v0 = f"{src}scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color={ST.norm_color(lay['bg_color']).replace('#', '0x')}[v0];"
    extra = extra_pulse_times(zm, spans, clip_len, Pm) if zm["enabled"] else []
    z = zoom_expr(zm, fps, Pm if (zm["enabled"] and peak) else None, extra)
    if zm["enabled"]: v1 = f"[v0]zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps={fps}[v1];"
    else: v1 = f"[v0]fps={fps}[v1];"
    vf = pre + v0 + v1; last = "[v1]"
    parts = []
    dt = ""; fd = fontsdir_for(st)
    if cap["enabled"] or side.get("hook_in_ass"):
        parts.append("subtitles=" + ass.replace(":", chr(92) + ":") + (":fontsdir=" + fd if fd else ""))
    if hk["enabled"] and hook and not side.get("hook_in_ass"):
        ff = hook_font(hk); safe = hook_text(hook, hk, st["language"]["code"]); hc = ST.norm_color(hk["color"]).replace("#", "0x"); bc = ST.norm_color(hk["border_color"]).replace("#", "0x")
        for k, ln in enumerate([x for x in safe.split("|") if x.strip()]):
            parts.append(f"drawtext=fontfile={ff}:text='{ln}':fontsize={int(hk['size'])}:fontcolor={hc}:borderw={int(hk['border_px'])}:bordercolor={bc}:x=(w-text_w)/2:y={int(hk['y']) + int(hk['line_gap']) * k}:enable='lt(t,{_n(hk['duration_s'])})'")
    # inputs
    cmd = ["ffmpeg", "-v", "error", "-y", "-ss", f"{s:.3f}"] + (["-t", f"{e - s:.3f}"] if cuts else []) + ["-i", body]; idx = 1; logo_i = sfx_i = mus_i = None
    if wm["enabled"]: cmd += ["-loop", "1", "-i", os.path.join(ROOT, "assets", "world_clips", "logo_clipglobe.png")]; logo_i = idx; idx += 1
    sfx_path = os.path.join(ROOT, "assets", "sfx", sfx["file"]); sfx_times = []
    use_sfx = (env.get("SHORTS_SFX") == "1") if sfx["mode"] == "env" else sfx["mode"] == "on"
    if use_sfx and os.path.exists(sfx_path):
        if "peak" in sfx["at"] and peak: sfx_times.append(Pm)
        if "start" in sfx["at"]: sfx_times.append(0.0)
        if "zoom" in sfx["at"]: sfx_times += list(extra)
    if sfx_times: cmd += ["-i", sfx_path]; sfx_i = idx; idx += 1
    mp = music_path(mu) if mu["enabled"] else None
    if mu["enabled"] and not mp: print("style music: file not found, no music:", mu.get("file"))
    if mp: cmd += ["-stream_loop", "-1", "-i", mp]; mus_i = idx; idx += 1
    cmd += ["-t", f"{clip_len:.3f}", "-filter_complex"]
    if parts: vf += f"{last}" + ",".join(parts) + "[vt];"; last = "[vt]"
    if logo_i is not None: vf += f"[{logo_i}:v]format=rgba,scale={int(wm['size_px'])}:-1,colorchannelmixer=aa={_n(wm['opacity'])}[wm];{last}[wm]overlay={_wm_pos(wm)}[v]"
    else: vf += f"{last}null[v]"
    # audio
    a_src = "[0:a]"; af = ""
    if cuts: af += f"[0:a]aselect='{_sel(cuts)}',asetpts=N/SR/TB[as];"; a_src = "[as]"
    lnorm = f"loudnorm=I={_n(ld['lufs'])}:TP={_n(ld['tp'])}:LRA={_n(ld['lra'])}," if ld["enabled"] else ""
    if mp:   # music bed under the speech, optionally ducked by the speech
        af += f"{a_src}asplit=2[sp][sc];[{mus_i}:a]volume={_n(mu['volume_db'])}dB,atrim=0:{clip_len:.3f}[mraw];" + (f"[mraw][sc]sidechaincompress=threshold=0.04:ratio=9:attack=15:release=350[mus];" if mu["duck"] else "[mraw]anull[mus];[sc]anullsink;")
        a_src = "[sp]"; mix_in = "[mus]"
    else: mix_in = None
    if sfx_times:
        if len(sfx_times) == 1: af += f"[{sfx_i}:a]adelay={int(sfx_times[0] * 1000)}|{int(sfx_times[0] * 1000)},volume={_n(sfx['volume_db'])}dB[sx];"; sx = ["[sx]"]
        else:
            af += f"[{sfx_i}:a]asplit={len(sfx_times)}" + "".join(f"[q{i}]" for i in range(len(sfx_times))) + ";"; sx = []
            for i, t in enumerate(sfx_times): af += f"[q{i}]adelay={int(t * 1000)}|{int(t * 1000)},volume={_n(sfx['volume_db'])}dB[x{i}];"; sx.append(f"[x{i}]")
    else: sx = []
    ins = [a_src] + sx + ([mix_in] if mix_in else [])
    if len(ins) > 1: af += "".join(ins) + f"amix=inputs={len(ins)}:normalize=0:duration=first,{lnorm}aresample=48000[aud]"
    else: af += f"{a_src}{lnorm}aresample=48000[aud]"
    cmd += [vf + ";" + af, "-map", "[v]", "-map", "[aud]", "-c:v", "libx264", "-preset", ex["preset"], "-crf", str(int(ex["crf"])), "-pix_fmt", "yuv420p", "-r", str(fps), "-c:a", "aac", "-b:a", f"{int(ex['audio_kbps'])}k"] + (["-ac", "2"] if st["intro"]["bumper_s"] > 0 else []) + ["-movflags", "+faststart", out]
    return cmd
def render_shorts(body, s, e, ass, out, hook, peak, st):
    side = {}
    try: side = json.load(open(ass + ".json"))
    except Exception: pass
    cmd = build_shorts_cmd(body, s, e, ass, out, hook, peak, st, side)
    r = sh(cmd)
    if r.returncode: print("render2 (style) failed:", r.stderr[-700:]); return False
    if st["intro"]["bumper_s"] > 0:   # logo bumper in front (stream-copy join: both parts are libx264 yuv420p + AAC 48k stereo)
        W, H = SIZES[st["layout"]["aspect"]]; fps = int(st["export"]["fps"]); b = out[:-4] + "_bump.mp4"; tmp = out[:-4] + "_main.mp4"; lst = out[:-4] + "_list.txt"
        try:
            make_bumper_fit(b, W, H, fps, float(st["intro"]["bumper_s"])); os.replace(out, tmp)
            open(lst, "w").write(f"file '{os.path.abspath(b)}'\nfile '{os.path.abspath(tmp)}'\n")
            r = sh(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", "-movflags", "+faststart", out])
            if r.returncode: print("bumper join failed:", r.stderr[-300:]); os.replace(tmp, out)
        except Exception as ex_: print("bumper skipped:", ex_)
        finally:
            for f in (b, tmp, lst):
                if os.path.exists(f) and f != out: os.remove(f)
    return True
# ---- Long ------------------------------------------------------------------------------------------------------------------------------------------------------
def long_encode_cmd(st, video, s1, dd, ass, cuts, logo, out):
    """ffmpeg command for the main part of a long video; with the classic long defaults it equals the pre-style command in vod_long.py"""
    cap, wm, ld, mu, ex = st["captions"], st["watermark"], st["loudness"], st["music"], st["export"]; cuts = [tuple(c) for c in cuts]; clip_len = dd - ST.total_cut(cuts)
    cmd = ["ffmpeg", "-v", "error", "-y", "-ss", f"{s1:.3f}", "-t", f"{dd:.3f}", "-i", video]; idx = 1; logo_i = None
    if wm["enabled"]: cmd += ["-loop", "1", "-i", logo]; logo_i = idx; idx += 1
    mp = music_path(mu) if mu["enabled"] else None
    if mp: cmd += ["-stream_loop", "-1", "-i", mp]; mus_i = idx; idx += 1
    chain = []; src = "[0:v]"
    pre = ""
    if cuts: chain.append(f"select='{_sel(cuts)}'"); chain.append("setpts=N/FRAME_RATE/TB")   # cut first, then burn the (already re-timed) captions
    if cap["enabled"] and ass: chain.append("subtitles=" + ass.replace(":", chr(92) + ":") + ":fontsdir=" + fontsdir_for(st))
    if chain: pre = src + ",".join(chain) + "[sv];"; src = "[sv]"
    if logo_i is not None: fc = pre + f"[{logo_i}:v]format=rgba,scale={int(wm['size_px'])}:-1,colorchannelmixer=aa={_n(wm['opacity'])}[wm];{src}[wm]overlay={_wm_pos(wm)}:shortest=1,format=yuv420p[v]"
    else: fc = pre + f"{src}format=yuv420p[v]"
    fade = f"afade=t=in:d=0.02,afade=t=out:st={clip_len - 0.05:.3f}:d=0.05"; cutaf = (f"aselect='{_sel(cuts)}',asetpts=N/SR/TB," if cuts else "")
    lnorm = f"loudnorm=I={_n(ld['lufs'])}:TP={_n(ld['tp'])}:LRA={_n(ld['lra'])}," if ld["enabled"] else ""
    cmd += ["-filter_complex"]
    if mp:
        fc += f";[0:a]{cutaf}{lnorm}aresample=48000,asplit=2[sp][sc];[{mus_i}:a]volume={_n(mu['volume_db'])}dB,atrim=0:{clip_len:.3f}[mraw];" + (f"[mraw][sc]sidechaincompress=threshold=0.04:ratio=9:attack=15:release=350[mus];" if mu["duck"] else "[mraw]anull[mus];[sc]anullsink;") + f"[sp][mus]amix=inputs=2:normalize=0:duration=first,{fade}[aud]"
        cmd += [fc, "-map", "[v]", "-map", "[aud]"]; af = []
    else:
        cmd += [fc, "-map", "[v]", "-map", "0:a:0"]; af = ["-af", cutaf + lnorm + fade]
    cmd += ["-c:v", "libx264", "-preset", ex["preset"], "-crf", str(int(ex["crf"])), "-c:a", "aac", "-b:a", f"{int(ex['audio_kbps'])}k", "-ar", "48000", "-ac", "2"] + af + ["-t", f"{clip_len:.3f}", "-movflags", "+faststart", out]
    return cmd

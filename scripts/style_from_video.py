#!/usr/bin/env python3
"""OPTIONAL feature: derive an editing style JSON (same schema as config/styles/signature.json, see scripts/styles.py) from a reference video.
usage: style_from_video.py <url-or-file> [--name NAME] [--out config/styles/NAME.json] [--seconds 180] [--no-gemini] [--compare STYLE] [--format shorts|long]
1. MEASURE with ffmpeg + numpy: cuts per minute / shot lengths (scene detection), loudness (EBU R128 integrated / LRA / true peak), silence share, caption presence + colour + position + size (sampled frames,
   static overlays removed by temporal persistence), hook text in the first seconds, zoom/punch-in events (global scale motion between consecutive frames), layout (blurred fill / bars / full frame).
2. Ask Gemini (free key rotation V.gem_keys, the video itself) to describe the qualitative parts (font family, caption animation, sfx, music, intro, language, what a copy-cat must reproduce).
3. Merge both into a style (measurements win for numbers) and write it. Without a Gemini key (or with --no-gemini) the style comes from the measurements alone.
--compare STYLE: no file is written; prints measured values next to what the style promises (a consistency / regression check of our own renders).
A URL is downloaded with yt-dlp (<= 720p, first --seconds seconds); only a GitHub runner can reach YouTube/Twitch/Kick (workflow style-from-video.yml). Output lines are prefixed STYLE| for the log."""
import argparse, json, os, re, subprocess, sys, tempfile, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, HERE)
import styles as ST
def sh(c, **k): return subprocess.run(c, capture_output=True, text=True, **k)
def say(*a): print("STYLE|", *a, flush=True)
# ---- input ---------------------------------------------------------------------------------------------------------------------------------------------------------
def probe(path):
    r = sh(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate:format=duration", "-of", "json", path]); d = json.loads(r.stdout)
    st = d["streams"][0]; n, m = st["r_frame_rate"].split("/"); return {"w": int(st["width"]), "h": int(st["height"]), "fps": round(float(n) / float(m or 1), 2), "dur": float(d["format"]["duration"])}
def fetch(src, seconds, tmp):
    """local file -> itself; URL -> yt-dlp download of the first `seconds` s at <= 720p"""
    if os.path.exists(src): return src
    out = os.path.join(tmp, "ref.mp4")
    base = ["yt-dlp", "-f", "best[height<=720]/best", "--no-playlist", "-o", out]
    r = sh(base + ["--download-sections", f"*0-{int(seconds)}", "--force-keyframes-at-cuts", src])
    if not os.path.exists(out) or os.path.getsize(out) < 10000:
        say("section download failed, trying the full file:", (r.stderr or r.stdout)[-200:].replace("\n", " ")); sh(base + [src])
    if not os.path.exists(out): sys.exit("download failed: " + (r.stderr or "")[-300:])
    return out
def read_frames(path, vf, w, h, ss=0.0, t=None, ch=3):
    """generator of numpy frames (h, w, ch) from ffmpeg rawvideo"""
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{ss:.3f}"] + (["-t", f"{t:.3f}"] if t else []) + ["-i", path, "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24" if ch == 3 else "gray", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL); n = w * h * ch
    try:
        while True:
            b = p.stdout.read(n)
            if len(b) < n: break
            yield np.frombuffer(b, dtype=np.uint8).reshape(h, w, ch) if ch == 3 else np.frombuffer(b, dtype=np.uint8).reshape(h, w)
    finally: p.kill()
# ---- scenes / audio ------------------------------------------------------------------------------------------------------------------------------------------------
def measure_cuts(path, dur, thr=0.30):
    r = sh(["ffmpeg", "-nostats", "-v", "info", "-i", path, "-an", "-vf", f"select='gt(scene,{thr})',showinfo", "-f", "null", "-"]).stderr
    ts = [float(x) for x in re.findall(r"pts_time:([\d.]+)", r)]; ts = [t for t in ts if t > 0.3]
    edges = [0.0] + ts + [dur]; shots = np.diff(edges); shots = shots[shots > 0.1]
    return {"cuts": len(ts), "cuts_per_min": round(len(ts) / dur * 60, 1), "avg_shot_s": round(float(shots.mean()), 2), "median_shot_s": round(float(np.median(shots)), 2), "min_shot_s": round(float(shots.min()), 2), "max_shot_s": round(float(shots.max()), 2), "cut_times": [round(t, 2) for t in ts[:200]]}
def measure_audio(path, dur):
    r = sh(["ffmpeg", "-nostats", "-v", "info", "-i", path, "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"]).stderr; sm = r.split("Summary:")[-1]
    def g(rx):
        m = re.search(rx, sm); return float(m.group(1)) if m else None
    out = {"lufs": g(r"I:\s+(-?[\d.]+) LUFS"), "lra": g(r"LRA:\s+([\d.]+) LU"), "true_peak_db": g(r"Peak:\s+(-?[\d.]+) dBFS")}
    s = sh(["ffmpeg", "-nostats", "-v", "info", "-i", path, "-vn", "-af", "silencedetect=n=-42dB:d=0.5", "-f", "null", "-"]).stderr
    st = [float(x) for x in re.findall(r"silence_duration: ([\d.]+)", s)]; out["silence_pct"] = round(100 * sum(st) / dur, 1); out["silences_per_min"] = round(len(st) / dur * 60, 1)
    return out
# ---- captions / hook / layout ----------------------------------------------------------------------------------------------------------------------------------------
def _dilate(b, r):
    out = b.copy()
    for _ in range(r):
        o = out.copy(); o[1:] |= out[:-1]; o[:-1] |= out[1:]; out = o
        o = out.copy(); o[:, 1:] |= out[:, :-1]; o[:, :-1] |= out[:, 1:]; out = o
    return out
def text_mask(fr):
    """bright (saturated or white) pixels touching a near-black outline = burned-in text"""
    f = fr.astype(np.int16); mx = f.max(2); mn = f.min(2); sat = (mx - mn) / (mx + 1.0)
    fill = (mx >= 200) & ((sat > 0.55) | (mn >= 205)); dark = mx <= 50
    return fill & _dilate(dark, 2)
def sample_frames(path, d, w, h, step=0.5, ss=0.0, t=None, cap=160):
    fr = list(read_frames(path, f"fps={1 / step},scale={w}:{h}", w, h, ss, t)); return fr[:cap]
def analyse_text(frames, step, y_lo=0.0, y_hi=1.0):
    """presence / colour / vertical position of text-like pixels in the band [y_lo, y_hi] of the frames after removing static overlays"""
    if not frames: return None
    H, W = frames[0].shape[:2]; ms = np.stack([text_mask(f) for f in frames]); band = np.zeros((H, W), bool); band[int(y_lo * H):int(y_hi * H)] = True
    static = ms.mean(0) > 0.6; ms = ms & ~static & band; cnt = ms.reshape(len(frames), -1).sum(1); present = cnt > 0.0012 * H * W
    res = {"coverage": round(float(present.mean()), 2), "frames": len(frames), "present_flags": present.tolist()}
    if present.sum() == 0: return res
    pm = ms[present]; rows = pm.sum(2)   # (n, H) pixels per row
    ys = []; hs = []; bots = []; tops = []; sel_runs = []
    for fi_, r in zip(np.where(present)[0], rows):
        if r.sum() < 5: continue
        on = r >= max(2.0, 0.12 * r.max()); runs = []; i = 0; gap = max(3, int(H * 0.012))
        while i < H:   # contiguous runs of text rows (gaps up to ~1.2 % of the height are bridged)
            if on[i]:
                j = i; last = i
                while j < H and (on[j] or j - last <= gap):
                    if on[j]: last = j
                    j += 1
                runs.append((i, last, float(r[i:last + 1].sum()))); i = j
            else: i += 1
        if not runs: continue
        mx = max(x[2] for x in runs); lo_ = [x for x in runs if x[2] >= 0.4 * mx][-1]   # the lowest substantial run = the caption (a hook above it is a separate run)
        ys.append((lo_[0] + lo_[1]) / 2.0); tops.append(lo_[0]); bots.append(lo_[1]); hs.append(lo_[1] - lo_[0] + 1); sel_runs.append((fi_, lo_[0], lo_[1]))
    if ys:   # keep only the frames whose text sits where most of it sits (drops the hook line that shows alone during the first seconds)
        med = float(np.median(ys)); keep = [i for i, y in enumerate(ys) if abs(y - med) <= 0.06 * H]
        ys, tops, bots, hs, sel_runs = ([x[i] for i in keep] for x in (ys, tops, bots, hs, sel_runs))
        res.update({"y_center": round(float(np.median(ys)) / H, 3), "y_top": round(float(np.percentile(tops, 20)) / H, 3), "y_bottom": round(float(np.percentile(bots, 80)) / H, 3), "band_h": round(float(np.median(hs)) / H, 3)})
    if sel_runs:   # burned-in captions are horizontally centred and do not touch the frame edge; game HUD / stream overlays sit in corners and edges
        xs = np.concatenate([np.where(ms[i][lo:hi + 1])[1] for i, lo, hi in sel_runs]); res["x_center"] = round(float(xs.mean()) / W, 2) if len(xs) else None
        if res["x_center"] is None or abs(res["x_center"] - 0.5) > 0.12 or res.get("y_bottom", 0) > 0.985:
            res["rejected"] = "not caption-like (off-centre or on the frame edge)"; res["coverage"] = 0.0
    px = np.concatenate([frames[i][lo:hi + 1][ms[i][lo:hi + 1]] for i, lo, hi in sel_runs] or [np.zeros((0, 3), np.uint8)]); px = px[:200000].astype(np.int16)
    mx, mn = px.max(1), px.min(1); white = (mn >= 205) & ((mx - mn) < 40); col = ~white
    res["white_share"] = round(float(white.mean()), 2)
    if col.sum() > 30:
        c = px[col]; hue = np.arctan2(np.sqrt(3) * (c[:, 1] - c[:, 2]), 2 * c[:, 0] - c[:, 1] - c[:, 2]); hb = ((hue + np.pi) / (2 * np.pi) * 12).astype(int) % 12; top = np.bincount(hb, minlength=12).argmax()
        sel = c[hb == top]; sel = sel[sel.max(1) >= np.percentile(sel.max(1), 40)]; res["color_hex"] = "#%02X%02X%02X" % tuple(int(x) for x in np.median(sel, axis=0)); res["colored_share"] = round(float(col.mean()), 2)
    return res
def measure_layout(frames):
    """portrait frames: sharp content in the middle with blurred/black bands above and below?"""
    if not frames: return {}
    g = np.stack([f.astype(np.float32).mean(2) for f in frames[::3] or frames]); gx = np.abs(np.diff(g, axis=2)).mean((0, 2)); gy = np.abs(np.diff(g, axis=1)).mean((0, 2)); e = gx[: len(gy)] + gy[: len(gx)] if len(gx) != len(gy) else gx + gy
    e = np.convolve(e, np.ones(5) / 5, mode="same"); H = len(e); top, mid, bot = e[: int(.12 * H)].mean(), e[int(.4 * H):int(.6 * H)].mean(), e[int(.88 * H):].mean(); bright = np.stack([f.astype(np.float32).mean(2) for f in frames]).mean((0, 2))
    tb = float(bright[: int(.12 * H)].mean()); bb = float(bright[int(.88 * H):].mean()); out = {"edge_top": round(float(top), 2), "edge_mid": round(float(mid), 2), "edge_bottom": round(float(bot), 2), "brightness_top": round(tb, 1)}
    sharp = e > 0.45 * mid; idx = np.where(sharp)[0]
    if len(idx): out["content_h_frac"] = round((idx.max() - idx.min()) / H, 2)
    if max(top, bot) < 0.35 * mid: out["mode"] = "bars" if (tb < 10 and bb < 10) else "blur_fill"
    else: out["mode"] = "full_frame"
    return out
# ---- zoom ------------------------------------------------------------------------------------------------------------------------------------------------------------
def measure_zoom(path, info, seconds=60.0, fps=30, w=160):
    """global scale change between consecutive frames (least squares of dI = -(s-1) * grad(I).r) outside text/overlay pixels (caption pop-in animations would look like zooms);
    a zoom event = the scale rises >= 3 % (as estimated; the estimate reads about 0.65x of a true punch-in) within 0.7 s. Scene cuts are skipped."""
    h = int(round(w * info["h"] / info["w"] / 2) * 2); prev = None; pm = None; ks = []
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32); rx, ry = xx - w / 2, yy - h / 2
    for f in read_frames(path, f"fps={fps},scale={w}:{h}", w, h, 0.0, seconds, ch=3):
        g = f.astype(np.float32).mean(2); m = _dilate(text_mask(f), 5)
        if prev is not None:
            d = g - prev; ok = ~(m | pm); gy, gx = np.gradient((g + prev) / 2); gr = (gx * rx + gy * ry) * ok; den = float((gr * gr).sum()) + 1e-6; k = -float((d * ok * gr).sum()) / den
            ks.append(0.0 if float(np.abs(d).mean()) > 18 else k)
        prev, pm = g, m
    if len(ks) < fps: return {"events": 0, "events_per_min": 0.0, "frames": len(ks)}
    k = np.clip(np.array(ks), -0.05, 0.05); S = np.cumsum(k); win = int(0.7 * fps); ev = []; i = 0
    while i < len(S) - 2:
        j = min(len(S) - 1, i + win); rise = float(S[i:j + 1].max() - S[i])
        if rise >= 0.03: ev.append((i / fps, rise / 0.65)); i = j + fps // 2
        else: i += 1
    dur = len(ks) / fps
    strengths = [x for x in (refine_strength(path, info, t) for t, _ in ev[:12]) if x is not None]
    return {"events": len(ev), "events_per_min": round(len(ev) / dur * 60, 1), "median_strength": round(float(np.median(strengths)), 3) if strengths else (round(float(np.median([r for _, r in ev])), 3) if ev else 0.0), "event_times": [round(t, 2) for t, _ in ev][:100], "analysed_s": round(dur, 1)}
def refine_strength(path, info, t, w=320, seconds=1.7):
    """punch-in size of one detected event: best zoom factor s (1.00-1.30) that maps the frame before the event onto a later frame (normalised correlation outside text pixels)"""
    h = int(round(w * info["h"] / info["w"] / 2) * 2); fr = list(read_frames(path, f"fps=30,scale={w}:{h}", w, h, max(0.0, t - 0.1), seconds, ch=3))
    if len(fr) < 8: return None
    g = [f.astype(np.float32).mean(2) for f in fr]; ok = ~_dilate(text_mask(fr[0]), 5)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32); cy, cx = h / 2, w / 2; A = g[0]; best = (0.0, 1.0)
    def warp(img, sc):   # zoom in by sc around the centre (bilinear)
        y = (yy - cy) / sc + cy; x = (xx - cx) / sc + cx; y0 = np.clip(np.floor(y).astype(int), 0, h - 2); x0 = np.clip(np.floor(x).astype(int), 0, w - 2); fy, fx = y - y0, x - x0
        return (img[y0, x0] * (1 - fy) * (1 - fx) + img[y0 + 1, x0] * fy * (1 - fx) + img[y0, x0 + 1] * (1 - fy) * fx + img[y0 + 1, x0 + 1] * fy * fx)
    wins = np.zeros((h, w), bool); wins[int(h * .1):int(h * .9), int(w * .1):int(w * .9)] = True
    P = [1.0]; step = 3   # local scale between frames 0.1 s apart (small motion -> reliable), chained; the event size = the largest rise of the chained scale
    for j in range(step, len(g), step):
        A_, B_ = g[j - step], g[j]; okj = wins & ~_dilate(text_mask(fr[j - step]), 5) & ~_dilate(text_mask(fr[j]), 5); bs = (-2.0, 1.0)
        for sc in np.arange(0.97, 1.081, 0.004):
            Aw = warp(A_, sc); a = Aw[okj] - Aw[okj].mean(); b = B_[okj] - B_[okj].mean(); c = float((a * b).sum() / (np.sqrt((a * a).sum() * (b * b).sum()) + 1e-6))
            if c > bs[0]: bs = (c, sc)
        P.append(P[-1] * (bs[1] if bs[0] >= 0.5 else 1.0))
    P = np.array(P); rise = max(float(P[i:].max() / P[i]) - 1.0 for i in range(len(P)))
    best = (0, 1.0 + rise)
    return round(best[1] - 1.0, 3)
# ---- everything ------------------------------------------------------------------------------------------------------------------------------------------------------
def measure(path, seconds=180.0, log=say):
    info = probe(path); dur = min(info["dur"], seconds); portrait = info["h"] > info["w"]; W = 540 if portrait else 960; H = int(round(W * info["h"] / info["w"] / 2) * 2)
    m = {"video": dict(info, analysed_s=round(dur, 1), portrait=portrait)}
    log("probe", m["video"]); m["pace"] = measure_cuts(path, dur); log("cuts", {k: v for k, v in m["pace"].items() if k != "cut_times"}); m["audio"] = measure_audio(path, dur); log("audio", m["audio"])
    step = 0.5; fr = sample_frames(path, dur, W, H, step, 0.0, dur, cap=160)
    lo, hi = (0.0, 1.0) if portrait else (0.55, 1.0)   # landscape sources: captions live in the lower part, the upper part is the game/stream
    m["captions"] = analyse_text(fr, step, lo, hi) or {}; m["captions"].pop("present_flags", None); log("captions", {k: v for k, v in m["captions"].items() if k != "present_flags"})
    # hook text: text visible in the first seconds in the upper half that is gone afterwards
    ef = sample_frames(path, dur, W, H, 0.25, 0.0, 5.0, cap=20); hk = analyse_text(ef, 0.25, 0.08, 0.5 if portrait else 0.45) if ef else None
    if hk and "present_flags" in hk:
        fl = hk["present_flags"]; late = np.mean(fl[12:]) if len(fl) > 12 else 0; early = np.mean(fl[:6]); hk["present"] = bool(early > 0.6 and late < 0.4)
        if hk["present"]:
            n = 0
            while n < len(fl) and fl[n]: n += 1
            hk["duration_s"] = round(n * 0.25, 2)
        hk.pop("present_flags", None)
    m["hook"] = hk or {"present": False}; log("hook", m["hook"])
    if portrait: m["layout"] = measure_layout(fr); log("layout", m["layout"])
    m["zoom"] = measure_zoom(path, info, min(60.0, dur)); log("zoom", {k: v for k, v in m["zoom"].items() if k != "event_times"})
    return m
# ---- Gemini ----------------------------------------------------------------------------------------------------------------------------------------------------------
FONTS = ["Heebo Black", "Anton", "Bangers", "Bebas Neue", "Montserrat"]
def gemini_describe(path, measured, seconds=150):
    """upload a small proxy of the video to the Gemini Files API and ask for the qualitative style description (JSON). Returns dict or None."""
    try: import vod_shorts as V; keys = V.gem_keys()
    except Exception as e: say("vod_shorts import failed:", e); keys = [os.environ[k] for k in ["GEMINI_API_KEY"] + [f"GEMINI_API_KEY_{i}" for i in range(2, 8)] if os.environ.get(k)]
    if not keys: say("no Gemini key: measurements only"); return None
    tmp = tempfile.mkdtemp(); prox = os.path.join(tmp, "p.mp4")
    r = sh(["ffmpeg", "-v", "error", "-y", "-i", path, "-t", str(seconds), "-vf", "scale='min(540,iw)':-2", "-r", "24", "-c:v", "libx264", "-crf", "30", "-preset", "veryfast", "-c:a", "aac", "-b:a", "64k", prox])
    if r.returncode: say("proxy encode failed", r.stderr[-200:]); return None
    mm = {k: v for k, v in measured.items()}; mm["pace"] = {k: v for k, v in measured["pace"].items() if k != "cut_times"}; mm["zoom"] = {k: v for k, v in measured["zoom"].items() if k != "event_times"}
    prompt = ("You analyse HOW a video is edited (not what it is about) so that a copy-cat editor can reproduce the look. Watch picture and listen to sound. Measured facts from software (trust these numbers): " + json.dumps(mm)[:2500] + "\n"
              "Return JSON only with exactly these keys: {\"summary\":\"2 sentences on the editing style\",\"genre\":\"reaction|comedy|gaming|story|compilation|other\",\"language\":\"ISO code of the speech\",\"language_name\":\"\","
              "\"captions\":{\"present\":bool,\"font_look\":\"describe the typeface\",\"closest_font\":\"one of " + ", ".join(FONTS) + "\",\"animation\":\"none|pop|bounce|fade|karaoke\",\"uppercase\":bool,\"words_per_group\":int,\"active_word_highlighted\":bool,\"highlight_color_hex\":\"#RRGGBB or empty\"},"
              "\"hook_text\":{\"present\":bool,\"style\":\"\"},\"zoom\":{\"used\":bool,\"kind\":\"punch-in|slow push|none\"},\"sfx\":{\"used\":bool,\"kinds\":\"\"},\"music\":{\"used\":bool,\"kind\":\"\"},\"intro\":{\"present\":bool,\"seconds\":number},\"outro\":{\"present\":bool,\"seconds\":number},"
              "\"layout\":\"how the picture is arranged\",\"pacing\":\"slow|medium|fast\",\"transitions\":\"\",\"must_reproduce\":[\"3-6 concrete rules a copy-cat must follow\"]}")
    n = os.path.getsize(prox)
    for key in keys:
        try:
            h = ["-H", "X-Goog-Upload-Protocol: resumable", "-H", "X-Goog-Upload-Command: start", "-H", f"X-Goog-Upload-Header-Content-Length: {n}", "-H", "X-Goog-Upload-Header-Content-Type: video/mp4", "-H", "Content-Type: application/json"]
            hd = sh(["curl", "-sS", "-m", "60", "-D", "-", "-o", "/dev/null", f"https://generativelanguage.googleapis.com/upload/v1beta/files?key={key}"] + h + ["-d", json.dumps({"file": {"display_name": "ref"}})]).stdout
            up = re.search(r"(?i)x-goog-upload-url:\s*(\S+)", hd)
            if not up: say("gemini upload start failed:", hd[:120].replace("\n", " ")); continue
            fi = json.loads(sh(["curl", "-sS", "-m", "600", up.group(1), "-H", "X-Goog-Upload-Offset: 0", "-H", "X-Goog-Upload-Command: upload, finalize", "--data-binary", f"@{prox}"]).stdout)["file"]
            for _ in range(60):
                if fi.get("state") != "PROCESSING": break
                time.sleep(4); fi = json.loads(sh(["curl", "-sS", "-m", "60", f"https://generativelanguage.googleapis.com/v1beta/{fi['name']}?key={key}"]).stdout)
            if fi.get("state") != "ACTIVE": say("gemini file state", fi.get("state")); continue
            for model in ("gemini-flash-latest", "gemini-3.5-flash", "gemini-flash-latest"):   # last entry = one retry of the alias after a 503 (temporary overload)
                body = {"contents": [{"parts": [{"file_data": {"file_uri": fi["uri"], "mime_type": "video/mp4"}}, {"text": prompt}]}], "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"}}
                r = sh(["curl", "-sS", "-m", "300", f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent", "-H", "x-goog-api-key: " + key, "-H", "Content-Type: application/json", "-d", json.dumps(body)])
                try: return json.loads(json.loads(r.stdout)["candidates"][0]["content"]["parts"][0]["text"])
                except Exception:
                    say("gemini", model, "failed:", r.stdout[:160].replace("\n", " "))
                    if '"code": 503' in r.stdout: time.sleep(20)
        except Exception as e: say("gemini error:", str(e)[:150])
    return None
# ---- build the style -------------------------------------------------------------------------------------------------------------------------------------------------
def _clamp(v, lo, hi): return max(lo, min(hi, v))
def build_style(name, src, m, g, fmt=None):
    v = m["video"]; fmt = fmt or ("shorts" if v["portrait"] and v["dur"] <= 190 else "long"); S = {}; notes = []
    def put(sec, key, val):
        if val is not None: S.setdefault(sec, {})[key] = val
    if fmt == "shorts":
        d = v["analysed_s"]; put("pace", "min_clip_s", float(_clamp(round(d * 0.7), 5, 180))); put("pace", "max_clip_s", float(_clamp(round(d * 1.3 + 3), 10, 180))); put("pace", "target_clip_s", float(_clamp(round(d), 5, 180)))
        asp = v["w"] / v["h"]; put("layout", "aspect", "9:16" if asp < 0.6 else "4:5" if asp < 0.85 else "1:1" if asp < 1.2 else "16:9")
        lay = m.get("layout", {}); mode = lay.get("mode")
        if mode in ("blur_fill", "bars"): put("layout", "mode", mode)
        elif mode == "full_frame": put("layout", "mode", "crop_fill")
    ca = m["captions"]; gc = (g or {}).get("captions", {})
    cap_present = ca.get("coverage", 0) >= 0.25
    if g and "present" in gc and not cap_present and gc["present"] and ca.get("coverage", 0) >= 0.12: cap_present = True
    put("captions", "enabled", bool(cap_present))
    if cap_present:
        H = 1920 if v["portrait"] else 1080; scale = H / 1920.0 if v["portrait"] else 1.0
        if "color_hex" in ca and ca.get("white_share", 0) < 0.6: put("captions", "color", ca["color_hex"])
        elif ca.get("white_share", 0) >= 0.6: put("captions", "color", "#FFFFFF")
        if "color_hex" in ca and ca.get("white_share", 0) >= 0.6 and ca.get("colored_share", 0) >= 0.1: put("captions", "highlight_color", ca["color_hex"]); put("captions", "animation", "karaoke")
        if "band_h" in ca and ca.get("frames"):
            lines = 1; size = ca["band_h"] * H / 0.6 / lines; put("captions", "size", int(_clamp(round(size / 2) * 2, 28, 200)) if v["portrait"] else int(_clamp(round(size * 1080 / H / 2) * 2, 24, 120)))
        if "y_bottom" in ca:
            if ca["y_center"] < 0.33: put("captions", "align", 8); put("captions", "margin_v", int(_clamp(ca["y_top"] * H, 0, 1800)))
            elif ca["y_center"] < 0.6 and v["portrait"]: put("captions", "align", 5); put("captions", "margin_v", 0)
            else: put("captions", "align", 2); put("captions", "margin_v", int(_clamp((1 - ca["y_bottom"]) * H - 30, 0, 1800)))
        if gc:
            if gc.get("closest_font") in FONTS: put("captions", "font", gc["closest_font"])
            if gc.get("animation") in ("none", "pop", "bounce", "fade", "karaoke") and "animation" not in S.get("captions", {}): put("captions", "animation", gc["animation"])
            if isinstance(gc.get("uppercase"), bool): put("captions", "uppercase", gc["uppercase"])
            if isinstance(gc.get("words_per_group"), int) and 1 <= gc["words_per_group"] <= 12: put("captions", "words_per_group", gc["words_per_group"])
            hc = gc.get("highlight_color_hex") or ""
            if re.fullmatch(r"#[0-9a-fA-F]{6}", hc) and S["captions"].get("animation") == "karaoke" and "highlight_color" not in S["captions"]: put("captions", "highlight_color", hc.upper())
    if fmt == "shorts":
        hk = m.get("hook", {}); gh = (g or {}).get("hook_text", {})
        hook_on = bool(hk.get("present")) or (bool(gh.get("present")) and "present" not in hk)
        put("hook", "enabled", hook_on)
        if hk.get("present"):
            if hk.get("duration_s"): put("hook", "duration_s", float(_clamp(hk["duration_s"], 0.5, 8)))
            if "y_top" in hk: put("hook", "y", int(_clamp(hk["y_top"] * 1920, 0, 1800)))
            if "band_h" in hk: put("hook", "size", int(_clamp(round(hk["band_h"] * 1920 / 0.7 / 2) * 2, 24, 200)))
            if hk.get("white_share", 0) < 0.6 and "color_hex" in hk: put("hook", "color", hk["color_hex"])
    z = m["zoom"]; gz = (g or {}).get("zoom", {})
    if fmt == "shorts":
        if z["events"] >= 1:
            put("zoom", "enabled", True); put("zoom", "strength", round(_clamp(z["median_strength"], 0.02, 0.2), 3)); epm = z["events_per_min"]
            if epm >= 4 and z["events"] >= 3: put("zoom", "extra_every_s", round(_clamp(60 / epm, 2, 30), 1))
        else: put("zoom", "enabled", False)
    ad = m["audio"]
    if ad.get("lufs") is not None and ad["lufs"] > -60:
        put("loudness", "enabled", True); put("loudness", "lufs", round(_clamp(ad["lufs"], -30, -8), 1))
        if ad.get("true_peak_db") is not None: put("loudness", "tp", round(_clamp(min(ad["true_peak_db"], -1.0), -9, 0), 1))
        if ad.get("lra") is not None: put("loudness", "lra", round(_clamp(ad["lra"], 1, 20), 1))
    pc = m["pace"]; dead = 0.0
    if v["analysed_s"] < 30: pass   # too short to judge a cut pace
    elif pc["cuts_per_min"] >= 6 and ad.get("silence_pct", 100) < 4: dead = 0.7   # fast jump-cut pace with almost no silence left in it
    elif pc["cuts_per_min"] >= 2 and ad.get("silence_pct", 100) < 8: dead = 1.5
    put("pace", "dead_air_trim_s", dead)
    if g:
        if g.get("language") and re.fullmatch(r"[a-z]{2,3}", str(g["language"]).lower()): put("language", "code", g["language"].lower()); put("language", "name", g.get("language_name") or g["language"])
        sfx = g.get("sfx", {})
        if fmt == "shorts" and isinstance(sfx.get("used"), bool): put("sfx", "mode", "on" if sfx["used"] else "off")
        if g.get("music", {}).get("used"): notes.append("the reference uses music (" + str(g["music"].get("kind", "")) + "): supply a royalty-free file in assets/music and set music.enabled + music.file")
        it = g.get("intro", {})
        if it.get("present") and isinstance(it.get("seconds"), (int, float)) and 0 < it["seconds"] <= 8: put("intro", "bumper_s", float(it["seconds"]))
        elif it.get("present") is False and fmt == "long": put("intro", "bumper_s", 0)
        for x in g.get("must_reproduce", []) or []: notes.append(str(x)[:200])
    S = {sec: kv for sec, kv in S.items() if kv}
    style = {"schema": 1, "name": name, "label": name, "description": (g or {}).get("summary") or f"Measured from {src}: {pc['cuts_per_min']} cuts/min, {ad.get('lufs')} LUFS, captions coverage {m['captions'].get('coverage')}", "extends": "signature",
             "source": {"kind": "video", "url": src if not os.path.exists(src) else os.path.basename(src), "format": fmt, "measured": {k: ({kk: vv for kk, vv in v_.items() if kk not in ("cut_times", "event_times")} if isinstance(v_, dict) else v_) for k, v_ in m.items()}}, fmt: S}
    if g: style["source"]["gemini"] = g
    if notes: style["notes"] = notes
    return style
def compare(m, stylename):
    """measured values next to what the style promises"""
    fmt = "shorts" if m["video"]["portrait"] else "long"; st = ST.resolve(stylename, fmt); rows = []; ca = m["captions"]; c = st["captions"]
    def row(k, exp, got, ok): rows.append((k, exp, got, ok)); say(f"{'OK  ' if ok else 'DIFF'} {k:26s} style={exp!s:22s} measured={got}")
    row("captions present", c["enabled"], ca.get("coverage", 0) >= 0.25, c["enabled"] == (ca.get("coverage", 0) >= 0.25))
    if c["enabled"] and "color_hex" in ca:
        def rgb(h): h = ST.norm_color(h)[1:]; return [int(h[i:i + 2], 16) for i in (0, 2, 4)]
        e = rgb(c["color"]); gg = rgb(ca["color_hex"]); row("caption colour", ST.norm_color(c["color"]), ca["color_hex"], max(abs(a - b) for a, b in zip(e, gg)) <= 40)
    if c["enabled"] and "y_bottom" in ca and m["video"]["portrait"]:
        exp_bottom = 1 - c["margin_v"] / 1920.0 - 0.015; row("caption bottom edge (frac of H)", round(exp_bottom, 2), ca["y_bottom"], abs(exp_bottom - ca["y_bottom"]) <= 0.03)
        exp_h = c["size"] * 0.6 / 1920.0; row("caption band height (frac of H)", round(exp_h, 3), ca.get("band_h"), abs(exp_h - ca.get("band_h", 0)) <= 0.012)
    if st["loudness"]["enabled"] and m["audio"].get("lufs") is not None: row("loudness LUFS", st["loudness"]["lufs"], m["audio"]["lufs"], abs(st["loudness"]["lufs"] - m["audio"]["lufs"]) <= 1.5)
    if fmt == "shorts":
        row("zoom events (>=1 expected)" if st["zoom"]["enabled"] else "zoom events (0 expected)", st["zoom"]["enabled"], m["zoom"]["events"], (m["zoom"]["events"] >= 1) == st["zoom"]["enabled"])
        row("layout mode", st["layout"]["mode"], m.get("layout", {}).get("mode"), m.get("layout", {}).get("mode") == st["layout"]["mode"])
    row("cuts per minute (single take expected)" if st["pace"]["dead_air_trim_s"] == 0 else "cuts per minute", "~0" if st["pace"]["dead_air_trim_s"] == 0 else ">0", m["pace"]["cuts_per_min"], True)
    return rows
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("src"); ap.add_argument("--name", default=None); ap.add_argument("--out", default=None); ap.add_argument("--seconds", type=float, default=180); ap.add_argument("--no-gemini", action="store_true"); ap.add_argument("--compare", default=None); ap.add_argument("--format", default=None, choices=["shorts", "long"]); a = ap.parse_args()
    tmp = tempfile.mkdtemp(); path = fetch(a.src, a.seconds, tmp); m = measure(path, a.seconds)
    if a.compare:
        rows = compare(m, a.compare); sys.exit(0 if all(r[3] for r in rows) else 2)
    g = None if a.no_gemini else gemini_describe(path, m)
    if g: say("gemini:", json.dumps(g, ensure_ascii=False)[:1500])
    name = re.sub(r"[^a-z0-9_-]+", "-", (a.name or os.path.splitext(os.path.basename(a.src))[0] or "style").lower()).strip("-") or "style"
    style = build_style(name, a.src, m, g, a.format); errs = ST.validate(style)
    if errs: say("VALIDATION PROBLEMS:", errs); [style[f].get(sec, {}).pop(k, None) for f in ("shorts", "long") if f in style for e_ in errs for sec, k in [re.sub(r"^(shorts|long)\.", "", e_.split(":")[0]).split(".", 1)] if "." in e_.split(":")[0]]
    out = a.out or os.path.join(ST.STYLE_DIR, name + ".json"); os.makedirs(os.path.dirname(out) or ".", exist_ok=True); json.dump(style, open(out, "w", encoding="utf-8"), indent=1, ensure_ascii=False); open(out, "a").write("\n")
    say("wrote", out, "| validation:", ST.validate(out) or "OK"); print(json.dumps(style, indent=1, ensure_ascii=False)[:6000])
if __name__ == "__main__": main()

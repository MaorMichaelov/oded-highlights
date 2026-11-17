#!/usr/bin/env python3
"""Pro-looking 16:9 thumbnail from a REAL frame of the video (no AI art): best frame -> face-aware crop -> colour grade -> rim glow -> big outlined hook text -> brand strip + logo.
usage: thumb_pro.py VIDEO.mp4 OUT.jpg --text "WHO IS THIS GUY" [--accent FFC107] [--logo assets/world_clips/logo_clipglobe.png] [--frames 24]
Frame choice: sharp + colourful candidates, then Gemini vision (if a key is set) picks the most expressive one and returns the face box; without Gemini a centred crop of the sharpest frame is used.
Fonts: assets/fonts/Anton-Regular.ttf (fetch-fonts workflow), fallback DejaVu Sans Bold."""
import argparse, base64, glob, json, os, subprocess, sys, tempfile
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageEnhance, ImageChops
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
W, H = 1280, 720
def sh(c): return subprocess.run(c, capture_output=True, text=True)
def font(size):
    for f in ("assets/fonts/Anton-Regular.ttf", "assets/fonts/BebasNeue-Regular.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        p = os.path.join(ROOT, f) if not f.startswith("/") else f
        if os.path.exists(p) and os.path.getsize(p) > 5000:
            try: return ImageFont.truetype(p, size)
            except Exception: pass
    return ImageFont.load_default()
def extract(video, n, d):
    dur = float(sh(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video]).stdout.strip() or 0)
    out = []
    for i in range(n):
        t = dur * (0.04 + 0.92 * i / max(1, n - 1)); f = f"{d}/f{i:02d}.jpg"
        sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", video, "-frames:v", "1", "-vf", "scale=1920:-2", "-q:v", "2", f]);
        if os.path.exists(f): out.append((t, f))
    return out
def score(f):
    im = Image.open(f).convert("RGB"); sm = im.resize((480, 270)); a = np.asarray(sm.convert("L"), dtype=np.float32)
    lap = np.abs(a[1:-1, 1:-1] * 4 - a[:-2, 1:-1] - a[2:, 1:-1] - a[1:-1, :-2] - a[1:-1, 2:]).var()       # sharpness
    hsv = np.asarray(sm.convert("HSV"), dtype=np.float32); sat = hsv[..., 1].mean(); val = hsv[..., 2].mean()
    exposure = 1 - abs(val - 125) / 125
    return float(lap) ** 0.5 * 2 + sat * 0.4 + exposure * 30
def gemini_pick(cands, hint):
    keys = [os.environ[k] for k in ["GEMINI_API_KEY"] + [f"GEMINI_API_KEY_{i}" for i in range(2, 8)] if os.environ.get(k)]
    if not keys: return None
    parts = [{"text": f"These are {len(cands)} candidate frames (numbered 0..{len(cands)-1}) from a streamer video{(' about: ' + hint) if hint else ''}. Choose the ONE best YouTube thumbnail frame: a clear, large, well-lit face with a strong readable emotion (shock, laughter, intensity), eyes visible, not mid-blink, not blurry, no UI clutter. Return JSON {{\"best\": index, \"face_box\": [ymin, xmin, ymax, xmax] of the main face in that frame as 0-1000 normalized coordinates, or null if no face}}."}]
    for i, (_, f) in enumerate(cands):
        im = Image.open(f).convert("RGB"); im.thumbnail((640, 360)); b = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False); im.save(b.name, quality=80)
        parts += [{"text": f"frame {i}:"}, {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(open(b.name, "rb").read()).decode()}}]
    for key in keys:
        for model in ("gemini-flash-latest", "gemini-3.5-flash"):
            r = sh(["curl", "-sS", "-m", "90", f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent", "-H", "x-goog-api-key: " + key, "-H", "Content-Type: application/json", "-d", json.dumps({"contents": [{"parts": parts}], "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}})])
            try: d = json.loads(json.loads(r.stdout)["candidates"][0]["content"]["parts"][0]["text"]); return int(d["best"]), d.get("face_box")
            except Exception: print("gemini pick failed:", r.stdout[:100].replace("\n", " "))
    return None
def grade(im):
    im = ImageEnhance.Contrast(im).enhance(1.18); im = ImageEnhance.Color(im).enhance(1.28); im = ImageEnhance.Brightness(im).enhance(1.05)
    a = np.asarray(im, dtype=np.float32) / 255; a = np.clip(a ** 0.92, 0, 1)                       # slight lift of shadows
    a[..., 0] *= 1.03; a[..., 2] *= 0.97                                                            # warm tint
    return Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.UnsharpMask(2, 90, 3))
def vignette(im, strength=0.55):
    y, x = np.ogrid[:H, :W]; d = np.sqrt(((x - W / 2) / (W / 2)) ** 2 + ((y - H / 2) / (H / 2)) ** 2); m = 1 - np.clip((d - 0.55) / 0.9, 0, 1) ** 1.6 * strength
    return Image.fromarray((np.asarray(im, dtype=np.float32) * m[..., None]).clip(0, 255).astype(np.uint8))
def crop_to(img, box):
    """16:9 crop; if a face box (ymin,xmin,ymax,xmax in 0-1000) is known, zoom so the face is ~42% of the height and sits on the right third (text goes left)."""
    iw, ih = img.size
    if not box:
        ch = ih; cw = int(ch * 16 / 9)
        if cw > iw: cw = iw; ch = int(cw * 9 / 16)
        x0 = (iw - cw) // 2; y0 = (ih - ch) // 2; return img.crop((x0, y0, x0 + cw, y0 + ch)).resize((W, H), Image.LANCZOS), None
    y0, x0, y1, x1 = [v / 1000 for v in box]; fh = (y1 - y0) * ih; fcx = (x0 + x1) / 2 * iw; fcy = (y0 + y1) / 2 * ih
    ch = min(ih, max(fh / 0.42, ih * 0.55)); cw = ch * 16 / 9
    if cw > iw: cw = iw; ch = cw * 9 / 16
    cx = fcx - cw * (0.30 if fcx > iw * 0.5 else -0.30)                                             # face on the right when it is right of centre, else on the left
    cx = min(max(cx, cw / 2), iw - cw / 2); cy = min(max(fcy + ch * 0.05, ch / 2), ih - ch / 2)
    c = img.crop((int(cx - cw / 2), int(cy - ch / 2), int(cx + cw / 2), int(cy + ch / 2))).resize((W, H), Image.LANCZOS)
    s = W / cw; fx = (fcx - (cx - cw / 2)) * s; fy = (fcy - (cy - ch / 2)) * s; return c, (fx, fy, (x1 - x0) * iw * s, fh * s)
def stroke_text(d, xy, txt, f, fill, stroke=9, shadow=True):
    x, y = xy
    if shadow: d.text((x + 7, y + 9), txt, font=f, fill=(0, 0, 0, 170), stroke_width=stroke, stroke_fill=(0, 0, 0, 170))
    d.text((x, y), txt, font=f, fill=fill, stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
def hexrgb(h): h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
def build(video, out, text, accent, logo, nframes, hint):
    d = tempfile.mkdtemp(); fr = extract(video, nframes, d)
    if not fr: print("no frames"); return 1
    ranked = sorted(fr, key=lambda x: -score(x[1]))[:6]; box = None; pick = ranked[0]
    g = gemini_pick(ranked, hint)
    if g: pick = ranked[max(0, min(g[0], len(ranked) - 1))]; box = g[1]
    print("frame at", round(pick[0], 1), "s", "(gemini)" if g else "(sharpness)", "face box:", box)
    im = Image.open(pick[1]).convert("RGB"); base, face = crop_to(im, box); base = grade(base)
    # soft glow behind the face area (separates subject from background)
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if face:
        fx, fy, fw, fh = face; gl = Image.new("L", (W, H), 0); ImageDraw.Draw(gl).ellipse((fx - fw * 1.0, fy - fh * 0.9, fx + fw * 1.0, fy + fh * 1.1), fill=140); gl = gl.filter(ImageFilter.GaussianBlur(70))
        col = Image.new("RGB", (W, H), hexrgb(accent)); base = Image.composite(Image.blend(base, col, 0.28), base, gl)
    base = vignette(base)
    # text side = opposite to the face
    left_text = (face is None) or (face[0] > W * 0.5); words = text.upper().split(); lines = [" ".join(words[:2]), " ".join(words[2:4])] if len(words) > 2 else [" ".join(words)]; lines = [l for l in lines if l]
    fs = 170 if max(len(l) for l in lines) <= 8 else 140 if max(len(l) for l in lines) <= 12 else 112
    f = font(fs); mw = int(W * 0.56)
    while f.getlength(max(lines, key=len)) > mw and fs > 60: fs -= 6; f = font(fs)
    gradient = Image.new("RGBA", (W, H), (0, 0, 0, 0)); gd = ImageDraw.Draw(gradient)
    for x in range(int(W * 0.62)):
        a = int(165 * (1 - x / (W * 0.62)) ** 1.4); xx = x if left_text else W - 1 - x; gd.line((xx, 0, xx, H), fill=(0, 0, 0, a))
    base = Image.alpha_composite(base.convert("RGBA"), gradient)
    t = Image.new("RGBA", (W, H), (0, 0, 0, 0)); td = ImageDraw.Draw(t); lh = fs * 1.02; total = lh * len(lines); y = (H - total) / 2 - 10
    for i, l in enumerate(lines):
        x = 46 if left_text else W - 46 - f.getlength(l)
        stroke_text(td, (x, y + i * lh), l, f, hexrgb(accent) + (255,) if i == len(lines) - 1 else (255, 255, 255, 255), stroke=max(8, fs // 16))
    base = Image.alpha_composite(base, t)
    if logo and os.path.exists(logo):
        S = 128; lg = Image.open(logo).convert("RGB").resize((S, S), Image.LANCZOS); m = Image.new("L", (S * 4, S * 4), 0); ImageDraw.Draw(m).ellipse((0, 0, S * 4 - 1, S * 4 - 1), fill=255); m = m.resize((S, S), Image.LANCZOS)
        ring = Image.new("RGBA", (S + 12, S + 12), (0, 0, 0, 0)); ImageDraw.Draw(ring).ellipse((0, 0, S + 11, S + 11), fill=hexrgb(accent) + (255,)); pos = (W - S - 40 if left_text else 28, H - S - 38)
        base.alpha_composite(ring, (pos[0] - 6, pos[1] - 6)); badge = lg.convert("RGBA"); badge.putalpha(m); base.alpha_composite(badge, pos)
    # thin accent bar along the bottom
    ImageDraw.Draw(base).rectangle((0, H - 10, W, H), fill=hexrgb(accent) + (255,))
    base.convert("RGB").save(out, quality=93, subsampling=0); print("saved", out, os.path.getsize(out) // 1024, "KB"); return 0
if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("video"); ap.add_argument("out"); ap.add_argument("--text", required=True); ap.add_argument("--accent", default="FFC107"); ap.add_argument("--logo", default=os.path.join(ROOT, "assets/world_clips/logo_clipglobe.png")); ap.add_argument("--frames", type=int, default=24); ap.add_argument("--hint", default=""); a = ap.parse_args()
    sys.exit(build(a.video, a.out, a.text, a.accent, a.logo, a.frames, a.hint))

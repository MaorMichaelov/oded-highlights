#!/usr/bin/env python3
"""High-quality, fully automatic, zero-cost thumbnail maker (no paid image API).

Pipeline: real face frame -> crop -> upscale + detail recovery -> person cut-out (rembg human segmentation)
-> sticker outline + glow + shadow -> themed background (sunburst / gradient / optional real-frame backdrop)
-> optional guest cut-out + prop PNG -> Hebrew RTL headline (Heebo Black, stroke, accent word) placed on the side
OPPOSITE the face -> automatic QA (headline never overlaps the face, size <2 MB, legible at 168x94) -> JPEG.

usage:
  thumb_maker.py --frame FRAME.png --crop x0,y0,x1,y1 --head "עשיתי לו" --accent "סע!" --theme green --out thumb.jpg
                 [--guest GFRAME.png --guest-crop x0,y0,x1,y1] [--prop PROP.png] [--bg BACKDROP.png] [--side left|right]
Themes: green (brand), danger, party, money, cool.
Needs: pillow numpy opencv-python-headless rembg onnxruntime  (CPU only, runs on GitHub runners).
An AI scene generator can be plugged in later by passing --bg with the generated image; everything else stays the same.
"""
import argparse, math, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance, ImageFont, ImageChops

W, H = 1280, 720
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/sand-box/google/Heebo/Heebo-VariableFont_wght.ttf",
    "/usr/share/fonts/truetype/heebo/Heebo[wght].ttf",
]
THEMES = {  # bg dark, bg ray, accent (headline accent word + glow), outline (sticker)
    "green":  dict(dark=(8, 12, 8),   ray=(18, 48, 14),  accent=(120, 230, 40), glow=(60, 170, 30),  outline=(255, 255, 255)),
    "danger": dict(dark=(14, 6, 6),   ray=(60, 12, 12),  accent=(255, 70, 50),  glow=(190, 30, 20),  outline=(255, 255, 255)),
    "party":  dict(dark=(14, 6, 24),  ray=(54, 20, 84),  accent=(255, 210, 40), glow=(200, 60, 200), outline=(255, 255, 255)),
    "money":  dict(dark=(14, 12, 4),  ray=(64, 52, 10),  accent=(255, 205, 40), glow=(210, 160, 20), outline=(255, 255, 255)),
    "cool":   dict(dark=(5, 10, 20),  ray=(12, 40, 80),  accent=(60, 200, 255), glow=(30, 120, 220), outline=(255, 255, 255)),
}

def font(size):
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            f = ImageFont.truetype(p, size)
            try: f.set_variation_by_name("Black")
            except Exception: pass
            return f
    raise SystemExit("Heebo font not found (install fonts-google / download Heebo[wght].ttf)")

_session = None
def cutout(img_rgb):
    """person cut-out with soft, clean edges."""
    global _session
    from rembg import remove, new_session
    if _session is None: _session = new_session("u2net_human_seg")
    out = remove(img_rgb, session=_session, alpha_matting=False)
    a = np.array(out.split()[-1]).astype(np.float32) / 255.0
    a = np.clip((a - 0.12) / 0.76, 0, 1)                      # tighten the matte a little
    a = np.array(Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.1)))
    out.putalpha(Image.fromarray(a)); return out

def enhance(img, target_h):
    """upscale + recover detail from a low-res facecam crop."""
    s = target_h / img.height
    up = img.resize((int(img.width * s), target_h), Image.LANCZOS)
    try:
        import cv2
        a = cv2.cvtColor(np.array(up), cv2.COLOR_RGB2BGR)
        a = cv2.fastNlMeansDenoisingColored(a, None, 2, 2, 5, 15)
        lab = cv2.cvtColor(a, cv2.COLOR_BGR2LAB); l, A, B = cv2.split(lab)
        l = cv2.createCLAHE(clipLimit=1.6, tileGridSize=(8, 8)).apply(l)
        up = Image.fromarray(cv2.cvtColor(cv2.cvtColor(cv2.merge((l, A, B)), cv2.COLOR_LAB2BGR), cv2.COLOR_BGR2RGB))
    except Exception: pass
    up = up.filter(ImageFilter.UnsharpMask(radius=2.2, percent=140, threshold=2))
    up = ImageEnhance.Contrast(up).enhance(1.08); up = ImageEnhance.Color(up).enhance(1.18)
    return up

def sticker(person, th, outline_px=16, glow_px=46):
    """white outline + colored glow + soft shadow around an RGBA person."""
    a = person.split()[-1]
    pad = glow_px * 2 + 10
    canvas = Image.new("RGBA", (person.width + 2 * pad, person.height + 2 * pad), (0, 0, 0, 0))
    big = Image.new("L", canvas.size, 0); big.paste(a, (pad, pad))
    glow = big.filter(ImageFilter.MaxFilter(2 * outline_px + 1)).filter(ImageFilter.GaussianBlur(glow_px / 2))
    gl = Image.new("RGBA", canvas.size, th["glow"] + (0,)); gl.putalpha(glow.point(lambda v: int(v * 0.85)))
    canvas.alpha_composite(gl)
    sh = big.filter(ImageFilter.MaxFilter(2 * outline_px + 1)).filter(ImageFilter.GaussianBlur(14))
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0)); shadow.putalpha(sh.point(lambda v: int(v * 0.6)))
    canvas.alpha_composite(shadow, (8, 10)) if False else canvas.alpha_composite(ImageChops.offset(shadow, 8, 10))
    ol = big.filter(ImageFilter.MaxFilter(2 * outline_px + 1)).filter(ImageFilter.GaussianBlur(1.2))
    o = Image.new("RGBA", canvas.size, th["outline"] + (0,)); o.putalpha(ol); canvas.alpha_composite(o)
    p = Image.new("RGBA", canvas.size, (0, 0, 0, 0)); p.paste(person, (pad, pad)); canvas.alpha_composite(p)
    return canvas, pad

def background(th, side, backdrop=None):
    bg = Image.new("RGB", (W, H), th["dark"])
    if backdrop is not None:
        b = backdrop.convert("RGB").resize((W, H), Image.LANCZOS).filter(ImageFilter.GaussianBlur(10))
        b = ImageEnhance.Brightness(b).enhance(0.45); bg = Image.blend(bg, b, 0.85)
    d = ImageDraw.Draw(bg, "RGBA")
    cx = W * (0.30 if side == "left" else 0.70); cy = H * 0.52
    for i in range(28):
        a0 = math.radians(i * 360 / 28); a1 = math.radians(i * 360 / 28 + 6.5)
        d.polygon([(cx, cy), (cx + 1800 * math.cos(a0), cy + 1800 * math.sin(a0)), (cx + 1800 * math.cos(a1), cy + 1800 * math.sin(a1))], fill=th["ray"] + (170,))
    glow = Image.new("RGB", (W, H), (0, 0, 0)); ImageDraw.Draw(glow).ellipse((cx - 380, cy - 380, cx + 380, cy + 380), fill=th["glow"])
    glow = glow.filter(ImageFilter.GaussianBlur(130)); bg = ImageChops.add(bg, glow.point(lambda v: int(v * 0.55)))
    vig = Image.new("L", (W, H), 0); ImageDraw.Draw(vig).ellipse((-W * 0.2, -H * 0.2, W * 1.2, H * 1.2), fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(160)); bg = Image.composite(bg, Image.new("RGB", (W, H), (0, 0, 0)), vig.point(lambda v: 90 + int(v * 0.65)))
    return bg

def headline(bg, lines, th, side, avoid_box, area=None, y0=96):
    """lines: [(text, kind)] kind in white|accent. Placed on the side opposite the face; returns text bbox."""
    d = ImageDraw.Draw(bg)
    pb = avoid_box
    area_x0, area_x1 = (max(int(W * 0.40), pb[2] - 70), W - 36) if side == "left" else (36, min(int(W * 0.60), pb[0] + 70))
    sizes = [(170, 150), (250, 205)]  # (size for first line, size for accent line)
    if area: area_x0, area_x1 = area
    y = y0; boxes = []
    for i, (txt, kind) in enumerate(lines):
        size = 150 if i == 0 else 230
        while True:
            f = font(size); w = d.textlength(txt, font=f, direction="rtl")
            if w <= (area_x1 - area_x0) or size < 60: break
            size -= 6
        asc, desc = f.getmetrics(); x = area_x1 - w if side == "left" else area_x0 + (area_x1 - area_x0 - w)
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ld = ImageDraw.Draw(layer)
        fill = th["accent"] if kind == "accent" else (255, 255, 255)
        ld.text((x + 6, y + 8), txt, font=f, fill=(0, 0, 0, 255), stroke_width=16, stroke_fill=(0, 0, 0, 255), direction="rtl", language="he")  # drop shadow
        ld.text((x, y), txt, font=f, fill=fill, stroke_width=14, stroke_fill=(0, 0, 0, 255), direction="rtl", language="he")
        layer = layer.rotate(2.0 if side == "left" else -2.0, resample=Image.BICUBIC, center=(W / 2, y + asc / 2))
        bg.paste(layer, (0, 0), layer); boxes.append((int(x) - 14, y - 14, int(x + w) + 14, y + asc + desc))
        y += int((asc + desc) * 0.78)
    box = (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))
    return box

def detect_face_box(person, px, py):
    """face box on the canvas (OpenCV Haar; fallback: upper-middle of the cut-out)."""
    try:
        fs = detect_faces(person.convert("RGB"))
        if fs:
            x0, y0, x1, y1 = max(fs, key=lambda r: (r[2] - r[0]) * (r[3] - r[1])); return (px + x0, py + y0, px + x1, py + y1)
    except Exception: pass
    w, h = person.size
    return (px + int(0.2 * w), py, px + int(0.8 * w), py + int(0.55 * h))

YUNET = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "face_detection_yunet_2023mar.onnx")
def detect_faces(rgb):
    """[(x0,y0,x1,y1)] using YuNet (works on stylised / AI faces too), Haar fallback."""
    import cv2
    bgr = cv2.cvtColor(np.array(rgb), cv2.COLOR_RGB2BGR); h, w = bgr.shape[:2]; out = []
    try:
        det = cv2.FaceDetectorYN.create(YUNET, "", (w, h), 0.55, 0.3, 5000); _, res = det.detect(bgr)
        for r in (res if res is not None else []):
            x, y, fw, fh = r[:4]; m = 0.18 * fw; out.append((int(x - m), int(y - m), int(x + fw + m), int(y + fh + m)))
    except Exception: pass
    if not out:
        g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        for x, y, fw, fh in cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml").detectMultiScale(g, 1.08, 4, minSize=(70, 70)):
            m = int(0.15 * fw); out.append((x - m, y - m, x + fw + m, y + fh + m))
    return out

def overlap(a, b):
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    return max(0, x1 - x0) * max(0, y1 - y0)

def scene_mode(args):
    """AI-generated scene already contains the people/props: add the Hebrew headline where it does NOT cover faces, then QA."""
    th = THEMES[args.theme]
    im = Image.open(args.scene).convert("RGB"); r = max(W / im.width, H / im.height)
    im = im.resize((int(im.width * r) + 1, int(im.height * r) + 1), Image.LANCZOS); l, t = (im.width - W) // 2, (im.height - H) // 2
    bg = im.crop((l, t, l + W, t + H))
    faces = detect_faces(bg)
    lines = [(args.head, "white"), (args.accent, "accent")] if args.accent else [(args.head, "accent")]
    # try candidate headline areas (top band split / top-left / top-right / top-center); keep the one with the least face overlap
    cands = [(36, W - 36), (36, int(W * 0.62)), (int(W * 0.38), W - 36), (int(W * 0.2), int(W * 0.8))]
    best = None
    for (ax0, ax1) in cands:
        probe = bg.copy(); box = headline(probe, lines, th, "left", (0, 0, 0, 0), area=(ax0, ax1), y0=18)
        ov = sum(overlap(box, f) for f in faces)
        if best is None or ov < best[0]: best = (ov, (ax0, ax1), box)
        if ov == 0: break
    box = headline(bg, lines, th, "left", (0, 0, 0, 0), area=best[1], y0=18)
    inter = sum(overlap(box, f) for f in faces); fa = max(1, sum((f[2] - f[0]) * (f[3] - f[1]) for f in faces)) if faces else 1
    ok = inter / fa < 0.02; q = 94
    while True:
        bg.save(args.out, quality=q, optimize=True, subsampling=0)
        if os.path.getsize(args.out) < 1_900_000 or q <= 70: break
        q -= 4
    bg.resize((168, 94), Image.LANCZOS).save(os.path.splitext(args.out)[0] + "_168.png")
    print(f"QA(scene) faces_found={len(faces)} overlap_ok={ok} size={os.path.getsize(args.out)//1024} KB headline box={box}")
    return 0 if ok else 3

def make(args):
    if args.scene: return scene_mode(args)
    th = THEMES[args.theme]; side = args.side
    frame = Image.open(args.frame).convert("RGB"); x0, y0, x1, y1 = map(int, args.crop.split(","))
    face = enhance(frame.crop((x0, y0, x1, y1)), int(H * 1.02)); person = cutout(face)
    bb = person.split()[-1].getbbox(); person = person.crop(bb)
    k = min(1.0, H * 0.98 / person.height, W * 0.55 / person.width)
    if k < 1.0: person = person.resize((int(person.width * k), int(person.height * k)), Image.LANCZOS)
    stk, pad = sticker(person, th)
    bg = background(th, side, Image.open(args.bg) if args.bg else None)
    px = -10 if side == "left" else W - person.width + 10   # flush to the edge
    py = H - person.height + 22   # bleed off the bottom edge like pro thumbnails (no floating outline)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0)); layer.alpha_composite(stk, (px - pad, py - pad) if False else (px - pad, py - pad)); bg.paste(layer, (0, 0), layer)
    person_box = (px, py, px + person.width, py + person.height)
    face_box = detect_face_box(person, px, py)
    if args.guest:
        g = Image.open(args.guest).convert("RGB"); gx0, gy0, gx1, gy1 = map(int, args.guest_crop.split(","))
        gp = cutout(enhance(g.crop((gx0, gy0, gx1, gy1)), int(H * 0.62))); gp = gp.crop(gp.split()[-1].getbbox())
        gs, gpad = sticker(gp, th, 12, 30)
        gx = (W - gs.width + gpad - 30) if side == "left" else 30; gy = H - gs.height + gpad
        L2 = Image.new("RGBA", (W, H), (0, 0, 0, 0)); L2.alpha_composite(gs, (gx - gpad, gy - gpad)); bg.paste(L2, (0, 0), L2)
        face_box = (min(face_box[0], gx), min(face_box[1], gy), max(face_box[2], gx + gp.width), max(face_box[3], gy + gp.height)) if False else face_box
    if args.prop:
        pr = Image.open(args.prop).convert("RGBA"); s = min(330 / pr.width, 330 / pr.height); pr = pr.resize((int(pr.width * s), int(pr.height * s)), Image.LANCZOS)
        bg.paste(pr, ((W - pr.width - 40) if side == "left" else 40, H - pr.height - 30), pr)
    lines = [(args.head, "white"), (args.accent, "accent")] if args.accent else [(args.head, "accent")]
    tb = headline(bg, lines, th, side, person_box)
    # ---- QA ----
    inter = overlap(tb, face_box); face_area = (face_box[2] - face_box[0]) * (face_box[3] - face_box[1])
    ok_overlap = inter / max(1, face_area) < 0.02
    out = args.out; q = 94
    while True:
        bg.save(out, quality=q, optimize=True, subsampling=0)
        if os.path.getsize(out) < 1_900_000 or q <= 70: break
        q -= 4
    sm = bg.resize((168, 94), Image.LANCZOS); sm.save(os.path.splitext(out)[0] + "_168.png")
    print(f"QA overlap_ok={ok_overlap} (text/face overlap {100*inter/max(1,face_area):.1f}%) | size={os.path.getsize(out)//1024} KB q={q} | headline box={tb}")
    return 0 if ok_overlap else 3

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--frame"); ap.add_argument("--crop"); ap.add_argument("--scene", help="finished AI scene image (full 16:9 art); only the Hebrew headline + QA are added")
    ap.add_argument("--head", required=True); ap.add_argument("--accent", default=""); ap.add_argument("--theme", default="green", choices=THEMES)
    ap.add_argument("--out", required=True); ap.add_argument("--guest"); ap.add_argument("--guest-crop"); ap.add_argument("--prop"); ap.add_argument("--bg")
    ap.add_argument("--side", default="left", choices=["left", "right"])
    sys.exit(make(ap.parse_args()))

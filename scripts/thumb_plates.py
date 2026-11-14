#!/usr/bin/env python3
"""Procedural stylised scene plates (no people) for thumbnails: night_city, neon_sunset. Fallback when no AI plate is available.
usage: thumb_plates.py --scene night_city --out plate.jpg"""
import argparse, math, random
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageChops
W, H = 1280, 720

def grad(top, bot, h=H):
    a = np.zeros((h, W, 3), np.float32)
    for y in range(h): t = y / (h - 1); a[y, :, :] = [top[i] * (1 - t) + bot[i] * t for i in range(3)]
    return Image.fromarray(a.astype(np.uint8))

def skyline(seed, base_y, hmin, hmax, color, win=(255, 210, 120), density=0.35, wide=(40, 110)):
    random.seed(seed); L = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(L); x = -20
    while x < W + 20:
        w = random.randint(*wide); h = random.randint(hmin, hmax); d.rectangle((x, base_y - h, x + w, base_y), fill=color + (255,))
        for wy in range(base_y - h + 10, base_y - 8, 16):
            for wx in range(x + 8, x + w - 8, 14):
                if random.random() < density: d.rectangle((wx, wy, wx + 5, wy + 8), fill=win + (random.randint(120, 255),))
        x += w + random.randint(0, 6)
    return L

def glow(layer_fn, blur, strength=1.0):
    g = Image.new("RGB", (W, H), (0, 0, 0)); layer_fn(ImageDraw.Draw(g)); g = g.filter(ImageFilter.GaussianBlur(blur)); return g.point(lambda v: min(255, int(v * strength)))

def night_city(seed=2):
    random.seed(seed); hz = 430
    img = grad((18, 10, 46), (255, 110, 50), hz).convert("RGB"); canvas = Image.new("RGB", (W, H), (10, 8, 20)); canvas.paste(img, (0, 0))
    far = skyline(1, hz, 120, 300, (60, 36, 100), (255, 170, 110), 0.22, (50, 120)).filter(ImageFilter.GaussianBlur(2.5))
    near = skyline(7, hz + 10, 90, 360, (16, 12, 36), (255, 210, 120), 0.30, (40, 100))
    c = canvas.convert("RGBA"); c.alpha_composite(far); c.alpha_composite(near); canvas = c.convert("RGB")
    def neon(d):
        for (x, y, w, h, col) in [(820, 220, 220, 22, (255, 40, 160)), (1010, 300, 14, 130, (0, 230, 255)), (700, 330, 160, 18, (255, 220, 40)), (1130, 200, 90, 16, (0, 255, 160)), (900, 380, 120, 14, (255, 70, 90))]:
            d.rectangle((x, y, x + w, y + h), fill=col)
    canvas = ImageChops.add(canvas, glow(neon, 22, 1.5)); canvas = ImageChops.add(canvas, glow(neon, 6, 0.8))
    # wet street: mirrored reflection with fade + car-light streaks
    top = canvas.crop((0, 0, W, hz)); refl = top.transpose(Image.FLIP_TOP_BOTTOM).resize((W, H - hz)).filter(ImageFilter.GaussianBlur(7))
    fade = Image.new("L", (W, H - hz), 0); fd = ImageDraw.Draw(fade)
    for y in range(H - hz): fd.line([(0, y), (W, y)], fill=int(185 * (1 - y / (H - hz)) ** 1.2))
    street = Image.new("RGB", (W, H - hz), (12, 10, 24)); street.paste(refl, (0, 0), fade); canvas.paste(street, (0, hz))
    def streaks(d):
        for _ in range(26):
            y = random.randint(hz + 18, H - 16); x = random.randint(380, 1260); l = random.randint(120, 380); col = random.choice([(255, 60, 60), (255, 190, 80), (255, 255, 255), (0, 200, 255)])
            d.line([(x, y), (x + l, y + random.randint(-3, 3))], fill=col, width=random.randint(2, 5))
    canvas = ImageChops.add(canvas, glow(streaks, 3, 1.3))
    def bokeh(d):
        for _ in range(34):
            x = random.randint(430, 1270); y = random.randint(40, 560); r = random.randint(14, 54); col = random.choice([(255, 90, 160), (0, 210, 255), (255, 190, 60), (170, 90, 255)])
            d.ellipse((x - r, y - r, x + r, y + r), fill=tuple(int(v * 0.22) for v in col))
    canvas = ImageChops.add(canvas, glow(bokeh, 5, 1.0))
    canvas = canvas.filter(ImageFilter.GaussianBlur(1.6))
    return canvas

def neon_sunset(seed=4):
    random.seed(seed); hz = 470
    img = Image.new("RGB", (W, H)); a = np.zeros((hz, W, 3), np.float32)
    stops = [(0, (40, 20, 110)), (0.45, (210, 60, 160)), (0.8, (255, 140, 90)), (1.0, (255, 210, 120))]
    for y in range(hz):
        t = y / (hz - 1)
        for i in range(len(stops) - 1):
            if stops[i][0] <= t <= stops[i + 1][0]:
                u = (t - stops[i][0]) / (stops[i + 1][0] - stops[i][0]); a[y, :, :] = [stops[i][1][k] * (1 - u) + stops[i + 1][1][k] * u for k in range(3)]
    img.paste(Image.fromarray(a.astype(np.uint8)), (0, 0)); d = ImageDraw.Draw(img)
    img.paste(Image.new("RGB", (W, H - hz), (30, 16, 60)), (0, hz))
    def sun(g): g.ellipse((800, hz - 190, 1100, hz + 110), fill=(255, 220, 160))
    img = ImageChops.add(img, glow(sun, 60, 0.9)); ImageDraw.Draw(img).ellipse((830, hz - 160, 1070, hz + 80), fill=(255, 238, 200))
    c = img.convert("RGBA"); c.alpha_composite(skyline(3, hz, 60, 220, (70, 30, 100), (255, 190, 140), 0.2, (50, 110)).filter(ImageFilter.GaussianBlur(1.5)))
    L = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ld = ImageDraw.Draw(L)
    for px, ph in [(640, 440), (1000, 380), (1180, 470), (560, 300)]:    # palm silhouettes
        ld.polygon([(px - 7, hz + 20), (px + 7, hz + 20), (px + 4, hz - ph), (px - 4, hz - ph)], fill=(18, 8, 34, 255))
        for k in range(9):
            ang = math.radians(-170 + k * 20); ex = px + math.cos(ang) * 130; ey = hz - ph + math.sin(ang) * 80 + 30
            ld.polygon([(px, hz - ph), (px + math.cos(ang) * 65, hz - ph + math.sin(ang) * 40 - 16), (ex, ey), (px + math.cos(ang) * 65, hz - ph + math.sin(ang) * 40 + 12)], fill=(18, 8, 34, 255))
    c.alpha_composite(L); out = c.convert("RGB")
    return out.filter(ImageFilter.GaussianBlur(1.2))

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--scene", default="night_city", choices=["night_city", "neon_sunset"]); ap.add_argument("--out", required=True)
    a = ap.parse_args(); (night_city() if a.scene == "night_city" else neon_sunset()).save(a.out, quality=93); print("saved", a.out)

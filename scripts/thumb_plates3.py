#!/usr/bin/env python3
"""High-detail plates v3 (built ourselves from what the reference thumbnails show: elements, lighting, layout; no file is copied).
Drawn at 2x supersampling. Left ~45% stays calm/darker for the portrait. usage: thumb_plates3.py --scene jewellery_store --out p.jpg | --all --outdir assets/plates3"""
import argparse, math, os, random
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageChops, ImageFont
W, H, S = 1280, 720, 2
FONT = "/usr/share/fonts/truetype/sand-box/google/Heebo/Heebo-VariableFont_wght.ttf"

class C:
    def __init__(s, bg=(0, 0, 0)): s.im = Image.new("RGB", (W * S, H * S), bg); s.d = ImageDraw.Draw(s.im)
    def p(s, pts): return [(x * S, y * S) for x, y in pts]
    def poly(s, pts, fill, outline=None, w=1): s.d.polygon(s.p(pts), fill=fill, outline=outline, width=w * S if outline else 0)
    def rect(s, b, fill, outline=None, w=1): s.d.rectangle([b[0] * S, b[1] * S, b[2] * S, b[3] * S], fill=fill, outline=outline, width=w * S if outline else 0)
    def ell(s, b, fill, outline=None, w=1): s.d.ellipse([b[0] * S, b[1] * S, b[2] * S, b[3] * S], fill=fill, outline=outline, width=w * S if outline else 0)
    def line(s, pts, fill, w=1): s.d.line(s.p(pts), fill=fill, width=max(1, int(w * S)))
    def vgrad(s, y0, y1, top, bot, x0=0, x1=W):
        a = np.zeros(((y1 - y0) * S, (x1 - x0) * S, 3), np.float32)
        for i in range((y1 - y0) * S): t = i / max(1, (y1 - y0) * S - 1); a[i, :, :] = [top[k] * (1 - t) + bot[k] * t for k in range(3)]
        s.im.paste(Image.fromarray(a.astype(np.uint8)), (x0 * S, y0 * S))
        s.d = ImageDraw.Draw(s.im)
    def final(s): return s.im.resize((W, H), Image.LANCZOS)

def glow_layer(draw_fn, blur, k=1.0):
    c = C((0, 0, 0)); draw_fn(c); g = c.final().filter(ImageFilter.GaussianBlur(blur)); return g.point(lambda v: min(255, int(v * k)))
def add(a, b): return ImageChops.add(a, b)
def blob(col, box, blur, k=1.0):
    g = Image.new("RGB", (W, H), (0, 0, 0)); ImageDraw.Draw(g).ellipse(box, fill=col); return g.filter(ImageFilter.GaussianBlur(blur)).point(lambda v: int(v * k))
def split(img, warm, cool, kw=0.6, kc=0.6):
    return add(add(img, blob(warm, (-320, 60, 620, 900), 150, kw)), blob(cool, (640, -200, 1580, 680), 150, kc))
def left_dark(img, st=0.55):
    g = Image.new("L", (W, H), 0); d = ImageDraw.Draw(g)
    for x in range(W): d.line([(x, 0), (x, H)], fill=int(255 * st * max(0.0, 1 - x / (W * 0.5)) ** 1.2))
    return Image.composite(Image.new("RGB", (W, H), (5, 4, 10)), img, g)
def vignette(img, k=0.55):
    g = Image.new("L", (W, H), 0); ImageDraw.Draw(g).ellipse((-W * .25, -H * .3, W * 1.25, H * 1.3), fill=255); g = g.filter(ImageFilter.GaussianBlur(170))
    return Image.composite(img, Image.new("RGB", (W, H), (0, 0, 0)), g.point(lambda v: int(255 * (1 - k) + v * k)))
def bokeh(img, cols, pts, k=0.3, blur=5):
    g = Image.new("RGB", (W, H), (0, 0, 0)); d = ImageDraw.Draw(g)
    for (x, y, r, ci) in pts: d.ellipse((x - r, y - r, x + r, y + r), fill=tuple(int(v * k) for v in cols[ci % len(cols)]))
    return add(img, g.filter(ImageFilter.GaussianBlur(blur)))
def rays(img, origin, angles, length, col, k=0.5, blur=14):
    g = Image.new("RGB", (W, H), (0, 0, 0)); d = ImageDraw.Draw(g)
    for a0, a1 in angles:
        d.polygon([origin, (origin[0] + length * math.cos(math.radians(a0)), origin[1] + length * math.sin(math.radians(a0))), (origin[0] + length * math.cos(math.radians(a1)), origin[1] + length * math.sin(math.radians(a1)))], fill=col)
    return add(img, g.filter(ImageFilter.GaussianBlur(blur)).point(lambda v: int(v * k)))
def reflect_floor(img, hz, fade=0.55, blur=7):
    top = img.crop((0, 0, W, hz)); r = top.transpose(Image.FLIP_TOP_BOTTOM).resize((W, H - hz)).filter(ImageFilter.GaussianBlur(blur))
    m = Image.new("L", (W, H - hz), 0); d = ImageDraw.Draw(m)
    for y in range(H - hz): d.line([(0, y), (W, y)], fill=int(255 * fade * (1 - y / (H - hz)) ** 1.25))
    out = img.copy(); base = out.crop((0, hz, W, H)); base.paste(r, (0, 0), m); out.paste(base, (0, hz)); return out

# ============ 1. JEWELLERY STORE (heist) ============
def jewellery_store(seed=1):
    rnd = random.Random(seed); c = C((10, 10, 22)); hz = 470
    c.vgrad(0, hz, (6, 7, 18), (14, 14, 32)); c.vgrad(hz, H, (22, 20, 38), (5, 5, 12))
    # floor perspective lines (glossy tiles)
    vp = (900, hz - 60)
    for i in range(-10, 22):
        x = vp[0] + (i - 6) * 150; c.line([(vp[0], vp[1] + 55), (x, H + 30)], (46, 44, 76), 1.5)
    for k in range(1, 7): y = hz + (k ** 1.7) * 9; c.line([(0, y), (W, y)], (44, 42, 72), 1.2)
    # back wall panels
    for x in range(380, W, 140): c.rect((x, 70, x + 128, hz - 10), (10, 12, 28), (24, 28, 56), 2)
    # gold sign
    c.rect((820, 62, 1180, 128), (24, 16, 6), (255, 200, 80), 5)
    f = ImageFont.truetype(FONT, 46 * S); 
    try: f.set_variation_by_name("Black")
    except Exception: pass
    c.d.text((1000 * S, 95 * S), "JEWELRY", font=f, fill=(255, 214, 96), anchor="mm")
    # display cabinets (glass, glowing interior, jewellery)
    def cabinet(x, w, y0, y1, hue):
        c.rect((x, y0, x + w, y1), (8, 14, 34), (120, 160, 220), 3)
        c.rect((x + 6, y0 + 6, x + w - 6, y1 - 6), (6, 10, 26))
        for sh in range(1, 4): c.line([(x + 6, y0 + sh * (y1 - y0) // 4), (x + w - 6, y0 + sh * (y1 - y0) // 4)], (120, 170, 240), 2)
        for sh in range(4):
            yy = y0 + 14 + sh * (y1 - y0) // 4
            for k in range(3):
                gx = x + 22 + k * (w - 44) // 2 + rnd.randint(-5, 5); gy = yy + 26
                col = rnd.choice([(210, 245, 255), (255, 255, 255), (255, 150, 200), (140, 255, 210), (255, 215, 90)])
                c.poly([(gx, gy - 18), (gx + 15, gy - 4), (gx, gy + 14), (gx - 15, gy - 4)], col, (255, 255, 255), 1)
                c.line([(gx - 15, gy - 4), (gx + 15, gy - 4)], (255, 255, 255), 1); c.line([(gx, gy - 18), (gx - 6, gy - 4), (gx, gy + 14)], (255, 255, 255), 1)
        c.poly([(x + 10, y0 + 8), (x + 40, y0 + 8), (x + 8, y0 + 70)], (200, 230, 255)) if False else None
    for i, x in enumerate((420, 600, 780)): cabinet(x, 150, 250, 470, i)
    c.rect((400, 468, 960, 512), (30, 24, 56), (90, 80, 150), 3)                                  # counter
    img0 = c.final()
    # big shop window on the right with a shattered hole + night street + police lights
    c2 = C((0, 0, 0)); c2.rect((960, 150, 1270, 470), (10, 12, 34), (170, 200, 255), 6)
    win = c2.final()
    img = img0.copy(); sw = Image.new("RGB", (W, H), (10, 12, 34)); sd = ImageDraw.Draw(sw)
    sd.rectangle((960, 150, 1270, 470), fill=(18, 14, 44))
    for i in range(5): x = 975 + i * 62; sd.rectangle((x, 300 - rnd.randint(0, 90), x + 40, 470), fill=(30, 26, 62))     # street buildings
    car = Image.new("RGB", (W, H), (0, 0, 0)); cd = ImageDraw.Draw(car)
    cd.rounded_rectangle((1010, 400, 1160, 450), 12, fill=(40, 44, 70)); cd.rectangle((1040, 380, 1130, 405), fill=(50, 56, 90))
    cd.ellipse((1030, 330, 1080, 380), fill=(255, 40, 50)); cd.ellipse((1090, 330, 1140, 380), fill=(40, 100, 255))
    sw = add(sw, car.filter(ImageFilter.GaussianBlur(1))); mask = Image.new("L", (W, H), 0); ImageDraw.Draw(mask).rectangle((960, 150, 1270, 470), fill=255); img.paste(sw, (0, 0), mask)
    pol = Image.new("RGB", (W, H), (0, 0, 0)); pd = ImageDraw.Draw(pol); pd.ellipse((1015, 335, 1075, 375), fill=(255, 40, 50)); pd.ellipse((1095, 335, 1155, 375), fill=(40, 100, 255))
    img = add(img, pol.filter(ImageFilter.GaussianBlur(34)).point(lambda v: min(255, int(v * 1.6))))
    c3 = C((0, 0, 0)); c3.rect((960, 150, 1270, 470), (0, 0, 0), (170, 200, 255), 6)                    # frame + shards radiating from a hole
    hole = (1110, 300)
    for i in range(34):
        a = math.radians(i * 360 / 34 + rnd.randint(-4, 4)); l = rnd.randint(70, 220); c3.line([hole, (hole[0] + l * math.cos(a), hole[1] + l * math.sin(a))], (230, 245, 255), 2)
    for r in (40, 85, 135):
        pts = [(hole[0] + (r + rnd.randint(-10, 10)) * math.cos(math.radians(a)), hole[1] + (r + rnd.randint(-10, 10)) * math.sin(math.radians(a))) for a in range(0, 360, 20)]
        c3.d.polygon(c3.p(pts), outline=(220, 238, 255), width=2 * S)
    c3.poly([(hole[0] - 18, hole[1] - 22), (hole[0] + 24, hole[1] - 10), (hole[0] + 14, hole[1] + 26), (hole[0] - 22, hole[1] + 12)], (6, 8, 24))
    sh = c3.final(); sm = sh.convert("L").point(lambda v: 255 if v > 24 else 0); sh_glow = sh.filter(ImageFilter.GaussianBlur(3))
    img.paste(sh, (0, 0), sm); img = add(img, sh_glow.point(lambda v: int(v * 0.5)))
    # flying glass pieces in the foreground (bokeh sharp)
    fg = C((0, 0, 0))
    for _ in range(26):
        x = rnd.randint(640, 1270); y = rnd.randint(300, 650); s0 = rnd.randint(8, 26); a = rnd.random() * 6.28
        fg.poly([(x, y), (x + s0 * math.cos(a), y + s0 * math.sin(a)), (x + s0 * 0.5 * math.cos(a + 2), y + s0 * 0.7 * math.sin(a + 2))], (220, 240, 255), (255, 255, 255), 1)
    f2 = fg.final(); fm = f2.convert("L").point(lambda v: 150 if v > 30 else 0); img.paste(f2, (0, 0), fm)
    # ceiling spotlights cones
    img = rays(img, (560, 0), [(78, 84), (86, 92)], 560, (255, 240, 200), 0.18, 22); img = rays(img, (760, 0), [(88, 94)], 560, (255, 240, 200), 0.14, 22)
    gl = Image.new('RGB', (W, H), (0, 0, 0)); gd = ImageDraw.Draw(gl)
    for x in (420, 600, 780): gd.rectangle((x + 10, 258, x + 140, 462), fill=(70, 120, 200))
    img = add(img, gl.filter(ImageFilter.GaussianBlur(30)).point(lambda v: int(v * 0.8)))
    img = reflect_floor(img, hz + 40, 0.42)
    img = split(img, (255, 40, 50), (40, 100, 255), 0.30, 0.34)
    img = bokeh(img, [(255, 50, 60), (50, 110, 255)], [(rnd.randint(640, 1270), rnd.randint(480, 700), rnd.randint(14, 34), i) for i in range(16)], 0.35)
    return vignette(left_dark(img, 0.5)).filter(ImageFilter.GaussianBlur(0.8))

# ============ 2. LAW OFFICE ============
def law_office(seed=2):
    rnd = random.Random(seed); c = C((26, 14, 8)); hz = 560
    c.vgrad(0, hz, (34, 18, 10), (74, 40, 20)); c.vgrad(hz, H, (60, 32, 16), (20, 10, 6))
    # perspective bookshelves wall
    for bay in range(7):
        x = 400 + bay * 125; c.rect((x, 40, x + 118, 536), (50, 28, 14), (26, 14, 6), 4)
        for row in range(6):
            y = 52 + row * 80; bx = x + 8
            while bx < x + 108:
                bw = rnd.randint(8, 18); bh = rnd.randint(52, 72); col = rnd.choice([(130, 28, 30), (24, 60, 104), (36, 88, 50), (156, 112, 38), (86, 40, 100), (200, 190, 150)])
                c.rect((bx, y + 74 - bh, bx + bw, y + 74), col, (20, 10, 6), 1); c.line([(bx + 2, y + 74 - bh + 6), (bx + bw - 2, y + 74 - bh + 6)], (230, 200, 120), 1); bx += bw + 1
            c.rect((x + 4, y + 74, x + 114, y + 80), (34, 18, 8))
    # window blinds light stripes (cinematic) over the right part
    img = c.final(); st = Image.new("RGB", (W, H), (0, 0, 0)); sd = ImageDraw.Draw(st)
    for i in range(16): y0 = 40 + i * 34; sd.polygon([(700, y0), (1280, y0 + 90), (1280, y0 + 112), (700, y0 + 22)], fill=(255, 200, 120))
    img = add(img, st.filter(ImageFilter.GaussianBlur(6)).point(lambda v: int(v * 0.30)))
    c = C((0, 0, 0))
    # desk
    c.poly([(700, 520), (1280, 500), (1280, 560), (680, 580)], (96, 52, 22), (50, 26, 10), 3); c.rect((720, 580, 770, 720), (62, 34, 14)); c.rect((1190, 560, 1240, 720), (62, 34, 14))
    # brass scales of justice
    cx, top = 1010, 210
    c.rect((cx - 8, top + 20, cx + 8, 480), (230, 180, 60), (140, 100, 20), 2); c.ell((cx - 40, 470, cx + 40, 500), (230, 180, 60), (140, 100, 20), 2); c.ell((cx - 14, top - 8, cx + 14, top + 20), (255, 215, 100))
    c.line([(cx - 150, top + 70), (cx + 150, top + 60)], (240, 190, 70), 8)
    for sx, sy in ((cx - 150, top + 70), (cx + 150, top + 60)):
        c.line([(sx, sy), (sx - 55, sy + 130)], (240, 190, 70), 3); c.line([(sx, sy), (sx + 55, sy + 130)], (240, 190, 70), 3)
        c.poly([(sx - 70, sy + 130), (sx + 70, sy + 130), (sx + 52, sy + 150), (sx - 52, sy + 150)], (255, 214, 100), (150, 105, 20), 2)
    # banker lamp
    c.poly([(1150, 440), (1230, 440), (1215, 400), (1165, 400)], (20, 110, 70), (10, 60, 40), 2); c.rect((1186, 440, 1194, 508), (210, 160, 50))
    # framed diploma
    c.rect((820, 90, 960, 170), (230, 220, 190), (90, 50, 20), 6); c.line([(840, 120), (940, 120)], (80, 60, 40), 2); c.line([(840, 140), (920, 140)], (80, 60, 40), 2)
    fg = c.final(); m = fg.convert("L").point(lambda v: 255 if v > 4 else 0); img.paste(fg, (0, 0), m)
    lamp = Image.new("RGB", (W, H), (0, 0, 0)); ImageDraw.Draw(lamp).ellipse((1120, 400, 1260, 470), fill=(255, 190, 80)); img = add(img, lamp.filter(ImageFilter.GaussianBlur(40)).point(lambda v: min(255, int(v * 1.6))))
    img = split(img, (255, 140, 40), (50, 100, 190), 0.65, 0.30)
    img = bokeh(img, [(255, 200, 110)], [(rnd.randint(500, 1270), rnd.randint(40, 300), rnd.randint(10, 28), 0) for i in range(10)], 0.22)
    return vignette(left_dark(img, 0.55)).filter(ImageFilter.GaussianBlur(0.8))

# ============ 3. AIRPORT ============
def airport(seed=3):
    rnd = random.Random(seed); c = C((120, 160, 220)); hz = 470
    c.vgrad(0, 330, (90, 140, 235), (255, 206, 150))                                 # sky -> sunset horizon
    c.rect((0, 330, W, hz), (150, 150, 170))                                          # apron
    c.line([(0, 345), (W, 345)], (210, 190, 160), 3)
    # airplane on the apron (more detailed)
    c.poly([(780, 395), (1180, 372), (1230, 384), (1236, 398), (1180, 410), (860, 420)], (240, 244, 250), (170, 176, 190), 2)
    c.poly([(1170, 374), (1236, 330), (1250, 336), (1218, 384)], (226, 40, 50))        # tail
    c.poly([(960, 400), (1040, 440), (1010, 442), (930, 410)], (205, 210, 224))        # wing
    for k in range(9): c.ell((900 + k * 30, 388 - k * 1.2, 910 + k * 30, 396 - k * 1.2), (60, 90, 150))
    # terminal glass wall with mullions
    for x in range(380, W + 90, 120): c.rect((x, 30, x + 10, hz), (62, 70, 94))
    for y in (150, 280): c.rect((380, y, W, y + 8), (62, 70, 94))
    c.rect((380, 22, W, 40), (44, 50, 70))
    # departures board
    c.rect((730, 40, 1250, 150), (10, 12, 26), (90, 100, 150), 4)
    f = ImageFont.truetype(FONT, 17 * S)
    rows = [("TLV  NEW YORK", "18:40", (255, 200, 60)), ("TLV  LONDON", "19:05", (110, 220, 255)), ("TLV  PARIS", "19:30", (255, 200, 60)), ("TLV  ROME", "20:10", (110, 220, 255))]
    for i, (t, tm, col) in enumerate(rows): c.d.text((750 * S, (62 + i * 22) * S), t, font=f, fill=col, anchor="lm"); c.d.text((1230 * S, (62 + i * 22) * S), tm, font=f, fill=col, anchor="rm")
    # polished floor with perspective & check-in desks
    c.vgrad(hz, H, (150, 150, 176), (70, 70, 98))
    vp = (860, hz - 20)
    for i in range(-8, 20): c.line([(vp[0], vp[1] + 20), (vp[0] + (i - 5) * 170, H + 20)], (126, 126, 156), 2)
    for k in range(1, 8): y = hz + (k ** 1.6) * 8; c.line([(0, y), (W, y)], (122, 122, 150), 1.5)
    for x in (470, 700): c.rect((x, 400, x + 150, 480), (50, 58, 90), (30, 34, 56), 3); c.rect((x + 8, 408, x + 142, 424), (90, 200, 255))
    img = c.final()
    sun = Image.new("RGB", (W, H), (0, 0, 0)); ImageDraw.Draw(sun).ellipse((1050, 250, 1170, 370), fill=(255, 220, 150)); img = add(img, sun.filter(ImageFilter.GaussianBlur(46)).point(lambda v: min(255, int(v * 1.3))))
    img = rays(img, (1110, 310), [(150, 156), (160, 166), (170, 176), (180, 186)], 900, (255, 210, 140), 0.22, 18)
    img = reflect_floor(img, hz, 0.35)
    img = split(img, (255, 180, 90), (70, 130, 255), 0.45, 0.30)
    img = bokeh(img, [(255, 220, 150), (140, 190, 255)], [(rnd.randint(420, 1270), rnd.randint(480, 700), rnd.randint(12, 30), i) for i in range(14)], 0.2)
    return vignette(left_dark(img, 0.42), 0.45).filter(ImageFilter.GaussianBlur(0.7))

SCENES = {"jewellery_store": jewellery_store, "law_office": law_office, "airport": airport}
if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--all", action="store_true"); ap.add_argument("--scene", choices=SCENES); ap.add_argument("--out"); ap.add_argument("--outdir", default="assets/plates3"); a = ap.parse_args()
    if a.all:
        os.makedirs(a.outdir, exist_ok=True)
        for k, f in SCENES.items(): f().save(os.path.join(a.outdir, k + ".jpg"), quality=93); print("saved", k, flush=True)
    else: SCENES[a.scene]().save(a.out, quality=93)

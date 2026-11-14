#!/usr/bin/env python3
"""Plate library: 16 stylised scene backgrounds (no people) following the rules learned from the 35 reference thumbnails:
literal topic environment, split warm/cool lighting, dark calm LEFT side for the portrait, props that repeat the topic on the right, glow, bokeh, depth.
usage: thumb_plates2.py --all --outdir assets/plates     or    --scene law_office --out p.jpg"""
import argparse, math, os, random
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageChops
W, H = 1280, 720

def lin(top, bot, y0=0, y1=H):
    a = np.zeros((H, W, 3), np.float32)
    for y in range(H):
        t = min(1, max(0, (y - y0) / max(1, y1 - y0))); a[y, :, :] = [top[i] * (1 - t) + bot[i] * t for i in range(3)]
    return Image.fromarray(a.astype(np.uint8))

def blob(col, box, blur, k=1.0):
    g = Image.new("RGB", (W, H), (0, 0, 0)); ImageDraw.Draw(g).ellipse(box, fill=col); return g.filter(ImageFilter.GaussianBlur(blur)).point(lambda v: int(v * k))

def split_light(img, warm, cool, kw=0.8, kc=0.7):
    img = ImageChops.add(img, blob(warm, (-300, 40, 640, 900), 140, kw)); return ImageChops.add(img, blob(cool, (620, -160, 1560, 700), 140, kc))

def darken_left(img, strength=0.62):
    g = Image.new("L", (W, H), 0); d = ImageDraw.Draw(g)
    for x in range(W): d.line([(x, 0), (x, H)], fill=int(255 * strength * max(0.0, 1 - x / (W * 0.52))))
    return Image.composite(Image.new("RGB", (W, H), (6, 5, 12)), img, g)

def bokeh(img, cols, n=26, rmin=10, rmax=44, region=(380, 20, 1270, 620), k=0.28, seed=1):
    rnd = random.Random(seed); g = Image.new("RGB", (W, H), (0, 0, 0)); d = ImageDraw.Draw(g)
    for _ in range(n):
        x = rnd.randint(region[0], region[2]); y = rnd.randint(region[1], region[3]); r = rnd.randint(rmin, rmax); c = rnd.choice(cols)
        d.ellipse((x - r, y - r, x + r, y + r), fill=tuple(int(v * k) for v in c))
    return ImageChops.add(img, g.filter(ImageFilter.GaussianBlur(4)))

def glow(img, fn, blur=18, k=1.2):
    g = Image.new("RGB", (W, H), (0, 0, 0)); fn(ImageDraw.Draw(g)); return ImageChops.add(img, g.filter(ImageFilter.GaussianBlur(blur)).point(lambda v: min(255, int(v * k))))

def finish(img, soft=1.4):
    return img.filter(ImageFilter.GaussianBlur(soft))

def floor_reflect(img, hz, fade=170):
    top = img.crop((0, 0, W, hz)); refl = top.transpose(Image.FLIP_TOP_BOTTOM).resize((W, H - hz)).filter(ImageFilter.GaussianBlur(8))
    m = Image.new("L", (W, H - hz), 0); d = ImageDraw.Draw(m)
    for y in range(H - hz): d.line([(0, y), (W, y)], fill=int(fade * (1 - y / (H - hz)) ** 1.3))
    fl = Image.new("RGB", (W, H - hz), (10, 8, 18)); fl.paste(refl, (0, 0), m); out = img.copy(); out.paste(fl, (0, hz)); return out

# ---------------- scenes ----------------
def law_office(s=1):
    img = lin((40, 24, 14), (90, 52, 24)); d = ImageDraw.Draw(img)
    for x in range(380, W, 150):                                   # bookshelves with books
        d.rectangle((x, 60, x + 138, 560), fill=(46, 26, 12), outline=(20, 10, 4), width=3)
        for row in range(5):
            y = 70 + row * 98; rnd = random.Random(x + row); bx = x + 8
            while bx < x + 128:
                bw = rnd.randint(9, 20); bh = rnd.randint(60, 86); col = rnd.choice([(120, 30, 30), (30, 70, 110), (40, 90, 50), (150, 110, 40), (80, 40, 100)])
                d.rectangle((bx, y + 90 - bh, bx + bw, y + 90), fill=col); bx += bw + 1
            d.line([(x + 4, y + 92), (x + 134, y + 92)], fill=(20, 10, 4), width=4)
    d.rectangle((0, 560, W, H), fill=(60, 32, 16))                 # desk / floor
    d.rectangle((760, 470, 1250, 500), fill=(95, 55, 25)); d.rectangle((790, 500, 830, 720), fill=(70, 40, 18)); d.rectangle((1180, 500, 1220, 720), fill=(70, 40, 18))
    def scales(dr):                                               # golden scales of justice
        cx = 1090; dr.rectangle((cx - 5, 250, cx + 5, 470), fill=(255, 200, 70)); dr.line([(cx - 130, 290), (cx + 130, 290)], fill=(255, 200, 70), width=8)
        for sx in (cx - 130, cx + 130): dr.line([(sx, 290), (sx - 45, 390)], fill=(255, 200, 70), width=4); dr.line([(sx, 290), (sx + 45, 390)], fill=(255, 200, 70), width=4); dr.ellipse((sx - 55, 380, sx + 55, 410), fill=(255, 200, 70))
    img = glow(img, scales, 6, 1.0); scales(ImageDraw.Draw(img))
    def lamp(dr): dr.ellipse((880, 330, 1000, 450), fill=(255, 190, 90))
    img = glow(img, lamp, 38, 1.4)
    img = split_light(img, (255, 150, 50), (60, 110, 200), 0.7, 0.35); img = bokeh(img, [(255, 200, 110)], 14, k=0.2)
    return finish(darken_left(img))

def jewellery_store(s=2):
    img = lin((14, 12, 28), (30, 22, 48)); d = ImageDraw.Draw(img)
    d.rectangle((0, 520, W, H), fill=(26, 22, 40))
    for i, x in enumerate(range(400, 1260, 215)):                  # glass display cabinets with gems
        d.rectangle((x, 250, x + 190, 540), fill=(40, 52, 88), outline=(150, 190, 255), width=4)
        d.rectangle((x + 10, 262, x + 180, 528), fill=(22, 30, 60))
        rnd = random.Random(i)
        for k in range(7):
            gx = x + 22 + rnd.randint(0, 130); gy = 300 + rnd.randint(0, 200); c = rnd.choice([(200, 240, 255), (255, 255, 255), (255, 120, 180), (120, 255, 200)])
            d.polygon([(gx, gy - 14), (gx + 12, gy), (gx, gy + 14), (gx - 12, gy)], fill=c)
    def sparkle(dr):
        rnd = random.Random(9)
        for _ in range(30):
            x = rnd.randint(410, 1250); y = rnd.randint(270, 520); dr.line([(x - 14, y), (x + 14, y)], fill=(255, 255, 255), width=2); dr.line([(x, y - 14), (x, y + 14)], fill=(255, 255, 255), width=2)
    img = glow(img, sparkle, 5, 1.6)
    def sign(dr): dr.rectangle((820, 90, 1210, 180), fill=(255, 190, 60))
    img = glow(img, sign, 30, 0.9); d = ImageDraw.Draw(img); d.rectangle((820, 90, 1210, 180), fill=(40, 28, 10)); d.text((1015, 135), "JEWELRY", fill=(255, 215, 90), anchor="mm")
    img = split_light(img, (255, 40, 50), (40, 90, 255), 0.9, 0.9)       # police red / blue
    return finish(darken_left(img, 0.55))

def airport(s=3):
    img = lin((110, 170, 235), (255, 190, 120), 0, 420); d = ImageDraw.Draw(img)
    d.rectangle((0, 420, W, H), fill=(140, 140, 160))
    for x in range(380, W, 170): d.rectangle((x, 60, x + 12, 430), fill=(70, 80, 100))        # window frames
    d.line([(380, 250), (W, 250)], fill=(70, 80, 100), width=8)
    d.polygon([(900, 330), (1180, 300), (1230, 312), (1170, 322), (1100, 335)], fill=(235, 240, 250))   # plane on the apron
    d.rectangle((420, 420, W, 440), fill=(110, 110, 130))
    d.rectangle((760, 40, 1240, 150), fill=(14, 16, 30)); 
    for i in range(4): d.rectangle((775, 52 + i * 24, 1225, 66 + i * 24), fill=(255, 190, 60) if i % 2 else (90, 200, 255))      # flight board
    for x in range(420, W, 140): d.polygon([(x, 440), (x + 70, 440), (x + 120, H), (x - 50, H)], fill=(150, 150, 172))          # floor perspective
    img = split_light(img, (255, 170, 80), (80, 140, 255), 0.5, 0.35)
    def sun(dr): dr.ellipse((1000, 180, 1200, 380), fill=(255, 230, 170))
    img = glow(img, sun, 50, 0.8)
    return finish(darken_left(img, 0.5))

def tv_studio(s=4):
    img = lin((26, 10, 60), (60, 16, 90)); d = ImageDraw.Draw(img)
    d.rectangle((0, 560, W, H), fill=(26, 14, 44))
    for i, x in enumerate(range(420, W, 90)):                      # LED panel wall
        col = [(255, 60, 170), (80, 90, 255), (255, 190, 50)][i % 3]; d.rectangle((x, 70, x + 70, 500), fill=tuple(int(c * 0.45) for c in col))
    def panels(dr):
        for i, x in enumerate(range(420, W, 90)): dr.rectangle((x, 70, x + 70, 500), fill=([(255, 60, 170), (80, 90, 255), (255, 190, 50)][i % 3]))
    img = glow(img, panels, 26, 0.55)
    def hearts(dr):
        for (cx, cy, r) in [(900, 200, 46), (1100, 330, 38), (780, 380, 30)]:
            dr.ellipse((cx - r, cy - r, cx, cy), fill=(255, 70, 160)); dr.ellipse((cx, cy - r, cx + r, cy), fill=(255, 70, 160)); dr.polygon([(cx - r, cy - r // 3), (cx + r, cy - r // 3), (cx, cy + r)], fill=(255, 70, 160))
    img = glow(img, hearts, 12, 1.4); hearts(ImageDraw.Draw(img))
    d = ImageDraw.Draw(img); d.rectangle((1000, 40, 1240, 100), fill=(220, 30, 40)); d.text((1120, 70), "ON AIR", fill=(255, 255, 255), anchor="mm")
    img = split_light(img, (255, 60, 140), (80, 90, 255), 0.7, 0.7); img = bokeh(img, [(255, 120, 200), (120, 140, 255)], 22, k=0.3)
    return finish(darken_left(img, 0.5))

def casino(s=5):
    img = lin((20, 6, 10), (40, 8, 14)); d = ImageDraw.Draw(img)
    d.ellipse((380, 470, 1700, 1250), fill=(10, 80, 40), outline=(90, 50, 20), width=18); d.ellipse((520, 520, 1560, 1180), outline=(235, 220, 160), width=3)
    for i in range(14):                                            # chips
        rnd = random.Random(i); x = rnd.randint(520, 1200); y = rnd.randint(540, 700); c = rnd.choice([(220, 40, 40), (40, 80, 220), (250, 250, 250), (30, 30, 30)])
        d.ellipse((x - 26, y - 10, x + 26, y + 10), fill=c, outline=(255, 255, 255), width=2)
    def neon(dr):
        dr.rectangle((820, 90, 1210, 130), fill=(255, 40, 80)); dr.rectangle((960, 190, 1230, 214), fill=(255, 200, 50)); dr.rectangle((700, 150, 740, 420), fill=(60, 200, 255))
    img = glow(img, neon, 26, 1.4); img = glow(img, neon, 5, 0.8)
    def wheel(dr):
        dr.ellipse((960, 330, 1220, 500), outline=(255, 200, 70), width=10)
    img = glow(img, wheel, 10, 1.0)
    img = split_light(img, (255, 50, 50), (255, 190, 60), 0.8, 0.5); img = bokeh(img, [(255, 190, 60), (255, 60, 90)], 30, k=0.3)
    return finish(darken_left(img))

def stage_arena(s=6):
    img = lin((8, 8, 40), (20, 10, 70)); d = ImageDraw.Draw(img)
    d.rectangle((0, 560, W, H), fill=(12, 10, 36))
    rnd = random.Random(2)
    for i in range(18):                                            # spotlight beams from the top
        x = 380 + i * 52; col = (255, 70, 60) if i % 2 else (70, 130, 255)
        d.polygon([(x, 0), (x + 16, 0), (x + 150 - i * 6, 560), (x - 130 + i * 6, 560)], fill=tuple(int(c * 0.25) for c in col))
    img = split_light(img, (255, 50, 40), (50, 110, 255), 1.0, 1.0)
    def pad(dr): dr.ellipse((450, 560, 1260, 660), outline=(255, 255, 255), width=3)
    img = glow(img, pad, 16, 1.3); img = bokeh(img, [(255, 90, 70), (90, 150, 255)], 20, k=0.4)
    return finish(darken_left(img, 0.5))

def vault_money(s=7):
    img = lin((30, 20, 4), (80, 54, 8)); d = ImageDraw.Draw(img)
    d.ellipse((620, 120, 1240, 740), fill=(60, 52, 36), outline=(210, 170, 70), width=14); d.ellipse((700, 200, 1160, 660), outline=(210, 170, 70), width=8)
    for a in range(0, 360, 45): d.line([(930, 430), (930 + 220 * math.cos(math.radians(a)), 430 + 220 * math.sin(math.radians(a)))], fill=(210, 170, 70), width=10)
    d.ellipse((880, 380, 980, 480), fill=(230, 190, 80))
    for i in range(8):                                             # gold bars bottom
        x = 420 + i * 100; d.polygon([(x, 700), (x + 90, 700), (x + 76, 660), (x + 14, 660)], fill=(240, 190, 50), outline=(140, 100, 10))
    for i in range(70):
        a = math.radians(i * 5.1); d.line([(930, 430), (930 + 900 * math.cos(a), 430 + 900 * math.sin(a))], fill=(110, 80, 12), width=3)
    img = split_light(img, (255, 190, 60), (60, 200, 110), 0.7, 0.45); img = bokeh(img, [(255, 220, 110)], 30, k=0.3)
    return finish(darken_left(img))

def street_night(s=8):
    rnd = random.Random(s); hz = 430
    img = lin((18, 10, 46), (255, 110, 50), 0, hz); d = ImageDraw.Draw(img)
    for layer, (hmin, hmax, col, wc) in enumerate([(110, 280, (60, 36, 100), 0.2), (90, 360, (16, 12, 36), 0.3)]):
        x = -20
        while x < W + 20:
            w = rnd.randint(40, 110); h = rnd.randint(hmin, hmax); d.rectangle((x, hz - h, x + w, hz), fill=col)
            for wy in range(hz - h + 10, hz - 8, 16):
                for wx in range(x + 8, x + w - 8, 14):
                    if rnd.random() < wc: d.rectangle((wx, wy, wx + 5, wy + 8), fill=(255, 205, 120))
            x += w + rnd.randint(0, 6)
    def neon(dr):
        for (x, y, w, h, c) in [(820, 220, 220, 22, (255, 40, 160)), (1010, 300, 14, 130, (0, 230, 255)), (700, 330, 160, 18, (255, 220, 40)), (1130, 200, 90, 16, (0, 255, 160))]: dr.rectangle((x, y, x + w, y + h), fill=c)
    img = glow(img, neon, 22, 1.5); img = glow(img, neon, 6, 0.8); img = floor_reflect(img, hz)
    img = bokeh(img, [(255, 90, 160), (0, 210, 255), (255, 190, 60)], 30, k=0.24)
    return finish(darken_left(img, 0.5))

def alley_rain(s=9):
    rnd = random.Random(s); img = lin((8, 10, 26), (26, 20, 40)); d = ImageDraw.Draw(img)
    d.rectangle((420, 0, 1280, 520), fill=(52, 30, 36))                      # brick wall
    for y in range(0, 520, 30):
        for x in range(420 + (y // 30 % 2) * 30, 1280, 60): d.rectangle((x, y, x + 56, y + 26), outline=(30, 16, 20), width=2)
    d.polygon([(760, 90), (900, 70), (950, 220), (800, 260)], fill=(255, 90, 160), outline=(255, 255, 255)); d.rectangle((1010, 320, 1250, 520), fill=(18, 40, 32), outline=(10, 20, 16), width=4)  # graffiti + dumpster
    d.rectangle((0, 520, W, H), fill=(14, 14, 28))
    def police(dr): dr.ellipse((1080, 120, 1200, 200), fill=(255, 40, 40)); dr.ellipse((1200, 120, 1260, 200), fill=(40, 90, 255))
    img = glow(img, police, 50, 1.4)
    img = floor_reflect(img, 520, 150); img = split_light(img, (255, 40, 40), (40, 100, 255), 0.7, 0.8)
    d = ImageDraw.Draw(img)
    for _ in range(260): x = rnd.randint(0, W); y = rnd.randint(0, H); d.line([(x, y), (x - 6, y + 30)], fill=(150, 170, 210), width=1)       # rain
    return finish(darken_left(img, 0.55), 1.1)

def birthday(s=10):
    rnd = random.Random(s); img = lin((40, 18, 90), (110, 40, 120)); d = ImageDraw.Draw(img)
    for i in range(8): d.line([(380 + i * 120, 0), (480 + i * 120, 120)], fill=(255, 240, 200), width=3)            # string lights
    cols = [(255, 70, 90), (255, 200, 40), (60, 200, 255), (120, 255, 150), (200, 90, 255)]
    for _ in range(18):                                                                                           # balloons
        x = rnd.randint(420, 1240); y = rnd.randint(40, 460); c = rnd.choice(cols); d.ellipse((x - 44, y - 56, x + 44, y + 56), fill=c); d.line([(x, y + 56), (x - 6, y + 160)], fill=(230, 230, 230), width=2)
    def bulbs(dr):
        for i in range(8): dr.ellipse((470 + i * 120, 100, 490 + i * 120, 120), fill=(255, 235, 170))
    img = glow(img, bulbs, 16, 1.5)
    for _ in range(120): x = rnd.randint(380, W); y = rnd.randint(0, H); d.rectangle((x, y, x + 8, y + 4), fill=rnd.choice(cols))                  # confetti
    img = split_light(img, (255, 190, 70), (150, 80, 255), 0.7, 0.7)
    return finish(darken_left(img, 0.45), 1.2)

def gaming_room(s=11):
    img = lin((14, 10, 34), (26, 14, 54)); d = ImageDraw.Draw(img)
    d.rectangle((380, 200, 1010, 470), fill=(8, 10, 22), outline=(60, 50, 110), width=6); d.rectangle((1040, 250, 1260, 440), fill=(8, 10, 22), outline=(60, 50, 110), width=6)     # monitors
    def scr(dr): dr.rectangle((392, 212, 998, 458), fill=(70, 90, 255)); dr.rectangle((1052, 262, 1248, 428), fill=(255, 70, 160))
    img = glow(img, scr, 40, 0.9); d = ImageDraw.Draw(img)
    for i in range(7): d.rectangle((410 + i * 84, 236 + (i % 3) * 24, 470 + i * 84, 300 + (i % 3) * 24), fill=(150, 190, 255))
    d.rectangle((360, 470, W, 500), fill=(30, 24, 60)); d.rectangle((0, 500, W, H), fill=(18, 12, 40))
    def rgb(dr):
        dr.line([(380, 90), (1260, 90)], fill=(255, 60, 200), width=10); dr.line([(380, 560), (1260, 560)], fill=(60, 200, 255), width=8)
    img = glow(img, rgb, 20, 1.4); img = glow(img, rgb, 4, 0.9)
    img = split_light(img, (255, 70, 180), (60, 120, 255), 0.7, 0.7); img = bokeh(img, [(255, 90, 200), (90, 160, 255)], 14, k=0.3)
    return finish(darken_left(img, 0.5), 1.8)

def server_room(s=12):
    img = lin((4, 14, 30), (10, 30, 60)); d = ImageDraw.Draw(img)
    for x in range(380, W, 120):
        d.rectangle((x, 40, x + 100, 640), fill=(14, 22, 40), outline=(40, 80, 130), width=3); rnd = random.Random(x)
        for y in range(60, 620, 22): d.rectangle((x + 8, y, x + 92, y + 14), fill=(24, 40, 66)); d.rectangle((x + 74, y + 3, x + 84, y + 11), fill=rnd.choice([(60, 255, 150), (60, 200, 255), (255, 80, 80)]))
    def beams(dr):
        for i in range(6): dr.polygon([(760 + i * 70, 0), (790 + i * 70, 0), (850 + i * 40, 700), (700 + i * 40, 700)], fill=(30, 120, 200))
    img = glow(img, beams, 24, 0.6); img = split_light(img, (255, 150, 60), (40, 150, 255), 0.35, 0.8)
    return finish(darken_left(img, 0.55))

def stadium(s=13):
    img = lin((10, 16, 40), (30, 70, 40), 0, 520); d = ImageDraw.Draw(img)
    d.rectangle((0, 520, W, H), fill=(190, 60, 40))
    for i in range(7): d.line([(380, 560 + i * 22), (W, 560 + i * 22)], fill=(255, 255, 255), width=3)
    for i, x in enumerate((520, 760, 1000, 1220)):
        d.rectangle((x - 6, 180, x + 6, 420), fill=(50, 50, 60))
    def lights(dr):
        for x in (520, 760, 1000, 1220): dr.rectangle((x - 40, 120, x + 40, 180), fill=(255, 245, 200))
    img = glow(img, lights, 40, 1.6); img = glow(img, lights, 8, 0.9)
    for i in range(18): d.ellipse((380 + i * 50, 440 - (i % 3) * 14, 410 + i * 50, 470 - (i % 3) * 14), fill=(24, 24, 34))   # crowd heads
    img = split_light(img, (255, 190, 60), (60, 120, 255), 0.6, 0.6)
    return finish(darken_left(img, 0.5))

def food_stall(s=14):
    rnd = random.Random(s); img = lin((20, 10, 8), (60, 24, 10)); d = ImageDraw.Draw(img)
    d.rectangle((380, 330, W, 560), fill=(70, 36, 18)); d.rectangle((380, 330, W, 350), fill=(210, 150, 60))
    for i in range(6): d.rectangle((440 + i * 140, 220, 440 + i * 140 + 26, 330), fill=(160, 70, 30))                     # hanging skewers
    d.ellipse((860, 380, 1160, 460), fill=(30, 18, 10)); 
    def fire(dr):
        for i in range(12): dr.ellipse((880 + i * 22, 360 + rnd.randint(-20, 20), 920 + i * 22, 420), fill=(255, rnd.randint(110, 190), 30))
    img = glow(img, fire, 24, 1.5)
    def bulbs(dr):
        for i in range(10): dr.ellipse((410 + i * 90, 90, 440 + i * 90, 120), fill=(255, 210, 120))
    img = glow(img, bulbs, 20, 1.4); img = split_light(img, (255, 120, 30), (60, 90, 170), 0.8, 0.3); img = bokeh(img, [(255, 190, 90)], 16, k=0.3)
    # smoke
    sm = Image.new("RGB", (W, H), (0, 0, 0)); sd = ImageDraw.Draw(sm)
    for i in range(14): cx = 960 + rnd.randint(-80, 120); sd.ellipse((cx - 70, 80 + i * 24, cx + 70, 160 + i * 24), fill=(70, 60, 56))
    img = ImageChops.add(img, sm.filter(ImageFilter.GaussianBlur(34)))
    return finish(darken_left(img, 0.5))

def horror_room(s=15):
    img = lin((6, 4, 10), (20, 8, 4)); d = ImageDraw.Draw(img)
    d.rectangle((900, 120, 1230, 520), fill=(255, 150, 40)); d.line([(1065, 120), (1065, 520)], fill=(30, 12, 4), width=10); d.line([(900, 320), (1230, 320)], fill=(30, 12, 4), width=10)      # window
    sil = Image.new("L", (W, H), 0); sd = ImageDraw.Draw(sil); sd.ellipse((1010, 160, 1120, 290), fill=255); sd.polygon([(960, 520), (1170, 520), (1140, 300), (990, 300)], fill=255)
    img.paste(Image.new("RGB", (W, H), (6, 4, 8)), (0, 0), sil.filter(ImageFilter.GaussianBlur(2)))
    img = glow(img, lambda dr: dr.rectangle((900, 120, 1230, 520), fill=(255, 140, 30)), 60, 1.2)
    img = split_light(img, (255, 130, 30), (30, 60, 140), 0.5, 0.4)
    return finish(darken_left(img, 0.6))

def courtroom(s=16):
    img = lin((30, 14, 12), (70, 30, 18)); d = ImageDraw.Draw(img)
    d.rectangle((420, 60, W, 520), fill=(80, 40, 22))
    for i in range(6): d.rectangle((460 + i * 130, 80, 540 + i * 130, 500), fill=(104, 56, 30), outline=(50, 24, 12), width=4)    # wood panelling
    d.rectangle((760, 330, 1230, 600), fill=(66, 32, 16)); d.rectangle((740, 310, 1250, 345), fill=(120, 66, 34))                 # judge desk
    def spark(dr):
        rnd = random.Random(3)
        for _ in range(40): x = 900 + rnd.randint(-120, 120); y = 300 + rnd.randint(-90, 40); dr.line([(x, y), (x + rnd.randint(-22, 22), y + rnd.randint(-22, 22))], fill=(255, 200, 60), width=3)
    img = glow(img, spark, 6, 1.4)
    img = split_light(img, (255, 110, 30), (40, 90, 200), 0.8, 0.5)
    return finish(darken_left(img, 0.55))

SCENES = {"law_office": law_office, "jewellery_store": jewellery_store, "airport": airport, "tv_studio": tv_studio, "casino": casino, "stage_arena": stage_arena,
          "vault_money": vault_money, "street_night": street_night, "alley_rain": alley_rain, "birthday": birthday, "gaming_room": gaming_room, "server_room": server_room,
          "stadium": stadium, "food_stall": food_stall, "horror_room": horror_room, "courtroom": courtroom}

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--all", action="store_true"); ap.add_argument("--scene", choices=SCENES); ap.add_argument("--out"); ap.add_argument("--outdir", default="assets/plates")
    a = ap.parse_args()
    if a.all:
        os.makedirs(a.outdir, exist_ok=True)
        for k, f in SCENES.items(): f().save(os.path.join(a.outdir, k + ".jpg"), quality=92); print("saved", k, flush=True)
    else: SCENES[a.scene]().save(a.out, quality=92)

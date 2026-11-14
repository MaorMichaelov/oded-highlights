#!/usr/bin/env python3
"""Topic thumbnail built from learned rules: big sharp portrait left, readable topic prop (phone with incoming-call screen + bills) lower right,
colour story orange/green, 2-line headline top-right (white + yellow, thick black outline). Uses thumb_maker helpers.
usage: thumb_call.py --face smirk.jpg --name "עמית שיבר" --head "מתקשר" --accent "לעמית שיבר!" --out out.jpg"""
import argparse, math, random, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageChops, ImageEnhance
import thumb_maker as T
W, H = T.W, T.H

def rr(d, box, r, fill, outline=None, width=0): d.rounded_rectangle(box, r, fill=fill, outline=outline, width=width)

def phone(name, w=360, h=700):
    S = 3; im = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    rr(d, (0, 0, w * S - 1, h * S - 1), 58 * S, (14, 14, 20, 255), (200, 200, 215, 255), 6 * S)
    rr(d, (14 * S, 14 * S, w * S - 14 * S, h * S - 14 * S), 46 * S, (30, 20, 70, 255))
    g = Image.new("RGB", (w * S, h * S)); gd = ImageDraw.Draw(g)
    for y in range(h * S): t = y / (h * S); gd.line([(0, y), (w * S, y)], fill=(int(70 + 90 * t), int(30 + 10 * t), int(150 - 40 * t)))
    m = Image.new("L", (w * S, h * S), 0); ImageDraw.Draw(m).rounded_rectangle((14 * S, 14 * S, w * S - 14 * S, h * S - 14 * S), 46 * S, fill=255)
    im.paste(g, (0, 0), m); d = ImageDraw.Draw(im)
    cx = w * S // 2
    d.ellipse((cx - 70 * S, 120 * S, cx + 70 * S, 260 * S), fill=(255, 190, 40, 255), outline=(255, 255, 255, 255), width=5 * S)
    f = T.font(90 * S); d.text((cx, 190 * S), name[0], font=f, fill=(60, 20, 0, 255), anchor="mm", direction="rtl", language="he")
    f2 = T.font(46 * S); d.text((cx, 330 * S), name, font=f2, fill=(255, 255, 255, 255), anchor="mm", direction="rtl", language="he", stroke_width=2 * S, stroke_fill=(0, 0, 0, 120))
    f3 = T.font(30 * S); d.text((cx, 392 * S), "שיחה נכנסת...", font=f3, fill=(230, 220, 255, 255), anchor="mm", direction="rtl", language="he")
    by = 560 * S
    d.ellipse((60 * S, by - 56 * S, 172 * S, by + 56 * S), fill=(235, 40, 50, 255))
    d.line([(92 * S, by - 20 * S), (140 * S, by + 20 * S)], fill=(255, 255, 255, 255), width=12 * S); d.line([(140 * S, by - 20 * S), (92 * S, by + 20 * S)], fill=(255, 255, 255, 255), width=12 * S)
    d.ellipse((w * S - 172 * S, by - 56 * S, w * S - 60 * S, by + 56 * S), fill=(40, 210, 80, 255))
    hx, hy = w * S - 116 * S, by
    d.arc((hx - 30 * S, hy - 30 * S, hx + 30 * S, hy + 30 * S), 200, 340, fill=(255, 255, 255, 255), width=14 * S)
    d.ellipse((hx - 34 * S, hy - 4 * S, hx - 12 * S, hy + 18 * S), fill=(255, 255, 255, 255)); d.ellipse((hx + 12 * S, hy - 4 * S, hx + 34 * S, hy + 18 * S), fill=(255, 255, 255, 255))
    return im.resize((w, h), Image.LANCZOS)

def bill(w=230, h=110, seed=0):
    S = 3; im = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    rr(d, (0, 0, w * S - 1, h * S - 1), 10 * S, (70, 150, 75, 255), (25, 80, 35, 255), 5 * S)
    rr(d, (12 * S, 12 * S, w * S - 12 * S, h * S - 12 * S), 6 * S, (110, 190, 110, 255), (40, 110, 55, 255), 3 * S)
    d.ellipse((w * S // 2 - 34 * S, h * S // 2 - 34 * S, w * S // 2 + 34 * S, h * S // 2 + 34 * S), fill=(60, 140, 70, 255), outline=(30, 90, 40, 255), width=4 * S)
    d.text((w * S // 2, h * S // 2), "$", font=T.font(52 * S), fill=(235, 250, 235, 255), anchor="mm")
    d.text((26 * S, 26 * S), "100", font=T.font(22 * S), fill=(30, 90, 40, 255)); d.text((w * S - 26 * S, h * S - 26 * S), "100", font=T.font(22 * S), fill=(30, 90, 40, 255), anchor="rs")
    return im.resize((w, h), Image.LANCZOS)

def shadowed(layer, off=(10, 14), blur=14, op=0.6):
    sh = layer.split()[-1].filter(ImageFilter.GaussianBlur(blur)); s = Image.new("RGBA", layer.size, (0, 0, 0, 0)); s.putalpha(sh.point(lambda v: int(v * op)))
    out = Image.new("RGBA", (layer.width + 60, layer.height + 60), (0, 0, 0, 0)); out.alpha_composite(s, (30 + off[0], 30 + off[1])); out.alpha_composite(layer, (30, 30)); return out

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--face", required=True); ap.add_argument("--name", default="עמית שיבר")
    ap.add_argument("--head", default="מתקשר"); ap.add_argument("--accent", default="לעמית שיבר!"); ap.add_argument("--out", required=True); ap.add_argument("--bg", help="scene plate (16:9) without people; replaces the procedural background")
    a = ap.parse_args(); random.seed(5)
    # background: warm orange/red story with a green accent, dark vignette
    bg = Image.new("RGB", (W, H), (22, 8, 10)); d = ImageDraw.Draw(bg)
    for i in range(30):
        a0 = math.radians(i * 12); a1 = math.radians(i * 12 + 6)
        d.polygon([(900, 470), (900 + 1800 * math.cos(a0), 470 + 1800 * math.sin(a0)), (900 + 1800 * math.cos(a1), 470 + 1800 * math.sin(a1))], fill=(70, 24, 12))
    glow = Image.new("RGB", (W, H), (0, 0, 0)); ImageDraw.Draw(glow).ellipse((520, 140, 1280, 760), fill=(255, 120, 20)); glow = glow.filter(ImageFilter.GaussianBlur(110))
    bg = ImageChops.add(bg, glow.point(lambda v: int(v * 0.8)))
    g2 = Image.new("RGB", (W, H), (0, 0, 0)); ImageDraw.Draw(g2).ellipse((-200, 300, 520, 900), fill=(30, 180, 70)); g2 = g2.filter(ImageFilter.GaussianBlur(120)); bg = ImageChops.add(bg, g2.point(lambda v: int(v * 0.35)))
    if a.bg:
        pl = Image.open(a.bg).convert("RGB"); r = max(W / pl.width, H / pl.height)
        pl = pl.resize((int(pl.width * r) + 1, int(pl.height * r) + 1), Image.LANCZOS); l, t = (pl.width - W) // 2, (pl.height - H) // 2
        pl = pl.crop((l, t, l + W, t + H)).filter(ImageFilter.UnsharpMask(radius=2, percent=80, threshold=2))
        g = Image.new("L", (W, H), 0); gd = ImageDraw.Draw(g)
        for x in range(W): gd.line([(x, 0), (x, H)], fill=int(150 * max(0.0, 1 - x / (W * 0.55))))      # darker behind the face side
        bg = Image.composite(Image.new("RGB", (W, H), (10, 6, 14)), pl, g)
    if not a.bg:
        L1 = Image.new("RGB", (W, H), (0, 0, 0)); ImageDraw.Draw(L1).ellipse((-260, 60, 620, 900), fill=(255, 120, 30)); L1 = L1.filter(ImageFilter.GaussianBlur(130))
        L2 = Image.new("RGB", (W, H), (0, 0, 0)); ImageDraw.Draw(L2).ellipse((640, -120, 1500, 700), fill=(20, 170, 255)); L2 = L2.filter(ImageFilter.GaussianBlur(130))
        base = Image.new("RGB", (W, H), (10, 8, 24)); bg = ImageChops.add(ImageChops.add(base, L1.point(lambda v: int(v * 0.85))), L2.point(lambda v: int(v * 0.75)))
        dd = ImageDraw.Draw(bg)
        for i in range(34):                                  # light rays from the prop side
            a0 = math.radians(200 + i * 4.2); a1 = a0 + math.radians(1.6); cx, cy = 1000, 400
            dd.polygon([(cx, cy), (cx + 1600 * math.cos(a0), cy + 1600 * math.sin(a0)), (cx + 1600 * math.cos(a1), cy + 1600 * math.sin(a1))], fill=(30, 60, 110))
        bg = ImageChops.add(bg, L2.point(lambda v: int(v * 0.35)))
    bg = bg.convert("RGBA")
    # bills flying around the phone
    for i in range(11):
        b = bill(random.randint(150, 230), random.randint(72, 110)); b = b.rotate(random.randint(-50, 50), expand=True, resample=Image.BICUBIC)
        b = shadowed(b, blur=8, op=0.5); x = random.randint(640, 1100); y = random.randint(380, 660)
        bg.alpha_composite(b, (x, y))
    # phone
    ph = phone(a.name, 270, 520).rotate(-8, expand=True, resample=Image.BICUBIC); ph = shadowed(ph, blur=20, op=0.7)
    PH = (880, 150)
    # portrait (sharp AI portrait) big on the left, bleeding off the bottom (phone is drawn AFTER it)
    fr = Image.open(a.face).convert("RGB"); person = T.cutout(fr); person = person.crop(person.split()[-1].getbbox())
    k = min(1.0, (H * 1.04) / person.height, (W * 0.50) / person.width)
    person = person.resize((int(person.width * k), int(person.height * k)), Image.LANCZOS)
    stk, pad = T.sticker(person, dict(glow=(255, 150, 40), outline=(255, 255, 255)), outline_px=9, glow_px=34)
    bg.alpha_composite(stk, (-30 - pad + 30, H - stk.height + pad + 20))
    bg.alpha_composite(ph, (PH[0] - 150, PH[1]))
    out = bg.convert("RGB")
    face_box = (0, H - person.height + 20, person.width, H)
    box = T.headline_taklipu(out, [(a.head, "white"), (a.accent, "accent")], (int(W * 0.42), W - 28), ribbon=None, tilt=3.0)
    out = T.finish(out)
    q = 94
    while True:
        out.save(a.out, quality=q, optimize=True, subsampling=0)
        if os.path.getsize(a.out) < 1_900_000 or q <= 70: break
        q -= 4
    out.resize((168, 94), Image.LANCZOS).save(os.path.splitext(a.out)[0] + "_168.png")
    fb = T.detect_faces(out.crop((0, 0, 640, H))); inter = sum(T.overlap(box, (f[0], f[1], f[2], f[3])) for f in fb)
    print("headline box", box, "| faces found", len(fb), "| overlap px", inter)
main()

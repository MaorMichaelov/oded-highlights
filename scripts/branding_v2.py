#!/usr/bin/env python3
"""Reference-style branding pieces (orange theme for Ronen, green for Oded).

  sub_overlay_frames(): lower-right logo pop + speech bubble
      'תנו לייק וסאב, די להיות קמצנים!' + animated like / subscribe / bell (no counts)
  caption_png(): big punchy Hebrew caption, white + accent highlight words, thick black outline
The intro itself is branding.make_intro().
"""
from __future__ import annotations
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
from branding import THEMES, _font, _circle_logo, _rtl
from config import CHANNEL

SUB_SEC = 5.0


def _ease_pop(p):  # 0..1 -> overshoot pop
    if p <= 0:
        return 0.0
    if p >= 1:
        return 1.0
    return 1 + 0.18 * math.sin(p * math.pi) if p > 0.6 else p / 0.6 * 1.1


def _thumb(d, x, y, s, fill):
    d.rectangle((x, y + s * 0.42, x + s * 0.22, y + s), fill=fill)
    d.rounded_rectangle((x + s * 0.28, y + s * 0.40, x + s * 0.95, y + s), radius=int(s * 0.12), fill=fill)
    d.polygon([(x + s * 0.30, y + s * 0.45), (x + s * 0.52, y), (x + s * 0.66, y + s * 0.08), (x + s * 0.60, y + s * 0.42)], fill=fill)


def _bell(d, cx, cy, s, fill, ang=0.0):
    pts = []
    for k in range(0, 181, 15):
        a = math.radians(k)
        pts.append((cx - s * 0.42 * math.cos(a), cy - s * 0.1 - s * 0.42 * math.sin(a)))
    pts += [(cx + s * 0.42, cy + s * 0.25), (cx + s * 0.55, cy + s * 0.38), (cx - s * 0.55, cy + s * 0.38), (cx - s * 0.42, cy + s * 0.25)]
    ca, sa = math.cos(ang), math.sin(ang)
    rot = [(cx + (px - cx) * ca - (py - cy) * sa, cy + (px - cx) * sa + (py - cy) * ca) for px, py in pts]
    d.polygon(rot, fill=fill)
    d.ellipse((cx - s * 0.1 + s * 0.3 * sa, cy + s * 0.4, cx + s * 0.1 + s * 0.3 * sa, cy + s * 0.6), fill=fill)


def sub_overlay_frame(t, W, H, theme):
    acc = theme["accent"]
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    out_a = max(0.0, min(1.0, (SUB_SEC - t) / 0.4))
    # logo pop (lower right)
    ls = int(H * 0.25)
    sc = _ease_pop(t / 0.35)
    if sc > 0.02:
        s = max(4, int(ls * sc))
        lg = _circle_logo(theme["logo"], s)
        ring = Image.new("RGBA", (s + 12, s + 12), (0, 0, 0, 0))
        ImageDraw.Draw(ring).ellipse((0, 0, s + 11, s + 11), fill=acc + (255,))
        cx, cy = W - 40 - ls / 2, H - 50 - ls / 2
        im.alpha_composite(ring, (int(cx - s / 2 - 6), int(cy - s / 2 - 6)))
        im.alpha_composite(lg, (int(cx - s / 2), int(cy - s / 2)))
    # bubble slides in from the logo
    p = max(0.0, min(1.0, (t - 0.25) / 0.35))
    if p > 0:
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        bw, bh = int(W * 0.30), int(H * 0.20)
        x1 = W - 60 - ls - 10
        x0 = x1 - bw + int((1 - p) * 40)
        y0 = H - 60 - bh - int(H * 0.03)
        d.rounded_rectangle((x0, y0, x0 + bw, y0 + bh), radius=28, fill=(255, 255, 255, 250), outline=acc + (255,), width=5)
        d.polygon([(x0 + bw - 4, y0 + bh * 0.35), (x0 + bw + 26, y0 + bh * 0.55), (x0 + bw - 4, y0 + bh * 0.70)], fill=(255, 255, 255, 250))
        f1 = _font(int(bh * 0.20))
        _rtl(d, (x0 + bw / 2, y0 + bh * 0.20), "תנו לייק וסאב,", f1, (20, 20, 20))
        # second line with the punchline highlighted
        words = [("די", False), ("להיות", False), ("קמצנים!", True)]
        widths = [d.textlength(w, font=f1, direction="rtl") for w, _ in words]
        gap = bh * 0.06
        total = sum(widths) + gap * (len(words) - 1)
        x = x0 + bw / 2 + total / 2
        for (w, hl), wd in zip(words, widths):
            if hl:
                d.rounded_rectangle((x - wd - 6, y0 + bh * 0.33, x + 6, y0 + bh * 0.58), radius=8, fill=acc + (255,))
            d.text((x, y0 + bh * 0.455), w, font=f1, fill=(255, 255, 255) if hl else (20, 20, 20), anchor="rm", direction="rtl")
            x -= wd + gap
        # buttons row: like, subscribe, bell (animated one after another)
        by, bhh = y0 + bh * 0.66, bh * 0.25
        def pulse(t0):
            q = (t - t0) / 0.35
            return 1 + 0.18 * math.sin(q * math.pi) if 0 <= q <= 1 else 1.0
        # like
        s = pulse(1.0)
        lw = bhh * 1.6 * s
        lx = x0 + bw * 0.08
        liked = t >= 1.15
        d.rounded_rectangle((lx, by - (s - 1) * bhh / 2, lx + lw, by + bhh * s), radius=int(bhh * s / 2),
                            fill=(acc if liked else (30, 30, 30)) + (255,))
        _thumb(d, lx + lw * 0.3, by + bhh * 0.15, bhh * 0.7 * s, (255, 255, 255, 255))
        # subscribe
        s = pulse(1.8)
        sx = lx + lw + bw * 0.05
        sw = bw * 0.42 * s
        subbed = t >= 1.95
        d.rounded_rectangle((sx, by - (s - 1) * bhh / 2, sx + sw, by + bhh * s), radius=int(bhh * s / 2),
                            fill=((90, 90, 90) if subbed else (230, 20, 30)) + (255,))
        _rtl(d, (sx + sw / 2, by + bhh * s / 2 - 1), "נרשמתם ✓" if subbed else "הרשמה", _font(int(bhh * 0.62)), (255, 255, 255))
        # bell
        bx = sx + sw + bw * 0.05 + bhh * 0.6
        ang = 0.45 * math.sin((t - 2.6) * 18) * max(0.0, 1 - (t - 2.6) / 0.8) if t >= 2.6 else 0.0
        d.ellipse((bx - bhh * 0.65, by - bhh * 0.15, bx + bhh * 0.65, by + bhh * 1.15), fill=(30, 30, 30, 255))
        _bell(d, bx, by + bhh * 0.45, bhh * 0.8, acc + (255,) if t >= 2.6 else (255, 255, 255, 255), ang)
        a = layer.split()[3].point(lambda v: int(v * min(1.0, p * 1.5)))
        layer.putalpha(a)
        im.alpha_composite(layer)
    if out_a < 1:
        im.putalpha(im.split()[3].point(lambda v: int(v * out_a)))
    return im


def sub_overlay_frames(dest_dir, W, H, fps=30):
    theme = THEMES.get(CHANNEL, THEMES["odedsvr"])
    dest_dir = Path(dest_dir); dest_dir.mkdir(parents=True, exist_ok=True)
    n = int(SUB_SEC * fps)
    for i in range(n):
        sub_overlay_frame(i / fps, W, H, theme).save(dest_dir / f"s{i:04d}.png")
    return dest_dir / "s%04d.png", fps


def caption_png(words, dest, W, H, size=64, y_frac=0.80):
    """words: [(text, highlight_bool)] in reading order (RTL)."""
    theme = THEMES.get(CHANNEL, THEMES["odedsvr"])
    acc = theme["accent"]
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    while True:  # shrink until the line fits inside 88% of the frame width
        f = _font(size)
        widths = [d.textlength(w, font=f, direction="rtl") for w, _ in words]
        gap = size * 0.28
        total = sum(widths) + gap * (len(words) - 1) + 2 * max(4, size // 11)
        if total <= W * 0.88 or size <= 30:
            break
        size -= 4
    x = W / 2 + total / 2
    y = H * y_frac
    for (w, hl), wd in zip(words, widths):
        d.text((x, y), w, font=f, fill=acc if hl else (255, 255, 255), anchor="rm", direction="rtl",
               stroke_width=max(4, size // 11), stroke_fill=(0, 0, 0))
        x -= wd + gap
    im.save(dest)
    return dest

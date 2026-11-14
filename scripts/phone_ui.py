#!/usr/bin/env python3
"""Clean smartphone incoming-call mockup drawn with Pillow (no AI garbling): glowing frame, caller avatar, name, green accept / red decline with handset icons.
Used by make_scene_thumb.py for the phone_call preset: paste_phone(img, caller, box)."""
import math, os, sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
S = 3  # supersampling
def _font(size):
    for p in ["/usr/share/fonts/truetype/sand-box/google/Heebo/Heebo-VariableFont_wght.ttf", "/workspace/fonts/Heebo-VariableFont_wght.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]:
        if os.path.exists(p):
            f = ImageFont.truetype(p, size)
            try: f.set_variation_by_name("Bold")
            except Exception: pass
            return f
    return ImageFont.load_default()
def handset(size, color, angle):
    """classic handset: curved bar with two chunky earpiece/mouthpiece blocks (rest position: arch, ends down), rotated by angle."""
    L = Image.new("RGBA", (size * 2, size * 2), (0, 0, 0, 0)); d = ImageDraw.Draw(L); c = size; r = int(size * 0.80); w = int(size * 0.26)
    cy = c + int(size * 0.25)
    d.arc((c - r, cy - r, c + r, cy + r), 205, 335, fill=color, width=w)
    for a in (205, 335):
        x = c + (r - w / 2) * math.cos(math.radians(a)); y = cy + (r - w / 2) * math.sin(math.radians(a))
        d.rounded_rectangle((x - w * 0.95, y - w * 0.2, x + w * 0.95, y + w * 1.15), int(w * 0.35), fill=color)
    return L.rotate(angle, resample=Image.BICUBIC)
def phone_layer(caller, w=330, h=560):
    W, H = w * S, h * S; im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    rr = 46 * S
    d.rounded_rectangle((0, 0, W - 1, H - 1), rr, fill=(18, 14, 30, 255), outline=(255, 140, 60, 255), width=5 * S)  # body + neon rim
    sx, sy = 12 * S, 12 * S
    scr = Image.new("RGBA", (W - 2 * sx, H - 2 * sy), (0, 0, 0, 0)); sd = ImageDraw.Draw(scr)
    for y in range(scr.height):  # screen gradient
        t = y / scr.height; sd.line([(0, y), (scr.width, y)], fill=(int(40 + 40 * t), int(18 + 10 * t), int(80 - 30 * t), 255))
    sw, sh = scr.size
    sd.rounded_rectangle((sw // 2 - 50 * S, 14 * S, sw // 2 + 50 * S, 36 * S), 11 * S, fill=(0, 0, 0, 255))  # notch
    f1, f2 = _font(21 * S), _font(40 * S)
    sd.text((sw // 2, 70 * S), "שיחה נכנסת", font=f1, fill=(215, 205, 235, 255), anchor="mm", direction="rtl", language="he")
    sd.text((sw // 2, 330 * S), caller, font=_font(52 * S), fill=(255, 255, 255, 255), anchor="mm", direction="rtl", language="he")
    sd.text((sw // 2, 392 * S), "מתקשר...", font=f1, fill=(215, 205, 235, 255), anchor="mm", direction="rtl", language="he")
    by, br = sh - 86 * S, 44 * S  # buttons
    for bx, col, ang in ((sw * 0.27, (230, 45, 45, 255), 0), (sw * 0.73, (45, 205, 80, 255), 40)):
        sd.ellipse((bx - br, by - br, bx + br, by + br), fill=col)
        hs = handset(int(34 * S), (255, 255, 255, 255), ang); scr.alpha_composite(hs, (int(bx - hs.width / 2), int(by - hs.height / 2))) if False else scr.paste(hs, (int(bx - hs.width / 2), int(by - hs.height / 2)), hs)
    mask = Image.new("L", scr.size, 0); ImageDraw.Draw(mask).rounded_rectangle((0, 0, sw - 1, sh - 1), 36 * S, fill=255)
    im.paste(scr, (sx, sy), mask)
    return im.resize((w, h), Image.LANCZOS)
def paste_phone(img, caller, xy=(820, 150), size=(330, 560), tilt=6):
    ph = phone_layer(caller, 330, 560).resize(size, Image.LANCZOS).rotate(tilt, resample=Image.BICUBIC, expand=True)
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0)); g = Image.new("RGBA", ph.size, (255, 130, 40, 255)); g.putalpha(ph.getchannel("A").filter(ImageFilter.MaxFilter(15)))
    glow.paste(g, xy, g); glow = glow.filter(ImageFilter.GaussianBlur(28))
    base = img.convert("RGBA"); base.alpha_composite(glow); base.alpha_composite(ph, xy)
    return base.convert("RGB")
if __name__ == "__main__":
    bg = Image.new("RGB", (1280, 720), (90, 40, 150)); paste_phone(bg, sys.argv[1] if len(sys.argv) > 1 else "ביגי").save(sys.argv[2] if len(sys.argv) > 2 else "/tmp/phone_ui_test.jpg")

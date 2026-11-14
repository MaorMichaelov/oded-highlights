#!/usr/bin/env python3
"""Smartphone mockup drawn with Pillow (AI garbles phone UI). Style copied from the owner's reference (Grok thumbnail):
modern thin-bezel phone UPRIGHT facing the viewer, dynamic-island pill, glossy edge, neon glow, dark-green screen with ONE big white handset icon + 3 sound waves
and one wide green call button with a white handset. paste_phone(img, xy, size, tilt, glow=(r,g,b), accent=(r,g,b), caller=None) -> (img, bbox)."""
import math, os, sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont
S = 4
def _font(size):
    for p in ["/usr/share/fonts/truetype/sand-box/google/Heebo/Heebo-VariableFont_wght.ttf", "/workspace/fonts/Heebo-VariableFont_wght.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]:
        if os.path.exists(p):
            f = ImageFont.truetype(p, size)
            try: f.set_variation_by_name("Bold")
            except Exception: pass
            return f
    return ImageFont.load_default()
def handset(size, color=(255, 255, 255, 255), angle=135):
    """classic phone icon: curved handset, earpiece upper-left, mouthpiece lower-right, curve bulging to the lower-left."""
    L = Image.new("RGBA", (size * 2, size * 2), (0, 0, 0, 0)); d = ImageDraw.Draw(L); c = size; r = int(size * 0.80); w = int(size * 0.27)
    cy = c + int(size * 0.25)
    d.arc((c - r, cy - r, c + r, cy + r), 205, 335, fill=color, width=w)
    for a in (205, 335):
        x = c + (r - w / 2) * math.cos(math.radians(a)); y = cy + (r - w / 2) * math.sin(math.radians(a))
        d.rounded_rectangle((x - w * 0.95, y - w * 0.2, x + w * 0.95, y + w * 1.15), int(w * 0.35), fill=color)
    return L.rotate(angle, resample=Image.BICUBIC)
def phone_layer(w=330, h=620, accent=(40, 205, 90), screen_top=(6, 40, 26), screen_bot=(2, 14, 10), caller=None):
    W, H = w * S, h * S; im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    rr = int(W * 0.15)
    d.rounded_rectangle((0, 0, W - 1, H - 1), rr, fill=(70, 78, 82, 255))                       # metal frame
    d.rounded_rectangle((int(W * .012), int(W * .012), W - 1 - int(W * .012), H - 1 - int(W * .012)), rr, fill=(10, 12, 14, 255))   # black body
    m = int(W * 0.035); sw, sh = W - 2 * m, H - 2 * m
    scr = Image.new("RGBA", (sw, sh), (0, 0, 0, 0)); sd = ImageDraw.Draw(scr)
    for y in range(sh):
        t = y / sh; sd.line([(0, y), (sw, y)], fill=tuple(int(screen_top[k] * (1 - t) + screen_bot[k] * t) for k in range(3)) + (255,))
    glow = Image.new("RGBA", (sw, sh), (0, 0, 0, 0)); ImageDraw.Draw(glow).ellipse((sw * .1, sh * .08, sw * .9, sh * .50), fill=accent + (70,)); glow = glow.filter(ImageFilter.GaussianBlur(sw * .10)); scr.alpha_composite(glow)
    sd = ImageDraw.Draw(scr)
    sd.rounded_rectangle((sw // 2 - int(sw * .17), int(sh * .02), sw // 2 + int(sw * .17), int(sh * .02) + int(sw * .085)), int(sw * .05), fill=(0, 0, 0, 255))   # dynamic island
    ic = handset(int(sw * 0.25), (255, 255, 255, 255), 135); icx, icy = int(sw * 0.43), int(sh * 0.28)
    gl = Image.new("RGBA", scr.size, (0, 0, 0, 0)); gl.paste(ic, (icx - ic.width // 2, icy - ic.height // 2), ic); gl = gl.filter(ImageFilter.GaussianBlur(sw * .03)); scr.alpha_composite(gl)
    scr.paste(ic, (icx - ic.width // 2, icy - ic.height // 2), ic)
    sd = ImageDraw.Draw(scr)
    for k, rad in enumerate((0.13, 0.20, 0.27)):   # 3 sound waves up-right of the handset
        cx_, cy_ = icx + int(sw * .02), icy - int(sw * .02); R = int(sw * rad)
        sd.arc((cx_ - R, cy_ - R, cx_ + R, cy_ + R), 295, 355, fill=(255, 255, 255, 255 - 25 * k), width=max(6, int(sw * .028)))
    if caller:
        sd.text((sw // 2, int(sh * .52)), caller, font=_font(int(sw * .16)), fill=(255, 255, 255, 255), anchor="mm", direction="rtl", language="he")
    bx0, bx1, by0, by1 = int(sw * .12), int(sw * .88), int(sh * .72), int(sh * .72) + int(sw * .27)    # one wide green call button
    sd.rounded_rectangle((bx0, by0, bx1, by1), int((by1 - by0) / 2), fill=accent + (255,))
    hb = handset(int(sw * 0.115), (255, 255, 255, 255), 135); scr.paste(hb, ((bx0 + bx1) // 2 - hb.width // 2, (by0 + by1) // 2 - hb.height // 2), hb)
    mask = Image.new("L", scr.size, 0); ImageDraw.Draw(mask).rounded_rectangle((0, 0, sw - 1, sh - 1), rr - m, fill=255)
    im.paste(scr, (m, m), mask)
    sh_ = Image.new("RGBA", im.size, (0, 0, 0, 0)); sd2 = ImageDraw.Draw(sh_)   # glossy reflection on the glass
    sd2.polygon([(m, m), (int(W * .55), m), (m, int(H * .32))], fill=(255, 255, 255, 22)); im.alpha_composite(Image.composite(sh_, Image.new("RGBA", im.size, (0, 0, 0, 0)), im.getchannel("A")))
    return im.resize((w, h), Image.LANCZOS)
def paste_phone(img, xy=(40, 60), size=(330, 620), tilt=-3, glow=(40, 230, 90), accent=(40, 205, 90), caller=None, **kw):
    ph = phone_layer(330, 620, accent=accent, caller=caller).resize(size, Image.LANCZOS).rotate(tilt, resample=Image.BICUBIC, expand=True)
    g = Image.new("RGBA", ph.size, glow + (255,)); g.putalpha(ph.getchannel("A").filter(ImageFilter.MaxFilter(21)))
    gl = Image.new("RGBA", img.size, (0, 0, 0, 0)); gl.paste(g, xy, g); gl = gl.filter(ImageFilter.GaussianBlur(30)); gl.putalpha(gl.getchannel("A").point(lambda v: min(255, int(v * 1.7))))
    base = img.convert("RGBA"); base.alpha_composite(gl); base.alpha_composite(ph, xy)
    return base.convert("RGB"), (xy[0], xy[1], xy[0] + ph.width, xy[1] + ph.height)
if __name__ == "__main__":
    bg = Image.new("RGB", (1280, 720), (8, 40, 24)); paste_phone(bg, xy=(60, 50), size=(340, 640))[0].save(sys.argv[1] if len(sys.argv) > 1 else "/tmp/phone_ui_test.jpg")

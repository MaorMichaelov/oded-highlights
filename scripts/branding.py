#!/usr/bin/env python3
"""Channel branding for long videos (cheap: PIL frames + ffmpeg, no paid assets).

  intro (~2.6s): dark background with rotating light rays, channel logo,
                 camcorder corner brackets, blinking REC dot + running
                 timecode, bottom banner 'הרגעים הכי טובים של <name>',
                 synthesized whoosh.
  like/sub overlay (~4s, top of frame) right after the intro: speech bubble
                 'תנו לייק וסאב!', like + subscribe buttons and the logo.
                 No fake counts.

  brand_long(src, dest)  -> intro + src with the overlay on its first 4s.
  Per-channel look comes from config (STREAMER_NAME_HE, CHANNEL).
"""
from __future__ import annotations

import json
import math
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from config import CHANNEL, STREAMER_NAME_HE

FONT = "/usr/share/fonts/truetype/sand-box/google/IBM Plex Sans Hebrew/IBMPlexSansHebrew-Bold.ttf"
MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
THEMES = {
    "ronengg": {"logo": "/workspace/ronen_research/ronen_highlights_logo_v2.jpg", "accent": (255, 122, 20)},
    "odedsvr": {"logo": "/workspace/oded_research/oded_highlights_logo.jpg", "accent": (120, 230, 40)},
}
# Maor's chosen final logo wins when present.
_rf = Path("/workspace/ronen_research/ronen_highlights_logo_final.jpg")
if _rf.is_file():
    THEMES["ronengg"]["logo"] = str(_rf)
INTRO_SEC = 2.6
OVERLAY_SEC = 4.0


def _font(size, path=FONT):
    try:
        return ImageFont.truetype(path, size, layout_engine=ImageFont.Layout.RAQM)
    except Exception:
        return ImageFont.truetype(path, size)


def _rtl(draw, xy, text, font, fill, anchor="mm", **kw):
    # RAQM does the bidi/shaping; direction rtl keeps punctuation on the right side
    draw.text(xy, text, font=font, fill=fill, anchor=anchor, direction="rtl", features=["-kern"], **kw)


def _circle_logo(path, size):
    im = Image.open(path).convert("RGB").resize((size, size), Image.LANCZOS)
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).ellipse((0, 0, size - 1, size - 1), fill=255)
    out = Image.new("RGBA", (size, size))
    out.paste(im, (0, 0), m)
    return out


def _probe(src):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                          "stream=codec_type,width,height,r_frame_rate,sample_rate,channels",
                          "-of", "json", str(src)], capture_output=True, text=True).stdout
    st = json.loads(out)["streams"]
    v = next(s for s in st if s["codec_type"] == "video")
    a = next((s for s in st if s["codec_type"] == "audio"), {})
    n, d = v["r_frame_rate"].split("/")
    return int(v["width"]), int(v["height"]), float(n) / float(d), int(a.get("sample_rate", 48000)), int(a.get("channels", 2))


def intro_frame(i, fps, W, H, theme, name_he, logo_cache={}, fades=True):
    t = i / fps
    acc = theme["accent"]
    img = Image.new("RGB", (W, H), (8, 6, 10))
    # light rays
    rays = Image.new("L", (W, H), 0)
    rd = ImageDraw.Draw(rays)
    cx, cy, R = W / 2, H * 0.45, W
    for k in range(14):
        a0 = k * (2 * math.pi / 14) + t * 0.35
        rd.polygon([(cx, cy), (cx + R * math.cos(a0), cy + R * math.sin(a0)),
                    (cx + R * math.cos(a0 + 0.11), cy + R * math.sin(a0 + 0.11))], fill=70)
    rays = rays.filter(ImageFilter.GaussianBlur(18))
    glow = Image.new("RGB", (W, H), acc)
    img = Image.composite(glow, img, rays)
    # center glow
    g = Image.new("L", (W, H), 0)
    ImageDraw.Draw(g).ellipse((cx - 260, cy - 260, cx + 260, cy + 260), fill=110)
    img = Image.composite(glow, img, g.filter(ImageFilter.GaussianBlur(80)))
    d = ImageDraw.Draw(img)
    # logo pop-in
    sc = min(1.0, 0.75 + 0.25 * (t / 0.35)) if t < 0.35 else 1.0 + 0.015 * math.sin(t * 6)
    size = int(H * 0.46 * sc)
    key = (size, theme["logo"])
    if key not in logo_cache:
        logo_cache[key] = _circle_logo(theme["logo"], size)
    lg = logo_cache[key]
    ring = int(size * 0.035) + 4
    d.ellipse((cx - size / 2 - ring, cy - size / 2 - ring, cx + size / 2 + ring, cy + size / 2 + ring), fill=acc)
    img.paste(lg, (int(cx - size / 2), int(cy - size / 2)), lg)
    # camcorder corner brackets
    m, L, w = 36, 70, 6
    for (x, y, sx, sy) in [(m, m, 1, 1), (W - m, m, -1, 1), (m, H - m, 1, -1), (W - m, H - m, -1, -1)]:
        d.line([(x, y), (x + sx * L, y)], fill=(240, 240, 240), width=w)
        d.line([(x, y), (x, y + sy * L)], fill=(240, 240, 240), width=w)
    # REC + timecode
    if int(t * 2) % 2 == 0:
        d.ellipse((m + 24, m + 22, m + 50, m + 48), fill=(235, 30, 30))
    d.text((m + 62, m + 35), "REC", font=_font(30, MONO), fill=(245, 245, 245), anchor="lm")
    fr = int(round((t % 1) * fps))
    d.text((W - m - 24, m + 35), f"00:00:{int(t):02d}:{fr:02d}", font=_font(28, MONO), fill=(245, 245, 245), anchor="rm")
    # bottom banner slides up
    p = min(1.0, max(0.0, (t - 0.25) / 0.35))
    bh = 86
    by = H - 40 - bh * p - 10
    if p > 0:
        bw = int(W * 0.62)
        d.rounded_rectangle((cx - bw / 2, by, cx + bw / 2, by + bh), radius=22, fill=(15, 12, 14), outline=acc, width=5)
        _rtl(d, (cx, by + bh / 2 - 4), f"הרגעים הכי טובים של {name_he}", _font(46), (255, 255, 255))
    # fade from/to black
    fade = min(1.0, t / 0.15, max(0.0, (INTRO_SEC - t) / 0.25)) if fades else 1.0  # fades=False: Nov 13b wipes in/out
    if fade < 1:
        img = Image.blend(Image.new("RGB", (W, H)), img, fade)
    return img


def make_overlay_png(W, H, theme, dest):
    acc = theme["accent"]
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    bw, bh = int(W * 0.50), int(H * 0.15)
    x0, y0 = (W - bw) / 2 - 40, int(H * 0.04)
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((x0 + 6, y0 + 8, x0 + bw + 6, y0 + bh + 8), radius=40, fill=(0, 0, 0, 120))
    im = Image.alpha_composite(im, sh.filter(ImageFilter.GaussianBlur(8)))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((x0, y0, x0 + bw, y0 + bh), radius=40, fill=(255, 255, 255, 245), outline=acc + (255,), width=5)
    # bubble tail pointing to the logo on the right
    d.polygon([(x0 + bw - 8, y0 + bh * 0.45), (x0 + bw + 46, y0 + bh * 0.62), (x0 + bw - 8, y0 + bh * 0.8)],
              fill=(255, 255, 255, 245))
    _rtl(d, (x0 + bw * 0.66, y0 + bh / 2 - 4), "תנו לייק וסאב!", _font(int(bh * 0.40)), (20, 20, 20))
    # like button (thumb drawn with shapes) and subscribe pill
    lx, ly, lw, lh = x0 + 22, y0 + bh * 0.22, bh * 0.56 * 1.0, bh * 0.56
    d.rounded_rectangle((lx, ly, lx + lw, ly + lh), radius=int(lh / 2), fill=(30, 30, 30, 255))
    tx, ty, s = lx + lw * 0.22, ly + lh * 0.2, lh * 0.6
    d.rectangle((tx, ty + s * 0.42, tx + s * 0.22, ty + s), fill=(255, 255, 255, 255))
    d.rounded_rectangle((tx + s * 0.28, ty + s * 0.40, tx + s * 0.95, ty + s), radius=int(s * 0.12), fill=(255, 255, 255, 255))
    d.polygon([(tx + s * 0.30, ty + s * 0.45), (tx + s * 0.52, ty), (tx + s * 0.66, ty + s * 0.08), (tx + s * 0.60, ty + s * 0.42)],
              fill=(255, 255, 255, 255))
    sx = lx + lw + 14
    sw = bw * 0.27
    d.rounded_rectangle((sx, ly, sx + sw, ly + lh), radius=int(lh / 2), fill=(230, 20, 30, 255))
    _rtl(d, (sx + sw / 2, ly + lh / 2 - 2), "הרשמה", _font(int(lh * 0.5)), (255, 255, 255))
    # logo on the side
    ls = int(bh * 1.05)
    lg = _circle_logo(theme["logo"], ls)
    ring = Image.new("RGBA", (ls + 12, ls + 12), (0, 0, 0, 0))
    ImageDraw.Draw(ring).ellipse((0, 0, ls + 11, ls + 11), fill=acc + (255,))
    rx, ry = int(x0 + bw + 50), int(y0 + bh / 2 - ls / 2 - 6)
    im.alpha_composite(ring, (rx, ry))
    im.alpha_composite(lg, (rx + 6, ry + 6))
    im.save(dest)
    return dest


def make_intro(dest, W, H, fps, sr, ch, theme, name_he, fades=True):
    tmp = Path(tempfile.mkdtemp(prefix="intro_"))
    n = int(round(INTRO_SEC * fps))
    for i in range(n):
        intro_frame(i, fps, W, H, theme, name_he, fades=fades).save(tmp / f"f{i:04d}.png")
    # whoosh: band-passed pink noise with a fast swell, plus a low boom
    af = (f"anoisesrc=d={INTRO_SEC}:c=pink:a=0.6:r={sr},highpass=f=250,lowpass=f=4500,"
          f"afade=t=in:st=0:d=0.35:curve=exp,afade=t=out:st=0.45:d=0.9,volume=1.4[n];"
          f"sine=f=55:d={INTRO_SEC}:r={sr},afade=t=in:st=0.3:d=0.05,afade=t=out:st=0.4:d=1.0,volume=0.8[b];"
          f"[n][b]amix=inputs=2:normalize=0,apad=whole_dur={INTRO_SEC},"
          f"aformat=channel_layouts={'stereo' if ch == 2 else 'mono'}[a]")
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-framerate", f"{fps}",
                    "-i", str(tmp / "f%04d.png"), "-filter_complex", af, "-map", "0:v", "-map", "[a]",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-r", f"{fps}",
                    "-c:a", "aac", "-b:a", "160k", "-ar", str(sr), "-t", f"{INTRO_SEC}", str(dest)], check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    return dest


def brand_long(src, dest, workdir=None):
    src, dest = Path(src), Path(dest)
    theme = THEMES.get(CHANNEL, THEMES["odedsvr"])
    W, H, fps, sr, ch = _probe(src)
    work = Path(workdir or tempfile.mkdtemp(prefix="brand_"))
    work.mkdir(parents=True, exist_ok=True)
    intro = make_intro(work / "intro.mp4", W, H, fps, sr, ch, theme, STREAMER_NAME_HE)
    ov = make_overlay_png(W, H, theme, work / "overlay.png")
    # first keyframe after the overlay ends -> re-encode only the head
    kf = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-skip_frame", "nokey",
                         "-show_entries", "frame=pts_time", "-of", "csv=p=0", "-read_intervals", "%+30", str(src)],
                        capture_output=True, text=True).stdout.split()
    K = next((float(x) for x in kf if float(x) >= OVERLAY_SEC + 0.3), None)
    head, tail = work / "head.mp4", work / "tail.mp4"
    fc = (f"[1:v]format=rgba,fade=t=in:st=0:d=0.45:alpha=1,fade=t=out:st={OVERLAY_SEC - 0.5}:d=0.5:alpha=1[o];"
          f"[0:v][o]overlay=x=0:y='-40+40*min(1,t/0.45)':enable='lte(t,{OVERLAY_SEC})':eof_action=pass,format=yuv420p[v]")
    common = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-r", f"{fps}",
              "-c:a", "aac", "-b:a", "160k", "-ar", str(sr)]
    if K is None:  # no usable keyframe: re-encode everything
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(src), "-loop", "1",
                        "-t", f"{OVERLAY_SEC}", "-i", str(ov), "-filter_complex", fc, "-map", "[v]", "-map", "0:a?",
                        *common, str(head)], check=True)
        parts = [intro, head]
    else:
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(src), "-loop", "1",
                        "-t", f"{OVERLAY_SEC}", "-i", str(ov), "-filter_complex", fc, "-map", "[v]", "-map", "0:a?",
                        "-t", f"{K:.3f}", *common, str(head)], check=True)
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{K:.3f}", "-i", str(src),
                        "-c", "copy", "-avoid_negative_ts", "make_zero", str(tail)], check=True)
        parts = [intro, head, tail]
    lst = work / "list.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c", "copy", "-movflags", "+faststart", str(dest)], check=True)
    return dest, {"intro_sec": INTRO_SEC, "overlay_sec": OVERLAY_SEC, "split_keyframe": K, "work": str(work)}


def brand_concat(parts, dest, workdir=None):
    """One re-encode pass: intro + parts (overlay on the first OVERLAY_SEC of part 1).
    Uses the concat filter, so parts with different timestamps join cleanly."""
    parts = [Path(p) for p in parts]
    theme = THEMES.get(CHANNEL, THEMES["odedsvr"])
    W, H, fps, sr, ch = _probe(parts[0])
    work = Path(workdir or tempfile.mkdtemp(prefix="brand_"))
    work.mkdir(parents=True, exist_ok=True)
    intro = make_intro(work / "intro.mp4", W, H, fps, sr, ch, theme, STREAMER_NAME_HE)
    ov = make_overlay_png(W, H, theme, work / "overlay.png")
    args = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(intro)]
    for p in parts:
        args += ["-i", str(p)]
    args += ["-loop", "1", "-t", f"{OVERLAY_SEC}", "-i", str(ov)]
    n = len(parts)
    oi = n + 1
    fc = [f"[{oi}:v]format=rgba,fade=t=in:st=0:d=0.45:alpha=1,fade=t=out:st={OVERLAY_SEC - 0.5}:d=0.5:alpha=1[o]",
          f"[1:v][o]overlay=x=0:y='-40+40*min(1,t/0.45)':eof_action=pass,format=yuv420p,setsar=1[v1]",
          "[0:v]format=yuv420p,setsar=1[v0]"]
    for k in range(2, n + 1):
        fc.append(f"[{k}:v]format=yuv420p,setsar=1[v{k}]")
    for k in range(0, n + 1):
        fc.append(f"[{k}:a]aresample={sr},aformat=sample_fmts=fltp:channel_layouts=stereo[a{k}]")
    fc.append("".join(f"[v{k}][a{k}]" for k in range(n + 1)) + f"concat=n={n + 1}:v=1:a=1[vout][aout]")
    args += ["-filter_complex", ";".join(fc), "-map", "[vout]", "-map", "[aout]",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", f"{fps}",
             "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(dest)]
    subprocess.run(args, check=True)
    return dest


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("dest")
    ap.add_argument("--preview", action="store_true", help="only write preview frames to dest dir")
    a = ap.parse_args()
    if a.preview:
        out = Path(a.dest); out.mkdir(parents=True, exist_ok=True)
        theme = THEMES.get(CHANNEL, THEMES["odedsvr"])
        for i in (20, 70, 130):
            intro_frame(i, 60, 1280, 720, theme, STREAMER_NAME_HE).save(out / f"intro_{i}.png")
        make_overlay_png(1280, 720, theme, out / "overlay.png")
    else:
        print(brand_long(a.src, a.dest))

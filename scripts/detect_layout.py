#!/usr/bin/env python3
"""Detect facecam / content crop boxes from a sample frame of Oded's layout.

Writes fractions of width/height (so the same file works at 720p and 1080p).
Falls back to the measured default if detection is not confident.

Facecam is the webcam window only — the Kick chat strip under the cam is
trimmed off. In the full-screen game + overlay layout, the content box is a
zoomed gameplay crop that excludes the original cam (and the chat under it).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from config import DEFAULT_LAYOUT


def _skin_mask(a: np.ndarray) -> np.ndarray:
    r, g, b = a[:, :, 0].astype(np.int16), a[:, :, 1].astype(np.int16), a[:, :, 2].astype(np.int16)
    return (
        (r > 95)
        & (g > 40)
        & (b > 20)
        & (r > g)
        & (r > b)
        & ((r - g).clip(0) > 15)
        & ((r - np.minimum(g, b)) > 15)
    )


def _iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    inter = max(0, ix1 - ix0) * max(0, iy1 - iy0)
    area_a = max(0, ax1 - ax0) * max(0, ay1 - ay0)
    area_b = max(0, bx1 - bx0) * max(0, by1 - by0)
    den = area_a + area_b - inter
    return inter / den if den else 0.0


def _frac_box(layout_box: dict, w: int, h: int) -> tuple[int, int, int, int]:
    x0 = int(layout_box["x"] * w)
    y0 = int(layout_box["y"] * h)
    x1 = int((layout_box["x"] + layout_box["w"]) * w)
    y1 = int((layout_box["y"] + layout_box["h"]) * h)
    return x0, y0, x1, y1


def _row_chat_features(a: np.ndarray, y: int, x0: int, x1: int) -> tuple[float, float, float, float]:
    """mean, std, green-badge fraction, white-text fraction for one row."""
    row = a[y, x0:x1]
    r = row[:, 0].astype(np.int16)
    g = row[:, 1].astype(np.int16)
    b = row[:, 2].astype(np.int16)
    gray = 0.3 * r + 0.59 * g + 0.11 * b
    greenish = float(((g > r + 20) & (g > b + 10) & (g > 80)).mean())
    white = float(((r > 180) & (g > 180) & (b > 180)).mean())
    return float(gray.mean()), float(gray.std()), greenish, white


def trim_chat_below_cam(a: np.ndarray, x0: int, y0: int, x1: int, y1: int) -> int:
    """Return a new y1 that stops above the Kick chat strip under the cam.

    Chat is recognized by Kick's green badges, white caption text, or a sudden
    jump from the dark shirt/window bottom to a bright overlay.
    """
    h, w = a.shape[:2]
    # Stay inside the cam horizontally so game pixels left of the window
    # don't hide the overlay.
    ix0 = min(x1 - 8, max(x0 + int((x1 - x0) * 0.10), x0))
    ix1 = x1
    if ix1 - ix0 < 16:
        return y1
    # Start in the lower part of the cam so mid-face overlays (or green UI
    # that happens to sit on the shirt) are not treated as the chat strip.
    search_lo = max(y0 + int((y1 - y0) * 0.62), 0)
    search_hi = min(h - 1, y1 + int(h * 0.14))
    prev: list[float] = []
    chat_y = None
    for y in range(search_lo, search_hi):
        mean, _std, green, white = _row_chat_features(a, y, ix0, ix1)
        baseline = sum(prev[-8:]) / max(1, len(prev[-8:])) if prev else mean
        jumped = bool(prev) and (mean - baseline > 40) and mean > 85
        is_chat = (green >= 0.010) or (white >= 0.035 and mean > 90) or jumped
        if is_chat:
            chat_y = y
            break
        prev.append(mean)
    # Last row with real skin — do not crop above this (would cut the face).
    skin = _skin_mask(a)
    band = skin[y0:y1, ix0:ix1]
    skin_bottom = y0
    if band.size:
        rows = np.where(band.mean(axis=1) >= 0.08)[0]
        if len(rows):
            skin_bottom = y0 + int(rows[-1])
    if chat_y is not None:
        # A couple of pixels above the first chat row, so the divider is clean.
        trimmed = min(y1, chat_y - 2)
        # Keep at least a little shirt below the face; never cut into it.
        return max(y0 + 8, max(trimmed, skin_bottom + int(h * 0.015)))
    return max(y1, skin_bottom + int(h * 0.015)) if skin_bottom > y0 else y1


def find_cam_window_bottom(
    gray: np.ndarray,
    a: np.ndarray,
    x0: int,
    y0: int,
    x1: int,
    h: int,
    default_y1: int,
) -> int:
    """Bottom of the cam *window*, not the face and not the chat under it.

    Primary cue: a strong horizontal edge (the window frame). Kick chat is
    used only to trim a couple of pixels if it sits just below that edge.
    Mid-cam green UI or badges are ignored.
    """
    chat_y1 = trim_chat_below_cam(a, x0, y0, x1, default_y1)
    ix0 = x0 + int(max(4, (x1 - x0) * 0.08))
    ix1 = x1
    if ix1 - ix0 < 16:
        return chat_y1
    search_lo = y0 + int(max(20, (default_y1 - y0) * 0.55))
    search_hi = min(h - 2, max(default_y1, y0 + int(h * 0.22)) + int(h * 0.10))
    search_lo = max(y0 + 20, min(search_lo, search_hi - 5))
    # Take the FIRST strong horizontal edge (window frame). Chat text below
    # it can have an even sharper gradient, which must not win.
    for y in range(search_lo, search_hi):
        above = gray[max(0, y - 2), ix0:ix1]
        below = gray[min(gray.shape[0] - 1, y + 2), ix0:ix1]
        grad = float(np.abs(below - above).mean())
        dark_jump = abs(float((above < 45).mean()) - float((below < 45).mean()))
        mean_jump = abs(float(below.mean()) - float(above.mean()))
        if grad >= 22 and (dark_jump >= 0.18 or mean_jump >= 18):
            if chat_y1 < y - int(h * 0.04):
                return y
            return min(y, chat_y1)
    return chat_y1


def refine_cam_left(gray: np.ndarray, x0: int, y0: int, x1: int, y1: int, w: int) -> int:
    """Snap the left edge to the dark window border, if one is visible."""
    my0 = y0 + int((y1 - y0) * 0.18)
    my1 = y0 + int((y1 - y0) * 0.78)
    if my1 - my0 < 12:
        return x0
    # Only search a tight band around the current left edge. A wider search
    # can snap to the chair inside the window (or a dark game UI).
    search_lo = max(0, x0 - int(w * 0.05))
    search_hi = min(x1 - 8, x0 + int(w * 0.045))
    # Take the LEFTMOST strong border (game -> dark window frame). A later,
    # darker column inside the chair would otherwise pull the box in too far.
    for x in range(search_lo, search_hi):
        col = gray[my0:my1, x]
        dark = float((col < 45).mean())
        mean = float(col.mean())
        if x > 4:
            left_mean = float(gray[my0:my1, max(0, x - 6):x].mean())
        else:
            left_mean = mean
        if dark >= 0.28 and left_mean > mean + 20:
            return min(x1 - 16, max(0, x + 2))
    return x0


def gameplay_box_excluding_cam(
    w: int, h: int, fx0: int, fy0: int, fx1: int, fy1: int, target_aspect: float = 1.20
) -> tuple[int, int, int, int]:
    """Crop/zoom the game so the original upper-right cam (and its chat) is out."""
    pad = int(max(8, w * 0.008))
    # Chat under the cam typically covers ~half the cam height again.
    chat_extra = int(max((fy1 - fy0) * 0.55, h * 0.10))
    ex0 = max(0, fx0 - pad)
    # Typical odedsvr overlay: cam is in the upper right.
    cam_cx = 0.5 * (fx0 + fx1)
    if ex0 >= int(w * 0.40) and cam_cx > w * 0.50:
        avail_x0, avail_x1 = 0, ex0
        avail_y0, avail_y1 = 0, h
        avail_w = avail_x1 - avail_x0
        avail_h = avail_y1 - avail_y0
        crop_h = avail_h
        crop_w = int(round(crop_h * target_aspect))
        if crop_w > avail_w:
            crop_w = avail_w
            crop_h = int(round(crop_w / max(target_aspect, 0.1)))
            cy0 = avail_y0 + max(0, (avail_h - crop_h) // 2)
            return avail_x0, cy0, avail_x0 + crop_w, cy0 + crop_h
        # Right-align against the cam so we keep the action near frame center.
        cx0 = avail_x1 - crop_w
        return cx0, avail_y0, avail_x1, avail_y0 + crop_h
    # Cam not on the right: take the largest rectangle that does not overlap
    # the cam+chat exclusion (upper band of the cam's x-range).
    ex1, ey0, ey1 = min(w, fx1 + pad), max(0, fy0 - pad), min(h, fy1 + chat_extra)
    # Prefer the region to the left of the cam if it is wide enough.
    if ex0 >= int(w * 0.35):
        return 0, 0, ex0, h
    # Otherwise the region below the cam+chat.
    if h - ey1 >= int(h * 0.40):
        return 0, ey1, w, h
    return 0, 0, ex0 if ex0 > 8 else w, h


def detect(frame_path: Path) -> dict:
    im = Image.open(frame_path).convert("RGB")
    a = np.array(im)
    h, w = a.shape[:2]
    gray = (0.3 * a[:, :, 0] + 0.59 * a[:, :, 1] + 0.11 * a[:, :, 2]).astype(np.float32)
    skin = _skin_mask(a)

    default_px = _frac_box(DEFAULT_LAYOUT["facecam"], w, h)
    source = "detected"

    def skin_bbox(x_lo, y_lo, x_hi, y_hi, p_lo=4, p_hi=98):
        region = skin[y_lo:y_hi, x_lo:x_hi]
        if region.size == 0:
            return None, 0
        # Require a column/row to be actually face-like, so sparse Minecraft
        # "skin" pixels on the left do not pull the box open.
        col = region.mean(axis=0)
        row = region.mean(axis=1)
        xs = np.where(col >= 0.12)[0]
        ys = np.where(row >= 0.12)[0]
        if len(xs) < 8 or len(ys) < 8:
            return None, 0
        x0 = x_lo + int(xs[0])
        x1 = x_lo + int(xs[-1]) + 1
        y0 = y_lo + int(ys[0])
        y1 = y_lo + int(ys[-1]) + 1
        pad_x, pad_y = int(w * 0.006), int(h * 0.01)
        x0, y0 = max(0, x0 - pad_x), max(0, y0 - pad_y)
        x1, y1 = min(w, x1 + pad_x), min(h, y1 + pad_y)
        return (x0, y0, x1, y1), float(skin[y0:y1, x0:x1].mean()) if x1 > x0 and y1 > y0 else 0

    # 1) Refine around the known cam box (padded ~18%). This is the usual
    #    odedsvr desktop layout and avoids Minecraft blocks being read as skin.
    dx0, dy0, dx1, dy1 = default_px
    padw, padh = int((dx1 - dx0) * 0.18), int((dy1 - dy0) * 0.25)
    local, local_skin = skin_bbox(
        max(0, dx0 - padw), max(0, dy0 - padh),
        min(w, dx1 + padw), min(h, dy1 + padh),
    )
    # 2) Wide search only if the default region has almost no skin (layout changed).
    wide = None
    wide_skin = 0
    if local is None or local_skin < 0.08:
        wide, wide_skin = skin_bbox(int(w * 0.58), int(h * 0.04), w - 2, int(h * 0.42))

    def ok_box(b):
        if not b:
            return False
        x0, y0, x1, y1 = b
        bw, bh = x1 - x0, y1 - y0
        aspect = bw / max(bh, 1)
        return (
            bw >= int(w * 0.14)
            and bh >= int(h * 0.12)
            and 1.05 <= aspect <= 3.4
            and (y0 + y1) / 2 < h * 0.40
        )

    if local and ok_box(local) and local_skin >= 0.10:
        x0, y0, x1, y1 = local
        # Keep close to the measured cam horizontally so we don't open into the game,
        # but do not extend downward — that is how the chat strip used to leak in.
        x0 = max(dx0 - int(w * 0.015), min(x0, dx0 + int(w * 0.01)))
        x1 = max(x1, dx1 - int(w * 0.005))
        x1 = min(w, x1)
        y0 = max(dy0 - int(h * 0.05), min(y0, dy0 + int(h * 0.02)))
        y0 = max(0, y0)
        # Never force y1 down toward the default if the default already includes chat.
        y1 = min(y1, dy1)
        source = f"refined_default_skin{local_skin:.2f}"
        skin_bottom_hint = y1
    elif wide and ok_box(wide) and wide_skin >= 0.12:
        x0, y0, x1, y1 = wide
        source = f"wide_search_skin{wide_skin:.2f}"
    else:
        x0, y0, x1, y1 = default_px
        source = "fallback_default"

    # Precise edges: window border on the left, window bottom (above chat).
    x0 = refine_cam_left(gray, x0, y0, x1, y1, w)
    # Hint with the measured default bottom so a short skin box (face only)
    # does not hide the real window edge.
    y1 = find_cam_window_bottom(gray, a, x0, y0, x1, h, dy1)
    inset = max(1, int(h * 0.004))
    y1 = max(y0 + 8, y1 - inset)
    source = source + "+nochat"

    # Content crop. Two common layouts on this channel:
    # - desktop capture (browser + taskbar): game is the left window
    # - full-screen game with a facecam overlay: zoom gameplay, exclude the cam
    bottom = gray[int(h * 0.90) :, :]
    bottom_mean = float(bottom.mean())
    # A Windows taskbar is a dark mid-gray strip with a fairly flat profile.
    # Game HUDs are usually brighter or more varied.
    taskbarish = bottom_mean < 58
    if not taskbarish:
        cx0, cy0, cx1, cy1 = gameplay_box_excluding_cam(w, h, x0, y0, x1, y1)
        source = source + "+content_gameplay"
    elif source.startswith("fallback"):
        cx0, cy0, cx1, cy1 = _frac_box(DEFAULT_LAYOUT["content"], w, h)
    else:
        cx0 = int(w * 0.02)
        if float(gray[:, : int(w * 0.08)].mean()) < 30:
            cx0 = int(w * 0.10)
        cy0 = int(h * 0.10)
        cx1 = max(int(x0 * 0.99), cx0 + int(w * 0.35))
        cy1 = int(h * 0.84)

    def box(x0_, y0_, x1_, y1_):
        x0_, y0_ = max(0, x0_), max(0, y0_)
        x1_, y1_ = min(w, x1_), min(h, y1_)
        if x1_ <= x0_:
            x1_ = min(w, x0_ + 2)
        if y1_ <= y0_:
            y1_ = min(h, y0_ + 2)
        return {
            "x": round(x0_ / w, 4),
            "y": round(y0_ / h, 4),
            "w": round((x1_ - x0_) / w, 4),
            "h": round((y1_ - y0_) / h, 4),
            "px": [int(x0_), int(y0_), int(x1_), int(y1_)],
        }

    return {
        "facecam": box(x0, y0, x1, y1),
        "content": box(cx0, cy0, cx1, cy1),
        "source": source,
        "frame": str(frame_path),
        "frame_size": [int(w), int(h)],
    }


def save_debug(frame_path: Path, layout: dict, out_path: Path) -> None:
    im = Image.open(frame_path).convert("RGB")
    w, h = im.size
    draw = ImageDraw.Draw(im)

    def rect(key, color):
        b = layout[key]
        x0, y0 = b["x"] * w, b["y"] * h
        x1, y1 = x0 + b["w"] * w, y0 + b["h"] * h
        draw.rectangle([x0, y0, x1, y1], outline=color, width=4)
        draw.text((x0 + 6, y0 + 6), key, fill=color)

    rect("facecam", (0, 255, 0))
    rect("content", (255, 220, 0))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    im.save(out_path, quality=90)


def load_layout(path: Path | None) -> dict:
    if path and path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return json.loads(json.dumps(DEFAULT_LAYOUT))


def pix_box(layout: dict, key: str, width: int, height: int) -> tuple[int, int, int, int]:
    b = layout[key]
    x = int(round(b["x"] * width))
    y = int(round(b["y"] * height))
    w = int(round(b["w"] * width))
    h = int(round(b["h"] * height))
    # clip
    x = max(0, min(x, width - 2))
    y = max(0, min(y, height - 2))
    w = max(2, min(w, width - x))
    h = max(2, min(h, height - y))
    return x, y, w, h


def content_overlaps_cam(layout: dict, width: int, height: int, min_iou: float = 0.02) -> bool:
    fx, fy, fw, fh = pix_box(layout, "facecam", width, height)
    cx, cy, cw, ch = pix_box(layout, "content", width, height)
    return _iou((fx, fy, fx + fw, fy + fh), (cx, cy, cx + cw, cy + ch)) > min_iou


def ensure_gameplay_excludes_cam(layout: dict, width: int, height: int) -> dict:
    """If the content crop still contains the cam, replace it with a zoomed gameplay box."""
    if "facecam" not in layout or "content" not in layout:
        return layout
    if not content_overlaps_cam(layout, width, height):
        return layout
    fx, fy, fw, fh = pix_box(layout, "facecam", width, height)
    x0, y0, x1, y1 = gameplay_box_excluding_cam(width, height, fx, fy, fx + fw, fy + fh)
    layout = json.loads(json.dumps(layout))
    layout["content"] = {
        "x": round(x0 / width, 4),
        "y": round(y0 / height, 4),
        "w": round((x1 - x0) / width, 4),
        "h": round((y1 - y0) / height, 4),
        "px": [int(x0), int(y0), int(x1), int(y1)],
    }
    src = str(layout.get("source") or "")
    if "content_gameplay" not in src:
        layout["source"] = src + "+content_gameplay_fix"
    return layout


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("frame", type=Path)
    p.add_argument("-o", "--out", type=Path, default=None)
    p.add_argument("--debug", type=Path, default=None)
    args = p.parse_args()
    if not args.frame.is_file():
        print(f"ERROR: frame not found: {args.frame}", file=sys.stderr)
        return 1
    layout = detect(args.frame)
    text = json.dumps(layout, ensure_ascii=False, indent=2)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {args.out}")
    if args.debug:
        save_debug(args.frame, layout, args.debug)
        print(f"wrote debug {args.debug}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

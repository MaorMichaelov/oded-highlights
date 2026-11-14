#!/usr/bin/env python3
"""Real-photo plates from Poly Haven HDRIs (CC0, free, API only, unique User-Agent per their API terms).
Downloads the tonemapped 360 JPG, projects a 16:9 perspective view (yaw/pitch/fov), darkens the left side for the portrait.
usage: thumb_hdri.py --id stadium_01 --yaw 30 --pitch 5 --fov 75 --out plate.jpg [--cache dir]"""
import argparse, os, subprocess, sys
import numpy as np, cv2
from PIL import Image
UA = "oded-highlights-thumbnail-pipeline/1.0 (contact: repo owner)"
def fetch(aid, cache):
    os.makedirs(cache, exist_ok=True); f = os.path.join(cache, aid + ".jpg")
    if not os.path.exists(f) or os.path.getsize(f) < 100000:
        url = f"https://dl.polyhaven.org/file/ph-assets/HDRIs/extra/Tonemapped%20JPG/{aid}.jpg"
        subprocess.run(["curl", "-sS", "-L", "-A", UA, "-m", "240", "-o", f, url], check=True)
    return f
def project(equi, yaw, pitch, fov, W=1920, H=1080):
    h, w = equi.shape[:2]; f = 0.5 * W / np.tan(np.radians(fov) / 2)
    xs, ys = np.meshgrid(np.arange(W) - W / 2, np.arange(H) - H / 2); z = np.full_like(xs, f, dtype=np.float32)
    d = np.stack([xs, ys, z], -1).astype(np.float32); d /= np.linalg.norm(d, axis=-1, keepdims=True)
    cy, sy, cp, sp = np.cos(np.radians(yaw)), np.sin(np.radians(yaw)), np.cos(np.radians(pitch)), np.sin(np.radians(pitch))
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]], np.float32); Rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]], np.float32)
    d = d @ (Ry @ Rx).T; lon = np.arctan2(d[..., 0], d[..., 2]); lat = np.arcsin(np.clip(-d[..., 1], -1, 1))
    mx = ((lon / (2 * np.pi) + 0.5) * w).astype(np.float32); my = ((0.5 - lat / np.pi) * h).astype(np.float32)
    return cv2.remap(equi, mx, my, cv2.INTER_AREA if False else cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
def plate(img, left=0.55, vign=0.3, sat=1.08):
    im = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)).resize((1280, 720), Image.LANCZOS)
    a = np.asarray(im).astype(np.float32) / 255
    g = (a.mean(2, keepdims=True)); a = np.clip(g + (a - g) * sat, 0, 1)
    x = np.linspace(0, 1, 1280)[None, :, None]; m = np.clip(1 - x / 0.52, 0, 1) ** 1.3; a = a * (1 - left * m)
    yy, xx = np.mgrid[0:720, 0:1280]; r = np.sqrt(((xx - 640) / 640) ** 2 + ((yy - 360) / 360) ** 2); a = a * (1 - vign * np.clip((r - 0.6) / 0.8, 0, 1))[..., None]
    return Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))
if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--id", required=True); ap.add_argument("--yaw", type=float, default=0); ap.add_argument("--pitch", type=float, default=0)
    ap.add_argument("--fov", type=float, default=75); ap.add_argument("--out", required=True); ap.add_argument("--cache", default=os.path.expanduser("~/.cache/polyhaven"))
    a = ap.parse_args(); eq = cv2.imread(fetch(a.id, a.cache)); eq = cv2.resize(eq, (4096, 2048), interpolation=cv2.INTER_AREA)
    plate(project(eq, a.yaw, a.pitch, a.fov)).save(a.out, quality=93); print("saved", a.out)

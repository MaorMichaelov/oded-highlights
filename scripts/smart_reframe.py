#!/usr/bin/env python3
"""Purposeful reframing for screen-share layouts (no arbitrary zoom).
Detects (a) the streamer's webcam box with YuNet and (b) the active content window with block frame-difference on sampled frames,
then composes a 1920x1080 frame: content window big (left ~70%) + webcam window (right, big, face visible) -> one stable layout for the whole clip.
If the layout is already a full-screen game (no small webcam overlay / content already fills the frame) it returns 'keep' and does nothing.
usage: smart_reframe.py IN.mp4 OUT.mp4 [--analyze-only]   writes OUT.mp4.layout.json"""
import argparse, json, os, subprocess, sys
import numpy as np, cv2
HERE = os.path.dirname(os.path.abspath(__file__)); YUNET = os.path.join(HERE, "models", "face_detection_yunet_2023mar.onnx")
ap = argparse.ArgumentParser(); ap.add_argument("inp"); ap.add_argument("out"); ap.add_argument("--analyze-only", action="store_true"); ap.add_argument("--enable", action="store_true", help="actually reframe (EXPERIMENTAL; off by default: detection is unstable on short/mixed clips)"); a = ap.parse_args()
cap = cv2.VideoCapture(a.inp); n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); fps = cap.get(cv2.CAP_PROP_FPS) or 60; W = int(cap.get(3)); H = int(cap.get(4))
idx = np.linspace(int(fps * 20), max(int(fps * 21), n - int(fps * 5)), 24).astype(int) if n > fps * 40 else np.linspace(0, max(1, n - 1), 12).astype(int)
frames = []
for i in idx:
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(i)); ok, f = cap.read()
    if ok: frames.append(f)
if len(frames) < 4: print("too few frames"); sys.exit(1)
det = cv2.FaceDetectorYN.create(YUNET, "", (W, H), 0.6, 0.3, 5000); per_frame = []
for f in frames:
    _, r = det.detect(f); per_frame.append([tuple(float(v) for v in x[:4]) for x in (r if r is not None else [])])
# webcam face = the face that stays at (almost) the same place in most frames; faces inside the shared content move/change
cands = []
for fr in per_frame:
    for (fx, fy, fw, fh) in fr: cands.append((fx + fw / 2, fy + fh / 2, fw, fh))
cam = None; best = (0, None)
for (cx, cy, fw, fh) in cands:
    hits = [1 for fr in per_frame if any(abs((x + w / 2) - cx) < 0.05 * W and abs((y + h / 2) - cy) < 0.07 * H for (x, y, w, h) in fr)]
    if len(hits) > best[0]: best = (len(hits), (cx, cy, fw, fh))
if best[1] and best[0] >= 0.6 * len(frames):
    cx, cy, fw, fh = best[1]; ch = int(min(H * 0.6, fh * 3.2)); cw = int(ch * 16 / 9); x0 = int(np.clip(cx - cw / 2, 0, W - cw)); y0 = int(np.clip(cy - ch * 0.42, 0, H - ch)); cam = (x0, y0, cw, ch, round(float(fw / W), 3))
# content window = block-activity bounding box excluding the webcam region
g = [cv2.cvtColor(cv2.resize(f, (480, 270)), cv2.COLOR_BGR2GRAY).astype(np.float32) for f in frames]
act = np.zeros_like(g[0])
for p, q in zip(g, g[1:]): act += np.abs(p - q)
act = cv2.GaussianBlur(act, (0, 0), 3); thr = max(8.0, float(np.percentile(act, 70)))
m = (act > thr).astype(np.uint8)
if cam: sx, sy = 480 / W, 270 / H; m[int(cam[1] * sy):int((cam[1] + cam[3]) * sy), int(cam[0] * sx):int((cam[0] + cam[2]) * sx)] = 0
m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8)); cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
content = None
if cnts:
    c = max(cnts, key=cv2.contourArea); x, y, w, h = cv2.boundingRect(c)
    if w * h > 0.12 * 480 * 270: content = (int(x / 480 * W), int(y / 270 * H), int(w / 480 * W), int(h / 270 * H))
layout = {"cam": cam, "content": content, "src": [W, H]}
small_cam = cam is not None and cam[4] < 0.10                      # webcam face is tiny relative to the frame -> screen-share style layout
fills = content is not None and content[2] * content[3] > 0.85 * W * H
layout["action"] = "reframe" if (a.enable and small_cam and content and not fills) else "keep"
json.dump(layout, open(a.out + ".layout.json", "w"), indent=1); print(json.dumps(layout))
if a.analyze_only or layout["action"] == "keep":
    if layout["action"] == "keep" and not a.analyze_only: subprocess.run(["cp", a.inp, a.out])
    sys.exit(0)
cx0, cy0, cw0, ch0 = content
# snap the content window to 16:9 inside the source, then compose: content 1296x729 left, webcam 624x351 top-right, blurred content as background
ar = 16 / 9
if cw0 / ch0 > ar: nh = int(cw0 / ar); cy0 = int(np.clip(cy0 - (nh - ch0) / 2, 0, H - nh)); ch0 = nh
else: nw = int(ch0 * ar); cx0 = int(np.clip(cx0 - (nw - cw0) / 2, 0, W - nw)); cw0 = nw
cx0 = int(np.clip(cx0, 0, W - cw0)); cy0 = int(np.clip(cy0, 0, H - ch0))
fc = (f"[0:v]split=3[a][b][c];[a]crop={cw0}:{ch0}:{cx0}:{cy0},scale=1296:729[main];"
      f"[b]crop={cam[2]}:{cam[3]}:{cam[0]}:{cam[1]},scale=576:324[face];"
      f"[c]scale=1920:1080,boxblur=40:5,eq=brightness=-0.15[bg];"
      f"[bg][main]overlay=24:176[t1];[t1][face]overlay=1344:176[o]")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", a.inp, "-filter_complex", fc, "-map", "[o]", "-map", "0:a", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "copy", a.out], check=True)
print("reframed ->", a.out)

#!/usr/bin/env python3
"""Game video thumbnail (owner's style): the GAME is the background (a 1080p gameplay frame without webcam/chat), a big sharp AI portrait of the
streamer on the left, game logo text bottom-right.  usage: thumb_game.py --frame game.png --face face.jpg --logo1 ROB --logo2 RUN --out out.jpg"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import thumb_maker as T
from PIL import Image, ImageDraw
ap = argparse.ArgumentParser(); ap.add_argument("--frame", required=True); ap.add_argument("--face", required=True); ap.add_argument("--logo1", default=""); ap.add_argument("--logo2", default="")
ap.add_argument("--out", required=True); ap.add_argument("--theme", default="party"); ap.add_argument("--side", default="left"); a = ap.parse_args()
tmp = a.out + ".tmp.jpg"
sys.argv = ["x", "--react", a.frame, "--frame", a.face, "--crop", "0,0,1024,1024", "--side", a.side, "--theme", a.theme, "--out", tmp]
T.main_cli()
im = Image.open(tmp).convert("RGB"); d = ImageDraw.Draw(im); f = T.font(118); x = 835 if a.side == "left" else 60
for i, (txt, col) in enumerate(((a.logo1, (255, 255, 255)), (a.logo2, (255, 210, 40)))):
    if txt: d.text((x, 418 + i * 102), txt, font=f, fill=col, stroke_width=12, stroke_fill=(0, 0, 0))
im.save(a.out, quality=93); os.remove(tmp); os.path.exists(tmp.replace(".jpg", "_168.png")) and os.remove(tmp.replace(".jpg", "_168.png")); im.resize((168, 94), Image.LANCZOS).save(os.path.splitext(a.out)[0] + "_168.png"); print("saved", a.out)

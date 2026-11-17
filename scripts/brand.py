#!/usr/bin/env python3
"""ClipGlobe branding for the English channel: the OWNER'S logo (assets/world_clips/logo_clipglobe.png) used exactly as is (only scaled/faded) as
 - a 2.5 s logo bumper at the start of long videos (black background, logo scales in 88%->100% with a fade, whoosh sound),
 - a small watermark in the corner of every video / Short.
Never redraw or restyle the logo (owner rule, 17 Nov)."""
import os, subprocess
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); LOGO = os.path.join(ROOT, "assets", "world_clips", "logo_clipglobe.png"); WHOOSH = os.path.join(ROOT, "assets", "sfx", "whoosh.wav")
def make_bumper(out, w=1920, h=1080, fps=60, dur=2.5):
    side = int(h * 0.78) // 2 * 2
    fc = (f"[1:v]format=rgba,scale=w='trunc({side}*(0.88+0.12*min(t/0.8\\,1))/2)*2':h=-2:eval=frame,fade=t=in:st=0:d=0.5:alpha=1[lg];[0:v][lg]overlay=(W-w)/2:(H-h)/2:eval=frame:shortest=0,format=yuv420p[v];"
          f"[2:a]aformat=sample_rates=48000:channel_layouts=stereo,apad,atrim=0:{dur},volume=-4dB[a]")
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=black:s={w}x{h}:r={fps}:d={dur}", "-loop", "1", "-t", str(dur), "-i", LOGO, "-i", WHOOSH, "-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-t", str(dur),
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", "-r", str(fps), "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode: raise RuntimeError("bumper failed: " + r.stderr[-300:])
    return out
def watermark_filter(inp_label, logo_label, out_label, size, x, y, alpha=0.9):
    """filter_complex fragment: overlays the logo (scaled to `size` px wide, alpha) at x:y"""
    return f"[{logo_label}]format=rgba,scale={size}:-1,colorchannelmixer=aa={alpha}[wm];[{inp_label}][wm]overlay={x}:{y}[{out_label}]"

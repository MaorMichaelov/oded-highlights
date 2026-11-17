#!/usr/bin/env python3
"""Regression tests for the style system: python3 scripts/test_styles.py [--render]
1. the signature style validates and equals the code defaults;  2. captions (ASS) from the style == the classic station make_ass + amber swap;
3. the Shorts ffmpeg command built through the style == the classic render2 command (with and without peak / hook / SFX env);  4. same for the long-video encode command;
5. --render: real renders (classic vs signature) of a local clip, compared by frame PSNR + loudness."""
import json, os, random, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "stations"))
import styles as ST, style_render as SR, vod_shorts as V
import shorts as SH
FAIL = []
def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + (" " + info if info and not ok else "")); (None if ok else FAIL.append(name))
def words(seed=3, n=70):
    random.seed(seed); ws = []; t = 2.0
    for i in range(n):
        d = random.uniform(.15, .5); ws.append({"word": " Word%d" % i + random.choice(["", "", ".", ",", "!"]), "start": t, "end": t + d}); t += d + random.choice([0.02, 0.05, 0.3, 0.9])
    return ws
def main():
    check("signature validates", ST.validate("signature") == [], str(ST.validate("signature")))
    for fmt in ("shorts", "long"): check(f"signature == code defaults ({fmt})", ST.resolve("signature", fmt) == ST.resolve(None, fmt))
    tmp = tempfile.mkdtemp(); ws = words()
    # 2. captions
    SH.make_ass(ws, 3.0, 40.0, tmp + "/legacy.ass"); legacy = open(tmp + "/legacy.ass").read().replace("&H0028E678", "&H0007C1FF")
    ST.make_ass(ws, 3.0, 40.0, tmp + "/new.ass", ST.resolve("signature", "shorts")["captions"], 1080, 1920); check("captions ASS identical", legacy == open(tmp + "/new.ass").read())
    # 3. Shorts command
    sig = ST.resolve("signature", "shorts"); cap = {}
    def fake(c, **k): cap["cmd"] = c; return subprocess.CompletedProcess(c, 0, "", "")
    for peak, hook, sfx in ((12.0, "He lost EVERYTHING in one second", "1"), (None, "", None), (7.5, "short hook", None), (5.0, "A", "1")):
        env = dict(os.environ); env.pop("STYLE", None)
        if sfx: os.environ["SHORTS_SFX"] = "1"
        else: os.environ.pop("SHORTS_SFX", None)
        V.sh = fake; V.render2("/x/body.mp4", 2.0, 40.0, "/x/a.ass", "/x/o.mp4", hook, peak); old = cap["cmd"]
        new = SR.build_shorts_cmd("/x/body.mp4", 2.0, 40.0, "/x/a.ass", "/x/o.mp4", hook, peak, sig)
        check(f"Shorts cmd identical (peak={peak}, hook={bool(hook)}, sfx={sfx})", old == new, "\n OLD " + " ".join(map(str, old))[:900] + "\n NEW " + " ".join(map(str, new))[:900])
    os.environ.pop("SHORTS_SFX", None)
    # 4. Long command
    import brand
    lg = ST.resolve("signature", "long"); dd = 1234.5
    old = ["ffmpeg", "-v", "error", "-y", "-ss", f"{77.25:.3f}", "-t", f"{dd:.3f}", "-i", "VID", "-loop", "1", "-i", brand.LOGO, "-filter_complex", "[1:v]format=rgba,scale=120:-1,colorchannelmixer=aa=0.85[wm];[0:v][wm]overlay=W-w-32:H-h-32:shortest=1,format=yuv420p[v]",
           "-map", "[v]", "-map", "0:a:0", "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", "-af", "afade=t=in:d=0.02,afade=t=out:st=%.3f:d=0.05" % (dd - 0.05), "-t", f"{dd:.3f}", "-movflags", "+faststart", "OUT"]
    new = SR.long_encode_cmd(lg, "VID", 77.25, dd, None, [], brand.LOGO, "OUT"); check("Long cmd identical", old == new, "\n OLD " + " ".join(old) + "\n NEW " + " ".join(new))
    if "--render" in sys.argv: render_tests(tmp, sig, ws)
    print("\nALL PASS" if not FAIL else "\nFAILED: " + ", ".join(FAIL)); sys.exit(1 if FAIL else 0)
def render_tests(tmp, sig, ws):
    import re
    src = next((p for p in ("/tmp/bt/w/body.mp4", "/tmp/stest/shorts/short1.mp4") if os.path.exists(p)), None)
    if not src: print("no local clip for render tests"); return
    V.sh = lambda c, **k: subprocess.run(c, capture_output=True, text=True, **k)
    SH.make_ass(ws, 0.5, 6.0, tmp + "/l.ass"); _t = open(tmp + "/l.ass").read().replace("&H0028E678", "&H0007C1FF"); open(tmp + "/l.ass", "w").write(_t)
    os.environ.pop("STYLE", None); ok1 = V.render2(src, 0.5, 6.0, tmp + "/l.ass", tmp + "/legacy.mp4", "Hook test line", 3.0)
    os.environ["STYLE"] = "signature"; SR.shorts_captions(sig, ws, 0.5, 6.0, tmp + "/n.ass", "Hook test line", []); ok2 = V.render2(src, 0.5, 6.0, tmp + "/n.ass", tmp + "/new.mp4", "Hook test line", 3.0)
    check("both renders ran", ok1 and ok2)
    r = subprocess.run(["ffmpeg", "-v", "info", "-i", tmp + "/legacy.mp4", "-i", tmp + "/new.mp4", "-lavfi", "psnr", "-f", "null", "-"], capture_output=True, text=True).stderr
    m = re.search(r"average:(\S+)", r); psnr = float(m.group(1)) if m and m.group(1) != "inf" else 99.0; check("video PSNR classic vs signature >= 60 dB (identical)", psnr >= 60, f"psnr={psnr}")
    def lufs(f): return float(re.search(r"I:\s+(-?[\d.]+) LUFS", subprocess.run(["ffmpeg", "-nostats", "-i", f, "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True).stderr.split("Summary")[-1]).group(1))
    a, b = lufs(tmp + "/legacy.mp4"), lufs(tmp + "/new.mp4"); check("loudness classic vs signature within 0.1 LU", abs(a - b) < 0.1, f"{a} vs {b}"); print("psnr", psnr, "lufs", a, b, "outputs in", tmp)
if __name__ == "__main__": main()

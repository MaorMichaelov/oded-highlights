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
    if "--render" in sys.argv: render_tests(tmp, sig, ws); feature_tests(tmp)
    if "--roundtrip" in sys.argv: roundtrip_tests(tmp)
    print("\nALL PASS" if not FAIL else "\nFAILED: " + ", ".join(FAIL)); sys.exit(1 if FAIL else 0)
def render_tests(tmp, sig, ws):
    import re
    src = next((p for p in ("/tmp/bt/w/body.mp4", "/tmp/stest/shorts/short1.mp4") if os.path.exists(p)), None)
    if not src: print("no local clip for render tests"); return
    V.sh = lambda c, **k: subprocess.run(c, capture_output=True, text=True, **k)
    SH.make_ass(ws, 0.5, 6.0, tmp + "/l.ass"); _t = open(tmp + "/l.ass").read().replace("&H0028E678", "&H0007C1FF"); open(tmp + "/l.ass", "w").write(_t)
    os.environ.pop("STYLE", None); ok1 = V.render2(src, 0.5, 6.0, tmp + "/l.ass", tmp + "/legacy.mp4", "Hook test line", 3.0)
    SR.shorts_captions(sig, ws, 0.5, 6.0, tmp + "/n.ass", "Hook test line", []); ok2 = SR.render_shorts(src, 0.5, 6.0, tmp + "/n.ass", tmp + "/new.mp4", "Hook test line", 3.0, sig)   # the style renderer itself, not the classic code
    check("both renders ran", ok1 and ok2)
    r = subprocess.run(["ffmpeg", "-v", "info", "-i", tmp + "/legacy.mp4", "-i", tmp + "/new.mp4", "-lavfi", "psnr", "-f", "null", "-"], capture_output=True, text=True).stderr
    m = re.search(r"average:(\S+)", r); psnr = float(m.group(1)) if m and m.group(1) != "inf" else 99.0; check("video PSNR classic vs signature >= 60 dB (identical)", psnr >= 60, f"psnr={psnr}")
    def lufs(f): return float(re.search(r"I:\s+(-?[\d.]+) LUFS", subprocess.run(["ffmpeg", "-nostats", "-i", f, "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True).stderr.split("Summary")[-1]).group(1))
    a, b = lufs(tmp + "/legacy.mp4"), lufs(tmp + "/new.mp4"); check("loudness classic vs signature within 0.1 LU", abs(a - b) < 0.1, f"{a} vs {b}"); print("psnr", psnr, "lufs", a, b, "outputs in", tmp)
def dur(f): return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f], capture_output=True, text=True).stdout.strip())
def feature_tests(tmp):
    """optional parameters (not used by the signature style) must keep working: dead-air cuts, other layouts/animations, extra zooms, sfx, music bed, bumper, long captions+loudness"""
    import re
    V.sh = lambda c, **k: subprocess.run(c, capture_output=True, text=True, **k)
    src = tmp + "/synth.mp4"   # 20 s: speech-like tone 0-5, silence 5-9, tone 9-14, silence 14-16, tone 16-20
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=1280x720:r=30:d=20", "-f", "lavfi", "-i", "sine=f=300:d=20", "-af", "volume='if(between(t,5,9)+between(t,14,16),0,0.5)':eval=frame", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", src], check=True)
    ws = [{"word": f" w{i}", "start": t, "end": t + 0.4} for i, t in enumerate([0.5, 1.2, 2.0, 3.0, 4.0, 9.5, 10.3, 11.0, 12.5, 13.2, 16.5, 17.4, 18.5, 19.2])]
    pace = {"dead_air_trim_s": 1.0, "keep_pause_s": 0.4, "silence_db": -42}
    cuts = SR.dead_air_cuts(src, 0.0, 20.0, ws, pace); print("dead-air cuts:", cuts)
    check("dead-air cuts found (2 silences)", len(cuts) == 2 and abs(cuts[0][0] - 5.2) < 0.4 and abs(cuts[1][0] - 14.2) < 0.4, str(cuts))
    # Shorts with every optional feature: crop_fill, karaoke captions, extra zooms, sfx, music (generated tone), bumper, cuts
    music = tmp + "/music.wav"; subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=f=220:d=5", music], check=True)
    for name, ov in (("everything on", {"layout": {"mode": "crop_fill"}, "captions": {"animation": "karaoke", "font": "Anton", "uppercase": True}, "zoom": {"extra_every_s": 4, "extra_strength": 0.05}, "sfx": {"mode": "on", "at": ["peak", "start", "zoom"]}, "music": {"enabled": True, "file": music}, "intro": {"bumper_s": 1.5}}),
                     ("square bars no zoom/captions/wm", {"layout": {"aspect": "1:1", "mode": "bars", "bg_color": "#202020"}, "captions": {"enabled": False}, "zoom": {"enabled": False}, "watermark": {"enabled": False}, "loudness": {"enabled": False}}),
                     ("16:9 contain blur", {"layout": {"aspect": "16:9", "fg_fit": "contain"}, "captions": {"animation": "fade", "color": "#00FF99"}})):
        st = ST.resolve({"extends": None, "shorts": ov}, "shorts"); ass = tmp + "/f.ass"; side = SR.shorts_captions(st, ws, 0.0, 20.0, ass, "Hook line here", cuts); out = tmp + f"/f_{name[:4]}.mp4"
        ok = SR.render_shorts(src, 0.0, 20.0, ass, out, "Hook line here", 10.0, st); L = dur(out) if ok and os.path.exists(out) else 0
        exp = 20.0 - ST.total_cut(cuts) + (1.5 if st["intro"]["bumper_s"] else 0)
        check(f"Shorts [{name}] renders, length {L:.1f}s (expected {exp:.1f})", ok and abs(L - exp) < 0.6, f"{L} vs {exp}")
    # Long: captions + dead-air + loudness + music through long_encode_cmd
    lg = ST.resolve({"extends": None, "long": {"captions": {"enabled": True}, "loudness": {"enabled": True}, "music": {"enabled": True, "file": music}}}, "long"); ass = tmp + "/l2.ass"
    ST.make_ass(ws, 0.0, 20.0, ass, lg["captions"], 1920, 1080, ST.make_remap(cuts)); out = tmp + "/long_f.mp4"
    import brand
    r = subprocess.run(SR.long_encode_cmd(lg, src, 0.0, 20.0, ass, cuts, brand.LOGO, out), capture_output=True, text=True)
    L = dur(out) if r.returncode == 0 else 0; check(f"Long [captions+cuts+loudness+music] renders, length {L:.1f}s", r.returncode == 0 and abs(L - (20 - ST.total_cut(cuts))) < 0.6, r.stderr[-400:])
    print("feature outputs in", tmp)
def roundtrip_tests(tmp):
    """render clips with KNOWN style parameters, run the measurer + style builder on them (no Gemini) and check the parameters are recovered"""
    import style_from_video as M
    V.sh = lambda c, **k: subprocess.run(c, capture_output=True, text=True, **k)
    random.seed(1); ws = []; t = 0.3
    for i in range(16): d = random.uniform(.2, .4); ws.append({"word": " Word%d" % i, "start": t, "end": t + d}); t += d + 0.05
    cases = [("amber104", {}, 3.0), ("green72-nozoom", {"captions": {"size": 72, "margin_v": 700, "color": "#00FF99"}, "zoom": {"enabled": False}}, None), ("white128-zoom12", {"captions": {"size": 128, "margin_v": 300, "color": "#FFFFFF", "outline_px": 10}, "zoom": {"strength": 0.12}}, 3.0)]
    for name, ov, peak in cases:
        st = ST.resolve({"extends": None, "shorts": ov}, "shorts"); ass = f"{tmp}/r_{name}.ass"; SR.shorts_captions(st, ws, 0.5, 6.3, ass, "Hook line", []); out = f"{tmp}/r_{name}.mp4"
        SR.render_shorts("/tmp/bt/w/body.mp4", 0.5, 6.3, ass, out, "Hook line", peak, st); m = M.measure(out, 60, log=lambda *a: None); sty = M.build_style("rt", out, m, None); got = sty["shorts"]; c = got.get("captions", {}); e = st["captions"]
        def rgb(h): h = ST.norm_color(h)[1:]; return [int(h[i:i + 2], 16) for i in (0, 2, 4)]
        check(f"[{name}] style validates", ST.validate(sty) == [], str(ST.validate(sty)))
        check(f"[{name}] caption colour recovered {c.get('color')} vs {e['color']}", "color" in c and max(abs(a - b) for a, b in zip(rgb(c["color"]), rgb(e["color"]))) <= 45)
        check(f"[{name}] caption size recovered {c.get('size')} vs {e['size']} (+-30 %)", abs(c.get("size", 0) - e["size"]) <= 0.3 * e["size"])
        check(f"[{name}] caption margin_v recovered {c.get('margin_v')} vs {e['margin_v']} (+-90 px)", abs(c.get("margin_v", -999) - e["margin_v"]) <= 90)
        z = got.get("zoom", {}); check(f"[{name}] zoom recovered {z}", z.get("enabled") == st["zoom"]["enabled"] and (not z.get("enabled") or abs(z.get("strength", 0) - st["zoom"]["strength"]) <= 0.04))
        check(f"[{name}] loudness recovered {got.get('loudness', {}).get('lufs')}", abs(got.get("loudness", {}).get("lufs", 0) - (-14)) <= 1.0)
        check(f"[{name}] layout blur_fill recovered", got.get("layout", {}).get("mode") == "blur_fill")
    # Gemini answer merged (fake answer: the merge + validation path)
    fake = {"summary": "test", "language": "en", "language_name": "English", "captions": {"present": True, "closest_font": "Anton", "animation": "bounce", "uppercase": True, "words_per_group": 2, "highlight_color_hex": ""}, "hook_text": {"present": True}, "zoom": {"used": True}, "sfx": {"used": True, "kinds": "boom"}, "music": {"used": True, "kind": "lofi"}, "intro": {"present": False, "seconds": 0}, "must_reproduce": ["captions two words"]}
    sty = M.build_style("fake", "x.mp4", m, fake); check("Gemini answer merges into a valid style", ST.validate(sty) == [] and sty["shorts"]["captions"]["font"] == "Anton" and sty["shorts"]["sfx"]["mode"] == "on", str(ST.validate(sty)))
if __name__ == "__main__": main()

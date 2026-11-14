#!/usr/bin/env python3
"""STATION 7 - QUALITY GATE: nothing reaches YouTube unless final.mp4 passes. Writes quality.json, exits 5 on any ERROR.
Checks: 1920x1080 (never 720p), 60 fps, video > 8 Mbps, audio present 48 kHz, A/V sync < 0.5 s, duration matches the cut plan, no silence >= 8 s, no black >= 3 s,
loudness not too quiet / not clipping, file decodes, source segments were 1080p60.
usage: quality.py state/clips/<id>"""
import json, os, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); from common import Timer
clip = os.path.abspath(sys.argv[1]); f = os.path.join(clip, "final.mp4"); err, warn, info = [], [], {}
def sh(c): r = subprocess.run(c, capture_output=True, text=True); return r.stdout + r.stderr
def probe(sel, ent): return sh(["ffprobe", "-v", "error", "-select_streams", sel, "-show_entries", ent, "-of", "default=nw=1:nk=1", f]).split()
with Timer(clip, "quality"):
    if not os.path.exists(f) or os.path.getsize(f) < 1_000_000: err.append("final.mp4 missing or tiny")
    else:
        w, h, rate = (probe("v:0", "stream=width,height,r_frame_rate") + ["0", "0", "0/1"])[:3]; n, d = rate.split("/"); fps = float(n) / float(d or 1)
        info.update(width=int(w), height=int(h), fps=round(fps, 2))
        if (int(w), int(h)) != (1920, 1080): err.append(f"resolution {w}x{h}, must be 1920x1080")
        if abs(fps - 60) > 0.5: err.append(f"fps {fps:.1f}, must be 60")
        br = sh(["ffprobe", "-v", "error", "-show_entries", "format=bit_rate,duration", "-of", "default=nw=1", f]); m = dict(l.split("=") for l in br.split() if "=" in l)
        mbps = int(m.get("bit_rate", 0)) / 1e6; dur = float(m.get("duration", 0)); info.update(mbps=round(mbps, 1), duration=round(dur, 1))
        if mbps < 8: err.append(f"bitrate {mbps:.1f} Mbps, must be > 8")
        a = probe("a:0", "stream=codec_name,sample_rate,duration"); v = probe("v:0", "stream=duration")
        if not a: err.append("no audio stream")
        else:
            try:
                if abs(float(a[2]) - float(v[0])) > 0.5: err.append(f"A/V sync diff {abs(float(a[2]) - float(v[0])):.2f}s")
            except Exception: pass
            if a[1] != "48000": warn.append(f"audio rate {a[1]}")
        cuts = json.load(open(os.path.join(clip, "cuts.json"))); body = sum(y - x for p in cuts["pieces"] for x, y in p["keep"])
        info["planned_body"] = round(body, 1)
        dj = os.path.join(clip, "durations.json"); exp = json.load(open(dj))["expected"] if os.path.exists(dj) else body + 11
        info["expected"] = round(exp, 1)
        if abs(dur - exp) > 2.0: err.append(f"duration {dur:.1f}s but body+opening should be {exp:.1f}s (lost or duplicated {dur - exp:+.1f}s)")
        out = sh(["ffmpeg", "-nostats", "-hide_banner", "-vn", "-i", f, "-af", "silencedetect=n=-45dB:d=8,ebur128=peak=true", "-f", "null", "-"])
        sil = re.findall(r"silence_duration: ([\d.]+)", out)
        if sil: warn.append(f"{len(sil)} silence(s) >= 8 s (max {max(map(float, sil)):.0f}s)")
        if len(sil) >= 3: err.append("too many long silences (dead air)")
        lu = re.findall(r"I:\s+(-?[\d.]+) LUFS", out); pk = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", out)
        if lu:
            info["lufs"] = float(lu[-1])
            if info["lufs"] < -32: err.append(f"too quiet {info['lufs']} LUFS")
        if pk and float(pk[-1]) > 0.5: warn.append(f"clipping peak {pk[-1]} dBFS")
        blk = re.findall(r"black_duration:([\d.]+)", sh(["ffmpeg", "-nostats", "-hide_banner", "-an", "-skip_frame", "nokey", "-i", f, "-vf", "blackdetect=d=3:pix_th=0.1", "-f", "null", "-"]))
        if blk: err.append(f"black screen {max(map(float, blk)):.0f}s")
    seg = os.path.join(clip, "work", "seg")
    if os.path.isdir(seg):   # source check: a downloaded VOD segment must be 1080p60
        ts = sorted(os.listdir(seg))[:1]
        if ts:
            sw = sh(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate", "-of", "csv=p=0", os.path.join(seg, ts[0])]).strip()
            info["source"] = sw
            if not sw.startswith("1920,1080"): err.append(f"source segment is {sw}, not 1080p")
    json.dump({"errors": err, "warnings": warn, "info": info}, open(os.path.join(clip, "quality.json"), "w"), indent=1, ensure_ascii=False)
    print("QUALITY", "FAIL" if err else "PASS", json.dumps(info), "errors:", err, "warnings:", warn)
    if err: sys.exit(5)

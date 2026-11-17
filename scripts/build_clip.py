#!/usr/bin/env python3
"""Build the BODY of a clip from a Kick VOD: download only the needed 1080p60 segments, then render
each `keep` range with trim/atrim (never -ss on a concat of .ts) and join them.
usage: build_clip.py BASE_URL CUTS.json WORKDIR [quality=1080p60] [preset=veryfast]
BASE_URL is the VOD hls base (…/media/hls). CUTS.json = {"pieces":[{"keep":[[a,b],...],"ch":"chapter"}]} in VOD seconds.
Writes WORKDIR/body.mp4 and WORKDIR/chapters.json (chapter start times inside body)."""
import json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
base, cuts_f, work = sys.argv[1], sys.argv[2], Path(sys.argv[3])
Q = sys.argv[4] if len(sys.argv) > 4 else "1080p60"
PRESET = sys.argv[5] if len(sys.argv) > 5 else "veryfast"
work.mkdir(parents=True, exist_ok=True); (work / "seg").mkdir(exist_ok=True); (work / "parts").mkdir(exist_ok=True)
pl = subprocess.run(["curl", "-sS", "-A", UA, "-m", "60", f"{base}/{Q}/playlist.m3u8"], capture_output=True, text=True).stdout.splitlines()
segs = []; cum = 0.0; d = None
for l in pl:
    if l.startswith("#EXTINF:"): d = float(l[8:].split(",")[0])
    elif l and not l.startswith("#") and d is not None: segs.append((l, cum, d)); cum += d; d = None
if not segs: sys.exit(f"no {Q} playlist at {base}: refusing to fall back to a lower quality")
if Q != "1080p60": sys.exit("only 1080p60 is allowed (owner rule: never 720p)")
C = json.load(open(cuts_f))
def files(a, b): return [s for s in segs if s[1] + s[2] > a and s[1] < b]
need = {}
for p in C["pieces"]:
    for a, b in p["keep"]:
        for s in files(a, b): need[s[0]] = s
_ranges = [(a, b) for p in C["pieces"] for a, b in p["keep"]]
if _ranges:   # edge refinement (owner priority: precise start/end) needs ~2 s of audio before the first range and after the last one
    for s in files(_ranges[0][0] - 2.0, _ranges[0][0]): need[s[0]] = s
    for s in files(_ranges[-1][1], _ranges[-1][1] + 2.0): need[s[0]] = s
def dl(s):
    f = work / "seg" / s[0]
    if f.exists() and f.stat().st_size > 1000: return
    subprocess.run(["curl", "-sS", "-A", UA, "-m", "120", "--retry", "3", "-o", str(f), f"{base}/{Q}/{s[0]}"])
print(f"downloading {len(need)} segments ({Q})", flush=True)
with ThreadPoolExecutor(8) as ex: list(ex.map(dl, need.values()))
import re as _re
SPIKES = []
try:   # chat reaction spikes = funny / big moments: a pause right before or around them is a comedic pause, never trimmed
    sys.path.insert(0, str(Path(__file__).resolve().parent)); import topic_scan
    _ing = json.load(open(Path(__file__).resolve().parent.parent / "state" / "ingest_state.json"))
    if str(C.get("vod")) == str(_ing.get("_current_vod")): SPIKES = [t for t, z in topic_scan.chat_spikes(_ing.get("_vod_start_epoch")) if z >= 2.3]
    print("protected funny moments (chat spikes):", len(SPIKES), flush=True)
except Exception as _e: print("chat spikes unavailable:", _e)
def true_silences(a, b, thr_s):
    """real audio silences (>= thr_s seconds, below -42 dB) inside [a, b] of the VOD (works for reactions: the video he watches is NOT silence)"""
    fs = files(a, b); s0 = fs[0][1]; x = a - s0
    inp = "concat:" + "|".join(str(work / "seg" / n) for n, _, _ in fs)
    r = subprocess.run(["ffmpeg", "-nostats", "-hide_banner", "-v", "info", "-i", inp, "-vn", "-af", f"atrim=start={x:.3f}:duration={b - a:.3f},asetpts=PTS-STARTPTS,silencedetect=n=-42dB:d={thr_s}", "-f", "null", "-"], capture_output=True, text=True).stderr
    st = [float(v) for v in _re.findall(r"silence_start: ([\d.]+)", r)]; en = [float(v) for v in _re.findall(r"silence_end: ([\d.]+)", r)]
    out = []
    for i_, sv in enumerate(st):
        ev = en[i_] if i_ < len(en) else b - a
        if not any(a + sv <= sp_ + 5 and a + ev >= sp_ - 15 for sp_ in SPIKES): out.append((sv, ev))   # keep silences around funny moments
    return out
def trim_ranges(keep, thr_s):
    res = []
    for a, b in keep:
        cur = a
        for sv, ev in true_silences(a, b, thr_s):
            if sv - (cur - a) > 2.0: res.append([cur, a + sv + 0.5])
            cur = a + ev - 0.5
        if b - cur > 2.0: res.append([cur, b])
    return res
# remove REAL silences from the audio; adaptive so a long clip never drops below ~14 min
def _edge_env(lo, hi):
    """10 ms RMS energy (dB) of the downloaded audio in [lo, hi] (VOD seconds); only segments that are present"""
    import numpy as _np
    fs = [f for f in files(lo, hi) if (work / "seg" / f[0]).exists()]
    if not fs: return None, None, None
    s0 = fs[0][1]; x = max(0.0, lo - s0)
    inp = "concat:" + "|".join(str(work / "seg" / n) for n, _, _ in fs)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", inp, "-vn", "-ac", "1", "-ar", "16000", "-af", f"atrim=start={x:.3f}:duration={hi - lo:.3f},asetpts=PTS-STARTPTS", "-f", "s16le", "-"], capture_output=True).stdout
    a_ = _np.frombuffer(raw, dtype=_np.int16).astype(_np.float32) / 32768.0; n_ = 160; m_ = len(a_) // n_
    if m_ < 20: return None, None, None
    return 20 * _np.log10(_np.sqrt((a_[:m_ * n_].reshape(m_, n_) ** 2).mean(1) + 1e-10)), 0.01, max(lo, s0 + x)
def _gaps_env(env, hop, t0, lo, hi, fl, min_len=0.12, margin=7.0):
    """quiet gaps (energy <= floor+margin dB for >= min_len) fully inside [lo, hi] -> [(start, end)] in VOD seconds"""
    out = []; i = 0; n = len(env)
    while i < n:
        if env[i] <= fl + margin:
            j = i
            while j < n and env[j] <= fl + margin: j += 1
            a_, b_ = t0 + i * hop, t0 + j * hop
            if b_ - a_ >= min_len and a_ >= lo - 1e-6 and b_ <= hi + 1e-6: out.append((a_, b_))
            i = j
        else: i += 1
    return out
def refine_start(t):
    env, hop, t0 = _edge_env(t - 2.5, t + 2.5)
    if env is None: return t
    import numpy as _np; fl = float(_np.percentile(env, 10)); gs = _gaps_env(env, hop, t0, t - 2.0, t + 0.9, fl)
    if not gs: print(f"edge start {t:.1f}: no pause found nearby, kept", flush=True); return t
    a_, b_ = min(gs, key=lambda g: abs(g[1] - t)); n_ = min(max(b_ - 0.15, a_ + 0.03), b_ - 0.03)   # cut 150 ms before speech resumes, inside the pause
    print(f"edge start {t:.2f} -> {n_:.2f} (pause {a_:.2f}-{b_:.2f})", flush=True); return n_
def refine_end(t):
    env, hop, t0 = _edge_env(t - 2.0, t + 1.5)
    if env is None: return t
    import numpy as _np; fl = float(_np.percentile(env, 10)); gs = _gaps_env(env, hop, t0, t - 0.6, t + 1.2, fl)
    if not gs: print(f"edge end {t:.1f}: no pause found nearby, kept", flush=True); return t
    a_, b_ = min(gs, key=lambda g: abs(g[0] - t)); n_ = min(a_ + 0.30, b_ - 0.05)   # 300 ms after the last sound, inside the pause
    print(f"edge end {t:.2f} -> {n_:.2f} (pause {a_:.2f}-{b_:.2f})", flush=True); return n_
try:
    if C.get("pieces") and not C.get("no_edge_snap"):
        _p0 = C["pieces"][0]["keep"]; _pl = C["pieces"][-1]["keep"]
        _ns = refine_start(_p0[0][0]); _ne = refine_end(_pl[-1][1])
        if _ns < _p0[0][1] - 5: _p0[0][0] = round(_ns, 3)
        if _ne > _pl[-1][0] + 5: _pl[-1][1] = round(_ne, 3)
except Exception as _e: print("edge refinement skipped:", _e, flush=True)
all_keep = [r for p_ in C["pieces"] for r in p_["keep"]]; before = sum(b - a for a, b in all_keep)
for thr_s in (*(C.get("silence") or [6, 10, 18]), None):   # games / reactions: only very long silences (>= 25 s), continuous video
    if thr_s is None: print("silence trimming skipped (clip would become too short)"); break
    trial = [trim_ranges(p_["keep"], thr_s) for p_ in C["pieces"]]; after = sum(b - a for k in trial for a, b in k)
    print(f"silence trim >= {thr_s}s: {before / 60:.1f} -> {after / 60:.1f} min", flush=True)
    if before < 840 or after >= 840:   # short clips (old rules) are trimmed fully; long ones must stay >= 14 min
        for p_, k in zip(C["pieces"], trial): p_["keep"] = k if k else p_["keep"]
        break
lst = []; i = 0; t = 0.0; chapters = []
for p in C["pieces"]:
    if p.get("ch"): chapters.append({"t": round(t, 2), "ch": p["ch"]})
    for a, b in p["keep"]:
        fs = files(a, b); s0 = fs[0][1]; x = a - s0; dur = b - a
        out = work / "parts" / f"p{i:03d}.mp4"; i += 1
        if not out.exists():
            inp = "concat:" + "|".join(str(work / "seg" / n) for n, _, _ in fs)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", inp, "-map", "0:v:0", "-map", "0:a:0",
              "-vf", f"trim=start={x:.3f}:duration={dur:.3f},setpts=PTS-STARTPTS,fps=60,format=yuv420p,setsar=1",
              "-af", f"atrim=start={x:.3f}:duration={dur:.3f},asetpts=PTS-STARTPTS,aresample=48000,afade=t=in:d=0.02,afade=t=out:st={max(0, dur-0.04):.3f}:d=0.04",
              "-c:v", "libx264", "-preset", PRESET, "-b:v", "12M", "-maxrate", "16M", "-bufsize", "24M", "-g", "120", "-keyint_min", "120", "-sc_threshold", "0", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", str(out)], check=True)
        lst.append(out); t += dur
        print(f"part {i} done ({t:.0f}s so far)", flush=True)
(work / "list.txt").write_text("".join(f"file '{x}'\n" for x in lst))
subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(work / "list.txt"), "-c", "copy", "-movflags", "+faststart", str(work / "body.mp4")], check=True)
json.dump(chapters, open(work / "chapters.json", "w"), ensure_ascii=False, indent=1)
print("BODY READY", round(t, 1), "s")

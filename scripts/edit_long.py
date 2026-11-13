#!/usr/bin/env python3
"""Enhance a finished long 16:9 highlight.

Same enhance as ronen_clipper/edit_long.py, branded for ODED HIGHLIGHTS.
Lessons (principles only) from the Ronen study, 2026-11-11:
  * Start with a strong hook, not browsing / black / a long bumper.
  * Keep the branded sting short (~2.6s, already in branding.py).
  * Like/sub CTA after the hook (Peak uses this).
  * Light punch-in zooms on a reaction, not jump-cut montages
    (measured cut rates on top videos are usually < 1.2 cuts/min at scene 0.40).
  * Burned captions are OPTIONAL: the top long videos we measured do not
    use continuous Hebrew subtitles. Punchy 2–6 word captions at peaks only.

All of this is behind a flag (config.ENABLE_EDIT_ENHANCE / --enhance).
Env override: ODED_EDIT_ENHANCE or KICK_EDIT_ENHANCE (0/false/no/off disables).
Default: hook + brand + a few zooms on; captions off unless --captions.

Usage:
  python3 edit_long.py --enhance SRC DEST [--hook-start SEC] [--hook-dur SEC]
      [--body-start SEC] [--body-dur SEC] [--zooms] [--no-zooms]
      [--captions] [--no-brand] [--no-hook]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from branding import INTRO_SEC, OVERLAY_SEC, THEMES, _probe, make_intro  # noqa: E402
from branding_v2 import SUB_SEC, caption_png, sub_overlay_frames  # noqa: E402
from config import CHANNEL, STREAMER_NAME_HE  # noqa: E402

FFMPEG = "ffmpeg"
HOOK_DUR = 8.0
ZOOM_SCALE = 1.18
ZOOM_DUR = 1.5
MAX_ZOOMS = 2
# like/sub starts this many seconds into the BODY (after hook+intro)
SUB_AT = 3.0


def _run(cmd, timeout=1800):
    subprocess.run(cmd, check=True, timeout=timeout)


def _ffprobe_dur(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float((r.stdout or "0").strip())
    except ValueError:
        return 0.0


def rms_windows(src: Path, win=0.5) -> list[tuple[float, float]]:
    """Return [(t, rms_db)] for ~win-second windows. rms_db is more-negative = quieter."""
    r = subprocess.run(
        [
            FFMPEG, "-hide_banner", "-i", str(src),
            "-af", f"astats=metadata=1:reset={win},ametadata=print:key=lavfi.astats.Overall.RMS_level",
            "-f", "null", "-",
        ],
        capture_output=True, text=True, timeout=600,
    )
    text = r.stderr or ""
    out = []
    cur_t = 0.0
    # pts times appear as "pts_time:X" on lavfi lines, RMS on following
    last_pts = 0.0
    for line in text.splitlines():
        m = re.search(r"pts_time:([0-9.]+)", line)
        if m:
            last_pts = float(m.group(1))
        m = re.search(r"RMS_level=([-\d.]+)", line)
        if m:
            try:
                out.append((last_pts, float(m.group(1))))
            except ValueError:
                pass
    return out


def find_hook_window(src: Path, hook_dur: float = HOOK_DUR, duration: float | None = None) -> tuple[float, float]:
    """Loudest hook_dur window, avoiding the first 3s (bumpers) and the last 8s."""
    duration = duration or _ffprobe_dur(src)
    rows = rms_windows(src, win=0.5)
    if not rows or duration < hook_dur + 1:
        start = min(3.0, max(0.0, duration * 0.05))
        return start, min(duration, start + hook_dur)
    # higher RMS_level is louder (e.g. -12 > -25)
    best = None
    best_score = -1e9
    lo = 3.0
    hi = max(lo + hook_dur, duration - 8.0)
    # 0.5s step
    t = lo
    by = {round(t, 2): v for t, v in rows}
    times = [t for t, _ in rows]
    def score_at(t0):
        vals = [v for tt, v in rows if t0 <= tt < t0 + hook_dur and v > -80]
        if len(vals) < 3:
            return -1e9
        # mean of the loudest half of the window (favours a shout inside the hook)
        vals = sorted(vals, reverse=True)
        return sum(vals[: max(3, len(vals)//2)]) / max(3, len(vals)//2)
    while t + hook_dur <= hi:
        sc = score_at(t)
        if sc > best_score:
            best_score = sc
            best = t
        t += 0.5
    if best is None:
        best = lo
    return round(best, 3), round(min(duration, best + hook_dur), 3)


def find_zoom_times(src: Path, duration: float, avoid: list[tuple[float, float]] | None = None,
                    count: int = MAX_ZOOMS) -> list[float]:
    """Start times of short punch-in zooms at the loudest moments, away from `avoid`."""
    avoid = avoid or []
    rows = rms_windows(src, win=0.5)
    if not rows:
        return []
    # candidate peaks: local maxima at least 8s apart, not in avoid, not first 2s / last 3s
    ranked = sorted(rows, key=lambda kv: kv[1], reverse=True)
    picks = []
    for t, db in ranked:
        if t < 2.0 or t > duration - (ZOOM_DUR + 1.0):
            continue
        if db < -25:  # not actually loud
            continue
        if any(a - 1.0 <= t <= b + 1.0 for a, b in avoid):
            continue
        if any(abs(t - p) < 8.0 for p in picks):
            continue
        picks.append(round(t, 3))
        if len(picks) >= count:
            break
    return picks


def _extract(src: Path, dest: Path, start: float, dur: float, vf: str | None = None):
    cmd = [
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
        "-ss", f"{start:.3f}", "-i", str(src), "-t", f"{dur:.3f}",
    ]
    if vf:
        cmd += ["-vf", vf, "-af", "aresample=48000"]
    else:
        # accurate short cuts: re-encode
        pass
    cmd += [
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart", str(dest),
    ]
    _run(cmd)
    return dest


def _zoom_vf(w: int, h: int, scale=ZOOM_SCALE) -> str:
    # scale up then crop back to the exact source size (integer crop, no rounding drift)
    return (
        f"scale=iw*{scale}:ih*{scale},crop={w}:{h}:(iw-{w})/2:(ih-{h})/2,"
        f"setsar=1,format=yuv420p"
    )


def enhance_long(
    src: Path,
    dest: Path,
    *,
    hook: bool = True,
    brand: bool = True,
    zooms: bool = True,
    captions: bool = False,
    hook_start: float | None = None,
    hook_dur: float = HOOK_DUR,
    body_start: float = 0.0,
    body_dur: float | None = None,
    caption_events: list[tuple[list[tuple[str, bool]], float, float]] | None = None,
    workdir: Path | None = None,
) -> dict:
    """Build dest = [optional hook] + [optional intro] + body (overlay, zooms, optional captions).

    caption_events: list of (words, start_in_body, end_in_body) where words is
    [(text, highlight), ...] in RTL reading order. Only used if captions=True.
    """
    src, dest = Path(src), Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    duration = _ffprobe_dur(src)
    if duration <= 0:
        raise SystemExit(f"cannot probe {src}")
    body_start = max(0.0, body_start)
    if body_dur is None:
        body_dur = max(0.5, duration - body_start)
    else:
        body_dur = min(body_dur, duration - body_start)

    work = Path(workdir or tempfile.mkdtemp(prefix="edit_long_"))
    work.mkdir(parents=True, exist_ok=True)
    W, H, fps, sr, ch = _probe(src)
    theme = THEMES.get(CHANNEL, THEMES["odedsvr"])
    info: dict = {"src": str(src), "dest": str(dest), "src_duration": duration,
                  "body_start": body_start, "body_dur": body_dur, "fps": fps, "size": [W, H]}

    parts: list[Path] = []

    # --- hook ---
    hook_range = None
    if hook:
        if hook_start is None:
            hs, he = find_hook_window(src, hook_dur=hook_dur, duration=duration)
        else:
            hs = hook_start
            he = min(duration, hook_start + hook_dur)
        hook_range = (hs, he)
        # If the hook is already how the body starts, don't replay it: just start the body there.
        if abs(hs - body_start) < 2.0:
            body_start = hs
            body_dur = min(duration - body_start, body_dur + (body_start - hs if False else body_dur))
            info["hook"] = {"reused_as_body_start": True, "start": hs, "end": he}
        else:
            hook_path = work / "hook.mp4"
            _extract(src, hook_path, hs, he - hs)
            parts.append(hook_path)
            info["hook"] = {"start": hs, "end": he, "dur": round(he - hs, 3)}

    # --- intro sting ---
    if brand:
        intro = make_intro(work / "intro.mp4", W, H, fps, sr, ch, theme, STREAMER_NAME_HE)
        parts.append(Path(intro))
        info["intro_sec"] = INTRO_SEC

    # --- zooms on the body timeline ---
    zoom_at: list[float] = []
    if zooms:
        # search peaks inside the body range, expressed as offsets from body_start
        # We search the source but only keep peaks that fall in [body_start, body_start+body_dur]
        raw_peaks = find_zoom_times(src, duration, avoid=[hook_range] if hook_range else [], count=MAX_ZOOMS + 2)
        for t in raw_peaks:
            rel = t - body_start
            if 2.0 <= rel <= body_dur - (ZOOM_DUR + 0.4):
                zoom_at.append(rel)
            if len(zoom_at) >= MAX_ZOOMS:
                break
        info["zooms_in_body"] = zoom_at

    # --- build body with overlay + zooms + captions in one filter ---
    body_src = work / "body_src.mp4"
    _extract(src, body_src, body_start, body_dur)
    body_out = work / "body.mp4"

    args = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", str(body_src)]
    fc = []
    maps_in = []
    idx = 1  # 0 is body_src
    ov_idx = None
    if brand:
        seq, sfps = sub_overlay_frames(work / "sub", W, H, fps=min(30, int(round(fps)) or 30))
        args += ["-framerate", str(sfps), "-i", str(seq)]
        ov_idx = idx
        idx += 1
        # overlay appears at SUB_AT for SUB_SEC, fade handled in the png sequence itself
        fc.append(f"[{ov_idx}:v]format=rgba,setpts=PTS+{SUB_AT}/TB[sub]")

    cap_specs = []
    if captions and caption_events:
        for i, (words, a, e) in enumerate(caption_events):
            if e <= 0 or a >= body_dur:
                continue
            png = work / f"cap{i}.png"
            caption_png([(w, bool(h)) for w, h in words], png, W, H, size=74)
            args += ["-loop", "1", "-t", f"{min(body_dur, e) + 0.3:.2f}", "-i", str(png)]
            cap_specs.append((idx, a, min(e, body_dur)))
            idx += 1

    # video chain: optional zooms via split/trim, then overlays
    # Build a concat of unzoomed / zoomed segments of the body.
    cuts = [0.0]
    for z in zoom_at:
        cuts += [z, z + ZOOM_DUR]
    cuts.append(body_dur)
    # merge tiny gaps
    merged = [0.0]
    for c in cuts[1:]:
        if c - merged[-1] >= 0.12:
            merged.append(c)
    if merged[-1] < body_dur:
        merged.append(body_dur)
    segs = list(zip(merged, merged[1:]))
    vparts = []
    aparts = []
    for i, (a, b) in enumerate(segs):
        is_zoom = any(abs(a - z) < 0.08 for z in zoom_at)
        zf = f",{_zoom_vf(W, H)}" if is_zoom else ",setsar=1"
        fc.append(f"[0:v]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS{zf},format=yuv420p[v{i}]")
        fc.append(f"[0:a]atrim=start={a:.3f}:end={b:.3f},asetpts=PTS-STARTPTS[a{i}]")
        vparts.append(f"[v{i}]")
        aparts.append(f"[a{i}]")
    if len(segs) == 1:
        fc.append("[v0]format=yuv420p,setsar=1[bv]")
        fc.append("[a0]anull[ba]")
    else:
        fc.append("".join(v + a for v, a in zip(vparts, aparts)) + f"concat=n={len(segs)}:v=1:a=1[bv][ba]")

    last = "bv"
    if brand and ov_idx is not None:
        end = SUB_AT + SUB_SEC
        fc.append(
            f"[{last}][sub]overlay=0:0:eof_action=pass:enable='between(t,{SUB_AT},{end})'[s0]"
        )
        last = "s0"
    for i, (ci, a, e) in enumerate(cap_specs):
        fc.append(f"[{ci}:v]format=rgba[k{i}]")
        fc.append(f"[{last}][k{i}]overlay=0:0:eof_action=pass:enable='between(t,{a:.3f},{e:.3f})'[s{i+1}]")
        last = f"s{i+1}"
    fc.append(f"[{last}]format=yuv420p,setsar=1[vout]")
    fc.append("[ba]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[aout]")

    args += [
        "-filter_complex", ";".join(fc),
        "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
        "-r", f"{fps}",
        "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
        "-movflags", "+faststart", str(body_out),
    ]
    _run(args)
    parts.append(body_out)

    # --- concat hook + intro + body ---
    if len(parts) == 1:
        shutil.copy2(parts[0], dest)
    else:
        # re-encode concat to avoid timebase issues
        cargs = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error"]
        for p in parts:
            cargs += ["-i", str(p)]
        n = len(parts)
        cfc = []
        for i in range(n):
            cfc.append(f"[{i}:v]format=yuv420p,setsar=1,fps={fps}[cv{i}]")
            cfc.append(f"[{i}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[ca{i}]")
        cfc.append("".join(f"[cv{i}][ca{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[vout][aout]")
        cargs += [
            "-filter_complex", ";".join(cfc), "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(dest),
        ]
        _run(cargs)

    info["out_duration"] = _ffprobe_dur(dest)
    info["parts"] = [str(p) for p in parts]
    (work / "enhance_info.json").write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n")
    return info


def enhance_if_enabled(src: Path, dest: Path, **kwargs) -> tuple[Path, bool]:
    """Used by cut_clip / enhance_ready. Honour ENABLE_EDIT_ENHANCE / ODED_EDIT_ENHANCE.

    Returns (dest, did_enhance). did_enhance is False when the flag is off
    (file may still be copied). The live watcher already imported the old
    cut_clip; do not rely on this hook until that process is restarted.
    """
    from config import ENABLE_EDIT_ENHANCE
    env = os.environ.get("ODED_EDIT_ENHANCE") or os.environ.get("KICK_EDIT_ENHANCE") or os.environ.get("RONEN_EDIT_ENHANCE")
    enabled = ENABLE_EDIT_ENHANCE if env is None else env.strip().lower() not in {"0", "false", "no", "off"}
    if not enabled:
        if src != dest:
            shutil.copy2(src, dest)
        return dest, False
    enhance_long(src, dest, **kwargs)
    return dest, True


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("src", type=Path)
    p.add_argument("dest", type=Path)
    p.add_argument("--enhance", action="store_true", help="required to actually run (safety)")
    p.add_argument("--no-hook", action="store_true")
    p.add_argument("--no-brand", action="store_true")
    p.add_argument("--no-zooms", action="store_true")
    p.add_argument("--captions", action="store_true")
    p.add_argument("--hook-start", type=float, default=None)
    p.add_argument("--hook-dur", type=float, default=HOOK_DUR)
    p.add_argument("--body-start", type=float, default=0.0)
    p.add_argument("--body-dur", type=float, default=None)
    p.add_argument("--work", type=Path, default=None)
    a = p.parse_args()
    if not a.enhance:
        raise SystemExit("refusing to run without --enhance")
    info = enhance_long(
        a.src, a.dest,
        hook=not a.no_hook, brand=not a.no_brand, zooms=not a.no_zooms,
        captions=a.captions, hook_start=a.hook_start, hook_dur=a.hook_dur,
        body_start=a.body_start, body_dur=a.body_dur, workdir=a.work,
    )
    print(json.dumps(info, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

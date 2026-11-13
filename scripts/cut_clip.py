#!/usr/bin/env python3
"""Cut a candidate range into a 16:9 long highlight and/or a 9:16 Short.

Long: 16:9 primary output, conservative dead-air removal (real silence only, snapped to transcript).
Short: 9:16, facecam on top, content on the bottom, white divider, word-by-word
Hebrew captions (bold white, black stroke, keywords yellow) centered on the divider.

Usage:
  cut_clip.py --session DIR --start SEC --end SEC [--long] [--short] [--out DIR]
  cut_clip.py --session DIR --candidate-index N --short
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import (  # noqa: E402
    CUT_PAD_SEC,
    DEFAULT_LAYOUT,
    FINAL_WHISPER_MODEL,
    HEBREW_FONT,
    HEBREW_FONT_NAME,
    KEYWORD_GROUPS,
    LONG_MAX,
    LONG_MIN,
    ROOT,
    SHORT_MAX,
    SHORT_MIN,
    SHORT_TARGET,
    SILENCE_MIN_DUR,
    SILENCE_NOISE_DB,
    SNAP_MAX_EXPAND,
)
from detect_layout import (  # noqa: E402
    detect,
    ensure_gameplay_excludes_cam,
    load_layout,
    pix_box,
    save_debug,
)
from process_segment import (  # noqa: E402
    ffprobe_duration,
    is_closed_mp4,
    is_segment_name,
    load_jsonl,
    load_manifest,
    log,
)

FFMPEG = "ffmpeg"
AUTO_EDITOR = str(ROOT / "venv" / "bin" / "auto-editor")
KEYWORD_FLAT = {w.lower() for ws in KEYWORD_GROUPS.values() for w in ws}

_FINAL_MODEL = None


def load_utterances(session: Path) -> list[dict]:
    rows = load_jsonl(session / "transcript.jsonl")
    out = []
    for r in rows:
        out.append({
            "start": float(r["abs_start"]),
            "end": float(r["abs_end"]),
            "text": r.get("text") or "",
            "words": r.get("words") or [],
        })
    return out


def snap_range(
    session: Path,
    start: float,
    end: float,
    pad: float = CUT_PAD_SEC,
    max_expand: float = SNAP_MAX_EXPAND,
) -> tuple[float, float]:
    """Snap [start, end] to sentence/word boundaries. Never mid-sentence.

    Expands (or slightly shrinks) to the surrounding utterance edges, then
    pads by ~0.2s so the first/last syllable is not clipped.
    """
    utts = load_utterances(session)
    if not utts:
        return max(0.0, start - pad), end + pad
    nearby = [u for u in utts if u["end"] > start - max_expand - 1 and u["start"] < end + max_expand + 1]
    if not nearby:
        return max(0.0, start - pad), end + pad

    new_start = start
    inside = [u for u in nearby if u["start"] - 0.05 <= start < u["end"] - 0.12]
    if inside:
        u = min(inside, key=lambda x: x["start"])
        if start - u["start"] <= max_expand:
            new_start = u["start"]
        else:
            later = [x for x in nearby if x["start"] >= start - 0.05]
            later.sort(key=lambda x: x["start"])
            if later and later[0]["start"] - start <= 2.5 and end - later[0]["start"] >= 8:
                new_start = later[0]["start"]
            else:
                new_start = u["start"]
    else:
        later = sorted((x for x in nearby if x["start"] >= start - 0.05), key=lambda x: x["start"])
        if later and later[0]["start"] - start <= 1.5:
            new_start = later[0]["start"]

    new_end = end
    inside = [u for u in nearby if u["start"] + 0.12 < end <= u["end"] + 0.05]
    if inside:
        u = max(inside, key=lambda x: x["end"])
        if u["end"] - end <= max_expand:
            new_end = u["end"]
        else:
            earlier = sorted((x for x in nearby if x["end"] <= end + 0.05), key=lambda x: x["end"])
            if earlier and end - earlier[-1]["end"] <= 2.5 and earlier[-1]["end"] - new_start >= 8:
                new_end = earlier[-1]["end"]
            else:
                new_end = u["end"]
    else:
        earlier = sorted((x for x in nearby if x["end"] <= end + 0.05), key=lambda x: x["end"])
        if earlier and end - earlier[-1]["end"] <= 1.5:
            new_end = earlier[-1]["end"]

    if new_end <= new_start + 1.0:
        return max(0.0, start - pad), end + pad
    return max(0.0, new_start - pad), new_end + pad


def transcribe_final_words(path: Path) -> list[dict] | None:
    """Word timestamps for a finished Short, using medium int8 when possible.

    Live detection stays on the small model. If medium is missing or too
    slow/fails, the caller falls back to the session (small) transcript.
    """
    global _FINAL_MODEL
    try:
        from faster_whisper import WhisperModel
        if _FINAL_MODEL is None:
            log(f"loading faster-whisper {FINAL_WHISPER_MODEL} int8 (final captions only)")
            t0 = __import__("time").perf_counter()
            _FINAL_MODEL = WhisperModel(FINAL_WHISPER_MODEL, device="cpu", compute_type="int8")
            log(f"final_model_load_sec={__import__('time').perf_counter()-t0:.2f}")
        t0 = __import__("time").perf_counter()
        segments, info = _FINAL_MODEL.transcribe(
            str(path),
            language="he",
            vad_filter=True,
            beam_size=5,
            word_timestamps=True,
        )
        words = []
        for seg in segments:
            for w in (getattr(seg, "words", None) or []):
                words.append({
                    "word": (w.word or "").strip(),
                    "start": round(float(w.start), 3),
                    "end": round(float(w.end), 3),
                })
        dur = float(getattr(info, "duration", 0) or 0)
        took = __import__("time").perf_counter() - t0
        log(f"final captions {path.name}: words={len(words)} audio={dur:.1f}s took={took:.1f}s rtf={took/dur if dur else 0:.3f}")
        return words
    except Exception as e:
        log(f"final medium transcribe failed ({e}); using session transcript")
        return None


def layout_from_video(src: Path, t: float = 2.0) -> dict | None:
    """Detect layout from a mid-clip frame so we don't reuse a stale session box."""
    import tempfile
    frame = src.parent / f".layout_{src.stem}.jpg"
    try:
        run([
            FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
            "-ss", f"{max(0.0, t):.3f}", "-i", str(src), "-frames:v", "1", str(frame),
        ], check=False)
        if frame.is_file():
            layout = detect(frame)
            try:
                frame.unlink()
            except Exception:
                pass
            return layout
    except Exception as e:
        log(f"mid-clip layout detect failed ({e})")
    return None



def run(cmd: list[str], check: bool = True, **kw) -> subprocess.CompletedProcess:
    log("+ " + " ".join(str(c) for c in cmd))
    return subprocess.run(cmd, check=check, **kw)


def session_segments(session: Path) -> list[dict]:
    man = load_manifest(session)
    if man:
        out = []
        for r in man:
            p = Path(r.get("path") or (session / r["file"]))
            if p.is_file():
                rec = dict(r)
                rec["path"] = p
                out.append(rec)
        if out:
            return sorted(out, key=lambda r: r.get("abs_start") or 0)
    # infer
    files = [p for p in session.glob("*.mp4") if is_segment_name(p) and is_closed_mp4(p)]
    files = sorted(files, key=lambda p: p.name)
    acc = 0.0
    out = []
    for p in files:
        d = ffprobe_duration(p) or 0
        out.append({"file": p.name, "path": p, "abs_start": acc, "abs_end": acc + d, "duration": d})
        acc += d
    return out


def extract_range(session: Path, start: float, end: float, dest: Path) -> Path:
    """Extract [start, end) in absolute stream seconds into dest (stream copy when possible)."""
    segs = session_segments(session)
    if not segs:
        raise SystemExit(f"no segments in {session}")
    pieces = []
    for s in segs:
        a0, a1 = float(s["abs_start"]), float(s["abs_end"])
        if a1 <= start or a0 >= end:
            continue
        local_ss = max(0.0, start - a0)
        local_ee = min(a1, end) - a0
        if local_ee - local_ss < 0.05:
            continue
        pieces.append((Path(s["path"]), local_ss, local_ee))
    if not pieces:
        raise SystemExit(f"no media overlaps {start}-{end}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if len(pieces) == 1:
        src, ss, ee = pieces[0]
        # Re-encode a short accurate cut so the timestamp is exact (copy +ss on
        # keyframes would drift). For long ranges, -ss before -i + copy is ok
        # if we pad a little; we prefer accuracy for shorts.
        dur = ee - ss
        if dur <= 45:
            run([
                FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
                "-ss", f"{ss:.3f}", "-i", str(src), "-t", f"{dur:.3f}",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
                str(dest),
            ])
        else:
            run([
                FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
                "-ss", f"{ss:.3f}", "-i", str(src), "-t", f"{dur:.3f}",
                "-c", "copy", "-avoid_negative_ts", "make_zero",
                str(dest),
            ])
        return dest

    tmp = dest.parent / f".tmp_parts_{dest.stem}"
    tmp.mkdir(parents=True, exist_ok=True)
    parts = []
    for i, (src, ss, ee) in enumerate(pieces):
        part = tmp / f"p{i:03d}.mp4"
        dur = ee - ss
        run([
            FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
            "-ss", f"{ss:.3f}", "-i", str(src), "-t", f"{dur:.3f}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-c:a", "aac", "-b:a", "160k",
            str(part),
        ])
        parts.append(part)
    lst = tmp / "list.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts), encoding="utf-8")
    run([
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", str(lst),
        "-c", "copy", "-movflags", "+faststart",
        str(dest),
    ])
    shutil.rmtree(tmp, ignore_errors=True)
    return dest


def silence_cut(src: Path, dest: Path, session: Path | None = None, abs_start: float = 0.0) -> Path:
    """Remove only real dead air. Do not cut mid-sentence or mid-moment.

    Cuts are snapped to transcript word/utterance edges with a ~0.2s pad.
    auto-editor is not used: its default pass was too aggressive.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    return silence_cut_ffmpeg(src, dest, session=session, abs_start=abs_start)


def _silence_inside_utterance(s: float, e: float, utts_rel: list[dict]) -> bool:
    """True if this 'silence' is just a pause inside one utterance — do not cut."""
    for u in utts_rel:
        if u["start"] < s - 0.05 and u["end"] > e + 0.05:
            return True
    return False


def _snap_cut_point(t: float, utts_rel: list[dict], words_rel: list[dict], *, is_start: bool, pad: float) -> float:
    """Move a keep-range edge off a mid-word/mid-sentence position."""
    for w in words_rel:
        if w["start"] < t < w["end"]:
            return (w["start"] - pad) if is_start else (w["end"] + pad)
    for u in utts_rel:
        if u["start"] < t < u["end"]:
            return (u["start"] - pad) if is_start else (u["end"] + pad)
    return t


def silence_cut_ffmpeg(
    src: Path,
    dest: Path,
    noise_db: float = SILENCE_NOISE_DB,
    min_dur: float = SILENCE_MIN_DUR,
    pad: float = CUT_PAD_SEC,
    session: Path | None = None,
    abs_start: float = 0.0,
) -> Path:
    proc = subprocess.run(
        [
            FFMPEG, "-hide_banner", "-i", str(src),
            "-af", f"silencedetect=noise={noise_db}dB:d={min_dur}",
            "-f", "null", "-",
        ],
        capture_output=True, text=True, timeout=600,
    )
    text = proc.stderr or ""
    starts = [float(x) for x in re.findall(r"silence_start:\s*([0-9.]+)", text)]
    ends = [float(x) for x in re.findall(r"silence_end:\s*([0-9.]+)", text)]
    duration = ffprobe_duration(src) or 0
    if len(starts) == len(ends) + 1:
        ends.append(duration)
    silences = list(zip(starts, ends))

    utts_rel, words_rel = [], []
    if session is not None:
        for u in load_utterances(session):
            rel = {"start": u["start"] - abs_start, "end": u["end"] - abs_start}
            if rel["end"] < -0.5 or rel["start"] > duration + 0.5:
                continue
            utts_rel.append(rel)
            for w in u.get("words") or []:
                a0, a1 = w.get("abs_start"), w.get("abs_end")
                if a0 is None:
                    continue
                words_rel.append({"start": float(a0) - abs_start, "end": float(a1) - abs_start})

    # Drop mid-utterance pauses — those are not dead air.
    silences = [(s, e) for s, e in silences if not _silence_inside_utterance(s, e, utts_rel)]
    # invert to keep ranges, with padding, then snap to word/sentence edges
    keeps = []
    cur = 0.0
    for s, e in silences:
        keep_end = max(cur, s - pad)
        keep_end = _snap_cut_point(keep_end, utts_rel, words_rel, is_start=False, pad=pad)
        if keep_end - cur >= 0.20:
            keeps.append((max(0.0, cur), min(duration, keep_end)))
        cur = min(duration, e + pad)
        cur = _snap_cut_point(cur, utts_rel, words_rel, is_start=True, pad=pad)
        cur = min(duration, max(0.0, cur))
    if duration - cur >= 0.20:
        keeps.append((cur, duration))
    # If almost nothing was silence, don't cut at all.
    kept_dur = sum(b - a for a, b in keeps)
    if not keeps or kept_dur < 0.5 or kept_dur > duration - 0.35:
        if not keeps or kept_dur < 0.5:
            shutil.copy2(src, dest)
            return dest
    if len(keeps) == 1 and abs(keeps[0][0]) < 0.05 and abs(keeps[0][1] - duration) < 0.05:
        shutil.copy2(src, dest)
        return dest
    parts = []
    filt = []
    for i, (a, b) in enumerate(keeps):
        filt.append(f"[0:v]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS[v{i}]")
        filt.append(f"[0:a]atrim=start={a:.3f}:end={b:.3f},asetpts=PTS-STARTPTS[a{i}]")
        parts.append(f"[v{i}][a{i}]")
    n = len(keeps)
    if n == 1:
        filt_str = ";".join(filt)
        mapv, mapa = "[v0]", "[a0]"
    else:
        filt_str = ";".join(filt) + ";" + "".join(parts) + f"concat=n={n}:v=1:a=1[outv][outa]"
        mapv, mapa = "[outv]", "[outa]"
    run([
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(src),
        "-filter_complex", filt_str,
        "-map", mapv, "-map", mapa,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
        str(dest),
    ])
    return dest


def ass_time(t: float) -> str:
    if t < 0:
        t = 0
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def is_keyword(word: str) -> bool:
    w = re.sub(r"[\s.,!?~\-\"'`]+", "", (word or "")).lower()
    if not w:
        return False
    if w in KEYWORD_FLAT:
        return True
    # also highlight מה / וואו even with extra letters
    if w in {"מה", "וואו", "ואו", "wow"}:
        return True
    return False


def words_for_range(session: Path, start: float, end: float) -> list[dict]:
    rows = load_jsonl(session / "transcript.jsonl")
    words = []
    for r in rows:
        for w in r.get("words") or []:
            a0 = w.get("abs_start")
            a1 = w.get("abs_end")
            if a0 is None:
                continue
            if a1 <= start or a0 >= end:
                continue
            words.append({
                "word": w.get("word") or "",
                "start": max(0.0, a0 - start),
                "end": max(0.0, a1 - start),
            })
        if not r.get("words") and r.get("text"):
            # no word timestamps: show the whole utterance
            if r["abs_end"] <= start or r["abs_start"] >= end:
                continue
            words.append({
                "word": r["text"],
                "start": max(0.0, r["abs_start"] - start),
                "end": max(0.0, r["abs_end"] - start),
            })
    words.sort(key=lambda w: w["start"])
    return words


def write_ass(words: list[dict], dest: Path, duration: float) -> Path:
    """Word-by-word captions, centered on the divider (x=540, y=960)."""
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{HEBREW_FONT_NAME},78,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,6,0,5,40,40,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    for w in words:
        text = (w["word"] or "").strip()
        if not text:
            continue
        t0, t1 = w["start"], max(w["end"], w["start"] + 0.12)
        # don't run past the clip
        if t0 >= duration:
            continue
        t1 = min(t1, duration)
        # yellow for keywords (ASS colour is AABBGGRR)
        if is_keyword(text):
            body = r"{\an5\pos(540,960)\c&H0000FFFF&}" + text
        else:
            body = r"{\an5\pos(540,960)}" + text
        lines.append(f"Dialogue: 0,{ass_time(t0)},{ass_time(t1)},Default,,0,0,0,,{body}\n")
    dest.write_text("".join(lines), encoding="utf-8")
    return dest


def probe_wh(path: Path) -> tuple[int, int]:
    out = subprocess.check_output(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height", "-of", "csv=p=0", str(path),
        ],
        text=True,
    ).strip()
    w, h = out.split(",")
    return int(w), int(h)


def make_short(src: Path, dest: Path, layout: dict, ass_path: Path | None) -> Path:
    w, h = probe_wh(src)
    layout = ensure_gameplay_excludes_cam(layout, w, h)
    fx, fy, fw, fh = pix_box(layout, "facecam", w, h)
    cx, cy, cw, ch = pix_box(layout, "content", w, h)
    # 1080x1920 = 956 + 8 + 956
    top_h, div_h, bot_h = 956, 8, 956
    # Face sits on the right of Oded's cam; bias the 9:16 crop toward it.
    cam = (
        f"[0:v]crop={fw}:{fh}:{fx}:{fy},"
        f"scale=1080:{top_h}:force_original_aspect_ratio=increase,"
        f"crop=1080:{top_h}:(iw-1080)*0.62:0,setsar=1[cam]"
    )
    game = (
        f"[0:v]crop={cw}:{ch}:{cx}:{cy},"
        f"scale=1080:{bot_h}:force_original_aspect_ratio=increase,"
        f"crop=1080:{bot_h},setsar=1[game]"
    )
    filt = f"{cam};{game};color=white:1080x{div_h}:d=1,setsar=1[div];[cam][div][game]vstack=inputs=3,format=yuv420p[base]"
    if ass_path and ass_path.is_file():
        # fontsdir so libass finds IBM Plex Sans Hebrew
        fontdir = str(Path(HEBREW_FONT).parent)
        # escape the ass path for the filter
        ass = str(ass_path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
        filt += f";[base]ass='{ass}':fontsdir='{fontdir}'[vout]"
        vmap = "[vout]"
    else:
        vmap = "[base]"
    run([
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(src),
        "-filter_complex", filt,
        "-map", vmap, "-map", "0:a?",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
        "-r", "30", "-c:a", "aac", "-b:a", "160k",
        "-movflags", "+faststart",
        str(dest),
    ])
    return dest


def pick_short_window(session: Path, start: float, end: float) -> tuple[float, float]:
    """If the requested range is longer than SHORT_MAX, keep the best ~25s inside it."""
    dur = end - start
    if SHORT_MIN <= dur <= SHORT_MAX:
        return start, end
    if dur < SHORT_MIN:
        return start, end
    cands = [c for c in load_jsonl(session / "candidates.jsonl") if c.get("kind") == "short"]
    inside = [c for c in cands if c["abs_start"] >= start - 1 and c["abs_end"] <= end + 1]
    if inside:
        best = max(inside, key=lambda c: c["score"])
        a, b = best["abs_start"], best["abs_end"]
        if b - a > SHORT_MAX:
            mid = 0.5 * (a + b)
            a, b = mid - SHORT_TARGET / 2, mid + SHORT_TARGET / 2
        return max(start, a), min(end, b)
    # fallback: take the first SHORT_TARGET seconds? better: highest loudness
    loud = load_jsonl(session / "loudness.jsonl")
    best_t, best_m = start, -99
    for b in loud:
        a0 = b.get("abs_t0", b.get("t0"))
        if a0 is None or a0 < start or a0 > end - SHORT_TARGET:
            continue
        m = b.get("max_M")
        if m is not None and m > best_m:
            best_m, best_t = m, a0
    return best_t, min(end, best_t + SHORT_TARGET)


def _layout_is_current(layout: dict | None) -> bool:
    if not layout:
        return False
    src = str(layout.get("source") or "")
    return "nochat" in src


def maybe_detect_layout(session: Path, layout_path: Path | None) -> dict:
    if layout_path and layout_path.is_file():
        layout = load_layout(layout_path)
        if _layout_is_current(layout):
            return layout
    auto = session / "layout.json"
    if auto.is_file():
        layout = load_layout(auto)
        if _layout_is_current(layout):
            return layout
    # Detect (or re-detect a stale file that still includes the chat strip).
    segs = session_segments(session)
    if segs:
        frame = session / "layout_frame.jpg"
        try:
            run([
                FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
                "-ss", "3", "-i", str(segs[0]["path"]), "-frames:v", "1", str(frame),
            ], check=False)
            if frame.is_file():
                layout = detect(frame)
                auto.write_text(json.dumps(layout, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                save_debug(frame, layout, session / "layout_debug.jpg")
                log(f"detected layout source={layout.get('source')}")
                return layout
        except Exception as e:
            log(f"layout detect failed ({e}), using default")
    return json.loads(json.dumps(DEFAULT_LAYOUT))


def cut_and_maybe_enqueue(
    session: Path,
    start: float,
    end: float,
    kind: str,
    candidate: dict | None = None,
    outdir: Path | None = None,
) -> Path | None:
    """Snap, cut one clip, write a ready/ JSON. kind is 'long' or 'short'."""
    from ready_queue import enqueue, source_fields, suggest_description, suggest_title

    kind = "short" if kind == "short" else "long"
    start, end = snap_range(session, start, end)
    if kind == "short":
        if end - start > SHORT_MAX:
            mid = 0.5 * (start + end)
            start, end = snap_range(session, mid - SHORT_TARGET / 2, mid + SHORT_TARGET / 2)
        if end - start < SHORT_MIN * 0.8:
            log(f"skip short {start:.1f}-{end:.1f}: too short after snap")
            return None
    else:
        if end - start > LONG_MAX:
            mid = 0.5 * (start + end)
            start, end = snap_range(session, mid - min(LONG_MAX, end - start) / 2,
                                    mid + min(LONG_MAX, end - start) / 2)
        if end - start < LONG_MIN * 0.8:
            log(f"skip long {start:.1f}-{end:.1f}: too short after snap")
            return None

    outdir = outdir or (session / "clips")
    outdir.mkdir(parents=True, exist_ok=True)
    stem = f"{'short' if kind == 'short' else 'highlight'}_{int(start):05d}_{int(end):05d}"
    raw = outdir / f"{stem}_raw.mp4"
    extract_range(session, start, end, raw)
    cand = candidate or {}
    title = suggest_title(
        kind,
        cand.get("summary") or "",
        cand.get("text_joined") or "",
        cand.get("keyword_groups") or {},
        cand.get("topic_label"),
        source=cand,
    )
    description = suggest_description(kind, cand)
    src_meta = source_fields(cand)
    score = float(cand.get("score") or 0)

    if kind == "long":
        dest = outdir / f"{stem}.mp4"
        try:
            silence_cut(raw, dest, session=session, abs_start=start)
        except Exception as e:
            log(f"silence cut failed ({e}), copying raw")
            shutil.copy2(raw, dest)
        enhanced_ok = False
        try:
            from edit_long import enhance_if_enabled
            enhanced = dest.with_name(dest.stem + "_enhanced.mp4")
            _, enhanced_ok = enhance_if_enabled(dest, enhanced)
            if enhanced.is_file() and enhanced.stat().st_size > 10_000 and enhanced_ok:
                enhanced.replace(dest)
            elif enhanced.is_file():
                enhanced.unlink(missing_ok=True)
                enhanced_ok = False
        except Exception as e:
            log(f"edit enhance skipped ({e})")
            enhanced_ok = False
        dur = ffprobe_duration(dest)
        ready = enqueue(
            path=dest, kind="long", title=title, score=score,
            source_start=start, source_end=end, session=session, duration=dur,
            extra={"layout": "16:9", "description": description, "enhanced": enhanced_ok, **src_meta},
        )
        try:
            raw.unlink()
        except Exception:
            pass
        return ready

    # Short: prefer a layout detected from this clip itself.
    layout = layout_from_video(raw, t=min(3.0, max(0.4, (end - start) * 0.3)))
    if not layout:
        layout = maybe_detect_layout(session, None)
    (outdir / f"{stem}_layout.json").write_text(
        json.dumps(layout, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    words = transcribe_final_words(raw)
    if not words:
        words = words_for_range(session, start, end)
    dur = ffprobe_duration(raw) or (end - start)
    ass = outdir / f"{stem}_captions.ass"
    write_ass(words, ass, dur)
    dest = outdir / f"{stem}.mp4"
    make_short(raw, dest, layout, ass)
    dur = ffprobe_duration(dest)
    ready = enqueue(
        path=dest, kind="short", title=title, score=score,
        source_start=start, source_end=end, session=session, duration=dur,
        extra={"layout": "1080x1920 facecam/game", "caption_words": len(words)},
    )
    try:
        raw.unlink()
    except Exception:
        pass
    return ready


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--session", type=Path, required=True)
    p.add_argument("--start", type=float, default=None)
    p.add_argument("--end", type=float, default=None)
    p.add_argument("--long", action="store_true")
    p.add_argument("--short", action="store_true")
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--layout", type=Path, default=None)
    p.add_argument("--name", default=None, help="output filename stem")
    args = p.parse_args()
    if not args.long and not args.short:
        args.long = args.short = True
    if args.start is None or args.end is None:
        raise SystemExit("need --start and --end (absolute stream seconds)")
    if args.end <= args.start:
        raise SystemExit("end must be after start")
    session = args.session
    start, end = snap_range(session, args.start, args.end)
    if abs(start - args.start) > 0.05 or abs(end - args.end) > 0.05:
        log(f"snapped range {args.start:.2f}-{args.end:.2f} -> {start:.2f}-{end:.2f}")
    outdir = args.out or (session / "clips")
    outdir.mkdir(parents=True, exist_ok=True)
    stem = args.name or f"clip_{int(start):05d}_{int(end):05d}"
    raw = outdir / f"{stem}_raw.mp4"
    extract_range(session, start, end, raw)
    raw_dur = ffprobe_duration(raw)
    log(f"extracted {raw} duration={raw_dur}")

    results = {}
    if args.long:
        long_path = outdir / f"{stem}_highlight.mp4"
        try:
            silence_cut(raw, long_path, session=session, abs_start=start)
        except Exception as e:
            log(f"silence cut failed ({e}), copying raw")
            shutil.copy2(raw, long_path)
        try:
            from edit_long import enhance_if_enabled
            enhanced = long_path.with_name(long_path.stem + "_enhanced.mp4")
            _, ok = enhance_if_enabled(long_path, enhanced)
            if enhanced.is_file() and enhanced.stat().st_size > 10_000 and ok:
                enhanced.replace(long_path)
                results["enhanced"] = True
            elif enhanced.is_file():
                enhanced.unlink(missing_ok=True)
        except Exception as e:
            log(f"edit enhance skipped ({e})")
        results["highlight"] = str(long_path)
        results["highlight_duration"] = ffprobe_duration(long_path)
        results["snapped_range"] = [start, end]
        log(f"highlight {long_path} duration={results['highlight_duration']}")

    if args.short:
        s0, s1 = pick_short_window(session, start, end)
        s0, s1 = snap_range(session, s0, s1)
        short_src = raw
        if abs(s0 - start) > 0.4 or abs(s1 - end) > 0.4:
            short_src = outdir / f"{stem}_short_src.mp4"
            extract_range(session, s0, s1, short_src)
        layout = layout_from_video(short_src, t=min(3.0, max(0.4, (s1 - s0) * 0.3)))
        if not layout:
            layout = maybe_detect_layout(session, args.layout)
        (outdir / f"{stem}_layout.json").write_text(
            json.dumps(layout, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        words = transcribe_final_words(short_src)
        if not words:
            words = words_for_range(session, s0, s1)
        ass = outdir / f"{stem}_captions.ass"
        dur = ffprobe_duration(short_src) or (s1 - s0)
        write_ass(words, ass, dur)
        short_path = outdir / f"{stem}_short.mp4"
        make_short(short_src, short_path, layout, ass)
        results["short"] = str(short_path)
        results["short_duration"] = ffprobe_duration(short_path)
        results["short_range"] = [s0, s1]
        results["caption_words"] = len(words)
        log(f"short {short_path} duration={results['short_duration']} words={len(words)}")

    (outdir / f"{stem}_meta.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

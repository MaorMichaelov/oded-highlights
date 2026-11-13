#!/usr/bin/env python3
"""Process a closed Kick recording segment.

- Transcribe Hebrew with faster-whisper small int8
- Append to a running transcript with absolute stream timestamps
- ffmpeg ebur128 loudness per 10s
- Score signals (loudness spikes, laughter/shouting, chat spikes, keywords)
- Keep only strict, top-ranked moments (weak/average talk is dropped)
- Write candidates.jsonl and group topic sections for long highlights
- After a segment (and on finalize), cut ready clips into ready/

Usage:
  process_segment.py --session DIR [--segment FILE]
  process_segment.py --session DIR --watch
  process_segment.py --session DIR --finalize
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import (  # noqa: E402
    CHAT_SPIKE_Z,
    KEYWORD_GROUPS,
    LAUGHTER_MARKERS,
    LIVE_WHISPER_MODEL,
    LONG_MAX,
    LONG_MIN,
    LONG_SCORE_MIN,
    LOUD_SPIKE_LU,
    SEGMENT_TIME,
    SHORT_MAX,
    SHORT_MIN,
    SHORT_SCORE_MIN,
    SHORT_TARGET,
    SHORT_TOP_K_PER_SEGMENT,
    SHOUT_LU,
    WEAK_KEYWORDS,
)

PUNCT_RE = re.compile(r"[\s.,!?~\-\"'`]+")


def log(msg: str) -> None:
    print(f"{datetime.now().astimezone().isoformat(timespec='seconds')} {msg}", flush=True)


def ffprobe_duration(path: Path) -> float | None:
    try:
        out = subprocess.check_output(
            [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=nw=1:nk=1", str(path),
            ],
            text=True,
            timeout=30,
        ).strip()
        return float(out)
    except Exception:
        return None


def is_closed_mp4(path: Path) -> bool:
    """True if the MP4 has a moov atom and is readable."""
    try:
        subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(path)],
            stderr=subprocess.DEVNULL,
            timeout=20,
        )
        return True
    except Exception:
        return False


def load_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def append_jsonl(path: Path, obj: dict) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def session_start_epoch(session: Path) -> float | None:
    meta = session / "session_meta.json"
    if meta.is_file():
        try:
            return float(json.loads(meta.read_text(encoding="utf-8"))["started_epoch"])
        except Exception:
            pass
    p = session / "started_at.txt"
    if p.is_file():
        try:
            t = p.read_text(encoding="utf-8").strip().replace("Z", "+00:00")
            return datetime.fromisoformat(t).timestamp()
        except Exception:
            pass
    return None


def parse_segment_wall(path: Path) -> float | None:
    """Parse odedsvr_YYYYMMDDTHHMMSS.mp4 as local wall time."""
    m = re.search(r"(\d{8}T\d{6})", path.stem)
    if not m:
        return None
    try:
        dt = datetime.strptime(m.group(1), "%Y%m%dT%H%M%S").astimezone()
        return dt.timestamp()
    except Exception:
        return None


def load_manifest(session: Path) -> list[dict]:
    man = session / "segments.jsonl"
    return load_jsonl(man)


def upsert_manifest(session: Path, rec: dict) -> None:
    existing = load_manifest(session)
    by_name = {r.get("file"): r for r in existing}
    by_name[rec["file"]] = rec
    path = session / "segments.jsonl"
    with path.open("w", encoding="utf-8") as f:
        for r in sorted(by_name.values(), key=lambda x: (x.get("abs_start") or 0, x.get("file") or "")):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def resolve_abs_start(session: Path, seg: Path, duration: float) -> float:
    """Absolute start of this segment within the stream, in seconds."""
    # Prefer an existing manifest entry (VOD sim writes offsets explicitly).
    for r in load_manifest(session):
        if r.get("file") == seg.name or r.get("path") == str(seg):
            if r.get("abs_start") is not None:
                return float(r["abs_start"])
    start_ep = session_start_epoch(session)
    wall = parse_segment_wall(seg)
    if start_ep is not None and wall is not None:
        return max(0.0, wall - start_ep)
    # Fallback: sort closed segments and accumulate durations
    segs = sorted(s for s in session.glob("*.mp4") if s.name.startswith(seg.name.split("_")[0]) or True)
    # Only siblings that look like recorded segments, not clips
    segs = [s for s in session.glob("*.mp4") if is_segment_name(s)]
    segs = sorted(segs, key=lambda p: (parse_segment_wall(p) or p.stat().st_mtime, p.name))
    acc = 0.0
    for s in segs:
        if s.resolve() == seg.resolve():
            return acc
        d = ffprobe_duration(s) or 0
        acc += d
    return 0.0


def is_segment_name(path: Path) -> bool:
    if path.parent.name in {"clips", "samples", "_source"}:
        return False
    if "review" in path.name or "short" in path.name or "highlight" in path.name:
        return False
    return bool(re.search(r"\.(mp4)$", path.name, re.I)) and path.parent.name != "clips"


def measure_loudness_10s(path: Path) -> list[dict]:
    """Return 10-second bins of ebur128 momentary/short-term/integrated loudness.

    ffmpeg 7's ebur128 framelog=verbose is silent at the default info
    loglevel, so we inject metadata and print it to a temp file instead.
    """
    import tempfile
    with tempfile.NamedTemporaryFile("w+", suffix=".ebur.txt", delete=False) as tmp:
        meta_path = Path(tmp.name)
    try:
        subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path),
                "-af", f"ebur128=peak=true:metadata=1,ametadata=mode=print:file={meta_path}",
                "-f", "null", "-",
            ],
            capture_output=True, text=True, timeout=600, check=False,
        )
        text = meta_path.read_text(encoding="utf-8", errors="replace") if meta_path.is_file() else ""
    finally:
        try:
            meta_path.unlink()
        except Exception:
            pass
    samples = []
    cur_t = None
    cur = {}
    for line in text.splitlines():
        if line.startswith("frame:"):
            if cur_t is not None and "M" in cur:
                samples.append((cur_t, cur.get("M", -120), cur.get("S", -120), cur.get("I", -70)))
            cur_t = None
            cur = {}
            m = re.search(r"pts_time:([0-9.]+)", line)
            if m:
                cur_t = float(m.group(1))
        elif line.startswith("lavfi.r128.M="):
            cur["M"] = float(line.split("=", 1)[1])
        elif line.startswith("lavfi.r128.S="):
            cur["S"] = float(line.split("=", 1)[1])
        elif line.startswith("lavfi.r128.I="):
            cur["I"] = float(line.split("=", 1)[1])
    if cur_t is not None and "M" in cur:
        samples.append((cur_t, cur.get("M", -120), cur.get("S", -120), cur.get("I", -70)))
    if not samples:
        return []
    duration = samples[-1][0]
    bins = []
    t0 = 0.0
    while t0 < duration - 0.5:
        t1 = t0 + 10.0
        chunk = [s for s in samples if t0 <= s[0] < t1]
        if chunk:
            Ms = [s[1] for s in chunk if s[1] > -70]
            Ss = [s[2] for s in chunk if s[2] > -70]
            bins.append({
                "t0": round(t0, 3),
                "t1": round(min(t1, duration), 3),
                "max_M": round(max(Ms), 2) if Ms else None,
                "mean_M": round(sum(Ms) / len(Ms), 2) if Ms else None,
                "max_S": round(max(Ss), 2) if Ss else None,
                "I_end": round(chunk[-1][3], 2),
            })
        t0 = t1
    return bins


def _norm_token(tok: str) -> str:
    return PUNCT_RE.sub("", tok).lower()


def keyword_hits(text: str) -> dict[str, list[str]]:
    """Match keywords. Short tokens (e.g. "מה") must be whole words, not substrings."""
    if not text:
        return {}
    low = text.lower()
    tokens = {tok for tok in PUNCT_RE.split(low) if tok}
    hits: dict[str, list[str]] = {}
    for group, words in KEYWORD_GROUPS.items():
        found = []
        for w in words:
            wl = w.lower()
            if " " in wl:
                if wl in low:
                    found.append(w)
            elif len(wl) <= 3:
                if wl in tokens:
                    found.append(w)
            elif wl in low:
                found.append(w)
        if found:
            hits[group] = found
    return hits


def has_laughter(text: str) -> bool:
    low = (text or "").lower()
    if any(m in low for m in LAUGHTER_MARKERS):
        return True
    # long run of ח or ה
    if re.search(r"[חה]{3,}", text or ""):
        return True
    return False


def shouting(text: str, max_M: float | None, loud_median: float | None = None) -> bool:
    """True only for a real outburst, not ordinary talking.

    A typical odedsvr median is around -12.5 LUFS, so a flat "-14 LUFS"
    threshold was marking almost every window as a shout.
    """
    if max_M is not None and loud_median is not None and max_M >= loud_median + SHOUT_LU:
        return True
    if text and text.count("!") >= 2:
        return True
    if text and text.strip().endswith("!") and len(text.strip()) < 24:
        return True
    return False


_MODEL = None


def get_model():
    global _MODEL
    if _MODEL is None:
        from faster_whisper import WhisperModel
        log(f"loading faster-whisper {LIVE_WHISPER_MODEL} int8")
        t0 = time.perf_counter()
        _MODEL = WhisperModel(LIVE_WHISPER_MODEL, device="cpu", compute_type="int8")
        log(f"model_load_sec={time.perf_counter()-t0:.2f}")
    return _MODEL


def transcribe(path: Path) -> list[dict]:
    model = get_model()
    t0 = time.perf_counter()
    segments, info = model.transcribe(
        str(path),
        language="he",
        vad_filter=True,
        beam_size=5,
        word_timestamps=True,
    )
    rows = []
    for seg in segments:
        words = []
        if getattr(seg, "words", None):
            for w in seg.words:
                words.append({
                    "start": round(float(w.start), 3),
                    "end": round(float(w.end), 3),
                    "word": (w.word or "").strip(),
                })
        rows.append({
            "start": round(float(seg.start), 3),
            "end": round(float(seg.end), 3),
            "text": (seg.text or "").strip(),
            "words": words,
        })
    dur = float(getattr(info, "duration", 0) or 0)
    took = time.perf_counter() - t0
    log(
        f"transcribe {path.name}: {len(rows)} segs, audio={dur:.1f}s, "
        f"took={took:.1f}s, rtf={took/dur if dur else 0:.3f}, lang={getattr(info,'language',None)}"
    )
    return rows


def chat_counts(session: Path, abs0: float, abs1: float) -> tuple[int, float]:
    """Return (n_messages, per_min) in [abs0, abs1)."""
    rows = load_jsonl(session / "chat.jsonl")
    n = 0
    for r in rows:
        a = r.get("abs_sec")
        if a is None:
            continue
        if abs0 <= float(a) < abs1:
            n += 1
    dur = max(0.1, abs1 - abs0)
    return n, n / dur * 60.0


def load_chat_baseline(session: Path) -> float:
    rates = load_jsonl(session / "chat_rate.jsonl")
    vals = [r["per_min_60s"] for r in rates if r.get("per_min_60s") is not None]
    if not vals:
        return 0.0
    vals = sorted(vals)
    return vals[len(vals) // 2]


def summarize_he(utterances: list[str], limit: int = 80) -> str:
    """Extractive: pick the most distinctive short utterance, don't invent."""
    texts = [u.strip() for u in utterances if u and u.strip()]
    if not texts:
        return ""
    scored = []
    for t in texts:
        hits = keyword_hits(t)
        n = sum(len(v) for v in hits.values())
        scored.append((n, len(t), t))
    scored.sort(key=lambda x: (-x[0], x[1]))
    best = scored[0][2]
    if len(best) > limit:
        best = best[: limit - 1] + "…"
    return best


def _self_names() -> set[str]:
    """The streamer's own names (never a 'guest')."""
    try:
        from config import CHANNEL, STREAMER_NAME_HE
    except Exception:
        return {"עודד", "oded"}
    base = {STREAMER_NAME_HE, CHANNEL.lower(), CHANNEL.lower().rstrip("gsvr")}
    base |= {"oded"} if CHANNEL.startswith("oded") else set()
    base |= {"ronen"} if CHANNEL.startswith("ronen") else set()
    return {b.lower() for b in base if b}


def topic_label(texts: list[str]) -> tuple[str, str]:
    """Return (kind, hebrew label) from combined text."""
    blob = " ".join(texts)
    hits = keyword_hits(blob)
    if "game" in hits:
        word = hits["game"][0]
        return "game", f"משחק {word}"
    selfn = _self_names()
    if "names" in hits and any(n for n in hits["names"] if n.lower() not in selfn):
        name = [n for n in hits["names"] if n.lower() not in selfn][0]
        return "guest", f"אורח {name}"
    if "curse" in hits or "התפוצץ" in blob or "מתפוצץ" in blob or "דרמה" in blob:
        return "drama", "דרמה"
    if "חבר" in blob or "חברה" in blob:
        return "guest", "עם חבר"
    if "reaction" in hits or "ריאקשן" in blob or "יוטיוב" in blob or "youtube" in blob.lower():
        return "reaction", "ריאקשן"
    return "talk", "שיחה"


def _kw_score(hits_all: dict) -> tuple[float, bool]:
    """Return (kw_score, has_strong_transcript_keyword).

    Weak everyday words (מה, איזה, יאללה, עודד, ...) do not count as a cue
    on their own and contribute very little to the score.
    """
    weights = {"curse": 1.4, "reaction": 1.2, "names": 0.8, "game": 0.6}
    kw_score = 0.0
    strong = False
    for g, ws in hits_all.items():
        unique = set(ws)
        strong_ws = [w for w in unique if w.lower() not in WEAK_KEYWORDS]
        weak_ws = [w for w in unique if w.lower() in WEAK_KEYWORDS]
        if strong_ws:
            if g in {"curse", "reaction"} or (g == "names" and any(w.lower() not in _self_names() for w in strong_ws)):
                strong = True
            if g == "game":
                # a game name alone is context, not a "moment"
                pass
            else:
                strong = True if g in {"curse", "reaction"} else strong
        kw_score += weights.get(g, 0.5) * min(3, len(strong_ws))
        kw_score += 0.12 * min(2, len(weak_ws))
    return min(kw_score / 4.0, 1.5), strong


def score_window(
    abs_start: float,
    abs_end: float,
    transcripts: list[dict],
    loud_bins: list[dict],
    chat_per_min: float,
    chat_base: float,
    loud_median: float | None,
) -> dict:
    texts = []
    hits_all: dict[str, list[str]] = defaultdict(list)
    laugh = False
    shout = False
    for t in transcripts:
        if t["abs_end"] < abs_start or t["abs_start"] > abs_end:
            continue
        texts.append(t["text"])
        h = keyword_hits(t["text"])
        for g, ws in h.items():
            hits_all[g].extend(ws)
        if has_laughter(t["text"]):
            laugh = True
    # loudness overlapping this window
    Ms = []
    for b in loud_bins:
        a0 = b.get("abs_t0", b["t0"])
        a1 = b.get("abs_t1", b["t1"])
        if a1 < abs_start or a0 > abs_end:
            continue
        if b.get("max_M") is not None:
            Ms.append(b["max_M"])
    max_M = max(Ms) if Ms else None
    mean_M = sum(Ms) / len(Ms) if Ms else None

    if loud_median is None:
        loud_median = -20.0
    if max_M is None:
        loud_z = 0.0
        loud_lu = 0.0
    else:
        loud_lu = max_M - loud_median
        loud_z = max(0.0, loud_lu / 6.0)

    if any(shouting(t, max_M, loud_median) for t in texts) or (
        max_M is not None and max_M >= loud_median + SHOUT_LU
    ):
        shout = True

    kw_score, strong_kw = _kw_score(hits_all)

    if chat_base and chat_base > 0:
        chat_z = max(0.0, (chat_per_min - chat_base) / max(chat_base, 5.0))
    else:
        chat_z = 0.0 if chat_per_min == 0 else min(1.0, chat_per_min / 30.0)

    laugh_s = 1.0 if laugh else 0.0
    shout_s = 0.7 if shout else 0.0

    has_chat = chat_per_min > 0 or chat_base > 0
    if has_chat:
        score = 0.35 * loud_z + 0.25 * kw_score + 0.15 * laugh_s + 0.15 * shout_s + 0.25 * chat_z
    else:
        score = 0.45 * loud_z + 0.30 * kw_score + 0.15 * laugh_s + 0.20 * shout_s

    loud_spike = loud_lu >= LOUD_SPIKE_LU
    chat_spike = has_chat and chat_z >= CHAT_SPIKE_Z
    transcript_cue = bool(laugh or strong_kw or shout)
    n_signals = int(loud_spike) + int(chat_spike) + int(transcript_cue)

    return {
        "abs_start": round(abs_start, 3),
        "abs_end": round(abs_end, 3),
        "duration": round(abs_end - abs_start, 3),
        "score": round(float(score), 3),
        "loud_max_M": max_M,
        "loud_mean_M": None if mean_M is None else round(mean_M, 2),
        "loud_z": round(loud_z, 3),
        "loud_lu": round(loud_lu, 2),
        "loud_spike": loud_spike,
        "keyword_groups": {k: sorted(set(v)) for k, v in hits_all.items()},
        "kw_score": round(kw_score, 3),
        "strong_kw": strong_kw,
        "laughter": laugh,
        "shouting": shout,
        "transcript_cue": transcript_cue,
        "chat_per_min": round(chat_per_min, 2),
        "chat_z": round(chat_z, 3),
        "chat_spike": chat_spike,
        "n_signals": n_signals,
        "summary": summarize_he(texts),
        "text_joined": " ".join(texts)[:400],
    }


def passes_strict_gate(sc: dict, has_chat: bool, kind: str = "short") -> bool:
    """Keep only genuinely strong moments.

    When chat exists: at least two of (loudness spike, chat-rate spike,
    transcript cue) and a high enough score.
    When chat is missing (typical VOD replay): loudness spike AND a
    transcript cue. Long highlights are slightly looser so a clear peak
    in a longer section can still ship as the primary 16:9 output.
    """
    loud = bool(sc.get("loud_spike"))
    chat = bool(sc.get("chat_spike"))
    cue = bool(sc.get("transcript_cue"))
    n = int(loud) + int(chat) + int(cue)
    score = float(sc.get("score") or 0)
    if kind == "long":
        if score < LONG_SCORE_MIN:
            return False
        if has_chat:
            return n >= 2 or (cue and score >= LONG_SCORE_MIN + 0.08)
        return cue and (loud or score >= LONG_SCORE_MIN + 0.10)
    # shorts: strict
    if score < SHORT_SCORE_MIN:
        return False
    if has_chat:
        return n >= 2
    return loud and cue


def rescore_candidate(session: Path, cand: dict) -> dict:
    """Re-run score_window on a stored candidate so old rows pick up new rules."""
    transcripts = load_jsonl(session / "transcript.jsonl")
    all_loud = load_jsonl(session / "loudness.jsonl")
    Ms = [b["max_M"] for b in all_loud if b.get("max_M") is not None]
    loud_median = sorted(Ms)[len(Ms) // 2] if Ms else -20.0
    chat_base = load_chat_baseline(session)
    n, per_min = chat_counts(session, float(cand["abs_start"]), float(cand["abs_end"]))
    sc = score_window(
        float(cand["abs_start"]), float(cand["abs_end"]),
        transcripts, all_loud, per_min, chat_base, loud_median,
    )
    out = dict(cand)
    out.update(sc)
    # preserve topic metadata if present
    for k in ("kind", "topic_kind", "topic_label", "window", "segment", "n_shorts"):
        if k in cand and k not in sc:
            out[k] = cand[k]
        elif k in cand:
            out[k] = cand[k]
    return out



def nms(cands: list[dict], iou_or_gap: float = 4.0, top_k: int = 12) -> list[dict]:
    cands = sorted(cands, key=lambda c: -c["score"])
    kept = []
    for c in cands:
        ok = True
        for k in kept:
            # overlap in time
            latest_start = max(c["abs_start"], k["abs_start"])
            earliest_end = min(c["abs_end"], k["abs_end"])
            if earliest_end - latest_start > iou_or_gap:
                ok = False
                break
        if ok:
            kept.append(c)
        if len(kept) >= top_k:
            break
    return sorted(kept, key=lambda c: c["abs_start"])


def process_one(session: Path, seg: Path, force: bool = False) -> None:
    if not seg.is_file():
        log(f"skip missing {seg}")
        return
    if not is_closed_mp4(seg):
        log(f"skip unreadable (open?) {seg.name}")
        return
    stamp = session / "processed" / f"{seg.name}.done"
    stamp.parent.mkdir(parents=True, exist_ok=True)
    if stamp.is_file() and not force:
        log(f"already processed {seg.name}")
        return

    duration = ffprobe_duration(seg)
    if not duration or duration < 1:
        log(f"skip too short/unknown duration {seg.name}")
        return

    abs_start = resolve_abs_start(session, seg, duration)
    rec = {
        "file": seg.name,
        "path": str(seg),
        "duration": round(duration, 3),
        "abs_start": round(abs_start, 3),
        "abs_end": round(abs_start + duration, 3),
        "size": seg.stat().st_size,
    }
    upsert_manifest(session, rec)
    log(f"process {seg.name} abs={abs_start:.1f}-{abs_start+duration:.1f} dur={duration:.1f}s")

    # Loudness
    bins = measure_loudness_10s(seg)
    for b in bins:
        b["abs_t0"] = round(abs_start + b["t0"], 3)
        b["abs_t1"] = round(abs_start + b["t1"], 3)
        b["file"] = seg.name
        append_jsonl(session / "loudness.jsonl", b)

    # Transcript
    parts = transcribe(seg)
    abs_rows = []
    for p in parts:
        row = {
            "file": seg.name,
            "rel_start": p["start"],
            "rel_end": p["end"],
            "abs_start": round(abs_start + p["start"], 3),
            "abs_end": round(abs_start + p["end"], 3),
            "text": p["text"],
            "words": [
                {
                    "start": w["start"],
                    "end": w["end"],
                    "abs_start": round(abs_start + w["start"], 3),
                    "abs_end": round(abs_start + w["end"], 3),
                    "word": w["word"],
                }
                for w in p["words"]
            ],
        }
        append_jsonl(session / "transcript.jsonl", row)
        abs_rows.append(row)

    # Also a running human-readable transcript
    with (session / "transcript.txt").open("a", encoding="utf-8") as f:
        for r in abs_rows:
            f.write(f"[{r['abs_start']:8.1f} -> {r['abs_end']:8.1f}] {r['text']}\n")

    # Signals + short-window candidates
    all_loud = load_jsonl(session / "loudness.jsonl")
    Ms = [b["max_M"] for b in all_loud if b.get("max_M") is not None]
    loud_median = sorted(Ms)[len(Ms) // 2] if Ms else -20.0
    chat_base = load_chat_baseline(session)
    transcripts = load_jsonl(session / "transcript.jsonl")

    # 20s windows hop 8s across this segment, plus 15s and 30s
    new_cands = []
    for win, hop in ((15.0, 7.0), (20.0, 8.0), (30.0, 10.0), (40.0, 12.0)):
        t = abs_start
        end = abs_start + duration
        while t + SHORT_MIN <= end + 0.01:
            w1 = min(t + win, end)
            if w1 - t < SHORT_MIN:
                break
            n, per_min = chat_counts(session, t, w1)
            sc = score_window(t, w1, transcripts, all_loud, per_min, chat_base, loud_median)
            sc["kind"] = "short"
            sc["window"] = win
            sc["segment"] = seg.name
            new_cands.append(sc)
            t += hop

    # Strict gate: weak/average talk is dropped here, before ranking.
    has_chat = chat_base > 0 or any(c["chat_per_min"] > 0 for c in new_cands)
    new_cands = [c for c in new_cands if passes_strict_gate(c, has_chat=has_chat, kind="short")]
    # Gambling / promo filter. Cheap text+category first so those windows
    # don't occupy the top-K slots; visual check on the survivors only.
    from gambling import is_gambling_window
    cheap = []
    for c in new_cands:
        text = f"{c.get('text_joined') or ''} {c.get('summary') or ''}"
        hit, reasons = is_gambling_window(
            session, c["abs_start"], c["abs_end"], text=text, do_visual=False
        )
        if hit:
            append_jsonl(session / "rejected_gambling.jsonl", {**c, "rejected": reasons})
            log(f"reject gambling candidate {c['abs_start']:.0f}-{c['abs_end']:.0f} {reasons}")
            continue
        cheap.append(c)
    new_cands = nms(cheap, iou_or_gap=8.0, top_k=SHORT_TOP_K_PER_SEGMENT)
    kept = []
    for c in new_cands:
        text = f"{c.get('text_joined') or ''} {c.get('summary') or ''}"
        hit, reasons = is_gambling_window(
            session, c["abs_start"], c["abs_end"], text=text, do_visual=True
        )
        if hit:
            append_jsonl(session / "rejected_gambling.jsonl", {**c, "rejected": reasons})
            log(f"reject gambling candidate (visual) {c['abs_start']:.0f}-{c['abs_end']:.0f} {reasons}")
            continue
        kept.append(c)
    new_cands = kept
    for c in new_cands:
        append_jsonl(session / "candidates.jsonl", c)

    update_topics(session)
    stamp.write_text(json.dumps({"file": seg.name, "abs_start": abs_start, "duration": duration}) + "\n")
    log(f"done {seg.name}: {len(new_cands)} short candidates, loud_median={loud_median}")
    try:
        from ready_queue import render_session_clips
        render_session_clips(session, finalize=False)
    except Exception as e:
        log(f"ready render after segment failed ({e})")


def update_topics(session: Path, finalize: bool = False) -> None:
    """Detect finished topics and write topics.json. Delegates to topics.py."""
    from topics import update_topic_model
    try:
        update_topic_model(session, finalize=finalize)
    except Exception as e:
        log(f"topic model failed ({e})")
        import traceback
        traceback.print_exc()


def list_closed_segments(session: Path, record_alive: bool) -> list[Path]:
    files = [p for p in session.glob("*.mp4") if is_segment_name(p)]
    files = sorted(files, key=lambda p: (parse_segment_wall(p) or p.stat().st_mtime, p.name))
    out = []
    for i, p in enumerate(files):
        # If recording is alive, the newest file may still be open
        if record_alive and i == len(files) - 1:
            if not is_closed_mp4(p):
                continue
            # even if ffprobe works, ffmpeg -f segment may still be writing;
            # treat as open if mtime is < 3s old and it's the newest
            if time.time() - p.stat().st_mtime < 3:
                continue
        elif not is_closed_mp4(p):
            continue
        out.append(p)
    return out


def record_is_alive(session: Path) -> bool:
    pidf = session / "record.pid"
    if not pidf.is_file():
        return False
    try:
        pid = int(pidf.read_text().strip())
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def watch(session: Path, poll: float = 15.0) -> None:
    log(f"watch {session}")
    # Preload model so the first closed segment is processed quickly
    try:
        get_model()
    except Exception as e:
        log(f"WARNING: could not preload whisper: {e}")
    stop = session / "STOP_WATCH"
    while not stop.is_file():
        try:
            from gambling import poll_and_log_category
            poll_and_log_category(session)
        except Exception as e:
            log(f"category poll failed ({e})")
        alive = record_is_alive(session)
        for seg in list_closed_segments(session, alive):
            try:
                process_one(session, seg)
            except Exception as e:
                log(f"ERROR processing {seg.name}: {e}")
                import traceback
                traceback.print_exc()
        try:
            update_topics(session, finalize=False)
        except Exception as e:
            log(f"topic model failed ({e})")
        if not alive and (session / "FINALIZE").is_file():
            break
        time.sleep(poll)
    # flush remaining
    for seg in list_closed_segments(session, record_is_alive(session)):
        try:
            process_one(session, seg)
        except Exception as e:
            log(f"ERROR processing {seg.name}: {e}")
    update_topics(session, finalize=True)
    log("watch exit")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--session", type=Path, required=True)
    p.add_argument("--segment", type=Path, default=None)
    p.add_argument("--watch", action="store_true")
    p.add_argument("--finalize", action="store_true")
    p.add_argument("--force", action="store_true")
    args = p.parse_args()
    session = args.session
    session.mkdir(parents=True, exist_ok=True)
    if args.watch:
        watch(session)
        return 0
    if args.segment:
        process_one(session, args.segment, force=args.force)
        return 0
    # process every closed segment, then maybe finalize topics
    for seg in list_closed_segments(session, record_is_alive(session)):
        process_one(session, seg, force=args.force)
    if args.finalize:
        update_topics(session, finalize=True)
        try:
            from ready_queue import render_session_clips
            n = render_session_clips(session, finalize=True)
            log(f"finalized topics and ready clips n={len(n)}")
        except Exception as e:
            log(f"finalized topics; ready render failed ({e})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

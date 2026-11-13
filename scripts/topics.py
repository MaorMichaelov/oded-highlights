#!/usr/bin/env python3
"""Topic-based segmentation for long 16:9 highlight videos.

One long video per *finished* topic (a game session, a video/TikTok/doc he
reacts to, a drama/discussion). A topic is closed only after the next one
has clearly started, or the stream has ended.

Boundaries come from, in order of strength:
  - Kick category / title changes (from category.jsonl)
  - Explicit transition phrases in the transcript
  - Sustained visual scene / layout change
  - Transcript topic shift (bag-of-words cosine)

Gambling topics are marked and never cut. Topics shorter than ~6 minutes
or with almost no real content are marked weak and skipped.
Shorts may only be taken from a finished, non-gambling, non-weak topic.
"""
from __future__ import annotations

import json
import math
import re
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

from config import CHANNEL
from gambling import (
    category_gambling_in_range,
    extract_frame,
    is_gambling_window,
    load_category_log,
    poll_and_log_category,
    transcript_gambling_hits,
)


def _ps():
    """Lazy import to avoid a circular import with process_segment."""
    import process_segment as ps
    return ps

# Minimum duration to *cut* a long topic video (and to allow shorts).
TOPIC_MIN_SEC = 360.0  # ~6 minutes
# Slivers smaller than this get merged into a neighbour.
TOPIC_MERGE_SEC = 150.0
# Last topic stays open until this much of the *next* topic has been seen.
NEXT_TOPIC_CONFIRM_SEC = 45.0
# Visual: 1 frame per this many seconds of a closed segment.
SCENE_STEP_SEC = 60.0
# Histogram cosine distance above this, over 2 consecutive bins, is a scene cut.
SCENE_DIST_THR = 0.42
# Transcript window similarity below this (with enough tokens) is a shift.
TEXT_SIM_THR = 0.18
TEXT_SIM_WEAK = 0.28
TEXT_MIN_TOKS = 8
# Reaction topics (see reaction_source.py). A reaction closes only when BOTH
# the reacted video is off the main screen AND the talk moves on.
REACTION_LEAD_SEC = 15.0      # include his intro right before the video starts
REACTION_MIN_TAIL_SEC = 30.0  # always keep at least this much post-video reaction
REACTION_WAIT_MAX_SEC = 600.0 # no talk shift this long after the video -> next strong cut

SHIFT_PHRASES = [
    "בואו נעבור",
    "בוא נעבור",
    "נעבור הלאה",
    "נעבור ל",
    "סרטון הבא",
    "הסרטון הבא",
    "טיקטוק הבא",
    "הבא בתור",
    "סיימנו",
    "סיימתי",
    "זהו סיימנו",
    "עוברים ל",
    "עוברים למשחק",
    "משחק חדש",
    "בוא נשחק משהו אחר",
    "next video",
    "next tiktok",
    "next one",
]


def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[\w\u0590-\u05FF]{2,}", (text or "").lower()) if t]


def _bow(text: str) -> Counter:
    c: Counter = Counter(_tokens(text))
    # char trigrams help Hebrew typo-y whisper text
    compact = re.sub(r"\s+", "", (text or "").lower())
    for i in range(len(compact) - 2):
        c["#" + compact[i : i + 3]] += 0.4
    return c


def _cosine(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    keys = set(a) | set(b)
    num = sum(a[k] * b[k] for k in keys)
    da = math.sqrt(sum(v * v for v in a.values()))
    db = math.sqrt(sum(v * v for v in b.values()))
    if da == 0 or db == 0:
        return 0.0
    return num / (da * db)


def _hist_feature(frame_path: Path) -> list[float] | None:
    try:
        import numpy as np
        from PIL import Image
        im = Image.open(frame_path).convert("RGB")
        # Use the center-right content area if the frame is 16:9 desktop
        w, h = im.size
        # skip typical facecam upper-right and kick bar; take mid-left game/video
        box = (int(w * 0.08), int(h * 0.08), int(w * 0.72), int(h * 0.92))
        im = im.crop(box).resize((64, 36), Image.BILINEAR)
        arr = np.asarray(im)
        # 4x4x4 RGB histogram, L1-normalized
        q = (arr.astype(np.int32) * 4 // 256).clip(0, 3)
        idx = q[:, :, 0] * 16 + q[:, :, 1] * 4 + q[:, :, 2]
        hist = np.bincount(idx.ravel(), minlength=64).astype(np.float32)
        s = hist.sum()
        if s <= 0:
            return None
        hist /= s
        return hist.tolist()
    except Exception:
        return None


def _hist_dist(a: list[float], b: list[float]) -> float:
    # cosine distance
    dot = sum(x * y for x, y in zip(a, b))
    da = math.sqrt(sum(x * x for x in a))
    db = math.sqrt(sum(x * x for x in b))
    if da == 0 or db == 0:
        return 1.0
    return 1.0 - (dot / (da * db))


def processed_end(session: Path) -> float:
    man = _ps().load_manifest(session)
    if not man:
        return 0.0
    return max(float(r.get("abs_end") or 0) for r in man)


def ensure_scene_features(session: Path) -> list[dict]:
    """Extract ~1 frame/minute from closed segments; cache features in scene_features.jsonl."""
    session = Path(session)
    existing = {round(float(r["abs_t"]), 1): r for r in _ps().load_jsonl(session / "scene_features.jsonl") if "abs_t" in r}
    start_ep = _ps().session_start_epoch(session)
    cache_dir = session / "frames" / "scene"
    new_rows = []
    for rec in _ps().load_manifest(session):
        p = Path(rec.get("path") or (session / rec["file"]))
        if not p.is_file():
            continue
        a0 = float(rec["abs_start"])
        a1 = float(rec["abs_end"])
        t = a0 + min(20.0, max(5.0, (a1 - a0) * 0.15))
        while t < a1 - 2:
            key = round(t, 1)
            if key not in existing:
                rel = t - a0
                dest = cache_dir / f"t{int(t):05d}.jpg"
                if not (dest.is_file() and dest.stat().st_size > 800):
                    if extract_frame(p, rel, dest) is None:
                        t += SCENE_STEP_SEC
                        continue
                feat = _hist_feature(dest)
                row = {"abs_t": round(t, 2), "file": p.name, "frame": str(dest), "hist": feat}
                with (session / "scene_features.jsonl").open("a", encoding="utf-8") as f:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
                existing[key] = row
                new_rows.append(row)
            t += SCENE_STEP_SEC
    rows = _ps().load_jsonl(session / "scene_features.jsonl")
    rows.sort(key=lambda r: float(r.get("abs_t") or 0))
    return rows


def _category_events(session: Path) -> list[tuple[float, dict]]:
    start_ep = _ps().session_start_epoch(session)
    if start_ep is None:
        return []
    out = []
    for r in load_category_log(session):
        try:
            out.append((float(r["epoch"]) - start_ep, r))
        except Exception:
            continue
    out.sort(key=lambda x: x[0])
    return out


def _phrase_boundaries(transcripts: list[dict]) -> list[tuple[float, str]]:
    found = []
    for r in transcripts:
        text = r.get("text") or ""
        low = text.lower()
        for p in SHIFT_PHRASES:
            if p.lower() in low:
                found.append((float(r.get("abs_end") or r.get("abs_start") or 0), f"phrase:{p}"))
                break
    return found


def _text_shift_boundaries(transcripts: list[dict]) -> list[tuple[float, str]]:
    if not transcripts:
        return []
    t_min = min(r["abs_start"] for r in transcripts)
    t_max = max(r["abs_end"] for r in transcripts)
    win, hop = 120.0, 60.0
    windows = []
    t = t_min
    while t + 40 < t_max:
        t1 = min(t + win, t_max)
        text = " ".join(
            r["text"] for r in transcripts if not (r["abs_end"] < t or r["abs_start"] >= t1)
        )
        toks = _tokens(text)
        windows.append((t, t1, text, _bow(text), len(toks)))
        t += hop
    bounds = []
    for i in range(1, len(windows)):
        _, _, _, b_prev, n_prev = windows[i - 1]
        t0, _, _, b_cur, n_cur = windows[i]
        if n_prev < TEXT_MIN_TOKS or n_cur < TEXT_MIN_TOKS:
            continue
        sim = _cosine(b_prev, b_cur)
        if sim < TEXT_SIM_THR:
            bounds.append((t0, f"transcript_shift:sim={sim:.2f}"))
        elif sim < TEXT_SIM_WEAK:
            bounds.append((t0, f"transcript_shift_weak:sim={sim:.2f}"))
    return bounds


def _visual_boundaries(features: list[dict]) -> list[tuple[float, str]]:
    pts = [(float(r["abs_t"]), r.get("hist")) for r in features if r.get("hist")]
    pts.sort(key=lambda x: x[0])
    bounds = []
    run = 0
    run_start = None
    run_dist = 0.0
    for i in range(1, len(pts)):
        d = _hist_dist(pts[i - 1][1], pts[i][1])
        if d >= SCENE_DIST_THR:
            run += 1
            if run_start is None:
                run_start = pts[i][0]
                run_dist = d
            run_dist = max(run_dist, d)
            # confirm with a second consecutive bin (or a very strong single jump)
            if run >= 2 or d >= 0.62:
                bounds.append((run_start, f"visual_scene:dist={run_dist:.2f}"))
                run = 0
                run_start = None
        else:
            run = 0
            run_start = None
    return bounds


def _category_boundaries(events: list[tuple[float, dict]]) -> list[tuple[float, str]]:
    bounds = []
    prev_key = None
    prev_title = None
    for t, r in events:
        if not r.get("live"):
            continue
        key = (
            (r.get("category_slug") or "").lower(),
            (r.get("parent_slug") or "").lower(),
        )
        title = (r.get("title") or "").strip()
        if prev_key is not None and key != prev_key and any(key):
            label = r.get("category_name") or r.get("category_slug") or "category"
            bounds.append((t, f"category_change:{label}"))
        if prev_title is not None and title and prev_title and title != prev_title:
            # Title changes are weaker (often just added tags); keep them
            # only if the strings differ by a decent amount.
            if abs(len(title) - len(prev_title)) > 8 or title.split("|")[0].strip() != prev_title.split("|")[0].strip():
                bounds.append((t, "title_change"))
        prev_key = key or prev_key
        if title:
            prev_title = title
    return bounds


def _merge_boundaries(bounds: list[tuple[float, str, int]], min_gap: float = 80.0) -> list[tuple[float, list[str], int]]:
    """Cluster nearby boundaries. strength 3=hard, 2=medium, 1=weak (needs a friend)."""
    if not bounds:
        return []
    bounds = sorted(bounds, key=lambda x: x[0])
    clusters = []
    cur_t, cur_whys, cur_s = bounds[0][0], [bounds[0][1]], bounds[0][2]
    for t, why, s in bounds[1:]:
        if t - cur_t <= min_gap:
            cur_whys.append(why)
            cur_s = max(cur_s, s)
        else:
            clusters.append((cur_t, cur_whys, cur_s))
            cur_t, cur_whys, cur_s = t, [why], s
    clusters.append((cur_t, cur_whys, cur_s))
    # Drop isolated weak (strength 1) clusters
    kept = []
    for t, whys, s in clusters:
        if s >= 2:
            kept.append((t, whys, s))
        elif any(not w.startswith("transcript_shift_weak") and not w.startswith("title_change") for w in whys):
            kept.append((t, whys, s))
    return kept


def _strength(why: str) -> int:
    if why.startswith("category_change") or why.startswith("phrase:") or why.startswith("visual_scene"):
        return 3
    if why.startswith("transcript_shift") and "weak" not in why:
        return 2
    return 1


def _label_topic(session: Path, t0: float, t1: float, transcripts: list[dict], gambling: bool) -> tuple[str, str, str]:
    texts = [r["text"] for r in transcripts if not (r["abs_end"] < t0 or r["abs_start"] >= t1)]
    kind, label = _ps().topic_label(texts)
    # Prefer category name when it is a game
    evs = _category_events(session)
    cat_name = ""
    start_mid = 0.5 * (t0 + t1)
    for t, r in evs:
        if t <= start_mid + 30:
            if r.get("category_name"):
                cat_name = r["category_name"]
        else:
            break
    if gambling:
        kind, label = "הימורים", "הימורים / קזינו"
    elif cat_name and cat_name.lower() not in {"just chatting", "irl", "pools", "music"}:
        if kind in {"אחר", "שיחה"} or not kind:
            kind, label = "משחק", cat_name
    summary = " ".join(texts)[:180]
    return kind, label, summary


def _is_weak_topic(session: Path, t0: float, t1: float, transcripts: list[dict], score: float) -> tuple[bool, str]:
    dur = t1 - t0
    if dur < TOPIC_MIN_SEC:
        return True, f"too_short:{dur:.0f}s"
    speech = sum(
        max(0.0, min(r["abs_end"], t1) - max(r["abs_start"], t0))
        for r in transcripts
        if not (r["abs_end"] < t0 or r["abs_start"] >= t1)
    )
    coverage = speech / max(dur, 1.0)
    n, per_min = _ps().chat_counts(session, t0, t1)
    if coverage < 0.08 and per_min < 2 and score < 0.25:
        return True, f"boring:speech={coverage:.2f} chat={per_min:.1f} score={score:.2f}"
    return False, ""


def _reaction_end(sp: dict, raw: list[tuple[float, str, int]], tend: float, finalize: bool) -> float | None:
    """End of a reaction topic, or None = keep the topic open (wait)."""
    if sp.get("status") != "ended":
        return tend if finalize else None
    a = float(sp["ended_at"])
    if str(sp.get("end_reason", "")).startswith("new_video"):
        # the next video starting is both a screen change and a subject change
        return max(float(sp["last_seen"]), a - REACTION_LEAD_SEC)
    talk = sorted(
        t for t, w, _ in raw
        if t >= a - 30 and (w.startswith("transcript_shift") or w.startswith("phrase:")
                            or w.startswith("category_change") or w.startswith("title_change"))
    )
    if talk:
        return max(a + REACTION_MIN_TAIL_SEC, talk[0])
    if finalize:
        return tend
    if tend - a > REACTION_WAIT_MAX_SEC:
        strong = sorted(t for t, w, st in raw if t >= a + 60 and st >= 3)
        if strong:
            return strong[0]
    return None


def _attach_source(rec: dict, spans: list[dict], texts: list[str]) -> None:
    t0, t1 = float(rec["abs_start"]), float(rec["abs_end"])
    best, best_ov = None, 0.0
    for sp in spans:
        s0 = float(sp["video_start"])
        s1 = float(sp.get("ended_at") or sp.get("last_seen") or s0)
        ov = max(0.0, min(t1, s1) - max(t0, s0))
        # the reacted video must fill most of the topic (not a 2-min tail of a long chat)
        if ov > best_ov and ov >= 0.5 * max(1.0, t1 - t0):
            best, best_ov = sp, ov
    if best:
        rec.update({
            "source_creator": best.get("creator"),
            "source_title": best.get("title"),
            "source_url": best.get("url"),
            "source_channel_url": best.get("creator_url"),
            "source_confidence": 0.95 if best.get("how") else 0.8,
            "source_verified_by": best.get("how"),
            "source_video_status": best.get("status"),
            "source_video_start": best.get("video_start"),
            "source_video_end": best.get("ended_at"),
        })
        rec["topic_kind"] = "reaction"
        try:
            from config import CREATOR_NAME_HE
        except ImportError:
            CREATOR_NAME_HE = {}
        cr = CREATOR_NAME_HE.get(best.get("creator") or "", best.get("creator") or "סרטון")
        rec["topic_label"] = f"ריאקשן ל{cr}" if re.match(r"[\u0590-\u05FF]", cr) else f"ריאקשן ל-{cr}"
        return
    hint = None
    try:
        from reaction_source import transcript_creator_hint
        hint = transcript_creator_hint(texts)
    except Exception:
        pass
    rec.update({
        "source_creator": hint,  # heard in the transcript only; not verified
        "source_title": None,
        "source_url": None,
        "source_confidence": 0.35 if hint else 0.0,
        "source_verified_by": "transcript_mention" if hint else None,
    })


def update_topic_model(session: Path, finalize: bool = False) -> dict:
    """Rebuild topics.json from current evidence. Idempotent."""
    session = Path(session)
    transcripts = _ps().load_jsonl(session / "transcript.jsonl")
    tend = processed_end(session)
    if tend < 30 and not transcripts:
        empty = {"topics": [], "sections": [], "updated": datetime.now().astimezone().isoformat(), "finalize": finalize}
        (session / "topics.json").write_text(json.dumps(empty, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return empty

    t0 = 0.0
    meta_start = 0.0
    # Prefer absolute 0 as stream start
    features = ensure_scene_features(session) if tend >= 30 else []

    raw: list[tuple[float, str, int]] = []
    for t, why in _category_boundaries(_category_events(session)):
        raw.append((t, why, _strength(why)))
    for t, why in _phrase_boundaries(transcripts):
        raw.append((t, why, _strength(why)))
    for t, why in _visual_boundaries(features):
        raw.append((t, why, _strength(why)))
    for t, why in _text_shift_boundaries(transcripts):
        raw.append((t, why, _strength(why)))

    # What is he reacting to? Keep each reacted video + his reaction as ONE topic.
    spans: list[dict] = []
    try:
        from reaction_source import build_spans
        spans = build_spans(session, tend)
    except Exception as e:
        _ps().log(f"reaction source scan failed ({e})")
    for i, sp in enumerate(spans):
        s0 = max(0.0, float(sp["video_start"]) - REACTION_LEAD_SEC)
        r_end = _reaction_end(sp, raw, tend, finalize)
        if r_end is not None and i + 1 < len(spans):
            r_end = min(r_end, max(s0 + 1, float(spans[i + 1]["video_start"]) - REACTION_LEAD_SEC))
        sp["reaction_end"] = r_end
        hi = r_end if r_end is not None else float("inf")
        raw = [(t, w, st) for t, w, st in raw if not (s0 + 20 < t < hi) or w.startswith("source_start")]
        raw.append((s0, f"source_start:{sp['id']}", 3))
        if r_end is not None and r_end < tend:
            raw.append((r_end, f"reaction_end:{sp.get('end_reason')}", 3))

    # Only place boundaries inside already-processed media
    raw = [(t, w, s) for t, w, s in raw if 20.0 <= t <= tend - (0.0 if finalize else NEXT_TOPIC_CONFIRM_SEC)]
    clusters = _merge_boundaries(raw)

    # Build [start, end) topic ranges. The last one stays open unless finalize
    # or we have confirmed the next topic (boundary + NEXT_TOPIC_CONFIRM_SEC of media).
    cuts = [t for t, _, _ in clusters]
    reasons_at = {round(t, 2): whys for t, whys, _ in clusters}

    points = [0.0] + cuts
    ranges: list[tuple[float, float, list[str], str]] = []
    for i, start in enumerate(points):
        if i + 1 < len(points):
            end = points[i + 1]
            status = "closed"
        else:
            end = tend
            status = "closed" if finalize else "open"
        # On finalize, close the last topic at processed end (or stream end).
        why = []
        # reasons that *started* this topic = the cut at `start`
        if start > 0:
            # find nearest cluster
            for ct, whys, _ in clusters:
                if abs(ct - start) < 2:
                    why = whys
                    break
        ranges.append((start, end, why, status))

    # Merge slivers
    merged = []
    for r in ranges:
        if merged and (r[1] - r[0]) < TOPIC_MERGE_SEC and r[3] == "closed":
            # absorb into previous
            ps, pe, pw, pst = merged[-1]
            merged[-1] = (ps, r[1], pw + [f"merged_sliver"] + r[2], pst if pst == "open" or r[3] == "open" else "closed")
        elif merged and (merged[-1][1] - merged[-1][0]) < TOPIC_MERGE_SEC:
            ps, pe, pw, pst = merged[-1]
            merged[-1] = (ps, r[1], pw + r[2], r[3])
        else:
            merged.append(r)
    ranges = merged

    all_loud = _ps().load_jsonl(session / "loudness.jsonl")
    Ms = [x["max_M"] for x in all_loud if x.get("max_M") is not None]
    loud_median = sorted(Ms)[len(Ms) // 2] if Ms else -20.0
    chat_base = _ps().load_chat_baseline(session)

    topics = []
    for i, (start, end, why, status) in enumerate(ranges, 1):
        dur = end - start
        if dur < 5:
            continue
        g_hit, g_reasons = is_gambling_window(session, start, end, do_visual=(dur >= 20 and status == "closed"))
        # Also flag if category was gambling anywhere in the span
        cat_hit, cat_why = category_gambling_in_range(session, start, end)
        if cat_hit:
            g_hit = True
            g_reasons = list(g_reasons) + [cat_why]
        sc = _ps().score_window(start, end, transcripts, all_loud, _ps().chat_counts(session, start, end)[1], chat_base, loud_median)
        kind, label, summary = _label_topic(session, start, end, transcripts, g_hit)
        weak, weak_why = _is_weak_topic(session, start, end, transcripts, float(sc.get("score") or 0))
        if g_hit:
            # gambling topics are skipped, not "weak"
            pass
        rec = {
            "id": f"topic_{i:03d}",
            "kind": "topic",
            "status": status,
            "topic_kind": kind,
            "topic_label": label,
            "abs_start": round(start, 3),
            "abs_end": round(end, 3),
            "duration": round(dur, 3),
            "score": round(float(sc.get("score") or 0), 3),
            "summary": sc.get("summary") or summary or label,
            "text_joined": " ".join(
                r["text"] for r in transcripts if not (r["abs_end"] < start or r["abs_start"] >= end)
            )[:500],
            "boundary_reasons": why,
            "gambling": bool(g_hit),
            "gambling_reasons": g_reasons,
            "weak": bool(weak and not g_hit),
            "weak_reason": weak_why,
            "chat_per_min": sc.get("chat_per_min"),
            "loud_max_M": sc.get("loud_max_M"),
            "keyword_groups": sc.get("keyword_groups") or {},
            "n_utterances": sum(
                1 for r in transcripts if not (r["abs_end"] < start or r["abs_start"] >= end)
            ),
        }
        _attach_source(rec, spans, [r["text"] for r in transcripts if not (r["abs_end"] < start or r["abs_start"] >= end)])
        topics.append(rec)

    payload = {
        "topics": topics,
        # sections: compatibility with older ready_queue (closed cuttable topics)
        "sections": [
            {**t, "kind": "topic"}
            for t in topics
        ],
        "updated": datetime.now().astimezone().isoformat(timespec="seconds"),
        "finalize": finalize,
        "processed_end": round(tend, 3),
        "reaction_sources": spans,
    }
    (session / "topics.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    n_closed = sum(1 for t in topics if t["status"] == "closed")
    n_g = sum(1 for t in topics if t["gambling"])
    _ps().log(f"topics updated n={len(topics)} closed={n_closed} gambling={n_g} processed_end={tend:.0f}s finalize={finalize}")
    return payload


def load_topics(session: Path) -> list[dict]:
    path = Path(session) / "topics.json"
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return list(data.get("topics") or data.get("sections") or [])


def finished_clipable_topics(session: Path) -> list[dict]:
    """Closed, non-gambling, non-weak topics long enough to cut."""
    out = []
    for t in load_topics(session):
        if t.get("status") not in {"closed", None}:
            # open topics are not clipable
            if t.get("status") == "open":
                continue
        if t.get("gambling"):
            continue
        if t.get("weak"):
            continue
        dur = float(t.get("duration") or (float(t.get("abs_end", 0)) - float(t.get("abs_start", 0))))
        if dur < TOPIC_MIN_SEC:
            continue
        out.append(t)
    return out


def topic_covering(session: Path, abs_start: float, abs_end: float) -> dict | None:
    mid = 0.5 * (abs_start + abs_end)
    for t in load_topics(session):
        if float(t.get("abs_start", 0)) - 1 <= mid <= float(t.get("abs_end", 0)) + 1:
            return t
    return None

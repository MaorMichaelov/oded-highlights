#!/usr/bin/env python3
"""Select strong moments, cut clips, and write a review-ready queue.

Long 16:9 highlights are the primary output. Shorts are cut only from
top-scoring moments that pass the multi-signal gate. Nothing is uploaded.

Each finished clip gets a JSON file in ready/:
  path, type (long|short), title (suggested Hebrew), score, source timestamps.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from config import (
    CUT_PAD_SEC,
    LONG_MAX,
    LONG_MAX_PER_HOUR,
    LONG_MIN,
    LONG_SCORE_MIN,
    READY,
    ROOT,
    SHORT_MAX,
    SHORT_MAX_PER_HOUR,
    SHORT_MIN,
    SHORT_NMS_GAP,
    SHORT_SCORE_MIN,
)
from config import CHANNEL, STREAMER_NAME_HE
try:
    from config import CREATOR_NAME_HE
except ImportError:  # older config
    CREATOR_NAME_HE = {}
from process_segment import load_jsonl, log

STEM_RE = re.compile(r"[^\w\u0590-\u05FF]+", re.UNICODE)


def _session_name(session: Path) -> str:
    return session.name


def ready_id(session: Path, kind: str, start: float, end: float) -> str:
    return f"{_session_name(session)}_{kind}_{int(start):05d}_{int(end):05d}"


def already_rendered(session: Path, kind: str, start: float, end: float) -> bool:
    rid = ready_id(session, kind, start, end)
    if (READY / f"{rid}.json").is_file():
        return True
    logf = session / "rendered.jsonl"
    for r in load_jsonl(logf):
        if r.get("id") == rid:
            return True
        # same kind overlapping almost the same range
        if r.get("type") == kind and abs(float(r.get("source_start", -1)) - start) < 4:
            return True
    return False


def _is_garbage_quote(text: str) -> bool:
    t = (text or "").strip()
    if len(t) < 3:
        return True
    # mostly punctuation or single characters repeated
    letters = re.findall(r"[\w\u0590-\u05FF]", t, re.UNICODE)
    if len(letters) < 3:
        return True
    return False


def _creator_he(creator: str) -> str:
    return CREATOR_NAME_HE.get(creator, creator)


def _le(name: str) -> str:
    """Hebrew 'ל' prefix; hyphenated before a non-Hebrew name."""
    return f"ל{name}" if re.match(r"[\u0590-\u05FF]", name or "") else f"ל-{name}"


def suggest_title(
    kind: str,
    summary: str = "",
    text: str = "",
    keyword_groups: dict | None = None,
    topic_label: str | None = None,
    source: dict | None = None,
) -> str:
    """Suggested Hebrew title from real transcript words / verified source only."""
    keyword_groups = keyword_groups or {}
    source = source or {}
    name = STREAMER_NAME_HE
    quote = (summary or "").strip().strip(".,!?;:\"'")
    drama = ("curse" in keyword_groups) or (topic_label == "דרמה")
    reaction = "reaction" in keyword_groups or (topic_label or "").startswith("ריאקשן")
    if drama:
        hook = f"{name} מתפוצץ"
    elif reaction:
        hook = f"{name} מגיב"
    else:
        hook = f"{name} בלייב"
    creator = source.get("source_creator")
    stitle = source.get("source_title")
    if creator and stitle and float(source.get("source_confidence") or 0) >= 0.8:
        t = f"{name} מגיב {_le(_creator_he(creator))} - {stitle}"
        return t[:100] if kind != "short" else t[:70]
    if kind == "short":
        if quote and not _is_garbage_quote(quote):
            return quote[:40]
        return hook
    # long highlight (primary)
    if quote and not _is_garbage_quote(quote):
        title = f'"{quote}" {hook}'
    elif topic_label:
        title = f"{hook} — {topic_label}"
    else:
        title = hook
    return title[:90]


def suggest_description(kind: str, source: dict | None = None) -> str:
    """Hebrew description with credit to the original video (verified only)."""
    source = source or {}
    name = STREAMER_NAME_HE
    lines = [f"קטע מהלייב של {name} בקיק: https://kick.com/{CHANNEL}"]
    creator, stitle, url = source.get("source_creator"), source.get("source_title"), source.get("source_url")
    if creator and stitle and url and float(source.get("source_confidence") or 0) >= 0.8:
        lines = [f"{name} מגיב לסרטון של {_creator_he(creator)}: \"{stitle}\"", ""] + lines + [
            "",
            f"הסרטון המקורי: {url}",
            f"קרדיט מלא לערוץ {creator}" + (f" ({source.get('source_channel_url')})" if source.get("source_channel_url") else "")
            + ". כל הזכויות על הסרטון המקורי שמורות ליוצר.",
        ]
    return "\n".join(lines)


def source_fields(c: dict | None) -> dict:
    c = c or {}
    keys = ["source_creator", "source_title", "source_url", "source_channel_url",
            "source_confidence", "source_verified_by", "topic_label", "id"]
    out = {k: c.get(k) for k in keys if k in c}
    if "id" in out:
        out["topic_id"] = out.pop("id")
    return out


def enqueue(
    *,
    path: Path,
    kind: str,
    title: str,
    score: float,
    source_start: float,
    source_end: float,
    session: Path,
    duration: float | None = None,
    extra: dict | None = None,
) -> Path:
    READY.mkdir(parents=True, exist_ok=True)
    rid = ready_id(session, kind, source_start, source_end)
    rec = {
        "id": rid,
        "path": str(path.resolve()) if path else "",
        "type": "long" if kind in {"long", "highlight", "long_highlight", "topic"} else "short",
        "title": title,
        "score": round(float(score), 3),
        "source_start": round(float(source_start), 3),
        "source_end": round(float(source_end), 3),
        "source_timestamps": [round(float(source_start), 3), round(float(source_end), 3)],
        "duration": None if duration is None else round(float(duration), 3),
        "session": str(session),
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "no_upload": True,
    }
    if extra:
        rec.update(extra)
    dest = READY / f"{rid}.json"
    dest.write_text(json.dumps(rec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    from process_segment import append_jsonl
    append_jsonl(session / "rendered.jsonl", {"id": rid, "type": rec["type"],
                                              "source_start": rec["source_start"],
                                              "source_end": rec["source_end"],
                                              "path": rec["path"],
                                              "ready": str(dest)})
    log(f"ready queue wrote {dest.name} type={rec['type']} score={rec['score']} title={title}")
    return dest


def _has_chat(session: Path) -> bool:
    return (session / "chat.jsonl").is_file() and bool(load_jsonl(session / "chat.jsonl"))


def _hour_bucket(t: float) -> int:
    return int(max(0.0, t) // 3600)



def select_shorts(session: Path, candidates: list[dict] | None = None) -> list[dict]:
    """Rank and keep only top-scoring shorts inside a *finished* topic.

    Shorts are not cut from an open topic, a gambling topic, or a weak/short
    one. Promo-code and gambling windows are rejected again here as a safety net.
    """
    from process_segment import nms, passes_strict_gate, rescore_candidate
    from topics import finished_clipable_topics, topic_covering
    from gambling import is_gambling_window

    allowed = finished_clipable_topics(session)
    if not allowed:
        return []

    has_chat = _has_chat(session)
    raw = candidates if candidates is not None else load_jsonl(session / "candidates.jsonl")
    raw = [c for c in raw if c.get("kind") == "short"]
    scored = [rescore_candidate(session, c) for c in raw]
    passed = [c for c in scored if passes_strict_gate(c, has_chat=has_chat, kind="short")]
    passed = nms(passed, iou_or_gap=SHORT_NMS_GAP, top_k=200)
    passed.sort(key=lambda c: -c["score"])
    kept: list[dict] = []
    per_hour: dict[int, int] = {}
    for c in passed:
        if c["score"] < SHORT_SCORE_MIN:
            continue
        if c.get("duration", 0) < SHORT_MIN * 0.7:
            continue
        mid = 0.5 * (float(c["abs_start"]) + float(c["abs_end"]))
        if not any(float(t["abs_start"]) - 1 <= mid <= float(t["abs_end"]) + 1 for t in allowed):
            continue
        cov = topic_covering(session, c["abs_start"], c["abs_end"])
        if cov is not None and (cov.get("gambling") or cov.get("weak") or cov.get("status") == "open"):
            continue
        text = f"{c.get('text_joined') or ''} {c.get('summary') or ''}"
        hit, reasons = is_gambling_window(
            session, float(c["abs_start"]), float(c["abs_end"]), text=text, do_visual=True
        )
        if hit:
            log(f"select_shorts skip gambling {c['abs_start']:.0f}-{c['abs_end']:.0f} {reasons}")
            continue
        h = _hour_bucket(c["abs_start"])
        if per_hour.get(h, 0) >= SHORT_MAX_PER_HOUR:
            continue
        if cov is not None:
            c["topic_label"] = cov.get("topic_label") or c.get("topic_label")
            c["topic_id"] = cov.get("id")
        kept.append(c)
        per_hour[h] = per_hour.get(h, 0) + 1
    return sorted(kept, key=lambda c: c["abs_start"])


def select_longs(session: Path) -> list[dict]:
    """One 16:9 video per finished topic, covering that topic start to end.

    Replaces the old '2 longs per hour of ~5 minutes' cap. Gambling, weak,
    short (< ~6 min), and still-open topics are skipped.
    """
    from gambling import is_gambling_window
    from topics import finished_clipable_topics

    kept: list[dict] = []
    for t in finished_clipable_topics(session):
        rec = dict(t)
        rec["kind"] = "long"
        rec["abs_start"] = float(t["abs_start"])
        rec["abs_end"] = float(t["abs_end"])
        rec["duration"] = rec["abs_end"] - rec["abs_start"]
        text = f"{t.get('text_joined') or ''} {t.get('summary') or ''}"
        hit, reasons = is_gambling_window(
            session, rec["abs_start"], rec["abs_end"], text=text, do_visual=True
        )
        if hit or rec.get("gambling"):
            log(f"select_longs skip gambling topic {rec.get('id')} {reasons}")
            continue
        kept.append(rec)
    return sorted(kept, key=lambda c: c["abs_start"])



def _processed_end(session: Path) -> float:
    man = load_jsonl(session / "segments.jsonl")
    if not man:
        return 0.0
    return max(float(r.get("abs_end") or 0) for r in man)


def render_session_clips(session: Path, finalize: bool = False) -> list[Path]:
    """Cut selected clips and write ready/ JSON. Safe to call repeatedly."""
    from cut_clip import cut_and_maybe_enqueue

    written: list[Path] = []
    processed_end = _processed_end(session)
    # During a live session, don't cut a moment that hasn't finished yet.
    live_margin = 0.0 if finalize else 20.0

    longs = select_longs(session) if finalize or processed_end > 180 else []
    if not finalize:
        # Only cut a long once its end is well behind the current processed edge.
        longs = [c for c in longs if c["abs_end"] <= processed_end - 30]
    try:
        from config import ENABLE_SHORTS
    except ImportError:
        ENABLE_SHORTS = True
    shorts = select_shorts(session) if ENABLE_SHORTS else []
    if not finalize:
        shorts = [c for c in shorts if c["abs_end"] <= processed_end - live_margin]

    # Longs first (primary output), then top shorts.
    jobs = [("long", c) for c in longs] + [("short", c) for c in shorts]
    for kind, c in jobs:
        start, end = float(c["abs_start"]), float(c["abs_end"])
        if already_rendered(session, kind, start, end):
            continue
        try:
            dest = cut_and_maybe_enqueue(session, start, end, kind=kind, candidate=c)
            if dest:
                written.append(dest)
        except Exception as e:
            log(f"ERROR cutting {kind} {start:.1f}-{end:.1f}: {e}")
            import traceback
            traceback.print_exc()
    return written


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--session", type=Path, required=True)
    p.add_argument("--finalize", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    if args.dry_run:
        shorts = select_shorts(args.session)
        longs = select_longs(args.session)
        print(json.dumps({
            "longs": [{"start": c["abs_start"], "end": c["abs_end"], "score": c["score"],
                       "title": suggest_title("long", c.get("summary") or "", c.get("text_joined") or "",
                                              c.get("keyword_groups") or {}, c.get("topic_label"))}
                      for c in longs],
            "shorts": [{"start": c["abs_start"], "end": c["abs_end"], "score": c["score"],
                        "title": suggest_title("short", c.get("summary") or "", c.get("text_joined") or "",
                                               c.get("keyword_groups") or {}, c.get("topic_label"))}
                       for c in shorts],
        }, ensure_ascii=False, indent=2))
    else:
        out = render_session_clips(args.session, finalize=args.finalize)
        print(json.dumps([str(p) for p in out], ensure_ascii=False, indent=2))

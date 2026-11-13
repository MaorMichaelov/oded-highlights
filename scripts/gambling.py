#!/usr/bin/env python3
"""Reject clips only when he is *actually gambling*.

Used by both the Oded and Ronen clipper pipelines. A candidate or topic
is dropped if ANY of these fire:

  (a) Kick livestream category at that time is Slots / Casino / Gambling
  (b) Sustained talk about his bets / spins / casino play
  (c) The *main screen content* is a casino / slots game

Permanent Stake overlay ads (corner "200% BONUS / CLAIM BONUS" or raffle
box, bottom Stake banner) must NOT reject a clip and must NEVER be
blacked out or masked — leave the frame as-is.

A single "Stake" / "bonus" / promo-code mention is not enough. Promo
codes reject only when he is actively reading or promoting the code
at length.

"$" in Kick donation overlays is NOT a gambling signal.
The stream title may contain "Stake" / "Code …" as a standing promo —
never treat the session title itself as evidence for a specific window.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from config import CHANNEL, KICK_UA, KICK_ORIGIN

# --- Transcript cues -------------------------------------------------------

# Weak / incidental: standing brand and overlay words. A single mention of
# these (or even a couple) is normal on a stream that always shows Stake ads.
# They never reject a clip on their own.
WEAK_GAMBLING_CUES: list[str] = [
    "stake", "סטייק", "stake.com",
    "bonus", "בונוס",
    "ronengg",
    "raffle", "ראפל",
]

# Strong activity cues: he is playing or talking about gambling itself.
STRONG_GAMBLING_CUES: list[str] = [
    "סלוטים", "סלוט", "סלוטס", "slot", "slots",
    "קזינו", "casino", "קסינו",
    "רולטה", "roulette",
    "בלאקג'ק", "בלקג'ק", "blackjack", "baccarat", "באקרה",
    "plinko", "פלינקו", "keno", "limbo", "mines", "מיינס",
    "הימור", "הימורים", "להמר", "מהמר", "מהמרים", "המרתי", "המרנו",
    "gamble", "gambling", "wager", "betting",
    "בונוס ביי", "בונוס באי", "bonus buy", "bonusbuy",
    "ספינים", "ספין", "spin", "spins", "ספינא",
    "מולטיפלייר", "מולטיפלייר", "multiplier",
    "באלאנס", "הבאלאנס",
    "רייקבק", "rakeback", "rake back",
    "high roller", "היי רולר",
]

# Back-compat alias used by a few tests / callers
GAMBLING_CUES: list[str] = STRONG_GAMBLING_CUES + WEAK_GAMBLING_CUES

# Whole-word only (too common as substrings otherwise)
GAMBLING_WHOLE_WORDS = {
    "bet", "bets", "betting", "spin", "spins", "slot", "slots",
    "bonus", "stake", "mines", "crash", "limbo", "keno", "wager",
    "balance", "raffle",
}

# Promo-code mentions (Stake affiliate). "קוד" alone is a common Hebrew
# word, so it must sit next to a promo/brand cue.
PROMO_RE = re.compile(
    r"(?:"
    r"\b(?:use\s+)?(?:promo\s*)?code\s+[a-z0-9_]{3,}"
    r"|\bcode\s+ronen\w*"
    r"|(?:קוד|פרומו(?:\s*קוד)?)\s*(?:שלי|שלנו|רונן|ronen\w*|stake|סטייק|פרומו)"
    r"|(?:קוד\s+)?פרומו"
    r"|\bpromo\s*code\b"
    r"|\baffiliate\s+code\b"
    r")",
    re.IGNORECASE,
)

# Slot-style multipliers: x100, x500, x1000, 1000x — not CS "x" names
MULTIPLIER_RE = re.compile(
    r"(?:\b[xX]\s?(?:[2-9]\d{2}|\d{4,})\b|(?:\b(?:[2-9]\d{2}|\d{4,})\s?[xX]\b))",
)

GAMBLING_CATEGORY_SLUGS = {
    "slots", "casino", "gambling", "slots-casino", "slots-and-casino",
    "slots-amp-casino", "roulette", "blackjack", "poker",
}
GAMBLING_CATEGORY_NAMES = {
    "slots", "casino", "gambling", "slots & casino", "slots and casino",
    "roulette", "blackjack", "poker", "stake",
}
GAMBLING_PARENT_SLUGS = {"gambling"}

_CATEGORY_POLL_GAP = 20.0  # seconds, min interval


def _norm(text: str) -> str:
    return (text or "").lower().replace("’", "'").replace("׳", "'")


def _hit_word(text_low: str, word: str) -> bool:
    w = word.lower()
    if " " in w:
        return w in text_low
    if w in GAMBLING_WHOLE_WORDS or (w.isascii() and len(w) <= 6):
        return re.search(rf"(?<![a-z0-9]){re.escape(w)}(?![a-z0-9])", text_low) is not None
    return w in text_low



def _hits_in(text: str, cues: list[str]) -> list[str]:
    if not text:
        return []
    low = _norm(text)
    found: list[str] = []
    for w in cues:
        if w.lower() in {"ronengg"}:
            continue
        if _hit_word(low, w) and w not in found:
            found.append(w)
    return found


def transcript_gambling_hits(text: str) -> list[str]:
    """Strong activity cues in text. Weak brand words (Stake/bonus) are omitted."""
    found = _hits_in(text, STRONG_GAMBLING_CUES)
    if MULTIPLIER_RE.search(text or ""):
        found.append("multiplier_xn")
    return found


def weak_brand_hits(text: str) -> list[str]:
    return _hits_in(text, WEAK_GAMBLING_CUES)


def has_promo_code(text: str) -> bool:
    """Any promo-code mention (including a passing one). See promo_pitch_at_length."""
    return bool(PROMO_RE.search(text or ""))


def _utterances(session: Path | None, abs_start: float, abs_end: float, fallback_text: str) -> list[dict]:
    rows: list[dict] = []
    if session is not None:
        tpath = Path(session) / "transcript.jsonl"
        if tpath.is_file():
            for line in tpath.read_text(encoding="utf-8").splitlines():
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if r.get("abs_end", -1) < abs_start or r.get("abs_start", 1e18) > abs_end:
                    continue
                rows.append(r)
    if rows:
        return rows
    # Fall back to splitting the provided blob into sentence-like bits
    chunks = [c.strip() for c in re.split(r"[\n.!?;]+", fallback_text or "") if c.strip()]
    return [{"text": c, "abs_start": abs_start, "abs_end": abs_end} for c in chunks]


def sustained_gambling_talk(
    text: str,
    session: Path | None = None,
    abs_start: float = 0.0,
    abs_end: float = 0.0,
) -> tuple[bool, list[str]]:
    """True only when he is actually talking about betting / spinning, not a one-off 'Stake' or 'bonus'.

    Requires two or more strong utterances, two distinct strong cue types,
    a strong cue repeated 3+ times, or 12+ seconds of such talk.
    """
    utts = _utterances(session, abs_start, abs_end, text)
    strong_utts = []
    term_counts: dict[str, int] = {}
    talk_dur = 0.0
    for r in utts:
        hits = transcript_gambling_hits(r.get("text") or "")
        if hits:
            strong_utts.append(hits)
            for h in hits:
                term_counts[h] = term_counts.get(h, 0) + 1
            talk_dur += max(0.0, float(r.get("abs_end") or 0) - float(r.get("abs_start") or 0))
    # If we only have a single blob with no timings, use hit diversity / repetition
    all_hits = transcript_gambling_hits(text)
    n_utts = len(strong_utts)
    n_types = len(term_counts)
    n_total = sum(term_counts.values()) or len(all_hits)
    if n_utts >= 2 or n_types >= 2 or n_total >= 3 or talk_dur >= 12.0:
        why = (
            "sustained_talk utts=%s types=%s hits=%s dur=%.0fs"
            % (n_utts, n_types, ",".join(list(term_counts)[:8] or all_hits[:8]), talk_dur)
        )
        return True, [why]
    return False, []


def promo_pitch_at_length(
    text: str,
    session: Path | None = None,
    abs_start: float = 0.0,
    abs_end: float = 0.0,
) -> tuple[bool, str]:
    """Reject only if he is actively reading / promoting a code at length.

    A single 'code RonenGG' or 'קוד רונן' is not enough — that can appear
    in passing or on the standing overlay. Need 2+ separate utterances,
    or promo talk spanning 12+ seconds, or 3+ promo-tagged lines.
    """
    utts = _utterances(session, abs_start, abs_end, text)
    promo_utts = []
    for r in utts:
        tx = r.get("text") or ""
        if PROMO_RE.search(tx) or re.search(r"(?:use\s+code|promo\s*code|affiliate)|(?:קוד רונן|קוד ronen|פרומו קוד)", tx, re.I):
            promo_utts.append(r)
    matches = list(PROMO_RE.finditer(text or ""))
    dur = sum(max(0.0, float(r.get("abs_end") or 0) - float(r.get("abs_start") or 0)) for r in promo_utts)
    if len(promo_utts) >= 2 or len(matches) >= 2 or dur >= 12.0:
        return True, f"promo_pitch utts={len(promo_utts)} matches={len(matches)} dur={dur:.0f}s"
    return False, ""


def category_is_gambling(cat: dict | None) -> bool:
    if not cat:
        return False
    slugs = {
        str(cat.get("slug") or "").lower().strip(),
        str(cat.get("category_slug") or "").lower().strip(),
        str(cat.get("parent_slug") or "").lower().strip(),
        str((cat.get("category") or {}).get("slug") or "").lower().strip(),
    }
    names = {
        str(cat.get("name") or "").lower().strip(),
        str(cat.get("category_name") or "").lower().strip(),
        str(cat.get("parent_name") or "").lower().strip(),
        str((cat.get("category") or {}).get("name") or "").lower().strip(),
    }
    tags = [str(t).lower() for t in (cat.get("tags") or [])]
    if slugs & GAMBLING_CATEGORY_SLUGS or slugs & GAMBLING_PARENT_SLUGS:
        return True
    if names & GAMBLING_CATEGORY_NAMES:
        return True
    if "gambling" in tags or "casino" in tags or "slots" in tags:
        return True
    return False


def _flatten_livestream_category(data: dict) -> dict:
    ls = data.get("livestream") or {}
    cats = ls.get("categories") or []
    top = cats[0] if cats else {}
    parent = top.get("category") or {}
    rec = {
        "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
        "epoch": time.time(),
        "live": bool(ls),
        "title": (ls.get("session_title") or ls.get("title") or "") if ls else "",
        "category_name": top.get("name") or "",
        "category_slug": top.get("slug") or "",
        "category_id": top.get("id"),
        "parent_name": parent.get("name") or "",
        "parent_slug": parent.get("slug") or "",
        "tags": list(top.get("tags") or []),
        "viewers": ls.get("viewer_count") if ls else None,
    }
    rec["gambling"] = category_is_gambling(rec) or category_is_gambling(top)
    return rec


def poll_and_log_category(session: Path, slug: str | None = None) -> dict | None:
    """Fetch current Kick category and append to session/category.jsonl.

    Rate-limited. Safe to call every watch loop. Returns the logged row or
    None if skipped/failed.
    """
    slug = slug or CHANNEL
    session = Path(session)
    logf = session / "category.jsonl"
    # rate limit
    try:
        if logf.is_file() and logf.stat().st_size > 0:
            last = logf.read_text(encoding="utf-8").strip().splitlines()[-1]
            prev = json.loads(last)
            if time.time() - float(prev.get("epoch") or 0) < _CATEGORY_POLL_GAP:
                return prev
    except Exception:
        pass
    url = f"https://kick.com/api/v2/channels/{slug}"
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": KICK_UA,
                "Accept": "application/json",
                "Origin": KICK_ORIGIN,
            },
        )
        with urllib.request.urlopen(req, timeout=12) as r:
            data = json.load(r)
    except Exception:
        return None
    rec = _flatten_livestream_category(data)
    rec["slug"] = slug
    with logf.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def load_category_log(session: Path) -> list[dict]:
    path = Path(session) / "category.jsonl"
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


def _session_start_epoch(session: Path) -> float | None:
    meta = Path(session) / "session_meta.json"
    if meta.is_file():
        try:
            return float(json.loads(meta.read_text(encoding="utf-8")).get("started_epoch"))
        except Exception:
            return None
    return None


def category_gambling_in_range(session: Path, abs_start: float, abs_end: float) -> tuple[bool, str]:
    """True if a logged Kick category overlapping [abs_start, abs_end] is gambling.

    Category samples are wall-clock; we convert to stream-absolute using
    session started_epoch. If we have no overlap in the log, returns False
    (other detectors still apply).
    """
    rows = load_category_log(session)
    if not rows:
        return False, ""
    start_ep = _session_start_epoch(session)
    if start_ep is None:
        return False, ""
    # Each poll covers the time until the next poll (or a short window after last)
    events = []
    for r in rows:
        try:
            ev_abs = float(r["epoch"]) - start_ep
        except Exception:
            continue
        events.append((ev_abs, r))
    events.sort(key=lambda x: x[0])
    for i, (t0, r) in enumerate(events):
        t1 = events[i + 1][0] if i + 1 < len(events) else t0 + 90.0
        if t1 < abs_start or t0 > abs_end:
            continue
        if r.get("gambling") or category_is_gambling(r):
            label = r.get("category_name") or r.get("parent_name") or r.get("category_slug") or "gambling"
            return True, f"kick_category:{label}"
    return False, ""


# --- Cheap visual check -----------------------------------------------------

def extract_frame(src: Path, t_rel: float, dest: Path) -> Path | None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    t_rel = max(0.0, float(t_rel))
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-ss", f"{t_rel:.3f}", "-i", str(src),
        "-frames:v", "1", "-q:v", "4", str(dest),
    ]
    try:
        subprocess.run(cmd, check=True, timeout=20)
    except Exception:
        return None
    return dest if dest.is_file() and dest.stat().st_size > 1000 else None



def _stake_green_and_dark_masks(arr):
    """Boolean masks on an RGB float array (H,W,3)."""
    import numpy as np
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    stake_green = (g > 90) & (g > r * 1.35) & (g > b * 1.35) & ((g - mn) > 40)
    # Also count typical Stake navy/gold promo chrome as "ad", not used for
    # the main-area casino test (those live in the overlay zone we mask out).
    dark = mx < 45
    return stake_green, dark


def _stake_green_and_dark_fractions(im) -> tuple[float, float]:
    """Whole-frame fractions (kept for debugging / older tests)."""
    import numpy as np
    from PIL import Image

    small = im.convert("RGB").resize((320, 180), Image.BILINEAR)
    arr = np.asarray(small, dtype=np.float32)
    green, dark = _stake_green_and_dark_masks(arr)
    n = arr.shape[0] * arr.shape[1]
    return float(green.sum()) / n, float(dark.sum()) / n


def _overlay_ignore_mask(h: int, w: int):
    """Pixels that belong to standing Stake overlay ads, not the main picture.

    Ronen permanently shows a bottom Stake banner and a bottom-right
    'BONUS / CLAIM BONUS' or raffle box. Those must be ignored.
    """
    import numpy as np
    mask = np.zeros((h, w), dtype=bool)
    # Bottom banner (~14% of the frame height)
    mask[int(h * 0.86) :, :] = True
    # Bottom-right promo / raffle box, sitting just above the banner
    mask[int(h * 0.52) : int(h * 0.90), int(w * 0.68) :] = True
    return mask


def visual_casino_ui(frame_path: Path) -> tuple[bool, str]:
    """True only if the MAIN content area looks like a casino/slots game.

    Standing corner boxes and the bottom Stake banner are ignored. We
    never black out or mask those ads in the output clip — this mask is
    only for the detector. CS / IRL cam / YouTube should not trip it.
    """
    try:
        import numpy as np
        from PIL import Image
        im = Image.open(frame_path)
        im.load()
    except Exception:
        return False, ""
    small = im.convert("RGB").resize((320, 180), Image.BILINEAR)
    arr = np.asarray(small, dtype=np.float32)
    h, w = arr.shape[0], arr.shape[1]
    ignore = _overlay_ignore_mask(h, w)
    main = ~ignore
    green, dark = _stake_green_and_dark_masks(arr)
    main_n = int(main.sum()) or 1
    main_green = float((green & main).sum()) / main_n
    main_dark = float((dark & main).sum()) / main_n
    # Spatial extent: casino UI should fill a large part of the main area,
    # not a leftover sliver next to the overlays.
    ys, xs = np.where(dark & main)
    coverage = 0.0
    if len(xs) >= 20:
        coverage = ((xs.max() - xs.min() + 1) * (ys.max() - ys.min() + 1)) / main_n

    # Require the main picture itself to look like a dark Stake/slots page.
    if main_dark >= 0.50 and main_green >= 0.05 and coverage >= 0.35:
        return True, (
            f"visual:main_casino dark={main_dark:.2f} green={main_green:.3f} "
            f"cover={coverage:.2f}"
        )
    if main_green >= 0.12 and main_dark >= 0.35 and coverage >= 0.40:
        return True, (
            f"visual:main_slots dark={main_dark:.2f} green={main_green:.3f} "
            f"cover={coverage:.2f}"
        )
    return False, ""


def _segment_for_abs(session: Path, abs_t: float) -> tuple[Path, float] | None:
    """Return (mp4 path, relative seconds) for a stream-absolute timestamp."""
    man = Path(session) / "segments.jsonl"
    rows = []
    if man.is_file():
        for line in man.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    for r in rows:
        try:
            a0 = float(r.get("abs_start"))
            a1 = float(r.get("abs_end"))
        except Exception:
            continue
        if a0 - 0.5 <= abs_t <= a1 + 0.5:
            p = Path(r.get("path") or (Path(session) / r["file"]))
            if p.is_file():
                return p, max(0.0, abs_t - a0)
    # Fallback: parse filenames in the session dir
    from process_segment import parse_segment_wall, session_start_epoch, is_segment_name, ffprobe_duration

    start_ep = session_start_epoch(session)
    for p in sorted(Path(session).glob("*.mp4")):
        if not is_segment_name(p):
            continue
        wall = parse_segment_wall(p)
        if start_ep is None or wall is None:
            continue
        a0 = max(0.0, wall - start_ep)
        dur = ffprobe_duration(p) or 0.0
        if a0 - 0.5 <= abs_t <= a0 + dur + 0.5:
            return p, max(0.0, abs_t - a0)
    return None


def visual_gambling_in_range(session: Path, abs_start: float, abs_end: float) -> tuple[bool, str]:
    """Extract 1 (short) or 2 (long) mid-frames and test for casino UI."""
    dur = max(0.1, abs_end - abs_start)
    if dur >= 90:
        times = [abs_start + dur * 0.33, abs_start + dur * 0.66]
    else:
        times = [abs_start + dur * 0.5]
    cache = Path(session) / "frames" / "gamble_check"
    reasons = []
    for i, t in enumerate(times):
        loc = _segment_for_abs(session, t)
        if not loc:
            continue
        src, rel = loc
        dest = cache / f"t{int(t):05d}_{i}.jpg"
        if not (dest.is_file() and dest.stat().st_size > 1000):
            if extract_frame(src, rel, dest) is None:
                continue
        hit, why = visual_casino_ui(dest)
        if hit:
            reasons.append(why)
    if reasons:
        return True, "; ".join(reasons)
    return False, ""


def window_text(session: Path, abs_start: float, abs_end: float, extra_text: str = "", include_chat: bool = False) -> str:
    parts = [extra_text or ""]
    tpath = Path(session) / "transcript.jsonl"
    if tpath.is_file():
        for line in tpath.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("abs_end", -1) < abs_start or r.get("abs_start", 1e18) > abs_end:
                continue
            parts.append(r.get("text") or "")
    # Chat often repeats standing Stake ads; do not use it unless asked.
    cpath = Path(session) / "chat.jsonl"
    if include_chat and cpath.is_file():
        start_ep = _session_start_epoch(session)
        for line in cpath.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = r.get("abs_ts") or r.get("abs_time") or r.get("t") or r.get("epoch")
            if ts is None:
                continue
            try:
                ts = float(ts)
            except Exception:
                continue
            if start_ep and ts > 1e9:  # wall epoch
                ts = ts - start_ep
            if abs_start - 2 <= ts <= abs_end + 2:
                parts.append(str(r.get("content") or r.get("message") or r.get("text") or ""))
    return " ".join(parts)



def is_gambling_window(
    session: Path,
    abs_start: float,
    abs_end: float,
    text: str | None = None,
    do_visual: bool = True,
) -> tuple[bool, list[str]]:
    """Combined detector. Returns (rejected, reasons).

    Overlay ads and one-off 'Stake'/'bonus'/promo words do not reject.
    """
    reasons: list[str] = []
    cat_hit, cat_why = category_gambling_in_range(session, abs_start, abs_end)
    if cat_hit:
        reasons.append(cat_why)

    # Transcript only — chat often repeats the standing promo/ad and must
    # not reject a clip by itself.
    blob = text if text is not None else ""
    if not blob:
        blob = window_text(session, abs_start, abs_end, include_chat=False)

    talk, talk_why = sustained_gambling_talk(blob, session, abs_start, abs_end)
    if talk:
        reasons.extend(talk_why)
    pitch, pitch_why = promo_pitch_at_length(blob, session, abs_start, abs_end)
    if pitch:
        reasons.append(pitch_why)

    if do_visual and not reasons:
        v_hit, v_why = visual_gambling_in_range(session, abs_start, abs_end)
        if v_hit:
            reasons.append(v_why)
    return bool(reasons), reasons

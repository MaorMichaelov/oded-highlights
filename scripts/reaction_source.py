#!/usr/bin/env python3
"""What is the streamer reacting to? (YouTube source detection)

Every SAMPLE_STEP seconds of processed media we OCR one main-screen frame
(tesseract heb+eng; the right-hand facecam/chat strip is ignored) and look for
  - a YouTube watch page: URL bar 'watch?v=', player timecode 'm:ss / mm:ss',
    the video title under the player
  - a YouTube browse/channel page (= he is between videos)
Title-like OCR lines are searched on YouTube (yt-dlp flat search, no login)
and only accepted when the result title closely matches the on-screen text
and YouTube oEmbed confirms title + channel. Nothing is guessed: an
unverified source stays unknown (confidence 0) or, if only the creator's
name is heard in the transcript, creator-only with low confidence.

Outputs (per session):
  source_frames.jsonl  one OCR row per sampled frame
  source_cache.json    search / oEmbed results
  sources.json         reaction spans: video id, title, creator, url,
                       first/last seen, estimated and observed end
"""
from __future__ import annotations

import difflib
import json
import re
import subprocess
import time
from pathlib import Path

SAMPLE_STEP = 30.0
MATCH_MIN = 0.72          # OCR line vs YouTube title similarity to accept
MAX_SEARCHES_PER_RUN = 8
MAIN_X_MAX = 0.74         # ignore OCR boxes right of this (Kick facecam/chat overlay)
TIMECODE_RE = re.compile(r"(?<![\d:/])(\d{1,2}:?\d{2}(?::\d{2})?|\d{2})\s*/\s*(\d{1,2}:?\d{2}(?::\d{2})?)(?![\d:/])")
VID_RE = re.compile(r"v[=:s«]?\s*([A-Za-z0-9_-]{11})")


def _ps():
    import process_segment as ps
    return ps


def _norm(s: str) -> str:
    s = re.sub(r"[^\w\u0590-\u05FF ]+", " ", s or "", flags=re.UNICODE)
    return re.sub(r"\s+", " ", s).strip().lower()


def _sim(a: str, b: str) -> float:
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return 0.0
    # line may be a cropped piece of the title or title + junk
    if len(a) > len(b):
        a, b = b, a
    best = difflib.SequenceMatcher(None, a, b).ratio()
    if len(a) >= 12:
        sm = difflib.SequenceMatcher(None, a, b)
        m = sum(bl.size for bl in sm.get_matching_blocks())
        best = max(best, m / max(1, len(a)) * min(1.0, len(a) / max(1, 0.6 * len(b))))
    return best


def _hms(s: str) -> float:
    if ":" not in s:
        s = (s[:-2] or "0") + ":" + s[-2:]
    parts = [int(x) for x in s.split(":")]
    v = 0
    for p in parts:
        v = v * 60 + p
    return float(v)


def ocr_frame(img: Path) -> dict:
    """OCR one frame; return main-area lines, url text, timecodes, page class."""
    from PIL import Image
    im = Image.open(img).convert("L")
    W, H = im.size
    big = im.resize((W * 2, H * 2), Image.LANCZOS)
    tmp = img.with_suffix(".ocr.png")
    big.save(tmp)
    lines: dict[tuple, list] = {}
    try:
        out = subprocess.run(["tesseract", str(tmp), "-", "-l", "heb+eng", "--psm", "11", "tsv"],
                             capture_output=True, text=True, timeout=60).stdout
    except Exception:
        out = ""
    for row in out.splitlines()[1:]:
        f = row.split("\t")
        if len(f) < 12 or not f[11].strip():
            continue
        try:
            left, top, hgt, conf = int(f[6]), int(f[7]), int(f[9]), float(f[10])
        except ValueError:
            continue
        if conf < 20:
            continue
        key = (f[2], f[3], f[4])
        lines.setdefault(key, []).append((left, top, hgt, f[11]))
    main_lines = []
    for ws in lines.values():
        # keep tesseract's word order (correct logical order for Hebrew RTL)
        txt = " ".join(w[3] for w in ws).strip()
        y = min(w[1] for w in ws) / (2 * H)
        x0 = min(w[0] for w in ws) / (2 * W)
        hs = sorted(w[2] for w in ws)
        if txt:
            main_lines.append({"y": round(y, 3), "x": round(x0, 3), "h": hs[len(hs) // 2] / 2, "text": txt})
    # URL strip (top of the browser)
    url_txt = ""
    try:
        strip = im.crop((0, int(H * 0.02), int(W * 0.5), int(H * 0.06)))
        strip = strip.resize((strip.width * 3, strip.height * 3), Image.LANCZOS)
        strip.save(tmp)
        url_txt = subprocess.run(["tesseract", str(tmp), "-", "-l", "eng", "--psm", "7"],
                                 capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception:
        pass
    try:
        tmp.unlink()
    except Exception:
        pass
    alltxt = " ".join(l["text"] for l in main_lines)
    tcs = [(_hms(a), _hms(b)) for a, b in TIMECODE_RE.findall(alltxt) if _hms(b) >= _hms(a)]
    low = (url_txt + " " + alltxt).lower()
    watch = "watch" in url_txt.lower() or bool(tcs) or (
        ("youtube" in low or "הרשמה" in alltxt or "subscribe" in low)
        and ("צפיות" in alltxt or " views" in low or "הועלה" in alltxt or "הועלו" in alltxt))
    browse = (not watch) and ("youtube" in low) and (
        "/@" in url_txt or "videos" in url_txt.lower() or alltxt.count("צפיות") >= 2 or alltxt.count("לפני") >= 3)
    vid = None
    if "watch" in url_txt.lower():
        m = VID_RE.search(url_txt.split("watch", 1)[1])
        if m:
            vid = m.group(1)
    return {"lines": main_lines, "url_text": url_txt, "timecodes": tcs,
            "watch_page": watch, "browse_page": browse, "vid_ocr": vid,
            "youtube": "youtube" in low}


# ---------- YouTube lookup (no login, no credits) ----------

def _load_cache(session: Path) -> dict:
    p = session / "source_cache.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"search": {}, "oembed": {}}


def _save_cache(session: Path, c: dict) -> None:
    (session / "source_cache.json").write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")


def oembed(vid: str, cache: dict) -> dict | None:
    if vid in cache["oembed"]:
        return cache["oembed"][vid]
    url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={vid}&format=json"
    try:
        out = subprocess.run(["curl", "-s", "-f", "--max-time", "15", url], capture_output=True, text=True, timeout=20)
        data = json.loads(out.stdout) if out.returncode == 0 and out.stdout.strip() else None
    except Exception:
        data = None
    rec = None
    if data and data.get("title"):
        rec = {"title": data["title"], "author_name": data.get("author_name"), "author_url": data.get("author_url")}
    cache["oembed"][vid] = rec
    return rec


def yt_search(query: str, cache: dict) -> list[dict]:
    q = _norm(query)[:120]
    if q in cache["search"]:
        return cache["search"][q]
    res = []
    try:
        out = subprocess.run(
            ["yt-dlp", "--flat-playlist", "--print", "%(id)s\t%(channel)s\t%(duration)s\t%(title)s",
             f"ytsearch6:{query[:120]}"], capture_output=True, text=True, timeout=90).stdout
        for line in out.splitlines():
            f = line.split("\t")
            if len(f) == 4 and len(f[0]) == 11:
                dur = None
                try:
                    dur = float(f[2])
                except ValueError:
                    pass
                res.append({"id": f[0], "channel": f[1], "duration": dur, "title": f[3]})
    except Exception:
        pass
    cache["search"][q] = res
    return res


def _title_lines(fr: dict, main_only: bool = False) -> list[str]:
    """Title-like lines. main_only: only the biggest-font lines (watch-page
    title / subtitles), never sidebar recommendations or chat."""
    cands = []
    for l in fr.get("lines") or []:
        t = l["text"].strip()
        letters = re.findall(r"[A-Za-z\u0590-\u05FF]", t)
        if len(letters) >= 12 and not TIMECODE_RE.search(t):
            cands.append((float(l.get("h") or 0), t))
    if main_only and cands:
        hmax = max(h for h, _ in cands)
        cands = [(h, t) for h, t in cands if h >= 0.85 * hmax]
    return [t for _, t in cands]


def _titleness(line: str) -> float:
    """Higher = looks like a YouTube title, lower = chat line / UI junk."""
    toks = line.split()
    if not toks:
        return 0.0
    junk = sum(1 for t in toks if re.search(r"\d", t) and re.search(r"[A-Za-z]", t) or "_" in t)
    words = sum(1 for t in toks if re.fullmatch(r"[\u0590-\u05FF\"'״׳]{2,}[!?.,]?|[A-Za-z']{2,}[!?.,]?", t))
    sc = words / len(toks) - 0.5 * junk
    if re.search(r"[!()|]|\s-\s", line):
        sc += 0.3
    try:
        from config import STREAMER_NAME_HE
        if STREAMER_NAME_HE in line:  # chat talking to the streamer
            sc -= 0.6
    except Exception:
        pass
    if len(line) > 90:  # descriptions run long; titles are short
        sc -= 0.3
    n_letters = len(re.findall(r"[A-Za-z\u0590-\u05FF]", line))
    if n_letters < 18:
        sc -= 0.5
    sc += min(n_letters, 50) / 100.0
    return sc


def _context(frames: list[dict], i: int, win: float = 120.0) -> tuple[list[float], str]:
    """Player durations and all OCR text in frames near frame i."""
    t = float(frames[i]["abs_t"])
    durs, texts = [], []
    for fr in frames:
        if abs(float(fr["abs_t"]) - t) <= win:
            durs += [d for _, d in fr.get("timecodes") or []]
            texts.append(" ".join(l["text"] for l in fr.get("lines") or []))
    return durs, _norm(" ".join(texts))


def _verify(r: dict, meta: dict, durs: list[float], ctx: str) -> str | None:
    """A search hit is accepted only with a second, independent on-screen proof."""
    if r.get("duration") and any(abs(d - r["duration"]) <= 3 for d in durs):
        return "title+player_duration+oembed"
    ch = _norm(meta.get("author_name") or r.get("channel") or "")
    if len(ch) >= 4 and ch in ctx:
        return "title+channel_name+oembed"
    return None


def _resolve(session: Path, frames: list[dict], cache: dict) -> dict[str, dict]:
    """Return verified videos {vid: meta} and tag frames with fr['vid']."""
    videos: dict[str, dict] = {v["id"]: v for v in (cache.get("verified") or [])}
    pending: dict[str, dict] = cache.setdefault("pending", {})
    searches = 0
    for i in sorted(range(len(frames)), key=lambda k: -float(frames[k]["abs_t"])):
        fr = frames[i]
        if fr.get("vid"):
            continue
        lines = _title_lines(fr)
        hit = None
        # 1) a verified title visible on screen
        best = (0.0, None)
        for v in videos.values():
            sc = max([max(_sim(l, v["title"]), _sim(l, v.get("alt_title") or "")) for l in lines] or [0.0])
            if sc >= MATCH_MIN and sc > best[0]:
                best = (sc, v["id"])
        hit = best[1]
        # 2) search on-screen titles of a watch page; verify with oEmbed + a 2nd proof
        if not hit and fr.get("watch_page"):
            durs, ctx = _context(frames, i)
            for l in sorted(lines, key=_titleness, reverse=True)[:3]:
                if _titleness(l) < 0.5:
                    continue
                key = _norm(l)[:120]
                if key not in cache["search"]:
                    if searches >= MAX_SEARCHES_PER_RUN:
                        continue
                    searches += 1
                for r in yt_search(l, cache):
                    # search titles can be a localized/A-B variant: compare both
                    meta = oembed(r["id"], cache)
                    if not meta:
                        continue
                    if max(_sim(l, r["title"]), _sim(l, meta["title"])) < MATCH_MIN:
                        continue
                    how = _verify(r, meta, durs, ctx)
                    if how:
                        videos[r["id"]] = {"id": r["id"], **meta, "alt_title": r["title"], "duration": r.get("duration"), "how": how}
                        pending.pop(r["id"], None)
                        hit = r["id"]
                        break
                    pending[r["id"]] = {"id": r["id"], "title": meta["title"], "creator": meta.get("author_name"),
                                        "seen_at": fr["abs_t"], "why": "title match only (sidebar?)"}
                if hit:
                    break
        fr["vid"] = hit or ""
    cache["verified"] = list(videos.values())
    return videos


def scan(session: Path) -> list[dict]:
    """OCR new frames from processed segments. Returns all frame rows."""
    from gambling import extract_frame
    session = Path(session)
    path = session / "source_frames.jsonl"
    rows = _ps().load_jsonl(path)
    have = {round(float(r["abs_t"])) for r in rows}
    fdir = session / "frames" / "source"
    for rec in _ps().load_manifest(session):
        p = Path(rec.get("path") or (session / rec["file"]))
        if not p.is_file():
            continue
        a0, a1 = float(rec["abs_start"]), float(rec["abs_end"])
        t = a0 + 3.0
        while t < a1 - 1:
            if round(t) not in have and not any(abs(round(t) - h) < SAMPLE_STEP / 2 for h in have):
                dest = fdir / f"t{int(t):05d}.jpg"
                if extract_frame(p, t - a0, dest):
                    r = {"abs_t": round(t, 1), "frame": str(dest), **ocr_frame(dest)}
                    _ps().append_jsonl(path, r)
                    rows.append(r)
                    have.add(round(t))
            t += SAMPLE_STEP
    rows.sort(key=lambda r: float(r["abs_t"]))
    return rows


def build_spans(session: Path, processed_end: float) -> list[dict]:
    """Scan, resolve and group frames into reaction spans. Writes sources.json."""
    session = Path(session)
    rows = scan(session)
    cache = _load_cache(session)
    # previously resolved tags are kept in the cache, keyed by abs_t
    tags = cache.setdefault("frame_vid", {})
    for r in rows:
        k = str(round(float(r["abs_t"])))
        if tags.get(k):
            r["vid"] = tags[k]
    videos = _resolve(session, rows, cache)
    for r in rows:
        tags[str(round(float(r["abs_t"])))] = r.get("vid") or ""
    _save_cache(session, cache)

    spans: list[dict] = []
    cur = None
    for r in rows:
        t, vid = float(r["abs_t"]), r.get("vid") or ""
        # fullscreen player with controls: the timecode's total length identifies it
        if not vid and cur and "ended_at" not in cur and cur.get("duration"):
            if any(abs(d - cur["duration"]) <= 3 for _, d in r.get("timecodes") or []):
                vid = cur["id"]
                r["vid_by"] = "player_duration"
        if vid:
            if cur and cur["id"] == vid:
                cur["last_seen"] = t
                cur["_other"] = 0
            else:
                if cur:
                    cur.setdefault("ended_at", t)
                    cur.setdefault("end_reason", f"new_video:{vid}")
                v = videos[vid]
                start = t
                if r.get("timecodes") and v.get("duration"):
                    pos, dur = r["timecodes"][0]
                    if abs(dur - v["duration"]) < 3 and pos < 300:
                        start = t - pos
                cur = {"id": vid, "title": v["title"], "creator": v.get("author_name"),
                       "creator_url": v.get("author_url"), "url": f"https://www.youtube.com/watch?v={vid}",
                       "duration": v.get("duration"), "how": v.get("how"),
                       "first_seen": t, "video_start": round(start, 1), "last_seen": t}
                spans.append(cur)
            for pos, dur in r.get("timecodes") or []:
                if cur.get("duration") and abs(dur - cur["duration"]) <= 3:
                    cur["est_end"] = round(t + (dur - pos), 1)
                    if t - pos < cur["video_start"] and cur["first_seen"] - (t - pos) < 600:
                        cur["video_start"] = round(t - pos, 1)
            continue
        if not cur or "ended_at" in cur:
            continue
        # frame without the video: decide whether the video is over
        est_end = cur.get("est_end") or (cur["video_start"] + cur["duration"] if cur.get("duration") else None)
        if r.get("browse_page"):
            cur["ended_at"], cur["end_reason"] = t, "youtube_browse"
        elif r.get("watch_page") and _title_lines(r) and not any(_sim(l, cur["title"]) >= 0.5 for l in _title_lines(r)):
            # another (unverified) watch page: needs 2 frames in a row
            cur["_other"] = cur.get("_other", 0) + 1
            if cur["_other"] >= 2:
                cur["ended_at"], cur["end_reason"] = t - SAMPLE_STEP, "other_watch_page"
            continue
        elif est_end is not None and t > est_end + 45:
            cur["ended_at"], cur["end_reason"] = max(cur["last_seen"], est_end), "duration_elapsed"
        elif est_end is None and t > cur["last_seen"] + 2 * SAMPLE_STEP + 5:
            cur["ended_at"], cur["end_reason"] = cur["last_seen"] + SAMPLE_STEP, "not_seen_60s"
    for s in spans:
        s.pop("_other", None)
        s["status"] = "ended" if "ended_at" in s else "playing"
        s.setdefault("est_end", (s["video_start"] + s["duration"]) if s.get("duration") else None)
    payload = {"spans": spans, "processed_end": processed_end,
               "updated": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    (session / "sources.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return spans


def transcript_creator_hint(texts: list[str]) -> str | None:
    from config import CREATOR_ALIASES
    joined = " ".join(texts).lower()
    for alias, creator in CREATOR_ALIASES.items():
        if alias.lower() in joined:
            return creator
    return None


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", type=Path, required=True)
    a = ap.parse_args()
    from topics import processed_end
    for s in build_spans(a.session, processed_end(a.session)):
        print(json.dumps(s, ensure_ascii=False))

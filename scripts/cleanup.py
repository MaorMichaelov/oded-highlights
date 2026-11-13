#!/usr/bin/env python3
"""Delete raw segments older than 3 days once clips exist. Log disk use."""
from __future__ import annotations

import json
import shutil
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import LOGS, SAMPLES, STREAMS  # noqa: E402

MAX_AGE_DAYS = 3


def log(msg: str) -> str:
    line = f"{datetime.now().astimezone().isoformat(timespec='seconds')} {msg}"
    print(line, flush=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    with (LOGS / "disk.log").open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    return line


def disk() -> dict:
    u = shutil.disk_usage(str(STREAMS if STREAMS.exists() else "/"))
    return {
        "total_gb": round(u.total / 1e9, 2),
        "used_gb": round(u.used / 1e9, 2),
        "free_gb": round(u.free / 1e9, 2),
        "percent": round(100 * u.used / u.total, 1),
    }


def session_age(session: Path) -> float | None:
    meta = session / "session_meta.json"
    if meta.is_file():
        try:
            ep = float(json.loads(meta.read_text(encoding="utf-8")).get("started_epoch"))
            return time.time() - ep
        except Exception:
            pass
    for name in ("started_at.txt",):
        p = session / name
        if p.is_file():
            try:
                t = p.read_text().strip().replace("Z", "+00:00")
                return time.time() - datetime.fromisoformat(t).timestamp()
            except Exception:
                pass
    return time.time() - session.stat().st_mtime


def has_clips(session: Path) -> bool:
    clips = session / "clips"
    if clips.is_dir() and any(clips.glob("*.mp4")):
        return True
    # samples produced from a vod sim session
    if any(SAMPLES.glob("*.mp4")) and (session / "candidates.jsonl").is_file():
        return True
    return False


def raw_segments(session: Path) -> list[Path]:
    out = []
    for p in session.glob("*.mp4"):
        if p.parent.name == "clips":
            continue
        out.append(p)
    return out


def main() -> int:
    d = disk()
    log(f"disk used={d['used_gb']}GB free={d['free_gb']}GB ({d['percent']}%)")
    if not STREAMS.is_dir():
        return 0
    cutoff = MAX_AGE_DAYS * 86400
    for session in sorted(STREAMS.iterdir()):
        if not session.is_dir():
            continue
        age = session_age(session)
        if age is None or age < cutoff:
            continue
        segs = raw_segments(session)
        if not segs:
            continue
        if not has_clips(session):
            log(f"keep {session.name}: older than {MAX_AGE_DAYS}d but no clips yet ({len(segs)} raw files)")
            continue
        freed = 0
        for p in segs:
            try:
                sz = p.stat().st_size
                p.unlink()
                freed += sz
                log(f"deleted raw {p} ({round(sz/1e6,1)} MB)")
            except Exception as e:
                log(f"failed to delete {p}: {e}")
        log(f"session {session.name}: freed {round(freed/1e6,1)} MB of raw segments")
    d2 = disk()
    log(f"disk after cleanup used={d2['used_gb']}GB free={d2['free_gb']}GB ({d2['percent']}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

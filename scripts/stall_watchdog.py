#!/usr/bin/env python3
"""Recorder stall watchdog (does not replace the recorder).

Scans <root>/streams/* sessions whose record.pid is alive. If the newest
segment mp4 has not grown for STALL_S seconds, sends SIGINT to the hung
ffmpeg child (record.sh / supervisor then reconnect into the same
session), logs the gap to gaps.jsonl and backfills the missing range
from the Kick VOD HLS (session_meta.json vod_source) once it is available.
"""
import json, os, re, subprocess, sys, time
from datetime import datetime
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).parent)
STALL_S = 90
LOG = ROOT / "logs" / "stall_watchdog.log"


def log(msg):
    LOG.parent.mkdir(exist_ok=True)
    with LOG.open("a") as f:
        f.write(f"{datetime.now().isoformat(timespec='seconds')} {msg}\n")


def alive(pid):
    try:
        os.kill(pid, 0); return True
    except Exception:
        return False


def ffmpeg_children(sess: Path):
    out = []
    for p in Path("/proc").iterdir():
        if not p.name.isdigit():
            continue
        try:
            cmd = (p / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="ignore")
        except Exception:
            continue
        if cmd.startswith("ffmpeg") and str(sess) in cmd and "segment" in cmd:
            out.append(int(p.name))
    return out


def wall(name):
    m = re.search(r"(\d{8}T\d{6})", name)
    return datetime.strptime(m.group(1), "%Y%m%dT%H%M%S").astimezone().timestamp() if m else None


def backfill(sess: Path, gap):
    meta = json.loads((sess / "session_meta.json").read_text())
    src = meta.get("vod_source")
    if not src:
        return False
    pl = src.rsplit("/", 1)[0] + f"/{meta.get('quality', '720p60')}/playlist.m3u8"
    start_ep = float(meta["started_epoch"])
    a, b = gap["abs_from"], gap["abs_to"]
    chan = meta.get("channel", "seg")
    tmp = sess / "_source"; tmp.mkdir(exist_ok=True)
    t = a
    while t < b - 5:
        d = min(300, b - t)
        name = datetime.fromtimestamp(start_ep + t).astimezone().strftime("%Y%m%dT%H%M%S")
        part = tmp / f"bf_{name}.mp4"
        r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", str(t), "-i", pl,
                            "-t", str(d), "-c", "copy", "-movflags", "+faststart", str(part)], timeout=900)
        if r.returncode != 0:
            return False
        part.rename(sess / f"{chan}_{name}.mp4")
        log(f"backfilled {sess.name} abs {t:.0f}+{d:.0f}")
        t += d
    return True


def check(sess: Path, state):
    try:
        rp = int((sess / "record.pid").read_text().strip())
    except Exception:
        return
    if not alive(rp):
        return
    segs = sorted([p for p in sess.glob("*.mp4")], key=lambda p: p.stat().st_mtime)
    if not segs:
        return
    newest = segs[-1]
    age = time.time() - newest.stat().st_mtime
    if age < STALL_S:
        return
    # just restarted: give the reconnect time to open a new segment
    if time.time() - state.get(str(sess), 0) < 180:
        return
    kids = ffmpeg_children(sess)
    if not kids:
        return
    # stalled: archive the unfinalized file, kill the hung ffmpeg, note the gap
    meta = json.loads((sess / "session_meta.json").read_text())
    start_ep = float(meta["started_epoch"])
    w = wall(newest.name) or newest.stat().st_mtime
    gap = {"abs_from": max(0.0, w - start_ep), "detected": time.time(), "file": newest.name, "done": False}
    state[str(sess)] = time.time()
    closed = subprocess.run(["ffprobe", "-v", "error", str(newest)], capture_output=True).returncode == 0
    if closed:
        # ffmpeg hangs between segments: the gap starts where the closed file ends
        try:
            d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                      "csv=p=0", str(newest)], capture_output=True, text=True).stdout.strip())
        except ValueError:
            d = 0.0
        gap["abs_from"] = max(0.0, w + d - start_ep)
    for k in kids:
        os.kill(k, 2)
    log(f"STALL {sess.name}: {newest.name} idle {age:.0f}s; SIGINT ffmpeg {kids}")
    time.sleep(10)
    if not closed:
        (sess / "_source").mkdir(exist_ok=True)
        newest.rename(sess / "_source" / (newest.stem + ".broken.mp4"))
    with (sess / "gaps.jsonl").open("a") as f:
        f.write(json.dumps(gap) + "\n")


def finish_gaps(sess: Path):
    gp = sess / "gaps.jsonl"
    if not gp.is_file():
        return
    gaps = [json.loads(l) for l in gp.read_text().splitlines() if l.strip()]
    changed = False
    meta = json.loads((sess / "session_meta.json").read_text())
    start_ep = float(meta["started_epoch"])
    for g in gaps:
        if g.get("done"):
            continue
        # gap ends where the first segment written after detection starts
        later = [p for p in sess.glob("*.mp4") if (wall(p.name) or 0) > g["detected"] - 60]
        if not later:
            continue
        g["abs_to"] = min(wall(p.name) for p in later) - start_ep
        if time.time() - g["detected"] < 60:
            continue
        try:
            g["done"] = backfill(sess, g)
        except Exception as e:
            log(f"backfill failed {e}")
        changed = True
    if changed:
        gp.write_text("".join(json.dumps(g) + "\n" for g in gaps))


def main():
    log(f"start root={ROOT}")
    state = {}
    while True:
        for sess in (ROOT / "streams").glob("*"):
            if sess.is_dir() and (sess / "session_meta.json").is_file():
                try:
                    check(sess, state); finish_gaps(sess)
                except Exception as e:
                    log(f"err {sess.name}: {e}")
        time.sleep(20)


if __name__ == "__main__":
    main()

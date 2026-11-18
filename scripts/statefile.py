#!/usr/bin/env python3
"""Crash-safe state files: atomic writes, tolerant reads, locked appends.

Why (audit 18 Nov): the loops wrote state with `json.dump(x, open(p, "w"))`. A runner killed (timeout, OOM, cancel) in the middle left a truncated file; the next read raised
or - worse, in live_watch.load() - silently returned the default, which restarted the whole transcription from segment 0 and duplicated hours of transcript.
  write_json(path, obj)        write to a temp file in the same folder, fsync, os.replace (atomic on POSIX): readers see the old or the new file, never half of one
  read_json(path, default)     a missing file -> default; a corrupt file is moved to <path>.corrupt-<ts> (kept for inspection) and default is returned, loudly
  append_line(path, line)      one complete line appended under an flock (concurrent producers on one runner never interleave)
  append_jsonl_unique(path, obj, key)   append only if no existing line has the same obj[key]  (idempotent: re-running a step cannot duplicate its record)
  truncate_jsonl_from(path, field, value)   drop rows whose obj[field] >= value (a re-ingested window replaces its earlier, partial output instead of duplicating it)
"""
import json, os, tempfile, time
try: import fcntl
except Exception: fcntl = None


def write_text(path, text):
    path = str(path); d = os.path.dirname(os.path.abspath(path)); os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="." + os.path.basename(path) + ".", suffix=".tmp", dir=d)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try: os.unlink(tmp)
        except OSError: pass
        raise


def write_json(path, obj, indent=1):
    write_text(path, json.dumps(obj, ensure_ascii=False, indent=indent))


def read_json(path, default=None, quarantine=True):
    path = str(path)
    if not os.path.exists(path): return default
    try:
        with open(path, encoding="utf-8") as f: return json.load(f)
    except Exception as e:
        print(f"STATE CORRUPT: {path}: {type(e).__name__}", flush=True)
        if quarantine:
            try: os.replace(path, f"{path}.corrupt-{int(time.time())}")
            except OSError: pass
        return default


class _Lock:
    def __init__(self, path): self.p = str(path) + ".lock"; self.f = None
    def __enter__(self):
        os.makedirs(os.path.dirname(os.path.abspath(self.p)), exist_ok=True); self.f = open(self.p, "a")
        if fcntl: fcntl.flock(self.f, fcntl.LOCK_EX)
        return self
    def __exit__(self, *a):
        if fcntl and self.f: fcntl.flock(self.f, fcntl.LOCK_UN)
        if self.f: self.f.close()


def lock(path): return _Lock(path)


def append_line(path, line):
    if not line.endswith("\n"): line += "\n"
    with lock(path):
        with open(path, "a", encoding="utf-8") as f: f.write(line); f.flush(); os.fsync(f.fileno())


def read_jsonl(path):
    out = []
    if not os.path.exists(path): return out
    with open(path, encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln: continue
            try: out.append(json.loads(ln))
            except Exception: pass   # a torn last line (killed mid-write) is skipped, not fatal
    return out


def append_jsonl_unique(path, obj, key):
    with lock(path):
        if any(r.get(key) == obj.get(key) for r in read_jsonl(path)): return False
        with open(path, "a", encoding="utf-8") as f: f.write(json.dumps(obj, ensure_ascii=False) + "\n"); f.flush(); os.fsync(f.fileno())
        return True


def truncate_jsonl_from(path, field, value):
    """remove rows with row[field] >= value; returns how many were removed (0 = file untouched unless it had a torn last line)."""
    if not os.path.exists(path): return 0
    with lock(path):
        rows = read_jsonl(path); keep = [r for r in rows if not (isinstance(r.get(field), (int, float)) and r[field] >= value)]
        with open(path, encoding="utf-8") as f: txt = f.read()
        if len(keep) == len(rows) and (not txt or txt.endswith("\n")): return 0
        write_text(path, "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in keep)); return len(rows) - len(keep)

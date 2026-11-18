#!/usr/bin/env python3
"""ONE de-duplication guard for every producer (pick station, vod_long, vod_shorts, live_shorts, customer jobs): the same stretch of the same VOD must become the same kind of video ONCE.

Key = (vod, start, end, kind). Two items are duplicates when they are for the same vod, the same kind ("long" | "short"), the same target YouTube channel (yt: main|en|<customer>, when both
known) and their time ranges overlap by >= thr of the SHORTER one (default 0.8: re-picks drift by a few seconds after a state reset or a re-segmentation; 0.8 keeps genuinely different parts).
Sources of truth, merged:
  1. the ledger state/dedup.jsonl (append-only, one JSON per line, merge=union in .gitattributes so concurrent runners' pushes both survive)
  2. ranges already on disk: state/**/clips/*/cuts.json (long clips of the pick station) and state/<slug>/{long,shorts}/*.json (vod_long / vod_shorts metas)
claim() = check + append to the ledger under a lock. Cross-runner races (two machines claiming within the same minute before either pushes) are still possible: the YouTube-side title
check in yt_upload.py is the last line of defence.
usage: dedup.py check --vod V --start S --end E [--kind long|short] [--yt main]   |   dedup.py backfill   |   dedup.py list
"""
import argparse, glob, json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, HERE)
import statefile as SF
LEDGER = os.environ.get("DEDUP_LEDGER") or os.path.join(ROOT, "state", "dedup.jsonl")
THR = 0.8


def overlap(a0, a1, b0, b1):
    o = min(a1, b1) - max(a0, b0); return max(0.0, o) / max(1e-6, min(a1 - a0, b1 - b0))


def key(vod, start, end, kind="long"): return f"{vod}:{int(round(start))}:{int(round(end))}:{kind}"


def _disk_ranges(vod, root=None):
    """ranges already produced on disk for this VOD (all state dirs)"""
    root = root or ROOT; out = []
    for f in glob.glob(os.path.join(root, "state", "**", "clips", "*", "cuts.json"), recursive=True):
        c = SF.read_json(f, None, quarantine=False)
        if not isinstance(c, dict) or str(c.get("vod")) != str(vod): continue
        ks = [(x, y) for p in c.get("pieces", []) for x, y in p.get("keep", [])]
        if ks: out.append({"kind": "long", "start": min(x for x, _ in ks), "end": max(y for _, y in ks), "src": os.path.relpath(f, root), "yt": None})
    for kind, d in (("short", "shorts"), ("long", "long")):
        for f in glob.glob(os.path.join(root, "state", "*", d, "*.json")):
            if f.endswith(("uploaded.json", ".words.json")): continue
            s = (SF.read_json(f, {}, quarantine=False) or {}).get("source") or {}
            if str(s.get("vod")) == str(vod) and s.get("start_s") is not None and s.get("end_s") is not None: out.append({"kind": kind, "start": float(s["start_s"]), "end": float(s["end_s"]), "src": os.path.relpath(f, root), "yt": None})
    return out


def find(vod, start, end, kind="long", yt=None, thr=THR, ledger=None, disk=True, root=None):
    """first existing entry that duplicates (vod,start,end,kind), else None"""
    if end <= start: return None
    items = [r for r in SF.read_jsonl(ledger or LEDGER) if str(r.get("vod")) == str(vod)] + (_disk_ranges(vod, root) if disk else [])
    for r in items:
        if r.get("kind", "long") != kind: continue
        if yt and r.get("yt") and r["yt"] != yt: continue
        try:
            if overlap(start, end, float(r["start"]), float(r["end"])) >= thr: return r
        except Exception: continue
    return None


def claim(vod, start, end, kind="long", yt=None, producer="", clip_id="", thr=THR, ledger=None, disk=True, root=None):
    """(True, entry) when the range was free and is now recorded, (False, existing) when it is a duplicate. Idempotent for the same clip_id."""
    path = ledger or LEDGER
    with SF.lock(path):
        ex = find(vod, start, end, kind, yt, thr, path, disk, root)
        if ex is not None:
            return (True, ex) if (clip_id and ex.get("clip_id") == clip_id) else (False, ex)
        ent = {"key": key(vod, start, end, kind), "vod": str(vod), "start": round(float(start), 2), "end": round(float(end), 2), "kind": kind, "yt": yt, "producer": producer, "clip_id": clip_id, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        with open(path, "a", encoding="utf-8") as f: f.write(json.dumps(ent, ensure_ascii=False) + "\n"); f.flush(); os.fsync(f.fileno())
        return True, ent


def backfill(root=None, ledger=None):
    """record every long range already on disk (first run, or after a ledger loss). Returns the number of entries added."""
    root = root or ROOT; path = ledger or LEDGER; n = 0; seen = {r.get("key") for r in SF.read_jsonl(path)}; vods = set()
    for f in glob.glob(os.path.join(root, "state", "**", "clips", "*", "cuts.json"), recursive=True):
        c = SF.read_json(f, None, quarantine=False)
        if isinstance(c, dict) and c.get("vod"): vods.add(str(c["vod"]))
    for v in sorted(vods):
        for r in _disk_ranges(v, root):
            k = key(v, r["start"], r["end"], r["kind"])
            if k in seen: continue
            seen.add(k); n += 1
            SF.append_line(path, json.dumps({"key": k, "vod": v, "start": round(r["start"], 2), "end": round(r["end"], 2), "kind": r["kind"], "yt": None, "producer": "backfill", "clip_id": r["src"], "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, ensure_ascii=False))
    return n


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["check", "backfill", "list"]); ap.add_argument("--vod"); ap.add_argument("--start", type=float); ap.add_argument("--end", type=float); ap.add_argument("--kind", default="long"); ap.add_argument("--yt"); a = ap.parse_args(argv)
    if a.cmd == "backfill": print("added", backfill()); return 0
    if a.cmd == "list":
        for r in SF.read_jsonl(LEDGER): print(r.get("key"), r.get("producer"), r.get("clip_id"))
        return 0
    ex = find(a.vod, a.start, a.end, a.kind, a.yt); print(json.dumps(ex, ensure_ascii=False) if ex else "free"); return 3 if ex else 0


if __name__ == "__main__": sys.exit(main())

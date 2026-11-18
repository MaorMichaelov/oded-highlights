#!/usr/bin/env python3
"""INGEST WATCHER: turns the recordings of a restream server (MediaMTX, see deploy/ingest/ and docs/INGEST.md) into render jobs. Free software only, runs on the owner's PC or any cheap VPS.

What it does
  1. serves the publish-auth hook for MediaMTX on 127.0.0.1:8899/auth  -> only a customer's secret restream key (ik_<32 hex>) may publish; anybody else is refused, so nobody can fill the disk.
  2. scans $RECORD_DIR/live/<key>/*.ts (5-minute MPEG-TS segments written by MediaMTX). A stream is OVER when its newest segment has not changed for --end-after-s (default 600 s: a dropped connection that
     comes back within 10 minutes stays one stream). The segments are moved to $INGEST_DIR/s<hash>-<start>/ (a flat folder name that does not contain the key) and ONE job is created: source.ref = ingest:<folder>.
  3. optional live clipping (--live-every-min N): while the stream is still running, every N minutes of CLOSED segments are hard-linked into their own folder and become a job (outputs: Shorts only, kind live),
     so drafts arrive while the streamer is still live. At the end only the not yet handed-over rest becomes the final job (no segment is ever processed twice, no credit is charged twice).
  4. creates the job through the studio API (POST /studio/worker/ingest, x-worker-key) or, without network, as a JSON file in --spool DIR for `render_worker.py --spool DIR`.
Streams shorter than --min-stream-s (default 120) are ignored (test streams). Ingest folders older than --keep-days (default 3) are deleted. Crash-safe: all state is in $INGEST_DIR/.watcher_state.json (atomic writes);
a job that could not be created (API down) is retried on the next scan, idempotent through the folder name.

usage: ingest_watcher.py --record-dir recordings/live --ingest-dir /data/ingest [--api URL | --spool DIR --keys-file keys.json] [--live-every-min 15] [--once]
env: STUDIO_URL, STUDIO_WORKER_KEY (API mode; the worker key is never logged)
keys-file (spool mode, no API): {"ik_<32 hex>": {"org":"o_1","channel":"c_1","shorts":5,"long":true}}"""
import argparse, hashlib, json, os, re, shutil, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import worker_sources as WS
from render_worker import Log, StudioApi, ApiError, AuthError

KEY_RX = re.compile(r"^ik_[a-f0-9]{32}$")
SEG_EXT = (".ts",)


def key_tag(key): return hashlib.sha256(key.encode()).hexdigest()[:10]


class Keys:
    """key -> {org, channel, ...} from the studio API (op check, cached 60 s) or a local JSON file"""
    def __init__(self, api=None, path=None, clock=time.time): self.api, self.path, self.clock, self.cache = api, path, clock, {}
    def lookup(self, key):
        if not KEY_RX.match(key or ""): return None
        c = self.cache.get(key)
        if c and self.clock() - c[0] < 60: return c[1]
        ent = None
        try:
            if self.path:
                ent = (json.load(open(self.path, encoding="utf-8")) or {}).get(key)
            elif self.api:
                r = self.api._call("/studio/worker/ingest", {"op": "check", "key": key}); ent = r if r.get("ok") else None
        except AuthError: raise
        except ApiError as e:
            if e.status != 404: return (c or (0, None))[1]   # API trouble: keep the last answer instead of kicking a live streamer
        except Exception: return (c or (0, None))[1]
        self.cache[key] = (self.clock(), ent); return ent


def auth_handler(keys, log):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_POST(self):
            try: b = json.loads(self.rfile.read(min(int(self.headers.get("content-length") or 0), 10000)) or b"{}")
            except Exception: b = {}
            act, path, ip = b.get("action"), str(b.get("path") or ""), str(b.get("ip") or "")
            ok = False
            if act == "publish":
                m = re.fullmatch(r"live/(ik_[a-f0-9]{32})", path); ok = bool(m and keys.lookup(m.group(1)))
                log("auth_publish", "info" if ok else "warn", ok=ok, tag=key_tag(m.group(1)) if m else "-", ip=ip, protocol=b.get("protocol"))
            elif act in ("read", "playback"): ok = ip in ("127.0.0.1", "::1")
            self.send_response(200 if ok else 401); self.end_headers()
    return H


def seg_list(d):
    try: names = sorted(n for n in os.listdir(d) if n.lower().endswith(SEG_EXT))
    except FileNotFoundError: return []
    out = []
    for n in names:
        p = os.path.join(d, n)
        try: st = os.stat(p)
        except OSError: continue
        if st.st_size > 0: out.append((n, p, st.st_mtime, st.st_size))
    return out


class Watcher:
    def __init__(self, record_dir, ingest_dir, keys, submit, log, end_after_s=600, live_every_min=0, min_stream_s=120, keep_days=3, clock=time.time, probe=None):
        self.rec, self.ing, self.keys, self.submit, self.log = record_dir, ingest_dir, keys, submit, log
        self.end_after, self.live_every, self.min_stream, self.keep_days, self.clock = end_after_s, live_every_min, min_stream_s, keep_days, clock
        self.probe = probe or (lambda p: WS.probe(p)["duration_s"]); os.makedirs(ingest_dir, exist_ok=True)
        self.sp = os.path.join(ingest_dir, ".watcher_state.json"); self.state = self._load()
    def _load(self):
        try: return json.load(open(self.sp))
        except Exception: return {"handed": {}, "pending": []}
    def _save(self):
        tmp = self.sp + ".tmp"; json.dump(self.state, open(tmp, "w")); os.replace(tmp, self.sp)

    def dur(self, segs):
        t = 0.0
        for n, p, mt, sz in segs:
            try: t += self.probe(p)
            except Exception: t += 300.0   # unreadable segment: assume the configured length
        return t

    def _enqueue(self, key, name, minutes, live):
        self.state["pending"].append({"key": key, "name": name, "minutes": minutes, "live": live, "tries": 0}); self._save()

    def scan(self):
        """one pass; returns the list of job refs created now"""
        made = []
        for key in sorted(os.listdir(self.rec)) if os.path.isdir(self.rec) else []:
            if not KEY_RX.match(key): continue
            segs = seg_list(os.path.join(self.rec, key)); handed = set(self.state["handed"].get(key, []))
            if not segs: continue
            newest = max(s[2] for s in segs); live = self.clock() - newest < self.end_after; fresh = [s for s in segs if s[0] not in handed]
            tag = key_tag(key)
            if live:
                if not self.live_every: continue
                closed = [s for s in sorted(segs, key=lambda x: x[0])[:-1] if s[0] not in handed]   # the newest segment is still being written
                if closed and self.dur(closed) >= self.live_every * 60:
                    name = "s%s-%s-live" % (tag, closed[0][0][:15].replace(".ts", "")); d = os.path.join(self.ing, name); os.makedirs(d, exist_ok=True)
                    for n, p, mt, sz in closed:
                        try: os.link(p, os.path.join(d, n))
                        except OSError: shutil.copy2(p, os.path.join(d, n))
                    self.state["handed"].setdefault(key, []).extend(s[0] for s in closed); self._enqueue(key, name, max(1, int(self.dur(closed) / 60)), True)
                continue
            # the stream is over: hand over what is left, forget the key's state
            if fresh and self.dur(fresh) >= self.min_stream:
                name = "s%s-%s" % (tag, fresh[0][0][:15].replace(".ts", "")); d = os.path.join(self.ing, name); os.makedirs(d, exist_ok=True)
                for n, p, mt, sz in fresh: shutil.move(p, os.path.join(d, n))
                self._enqueue(key, name, max(1, int(self.dur(seg_list(d)) / 60)), False)
            elif fresh: self.log("stream_too_short", "info", tag=tag, segments=len(fresh))
            for n, p, mt, sz in seg_list(os.path.join(self.rec, key)):
                try: os.remove(p)
                except OSError: pass
            self.state["handed"].pop(key, None); self._save()
        made += self.flush_pending(); self.prune(); self._save(); return made

    def flush_pending(self):
        made, keep = [], []
        for p in self.state["pending"]:
            try:
                ref = self.submit(p["key"], "ingest:" + p["name"], p["minutes"], p["live"], p["name"]); made.append(ref); self.log("job_created", name=p["name"], minutes=p["minutes"], live=p["live"])
            except AuthError: self.log("api_auth_rejected", "error"); keep.append(p)
            except ApiError as e:
                p["tries"] += 1
                if e.status and 400 <= e.status < 500 and e.status != 429: self.log("job_rejected", "error", name=p["name"], status=e.status, body=str(e.body)[:100])   # e.g. 402 no credits, 404 key revoked: do not retry forever
                elif p["tries"] < 50: keep.append(p); self.log("job_retry_later", "warn", name=p["name"], error=str(e)[:100])
            except Exception as e: p["tries"] += 1; keep.append(p); self.log("job_retry_later", "warn", name=p["name"], error=str(e)[:100])
        self.state["pending"] = keep; return made

    def prune(self):
        for n in os.listdir(self.ing):
            p = os.path.join(self.ing, n)
            if n.startswith("s") and os.path.isdir(p) and self.clock() - os.path.getmtime(p) > self.keep_days * 86400 and n not in [x["name"] for x in self.state["pending"]]:
                shutil.rmtree(p, ignore_errors=True); self.log("pruned", name=n)


def api_submit(api):
    def submit(key, ref, minutes, live, idem):
        r = api._call("/studio/worker/ingest", {"op": "job", "key": key, "ref": ref, "duration_min": minutes, "live": live, "idem": idem, "shorts": 3 if live else 5, "long": not live})
        return r.get("job_id") or ref
    return submit


def spool_submit(spool, keys):
    os.makedirs(spool, exist_ok=True)
    def submit(key, ref, minutes, live, idem):
        ent = keys.lookup(key)
        if not ent: raise ApiError(404, "unknown key")
        jid = "j_" + hashlib.sha256((key + idem).encode()).hexdigest()[:12]; p = os.path.join(spool, jid + ".json")
        if os.path.exists(p) or any(os.path.exists(os.path.join(spool, jid + e)) for e in (".running", ".done")): return jid
        job = {"id": jid, "org": ent.get("org", "o_local"), "channel": ent.get("channel", "c_local"), "kind": "edit", "source": {"type": "live" if live else "url", "ref": ref, "duration_min": minutes}, "style_id": ent.get("style_id", "signature"),
               "outputs": {"shorts": int(ent.get("shorts", 3 if live else 5)), "long": bool(ent.get("long", not live))}, "hints": ent.get("hints", {})}
        json.dump(job, open(p + ".tmp", "w")); os.replace(p + ".tmp", p); return jid
    return submit


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--record-dir", default=os.environ.get("RECORD_DIR", "recordings/live")); ap.add_argument("--ingest-dir", default=os.environ.get("INGEST_DIR", "ingest"))
    ap.add_argument("--api"); ap.add_argument("--spool"); ap.add_argument("--keys-file"); ap.add_argument("--end-after-s", type=int, default=600); ap.add_argument("--live-every-min", type=int, default=0)
    ap.add_argument("--min-stream-s", type=int, default=120); ap.add_argument("--keep-days", type=int, default=3); ap.add_argument("--auth-port", type=int, default=8899); ap.add_argument("--no-auth", action="store_true")
    ap.add_argument("--interval-s", type=int, default=30); ap.add_argument("--once", action="store_true"); a = ap.parse_args(argv)
    wk = os.environ.get("STUDIO_WORKER_KEY", ""); log = Log(os.environ.get("WORKER_LOG", "json"), [wk], name="ingest_watcher")
    if a.spool:
        if not a.keys_file: ap.error("--spool needs --keys-file");
        keys = Keys(path=a.keys_file); submit = spool_submit(a.spool, keys)
    else:
        base = a.api or os.environ.get("STUDIO_URL", "")
        if not base or not wk: print("STUDIO_URL and STUDIO_WORKER_KEY are required (or --spool DIR --keys-file F)", file=sys.stderr); return 2
        api = StudioApi(base, wk); keys = Keys(api=api); submit = api_submit(api)
    w = Watcher(a.record_dir, a.ingest_dir, keys, submit, log, a.end_after_s, a.live_every_min, a.min_stream_s, a.keep_days)
    if not a.no_auth and not a.once:
        srv = ThreadingHTTPServer(("127.0.0.1", a.auth_port), auth_handler(keys, log)); threading.Thread(target=srv.serve_forever, daemon=True).start(); log("auth_listening", port=a.auth_port)
    log("watcher_start", record=a.record_dir, ingest=a.ingest_dir, live_every_min=a.live_every_min)
    while True:
        try: w.scan()
        except Exception as e: log("scan_failed", "error", error="%s: %s" % (type(e).__name__, str(e)[:150]))
        if a.once: return 0
        time.sleep(a.interval_s)


if __name__ == "__main__": sys.exit(main())

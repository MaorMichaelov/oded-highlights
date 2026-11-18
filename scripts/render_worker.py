#!/usr/bin/env python3
"""RENDER WORKER: long-running daemon for the customer studio. claim a job -> run the pipeline (scripts/job_runner.py, one subprocess per job) -> report progress -> post the finished DRAFTS + QA grade.
It NEVER uploads. Drafts stay on this machine under $WORKER_OUT_DIR/<job>/ with a manifest.json; uploading to the customer's YouTube is a separate step (scripts/yt_upload_customer.py, private by default, honours state/UPLOAD_HOLD).

usage:  render_worker.py                    run forever against the studio API (env STUDIO_URL + STUDIO_WORKER_KEY)
        render_worker.py --once             drain mode (GitHub Actions / cron): claim queued jobs, finish them, exit as soon as the queue is empty (never waits for new jobs)
        render_worker.py --max-minutes N    time budget: stop claiming (and do not start a job with < WORKER_MIN_CLAIM_MIN=5 minutes left); jobs still running at N minutes are killed and reported failed (credit refunded). Works with or without --once
        render_worker.py --spool DIR        no network: jobs are *.json files in DIR (what ingest_watcher.py --spool writes); reports go to DIR/<id>.report.jsonl
        render_worker.py --demo             offline end-to-end demo: makes a synthetic video, runs a job on it, prints the drafts (no network, no keys, no models)
env (all optional except the first two for API mode):
  STUDIO_URL, STUDIO_WORKER_KEY            studio base URL and the shared worker secret (never logged, never passed to the job subprocess)
  WORKER_CONCURRENCY=1                     parallel jobs (about 4 vCPU each)       WORKER_POLL_S=10          idle poll interval
  WORKER_JOB_TIMEOUT_S=14400               hard limit per attempt                  WORKER_STALL_S=1800       kill a job that prints nothing for this long
  WORKER_RETRIES=1                         extra attempts after a crash/timeout (never after a customer-fixable error)
  WORKER_WORK_DIR=./work  WORKER_OUT_DIR=./out   scratch and finished drafts     WORKER_KEEP_FAILED_H=24  WORKER_KEEP_DRAFTS_D=14  WORKER_MIN_FREE_GB=5
  WORKER_GRACE_S=600                       on SIGTERM: stop claiming, wait this long for running jobs, then kill them and report them failed (the credit is refunded by the API)
  STUDIO_PREVIEW_PUBLISH=github-release    after a job: publish 720p previews as GitHub release assets (scripts/preview_publish.py; needs GITHUB_TOKEN, GITHUB_REPOSITORY, WORKER_PREVIEW_ORGS) and send them as draft.preview_url
  WORKER_LOG=json|text                     structured logs (one JSON object per line) are the default
  plus everything job_runner.py reads (UPLOAD_DIR, INGEST_DIR, WORKER_MEDIA_ROOTS, WORKER_NO_CLOUD, GROQ_API_KEY, GEMINI_API_KEY, CUSTOMER_PROFILES_DIR ...)
Exit codes: 0 clean stop | 2 usage/config | 5 the API rejected the worker key."""
import argparse, json, os, random, re, shutil, signal, subprocess, sys, tempfile, threading, time, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
RUNNER = os.path.join(HERE, "job_runner.py")
SECRET_RX = re.compile(r"(AIza[0-9A-Za-z_-]{20,}|gsk_[0-9A-Za-z]{20,}|ya29\.[0-9A-Za-z_-]{20,}|Bearer\s+[0-9A-Za-z._~+/=-]{16,}|x-worker-key[\"':= ]+[0-9A-Za-z._-]{6,}|wk_[0-9A-Za-z]{6,})", re.I)


def redact(s, secrets=()):
    s = str(s)
    for x in secrets:
        if x and len(x) >= 6: s = s.replace(x, "***")
    return SECRET_RX.sub("***", s)


class Log:
    """structured logs: one JSON object per line on stdout (WORKER_LOG=text for humans). Secrets are redacted."""
    def __init__(self, fmt="json", secrets=(), stream=None, name="render_worker"): self.fmt, self.secrets, self.stream, self.name, self.lock = fmt, list(secrets), stream or sys.stdout, name, threading.Lock()
    def __call__(self, event, level="info", **kw):
        rec = {"t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "level": level, "src": self.name, "event": event}
        rec.update({k: (redact(v, self.secrets) if isinstance(v, str) else v) for k, v in kw.items()})
        line = json.dumps(rec, ensure_ascii=False) if self.fmt == "json" else "%s %-5s %s %s" % (rec["t"], level, event, " ".join("%s=%s" % (k, v) for k, v in kw.items()))
        with self.lock: print(line, file=self.stream, flush=True)


# ---------------------------------------------------------------- API clients
class ApiError(Exception):
    def __init__(self, status, body=None): super().__init__("API %s %s" % (status, str(body)[:120])); self.status, self.body = status, body
class AuthError(ApiError): pass


def urllib_transport(method, url, headers, body, timeout):
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r: return r.status, r.read()
    except urllib.error.HTTPError as e: return e.code, e.read()


class StudioApi:
    """worker side of app/studio.js: POST /studio/worker/claim, POST /studio/worker/jobs/:id. transport(method,url,headers,bytes,timeout)->(status, bytes) is injectable (tests)."""
    def __init__(self, base, key, transport=None, retries=3, sleep=time.sleep, timeout=30):
        self.base, self.key, self.t, self.retries, self.sleep, self.timeout = base.rstrip("/"), key, transport or urllib_transport, retries, sleep, timeout
    def _call(self, path, body):
        data = json.dumps(body or {}).encode(); last = None
        for i in range(self.retries):
            try: st, raw = self.t("POST", self.base + path, {"content-type": "application/json", "x-worker-key": self.key, "user-agent": "render-worker/1"}, data, self.timeout)
            except Exception as e: last = e; self.sleep(min(30, 2 ** i + random.random())); continue
            try: j = json.loads(raw or b"{}")
            except Exception: j = {}
            if st == 401: raise AuthError(401, j)
            if st >= 500 or st == 429: last = ApiError(st, j); self.sleep(min(30, 2 ** i + random.random())); continue
            if st >= 400: raise ApiError(st, j)
            return j
        raise last if isinstance(last, ApiError) else ApiError(0, "network: %s" % type(last).__name__)
    def claim(self): return (self._call("/studio/worker/claim", {}) or {}).get("job")
    def post(self, job_id, **body): return self._call("/studio/worker/jobs/" + job_id, body)


class SpoolApi:
    """no-network job source: DIR/<id>.json = a job (same shape as the claim response). claim() renames it to .running atomically; post() appends to DIR/<id>.report.jsonl; drafts end in DIR/<id>.result.json."""
    def __init__(self, d): self.d = d; os.makedirs(d, exist_ok=True)
    def claim(self):
        for n in sorted(os.listdir(self.d)):
            if n.endswith(".json") and not n.endswith((".result.json", ".report.json")):
                p = os.path.join(self.d, n); q = p[:-5] + ".running"
                try: os.rename(p, q)
                except OSError: continue
                try: job = json.load(open(q, encoding="utf-8"))
                except Exception: os.rename(q, p[:-5] + ".bad"); continue
                job.setdefault("id", n[:-5]); return job
        return None
    def post(self, job_id, **body):
        with open(os.path.join(self.d, job_id + ".report.jsonl"), "a", encoding="utf-8") as f: f.write(json.dumps({"t": time.time(), **body}, ensure_ascii=False) + "\n")
        if body.get("status") in ("draft_ready", "failed"):
            json.dump(body, open(os.path.join(self.d, job_id + ".result.json"), "w"), ensure_ascii=False, indent=1)
            try: os.rename(os.path.join(self.d, job_id + ".running"), os.path.join(self.d, job_id + ".done"))
            except OSError: pass
        return {"ok": True}


# ---------------------------------------------------------------- running one attempt
class Outcome:
    def __init__(self, code, result=None, error=None, killed=None): self.code, self.result, self.error, self.killed = code, result, error, killed


def run_subprocess(job, workdir, cfg, on_progress, log, stop_event, secrets=()):
    """default runner: job_runner.py as a child process in its own process group (so ffmpeg children die with it). Enforces the hard timeout and the no-output stall timeout."""
    os.makedirs(workdir, exist_ok=True); jp = os.path.join(workdir, "job.json")
    with open(jp, "w") as f: json.dump(job, f)
    env = {k: v for k, v in os.environ.items() if k not in ("STUDIO_WORKER_KEY", "GITHUB_TOKEN", "GH_TOKEN", "ACTIONS_RUNTIME_TOKEN", "ACTIONS_ID_TOKEN_REQUEST_TOKEN")}   # the job subprocess handles untrusted media: it never sees the worker key or the repo token; env.update(cfg.get("child_env") or {})
    cmd = [sys.executable, "-u", RUNNER, "--job", jp, "--workdir", workdir] + (["--demo"] if cfg.get("demo") else [])
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env, start_new_session=True, cwd=ROOT)
    state = {"killed": None, "last": time.time()}
    def kill(why):
        state["killed"] = why
        try: os.killpg(p.pid, signal.SIGTERM)
        except OSError: pass
        threading.Timer(10, lambda: (os.killpg(p.pid, signal.SIGKILL) if p.poll() is None else None)).start()
    def watchdog():
        t0 = time.time()
        while p.poll() is None:
            if time.time() - t0 > cfg["job_timeout_s"]: kill("timeout"); return
            if time.time() - state["last"] > cfg["stall_s"]: kill("stalled"); return
            if stop_event.is_set() and time.time() > cfg.get("hard_stop_at", 1e18): kill("shutdown"); return
            time.sleep(1)
    threading.Thread(target=watchdog, daemon=True).start()
    err = None; res_path = None
    for line in p.stdout:
        state["last"] = time.time(); line = line.rstrip("\n")
        if line.startswith("PROGRESS "):
            try: on_progress(json.loads(line[9:]))
            except Exception: pass
        elif line.startswith("RESULT "): res_path = line[7:].strip()
        elif line.startswith("ERROR "):
            try: err = json.loads(line[6:])
            except Exception: err = {"code": "crash", "message": line[6:100]}
        else: log("job_output", job=job.get("id"), line=redact(line, secrets)[:300], level="debug")
    code = p.wait(); result = None
    if code == 0 and res_path:
        try:
            with open(res_path, encoding="utf-8") as f: result = json.load(f)
        except Exception as e: code, err = 1, {"code": "bad_result", "message": str(e)[:100]}
    return Outcome(code, result, err, state["killed"])


# ---------------------------------------------------------------- the worker
def default_cfg(env=None):
    e = os.environ if env is None else env; i = lambda k, d: int(float(e.get(k, d) or d))
    return {"concurrency": max(1, i("WORKER_CONCURRENCY", 1)), "poll_s": max(1, i("WORKER_POLL_S", 10)), "job_timeout_s": i("WORKER_JOB_TIMEOUT_S", 14400), "stall_s": i("WORKER_STALL_S", 1800), "retries": max(0, i("WORKER_RETRIES", 1)),
            "work_dir": os.path.abspath(e.get("WORKER_WORK_DIR", "./work")), "out_dir": os.path.abspath(e.get("WORKER_OUT_DIR", "./out")), "keep_failed_h": i("WORKER_KEEP_FAILED_H", 24), "keep_drafts_d": i("WORKER_KEEP_DRAFTS_D", 14),
            "min_free_gb": float(e.get("WORKER_MIN_FREE_GB", "5") or 5), "grace_s": i("WORKER_GRACE_S", 600), "progress_min_interval_s": 2.0, "backoff_s": 20, "min_claim_s": int(float(e.get("WORKER_MIN_CLAIM_MIN", "5") or 5) * 60)}


FRIENDLY = {"no_recording": "No recording of your stream was found yet.", "no_file": "We could not find that file.", "bad_url": "That link cannot be used. Paste a direct video link or upload the file.",
            "host_not_allowed": "That site cannot be downloaded. Restream to our ingest or upload the file.", "download_failed": "We could not download that link.", "too_short": "The video is too short to clip.",
            "too_long": "The video is longer than we can process in one job.", "no_audio": "The video has no audio.", "unreadable_media": "We could not read that video file.", "no_moments": "We found no moment worth clipping in this stream.",
            "path_not_allowed": "That file location is not allowed.", "no_video": "The source has no video track."}


class Worker:
    def __init__(self, api, cfg=None, log=None, runner=None, clock=time.time, sleep=None, publisher=None):
        self.api, self.cfg, self.log = api, cfg or default_cfg(), log or Log(); self.runner = runner or run_subprocess; self.clock = clock; self.publisher = publisher; self.deadline = None
        self.stop = threading.Event(); self.sleep = sleep or (lambda s: self.stop.wait(s)); self.inflight = {}; self.lock = threading.Lock(); self.done_ids = set(); self.pool = ThreadPoolExecutor(max_workers=self.cfg["concurrency"]); self.futures = []; self.last_cleanup = 0
        os.makedirs(self.cfg["work_dir"], exist_ok=True); os.makedirs(self.cfg["out_dir"], exist_ok=True)

    # -- reporting (never raises: a lost progress message must not kill a render)
    def _post(self, jid, **body):
        try: return self.api.post(jid, **body)
        except AuthError: raise
        except Exception as e: self.log("report_failed", "warn", job=jid, error=str(e)[:150]); return None

    # -- one job, with retries
    def process(self, job):
        jid = job["id"]; t0 = self.clock(); self.log("job_start", job=jid, org=job.get("org"), source=(job.get("source") or {}).get("type")); last_post = [0.0, None]
        workdir = os.path.join(self.cfg["work_dir"], jid)
        def on_progress(d):
            key = (d.get("msg"), d.get("message")); now = self.clock()
            if key == last_post[1] and now - last_post[0] < self.cfg["progress_min_interval_s"]: return
            last_post[0], last_post[1] = now, key; self._post(jid, **d)
        out = None; attempts = self.cfg["retries"] + 1
        for attempt in range(1, attempts + 1):
            if attempt > 1: shutil.rmtree(workdir, ignore_errors=True); self.sleep(min(self.cfg["backoff_s"] * (attempt - 1), 120)); self.log("job_retry", "warn", job=jid, attempt=attempt)
            try: out = self.runner(job, workdir, self.cfg, on_progress, self.log, self.stop)
            except AuthError: raise
            except Exception as e: out = Outcome(1, error={"code": "crash", "message": "%s: %s" % (type(e).__name__, str(e)[:100])})
            if out.code == 0 or out.code in (3, 4) or out.killed == "shutdown" or self.stop.is_set(): break
            self.log("job_attempt_failed", "warn", job=jid, attempt=attempt, code=out.code, killed=out.killed, error=(out.error or {}).get("message", ""))
        if out.code == 0 and out.result: self._finish_ok(job, out.result, workdir, t0)
        else: self._finish_failed(job, out, workdir, t0)
        self.done_ids.add(jid)

    def _finish_ok(self, job, result, workdir, t0):
        jid = job["id"]; dest = os.path.join(self.cfg["out_dir"], jid); shutil.rmtree(dest, ignore_errors=True)
        os.makedirs(dest, exist_ok=True); drafts = []
        for d in result.get("drafts", []):
            try:
                for k in ("file", "meta_file"):
                    src = os.path.join(workdir, d[k]); tgt = os.path.join(dest, os.path.basename(src)); shutil.move(src, tgt)
                for ext in (".words.json", ".ass"):   # side files used by the QA/upload step
                    s2 = os.path.join(workdir, os.path.splitext(d["file"])[0] + ext)
                    if os.path.exists(s2): shutil.move(s2, os.path.join(dest, os.path.basename(s2)))
                d = dict(d, file=os.path.basename(d["file"]), meta_file=os.path.basename(d["meta_file"]), local_id="%s/%s" % (jid, os.path.basename(d["file"]))); drafts.append(d)
            except Exception as e: self.log("draft_move_failed", "error", job=jid, error=str(e)[:150])
        if not drafts: return self._finish_failed(job, Outcome(1, error={"code": "no_drafts", "message": "drafts could not be stored"}), workdir, t0)
        self._post(jid, status="qa", msg="qa", progress=97)
        if self.publisher:   # preview phase: small renditions the browser can play; a failure here never fails the job (the draft just has no preview)
            try:
                urls = self.publisher(job, drafts, dest) or {}
                for d in drafts:
                    if urls.get(d["file"]): d["preview_url"] = urls[d["file"]]
            except Exception as e: self.log("preview_failed", "warn", job=jid, error=str(e)[:150])
        json.dump({"job": jid, "org": job.get("org"), "channel": job.get("channel"), "created": time.time(), "drafts": drafts, "uploaded": False}, open(os.path.join(dest, "manifest.json"), "w"), ensure_ascii=False, indent=1)
        api_drafts = [{"kind": d["kind"], "title": d["title"], "qa_ok": bool(d["qa_ok"]), "qa_notes": d.get("qa_notes", ""), "qa_score": d.get("qa_score"), "duration_s": d.get("duration_s"), "local_id": d["local_id"], "hook": d.get("hook", ""), "preview_url": d.get("preview_url", "")} for d in drafts]
        self._post(jid, status="draft_ready", progress=100, drafts=api_drafts)
        shutil.rmtree(workdir, ignore_errors=True)   # success: scratch (source copy, audio chunks, bodies) is deleted at once; the drafts live in out/
        self.log("job_done", job=jid, drafts=len(drafts), qa_ok=sum(1 for d in drafts if d["qa_ok"]), seconds=round(self.clock() - t0, 1))

    def _finish_failed(self, job, out, workdir, t0):
        jid = job["id"]; code = (out.error or {}).get("code") or (out.killed or "crash")
        msg = FRIENDLY.get(code) or {"timeout": "This took too long and was stopped.", "stalled": "This got stuck and was stopped.", "shutdown": "The server restarted while working on this."}.get(code) or "Something went wrong on our side."
        self._post(jid, status="failed", error=redact(msg + " [" + str(code) + "]", [self.cfg.get("secret", "")])[:200], progress=0)
        self.log("job_failed", "error", job=jid, code=code, detail=(out.error or {}).get("message", ""), killed=out.killed, seconds=round(self.clock() - t0, 1))
        try:
            os.makedirs(workdir, exist_ok=True)
            with open(os.path.join(workdir, "FAILED"), "w") as f: f.write(str(code))   # scratch is kept for keep_failed_h so the owner can look at it
        except OSError: pass

    # -- housekeeping
    def cleanup(self):
        """delete failed scratch older than keep_failed_h, orphan scratch (crashed worker), finished drafts older than keep_drafts_d"""
        now = self.clock(); n = 0
        for base, max_age in ((self.cfg["work_dir"], self.cfg["keep_failed_h"] * 3600),):
            for name in os.listdir(base):
                p = os.path.join(base, name)
                if name in self.inflight or not os.path.isdir(p): continue
                try:
                    if now - os.path.getmtime(p) > max_age: shutil.rmtree(p, ignore_errors=True); n += 1
                except OSError: pass
        keep = self.cfg["keep_drafts_d"] * 86400
        for name in os.listdir(self.cfg["out_dir"]):
            p = os.path.join(self.cfg["out_dir"], name)
            try:
                if os.path.isdir(p) and now - os.path.getmtime(p) > keep: shutil.rmtree(p, ignore_errors=True); n += 1
            except OSError: pass
        if n: self.log("cleanup", removed=n)
        return n

    def free_gb(self):
        try: return shutil.disk_usage(self.cfg["work_dir"]).free / 1e9
        except Exception: return 1e9

    # -- main loop
    def _run_one(self, job):
        jid = job["id"]
        try: self.process(job)
        except AuthError: self.log("auth_rejected", "error"); self.auth_failed = True; self.stop.set()
        except Exception as e: self.log("job_crashed", "error", job=jid, error="%s: %s" % (type(e).__name__, str(e)[:150])); self._post(jid, status="failed", error="Something went wrong on our side. [internal]")
        finally:
            with self.lock: self.inflight.pop(jid, None)

    queue_empty = False   # set by tick(): the last claim returned no job (drain mode exits on it, not on "all slots busy")
    def tick(self):
        """one scheduling step; returns True when a job was claimed"""
        self.queue_empty = False
        with self.lock: busy = len(self.inflight)
        if busy >= self.cfg["concurrency"] or self.stop.is_set(): return False
        if self.deadline is not None and self.deadline - self.clock() < self.cfg.get("min_claim_s", 300): self.log("budget_reached", seconds_left=int(self.deadline - self.clock())); self.out_of_time = True; return False
        if self.free_gb() < self.cfg["min_free_gb"]: self.log("disk_low", "warn", free_gb=round(self.free_gb(), 1)); self.cleanup(); self.queue_empty = True; return False
        job = self.api.claim()
        if not job: self.queue_empty = True; return False
        jid = job.get("id")
        if not isinstance(jid, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", jid): self.log("bad_job_id", "error"); return False
        if jid in self.done_ids or jid in self.inflight: self.log("duplicate_claim", "warn", job=jid); return False
        with self.lock: self.inflight[jid] = self.clock()
        self.futures.append(self.pool.submit(self._run_one, job)); self.futures = [f for f in self.futures if not f.done()]; return True

    auth_failed = False; out_of_time = False
    def run_forever(self, once=False, max_minutes=None):
        """once=True: drain the queue (claim until a claim returns nothing), wait for the running jobs, return. max_minutes: overall time budget (see the module docstring)."""
        if max_minutes: self.deadline = self.clock() + float(max_minutes) * 60; self.cfg["hard_stop_at"] = self.deadline   # running jobs are killed (and reported failed) at the deadline
        self.log("worker_start", concurrency=self.cfg["concurrency"], work=self.cfg["work_dir"], out=self.cfg["out_dir"], once=once, max_minutes=max_minutes, previews=bool(self.publisher)); errors = 0
        while not self.stop.is_set():
            if self.deadline is not None and self.clock() >= self.deadline: self.out_of_time = True; self.log("deadline_reached"); break
            if self.clock() - self.last_cleanup > 3600: self.last_cleanup = self.clock(); self.cleanup()
            try: got = self.tick(); errors = 0
            except AuthError: self.log("auth_rejected", "error", hint="STUDIO_WORKER_KEY does not match the studio"); self.auth_failed = True; break
            except Exception as e: errors += 1; got = False; self.log("claim_failed", "warn", error=str(e)[:150], consecutive=errors)
            if got: continue
            if once:
                with self.lock: busy = len(self.inflight)
                if busy >= self.cfg["concurrency"]: self.sleep(1.0); continue   # all slots busy: just wait for one to free up
                if (self.queue_empty or self.out_of_time) and not busy: break
                if (self.queue_empty or self.out_of_time) and busy: self.sleep(1.0); continue   # nothing more to claim; wait for the running jobs (they end by themselves or at the deadline)
                if errors >= 5: break   # API unreachable: a drain run gives up instead of burning runner minutes
            if self.out_of_time and not once: break
            self.sleep(min(300, self.cfg["poll_s"] * (2 ** min(errors, 4) if errors else 1)) * (0.8 + 0.4 * random.random()))
        if once and not self.stop.is_set() and not self.auth_failed and not self.out_of_time: self.wait_for_jobs()   # drain: let running jobs finish normally (no grace limit)
        self.shutdown()
        return 5 if self.auth_failed else 0

    def wait_for_jobs(self):
        for f in list(self.futures):
            try: f.result()
            except Exception: pass

    def shutdown(self):
        """stop claiming; running jobs get grace_s seconds, then they are killed and reported failed (credit refunded by the API)"""
        self.stop.set(); self.cfg.setdefault("hard_stop_at", self.clock() + self.cfg["grace_s"])
        self.log("worker_stopping", running=len(self.inflight), grace_s=self.cfg["grace_s"])
        for f in list(self.futures):
            try: f.result()
            except Exception: pass
        self.pool.shutdown(wait=True); self.log("worker_stopped")


# ---------------------------------------------------------------- demo
def demo(log, keep=False):
    """offline end-to-end: synthetic video -> spool job -> worker -> drafts + QA, all in a temp directory. Returns the finished worker report."""
    tmp = tempfile.mkdtemp(prefix="rw_demo_"); sys.path.insert(0, HERE); import job_runner as JR
    media = JR.make_demo_media(os.path.join(tmp, "demo.mp4"), 150); spool = os.path.join(tmp, "spool"); os.makedirs(spool)
    json.dump({"id": "j_demo01", "org": "o_demo", "channel": "c_demo", "kind": "edit", "source": {"type": "url", "ref": media}, "style_id": "signature", "outputs": {"shorts": 2, "long": False}, "hints": {}}, open(os.path.join(spool, "j_demo01.json"), "w"))
    cfg = default_cfg(); cfg.update({"work_dir": os.path.join(tmp, "work"), "out_dir": os.path.join(tmp, "out"), "demo": True, "poll_s": 1, "retries": 0})
    w = Worker(SpoolApi(spool), cfg, log); rc = w.run_forever(once=True)
    rep = [json.loads(l) for l in open(os.path.join(spool, "j_demo01.report.jsonl"))]
    final = rep[-1]; print("\nDEMO RESULT (status=%s) files in %s" % (final.get("status"), cfg["out_dir"]))
    for d in final.get("drafts", []): print("  %-5s %-40s qa_ok=%s score=%s %ss  %s" % (d["kind"], d["title"][:40], d["qa_ok"], d.get("qa_score"), d.get("duration_s"), d["local_id"]))
    if not keep: print("(temp dir kept at %s)" % tmp)
    return 0 if final.get("status") == "draft_ready" else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0]); ap.add_argument("--once", action="store_true"); ap.add_argument("--max-minutes", type=float, default=0); ap.add_argument("--spool"); ap.add_argument("--demo", action="store_true"); ap.add_argument("--api"); a = ap.parse_args(argv)
    key = os.environ.get("STUDIO_WORKER_KEY", ""); log = Log(os.environ.get("WORKER_LOG", "json"), [key, os.environ.get("GITHUB_TOKEN", "")])
    if a.demo: return demo(log)
    cfg = default_cfg(); cfg["secret"] = key
    if a.spool: api = SpoolApi(a.spool)
    else:
        base = a.api or os.environ.get("STUDIO_URL", "")
        if not base or not key: print("STUDIO_URL and STUDIO_WORKER_KEY are required (or use --spool DIR / --demo)", file=sys.stderr); return 2
        if not base.startswith("https://") and not re.match(r"^http://(localhost|127\.0\.0\.1)", base): print("STUDIO_URL must be https (or localhost)", file=sys.stderr); return 2
        api = StudioApi(base, key)
    try: import preview_publish as PP; publisher = PP.from_env(log=lambda ev, level="info", **kw: log(ev, level, **kw))
    except Exception as e: publisher = None; log("preview_setup_failed", "warn", error=str(e)[:150])
    w = Worker(api, cfg, log, publisher=publisher); n = [0]
    def on_sig(sig, frm):
        n[0] += 1; log("signal", signum=int(sig), count=n[0])
        if n[0] == 1: w.stop.set(); w.cfg["hard_stop_at"] = w.clock() + w.cfg["grace_s"]
        else: w.cfg["hard_stop_at"] = 0   # second signal: kill running jobs now
    signal.signal(signal.SIGTERM, on_sig); signal.signal(signal.SIGINT, on_sig)
    return w.run_forever(once=a.once, max_minutes=a.max_minutes or None)


if __name__ == "__main__": sys.exit(main())

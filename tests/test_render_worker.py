"""Unit tests for scripts/render_worker.py: the job loop against a MOCKED studio API (no network, no models, no ffmpeg except the one end-to-end test at the bottom).
The mock studio re-implements the worker contract of app/studio.js (x-worker-key, claim, JOB_FLOW transitions, draft mapping) so the loop is tested against the same rules.
Run: python3 -m unittest tests/test_render_worker.py"""
import io, json, os, shutil, sys, tempfile, textwrap, threading, time, unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import render_worker as RW

KEY = "wk_secretvalue123"
JOB_FLOW = {"queued": ["running", "cancelled"], "running": ["qa", "failed", "cancelled"], "qa": ["draft_ready", "failed"], "draft_ready": ["approved", "rejected"]}


class FakeStudio:
    """transport(method, url, headers, body, timeout) -> (status, bytes), plus the state a real studio would hold"""
    def __init__(self, key=KEY):
        self.key, self.queue, self.jobs, self.requests, self.fail_next, self.lock = key, [], {}, [], [], threading.Lock()
    def add_job(self, jid, **kw):
        job = {"id": jid, "org": "o_1", "channel": "c_1", "kind": "edit", "source": {"type": "url", "ref": "/x.mp4"}, "style_id": "signature", "outputs": {"shorts": 2, "long": False}, "hints": {}}; job.update(kw)
        self.queue.append(job); self.jobs[jid] = {"status": "queued", "events": [], "drafts": [], "progress": 0, "msgs": [], "error": None}; return job
    def __call__(self, method, url, headers, body, timeout):
        with self.lock:
            self.requests.append((method, url, dict(headers)))
            if self.fail_next:
                st = self.fail_next.pop(0)
                if st == "net": raise OSError("connection reset")
                return st, b"{}"
            if headers.get("x-worker-key") != self.key: return 401, b'{"error":"unauthorized"}'
            b = json.loads(body or b"{}"); path = url.split("//", 1)[1].split("/", 1)[1]
            if path == "studio/worker/claim":
                if not self.queue: return 200, b'{"job":null}'
                job = self.queue.pop(0); self.jobs[job["id"]]["status"] = "running"; return 200, json.dumps({"job": job}).encode()
            if path.startswith("studio/worker/jobs/"):
                j = self.jobs[path.rsplit("/", 1)[1]]
                if b.get("status") and b["status"] != j["status"]:
                    if b["status"] not in JOB_FLOW.get(j["status"], []) or b["status"] not in ("qa", "draft_ready", "failed"): return 409, b'{"error":"bad_state"}'
                    j["status"] = b["status"]
                if b.get("msg") or b.get("message"): j["msgs"].append((b.get("msg"), b.get("vars"), b.get("message")))
                if "progress" in b: j["progress"] = b["progress"]
                if "drafts" in b: j["drafts"] = b["drafts"]
                if b.get("error"): j["error"] = b["error"]
                return 200, b'{"ok":true}'
            return 404, b"{}"


def fake_outcome_ok(n=2, qa_ok=True):
    """a runner that 'renders' n drafts into the workdir the way job_runner.py does"""
    def runner(job, workdir, cfg, on_progress, log, stop):
        os.makedirs(os.path.join(workdir, "drafts"), exist_ok=True); drafts = []
        on_progress({"progress": 10, "msg": "downloading", "vars": {}}); on_progress({"progress": 40, "msg": "found_moments", "vars": {"n": n}})
        for i in range(n):
            f = "drafts/short_%d.mp4" % i; open(os.path.join(workdir, f), "wb").write(b"mp4data"); open(os.path.join(workdir, f[:-4] + ".json"), "w").write("{}"); open(os.path.join(workdir, f[:-4] + ".words.json"), "w").write("[]")
            drafts.append({"kind": "short", "title": "Clip %d #Shorts" % i, "file": f, "meta_file": f[:-4] + ".json", "qa_ok": qa_ok, "qa_score": 90, "qa_notes": "", "duration_s": 30.0, "start_s": 1, "end_s": 31, "hook": "H"})
        return RW.Outcome(0, {"drafts": drafts})
    return runner


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rwtest_"); self.studio = FakeStudio(); self.logbuf = io.StringIO()
        self.cfg = RW.default_cfg({}); self.cfg.update({"work_dir": os.path.join(self.tmp, "work"), "out_dir": os.path.join(self.tmp, "out"), "poll_s": 1, "backoff_s": 0, "progress_min_interval_s": 0, "secret": KEY, "grace_s": 5})
        self.log = RW.Log("json", [KEY], self.logbuf)
    def tearDown(self): shutil.rmtree(self.tmp, ignore_errors=True)
    def worker(self, runner, **cfg):
        self.cfg.update(cfg); api = RW.StudioApi("https://studio.test", KEY, transport=self.studio, retries=2, sleep=lambda s: None)
        return RW.Worker(api, self.cfg, self.log, runner=runner, sleep=lambda s: None)
    def logs(self): return [json.loads(l) for l in self.logbuf.getvalue().splitlines() if l.strip()]


class JobLoop(Base):
    def test_happy_path_posts_progress_then_drafts_and_never_uploads(self):
        before = set(sys.modules); self.studio.add_job("j_aa01"); w = self.worker(fake_outcome_ok(2)); self.assertTrue(w.tick()); [f.result() for f in w.futures]
        j = self.studio.jobs["j_aa01"]; self.assertEqual(j["status"], "draft_ready"); self.assertEqual(j["progress"], 100)
        self.assertIn(("found_moments", {"n": 2}, None), j["msgs"])
        self.assertEqual([d["title"] for d in j["drafts"]], ["Clip 0 #Shorts", "Clip 1 #Shorts"]); self.assertTrue(all(d["qa_ok"] and d["local_id"].startswith("j_aa01/") for d in j["drafts"]))
        out = os.path.join(self.cfg["out_dir"], "j_aa01"); self.assertTrue(os.path.exists(os.path.join(out, "short_0.mp4"))); self.assertTrue(os.path.exists(os.path.join(out, "short_0.json")))
        man = json.load(open(os.path.join(out, "manifest.json"))); self.assertFalse(man["uploaded"]); self.assertEqual(len(man["drafts"]), 2)
        self.assertFalse(os.path.exists(os.path.join(self.cfg["work_dir"], "j_aa01")), "scratch must be deleted after success")
        # the only host the worker ever talks to is the studio; no module that uploads was imported
        self.assertTrue(all(u.startswith("https://studio.test/studio/worker/") for _, u, _ in self.studio.requests)); self.assertFalse([m for m in set(sys.modules) - before if m.startswith("yt_upload")])

    def test_qa_failed_draft_is_reported_with_qa_ok_false(self):
        self.studio.add_job("j_aa02"); w = self.worker(fake_outcome_ok(1, qa_ok=False)); w.tick(); [f.result() for f in w.futures]
        self.assertFalse(self.studio.jobs["j_aa02"]["drafts"][0]["qa_ok"]); self.assertEqual(self.studio.jobs["j_aa02"]["status"], "draft_ready")

    def test_crash_is_retried_then_succeeds(self):
        calls = []; ok = fake_outcome_ok(1)
        def flaky(job, workdir, cfg, on_progress, log, stop):
            calls.append(1)
            return RW.Outcome(1, error={"code": "crash", "message": "boom"}) if len(calls) == 1 else ok(job, workdir, cfg, on_progress, log, stop)
        self.studio.add_job("j_aa03"); w = self.worker(flaky, retries=1); w.tick(); [f.result() for f in w.futures]
        self.assertEqual(len(calls), 2); self.assertEqual(self.studio.jobs["j_aa03"]["status"], "draft_ready")

    def test_crash_every_time_fails_job_after_retries(self):
        calls = []
        def bad(job, workdir, cfg, on_progress, log, stop): calls.append(1); return RW.Outcome(1, error={"code": "crash", "message": "boom"})
        self.studio.add_job("j_aa04"); w = self.worker(bad, retries=2); w.tick(); [f.result() for f in w.futures]
        self.assertEqual(len(calls), 3); j = self.studio.jobs["j_aa04"]; self.assertEqual(j["status"], "failed"); self.assertIn("went wrong", j["error"]); self.assertTrue(os.path.exists(os.path.join(self.cfg["work_dir"], "j_aa04", "FAILED")))

    def test_customer_fixable_error_is_not_retried_and_message_is_friendly(self):
        calls = []
        def bad(job, workdir, cfg, on_progress, log, stop): calls.append(1); return RW.Outcome(3, error={"code": "no_audio", "message": "x"})
        self.studio.add_job("j_aa05"); w = self.worker(bad, retries=3); w.tick(); [f.result() for f in w.futures]
        self.assertEqual(len(calls), 1); j = self.studio.jobs["j_aa05"]; self.assertEqual(j["status"], "failed"); self.assertIn("no audio", j["error"].lower())

    def test_no_moments_fails_with_message(self):
        self.studio.add_job("j_aa06"); w = self.worker(lambda *a: RW.Outcome(4, error={"code": "no_moments", "message": ""})); w.tick(); [f.result() for f in w.futures]
        self.assertIn("no moment", self.studio.jobs["j_aa06"]["error"].lower())

    def test_runner_exception_does_not_kill_the_worker(self):
        def boom(*a): raise RuntimeError("kaboom")
        self.studio.add_job("j_aa07"); self.studio.add_job("j_aa08"); w = self.worker(boom, retries=0); w.tick(); [f.result() for f in w.futures]; w.futures = []
        self.assertEqual(self.studio.jobs["j_aa07"]["status"], "failed"); self.assertTrue(w.tick())   # still alive, claims the next one

    def test_concurrency_limit(self):
        gate = threading.Event(); started = []
        def slow(job, workdir, cfg, on_progress, log, stop): started.append(job["id"]); gate.wait(10); return fake_outcome_ok(1)(job, workdir, cfg, on_progress, log, stop)
        for i in range(4): self.studio.add_job("j_bb0%d" % i)
        w = self.worker(slow, concurrency=2); self.assertTrue(w.tick()); self.assertTrue(w.tick()); self.assertFalse(w.tick(), "third claim must wait for a free slot")
        self.assertEqual(len(self.studio.queue), 2); gate.set(); [f.result() for f in w.futures]
        deadline = time.time() + 5
        while w.inflight and time.time() < deadline: time.sleep(0.05)
        self.assertTrue(w.tick())

    def test_duplicate_claim_is_ignored(self):
        job = self.studio.add_job("j_aa09"); w = self.worker(fake_outcome_ok(1)); w.tick(); [f.result() for f in w.futures]
        self.studio.queue.append(dict(job)); self.assertFalse(w.tick()); self.assertTrue(any(l["event"] == "duplicate_claim" for l in self.logs()))

    def test_bad_job_id_rejected(self):
        self.studio.add_job("../../etc"); w = self.worker(fake_outcome_ok(1)); self.assertFalse(w.tick())

    def test_disk_low_stops_claiming(self):
        self.studio.add_job("j_aa10"); w = self.worker(fake_outcome_ok(1), min_free_gb=10 ** 9); self.assertFalse(w.tick()); self.assertEqual(len(self.studio.queue), 1)

    def test_progress_is_throttled(self):
        def chatty(job, workdir, cfg, on_progress, log, stop):
            for i in range(20): on_progress({"progress": i, "msg": "transcribing", "vars": {"pct": i}})
            return RW.Outcome(4, error={"code": "no_moments"})
        self.studio.add_job("j_aa11"); w = self.worker(chatty, progress_min_interval_s=3600); w.tick(); [f.result() for f in w.futures]
        self.assertEqual(len(self.studio.jobs["j_aa11"]["msgs"]), 1)


class ApiResilience(Base):
    def test_network_errors_and_5xx_are_retried(self):
        self.studio.fail_next = ["net", 503]; self.studio.add_job("j_cc01"); api = RW.StudioApi("https://studio.test", KEY, transport=self.studio, retries=3, sleep=lambda s: None)
        self.assertEqual(api.claim()["id"], "j_cc01")

    def test_wrong_key_stops_the_worker_with_exit_5(self):
        api = RW.StudioApi("https://studio.test", "wrong-key-xxxx", transport=self.studio, retries=1, sleep=lambda s: None); w = RW.Worker(api, self.cfg, self.log, runner=fake_outcome_ok(1), sleep=lambda s: None)
        self.assertEqual(w.run_forever(), 5); self.assertTrue(any(l["event"] == "auth_rejected" for l in self.logs()))

    def test_claim_outage_keeps_loop_alive(self):
        n = [0]
        class Flaky:
            def claim(s):
                n[0] += 1
                if n[0] < 3: raise RW.ApiError(503, "down")
                w.stop.set(); return None
            def post(s, *a, **k): return {}
        w = RW.Worker(Flaky(), self.cfg, self.log, runner=fake_outcome_ok(1), sleep=lambda s: None); self.assertEqual(w.run_forever(), 0); self.assertEqual(n[0], 3)
        self.assertEqual(sum(1 for l in self.logs() if l["event"] == "claim_failed"), 2)

    def test_progress_post_failure_does_not_fail_the_job(self):
        self.studio.add_job("j_cc02"); w = self.worker(fake_outcome_ok(1)); real = w.api.post; cnt = [0]
        def post(jid, **b):
            cnt[0] += 1
            if "msg" in b and b.get("msg") == "found_moments": raise RW.ApiError(500, "x")
            return real(jid, **b)
        w.api.post = post; w.tick(); [f.result() for f in w.futures]; self.assertEqual(self.studio.jobs["j_cc02"]["status"], "draft_ready")

    def test_secrets_never_reach_logs(self):
        self.studio.add_job("j_cc03"); w = self.worker(lambda *a: RW.Outcome(1, error={"code": "crash", "message": "token " + KEY + " Bearer abcdefghijklmnop12345 AIzaSyA1234567890123456789012"}), retries=0); w.tick(); [f.result() for f in w.futures]
        txt = self.logbuf.getvalue(); self.assertNotIn(KEY, txt); self.assertNotIn("abcdefghijklmnop12345", txt); self.assertNotIn("AIzaSyA1234567890123456789012", txt)


class Subprocess(Base):
    """the real run_subprocess with a stand-in RUNNER script (no ffmpeg)"""
    def script(self, body):
        p = os.path.join(self.tmp, "fake_runner.py"); open(p, "w").write(textwrap.dedent(body)); self._old = RW.RUNNER; RW.RUNNER = p; self.addCleanup(lambda: setattr(RW, "RUNNER", self._old)); return p
    def run_sub(self, **cfg):
        c = dict(self.cfg); c.update(cfg); prog = []; out = RW.run_subprocess({"id": "j_dd01"}, os.path.join(self.tmp, "w1"), c, prog.append, self.log, threading.Event(), [KEY]); return out, prog
    def test_ok_result_and_progress_lines_parsed(self):
        self.script("""
            import sys, json, os
            wd = sys.argv[sys.argv.index('--workdir') + 1]; os.makedirs(wd, exist_ok=True)
            print('PROGRESS ' + json.dumps({'progress': 5, 'msg': 'downloading', 'vars': {}}), flush=True)
            json.dump({'drafts': []}, open(wd + '/result.json', 'w')); print('RESULT ' + wd + '/result.json')
            """)
        out, prog = self.run_sub(); self.assertEqual(out.code, 0); self.assertEqual(out.result, {"drafts": []}); self.assertEqual(prog[0]["msg"], "downloading")
    def test_timeout_kills_the_process_group(self):
        self.script("import time\nprint('PROGRESS {}', flush=True)\ntime.sleep(60)\n"); t0 = time.time(); out, _ = self.run_sub(job_timeout_s=2, stall_s=100)
        self.assertEqual(out.killed, "timeout"); self.assertNotEqual(out.code, 0); self.assertLess(time.time() - t0, 20)
    def test_stall_is_detected(self):
        self.script("import time\nprint('hello', flush=True)\ntime.sleep(60)\n"); out, _ = self.run_sub(job_timeout_s=100, stall_s=2); self.assertEqual(out.killed, "stalled")
    def test_error_line_and_exit_code_3(self):
        self.script("import sys\nprint('ERROR {\"code\": \"no_audio\", \"message\": \"m\"}')\nsys.exit(3)\n"); out, _ = self.run_sub(); self.assertEqual((out.code, out.error["code"]), (3, "no_audio"))
    def test_worker_key_is_not_passed_to_the_job(self):
        self.script("import os\nprint('PROGRESS ' + __import__('json').dumps({'message': 'key=' + os.environ.get('STUDIO_WORKER_KEY', 'absent')}))\n"); os.environ["STUDIO_WORKER_KEY"] = KEY; self.addCleanup(lambda: os.environ.pop("STUDIO_WORKER_KEY", None))
        out, prog = self.run_sub(); self.assertEqual(prog[0]["message"], "key=absent")


class Shutdown(Base):
    def test_sigterm_lets_running_job_finish_and_claims_nothing_new(self):
        gate = threading.Event(); self.studio.add_job("j_ee01"); self.studio.add_job("j_ee02")
        def slow(job, workdir, cfg, on_progress, log, stop): gate.wait(10); return fake_outcome_ok(1)(job, workdir, cfg, on_progress, log, stop)
        w = self.worker(slow, concurrency=1); t = threading.Thread(target=w.run_forever); t.start(); deadline = time.time() + 5
        while not w.inflight and time.time() < deadline: time.sleep(0.02)
        w.stop.set(); gate.set(); t.join(10); self.assertFalse(t.is_alive())
        self.assertEqual(self.studio.jobs["j_ee01"]["status"], "draft_ready"); self.assertEqual(self.studio.jobs["j_ee02"]["status"], "queued")

    def test_after_grace_running_job_is_killed_and_reported_failed(self):
        p = os.path.join(self.tmp, "slow_runner.py"); open(p, "w").write("import time\nprint('PROGRESS {}', flush=True)\ntime.sleep(60)\n"); old = RW.RUNNER; RW.RUNNER = p; self.addCleanup(lambda: setattr(RW, "RUNNER", old))
        self.studio.add_job("j_ee03"); w = self.worker(RW.run_subprocess, retries=3, grace_s=1); t = threading.Thread(target=w.run_forever); t.start(); deadline = time.time() + 5
        while not w.inflight and time.time() < deadline: time.sleep(0.02)
        time.sleep(0.5); w.stop.set(); w.cfg["hard_stop_at"] = time.time() + 1; t.join(30); self.assertFalse(t.is_alive())
        j = self.studio.jobs["j_ee03"]; self.assertEqual(j["status"], "failed"); self.assertIn("restarted", j["error"])


class Housekeeping(Base):
    def test_cleanup_removes_old_scratch_and_drafts_but_not_running_jobs(self):
        w = self.worker(fake_outcome_ok(1)); old = time.time() - 3 * 86400 * 30
        for base, name in ((self.cfg["work_dir"], "j_old_failed"), (self.cfg["work_dir"], "j_running"), (self.cfg["work_dir"], "j_recent"), (self.cfg["out_dir"], "j_old_drafts"), (self.cfg["out_dir"], "j_new_drafts")):
            os.makedirs(os.path.join(base, name));
            if "old" in name or name == "j_running": os.utime(os.path.join(base, name), (old, old))
        w.inflight["j_running"] = time.time(); n = w.cleanup()
        self.assertEqual(n, 2); self.assertFalse(os.path.exists(os.path.join(self.cfg["work_dir"], "j_old_failed"))); self.assertTrue(os.path.exists(os.path.join(self.cfg["work_dir"], "j_running")))
        self.assertTrue(os.path.exists(os.path.join(self.cfg["work_dir"], "j_recent"))); self.assertFalse(os.path.exists(os.path.join(self.cfg["out_dir"], "j_old_drafts"))); self.assertTrue(os.path.exists(os.path.join(self.cfg["out_dir"], "j_new_drafts")))


class Spool(Base):
    def test_spool_roundtrip(self):
        d = os.path.join(self.tmp, "spool"); os.makedirs(d); json.dump({"id": "j_ff01", "source": {"type": "url", "ref": "/x"}}, open(os.path.join(d, "j_ff01.json"), "w"))
        api = RW.SpoolApi(d); w = RW.Worker(api, self.cfg, self.log, runner=fake_outcome_ok(1), sleep=lambda s: None); self.assertEqual(w.run_forever(once=True), 0)
        rep = [json.loads(l) for l in open(os.path.join(d, "j_ff01.report.jsonl"))]; self.assertEqual(rep[-1]["status"], "draft_ready"); self.assertTrue(os.path.exists(os.path.join(d, "j_ff01.result.json"))); self.assertIsNone(api.claim())


if __name__ == "__main__": unittest.main()

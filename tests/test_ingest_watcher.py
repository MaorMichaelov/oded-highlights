"""Tests for scripts/ingest_watcher.py: stream-end detection, segment hand-off, live windows, retries, the MediaMTX auth hook. No ffmpeg, no network (fake segments, fake submit, localhost HTTP).
Run: python3 -m unittest tests/test_ingest_watcher.py"""
import io, json, os, shutil, sys, tempfile, threading, time, unittest, urllib.error, urllib.request
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import ingest_watcher as IW
import render_worker as RW

KEY = "ik_0123456789abcdef0123456789abcdef"
KEY2 = "ik_fedcba9876543210fedcba9876543210"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="iwtest_"); self.rec = os.path.join(self.tmp, "rec"); self.ing = os.path.join(self.tmp, "ing"); os.makedirs(os.path.join(self.rec, KEY)); self.now = [time.time()]
        self.jobs = []; self.fail = []; self.log = RW.Log("json", [], io.StringIO(), "t")
    def tearDown(self): shutil.rmtree(self.tmp, ignore_errors=True)
    def seg(self, name, age_s, key=KEY, size=1000):
        p = os.path.join(self.rec, key, name); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "wb").write(b"x" * size); t = self.now[0] - age_s; os.utime(p, (t, t)); return p
    def submit(self, key, ref, minutes, live, idem):
        if self.fail:
            e = self.fail.pop(0)
            if e: raise e
        self.jobs.append({"key": key, "ref": ref, "minutes": minutes, "live": live, "idem": idem}); return "j_" + str(len(self.jobs))
    def watcher(self, **kw):
        kw.setdefault("probe", lambda p: 300.0); return IW.Watcher(self.rec, self.ing, IW.Keys(path=None), self.submit, self.log, clock=lambda: self.now[0], **kw)


class Handoff(Base):
    def test_ended_stream_becomes_one_job_and_segments_move(self):
        for i, n in enumerate(("20261117-200000.ts", "20261117-200500.ts", "20261117-201000.ts")): self.seg(n, 1200 - i * 300)
        w = self.watcher(end_after_s=600); made = w.scan(); self.assertEqual(len(made), 1); j = self.jobs[0]
        self.assertRegex(j["ref"], r"^ingest:s[0-9a-f]{10}-20261117-200000$"); self.assertNotIn(KEY, json.dumps(j["ref"])); self.assertFalse(j["live"]); self.assertEqual(j["minutes"], 15); self.assertEqual(j["key"], KEY)
        d = os.path.join(self.ing, j["ref"][7:]); self.assertEqual(len(os.listdir(d)), 3); self.assertEqual(os.listdir(os.path.join(self.rec, KEY)), [])
        self.assertEqual(w.scan(), []); self.assertEqual(len(self.jobs), 1)   # nothing is processed twice

    def test_running_stream_is_left_alone(self):
        self.seg("20261117-200000.ts", 100); self.assertEqual(self.watcher(end_after_s=600).scan(), []); self.assertEqual(self.jobs, [])

    def test_reconnect_within_the_end_window_stays_one_stream(self):
        self.seg("20261117-200000.ts", 500); self.seg("20261117-200800.ts", 60)   # gap of 8 minutes, newest segment is fresh -> still live
        self.assertEqual(self.watcher(end_after_s=600).scan(), [])

    def test_short_test_stream_is_ignored_and_cleaned(self):
        self.seg("20261117-200000.ts", 1000); w = self.watcher(min_stream_s=400, probe=lambda p: 30.0); self.assertEqual(w.scan(), []); self.assertEqual(self.jobs, []); self.assertEqual(os.listdir(os.path.join(self.rec, KEY)), [])

    def test_other_directories_and_files_are_ignored(self):
        os.makedirs(os.path.join(self.rec, "not-a-key")); open(os.path.join(self.rec, "not-a-key", "a.ts"), "w").write("x"); self.seg("readme.txt", 5000); self.seg("empty.ts", 5000, size=0)
        self.assertEqual(self.watcher().scan(), [])

    def test_live_windows_then_final_job_without_double_processing(self):
        names = ["20261117-20%02d00.ts" % (m * 5) for m in range(6)]
        for i, n in enumerate(names[:4]): self.seg(n, 100 + (3 - i) * 300)   # 4 segments, newest still being written (age 100 s)
        w = self.watcher(end_after_s=600, live_every_min=10); made = w.scan(); self.assertEqual(len(made), 1); live = self.jobs[0]; self.assertTrue(live["live"]); d = os.path.join(self.ing, live["ref"][7:])
        self.assertEqual(sorted(os.listdir(d)), names[:3]); self.assertEqual(len(os.listdir(os.path.join(self.rec, KEY))), 4)   # hard links: the recorder's files stay in place
        self.assertEqual(w.scan(), [])   # the 4th segment is still open: no second window yet
        self.now[0] += 3000; self.seg("20261117-202000.ts", 900)   # stream ends; one more segment came in
        w.scan(); final = self.jobs[-1]; self.assertFalse(final["live"]); self.assertEqual(sorted(os.listdir(os.path.join(self.ing, final["ref"][7:]))), [names[3], "20261117-202000.ts"])
        self.assertEqual(os.listdir(os.path.join(self.rec, KEY)), [])

    def test_api_down_is_retried_and_idempotent_name_is_stable(self):
        self.seg("20261117-200000.ts", 2000); self.fail = [RW.ApiError(503, "down"), OSError("net")]; w = self.watcher()
        self.assertEqual(w.scan(), []); self.assertEqual(len(w.state["pending"]), 1); self.assertEqual(w.scan(), []); self.assertEqual(len(w.state["pending"]), 1)
        made = w.scan(); self.assertEqual(len(made), 1); self.assertEqual(w.state["pending"], []); self.assertEqual(self.jobs[0]["idem"], self.jobs[0]["ref"][7:])
        w2 = self.watcher(); self.assertEqual(w2.state["pending"], [])   # state survives a restart (and a half done hand-off survives too)

    def test_pending_survives_restart(self):
        self.seg("20261117-200000.ts", 2000); self.fail = [RW.ApiError(503, "down")]; self.watcher().scan(); w2 = self.watcher(); self.assertEqual(len(w2.state["pending"]), 1); self.assertEqual(len(w2.scan()), 1)

    def test_no_credits_is_dropped_not_retried_forever(self):
        self.seg("20261117-200000.ts", 2000); self.fail = [RW.ApiError(402, {"error": "insufficient_credits"})]; w = self.watcher(); w.scan(); self.assertEqual(w.state["pending"], []); self.assertEqual(self.jobs, [])

    def test_prune_old_ingest_folders(self):
        d = os.path.join(self.ing, "sold-1"); os.makedirs(d); old = self.now[0] - 10 * 86400; os.utime(d, (old, old)); os.makedirs(os.path.join(self.ing, "snew-1")); self.watcher(keep_days=3).scan()
        self.assertFalse(os.path.exists(d)); self.assertTrue(os.path.exists(os.path.join(self.ing, "snew-1")))


class SpoolSubmit(Base):
    def test_spool_job_file_is_idempotent_and_needs_a_known_key(self):
        keys = os.path.join(self.tmp, "keys.json"); json.dump({KEY: {"org": "o_7", "channel": "c_7", "shorts": 4, "long": False}}, open(keys, "w")); spool = os.path.join(self.tmp, "spool"); sub = IW.spool_submit(spool, IW.Keys(path=keys))
        a = sub(KEY, "ingest:sabc-1", 50, False, "sabc-1"); b = sub(KEY, "ingest:sabc-1", 50, False, "sabc-1"); self.assertEqual(a, b); self.assertEqual(len(os.listdir(spool)), 1)
        job = json.load(open(os.path.join(spool, a + ".json"))); self.assertEqual((job["org"], job["outputs"]["shorts"], job["source"]["ref"]), ("o_7", 4, "ingest:sabc-1"))
        with self.assertRaises(RW.ApiError): sub(KEY2, "ingest:x", 5, False, "x")


class AuthHook(Base):
    """the MediaMTX http auth hook: only known keys may publish"""
    def start(self, keys):
        srv = ThreadingHTTPServer(("127.0.0.1", 0), IW.auth_handler(keys, self.log)); threading.Thread(target=srv.serve_forever, daemon=True).start(); self.addCleanup(srv.shutdown); return srv.server_address[1]
    def ask(self, port, **body):
        req = urllib.request.Request("http://127.0.0.1:%d/auth" % port, data=json.dumps(body).encode(), method="POST", headers={"content-type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=5) as r: return r.status
        except urllib.error.HTTPError as e: return e.code
    def test_publish_rules(self):
        kf = os.path.join(self.tmp, "keys.json"); json.dump({KEY: {"org": "o"}}, open(kf, "w")); port = self.start(IW.Keys(path=kf))
        self.assertEqual(self.ask(port, action="publish", path="live/" + KEY, ip="1.2.3.4", protocol="rtmp"), 200)
        self.assertEqual(self.ask(port, action="publish", path="live/" + KEY2, ip="1.2.3.4"), 401)            # unknown key
        self.assertEqual(self.ask(port, action="publish", path="other/" + KEY, ip="1.2.3.4"), 401)            # wrong path prefix
        self.assertEqual(self.ask(port, action="publish", path="live/../" + KEY), 401)
        self.assertEqual(self.ask(port, action="read", path="live/" + KEY, ip="8.8.8.8"), 401)               # nobody watches from outside
        self.assertEqual(self.ask(port, action="read", path="live/" + KEY, ip="127.0.0.1"), 200)
        self.assertEqual(self.ask(port, action="api", path="", ip="127.0.0.1"), 401)                          # anything else is refused
        self.assertEqual(self.ask(port), 401)

    def test_api_keys_lookup_and_outage_keeps_last_answer(self):
        calls = []
        class Api:
            def _call(s, path, body):
                calls.append(body)
                if len(calls) == 1: return {"ok": True, "org": "o", "channel": "c"}
                raise RW.ApiError(503, "down")
        t = [0.0]; k = IW.Keys(api=Api(), clock=lambda: t[0]); self.assertTrue(k.lookup(KEY)); t[0] += 100; self.assertTrue(k.lookup(KEY), "an API outage must not kick a live streamer"); self.assertIsNone(k.lookup("garbage"))
        class Api404:
            def _call(s, path, body): raise RW.ApiError(404, "unknown_key")
        self.assertIsNone(IW.Keys(api=Api404()).lookup(KEY))


if __name__ == "__main__": unittest.main()

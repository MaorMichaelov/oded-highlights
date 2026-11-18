"""End to end on this machine, no network and no secrets: the REAL app/studio.js (node, in-memory KV) <-> render_worker.py (--once drain) <-> the REAL job pipeline in demo mode
(synthetic video, energy transcriber) <-> the REAL 720p preview encode <-> a FAKE GitHub API. Proves: queued job -> claimed -> drafts with preview_url stored in the studio -> a second run finds nothing.
Skipped without node/ffmpeg. About 1-2 minutes. Run: python3 -m unittest tests/test_studio_preview_e2e.py"""
import json, os, shutil, subprocess, sys, tempfile, time, unittest, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import render_worker as RW, preview_publish as PP, job_runner as JR
from test_studio_preview import FakeGithub, REPO

KEY = "wk_local_test_key"; READY = shutil.which("node") and shutil.which("ffmpeg") and shutil.which("ffprobe")


def http(method, url, body=None, headers=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, method=method, headers=dict({"content-type": "application/json"}, **(headers or {})))
    try:
        with urllib.request.urlopen(req, timeout=30) as r: return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e: return e.code, json.loads(e.read() or b"{}")


@unittest.skipUnless(READY, "node and ffmpeg are needed")
class E2E(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="e2e_"); self.srv = subprocess.Popen(["node", os.path.join(HERE, "helpers", "studio_mock_server.mjs")], stdout=subprocess.PIPE, text=True, env=dict(os.environ, MOCK_WORKER_KEY=KEY))
        self.port = int(self.srv.stdout.readline().split()[1]); self.base = "http://127.0.0.1:%d" % self.port
        self.media = JR.make_demo_media(os.path.join(self.tmp, "demo.mp4"), 100)
    def tearDown(self):
        self.srv.terminate(); self.srv.wait(10); shutil.rmtree(self.tmp, ignore_errors=True)
    def worker(self, org, gh, **envs):
        for k, v in dict(WORKER_DEMO="1", WORKER_ALLOW_ANY_PATH="1", WORKER_NO_CLOUD="1", **envs).items(): os.environ[k] = v; self.addCleanup(os.environ.pop, k, None)
        cfg = RW.default_cfg(); cfg.update({"work_dir": os.path.join(self.tmp, "work"), "out_dir": os.path.join(self.tmp, "out"), "poll_s": 1, "retries": 0, "secret": KEY})
        pub = PP.GithubReleasePublisher(REPO, "t" * 20, http=gh, orgs=(org,)); return RW.Worker(RW.StudioApi(self.base, KEY), cfg, RW.Log("text", [KEY]), publisher=pub)

    def test_queued_job_becomes_drafts_with_previews_then_queue_is_empty(self):
        self.assertEqual(http("POST", self.base + "/studio/worker/queue", {})[0], 401)   # the poller needs the key
        st, seed = http("POST", self.base + "/__seed", {"source": {"type": "url", "ref": self.media}, "outputs": {"shorts": 1, "long": False}}); jid, org = seed["job_id"], seed["org_id"]
        self.assertEqual(http("GET", self.base + "/studio/worker/queue", headers={"x-worker-key": KEY})[1]["queued"], 1)
        gh = FakeGithub(); w = self.worker(org, gh); self.assertEqual(w.run_forever(once=True, max_minutes=20), 0)
        job = http("GET", self.base + "/__job/" + jid)[1]; self.assertEqual(job["status"], "draft_ready", job.get("events")); self.assertTrue(job["result"]["drafts"])
        d = job["result"]["drafts"][0]; tag = gh.releases[1]["tag_name"]; self.assertEqual(d["preview_url"], "https://github.com/%s/releases/download/%s/%s" % (REPO, tag, d["local_id"].split("/")[1]))
        (name, size, ctype), = gh.assets["1"][:1]; self.assertEqual(ctype, "video/mp4"); self.assertLess(size, 3_000_000)   # the uploaded asset is the small 720p rendition
        self.assertEqual(http("GET", self.base + "/studio/worker/queue", headers={"x-worker-key": KEY})[1]["queued"], 0)
        t0 = time.time(); w2 = self.worker(org, FakeGithub()); self.assertEqual(w2.run_forever(once=True, max_minutes=15), 0); self.assertLess(time.time() - t0, 10)   # nothing queued: exits at once

    def test_customer_kick_link_is_refused_but_the_job_fails_cleanly_and_credit_is_refunded(self):
        st, seed = http("POST", self.base + "/__seed", {"source": {"type": "vod", "ref": "https://kick.com/video/abc"}}); jid = seed["job_id"]
        w = self.worker("o_someone_else", FakeGithub()); self.assertEqual(w.run_forever(once=True, max_minutes=15), 0)
        job = http("GET", self.base + "/__job/" + jid)[1]; self.assertEqual(job["status"], "failed"); self.assertIn("host_not_allowed", job["events"][-1]["note"]); self.assertEqual(job["credits_held"], 0)


if __name__ == "__main__": unittest.main()

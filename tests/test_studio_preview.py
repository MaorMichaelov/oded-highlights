"""Tests for the Studio preview phase on GitHub Actions: render_worker drain mode (--once / --max-minutes), preview delivery (scripts/preview_publish.py) and the workflow file.
Mocked studio + fake GitHub API: no network, no secrets. Run: python3 -m unittest tests/test_studio_preview.py"""
import io, json, os, shutil, subprocess, sys, tempfile, time, unittest

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import render_worker as RW
import preview_publish as PP
from test_render_worker import FakeStudio, fake_outcome_ok, KEY

REPO = "Owner/some-repo"
HAVE_FFMPEG = shutil.which("ffmpeg") is not None


class FakeGithub:
    """just enough of the GitHub REST API: create release, upload asset, list/delete releases, delete tag ref"""
    def __init__(self): self.releases, self.assets, self.calls, self.deleted_tags, self.fail_upload = {}, {}, [], [], False
    def __call__(self, method, url, headers, data, timeout=0):
        self.calls.append((method, url, headers)); assert headers.get("authorization", "").startswith("Bearer ")
        path = url.split("https://", 1)[1].split("/", 1)[1]
        if method == "POST" and path == "repos/%s/releases" % REPO:
            b = json.loads(data); rid = len(self.releases) + 1; self.releases[rid] = {"id": rid, "tag_name": b["tag_name"], "prerelease": b["prerelease"], "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "upload_url": "https://uploads.github.com/repos/%s/releases/%d/assets{?name,label}" % (REPO, rid)}
            return 201, json.dumps(self.releases[rid]).encode()
        if method == "POST" and url.startswith("https://uploads.github.com/"):
            if self.fail_upload: return 500, b"{}"
            self.assets.setdefault(url.split("/releases/")[1].split("/")[0], []).append((url.split("name=")[1], len(data), headers.get("content-type"))); return 201, b"{}"
        if method == "GET" and path.startswith("repos/%s/releases" % REPO): return 200, json.dumps(list(self.releases.values())).encode()
        if method == "DELETE" and "/releases/" in path: self.releases.pop(int(path.rsplit("/", 1)[1]), None); return 204, b""
        if method == "DELETE" and "/git/refs/tags/" in path: self.deleted_tags.append(path.rsplit("/", 1)[1]); return 204, b""
        return 404, b"{}"


def fake_encode(src, dst): open(dst, "wb").write(b"small" * 10)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="sp_"); self.studio = FakeStudio(); self.logbuf = io.StringIO(); self.gh = FakeGithub()
        self.cfg = RW.default_cfg({}); self.cfg.update({"work_dir": os.path.join(self.tmp, "work"), "out_dir": os.path.join(self.tmp, "out"), "poll_s": 1, "backoff_s": 0, "progress_min_interval_s": 0, "secret": KEY, "grace_s": 2, "min_claim_s": 0})
        self.log = RW.Log("json", [KEY], self.logbuf)
    def tearDown(self): shutil.rmtree(self.tmp, ignore_errors=True)
    def worker(self, runner, publisher=None, **cfg):
        self.cfg.update(cfg); api = RW.StudioApi("https://studio.test", KEY, transport=self.studio, retries=2, sleep=lambda s: None)
        return RW.Worker(api, self.cfg, self.log, runner=runner, sleep=lambda s: time.sleep(min(s, 0.05)), publisher=publisher)
    def logs(self): return [json.loads(l) for l in self.logbuf.getvalue().splitlines() if l.strip()]


class Drain(Base):
    def test_once_processes_every_queued_job_then_exits(self):
        for i in range(3): self.studio.add_job("j_d%d" % i)
        w = self.worker(fake_outcome_ok(1), concurrency=1); t0 = time.time(); self.assertEqual(w.run_forever(once=True), 0)
        self.assertLess(time.time() - t0, 20); self.assertEqual([self.studio.jobs["j_d%d" % i]["status"] for i in range(3)], ["draft_ready"] * 3); self.assertEqual(self.studio.queue, [])
        self.assertEqual(sum(1 for l in self.logs() if l["event"] == "job_done"), 3)

    def test_once_with_empty_queue_exits_immediately(self):
        w = self.worker(fake_outcome_ok(1)); t0 = time.time(); self.assertEqual(w.run_forever(once=True), 0); self.assertLess(time.time() - t0, 3)
        self.assertEqual([r for r in self.studio.requests if r[1].endswith("/claim")].__len__(), 1)

    def test_once_with_concurrency_waits_for_running_jobs(self):
        for i in range(2): self.studio.add_job("j_c%d" % i)
        def slow(job, workdir, cfg, on_progress, log, stop): time.sleep(0.4); return fake_outcome_ok(1)(job, workdir, cfg, on_progress, log, stop)
        w = self.worker(slow, concurrency=2); self.assertEqual(w.run_forever(once=True), 0)
        self.assertTrue(all(self.studio.jobs["j_c%d" % i]["status"] == "draft_ready" for i in range(2)))

    def test_once_gives_up_when_the_api_is_down(self):
        self.studio.fail_next = ["net"] * 500
        w = self.worker(fake_outcome_ok(1)); self.assertEqual(w.run_forever(once=True), 0); self.assertTrue(any(l["event"] == "claim_failed" for l in self.logs()))

    def test_once_wrong_key_exits_5(self):
        w = self.worker(fake_outcome_ok(1)); w.api.key = "wrong"; self.assertEqual(w.run_forever(once=True), 5)

    def test_budget_too_small_claims_nothing(self):
        self.studio.add_job("j_b0"); w = self.worker(fake_outcome_ok(1), min_claim_s=300); self.assertEqual(w.run_forever(once=True, max_minutes=1), 0)
        self.assertEqual(len(self.studio.queue), 1); self.assertEqual(self.studio.jobs["j_b0"]["status"], "queued"); self.assertTrue(any(l["event"] == "budget_reached" for l in self.logs()))

    def test_deadline_kills_a_running_job_and_reports_it_failed(self):
        p = os.path.join(self.tmp, "slow_runner.py"); open(p, "w").write("import time\nprint('PROGRESS {}', flush=True)\ntime.sleep(120)\n"); old = RW.RUNNER; RW.RUNNER = p; self.addCleanup(lambda: setattr(RW, "RUNNER", old))
        self.studio.add_job("j_k0"); self.studio.add_job("j_k1"); w = self.worker(RW.run_subprocess, retries=3); t0 = time.time(); self.assertEqual(w.run_forever(once=True, max_minutes=0.05), 0)   # 3 s budget
        self.assertLess(time.time() - t0, 40); j = self.studio.jobs["j_k0"]; self.assertEqual(j["status"], "failed"); self.assertEqual(self.studio.jobs["j_k1"]["status"], "queued")   # killed job failed (credit refunded by the studio), the next one never started
        self.assertTrue(any(l["event"] in ("deadline_reached", "budget_reached") for l in self.logs()))

    def test_child_never_sees_worker_key_or_github_token(self):
        p = os.path.join(self.tmp, "env_runner.py"); open(p, "w").write("import os, json\nprint('PROGRESS ' + json.dumps({'message': 'k=%s t=%s g=%s' % (os.environ.get('STUDIO_WORKER_KEY', 'absent'), os.environ.get('GITHUB_TOKEN', 'absent'), os.environ.get('GH_TOKEN', 'absent'))}))\n")
        old = RW.RUNNER; RW.RUNNER = p; self.addCleanup(lambda: setattr(RW, "RUNNER", old))
        for k in ("STUDIO_WORKER_KEY", "GITHUB_TOKEN", "GH_TOKEN"): os.environ[k] = "secretvalue123"; self.addCleanup(lambda k=k: os.environ.pop(k, None))
        seen = []; out = RW.run_subprocess({"id": "j_e"}, os.path.join(self.tmp, "w"), self.cfg, seen.append, self.log, __import__("threading").Event())
        self.assertEqual(seen[0]["message"], "k=absent t=absent g=absent")


class Previews(Base):
    def pub(self, orgs=("o_1",), encode=fake_encode): return PP.GithubReleasePublisher(REPO, "ghs_faketoken0123456789", http=self.gh, encode=encode, orgs=orgs, log=lambda ev, level="info", **kw: self.log(ev, level, **kw))

    def test_drafts_get_a_preview_url_that_the_studio_stores(self):
        self.studio.add_job("j_p0"); w = self.worker(fake_outcome_ok(2), publisher=self.pub()); w.run_forever(once=True)
        d = self.studio.jobs["j_p0"]["drafts"]; self.assertEqual(len(d), 2); tag = self.gh.releases[1]["tag_name"]; self.assertRegex(tag, r"^studio-preview-j_p0-[0-9a-f]{8}$"); self.assertTrue(self.gh.releases[1]["prerelease"])
        self.assertEqual([x["preview_url"] for x in d], ["https://github.com/%s/releases/download/%s/short_%d.mp4" % (REPO, tag, i) for i in range(2)])
        self.assertEqual(sorted(a[0] for a in self.gh.assets["1"]), ["short_0.mp4", "short_1.mp4"]); self.assertTrue(all(a[2] == "video/mp4" for a in self.gh.assets["1"]))
        out = os.path.join(self.cfg["out_dir"], "j_p0"); self.assertFalse([n for n in os.listdir(out) if n.startswith(".preview_")], "temporary renditions must be removed")
        self.assertEqual(json.load(open(os.path.join(out, "manifest.json")))["drafts"][0]["preview_url"], d[0]["preview_url"])
        self.assertNotIn("ghs_faketoken", self.logbuf.getvalue())

    def test_url_shape_is_accepted_by_the_studio_validator(self):
        import re
        rx = re.compile(r"^https://github\.com/[A-Za-z0-9_.-]{1,60}/[A-Za-z0-9_.-]{1,100}/releases/download/[A-Za-z0-9._-]{1,120}/[A-Za-z0-9._-]{1,120}\.mp4$")   # same pattern as previewUrl() in app/studio.js
        self.studio.add_job("j_p1"); self.worker(fake_outcome_ok(1), publisher=self.pub()).run_forever(once=True); self.assertRegex(self.studio.jobs["j_p1"]["drafts"][0]["preview_url"], rx)
        src = open(os.path.join(HERE, "..", "app", "studio.js"), encoding="utf-8").read(); self.assertIn(r"/^https:\/\/github\.com\/[A-Za-z0-9_.-]{1,60}\/[A-Za-z0-9_.-]{1,100}\/releases\/download\/[A-Za-z0-9._-]{1,120}\/[A-Za-z0-9._-]{1,120}\.mp4$/", src)

    def test_org_not_listed_gets_no_preview_and_no_github_call(self):
        self.studio.add_job("j_p2"); self.worker(fake_outcome_ok(1), publisher=self.pub(orgs=("o_other",))).run_forever(once=True)
        self.assertEqual(self.studio.jobs["j_p2"]["status"], "draft_ready"); self.assertEqual(self.studio.jobs["j_p2"]["drafts"][0]["preview_url"], ""); self.assertEqual(self.gh.calls, [])

    def test_star_means_every_org(self):
        self.studio.add_job("j_p3"); self.worker(fake_outcome_ok(1), publisher=self.pub(orgs=("*",))).run_forever(once=True); self.assertTrue(self.studio.jobs["j_p3"]["drafts"][0]["preview_url"])

    def test_upload_failure_never_fails_the_job_and_leaves_no_empty_release(self):
        self.gh.fail_upload = True; self.studio.add_job("j_p4"); self.worker(fake_outcome_ok(1), publisher=self.pub()).run_forever(once=True)
        j = self.studio.jobs["j_p4"]; self.assertEqual(j["status"], "draft_ready"); self.assertEqual(j["drafts"][0]["preview_url"], ""); self.assertEqual(self.gh.releases, {}); self.assertTrue(any(l["event"] == "preview_failed" for l in self.logs()))

    def test_github_outage_never_fails_the_job(self):
        def down(*a, **k): raise OSError("github down")
        p = PP.GithubReleasePublisher(REPO, "t" * 20, http=down, encode=fake_encode, orgs=("*",)); self.studio.add_job("j_p5"); self.worker(fake_outcome_ok(1), publisher=p).run_forever(once=True)
        self.assertEqual(self.studio.jobs["j_p5"]["status"], "draft_ready"); self.assertTrue(any(l["event"] == "preview_failed" for l in self.logs()))

    def test_from_env(self):
        base = {"STUDIO_PREVIEW_PUBLISH": "github-release", "GITHUB_TOKEN": "t" * 20, "GITHUB_REPOSITORY": REPO, "WORKER_TRUSTED_ORGS": "o_1"}
        self.assertIsNotNone(PP.from_env(base)); self.assertEqual(PP.from_env(base).orgs, {"o_1"}); self.assertEqual(PP.from_env(dict(base, WORKER_PREVIEW_ORGS="o_2, o_3")).orgs, {"o_2", "o_3"})
        for drop in ("STUDIO_PREVIEW_PUBLISH", "GITHUB_TOKEN", "GITHUB_REPOSITORY", "WORKER_TRUSTED_ORGS"): self.assertIsNone(PP.from_env({k: v for k, v in base.items() if k != drop}), drop)   # off unless fully configured (no orgs = no public previews)
        with self.assertRaises(ValueError): PP.GithubReleasePublisher("not a repo", "t")

    def test_cleanup_deletes_only_old_preview_releases(self):
        old = "2026-01-01T00:00:00Z"; now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.gh.releases = {1: {"id": 1, "tag_name": "studio-preview-j_x-aaaa1111", "created_at": old}, 2: {"id": 2, "tag_name": "studio-preview-j_y-bbbb2222", "created_at": now}, 3: {"id": 3, "tag_name": "v1.0", "created_at": old}}
        self.assertEqual(PP.cleanup(REPO, "t" * 20, 7, http=self.gh), 1); self.assertEqual(sorted(self.gh.releases), [2, 3]); self.assertEqual(self.gh.deleted_tags, ["studio-preview-j_x-aaaa1111"])

    def test_preview_command_is_720p_small_and_capped(self):
        c = PP.preview_args("in.mp4", "out.mp4", max_s=120); j = " ".join(c)
        for want in ("-maxrate 900k", "-b:a 64k", "-movflags +faststart", "-t 120", "libx264"): self.assertIn(want, j)
        self.assertIn("720", c[c.index("-vf") + 1])

    @unittest.skipUnless(HAVE_FFMPEG, "ffmpeg missing")
    def test_real_encode_makes_a_small_720p_file(self):
        src = os.path.join(self.tmp, "in.mp4")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=s=1080x1920:r=30:d=4", "-f", "lavfi", "-i", "sine=f=400:d=4", "-c:v", "libx264", "-c:a", "aac", "-shortest", src], check=True)
        dst = os.path.join(self.tmp, "out.mp4"); PP.make_preview(src, dst, 300)
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", dst], capture_output=True, text=True); self.assertEqual(r.stdout.strip(), "720,1280")
        self.assertLess(os.path.getsize(dst), os.path.getsize(src))


class WorkflowFile(unittest.TestCase):
    """static checks of .github/workflows/studio-worker.yml (the real run needs the owner's secrets, which this repo deliberately does not have)"""
    def setUp(self):
        import yaml; self.path = os.path.join(HERE, "..", ".github", "workflows", "studio-worker.yml"); self.text = open(self.path, encoding="utf-8").read(); self.y = yaml.safe_load(self.text)
    def test_triggers_and_concurrency(self):
        on = self.y.get("on") or self.y.get(True); self.assertIn("schedule", on); self.assertIn("workflow_dispatch", on); self.assertRegex(on["schedule"][0]["cron"], r"^\*/5 ")
        self.assertEqual(self.y["concurrency"]["cancel-in-progress"], False); self.assertTrue(self.y["concurrency"]["group"])
    def test_permissions_are_minimal(self):
        self.assertEqual(self.y["permissions"], {}); jobs = self.y["jobs"]
        self.assertEqual(jobs["check"].get("permissions"), {"contents": "read"}); self.assertEqual(jobs["render"]["permissions"], {"contents": "write"})   # write only where the preview release is created
    def test_secrets_only_via_env_and_never_inline(self):
        import re
        for m in re.finditer(r"\$\{\{[^}]*\}\}", self.text):
            expr = m.group(0)
            if "secrets." in expr: line = [l for l in self.text.splitlines() if expr in l][0]; self.assertRegex(line, r"^\s+[A-Z_]+: \$\{\{", "secrets are only assigned to env vars: " + line)
        self.assertNotRegex(self.text, r"run:[^\n]*\$\{\{")   # no expression pasted straight into a shell line
        self.assertNotIn("set -x", self.text); self.assertNotIn("echo $STUDIO", self.text)
    def test_missing_secrets_exit_zero_with_a_clear_message(self):
        self.assertIn("secrets not configured", self.text); self.assertIn("exit 0", self.text)

    def run_check(self, env, handler=None):
        """run the real shell of the 'check' job against a local mock of /studio/worker/queue; returns (exit code, combined output, GITHUB_OUTPUT dict)"""
        import http.server, threading
        script = [st for st in self.y["jobs"]["check"]["steps"] if st.get("id") == "peek"][0]["run"]; seen = {}
        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(h):
                seen["key"] = h.headers.get("x-worker-key"); seen["path"] = h.path; code, body = handler(h.headers) if handler else (200, b'{"queued": 2}')
                h.send_response(code); h.send_header("content-type", "application/json"); h.end_headers(); h.wfile.write(body)
            def log_message(h, *a): pass
        srv = http.server.HTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start(); self.addCleanup(srv.shutdown)
        tmp = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, tmp, True); go = os.path.join(tmp, "out"); e = {"PATH": os.environ["PATH"], "GITHUB_OUTPUT": go, "EVENT": "schedule"}
        e.update({k: v.replace("PORT", str(srv.server_port)) for k, v in env.items()})
        r = subprocess.run(["bash", "-e", "-c", script], env=e, capture_output=True, text=True, timeout=60)
        o = dict(l.split("=", 1) for l in open(go).read().split()) if os.path.exists(go) else {}
        return r.returncode, r.stdout + r.stderr, o, seen
    def test_check_job_shell_no_secrets_is_green_and_clear(self):
        rc, out, o, seen = self.run_check({}); self.assertEqual(rc, 0); self.assertIn("secrets not configured", out); self.assertEqual(o["queued"], "0"); self.assertEqual(seen, {})
        rc, out, o, _ = self.run_check({"STUDIO_URL": "http://127.0.0.1:PORT"}); self.assertEqual((rc, o["queued"]), (0, "0")); self.assertIn("secrets not configured", out)
    def test_check_job_shell_reads_the_queue_and_never_prints_the_key(self):
        rc, out, o, seen = self.run_check({"STUDIO_URL": "http://127.0.0.1:PORT/", "STUDIO_WORKER_KEY": "wk_supersecret_value"}); self.assertEqual(rc, 0); self.assertEqual(o["queued"], "2"); self.assertEqual(seen["key"], "wk_supersecret_value"); self.assertEqual(seen["path"], "/studio/worker/queue")
        self.assertNotIn("wk_supersecret_value", out); self.assertIn("2 job(s) queued", out)
    def test_check_job_shell_bad_key_and_outage_stay_green_on_schedule_red_on_manual_run(self):
        env = {"STUDIO_URL": "http://127.0.0.1:PORT", "STUDIO_WORKER_KEY": "wk_x"}
        rc, out, o, _ = self.run_check(env, lambda h: (401, b'{"error":"unauthorized"}')); self.assertEqual((rc, o["queued"]), (0, "0")); self.assertIn("rejected the worker key", out)
        rc, out, o, _ = self.run_check(dict(env, EVENT="workflow_dispatch"), lambda h: (401, b"{}")); self.assertEqual(rc, 1)
        rc, out, o, _ = self.run_check(env, lambda h: (503, b"oops")); self.assertEqual((rc, o["queued"]), (0, "0"))
        rc, out, o, _ = self.run_check(env, lambda h: (200, b"<html>not json</html>")); self.assertEqual((rc, o["queued"]), (0, "0"))
        rc, out, o, _ = self.run_check({"STUDIO_URL": "https://evil.example/path?x=1", "STUDIO_WORKER_KEY": "wk_x"}); self.assertEqual((rc, o["queued"]), (0, "0")); self.assertIn("STUDIO_URL must look like", out)
    def test_check_job_shell_cleanup_flag_only_on_request(self):
        env = {"STUDIO_URL": "http://127.0.0.1:PORT", "STUDIO_WORKER_KEY": "wk_x", "EVENT": "workflow_dispatch", "IN_CLEANUP": "true"}
        rc, out, o, _ = self.run_check(env); self.assertEqual(o["cleanup"], "true"); rc, out, o, _ = self.run_check(dict(env, IN_CLEANUP="false")); self.assertEqual(o["cleanup"], "false")
    def test_checkout_is_read_only_and_pinned_major(self):
        self.assertIn("actions/checkout@v4", self.text); self.assertIn("persist-credentials: false", self.text)


if __name__ == "__main__": unittest.main()

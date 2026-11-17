"""Unit tests for scripts/yt_upload_customer.py. Every network call goes through a fake transport: nothing here can reach Google or the Worker.
Run: python3 -m unittest tests/test_yt_upload_customer.py   (or: python3 tests/test_yt_upload_customer.py)"""
import json, os, re, sys, tempfile, unittest, warnings, datetime as dt
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import yt_upload_customer as U

FAKE_AT = "ya29.FAKE-ACCESS-TOKEN"
BASE = "https://studio.test"
CH = "UCfake1"


def wfile(path, data, mode="wb"):
    with open(path, mode) as f: f.write(data)


def wjson(path, obj):
    with open(path, "w", encoding="utf-8") as f: json.dump(obj, f, ensure_ascii=False)


class World:
    """Scripted fake of the Worker broker + Google (token, channels.list, resumable upload, thumbnails)."""
    def __init__(self, size, policy=None, channel_of_token=CH, broker_channel=CH):
        self.size, self.calls, self.reports, self.tokens = size, [], [], []
        self.policy = policy or {"mode": "private", "privacy": "private", "publish_at": None, "downgraded": None}
        self.channel_of_token, self.broker_channel = channel_of_token, broker_channel
        self.broker_status, self.broker_body = 200, None            # override to simulate 409 / 429
        self.init_script = []                                       # list of (status, body) consumed by the resumable init
        self.put_script = []                                        # list of 'net' | (status, body) consumed by chunk PUTs
        self.received = 0; self.session = "https://upload.test/session/abc"; self.video_id = "vid_FAKE1"; self.thumb_status = 200
        self.ranges = []; self.init_bodies = []; self.expired_tokens = 0

    def __call__(self, method, url, headers=None, body=None, timeout=60):
        headers = {k.lower(): v for k, v in (headers or {}).items()}; self.calls.append((method, url, headers, body))
        J = lambda o, s=200, h=None: (s, h or {}, json.dumps(o).encode())
        if url == BASE + "/internal/yt/token":
            req = json.loads(body); self.tokens.append(req); assert headers.get("x-worker-key") == "wk_fake"
            if self.broker_status != 200: return J(self.broker_body or {}, self.broker_status)
            return J({"access_token": FAKE_AT, "channel_id": self.broker_channel, "channel_title": "Fake Channel", "policy": self.policy, "reserved_units": 0 if req.get("renew") else 1600})
        if url == BASE + "/internal/yt/report": self.reports.append(json.loads(body)); return J({"ok": True})
        assert headers.get("authorization") == "Bearer " + FAKE_AT, "every Google call carries the broker's access token"
        if url.startswith("https://www.googleapis.com/youtube/v3/channels"): return J({"items": [{"id": self.channel_of_token}]})
        if url.startswith("https://www.googleapis.com/upload/youtube/v3/videos"):
            self.init_bodies.append(json.loads(body))
            if self.init_script: st, b = self.init_script.pop(0); return J(b, st)
            return 200, {"location": self.session}, b""
        if url == self.session:
            if headers.get("content-range", "").startswith("bytes */"):               # status query
                return (308, {"range": f"bytes=0-{self.received - 1}"}, b"") if self.received else (308, {}, b"")
            if self.put_script:
                act = self.put_script.pop(0)
                if act == "net": raise U.NetError("ConnectionResetError")
                if act == "401": self.expired_tokens += 1; return J({"error": {"code": 401, "errors": [{"reason": "authError"}]}}, 401)
                st, b = act; return J(b, st)
            m = re.match(r"bytes (\d+)-(\d+)/(\d+)", headers["content-range"]); a, z, tot = map(int, m.groups()); assert a == self.received, f"gap: server has {self.received}, got {a}"; assert len(body) == z - a + 1
            self.received = z + 1; self.ranges.append((a, z))
            if self.received >= tot: return J({"id": self.video_id, "status": {"uploadStatus": "uploaded", "privacyStatus": "private"}}, 200)
            return 308, {"range": f"bytes=0-{self.received - 1}"}, b""
        if url.startswith("https://www.googleapis.com/upload/youtube/v3/thumbnails/set"): return J({}, self.thumb_status) if self.thumb_status == 200 else J({"error": {"errors": [{"reason": "forbidden"}]}}, self.thumb_status)
        raise AssertionError("unexpected url " + url)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.d = self.tmp.name; self.logs = []
        self.video = os.path.join(self.d, "v.mp4"); wfile(self.video, os.urandom(700 * 1024))      # 700 KiB -> 3 chunks of 256 KiB
        self.meta = os.path.join(self.d, "m.json"); wjson(self.meta, {"title": "כותרת בדיקה", "description": "d", "tags": ["a", "b"]})
        self.thumb = os.path.join(self.d, "t.jpg"); wfile(self.thumb, b"\xff\xd8" + os.urandom(1000))
        self.env = {"STUDIO_URL": BASE, "STUDIO_WORKER_KEY": "wk_fake", "YT_UPLOAD_SESSION_DIR": os.path.join(self.d, "sess"), "YT_CHUNK_MB": "0.25"}
        self.hold = os.path.join(self.d, "HOLD"); self.sleeps = []
        self.world = World(os.path.getsize(self.video))

    def tearDown(self): self.tmp.cleanup()

    def run_main(self, extra=None, world=None, env=None, args=None):
        w = world or self.world
        argv = args or [self.video, self.meta] + ([self.thumb] if extra == "thumb" else []) + ["--org", "o_1", "--channel", "c_1", "--job", "j_1"]
        if isinstance(extra, list): argv += extra
        return U.main(argv, env=self.env if env is None else env, http=w, sleep=self.sleeps.append, hold_path=self.hold, log=lambda *a: self.logs.append(" ".join(map(str, a))))

    def out(self): return "\n".join(self.logs)


class HappyPath(Base):
    def test_private_upload_chunked_and_reported(self):
        self.assertEqual(self.run_main("thumb"), U.OK)
        w = self.world; self.assertEqual(w.ranges, [(0, 262143), (262144, 524287), (524288, 716799)])
        self.assertEqual(w.init_bodies[0]["status"]["privacyStatus"], "private"); self.assertNotIn("publishAt", w.init_bodies[0]["status"]); self.assertFalse(w.init_bodies[0]["status"]["selfDeclaredMadeForKids"])
        self.assertEqual(w.init_bodies[0]["snippet"]["title"], "כותרת בדיקה")
        self.assertEqual(w.reports[0]["event"], "uploaded"); self.assertEqual(w.reports[0]["video_id"], "vid_FAKE1"); self.assertEqual(w.reports[0]["job_id"], "j_1")
        self.assertEqual(w.tokens[0], {"org_id": "o_1", "channel_id": "c_1", "job_id": "j_1", "thumbnail": True, "renew": False})
        self.assertIn("VIDEO_ID vid_FAKE1", self.out()); self.assertIn("thumbnail: set", self.out()); self.assertNotIn(FAKE_AT, self.out()); self.assertNotIn("wk_fake", self.out())
        self.assertEqual(os.listdir(self.env["YT_UPLOAD_SESSION_DIR"]), [], "session file removed after success")

    def test_channel_enforced_before_any_upload(self):
        w = World(self.world.size, channel_of_token="UCwrong"); self.assertEqual(self.run_main(world=w), U.WRONG_CHANNEL)
        self.assertFalse([c for c in w.calls if "uploadType=resumable" in c[1]], "nothing uploaded to the wrong channel"); self.assertEqual(w.reports[0]["event"], "failed"); self.assertIn("REFUSED", self.out())

    def test_expect_channel_flag(self):
        self.assertEqual(self.run_main(["--expect-channel", "UCsomeoneelse"]), U.WRONG_CHANNEL)
        self.assertEqual(self.run_main(["--expect-channel", CH], world=World(self.world.size)), U.OK)

    def test_thumbnail_failures_are_not_fatal(self):
        self.world.thumb_status = 403; self.assertEqual(self.run_main("thumb"), U.OK); self.assertIn("thumbnail: not set", self.out())
        big = os.path.join(self.d, "big.jpg"); wfile(big, b"0" * (2 * 1024 * 1024 + 1)); self.logs.clear()
        w = World(self.world.size); self.assertEqual(U.main([self.video, self.meta, big, "--org", "o_1", "--job", "j_1"], env=self.env, http=w, sleep=self.sleeps.append, hold_path=self.hold, log=lambda *a: self.logs.append(" ".join(map(str, a)))), U.OK)
        self.assertFalse([c for c in w.calls if "thumbnails/set" in c[1]]); self.assertEqual(w.tokens[0].get("channel_id"), None)


class Policy(Base):
    def test_meta_cannot_make_the_video_public_or_scheduled(self):
        wjson(self.meta, {"title": "t", "privacy": "public", "publishAt": "2030-01-01T00:00:00Z"}); self.assertEqual(self.run_main(), U.OK)
        st = self.world.init_bodies[0]["status"]; self.assertEqual(st["privacyStatus"], "private"); self.assertNotIn("publishAt", st); self.assertIn("meta privacy 'public' ignored", self.out()); self.assertIn("meta publishAt ignored", self.out())

    def test_schedule_policy_sets_publishAt_and_stays_private(self):
        w = World(self.world.size, policy={"mode": "schedule", "privacy": "private", "publish_at": "2026-11-20T16:00:00.000Z", "downgraded": None}); self.assertEqual(self.run_main(world=w), U.OK)
        st = w.init_bodies[0]["status"]; self.assertEqual(st["privacyStatus"], "private"); self.assertEqual(st["publishAt"], "2026-11-20T16:00:00.000Z"); self.assertEqual(w.reports[0]["publish_at"], "2026-11-20T16:00:00.000Z")

    def test_public_needs_policy_and_meta(self):
        pol = {"mode": "public", "privacy": "public", "publish_at": None, "downgraded": None}
        w = World(self.world.size, policy=pol); self.assertEqual(self.run_main(world=w), U.OK); self.assertEqual(w.init_bodies[0]["status"]["privacyStatus"], "private", "policy public but META did not ask: private")
        wjson(self.meta, {"title": "t", "privacy": "public"}); w = World(self.world.size, policy=pol); self.assertEqual(self.run_main(world=w), U.OK); self.assertEqual(w.init_bodies[0]["status"]["privacyStatus"], "public")

    def test_downgrade_is_logged(self):
        w = World(self.world.size, policy={"mode": "schedule", "privacy": "private", "publish_at": None, "downgraded": "project_not_audited"}); self.run_main(world=w); self.assertIn("project_not_audited", self.out())

    def test_resolve_status_and_body(self):
        self.assertEqual(U.resolve_status({}, {}), ("private", None, []))
        self.assertEqual(U.resolve_status({"privacy": "unlisted"}, {"privacy": "private"})[0], "private")
        b = U.build_body({"title": "x" * 300, "description": "d" * 6000, "tags": ["ok"] + ["t" * 100] * 10, "lang": "en"}, "private", None)
        self.assertEqual(len(b["snippet"]["title"]), 100); self.assertEqual(len(b["snippet"]["description"]), 4900); self.assertLessEqual(sum(len(t) + 1 for t in b["snippet"]["tags"]), 480); self.assertEqual(b["snippet"]["defaultLanguage"], "en")
        self.assertEqual(U.parse_range_end({"range": "bytes=0-524287"}), 524288); self.assertEqual(U.parse_range_end({}), 0)


class Guards(Base):
    def test_upload_hold(self):
        wfile(self.hold, (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ"), "w"); self.assertEqual(self.run_main(), U.HOLD)
        self.assertEqual(self.world.calls, [], "no network call at all while the hold is active")
        wfile(self.hold, (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"), "w"); self.assertEqual(self.run_main(world=World(self.world.size)), U.OK)
        wfile(self.hold, "garbage", "w"); self.assertEqual(self.run_main(world=World(self.world.size)), U.OK, "an unreadable hold file does not block (same as yt_upload.py)")

    def test_real_hold_file_in_repo_is_parsed(self):
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "state", "UPLOAD_HOLD")
        if os.path.exists(p): self.assertIsInstance(U.hold_active(p, dt.datetime(2000, 1, 1, tzinfo=dt.timezone.utc)), dt.datetime)

    def test_needs_reconnect(self):
        self.world.broker_status, self.world.broker_body = 409, {"error": "needs_reconnect", "channel_title": "Fake Channel"}; self.assertEqual(self.run_main(), U.RECONNECT); self.assertIn("reconnect", self.out())

    def test_broker_quota_and_customer_limit(self):
        self.world.broker_status, self.world.broker_body = 429, {"error": "quota_exhausted", "retry_after_s": 3600, "reset_at": "2026-11-18T08:00:00.000Z"}; self.assertEqual(self.run_main(), U.QUOTA); self.assertIn("3600", self.out())
        self.assertFalse([c for c in self.world.calls if "googleapis" in c[1]])

    def test_broker_errors(self):
        self.world.broker_status, self.world.broker_body = 401, {"error": "unauthorized"}; self.assertEqual(self.run_main(), U.ERR)
        self.world.broker_status, self.world.broker_body = 403, {"error": "job_mismatch"}; self.assertEqual(self.run_main(), U.ERR)

    def test_usage_and_input_errors(self):
        self.assertEqual(self.run_main(env={}), U.USAGE); self.assertEqual(U.main([self.video], env=self.env, http=self.world, log=lambda *a: None), U.USAGE)
        self.assertEqual(self.run_main(args=[self.video, os.path.join(self.d, "nope.json"), "--org", "o", "--job", "j"]), U.BAD_INPUT)
        wjson(self.meta, {"title": " "}); self.assertEqual(self.run_main(), U.BAD_INPUT)
        wfile(self.video, b""); wjson(self.meta, {"title": "t"}); self.assertEqual(self.run_main(), U.BAD_INPUT)
        self.assertEqual(self.world.reports, [])


class QuotaAndRetry(Base):
    def test_youtube_quota_exceeded_at_init_is_reported(self):
        self.world.init_script = [(403, {"error": {"code": 403, "errors": [{"reason": "quotaExceeded"}]}})]; self.assertEqual(self.run_main(), U.QUOTA)
        self.assertEqual(self.world.reports[0]["event"], "quota_exceeded"); self.assertEqual(self.world.reports[0]["units"], 1600); self.assertEqual(self.sleeps, [], "quota is not retried")

    def test_upload_limit_exceeded_mid_upload(self):
        self.world.put_script = [(403, {"error": {"errors": [{"reason": "uploadLimitExceeded"}]}})]; self.assertEqual(self.run_main(), U.QUOTA); self.assertEqual(self.world.reports[0]["event"], "quota_exceeded")

    def test_init_retries_transient_errors_with_backoff(self):
        self.world.init_script = [(503, {}), (403, {"error": {"errors": [{"reason": "rateLimitExceeded"}]}})]; self.assertEqual(self.run_main(), U.OK)
        self.assertEqual(len(self.sleeps), 2); self.assertTrue(2 <= self.sleeps[0] < 4 and 4 <= self.sleeps[1] < 6, self.sleeps)

    def test_unverified_app_forbidden_is_fatal_not_retried(self):
        self.world.init_script = [(403, {"error": {"errors": [{"reason": "forbidden"}]}})]; self.assertEqual(self.run_main(), U.ERR); self.assertEqual(self.sleeps, [])

    def test_network_drop_resumes_from_server_offset(self):
        self.world.put_script = [None]                       # first chunk goes through
        self.world.put_script = []
        orig = self.world.__call__; state = {"n": 0}
        def flaky(method, url, headers=None, body=None, timeout=60):
            if url == self.world.session and method == "PUT" and not (headers or {}).get("content-range", "").startswith("bytes */"):
                state["n"] += 1
                if state["n"] == 2: raise U.NetError("ConnectionResetError")     # drop while sending chunk 2 (server has chunk 1 only)
                if state["n"] == 3: return 503, {}, b"{}"
            return orig(method, url, headers, body, timeout)
        self.assertEqual(self.run_main(world=type("W", (), {"__call__": staticmethod(flaky), "reports": self.world.reports, "init_bodies": self.world.init_bodies, "calls": self.world.calls, "tokens": self.world.tokens})()), U.OK)
        self.assertEqual(self.world.ranges, [(0, 262143), (262144, 524287), (524288, 716799)], "no byte sent twice, none skipped"); self.assertEqual(len(self.world.init_bodies), 1, "one resumable session, one video")
        self.assertEqual(len(self.sleeps), 2)

    def test_crash_then_rerun_resumes_same_session_without_new_reservation(self):
        w = self.world; w.put_script = ["net"] * 12                                  # every PUT fails: gives up after max_failures
        self.assertEqual(self.run_main(), U.ERR); self.assertIn("rerun to resume", self.out()); sess_files = os.listdir(self.env["YT_UPLOAD_SESSION_DIR"]); self.assertEqual(len(sess_files), 1)
        w.put_script = []; w.tokens.clear(); w.init_bodies.clear(); self.assertEqual(self.run_main(), U.OK)
        self.assertEqual(w.init_bodies, [], "second run did not create a new upload"); self.assertTrue(w.tokens[0]["renew"], "resume does not reserve quota again"); self.assertEqual(w.ranges[-1][1], 716799)
        self.assertEqual(w.video_id, "vid_FAKE1")

    def test_expired_session_is_replaced(self):
        self.assertEqual(self.run_main(), U.OK)
        w = World(self.world.size); w.put_script = ["net"] * 12; self.run_main(world=w); w2 = World(self.world.size)
        orig = w2.__call__
        def gone(method, url, headers=None, body=None, timeout=60):
            if method == "PUT" and url == w2.session and (headers or {}).get("content-range", "").startswith("bytes */") and not getattr(gone, "done", False): gone.done = True; return 404, {}, b"{}"
            return orig(method, url, headers, body, timeout)
        self.assertEqual(self.run_main(world=type("W", (), {"__call__": staticmethod(gone), "reports": w2.reports, "init_bodies": w2.init_bodies, "calls": w2.calls, "tokens": w2.tokens})()), U.OK); self.assertEqual(len(w2.init_bodies), 1, "a dead session triggers a fresh init")

    def test_token_expiry_mid_upload_renews_without_reservation(self):
        self.world.put_script = ["401"]; self.assertEqual(self.run_main(), U.OK); self.assertEqual([t["renew"] for t in self.world.tokens], [False, True])


if __name__ == "__main__":
    unittest.main()

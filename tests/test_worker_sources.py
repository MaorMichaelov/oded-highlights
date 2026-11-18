"""Tests for scripts/worker_sources.py (source resolving + safety) and the pure parts of scripts/job_runner.py. ffmpeg is used for tiny generated clips; no network.
Run: python3 -m unittest tests/test_worker_sources.py"""
import json, os, shutil, subprocess, sys, tempfile, unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import worker_sources as WS
import job_runner as JR

HAVE_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def make_clip(path, seconds=4, audio=True, ext_args=()):
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=s=320x180:r=15:d=%d" % seconds] + (["-f", "lavfi", "-i", "sine=f=300:d=%d" % seconds] if audio else []) + ["-c:v", "libx264", "-pix_fmt", "yuv420p"] + (["-c:a", "aac"] if audio else []) + list(ext_args) + [path]
    subprocess.run(cmd, check=True, capture_output=True)


class Refs(unittest.TestCase):
    def test_parse_ref(self):
        self.assertEqual(WS.parse_ref("ingest:s123-2026#t=60-120"), ("ingest", "s123-2026", (60.0, 120.0)))
        self.assertEqual(WS.parse_ref("upload:my.mp4"), ("upload", "my.mp4", None)); self.assertEqual(WS.parse_ref("https://x.com/a.mp4")[0], "url"); self.assertEqual(WS.parse_ref("/data/a.mp4")[0], "file"); self.assertEqual(WS.parse_ref("file:///data/a%20b.mp4")[1], "/data/a b.mp4")
        for bad in ("", "javascript:alert(1)", "ftp://x/y", "gopher://x", "somefile.mp4", "ingest:x#t=50-10"):
            with self.assertRaises(WS.SourceError): WS.parse_ref(bad)

    def test_safe_name_rejects_traversal(self):
        for bad in ("../x", "a/b", "..", ".hidden", "a\\b", "", "x" * 200, "a b", "a\x00b"):
            with self.assertRaises(WS.SourceError, msg=repr(bad)): WS.safe_name(bad)
        self.assertEqual(WS.safe_name("show_01-final.mp4"), "show_01-final.mp4")

    def test_url_policy(self):
        pub = lambda h: ["93.184.216.34"]
        self.assertEqual(WS.check_url("https://example.com/v.mp4", resolver=pub), "example.com")
        for url in ("file:///etc/passwd", "ftp://example.com/x", "https://user:pw@example.com/x", "https://kick.com/video/1", "https://www.kick.com/x"):
            with self.assertRaises(WS.SourceError, msg=url): WS.check_url(url, resolver=pub)
        WS.check_url("https://kick.com/video/1", resolver=pub, trusted=True)   # owner's own org may bypass the Kick block
        for ip in ("127.0.0.1", "10.1.2.3", "192.168.0.5", "169.254.169.254", "::1", "0.0.0.0", "fd00::1"):
            with self.assertRaises(WS.SourceError, msg=ip): WS.check_url("https://evil.example/x", resolver=lambda h, ip=ip: [ip])
        with self.assertRaises(WS.SourceError): WS.check_url("https://evil.example/x", resolver=lambda h: ["93.184.216.34", "10.0.0.1"])   # one private answer is enough to refuse
        def nx(h): raise OSError("nxdomain")
        with self.assertRaises(WS.SourceError): WS.check_url("https://nope.invalid/x", resolver=nx)


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg not installed")
class Resolve(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="wstest_"); self.up = os.path.join(self.tmp, "uploads"); self.ing = os.path.join(self.tmp, "ingest"); os.makedirs(self.up); os.makedirs(self.ing)
        self.cfg = {"upload_dir": self.up, "ingest_dir": self.ing, "min_source_s": 1}
    def tearDown(self): shutil.rmtree(self.tmp, ignore_errors=True)
    def job(self, ref, typ="url", **kw): return dict({"id": "j_1", "channel": "c_1", "source": {"type": typ, "ref": ref}}, **kw)

    def test_upload(self):
        make_clip(os.path.join(self.up, "a.mp4")); r = WS.resolve_source(self.job("upload:a.mp4"), os.path.join(self.tmp, "w"), self.cfg); self.assertEqual(r["kind"], "upload"); self.assertAlmostEqual(r["duration_s"], 4, delta=0.5)

    def test_upload_traversal_and_missing(self):
        make_clip(os.path.join(self.tmp, "secret.mp4"))
        for ref in ("upload:../secret.mp4", "upload:..%2Fsecret.mp4", "upload:nofile.mp4"):
            with self.assertRaises(WS.SourceError): WS.resolve_source(self.job(ref), os.path.join(self.tmp, "w"), self.cfg)

    def test_symlink_cannot_escape_upload_dir(self):
        make_clip(os.path.join(self.tmp, "outside.mp4")); os.symlink(os.path.join(self.tmp, "outside.mp4"), os.path.join(self.up, "link.mp4"))
        with self.assertRaises(WS.SourceError) as c: WS.resolve_source(self.job("upload:link.mp4"), os.path.join(self.tmp, "w"), self.cfg)
        self.assertEqual(c.exception.code, "no_file")

    def test_local_path_only_inside_roots(self):
        make_clip(os.path.join(self.tmp, "elsewhere.mp4")); ref = os.path.join(self.tmp, "elsewhere.mp4")
        with self.assertRaises(WS.SourceError) as c: WS.resolve_source(self.job(ref), os.path.join(self.tmp, "w"), self.cfg)
        self.assertEqual(c.exception.code, "path_not_allowed"); self.assertEqual(WS.resolve_source(self.job(ref), os.path.join(self.tmp, "w"), dict(self.cfg, allow_any_path=True))["kind"], "file")
        with self.assertRaises(WS.SourceError): WS.resolve_source(self.job("/etc/passwd"), os.path.join(self.tmp, "w"), self.cfg)

    def test_ingest_concat_and_window(self):
        d = os.path.join(self.ing, "sabc-20261117"); os.makedirs(d)
        for i in range(3): make_clip(os.path.join(d, "2026111%d-000000.ts" % (7 + i)), 3, ext_args=("-f", "mpegts"))
        r = WS.resolve_source(self.job("ingest:sabc-20261117"), os.path.join(self.tmp, "w"), self.cfg); self.assertEqual(r["kind"], "ingest"); self.assertAlmostEqual(r["duration_s"], 9, delta=1.0)
        r = WS.resolve_source(self.job("ingest:sabc-20261117#t=3-7"), os.path.join(self.tmp, "w2"), self.cfg); self.assertAlmostEqual(r["duration_s"], 4, delta=1.5)

    def test_ingest_auto_picks_newest_recording_of_the_channel(self):
        d = os.path.join(self.ing, "c_1"); os.makedirs(d); make_clip(os.path.join(d, "a.ts"), 3, ext_args=("-f", "mpegts"))
        r = WS.resolve_source(self.job("", typ="auto"), os.path.join(self.tmp, "w"), self.cfg); self.assertEqual(r["title"], "c_1")
        with self.assertRaises(WS.SourceError) as c: WS.resolve_source(dict(self.job("", typ="auto"), channel="c_none"), os.path.join(self.tmp, "w3"), self.cfg)
        self.assertEqual(c.exception.code, "no_recording")

    def test_ingest_off_and_empty_dir(self):
        with self.assertRaises(WS.SourceError) as c: WS.resolve_source(self.job("ingest:x"), os.path.join(self.tmp, "w"), {"min_source_s": 1})
        self.assertEqual(c.exception.code, "ingest_off")
        os.makedirs(os.path.join(self.ing, "empty"))
        with self.assertRaises(WS.SourceError) as c: WS.resolve_source(self.job("ingest:empty"), os.path.join(self.tmp, "w"), self.cfg)
        self.assertEqual(c.exception.code, "no_recording")

    def test_no_audio_too_short_too_long_corrupt(self):
        make_clip(os.path.join(self.up, "mute.mp4"), audio=False); open(os.path.join(self.up, "junk.mp4"), "wb").write(b"not a video" * 50); make_clip(os.path.join(self.up, "ok.mp4"), 4)
        for ref, code, cfg in (("upload:mute.mp4", "no_audio", self.cfg), ("upload:junk.mp4", "unreadable_media", self.cfg), ("upload:ok.mp4", "too_short", dict(self.cfg, min_source_s=60)), ("upload:ok.mp4", "too_long", dict(self.cfg, max_source_h=0.0001))):
            with self.assertRaises(WS.SourceError, msg=ref) as c: WS.resolve_source(self.job(ref), os.path.join(self.tmp, "w"), cfg)
            self.assertEqual(c.exception.code, code)

    def test_url_goes_through_policy_before_any_download(self):
        called = []
        def runner(cmd, timeout=None): called.append(cmd); raise AssertionError("must not download")
        for url in ("https://kick.com/some/vod", "file:///etc/passwd", "http://127.0.0.1:8080/x.mp4"):
            with self.assertRaises(WS.SourceError): WS.resolve_source(self.job(url), os.path.join(self.tmp, "w"), self.cfg, runner=runner, resolver=lambda h: ["127.0.0.1"] if "127" in h else ["93.184.216.34"])
        self.assertEqual(called, [])

    def test_url_download_uses_ytdlp_with_safe_flags(self):
        seen = []
        def runner(cmd, timeout=None):
            seen.append(cmd); wd = os.path.dirname(cmd[cmd.index("-o") + 1]); make_clip(os.path.join(wd, "dl.mp4"), 4); return subprocess.CompletedProcess(cmd, 0, "", "")
        r = WS.resolve_source(self.job("https://example.com/v.mp4"), os.path.join(self.tmp, "w"), self.cfg, runner=runner, resolver=lambda h: ["93.184.216.34"]); self.assertEqual(r["kind"], "url")
        cmd = seen[0]; self.assertIn("--no-playlist", cmd); self.assertIn("--max-filesize", cmd); self.assertEqual(cmd[-2:], ["--", "https://example.com/v.mp4"])   # "--" stops a URL from being read as an option


class Pure(unittest.TestCase):
    def test_peaks_find_loud_dense_moments(self):
        import numpy as np
        en = [300.0] * 300; words = [{"word": " a", "start": float(i), "end": i + .2} for i in range(0, 300, 2)]
        for t in (50, 150, 250):
            for i in range(t, t + 6): en[i] = 3000.0; words += [{"word": " x", "start": i + .2, "end": i + .4}, {"word": " y", "start": i + .5, "end": i + .7}]
        S = JR.score_series(en, words, 0.0, 300); peaks = JR.pick_peaks(S, 3, 0.9)
        self.assertEqual(len(peaks), 3); self.assertTrue(all(any(abs(p - t) < 12 for t in (50, 150, 250)) for p in peaks))

    def test_customer_style_has_no_owner_branding(self):
        st = JR.customer_style({"style_id": "signature", "hints": {}}, None, {}); self.assertFalse(st["watermark"]["enabled"]); self.assertEqual(st["intro"]["bumper_s"], 0)
        st = JR.customer_style({"style_id": "nonexistent-style"}, {"language": "he", "preferences": {"min_len_s": 30, "max_len_s": 45}}, {}); self.assertEqual(st["language"]["code"], "he"); self.assertEqual((st["pace"]["min_clip_s"], st["pace"]["max_clip_s"]), (30, 45))
        self.assertTrue(JR.customer_style({}, None, {"keep_watermark": True})["watermark"]["enabled"])   # owner channels may keep the watermark

    def test_profile_loading_is_defensive(self):
        CP, p = JR.load_profile({"org": "o_1", "hints": {"profile": "not a dict"}}, {}); self.assertIsNone(p)
        d = tempfile.mkdtemp(); os.makedirs(os.path.join(d, "o_9")); json.dump({"schema": 1, "rules": [{"kind": "ban_word", "text": "casino"}]}, open(os.path.join(d, "o_9", "profile.json"), "w"))
        CP, p = JR.load_profile({"org": "o_9"}, {"profiles_dir": d}); self.assertEqual(p["rules"][0]["text"], "casino"); CP, p = JR.load_profile({"org": "../../etc"}, {"profiles_dir": d}); self.assertIsNone(p)
        shutil.rmtree(d)
        self.assertIsNone(JR.load_profile({"hints": {"profile": {"schema": 1}}}, {})[1]["language"])   # no explicit language: the profile must not force Hebrew
        self.assertEqual(JR.load_profile({"hints": {"profile": {"schema": 1, "language": "en"}}}, {})[1]["language"], "en")


@unittest.skipUnless(HAVE_FFMPEG and os.environ.get("RUN_SLOW_TESTS", "1") == "1", "ffmpeg missing or RUN_SLOW_TESTS=0")
class EndToEnd(unittest.TestCase):
    """the whole pipeline on a generated 100 s video: demo mode (no models, no network). Takes about a minute."""
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="e2e_"); cls.media = JR.make_demo_media(os.path.join(cls.tmp, "demo.mp4"), 100)
    @classmethod
    def tearDownClass(cls): shutil.rmtree(cls.tmp, ignore_errors=True)
    def run_job(self, extra_hints=None, outputs=None):
        job = {"id": "j_e2e", "org": "o_1", "channel": "c_1", "source": {"type": "url", "ref": self.media}, "style_id": "signature", "outputs": outputs or {"shorts": 1, "long": False}, "hints": extra_hints or {}}
        wd = os.path.join(self.tmp, "w_%d" % len(os.listdir(self.tmp))); cfg = JR.cfg_from_env({}); cfg.update({"demo": True, "allow_any_path": True}); msgs = []
        return JR.run_job(job, wd, cfg, emit=lambda progress=None, msg=None, vars=None, message=None: msgs.append((msg, vars))), wd, msgs
    def test_demo_job_makes_a_vertical_qa_graded_draft_without_owner_logo(self):
        res, wd, msgs = self.run_job(); d = res["drafts"][0]; self.assertEqual(d["kind"], "short"); self.assertTrue(d["qa_ok"], d["qa_notes"]); self.assertGreaterEqual(d["duration_s"], 19)
        probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=width,height", "-of", "json", os.path.join(wd, d["file"])], capture_output=True, text=True).stdout); self.assertEqual((probe["streams"][0]["width"], probe["streams"][0]["height"]), (1080, 1920))
        meta = json.load(open(os.path.join(wd, d["meta_file"]))); self.assertEqual(meta["privacy"], "private"); self.assertIn("qa", meta); self.assertEqual(meta["picker"], "heuristic")
        self.assertIn("found_moments", [m for m, _ in msgs]); self.assertIn("rendering", [m for m, _ in msgs])
    def test_profile_banned_word_in_transcript_flags_draft_qa_fail(self):
        res, wd, _ = self.run_job({"profile": {"schema": 1, "rules": [{"kind": "ban_word", "text": "demo"}]}}); d = res["drafts"][0]
        self.assertFalse(d["qa_ok"]); self.assertIn("customer profile", d["qa_notes"]); self.assertTrue(res["profile_applied"])   # kept for the customer to see, but never eligible for upload
    def test_llm_path_uses_customer_profile_and_hints_in_the_prompt(self):
        prompts = []
        def fake_llm(prompt):
            prompts.append(prompt); return {"score": 8, "start": 0, "end": 0, "title": "gets loud right here wow!", "hook": "LOUD", "reject": False, "kind": "hype", "why": "x"}
        job = {"id": "j_llm", "org": "o_1", "channel": "c_1", "source": {"type": "url", "ref": self.media}, "style_id": "signature", "outputs": {"shorts": 1, "long": False}, "hints": {"mood": "funny", "text": "make it funny", "profile": {"schema": 1, "rules": [{"kind": "prefer", "text": "PREFER-MARKER short punchy clips"}]}}}
        cfg = JR.cfg_from_env({}); cfg.update({"demo": True, "allow_any_path": True}); wd = os.path.join(self.tmp, "w_llm")
        res = JR.run_job(job, wd, cfg, emit=lambda *a, **k: None, deps={"llm": fake_llm}); self.assertEqual(res["picker"], "llm"); self.assertTrue(prompts)
        self.assertIn("PREFER-MARKER", prompts[0]); self.assertIn("funny", prompts[0]); self.assertIn("make it funny", prompts[0]); self.assertNotIn("%%", prompts[0]); self.assertNotIn("%d", prompts[0]); self.assertIn("English", prompts[0])
        self.assertIn("gets loud right here wow", res["drafts"][0]["title"])
    def test_llm_rejecting_everything_yields_no_moments(self):
        job = {"id": "j_rej", "org": "o_1", "channel": "c_1", "source": {"type": "url", "ref": self.media}, "outputs": {"shorts": 1, "long": False}, "hints": {}}
        cfg = JR.cfg_from_env({}); cfg.update({"demo": True, "allow_any_path": True})
        with self.assertRaises(JR.NoMoments): JR.run_job(job, os.path.join(self.tmp, "w_rej"), cfg, emit=lambda *a, **k: None, deps={"llm": lambda p: {"score": 9, "reject": True}})
    def test_profile_banned_word_in_title_blocks_the_clip(self):
        words = "this is a demo moment from the test stream and it gets loud right here wow".split()
        with self.assertRaises(JR.NoMoments): self.run_job({"profile": {"schema": 1, "rules": [{"kind": "ban_word", "text": w} for w in words]}})


class PreviewSources(unittest.TestCase):
    """GitHub-runner preview phase: the owner's trusted org may use Kick/Twitch VOD links and "my last stream"; customers stay blocked from Kick"""
    pub = staticmethod(lambda h: ["93.184.216.34"])
    def setUp(self): self.tmp = tempfile.mkdtemp(prefix="wsprev_")
    def tearDown(self): shutil.rmtree(self.tmp, ignore_errors=True)
    def fake_runner(self, calls, listing=""):
        class R:
            def __init__(s, out="", code=0): s.stdout, s.stderr, s.returncode = out, "", code
        def run(cmd, timeout=None, **kw):
            calls.append(list(cmd))
            if cmd[0] == "yt-dlp" and "--flat-playlist" in cmd or cmd[0] == "curl": return R(listing)
            if cmd[0] == "yt-dlp":   # the download: write the file where -o points
                out = cmd[cmd.index("-o") + 1].replace("%(ext)s", "mp4")
                if HAVE_FFMPEG: make_clip(out, 40)
                else: open(out, "wb").write(b"x")
                return R("")
            return WS.sh(cmd, timeout=timeout)
        return run

    def test_latest_twitch_vod(self):
        calls = []; listing = "v2001|60|too short\nv123456789|7200|Big stream\n"
        url, title = WS.latest_platform_vod("twitch", "noa", self.fake_runner(calls, listing))
        self.assertEqual(url, "https://www.twitch.tv/videos/123456789"); self.assertEqual(title, "Big stream")
        self.assertIn("https://www.twitch.tv/noa/videos?filter=archives&sort=time", calls[0])

    def test_latest_kick_vod(self):
        listing = json.dumps([{"duration": 60000, "source": "https://x.example/short/master.m3u8"}, {"duration": 7200000, "session_title": "VOD", "source": "https://stream.kick.com/abc/master.m3u8"}])
        url, title = WS.latest_platform_vod("kick", "odedsvr", self.fake_runner([], listing)); self.assertEqual(url, "https://stream.kick.com/abc/master.m3u8"); self.assertEqual(title, "VOD")
        with self.assertRaises(WS.SourceError): WS.latest_platform_vod("kick", "odedsvr", self.fake_runner([], "not json"))
        with self.assertRaises(WS.SourceError): WS.latest_platform_vod("kick", "odedsvr", self.fake_runner([], json.dumps([{"duration": 7200000, "source": "http://insecure/x.m3u8"}])))

    def test_bad_platform_or_slug_refused(self):
        for plat, slug in (("youtube", "x1"), ("kick", "../etc"), ("twitch", "a b"), ("kick", ""), ("kick", "x" * 40)):
            with self.assertRaises(WS.SourceError, msg=(plat, slug)): WS.latest_platform_vod(plat, slug, self.fake_runner([], "[]"))

    @unittest.skipUnless(HAVE_FFMPEG, "ffmpeg missing")
    def test_trusted_org_auto_job_resolves_last_twitch_vod_with_caps(self):
        calls = []; job = {"id": "j_1", "org": "o_1", "channel": "c_1", "source": {"type": "auto"}, "channel_info": {"platform": "twitch", "slug": "noa"}}
        cfg = {"trusted": True, "platform_vod": True, "download_max_min": 90, "download_height": 720, "min_source_s": 30}
        r = WS.resolve_source(job, os.path.join(self.tmp, "w"), cfg, runner=self.fake_runner(calls, "v123456789|7200|Big\n"), resolver=self.pub)
        self.assertEqual(r["kind"], "url"); dl = [c for c in calls if "--merge-output-format" in c][0]
        self.assertIn("*0-5400", dl); self.assertIn("bv*[height<=720]+ba/b[height<=720]/b", dl); self.assertEqual(dl[-1], "https://www.twitch.tv/videos/123456789")

    def test_customer_org_cannot_use_platform_vod_or_kick_links(self):
        job = {"id": "j_2", "org": "o_9", "channel": "c_1", "source": {"type": "auto"}, "channel_info": {"platform": "kick", "slug": "noa"}}
        with self.assertRaises(WS.SourceError) as e: WS.resolve_source(job, os.path.join(self.tmp, "w2"), {"platform_vod": True, "trusted": False}, runner=self.fake_runner([], "[]"), resolver=self.pub)
        self.assertEqual(e.exception.code, "no_recording")   # platform_vod needs trusted too
        job["source"] = {"type": "vod", "ref": "https://kick.com/video/abc"}
        with self.assertRaises(WS.SourceError) as e: WS.resolve_source(job, os.path.join(self.tmp, "w3"), {"trusted": False}, runner=self.fake_runner([], "[]"), resolver=self.pub)
        self.assertEqual(e.exception.code, "host_not_allowed")

    @unittest.skipUnless(HAVE_FFMPEG, "ffmpeg missing")
    def test_trusted_org_may_use_kick_link_and_window_end_wins_over_cap(self):
        calls = []; job = {"id": "j_3", "org": "o_1", "channel": "c_1", "source": {"type": "vod", "ref": "https://kick.com/video/abc#t=0-30"}}
        r = WS.resolve_source(job, os.path.join(self.tmp, "w4"), {"trusted": True, "download_max_min": 90, "min_source_s": 10}, runner=self.fake_runner(calls), resolver=self.pub)
        dl = [c for c in calls if "--merge-output-format" in c][0]; self.assertIn("*0-30", dl); self.assertTrue(r["duration_s"] >= 10)

    def test_job_runner_env_wiring(self):
        c = JR.cfg_from_env({"WORKER_PLATFORM_VOD": "1", "WORKER_DOWNLOAD_MAX_MIN": "90", "WORKER_DOWNLOAD_HEIGHT": "720", "WORKER_TRUSTED_ORGS": "o_1, o_2"})
        self.assertTrue(c["platform_vod"]); self.assertEqual(c["download_max_min"], 90); self.assertEqual(c["download_height"], 720); self.assertEqual(c["trusted_orgs"], ["o_1", "o_2"])
        d = JR.cfg_from_env({}); self.assertFalse(d["platform_vod"]); self.assertEqual(d["download_max_min"], 0); self.assertEqual(d["blocked_hosts"], ["kick.com"])


if __name__ == "__main__": unittest.main()

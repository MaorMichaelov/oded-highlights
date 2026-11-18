"""scripts/live_shorts.py: a streamer who is live must get a window processed within a few iterations (regression: the first window of a new stream
was always 'not complete yet', so nothing was ever cut).   python3 -m unittest tests.test_live_shorts -v"""
import json, os, sys, tempfile, unittest
from unittest import mock
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import live_shorts as LS


class Window(unittest.TestCase):
    def run_iter(self, dur, window=12, argv_extra=()):
        calls = []
        def fake_run(cmd, *a, **k):
            calls.append(cmd); return mock.Mock(returncode=0, stdout="", stderr="")
        argv = ["live_shorts.py", "--slug", "tester", "--platform", "twitch", "--window", str(window), "--long-every", "0", *argv_extra]
        with mock.patch.object(LS, "is_live", return_value=True), mock.patch.object(LS, "newest", return_value={"vod": "99", "title": "t", "audio": "x"}), \
             mock.patch.object(LS, "media_minutes", return_value=dur), mock.patch.object(LS.subprocess, "run", side_effect=fake_run), mock.patch.object(sys, "argv", argv):
            LS.main()
        return [c for c in calls if any("vod_shorts.py" in str(x) for x in c)]

    def setUp(self):
        self.old = os.getcwd(); self.tmp = tempfile.mkdtemp(prefix="liveshorts_"); os.chdir(self.tmp)
    def tearDown(self):
        os.chdir(self.old)

    def test_first_iteration_of_a_long_running_stream_processes_a_finished_window(self):
        cuts = self.run_iter(229.5)
        self.assertEqual(len(cuts), 1, "a stream that is already 229 min long must yield a finished window right away")
        c = cuts[0]; f, t = int(c[c.index("--from-min") + 1]), int(c[c.index("--to-min") + 1])
        self.assertEqual(t - f, 12); self.assertLessEqual(t, 229.5 - 2, "the window must be finished (>=2 min behind the live edge)")

    def test_windows_are_contiguous_and_progress_is_saved(self):
        first = self.run_iter(100.0); self.assertEqual(len(first), 1)
        st = json.load(open("state/tester/live_state.json")); self.assertEqual(st["vod"], "99")
        nxt = self.run_iter(100.0 + 13); self.assertEqual(len(nxt), 1)
        c0, c1 = first[0], nxt[0]
        self.assertEqual(int(c1[c1.index("--from-min") + 1]), int(c0[c0.index("--to-min") + 1]), "next window starts where the last ended")

    def test_progress_is_kept_when_the_next_window_is_not_ready(self):
        self.run_iter(100.0)
        self.assertEqual(self.run_iter(100.5), [], "not enough new stream yet: nothing to cut")
        self.assertTrue(os.path.exists("state/tester/live_state.json"))


if __name__ == "__main__":
    unittest.main()

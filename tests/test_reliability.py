import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import statefile as SF, dedup as D, retry as R


class StateFile(unittest.TestCase):
    def test_atomic_write_and_corrupt_read(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "s.json"); SF.write_json(p, {"a": 1}); self.assertEqual(SF.read_json(p), {"a": 1})
            self.assertEqual([f for f in os.listdir(d) if f.endswith(".tmp")], [])
            open(p, "w").write('{"a": 1, "b"')   # truncated by a killed runner
            self.assertEqual(SF.read_json(p, {"x": 0}), {"x": 0})
            self.assertTrue(any(".corrupt-" in f for f in os.listdir(d)))   # kept for inspection
            self.assertEqual(SF.read_json(p, "gone"), "gone")
    def test_unique_append_and_torn_line(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "l.jsonl")
            self.assertTrue(SF.append_jsonl_unique(p, {"id": "a"}, "id")); self.assertFalse(SF.append_jsonl_unique(p, {"id": "a"}, "id")); self.assertTrue(SF.append_jsonl_unique(p, {"id": "b"}, "id"))
            open(p, "a").write('{"id": "c", "x')   # torn tail
            self.assertEqual([r["id"] for r in SF.read_jsonl(p)], ["a", "b"])
    def test_truncate_from_makes_reingest_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "t.jsonl")
            for s in (0, 10, 20, 30): SF.append_line(p, json.dumps({"start": s, "text": "x"}))
            self.assertEqual(SF.truncate_jsonl_from(p, "start", 20), 2); self.assertEqual([r["start"] for r in SF.read_jsonl(p)], [0, 10])
            self.assertEqual(SF.truncate_jsonl_from(p, "start", 20), 0)


class Dedup(unittest.TestCase):
    def setUp(self): self.d = tempfile.TemporaryDirectory(); self.led = os.path.join(self.d.name, "dedup.jsonl")
    def tearDown(self): self.d.cleanup()
    def claim(self, *a, **k): return D.claim(*a, ledger=self.led, disk=False, **k)
    def test_same_range_twice(self):
        self.assertTrue(self.claim("v1", 100, 1000, "long", "main", "pick", "c1")[0])
        ok, ex = self.claim("v1", 105, 1004, "long", "main", "vod_long", "c2"); self.assertFalse(ok); self.assertEqual(ex["clip_id"], "c1")
    def test_idempotent_for_same_clip(self): self.claim("v1", 0, 600, "long", "main", "pick", "c1"); self.assertTrue(self.claim("v1", 0, 600, "long", "main", "pick", "c1")[0])
    def test_different_vod_kind_channel_or_part_is_not_a_duplicate(self):
        self.claim("v1", 0, 600, "long", "main", "pick", "c1")
        self.assertTrue(self.claim("v2", 0, 600, "long", "main")[0])          # other vod
        self.assertTrue(self.claim("v1", 100, 160, "short", "main")[0])       # a Short inside a long video is a different product
        self.assertTrue(self.claim("v1", 0, 600, "long", "en")[0])            # other channel
        self.assertTrue(self.claim("v1", 600, 1200, "long", "main")[0])       # next part
    def test_disk_ranges(self):
        root = self.d.name; cd = os.path.join(root, "state", "clips", "v9_5"); os.makedirs(cd)
        with open(os.path.join(cd, "cuts.json"), "w") as fh: json.dump({"vod": "v9", "pieces": [{"keep": [[100, 300], [320, 900]]}]}, fh)
        half = os.path.join(root, "state", "clips", "v9_half"); os.makedirs(half)
        with open(os.path.join(half, "cuts.json"), "w") as fh: json.dump({"vod": "v9", "pieces": [{"keep": [[5000, 6000]]}]}, fh)   # crash between cuts.json and spec.json: not a clip
        with open(os.path.join(cd, "spec.json"), "w") as fh: fh.write("{}")
        self.assertIsNotNone(D.find("v9", 110, 880, "long", ledger=self.led, root=root)); self.assertIsNone(D.find("v9", 2000, 2600, "long", ledger=self.led, root=root)); self.assertIsNone(D.find("v9", 5000, 6000, "long", ledger=self.led, root=root))
        self.assertEqual(D.backfill(root, self.led), 1); self.assertEqual(D.backfill(root, self.led), 0)


class Retry(unittest.TestCase):
    def test_classify(self):
        self.assertEqual(R.classify(200), "ok"); self.assertEqual(R.classify(429, "rate limit reached for tokens per minute (TPM)"), "retry")
        self.assertEqual(R.classify(429, "You exceeded your current quota"), "quota"); self.assertEqual(R.classify(429, "Rate limit reached ... tokens per day (TPD)"), "quota")
        self.assertEqual(R.classify(403, "dailyLimitExceeded"), "quota"); self.assertEqual(R.classify(401, "invalid api key"), "fatal")
        self.assertEqual(R.classify(503, ""), "retry"); self.assertEqual(R.classify(0, "timeout"), "retry"); self.assertEqual(R.classify(400, "bad request"), "fatal")
    def test_call_retries_only_transient(self):
        seq = iter([(503, ""), (429, "try again"), (200, "ok")]); slept = []
        v, st, _ = R.call(lambda: next(seq), attempts=4, sleep=slept.append, rnd=lambda: 1.0); self.assertEqual((v, st, len(slept)), ("ok", 200, 2))
        n = []; v, st, _ = R.call(lambda: (n.append(1), (429, "quota exhausted"))[1], attempts=4, sleep=lambda s: None); self.assertEqual((v, len(n)), ("quota", 1))
        n = []; v, st, _ = R.call(lambda: (n.append(1), (500, ""))[1], attempts=3, sleep=lambda s: None); self.assertEqual((v, len(n)), ("retry", 3))
    def test_delay_bounds(self):
        self.assertAlmostEqual(R.delay(10, 2, 60, rnd=lambda: 1.0), 60.0); self.assertEqual(R.delay(0, retry_after="7"), 7.0)


if __name__ == "__main__": unittest.main()

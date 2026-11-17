import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import cutqa as Q, vod_shorts as V
WORDS = [{"word": w, "start": i * 0.3, "end": i * 0.3 + 0.25} for i, w in enumerate("so I played my song live at twitchcon and the crowd was loud and Bam was there with the skaters and everyone laughed at the prize".split())]
class TruthfulTitle(unittest.TestCase):
    def test_supported_title_passes_without_llm(self):
        V.llm = lambda p: (_ for _ in ()).throw(AssertionError("LLM must not be called"))
        t, tt, ok = V.truthful_title("N3on plays his song live at TwitchCon", WORDS, ["N3on"]); self.assertTrue(ok); self.assertEqual(t, "N3on plays his song live at TwitchCon")
    def test_invented_name_is_rewritten(self):
        calls = []; V.llm = lambda p: (calls.append(p), {"title": "N3on plays his song live at TwitchCon with Bam"})[1]
        t, tt, ok = V.truthful_title("N3on and Drake play 500 songs at TwitchCon", WORDS, ["N3on"]); self.assertTrue(ok); self.assertEqual(len(calls), 1); self.assertIn("Drake", calls[0]); self.assertNotIn("Drake", t)
    def test_bad_rewrite_stays_unverified(self):
        V.llm = lambda p: {"title": "Drake wins 500 dollars"}
        t, tt, ok = V.truthful_title("N3on and Drake play 500 songs at TwitchCon", WORDS, ["N3on"]); self.assertFalse(ok)
    def test_stream_title_allows_names(self):
        V.llm = lambda p: None; t, tt, ok = V.truthful_title("N3on and Margera play at TwitchCon", WORDS, ["N3on"], stream_title="N3on x Bam Margera"); self.assertTrue(ok)
class ExistingRanges(unittest.TestCase):
    def test_reads_state(self):
        root = tempfile.mkdtemp(); d = os.path.join(root, "state", "n3on", "shorts"); os.makedirs(d)
        json.dump({"title": "x", "source": {"vod": "5", "start_s": 100, "end_s": 130}}, open(os.path.join(d, "short_5_100.json"), "w")); json.dump({}, open(os.path.join(d, "uploaded.json"), "w")); json.dump({"words": []}, open(os.path.join(d, "short_5_100.words.json"), "w"))
        r = Q.existing_ranges("n3on", 5, root=root); self.assertEqual(len(r), 1); self.assertEqual((r[0]["start"], r[0]["end"]), (100.0, 130.0)); self.assertEqual(Q.existing_ranges("n3on", 6, root=root), [])
if __name__ == "__main__": unittest.main()

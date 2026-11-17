import os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts")); sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import cutsnap as CS, synth
def scene():
    """3 sentences with 0.7 s pauses; words 0.3 s with 0.08 s gaps; returns words (dicts), the signal and the sentence (first start, last end) list"""
    w1, e1 = synth.sentence(1.0, 8); w2, e2 = synth.sentence(e1 + 0.7, 10); w3, e3 = synth.sentence(e2 + 0.7, 6); allw = w1 + w2 + w3; total = e3 + 2.0
    words = [{"word": f"w{i}", "start": a, "end": b} for i, (a, b) in enumerate(allw)]
    return words, synth.make_speech(allw, total), [(w1[0][0], e1), (w2[0][0], e2), (w3[0][0], e3)]
class Sentences(unittest.TestCase):
    def test_breaks(self):
        words, _, sents = scene(); br = CS.sentence_breaks(words); self.assertEqual([round(words[i]["end"], 2) for i in br], [round(s[1], 2) for s in sents])
    def test_start_mid_sentence_goes_to_sentence_start(self):
        words, _, sents = scene(); mid = (sents[1][0] + sents[1][1]) / 2; self.assertAlmostEqual(CS.sentence_start_near(mid, words), sents[1][0], 2)
    def test_start_far_inside_prefers_forward_when_back_too_long(self):
        words, _, sents = scene(); t = sents[1][0] + 7.0   # more than 5 s into sentence 2: nothing before within 5 s -> next sentence start
        self.assertAlmostEqual(CS.sentence_start_near(t, words, back=5.0, fwd=3.0), sents[2][0], 2)
    def test_end_finishes_the_sentence(self):
        words, _, sents = scene(); mid = sents[1][0] + 2.0; self.assertAlmostEqual(CS.sentence_end_near(mid, words, fwd=6.0), sents[1][1], 2)
    def test_align_span_length(self):
        words, _, sents = scene(); s, e, info = CS.align_span(sents[0][0] + 1.0, sents[1][0] + 1.0, words, min_len=5, max_len=40)
        self.assertAlmostEqual(s, sents[0][0], 2); self.assertAlmostEqual(e, sents[1][1], 2)
    def test_align_span_too_long_pulls_back(self):
        words, _, sents = scene(); s, e, info = CS.align_span(sents[0][0], sents[2][1], words, min_len=5, max_len=sents[1][1] - sents[0][0] + 0.5)
        self.assertAlmostEqual(e, sents[1][1], 2); self.assertTrue(info.get("end_pulled_back"))
    def test_align_span_too_short_extends(self):
        words, _, sents = scene(); s, e, info = CS.align_span(sents[0][0], sents[0][1], words, min_len=sents[1][1] - sents[0][0] - 1, max_len=60)
        self.assertAlmostEqual(e, sents[1][1], 2); self.assertTrue(info.get("end_extended"))
class Snap(unittest.TestCase):
    def test_snap_lands_in_pauses(self):
        words, x, sents = scene(); p = os.path.join(tempfile.mkdtemp(), "a.wav"); synth.write_wav(p, x); env, hop = CS.energy_db(p)
        for k in (0, 1, 2):
            a, b = sents[k]; s = CS.snap_start(a, words, env, hop, 0.0); e = CS.snap_end(b, words, env, hop, 0.0)
            self.assertLess(s, a); self.assertGreater(a - s, 0.05); self.assertLess(a - s, 0.65); self.assertGreater(e, b); self.assertLess(e - b, 0.5)
            self.assertFalse(CS._inside_word(s, words)); self.assertFalse(CS._inside_word(e, words)); self.assertTrue(CS.check_boundaries(s, e, env, hop, 0.0)["ok"])
    def test_trim_dead_air(self):
        words, x, sents = scene(); p = os.path.join(tempfile.mkdtemp(), "a.wav"); synth.write_wav(p, x); env, hop = CS.energy_db(p)
        a, b = CS.trim_dead_air(0.0, sents[2][1] + 1.9, words, env, hop, 0.0)   # 1 s of silence before the first word, 1.9 s after the last
        self.assertGreater(a, 0.5); self.assertLess(a, sents[0][0]); self.assertLess(b, sents[2][1] + 0.6); self.assertGreater(b, sents[2][1])
if __name__ == "__main__": unittest.main()

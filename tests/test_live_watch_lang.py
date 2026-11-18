import os, sys, tempfile, types, unittest
_tmp = tempfile.mkdtemp(); os.environ["STATE_DIR"] = _tmp   # absolute path: live_watch joins it to ROOT, an absolute path wins
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import live_watch as LW


class FakeModel:
    def __init__(self, name, lang, prob): self.name, self.lang, self.prob, self.calls = name, lang, prob, []
    def transcribe(self, path, language=None, **kw):
        self.calls.append(language)
        seg = types.SimpleNamespace(text=" hello ", start=0.0, end=2.0)
        return iter([seg]), types.SimpleNamespace(language=language or self.lang, language_probability=self.prob)


class Lang(unittest.TestCase):
    def setUp(self): LW._models.clear(); LW.DETECTED = (None, 0.0); self.made = {}
    def patch(self, lang, prob):
        def get(name): self.made.setdefault(name, FakeModel(name, lang, prob)); return self.made[name]
        LW._get_model = get
    def test_auto_detects_english_and_locks(self):
        self.patch("en", 0.97); rows = LW.ivrit_transcribe("x.mp3", "auto")
        self.assertEqual(rows, [(0.0, 2.0, "hello")]); self.assertEqual(LW.DETECTED[0], "en"); self.assertIn(LW.MULTI_MODEL, self.made); self.assertNotIn(LW.HE_MODEL, self.made)
    def test_auto_hebrew_reruns_with_ivrit_model(self):
        self.patch("he", 0.9); LW.ivrit_transcribe("x.mp3", "auto")
        self.assertIn(LW.HE_MODEL, self.made); self.assertEqual(self.made[LW.HE_MODEL].calls, ["he"]); self.assertEqual(LW.DETECTED[0], "he")
    def test_fixed_language_does_not_detect(self):
        self.patch("xx", 0.1); LW.ivrit_transcribe("x.mp3", "en"); self.assertEqual(self.made[LW.MULTI_MODEL].calls, ["en"])
    def test_engine_failure_returns_none(self):
        def boom(name): raise RuntimeError("no model")
        LW._get_model = boom; self.assertIsNone(LW.ivrit_transcribe("x.mp3", "he"))


if __name__ == "__main__": unittest.main()

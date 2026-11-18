import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import safety as S


class Screen(unittest.TestCase):
    def cfg(self, d):
        f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8"); json.dump(d, f); f.close(); self.addCleanup(os.unlink, f.name); return f.name
    def test_builtin(self):
        s = S.Screen(config_path=self.cfg({}), profile={}); self.assertTrue(s.hits("use code BIGWIN for the casino")); self.assertTrue(s.ok("great clutch play with his friends"))
    def test_per_channel_and_customer_words(self):
        c = self.cfg({"global": ["badword"], "channels": {"n3on": ["mommy joke"]}, "customers": {"acme": ["rival"]}})
        self.assertEqual(S.Screen("n3on", None, config_path=c, profile={}).hits("a Mommy Joke and a BADWORD"), ["mommy joke", "badword"])
        self.assertTrue(S.Screen("xqc", None, config_path=c, profile={}).ok("mommy joke"))      # other channel unaffected
        self.assertFalse(S.Screen("xqc", "acme", config_path=c, profile={}).ok("our rival game")); self.assertTrue(S.Screen("xqc", "other", config_path=c, profile={}).ok("our rival game"))
    def test_hebrew_prefix_and_profile(self):
        prof = {"schema": 1, "rules": [{"kind": "ban_word", "text": "הימורים", "status": "active"}, {"kind": "ban_topic", "text": "פוליטיקה", "keywords": ["בחירות"], "status": "active"}]}
        s = S.Screen(config_path=self.cfg({}), profile=prof); self.assertTrue(s.hits("הוא מדבר בהימורים")); self.assertTrue(s.hits("על הבחירות")); self.assertTrue(s.ok("שיחה רגילה"))
    def test_missing_config_is_fine(self): self.assertTrue(S.Screen(config_path="/nonexistent.json", profile={}).ok("hello"))


if __name__ == "__main__": unittest.main()

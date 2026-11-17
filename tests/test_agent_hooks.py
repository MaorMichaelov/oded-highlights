"""The documented hooks (docs/agent_hooks/*.patch) must keep applying to the CURRENT app/studio.js, app/worker.js and app/deploy.py, and the patched copy must pass
the old Studio tests AND the agent end-to-end test. Nothing in the real app/ is touched: everything runs on a temporary copy.   python3 -m unittest tests.test_agent_hooks -v"""
import os, shutil, subprocess, sys, tempfile, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HAVE_NODE = shutil.which("node") is not None and shutil.which("git") is not None


@unittest.skipUnless(HAVE_NODE, "node and git are needed")
class Hooks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="hooks_"); shutil.copytree(os.path.join(ROOT, "app"), os.path.join(cls.tmp, "app"))
        shutil.copytree(os.path.join(ROOT, "tests", "fixtures"), os.path.join(cls.tmp, "tests", "fixtures"))
        cls.applied = []
        for p in ("studio.patch", "worker_deploy.patch"):
            r = subprocess.run(["git", "apply", "--whitespace=nowarn", os.path.join(ROOT, "docs", "agent_hooks", p)], cwd=cls.tmp, capture_output=True, text=True); cls.applied.append((p, r.returncode, r.stderr[-300:]))

    @classmethod
    def tearDownClass(cls): shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_patches_apply(self):
        for p, rc, err in self.applied: self.assertEqual(rc, 0, f"{p} no longer applies to the current app/: {err}")

    def node(self, f):
        return subprocess.run(["node", os.path.join(self.tmp, "app", f)], cwd=self.tmp, capture_output=True, text=True, timeout=120)

    def test_studio_tests_still_pass_with_hooks(self):
        r = self.node("studio.test.mjs"); self.assertEqual(r.returncode, 0, r.stdout[-600:] + r.stderr[-1200:])

    def test_agent_end_to_end(self):
        r = self.node("agent_studio.e2e.mjs"); self.assertEqual(r.returncode, 0, r.stdout[-800:] + r.stderr[-1500:]); self.assertIn("e2e groups passed", r.stdout)

    def test_deploy_bundles_agent_modules(self):
        r = subprocess.run([sys.executable, "-I", os.path.join(self.tmp, "app", "deploy.py"), "--dry-run"], cwd=self.tmp, capture_output=True, text=True, env={**os.environ, "BUNDLE_DIR": self.tmp}); self.assertEqual(r.returncode, 0, r.stderr[-400:])
        src = open(os.path.join(self.tmp, "app", "deploy.py"), encoding="utf-8").read(); self.assertIn("agent_studio.js", src)
        for f in ("agent.js", "agent_studio.js"): self.assertTrue(os.path.exists(os.path.join(self.tmp, "app", f)))


if __name__ == "__main__": unittest.main()

"""scripts/setup_studio_worker.sh with STUB curl/gh binaries: the real script logic, no network, no credentials. Checks the order of steps, that the same key reaches Cloudflare KV and GitHub, and that the key
never appears in output, in any command line or in any file the script wrote. Run: python3 -m unittest tests/test_setup_studio_worker.py"""
import os, shutil, stat, subprocess, tempfile, unittest

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "setup_studio_worker.sh")
CURL = r'''#!/bin/bash
echo "curl $*" >> "$STUB_LOG"
args="$*"; if [[ "$args" == *"-K -"* ]]; then cfg=$(cat); echo "curl-config-stdin: $cfg" >> "$STUB_SECRET_LOG"; fi
for a in "$@"; do if [[ "$a" == /dev/fd/* ]]; then echo "curl-config-fd: $(cat "$a")" >> "$STUB_SECRET_LOG"; fi; done
case "$args" in
  *"storage/kv/namespaces?per_page"*) echo '{"success":true,"result":[{"id":"nsid123","title":"other"},{"id":"nsid999","title":"studio-app"}]}' ;;
  *"-X PUT"*"values/studio%3Acfg%3Aworker_key"*) body=$(cat); echo "kv-body: $body" >> "$STUB_SECRET_LOG"; echo "kv-url: $args" >> "$STUB_LOG"; echo '{"success":true}' ;;
  *"/studio/worker/queue"*) printf '%s' "${STUB_QUEUE_CODE:-200}" ;;
  *) echo '{}' ;;
esac
'''
GH = r'''#!/bin/bash
echo "gh $*" >> "$STUB_LOG"
if [ "$1 $2" = "secret set" ]; then body=$(cat); echo "secret $3: $body" >> "$STUB_SECRET_LOG"; fi
exit 0
'''


class Setup(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="setup_"); self.bin = os.path.join(self.tmp, "bin"); os.makedirs(self.bin)
        for name, body in (("curl", CURL), ("gh", GH)):
            p = os.path.join(self.bin, name); open(p, "w").write(body); os.chmod(p, 0o755)
        self.log, self.slog = os.path.join(self.tmp, "calls.log"), os.path.join(self.tmp, "secrets.log")
    def tearDown(self): shutil.rmtree(self.tmp, ignore_errors=True)
    def run_script(self, *args, stdin="", **env):
        e = {"PATH": self.bin + ":" + os.environ["PATH"], "STUB_LOG": self.log, "STUB_SECRET_LOG": self.slog, "CLOUDFLARE_API_TOKEN": "cftoken_abcdefghijklmnopqrstuvwxyz", "HOME": self.tmp, "SETUP_RETRY_SLEEP": "0"}; e.update(env)
        return subprocess.run(["bash", SCRIPT] + list(args), input=stdin, capture_output=True, text=True, env=e, timeout=60)
    def secrets(self): return open(self.slog).read() if os.path.exists(self.slog) else ""
    def calls(self): return open(self.log).read() if os.path.exists(self.log) else ""

    def test_happy_path_same_key_in_kv_and_github_and_never_shown(self):
        r = self.run_script("--trusted-orgs", "o_abc123,o_def456"); self.assertEqual(r.returncode, 0, r.stderr)
        s = self.secrets(); kv = [l for l in s.splitlines() if l.startswith("kv-body: ")][0][9:]; self.assertRegex(kv, r"^wk_[0-9a-f]{64}$")
        self.assertIn("secret STUDIO_WORKER_KEY: " + kv, s); self.assertIn("secret STUDIO_URL: https://studio-app.odedhl.workers.dev", s); self.assertIn("secret STUDIO_TRUSTED_ORGS: o_abc123,o_def456", s)
        for hay, what in ((r.stdout, "stdout"), (r.stderr, "stderr"), (self.calls(), "command lines")): self.assertNotIn(kv, hay, "key leaked into " + what); self.assertNotIn("cftoken_abcdefghijklmnopqrstuvwxyz", hay, "Cloudflare token leaked into " + what)
        self.assertIn("accepted the key (HTTP 200)", r.stdout); self.assertIn("workflow run studio-worker.yml", self.calls())
        self.assertIn("storage/kv/namespaces/nsid999/values/studio%3Acfg%3Aworker_key", self.calls())   # the namespace was looked up by title, not guessed
        order = [l for l in self.calls().splitlines()]; self.assertLess(next(i for i, l in enumerate(order) if "kv-url" in l), next(i for i, l in enumerate(order) if l.startswith("gh secret set STUDIO_WORKER_KEY")))   # KV first

    def test_each_run_makes_a_new_key(self):
        self.run_script("--no-run"); k1 = [l for l in self.secrets().splitlines() if l.startswith("kv-body")][0]; os.remove(self.slog); self.run_script("--no-run"); k2 = [l for l in self.secrets().splitlines() if l.startswith("kv-body")][0]; self.assertNotEqual(k1, k2)

    def test_ask_key_reads_stdin_without_echo(self):
        mine = "my-own-key-" + "a" * 30; r = self.run_script("--ask-key", "--no-run", stdin=mine + "\n"); self.assertEqual(r.returncode, 0, r.stderr); self.assertIn("kv-body: " + mine, self.secrets()); self.assertNotIn(mine, r.stdout + r.stderr + self.calls())
        r = self.run_script("--ask-key", "--no-run", stdin="short\n"); self.assertEqual(r.returncode, 1)

    def test_dry_run_changes_nothing(self):
        r = self.run_script("--dry-run"); self.assertEqual(r.returncode, 0); self.assertIn("nothing was changed", r.stdout); self.assertEqual(self.calls(), ""); self.assertEqual(self.secrets(), "")

    def test_refuses_production_app_and_bad_input(self):
        for args in (["--url", "https://oded-app.odedhl.workers.dev"], ["--url", "http://studio-app.x.workers.dev"], ["--repo", "bad repo"], ["--trusted-orgs", "o_1;rm -rf"], ["--bogus"]):
            r = self.run_script(*args); self.assertNotEqual(r.returncode, 0, args); self.assertEqual(self.calls(), "", args)

    def test_wrong_status_is_a_warning_not_a_crash_and_missing_namespace_is_an_error(self):
        r = self.run_script("--no-run", STUB_QUEUE_CODE="401"); self.assertEqual(r.returncode, 0); self.assertIn("HTTP 401", r.stderr)
        open(self.log, "w").close(); open(os.path.join(self.bin, "curl"), "w").write(CURL.replace('"title":"studio-app"', '"title":"nope"')); r = self.run_script("--no-run"); self.assertEqual(r.returncode, 1); self.assertIn("not found", r.stderr); self.assertNotIn("gh secret set", self.calls())


if __name__ == "__main__": unittest.main()

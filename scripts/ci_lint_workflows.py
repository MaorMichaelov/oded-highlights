#!/usr/bin/env python3
"""Lints .github/workflows/*.yml: every file parses, every workflow declares `permissions`, and no `run:` script contains ${{ inputs.* }} / ${{ github.event.* }} / ${{ github.head_ref }}
(script injection: pass them through env instead). Constant-output expressions like ${{ inputs.upload == 'true' && '--upload' || '' }} are allowed. Exit 1 on any problem."""
import glob, os, re, sys
import yaml
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RISKY = re.compile(r"\$\{\{\s*(inputs\.[A-Za-z0-9_]+|github\.event\.[^}]*|github\.head_ref|github\.ref_name)\s*\}\}")
def lint(path):
    probs = []
    try: d = yaml.safe_load(open(path, encoding="utf-8"))
    except Exception as e: return [f"{path}: YAML error {e}"]
    if not isinstance(d, dict) or "jobs" not in d: return [f"{path}: no jobs"]
    if "permissions" not in d and not all("permissions" in j for j in d["jobs"].values()): probs.append(f"{path}: no `permissions:` (the default token may be write-all)")
    for jn, j in d["jobs"].items():
        for s in j.get("steps", []) or []:
            if RISKY.search(s.get("run", "") or ""): probs.append(f"{path}: job {jn} step {s.get('name') or s.get('run','')[:40]!r} pastes untrusted context into a shell script")
    return probs
def main():
    probs = []
    for f in sorted(glob.glob(os.path.join(ROOT, ".github", "workflows", "*.yml"))): probs += lint(f)
    for p in probs: print("::error::" + p)
    print("workflows checked, problems:", len(probs)); return 1 if probs else 0
if __name__ == "__main__": sys.exit(main())

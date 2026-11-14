#!/usr/bin/env python3
"""Posts ONE comment on issue #1 when odedsvr goes live (offline -> live). The assistant session is subscribed to that issue and wakes up to tell the owner."""
import json, os, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); ST = os.path.join(ROOT, "state")
ls = json.load(open(os.path.join(ST, "live_status.json"))); af = os.path.join(ST, "alert_state.json")
prev = json.load(open(af)) if os.path.exists(af) else {"live": False}
if ls.get("live") and not prev.get("live"):
    body = f"🔴 עודד עלה ללייב: {ls.get('title') or ''} | קטגוריה: {ls.get('category') or '-'} | צופים: {ls.get('viewers')} | {ls.get('checked_at')}"
    subprocess.run(["gh", "api", "-X", "POST", f"repos/{os.environ.get('GITHUB_REPOSITORY', 'MaorMichaelov/oded-highlights')}/issues/1/comments", "-f", f"body={body}"], check=False)
    print("live alert sent")
json.dump({"live": bool(ls.get("live"))}, open(af, "w"))

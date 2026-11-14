#!/usr/bin/env python3
"""Posts ONE comment on issue #1 when odedsvr goes live (offline -> live). The assistant session is subscribed to that issue and wakes up to tell the owner."""
import json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from events import event
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); ST = os.path.join(ROOT, "state")
ls = json.load(open(os.path.join(ST, "live_status.json"))); af = os.path.join(ST, "alert_state.json")
prev = json.load(open(af)) if os.path.exists(af) else {"live": False}
if ls.get("live") and not prev.get("live"):
    body = f"🔴 עודד עלה ללייב: {ls.get('title') or ''} | קטגוריה: {ls.get('category') or '-'} | צופים: {ls.get('viewers')} | {ls.get('checked_at')}"
    subprocess.run(["gh", "api", "-X", "POST", f"repos/{os.environ.get('GITHUB_REPOSITORY', 'MaorMichaelov/oded-highlights')}/issues/1/comments", "-f", f"body={body}"], check=False)
    event("live_up", body); print("live alert sent")
elif prev.get("live") and not ls.get("live"): event("live_down", "עודד ירד מהלייב")
import time as _t
if ls.get("live"):   # viewer/title history for the app and the pick station
    with open(os.path.join(ST, "live_history.jsonl"), "a") as hf: hf.write(json.dumps({"t": ls.get("checked_at"), "viewers": ls.get("viewers"), "title": ls.get("title"), "category": ls.get("category")}, ensure_ascii=False) + "\n")
json.dump({"live": bool(ls.get("live"))}, open(af, "w"))

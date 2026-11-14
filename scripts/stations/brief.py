#!/usr/bin/env python3
"""Daily brief (about 09:00 Israel): what happened in the last 24 h, written by the free LLM from our own state, posted as an event in the app chat. Runs once per day (state/brief_state.json)."""
import json, os, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from events import ST, event, ROOT
bs = os.path.join(ST, "brief_state.json"); st = json.load(open(bs)) if os.path.exists(bs) else {}
today = time.strftime("%Y-%m-%d", time.gmtime())
if st.get("last") == today or int(time.strftime("%H", time.gmtime())) < 6: sys.exit(0)
def jf(p, d=None): return json.load(open(os.path.join(ST, p))) if os.path.exists(os.path.join(ST, p)) else d
ev = [json.loads(l) for l in open(os.path.join(ST, "events.jsonl"), encoding="utf-8")][-40:] if os.path.exists(os.path.join(ST, "events.jsonl")) else []
stats = jf("yt_stats.json", {}) or {}; idx = jf("index.json", []) or []; les = (jf("lessons.json", []) or [])[-5:]
facts = {"events_last": [e["text"] for e in ev][-25:], "drafts": [{"title": c["title"], "uploaded": bool(c.get("draft"))} for c in idx][-10:], "channel": stats.get("channel"), "top_videos": [{"t": v["title"], "views": v["views"]} for v in sorted(stats.get("videos", []), key=lambda v: -v["views"])[:5]], "lessons": [l["text"] for l in les], "health": jf("health.json")}
prompt = "כתוב סיכום בוקר קצר בעברית (עד 6 שורות, אימוג'ים מעטים) לבעל ערוץ הקליפים ODED HIGHLIGHTS. רק מתוך העובדות, בלי להמציא מספרים:\n" + json.dumps(facts, ensure_ascii=False)
body = json.dumps({"model": "openai/gpt-oss-120b", "messages": [{"role": "user", "content": prompt}], "max_tokens": 900, "reasoning_effort": "low"}, ensure_ascii=False)
hdr = ["-H", "Content-Type: application/json"] + (["-H", "Authorization: Bearer " + os.environ["GROQ_API_KEY"]] if os.environ.get("GROQ_API_KEY") else [])
out = subprocess.run(["curl", "-sS", "-m", "90", "https://api.groq.com/openai/v1/chat/completions"] + hdr + ["-d", body], capture_output=True, text=True).stdout
try: txt = json.loads(out)["choices"][0]["message"]["content"].strip()
except Exception: sys.exit("brief: model unavailable")
event("brief", "☀️ סיכום בוקר\n" + txt); st["last"] = today; json.dump(st, open(bs, "w")); print("brief posted")

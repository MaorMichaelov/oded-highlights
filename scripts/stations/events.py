"""Tiny shared helpers: events feed (state/events.jsonl, read by the chat app) and lessons (state/lessons.json, read by the pick station)."""
import json, os, time
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); ST = os.path.join(ROOT, os.environ.get("STATE_DIR", "state"))
def event(kind, text, **kw):
    with open(os.path.join(ST, "events.jsonl"), "a", encoding="utf-8") as f: f.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "kind": kind, "text": text, **kw}, ensure_ascii=False) + "\n")
def lesson(text, source="system"):
    p = os.path.join(ST, "lessons.json"); L = json.load(open(p)) if os.path.exists(p) else []
    if any(x["text"] == text for x in L): return
    L.append({"t": time.strftime("%Y-%m-%d", time.gmtime()), "source": source, "text": text}); json.dump(L[-200:], open(p, "w"), ensure_ascii=False, indent=1)

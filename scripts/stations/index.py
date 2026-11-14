#!/usr/bin/env python3
"""Builds state/index.json: one line per clip (id, title, status, draft url, brief) for the chat app."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from events import ST
cd = os.path.join(ST, "clips"); out = []
for d in sorted(os.listdir(cd)) if os.path.isdir(cd) else []:
    jf = lambda n: json.load(open(os.path.join(cd, d, n))) if os.path.exists(os.path.join(cd, d, n)) else {}
    sp, stt, q = jf("spec.json"), jf("status.json"), jf("quality.json")
    if not sp: continue
    out.append({"id": d, "title": sp.get("title"), "brief": sp.get("brief"), "stages": {k: v.get("state") for k, v in stt.items()}, "draft": (stt.get("draft") or {}).get("url"), "draft_at": (stt.get("draft") or {}).get("at"), "quality_errors": q.get("errors"), "auto": sp.get("auto", False)})
json.dump(out, open(os.path.join(ST, "index.json"), "w"), ensure_ascii=False, indent=1); print(len(out), "clips indexed")

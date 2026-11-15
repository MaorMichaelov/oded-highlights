#!/usr/bin/env python3
"""TIMELINE: a topic timeline of the live ("what happened when"), built incrementally from the transcript by the free LLM, for the app and the pick station.
state/timeline.json = [{"from": sec, "to": sec, "label": "short Hebrew topic", "kind": talk|game|cooking|guest|call|reaction|chat|idle}] (consecutive identical topics merged).
Each 5-minute chunk is labelled once (cached) with gpt-oss-20b (own free token bucket). usage: timeline.py"""
import json, os, re, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from events import ST
CH = 300
def jl(p): return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()] if os.path.exists(p) else []
ing = json.load(open(os.path.join(ST, "ingest_state.json"))) if os.path.exists(os.path.join(ST, "ingest_state.json")) else {}
vod = ing.get("_current_vod")
if not vod: sys.exit(0)
rows = jl(os.path.join(ST, "transcripts", f"{vod}.jsonl"))
if not rows: sys.exit(0)
tf = os.path.join(ST, "timeline.json"); T = json.load(open(tf)) if os.path.exists(tf) else {}
if T.get("vod") != vod: T = {"vod": vod, "chunks": {}}
end = rows[-1]["end"]
for k, x in list(T["chunks"].items()):   # relabel weak v1 chunks once (idle/unclear although there is speech)
    c = int(k); w = sum(len(r["text"].split()) for r in rows if c * CH <= r["start"] < (c + 1) * CH)
    if x.get("v", 1) < 2 and (x.get("kind") == "idle" or "ברור" in x.get("label", "")) and w > 150: del T["chunks"][k]
todo = [c for c in range(0, int(end // CH) + 1) if str(c) not in T["chunks"] and (c + 1) * CH <= end + 1 or (c == int(end // CH) and False)]
todo = [c for c in todo if (c + 1) * CH <= end + 1][:6]
CATS = [json.loads(l) for l in open(os.path.join(ST, "category.jsonl"), encoding="utf-8") if l.strip()] if os.path.exists(os.path.join(ST, "category.jsonl")) else []
VS = ing.get("_vod_start_epoch") or 0
def cat_at(c):
    t = VS + c * CH + CH / 2; cur = None
    for x in CATS:
        if x["t"] <= t: cur = x.get("cat")
    return cur
def add_plan(text, c):
    pf = os.path.join(ST, "plans.json"); P = json.load(open(pf)) if os.path.exists(pf) else []
    if any(x["text"] == text for x in P): return
    P.append({"t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "vod": vod, "at_min": c * 5, "text": text, "status": "planned"}); json.dump(P[-60:], open(pf, "w"), ensure_ascii=False, indent=1)
    from events import event; event("plan", f"📌 עודד תכנן: {text} (בדקה {c * 5} בשידור)")
def label(chs):
    parts = []
    for c in chs:
        txt = " ".join(r["text"] for r in rows if c * CH <= r["start"] < (c + 1) * CH)[:3000]
        parts.append(f"### chunk {c} ({c * 5}-{c * 5 + 5} min) | קטגוריית Kick באותו זמן: {cat_at(c) or 'לא ידוע'}\n{txt}")
    prompt = ("לכל קטע תמלול של 5 דקות מלייב של סטרימר ישראלי (התמלול האוטומטי מלא שגיאות, אל תתייאש), תן: label = משפט קצר בעברית על מה קורה בפועל (4-10 מילים, ספציפי: 'מבשל פסטה עם אשתו ועונה לצ'אט', 'מספר על חרדות לפני הסבתון', 'משחק רוב ראן עם חברים'), "
              "keywords = 3-6 מילות מפתח, plans = רשימה (0-3) של דברים שהוא אומר במפורש שהוא מתכנן לעשות/לצפות/לשחק/להגיב עליהם בהמשך (בשידור הזה או בשידורים הבאים; משפט קצר בעברית, למשל 'להגיב לסרטון של פרנזי'), רק אם נאמר בפירוש, kind אחד מ: talk,game,cooking,guest,call,reaction,chat,idle (reaction = הוא צופה/קורא כתבה, סרטון או חדשות (למשל על GTA 6) ומגיב עליהם בקול; ציין על מה). idle רק אם כמעט אין דיבור. אסור לכתוב 'לא ברור'. "
              "החזר JSON בלבד: {\"labels\":[{\"chunk\":n,\"label\":\"...\",\"keywords\":[...],\"plans\":[...],\"kind\":\"...\"}]}\n\n" + "\n\n".join(parts))
    hdr = ["-H", "Content-Type: application/json"] + (["-H", "Authorization: Bearer " + os.environ["GROQ_API_KEY"]] if os.environ.get("GROQ_API_KEY") else [])
    for model in ("openai/gpt-oss-120b", "openai/gpt-oss-20b"):
        out = subprocess.run(["curl", "-sS", "-m", "120", "https://api.groq.com/openai/v1/chat/completions"] + hdr + ["-d", json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 1000, "reasoning_effort": "low"}, ensure_ascii=False)], capture_output=True, text=True).stdout
        try: return json.loads(re.search(r"\{.*\}", json.loads(out)["choices"][0]["message"]["content"], re.S).group(0))["labels"]
        except Exception as e: print("timeline model", model, "failed:", str(e)[:80], out[:120])
    return []
for i in range(0, len(todo), 3):
    for l in label(todo[i:i + 3]):
        T["chunks"][str(l["chunk"])] = {"label": l.get("label", ""), "kind": l.get("kind", "talk"), "kw": l.get("keywords", []), "v": 2}
        for pl in (l.get("plans") or [])[:3]:   # what he says he will do / react to / play: remembered for next lives and shown in the app
            if isinstance(pl, str) and len(pl) > 6: add_plan(pl.strip(), int(l["chunk"]))
    time.sleep(1)
def segment(T, nchunks):
    """LLM groups consecutive chunk labels into topic SPANS (what a clip would be). Incremental: re-segments from the start of the last open span."""
    spans = T.get("spans", []); last_chunk = max(map(int, T["chunks"]), default=-1)
    start_c = 0
    if spans:
        open_ = [x for x in spans if not x.get("closed")]
        start_c = open_[0]["from"] // CH if open_ else (spans[-1]["to"] // CH)
        spans = [x for x in spans if x["to"] <= start_c * CH]
    cs = [c for c in range(start_c, last_chunk + 1) if str(c) in T["chunks"]][:60]
    if len(cs) < 2: return spans
    lines = "\n".join(f"{c * 5}-{c * 5 + 5} [{T['chunks'][str(c)]['kind']}] (קטגוריה: {cat_at(c) or '?'}) {T['chunks'][str(c)]['label']} ({', '.join(T['chunks'][str(c)].get('kw', [])[:4])})" for c in cs)
    prompt = ("אלו תוויות של קטעי 5 דקות ברצף מלייב של סטרימר ישראלי (דקות מתחילת השידור). קבץ קטעים רצופים לנושאים (spans) שכל אחד הוא פעילות/נושא אחד שלם: למשל בישול עם אשתו, שיחה על הסבתון, משחק. "
              "לכל span: from/to בדקות (כפולות של 5), title בעברית קצר, kind, clip_worthy=true רק אם זה נושא שווה סרטון (סיפור, פעילות בבית כמו בישול, אורח, משחק עם חברים, ריאקשן, דרמה) ולא שיחת צ'אט כללית/המתנה, why=סיבה קצרה. "
              "כשקטגוריית Kick היא משחק (לא Just Chatting) והוא משחק, זה span מסוג game ושווה קליפ ברגע שהוא נמשך 15 דקות ומעלה. אל תפצל פעילות אחת לכמה spans, ואל תאחד נושאים שונים. סשן רציף של ריאקשנים (הוא צופה/קורא כמה כתבות או סרטונים ברצף ומגיב) הוא span אחד מסוג reaction ושווה קליפ, עם כותרת כמו 'מגיב לכתבות וחדשות על GTA 6'. החזר JSON בלבד: {\"spans\":[{\"from\":m,\"to\":m,\"title\":\"\",\"kind\":\"\",\"clip_worthy\":true,\"why\":\"\"}]}\n\n" + lines)
    hdr = ["-H", "Content-Type: application/json"] + (["-H", "Authorization: Bearer " + os.environ["GROQ_API_KEY"]] if os.environ.get("GROQ_API_KEY") else [])
    for model in ("openai/gpt-oss-120b", "openai/gpt-oss-20b"):
        out = subprocess.run(["curl", "-sS", "-m", "120", "https://api.groq.com/openai/v1/chat/completions"] + hdr + ["-d", json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 1500, "reasoning_effort": "low"}, ensure_ascii=False)], capture_output=True, text=True).stdout
        try:
            new = json.loads(re.search(r"\{.*\}", json.loads(out)["choices"][0]["message"]["content"], re.S).group(0))["spans"]
            for x in new:
                x["from"], x["to"] = int(x["from"]) * 60, int(x["to"]) * 60; x["closed"] = x["to"] <= (last_chunk - 0) * CH   # a span is closed once at least one later chunk exists after it
            merged = []
            for x in sorted((x for x in new if x["to"] > x["from"]), key=lambda x: x["from"]):   # one activity = one span: merge adjacent spans of the same activity kind
                if merged and merged[-1]["to"] == x["from"] and x["kind"] == merged[-1]["kind"] and x["kind"] in ("cooking", "game", "guest", "call", "reaction"):
                    merged[-1]["to"] = x["to"]; merged[-1]["closed"] = x["closed"]; merged[-1]["clip_worthy"] = merged[-1]["clip_worthy"] or x["clip_worthy"]
                else: merged.append(x)
            return spans + merged
        except Exception as e: print("segment model", model, "failed:", str(e)[:80], out[:120])
    return spans
T["spans"] = segment(T, 0)
tl = []
for c in sorted(map(int, T["chunks"])):
    x = T["chunks"][str(c)]
    if tl and tl[-1]["label"] == x["label"] and tl[-1]["to"] == c * CH: tl[-1]["to"] = (c + 1) * CH
    else: tl.append({"from": c * CH, "to": (c + 1) * CH, "label": x["label"], "kind": x["kind"]})
T["timeline"] = tl; T["transcript_end"] = round(end); T["updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
json.dump(T, open(tf, "w"), ensure_ascii=False, indent=1); print("timeline:", len(tl), "topics,", len(T["chunks"]), "chunks, transcript to", round(end / 60), "min")

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
end = rows[-1]["end"]; todo = [c for c in range(0, int(end // CH) + 1) if str(c) not in T["chunks"] and (c + 1) * CH <= end + 1 or (c == int(end // CH) and False)]
todo = [c for c in todo if (c + 1) * CH <= end + 1][:6]
def label(chs):
    parts = []
    for c in chs:
        txt = " ".join(r["text"] for r in rows if c * CH <= r["start"] < (c + 1) * CH)[:2200]
        parts.append(f"### chunk {c} ({c * 5}-{c * 5 + 5} min)\n{txt}")
    prompt = ("לכל קטע תמלול של 5 דקות מלייב של סטרימר ישראלי, תן תווית נושא קצרה בעברית (2-6 מילים, מה קורה בפועל: למשל 'מבשל פסטה עם אשתו', 'משחק רוב ראן עם חברים', 'שיחה עם הצופים על הסבתון', 'שקט/המתנה') וסוג אחד מ: talk,game,cooking,guest,call,reaction,chat,idle. "
              "אם הקטע לא ברור או ריק: idle. החזר JSON בלבד: {\"labels\":[{\"chunk\":n,\"label\":\"...\",\"kind\":\"...\"}]}\n\n" + "\n\n".join(parts))
    hdr = ["-H", "Content-Type: application/json"] + (["-H", "Authorization: Bearer " + os.environ["GROQ_API_KEY"]] if os.environ.get("GROQ_API_KEY") else [])
    for model in ("openai/gpt-oss-20b", "openai/gpt-oss-120b"):
        out = subprocess.run(["curl", "-sS", "-m", "120", "https://api.groq.com/openai/v1/chat/completions"] + hdr + ["-d", json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 700, "reasoning_effort": "low"}, ensure_ascii=False)], capture_output=True, text=True).stdout
        try: return json.loads(re.search(r"\{.*\}", json.loads(out)["choices"][0]["message"]["content"], re.S).group(0))["labels"]
        except Exception as e: print("timeline model", model, "failed:", str(e)[:80], out[:120])
    return []
for i in range(0, len(todo), 3):
    for l in label(todo[i:i + 3]): T["chunks"][str(l["chunk"])] = {"label": l.get("label", ""), "kind": l.get("kind", "talk")}
    time.sleep(1)
tl = []
for c in sorted(map(int, T["chunks"])):
    x = T["chunks"][str(c)]
    if tl and tl[-1]["label"] == x["label"] and tl[-1]["to"] == c * CH: tl[-1]["to"] = (c + 1) * CH
    else: tl.append({"from": c * CH, "to": (c + 1) * CH, "label": x["label"], "kind": x["kind"]})
T["timeline"] = tl; T["transcript_end"] = round(end); T["updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
json.dump(T, open(tf, "w"), ensure_ascii=False, indent=1); print("timeline:", len(tl), "topics,", len(T["chunks"]), "chunks, transcript to", round(end / 60), "min")

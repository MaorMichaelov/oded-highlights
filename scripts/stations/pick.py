#!/usr/bin/env python3
"""STATION 2 - PICK: decides which closed topics of the live become clips. Runs inside the live loop (and can be run alone on any transcript).
Reads : state/transcripts/<vod>.jsonl (+ category.jsonl, chat spikes, existing clips, docs/TOPICS_TO_CLIP.md)
Model : Groq openai/gpt-oss-120b (free, Hebrew OK, 131k context).  Falls back to marking nothing if the model is unavailable (never uploads a weak clip).
Writes: state/clips/<id>/{cuts.json,spec.json}  then dispatches render-clip (cut -> edit -> draft stations).
Safety: a topic counts only when it ended >= HOLD s before the end of the transcript; start/end are snapped to sentence boundaries; hard lines are cut out.
usage: pick.py [--vod ID] [--dry-run] [--state DIR] [--hold 300]"""
import argparse, json, os, re, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE)); sys.path.insert(0, os.path.dirname(HERE))
MODEL = os.environ.get("PICK_MODEL", "openai/gpt-oss-120b")
MIN_LEN, MAX_LEN, PRE = 360, 1500, 3.0
PRESETS = ["game_launch", "phone_call", "heist", "lawsuit", "courtroom_ban", "airport_leave", "birthday", "quiz_game", "rant", "money", "ai_tech", "reaction_video", "date_show", "gaming_fail", "sleeping_drunk"]
HARD = re.compile(r"היטלר|שואה|התאבד|אתיופ|נאצי|גז(?:ים)? יהוד")
def jl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()] if os.path.exists(p) else []
def jf(p, d=None):
    return json.load(open(p)) if os.path.exists(p) else d
def mmss(t): t = int(t); return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}"
def lines(rows, a, b, step=30):
    out, cur, t0 = [], [], None
    for r in rows:
        if r["end"] <= a or r["start"] >= b: continue
        if t0 is None: t0 = r["start"]
        cur.append(r["text"].strip())
        if r["end"] - t0 >= step: out.append(f"[{mmss(t0)}|{int(t0)}] " + " ".join(cur)); cur, t0 = [], None
    if cur: out.append(f"[{mmss(t0)}|{int(t0)}] " + " ".join(cur))
    return out
def ask(system, user):
    body = json.dumps({"model": MODEL, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}], "temperature": 0.3, "max_tokens": 3000, "reasoning_effort": "low"}, ensure_ascii=False)
    hdr = ["-H", "Content-Type: application/json"] + (["-H", "Authorization: Bearer " + os.environ["GROQ_API_KEY"]] if os.environ.get("GROQ_API_KEY") else [])
    for attempt in range(3):
        r = subprocess.run(["curl", "-sS", "-m", "180", "https://api.groq.com/openai/v1/chat/completions"] + hdr + ["-d", body], capture_output=True, text=True)
        try: d = json.loads(r.stdout); return d["choices"][0]["message"]["content"]
        except Exception: print("model error:", r.stdout[:300], r.stderr[:200]); time.sleep(20 * (attempt + 1))
    return None
def snap(rows, a, b):
    """snap start to a sentence start (<= a), end to a sentence end (>= b), 3 s pre-roll"""
    s = max([r["start"] for r in rows if r["start"] <= a], default=a); e = min([r["end"] for r in rows if r["end"] >= b], default=b)
    return max(0, s - PRE), e
def valid_title(t): return 28 <= len(t) <= 60 and t.strip()[-1] in "!?"
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--vod"); ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--state", default=os.environ.get("STATE_DIR", "state")); ap.add_argument("--hold", type=int, default=300); ap.add_argument("--window", type=int, default=4500); a = ap.parse_args()
    ST = os.path.join(ROOT, a.state)
    if os.path.exists(os.path.join(ST, "PAUSE")): print("PAUSE"); return 0
    ing = jf(os.path.join(ST, "ingest_state.json"), {}) or {}; vod = a.vod or ing.get("_current_vod")
    if not vod: print("no vod"); return 0
    rows = jl(os.path.join(ST, "transcripts", f"{vod}.jsonl"))
    if not rows: print("no transcript"); return 0
    pf = os.path.join(ST, "pick_state.json"); ps = jf(pf, {}) or {}; cursor = ps.get(vod, {}).get("cursor", rows[0]["start"])
    end = rows[-1]["end"]; closed = end - a.hold; lo = cursor; hi = min(closed, cursor + a.window)
    if hi - lo < 480: print(f"not enough closed new content ({int(hi - lo)} s)"); return 0
    clipsd = os.path.join(ST, "clips"); done = []
    for d in (os.listdir(clipsd) if os.path.isdir(clipsd) else []):
        c = jf(os.path.join(clipsd, d, "cuts.json"))
        if c and c.get("vod") == vod: done += [(x, y) for p in c.get("pieces", []) for x, y in p.get("keep", [])]
    guide = open(os.path.join(ROOT, "docs", "TOPICS_TO_CLIP.md"), encoding="utf-8").read()
    BUDGET = int(os.environ.get("PICK_TOKEN_BUDGET", "4300"))   # Groq free: 8000 tokens/min including max_tokens(3000)
    est = lambda txt: len(txt) / 2.6
    while hi - lo > 480 and est(guide) + est("\n".join(lines(rows, lo, hi))) + 900 > BUDGET: hi = lo + (hi - lo) * 0.8
    cat = [x for x in jl(os.path.join(ST, "category.jsonl"))][-6:]
    recent = [v["title"] for v in (jf(os.path.join(ROOT, "state", "yt_research", "own.json"), {}) or {}).get("videos", [])][:25]
    system = ("You are the topic editor of the YouTube channel ODED HIGHLIGHTS (clips of the Kick streamer OdedSVR, Hebrew). You get a transcript of a live stream "
              "(ivrit ASR, may contain errors) and decide which COMPLETE topics become long videos. Follow the guide strictly. Reply with JSON only.\n\nGUIDE:\n" + guide)
    user = (f"Transcript window {mmss(lo)} - {mmss(hi)} (stream seconds; each line starts with [h:mm:ss|seconds]). Only topics that END before {int(hi)} s are closed.\n"
            f"Category/title changes (recent): {json.dumps(cat, ensure_ascii=False)}\nRanges already cut (seconds): {done}\nRecent uploaded titles (do not repeat a topic): {json.dumps(recent, ensure_ascii=False)}\n\n"
            + "\n".join(lines(rows, lo, hi)) +
            f"\n\nReturn JSON: {{\"clips\":[{{\"start\":sec,\"end\":sec,\"title\":\"Hebrew 40-55 chars ending ! or ?!\",\"description\":\"2-3 Hebrew sentences\",\"tags\":[...],\"preset\":one of {PRESETS},"
            f"\"head\":\"<=2 Hebrew words\",\"accent\":\"<=2 Hebrew words ending !\",\"brief\":{{\"about\":\"\",\"who\":\"\",\"peak\":\"mm:ss + what\"}},\"exclude\":[[sec,sec]]}}],"
            f"\"next_cursor\":sec (start of the first topic that is still open or unclear; if everything up to {int(hi)} is decided put {int(hi)}),\"notes\":\"why skipped\"}}. "
            f"Each clip {MIN_LEN}-{MAX_LEN} s, ONE topic, no overlap with already cut ranges. Empty clips list is fine and common. Be strict: weak topics are skipped.")
    out = ask(system, user)
    if not out: print("model unavailable: nothing picked"); return 1
    m = re.search(r"\{.*\}", out, re.S)
    try: res = json.loads(m.group(0))
    except Exception: print("bad JSON:", out[:300]); return 1
    made = []
    for c in res.get("clips", []):
        try: s0, e0 = snap(rows, float(c["start"]), float(c["end"]))
        except Exception: continue
        if e0 > closed or e0 - s0 < MIN_LEN or e0 - s0 > MAX_LEN + 120 or any(s0 < y and x < e0 for x, y in done) or not valid_title(c.get("title", "")):
            print("rejected:", c.get("title"), int(s0), int(e0)); continue
        keep = [[s0, e0]]
        text = " ".join(r["text"] for r in rows if r["start"] >= s0 and r["end"] <= e0)
        ex = [list(map(float, x)) for x in c.get("exclude", []) if len(x) == 2]
        for m_ in HARD.finditer(text):   # hard lines: cut the sentence out
            pos = m_.start(); acc = 0; 
            for r in rows:
                if r["start"] >= s0 and r["end"] <= e0:
                    acc += len(r["text"]) + 1
                    if acc > pos: ex.append([r["start"] - 0.5, r["end"] + 0.5]); break
        for x, y in sorted(ex):
            nk = []
            for p, q in keep:
                if y <= p or x >= q: nk.append([p, q])
                else:
                    if x - p > 20: nk.append([p, x])
                    if q - y > 20: nk.append([y, q])
            keep = nk
        if sum(q - p for p, q in keep) < MIN_LEN: print("too short after exclusions:", c["title"]); continue
        cid = f"{vod}_{int(s0)}"; d = os.path.join(clipsd, cid)
        if os.path.exists(os.path.join(d, "spec.json")): continue
        os.makedirs(d, exist_ok=True)
        json.dump({"vod": vod, "base": ing.get("_vod_base"), "pieces": [{"keep": keep, "ch": c.get("brief", {}).get("about", "הנושא")[:40] or "הנושא"}]}, open(os.path.join(d, "cuts.json"), "w"), ensure_ascii=False, indent=1)
        desc = c.get("description", "").strip() + "\n\nהרגעים הכי טובים מהלייב של עודד בקיק | ODED HIGHLIGHTS\n\nהקטע מתוך הלייב של עודד בקיק: https://kick.com/odedsvr\n\n#עודד #OdedSVR #עודדהיילייטס #קיק"
        json.dump({"title": c["title"].strip(), "description": desc, "tags": (c.get("tags") or []) + ["עודד", "OdedSVR", "ODED HIGHLIGHTS"], "preset": c.get("preset") if c.get("preset") in PRESETS else "reaction_video",
                   "head": c.get("head", ""), "accent": c.get("accent", ""), "refs": "shock,excited,smirk", "brief": c.get("brief", {}), "auto": True, "picked_by": MODEL}, open(os.path.join(d, "spec.json"), "w"), ensure_ascii=False, indent=1)
        made.append(cid); print(f"PICKED {cid}: {c['title']} ({int(s0)}-{int(e0)}, {int((e0 - s0) / 60)} min)")
    ps[vod] = {"cursor": max(lo, min(float(res.get("next_cursor", hi) or hi), hi)), "last_run": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "notes": res.get("notes", "")[:300]}
    if not a.dry_run: json.dump(ps, open(pf, "w"), indent=1)
    if made and not a.dry_run and not os.environ.get("NO_DISPATCH"):
        from autopilot import publish
        for cid in made: publish(cid, f"pick: {cid}", False)
    print("cursor ->", int(ps[vod]["cursor"]), "| notes:", res.get("notes", "")[:200]); return 0
if __name__ == "__main__": sys.exit(main())

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
MIN_LEN, MAX_LEN, PRE = 900, 2400, 3.0   # owner rule (15 Nov): every clip 15-40 minutes, a COMPLETE topic
PRESETS = ["game_launch", "phone_call", "heist", "lawsuit", "courtroom_ban", "airport_leave", "birthday", "quiz_game", "rant", "money", "ai_tech", "reaction_video", "date_show", "gaming_fail", "sleeping_drunk"]
DONATION = re.compile(r"תרם |תרמת |תרמו |דונ(?:ייט|יישן|ציה)|גיפט|\d+ דולר|(?:שלושה|חמישה|עשרה|עשרים|חמישים) דולר|קיקס ")   # donation reading (owner rule: never in a clip)
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
def trim_dead_air(rows, keep, gap=5.0, pad_a=0.6, pad_b=0.8, min_seg=12.0):
    """Remove silent gaps (> gap s without speech) from the keep ranges: owner/quality rule = no dead air. Returns the new keep list."""
    out = []
    for a, b in keep:
        rs = [r for r in rows if r["end"] > a and r["start"] < b]
        if not rs: continue
        segs = []; cs, ce = rs[0]["start"], rs[0]["end"]
        for r in rs[1:]:
            if r["start"] - ce > gap: segs.append([cs, ce]); cs = r["start"]
            ce = max(ce, r["end"])
        segs.append([cs, ce])
        for x, y in segs:
            x, y = max(a, x - pad_a), min(b, y + pad_b)
            if out and x - out[-1][1] < 1.5: out[-1][1] = y   # keep adjacent pieces joined
            elif y - x >= min_seg: out.append([x, y])   # a short fragment (a few words) is dropped
    return out
def valid_title(t): return 28 <= len(t) <= 75 and t.strip()[-1] in "!?"
LANG = os.environ.get("PICK_LANG", "he"); CREDIT = os.environ.get("CHANNEL_CREDIT", "עודד (OdedSVR)"); SLUG = os.environ.get("CHANNEL", "odedsvr")

def refine(rows, lo, hi, title, which):
    """exact second where the activity really starts (which='start') or ends ('end') inside a 6-minute edge window, sentence boundary."""
    a, b = (lo - 60, lo + 300) if which == "start" else (hi - 300, hi + 60)
    ls = [f"[{r['start']:.0f}] {r['text'][:140]}" for r in rows if a <= r["start"] <= b]
    if not ls: return lo if which == "start" else hi
    q = (f"Stream transcript lines [second] text. The activity/topic is: '{title}'. Find the second where it really " + ("BEGINS (first sentence that belongs to it; skip waiting, technical issues, unrelated chatter before it)" if which == "start" else "ENDS (last sentence that belongs to it; do not include unrelated talk after it)") +
         ". Reply JSON only: {\"second\": n}\n\n" + "\n".join(ls)[:5000])
    out = ask("You find exact boundaries in a stream transcript. JSON only.", q)
    try:
        sec = float(json.loads(re.search(r"\{.*\}", out, re.S).group(0))["second"])
        return sec if a - 5 <= sec <= b + 5 else (lo if which == "start" else hi)
    except Exception: return lo if which == "start" else hi
def span_meta(rows, keep, title, kind):
    ls = [(r["start"], r["text"]) for r in rows if any(x <= r["start"] < y for x, y in keep)]
    step = max(1, len(ls) // 45); sample = [f"[{t:.0f}] {x[:130]}" for t, x in ls[::step]][:50]
    q = (f"Context: the streamer is ODED (a man, Israeli, Hebrew, Kick streamer OdedSVR); he is live from his home, his wife is sometimes next to him, chat questions are read aloud, the transcript is automatic and contains errors (names/words may be wrong, speakers are not labelled). Write all names in HEBREW letters (עודד, not Oded). Do NOT invent a person (no 'chef', no 'broadcaster'): the main person is Oded and the people he mentions. Clip of Oded's live: activity '{title}' ({kind}). Transcript samples (evenly spread over the whole clip; [second] text):\n" + "\n".join(sample)[:5200] +
         "\n\nReturn JSON only: {\"title\":\"Hebrew 40-70 chars: a short QUOTE from the clip in quotes ending with !, then who + what actually happens (be ACCURATE: only what is really in the clip)\",\"description\":\"2-3 Hebrew sentences, accurate\",\"tags\":[...],\"preset\":\"one of "
         + ",".join(PRESETS) + "\",\"head\":\"<=2 Hebrew words\",\"accent\":\"<=2 Hebrew words ending !\",\"about\":\"one Hebrew sentence: what the clip is about\",\"who\":\"Hebrew names of who appears (e.g. his wife, chat)\",\"peak_second\":n (a [second] from the samples that is the strongest moment)}")
    out = ask("You are the topic editor of an Israeli streamer-highlights YouTube channel. Titles must describe the real content. JSON only.", q)
    try: return json.loads(re.search(r"\{.*\}", out, re.S).group(0))
    except Exception: return None
def span_pick(ST, ing, rows, closed, done, clipsd, vod, ps, dry):
    tf = os.path.join(ST, "timeline.json"); T = jf(tf)
    if not T or T.get("vod") != vod or not T.get("spans"): return None
    seen = ps.setdefault(vod, {}).setdefault("spans_done", []); made = []
    for sp in sorted(T["spans"], key=lambda x: x["from"]):
        key = f"{sp['from']}-{sp['to']}"
        if key in seen or not sp.get("closed") or not sp.get("clip_worthy") or sp["to"] > closed: continue
        dur = sp["to"] - sp["from"]
        if dur < 840: seen.append(key); continue
        if sum(max(0, min(sp["to"], y) - max(sp["from"], x)) for x, y in done) > 0.3 * dur: seen.append(key); print("span overlaps existing clips, skipped:", sp["title"]); continue
        a = refine(rows, sp["from"], sp["to"], sp["title"], "start"); b = refine(rows, sp["from"], sp["to"], sp["title"], "end")
        if b - a < 840: a, b = sp["from"], sp["to"]
        parts = max(1, -(-int(b - a) // MAX_LEN)); step = (b - a) / parts; got = False
        for i in range(parts):
            lo, hi = a + i * step, a + (i + 1) * step
            rs = [r for r in rows if r["start"] >= lo and r["end"] <= hi + 2]
            if not rs: continue
            s0, e0 = max(0.0, rs[0]["start"] - PRE), rs[-1]["end"]; keep = [[s0, e0]]
            text = " ".join(r["text"] for r in rs); ex = []
            for m_ in list(HARD.finditer(text)) + list(DONATION.finditer(text)):
                acc = 0
                for r in rs:
                    acc += len(r["text"]) + 1
                    if acc > m_.start(): ex.append([r["start"] - 0.4, r["end"] + 0.4]); break
            for x, y in sorted(ex):
                nk = []
                for p0, q0 in keep:
                    if y <= p0 or x >= q0: nk.append([p0, q0])
                    else:
                        if x - p0 > 5: nk.append([p0, x])
                        if q0 - y > 5: nk.append([y, q0])
                keep = nk
            keep = trim_dead_air(rows, keep, gap=7.0, min_seg=10.0); tot = sum(q0 - p0 for p0, q0 in keep)
            if tot < 900: print(f"span '{sp['title']}' only {int(tot)} s after cleaning (<15 min): skipped"); __import__("events").event("pick_skip", f"🔎 הנושא \"{sp['title']}\" ({int(dur / 60)} דק׳) יצא {int(tot / 60)} דק׳ אחרי ניקוי שקטים ודונייטים, פחות מ-15: לא נחתך."); continue
            meta = None
            for _try in range(3):
                m_ = span_meta(rows, keep, sp["title"], sp["kind"])
                if m_ and m_.get("title"):
                    t_ = m_["title"].strip()
                    if t_[-1] not in "!?": t_ += "!"
                    m_["title"] = t_
                    if valid_title(t_): meta = m_; break
                    print("title rejected:", len(t_), t_[:80])
            if not meta: print("meta/title failed for", sp["title"]); continue
            title = meta["title"].strip() + (f" (חלק {i + 1}/{parts})" if parts > 1 else "")
            cid = f"{vod}_{int(s0)}"; d = os.path.join(clipsd, cid)
            if os.path.exists(os.path.join(d, "spec.json")): continue
            os.makedirs(d, exist_ok=True)
            json.dump({"vod": vod, "base": ing.get("_vod_base"), "pieces": [{"keep": [[round(x, 2), round(y, 2)] for x, y in keep], "ch": (meta.get("about") or sp["title"])[:40]}]}, open(os.path.join(d, "cuts.json"), "w"), ensure_ascii=False, indent=1)
            acc, pv = 0.0, None
            for x, y in keep:
                if x <= float(meta.get("peak_second", -1)) <= y: pv = acc + (float(meta["peak_second"]) - x) + 11.2
                acc += y - x
            peak = f"{int(pv // 60):02d}:{int(pv % 60):02d}" if pv is not None else ""
            desc = meta.get("description", "").strip() + "\n\nהרגעים הכי טובים מהלייב של עודד בקיק | ODED HIGHLIGHTS\n\nהקטע מתוך הלייב של עודד בקיק: https://kick.com/odedsvr\n\n#עודד #OdedSVR #עודדהיילייטס #קיק"
            aff = os.path.join(ROOT, "config", "affiliate.txt")
            if os.path.exists(aff): desc += "\n\n" + open(aff, encoding="utf-8").read().strip()
            json.dump({"title": title, "description": desc, "tags": (meta.get("tags") or []) + ["עודד", "OdedSVR", "ODED HIGHLIGHTS"], "preset": meta.get("preset") if meta.get("preset") in PRESETS else "reaction_video",
                       "head": meta.get("head", ""), "accent": meta.get("accent", ""), "refs": "shock,excited,smirk", "brief": {"about": meta.get("about", ""), "who": meta.get("who", "עודד"), "peak": peak}, "lang": LANG, "auto": True, "picked_by": "span:" + MODEL, "span": sp["title"]},
                      open(os.path.join(d, "spec.json"), "w"), ensure_ascii=False, indent=1)
            made.append(cid); got = True; done.append((s0, e0))
            __import__("events").event("pick", f"נבחר נושא לקליפ: {title} ({int(tot / 60)} דק׳, מתוך {sp['title']}). רינדור בדרך.", clip=cid); print(f"PICKED {cid}: {title} ({int(tot / 60)} min)")
        seen.append(key)
    ps[vod]["last_run"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if not dry: json.dump(ps, open(os.path.join(ST, "pick_state.json"), "w"), indent=1)
    if made and not dry and not os.environ.get("NO_DISPATCH"):
        from autopilot import publish
        for cid in made: publish(cid, f"pick: {cid}", False)
    return made
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
    clipsd = os.path.join(ST, "clips"); done = []
    for d_ in (os.listdir(clipsd) if os.path.isdir(clipsd) else []):
        c_ = jf(os.path.join(clipsd, d_, "cuts.json"))
        if c_ and c_.get("vod") == vod: done += [(x, y) for p_ in c_.get("pieces", []) for x, y in p_.get("keep", [])]
    _r = span_pick(ST, ing, rows, closed, done, clipsd, vod, ps, a.dry_run)   # topic-span picker (15-40 min complete topics); None = no timeline yet -> old window picker
    if _r is not None: print("span picker done:", len(_r), "clip(s)"); return 0
    if hi - lo < 480: print(f"not enough closed new content ({int(hi - lo)} s)"); return 0
    clipsd = os.path.join(ST, "clips"); done = []
    for d in (os.listdir(clipsd) if os.path.isdir(clipsd) else []):
        c = jf(os.path.join(clipsd, d, "cuts.json"))
        if c and c.get("vod") == vod: done += [(x, y) for p in c.get("pieces", []) for x, y in p.get("keep", [])]
    guide = open(os.path.join(ROOT, "docs", "TOPICS_TO_CLIP.md"), encoding="utf-8").read() + "\n\nSTYLE (from the best channels): " + open(os.path.join(ROOT, "docs", "CLIP_STYLE.md"), encoding="utf-8").read().split("## Rules we take from it")[-1]
    BUDGET = int(os.environ.get("PICK_TOKEN_BUDGET", "4300"))   # Groq free: 8000 tokens/min including max_tokens(3000)
    est = lambda txt: len(txt) / 2.6
    while hi - lo > 480 and est(guide) + est("\n".join(lines(rows, lo, hi))) + 900 > BUDGET: hi = lo + (hi - lo) * 0.8
    cat = [x for x in jl(os.path.join(ST, "category.jsonl"))][-6:]
    recent = [v["title"] for v in (jf(os.path.join(ROOT, "state", "yt_research", "own.json"), {}) or {}).get("videos", [])][:25]
    L = (jf(os.path.join(ROOT, "state", "lessons.json"), []) or [])[-12:]
    ins = open(os.path.join(ROOT, "state", "chat_instructions.md"), encoding="utf-8").read()[-1200:] if os.path.exists(os.path.join(ROOT, "state", "chat_instructions.md")) else ""
    guide += ("\n\nLESSONS LEARNED (from deleted drafts, weak videos, quality failures; obey):\n" + "\n".join("- " + x["text"] for x in L) if L else "") + (("\n\nOWNER INSTRUCTIONS (from the app chat):\n" + ins) if ins.strip() else "")
    system = (f"You are the topic editor of a YouTube clips channel (clips of the Kick streamer {SLUG}; language: {LANG}). " + ("Write ALL titles and descriptions in ENGLISH. " if LANG == "en" else "") + "You get a transcript of a live stream "
              "(ivrit ASR, may contain errors) and decide which COMPLETE topics become long videos. Follow the guide strictly. Reply with JSON only.\n\nGUIDE:\n" + guide)
    user = (f"Transcript window {mmss(lo)} - {mmss(hi)} (stream seconds; each line starts with [h:mm:ss|seconds]). Only topics that END before {int(hi)} s are closed.\n"
            f"Category/title changes (recent): {json.dumps(cat, ensure_ascii=False)}\nRanges already cut (seconds): {done}\nRecent uploaded titles (do not repeat a topic): {json.dumps(recent, ensure_ascii=False)}\n\n"
            + "\n".join(lines(rows, lo, hi)) +
            f"\n\nReturn JSON: {{\"clips\":[{{\"start\":sec,\"end\":sec,\"title\":\"" + ("English" if LANG == "en" else "Hebrew") + " 40-70 chars: a short QUOTE from the clip in quotes ending with !, then who + what (names of the people)\",\"description\":\"2-3 Hebrew sentences\",\"tags\":[...],\"preset\":one of {PRESETS},"
            f"\"head\":\"<=2 Hebrew words\",\"accent\":\"<=2 Hebrew words ending !\",\"brief\":{{\"about\":\"\",\"who\":\"\",\"peak\":\"mm:ss + what\"}},\"exclude\":[[sec,sec]]}}],"
            f"\"next_cursor\":sec (start of the first topic that is still open or unclear; if everything up to {int(hi)} is decided put {int(hi)}),\"notes\":\"why skipped\"}}. "
            f"Each clip {MIN_LEN}-{MAX_LEN} s, ONE topic, no overlap with already cut ranges. Empty clips list is fine and common. Be strict: weak topics are skipped.")
    try:
        import topic_scan; sp = [(int(t), round(z, 1)) for t, z in topic_scan.chat_spikes(ing.get("_vod_start_epoch")) if lo <= t <= hi]
        if sp: user += f"\nChat reaction spikes (stream second, z-score; strong = audience reacted): {sorted(sp, key=lambda x: -x[1])[:8]}"
    except Exception as e: print("chat spikes unavailable:", e)
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
        for m_ in list(HARD.finditer(text)) + list(DONATION.finditer(text)):   # hard lines: cut the sentence out
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
        keep = trim_dead_air(rows, keep)
        if sum(q - p for p, q in keep) < 300: print("too short after exclusions / dead air:", c["title"]); continue
        cid = f"{vod}_{int(s0)}"; d = os.path.join(clipsd, cid)
        if os.path.exists(os.path.join(d, "spec.json")): continue
        os.makedirs(d, exist_ok=True)
        json.dump({"vod": vod, "base": ing.get("_vod_base"), "pieces": [{"keep": keep, "ch": c.get("brief", {}).get("about", "הנושא")[:40] or "הנושא"}]}, open(os.path.join(d, "cuts.json"), "w"), ensure_ascii=False, indent=1)
        desc = c.get("description", "").strip() + (f"\n\nClip from {CREDIT}'s live on Kick: https://kick.com/{SLUG}\n\n#{SLUG} #kick #streamer #highlights" if LANG == "en" else "\n\nהרגעים הכי טובים מהלייב של עודד בקיק | ODED HIGHLIGHTS\n\nהקטע מתוך הלייב של עודד בקיק: https://kick.com/odedsvr\n\n#עודד #OdedSVR #עודדהיילייטס #קיק")
        aff = os.path.join(ROOT, "config", "affiliate.txt")
        if os.path.exists(aff): desc += "\n\n" + open(aff, encoding="utf-8").read().strip()
        json.dump({"title": c["title"].strip(), "description": desc, "tags": (c.get("tags") or []) + ["עודד", "OdedSVR", "ODED HIGHLIGHTS"], "preset": c.get("preset") if c.get("preset") in PRESETS else "reaction_video",
                   "head": c.get("head", ""), "accent": c.get("accent", ""), "refs": "shock,excited,smirk", "brief": c.get("brief", {}), "lang": LANG, "auto": True, "picked_by": MODEL}, open(os.path.join(d, "spec.json"), "w"), ensure_ascii=False, indent=1)
        made.append(cid); (__import__("events").event("pick", f"נבחר נושא לקליפ: {c['title']} ({int((e0 - s0) / 60)} דק׳). רינדור בדרך." , clip=cid)); print(f"PICKED {cid}: {c['title']} ({int(s0)}-{int(e0)}, {int((e0 - s0) / 60)} min)")
    ps[vod] = {"cursor": max(lo, min(float(res.get("next_cursor", hi) or hi), hi)), "last_run": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "notes": res.get("notes", "")[:300]}
    if not a.dry_run: json.dump(ps, open(pf, "w"), indent=1)
    if not made and not a.dry_run and res.get("notes"): __import__("events").event("pick_skip", f"🔎 בדקתי את דקות {int(lo // 60)}-{int(hi // 60)} בשידור: לא נבחר נושא. {str(res.get('notes'))[:110]}")
    if made and not a.dry_run and not os.environ.get("NO_DISPATCH"):
        from autopilot import publish
        for cid in made: publish(cid, f"pick: {cid}", False)
    print("cursor ->", int(ps[vod]["cursor"]), "| notes:", res.get("notes", "")[:200]); return 0
if __name__ == "__main__": sys.exit(main())

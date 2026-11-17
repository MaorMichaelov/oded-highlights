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
MIN_LEN, MAX_LEN, PRE = 900, 2400, 1.0   # pre-roll before the first sentence: 3.0 s used to include the tail of the previous topic (owner: precision of the start)
MAX_SESSION = 7200   # a great SESSION (game, challenge, pack opening, event, guest) is kept whole up to 60 min: viewers ask for the full thing (owner, 15 Nov)   # owner rule (15 Nov): every clip 15-40 minutes, a COMPLETE topic
PRESETS = ["game_launch", "phone_call", "heist", "lawsuit", "courtroom_ban", "airport_leave", "birthday", "quiz_game", "rant", "money", "ai_tech", "reaction_video", "date_show", "gaming_fail", "sleeping_drunk"]
DONATION = re.compile(r"תרם |תרמת |תרמו |דונ(?:ייט|יישן|ציה)|גיפט|\d+ דולר|(?:שלושה|חמישה|עשרה|עשרים|חמישים) דולר|קיקס ")   # donation reading (owner rule: never in a clip)
HARD = re.compile(r"היטלר|שואה|התאבד|אתיופ|נאצי|גז(?:ים)? יהוד|יותר שחורים|כושי|בית זונות|שרמוט|יכול לי למות|לך למות")   # + lines Grok flagged in the GTA 6 reaction review (15 Nov)
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
def gemini_ask(system, user):
    """Fallback when the shared free Groq quota is exhausted: Gemini (free key, GEMINI_API_KEY secret)."""
    key = os.environ.get("GEMINI_API_KEY")
    if not key: return None
    body = json.dumps({"systemInstruction": {"parts": [{"text": system}]}, "contents": [{"parts": [{"text": user}]}], "generationConfig": {"temperature": 0.3, "maxOutputTokens": 4000}}, ensure_ascii=False)
    for model in ("gemini-flash-latest", "gemini-3.5-flash"):
        r = subprocess.run(["curl", "-sS", "-m", "120", f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent", "-H", "x-goog-api-key: " + key, "-H", "Content-Type: application/json", "-d", body], capture_output=True, text=True)
        try: return "".join(p_.get("text", "") for p_ in json.loads(r.stdout)["candidates"][0]["content"]["parts"])
        except Exception: print("gemini error:", r.stdout[:200])
    return None
def ask(system, user):
    body = json.dumps({"model": MODEL, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}], "temperature": 0.3, "max_tokens": 3000, "reasoning_effort": "low"}, ensure_ascii=False)
    hdr = ["-H", "Content-Type: application/json"] + (["-H", "Authorization: Bearer " + os.environ["GROQ_API_KEY"]] if os.environ.get("GROQ_API_KEY") else [])
    for attempt in range(3):
        r = subprocess.run(["curl", "-sS", "-m", "180", "https://api.groq.com/openai/v1/chat/completions"] + hdr + ["-d", body], capture_output=True, text=True)
        try: d = json.loads(r.stdout); return d["choices"][0]["message"]["content"]
        except Exception:
            print("model error:", r.stdout[:300], r.stderr[:200])
            if attempt == 1:
                g = gemini_ask(system, user)
                if g: return g
            time.sleep(20 * (attempt + 1))
    return gemini_ask(system, user)
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
BAN_WORDS = re.compile(r"אוטי|מפגר|מוגבל")   # derogatory slang the streamer uses: never in a title/description (channel safety)
def valid_title(t): return 28 <= len(t) <= 75 and t.strip()[-1] in "!?" and not BAN_WORDS.search(t)
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
def offtopic_cuts(rows, keep, title):
    """Reaction clips must contain ONLY the reaction (Grok review, 15 Nov: drama with a viewer, IRL/dog/shirt chatter and a 100 s dead stretch inside a GTA 6 reaction got the draft rejected). One cheap LLM pass lists the stretches (>=20 s) that are NOT about reacting to the video/article; they are cut, at most 40% of the clip."""
    ls = [f"[{r['start']:.0f}] {r['text'][:90]}" for r in rows if any(x <= r["start"] < y for x, y in keep)]
    if len(ls) < 12: return []
    step = max(1, len(ls) // 110)
    q = (f"Transcript lines [second] of a stream stretch where the streamer reacts to: '{title}'. List the stretches of at least 20 seconds that are NOT part of the reaction to that video/article/trailer: personal drama with a specific viewer, IRL / shopping / pets / shirt-sale chatter, donation thanks, technical problems. "
         "Never include a stretch that is a funny comment about the video. Reply JSON only: {\"cut\":[[from_second,to_second],...]} (empty list if the whole thing is on topic)\n\n" + "\n".join(ls[::step])[:7500])
    out = ask("You are a strict video editor. JSON only.", q)
    try:
        cs = [[float(a), float(b)] for a, b in json.loads(re.search(r"\{.*\}", out, re.S).group(0))["cut"] if float(b) - float(a) >= 20]
    except Exception: return []
    tot = sum(y - x for x, y in keep)
    return cs if sum(b - a for a, b in cs) <= 0.4 * tot else []
def span_meta(rows, keep, title, kind, funny=()):
    ls = [(r["start"], r["text"]) for r in rows if any(x <= r["start"] < y for x, y in keep)]
    step = max(1, len(ls) // 45); sample = [f"[{t:.0f}] {x[:130]}" for t, x in ls[::step]][:50]
    fl = [f"[{t:.0f}] {x[:130]}" for t, x in funny][:8]
    q = (("FUNNIEST MOMENTS (the chat exploded right after these lines; the title QUOTE and peak_second must come from these if one is a complete, meaningful, funny or dramatic sentence; otherwise NO quote, a descriptive title only):\n" + "\n".join(fl) + "\n\n" if fl else "") + f"Context: the streamer is ODED (a man, Israeli, Hebrew, Kick streamer OdedSVR); he is live from his home, his wife is sometimes next to him, chat questions are read aloud, the transcript is automatic and contains errors (names/words may be wrong, speakers are not labelled). Write all names in HEBREW letters (עודד, not Oded). Do NOT invent a person (no 'chef', no 'broadcaster'): the main person is Oded and the people he mentions. Clip of Oded's live: activity '{title}' ({kind}). Transcript samples (evenly spread over the whole clip; [second] text):\n" + "\n".join(sample)[:5200] +
         "\n\nReturn JSON only: {\"title\":\"Hebrew 40-70 chars: a short QUOTE from the clip in quotes ending with !, then who + what actually happens (be ACCURATE: only what is really in the clip)\",\"description\":\"2-3 Hebrew sentences with SPECIFICS (who, what they do, key moments); accurate, like: עודד, סנסי וחברים עוברים לשרת חדש ברוב ראן ומתחילים מאפס: פורצים לבתים, גונבים קרגו ובונים מארב על הגשר.\",\"seo_line\":\"one line: עודד SVR משחק/עושה X | X in English | 2-3 keywords\",\"hashtags\":[\"#עודד\",\"#OdedSVR\", ...3-6 more: game / people / topic in Hebrew and English],\"tags\":[...],\"preset\":\"one of "
         + ",".join(PRESETS) + "\",\"head\":\"<=2 Hebrew words\",\"accent\":\"<=2 Hebrew words ending !\",\"chapters\":[{\"second\":n,\"title\":\"<=6 specific Hebrew words (a name, a quote or what happens)\"}] (6-12 entries IN ORDER covering the whole clip, [second] values taken from the samples, the first one at the clip start; a reaction needs one about every minute, a long game/event/guest session one about every 3-5 minutes; like the streamer channel: 'חדשות 13: אחרי 13 שנים GTA 6 מגיע', 'וייס סיטי והמחיר בישראל', 'מה הקשר מחשבים?!'),\"about\":\"one Hebrew sentence: what the clip is about\",\"who\":\"Hebrew names of who appears (e.g. his wife, chat)\",\"peak_second\":n (a [second] from the samples that is the strongest moment)}")
    if kind == "reaction": q += "\n\nTITLE STYLE for a reaction (copy the streamer's own channel): עודד מגיב ל\"<שם הסרטון/הכתבה שהוא צופה בו>\" של <שם היוצר>  (e.g. עודד מגיב ל\"זייפתי לייבים של סטרימרים מפורסמים\" של מרסי). Use it only when the video name and creator are clearly in the transcript (a news report: name the outlet, e.g. חדשות 13; a YouTuber: the creator); otherwise a quote + who + what title. One clip = ONE source video/article: if the stretch mixes two different reports, describe only the main one. In the description name the source and what is said in it with specifics (see docs/GROK_EXAMPLES.md style)."
    if kind in ("game", "event"): q += "\n\nTITLE STYLE for a game session (the streamer's own channel): a strong judgement/quote ending with ! then the game name in parentheses, e.g. זה המשחק הכי חולני ששיחקתי! (Can Em All). Put the game name only if it is clearly in the transcript."
    out = ask("You are the topic editor of an Israeli streamer-highlights YouTube channel. Titles must describe the real content. JSON only.", q)
    try: return json.loads(re.search(r"\{.*\}", out, re.S).group(0))
    except Exception: return None
def span_pick(ST, ing, rows, closed, done, clipsd, vod, ps, dry):
    tf = os.path.join(ST, "timeline.json"); T = jf(tf)
    if not T or T.get("vod") != vod or not T.get("spans"): return None
    if ps.setdefault(vod, {}).get("seg_v") != T.get("seg_v"): ps[vod]["spans_done"] = []; ps[vod]["seg_v"] = T.get("seg_v")   # re-evaluate spans after the criteria changed (overlap with existing clips is still checked)
    seen = ps[vod].setdefault("spans_done", []); made = []
    SESS = ("game", "event", "guest", "call", "reaction")
    sp_all = sorted(T["spans"], key=lambda x: x["from"]); mg = []
    for x in sp_all:   # one game / event / guest session = ONE video: join its consecutive spans (the segmenter cuts every ~15 min), bridging short chat/idle gaps (owner, 15 Nov: 1.5 h of game must be 40+ min clips, not 15)
        if mg and x["kind"] in SESS:
            j = len(mg) - 1
            while j >= 0 and mg[j]["kind"] in ("chat", "idle") and mg[j]["to"] - mg[j]["from"] <= 360: j -= 1
            if j >= 0 and mg[j]["kind"] == x["kind"]:
                mg[j] = dict(mg[j], to=x["to"], closed=x.get("closed"), clip_worthy=True, title=mg[j]["title"]); del mg[j + 1:]; continue
        mg.append(dict(x))
    try:   # spans forced by the owner/by me (state/forced_spans.json: [{"vod":..,"from":s,"to":s,"kind":..,"title":..,"min":s}]): a topic the owner asked for is cut even when shorter than 15 min
        for f_ in json.load(open(os.path.join(ST, "forced_spans.json"))):
            if str(f_.get("vod")) == str(vod): mg.append(dict(f_, closed=True, clip_worthy=True, forced=True))
    except Exception: pass
    for sp in mg:
        key = f"{sp['from']}-{sp['to']}"
        if key in seen or not sp.get("closed") or not sp.get("clip_worthy") or sp["to"] > closed: continue
        dur = sp["to"] - sp["from"]; mn = sp.get("min") or (360 if sp.get("kind") == "reaction" else 900)   # owner (15 Nov): a reaction to articles/videos of other creators is wanted even at 6-8 min, few cuts
        if dur < mn - 60: seen.append(key); continue
        if not sp.get("forced") and sum(max(0, min(sp["to"], y) - max(sp["from"], x)) for x, y in done) > 0.3 * dur: seen.append(key); print("span overlaps existing clips, skipped:", sp["title"]); continue
        a, b = (sp["from"], sp["to"]) if sp.get("forced") else (refine(rows, sp["from"], sp["to"], sp["title"], "start"), refine(rows, sp["from"], sp["to"], sp["title"], "end"))
        if b - a < mn - 60: a, b = sp["from"], sp["to"]
        mx = MAX_SESSION if sp.get("kind") in ("game", "event", "guest", "call", "reaction") else MAX_LEN
        if mx == MAX_LEN and b - a < 1100:   # cleaning (silence/donations) shaves 10-20%: a 14-18 min topic used to fall under 15 min and be skipped, so give it the missing tail (the stream continues) instead of losing the clip
            b2 = min(closed, b + (1100 - (b - a)))
            if not any(a < y and x < b2 for x, y in done): b = b2
        parts = max(1, -(-int(b - a) // mx)); step = (b - a) / parts; got = False; failed = False
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
            if sp.get("kind") == "reaction" and not sp.get("forced"):
                ex += [[a_, b_] for a_, b_ in offtopic_cuts(rows, keep, sp["title"])]   # remove drama/IRL/chatter inside the reaction
            for x, y in sorted(ex):
                nk = []
                for p0, q0 in keep:
                    if y <= p0 or x >= q0: nk.append([p0, q0])
                    else:
                        if x - p0 > 5: nk.append([p0, x])
                        if q0 - y > 5: nk.append([y, q0])
                keep = nk
            if sp.get("kind") not in ("reaction", "game", "event"): keep = trim_dead_air(rows, keep, gap=10.0, min_seg=10.0)
            elif sp.get("kind") in ("game", "event"): keep = trim_dead_air(rows, keep, gap=45.0, min_seg=30.0)   # one game session = ONE video; only long (45 s+) speechless stretches (stuck game, waiting) are cut (Grok/owner review, 15 Nov)   # reactions: his silence is the video he watches; real silence is removed from the audio in the cut station
            tot = sum(q0 - p0 for p0, q0 in keep)
            if tot < mn: print(f"span '{sp['title']}' only {int(tot)} s after cleaning (<15 min): skipped"); __import__("events").event("pick_skip", f"🔎 הנושא \"{sp['title']}\" ({int(dur / 60)} דק׳) יצא {int(tot / 60)} דק׳ אחרי ניקוי שקטים ודונייטים, פחות מ-15: לא נחתך."); continue
            try:
                sys.path.insert(0, os.path.dirname(HERE)); import topic_scan as _ts
                sps = [t_ for t_, z_ in _ts.chat_spikes(ing.get("_vod_start_epoch")) if z_ >= 2.3 and any(x_ <= t_ <= y_ for x_, y_ in keep)]
            except Exception: sps = None
            if sps is not None and not sps and sp.get("kind") not in ("game", "reaction", "guest", "call", "event"):   # review rule: a clip needs a PEAK (the audience reacted somewhere), no raw stretches
                print(f"span '{sp['title']}' has no chat peak: skipped"); __import__("events").event("pick_skip", f"🔎 הנושא \"{sp['title']}\" ({int(tot / 60)} דק׳) בלי שיא בצ'אט (שום רגע שהקהל הגיב אליו): לא נחתך, כדי לא להעלות סטרים גולמי."); continue
            funny = [(r["start"], r["text"]) for r in rows if sps and any(abs(r["start"] - t_) <= 6 for t_ in sps) and any(x_ <= r["start"] <= y_ for x_, y_ in keep)]
            meta = None
            for _try in range(3):
                m_ = span_meta(rows, keep, sp["title"], sp["kind"], funny)
                if m_ and m_.get("title"):
                    t_ = m_["title"].strip()
                    if t_[-1] not in "!?": t_ += "!"
                    m_["title"] = t_
                    import re as _re
                    q_ = _re.search(r"[\"“”״]([^\"“”״]{4,60})[\"“”״]", t_)
                    norm = lambda z: _re.sub(r"[^\u0590-\u05FFa-zA-Z0-9 ]", "", z).strip()
                    full = norm(" ".join(r["text"] for r in rs))
                    if q_ and norm(q_.group(1)) not in full:   # the quoted phrase is not in the clip (ASR/LLM invention): drop it, keep who + what
                        rest = _re.sub(r"^[\s–\-]+", "", t_.replace(q_.group(0), "", 1)).strip(); print("quote not in transcript, dropped:", q_.group(1)); t_ = rest if rest[-1:] in "!?" else rest + "!"; m_["title"] = t_
                    if valid_title(t_): meta = m_; break
                    print("title rejected:", len(t_), t_[:80])
            if not meta: print("meta/title failed for", sp["title"]); failed = True; continue
            title = meta["title"].strip() + (f" (חלק {i + 1}/{parts})" if parts > 1 else "")
            cid = f"{vod}_{int(s0)}"; d = os.path.join(clipsd, cid)
            if os.path.exists(os.path.join(d, "spec.json")): continue
            os.makedirs(d, exist_ok=True)
            pieces = []; chs = (T.get("chunks") or {})
            for c_ in range(int(keep[0][0] // 300), int(keep[-1][1] // 300) + 1):
                sub = [[max(x, c_ * 300), min(y, (c_ + 1) * 300)] for x, y in keep if min(y, (c_ + 1) * 300) - max(x, c_ * 300) > 0.5]
                if not sub: continue
                lab = (chs.get(str(c_), {}).get("label") or meta.get("about") or sp["title"])[:40]
                if pieces and (pieces[-1]["ch"] == lab or sum(y - x for x, y in sub) < 25): pieces[-1]["keep"] += sub   # same topic (or a tiny tail) stays in the previous chapter
                else: pieces.append({"keep": sub, "ch": lab})
            if len(pieces) < 3: pieces = [{"keep": keep, "ch": (meta.get("about") or sp["title"])[:40]}]
            try:   # fine chapters from the LLM (Grok's uploads have a chapter every ~1 min with real names): split the kept ranges at the chapter seconds
                chp = sorted({int(float(c_["second"])): str(c_["title"]).strip()[:45] for c_ in (meta.get("chapters") or []) if str(c_.get("title", "")).strip()}.items())
                chp = [(t_, n_) for t_, n_ in chp if keep[0][0] - 1 <= t_ <= keep[-1][1]]
                if len(chp) >= 4:
                    chp[0] = (keep[0][0], chp[0][1]); np_ = []
                    for k_, (t_, n_) in enumerate(chp):
                        t2 = chp[k_ + 1][0] if k_ + 1 < len(chp) else keep[-1][1] + 1
                        sub = [[max(x, t_), min(y, t2)] for x, y in keep if min(y, t2) - max(x, t_) > 0.5]
                        if sub and sum(y - x for x, y in sub) >= 12: np_.append({"keep": sub, "ch": n_})
                        elif sub and np_: np_[-1]["keep"] += sub
                    if len(np_) >= 4: pieces = np_
            except Exception as e_: print("chapters from LLM failed:", e_)
            json.dump({"vod": vod, "base": ing.get("_vod_base"), **({"silence": [25]} if sp.get("kind") in ("game", "reaction", "event") else {}), "pieces": [{"keep": [[round(x, 2), round(y, 2)] for x, y in pc["keep"]], "ch": pc["ch"]} for pc in pieces]}, open(os.path.join(d, "cuts.json"), "w"), ensure_ascii=False, indent=1)   # games/reactions: continuous, only silences >= 25 s are removed
            acc, pv = 0.0, None
            for x, y in keep:
                if x <= float(meta.get("peak_second", -1)) <= y: pv = acc + (float(meta["peak_second"]) - x) + 11.2
                acc += y - x
            peak = f"{int(pv // 60):02d}:{int(pv % 60):02d}" if pv is not None else ""
            hs = [h for h in (meta.get("hashtags") or []) if isinstance(h, str) and h.startswith("#")][:8]
            hs = list(dict.fromkeys(hs + ["#עודד", "#OdedSVR", "#עודדהיילייטס", "#ODEDHIGHLIGHTS", "#קיק", "#Kick", "#סטרימרישראלי"]))   # the channel's own best-performing description format
            desc = "קטעים מהלייב של עודד (OdedSVR) ב-Kick: https://kick.com/odedsvr | ערוץ מעריצים לא רשמי.\n" + meta.get("description", "").strip() + ("\n" + meta["seo_line"].strip() if meta.get("seo_line") else "") + "\nהרגעים הכי טובים מהלייב של עודד בקיק | ODED HIGHLIGHTS\n\nהקטע מתוך הלייב של עודד בקיק: https://kick.com/odedsvr\nערוץ מעריצים לא רשמי: כל הקטעים נלקחו מהשידורים של עודד (OdedSVR) בקיק, וזה אינו הערוץ הרשמי של עודד. הערוץ הרשמי: https://www.youtube.com/@OdedSVRLive\n\n" + " ".join(hs)
            desc = "\n".join(" ".join(x_ for x_ in re.split(r"(?<=[.!?])\s+", ln_) if not BAN_WORDS.search(x_)) for ln_ in desc.split("\n"))
            aff = os.path.join(ROOT, "config", "affiliate.txt")
            if os.path.exists(aff): desc += "\n\n" + open(aff, encoding="utf-8").read().strip()
            json.dump({"title": title, "description": desc, "tags": (meta.get("tags") or []) + ["עודד", "OdedSVR", "ODED HIGHLIGHTS"], "preset": meta.get("preset") if meta.get("preset") in PRESETS else "reaction_video",
                       "head": meta.get("head", ""), "accent": meta.get("accent", ""), "refs": "shock,excited,smirk", "brief": {"about": meta.get("about", ""), "who": meta.get("who", "עודד"), "peak": peak}, "lang": LANG, "auto": True, "picked_by": "span:" + MODEL, "span": sp["title"]},
                      open(os.path.join(d, "spec.json"), "w"), ensure_ascii=False, indent=1)
            made.append(cid); got = True; done.append((s0, e0))
            __import__("events").event("pick", f"נבחר נושא לקליפ: {title} ({int(tot / 60)} דק׳, מתוך {sp['title']}). רינדור בדרך.", clip=cid); print(f"PICKED {cid}: {title} ({int(tot / 60)} min)")
        rt = ps[vod].setdefault("retry", {}); rt[key] = rt.get(key, 0) + (1 if failed else 0)
        if not failed or rt[key] >= 4: seen.append(key)   # a part whose title/meta failed is retried (max 4 times) instead of being lost silently: the other parts of the session were cut, this one must not vanish
        elif failed: print("will retry span", key, rt[key])
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
        desc = c.get("description", "").strip() + (f"\n\nClip from {CREDIT}'s live on Kick: https://kick.com/{SLUG}\n\n#{SLUG} #kick #streamer #highlights" if LANG == "en" else "\n\nהרגעים הכי טובים מהלייב של עודד בקיק | ODED HIGHLIGHTS\n\nהקטע מתוך הלייב של עודד בקיק: https://kick.com/odedsvr\nערוץ מעריצים לא רשמי: כל הקטעים נלקחו מהשידורים של עודד (OdedSVR) בקיק, וזה אינו הערוץ הרשמי של עודד. הערוץ הרשמי: https://www.youtube.com/@OdedSVRLive\n\n#עודד #OdedSVR #עודדהיילייטס #קיק")
        aff = os.path.join(ROOT, "config", "affiliate.txt")
        if os.path.exists(aff): desc += "\n\n" + open(aff, encoding="utf-8").read().strip()
        json.dump({"title": c["title"].strip(), "description": desc, "tags": (c.get("tags") or []) + ["עודד", "OdedSVR", "ODED HIGHLIGHTS"], "preset": c.get("preset") if c.get("preset") in PRESETS else "reaction_video",
                   "head": c.get("head", ""), "accent": c.get("accent", ""), "refs": "shock,excited,smirk", "brief": c.get("brief", {}), "lang": LANG, "auto": True, "picked_by": MODEL}, open(os.path.join(d, "spec.json"), "w"), ensure_ascii=False, indent=1)
        made.append(cid); (__import__("events").event("pick", f"נבחר נושא לקליפ: {c['title']} ({int((e0 - s0) / 60)} דק׳). רינדור בדרך." , clip=cid)); print(f"PICKED {cid}: {c['title']} ({int(s0)}-{int(e0)}, {int((e0 - s0) / 60)} min)")
    ps[vod] = {"cursor": max(lo, min(float(res.get("next_cursor", hi) or hi), hi)), "last_run": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "notes": res.get("notes", "")[:300]}
    if not a.dry_run: json.dump(ps, open(pf, "w"), indent=1)
    if not made and not a.dry_run and res.get("notes"): __import__("events").event("pick_skip", f"🔎 בדקתי את דקות {int(lo // 60)}-{int(hi // 60)} בשידור: אין שם נושא שלם של 15 דקות ומעלה.")
    if made and not a.dry_run and not os.environ.get("NO_DISPATCH"):
        from autopilot import publish
        for cid in made: publish(cid, f"pick: {cid}", False)
    print("cursor ->", int(ps[vod]["cursor"]), "| notes:", res.get("notes", "")[:200]); return 0
if __name__ == "__main__": sys.exit(main())

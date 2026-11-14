#!/usr/bin/env python3
"""Deterministic autopilot that does NOT need an LLM (runs inside the live loop every cycle, after state is committed).
1) GTA 6 FIRST-REACTION: detects the moment the stream category/title becomes Grand Theft Auto VI / GTA 6 (or, as a backup, the first strong
   GTA-6 transcript cue), waits HOLD_FIRST seconds of content after it (fast lane, default 8 min), then writes state/clips/gta6_first_reaction/{cuts,spec}.json,
   commits, pushes and dispatches the render-clip workflow.  Runs ONCE.
2) FALLBACK clips: if the judge session has not produced clips for FALLBACK_HOURS and a heuristic candidate scores >= FALLBACK_SCORE, creates ONE generic clip
   (max FALLBACK_PER_DAY per day, never the same time range twice). Titles are generic and uploads are private, so the owner can rename before publishing.
usage: autopilot.py [--dry-run]"""
import argparse, json, os, re, subprocess, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); ST = os.path.join(ROOT, "state")
HOLD_FIRST = int(os.environ.get("HOLD_FIRST", "480")); FIRST_LEN = int(os.environ.get("FIRST_LEN", "780")); PRE = int(os.environ.get("FIRST_PRE", "90"))
FALLBACK_HOURS = float(os.environ.get("FALLBACK_HOURS", "2.5")); FALLBACK_SCORE = float(os.environ.get("FALLBACK_SCORE", "22")); FALLBACK_PER_DAY = int(os.environ.get("FALLBACK_PER_DAY", "2"))
GTA6 = re.compile(r"grand theft auto\s*(vi\b|6)|gta\s*(vi\b|6)|גי\s?טי\s?איי\s*(6|שש)|ג'י\s?טי\s?איי\s*(6|שש)", re.I)
def jl(p):
    out = []
    if os.path.exists(p):
        for l in open(p, encoding="utf-8"):
            try: out.append(json.loads(l))
            except Exception: pass
    return out
def jf(p, d=None):
    try: return json.load(open(p))
    except Exception: return d
def sh(cmd, dry): 
    print("$", " ".join(cmd)); 
    if dry: return 0
    return subprocess.run(cmd, cwd=ROOT).returncode
def publish(cid, msg, dry):
    sh(["git", "add", "state"], dry); sh(["git", "commit", "-q", "-m", msg], dry)
    for _ in range(3):
        if sh(["git", "pull", "--rebase", "-q"], dry) == 0 and sh(["git", "push", "-q"], dry) == 0: break
    if os.environ.get("GH_TOKEN") or dry: sh(["gh", "workflow", "run", "render-clip.yml", "--ref", "main", "-f", f"clip_id={cid}", "-f", "upload=true"], dry)
def snap_end(rows, t):
    """end of the sentence that contains/precedes t"""
    best = None
    for r in rows:
        if r["end"] <= t: best = r["end"]
        else: break
    return best or t
def first_reaction(ing, dry):
    cid = "gta6_first_reaction"; d = os.path.join(ST, "clips", cid); ev = os.path.join(ST, "events", "gta6_first.json")
    if os.path.exists(d) and os.path.exists(os.path.join(d, "spec.json")): return False
    vod = ing.get("_current_vod"); start = ing.get("_vod_start_epoch")
    if not vod or not start: return False
    cats = jl(os.path.join(ST, "category.jsonl")); rows = sorted(jl(os.path.join(ST, "transcripts", f"{vod}.jsonl")), key=lambda r: r["start"])
    t0 = None; how = None
    for c in cats:
        if GTA6.search(f"{c.get('cat') or ''} {c.get('title') or ''}"): t0 = c["t"] - start; how = "category/title"; break
    if t0 is None:                                                 # backup: first strong spoken cue (two cues within 60 s)
        hits = [r for r in rows if GTA6.search(r["text"]) or re.search(r"(פתחתי|נכנסתי|נכנס|מתחיל).{0,12}(למשחק|ל-?GTA)", r["text"])]
        for i, r in enumerate(hits[:-1]):
            if hits[i + 1]["start"] - r["start"] < 60 and re.search(r"פעם ראשונה|בפעם הראשונה|סוף סוף|וואו", " ".join(x["text"] for x in rows if r["start"] - 30 <= x["start"] <= r["start"] + 90)): t0 = r["start"]; how = "transcript"; break
    if t0 is None: return False
    ready_at = t0 + HOLD_FIRST; vod_end = rows[-1]["end"] if rows else 0
    json.dump({"vod": vod, "t0": t0, "how": how, "detected": int(time.time()), "ready_when_vod_seconds": ready_at}, open(ev, "w"), indent=1)
    if vod_end < ready_at: print(f"GTA6 detected via {how} at VOD {int(t0)} s; waiting for {int(ready_at - vod_end)} s more content"); return False
    a = max(0, t0 - PRE); b = snap_end(rows, min(vod_end, t0 + FIRST_LEN)); a = max(0, min(a, b - 360))
    base = ing.get("_vod_base"); os.makedirs(d, exist_ok=True)
    json.dump({"vod": vod, "base": base, "pieces": [{"keep": [[round(a, 2), round(b, 2)]], "ch": "עודד נכנס ל-GTA 6"}]}, open(os.path.join(d, "cuts.json"), "w"), ensure_ascii=False, indent=1)
    json.dump({"title": "עודד נכנס ומגיב בפעם הראשונה ל-GTA 6!", "description": "הרגע שעודד נכנס בפעם הראשונה ל-GTA 6 בסבתון, והתגובה שלו.\n\nהרגעים הכי טובים מהלייב של עודד בקיק | ODED HIGHLIGHTS\n\nהקטע מתוך הלייב של עודד בקיק: https://kick.com/odedsvr\n\n#עודד #OdedSVR #GTA6 #סבתון #עודדהיילייטס #קיק #Kick",
               "tags": ["עודד", "OdedSVR", "GTA 6", "GTA VI", "סבתון", "עודד קיק", "ODED HIGHLIGHTS", "פעם ראשונה"], "preset": "game_launch", "head": "פעם ראשונה", "accent": "ב-GTA 6!", "refs": "shock,excited,smirk", "auto": True},
              open(os.path.join(d, "spec.json"), "w"), ensure_ascii=False, indent=1)
    print(f"FIRST REACTION clip created: VOD {int(a)}-{int(b)} ({int((b - a) / 60)} min)"); publish(cid, f"autopilot: {cid} ({int(a)}-{int(b)})", dry); return True
def fallback(ing, dry):
    vod = ing.get("_current_vod")
    if not vod: return False
    clips = os.path.join(ST, "clips"); mine = [d for d in (os.listdir(clips) if os.path.isdir(clips) else []) if os.path.exists(os.path.join(clips, d, "spec.json"))]
    last = max([os.path.getmtime(os.path.join(clips, d, "spec.json")) for d in mine], default=0)
    if time.time() - last < FALLBACK_HOURS * 3600: return False
    today = time.strftime("%Y%m%d", time.gmtime())
    if sum(1 for d in mine if d.startswith(f"auto_{today}")) >= FALLBACK_PER_DAY: return False
    cf = os.path.join(ST, "topics", f"{vod}.candidates.json"); cands = jf(cf, []) or []
    done = [json.load(open(os.path.join(clips, d, "cuts.json"))) for d in mine if os.path.exists(os.path.join(clips, d, "cuts.json"))]
    def used(c): return any(any(a < c["b"] and c["a"] < b for p in x.get("pieces", []) for a, b in p.get("keep", [])) for x in done)
    for c in cands:
        if c["score"] < FALLBACK_SCORE or used(c): continue
        if os.environ.get("FALLBACK_RENDER", "0") != "1":    # owner rule: a heuristic must never upload alone; mark the candidate and wait for the judge
            pf = os.path.join(ST, "pending_candidates.json"); pend = jf(pf, []) or []
            if not any(abs(x["a"] - c["a"]) < 60 for x in pend):
                pend.append({"vod": vod, "a": c["a"], "b": c["b"], "score": c["score"], "preview": c.get("preview", ""), "marked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
                json.dump(pend, open(pf, "w"), ensure_ascii=False, indent=1); print(f"candidate marked (no upload): VOD {c['a']}-{c['b']} score {c['score']}")
            continue
        cid = f"auto_{today}_{time.strftime('%H%M', time.gmtime())}"; d = os.path.join(clips, cid); os.makedirs(d, exist_ok=True)
        json.dump({"vod": vod, "base": ing.get("_vod_base"), "pieces": [{"keep": [[c["a"], c["b"]]], "ch": "הרגע המרכזי"}]}, open(os.path.join(d, "cuts.json"), "w"), ensure_ascii=False, indent=1)
        gta = c.get("info", {}).get("gta", 0) > 2
        json.dump({"title": "בדיקה: רגע מהסבתון של עודד (לשנות כותרת לפני פרסום)", "description": "רגע מהלייב של עודד בקיק.\n\nהרגעים הכי טובים מהלייב של עודד בקיק | ODED HIGHLIGHTS\n\nהקטע מתוך הלייב של עודד בקיק: https://kick.com/odedsvr\n\n#עודד #OdedSVR #סבתון #עודדהיילייטס #קיק",
                   "tags": ["עודד", "OdedSVR", "סבתון", "ODED HIGHLIGHTS"], "preset": "game_launch" if gta else "reaction_video", "head": "הרגע" , "accent": "הכי מטורף!", "refs": "shock,excited,smirk", "auto": True, "needs_title": True,
                   "preview": c.get("preview", "")}, open(os.path.join(d, "spec.json"), "w"), ensure_ascii=False, indent=1)
        print(f"FALLBACK clip {cid}: VOD {c['a']}-{c['b']} score {c['score']}"); publish(cid, f"autopilot fallback: {cid}", dry); return True
    return False
if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--dry-run", action="store_true"); a = ap.parse_args()
    if os.path.exists(os.path.join(ST, "PAUSE")): print("PAUSE"); sys.exit(0)
    ing = jf(os.path.join(ST, "ingest_state.json"), {}) or {}
    if not first_reaction(ing, a.dry_run): fallback(ing, a.dry_run)

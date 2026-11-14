#!/usr/bin/env python3
"""Topic scanner for the live loop. Reads state/transcripts/<vod>.jsonl (start,end,text in VOD seconds) and
  1) writes a compact DIGEST (state/topics/<vod>.digest.txt) of the NEW closed part of the stream for the Claude session to judge cheaply,
  2) writes heuristic CANDIDATES (state/topics/<vod>.candidates.json) usable without any LLM (fallback when the usage limit is hit).
A topic is only considered CLOSED if it ended at least HOLD seconds before the end of the transcript (default 15 min).
usage: topic_scan.py [--vod ID] [--hold 900] [--min 360] [--max 2400]"""
import argparse, json, math, os, re, sys
from collections import Counter
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); ST = os.path.join(ROOT, os.environ.get("STATE_DIR", "state")); TD = os.path.join(ST, "topics"); os.makedirs(TD, exist_ok=True)
GTA_CUES = ["GTA","ג'י טי איי","גי טי איי","ויס סיטי","וייס סיטי","לוס סנטוס","לאוס","מיסיון","משימה","תוכנית השוד","הפשע","מרדף","משטרה","שוטרים","נכנסתי למשחק","יצא המשחק","פתחתי את המשחק"]
FIRST_CUES = ["פעם ראשונה","בפעם הראשונה","הפעם הראשונה","סוף סוף","לא מאמין","אני בשוק","וואו"]
CUES = ["דרמה","ריב","התפוצץ","פתח עליו","עבר כל גבול","דירוג","מדרג","טייר","אתגר","התערבנו","על כסף","טריוויה","נחש מי","חקיין","נמאס לי","עוזב","מודיע",
        "נפגש","התקשר","מתקשר","שיחה","עלה ללייב","מגיב","תראו את זה","סיפור","תשמעו מה קרה","פעם ראשונה","בפעם הראשונה","וואו","לא ייאמן","אי אפשר","מטורף","סבתון"]
BAD = ["סטייק","קוד קופון","קזינו","הימור","רולטה","בהמתנה","מיד חוזרים","ברבי","starting soon"]
STOP = set("את של על זה לא כן אני אתה הוא היא הם אנחנו מה כי אבל גם עוד כל יש אין אם או רק כמו אז פה שם הזה הזאת זאת מי איך למה כאילו אחי וואלה טוב".split())
def tok(t): return [w for w in re.findall(r"[א-ת]{2,}", t) if w not in STOP]
def chat_spikes(vod_start, offset=20):
    """returns [(vod_second, z)] of chat-rate spikes mapped to VOD time (chat lags the event by ~offset s)."""
    import glob
    rows = []
    for f in sorted(glob.glob(os.path.join(ST, "chat", "*.jsonl"))):
        for l in open(f):
            try: rows.append(json.loads(l))
            except Exception: pass
    if len(rows) < 30 or not vod_start: return []
    n = [r["n"] + 0.5 * r.get("k", 0) for r in rows]; mu = sum(n) / len(n); sd = (sum((x - mu) ** 2 for x in n) / len(n)) ** 0.5 or 1.0
    return [(r["t"] - vod_start - offset, round((x - mu) / sd, 2)) for r, x in zip(rows, n) if (x - mu) / sd >= 2.0]
def load(vod):
    f = os.path.join(ST, "transcripts", f"{vod}.jsonl"); rows = []
    if os.path.exists(f):
        for l in open(f, encoding="utf-8"):
            try: rows.append(json.loads(l))
            except Exception: pass
    return sorted(rows, key=lambda r: r["start"])
def windows(rows, size=120):
    W = {}
    for r in rows: W.setdefault(int(r["start"] // size), []).append(r)
    return [(k * size, (k + 1) * size, " ".join(x["text"] for x in v)) for k, v in sorted(W.items())]
def cos(a, b):
    ca, cb = Counter(a), Counter(b); dot = sum(ca[w] * cb.get(w, 0) for w in ca)
    na = math.sqrt(sum(v * v for v in ca.values())); nb = math.sqrt(sum(v * v for v in cb.values())); return dot / (na * nb) if na and nb else 0.0
def segment(wins, thr=0.06):
    if not wins: return []
    cuts = [0]
    for i in range(1, len(wins)):
        a = sum((tok(w[2]) for w in wins[max(0, i - 3):i]), []); b = sum((tok(w[2]) for w in wins[i:i + 3]), [])
        if cos(a, b) < thr: cuts.append(i)
    cuts.append(len(wins)); segs = []
    for x, y in zip(cuts, cuts[1:]):
        txt = " ".join(w[2] for w in wins[x:y]); segs.append(dict(a=wins[x][0], b=wins[y - 1][1], text=txt))
    return segs
def score(seg, lo, hi, spikes=None):
    d = seg["b"] - seg["a"]; t = seg["text"]; words = tok(t)
    if d < lo or d > hi: return -1, {}
    if any(b in t for b in BAD): return -1, {"bad": True}
    cue = sum(t.count(c) for c in CUES); names = len(re.findall(r"עמית|ביגי|סנסיי|רונן|אוהד|סייקניק|ליאור|מיכאל|אינדה|נדב|איתן", t))
    density = len(words) / max(1, d / 60.0); ex = t.count("!") + t.count("?")
    gta = sum(t.count(c) for c in GTA_CUES); first = sum(t.count(c) for c in FIRST_CUES)
    sp = [z for (ts, z) in (spikes or []) if seg['a'] <= ts <= seg['b']]; chat = min(len(sp), 8) * 0.8 + (max(sp) if sp else 0) * 0.6
    s = min(gta, 10) * 1.4 + (6 if (gta and first) else 0) + chat + min(cue, 12) * 1.5 + min(names, 10) * 1.2 + min(density / 60.0, 2.0) * 3 + min(ex, 10) * 0.4 + min(d / 600.0, 2.0)
    return round(s, 2), dict(cues=cue, names=names, wpm=round(density), minutes=round(d / 60, 1), gta=gta, first=first, chat_spikes=len(sp), chat_max_z=(max(sp) if sp else 0))
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--vod"); ap.add_argument("--hold", type=int, default=900); ap.add_argument("--min", type=int, default=360); ap.add_argument("--max", type=int, default=2400); a = ap.parse_args()
    ing = json.load(open(os.path.join(ST, "ingest_state.json"))) if os.path.exists(os.path.join(ST, "ingest_state.json")) else {}
    vod = a.vod or ing.get("_current_vod")
    if not vod: print("no vod"); return 0
    rows = load(vod)
    if not rows: print("no transcript yet for", vod); return 0
    end = rows[-1]["end"]; closed_until = end - a.hold
    seen_f = os.path.join(TD, f"{vod}.seen.json"); seen = json.load(open(seen_f)) if os.path.exists(seen_f) else {"digest_to": 0}
    wins = [w for w in windows(rows) if w[1] <= closed_until]
    new = [w for w in wins if w[0] >= seen["digest_to"]]
    with open(os.path.join(TD, f"{vod}.digest.txt"), "w", encoding="utf-8") as fh:
        fh.write(f"VOD {vod} transcript_end={int(end)}s closed_until={int(closed_until)}s (topics ending after this are NOT closed yet)\n")
        for w in new: fh.write(f"[{int(w[0])}-{int(w[1])}] {w[2][:420]}\n")
    spikes = chat_spikes(ing.get('_vod_start_epoch'))
    segs = segment(wins); cands = []
    for s in segs:
        sc, info = score(s, a.min, a.max, spikes)
        if sc > 0: cands.append(dict(vod=vod, a=int(s["a"]), b=int(s["b"]), score=sc, info=info, preview=s["text"][:220], status="candidate"))
    cands.sort(key=lambda c: -c["score"]); json.dump(cands, open(os.path.join(TD, f"{vod}.candidates.json"), "w"), ensure_ascii=False, indent=1)
    print(f"chat spikes mapped: {len(spikes)}")
    print(f"vod {vod}: transcript {int(end/60)} min, closed {int(closed_until/60)} min, new windows {len(new)}, candidates {len(cands)}")
    return 0
if __name__ == "__main__": sys.exit(main())

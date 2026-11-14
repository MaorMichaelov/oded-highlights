#!/usr/bin/env python3
"""Lightweight Kick chat logger (no login, public endpoint GET /api/v2/channels/<id>/messages = last ~25 messages).
Polls every POLL seconds, de-duplicates by message id, writes per-10-second buckets to state/chat/<YYYYMMDD>.jsonl:
  {"t": <bucket start epoch>, "n": messages, "u": unique chatters, "e": emote-ish tokens, "k": keyword hits (GTA / reaction words)}
Chat lags the on-stream event (~15-25 s), the topic scanner offsets for that. usage: chat_poll.py [--seconds 20400] [--poll 10]"""
import argparse, json, os, re, subprocess, sys, time
from collections import defaultdict
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = os.path.join(ROOT, "state", "chat"); os.makedirs(OUT, exist_ok=True)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
CHANNEL_ID = os.environ.get("CHANNEL_ID", "7685090")
KW = re.compile(r"gta|ויס|וייס|סיטי|לוס|וואו|מטורף|פיצוץ|בום|אלוהים|הלו|חחח|😂|🤣|lol|lmao|omg|wtf|פס|קיל|סבתון|ראשון", re.I)
def fetch():
    r = subprocess.run(["curl", "-sS", "-A", UA, "-m", "20", f"https://kick.com/api/v2/channels/{CHANNEL_ID}/messages"], capture_output=True, text=True)
    try: return (json.loads(r.stdout).get("data") or {}).get("messages") or []
    except Exception: return None
def epoch(ts):
    try: return int(time.mktime(time.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S"))) - time.timezone
    except Exception: return int(time.time())
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--seconds", type=int, default=20400); ap.add_argument("--poll", type=int, default=10); a = ap.parse_args()
    seen = set(); buckets = defaultdict(lambda: {"n": 0, "u": set(), "e": 0, "k": 0}); end = time.time() + a.seconds; flushed = 0; fails = 0
    while time.time() < end:
        msgs = fetch()
        if msgs is None: fails += 1; time.sleep(min(60, a.poll * (1 + fails))); continue
        fails = 0
        for m in msgs:
            mid = m.get("id")
            if mid in seen: continue
            seen.add(mid); b = (epoch(m.get("created_at", "")) // 10) * 10; txt = str(m.get("content") or "")
            x = buckets[b]; x["n"] += 1; x["u"].add((m.get("sender") or {}).get("username")); x["e"] += len(re.findall(r"\[emote:[^\]]+\]", txt)); x["k"] += len(KW.findall(txt))
        if len(seen) > 5000: seen = set(list(seen)[-2000:])
        cutoff = (int(time.time()) // 10) * 10 - 40                     # buckets older than 40 s are final
        done = sorted(b for b in buckets if b <= cutoff)
        if done:
            f = os.path.join(OUT, time.strftime("%Y%m%d", time.gmtime(done[0])) + ".jsonl")
            with open(f, "a", encoding="utf-8") as fh:
                for b in done: x = buckets.pop(b); fh.write(json.dumps({"t": b, "n": x["n"], "u": len(x["u"]), "e": x["e"], "k": x["k"]}) + "\n")
        time.sleep(a.poll)
if __name__ == "__main__": sys.exit(main())

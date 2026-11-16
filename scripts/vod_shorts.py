#!/usr/bin/env python3
"""VOD -> SHORTS for any Kick streamer (English). Built from the research in docs/SHORTS_RESEARCH.md.
usage: vod_shorts.py --slug n3on [--vod ID|auto] [--from-min 0] [--to-min 60] [--n 3] [--out state/n3on/shorts]
Steps: pick a VOD (skips gambling/giveaway streams) -> audio of the window -> Groq whisper (English, word times) -> per-second signals (audio energy + words/s) -> robust z-score peaks
-> free LLM scores each peak window (setup sentence .. payoff sentence, rejects gambling/promo/hard lines) -> snap to word boundaries (20-58 s) -> cut 1080p60 from Kick HLS
-> 9:16 render (blurred fill + centred stream, big captions, -14 LUFS) via scripts/stations/shorts.py. No chat signal for past VODs (Kick keeps no chat replay): live runs add chat spikes later.
env: GROQ_API_KEY"""
import argparse, json, os, re, subprocess, sys, tempfile, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, os.path.join(HERE, "stations")); sys.path.insert(0, HERE)
GAMBLING = re.compile(r"jack\.?com|gambl|giveaway|casino|stake\.|slots?\b|roulette|promo code|use code|sportsbook|betting|\bbets?\b|18\+", re.I)
def sh(c, **k): return subprocess.run(c, capture_output=True, text=True, **k)
def jget(url): return json.loads(sh(["curl", "-sS", "-m", "40", "-A", "Mozilla/5.0", url]).stdout)
def groq(model, messages, mx=1200):
    key = os.environ["GROQ_API_KEY"]
    r = sh(["curl", "-sS", "-m", "120", "https://api.groq.com/openai/v1/chat/completions", "-H", "Authorization: Bearer " + key, "-H", "Content-Type: application/json", "-d", json.dumps({"model": model, "messages": messages, "max_tokens": mx, "reasoning_effort": "low"})])
    return json.loads(r.stdout)["choices"][0]["message"]["content"]
def llm(prompt):
    for m in ("openai/gpt-oss-120b", "openai/gpt-oss-20b"):
        try: return json.loads(re.search(r"\{.*\}", groq(m, [{"role": "user", "content": prompt}]), re.S).group(0))
        except Exception as e: print("llm", m, "failed:", str(e)[:100]); time.sleep(3)
    return None
def pick_vod(slug, vid):
    vs = jget(f"https://kick.com/api/v2/channels/{slug}/videos")
    for v in vs:
        title = v.get("session_title") or ""
        if str(v["id"]) == str(vid) or (vid == "auto" and (v.get("duration") or 0) > 25 * 60000 and not GAMBLING.search(title)): return v
    sys.exit("no suitable VOD")
def whisper(path):   # Groq whisper large-v3-turbo, word timestamps (free tier: 7200 audio-seconds/hour)
    r = sh(["curl", "-sS", "-m", "300", "https://api.groq.com/openai/v1/audio/transcriptions", "-H", "Authorization: Bearer " + os.environ["GROQ_API_KEY"], "-F", f"file=@{path}", "-F", "model=whisper-large-v3-turbo", "-F", "language=en", "-F", "response_format=verbose_json", "-F", "timestamp_granularities[]=word"])
    return json.loads(r.stdout).get("words", [])
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--slug", required=True); ap.add_argument("--vod", default="auto"); ap.add_argument("--from-min", type=float, default=0); ap.add_argument("--to-min", type=float, default=60); ap.add_argument("--n", type=int, default=3); ap.add_argument("--out", default=None); a = ap.parse_args()
    out = a.out or f"state/{a.slug}/shorts"; os.makedirs(out, exist_ok=True); v = pick_vod(a.slug, a.vod); base = v["source"].rsplit("/master.m3u8", 1)[0]; vid = str(v["id"])
    print("VOD", vid, v.get("session_title"), round((v.get("duration") or 0) / 60000), "min"); t0 = a.from_min * 60; dur = (a.to_min - a.from_min) * 60
    tmp = tempfile.mkdtemp(); words = []; en = []
    # 1. audio in 10-minute chunks -> words (absolute VOD seconds) + energy per second
    for c0 in np.arange(0, dur, 600):
        d = min(600, dur - c0); mp3 = f"{tmp}/a{int(c0)}.mp3"
        r = sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{t0 + c0:.1f}", "-t", f"{d:.1f}", "-i", f"{base}/480p30/playlist.m3u8", "-vn", "-ac", "1", "-ar", "16000", "-c:a", "libmp3lame", "-b:a", "48k", mp3])
        if r.returncode: print("audio chunk failed", r.stderr[-200:]); continue
        for w in whisper(mp3): words.append({"word": w["word"], "start": t0 + c0 + w["start"], "end": t0 + c0 + w["end"]})
        raw = sh(["ffmpeg", "-v", "error", "-i", mp3, "-f", "s16le", "-ac", "1", "-ar", "8000", "-"], text=False).stdout; x = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
        n = len(x) // 8000; en += list(np.sqrt((x[:n * 8000].reshape(n, 8000) ** 2).mean(1)) + 1e-3)
        print(f"chunk {int(c0 / 60)}-{int((c0 + d) / 60)} min: {len(words)} words total"); time.sleep(2)
    N = int(dur); e = np.zeros(N); e[:min(N, len(en))] = np.array(en[:N]); wps = np.zeros(N)
    for w in words:
        i = int(w["start"] - t0)
        if 0 <= i < N: wps[i] += 1
    def rz(s):
        k = 600; z = np.zeros(len(s))
        for i in range(0, len(s), 60):
            seg = s[max(0, i - k):i + k]; med = np.median(seg); mad = np.median(np.abs(seg - med)) + 1e-6; z[i:i + 60] = (s[i:i + 60] - med) / (1.4826 * mad)
        return np.clip(z, -3, 6)
    sm = lambda z: np.convolve(z, np.ones(5) / 5, mode="same")
    S = sm(0.6 * rz(np.log(e + 1e-3)) + 0.4 * rz(wps)); order = np.argsort(-S); peaks = []
    for i in order:
        if S[i] < 1.8: break
        if all(abs(i - p) >= 60 for p in peaks): peaks.append(int(i))
        if len(peaks) >= a.n * 4: break
    print("peaks:", [(int(p + t0) // 60, round(float(S[p]), 1)) for p in peaks])
    # 2. LLM scoring of every peak window
    cands = []
    for p in peaks:
        pk = t0 + p; ws = [w for w in words if pk - 45 <= w["start"] <= pk + 20]
        if len(ws) < 15: continue
        txt = " ".join(f"[{w['start']:.0f}]{w['word'].strip()}" for w in ws)[:5500]
        j = llm("You edit YouTube Shorts from a live stream of a big streamer. Below: words with [second] for the window around an audio/speech peak at second %d. Decide if it is a clip-worthy moment (funny, shocking, dramatic, a story with a punchline). REJECT (reject=true) gambling/casino/giveaway/promo-code talk, sponsored reads, slurs, sexual content, self-harm, minors, or random chatter. Return JSON only: {\"score\":1-10,\"start\":second where the SETUP sentence starts (8-25 s before the peak, a sentence start),\"end\":second where the PAYOFF/reaction sentence ends (+0.4 s allowed),\"title\":\"English YouTube Shorts title 40-70 chars, hook first, quote the funniest line if it is clean, ends with ! or ?\",\"hook\":\"3-6 word on-screen text\",\"reject\":false,\"why\":\"\"}\n\n%s" % (pk, txt))
        if j and not j.get("reject") and float(j.get("score", 0)) >= 6: cands.append((float(j["score"]) + float(S[p]) / 3, pk, j))
    cands.sort(reverse=True); made = []
    # 3. cut + 9:16 render
    import shorts as SH
    for sc, pk, j in cands:
        if len(made) >= a.n: break
        try: s = float(j["start"]); e_ = float(j["end"])
        except Exception: continue
        s = max(s, pk - 25); e_ = min(max(e_, pk + 3), s + 58)
        s0 = max([w["start"] for w in words if w["start"] <= s], default=s) - 0.2; e0 = min([w["end"] for w in words if w["end"] >= e_], default=e_) + 0.45
        if not (20 <= e0 - s0 <= 59) or any(s0 < y and x < e0 for x, y in [(m[2], m[3]) for m in made]): print("rejected", round(s0), round(e0), j.get("title")); continue
        body = f"{tmp}/b{int(s0)}.mp4"; pad = 2.0
        r = sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{s0 - pad:.2f}", "-t", f"{e0 - s0 + 2 * pad:.2f}", "-i", f"{base}/1080p60/playlist.m3u8", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "aac", "-b:a", "192k", body])
        if r.returncode: print("cut failed", r.stderr[-300:]); continue
        rel = [{"word": w["word"], "start": w["start"] - (s0 - pad), "end": w["end"] - (s0 - pad)} for w in words if s0 - pad <= w["start"] <= e0 + pad]
        ass = f"{out}/short_{vid}_{int(s0)}.ass"; mp4 = f"{out}/short_{vid}_{int(s0)}.mp4"; SH.make_ass(rel, pad, pad + e0 - s0, ass)
        txt = open(ass, encoding="utf-8").read().replace("&H0028E678", "&H0000E6FF").replace("Heebo Black", "Heebo Black"); open(ass, "w", encoding="utf-8").write(txt)
        if not SH.render(body, pad, pad + e0 - s0, ass, mp4): continue
        meta = {"title": j["title"][:90] + " #Shorts", "hook": j.get("hook", ""), "source": {"slug": a.slug, "vod": vid, "start_s": round(s0), "end_s": round(e0), "vod_title": v.get("session_title")}, "score": round(sc, 1), "why": j.get("why", ""),
                "description": f"{j['title']}\n\nClip from {a.slug}'s live stream on Kick (https://kick.com/{a.slug}). Unofficial fan channel, not affiliated.\n#Shorts #{a.slug}"}
        json.dump(meta, open(mp4.replace(".mp4", ".json"), "w"), ensure_ascii=False, indent=1); made.append((mp4, meta, s0, e0)); print(f"SHORT {len(made)}: {int(s0 // 60)}:{int(s0 % 60):02d}-{int(e0 // 60)}:{int(e0 % 60):02d} ({e0 - s0:.0f}s) score {sc:.1f} | {j['title']}")
    if not made: sys.exit("no short produced")
if __name__ == "__main__": main()

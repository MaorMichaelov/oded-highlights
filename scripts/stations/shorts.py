#!/usr/bin/env python3
"""STATION 8 - SHORTS: cuts 1-2 vertical Shorts (1080x1920, 25-58 s) from the strongest moments of a finished long clip and uploads them as private drafts.
In : <clip>/work/body.mp4 + work/words.json (word timings) + spec.json     Out: <clip>/shorts/short1.mp4 (+ meta json), drafts on YouTube (with --upload)
Layout: the 16:9 video centred over a blurred, zoomed copy of itself (safe for any stream layout), big green word captions (2-3 words, pop-in), loudness normalised.
The moment is chosen by the free LLM (Groq) from the clip transcript; heuristic fallback = densest speech window. usage: shorts.py state/clips/<id> [--upload] [--n 2]"""
import argparse, json, os, re, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); from common import Timer
from events import event
ROOT = os.path.dirname(os.path.dirname(HERE))
FONTS = [d for d in ("/workspace/fonts", "/usr/share/fonts/truetype/sand-box/google/Heebo") if os.path.isdir(d)]
def sh(c, **k): return subprocess.run(c, capture_output=True, text=True, **k)
def mmss(t): return f"{int(t // 60)}:{int(t % 60):02d}"
def pick_moments(words, spec, n, dur):
    lines, cur, t0 = [], [], None
    for w in words:
        if t0 is None: t0 = w["start"]
        cur.append(w["word"].strip())
        if w["end"] - t0 >= 5: lines.append(f"[{t0:.1f}] " + " ".join(cur)); cur, t0 = [], None
    if cur: lines.append(f"[{t0:.1f}] " + " ".join(cur))
    lang = spec.get("lang", "he"); body = "\n".join(lines)[:9000]
    prompt = (f"Names used by this streamer scene (the transcript often misspells them, write them correctly in titles): עודד, ביגי, עמית שיבר, סנסיי, רונן, אינדה, איתן ניסים, אוהד, מיכאל. Use the clip title as the reference for names and topic. You pick viral YouTube Shorts from a streamer clip transcript (language: {lang}). Clip title: {spec.get('title')}. Lines start with [seconds]. "
              f"Choose up to {n} NON-overlapping moments of 25-55 seconds each: strongest punchline/reaction/drama; the first 3 seconds must hook; start at the beginning of a sentence, end right after the punchline. "
              "Return JSON only: {\"shorts\":[{\"start\":sec,\"end\":sec,\"title\":\"punchy title <=60 chars in the clip language, ending with ! or ?!\",\"why\":\"\"}]}\n\n" + body)
    key = os.environ.get("GROQ_API_KEY")
    if key:
        for model in ("openai/gpt-oss-120b", "openai/gpt-oss-20b"):
            r = sh(["curl", "-sS", "-m", "120", "https://api.groq.com/openai/v1/chat/completions", "-H", "Authorization: Bearer " + key, "-H", "Content-Type: application/json",
                    "-d", json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 900, "reasoning_effort": "low"}, ensure_ascii=False)])
            try:
                txt = json.loads(r.stdout)["choices"][0]["message"]["content"]; return json.loads(re.search(r"\{.*\}", txt, re.S).group(0))["shorts"]
            except Exception as e: print("shorts LLM", model, "failed:", str(e)[:100], r.stdout[:150])
    best = max(((sum(1 for w in words if t <= w["start"] < t + 40), t) for t in range(5, max(6, int(dur) - 42), 5)), default=(0, 5))   # fallback: densest 40 s
    return [{"start": best[1], "end": best[1] + 40, "title": spec.get("title", "")[:60]}]
def snap(words, s, e, dur):
    s0 = max([w["start"] for w in words if w["start"] <= s], default=s); e0 = min([w["end"] for w in words if w["end"] >= e], default=e)
    return max(0.0, s0 - 0.25), min(dur, e0 + 0.5)
def make_ass(words, s, e, path):
    ws = [w for w in words if w["start"] >= s - 0.05 and w["end"] <= e + 0.05 and w["word"].strip()]
    groups, cur = [], []
    for w in ws:
        cur.append(w)
        if len(cur) >= 3 or re.search(r"[.!?,]$", w["word"].strip()) or (cur and w["end"] - cur[0]["start"] > 1.6): groups.append(cur); cur = []
    if cur: groups.append(cur)
    def ts(t): t = max(0, t - s); return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"
    hdr = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 0\n\n[V4+ Styles]\n"
           "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\n"
           "Style: Cap,Heebo Black,104,&H0028E678,&H0028E678,&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,9,3,2,60,60,520,1\n\n[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n")
    ev = []
    for i, g in enumerate(groups):
        a = g[0]["start"]; b = groups[i + 1][0]["start"] if i + 1 < len(groups) and groups[i + 1][0]["start"] - g[-1]["end"] < 0.6 else g[-1]["end"] + 0.15
        txt = " ".join(x["word"].strip() for x in g).replace("{", "").replace("}", "")
        ev.append(f"Dialogue: 0,{ts(a)},{ts(b)},Cap,,0,0,0,,{{\\fscx80\\fscy80\\t(0,110,\\fscx100\\fscy100)}}{txt}")
    open(path, "w", encoding="utf-8").write(hdr + "\n".join(ev) + "\n")
def render(body, s, e, ass, out):
    vf = ("[0:v]split=2[a][b];[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=28:4,eq=brightness=-0.12[bg];[b]scale=1080:-2[fg];"
          "[bg][fg]overlay=(W-w)/2:(H-h)/2[v0];[v0]subtitles=" + ass.replace(":", "\\:") + (":fontsdir=" + FONTS[0] if FONTS else "") + "[v]")
    cmd = ["ffmpeg", "-v", "error", "-y", "-ss", f"{s:.3f}", "-i", body, "-t", f"{e - s:.3f}", "-filter_complex", vf, "-map", "[v]", "-map", "0:a:0", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000",
           "-c:v", "libx264", "-preset", "veryfast", "-b:v", "9M", "-maxrate", "12M", "-bufsize", "18M", "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out]
    r = sh(cmd); 
    if r.returncode: print("ffmpeg failed:", r.stderr[-600:]); return False
    return True
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("clip"); ap.add_argument("--upload", action="store_true"); ap.add_argument("--n", type=int, default=2); a = ap.parse_args()
    clip = os.path.abspath(a.clip); cid = os.path.basename(clip.rstrip("/")); work = os.path.join(clip, "work"); spec = json.load(open(os.path.join(clip, "spec.json")))
    body = os.path.join(work, "body.mp4"); wj = os.path.join(work, "words.json")
    if not (os.path.exists(body) and os.path.exists(wj)): sys.exit("shorts: body.mp4/words.json missing (run cut + edit first)")
    words = json.load(open(wj)).get("words", []); dur = float(sh(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", body]).stdout.strip())
    os.makedirs(os.path.join(clip, "shorts"), exist_ok=True); made = []
    with Timer(clip, "shorts"):
        used = []
        for i, m in enumerate(pick_moments(words, spec, a.n, dur)[:a.n], 1):
            try: s, e = snap(words, float(m["start"]), float(m["end"]), dur)
            except Exception: continue
            if not (20 <= e - s <= 59) or any(s < y and x < e for x, y in used): print("rejected moment", m); continue
            ass = os.path.join(clip, "shorts", f"short{i}.ass"); out = os.path.join(clip, "shorts", f"short{i}.mp4"); make_ass(words, s, e, ass)
            if not render(body, s, e, ass, out): continue
            used.append((s, e)); title = (m.get("title") or spec.get("title", ""))[:85].strip()
            meta = {"title": title + " #Shorts", "description": (spec.get("description", "").split("\n\n")[0] + "\n\n" + "\n".join(spec.get("description", "").split("\n\n")[1:3]) + "\n#Shorts").strip(), "tags": (spec.get("tags") or []) + ["Shorts"], "privacy": "private"}
            json.dump(meta, open(os.path.join(clip, "shorts", f"short{i}.json"), "w"), ensure_ascii=False, indent=1); made.append((out, meta, s, e)); print(f"SHORT {i}: {mmss(s)}-{mmss(e)} ({e - s:.0f}s) {title}")
        if a.upload:
            for out, meta, s, e in made:
                r = sh([sys.executable, os.path.join(ROOT, "scripts", "yt_upload.py"), out, out.replace(".mp4", ".json")]); url = [l for l in r.stdout.splitlines() if l.startswith("https://youtu.be/")]
                print("upload:", url[-1] if url else (r.stdout + r.stderr)[-300:])
                if url: event("draft", f"עלה שורט (טיוטה): {meta['title']}", url=url[-1], clip=cid, kind_short=True)
        if not made: sys.exit("no short produced")
if __name__ == "__main__": main()

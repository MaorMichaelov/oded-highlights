#!/usr/bin/env python3
"""Render a finished clip from a decision made by the topic session.
state/clips/<id>/cuts.json = {"vod": "...", "base": "<hls base url>", "pieces": [{"keep": [[a,b],...], "ch": "chapter name"}]}   (VOD seconds)
state/clips/<id>/spec.json = {title, description, tags, preset, head, accent, refs, hooks?: [{"t": vod_sec, "d": 2.8, "cap": "...", "hl": ["word"]}]}
Steps: body (1080p60, trim filters, no zoom) -> Groq word timings -> 3-shot cold open (green captions) + green sting + subscribe popup -> final.mp4 + chapters in description.
usage: render_clip.py state/clips/<id>"""
import json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
clip = os.path.abspath(sys.argv[1]); cid = os.path.basename(clip.rstrip("/"))
cuts = json.load(open(os.path.join(clip, "cuts.json"))); spec = json.load(open(os.path.join(clip, "spec.json")))
work = os.path.join(clip, "work"); os.makedirs(work, exist_ok=True)
def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode: print("FAILED:", " ".join(cmd)[:200], "\n", r.stderr[-800:], r.stdout[-300:]); sys.exit(1)
    return r.stdout
base = cuts.get("base") or json.load(open(os.path.join(ROOT, "state", "ingest_state.json")))["_vod_base"]
if not os.path.exists(os.path.join(work, "body.mp4")):
    print("building body ..."); run([sys.executable, os.path.join(HERE, "build_clip.py"), base, os.path.join(clip, "cuts.json"), work, "1080p60", "veryfast"])
body = os.path.join(work, "body.mp4"); chapters = json.load(open(os.path.join(work, "chapters.json")))
dur = float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", body]).strip())
# word timings via Groq
wj = os.path.join(work, "words.json")
if not os.path.exists(wj):
    mp3 = os.path.join(work, "body.mp3"); run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", body, "-vn", "-ac", "1", "-ar", "16000", "-b:a", "48k", mp3])
    key = ["-H", "Authorization: Bearer " + os.environ["GROQ_API_KEY"]] if os.environ.get("GROQ_API_KEY") else []
    prompt = spec.get("asr_prompt", "עודד, ביגי, עמית שיבר, סנסיי, רונן, קיק, סטרימר, פוקימון, GTA")
    out = run(["curl", "-sS", "-m", "600", "https://api.groq.com/openai/v1/audio/transcriptions"] + key + ["-F", "model=whisper-large-v3", "-F", "language=he", "-F", "response_format=verbose_json",
              "-F", "timestamp_granularities[]=word", "-F", "timestamp_granularities[]=segment", "-F", f"prompt={prompt}", "-F", f"file=@{mp3}"])
    open(wj, "w").write(out)
words = json.load(open(wj)).get("words", [])
# vod-time -> body-time
def vod2body(t):
    acc = 0.0
    for p in cuts["pieces"]:
        for a, b in p["keep"]:
            if a <= t <= b: return acc + (t - a)
            acc += b - a
    return None
hooks = []
if spec.get("hooks"):
    for h in spec["hooks"]:
        bt = vod2body(h["t"]);  
        if bt is not None: hooks.append(dict(t=round(bt, 2), d=h.get("d", 2.8), cap=h.get("cap", ""), hl=h.get("hl", [])))
if len(hooks) < 3:                                    # auto: densest 2.8 s windows (not in the first 12 s), spaced >= 25 s apart
    cand = []
    for t in range(12, int(dur) - 6):
        n = sum(1 for w in words if t <= w["start"] < t + 2.8); cand.append((n, t))
    for n, t in sorted(cand, reverse=True):
        if all(abs(t - h["t"]) >= 25 for h in hooks) and n >= 3: hooks.append(dict(t=float(t), d=2.8, cap="", hl=[]))
        if len(hooks) >= 3: break
montage = []
for h in sorted(hooks, key=lambda h: h["t"])[:3]:
    ws = [[round(w["start"] - h["t"], 3), w["word"].strip()] for w in words if h["t"] - 0.02 <= w["start"] < h["t"] + h["d"] - 0.15 and w["word"].strip()]
    montage.append(dict(t=h["t"], d=h["d"], cap=" ".join(x[1] for x in ws) or h["cap"] or "...", words=ws, hl=h["hl"] or ([ws[-1][1]] if ws else [])))
if len(montage) < 3: print("not enough hook moments (need 3)"); sys.exit(2)
logo = "/workspace/oded_research/oded_highlights_logo.jpg"
ospec = dict(body=body, body_dur=dur, work=os.path.join(work, "po"), res=[1920, 1080], montage=montage, premise=["-"], headshot=logo, popup_face=logo, sub_at=4.0)
sp = os.path.join(work, "open_spec.json"); json.dump(ospec, open(sp, "w"), ensure_ascii=False, indent=1)
final = os.path.join(clip, "final.mp4"); print("building opening ...")
run([sys.executable, os.path.join(HERE, "peak_open", "nov13_open.py"), sp, final])
off = json.load(open(final + ".open.json"))["body_offset_in_out"]
def ts(s): s = int(round(s)); return f"{s//60:02d}:{s%60:02d}"
lines = ["00:00 פתיחה"] + [f'{ts(c["t"] + off)} {c["ch"]}' for c in chapters]
meta = json.load(open(os.path.join(clip, "meta.json"))) if os.path.exists(os.path.join(clip, "meta.json")) else {"title": spec["title"], "description": spec["description"], "tags": spec.get("tags", []), "privacy": "private"}
meta["description"] = spec["description"].rstrip() + "\n\nפרקים:\n" + "\n".join(lines)
b = spec.get("brief")   # draft note for the thumbnail bot: what the clip is about, who appears, the strongest moment
if b:
    note = f"[טיוטה - למחוק לפני פרסום] על מה: {b.get('about', '')} | מופיעים: {b.get('who', 'עודד')} | הרגע החזק: {b.get('peak', '')}"
    meta["description"] = note + "\n\n" + meta["description"]; open(os.path.join(clip, "brief.md"), "w").write(note + "\n")
json.dump(meta, open(os.path.join(clip, "meta.json"), "w"), ensure_ascii=False, indent=1)
print("FINAL", final, "chapters:", len(lines))

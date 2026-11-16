#!/usr/bin/env python3
"""WATCH a video (picture + sound) with Gemini and print a detailed, timestamped description of how it is made.
usage: watch_video.py URL ["extra question"]      env: GEMINI_API_KEY (free key from aistudio.google.com/apikey)
- YouTube URL (public/unlisted): sent to Gemini as a video URL (no download, so YouTube's bot check does not matter).
- any other site (TikTok, Instagram, X, Kick clip ...): downloaded with yt-dlp (best <=720p), uploaded to the Gemini Files API, then analysed.
Output lines start with WATCH| so a workflow log can be grepped."""
import json, os, re, subprocess, sys, time, urllib.request
KEY = os.environ["GEMINI_API_KEY"]; URL = sys.argv[1]; EXTRA = sys.argv[2] if len(sys.argv) > 2 else ""
def list_models():   # model names change: pick the newest "flash" model that supports generateContent
    try:
        ms = json.loads(urllib.request.urlopen(f"https://generativelanguage.googleapis.com/v1beta/models?pageSize=200&key={KEY}", timeout=60).read())["models"]
        names = [m["name"].split("/")[-1] for m in ms if "generateContent" in m.get("supportedGenerationMethods", [])]
        print("WATCH|available:", ", ".join(names)[:1500])
        fl = sorted([n for n in names if "flash" in n and not re.search(r"lite|image|tts|live|audio|thinking|exp|preview-\d{2}-\d{2}", n)], reverse=True)
        return fl[:3] + ["gemini-2.5-flash", "gemini-2.0-flash"]
    except Exception as e: print("WATCH|list models failed", str(e)[:200]); return ["gemini-2.5-flash", "gemini-2.0-flash"]
MODELS = list_models()
PROMPT = ("Watch this video carefully, both picture and sound. It is a highlights/reaction video made from a live stream of an Israeli streamer (Hebrew). Answer in HEBREW, in detail, with mm:ss timestamps:\n"
          "1. Timeline of EVERY visible change: scene/cut, layout (what fills the screen: the news article / the reacted video full screen, the streamer's face-cam: size and position, chat overlay, captions: colour, font, position), transitions, zooms, effects, sound effects, music, intro/outro, subscribe pop-up, logos, text overlays.\n"
          "2. What exactly is SHOWN and what is NOT shown (e.g. only the article, without the streamer's drama/IRL talk). What was cut out between consecutive parts and why it seems to be cut.\n"
          "3. Counts: total number of cuts, shortest/longest uninterrupted part, how a part starts (at a sentence start?) and ends.\n"
          "4. Title/hook: how the first 10 seconds are built. 5. Anything a copy-cat editor must reproduce to get the same quality. " + EXTRA)
def post(url, body):
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=600).read())
def gen(part):
    last = ""
    for m in MODELS:
        try:
            r = post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={KEY}", {"contents": [{"parts": [part, {"text": PROMPT}]}], "generationConfig": {"temperature": 0.2}})
            return m, "".join(p.get("text", "") for p in r["candidates"][0]["content"]["parts"])
        except Exception as e:
            try: body = e.read().decode()[:400]
            except Exception: body = ""
            last = f"{m}: {e} {body}"; print("WATCH|model failed", last[:500])
    raise SystemExit("all models failed: " + last)
if re.search(r"youtube\.com|youtu\.be", URL): part = {"file_data": {"file_uri": URL}}
else:
    os.makedirs("/tmp/w", exist_ok=True); f = "/tmp/w/v.mp4"
    subprocess.run(["yt-dlp", "-f", "best[height<=720]/best", "-o", f, URL], check=True)
    n = os.path.getsize(f); h = {"X-Goog-Upload-Protocol": "resumable", "X-Goog-Upload-Command": "start", "X-Goog-Upload-Header-Content-Length": str(n), "X-Goog-Upload-Header-Content-Type": "video/mp4", "Content-Type": "application/json"}
    req = urllib.request.Request(f"https://generativelanguage.googleapis.com/upload/v1beta/files?key={KEY}", json.dumps({"file": {"display_name": "v"}}).encode(), h)
    up = urllib.request.urlopen(req, timeout=120).headers["X-Goog-Upload-URL"]
    req = urllib.request.Request(up, open(f, "rb").read(), {"X-Goog-Upload-Offset": "0", "X-Goog-Upload-Command": "upload, finalize", "Content-Length": str(n)})
    fi = json.loads(urllib.request.urlopen(req, timeout=900).read())["file"]
    while fi.get("state") == "PROCESSING": time.sleep(5); fi = json.loads(urllib.request.urlopen(f"https://generativelanguage.googleapis.com/v1beta/{fi['name']}?key={KEY}", timeout=60).read())
    part = {"file_data": {"file_uri": fi["uri"], "mime_type": "video/mp4"}}
m, txt = gen(part)
print("WATCH|model:", m)
for l in txt.splitlines(): print("WATCH|" + l)

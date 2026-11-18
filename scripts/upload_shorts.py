#!/usr/bin/env python3
"""Uploads the Shorts of state/<slug>/shorts/*.mp4 (+ .json meta) as PRIVATE drafts to the English channel (CHANNEL_YT=en, YT2_* secrets; yt_upload.py refuses any channel but the verified id in config/channels.json).
usage: upload_shorts.py <slug> [max]   Highest score first; already uploaded files are remembered in state/<slug>/shorts/uploaded.json."""
import glob, json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import statefile as SF   # the uploaded-record is saved after EVERY upload (a killed job must not forget what is already on YouTube)
slug = sys.argv[1]; mx = int(sys.argv[2]) if len(sys.argv) > 2 else 6; sub = sys.argv[3] if len(sys.argv) > 3 else "shorts"; d = f"state/{slug}/{sub}"; rec_f = f"{d}/uploaded.json"
rec = SF.read_json(rec_f, {}) or {}
todo = []
for mp4 in glob.glob(f"{d}/*.mp4"):
    mf = mp4[:-4] + ".json"
    if os.path.basename(mp4) in rec or not os.path.exists(mf): continue
    mj = json.load(open(mf))
    if mj.get("qa_fail") and os.environ.get("QA_OVERRIDE") != "1":   # scripts/qa_clip.py / vod_shorts / vod_long flag a draft that failed the automatic grade (sync, dead air, chopped audio, word cut, caption overflow, title not in the transcript)
        print("SKIPPED (qa_fail)", os.path.basename(mp4), "|", "; ".join((mj.get("qa") or {}).get("fail", []))[:220], "(QA_OVERRIDE=1 uploads anyway)"); continue
    todo.append((mj.get("score", 0), mp4, mf))
todo.sort(reverse=True); n = 0
for sc, mp4, mf in todo[:mx]:
    meta = json.load(open(mf)); meta["privacy"] = "private"; meta["tags"] = list(dict.fromkeys(meta.get("tags", []) + (["Shorts"] if sub == "shorts" else []) + [slug])); SF.write_json(mf, meta, indent=None)
    th = mp4[:-4] + ".jpg"; cmd = [sys.executable, "scripts/yt_upload.py", mp4, mf] + ([th] if sub != "shorts" and os.path.exists(th) else [])   # long videos carry a custom thumbnail
    r = subprocess.run(cmd, capture_output=True, text=True, env=dict(os.environ, CHANNEL_YT="en"))
    url = [l for l in r.stdout.splitlines() if l.startswith("https://youtu.be/")]
    print(("UPLOADED " + url[-1] + " | " + meta["title"]) if url else ("FAILED " + (r.stdout + r.stderr)[-300:]))
    if url: rec[os.path.basename(mp4)] = url[-1]; n += 1; SF.write_json(rec_f, rec)
    elif "UPLOAD_HOLD" in r.stdout: print("upload hold active, stopping"); break
    elif "quota" in (r.stdout + r.stderr).lower(): print("quota reached, stopping"); break
    elif "REFUSED" in r.stdout: print("upload refused by the channel guard, stopping"); break
SF.write_json(rec_f, rec); print("uploaded", n, "of", len(todo), "pending")

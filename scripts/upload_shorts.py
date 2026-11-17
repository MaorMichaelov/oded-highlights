#!/usr/bin/env python3
"""Uploads the Shorts of state/<slug>/shorts/*.mp4 (+ .json meta) as PRIVATE drafts to the English channel (CHANNEL_YT=en, YT2_* secrets; yt_upload.py refuses any channel but the verified id in config/channels.json).
usage: upload_shorts.py <slug> [max]   Highest score first; already uploaded files are remembered in state/<slug>/shorts/uploaded.json."""
import glob, json, os, subprocess, sys
slug = sys.argv[1]; mx = int(sys.argv[2]) if len(sys.argv) > 2 else 6; d = f"state/{slug}/shorts"; rec_f = f"{d}/uploaded.json"
rec = json.load(open(rec_f)) if os.path.exists(rec_f) else {}
todo = []
for mp4 in glob.glob(f"{d}/*.mp4"):
    mf = mp4[:-4] + ".json"
    if os.path.basename(mp4) in rec or not os.path.exists(mf): continue
    todo.append((json.load(open(mf)).get("score", 0), mp4, mf))
todo.sort(reverse=True); n = 0
for sc, mp4, mf in todo[:mx]:
    meta = json.load(open(mf)); meta["privacy"] = "private"; meta.setdefault("tags", []).extend(["Shorts", slug]); json.dump(meta, open(mf, "w"), ensure_ascii=False)
    r = subprocess.run([sys.executable, "scripts/yt_upload.py", mp4, mf], capture_output=True, text=True, env=dict(os.environ, CHANNEL_YT="en"))
    url = [l for l in r.stdout.splitlines() if l.startswith("https://youtu.be/")]
    print(("UPLOADED " + url[-1] + " | " + meta["title"]) if url else ("FAILED " + (r.stdout + r.stderr)[-300:]))
    if url: rec[os.path.basename(mp4)] = url[-1]; n += 1
    elif "quota" in (r.stdout + r.stderr).lower(): print("quota reached, stopping"); break
    elif "REFUSED" in r.stdout: print("upload refused by the channel guard, stopping"); break
json.dump(rec, open(rec_f, "w"), indent=1); print("uploaded", n, "of", len(todo), "pending")

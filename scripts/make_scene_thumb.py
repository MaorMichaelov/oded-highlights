#!/usr/bin/env python3
"""One-command thumbnail: scene WITH the streamer inside (Cloudflare klein + portrait references) + Hebrew headline + QA.
This is the owner-approved template (14 Nov 2026): big face inside the scene, hand on cheek / strong expression, a story prop, headline top-right.
usage: make_scene_thumb.py --slug gta6_first --scene "<scene+props+lighting>" --expr "<expression/pose>" --head "פעם ראשונה" --accent "ב-GTA 6!" [--refs shock,excited,smirk] [--seeds 3]
Outputs assets/scenes_ai/<slug>_s<seed>.jpg (raw scenes) and assets/final_thumbs/<slug>_s<seed>.jpg (with headline). Pick the best by eye."""
import argparse, base64, json, os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
ACC = os.environ.get("CF_ACCOUNT_ID", "3edbd7bb8767f3894f5345e53d3fb0a6")
BASE = ("Photorealistic cinematic YouTube thumbnail, 16:9, ultra sharp, vivid saturated colours. The man from the reference photos (keep his exact face, beard, dark hair "
        "and black headphones, same identity, no changes) is the hero in the scene, face very large on the left half of the frame. No text, no logos, no watermarks, no extra fingers, one coherent scene. ")
def refs_to_480(names, tmp):
    from PIL import Image; out = []
    for n in names:
        im = Image.open(os.path.join(ROOT, "assets", "portraits", n + ".jpg")).convert("RGB").crop((60, 0, 964, 904)).resize((480, 480), Image.LANCZOS)
        f = os.path.join(tmp, n + ".jpg"); im.save(f, quality=93); out.append(f)
    return out
def gen(prompt, refs, seed):
    cmd = ["curl", "-sS", "-m", "170", "-X", "POST", f"https://api.cloudflare.com/client/v4/accounts/{ACC}/ai/run/@cf/black-forest-labs/flux-2-klein-4b", "-F", f"prompt={prompt}", "-F", "width=1280", "-F", "height=720", "-F", f"seed={seed}"]
    for i, r in enumerate(refs): cmd += ["-F", f"input_image_{i}=@{r}"]
    if os.environ.get("CF_API_TOKEN"): cmd += ["-H", "Authorization: Bearer " + os.environ["CF_API_TOKEN"]]
    d = json.loads(subprocess.run(cmd, capture_output=True, text=True).stdout); img = (d.get("result") or {}).get("image") if d.get("success") else None
    if not img: print("failed:", str(d.get("errors"))[:200]); return None
    return base64.b64decode(img)
if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--slug", required=True); ap.add_argument("--scene", required=True); ap.add_argument("--expr", default="pure shock, mouth open, one hand on his cheek")
    ap.add_argument("--head", required=True); ap.add_argument("--accent", default=""); ap.add_argument("--refs", default="shock,excited,smirk"); ap.add_argument("--seeds", type=int, default=3); ap.add_argument("--grad", default="255,238,10:255,150,40")
    a = ap.parse_args(); os.makedirs(os.path.join(ROOT, "assets", "scenes_ai"), exist_ok=True); os.makedirs(os.path.join(ROOT, "assets", "final_thumbs"), exist_ok=True)
    tmp = tempfile.mkdtemp(); refs = refs_to_480(a.refs.split(","), tmp)
    prompt = BASE + f"His expression: {a.expr}. Scene, props and lighting: {a.scene}. Top 25 percent of the frame is calm and darker."
    for seed in range(1, a.seeds + 1):
        raw = gen(prompt, refs, seed * 7)
        if not raw: continue
        sp = os.path.join(ROOT, "assets", "scenes_ai", f"{a.slug}_s{seed}.jpg"); open(sp, "wb").write(raw)
        fp = os.path.join(ROOT, "assets", "final_thumbs", f"{a.slug}_s{seed}.jpg")
        cmd = [sys.executable, os.path.join(HERE, "thumb_maker.py"), "--scene", sp, "--head", a.head, "--accent", a.accent, "--grad", a.grad, "--out", fp]
        r = subprocess.run(cmd, capture_output=True, text=True); print(seed, [l for l in r.stdout.splitlines() if "QA" in l])

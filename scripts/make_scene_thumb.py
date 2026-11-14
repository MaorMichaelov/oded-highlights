#!/usr/bin/env python3
"""One-command thumbnail: scene WITH the streamer inside (Cloudflare klein + portrait references) + Hebrew headline + QA.
This is the owner-approved template (14 Nov 2026): big face inside the scene, hand on cheek / strong expression, a story prop, headline top-right.
usage: make_scene_thumb.py --slug gta6_first --scene "<scene+props+lighting>" --expr "<expression/pose>" --head "פעם ראשונה" --accent "ב-GTA 6!" [--refs shock,excited,smirk] [--seeds 3]
Outputs assets/scenes_ai/<slug>_s<seed>.jpg (raw scenes) and assets/final_thumbs/<slug>_s<seed>.jpg (with headline). Pick the best by eye."""
import argparse, base64, json, os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
ACC = os.environ.get("CF_ACCOUNT_ID", "3edbd7bb8767f3894f5345e53d3fb0a6")
BASE = ("Photorealistic cinematic YouTube thumbnail, 16:9, ultra sharp, vivid saturated colours. The man from the reference photos (keep his EXACT face, same identity, same narrow face shape, same eyes, same nose, same thick dark beard, same messy curly dark hair, "
        "wearing the same dark grey crew-neck sweatshirt and the same black over-ear headphones, no changes at all) is the hero in the scene, face very large on the {side} half of the frame. No text, no logos, no watermarks, no extra fingers, one coherent scene. ")

# ---- style presets per video type (vary the scene/costume/prop/colours with the topic) ----
PRESETS = {
 "game_launch": dict(scene="neon tropical city boulevard at sunset, a red sports car, palm trees, pink and orange sky, glowing neon signs", expr="pure shock, mouth open, one hand on his cheek", grad="255,238,10:255,150,40"),
 "phone_call": dict(scene="dark emerald-green cinematic background PACKED densely with large flying US dollar bills everywhere, dozens of big bills close to the camera with strong depth-of-field blur and many smaller ones behind, a bright neon green glow and green rim light on the edges of his hair and shoulders. His FACE is brightly and warmly lit by a strong soft key light from the front-left with vivid skin highlights, crisp contrast and glowing healthy skin tones, like a professional portrait. A vertical warm yellow-orange light streak glows far behind him in the top-right corner, never touching his headphones. His headphones stay matte black with no yellow reflection. He is on the RIGHT half of the frame, very close to the camera, laughing hard with a huge open-mouth grin and looking down at a smartphone he holds in front of his chest, the phone has its BACK to the viewer with a triple camera lens. Exactly two hands and arms in total, never three. The left 40 percent of the frame is only dark green with flying bills (a phone will be added there later)", expr="huge excited laugh, mouth wide open, looking at his phone", side="right", refs="real/laugh_01,real/smile_01,real/explain_01,real/smirk_02", grad="255,238,10:255,150,40", overlay="phone", box=(80, 40, 340, 620, -2), hbox="255,640,452,0.56", ribbon=True, glow=(40, 230, 90), accent=(40, 205, 90), alt="phone_call_b"),
 "phone_call_b": dict(scene="deep purple and black cinematic background filled with hundreds of flying US dollar bills of different sizes with depth-of-field blur, violet glow and violet rim light on the edges of his hair and shoulders. His FACE is brightly and warmly lit by a strong soft key light from the front with vivid skin highlights, crisp contrast, like a professional portrait. A soft orange light bloom at the far left edge only, his headphones stay matte black with no glow or yellow reflection. He is on the LEFT half of the frame, very close to the camera, eyes wide open with a shocked grin, pressing ONE smartphone against his ear with one hand so only the BACK of the phone with its camera is visible to the viewer; his other arm hangs down out of frame. Exactly two hands and arms in total, never three. The right 40 percent of the frame is only dark purple with flying bills (a phone will be added there later)", expr="wide shocked eyes, mouth open, thrilled disbelief", side="left", refs="shock,excited,smirk", grad="255,238,10:255,150,40", overlay="phone", box=(965, 250, 265, 455, 3), glow=(190, 90, 255), accent=(40, 205, 90)),
 "heist": dict(scene="wearing a black beanie and a tactical vest, clutching a heavy sack of cash in a wrecked luxury jewellery shop, broken glass, red and blue police lights through the window", expr="wide panicked eyes, nervous grin", grad="255,238,10:255,60,60"),
 "lawsuit": dict(scene="wearing a dark suit and red tie in a mahogany law office with bookshelves and brass scales, holding a giant official envelope with a red stamp and wax seal toward the camera, warm lamp light", expr="stern intimidating stare, one eyebrow raised", grad="255,238,10:255,120,30"),
 "courtroom_ban": dict(scene="wearing a black judge robe, slamming a huge wooden gavel with orange sparks in a dark wood courtroom, a glowing screen with red X marks behind", expr="furious, teeth clenched", grad="255,238,10:255,90,40"),
 "airport_leave": dict(scene="wearing a pilot uniform and cap, holding a passport and a boarding pass in a bright airport departures hall with a sunset window and an airplane outside", expr="serious worried stare", grad="255,255,255:255,210,60"),
 "birthday": dict(scene="wearing a colourful party hat and bow tie, holding a cake with number candles, balloons and confetti, purple and gold party lights", expr="huge joyful laugh", grad="255,238,10:255,90,170"),
 "quiz_game": dict(scene="pointing at a giant glowing colourful quiz board on a game-show stage with spotlights and blue-purple haze", expr="excited confident grin, pointing at the camera", grad="255,238,10:255,150,40"),
 "rant": dict(scene="fists clenched, in a dark room with a stormy red and orange sky through the window, sparks and smoke", expr="screaming with rage, veins visible", grad="255,238,10:255,60,40"),
 "money": dict(scene="in a golden vault surrounded by flying cash bills and gold bars, golden rays", expr="greedy wide-eyed excitement, big grin", grad="255,238,10:255,160,0"),
 "ai_tech": dict(scene="wearing a white lab coat and safety goggles, holding a small glowing robot in a futuristic server room with blue light beams", expr="intense wide-eyed stare, pointing at the camera", grad="255,255,255:60,190,255"),
 "reaction_video": dict(scene="pointing at a giant floating video player screen showing a blurry clip, dark studio with purple and red light", expr="disbelief, mouth open, hand reaching out", grad="255,238,10:255,70,70"),
 "date_show": dict(scene="wearing a tuxedo and bow tie holding a red heart card in a glossy TV dating-show studio with neon hearts and an ON AIR sign, purple and pink lights", expr="flirty wink, finger pointing at the camera", grad="255,255,255:255,90,170"),
 "gaming_fail": dict(scene="both hands on his head in a dark gaming room with RGB lights and a glowing monitor, red and blue split lighting", expr="panic, mouth wide open", grad="255,238,10:255,90,40"),
 "sleeping_drunk": dict(scene="in a dark room with a cheeky grin pointing at a sleeping friend slumped on a gaming chair with a bottle, purple party lights", expr="mischievous laughing grin", grad="255,238,10:255,90,170"),
}

def refs_to_480(names, tmp):
    """names: portrait names (AI portraits, assets/portraits) or real/<name> (REAL Kick frames of Oded, assets/real_faces/oded): real frames keep his identity best."""
    from PIL import Image; out = []
    for n in names:
        if n.startswith("real/") and not os.path.exists(os.path.join(ROOT, "assets", "real_faces", "oded", n[5:] + ".jpg")): continue   # real frames are not in the public repo
        if n.startswith("real/"):
            im = Image.open(os.path.join(ROOT, "assets", "real_faces", "oded", n[5:] + ".jpg")).convert("RGB"); r = 480 / max(im.size); im = im.resize((int(im.width * r), int(im.height * r)), Image.LANCZOS)
            n = n.replace("/", "_")
        else:
            im = Image.open(os.path.join(ROOT, "assets", "portraits", n + ".jpg")).convert("RGB").crop((110, 10, 914, 814)).resize((480, 480), Image.LANCZOS)
        f = os.path.join(tmp, n + ".jpg"); im.save(f, quality=93); out.append(f)
    return out or refs_to_480(["laugh", "excited", "smirk", "shock"], tmp)
def gen(prompt, refs, seed):
    cmd = ["curl", "-sS", "-m", "170", "-X", "POST", f"https://api.cloudflare.com/client/v4/accounts/{ACC}/ai/run/@cf/black-forest-labs/flux-2-klein-4b", "-F", f"prompt={prompt}", "-F", "width=1280", "-F", "height=720", "-F", f"seed={seed}"]
    for i, r in enumerate(refs): cmd += ["-F", f"input_image_{i}=@{r}"]
    if os.environ.get("CF_API_TOKEN"): cmd += ["-H", "Authorization: Bearer " + os.environ["CF_API_TOKEN"]]
    d = json.loads(subprocess.run(cmd, capture_output=True, text=True).stdout); img = (d.get("result") or {}).get("image") if d.get("success") else None
    if not img: print("failed:", str(d.get("errors"))[:200]); return None
    return base64.b64decode(img)
if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--slug", required=True); ap.add_argument("--preset", choices=list(PRESETS)); ap.add_argument("--scene", default=""); ap.add_argument("--expr", default="")
    ap.add_argument("--head", required=True); ap.add_argument("--accent", default=""); ap.add_argument("--refs", default="shock,excited,smirk"); ap.add_argument("--seeds", type=int, default=3); ap.add_argument("--grad", default=""); ap.add_argument("--caller", default="ביגי")
    a = ap.parse_args(); pr = PRESETS.get(a.preset, {})
    a.scene = a.scene or pr.get("scene", ""); a.expr = a.expr or pr.get("expr", "pure shock, mouth open"); a.grad = a.grad or pr.get("grad", "255,238,10:255,150,40")
    if not a.scene: sys.exit("give --preset or --scene")
    os.makedirs(os.path.join(ROOT, "assets", "scenes_ai"), exist_ok=True); os.makedirs(os.path.join(ROOT, "assets", "final_thumbs"), exist_ok=True)
    tmp = tempfile.mkdtemp(); refs = refs_to_480(a.refs.split(","), tmp)
    base_pr = pr
    for seed in range(1, a.seeds + 1):
        avoid = ""
        pr = base_pr if seed == 1 or not base_pr.get("alt") else PRESETS[base_pr["alt"]]   # thumbnail B uses the alternative layout of the topic
        prompt = BASE.replace("{side}", pr.get("side", "left")) + f"His expression: {pr.get('expr', a.expr)}. Scene, props and lighting: {pr.get('scene', a.scene)}. Top 25 percent of the frame is calm and darker."
        raw = None
        if pr.get("refs"): refs = refs_to_480(pr["refs"].split(","), tmp)
        elif seed > 1: refs = refs_to_480(a.refs.split(","), tmp)
        for retry in range(4):   # Cloudflare sometimes flags (3030) a random seed: try another
            raw = gen(prompt, refs, seed * 7 + retry * 101)
            if raw: break
        if not raw: continue
        sp = os.path.join(ROOT, "assets", "scenes_ai", f"{a.slug}_s{seed}.jpg"); open(sp, "wb").write(raw)
        if pr.get("overlay") == "phone":   # clean drawn call screen (AI garbles phone UI): real details, correct orientation
            from PIL import Image; sys.path.insert(0, HERE); import phone_ui
            bx, by, bw, bh, tl = pr["box"]; im2, pbox = phone_ui.paste_phone(Image.open(sp).convert("RGB"), xy=(bx, by), size=(bw, bh), tilt=tl, glow=pr.get("glow", (40, 230, 90)), accent=pr.get("accent", (40, 205, 90))); im2.save(sp, quality=95)
            avoid = ",".join(str(v) for v in pbox)
        fp = os.path.join(ROOT, "assets", "final_thumbs", f"{a.slug}_s{seed}.jpg")
        cmd = [sys.executable, os.path.join(HERE, "thumb_maker.py"), "--avoid", avoid, *(["--hbox", pr["hbox"]] if pr.get("hbox") else []), *(["--ribbon"] if pr.get("ribbon") else []), "--scene", sp, "--head", a.head, "--accent", a.accent, "--grad", a.grad, "--out", fp]
        r = subprocess.run(cmd, capture_output=True, text=True); print(seed, [l for l in r.stdout.splitlines() if "QA" in l] or r.stderr[-300:])

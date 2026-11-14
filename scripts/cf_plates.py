#!/usr/bin/env python3
"""Generate people-free background plates with Cloudflare Workers AI (FLUX.2 klein 4B, Apache-2.0).
Auth: the token is injected by the environment proxy locally; in CI pass CF_API_TOKEN. Account id is not secret.
usage: cf_plates.py --all --outdir assets/plates_ai  |  --scene law_office --seed 3"""
import argparse, base64, json, os, subprocess, sys, time
ACC = os.environ.get("CF_ACCOUNT_ID", "3edbd7bb8767f3894f5345e53d3fb0a6")
BASE = "Photorealistic cinematic background plate for a YouTube thumbnail, 16:9, ultra sharp, saturated colours, dramatic split lighting (warm on one side, cool on the other), shallow depth of field. The left 45 percent of the frame is calmer and darker (empty space for a person), main details on the right. No people, no text, no logos, no watermarks. "
SCENES = {
 "law_office": "dark mahogany law office, floor-to-ceiling bookshelves, brass scales of justice on a desk, green banker lamp glowing, window blind light stripes, warm amber light.",
 "jewellery_store": "luxury jewellery shop at night after a break-in, glass cabinets full of diamonds and gold, shattered display window with glass shards on the floor, police car red and blue lights flooding through the window.",
 "alley_rain": "night alley with wet asphalt, brick wall with graffiti, a dumpster, police car lights in the distance, blue and red neon reflections, rain.",
 "airport": "bright airport departures hall, huge windows with a sunset and an airplane outside, flight information board, check-in desks, polished floor reflections.",
 "birthday": "party room with colourful balloons, string lights, confetti, a table with a cake, purple and gold lighting.",
 "tv_studio": "glossy TV dating-show studio set, neon hearts, LED wall in purple and pink, an ON AIR sign, two small cafe tables.",
 "quiz_arena": "game-show stage with a giant glowing multi-colour quiz board, spotlights, blue and purple haze.",
 "courtroom": "dark wood courtroom, judge bench with a giant wooden gavel on a block with orange sparks, a glowing screen with a list and red X marks.",
 "ai_lab": "modern lab with server racks, robotic arms, holographic blue beams, a white lab bench.",
 "throne_room": "red velvet throne room with gold details and a large glowing world map screen.",
 "gaming_room": "modern streamer studio room, desk with two glowing monitors and a microphone arm, RGB strip lights along the walls, shelves with figurines, purple and blue ambient light.",
 "game_launch": "neon sunset skyline of a tropical city, pink and purple sky, palm trees, sports cars on the street.",
 "casino": "casino floor with a roulette wheel and green felt table, neon signs in red and gold, scattered chips.",
 "election": "ballot box with a national emblem, papers flying in the air, yellow and blue burst light.",
 "horror_room": "dark room with an orange window light and a long creepy shadow of a hand on the wall.",
 "gta_beach": "tropical neon beach boulevard at golden sunset, palm trees, pink and orange sky, a classic lowrider car parked at the curb, glowing neon signs, ocean in the distance.",
 "gta_night_drive": "first-person view from inside a sports car driving at night through a neon city, glowing dashboard, wet road reflections, pink and cyan lights, skyscrapers.",
 "gta_skyline": "huge neon city skyline at dusk seen from a rooftop, purple and pink gradient sky, helicopters, palm trees, glowing billboards.",
 "hotel_street": "hotel street at night with neon palm signs, purple lights, wet road, a hotel entrance.",
}
def gen(name, seed=7, w=1280, h=720, outdir="assets/plates_ai"):
    os.makedirs(outdir, exist_ok=True); out = os.path.join(outdir, name + ".jpg")
    cmd = ["curl", "-sS", "-m", "150", "-X", "POST", f"https://api.cloudflare.com/client/v4/accounts/{ACC}/ai/run/@cf/black-forest-labs/flux-2-klein-4b",
           "-F", f"prompt={BASE}{SCENES[name]}", "-F", f"width={w}", "-F", f"height={h}", "-F", f"seed={seed}"]
    if os.environ.get("CF_API_TOKEN"): cmd += ["-H", "Authorization: Bearer " + os.environ["CF_API_TOKEN"]]
    r = subprocess.run(cmd, capture_output=True, text=True)
    try: d = json.loads(r.stdout)
    except Exception: print(name, "bad response", r.stdout[:150]); return False
    img = (d.get("result") or {}).get("image") if d.get("success") else None
    if not img: print(name, "failed:", str(d.get("errors"))[:200]); return False
    open(out, "wb").write(base64.b64decode(img)); print("saved", name, flush=True); return True
if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--all", action="store_true"); ap.add_argument("--scene", choices=SCENES); ap.add_argument("--seed", type=int, default=7); ap.add_argument("--outdir", default="assets/plates_ai"); a = ap.parse_args()
    names = list(SCENES) if a.all else [a.scene]
    for n in names:
        if os.path.exists(os.path.join(a.outdir, n + ".jpg")) and a.all: continue
        gen(n, a.seed, outdir=a.outdir); time.sleep(1)

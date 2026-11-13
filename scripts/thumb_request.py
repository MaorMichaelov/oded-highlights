#!/usr/bin/env python3
"""Build a ready-to-paste request pack for the scene generator (Grok Bot GenerateImage has no API: human-in-the-loop).
usage: thumb_request.py --slug gta6_first --topic "..." --scene "..." --expr shock --head "הפעם הראשונה" --accent "ב-GTA 6!" [--guests "..."]
Writes research/requests/<slug>/{prompt.txt, README.txt} and prints the prompt. After the image comes back:
  python3 scripts/thumb_maker.py --scene scene.png --head "..." --accent "..." --ribbon --out thumb.jpg
Expression tags available in the owner's face library: laugh, facepalm, stare, smile, explain, lean-in, smirk.
"""
import argparse, os, textwrap
ap = argparse.ArgumentParser()
ap.add_argument("--slug", required=True); ap.add_argument("--topic", required=True); ap.add_argument("--scene", required=True)
ap.add_argument("--expr", default="shock"); ap.add_argument("--head", required=True); ap.add_argument("--accent", default="")
ap.add_argument("--guests", default=""); ap.add_argument("--colors", default="saturated cinematic lighting")
a = ap.parse_args()
EXPR = {"shock": "jaw dropped, eyes wide open, extreme shock", "laugh": "huge open-mouth laugh, eyes squeezed, pure joy",
        "rage": "furious, teeth clenched, veins showing", "awe": "pure awe, mouth open, eyes sparkling", "smirk": "cocky half smirk, one eyebrow raised",
        "facepalm": "hand on forehead, disbelief"}
expr = EXPR.get(a.expr, a.expr)
prompt = (f"Photorealistic cinematic YouTube thumbnail, 16:9, ultra sharp, {a.colors}. The streamer from the reference photos "
          f"(keep his exact face, beard, dark hair and black headphones, same identity, no retouching) is the hero, very large in frame on one side, "
          f"expression: {expr}. Scene and props that tell the story: {a.scene}. "
          + (f"Other people in the same scene, smaller, with their own reactions: {a.guests}. " if a.guests else "")
          + "Clean uncluttered area in the top 30% for a headline. No text, no logos, no watermarks, no extra fingers, no collage, one coherent scene.")
d = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "research", "requests", a.slug); os.makedirs(d, exist_ok=True)
open(os.path.join(d, "prompt.txt"), "w", encoding="utf-8").write(prompt + "\n")
readme = f"""REQUEST PACK: {a.slug}
Topic: {a.topic}
1. In Grok Bot call GenerateImage with: aspect_ratio "16:9", reference_image_paths = 2-3 faces from thumb_assets/faces/oded (best match for tag "{a.expr}": see index.json),
   description = the text of prompt.txt.  Ask for 2 variants (C and D) with different composition.
2. Save the images and send them back (or drop them in the repo folder research/requests/{a.slug}/).
3. Headline to add: line 1 "{a.head}"  line 2 "{a.accent}"  -> python3 scripts/thumb_maker.py --scene IMG --head "{a.head}" --accent "{a.accent}" --ribbon --out thumb_c.jpg
"""
open(os.path.join(d, "README.txt"), "w", encoding="utf-8").write(readme)
print(prompt); print("\n--> saved to", d)

# Scene generation WITH the streamer inside (best method, found 14 Nov 2026)
Cloudflare Workers AI @cf/black-forest-labs/flux-2-klein-4b accepts up to 4 reference images (input_image_0..3, each < 512x512, we use 480x480 crops of the sharp AI portraits).
Prompt skeleton: "Photorealistic cinematic YouTube thumbnail, 16:9, ultra sharp, vivid saturated neon colours. The man from the reference photos (keep his exact face, beard, dark hair and black headphones, same identity, no changes) is the hero in the scene. <SCENE + POSE + EXPRESSION + lighting colours>. Face large on the left. Top 25 percent clean. No text, no logos, no extra fingers, one coherent scene."
Then headline: python3 scripts/thumb_maker.py --scene scene.jpg --head ... --accent ... (face-aware placement + QA).
No cut-out needed: the person is lit by the scene. Identity is close but not exact -> generate 3-4 seeds, pick the most similar by eye (or ArcFace later).
Examples in assets/scenes_ai/. Refs: assets/portraits (oded_ai_faces from Grok Bot).

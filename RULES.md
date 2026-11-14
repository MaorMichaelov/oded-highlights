# Operating rules (ODED HIGHLIGHTS pipeline)

- Upload only to the ODED HIGHLIGHTS channel. Never delete anything on YouTube.
- Long videos only (>= ~6 min), one complete topic per video. No gambling content, no waiting screens.
- Render 1920x1080 60fps, libx264 crf 18, AAC 192k, +faststart. Never use `-ss` on a concat of .ts segments (use trim/atrim).
- Opening: cold-open montage (3 shots, word-by-word captions), green logo sting, then content; subscribe popup a few seconds in. No premise card.
- Thumbnails: one cohesive scene, big expressive face, 2-3 word Hebrew headline, headline never covers faces. No collages.
- Hebrew title 40-55 chars naming the people in the story, ends with ! or ?!. Description with chapters + credit kick.com/odedsvr.
- Budget is 0: use free tiers only (GitHub Actions, Groq free Whisper, YouTube API).
- Priority topic for the GTA 6 subathon: the first reaction / first time entering the game.
- Never put tokens or keys in this repo. They live in GitHub Actions secrets.

## Owner feedback (permanent rules)
- Opening captions use the BRAND GREEN (120,230,40), not yellow (peak_open_lowmem.py REF_YEL).
- NO arbitrary zooms / punch-ins. Only reframe or crop when it has a clear purpose (e.g. a screen-share where the content is tiny). Default: no zoom.
- Keep the logo sting + subscribe popup; they should look closer to the Taklipu reference (animated wipe, logo bounce, cursor click) - improvement in progress.
- Test uploads are Private and titled with "בדיקה:" until the owner approves. Never delete anything.
- Transcription audio must come from the 480p30 rendition (102 kbps AAC), not 160p (51 kbps): measured on the same 150 s, 160p produced garbled phone-call text, 480p was readable.

- NO red ribbon behind the headline (owner: it looks bad). Ribbon only if explicitly requested.
- THUMBNAIL BACKGROUNDS (approved by owner 14 Nov 2026): photorealistic people-free plates from Cloudflare Workers AI flux-2-klein-4b (scripts/cf_plates.py, assets/plates_ai/).
  Portrait = sharp AI portraits (assets from Grok, 8 expressions). Headline = scripts/thumb_maker.py. Never copy another channel's image files; learn their rules only.
  Cloudflare token is stored by the environment proxy; account id 3edbd7bb... is not secret. Daily free quota ~100 images; generate per-topic plates on demand (new seed/prompt).
- APPROVED THUMBNAIL TEMPLATE (owner: "זה טוב", 14 Nov 2026): scripts/make_scene_thumb.py -> scene generated WITH Oded inside (Cloudflare klein + his sharp AI portraits as refs),
  face very large on the left, strong expression/hand gesture, story prop + neon scene, headline top-right (white line + yellow/orange gradient line, thick black outline).
  Always generate 3 seeds, LOOK at them before sending, pick the closest likeness, never send a thumbnail whose QA says overlap_ok=False.

## Thumbnails: always TWO per video (owner, 14 Nov 2026)
Every video gets two different thumbnails (A and B) for YouTube "Test & compare" (Studio only, the API cannot do it). The pipeline uploads A with the video and keeps B in the workflow artifact / assets/final_thumbs/<id>_s2.jpg.
The props must match what happens in the topic (no money bills in a phone-call thumbnail). Owner called the 14 Nov phone-call thumbnails "very bad": generic AI guy, irrelevant money, random neon street.
Owner feedback 14 Nov (evening): the face of Oded is great ("מטורף, בדיוק איך שביקשתי"); busy neon backgrounds and small headline were the weak part. Backgrounds: calm, blurred (shallow depth of field), related to the topic, empty space on the right for the headline. Phone-call preset updated accordingly (v2test).

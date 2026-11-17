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
Owner showed Grok Bot's thumbnails for the same video (14 Nov): vivid saturated purple/orange glow background, one HUGE glowing prop (phone with green/red call buttons) on the right, a few bills flying, big headline top-right, huge face on the left. Match this energy: saturated, glowing, simple background, one big topic prop. phone_call preset = v3test.
Thumbnail QA (owner 14 Nov, strict on details): (1) exactly two hands, never three; (2) a phone held to the ear shows its BACK to the viewer, the screen is against the ear; (3) screens/UI/props must have real, readable details: phone UI is DRAWN with scripts/phone_ui.py (not AI), caller name, green accept and red decline icons. Reject seeds that fail by eye. gen() retries other seeds when Cloudflare flags a prompt (3030).
Thumbnail A/B (owner 14 Nov): each video gets TWO different layouts (preset + its "alt" preset). phone_call: A = Oded shocked with phone at ear + drawn call screen lower-right; B = Oded laughing at his phone on the right, green money background, big call screen on the left. The headline must NOT cover the screen/prop: pass --avoid zones to thumb_maker.py (make_scene_thumb does it).
Phone-call thumbnail v6 (owner reference = Grok "הכל זה כסף"): DARK emerald (or deep purple) cinematic background with HUNDREDS of flying dollar bills at different depths + warm light bloom at an edge; a thin-bezel UPRIGHT phone drawn by phone_ui.py with dynamic island, neon glow, dark-green screen, ONE big white handset icon with 3 waves and one wide green call button (no avatar, no red button, no text); Oded close-up big laugh looking at his phone (back with camera lenses visible) or phone at ear; headline never on the phone/face. Study the reference image details before changing anything; owner is very strict and notices small details.
LIGHTING (owner 14 Nov): the face must be BRIGHTLY lit (strong soft key light, vivid skin highlights, rim light in the background colour) like the Grok reference. A flat unlit face "looks like shit". Warm glow only far behind, never on the headphones.
OWNER REFERENCE 1:1 (14 Nov): when the owner shows a reference thumbnail and says "אחד לאחד" he wants the SAME composition: big upright glowing phone at the left (x 80-420), Oded close-up laughing on the right with his phone in hand, dense money background, yellow-orange light streak top-right, headline bottom-centre over the phone's lower edge on a red torn ribbon (white line 1 + yellow line 2). Preset phone_call = this layout (hbox + ribbon). Identity: 4 tight-cropped portrait refs + "same messy curly hair, dark grey sweatshirt" in the prompt.
How Grok Bot makes thumbnails (from its handoff THUMBS_CLAUDE.md): built-in GenerateImage tool, only inside Grok Bot (no API), 16:9, reference_image_paths = REAL 1080p Kick frames of Oded (3-5 per video, clean face, no mic/overlay), one coherent scene, no Hebrew in the AI image, Hebrew headline added by overlay.py (Heebo Black, white line1 stroke 12 + yellow-orange line2 stroke 16, red torn ribbon, rotation 4 deg, sizes tuned by hand per image), two variants C and D per video. Our make_scene_thumb.py mirrors this; real frames go in assets/real_faces/oded (gitignored: not in the public repo).
GROK BOT'S INSTRUCTIONS (owner pasted 14 Nov): drafts = private + full Hebrew title/description, NO thumbnail (other bot does thumbnails + publishing); 1080p60 only, crf 18, >8 Mbps, never 720p; opening without premise card, captions same size/style as 5zTSmoByVyA at ~80% height, then green sting, then subscribe popup; topic_scan never uploads alone (candidates are marked in state/pending_candidates.json); every relevant topic gets a clip; long videos only; smart_reframe off; repo should be private (CONFLICT: private repo = 2000 Actions min/month, the 24/7 loop needs ~43000; owner to decide); GTA 6 marathon: loop must survive 6 h limit; draft brief about/who/peak.

## Draft review rules (owner + Grok Bot, 15 Nov 2026)
- A clip starts and ends at the end of a sentence (never mid-sentence). One topic only; topics that belong to another clip are not repeated.
- No silence, empty chair, donation reading, or digressions (automatic: dead air > 5 s trimmed, donation sentences removed, hard lines removed).
- Time stamps in the description (chapters, "הרגע החזק") must match the video: the strongest moment is computed from the real cut.
- Long videos only, NO Shorts (render-clip shorts input defaults to false). 1080p60.
- Never upload duplicates of the same clip: one clip = one render. If a clip is corrected, re-render once; the owner deletes the old draft (the system never deletes on YouTube).

- LENGTH (owner, 15 Nov): every clip 15-40 min and a COMPLETE topic (e.g. the whole cooking with his wife). Short fragments of 4-6 min are wrong. The topic-span picker (timeline spans -> pick) enforces it; clips under 15 min after cleaning are skipped.
- ACCURACY: titles/descriptions/brief must describe what is really in the clip; names in Hebrew; peak time computed from the real cut.

- GREAT SESSIONS ARE LONG (owner, 15 Nov, from a viewer comment on the 36-pokemon-packs video: "15 minutes can't summarise all this fun, watch the live"): a strong session (pack opening, game session, challenge, event, big guest) is kept WHOLE, 30-35 min at least and up to 60 min; the 15-min minimum is only for ordinary topics.

- REACTIONS ARE SHORT-OK (owner, 15 Nov): a reaction to articles / videos / trailers of other creators is cut even at 6-8 min, with few cuts (kept continuous); the 15-min minimum does not apply to kind=reaction. Reaction to GTA 6 content is a priority topic.

- BIG LIVE EVENTS ARE ONE LONG VIDEO (owner, 15 Nov): e.g. in the subathon (Thu 19 Nov) he brings a dog and buys everything for it live: that is ONE video of about 1 hour (up to 75 min kept whole), not 15-min pieces. Same for any IRL / shopping / challenge / pack-opening event.

- REACTION CONTENT (owner, 15 Nov): the video he reacts to can be in English / by any creator. While reacting he asks the chat about the video or talks about it: that is part of the reaction and STAYS in the clip (do not cut it as a digression). Reactions need few cuts, only here and there.

- CHANNEL DISCLAIMER (Oded himself commented, 15 Nov): every description says where the clips come from (Oded's Kick live) and that this is NOT the official channel (an unofficial fan channel); links to kick.com/odedsvr and his official YouTube channel @OdedSVRLive.

- GROK'S UPLOADS ARE THE QUALITY BAR (owner, 16 Nov): see docs/GROK_EXAMPLES.md. One video per source (a news report and a different report = two videos), title `עודד מגיב ל"<original title>" של <outlet/creator>`, description first line = fan-channel disclaimer + kick link, 2-3 specific sentences, SEO line, credit, chapters about every minute for reactions (every 3-5 min for long sessions) with real names/quotes, hashtags.

- HOW A NEWS/VIDEO REACTION IS EDITED (watched with Gemini, 16 Nov, see docs/GROK_EXAMPLES.md): highlight stitch, not raw stretch: ~14 cuts per 5 min, a hook of the 3 strongest moments, the body starts where the reacted video/article starts and ends when he closes it; keep his props/funny monologues, drop dry parts and chat-reading; one source per video.

- TWO CHANNELS (owner, 17 Nov): ODED HIGHLIGHTS = Oded only (Hebrew). WORLD CLIPS (the English channel, yt=en, secrets YT2_*) = Kai Cenat / N3on reactions and clips, long videos and Shorts. Never mix them. Nothing is uploaded to WORLD CLIPS until the owner connects the channel; until then the English Shorts stay as workflow artifacts.

- WORLD CLIPS streamers (owner, 17 Nov): start with N3on (Kick) and Kai Cenat (TWITCH; the owner brings the Twitch app key today); then maybe xQc / Trainwreck / Adin Ross (Kick). Priorities for the new channel: (1) PRECISION of where each clip starts and ends, (2) SPEED (being first to upload matters).

- CUT PRECISION (owner priority, 17 Nov): every clip start/end must be exact. Shorts use scripts/cutsnap.py (audio-energy onset/offset, pauses, boundary check, stretched-word cap). Long clips: pre-roll before the first sentence is 1.0 s (was 3.0 s: it dragged in the previous topic). Never start/end inside a word, no dead air > 0.6 s at either end.

- CLIPGLOBE LOGO (owner, 17 Nov): the channel logo is the owner's own artwork (yellow swoosh C around a red globe with a play button on black): assets/world_clips/logo_clipglobe.png. Use it EXACTLY as is (only resizing); never redraw, restyle or replace it, and do not make banners from it unless asked.

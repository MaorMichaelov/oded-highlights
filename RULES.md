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

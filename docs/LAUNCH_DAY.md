# GTA 6 launch day plan (release 18 Nov midnight, subathon Thursday 19 Nov)
Goal: be FIRST with the best clips, on the Hebrew channel (Oded) and an English channel; money comes from views (ads after YPP approval), affiliate links in every description, and growth (subs, watch hours).

## Already running (Hebrew)
Oded live-loop -> pick -> cut -> edit -> quality -> private drafts. First clip "עודד נכנס ומגיב בפעם הראשונה ל-GTA 6!" within ~15 min of his reaction.

## English channel (pilot, built 15 Nov)
- config/channels.json lists streamers (adinross, xqc, trainwreckstv: all on Kick, all play GTA). Start one with:
  gh workflow run live-loop-channel.yml -f channel=adinross -f lang=en -f yt=en   (needs the English YouTube channel secrets YT2_REFRESH_TOKEN / YT2_CLIENT_ID / YT2_CLIENT_SECRET; until then use yt=main to test).
- English ASR (faster-whisper large-v3-turbo), English titles (quote + streamer + what happened), credit line to the streamer in every description.
- Blocklist: a streamer who asks to be removed: create state/<slug>/PAUSE and delete their drafts.

## Money levers
1. Affiliate block: copy config/affiliate.txt.example to config/affiliate.txt with real links; every auto draft description gets it.
2. YPP: check YouTube Studio > Earn (1000 subs OK, 4000 public watch hours needed). Ads only count after approval.
3. Shorts (30-60 s cut of the strongest moment): NOT built yet. On the big clip channels shorts give 10-100x the views.

## Owner to do before Thursday
- Create the English YouTube channel and authorize it (I will guide), decide the streamers.
- Affiliate account + links. Written OK from Oded. Check YPP status.

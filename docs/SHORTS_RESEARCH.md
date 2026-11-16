# Shorts research (16 Nov 2026) - agent reports, saved for the implementation

## A. Where to start/stop a clip (agent report 1)
Evidence is thin: no source gives numeric thresholds; the parameters below are engineering defaults to be tuned on 20-30 clips rated by the owner.
Signals: chat rate (standard; only approximate position, chat lags the action ~3-4 s), emote spikes, audio energy, laughter/scream classifier (YAMNet/AudioSet; screams have many false alarms), transcript as semantic filter. Raids/giveaways/sub trains/bots create false spikes; loud audio can be music/cutscenes/alerts.
Algorithm:
1. 1 s bins: chat msgs/s, emotes/s, RMS audio energy, YAMNet laughter/scream prob, words/s.
2. Robust z-score (median/MAD) over a rolling 10 min window, 5 s smoothing, shift chat 4 s earlier.
3. S = 0.35 z_chat + 0.15 z_emote + 0.30 z_audio + 0.20 z_laugh_or_scream (clip z at 6); drop bins with raid/sub/bot rate > 3x normal.
4. Peaks: local maxima S > 2.5, >= 45 s apart, top N per hour.
5. LLM scores the transcript window [peak-30 s, peak+15 s] 1-10 and returns setup sentence + payoff sentence; F = 0.6 S_norm + 0.4 llm/10.
6. START: setup sentence start (else peak-12 s), snap to the preceding word start minus 0.2 s, lead-in 8-25 s (Shorts), up to 45 s for long clips.
7. END: peak+3 s moved to the sentence end + 0.4 s; extend while audio energy > 60% of the peak, up to 6 s. Never end on trailing silence.
8. Length: Shorts 20-58 s; longer clips 60-180 s.
9. Reject: z_audio < 1.5 and z_chat < 1.5; LLM score < 6; > 25% silence or < 0.5 words/s outside the peak; mid-word start/end; overlaps a stronger clip; within 2 min of a raid/giveaway/sub event.
First-time-reaction structure: 0-3 s hook, 3-20 s buildup (10-25 s for jump scares), peak, 3-5 s aftermath, cut.
Word timing: Whisper is coarse; WhisperX / stable-ts / whisper-timestamped are better.

## B. Shorts editing rules (agent report 2; vendor heuristics, A/B test in Studio)
1 Length 20-45 s (cap 60 s unless retention stays flat; 3 min allowed but no evidence it wins). 2 Frame 0-1 s = the peak reaction (cold open). 3 On-screen hook text on frame 0, 3-6 words, 2-3 s. 4 Start <= 0.5 s before the first beat, no silence > 0.4 s. 5 End on the punchline + 0.3-0.5 s, no outro/CTA. 6 Loop: last frame/line echoes the first. 7 1080x1920, 30/60 fps, H.264, from the highest-res source. 8 Stacked layout: face-cam ~1080x800 top, gameplay ~1080x700 below, captions lower-middle; no black bars (blurred fill). 9 Keep key content in a centered 900x1400 box; nothing in the bottom 300-380 px / right 165 px. 10 Switch layout at scene changes. 11 Burned-in captions 64-72 px bold, white + 3 px black stroke. 12 2-5 words/group, max 2 lines, new group every 0.4-1.0 s, active word yellow. 13 Captions at y 1200-1550. 14 Keep original reaction audio; -14 LUFS, true peak <= -1 dBTP. 15 Music only from the YouTube Audio Library, ducked 15-20 dB. 16 Title 40-70 chars, hook first, no profanity; #Shorts + 2-4 hashtags. 17 1-3 Shorts/day on a fixed schedule. 18 Add original value per clip, vary templates (mass-produced = inauthentic-content risk). 19 Judge by viewed-vs-swiped (>= 70%) and avg % viewed (>= 80% for 20-45 s). 20 Strong profanity infrequent (since 29 Jul 2025 profanity in the first 7 s no longer limits ads, frequent profanity still does).
Since 31 Mar 2025 a Short view counts on start/replay; YPP earnings use "engaged views".

## C. Policy / risk (agent report 3; WebFetch was blocked, summaries only - verify official pages)
- YouTube "inauthentic content" (renamed 15 Jul 2025) + reused-content rules: clips/reactions are monetizable only with significant original commentary/edit/entertainment value; raw highlights of someone else's stream and templated mass uploads are the failing profile; enforcement is channel-level; the streamer's permission does not fix a reused-content problem.
- Permission/enforcement: no statement from Kai Cenat about clippers found; IShowSpeed's agency (Thumb Media) has been accused of Content-ID claims on small creators; paid clipping campaigns exist (Whop, Content Rewards, Kick) but only on supplied footage.
- GTA: Rockstar's policy allows NON-COMMERCIAL use only; Take-Two can remove content; avoid spoilers/leaks and cutscene-only clips. Stream music can cause Content-ID claims.
- Overall: MEDIUM-HIGH for a raw-highlight channel, MEDIUM if heavily transformed. Checklist: transformative edits/commentary, short excerpts, credit + "unofficial fan channel" line, vary templates, take down on request, check music, keep a backup plan, no fake views.

## D. Sources and content (agent report 4)
- GTA VI releases 19 Nov 2026 (PS5/Xbox Series only, no PC). Kai's first-time GTA 6 gameplay cannot exist before then; he announced a 100% completion marathon at release. Existing material: Kai + IShowSpeed live reactions to the Netflix "Extended Look" (27 Aug 2026, Twitch), Kai's GTA marathon III..V (from 5 Nov, ~130 h, Twitch+YouTube).
- Kai Cenat streams on Twitch AND YouTube simultaneously; not on Kick (Kick API shows empty placeholder channels for kaicenat/ishowspeed). YouTube media cannot be downloaded from datacenter IPs (bot check); Twitch is the media source.
- Twitch: Helix app token (free client id/secret): /streams?user_login= (live), /videos?user_id=&type=archive (VODs), /clips?broadcaster_id=&started_at=&ended_at= (windows <= 1 day, paginate). Clip/VOD files: yt-dlp (unverified from GitHub runners; test), `--download-sections`. VOD retention: Partner ~60 days (inferred). VOD chat: no official endpoint; TwitchDownloaderCLI chatdownload (unofficial GQL) to find chat spikes.
- N3on: streams on KICK (verified, 1.26M followers, Kick API returns VODs; many streams are Jack.com gambling giveaways: gambling segments must be skipped, scripts/gambling.py exists).

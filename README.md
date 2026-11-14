# oded-highlights

Automation for turning Kick live streams (kick.com/odedsvr) into long Hebrew highlight videos for the ODED HIGHLIGHTS YouTube channel. Budget: $0.

## Pipeline map
| Stage | Where | Script |
|---|---|---|
| 1. Detect live + ingest audio + transcribe | GitHub Actions `live-loop` (every 5 min, self-chaining) | `scripts/live_watch.py` |
| 2. Choose a finished topic, write the cut list | Claude (scheduled session) | `docs/`, `RULES.md` |
| 3. Cut body (1080p60 ranges), opening, captions, sting, subscribe popup | scripts | `scripts/build_clip.py`, `scripts/peak_open/nov13_open.py` |
| 4. Thumbnail: scene WITH the streamer inside + Hebrew headline + QA | Cloudflare Workers AI (free) | `scripts/make_scene_thumb.py` (+ `thumbnail.yml`) |
| 5. Package (3 thumbnail candidates + metadata) | script | `scripts/package_clip.py state/clips/<id>` |
| 6. Upload (private first, owner approves) | YouTube Data API | `scripts/yt_upload.py` |

## Thumbnails (owner-approved style, 14 Nov 2026)
`python3 scripts/make_scene_thumb.py --slug my_clip --preset phone_call --head "מתקשר" --accent "לעמית שיבר!" --seeds 3`
15 presets by video type (`PRESETS` in the script): game_launch, phone_call, heist, lawsuit, courtroom_ban, airport_leave, birthday, quiz_game, rant, money, ai_tech, reaction_video, date_show, gaming_fail, sleeping_drunk.
Portraits: `assets/portraits/` (8 sharp AI expressions). Plates only (no person): `scripts/cf_plates.py`, `assets/plates_ai/`. Game videos: `scripts/thumb_game.py` (gameplay frame + portrait).
Rules and learned style: `RULES.md`, `docs/THUMBNAIL_*.md`. Research: `research_notes/`.

## Secrets (GitHub Actions)
`GROQ_API_KEY` (transcription), `CF_API_TOKEN` (Cloudflare Workers AI, for `thumbnail.yml`). The YouTube token is kept outside the repo.
No secrets are stored in this repo.

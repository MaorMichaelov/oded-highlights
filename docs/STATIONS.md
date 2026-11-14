# The stations (production line)
Each station is one script with a clear input/output, writes state/clips/<id>/status.json (state + seconds) and can be run and tested alone.

| # | station | script | in -> out | runs in |
|---|---|---|---|---|
| 1 | WATCH / RECORD | scripts/live_watch.py, chat_poll.py, autopilot.py (GTA 6 first reaction) | Kick API -> state/transcripts, chat, category | .github/workflows/live-loop.yml (every 5 min, self-chaining) |
| 2 | PICK | scripts/stations/pick.py (Groq gpt-oss-120b + docs/TOPICS_TO_CLIP.md) | closed transcript -> state/clips/<id>/{cuts,spec}.json -> dispatch | live-loop (after every ingest) |
| 3 | CUT | scripts/stations/cut.py (build_clip.py) | cuts.json -> work/body.mp4 (1080p60 only, 12 Mbps) | render-clip.yml |
| 4 | EDIT | scripts/stations/edit.py (render_clip.py, peak_open/) | body.mp4 -> final.mp4 (opening, sting, popup, stream-copy join) | render-clip.yml |
| 7 | QUALITY | scripts/stations/quality.py | final.mp4 -> quality.json, exit 5 blocks the draft | render-clip.yml |
| 5 | DRAFT | scripts/stations/draft.py (yt_upload.py) | final.mp4 -> private YouTube draft (no thumbnail) | render-clip.yml |
| 6 | MONITOR | scripts/stations/monitor.py | runs/state -> state/health.json, GitHub issue on problems, restarts the live loop | .github/workflows/monitor.yml (every 20 min) |

Run one station alone (example, on a clip folder that exists): `python3 scripts/stations/quality.py state/clips/<id>`.
Different clips render in parallel (concurrency group per clip). Thumbnails and publishing belong to the other bot (drop files in assets/thumbs_override/).
Rules enforced in code: 1080p60 only (build_clip refuses anything else), > 8 Mbps, no silence/black, nothing uploads except as PRIVATE drafts, heuristics never upload alone.

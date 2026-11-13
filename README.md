# oded-highlights

Automation for turning Kick live streams (kick.com/odedsvr) into long Hebrew highlight videos for the ODED HIGHLIGHTS YouTube channel.

Layout:
- `scripts/` editing and VOD tools (branding, captions, zooms, opening, transcription helpers)
- `assets/` channel logo and sound effects
- `state/` run logs (which VODs/topics were done, uploaded, rejected). Committed so nothing is processed twice.
- `RULES.md` operating rules

No secrets are stored here.

## Links
- Privacy policy: [PRIVACY.md](PRIVACY.md)

## Thumbnail maker (`scripts/thumb_maker.py`)
Zero-cost, automatic: real face frame -> upscale/recover -> person cut-out (rembg) -> sticker outline + glow -> themed sunburst background ->
Hebrew headline on the opposite side -> QA (headline never overlaps the face, <2 MB, 168x94 preview).
`python3 scripts/thumb_maker.py --frame F.png --crop x0,y0,x1,y1 --head "הכל זה" --accent "כסף!" --theme money --side right --out thumb.jpg`
Themes: green, danger, party, money, cool. Needs: pillow numpy opencv-python-headless rembg onnxruntime. An AI-generated scene can be passed with `--bg`.

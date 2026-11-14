# Thumbnail style bible (learned from the owner's reference screenshots, Nov 2026)

Source: ~40 thumbnails of Taklipu (Israeli clip channel) and OdedSVR Live that the owner sent as the target quality.
Observed, not measured. Measured rules and scoring: see research_notes/.../thumbnail_style_bible_scoring.md.

## Core idea
ONE literal story scene, photorealistic, that a stranger can read in 1 second. The video's TOPIC is turned into a COSTUME + PROP + PLACE:
| Video topic | Scene concept seen in the references |
|---|---|
| Rob Run heist | jewel thief in tactical vest holding a sack of diamonds inside a jewellery store |
| Streamer got a lawsuit letter | lawyer suit, stamped envelope "מכתב תביעה רשמי", shocked guests behind |
| Trip went wrong (Netanyahu poster) | hotel umbrella as a weapon, neon palm street at night |
| Leave everything / leaving the country | pilot uniform, passport, boarding pass, airport, worried guest |
| Anime reaction (avatar) | the streamer dressed as Aang with glider on a mountain temple |
| Dating-show reaction | tuxedo, heart card, three guests with cute reactions, TV studio |
| Guess-who game vs a streamer | the streamer in a detective hat holding a giant guess-who board with faces |
| Strategy game on stream | king with crown and sceptre, world map behind |
| AI revolution talk | scientist goggles holding a small robot, server room |
| Birthday surprise for a viewer | party hats, 15 candle cake, balloons, the guest next to him |
| Merch calls | the shirt, a price badge "₪120!", laughing face |
| Gold weapon in danger | rain, police lights, a golden rifle |
| Phone call drama | phone at the ear, a UI mock (chat / order list) behind |

## Rules
1. Hero face LARGE, one side, extreme topic-matching expression (shock, joy, rage). Eyes visible and sharp.
2. Guests in the SAME scene, smaller, with their own reaction.
3. Saturated cinematic lighting with ONE colour story per video (neon purple/blue, gold, red/blue police).
4. Headline: 2-3 words, TOP of the frame, two lines max, white word + yellow word, very heavy black stroke, slight rotation (about -3 deg),
   sometimes on a red/yellow ribbon; never covers a face. Heavy Hebrew display weight (Heebo Black or heavier).
5. A prop readable at 168x94 (envelope, passport, diamonds, cake). Optional number badge "#2" for series; keep bottom-right free (duration badge).
6. Real UI mock elements (phone chat, quiz screen, Kick page) are used when the story is a call/quiz.
7. No collages. No visible watermarks/logos of other channels.

## Owner's own channel style (OdedSVR Live, different brand)
Serious real photo of the streamer large on the left, topic image on the right, almost no text. We do NOT copy this; ours follows Taklipu-level scenes.

## What our pipeline can and cannot do
- CAN: Hebrew headline in this style, face-aware placement, QA, 168x94 preview, theme colours (scripts/thumb_maker.py).
- CANNOT (no image model of its own): generate the scene. Scene = AI-generated with reference faces (Grok Bot / Gemini / future free API), then headline added here.
- Composite-from-video-frame thumbnails were rejected by the owner (twice). Do not ship them as final.

## Layout rules measured by eye from ~40 reference thumbnails (14 Nov 2026)
- Headline sits in the TOP band (about 80%): either a full-width bar across the top or a 2-line block top-right/top-left, above the heads, not on faces.
- Headline colour is a PAIR: white+yellow, yellow+red or white+orange; the 2nd colour matches the scene's colour story. Black outline ~10% of letter height, optional thin white outer line.
- Faces: 1 very large (45-60% of height) on the left/centre, bleeding off the bottom; eyes around the upper third; guests smaller on the opposite side.
- ONE readable prop next to the face that tells the story. For calls/quizzes/chats they draw a UI mock (incoming-call screen, order list, quiz board).
- One colour story per thumbnail (orange/green, purple/blue, gold, red/blue), dark vivid background with a glow behind the subject.
- Built by scripts/thumb_call.py (phone-call topic) as the first template; scripts/thumb_maker.py --react for "face + thing he reacts to".

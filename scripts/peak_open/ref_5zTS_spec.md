# Reference opening spec — youtube.com/watch?v=5zTSmoByVyA (measured 2026-11-13, 1920x1080, ~60fps)
Source: first 45 s downloaded to peak_open/ref5/ref.webm (analysis only; none of its audio/video is reused).

## Shot-by-shot timeline (cold open → intro)
| time (s) | on screen | transition IN | captions | audio |
|---|---|---|---|---|
| 0.00–2.65 | shot 1: dark interior, streamer finds a safe (GTA RP), webcam/chat HUD left as-is, NO zoom/shake | hard start (no fade) | word-by-word: "יש" → "יש פה" → "זהב" → "זהב אחי" → "פה" → "פה כספת" (כספת yellow) | ~0.5 s near-silence beat, then raw stream speech; NO music bed, NO sfx |
| 2.65–5.45 | shot 2: daylight street, character crouching | WHITE FLASH: 1 full-white frame, white fades out over ~0.2 s (gone by ~2.85) | "הם" → "הם צ'יטרים" (צ'יטרים yellow) → "צ'יטר אחי שלוש" → "כדורים בוי" | speech hard-cut, flash is silent |
| 5.45–8.05 | shot 3: red car on pavement | WHITE FLASH (same) | "אל" → "אל תיקח סיכון" → "אחי" → "אחי אנחנו" → "100" → "100 אלף" → "לא" → "לא יוצא מפה" → "בלי" → "בלי ארנק" | speech only |
| 7.85–8.05 | channel logo (clapperboard icon) pops in bottom-right, grows | — | last caption still up | — |
| 8.05–8.45 | two-colour CURVED WIPE right→left: yellow band leading, purple fill behind (thin black edge lines); logo rides the wipe to centre | wipe | captions covered | small air/whoosh |
| 8.45–10.55 | channel intro "תקליפו!" (purple bg, logo bounce, tagline) ≈ 2.1 s | — | — | bass-heavy jingle, hits at ~8.8 / 9.0 |
| 10.55–10.85 | reverse wipe (purple then yellow band) uncovers content | wipe | — | light whoosh |
| 10.85→ | content starts at full; sub/like bubble pops top-right at ~11.2 (≈0.35 s after the intro) | — | — | stream audio |

Observed: 3 shots, cut lengths 2.65 / 2.8 / 2.6 s (~8 s cold open). No zoom punches, shakes, whip/glitch, black frames,
speed ramps, freeze frames or slow-mo in the cold open — only the white flash on cuts. No riser/drone/music under the
cold open; the "build" is pure fast dialogue + word-pop captions; the only music is the intro jingle.
(Audio checked with band-energy analysis: low/high band follow speech only until 8.8 s.)

## Captions (measured at 1080p)
- Font: heavy blocky sans; closest on box = **Heebo Black** (checked vs Rubik Black, Secular One, Assistant XB, Suez One).
- Glyph height ≈ 81 px = **7.5 % of H** → Heebo size 0.123·H, x-squeezed to 0.93 (ref glyphs narrower than Heebo).
- ONE line, **1–3 words** per phrase (max line ≈ 48 % of W); new phrase after punctuation.
- Layers: black outline ≈ 8 px (**0.0075·H**); hard offset copy shifted (+0.005·H, +0.0065·H) drawn over the outline,
  under the fill → black shows top/left, colour shows bottom/right. No soft shadow, no box.
- Colours: normal word = **white fill + yellow (255,214,0) offset**; highlighted keyword = **yellow fill + black offset**.
- Position: line centre at **≈ 0.795·H** (ours 0.80 kept), centred horizontally.
- Animation: words appear one by one **in place** on the speech (phrase layout fixed). New phrase pops 1.28×→1.0 in
  ~0.2 s with alpha 0.35→1 over 2 frames; each added word re-pops the line ~1.08×→1.0 (~0.13 s); old phrase fades out
  over ~2 frames as the next appears.

## Ours before (calls_shiber_biggie_v2_enhanced, t≈4): full sentence, 2 lines, Heebo Black 0.15·H + 0.018·H stroke + soft
shadow → glyphs ~25 % bigger, ~4× more text on screen. See ref_5zTS_cmp_old.jpg.

## Files
ref_5zTS_overview.jpg (0–45 s @2fps), ref_5zTS_capstrip.jpg (caption region 0–12 s @4fps), ref_5zTS_anim_pop.jpg /
ref_5zTS_anim_phrase.jpg (30 fps pop + phrase change), ref_5zTS_crop_*.jpg, ref_5zTS_zoom_layers.png (layer order),
ref_5zTS_transitions.jpg (flash cuts, logo+wipe in, wipe out @30fps), ref_5zTS_cmp_old.jpg.

## Mapping to our builder (Nov 13b, peak_open_lowmem.py cap_style "ref5")
3 montage shots ~2.6–2.9 s → white flash cuts (silent) → our logo pops bottom-right 0.6 s before the end, rides a
green/dark curved wipe (0.45 s, soft whoosh) and lands at the green sting's first-frame logo size → green brand sting
(branding.make_intro, 2.6 s, unchanged) → reverse wipe uncovers content (0.35 s, soft whoosh) → content; v2 sub element
at body t=sub_at (4 s per Maor; the ref puts its sub bubble ~0.35 s after the intro). No premise card.

# Thumbnail style bible, prompt library, CPU scoring and learning loop for ODED HIGHLIGHTS (Taklipu-level, Nov 2026)

Method note. WebFetch could reach only github.com (and only after the session granted it). support.google.com, vidiq.com, eden.so, searchenginejournal.com, docs.opencv.org and others failed DNS. Almost every "Cited Finding" below is therefore read from WebSearch result summaries of the primary or third-party page, not from the page itself. Each such item is tagged (search summary). GitHub items marked (fetched) were read directly. Items marked (TESTED) were run in this session on tiny/synthetic data (Python 3.13, OpenCV 5.0.0, Pillow 12.3 with raqm 0.10.5, numpy, scikit-image; NO torch, open_clip, insightface or tesseract installed, so CLIP/ArcFace/OCR code is untested). Taklipu's thumbnails could not be measured: the screenshots were not available to this researcher, and a Hebrew web search for the channel returned nothing. Everything about Taklipu comes from the owner's description in the task and the repo file docs/THUMBNAIL_STYLE_BIBLE.md. Evidence (Cited Findings) is kept separate from proposals (Inferences).

Existing repo assets this builds on: docs/THUMBNAIL_STYLE_BIBLE.md, docs/THUMBNAIL_BRIEF.md, scripts/thumb_maker.py, scripts/thumbs/common.py (Heebo + raqm helpers), scripts/models/face_detection_yunet_2023mar.onnx, research_notes/.../thumbnails_free_ai.md (generation stack, licences, policy; not repeated in full here).

---

## 1. What drives CTR: evidence, genre design systems, dimensions and safe zones, plus the style bible

### Takeaway
Public CTR evidence is thin and mostly correlational: the best dataset (vidIQ, 500 breakout videos) shows faces and high contrast are common in winners and that overlay text is short, but not that they cause higher CTR, and vendor claims such as "+25-40% for emotion" are unsourced. The genre-specific rules (huge expressive face, role/costume plus one readable prop, 2-3 word heavy headline, no collage, bottom-right clear) are therefore design conventions to be tested on the channel's own data, not proven laws.

### Cited Findings
- vidIQ Research (July 2026): 500 breakout long-form videos (views far above their own channel average, from vidIQ Outliers data), thumbnails visually coded for face, colour contrast, overlay word count, expression. Human face in 69% of all 500, 75% of the top 100, 80% of the top 50 by breakout score. High contrast about 56% regardless of breakout size. Face OR high contrast in 89% (92% of top 50). Most have 3 words or fewer of overlay text (blog version says the median among thumbnails with text is 5 words). Only about 5% had an exaggerated face. vidIQ itself says thumbnail is one of several factors (topic, title, channel, timing). Descriptive, not causal. — [vidIQ study](https://vidiq.com/research/youtube-thumbnail-study/) (search summary), [vidIQ design tips](https://vidiq.com/blog/post/youtube-thumbnail-design-tips/) (search summary)
- Eden analysed 507,478 videos: 84.2% of breakout thumbnails contain a face, but so do 82.2% of underperformers (faces do not discriminate), and average overlay text was about 7 words. This conflicts with the "3 words" folklore and with vidIQ's reading. — [Eden](https://eden.so/blog/what-makes-a-good-youtube-thumbnail/) (search summary, via the vidIQ search; unverified single source)
- SEJ coverage of a 300,000+ viral-video study (2025): faces vs no faces similar on average; effect depends on niche; multiple faces did better than a single face. — [SEJ](https://www.searchenginejournal.com/do-faces-help-youtube-thumbnails-heres-what-the-data-says/563944/) (search summary, quoted in repo note thumbnails_free_ai.md)
- Study of 1,043 channels with 100K+ subs: shocked expression on about a quarter of Gaming faces vs 3% of Fitness; gaming covers use faces less often (47%). Prevalence, not performance. — [NetInfluencer](https://www.netinfluencer.com/youtube-thumbnail-study-of-100k-channels-finds-shocked-faces-on-just-1-in-10-covers/) (search summary, quoted in repo note)
- A Creative Bloq piece reports a MrBeast experiment suggesting less exaggerated "shocked" faces got more views; original data not found. — [Creative Bloq](https://creativebloq.com/news/youtube-thumbnails) (search summary, via repo note; anecdotal)
- Vendor claims (unsourced methodology, treat as directional only): face vs no face 6.8% vs 4.1% CTR; shocked vs neutral 8.3% vs 5.1%; "+33% from faces" in a 3,200 song-thumbnail review; text cut 7 to 4 words "+34%"; "<4 words = +30% CTR (1of10)". Face-fill claims contradict each other: 20-35% of frame in one Lovart page, 40-60% in another. — [mer.vin](https://mer.vin/2026/09/youtube-thumbnail-ctr-for-song-videos-what-3200-thumbnails-teach-us/), [thumbnailcreator.com](https://www.thumbnailcreator.com/blog/case-study-high-ctr-thumbnails-balanced-design), [Lovart](https://www.lovart.ai/de/blog/youtube-thumbnail-design-science-2027) (all search summaries)
- Paddy Galloway (consultant to MrBeast, Jesser, Ryan Trahan): says thumbnail success is "80, maybe 90% the psychology of the click and 10-20% the design"; keep thumbnails simple, 4-5 impactful words at most; packaging (title+thumbnail) is the leverage. A "three-element rule" attributed to him could not be confirmed from a primary source. — [Colin and Samir summary](https://www.colinandsamir.com/resources/the-new-rules-of-youtube-from-paddy-galloway), [Creator Science](https://podcast.creatorscience.com/paddy-galloway/), [contentcreators.com](https://contentcreators.com/blog/youtube-thumbnail-best-practices) (all search summaries, secondary)
- Specs: 1280x720, 16:9, under 2 MB (JPG/PNG/GIF/BMP/WebP listed by various guides), minimum width 640. Duration badge sits bottom-right: keep faces and text out. Safe-zone numbers disagree between guides (central 80% about 1024x576; central 70%; 1100x620 desktop vs 960x540 mobile). — [klap.app](https://klap.app/blog/thumbnail-size-for-youtube-videos), [postfa.st](https://postfa.st/sizes/youtube/thumbnail), [quso.ai](https://quso.ai/blog/youtube-thumbnail-size) (search summaries; third-party, not YouTube Help)
- Test & compare: up to 3 thumbnails per video; winner picked by watch-time share (not CTR); labels "Winner" (statistically significant) vs "Preferred" (likely better) and a "performed the same" outcome; typically runs about 2 weeks; YouTube states CTR-only tools may pick a different winner than watch-time share. — [YouTube Help 13861714](https://support.google.com/youtube/answer/13861714) (search summary), [vidIQ](https://vidiq.com/blog/post/youtube-launches-new-thumbnail-testing-tool) (search summary)
- Genre detail from the owner's description (primary evidence for THIS task, not independently verified): Taklipu = one photorealistic AI scene per story, huge extreme-expression face, costume/role, prop, guests in scene, one saturated colour theme, 2-3 word Hebrew headline (white + yellow, black stroke, red/yellow ribbon, slight rotation, at top), series number badge, no collage. — repo file docs/THUMBNAIL_STYLE_BIBLE.md

### Inferences
**A. Style bible (proposal; every number is a starting value to be re-calibrated by running the scorer on the ~40 reference screenshots and taking the p20-p80 range of each feature).**

| # | Rule | Measurable property (1280x720) | Starting target | Evidence level |
|---|------|------|------|------|
| 1 | One hero face, one side | YuNet largest face bbox height / frame height | 0.30-0.55 (bbox of face only; head incl. hair about +25%); hero centre x within 0.15-0.40 or 0.60-0.85 | owner observation; faces common in winners (vidIQ) |
| 2 | Extreme topic-matching expression | manual tag from prompt (shock/joy/rage); eyes visible, face sharp | face Laplacian variance (face crop resized to 192 px) >= 100 | owner observation; Creative Bloq anecdote argues not over-exaggerating, so test "extreme" vs "strong" |
| 3 | Role/costume + ONE prop | prop occupies 8-25% of area, high local contrast, survives 168x94 | 1 hero prop; <= 3 distinct foreground objects | owner observation |
| 4 | Guests in same scene | 1-3 extra faces, each 0.10-0.25 of frame height, own reaction | n_faces 2-4 | SEJ: multiple faces did better (secondary) |
| 5 | Single colour story, saturated | HSV mean saturation 0.40-0.65; top-2 of 12 hue bins hold >= 55% of saturated pixels | as left | owner observation; vidIQ contrast 56% |
| 6 | Strong tonal contrast | luminance RMS 0.20-0.34; p95-p5 range >= 0.60 | as left | vidIQ (descriptive) |
| 7 | Low clutter | Canny edge density outside faces at 320x180 | 0.02-0.08 | design heuristic |
| 8 | Headline 2-3 words | word count; Eden/vidIQ show real-world text is longer, so 3 is a style choice | <= 3 (max 4) | Galloway/vidIQ (short is typical) |
| 9 | Headline at top, never on faces | headline bbox (with stroke) y0 < 0.20H; overlap with face bbox expanded 15% = 0 | as left | owner observation |
| 10 | Headline legible at 168x94 | cap-height >= 14% of H (about 100 px on 720) so >= 13 px at 94 px height; two lines total <= 40% of H | as left | design heuristic |
| 11 | Bottom-right clear | nothing important in x > 0.84W and y > 0.86H | as left (generous vs about 50x25 px real badge; exact badge size unverified) | consistent across guides |
| 12 | No collage, no logos/watermarks | one coherent light source; no text from the scene model | OCR on the raw scene finds nothing | owner observation |
| 13 | Series number badge | optional, small, top-left or on ribbon | - | owner observation |

**B. Contrast between the two house styles.** Taklipu-style = rule set above (AI scene). OdedSVR Live = real photo, serious face left, topic image right, little text. These are different brands; do not mix cues. Keep a `style_id` per thumbnail so the learning loop can compare styles.

**C. Why small-size matters (inference).** The checks that most plausibly matter at 168x94 (smallest feed/sidebar size) and 320x180 are: hero face still detectable, one dominant prop, headline words readable, high luminance contrast between hero and background. Verify visually by downscaling every candidate to 168x94 and 320x180 (TESTED code in section 4 does the detection on a 168x94 downscale).

### Gaps
- Taklipu not measured (no screenshots available to this researcher, Hebrew search returned nothing). No Israeli-channel CTR data found.
- No primary YouTube Help text read; no primary peer-reviewed CTR study found. Face-size optimum is unresolved (vendors contradict).
- MrBeast-team design system: only second-hand talk summaries (Galloway); no primary "thumbnail rules" document found. "Three-element rule" unverified.
- Exact duration-badge pixel size not found.

---

## 2. Prompt engineering for photorealistic scene thumbnails with identity references, and the 14-prompt library

### Takeaway
Google's own guidance for its image model is to "think like a photographer" (shot type, subject, action/expression, environment, lighting, mood, lens/camera) and to prefer positive phrasing; no official source on negative prompts or identity preservation was reachable. A reliable structure is: identity block -> shot/framing -> expression -> costume+prop -> scene+lighting+colour story -> composition reservations (headline band, bottom-right) -> guard clauses. Keep props textless (any text on props gets garbled; add text later in Pillow).

### Cited Findings
- Google Developers blog (Gemini 2.5 Flash Image): for realistic images mention camera angles, lens types, lighting and fine details; template "A photorealistic [shot type] of [subject], [action or expression], set in [environment]. The scene is illuminated by [lighting], creating a [mood] atmosphere. Captured with a [camera/lens], emphasizing [textures/details]"; 85mm paired with soft bokeh in the example. — [Google blog](https://developers.googleblog.com/how-to-prompt-gemini-2-5-flash-image-generation-for-the-best-results/) (search summary)
- Imagen prompt guide lists lens/camera vocabulary (35mm, 50mm, fisheye, wide angle, macro). — [Imagen prompt guide](https://ai.google.dev/gemini-api/docs/imagen-prompt-guide) (search summary)
- Third-party guidance: phrase constraints positively ("keep all existing subjects and objects intact, maintain consistent lighting") and avoid vague/contradictory terms; face-preservation phrases like "face preserved precisely" are community patterns, not official. — search summary of Gemini prompt guides (e.g. [Ainsider](https://ainsider.beehiiv.com/p/nano-banana-prompting-guide)); unverified
- Repo brief (owner's current template): "Leave the top 28% of the image fairly clean and darker for a headline. No text, no logos, no watermarks, no extra fingers." — docs/THUMBNAIL_BRIEF.md
- Free-model stack, identity licences and QA gating already researched in thumbnails_free_ai.md (FLUX.2 klein, Qwen-Image-Edit-2511, Gemini app etc.); not repeated.

### Inferences (proposals; none of these prompts has been run in this session)

**Prompt skeleton (fill the slots; keep it one paragraph per slot).**
1. IDENTITY: "Use the attached reference photos of {HERO} (images 1-3) as his exact identity: same face shape, beard, hairline, glasses/headphones; no beautification, same age."
2. SHOT: "Photorealistic cinematic YouTube thumbnail, 16:9. Close-up / chest-up, 35mm lens at eye level (or 24mm slightly low angle for power), hero's face fills about 40% of the frame height, on the {left|right} third."
3. EXPRESSION (name the muscles): jaw dropped / eyes wide with whites visible / eyebrows raised high; or teeth-gritted snarl, brows pulled down, veins.
4. COSTUME + ONE PROP: concrete, large, simple geometry, textless.
5. SCENE + LIGHT + COLOUR STORY: one dominant hue pair, rim light, volumetric haze.
6. GUESTS: "second person {GUEST} (reference image 4), smaller, behind/beside, with his own distinct reaction."
7. COMPOSITION RESERVATIONS: "top 30% is darker/uncluttered (sky, wall, bokeh) for a headline added later; bottom-right 15% plain; hero's eyes at the upper third; nothing touches the frame edges except the hero's shoulder."
8. GUARDS (positive wording first): "All signs, screens, packaging and props are blank or abstract, no readable letters or numbers, no logos, no watermarks. Hands: exactly five natural fingers each, or hands kept out of frame. Sharp focus on the eyes, realistic skin texture, no plastic look, one coherent light source, single scene (no collage, no split screen)."

**Hand/prop robustness tricks.** Hold the prop with both hands in the lower half and ask for fingers "clearly visible and relaxed" or avoid hands entirely (prop on table, strapped to chest, hanging from belt). One prop per image. Avoid text, banknote details, logos on props. Generate 4 candidates, gate by face count, ArcFace/SFace similarity and the scorer; regenerate rather than inpaint hands. For FLUX-family models that ignore negative prompts, rely only on the positive guard text (general knowledge, unverified here).

**Adding a guest.** Always pass the guest's own reference frame as a separate numbered image and name it. State relative size ("his head about half the height of the hero's"), position ("behind the hero's left shoulder, partly in shadow") and a different emotion from the hero. Check face count == requested after generation. For a guest without consent or a good reference, use a back-of-head silhouette or an invented non-identifiable extra.

**Using a famous game's look without logos.** Describe the visual grammar, not the product: palette, architecture, props, time of day, camera style. Do not name the title in the image prompt if the model reproduces logos; never request the logo, title treatment, box art or character likenesses; the headline text added by us can say the game name. Example for GTA 6: "sun-drenched neon coastal city at sunset, pink-orange gradient sky, palm trees, art-deco hotels, glossy sports car, retro-futuristic glow" (no logo, no "GTA", no "Rockstar"). Trademark/copyright risk of look-alike key art is a legal judgement; keep it to generic setting cues (see section 6).

**Prompt library** ({HERO}=Oded, refs 1-3; {GUEST}=ref 4 where used; append GUARDS and COMPOSITION RESERVATIONS from the skeleton to every prompt; abbreviated here as "[+RES][+GUARDS]". Hebrew headline suggestions are for the later Pillow step: white word + yellow word.)

1. **First-time reaction to a hyped game (GTA 6)** - headline "פעם ראשונה / ב-GTA 6!" (accent: the game). "Photorealistic chest-up thumbnail of {HERO} at the left third, 35mm eye level, jaw dropped, eyes wide with whites showing, both hands pressed to his cheeks, wearing a loud 1980s tropical shirt and gold chain. Behind him a sun-drenched neon coastal city at sunset: pink-orange gradient sky, palm trees, art-deco hotels, a glossy chrome sports car, haze glow (no logos, no title). Teal and hot-pink rim light on his face. [+RES][+GUARDS]"
2. **Heist / game story (Rob Run style)** - "שוד / הגדול!" "{HERO} as a jewel thief in a black tactical vest, balaclava pulled up on his forehead so the face is clear, grinning manically with eyes wide, close-up 28mm slightly low angle, holding a large sack overflowing with blank sparkling diamonds against his chest; ransacked jewellery store, glass display shards, gold and teal lighting, a small security guard in the background with a panicked face. [+RES][+GUARDS]"
3. **Phone call / drama** - "התקשר / והתחנן!" "{HERO} on the right third, extreme close-up 50mm, a smartphone with a plain glowing blank screen at his ear, eyes wide, brows raised, mouth in a stunned half-open 'no way' shape, a sweat drop on his temple; dark room with red and blue police-style rim lights on a rainy window behind him; a tense {GUEST} smaller in the background looking over his shoulder. [+RES][+GUARDS]"
4. **Ranking / tier list** - "דירוג / אכזרי!" "{HERO} as a strict judge in a black robe, smug raised eyebrow, tapping a golden gavel, left third, 35mm; behind him a giant glowing tier board made only of colour bars (red, orange, yellow, green) with blank square icon slots, no letters or numbers; purple stage lights and gold rim light. [+RES][+GUARDS]" (add the S/A/B letters later in post if wanted.)
5. **Trivia / quiz** - "חידון / הלחץ!" "{HERO} as a flamboyant game-show host in a sparkly blazer holding a microphone, big open-mouth smile and one raised eyebrow, right third, 35mm; behind him four glowing answer podiums with blank screens, spotlights and confetti; {GUEST} as a contestant, smaller, scratching his head in confusion; magenta and cyan stage colours. [+RES][+GUARDS]"
6. **Birthday / guest surprise** - "יום הולדת / הפתעה!" "{HERO} wearing a party hat, face lit with pure delight, mouth wide open laughing, left third, 35mm; {GUEST} beside him, equal-ish size, wearing a party hat and tearing up with joy; a big cake with lit candles (no writing on the cake) in the foreground, balloons, falling confetti, warm gold and pink bokeh lights. [+RES][+GUARDS]"
7. **Angry rant** - "הגזמתם / לגמרי!" "{HERO} extreme close-up, 24mm slightly low angle, teeth bared, brows pulled down, neck veins visible, pointing one finger straight at the camera (hand in sharp focus, five fingers), red backlight and black smoke, a broken keyboard flying in the air behind him (blank keys), red and black palette. [+RES][+GUARDS]"
8. **Money / shopping** - "קנה / הכל!" "{HERO} as a stunned shopper in a luxury boutique, eyes huge, mouth open in joy-shock, holding six bulging glossy shopping bags (no logos) in both arms, gold dust and a rain of blank green banknotes without legible details, gold and emerald lighting, right third, 35mm. [+RES][+GUARDS]"
9. **Travel** - "עוזבים / הכל!" "{HERO} as an airline pilot in a white uniform and cap, worried clenched expression, holding a blank navy passport and a blank boarding card in one hand, suitcase beside him; airport apron at golden hour, airliner behind, {GUEST} smaller with an anxious face; orange and sky-blue palette, 35mm. [+RES][+GUARDS]"
10. **AI / tech topic** - "מהפכת / ה-AI!" "{HERO} as a scientist in safety goggles and white lab coat, awestruck wide eyes, cradling a small friendly robot with glowing cyan eyes in both hands, server-room corridor behind with blue and violet neon, volumetric haze, 50mm. [+RES][+GUARDS]"
11. **Reaction to a viral video** - "לא / מאמין!" "{HERO} in a gaming chair with headset around his neck, hands on his head, jaw dropped, lit by the cyan-magenta glow of a huge monitor that shows only an abstract blurred chaotic colourful scene (no real person, no text), a bucket of popcorn spilling, 35mm; right third. [+RES][+GUARDS]" (Never show a real viral person's likeness.)
12. **Challenge / wager** - "מהמר / על הכל!" "{HERO} on the left and {GUEST} on the right facing each other over a table with a stack of blank cash and a golden championship belt between them, both with fierce determined smirks, red light on one side and blue on the other within one coherent arena scene (not a collage), 28mm low angle, smoke. [+RES][+GUARDS]"
13. **Lawsuit / drama (from the references)** - "מכתב / תביעה!" "{HERO} in a dark suit and tie as a lawyer, horrified wide-eyed face, holding a large cream envelope with a red wax seal (envelope blank, text added later) up at chest height, courtroom wood panelling, {GUEST} and a second guest behind him with shocked faces, warm amber and deep blue lighting. [+RES][+GUARDS]"
14. **Strategy game king** - "המלך / החדש!" "{HERO} as a king in a velvet cape and gold crown, smug confident half-smile, chin raised, gripping a sceptre, seated at a stone table covered in miniature wooden armies, castle hall with torches behind, gold and crimson, 35mm slightly low angle. [+RES][+GUARDS]"

**Per-prompt QA.** Generate 4; gate with section 4; keep the best two; one variant with a calmer expression for A/B (Creative Bloq anecdote says over-exaggeration may lose).

### Gaps
- No official Google guidance on identity preservation or negative prompts reached; all identity-phrase advice is community pattern.
- None of the 14 prompts was executed (no image model access in this session); expect to iterate per model (Gemini vs FLUX vs Qwen).
- No validated automatic "extra finger" detector (repo note also lists this as unresolved).

---

## 3. Headline typography and Pillow RTL implementation

### Takeaway
Pillow with raqm renders Hebrew RTL correctly (TESTED here, Pillow 12.3, raqm 0.10.5): pass direction='rtl', language='he', and set Heebo's variable weight axis to 900 for the Black look. A heavy black stroke of about 11% of font size, white word + yellow word, a red ribbon polygon and a 3-5 degree rotation reproduce the genre look.

### Cited Findings
- Pillow: direction/features/language parameters require libraqm; check with features.check('raqm'); direction 'rtl'; language BCP-47 ('he'); stroke_width supported in text drawing and bbox methods. — [Pillow ImageFont docs](https://pillow.readthedocs.io/en/latest/reference/ImageFont.html) (search summary via repo note)
- Heebo (Hebrew drawn by Oded Ezer on Roboto Latin) is a text family; Rubik has the broadest weight range (Black) and Hebrew+Latin; Secular One is a single-weight display face; Suez One is a single heavy display face. Source comparison is inferred; no source compares them for thumbnails. — [Awesome Hebrew Fonts](https://github.com/danielrosehill/Awesome-Hebrew-Fonts), [googlefonts/rubik](https://github.com/googlefonts/rubik), [Secular One](https://www.figma.com/fonts/secular-one/) (search summaries)
- Heebo ships as a variable TTF under OFL. — [google/fonts heebo](https://github.com/google/fonts/tree/main/ofl/heebo) (via repo note)
- (TESTED, local) The installed font /usr/share/fonts/truetype/sand-box/google/Heebo/Heebo-VariableFont_wght.ttf accepts set_variation_by_axes([900]); a Hebrew string with "!" rendered RTL with the punctuation on the correct (left) end; features.check('raqm') is True. Rubik/Secular One/Suez One are NOT installed locally (fc-list found only Heebo).

### Inferences (design proposals; numbers from the genre description and the tested render)
**Rules**
- Words: 2-3 total, two lines max (line 1 white = context/person, line 2 yellow = the hook word, 1-2 words). Hebrew words average short; check line width after rendering, not by character count.
- Font: Heebo Black (wght 900) is the safe default (already in repo). Candidates for variety: Rubik (wght 900), Suez One and Secular One (single heavy weights; Suez is the most poster-like). Pick ONE headline font for the channel for brand consistency.
- Size: line 1 cap-height about 11-14% of H; line 2 larger (15-22% of H, e.g. 150-190 px at 720p). Total headline block <= 40% of H, <= 55% of W.
- Stroke: black stroke width 10-12% of font size for line 1 (e.g. 12-17 px at 150 px), 12-14% for the yellow line; stroke outermost, drawn with the fill on top (Pillow draws stroke+fill in one call correctly). Add a blurred black drop shadow offset about 5% of size, blur about 3% of size (TESTED look).
- Colours: white #FFFFFF and yellow #FFDE00 (gradient to orange #FF960A toward the bottom is used in the repo script). Accent colour rule: the accent word is the high-emotion or key-noun word; never more than one accent colour per headline; avoid putting the accent colour equal to the scene's dominant hue.
- Ribbon: red #D71919 polygon with 6 px black outline behind the yellow line, slightly non-rectangular (corner offsets 10-20 px), padding about 25 px.
- Rotation: 3-5 degrees (counter-clockwise looks upward-optimistic; the repo uses 4-5) about the block centre; recompute the rotated bounding box for the face-overlap test.
- Placement: top band (y0 < 0.20H), right-aligned or on the side opposite the hero's face; never over a face bbox expanded 15%; never in x > 0.84W and y > 0.86H; keep 30 px margin from edges.
- Badge: '#2' number badge in a circle top-left, size about 8% of H.

**Tested Pillow snippet (RTL, Black weight, stroke, shadow, ribbon, rotate).** Output looked correct visually.
```python
from PIL import Image, ImageDraw, ImageFont, ImageFilter
HEEBO='/usr/share/fonts/truetype/sand-box/google/Heebo/Heebo-VariableFont_wght.ttf'
def font(size,wght=900):
    f=ImageFont.truetype(HEEBO,size,layout_engine=ImageFont.Layout.RAQM)
    f.set_variation_by_axes([wght]); return f
def word_layer(txt,size,fill,stroke_ratio=0.11,shadow=0.05):
    f=font(size); sw=int(size*stroke_ratio)
    d=ImageDraw.Draw(Image.new('L',(1,1)))
    x0,y0,x1,y1=d.textbbox((0,0),txt,font=f,stroke_width=sw,direction='rtl',language='he')
    pad=int(size*0.25); w,h=x1-x0+2*pad,y1-y0+2*pad
    L=Image.new('RGBA',(w,h),(0,0,0,0)); sh=Image.new('RGBA',(w,h),(0,0,0,0))
    ImageDraw.Draw(sh).text((pad-x0+size*shadow,pad-y0+size*shadow*1.3),txt,font=f,fill=(0,0,0,210),
        stroke_width=sw,stroke_fill=(0,0,0,210),direction='rtl',language='he')
    L=Image.alpha_composite(L,sh.filter(ImageFilter.GaussianBlur(size*0.03)))
    ImageDraw.Draw(L).text((pad-x0,pad-y0),txt,font=f,fill=fill,stroke_width=sw,
        stroke_fill=(0,0,0,255),direction='rtl',language='he')
    return L            # compose white line 1 + ribbon polygon + yellow line 2, G.rotate(3,expand=True), paste top-right
```
- Fail loudly if `features.check('raqm')` is False (silent fallback gives reversed Hebrew). Use a static Black TTF if variable-axis behaviour differs on another Pillow build.
- Overlap check: take the rotated layer's alpha bbox (`G.getbbox()` after rotate) plus its paste offset and feed it to `headline_checks()` in section 4. Place candidates in order (top-right, top-left, top-centre), shrink font 4% steps to a floor (line 2 >= 12% of H), else reject the scene.
- Always render the final at 1280x720, JPEG q 88-92, then check < 2 MB; preview 168x94 and 320x180.

### Gaps
- No primary typography study for Hebrew thumbnails; stroke ratio and sizes are derived from the repo script and the genre description, not measured on Taklipu.
- Rubik, Suez One, Secular One fonts not installed locally, so not rendered here; their metrics and Pillow variable-axis names are unverified.
- Hebrew mixed-script edge cases (Latin game names like "GTA 6", digits, quotes) were not tested; test "ב-GTA 6!" before shipping (bidi order of the Latin chunk with raqm).

---

## 4. Automatic thumbnail scoring and selection on CPU

### Takeaway
With only a few dozen references, use a transparent heuristic scorer made of hard gates (no face, face under badge, headline over face, identity too low, hero lost at 168x94) plus a weighted soft score on measurable features, and treat CLIP reference-similarity as ONE low-weight feature, not a learned CTR model. The face/contrast/clutter/headline-overlap parts below ran on CPU in this session on a stock image (YuNet about 30 ms per 1280x720 frame); CLIP, identity embedding and OCR parts are unverified here.

### Cited Findings
- YuNet via cv2.FaceDetectorYN: output N x 15 array [x,y,w,h, 5 landmarks, score]; detects faces about 10x10 to 300x300 px; MIT licence; files face_detection_yunet_2026may.onnx (default, dynamic input, for OpenCV 5.x), 2023mar (fixed input), int8 variants; WIDER Face AP 0.8844/0.8656/0.7503 (easy/medium/hard) in the zoo evaluation. — [opencv_zoo YuNet](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet) (fetched)
- SFace (OpenCV recognition model): face_recognition_sface_2021dec.onnx (+int8 variants), Apache 2.0, accuracy 0.9940 on the zoo's evaluation (dataset not named), expects the 5-landmark alignment that YuNet provides; the page gives no match threshold. — [opencv_zoo SFace](https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface) (fetched)
- InsightFace: code MIT, but pretrained models are "non-commercial research only"; 2025-11-24 update says open-sourced recognition packs such as buffalo_l need contact for licensing (recognition-oss-pack@insightface.ai); ArcFace dimension not stated on the page. — [insightface README](https://github.com/deepinsight/insightface) (fetched)
- open_clip: `open_clip.create_model_and_transforms('ViT-B-32', pretrained='laion2b_s34b_b79k')`; OpenAI weights use 'ViT-B-32-quickgelu' + 'openai'; param/FLOP table in docs/model_profile.csv (not read). — [open_clip](https://github.com/mlfoundations/open_clip) (fetched)
- Schuhmann improved-aesthetic-predictor: small MLP on CLIP embeddings, Apache-2.0; weights named l14 (ViT-L/14), no ViT-B/32 variant seen; trained on AVA/SAC/logos style data, so a general-aesthetic score, not thumbnail CTR. — [improved-aesthetic-predictor](https://github.com/christophschuhmann/improved-aesthetic-predictor) (fetched)
- TubeCLIP (CLIP-L fine-tune predicting thumbnail+title performance class) and z03 are CC BY-NC (restricted for commercial use); one project notes training data cannot be redistributed under YouTube API terms. — [TubeCLIP](https://huggingface.co/Krudev/TubeCLIP), [z03](https://huggingface.co/Krudev/z03) (search summaries)
- Tesseract/EasyOCR on Hebrew: reports of poor Tesseract Hebrew accuracy and bad nikud data; no head-to-head Hebrew benchmark found; stylized fonts are hard for both. — [Tesseract issue 4119](https://github.com/tesseract-ocr/tesseract/issues/4119), [Hebrew OCR write-ups](https://prog.world/my-experience-and-solutions) (search summaries)
- InsightFace docs advise choosing the cosine threshold from your own genuine/impostor pairs; ArcFace thresholds vary by model (0.5 in one 2025 paper, about 0.69 DeepFace). — [InsightFace guide](https://insightface.ai/guides/choose-face-recognition-model-and-evaluate), [arXiv 2507.15961](https://arxiv.org/pdf/2507.15961) (via repo note)
- (TESTED) OpenCV 5.0.0 headless: `cv2.FaceDetectorYN.create(<2023mar onnx>,'',(1280,720),0.6)` works with the default DNN engine. It crashed with "stoull" when I wrongly exported OPENCV_FORCE_DNN_ENGINE to an empty string, and with engine=1; engines 2/3/4 worked. On a stock photo (skimage astronaut) pasted on a purple canvas it found 1 face (score 0.94, bbox 129x164 px) in 33 ms; the detection on a 168x94 downscale still worked.

### Inferences (proposal; thresholds are starting points, none calibrated on references)

**Design principle.** A learned CTR model needs hundreds to thousands of labelled thumbnails; with about 40 references (all "good", no negatives) and 1-2K-sub channel data, learning is not feasible. So: (1) hard gates for defects, (2) transparent weighted soft score, (3) distribution-based calibration (set each target range from the references' p20-p80), (4) CLIP kNN style-similarity to the references as one feature, (5) later, shrinkage-regularised updates of the weights from own outcomes (section 5). Choosing between candidates of the SAME video needs only the relative ranking, which is easier than predicting absolute CTR.

**Features and thresholds (1280x720 working size)**

| Feature | How | Soft target (score 1.0 plateau) | Hard gate |
|---|---|---|---|
| Hero face size | YuNet, largest bbox h/H | 0.30-0.55 (ramp 0.10->0.30, 0.55->0.80) | n_faces = 0 reject; > 4 reject |
| Hero survives 168x94 | rerun YuNet on 168x94, area > 0.5 x expected | true | false = reject |
| Face sharpness | var(Laplacian) of hero crop resized to 192x192 | >= 120 (ramp from 20) | < 20 reject-ish. NOTE the stock test face upscaled gave 49, so recalibrate with the real references |
| Saturation | mean HSV S/255 | 0.40-0.65 | - |
| Contrast | 0.5 x RMS luminance (0.20-0.34) + 0.5 x p95-p5 range (>= 0.60) | as left | - |
| Colour story | share of saturated pixels in top-2 of 12 hue bins | >= 0.55 | - |
| Clutter | Canny (80,160) edge density at 320x180 outside face boxes | 0.02-0.08 | - |
| Guest | 2nd face >= 0.10 H | 1.0 if guests requested and present | face count != requested |
| Headline overlap | headline bbox (stroke incl.) vs face bbox expanded 15% | 0 | > 2% of a face area = reject |
| Headline size/pos | words <= 3, height 0.14-0.30 H, y0 < 0.20 H | - | in badge corner = reject |
| Badge corner | any face or headline in x>0.84W, y>0.86H | clear | else reject |
| Identity | cosine of ArcFace/SFace embedding (hero crop) vs mean of reference embeddings | >= tau | < tau reject; tau from own genuine/impostor pairs (do NOT reuse 0.5 blindly; SFace threshold must be calibrated too) |
| Style similarity | open_clip ViT-B/32 image embedding cosine to the reference-set centroid (and mean of top-3 nearest) | calibrate: take leave-one-out cosine of each reference to the others, plateau from its p25 to 1.0 | - |
| Stray text | OCR on the raw scene (before headline) finds >= 2 characters | none | reject (scene model wrote text) |

**Formula.** `score = 100 x sum(w_k x s_k) / sum(w_k)` over the available soft features, applied only if no gate fires. Initial weights: face_size .22, headline .14, style .18 (when available), contrast .10, sharp .08, sat .08, clutter .08, colour_story .06, guest .06. Selection: among gate-passing candidates take the highest score; if the top two are within 3 points choose the one with higher face-size and identity margin; if none pass, regenerate (max 3-4 rounds) and finally fall back to the plain-photo style.
Rationale for ordering the weights: the face is the only feature with replicated descriptive support (vidIQ), and the style bible puts face size and headline placement first; all other weights are judgment.

**OCR.** Do not use OCR to read the headline: you rendered it, so you know the string; verify legibility geometrically (cap-height, contrast of fill vs stroke vs surrounding ring at 168x94, e.g. mean luminance difference >= 0.35). Use OCR only (a) to detect unwanted garbled text in the raw scene (any engine; false positives are fine because you reject), (b) optionally on the 168x94 and 320x180 downscales to check the headline is still read (Tesseract `heb` is unreliable on stylized heavy fonts, so treat a failure as a warning, not a gate). Heavy lifting not needed on CPU: both are a few seconds per image.

**CLIP/ViT-B/32 on CPU (unverified here).** Roughly 0.1-0.5 s per image on a few cores with batch size 1 and `torch.set_num_threads(2)` (typical figure from general knowledge, not measured); weights about 600 MB RAM in fp32. The session was OOM-killed before, so: one process, batch 1, `torch.inference_mode()`, delete the model after embedding, cache embeddings of the references to .npy, and compute reference stats once. Optional: export to ONNX and use onnxruntime (already installed locally).

**Learned vs heuristic with a few dozen references.** Heuristic + reference-percentile calibration is the right primary scorer. A learned head (logistic regression on CLIP embeddings to separate "Taklipu style" from "own previous thumbnails") is feasible only if you also have 30+ negatives (own earlier thumbnails); use leave-one-out and strong L2. Do not use generic LAION aesthetic (ViT-L/14, not thumbnail-specific) or non-commercial CTR predictors (TubeCLIP/z03) as the selector.

**Calibration procedure.** (1) Run feature extraction on the ~40 reference screenshots after resizing to 1280x720; store distributions. (2) Set each plateau to [p20, p80] of the references; ramps out to [p1, p99] widened by 20%. (3) Run the same on 30 own past thumbnails and on 30 deliberately bad variants (headline over face, tiny face, cluttered); check the score separates them (AUC >= 0.85 expected; if not, fix features, not weights). (4) Identity: compute ArcFace/SFace genuine pairs (Oded frames) and impostor pairs (guests, other streamers); set tau at about 1% false accept. (5) Human check on 20 candidates: Spearman correlation between scorer rank and the owner's preference; target >= 0.5 before trusting auto-pick.

**Tested code (condensed from the file I ran; OpenCV + numpy only).**
```python
import cv2, numpy as np
W,H=1280,720; BADGE=(0.84,0.86,1.0,1.0)
def trap(x,a,b,c,d):
    if x<=a or x>=d: return 0.0
    return (x-a)/(b-a) if x<b else 1.0 if x<=c else (d-x)/(d-c)
def faces(img,det,thr=0.6):
    det.setInputSize((img.shape[1],img.shape[0])); det.setScoreThreshold(thr)
    _,f=det.detect(img)
    return [] if f is None else [dict(x=r[0],y=r[1],w=r[2],h=r[3],s=r[14]) for r in f]
def image_stats(img,fcs):
    hsv=cv2.cvtColor(img,cv2.COLOR_BGR2HSV).astype(np.float32); gray=cv2.cvtColor(img,cv2.COLOR_BGR2GRAY).astype(np.float32)/255
    small=cv2.resize(img,(320,180),interpolation=cv2.INTER_AREA); ed=cv2.Canny(cv2.cvtColor(small,cv2.COLOR_BGR2GRAY),80,160)>0
    m=np.ones((180,320),bool)
    for f in fcs: m[int(f['y']/4):int((f['y']+f['h'])/4),int(f['x']/4):int((f['x']+f['w'])/4)]=False
    hue=hsv[...,0][hsv[...,1]>80]*2; hist=np.histogram(hue,bins=12,range=(0,360))[0].astype(float); hist/=max(hist.sum(),1)
    return dict(sat=hsv[...,1].mean()/255, rms=gray.std(), dyn=np.percentile(gray,95)-np.percentile(gray,5),
                edge_bg=ed[m].mean(), hue_top2=np.sort(hist)[-2:].sum())
def face_feats(img,fcs,det):
    hero=max(fcs,key=lambda f:f['w']*f['h']); x,y,w,h=map(int,(hero['x'],hero['y'],hero['w'],hero['h']))
    crop=cv2.resize(cv2.cvtColor(img[max(y,0):y+h,max(x,0):x+w],cv2.COLOR_BGR2GRAY),(192,192))
    s=faces(cv2.resize(img,(168,94),interpolation=cv2.INTER_AREA),det,0.5)
    return dict(n=len(fcs),hero_h=hero['h']/H,sharp=cv2.Laplacian(crop,cv2.CV_64F).var(),
        ok168=any(f['w']*f['h']>0.5*hero['w']*hero['h']/7.6**2 for f in s),
        others=sorted([f['h']/H for f in fcs if f is not hero],reverse=True),
        in_badge=any((f['x']+f['w'])/W>BADGE[0] and (f['y']+f['h'])/H>BADGE[1] for f in fcs))
def headline_checks(box,fcs,n_words,margin=0.15):   # box=(x0,y0,x1,y1) px incl. stroke, after rotation
    x0,y0,x1,y1=box; ov=0.0
    for f in fcs:
        fx0,fy0=f['x']-margin*f['w'],f['y']-margin*f['h']; fx1,fy1=f['x']+f['w']*(1+margin),f['y']+f['h']*(1+margin)
        iw=max(0,min(x1,fx1)-max(x0,fx0)); ih=max(0,min(y1,fy1)-max(y0,fy0)); ov=max(ov,iw*ih/max(f['w']*f['h'],1))
    return dict(face_overlap=ov,top=y0/H,height=(y1-y0)/H,words=n_words,in_badge=(x1/W>BADGE[0] and y1/H>BADGE[1]))
```
Full scorer (gates + weights) = the `score()` function described by the table above; test result on the stock-face canvas: no gates with headline at the right, score 82 (with a fake style_sim 0.8 and id_sim 0.6); moving the headline over the face fired `headline_covers_face`; random-noise image fired `no_face`. This only proves the code runs and the gates trigger; it says nothing about real-thumbnail calibration.

**Identity check choice (licence).** InsightFace buffalo_l is non-commercial unless licensed (fetched README), which matters if the channel monetises. License-clean option: OpenCV YuNet + SFace (both Apache 2.0/MIT per zoo pages). SFace file could not be downloaded here (GitHub LFS path returned 403 under this session's repo policy), so SFace was NOT tested.

### Gaps
- Real thumbnails and screenshots were unavailable, so every threshold is unvalidated; sharpness especially depends on upscaling.
- CLIP, InsightFace/SFace and OCR code not run (packages not installed; avoided heavy jobs). CPU latency/memory numbers for ViT-B/32 are unmeasured.
- No validated generated-hand artefact detector; no benchmark of Hebrew OCR on stylized heavy fonts.
- SFace cosine match threshold not found in the page read (commonly cited value 0.363 is from memory, unverified).

---

## 5. Learning loop from the channel's own results (Test & compare, Reporting API)

### Takeaway
Per-video thumbnail CTR is available through the YouTube Reporting API reach reports (thumbnail impressions and impressions CTR), but a small channel's CTR differences are mostly noise: detecting a 5%->6% lift needs about 8,000 impressions per arm. Therefore learn slowly: log every thumbnail's features, compare to the channel baseline with shrinkage, use Test & compare (watch-time share) for the head-to-head decisions, and adjust only a few weights/templates at a time.

### Cited Findings
- Reporting API: reach reports channel_reach_basic_a1 and channel_reach_combined_a1 (channel) and content_owner_reach_basic_a1 exist; metrics video_thumbnail_impressions and video_thumbnail_impressions_ctr, added per the revision history on 2025-09-22; the combined report has date, channel, video, traffic source and device dimensions. Impression is counted when the thumbnail is shown more than 1 s with at least 50% visible. CTR = clicks / impressions. A 2026-08-27 revision-history entry mentions a "Thumbnail Impression" definition (displayed without interaction or autoplay). — [Reporting API revision history](https://developers.google.com/youtube/reporting/revision_history), [channel reports](https://developers.google.com/youtube/reporting/v1/reports/channel_reports) (search summaries)
- Analytics API metrics reference lists videoThumbnailImpressions and videoThumbnailImpressionsClickRate under reach metrics; older Stack Overflow/issue-tracker threads said impressions were not retrievable (predates the docs; may be outdated). One third-party tool claims impression data is kept only about 500 days (unverified). — [Analytics API metrics](https://developers.google.com/youtube/analytics/metrics), [StackOverflow thread](https://stackoverflow.com/questions/64786908) (search summaries)
- Test & compare: watch-time-share winner, up to 3 thumbnails, desktop-only, long-form/live archives/podcasts, advanced features required; YPP requirement disputed across 2026 blogs; no API for Test & compare found (repo note). — [YouTube Help 13861714](https://support.google.com/youtube/answer/13861714), [vidanalyze](https://vidanalyze.com/news/youtube-ab-testing-for-titles-thumbnails-2026-guide) (search summaries)
- thumbnails.set: JPEG/PNG up to 2 MB, about 50 quota units per call, 10,000 units/day default. — [thumbnails.set](https://developers.google.com/youtube/data/reference/rest/v3/thumbnails/set), [quota table](https://developers.google.com/youtube/v3/determine_quota_cost) (via repo note)
- Statistics (TESTED, computed here with scipy; two-sided alpha .05, power .80): impressions per arm needed to detect CTR 4%->5%: 6,745; 5%->6%: 8,158; 5%->6.5%: 3,780; 6%->8%: 2,554; 8%->10%: 3,213; 8%->12%: 882. Standard error of one video's CTR: 5% at 1,000 impressions = 0.69 pp; at 3,000 = 0.40 pp; 6% at 10,000 = 0.24 pp.

### Inferences (proposal)
**Data to log per video.** video_id, publish time, thumbnail version/time swapped, style_id (Taklipu-scene vs real-photo), template/category, features from section 4 (the vector), scorer total, generation model, headline text, reached impressions and CTR by traffic source (browse, suggested, search) for first 48 h and 7 days, average view duration/percentage, Test & compare outcome (Winner/Preferred/same, watch-time shares).

**Metrics.** Outcome = log-odds of CTR relative to the channel's trailing median for the same traffic source and video age window (controls for audience drift), shrunk with a Beta prior: `ctr_hat=(clicks+a)/(impr+a+b)` with prior mean = channel baseline and prior strength about 500-1000 impressions. Treat retention/watch-time as a co-outcome so clickbait that loses watch time is penalised (YouTube's own test picks by watch-time share).

**Model.** Keep it low-dimensional: Bayesian ridge on at most 4-6 composite features (face_size score, headline score, colour_story, style similarity, guest present, expression-intensity tag), prior mean = current weights (from the style bible), prior variance tight; update weights as posterior means. With 30 videos only the 1-2 largest effects can move. For template choice use Thompson sampling over the 14 categories/styles (Beta posteriors on above-baseline CTR) so exploration is automatic. Pairwise data from Test & compare (A beat B) feeds a Bradley-Terry update of feature weights, which is more robust than comparing across videos.

**Process.** (1) Per video generate 4, auto-pick top 2, ship one and queue the other as the Test & compare challenger when the channel is eligible; change ONE thing between variants (expression intensity, headline colour, guest presence). (2) Re-fit monthly, not per video. (3) Freeze the style bible for 8-10 videos between changes. (4) Rank-correlate scorer total vs outcome; if the Spearman is below about 0.2 after 30 videos, reduce weights on the scorer and rely on the owner's judgement.

**Pitfalls.** Confounding by topic, title, trend timing and collab guest (the thumbnail is 10-20% of the effect per Galloway, secondary); novelty spikes; impressions shift between browse/suggested; regression to the mean after a lucky video; multiple comparisons with many features; CTR vs retention conflict; Test & compare tests thumbnails only on its own allocation and takes about 2 weeks, so low-traffic videos may yield "same"; changing thumbnails mid-life distorts the baseline (record swap time); Shorts excluded; storage of analytics data must follow YouTube API terms (derived features, not raw copies, long-term; the 30-day refresh/deletion rule mentioned for API data is from a model-card note, unverified).

### Gaps
- Not verified live: whether the channel can create a Reporting job for reach reports (needs OAuth scope yt-analytics.readonly), report retention/backfill length and exact CSV columns. A live API call is needed.
- No evidence of any official Test & compare API; manual in Studio only (repo note, unconfirmed).
- No public data for how few impressions an Israeli 1-2K-sub clip channel gets per video; sample-size numbers assume uniform CTR and ignore traffic-source mix.

---

## 6. Legal and policy: style references, likeness, AI disclosure, misleading thumbnails

### Takeaway
Imitating another channel's thumbnail STYLE (composition conventions, lighting, costume-and-prop storytelling, font look) is ordinary genre practice, but copying its artwork or characters is not; YouTube requires disclosure of realistic synthetic content, with secondary sources disagreeing about whether an AI thumbnail alone triggers it; and the real exposure is the misleading-thumbnail policy and Israeli privacy law on using a person's image for profit without consent.

### Cited Findings
- YouTube Help "Disclosing use of altered or synthetic content": creators must disclose meaningfully altered or synthetic content that appears realistic (e.g. a real person doing/saying something they did not), via the Studio setting at upload; unrealistic or minor edits excluded. Secondary guides: AI-generated still thumbnails generally fall under "no disclosure needed", but thumbnails/metadata that imply authentic footage when synthetic can be a concern; sources disagree. — [YouTube Help 14328491](https://support.google.com/youtube/answer/14328491), [AIR Media-Tech](https://air.io/en/youtube-glossary/what-is-youtubes-ai-content-disclosure-policy), [influencermarketinghub](https://influencermarketinghub.com/youtube-inauthentic-content) (search summaries)
- YouTube Spam, deceptive practices and scams policy: misleading thumbnails/titles that make users believe the content is something it is not are not allowed; (repeatedly) the list is non-exhaustive. YouTube removed two channels of fake AI movie trailers under spam/misleading-metadata policies. — [YouTube spam policy](https://support.google.com/youtube/answer/2801973), [pulse.bot](https://www.pulse.bot/ai/news/youtube-bans-two-popular-channels-that-created-fake-ai-movie-trailers-42e944af-83e7-47f4-b12e-c9c27b89f7dd/) (via repo note; search summary)
- Israel, Protection of Privacy Law 5741-1981: s.1 forbids infringing privacy without consent; s.2(6) lists use of a person's name, appellation, picture or voice for profit as an infringement; consent means informed consent, express or implied; willful infringement carries criminal exposure and civil liability; one court decision reads "for profit" broadly; Israeli courts also apply unjust enrichment. English translations differ; the Hebrew text controls. — [WIPO translation](https://www.wipo.int/wipolex/en/text/347462), [Chambers right-of-publicity guide](https://chambers.com/articles/right-of-publicity-according-to-israeli-law), [afiklaw case summary](https://www.afiklaw.com/caselaw/19927/5) (search summaries)
- InsightFace pretrained models are non-commercial unless licensed; TubeCLIP/z03 are CC BY-NC. (Tooling licence risk, see section 4.)

### Inferences (not legal advice; confirm with an Israeli lawyer)
- **Style references.** Treat Taklipu as a style reference only: reproduce the rules (huge face, costume+prop, colour story, headline layout), never their image files, characters, logos, channel name or a near-copy composition of a specific thumbnail. Do not use their thumbnails as image inputs to the generator or as CLIP training data beyond internal similarity scoring; keep the reference set private and out of the repository's public output.
- **Streamer likeness.** Written, revocable permission from Oded for AI-generated likeness (and for the costume/role depictions) kept on file. **Guests**: informed consent for synthetic likeness in a monetised thumbnail (privacy law s.2(6) risk), keep a record; skip guests who have not agreed.
- **AI disclosure.** Tick the "altered or synthetic content" disclosure if the thumbnail depicts a realistic event that did not occur, as a conservative choice, because thumbnails are not clearly addressed; the cost of ticking it is none per YouTube (does not limit reach or monetisation per a secondary source). Keep every scene element truthful to the video (the premise must be real; a costume is a stylisation, a fake arrest or injury is not).
- **Misleading thumbnails.** Costume scenes (jewel thief, pilot) are acceptable as metaphors if the video actually covers that story; avoid depicting events, products or people states the video does not contain; no fake UI of real services; no third-party logos or game key art copies; do not depict real viral people.
- **Game visuals.** Use generic setting cues; avoid logos and character likenesses; the headline text may name the game (nominative use), but trademark/copyright of game art remains a legal judgement.
- Keep a provenance log per thumbnail: prompt, model, reference files used, approval date.

### Gaps
- YouTube Help pages not read directly; whether the Studio synthetic-content toggle is intended to cover AI-made thumbnails is unresolved.
- No Israeli case law found on AI-generated likeness in thumbnails; the s.2(6) "for profit" reach for a monetised channel is a legal question.
- Streamer-platform terms (Kick content reuse) and music/SFX licensing are out of scope.

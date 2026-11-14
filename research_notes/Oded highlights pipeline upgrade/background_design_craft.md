# Thumbnail background craft: how experts build attractive backgrounds, and what to change in the Oded Highlights pipeline

*Written 14 Nov 2026. Method and reach limits (read first).* Reachable from this sandbox: `github.com`, `raw.githubusercontent.com`, `gh api search/...` (repository and code search). NOT reachable: every non-GitHub page I tried through WebFetch failed DNS (`www.photoshoproadmap.com`, `we.graphics`, `www.photoshopessentials.com`, `digital-photography-school.com`, `1of10.com`); the tool said the hosts "have to be allowed in the session's network settings". So ALL designer-tutorial and video-tutorial material below comes from WebSearch result summaries (page text not read, video transcripts not read, YouTube not reachable) and is marked **(search summary)**. `gh api repos/...` and git-tree listings were refused for repos not attached to the session; file lists came from `gh api search/code` and README text. "Read" = I downloaded the raw file and read it. No downloaded script was executed; the only code that ran is my own (`bgfx.py`, below) on <=1280x720 images, peak RSS 183 MB, <1 s per frame. Test images are `skimage.data` stand-ins (astronaut GrabCut cut-out, rocket, coffee, cat) plus our own plates; so tests prove mechanics, not final beauty. Taste statements ("looks better") are my eyeballing of single renders; no CTR data supports them (see Q1 Gaps). Contact sheets are in the session scratchpad (`.../scratchpad/bg/out/sheet1..5.png`), not in the repo.

---

## Q1. What makes a thumbnail background attractive, and how do experts construct it (layer stacks, blend modes, numbers)?

### Takeaway
Experts do not "draw a nice background"; they take a real or rendered scene, make it quieter than the subject (blur, darken, desaturate), push one saturated colour pair into it as LIGHT (screen/add, coloured glows, rays, bokeh, flares), choose the background hue as the complement of the subject's dominant hue, add a rim/back light to the subject, then unify everything with a grade, vignette and grain. Our current plates fail exactly where this recipe works: they are flat opaque shapes with no luminance hierarchy, no light, no texture.

### Cited Findings
- **Duplicate-and-blur / blurred reference as background.** Take a still from the video, Gaussian-blur 20-40 px (Photoshop/GIMP/Canva), keep the subject as a separate sharp layer on top; Canva variant: blur about 25 on a duplicated background image — (search summary) [get-youtube-thumbnail-downloader background ideas](https://get-youtube-thumbnail-downloader.pages.dev/blog/youtube-thumbnail-background-ideas/), [Recapio digest: Canva thumbnails](https://recapio.com/digest/how-i-design-my-youtube-thumbnails-on-canva-by-laressa-ngoeun); Photoshop variant "Filter > Blur > Gaussian Blur on the background layer" — (search summary) [Recapio digest: Photoshop thumbnail, Vince Opra](https://recapio.com/digest/how-to-make-a-youtube-thumbnail-in-photoshop-2023-quick-easy-tutorial-by-vince-opra). Adobe's own guidance is relayed as "solid colour or relevant image, Gaussian blur if detail distracts" (secondary).
- **Background glow layer = black layer + Screen + big soft brush.** A Photoshop glow tutorial fills a new layer with black, sets it to Screen, paints a soft brush in the middle for a background glow; a second digest describes a bloom glow with a soft round brush in Screen; glow works best on dark backgrounds and should be restrained — (search summary) [Recapio digest: glow effect, Pixolid](https://recapio.com/digest/how-to-create-glow-effect-for-thumbnails-easiest-way-in-photoshop-by-pixolid).
- **Colour-matching trick:** eyedrop a colour from the main subject and use it as the background colour for a harmonious thumbnail — (search summary) [Recapio digest, Canva thumbnails](https://recapio.com/digest/how-i-design-my-youtube-thumbnails-on-canva-by-laressa-ngoeun). The opposite advice (complement of the subject's skin tone: warm face on blue/teal/violet) appears in several colour guides; a guide suggests swapping the background to the complement and previewing at 168x94 — (search summary, not attributable to one page) [1of10 colours](https://1of10.com/blog/best-colors-for-youtube-thumbnails), [Recraft colourful backgrounds](https://www.recraft.ai/blog/colorful-thumbnail-background-guide). Same sources: contrast between foreground and background matters more than which hue; dark background + bright subject (or reverse) beats mid-tones; in dark mode a pure-black background hides the thumbnail edge, so keep a slightly lighter dark.
- **Rim light** = a bright light placed behind the character giving an edge glow that separates it from the background; most important when a dark character sits in a dark scene — (search summary) [Photoshop Roadmap glowing thumbnails](https://www.photoshoproadmap.com/how-to-create-glowing-youtube-thumbnails-in-photoshop/). A rim alone looks unfinished and needs grading afterwards — (search summary) [Fstoppers](https://fstoppers.com/education/how-add-lovely-rim-light-effect-using-photoshop-197434) (cited by an earlier note in this repo).
- **Light leaks / bokeh overlays:** place the light-leak or bokeh layer above the photo, blend mode Screen (black drops out; grey does not, so the overlay should be near-black), then reduce opacity (one guide ~70%, another ~50%), hue-shift to match, mask off unwanted areas; other modes mentioned: Lighten, Color Dodge, Linear Dodge — (search summary) [Expert Photography light leaks](https://expertphotography.com/light-leaks-overlays), [PHLEARN add bokeh](https://phlearn.com/tutorial/add-bokeh/), [Fontbundles easy light leak](https://fontbundles.net/design-school/easy-light-leak-in-photoshop).
- **Volumetric rays:** build streaks with Radial Blur (Zoom) with the blur centre at the light source, repeat with Ctrl-F, Gaussian-blur to soften, set the layer to Screen (Soft Light for subtlety), mask the rays off where they should not cross the subject — (search summary) [Fontbundles light rays](https://fontbundles.net/design-school/add-light-rays-in-photoshop), [PHLEARN light flare and rays](https://phlearn.com/tutorial/how-to-add-light-flare-light-rays-in-photoshop/). The same summary noted no tutorial covered the glow-behind-subject step itself.
- **Split tone / teal-orange:** one tint in shadows, another in highlights; teal/blue shadows with amber/orange highlights is the standard way to separate warm skin from the background; keep it subtle (a tool guide: saturation about 15-45%, a rule of thumb) — (search summary) [ShotKit teal-orange](https://shotkit.com/teal-orange-look/), [Zoner teal-orange](https://learn.zoner.com/color-grading-step-by-step-iii-how-to-get-the-popular-teal-orange-look/), [imag-r split toning](https://imag-r.com/toolset/splittoning).
- **Gradient Map** as a non-destructive adjustment layer, complementary pair typed as hex, blend mode soft light/overlay (the summary did not say which page states which), used to separate the subject from the background rather than as a stylised grade — (search summary) [Digital Photography School gradient maps](https://digital-photography-school.com/how-to-create-and-use-gradient-maps-in-photoshop/), [CapCut gradient maps](https://www.capcut.com/create/gradient-maps-creative-color-grading-photos-video).
- **Vignette:** painted on a separate layer with a large soft brush at reduced opacity (generic tutorial advice); draws the eye to the centre — (search summary, several game-thumbnail pages, low authority) [Photoshop Roadmap](https://www.photoshoproadmap.com/how-to-create-glowing-youtube-thumbnails-in-photoshop/).
- **MrBeast-style backgrounds** (SEO/tool-vendor articles, no named designer, unverified): background simplified to one high-saturation colour or a simple scene; complex backgrounds blurred or replaced with 3D renders; text/main object on the opposite side of the colour wheel from the dominant background colour — (search summary) [thumbli MrBeast guide](https://thumbli.pages.dev/blog/how-mrbeast-designs-his-youtube-thumbnails-template-guide), [Touhfa analysis](https://touhfa.pages.dev/blog/thumbnails/mrbeast-thumbnail-article/), [Podcastle](https://podcastle.ai/blog/mrbeast-thumbnails).
- **Skill-file wording on the same rules** (read): "One focal subject ... Blur, darken, or crop everything else. The subject is the brightest, most saturated, most in-focus element"; "Use 1 or 2 hero colors on a complementary background"; lighting line "strong rim light to separate the subject from the background, bright key light on the face, darker or blurred background. Push saturation and contrast past what feels tasteful on a monitor"; image prompt skeleton "Plain deep-blue studio background with a soft radial glow behind the subject. Strong cyan rim light ... background slightly blurred" — [mrbeast-thumbnail-skill packaging-rules.md](https://raw.githubusercontent.com/Albisourous/mrbeast-thumbnail-skill/main/references/packaging-rules.md), [image-prompts.md](https://raw.githubusercontent.com/Albisourous/mrbeast-thumbnail-skill/main/references/image-prompts.md). Also from a CC-BY skill: "Flat lighting that makes the face look 2D. Add a slight rim light or glow behind the subject"; "Background colors that blend with skin tone or hair color" are a mistake; "Never busy backgrounds that fight the expression" — [creator-skills-samples ai-thumbnail-factory SKILL.md](https://raw.githubusercontent.com/calebvbi/creator-skills-samples/main/skills/ai-thumbnail-factory/SKILL.md).
- **Counter-evidence on whether any of this moves CTR:** an analysis of 507,478 videos reported brightness, saturation, contrast and warm colours did not separate winners from losers — (search snippet only, page unreachable) [Eden](https://eden.so/blog/what-makes-a-good-youtube-thumbnail/), quoted in `research_notes/.../thumbnail_finishing_techniques.md` Q1.
- **Taklipu reference analysis (repo doc, 35 thumbnails):** background is the literal story location, person lit by the scene, split warm/cool lighting, all-sharp frames, median brightness 0.41, median saturation 0.50 — [docs/THUMBNAIL_BACKGROUNDS_LEARNED.md](file:///home/user/oded-highlights/docs/THUMBNAIL_BACKGROUNDS_LEARNED.md). Note median brightness 0.41 (not dark-moody): the references are mid-bright and saturated, not murky.
- **First-hand diagnosis of our plates (viewed `assets/plates3/jewellery_store.jpg`, `assets/plates/stage_arena.jpg`, `airport.jpg`, `casino.jpg`):** (a) stage plate = opaque, hard-edged translucent cones and uniform alpha-composited discs: no additive light, no falloff, no highlights over 80% luminance except flat pastel; (b) jewellery plate bakes the Latin word "JEWELRY" in a box into the plate (clashes with our Hebrew overlay and reads as a UI mock); (c) airport plate is bright and pastel with a hard-edged grid, so any additive effect blows it out (my test, Q4); (d) `thumb_plates3.py` bokeh = `ImageDraw.ellipse` filled with a dimmed colour then Gaussian blur (so a soft disc without a rim, additive but low-contrast), `rays()` = polygons blurred. — files: [scripts/thumb_plates3.py](file:///home/user/oded-highlights/scripts/thumb_plates3.py), [assets/plates/stage_arena.jpg](file:///home/user/oded-highlights/assets/plates/stage_arena.jpg).
- **First-hand tests ([TESTED], code in Q4):** the same plates after a 160-230 ms post-pass (gamma 1.12, soft-light fbm texture 10%, bloom from highlights, light leaks, window god-rays, rim-bokeh in Screen, S-curve, saturation 1.1, vignette 0.4, grain 0.016) looked richer and more photographic (stage, casino, jewellery), but the pass cannot fix composition and it blew out the bright airport plate. A real photo (rocket) through `photo_relight2` (mild desat, gamma 1.12, warm radial light screened bottom-left, cool top-right, split-tone 0.3, bloom, bokeh, S-curve, saturation 1.18, vignette) became noticeably more cinematic; my first, heavier version (gamma 1.35, desat .35, grain .03) looked muddy and worse than the raw photo, so the amounts matter.

**Typical Photoshop layer stack (bottom to top) and its numpy translation.** Numbers are tutorial-level starting points (search summaries) or my tested values, not measured optima.
| # | Photoshop layer | Blend / opacity (source or tested) | numpy / Pillow op |
|---|---|---|---|
| 0 | base plate: stock photo / game frame / AI scene / mesh gradient | normal | `to_f(cover(img,w,h))` or `mesh_gradient()` |
| 1 | duplicate + Gaussian blur (or lens blur outside the hero zone) | blur 20-40 px (tutorial, resolution unstated); tested: sigma 14*(w/640) px, 2.5-3 px for a photo that should stay recognisable | `gblur`, `depth_blur` |
| 2 | darken: curves / black fill | tested: gamma 1.12-1.25; dup-blur multiply 0.8 | `a**1.12`, `a*0.8` |
| 3 | colour grade: gradient map / solid colour (soft light) / split tone | soft light, 30-55% (tested 0.3) | `split_tone`, `gradient_map` |
| 4 | coloured light: soft radial gradients, warm one side, cool the other | Screen 60-75% (tested .7/.6) | `radial_light` + `screen` |
| 5 | light leaks, bokeh, flare overlays | Screen, 50-70% opacity (tutorials), tested .5-.9 with layer intensity .25-.5 | `light_leaks`, `bokeh`, `anamorphic_flare` |
| 6 | god rays (radial zoom blur of a bright shape) masked off the subject | Screen 0.5-1.0 | `window_source`, `god_rays(occluder=alpha)` |
| 7 | subject cut-out + outline + rim + back glow + light wrap | normal; rim Screen | see `thumbnail_finishing_techniques.md`; `light_wrap` here |
| 8 | vignette | multiply, black radial 30-50% | `vignette(0.4)` |
| 9 | headline scrim (feathered dark box) | normal black 40-55% | `scrim` |
| 10 | grain/noise | overlay or soft light, tiny (tested 0.016 std at 640 px) | `film_grain` |
| 11 | sharpen at export | unsharp 1.0 px / 70% | Pillow `UnsharpMask` |

### Inferences
- Consistent expert pattern: separation before beauty. In order: (1) quieter background than subject (luminance and detail), (2) hue relationship (complement or warm/cool split), (3) light that exists in the scene (rim, glow behind head, additive flares), (4) one global grade/vignette/grain to glue it.
- Our "not attractive" verdict is explained by: flat-fill shapes, normal-blend translucent discs, pastel mid-values, no texture or grain, no dark anchor, a prop-less scene that does not tell the story. Post-processing a flat plate improves "feel" but the biggest lever is a real or rendered photographic scene (Q2, Q6).
- Photoshop opacity numbers in the tutorials are for 1920x1080-class work and unspecified; use the tested numbers above and scale blurs by `w/640`.

### Gaps
- No primary designer breakdown, video transcript or MrBeast-team statement was reachable; all workflow facts are second-hand summaries from search results (listed as such). No A/B or CTR data for any single background technique (Eden snippet argues colour/brightness did not matter; unverified). I could not fetch Photoshop Roadmap, we.graphics, PHLEARN, Digital Photography School (DNS), so exact blur radii, opacities and blend orders are not confirmed from the pages themselves.

---

## Q2. Gaming / streamer / reaction niche: why is the background the thing reacted to, and what to do without an AI image generator?

### Takeaway
In reaction and highlight thumbnails the background is usually a blurred/darkened frame of the thing being reacted to (clip, article, game screen) with a large sharp face over it, because it gives context for free and stays below the face in contrast. Taklipu goes further (full AI scene lit around the person). Without an AI generator, the best no-cost background we always have is the stream's own frame (game screen or his room), blurred, graded and lit procedurally; second best: a licensed stock photo graded the same way.

### Cited Findings
- Blurred still from the scene as background with the subject sharp on top, face at least one third of the frame; a "mini version of what is being reacted to", a blurred screenshot or a graphic clue as the secondary element — (search summary) [Piktochart reaction thumbnails](https://piktochart.com/blog/how-to-make-a-reaction-thumbnail/), [get-youtube-thumbnail-downloader](https://get-youtube-thumbnail-downloader.pages.dev/blog/youtube-thumbnail-background-ideas/). A Picsart template post describes the same layout: cut-outs of subject and pointing finger over a darkened, blurred copy of the reference photo — (search summary) [Picsart](https://picsart.com/blog/wp-json/wp/v2/posts/262612).
- Copyright caution: a guide advises blurred or stylised official artwork rather than copyright-heavy raw screenshots; it adds that blurring does not clearly remove copyright issues — (search summary) [Piktochart](https://piktochart.com/blog/how-to-make-a-reaction-thumbnail/). Our channel already has its own stream as source, so this mainly matters for third-party clips.
- A blurred or hidden element can add curiosity ("withholding part of the story") — (search summary) [Piktochart](https://piktochart.com/blog/how-to-make-a-reaction-thumbnail/).
- AI-skill advice: generate only backgrounds and supporting elements, composite the real face ("AI faces look uncanny"); keep a gap (left/right 35%) for the face in generated backgrounds; reaction background prompt "describe what's being reacted to ... High contrast, dramatic lighting. Space on the right 35% ... No text, no logos" — [ai-thumbnail-factory SKILL.md](https://raw.githubusercontent.com/calebvbi/creator-skills-samples/main/skills/ai-thumbnail-factory/SKILL.md). The skill's gaming line: "Saturated colors, dynamic angles, character-focused, dark backgrounds with bright accents".
- Taklipu: person INSIDE the literal scene, props touching the person, generator renders person + scene as one image (so face lighting comes from the scene) — [docs/THUMBNAIL_BACKGROUNDS_LEARNED.md](file:///home/user/oded-highlights/docs/THUMBNAIL_BACKGROUNDS_LEARNED.md). Free AI route for such scenes (FLUX.2 klein on Cloudflare free neurons; 4 reference images) is analysed in [thumbnail_free_image_apis.md](file:///home/user/oded-highlights/research_notes/Oded%20highlights%20pipeline%20upgrade/thumbnail_free_image_apis.md); not repeated here.
- First-hand tests ([TESTED]): `dup_blur_bg` (zoom 1.12, blur sigma 14 at 640, darken, 25% navy multiply tint) on a dark photo gave a near-black dull plate at darken 0.55 (too heavy; default raised to 0.8); `photo_relight2` with a `focus` box (blur outside the hero zone 2.5 px) kept the rocket recognisable and added colour (see Q1 findings).
- No free stock-photo or CC0 texture repository was found on GitHub: searches for "cc0 backgrounds images", "light leak overlays free pack", "bokeh overlay textures free" returned unrelated repos; Pexels/Unsplash/Wikimedia hosts were not reachable (DNS) so I could not test downloading plates.

### Inferences
- No-AI plate hierarchy (best first): (1) the clip's own frame or his room (zero licensing question, topic-literal, already in the video), run through `dup_blur_bg` -> `photo_relight2`; (2) a pre-licensed stock photo bank per topic (owner's machine can probably reach Pexels/Unsplash; I could not verify), same pipeline; (3) our procedural scene (mesh gradient + light layers) with a recognisable cue object drawn large; (4) flat vector plates only after `upgrade_plate2`.
- Make the sharp face brighter and more saturated than anything behind it; the stream frame should lose detail (blur/zoom) but keep colour blobs so the topic still reads.
- When the reacted-to object itself is the story (article, tweet, game boss), keep a small, sharp, rotated copy as a prop in front of the blurred plate rather than making the background carry the information.

### Gaps
- No Taklipu or MrBeast-team material read; the "background is what is reacted to" claim rests on tutorial summaries plus the repo's own 35-thumbnail analysis. No quantitative comparison of blurred-frame vs AI-scene backgrounds for CTR. I did not view any real Taklipu thumbnails (they are described only in the repo doc).

---

## Q3. Background ideas per video topic (our 16), readable in one second at 168x94, with colour stories

### Takeaway
Every background below is built from at most three large shapes: one dark saturated field behind/around the subject (left, calm), one luminous focal accent on the prop side (the brightest object, 3-8% of the frame), and one topic cue (silhouette/prop) drawn big. Colour stories use a warm/cool pair; the dark key is the complement of the usual warm skin/hair, so the face separates.

### Cited Findings
- Topic list and scene prompts come from the repo's plate brief ([docs/THUMBNAIL_BACKGROUND_PLATES.md](file:///home/user/oded-highlights/docs/THUMBNAIL_BACKGROUND_PLATES.md): 16 scenes) and the observed topic table (props, colour stories) in [docs/THUMBNAIL_BACKGROUNDS_LEARNED.md](file:///home/user/oded-highlights/docs/THUMBNAIL_BACKGROUNDS_LEARNED.md). Observed Taklipu colour stories there: law = warm brown + red; heist = red/blue police split; alley = blue-red neon; airport = cool daylight + warm sun; birthday = purple + gold; dating show = purple/pink/gold; trivia = saturated rainbow on dark blue; AI = cool blue + white; king = gold + red; court = red-orange fire on dark blue; horror = black + orange; election = yellow burst + blue.
- Guides: 168x94 preview as the test; avoid neon-on-neon (equal-saturation colours fight); dark charcoal backgrounds make bright foreground elements stand out — (search summary) [colour guides](https://www.recraft.ai/blog/colorful-thumbnail-background-guide), [game thumbnail tips](https://clip.dor.gg/en/blog/game-thumbnail-design-tips).

### Inferences (proposals; hex values are my starting palettes, not measured from references)
Format: dark key / luminous accent / second hue; 1-second read; procedural ingredients (functions from Q4); 'photo' = what to ask a photo/AI source for.
| # | Topic | Palette (dark key / accent / 2nd) | 1-second read at 168 px | Procedural ingredients | Photo / AI ask |
|---|---|---|---|---|---|
| 1 | Phone call / drama | #0b1d2a / #ff7a1a / #19d3da | glowing phone-screen rectangle on the right, orange street lamps | mesh gradient teal-black, `bokeh` orange + cyan (rim 0.55) in lower half, `anamorphic_flare` cyan, wet-street reflection (flip + blur + fade) | dark neon street, wet asphalt |
| 2 | Heist / jewellery | #0a0f2c / #ff2030 + #2a6bff / white | red-left vs blue-right police light, sparkling gems | `radial_light` red left, blue right, `sparkles` on gems, `anamorphic_flare`, shard particles | jewellery shop at night, police lights |
| 3 | Money / vault | #08140f / #ffc93c / #2ecf6a | gold light rays from a vault door, green cash | `window_source` as vault door + `god_rays` gold, gold `bokeh`, `sparkles` | gold-and-green vault, rays |
| 4 | Casino-style | #14040a / #ff2a4d / #ffcf3a | red wall, dense gold bokeh, marquee dots | dense `bokeh` (n 40), row of bulbs (dots), green felt wedge, `light_leaks` red | casino floor neon |
| 5 | Court / law letter | #1a0f08 / #c98a3c / #b3202a | amber window light shafts through a dark room, red stamp | `window_source` + `god_rays` amber at low strength, heavy `vignette`, books as dark silhouettes, dust motes (small `sparkles`) | dark wood law office, lamp light |
| 6 | Airport | #123a73 / #ffb45a / #e8f4ff | huge window, sun flare, perspective floor | `anamorphic_flare` warm from window, mesh blue gradient; keep mean luma <0.5 (auto-gamma) or it washes out (my test) | departures hall, sunset light |
| 7 | Birthday | #2a0f5c / #ffcf3a / #ff4fa3 | confetti and string-light bokeh, balloon colour blobs | `bokeh` gold/pink, `sunburst` 0.25, confetti (small rotated rectangles; not tested) | party room |
| 8 | TV studio / dating show | #1a0838 / #ff3fa4 / #7a4bff | pink neon heart outline, "ON AIR" red box, glossy floor | neon outline = draw shape, blur, `add` twice (glow + core); floor reflection | talk-show studio, purple and pink neon |
| 9 | Quiz / trivia | #0b1a5c / #ffd23a / #36e0ff | bright coloured grid on a stage, spotlight beams | `sunburst` (soft), additive spotlight cones (NOT opaque), `sparkles` | game-show stage |
| 10 | Gaming room / streamer | #0d0a2a / #7a3dff / #19c8ff | monitor glow rectangles, RGB strips | his real room via `dup_blur_bg` + purple `radial_light` + monitor rectangles in Screen | dark gaming room RGB |
| 11 | Game launch / GTA-style | #2a0b4d / #ff4f9a / #ffb347 | sunset sun disc, palm silhouettes, pink-purple sky | `mesh_gradient` sky (warp 0.15), sun disc + 3-4 horizontal stripes, silhouettes | neon sunset skyline |
| 12 | Fight / rage | #1a0505 / #ff3b14 / #ffb02e | red-orange fire sky, embers, speed lines | `sunburst` + `speed_lines` (white 0.5), embers = small `sparkles`, smoke = `fbm` soft-light | stormy red sky, sparks |
| 13 | Travel gone wrong | #150a30 / #b04bff / #ff7ab0 | purple neon palm-hotel sign, rain streaks | `radial_light` purple, rain = thin slanted lines blurred, bokeh pink | hotel street at night, rain |
| 14 | Food / shawarma | #1b0d05 / #ff8a1f / #ffd25a | orange grill glow, steam | `radial_light` orange low-centre, steam = `fbm` Screen 0.25, warm `bokeh`; small teal accent right | street-food stall at night |
| 15 | AI / tech | #04122a / #1e7bff / #8be9ff | cyan glow orb, light beams, grid | `god_rays` blue, `anamorphic_flare` cyan, `halftone_dots` as circuit dots, grid lines | server room, blue beams |
| 16 | Sports / challenge | #07121f / #ffd84a / #22b86a | stadium floodlights (bright stars), green pitch at bottom | `sparkles` large (floodlights) + `anamorphic_flare` gold, `speed_lines` low density | stadium floodlights at dusk |
Rules that apply to all rows: luminous accent is the brightest area except the face; subject zone (left 45%) mean luma 0.15-0.35; do not exceed 2 motifs (e.g. rays + bokeh) per plate; no Latin or Hebrew text in the plate; the second hue must differ in lightness as well as hue (avoid neon-on-neon).

### Gaps
- None of the hexes or motif choices is validated against the actual Taklipu thumbnails or any CTR data; confetti, rain, neon-outline and wet-floor reflection recipes were not implemented/tested. No per-topic reference thumbnails were available to me.

---

## Q4. Existing open-source code and tested recipes (repos evaluated; code runs at 640x360)

### Takeaway
No mature open-source "thumbnail background generator" exists: the usable code is small and scattered (notion-bg-gen for numpy gradient fields, film-lab for fitted grain/halation constants, pilgram for blend-mode LUTs). Everything needed fits in ~200 lines of numpy/OpenCV that I wrote and tested; the repos mainly provide validation of the approach and a few constants.

### Cited Findings
Repository evaluation (all read from raw GitHub on 14 Nov 2026; star counts and push dates from `gh api search/repositories`):
| Repo | Licence | Stars / pushed | What I read | Output quality / how to borrow |
|---|---|---|---|---|
| [dj-skn/notion-bg-gen](https://raw.githubusercontent.com/dj-skn/notion-bg-gen/main/src/notion_bg_gen/render/gradient.py) (Python, Notion cover mesh-gradients) | MIT (c) 2024 Jan Halczuk ([LICENSE](https://raw.githubusercontent.com/dj-skn/notion-bg-gen/main/LICENSE)) | 18 / 2026-11-04 | `render/gradient.py` (4 styles: mesh, aurora, blobs, linear), `render/grain.py`, `render/palette.py` | numpy-only. "mesh" = 10 radial alpha blobs (random centres, colours from palette) premultiplied-over, masked to a bottom ellipse, blurred sigma 300*scale; "aurora" = 6 sine-warped horizontal bands; blur = 3 box passes via summed-area table, "cost independent of the radius" and large blurs run on a downsampled copy. grain.py documents a bug: `np.random.normal(...).astype(np.uint8)` wraps negatives so ~47% of noise lands at 200-255 (salt-and-pepper); fix = signed float noise, mono across RGB, clip once. I did not render its output. Borrow: box-blur-via-cumsum, premultiplied `over`, the grain lesson. Not thumbnail-specific. |
| [thedevmark/film-lab](https://raw.githubusercontent.com/thedevmark/film-lab/main/filmlab/effects.py) | MIT (c) 2026 Mark Koellmann | 2 / 2026-10-06 | `filmlab/effects.py` | halation: additive in linear light, threshold 0.70, channel gains R 1.0 / G 0.28 / B 0, radius as fraction of long edge; grain: band-pass (subtract a blur 4x wider), tone weight with floor 0.31 at both ends, chroma share 0.80, channel gains (1.20, 1.00, 1.05), constants fitted to two Kodak scans (the file states "they describe THAT scanner and THAT stock"). Borrow constants/ideas for `film_grain`; code not run (I re-implemented a simplified version). |
| [praveenmuragod/youtube-thumbnail-generator](https://raw.githubusercontent.com/praveenmuragod/youtube-thumbnail-generator/main/core/ai_backgrounds.py) | MIT ([LICENSE](https://raw.githubusercontent.com/praveenmuragod/youtube-thumbnail-generator/main/LICENSE)) | 0 / 2026-05-13 | `core/ai_backgrounds.py`, README | Flask app, DALL-E 3 background or procedural fallback: 1024-px multi-stop colour ramp rotated to an angle; "glow" = concentric alpha ellipses + blur 60; "vignette" = 40 concentric rectangle outlines + blur 30 (crude). Output not rendered. Only idea worth taking: "AI scene if available else procedural plate" switch. Weak. |
| [akiomik/pilgram](https://raw.githubusercontent.com/akiomik/pilgram/main/README.md) | Apache-2.0 ([LICENSE](https://raw.githubusercontent.com/akiomik/pilgram/main/LICENSE)) | 134 / 2026-11-10 | README, `pilgram/css/blending/soft_light.py` | Instagram-style filters and CSS blend modes for Pillow via 256-entry LUTs; its soft-light uses the W3C formula incl. the `D(Cb)` sqrt branch, same as my numpy `soft_light`. Use only if we want ready-made grades; not installed here. |
| [philgyford/python-halftone](https://raw.githubusercontent.com/philgyford/python-halftone/master/halftone.py) | NO licence file found (`LICENSE.txt` 404; search spdx null); source credits a StackOverflow answer by fraxel | 104 / 2021-12-21 | head of `halftone.py` | CMYK screen angles [0,15,30,45], dot size from sampled block brightness (PIL). Cannot be copied; my own `halftone_dots` is a 12-line rotated-grid distance field. |
| [JaydenB/ghostlight](https://raw.githubusercontent.com/JaydenB/ghostlight/main/README.md) | MIT per GitHub search (licence file not read) | 1 / 2026-10-05 | README only | optical-design/lens-flare ghost renderer requiring NVIDIA CUDA; not usable on our CPU box; useful only as a reference for how real flare ghosts/starbursts look. |
| [wundercorp/gradient-mesh-skill](https://raw.githubusercontent.com/wundercorp/gradient-mesh-skill/main/SKILL.md) | MIT (c) 2026 BuilderStudio | 1 / 2026-06-08 | SKILL.md, README | Web (CSS/SVG) mesh backgrounds; rules: two to five colour stops, avoid busy high-frequency texture behind text, keep a fallback colour. Its Python pointer (DonsetPG/MeshGradientPy) is, by its own text, a library for "computing gradients on mesh and unstructured data objects" (numerical), NOT a graphics mesh-gradient maker. Not useful for rendering. |
| [jsath/claude-skills thumbnail-generator](https://raw.githubusercontent.com/jsath/claude-skills/main/skills/video/thumbnail-generator/SKILL.md), [ArnavPuri/designskills](https://raw.githubusercontent.com/ArnavPuri/designskills/main/skills/thumbnail-design/SKILL.md) | MIT / MIT | see [design_skills_review.md](file:///home/user/oded-highlights/research_notes/Oded%20highlights%20pipeline%20upgrade/design_skills_review.md) | read by an earlier researcher in this repo | Pillow compositor with QA, glow-ring rule (radial gradient 0.4 alpha behind the face). Not repeated. |
Other findings: GitHub search for mesh gradient / lens flare / bokeh / aurora / god rays / Perlin clouds in Python returned no usable maintained library (hits were FEM mesh code, WebGL/Swift/Flutter/JS fluid-gradient libs such as sarcadass/granim.js and Cindori/FluidGradient, or tiny abandoned repos). The earlier note lists no mature thumbnail generator either ([design_skills_review.md](file:///home/user/oded-highlights/research_notes/Oded%20highlights%20pipeline%20upgrade/design_skills_review.md)).

**First-hand tests ([TESTED] at 640x360, warm, 4-core CPU, my own code below; 1280x720 about 4.5x):** mesh gradient 4 ms; light leaks 3.6 ms (drawn at 1/4 res; my first version at full res took 107 ms); anamorphic flare 17 ms; god rays (28 zoom steps) 11 ms; bokeh (40 balls) 6.5 ms; film grain 27 ms; halftone 17 ms; speed lines 11 ms; sparkles (5 stars) 27 ms; fbm clouds 12 ms; sunburst 8 ms; dup-blur 30-40 ms; full `upgrade_plate2` 159 ms (724 ms at 1280x720); `photo_relight2` 154 ms (862 ms at 1280x720); peak RSS 183 MB. Visual findings from the sheets: (1) OKLab mesh mixing gave lighter, pastel mid-tones (lavender between red and blue), sRGB mixing gave punchier saturated purple, so for dark punchy thumbnail plates sRGB may be preferable and OKLab is for avoiding grey mid-gradients between complementary hues; (2) a plain radial blob through zoom accumulation gives only a glow; rays need a structured source (window mullions) to be streaky; occluder alpha makes the rays pass behind the subject; (3) bokeh drawn as additive layer with a brighter rim, Screen-blended, looks like lens bokeh; the same circles alpha-composited as flat discs look like stickers; (4) film grain at 0.03 looked blotchy at 640 px, 0.016 looked right; (5) halftone dots read as comic print when the field is a radial burst; (6) speed lines and sunburst are strong, use at 0.4-0.6 opacity.

### Inferences — recipes (copy these; all tested; the file used is `scratchpad/bg/bgfx.py`, ~230 lines; MIT-style free to copy into the repo, written by me from standard formulas; the blend-mode formulas are the W3C compositing definitions)
**Helpers, blend modes, OKLab, noise** (imports first; every snippet below is extracted verbatim from the tested file)
```python
import math
import numpy as np
import cv2
from PIL import Image
```
```python
def to_f(im): return np.asarray(im.convert("RGB"), np.float32) / 255.0

def to_im(a): return Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8))

def grid(w, h):
    y, x = np.mgrid[0:h, 0:w].astype(np.float32); return x, y

def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a + 1e-9), 0, 1); return t * t * (3 - 2 * t)

def luma(a): return a @ np.array([0.2126, 0.7152, 0.0722], np.float32)

def gblur(a, sigma):
    return cv2.GaussianBlur(a, (0, 0), sigmaX=float(sigma), sigmaY=float(sigma), borderType=cv2.BORDER_REFLECT)

def screen(base, top, k=1.0): return 1 - (1 - base) * (1 - np.clip(top * k, 0, 1))

def add(base, top, k=1.0): return base + top * k            # "linear dodge"; clip at the end

def multiply(base, top, k=1.0): return base * (1 - k + k * top)

def overlay(a, b):  return np.where(a < .5, 2 * a * b, 1 - 2 * (1 - a) * (1 - b))

def soft_light(a, b):  # W3C compositing spec formula
    d = np.where(a <= .25, ((16 * a - 12) * a + 4) * a, np.sqrt(a))
    return np.where(b <= .5, a - (1 - 2 * b) * a * (1 - a), a + (2 * b - 1) * (d - a))

def lerp(a, b, t):
    t = t[..., None] if (np.ndim(t) == 2) else t
    return a * (1 - t) + b * t
```
```python
# ---------- colour: OKLab so mixes do not go grey/muddy ----------
_M1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929], [0.2119034982, 0.6806995451, 0.1073969566], [0.0883024619, 0.2817188376, 0.6299787005]], np.float32)
_M2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468], [1.9779984951, -2.4285922050, 0.4505937099], [0.0259040371, 0.7827717662, -0.8086757660]], np.float32)
def srgb2lin(c): return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
def lin2srgb(c): c = np.clip(c, 0, 1); return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)
def rgb2oklab(c):
    l = srgb2lin(c) @ _M1.T; return np.cbrt(l) @ _M2.T
def oklab2rgb(L):
    l = (L @ np.linalg.inv(_M2).T) ** 3; return lin2srgb(l @ np.linalg.inv(_M1).T)
def hex2f(h): h = h.lstrip("#"); return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], np.float32) / 255
```
```python
# ---------- value-noise / fbm (Perlin substitute: random grids upscaled bicubic) ----------
def value_noise(w, h, cell, seed=0):
    rng = np.random.default_rng(seed)
    gw, gh = max(2, int(w / cell) + 3), max(2, int(h / cell) + 3)
    g = rng.random((gh, gw)).astype(np.float32)
    up = cv2.resize(g, (gw * int(cell), gh * int(cell)), interpolation=cv2.INTER_CUBIC)
    return up[:h, :w]
def fbm(w, h, base_cell=160, octaves=4, seed=0):
    out = np.zeros((h, w), np.float32); amp = 1.0; tot = 0
    for o in range(octaves):
        out += amp * value_noise(w, h, max(4, base_cell / 2 ** o), seed + o); tot += amp; amp *= 0.5
    return out / tot
```
**Recipe 1: mesh gradient** (Gaussian-weighted colour points solved at 1/6 res, bicubic upscale; `warp` domain-warps with fbm for the fluid look; `space="srgb"` for punchier mids)
```python
def mesh_gradient(w, h, pts, sigma=0.35, warp=0.0, seed=0, space="oklab", res=1 / 6):
    """pts = [(x01, y01, '#rrggbb', weight)]. Gaussian-weighted colour points, solved at low-res then bicubic-upscaled.
    warp>0 domain-warps with fbm for the 'fluid' look. space='oklab' avoids grey mid-tones."""
    sw, sh = max(16, int(w * res)), max(9, int(h * res))
    x, y = grid(sw, sh); x /= sw; y /= sh
    if warp:
        x = x + warp * (fbm(sw, sh, sw / 3, 3, seed) - .5); y = y + warp * (fbm(sw, sh, sw / 3, 3, seed + 9) - .5)
    num = np.zeros((sh, sw, 3), np.float32); den = np.zeros((sh, sw, 1), np.float32)
    for (px, py, col, wt) in pts:
        c = hex2f(col) if isinstance(col, str) else np.asarray(col, np.float32)
        if space == "oklab": c = rgb2oklab(c)
        d2 = ((x - px) ** 2 + (y - py) ** 2 * (h / w) ** 2) / (2 * sigma ** 2)
        wgt = (wt * np.exp(-d2))[..., None]; num += wgt * c; den += wgt
    out = num / np.maximum(den, 1e-6)
    out = oklab2rgb(out) if space == "oklab" else out
    return np.clip(cv2.resize(out, (w, h), interpolation=cv2.INTER_CUBIC), 0, 1)
```
Example: `mesh_gradient(640,360,[(.05,.15,"#ff2a3d",1),(.45,.9,"#7a1fff",1),(.95,.2,"#1fa2ff",1),(.75,.85,"#00e0c6",.7)],.38,warp=.18,seed=2)`
**Recipe 2: light leaks** (returns a LIGHT layer; combine with `screen(plate, ll, .85)`)
```python
def light_leaks(w, h, colors=("#ff5a1f", "#ff2d6f", "#ffb347"), n=3, seed=1, blur=0.08):
    """Soft elongated warm blobs entering from the frame edge; returns a LIGHT layer (black bg) -> screen it. Drawn at 1/4 res (blur is huge anyway)."""
    rng = np.random.default_rng(seed); q = 4; sw, sh = w // q, h // q; layer = np.zeros((sh, sw, 3), np.float32)
    for i in range(n):
        c = hex2f(colors[i % len(colors)]); edge = rng.integers(4)
        cx, cy = [(rng.uniform(.1, .9) * sw, -0.05 * sh), (rng.uniform(.1, .9) * sw, 1.05 * sh), (-0.05 * sw, rng.uniform(.1, .9) * sh), (1.05 * sw, rng.uniform(.1, .9) * sh)][edge]
        a = np.zeros((sh, sw), np.float32)
        cv2.ellipse(a, (int(cx), int(cy)), (int(sw * rng.uniform(.25, .5)), int(sh * rng.uniform(.06, .14))), math.degrees(rng.uniform(0, math.pi)), 0, 360, 1.0, -1)
        a = gblur(a, sw * blur * rng.uniform(.8, 1.6)); a /= max(a.max(), 1e-6)
        layer += a[..., None] * c * rng.uniform(.55, .95)
    return cv2.resize(layer, (w, h), interpolation=cv2.INTER_CUBIC)
```
**Recipe 3: anamorphic flare** (thin horizontal streak + fat faint skirt + hot core + faint ghost ring; `screen`/`add` it)
```python
def anamorphic_flare(w, h, pos, color="#5ab8ff", length=0.5, core=0.05, intensity=1.0):
    """Horizontal blue streak + hot core from one point. Returns LIGHT layer -> screen/add."""
    x, y = grid(w, h); px, py = pos[0] * w, pos[1] * h
    dx, dy = np.abs(x - px), np.abs(y - py)
    streak = np.exp(-dx / (w * length * .35)) * np.exp(-(dy / (h * 0.006 + 0.8)) ** 2)      # thin, long, exponential falloff
    streak2 = np.exp(-dx / (w * length * .9)) * np.exp(-(dy / (h * 0.02 + 1.5)) ** 2) * .35  # fatter faint skirt
    glow = np.exp(-((dx ** 2 + dy ** 2) / (2 * (min(w, h) * core) ** 2))) * 1.2
    ring = np.exp(-(((np.hypot(dx, dy) - min(w, h) * .12) / (min(w, h) * .012)) ** 2)) * .08   # faint ghost ring
    c = hex2f(color)
    lay = (streak + streak2)[..., None] * c + glow[..., None] * np.array([1, .95, .9], np.float32) + ring[..., None] * c
    return lay * intensity
```
**Recipe 4: volumetric god rays** (structured source -> radial zoom accumulation -> occluded by the subject alpha -> Screen)
```python
def god_rays(src, center, occluder=None, n=28, decay=0.965, spread=0.22, color=(1.0, .85, .6)):
    """src: HxW float 0..1 light mask (e.g. bright blob / window). Radial zoom accumulation toward `center` (x01,y01).
    occluder: HxW alpha of the subject; rays are removed where the subject is (so light appears BEHIND the person)."""
    h, w = src.shape; cx, cy = center[0] * w, center[1] * h
    acc = np.zeros_like(src); wgt = 1.0; tot = 0
    for i in range(n):
        s = 1.0 + spread * i / n
        M = np.array([[s, 0, cx - s * cx], [0, s, cy - s * cy]], np.float32)   # sample from farther out -> streaks point away from centre
        acc += wgt * cv2.warpAffine(src, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
        tot += wgt; wgt *= decay
    acc /= tot
    acc = gblur(acc, 1.2)
    if occluder is not None: acc *= (1 - occluder)
    return acc[..., None] * np.array(color, np.float32)

def window_source(w, h, box01=(.62, -.1, .98, .42), cols=3, rows=2, bar=0.012):
    """Bright window with mullions (what makes rays STREAKY: a blob only gives glow, shapes with gaps give rays)."""
    m = np.zeros((h, w), np.float32); x0, y0, x1, y1 = [int(v) for v in (box01[0] * w, box01[1] * h, box01[2] * w, box01[3] * h)]
    m[max(0, y0):y1, x0:x1] = 1
    for i in range(1, cols): xx = x0 + (x1 - x0) * i // cols; m[:, max(0, xx - int(bar * w)):xx + int(bar * w)] = 0
    for j in range(1, rows): yy = y0 + (y1 - y0) * j // rows; m[max(0, yy - int(bar * w)):yy + int(bar * w), :] = 0
    mm = np.zeros_like(m); mm[max(0, y0):y1, x0:x1] = 1; return m * mm
```
Use: `src=window_source(W,H); gr=god_rays(src,(.8,.08),occluder=subject_alpha,n=30,spread=.9,color=(1,.8,.5)); bg=screen(bg,gr,1.0)`
**Recipe 5: bokeh balls with proper blending** (light on black with ADD inside the layer, rim brighter than centre, power-law radii, then SCREEN onto the plate)
```python
def bokeh(w, h, cols, n=40, seed=3, rmin=0.012, rmax=0.07, intensity=0.45, zone=None, rim=0.55):
    """Physically it is LIGHT: build on black with ADD, then SCREEN onto the plate. Rim brighter than centre (cat's-eye look).
    Radius power-law (many small, few big). zone=(x0,y0,x1,y1) in 0..1 restricts where balls appear."""
    rng = np.random.default_rng(seed); layer = np.zeros((h, w, 3), np.float32); x, y = grid(w, h)
    for i in range(n):
        r = (rmin + (rmax - rmin) * rng.random() ** 2.2) * w
        z = zone or (0, 0, 1, 1); cx = rng.uniform(z[0], z[2]) * w; cy = rng.uniform(z[1], z[3]) * h
        c = hex2f(cols[rng.integers(len(cols))]); x0, x1, y0, y1 = int(max(0, cx - r - 3)), int(min(w, cx + r + 3)), int(max(0, cy - r - 3)), int(min(h, cy + r + 3))
        if x1 <= x0 or y1 <= y0: continue
        d = np.hypot(x[y0:y1, x0:x1] - cx, y[y0:y1, x0:x1] - cy)
        disc = smoothstep(r + 1.2, r - 1.2, d) * (1 - rim + rim * smoothstep(r * .55, r, d))
        layer[y0:y1, x0:x1] += disc[..., None] * c * intensity * rng.uniform(.5, 1.0) * (0.6 + 0.4 * (r / (rmax * w)))
    return gblur(layer, 0.9)
```
Use: `bg=screen(bg, bokeh(W,H,["#ff3b5c","#ffb020","#3bd1ff"],n=30,seed=3,intensity=.5), 1.0)`
**Recipe 6: film grain** (band-pass, luminance-weighted with a floor, slightly chromatic; simplified from film-lab's idea; apply LAST, after any resize)
```python
def film_grain(a, amount=0.03, size=0.7, seed=0, chroma=0.25):
    """Band-pass, luminance-weighted grain (shape from thedevmark/film-lab idea, simplified). amount ~ std in 0..1 at midtones."""
    h, w = a.shape[:2]; rng = np.random.default_rng(seed)
    def field():
        n = rng.standard_normal((h, w)).astype(np.float32); n = gblur(n, size) - gblur(n, size * 4); return n / (n.std() + 1e-6)
    mono = field(); out = a.copy(); L = luma(a); wt = 0.31 + 0.69 * np.clip(4 * L * (1 - L), 0, 1) ** 1.65
    for c in range(3):
        n = (1 - chroma) * mono + chroma * field(); out[..., c] += n * amount * wt
    return np.clip(out, 0, 1)
```
**Recipe 7: halftone / comic dots** (rotated-grid distance field; `field01` = ink amount, e.g. a radial burst; tint a darker colour of the plate and `lerp` at 0.4-0.55)
```python
def halftone_dots(w, h, field01, cell=11, angle=45, color=(1, 1, 1), gain=0.9):
    """field01: HxW 0..1 'ink amount' (e.g. radial burst falloff). Returns RGBA-ish: (mask HxW). Dot radius ~ sqrt(ink)."""
    x, y = grid(w, h); t = math.radians(angle); u = x * math.cos(t) + y * math.sin(t); v = -x * math.sin(t) + y * math.cos(t)
    fu, fv = (u / cell) % 1 - .5, (v / cell) % 1 - .5
    d = np.hypot(fu, fv); ink = gblur(field01.astype(np.float32), cell * .6)
    r = 0.5 * np.sqrt(np.clip(ink, 0, 1)) * 1.25 * gain
    aa = 1.2 / cell
    return smoothstep(r + aa, r - aa, d)
```
**Recipe 8: manga speed lines** (angular random threshold x radial ramp; white at 0.5-0.75 over a darkened plate)
```python
def speed_lines(w, h, center=(.5, .5), n=200, inner=0.28, seed=5, density=0.5, sharp=0.04):
    rng = np.random.default_rng(seed); x, y = grid(w, h)
    th = (np.arctan2(y - center[1] * h, x - center[0] * w) / (2 * math.pi)) % 1.0
    vals = rng.random(n + 1).astype(np.float32); vals[-1] = vals[0]
    # a second octave so line widths vary
    v = np.interp(th * n, np.arange(n + 1), vals)
    lines = smoothstep(1 - density, 1 - density + sharp * 4, v) * smoothstep(0.0, 1.0, v)
    r = np.hypot((x - center[0] * w), (y - center[1] * h)) / math.hypot(w, h)
    ramp = smoothstep(inner * .6, inner * 1.4, r)
    return (lines * ramp).astype(np.float32)
```
**Recipe 9: sparkle stars** (core + exponential 4-point cross + faint 45-degree cross; LIGHT layer, screen it)
```python
def sparkles(w, h, pts, color=(1, 1, 1), arm=0.05):
    """pts=[(x01,y01,size01)] -> LIGHT layer. 4-point star = thin cross with exponential arms + soft core (+ small 45deg cross)."""
    lay = np.zeros((h, w), np.float32); x, y = grid(w, h)
    for (px, py, s) in pts:
        R = s * w; dx, dy = x - px * w, y - py * h
        core = np.exp(-(dx ** 2 + dy ** 2) / (2 * (R * .16) ** 2))
        a1 = np.exp(-np.abs(dx) / (R * 1.0)) * np.exp(-(dy / (R * .06 + .6)) ** 2)
        a2 = np.exp(-np.abs(dy) / (R * 1.0)) * np.exp(-(dx / (R * .06 + .6)) ** 2)
        u, v = (dx + dy) / 1.414, (dx - dy) / 1.414
        a3 = (np.exp(-np.abs(u) / (R * .45)) * np.exp(-(v / (R * .04 + .5)) ** 2) + np.exp(-np.abs(v) / (R * .45)) * np.exp(-(u / (R * .04 + .5)) ** 2)) * .35
        lay += core * 1.2 + a1 + a2 + a3
    return lay[..., None] * np.array(color, np.float32)
```
**Recipe 10: sunburst / radial burst, duplicate-and-blur background**
```python
def sunburst(w, h, center=(.72, .45), n=14, rot=0.0, soft=0.02, falloff=1.1):
    """n alternating wedges from `center`, soft edges, fading outward. Returns 0..1 mask -> tint with a light colour and screen/soft-light."""
    x, y = grid(w, h); th = (np.arctan2(y - center[1] * h, x - center[0] * w) + rot) % (2 * math.pi)
    m = smoothstep(-soft * 8, soft * 8, np.sin(th * n))
    r = np.hypot(x - center[0] * w, y - center[1] * h) / math.hypot(w, h)
    return (m * np.clip(1.15 - r * falloff * 1.6, 0, 1) ** 1.2).astype(np.float32)

def dup_blur_bg(frame, w, h, zoom=1.12, sigma=14, dark=.8, tint="#101a4a", tint_amt=.25):
    """'Duplicate and blur': same frame scaled up, heavy blur, darken, tint -> context stays (colours/shapes) but detail is gone."""
    a = to_f(cover(frame, int(w * zoom), int(h * zoom))); a = a[(a.shape[0] - h) // 2:(a.shape[0] - h) // 2 + h, (a.shape[1] - w) // 2:(a.shape[1] - w) // 2 + w]
    a = gblur(a, sigma * w / 640) * dark; return lerp(a, multiply(a, np.broadcast_to(hex2f(tint), a.shape) * 2.2), tint_amt)
```
**Lighting, grading and finishing helpers**
```python
def vignette(a, strength=0.45, power=2.2, center=(.5, .5)):
    h, w = a.shape[:2]; x, y = grid(w, h)
    d = np.hypot(x / w - center[0], (y / h - center[1]) * 0.9) / 0.75
    m = 1 - strength * np.clip(d, 0, 1.4) ** power
    return a * m[..., None]

def scrim(a, box01, strength=0.55, feather=0.12, color=(0.02, 0.02, 0.05)):
    """Soft dark rounded-rectangle behind the headline: darkens + keeps hue (multiply-ish)."""
    h, w = a.shape[:2]; m = np.zeros((h, w), np.float32)
    x0, y0, x1, y1 = [int(v) for v in (box01[0] * w, box01[1] * h, box01[2] * w, box01[3] * h)]
    m[y0:y1, x0:x1] = 1; m = gblur(m, feather * w) ; m = np.clip(m / max(m.max(), 1e-6), 0, 1) * strength
    return lerp(a, np.array(color, np.float32), m)

def radial_light(w, h, center, radius, color, power=1.6):
    x, y = grid(w, h); d = np.hypot(x - center[0] * w, y - center[1] * h) / (radius * w)
    return (np.clip(1 - d, 0, 1) ** power)[..., None] * hex2f(color) if isinstance(color, str) else (np.clip(1 - d, 0, 1) ** power)[..., None] * np.asarray(color, np.float32)

def split_tone(a, shadow="#0b2a5b", highlight="#ffb36b", amount=0.5, balance=0.5):
    """gradient-map style: luminance picks between shadow tint and highlight tint, SOFT-LIGHT/mix over original."""
    L = luma(a); t = smoothstep(0.0, 1.0, np.clip(L + (balance - .5), 0, 1))[..., None]
    tint = hex2f(shadow) * (1 - t) + hex2f(highlight) * t
    return lerp(a, soft_light(a, tint) * 1.0, amount)

def gradient_map(a, stops):
    """stops=[(pos, '#hex'), ...] ascending; maps luminance through the ramp (Photoshop Gradient Map)."""
    L = np.clip(luma(a), 0, 1); pos = [s[0] for s in stops]; cols = np.stack([hex2f(s[1]) for s in stops])
    return np.stack([np.interp(L, pos, cols[:, c]) for c in range(3)], -1).astype(np.float32)

def cover(im, w, h):
    s = max(w / im.width, h / im.height); im = im.resize((int(im.width * s + .5), int(im.height * s + .5)), Image.LANCZOS)
    l, t = (im.width - w) // 2, (im.height - h) // 2; return im.crop((l, t, l + w, t + h))

def s_curve(a, k=0.35):
    """Contrast S-curve around 0.5 (k 0..1)."""
    return np.clip(0.5 + (a - .5) * (1 + k) - k * (a - .5) ** 3 * 4, 0, 1)

def saturate(a, f=1.2):
    L = luma(a)[..., None]; return np.clip(L + (a - L) * f, 0, 1)

def depth_blur(a, focus_box01, sigma=3.0):
    """Blur everything outside the focus box (feathered) - cheap fake depth-of-field for a busy photo plate."""
    h, w = a.shape[:2]; m = np.zeros((h, w), np.float32)
    x0, y0, x1, y1 = [int(v) for v in (focus_box01[0] * w, focus_box01[1] * h, focus_box01[2] * w, focus_box01[3] * h)]
    m[y0:y1, x0:x1] = 1; m = gblur(m, w * .06); b = gblur(a, sigma); return lerp(b, a, m)

def light_wrap(fg_rgb, fg_alpha, bg_rgb, radius=10, strength=.55):
    """Cut-out feels INSIDE the scene: background light bleeds onto the subject's edge (Photoshop 'light wrap')."""
    band = gblur(1 - fg_alpha, radius * .5) * fg_alpha                         # inside-edge band
    band = band / max(band.max(), 1e-6)
    wrap = gblur(bg_rgb, radius * 1.5) * band[..., None]
    return screen(fg_rgb, wrap, strength)

def dominant_hue(rgb01, alpha=None, smin=0.25):
    hsv = cv2.cvtColor((rgb01 * 255).astype(np.uint8), cv2.COLOR_RGB2HSV).astype(np.float32)
    wt = (hsv[..., 1] / 255 > smin) * (hsv[..., 2] / 255 > .2);
    if alpha is not None: wt = wt * (alpha > .5)
    ang = hsv[..., 0] * 2 * math.pi / 180   # OpenCV hue 0..180
    if wt.sum() < 10: return None
    return (math.degrees(math.atan2((np.sin(ang) * wt).sum(), (np.cos(ang) * wt).sum())) % 360)

def hsv_hex(h, s, v):
    c = cv2.cvtColor(np.uint8([[[h / 2, s * 255, v * 255]]]), cv2.COLOR_HSV2RGB)[0, 0]; return "#%02x%02x%02x" % tuple(int(i) for i in c)
```
**Recipe 11: real-photo plate + procedural lighting** (`photo_relight2`) and **Recipe 12: post-pass for our flat vector plates** (`upgrade_plate2`)
```python
def photo_relight2(photo, w, h, warm="#ff7a2a", cool="#2a7bff", warm_pos=(.0, .75), cool_pos=(1.0, .1), seed=0, grain=.016, vig=.4, focus=None, blur=2.5):
    a = to_f(cover(photo, w, h))
    a = lerp(a, luma(a)[..., None].repeat(3, -1), .15)                          # mild desat only
    a = np.clip(a, 0, 1) ** 1.12                                              # mild darken
    if focus is not None: a = depth_blur(a, focus, blur)                      # photo plates: soften what is not the hero zone
    a = screen(a, radial_light(w, h, warm_pos, .7, warm, 1.4), .7)             # coloured LIGHT, screen, opposite corners
    a = screen(a, radial_light(w, h, cool_pos, .6, cool, 1.4), .6)
    a = split_tone(a, "#0a1f55", "#ffa860", .30, .5)
    hi = np.clip(luma(a) - .6, 0, 1)[..., None] * a; a = add(a, gblur(hi, w * .02), .8)
    a = screen(a, bokeh(w, h, [warm, cool, "#ffffff"], 14, seed, intensity=.28), .9)
    a = s_curve(a, .35); a = saturate(a, 1.18)
    a = vignette(a, vig)
    return film_grain(a, grain, .7, seed)

def upgrade_plate2(plate, w, h, seed=0, warm="#ff6a2a", cool="#2a8bff", texture=.10, grain=.016, vig=.4, rays=True):
    a = to_f(cover(plate, w, h)); a = np.clip(a, 0, 1) ** 1.12
    tex = .6 * fbm(w, h, w / 3, 4, seed) + .4 * fbm(w, h, w / 14, 3, seed + 5)
    a = lerp(a, soft_light(a, np.repeat(tex[..., None], 3, -1)), texture)
    hi = np.clip(luma(a) - .5, 0, 1)[..., None] * a; a = add(a, gblur(hi, w * .015), .9)
    a = screen(a, light_leaks(w, h, (warm, "#ff3d7a"), 2, seed + 3), .5)
    if rays: src = window_source(w, h, (.55, -.15, .95, .3)); a = screen(a, god_rays(src, (.75, .08), n=26, spread=.8, color=(1, .8, .55)), .5)
    a = screen(a, bokeh(w, h, [warm, cool, "#ffffff"], 12, seed, intensity=.25), .9)
    a = s_curve(a, .3); a = saturate(a, 1.1); a = vignette(a, vig)
    return film_grain(a, grain, .7, seed)
```
Use: `out = to_im(photo_relight2(Image.open(photo), 1280, 720, warm="#ff7a2a", cool="#2a7bff", focus=(.35,0,.75,1)))`; add `light_wrap(subject_rgb, subject_alpha, bg_rgb)` when compositing the cut-out. Complement-hue palette: `hue=dominant_hue(subject_rgb, alpha); comp=(hue+180)%360; dark=hsv_hex(comp,.85,.30); accent=hsv_hex((comp+25)%360,.9,.75)` (test: orange astronaut suit hue 17 -> complement 197 -> `#0e4559` dark, `#17aee5` accent; the composite gave clear separation, though my chosen value .30 looked dull: raise accent value/saturation).
Known caveats from my tests: `upgrade_plate2` washes out already-bright plates (airport): add an exposure guard (if mean luma >0.5, raise gamma to ~1.4 and halve the screen layers). Blends here are in sRGB-encoded space (Photoshop-style); physically correct light addition should be in linear light (film-lab does halation in linear); I did not compare, and at thumbnail strengths the difference is small.

### Gaps
- Not run: notion-bg-gen, film-lab, pilgram code itself (read only). Output of those repos not rendered. Chromatic aberration, confetti, rain, neon-outline, wet-floor reflection recipes not implemented. Real rembg portraits (hair, hands) not tested with `light_wrap`/occluded rays; the astronaut GrabCut matte is rough. No 1280x720 visual check beyond timing. GPU/AI-based backgrounds are out of scope here (see free-image-API note).

---

## Q5. Claude/agent SKILLS and knowledge packs worth copying into the repo

### Takeaway
No skill found teaches raster background craft (light, grade, bokeh); the useful ones are (a) colour science, (b) thumbnail-composition rules, (c) generic design critique. Best copy candidates: meodai color-expert (CC-BY-4.0, with attribution) for colour-space rules, Albisourous mrbeast-thumbnail-skill (MIT) for lighting/colour rules and a phone-preview script, and the earlier-reviewed jsath/ArnavPuri skills (MIT). Copy ideas, not scripts; never run downloaded scripts without review.

### Cited Findings
| Skill / pack | Licence | What I read | Useful content for backgrounds | Notes |
|---|---|---|---|---|
| [meodai/skill.color-expert](https://raw.githubusercontent.com/meodai/skill.color-expert/main/SKILL.md) (656 stars, pushed 2026-10-21) | CC-BY-4.0 (spdx from GitHub search; `LICENSE` fetched 200 but I did not read its text; [THIRD_PARTY_NOTICES.md](https://raw.githubusercontent.com/meodai/skill.color-expert/main/THIRD_PARTY_NOTICES.md) fetched, not read) | SKILL.md (36 KB, top ~250 lines) and `references/techniques/glsl-lut-color-grading.md` | OKLCH/OKLab for perceptual mixing and gradients ("No mid-gradient darkening like RGB/HSL"); "Reduce chroma, not lightness or hue" when out of gamut; hue ranges table (red 345-15, orange 15-45, yellow 45-70, green 70-165, cyan 165-195, blue 195-260, purple 260-310, pink 310-345); "hue-first harmony (complementary, triadic) is a weak standalone heuristic" and "hue is usually a weaker predictor of emotional response than chroma and lightness"; LUT grading idea (per-pixel colour map baked into a texture; cannot do blur) | UI/web-oriented; 180+ reference files not read. Attribution required if text is copied. |
| [Albisourous/mrbeast-thumbnail-skill](https://raw.githubusercontent.com/Albisourous/mrbeast-thumbnail-skill/main/README.md) (1 star, pushed 2026-11-02) | MIT ([LICENSE](https://raw.githubusercontent.com/Albisourous/mrbeast-thumbnail-skill/main/LICENSE)) | README, packaging-rules.md (grep'd sections), image-prompts.md, SKILL.md fetched | "Blur, darken, or crop everything else", 1-2 hero colours on complementary background, colour table (cyan/teal vs orange for contrast; white on saturated red for alarm), prompt skeleton with rim light/radial glow; Pillow script crops, strokes text, makes a phone-size preview; `feed.py` mocks a phone feed to compare thumbnails | Latin-text oriented; scripts not run. Cites MrBeast "leaked handbook" and blog sources (secondary). |
| [calebvbi/creator-skills-samples ai-thumbnail-factory](https://raw.githubusercontent.com/calebvbi/creator-skills-samples/main/skills/ai-thumbnail-factory/SKILL.md) | front-matter says CC BY 4.0; repo `LICENSE` 404 (so unclear) | SKILL.md (27 KB, grep'd for background/colour/gaming lines) | Archetype list; reaction-background prompt; gaming palette line; "Use a DIFFERENT primary color than the top 3 competitors" | Marketing-style; ask-the-user workflow does not fit an automatic pipeline. |
| [wundercorp/gradient-mesh-skill](https://raw.githubusercontent.com/wundercorp/gradient-mesh-skill/main/SKILL.md) | MIT | full SKILL.md head | 2-5 stops, keep text on solid/blurred/translucent surfaces, avoid busy texture behind text, avoid oversaturated contrast fighting CTAs | Web-only. Python pointer is numerical, not graphic (see Q4). |
| [djsbaker/design-principles-skill](https://raw.githubusercontent.com/djsbaker/design-principles-skill/main/README.md) | MIT | README only | 6 reference files (colour 60/30/10, contrast and hierarchy, balance), "AI design tells" checklist (purple-blue gradients, etc.) | HTML/CSS static composition; SKILL.md and references not read. |
| iart-ai/motion-design-skills (231 stars, MIT), obaidr1/color-theory-ui-skill (MIT), projectnamedate/color-theory-skill (no licence) | MIT / MIT / none | listing + README skimmed only (not read in depth) | motion = irrelevant to stills; colour-theory skills are UI palettes (60-30-10, WCAG) | Do not copy projectnamedate (no licence). |
| jsath/claude-skills thumbnail-generator, ArnavPuri/designskills, sergebulaev/youtube-skills, AgriciDaniel/claude-youtube, kangarooking cover-skill, anthropics/skills | MIT, MIT, MIT, MIT, none, Apache-2.0 | read by an earlier researcher | composition, 168 px previews, QA gates | See [design_skills_review.md](file:///home/user/oded-highlights/research_notes/Oded%20highlights%20pipeline%20upgrade/design_skills_review.md); not re-read. |
Also: [pbakaus/impeccable](https://github.com/pbakaus/impeccable) appears (named in the design-principles README) as a larger design toolkit with a CLI and 62 deterministic detector rules; I did not read it (CLI, web-UI oriented).

### Inferences
- Copy-ready knowledge into a repo doc (not the skill files wholesale): (1) colour rules from color-expert (OKLab mixing, chroma vs lightness, hue table); (2) mrbeast-skill lighting skeleton and the `feed.py` idea (our own 168 px feed mock: put 12 candidate thumbnails in a 3x4 grid at 168x94, pick the one that reads); (3) the "AI design tells" list as a negative checklist for our plates (purple-blue gradient wash = generic).
- Safest licence path: MIT/Apache items can be adapted with a notice; CC-BY needs attribution; no-licence items (kangarooking, ComposioHQ, projectnamedate, python-halftone) should be re-expressed in our words, not copied.

### Gaps
- Skill registries (bergside, ComposioHQ, VoltAgent, etc.) not audited; skills.sh and others unreachable/not tried. I found no skill on lighting, bokeh, flares or grading for raster work.

---

## Q6. Prioritised 10 changes (impact / effort), with a way to blend a real-photo plate with procedural lighting

### Takeaway
Fastest visible gains: (1) always run a finishing pass over plates (texture, bloom, light, bokeh, vignette, grain), (2) stop relying on flat vector plates: use the stream's own frame or a photo through a grade + coloured Screen lights, (3) choose the plate palette from the subject's complement and enforce a luminance hierarchy. All of it is under ~250 lines of numpy and under 1 s per frame at 1280x720.

### Cited Findings
- Evidence base for the list: Q1 (expert stack, our plates' defects), Q2 (reaction pattern), Q4 (tested recipes and timings).
- Existing pipeline facts (read): `scripts/thumb_maker.py` has `finish(img, vignette=0.78, grain=2.2, s_curve=0.12, clarity=0.35)` (line 224: S-curve, clarity via 40 px blur, vibrance, vignette, Gaussian grain of 2.2/255 std, i.e. about 0.009), and `scripts/thumb_call.py` line 96 calls `T.finish(out)` on the finished composite; so a global final grade exists on that path, but nothing lights or textures the PLATE before the subject is composited. `art_background`/`background` darken horizontally only (per the earlier note, [thumbnail_finishing_techniques.md](file:///home/user/oded-highlights/research_notes/Oded%20highlights%20pipeline%20upgrade/thumbnail_finishing_techniques.md) Q8, which says no global grade exists in the other `make/scene_mode/react_mode` paths). Files: [scripts/thumb_maker.py](file:///home/user/oded-highlights/scripts/thumb_maker.py), [scripts/thumb_call.py](file:///home/user/oded-highlights/scripts/thumb_call.py).

### Inferences (proposals; ordered by impact / effort, 1 = do first)
1. **Plate finishing pass for every plate (impact high, effort S, ~1 hour).** Run BEFORE the subject is composited (the existing `finish()` then still runs once on the whole frame; drop the plate's own grain/vignette if `finish()` already adds them, to avoid double grain). Add `upgrade_plate2` (texture, bloom from highlights, leaks, window rays, rim-bokeh, S-curve, saturation, vignette, grain) as the last step of plate loading, with an exposure guard for bright plates. 0.16 s at 640, 0.72 s at 1280.
2. **Real-photo plate + procedural lighting (impact very high, effort S-M).** Plate source order: stream frame (`dup_blur_bg`), licensed stock photo, AI scene. Pipeline = `cover` -> mild desaturate .15 -> gamma 1.12 -> optional `depth_blur` outside the hero zone -> coloured light as Screen (warm radial at the side opposite the cool one; 0.7/0.6) -> split-tone 0.3 -> highlight bloom -> rim-bokeh -> S-curve 0.35 + saturation 1.18 -> vignette -> grain. That is exactly `photo_relight2`. Keep the photo's real shadows/highlights (do not flatten) so lights from the photo and our procedural colour agree; if the photo has a visible light direction, put the warm light on that side.
3. **Subject-driven palette (impact high, effort S).** `dominant_hue(subject, alpha)` -> background key = complement (dark, saturated) + accent = analogous-to-complement (bright). Warm/cool split as in Taklipu. Reject palettes where key and subject luminance differ by < 25 points.
4. **Replace opaque cones/discs with additive light (impact high, effort S).** In `thumb_plates*.py`, change spotlight cones, rays and bokeh to light layers added in Screen/Add; use `window_source` + `god_rays` for beams, rim-bokeh for balls.
5. **Light integration of the cut-out (impact high, effort S).** `light_wrap` + rim light in the plate's accent colour + back glow behind the head (the existing finishing note has rim/AO/stroke recipes; this adds the plate-derived colour and wrap). Tested: subtle but visible edge colour.
6. **Headline zone scrim and vignette centred on the face (impact medium-high, effort XS).** `scrim(box, 0.45)` under the headline (soft feathered box) instead of busy plate behind text; `vignette(a, .4, center=face)`.
7. **Luminance-hierarchy QA at 168x94 (impact medium, effort S).** Downscale each result; require: face region brightest and most saturated; subject-zone plate mean luma 0.15-0.35 (Taklipu's median over the full frame is 0.41); luminous accent peak present; plate mean luma < 0.5 pre-effects (airport case). Auto-retry with a different seed/palette.
8. **Strip baked text and UI from plates (impact medium, effort XS).** `jewellery_store.jpg` contains "JEWELRY" in a box; our overlay language is Hebrew. Only code adds text.
9. **Topic motif library, one per thumbnail (impact medium, effort M).** Add the topic-table ingredients: sparkles (heist/vault/food), speed lines + embers (rage), sunburst (quiz/birthday), halftone dots (tech/dating), neon outline (studio), steam fbm (food), confetti (birthday). Rule: one hero motif + one supporting light.
10. **Plate bank and variation by seed (impact medium, effort S-M).** Generate 4-6 variants per topic per run (palette jitter, light positions, bokeh seed), score with item 7, keep the best; also cache the best per topic to keep the channel consistent (brand colour = fixed accent + fixed grain/vignette + fixed type colours while the key hue changes per topic).
Brand-consistency suggestion (inference, unsourced): keep the same grade/grain/vignette/headline treatment on every thumbnail and vary only the topic palette, so the feed looks like one channel.
- Concerning the grading strength: my own first heavy settings made photos worse than raw; start from the "v2" numbers and A/B on the owner's eye before tuning.

### Gaps
- Not tested on real rembg portraits; stock-photo sourcing host reachability unverified; no CTR measurement; the exposure guard and the luminance thresholds in item 7 are proposals not tested; Taklipu-like full-scene generation (portrait + scene as one image) remains the strongest option and depends on the image tool covered in the free-image-API note.

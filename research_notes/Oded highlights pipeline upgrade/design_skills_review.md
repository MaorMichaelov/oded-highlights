# Design skills and design-knowledge packages for the ODED HIGHLIGHTS thumbnail pipeline (review, 14 Nov 2026)

Method and limits (read first)
- Reachable: github.com search through `gh api search/...` (repositories and code search worked) and `raw.githubusercontent.com` (worked for every public repo tried). `gh api repos/...` and the git-tree API were REFUSED for repos not attached to the session ("GitHub access to this repository is not enabled"), so full directory listings of anthropics/skills and of the other skill repos could NOT be read; file lists below come from code search or from README text and may be incomplete. Other hosts (skills.sh, typeui.sh, agentskills.io, vidiq etc.) were not tried: the brief says they fail DNS, and everything here comes from GitHub only.
- "VERIFIED" = I downloaded and read the file (raw GitHub, 14 Nov 2026). "CLAIMED" = repo description/README/star counts or a statement I could not check. Nothing was installed, no downloaded script was executed (only read, plus grep for network/exec calls). Downloads sit in the session scratchpad, not in the repo.
- Read in the repo (VERIFIED): scripts/thumb_maker.py (328 lines), docs/THUMBNAIL_STYLE_BIBLE.md, docs/THUMBNAIL_BRIEF.md, head of research_notes/.../thumbnail_style_bible_scoring.md (another researcher covers CTR evidence, prompts and the CPU scorer; not repeated here). Environment check (VERIFIED, run here): Pillow 12.3.0 with raqm, fribidi and harfbuzz all True; Heebo variable font present (fc-list).
- No Taklipu thumbnails were available to me; "Taklipu look" claims come from the owner's description in the repo docs.
- Honest headline: NO skill found contains raster-compositing craft (rim light, light wrap, grading, glow, texture). The skills are either web-UI design, abstract art, or YouTube marketing briefs. The concrete techniques in section 3 are my own engineering design knowledge applied to the code I read; they are inferences to validate, not quotes from any skill.

---

## 1. Which skills exist and which are relevant to raster thumbnail design

### Takeaway
Of ~25 skills inspected, four are worth reading for thumbnail work (jsath thumbnail-generator, ArnavPuri thumbnail-design plus design-critique, sergebulaev yt-thumbnail-brief/principles, kangarooking cover-skill for ideas only); Anthropic's own design skills (canvas-design, frontend-design, theme-factory, brand-guidelines, algorithmic-art, slack-gif-creator) are mostly irrelevant to thumbnails, with frontend-design's critique loop the only transferable part.

### Cited Findings

Ranked list (relevance to a Pillow thumbnail pipeline, then quality):

**Rank 1. jsath/claude-skills `skills/video/thumbnail-generator` (MIT, (c) johannships, 18 stars, pushed 2026-10-27)** — closest match: "image models make the plate, code makes the words", Pillow compositor with automatic QA and 320 px / 168 px previews. Contents read: SKILL.md (6 KB), references/composition.md, references/reference-matching.md, scripts/compose_thumbnail.py (138 lines, local-only, imports argparse/json/os/sys/PIL). — [SKILL.md](https://raw.githubusercontent.com/jsath/claude-skills/main/skills/video/thumbnail-generator/SKILL.md), [composition.md](https://raw.githubusercontent.com/jsath/claude-skills/main/skills/video/thumbnail-generator/references/composition.md), [compose_thumbnail.py](https://raw.githubusercontent.com/jsath/claude-skills/main/skills/video/thumbnail-generator/scripts/compose_thumbnail.py), [LICENSE](https://raw.githubusercontent.com/jsath/claude-skills/main/LICENSE)
  Quotable rules (VERIFIED in SKILL.md/composition.md):
  - "Hierarchy: face > headline > logo > background." and "Everything is too small. Make elements 30 to 50% bigger than feels right; most people see 168 px wide."
  - Cutout `height` 0.85 to 0.95 of frame, flush with the bottom, never under 70%; headline size 110 to 140 px, second line 60 to 80 px at 1280x720; outline around cutout 6 to 10 px (white on dark plates, black on light).
  - "If it looks big enough at full size, it is too small at 168 px." Preview shows 1280, 320 and 168 px.
  - "Do not upscale a cutout more than about 1.15x (the script warns): find a bigger source." (our enhance() upscales a low-res facecam crop to ~H*1.02; this rule says that will look soft).
  - "Duplicated or mirrored elements look cheap"; "Each new thumbnail looks different from the channel's last few."; "Nothing covers the face."
  - Layer order (bottom to top): plate, darken overlay, logos, text blocks, cutout (face on top).
  - Script checks: text/logo leaving frame, text overlapping the cutout's real alpha pixels (not just the bbox), text-block overlap, more than 5 words, cutout under 70% height.
  Mismatch with our style: its text style is solid colour blocks with Impact/Arial (Latin); ours is stroked Heebo Black with gradient. Hebrew shaping is not handled (no direction="rtl"). Take the checks and size table, not the text renderer.

**Rank 2. ArnavPuri/designskills (MIT, 19 stars, pushed 2026-09-28): `thumbnail-design`, `design-critique`, `layout-composition`, `typography`, `color-palette`, `image-treatment`** — a 29-skill suite; thumbnail-design is the relevant one. — [thumbnail-design](https://raw.githubusercontent.com/ArnavPuri/designskills/main/skills/thumbnail-design/SKILL.md), [design-critique](https://raw.githubusercontent.com/ArnavPuri/designskills/main/skills/design-critique/SKILL.md), [LICENSE](https://raw.githubusercontent.com/ArnavPuri/designskills/main/LICENSE)
  Quotable rules (VERIFIED, thumbnail-design):
  - "Maximum 5-7 words of text; font size minimum 60px at 1280x720; No thin fonts -- use bold or black weights only."
  - "The Three-Element Maximum": face/focal image, bold text (2-5 words), one supporting visual.
  - Reaction layout: "Face/headshot: 60% of frame... 2-3 words of text on the opposite side... Colored border or glow behind the face to separate from background."
  - Overlay zones: keep "bottom-right (duration badge), red watch-progress bar along the bottom edge, and top-right hover icons" clear.
  - "Colors are distinct from platform UI (avoid pure white or YouTube red)" (relevant: our ribbon is (210,25,25), close to YouTube red).
  - Glow ring behind the face: radial gradient at 0.4 alpha of the primary colour, drop-shadow 30 px at 0.6.
  - Text: stroke 3 px at 80 px size + hard shadow 4px 4px + soft 20 px shadow; angled highlight bar skewX(-5deg).
  - Procedure: Read the output PNG, then shrink to 168x94 with Pillow and Read that too: "Text must still be readable and the face expression visible."
  - design-critique: for static images "estimate contrast by sampling pixel colors with Pillow and the WCAG formula"; hierarchy checklist (one focal point, size contrast, colour contrast, weight contrast); text on images must meet 3:1 for large text "against the lightest pixels behind it" (image-treatment).
  Weaknesses: CSS-centric, generation path assumes Gemini via a script needing GEMINI_API_KEY; frontend-oriented critique script uses Playwright.

**Rank 3. sergebulaev/youtube-skills `skills/yt-thumbnail-brief` + `references/thumbnail-principles.md` (MIT, 99 stars, pushed 2026-11-11)** — a brief writer, not a renderer. — [principles](https://raw.githubusercontent.com/sergebulaev/youtube-skills/main/references/thumbnail-principles.md), [skill](https://raw.githubusercontent.com/sergebulaev/youtube-skills/main/skills/yt-thumbnail-brief/SKILL.md)
  Quotable (VERIFIED):
  - "High contrast and separation. The subject must pop off the background. Use a rim light, a blurred or darkened background, or a bold color the competitors are not using."
  - "Foreground / background depth. A sharp subject on a softened background creates the separation that survives shrinking."
  - "Color contrast over color matching... Reds, yellows, and cyans pop; muted earth tones disappear in the feed."
  - "Rule of thirds... text on the opposite side. A centered face with text underneath reads as a template." "Direction of gaze. A subject looking at the text or the object pulls the viewer's eye there too."
  - "Close crop: eyes and mouth are the signal. A tiny face in a wide shot loses at 120 px." "One emphasized word in a contrasting color is a strong pattern."
  - Conflicts with our house style: "3 to 4 words maximum", "never the same words as the title", "no punctuation in overlay text" (our headlines include "!" and Latin tokens such as "GTA 6!"). Also its repo is built around Publora auto-publishing (lib/publora_client.py, lib/approval.py) which we do not want.

**Rank 4. AgriciDaniel/claude-youtube (MIT, 768 stars, pushed 2026-04-10) `sub-skills/thumbnail.md`, `references/thumbnail-ctr-guide.md`** — also a brief writer (focal point, expression, text, palette hex roles, composition, depth, 168x94 check, 3 A/B variants). Useful template headings ("Depth: foreground/background relationship, blur", "Remove at small size"). Its numbers (+20-30% CTR for faces, "30-40% negative space", niche CTR table) are second-hand vendor figures and conflict with the more careful evidence already in thumbnail_style_bible_scoring.md; treat as weak. Sub-skill optionally calls a NanoBanana MCP and DataForSEO (needs keys). — [thumbnail.md](https://raw.githubusercontent.com/AgriciDaniel/claude-youtube/main/skills/claude-youtube/sub-skills/thumbnail.md), [ctr guide](https://raw.githubusercontent.com/AgriciDaniel/claude-youtube/main/skills/claude-youtube/references/thumbnail-ctr-guide.md)

**Rank 5 (ideas only, do not copy). kangarooking/kangarooking-skills `cover-skill` (750 stars, NO licence file: raw LICENSE 404, GitHub spdx null, pushed 2026-11-04)** — personal-brand cover system for a Chinese creator, very strict. Transferable ideas (VERIFIED in core-rules.md, qa.md, SKILL.md):
  - Compositing rule: image model makes scene "without final ... copy when possible. Add exact title ... afterward with deterministic compositing." (same as our architecture).
  - Layer/face model: background, rear text, product, subject cut-out, foreground text, contrast treatments, then a "face exclusion mask protecting facial features across all layers"; typography "may surround the subject or pass behind hair, shoulders, arms ... provided the word remains unmistakable"; overlap "approaching roughly 18% usually deserves redesign".
  - Process: four concepts then pick; contact sheet and target-size thumbnails inspected with an image viewer; a hard-gate PASS/FAIL table per output; "Manifest booleans alone are never sufficient." Because it has no licence, copying is not allowed; re-express the ideas in our own words. — [SKILL.md](https://raw.githubusercontent.com/kangarooking/kangarooking-skills/main/cover-skill/SKILL.md), [core-rules](https://raw.githubusercontent.com/kangarooking/kangarooking-skills/main/cover-skill/references/core-rules.md), [qa](https://raw.githubusercontent.com/kangarooking/kangarooking-skills/main/cover-skill/references/qa.md)

**Rank 6. anthropics/skills (README says many skills Apache-2.0; per-skill LICENSE.txt are Apache 2.0, VERIFIED for canvas-design, frontend-design, slack-gif-creator)** — [README](https://raw.githubusercontent.com/anthropics/skills/main/README.md)
  - `frontend-design` (9.4 KB): web UI. Transferable: plan then "review that plan against the brief" and revise if it "reads like the generic default"; "Spend your boldness in one place. Let one element be the memorable thing, keep everything around it quiet and disciplined"; "Critique your own work as you build, taking screenshots to review"; "Chanel ... remove one accessory". It also lists AI "tells" including "Accenting just a single word or phrase in a headline" (conflicts with our deliberate white-plus-yellow headline convention; ignore that item). — [SKILL.md](https://raw.githubusercontent.com/anthropics/skills/main/skills/frontend-design/SKILL.md)
  - `canvas-design` (11.9 KB): produces abstract museum-style PNG/PDF "90% visual design, 10% essential text", "Most of the time, font should be thin", "nothing overlaps", looks for `./canvas-fonts`. Opposite of thumbnail needs (heavy type, one literal story). Only reusable lines: "Take a second pass ... refine what has been created rather than adding more graphics" and "nothing falls off the page ... breathing room". Not recommended. — [SKILL.md](https://raw.githubusercontent.com/anthropics/skills/main/skills/canvas-design/SKILL.md)
  - `theme-factory` (10 preset colour/font themes for slides/docs; needs theme-showcase.pdf, which I did not read), `brand-guidelines` (Anthropic brand colours), `algorithmic-art` (p5.js generative art), `slack-gif-creator` (Pillow GIF builder with 128x128 constraints; its `core/gif_builder` is irrelevant). Not relevant to YouTube thumbnails. — [theme-factory](https://raw.githubusercontent.com/anthropics/skills/main/skills/theme-factory/SKILL.md), [slack-gif-creator](https://raw.githubusercontent.com/anthropics/skills/main/skills/slack-gif-creator/SKILL.md)
  - The `image-enhancer` entry in ComposioHQ/awesome-claude-skills (VERIFIED, 2.5 KB) is a generic prompt-only skill ("upscales ... sharpens"), no technique content; that repo has no licence (spdx null), so do not copy. — [image-enhancer](https://raw.githubusercontent.com/ComposioHQ/awesome-claude-skills/master/image-enhancer/SKILL.md)

**Other skills seen and rejected (VERIFIED by reading the file unless noted)**
  - qwwiwi/agentos-skills-public `youtube-thumbnail` (MIT, 4 stars): pipeline = gpt-image-2 via a `codex-image` skill and Codex OAuth with exactly five reference images, fallback Node/Playwright boxes script, needs `npm install -g @openai/codex`; one useful rule: "Eyes rule: only frames with fully open eyes and a direct gaze ... one half-closed eye in a reference is copied onto every cover" (relevant to choosing face reference frames). Palette fixed to author's brand. — [SKILL.md](https://raw.githubusercontent.com/qwwiwi/agentos-skills-public/main/skills/youtube-thumbnail/SKILL.md)
  - kabbajHoussine/video-editing `youtube-thumbnail` (no licence): one person's absolute-path workflow with Thumbfast CLI and Codex; also rule "Never paint, patch, or Pillow-overlay text on a final" (opposite of our approach). Rejected.
  - daiki-beppu/youtube-automation `thumbnail` (NOASSERTION licence, 169 stars): 72 KB Japanese workflow tied to that repo's CLI commands; rejected. (Only headings read.)
  - Predisai/predis-skills `thumbnail` (MIT): requires the paid Predis MCP connector and credits; prompt list item useful: "strong key light on the face, bright rim light separating subject from background, vivid saturated color, deep blacks, simple background with a soft vignette" (good line for our external scene-generator prompt). — [SKILL.md](https://raw.githubusercontent.com/Predisai/predis-skills/main/skills/thumbnail/SKILL.md)
  - pablostanley/efecto-plugin `graphic-design` (no licence): drives a hosted "Efecto" MCP design tool; rejected. Conava/claude-devline `graphic-design`: logos, banners, slides; not thumbnails.
  - Hebrew: skills-il/localization `hebrew-rtl-best-practices` (MIT, 26 stars) and yodem/hebrew-book-producer `hebrew-typography` (MIT) are web-CSS and book-typesetting (Frank Ruhl Libre, margins) respectively; neither covers display type in raster images. Only transferable fact: Hebrew has no letter case, so `text-transform` and "all caps" tricks do not apply; "Nikkud and cantillation marks need vertical room" (tight line-height clips them); numbers and Latin inside Hebrew need bidi care. — [skills-il RTL](https://raw.githubusercontent.com/skills-il/localization/master/hebrew-rtl-best-practices/SKILL.md), [yodem](https://raw.githubusercontent.com/yodem/hebrew-book-producer/main/plugins/hebrew-book-producer/skills/hebrew-typography/SKILL.md)
  - Registries: bergside/awesome-design-skills (MIT, 3.6k stars, 67 DESIGN.md/SKILL.md brand-style files; web design systems, pulled with `npx typeui.sh` from typeui.sh, an external host, which would be remote code/content fetched at install time: skip), ComposioHQ/awesome-claude-skills (79k stars, no licence), sickn33/agentic-awesome-skills (49k stars), VoltAgent/awesome-agent-skills (37k), travisvn, BehiSecc. These are catalogues; I did not audit their 1000+ entries. — [bergside README](https://raw.githubusercontent.com/bergside/awesome-design-skills/main/README.md)
  - Other YouTube skill bundles by star count only (CLAIMED, not read): Jakeschincariol/youtube-agent-skill (5.8k stars; its yt-package skill has title.py; thumbnail content unverified), adityaarsharma/youtube-marketing-skills, TubeLabHQ/youtube-research-skills.

**Open-source thumbnail generators / libraries (borrowable code)**
  - GitHub search for Pillow/rembg/Skia/Playwright YouTube-thumbnail generators returned only tiny, unmaintained or unlicensed projects (e.g. dunossauro/ldp-thumb GPL-3.0, 2022; 2h311/Youtube-Thumbnail-Generator 2022; none above 10 stars). I found no mature open-source project to borrow from. The Playwright/HTML approach exists only inside skills (ArnavPuri render.mjs; qwwiwi yt-boxes.mjs).
  - akiomik/pilgram (Apache-2.0, 134 stars, pushed 2026-11-10): Instagram-style filters plus CSS blend modes on Pillow images (`pilgram.css.blending` offers soft_light, overlay, screen, color, multiply, etc., VERIFIED in README). Useful for colour grading and screen-blend rim light; adds a dependency (not installed here). — [README](https://raw.githubusercontent.com/akiomik/pilgram/main/README.md)
  - pashango2/Image4Layer (MIT, 2017): Pillow blend modes, unmaintained; skip. Blend modes can be written directly in numpy in ~10 lines.

### Inferences
- Because the scene is generated externally, the most valuable "skill" is a QA and brief discipline (small-size preview, face/text overlap, zones, contrast), which jsath and ArnavPuri provide, plus prompt phrases for lighting (Predis, sergebulaev). Nothing found teaches the compositing craft; we must encode that ourselves.
- Rules in these skills that contradict the Taklipu style bible (3-word titles, no punctuation, no repeated words, "avoid YouTube red", anti-single-accent-word) should be overridden by docs/THUMBNAIL_STYLE_BIBLE.md.

### Gaps
- Full file trees of anthropics/skills and the others could not be listed (API refused); canvas-design's `canvas-fonts/` and theme-factory's themes/ were not read.
- I did not read the full 52 KB efecto, 72 KB daiki, 45 KB kangarooking validate_exports.py beyond grep (imports only argparse, hashlib, json, re, sys, pathlib plus an optional import: no network or exec calls matched) and headings.
- No Hebrew-specific raster thumbnail skill exists in what I found; no skill covered rim light, light wrap or grading.
- Star counts and pushed dates are from GitHub search metadata (CLAIMED, as of 14 Nov 2026).

---

## 2. Licences and safety (scripts read)

### Takeaway
All recommended text-only skills are MIT or Apache-2.0; no script I read downloads or executes remote code, but several skills assume paid/keyed services (Gemini, Codex, Predis, Publora, DataForSEO) and two web-oriented scripts (ArnavPuri audit.mjs, render.mjs) need Playwright/npm; copy only the Markdown and the single local jsath script.

### Cited Findings
- anthropics/skills: Apache License 2.0 in skills/canvas-design/LICENSE.txt, skills/frontend-design/LICENSE.txt, skills/slack-gif-creator/LICENSE.txt (header read); the README states the repo's open-source skills are Apache 2.0 and carries a disclaimer "provided for demonstration and educational purposes only". Install route: `/plugin marketplace add anthropics/skills`, then `/plugin install example-skills@anthropic-agent-skills` (adds ~all example skills, including irrelevant ones). — [LICENSE canvas-design](https://raw.githubusercontent.com/anthropics/skills/main/skills/canvas-design/LICENSE.txt), [README](https://raw.githubusercontent.com/anthropics/skills/main/README.md)
- jsath/claude-skills: MIT. compose_thumbnail.py read in full: reads a JSON layout, opens local images, draws text, writes PNG; no subprocess, network, eval or environment reads. Hard-coded font list includes macOS/Windows Impact paths with a DejaVu fallback (on this box set "font" explicitly). — [LICENSE](https://raw.githubusercontent.com/jsath/claude-skills/main/LICENSE)
- ArnavPuri/designskills: MIT. skills/image-generation/scripts/gemini-generate.py requires `GEMINI_API_KEY`/`GOOGLE_API_KEY` and the `google-genai` package (calls Google, secret request: do not copy). skills/graphic-design/scripts/render.mjs runs `npm root -g` through execSync and needs Playwright (local only, but npm tooling). skills/design-critique/scripts/audit.mjs: per its SKILL.md it "loads axe from a CDN" unless axe-core is npm-installed (remote script load; flag; I did not read that file). contrast.py and palette.py not read beyond grep (no network hits in contrast.py). The thumbnail-design and design-critique SKILL.md files themselves are plain Markdown. — [LICENSE](https://raw.githubusercontent.com/ArnavPuri/designskills/main/LICENSE)
- sergebulaev/youtube-skills: MIT (GitHub metadata and LICENSE file exists). The Markdown brief skill is harmless; the repo also ships lib/publora_client.py and lib/approval.py for auto-publishing through a third-party API (not read; do not copy `lib/`). AgriciDaniel/claude-youtube: MIT (LICENSE exists); sub-skills call optional MCPs (NanoBanana, DataForSEO) and `execution/fetch_channel_data.py` and `search_competitor_videos.py` (network scripts, not read).
- No licence (cannot lawfully copy): kangarooking/kangarooking-skills (LICENSE 404, spdx null), ComposioHQ/awesome-claude-skills (null), pablostanley/efecto-plugin (null), kabbajHoussine/video-editing (null). NOASSERTION: daiki-beppu/youtube-automation.
- Maintenance (GitHub metadata, CLAIMED): jsath 2026-10-27, ArnavPuri 2026-09-28, sergebulaev 2026-11-11, anthropics/skills active, AgriciDaniel/claude-youtube last push 2026-04-10 (7 months stale), kangarooking 2026-11-04. All are small single-author repos except Anthropic's; treat as snapshots, pin the commit when copying.

### Inferences
- Prompt-injection hygiene: these skills are instructions Claude will follow. Copy by reading them, remove sections that call external services, MCPs, API keys or `npx`/CDN loaders, and keep the commit hash in a header comment. SKILL.md bodies I read contained no hidden instructions to exfiltrate data, but only the Markdown I opened.

### Gaps
- Did not read lib/*.py of sergebulaev, execution/*.py of AgriciDaniel, audit.mjs or palette.py of ArnavPuri; therefore recommend not copying those.
- Licence terms for fonts: Heebo is SIL OFL (general knowledge, not verified in this session).

---

## 3. Ten concrete changes to scripts/thumb_maker.py (highest expected quality gain first)

### Takeaway
The main path today is `--scene` (AI scene) followed by headline-only compositing (scene_mode, lines 216-241), so the biggest wins are a finishing grade on the whole scene, a much richer headline render (layered extrusion, glow, correct ribbon), and layout/QA relative to faces; cut-out refinements (rim light, light wrap, colour match, outline) matter only for the `--react`/classic modes, which the owner has largely rejected for final output.

### Cited Findings (what I verified in the file; line numbers are from the 328-line version I read)
- scene_mode does only cover-fit, face detection, headline and QA: no grading, vignette, grain or scrim (lines 216-241). Four fixed candidate areas are tried (line 225).
- headline_taklipu: line 1 size 112, line 2 size 180, shrink-to-fit by 5 px steps; stroke `st = max(6, size*0.075)` plus 6; accent gradient from (255,238,10) at the top to (255,160,20); inner edge darkening at 35%; shear 0.17; drop shadow = alpha blurred 10 px at 0.6, offset (6,10); whole text layer rotated by `tilt` (3.5) (lines 165-210).
- BUG (verified by reading): the red ribbon is pasted onto `bg` (line 206) BEFORE the text layer is rotated (line 207) and the ribbon itself is never rotated, so at tilt 3.5 the text swings away from its own ribbon; the ribbon is a flat colour (210,25,25) with +-14 px jitter and 1.2 px blur and no texture or shadow.
- sticker(): outline built with `MaxFilter(2*outline_px+1)` which is a square kernel (rectangular corners), outline_px=16, white; glow max-filter radius then blur; no edge colour decontamination; cutout() uses `alpha_matting=False` and a hard remap `(a-0.12)/0.76` (lines 43-85).
- enhance(): denoise, CLAHE 1.6, unsharp, contrast 1.08, colour 1.18, all global, applied before cut-out, so subject colour is never matched to the scene.
- QA covers only headline/face overlap, JPEG size and a saved 168x94 PNG; it does not measure contrast, text size at 168x94, bottom-right occupancy or hierarchy (lines 233-240).
- Pillow raqm available here, so `direction="rtl", language="he"` works (VERIFIED run). Mixed Hebrew plus "GTA 6!" must still be eyeballed for the exclamation mark position.
- Supporting lines from skills: sergebulaev "rim light, or a blurred or darkened background"; jsath outline "6 to 10 px", cutout upscale warning above 1.15x, "overlaps the cutout's real pixels" check; ArnavPuri glow ring behind the face and 168x94 shrink test; kangarooking face-exclusion mask and text-behind-subject depth with an overlap cap of about 18%.

### Inferences (my design knowledge, each needs a before/after test on 5 to 10 real thumbnails)

Ordered by expected impact on the SCENE path first.

1. **Finishing grade for the whole scene, face-masked (new function `finish(im, faces)` called at the end of scene_mode, before JPEG save).** Order: (a) gentle S-curve on luminance, strength 0.10-0.15 (smoothstep blend); (b) vibrance rather than saturation: s += (1-s)*0.22, half strength where hue is 5-35 deg (skin) and where s>0.7; (c) "clarity": unsharp with radius 35-45 px, amount 0.20-0.30 for local contrast, plus final sharpen radius 1.0, 60% after the downscale to 1280x720 to survive YouTube recompression; (d) radial vignette multiplying 1.0 at centre down to 0.72-0.78 at corners, centre offset toward the hero face; (e) monochrome film grain sigma 2-3/255 added before JPEG (reduces banding in AI gradients, hides AI plastic skin); (f) reduce (a)-(c) to 40% inside each face box expanded 15% so faces are not re-sharpened. Parameters are starting values.
2. **Headline renderer v2 (headline_taklipu):** (a) replace the single (6,10) shadow with an extrusion of 8-12 stacked offset copies (step 1 px, down-right, colour (20,8,0) then black), then a soft 18 px shadow at 0.55; (b) accent-line glow: blur sigma 22-30 of the accent colour at 0.40-0.50 alpha behind the text (screen blend) so the yellow line "lights" the scene; (c) accent gradient with a highlight band: top 0-30% (255,246,140) to mid (255,206,20) to bottom (255,132,20), plus a 2-3 px lighter keyline just inside the black stroke; (d) white line: slight vertical gradient (255,255,255) to (225,230,240), and the same extrusion; (e) stroke width 0.075*size is fine but check letter collisions in Heebo Black with strokes 14+ px: add 2-3% tracking by drawing Hebrew words char by char with `font.getlength` (safe for unpointed Hebrew, no joining forms; keep Latin/digit runs whole to avoid bidi breakage). Cap-height target >= 14% of frame height for the accent line (sibling note: 13 px at 94 px).
3. **Fix and upgrade the ribbon:** build ribbon on its own RGBA layer in text-local coordinates, composite text onto it, then rotate the combined layer once (fixes the verified bug). Ribbon: base (205,22,28) with a vertical gradient to (150,10,18), 3-4 px lighter top edge, torn edge made by thresholding smoothed noise (not +-14 px polygon jitter) with a 3-5 px off-white paper-fibre rim on the torn sides, subtle paper noise (sigma 6/255), its own drop shadow (blur 12, offset (5,9), 0.5). Test hue against YouTube's red UI if it touches the thumbnail edge (ArnavPuri advice); a yellow/orange ribbon variant per theme.
4. **Headline placement and size optimiser relative to faces (replace the 4 fixed areas, line 225):** search candidate boxes over a grid (top band, y0 between 14 and 0.22H), for each scale s in [0.75, 1.30] of the baseline sizes pick the largest scale with zero overlap against every YuNet face box expanded 15% and against hero-prop boxes; tie-break by lowest edge density (Canny) under the text and by visual balance (text centroid opposite the largest face). Use YuNet's five landmarks (nose offset relative to eye midpoint) to estimate gaze direction and prefer the side the hero looks toward (sergebulaev: "a subject looking at the text ... pulls the viewer's eye there"). Optional experiment: when face overlap is the only blocker, run rembg human segmentation on the scene and allow up to ~10% of glyph area to tuck behind the hero's head/shoulders (kangarooking cap ~18%), never touching the face exclusion mask.
5. **Adaptive top scrim and contrast guarantee:** before the headline, multiply a vertical gradient scrim over the top 0-30% (black alpha 0.35 at the top, 0 at 30%), tinted with `theme["dark"]` rather than pure black, strength raised when mean luminance under the text box exceeds 0.45. Measure WCAG-style contrast of the text fill vs the 90th-percentile background luminance under the text; fail the QA below 3:1 for large text (ArnavPuri/image-treatment threshold).
6. **Cut-out rim light and kicker glow (react/classic modes; also used for a guest cut-out):** compute an edge band from the alpha via cv2.distanceTransform (band width 6-10 px on the side facing the dominant light), tint it with the scene's brightest saturated colour (or theme["glow"]) and screen-blend at 0.55-0.70 with 1.5 px blur; add a coloured kicker halo behind the subject, sigma 25-40, alpha 0.35-0.50 (current sticker() glow already approximates this at 0.85 but is a uniform max-filter ring, which reads as a sticker). Skills echo: sergebulaev rim light, ArnavPuri glow ring.
7. **Light wrap and colour match of the cut-out to the scene:** (a) light wrap: blur the background sigma 16-20, take the 10-14 px inside edge band of the cut-out and mix 20-30% of the blurred background colour into it (screen/normal), which is the standard trick that makes a cut-out look "in" the plate; (b) Reinhard-style LAB transfer of the subject toward the surrounding plate statistics at strength 0.25-0.35 on a/b channels only, with the skin hue range protected; (c) one ambient colour cast: multiply the subject by the plate's mean colour at 8-12% opacity; (d) contact shadow where the person meets the frame bottom (dark gradient 40-60 px at 0.35).
8. **Cut-out edge quality and outline:** switch the outline from MaxFilter (square kernel) to a circular dilation from cv2.distanceTransform thresholded at r, r = 8 px at 720p (jsath says 6-10 px; ours is 16, which looks like a thick sticker and is out of line with a cohesive cinematic scene), feather 1.0-1.5 px; use rembg `alpha_matting=True` with foreground threshold ~240, background ~10, erode ~10 for hair detail, or guided filter from opencv-contrib if available; decontaminate fringes by replacing pixels with alpha in (0.05,0.95) by the nearest-interior colour after 2 px erosion; do not upscale a cut-out beyond 1.15x (jsath) and prefer the original facecam resolution crop: judge with a Laplacian variance on the face crop.
9. **Background depth for the non-scene path (`background()`, lines 98-112):** replace the 28-ray sunburst (a cliche) when a backdrop exists with: lens-blur (disc kernel radius 8-14 via cv2.filter2D) of the backdrop, brightness 0.55-0.70, saturation -10%, split-tone (shadows toward theme["dark"] hue shifted to teal/blue, highlights warm +8 R), vignette 0.25-0.35, plus 1.03x scale-in; keep the radial glow behind the subject with the theme glow colour (sergebulaev: "sharp subject on a softened background"). Keep one colour story: pass backdrop dominant hue to select the theme automatically.
10. **QA upgrade at 168x94 and 320x180 (extend the QA print at lines 233-240 and add exit codes):** report and gate on (a) accent-line cap height >= 14% of H and total headline block <= 40% of H; (b) text-vs-background contrast >= 3:1 (see 5); (c) bottom-right 16% x 14% box and top-right hover-icon zone free of faces/text; (d) hero face height 30-55% of H (sibling note); (e) face sharpness (Laplacian variance >= 100 on a 192 px crop); (f) headline words <= 3 (warn at 4+), (g) save a side-by-side contact sheet (1280, 320, 168 plus a greyscale 168 version to test value contrast) like jsath's preview. Add a "variants" flag that renders 2-3 variants changing one thing each (theme, headline side, accent colour) for YouTube Test and Compare.

Implementation order suggested: 3 (bug) then 2, 1, 5, 4, 10, then 6-9 only if the react/classic modes are kept.

### Gaps
- No measured baseline: none of these parameters was run against real frames in this task (no scene images were supplied); all are starting values.
- cv2.ximgproc/guided filter availability depends on opencv-contrib; the repo uses opencv-python-headless (per thumb_maker header), so use cv2.distanceTransform/numpy instead.
- The per-glyph tracking idea for Hebrew with Latin runs is untested for bidi correctness.
- Taklipu's actual typography and grading were not measured.

---

## 4. Recommended skills to copy into the repo under .claude/skills/

### Takeaway
Copy three trimmed external skills (jsath thumbnail-generator, ArnavPuri thumbnail-design with design-critique, sergebulaev yt-thumbnail-brief with its principles file) and author one in-house skill that holds the ODED style bible plus the ten changes; do not copy canvas-design, theme-factory or anything unlicensed.

### Cited Findings
- Claude Code skills are folders with a SKILL.md and YAML frontmatter (name, description); a repo-local skill lives at `.claude/skills/<name>/SKILL.md` (the `.claude/` directory does not exist yet in /home/user/oded-highlights: VERIFIED by `ls`). — [anthropics/skills README](https://raw.githubusercontent.com/anthropics/skills/main/README.md)
- Marketplace install is available for Anthropic's set (`/plugin marketplace add anthropics/skills`), but manual copy of a pinned folder is safer for the community repos.

### Inferences (recommended set; exact layout)

```
.claude/skills/
  thumbnail-generator/            # from jsath/claude-skills (MIT)
    SKILL.md
    references/composition.md
    references/reference-matching.md
    scripts/compose_thumbnail.py   # optional, read-only reference for the QA checks; we do not run it for Hebrew
    LICENSE                        # copy MIT text with "Copyright (c) 2026 johannships"
  thumbnail-design/               # from ArnavPuri/designskills (MIT)
    SKILL.md                       # skills/thumbnail-design/SKILL.md only
    LICENSE                        # "Copyright (c) 2026 Arnav Puri"
  design-critique/                # from ArnavPuri/designskills, SKILL.md only, no scripts/
    SKILL.md
  yt-thumbnail-brief/             # from sergebulaev/youtube-skills (MIT)
    SKILL.md
    references/brief-template.md
    references/thumbnail-principles.md   # moved from the repo root references/
    LICENSE
  oded-thumbnail-craft/           # ours: style bible + ten pipeline rules (write after owner review)
    SKILL.md
```

Edits to make after copying (mandatory, because these skills conflict with the house style):
- jsath: remove "Impact/solid colour blocks" guidance; state that text is rendered by scripts/thumb_maker.py (Heebo Black, RTL), keep size table, 168 px rule, QA checklist, layer order; add a header with source URL and commit hash.
- ArnavPuri thumbnail-design: delete the Gemini path, CSS export and OG/article sections; keep Steps 3, 5 (text treatment ideas), 6, 8 (zones), Quality Checklist; delete design-context dependencies; design-critique: keep Step 0 static-image branch, hierarchy checklist, scoring; delete Playwright/axe/audit.mjs mentions.
- sergebulaev: strip the Publora upload flow; add an override line "headlines in this channel may be 2-3 Hebrew words with punctuation and may repeat a title keyword; docs/THUMBNAIL_STYLE_BIBLE.md wins".
- Do NOT copy: canvas-design (thin fonts, abstract art), theme-factory, brand-guidelines, algorithmic-art, slack-gif-creator, efecto, kangarooking cover-skill (no licence; re-express ideas in oded-thumbnail-craft), anything from ComposioHQ (no licence), bergside/typeui (remote pull via npx).

How to invoke from Claude Code
- Auto-trigger by description (e.g. "make a thumbnail", "review this thumbnail") or explicitly: "Use the thumbnail-generator skill to QA out/thumb.jpg at 168 px", "Use design-critique on thumb.jpg and thumb_168.png" (Claude must Read both images, per the skills' procedure), "Use yt-thumbnail-brief to write the scene prompt and 3 variants for this clip".
- Suggested workflow per clip: (1) yt-thumbnail-brief produces the concept (scene, expression, prop, free headline area, colour story); (2) the external AI tool makes the scene from the docs/THUMBNAIL_BRIEF.md prompt, adding lighting words "strong key light on the face, bright rim light, vivid saturated colour, deep blacks, soft vignette" (Predis/sergebulaev); (3) `scripts/thumb_maker.py --scene ...` (with the ten changes); (4) thumbnail-design + design-critique review the output and the 168x94 preview; (5) pick the best of 2-3 variants.
- Fallback if the owner prefers zero external text: ship only oded-thumbnail-craft plus the jsath QA checklist.

### Gaps
- I did not test that these skills trigger correctly in Claude Code; description fields should be shortened and the `name` must match each folder.
- Skills do not create design quality by themselves; the real lift will come from items 1-5 of section 3.

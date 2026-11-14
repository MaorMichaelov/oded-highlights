# Thumbnail finishing techniques ("the Photoshop look") and how to reproduce them with Pillow / numpy / OpenCV

Scope: compositing + finishing recipes for `scripts/thumb_maker.py` (Python 3.13, Pillow 12.3.0, numpy 2.5.3, OpenCV 5.0.0 headless, rembg, CPU only). Written 2026-11-14.
Everything marked **[TESTED]** was run in this session on tiny inputs (640x360, one 1280x720 timing pass); code blocks below are extracted verbatim from the test modules that ran (`fx.py`, `typo.py`, `accents.py`, `read168.py`, kept in the session scratchpad, not in the repo). Timings: 4-core CPU, warm (second call), 640x360 unless stated; 1280x720 costs about 4x unless I measured it.
Test inputs: `skimage.data.astronaut()` (portrait, cut out with OpenCV GrabCut as a stand-in for rembg output, because the rembg model is not cached offline) over `skimage.data.rocket()` as "key art". The matte therefore still contains a bit of grey wall (rectangular blob at the top-left). So the visual results prove the mechanics, not final beauty. Taste judgements ("looks better") are mine, from eyeballing single images, not from CTR data.

## Q1. What do pro (MrBeast / gaming-clip) thumbnails do, and how solid is that evidence?

### Takeaway
Pro-look consensus (from tutorials, not studies): subject separated from background by a strong outline plus coloured rim/backlight, a high-contrast saturated palette, a large expressive face with eyes near the upper third, very thick outlined text, tested at phone size. The only large-sample data point found (Eden, 507,478 videos, via search snippet) says brightness/saturation/contrast/warm colour did NOT separate winners from losers, so treat "Photoshop look" as brand convention / polish, not a proven CTR lever.

### Cited Findings
- Rim light is used to separate subject from background; a mask-based rim keeps the effect on the edge only, and a Select-Subject mask can act as the stencil so the edge light stays off the interior — [Photoshop Cafe rim light](https://photoshopcafe.com/add-rim-light-photo-photoshop/), [Photoshop Cafe edge lights](https://photoshopcafe.com/?p=57355) (search-result summaries; pages not fetched).
- A rim light alone looks unfinished and needs colour grading afterwards — [Fstoppers](https://fstoppers.com/education/how-add-lovely-rim-light-effect-using-photoshop-197434) (search summary).
- Game-thumbnail tutorials use outer glow with adjustable size/spread on characters/eyes/text — [Photoshop Roadmap glowing thumbnails](https://www.photoshoproadmap.com/how-to-create-glowing-youtube-thumbnails-in-photoshop/) (search summary).
- MrBeast-style guides: saturated high-contrast complementary pairs (blue/yellow/red), strong outline + small shadow on text, shock/elation faces; guides disagree on whether an extra outer glow is used — [Touhfa MrBeast style analysis](https://touhfa.pages.dev/blog/thumbnails/mrbeast-thumbnail-article/) (search snippet only; host failed DNS on fetch). Many of these pages are AI/marketing content with untraceable stats.
- Counter-evidence: analysis of 507,478 videos found brightness, saturation, contrast and warm colours showed no measurable difference between winners and losers — [Eden](https://eden.so/blog/what-makes-a-good-youtube-thumbnail/) (search snippet only; fetch failed DNS).
- Check legibility by shrinking to phone size / ~10% (squint test); 3-6 big words; thick simple fonts with stroke/shadow/solid block; yellow on black cited as mobile-safe — [TimeSkip best practices](https://timeskip.io/blog/youtube-thumbnail-best-practices), [thumbnailtest rules](https://thumbnailtest.com/guides/youtube-thumbnail-rules/) (search summaries).
- Face size advice conflicts: "20-35% of the frame", "over 40%", "40-60% subject size" (blogs, no controlled study); eyes on the upper-third line, looking at camera, from one Reddit post — [r/YouTubeThumbnailHub checklist](https://redlib.ssps.io/r/YouTubeThumbnailHub/comments/w9proo/ultimate_thumbnail_guide_your_checklist_to). Rule of thirds is "a framework, not a law"; a centred close-up can work — same search summaries.
- YouTube spec baseline: 1280x720, min width 640, 16:9, JPG/GIF/PNG under 2 MB — [YouTube Help: Add video thumbnails](https://support.google.com/youtube/answer/72431) (older snapshot seen in search). A third-party Sept-2026 guide claims newer limits (3840x2160 recommended, 50 MB desktop / 2 MB mobile app); I could not confirm against Google's live page — keep the 1280x720 / <2 MB rule that the pipeline already uses.

### Inferences
- Since convention != measured lift, spend effort first on things that are objectively visible at 168x94 (separation, contrast, text legibility, face size) and only then on atmosphere (grain, flares, aberration).
- The "cut-and-paste" feel in `thumb_maker.py` comes mostly from missing separation + missing light/colour integration + no global finishing pass (see Q8), not from missing exotic effects.

### Gaps
- No A/B or CTR data for any single effect. No verified spec for 2026 YouTube limits. w3.org, touhfa.pages.dev, thumbnailtest.com, eden.so all failed DNS from this sandbox (only github.com / raw.githubusercontent.com reachable); claims from them are search-snippet-level only.

## Q2. Subject separation and matte quality: what to do and exact recipes

### Takeaway
Order matters: clean the matte -> decontaminate edge colour -> then build separation layers from that alpha: round crisp stroke (3-5 px @640, i.e. 6-10 px @1280) + coloured glow (sigma 10-14 @640) + alpha-gradient rim light + light wrap + two-layer shadow. The current `sticker()` uses `MaxFilter`, which is a SQUARE kernel (I verified: MaxFilter(33) on one pixel -> 33x33 square), so outlines have squared corners; a distance-transform stroke is round, anti-aliased and 5 ms.

### Cited Findings
- Guided filter formulas (He et al.): box means over window r, a = cov(I,p)/(var(I)+eps), b = mean(p) - a*mean(I), output = mean(a)*I + mean(b) — read from [opencv_contrib guided_filter.cpp](https://raw.githubusercontent.com/opencv/opencv_contrib/4.x/modules/ximgproc/src/guided_filter.cpp). `cv2.ximgproc` is NOT present in opencv-python-headless here (I checked `hasattr(cv2,'ximgproc') == False`), so implement with `cv2.boxFilter`.
- pymatting (already installed as a rembg dependency, v1.1.16) ships "Fast Multi-Level Foreground Estimation (CPU, CUDA, OpenCL)" (Germer et al.) — [pymatting README](https://raw.githubusercontent.com/pymatting/pymatting/master/README.md). README gives no usage snippet/timings for it; usage below is from my test.
- Hue/Saturation-adjusted bright coloured rim lights are the standard Photoshop trick for separation — [Photoshop Roadmap](https://www.photoshoproadmap.com/how-to-create-glowing-youtube-thumbnails-in-photoshop/) (search summary).

### Inferences
Tested recipes ([TESTED], helper code is exactly what ran):

**1. Matte cleanup (`refine_alpha`)** — levels, drop islands, fill holes, guided filter only inside the unknown band, then re-steepen. 8-10 ms @640x360.
Finding: running a guided filter over a whole already-tight matte WIDENS the edge (soft-edge width 2.1 px -> 4.2 px at r=2, 7.6 px at r=4) because gray guide has little contrast at hair/wall boundaries; restricting it to the unknown band and re-steepening (gain 2) gave 0.9 px. Use r=2, eps=1e-4, gain 1.0-2.0 (gain 1.0 for genuinely soft hair/motion blur, 2.0 for hard cut-outs). Visual check: crisp edge, no foggy halo.
Honest limit: on my synthetic disk with an 8 px soft true edge the gain-2 steepening increased error (it "corrects" a soft edge into a hard one); the metric there is dominated by alpha shape, not colour. Do not tune gain from that test; tune on real rembg hair.
```python
def guided_filter(I, p, r, eps):
    """He et al. guided filter, gray guide (cv2.ximgproc is NOT in opencv-python-headless). I,p float32 HxW."""
    k = (2 * r + 1, 2 * r + 1); box = lambda x: cv2.boxFilter(x, -1, k, borderType=cv2.BORDER_REFLECT)
    mI, mp = box(I), box(p); cov = box(I * p) - mI * mp; var = box(I * I) - mI * mI
    a = cov / (var + eps); b = mp - a * mI
    return box(a) * I + box(b)
```
```python
def refine_alpha(rgb, a, lo=0.08, hi=0.92, gf_r=2, gf_eps=1e-4, shrink_px=0, gain=2.0, min_area_frac=0.002, fill_holes_frac=0.001):
    a = np.clip((a - lo) / (hi - lo), 0, 1).astype(np.float32)
    b = (a > 0.5).astype(np.uint8); n, lab, st, _ = cv2.connectedComponentsWithStats(b, 8)       # drop islands
    keep = np.zeros(n, bool); keep[1:] = st[1:, cv2.CC_STAT_AREA] >= min_area_frac * a.size
    a = a * keep[lab]
    inv = (a < 0.5).astype(np.uint8); n, lab, st, _ = cv2.connectedComponentsWithStats(inv, 4)   # fill small holes
    hole = np.zeros(n, bool); hole[1:] = st[1:, cv2.CC_STAT_AREA] < fill_holes_frac * a.size
    hole[lab[0, 0]] = False; a = np.maximum(a, hole[lab].astype(np.float32))
    g = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    band = cv2.dilate(((a > 0.02) & (a < 0.98)).astype(np.uint8), np.ones((2 * gf_r + 1,) * 2, np.uint8)) > 0     # only touch the unknown band
    a = np.where(band, np.clip(guided_filter(g, a, gf_r, gf_eps), 0, 1), a)
    if gain != 1: a = np.clip((a - 0.5) * gain + 0.5, 0, 1)                                                         # re-steepen edge after the smoothing
    if shrink_px: a = cv2.erode(a, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * shrink_px + 1,) * 2)); a = blur(a, 0.6)
    return a
```

**2. Edge colour decontamination.** Test: synthetic orange foreground with a known soft alpha, photographed on blue or white, composited on red; error = mean abs diff vs ground-truth composite in the edge band (alpha 0.02-0.98), true alpha supplied:

| method | blue-origin bg | white-origin bg | cost @640x360 |
|---|---|---|---|
| naive (photo RGB + alpha) | 27.0/255 | 19.7/255 | 0 |
| `decontaminate` below (interior diffusion, edge pixels only) | 4.2 | 3.2 | ~10 ms |
| `pymatting.estimate_foreground_ml` | 0.13 | 0.13 | ~40 ms |

Caveat: synthetic fg is smooth; real hair has detail inside the semi-transparent band, which diffusion discards (first version blurred the whole 3-4 px edge and visibly smeared hair; I fixed it to touch only alpha<0.985 pixels, smoothstep-weighted). pymatting is the better default (already a dependency): `from pymatting import estimate_foreground_ml; fg = estimate_foreground_ml(rgb.astype(np.float64), alpha.astype(np.float64)).astype(np.float32)`; use `decontaminate` as a fallback/speed path. Real-rembg/hair/hand behaviour NOT verified.
```python
def decontaminate(rgb, a, core_erode=1, sigma=3.0, lo=0.55, hi=0.985):
    """edge-only colour decontamination: pixels with alpha<hi take colour diffused from the trusted interior (a>0.99, eroded)
    (normalised convolution). Interior pixels (a>=hi) are NOT touched, so hair/skin detail stays sharp."""
    core = cv2.erode((a > 0.99).astype(np.float32), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * core_erode + 1,) * 2))
    num = blur(rgb * core[..., None], sigma); den = blur(core, sigma)[..., None]
    inner = num / np.maximum(den, 1e-4)
    t = np.clip((a - lo) / (hi - lo), 0, 1); trust = (t * t * (3 - 2 * t))[..., None]          # smoothstep: 0 below lo, 1 above hi
    return rgb * trust + inner * (1 - trust)
```

**3. Rim colour from the backdrop.** k-means (k=4, 64x36 downsample, fixed seed) and pick the cluster maximising sqrt(share)*S*(0.3+V); force S>=0.65, V=1. 0.7-3.6 ms. On the rocket backdrop it returned (0.35,0.56,1.0), a clean sky blue. Use this instead of the static `THEMES[...]["glow"]`.
```python
def dominant_color(rgb, k=4, mask=None):
    """most 'colourful & bright & frequent' cluster of the backdrop -> RGB float. ~2 ms."""
    small = cv2.resize(rgb, (64, 36), interpolation=cv2.INTER_AREA).reshape(-1, 3)
    cv2.setRNGSeed(0)
    _, lab, cen = cv2.kmeans(small, k, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 0.5), 2, cv2.KMEANS_PP_CENTERS)
    cnt = np.bincount(lab.ravel(), minlength=k) / len(lab)
    hsv = cv2.cvtColor(cen.reshape(1, k, 3).astype(np.float32), cv2.COLOR_RGB2HSV).reshape(k, 3)   # H 0..360, S,V 0..1
    score = np.sqrt(cnt) * hsv[:, 1] * (0.3 + hsv[:, 2])
    return cen[int(np.argmax(score))], hsv[int(np.argmax(score))]
```
```python
def rim_color(rgb_backdrop, min_s=0.65, v=1.0):
    c, hsv = dominant_color(rgb_backdrop)
    out = cv2.cvtColor(np.float32([[[hsv[0], max(hsv[1], min_s), v]]]), cv2.COLOR_HSV2RGB)[0, 0]
    return out
```

**4. Crisp outer stroke + soft glow.** Stroke: distance transform, exact round width, anti-aliased, 5 ms. Glow: dilate 3 px, Gaussian sigma 10-14 @640, composite with screen at 0.6-0.85 in the rim colour. Parameters that looked right: white stroke 3 px @640 (6 px @1280) with softness 1.0; glow radius 3, sigma 10, opacity 0.7. Bad: stroke >= 5 px @640 reads as a sticker; a wide, strong glow (radius 6, sigma 12, opacity 0.85 in my first pass) turned into fog around the head.
```python
def outer_stroke(alpha, px, color=(1, 1, 1), softness=0.8):
    """round, anti-aliased stroke of exactly px pixels via distance transform. returns (rgb layer, alpha layer) incl. subject."""
    d = cv2.distanceTransform((alpha < 0.5).astype(np.uint8), cv2.DIST_L2, 5)
    s = np.clip((px + 0.5 - d) / max(softness, 1e-3) * 1.0, 0, 1)
    s = np.maximum(s, alpha)
    return np.ones(alpha.shape + (3,), np.float32) * np.float32(color), s
```
```python
def glow_layer(alpha, radius, sigma, color, strength=0.9, ):
    base = cv2.dilate(alpha, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * radius + 1,) * 2)) if radius else alpha
    g = np.clip(blur(base, sigma) * strength, 0, 1)
    return np.ones(alpha.shape + (3,), np.float32) * np.float32(color), g
```

**5. Rim light / inner edge highlight from the alpha gradient.** Pseudo-normal = -grad(blur(alpha, 5)); lit weight = max(0, n.L)^power; band = exp(-dist_inside/width) * alpha; composite with screen in a brightened rim colour. `light_dir` points toward the light in image coords (y down), e.g. (1,-0.4) = light from the right and above, which should match where the backdrop's bright area is. Good: width 4-6 px @640, power 1.6-2.0, strength 0.6-0.9. Bad: strength >1 and width >8 paints a pink/blue blush over skin and shoulders (my first pass). 17-21 ms.
```python
def rim_light(rgb, alpha, light_dir, color, width=7.0, power=1.6, strength=1.0, normal_sigma=5.0, add_mode="screen"):
    """inner edge light: pseudo-normal from alpha gradient, lit where normal faces the light. light_dir=(lx,ly) points TOWARD the light (image coords, y down)."""
    ab = blur(alpha, normal_sigma)
    gx = cv2.Sobel(ab, cv2.CV_32F, 1, 0, ksize=3); gy = cv2.Sobel(ab, cv2.CV_32F, 0, 1, ksize=3)
    mag = np.sqrt(gx * gx + gy * gy) + 1e-6
    nx, ny = -gx / mag, -gy / mag                      # outward normal
    L = np.float32(light_dir) / np.linalg.norm(light_dir)
    facing = np.clip(nx * L[0] + ny * L[1], 0, 1) ** power
    d_in = cv2.distanceTransform((alpha > 0.5).astype(np.uint8), cv2.DIST_L2, 3)
    band = np.exp(-d_in / width) * alpha
    rim = np.clip(band * facing * strength, 0, 1)
    col = np.float32(color)
    return screen(rgb, rim[..., None] * col) if add_mode == "screen" else np.clip(rgb + rim[..., None] * col, 0, 1), rim
```

**6. Light wrap** (compositor trick: blurred backdrop colour bleeds onto the subject's inner edge so it feels inside the scene). width 8-10, strength 0.15-0.3, bg_blur 14. 18-20 ms.
```python
def light_wrap(fg_rgb, alpha, bg_rgb, width=10, strength=0.5, bg_blur=14):
    """background colour 'wraps' onto the subject's inner edge (compositor trick); fg_rgb/alpha/bg_rgb all canvas-sized."""
    d_in = cv2.distanceTransform((alpha > 0.5).astype(np.uint8), cv2.DIST_L2, 3)
    band = np.exp(-d_in / (width / 2)) * alpha
    wrapc = blur(bg_rgb, bg_blur)
    return screen(fg_rgb, wrapc * (band * strength)[..., None] * 1.0)
```

**7. Shadows.** Backdrop darkening that follows the subject: ambient occlusion = Gaussian(alpha, sigma 22 @640) x 0.55 plus a drop shadow offset AWAY from the light (10,6 px, sigma 6, opacity 0.6) multiplied into the backdrop. Subject that bleeds off the bottom edge needs no floor shadow; for a standing cut-out use a flattened/sheared copy of the alpha (cv2.warpAffine with y-scale 0.2-0.3, shear toward the light) blurred sigma 3-8 at 0.4-0.6 opacity and a tight contact shadow (sigma 2-3, 0.5-0.7) directly under the feet. Contact shadow variant was NOT built/tested. Whole AO+drop shadow = 10 ms.
```python
def drop_shadow(alpha, dx, dy, sigma, opacity):
    return np.clip(blur(shift(alpha, dx, dy), sigma) * opacity, 0, 1)
```

Ablation image check (head crop 2x): raw -> refine+decontaminate -> +stroke -> +glow -> +rim -> +wrap; stroke+glow is the largest single jump in "cut-out stops looking pasted"; rim light and light wrap are subtle at the safe strengths above (visible mainly on the shoulder/hair edge), so judge them at 2x zoom, not at 168 px.

### Gaps
- Not tested with real rembg `u2net_human_seg` output (model not available offline), so hair strands, hands/fists, and the existing `cutout()` (threshold 0.12..0.88 then GaussianBlur 1.1) were not benchmarked against my refine. `rembg.remove(..., alpha_matting=True)` (pymatting closed-form) not timed.
- Contact shadow for a standing cut-out not tested. skimage / kornia not used (pure OpenCV/numpy); pilgram not run, only its README read.

## Q3. Colour grading and scene matching

### Takeaway
Highest value per ms: partial (strength 0.25-0.4) Reinhard Lab transfer of the subject toward the backdrop, a luminance-only S-curve (0.15-0.25), vibrance not saturation, and a final vignette; teal/orange split-tone at 6-10% is cheap. Grain and chromatic aberration are near-invisible after downscale + JPEG; keep them tiny or skip.

### Cited Findings
- Reinhard-style transfer in the reference implementation: convert to L*a*b* float32, per channel `(x - mean_src) * (std_ref/std_src) + mean_ref` (the repo's `preserve_paper=False` uses the inverse ratio, which its docstring says tends to look more pleasing), clip to [0,255] — [jrosebr1/color_transfer](https://raw.githubusercontent.com/jrosebr1/color_transfer/master/color_transfer/__init__.py).
- pilgram offers Instagram-style filters, CSS filters (contrast, grayscale, hue_rotate, saturate, sepia) and blend modes (multiply, screen, overlay, soft_light, hard_light, color_dodge, etc.) on Pillow images and requires Pillow >= 10.3 for current versions — [pilgram README](https://github.com/akiomik/pilgram). It is a convenience; everything below is plain numpy and needs no extra dependency.
- Grading after the light matters; MrBeast-style guides mention warm midtones/cooler shadows split toning — [Fstoppers](https://fstoppers.com/education/how-add-lovely-rim-light-effect-using-photoshop-197434), [Touhfa](https://touhfa.pages.dev/blog/thumbnails/mrbeast-thumbnail-face-effect/) (snippets).

### Inferences
Tested recipes [TESTED]:

**1. Masked, partial Reinhard in Lab** (`reinhard_lab`): subject stats from alpha>0.5, reference stats from backdrop pixels away from the subject; std ratio clamped 0.75-1.35; chroma channels at full `strength`, L at half (keep face lighting). Measured on astronaut/rocket: Lab chroma distance subject->backdrop 40.4 (off) -> 32.5 (0.2) -> 26.6 (0.35) -> 20.9 (0.5); a* of the subject moved 21.4 -> 15.6 at 0.35, so skin loses ~25% of its warmth. Use 0.25-0.35 for people, 0.5 only for props/logos. 9-11 ms @640 (41 ms @1280 full-frame).
```python
def reinhard_lab(src, ref, src_mask=None, ref_mask=None, strength=0.4, clamp=(0.75, 1.35), keep_L=0.5):
    """Reinhard 2001 colour transfer in Lab (cv2 float32 Lab: L 0..100, a/b ~ +-127), masked stats, partial strength."""
    sl = cv2.cvtColor(src, cv2.COLOR_RGB2Lab); rl = cv2.cvtColor(ref, cv2.COLOR_RGB2Lab)
    sm = (src_mask > 0.5) if src_mask is not None else np.ones(src.shape[:2], bool)
    rm = (ref_mask > 0.5) if ref_mask is not None else np.ones(ref.shape[:2], bool)
    out = sl.copy()
    for c in range(3):
        s_m, s_s = sl[..., c][sm].mean(), sl[..., c][sm].std() + 1e-4
        r_m, r_s = rl[..., c][rm].mean(), rl[..., c][rm].std() + 1e-4
        ratio = float(np.clip(r_s / s_s, *clamp))
        t = (sl[..., c] - s_m) * ratio + r_m
        k = strength * (keep_L if c == 0 else 1.0)        # transfer chroma at full strength, luminance at half (don't destroy the lighting on the face)
        out[..., c] = sl[..., c] * (1 - k) + t * k
    return np.clip(cv2.cvtColor(out, cv2.COLOR_Lab2RGB), 0, 1)
```

**2. S-curve on L\* only** (`s_curve(amount=0.15..0.3)`, smoothstep blend; in Lab so hue/saturation do not shift) and **vibrance** (`amount 0.25-0.4`, boosts weak colours more, down-weights hue ~25 degrees = skin). 8 ms @640, 33 ms @1280 for both.
```python
def s_curve(rgb, amount=0.25, in_lab=True):
    f = lambda x: x + amount * (3 * x * x - 2 * x ** 3 - x)        # smoothstep blend; amount 0.15-0.35
    if not in_lab: return np.clip(f(rgb), 0, 1)
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2Lab); lab[..., 0] = f(lab[..., 0] / 100) * 100
    return np.clip(cv2.cvtColor(lab, cv2.COLOR_Lab2RGB), 0, 1)
```
```python
def vibrance(rgb, amount=0.35, protect_skin=True):
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV); h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    w = 1 - s                                         # weak colours get boosted more
    if protect_skin: w = w * (1 - 0.6 * np.exp(-((((h - 25 + 180) % 360) - 180) / 25.0) ** 2))   # hue ~25deg = skin/orange
    hsv[..., 1] = np.clip(s * (1 + amount * w), 0, 1)
    return np.clip(cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB), 0, 1)
```

**3. Teal/orange split tone** (shadows -> (0,0.45,0.55) at 6-10%, highlights -> (1,0.6,0.25) at 5-8%; luminance-weighted). 14.5 ms @640. Apply to the backdrop at the upper end, to the whole frame at the lower end; on a subject already orange (skin/suit) it makes everything orange.
```python
def split_tone(rgb, shadow=(0.0, 0.45, 0.55), high=(1.0, 0.6, 0.25), s_amt=0.10, h_amt=0.08):
    l = lum(rgb)[..., None]
    ws = np.clip(1 - l * 2, 0, 1) ** 1.5; wh = np.clip(l * 2 - 1, 0, 1) ** 1.5
    out = rgb + (np.float32(shadow) - rgb) * ws * s_amt + (np.float32(high) - rgb) * wh * h_amt   # 'soft' blend toward tint
    return np.clip(out, 0, 1)
```

**4. Vignette** (strength 0.25-0.4, centre near the face, not frame centre): 5.5 ms @640 / 21 ms @1280. **Grain** (sigma 0.010-0.015, midtone-weighted, blur 0.6): 7.7 ms; will be mostly destroyed by the 168/320 downscale and JPEG q<95, and it inflates JPEG size; priority 1. **Chromatic aberration** (radial R/B scale +/-1-1.5 px at the frame edge): 3.5 ms @640 / 15 ms @1280; priority 1, fine fringing on small text makes it harder to read — keep <=1.2 px and never on the text layer (apply before text).
```python
def vignette(rgb, strength=0.35, center=(0.5, 0.5), radius=0.85, power=2.0):
    h, w = rgb.shape[:2]; yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.hypot((xx / w - center[0]) * (w / h), yy / h - center[1]) / (radius * (w / h) * 0.5 + 1e-6)
    v = 1 - strength * np.clip(d, 0, 1.5) ** power / 1.5 ** (power - 1) / 1.5
    return rgb * np.clip(v, 0, 1)[..., None]
```
```python
def grain(rgb, sigma=0.015, seed=1, chroma=0.0):
    rng = np.random.default_rng(seed); n = blur(rng.normal(0, 1, rgb.shape[:2]).astype(np.float32), 0.6) * sigma * 1.6
    l = lum(rgb); w = 4 * l * (1 - l) + 0.2                                    # strongest in midtones
    return np.clip(rgb + (n * w)[..., None], 0, 1)
```
```python
def chroma_ab(rgb, px=1.5):
    h, w = rgb.shape[:2]; yy, xx = np.mgrid[0:h, 0:w].astype(np.float32); cx, cy = w / 2, h / 2
    out = rgb.copy()
    for c, k in ((0, +1), (2, -1)):
        s = 1 + k * px / (w / 2)
        mx = (xx - cx) / s + cx; my = (yy - cy) / s + cy
        out[..., c] = cv2.remap(rgb[..., c], mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    return out
```

**5. Bloom on highlights.** Full-resolution Gaussians are the single slowest effect (269 ms @1280); do the blur at 1/4 resolution: 11.7 ms @1280 (3.6 ms @640), visually equivalent for sigma >= 12. Threshold 0.70-0.75, sigmas (6,22)@640, amount 0.25-0.35 screen.
```python
def bloom_fast(rgb, thresh=0.72, sigmas=(6, 22), amount=0.30, s=0.25):
    small = cv2.resize(rgb, None, fx=s, fy=s, interpolation=cv2.INTER_AREA); l = fx.lum(small)
    hi = np.clip((l - thresh) / (1 - thresh), 0, 1)[..., None] * small
    b = sum(cv2.GaussianBlur(hi, (0, 0), sg * s) for sg in sigmas) / len(sigmas)
    b = cv2.resize(b, (rgb.shape[1], rgb.shape[0]), interpolation=cv2.INTER_LINEAR)
    return fx.screen(rgb, np.clip(b * amount * 2, 0, 1))
```
```python
def bloom(rgb, thresh=0.72, sigmas=(6, 22), amount=0.30):
    l = lum(rgb); hi = np.clip((l - thresh) / (1 - thresh), 0, 1)[..., None] * rgb
    b = sum(blur(hi, s) for s in sigmas) / len(sigmas)
    return screen(rgb, np.clip(b * amount * 2, 0, 1))
```
Recommended order for the global pass: reinhard (subject only) -> s_curve -> vibrance -> split_tone -> bloom_fast -> vignette -> (grain 0.008) -> text/accents on top -> final unsharp.

### Gaps
- No perceptual/CTR validation of strengths; ranges come from my eyeballing one frame plus the Lab statistics above. Teal/orange not compared on a real streamer portrait (skin-tone safety unverified beyond the vibrance hue guard).

## Q4. Depth and energy: making a flat key-art backdrop feel "behind" the subject

### Takeaway
Five cheap cues do most of it: (1) blur+darken the backdrop 15-30% (sigma 1.5-3 px @640), (2) a back-glow in the rim colour behind the head, (3) AO/drop shadow on the backdrop, (4) light wrap + coloured rim on the subject, (5) put something in FRONT of the subject's edge (a few sparks/bokeh layers drawn over it) so there is a z-order cue. Zoom blur and speed lines add energy but must be masked away from the face; speed lines were the weakest effect in my tests.

### Cited Findings
- Subject-separation advice: a simpler/more contrasty backdrop beats a busy photographic one at thumbnail size — search summary of [Photoshop Roadmap](https://www.photoshoproadmap.com/how-to-create-glowing-youtube-thumbnails-in-photoshop/) and related results. No source found with numeric parameters for blur/darkening; the parameters below are mine.

### Inferences
Tested recipes [TESTED]:
- Backdrop: `GaussianBlur(sigma=1.6)` then `* 0.80` then zoom blur centred on the subject's head (amount 0.035, 8 steps, 9 ms @640 / 27 ms @1280 for 10 steps). My first try (sigma 2.5, x0.72) destroyed the recognisability of the key art — for "GTA 6 key art must stay recognisable" use sigma <= 1.5 @640 (3 @1280), darken 0.85-0.9, and put the blur/darken only on the half the subject overlaps via a horizontal mask.
- Back-glow: radial gradient `clip(1-d)**1.8` (ellipse ~0.45W x 0.7H centred behind the head), colour = rim colour, screen at 0.45-0.6. 8-11 ms.
- Zoom blur (radial speed blur): average of 8-12 `warpAffine` scalings 1.0..1.04-1.08 about the focal point, optionally blended in with a radial mask (`keep_radius` 0.2-0.3 keeps centre sharp).
```python
def zoom_blur(rgb, center, amount=0.06, steps=10, keep_radius=0.0, feather=0.25):
    h, w = rgb.shape[:2]; acc = np.zeros_like(rgb)
    for i in range(steps):
        s = 1 + amount * i / (steps - 1)
        M = np.float32([[s, 0, center[0] * w * (1 - s)], [0, s, center[1] * h * (1 - s)]])
        acc += cv2.warpAffine(rgb, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    acc /= steps
    if keep_radius <= 0: return acc
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32); d = np.hypot((xx / w - center[0]) * (w / h), yy / h - center[1])
    m = np.clip((d - keep_radius) / feather, 0, 1)[..., None]
    return rgb * (1 - m) + acc * m
```
- Speed lines: ss=2 polygons from the focal point, alpha 0.15-0.25, 20-30 wedges, half-angle 0.006-0.02 rad, inner radius >=0.28 of the diagonal, faded to zero near the face. 14-16 ms. In my test render they read as random streaks, not a convincing burst; zoom blur + sparks gave better energy per ms. Priority 2.
```python
def speed_lines(size, center, n=70, r_in=0.30, r_out=1.2, color=(1, 1, 1), alpha=0.22, seed=3, ss=2):
    w, h = size; rng = np.random.default_rng(seed); big = Image.new("L", (w * ss, h * ss), 0); d = ImageDraw.Draw(big)
    cx, cy = center[0] * w * ss, center[1] * h * ss; R = math.hypot(w, h) * ss
    for _ in range(n):
        ang = rng.uniform(0, 2 * math.pi); half = rng.uniform(0.0015, 0.006); r0 = rng.uniform(r_in, r_in + 0.25) * R; r1 = r_out * R
        d.polygon([(cx + r0 * math.cos(ang - half), cy + r0 * math.sin(ang - half)), (cx + r1 * math.cos(ang), cy + r1 * math.sin(ang)), (cx + r0 * math.cos(ang + half), cy + r0 * math.sin(ang + half))],
                  fill=int(255 * rng.uniform(0.4, 1.0)))
    m = np.asarray(big.resize((w, h), Image.LANCZOS), np.float32) / 255 * alpha
    return np.ones((h, w, 3), np.float32) * np.float32(color), m
```
- Sparks/particles: short motion-direction lines (1-2.6 px wide, 6-26 px long) with white-hot core + Gaussian glow, screen, 40-60 per 640x360; bokeh: 14-20 rings 8-34 px radius, opacity 0.2, blurred 1 px. 30 ms together. Keep sparks warm (orange) over a cool backdrop for colour contrast.
```python
def sparks(size, n=60, color=(1.0, 0.65, 0.2), seed=5, dir_deg=-40, ss=2, region=None):
    w, h = size; rng = np.random.default_rng(seed); big = Image.new("L", (w * ss, h * ss), 0); d = ImageDraw.Draw(big)
    x0, y0, x1, y1 = region or (0, 0, w, h)
    for _ in range(n):
        x = rng.uniform(x0, x1) * ss; y = rng.uniform(y0, y1) * ss; L = rng.uniform(6, 26) * ss; a = math.radians(dir_deg + rng.uniform(-20, 20))
        wd = max(1, int(rng.uniform(1, 2.6) * ss)); d.line([(x, y), (x + L * math.cos(a), y + L * math.sin(a))], fill=int(rng.uniform(150, 255)), width=wd)
    m = np.asarray(big.resize((w, h), Image.LANCZOS), np.float32) / 255
    glow = np.clip(blur(m, 3) * 1.6, 0, 1); a = np.clip(m + glow * 0.8, 0, 1)
    col = np.ones((h, w, 3), np.float32) * np.float32(color); col = col * (1 - m[..., None] * 0.6) + m[..., None] * 0.6   # white-hot core
    return col, a
```
```python
def bokeh(size, n=18, color=(1, 0.8, 0.5), seed=9, rmin=8, rmax=34, opacity=0.22, ss=2):
    w, h = size; rng = np.random.default_rng(seed); big = Image.new("L", (w * ss, h * ss), 0); d = ImageDraw.Draw(big)
    for _ in range(n):
        r = rng.uniform(rmin, rmax) * ss; x = rng.uniform(0, w) * ss; y = rng.uniform(0, h) * ss; v = int(255 * rng.uniform(0.35, 1))
        d.ellipse((x - r, y - r, x + r, y + r), fill=int(v * 0.55), outline=v, width=max(1, int(r * 0.12)))
    m = blur(np.asarray(big.resize((w, h), Image.LANCZOS), np.float32) / 255, 1.0) * opacity
    return np.ones((h, w, 3), np.float32) * np.float32(color), m
```
- Light leak (corner radial gradient, screen 0.35-0.5, warm) 5.5 ms; anamorphic lens flare (core + horizontal streak + 3 ghosts toward centre) 16.5 ms. Both ran and produced plausible output but are easy to overdo; priority 1-2, place the flare at a real bright spot of the backdrop and never near the face.
```python
def light_leak(size, corner=(1.0, 0.0), color=(1.0, 0.45, 0.15), radius=0.55, strength=0.5):
    w, h = size; yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.hypot((xx / w - corner[0]) * (w / h), yy / h - corner[1]) / radius
    m = np.clip(1 - d, 0, 1) ** 2 * strength
    return np.ones((h, w, 3), np.float32) * np.float32(color), m
```
```python
def lens_flare(size, pos, color=(1.0, 0.85, 0.6), strength=0.8, streak=0.55):
    w, h = size; yy, xx = np.mgrid[0:h, 0:w].astype(np.float32); px, py = pos[0] * w, pos[1] * h
    d = np.hypot(xx - px, yy - py); core = np.exp(-(d / (0.018 * w)) ** 2) + 0.35 * np.exp(-(d / (0.06 * w)) ** 2)
    st = np.exp(-((yy - py) / (0.006 * h * 3)) ** 2) * np.exp(-np.abs(xx - px) / (0.25 * w)) * streak          # anamorphic horizontal streak
    m = np.clip(core + st, 0, 1) * strength
    cx, cy = w / 2, h / 2
    for t, r, a in ((0.4, 0.03, 0.25), (0.8, 0.05, 0.18), (1.3, 0.02, 0.22)):                                  # ghosts along the line to centre
        gx, gy = px + (cx - px) * t * 1.6, py + (cy - py) * t * 1.6
        m += np.exp(-(np.hypot(xx - gx, yy - gy) / (r * w)) ** 6) * a * strength
    return np.ones((h, w, 3), np.float32) * np.float32(color), np.clip(m, 0, 1)
```

### Gaps
- Atmospheric-perspective (lift blacks / reduce contrast of the backdrop) and foreground-occluding backdrop elements (sub-layer split of the key art) not tested. No evidence on which energy effect raises CTR.

## Q5. Composition and graphic accents

### Takeaway
Layout: put the eyes on the upper-third line (y ~ 0.30-0.36 H), face large (face-box height ~ 35-50% H for a head-and-shoulders portrait; sources conflict), subject overlapping the backdrop edge, 40-50% width of calm negative space for the headline, diagonal arrow/circle pointing from face to the subject. Accents: ONE or at most two (arrow or circle, plus optionally a badge); drawn at 4x supersampling on a cropped ROI.

### Cited Findings
- Eyes on the upper-third line, looking at camera — [r/YouTubeThumbnailHub](https://redlib.ssps.io/r/YouTubeThumbnailHub/comments/w9proo/ultimate_thumbnail_guide_your_checklist_to) (search summary). Face-size claims conflict (20-35% / >40% / 40-60%) — [TimeSkip](https://timeskip.io/blog/youtube-thumbnail-best-practices) and other results (search summaries). Rule of thirds as framework not law — same results.
- 3-6 words maximum; a stroke/shadow/solid block behind text — [thumbnailtest rules](https://thumbnailtest.com/guides/youtube-thumbnail-rules/) (search summary).

### Inferences
Tested [TESTED]:
- **Eye-line from YuNet landmarks.** The repo's `detect_faces()` keeps only `r[:4]`; YuNet rows also carry landmarks `r[4:14]` = right eye (x,y), left eye, nose, mouth corners. On the astronaut test: eye y = 65 px = 18% of the cut-out height, face h = 82 px; to put the eyes at H/3 the cut-out needs `py = H/3 - eye_y`. Recipe: scale the subject so face-box height = 0.38-0.48 H, then `py = 0.33*H - eye_y*scale`; if that leaves a gap at the bottom, scale up instead of moving the subject up (bleed off the bottom like now).
```python
det = cv2.FaceDetectorYN.create(YUNET, "", (w, h), 0.55, 0.3, 5000); _, res = det.detect(bgr)
r = res[0]; eye_y = (r[5] + r[7]) / 2; face_h = r[3]            # r: x,y,w,h, reye(x,y), leye(x,y), nose, mouth_r, mouth_l, score
```
- **Accents with supersampling.** Render the vector mask on an ROI (not the full canvas) at 4x, build white + black strokes with the distance transform, drop shadow, downsample with INTER_AREA. Full-canvas 4x for four shapes took 1.9 s; ROI version: arrow 77 ms, scribble circle 43 ms, badge 35 ms (measured end to end per shape: mask draw + distance transform + resize). Styles that looked like real thumbnails: red arrow (235,20,30) + 3 px white + 8 px black; yellow (255,230,20) hand-drawn ring 11 px + 2.5 px black; red circle badge "#1" with white ring and black outline. Use sparingly: at most one pointer + one badge, never covering a face, arrow pointing at the thing the streamer reacts to.
```python
def stylize(mask, fill, strokes, ss=4, shadow=(5, 7, 5, 0.5)):
    """mask: float HxW at ss x resolution (ROI only!). strokes=[(px_at_final_res,(r,g,b)),...] innermost first. returns RGBA float at 1/ss res."""
    d = cv2.distanceTransform((mask < 0.5).astype(np.uint8), cv2.DIST_L2, 5); out = np.zeros(mask.shape + (4,), np.float32)
    if shadow:
        mm = np.clip(strokes[-1][0] * ss + 0.5 - d, 0, 1) if strokes else mask
        out[..., 3] = cv2.GaussianBlur(cv2.warpAffine(mm, np.float32([[1, 0, shadow[0] * ss], [0, 1, shadow[1] * ss]]), mask.shape[::-1]), (0, 0), shadow[2] * ss) * shadow[3]
    for px, col in reversed(strokes):
        m = np.clip(px * ss + 0.5 - d, 0, 1)[..., None]; out[..., :3] = out[..., :3] * (1 - m) + np.float32(col) / 255 * m; out[..., 3] = np.maximum(out[..., 3], m[..., 0])
    m = mask[..., None]; out[..., :3] = out[..., :3] * (1 - m) + np.float32(fill) / 255 * m; out[..., 3] = np.maximum(out[..., 3], mask)
    return cv2.resize(out, (mask.shape[1] // ss, mask.shape[0] // ss), interpolation=cv2.INTER_AREA)
```
```python
def arrow_mask(w, h, ss=4, shaft=14, head=40, length=175, angle_deg=160):
    A = Image.new("L", (w * ss, h * ss), 0); c = (w * ss / 2, h * ss / 2); s = ss
    pts = [(0, -shaft), (length - 65, -shaft), (length - 65, -head), (length, 0), (length - 65, head), (length - 65, shaft), (0, shaft)]
    a = math.radians(angle_deg); ca, sa = math.cos(a), math.sin(a)
    ImageDraw.Draw(A).polygon([(c[0] + ((x - length / 2) * ca - y * sa) * s, c[1] + ((x - length / 2) * sa + y * ca) * s) for x, y in pts], fill=255)
    return np.asarray(A, np.float32) / 255
```
```python
def scribble_circle_mask(w, h, ss=4, width=11, turns=1.12, wobble=0.03, seed=4):
    B = Image.new("L", (w * ss, h * ss), 0); d = ImageDraw.Draw(B); cx, cy, rx, ry = w * ss / 2, h * ss / 2, w * ss * 0.42, h * ss * 0.42; pts = []
    for t in np.linspace(0, 2 * math.pi * turns, 90):
        r = (1 + 0.05 * t / (2 * math.pi)) * (1 + wobble * math.sin(3 * t + 1)); pts.append((cx + rx * r * math.cos(t - 1.2), cy + ry * r * math.sin(t - 1.2)))
    d.line(pts, fill=255, width=width * ss, joint="curve")
    for p in (pts[0], pts[-1]): d.ellipse((p[0] - width * ss / 2, p[1] - width * ss / 2, p[0] + width * ss / 2, p[1] + width * ss / 2), fill=255)
    return np.asarray(B, np.float32) / 255
```
```python
def badge_masks(w, h, text="#1", ss=4, font_px=64):
    C = Image.new("L", (w * ss, h * ss), 0); ImageDraw.Draw(C).ellipse((2 * ss, 2 * ss, (w - 2) * ss, (h - 2) * ss), fill=255)
    T_ = Image.new("L", (w * ss, h * ss), 0); ImageDraw.Draw(T_).text((w * ss / 2, h * ss / 2), text, font=typo.font(font_px * ss), fill=255, anchor="mm")
    return np.asarray(C, np.float32) / 255, np.asarray(T_, np.float32) / 255
```
```python
def paste_rgba(bg, rgba, x, y):
    h, w = rgba.shape[:2]; a = rgba[..., 3:4]; bg[y:y + h, x:x + w] = bg[y:y + h, x:x + w] * (1 - a) + rgba[..., :3] * a
```
Hebrew caveat: a "NEW" badge in Latin is fine, but any Hebrew in a badge should go through the same `typo.multilayer` path (RTL via raqm).

### Gaps
- Face-size/eye-line numbers are blog convention (conflicting) — treat as defaults to A/B. Leading lines, scale contrast and negative-space scoring were not implemented; the existing `overlap()` face-box check in `thumb_maker.py` already covers the hard constraint.

## Q6. Typography polish (Hebrew RTL)

### Takeaway
Stack: soft glow (only on dark backgrounds) -> drop shadow -> thick black outer stroke -> thin white inner stroke -> gradient fill with bevel + gloss band -> italic shear. Checked numerically: black stroke on a dark backdrop has WCAG ratio 1.07, so the stroke vanishes; add a light/coloured outer ring or glow when the surrounding luminance is low.

### Cited Findings
- Thick simple fonts with stroke, shadow or a solid block behind the text; yellow-on-black as mobile-safe example; 3-6 words — [TimeSkip](https://timeskip.io/blog/youtube-thumbnail-best-practices), [thumbnailtest](https://thumbnailtest.com/guides/youtube-thumbnail-rules/) (search summaries). MrBeast-style white text -> black stroke -> small shadow, glow disputed — [Touhfa](https://touhfa.pages.dev/blog/thumbnails/mrbeast-thumbnail-article/) (snippet).

### Inferences
Tested [TESTED] on Heebo variable (Black via `set_variation_by_name("Black")`), raqm/fribidi/harfbuzz all present in this Pillow build:
- `multilayer()` ~31-60 ms for a 132 px two-word line @1280 (first call slower). Parameters: outer stroke `max(6, 0.085*size)`, inner white stroke `0.03*size`, gradient (255,240,40)->(255,150,20), bevel offset `0.025*size`, shadow offset (8,10) blur 10 opacity 0.55, glow sigma `0.10*size` only on dark backgrounds, shear 0.12-0.17. Pillow's `stroke_width` gives round joins, good for the thick Black weight.
- Tracking: Pillow's `text()` has no letter-spacing argument. Hebrew has no joining forms, so per-glyph drawing in visual order works (`tracked_mask`); digits/Latin runs must be kept un-reversed (`visual_runs`). Tested -3%, 0, +4% em: -3% makes neighbouring outer strokes nearly touch/overlap; use 0 to +2% for the Black weight because the thick stroke already closes the gaps (judged by eye on one 8-glyph line). Nikud (vowel points) and Arabic would break this per-glyph path.
- Auto-fit: binary search on `font.getbbox(text, stroke_width=sw, direction="rtl", language="he")`, 8.6 ms (the existing downward `size -= 5` loop is ~3 ms of font reloads, so not a speed issue; the improvement is that stroke width is included in the fit).
- Contrast ratio: WCAG formula (relative luminance 0.2126/0.7152/0.0722 on linearised sRGB, ratio (L1+0.05)/(L2+0.05)); 3:1 is the large-text threshold, 4.5:1 normal — from memory/common knowledge, NOT verified against w3.org (DNS failed). Numbers from my run: white vs black 21.0, yellow (255,240,40) vs black 17.7, black stroke vs mid blue (90,128,179) 5.2, black stroke vs near-black (10,10,20) 1.07. Rule: if stroke-vs-surround < 3, add a 2-3 px light outer ring (white or the rim colour) or a glow.
- Face avoidance: keep the repo's candidate-area search + `overlap(box, face)<2%`; add a flatness term (prefer the candidate box with the lowest edge density, `cv2.Laplacian` variance, of the backdrop).
```python
def visual_runs(text):
    """logical -> visual order runs for simple RTL headlines: Hebrew runs reversed char-wise, digits/latin runs kept, run order reversed."""
    runs=re.findall(r"[֐-׿\s]+|[^֐-׿\s]+",text); out=[]
    for r in reversed(runs):
        out.append(r[::-1] if HEB.search(r) else r)
    return "".join(out)
```
```python
def tracked_mask(text, f, track_px, stroke=0, pad=0):
    """draw glyph by glyph (LTR in visual order) with extra tracking. Hebrew has no joining forms so this is safe (not for Arabic)."""
    vis=visual_runs(text); adv=[f.getlength(c) for c in vis]; w=int(f.getlength(text,direction='rtl',language='he') if False else sum(adv)+track_px*(len(vis)-1))+2*pad
    asc,desc=f.getmetrics(); m=Image.new("L",(w,asc+desc+2*pad),0); d=ImageDraw.Draw(m); x=pad
    for c,a in zip(vis,adv):
        d.text((x,pad),c,font=f,fill=255,stroke_width=stroke); x+=a+track_px
    return m
```
```python
def fit_size(text, max_w, max_h, stroke_ratio=0.08, lo=30, hi=500):
    while hi-lo>2:
        mid=(lo+hi)//2; f=font(mid); sw=int(mid*stroke_ratio); b=f.getbbox(text,stroke_width=sw,direction="rtl",language="he")
        if b[2]-b[0]<=max_w and b[3]-b[1]<=max_h: lo=mid
        else: hi=mid
    return lo
```
```python
def multilayer(text, size, fill="gradient", grad=((255,240,40),(255,150,20)), outer=(0,0,0), inner=(255,255,255), outer_px=None, inner_px=None,
               bevel=True, shadow=(8,10,10,0.55), glow=None, track=0.0, shear=0.15, use_raqm=True, return_masks=False):
    f=font(size); outer_px=outer_px if outer_px is not None else max(6,int(size*0.085)); inner_px=inner_px if inner_px is not None else int(size*0.03)
    pad=outer_px+int(size*0.25); asc,desc=f.getmetrics()
    def mask(stroke):
        if track==0 and use_raqm:
            m=Image.new("L",(int(f.getlength(text,direction="rtl",language="he"))+2*pad,asc+desc+2*pad),0)
            ImageDraw.Draw(m).text((pad,pad),text,font=f,fill=255,stroke_width=stroke,direction="rtl",language="he"); return m
        return tracked_mask(text,f,track*size,stroke,pad-stroke if pad>stroke else 0) if False else tracked_mask(text,f,track*size,stroke,pad)
    m0=np.asarray(mask(0),np.float32)/255; mi=np.asarray(mask(inner_px),np.float32)/255; mo=np.asarray(mask(outer_px),np.float32)/255
    if mo.shape!=m0.shape: raise SystemExit("mask shapes differ")
    h,w=m0.shape; out=np.zeros((h,w,3),np.float32); A=np.zeros((h,w),np.float32)
    if glow:
        g=np.clip(cv2.GaussianBlur(mo,(0,0),size*0.10)*1.4,0,1); out=out*(1-g[...,None])+np.float32(glow)/255*g[...,None]; A=np.maximum(A,g*glow_a if False else g*0.9)
    if shadow:
        dx,dy,s,op=shadow; sh=cv2.GaussianBlur(cv2.warpAffine(mo,np.float32([[1,0,dx],[0,1,dy]]),(w,h)),(0,0),s)*op
        out=out*(1-sh[...,None]); A=np.maximum(A,sh)
    out=np.where(mo[...,None]>0, out*(1-mo[...,None])+np.float32(outer)/255*mo[...,None], out); A=np.maximum(A,mo)
    out=out*(1-mi[...,None])+np.float32(inner)/255*mi[...,None]
    if fill=="gradient":
        ys=np.clip((np.arange(h)-pad)/(asc+desc),0,1)[:,None,None]; c0=np.float32(grad[0])/255; c1=np.float32(grad[1])/255
        fc=c0*(1-ys)+c1*ys; fc=np.broadcast_to(fc,(h,w,3))
    else: fc=np.broadcast_to(np.float32(fill)/255,(h,w,3))
    fc=fc.copy()
    if bevel:
        d=max(2,int(size*0.025)); sh_=lambda x,dx,dy: cv2.warpAffine(x,np.float32([[1,0,dx],[0,1,dy]]),(w,h))
        hi=np.clip(m0-sh_(m0,d,d),0,1); lo=np.clip(m0-sh_(m0,-d,-d),0,1)               # top-left lit rim, bottom-right dark rim, inside glyph only
        hi=cv2.GaussianBlur(hi,(0,0),d*0.5); lo=cv2.GaussianBlur(lo,(0,0),d*0.6)
        gloss=np.clip(1-np.abs((np.arange(h)-pad-(asc+desc)*0.28)/((asc+desc)*0.16)),0,1)[:,None]*0.18*m0       # soft horizontal gloss band
        fc=fc+ (1-fc)*hi[...,None]*0.6 + gloss[...,None]*(1-fc); fc=fc*(1-lo[...,None]*0.45)
    out=out*(1-m0[...,None])+fc*m0[...,None]; A=np.maximum(A,m0)
    rgba=np.dstack([out,A]); 
    if shear:
        M=np.float32([[1,shear,-shear*h/2],[0,1,0]]); rgba=cv2.warpAffine(rgba,M,(w,h),flags=cv2.INTER_CUBIC)
    if return_masks:
        sh2=lambda x: cv2.warpAffine(x,np.float32([[1,shear,-shear*h/2],[0,1,0]]),(w,h),flags=cv2.INTER_CUBIC) if shear else x
        return np.clip(rgba,0,1),sh2(m0),sh2(mo)
    return np.clip(rgba,0,1)
```
```python
def wcag_ratio(rgb1,rgb2):
    l=lambda c: float(fx.lum(fx.srgb2lin(np.float32(c)/255)))
    a,b=l(rgb1),l(rgb2); a,b=max(a,b),min(a,b); return (a+0.05)/(b+0.05)
```

### Gaps
- Optical alignment and kerning pairs for Hebrew not tested (raqm default kerning only). Red torn ribbon text-on-ribbon not re-tested (existing code unchanged). Variable-font weight axis beyond "Black" not explored.

## Q7. Sharpening, downscale, export, and an automatic 168x94 readability check

### Takeaway
Final pass: resample with area-averaging (never plain bicubic when shrinking), unsharp mildly at full size, JPEG q92-95 with 4:4:4 (size is nowhere near 2 MB on this kind of image), and gate on an automatic legibility number measured at 168x94 (stem width >= ~2.5 px, stroke-vs-surround ratio >= 3).

### Cited Findings
- 1280x720, 16:9, < 2 MB, JPG/PNG/GIF — [YouTube Help](https://support.google.com/youtube/answer/72431) (older snapshot; newer third-party claims unverified).

### Inferences
Tested [TESTED] on a 1280x720 composite:
- **JPEG** (this synthetic composite, so sizes are optimistic; real photographic detail + grain will be several times larger): q88/92/95, 4:4:4: 192/235/308 KB; 4:2:0: 142/170/223 KB; progressive saves another ~2-3%. MAE on the saturated headline region: 4:4:4 q92 = 0.98/255 vs 4:2:0 q92 = 1.47 (chroma subsampling hurts saturated edges, ~50% more error). Keep `subsampling=0`, `optimize=True`, start q=94, step down until < 1.9 MB (the repo already does this).
- **Downscale** 1280->168 / 320: Pillow LANCZOS 9-11 ms, BOX 1.7-2.3 ms, `reducing_gap=2` 2-4 ms, cv2 INTER_AREA 2-3 ms (Laplacian variance of these four within ~8% of each other at 168 px, ~6% at 320), but cv2 INTER_CUBIC (no antialias) gave 2.5x / 1.8x higher Laplacian variance = aliasing masquerading as sharpness; never use it for shrinking or for the 168 preview/QA. Linear-light vs sRGB downscale differ by mean 1.2/255 (max 73/255 on hard text edges); not worth the cost except for the QA preview where you want to mimic a good downsampler — YouTube's own downsampler is unknown.
- **Unsharp** (radius/percent/threshold at 1280x720; effect judged at 320x180 Laplacian var, baseline 2640): r0.8/p60/t2 -> 2744; r1.0/p80/t2 -> 2866; r1.2/p100/t2 -> 3051; r2.0/p120/t2 -> 3797 (I did not inspect halos for these settings; the highest variance is not automatically better). Sharpening AFTER the downscale raises the 320 px variance most (r0.6/p60 -> 3736). Recommended: full-res `UnsharpMask(radius=1.0, percent=70, threshold=2)` applied before text, nothing on the text layer, and a separate sharpen only for the 168 QA preview (never for the uploaded file). The repo's current `enhance()` uses radius 2.2/percent 140 on the face crop — that is stronger than anything I tested (r2.0/p120 was the strongest), so check it for halos on real portraits.
- **168x94 readability metric** `legibility()`: downsample the image and both masks with INTER_AREA, ring = 3 px band just outside the text silhouette, WCAG ratio stroke colour vs ring median; stem width = 2*area/perimeter of the fill mask; text height. Results with a 132 px headline: bright bg 15.6:1 / mid 4.9:1 / dark 1.09:1 (flagged), stem 2.7 px, text height 16 px at 168 wide. 6-16 ms. Suggested gates: stem >= 2.5 px, stroke-vs-surround >= 3.0, line height >= 12 px at 168.
```python
def legibility(img_rgb, fill_mask, outer_mask, fill_rgb, stroke_rgb, target=(168,94)):
    """img float RGB full-res; masks float full-res (glyph fill / glyph+outer stroke). Returns dict of at-168 numbers. ~3 ms."""
    tw,th=target; im=cv2.resize(img_rgb,(tw,th),interpolation=cv2.INTER_AREA)
    fm=cv2.resize(fill_mask,(tw,th),interpolation=cv2.INTER_AREA); om=cv2.resize(outer_mask,(tw,th),interpolation=cv2.INTER_AREA)
    ring=(cv2.dilate((om>0.5).astype(np.uint8),np.ones((7,7),np.uint8))>0)&(om<0.05)       # ~3 px band just outside the text at 168 scale
    ring_rgb=np.median(im[ring],axis=0) if ring.any() else np.float32([.5,.5,.5])
    cs,_=cv2.findContours((fm>0.5).astype(np.uint8),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE)
    per=sum(cv2.arcLength(c,True) for c in cs); area=(fm>0.5).sum()
    sil=(om>0.5); stroke_w=(om>0.5).sum()
    return dict(ratio_stroke_vs_surround=typo.wcag_ratio(np.float32(stroke_rgb),ring_rgb*255),
                ratio_fill_vs_stroke=typo.wcag_ratio(np.float32(fill_rgb),np.float32(stroke_rgb)),
                stem_px_at_168=2*area/max(per,1), text_height_px_at_168=float(np.ptp(np.nonzero(sil.any(1))[0])+1))
```
- Quick global score (kept short; another note covers scoring): luminance std of the 320x180 version (>= 0.18), mean saturation (HSV S) 0.35-0.65, Laplacian-variance of the 320 version relative to a golden sample, face-box height fraction 0.35-0.5, `legibility()` ratio >= 3. These thresholds are my starting guesses, not validated.

### Gaps
- 2 MB JPEG headroom with real content, and YouTube's server-side recompression/downscaling, not measured. No check at actual phone display sizes beyond 168/320 px.

## Q8. Priorities and the 8 "before -> after" changes to `scripts/thumb_maker.py`

### Takeaway
Impact/effort priority (5 = do first): separation stack and matte hygiene > colour/light integration > global finishing > text polish/contrast > accents > atmosphere. Full tested finishing stack on one 640x360 frame cost 256 ms total (first measured 384 ms cold); at 1280x720 expect ~1 s with bloom at 1/4 res (I did not run the full chain at 1280).

### Cited Findings
- See Q1-Q7 for sources; this section combines first-hand tests with them. File facts below come from reading `/home/user/oded-highlights/scripts/thumb_maker.py` (not modified).

### Inferences
**Technique scoreboard** (priority 1-5 = visual impact per effort; ms @640x360 measured, @1280 in brackets if measured/estimated "~"):

| technique | looks good when | looks bad when | key params | ms | prio |
|---|---|---|---|---|---|
| round outer stroke + coloured glow | thin crisp white/black stroke 6-10 px @1280, glow in backdrop hue | thick sticker, fog | stroke 3 px, glow r3 s10 a0.7 | 16 (~65) | 5 |
| two-layer shadow / AO on backdrop | soft dark halo opposite the light | uniform dark box | AO s22 a0.55, drop (10,6) s6 a0.6 | 10 (~40) | 5 |
| matte refine + edge decontaminate | no colour fringe, crisp hair silhouette | smeared hair | gf r2 eps1e-4 gain1-2; pymatting fg | 8+10 (40 pymatting; ~160) | 5 |
| headline contrast ring + multilayer | readable on any bg at 168 px | black stroke on dark bg | stroke 0.085em, ring if ratio<3 | 30-60 | 5 |
| rim light from alpha gradient | thin coloured edge on lit side | blush across skin | w4-6 p2 s0.7 | 17-21 (~75) | 4 |
| light wrap | edge picks up backdrop colour | glowing halo | w8 s0.2 | 18 (~75) | 4 |
| partial Reinhard + S-curve + vibrance | subject shares scene palette, skin still warm | grey/teal skin | 0.25-0.35, s0.2, v0.3 | 9+8 (41+33) | 4 |
| back-glow + backdrop blur/darken | key art still recognisable, subject pops | muddy backdrop | blur 1.5, x0.8-0.9, glow 0.5 | 9+8 | 4 |
| vignette + bloom_fast + split tone | subtle depth, glossy highlights | grey haze | v0.3, bloom 0.3, tone 0.06-0.1 | 5.5+3.6+14.5 (21+12+58) | 3-4 |
| 168 px legibility gate + eye-line placement | consistent faces/headlines | n/a | see Q5/Q7 | 6-16 | 4 |
| zoom blur / sparks | energy aimed at the backdrop | cluttered face area | zoom 0.035; 40-60 sparks | 7+30 (27) | 3 |
| accents (arrow/circle/badge) | one clear pointer | 3+ stickers | ROI 4x ss | 35-77 each | 3 |
| speed lines | rare | random streaks | n 20-30, a0.2 | 14 | 2 |
| bokeh / light leak / flare | faint, backdrop-hue | on face | a0.2 | 30 / 5.5 / 16.5 | 2 |
| grain | invisible at 168 | JPEG bloat | s0.01 | 7.7 (23) | 1 |
| chromatic aberration | <=1.2 px at edges | on text | 1.2 px | 3.5 (15) | 1 |

**Eight changes to `thumb_maker.py`, ordered by impact:**
1. `sticker()` (lines 70-85): square `MaxFilter(2*outline_px+1)` for outline, glow and shadow -> distance-transform round stroke (`outer_stroke`, 3-5 px @640 equivalent = 8-10 px at W=1280, not 16) + `glow_layer` in a colour derived from the backdrop (`rim_color`) instead of the fixed `th["glow"]`. Before: boxy white sticker; after: crisp round outline with matched glow. ~25 ms.
2. `react_mode()` (lines 243-276) applies ONLY a Gaussian drop shadow (lines 261-263) — no outline, glow, rim, or colour match. -> call the same separation stack (stroke + glow + rim + light wrap + AO/drop shadow). This is the "cut-and-paste" look in the react layout.
3. `cutout()` (lines 43-52: `clip((a-0.12)/0.76)` then `GaussianBlur(1.1)` blurs every edge and leaves background colour in semi-transparent pixels) -> `refine_alpha()` (no extra blur) + `estimate_foreground_ml` (pymatting, already installed with rembg) before compositing; keep `rembg` alpha_matting off for speed. Before: soft fringe/halo; after: tight edge, no colour contamination.
4. Subject grade: `enhance()` does generic CLAHE + `Contrast 1.08` + `Color 1.18` (lines 54-68) on the face crop only, regardless of scene -> add `reinhard_lab(strength=0.3)` toward the backdrop stats, `vibrance(0.3)` instead of `Color` 1.18, `s_curve(0.2)`; reduce the unsharp (radius 2.2, percent 140) to radius 1.0-1.2, percent 70-100.
5. Backdrop integration: `art_background`/`react_mode` darken with a horizontal gradient only (lines 87-96, 250-254) -> add backdrop blur (sigma 1.5 @640 / 3 @1280) + darken x0.85, rim-coloured back-glow behind the head, AO under the subject, optional zoom blur centred on the head.
6. Add a single global finishing pass in `make/scene_mode/react_mode` BEFORE the headline: `split_tone` (0.06-0.1), `bloom_fast`, `vignette` centred on the face, then text, then final `UnsharpMask(1.0, 70, 2)`; currently no global grade exists anywhere.
7. `headline_taklipu()` (lines 165-210): currently black stroke + dark inner edge + shadow. -> add a light outer ring or glow when stroke-vs-surround WCAG < 3 (dark backdrops), a thin white inner stroke, gradient+bevel+gloss (`multilayer`), and include stroke width in the auto-fit (binary search instead of `size -= 5`). Face-avoidance logic can stay.
8. QA/placement: after layout compute `legibility()` at 168x94 (stem >= 2.5 px, ratio >= 3, line height >= 12 px) and fail/adjust like the existing overlap check; use YuNet landmarks to scale the subject so face height = 0.38-0.48 H and eyes at 0.33 H (currently `py = H - person.height + 24` / `k = min(...)` ignores the face position entirely); keep `subsampling=0`, add the 168 preview via `cv2.INTER_AREA`.

### Gaps
- Rankings are judgement from first-hand renders of one test frame plus conventional wisdom; no CTR evidence (and Eden's data argues grading strength may not matter for CTR). End-to-end chain at 1280x720 and with real rembg portraits (hair, fists) not run. Contact shadow for floor-standing cut-outs, foreground occlusion layering and Hebrew optical kerning not tested. Not run: kornia, scikit-image filters, pilgram (README read only). Pillow/OpenCV/skimage official docs were not fetched; API behaviour was established by running the code on Pillow 12.3.0 / OpenCV 5.0.0 / numpy 2.5.3. Hosts that failed DNS: touhfa.pages.dev, www.w3.org, thumbnailtest.com, eden.so (only github.com and raw.githubusercontent.com resolved; search results are summaries).

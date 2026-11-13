# Polished-edit techniques for an automated Hebrew stream-highlight pipeline (ffmpeg + Pillow/numpy, CPU-only CI)

Date of research: 2026-11-13. Environment used for local tests: ffmpeg 6.1.1 (Ubuntu), Pillow 12.3.0 with Raqm/FriBiDi/HarfBuzz all True, numpy 2.5.3, OpenCV 5.0.0 (no Haar cascade files shipped, `FaceDetectorYN` present), no scipy, no python-bidi, no mediapipe, no moviepy, auto-editor not installed locally. Heebo variable font is installed at `/usr/share/fonts/truetype/sand-box/google/Heebo/Heebo-VariableFont_wght.ttf`.

Evidence labels used throughout:
- **[TESTED]** = I ran it in this session (small, 480x270 or less, a few seconds). Code in this file is the code that ran, lightly trimmed.
- **[CITED]** = from a web source with a link. Most web results were blogs/vendor pages, not primary docs (see Gaps per section). The search tool returned summaries, not page text, and `WebFetch` was blocked for pixabay.com, partnerhelp.netflixstudios.com and auto-editor.com (host not in the session allowlist), so none of those pages were read directly.
- **[CLAIMED]** = my own general knowledge, not verified here. Treat as hypotheses.

Repo observations (local files, read this session): `scripts/zoom_body.py` applies a fixed 1.18x centre punch-in to arbitrary time ranges (this is exactly the behaviour the owner dislikes); `scripts/branding_v2.py` already has `_ease_pop`, `sub_overlay_frames` and `caption_png`; `scripts/detect_layout.py` uses a skin-colour mask plus a fractional default layout (`DEFAULT_LAYOUT` in `scripts/config.py`: facecam x=.7438,y=.0926,w=.2562,h=.2269; content x=.1042,y=.1019,w=.6042,h=.7315); `assets/sfx/` holds boing/boom/ding/slide/slidedown/whoosh wavs (0.35 to 1.4 s); `scripts/requirements.txt` pins pillow==13.0.0 and auto-editor==29.3.1.

---

## 1. Animated logo stings and wipe transitions (CPU, no GL)

### Takeaway
Render the sting and the wipe once as pre-baked frames with Pillow/numpy (sunburst + spring-scaled logo + particle burst + sub-frame motion blur), cache them as an mp4/PNG sequence, and composite them at build time; use ffmpeg `xfade` (built-in or `custom` expression) or a Pillow-rendered matte with `maskedmerge` for the wipe. gl-transitions is unnecessary: the CPU paths below ran in well under a second on small test clips.

### Cited Findings
- `xfade` supports a `custom` transition with an `expr` that can use X, Y (pixel coordinates), W, H, and the A/B input pixel values; the filter was added in FFmpeg Jan 2020 — [FFmpeg cvslog commit](https://ffmpeg.org/pipermail/ffmpeg-cvslog/2020-January/120813.html), [vf_xfade.c 6.1 source](https://www.ffmpeg.org/doxygen/6.1/vf__xfade_8c_source.html). A third-party page's example `if(gt(X+Y,W+HP),B,A)` looks like it contains a typo ([skills.lc](https://www.skills.lc/majiayu000/claude-skill-registry/majiayu000-claude-skill-registry-skills-data-ffmpeg-transitions-effects-skill-md)); do not copy it.
- Ease-out-back (Penner): `1 + (s+1)(t-1)^3 + s(t-1)^2`, default s = 1.70158 gives ~10% overshoot — [Phaser Back easing](https://docs.phaser.io/api-documentation/3.88.2/namespace/math-easing-back), [Cinder EaseOutBack](https://libcinder.org/docs/structcinder_1_1_ease_out_back.html). (The Penner form with (t-1) is from my knowledge; the sources confirm s and the ~10% figure.)
- Flutter approximates easeOutBack with a cubic Bezier `Cubic(0.175, 0.885, 0.32, 1.275)` — [Flutter API](https://api.flutter.dev/flutter/animation/Curves/easeOutBack-constant.html). This is the CSS `cubic-bezier()` form and can be solved numerically (see snippet).
- Search results contained no source for spring physics (mass/stiffness/damping) or for particle bursts; the spring and particle approaches below are my own derivation, validated only by test.

### Inferences
**Verified by local test [TESTED]**

1. Easing/spring library (all ran). `spring()` is the closed-form underdamped step response; with zeta=0.45, omega=14 rad/s it peaked at 1.201 (20% overshoot) at t=0.267 s and stayed within 2% of 1.0 from t=0.6 s. `out_back` with s=1.70158 peaked at 1.100.
```python
import math, numpy as np
def clamp(x,a=0.0,b=1.0): return max(a,min(b,x))
def out_cubic(t): return 1-(1-t)**3
def out_expo(t): return 1.0 if t>=1 else 1-2**(-10*t)
def out_back(t,s=1.70158): t-=1; return 1+(s+1)*t**3+s*t**2
def spring(t, zeta=0.45, omega=14.0):      # t in SECONDS. overshoot ~ exp(-pi*zeta/sqrt(1-zeta^2))
    if t<=0: return 0.0
    wd=omega*math.sqrt(1-zeta**2)
    return 1-math.exp(-zeta*omega*t)*(math.cos(wd*t)+zeta*omega/wd*math.sin(wd*t))
def bezier_ease(x1,y1,x2,y2):              # CSS cubic-bezier(x1,y1,x2,y2) -> f(t)
    def f(t):
        lo,hi=0.0,1.0
        for _ in range(30):
            m=(lo+hi)/2; x=3*(1-m)**2*m*x1+3*(1-m)*m*m*x2+m**3
            lo,hi=(m,hi) if x<t else (lo,m)
        m=(lo+hi)/2; return 3*(1-m)**2*m*y1+3*(1-m)*m*m*y2+m**3
    return f
```
2. Sunburst background in numpy (rays = `sin(n*atan2)>0` wedges, radial fade, vignette). Rotating it slowly (`rot=t*0.25`) gives the "alive" look at no cost:
```python
def sunburst(W,H,n=16,rot=0.0,c0=(10,18,12),c1=(22,70,34),vign=0.55):
    yy,xx=np.mgrid[0:H,0:W].astype(np.float32); cx,cy=W/2,H/2
    ang=np.arctan2(yy-cy,xx-cx)+rot
    ray=(np.sin(ang*n)>0).astype(np.float32)
    r=np.hypot(xx-cx,yy-cy)/np.hypot(W/2,H/2)
    fade=np.clip(1-r*0.9,0,1)[...,None]
    base=np.array(c0,np.float32); hi=np.array(c1,np.float32)
    img=base+(hi-base)*(ray[...,None]*fade)
    return np.clip(img*(1-vign*np.clip(r,0,1.2)**2)[...,None],0,255).astype(np.uint8)
```
3. Logo sting: logo scaled by `spring(t-0.15)` (with a rotation that settles, `(1-s)*-12` degrees), particle burst at t=0.35 with `out_cubic` radial travel and shrinking radius, **motion blur by sub-frame accumulation** (render SUB=4 sub-samples across a 180-degree shutter, i.e. a half-frame time window, and average them as float32). Frames piped as rawvideo into one ffmpeg libx264 process (no frame files, constant memory). Result: 60 frames at 480x270 with SUB=4 rendered in 2.95 s; visual check of 4 frames showed the logo growing with overshoot, particles flying out, rays rotating. Scaling the cost by pixel count (x16 at 1920x1080) suggests ~45 s for a 2 s sting; since the sting is static branding, pre-render once and cache (this extrapolation is an estimate, not measured).
```python
def frame(i, FPS=30, SUB=4):
    acc=None
    for k in range(SUB):
        t=(i+(k/SUB-0.5)*0.5)/FPS            # 180-degree shutter: +-0.25 frame
        a=np.asarray(render(max(0,t)),np.float32)
        acc=a if acc is None else acc+a
    return (acc/SUB).astype(np.uint8)
# p=subprocess.Popen(["ffmpeg","-y","-f","rawvideo","-pix_fmt","rgb24","-s","1920x1080","-r","30","-i","-","-c:v","libx264","-pix_fmt","yuv420p","-crf","18","sting.mp4"],stdin=PIPE)
```
4. ffmpeg `xfade` built-ins available in 6.1.1 (from `ffmpeg -h filter=xfade`): fade, wipeleft/right/up/down, slideleft/right/up/down, circlecrop, rectcrop, distance, fadeblack, fadewhite, radial, smoothleft/right/up/down, circleopen/close, vertopen/close, horzopen/close, dissolve, pixelize, diagtl/tr/bl/br, hlslice/hrslice/vuslice/vdslice, hblur, fadegrays, wipetl/tr/bl/br, squeezeh/v, zoomin, fadefast, fadeslow, hlwind/hrwind/vuwind/vdwind, coverleft/right/up/down, revealleft/right/up/down. All 7 I ran (wipeleft, circleopen, radial, slideleft, zoomin, squeezeh, hlslice) were accepted (timing not recorded: my `/usr/bin/time` was missing).
5. **Custom xfade expression: a slanted wipe with a green leading band and eased progress.** Two traps found by test: (a) **`P` runs from 1 down to 0**, so use `1-P` for "progress"; (b) using `st()/ld()` registers inside `expr` produced **noisy/garbled pixels** with default threading; adding `-filter_threads 1 -filter_complex_threads 1` made the output clean (I infer a race on the shared expression state across slice threads; I did not confirm the mechanism). Safest: avoid `st/ld` and inline the ease expression, or force single-threaded filters. Work in `gbrp` so PLANE 0/1/2 = G/B/R and the band colour is easy to set.
```
ffmpeg -filter_threads 1 -filter_complex_threads 1 \
 -i a.mp4 -i b.mp4 -filter_complex "[0]format=gbrp[a];[1]format=gbrp[b];[a][b]xfade=transition=custom:duration=0.6:offset=0.7:expr='st(0,1-P);st(0,ld(0)*ld(0)*(3-2*ld(0)));st(1,X+Y*0.35);st(2,ld(0)*(W+H*0.35+60)-60);if(lt(ld(1),ld(2)),B,if(lt(ld(1),ld(2)+40),if(eq(PLANE,0),220,if(eq(PLANE,1),90,40)),A))',format=yuv420p" out.mp4
```
   Custom expr 480x270, 2 s: 1.6 s wall (user 5.2 s, multi-thread). Not tested at 1080p.
6. **Matte-driven wipe (most flexible, and my recommendation for the clapper-board wipe):** render a grayscale matte video with numpy (soft-edged growing circle, `m=clip((k*rmax*1.05-r)/edge+0.5,0,1)` with `k=out_cubic(t)`), then `maskedmerge` A and B with the matte. 480x270, 2 s: 0.4 s. A second Pillow-rendered RGBA overlay stream (clapper-board icon spinning, coloured band at the matte edge) can be overlaid on top; any shape (clapper silhouette, logo, diagonal blinds) works because the matte is arbitrary.
```
ffmpeg -i a.mp4 -i b.mp4 -i matte.mp4 -filter_complex "[0]format=gbrp[a];[1]format=gbrp[b];[2]format=gray,format=gbrp[m];[a][b][m]maskedmerge,format=yuv420p" out.mp4
```
7. Camera-shake-free: nothing above translates the whole frame; motion comes only from scale/rotation of discrete elements plus ray rotation. Any "shake" would have to be added explicitly, so avoiding it requires no extra work.

**Design guidance [CLAIMED] for the Taklipu-style look**
- Timeline for a ~2.2 s sting at 30 fps: 0.00-0.25 rays fade/spin up; 0.10-0.60 logo spring-scale (zeta 0.45-0.55, omega 12-16); 0.30 particle burst + impact SFX; 0.45-0.80 tagline pill slides/scales in with `out_back` (stagger 3-5 frames after logo); hold; 1.9-2.2 everything scales to ~1.05 then wipes out (anticipation).
- Ease choice: enters decelerate (out_cubic/out_expo/out_back), exits accelerate (in_cubic), never linear. Stagger elements by 2-5 frames rather than moving all at once.
- Wipe length 0.4-0.6 s, with SFX whoosh starting ~3-6 frames before the visible edge; put the clapper icon on the wipe edge (spinning, `rotate = 360*out_cubic`), and cut to the sting while it is full-screen.
- Output at the project's fps (the repo's zoom_body uses 60 fps; stings can be 30 fps if the main video is 30, otherwise render at the project fps to avoid judder at the join).

### Gaps
- No source found for how Taklipu or other channels build their stings; the "Taklipu look" is only the owner's description. Not able to watch the reference video.
- Not tested: 1080p timing, transparent-overlay (alpha) workflow into the real pipeline, `xfade` custom at 1080p, and whether the `st/ld` noise is thread-race (only inferred).
- Not tested: gl-transitions (ffmpeg-gl-transition) on CPU/EGL-OSMesa; omitted because it needs a custom ffmpeg build.

---

## 2. Animated subscribe / like / bell popup with cursor-click choreography

### Takeaway
A fully procedural Pillow animation (card spring-in, cursor on a Bezier path with ease-in-out, press-scale, click ripple, state flip red "subscribe" to green "subscribed", damped-sine bell ring) rendered at 2x supersample and downscaled works on CPU; test run 3 s at 480x270 produced correct-looking frames.

### Cited Findings
- No external sources found on subscribe-button choreography; findings below are from local test. The spring and ease-out-back curves used are the ones cited in section 1.

### Inferences
**Verified by local test [TESTED]** (6 frames inspected: card visible; cursor mid-travel; hover; press with ripple; flipped green state; bell wobble).

Timeline that was implemented (seconds): 0 card spring-in (`spring(t,0.5,16)`); 0.5-1.4 cursor along cubic Bezier `start=(.85W,.95H)`, controls `(.95W,.60H),(.70W,.50H)`, `end`, eased by `bezier_ease(.45,0,.2,1)`; click at 1.6: button scale `1-0.08*press` for 0.2 s, ripple ring radius `14+60*out_cubic(u)` px fading out over 0.45 s, cursor drawn at `1-0.12*press` scale; at click+0.1 s the button flips to green with `out_back` scale pop and the bell rotates `25*exp(-5*dt)*sin(40*dt)` degrees; exit from 2.6 s by scaling the card down.
```python
def bez(p0,p1,p2,p3,u): return tuple((1-u)**3*a+3*(1-u)**2*u*b+3*(1-u)*u*u*c+u**3*d for a,b,c,d in zip(p0,p1,p2,p3))
def cursor(d,x,y,s=1.0,SS=2):   # classic arrow polygon, white fill, black outline
    pts=[(0,0),(0,17),(4.5,13),(8,21),(11,19.5),(7.5,12),(13,12)]
    d.polygon([(x+px*s*SS,y+py*s*SS) for px,py in pts],fill=(255,255,255),outline=(0,0,0))
press = clamp(1-abs(t-(CLICK+0.05))/0.1)          # triangle pulse 0..1..0 over 0.2 s
ang = 25*math.exp(-5*(t-CLICK-0.1))*math.sin(40*(t-CLICK-0.1))   # bell ring (deg)
```
Pitfalls found in this test:
- **Heebo has no check-mark glyph (U+2713)**: it rendered as a tofu box in "נרשם ✓". Draw the tick as a polygon/line, or use a font that has it.
- My first version ended the cursor at a hard-coded point that missed the button centre. Compute the cursor target from the button's geometry (button centre plus a small offset toward the cursor tip) and sync the click time to the SFX.
- Hebrew label rendering needed `direction="rtl"` with Raqm; `anchor="mm"` works for centering.
- Render shapes at 2x and downsample with LANCZOS for anti-aliased edges (Pillow's polygon/ellipse are aliased otherwise).
- Composite the popup as an RGBA overlay stream over the body (ffmpeg `overlay` with `enable='between(t,a,b)'`, or pre-render to a transparent-capable mp4/PNG sequence; **I did not test alpha-carrying codecs** (qtrle/prores 4444/png sequence) through ffmpeg, so verify before relying on them).

**Choreography rules [CLAIMED]**: (1) cursor enters from outside the card edge toward the button, with slight overshoot then settle (ease-out-back on the last 20% of the path); (2) cursor path is an arc, not a straight line; (3) click = press-scale 90-92% for 2-4 frames + ripple + "tick" SFX in sync, then state change on the next frame; (4) bell rings only after subscribe (gives like -> subscribe -> bell order); (5) keep the whole popup under ~3.5 s; (6) show it once, early (the channel does 4 s into the body, fine), not over the face-cam or captions; place it away from the corner logo bug.

### Gaps
- No reference on Taklipu's actual popup. No test of alpha overlay pipeline or of the real brand art.

---

## 3. Lower-thirds, context labels, corner logo bug, progress/chapter titles

### Takeaway
No sourced material was found on these conventions for stream-clip channels; the actionable design is implementable with the same Pillow tools (rounded pill + text in Heebo, spring in, hold, ease out) and a persistent PNG logo bug via ffmpeg `overlay`.

### Cited Findings
- Vertical-short UI safe-zone guidance (third-party, figures disagree): keep critical text out of roughly the bottom 25% and the right ~15% edge on Shorts-style 9:16; usable area suggested ~984x1500 px centred; right-side action column ~120 px — [reap.video](https://reap.video/blog/short-form-video-safe-zones), [blitzcut](https://blitzcutai.com/blog/safe-zones-youtube-shorts-reels-tiktok), [clipspeed](https://www.clipspeed.ai/blog/youtube-shorts-size.html). **These apply to 9:16 only; the channel's output is 16:9 (1920x1080), where the usual title-safe convention is ~5% margin [CLAIMED].** I found no official YouTube safe-area spec.

### Inferences
**[CLAIMED], implementation notes (not tested except the Pillow pill/text rendering used in section 2/6):**
- Corner logo bug: persistent, 60-70% opacity, ~8-10% of frame width max, top-left or top-right depending on where the facecam/Kick UI is; fade in 0.4 s after the sting, never during the cold-open or popup; implement as `overlay=W-w-40:40` with a pre-scaled RGBA PNG; for the "alive" feel add a subtle 0.5 s spring pop at each chapter change instead of continuous animation.
- Context label (what is happening): short Hebrew pill, auto-generated from the topic/keyword detector already in `scripts/topics.py`/`config.py` (e.g. "הרגע שבו...", game name, "לייב"), appear 0.3-0.5 s into the shot, 2-3 s hold, slide in from the reading side (right for Hebrew), exit by reversing. Max ~25 characters, 1 line.
- Chapter/progress title between segments (for compilations): number badge + title, shown with the matte wipe in section 1; a thin progress bar (width = elapsed/total) along the bottom edge in brand green; for compilations a "#3/10" counter.
- Make label background a semi-opaque dark rounded rectangle (alpha ~0.75) with brand-green accent bar; text white; stroke not needed over a solid pill (stroke is for captions on raw video).
- Keep labels off the caption zone: captions live in the lower third; labels at top or lower-left/right band above captions.

### Gaps
- No source on conventions used by top clip channels (Israeli or global). Needs a visual review of real channels, which was not possible with the tools here.

---

## 4. Purposeful zoom/crop; layout detection and reframing for desktop-share and game+facecam

### Takeaway
Zoom only when it is motivated by content: emphasis on a reaction/punchline, or necessity (small UI/text unreadable at 1080p). Implement reframing as a "virtual camera" that holds still, then makes rare, eased moves between detected regions of interest, instead of per-frame tracking; detect the facecam with a face detector (YuNet via OpenCV) and the main content with block-based frame-difference activity.

### Cited Findings
- Editors zoom on a specific beat (a reaction, a key line, a detail the viewer needs); subtle movement is preferred for talking heads; a punch-in on a face at a key line needs no second camera — [PremiumBeat](https://www.premiumbeat.com/blog/mastering-zoom-and-punch-in), [Tella](https://help.tella.com/article/punch-in-zoom-in-on-your-camera).
- Vendor guidance: gentle ~8-12% zoom over ~0.5 s for reactions; sharp 3-6 frame zooms for punchlines; do not use zooms to cover weak pacing; linear keyframes look mechanical so ease them; do not exceed source resolution — [Quso](https://quso.ai/blog/zoom-in-on-video.html), [Premiere Copilot](https://www.premierecopilot.com/blog/auto-zoom-ai-emotion-detection-premiere-pro) (the latter is a vendor selling an auto-zoom tool and says most auto-zooms are arbitrary; treat as a sales claim).
- No source specifically on streamer-clip or Israeli clip-channel zoom norms was found.

### Inferences
**Policy [CLAIMED, derived from the sources above + owner feedback]**
- Allowed zoom triggers (all content-motivated): (a) *legibility*: the important region (game window, chat, UI text) occupies < ~45% of the frame and is therefore small, so reframe to it once per segment; (b) *facecam reaction*: audio energy peak + laughter/shout + face present, so a one-time 1.10-1.15x push-in on the facecam or an enlarged facecam inset; (c) *reveal*: cursor/loot/score detail; every zoom has an explicit cause and a matching un-zoom when the cause ends.
- Banned: fixed periodic zooms, random zooms over the whole frame, zooms during talking without a peak, zooms that cut off a speaker or the subject. Replace `scripts/zoom_body.py`'s hand-listed 1.18x punch-ins with the planner below, and let it return "no zoom" most of the time.
- Cap rate: at most one reframe move per ~6-8 s; hold min 1.5-2 s; ease durations 0.6-1.0 s (ease-in-out or out_cubic); no moves inside a caption word burst.

**Verified by local test [TESTED]**

1. *Virtual camera in pure ffmpeg* (no zoompan jitter): `crop` w/h are not re-evaluated per frame, so scale with `eval=frame` then fixed-size `crop` with an `x` expression. Ran on 640x360 synthetic: zoom 1.0 to 1.6x with simultaneous pan, ease-out cubic, visually smooth. Use inline expressions (no `st/ld`, see section 1). **Caveat**: crop positions are integer pixels, so very slow pans (a few px/s) can step; keep glides >= ~0.6 s and >= ~60 px, or crop from a pre-upscaled source [CLAIMED].
```python
def ease_out_cubic(t0,t1):
    u=f"clip((t-{t0})/{t1-t0},0,1)"; return f"(1-pow(1-{u},3))"
s=ease_out_cubic(1.0,2.2)
vf=(f"scale=w='iw*(1+0.6*{s})':h='ih*(1+0.6*{s})':eval=frame,"
    f"crop=640:360:x='(iw-640)*0.9*{s}':y='(ih-360)*0.0*{s}',setsar=1")
```
   For several moves per clip, chain terms `+ (x1-x0)*ease(t_a,t_b)` per segment inside one expression (sum of eased deltas, each already clipped to 0..1, avoids if/else nesting).
2. *Stable crop planner* ("hold, then glide"): input noisy detections of desired (cx, cy, zoom); a move triggers only if the target leaves a dead-zone (0.04 of frame in position, 0.08 in zoom) for >= min_hold s. On jitter-only data (sigma 1.2% of frame) it produced **zero** moves; on a genuine change at t=6 s it produced exactly one 0.9 s glide. Latency was 1.6 s after the change (min_hold), but because the pipeline is offline you can back-date the glide start to the time the target first left the dead-zone minus ~0.3 s [CLAIMED fix].
```python
def plan_crop(t, tgt, dead=0.04, glide=0.9, min_hold=1.5):
    tgt=np.asarray(tgt,float); cur=tgt[:int(min_hold/(t[1]-t[0]))].mean(0); segs=[]; since=None
    for k in range(len(t)):
        off=np.abs(tgt[k]-cur); out=(off[:2].max()>dead) or (off[2]>0.08)
        if out and since is None: since=k
        if not out: since=None
        if since is not None and t[k]-t[since]>=min_hold:
            new=tgt[since:k+1].mean(0); segs.append((t[k],t[k]+glide,tuple(cur),tuple(new))); cur=new; since=None
    return segs
```
3. *Active-window detection by frame difference*: decode at 5 fps, gray, 640x360 via ffmpeg rawvideo; abs-diff of consecutive frames, threshold 12; per 8x8-block fraction of changed pixels averaged over time; threshold 0.08; connected components on the block grid; bbox of the largest component. On a synthetic desktop (static grey UI, an animated 400x240 "game" window at (120,60), a tiny noisy facecam at top right) it returned the main window as (120,64,520,296) vs truth (120,60,520,300). The sparse facecam region was only picked up as small fragments, so motion alone is **not** adequate for the facecam: use a face detector. Memory: all 30 gray frames of 640x360 in RAM; for long clips process in chunks of ~60 s.
   Block size must divide the frame (360/16 failed: use 8, or crop the frame).
4. *Face detector feasibility*: OpenCV `FaceDetectorYN` (YuNet) with the ONNX model `face_detection_yunet_2023mar.onnx` (232,589 bytes, from the `opencv_zoo` repo; the plain `raw` github URL returned a "GitHub access not enabled for this session" JSON, while `https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx` returned the real model) loads in OpenCV 5.0.0 and runs at **8.3 ms/frame at 640x360 on CPU**. I had no real face footage, so **accuracy was NOT tested** (only "no face" on a synthetic frame). Vendor the model file into the repo/CI cache instead of downloading in CI. The OpenCV pip wheel here does not ship Haar cascades, so Haar is not an offline fallback. (YuNet's licence is MIT per my memory; verify before committing the file [CLAIMED].)

**Detection design [CLAIMED]**
- Layout classes: (A) full-screen game with overlaid cam (original layout in `DEFAULT_LAYOUT`) -> keep as is; (B) game + separate facecam window; (C) desktop share (browser, Kick page, tabs, small cam). Decide per segment from: face box size relative to frame (cam < ~6% frame area and in a corner => B/C), browser chrome detection (long horizontal edges at the top, repeated tab strips), and fraction of frame that is active (A: > 60%, C: < 40%).
- Region of interest for C: the largest high-activity component (above), optionally refined with the cursor/focus window; pad 6-8% and snap to 16:9 aspect; reject boxes whose area < 18% of the frame (not worth zooming) or > 85% (no reframe needed).
- Composition for B/C: output either (1) one reframe to content window with the cam as a rounded inset in a corner (cam ~22-26% width, never covering content), or (2) split layout (content 2/3, cam 1/3). Rule of thirds: place the face's eye line near the upper third line; leave lead room in the gaze direction; for cam crops include headroom ~ 10-15% of crop height.
- Smooth tracked values with the hold/glide planner or, if continuous tracking is unavoidable, a critically damped smoother or One Euro filter [CLAIMED; not tested]; run detection every 0.5-1 s, not per frame.
- Trigger only on sustained changes (>= 1.5 s), never on a single frame detection; keep a per-source cache of the facecam box and re-verify every ~30 s since the owner's layout is stable.
- Use cropdetect only for black borders; it does not find windows (not tested).

### Gaps
- Face and window detection not tested on real stream footage (none available offline, and no network access to VOD from this environment). Thresholds (0.08 activity, 12 diff) come from a synthetic scene only.
- No quantified data on how Israeli stream-clip channels use zooms.

---

## 5. Sound design: whoosh/impact placement, ducking, loudness, free sources

### Takeaway
Place a whoosh 3-6 frames before the visual transition edge and an impact on the logo "land" frame; duck music under speech by about 12-16 dB with look-ahead; finish with two-pass linear loudnorm to -14 LUFS / -1.5 dBTP. **The commonly quoted `sidechaincompress` thresholds (0.02 to 0.05) did not duck in my test; thresholds near 0.003 were needed**, so calibrate or use the numpy envelope below.

### Cited Findings
- YouTube plays back at roughly -14 LUFS integrated; louder content is turned down, quieter is not turned up; true peak near -1 dBTP is common advice — [MeterPlugs](https://www.meterplugs.com/blog/2019/09/18/youtube-changes-loudness-reference-to-14-lufs.html), [convertintomp4](https://convertintomp4.com/blog/how-to-convert-audio-for-youtube), [frame.io](https://workflow.frame.io/guide/loudness-for-youtube). These are secondary sources; the official YouTube help page was not found/read.
- Typical command: `loudnorm=I=-14:TP=-1.0:LRA=7` (some sources use LRA=11); duck first, then normalise the mix — [ffmpeg-cookbook audio ducking](https://ffmpeg-cookbook.pages.dev/en/articles/audio-ducking/), [DEV article](https://dev.to/javidjamae/how-to-normalize-audio-with-ffmpeg-volume-loudnorm-and-api-11cb). The cookbook suggests `sidechaincompress` threshold ~0.02-0.05, ratio 4-8, attack/release tens to hundreds of ms.
- Licences (third-party summaries; verify on each site's licence page): Pixabay and Mixkit sound effects are commonly described as free for commercial use without attribution, but a licence does not prevent Content ID claims, and one source says Pixabay prohibits registering the audio in Content ID (single weak source); Mixkit sources conflict (check per-file notice); Freesound is per-file: CC0 is safe, CC BY needs credit, CC BY-NC is unsuitable for monetised videos — [gyre.pro](https://gyre.pro/es/blog/top--websites-with-free-sound-effects), [studio-47o guide](https://studio-47o.pages.dev/en/blog/post/free-music-copyright-guide), [wyzowl](https://wyzowl.com/free-sound-effects-sites/), [vidIQ on YouTube Audio Library](https://vidiq.com/blog/post/royalty-free-music-youtube-audio-library/).

### Inferences
**Verified by local test [TESTED]** (6 s synthetic: 220 Hz tone as "voice" during 2-4 s at 0.3 amplitude; pink noise "music" at -29 dB RMS):

1. `sidechaincompress` depth during the voice window (music RMS change vs original):
   | params | depth in voice | note |
   |---|---|---|
   | threshold=0.05 ratio=4 attack=20 release=400 | 0.0 dB | no ducking |
   | threshold=0.02 ratio=10 attack=15 release=350 | -2.1 dB | weak |
   | threshold=0.01 ratio=20 attack=10 release=300 | -7.6 dB | |
   | threshold=0.003 ratio=8 attack=20 release=400 knee=2 | -16.0 dB | recovery at 4.0-4.3 s still -9.6 dB (slow release), back to 0 by 4.6 s |
   I have not worked out why a 0.3-amplitude sine does not trigger threshold 0.05 (the filter detects RMS, and a sine of peak 0.3 has RMS ~0.21, which should exceed it); this suggests detection/knee behaviour differs from the tutorials' assumptions. Treat the table as empirical for this ffmpeg build only and re-measure with real speech.
2. **Deterministic numpy ducker (recommended, controllable, with look-ahead)**: 10 ms RMS frames of the voice track, speech = frames within 18 dB of the voice's own 95th-percentile level, shift 80 ms earlier (look-ahead), target gain -14 dB, one-pole smoothing (60 ms attack, 450 ms release), upsample the gain curve, multiply music, then `amix=normalize=0`. Measured: -14.0 dB during speech, -8.6 dB at 0.0-0.3 s after speech ends, -1.5 dB after 0.6-1.0 s (smooth recovery). Real speech has gaps; apply a 250 ms hold/gap-closing so music does not pump between words (I wrote the line but my gap-closing code was a no-op placeholder: not tested).
```python
hop=int(.01*sr); rms=np.array([np.sqrt((v[i*hop:(i+1)*hop]**2).mean()) for i in range(len(v)//hop)])
db=20*np.log10(rms+1e-9); speech=db>(np.percentile(db,95)-18)
speech=np.roll(speech,-8)                                    # 80 ms look-ahead
target=np.where(speech,10**(-14/20),1.0); g=np.zeros(len(target)); cur=1.0
a_att=1-np.exp(-0.01/0.060); a_rel=1-np.exp(-0.01/0.450)
for i,tg in enumerate(target):
    cur+=(a_att if tg<cur else a_rel)*(tg-cur); g[i]=cur
G=np.repeat(g,hop); music_ducked=music[:len(G)]*G[:,None]
```
3. **Two-pass linear loudnorm**: pass 1 `loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json` -> pass 2 with `measured_I/TP/LRA/thresh`, `offset=target_offset`, `linear=true`. Result on the 6 s mix: **-13.9 LUFS integrated, -2.8 dBTP** (first-pass input -28.33 LUFS). Single-pass dynamic mode on the same file gave -13.97 LUFS. loudnorm needs sufficient programme length; very short stings are better normalised as part of the full clip (the 6 s test is already at the edge) [CLAIMED].
```python
m=json.loads(re.search(r"\{.*?\}", stderr, re.S).group(0))      # from pass-1 stderr
af=f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true"
```
4. SFX placement via `adelay` + `amix=inputs=N:normalize=0:duration=first`; ran with the repo's `whoosh.wav` at 1.5 s and `boom.wav` at 2.1 s on the test mix without error (placement accuracy not measured). `amix` without `normalize=0` would lower every input by 1/N, which is why `normalize=0` is used.

**Design rules [CLAIMED]**
- Whoosh: starts 3-6 frames (100-200 ms) before the visual edge so its peak coincides with the full-coverage frame; impact/"boom" on the logo landing frame; "tick"/pop on the cursor click; "ding" on subscribed; a short riser (0.5-1 s) before the sting peak if the cold-open ends on a cliffhanger.
- Level: SFX ~ -12 to -18 dBFS peaks under speech, ~ -6 dBFS during silent stings; music bed 18-24 dB below speech peaks during talk, rising 6-8 dB under stings and wipes; high-pass music at ~100-150 Hz and low-pass at ~10-12 kHz so it does not mask speech.
- Use per-SFX micro-variation (random 0.97-1.03 pitch/speed with `asetrate`/`atempo`, +-1 dB) so repeated wooshes do not sound mechanical.
- Normalise the final file once (two-pass), not each stage; true-peak limit with `alimiter=limit=0.89` before loudnorm if clipping occurs (not tested).
- Source licensing: prefer CC0 (Freesound CC0 filter, Kenney audio packs [CLAIMED CC0], Pixabay) and synthesise sounds in code (numpy; the repo's `assets/sfx` already appears generated, unverified origin); keep a `LICENSES.md` per asset with URL/licence/date for Content ID disputes. Avoid any music with Content ID registration risk on monetised channels.

### Gaps
- Official YouTube loudness page and the official licence pages (Pixabay, Mixkit, Freesound) not read; all licence statements are second-hand.
- The ducking-threshold discrepancy is unexplained; real-speech test pending.

---

## 6. Caption design in Hebrew (RTL, size/position, stroke, brand colours, word-by-word vs phrase)

### Takeaway
Pillow with Raqm renders Hebrew correctly (including digits, hyphen and embedded Latin words) when you pass `direction="rtl"` and let Raqm do shaping/bidi; do not additionally run python-bidi (double reversal). Lay out word-by-word captions by shaping each word separately and placing words right-to-left; highlight the active word in brand green with a thick black stroke.

### Cited Findings
- Pillow: `direction` ('rtl','ltr','ttb') requires libraqm; `Layout.BASIC` does not support direction; check with `PIL.features.check_feature("raqm")`; wheels since 8.2.0 bundle a modified libraqm that loads libfribidi at runtime — [Pillow ImageFont docs](https://pillow.readthedocs.io/en/latest/reference/ImageFont.html). If Raqm is absent, one must reorder with python-bidi/arabic-reshaper, but not when Raqm is present, to avoid double reversal (that advice is from third-party Arabic examples, not Hebrew-specific).
- Netflix subtitle norms in general: 42 chars/line for most languages, 17 cps for adults, max 2 lines (single line preferred) — [Netflix general requirements](https://backlothelp.netflix.com/hc/en-us/articles/215758617) and language guides listed in search; **the Hebrew-specific Netflix guide was not found**, so these are other-language norms.
- Caption placement for vertical short-form: lower-middle, above bottom UI, clear of the right action column — [blitzcut](https://blitzcutai.com/blog/best-caption-placement-short-form-video), [reap.video](https://reap.video/blog/short-form-video-safe-zones). Third-party; these apply to 9:16.

### Inferences
**Verified by local test [TESTED]** (rendered 1080x360 PNG, inspected): both lines rendered with correct glyph shaping and RTL order: `וואו איך הוא פספס את זה ב-2 שניות` (digit/hyphen after a Hebrew prefix displayed as "2-ב" visually, which is correct bidi) and `הוא שיחק ב Kick עם 100 חיים` (Latin word and number positioned correctly). Active word highlighted in green `(34,220,100)`, white others, 8 px black stroke at 64 px size, Heebo variable font weight 800 (`font.set_variation_by_axes([800])` worked).
```python
FONT="/usr/share/fonts/truetype/sand-box/google/Heebo/Heebo-VariableFont_wght.ttf"
def font(size,wght=800):
    f=ImageFont.truetype(FONT,size,layout_engine=ImageFont.Layout.RAQM); f.set_variation_by_axes([wght]); return f
def draw_line(img,words,active,cx,y,size=64,stroke=8,base=(255,255,255),hi=(34,220,100)):
    d=ImageDraw.Draw(img); f=font(size)
    sp=f.getlength(" ",direction="rtl")*0.9
    ws=[f.getlength(w,direction="rtl") for w in words]            # words in LOGICAL order
    x=cx+(sum(ws)+sp*(len(words)-1))/2                            # start at the right edge
    for i,w in enumerate(words):
        x-=ws[i]
        d.text((x,y),w,font=f,fill=hi if i==active else base,stroke_width=stroke,stroke_fill=(0,0,0),direction="rtl")
        x-=sp
```
Known limitation of per-word layout: a multi-word Latin phrase or number sequence ("Call of Duty", "2 000") inside a Hebrew line is placed right-to-left word order, which is visually reversed relative to proper bidi; for such lines render the whole line with Raqm and highlight by redrawing a clipped copy (clip to the word's measured box) or keep Latin phrases as one token [CLAIMED].

**Design rules [CLAIMED]**
- Size for 1080p 16:9: 56-72 px cap height-equivalent (font size ~64-80 px), max ~28-32 chars per line, 1-2 lines; stroke 6-10 px black (or dark with soft shadow) outside the glyph; brand green highlight only on the active word; avoid green-on-green backgrounds by always having the stroke.
- Position: lower third, centre at ~80-85% of height (the repo's `caption_png` already uses y_frac=0.80); keep inside 5% title-safe margins; avoid covering the facecam and the corner logo; in reframed desktop layouts place captions in the main content's lower area, not inside the small cam.
- Word-by-word (pop/highlight) suits short punchy hype moments and stream clips; phrase-level (2 lines, all words visible, active-word highlight only) is easier to read for long sentences. A hybrid works well: show groups of 2-5 words (a phrase) with the active-word highlight, group boundaries at pauses > 150-200 ms or punctuation. Minimum on-screen time per group >= ~0.7 s unless a single word is shorter by speech [CLAIMED].
- Timing: from faster-whisper word timestamps, but add 40-80 ms lead (appear slightly before the word is spoken) and fix words with zero or overlapping duration; snap group ends to the next group start minus 1 frame to avoid flicker.
- Pop animation for each new group: scale 0.85 to 1.0 via `out_back` over 4-5 frames (alpha 0 to 1 over 3 frames).
- Common mistakes [CLAIMED]: (1) using `Layout.BASIC` or python-bidi together with Raqm -> reversed/garbled text; (2) punctuation at the wrong end (neutral characters at line edges flip under bidi, so wrap the line with U+200F RLM marks if a trailing "?" or "!" lands on the wrong side; not tested); (3) stroke on a variable font with overlapping contours creating inner artifacts (not seen at weight 800 here); (4) missing glyphs (tofu) for symbols/emoji (seen with U+2713); (5) captions colliding with UI/popup/logo; (6) too long lines on mobile; (7) font fallback for Latin handles (Heebo has Latin, so Kick/English words rendered fine).

### Gaps
- Hebrew-specific subtitle norms (chars per line, cps) not found; Netflix Hebrew guide not retrievable. No Israeli channel's actual caption style was reviewed.
- RLM-wrapping effect and Latin multi-word bidi were not tested.

---

## 7. Pacing: jump cuts, dead-air removal, B-roll/meme inserts, end screen

### Takeaway
Use auto-editor-style audio-threshold silence removal with margins (default 0.2 s) plus keyword/energy protection for comedic beats; cut at word boundaries from Whisper timestamps; meme/B-roll inserts and the end screen can be built with the same overlay/xfade tools. Little sourced material exists for comedic-timing rules, so those are working hypotheses.

### Cited Findings
- auto-editor: `--margin` pads kept sections (default 0.2 s; asymmetric `--margin 0.3s,1.5sec` supported); `--edit audio:threshold=0.04` default in 23.x/29.x, or in dB (`audio:threshold=-19dB`); newer README uses labelled segments (`--edit:2 audio:-12dB --when:2 speed:1.5`, 0 = silent/cut, 1 = active); older docs use `--silent-speed`/`--video-speed` (preview cuts with video-speed 99999, silent-speed 1) — [auto-editor README (WyattBlue)](https://github.com/wyattblue/auto-editor), [PyPI](https://pypi.org/project/auto-editor). Syntax differs by version; the repo pins 29.3.1, so verify with `auto-editor --help` there (not installed locally, not tested).

### Inferences
**[CLAIMED], no tests run in this section:**
- Dead-air policy: remove pauses > 0.6-0.8 s (keep ~0.25-0.35 s of the pause as "breathing room"), tighten 0.3-0.6 s pauses by ~40%, but **never cut** (a) the 0.5-1.5 s beat right before/after a laugh, scream, or punchline, (b) the pause after a question before the answer when the answer is the joke, (c) game-audio reaction moments (explosion, kill, fail): protect these by marking windows around audio-energy peaks, laughter, and keyword hits (`KEYWORD_GROUPS` in `scripts/config.py`) as untouchable.
- Cut points: snap cut boundaries to word edges from the ASR output +- 60-100 ms; add 2-4 frame audio crossfades (`acrossfade=d=0.03`) to avoid clicks; align video cut to the audio cut; if two kept segments come from different moments (non-contiguous), consider a brief J-cut/L-cut (audio leads video by ~0.15-0.3 s) rather than hard simultaneous cuts.
- Jump-cut cadence: with a static facecam, a new "visual event" (cut to a different sub-shot, caption group pop, label, zoom/crop move with a cause) every ~3-6 s keeps attention; do not add motion that has no content cause (owner's rule).
- B-roll / meme inserts: only when a reaction line names a thing or the clip has a clear punchline; 0.8-1.5 s duration; slide/scale-in with `out_back`; SFX tied; keep a library of CC0/own-made reaction stickers (Pillow-drawn emoji/speech-bubbles); avoid copyrighted memes with Content ID risk on monetised videos; ensure inserts do not cover captions.
- End screen (YouTube end-screen elements need 5-20 s of end-screen space [CLAIMED, check YouTube help]): last 8-12 s, background = darkened/blurred last frame (`gblur=sigma=20`, `eq=brightness=-0.15`), two video-slot rectangles and a subscribe-circle area pre-drawn as brand-coloured placeholders (YouTube places the actual elements in Studio), logo bounce-in with the spring, "הרשמו" text, and quiet music tail. Fade out last 0.5 s.
- Compilation pacing: sting (<=2.2 s) at start; chapter wipes between clips of 0.5 s; vary clip length 12-35 s; put the strongest clip in the first 3 and the cold-open three-shot as already done.

### Gaps
- No sourced guidance on comedic-timing-safe silence removal, nor on end-screen specs; nothing tested here. auto-editor 29.3.1 flag syntax for protected windows not verified.

---

## Priority list for the pipeline upgrade (derived; ordered by owner-visible impact per effort)

1. Replace the static sting with the pre-rendered animated sting (sunburst + spring logo + particles + tagline pill) and the matte-wipe with clapper icon between cold-open and body (section 1). Cheap, cached, tested core.
2. Animated popup with cursor click and state flip (section 2): fix tick glyph, compute cursor target from button geometry.
3. Remove `zoom_body.py` arbitrary punch-ins; introduce the hold/glide virtual-camera planner with content-motivated triggers only (section 4), starting with legibility reframes for desktop-share segments.
4. Add persistent corner logo bug + context-label pill (section 3).
5. Sound design: SFX at transitions, numpy ducking with look-ahead, final two-pass loudnorm -14 LUFS / -1.5 dBTP (section 5).
6. Caption refinements (section 6): phrase groups with active-word highlight, lead time, pop animation.
7. Pacing protections (section 7) once reframing and branding are in place.

## Test artifacts (scratchpad, may be cleared)
`/tmp/claude-0/-home-user-oded-highlights/9afff02d-82b9-5aa1-8251-aa0bcb4c3a4d/scratchpad/t/` contains motion.py (easings + sunburst), t1.py (sting), sub.py (subscribe/cursor), cap.py (Hebrew captions), duck.py/duck2.py (ducking), vcam.py, plan.py, region.py, and the sample outputs (sting.mp4, sub.mp4, xf_custom1.mp4, iris.mp4, cap.png, strips).

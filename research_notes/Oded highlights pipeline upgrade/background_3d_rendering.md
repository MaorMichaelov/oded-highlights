# Free headless CPU 3D rendering of topic background plates (YouTube thumbnails)

Date of tests: 2026-11-14. Machine: Linux 6.18, 4 vCPU, 15 GB RAM, Python 3.13.18, Node 22, no GPU. "Measured" = run in this session; scripts are saved in `background_3d_scripts/` next to this file (law_office.py, post.py, ph_get.py, threejs_room.html, threejs_shot.js). Test render: `/home/user/oded-highlights/assets/plates3d/test_blender.png` (1280x720, Cycles CPU 48 spp + OIDN + numpy post).

## 1. Is Blender headless on CPU (bpy pip module / Cycles + OpenImageDenoise) feasible, with what install, time, memory, recipe?

### Takeaway
Yes. `pip install bpy==5.3.0` works from PyPI in this sandbox (427 MB wheel, ~1.2 GB installed in a venv, Python 3.13 only), Cycles CPU + OIDN rendered a 1280x720 interior in 127 s at 48 spp (adaptive) with ~0.8 GB RSS (at 640x360). EEVEE does NOT work here (no libEGL/Vulkan), so Cycles is the engine. The result looks like a clean "Pixar/Unreal-lite" 3D room, clearly better than Pillow vector art, but still "primitive-built" until real assets and post-grade are added.

### Cited Findings
- PyPI has `bpy` 5.3.0 (also 5.2.x, 5.1.x); Linux wheel is `bpy-5.3.0-cp313-cp313-manylinux_2_28_x86_64.whl`, 427 MB; requires Python ==3.13.*; licence GPL-3.0 — [PyPI JSON API](https://pypi.org/pypi/bpy/5.3.0/json)
- Measured: `python3 -m venv v && v/bin/pip install bpy==5.3.0 numpy pillow scipy` succeeded in about 1-2 min on this proxy; venv size 1.2 GB; `import bpy; bpy.app.version_string` -> `5.3.0` — measured here (venv /tmp/claude-0/bpyenv)
- Blender download host `download.blender.org` is NOT reachable through the session proxy (connect refused), so the official binary/tarball route is unavailable here; the pip wheel is the only route in this environment — measured here with curl
- Measured render times (Cycles CPU, OIDN denoise, adaptive sampling threshold 0.03, AgX tonemap, volumetric haze cube + DOF + 4 area lights + 1 spot + 1 point, ~900 mesh objects): 640x360 @ 24 spp = 15.4-18.9 s (render only; about 26 s wall incl. bpy import and scene build); 1280x720 @ 48 spp = 126.7 s render (137 s wall) — measured here with law_office.py
- Measured peak RSS (resource.getrusage) for the 640x360 @ 24 spp run: 782 MB. 720p not separately measured; expect roughly 1-1.5 GB for such a scene (inference) — measured here (memwrap test)
- EEVEE/EEVEE Next: `bpy` in this container prints "Unable to initialize a Vulkan 1.1 instance" and "Couldn't open libEGL.so.1" and the process aborts when rendering with EEVEE; no GPU/GL context. Installing Mesa (llvmpipe) via apt was not attempted (not tested whether apt is reachable) — measured here (eevee.py). Workbench engine was not reached because the process aborted first.
- Blender 5.x API changes that broke older scripts: `Scene.node_tree` is gone (compositor now `scene.compositing_node_group`), `use_nodes` is deprecated (removal planned for 6.0), Principled inputs are named `Coat Weight`, `Emission Color/Strength`; AgX is the default view transform (`sc.view_settings.look='AgX - Medium High Contrast'`) — observed here (DeprecationWarnings and AttributeError 'Scene' object has no attribute 'node_tree')
- Cycles settings that matter for speed on CPU: adaptive sampling, `sample_clamp_indirect=8`, bounces 6/3/4, `volume_bounces=1`, `volume_step_rate=2`, haze density ~0.011 in an enclosing cube (0.035 blew out to milky overexposure) — measured here (two iterations of law_office.py)
- Poly Haven glTF models import into bpy in 0.04-0.06 s (`bpy.ops.import_scene.gltf`) with textures resolved from the `textures/` folder — measured here with `wooden_bookshelf_worn`

### Working recipe (copy-paste)
```bash
python3 -m venv /opt/bpyenv && /opt/bpyenv/bin/pip install bpy==5.3.0 numpy pillow scipy
# build + render (script in background_3d_scripts/law_office.py): args = out.png W H samples
/opt/bpyenv/bin/python -W ignore law_office.py raw.png 1280 720 48     # ~2 min on 4 vCPU
/opt/bpyenv/bin/python post.py raw.png plate.png                       # bloom, lens blur, left-dark ramp, vignette, grain, split tone (~2 s)
```
law_office.py builds from primitives: room shell, wainscot, 6-shelf bookcase with ~400 randomly sized/coloured books with gold spine labels, desk with leather blotter, stacked law books, brass scales (cylinders + pans), gavel, banker's lamp (emissive bulb + point light), framed certificates, window with cool emissive pane; lights = warm RECTANGLE area key (right), cool area rim (back-left), warm shelf wash, tiny cool fill, cool SPOT shaft through window; Volume Scatter haze cube (density 0.011, anisotropy 0.55); camera 40 mm f/1.6 with focus empty on desk (DOF); glossy coated floor (Principled `Coat Weight` 0.6). Composition puts bookcase/desk in the right 55% and keeps the left 45% empty dark wall.

### Inferences
- GitHub Actions budget: 1280x720 @ 48 spp = ~2 min; 1920x1080 is 2.25x pixels so ~5 min @ 48 spp, ~13 min @ 128 spp. A 6 h job therefore fits dozens of 1080p plates, but a per-video-topic plate (1 image) is trivially cheap. Only 20 min of job time is needed for ~10 topic plates at 720p/48 spp. (Estimate extrapolated from the measurements above; assumes the runner has 4 vCPU like this machine. GitHub's public-repo standard runner has 4 vCPU/16 GB and private-repo runners have fewer — from memory, not verified in this session; check the repo visibility.)
- Cache the 427 MB wheel with `actions/cache` keyed on `bpy==5.3.0` to avoid re-downloading each run.
- Render 720p and upscale to 1080p only if needed; thumbnails are shown at ~360 px wide in feeds, so 1280x720 is the real target (YouTube thumbnail spec is 1280x720).
- Render at fewer samples than you think: OIDN + post blur hides noise; 32-48 spp is enough for dark moody plates.

### Gaps
- EEVEE software rendering (Mesa llvmpipe) was not tested; libEGL missing and apt/snap reachability not tested. Cycles is the supported path.
- Exact 720p memory not measured; 1080p at 128 spp not tested (to stay inside the "no job over ~3 min" rule).
- GitHub Actions runner specs were not verified from a source in this session.
- Not tested: `bpy` installation on a GitHub runner itself (Python 3.13 must be selected via `actions/setup-python`; wheel is manylinux_2_28 so Ubuntu 22.04/24.04 runners should be fine, but untested).

## 2. Lightweight alternatives (Three.js via Playwright/SwiftShader, Mitsuba 3, pyrender, Panda3D, Open3D, POV-Ray, Filament, numpy tracers): which are worth it?

### Takeaway
Three.js in headless Chromium (SwiftShader) works and is ~100x faster (0.5 s render, 1 s total for 1280x720 with shadows, ACES, bloom, bokeh) but looks like a game prototype without global illumination; it needs heavy lighting tuning to approach Cycles. Mitsuba 3 pip works (scalar_rgb 640x360 Cornell box 32 spp in 2.3 s) but has no asset/material workflow comparable to Blender. Ranking by visual quality per effort: Blender Cycles >> Three.js (+ fake GI tricks) > Mitsuba > everything else.

### Cited Findings
- `require('playwright')` resolves at `/opt/node-tools/node_modules/playwright`; Chromium launched headless with `--use-gl=angle --use-angle=swiftshader --enable-unsafe-swiftshader --ignore-gpu-blocklist --no-sandbox` and WebGL2 worked — measured here (threejs_shot.js)
- three.js is NOT loadable from CDNs here (cdn.jsdelivr.net, unpkg.com, cdnjs.cloudflare.com all refused by the proxy), but `registry.npmjs.org` is reachable: `npm install three@0.170.0` worked and the page serves it locally through an importmap + `python3 -m http.server` — measured here
- Measured: 1280x720 scene (box room, ~400 book boxes, desk, lamp, scales, 3 shadow-casting spot lights, RoomEnvironment IBL, FogExp2, ACES, EffectComposer with BokehPass + UnrealBloomPass + OutputPass) rendered in 441-508 ms inside the page; whole script 0.9-1.2 s including Chromium launch — measured here
- Look of Three.js result: soft shadows, lamp bloom, bokeh OK, but flat Lambert-like lit surfaces, no bounce light, no volumetric shafts; my first light values were far too dim (spot candela units; needed x7) and I mirrored the scene with `scene.scale.x=-1` which also mirrored light positions so the second image has the light placed wrongly. It was not tuned further; treat as an untuned prototype, not a final look — measured here (look judged from screenshots, files not kept in repo)
- three.js examples include `GTAOPass`, `SSAOPass`, `SSRPass`, `UnrealBloomPass`, `BokehPass`, `FilmPass`, `OutputPass` (all present in the installed package) — checked in node_modules/three/examples/jsm/postprocessing
- Mitsuba 3: `pip install mitsuba` -> mitsuba 3.9.1 + drjit 1.5.0 (218 MB venv); variants include `scalar_rgb` and `llvm_ad_rgb` (llvm needs libLLVM, not tested); Cornell box 640x360 @ 32 spp `scalar_rgb` = 2.32 s — measured here (mit.py)
- pyrender 0.1.45 (pure python, needs OSMesa/EGL), Panda3D 1.10.16 (~48 MB wheel), Open3D 0.20.0 (~48 MB wheel), trimesh 5.2.1, moderngl 5.13.0 exist on PyPI — [PyPI JSON API](https://pypi.org/pypi/panda3d/json). Not installed or rendered here (need GL/OSMesa which the container lacks; same libEGL problem as EEVEE)

### Inferences
- Three.js only becomes attractive if you need 1-second renders or animation; for still thumbnails a 2-minute Cycles render is cheap. To get Cycles-like look in Three.js you need baked lightmaps, fake volumetric cones (additive cone meshes), env maps, and manual bounce lights — more work than building the scene in Blender.
- Mitsuba is physically beautiful but has no GUI-free asset pipeline for glTF (it imports OBJ/PLY/Blender-exported XML); skip.
- pyrender/Panda3D/Open3D are GL rasterizers and would need Mesa OSMesa/EGL that is missing here; they produce game-like shading and would not beat Three.js. POV-Ray: not installed (`which povray` empty), not tested. Filament: no PyPI-distributed headless renderer was checked. Numpy "raytracing in a weekend" tracers: sphere/plane only, hours of tuning, no meshes — not worth it.

### Gaps
- POV-Ray, Filament, Panda3D offscreen, Open3D, pyrender/OSMesa were not run; judgement is from environment constraints (no GL libs) and general knowledge, not tests.
- Mitsuba `llvm_ad_rgb` variant and a textured/mesh scene were not tested.
- Three.js scene was not tuned; a well-lit Three.js result could look better than the images I saw.

## 3. Free CC0 assets: which exist for our topics, are they reachable/licensed?

### Takeaway
Poly Haven is reachable (API + file downloads) and is all CC0; it has furniture/props (bookshelves, desks, TVs, lamps, street lamps) and 997 HDRIs including `tv_studio`, `stadium_01`, `rostock_laage_airport`, `neon_photostudio`, `cinema_lobby`. It does NOT have scales of justice, gavel, microphone, jewellery/diamond, roulette table, server rack, neon sign, or check-in counter — those must be built procedurally in Blender (easy) or taken from Kenney/Quaternius/Sketchfab which are NOT reachable from this sandbox.

### Cited Findings
- Reachable from this session: `api.polyhaven.com` (HTTP 200), file downloads at `dl.polyhaven.org/file/ph-assets/...` (e.g. Shelf_01.bin 12676 B and `tv_studio_1k.hdr` 1.7 MB downloaded OK; the bare root returns 521 but files work), `registry.npmjs.org`, `pypi.org`. NOT reachable (proxy connect refused): `download.blender.org`, `ambientcg.com`, `kenney.nl`, `quaternius.com`, `api.sketchfab.com`, cdn.jsdelivr/unpkg/cdnjs — measured here with curl
- Poly Haven licence: "Our assets are all licensed as CC0 ... no rights reserved" — [polyhaven.com/license](https://polyhaven.com/license)
- Poly Haven API: `GET https://api.polyhaven.com/assets?t=models|hdris|textures` (522 models, 997 HDRIs, 869 textures at test time), `GET /files/{id}` gives per-format URLs (gltf/fbx/blend/usd, 1k/2k/4k, with `include` map of textures), `GET /info/{id}` gives authors/polycount/dimensions. Send a custom User-Agent. — [API listing queried here](https://api.polyhaven.com/assets?t=models)
- Models relevant to our topics (id : polycount where checked): `wooden_bookshelf_worn` (10 106 tris, 1.37x0.58x2.06 m, imported into bpy OK), `Shelf_01` (182), `wooden_display_shelves_01` (3 174), `steel_frame_shelves_01/02/03` (4 348), `worn_metal_rack`, `book_encyclopedia_set_01`, `decorative_book_set_01`, `metal_office_desk`, `SchoolDesk_01`, `WoodenTable_01/02/03`, `painted_wooden_table`, `desk_lamp_arm_01`, `modern_ceiling_lamp_01`, `Chandelier_01/02/03` (26 860), `hanging_industrial_lamp`, `classic_laptop` (14 450), `Television_01` (1 918), `television_02` (2 310), `projector_screen` (8 727), `security_camera_01/02`, `gamepad` (9 546), `chess_set`, `vintage_suitcase` (16 474), `modern_arm_chair_01`, `bar_chair_round_01`, `modular_street_seating`, `street_lamp_01/02` (30 610), `fire_hydrant`, `concrete_road_barrier`, `modular_electricity_poles`, `modular_fire_escape`, `modular_pipes`, `flood_lights`, `wine_barrel_01`, `wine_bottles_01`, `round_spectacles`, `Camera_01`, `vintage_video_camera`, `vintage_radio_transceiver`, `boombox`, `cassette_player`, `vintage_telephone_wall_clock`, `standing_picture_frame_01/02`, `wooden_candlestick`. Missing in Poly Haven (keyword search for scale/gavel/mic/jewel/diamond/gem/roulette/poker/server/rack/neon/check/luggage/counter/trophy/keyboard/monitor returned none relevant) — queried here
- Poly Haven HDRI ids useful per topic: `tv_studio`, `neon_photostudio`, `colorful_studio`, `studio_small_01..09`, `photo_studio_loft_hall`, `rostock_laage_airport`, `hangar_interior`, `stadium_01`, `stadium_exterior`, `orlando_stadium`, `ushaka_dolphin_stadium`, `cinema_lobby`, `cinema_hall`, `newman_lobby`, `entrance_hall`, `bank_vault`, `decor_shop`, `phone_shop`, `gear_store`, `modern_evening_street`, `cobblestone_street_night`, `urban_street_01..04`, `rooftop_night`, `dresden_station_night`, `warm_restaurant_night`, `billiard_hall`, `unfinished_office(_night)`, `abandoned_games_room_01/02`, `machine_shop_01..03`, `mirrored_hall`, `old_hall`, `music_hall_01/02`, `ballroom`, `circus_arena` — queried here (note: HDRIs are fully photographic, so as a background they are an alternative "plate" with zero modelling; but they are 360 panoramas of real places, usable as blurred backdrop behind primitives)
- Download helper (saved as ph_get.py): fetches `/files/{id}` -> `gltf.1k.gltf` + `include` files; verified for `wooden_bookshelf_worn` (2.7 MB textures) and `street_lamp_01` (2.1 MB) — measured here
- From general knowledge (NOT verified here, hosts unreachable): Kenney.nl (CC0 game kits incl. furniture, city, casino/cards, space), Quaternius (CC0 low-poly packs: furniture, city, modular interiors), ambientCG (CC0 PBR textures), Sketchfab has a CC0 filter but downloads require login/API token. Poly Haven textures cover floor wood/marble/carpet/wall paint equivalents (869 textures reachable via API)

### Inferences
- For the missing props, build procedurally (all <40 lines each in bpy): scales (cylinders + pans, done in the test), gavel (cylinders, done), microphone (sphere + cylinder + mesh-texture via noise bump), diamond (icosphere subdiv 1, flat shading, Glass BSDF IOR 2.42 or Principled Transmission, over an emissive-lit pedestal), jewellery case (box + glass with Transmission 1.0 + inner spot), roulette table (cylinder wheel + torus + green table box + chips as cylinders), server rack (stack of boxes with tiny emissive LED cubes in random green/blue), neon sign (curved tube from `bpy.ops.curve` with bevel + emission strength 15-30 + bloom), check-in counter (long box + emissive screen), broken window (plane with shard-shaped holes = mesh from Voronoi/Cell Fracture addon or a hand-made polygon fan + dark exterior + cool backlight).
- Photoreal quality will come mostly from lighting + HDRI reflections + post, not from props: use a Poly Haven HDRI (e.g. `studio_small_0x` or `neon_photostudio`) at low strength as reflection/ambient source so glossy surfaces reflect something interesting.

### Gaps
- Kenney, Quaternius, ambientCG, Sketchfab licences/asset names could not be verified (hosts blocked). Their licence statements above are from memory only.
- Specific asset IDs for the missing props (scales, gavel, mic, diamond, roulette, rack, neon, check-in) could not be confirmed on any reachable host.
- Poly Haven author/credit text for individual models is not required under CC0 but was not collected.

## 4. What cinematic look tricks matter most, how to keep the left 45% calm, and what is the ranked recommendation?

### Takeaway
Implement in this order: (1) colour-split lighting (warm key right / cool rim back-left), (2) strong tonemap + grade, (3) volumetric haze/shafts, (4) shallow DOF + lens-blur in post, (5) bloom on emissives, (6) glossy floor reflections, (7) grain + vignette. Keep left 45% calm by composition (empty wall/dark negative space), a darkening + desaturation ramp in post, and no emissive objects on the left. Recommended pipeline: bpy Cycles CPU @1280x720, 32-64 spp + OIDN, then numpy post.

### Cited Findings
- Everything below was applied in the test render (`assets/plates3d/test_blender.png`): warm RECTANGLE area light (1.0,0.62,0.32) at 650 W from the right, cool (0.25,0.45,1.0) rim at 420 W from back-left, cool SPOT through the window with haze for a shaft, banker's lamp emissive + point light, f/1.6 DOF, coated floor, bloom/blur/grain in post.py — measured here
- Post chain used (post.py, numpy + Pillow, ~2 s at 720p): 55/45 mix of sharp and Gaussian-blurred (sigma 1.6 px) image for "photographic" softness; bloom = threshold luminance>0.62, three Gaussian radii 6/18/48 px, screen-blend; split-tone (+teal in shadows, +warm in highlights) with smoothstep S-curve; left-side ramp `k = 0.52 + 0.48*smoothstep(x/0.5)` and saturation 0.6->1.0; elliptical vignette centred at 58% width; Gaussian grain sigma 0.018 scaled by (1.2 - luminance) — measured here
- Light values given are Blender watts for an 8 m room; they needed three rounds of reduction (first render was washed out because haze density 0.035 and lights 2x too strong) — measured here
- Pillow-based blur works with standard `ImageFilter.GaussianBlur`; for lens-like bokeh disks instead of Gaussian, use `ImageFilter.BoxBlur` or a disk kernel via scipy `ndimage.convolve` — not tested

### Inferences
- Ranked recommendation:
  1. **Blender bpy + Cycles CPU + OIDN (primary).** Install via PyPI wheel, ~2 min per 720p plate, 0.8-1.5 GB RAM; realistic reflections, GI, volumetrics, glTF import of Poly Haven props. Build one parametrised "room builder" module (floor, walls, shelf, desk, window, light rig) plus a per-topic prop function; keep a cache of the pip wheel. Fits 6 h Actions limit by a wide margin.
  2. **Poly Haven HDRI as the "photo" backdrop + Blender foreground props** (use HDRI strength 0.3 for reflections, optionally render the HDRI sphere blurred as the background): fastest route to believable places (airport, stadium, TV studio, street night) because the environment is real photography, but it is a 360 view of an actual location, so the look is photographic rather than "AI cinematic"; always add the colour-split grade.
  3. **Three.js + Playwright SwiftShader** if sub-second/animated output matters; needs fake GI work. Untuned test looked like a game.
  4. Mitsuba 3, pyrender, Panda3D, Open3D, POV-Ray, numpy tracers: not recommended.
- Honest look assessment: the test plate looks like a clean stylised 3D render, not like Taklipu's AI-generated photoreal scenes: books/desk are simple boxes, no texture detail, uniform wood colour. To close the gap: Poly Haven PBR textures (wood, plaster, marble) with 1k maps, the real `wooden_bookshelf_worn`/furniture models, noise-based roughness variation, a Poly Haven HDRI for reflections, dust/haze particles, and then a light AI/photographic "img2img" pass is the realistic final step (outside this task). A 3-8 px lens blur on the whole plate is acceptable because the portrait and text sit on top and thumbnails are viewed small.
- Left calm 45%: put the shelf/desk subject right of centre (x>=50% of frame), leave the left a low-detail wall and floor; optionally in post darken 30-50% and desaturate; don't light that side with keys or put emissives (monitors, neon) there; use a very dim cool fill only. Mirror composition per topic if the portrait goes right.
- Topic cheat-sheet (all built from primitives + a few Poly Haven props): law office (done); jewellery store (glass boxes with Principled Transmission, spot lights from above, red emissive "broken window" shards, blue/red police rim); airport (long wall of glass with HDRI `rostock_laage_airport` as exterior, rows of boxes as check-in counters, emissive blue signage panels); TV studio (curved emissive LED wall = plane with HDR emission texture, floor reflections, truss lights as cylinders); casino (green felt cylinder table + chips + warm pendant lights + out-of-focus bokeh from emissive spheres); courtroom (wood panelling, raised bench, gavel); gaming room (emissive RGB strips with Emission 10 + bloom, monitor boxes on desk); neon rainy street (wet glossy plane roughness 0.05 reflecting coloured emissive tubes, rain streak planes or post streaks, volume haze); server room (repeated rack boxes with LED emissive cubes, cool blue light, floor reflections); stadium (HDRI `stadium_01`, or instanced light towers + haze).

### Gaps
- Not tested: more than one topic scene (only the law office was built); the jewellery, casino, airport etc. cheat-sheet items are plans, not renders.
- Whether the output beats the current Pillow plates in actual CTR terms is unknown; no A/B data.
- No comparison against Taklipu's actual thumbnails was possible (not fetched in this task); "AI-cinematic" look gap statements are my judgement from the rendered image.
- Bokeh from emissive points: not implemented in the test (the DOF is physical in Cycles; emissive bokeh would appear automatically for out-of-focus emissives such as extra bulbs, but was not tested).

## Quick usage reference
- Test render: `/home/user/oded-highlights/assets/plates3d/test_blender.png` (law office, 1280x720, raw Cycles 48 spp: 127 s; post.py ~2 s)
- Scripts: `/home/user/oded-highlights/research_notes/Oded highlights pipeline upgrade/background_3d_scripts/` (law_office.py, post.py, ph_get.py, threejs_room.html, threejs_shot.js)
- Install venv used for tests (temporary, may be deleted): `/tmp/claude-0/bpyenv`, `/tmp/claude-0/mitenv`, `/tmp/claude-0/three`

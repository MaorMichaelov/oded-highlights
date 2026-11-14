# Free, legally usable REAL photo backgrounds for ODED HIGHLIGHTS thumbnails (tested 2026-11-14)

**How to read this.** "TESTED" = I ran it in this sandbox on 2026-11-14 (curl / Python 3 / OpenCV 5.0.0 / numpy 2.5.3 / Pillow 12.3.0). "Primary" = text I read on the vendor's own page or repo. "Secondary" = WebSearch result summaries; where I put text in quotes that I could only see through a search summary, I say so. Items from my own background knowledge that I could not verify here are labelled "UNVERIFIED (training knowledge)" and are collected under Inferences/Gaps, not Cited Findings. WebFetch uses the same network allowlist as curl, so the licence pages of Pexels, Unsplash, NASA etc. could not be opened (they fail DNS) and must be allowlisted before they can be quoted from the primary page.

---

## Q1. Which hosts are reachable, and what actually works end-to-end (measured access)?

### Takeaway
Only Poly Haven is fully usable today with no key (list, filter, download, project, score: all TESTED). Openverse search works key-less (anonymous quota), and Wikimedia originals download works but throttles quickly. Pexels and Pixabay endpoints are reachable but return "no/invalid key" (owner must create free keys); Unsplash, NASA, Smithsonian, Flickr, LoC, ambientCG, Kenney, Poly Pizza, Sketchfab, rawpixel, StockSnap need allowlisting.

### Cited Findings
TESTED reachability from this sandbox (curl, 2026-11-14, `-m 15`):

| Host | Result | Meaning |
|---|---|---|
| api.polyhaven.com | 200 on `/`, `/types`, `/categories/hdris`, `/assets?t=hdris`, `/files/{id}`, `/info/{id}` | works, no key |
| polyhaven.com | 200 (`/license` page readable) | works |
| dl.polyhaven.org | `/` = 521 (origin error on the bare root), but `/file/ph-assets/...` = 200 | file downloads work (root 521 is irrelevant) |
| cdn.polyhaven.com | `/` = 404, `/asset_img/thumbs/{id}.png?width=512` = 200 (512x384 PNG, 301 KB) | thumbnails work |
| api.pexels.com | `GET /v1/search?query=airport` = **401** with no key | reachable, key needed |
| images.pexels.com | `/` = 404 | reachable; real image URL not tested (no key) |
| pixabay.com | `/api/?q=airport` = **400** "[ERROR 400] Invalid or missing API key"; `/api/docs/` = 200 (read); `/service/license-summary/` = **403 Cloudflare "Just a moment..." challenge** (not bypassed) | API reachable, key needed; licence summary page not readable by script |
| cdn.pixabay.com | one guessed URL gave 403 | INCONCLUSIVE (the URL I guessed may simply not exist); I did not try to evade the block with a browser User-Agent or Referer |
| api.openverse.org | 200 / 302 | works key-less; headers `x-ratelimit-limit-anon_burst: 20/min`, `anon_sustained: 200/day`, `anon_thumbnail: 1000/day` |
| commons.wikimedia.org | `/w/api.php` returned JSON once (200) with extmetadata; before and after that "You are making too many requests to the API" | shared-egress throttling; works intermittently |
| upload.wikimedia.org | original `Example.jpg` = 200; next original (`Oakland_Airport_Terminal_1.jpg`) and a 1920px thumb = **429, `retry-after: 600`** | works but throttled hard from this IP |
| thumb.wikimedia.org | CONNECT tunnel 403 (blocked) | `Special:FilePath?width=` redirects here, so do NOT use FilePath; use `upload.wikimedia.org/.../thumb/...` or originals |
| github.com | `/` = 400; raw.githubusercontent.com = 200 | raw works |
| NOT allowlisted (DNS fails, curl code 000) | unsplash.com, api.unsplash.com, images.unsplash.com, www.pexels.com, help.pexels.com, www.flickr.com, api.flickr.com, live.staticflickr.com, images-assets.nasa.gov, images.nasa.gov, nasa.gov, www.loc.gov, api.si.edu, www.si.edu, ids.si.edu, ambientcg.com, kenney.nl, poly.pizza, sketchfab.com, api.sketchfab.com, images.rawpixel.com, www.rawpixel.com, cdn.stocksnap.io, stocksnap.io, wordpress.org, images.metmuseum.org, openaccess-api.clevelandart.org | "needs allowlisting" |

- Poly Haven end-to-end TESTED: listed 997 HDRIs (1.08 MB JSON in one request), downloaded 3 tonemapped JPGs (all 8192x4096), projected 6 x 1920x1080 plates with numpy/OpenCV, scored them (section Q2, Q7). Source: [api.polyhaven.com/assets?t=hdris](https://api.polyhaven.com/assets?t=hdris).
- Openverse TESTED: `license=cc0,pdm`, `source=wikimedia`, `aspect_ratio=wide`, `size=large`, `category=photograph`, `mature=false` all accepted; "airport terminal" -> 240 hits (anonymous results cap is 240 = 12 pages of 20 per the Apify note, secondary), "casino interior" -> 2 CC0/PDM Wikimedia hits (Model T Casino interior 4624x2966; Casino Luxor Las Vegas 1920x1280). Source: [api.openverse.org/v1/images/](https://api.openverse.org/v1/images/?q=casino%20interior&source=wikimedia&license=cc0,pdm).
- Openverse thumbnail endpoint TESTED: `/v1/images/{id}/thumb/` returns only **600x442** JPEG (36 KB) – too small for a 1280x720 background; full-size URLs point to provider hosts (upload.wikimedia.org works here; images.rawpixel.com and cdn.stocksnap.io do not resolve). Source: [api.openverse.org](https://api.openverse.org/v1/images/de572d46-5136-420c-a0a3-328b290888a5/thumb/).
- Openverse anonymous: official auth doc says registered users get slightly higher limits and more is available on request; exceeding gives 429 — [Openverse docs](https://wordpress.github.io/openverse-api/reference/api/authentication_and_throttling.html) (via search summary). No source found for a specific OAuth daily number.

### Inferences
- In GitHub Actions the egress IP pool is different and unthrottled-by-us; Wikimedia 429s seen here are partly due to this sandbox's shared proxy IP. Still, budget "polite, serial, cached" access for Wikimedia (see Q4).
- The Pixabay cdn 403 is not proven to be a block; retest with a real key and a real hit URL from the API response before drawing conclusions.

### Gaps
- Pexels image download URLs, Pexels/Pixabay/Unsplash real searches: not testable without keys (owner action).
- Every host in the "NOT allowlisted" row is unverified beyond search summaries.

---

## Q2. Poly Haven HDRIs: licence, API, downloads, 16:9 perspective crop, which assets fit

### Takeaway
Poly Haven is the best $0, CC0, no-key, no-attribution source of genuinely real, people-free interiors/exteriors, and the API is explicitly free for commercial use. Coverage is strong for studios, offices, halls, gyms, stations/airport, stadium, streets, rooftops, night streets, bars/restaurants, but there is nothing for casino, server room, jewellery store, courtroom, birthday party, tropical city. The max free non-HDR download is an 8192x4096 tonemapped JPG; a 75-degree crop of it gives ~1707 native px for 1920x1080 (1.12x upscale), which is adequate for thumbnails.

### Cited Findings
**Licence (primary, read at [polyhaven.com/license](https://polyhaven.com/license)):**
- "Our assets are all licensed as CC0, which is effectively Public Domain even in jurisdictions that do not support the Public Domain."
- "You can use our assets for any purpose, including commercial work. You do not need to give credit or attribution when using them (although it is appreciated). You can redistribute them..."
- Website ToS 3.2 forbids "Web scraping or data mining without express permission" and DDoS; ToS 4.1: "All content on this website, excluding the CC0 assets themselves, is protected by intellectual property laws."
- **API ToS (primary, [raw ToS.md](https://raw.githubusercontent.com/Poly-Haven/Public-API/master/ToS.md); also sent as HTTP header `terms-of-service` on every API response):** 2.1 "The API is free to access and use by anyone - individuals, organizations, and companies alike - for any purpose, including commercial use, at no charge." 2.3 "Poly Haven will never require payment, a license, or a key in order to access the API." 2.4 "all API calls must be made with a unique 'Referer' header or user-agent that matches your software name". 2.5 "CC0 assets carry no attribution requirement whatsoever... However, if you use the live API inside your software, website, or service to surface Poly Haven content, you must make it clear to your users where that content comes from." 2.6 no disruptive use. No numeric rate limit is stated; API responses carry `cache-control: max-age=43200` (TESTED header) so cache listings 12 h.

**Endpoints (TESTED, all key-less):**
- `GET https://api.polyhaven.com/types` -> `["hdris","textures","models"]`
- `GET /categories/hdris` -> counts: all 997, natural light 822, outdoor 705, nature 532, urban 499, low contrast 369, high contrast 360, indoor 301, skies 299, artificial light 230, studio 96, night 61, pure skies 59, overcast 134.
- `GET /assets?t=hdris` (all, 1.08 MB JSON keyed by id). Filters `&c=cat1,cat2` are AND-combined: `c=indoor,artificial light` -> 199 ids; `c=night,urban` -> 38 ids. Per-asset fields: `name`, `categories[]`, hierarchical `category` string (e.g. `Interiors/Retail & Commercial/Offices`, `Streets & Town/Streets & Alleys/Alleyways`), `attributes{time_of_day, weather, light_type, contrast, environment, sky_view}`, `tags[]`, `description`, `authors`, `max_resolution` ([w,h]), `backplates` (bool), `date_taken`, `coords`, `files_hash`.
- `GET /info/{id}`, `GET /files/{id}` -> JSON with `tonemapped.url`, `hdri.{1k,2k,4k,8k,16k,...}.{hdr,exr}.url`, `colorchart`, and (when `backplates:true`) `backplates.{DSC_xxxx}.{jpg_pretty,jpg_plain,raw}.url`.
- Direct file URL pattern (TESTED 200): `https://dl.polyhaven.org/file/ph-assets/HDRIs/extra/Tonemapped%20JPG/{id}.jpg` — content-type image/jpeg, supports `accept-ranges`, download time ~0.5 s for 7 MB, ~2 s for 45 MB.
- Thumbnail (TESTED 200): `https://cdn.polyhaven.com/asset_img/thumbs/{id}.png?width=512`.
- Backplates (TESTED listing only; not downloaded): `decor_shop` has flat DSLR photos e.g. `https://dl.polyhaven.org/file/ph-assets/HDRIs/extra/Backplates/decor_shop/jpg_pretty/DSC_4725.jpg` (12.4 MB). 208 of the 997 HDRIs have `backplates` (flat, already-rectilinear photos from the same spot; no projection needed). Not checked for resolution.

**Tonemapped JPG sizes (TESTED):** all three tested files were 8192x4096 but wildly different in bytes: abandoned_workshop 7.5 MB, rostock_laage_airport 45.1 MB, billiard_hall 48.0 MB (decor_shop listing says 4.6 MB). I downloaded ~100 MB in total, more than a "small" test; for CI, plan on 5-50 MB per HDRI, cache on disk/Actions cache, and prefer the id that is small, or download the `hdri.4k.hdr` (~26 MB, tonemap yourself) only if bandwidth matters. 1k/2k HDR files (1.7 MB / 6.7 MB for abandoned_workshop) are too low-res for a 75-degree crop (2k = ~430 px wide).

**Perspective crop (TESTED code, `scratchpad/proj.py`):** loads 8192x4096 JPG in 0.3-0.7 s, projects 1920x1080 with `cv2.remap(INTER_CUBIC, BORDER_WRAP)` in 0.2-0.6 s on this box. Rays: pinhole `f=(W/2)/tan(hfov/2)`, rotate by pitch (about x) then yaw (about y), `lon=atan2(x,z)`, `lat=asin(y)`, `u=(lon/2pi+0.5)*W`, `v=(0.5-lat/pi)*H`. Visual check of 6 plates (abandoned workshop yaw 0/120, Rostock-Laage airport yaw 0/90, billiard hall yaw 0/180, hfov 75, pitch 0): geometry is rectilinear and sharp, no seam artefacts.

```python
import numpy as np, cv2
def persp_from_equirect(img, yaw_deg, pitch_deg=0, hfov_deg=75, out_w=1920, out_h=1080):
    H, W = img.shape[:2]
    f = (out_w/2)/np.tan(np.radians(hfov_deg)/2)
    xs = np.arange(out_w)-(out_w-1)/2; ys = np.arange(out_h)-(out_h-1)/2
    x, y = np.meshgrid(xs, -ys)
    d = np.stack([x, y, np.full_like(x, f)], -1); d /= np.linalg.norm(d, axis=-1, keepdims=True)
    p, yw = np.radians(pitch_deg), np.radians(yaw_deg)
    Rx = np.array([[1,0,0],[0,np.cos(p),-np.sin(p)],[0,np.sin(p),np.cos(p)]])
    Ry = np.array([[np.cos(yw),0,np.sin(yw)],[0,1,0],[-np.sin(yw),0,np.cos(yw)]])
    d = d @ (Ry @ Rx).T
    lon = np.arctan2(d[...,0], d[...,2]); lat = np.arcsin(np.clip(d[...,1], -1, 1))
    mx = ((lon/(2*np.pi))+0.5)*W-0.5; my = (0.5-lat/np.pi)*H-0.5
    return cv2.remap(img, mx.astype(np.float32), my.astype(np.float32), cv2.INTER_CUBIC, borderMode=cv2.BORDER_WRAP)
# usage: persp_from_equirect(cv2.imread("id.jpg"), yaw, 0, 70)  # sweep yaw 0..330 step 30, hfov 60-80
```
Resolution rule: native px of crop = W * hfov/360 (8192 -> 1365 px at 60 deg, 1707 at 75, 2048 at 90). Use hfov 65-80 for 1920 output; wider than ~90 shows perspective stretch at the edges (not tested visually).

**Tonemapping:** the `tonemapped` JPG is already display-ready (visual check OK, slightly flat/clean). Raw `.hdr` needs `cv2.imread(path, cv2.IMREAD_ANYDEPTH|cv2.IMREAD_COLOR)` + e.g. `cv2.createTonemapReinhard`; `.exr` needs env `OPENCV_IO_ENABLE_OPENEXR=1`. Not tested (I did not download an HDR).

**Concrete asset ids (verified present in the live listing; categories from the API):**
- TV studio: `tv_studio` (Studio/Themed & Set-Dressed, tags camera, studio, set, news, show; 16384 px); other studios: `neon_photostudio` (coloured gel lighting, has backplates), `poly_haven_studio`, 97 `*_photo_studio_*` ids (`brown_photostudio_01..07`, `blue_photo_studio`, `christmas_photo_studio_01..07`, `blocky_photo_studio`).
- Law office / office: `small_empty_room_1..4` (Offices), `blender_institute`, `poly_haven_studio`, `unfinished_office`, `unfinished_office_night`; wood-panelled "lawyer" look: `combination_room`, `reading_room`, `entrance_hall`, `vestibule`, `large_corridor`, `ballroom`, `country_club`, `warm_reception_dinner`.
- Courtroom: none. Closest by look: `combination_room`, `church_meeting_room`, `school_hall`, `cowboy_town_hall`, `music_hall_01/02`, `de_balie` (tags include "people" – reject).
- Jewellery / retail: `decor_shop` (chandelier, has backplates), `phone_shop`, `gear_store`, `witsand_woolshop`, `leadenhall_market`, `royal_esplanade`. No jewellery store.
- Airport terminal: `rostock_laage_airport` (TESTED; shows a Sixt rental desk -> trademark), `hamburg_hbf`, `dresden_station_night`, `metro_noord`, `metro_vijzelgracht`, `alte_veste_station`, `subway_entrance`, `hangar_interior`, `small_hangar_01/02`, `aircraft_workshop_01`, `freight_station`.
- Casino: none. Closest mood: `warm_bar`, `wooden_lounge`, `ballroom`, `billiard_hall` (TESTED, brick, daylight), `cowboy_town_saloon`, `neon_photostudio`.
- Gaming room: `abandoned_games_room_01/02` (02 has "arcade"), `empty_play_room`, `billiard_hall`, `kart_club`, `neon_photostudio` (colour-gel it).
- Server room: none; closest `bank_vault`, `vintage_measuring_lab`, `boiler_room`, `industrial_pipe_and_valve_01/02`, `moon_lab`, `small_hangar_*` (grade blue/teal).
- Rainy neon alley: no rain HDRIs (`rain` matched only unrelated tags). Night alleys/streets: `cobblestone_street_night`, `modern_evening_street`, `urban_alley_01`, `stone_alley`, `stone_alley_02/03`, `palermo_sidewalk`, `zawiszy_czarnego`, `pergola_walkway`; neon: `shanghai_bund` (night, neon, skyscrapers). Add rain/neon by grading (not photoreal).
- Tropical sunset city: no tropical id; use `blue_lagoon_night`, `golden_bay`, `venice_sunset`, `the_sky_is_on_fire`, `sunset_jhbcentral` (Joburg, dusk), `hotel_rooftop_balcony`, `shanghai_bund`, `homecoming_center_rooftop` (Cape Town), `illovo_beach_balcony`, `victoria_sunset`, plus 37 "sunset" assets.
- Stadium: `stadium_01` (sunset, pitch), `orlando_stadium` (midday), `stadium_exterior`, `ushaka_dolphin_stadium`, `circus_arena`, `netball_court`, `squash_court`, `crossfit_gym`, `basement_boxing_ring`, `wrestling_gym`.
- Birthday party: none; use `ballroom`, `dancing_hall`, `country_club`, `warm_reception_dinner`, `events_hall_interior`, `anniversary_lounge` (+ overlay balloons/confetti graphics).
- Kitchen / food stall: `kiara_interior`, `blinds`, `glasshouse_interior` (Kitchens & Dining), `comfy_cafe`, `boma`, `bush_restaurant`, `sundowner_deck`, `warm_restaurant(_night)`, `leadenhall_market`, `newman_cafeteria`.
- Hotel street at night: `modern_evening_street`, `cobblestone_street_night`, `modern_buildings_night`, `zwinger_night`, `vignaioli_night`, `neuer_zollhof`, `hansaplatz`, `street_lamp`, `golden_bay`; hotel interiors `hotel_room`, `relax_inn_seaview_suite`, `hotel_rooftop_balcony`.
- Other useful: `warm_bar`, `warm_restaurant_night`, `rooftop_night`, `fireplace`, `lythwood_lounge`, `cinema_hall`, `pretville_cinema`, `theater_01/02`, `music_hall_01/02`.

### Inferences
- Because Poly Haven shows hundreds of unedited places, it is the best automated "literal environment" source; a rig that sweeps yaw (every 30 deg), crops at hfov 70, and scores each plate can pick a good plate per HDRI automatically.
- The 8K cap means 1280x720 thumbnails are fine but 4K video thumbnails would be soft; thumbnails need 1280x720 only.
- Since the API is explicitly "free for commercial use" but website ToS 3.2 bans scraping, use only `api.polyhaven.com`/`dl.polyhaven.org` with a unique User-Agent (e.g. `OdedHighlightsThumbs/1.0 (+repo url)`) and cache the 1 MB listing; do not crawl polyhaven.com HTML.
- ToS 2.5's credit duty is about showing API content to *users of your service*; our pipeline only consumes finished CC0 files, so it probably does not apply, but a one-line "Backgrounds: Poly Haven (CC0)" in the credits file is free insurance (inference, not legal advice).
- Textures/images inside an HDRI can still contain trademarks (Sixt desk in the airport plate) and copyrighted wall art; CC0 from the photographer does not cover third-party rights (see Q8).

### Gaps
- Not checked: whether any HDRIs contain blurred/visible people (e.g. `de_balie`; some outdoor ones); needs the person-detector filter in Q7.
- Did not download an HDR/EXR or a backplate, so tonemapping code and backplate resolutions are untested.
- Poly Haven has no stated numeric API rate limit; unknown behaviour under heavy bulk use.

---

## Q3. Pexels, Pixabay, Unsplash: licence, attribution, restrictions, API, quota

### Takeaway
All three allow commercial use without mandatory attribution, but none is CC0: each carves out identifiable people, logos/brands and (Pexels) architecture, and each has API rules. Pexels and Pixabay need a free API key (owner action) and are the best breadth source for casino/server room/jewellery etc.; Unsplash needs a key plus hotlink/download-tracking obligations and is not reachable here. I could not read the Pexels or Unsplash licence pages (not allowlisted) or the Pixabay licence page (Cloudflare challenge), so licence wording below is partly from search summaries.

### Cited Findings
**Pexels**
- Help-centre text (search summary quoting [help.pexels.com](https://help.pexels.com/hc/en-us/articles/360042295174)): "All photos and videos uploaded on Pexels are licensed under the Pexels license. This means you can use them for free for personal and commercial purposes without attribution."
- ToS (search summary of [pexels.com/terms-of-service](https://pexels.com/terms-of-service)): license is a "non-exclusive and royalty-free right to download, use, copy, modify or adapt the Content for commercial or non-commercial purposes"; third-party rights are carved out: "This includes but is not limited to identifiable people, logos, brands of all kinds (whether two- or three-dimensional), goods or services, buildings and architecture, audio or video samples and organisations." Note "buildings and architecture".
- Rules page ([help.pexels.com rules](https://help.pexels.com/hc/en-us/articles/360042332714-What-are-the-rules-for-using-Pexels-photos-or-videos)): identifiable people must not be shown in a bad light/offensive; no political endorsement use of identifiable people or trademarks ([help](https://help.pexels.com/hc/en-us/articles/360043229813-Can-I-use-photos-and-videos-from-Pexels-in-a-political-campaign)). Secondary summaries: cannot sell unmodified copies or redistribute on competing stock platforms.
- API: default limit 200 requests/hour and 20,000/month; higher limits free if you show acceptable attribution (a prominent link such as "Photos provided by Pexels"); a source says increases may be paused; abuse/limit circumvention terminates access ([Pexels API docs](https://www.pexels.com/api/documentation/), [help article on limits](https://help.pexels.com/hc/en-us/articles/900005852323), [python-pexels guidelines](https://python-pexels.readthedocs.io/en/latest/guidelines.html)).
- TESTED: `https://api.pexels.com/v1/search?query=airport&per_page=1` without a key -> HTTP 401 (reachable).

**Pixabay (primary: [API docs, read](https://pixabay.com/api/docs/))**
- Key required (`key=`); rate limit "100 requests per 60 seconds... associated with the API key"; headers `X-RateLimit-Limit/Remaining/Reset`; 429 "API rate limit exceeded".
- "requests must be cached for 24 hours. Also, the API is made for real human requests; do not send lots of automated queries. Systematic mass downloads are not allowed."
- "permanent hotlinking of images (using Pixabay URLs in your app) is not allowed. If you intend to use the images, please download them to your server first." Show users where images come from when displaying search results ("the one thing we kindly request in return").
- Search params: `q` (<=100 chars), `lang` (incl. `en`), `image_type=photo|illustration|vector|all`, `orientation=horizontal|vertical|all`, `category` (backgrounds, fashion, nature, science, education, feelings, health, people, religion, places, animals, industry, computer, food, sports, transportation, travel, buildings, business, music), `min_width`, `min_height`, `colors`, `editors_choice`, `safesearch`, `order=popular|latest`, `page`, `per_page` 3-200; max 500 hits per query.
- Sizes: `webformatURL` 640 px (URL valid 24 h); `largeImageURL` max 1280 px; `fullHDURL` (1920) and `imageURL` (original) only "if your account has been approved for full API access". So default key = 1280 px max, exactly the thumbnail width (no upscaling margin).
- Licence (Pixabay ToS via search summary, [pixabay.com/service/terms](https://pixabay.com/service/terms/)): "You cannot sell or distribute the Content (either in digital or physical form) on a Standalone basis. This includes but is not limited to identifiable people, logos, brands of all kinds." Using it with only a filter/colour change/resize/crop still counts as standalone. Licence summary (search summary of [pixabay.com/en/service/license](https://pixabay.com/en/service/license/)): recognisable trademarks/logos/brands cannot be used commercially in relation to goods/services; identifiable people may need consent; "Pixabay does not guarantee any consents have been obtained"; prohibited: misleading use, offensive depiction of people. Attribution not required (per the API docs' statement that content is "released by Pixabay under the Content License"; no attribution clause found in summaries).
- TESTED: `https://pixabay.com/api/?q=airport` -> 400 "Invalid or missing API key".

**Unsplash (secondary only; host not reachable)**
- Licence (search summaries of [unsplash.com/license](https://unsplash.com/license), Unsplash Medium post): free commercial use; no right "to compile images from Unsplash to replicate a similar or competing service"; cannot sell a photo without "updating, modifying, or otherwise incorporating new creative elements" (Feb 2018 wording change). Unsplash+ is a separate paid licence.
- API ([unsplash.com/documentation](https://unsplash.com/documentation), [help.unsplash.com/api-guidelines](https://help.unsplash.com/api-guidelines), via search summary): new apps are in demo mode at 50 requests/hour; approval ("Apply for Production") raises to 5,000/hour; image file requests to images.unsplash.com do not count; guidelines require hotlinking to Unsplash URLs and triggering the download endpoint when a photo is used; attribution is part of the API guidelines. One directory says 1000/h for production (conflicts; likely outdated).

### Inferences
- Rank for our use: Pexels > Pixabay > Unsplash. Pexels returns 80-ish results per page and large originals (UNVERIFIED, training knowledge: `Authorization: <key>` header; `GET /v1/search?query=&orientation=landscape&size=large&per_page=80&page=`; response `photos[].src.{original,large2x,large,landscape(1200x627)}`, `photos[].alt`, `photographer`, `url`), 200/h x 80 results is plenty for a handful of thumbs/day. Pixabay's 1280 px cap is workable for 1280x720 but leaves no crop margin.
- Both are "free for commercial use" but **not CC0**: keep a per-image record (provider, id, URL, photographer, licence name, retrieval date) so a takedown claim can be answered.
- The "no identifiable people / logos / brands / architecture" carve-outs mean automatic filters (Q7) matter more here than for Poly Haven.
- Pexels' API attribution duty applies when search results are shown to users; our pipeline would not show them, but cheap to put a credit line in the credits file.
- Unsplash adds a "must hotlink + ping download endpoint" burden that fits poorly with a CI pipeline that bakes images into a flattened thumbnail; defer unless the others fail.

### Gaps
- Could not read primary licence text for Pexels/Unsplash/Pixabay (hosts blocked / Cloudflare) — owner should open https://www.pexels.com/license/, https://unsplash.com/license, https://pixabay.com/service/license-summary/ once and screenshot/save the text into the repo for evidence.
- Whether images on Pexels flagged "Free to use" may actually be CC0-public domain on some items: not verified.
- Whether Pixabay CDN or `pixabay.com/get/...` downloads work from GitHub Actions (Cloudflare) : not tested (needs key).

---

## Q4. Openverse, Wikimedia Commons, NASA, Smithsonian, Library of Congress, Flickr Commons (CC0/PD filters)

### Takeaway
Openverse is a working key-less meta-search across Wikimedia, Smithsonian, NASA, Flickr, Met, Europeana, etc.; with `license=cc0,pdm` it avoids CC-BY-SA traps, but results are thin for generic topics, skew to old/museum/people photos, and downloads depend on provider hosts (only upload.wikimedia.org reachable here, and it throttled). Use it as a fallback for topics Poly Haven cannot cover (casino, jewellery shop, courtroom), always with automatic people/logo filtering.

### Cited Findings
- TESTED Openverse query examples (anonymous): `q=courtroom&license=cc0&category=photograph&aspect_ratio=wide&size=large` -> 90 hits, first results were rawpixel/Getty "Scene Courtroom Erich Salomon" (CC0 label, with people); `q=airport terminal&source=wikimedia&license=cc0,pdm` -> 240 hits, e.g. Oakland Airport Terminal 1 (3264x1840, CC0), Sittwe Airport Terminal (5312x2988, CC0); `q=casino interior&source=wikimedia&license=cc0,pdm` -> 2 hits; `q=neon street night&license=cc0` -> 42 hits (Wikimedia diner dusk 6000x4000, StockSnap, rawpixel).
- Result fields (TESTED): `id, title, url (original), thumbnail, foreign_landing_url, license, license_version, license_url, creator, provider, source, category, width, height, tags[], attribution, mature`. A ready-made `attribution` string is returned.
- Sources indexed (TESTED `/v1/images/stats/`): wikimedia 88.9 M, flickr 536 M, europeana 13.8 M, smithsonian_* (e.g. NMNH 4.99 M), nasa 131,756, rawpixel 1.27 M, met 498 k, stocksnap 40,333, wordpress (WP Photo Directory) 43,359, sketchfab 37,872, geographorguk 1.09 M, nappy 2,211, woc_tech 268, among others.
- Anonymous limits TESTED from headers: burst 20/min, sustained 200/day, thumbnail 1000/day. Registered key lifts these (docs).
- Wikimedia Commons: `extmetadata` is retrievable per file: Oakland file returned `LicenseShortName: CC0`, `UsageTerms: Creative Commons Zero, Public Domain Dedication`, `Copyrighted: True`, `Restrictions: ""` via `action=query&prop=imageinfo&iiprop=url|size|extmetadata&iiextmetadatafilter=...` (TESTED once). Throttling: the API and upload.wikimedia.org returned 429 / `retry-after: 600` after a handful of requests from this IP. Wikimedia's thumbnail host `thumb.wikimedia.org` is blocked here, and a non-standard thumb size (640px) returns 400 (standard steps such as 960/1280/1920/3840 are accepted by Wikimedia; UNVERIFIED).
- Commons pitfalls (search summaries of Commons policy pages, e.g. [Commons:Photographs of identifiable people](https://blogs.ashmolean.org/commons.wikimedia.org/wiki/Special_MyLanguage/Commons_Photographs_of_identifiable_people.html), [Non-copyright restrictions](https://blogs.ashmolean.org/commons.wikimedia.org/wiki/Special_MyLanguage/Commons_Non-copyright_restrictions.html)): all Commons images must allow commercial reuse "from a copyright point-of-view", but the subject may still refuse permission (personality rights); trademark law is separate from copyright; freedom-of-panorama differs by country (images of buildings/artworks may be non-free in some countries).
- NASA: "NASA's current guidelines say its images, audio, and video generally are not subject to copyright in the United States" but third-party material is excluded; "The NASA Insignia, Logotype, identifiers, and imagery are not in the public domain" ([nasa.gov guidelines](https://www.nasa.gov/multimedia/guidelines/index.html), search summary; the rule for "Media including Identifiable Persons" was not retrieved).
- Smithsonian Open Access: key from [api.data.gov/signup](https://api.data.gov/signup/); api.data.gov default 1,000 requests/hour/key; `DEMO_KEY` 30/hour/IP and 50/day ([api.data.gov manual](https://api.data.gov/docs/developer-manual)); Open Access content is CC0 (secondary). Reachable only after allowlisting api.si.edu. Via Openverse the Smithsonian images appear without key (but mostly museum objects).

### Inferences
- For the "no CC-BY-SA" requirement, always send `license=cc0,pdm` (or `cc0`) to Openverse and re-check `LicenseShortName` through the Commons API before use; reject anything whose `license` is not cc0/pdm. For Wikimedia "PD" tags such as PD-USGov, PD-old, keep the licence label in the credits file.
- Openverse's `cc0` label for aggregator items (rawpixel) means "rawpixel says CC0"; for old Getty photos with people it is still a personality-rights/editorial risk. Prefer `source=wikimedia,stocksnap,nappy,wordpress,nasa,smithsonian_*` and skip rawpixel/Getty.
- Wikimedia fetching should be: one search through Openverse (cheap), download original once with a descriptive UA including a contact URL, 1 request/second, honour `retry-after`, cache forever.
- Library of Congress and Flickr Commons were not reachable and not researched: LoC (loc.gov, public-domain-heavy, mostly historic b/w with people) and Flickr Commons ("no known copyright restrictions" statements, not CC0) are poor fits for modern topic backgrounds.

### Gaps
- No primary check of Smithsonian / NASA / LoC / Flickr Commons terms or APIs (hosts not allowlisted). Not tested: any download of a non-Wikimedia Openverse image. Wikimedia download of a >1 MB original was throttled, so I did not obtain a measured file size/time for one.
- Result quality for generic backgrounds: only a few probes; no systematic count of usable hits per topic.

---

## Q5. CC0 vector / 3D / texture sources (Kenney, Poly Pizza, ambientCG, Sketchfab CC0) for building backgrounds

### Takeaway
These are useful only for synthesising backgrounds (needs Blender/Three.js style rendering or 2D compositing), not for "real photographic" plates. Kenney (CC0) and ambientCG (CC0 textures, v3 JSON API) are safe; Poly Pizza and Sketchfab are mixed-licence and need per-asset checks. None of their hosts is allowlisted here, so nothing was tested.

### Cited Findings
- Kenney assets are CC0 (secondary: [licenseorg Kenney](https://licenseorg.com/guide/3d-assets/kenney-assets), [cinevva guide](https://app.cinevva.com/guides/sketchfab-polyhaven-kenney)); Quaternius is also CC0.
- Poly Pizza: mostly CC-BY with a CC0 subset, licence set per model ([cinevva guide](https://app.cinevva.com/guides/game-assets-guide); [flat.social credits](https://flat.social/credits) shows both CC-BY 3.0 and CC0 models on the same site).
- ambientCG API: v3 is current ("Version 2 ... does not receive updates anymore"), `https://ambientcg.com/api/v3/assets` returns JSON metadata+downloads; v2 `downloads_csv` / `full_json` still documented ([docs.ambientcg.com](https://docs.ambientcg.com/api/v3/)). The CC0 licence of ambientCG was not stated in the results I got (UNVERIFIED, training knowledge: all ambientCG assets are CC0).
- Sketchfab Data API v3: model search and detail endpoints work without authentication; downloads use `GET https://api.sketchfab.com/v3/models/{uid}/download` with `Authorization: Token ...`; search has `downloadable` and `license` filters (value `cc0`); only models the author made downloadable can be fetched ([Sketchfab developer docs](https://sketchfab.com/developers/data-api/v3), secondary summaries).

### Inferences
- Low priority: the effort of rendering a believable room from 3D assets is higher than cropping a Poly Haven HDRI, and the existing repo already has procedural scenes (`scripts/thumb_plates3.py` has `jewellery_store`, `law_office`, `airport`). Use these sources only as overlays/props (e.g., balloons, slot-machine silhouettes, server racks) on top of a real photo.
- Poly Haven `models` and `textures` (CC0, same key-less API, `GET /assets?t=models`) are the better 3D/texture source because they are already reachable (not enumerated here).

### Gaps
- Nothing tested; ambientCG/Kenney/Poly Pizza/Sketchfab primary licence pages unread.

---

## Q6. Game screenshots / streamer VOD frames as backgrounds: legal angle and technical treatment

### Takeaway
Using the streamer's own VOD frames is plausible but not risk-free: publisher policies mostly permit streaming with commentary and monetisation, copyright in the game art still belongs to the publisher, and fair use is not guaranteed. Treat it as "tolerated under publisher content policy", transform it heavily (blur/darken/grade), and keep game-specific uses to games whose policy is known.

### Cited Findings
- Many publisher policies allow monetised streaming/videos but require creative input (commentary), and bar raw footage uploads: Relic/SEGA, Jackbox, Nintendo and Capcom policies are examples; Capcom's is described as permitting monetisation via partner programs ([search summary, with links to Relic, Jackbox, Capcom pages](https://community.companyofheroes.com/coh-franchise-home/company-of-heroes-3/forums/2-welcome-info/threads/4-content-creator-guidelines), [Jackbox](https://www.jackboxgames.com/jackbox-games-content-guidelines-for-streaming-platforms/)).
- Policy is not law: "a creator is still relying on the 'leave' ... of the copyright holder, or on the nebulous world of fair use" and platform-guideline compliance "does not necessarily mean their content complies with copyright law" ([Techdirt](https://www.techdirt.com/2022/06/27/copyright-has-failed-for-game-streaming-so-alternatives-have-emerged/), [Romano Law](https://www.romanolaw.com/lets-play-fair-streaming-video-game-content/), via search summary).
- Enforcement varies: Bethesda's policy reportedly "does not prevent the company from issuing a takedown notice... at any time, for any reason"; Nintendo relies on Content ID ([Techdirt summary](https://www.techdirt.com/tag/video-game-streamers/)). Academic study of game UGC policies: [Internet Policy Review](https://policyreview.info/articles/analysis/merit-and-monetisation-video-game-user-generated-content-policies).
- Search found nothing on *thumbnails specifically*.

### Inferences
- The thumbnail is a still of the same footage already in the video, so the risk profile is close to the video's own; if the video is OK under the publisher's policy, a transformed still is likely similar, but this is inference, not advice.
- Safe-ish treatment pipeline (all Pillow/OpenCV): crop gameplay region only (drop HUD/face-cam/chat/usernames/watermarks), Gaussian blur radius ~10-20 px at 1280x720 (so text and character art are not legible), darken 35-50 %, reduce saturation 20-40 % then colour-grade toward the thumbnail palette, add vignette, keep the left calm zone dark; reject frames with the streamer's face-cam or chat overlay (YuNet) and frames with readable UI text (OCR check, Q7). Skip games whose policy forbids monetisation or logo use, and never use a frame containing third-party licensed content (music-video, TV, sports broadcast) that the streamer is merely reacting to.
- Keep a per-video record (game, publisher policy URL, retrieval date).

### Gaps
- Per-game policy lookup is manual; no list of the streamer's actual games was provided; no legal advice here.

---

## Q7. Keyword -> source routing for the 16 topics, and automatic picking of the best candidate

### Takeaway
Route first to Poly Haven where an HDRI exists (7-8 of 16 topics), then to Pexels/Pixabay search (needs keys) for casino, server room, jewellery, courtroom, birthday, tropical city, then Openverse/Wikimedia CC0, then procedural plate/blurred VOD frame as the last fallback. Pick the plate with a score built from sharpness, mid brightness, calm left third, zero people/faces, zero text; the first three metrics and the face detector are tested.

### Cited Findings
**Routing table.** The 16 topics are the 14 named in the brief plus two I added (bar/nightclub, tech/hacking dark room) because the brief said 16 without naming all; adjust to `scripts/topics.py` categories if they differ. PH = Poly Haven id (verified in live listing); queries are for Pexels/Pixabay/Openverse (UNTESTED for Pexels/Pixabay).

| # | Topic | 1st: Poly Haven ids | 2nd: stock keyword queries | Notes |
|---|---|---|---|---|
| 1 | Law office | `small_empty_room_1..4`, `combination_room`, `reading_room`, `blender_institute`, `vestibule` | "law office interior", "lawyer office bookshelf", "attorney office desk empty" | wood + bookcases; avoid diplomas with text |
| 2 | Jewellery store | `decor_shop` (chandelier, backplates), `phone_shop`, `leadenhall_market` | "jewelry store interior", "jewellery display case", "luxury boutique interior" (Pexels/Pixabay) | PH weak; brand logos on shop windows |
| 3 | Airport terminal | `rostock_laage_airport` (TESTED, Sixt logo), `hamburg_hbf`, `dresden_station_night`, `metro_noord`, `alte_veste_station`, `hangar_interior` | "airport terminal interior", "airport departure hall empty"; Openverse wikimedia cc0 (Oakland, Sittwe, Gazipasa terminals found) | signage/airline logos |
| 4 | TV studio | `tv_studio`, `neon_photostudio`, `poly_haven_studio` | "television studio set", "news studio empty" | `tv_studio` is the only literal one |
| 5 | Casino | none (nearest `warm_bar`, `ballroom`, `neon_photostudio`) | "casino interior", "slot machines casino floor", "poker table"; Openverse wikimedia cc0 (Model T Casino interior 4624x2966; Luxor) | likely logos/people; the channel also has a gambling policy (`scripts/gambling.py`) – check before using a casino look |
| 6 | Courtroom | none (nearest `combination_room`, `school_hall`, `church_meeting_room`) | "courtroom empty", "courtroom interior", "judge bench gavel" | Openverse cc0 courtroom hits are historical photos with people |
| 7 | Birthday party | none (nearest `ballroom`, `dancing_hall`, `events_hall_interior`, `anniversary_lounge`) | "birthday party decoration balloons table", "party room balloons" | overlay confetti/balloons assets |
| 8 | Gaming room | `abandoned_games_room_02` (arcade), `empty_play_room`, `kart_club`, `neon_photostudio` | "gaming room setup RGB", "gaming desk neon", "esports arena empty" | colour-grade to purple/cyan; monitors show text |
| 9 | Server room | none (nearest `bank_vault`, `vintage_measuring_lab`, `industrial_pipe_and_valve_01`, `moon_lab`) | "server room", "data center corridor", "server racks" | grade blue/teal; Pexels/Pixabay have many |
| 10 | Rainy neon alley | `shanghai_bund` (neon skyline), `cobblestone_street_night`, `urban_alley_01`, `stone_alley_02`, `palermo_sidewalk`, `modern_evening_street` | "rainy neon street night", "wet alley neon lights", "cyberpunk city street" | rain/neon via grade + overlay |
| 11 | Tropical sunset city | `blue_lagoon_night`, `golden_bay`, `venice_sunset`, `the_sky_is_on_fire`, `sunset_jhbcentral`, `homecoming_center_rooftop`, `hotel_rooftop_balcony` | "tropical city sunset skyline palm", "beach city sunset", "Miami sunset" | no palm HDRI |
| 12 | Stadium | `stadium_01` (sunset), `orlando_stadium`, `stadium_exterior`, `circus_arena` | "football stadium empty", "stadium floodlights night" | stadium sponsor boards = logos |
| 13 | Kitchen / food stall | `kiara_interior`, `blinds`, `comfy_cafe`, `boma`, `leadenhall_market`, `newman_cafeteria` | "street food stall night", "restaurant kitchen empty", "food market" | food stalls usually have people |
| 14 | Hotel street at night | `modern_evening_street`, `cobblestone_street_night`, `modern_buildings_night`, `zwinger_night`, `golden_bay`, `hotel_room`, `hotel_rooftop_balcony` | "hotel facade night street", "city street night lights" | |
| 15 | Bar / nightclub (added) | `warm_bar`, `wooden_lounge`, `cowboy_town_saloon`, `warm_restaurant_night` | "bar interior empty", "nightclub empty dance floor" | |
| 16 | Tech/hacker dark room (added) | `neon_photostudio`, `unfinished_office_night`, `small_empty_room_*` | "dark office computers night", "control room" | |

**Auto-pick scoring.** TESTED on six projected plates (`scratchpad/score_bg.py`, OpenCV 5.0.0, YuNet model at `scratchpad/t/models/yunet.onnx` from an earlier session):

| plate | Laplacian var (1280x720 gray) | mean brightness | left-third texture std (lower = calmer) | YuNet faces |
|---|---|---|---|---|
| abandoned_workshop yaw 0 | 378 | 0.64 | 16.4 | 0 |
| abandoned_workshop yaw 120 | 740 | 0.52 | 22.6 | 0 |
| billiard_hall yaw 0 | 1213 | 0.58 | 34.8 | 0 |
| billiard_hall yaw 180 | 617 | 0.24 | 21.8 | 0 |
| rostock_laage_airport yaw 0 | 2099 | 0.66 | 38.0 | 0 |
| rostock_laage_airport yaw 90 | 1829 | 0.40 | 46.3 | **2 (false positives: pictures/posters)** |

- `cv2.HOGDescriptor` does NOT exist in the installed OpenCV 5.0.0 (AttributeError) — if CI installs unpinned `opencv-python-headless` (see `scripts/requirements-thumbs.txt`) it may get 5.x too, so do not rely on HOG; use YuNet (works) plus the repo's `rembg`/`onnxruntime` for a person mask.

Suggested rule set (proposal; thresholds are my guess from the 6 samples, untested at scale):
```python
def score(plate):            # plate = BGR 1920x1080 crop
    sharp  = laplacian_var(gray_1280x720)                  # want >= 300; normalise by log
    bright = gray.mean()/255                               # want 0.25-0.60 (dark is fine for blur/darken; reject <0.12 or >0.8)
    calm   = laplacian_std(gray[:, :w//3])                 # lower is better for text zone
    faces  = len(yunet(plate, score_thr=0.6))              # reject if > 0 (posters can false-positive: then check size/rembg)
    person = rembg_mask_area_fraction(plate_small)         # reject if > 0.02 (rembg is already a dependency)
    text   = ocr_box_count(plate_small)                    # reject if > 2 or any box area > 1 % (EAST/DB detector or RapidOCR; not tested)
    return log(sharp) - 2*abs(bright-0.4) - 0.02*calm, rejected = faces or person>0.02 or text>2
```
Auto-pick loop: for each candidate asset, sweep yaw 0..330 step 30 (PH) or smart-crop 16:9 around the sharpest/calmest region (stock), score, keep top 3, final pick by random among top 3 weighted by score to avoid every video using the same plate; hash-record chosen asset ids to avoid reuse within 10 videos.

### Inferences
- The routing is the "best available" mapping; for casino/courtroom/jewellery/server/birthday there is no CC0 photographic source that I could verify, so those four-to-six topics depend on the owner creating Pexels/Pixabay keys, or on keeping the existing procedural plates.
- Keyword translation: Hebrew topic -> English query list (Hebrew queries are not reliable on Pexels; Pixabay supports `lang` but not `he` in the documented list — `he` is absent from the accepted values).
- OCR check: no OCR package is in `requirements-thumbs.txt`; choose between `rapidocr-onnxruntime` (onnxruntime already present) or OpenCV `TextDetectionModel_DB`/EAST (needs a model file). Not tested.

### Gaps
- Pexels and Pixabay hit counts per topic could not be measured (no keys).
- Left-calm/text/person thresholds were calibrated on 6 images only; need a run on 50+ plates.
- No test of rembg person mask on plates (not run to avoid heavy jobs).

---

## Q8. Legal checklist and attribution file

### Takeaway
CC0/free licences clear the photographer's copyright, not trademarks, architecture/artwork rights, personality rights or editorial restrictions. Automate: no people, no readable logos/text, source-licence whitelist, per-image provenance record; keep a credits file even where credit is optional.

### Cited Findings
- CC0 is a copyright waiver; Poly Haven states assets can be used "for any purpose, including commercial work" with no credit duty ([polyhaven.com/license](https://polyhaven.com/license)). It says nothing about trademarks visible in the photo; e.g. TESTED plate `rostock_laage_airport` shows an orange rental-car desk with a company logo.
- Pexels: third-party rights incl. "logos, brands ... buildings and architecture" are carved out of its licence; Pexels licence prohibits showing identifiable people in a bad light and for political endorsement ([Pexels ToS summary](https://pexels.com/terms-of-service), [rules](https://help.pexels.com/hc/en-us/articles/360042332714-What-are-the-rules-for-using-Pexels-photos-or-videos)). A licensing guide notes the platforms do not verify photographer obtained consent from people ([licenseorg](https://licenseorg.com/blog/free-stock-photos-licensing-traps)).
- Pixabay: "Pixabay does not guarantee any consents have been obtained"; trademarks/logos cannot be used commercially in relation to goods/services; standalone resale of unmodified images (incl. filter/crop/resize only) is forbidden ([Pixabay ToS](https://pixabay.com/service/terms/), summary).
- Unsplash: no compiling to run a competing service; no selling unaltered copies ([unsplash.com/license](https://unsplash.com/license), summary).
- NASA: insignia/logotype are not public domain; third-party content excluded ([nasa.gov](https://www.nasa.gov/multimedia/guidelines/index.html), summary).
- Commons: personality rights and trademark law apply independently of the licence; freedom-of-panorama varies per country ([Commons:Non-copyright restrictions](https://blogs.ashmolean.org/commons.wikimedia.org/wiki/Special_MyLanguage/Commons_Non-copyright_restrictions.html)). Wikimedia labels such as CC-BY-SA require attribution and share-alike on adaptations (detailed terms not retrieved; avoid by filtering to CC0/PDM).

### Inferences
Checklist for the pipeline (not legal advice):
1. Licence whitelist at fetch time: Poly Haven (CC0), Pexels (Pexels licence), Pixabay (Content License), Openverse only `cc0`/`pdm`, Wikimedia only CC0/PD tags; drop anything with `license` containing `by`, `sa`, `nc`, `nd`.
2. Reject any plate with people/faces (YuNet + rembg), including photos of posters of people; editorial-use-only or "model release" labels in metadata -> reject (Pexels/Pixabay API do not expose a reliable release flag).
3. No visible third-party logos/readable brand text: OCR/text-density check; blur or crop out signage; avoid stadium sponsor boards, airline/rental desks, shop fronts, screens; a blur of 8-12 px behind the cut-out already helps and is aesthetically standard.
4. Avoid recognisable copyrighted buildings/artwork/murals as the main subject (Pexels carve-out; freedom of panorama).
5. Never imply endorsement (no "official" look-alike backgrounds for real organisations: courtrooms of a named court, police, bank logos).
6. Transform: crop/grade/blur and composite with the cut-out; never sell/distribute the unaltered background standalone (Pixabay/Unsplash).
7. Keep `credits/backgrounds.jsonl` (append-only): `video_id, thumb_path, provider, asset_id, url, licence_name, licence_url, creator, retrieved_at, sha256, crop (yaw/pitch/hfov), checks (faces, text, brightness)`; add one line to the video description "Backgrounds: Poly Haven (CC0), Pexels" when used — free insurance for API attribution clauses (Poly Haven 2.5, Pexels, Pixabay).
8. Save a dated copy of the licence page text for each provider in the repo (since I could not read Pexels/Unsplash/Pixabay pages here).
9. Respect each API's terms: unique User-Agent (Poly Haven 2.4), cache 24 h (Pixabay), no permanent hotlinking (Pixabay, but Unsplash requires hotlinking), no mass scraping (Poly Haven ToS 3.2, Pixabay), honour 429/retry-after (Wikimedia).
10. Channel-specific: the repo has gambling detection (`scripts/gambling.py`); casino-looking backgrounds may collide with YouTube advertiser-friendliness; check policy notes before adding casino plates.

### Gaps
- No primary-text confirmation of "editorial use only" handling for Pexels/Pixabay.
- No jurisdiction analysis (Israel-based channel; YouTube US-law notice process); no lawyer review.
- Real-world frequency of takedowns for CC0/stock backgrounds on YouTube: no data found.

---

## Ranked source list (summary for the report writer)

1. **Poly Haven HDRIs (+ backplates)** — CC0, no key, no attribution, key-less JSON API, tested end-to-end; ~7-48 MB per 8K tonemapped JPG; covers ~8 of 16 topics literally.
2. **Pexels API** — free key, 200 req/h & 20k/month, commercial use without attribution (Pexels licence, not CC0), widest topic coverage; `api.pexels.com` reachable, key needed.
3. **Pixabay API** — free key, 100 req/60 s, cache 24 h, download don't hotlink, 1280 px max unless "full API access" approved; Cloudflare may block scripts on some paths.
4. **Openverse -> Wikimedia/NASA/Smithsonian (cc0, pdm)** — key-less, tested search; origin downloads throttled; filter carefully.
5. **Unsplash API** — key + hotlink/download-ping rules; host not allowlisted; demo 50/h.
6. **Streamer VOD frames (blurred/graded)** — policy-dependent, last-resort for game topics.
7. **CC0 vector/3D/textures (Kenney, ambientCG, Poly Haven models/textures; Poly Pizza/Sketchfab per-asset)** — only as props/overlays.

**Owner actions:** create free keys at Pexels (https://www.pexels.com/api/) and Pixabay (https://pixabay.com/api/docs/); optionally Unsplash; add GitHub Actions secrets `PEXELS_API_KEY`, `PIXABAY_API_KEY`; allowlist in the sandbox: `www.pexels.com`, `help.pexels.com`, `unsplash.com`, `api.unsplash.com`, `images.unsplash.com`, `images-assets.nasa.gov`, `api.si.edu`, `ambientcg.com`, `docs.ambientcg.com`, `sketchfab.com`, `www.loc.gov`, `live.staticflickr.com` if those sources should be verified; and save licence-page snapshots into the repo.

Files created during testing (scratchpad, not in repo): `/tmp/claude-0/-home-user-oded-highlights/9afff02d-82b9-5aa1-8251-aa0bcb4c3a4d/scratchpad/proj.py` (projection), `.../scratchpad/score_bg.py` (scoring), `.../scratchpad/t/sheet.jpg` (contact sheet of 6 plates), `.../scratchpad/t/hdris.json` (997-asset listing).

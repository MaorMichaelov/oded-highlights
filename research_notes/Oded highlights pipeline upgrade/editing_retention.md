# Editing practices for retention in long-form stream-highlight videos, and free headless tooling (as of Nov 2026)

Research-environment caveat (affects every section): this session's sandbox could only fetch github.com / raw.githubusercontent.com directly. support.google.com, youtube.com, remotion.dev, ffmpeg.org, vidiq.com, air.io, pixabay.com, tubefilter, searchenginejournal and others failed DNS resolution in WebFetch. I could not read YouTube Help, Creator Insider, or any channel's videos. All YouTube-official and channel claims below come from search-result summaries or secondary sources and are flagged. Items marked "Local test" were measured or observed on this 4-core Linux sandbox (FFmpeg 6.1.1 Ubuntu build, Pillow 12.3 with RAQM, Remotion 4.0.543, Playwright's chrome-headless-shell). They have no URL; they are reproducible, but timings were taken while another process was loading the machine (load average about 8), so treat them as rough and likely pessimistic.

---

## 1. What do YouTube official sources and credible data say about the first 30 s, intro length, pacing, pattern interrupts and long-form retention benchmarks?

### Takeaway
YouTube officially defines an "Intro" retention metric (share still watching at 30 s) and tells creators to edit and experiment with the first 30 s. It gives no official ideal intro length, no official cut cadence and no official "good retention" percentage. Everything numeric about pacing and benchmarks comes from third-party blogs, which disagree with each other and are mostly unsourced. The one consistent theme across them is front-loading the payoff and keeping the intro short.

### Cited Findings
- YouTube Help (via search-result summary; page itself not readable here) defines the Intro metric as the percentage of the audience still watching at the 30-second mark and suggests modifying the first 30 seconds and experimenting with styles — [YouTube Help: audience retention](https://support.google.com/youtube/answer/1715160)
- A glossary page says YouTube uses 50% at 30 s for its "above typical intros" list; other blogs say 70%+ is "solid" and 80%+ "exceptional". These are third-party figures, not YouTube's — [Creator Essentials glossary](https://www.creatoressentials.com/glossary/intro-retention/); contradicted in threshold by [vidIQ](https://vidiq.com/blog/post/increase-audience-retention-youtube/)
- Search Engine Journal, citing Creator Insider (the video itself was not located or verified), says the grey "typical retention" band is computed from the creator's own videos of similar length over the past year, with cross-channel comparison described as planned — [SEJ](https://www.searchenginejournal.com/youtube-typical-audience-retention/421700/)
- Third-party long-form benchmarks: vidIQ says roughly 30% average percentage viewed for most long-form with no magic number; Uppbeat says 35-50% is strong; Opus Pro advises comparing against your own same-length videos — [vidIQ](https://vidiq.com/blog/post/increase-audience-retention-youtube/), [Uppbeat](https://uppbeat.io/blog/youtube-growth/youtube-analytics/youtube-audience-retention), [Opus Pro](https://www.opus.pro/blog/youtube-retention-graphs-explained)
- Typical first-30-s loss is stated as 20-40% and the steepest drop in the first ~5 s, by marketing blogs without methodology — [Subscribr](https://subscribr.ai/p/youtube-analytics-improve-video-hooks-intros)
- Intro-length advice conflicts and is non-official: "collapse the intro to ~3 s or drop it" in one 2026 guide, "5-10 s hook" in another — [Gyre](https://gyre.pro/blog/how-to-make-a-youtube-intro-that-keeps-viewers-watching), [1of10](https://1of10.com/blog/how-to-hook-viewers-in-the-first-30-seconds-of-a-youtube-video)
- Pattern-interrupt cadence claims range from every 4-6 s to every 60-90 s. The most specific is an AIR Media-Tech write-up claiming a study of 100 long-form channels: top-quartile channels held viewers 20-30% longer, with a visual change every 10-20 s in the first 3 minutes widening to 25-40 s once hooked. I could not read the original or its methodology — [AIR Media-Tech](https://air.io/en/youtube-hacks/advanced-retention-editing-cutting-patterns-that-keep-viewers-past-minute-8). The same search also surfaced unverifiable claims (e.g. an unconfirmable "MIT-Harvard study", a 25% to 63% anecdote) that should not be used.
- The same AIR piece (as summarised) says clarity and narrative flow, not cut density, keep long-form viewers past minute 8 — [AIR Media-Tech](https://air.io/en/youtube-hacks/advanced-retention-editing-cutting-patterns-that-keep-viewers-past-minute-8)
- Reported contents of the leaked MrBeast production memo (not verified against the document): the first minute is where most viewers leave ("We lost 21 million viewers in the first minute"), with a further "re-engagement" point about three minutes later; outsiders call this "retention editing" — [OMR summary](https://omr.com/de/daily/mrbeast-doc-pdf-leak), [Tubefilter](https://www.tubefilter.com/2024/09/17/mrbeast-internal-production-guide-leaked-key-points/amp/)
- A claimed Paddy Galloway retention analysis could not be found; the only hit was an AI-generated video summary of uncertain provenance — [Pulse.bot](https://www.pulse.bot/personal-growth/video/the-30-second-youtube-rule-b79b9a71-a99d-4419-8144-84dc3c94dc8e/). Not usable as evidence.
- End screens (official, via search summary): can be placed in the last 5-20 s of a video, video must be at least 25 s, up to four elements on 16:9 — [YouTube Help: end screens](https://support.google.com/youtube/answer/6388789)
- Chapters: guides say first timestamp must be 0:00, at least 3 chapters, each at least 10 s. This is third-party only and unverified against YouTube Help. A "20-40% higher watch time with chapters" claim comes from a low-quality source and should be ignored — [Socialk.it](https://socialk.it/en/blog/youtube-chapters-timestamps-guide), [Humble & Brag](https://humbleandbrag.com/blog/youtube-chapters)
- Policy risk relevant to clip channels: on 15 Jul 2025 YouTube renamed "repetitious content" to "inauthentic content" and said its reused-content rules for clips/compilations/reactions did not change. Compilations with minimal added value risk monetization loss, applied channel-wide. Original commentary, editing or entertainment value is what keeps them eligible. Copyright is a separate matter — [Engadget](https://www.engadget.com/entertainment/youtube/never-fear-reaction-videos-are-still-allowed-under-youtubes-new-inauthentic-content-policy-222401009.html), [PPC Land](https://ppc.land/google-clarifies-youtube-monetization-policies-amid-creator-confusion/), [YouTube Help: reused content](https://support.google.com/youtube/answer/1311392)

### Inferences
- (Opinion, from the above) The defensible, low-regret set for a stream-highlight channel: a cold open that shows the best payoff in the first few seconds with context for a viewer who does not know the stream; a very short brand sting (the existing 2.6 s is already at the upper end of what blogs suggest); a visible change (zoom, cut to different moment, graphic, SFX hit) roughly every 10-30 s early, relaxing later; and a "re-engagement" beat around 3 min and then at chapter boundaries.
- Because no official number exists, the only authoritative benchmark is the channel's own YouTube Studio "Intro" metric and grey typical-retention band. A/B comparisons of the current cold open versus a variant on the same channel are the real test; at ~1,850 subs the sample will be noisy.
- Reused-content policy means original value-add (editing, captions, context labels, commentary) is not just polish; it is also compliance-relevant. This is an inference from YouTube's stated criteria, not a verified ruling for this channel.

### Gaps
- No readable official YouTube text on intro length or cut cadence; no Creator Insider video located and verified.
- No methodology for the AIR Media-Tech 100-channel analysis; could not fetch it.
- No independent, peer-reviewed or platform-published data on cut frequency vs retention for long-form.
- Chapter requirements not confirmed from YouTube Help.

---

## 2. What do successful stream-clip channels (Israeli and global) actually do?

### Takeaway
I could not verify the editing practices of Taklipu/תקליפו, OdedSVR Live/Moments, Ronen Live or RonenGG Peak, nor of xQc, Kai Cenat, IShowSpeed, Asmongold, Ludwig or Jynxzi clip channels. Searches returned no pages about Taklipu at all, and video platforms were unreachable. The only usable evidence is generic guidance from clipping-tool vendors, which is commercial and Shorts-oriented.

### Cited Findings
- Searches for "Taklipu" and "תקליפו" returned no results about such a channel; the search engine suggested the name may be misspelled or not indexed — web searches run in this session (no URL available)
- OdedSVR: Streams Charts lists him as a Twitch partner (not Kick) with a mostly Israeli audience, second most-watched Hebrew streamer over a 7-day window at the time of crawl (109,688 hours watched, behind ronengg); this may be stale — [Streams Charts](https://streamscharts.com/channels/odedsvr). The brief says Kick; I could not confirm current platform.
- Ronen Robin ("RonenGG") has a YouTube channel of roughly 508k subscribers and ~90M views as of July 2025 per a Hebrew wiki — [Hamichlol](https://www.hamichlol.org.il/%D7%A8%D7%95%D7%A0%D7%9F_%D7%A8%D7%95%D7%91%D7%99%D7%9F). Nothing found on his clip/peak channels' editing.
- Vendor guides (not channel analysis) say: captions are "retention tools" because many viewers watch muted; a zoom signals that a line matters, and "a zoom disguises a weak sentence"; a subtle logo/watermark and consistent style build recognition; the best reaction clips show the trigger within the first seconds — [Eklipse](https://eklipse.gg/help/what-are-the-best-practices-for-editing-stream-highlights), [Opus Pro top-50 piece](https://www.opus.pro/blog/top-50-youtube-channels-video-strategy-2026), [ClipSpeed on Kai Cenat](https://www.clipspeed.ai/blog/clip-kai-cenat-streams-highlights.html)
- Source quality is low: these are marketing pages from tools that sell clipping/captioning software, mostly about vertical Shorts, and the top-50 piece cannot be tied to any named channel's actual edit.
- The competitor features in the brief (wipe transitions, spinning-logo sting, animated subscribe popup with cursor click, corner logo bug, tagline pill) are taken from the brief, not independently verified.

### Inferences
- (Opinion) Persistent corner logo, consistent sting and animated subscribe prompt are brand-recognition features with plausible but unmeasured retention effect. Evidence for retention impact specifically is absent; they most likely help perceived polish and channel recall rather than watch time.
- To learn what Taklipu etc. really do, a human should watch 3-5 of their top videos with a stopwatch and log: cold-open length, number of cuts per minute, zoom count, SFX/music presence, caption style, label/lower-third usage, video length, chapter use, end-screen layout. This cannot be done from this environment.

### Gaps
- Everything channel-specific: cold-open structure, caption style, zoom frequency, SFX/music, lower-thirds, lengths, chapters and end screens for all named Israeli and global channels. Unverified.
- Whether Taklipu's channel exists under that transliteration; search returned nothing.

---

## 3. Captions: evidence, and Hebrew/RTL implementation (ASS/libass, Pillow+RAQM, Remotion)

### Takeaway
Evidence that captions help is moderate for captions in general and weak (vendor-only) for animated word-by-word styles specifically. For implementation, libass can render Hebrew correctly, but the default ASS Encoding value forces a left-to-right paragraph and scrambles word order; setting style Encoding to -1 fixes it (verified locally). Pillow needs the RAQM layout engine for Hebrew.

### Cited Findings
- The most rigorous figure cited for captions generally is a 2019 Verizon Media / Publicis Media survey of 5,616 US adults: 80% said they were more likely to watch a video to completion with captions available. It does not compare animated vs static, and is not YouTube-specific — [VideoCaptions.ai summary](https://www.videocaptions.ai/blog/how-video-captions-increase-engagement)
- Animated word-by-word vs static uplift claims (8-12% static vs 18-28% animated; 15-25% longer watch time; +34% with colour emphasis) are vendor figures without methodology; a "47% from TikTok internal research" claim has no source. Several sources warn heavy animation distracts — [ClipSpeed](https://clipspeed.ai/blog/ai-captions-increase-views.html), [Opus Pro captions](https://www.opus.pro/blog/best-caption-presets-styles-boost-retention), [BlitzCut](https://blitzcutai.com/blog/animated-captions-vs-static-captions)
- Safe areas: sources conflict. SMPTE 2009 moved title-safe from 80% to 90% of width/height; a software project reserves 5-8% of frame height at the bottom for platform UI (about 40-64 px at 1080p), which is a tool default, not a YouTube rule — [Dartmouth quick guide](https://services.dartmouth.edu/TDClient/1806/Portal/KB/Article/171286/Title-Safe-Areas-Quick-Guide-for-Video-Creation), [SMPTE ST 2046-1](https://pub.smpte.org/doc/st2046-1/20091123-pub/st2046-1-2009.pdf)
- Pillow: layout engine BASIC does not support text direction; RAQM supports advanced features; check availability with `PIL.features.check_feature("raqm")` — [Pillow ImageFont docs](https://raw.githubusercontent.com/python-pillow/Pillow/main/docs/reference/ImageFont.rst). The page does not document the direction/language parameters or the RAQM dependencies (fribidi/harfbuzz).
- libass: portable ASS/SSA renderer, latest release 0.17.5 dated 2026-06-24 — [libass README](https://raw.githubusercontent.com/libass/libass/master/README.md). The README gives no RTL guidance.
- Local test (ASS/libass, FFmpeg 6.1.1, DejaVu Sans Bold, Hebrew sentence with an embedded Latin name "OdedSVR" and digits):
  - With style `Encoding` = 177 (the Hebrew charset value, which Aegisub-style tools often write), libass shapes each Hebrew word correctly but orders the words/runs left-to-right, so the sentence reads scrambled to a Hebrew reader. Prepending RLE/RLI/RLM Unicode marks did not fix paragraph direction (they only moved neutral punctuation).
  - With style `Encoding` = -1, or the inline tag `{\fe-1}`, the line renders in correct RTL order, including the mixed "ש-OdedSVR" token and `{\k40}` karaoke word-highlight tags between words. Per-word colour highlighting works and stays in RTL order.
  - Hebrew-capable fonts installed locally: DejaVu Sans, FreeSans, Heebo, IBM Plex Sans Hebrew. On a fresh Actions runner install Hebrew fonts explicitly and pass `subtitles=file.ass:fontsdir=...`.
- Local test (Pillow 12.3, RAQM available): `ImageFont.truetype(..., layout_engine=ImageFont.Layout.RAQM)` with `d.text(..., direction='rtl', language='he', anchor='ra')` produced correct Hebrew. `Layout.BASIC` produced fully reversed text (each line mirrored in character order).
- Local test: a full-line libass Hebrew subtitle filter added no measurable time to a 10 s x264 encode within run-to-run noise (8.8 s vs 8.6-9.4 s baseline).
- Remotion renders in Chromium, so RTL text goes through the browser's bidi/shaping (`dir="rtl"` worked in a test composition that rendered; I did not visually inspect the Hebrew output, so correctness of Remotion Hebrew rendering is inferred, not verified) — Local test.

### Inferences
- (Recommendation) For word-by-word Hebrew captions in ASS: write Style with Encoding -1; use `\k` karaoke tags for in-line highlighting, or one Dialogue per word if one-word-at-a-time pop-in is wanted (then bidi is irrelevant); keep Hebrew text and Latin names in the same line only after testing, since mixed-script punctuation placement is where bidi problems hide.
- Keep captions inside the inner ~90% box and above the bottom ~8% (about 85 px at 1080p), and avoid collision with the logo bug or subscribe popup region; these margins are conventions, not YouTube rules.
- Because animated-vs-static evidence is vendor-only, treat the caption style as a taste/brand decision; readability (contrast, outline, size at phone scale) matters more than animation.
- Pillow pre-rendered caption frames are fine if RAQM is present on the runner; GitHub's Ubuntu runners need `libraqm0` (verify) or pip wheels with RAQM bundled. Pillow wheels bundle RAQM in recent versions, but I did not confirm this for the runner image.

### Gaps
- No Hebrew-specific subtitle reading-speed (chars/sec) or font-size guidance found.
- No official YouTube safe-area guidance found.
- Remotion Hebrew output not visually verified; libass behaviour verified only on one FFmpeg/libass build.

---

## 4. Audio: loudness target, ffmpeg chains, licensed SFX/music, sound-design conventions

### Takeaway
Target about -14 LUFS integrated with true peak at or below about -1 dBTP. YouTube is said to only turn loud audio down, not boost quiet audio. Sources for this are secondary, so the exact official wording is unverified. The filter chains run in seconds. Free, safely licensed SFX/music sources exist; the YouTube Audio Library is the lowest-risk option.

### Cited Findings
- Multiple mastering sources say YouTube normalises playback to about -14 LUFS, turns louder videos down, and does not raise quieter ones; original file is unchanged. None are YouTube's own documentation — [Sage Audio](https://www.sageaudio.com/articles/mastering-for-streaming-platform-loudness-and-normalization-explained), [Production Advice](https://productionadvice.co.uk/youtube-loudness/), [MasteringBOX](https://www.masteringbox.com/learn/mastering-for-streaming)
- FFmpeg loudnorm options and defaults from source: I=-24 (range -70..-5), LRA=7, TP=-2, measured_I/LRA/TP/thresh, offset, linear default on, dual_mono default off, print_format none/json/summary — [FFmpeg af_loudnorm.c](https://raw.githubusercontent.com/FFmpeg/FFmpeg/master/libavfilter/af_loudnorm.c)
- Standard two-pass pattern: pass 1 `loudnorm=I=-14:TP=-1:LRA=11:print_format=json` to `-f null`, then pass 2 with the measured values; guides say two-pass gives more precise results than single-pass, which is fine for streaming — [DEV Community guide](https://dev.to/javidjamae/ffmpeg-loudnorm-filter-ebu-r128-loudness-normalization-guide-15d4)
- Local test: a single-pass chain `highpass=f=80,afftdn=nf=-25,acompressor=threshold=-18dB:ratio=3:attack=5:release=80:makeup=4,loudnorm=I=-14:TP=-1.5:LRA=11` on 30 s of audio ran in about 1.4 s; loudnorm analysis alone about 0.5 s. Audio processing cost is negligible next to video encode. (Tested on synthetic sine input, so it shows runtime only, not sound quality.)
- SFX/music licensing: YouTube's Audio Library is described as copyright-safe and not claimed via Content ID for Partner Program members, with a warning that other "royalty-free" libraries are not covered — [YouTube Help: Audio Library](https://support.google.com/youtube/answer/3376882). Pixabay says content is under the Pixabay License, usable without attribution including commercially — [Pixabay FAQ](https://pixabay.com/service/faq/). Freesound licences vary per file (CC0, CC BY, CC BY-NC); a forum reply says CC0 needs no credit, and one creator reported a demonetisation anecdote involving CC0 sounds — [Freesound forum](https://freesound.org/forum/legal-help-and-attribution-questions/40088)
- A claimed Content ID mitigation using a Pixabay licence certificate comes from a single blog — [blog](https://smarthustlers101.blogspot.com/2022/09/how-to-clear-youtube-content-id-claim.html); treat as unverified.

### Inferences
- (Recommendation) Chain: high-pass at 80 Hz, optional `afftdn` (denoise; may harm streamer voice if overused, test on real audio), `acompressor` to even out shouting-versus-talking dynamics, then two-pass `loudnorm` to -14 LUFS / -1.5 dBTP using `linear=true` with measured values. Apply on the final mix, not on each clip, so sting/SFX/music stay balanced against voice.
- (Opinion, conventional practice, not sourced here) Duck any music bed 10-15 dB under speech with `sidechaincompress`; keep SFX (whoosh on wipes, click on subscribe popup, impact on punch-in zooms) short and sparse, mixed below speech peaks; use SFX to mark pattern interrupts rather than constantly. I did not test `sidechaincompress` here.
- Keep a licence log (URL, licence, date) per SFX/music file in the repo, since YouTube's own warning shifts responsibility to the uploader.

### Gaps
- No YouTube-official statement of the -14 LUFS reference was readable; all figures are secondary.
- No data-backed sound-design conventions for stream-highlight channels found.
- Loudness result accuracy (after processing) not measured on real speech.

---

## 5. Tools: Remotion headless on GitHub Actions, transparent overlays, alternatives, render time and speed-ups

### Takeaway
Remotion can render headless on a GitHub Actions Ubuntu runner and output alpha overlays (ProRes 4444, VP8/VP9 WebM, or PNG sequences) to composite with ffmpeg. Free use is allowed for individuals and for-profit organisations up to 3 employees. For short overlays, a PNG sequence or ProRes 4444 render is much faster than VP8-alpha WebM. The main cost for the whole video is the x264 encode, which preset choice controls.

### Cited Findings
- Remotion docs show a ready-made GitHub Actions workflow on `ubuntu-latest`: checkout, setup-node, `npm i`, `npx remotion render MyComp out/video.mp4`, `upload-artifact@v4`; props can be passed from `workflow_dispatch` inputs via `--props` — [Remotion SSR docs (raw)](https://raw.githubusercontent.com/remotion-dev/remotion/main/packages/docs/docs/ssr.mdx)
- Remotion Linux requirements: glibc 2.35+; Ubuntu 24.04 packages listed (libnss3, libdbus-1-3, libatk1.0-0, libasound2t64, libxrandr2, libxkbcommon-dev, libxfixes3, libxcomposite1, libxdamage1, libgbm-dev, libcups2, libcairo2, libpango-1.0-0, libatk-bridge2.0-0); Alpine unsupported; Remotion ships its own Chrome and FFmpeg — [Remotion Linux dependencies (raw)](https://raw.githubusercontent.com/remotion-dev/remotion/main/packages/docs/docs/miscellaneous/linux-dependencies.mdx)
- Transparent output: WebM `--image-format=png --pixel-format=yuva420p --codec=vp8` (vp9 also allowed); ProRes `--image-format=png --pixel-format=yuva444p10le --codec=prores --prores-profile=4444` (or 4444-xq); do not set a background in the composition; only Chrome and Firefox play WebM alpha. For Lambda, WebM can flicker at chunk boundaries (not relevant to a single-machine Actions render). `<OffthreadVideo>` needs the `transparent` prop for alpha input — [Remotion transparent videos docs (raw)](https://github.com/remotion-dev/remotion/blob/main/packages/docs/docs/transparent-videos.mdx)
- Remotion performance guidance: use `<Video>` from `@remotion/media` rather than `<OffthreadVideo>`/`<Html5Video>`; tune `--concurrency` and use `npx remotion benchmark`; jpeg renders faster than png (use png only for transparency); vp8/vp9 encode slowly; WebGL/canvas/GPU-accelerated CSS (blur, box-shadow) can slow CPU-only renders; lower resolution with `--scale`; `--log=verbose` to find slow frames — [Remotion performance docs (raw)](https://raw.githubusercontent.com/remotion-dev/remotion/main/packages/docs/docs/performance.mdx)
- Remotion licence: free for individuals, for-profit organisations with up to 3 employees, non-profits and evaluators; a paid company licence is required otherwise; licence terms will change in Remotion 5.0 — [Remotion LICENSE](https://raw.githubusercontent.com/remotion-dev/remotion/main/LICENSE.md)
- GitHub-hosted `ubuntu-latest` (x64): public repositories get 4 vCPU / 16 GB RAM / 14 GB SSD and free unlimited use; private repositories get 2 vCPU / 8 GB / 14 GB and consume plan minutes — [GitHub Docs (raw)](https://raw.githubusercontent.com/github/docs/main/data/reusables/actions/supported-github-runners.md). The 4-core assumption in the brief therefore only holds for a public repo.
- FFmpeg xfade transitions available (from source): fade, wipeleft/right/up/down, slideleft/right/up/down, circlecrop, rectcrop, distance, fadeblack, fadewhite, radial, smoothleft/right/up/down, circleopen/close, vertopen/close, horzopen/close, dissolve, pixelize, diagtl/tr/bl/br, hlslice/hrslice/vuslice/vdslice, hblur, fadegrays, wipetl/tr/bl/br, squeezeh/v, zoomin, fadefast, fadeslow, hlwind/hrwind/vuwind/vdwind, coverleft/right/up/down, revealleft/right/up/down; options `duration` (default 1 s, max 60 s) and `offset` (start relative to first input); a custom expression mode exists — [FFmpeg vf_xfade.c](https://raw.githubusercontent.com/FFmpeg/FFmpeg/master/libavfilter/vf_xfade.c)
- Motion Canvas: TypeScript generator-based animation library with an editor; the README does not state headless rendering, alpha output, or maintenance status, so it is unverified for this use — [Motion Canvas README](https://raw.githubusercontent.com/motion-canvas/motion-canvas/main/README.md)
- Remotion's Chrome download: in my test, Remotion 4.0.543 tried to fetch Chrome Headless Shell from `remotion.media`; on a network that blocks that host the render fails. On GitHub-hosted runners this host should be reachable, but pinning/caching the browser (or `npx remotion browser ensure`, per a third-party mirror — [Remotion Lab mirror](https://remotionlab.pages.dev/docs/misc-linux-dependencies)) avoids per-run download flakiness.

**Local measurements (no URLs; reproducible; noisy shared 4-core box; synthetic content)**
- Remotion 1080p60 trivial overlay (spring-scaled Hebrew RTL "subscribe" pill + rotating disc), frames 0-119 (2 s), using Playwright's chrome-headless-shell via `--browser-executable`:
  - PNG sequence (`--sequence --image-format=png`): 10.4 s (about 11.5 fps); 7.0 MB for 120 frames.
  - ProRes 4444 `yuva444p10le`: 16.2 s (about 7.4 fps); 12.9 MB for 2 s.
  - VP8 WebM alpha: 51.4 s (about 2.3 fps) for 120 frames; the 300-frame run took 128 s.
  - H.264 jpeg (no alpha): 10.3 s.
  - A first "PNG sequence" attempt that reported 4.7 s was invalid: it wrote no files. Disregard it.
- ffmpeg compositing of that overlay (ProRes .mov or PNG sequence via `-framerate 60 -i element-%03d.png` with `overlay=eof_action=pass`) onto a 10 s 1080p60 clip: 9.6 s and 8.9 s versus an 8.6-9.4 s baseline, so overlay compositing overhead is within noise.
- x264 encode of 30 s synthetic 1080p60 (8 Mbit/s source, decode alone 3.1 s), CRF 20, no audio: ultrafast 6.9 s (105 MB output); veryfast 13.2 s (34 MB); fast 27.0 s (40 MB); medium 30.5 s (39 MB). So veryfast is about 0.44x real time and medium about 1.0x real time on this box; a 30-minute output would be roughly 13 min (veryfast) vs 30 min (medium) of encode, before filters. Real footage will differ from synthetic noise.
- Stream copy and concat demuxer of two 10 s segments: 0.1 s (versus ~9 s to re-encode 10 s). Copy only works for pieces already encoded with identical codec parameters and cut on keyframes.
- Zoom: `scale=w='1920*(1+0.25*min(t/2,1))':h=...:eval=frame,crop=1920:1080` ran in 12.3-14.0 s for 10 s versus 8.7-9.4 s baseline (about +40%). A `zoompan` variant ran in 9.4 s (likely near baseline). A crop-expression variant that ran faster than baseline probably did not animate (crop width/height expressions are evaluated once), so ignore it.
- xfade `wipeleft` (0.5 s) between two 5 s clips: 10.4 s.

### Inferences
- (Recommendation) Architecture that keeps cost low: render branded elements in Remotion once as short PNG-sequence or ProRes-4444 assets (sting, subscribe popup, wipe masks, tagline pill, logo bug loop) and cache them in the repo or Actions cache, since they do not depend on the footage; composite in ffmpeg with `overlay` and `enable='between(t,a,b)'`. Only re-render Remotion when the design changes or text varies per video (then a short per-video overlay, a few seconds, is cheap). This avoids rendering the whole video in Remotion, which is slow on CPU.
- (Recommendation) Prefer ProRes 4444 or PNG sequences over VP8/VP9 alpha WebM for intermediates in this pipeline; WebM alpha was about 3-5x slower in the local test and is only needed for browser playback.
- (Recommendation) Speed levers, in order: (1) encode preset veryfast or faster with CRF about 20-23 during iteration and `fast`/`medium` only for final; (2) cut unchanged runs as stream copy where codec params match, re-encoding only the sections with graphics, zooms and captions; (3) cache decoded/normalised clips; (4) render the audio chain separately (cheap). This was not tested end to end.
- (Inference) The 3-employee free-licence threshold is likely fine for a one-person channel; re-check at Remotion 5.0.
- (Inference) The motion-graphic recipes in ffmpeg-only form: wipe/slide transitions via `xfade` (e.g. `wipeleft`, `slideleft`, `circleopen`) with a whoosh SFX at the offset; spinning logo via Remotion rotation or an ffmpeg `rotate` filter on a PNG; corner logo bug as a static `overlay` with fade-in; tagline pill and animated subscribe button with cursor click are best as Remotion-rendered alpha clips; punch-in zoom via `zoompan` or scale-eval-frame with an easing expression. Only the xfade list, the overlay path and the zoom/subtitle timings were verified here.
- Alternatives (unverified here): HTML + Playwright frame capture (same cost profile as Remotion, more manual), Motion Canvas (unclear headless/alpha story), MoviePy (Python, slow per-frame compositing; not benchmarked).

### Gaps
- Remotion on a real GitHub-hosted runner was not tested; my numbers are from a different Chromium on a shared sandbox. Real 1080p60 x264 total render time for a full video on an Actions runner was not measured with real footage.
- Whether the Remotion Chrome download works reliably in this project's CI was not tested.
- Alternatives (Playwright capture, MoviePy, Motion Canvas rendering) were not benchmarked.
- Remotion docs from remotion.dev itself were unreachable; I used the repo's source docs on GitHub, which may differ slightly from the published site.

---

## 6. Automatic silence/dead-air removal and risks for comedic timing

### Takeaway
auto-editor (CLI, pip-installable) and ffmpeg `silencedetect` can cut silence automatically, with `--margin` controlling how much silence is kept. Nothing authoritative addresses comedic timing. The risk is that over-aggressive cutting clips word onsets and removes beats that make a joke or a reaction work. In a highlight pipeline, where clips are already selected, use it conservatively or only for long dead stretches.

### Cited Findings
- auto-editor: `--margin` adds "silent" padding around cuts so the edit feels less abrupt; default 0.2 s; takes before and after values, e.g. `--margin 0.3s,1.5sec`; default edit method is audio with threshold 0.04 (also dB form such as `audio:-19dB`); `--edit motion:threshold=0.02` cuts low-motion sections; methods can be combined with `or`. The README has no headless-Linux notes and points to its installing page — [auto-editor README](https://github.com/WyattBlue/auto-editor)
- A maintainer discussion advises margin 0 plus a minimum-cut length of about half a second to remove short gaps for tighter cuts — [auto-editor discussion #438](https://www.github.com/WyattBlue/auto-editor/discussions/438)
- A third-party write-up argues that aggressive automatic cutting that clips the first word of sentences makes rough cuts feel mechanical; it is a general editing point, not comedy-specific — [Knightli](https://knightli.com/en/2026/04/23/auto-editor-auto-cut-silence-premiere-resolve-workflow/)
- Version drift: older releases used differently named margin flags (`--frame-margin`); check `auto-editor --help` for the installed version — [PyPI auto-editor](https://pypi.org/project/auto-editor/24.31.1)

### Inferences
- (Opinion) Stream audio contains game sound, music and chat TTS, so an audio-threshold cut will seldom find true silence; motion-based detection will also misfire on static game scenes. A threshold tuned on speech may delete quiet but meaningful beats (pauses before a punchline, reaction silence).
- (Recommendation) Use dead-air removal only above a minimum gap (for example over 1.5-2 s) and keep a margin of 0.3-0.5 s on both sides; always preserve the beat directly before and after a flagged "moment" (laugh, scream, donation reaction). Prefer shortening long gaps to a fixed short pause rather than removing them. Compare against the unedited cut on a handful of known funny clips before enabling it.
- `ffmpeg silencedetect` (standard filter) can produce timestamps for the same purpose without installing anything; not tested here.

### Gaps
- No evidence found on the effect of silence removal on retention or comedic timing specifically.
- Not tested: auto-editor on this machine (not installed), silencedetect behaviour on stream audio.

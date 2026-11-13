# Free photorealistic AI thumbnails with identity-preserving faces (as of Nov 2026)

Method note: the research session's WebFetch could only reach github.com. ai.google.dev, support.google.com, huggingface.co, kaggle.com and the YouTube help pages all failed DNS. So almost every number below comes from WebSearch result summaries of third-party pages, and a few come from GitHub pages. Official-page values are NOT directly verified. Anything not backed by Google, YouTube, Hugging Face or Cloudflare text that the search tool quoted is marked unverified. Before building, re-check the "Gaps" items with a live request, for example listing models with the API key and making one test call.

## 1. CTR evidence for the streamer-highlight genre, YouTube guidance, Test & compare, thumbnails.set

### Takeaway
Public CTR evidence is mostly vendor and SEO blog material with conflicting effect sizes. The only consistent directional claims are an expressive face, 3 words or fewer of text, high contrast and a single focal point. The best evidence for your channel will be YouTube's own Test & compare, which optimises for watch-time share, not raw CTR. thumbnails.set takes JPEG or PNG up to 2 MB and costs 50 quota units per call.

### Cited Findings
- A study of more than 300,000 viral 2025 videos found that thumbnails with faces and without faces perform similarly on average. The effect varied by niche, and multiple faces did best versus a single face. — [SEJ "Do faces help YouTube thumbnails" (summary via search)](https://www.searchenginejournal.com/do-faces-help-youtube-thumbnails-heres-what-the-data-says/563944/)
- A vidIQ study of 500 breakout thumbnails found a face in 69% of all 500, 75% of the top 100 and 80% of the top 50 by breakout score. This is association, not causal CTR lift. — [vidIQ Research, July 2026](https://vidiq.com/research/youtube-thumbnail-study/)
- A vendor review of 3,200+ song-video thumbnails and 127 A/B tests claimed faces added +33% CTR on average. Single vendor, music niche, unverified. — [mer.vin/LinkedIn summary](https://mer.vin/linkedin/youtube-thumbnail-ctr-for-song-videos-what-3200-thumbnails-teach-us-linkedin/)
- Blog claims of an 18-32% CTR lift from one expressive face, or 20-30% attributed to TubeBuddy, are uncited. A "2.3x CTR from YouTube Creator Insider" claim could not be verified. — [1of10 trends 2026](https://1of10.com/blog/youtube-thumbnail-trends-2026/), [unilink guide](https://www.unilink.us/blog/youtube-thumbnail-design-2026)
- A study of 1,043 channels with 100K+ subscribers found the shocked expression on about a quarter of Gaming faces versus 3% of Fitness, and gaming covers use faces less often than other niches (47%). This is prevalence, not performance. — [Creative Bloq / NetInfluencer coverage](https://www.netinfluencer.com/youtube-thumbnail-study-of-100k-channels-finds-shocked-faces-on-just-1-in-10-covers/)
- Creative Bloq reports a MrBeast experiment suggesting less exaggerated "shocked" faces get more views. The original data could not be found, so it is anecdotal. — [Creative Bloq](https://creativebloq.com/news/youtube-thumbnails)
- Text length guidance clusters at 3 words or fewer, or 3-5 words. A 2026 trend piece says top entertainment and gaming thumbnails use less text than in 2023. None of this cites controlled experiments. — [1of10](https://1of10.com/blog/youtube-thumbnail-trends-2026/), [growthos](https://growthos.in/blog/youtube-thumbnail-best-practices)
- Common design advice: keep the bottom-right corner clear of the duration badge, use large readable text and one clear focal point. — [vidIQ design tips](https://vidiq.com/blog/post/youtube-thumbnail-design-tips/), [Snappa](https://snappa.com/blog/youtube-thumbnail-best-practices/)
- Test one variable at a time. A gaming "busy background to clean gradient = +28% CTR" claim has no source or sample size. — [touhfa guide](https://touhfa.pages.dev/blog/thumbnails/high-ctr-thumbnails-guide/)
- Test & compare launched June 2024 for channels with Advanced features enabled. It is desktop-only and compares up to 3 thumbnails. YouTube's own blog says it is rolling out to any and all channels with Advanced Features enabled. — [YouTube blog "Rene's Top Five" June 2024](https://blog.youtube/creator-and-artist-stories/renes-top-five-june-14-2024/)
- Eligibility details: not for kids-labelled, mature or private videos. It is limited to public long-form videos, live stream archives and podcasts. Advanced features need phone or ID verification plus Channel History. — [fonearena / SEJ coverage](https://www.fonearena.com/blog/?p=426241), [search summary of YouTube support page](https://support.google.com/youtube/answer/13861714)
- Winner metric: multiple sources say the winner is chosen by watch-time share, not CTR. The tool returns watch time rather than separate CTR and retention. A conflicting source says "viewer engagement". — [vidIQ](https://vidiq.com/vi/blog/post/youtube-launches-new-thumbnail-testing-tool), [1of10 A/B guide](https://1of10.com/blog/how-to-ab-test-youtube-thumbnails/)
- Some 2026 blogs say Test & compare now needs YPP, others say no YPP is needed. This is unresolved. — [vidanalyze](https://vidanalyze.com/news/youtube-ab-testing-for-titles-thumbnails-2026-guide)
- A single-source claim says that if any experiment image is below 720p, all are downscaled to 854x480. Keep every variant at 1280x720 or larger. — [search result summary](https://alejandrorioja.com/youtube-thumbnail-size/)
- thumbnails.set: cost is about 50 quota units per call. The default project quota is 10,000 units/day, so about 200 calls/day. — [YouTube Data API quota table](https://developers.google.com/youtube/v3/determine_quota_cost)
- thumbnails.set file limit is 2 MB, JPEG or PNG (also application/octet-stream). The API has a "channel has uploaded too many thumbnails recently" error. — [thumbnails.set reference](https://developers.google.com/youtube/data/reference/rest/v3/thumbnails/set)
- 1280x720 at 16:9 is a recommendation in third-party guides. One blog claims a 50 MB limit, which conflicts with Google's 2 MB and should be ignored. — [piktochart](https://piktochart.com/blog/youtube-thumbnail-size/), [rioja](https://alejandrorioja.com/youtube-thumbnail-size/)

### Inferences
- For an Israeli Kick highlight channel, the reaction face is the genre norm. The real lever is clarity at small size (one face, one prop, 2-3 words). Do not over-trust "+30%" claims.
- Because Test & compare scores watch-time share, a clickbait-ier AI composite can lose even if it gets clicks. Plan on 2 variants per video (for example expressive vs calmer face) and one change per test.
- Export as JPEG at quality 85-90 at 1280x720 and keep it under about 1.5 MB, to stay under 2 MB with margin. Check size in code and re-encode if needed.
- At 1,850 subs, each video's impressions are low, so a Test & compare result will take time or may not reach significance. Treat results as directional.

### Gaps
- No primary YouTube Help text could be fetched. The YPP requirement for Test & compare, and the exact wording "thumbnail max 2 MB", are not confirmed on the live support page.
- No controlled CTR study specific to Hebrew or Israeli streamer-highlight channels. The Taklipu style was not analysed because no data was found.
- No hard number found for the "too many thumbnails recently" limit.

## 2. Free hosted generation/editing with face references (Gemini, ChatGPT, others)

### Takeaway
There is no free Gemini API tier for image output in late 2026. Sources dated Oct 2026 say the pricing page shows "Free tier: not available" for all Nano Banana models. The free Gemini app and ChatGPT free are manual-only and small (about 20 per day and about 2-3 per day respectively, both unofficial figures). No hosted option gives a free, automatable, reliable reference-image identity workflow at scale.

### Cited Findings
- As of 21 Oct 2026, Google's pricing page reportedly shows "Free Tier: Not available" for every Nano Banana image model including gemini-3.1-flash-image (Nano Banana 2). Paid price about $0.045 (512px), $0.067 (1K), $0.101 (2K), $0.151 (4K) per image, batch about half. Reported via aggregators, not read directly. — [developersdigest](https://www.developersdigest.tech/models/image-generation/google-gemini-api), [aifreeapi 3.1 flash image](https://www.aifreeapi.com/en/posts/gemini-3-1-flash-image-preview-api-free), [laozhang pricing](https://blog.laozhang.ai/en/posts/nano-banana-api-pricing-free-vs-pro)
- Google forum replies say gemini-2.5-flash-image is not available on the Free Tier, with free-tier quota 0 and 429 errors. Some paid-tier users also hit "free tier limit 0" bugs. — [discuss.ai.google.dev: bug thread](https://discuss.ai.google.dev/t/bug-paid-tier-1-account-getting-free-tier-requests-limit-0-on-image-generation-models-gemini-2-5-flash-image-gemini-3-pro-image-preview/123906), [free tier image gen thread](https://discuss.ai.google.dev/t/free-tier-api-image-generation/177423)
- Older claims of 500 free requests/day for image models are outdated, and one forum user mentioned a temporary free weekend. — [forum](https://discuss.ai.google.dev/t/does-gemini-2-5-flash-image-preview-have-free-tier/100509), [aifreeapi](https://www.aifreeapi.com/en/posts/gemini-image-free-tier-2026)
- Gemini app (manual, web UI only): most consistent figure is up to 20 images/day for Basic users with Nano Banana 2, attributed to Google's help page as of 29 Mar 2026. Other sources say 2-3 up to 100. One source claims Google Flow gives about 400 Nano Banana 2 images/day, uncorroborated. — [aifreeapi free tier 2026](https://www.aifreeapi.com/en/posts/gemini-image-free-tier-2026), [felloai](https://felloai.com/is-nano-banana-free/)
- ChatGPT Free (manual): OpenAI publishes no fixed number. Third-party figures are about 2-3 images/day on a rolling 24 h window, with some saying 3-10 per 3 h. One anecdote reports 22 images in one day without a limit message (12 Oct 2026). — [atlascloud](https://www.atlascloud.ai/blog/tips/chatgpt-image-generation-limit), [aiweekly](https://aiweekly.co/alerts/openai-quietly-cuts-chatgpt-free-tier-limits), [cometapi](https://www.cometapi.com/how-many-images-can-you-create-with-chatgpt-free-in-2026/)
- OpenRouter: free models are limited to 50 requests/day under $10 lifetime credit, 20 req/min. A free "Nano Banana" variant (gemini-2.5-flash-image-preview:free) existed, but there is no evidence it is still active or that it accepts reference images. Docs say image references are accepted as URL or base64 depending on the provider. — [OpenRouter free models summary](https://lilting.ch/en/articles/openrouter-free-models), [model page](https://openrouter.ai/google/gemini-2.5-flash-image-preview:free), [OpenRouter image docs](https://openrouter.ai/docs/features/multimodal/image-generation)
- Pollinations: API now needs a key from enter.pollinations.ai. A Feb 2026 update says kontext (the reference-image model) and other models moved to paid-only, and nanobanana-pro needs purchased pollen. Free allowance reportedly cut to 0.01 pollen/hour in Mar 2026. Plain "nanobanana" free status is unconfirmed. — [Pollinations GitHub](https://github.com/pollinations), [novita comparison](https://blogs.novita.ai/ko/free-ai-image-generation-api-no-key-required/)
- Hugging Face Inference Providers: free accounts get about $0.10/month of credits routed via HF, no overage, 402 error when exhausted. Kontext dev is reachable via fal or Replicate providers, so $0.10 is only a few images. — [HF pricing docs](https://huggingface.co/docs/inference-providers/pricing), [HF image-editor guide](https://huggingface.co/docs/inference-providers/guides/image-editor)
- Cloudflare Workers AI: 10,000 Neurons/day free, resets 00:00 UTC. FLUX.2 klein 4B is listed at 5.37 neurons per input 512x512 tile and 26.05 neurons per output tile, so input images are supported on that model. Per-image estimates range 57 to 5,000 neurons across blogs. — [Cloudflare pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/), [learnwithhasan](https://learnwithhasan.com/guide/free-ai-images-claude-code-cloudflare/)

### Inferences
- Rough Cloudflare arithmetic: a 1024x768 output is about 6 tiles x 26 = about 160 neurons, plus one or two 1024 input references at about 4-8 tiles x 5.4 = about 20-45 neurons each. That is about 200-250 neurons per image, so roughly 40 free images/day. This is my estimate from the quoted per-tile rates. Verify with one real call, and check the max input resolution and the number of reference images the endpoint accepts.
- Cloudflare FLUX.2 klein 4B is therefore the strongest candidate for a fully free, API-automatable, reference-image path with no GPU of your own. Its identity fidelity from multi-reference editing is untested here.
- Gemini app and ChatGPT free work as a manual "premium" path for the operator (about 20 and about 2-3 images a day). They cannot be automated without violating terms or using fragile browser automation, and should not be a pipeline dependency.
- A Gemini API key on a paid billing account would cost about $0.067 per 1K image. That breaks the $0 constraint, so exclude it.

### Gaps
- Could not read ai.google.dev pricing/rate-limit pages. Nano Banana "free: not available" is secondary-sourced. Test with one call to confirm.
- Exact current model names beyond "Nano Banana 2 (gemini-3.1-flash-image)", "Nano Banana Pro" and "2.1 / 2 Lite" not confirmed.
- Whether Cloudflare's FLUX.2 klein endpoint takes multiple reference images and how large, not confirmed.
- ChatGPT free daily count is unofficial and varies.

## 3. Open models for identity-preserving generation: quality, licences, VRAM

### Takeaway
For a channel operator who has the streamer's permission, licence risk is mostly about commercial use. Qwen-Image-Edit-2511 (Apache 2.0) and FLUX.2 klein 4B (Apache 2.0) are the clean, permissively licensed choices. FLUX.1 Kontext [dev], FLUX.2 [dev] and klein 9B are non-commercial. InsightFace-based adapters (InstantID, PuLID, IP-Adapter FaceID) inherit a non-commercial restriction on the face models. A monetised channel is arguably commercial use.

### Cited Findings
- FLUX.1 Kontext [dev] is under the FLUX.1-dev Non-Commercial License. Commercial use needs a BFL licence with usage-based fees. Code is Apache 2.0 and the autoencoder is Apache 2.0. FLUX.1 schnell is Apache 2.0. — [black-forest-labs/flux README](https://github.com/black-forest-labs/flux)
- FLUX.2 klein 4B and 4B Base are Apache 2.0. The 9B Base is under the FLUX non-commercial licence. The 4B fits in about 13 GB VRAM, the 9B needs about 29 GB per one source. The 4B accepts up to 4 reference images (10 in BFL's playground). — [BFL klein blog](https://bfl.ai/blog/flux2-klein-towards-interactive-visual-intelligence), [HF mirror](https://huggingface.co/Kuau/FLUX.2-klein-4B)
- Qwen-Image-Edit-2511 is Apache 2.0, a 20B model, and its headline improvement is character and identity consistency, including multi-person edits. Claims are self-reported. VRAM: no official figure. A community workflow runs BF16 on 10 GB VRAM plus 64 GB RAM with offload, and Vast lists a 5090 for the FP8. — [Qwen-Image-Edit-2511 model card](https://huggingface.co/Qwen/Qwen-Image-Edit-2511), [the-decoder](https://the-decoder.com/qwen-updates-image-editing-model-with-better-character-consistency/), [vast.ai](https://vast.ai/model/qwen-image-edit)
- A CelebA/CelebSET facial-editing evaluation found Nano Banana and Kontext-Pro best at preserving identity. Flux.1-Dev (text-to-image dev) was worst, with an identity drop above 80%. Qwen-Edit's number was not isolated, and Kontext [dev] was not tested. — [arXiv 2608.28802 (search summary)](https://arxiv.org/pdf/2608.28802)
- Practitioner comparison: "Kontext holds truer to the original image than Qwen Image Edit". A character-consistency test ranked FLUX.2 [dev] and Nano Banana 2 top, but used two comic-style characters. Both are qualitative. — [diffusiondoodles](https://diffusiondoodles.substack.com/p/qwen-image-edit-vs-flux1-kontext), [rentierdigital](https://rentierdigital.xyz/blog/ai-image-model-character-consistency-benchmark)
- InstantID: code is Apache 2.0, but the InsightFace face models (antelopev2) it downloads are non-commercial research only, and InstantX said they plan to move to commercially usable encoders. PuLID is Apache 2.0 on the node page but inherits the same antelopev2 restriction. InsightFace says its models need a separate commercial licence. — [InstantID repo](https://github.com/instantX-research/InstantID), [InstantID discussion](https://huggingface.co/InstantX/InstantID/discussions/2), [InsightFace licensing](https://www.insightface.ai/solutions/face-recognition-licensing), [PuLID node](https://comfy.icu/node/PulidInsightFaceLoader)
- InfiniteYou (ByteDance): no commercial licence found. ByteDance replied only that it would investigate. — [HF discussion #13](https://huggingface.co/ByteDance/InfiniteYou/discussions/13)

### Inferences
- Candidate ranking for open models (identity fidelity is my judgement from partial evidence, not a measured result):
  1. FLUX.2 klein 4B (Apache 2.0, multi-ref, 13 GB) is the best fit for Kaggle T4/P100 or Cloudflare. Test identity on real Oded frames.
  2. Qwen-Image-Edit-2511 (Apache 2.0, strong identity claims, but 20B, so it needs quantised weights on 16 GB).
  3. FLUX.1 Kontext [dev] (good editing, 12B, non-commercial licence). Fine as a fallback if you accept the licence risk.
  4. InstantID / PuLID / IP-Adapter FaceID (SDXL or FLUX, good likeness but licence-tainted). Lower priority.
- Because the finished artefact is a composite scene (face + props), identity is better enforced by a post-generation similarity gate (section 5) plus retry, whichever model is used.
- If the face is not good enough, a hybrid is possible: generate the scene with a placeholder person, then paste or blend the real face crop with feathering (a classical fallback that guarantees identity at the cost of realism). This was not researched and is a design suggestion only.

### Gaps
- No head-to-head ArcFace similarity numbers for FLUX.2 klein 4B versus Qwen-Image-Edit-2511 versus Kontext [dev] found. Needs an in-house test with 10-20 Oded frames.
- Qwen-Image-Edit-2509/2511 and FLUX.2 klein exact quantised VRAM figures not verified from model cards (huggingface.co not reachable).
- The licence status of "monetised YouTube channel = commercial" was not tested against the text of the FLUX non-commercial licence.

## 4. Where to run open models for free (Kaggle, Colab, ZeroGPU, providers)

### Takeaway
Kaggle is the only free GPU option with a documented, scriptable (CLI) workflow that can be driven from GitHub Actions. It gives about 30 GPU-hours/week (unofficial) on T4 x2 or P100 (16 GB each), but phone verification is needed. Hugging Face ZeroGPU is too small (about 3.5-5 GPU-minutes/day on a free account) to rely on. Colab free has no scriptable background execution or published limits.

### Cited Findings
- Kaggle: free P100 (16 GB) or 2x T4 (16 GB each). The weekly quota is commonly reported as about 30 GPU hours, but one source says it is not in Kaggle's docs and floats, shown in account settings. Session limit is reported as 9 h or 12 h (a source citing docs read 21 Sep 2026 says 12 h CPU/GPU, 9 h TPU). Phone verification is needed to enable GPU and internet. — [gpuperhour](https://gpuperhour.com/blog/free-cloud-gpus-and-credits), [gmicloud](https://www.gmicloud.ai/en/blog/best-free-gpu-cloud-options-for-ai-startups-and-researchers), [aimultiple](https://aimultiple.com/free-cloud-gpu)
- Kaggle automation: `kaggle kernels push -p <dir>` pushes the code plus kernel-metadata.json and runs the kernel. Metadata fields `enable_gpu` and `enable_internet` default to false. `machine_shape` examples include NvidiaTeslaT4, NvidiaL4 and TpuV5E8. A kernel `title` must resolve to the `id` slug or the push fails with 400. A GitHub Actions workflow with a repository secret for the Kaggle token works. — [Kaggle API docs: kernels_metadata](https://github.com/Kaggle/kaggle-api/blob/main/docs/kernels_metadata.md), [kernels.md](https://raw.githubusercontent.com/Kaggle/kaggle-api/main/docs/kernels.md), [DEV: Git-driven Kaggle](https://dev.to/yasumorishima/git-driven-kaggle-manage-notebooks-in-github-auto-deploy-via-actions-3ce4), [dev.to GitHub Actions + Kaggle API](https://dev.to/yasumorishima/kaggle-code-competitions-without-a-local-gpu-github-actions-kaggle-api-cloud-workflow-m3)
- Hugging Face ZeroGPU free account daily quota: current docs reportedly say 5 minutes/day, an older docs table and forum posts say 3.5 minutes. Resets 24 h after first use. Failed and timed-out calls can still consume quota. The default per-call duration is 60 s. A forum reply says "three times per day". Many public ZeroGPU Spaces for FLUX.1 Kontext [dev] exist (accept image + prompt). — [HF ZeroGPU docs](https://huggingface.co/docs/hub/spaces-zerogpu), [forum: free ZeroGPU quota](https://discuss.huggingface.co/t/what-is-the-free-zerogpu-quota-for-1-space/178610), [forum: 60 sec quota](https://discuss.huggingface.co/t/it-seems-use-60-sec-gpu-quota-instead-of-real-time-usage/175130), [Kontext Space example](https://huggingface.co/spaces/akhaliq/FLUX.1-Kontext-dev/blob/main/app.py)
- Colab free: T4 when available, 12 h max session, about 90 min idle timeout, "dynamic" unpublished limits, no guaranteed availability. Nothing was found on background or automated runs. — [hivenet Colab guide](https://www.hivenet.com/es/post/google-colaboratory-gpu-complete-guide-to-free-cloud-gpu-access-and-limitations), [gpuperhour Colab alternatives](https://gpuperhour.com/blog/google-colab-alternatives)
- A Google Colab CLI for running agents on cloud GPUs exists as of 2026, per one dev.to post (not examined). — [dev.to Colab CLI](https://dev.to/jovan_chan_9500711396d4e6/google-colab-cli-run-ai-agents-on-cloud-gpus-2026-4c7j)
- Heebo font: google/fonts ships `Heebo[wght].ttf` (variable) in ofl/heebo with OFL.txt (SIL Open Font License). — [google/fonts heebo](https://github.com/google/fonts/tree/main/ofl/heebo)

### Inferences
- A weekly Kaggle budget of about 30 h is ample. One thumbnail with FLUX.2 klein 4B on a T4 should take on the order of tens of seconds to a few minutes, including model load (my estimate, not measured). Kernel startup and model download (about 8-15 GB) will dominate, so cache models as a Kaggle dataset or private model to avoid re-download every run.
- Recommended automation: GitHub Actions job builds the face-frame inputs, uploads them as a private Kaggle dataset, `kaggle kernels push` a notebook with `enable_gpu` and `enable_internet`, polls `kaggle kernels status`, then `kaggle kernels output` to fetch results. This is feasible but not tested here. The Kaggle ToS on automated use and secret handling should be checked.
- ZeroGPU through gradio_client is a usable emergency fallback for 1-3 images/day, but not a pipeline foundation. Kontext Spaces also require HF login for API use in some cases.
- Use Colab only as a manual notebook, not for automation.

### Gaps
- Official Kaggle quota, session limit and ToS on automated pushes not verified (kaggle.com unreachable).
- `kaggle kernels push/status/output` details come from secondary sources. The metadata doc page did not list push/status/output.
- Default GPU in a pushed kernel (P100 vs T4x2) with the new `machine_shape` field not verified, and T4s are not supported in all FP8/bf16 paths (T4 has no bf16 support). This matters for Qwen and FLUX weights.
- Together AI, Fal and Replicate free-credit status for FLUX Kontext/FLUX.2 not verified in this pass.

## 5. Automated QA (face similarity, artefacts, headline-vs-face overlap, legibility)

### Takeaway
Use InsightFace buffalo_l (w600k_r50 ArcFace) cosine similarity of `normed_embedding` between the generated face and reference frames, with a threshold calibrated on your own pairs. 0.4-0.5 is only a plausible starting range, not a confirmed standard. Headline-overlap and legibility checks are straightforward with face-detection boxes and Pillow.

### Cited Findings
- No source confirms 0.4-0.5 as the buffalo_l same-person cutoff. A 2025 arXiv paper using ArcFace set 0.5 as its match threshold. DeepFace's ArcFace cosine threshold is about 0.687, from a different model and training. — [arXiv 2507.15961](https://arxiv.org/pdf/2507.15961), [sefiks ArcFace](https://sefiks.com/2020/12/14/deep-face-recognition-with-arcface-in-keras-and-python/)
- InsightFace's guide recommends cosine similarity on normalised embeddings (`face.normed_embedding`) and choosing the threshold from your own genuine and impostor pairs at an acceptable false-accept rate. A threshold picked on one sample may not transfer. — [InsightFace guide](https://insightface.ai/guides/choose-face-recognition-model-and-evaluate), [insightface issue #2239](https://github.com/deepinsight/insightface/issues/2239)
- InsightFace code is MIT but the pretrained model packs (buffalo_l, antelopev2) need a commercial licence. — [InsightFace licensing](https://www.insightface.ai/solutions/face-recognition-licensing)
- Test & compare and other CTR claims say small-size legibility and avoiding the bottom-right duration badge matter. — [vidIQ design tips](https://vidiq.com/blog/post/youtube-thumbnail-design-tips/)

### Inferences
- Calibration recipe: take about 100 real Oded frames, compute all genuine pairs (same person) and impostor pairs (other streamers/guests), pick the threshold at about 1% false accept, then require generated-face-to-reference-median similarity above it (also compare against the best-of-N reference). Cap retries at 3-4 and fall back to the best-scoring candidate or a plain frame-based thumbnail.
- For guests, require similarity to their own reference frame. Also check the number of detected faces equals the number requested, to catch extra or merged faces.
- Headline-vs-face overlap: run the face detector (InsightFace SCRFD or OpenCV/MediaPipe) on the generated image, expand each box by 10-15% margin, render the headline mask via `ImageDraw.textbbox(stroke_width=...)`, and test rectangle (or mask pixel) intersection. If it overlaps, try alternative anchor positions (top-left, top-right, bottom band avoiding the bottom-right corner), shrink the font down to a floor, then reject. This is design guidance, not sourced.
- Small-size legibility: downscale to 168x94 (and about 320x180) and check mean luminance contrast between the stroked text mask and its surrounding ring, plus minimum text height (for example >= 18% of image height) and 2-3 words. Run OCR on the downscaled image as an optional check (Hebrew OCR such as Tesseract `heb` is not tested here).
- Finger and hand artefacts: no reliable open detector was researched. Practical options are to detect hands (MediaPipe Hands) and either reject images with large visible hands, or prompt for hands out of frame. A VLM judge was not evaluated.

### Gaps
- No free, validated automated "extra fingers" detector found. This is unresolved.
- Confirmed buffalo_l threshold for same-person verification not found. Must be calibrated.
- 2026 identity-preservation benchmark that uses ArcFace and includes FLUX.2 klein or Qwen-2511 not found.

## 6. Hebrew RTL headline rendering with Pillow

### Takeaway
Pillow with libraqm renders Hebrew correctly (shaping and bidi) when you pass `direction="rtl"` and `language="he"`. Verify with `features.check("raqm")` on the Actions runner. Without raqm, fall back to python-bidi to reorder first. Stroke is supported via `stroke_width`. Wrapping is not RTL-aware, so wrap manually.

### Cited Findings
- `direction`, `features` and `language` parameters require libraqm. If raqm is available it is the default layout engine, otherwise BASIC is used (and an explicit RAQM request warns and falls back). Check with `PIL.features.check_feature("raqm")`. — [Pillow ImageFont docs](https://pillow.readthedocs.io/en/latest/reference/ImageFont.html)
- Direction values 'rtl', 'ltr', 'ttb'. Language is a BCP 47 code, so `he` for Hebrew. — [Pillow ImageFont docs](https://pillow.readthedocs.io/en/latest/reference/ImageFont.html)
- `stroke_width` is accepted by `getbbox`, `getmask` and the text-drawing methods. — [Pillow ImageFont docs](https://pillow.readthedocs.io/en/latest/reference/ImageFont.html)
- The newer ImageText wrapping path supports only ltr direction. — [PIL.ImageText source](https://pillow-radarhere.readthedocs.io/en/latest/_modules/PIL/ImageText.html)
- Without raqm, community advice is to reorder with python-bidi `get_display` before drawing. — [layout_engine example](https://huggingface.co/spaces/esmailx50/id/blob/main/core/layout_engine.py)
- Heebo is shipped as a variable TTF (`Heebo[wght].ttf`) under OFL. — [google/fonts](https://github.com/google/fonts/tree/main/ofl/heebo)

### Inferences
- On Ubuntu runners: `apt-get install libraqm0 libfribidi0 libharfbuzz0b` and ensure the Pillow wheel was built with raqm (the manylinux wheels bundle raqm, but check the feature flag). Fail the build loudly if raqm is off, rather than silently outputting reversed Hebrew.
- Black weight from a variable font: use `font.set_variation_by_axes([900])` (Pillow supports variable fonts through FreeType, which requires `set_variation_by_axes`, not verified in this pass) or ship a static Heebo-Black.ttf instead. Prefer the static file to avoid variable-axis quirks.
- Strong stroke recipe: draw text with `stroke_width` of about 6-10% of font size and a dark `stroke_fill`, optionally on top of an additional blurred shadow layer. Draw the stroke first and the fill second if the stroke eats into the glyphs.
- Hebrew niqqud, punctuation and mixed LTR numerals/Latin words (for example "KICK", "100") need bidi correctness, so test raqm output on strings with digits and Latin words. Quotes and exclamation marks may land on the wrong side without correct paragraph direction.
- Wrap manually for 2-3 word headlines: split words by measuring `getbbox` per word and join lines top-down, keeping RTL by right-aligning each line yourself.

### Gaps
- Pillow version-specific behaviour for `set_variation_by_axes` and ImageText was not checked against a running install. Run a quick local test.
- Hebrew punctuation mirroring edge cases not tested.

## 7. Policy: synthetic content disclosure and misleading thumbnails

### Takeaway
YouTube requires disclosure of realistic altered or synthetic content that could make a real person appear to say or do something they did not. Whether an AI thumbnail alone triggers the Studio disclosure toggle is unsettled in secondary sources. The firmer risk is the spam/deceptive practices policy: a thumbnail must not mislead about what the video contains.

### Cited Findings
- YouTube's disclosure rule covers realistic altered or synthetic content, for example making a real person appear to say or do something they didn't. It is set through the "altered content" option in Studio at upload. — [YouTube Help: Disclosing altered or synthetic content](https://support.google.com/youtube/answer/14328491), [YouTube blog](https://blog.youtube/news-and-events/disclosing-ai-generated-content)
- On thumbnails specifically, sources disagree. One says AI-generated still thumbnails don't need disclosure, another says if AI is used only for thumbnails and the footage is unmodified the prompt may not apply but you should check. — [air.io](https://air.io/en/youtube-glossary/what-is-youtubes-ai-content-disclosure-policy), [geekchamp](https://geekchamp.com/?p=271829)
- Other sources warn that thumbnails or titles implying authentic footage when it is synthetic can lead to enforcement, including demonetisation (unverified). — [influencermarketinghub](https://influencermarketinghub.com/youtube-inauthentic-content), [gofaceless](https://www.gofaceless.ai/en/blog/ai-disclosure-youtube-viewer-trust)
- YouTube's Spam, deceptive practices and scams policy bans misleading metadata or thumbnails that trick users into believing the content is something it is not, and malicious clickbait with misleading titles, thumbnails or imagery. The list is not exhaustive. Its inauthentic example mentions repetitive AI-generated imagery with AI-generated scripts. — [YouTube Spam policy](https://support.google.com/youtube/answer/2801973)
- YouTube removed two channels producing fake AI movie trailers under spam and misleading-metadata policies. — [pulse.bot](https://www.pulse.bot/ai/news/youtube-bans-two-popular-channels-that-created-fake-ai-movie-trailers-42e944af-83e7-47f4-b12e-c9c27b89f7dd/)

### Inferences
- Low risk if the AI composite is a stylised illustration of the topic of a video that really shows these people and events (the premise is true). Higher risk if the scene depicts something that does not occur in the video, or a realistic event involving a real person doing or saying something they did not.
- Safe practices: keep every scene element something that actually happens in the clip, never show a real person in a fabricated realistic event (for example a fake arrest or injury), avoid prop claims that imply false events, and consider ticking the altered-content disclosure when the thumbnail depicts a realistic scene that did not occur. Check the Studio upload flow wording, since thumbnails are not clearly covered.
- Keep proof of the streamer's permission (a short written OK) on file. Likeness handling for guests: consider obtaining guest consent, since guests' faces are also synthesised. YouTube's privacy and impersonation policies were not researched.
- Streamer-platform terms (Kick content, clip reuse) are out of scope and belong with another researcher.

### Gaps
- Could not read the live YouTube Help pages. Current wording on thumbnails and the May 2026 labelling update mentioned by one source are unverified.
- Guest-consent and likeness policy (privacy complaint process) not researched.
- Israeli law on likeness/personality rights not researched.

## Recommended free stack summary (inference from the above)
1. Primary: FLUX.2 klein 4B (Apache 2.0) with 1-4 reference face frames, run either via Cloudflare Workers AI free tier (about 10,000 neurons/day, automatable by REST, verify reference-image input) or on a Kaggle GPU kernel launched from Actions.
2. Alternative: Qwen-Image-Edit-2511 (Apache 2.0) quantised on Kaggle for the best identity claims. Kontext [dev] only if the non-commercial licence is acceptable.
3. Gate every candidate: ArcFace similarity vs calibrated threshold, face count, hand detection, headline placement via face boxes, 168x94 legibility. Retry up to N, then fall back to a plain frame thumbnail.
4. Headline: Pillow + raqm, Heebo Black, rtl/he, heavy stroke, manual wrapping. Export JPEG under 2 MB at 1280x720.
5. Upload via thumbnails.set (50 units). Use Test & compare manually in Studio on desktop (no API for it was found).
6. Manual-only premium fallback for hero videos: Gemini app (about 20/day unofficial) or ChatGPT free (about 2-3/day).

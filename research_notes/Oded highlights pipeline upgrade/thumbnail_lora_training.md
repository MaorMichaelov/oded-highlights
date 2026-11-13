# Free, scripted identity-LoRA pipeline for photoreal Hebrew-channel thumbnails (as of 2026-11-13)

## Method note and reliability

- Only github.com and raw.githubusercontent.com could be read directly. huggingface.co, docs.bfl.ai, kaggle.com, runcomfy.com, developer.civitai.com, blog.youtube and docs.github.com all failed DNS (`getaddrinfo ENOTFOUND`).
- "Primary" below means a README, doc or licence file read raw from GitHub. "Search summary" means WebSearch result text from a third-party or vendor page that I could not open. Treat search summaries as unverified.
- Nothing here was benchmarked. Every runtime, step-time and quality number in the Inferences blocks is an estimate or a proposal, not a measurement.
- Hugging Face model-card licences (Z-Image, Qwen-Image-Edit-2511, FLUX.1 Kontext) were not read first-hand. The licence of the Qwen-Image and Z-Image GitHub repos was read first-hand, and it is Apache 2.0 for both.
- The existing note `thumbnails_free_ai.md` in the same folder covers CTR evidence, Gemini-style APIs and thumbnails.set. This note does not repeat it.

---

## 1. Which open model: licence, identity fidelity, prompt following, VRAM

### Takeaway
FLUX.2 [klein] 4B (and 4B Base) is the only recent top-tier photoreal model whose GitHub README states Apache 2.0 for both the model and the fine-tuning base, and it fits free-GPU memory. That makes it the default pick. Z-Image (Apache 2.0 repo, Turbo and Base) is the strongest alternative, and community evidence on its likeness is anecdotal but good. Qwen-Image (20B) is licence-friendly but too heavy to train on a free T4. FLUX.1 Kontext, FLUX.2 dev and klein 9B are non-commercial.

### Cited Findings
- FLUX.2 [klein] 4B and 4B Base are Apache 2.0. 9B, 9B KV, 9B Base and FLUX.2 [dev] use the FLUX Non-Commercial licence. — [BFL flux2 README](https://raw.githubusercontent.com/black-forest-labs/flux2/main/README.md)
- The same README says klein 4B "fits in ~8GB VRAM" for inference, is released 2026-01-15, and does text-to-image, single-reference edit and multi-reference edit in one model. — [BFL flux2 README](https://raw.githubusercontent.com/black-forest-labs/flux2/main/README.md)
- BFL says to use the Base variants (50-step, undistilled) for fine-tuning and LoRA training. The distilled 4B is for fast inference. — [BFL flux2 README](https://raw.githubusercontent.com/black-forest-labs/flux2/main/README.md)
- Internal inconsistency in that README: the table points the 9B licence at `LICENSE-FLUX-NON-COMMERICAL`, while the prose says 9B uses the "FLUX.2-dev Non-Commercial License" (`LICENSE-FLUX-DEV`). Either way it is non-commercial. — [BFL flux2 README](https://raw.githubusercontent.com/black-forest-labs/flux2/main/README.md)
- Z-Image-Turbo is a distilled model that runs in 8 NFEs, fits "16G VRAM consumer devices", and is pitched on photorealism and bilingual (English and Chinese) text. Z-Image (non-distilled, 28-50 steps) was released on 2026-01-27. The README's variant table still says "To be released" for Omni-Base and Edit, so the table lags the news log. — [Z-Image README](https://raw.githubusercontent.com/Tongyi-MAI/Z-Image/main/README.md)
- The Z-Image GitHub repo LICENSE is Apache 2.0. The licence of the model weights on Hugging Face was not read. — [Z-Image LICENSE](https://raw.githubusercontent.com/Tongyi-MAI/Z-Image/main/LICENSE)
- The Qwen-Image GitHub repo LICENSE is Apache 2.0. — [Qwen-Image LICENSE](https://raw.githubusercontent.com/QwenLM/Qwen-Image/main/LICENSE)
- Qwen-Image-Edit-2511 shows `license: apache-2.0` on its Hugging Face card, is described as a 20B model, and Qwen claims better multi-person consistency (fusing two person images into one group shot). Unsloth and others publish GGUF builds. Vendor claim, with no independent face-similarity benchmark found. — [search summary: Qwen card / SGLang cookbook / Unsloth GGUF](https://huggingface.co/Qwen/Qwen-Image-Edit-2511)
- ai-toolkit (the trainer) currently lists as supported: FLUX.2-klein-base-4B and 9B, Z-Image Turbo, Z-Image, Z-Image De-Turbo, Qwen-Image / 2512 / 2.1 / 2.1 Turbo, Qwen-Image-Edit / 2509 / 2511, FLUX.1 Kontext-dev, SDXL, and many newer models (Krea 2, HiDream O1, etc.). — [ai-toolkit README](https://raw.githubusercontent.com/ostris/ai-toolkit/main/README.md)
- diffusers has `Flux2KleinPipeline` and a `train_dreambooth_lora_flux2_klein.py` script. The README calls klein "much more memory efficient and suitable for consumer hardware". — [diffusers flux2 docs](https://raw.githubusercontent.com/huggingface/diffusers/main/docs/source/en/api/pipelines/flux2.md), [diffusers DreamBooth FLUX.2 README](https://raw.githubusercontent.com/huggingface/diffusers/main/examples/dreambooth/README_flux2.md)
- BFL's training doc (via search) lists klein 4B Base training at 12 GB VRAM and 32 GB RAM, and 9B at 22 GB VRAM and 64 GB RAM. — [search summary of docs.bfl.ai](https://docs.bfl.ai/flux_2/flux2_klein_training)
- Hugging Face's klein LoRA blog (4 June 2026, per search) recommends 15-40 images that share one look, about 60 minutes on an RTX 4090 (24 GB). — [search summary: HF blog](https://huggingface.co/blog/black-forest-labs/flux-2-klein-lora)
- RunComfy (a cloud-training vendor, so biased) says 4B Base is the sensible default on 16 GB, starting at 512 or 768 px, batch size 1. — [search summary: RunComfy 16GB klein guide](https://www.runcomfy.com/trainer/ai-toolkit/flux-2-klein-16gb-vram-training)
- Likeness anecdotes. A Reddit post relayed on Telegram reports 95%+ likeness from a Z-Image-Turbo LoKr with settings close to the klein-9B LoKr config. Another user reports about 85% similarity on Z-Image Base after 100+ runs. RunComfy argues Base is the safer default for likeness. A community wiki claims klein 4B gives lower identity fidelity than 9B ("4B for prototyping, 9B for production"). None of these is a controlled test. — [r/StableDiffusion relay](https://t.me/s/rStableDiffusion/60216), [RunComfy Base vs Turbo](https://www.runcomfy.com/trainer/ai-toolkit/z-image-base-vs-turbo-lora-training), [knowledge-space wiki](https://knowledge-space.pages.dev/image-generation/flux-klein-character-lora/)
- ai-toolkit's Qwen-Image example is 24 GB-class: it uses a 3-bit quantised transformer plus `low_vram: true`, and `qwen_image_edit` examples are named 32gb. — [ai-toolkit Qwen example](https://raw.githubusercontent.com/ostris/ai-toolkit/main/config/examples/train_lora_qwen_image_24gb.yaml), [examples listing](https://github.com/ostris/ai-toolkit/tree/main/config/examples)

### Inferences
- Rank for this channel (licence, then fit, then quality): (1) FLUX.2 klein 4B Base as the training target, with klein 4B or Base for inference. (2) Z-Image Base or Turbo-with-adapter as the quality challenger, run as a 1-2 hour head-to-head. (3) SDXL (RealVisXL, Juggernaut) as the fallback if fp16 on the T4 misbehaves with the newer models. Qwen-Image 20B should not be trained on a free T4.
- Licence caveat on SDXL fine-tunes: I did not verify RealVisXL or Juggernaut licences. Check each model card before commercial use.
- The "non-commercial" 9B and dev models are risky for a monetised channel even if the output licence were lenient. I did not read the licence text, so do not rely on a "outputs are free to use" argument.
- A T4 has no hardware bf16 and is compute capability 7.5. Check fp16 stability for klein and Z-Image in a 10-minute smoke test before committing to either.
- Prompt following and Hebrew: none of these models is claimed to render Hebrew text well (Z-Image advertises English and Chinese). Plan text-free scenes and add Hebrew headlines in a CPU compositing step (Pillow or HTML-to-PNG on GitHub Actions) with a proper Hebrew font and RTL handling.
- "Taklipu-style" scene complexity (costume, neon city, hero large on one side) matches what klein and Z-Image Turbo do well in one pass. I found no benchmark of hero-plus-guest multi-person scenes. Expect guests to need the multi-reference route (section 4) or a separate LoRA.

### Gaps
- Hugging Face model cards (licence text for Z-Image weights, Kontext, Qwen-Image-Edit-2511, klein gating) could not be read, because the host is blocked from this session.
- No controlled likeness comparison of klein 4B vs Z-Image on the same dataset was found.
- Whether Qwen-Image 2.1 (listed in ai-toolkit) has a permissive licence is unknown.

---

## 2. Training a face LoRA on a free Kaggle GPU

### Takeaway
Kaggle's docs (Sep 2026, via the kaggle-api repo) list `NvidiaTeslaT4` (GPU T4 x2) as the default GPU, and secondary sources say the P100 was retired in Sep 2026. A klein-4B-Base LoRA should fit in about 15 GB per T4 if you quantise and cache, but nobody has published a Kaggle T4 timing. FP8 training in diffusers is impossible on a T4, so use ai-toolkit (quantised) or the diffusers NF4/bitsandbytes path. The 30 h/week quota is plenty for a 2-5 hour run.

### Cited Findings
- `kaggle kernels push --accelerator` accepts, "as of Sep 2026": NvidiaTeslaT4 ("GPU T4 x2, default GPU"), NvidiaTeslaA100, NvidiaL4, NvidiaL4X1, NvidiaH100, NvidiaRtxPro6000 and TPUs. "Some of these are only available to participants of specific competitions, and some are only available to Kaggle admins." P100 is not listed. — [kaggle-api kernels.md](https://raw.githubusercontent.com/Kaggle/kaggle-api/main/docs/kernels.md)
- A secondary guide claims Kaggle retired the P100 on 15 Sep 2026 and that T4 x2 is the only GPU in notebooks. Other guides still list the P100. Unverified. — [search summary](https://gabrubuilds.com/guides/kaggle-free-gpu/)
- Quota: most guides say about 30 GPU hours per week ("or sometimes higher depending on demand"), with a weekly reset. Session limit: 12 h for CPU and GPU sessions and 9 h for TPU in the newest source, while older ones say 9 h. All secondary. — [fastero.com](https://fastero.com/blog/kaggle-notebooks), [search summary](https://agentdeals.dev/vendor/kaggle)
- Secondary guides say phone verification is required for GPU and internet access, and that a missing Internet toggle in notebook settings usually means the phone is unverified. — [search summary](https://dev.to/amrendra_singh_c700783152/kaggle-gpu-free-limit-what-you-get-and-how-to-use-it-f8i)
- diffusers' FLUX.2 DreamBooth LoRA example uses `--do_fp8_training`, which "need[s] CUDA GPUs with compute capability at least 8.9". For older cards it points to SimpleTuner or ai-toolkit. The script also offers `--offload` (VAE and text encoder to CPU), `--cache_latents`, `--gradient_checkpointing`, `--use_8bit_adam` and bitsandbytes NF4 via `--bnb_quantization_config_path`. The remote text encoder is not supported for klein. — [diffusers README_flux2](https://raw.githubusercontent.com/huggingface/diffusers/main/examples/dreambooth/README_flux2.md)
- diffusers' klein-4B example defaults: resolution 1024, batch 1, gradient accumulation 4, AdamW, lr 1e-4, constant schedule, 100 warmup steps, 500 steps, guidance_scale 1. It is a demo on a dog dataset. — [diffusers README_flux2](https://raw.githubusercontent.com/huggingface/diffusers/main/examples/dreambooth/README_flux2.md)
- ai-toolkit's example configs (Qwen-Image) use: LoRA `linear: 16` / `linear_alpha: 16`; `adamw8bit`; `lr: 1e-4`; `batch_size: 1`; `steps: 2000` ("500-4000 is a good range"); `gradient_checkpointing: true`; `cache_latents_to_disk: true`; `cache_text_embeddings: true`; `caption_dropout_rate: 0.05`; `resolution: [512, 768, 1024]`; `quantize_te: true` with `qtype_te: qfloat8`; `low_vram: true`; samples every 250 steps and saves every 250 steps. The FLUX example uses rank 128 in the README snippet. — [ai-toolkit Qwen example](https://raw.githubusercontent.com/ostris/ai-toolkit/main/config/examples/train_lora_qwen_image_24gb.yaml), [ai-toolkit README](https://raw.githubusercontent.com/ostris/ai-toolkit/main/README.md)
- ai-toolkit captions: one `.txt` per image with the same basename. `[trigger]` in a caption is replaced by the config's `trigger_word`. You can resume from the last checkpoint after Ctrl+C. — [ai-toolkit README](https://raw.githubusercontent.com/ostris/ai-toolkit/main/README.md)
- Z-Image-Turbo is distilled, so ai-toolkit LoRA training uses a training/de-distill adapter (De-Turbo or a "training adapter") or you train on Base. Guides give 10-30 images, or about 20 face-focused images, and claim 16 GB is feasible. No Kaggle-specific guide was found. — [search summary: lilting.ch](https://lilting.ch/en/articles/z-image-turbo-lora-dedistill-adapter), [RunComfy Z-Image Turbo](https://www.runcomfy.com/trainer/ai-toolkit/z-image-turbo-lora-training)
- No source about training a FLUX-family LoRA on Kaggle T4 x2, with measured step times, was found. A SimpleTuner guide says Optimum-Quanto brings FLUX.1 training to about 20 GB. A FLUX schnell notebook warns `low_vram` is "painfully slow". — [search summary: SimpleTuner FLUX quickstart](https://github.imc.re/bghira/SimpleTuner/blob/v0.9.8/documentation/quickstart/FLUX.md)

### Inferences (proposals, untested)
- Proposed recipe (klein-base-4B in ai-toolkit): 25-40 images, LoRA rank 16-32 (alpha equal to rank), `adamw8bit`, lr 1e-4, batch 1, 1500-2500 steps (checkpoint every 250 and pick the best by the ArcFace metric in section 7), resolution bucketed at 768 or [512, 768] (1024 only if memory allows), `quantize: true` with qfloat8 on the transformer and text encoder, `cache_latents_to_disk`, `cache_text_embeddings`, `gradient_checkpointing`, `dtype` fp16 (no bf16 on T4), `low_vram` only if OOM, and caption dropout 0.05.
- Caption style for identity LoRAs, the common community heuristic (unverified here): a short caption with a unique trigger token ("odedsvr man") and a description of what varies (clothing, background, expression, headphones on or off) and not of fixed facial features. Include some images without headphones and some with, so the LoRA learns headphones as an optional prop. Caption beard and hair as "baseline" or leave them out.
- Regularisation: with modern flow models and rank 16-32, I would skip class-image regularisation and use caption dropout plus checkpoint selection. Treat that as a hypothesis, not a result.
- Dataset: 25-40 images, mostly 512 px and up on the face. Include the sharp studio thumbnails (face-forward, high-res), then webcam frames for expression variety. Remove blurry or compressed frames, because the LoRA learns the blur. Vary lighting and angle. A few full-body or half-body frames help the hero-on-one-side composition. Auto-crop face-centred 1:1 and 4:5 variants, plus the original frame.
- Time and fit (a guess): a 4B transformer with qfloat8 weights is about 4 GB. Gradient checkpointing at 768 px on a 15 GB T4 should fit, with the text encoder cached and unloaded. The T4's fp16 throughput is far below an RTX 4090 (about 60 minutes per HF blog), so expect roughly 3-8x longer, which is 3-6 hours for ~2000 steps. That fits the 12 h session and costs about 3-6 of the 30 weekly GPU hours. Measure first: run 20 steps and extrapolate.
- Use both T4s: ai-toolkit trains on one GPU. Use the second one to train a rival config in parallel (for example Z-Image, or klein at a different rank). Or keep GPU 1 idle for validation sampling. Kaggle counts wall-clock hours, not GPU-hours, as far as I know (unverified).
- Risks: (a) 29 GB system RAM on Kaggle is a recollection I could not source. The Qwen3-based text encoder of klein plus the transformer load can spike RAM, so cache embeddings and delete the encoder. (b) /kaggle/working has a size cap (I recall about 20 GB, unverified), so keep only the final LoRA safetensors (about 50-150 MB) plus 3-4 checkpoints. (c) fp16 overflow can produce NaN losses on T4. (d) Training from a random pip-installed ai-toolkit at its HEAD may break between runs, so pin a commit.

### Gaps
- No measured step time on a Kaggle T4 for any of these models.
- Kaggle RAM, disk, the exact GPU hour quota and the session limit were not read from Kaggle's own pages.
- Whether klein-base-4B on Hugging Face is gated (needs token and licence click-through) is unknown. Assume a token is needed.
- Exact ai-toolkit klein config filename: the examples listing shows no klein example file (it lists only FLUX.1, Qwen, Wan and similar). The klein config is probably created through the ai-toolkit UI or CLI templates. Verify in the cloned repo.

---

## 3. Automating Kaggle runs from GitHub Actions: push, secrets, internet, outputs, ToS

### Takeaway
The whole loop (push a kernel, poll status, download outputs) is scriptable from a CPU-only GitHub Actions job with the official `kaggle` CLI. Two one-time manual steps cannot be scripted: phone verification and adding the Hugging Face token under Kaggle Secrets. GitHub job limits are not an issue if you poll rather than block for more than 6 hours.

### Cited Findings
- `kernel-metadata.json` fields: `id`, `title`, `code_file`, `language`, `kernel_type` (`script` or `notebook`), `is_private` (default true), `enable_gpu` (default false), `enable_internet` (default false), `machine_shape`, `dataset_sources`, `competition_sources`, `kernel_sources`, `model_sources`. — [kaggle-api kernels_metadata.md](https://raw.githubusercontent.com/Kaggle/kaggle-api/main/docs/kernels_metadata.md)
- `kaggle kernels push -p DIR [--accelerator ID] [-t SECONDS] [--no-run]` uploads and runs. `kaggle kernels status owner/slug` reports status. `kaggle kernels output owner/slug -p DIR [--file-pattern REGEX] [-o]` downloads outputs, paged at up to 200 files per page. — [kaggle-api kernels.md](https://raw.githubusercontent.com/Kaggle/kaggle-api/main/docs/kernels.md)
- Auth options: `KAGGLE_API_TOKEN` env var (token from kaggle.com/settings/api), `~/.kaggle/access_token`, or legacy `kaggle.json`. — [kaggle-api README](https://raw.githubusercontent.com/Kaggle/kaggle-api/main/docs/README.md)
- Secrets: defined only in the notebook editor (Add-ons, Secrets) and "no CLI support". They are read in the kernel with `UserSecretsClient().get_secret("NAME")`. — [kaggle-api kernels.md](https://raw.githubusercontent.com/Kaggle/kaggle-api/main/docs/kernels.md)
- GitHub-hosted runner jobs are limited to 6 hours, and a workflow run to 35 days. — [GitHub Actions limits (github/docs copy)](https://docs.github.com/en/actions/reference/limits)
- Kaggle ToS: a DrivenData forum post says Kaggle's Terms grant it a royalty-free, perpetual, irrevocable licence over "User Submissions", and that deletion takes about two months. Secondhand, unverified. I found no Kaggle rule against LoRA training or image generation. — [DrivenData thread](https://community.drivendata.org/t/clarification-on-ai-coding-assistants-and-cloud-gpu-compute-with-competition-data/11479)

### Inferences (proposals)
- Mechanism: `kernels push` of a private script kernel (`enable_gpu: true`, `enable_internet: true`, `machine_shape: NvidiaTeslaT4`, `dataset_sources: ["<user>/oded-face-photos"]`). The kernel clones ai-toolkit (pinned), downloads weights from Hugging Face with the token from Kaggle Secrets, trains, runs a validation sample, and writes `oded_lora.safetensors` and a `metrics.json` to `/kaggle/working`. GitHub Actions then runs `kaggle kernels status` in a loop (every 60-120 s, up to about 5.5 h per job, or use two chained jobs or a scheduled cron poller), then `kaggle kernels output -p out --file-pattern ...`.
- Hand-off of the trained LoRA to the generation kernel: either (a) `kernel_sources: ["<user>/train-kernel"]` in the generation kernel's metadata, so its output appears under `/kaggle/input/`, or (b) upload the LoRA to a private Hugging Face repo from the training kernel (internet is on) and download it from the generation kernel, or (c) `kaggle datasets version`. Option (b) is the most robust and gives a durable copy off Kaggle. This is untested on Kaggle.
- Whether a kernel pushed by CLI inherits the Secrets attached in the UI is not documented in what I read. Test once. Fallback: a one-time manual "Save Version" in the notebook editor with the secret attached.
- Privacy: the face photos are personal data of a real person. Keep the Kaggle dataset and kernel private, and note the ToS licence wording above, unverified. If that concerns the streamer, store the dataset on a private Hugging Face dataset repo and download it inside the kernel instead.
- Kaggle may sometimes queue GPU sessions or have no T4 capacity. The workflow needs retry-with-backoff and a failure artifact.

### Gaps
- Kaggle's current ToS and its stance on generative-image use were not read. The page failed DNS.
- Whether internet-enabled GPU kernels can be pushed through the API without a verified phone is unknown.
- Exact quota behaviour (does a failed or cancelled run count?) is unknown.

---

## 4. Alternatives that need no training, and the InsightFace licence trap

### Takeaway
Reference-image methods exist and some are Apache-clean (klein multi-reference, Qwen-Image-Edit-2511), but there is no controlled evidence that they match a LoRA on a specific face. The classic face-encoder methods (InstantID, PuLID, IP-Adapter FaceID) depend on InsightFace models, whose weights are non-commercial research only.

### Cited Findings
- InsightFace: the code is MIT, but "the training data containing the annotation (and the models trained with these data)" are for non-commercial research only. Models auto-downloaded by the Python library follow that same policy. For buffalo_l and other recognition packs, and for inswapper, the README says to contact InsightFace for licensing. — [insightface README](https://raw.githubusercontent.com/deepinsight/insightface/master/README.md)
- FLUX.2 klein 4B supports multi-reference editing natively (up to what the model supports), with Apache 2.0 weights. — [BFL flux2 README](https://raw.githubusercontent.com/black-forest-labs/flux2/main/README.md)
- Qwen-Image-Edit-2511 is Apache 2.0 per its card (via search) and claims improved identity consistency in multi-person edits. — [search summary](https://huggingface.co/Qwen/Qwen-Image-Edit-2511)
- No head-to-head test of klein multi-reference vs a trained identity LoRA was found. A community wiki mentions a "PuLID-Flux2" pipeline and says klein 4B LoRAs are weaker than 9B, both unverifiable. — [knowledge-space wiki](https://knowledge-space.pages.dev/image-generation/flux-klein-character-lora/)
- A hosted klein 4B Base + LoRA endpoint exists at Replicate (`black-forest-labs/flux-2-klein-4b-base-lora`), and a fal endpoint takes a `loras` list of up to 3 weights. — [Replicate](https://replicate.com/black-forest-labs/flux-2-klein-4b-base-lora), [fal llms.txt](https://fal.ai/models/fal-ai/flux-2/klein/4b/base/lora/llms.txt)

### Inferences
- InstantID, PuLID and IP-Adapter-FaceID (and probably InfiniteYou, which I did not check) should be treated as non-commercial because of the InsightFace models they load, even where their own code is Apache or MIT. The channel is monetised, so skip them unless InsightFace grants a licence.
- Realistic expectation (hypothesis): reference-only methods give "looks like a bearded man with headphones" on side-view or costumed scenes, while a trained LoRA gives a recognisable person. Hero-in-costume scenes change pose, lighting and head angle a lot, which is where adapters lose identity. Recommend the LoRA as the main route, and klein multi-reference with 2-3 sharp photos as the zero-training fallback and as the route for 1-2 guests who supply their own photos and consent.
- A cheap test of this: generate the same 10 prompts with (a) klein multi-ref and (b) the LoRA, then compare mean ArcFace cosine. This takes about 20 minutes once the LoRA exists.

### Gaps
- InfiniteYou, FLUX Redux and Kontext licences were not checked. FLUX.1 Kontext-dev is known to be under the FLUX.1 dev non-commercial licence, but I did not read it.
- No independent identity benchmark of Qwen-Image-Edit-2511 or klein multi-reference was found.

---

## 5. Generation after training: runtime, batching, triggering from CPU-only CI, hosted LoRA options

### Takeaway
On a Kaggle T4, a 4-step distilled klein 4B or 8-step Z-Image Turbo should take seconds per image, so 10-20 variants per video cost minutes (estimate, not measured). The free hosted route most likely to work is a Hugging Face ZeroGPU Space, since free users can host two. No free hosted service with confirmed custom-LoRA support for these models was found.

### Cited Findings
- klein is marketed as "sub-second generation on consumer GPUs", and Z-Image-Turbo as "sub-second" on H800s with 8 NFEs and 16 GB. — [BFL README](https://raw.githubusercontent.com/black-forest-labs/flux2/main/README.md), [Z-Image README](https://raw.githubusercontent.com/Tongyi-MAI/Z-Image/main/README.md)
- Hugging Face ZeroGPU: free for all users to use. Free personal accounts "in good standing (verified email, account older than 30 days) can host up to 2 ZeroGPU Spaces". Hardware is half or a full RTX Pro 6000 Blackwell (48 GB or 96 GB). Gradio SDK only. Default GPU function limit is 60 s, extendable with `@spaces.GPU(duration=...)`. Shorter durations get queue priority. PRO users get 8x the daily quota. The free daily quota figure was not in the doc I read. — [hub-docs ZeroGPU](https://huggingface.co/docs/hub/spaces-zerogpu) (read via a local copy of the GitHub doc)
- Replicate lists `flux-2-klein-4b-base-lora` for custom LoRA inference. Pricing and free credit were not found. A third-party aggregator lists $0.02 per image for klein 4B with LoRA. — [Replicate](https://replicate.com/black-forest-labs/flux-2-klein-4b-base-lora), [MuAPI](https://muapi.ai/comparison/flux-2-klein-4b-text-to-image-lora)
- fal.ai exposes klein 4B Base LoRA and an edit-LoRA endpoint (up to 3 LoRAs). Free-credit terms were not found. — [fal llms.txt](https://fal.ai/models/fal-ai/flux-2/klein/4b/base/lora/llms.txt)
- Cloudflare Workers AI has a LoRA fine-tune feature (upload an adapter, run inference on a supported base model), documented around LLMs. The `flux-1-schnell` model page does not mention LoRA adapters. A `flux-2-klein-4b` model page exists in Cloudflare's docs, but LoRA support there was not shown. Free-tier terms were not found. — [Cloudflare fine-tunes docs](https://developers.cloudflare.com/workers-ai/features/fine-tunes/), [flux-1-schnell page](https://developers.cloudflare.com/workers-ai/models/flux-1-schnell)

### Inferences (estimates, unmeasured)
- Kaggle T4 inference estimate: klein 4B (4-step) at 1344x768 in fp16 is probably 4-15 s per image, and Z-Image Turbo at 9 steps is probably 10-30 s. So 20 variants take about 2-10 minutes per GPU, and half that if you split the batch over both T4s (run two worker processes with `CUDA_VISIBLE_DEVICES`). Model load adds 1-3 minutes. Measure it in the smoke test.
- Generate at the native model-friendly size (for example 1344x768, a multiple of 16) and then Lanczos-resize or crop to 1280x720 on the CPU runner. The target is a thumbnail under 2 MB (see the existing note for the limit).
- Request flow: a GitHub Actions workflow writes `prompts.json` and runs `kaggle kernels push` for a generation kernel (with the LoRA as a source). It then polls `kaggle kernels status`, pulls PNGs with `kernels output`, runs QC, composites Hebrew text, and uploads the winners as workflow artifacts or commits to a release. Kaggle cold start (queue, image boot, model download) adds a few minutes. Cache the base weights in a Kaggle Dataset or Model to skip the Hugging Face download.
- A ZeroGPU Space is the best "always-on" option: a private Gradio Space with klein 4B + the LoRA (loaded from a private model repo), called from Actions with `gradio_client` and an HF token. 48 GB of GPU makes 1280x720 trivial, and the 60 s limit is fine for a 4-step model. Unknowns: the free daily quota (authenticated free users get an unstated amount), whether a free Space can load a private repo (it can with a Space secret), and whether ZeroGPU suits a CI-style burst of 20 images. Keep Kaggle as the main path, with ZeroGPU as a fallback to test.
- Applying a LoRA trained on klein Base to the distilled klein 4B is a common community practice, but I did not verify that it works well. Safest is to generate with Base (50 steps, slower, about 10x the cost of distilled) if the distilled version loses likeness.
- Hosted paid-by-credit services (Replicate, fal) are not free in the strict sense. They matter only if free credits cover one-off tests. Cloudflare's route looks unavailable for image LoRAs.

### Gaps
- No measured generation time on a T4 for klein or Z-Image.
- Free credits and free-tier daily quotas for fal, Replicate and ZeroGPU could not be read.
- Whether Cloudflare Workers AI supports image-model LoRA for klein or Z-Image is not established.

---

## 6. Style: teaching the "Taklipu look" and staying original

### Takeaway
Use a prompt library built on abstract, describable ingredients (saturated cinematic grade, hero large on one side, costume and prop tied to the video topic, clean negative space for a headline) and not a style LoRA trained on another channel's thumbnails. A style LoRA is only safe if you train it on images you own or generate.

### Cited Findings
- No primary source on Taklipu thumbnails, on copyright in thumbnail style, or on YouTube's policy about imitation was read. I did not search for it because YouTube and most hosts are unreachable.
- The existing note lists generic design guidance: one clear focal point, 3 words or fewer of text, keep the bottom-right corner clear of the duration badge. — [thumbnails_free_ai.md](/home/user/oded-highlights/research_notes/Oded%20highlights%20pipeline%20upgrade/thumbnails_free_ai.md)
- BFL names style transfer and character consistency as the LoRA use-cases for klein Base (via search). — [search summary](https://docs.bfl.ai/flux_2/flux2_klein_training)

### Inferences (proposals, general knowledge, not sourced)
- Prompt library: a template with slots (topic scene, costume or prop, lighting palette, camera, composition) such as "medium close-up of {hero} on the left third, wearing {costume}, {setting} with neon magenta and cyan rim light, shallow depth of field, cinematic film grade, empty dark area on the right for headline, no text". Keep 15-30 templates by genre (horror, GTA-style city, medieval, sci-fi), and version-control them. Log which template produced each winning thumbnail, then feed YouTube Test & compare results back.
- Style LoRA only if the prompt library plateaus. Train it on 30-80 of your own best outputs (and your own channel's studio thumbnails) so it encodes your own look. Do not use Taklipu's thumbnails as training data. Training on another creator's images to reproduce their look is the clear risk (copyright in the images themselves, and possible imitation or reuse complaints), even though a general style is not protected by copyright.
- To stay original: do not reproduce a specific Taklipu composition, character, costume design or logo. Reference the genre and not the channel in prompts ("do not use the name Taklipu in prompts" is unnecessary for open models but avoids nudging toward recognisable copies). Run a reverse-image search on the best outputs.
- Treat any named game or film IP (GTA, Vice City) as a trademark and look-and-feel issue. Use "neon retro-Miami city" in the image and keep the real logos in the title only if the channel already uses them.

### Gaps
- No evidence gathered about Taklipu's actual thumbnail style, YouTube's policies on copied thumbnails or Israeli copyright law. All of the above is reasoning and not research.

---

## 7. Quality control, safety, consent, YouTube disclosure

### Takeaway
Gate every generated image on an ArcFace cosine similarity to the real reference set plus simple artefact checks, and keep a human final pick. The usual ArcFace tooling (InsightFace models) is itself non-commercial, so decide consciously. For disclosure, I found no source saying whether thumbnails fall under YouTube's "altered or synthetic content" label, which targets videos.

### Cited Findings
- InsightFace's recognition models (buffalo_l, etc.) require a licence for commercial use. See section 4. — [insightface README](https://raw.githubusercontent.com/deepinsight/insightface/master/README.md)
- YouTube's disclosure rule (via search): creators must flag realistic content a viewer could mistake for real footage of a real person, place or event, for example making a real person appear to say or do something they did not do, or replacing one person's face with another's. Obviously unrealistic or animated content, and routine production help such as scripts or automatic captions, is exempt. The toggle is "Altered or synthetic content" in YouTube Studio. A May-June 2026 update reportedly tightened enforcement and made labels more visible. — [YouTube blog on disclosure](https://blog.youtube/news-and-events/disclosing-ai-generated-content), [AIR Media-Tech 2026 guide](https://air.io/en/youtube-hacks/youtube-ai-disclosure-in-2026-label-it-yourself-or-youtube-will), [startupfortune June 2026](https://startupfortune.com/youtube-tightens-ai-disclosure-as-synthetic-video-gets-labeled-automatically/)
- None of the search results addresses thumbnails specifically. — same sources.
- The ai-toolkit and diffusers pipelines expose no built-in face-similarity metric. — [ai-toolkit README](https://raw.githubusercontent.com/ostris/ai-toolkit/main/README.md)

### Inferences (proposals)
- Identity gate: embed each generated face and the 20-40 reference faces, compute the cosine against the reference centroid (and the max over references), and reject below a threshold calibrated on your data. Calibrate by comparing real-vs-real (held-out photos) with real-vs-generated from several checkpoints, and choose the checkpoint with the best median. ArcFace buffalo_l thresholds are commonly cited around 0.3-0.5 cosine for "same person", but that is a rule of thumb. Calibrate yourself.
- Licence-clean alternatives (not verified): `facenet-pytorch` (MIT code, VGGFace2 weights, so data licence uncertain), AdaFace, or `deepface` wrappers. Check each model's weight licence. Because this check is internal, it never ships in the product, so the commercial risk is smaller, but it is still a licence question for the owner. A fully licence-free fallback is a human thumbnail pick plus a VLM yes/no judge, which is weaker for faces.
- Artefact filters (cheap, CPU): face detected exactly once for a solo hero (or the right count for guests), face-box area above a minimum fraction, sharpness (Laplacian variance) inside the face crop, hand and finger anomalies and melted-text detection through a VLM yes/no check, and exact match for forbidden items (watermarks, text). Take the top-k per video and let a human choose. Always include a prompt-side `text-free` instruction because the models garble Hebrew.
- Consent: get the streamer's written permission covering AI likeness, the LoRA and the training photos, and keep the LoRA private (not on public CivitAI or Hugging Face). Guests need their own explicit consent, and train nothing on a guest's face without it. Do not create a thumbnail that depicts the streamer doing or endorsing something false (a clickbait fake event). Use an obviously fantastical costume or setting and not a real news-like scene.
- Disclosure: a thumbnail of the real streamer in a costume in a neon city is stylised. It is probably not "realistic content a viewer could mistake for real footage", but it is photoreal, so this is a judgement call. Safest approach: turn the "altered or synthetic" toggle on whenever the video itself contains realistic synthetic content, and when in doubt tell viewers in the description that thumbnails are AI-assisted. Also check Studio's current wording on the day you ship, because the policy changed several times in 2026. EU AI Act transparency duties for deepfakes (Article 50, from August 2026) may matter if the channel targets EU viewers. I did not verify this.
- Also keep metadata: store the prompt, seed, LoRA version and score for each published thumbnail for audit.

### Gaps
- The YouTube Help page on altered or synthetic content could not be read. Nothing in my sources covers thumbnails.
- No licence-clean face-similarity model was verified.

---

## 8. Concrete step-by-step plan, times, and the human owner's one-time tasks

### Takeaway
About 1 hour of one-time human work, about 1.5 days of build and test (mostly waiting on Kaggle), then each video costs a few Kaggle minutes. All of this is a proposal built on the findings above, and nothing has been run.

### Cited Findings
- See sections 2, 3 and 5 for the sources behind each step (kaggle-api docs, ai-toolkit README and examples, BFL README, diffusers README).

### Inferences (the plan)

**One-time human tasks (about 60-90 minutes)**
1. Written consent from the streamer (AI likeness, LoRA, thumbnails) and from any recurring guest. 10 minutes.
2. Create a Kaggle account, verify the phone, and in notebook settings confirm the GPU and Internet toggles appear. Generate an API token at kaggle.com/settings/api. 15 minutes.
3. Create a Hugging Face account and an access token (read). Accept any model gate for FLUX.2-klein-base-4B / FLUX.2-klein-4B. Optionally create a private model repo for the LoRA. 10 minutes.
4. Add GitHub repo secrets `KAGGLE_API_TOKEN` (or `KAGGLE_USERNAME` and `KAGGLE_KEY` for legacy) and `HF_TOKEN`. In one Kaggle notebook, open Add-ons, Secrets, and add `HF_TOKEN`. 5 minutes.
5. Collect and curate 25-40 photos: sharp studio thumbnails and varied webcam frames, with and without headphones. 20-30 minutes.

**Build and test (about 1-1.5 days elapsed, 1-2 h of attention)**
6. Write `train_kernel.py` + `kernel-metadata.json` (private, GPU, internet, T4x2, dataset source): clone ai-toolkit at a pinned commit, install, download weights, write a klein-base-4B YAML (recipe in section 2), train, save LoRA, push it to a private HF repo, and write `metrics.json`. 1-2 hours to write.
7. Smoke test (20 steps, 10 minutes of GPU): get step time, peak VRAM, fp16 stability, RAM and disk. Decide at this point between klein 4B (Apache, preferred) and the Z-Image or SDXL fallback.
8. Full run: roughly 3-6 GPU hours (estimate, section 2). Sample checkpoints every 250 steps with fixed prompts.
9. Pick the checkpoint with the best ArcFace median and visual review. Test 10 hero-scene prompts and 3 guest prompts (multi-reference). 1 hour of human review.
10. Write `gen_kernel.py` (loads klein + LoRA, reads `prompts.json`, makes N variants per prompt with seeds across both T4s, saves PNG and a manifest) and a `generate.yml` GitHub workflow: write prompts, `kernels push`, poll `status`, `kernels output`, run QC and Hebrew-text compositing on the CPU runner, then upload the top picks as artifacts. 2-4 hours to write. Test the whole loop on 3 prompts. Expect about 10-20 minutes of Kaggle wall-clock per run including queue and model load.
11. Add the prompt library, the QC thresholds, a retry-with-backoff, and a log of prompt, seed and score per output.

**Per video (steady state)**
12. The pipeline gets the topic, picks 3-5 templates, generates 20 variants, filters by identity and artefact checks, and presents about 5 candidates. A human picks 2-3 for YouTube Test & compare. About 10-20 minutes elapsed, about 0.1-0.3 GPU hours. At 4 videos a week that is under 1.5 of the ~30 weekly GPU hours.

**Fallbacks**
- If klein 4B LoRA likeness is weak: try klein-base-9B only for private, non-monetised experiments (it is non-commercial). For production, try Z-Image Base, raise the rank, increase the face-crop share of the dataset, or add a second pass with multi-reference.
- If the T4 is too slow or unstable in fp16: switch to SDXL (RealVisXL or Juggernaut, licence check first) or use the ZeroGPU Space for inference only.
- If Kaggle rejects the API-pushed GPU run: the owner clicks "Save Version" in the notebook editor, and Actions polls and downloads only.

### Gaps
- Every duration here is an estimate. The first run's step-time measurement should replace them.
- Whether the free Kaggle quota survives a few failed runs per week is not established.

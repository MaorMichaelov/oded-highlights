# Free (no card) programmatic identity-preserving image generation for CI thumbnails (as of 2026-11-13)

**Method / reachability note (read first).** In this sandbox only `raw.githubusercontent.com` and `huggingface.co` resolved (checked with curl). `developers.cloudflare.com`, `docs.x.ai`, `ai.google.dev`, `openrouter.ai`, `gen.pollinations.ai`, `enter.pollinations.ai`, `fal.ai`, `api.together.ai`, `bfl.ai`, `discuss.ai.google.dev`, `*.hf.space` all failed DNS (they must be allowed in the session network settings to verify them directly). So:
- **Primary-verified** = read from GitHub raw sources of the vendor's own docs repo (Cloudflare docs repo, Pollinations repo) or from huggingface.co (docs repo, Space source, model API).
- **Secondary** = WebSearch result summaries of vendor pages, forum threads or blogs. Marked "(secondary)". I never opened OpenRouter, xAI, Google or Together pages directly.
- Nothing below was run end-to-end (no accounts/tokens here), so all code snippets are unexecuted proposals built from the docs.

---

## Q1. Ranked options and recommendation for 10-40 thumbnails/day, $0, no card

### Takeaway
Best verified free+no-card path is **Cloudflare Workers AI FLUX.2 [klein] 4B** (10,000 free neurons/day, up to 4 reference images, 1280x720 directly, Apache-2.0 model). Add **OpenRouter `:free` image models** (50 requests/day without any purchase, secondary) as a second engine/fallback, and a **HF ZeroGPU Space** as a third. Gemini API and xAI API have no usable free image tier. Identity fidelity of all the cheap open models (klein) is mediocre versus Nano Banana-class models, so plan for N attempts + automatic face-similarity selection.

### Cited Findings
Ranked table (quota facts are cited in the later sections; "calc" = my arithmetic from cited rates):

| Rank | Option | Free quota (no card) | Refs | 16:9 / res | Verdict |
|---|---|---|---|---|---|
| 1 | Cloudflare Workers AI `@cf/black-forest-labs/flux-2-klein-4b` | 10,000 neurons/day, reset 00:00 UTC; calc ~58-92 images/day at 1280x720 with 3 refs | up to 4, each must be <512x512 | width/height 256-1920 -> 1280x720 OK | Primary engine. Quota verified from vendor docs source. Weakness: tiny reference size (identity detail loss) |
| 2 | Cloudflare `flux-2-klein-9b` | same 10,000 neurons; calc ~5-6 images/day | up to 4, <512x512 | same | Better quality, too few images/day; 9B licence is non-commercial (HF tag) |
| 3 | OpenRouter `:free` models (`sourceful/riverflow-v2.5-pro:free`, `sourceful/riverflow-v2.5-fast:free`, `x-ai/grok-imagine-image-quality:free`) (secondary) | 20 req/min; 50 req/day if <$10 lifetime credits purchased, 1000/day after $10 purchase | Riverflow Pro: up to 10 refs; Grok Imagine Quality described as preserving identity with reference images | Riverflow lists 16:9; 1K/2K/4K | Strong second engine; free listings are volatile (promotional) so check live `/models` each run |
| 4 | HF Spaces via `gradio_client` (e.g. `black-forest-labs/FLUX.2-klein-9B`, `black-forest-labs/FLUX.1-Kontext-Dev`, `Qwen/Qwen-Image-Edit-2511`) | ZeroGPU: unauthenticated 2 min/day, free account 5 min/day GPU quota | klein-9B Space takes a list of input images | Space code caps width/height at 1024 (upscale needed) | Free but fragile (queues, app signature drift); good third fallback |
| 5 | Pollinations `gen.pollinations.ai` (`/v1/images/edits`) | Free credit is "Quest Pollen" earned via quests, no card; amount per day not found; some models `paid_only` | multi-ref on seedream-4.0, gemini-2.5-flash-image, flux.2-klein-4b | per-model | Unclear, probably not enough guaranteed free volume; test the account balance |
| 6 | Gemini API (AI Studio key) | Image models: no free tier per Google staff on forum (secondary); blog claims of 500/day conflict | - | - | Do not rely |
| 7 | xAI API (`grok-imagine-image*`) | No free tier found; $150/mo only via data-sharing opt-in that requires >=$5 prior spend | up to 3 refs | - | Not free |
| 8 | Together AI / fal / Replicate / BFL / Freepik(Magnific) / Leonardo / Ideogram / Krea / Stability | Trial credits at best, amounts/card rules unverified | varies | - | Not durable $0 |
| Manual | Gemini app, Copilot, ChatGPT free, Meta AI, Grok app | See Q9 | - | - | Human-in-the-loop only |

Pipeline sketch (proposal, not evidence): try CF klein-4B x3 seeds; if best face similarity < threshold, spend 1-3 OpenRouter free calls (Riverflow Pro / Grok Imagine free); else Space fallback; else queue for manual generation.

### Inferences
- With 10-40 thumbnails/day x 3 attempts = 30-120 generations/day, CF klein-4B alone (calc ~58-92/day) covers the low end; OpenRouter's 50/day extends it. Both together give ~100-140/day, enough for 40 thumbnails x 3 tries.
- Keep all quota-consuming steps behind a "remaining budget" guard and degrade gracefully, because every free tier here can be withdrawn.

### Gaps
- No live end-to-end test; no real face-fidelity measurement on the streamer's photos. Recommend a one-time calibration run (Q10).

---

## Q2. Cloudflare Workers AI (FLUX.2 klein / FLUX.1 schnell / others)

### Takeaway
Free plan = 10,000 Neurons/day (resets 00:00 UTC), no paid plan needed for these models per the docs. klein-4B is cheap (~100-170 neurons per 1280x720 image with 3 refs by calc) and supports 4 reference images, but each reference must be smaller than 512x512. No dedicated "edit with identity" model such as Kontext was found in the Cloudflare pricing table.

### Cited Findings
- Free allocation: "10,000 Neurons per day at no charge"; paid is $0.011 per 1,000 Neurons; "All limits reset daily at 00:00 UTC. If you exceed any one of the above limits, further operations will fail with an error." — [Cloudflare docs source: pricing.mdx](https://raw.githubusercontent.com/cloudflare/cloudflare-docs/production/src/content/docs/workers-ai/platform/pricing.mdx)
- Image model pricing from the same table: `flux-1-schnell` 4.80 neurons per 512x512 tile + 9.60 per step; `lucid-origin` 636 neurons per 512x512 tile + 12/step; `phoenix-1.0` 530/tile + 10/step; `flux-2-dev` 18.75 neurons per input 512x512 tile per step + 37.50 per output tile per step; `flux-2-klein-4b` 5.37 neurons per input 512x512 tile + 26.05 per output 512x512 tile; `flux-2-klein-9b` 1363.64 neurons per first MP (1024x1024), 181.82 per subsequent MP, 181.82 per input-image MP — [pricing.mdx](https://raw.githubusercontent.com/cloudflare/cloudflare-docs/production/src/content/docs/workers-ai/platform/pricing.mdx)
- Rate limit for Text-to-Image task: 720 requests/minute — [limits.mdx](https://raw.githubusercontent.com/cloudflare/cloudflare-docs/production/src/content/docs/workers-ai/platform/limits.mdx)
- klein-4B: fixed 4 steps, up to 4 image inputs, multipart form-data even for prompt only; params `prompt` (required), `input_image_0..3` (binary), `guidance`, `width` (256-1920, default 1024), `height` (256-1920, default 768), `seed`; inputs must be named `input_image_0`..`input_image_3`; "All input images must be smaller than 512x512"; prompt can refer to images by index ("take the subject of image 1 and style it like image 0") — [Cloudflare changelog source: klein 4B](https://raw.githubusercontent.com/cloudflare/cloudflare-docs/production/src/content/changelog/workers-ai/2026-01-15-flux-2-klein-4b-workers-ai.mdx)
- klein-9B: same interface and same 4-image / <512x512 constraint — [changelog source: klein 9B](https://raw.githubusercontent.com/cloudflare/cloudflare-docs/production/src/content/changelog/workers-ai/2026-01-28-flux-2-klein-9b-workers-ai.mdx)
- Output schema: `{"image": "<base64 string>"}` — [model schema JSON](https://raw.githubusercontent.com/cloudflare/cloudflare-docs/production/src/content/workers-ai-models/flux-2-klein-4b.json)
- Model terms property links to BFL ToS (`partner: true`) — same JSON.
- Licence: klein-4B tagged `apache-2.0` on HF; klein-9B tagged `other` / `flux-non-commercial-license` and gated — [HF API klein-4B](https://huggingface.co/api/models/black-forest-labs/FLUX.2-klein-4B), [HF API klein-9B](https://huggingface.co/api/models/black-forest-labs/FLUX.2-klein-9B)

### Calculations (mine, from cited rates; tile rounding rules are not documented)
- klein-4B at 1280x720 (921,600 px = 3.52 tiles of 262,144 px): output 91.6 neurons if proportional, 104 if rounded to 4 tiles, 156 if a 3x2 tile grid. Three refs (<512x512, >=1 tile each): +16.1. Total ~108-172 neurons -> **~58-92 images/day**.
- klein-9B: 1280x720 is <1 MP so first-MP price 1363.64 + 3 refs at 181.82 per MP (0.26-1 MP each) = ~1,507-1,909 neurons -> **~5-6 images/day**.

### Minimal call (proposal built from docs; response wrapper shape for REST not verified, standard Cloudflare `{"result":{...},"success":...}` assumed)
```python
import os, base64, requests
ACC, TOK = os.environ["CF_ACCOUNT_ID"], os.environ["CF_API_TOKEN"]   # token scope: Workers AI
URL = f"https://api.cloudflare.com/client/v4/accounts/{ACC}/ai/run/@cf/black-forest-labs/flux-2-klein-4b"
def gen(prompt, ref_paths, seed, w=1280, h=720):
    files = {f"input_image_{i}": (os.path.basename(p), open(p,"rb"), "image/png") for i,p in enumerate(ref_paths[:4])}  # each <512x512!
    data = {"prompt": prompt, "width": str(w), "height": str(h), "seed": str(seed)}
    r = requests.post(URL, headers={"Authorization": f"Bearer {TOK}"}, files=files, data=data, timeout=120)
    r.raise_for_status(); j = r.json()
    img = j.get("result", j)["image"]
    return base64.b64decode(img)
```
Pre-step: crop each reference tightly to the face/upper body and downscale to e.g. 480x480 (they must be <512x512), otherwise requests fail/are rejected.

### Inferences
- Because refs are capped under 512x512, use 2-3 tight face crops (different angles/lighting), not full frames; the model effectively sees a small face. Expect weaker likeness than a Nano Banana-class model.
- Output at 1280x720 is native (max 1920), so no upscale needed.

### Gaps
- Account creation without card: not directly verified (Workers Free plan is the documented tier; I did not open the signup flow).
- Real latency, tile rounding, REST response envelope, behavior when the daily neuron limit is hit (docs say "operations will fail with an error") not tested.
- Whether Cloudflare/BFL ToS restrict automated use or likeness of real people: not found.
- The 4B changelog's 512x512 input limit vs. per-tile pricing wording for bigger inputs: unresolved.

---

## Q3. OpenRouter free image models

### Takeaway
OpenRouter lists free (`:free`) image models with reference-image editing, and free-model access is 50 requests/day with no purchase (secondary figures). This is the best second source, but all facts below are secondary because openrouter.ai was unreachable.

### Cited Findings (all secondary: search-result summaries of OpenRouter pages/help center)
- Free model listings exist for `sourceful/riverflow-v2.5-pro:free`, `sourceful/riverflow-v2.5-fast:free`, `x-ai/grok-imagine-image-quality:free` — [Riverflow Pro free](https://openrouter.ai/sourceful/riverflow-v2.5-pro:free), [Riverflow Fast free](https://openrouter.ai/sourceful/riverflow-v2.5-fast:free), [Grok Imagine Image Quality free](https://openrouter.ai/x-ai/grok-imagine-image-quality:free)
- Riverflow V2.5 Pro: up to 10 reference images for editing; 4.5 MB request cap so URLs are recommended over base64; 1K/2K/4K; aspect ratios include 16:9; PNG/JPEG/WEBP; free endpoints are rate limited — [Riverflow Pro free page](https://openrouter.ai/sourceful/riverflow-v2.5-pro:free), [Riverflow Pro](https://openrouter.ai/sourceful/riverflow-v2.5-pro). A newer `riverflow-v2.6-pro-20261029` listing also appears — [OpenRouter](https://openrouter.ai/sourceful/riverflow-v2.6-pro-20261029) (free status unknown).
- Grok Imagine Image Quality (released May 18, 2026): "When given reference images, it preserves identity and structure"; paid price $0.05/image at 1K to $0.07 at 2K plus $0.01 per input image — [OpenRouter model page](https://openrouter.ai/x-ai/grok-imagine-image-quality), [free variant](https://openrouter.ai/x-ai/grok-imagine-image-quality:free)
- Free-model limits: 20 requests/min; accounts with <$10 lifetime credit purchases get 50 requests/day across free models; $10+ purchased raises to 1,000/day (sources differ on whether the status persists) — [OpenRouter help center](https://openrouter.zendesk.com/hc/en-us/articles/39501163636379), [fast.io](https://fast.io/resources/openrouter-rate-limit/), [pinggy](https://pinggy.io/blog/free_ai_model_apis_unlimited_tokens_openrouter/), [benchlm](https://benchlm.ai/md/free-tier/openrouter.md)
- API shape: image output via chat completions/Responses with `"modalities": ["image","text"]` and `image_config` (`aspect_ratio`, `image_size`); check `output_modalities` contains `image`; third-party code shows input images as `image_url` content parts — [OpenRouter image generation docs](https://openrouter.ai/docs/guides/overview/multimodal/image-generation); search noted 16:9 appears in a docs snippet but a supported-ratio list seen lacked it (conflict; providers clamp).
- Older `google/gemini-2.5-flash-image-preview:free` listing exists in search results but it is a preview model; likely stale — [OpenRouter](https://openrouter.ai/google/gemini-2.5-flash-image-preview:free)
- Price comparison page measured 11 Sep 2026 and warns that prices/models change often — [OpenRouter blog](https://openrouter.ai/blog/insights/image-generation-models-compared/)

### Minimal call (proposal; request/response shape from memory of the OpenRouter docs and the cited summary, UNVERIFIED here)
```python
import os, base64, requests
def or_gen(prompt, ref_urls_or_datauris, model="sourceful/riverflow-v2.5-pro:free"):
    content = [{"type":"text","text":prompt}] + [{"type":"image_url","image_url":{"url":u}} for u in ref_urls_or_datauris]
    body = {"model": model, "modalities": ["image","text"],
            "image_config": {"aspect_ratio": "16:9"},
            "messages": [{"role":"user","content":content}]}
    r = requests.post("https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"}, json=body, timeout=180)
    r.raise_for_status()
    url = r.json()["choices"][0]["message"]["images"][0]["image_url"]["url"]   # data:image/png;base64,...
    return base64.b64decode(url.split(",",1)[1])
```
Before relying on it: `GET https://openrouter.ai/api/v1/models` and filter `architecture.output_modalities` contains `image` and `pricing` all zero, so the pipeline discovers free image models dynamically.

### Inferences
- Because free listings are often launch promotions, treat any specific `:free` id as ephemeral; discover dynamically and fall back.
- 50/day shared across all free models and across keys means this is a ~12-16 thumbnail/day engine at 3 attempts each.

### Gaps
- Whether free variants accept image input on the free route and their actual identity quality: not verified (search could only confirm the paid model description).
- Free-tier data-retention/training terms ("free endpoints may log prompts") not checked; this matters because the streamer's face photos are sent.
- Exact current response field names (`message.images`).

---

## Q4. xAI API (Grok Imagine / Aurora) - free tier, editing, terms

### Takeaway
The xAI API has no ordinary free tier for images. Image generation/editing is paid per image (~$0.02-0.07 depending on model/host). The $150/month "free credits" requires opting into data sharing and prior spend of $5 (so a card), and does not appear usable for $0. The streamer's workflow (Grok Bot GenerateImage) is not reproducible for free via xAI directly; but Grok Imagine is reachable free-ish through OpenRouter `:free` (Q3) and Pollinations (Q6).

### Cited Findings (secondary; docs.x.ai unreachable)
- Official docs (via search) list `grok-imagine-image-2.0` editing at $0.04/image at 1K and 2K and "up to 3 reference images per request"; pricing page says generation and editing use Imagine API rates, no separate free allowance found — [xAI image docs](https://docs.x.ai/developers/model-capabilities/images), [xAI pricing](https://docs.x.ai/docs/pricing)
- Docs say $150/month in credits for teams that opt in to data sharing (eligible countries only; some countries excluded); a team must already have spent a minimum of $5 first; only admins can enable; cannot opt out afterwards — [data-sharing docs mirror](https://grok.cadn.net.cn/docs/data-sharing.html) (third-party mirror), search summary of [xAI docs]
- A tracker states the $25/month free API credits are no longer offered (Grok API paid-only as of 2026-04-13); other blogs still describe $25 sign-up credit - conflict — [agentdeals](https://agentdeals.dev/vendor/xai), [getaiperks](https://www.getaiperks.com/en/blogs/22-xai-grok-free-credits)
- Hosts: fal.ai $0.022/image for grok-imagine-image edit — [fal](https://fal.ai/models/xai/grok-imagine-image/edit/llms.txt); ModelsLab $0.024 — [ModelsLab](https://modelslab.com/models/xai/grok-imagine-image-i2i); Picsart API 200 free credits on signup — [Picsart](https://picsart.com/api-platform/models/grok-imagine-image/pricing)
- Free Grok app image generation is restricted/paywalled after January 2026 per one source (others describe strict caps) — [tech2](https://www.tech2.com/ai/chatgpt-vs-grok-vs-meta-ai-the-image-generation-battle-and-which-should-become-your-go-to-image-editor-in-2026-text-ws-l-10218312.html)

### Inferences
- Opting into data sharing means xAI may train on the streamer's reference photos; with the permission scope given, this should be an explicit decision for the operator.

### Gaps
- xAI ToS on public-figure/real-person likeness and automated use not found. Request body for `/v1/images/edits` not verified.

---

## Q5. Google AI Studio / Gemini API image models

### Takeaway
Official signals say there is **no free-tier image output** in the Gemini API (limit 0 on free tier for gemini-2.5-flash-image, Nano Banana 2/Pro, 3.1 flash(-lite) image). Some blogs claim ~500/day free for 2.5 Flash Image; this conflicts with Google staff statements and should not be relied on.

### Cited Findings (secondary; ai.google.dev and forum unreachable)
- Google staff reply: gemini-2.5-flash-image "is not available for use on the Free Tier" — [Google AI forum](https://discuss.ai.google.dev/t/free-tier-api-image-generation/177423), [other thread](https://discuss.google.dev/t/image-generation-at-free-tier-possible-or-not/322034)
- Forum: Google-affiliated responder said free tier quota limits for image models are 0, requiring a paid tier; gemini-3.1-flash-lite-image "suddenly" went to limit 0 after working before — [forum thread](https://discuss.ai.google.dev/t/gemini-3-1-flash-lite-image-suddenly-changed-to-free-tier-quota-limit-0/179208)
- Many paid Tier-1 projects report free-tier `limit: 0` 429s on image models (backend bug, unresolved in threads seen) — [forum](https://discuss.ai.google.dev/t/bug-paid-tier-1-account-getting-free-tier-requests-limit-0-on-image-generation-models-gemini-2-5-flash-image-gemini-3-pro-image-preview/123906), [forum](https://discuss.ai.google.dev/t/tier-1-prepay-project-still-applying-free-tier-quota-to-image-models/183204)
- A guide citing Google's pricing page updated 2026-09-24 says text Flash/Flash-Lite/2.5 Pro are free in the API while image and video models are not — [yingtu.ai](https://yingtu.ai/en/blog/google-gemini-api-free-tier-limits-2026)
- Conflicting blog claims of ~500 requests/day, 10/min free for 2.5 Flash Image — [laozhang.ai](https://blog.laozhang.ai/en/posts/gemini-image-generation-free-limit-2026), [yingtu.ai](https://yingtu.ai/blog/gemini-api-rate-limits-explained)
- Gemini image models are reachable through OpenRouter and Pollinations (`google/gemini-2.5-flash-image`, `gemini-3.1-flash-image`, `gemini-nano-banana-2.1`, `gemini-3-pro-image` in Pollinations list) but those need paid credit — [Pollinations APIDOCS](https://raw.githubusercontent.com/pollinations/pollinations/main/APIDOCS.md)

### Inferences
- A 5-minute probe in CI (one request with a fresh AI Studio key; a 429 with `limit: 0` = no free tier) is the only way to settle it for this account; cheap and worth doing once, but do not design around it.

### Gaps
- The official pricing page text could not be opened. Real-person likeness policy for Gemini API image edits not verified.

---

## Q6. Pollinations (current terms)

### Takeaway
Pollinations changed to a "Pollen" credit system. Primary docs show a rich image-edit API (many models incl. Nano Banana, Grok Imagine, Seedream, FLUX.2, GPT Image) but the free component is "Quest Pollen" earned via quests, with some models paid-only. A guaranteed free daily volume could not be established.

### Cited Findings (primary: Pollinations GitHub repo files)
- Unified API at `gen.pollinations.ai`; Pollen credits "$1 ≈ 1 Pollen"; secret keys `sk_` authenticate requests, `pk_` keys do not — [README](https://raw.githubusercontent.com/pollinations/pollinations/main/README.md), [APIDOCS](https://raw.githubusercontent.com/pollinations/pollinations/main/APIDOCS.md)
- "Earn Pollen by contributing, without a credit card" and "Pollen Quests: earn Pollen by completing Quests" — [README](https://raw.githubusercontent.com/pollinations/pollinations/main/README.md)
- Balances split into Quest Pollen ("tier" bucket) and paid Pollen ("pack"); models flagged `paid_only` cannot be paid with Quest Pollen and are hidden from key-only-Quest listings — [APIDOCS](https://raw.githubusercontent.com/pollinations/pollinations/main/APIDOCS.md)
- Image edit endpoint (OpenAI-compatible): `POST https://gen.pollinations.ai/v1/images/edits` multipart with `image`, `prompt`, `model`, `size`; repeat `-F image=@...` for multiple references on `bytedance/seedream-4.0`, `google/gemini-2.5-flash-image`, `black-forest-labs/flux.2-klein-4b`; GET `/image/{prompt}?model=...&image=url1|url2` also takes reference URLs — [APIDOCS](https://raw.githubusercontent.com/pollinations/pollinations/main/APIDOCS.md)
- Image model list includes `black-forest-labs/flux.1-kontext-pro`, `flux.2-pro/flex/max`, `flux-3-image(-klein)`, `google/gemini-3.1-flash-image`, `gemini-3-pro-image`, `openai/gpt-image-1.5/2/2.5/2.6`, `x-ai/grok-imagine-image(-quality/-2.0)`, `bytedance/seedream-4.0/4.5/5.0-*`, `qwen/qwen-image-2.1*`, `ideogram-ai/ideogram-v4-*`, `black-forest-labs/flux.1-schnell` (default), etc. — [APIDOCS](https://raw.githubusercontent.com/pollinations/pollinations/main/APIDOCS.md)
- Which models are paid-only and the Quest Pollen amounts are only exposed by live endpoints (`/v1/models`, `/quests/catalog`, `/account/quests`).
- Earlier changelog (secondary): kontext/seedream/grok/claude moved to paid-only on 2026-02-05; legacy keyless endpoint reportedly still works for non-premium models — [search summary of Pollinations changelog / Novita blog](https://blogs.novita.ai/free-ai-image-generation-api-no-key-required/)
- Secondary blogs disagree on daily free grants (one daily Pollen vs hourly expiry); no official figures — [fmhynotes](https://fmhynotes.pages.dev/pollinations-limits)

### Minimal call (primary docs)
```bash
curl -X POST "https://gen.pollinations.ai/v1/images/edits" \
  -H "Authorization: Bearer $POLLINATIONS_KEY" \
  -F "image=@ref1.png" -F "image=@ref2.png" \
  -F "prompt=..." -F "model=black-forest-labs/flux.2-klein-4b" -F "size=1280x720"
```

### Inferences
- Pollinations is useful as a testbed (one key, many models) but cannot be promised as $0 for 30+ images/day; treat as optional.

### Gaps
- Daily/quest Pollen amounts, per-image Pollen price of edit models, ToS on automated use and real-person images: not found.

---

## Q7. Hugging Face (Inference Providers, ZeroGPU Spaces via gradio_client)

### Takeaway
HF Inference Providers is not free for non-PRO users (no included credits). Free route = public ZeroGPU Spaces called with `gradio_client` and your HF token: free account gets 5 GPU-minutes/day. Good fallback with identifiable Spaces (klein-9B, Kontext-dev, Qwen-Image-Edit) but with fragile signatures and 1024 px cap.

### Cited Findings (primary: HF docs repo, HF API, Space source)
- Inference Providers: Free users get no monthly credits (must buy credits or go PRO); PRO gets $2/month — [HF pricing doc](https://raw.githubusercontent.com/huggingface/hub-docs/main/docs/inference-providers/pricing.md)
- ZeroGPU daily quota: unauthenticated 2 min, free account 5 min, PRO 40 min; resets exactly 24 h after first GPU usage; `large` size = half an RTX Pro 6000 Blackwell; quota remaining affects queue priority; PRO overage $1 per 10 min — [ZeroGPU doc](https://raw.githubusercontent.com/huggingface/hub-docs/main/docs/hub/spaces-zerogpu.md)
- `black-forest-labs/FLUX.2-klein-9B` Space: public, not gated, `RUNNING` on ZeroGPU as of check, tagged `mcp-server`; `infer()` has `@spaces.GPU(duration=85)`, takes `input_images` (gallery list), `mode_choice` ("Distilled (4 steps)" / "Base (50 steps)"), width/height 256-1024 (multiples of 8), seed, `prompt_upsampling`, returns `(image, seed)` — [Space API](https://huggingface.co/api/spaces/black-forest-labs/FLUX.2-klein-9B), [app.py](https://huggingface.co/spaces/black-forest-labs/FLUX.2-klein-9B/raw/main/app.py)
- Popular candidate Spaces found via HF API (likes): `black-forest-labs/FLUX.2-klein-9B` 945, `black-forest-labs/FLUX.2-klein-4B` 244, `black-forest-labs/flux-3-image-klein` 290, `black-forest-labs/FLUX.1-Kontext-Dev` 1661, `kontext-community/FLUX.1-Kontext-multi-image` 163, `Qwen/Qwen-Image-Edit` 874, `Qwen/Qwen-Image-Edit-2511` 511, `prithivMLmods/Qwen-Image-Edit-2511-LoRAs-Fast` 2794 (runtime stage not checked for these) — [HF Spaces API](https://huggingface.co/api/spaces?search=flux%20klein)
- Licences: Qwen-Image-Edit-2511 and klein-4B Apache-2.0; klein-9B and FLUX.1-Kontext-dev are FLUX non-commercial licences, gated — [HF model API](https://huggingface.co/api/models/Qwen/Qwen-Image-Edit-2511), [Kontext-dev](https://huggingface.co/api/models/black-forest-labs/FLUX.1-Kontext-dev)

### Minimal call (proposal; run `client.view_api()` once and pin the real signature)
```python
from gradio_client import Client, handle_file
c = Client("black-forest-labs/FLUX.2-klein-9B", hf_token=os.environ["HF_TOKEN"])
# print(c.view_api())   # confirm api_name (likely "/infer"), param order
img_path, seed = c.predict(prompt="...", input_images=[{"image": handle_file(p)} for p in refs],
                           mode_choice="Distilled (4 steps)", seed=0, randomize_seed=False,
                           width=1024, height=576, num_inference_steps=4, guidance_scale=1.0,
                           prompt_upsampling=False, api_name="/infer")
```
(Parameter names are inferred from the app.py function signature; the gallery input format may differ.)

### Inferences
- Single klein-9B generation inside ZeroGPU is ~few seconds of GPU, so 5 min/day plausibly gives dozens of gens, but this is not measured; queue time and quota debiting for failed calls unknown.
- Using the free-account token from a CI runner is a gray area for Space owners' intent; ToS on automation not checked.
- Output 1024x576 must be upscaled to 1280x720 (plain Lanczos is fine for YouTube thumbnails); but the klein-9B non-commercial licence is a concern for a monetised channel (output-use terms of the licence not readable, gated).

### Gaps
- Whether the `*.hf.space` endpoints resolve and respond from GitHub runners (unreachable here). Runtime state of Kontext/Qwen Spaces. Space-specific rate limits.

---

## Q8. Other providers (Together, fal, Replicate, BFL, Stability, Leonardo, Ideogram, Recraft, Krea, Freepik, Segmind, Novita, DeepInfra)

### Takeaway
No other provider was verified to offer a durable, no-card, image-reference free API. Mostly small one-time trial credits (secondary), and free text-to-image only (no reference) at best.

### Cited Findings (secondary)
- Together AI: free `black-forest-labs/FLUX.1-schnell-Free` model still listed on its model pages; original 3-month free promo (Oct 2024) expired; free model is text-to-image only (no references); another 2026 guide warns free models get retired/renamed; ~$1 trial credit claims unverified — [Together FLUX.1 schnell](https://together.ai/models/flux-1-schnell), [Together blog](https://together.ai/blog/flux-api-is-now-available-on-together-ai-new-pro-free-access-to-flux-schnell), [DEV guide](https://dev.to/build996/together-ai-free-api-run-llama-33-deepseek-r1-and-flux-image-generation-for-free-in-2026-19of)
- Replicate: mixed reports; API calls need token and prepaid credit for continued use — [toolfreebie](https://toolfreebie.com/?p=333), [Runflow](https://www.runflow.io/blog/free-ai-image-generation-api-lies)
- fal.ai: signup credits claimed, card requirement unconfirmed — [teamday comparison](https://teamday.pages.dev/blog/ai-image-video-api-providers-comparison-2026)
- Black Forest Labs API: no signup credit info found; klein/Kontext open weights are on other hosts — [search summary]
- Freepik (rebranded Magnific, April 2026): new API accounts get EUR 5 credit (trial, not ongoing) — [vantaige.io](https://vantaige.io/blog/freepik-ai-is-now-magnific-pricing-changes-2026)
- Krea: free consumer plan 100 compute units/day, no card; no free API found — [Krea blog](https://www.krea.ai/blog/best-free-ai-image-generators-in-2026)
- Leonardo/Ideogram: consumer free allowances reported (150/day Leonardo; Ideogram ~10 credits/day, sources differ); no free API info; some free plans restrict commercial use — [Krea blog](https://www.krea.ai/blog/best-free-ai-image-generators-in-2026)
- Stability AI: trial credits mentioned, amount not found — [Krea blog](https://www.krea.ai/blog/best-free-ai-image-generators-in-2026)
- Krea API docs list Grok Imagine 2.0 as an image model (paid API) — [Krea docs](https://www.krea.ai/docs/api-reference/image/grok-imagine-20-1.md)

### Inferences
- Do not plan on any of these for steady $0; one-time credits could still be used for a one-off high-quality test (e.g., to benchmark klein against Nano Banana/Grok on the streamer's face) but not for daily CI.

### Gaps
- Not checked at all: Recraft, Segmind, Novita, DeepInfra free tiers, Mistral/Le Chat API image tool, Adobe Firefly API (Firefly API is, to my recollection, enterprise/paid; unverified), Microsoft Copilot Designer programmatic access (no official API), Meta AI programmatic access (none found).

---

## Q9. Manual / human-in-the-loop free options and daily limits

### Takeaway
Copilot, Gemini app and Meta AI give the most free manual generations, ChatGPT free is tiny, Grok app is largely paywalled. All figures are inconsistent across blogs and change often.

### Cited Findings (secondary)
- Gemini app free: Nano Banana Pro cut to 2 images/day (falls back to standard Nano Banana); a March-2026 guide says ~20 Nano Banana 2 images/day at 1K plus 2 Pro/day; others differ (100/day old, Pro unavailable) — [Let's Data Science](https://letsdatascience.com/news/google-cuts-free-nano-banana-pro-image-generation-to-two-ima-175236df), [zenken](https://ai.zenken.co.jp/en/post/gemini-image-guide/), [Engadget](https://www.engadget.com/ai/google-limits-free-nano-banana-pro-image-generation-usage-due-to-high-demand-223442929.html?src=rss)
- ChatGPT free: ~2-3 images/day (one source reports ~10 in testing) — [tech2](https://www.tech2.com/ai/chatgpt-vs-grok-vs-meta-ai-the-image-generation-battle-and-which-should-become-your-go-to-image-editor-in-2026-text-ws-l-10218312.html)
- Copilot Designer: one source says 15 images/day free, no watermark, commercial use allowed — [Atlas Cloud](https://www.atlascloud.ai/blog/guides/free-alternatives-to-grok-image-generation-2026)
- Meta AI: free, runs on Meta's "Muse Image" since July 2026 per one source; cap unspecified — [tech2](https://www.tech2.com/ai/chatgpt-vs-grok-vs-meta-ai-the-image-generation-battle-and-which-should-become-your-go-to-image-editor-in-2026-text-ws-l-10218312.html)
- Grok app: restricted to paying subscribers after January 2026 per one source; another says strict free caps — same.

### Inferences
- A practical manual fallback: CI uploads a "thumbnail brief" (prompt + reference crops zip) as an artifact/issue; operator pastes into Gemini app (best identity edits in the evidence of Q10) and drops the result back. 

### Gaps
- Official help-center numbers for all of these; Bing Image Creator status (not checked).

---

## Q10. Identity/face-preservation evidence, likeness restrictions, licensing

### Takeaway
Evidence is thin and mostly vendor blogs: Nano Banana (Pro) > FLUX.2 for multi-reference identity stability; klein specifically drifts and benefits from tight prompts and one change per pass. No independent face-similarity benchmark of klein vs Qwen-Image-Edit vs Riverflow/Grok Imagine was found. Plan to measure on your own faces.

### Cited Findings (secondary, vendor/marketing blogs)
- WaveSpeed: FLUX.2 relatively poor in multi-reference identity stability vs Nano Banana Pro — [WaveSpeed](https://wavespeed.ai/blog/posts/flux2-arrives-on-wavespeedai--honest-comparison-with-nanobanana-pro); Renderfire noted identity drift even for Nano Banana Pro — [Renderfire](https://renderfire.com/blog/flux-2-vs-nano-banana-pro-comparison)
- Community ComfyUI workflows exist to fix klein identity drift; soft/blurry/shadowed faces make drift worse — [Floyo](https://www.floyo.ai/workflows/flux-2-klein-enhancer-for-identity-t-h3558gdqtme5)
- Prompt guidance: explicitly state "preserve facial identity, hairstyle, pose", one change per pass — [AIREITER](https://aireiter.com/blog/flux-2-klein-prompt-guide-image-editing-consistency)
- Realism test found klein outputs slightly waxy in places — [getimg](https://getimg.ai/blog/ai-realism-test-comparing-realistic-image-generation-models)
- BFL's own claim: FLUX.2 [pro] single-reference edit win-rate 59.8% vs Qwen-Image 49.3%, Kontext 41.2% (vendor, not klein) — [VentureBeat](https://venturebeat.com/ai/black-forest-labs-launches-flux-2-ai-image-models-to-challenge-nano-banana)
- Licensing: klein-4B Apache-2.0 (outputs unrestricted by licence); Qwen-Image-Edit-2511 Apache-2.0; klein-9B and Kontext-dev "other" non-commercial licence (output terms not readable, gated) — HF model APIs (Q2, Q7). OpenRouter/Pollinations output licences not checked.

### Inferences
- Likeness refusals: I found no evidence of refusals for self-supplied, permitted photos on klein/Riverflow/open models (they have no face-likeness policy of note in their docs); closed models (Gemini, OpenAI) are known in general to be stricter, but I did not verify this here.
- Best identity-for-cost is probably klein-4B with 2-3 tight crops + N seeds + automatic selection, escalating to Riverflow/Grok Imagine (OpenRouter free) for hard cases.

### Gaps
- No tests on Hebrew-free scene with costume/props; no data on guest + streamer two-person identity separation (multi-person scenes typically swap/blend faces; mitigate by giving each person a separate labeled reference: "person A is image 1, person B is image 2" — a proposal, not evidenced).

---

## Q11. Thumbnail prompt patterns, retries and automatic selection (InsightFace)

### Takeaway
Use a fixed prompt template with explicit "preserve identity from image N", 16:9, no text, high contrast, rim light; generate 3 seeds; score with ArcFace cosine similarity; pick highest above a threshold calibrated on your own images.

### Cited Findings
- Klein/Cloudflare prompting uses image index references in natural language ("take the subject of image 1 and ...") — [Cloudflare changelog](https://raw.githubusercontent.com/cloudflare/cloudflare-docs/production/src/content/changelog/workers-ai/2026-01-15-flux-2-klein-4b-workers-ai.mdx)
- Identity prompting tips (preserve facial identity/hairstyle/pose; one change at a time) — [AIREITER](https://aireiter.com/blog/flux-2-klein-prompt-guide-image-editing-consistency)
- InsightFace: use `FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])`, compare `face.normed_embedding` with a dot product (cosine); LFW same-person median cosine ~0.68, different-person ~0.01; thresholds quoted 0.25-0.35 for buffalo variants (so tune; do not take 0.4 as given) — [InsightFace guide](https://insightface.ai/guides/choose-face-recognition-model-and-evaluate), [LocalAI docs](https://localai.io/docs/features/face-recognition/), [Mixpeek](https://mixpeek.com/models/insightface-buffalo-l)
- InsightFace pretrained models are for non-commercial research only (licensing caveat; scoring is internal, but note it). LocalAI suggests OpenCV YuNet+SFace as an alternative — [LocalAI](https://localai.io/docs/features/face-recognition/)

### Prompt template (proposal, unverified by test)
```
Photorealistic cinematic YouTube thumbnail, 16:9. The man from images 1-3 (keep his exact face, hairstyle and skin tone) 
{action/pose, wearing costume/props} in {topic scene, e.g. neon-lit Vice City street at night, palm trees, pink and cyan lights}.
Close-up/medium shot, face large and sharply lit on the left third, expressive emotion {shock/excitement}, strong rim light, 
high contrast, saturated colors, shallow depth of field, clean empty space on the right for a title. No text, no logos, no watermark.
```
Guest: add "the second person is the woman/man from image 4 (keep her/his face)". Leave title text to be overlaid separately (Hebrew text is best rendered in Pillow/ffmpeg, not by the model).

### Selection code (proposal; CPU only, one-time ~300 MB model download)
```python
import cv2, numpy as np
from insightface.app import FaceAnalysis
app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"]); app.prepare(ctx_id=-1, det_size=(640,640))
def emb(img_bgr):
    fs = app.get(img_bgr)
    return max(fs, key=lambda f:(f.bbox[2]-f.bbox[0])*(f.bbox[3]-f.bbox[1])).normed_embedding if fs else None
refs = [e for e in (emb(cv2.imread(p)) for p in ref_paths) if e is not None]
centroid = np.mean(refs, 0); centroid /= np.linalg.norm(centroid)
def score(img_bgr):                      # in the main-streamer slot: largest face
    e = emb(img_bgr); return -1 if e is None else float(e @ centroid)
cands = [(score(cv2.imdecode(np.frombuffer(b,np.uint8),1)), b) for b in outputs]
best = max(cands, key=lambda t:t[0])     # accept if best[0] >= THRESH, else escalate engine
```
Calibrate THRESH by scoring held-out real photos of the streamer (same-person) vs other faces; expect same-person AI outputs well below real-photo scores. For two-person scenes, match each detected face to its own reference and take the min.

### Inferences
- Also add cheap non-identity checks: exactly the expected number of faces, face area >= ~8% of frame, no text artifacts (OCR not needed), aspect 16:9 resized to 1280x720 (YouTube thumbnail target; not from a fetched source).
- Attempt policy: 3 seeds per engine, stop early if score >= THRESH.

### Gaps
- No evidence on typical klein-4B cosine similarities for AI outputs vs refs; must be measured.
- YouTube thumbnail best practices (size/format limits) not sourced here.

---

## Source reachability summary (for the report writer)
- Primary/verified this session: Cloudflare docs repo files (pricing, limits, klein 4B/9B changelogs, model JSON), Pollinations README + APIDOCS, Hugging Face hub-docs (ZeroGPU, Inference Providers pricing), HF Space source/API for FLUX.2-klein-9B, HF model licence tags.
- Secondary (search summaries/blogs, direct page fetch failed with DNS error): everything on OpenRouter, xAI, Google/Gemini API, Together, fal, Replicate, Freepik, Krea, Leonardo, Ideogram, Stability, manual consumer apps, and all face-fidelity comparisons. `developers.cloudflare.com`, `docs.x.ai`, `ai.google.dev`, `openrouter.ai` need to be allowed in the session network settings to re-verify these directly.

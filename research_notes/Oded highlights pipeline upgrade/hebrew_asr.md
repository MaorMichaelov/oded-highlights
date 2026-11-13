# Free high-accuracy Hebrew ASR with word timestamps for Kick live-stream transcription (as of Nov 2026)

Research limitation: WebFetch could not reach huggingface.co or console.groq.com (network allowlist; DNS failure), so primary pages were NOT read directly. Everything below comes from search-result snippets (some are mirrors of primary pages). Every number is flagged where unverified. Worth re-running with those two hosts allowed, and above all worth benchmarking on the real audio (see "Recommended plan").

## ivrit-ai models in 2026: versions, WER vs stock Whisper, licences, decoding settings

### Takeaway
ivrit-ai ships Hebrew fine-tunes of Whisper large-v3 and large-v3-turbo (HF and CTranslate2 builds), Apache-2.0, trained on crowd-transcribe-v5, and they beat stock Whisper by a very wide margin on Hebrew (single-digit WER vs about 30% for stock large-v3 on FLEURS-he). The exact current leaderboard table and any newer 2026 versions could not be read.

### Cited Findings
- ivrit.ai's faster-whisper turbo model is based on ivrit-ai/whisper-large-v3-turbo, Apache-2.0, trained on crowd-transcribe-v5 — [ivrit-ai/whisper-large-v3-turbo-ct2 (via search result)](https://huggingface.co/ivrit-ai/whisper-large-v3-turbo-ct2) and [mirror](https://huggingface.co/LifeAi-dev/whisper-large-v3-turbo-ct2)
- Non-turbo CT2 build also exists: [ivrit-ai/whisper-large-v3-ct2](https://huggingface.co/ivrit-ai/whisper-large-v3-ct2); HF PyTorch: [ivrit-ai/whisper-large-v3](https://huggingface.co/ivrit-ai/whisper-large-v3) (card defers evaluation to the leaderboard)
- Leaderboard Space exists (datasets: eval-d1 = one manually transcribed podcast episode, eval-whatsapp, SASpeech ~4 h corrected portion); turbo results were added in a commit — [leaderboard](https://huggingface.co/spaces/ivrit-ai/hebrew-transcription-leaderboard/tree/737d82ae29c0d17614d368eda84ec26a561335d3), live at [hf.space](https://ivrit-ai-hebrew-transcription-leaderboard.hf.space/)
- Third-party table (Ozen-v1 card, claims its harness reproduces the ivrit leaderboard on 40/40 pairs) lists ivrit.ai turbo at 5.5% WER on eval-d1 (whisper-small 29.93%, whisper-base 48.32%); another community table gives ~5.5-8.1% across several Hebrew test sets — [Ozen v1](https://huggingface.co/itayinbar/Ozen-v1)
- Stock Whisper large-v3 reported at 32.9% WER on FLEURS Hebrew (different dataset, not comparable directly) — [ElevenLabs Hebrew page / vendor](https://elevenlabs.io/sv/speech-to-text/hebrew); an opinion blog reports ~4.8% on a clean podcast vs 25.0% on phone-line audio, showing channel sensitivity — [Times of Israel blog](https://blogs.timesofisrael.com/what-ai-really-hears-when-israelis-call/)
- Basic usage from the card: `WhisperModel('ivrit-ai/whisper-large-v3-turbo-ct2')`, `transcribe(..., language='he')` with defaults; no official beam/VAD/compute_type recommendation found — [mirror](https://huggingface.co/LifeAi-dev/whisper-large-v3-turbo-ct2)
- Community derivatives exist (e.g. d4 turbo checkpoint, Ozen-v1, Whisper-Hebrish) — [israelisraeli d4](https://huggingface.co/israelisraeli/ivrit-faster-whisper-turbo-d4), [Ozen v1](https://huggingface.co/itayinbar/Ozen-v1); not validated

### Inferences
- Benchmarks are clean podcast/read speech; Kick audio (shouting, game sound, 160p-rendition audio, slang) will be considerably worse than 5.5%; expect perhaps 15-30% WER (my guess, unsourced).
- The ivrit fine-tune should also reduce stock-Whisper garbling, but fine-tunes still hallucinate on silence/music.
- Moving from Groq stock turbo to ivrit-ai is probably the single biggest accuracy gain available.

### Gaps
- Live leaderboard numbers for large-v3 vs turbo vs ivrit-ai large-v3 and any 2026 newer releases (v2/v3 naming, "d4" etc.): not retrievable.
- Official recommended decoding settings (ivrit.ai GitHub/blog): not found. Check ivrit-ai GitHub README for "stable-ts"/chunking advice.

## CPU speed: faster-whisper turbo on 4 vCPU, whisper.cpp, distil; live keep-up; parallel jobs

### Takeaway
No reliable published RTF for large-v3-turbo on 4 CPU cores was found; it must be benchmarked. Turbo reduces decoder from 32 to 4 layers but keeps the full encoder, which dominates on CPU, so gains vs large-v3 are smaller on CPU than on GPU.

### Cited Findings
- Turbo keeps the large-v3 encoder and cuts decoder 32 -> 4 layers — [whispernotes](https://whispernotes.app/blog/introducing-whisper-large-v3-turbo)
- GPU batched numbers only: RTX 3060 laptop int8 turbo 46.1 s sequential vs 18.7 s batched (batch 10); RTX 4090 ~80x real time single, ~175x batched 16 — [spheron](https://www.spheron.network/blog/faster-whisper-gpu-cloud-production-deployment-guide/), [gigagpu](https://gigagpu.com/rtx-4090-24gb-whisper-benchmark/) (vendor blogs, weak methodology)
- One guide lists a Ryzen 7 7700X at ~10x real time INT8 CPU, model/threads unspecified — [spheron](https://www.spheron.network/blog/faster-whisper-gpu-cloud-production-deployment-guide/) (unreliable)

### Inferences
- Previous operator's finding ("accurate but slow") fits: on 4 shared GitHub vCPUs (typically slower than a desktop Ryzen), full large-v3-class encoder likely gives RTF around 0.5-1.5 (guess, unverified). Near-real-time for one stream is therefore marginal; a 48 h stream requires keeping RTF < 1 including VAD skipping.
- Levers: VAD to drop silence (streams often 30-50% non-speech), int8 (faster than int16 on CPU generally), beam 1, BatchedInferencePipeline (helps mainly with GPU, some CPU gain), and sharding time ranges across a GitHub Actions matrix (each job gets its own 4 vCPU; public-repo concurrency is up to ~20 jobs on free plan — unverified here). Matrix sharding is the most reliable way to catch up: split the VOD/HLS segments into chunks (e.g. 30-60 min) and run N jobs.
- Because timing is per-chunk, parallel jobs trade nothing in accuracy except chunk boundaries (overlap 10-20 s and de-duplicate).

### Gaps
- Measured RTF for ivrit turbo CT2 int8 on ubuntu-latest 4 vCPU; whisper.cpp numbers; distil-whisper Hebrew availability (none found). Plan a 10-minute benchmark job.
- GitHub Actions free-plan concurrency and usage limits not verified in this session.

## Free GPU options headless from CI

### Takeaway
Kaggle is the best-fit free GPU (about 30 h/week, scriptable via Kaggle API), Colab free is unreliable for unattended use, HF ZeroGPU quota is far too small (minutes/day) for hours of audio.

### Cited Findings
- Kaggle: commonly ~30 GPU h/week, reset weekly (Saturday 00:00 UTC per one source); sources disagree on whether the number is officially published; session limit 9 h (GPU) vs 12 h (CPU) per conflicting sources; phone verification needed to enable accelerators and internet; queueing possible — [aimultiple](https://research.aimultiple.com/free-cloud-gpu), [gpuperhour](https://gpuperhour.com/blog/free-cloud-gpus-and-credits), [resourify](https://resourify.com/resources/kaggle)
- Colab: Google says limits are not published, not guaranteed, fluctuate; background execution is a paid feature; a Colab CLI reportedly launched June 2026 (unverified) — [Colab FAQ](https://goo.gle/2wgbjec), [hivenet](https://www.hivenet.com/post/google-colaboratory-gpu-complete-guide-to-free-cloud-gpu-access-and-limitations), [mer.vin](https://mer.vin/2026/06/google-colab-cli-provision-gpus-and-run-scripts-from-your-terminal/)
- HF ZeroGPU: free account ~5 min/day GPU (older docs 3.5 min), unauthenticated 2 min, PRO 40 min; calls via gradio_client must pass hf_token or they are charged to the anonymous IP quota; failed calls still consume quota — [HF docs](https://huggingface.co/docs/hub/spaces-zerogpu), [forum](https://discuss.huggingface.co/t/what-is-the-free-zerogpu-quota-for-1-space/178610)

### Inferences
- Kaggle math: large-v3-turbo on a T4/P100 batched runs very roughly 20-60x real time (unmeasured here), so 30 GPU h/week could cover far more than 48 h of audio; the real constraint is orchestration (push kernel, poll, pull output) and phone-verification.
- Kaggle needs the audio to be reachable: either upload as a private dataset, or have the kernel fetch the HLS directly (internet must be enabled; Kick may block datacenter IPs - untested).
- ZeroGPU: 5 min/day cannot transcribe more than ~1-2 h of audio per day even at 20x; not viable as primary.

### Gaps
- Not verified: Kaggle `kaggle kernels push` flow and ToS on automation, internet in API-pushed kernels, exact current quota; public ivrit-ai Spaces/endpoints and any other free hosted ivrit inference (none found).

## Groq free tier and other free APIs

### Takeaway
Groq's table lists whisper-large-v3-turbo at 20 RPM, 2K RPD, 7.2K audio-s/hour, 28.8K audio-s/day (8 h/day) — but it is unclear whether these are free-tier or base values, and the 48 h stream would need ~6 days of quota. Other providers give only one-time credits.

### Cited Findings
- Groq rate-limits page: whisper-large-v3-turbo 20 RPM / 2K RPD / 7.2K ASH / 28.8K ASD — [Groq docs](https://console.groq.com/docs/rate-limits) (via search snippet; plan attribution ambiguous per aggregators, e.g. [dev.to](https://dev.to/build996/free-whisper-api-groq-deepgram-assemblyai-compared-562m))
- Verify actual limits at console.groq.com/settings/limits — [fast.io](https://fast.io/resources/groq-rate-limit/)
- Deepgram: one-time $200 credit, Hebrew advertised — [Deepgram Hebrew](https://deepgram.com/product/speech-to-text/hebrew), [dev.to](https://dev.to/build996/free-whisper-api-groq-deepgram-assemblyai-compared-562m)
- Soniox app: "10 free credits every week" (unit unclear); ElevenLabs Scribe Hebrew page offers free tool, quota unstated — [Soniox](https://soniox.com/soniox-app/use-cases/hebrew-voice-notes), [ElevenLabs](https://elevenlabs.io/speech-to-text/hebrew)

### Inferences
- Groq's large-v3 (non-turbo) limits not found; typically similar-or-lower ASD/ASH. Stock large-v3 vs turbo on Hebrew: turbo is generally slightly worse; neither approaches ivrit fine-tune.
- Groq is useful only as a fast first pass/topic discovery on a subset; Groq supports `timestamp_granularities[]=word` and `prompt` (from my background knowledge; not re-verified here). Prompt with names helps slightly; prompts can also induce hallucination.
- Deepgram/Assembly/Soniox credits are finite and cannot cover 48 h repeatedly; at best a validation oracle.

### Gaps
- Official free vs developer tier split, file size limit (25 MB free, believed), Gladia, Google, Azure Hebrew quotas, Hebrew quality of commercial APIs: not found.

## Accuracy improvements

### Takeaway
Gate audio with VAD, turn off conditioning on previous text, use a better audio rendition if available, and use the ivrit fine-tune; hallucinations like "תודה רבה" are the classic Whisper silence artefact and should also be filtered post-hoc.

### Cited Findings
- Silero VAD gating before Whisper is the main fix for silence hallucinations; `condition_on_previous_text=False` reduces repetition loops; `no_speech_threshold` (default 0.6) is a secondary defence; `hallucination_silence_threshold` applies only with word_timestamps — [popularai](https://www.popularai.org/p/whisper-hallucinations-during-silence), [dev.to](https://dev.to/nareshipme/whisper-hallucination-on-silence-why-your-transcript-loops-the-same-phrase-2pg4), [theneuralbase](https://theneuralbase.com/faster-whisper/learn/intermediate/reducing-hallucinations-via-vad/)
- Compression-ratio threshold catches "Thank you." style repeats — [theneuralbase](https://theneuralbase.com/faster-whisper/learn/intermediate/compression-ratio-threshold/)
- Hallucination study: [arXiv 2501.11378](https://export.arxiv.org/pdf/2501.11378)

### Inferences
- Rendition: 160p HLS video renditions often carry the same audio bitrate or a low one; if a higher rendition (e.g. 480p/source) has better audio (e.g. 128 kbps AAC) use that, since ASR quality drops with heavy compression; cost is bandwidth only. Unverified for Kick.
- Suggested config: faster-whisper, model ivrit-ai/whisper-large-v3-turbo-ct2, language="he", compute_type int8, beam_size 1-5, vad_filter True with vad_parameters (threshold ~0.5, min_silence_duration_ms ~500, speech_pad_ms ~200), condition_on_previous_text False, temperature fallback default, no_speech_threshold 0.6, log_prob_threshold -1.0, compression_ratio_threshold 2.4, word_timestamps True; blacklist post-filter for standalone "תודה רבה", "תודה", "תרגום ע"י..." only when segment avg_logprob is low or duration very short.
- Word timing: Whisper cross-attention word timestamps are good enough for captions; stable-ts or WhisperX with a Hebrew wav2vec2 aligner could refine but add CPU cost; no Hebrew aligner verified. Diarization (pyannote) is CPU-costly and low value for word captions; skip. Music/game separation (demucs) costs more than real time on CPU; skip unless on Kaggle GPU.
- LLM post-correction of names: use only for a closed list of streamer names via fuzzy matching, not free rewriting (risk of invented text; breaks word timestamps).

### Gaps
- No Hebrew-specific hallucination list or measured benefits; none for WhisperX/stable-ts Hebrew support; initial_prompt vs hotwords effect on ivrit models untested.

## Recommended plan (ranked, based on above; unverified items need benchmark)
1. ivrit-ai whisper-large-v3-turbo-ct2 + faster-whisper + Silero VAD on a GitHub Actions matrix (time shards, overlap) — free, unattended, best accuracy; benchmark RTF first.
2. Same model on Kaggle GPU (30 h/week) if CPU RTF > ~1 — needs phone verification and API orchestration; verify ToS.
3. Groq turbo as cheap topic-discovery pass only (28.8K s/day cap if applicable).
4. ZeroGPU / commercial credits: not viable for volume.

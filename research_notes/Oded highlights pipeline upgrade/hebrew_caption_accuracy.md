# Accurate, well-timed Hebrew word-by-word captions from noisy live-stream audio (free tools only)

Research date: 2026-11-13. Environment limits: only github.com / raw.githubusercontent.com and the web-search tool were reachable. huggingface.co, arxiv.org, console.groq.com, groq.com and docs.aws.amazon.com did NOT resolve from the fetch tool, so every Hugging Face / arXiv / Groq / AWS statement below comes from search-result summaries (secondary) and is flagged "[secondary]". GitHub sources were read directly ("[primary]"). Labels: **Evidence** = cited; **Proposal** = my design suggestion, untested on this pipeline; **Unverified** = needs a check on real audio.

Important framing: no source I found measures Hebrew *livestream* audio. All numbers (9% vs 15% WER, etc.) are clean-ish benchmark numbers; the user's own figures are carried as given in the assignment, not verified by me.

---

## 1. Audio preparation (rendition choice, filtering, denoise, voice isolation, speaker separation, VAD)

### Takeaway
Use the highest-bitrate audio you can get (Kick's HLS appears to be AWS IVS-based, where the 160p rendition's audio is plausibly ~48 kbps AAC versus 128 kbps for 480p-720p, and there may be an audio-only rendition) and do NOT pre-denoise by default: the available studies show speech enhancement before Whisper usually raises WER. Spend effort instead on a Silero VAD with a lower threshold / shorter min-silence and on a per-segment re-decode of weak segments.

### Cited Findings
- Kick's live playback URL comes from `api/v2/channels/{channel}/livestream` -> `playback_url` (an .m3u8), parsed by Streamlink as an HLS variant playlist; Streamlink's Kick plugin itself defines no quality names and no audio-only handling, so rendition names come from Kick's master playlist. [primary] — [streamlink kick.py](https://raw.githubusercontent.com/streamlink/streamlink/master/src/streamlink/plugins/kick.py)
- A Streamlink discussion lists `audio_only` and `160p` as quality keys (the example is Twitch-like) and a Kick user reports an "Audio only" entry in Kick's player quality menu. [secondary] — search result for [streamlink discussion #5580](https://github-redirect.dependabot.com/streamlink/streamlink/discussions/5580) and [Kick Audio Only Mode extension](https://chromewebstore.google.com/detail/kick-audio-only-mode/lgamhckbhabhnlmecnklmkheaffhogkg)
- Kick's CDN is reported as AWS IVS (live-video.net) by one Chrome-extension listing and as "live-edge-cdn.kick.com" HLS by one blog; neither is authoritative (conflicting). [secondary] — [Kick Audio Only Mode](https://chromewebstore.google.com/detail/kick-audio-only-mode/lgamhckbhabhnlmecnklmkheaffhogkg); [vd-ofa blog](https://vd-ofa-website.vercel.app/blog/how-to-record-kick-streams)
- Amazon IVS docs (via search summary): audio is transcoded for renditions of 360p and below on lower channel types; the Advanced HD ladder pairs 720p60 with 128 kbps audio, 480p30 with 128 kbps, 360p30 with 64 kbps, 160p30 with 48 kbps, plus an audio-only rendition at 64 kbps; codec AAC-LC. Stereo vs mono per rendition not stated. [secondary] — [AWS IVS channel types](https://docs.aws.amazon.com/ivs/latest/LowLatencyUserGuide/channel-types.html)
- Kick's own help centre reportedly publishes no audio bitrate (stereo, up to 48 kHz); third-party guides give 128-256 kbps ingest advice. [secondary, low quality] — [voxbooster 2026 table](https://voxbooster.com/blog/livestream-audio-bitrate-encoding-settings-statistics-2026/); [pMix Kick preset](https://docs-pmix-studio.pages.dev/docs/streaming-and-recording/streaming-to-kick)
- Denoising study on medical ASR: MetricGAN+ enhancement made things worse in all 40 model/noise configurations; Whisper at 10 dB SNR went from ~8.8% to ~25.8% error after enhancement. [secondary] — [arXiv 2512.17562](https://arxiv.org/abs/2512.17562?context=cs)
- SAM-Audio source separation before zero-shot Whisper (Bengali/English) improved signal metrics but raised WER/CER systematically, more so for larger Whisper models. [secondary] — [arXiv 2603.04710](https://arxiv.org/html/2603.04710v1)
- One paper (DenoASR) applied Demucs-type denoising only to samples below an intelligibility threshold and reported reduced disparity without hurting overall performance; not Whisper-based. [secondary, weakly attributed] — [arxiv.deeppaper.ai listing](https://arxiv.deeppaper.ai/papers/2512.17562v1/similar?locale=en)
- faster-whisper VadOptions defaults (Silero VAD v6): threshold 0.5, min_speech_duration_ms 0, min_silence_duration_ms 2000, speech_pad_ms 400, max_speech_duration_s inf, `neg_threshold` None; `vad_filter` default False. The BatchedInferencePipeline defaults vad_filter=True with min_silence_duration_ms=160. [primary] — [faster-whisper vad.py](https://raw.githubusercontent.com/SYSTRAN/faster-whisper/master/faster_whisper/vad.py); [transcribe.py](https://raw.githubusercontent.com/SYSTRAN/faster-whisper/master/faster_whisper/transcribe.py)
- stable-ts uses Silero VAD with `vad_threshold` default 0.35 when `vad=True` (otherwise loudness-based non-speech detection). Note: stable-ts README says development is "indefinitely paused". [primary] — [stable-ts README](https://raw.githubusercontent.com/jianfch/stable-ts/main/README.md)
- WhisperX README: overlapping speech is not handled well by Whisper/WhisperX; diarization "far from perfect"; VAD preprocessing is used to cut hallucination and allow batching. [primary] — [WhisperX README](https://raw.githubusercontent.com/m-bain/whisperX/main/README.md)

### Inferences
- If Kick runs on IVS defaults, the 160p rendition's 48 kbps AAC is the weakest audio available (my inference from the IVS ladder; Kick may use a custom ladder). Taking the 480p/720p variant (or the audio-only rendition) costs more video bandwidth than the audio-only/low variants but gives ~128 kbps audio. Cheapest robust route: pull the `audio_only` variant if present, otherwise the 360p/480p variant, and extract audio only (ffmpeg `-vn`); do the real check by running `ffprobe` on each variant (see Proposal).
- Because both denoising papers show harm to modern Whisper and no Hebrew-specific evidence exists, voice isolation (Demucs/RNNoise) is not justified as a default on a 4 vCPU box; at best a selective fallback.
- Phone-call segments are most likely lost to VAD (narrowband, quiet, often ducked under game audio) rather than to ASR: lowering VAD threshold is the cheapest fix.

### Proposal (untested)
- Measure first: `ffprobe -v error -select_streams a -show_entries stream=codec_name,channels,sample_rate,bit_rate` on every variant in the master playlist; record in notes which variant carries what audio. Pick the best audio; decode to 16 kHz mono PCM/FLAC (what Whisper uses internally anyway).
- Light preprocessing only: high-pass ~80 Hz, loudness normalisation (EBU R128 `loudnorm` or `dynaudnorm`) so quiet remote speakers are not under the VAD threshold; no spectral denoise. A/B on the gold set (Section 8) before adopting anything else.
- VAD: threshold 0.30-0.35 (or `neg_threshold` ~0.15), `min_silence_duration_ms` ~300-500 (not 2000), `speech_pad_ms` 200-400, `min_speech_duration_ms` ~100-150, `max_speech_duration_s` ~25-30. Tune by counting dropped words on the gold set. Also run a second pass: any region with VAD=speech but empty transcript, or RMS above a floor with no words, gets re-transcribed with VAD off, `no_speech_threshold` raised and a high-pass+gain stage.
- Phone calls: do not diarize/separate (WhisperX says overlap and diarization are weak; pyannote diarization needs a gated HF token). Instead, detect narrowband segments (spectral rolloff < ~3.4 kHz) and apply a +gain/normalise-only re-decode for those.
- Voice isolation only as a gated retry: run Demucs (`htdemucs --two-stems=vocals`) only on segments that came back empty/low-confidence after pass 2, compare the confidence, keep whichever scores higher. Cost: Demucs on CPU is slow (not measured here; Unverified) so cap it to a few minutes per hour of stream.

### Gaps
- Actual Kick lowest-rendition audio bitrate/channels: no authoritative source reachable; needs an `ffprobe` of a live master playlist.
- Whether Kick uses IVS transcode defaults (conflicting secondary evidence).
- No evidence found on Demucs/RNNoise before Whisper for Hebrew or for game-audio-heavy streams; no CPU timing for Demucs on 4 vCPU.
- Groq's accepted input formats / recommended preprocessing (16 kHz mono) could not be fetched (console.groq.com unreachable).

---

## 2. Decoding (prompts/hotwords, temperature, beam, conditioning, hallucination filters, chunk overlap)

### Takeaway
On the local faster-whisper path use `hotwords`/`initial_prompt` with a short glossary, `condition_on_previous_text=False`, `hallucination_silence_threshold` with word timestamps, and a post-filter for repeated stock phrases; on Groq only `prompt` is available. There is no Hebrew-specific published evidence that prompts help or hurt, so gate prompt use by A/B on the gold set.

### Cited Findings
- faster-whisper `transcribe()` defaults: beam_size 5; temperature [0.0,0.2,0.4,0.6,0.8,1.0]; compression_ratio_threshold 2.4; log_prob_threshold -1.0; no_speech_threshold 0.6; condition_on_previous_text True; prompt_reset_on_temperature 0.5; initial_prompt None; hotwords None (ignored if `prefix` set); hallucination_silence_threshold None (needs word_timestamps); word_timestamps False; `clip_timestamps` disables vad_filter. [primary] — [transcribe.py](https://raw.githubusercontent.com/SYSTRAN/faster-whisper/master/faster_whisper/transcribe.py)
- faster-whisper docstring: disabling condition_on_previous_text "reduces failure loops but can make text less consistent". The BatchedInferencePipeline forces condition_on_previous_text=False, hallucination_silence_threshold=None and max_initial_timestamp=0.0 regardless of arguments (so the batched mode cannot use the silence-hallucination guard). [primary] — [transcribe.py](https://raw.githubusercontent.com/SYSTRAN/faster-whisper/master/faster_whisper/transcribe.py)
- Whisper silence hallucinations: silence/long pauses/background noise trigger stock text; mitigations are VAD, disabling previous-text conditioning when hallucinations become repetition loops, tuning no_speech_threshold, and regex cleanup of repeated phrases. Single blogs / vendor pages. [secondary, low quality] — [popularai](https://www.popularai.org/p/whisper-hallucinations-during-silence); [yage.ai](https://yage.ai/share/whisper-repetition-hallucination-en-20260526.html); [GDELT experiments](https://blog.gdeltproject.org/experiments-with-whisper-asr-model-parameters-non-determinism-temperature_increment_on_fallback) (GDELT found temperature fallback can itself make output less reliable)
- I found no source mentioning the specific Hebrew hallucination "תודה רבה" with Whisper (search returned none), and none on whether `initial_prompt` helps or hurts Hebrew with ivrit-ai models. [secondary: search came back empty] 
- ivrit.ai's own runtime wrappers (runpod-serverless) always pass `language="he"`, support word timestamps on/off, and support `stable-whisper` as core engine for diarization; no VAD/prompt/beam guidance is given. ivrit.ai's asr-training README gives no inference recommendations either. [primary] — [runpod-serverless README](https://raw.githubusercontent.com/ivrit-ai/runpod-serverless/main/README.md); [asr-training](https://github.com/ivrit-ai/asr-training)
- Groq: word granularity is supported via `response_format=verbose_json` + `timestamp_granularities`, but a second Groq page lists `timestamp_granularities[]` as unsupported (conflicting/outdated). [secondary] — [Groq speech-to-text docs](https://console.groq.com/docs/speech-to-text)

### Inferences
- Observed 'תודה רבה' loops are consistent with the generic silence-hallucination pattern; the right defence is detect-and-drop (below), not trying to make the decoder never emit it.
- Temperature fallback mostly rescues loops/garbage but can inject invented words (GDELT); keep fallback but prefer keeping the T=0 result if it passes the thresholds, and treat fallback-decoded segments as lower trust.
- Chunk overlap: no source gives a Hebrew-specific figure. Standard practice is VAD-driven segmentation (speech chunks <= 30 s) rather than fixed windows.

### Proposal (untested)
- Local (ivrit-ai CT2): `language="he"`, `beam_size=5`, `condition_on_previous_text=False`, `word_timestamps=True`, `hallucination_silence_threshold=1.0-2.0`, `no_speech_threshold` ~0.5-0.6, `log_prob_threshold=-1.0`, `compression_ratio_threshold=2.0-2.4`, `hotwords="<glossary>"` (short, 10-30 tokens) rather than long `initial_prompt`. Use the non-batched pipeline if the guard matters.
- Groq: send `prompt` with a short natural Hebrew sentence containing the streamer names and 5-10 recurring slang words (Whisper prompts work as style/vocabulary priming; length cap is believed ~224 tokens - Unverified, Groq docs not reachable). Set `temperature=0`; use `language="he"`.
- Hebrew hallucination filter (post-ASR): maintain a blocklist of stock phrases (תודה רבה, תודה שצפיתם, תרגום כתוביות ..., "סוף", "היי" alone, etc. - collect from your own logs), and drop a segment when (a) text is in the list AND (no_speech_prob > ~0.3 OR avg_logprob < -0.8 OR audio RMS under floor), or (b) the same n-gram repeats >= 3 times, or (c) compression ratio > 2.4, or (d) the segment duration is much longer than speech duration under VAD. Never drop on the phrase alone (real speakers do say thanks).
- Glossary matters mostly for names: ניגי vs ביגי is a one-letter phonetic confusion that no prompt reliably fixes; handle with the glossary-substitution stage (Section 4) plus the low-confidence policy (Section 6).
- Long audio: VAD-segment into <= 30 s chunks with ~1-2 s padding; join without overlap-stitching (VAD splits at silence); only if you must use fixed windows, use 2-3 s overlap and de-duplicate by timestamp on the word level (Proposal).

### Gaps
- No Hebrew-specific evidence on initial_prompt/hotwords benefit; must be A/B tested.
- Exact Groq prompt token limit and whether Groq honours temperature fallback / compression-ratio thresholds (server-side, not exposed) not verified.
- Groq word-timestamp implementation details unavailable.

---

## 3. Word timing (forced alignment options, cost on 4 vCPU, fallbacks, acceptable error)

### Takeaway
WhisperX ships a default Hebrew aligner (`imvladikon/wav2vec2-xls-r-300m-hebrew`), so the cheapest upgrade over Groq's coarse word times is: keep the Whisper text, re-align the segment text against audio with that CTC model (or an MMS CTC aligner), and fall back to proportional-by-character timing when alignment fails. ivrit.ai maintains a public Hebrew forced-alignment evaluation suite, which signals that MMS and MFA-style (viter, Hebrew graphemes) aligners are the credible options, but I could not find its numbers.

### Cited Findings
- WhisperX `DEFAULT_ALIGN_MODELS_HF` maps `he` to `imvladikon/wav2vec2-xls-r-300m-hebrew` (other mapped languages use jonatasgrosman XLSR-53 models etc.). [primary] — [whisperx alignment.py](https://raw.githubusercontent.com/m-bain/whisperX/main/whisperx/alignment.py)
- WhisperX alignment behaviour: characters not in the model vocabulary are kept as wildcards (aligned against the max non-blank emission); words with no alignable chars get NaN times, filled with `interpolate_nans` (default "nearest") if at least one word in the sentence has times; segments that cannot be aligned (no dictionary characters, start beyond audio, failed backtrack) keep the ORIGINAL segment timestamps and get no word timings, with a warning. [primary] — [whisperx alignment.py](https://raw.githubusercontent.com/m-bain/whisperX/main/whisperx/alignment.py)
- WhisperX README: numbers/symbols (e.g. "2014.", "£13.60") can't be aligned and get no timing; alignment needs a language-specific wav2vec2 model; "bigger alignment models weren't found to be especially helpful". WhisperX also uses pyannote VAD by default; README does not state its licence in the fetched text (linked LICENSE file; not read). [primary] — [WhisperX README](https://raw.githubusercontent.com/m-bain/whisperX/main/README.md)
- ctc-forced-aligner (MahmoudAshraf97): default model `MahmoudAshraf/mms-300m-1130-forced-aligner` covers 1130+ languages (README names English/Arabic/Russian/German; does not mention Hebrew by name); `--romanize` required with the default model; "at least 5x less memory" than torchaudio's aligner; code BSD-2-Clause but the default model is CC-BY-NC 4.0 (non-commercial). A custom CTC model can be passed via `--alignment_model`. [primary] — [ctc-forced-aligner](https://github.com/MahmoudAshraf97/ctc-forced-aligner)
- ivrit-ai/eval-forced-alignment ("Hebrew Forced Alignment Evaluation Suite") scores aligners against human-corrected word boundaries and lists: wav2vec2-hebrew and MMS (ctc.py), whisper-stable-ts (CPU only, "slow"), MWA (Buckeye/TIMIT models), clap-ipa, MFA via `viter` (incl. pretrained `hebrew_graphemes` model), and `mms-corrected` (MMS output shifted per letter class). Its README says viter's off-domain Hebrew graphemes model "lands close to" MMS on the gold set. No millisecond numbers or results table are in the README (a referenced table is missing). WhisperX and ctc-forced-aligner are not in the suite. [primary] — [eval-forced-alignment](https://github.com/ivrit-ai/eval-forced-alignment)
- viter: "Montreal Forced Aligner recipe, on your GPU", single binary, MIT; can import MFA models; the fetched README does not mention Hebrew or CPU speed. [primary] — [viter](https://github.com/thewh1teagle/viter)
- stable-ts: word times from cross-attention + DTW; `align()` aligns known text and is "much faster than transcribing"; `refine()` re-times words by muting audio (slow, esp. on faster-whisper); `suppress_silence` post-adjusts; `regroup`. Whether `align()` handles Hebrew script well is not stated. Development "indefinitely paused". [primary] — [stable-ts README](https://raw.githubusercontent.com/jianfch/stable-ts/main/README.md)
- Hebrew CTC checkpoints: `imvladikon/wav2vec2-large-xlsr-53-hebrew` and `imvladikon/wav2vec2-xls-r-300m-hebrew` exist; `dekelabe/chords-align-en-ft3` is an int8 ONNX export of the former used for aligning sung Hebrew lyrics. Licences not checked. [secondary] — search summary of [imvladikon model](https://huggingface.co/imvladikon/wav2vec2-large-xlsr-53-hebrew), [dekelabe](https://huggingface.co/dekelabe/chords-align-en-ft3)
- Related 2026 work: a forced-alignment metrics paper compares MMS/MFA/IPA variants on FLEURS including Hebrew (numbers garbled in extraction), and a learned-DP aligner on MMS features reports Hebrew as an unseen-language success. [secondary, numbers not verified] — [arXiv 2608.28508](https://arxiv.org/pdf/2608.28508); [arXiv 2606.10675](https://arxiv.deeppaper.ai/papers/2606.10675v1)
- An English comparison (TIMIT, Buckeye) found MFA beats WhisperX and MMS. Not Hebrew. [secondary] — [search listing](https://arxiv.org/html/2406.19363v1)
- Hebrew in MMS: ~25 h of Hebrew in MMS's pretraining (via Hebrew TTS papers). [secondary] — [arXiv 2410.21502](https://arxiv.org/pdf/2410.21502)

### Inferences
- The shortest path is WhisperX's `align()` with the built-in Hebrew model on the Whisper text (wav2vec2 300M on CPU is a one-pass CTC forward, a fraction of real time; exact speed not measured - Unverified). It bypasses Groq's coarse word times entirely, and you can call it segment by segment.
- Hebrew is written without most vowels and includes final-form letters (ך ם ן ף ץ); CTC models trained on Hebrew graphemes should include these, but check the vocab.json of the model against your text normaliser (strip niqqud/punctuation, expand digits to words) - otherwise WhisperX's wildcard mechanism hides real misalignment. (My inference; model vocab not read.)
- Alignment quality decays with ASR text errors: forced alignment forces the given (possibly wrong) words onto audio. Look at the aligner's per-word CTC scores as a second confidence signal (Section 5/6).
- Practical acceptability for word-by-word burned-in captions: not found in any source (Unverified). Proposal: treat <=100-150 ms mean start error and nothing worse than ~250 ms as fine when 1-3 words are shown at a time; captions appearing late is more noticeable than early, so bias start times ~40-80 ms earlier and keep each caption visible until the next one starts.

### Proposal (untested)
1. Pass 1: Whisper transcription (Groq or local) -> text only (segments).
2. Normalise text -> CTC-align per VAD segment with WhisperX `he` model (`return_char_alignments=False`). Run on CPU in segments of <= 30 s; a 4 vCPU box should handle this near-real-time or faster (Unverified; benchmark on 10 minutes).
3. Quality gate per segment: share of NaN words, mean CTC score, and duration monotonicity. If failing, try `ctc-forced-aligner` with the MMS aligner (note: model is CC-BY-NC) as secondary; if it too fails, fall back to proportional timing: distribute the segment's [start,end] by character count (with minimum 120 ms/word, punctuation pauses), snapped to VAD speech onset/offset.
4. Post-process: enforce monotonic, minimum word duration ~80-120 ms, fill small gaps, clamp to VAD speech regions (stable-ts-style `suppress_silence` idea).
5. Evaluate timing on 20-30 hand-marked words (Section 8). If MMS or Hebrew-graphemes-MFA beats the imvladikon model, swap (ivrit.ai's own suite is the template to follow).

### Gaps
- No numbers for aligner accuracy on Hebrew: the ivrit-ai suite README has no table; the 2026 FLEURS paper's Hebrew row was unreadable.
- No measured CPU cost for any aligner; no direct evidence about aligner behaviour on noisy, shouted Hebrew.
- Licence of the imvladikon wav2vec2 Hebrew models not verified; WhisperX licence not read in the fetched text.
- No published threshold for acceptable word-timing error in burned-in captions found.

---

## 4. LLM correction of Hebrew ASR text with constrained edits

### Takeaway
Published evidence is mixed and none of it is Hebrew: unconstrained LLM post-correction often raises WER or inserts hallucinations, and gains come when the LLM is gated by confidence, given N-best/context, or restricted. For your use case the safest design is a substitution-only, glossary-driven corrector gated by Whisper confidence and verified by a CTC/ASR audio score; expect modest gains concentrated on names and recurring slang.

### Cited Findings
- Whisper + GPT study: correcting every ASR output risks damaging already-correct text; confidence-score filtering decides which transcripts go to the LLM. [secondary] — [arXiv 2407.21414](https://arxiv.org/html/2407.21414v1)
- Another paper: directly applying LLM in-context learning to improve ASR transcripts "often leads to a higher WER". [secondary] — [arXiv 2409.09554 / related, via search summary](https://arxiv.org/pdf/2409.09554)
- Three-stage framework to cut LLM hallucination in ASR correction (verification stage added). [secondary] — [arXiv 2505.24347](https://arxiv.org/pdf/2505.24347)
- LLMs hallucinate especially on rare/unknown named entities; a retrieval-augmented (TF-IDF over error-aware context) approach for low-resource Persian is proposed. [secondary] — [arXiv 2606.24915](https://arxiv.org/pdf/2606.24915)
- Persian noisy speech: fine-tuned Whisper-large with 5-best hypotheses + LLM cut WER from 31.10% (raw Whisper) to 24.84% on a mixed-noise test set. [secondary] — [Naderi, Interspeech 2024](https://publications.idiap.ch/attachments/papers/2024/Naderi_INTERSPEECH_2024.pdf)
- Low-resource West Frisian study questions how much reported LLM-GER gains come from data contamination; builds a non-public-text test. [secondary] — [arXiv 2605.19711](https://arxiv.org/abs/2605.19711)
- Oral-cancer speech: LLM correction improved WER, but results were stochastic so no definitive best approach; a sports-commentary Whisper study found LLM post-correction had "minimal impact". [secondary] — [arXiv 2605.15854](https://arxiv.org/pdf/2605.15854); [arXiv 2602.18966](https://arxiv.org/pdf/2602.18966)
- Hindi (EACL 2026): fine-tuned mT5/ByT5 vs instruction-tuned LLMs compared for post-ASR correction. [secondary, outcome not read] — [ACL Anthology](https://aclanthology.org/2026.eacl-short.45/)
- Hebrew-specific LLM ASR-correction evidence: none found (two searches).

### Inferences
- Hebrew's rich morphology and unpointed script make "plausible but wrong" substitutions easy for an LLM (similar surface forms, many valid readings), and general LLMs are weaker on Hebrew slang/transliterated names; with no Hebrew evidence, assume correction is net-neutral to slightly harmful unless constrained.
- Names like ניגי/ביגי are exactly the case where a glossary + phonetic-similarity match beats a free LLM.

### Proposal (untested)
- Stage A (deterministic, no LLM): glossary of streamer names/slang with variants. For each ASR word with low confidence, compute Hebrew-letter edit distance on a phonetically folded key (merge confusable pairs: ב/כ/פ-ish plosive/fricative alternations, ת/ט, כ/ק, ס/שׂ, א/ע, ו/ב in some mis-hearings, strip matres lectionis ו/י; handle prefixes ה/ו/ב/כ/ל/מ/ש). Replace only if distance <= 1 on folded key AND the word's confidence is below threshold AND the candidate is in the glossary.
- Stage B (optional LLM, free tier e.g. a free-API model): input = the 1-N-best words with indices and confidences, the glossary and 1-2 lines of context; output = JSON `{index: replacement}` for at most K indices; enforce programmatically: same word count, only listed indices changed, replacement must be (a) glossary entry or (b) within edit distance <= 2 of the original on the folded key; reject whole response otherwise. Timing is untouched because words are substituted in place.
- Stage C (audio verification): for each proposed substitution, re-score with the CTC aligner (wav2vec2) over the word's time span: accept only if CTC log-likelihood (per frame) of the new word >= the old word's - margin; or, with a local Whisper, force-decode both candidates (score via `generate` with forced tokens / `ctranslate2` scoring - Proposal, implementation not checked) and keep the higher-likelihood one.
- Gate by confidence: only attempt correction on words/segments with avg_logprob < ~-0.6 or per-word probability < ~0.5; never touch high-confidence words.
- Never let the LLM add/remove/reorder words, never fix punctuation-only; log all edits for review.

### Gaps
- No Hebrew LLM-correction results; no evidence on which free LLMs handle Hebrew slang well.
- Glossary-based phonetic matching for Hebrew is my design; no citation. Per-word probabilities are not available from Groq (only segment-level avg_logprob etc. - believed, Unverified).

---

## 5. Two ASR systems, ROVER-style voting, per-segment selection

### Takeaway
ROVER over several diverse ASR systems reliably helps in the literature (up to ~37% relative WER in one 2025 preprint, at ~3x compute), but with only two systems ROVER cannot vote, so use per-segment (or per-word) selection by confidence plus agreement as the tie-breaker; a third cheap system makes true majority voting possible.

### Cited Findings
- Three-model ensemble (Whisper-large-v3 + Canary + Parakeet) with ROVER: WER 6.26% -> 3.92% (~37% relative), roughly 3x inference time (English, 2025 preprint). [secondary] — [search result ref](https://arxiv.org/pdf/2603.16411)
- ROVER over N-best combined from Transducer + Whisper reached 4.72% WER, 32%/36% lower than the individual baselines. [secondary] — [arXiv 2409.09554](https://arxiv.org/pdf/2409.09554)
- CHiME-8 NTT: ROVER over six systems beat each system (except on deletions). [secondary] — [arXiv 2502.09859](https://arxiv.org/pdf/2502.09859)
- Hybrid Kaldi + XLS-R: ROVER ensembling gave a notable WER reduction though the two systems individually did not differ significantly. [secondary] — [LREC 2024](https://aclanthology.org/2024.lrec-main.547)
- faster-whisper/Whisper gives per-segment signals: avg_logprob (fail below -1.0), compression_ratio (fail above 2.4), no_speech_prob (silence if above 0.6 and logprob below threshold). [primary] — [transcribe.py](https://raw.githubusercontent.com/SYSTRAN/faster-whisper/master/faster_whisper/transcribe.py)
- ivrit.ai provides both large-v3 and large-v3-turbo CT2 Hebrew models (turbo model is Apache-2.0 per card metadata [secondary]), enabling two *different* Hebrew-tuned systems besides stock Groq Whisper. [secondary] — [ivrit-ai/whisper-large-v3-turbo-ct2](https://huggingface.co/ivrit-ai/whisper-large-v3-turbo-ct2); [ivrit-ai/whisper-large-v3-ct2](https://huggingface.co/ivrit-ai/whisper-large-v3-ct2)

### Inferences
- Diversity matters: stock Whisper (Groq) and ivrit-ai fine-tune share an architecture and a base model, so their errors are correlated; the ROVER literature uses architecturally different systems. A genuinely different third system for Hebrew (the wav2vec2-CTC Hebrew model, whose greedy transcript is cheap and whose per-character posteriors are native) gives a different error profile.
- With two systems, word-level agreement is itself the confidence signal: aligned words that agree are very likely right; disagreements go to the gate in Section 6.

### Proposal (untested)
- Run Groq turbo (stock) and ivrit-ai turbo CT2 on the same VAD segments; align texts at word level (Hebrew-aware tokenisation, normalise punctuation); compute agreement per word.
- Per segment: if one hypothesis fails hard gates (compression_ratio > 2.4, no_speech_prob high, repetition, empty while VAD speech), take the other; else prefer ivrit-ai text (lower WER on Hebrew per the assignment's benchmark) unless its avg_logprob is far below the other's. Per word at disagreement: use the CTC-aligner score of each candidate on the audio span (Section 4 Stage C) to choose; if scores are within a margin, mark word "uncertain".
- Keep compute in budget: the ivrit-ai CT2 on 4 vCPU CPU is the bottleneck (speed not measured here); run it in near-real-time only on segments flagged uncertain (disagreement, low logprob, or empty) rather than all audio.

### Gaps
- No Hebrew ROVER evidence; the ensemble figures are English and not from the sources fetched directly.
- Groq returns segment-level avg_logprob/no_speech_prob/compression_ratio in verbose_json (believed; not re-verified), not per-word probabilities.

---

## 6. Policy for low-confidence segments (omit vs show; names and slurs)

### Takeaway
No source addresses caption display policy; this is a product decision. Recommended: tiered display (show / show only high-confidence words / omit), with a hard rule that low-confidence proper nouns, profanity and slurs are never burned in unverified.

### Cited Findings
- Whisper's own failure criteria are avg_logprob < -1.0, compression ratio > 2.4, and no_speech_prob > 0.6 combined with low logprob. [primary] — [transcribe.py](https://raw.githubusercontent.com/SYSTRAN/faster-whisper/master/faster_whisper/transcribe.py)
- WhisperX leaves unalignable segments with original (coarse) timings and no word times - a natural "low-trust timing" flag. [primary] — [alignment.py](https://raw.githubusercontent.com/m-bain/whisperX/main/whisperx/alignment.py)
- Confidence-gated LLM use is the approach recommended by the Whisper+GPT study to avoid corrupting good transcripts. [secondary] — [arXiv 2407.21414](https://arxiv.org/html/2407.21414v1)
- I found no sources on display policies for uncertain captions, or on Hebrew slur lists. 

### Inferences
- A wrong word is worse than a missing word for burned-in 1-3 word captions; a short silent gap is generally less damaging than a visible error (editorial judgment, not evidence).
- Entire-phrase omission looks like a bug when the streamer is visibly talking; better to omit only the uncertain words, and show a neutral placeholder or nothing for 1-2 words, and omit whole captions only for hallucination-flagged segments.

### Proposal (untested)
Tiers computed per word from: segment avg_logprob, cross-system agreement, CTC score, alignment success, and hallucination flags.
- Tier A (show): both systems agree OR single system with avg_logprob > -0.5 and CTC score good.
- Tier B (show with care): disagreement resolved by CTC margin; show only if the chosen word is in a Hebrew dictionary / frequent-word list (build from ivrit.ai transcripts) or in the glossary; otherwise drop the word and keep timing for its neighbours.
- Tier C (omit): hallucination-flagged (stock phrase + low evidence, repetition, compression > 2.4), no_speech high, alignment failed AND logprob low, or fewer than ~50% words surviving.
- Hard rules: (1) never display a word that is a proper-noun candidate (not in glossary, capitalised-in-transliteration, or edit-distance-close to a glossary name) unless agreement + high confidence; if close to a glossary name and the CTC margin favours it, substitute the glossary name. (2) Slur/profanity list (curate yourself; keep it local): if the word is on the list and confidence is not high (both systems agree and CTC good), omit/mask; if you intend to display profanity, require high confidence and consider a manual review queue for clips before publishing. (3) Keep a per-clip report listing omitted/uncertain words so the editor can fix before export.
- Make thresholds config values, tuned on the gold set to hit a target such as "<2% visibly wrong words shown" at the cost of N% omitted.

### Gaps
- No empirical thresholds; must be tuned on own gold set.
- No curated Hebrew slur/profanity list found in the sources reached.

---

## 7. Hebrew-specific tools, datasets and licences

### Takeaway
The ivrit.ai ecosystem (models, CT2 conversions, eval suites, forced-alignment eval, MIT-licensed code) is the main free Hebrew resource; check each dataset/model licence before reuse, and note that the popular MMS aligner model is non-commercial.

### Cited Findings
- ivrit.ai models: `ivrit-ai/whisper-large-v3`, `whisper-large-v3-ct2`, `whisper-large-v3-turbo-ct2`; the turbo CT2 card lists Apache-2.0, base openai/whisper-large-v3-turbo, trained on `ivrit-ai/crowd-transcribe-v5` (a mirror says ~295 h volunteer-transcribed + ~93 h professionally transcribed - third-party mirror, verify on the original card). [secondary] — [ivrit-ai/whisper-large-v3-turbo-ct2](https://huggingface.co/ivrit-ai/whisper-large-v3-turbo-ct2); [LifeAi-dev mirror](https://huggingface.co/LifeAi-dev/whisper-large-v3-turbo-ct2)
- ivrit.ai leaderboard (HF Space `ivrit-ai/hebrew-transcription-leaderboard`) evaluates on ivrit-ai/eval-d1, eval-whatsapp, SASpeech, FLEURS he_il, and Hebrew KAN validation; turbo results are listed but I could not retrieve the scores (so the 9% vs 15% figures are as supplied in the assignment, not verified). Model cards defer to the leaderboard rather than reporting scores. [secondary] — [leaderboard Space](https://ivrit-ai-hebrew-transcription-leaderboard.hf.space/); [ivrit-ai/whisper-large-v3](https://huggingface.co/ivrit-ai/whisper-large-v3)
- ivrit.ai code is MIT (repos: ivrit.ai, asr-training, ivrit-py, runpod-serverless, eval-forced-alignment [licence not stated], faster-whisper fork [MIT], transcribe-service, live-transcribe, eliezer). The dataset paper: Marmor, Misgav, Lifshitz 2023, "ivrit.ai: A Comprehensive Dataset of Hebrew Speech for AI Research and Development", arXiv 2307.08720; dataset licences are not stated in the repo README. [primary] — [ivrit-ai GitHub org](https://github.com/ivrit-ai); [ivrit.ai repo](https://github.com/ivrit-ai/ivrit.ai); [asr-training](https://github.com/ivrit-ai/asr-training)
- ivrit.ai's own dataset-alignment pipeline uses `ivrit-ai/whisper-large-v3-turbo-ct2` as the alignment ("normalization") model. [primary] — [ivrit.ai repo](https://github.com/ivrit-ai/ivrit.ai)
- Eval datasets: eval-d1 (manually transcribed gold), SASpeech, FLEURS he_il, hebrew_speech_kan validation (not gated); Common Voice 17 he (gated). [primary] — [asr-training README](https://github.com/ivrit-ai/asr-training)
- Hebrew CTC models: imvladikon wav2vec2 xls-r-300m-hebrew (WhisperX default) and xlsr-53-hebrew; licences not retrieved. [primary for WhisperX mapping; secondary for model page] — [alignment.py](https://raw.githubusercontent.com/m-bain/whisperX/main/whisperx/alignment.py)
- Licences of aligner tooling: ctc-forced-aligner code BSD-2 but `mms-300m-1130-forced-aligner` CC-BY-NC 4.0; viter MIT; ivrit.ai runpod/asr-training MIT. WhisperX licence not confirmed here (linked LICENSE not read). [primary] — [ctc-forced-aligner](https://github.com/MahmoudAshraf97/ctc-forced-aligner); [viter](https://github.com/thewh1teagle/viter)
- Other community Hebrew Whisper fine-tunes exist (e.g. "Whisper-Hebrish" turbo fine-tune for mixed English-Hebrew speech: 6.07% WER on its author's own set, not comparable; "Ozen-v1", "BuzzASR/hebrew", `israelisraeli/ivrit-faster-whisper-turbo-d4`). [secondary] — [Whisper-Hebrish](https://huggingface.co/danielrosehill/Whisper-Hebrish); [search result list](https://huggingface.co/ivrit-ai)
- ivrit.ai live-transcribe (browser, on-device Hebrew) exists as a reference for a lighter streaming approach. [primary] — [ivrit-ai GitHub org](https://github.com/ivrit-ai)

### Inferences
- Because the pipeline publishes clips (possibly monetised), the MMS aligner's CC-BY-NC licence is a real risk; prefer imvladikon wav2vec2 (check licence) or viter + Hebrew graphemes (MIT tooling, model licence unknown).
- The community "Whisper-Hebrish" and similar fine-tunes may better handle English words in Hebrew speech (gaming terms) but are unverified on your audio.

### Gaps
- Actual leaderboard numbers for turbo (stock vs ivrit-ai); dataset licences (crowd-transcribe, Knesset, podcast data); imvladikon model licence; whether HebrewSpeech/KAN corpora are redistributable; none could be fetched.

---

## 8. Evaluation: tiny gold set, metrics, and an end-to-end plan

### Takeaway
A 2-3 minute hand-corrected gold set built from the hardest passages (phone call, shouting, overlapping, names) is enough to compare variants if you report CER and name-recall alongside WER and use paired comparisons; timing needs ~30 hand-marked words.

### Cited Findings
- The ivrit.ai alignment-eval suite uses clip-level bootstrap intervals and Holm-corrected paired tests, plus a human-agreement floor from doubly-annotated clips; its design is a usable template for small-sample statistical comparison. [primary] — [eval-forced-alignment](https://github.com/ivrit-ai/eval-forced-alignment)
- A 2024 West-Frisian study flags that LLM-correction gains can be inflated by data contamination, so use text the LLM could not have seen (your own stream transcripts). [secondary] — [arXiv 2605.19711](https://arxiv.org/abs/2605.19711)
- ivrit.ai's `eval-d1` is a manually transcribed "golden standard" episode and `run_bench.py` in asr-training supports plug-in engines (faster-whisper CT2, HF Transformers, OpenAI API, etc.). [primary/secondary] — [asr-training](https://github.com/ivrit-ai/asr-training)

### Inferences / Proposal (untested)
- Gold set: 3 clips x ~45-60 s: (1) clean streamer monologue with names, (2) phone-call/remote speaker, (3) loud/shouting + game audio. Transcribe by correcting the best system's output; mark each word's start/end for ~30 words in Audacity/ELAN/Praat (or use Whisper-guided then manual fix). ~2-3 minutes of audio gives ~400-600 words: enough to see differences >2-3 points WER, not smaller ones.
- Metrics: WER and CER (use `jiwer`), after normalisation (strip punctuation/niqqud, normalise final letters, digits); name-recall (share of glossary names correctly shown); "visible error rate" = wrong words that would actually be displayed (the metric that matters under the Section 6 policy) and "omission rate" = correct words suppressed; empty-region recall (spoken seconds with no words); hallucinated-word count in non-speech; timing: mean/median/p90 absolute start error in ms.
- Compare in this order (each as an ablation, stop when no gain): rendition/loudnorm; VAD params; prompt/hotwords on/off; ivrit-ai vs Groq turbo vs agreement-select; WhisperX alignment vs Groq word times vs proportional fallback; glossary substitution; LLM stage (expect smallest effect; drop it if visible-error rate does not fall).
- Keep a growing regression set: every time a wrong word is noticed in a published clip, add the 10 s clip and its fix.

### Gaps
- No ready Hebrew livestream gold set exists in the sources found; must be built locally.
- Minimum gold-set size for reliable conclusions is a rule of thumb, not sourced.

---

## Source-quality notes for the report writer
- Everything labelled [secondary] was summarised by the search tool and, where it matters, should be re-verified on the original page (Hugging Face model cards, arXiv PDFs, Groq and AWS docs) once those hosts are reachable; numbers in the ROVER and LLM-correction papers are English/Persian, not Hebrew.
- The direct-read sources (faster-whisper, WhisperX, stable-ts, ctc-forced-aligner, viter, ivrit-ai repos, Streamlink) are GitHub files read in full or via fetch summaries; defaults quoted are from the master branch on 2026-11-13 and can change.
- Biggest open questions that would change the design: (1) real audio bitrate of Kick's renditions (ffprobe), (2) measured accuracy of imvladikon wav2vec2 vs MMS vs viter on Hebrew timing, (3) whether Groq prompt/hotwords help Hebrew, (4) whether any LLM stage beats the glossary-only stage on a real gold set.

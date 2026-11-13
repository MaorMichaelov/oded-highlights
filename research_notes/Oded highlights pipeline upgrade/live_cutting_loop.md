# Live cutting loop: watching a long Hebrew Kick stream and cutting completed topics while it continues

Research scope note: arxiv.org, docs.github.com, autoclip.dev, hackernoon.com and githubstatus.com were NOT reachable from this session (DNS failure), so arXiv papers and GitHub docs are cited only through search-result snippets and mirrors. Anything I could not open is flagged "snippet only". Design proposals are kept in the Inferences blocks and are my own, not evidence.

## 1. Incremental topic segmentation on a growing transcript (when has a topic ended, no cutting of resumed topics, open/closed state across hourly runs)

### Takeaway
No published method does exactly "online LLM topic closing on a growing transcript with overlap and idempotent state". The nearest evidence is Membox (LLM sliding-window "does the topic continue?" classifier run turn by turn) plus classical TextTiling/embedding-block methods (TreeSeg, BertSeg), which are offline and score only modestly (TextTiling F1 about 0.53 on podcasts). So the reliable design is an LLM judging windows, with a mandatory lag buffer and a "resume check" as safeguards. Both are my proposals, listed under Inferences.

### Cited Findings
- Membox treats segmentation for LLM agent memory as an online problem. A "Topic Loom" is an LLM-guided sliding-window classifier that, per new message, decides whether the topic continues, grouping consecutive same-topic turns into "boxes". A second part, "Trace Weaver", links boxes across true discontinuities to recover recurring macro-topics (i.e. topics that resume). Exact prompt and label set were not visible in snippets. — [Membox arXiv 2601.03785 (search snippets)](https://www.arxiv.org/abs/2601.03785), [review](https://www.themoonlight.io/review/membox-weaving-topic-continuity-into-long-range-memory-for-llm-agents)
- Membox's paper positions neural approaches as offline supervised boundary prediction over fully observed sequences, in contrast to its online setting. — [Membox arXiv HTML (search snippet)](https://arxiv.org/html/2601.03785v1)
- TreeSeg: embeds each utterance, then uses divisive clustering to find split points, giving a hierarchy of topics. Its only hyperparameter is the utterance block width. It targets noisy ASR transcripts but assumes the full transcript is available (offline). — [TreeSeg arXiv 2407.12028](https://arxiv.org/pdf/2407.12028)
- BertSeg (TextTiling with pretrained sentence embeddings over overlapping blocks) and HyperSeg are named as TextTiling descendants in the TreeSeg related work. — [TreeSeg HTML](https://arxiv.org/html/2407.12028v1)
- A 2025 Webis thesis comparing segmentation on podcast transcripts reports plain TextTiling at F1 0.53, Pk 0.44, WindowDiff 0.45, and an LLM-labels-plus-mpnet-similarity approach whose F1 peaked around a similarity threshold of 0.4 (the LLM method's own numbers were cut off in the snippet). — [Webis thesis slides](https://downloads.webis.de/theses/slides/chaitanya-valaboju_2025.pdf)
- ToC-LLM (Jan 2026) uses an LLM to generate multi-level tables of contents from a complete speech transcript, with pause durations as extra input; reports gains over established baselines on meeting and lecture transcripts. It is offline. — [arXiv 2601.02128](https://arxiv.org/html/2601.02128)
- I found no paper that evaluates merging boundaries across overlapping LLM windows (stated by the search tool as well). — [search result summary, no single source]
- LIGHTOR (chat-driven highlight work) states that its first stage only gives an approximate highlight location, "still not clear about the exact boundary", and a second "Extractor" stage refines start and end. This is a precedent for coarse-then-refine boundary logic. — [LIGHTOR (SFU PDF)](https://www2.cs.sfu.ca/~jnwang/papers/lightor.pdf)
- Existing transcript-LLM clippers cap work at small units: clipsmith feeds an LLM at most 20 candidate moments by default and produces 15-30 s clips, so it is not a long-topic segmenter. — [clipsmith-ai on PyPI](https://pypi.org/project/clipsmith-ai/)

### Inferences
(Proposals, not evidence. All parameters need calibration on past VODs.)
- Data model, one JSON file per stream under `state/<vod_id>/topics.json` plus an append-only `events.jsonl`:
  - `topic = {id, status: open|closing|closed|cut|rejected, start_s, last_seen_end_s, title, summary, anchors:[first 3 and last 3 sentences with sec], category_hint, first_flag, score, revision}`.
  - Stable id = hash(vod_id + start_s rounded to the sentence) so re-running with overlap re-derives the same id (idempotence).
- Each hourly run reads: (a) the open topics with their summaries and last 2-3 minutes of text, (b) the new transcript plus a 10-15 minute overlap back before the previous run's high-water mark, (c) a list of recently closed topic summaries (last 6-8 hours, one line each). It outputs a JSON patch: extend, split, open, and propose-close operations. The runner validates the patch against the schema, never trusting the LLM to rewrite state.
- Three-stage closing instead of a binary judgement, to avoid cutting topics that resume:
  1. `open -> closing` when the LLM says the topic has moved on AND at least one different topic has been discussed for >= ~3 minutes (or a category change occurred).
  2. `closing -> closed` only after a hold buffer: a conservative default of >= 15-20 min of other content and one further run confirming no return. Streamers return to topics via chat questions and callbacks, so the lag is the price of reliability. For long topics, close on the next run's confirmation instead of a single run.
  3. Resume check before cutting: a cheap embedding or LLM query "does anything in the last N hours continue topic X?" over closed-topic summaries. If a later segment continues a closed-but-uncut topic, merge (or let the later segment form its own "Part 2" candidate). Merge candidates are chosen by summary similarity plus named-entity overlap.
- Cheap pre-filter (free, runs in the Action before the LLM session): sentence-embedding block similarity (TextTiling/BertSeg-style, using a multilingual model such as multilingual-e5-small, which is a model I assumed works for Hebrew and did not verify) to propose candidate boundaries. Give them to the LLM as hints, together with silence gaps over 20-30 s, category changes and long pauses. The LLM decides, the pre-filter only narrows attention. Given the TextTiling F1 about 0.53 evidence, do not rely on the embedding signal alone.
- Hard rule "never cut mid-topic" is enforced mechanically: a topic cannot enter the cut list unless status is `closed` and its end is at least `hold_buffer` before the transcript high-water mark.
- Fast lane for "firsts" (e.g. first GTA 6 entry): accept a shorter hold (e.g. 6-8 min) because a clear marker (category switch to GTA 6, "first time" language) exists, and mark the cut `provisional` so it can be superseded if the topic resumes. Prefer cutting the first N minutes as "Part 1" with a fixed natural end (sentence boundary) rather than waiting for the whole segment to end.

### Gaps
- No access to full text of Membox, so I cannot quote its prompt, window size or boundary accuracy.
- No published benchmark for online segmentation of Hebrew live-stream speech, which has no clear sectioning and heavy digressions.
- No evidence for the right hold-buffer length; it needs measuring on past VODs (see Q6 replay harness).

## 2. Scoring and selecting which closed topics deserve a video (signals, thresholds, calibration, human-in-the-loop)

### Takeaway
Published highlight detectors rely most on chat-message bursts (LIGHTOR, MINT, clippy) but all chat-based methods need live capture; Kick chat is reachable by an unauthenticated Pusher websocket but has no history API, so a logger must run during the stream. For a 6-30 minute "complete topic" the signal that matters is LLM judgement of the whole topic, with chat/audio as supporting features.

### Cited Findings
- LIGHTOR (ICDE 2020): "Highlight Initializer" uses time-stamped chat messages (a burst of messages in a short time implies a highlight just happened) to find approximate highlight positions; evaluated on real Twitch data (about 500 Mechanical Turk users for the crowd component); it also used 173 League of Legends videos per another snippet. — [LIGHTOR PDF](https://www2.cs.sfu.ca/~jnwang/papers/lightor.pdf), [arXiv 1910.12201 (snippet)](https://arxiv.org/pdf/1910.12201)
- MINT (EPJ Data Science 2021) is a multimodal model combining chat, video metadata and view counts to find "epic" moments, trained on Twitch clip data; code and clip dataset released on GitHub. — [Algorithms Suggest Epic Moments in Live Streaming](https://blogs.biomedcentral.com/on-physicalsciences/2021/09/02/epic-moments-live-streaming/)
- Ringer's York thesis covers highlight detection from audio, visual and language data plus a TwitchChat dataset; Autohighlight uses audio-visual fusion for League of Legends. — [York/White Rose thesis](https://etheses.whiterose.ac.uk/32406)
- KLive (arXiv 2407.12002) says there is no large public livestream-highlight dataset; AntHighlight has only 3,656 samples. — [arXiv 2407.12002 (snippet)](https://arxiv.org/pdf/2407.12002v1)
- clippy spike detector: per channel, per second, 5 s burst count versus 30 s sustained count; baseline = mean of non-zero burst values over a 30-sample window; fire if burst > baseline x (about 1.5-2.5 by channel size), burst > 1 msg/s, viewers >= 500, and no spike in the preceding 30 s. Then the last 50 chat messages plus game/title/viewers go to Claude Haiku 4.5 returning mood (9 classes), a one-sentence description and `clipWorthy`; LLM budget cap default $20. No accuracy evaluation or tests are mentioned. — [clippy README](https://github.com/hamzaskewl/clippy)
- clipsmith ranks candidates from chat message density, Twitch clips and `!clip` chat commands, then asks an LLM to pick; weights are not published. — [clipsmith-ai](https://pypi.org/project/clipsmith-ai/)
- Kick chat: public Pusher websocket, no login for public chatrooms, channel `chatroom.{chatroom_id}.v2`, chatroom id from `https://kick.com/api/v2/channels/{slug}` (Cloudflare-protected), cluster `ws-us2.pusher.com`; no chat history API, so only messages sent while the logger runs are captured; unofficial and may break. — [kick-api Rust crate source](https://docs.rs/crate/kick-api/0.1.7/source/src/live_chat.rs), [Apify Kick chat archive](https://apify.com/devilscrapes/kick-chat-archive)
- Event name varies between sources (`ChatMessageSentEvent` vs `ChatMessageEvent`). — [mattseabrook/KICK.com-Streaming-REST-API](https://github.com/mattseabrook/KICK.com-Streaming-REST-API)
- songomen/kick-chat-logger (Go) joins channels listed in `channels.json` keyed by chatroom id and writes per-month text logs. — [repo](https://github.com/songomen/kick-chat-logger)
- yt-dlp's Kick extractor has a clips extractor (`v2/clips/{id}`) and a channel clips listing (`v1/channels/{creator_id}/clips` with sort/time params and cursor), which could be polled for viewer-made clips as a "viewers cared here" signal. — [yt-dlp kick.py](https://raw.githubusercontent.com/yt-dlp/yt-dlp/master/yt_dlp/extractor/kick.py)

### Inferences
- A GitHub-hosted runner is not a good place for a 14-hour persistent chat logger (job timeout on hosted runners is 6 h per my memory, not verified here, and the chat connection can drop). The practical free options are (a) a chained sequence of Action jobs that each capture ~5.5 h and hand off with overlap, or (b) running the logger on Maor's own machine and pushing 1-minute-bucket counts. Either way store only aggregates: `chat/<vod>/<minute>.json = {msgs, uniq_users, emote_counts, top_tokens}`, not raw chat (size and privacy).
- Score a closed topic with a transparent additive rubric, LLM-filled but with numeric fields so thresholds can be calibrated:
  `score = 0.35*llm_story (complete arc, stakes, payoff) + 0.20*llm_entertainment (laughter words, shouting, surprise, conflict) + 0.15*first_bonus + 0.15*audio_peakiness (p95 loudness vs stream baseline, z-score) + 0.10*chat_z (peak minute z-score vs trailing 2 h) + 0.05*viewer_clip_count`.
  Missing signals are dropped and weights renormalised, so the system works with transcript only.
- Hard filters before scoring: topic duration 6-30 min (shorter -> merge candidate or Shorts-only; longer -> split at the best sub-boundary), `waiting_screen_fraction`, `gambling`, `third_party_video` flags (LLM boolean plus rules: very low words-per-minute for waiting; quoted or non-streamer speech for third-party video; casino/slot vocabulary) reject at once.
- Calibration: Maor labels 40-60 past topics (publish / maybe / no) in a CSV in the repo; fit thresholds by choosing the cutoff that reaches >= 90% recall of "publish" labels; re-fit monthly. Do not train a model on so few labels; tune cutoffs and weights by hand and check ranking agreement (Spearman or top-k overlap).
- Human-in-the-loop (free): every cut is first uploaded as private/unlisted; a GitHub Issue (one per candidate) is created with title, score breakdown, quotes and the private link; Maor replies with a label (a reaction emoji or `/approve`, `/reject reason`) which a small workflow reads, writes to `labels.csv`, and flips status. Rejections with reason become few-shot examples in the next selector prompt. Use issue comments, not email, to keep it free.

### Gaps
- No evidence on Hebrew laughter/shouting lexicons; no Hebrew-streamer-specific labelled data. All weights above are unvalidated guesses.
- Could not confirm whether Kick exposes viewer-clip timestamps relative to the VOD (clip objects might carry a start offset); needs a live API inspection.
- I did not verify the Kick Pusher key/event schema is still current as of Nov 2026.

## 3. Cut precision (sentence snapping, pre-roll, ASR gaps, cold-open quotes, verifying quotes)

### Takeaway
Word timestamps and VAD give the raw material, but known Whisper failure modes (hallucination in silence, repeated text, timestamp shift with VAD) mean that boundary logic must treat ASR gaps and repeated lines as suspicious. Verification of quotes against the transcript should be mechanical (fuzzy string match), not trusted to the LLM.

### Cited Findings
- clipsmith produces word-level timestamps with faster-whisper and cuts with ffmpeg at 15-30 s clips, but its docs do not describe how start/end are chosen or snapped. — [clipsmith-ai](https://pypi.org/project/clipsmith-ai/)
- Whisper in silence can emit repetitive or nonsensical text; `vad_filter=True` in faster-whisper (Silero VAD) is the commonly recommended mitigation, together with `condition_on_previous_text=False` to limit repetition loops. — [popularai](https://www.popularai.org/p/whisper-hallucinations-during-silence), [pyshine faster-whisper](https://pyshine.com/faster-whisper-2/), [Vexa docs](https://docs.vexa.ai/transcription-quality)
- `hallucination_silence_threshold` needs word timestamps and is off by default; sources disagree on whether faster-whisper has it in all versions. — [localaimaster](https://localaimaster.com/blog/whisper-hallucination-fix) and others as summarised in search
- One troubleshooting notebook claims combining `vad_filter` and `word_timestamps` shifts the timeline; other guides do not mention it (conflicting/unverified). — [ASR troubleshooting notebook](https://notebook-dg9.pages.dev/kb/ai/asr/troubleshooting/)
- Hebrew ASR: ivrit.ai fine-tuned faster-whisper models (e.g. `ivrit-ai/whisper-large-v3-turbo-ct2`, `faster-whisper-v2-d4`) report WER about 4.9-5.5% on ivrit.ai eval-d1 (podcast-like) and 6.1% on eval-whatsapp, self-reported by third-party model cards, so noisy live-stream speech with game audio will be worse. — [model card (MaorB/kol-stream-he-en)](https://huggingface.co/MaorB/kol-stream-he-en), [ivrit-ai turbo CT2](https://huggingface.co/ivrit-ai/whisper-large-v3-turbo-ct2)
- Whisper-style models need whole 30 s windows and are not truly streaming. — [same model card](https://huggingface.co/MaorB/kol-stream-he-en)
- The Kick VOD HLS manifest comes from `playback_url.vod` via POST `https://web.kick.com/api/v1/stream/{video_id}/playback`; requests use impersonation (Cloudflare). — [yt-dlp kick.py](https://raw.githubusercontent.com/yt-dlp/yt-dlp/master/yt_dlp/extractor/kick.py)

### Inferences
- Boundary algorithm (proposal): given LLM's topic `[start_hint, end_hint]`:
  1. Snap start to the beginning of the first sentence at or after the hint where the preceding gap >= 0.4 s (or the nearest preceding sentence start within 10 s). Snap end to the end of the last word of the last sentence, then add a 1.0-2.0 s tail.
  2. Pre-roll: 3-5 s before first word for normal topics; up to 10-15 s if the topic starts with an action that has no speech (entering a game).
  3. Because HLS cuts are keyframe-limited, request segments covering `[start-6s, end+6s]` from the downloader, then re-encode trim in ffmpeg with `-ss` after `-i` (accurate seek) on the already small range; this is a standard approach, not verified in this research.
- ASR gap handling: mark transcript gaps > 30 s with no words as `silence` objects with duration; if a gap is inside a topic and > 60-90 s, treat as potential waiting screen or ASR failure and ask the LLM to decide cut or keep; if a gap is on the boundary, trim to the first/last real word. Flag lines repeated >= 3 times or extremely low-confidence (high `no_speech_prob`, low `avg_logprob`) as hallucination and exclude them from quote selection.
- Cold-open hook: ask the LLM for 3 candidates as `{quote_text, start_s, end_s}` from inside the topic (each 3-8 s, self-contained, no spoilers of the ending needed). Verify mechanically: normalise Hebrew (strip niqqud, punctuation, final-letter forms), compute fuzzy partial ratio against the transcript words in `[start_s,end_s]`; accept at >= 0.9 else drop; re-derive true times from word timestamps rather than trusting LLM seconds. Reject quotes with profanity if the channel policy requires it, and ensure no quote lies within 15 s of the topic end if the hook would spoil.
- Hebrew-specific caution (my assumption): proper nouns, English game terms and Arabic/Russian mixtures are frequent ASR error sites, so pass the LLM a glossary (streamer's regulars, GTA 6 terms) and never publish a title that contains a name only seen once in ASR without a check.

### Gaps
- No reliable source on faster-whisper `word_timestamps` + VAD timing drift; must be tested on a sample hour before trusting boundaries to < 1 s.
- Not verified how the existing repo's transcripts record word-level times (the notes assume the JSONL has start/end per segment, possibly without words).
- ffmpeg `-ss` behaviour on Kick's HLS (IVS) segments not tested here.

## 4. Latency budget and the fast lane on free GitHub runners

### Takeaway
GitHub's scheduler is best-effort: typical delays of a few minutes, sometimes tens of minutes, and occasional silent drops; so an hourly Claude session plus 10-minute chunks yields a realistic topic-to-upload latency measured in about 1-3 hours, dominated by the deliberate hold buffer, not compute.

### Cited Findings
- GitHub schedule events are delayed under load; community reports say usual delay 3-10 minutes, sometimes dozens of minutes or over an hour; a skipped day was reported (about 24 h gap suggests long delay, about 48 h suggests skip). — [GitHub community discussion #27130](https://github.com/orgs/community/discussions/27130)
- A GitHub status incident reportedly affected about 23% of runs at peak with an average delay of 11 minutes (snippet only; page not reachable). — [githubstatus incident](https://www.githubstatus.com/incidents/fw294tth5m8y)
- Minimum documented schedule interval is 5 minutes; third parties report 5-30 minute drift and silent dropped runs, with advice to avoid the top of the hour, add `workflow_dispatch`, add a watchdog, or trigger from an external scheduler via the API. — [search summary of Hackernoon/dev.to/crontap sources](https://hackernoon.com/your-github-actions-cron-job-can-disappear-without-failing), [crontap](https://crontap.com/blog/github-actions-cron-drift-problem)
- Usage of standard GitHub-hosted runners in public repositories is free; 2026 pricing changes (the new per-minute platform charge) apply to self-hosted runners on private repos. — [GitHub changelog 2025-12-16](https://github.blog/changelog/2025-12-16-coming-soon-simpler-pricing-and-a-better-experience-for-github-actions/), [billing doc](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
- Private repos get 2,000 free minutes/month (Free plan), so a private repo cannot run a 12-hour-per-day pipeline. — [thepricer](https://www.thepricer.org/how-much-does-github-actions-cost/) (secondary)
- Kick has "real-time VODs" where the ongoing stream's VOD is viewable with only seconds of delay (Twitch drops the last 3-5 minutes). — [Gameland](https://gameland.gg/kick-now-has-real-time-vods-with-rewind-so-why-doesnt-twitch/); yt-dlp's Kick VOD extractor has a (skipped) test for an "ongoing livestream VOD". — [kick.py](https://raw.githubusercontent.com/yt-dlp/yt-dlp/master/yt_dlp/extractor/kick.py)
- I found no source confirming that the HLS playlist of an in-progress Kick VOD grows as segments arrive, nor how the VOD's second offsets line up with the already-ingested audio segments. — (unverified)
- Retention: one third-party guide says Kick keeps VODs 30 days on verified channels, 7 days on others (unofficial). — [Eklipse guide](https://blog.eklipse.gg/streaming-tips/how-to-download-vod-from-kick.html)
- Concurrency semantics: with a concurrency group only one run is in progress and one pending; a newer queued run replaces the older pending one even with `cancel-in-progress: false`; a `queue: max` option allows up to 100 pending (mirrored docs and a third-party write-up). — [GitHub docs mirror](https://docs.github.com/en/enterprise-server@3.14/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency), [dev.to concurrency trap](https://dev.to/kanta13jp1/github-actions-concurrency-trap-cancel-in-progress-false-still-drops-queued-runs-5hg3)

### Inferences
Estimated budget (my estimates; replace with measured numbers from a week of logs):
| Stage | Normal | Bad day |
|---|---|---|
| Segment audio ends -> ingest workflow starts | 3-12 min | 30+ min |
| Whisper transcribe + commit | 3-8 min | 15 min |
| Wait for hourly Claude run | 0-60 min (avg 30) | 90 min |
| Hold buffer before topic counted closed | 15-20 min | same |
| Claude decision + cut list commit | 3-10 min | 20 min |
| Render workflow: download range + trim + captions + upload | 5-20 min for a 20 min clip | 40 min |
| Total, topic ends -> private upload | about 1-1.5 h | about 3 h |
- The deliberate buffer, not the infrastructure, is the main latency. For normal topics 1-3 h latency is acceptable for a daily publishing cadence.
- Fast lane: a separate cheap workflow every 15-30 min (use a staggered minute like `:07` and `:37`, not on the hour) that only checks for "first" triggers: category change event, keywords ("first time", GTA 6 titles), or the LLM running on the last 30 min. When it opens a `first` candidate it can request a provisional cut after a short hold (6-8 min). Chain with `workflow_run` or `repository_dispatch` from a PAT/GitHub App token, because events created with `GITHUB_TOKEN` do not trigger further workflows (my memory of docs, not verified in this research).
- The Claude scheduled session cannot be trusted to be exactly hourly either; design it as "catch up from the high-water mark" so a skipped hour just doubles the next window.
- To make the hold buffer cheaper, run the Claude loop every 30 min (the incremental cost is low since it only reads new text and open-topic summaries).
- Subathon 48 h: Whisper and render load rise roughly 3x; ensure public repo (free minutes) and artifacts are cleaned; render queue should use `queue: max` or per-job concurrency groups so no cut is silently dropped.

### Gaps
- I could not open docs.github.com for the exact current limits on schedule events, job timeout, and `GITHUB_TOKEN`-triggered workflows.
- No measured latency for the existing ingest workflow was available to me.
- Unknown whether Kick VOD download of the live segment range works unauthenticated from GitHub runner IPs (Cloudflare may block data-center IPs; yt-dlp uses impersonation).

## 5. Existing open-source live clippers and highlight bots, and their reported failure modes

### Takeaway
Open-source tools are mostly post-hoc (VOD in, clips out) or chat-spike-triggered; none cover "complete topic, 6-30 min, Hebrew, Kick, transcript-driven, while live". Borrow design pieces: clippy (spike logic, LLM classification budget), clipsmith (candidates -> picks -> ffmpeg), kick chat loggers, yt-dlp Kick extractors. Reported failure modes are mostly about commercial tools and inferred from READMEs.

### Cited Findings
- **clippy** (hamzaskewl): Node/TypeScript, Postgres, chat firehose -> spike detection -> Claude Haiku 4.5 classification -> auto-clip; viewer floor 500 means small channels never trigger; no accuracy tests; every spike costs an LLM call, with a budget cap. — [repo](https://github.com/hamzaskewl/clippy)
- **clipsmith / clipsmith-ai** (ricardogr07): twitch-dl download, faster-whisper (Spanish) with word timestamps, chat-downloader, `candidates.json` -> `picks.json` -> ffmpeg/libass clips, watch mode polls every 120 s, Beta; LLM default `claude-sonnet-4-6`. — [PyPI](https://pypi.org/project/clipsmith-ai/)
- **py-autovod** (0jc1): downloads livestreams from Twitch, Kick, YouTube Live with timestamped transcription; upload not implemented; few stars; last pushed April 2025. — [awesome.ecosyste.ms](https://awesome.ecosyste.ms/projects/github.com%2F0jc1%2Fpy-autovod)
- **vod-search** (yurukusa, MIT): faster-whisper transcribe Twitch VODs and keyword search; no LLM ranking or clipping. — [dev.to](https://dev.to/yurukusa/i-built-a-cli-that-searches-3-hours-of-twitch-vods-in-7-minutes-514l)
- **openclip, FunClip, autoclip, Auto-clipper (bendawg2010), stream-clipper (nirvagold), Prompt2Clip, OpenClipping** are listed as Whisper/LLM/ffmpeg highlight clippers; I did not inspect their code, licences or maintenance. — [search listing](https://github.com/bendawg2010/Auto-clipper), [FunClip](https://www.sourcepulse.org/projects/1828172), [openclip](https://www.sourcepulse.org/projects/29444144)
- **Commercial**: Eklipse (free plan 720p, 15 clips/stream, 14-day storage; marketing claims unverified), ClipMe (taps live HLS on Kick/Twitch/YouTube and cuts ranked clips during the broadcast), Automatic Clipper Discord bot. — [Eklipse](https://eklipse.gg/features/automate-stream-clips), [ClipMe](https://alternativeto.net/software/clipme/about/), [Automatic Clipper](https://discordbotlist.com/bots/automatic-clipper/upvote)
- Kick-specific tools: `kick-dl` (juliogarciape), `kickvod-extractor` (mortyobnoxious; extracts master.m3u8 under `stream.kick.com/ivs/...`, suggesting AWS IVS delivery, inferred). — [kick-dl](https://awesome.ecosyste.ms/projects/github.com%2Fjuliogarciape%2Fkick-dl), [kickvod-extractor](https://awesome.ecosyste.ms/projects/github.com%2Fmortyobnoxious%2Fkickvod-extractor)
- yt-dlp issue: 403 Forbidden on sub-only Kick VOD metadata JSON (June 2025 nightly). — [yt-dlp #13442](https://github.com/yt-dlp/yt-dlp/issues/13442)
- Subtitled issue source: I found no user-reported failure-mode write-ups ("missed live", "duplicate clips", "drift") for these open-source tools in the sources I could open.

### Inferences
- Failure modes to design against (from the architecture of these tools, not from user reports): duplicates (same moment from chat spike and transcript path, or re-run after overlap) -> dedupe key by overlap of `[start,end]` > 50% or topic id; drift (VOD seconds vs wall-clock seconds, as in ingest segments with gaps or restarts) -> always store both `vod_s` and wall-clock UTC, and verify alignment by checking a known audio cue at the start of each cut; missed live (ingest dies, nobody notices) -> heartbeat + watchdog (Q6); credential/anti-bot breakage on Kick endpoints (403 on API) -> keep a fallback to the raw HLS master URL stored at stream start.
- Borrow: clippy's two-window spike test (burst 5 s vs sustained 30 s with debounce) for chat; clipsmith's `candidates -> picks` two-file separation (deterministic candidate generation, LLM only selects, then deterministic ffmpeg); kick-chat-logger's `channels.json` keyed by chatroom id; yt-dlp kick.py endpoints for VOD/clips.

### Gaps
- No user reports of failure modes (missed live, duplicates, drift) found.
- Did not open the repos of openclip, FunClip, autoclip, stream-clipper etc., so quality and licence unknown.
- Did not check streamlink's Kick plugin (a search hit: sources.debian.org tests for streamlink 8.1.0 `test_kick.py`) for how it handles live and VOD.

## 6. Operational robustness (state in git, concurrency, retries, dead-letter, alerting, dry-run, replay testing)

### Takeaway
The main hazard is silent stall: GitHub cron can lag or drop runs without any failure signal, so use a heartbeat file plus an external dead-man's-switch (Healthchecks.io free tier, or a self-checking second workflow). State in git is feasible with an append-only/ordered design, a single writer via a concurrency group, and rebase-retry on push.

### Cited Findings
- Dropped scheduled runs fail silently; mitigations from community sources: avoid top of the hour, add `workflow_dispatch`, add a watchdog job, or trigger from an external scheduler via API. — [dev.to monitoring scheduled workflows](https://dev.to/vincentabolarin/how-to-monitor-github-actions-scheduled-workflows-2l5g), [runhooks](https://runhooks.app/blog/github-actions-scheduled-workflows-unreliable/), [dev.to cron timing bugs](https://dev.to/morinaga/four-github-actions-cron-timing-bugs-that-silently-broke-my-daily-pipelines-4935)
- Healthchecks.io Hobbyist (free) tier: 20 checks, 100 log entries per check (per third-party summaries, which disagree on paid prices); it is open source and can be self-hosted. Using it from Actions is usually `curl` to the ping URL (general practice, not sourced). — [freetier.co](https://freetier.co/directory/products/healthchecksio), [toolradar](https://toolradar.com/tools/healthchecks-io/pricing)
- Concurrency groups: one running and one pending; a newer queued run evicts the older pending one even with `cancel-in-progress: false`; unique group per commit SHA or `queue: max` (up to 100) avoids dropped queued runs. — [dev.to concurrency trap](https://dev.to/kanta13jp1/github-actions-concurrency-trap-cancel-in-progress-false-still-drops-queued-runs-5hg3), [GitHub docs mirror](https://docs.github.com/en/enterprise-server@3.14/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency)
- clipsmith's watch mode polls on a fixed interval (120 s); clippy persists state in Postgres or memory (lost on restart without DB). — [clipsmith](https://pypi.org/project/clipsmith-ai/), [clippy](https://github.com/hamzaskewl/clippy)

### Inferences
(Proposals.)
- **State layout in git** (single repo, branch `data` or `main`):
  - `transcripts/<vod>/<seg>.jsonl` (existing, immutable), `state/<vod>/cursor.json {transcript_hwm_s, last_run_utc, run_id}`, `state/<vod>/topics.json`, `state/<vod>/events.jsonl` (append-only decisions), `cuts/pending/<cut_id>.json -> cuts/done/` or `cuts/failed/`.
  - Idempotency: `cut_id = sha1(vod_id|start_s|end_s)` rounded to 1 s; render workflow skips if `cuts/done/<cut_id>.json` exists or a YouTube/Kick upload record has that id in its description.
- **Single writer**: all state-writing workflows share `concurrency: {group: state-<vod>, cancel-in-progress: false}`; commit step does `git pull --rebase` then push with up to 5 retries and jitter; state files are JSON with `revision` incremented; on conflict re-read and re-apply the patch (patch-based updates, not blind overwrite). Artifacts and big files stay out of git (only manifests).
- **Retries and dead-letter**: each cut file has `attempts`, `last_error`; render workflow retries a failed cut up to 3 times with backoff across runs; then moves it to `cuts/failed/` and opens a GitHub Issue (label `dead-letter`) with log tail. A nightly job re-queues failed items marked `retryable`.
- **Alerting (free)**: (1) ingest and Claude loop each write `state/heartbeat/<name>.json` and ping a Healthchecks.io check on success (expected period 15 min ingest, 70 min Claude, with grace); Healthchecks emails or webhooks to Telegram/Discord; (2) an independent watchdog workflow on a different cron minute that fails (which triggers GitHub's own failure email) if `now - heartbeat > threshold` while the Kick channel is live; (3) invariants checked each run: transcript HWM within 25 min of wall clock, no cut stuck in `pending` > 3 h, number of open topics < N, no topic open > 3 h. Public repos with no commits for 60 days have scheduled workflows auto-disabled (my memory of GitHub behaviour, not verified here), so the heartbeat commit has a side benefit; do not rely on it.
- **Dry-run mode**: `DRY_RUN=1` runs the full decision loop, writes to `state_dryrun/` and `cuts/proposed/` and never triggers render or upload; the Claude prompt also receives a `mode` field. Use also for threshold tuning.
- **Replay harness**: take past VOD transcripts, feed them in 10-minute increments with the simulated clock (`now = chunk_end`) into the same entrypoint used in production (loop over `chunks`, call the decision function once per simulated hour), recording `cut_ready_at` for every topic. Metrics: (a) boundary error vs Maor-labelled topic ranges (IoU, start/end seconds), (b) premature-cut rate (topic resumed after close within 2 h), (c) missed topics, (d) latency from true topic end to close, (e) decision stability across overlap re-runs (the same topic id should not flip). Replay with seeded determinism (temperature 0, cached LLM responses keyed by prompt hash) so regression is cheap. Because an LLM session costs quota, replay one or two VODs per change, not all.
- **Idempotent re-runs** are tested by running the same hour twice and by killing between "write state" and "write cuts", expecting an identical final state.

### Gaps
- I could not open GitHub docs for the 60-day auto-disable rule, `GITHUB_TOKEN` event restrictions, or job timeouts; those statements in Inferences are from memory.
- Healthchecks.io free-tier numbers come from third-party comparison sites that disagree on some prices; verify at the vendor page.
- No source found on how a Claude scheduled session behaves if a run is missed or overlaps with the previous (platform-specific, outside this research).

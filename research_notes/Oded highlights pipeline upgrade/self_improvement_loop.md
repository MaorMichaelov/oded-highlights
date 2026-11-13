# Self-improvement loop and unattended reliability for an LLM-agent-run YouTube highlights pipeline (ODED HIGHLIGHTS)

Research date: 2026-11-13. Method note: developers.google.com, support.google.com, ffmpeg.org, docs.github.com and analytix.readthedocs.io all failed DNS from this sandbox, so Google/YouTube API facts below come from WebSearch result summaries of those pages (secondary) and from third-party docs; each is marked. Anthropic pages (code.claude.com, anthropic.com/engineering) were fetched in full. "Inferences" contain both logical inferences and PROPOSALS (labelled PROPOSAL); anything from my background knowledge that I could not source this session is labelled [BK, unverified].

---

## 1. Measurement: what the YouTube Analytics / Data APIs give a small channel, and latency/quota

### Takeaway
The Analytics API (scope yt-analytics.readonly) returns per-video and per-day views, watch time, average view duration, traffic sources and a retention curve (elapsedVideoTimeRatio x audienceWatchRatio). Thumbnail impressions and impression CTR exist in the API ecosystem (Reporting API reach reports; per search summaries also as Analytics API metrics), but the exact Analytics-API metric names and whether they combine with a video filter/day dimension could not be verified from Google's own page this session. Expect 2-3 days of lag and empty/suppressed rows for low-view videos.

### Cited Findings
- Reporting API (bulk CSV) has a channel reach report `channel_reach_basic_a1` with dimensions date, channel_id, video_id and metrics `video_thumbnail_impressions` and `video_thumbnail_impressions_ctr`; CTR = clicks / impressions; reports are daily CSVs covering 24h, accessible 30-60 days depending on report type. Reach metrics are also stated to be available in video reports "for targeted queries". — [WebSearch summary of Google Reporting API docs (channel_reports, full_report_list)](https://developers.google.com/youtube/reporting/v1/reports/channel_reports)
- The official Analytics API metrics page defines `videoThumbnailImpressionsClickRate` as the percentage of impressions that resulted in a click to watch, calculated as clicks / impressions (so an Analytics-API-side impressions/CTR metric appears to exist; sibling `videoThumbnailImpressions` assumed). — [WebSearch summary of metrics page](https://developers.google.com/youtube/analytics/metrics) (page itself not fetchable). One third-party guide lists a different field name `impressionsCtr` which could not be confirmed and conflicts with the official name — [benly.ai](https://benly.ai/learn/dimensions-metrics/youtube-dimensions-metrics). A 2020 Stack Overflow thread said no thumbnail-impression metric existed in the Analytics API; likely outdated — [SO mirror](https://kaweah.freedombox.rocks/kiwix/stackoverflow.com_en_all_2023-11/questions/64786908/youtube-analytics-api-get-thumbnail-impression-click-through-rate).
- YouTube help says CTR is computed on views that come from counted impressions, so views/impressions will not reproduce the reported CTR. — [YouTube Help (via search summary)](https://support.google.com/youtube/answer/7628154?hl=en-GB)
- Retention: dimension `elapsedVideoTimeRatio` (evenly spaced points; for a 2-min video ~1.2 s apart per one source), metric `audienceWatchRatio` (absolute, relative to total views, can exceed 1 with rewinds/loops), metric `relativeRetentionPerformance` (0-1, 0 worst, 0.5 median) compares against similar-length videos; filter `video==VIDEO_ID` required; filter values are strings and case-sensitive. One user reported `relativeRetentionPerformance` did not match the Studio relative-retention chart while `audienceWatchRatio` matched the absolute chart. — [analytix / community docs via search](https://analytix.readthedocs.io/en/v2.1.0/refs/yt-analytics-reports.html), [SO mirror](https://kiwix.lema.org/stackoverflow.com_en_all_2023-11/questions/40345970/youtube-analytics-api-v3-retrieving-relative-audience-retention)
- Latency: connector vendors report ~48 h to 72 h before data is finalized; most recent days can still change; API may withhold values below undisclosed thresholds and returns no rows for dates with no activity. — [Adverity](https://docs.adverity.com/guides/tips-and-best-practices/youtube-analytics-tips.html), [Supermetrics](https://support.supermetrics.com/support/solutions/articles/19000100211-about-youtube-missing-results-from-today-or-yesterday), [Coupler](https://docs.coupler.io/sources/category/marketing/youtube/best-practices)
- Google's data model says reports may be limited if views do not meet "minimum thresholds" (no number given); a wrapper doc says retention returns an empty curve for very-low-view or too-fresh videos and some per-video queries return empty rows even when Studio shows data. — [Zernio docs](https://docs.zernio.com/analytics/get-youtube-video-retention), [Analytics data model](https://developers.google.com/youtube/analytics/v1), [SO mirror](https://kiwix.lema.org/stackoverflow.com_en_all_2023-11/questions/72611423/youtube-analytics-reports-response-empty-rows)
- Data API quota: default 10,000 units/day, reset midnight Pacific; `thumbnails.set` costs 50 units; `videos.insert` historically 1,600 units. A 2026 third-party article claims Google cut insert cost (~Dec 2025) and moved uploads to their own bucket (~June 2026) — UNVERIFIED, conflicting with Google's calculator page. — [Quota calculator (search summary)](https://developers.google.com/youtube/v3/determine_quota_cost), [thumbnails.set ref](https://developers.google.com/youtube/data/reference/rest/v3/thumbnails/set), [postproxy 2026 guide](https://postproxy.dev/blog/youtube-upload-api-guide/)
- Videos uploaded through unverified API projects created after 28 July 2020 are locked private until the project passes an audit (user states app is "in production" — confirm audit status separately). Refresh tokens issued while the OAuth consent screen is in Testing expire in 7 days; switching to In production fixes that (tokens minted during Testing may need regeneration). — [YouTube Help: videos locked as private](https://support.google.com/youtube/answer/7300965), [Google group answer](https://groups.google.com/g/adwords-api/c/vdrb2QMWXHQ)
- Anthropic's long-running-agent harness stresses writing progress to files and git rather than context. — [Anthropic engineering](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)

### Inferences
- PROPOSAL (snapshot design): a GitHub Actions cron (free; no LLM) runs `scripts/snapshot_metrics.py` once daily, ~03:00 Pacific+, pulls for videos published in the last 60 days: (a) Data API `videos.list part=statistics` for views/likes/comments (cheap, 1 unit [BK, unverified]); (b) Analytics `reports.query` per video with `dimensions=day`, metrics `views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage` [BK for names; standard Analytics metrics]; (c) one channel-wide traffic-source query (`insightTrafficSourceType`) [BK]; (d) retention curve per video once at ~7 and ~28 days old; (e) impressions/CTR via Analytics metrics if they accept a video filter, otherwise via Reporting API reach report job (create job once, download daily CSV; retained only 30-60 days so MUST be committed to git). Write append-only `data/metrics/YYYY-MM-DD.json` + a compact `data/video_metrics.csv` (one row per video per snapshot age: 1d,3d,7d,14d,28d). Never overwrite; re-fetch last 4 days each run because values are restated.
- Compare videos at fixed ages (views at 7 days, AVD at 7 days) not at calendar date, otherwise old videos dominate.
- Because data lags 2-3 days, a 48-hour subathon will have no usable analytics during the event; learning from it happens afterwards. Plan the event on rules + health metrics, not on live performance data.
- Quota is not a constraint for metrics (a few hundred units/day) but is for thumbnail rotation (50/ call) and uploads (uncertain cost: assume 1,600 until verified, i.e. max ~6 uploads/day on 10,000 units, minus other calls). Log quota estimates in the snapshot and make the uploader refuse when the day budget is exhausted.
- Add a token-health check to the daily Action (call `channels.list mine=true`; on `invalid_grant` open a GitHub issue) because a dead OAuth token silently stops everything.

### Gaps
- Exact Analytics-API names/combinations for impressions and CTR (`videoThumbnailImpressions`, `videoThumbnailImpressionsClickRate`) with `video` filter and `day` dimension: not verified from Google (page unreachable). Test live with a 1-day query before building on it.
- Numeric "minimum thresholds" for suppressed rows/retention: not published.
- Current videos.insert quota cost and the audit status of this specific app: unverified.
- Whether a 2026 change altered Analytics latency from the ~48-72 h reported by vendors: not found.

---

## 2. Attribution with tens of videos: statistics, bandits, pitfalls, test design

### Takeaway
With tens of videos and ~1.8k subs, feature-level attribution (topic, title pattern, thumbnail style, upload time, length, opening) is mostly noise except for large effects; use pre-registered few-arm comparisons, hierarchical/shrinkage estimates, fixed-age normalisation and a "leave it alone unless the posterior is decisive" rule. Bandits help allocate exploration but are fragile with early data and non-stationarity.

### Cited Findings
- Thompson Sampling can lock traffic onto an early winner, leaving the loser underpowered; early-day observations have outsized influence in short experiments; daily performance drift was found in most experiments, violating stationarity. — [arXiv 2402.10870](https://web3.arxiv.org/pdf/2402.10870), [ar5iv 2210.14369](https://ar5iv.labs.arxiv.org/html/2210.14369)
- Thompson Sampling is more sensitive to time-varying effects than fixed-allocation A/B tests. — [arXiv 2003.01905](https://arxiv.org/pdf/2003.01905)
- Best-of-both-worlds / robust methods are suggested when treatments are few (<~10); asymptotic tests perform poorly at small sample sizes (exact tests suggested). — [arXiv 2307.15154](https://arxiv.org/pdf/2307.15154), [arXiv 2111.00137](https://pdf.arxiv.org/pdf/2111.00137)
- Practitioner advice: windowed/restarted bandits for drift; don't trust confidence intervals that tighten too early; a poor prior can lengthen tests. — [AI Engineer Melbourne](https://ai-engineer-melbourne.pages.dev/topic/multi-armed-bandits-for-evals), [Skeptric Test & Roll](https://skeptric.com/test-and-roll)
- Statsig overview of bandits vs A/B (tradeoff exploration/exploitation). — [Statsig](https://statsig.com/perspectives/multiarmed-bandits-dynamic-ab-testing)

### Inferences
- Power arithmetic (derived by me, standard two-proportion approximation n per arm ~= 16 * p(1-p) / delta^2 for 80% power, alpha 0.05): detecting CTR 4.0% -> 5.0% (25% relative lift) needs ~6,900 impressions per arm; 4% -> 6% needs ~3,000 per arm. A small channel likely gets a few hundred to a few thousand impressions per video, so per-video CTR A/B tests are almost always underpowered; only pooled-over-videos tests or large effects (>=40-50% relative) are detectable. Average view duration has high variance and is worse.
- PROPOSAL (analysis method): one row per video, outcome = log(views at 7d / channel baseline), plus CTR and average view percentage at 7d. Use a Bayesian hierarchical/ridge-regularised model (or simply Beta-Binomial for CTR with a channel-level prior from past videos; shrink every feature effect toward 0). Report effect with credible interval; ACT only if P(effect>0)>0.9 AND effect >= a practical size AND replicated on >=2 independent batches. With ~30 videos fit at most 1 feature at a time; never multi-feature regressions, never mine many features and pick the best (forking-paths false positives).
- Control confounds first: stream-size/hype of the source event, topic virality, day-of-week, whether the streamer shared the clip, Shorts vs long. Log these as covariates in the snapshot. "Topic" will dominate any title/thumbnail effect.
- PROPOSAL (bandit use): only for cheap, repeatable, low-stakes choices with many trials (e.g. 3 thumbnail templates, 3 title patterns), epsilon-greedy with epsilon~0.2 and a sliding window of last ~20 videos, or Thompson sampling with a weak Beta(2,2)-like prior and a floor of 15% allocation per arm. Fixed round-robin assignment is more honest at this scale; assign arms by hash of video_id and write the arm into the video's metadata file BEFORE publishing (pre-registration).
- Learn from big effects: retention-curve diagnostics (e.g. early drop in first 5-10 s) are within-video and far more informative than between-video comparisons; use them to attribute hook/opening problems.

### Gaps
- No small-channel-specific benchmark (typical impressions/video, CTR) was sourced. Typical CTR range figures were not fetched; treat 4-5% as illustrative only.
- No source found evaluating bandits on YouTube specifically.

---

## 3. Experimentation: safe A/B for titles/thumbnails/openings

### Takeaway
YouTube's native Test & compare (desktop Studio, up to 3 variants, winner by watch-time share) is manual and needs enough impressions; on a small channel it often yields no winner. A programmatic fallback (thumbnails.set time-window rotation) is confounded by time but feasible with strict alternating windows and pooled analysis; keep it to big, distinct variants.

### Cited Findings
- Test & compare: up to three thumbnails; winner chosen by watch time share (not CTR alone); available on desktop Studio; not for Shorts; more impressions finishes faster; fewer impressions means a winner is less likely; distinct variants recommended. Titles test added July 2025. — [YouTube Help: Test & compare thumbnails](https://support.google.com/youtube/answer/13861714), [A/B test titles & thumbnails](https://support.google.com/youtube/answer/16391400), [Toptal](https://www.toptal.com/creator/post/youtube-thumbnail-ab-testing), [Tubefilter](https://www.tubefilter.com/2025/07/16/youtube-feature-test-and-compare-titles-thumbnails/)
- Third-party (not official) time estimates: >10,000 impressions/day finishes in days; 1,000-10,000/day 7-10 days; <1,000/day up to the full two weeks; similar variants need more impressions. — [ThumbMagic via search](https://www.thumbmagic.co/blog/ab-test-youtube-thumbnails)
- `thumbnails.set` costs 50 quota units. — [Google ref](https://developers.google.com/youtube/data/reference/rest/v3/thumbnails/set)
- Anthropic: evaluator-optimizer fits when criteria are clear; start simple; add complexity only when it demonstrably improves outcomes. — [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)

### Inferences
- PROPOSAL (safe test ladder):
  1. Pre-publish: Claude proposes 2-3 titles/thumbnails; deterministic scripts check rules (length, banned words, face visible, text size); owner sees them in the approval issue. No live testing.
  2. Live "ABAB" rotation via API only for a handful of important videos: window = 24 h, order A,B,A,B (at least 4 windows = 4 days), `thumbnails.set` at fixed local time; compare impressions-CTR per window using daily Analytics data (lag 2-3 days, so decision at day ~7). Decision rule: pick B only if B wins both of its windows in its pairs AND pooled CTR difference's 90% interval excludes 0 AND impressions per arm >= ~1,500; else keep A (default = status quo). Cost: 50 units/swap, trivial.
  3. Cross-video "template" tests: assign thumbnail template or title pattern per video by hash; evaluate after >= 12 videos per arm (not before); one test at a time; freeze the rest.
- Do NOT test during the subathon (traffic regime is non-stationary; no data for days). Do not rotate titles via API during first 24 h on important videos (churn may confuse the algorithm [BK, unverified]); changes to metadata are not "fake engagement" but avoid excessive edits.
- Opening/intro tests: cannot be rotated post-publish; test across videos with retention-at-30s as the metric, treat only large (>=10 percentage-point) differences as real.
- Over-fitting guard: every learned rule needs (a) an effect size, (b) n, (c) date, (d) a review/expiry date (e.g. 60 days) in the rules file; rules without replication stay labelled "hypothesis" and are not enforced.

### Gaps
- Whether a dedicated API for Test & compare exists: no evidence found; assume manual only.
- No official minimum impression number for Test & compare.

---

## 4. Feedback capture: turning owner comments into persistent, enforced rules

### Takeaway
Because cloud sessions start fresh and Claude Code auto memory is machine-local (not shared across cloud environments), persistent owner feedback must live in the git repo: a short CLAUDE.md, path-scoped `.claude/rules/*.md`, a structured machine-checkable rules file consumed by scripts, and hooks/QA scripts for rules that must never be broken.

### Cited Findings
- Each Claude Code session begins with a fresh context window; CLAUDE.md (human-written instructions) and auto memory (Claude-written notes) carry knowledge across sessions; both are treated as context, not enforced configuration; to block an action use a PreToolUse hook. — [Claude Code memory docs](https://code.claude.com/docs/en/memory)
- Auto memory is machine-local; files are not shared across machines or cloud environments; the first 200 lines / 25 KB of MEMORY.md load at session start. — [Claude Code memory docs](https://code.claude.com/docs/en/memory)
- Keep CLAUDE.md under ~200 lines; scope rules with `.claude/rules/` and a `paths:` filter; for something that "has to happen every time", use a hook, deny rule or managed setting; if a CLAUDE.md line keeps being missed despite emphasis, it belongs in a hook; keep the enforced set small. — [Best practices](https://code.claude.com/docs/en/best-practices), [Memory docs](https://code.claude.com/docs/en/memory)
- Skills hold procedures (e.g. "how to cut a clip", "publish checklist"); `disable-model-invocation: true` stops Claude starting side-effect skills by itself. Custom subagents can be restricted to read-only tools and set to `model: haiku`. — [Best practices](https://code.claude.com/docs/en/best-practices)
- Anthropic harness post: JSON feature list with `passes` field that agents may only flip (JSON chosen because models are less likely to inappropriately edit it than Markdown); progress file + git commits at end of each session; read git log/progress at session start. — [Effective harnesses](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- Context engineering: structured note-taking outside the context window, sub-agents return 1-2k-token summaries, just-in-time retrieval via lightweight identifiers. — [Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- `/doctor prompt-audit` flags stale or contradicting instructions. — [Best practices](https://code.claude.com/docs/en/best-practices)

### Inferences
- PROPOSAL (feedback pipeline):
  - `feedback/inbox.md` or GitHub issue label `owner-feedback`: owner writes raw comments ("captions green", "no pointless zoom"). A (cheap-model) weekly/ad hoc session converts each into a rule entry in `rules/style_rules.yaml`: `{id, text_he, text_en, severity: MUST|SHOULD, source_quote, date, check: <script or null>, status: active|hypothesis|retired, expires}`. Ambiguous comments become a question issue, not a guess.
  - Rules implemented as parameters wherever possible: caption colour -> `config/render.yaml: caption.color`; "no unmotivated zoom" -> `zoom.max_per_minute` and zoom allowed only when `reason` field set. Config beats prose because the renderer enforces it deterministically.
  - CLAUDE.md stays <100 lines: pipeline map, how to run, pointer "read rules/style_rules.yaml before any edit decision", hard rules list. `.claude/rules/` for per-directory rules (render, upload, titles).
  - Enforce MUST rules in code: QA script checks (caption colour from config used, zoom count within cap); PreToolUse hook denying `videos.delete`, edits of `rules/hard_rules.yaml`, pushes to main; Stop hook running `scripts/qa.sh`.
  - Write rules "dated and sourced" and retire quarterly; run `/doctor prompt-audit` after big edits.
  - Never let the agent self-edit `hard_rules.yaml`/safety rules; it may only propose edits via PR/issue (it may append `hypothesis` entries to the learned file).
- Because auto memory does not persist in ephemeral cloud containers, do not depend on it; if used, set `autoMemoryDirectory` into a repo path [documented setting in memory docs; behaviour in cloud sessions not verified] and commit it, or just instruct the agent to write learnings to `rules/learned.md` explicitly.
- Learning log: `learning/log.md` append-only (date, hypothesis, evidence, decision) so the agent's improvements are auditable and revertible via git.

### Gaps
- No source on how scheduled-task sessions treat `autoMemoryDirectory` when repo is freshly cloned; test.
- Owner feedback channel (comments on YouTube vs Telegram vs GitHub issues) is a product decision; the YouTube Data API `commentThreads.list` could pull owner comments but cost/quota and attribution of "owner" were not researched.

---

## 5. Reliability engineering for unattended multi-day operation

### Takeaway
Treat the LLM as one fallible step in a deterministic, idempotent, git-backed state machine: scripts own ingest, state transitions, QA and publishing; the agent only makes bounded judgements and fixes; independent watchdogs (GitHub Actions) alert for free; the owner approves via a private-upload gate until a track record exists.

### Cited Findings
- Anthropic's unattended checklist: does it know what done looks like; can it check its own work; what may it touch; what stops it (`--max-turns`, `--max-budget-usd`); where does the result go and who signs off. "Watch the first few runs of anything new before trusting it unattended"; protect `main` with a branch rule the task can't bypass. — [Best practices](https://code.claude.com/docs/en/best-practices)
- Scheduled tasks: run as full cloud sessions with fresh repo clone each run; push to `claude/`-prefixed branches by default; minimum interval is hourly (sub-hourly cron rejected); on-the-hour runs can start minutes late; cron is UTC unless `CRON_TZ=`; run history marks Succeeded/Failed/Cancelled but "Succeeded" only means the session ended without Claude Code reporting a failure (blocked network requests or incomplete work appear only in the transcript); research preview, limits may change. — [Scheduled tasks docs](https://code.claude.com/docs/en/routines)
- Limits: 100 scheduled runs/hour per account; Run now/API fires 30/hour per task; over-limit scheduled runs wait; API trigger `/fire` endpoint with bearer token and optional `text` context (beta header `experimental-cc-routine-2026-04-01`); GitHub webhook events have hourly caps and excess events are dropped. — [Scheduled tasks docs](https://code.claude.com/docs/en/routines)
- `claude -p` flags for unattended scripts: `--allowedTools`, `--permission-mode dontAsk`, `--max-turns`, `--max-budget-usd`, `--output-format json`, `--bare` (auth then needs ANTHROPIC_API_KEY, which costs money; the user's budget is $0, so `-p` with API key is likely out; cloud scheduled tasks use claude.ai login). — [Best practices](https://code.claude.com/docs/en/best-practices)
- Agents should obtain ground truth at each step, use stopping conditions and human checkpoints; test extensively in sandboxes. — [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)
- Harness post: failure modes (declares done too early; leaves undocumented bugs; marks features done prematurely) and mitigations (feature list, one feature per session, git + progress file, run an end-to-end smoke test at session start, `init.sh`). — [Effective harnesses](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- Google OAuth: refresh token 7-day expiry is Testing-mode only. — [Google group](https://groups.google.com/g/adwords-api/c/vdrb2QMWXHQ)
- Videos from unverified API projects are forced private. — [YouTube Help](https://support.google.com/youtube/answer/7300965)

### Inferences
- PROPOSAL (state machine in git): `state/jobs/<vod_id>.json` with `stage` in {detected, downloaded, transcribed, topics_selected, cut, rendered, qa_passed, uploaded_private, approved, published, analysed, failed:<stage>}; each stage script is idempotent (output path derived from vod_id+stage+input hash; skip if output+hash exist), writes `attempts`, `last_error`, `next_retry_at`; commits state with `[skip ci]`-style tags carefully to avoid loops. Concurrency: GitHub Actions `concurrency:` group per pipeline and a lease field (`locked_by`, `lock_expires`) in the job file so a scheduled Claude session and an Action don't double-process. The upload step records `youtube_video_id` BEFORE doing anything else after the API returns, and checks by `videos.list` / title-hash before retrying so a crash never double-uploads.
- Split of labour: GitHub Actions (free cron, deterministic) = detect live, ingest/download, transcription if feasible, render, QA, upload, metrics, watchdog. Claude scheduled session (limited quota) = topic selection, title/description writing, thumbnail concept, failure triage, weekly retrospective. Scripts write `queue/needs_llm/*.json` with all precomputed inputs (transcript chunks with chat-spike scores, candidate windows); Claude reads queue, writes decisions JSON, scripts validate against a JSON schema and continue. If the LLM is unavailable, scripts fall back to a heuristic default (top-N chat-spike windows, templated titles) or just queue.
- Heartbeat/watchdog (BK, unverified specifics): a separate scheduled Action every 1-3 h reads `state/heartbeat.json` and job ages; opens (or comments on) a GitHub issue labelled `alert` when: no heartbeat > X h, any job stuck in a stage > Y min, OAuth check failed, quota near exhausted, disk/Actions minutes anomalies. GitHub issue creation emails the owner by default through GitHub notifications (free); push notification via the GitHub mobile app (free) or an ntfy.sh topic call (free; host may need allowlisting) [BK]. Beware GitHub may delay/skip scheduled workflows under load and disables scheduled workflows in repos inactive for ~60 days [BK, unverified; docs.github.com unreachable], so have the Claude schedule or a trivial commit as keepalive and a second independent heartbeat.
- Use Claude scheduled-task "Succeeded" as meaningless for health; health = state files and artifacts advanced. Make every session's last act a commit of `state/heartbeat.json` with a summary and a machine-readable status (`ok|degraded|blocked`).
- Retry policy: exponential backoff 2/10/60 min, max 5 attempts per stage, then `failed:<stage>` + issue; poison-pill protection (a VOD failing 3 times is skipped so it cannot block the queue).
- Automatic QA of rendered video (ffmpeg/ffprobe filters; syntax from background knowledge [BK, unverified this session]): `ffprobe` for resolution/codec/fps/duration/audio streams; `loudnorm=print_format=json` or `ebur128` to check integrated loudness near -14 LUFS (+/-2) and true peak <= -1 dBTP; `blackdetect=d=0.5:pix_th=0.1` and `freezedetect=n=-60dB:d=2` for black/frozen frames (fail if > tolerated); `silencedetect=noise=-50dB:d=3` for dead air; duration within [target +/- tolerance]; compare caption timestamps vs transcript, check caption text bounding boxes stay inside safe area and don't overlap burned-in overlays (render a frame at sampled times, OCR/pixel-box check), and that the video does not contain a long run of copyrighted third-party playback (see section 7). Save QA report JSON next to the job; fail closed.
- Golden tests: keep 2-3 short VOD excerpts (<= 60-90 s, public/own content) in the repo or release assets with expected outputs (duration, loudness, caption count, QA pass); run `scripts/golden.sh` in an Action on every change to render code; "replay mode" runs the full pipeline on a past VOD in dry-run (no upload; writes to `out/`) and diffs against the previous result. Add `--dry-run` that swaps the YouTube client for a fake that records calls.
- Approval gate: upload as `private` (or `unlisted` scheduled) + open a GitHub issue with preview link, title, thumbnail, QA report; owner flips to public (or comments "ok" and an Action calls `videos.update privacyStatus=public`). Graduate to auto-publish only per content class after N (e.g. 10) consecutive approvals with zero owner edits, passing QA, and no safety flags; keep an automatic kill switch file `state/PAUSE`. During the subathon, auto-publish only the lowest-risk template (e.g. highlights with no flagged content), with rate limits, and keep high-risk (flagged keywords, gambling mentions, third-party playback) in the approval queue.
- Rate of uploads: cap e.g. 4-6/day and min gap 60-90 min [BK-based proposal] to avoid flooding subscribers and spam heuristics; enforce in the uploader, not in the prompt.

### Gaps
- GitHub Actions scheduling behaviour (delays, 60-day inactivity disable, free minutes for private repos) could not be fetched; verify at docs.github.com when reachable.
- ffmpeg filter parameters were not fetched (ffmpeg.org blocked); verify defaults on a test clip before relying on thresholds.
- Free push-notification services and their reachability from Actions were not researched.
- Whether Claude scheduled sessions can run ffmpeg/YouTube API calls depends on the environment's network allowlist (developers.google.com was unreachable in this very sandbox, so "Limited" network may block YouTube hosts: scheduled tasks docs say Default environment is Limited with package managers allowed; custom allowed domains are configurable) — [Scheduled tasks docs](https://code.claude.com/docs/en/routines).

---

## 6. Cost-aware model routing and scheduling; surviving the usage limit mid-event

### Takeaway
Scheduled tasks draw on the same subscription usage as interactive sessions and, without usage credits, are rejected when the limit is hit until the window resets. Minimise LLM turns per day, put cheap models on routine work, and make scripts independent of the LLM so ingest and queueing continue when it is exhausted.

### Cited Findings
- Scheduled tasks draw down subscription usage like interactive sessions; when the usage limit is reached, orgs with usage credits can run on metered overage, otherwise additional runs are rejected until the usage window resets; "the last run stopped because a usage limit was reached" is a listed status. — [Scheduled tasks docs](https://code.claude.com/docs/en/routines)
- A scheduled task selects one model (and effort) used on every run; the model list in the docs includes Opus 5.5 (default), Sonnet 5.5, Haiku 5.5 and Fable 5.2; effort is the main control for thinking; "Haiku is a good fit for subagents doing simple work"; `model: haiku` can be set in a subagent definition; subagent token use counts against the same usage; each subagent starts with fresh context so there is startup cost; `/usage` breaks usage down by skill/subagent. — [Best practices](https://code.claude.com/docs/en/best-practices)
- Prompt cache lasts about an hour on subscription (five minutes otherwise, subagents five); every request resends the whole conversation, so long sessions cost more; `/clear` between unrelated tasks. — [Best practices](https://code.claude.com/docs/en/best-practices)
- Routing pattern: classify and send easy inputs to a smaller model, hard ones to a more capable one. — [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)
- Sub-agents return condensed 1-2k-token summaries; just-in-time retrieval. — [Context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- Scheduled run limits 100/hour per account; minimum one run/hour per cron; on-the-hour starts slip. — [Scheduled tasks docs](https://code.claude.com/docs/en/routines)
- The user reported one 5-hour limit exhausted by 6 parallel research agents on the largest model (from task brief, not sourced).

### Inferences
- PROPOSAL (task layout; each a separate scheduled task with its own model):
  - T1 "triage" (Haiku, low effort, every 2-3 h, reads `state/*.json` + heartbeat + queue sizes): decides nothing creative; opens/updates issues, retries stuck steps by invoking scripts, exits quickly when queue empty ("nothing to do" check done by a shell pre-check as first command so the session ends in a few turns). Better: do the empty-queue check in an Action and only fire the task via the API trigger (`/fire`, 30/hour per task) when `queue/needs_llm` is non-empty; this costs zero usage on idle ticks.
  - T2 "editor" (Sonnet, medium): topic selection/titles/description for queued VODs from precomputed JSON inputs (<~20-30k tokens per run); batch several clips per run.
  - T3 "retro" (strongest model, high effort, weekly): reads metrics CSV + feedback inbox, proposes rule changes as a PR/issue; escalate to the largest model only for judgement calls (policy-ambiguous content, rule conflicts, strategy).
  - Keep each run short: precompute transcripts, chat-spike windows, candidate segments, thumbnails candidate frames, metadata checklists in scripts; pass file pointers not content; use a fresh session per task (cloud tasks already clone fresh); no parallel research subagents on the large model.
- Subathon (~19 Nov, 48 h): estimate budget in advance: e.g. max N editor runs/day; move to "batch mode" (one editor run every 2-3 h processing all queued clips) rather than per-clip. Pre-write the decision schema and defaults. Pre-warm: pre-generate title templates and thumbnail templates (text overlays rendered by script).
- Graceful degradation ladder: (1) normal; (2) usage limit near (track via failed-run status or a `usage_state` file the T1 sets): drop to Sonnet/Haiku, shorter prompts; (3) limit hit: scripts continue detect/download/transcribe/cut candidate clips/render with heuristic defaults and queue everything private/draft; titles from templates + transcript keywords; no publishing without gate; (4) when window resets, T2 drains the queue oldest-first (or highest-chat-spike first), because a 3-hour late highlight still has value. Record `fallback_used: true` so analytics later attributes performance to LLM-vs-heuristic titles.
- Add a hard cap: per-day LLM-run counter in `state/budget.json` that scripts check before firing a task.
- Use `--max-turns`-like discipline inside scheduled prompts ("stop after processing at most 3 clips; commit; end") since scheduled tasks have no CLI flags in the UI [not verified].

### Gaps
- The exact size of the user's usage window and what fraction one scheduled run consumes: unknown; measure with `/usage` after the first week of runs.
- Whether scheduled tasks can be created with different models per task via UI: yes (model selector in task dialog per docs) but programmatic `fire` per-run model override not documented in what I read.
- Whether the free plan includes scheduled tasks/limits: docs say Pro, Max, Ultra, Team and Enterprise only — [Scheduled tasks docs](https://code.claude.com/docs/en/routines); confirm the owner's plan covers it.

---

## 7. Safety and compliance guardrails enforced automatically

### Takeaway
Enforce "never" rules in deterministic code and hooks, not prompts; classify content with a script filter plus a cheap-model second look; default to the approval queue when anything is flagged. YouTube's monetisation rules penalise mass-produced repetitive content, so each upload needs visible per-video added value.

### Cited Findings
- Deterministic vs non-deterministic control: CLAUDE.md/prompts are judged by the model; hooks, deny rules, sandbox, managed settings are enforced by the harness; deny rules hold in every permission mode; `command`/`http` hooks are deterministic while `prompt`/`agent` hooks are not; PreToolUse exit code 2 blocks an action. — [Best practices](https://code.claude.com/docs/en/best-practices)
- Scheduled runs start in auto mode (classifier judging risky actions) when available; protect `main` with a branch rule; Claude pushes to `claude/` branches. — [Scheduled tasks docs](https://code.claude.com/docs/en/routines)
- YouTube renamed "repetitious content" to "inauthentic content" (July 15, 2025); target is mass-produced/repetitive content such as many near-identical template videos; monetisation remains possible with significant original commentary, editing or entertainment value; coverage conflicts on whether it is a "crackdown" or a "minor update"; none of the sources addressed clips/highlights specifically. — [Gulf News](https://gulfnews.com/technology/youtube-updates-monetisation-policies-ai-and-repetitive-content-ban-begins-july-15-1.500192660), [Social Samosa](https://www.socialsamosa.com/news-2/youtube-clarifies-monetisation-policy-targeting-inauthentic-content-9493155), [Plagiarism Today](https://www.plagiarismtoday.com/2025/07/08/youtube-targets-inauthentic-content/)
- Videos locked private from unverified API projects cannot be appealed; re-upload via verified client. — [YouTube Help](https://support.google.com/youtube/answer/7300965)

### Inferences (all PROPOSALS; policy specifics [BK, unverified])
- Hard rules file `rules/hard_rules.yaml` (human-edited only), enforced by `scripts/guard.py` called by the uploader and by a PreToolUse hook on Bash/Edit:
  1. No deletion: the YouTube client wrapper simply lacks `delete` methods; PreToolUse hook blocks `git rm` of data/, `git push --force`, `videos.delete`/`playlistItems.delete` strings; OAuth scope audit (note: upload/edit need `youtube`/`youtube.upload` scopes; deletion is physically possible with the `youtube` scope, so enforce in code).
  2. Content filter: Hebrew+English slur list and gambling/casino/betting-promo terms matched against transcript segments, titles, descriptions, thumbnail OCR text; any hit => segment cut-out or whole clip diverted to `needs_owner` queue; the cheap model may classify borderline context but cannot override a hit. Gambling: exclude segments where the streamer promotes/plays gambling sites [YouTube policy details not verified; confirm in YouTube Help]. Also exclude personal data (doxxing, addresses, minors) — apply same flow.
  3. Third-party video playback: detect via audio fingerprint is heavy; cheap heuristics: streamer's stream "reaction/watching" scenes flagged by scene classifier or by transcript cues ("watching trailer"); limit any third-party footage to short segments; for GTA 6 official trailers/gameplay visible in stream, prefer game footage from the streamer's own gameplay; keep the owner approval gate for flagged segments. Content ID claim risk cannot be eliminated; accept private upload + owner decision.
  4. Credit/attribution: description template must include source stream title, streamer name, link to VOD with timestamp, "highlights from ..." and permission note; QA fails if template fields are missing; Claude may only fill the free-text part.
  5. Upload rate caps (per day, min gap), duplicate-title check, and a per-source-VOD cap (e.g. <= 5 clips/VOD/day) to avoid flooding and "mass-produced" patterns; add distinct title/thumbnail/topic and ensure each video contains commentary/editing value (captions, context, selection).
  6. No fake engagement: no like/comment/subscribe automation, no posting comments as the channel via the agent, no view-boost, no incentivising engagement; the agent's OAuth token should not include `youtube.force-ssl` comment-posting use; code wrapper has no `commentThreads.insert`/`ratings`. Pinned-comment links by the owner only.
  7. Disclosure: if AI-generated/synthetic voice or altered visuals are used, set the altered-content disclosure field; `containsSyntheticMedia` exists on videos status in recent API versions but I could not verify the field name — [BK, unverified; do not rely without checking].
  8. Kill switch: `state/PAUSE` file or issue label `pause` halts uploader; watchdog checks it.
- Add an audit log (`logs/uploads.jsonl`: video id, title, QA hash, who approved) and weekly Claude review of "near miss" flags.

### Gaps
- No primary YouTube policy text on gambling promotion, reused-content rules for stream highlights, or third-party video/Content ID handling was fetched (support.google.com unreachable); owner should confirm with the channel's own streamer permission and current YouTube policies.
- Exact AI-disclosure API field not verified.
- No sourced evidence of what free push-alert services allow Actions traffic.

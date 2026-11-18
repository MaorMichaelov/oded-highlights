# Backlog: what is still missing (audit of 18 Nov 2026)

Ranked by value / effort for the goal "a product streamers pay for" with budget zero. Sources: full read of workflows, scripts, Worker and docs; competitor table in `docs/PRODUCT_PLAN.md` section 1; the failure log in `docs/POSTMORTEM_15_16_NOV.md`.
Effort: S = under half a day, M = 1-3 days, L = a week or more. Value: H / M / L. "Next step" is the first concrete thing to do.

## A. Blockers for selling (do these before the first paying customer)

| # | Item | Value | Effort | Next step |
|---|---|---|---|---|
| A1 | **Private render server instead of GitHub Actions** (GitHub terms forbid Actions as the back end of a paid service; also lets the repo go private) | H | L | `scripts/render_worker.py` + `job_runner.py` exist (WIP). Run it on the owner's PC with `STUDIO_WORKER_KEY`, claim one demo job end to end, then move Hebrew live ingest to the same box. See `PRODUCT_ARCHITECTURE.md` section 9 |
| A2 | **Make the repo private / split it**: today the whole product (prompts, rules, pipeline, state, owner feedback) is public | H | S (after A1) | Move `state/` and `docs/` (owner feedback, prompts) to a private repo first; keep only generic code public if you want. History cannot be cleaned without a rewrite (not done on purpose): treat everything ever committed as public |
| A3 | **Move Studio from KV to D1 / Durable Objects** (credits, claims, queue are not atomic: double refund, double claim, lost credit on a race) | H | M | Credit ledger table + `UPDATE ... WHERE credits >= ?`; queue claim as `UPDATE ... WHERE status='queued' RETURNING`. The `TODO(D1)` markers in `app/studio.js` list every spot |
| A4 | **Payments** (Paddle / Lemon Squeezy as merchant of record) + top-up webhook | H | M | Create the Paddle seller account; webhook handler writes to the credit ledger (A3). Endpoint stubs exist (`/billing/checkout`) |
| A5 | **Email verification + invite emails** (trial credits can be farmed with throw-away addresses; invites are copy-paste links) | H | S | Resend / Brevo free tier from the Worker; verify before granting `TRIAL_CREDITS` |
| A6 | **Terms of Service, Privacy Policy for customers, DMCA agent** (`PRIVACY.md` says "personal tool, collects nothing about others": wrong once Studio stores emails and OAuth tokens) | H | S | Write the 3 pages (template + lawyer review), host them at `/studio/legal`, required for Google OAuth verification |
| A7 | **Google OAuth verification + YouTube API quota audit** (100 uploads/day per project; unverified apps are capped at 100 test users) | H | M | Start the audit form now (takes weeks); the connect flow (`youtube_connect.js`) is built and dormant |
| A8 | **Kick/Twitch ingest without scraping the undocumented API** (Kick ToS 1.4 forbids automated access) | H | M | Kick OAuth (`user:read`) for ownership + webhooks for live/offline; customer supplies VOD URL / file as the fallback (`worker_sources.py` has the resolvers) |

## B. Product features competitors have and we lack

| # | Item | Value | Effort | Next step |
|---|---|---|---|---|
| B1 | **Blind quality benchmark vs OpusClip / Eklipse** (we have no measurement that our picks win; this is also the sales page) | H | S | Run 3 streams through all tools, 20 moments each, owner rates blind; store in `docs/QUALITY_REPORT.md`. `scripts/eval_cuts.py` already grades cuts |
| B2 | **Gameplay-aware moment detection** (speech-only rankers miss non-verbal highlights: kills, wins, fails) | H | M | Add audio-energy / chat-spike / killfeed-OCR peaks to the Shorts candidate list (`vod_shorts.py` already uses energy peaks; add chat spikes from `state/chat` and a per-game killfeed template) |
| B3 | **Auto-reframe 9:16 with face + game focus** (known issue 1: screen-share layout unstable) | M | M | Finish `smart_reframe.py`: YuNet face box + frame-difference window, hold-then-glide; add a regression clip to `tests/` |
| B4 | **Caption style editor + brand kit per customer** (colour, font, logo, intro/outro) | M | M | `config/styles/*.json` is the data model; expose 3 knobs in the Studio page and pass `style_id` through the job |
| B5 | **Direct publishing + scheduling** (approve -> publish/schedule via `videos.update`; best-time suggestion) | M | M | Needs A7. `publishAt` is already supported by `yt_upload.py` |
| B6 | **TikTok / Instagram Reels export** (cross-post is the main reason people pay Opus/Vizard) | M | M | Export-only first (download button, correct specs, no watermark); API publish later (TikTok needs app review) |
| B7 | **Per-clip analytics loop** (views/retention back into the picker: `state/yt_stats.json` exists, `predict.py` predicts) | M | M | Feed 30-day results into `lessons.json` automatically; weekly report in the app |
| B8 | **Thumbnails for customers** (AI scene with the streamer: works for Oded only, needs 4 real portraits per customer) | M | L | Customer uploads 4 frames; reuse `make_scene_thumb.py` with a QA gate. Cloudflare free quota is ~100 images/day |
| B9 | **Multi-language for customers** (language auto-detect is now in: `ASR_LANG=auto` / `PICK_LANG=auto`; titles/prompts exist only for he and en) | M | S | Add a prompt table per language (es, pt, fr, de, ar, ru); the detected code is in `ingest_state.json` `_lang` |
| B10 | **Customer-facing progress + notifications** (email / push when drafts are ready) | M | S | Web push code exists in `worker.js` for the owner; generalise to Studio users |
| B11 | **Team approvals with comments / "ask for another take"** (chat intent exists, no re-render path) | L | M | `assistant()` intent "again" -> new job with `hints.text` and the previous draft excluded by the dedup ledger |

## C. Reliability and operations (what the audit found; see the "Done" list below)

| # | Item | Value | Effort | Next step |
|---|---|---|---|---|
| C1 | **Run tests in CI and keep them green**: `tests/test_agent_hooks.py` fails on main (the `docs/agent_hooks/*.patch` no longer apply after the YouTube-connect commits touched `worker.js` / `deploy.py`) | H | S | Regenerate the two patches against current `app/` or apply them for real and delete the patch step |
| C2 | **Second alive-check outside GitHub** (GitHub cron does not fire reliably for this repo; the Cloudflare watchdog is the only restarter and it needs the owner token in KV) | H | S | Free UptimeRobot/Better Stack heartbeat: the Worker pings it every 5 min only when `health.json.overall != critical` |
| C3 | **Groq / Gemini quota awareness**: no shared budget; Groq is used by the live picker, the Shorts jobs and the owner's chat | H | M | Use `scripts/retry.py` (classify quota vs rate limit) in `pick.ask`, `vod_shorts.llm`, `watch_video.py`; keep a per-day counter in `state/llm_budget.json`; stop low-priority work first |
| C4 | **Replace remaining `json.dump(x, open(p, "w"))` state writes** with `statefile.write_json` (done for live_watch, pick_state, uploaded.json, health; still open: `retries.json`, `timeline.json`, `index.json`, `status.json`, `lessons.json`, `events` readers) | M | S | Mechanical replace + `read_json` for every state read; the health check flags `*.corrupt-*` files |
| C5 | **Loop exits cleanly before the 6 h limit and hands over** (a cycle that overruns 355 min kills the job before it re-dispatches itself; recovery today = Cloudflare watchdog, up to 5 min gap) | M | S | Check remaining time at the top of each iteration (`$SECONDS`) and skip a long station when less than 20 min remain |
| C6 | **Upload ledger independent of git** (YouTube-side title check is in `yt_upload.py`; a durable ledger of `{clip, video id}` in the artifact/KV would also survive a lost push) | M | S | Worker KV key per clip id written by `draft.py` via a small authenticated endpoint |
| C7 | **Pin third-party actions and tools** (`actions/*@v4` tags, `pip install` without versions, `yt-dlp -U`): one breaking release stops every loop | M | S | Pin by SHA / version in one commit; Dependabot for workflows |
| C8 | **Structured logs / metrics page** (durations per station, failure counts, LLM calls) | L | M | `status.json` timings exist; aggregate in `health_check.py` into `state/metrics.json`, chart in the app |
| C9 | **Transcript retention**: `state/transcripts` grows forever in a public repo (privacy and 1 GB repo limit) | M | S | Move to release assets / R2 after 14 days; keep only spans and chapters in git |

## D. Security follow-ups (details in the audit report; none contains secret values)

| # | Item | Severity | Next step |
|---|---|---|---|
| D1 | Owner app stores the owner password, GitHub token and Groq key in the phone's `localStorage` and sends the password in a header on every call (single SHA-256 with salt on the server) | Medium | Session cookie (HttpOnly, SameSite=Strict) + PBKDF2 like `studio.js`; keep the GitHub token only server-side in KV and never return it |
| D2 | LLM agent has write tools (`cut`, `pause`, `lesson`, `instruction`) and reads untrusted text (transcripts, titles). Prompt injection could persist a rule via `instruction`/`lesson` | Medium | Confirmation step for write tools (the app shows "do X? yes/no" and only a user tap executes); rate-limit writes; show the stored instructions in the app |
| D3 | Whole repo is public (prompts, owner feedback, thresholds, workflows) | Medium (business) | See A2 |
| D4 | One historical commit carries a personal email address as author (GitHub web edit); everything else is `noreply` | Low | Cannot be removed without rewriting history (not done); owner can switch GitHub to "keep my email private" for the future |
| D5 | No script CSP on the two pages (inline scripts); frame-ancestors / nosniff added | Low | Move inline scripts to external files + nonce |
| D6 | `ERRS` array in `worker.js` is module-global (error text of one request can appear in another request's debug field) | Low | Make it per-request |
| D7 | `/api/setup` lets the first caller set the owner password when KV is empty (a wiped KV = takeover window) | Low | Require a one-time setup secret (Worker env) |
| D8 | Studio signup is unverified and unlimited per IP besides 10/h; trial credits farmable | Medium | A5 + Turnstile (free) on signup |

## Done in the 18 Nov audit (for reference)

* Workflows: every `${{ inputs.* }}` that reached a shell script now goes through an env var, plus `scripts/ci_check_inputs.py` (shape validation) as the first step; `permissions:` on every workflow; `scripts/ci_lint_workflows.py` keeps it that way in CI (`.github/workflows/tests.yml`).
* Worker: link rendering XSS fixed, LLM-chosen ids validated before they become repo paths / workflow inputs, tool whitelist, duplicate guard in the `cut` tool, https-only push endpoints, security headers, per-account login throttle in Studio, invite accept cannot downgrade a role, worker-key brute-force counter.
* Reliability: `scripts/health_check.py` + `health-check.yml` (every 30 min -> `state/health.json`, one GitHub issue per critical problem), `scripts/git_sync.sh` (race-safe push, no half-rebased checkouts), `scripts/statefile.py` (atomic writes, corrupt files quarantined), `live_watch.py` (progress saved after every window, idempotent transcript append, resume point recovered from the transcript), `scripts/dedup.py` (one ledger for all producers, hooked into pick / vod_long / vod_shorts), YouTube-side duplicate-title guard in `yt_upload.py`, `upload_shorts.py` records after every upload, monitor emits new-problem events (it never did), disk-space step in the big render workflows.
* Features: language auto-detect (`ASR_LANG=auto`, `PICK_LANG=auto`), per-channel / per-customer banned words for every producer (`scripts/safety.py`, `config/banned_words.json`), retry policy (`scripts/retry.py`, ready to adopt in C3).

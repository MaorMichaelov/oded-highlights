# Live-operation architecture: unattended mid-stream highlight clips on GitHub Actions (Kick, ~48h subathon, Nov 2026)

Research date: 2026-11-13. Session network allowlist blocked docs.github.com, docs.aws.amazon.com, docs.kick.com (DNS failure on fetch). Those primary docs were NOT read directly; claims from them come via search-result snippets or secondary sources and are flagged. No live endpoint test was possible from this sandbox.

## 1. Kick VOD/HLS behaviour mid-stream; IVS auto-record semantics; VOD expiry/splitting; live capture with yt-dlp/streamlink

### Takeaway
Nothing I could verify proves that the newest Kick VOD's HLS playlist grows mid-stream; it is plausible (IVS auto-record writes HLS to S3 during the session and only finalizes with ENDLIST at the end), but your own repo's "EVENT"-type playlist tag is the strongest evidence and must be confirmed with a live test. VODs expire (7 days non-verified / 30 days verified per third-party sources) and disconnects split sessions into multiple VODs, so the pipeline must consume per-VOD and never assume one VOD = one stream. Live capture via streamlink has a maintained Kick plugin that solved a Cloudflare 403 in 2025; yt-dlp has a Kick extractor.

### Cited Findings
- IVS auto-record: the hls folder holds all media and manifest files generated during the live session; byte-range playlists (HLS v4) can be generated alongside standard playlists; thumbnails are written every minute — [AWS IVS auto-record docs (via search snippet)](https://docs.aws.amazon.com/ivs/latest/LowLatencyUserGuide/record-to-s3.html)
- Recording session stays open through a reconnect window after an interruption and is finalized with the ENDLIST HLS tag only after that; `recordingReconnectWindowSeconds` lets a new stream after interruption record to the same S3 prefix — [AWS M&E blog on live input interruptions](https://aws.amazon.com/blogs/media/optimizing-amazon-ivs-live-to-vod-with-live-input-interruptions)
- AWS docs do not state a playlist update cadence in the snippets I could see; AWS says to test with a short stream — [search result summary of IVS docs](https://docs.aws.amazon.com/ivs/latest/LowLatencyUserGuide/record-to-s3.html)
- Kick VOD retention (third-party, citing Kick help): 7 days non-verified, 30 days verified; also a VOD count cap (~16 regular / ~30 verified) that can delete VODs before time expiry; deleted VODs are unrecoverable; disconnect/reconnect can split a session into multiple VODs — [Stream-Rise](https://stream-rise.com/blog/how-long-do-kick-vods-last); [AutoClip comparison](https://autoclip.dev/blog/kick-vs-twitch-vod-availability-for-clippers); [Upstream](https://upstream.so/blog/streamer-news-october-30-november-6-2026/)
- yt-dlp issue #13442: Kick extractor returned HTTP 403 on the API JSON for sub-only VODs; fixed June 30, 2025 via PR #13550 "[ie/kick] Support subscriber-only content"; issue locked Feb 2026 — [yt-dlp #13442](https://github.com/yt-dlp/yt-dlp/issues/13442)
- yt-dlp FAQ points Cloudflare-related 403s to cookies (`--cookies-from-browser`) — [yt-dlp FAQ mirror](https://lab.trianta.dev/mirrors/yt-dlp.yt-dlp/wiki/FAQ)
- Streamlink 7.5.0 (2025-07-08): "kick: fixed 403 API responses by solving the JS challenge using the webbrowser API"; 8.1.1 (2026-01-17) added `--kick-low-latency`; 8.2.0 (2026-02-09) latest I saw — [Streamlink changelog](https://streamlink.github.io/changelog.html); [Debian changelog](https://sources.debian.org/src/streamlink/8.2.0-1/CHANGELOG.md)
- Streamlink's webbrowser-API challenge solving needs a Chrome/Chromium on the machine (from my knowledge of Streamlink's design; not verified in this session) — flag.
- A third-party Kick plugin relies on cloudscraper to reach Kick's Cloudflare-protected API, showing Cloudflare challenges on the API are a known obstacle — [nonvegan/streamlink-plugin-kick](https://www.github.com/nonvegan/streamlink-plugin-kick)

### Inferences
- If your repo's playlists carry `#EXT-X-PLAYLIST-TYPE:EVENT` and lack `#EXT-X-ENDLIST` while live, that is consistent with a growing playlist (EVENT type = append-only until ended) — this is HLS-spec reasoning, not a Kick statement. Test: during a real stream, fetch the VOD `source` twice 60s apart and diff segment counts; check for ENDLIST.
- Delay behind live is unknown. Expect at least one segment duration (~10s) plus S3/IVS write latency; the pipeline should tolerate minutes, and measure it.
- With a 48h stream, a drop/reconnect can create several VODs; the poller should enumerate ALL VODs from the videos list created after stream start, key state by VOD id, and handle a new VOD starting mid-event. A 48h single recording is plausible only if no interruption; whether Kick caps VOD length is unknown.
- VOD expiry (>=7 days) is irrelevant to live operation but matters for any post-event rerender: 1080p ranges for all clips must be fetched/rendered within days, or the 1080p source is lost.
- Segment fetching through stream.kick.com (CDN) appears separate from the kick.com API Cloudflare gate; the 403 risk is mostly on the JSON endpoints. Unverified.

### Gaps
- No direct confirmation that the in-progress VOD's playlist is readable/updated mid-stream, nor its lag. Must be tested on a live stream (do this in the pre-event test).
- Kick's own help page on VOD length limits/splitting not read.
- docs.aws.amazon.com blocked: exact IVS wording on playlist availability during recording not read in full.

## 2. Kick official public API (api.kick.com / docs.kick.com), webhooks, chat

### Takeaway
An official Public API exists with OAuth-based access, a `GET /livestreams` endpoint, and webhook events (including livestream metadata/status and chat events), but it is app/token-authenticated, has no confirmed unauthenticated read, and does not expose the VOD list or HLS URLs, so it can replace the live-status poll but not the VOD fetch. Chat read is still commonly done via an unofficial Pusher websocket.

### Cited Findings
- Public API changelog: `GET /livestreams` (Apr 2025; multiple `broadcaster_user_id` Jul 2025; `custom_tags` Nov 2025), `GET /channels` (slug lookup), `GET /categories/:id`, moderation endpoints, chat reply endpoint, `DELETE /chat/:message_id` (Dec 2025); webhook events include livestream metadata, moderation banned, `kicks.gifted`, subscriptions; refresh tokens reusable/flexible (Nov 2025). Changelog has no 2026 entries — [KickEngineering/KickDevDocs](https://github.com/KickEngineering/KickDevDocs)
- Chat payload additions: `created_at`, `replies_to`, sender `identity` — same source above
- Rate limits are not documented in the repo README — same source
- Event name `livestream.status.updated` is used by developers; one KickDevDocs discussion reports its webhook not firing — [KickDevDocs discussion #147 (mirror)](https://github.qingwei-s.workers.dev/KickEngineering/KickDevDocs/discussions/147)
- Webhook behaviour per a third-party guide: 3 retries then auto-unsubscribe; dedupe on message-id header — [Streamer.bot Kick guide](https://docs.streamer.bot/guide/platforms/kick) and search result (secondary; unverified)
- Webhooks require a publicly reachable HTTPS endpoint; unofficial chat: Pusher websocket keyed by `chatroom.id` obtained from `https://kick.com/api/v2/channels/{slug}`, no auth for read, app key/event names scraped from web client and can change; payload double-JSON-encoded — [kick-api (Rust) live_chat.rs](https://docs.rs/kick-api/0.1.9/src/kick_api/live_chat.rs.html); also [chatmux Go](https://pkg.go.dev/github.com/andreas-bylund/chatmux/kick), [kichat.js](https://socket.dev/npm/package/kichat.js), [KickLib C#](https://www.nuget.org/packages/KickLib)

### Inferences
- Webhooks need an always-on public receiver; a GitHub Actions job can't receive them. A free Cloudflare Worker could receive them and fire `workflow_dispatch` (see section 5) — design option, unverified for Kick's webhook IP/signature requirements.
- Official API (app token, client-credentials flow, from my knowledge: OAuth 2.1) could poll `/livestreams` as a second, legit, Cloudflare-friendly liveness signal. Needs a free Kick developer app; credentials as repo secrets. Auth details not verified here.
- Chat spikes are the best clip-detection signal, but a 6h-capped Actions job holding a websocket is a ToS-grey, fragile path; treat chat as optional enrichment, with transcript-based detection as primary.

### Gaps
- docs.kick.com blocked: current endpoints/scopes/rate limits for 2026 not read; whether `/livestreams` works without a user token not confirmed. No official VOD endpoint found.

## 3. Cloudflare behaviour for kick.com from GitHub Actions IPs

### Takeaway
Kick sits behind Cloudflare; 403s on the API JSON are documented across tools (yt-dlp, streamlink) and fixed by upstream from time to time. For your use only legitimate mitigations: low request rate, retries with exponential backoff, graceful degradation, official API where possible.

### Cited Findings
- yt-dlp Kick API 403 on JSON download (sub-only case) — [yt-dlp #13442](https://github.com/yt-dlp/yt-dlp/issues/13442)
- Streamlink treated Kick 403s as a JS-challenge problem (7.5.0) — [Streamlink changelog](https://streamlink.github.io/changelog.html)
- Kick plugin author notes Cloudflare-protected public API — [streamlink-plugin-kick](https://www.github.com/nonvegan/streamlink-plugin-kick)
- No source found specifically reporting GitHub-runner-IP blocks of kick.com in 2026.

### Inferences
- Mitigations (all legitimate): 10-min polling is low-rate; add jitter; on 403 back off (e.g. 2, 4, 8 min), keep last-known state, alert (Actions failure notification / issue), and continue from state; reduce calls (one videos call per run, live-status call only if needed — the videos list alone reveals a growing newest VOD); cache ETag if returned. Use the official API for liveness as a fallback signal. Do not use cloudscraper-style challenge solving or proxy rotation: that is evasion and carries Kick ToS risk (Kick ToS not read — flag).
- Runner IPs vary per run, so 403s may be intermittent; a retry in-run after 30-60s is reasonable.

### Gaps
- Kick's ToS on automated access and VOD downloading not read; flag as a risk. No data on 403 frequency from Azure/GitHub IPs.

## 4. GitHub Actions in 2026: limits, reliability, ToS

### Takeaway
Public repos get free standard-runner minutes; jobs cap at 6h; scheduled runs can be delayed or dropped under load (especially at top of hour), so 10-min cron is best-effort, not a guarantee. Actions terms ban serverless-style/disproportionate use; a stream-recorder-like repo is a ToS grey area. Keep compute proportional and the output (clips) the core purpose.

### Cited Findings
- Standard GitHub-hosted runner usage is free in public repos; 6-hour job limit; 20 concurrent jobs on Free plan — [GitHub Actions limits docs (search snippet)](https://docs.github.com/en/actions/reference/actions-limits); [billing docs](https://docs.github.com/en/actions/reference/usage-limits-billing-and-administration)
- Scheduled events can be delayed in high load (start of every hour is high load); queued jobs may be dropped; run at an off-peak minute — GitHub docs as summarised in search; delays anecdotal 5-30 min+, sometimes hours; shortest interval 5 min — [community discussion #185355](https://github.com/orgs/community/discussions/185355); [runhooks](https://runhooks.app/blog/github-actions-scheduled-workflows-unreliable/); [crontap cron drift](https://crontap.com/blog/github-actions-cron-drift-problem)
- Runner specs: only a third-party guide says public repos get 4 vCPU/16 GB, private 2 vCPU/8 GB, 14 GB SSD — [open-exam-prep](https://open-exam-prep.com/study-guides/github-actions/runner-infrastructure-and-management/ch07-sec01-github-hosted-runners); same guide's "15-minute timeout" claim conflicts with the 6h doc and is unreliable
- GitHub Additional Product Terms: Actions must not be used in ways that burden servers disproportionately; CDN and serverless use are named as prohibited examples; consequences: job termination, restriction of Actions, repo disabling — [GitHub Terms for Additional Products](https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features)
- Account-ban example for free-hosting abuse of Actions (Tor) — [devactivity](https://devactivity.com/insights/github-actions-and-tor-why-free-hosting-attempts-lead-to-account-bans) (secondary)

### Inferences (from my own knowledge unless noted; UNVERIFIED this session)
- 60-day inactivity disabling of scheduled workflows in public repos: I recall it exists (GitHub docs); the state-commit each run counts as repo activity? Not guaranteed — commits made by GITHUB_TOKEN may not count as activity; test, or keep a human commit/ping. Flag.
- Commits/pushes made with GITHUB_TOKEN do not trigger new workflow runs, but `workflow_dispatch` and `repository_dispatch` calls via GITHUB_TOKEN are an explicit exception (documented in my recollection): a job can re-dispatch itself near the 6h limit. Verify in test. Also GITHUB_TOKEN needs `actions: write` permission.
- Concurrency groups: `concurrency: {group: poll, cancel-in-progress: false}` keeps one run, queueing at most one pending (older pending ones are cancelled) — from my knowledge; verify.
- Public runner free disk: expect roughly 14 GB on /mnt plus ~20+ GB on root; delete preinstalled toolchains if more needed; stream segments through disk, never hold the full range (1 h of 1080p60 is ~5 GB). Unverified.
- Artifacts: free storage quota is small; artifacts mainly for hand-off between jobs with short retention; do not rely on them for large media. Exact current limits not verified.
- Git repo growth: each state commit adds history; transcripts are small text, fine; never commit media. Prefer a single state file overwritten, or an orphan `state` branch force-pushed/squashed periodically; keep rebase-retry on push conflict.
- ToS posture: clips are derivative content; operate on the channel owner's own content with the owner's consent (state in README), modest runner use, no redistribution of raw streams. The 1080p rendering for up to 48h is the heaviest use; keep per-run work bounded. Risk is moderate, not zero.

### Gaps
- docs.github.com blocked: exact 2026 numbers (minutes for private repos, artifact retention/storage, runner disk) not verified. No found cases of enforcement against stream-recorder repos (absence of evidence, not evidence of safety).

## 5. Free fallbacks for an always-on worker/trigger

### Takeaway
Best zero-cost reliability gain: an external trigger (Cloudflare Worker cron or cron-job.org) calling `workflow_dispatch` so the schedule does not depend on GitHub's cron. Free VMs (Oracle, GCP) are possible but usually need a card and have caveats.

### Cited Findings
- Oracle Always Free: idle instances may be reclaimed if over 7 days the 95th percentile CPU is <20% — [Oracle Always Free docs](https://docs.oracle.com/iaas/Content/FreeTier/resourceref.htm); a 2026 blog claims the free allocation was reduced (2 OCPU/12 GB) while another says 4 OCPU/24 GB — conflicting, check current Oracle page — [braindetox](https://braindetox.kr/en/posts/oracle_always_free_tier_reduced_2026.html)
- GCP e2-micro: one instance free only in us-west1/us-central1/us-east1, 0.25 vCPU (shared)/1 GB, 30 GB disk — [agentdeals GCP free tier 2026](https://agentdeals.dev/gcp-free-tier-2026) (secondary)
- Cloudflare Workers free tier: ~100k requests/day (secondary); cron-trigger limits not confirmed — [publicapis.dev](https://publicapis.dev/blog/free-api-hosting)

### Inferences (my knowledge, unverified)
- Oracle and GCP require a credit/debit card for sign-up (card verification), which conflicts with "zero budget/no card" unless owner has one; GCP free tier needs billing account. 0.25 vCPU cannot render 1080p60; use only as orchestrator.
- Cloudflare Workers: free plan includes Cron Triggers, no card needed; a Worker can POST to `https://api.github.com/repos/OWNER/REPO/actions/workflows/ID/dispatches` with a fine-grained PAT (Actions: write) stored as a Worker secret. cron-job.org (free, no card, as I recall) can do the same HTTP POST with Authorization header. Kaggle notebooks (free, phone-verification, session limits ~9-12h, GPU) are possible renderers but ToS unclear; not recommended as primary. Verify each before relying on them.
- Run two independent triggers (GitHub cron + external dispatch) and a concurrency group so duplicates collapse.

### Gaps
- Card requirements, Cloudflare cron limits, cron-job.org and Kaggle terms not verified from primary sources.

## 6. Download/render planning

### Takeaway
No benchmarks sourced; use estimates and measure. 1080p60 at the stated 4.4-5.2 GB/h is ~10-12 Mbps, so a 2-5 minute clip source (~80-200 MB) downloads in seconds on a datacenter link.

### Cited Findings
- Source bitrate from the brief: 4.4-5.2 GB/hour — owner's figure; arithmetic: 4.4-5.2 GB/h ≈ 9.8-11.6 Mbps.
- No source found for GitHub runner network speed or x264 render time on 4 vCPU.

### Inferences (estimates; verify in test)
- Runners typically sustain hundreds of Mbps from CDNs (my experience; unverified). A 60s clip = ~80 MB.
- x264 1080p60 on 4 vCPU at `-preset veryfast`/`fast`, CRF ~20-23: roughly 1-2x realtime on 4 cores (so a 60s clip renders in ~30-90 s); `medium` ~0.5x. Re-encoding is needed for overlays/captions; use stream copy + cut at keyframes only for plain cuts. Cut points should align with ~10s segments, or trim with `-ss` after concatenation and re-encode just the clip.
- Budget: 20 clips x ~2 min wall each fits well within a single 6h job; keep per-job timeout 45-60 min.
- YouTube upload via Data API: default quota 10,000 units/day, ~1,600 units per upload (my recollection; ~6 uploads/day unless quota increase approved; unverified) — a major bottleneck for "many clips"; check before the event. Unaudited API projects may force uploads private; verify.

### Gaps
- All performance numbers untested.

## 7. Recommended architecture, runbook, pre-event test plan

### Takeaway
Use a staged, state-driven pipeline with idempotent jobs keyed by VOD id and segment index, an external trigger for resilience, and clip render/upload jobs dispatched per-candidate rather than long-lived.

### Cited Findings
- (Design draws on the facts above: 6h cap, drop/delay of cron, concurrency, workflow_dispatch exception, Kick 403 reports.) See sections 1-6 for sources.

### Inferences (recommended design)
Architecture
1. Trigger layer: GitHub cron (offset minutes, e.g. `3,13,23,...`, not top of hour) PLUS Cloudflare Worker cron or cron-job.org dispatching the same workflow every ~5 min. Concurrency group `poll` with `cancel-in-progress: false`.
2. Poll job (short): fetch videos list; for each VOD created since event start, fetch master+160p playlist, diff segments vs `state.json`, download new 160p segments, extract audio, transcribe via Groq (watch Groq free rate limits - not researched), append transcripts, commit. Backoff on 403; never fail loudly into data loss.
3. Detect job: score windows from transcripts (keywords, laughter, density) and optional chat; produce candidate list `candidates/*.json` with VOD id + start/end segment indices + padding.
4. Clip job (workflow_dispatch per batch, matrix limited to 1-2): download only needed 1080p60 segments from the VOD playlist (re-fetch the playlist for correct URIs), concat, ffmpeg render, upload to YouTube (resumable), record result in state, delete local files. Human-in-loop optional: draft/unlisted first.
5. State: small JSON on a dedicated `state` branch or committed file; rebase-retry on push; periodic squash. No media in git.
6. Watchdog: a scheduled job that opens/updates a GitHub issue if no poll succeeded in 30 min or 403 streak > N (issue notifications reach owner email/mobile).
7. Optional: if the VOD playlist turns out to be not readable mid-stream, fall back to streamlink live capture inside a 5h45m job that self-redispatches (Chrome needed for challenge solving; ToS/Cloudflare risk; ~10 Mbps stream recorded to short segments uploaded as artifacts or processed in-place). Weigh against GitHub's "disproportionate burden" clause.

Runbook
- T-7d: do the test plan; set secrets (Groq, YouTube OAuth refresh token, dispatch PAT); confirm repo has recent commits (60-day rule); pin tool versions; enable failure notifications.
- Before start: verify channel live and newest VOD growing; run manual dispatch; check both triggers fire.
- During (every few hours): glance at the issue/watchdog, YouTube quota, repo size, Actions minutes page.
- On 403 streak: don't raise polling frequency; wait; use the official API liveness signal; consider manual intervention.
- On VOD split/new VOD id: confirm state picked it up.
- After: render remaining clips within days (VOD expiry 7/30 days), then disable the schedules.

Pre-event test plan (Nov 14-18)
1. During any live stream (the owner's or a test stream by the owner): record segment count of newest VOD at T, T+60s, T+300s; check ENDLIST absence and lag vs live clock; check playlist type and whether the 1080p playlist is also growing.
2. Stop and restart the stream (simulate a disconnect) and note whether a new VOD id appears or the same VOD continues.
3. Run the poll from Actions 100+ times over 24h with logging of HTTP codes; compute 403 rate; test backoff.
4. Measure cron lateness for GitHub schedule vs the external trigger; confirm duplicates collapse.
5. Download 1080p range speeds; render a 60s test clip with x264 (preset veryfast/fast) on the runner; measure time and disk; confirm 14 GB disk suffices.
6. YouTube upload test of 3 clips; check quota counters and visibility restrictions.
7. Test `workflow_dispatch` via GITHUB_TOKEN from inside a workflow (self-redispatch) and push-conflict recovery.
8. Dry-run a 6h-boundary handoff and a state.json corruption restore.

### Gaps
- Groq free-tier limits for ~48h of audio not researched; YouTube quota not verified; exact runner specs and GitHub terms text not read directly (network allowlist). Recommend re-fetching docs.github.com, docs.aws.amazon.com, docs.kick.com once allowed.

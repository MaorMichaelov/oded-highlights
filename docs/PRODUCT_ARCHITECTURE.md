# Product architecture (Studio MVP skeleton)

Status 17 Nov 2026. Code: `app/studio.js` (API, imported by `app/worker.js`), `app/studio.html` (functional page, no design), `app/studio.test.mjs` (22 local test groups, `node app/studio.test.mjs`).
Not deployed. Business side: `docs/PRODUCT_PLAN.md`.

## 1. Overview

```
 Customer browser                Cloudflare Worker (app/worker.js + studio.js)               Render server (private)
 /studio  ──────────────────▶   /studio/api/*   sessions, orgs, channels, jobs, assistant      loop: claim -> render -> report
                                 KV (now) -> D1 (target)                                   ◀── POST /studio/worker/claim
 YouTube (Google OAuth) ◀──────  token vault (encrypted refresh tokens)  ──────────────────▶   private upload (videos.insert, privacyStatus=private)
 Kick / Twitch  ──webhook/poll─▶ detector -> creates jobs ("auto" source)                       ffmpeg, ASR (ivrit whisper), LLM moment picking, QA
```

* The owner app (`/`, `/api/*`, password `x-pass`) is untouched. `worker.js` only gets two lines: the import and `if (p startsWith "/studio") return handleStudio(...)`, placed BEFORE the owner auth.
* All studio KV keys start with `studio:`; the owner's keys (`pw`, `salt`, `gh`, `subs`, `vapid`...) are never read or written (checked by a test).
* The Worker never renders anything. It is the control plane: accounts, ownership proof, queue, state, approvals. The render server is a separate, replaceable process that only makes outbound HTTPS calls (no open ports).

## 2. UX principles (owner request: easy and fun)

1. **Three steps to first value:** paste channel link -> put a code in the bio (checked automatically every 8 s) -> connect YouTube. Then the home screen. One input field (`kick.com/name` or `twitch.tv/name`; platform and slug are parsed, no dropdowns).
2. **One button sign-in:** "Continue" tries login and falls back to signup (email + password, nothing else).
3. **One signature style:** no style picker in the UI. `style_id` stays on the channel (default `signature`) and `GET /styles` can list more, so adding styles later needs no migration.
4. **Approve/reject is the main action:** each draft is a card; swipe right = approve, left = reject (or arrow keys, or two buttons). Decisions are per draft; when every draft has a decision the job closes.
5. **Progress is spoken, not a spinner:** the worker reports a message key (`found_moments` with `n=5` -> "Found 5 moments, cutting...") and the page shows it in the browser language (he/en) with a progress bar. Catalogue: `MSG` in `app/studio.js`.
6. **Ask in plain language:** a chat box ("make 5 funny Shorts from yesterday") creates the job; chips give ready-made requests. Undo is "Cancel while queued" with automatic credit refund, not a confirmation dialog.
7. **Errors are friendly and bilingual** (`he`/`en` fields in error bodies where the user can act). Failures refund credits and say so.
8. **Nothing goes public by itself:** drafts are private; "approve" is the explicit consent YouTube's developer policy requires before changing visibility.
9. Short texts, Hebrew first (RTL) with English fallback by `navigator.language`. No visual design work was done (owner decision).

## 3. Data model

Now stored in KV (JSON values). KV has no transactions or queries, so the columns marked `*` need D1 before real customers (see section 8).

| Entity | KV key | Fields |
|---|---|---|
| user | `studio:u:<uid>` + email index `studio:e:<email>` | id, email, name, pw{salt, iter, hash} (PBKDF2-SHA256 100k), created |
| session | `studio:s:<sha256(token)>` (TTL 30 d) | uid, exp. Token is returned once, sent as `Authorization: Bearer` |
| org (team/workspace) | `studio:o:<oid>` | id, name, owner, plan (`trial`/`none`/...), credits*, created |
| membership | `studio:m:<oid>:<uid>` + reverse `studio:uo:<uid>:<oid>` | uid, email, role (`owner`/`editor`/`viewer`), added |
| invite | `studio:i:<sha256(token)>` + `studio:io:<oid>:<hash>` (TTL 7 d) | id, org, email, role (`editor`/`viewer`), exp, by |
| channel | `studio:c:<oid>:<cid>` | platform (`kick`/`twitch`), slug, status (`pending`/`verified`), verify_code, verify_expires, verified_at, verified_via (`bio`/`stream_title`), platform_user_id, linked_youtube, style_id, yt{status}, created |
| channel claim | `studio:claim:<platform>:<slug>` -> oid | one verified owner org per channel* |
| job | `studio:j:<jid>` + org index `studio:oj:<oid>:<jid>` | id, org, channel, kind (`edit`), source{type `vod`/`live`/`url`/`auto`, ref, when, duration_min}, style_id, outputs{shorts, long}, hints{mood, text}, status, status_text{he,en}, progress, credits_held, result{drafts[]}, events[] |
| draft (inside job) | `job.result.drafts[i]` | kind (`short`/`long`), title, yt_video_id, qa_ok, qa_notes, private:true, decision (`null`/`approved`/`rejected`) |
| queue | `studio:q:<iso time>:<jid>` | claimed (and deleted) by the worker* |
| assistant history | `studio:chat:<oid>` | last 40 messages |
| config | `studio:cfg:worker_key`, `studio:cfg:twitch` ({id,secret}) | secrets set by the owner (never in the repo) |

Roles (`PERMS` in studio.js): **owner** everything (team, billing, channels, YouTube connect); **editor** create jobs, approve/reject, set style; **viewer** read only. Other orgs answer 404 (not 403) so their existence is not revealed.

Job status machine (`JOB_FLOW`): `queued -> running -> qa -> draft_ready -> approved | rejected`; `failed` (from running/qa); `cancelled` (from queued/running). Credits are held at creation, refunded on cancel/fail.

Target SQL (D1) in short: `users, orgs, memberships, invites, channels(unique platform+slug where verified), youtube_tokens(org, channel, enc_refresh_token, scopes, revoked_at), jobs, drafts, credit_ledger(org, delta, reason, job_id, ts), webhook_events(id unique)`. The credit balance is the sum of the ledger, written in the same transaction as the job insert.

## 4. API (all JSON; `Authorization: Bearer <token>` unless public)

Public: `GET /studio` (page), `GET /studio/api/health`, `POST /studio/api/signup`, `POST /studio/api/login`, `POST /studio/api/invites/preview`.
Rate limited per IP (signup 10/h, login 20/h, verify 30/h per channel, assistant 60/h per org; KV counters, best effort).

Session: `GET /me`, `POST /logout`, `GET /styles` ({default:"signature", styles[]}; reads `config/styles/*.json` from GitHub, cached 10 min, falls back to the built-in style), `POST /invites/accept`, `POST /orgs` (extra workspace, e.g. an editor with several clients).

Org (`/studio/api/orgs/:oid...`, role in brackets):
* `GET ""` org info + my role.
* Team: `GET /members` [view], `POST /invites` {email, role} [owner] -> `accept_url` (`TODO(email)`: no email sent yet), `DELETE /invites/:id`, `PATCH|DELETE /members/:uid` [owner].
* Channels: `GET /channels`, `POST /channels` {url | platform+slug} [owner] -> code + instructions, `POST /channels/:cid/verify` [owner] (reads the public Kick bio/stream title or Twitch description/stream title and looks for the code; 48 h expiry; one verified owner per channel), `DELETE /channels/:cid`, `POST /channels/:cid/style` {style_id} [editor] (unused by the UI), `POST /channels/:cid/youtube` [owner] -> **501 TODO(youtube-oauth)**.
* Jobs: `GET /jobs`, `POST /jobs` {channel_id, source{type, ref, when, duration_min}, shorts, long} [editor] (channel must be verified, credits checked -> 402), `GET /jobs/:jid`, `POST /jobs/:jid/drafts/:i/approve|reject` [editor] (job must be `draft_ready`), `POST /jobs/:jid/approve|reject` (bulk: every undecided draft), `POST /jobs/:jid/cancel`.
* Assistant: `GET /assistant` (history + hint), `POST /assistant` {message, channel_id?} -> {reply, actions[], parsed}. See section 6.
* Billing: `GET /billing` (plan, credits), `POST /billing/checkout` -> **501 TODO(payment)**.

Render worker (header `x-worker-key`, secret in KV `studio:cfg:worker_key`): `POST /studio/worker/claim` -> {job|null}; `POST /studio/worker/jobs/:jid` {status?: qa|draft_ready|failed, progress?, msg?+vars? (key from `MSG`) or message?, drafts?[], error?}.

## 5. Job flow

```
 trigger                      queue                 render worker                                   customer
 ───────                      ─────                 ─────────────                                   ────────
 (a) Kick webhook             studio:q:<t>:<jid>    claim -> status running ("Getting started")
     livestream.status        (status queued,       1 resolve source (VOD url / live buffer / "auto": find the stream by date)
     .updated is_live=false   credits held)         2 download (msg downloading)
 (b) poll (Twitch EventSub    ───────────────▶      3 ASR (ivrit whisper) (msg transcribing pct)
     stream.offline / cron)                         4 pick moments (LLM) (msg found_moments n)
 (c) user clicks "new job"                          5 cut + edit in the signature style (msg rendering i/n)
 (d) assistant chat message                         6 QA gates (status qa): sync, loudness, caption overflow, black frames
                                                    7 upload PRIVATE drafts (videos.insert privacyStatus=private, ALWAYS explicit) + thumbnails.set
                                                    8 report drafts[] + status draft_ready ─────────────▶ cards appear (swipe)
                                                                                                          approve -> (TODO) videos.update visibility
                                                    failed -> credits refunded, message "Something went wrong. Your credit is back."
```

Triggers (a)-(b) create jobs with `source.type = "auto"` and `when = "last_stream"`, the worker resolves the stream. Idempotency: the detector keys jobs by `platform:slug:stream_started_at` so a re-sent webhook does not create a second job (TODO, needs D1 unique index).

Kick detection: official webhooks (`livestream.status.updated`, fields is_live, started_at, ended_at; needs Kick OAuth with `events:subscribe`) instead of polling. Twitch: EventSub `stream.online/offline`. Both need the customer to authorise our app once; until then polling the public channel page is the fallback.

Never: the worker never calls `videos.insert` without a customer's stored consent and never with `public`/`unlisted`. Visibility changes only after an explicit approve click.

## 6. Assistant chat API

`POST /studio/api/orgs/:oid/assistant` body `{ "message": "make 5 funny Shorts from yesterday", "channel_id": "c_..." }` (channel optional: the first verified one is used).

1. `understand(text)` (rule based, Hebrew + English, deterministic, unit tested) extracts: `intent` (`create` | `status` | `help`), `shorts` (digits or number words, default 5, max 30), `long` (asks for a long/full video), `when` (`yesterday` | `last_stream` | `week`), `mood` (`funny`, `hype`, `fail`).
2. `create`: checks role (viewers get an explanation), a verified channel (else tells the user to connect one), credits (else says how many are missing), then creates a job (`source {type:"auto", when}`, `hints {mood, text}`) and answers in the user's language, e.g. "On it! Making 5 funny Shorts from yesterday's stream. I'll update you here when drafts are ready. You can cancel while it's queued."
3. `status`: answers with the latest job's `status_text` and percent.
4. Response: `{ reply, actions: [{type:"job_created"|"show_job", job_id}], parsed }`. The page refreshes on actions and shows the history (`GET /assistant`).
5. `TODO(LLM)`: replace the rules with a small model (Workers AI `env.AI` is already bound, or a Haiku-class API at about $0.10/$0.50 per M tokens) that returns the same JSON shape (intent, counts, when, mood) so the rest is unchanged; keep the rules as fallback. Extra intents worth adding: "redo the 3rd draft shorter", "change the title", "pause auto mode".
6. The worker receives `hints.text` and `hints.mood` and should use them as extra instructions in the moment-picking prompt.

## 7. Security and compliance notes in the skeleton

* Passwords: PBKDF2-SHA256, 100000 iterations (Workers WebCrypto maximum), per-user salt, constant-time compare, equalised timing for unknown emails. Sessions: random 256-bit tokens, only the SHA-256 is stored.
* No secret in the repo. Worker key and Twitch app credentials live in KV (`studio:cfg:*`) or Worker env (`STUDIO_WORKER_KEY`, `STUDIO_TWITCH_ID/SECRET`). Set with the Cloudflare KV API, e.g. `PUT /accounts/<acct>/storage/kv/namespaces/<ns>/values/studio:cfg:worker_key` with the token the deploy script already uses.
* YouTube refresh tokens (when built) must be stored AES-GCM encrypted with a Worker secret, deleted within 7 days of revocation or account deletion, and every stored YouTube-derived datum re-checked/refreshed every 30 days (YouTube Developer Policies III.E).
* Ownership proof is a code in the public bio/description or stream title. Weakness: a bio can be edited by whoever controls the channel only, so this is a proof of control, which is the intended one. Better and planned: Kick OAuth (`user:read`, never `channel:read` because it returns the stream key) and Twitch OIDC login as the primary proof.
* `fetchChannelPublic` uses `kick.com/api/v2/...`, an undocumented endpoint, from a Cloudflare Worker. Kick may block it. **Untested from a Worker** (tested only the response shape with curl from the sandbox). Fallback: run the same fetch from the render server or a GitHub Actions job and post the result to a worker endpoint (not built). Kick's Terms (section 1.4) forbid automated access, so move to the official API (OAuth) soon.

## 8. What is NOT built (TODO markers are in the code)

`TODO(youtube-oauth)` Google OAuth connect + callback + encrypted token store + token refresh for the worker. `TODO(payment)` checkout, webhook, plans, credit top-ups. `TODO(email)` invite and notification emails. `TODO(D1)` atomic credits/queue/claims (KV is eventually consistent: two workers could claim one job, two parallel requests could overspend credits). `TODO(ingest)` webhook receivers and pollers that create jobs, "live" and "url" source validation (the VOD must belong to the verified channel). `TODO(worker)` the render server itself (section 9). `TODO(LLM)` assistant. `TODO(preview)` embed the draft for review. Note: the free Workers KV plan allows only 1,000 writes/day and 100,000 reads/day (Cloudflare KV pricing page), a few dozen jobs would exhaust it: the Workers Paid plan (5 USD/month) or D1 is required for any real use. Also: account deletion, password reset, email verification before trial credits, admin/support view, audit log, terms/privacy/DMCA pages, usage limits per org.

## 9. Moving rendering off GitHub Actions to a private server

Why: GitHub's Additional Product Terms forbid using Actions for "the provision of a stand-alone or integrated application or service offering the Actions product ... for commercial purposes", and for hosted runners any activity unrelated to the repository's software project; running customers' jobs there is at best grey, and a public repo cannot stay public if the code must be private. Details in `docs/PRODUCT_PLAN.md`.

What depends on Actions today (from the repo): ~24 workflows, state kept as committed files (`state/...`, git is the database and the queue), `live-loop` (self re-dispatching 5 h 40 m loop, restarted by the Worker watchdog every 5 min through the GitHub API), `render-clip` (`workflow_dispatch` with `clip_id`, `state_dir`, `yt`), secrets in GitHub secrets, ASR model cache via `actions/cache`.

Target:

1. **Worker daemon** `scripts/render_worker.py` (BUILT 18 Nov: see `docs/DEPLOY_PRIVATE_SERVER.md`, `docs/INGEST.md`; pipeline in `scripts/job_runner.py`, sources in `scripts/worker_sources.py`): loop `claim -> run -> report`. Claim = `POST /studio/worker/claim`; for each job create a scratch dir `/work/<jid>/` and run the existing stages as subprocesses with env instead of workflow inputs: `STATE_DIR=/work/<jid>/state`, `CLIP_ID`, `STYLE=<style_id>`, source from `job.source`. Report progress with `POST /studio/worker/jobs/<jid>` (the stage scripts print `PROGRESS <pct> <msg-key> k=v` lines which the daemon forwards). Delete scratch on success, keep on failure for 24 h.
2. **Replace git-as-database:** per-job files live in the scratch dir and a small result JSON goes back to the API; long-term artefacts (drafts are already on YouTube) are not stored. The owner's own channel keeps working through the same daemon as "org 0" (its jobs created by the detector), which lets the Actions workflows be retired.
3. **Packaging:** one Dockerfile (ffmpeg, python deps from `scripts/requirements.txt`, fonts, the ivrit whisper model baked or on a volume, ~3 GB) + `systemd` unit (`Restart=always`). Concurrency = number of cores / 4 (each job is about 4 vCPU). Image is built on the server (private repo cloned with a read-only deploy key), no registry needed.
4. **Hosts, cheapest first** (details and prices in the plan): the owner's own PC (free, beta only), a Hetzner dedicated/cloud box (about 35-70 USD per month, fixed), serverless containers (Modal, Cloudflare Containers) for burst only because they cost 3-6x more per CPU hour at steady load.
5. **Detector** (cron on the same box, or a Cloudflare cron on the Worker): polls/receives Kick/Twitch events and calls an internal "create job" function with `source.type = "auto"`.
6. **Cutover plan:** (a) run the daemon next to Actions for the owner's channel with `UPLOAD_HOLD` still on, compare outputs; (b) move `live-loop` last (needs the box to be reliable for 24/7 polling), keep the Worker watchdog as the dead-man switch (alert when the daemon has not claimed for N minutes); (c) disable workflows; (d) make the repo private and rotate every secret that was ever in Actions.
7. **Ingest for customers** (decision needed): customer-side restream to our SRT/RTMP endpoint (ToS clean, no VOD expiry, also gives live buffer for fast Shorts) vs. VOD URL download with streamlink (what we do today; against Kick's terms 1.4 as written, Twitch has no download API) vs. customer file/YouTube-link upload as the always-available fallback.

Capacity rule of thumb (estimates, see plan): one stream hour needs about 0.6-0.7 hours of a 4-vCPU slot (ASR 0.4x real time on CPU + about 11 minutes of cut/edit/render/QA). A 12-thread dedicated server therefore handles roughly 3 slots, about 100 stream hours per day at best, about 13 heavy streamers (4 h/day) realistically.

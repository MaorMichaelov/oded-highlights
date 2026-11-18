# Studio bug log (E2E bug hunt)

How it is tested: `tests/studio_e2e/run.mjs` (Playwright + Chromium, mobile 390x844 / desktop 1280x800, Hebrew + English).
* Deployed app: GitHub Actions workflow `studio-e2e` (`gh workflow run studio-e2e.yml -f url=https://studio-app.odedhl.workers.dev`), report in `state/studio_e2e/report.json` + a few PNGs (overwritten each run), all PNGs as a run artifact.
  The part of the journey that needs a verified channel (jobs, review, team, settings...) needs the repository secret `STUDIO_WORKER_KEY` (see `scripts/setup_studio_worker.sh`); without it the run reports those steps as `skipped`.
* Locally, full journey against the REAL `studio.js` + `studio.html` with an in-memory KV and a fake Kick/Twitch: `node tests/studio_e2e/local_server.mjs 8787 &` then `BASE=http://localhost:8787 OUT=/tmp/e2e node tests/studio_e2e/run.mjs` (needs `playwright`; Chrome via `CHROME=/usr/bin/google-chrome`).
* The journey collects: console errors, uncaught exceptions, failed requests, unexpected 4xx/5xx, horizontal overflow, clipped/offscreen/overlapping/covered controls, untranslated or wrong-language text, i18n keys leaking into the UI, `html lang/dir`, infinite spinners, and functional assertions per step.

## Fixed

| # | Bug | Where | Regression test |
|---|-----|-------|-----------------|
| 1 | Channel/job/member/invite/workspace vanished for up to a minute after creation (KV `list()` is eventually consistent): after "Add channel" a reload sent the wizard back to step 1, a new workspace or invite was "missing". Measured on the deployed app (`GET /channels` -> `[]` one second after the POST). | studio.js: index documents + `klist()` union, `kput`/`kdel`; studio.html: 90 s "fresh" merge | `lagging KV list()` |
| 2 | The wizard showed an arbitrary pending channel when there were several (first by random id). It now shows the newest. | studio.html | e2e |
| 3 | Verification message of a previous channel stayed on screen for the next channel. | studio.html | e2e |
| 4 | The 8 s auto-check hit the 30/hour verify rate limit after 4 minutes ("too many tries" for a user who just waits). Client backs off 8..30 s, server limit 200/h. | studio.html, studio.js | e2e |
| 5 | Guest limit 8/hour and signup 10/hour per IP: a school/office/demo room is locked out quickly. Now 30/20/60. | studio.js | - |
| 6 | Onboarding checklist never ticked "Connect YouTube" after "I'll do it later" (`yt || skip && ver && yt`). | studio.html | e2e |
| 7 | Invite link: the landing never showed "you were invited to X" and never prefilled the invited email (the preview was only fetched after login). A signed-in user opening an invite link saw an empty org name. | studio.html | e2e |
| 8 | After accepting an invite the user stayed in their own personal workspace instead of the one they joined. | studio.html | e2e |
| 9 | Pending invitations list did not refresh after creating an invite. | studio.html | e2e |
| 10 | Uncaught exception in "Approve all": `e.currentTarget` is null in the timeout. | studio.html | e2e (uncaught-exception collector) |
| 11 | Session expiry was silent (the user simply landed on the login page). Now a toast says "Please sign in again" and local state is cleared. | studio.html | e2e |
| 12 | Hebrew chip "3 רגעים מטורפים מהשבוע" was parsed as "latest stream" (only "שבוע שעבר" was understood) and the mood was lost (מטורף ends in a final-form pe, the plural מטורפים does not match). | studio.js `understand()` | studio.test.mjs |
| 13 | Any chat message with a number or "want/need/give" ("I need 3 things", "I want a pizza") created a job and held a credit. A request now needs a clip/video word. | studio.js `understand()` | studio.test.mjs |
| 14 | A re-sent `failed` from the worker could refund twice; refund now persists `credits_held = 0` first. | studio.js `refund()` | studio.test.mjs |
| 15 | Twitch verification returned "not configured" unless a Twitch app was set up: now falls back to Twitch's public web endpoint (same public bio/stream-title fields). | studio.js | studio.test.mjs |
| 16 | A new draft toast covered the approve/reject buttons while the user was already on the review screen. | studio.html | e2e screenshot |
| 17 | Event log showed raw status codes (`queued`, `running`) in Hebrew. | studio.html | e2e (latin-in-he) |
| 18 | Copy: chat told users to paste a channel link "above" (no such field), "Billing tab" (does not exist), "לצפיינים" typo, masculine singular Hebrew mixed with the plural UI. | studio.js | studio.test.mjs |
| 19 | A storage/runtime exception escaped as Cloudflare's raw error page; now JSON 500 `server_error` (UI shows the friendly message). | studio.js | studio.test.mjs |
| 20 | Kick/Twitch "blocked" answers (403/429) showed the generic "try again in a minute"; now explains that the code stays valid and "Check now" can be pressed again later. | studio.html | - |
| 22 | Per-request KV writes/lists burned the free-plan daily quota (~1000 writes and lists per day for the whole account): rate limiting is now in memory, `klist()` reads the index document instead of calling `list()` (legacy data is indexed on first sight), empty orgs do not re-list on every poll. | studio.js | `lagging KV list()` |
| 21 | Worker `claim` considered only the first 20 queue entries and deleted queue keys of jobs it then skipped; added `claim {job_id}` and e2e-flagged channels whose jobs the real render worker never takes. | studio.js | studio.test.mjs |

## Budget
Live E2E runs cost KV writes (see the header of `.github/workflows/studio-e2e.yml`); the default is two profiles. Use the local harness for everything else.

## Notes / known limits (not bugs of the preview)
* Kick: `kick.com/api/v2/channels/<slug>` answers from a Worker (checked on the deployed app: a missing code gives "code not visible yet", not an error). It is an undocumented endpoint; if Kick starts blocking Workers, the page already shows the manual "I put the code, check again" flow with a friendly explanation.
* The E2E hook `POST /studio/worker/e2e/verify` (worker key + guest-owned workspaces only) marks a test channel verified without the ownership check; such channels are flagged `e2e` and are invisible to normal `claim`.
* `login` and `signup` share one form (login first, signup on 401): every new sign-up shows one `401` in the browser console. Harmless, a dedicated "login or create" endpoint would remove it.
* Logout: Workers KV caches reads at the edge for up to 60 s, so a signed-out token can still be accepted for a short time (the E2E notes it).

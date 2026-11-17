# חיבור ערוץ היוטיוב של הלקוח / YouTube Connect

## תקציר לבעלים (עברית)

**מה בנוי.** כל לקוח לוחץ "חבר את ערוץ היוטיוב שלי", מאשר בחלון של גוגל, והמערכת שומרת (מוצפן) אישור קבוע לערוץ שלו. מרגע זה כל טיוטה שה-Render Worker מסיים עולה **אוטומטית לערוץ של הלקוח כ"פרטי"**, בלי שאף אחד מעתיק טוקנים. אפשר להפעיל לכל לקוח בנפרד מצב "פרסום אוטומטי / תזמון" עם מגבלות (כמה בכל יום, באילו שעות), וכל לקוח יכול לנתק בלחיצה (ביטול אצל גוגל + מחיקה אצלנו).
הקוד: `app/youtube_connect.js` (השרת), `scripts/yt_upload_customer.py` (ההעלאה), בדיקות ב-`app/youtube_connect.test.mjs` וב-`tests/test_yt_upload_customer.py`. **שום דבר לא חובר, לא פורס ולא הועלה ליוטיוב.** הכל נבדק רק מול גוגל מדומה.

**מה אתה צריך לעשות ידנית (פירוט מדויק בסעיף 3, בערך 30 דקות):**
1. פרויקט חדש ב-Google Cloud (לא הפרויקט של הערוץ שלך!) ← להפעיל YouTube Data API v3.
2. מסך הסכמה (OAuth consent screen): External, מצב Testing, להוסיף את המיילים של לקוחות הפיילוט כ-Test users.
3. ליצור OAuth Client מסוג Web application עם כתובת החזרה `https://<האפליקציה>/studio/yt/callback`.
4. להכניס ל-Cloudflare כ-Secrets (לא בצ'אט ולא ב-git): `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `STUDIO_ENC_KEY` (מפתח ההצפנה, נוצר ב-`openssl rand -base64 32`).
5. שני שינויים קטנים שלא עשיתי כי סוכנים אחרים עורכים את הקבצים: שורת hook אחת ב-`worker.js` ושורה ב-`deploy.py` שמעלה את הקובץ החדש (סעיף 10).
6. לפני לקוחות אמיתיים: להגיש אימות (Verification) לגוגל. זה דורש **דומיין משלך** (אי אפשר לאמת `workers.dev`), דף מדיניות פרטיות, וסרטון הדגמה (סעיף 5).

**הסיכונים העיקריים (תכל'ס):**
- **מצב Testing:** עד 100 משתמשי בדיקה, וה"אישור הקבוע" **פג אחרי 7 ימים** - הלקוח יצטרך לחבר מחדש כל שבוע. מתאים רק לפיילוט של כמה חברים. המערכת מזהה את זה ומציגה "צריך לחבר מחדש" (בלי להפיל כלום).
- **הפרויקט לא מאומת = כל סרטון ננעל כ"פרטי" ביוטיוב** (גם אם ביקשנו ציבורי/תזמון). לכן ברירת המחדל שלנו פרטי בכל מקרה, ופרסום אוטומטי/תזמון **נכבה אוטומטית** עד שמסמנים שהפרויקט עבר Audit (`YT_AUDIT_PASSED=1`). ה-Audit של "YouTube API Services" הוא תהליך נפרד מאימות ה-OAuth, ואין לו זמן מובטח (שבועות עד חודשים).
- **מכסה (Quota) - הצוואר בקבוק האמיתי:** המכסה שייכת לפרויקט שלך, לא ללקוח, ומשותפת לכל הלקוחות יחד. במודל הישן: 10,000 יחידות ליום ו-1,600 להעלאה = **כ-6 סרטונים ביום לכל המערכת**. לפי מקורות חדשים (לא אומתו מול גוגל, האתר שלה חסום מהסביבה שלי) מ-1 ביוני 2026 ההעלאות עברו ל"דלי" נפרד של ~100 העלאות ליום. **בדוק בקונסולה (IAM & Admin → Quotas) מה המספר אצלך** ועדכן ב-KV (סעיף 6). המערכת סופרת מכסה, מחלקת מכסה יומית לכל לקוח, ועוצרת בצורה נקייה כשנגמר. להגדלה מגישים "Quota Extension / API Compliance Audit" - חינם אבל איטי ולא מובטח.
- **ערוץ אחד, לקוח אחד:** אותו ערוץ יוטיוב לא יכול להיות מחובר לשני לקוחות (מונע חטיפה).

**החלטות שאני צריך ממך:** (א) דומיין - לקנות אחד (~$10 לשנה, חריגה מתקציב 0 רק ברגע האימות) או לחפש חינמי? (ב) פיילוט ב-Testing (7 ימים, עד 100) או לפרסם ל-Production לא מאומת (אין תפוגה של 7 ימים, אזהרה אדומה של גוגל, תקרה של 100 משתמשים לכל החיים של הפרויקט)? (ג) האם לבקש גם הרשאת `youtube.force-ssl` (רק אם רוצים ש"אישור הטיוטה" באפליקציה יפרסם אותה; אחרת לא צריך ומקטין סיכון באימות)? (ד) כמה העלאות ליום מותר ללקוח בתוכנית הבסיסית (ברירת מחדל 3).

---

# Details (English)

Status: module + script + tests built and passing offline; **not wired into worker.js/deploy.py, not deployed, never contacted Google.** Research caveat: from this sandbox `developers.google.com` and most vendor sites were unreachable (DNS blocked), so Google facts below come from web-search summaries. Items marked **[verify]** conflict between sources or are third-party only; check them in the Google Cloud Console / the official page before relying on them.

## 1. What the user experiences

1. Customer (role `owner` in the studio) opens Settings → "Connect YouTube". The app calls `POST /studio/yt/start` (Bearer session) and navigates the browser to the returned Google consent URL.
2. On Google's screen they pick the Google account, and, for brand accounts, the channel (see 8), then tick the permissions.
3. Google redirects to `/studio/yt/callback`. The Worker verifies the one-time state, the PKCE verifier and the browser-bound cookie, exchanges the code, reads the channel (`channels.list?mine=true`), stores the **encrypted** refresh token plus channel id/title, and sends the browser back to `/studio#youtube=connected`.
4. From then on, the render worker asks the Worker for a short-lived access token per job (`POST /internal/yt/token`) and uploads. Default: **private draft**. The customer reviews it in the studio (and in YouTube Studio) and publishes themselves, or, if the owner enabled it, a schedule/auto-publish mode applies.
5. Disconnect: `POST /studio/yt/disconnect` revokes the grant at Google and deletes our copy. The customer can always also remove access at `https://myaccount.google.com/permissions`.

## 2. Architecture

```
browser ──start──▶ Worker (youtube_connect.js) ──▶ consent URL (state, PKCE S256, offline, prompt=consent select_account)
browser ◀──Google consent──▶ accounts.google.com ──redirect(code,state)──▶ Worker /callback
Worker: state(one-time, KV) + cookie(ytstate) + PKCE ─▶ oauth2.googleapis.com/token ─▶ channels.list(mine) ─▶ KV (AES-GCM refresh token)
render worker (GitHub Actions) ─x-worker-key─▶ /internal/yt/token {org, job_id} ─▶ Worker refreshes at Google, applies quota + policy
render worker ─Bearer access token (1h)─▶ googleapis.com resumable upload ─▶ customer's channel;   ─▶ /internal/yt/report
```

KV keys (prefix `studio:yt:`, never touches owner-app keys):

| key | content |
|---|---|
| `studio:yt:c:<org>:<chan>` | connection: yt channel id/title, scopes, **encrypted** refresh token `{v,kid,iv,ct}`, status (`connected`/`needs_reconnect`), settings, scheduled slots, last upload |
| `studio:yt:ch:<ytChannelId>` | claim: which org/channel owns this YouTube channel (one YouTube channel can belong to one customer only) |
| `studio:yt:st:<sha256(state)>` | OAuth state (10 min TTL, single use): org, channel, user, PKCE verifier, redirect URI |
| `studio:yt:u:<pacificDay>:<org>:<chan>` | uploads reserved today by this customer (TTL 3 d) |
| `studio:yt:g:<pacificDay>` | project-wide units/uploads reserved today + `exhausted` flag |

`<chan>` is the studio channel id (`c_...`) so an agency org can connect several YouTube channels. The module also writes `yt: {status, channel_id, title}` into the existing studio channel record `studio:c:<org>:<chan>` (public info only) if that record exists, so the studio UI shows the state without calling us.

### Endpoints

| route | auth | purpose |
|---|---|---|
| `POST /studio/yt/start` `{org_id, channel_id?, scope_level?}` | session, owner | returns `{url}` and sets the state cookie |
| `GET /studio/yt/callback` | none (state + cookie) | finishes the flow, redirects to `/studio#youtube=connected\|error=<code>` |
| `GET /studio/yt/status?org_id&channel_id` | session, any member | connection summary, policy, usage; never secrets |
| `POST /studio/yt/settings` | session, owner | `mode` private/schedule/public, `max_per_day`, `schedule{tz,times,per_day,lead_min}`, `confirm_public` |
| `POST /studio/yt/disconnect` | session, owner | revoke at Google, delete record + claim |
| `POST /internal/yt/token` `{org_id, channel_id?, job_id, thumbnail?, renew?}` | `x-worker-key` | access token + `policy` + `reserved_units`; refuses on quota/limit/needs_reconnect |
| `POST /internal/yt/report` `{org_id, job_id, event: uploaded\|failed\|quota_exceeded, video_id?, publish_at?, units?}` | `x-worker-key` | records the result, refunds a reservation if nothing was created |

Callback error codes (in the redirect): `state_invalid`, `browser_mismatch`, `access_denied`, `missing_scope`, `no_refresh_token`, `no_youtube_channel`, `channel_already_connected`, `token_exchange_failed`, `forbidden`, `yt_not_configured`. Token endpoint: 401 bad worker key, 403 `job_mismatch`, 404 `not_connected`, 409 `needs_reconnect`, 429 `customer_daily_limit` / `quota_exhausted` (with `retry_after_s`), 502 transient Google error.

The default auth adapter reads the layout of `app/studio.js` (bearer token → `studio:s:<sha256>` → `studio:u:`; membership `studio:m:<org>:<uid>`; only role `owner` may connect, same as `PERMS.owner` containing `youtube.connect`). `handleYouTube(req, env, {getSession, getRole, fetchImpl, now})` takes overrides if studio.js changes its storage.

## 3. What the owner must do in Google Cloud (exact steps)

Do this with a Google account that is **not** tied to a customer. Names in the console move around (it is now called "Google Auth Platform"); the intent is stable.

1. https://console.cloud.google.com → project picker → **New project**, name `oded-studio`. Use a **separate project from the one behind the ODED HIGHLIGHTS channel**: quota is per project, and your own channel's uploads must not compete with customers (and a quota/ToS problem on one must not hit the other).
2. **APIs & Services → Library →** "YouTube Data API v3" → **Enable**.
3. **Google Auth Platform → Branding:** app name (what customers see, e.g. "Oded Studio"), user-support email, developer contact email. For Testing you can leave logo/home page/privacy policy empty; for verification they are required (section 5).
4. **Audience:** User type **External**. Publishing status **Testing** to start. Under **Test users** add the Gmail/Google accounts of pilot customers (max 100). Note: if the customer logs in with a Google account that owns the channel through a brand account, add the *Google account* (the person), not the channel.
5. **Data access → Add or remove scopes:** `.../auth/youtube.upload` and `.../auth/youtube.readonly` (needed: `channels.list mine=true` is not allowed with `youtube.upload` alone). Optional and only if you want "approve in the studio publishes the video": `.../auth/youtube.force-ssl` (used for `videos.update`); this is `scope_level: "manage"` in `/start`. All of these are *sensitive* scopes (not restricted: no security assessment by a third party) **[verify classification in the console's scope table]**.
6. **Clients → Create client →** type **Web application**, name `studio-worker`. **Authorized redirect URIs:** exactly `https://oded-app.odedhl.workers.dev/studio/yt/callback` (and your custom domain's equivalent later). No JavaScript origins needed. Copy the Client ID and Client secret **into the Cloudflare dashboard only** (next step), never into chat, git or a workflow log.
7. **Secrets in Cloudflare** (Workers & Pages → `oded-app` → Settings → Variables and Secrets → *Add* → type **Secret**): `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `STUDIO_ENC_KEY`. Generate the encryption key locally: `openssl rand -base64 32` (must decode to exactly 32 bytes). Keep a copy in your password manager: **if the key is lost, all stored refresh tokens are unreadable and every customer must reconnect.**
   IMPORTANT for `deploy.py`: a Worker upload replaces bindings, so secrets added in the dashboard are wiped by the next deploy unless the metadata contains `"keep_bindings": ["secret_text"]`. Add that key to the `meta` dict in `app/deploy.py` once (see 10).
8. **GitHub secrets** for the render workflow: `STUDIO_URL` (`https://oded-app.odedhl.workers.dev`) and `STUDIO_WORKER_KEY` (the same value as the `studio:cfg:worker_key` / `STUDIO_WORKER_KEY` studio.js already uses).
9. **Look at the real quota:** Cloud Console → **IAM & Admin → Quotas & system limits**, filter "YouTube Data API v3". Write down the daily limit(s) and whether `videos.insert` has its own line. Then set KV `studio:cfg:yt_quota` (JSON) to match, see section 6.
10. Pilot hygiene: for each test user, tell them to click "Advanced → Go to Oded Studio (unsafe)" on the unverified screen; that is normal for apps in Testing.

## 4. Testing vs production, 7-day expiry (the pilot trap)

- **Testing + External:** up to 100 listed test users, and an authorization (including the refresh token) **expires 7 days after consent**. Google's own docs state this; community reports confirm it. Our reaction: the token endpoint gets `invalid_grant`, sets the connection to `needs_reconnect`, and returns 409. The render job should end as "waiting for reconnect" and the studio should show a *Reconnect* button (`POST /start` again; the settings and schedule survive).
- **In production, not verified:** no 7-day expiry, but Google shows the "unverified app" warning and enforces a **hard cap of 100 users over the entire life of the project** (cannot be reset). So this is a bridge for a small paying pilot, not a launch plan; do not burn the 100 on freebies.
- **In production, verified (sensitive scopes):** no cap, no warning. Refresh tokens survive until the user revokes, 6 months of non-use, or the user's password change in some Gmail cases, and there is a per-account/per-client limit on outstanding refresh tokens **[verify exact number; we always `prompt=consent`, which issues a new token on each reconnect and Google invalidates the oldest beyond the limit]**.
- A token issued while the app was in Testing may keep dying after you switch to production. Ask pilot customers to **reconnect once after the switch**.

## 5. OAuth verification (sensitive scopes) and the separate YouTube audit

Two different Google reviews, both free, both slow:

**A. OAuth app verification** (removes the warning and the 100-user cap). Required: an app **home page** on a domain you own; a **privacy policy** URL on that domain which says what YouTube data you access, how it is used, stored, and deleted, and includes the *Google API Services User Data Policy / Limited Use* statement; **authorized domain** verified in Search Console; support email; app logo; a **scope justification** text per scope; and a **demo video** (unlisted YouTube link) that shows the full flow end to end: the consent screen with the app name and the OAuth client id visible in the address bar, then each scope being used in the product (the upload, the channel name displayed). Mismatch between app name, logo and home page is the commonest rejection. Timelines in sources range from 3-10 business days to several weeks; resubmissions restart the queue; budget 2-6 weeks **[verify]**.
**Domain problem:** `*.workers.dev` is on the public suffix list, so you cannot verify it in Search Console. Verification therefore needs a domain you control (a custom domain pointed at the Worker, ~USD 10/yr). Free subdomain services might be accepted but I could not confirm that **[unverified]**. The domain is only needed for this step, not for the Testing pilot. The repo is public: PRIVACY.md exists; make sure the studio has a public `/privacy` and `/terms` page (the app itself is not built here).

**B. YouTube API Services audit / quota extension form** (a separate form, `support.google.com/youtube/contact/yt_api_form` **[verify]**). It checks your compliance with the YouTube API Services Terms of Service and the Developer Policies. It is what (1) lifts the **"unverified API project → every uploaded video is locked to private"** rule that Google applies to projects created after 28 July 2020 (documented on the `videos.insert` page; one newer source claims this changed **[verify]**), and (2) raises quota. The form asks for company details, a demo account or video, privacy-policy screenshots and a per-endpoint justification. Until it passes, uploads from this project are private no matter what we request. The code therefore treats the project as "not audited" by default: `schedule` and `public` modes are downgraded to private and reported (`policy.downgraded: "project_not_audited"`). After approval set Worker env `YT_AUDIT_PASSED=1` (or KV `studio:cfg:yt_audit_passed` = `1`).
ToS items to respect from day one: show the customer what we store, delete tokens on disconnect (done), do not store data longer than needed (we store only channel id/title/thumbnail URL and the token), honour revocation, no creating multiple projects to multiply quota (forbidden by the Developer Policies).

## 6. Quota: facts, conflict, and the plan

Facts (per Google's quota pages as reported by search summaries **[verify all]**):
- Default project quota is **10,000 units/day**, reset at **midnight Pacific Time** (08:00 UTC in winter, 07:00 UTC in summer). The code uses Pacific days.
- Cost per call: `channels.list` 1, `videos.update` 50, `thumbnails.set` ~50, and `videos.insert`: **1,600** in the long-standing table (so ~6 uploads/day per project). Some sources say the cost fell to ~100 on 4 Dec 2025, and several say that since **1 June 2026** `videos.insert` is charged to its own "Video Uploads" bucket at 1 unit per call with a default of **100 uploads/day** per project. The two models differ by 16x, so the number must be read from your console.
- **The quota belongs to the Google Cloud project, not to the customer**, so all customers share it. That is the scaling constraint of this whole feature.

Implementation (`quotaModel` in `youtube_connect.js`): KV `studio:cfg:yt_quota` = `{"daily_units":10000,"upload_cost":1600,"thumb_cost":50,"headroom_units":500,"max_per_day_cap":20}`. Defaults are the conservative legacy numbers. If the console shows the new bucket, set e.g. `{"daily_units":100,"upload_cost":1,"thumb_cost":0,"headroom_units":0}` (units are then "uploads"). Every `/internal/yt/token` call **reserves** `upload_cost (+thumb_cost)` against the Pacific-day project counter and a per-customer counter (customer limit = min(their `max_per_day`, `max_per_day_cap`), default 3). `report(failed)` refunds; `report(quota_exceeded)` (Google said no anyway) marks the project exhausted until the Pacific reset so no further jobs waste time. Callers get `429` with `retry_after_s` and the script exits 6 (the workflow should reschedule, not fail loudly). KV is not transactional, so two concurrent jobs can over-reserve by one; acceptable with a single render worker, move to a Durable Object/D1 before scaling (same TODO as studio.js).

Plan, in order of cost:
1. **Now:** private drafts only, 3/day/customer, conservative accounting. At 6 uploads/day total you can serve about 2-3 pilot customers at full rate, many more at one draft/day each.
2. Read the real limit in the console (step 9). If it is the 100/day bucket the problem mostly disappears for the first dozens of customers.
3. Submit the **quota extension / audit form** as soon as there is a domain, privacy policy and 3+ real pilot customers; ask for a number justified by customers x drafts/day. Free; weeks to months; not guaranteed.
4. **Fallback that costs nothing in quota:** when the project is exhausted, the studio offers the finished MP4 + a ready title/description/thumbnail for manual upload (YouTube Studio upload does not use API quota). The job result should say `awaiting_manual_upload`. (Needs a small studio.js change; not built here.)
5. **Do not** spread customers over several Google projects to multiply quota (policy violation, can get all projects suspended). A *customer-owned* Google project ("bring your own API key") is allowed but too technical for streamers; keep it only as an enterprise option.

## 7. Upload mechanics (what the Python script does)

`scripts/yt_upload_customer.py VIDEO META.json [THUMB] --org O --job J [--channel C] [--expect-channel UC...]`, env `STUDIO_URL`, `STUDIO_WORKER_KEY`. It reuses the ideas of `scripts/yt_upload.py` (resumable, hold file, channel guard) but never sees a refresh token, and uses only the stdlib (no curl).

- **Order:** hold check → token from the Worker (reserves quota) → `channels.list mine=true` must equal the Worker's channel id (and `--expect-channel` if given) else exit 3 and refund → `videos.insert` resumable.
- **Resumable protocol:** `POST https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status` with `X-Upload-Content-Length/Type`, metadata JSON as body → `Location` session URI. Then `PUT` chunks (default 8 MiB, multiple of 256 KiB) with `Content-Range: bytes a-b/total`; `308` + `Range` header = continue; `200/201` = done with the video resource. After a network error or 5xx the script asks `Content-Range: bytes */total` and continues from the byte YouTube has. Backoff `2^n` (cap 300 s) + jitter, up to 8 consecutive failures. The session URI is saved (mode 0600, `$YT_UPLOAD_SESSION_DIR`, default `/tmp/oded_yt_sessions`) so a **re-run after a crash resumes the same upload** and asks the Worker for a token with `renew: true` (no second reservation). An expired session (404/410) starts a fresh init. 401 mid-upload → new token with `renew`.
- **Privacy:** `status.privacyStatus` is `private` unless the server policy says `public` **and** META also says `public`. META can never schedule or publish by itself.
- **Scheduled publishing:** `privacyStatus: "private"` plus `status.publishAt` (ISO 8601, in the future; YouTube flips it to public at that time). `publishAt` comes only from the policy: the Worker computes the next free slot from the customer's `schedule` (time zone, times of day, `per_day`, `lead_min`), skipping slots already scheduled. Only active after the audit (see 5B); the customer can always change it in YouTube Studio.
- **Metadata:** title ≤100 chars, description ≤4900, tags total ≤480 chars, `categoryId` 24 default, `defaultLanguage`/`defaultAudioLanguage` from META `lang` (default `he`), `selfDeclaredMadeForKids: false`. Shorts are recognised by YouTube from the media (vertical, ≤ 3 min), not by an API flag.
- **Thumbnail:** `thumbnails.set?videoId=` with the JPEG/PNG image (≤2 MB, 16:9, 1280x720 recommended, min 640 px wide), ~50 units. Custom thumbnails need the channel to have the "intermediate features" (phone verification) enabled; a 403 here is **non-fatal** (the video stays uploaded, log says "thumbnail not set"). Two thumbnails per video for "test & compare" is Studio-only (not in the API), as already noted in RULES.md.
- **Errors:** `quotaExceeded`/`dailyLimitExceeded`/`uploadLimitExceeded` → exit 6 and `report(quota_exceeded)`; `rateLimitExceeded`/`backendError`/5xx/429 → backoff; other 403 (e.g. unverified app, channel cannot upload) → exit 1, not retried.
- **Exit codes:** 0 ok, 1 error, 2 usage, 3 wrong channel, 4 `state/UPLOAD_HOLD` active, 5 customer must reconnect, 6 quota/limit (retry later), 7 bad input.

## 8. Brand accounts and channel selection

A Google account can own or manage several YouTube channels (brand accounts). The consent URL uses `prompt=consent select_account` so the customer explicitly chooses the identity; when a brand account is picked, Google shows its channels. The grant is for that identity, and `channels.list?mine=true` returns the channel it resolved to, which we store (id + title) and **show back to the customer** ("Connected: <title>") so a wrong pick is visible at once; reconnecting fixes it (old token is revoked, claim moved). We then always verify against that channel id before uploading. Official docs say little here and I could not confirm which channel a token binds to when the account has several; treat "title shown + guard before every upload" as the safety net **[verify with a real multi-channel test account in the pilot]**. `onBehalfOfContentOwner` (partners) is not used.
Another failure: the Google account has no YouTube channel → `no_youtube_channel` and the freshly issued token is revoked.

## 9. Token security

- Refresh token encrypted at rest with **AES-256-GCM**, random 12-byte IV per record, key from the Worker secret `STUDIO_ENC_KEY` (never in KV/git). The **AAD is `<org>:<channel>`**, so a record copied to another customer's key will not decrypt (tested). `kid` field + optional `STUDIO_ENC_KEY_OLD` give key rotation: records encrypted with the old key are re-encrypted on first use.
- Access tokens are never stored; they are minted per job (valid ~1 h) and held only by the GitHub runner process. `/internal/yt/token` demands the worker key **and** a real `job_id` of that customer (a leaked worker key still cannot ask for arbitrary customers without knowing job ids; set `YT_REQUIRE_JOB=0` only for manual tests).
- The module has no logging (a test fails if a `console.*` call is added); Google error bodies are reduced to a short `{code, description}`; status responses carry no secret fields (tested). The Python script never prints tokens, writes the resumable session URI with mode 0600, and has no import-time side effects.
- OAuth hardening: `state` random and single use (10 min), **PKCE S256**, an **HttpOnly Secure SameSite=Lax cookie** bound to the state (stops "victim completes the attacker's flow" login-CSRF; tested), callback re-checks that the starter is still the org owner, `referrer-policy: no-referrer` on the callback page, scopes granted are checked (users can untick permissions; we refuse and revoke if upload is missing), a YouTube channel can be claimed by one customer only.
- Least privilege: only `youtube.upload` + `youtube.readonly` by default. We cannot delete or edit anything with those (nothing is deleted anywhere, per RULES.md).
- Worker secrets and `keep_bindings`: see step 7. Rotating the OAuth client secret: change `YT_CLIENT_SECRET` in Cloudflare; existing refresh tokens keep working.
- Backups: KV is the only copy of the encrypted tokens; losing it just means reconnecting. Losing `STUDIO_ENC_KEY` equals the same.

## 9b. Disconnect, revocation, deletion

`POST /studio/yt/disconnect` (owner): decrypt token → `POST https://oauth2.googleapis.com/revoke` (revokes the grant and its access tokens) → delete connection record, channel claim, reset studio channel `yt` status. If the key is lost or Google is unreachable, our copy is still deleted and the response tells the customer to remove access at `myaccount.google.com/permissions`. If the customer revokes there first, the next token request returns `invalid_grant` → `needs_reconnect`. On customer/account deletion the studio must call disconnect for each channel (hook to add in studio.js). Videos already uploaded remain on the customer's channel (we never delete anything on YouTube).

## 10. Integration (not done here: other agents are editing these files)

1. `app/worker.js`, top of `fetch()` before the `/studio` route:
   ```js
   import { handleYouTube } from "./youtube_connect.js";                 // top of file
   if (p.startsWith("/studio/yt/") || p.startsWith("/internal/yt/")) { const r = await handleYouTube(req, env); if (r) return r; }
   ```
2. `app/deploy.py`: add `youtube_connect.js=@.../youtube_connect.js;type=application/javascript+module;filename=youtube_connect.js` to the multipart upload (same as `studio.js`), and add `"keep_bindings": ["secret_text"]` to `meta`. The file has no placeholders, so it needs no bundling step.
3. `app/studio.js`: replace the `501 youtube_oauth_not_implemented` branch of `POST /orgs/:id/channels/:cid/youtube` by a call to the same flow (or let the UI call `/studio/yt/start` directly), and in `/studio/worker/claim` hand the worker `{org, channel, job_id}` (already there) so the Python script can call `/internal/yt/token`. Never return a refresh token from `claim`.
4. Render workflow: after a job reaches QA, run `python3 scripts/yt_upload_customer.py clip.mp4 meta.json thumb.jpg --org $ORG --channel $CHAN --job $JOB` with `STUDIO_URL`/`STUDIO_WORKER_KEY`; map exit 5 → job `blocked: reconnect YouTube` (notify the customer), 6 → retry after `retry_after_s`/Pacific midnight, 4 → keep the file, retry later. On success put `VIDEO_ID` into the job draft (`yt_video_id`, already a field).
5. The owner's own pipeline (`yt_upload.py`, `config/channels.json`, `state/UPLOAD_HOLD`) is untouched. The customer script honours the same hold file.

## 11. Failure matrix

| situation | detected by | result |
|---|---|---|
| customer unticks the upload permission | callback scope check | `missing_scope`, token revoked, nothing stored |
| refresh token expired (Testing 7 d) / revoked | `invalid_grant` | `needs_reconnect`, exit 5; reconnect restores, settings kept |
| Google outage | 5xx on token endpoint | 502 `transient`; connection stays connected |
| project quota gone | reservation guard or Google 403 | 429/exit 6, project closed until Pacific midnight |
| customer exceeds own limit | per-customer counter | 429 `customer_daily_limit` |
| wrong channel somehow | `channels.list` ≠ stored id | exit 3, refund, nothing uploaded |
| runner dies mid-upload | session file | rerun resumes, no new reservation |
| YouTube channel claimed twice | claim key | `channel_already_connected` |
| unaudited project | policy | uploads private; schedule/public downgraded and flagged |
| encryption key lost | decrypt error | 500 `decrypt_failed`; all customers reconnect |

## 12. What is tested

`node app/youtube_connect.test.mjs` (28 checks): PKCE, consent URL, AES-GCM (aad, tamper, rotation), Pacific day/DST maths, schedule slots, settings validation, policy downgrade, full start→callback→status→settings→token→report→disconnect flow against a mocked Google, CSRF/cookie/state-reuse/role-change/missing-scope/no-refresh-token/no-channel/duplicate-channel cases, quota guard and `quota_exceeded`, `needs_reconnect` and recovery, no plaintext secrets in KV, no logging.
`python3 -m unittest tests/test_yt_upload_customer.py` (23 tests): chunked upload ranges, channel enforcement, policy (privacy/publishAt), hold file, reconnect/quota/limit exit codes, init retries/backoff, resume after network drop, crash-and-rerun, expired session, 401 mid-upload, thumbnail failures, input errors.
**Not tested** (needs real Google, deliberately not done): the actual consent screen, real token/refresh behaviour, brand-account selection, real `videos.insert`/`publishAt`/`thumbnails.set` responses, the Cloudflare deployment with secrets, the quota numbers.

## 13. Sources (search summaries; Google's own pages were not reachable from this environment)

- Google Identity: OAuth 2.0 for web server apps, production readiness / sensitive scope verification (developers.google.com/identity/protocols/oauth2/...), Google Cloud support "OAuth app verification" (support.google.com/cloud/answer/13461325, /15549945): 7-day expiry in Testing, 100 test users, 100-user lifetime cap and warning for unverified apps, verification contents.
- YouTube Data API: `videos.insert` reference (unverified projects after 28 Jul 2020 are private), quota and compliance audits guide, `determine_quota_cost`, `thumbnails.set` (≈50 units, ≤2 MB), revision history (granular quota buckets from 1 Jun 2026) at developers.google.com/youtube.
- Third-party summaries used only for cross-checking and flagged **[verify]**: ayrshare, postzen, repostit, outstand, adaptlypost, unipile, nylas, singhamandeep blogs and Google Groups/discuss.google.dev threads on refresh-token expiry.

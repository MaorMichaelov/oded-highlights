# Product plan: turning the highlights editor into a SaaS for streamers

Research date: 17 Nov 2026. Budget assumption: zero until paying customers. Companion: `docs/PRODUCT_ARCHITECTURE.md` (data model, API, job flow, migration off GitHub Actions) and the MVP skeleton in `app/studio.js`.

Evidence tags used below: **[V]** read today on the vendor's own page (primary), **[S]** from search-result summaries or third-party sites (could differ from the vendor), **[E]** my estimate or calculation, **[U]** could not verify. Not legal or tax advice.

---

## תקציר בעברית (לעודד)

**המסקנה בשורה אחת:** אפשר לבנות את זה, ההכנסות פוטנציאליות טובות (עלות ~0.17$ לשעת סטרים מול מחירי מתחרים של ~6$ לשעת וידאו), אבל יש 4 מכשולים אמיתיים שחייבים להחליט עליהם לפני שמוכרים לאנשים: חוזי GitHub, מכסת YouTube, איך מושכים את הסטרים מ-Kick/Twitch, ותשלומים לישראלי.

1. **GitHub Actions לא מתאים לשירות בתשלום.** התנאים של GitHub אוסרים להשתמש ב-Actions "כחלק מהצעת שירות מסחרי" ובשרתים שלהם רק לפרויקט התוכנה עצמו [V]. הריפו כרגע ציבורי, והקוד חייב להיות פרטי. מה שמחליף: שרת רינדור פרטי (מחשב שלך לבטא בחינם, אחר כך שרת Hetzner ב-35-70$ לחודש). זה גם מה שהארכיטקטורה שבניתי מניחה (ה-Worker של Cloudflare רק מנהל תורים, שרת רינדור מושך עבודות).
2. **YouTube:** מכסת ברירת מחדל = **100 העלאות ביום לכל הפרויקט** (לא לכל לקוח) ו-10,000 יחידות ליום לשאר הקריאות [V]. כל שעת סטרים מייצרת ~9 סרטונים, כלומר בלי הרחבת מכסה אפשר לשרת ~11 שעות סטרים ביום בסך הכל (בערך 3 סטרימרים). צריך להגיש בקשה לביקורת (Audit) והרחבה כבר מהשבוע הראשון, אין זמן תגובה מובטח [V/U]. בנוסף צריך אימות אפליקציית OAuth (scope רגיש youtube.upload) כדי לעבור את מגבלת משתמשי הבדיקה [S]. חדשות מה-2 בנובמבר 2026: העלאות מפרויקט לא מאומת כבר **לא** ננעלות כפרטיות, ואם לא מציינים privacyStatus הסרטון יוצא **ציבורי** [V]. לכן הקוד חייב תמיד לציין `private` במפורש (זה מה שהתכנון עושה).
3. **Kick/Twitch:** ל-Kick אין API רשמי להורדת VOD, והתנאים שלהם (סעיף 1.4) אוסרים גישה אוטומטית [V]; ל-Twitch אין API להורדת VOD (לפי הפורום שלהם) [S]. הדרך הנקייה: הלקוח מוסיף אצלו ב-OBS יעד שידור שני אלינו (SRT/RTMP), או מעלה קובץ/קישור יוטיוב. יש גם אימות זהות רשמי עם OAuth (Kick `user:read`, Twitch OIDC) שעדיף על קוד בביו. **החלטה נדרשת.**
4. **תשלומים:** Stripe לא תומך בעסק רשום בישראל בלי עקיפות (חברה אמריקאית/Atlas) [S]. מומלץ Paddle (Merchant of Record, תומך במוכרים מישראל [S], עמלה 5% + 50 סנט [S]) כי הוא גם מטפל במע"מ/מס מכירות בעולם; גיבוי: Lemon Squeezy. צריך רואה חשבון בנוגע לעוסק פטור/מורשה ויצוא שירותים (לא הצלחתי לאמת [U]).
5. **תמחור מומלץ (קרדיט = שעת סטרים):** Starter 19$ ל-12 שעות, Creator 49$ ל-40 שעות, Pro 129$ ל-120 שעות + 3 מושבים; חבילות נוספות 1.5$ לשעה. רווח גולמי אחרי עמלת תשלום: ~80% בתרחיש בסיס, ~30-50% בתרחיש יקר (מודל LLM חזק + שרת Cloudflare Containers) [E].
6. **תחרות:** OpusClip (15-29$ לחודש, קרדיט לדקת וידאו מקור, ~6$ לשעה [S]), Eklipse/StreamLadder (8-27$ [S]), Klap/Vizard/Submagic/Munch. החולשות שלהם לסטרימרים: מחיר על VOD ארוך, לא מזהים סטרימים חדשים ב-Kick/Twitch אוטומטית, מותאמים לדיבור ולא למשחק, אין עברית/RTL מוכחת [S]. היתרון שלנו: עברית מקורית (ASR ivrit-ai), זיהוי סטרים אוטומטי, העלאה כטיוטה פרטית + אישור, סרטון ארוך + שורטס + QA.
7. **סיכונים עיקריים:** זכויות יוצרים של תוכן צד שלישי בתוך הסטרים (מוזיקה, משחקים) על הלקוח, דורש תנאי שימוש + מדיניות DMCA ורישום סוכן DMCA (~6$ [S]); תקציר מדיניות "תוכן לא אותנטי" של YouTube מ-יולי 2025 נגד תוכן המוני חוזר [S]; שוק עברי קטן, צריך אנגלית; עבודה של איש אחד (תמיכה).
8. **מה נבנה:** שלד ב-`/studio` ב-Worker (הרשמה, אימות בעלות על ערוץ בקוד בביו, תור עבודות, צוות והזמנות, צ'אט עוזר "תכין 5 שורטס מצחיקים מאתמול", כרטיסי אישור/דחייה). **לא נבנה:** חיבור YouTube OAuth, תשלום, שרת הרינדור, מייל. אין פריסה לפרודקשן.

**החלטות שצריך ממך:** (א) לאשר מעבר רינדור לשרת פרטי ולהפוך את הריפו לפרטי; (ב) שיטת קליטת סטרים ללקוחות (restream / קובץ / VOD URL); (ג) Paddle מול Lemon Squeezy מול חברה אמריקאית; (ד) מחירים ומה כלול בניסיון חינם; (ה) להתחיל בקשת Audit למכסת YouTube עכשיו; (ו) האם להתחיל באנגלית וגם בעברית; (ז) דוא"ל ודומיין לדפי תנאים/פרטיות (נדרשים לאימות Google).

---

## 1. Competitors

### 1.1 Pricing and features (all prices from third-party pages, vendors' own pages were blocked in the sandbox; verify before quoting)

| Tool | Entry price | Unit | Notes |
|---|---|---|---|
| OpusClip | Free (60 min/mo), Starter 15 USD/mo (150 credits), Pro 29 USD/mo (300 credits); annual about 14.5 USD [S] | 1 credit = 1 minute of SOURCE video, partial minutes round down, min 1 [S] | So Pro is about 5 hours of source for 29 USD = about 5.8 USD per source hour [E]. Sources disagree on rollover/expiry. Accepts Twitch VOD links; its own blog says stream support is on the roadmap [S] |
| Klap | about 23-29 USD/mo (sources disagree, one says custom pricing) [S] | videos/credits | Built for talk/podcast style topics [S] |
| Vizard | about 16 USD/mo; free exports 720p [S] | credits | |
| Submagic | about 19-29 USD/mo; 25 videos/mo on the 29 plan [S] | videos | Caption focused; Hebrew transcription page exists, RTL layout unverified [S][U] |
| Munch (now munchstudio.com) | not found | per-minute cap | No Twitch/Kick integration; "two long sessions and the month's budget is gone" (complaint cited by a competitor blog) [S] |
| Eklipse | about 12.5 USD/mo annual, 24.99 monthly [S] | clips | Built for gaming streamers on Twitch, Kick, YouTube; competitor-published criticism: misses non-kill highlights [S] |
| StreamLadder | about 8-27 USD/mo [S] | | "ClipGPT" turns a VOD into about 10 vertical clips [S] |
| Powder.gg | shut down in 2025 [S] | | |
| Streamlabs Cross Clip | free with Streamlabs [S] | | No AI discovery of moments in a VOD [S] |

### 1.2 What streamers and reviewers complain about [S] (no direct Reddit evidence was retrievable: mostly competitor blogs, so treat as directional)

* Credit pricing punishes long VODs: a 90-minute stream burns 90 credits, about a third of an OpusClip Pro month.
* Wrong moments on long gaming content: one test of 50+ clips found about 40% discarded; gaming highlights depend on what happens, not what is said, and speech-based rankers miss them.
* Manual step: tools accept a VOD link but none discovers new streams by itself on Kick/Twitch.
* Billing, cancellation and support friction are the most common complaint category in 2026 roundups.

### 1.3 Where we can win and where we cannot

Win: Hebrew first (ivrit-ai whisper, RTL captions already in our pipeline), automatic new-stream detection, private-draft-then-approve flow (fits YouTube policy), one finished package (Shorts + long video + QA), chat-driven requests, price per stream hour far below per-source-hour competitors, editors/agencies with team roles.
Cannot (yet): brand and trust, volume of training data, a proven hit rate. Honest gap: we have no measurement that our picks beat Opus/Eklipse; run a blind comparison on 3 streams before selling.

---

## 2. Legal and terms

### 2.1 GitHub Actions for a paid service: do not [V]

GitHub Additional Product Terms, section Actions (read from the `github/docs` repository today): usage is limited by the Agreement, the Acceptable Use Policies and the Actions service limits, and "regardless of whether an Action is using self-hosted runners, Actions should not be used for: ... the provision of a stand-alone or integrated application or service offering the Actions product or service, or any elements of the Actions product or service, for commercial purposes; any activity that places a burden on our servers, where that burden is disproportionate to the benefits provided to users (for example, don't use Actions as a content delivery network or as part of a serverless application ...); or, if using GitHub-hosted runners, any other activity unrelated to the production, testing, deployment, or publication of the software project associated with the repository". Misuse can end with job termination, repository disabling or account suspension.
Reading for us: rendering paying customers' video on Actions is "using Actions as the back end of a commercial service". Even the status quo (24/7 loops that ingest and transcribe video for a YouTube channel) is arguably outside "the software project". Self-hosted runners do not fix the first three bullets.
Cost facts: Actions is free for standard hosted runners in PUBLIC repos and for self-hosted runners [V]; private repos draw from a plan allowance (the allowance size was not on the page I read [U]); hosted Linux is about 0.006 USD/min after the 1 Jan 2026 cut [S] (about 0.36 USD per hour; a 4-vCPU slot on Hetzner is 5-10x cheaper). A planned 0.002 USD/min fee on self-hosted runners was announced for March 2026 and postponed after backlash; no new date found [S].
Conclusion: customers' jobs must run on our own server; make the repo private after migrating (`docs/PRODUCT_ARCHITECTURE.md` section 9).

### 2.2 YouTube API Services

* **Quota [V]** (Google's page, last updated 2026-11-12): default per project = 100 `videos.insert` calls per day, 100 `search.list` calls per day, and 10,000 units per day for all other endpoints. Since 1 June 2026 `videos.insert` and `search.list` have their own buckets, each call costing 1 against its own 100/day [V]. The old "1600 units per upload" is gone: on 4 Dec 2025 Google cut the upload cost from about 1600 to about 100 units, and then moved it to its own bucket [V]. Other costs: `thumbnails.set` 50, `videos.update` 50, `playlistItems.insert` 50, `videos.list` 1 [V]. Resets at midnight Pacific.
* **The limit is per Google Cloud project, not per customer.** At about 9 videos per stream hour (8 Shorts + 1 long) the default supports about 11 stream hours per day for ALL customers together [E]; the 10,000 units also cap approve flows (videos.update 50 + thumbnails.set 50 = 100 units per video = about 100 videos/day) [E].
* **Extension [V]:** "you must first complete an audit to show that your project is in compliance with the YouTube API Services Terms of Service"; start with the "YouTube API Services - Audit and Quota Extension Form" (support.google.com/youtube/contact/yt_api_form); after an audit passed in the last 12 months, the same form requests more quota; a failed audit has an appeal form. No timeline or approval promise is published [V]; third-party guides say the form asks for project URL, privacy policy, terms, use case and expected daily usage [S]. Plan: file in week 1 with the working beta, expect weeks [U]. Periodic audits can follow [V].
* **Private uploads:** 28 Jul 2020 rule locked uploads of unverified projects to private; on **2 Nov 2026 YouTube reversed it**, and if `status.privacyStatus` is omitted the upload now defaults to PUBLIC (some account settings can still make it private) [V]. Our design uploads private drafts anyway, but the worker must always send `privacyStatus: "private"` explicitly, and a test must guard it. This used to be a safety net; it no longer is.
* **OAuth app verification [V/S]:** apps requesting sensitive scopes must be verified before any Google account can grant access: justification per scope, demo video, policy compliance [V]; in "Testing" status there is a user cap, a warning screen and limited refresh-token lifetime [V] (7-day refresh tokens and a 100-user cap are what I remember from Google's docs, not in the page text I read [U]). Scopes needed: `youtube.upload` (upload) plus `youtube.readonly` (channel identity); I believe both are classed sensitive, not restricted, so no paid CASA security assessment [U]. Need: verified domain, public privacy policy and terms pages, support email.
* **Developer Policies that shape the product [V]** (read from the policy page): privacy policy must be accepted by users and link to Google's privacy policy and security-settings page; revocation means deleting that user's authorized data within 7 calendar days; stored authorized data must be refreshed or deleted every 30 days; the client must "clearly identify any actions" it takes on the user's behalf and the user must expressly consent before they happen; "you must not automate or trigger views, uploads, comments ... without the user's prior specific and express consent"; a client that changes visibility needs the user's express consent (the private draft + approve click covers this, record the consent in the job log); no scraping of YouTube; one API project per API client; "selling an API client" is an explicitly permitted commercial use [V]; selling YouTube API access itself is not [V]. Required Minimum Functionality: for example do not cap the title below 100 characters [V].
* Our channel today uses a personal project; the product needs its own Google Cloud project and OAuth consent screen (separate from the owner's own channel automation).

### 2.3 Kick

* Official API (docs.kick.com) [V]: OAuth 2.1 with PKCE, scopes `user:read` (username, streamer id), `channel:read` (channel description, category, **and the stream key**), `events:subscribe`, etc.; webhooks include `livestream.status.updated` (is_live, started_at, ended_at) and `livestream.metadata.updated`. App creation needs 2FA on the Kick account. No VOD list/download endpoint appears in the documentation index [V]. App verification is by email to developers@kick.com [V].
* Ownership verification options: (1) code in the public bio/stream title (what the MVP does; the public channel JSON exposes `user.bio`, the stream title and even the linked `youtube` handle [V, checked with curl]); (2) Sign in with Kick (`user:read`): stronger and official, use it as the primary proof and keep the code as fallback. Do NOT request `channel:read`.
* Kick Terms of Service (23 Mar 2026) section 1.4 [V]: prohibited "using any automated system, including robots, spiders, offline readers ... to access any part of the Service" and "copying ... any part of the Service in any medium, including by any automated or non-automated scraping" (search-engine exception only). Our current code reads `kick.com/api/v2/...` and HLS playlists: that is a terms risk even for the owner today, and a bigger one when done for many customers. Mitigation: official API/webhooks for detection and identity, customer-initiated restream or file upload for the media.
* VOD retention: Kick's help article is reported to say 30 days for verified and 7 days for non-verified channels [S]; other sites claim different numbers [S]; [U].

### 2.4 Twitch

* The sandbox blocked dev.twitch.tv and legal.twitch.com: the Developer Services Agreement text and Helix reference are **[U]**. From forum summaries [S]: Helix `GET /videos` gives metadata only, and a Twitch staff reply states there is no official way to download VODs programmatically; third-party downloaders are described as against the agreement by a forum user (not authoritative). The built-in "export to YouTube" exists in the creator's Video Manager (manual).
* Ownership: Helix `GET /users` returns the public `description` (About text); app access token (client credentials) is enough, which is what the MVP uses (needs a Twitch app id/secret in KV). Better: "Sign in with Twitch" (OIDC, scope `openid`) [S].
* VOD retention 14 days (non-affiliates) / 60 days (affiliates, partners) is commonly quoted [S][U]; one report says some thresholds were lowered to 7 days [S].
* Detection: EventSub `stream.online` / `stream.offline` webhooks [U, from my knowledge of the API].

### 2.5 Copyright and DMCA position for a tool that clips only the customer's own streams

* Core control: we only edit/upload content for channels whose ownership the customer proved, and upload only to the YouTube channel the same customer authorised. That removes the "clip theft" case that gets clipping tools in trouble.
* A streamer owns their own performance but streams contain third-party material: music, game audio/footage (publisher licences), reaction content, other people's voices (guests, donators). The risk sits mostly with the customer and with YouTube Content ID, and partly with us as the host/processor.
* If we store customer content we are a hosting provider: to use the DMCA 512(c) safe harbour in the US the service must register a designated agent with the US Copyright Office (online, about 6 USD per designation, renew every 3 years; fee from 2016 guidance [S][U]) and run a notice-and-takedown and repeat-infringer policy. Keep source video only for the job duration (7 days max, [E]) and drafts live on the customer's own YouTube anyway.
* Terms of Service must state: customer warrants they own or have rights to the streams and all content in them; our indemnity exclusions; takedown handling; right to suspend. A lawyer should review (about a few hundred USD for a template review [E][U]).
* YouTube policy side: since 15 Jul 2025 YouTube's monetisation policy was renamed "inauthentic content" and targets mass-produced, repetitive, templated content, with examples such as near-identical templated videos; editing with significant original commentary/entertainment value is allowed [S]. Streamer highlights from the streamer's own channel are usually fine, but pushing identical templates at volume is the pattern to avoid: keep variety, titles that are specific, and QA. Reused-content rules are separate [S]. Gambling-related streams may bring YouTube advertiser/policy limits [U]; our repo contains gambling detection code, so this is relevant for some Israeli Kick streamers.
* Privacy law (Israel Protection of Privacy Law, EU GDPR for EU customers): we process email, channel identity and OAuth tokens: privacy policy, deletion on request, token revocation handling [U, needs legal check].

---

## 3. Compute: cost per stream hour and where to run

### 3.1 What one stream hour costs in our pipeline [E, based on measured stage times in `docs/SPEED_RESEARCH.md` and the repo]

Assumed output per stream hour: 8 Shorts (about 45 s) + 1 long video (about 12 min). Source 1080p60 about 8.4 Mbps = about 3.8 GB per hour.

* **ASR** (Hebrew): the repo runs `ivrit-ai/whisper-large-v3-turbo-ct2` int8 on CPU at about 0.4 x real time on 4 vCPU (repo comment), no per-minute fee, so it costs 0.4 slot-hours per stream hour. Hosted alternatives: Groq whisper-large-v3-turbo 0.04 USD per audio hour, large-v3 0.111 [S]; Cloudflare Workers AI whisper-large-v3-turbo 0.0005 USD/min = 0.03 USD/hour [V] (quality on Hebrew is the generic Whisper, probably worse than ivrit-ai [U]). Groq free tier limits seen on its docs [V]: whisper 7,200 audio seconds per hour and 28,800 per day (organisation level) = 8 stream hours per day for everybody: not usable beyond a demo.
* **Cut, edit, render, QA:** measured: CUT about 0.4-0.5 x clip length (19 min clip: 584 s), EDIT 100-190 s fixed, QA 3-50 s, upload 5-80 s (docs/SPEED_RESEARCH.md). For 8 Shorts + 12 min long: about 324 s + 150 s + 8 x 20 s (estimated) + 30 s = about 11 min = 0.18 slot-hours. Total about 0.6-0.7 slot-hours of a 4-vCPU machine per stream hour.
* **LLM** (moment scoring, moment refinement, long-video edit plan, titles/descriptions): about 95k input and 15k output tokens per stream hour (Hebrew transcript of an hour is about 9k words, about 25-30k tokens; four passes) [E]. At current list prices [V from the claude-api model table, and Cloudflare page]: Haiku 5.5 0.10/0.50 USD per M tokens = **0.017 USD**; Cloudflare gpt-oss-120b 0.35/0.75 = 0.044 USD; Sonnet 5.5 2/10 = 0.34 USD; Opus 5.5 4/20 = 0.68 USD; Gemini 2.5 Flash-Lite 0.10/0.40 (third-party figure [S]) = 0.016 USD. Recommended hybrid: cheap model for scanning (95k/15k) + Sonnet-class only on the top candidates (20k/3k) = **about 0.09 USD** [E]. The scheduled Claude session that picks topics today does not scale commercially; the LLM must be an API call per job.
* **Storage and egress:** source kept 7 days (0.9 GB-month) + outputs 30 days (0.5 GB): about 0.02 USD on Cloudflare R2 (0.015 USD/GB-month, no egress fees [V]).

### 3.2 Where to run (price per hour of a 4-vCPU slot, and per stream hour at 0.65 slot-hours)

| Option | Price | Per slot hour | Per stream hour | Notes |
|---|---|---|---|---|
| Owner's own PC at home + outbound-only worker | 0 (electricity) | 0 | 0 | Beta with a few friendly customers only: uptime, upload bandwidth, nobody else touches it. Free |
| Oracle Cloud Always Free (Ampere A1) | 0 | 0 | 0 | Allowance was 4 OCPU/24 GB; sources say it was cut to about half on 15 Jun 2026 [S][U]; idle VMs (<20% CPU p95 over 7 days) can be reclaimed [S]; ARM; paying customers on a free tier is a terms/uptime gamble. Not recommended for customers |
| Hetzner Cloud CCX23 (4 dedicated vCPU, 16 GB) | about 24-51 USD/mo; prices were raised 15 Jun 2026 and sources conflict [S][U] | 0.04-0.07 | 0.03-0.05 | Check hetzner.com/cloud (blocked here) |
| Hetzner dedicated AX41 (6 core/12 thread) | 57.30 EUR/mo excl. VAT, 67.10 USD (official price-adjustment page via search snippet) [S] | 0.03 if 3 slots busy | 0.02-0.06 | Best price per CPU at steady load; monthly commitment small; 1 box serves about 13 heavy streamers [E] |
| Cloudflare Containers standard-4 (4 vCPU, 12 GiB, 20 GB disk) | CPU 0.000020/vCPU-s + 12 GiB x 0.0000025/GiB-s + disk, plus 5 USD/mo Workers Paid [V] | 0.40 | **0.26** | Scales to zero, same vendor as the Worker/KV/R2, but 6-10x the cost of a rented box at steady load |
| Modal (CPU) | 0.0000131 USD/core-s (core = 2 vCPU) + 0.00000222/GiB-s; 30 USD/mo free credit on Starter [S] | 0.19 | 0.12 | Good for bursts; third-party notes mention regional/preemption multipliers [S] |
| GitHub-hosted runner (private) | 0.006 USD/min [S] | 0.36 | 0.23 | Terms problem, see 2.1 |
| fly.io | not retrieved [U] | | | |

Recommendation: phase 0 own PC (week 0-6, up to 5 beta customers, uploads still private), phase 1 one Hetzner dedicated box as soon as there are about 5 paying customers (fixed cost about 70 USD/month = about 14 USD per customer at 5, 5 USD at 13), phase 2 add Modal/Cloudflare Containers only for bursts, add boxes when slot utilisation passes about 60%. Whatever runs, put an alarm on "no claim for 10 minutes".

### 3.3 COGS per stream hour (compute at 0.65 slot-hours, LLM per 3.1, storage per 3.1)

| Scenario | LLM | Compute | Storage | Hosted ASR | **COGS per stream hour** |
|---|---|---|---|---|---|
| Low (Haiku-class everywhere, rented box) | 0.02 | 0.03 | 0.01 | 0 | **0.06 USD** |
| Base (hybrid LLM, dedicated box at about 65% load) | 0.09 | 0.06 | 0.02 | 0 | **0.17 USD** |
| High (Sonnet-class on all passes, Cloudflare Containers, Groq ASR) | 0.35 | 0.26 | 0.03 | 0.04 | **0.68 USD** |

A streamer doing 4 h/day x 20 days = 80 stream hours costs about 14 USD/month at base cost. So never sell "unlimited": meter by stream hour, and consider a "moments only" mode (ASR/LLM only around chat/audio peaks) to cut cost further [E].

---

## 4. Payments for an Israeli seller

* **Stripe:** Israel is not on Stripe's list of countries where a business can open an account, according to several secondary guides [S] (not checked on stripe.com: blocked here). Standard workaround is a US LLC/Delaware company via Stripe Atlas with a US bank or Wise/Payoneer account [S]: extra admin and tax (and Israeli tax on the owner). Card pricing around 2.9% + 0.30 USD plus surcharges for international cards and currency conversion [S][U].
* **Paddle (merchant of record):** sellers from Israel are on the supported list [S]; fee 5% + 0.50 USD per transaction, no payout fee by default except possible SWIFT fees (about 15 USD reported) [S]. As MoR they sell the product, collect and remit VAT/sales tax worldwide and issue invoices; you invoice Paddle. Needs an approved website, terms, privacy and refund policy; Paddle can reject certain product types: AI video clipping is normally fine but approval is a gating step [U].
* **Lemon Squeezy (owned by Stripe per a 2026 source [S]):** MoR, 5% + 0.50 USD [S]; Israel is on its bank-payout list, payout fees possibly 1-3% outside the US [S][U]. Product direction after the acquisition is uncertain [S].
* **Israeli local processors** (Cardcom, Tranzila, PayPlus, Grow...): not researched [U]. Good for ILS cards and local customers, but you handle foreign VAT yourself.
* **Recommendation:** Paddle first (MoR removes the worldwide tax problem when you are alone), Lemon Squeezy as backup, and ask an Israeli accountant about: becoming osek morsheh vs patur at the expected revenue, export-of-services VAT treatment for payouts from Paddle, and invoicing Paddle. I could not verify the osek patur ceiling or the export-of-services rules: [U].
* Model: **credits = stream hours**. Subscription tiers give monthly credits (expire with a one-month rollover cap), top-up packs for overage, trial credits (the skeleton grants 2). Hook points are marked `TODO(payment)` in `studio.js` (checkout creation, webhook that tops up `org.credits`, plan change).

---

## 5. Pricing recommendation and margins

Credit unit: 1 credit = 1 started hour of source stream; each credit includes up to 8 Shorts + 1 long video (fair-use caps) and the QA/private upload. Hours are only counted for streams the system actually processes.

| Plan | Price/mo | Credits (stream hours) | Price per credit | Seats |
|---|---|---|---|---|
| Free trial | 0 | 2 (one time) | | 1 |
| Starter | 19 USD | 12 | 1.58 | 1 |
| Creator | 49 USD | 40 | 1.23 | 2 |
| Pro / small agency | 129 USD | 120 | 1.07 | 5 |
| Extra credits | 1.50 USD each in packs of 10 | | 1.50 | |
Annual: 2 months free [E]. A viewer seat is free (approvals by managers).

Margins after the Paddle/Lemon Squeezy fee (5% + 0.50 USD) and COGS at 100% credit use [E]:

| | Starter | Creator | Pro |
|---|---|---|---|
| Fee | 1.45 | 2.95 | 6.95 |
| COGS low (0.06/h) | 0.72 -> margin 16.8 USD (89%) | 2.4 -> 43.7 (89%) | 7.2 -> 114.9 (89%) |
| COGS base (0.17/h) | 2.04 -> 15.5 USD (82%) | 6.8 -> 39.3 (80%) | 20.4 -> 101.7 (79%) |
| COGS high (0.68/h) | 8.16 -> 9.4 USD (49%) | 27.2 -> 18.9 (38%) | 81.6 -> 40.5 (31%) |

Fixed costs to cover (base): server about 70 USD/month, domain/email few USD, Cloudflare Workers Paid 5 USD (needed anyway: the free KV plan allows only 1,000 writes per day [V], one job already needs about 10 writes), legal templates one-off. Break-even is about 5 paying customers on the dedicated box [E]; before that the owner's PC.

Comparison: OpusClip Pro costs about 5.8 USD per source hour [E from S]; we are about 4-5x cheaper per hour but sell by "stream" not "video minute", and a streamer's real usage will be higher than a podcaster's. Review the price after 3 months of real COGS; the base case LLM figure is the largest uncertainty.

Guardrails: cap a single job (for example 8 source hours), hold credits at creation (already in the skeleton), refund on failure (done), reject sources not belonging to the verified channel, rate limit assistant requests.

---

## 6. Honest risk list

1. **YouTube quota and audit (high):** 100 uploads/day per project and an audit with no promised timeline cap us at about 3 heavy customers until approved; an audit can fail or YouTube can revoke API access (terms: termination at will, change of control notification) [V]. Mitigation: apply now, keep uploads low (fewer, better videos per stream), design a fallback where the customer downloads a ZIP of drafts.
2. **Google OAuth verification (high for launch):** unverified apps are capped and show a warning; needs a real domain, privacy policy, demo video, review time [V/S/U].
3. **Platform terms (high):** Kick 1.4 forbids automated access [V]; Twitch has no VOD download API [S]. Customer-side restream or file/link upload is the compliant route; otherwise a platform can block us overnight.
4. **GitHub account risk today (medium-high):** existing loops may already be outside Actions terms [V]; a suspension would kill the owner's live pipeline. Migrate first.
5. **Quality (high):** no evidence yet that picks beat competitors or that Hebrew RTL captions are better; competitor tests show about 40% of AI clips are discarded [S]. Draft-and-approve masks bad picks but costs customers time. Measure acceptance rate per customer and show it.
6. **Cost overrun (medium):** a customer pasting a 12-hour stream, high-cost model, idle servers. Hold credits, cap duration, per-job budget stop.
7. **Copyright claims (medium):** music and third-party footage in streams produce Content ID claims on the customer's channel and DMCA complaints; needs terms, DMCA agent, takedown process; consult a lawyer [U].
8. **YouTube policy (medium):** inauthentic/mass-produced content enforcement; gambling content limits [S][U].
9. **Payments/tax (medium):** Paddle approval not guaranteed; Israeli tax treatment unverified; chargebacks and refunds policy needed.
10. **Market size (medium):** Hebrew-language streamers are few; English streamers are the large market but also the crowded one. Decide early whether to localise (English UI exists as fallback in the skeleton).
11. **Single operator (medium):** support, uptime, security incidents (stored OAuth refresh tokens are the crown jewels: encrypt, minimise, revoke-on-delete).
12. **Architecture debt (medium):** KV is not transactional, so credits and claims need D1 before real money; the skeleton marks every place `TODO(D1)`.
13. **Default-public upload regression (medium):** from 2 Nov 2026 an omitted `privacyStatus` means public [V]; add a unit test that every upload call sets private.
14. **Refresh tokens expiring/revoked:** customers revoke or Google invalidates tokens; the worker must detect `invalid_grant`, pause the channel and tell the customer.
15. **Unverified from the sandbox (see section 8)**: several vendor pages could not be read.

## 7. Suggested sequence (no spending until revenue)

1. Week 1: apply for the YouTube audit/quota (needs privacy/terms pages hosted on the Worker: `/studio/privacy`, `/studio/terms`), create a separate Google Cloud project, start OAuth verification with the demo video, register the DMCA agent, choose Paddle vs Lemon Squeezy and submit the account.
2. Week 1-3: build the render daemon on the owner's PC, move the owner channel to it, make the repo private, build Google OAuth and the encrypted token store, D1 migration for credits/jobs.
3. Week 3-5: closed beta with 3-5 streamers (free credits), Kick/Twitch OAuth login for ownership, restream ingest option, measure approval rate and real COGS.
4. Week 5-8: payments live, pricing review, first paid customers, then rent the dedicated server.

## 8. What I could not verify (hosts blocked in this sandbox or no primary source)

Not reachable: dev.twitch.tv and legal.twitch.com (Twitch Developer Services Agreement, Helix reference, VOD retention), stripe.com (country support and fees), paddle.com / developer.paddle.com and docs.lemonsqueezy.com (country lists, fees, payout fees), hetzner.com and docs.hetzner.com (current prices after the 15 Jun 2026 increase), modal.com, fly.io, groq.com pricing (numbers via search), opus.pro (official pricing), help.kick.com (VOD retention), claude.ai pages. To re-check these the hosts have to be allowed in the session's network settings. Also unverified: YouTube audit duration, OAuth verification duration, the exact user cap and token lifetime of unverified apps, Oracle's current free allowance, Israeli tax rules (osek patur ceiling, export of services), whether competitors' Hebrew/RTL captions are good, real hit rates, and Twitch EventSub details.

## 9. Sources

Primary (read in full or in part today):
* YouTube Data API, Quota and Compliance Audits: https://developers.google.com/youtube/v3/guides/quota_and_compliance_audits
* YouTube Data API, quota calculator / costs: https://developers.google.com/youtube/v3/determine_quota_cost
* YouTube Data API revision history (2 Nov 2026 privacy default, 1 Jun 2026 buckets, 4 Dec 2025 cost cut): https://developers.google.com/youtube/v3/revision_history
* YouTube API Services Developer Policies: https://developers.google.com/youtube/terms/developer-policies ; Terms of Service: https://developers.google.com/youtube/terms/api-services-terms-of-service
* Google OAuth sensitive scope verification: https://developers.google.com/identity/protocols/oauth2/production-readiness/sensitive-scope-verification ; OAuth scopes: https://developers.google.com/identity/protocols/oauth2/scopes
* GitHub Additional Product Terms (Actions): https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features (source text: https://github.com/github/docs/blob/main/content/site-policy/github-terms/github-terms-for-additional-products-and-features.md); Actions billing: https://docs.github.com/en/actions/concepts/billing-and-usage
* Kick developer docs: https://docs.kick.com/ (scopes, channels, events); Kick Terms of Service: https://kick.com/terms-of-service
* Cloudflare pricing: Containers https://developers.cloudflare.com/containers/pricing/ ; Workers AI https://developers.cloudflare.com/workers-ai/platform/pricing/ ; R2 https://developers.cloudflare.com/r2/pricing/ ; KV https://developers.cloudflare.com/kv/platform/pricing/
* Groq rate limits: https://console.groq.com/docs/rate-limits
* Oracle Free Tier overview: https://www.oracle.com/cloud/free/
* Claude model prices (cached table in the claude-api skill, 3 Nov 2026): https://platform.claude.com/docs/en/about-claude/pricing

Secondary (search summaries, not verified at the source):
* OpusClip pricing: https://creatify.ai/blog/opusclip-pricing-plans-and-what-you-ll-actually-pay-in-2026 , https://eesel.ai/blog/opusclip-pricing , https://www.castmagic.io/blog/opus-clip-pricing
* Klap/Vizard/Submagic: https://openclip.app/alternatives/klap-alternatives , https://fluxnote.io/guides/submagic-pricing-2026 , https://toolradar.com/tools/submagic/pricing
* Eklipse/StreamLadder/Streamlabs: https://eklipse.gg/compare/eklipse-vs-streamladder/ , https://www.twoaveragegamers.com/eklipse-review-2026-hands-on-testing-for-streamers/
* Complaints: https://bigvu.tv/blog/opus-clip-tested-2026-where-ai-wins-40-percent-discard/ , https://autoclip.dev/blog/why-gaming-clippers-outgrow-opus-clip-and-munch , https://www.twoaveragegamers.com/opusclip-review-2026-great-tool-wrong-hype-for-gamers/ , https://www.opus.pro/blog/twitch-vod-to-clips-api
* Hebrew subtitles (Submagic): https://www.submagic.co/auto-subtitle-generator/hebrew-subtitles
* Twitch VOD API forum: https://discuss.dev.twitch.tv/t/download-vods-via-api-or-other-means/28490 ; Twitch OIDC: https://dev.twitch.tv/docs/authentication/getting-tokens-oidc/
* Kick VOD retention: https://help.kick.com/en/articles/7112432-kick-stream-replays-vods
* GitHub self-hosted runner fee postponed: https://www.theregister.com/2025/12/17/github_charge_dev_own_hardware/ , https://socket.dev/blog/github-actions-pricing-whiplash
* Hetzner: https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/ , https://www.bitdoze.com/hetzner-cloud-cost-optimized-plans/
* Oracle free tier changes: https://linuxiac.com/?p=214114 , https://docs.oracle.com/iaas/Content/FreeTier/resourceref.htm
* Modal pricing: https://dupple.com/learn/modal-pricing
* Groq whisper prices: https://groq.com/pricing
* Stripe in Israel: https://adircpa.com/en/guides/stripe-israel-tax , https://startglobal.co/us/international/israel/stripe/
* Paddle/Lemon Squeezy: https://developer.paddle.com/concepts/sell/supported-countries-locales , https://docs.lemonsqueezy.com/help/getting-started/supported-countries , https://fungies.io/paddle-vs-lemon-squeezy
* YouTube inauthentic content: https://www.plagiarismtoday.com/2025/07/08/youtube-targets-inauthentic-content/ , https://ppc.land/youtube-clarifies-inauthentic-content-policy-changes/
* DMCA agent registration: https://www.copyright.gov/title37/201/37cfr201-38.html
* Gemini pricing (third-party): https://developer.puter.com/tutorials/gemini-api-pricing/

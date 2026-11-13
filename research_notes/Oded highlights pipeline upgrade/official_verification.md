# Official-source verification of pipeline-upgrade claims (as of 2026-11-13)

Method note. Pages were fetched with curl through the session proxy (WebFetch could not resolve most hosts, but curl via the proxy could). All quotes below are copied from the primary page text as fetched on 2026-11-13.
Host reachability:
- Reached: developers.google.com, support.google.com, console.groq.com, docs.kick.com, kick.com, docs.github.com, huggingface.co.
- NOT reachable (proxy answered 403 to CONNECT, so a host-allowlist block): docs.aws.amazon.com and aws.amazon.com. Also help.kick.com (the Kick help center). github.com and api.github.com returned 403, so AWS doc sources on GitHub could not be read either. These hosts need to be added to the session network allowlist before items 6 (VOD retention) and 7 can be verified.

Headline surprises versus earlier snippet-based research:
1. YouTube removed the unverified-project private lock on 2026-11-02 (11 days ago). The YouTube Help page "Videos locked as private" still describes the old lock, so the official pages CONFLICT.
2. YouTube Data API quota is no longer one pool. Since 2026-06-01 `videos.insert` has its own bucket of 100 calls/day at 1 unit each, and the old "1600 units per upload" is gone (about 100 units, per a 2025-12-04 note, then superseded by the bucket model).
3. Groq free-tier whisper limits are 20 RPM, 2K RPD, 7.2K audio-seconds/hour and 28.8K audio-seconds/day. That is only 8 hours of audio per day.

---

## 1. YouTube: unverified-project private lock, revision history, audit form

### Takeaway
VERIFIED: the Data API revision history says that on November 2, 2026 YouTube reversed the 2020 policy, so videos from unverified API projects are no longer forced private, and the `videos.insert` reference now says so. CONFLICTING: the YouTube Help article "Videos locked as private" still lists the unverified-API lock, apparently not yet updated. The Audit and Quota Extension Form is a quota/compliance audit and is not required for uploading any more.

### Cited Findings
- VERIFIED (revision history, entry "November 2, 2026"): "Videos uploaded through the videos.insert method from unverified API projects are no longer restricted to private viewing mode. This change reverses the policy announced on July 28, 2020, which restricted videos uploaded from unverified API projects created after that date to private viewing mode until the project completed an audit. If you don't specify a value for the status.privacyStatus property in a videos.insert request, the uploaded video's privacy status defaults to public. Certain uploads might default to private based on creator account settings, as explained in the YouTube Help Center." — [YouTube Data API revision history](https://developers.google.com/youtube/v3/revision_history) (resolves to /youtube/data/revision_history; page "Last updated 2026-11-12 UTC")
- VERIFIED (original 2020 policy, same page, entry "July 28, 2020"): "All videos uploaded using the videos.insert endpoint from unverified API projects created after 28 July 2020 will be restricted to private viewing mode. To lift this restriction, each project must undergo an audit to verify compliance with the Terms of Service." Projects created before 28 July 2020 were not affected. — [revision history](https://developers.google.com/youtube/v3/revision_history)
- VERIFIED (videos.insert reference, "status.privacyStatus" row): "If you don't specify a value for this property, the uploaded video's privacy status defaults to public. Certain uploads might default to private based on creator account settings, as explained in the YouTube Help Center. Videos uploaded from unverified API projects are not restricted to private viewing mode." — [videos.insert](https://developers.google.com/youtube/v3/docs/videos/insert) (page "Last updated 2026-11-12 UTC")
- The "creator account settings" default refers to the YouTube Help page it links: "The default video privacy setting for creators aged 13–17 is private. If you're 18 or older, your default video privacy setting is set to public." — [YouTube Help, Upload videos / visibility](https://support.google.com/youtube/answer/157177)
- CONFLICTING: the YouTube Help article still reads: "For videos that have been locked as private due to upload via an unverified API service, you will not be able to appeal. You'll need to re-upload the video via a verified API service or via the YouTube app/site. The unverified API service can also apply for an API audit." and lists "Has been uploaded by an unverified third party API service" among things to avoid. The page has no visible date. — [Videos locked as private](https://support.google.com/youtube/answer/7300965). The dated developer revision-history entry (2026-11-02) and the reference page (updated 2026-11-12) are newer and more specific, so treat the Help article as stale. Still, this is a very recent change.
- Other 2025-2026 revision-history entries relevant to uploads:
  - 2026-11-03: "The thumbnails.set method now supports uploading custom thumbnails for YouTube Shorts after video processing is complete."
  - 2026-09-14: thumbnails.set maximum file size "has increased from 2MB to 50MB."
  - 2026-07-07: new `brandPartner` part on videos.insert/update/list.
  - 2026-06-01: granular quota transition (see item 2).
  - 2025-12-04: "reflect a change in the quota cost of a video upload from approximately 1600 units to approximately 100 units."
  - Source for all: [revision history](https://developers.google.com/youtube/v3/revision_history)
- videos.insert limits: "Maximum file size: 256GB. Accepted Media MIME types: video/*, application/octet-stream". Scopes: youtube.upload, youtube, youtubepartner, youtube.force-ssl. — [videos.insert](https://developers.google.com/youtube/v3/docs/videos/insert)
- Audit form mechanics. The guide says: "If you would like to request additional quota beyond the default allocation, you must first complete an audit to show that your project is in compliance with the YouTube API Services Terms of Service... To begin an audit of your project, fill out and submit the YouTube API Services - Audit and Quota Extension Form. A member of YouTube's API Services team will contact you as soon as possible." Other tracks: "If you have completed an API Compliance Audit within the last 12 months but require an additional quota extension, fill out and submit the Audit and Quota Extension Form"; an Appeals Form for failed audits; a Periodic Audit Form; a Change of Control Form. — [Quota and Compliance Audits](https://developers.google.com/youtube/v3/guides/quota_and_compliance_audits) (updated 2026-11-12)
- The form itself (live page) says: "This form collects information about your business, your API Client(s), and how you use YouTube API Services... All requests for additional quota requests must go through a compliance audit. We also conduct periodic re-audits." It offers two reasons: "Complete a compliance audit to request for additional quota" or "Complete a compliance audit to keep current quota (requested to complete re-audit)". It asks for organization and contact info, API client name (must not contain "YouTube" without written approval), public URL, privacy policy URL, a homepage screenshot showing the privacy policy link with YouTube branding, ToS documentation, optional demo account credentials, and a per-endpoint quota request. It also warns: "your application must comply with our developer policies including demonstrating significant independent value to the YT ecosystem and its users. Applications that are unable to meet requirements may not be granted additional quota." — [Audit and Quota Extension Form](https://support.google.com/youtube/contact/yt_api_form)
- The form lets you request quota for `search.list` and `videos.insert` separately from the general pool: "This quota can be used for all endpoints except search.list and videos.insert. If you need additional quota for search.list and videos.insert you must specify the quota required for each of these methods separately." — [form](https://support.google.com/youtube/contact/yt_api_form)

### Inferences
- A personal, single-channel uploader on an unverified project should now be able to publish public/unlisted videos via the API without an audit. This relies on the 2026-11-02 entry. Because the Help article still says otherwise and the change is under two weeks old, run a live test upload with `privacyStatus=unlisted` or `public` and confirm the video is not "locked as private" before relying on it.
- An audit is only needed for more than 100 uploads/day or more than 10,000 other units/day, which is unlikely for this pipeline.

### Gaps
- The form page does not state a turnaround time. No official review time was found.
- Whether a project created before 2020-07-28 versus after matters now is moot, because the restriction was reversed for all.
- The Help article's last-edited date is not shown on the page.

---

## 2. YouTube Data API quota

### Takeaway
VERIFIED: default is now 10,000 units/day for all endpoints except two separately metered methods. `videos.insert` has its own bucket of 100 calls/day at 1 unit per call. `thumbnails.set`, `videos.update` and `playlistItems.insert` each cost 50 units from the 10,000 pool.

### Cited Findings
- VERIFIED: "Projects that enable the YouTube Data API have a default quota allocation of 100 search.list calls, 100 videos.insert calls, and 10,000 units per day combined for all other endpoints... Daily quotas reset at midnight Pacific Time (PT)." Also "The search.list and videos.insert methods have their own quota buckets. Each of these methods has a default daily limit of 100 per day. The quota cost is 1 per call." and "All API requests, including invalid requests, incur a quota cost of at least one point." — [Quota Calculator](https://developers.google.com/youtube/v3/determine_quota_cost) (updated 2026-11-12)
- Costs from the same table: videos.insert "100 quota per day. Each call costs 1 quota."; thumbnails.set 50; videos.update 50; playlistItems.insert 50; videos.list 1; playlistItems.list 1; captions.insert 400; captions.update 450; captions.list 50; channels.list 1; liveBroadcasts/liveStreams 1; search.list "100 quota per day. Each call costs 1 quota." — [Quota Calculator](https://developers.google.com/youtube/v3/determine_quota_cost)
- Per-method pages agree: videos.insert "Quota impact: 100 calls per day. A call to this method has a quota cost of 1 unit in the Video Uploads quota bucket." — [videos.insert](https://developers.google.com/youtube/v3/docs/videos/insert). thumbnails.set "has a quota cost of approximately 50 units" and "Maximum file size: 50MB" — [thumbnails.set](https://developers.google.com/youtube/v3/docs/thumbnails/set). videos.update "quota cost of 50 units" — [videos.update](https://developers.google.com/youtube/v3/docs/videos/update). playlistItems.insert "quota cost of 50 units" — [playlistItems.insert](https://developers.google.com/youtube/v3/docs/playlistItems/insert)
- Change history: 2026-06-01 "The YouTube Data API is transitioning to a granular quota system covering smaller sets of methods, starting with videos.insert and search.list... API calls to the videos.insert and search.list methods will be charged to their own respective quota buckets. API calls to all other methods will be charged to the existing quota bucket... they can request additional quota through the Quota Extension Form." 2025-12-04: upload cost cut "from approximately 1600 units to approximately 100 units." Also 2026-06-03: new `videos.batchGetStats` costs 1 unit in its own bucket with 10,000/day default. — [revision history](https://developers.google.com/youtube/v3/revision_history)
- So the "separate per-day upload cap" is VERIFIED: 100 uploads/day per project by default (the videos.insert bucket), extendable only via the audit form.
- Example budget (arithmetic from the table): one clip with upload + thumbnail + playlist add = 1 insert-bucket unit + 50 + 50 = 100 units from the 10,000 pool, so about 100 such clips/day, also capped at 100 inserts/day. Adding a `videos.update` (50) gives 150 units per clip, about 66 clips/day.

### Inferences
- For a pipeline producing a handful of highlights per stream, the default quota is ample.
- The 100/day insert cap is project-wide, not per channel.

### Gaps
- Separate per-channel daily upload limits imposed by YouTube itself (account verification, "daily upload limit" in YouTube Help) were not checked here; they are channel-level policy, not API quota.

---

## 3. Google OAuth refresh-token expiry, 100-user cap, warning screen

### Takeaway
VERIFIED: refresh tokens issued to apps in "Testing" with an external user type expire after 7 days (apart from basic profile scopes). Official docs list no time-based expiry for "In production" apps other than 6 months of non-use, revocation, policy and limits. The 100-new-user cap applies to unverified apps in production that use sensitive/restricted scopes. NOT FOUND: any official statement that production-unverified apps get shorter-lived refresh tokens.

### Cited Findings
- VERIFIED (token expiry list): "A refresh token might stop working for one of these reasons: The user has revoked your app's access. The refresh token has not been used for six months. The user changed passwords and the refresh token contains Gmail scopes. The user account has exceeded a maximum number of granted (live) refresh tokens. The user granted time-based access to your app and the access expired. If an admin set any of the services requested in your app's scopes to Restricted (the error is admin_policy_enforced). For Google Cloud Platform APIs - the session length set by the admin could have been exceeded." — [OAuth 2.0 for Google APIs](https://developers.google.com/identity/protocols/oauth2) (updated 2026-10-29)
- VERIFIED (Testing): "A Google Cloud Platform project with an OAuth consent screen configured for an external user type and a publishing status of 'Testing' is issued a refresh token expiring in 7 days, unless the only OAuth scopes requested are a subset of name, email address, and user profile." — [OAuth 2.0 for Google APIs](https://developers.google.com/identity/protocols/oauth2)
- VERIFIED (Testing, support page): "Projects configured with a publishing status of Testing are limited to up to 100 test users... Authorizations by a test user will expire seven days from the time of consent. If your OAuth client requests an offline access type and receives a refresh token, that token will also expire." and Google "will display a warning message before allowing a specified test user to authorize scopes". — [Manage App Audience](https://support.google.com/cloud/answer/15549945)
- VERIFIED (In production): "Projects configured with a publishing status of In production are available to any user with a Google Account... Google will display an Unverified apps warning message if your project's OAuth clients request authorization of scopes considered sensitive or restricted before your project has completed verification for those scopes." — [Manage App Audience](https://support.google.com/cloud/answer/15549945)
- VERIFIED (cap): table row "New user cap | Apps that present the unverified app screen to users | 100 new users in total, after the app presents the unverified app screen" (that is, a lifetime count, not a daily one). "These might be adjusted for specific apps based on the app history, developer reputation, and riskiness." Warning screen triggers include "Your app uses sensitive or restricted scopes and you haven't configured them in your OAuth consent screen configuration page and requested verification" and "...requested verification, but the verification is not yet complete." Also: "Depending on the sensitivity of the data being requested, verification might require several months." — [Unverified apps](https://support.google.com/cloud/answer/7454865)
- Limit on live tokens: "There is currently a limit of 100 refresh tokens per Google Account per OAuth 2.0 client ID. If the limit is reached, creating a new refresh token automatically invalidates the oldest refresh token without warning." — [OAuth 2.0 for Google APIs](https://developers.google.com/identity/protocols/oauth2)
- Unverified-app exemption: apps used only by their developer's own account are covered by "Apps in development: if your app is experimental or a test build, you don't need to go through verification unless you decide to launch it to the public." — [Unverified apps](https://support.google.com/cloud/answer/7454865)
- Scope sensitivity: the scopes page says "Sensitive scopes, indicated in the Google Cloud Console, require review by Google." It lists `youtube.upload` as "Manage your YouTube videos" but the fetched text does not show its sensitivity label. — [OAuth 2.0 Scopes](https://developers.google.com/identity/protocols/oauth2/scopes)

### Inferences
- The most practical setup for a single-owner pipeline: set the consent screen to "In production" (not "Testing") so refresh tokens do not die after 7 days. The user (the channel owner) clicks through the unverified-app warning once, which counts toward the 100-new-user cap but leaves plenty of room for one user. Keep the token in use at least once every six months.
- Inference, not stated in the docs: with the 100-user cap, a pipeline serving only the owner's own Google account would never reach the cap.

### Gaps
- NOT FOUND: an explicit official statement on whether refresh tokens for sensitive scopes in "In production + unverified" apps expire earlier than the generic rules above. The docs list none, so by omission they follow the general rules, but this is an inference from absence.
- NOT FOUND: the "inactivity expiry" beyond the six-month rule above; no shorter inactivity window is documented.
- The sensitivity classification of `youtube.upload` was not confirmed from text (it is shown by an icon in the Cloud Console).

---

## 4. Groq Whisper limits (free tier)

### Takeaway
VERIFIED: free-tier limits for both `whisper-large-v3` and `whisper-large-v3-turbo` are 20 requests/min, 2,000 requests/day, 7,200 audio-seconds/hour (2 h) and 28,800 audio-seconds/day (8 h). The max file is 25 MB. Word-level timestamps are supported, and `prompt` is capped at 224 tokens.

### Cited Findings
- VERIFIED (rate limits table, "Free Plan Limits" tab, columns MODEL ID, RPM, RPD, TPM, TPD, ASH, ASD): `whisper-large-v3` 20 / 2K / - / - / 7.2K / 28.8K; `whisper-large-v3-turbo` 20 / 2K / - / - / 7.2K / 28.8K. The "Free Plan Limits" tab is the active default tab in the page HTML. Page definitions: "ASH: Audio seconds per hour; ASD: Audio seconds per day"; "Rate limits apply at the organization level". — [Groq Rate Limits](https://console.groq.com/docs/rate-limits)
- The same page embeds a Developer-plan table (not shown on the default tab; read from the page's embedded data): `whisper-large-v3` 300 RPM / 200K RPD / ASH 200K / ASD 4M; `whisper-large-v3-turbo` 400 RPM / 200K RPD / ASH 400K / ASD 4M. The prose says "Upgrade to Developer plan to access higher limits, Batch and Flex processing, and more." The page also says "The following is a high level summary and there may be exceptions to these limits. You can view the current, exact rate limits for your organization on the limits page in your account settings." — [Groq Rate Limits](https://console.groq.com/docs/rate-limits)
- Caveat: a sentence on the same page says "the limits shown below are the base limits for the Developer plan". With the tab labelling it is ambiguous which plan the default rendered table belongs to. The page data and the tab structure point to the table above being the Free plan (the Developer values are much higher), but confirm in the account Limits page.
- VERIFIED (speech-to-text page): "Max File Size: 25 MB (free tier), 100MB (dev tier)"; "Max Attachment File Size: 25 MB. If you need to process larger files, use the url parameter to specify a url to the file instead."; "Minimum File Length 0.01 seconds"; "Minimum Billed Length 10 seconds"; "Supported File Types: flac, mp3, mp4, mpeg, mpga, m4a, ogg, wav, webm"; "Only the first track will be transcribed for files with multiple audio tracks"; "Supported Response Formats: json, verbose_json, text". Audio is downsampled "to 16KHz mono". Recommended reduction: FLAC (lossless). — [Groq Speech to Text](https://console.groq.com/docs/speech-to-text)
- VERIFIED: "Supported Timestamp Granularities: segment, word". Parameter doc: "timestamp_granularities[] ... Either or both of word and segment are supported. segment returns full metadata and word returns only word, start, and end timestamps." `response_format` must be `verbose_json` to use granularities. — [Groq Speech to Text](https://console.groq.com/docs/speech-to-text)
- VERIFIED: "prompt ... Prompt to guide the model's style or specify how to spell unfamiliar words. (limited to 224 tokens)"; "The prompt parameter (max 224 tokens) helps provide context and maintain a consistent output style." The transcription `language` parameter takes ISO-639-1 codes. — [Groq Speech to Text](https://console.groq.com/docs/speech-to-text)
- Model comparison table on the page: `whisper-large-v3` "$0.111" per hour, WER 10.3%, speed factor 189; `whisper-large-v3-turbo` "$0.04" per hour, WER 12%, speed factor 216. Turbo does transcription only (translation: No). — [Groq Speech to Text](https://console.groq.com/docs/speech-to-text)

### Inferences
- 28,800 audio-seconds/day = 8 hours of audio/day on free tier; 7,200/hour means a single 2-hour stream consumes the whole hourly budget. The unbilled "10-second minimum" also counts toward ASH/ASD presumably (not stated for limits), so chunking into very short pieces wastes quota.
- A 25 MB file cap means long streams need to be chunked or compressed (for example, 16 kHz mono FLAC or Opus) before upload.
- The 224-token prompt cap restricts how much Hebrew vocabulary or name hinting can be passed.

### Gaps
- Groq's docs do not publish Hebrew-specific accuracy; the WER numbers above are generic (see item 8 for Hebrew-specific benchmarks).
- Whether the minimum billed 10 seconds counts against ASH/ASD was not found.

---

## 5. GitHub Actions limits and terms

### Takeaway
VERIFIED: standard GitHub-hosted runners are free and unlimited on public repositories; a job may run up to 6 hours; the free plan allows 20 concurrent jobs; scheduled workflows may be delayed or dropped at high load; public-repo schedules are auto-disabled after 60 days without repository activity. The Additional Product Terms bar using Actions as a content delivery network or as part of a serverless application, and any activity unrelated to the software project on GitHub-hosted runners.

### Cited Findings
- VERIFIED (cost): "GitHub Actions usage is free for standard GitHub-hosted runners in public repositories, and for self-hosted runners." — [Billing and usage](https://docs.github.com/en/actions/concepts/billing-and-usage). "Use of the standard GitHub-hosted runners is free and unlimited on public repositories." — [GitHub-hosted runners reference](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
- VERIFIED (public-repo runner specs): `ubuntu-slim` 1 CPU / 5 GB RAM / 14 GB SSD (single-CPU runners are containers on a shared VM); `ubuntu-latest` / `ubuntu-24.04` / `ubuntu-22.04` / `ubuntu-26.04` 4 CPU / 16 GB / 14 GB SSD x64; Windows x64 4 CPU / 16 GB; Linux arm64 4 CPU / 16 GB; macOS Intel 4 CPU / 14 GB; macOS M1 3 CPU / 7 GB. (Private repos get 2 CPU / 8 GB.) No GPU. — [GitHub-hosted runners reference](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
- VERIFIED (limits table): "All GitHub-hosted runners | Job execution time | 6 hours | Each job in a workflow can run for up to 6 hours of execution time. If a job reaches this limit, the job is terminated and fails." "Workflow run time: 35 days / workflow run". "Job Matrix: 256 jobs / workflow run". "Workflow trigger event rate limit: 1500 events / 10 seconds / repository". Cache: 200 uploads/min, 1500 downloads/min per repo. — [Actions limits](https://docs.github.com/en/actions/reference/limits)
- VERIFIED (concurrency): "Standard GitHub-hosted runner | Free | Total concurrent jobs 20 | Max concurrent macOS jobs 5"; Pro 40; Team 60; Enterprise 500. "GitHub Support can increase job concurrency limits." — [Actions limits](https://docs.github.com/en/actions/reference/limits)
- VERIFIED (storage by plan): GitHub Free: artifact storage 500 MB, cache storage 10 GB per repository, included compute for private repos $12. "GitHub Support cannot increase storage limits for GitHub Actions." — [Actions limits](https://docs.github.com/en/actions/reference/limits)
- VERIFIED (scheduled workflows): "The schedule event can be delayed during periods of high loads of GitHub Actions workflow runs. High load times include the start of every hour. If the load is sufficiently high enough, some queued jobs may be dropped. To decrease the chance of delay, schedule your workflow to run at a different time of the hour." "Scheduled workflows will only run on the default branch." "In a public repository, scheduled workflows are automatically disabled when no repository activity has occurred in 60 days." "The shortest interval you can run scheduled workflows is once every 5 minutes." The default timezone is UTC, and an IANA timezone can be specified. A deactivated schedule can be re-enabled by a write-access user committing a change to the cron line. — [Events that trigger workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)
- VERIFIED (terms), GitHub Terms for Additional Products and Features, version effective August 27, 2026, section "Actions": "Actions and any elements of the Actions product or service may not be used in violation of the Agreement, the GitHub Acceptable Use Policies, or the GitHub Actions service limitations... Additionally, regardless of whether an Action is using self-hosted runners, Actions should not be used for: Cryptomining; Disrupting, gaining, or attempting to gain unauthorized access to, any service...; The provision of a stand-alone or integrated application or service offering the Actions product or service... for commercial purposes; Any activity that places a burden on our servers, where that burden is disproportionate to the benefits provided to users (for example, don't use Actions as a content delivery network or as part of a serverless application, but a low benefit Action could be ok if it's also low burden); or If using GitHub-hosted runners, any other activity unrelated to the production, testing, deployment, or publication of the software project associated with the repository where GitHub Actions are used." And: "Misuse of GitHub Actions may result in termination of jobs, restrictions in your ability to use GitHub Actions, disabling of repositories created to run Actions in a way that violates these Terms, or in some cases, suspension or termination of your GitHub account." — [GitHub Additional Product Terms](https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features)
- VERIFIED (AUP, section 9 "Excessive Bandwidth Use"): "If we determine your bandwidth usage to be significantly excessive in relation to other users of similar features, we reserve the right to suspend your Account, throttle your file hosting, or otherwise limit your activity..." and the AUP also bars "excessive automated bulk activity". — [GitHub Acceptable Use Policies](https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies)

### Inferences
- A pipeline that downloads livestream video, transcribes it and uploads clips to YouTube from GitHub-hosted runners is arguably "unrelated to the production, testing, deployment, or publication of the software project associated with the repository". That wording is explicit for GitHub-hosted runners, and media processing is a grey-to-red area under the Additional Product Terms. It is a policy risk, not a technical block. The document gives no safe-harbour for personal media pipelines, so use self-hosted runners or other compute if account risk matters. Self-hosted runners remove only the final bullet; the burden/CDN/serverless bullets still apply.
- At 6 h job max and 14 GB SSD, a multi-hour VOD download plus intermediates must stream or be cleaned up. A 7.2K ASH Groq budget would also pace runs.

### Gaps
- No exact numeric bandwidth threshold in the AUP; "significantly excessive in relation to other users" is relative.
- Hosted runner network egress limits are not stated.

---

## 6. Kick public API, ToS on automated access, VOD retention

### Takeaway
VERIFIED: Kick has an official public API (base https://api.kick.com) with livestream, channel and webhook-event endpoints, OAuth 2.1 with app or user tokens. NOT FOUND: any documented API rate limit, any VOD/replay endpoint, or official VOD retention days (the Kick help center is blocked in this session). VERIFIED: the Kick ToS prohibits scraping and automated access to the Service by means not provided or authorized.

### Cited Findings
- VERIFIED (endpoints): `GET /public/v2/livestreams` ("Get active livestreams. Supports cursor pagination. Livestreams are sorted from oldest to newest"; filters: category_id up to 25, language_code up to 25, `limit` default 100 max 1000, cursor); `GET /public/v1/users/livestreams` (user_id up to 100); `GET /public/v1/livestreams/stats`; the V1 `GET /public/v1/livestreams` is "deprecated"; `GET/PATCH /public/v1/channels` (up to 50 broadcaster_user_id or slugs per call; the response includes a `stream` object with fields including is_live, start_time, viewer_count, thumbnail, url, key). — [Livestreams](https://docs.kick.com/apis/livestreams), [Channels](https://docs.kick.com/apis/channels) (via the .md versions)
- VERIFIED (changelog): 2026-06-23 "Added pagination supported Livestreams V2 endpoint. The Livestreams V1 endpoint is now deprecated."; 2026-07-03 livestreams by user IDs added, "Livestreams V1 should now be completely migrated off"; 2026-11-08 Get Channels `active_subscribers_count` now includes gifted subs. — [Kick changelog](https://docs.kick.com/changelog)
- VERIFIED (auth): two token types. "App Access Tokens are generated through the Client Credentials flow. These server-to-server API tokens... can access publicly available data and are ideal for use when user login is not required." "User Access Tokens are generated through the Authorization Grant flow." Endpoints accept either (OpenAPI "security: UserAccessToken or AppAccessToken"); OAuth token URL `https://id.kick.com/oauth/token`; PKCE (SHA-256) used for the user flow. Scopes include `channel:read`, `user:read`, `events:subscribe`, `streamkey:read`. — [OAuth 2.1](https://docs.kick.com/getting-started/generating-tokens-oauth2-flow), [Scopes](https://docs.kick.com/getting-started/scopes)
- VERIFIED (webhooks): `POST /public/v1/events/subscriptions` ("Subscribe to events via webhooks. There is a subscription limit of 10,000 per event type for a single app. For the 'chat.message.sent' event, there is a limit of 1,000 for unverified apps."); App access tokens can subscribe to any channel by user ID. Event `livestream.status.updated` v1 fires "when a stream's status has been updated. For example, a stream could have started or ended" with payload fields `is_live`, `title`, `started_at`, `ended_at`; `livestream.metadata.updated` also exists. The webhook URL must be publicly reachable over the internet. Signatures: RSA/SHA-256 over `messageID.timestamp.body`, with the public key fetched from `https://api.kick.com/public/v1/public-key`. "If an app's webhook continually fails to process an event for over a day, Kick automatically unsubscribes the app from that event." — [Webhook Payloads](https://docs.kick.com/events/event-types), [Subscribe to Events](https://docs.kick.com/events/subscribe-to-events), [Webhook security](https://docs.kick.com/events/webhook-security), [Events introduction](https://docs.kick.com/events/introduction)
- NOT FOUND: any statement of request rate limits anywhere in the docs (searched the OAuth, livestream, channel, webhook, FAQ and changelog pages for "rate"/"limit"; the only limits are the subscription and page-size limits above). The docs index (llms.txt) lists no VOD/replay/clip endpoint. The only apparent route to the live HLS is the channel `stream.url`/`key` fields, which, per the scope description, relate to a channel's own RTMP ingest ("streamkey:read: Read a user's stream URL and stream key"), so they are not a viewer playback URL. This is my reading of the field names and was not otherwise confirmed.
- VERIFIED (Kick Terms of Service, "Date Modified: 23 March 2026"), prohibited activities: "(a) copying, distributing, or disclosing any part of the Service in any medium, including by any automated or non-automated 'scraping'; (b) using any automated system, including 'robots,' 'spiders,' 'offline readers,' etc. to access any part of the Service in any medium (except... public search engines...); ... (e) taking any action that imposes, or may impose at our sole discretion an unreasonable or disproportionately large load on our infrastructure; ... (k) accessing any content on the Service through any technology or means other than those provided or authorized by the Service; (l) bypassing the measures we may use to prevent or restrict access to the Service, including features that prevent or restrict use or copying of any content..." — [Kick Terms of Service](https://kick.com/terms-of-service)
- VERIFIED (ToS, content): other users' content is owned by them or by Kick: "User Content belonging to other Users ... are the exclusive property of Company and its licensors (including other Users who post User Content to the Service). Except as explicitly provided herein, nothing in these Terms shall be deemed to create a license..." Users grant each other "a non-exclusive license to access your User Content through the Service, and to use, reproduce, distribute, display and perform such User Content as permitted through the functionality of the Service and under these Terms." — [Kick Terms of Service](https://kick.com/terms-of-service)
- VOD retention: NOT FOUND in primary sources. help.kick.com returned a proxy 403 (host not allowed), and the DMCA, community-guidelines and ToS pages were searched with no VOD retention terms. A web search (secondary, not verified) returned third-party guides claiming 7 days for regular channels and 30 for verified, and a help-center page titled "Kick Stream Replays / VODs" (https://help.kick.com/en/articles/7112432-kick-stream-replays-vods) that, per the search summary, only says a replay is saved after the stream. Treat 7/30 days as UNVERIFIED.

### Inferences
- Using the official API for live/offline detection (webhook `livestream.status.updated` or polling `GET /public/v1/channels`) is clearly authorized. Pulling the video stream or VODs from kick.com is not an API-provided function, so under ToS (a), (b), (k) it falls in the prohibited bucket unless the channel owner (the user) is capturing their own broadcast or Kick grants permission. This is my reading of the clauses, not legal advice.
- If the pipeline's owner is the streamer, recording at the source (an OBS local recording, or an RTMP restream to infrastructure the owner controls) avoids the ToS question and the VOD expiry window altogether.

### Gaps
- Kick API rate limits, VOD retention days, and any VOD download policy: not found in primary sources; requires help.kick.com access.
- Whether a viewer-playback HLS URL is exposed by any official endpoint: no evidence found.

---

## 7. AWS IVS auto-record to S3 (HLS playlist and reconnect behaviour)

### Takeaway
NOT FOUND in primary sources: docs.aws.amazon.com is blocked by the session proxy (403), so none of the IVS doc pages could be read. Only a search-engine summary is available, which is not verified.

### Cited Findings
- (UNVERIFIED, search-result summary only, of https://docs.aws.amazon.com/ivs/latest/LowLatencyUserGuide/record-to-s3.html) The reconnect window is the `recordingReconnectWindowSeconds` property of the recording configuration; default 0, range 0 to 300 seconds; a broadcast that drops and returns within the window is recorded to the same S3 prefix and merged into one recording; Recording End events and the recording-ended JSON metadata are delayed by at least the window. The same summary says each rendition folder under `hls/` has a `playlist.m3u8` alongside `master.m3u8` and a byte-range manifest `byte-range-multivariant.m3u8`, and notes a known issue with the Web Broadcast SDK when the reconnect window is enabled. These details are NOT confirmed against the official page text.
- NOT FOUND: whether playlists carry `#EXT-X-ENDLIST` mid-stream versus only after the recording ends, and the live-update cadence of `playlist.m3u8` during a stream. The search summary itself said the docs hits did not state this.

### Inferences
- None made. A direct test (record a short stream and inspect the S3 playlist during and after the stream) is the only safe way to settle ENDLIST timing, if the docs remain unreachable.

### Gaps
- All item 7 sub-questions remain unverified from primary sources. Add docs.aws.amazon.com to the session allowlist and re-fetch: https://docs.aws.amazon.com/ivs/latest/LowLatencyUserGuide/record-to-s3.html and the IVS API reference page for `RecordingConfiguration`.

---

## 8. Hugging Face: ivrit-ai models and Hebrew leaderboard

### Takeaway
VERIFIED: both `ivrit-ai/whisper-large-v3-turbo-ct2` and `ivrit-ai/whisper-large-v3-ct2` are Apache-2.0 faster-whisper (CTranslate2) models. The latest model files on `main` for both are the 2025-05-13 versions. The leaderboard benchmark file shows the ivrit-ai large-v3 model slightly ahead of turbo (average WER 8.84% versus 9.06% across 5 datasets), a difference of about 0.2 points. No newer ivrit-ai Hebrew Whisper release appeared in 2026 (the 2026 releases are Yiddish and streaming models).

### Cited Findings
- VERIFIED (turbo card): "License: apache-2.0"; "This is ivrit.ai's faster-whisper model, based on the ivrit-ai/whisper-large-v3-turbo Whisper model. Training data includes 295 hours of volunteer-transcribed speech from the ivrit-ai/crowd-transcribe-v5 dataset, as well as 93 hours of professional transcribed speech from other sources. Release date: TBD". Usage: `faster_whisper.WhisperModel('ivrit-ai/whisper-large-v3-turbo-ct2')` then `model.transcribe('media-file', language='he')`. Base model openai/whisper-large-v3-turbo. Downloads last month 53,267; 28 likes. — [whisper-large-v3-turbo-ct2](https://huggingface.co/ivrit-ai/whisper-large-v3-turbo-ct2)
- VERIFIED (large-v3 card): "License: apache-2.0"; "This is a Ctranslate2 (Faster Whisper) weight format of the ivrit-ai/whisper-large-v3. Please follow the Faster Whisper usage details here and use this model name." Downloads last month 7,654; 24 likes. — [whisper-large-v3-ct2](https://huggingface.co/ivrit-ai/whisper-large-v3-ct2)
- Commit history (HF API): turbo-ct2 main: "New version: 2025.05.13" (2025-05-22), "New model, 2025.04.03." (2025-04-22), last commit "Update README.md" 2025-10-27. large-v3-ct2 main: "New version: 2025.05.13" (2025-05-22), "New version: 2025.04.03." (2025-04-22), last commit "Update README.md" 2025-10-27. — [HF API: turbo-ct2 commits](https://huggingface.co/api/models/ivrit-ai/whisper-large-v3-turbo-ct2/commits/main), [HF API: large-v3-ct2 commits](https://huggingface.co/api/models/ivrit-ai/whisper-large-v3-ct2/commits/main)
- VERIFIED (org recommendation): the ivrit-ai org card's "Start here" table maps "Transcribe Hebrew fast on GPU/CPU" to `whisper-large-v3-turbo-ct2` (faster-whisper) and "Get the best Hebrew accuracy" to `whisper-large-v3` (transformers). It states "ivrit.ai is a non-profit building open, permissively licensed Hebrew (and Yiddish) datasets and models. Models: apache-2.0." — [ivrit-ai on Hugging Face](https://huggingface.co/ivrit-ai)
- Newer ivrit-ai releases (HF API listing sorted by last modified): `yi-whisper-large-v3-turbo-ct2` (Yiddish; modified 2026-10-26), `zipformer2-66m-streaming-he` (created 2026-10-14; Hebrew streaming ASR, license CC-BY-4.0, mirror of a model by Yakov Kolani; "Decodes in 1.28 s chunks as audio arrives"), `yi-whisper-large-v3-turbo-ggml` and `-ggml` variants (2026-02-09), `whisper-large-v3-turbo-onnx` (modified 2025-12-20). No newer Hebrew `whisper-large-v3*` release than the 2025.05.13 versions was found. The `yi-` models are Yiddish and their card says "it is intended for mostly-hebrew audio transcription" for language detection issues but language must be set explicitly to Yiddish. — [HF API: ivrit-ai models](https://huggingface.co/api/models?author=ivrit-ai&sort=lastModified&direction=-1&limit=40), [yi-whisper-large-v3-turbo card](https://huggingface.co/ivrit-ai/yi-whisper-large-v3-turbo)
- VERIFIED (leaderboard method): "Models are evaluated using Word Error Rate (WER) on each benchmark dataset. The final score is an average of WER across all benchmarks, with lower scores indicating better performance... done using the jiwer library." — Space source `src/about.py` in [hebrew-transcription-leaderboard](https://huggingface.co/spaces/ivrit-ai/hebrew-transcription-leaderboard). The Space UI is a dynamic Gradio app (page text is just "Running"), so the numbers below come from the Space's committed `benchmark.csv` (Space last modified 2026-10-14): https://huggingface.co/spaces/ivrit-ai/hebrew-transcription-leaderboard/resolve/main/benchmark.csv
- WER per dataset (eval-d1, eval-whatsapp, saspeech, fleurs-he, hebrew_speech_kan) and my unweighted mean:

| Model | d1 | whatsapp | saspeech | fleurs | kan | Mean |
|---|---|---|---|---|---|---|
| ivrit-ai/whisper-large-v3-ct2-20250513 | 0.051 | 0.072 | 0.064 | 0.174 | 0.081 | 0.0884 |
| ivrit-ai/whisper-large-v3-turbo-ct2-20250513 | 0.053 | 0.071 | 0.066 | 0.181 | 0.082 | 0.0906 |
| ivrit-ai/whisper-large-v3-ct2-20250403 | 0.055 | 0.075 | 0.071 | 0.200 | 0.095 | 0.0992 |
| ivrit-ai/whisper-large-v3-turbo-ct2-20250403 | 0.055 | 0.061 | 0.074 | 0.208 | 0.100 | 0.0996 |
| soniox stt | 0.048 | 0.090 | 0.065 | 0.177 | 0.114 | 0.0988 |
| ivrit-ai/whisper-large-v3-turbo-ct2-20250209 | 0.071 | 0.104 | 0.077 | 0.245 | 0.100 | 0.1194 |
| faster-whisper large-v3 (OpenAI original) | 0.098 | 0.132 | 0.094 | 0.262 | 0.134 | 0.1440 |
| faster-whisper large-v3-turbo (OpenAI original) | 0.084 | 0.128 | 0.104 | 0.289 | 0.156 | 0.1522 |
| deepgram nova-3 | 0.067 | 0.120 | 0.102 | 0.233 | 0.210 | 0.1464 |
| openai gpt-4o-transcribe | 0.073 | 0.126 | 0.109 | 0.210 | 0.394 | 0.1824 |
| openai gpt-4o-mini-transcribe | 0.090 | 0.158 | 0.150 | 0.300 | 0.468 | 0.2332 |
| elevenlabs scribe_v1 | 0.200 | 0.264 | 0.068 | 0.181 | 0.109 | 0.1644 |
| google-speech | 0.211 | 0.352 | 0.189 | 0.385 | 0.292 | 0.2858 |

  The means are my arithmetic over the CSV values. Source for the numbers: [Space benchmark.csv](https://huggingface.co/spaces/ivrit-ai/hebrew-transcription-leaderboard/resolve/main/benchmark.csv).
- Speed (Space `timing.csv`, ivrit-ai turbo-ct2 on faster-whisper): latency p50 for 15 to 30 s clips: RTX 5090 440 ms, L40S 357 ms, A10 513 ms, T4 832 ms; for audio of 30 s or more, speedup (p50) 61.2x on RTX 5090, 42.8x on A10, 24.1x on T4. — [timing.csv](https://huggingface.co/spaces/ivrit-ai/hebrew-transcription-leaderboard/resolve/main/timing.csv). No CPU-only timing rows exist in the file.

### Inferences
- The OpenAI base large-v3-turbo (15.2% mean WER) is far worse on Hebrew than the ivrit-ai fine-tuned turbo (9.1%). That is a 40% relative reduction, so Groq's stock `whisper-large-v3-turbo` (a pruned OpenAI model) should be expected to perform roughly like the "faster-whisper large-v3-turbo" row, not like the ivrit-ai rows (inference; Groq's exact weights differ from the faster-whisper conversion and no Hebrew numbers for Groq were found).
- The ivrit-ai turbo-ct2 trades about 0.2 points of mean WER for much faster decoding versus the ivrit-ai large-v3 (the leaderboard CSV has no timing rows for the non-turbo ivrit model).
- The leaderboard labels ("-20250513") match the dates of the commits on `main`, so the current model files on HF `main` should correspond to the best rows; this mapping is inferred from dates, not stated in the card.

### Gaps
- The model cards give no recommended-usage details beyond a one-line faster-whisper snippet (no VAD, beam or chunking advice) and "Release date: TBD".
- The live leaderboard UI could not be rendered; numbers rely on the committed CSV, which could differ from what the UI shows at this moment.
- Whether Groq hosts any ivrit-ai fine-tune: Groq's rate-limit table lists only OpenAI `whisper-large-v3` and `whisper-large-v3-turbo` for speech-to-text.

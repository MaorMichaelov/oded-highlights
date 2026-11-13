# YouTube API, policy and growth notes for an automated clip channel (as of 13 Nov 2026)

SOURCE-ACCESS CAVEAT (read first): in this session developers.google.com, developers.google.cn and support.google.com could not be fetched (DNS failure; they are outside the allowed network domains). Every finding below comes from WebSearch result summaries, which quote or paraphrase official pages and third-party sites. I never read a full official page or its revision history. Items marked [UNVERIFIED] must be checked by hand in the official page (or the Cloud Console) before relying on them. To redo this properly, allow developers.google.com and support.google.com.

## 1. "Locked as private" rule for videos.insert from unverified API projects

### Takeaway
The lock very likely still exists. Google's Help page "Videos locked as private" lists "uploaded by an unverified third-party API service" as a lock reason, says there is no appeal, and says the fix is to re-upload through a verified service or the YouTube site/app, or have the service apply for an audit. One secondary source claims an upload reference dated 8 Oct 2026 says the restriction no longer applies; I could not verify that. Treat the lock as the default and test with one real upload first.

### Cited Findings
- The Help page "Videos locked as private" lists "uploaded by an unverified third-party API service" as a reason. For this reason you cannot appeal. You must re-upload via a verified API service or via the YouTube app/site, or the unverified service can apply for an audit. — [YouTube Help 7300965](https://support.google.com/youtube/answer/7300965?hl=en) (via search summary, not fully read)
- Google's announcement, as quoted in a GitHub project: videos uploaded via videos.insert from unverified API projects created after 28 July 2020 are restricted to private viewing mode. — [porjo/youtubeuploader issue 86](https://github.com/porjo/youtubeuploader/issues/86) (secondary quote of the official announcement)
- Google's API docs say unverified projects' uploads are private by default and each project must undergo an audit to verify ToS compliance. Start by submitting the "YouTube API Services - Audit and Quota Extension Form". — [Quota and Compliance Audits](https://developers.google.com/youtube/data/guides/quota_and_compliance_audits) (search summary)
- Third-party guides say that until the audit passes, API-uploaded videos cannot be made public via the API or via Studio. — [singhamandeep.com](https://singhamandeep.com/?p=1462), [Ayrshare](https://www.ayrshare.com/solutions/google-api-error-403-unverified-app-how-to-fix-the-audit-pipeline/) (vendors that sell audit workarounds; secondary)
- Conflicting item: one developer guide says the revision history still describes the restriction but that an upload reference, as of 8 Oct 2026, says it does not apply. — [upload-post.com guide](https://www.upload-post.com/youtube-api/) [UNVERIFIED, single secondary source]
- Workaround stated in a community answer: upload manually through the website, so the video is never locked. — [Stack Overflow mirror](https://kiwix.lema.org/stackoverflow.com_en_all_2023-11/questions/66277512/youtube-videos-privacy-locked-on-upload) (older, secondary)
- Auditing the wrong Cloud project is a common mistake; the rule attaches to the API project. — [Ayrshare](https://www.ayrshare.com/solutions/google-api-error-403-unverified-app-how-to-fix-the-audit-pipeline/) (secondary)

### Inferences
- Because Help says locked videos cannot be appealed and must be re-uploaded, "make public manually in Studio" probably does not work for locked videos. Studio's visibility control is reported as greyed out. Treat as likely but test it.
- Rule-abiding options: (a) apply for the compliance audit (needed for any real automation); (b) hybrid pipeline: the script prepares the file, title, description, thumbnail and chapters, and a human uploads via Studio/web (no lock; drafts or scheduling are available in the UI); (c) test first with one short throwaway upload to see whether the lock still applies to this brand-new project. Do not use a "verified" third-party scheduler by proxy as a way to dodge the rules without checking its terms.
- A tiny single-channel hobby tool is a weak audit candidate; the audit form is aimed at public API clients. Expect possible rejection or follow-up questions. Do not expect a fast outcome before 19 Nov 2026.

### Gaps
- Exact audit duration, requirements and current form wording: not found in fetched official text.
- Whether the lock still applies in Nov 2026 (the 8 Oct 2026 claim vs. Help page) and whether any 2025-2026 revision-history entry changed it: unresolved.
- Whether a previously locked video is released after a passed audit: not documented in what I saw.

## 2. OAuth "Testing" status and refresh tokens

### Takeaway
Yes: in Testing with an External user type, authorizations by test users, including refresh tokens, expire after 7 days for non-basic scopes such as youtube/youtube.upload. Setting the app to "In production" stops the 7-day expiry in most reports, but because youtube.upload/youtube are sensitive scopes, an unverified production app shows the "unverified app" warning and is capped at 100 new users for the project's lifetime (fine for a single owner).

### Cited Findings
- Google: test-user authorizations expire seven days after consent; if the client requests offline access and gets a refresh token, that token also expires. — [Cloud Help 10311615](https://support.google.com/cloud/answer/10311615?hl=hr) (via search summary)
- Exception only for basic scopes (userinfo.email, userinfo.profile, openid); a YouTube scope does not qualify. — [Nango docs](https://www.nango.dev/docs/api-integrations/youtube/how-to-register-your-own-youtube-api-oauth-app.md) (secondary)
- Testing mode limit: 100 test users. — [Unipile](https://www.unipile.com/google-oauth-refresh-token/) (secondary)
- Fix per a Google Groups answer: Console > OAuth consent screen > change publishing status to "In production". — [Google Groups](https://groups.google.com/g/adwords-api/c/QTdeilIh_QY/m/eOHg0Q9CAgAJ)
- Unverified apps requesting sensitive/restricted scopes show an "unverified apps" warning; cap is 100 new users over the project's whole lifetime, cannot be reset. — [Cloud Help 15549945 Manage App Audience](https://support.google.com/cloud/answer/15549945?authuser=7)
- Conflict: a Google forum thread reports a refresh token still expiring in 7 days after moving to production but staying unverified. — [Google Groups](https://groups.google.com/g/adwords-api/c/WDgwEZT6Cd0)
- Other claims on production token lifetime: long-lived until revoked, vs. expiry after 6 months of inactivity — [Unipile](https://www.unipile.com/google-oauth-refresh-token/) [UNVERIFIED].

### Inferences
- Practical path at $0: click "Publish app" (In production), do the consent once through the "unverified app > Advanced > continue" screen as the owner, store the refresh token, and use it at least every few weeks (inactivity expiry). Keep a fallback: a re-auth script, plus an alert on invalid_grant.
- Owner-only use is far below the 100-user cap. Verification is only needed if you want to remove the warning; sensitive-scope verification may involve a demo video and privacy policy page (not confirmed here).
- Do not add youtube (full manage) scope if youtube.upload plus youtube.force-ssl is enough; narrower scopes are easier to defend in verification. Needs checking: thumbnails.set and playlistItems.insert need youtube or youtube.force-ssl, not youtube.upload alone (from my background knowledge; not verified here).

### Gaps
- Official text on whether In production + unverified avoids the 7-day expiry for youtube scopes: only forum reports, conflicting.
- Exact verification requirements for youtube.upload.

## 3. Quota

### Takeaway
Sources conflict and the official picture seems to have changed in late 2025/2026. Older material: 10,000 units/day, videos.insert 1,600 units (about 6 uploads/day), thumbnails.set 50. Newer material: a default of 100 videos.insert calls per day in a separate bucket, plus 10,000 units for everything else. Verify in Cloud Console > Quotas, which is authoritative for the project.

### Cited Findings
- Google's quota calculator page (English) is described as listing a default allocation of 100 search.list calls, 100 videos.insert calls and 10,000 units/day for other endpoints; the auto "Page Summary" and localized pages still show 1,600 for insert. — [Quota Calculator](https://developers.google.com/youtube/v3/determine_quota_cost) (search summary; internally inconsistent)
- A blog says the revision history entry of 4 Dec 2025 notes the upload cost changed from about 1,600 to about 100 units; and reports (June 2026) videos.insert moved to its own bucket at 1 unit per call. — [singhamandeep.com](https://singhamandeep.com/?p=1570) [UNVERIFIED, not confirmed on Google's page]
- Older/vendor guides: 10,000 units/day, insert about 1,600, so about 6 uploads/day; thumbnails.set 50 units (about 200/day). — [Adaptly](https://adaptlypost.com/blog/youtube-upload-limit-per-day), [bundle.social, Aug 2026](https://bundle.social/blog/youtube-api-quota-exceeded-limits-fixes)
- Quota extension requires the audit form, same as the compliance audit. — [Adaptly](https://adaptlypost.com/blog/youtube-api-quota-extension)

### Inferences
- Either way the channel needs only a handful of uploads per day. Even under the old model (about 6/day) a plan of 1-3 long videos/day plus thumbnails.set (50) and videos.update/playlistItems.insert (about 50 each by my background knowledge; not verified here) fits in 10,000 units. Quota is not the binding constraint; the private lock and OAuth are.
- Quota resets at midnight Pacific time (background knowledge, not verified here).

### Gaps
- Official current costs for videos.update, playlistItems.insert and thumbnails.set; official revision-history confirmation of the 2025-2026 change.

## 4. Other constraints (upload limits, verification, fields, Test and Compare)

### Takeaway
YouTube does not publish a per-channel daily upload cap; it varies by channel and counts API uploads too. Unverified channels are limited to 15 minutes and cannot set custom thumbnails; phone verification lifts that. Test and Compare is a Studio-only feature; I found no API for it.

### Cited Findings
- Daily upload limit per channel is unpublished, covers desktop, mobile and API, and may vary by country or channel history; message "Daily upload limit reached": wait 24h. — [Adaptly](https://adaptlypost.com/blog/youtube-upload-limit-per-day), [Viraly](https://viraly.io/docs/youve-reached-your-youtube-upload-limit-what-it-means-and-what-to-do) (secondary, paraphrasing Help)
- Unverified accounts: 15-minute cap; verified (phone) up to 12 hours; some tiers require ID or channel history. — [fast.io](https://fast.io/resources/youtube-upload-limit/) (single vendor page, treat cautiously)
- Test and Compare: Studio on desktop, up to 3 thumbnails, requires "Advanced features", not for Shorts, not for made-for-kids, mature or private videos; titles added July 2025. — [YouTube Help 13861714](https://support.google.com/youtube/answer/13861714), [Tubefilter July 2025](https://www.tubefilter.com/2025/07/16/youtube-feature-test-and-compare-titles-thumbnails/)
- No source mentioned an API endpoint for Test and Compare. — (absence in search results)
- A guide site covers an "AI Disclosure" section for the API (containsSyntheticMedia field) and scheduled publishing. — [singhamandeep.com AI disclosure](https://singhamandeep.com/?p=1572), [Scheduled publishing](https://singhamandeep.com/?p=1582) (secondary; not read in detail)

### Inferences
- Channel is presumably already phone-verified (it has about 1,850 subs), so the 15-minute cap is likely moot; confirm in Studio > Settings > Channel > Feature eligibility.
- From background knowledge (unverified here): status.selfDeclaredMadeForKids must be set explicitly (false); status.containsSyntheticMedia exists in the API; publishAt requires privacyStatus=private and an RFC 3339 time; chapters need description lines starting with 0:00, at least 3 chapters, each 10s+; categoryId 20 = Gaming, 24 = Entertainment, 22 = People & Blogs; snippet.defaultLanguage/defaultAudioLanguage "he". Verify these on the videos resource page.
- A scheduled publishAt upload from an unverified project would likely stay locked private anyway.

### Gaps
- Official statements for each field; any 2026 thumbnail test API.

## 5. Monetization and policy

### Takeaway
Stream-clip channels sit squarely in the "reused content" and "inauthentic content" risk zone. Permission from the original creator does not by itself make content eligible for YPP. Eligibility depends on meaningful transformation (commentary, editing, narrative), not on credit links. Fake engagement from your own second channel is prohibited.

### Cited Findings
- On 15 July 2025 YouTube renamed "repetitious content" to "inauthentic content" (mass-produced or repetitive content), said this was always ineligible, and said the reused content policy was unchanged. — [Engadget](https://www.engadget.com/entertainment/youtube/never-fear-reaction-videos-are-still-allowed-under-youtubes-new-inauthentic-content-policy-222401009.html), [PPC Land](https://ppc.land/youtube-clarifies-inauthentic-content-policy-changes/)
- Reused content policy applies even with the original creator's permission; it is separate from copyright. — [PPC Land](https://ppc.land/google-clarifies-youtube-monetization-policies-amid-creator-confusion/) (secondary; official: [Help 1311392](https://support.google.com/youtube/answer/1311392))
- The inauthentic content policy is evaluated at channel level. — [PPC Land](https://ppc.land/youtube-clarifies-inauthentic-content-policy-changes/)
- A 13 July 2026 Tubefilter report says YouTube reworked the guidance into three categories (generic or repetitive content; unsatisfying or off-putting content; AI personas on sensitive topics) and that it is not a new policy. — [Tubefilter](https://www.tubefilter.com/2026/07/13/youtube-inauthentic-content-monetization-policy-update/amp/) (headline-level only)
- Fake engagement policy: anything that artificially increases views, likes, comments or other metrics is prohibited; violating content or channels may be removed or terminated. — [YouTube Help 3399767](https://support.google.com/youtube/answer/3399767?hl=en)
- Kick terms (via summaries): the streamer grants Kick a broad license and warrants non-infringement; no clear public rule on third-party redistribution was found. A clipping blog says non-commercial clipping is broadly tolerated and monetized clips are a gray area depending on the streamer. — [ConductAtlas](https://conductatlas.com/platform/kick/kick-terms-of-service/), [autoclip.dev](https://autoclip.dev/blog/how-to-clip-kick-streams) (secondary)

### Inferences
- Long highlight compilations with little added value are the exact pattern reviewers reject. To be defensible, add commentary or voiceover, a distinct edit, context titles, and curation. Written permission from the streamer helps with Content ID and copyright disputes and with his goodwill, but does not fix reused-content review.
- Copyright/Content ID: music playing on the stream, or third-party videos the streamer watches, can trigger claims against your upload even if the streamer allows clipping. Mute or replace such segments.
- The streamer's own permission should be documented (message screenshot); a second owned channel liking/watching your uploads is fake engagement and can end the channel; do not do it.
- AI-generated thumbnails showing realistic people or events probably need the altered/synthetic disclosure; mark via containsSyntheticMedia when realistic. The official Help text was not read.

### Gaps
- Current YPP thresholds and exact reused-content wording; text of the 2026 update itself; actual Kick TOS clause on redistribution; official "altered or synthetic content" page.

## 6. Growth practices

### Takeaway
Evidence here is thin and mostly vendor blogs. Consistent claims: titles, thumbnails and viewer retention dominate; tags matter little; chapters are useful. I found nothing solid on Hebrew titling, event timing, or Israeli peak hours.

### Cited Findings
- Tags play a minor role (misspellings and variants); title and description are main metadata levers; chapters need first stamp at 0:00, at least 3 chapters, each at least 10 seconds. — [PeakAce 2026](https://peakace.agency/en/youtube-seo-guide-2026/), [TimeSkip](https://timeskip.io/blog/tags-and-keywords) (vendor blogs, secondary)
- No solid evidence found for a special "first 48 hours" ranking window. — (search results)
- Test and Compare can test thumbnails (and titles since mid-2025) in Studio. — [Tubefilter](https://www.tubefilter.com/2025/07/16/youtube-feature-test-and-compare-titles-thumbnails/)

### Inferences
- With many clip channels covering the same subathon moments, a small channel is unlikely to win on speed; differentiation (Hebrew-specific context, a compilation of best moments per day, chapters) is the safer bet. Posting several near-identical videos per day risks the "repetitive" label and splits a small audience; prefer 1-2 strong daily uploads. This is judgment, not evidence.
- Practical Hebrew packaging: put the key name/moment first in the first ~60 characters, avoid clickbait that the video does not deliver, and test thumbnail variants via Test and Compare manually. Not backed by sources.
- Playlists and end screens: standard good practice (series playlist per event, end screen to next part), no sourced evidence here.

### Gaps
- No data-backed source for Hebrew title length, Israeli peak hours (commonly guessed evenings), cadence during events, or flooding effects. Analyse the channel's own Studio audience-activity chart ("When your viewers are on YouTube") instead.

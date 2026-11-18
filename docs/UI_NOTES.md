# Studio UI notes

Page: `app/studio.html` (single file, vanilla JS/CSS, no build; served by the Worker as a string through `app/studio.js` + `app/deploy.py`).
Fonts: IBM Plex Sans Hebrew (body), Barlow Condensed (Latin display, Heebo 800 for Hebrew display), IBM Plex Mono (timecode/labels) from Google Fonts; system fallbacks work offline. No other external resources.

## Visual identity (edit bay, not an "AI app")
Ink/graphite panels with hairlines (dark) or paper/ink (light), ONE signal colour: tally amber (buttons, playhead, active nav). Red is only REC/reject/errors, green only approved/ok.
Motifs: timecode clock in the top bar, waveform bars (generated from a seed, used for job progress and clip posters), a scrubbing timeline with a playhead on the landing page, viewfinder corner brackets and REC tag on the clip player, in/out/duration cells on clip cards, clapperboard stripe on the verify code, SMPTE colour bars for empty states, a VU/LED meter for credits, hardware-key buttons (flat, 3px bottom edge, 4px radius). No gradients, glow, glass or sparkles.
`?theme=light|dark|auto` overrides the saved theme (handy for screenshots).

## Demo (no backend)
* `app/studio.html?demo=1` runs the whole UI against an in-memory fake API (same endpoints/shapes as `studio.js`, jobs progress live).
  Extra params: `scenario=new|verify|yt|full` (default `full`), `role=owner|editor|viewer`, `lang=he|en`, `landing=1` (show the landing/sign-in first).
* `docs/studio_demo.html` is the shareable single-file demo: the same file with `FORCE_DEMO = true`. Regenerate after every UI change:
  `sed 's/^const FORCE_DEMO = false; /const FORCE_DEMO = true;  /' app/studio.html > docs/studio_demo.html`
  (starts on the landing/sign-in screen, any email + password works, the ribbon switches between a new and a busy account).

## API additions for the UI
* `POST /studio/api/orgs/:oid/jobs/:jid/drafts/:i/title {title}` [editor]: inline title edit on the review screen (job must be `draft_ready` or `approved`; stored as `drafts[i].title`, `title_edited:true`). Covered in `app/studio.test.mjs`.
* YouTube connect uses `docs/YOUTUBE_CONNECT.md`: `POST /studio/yt/start {org_id, channel_id}` -> `{url}`, `GET /studio/yt/status`, `POST /studio/yt/disconnect`; the callback returns to `/studio#youtube=connected` or `#youtube=error=<code>`. 404/501/503 answers show "coming soon" instead of an error.

## Behaviour worth knowing
* Hebrew (RTL) is the default unless the browser language is English; the toggle persists in localStorage. Dark is the default look; Settings has Auto (follows the OS) / Light / Dark.
* Review: swipe right = approve, left = reject, arrow keys on desktop (physical directions, also in RTL). Decisions are sent after a 5 s "Undo" window (flushed on page hide).
* Polling: 3.5 s while a job is queued/running/qa, 15 s otherwise, paused in hidden tabs. A toast announces new drafts.

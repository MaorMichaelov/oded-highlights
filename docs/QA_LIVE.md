# QA log (live loops + Studio), newest first

Format: time (UTC), what was tested, PASS/FAIL, evidence, suspected cause. Maintained by the QA runner.

## 2026-11-18 17:05Z

| What | Result | Evidence / cause |
|---|---|---|
| live-check (who is live) run 44353836006 | INFO | Twitch kaicenat, ishowspeed, xqc and Kick n3on are all LIVE at 17:01Z. |
| English live loops (live-shorts runs 44326754275, 44326721745) | FAIL | 2h20m running, zero `live shorts:` commits, no `state/<slug>/live_state.json`. Cause: `scripts/live_shorts.py` main(): new-stream init sets `done_to_min = int(dur) - window`, so `b_ = int(dur)` and the guard `b_ > dur - 2` is always true; it returns before saving state, so the loop waits forever (only `--force` processes). Reproduced numerically for dur 10..500. Regression test written (tests/test_live_shorts.py, 3 tests, all fail on current code). |
| Same loops: Speed | FAIL | `newest(ishowspeed)` returns the OLD VOD 2928036561 (164 min, "REVIEWING MY NEW FORTNITE ICON SKIN") while he is live, so `record_mode` is never reached. |
| Same loops: code version | FAIL | Both runs were dispatched at 14:40 on head_sha 8916d29 / 9922683, i.e. before `record_mode` (46d1ef8); they need a cancel and re-dispatch after the fix (concurrency group has `cancel-in-progress: false`). |
| live-once kaicenat window 0-10 (run 44351438267) | FAIL | Gemini 503 "high demand" on all 6 model/key attempts, then "no short produced". Needs backoff or a non-Gemini fallback. |
| live-once ishowspeed window 0-4 (run 44351570332) | INFO | 18 words in the first 4 min of the VOD (intro silence), no short. Not a bug by itself. |
| http-probe assistant (run 44352854501) | PASS with notes | Deployed worker answers the 4 FAQ-type sentences correctly in Hebrew. Free-chat replies are acceptable but generic ("איזה רגעים אוהבים הצופים שלך?"); "תודה אחי" -> "בברכה!" is stiff. Health, queue, config, invite gate, terms: OK. gemma-3-12b not allowed on this account (5018), others OK. |
| Assistant FAQ false positives (local battery of 40 sentences) | FAIL, FIXED in fd241a7 | `תן לי כותרת בסגנון מצחיק` -> editing-style FAQ; `I want a costume video title` -> price FAQ (`cost` substring); `הסרטון של העורך שלי יצא גרוע` -> team FAQ; `explain the difference...` -> how-it-works; `איך להתחיל לצעוק פחות בשידור` -> how-to-start. Regexes tightened, task verbs and long messages skip the FAQ, regression test added to app/studio.test.mjs. Needs a Worker deploy to reach users. |
| node app/*.test.mjs | PASS | agent 24, studio 39, youtube_connect 28 + integration. |
| python3 -m unittest discover tests | KNOWN FAIL | 218 tests, 3 failures, all `test_agent_hooks` (docs/agent_hooks patches no longer apply; BACKLOG C1; CI treats it as a warning). Not a regression: studio.patch already fails on 014104a (SQLite DO commit). |
| scripts/ci_lint_workflows.py | PASS | 0 problems. |

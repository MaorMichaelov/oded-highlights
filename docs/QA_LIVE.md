# QA log (live loops + Studio), newest first

Format: time (UTC), what was tested, PASS/FAIL, evidence, suspected cause. Maintained by the QA runner.

## 2026-11-18 17:55Z

Owner decision (17:40Z): the Kai / Speed / N3on / xQc live loops are dropped; assistant and chat probes are stopped until 00:00 UTC (Workers AI free allocation of 10k neurons/day is used up).

| What | Result | Evidence / cause |
|---|---|---|
| Owner's job, studio-worker run 44356846447 (kick channel igz, 5 Shorts requested) | PARTIAL | Run success, but job j_748f82aca5669050 delivered 1 draft: `SHORT 26:38-27:07 (29s) qa=88 "Crazy Sony Talk: They Only Have Sony!"`, 427 s of work, preview + full file uploaded. Only a 30 min window was analysed and Gemini answered 429 (quota) on every key from 17:30 to 17:34. The log does not say how many Shorts were requested vs found. |
| Same run, job j_3c3f47c75888f778 | FAIL | `too_short: source is shorter than 30s` after 34 s (owner unknown; possibly an orphan of the cancelled e2e run 44356795402). |
| Queue latency | NOTE | That run was created 17:16:39 but its worker started 17:28:36: it waited ~11 min behind another studio-worker run in the same concurrency group (the one serving the QA e2e job, cancelled 17:27). A QA e2e run can delay the owner's job: QA no longer starts studio-e2e-job. |
| studio-worker cron | FAIL, FIXED by 0b8474f | Zero scheduled runs ever (6 runs, all dispatch); repo-wide schedule events are hours apart. studio-poller.yml (45 s queue watch) added; status text updated. Poller reviewed: logic OK (queue check, one worker at a time, self-chain at 5.5 h). Unverified: that the poller actually starts a worker for a fresh job. |
| Status report grammar | FIXED 7f28b4e | "1 טיוטות" / "1 drafts are" -> singular wording, test added. |
| Suites on 9732857 | PASS | node: agent 24, studio 41, youtube_connect 28 + integration; lint 0. Python: 221 tests, only the 3 known test_agent_hooks failures. |

## 2026-11-18 17:32Z

| What | Result | Evidence / cause |
|---|---|---|
| Live-loop fix 58a5191 (contiguous windows) | PASS | tests/test_live_shorts.py (3 tests) green on the fix; kaicenat live_state.json now saved (230 -> 242 -> 254). |
| Kai loop produces Shorts | FAIL | live-once 44358358596 (kaicenat, window 12): vod_shorts.py exits "no suitable Twitch VOD" for VOD 2932305259 (the stream that is live now). `twitch_pick()` re-lists the 12 newest archives and does not find the id (flaky; worked at 16:48). Proposed fix: skip the listing when `--vod <id>` is explicit, print stderr on empty listing, retry. |
| live_shorts ignores vod_shorts failure | FAIL | `subprocess.run(vod_shorts)` return code unused, so `done_to_min` advances over windows that were never cut (lost for good). Proposed: advance only on returncode 0, retry up to ~3 times. |
| Speed loop | FAIL | First record-mode window (17:18Z) uploaded nothing (`uploaded.json` = {}); run 44354379279 cancelled 17:23Z, no new ishowspeed run afterwards. |
| studio-e2e-job 44355445754 (live app, Kai VOD link) | PASS | 3 drafts in 15 min (qa_ok True/True/False). Notes: status text "Listening to the stream... 75%" while progress stays 45 for ~9 min; draft titles weak ("BRO! THEY GOT AWAY! I'm a suspect on my spot for suspect!"); the link request was answered in `mode: basic, why: no-ai`. |
| qa-assistant 44355976798 (26 sentences, Mistral small deployed) | FAIL, FIXED in bc82b8c / 98305bd | Invented TikTok rule; gibberish ("מיחדול", "פילגש", "פיינל", "קופסת האישורים"); invented weather; "כמה קרדיטים נשארו לי" answered with the generic FAQ (regex: "כמה" contains "מה"); "בכמה כסף זה" -> "אני לא יודע"; capabilities reply repeated one sentence 3 times. Curated FAQ answers added, prompt forbids guessing live data/platform rules, model order switched back to gpt-oss-120b first by main. Needs deploy to take effect. |
| node app tests / ci_lint_workflows | PASS | agent 24, studio 39 groups, youtube_connect 28 + integration; lint 0 problems. |

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

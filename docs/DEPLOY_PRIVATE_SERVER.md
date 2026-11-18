# שרת פרטי ל-Render Worker / Private server for the render worker

## תקציר לבעלים (עברית)

**למה שרת פרטי.** תנאי השימוש של GitHub Actions אוסרים להריץ עליהם שירות מסחרי; לכן העבודות של הלקוחות (חיתוך, תמלול, רינדור) חייבות לרוץ על מחשב/שרת שלך. ה-Worker של Cloudflare נשאר "מוח" (חשבונות, תור, אישורים) והשרת הפרטי רק פונה החוצה ומושך עבודות (אין פורטים פתוחים, חוץ מהריסטרים אם בחרת בו).

**מה בנוי (הכל בריפו, נבדק מקומית):**
* `scripts/render_worker.py` – דמון: לוקח עבודה מה-Studio, מריץ את הצינור הקיים (סגנון signature + הפרופיל של הלקוח), מדווח התקדמות ("מצאנו 5 רגעים, חותכים..."), מחזיר טיוטות עם ציון QA. **לעולם לא מעלה ליוטיוב** – ההעלאה היא שלב נפרד (`scripts/yt_upload_customer.py`, פרטי כברירת מחדל, כפוף ל-`state/UPLOAD_HOLD`).
* `deploy/` – Dockerfile, `docker-compose.yml`, קובץ סביבה לדוגמה (בלי סודות), יחידות systemd.
* בדיקת עשן בלי רשת ובלי מפתחות: `python3 scripts/render_worker.py --demo` (יוצר סרטון סינתטי, מריץ עבודה מלאה, מדפיס טיוטות; ~1.5 דקות).

**בטא על המחשב שלך (בחינם):** התקן Docker Desktop (או Python 3.12 + ffmpeg), `git clone`, `cp deploy/worker.env.example deploy/worker.env`, מלא `STUDIO_URL` ו-`STUDIO_WORKER_KEY` (אותו ערך ששמת ב-KV כ-`studio:cfg:worker_key`), והרץ `docker compose -f deploy/docker-compose.yml up -d --build worker`. המחשב צריך להיות דלוק ולא לישון. מגבלות: ברירת מחדל עבודה אחת בו-זמנית (4 ליבות). הצעד המלא בסעיף 2.

**VPS זול בהמשך:** אותם קבצים. מחירים ותכנון קיבולת: `docs/PRODUCT_PLAN.md`. צעדים בסעיף 3.

**להפוך את הריפו לפרטי בלי לשבור את הלולאות של הערוצים שלך.** הבעיה: ריפו **ציבורי** מקבל דקות Actions חינם ללא הגבלה, ריפו **פרטי** מקבל רק 2,000 דקות בחודש בתוכנית החינמית [לבדוק מחיר/מכסה עדכניים], והלולאות שלך (live-loop רץ ברצף בקטעים של 5 שעות 40 דקות) צורכות עשרות אלפי דקות. הפתרון שמומלץ (אפשרות C): **ריפו "מעטפת" ציבורי** עם ה-workflows וה-state בלבד, ו**ריפו קוד פרטי**; בכל הרצה ה-workflow מושך את הקוד מהפרטי עם deploy key לקריאה בלבד. יצרתי סקריפט שמייצר את קבצי המעטפת (`deploy/make_shell_repo.py`), נבדק על ה-29 ה-workflows (27 קיבלו את שלב המשיכה, YAML תקין). **לא יצרתי ריפו ולא שיניתי נראות.** הצעדים המדויקים בסעיף 5; אתה מבצע אותם.

**חשוב לדעת לפני:** (1) היסטוריית הריפו הציבורי הנוכחי כבר גלויה ואולי משוכפלת; הפיכתו לפרטי לא מוחקת עותקים קיימים, ולכן ההמלצה היא להפוך את **הריפו הנוכחי** לפרטי ולפתוח **ריפו חדש** למעטפת (עם היסטוריה נקיה). (2) כל הסודות מוזנים מחדש כ-Secrets בריפו המעטפת. (3) ה-Worker (`app/worker.js`) קורא קבצים מהריפו דרך API: צריך להפנות אותו למעטפת (סעיף 5, צעד 8). (4) הרצות בריפו ציבורי חושפות את הלוגים: קוד פרטי יכול להופיע בטרייסבק. פרטים וסיכונים בסעיף 5.

---

## 1. What runs where

```
Customer browser ──> Cloudflare Worker (app/worker.js + studio.js: accounts, queue, approvals, KV)
                           ^   outbound HTTPS only (POST /studio/worker/claim, /studio/worker/jobs/:id)
                           |
                 ┌─────────┴───────────────────────────── private server (owner's PC now, VPS later) ─────────┐
                 │ render_worker.py  ──subprocess per job──> job_runner.py (source -> ASR -> moments -> 9:16 render -> QA)   │
                 │ out/<job>/short_*.mp4 + .json + manifest.json  (drafts wait here)                                        │
                 │ [optional] MediaMTX + ingest_watcher.py (customer restream -> jobs)   docs/INGEST.md                     │
                 └───────────────────────────────────────────────────────────────────────────────────────────┘
                 upload to the customer's YouTube = a separate step: scripts/yt_upload_customer.py (private by default, state/UPLOAD_HOLD respected)
```

Properties worth knowing: the worker holds only the shared worker key (never passed to job subprocesses, never logged; logs redact it). It never calls YouTube. A job runs in its own process group with a hard timeout (4 h) and a stall timeout (30 min); SIGTERM stops claiming, running jobs get 10 minutes, then they are killed and reported failed (the studio refunds the credit). Failed scratch is kept 24 h, finished drafts 14 days, scratch of successful jobs is deleted at once, and no job is claimed when less than 5 GB are free. Customer media never leaves the machine except audio chunks sent to Groq/Gemini **when those keys are configured** (set `WORKER_NO_CLOUD=1` to forbid it; the local faster-whisper model is then used and the moment picker falls back to audio peaks).

## 2. Beta on the owner's PC (zero cost)

Needs about 16 GB RAM, 4 free cores, 50 GB free disk, a stable connection. The PC must be on and awake while jobs are expected.

1. Install Docker Desktop (Windows/macOS) or Docker Engine (Linux). No Docker? Install Python 3.12, ffmpeg, then `pip install -r deploy/requirements-worker.txt` and run `python3 scripts/render_worker.py` directly.
2. Clone the code repo (the private one, once it exists, with a read-only deploy key or your own login).
3. Self-test with no network: `python3 scripts/render_worker.py --demo` (needs only ffmpeg and numpy). Expect `DEMO RESULT (status=draft_ready)` and two 1080x1920 drafts under the printed temp folder.
4. `cp deploy/worker.env.example deploy/worker.env` and fill `STUDIO_URL`, `STUDIO_WORKER_KEY`. The key is the same value as KV `studio:cfg:worker_key` (or the Worker secret `STUDIO_WORKER_KEY`); never paste it into chat, git or an issue. `deploy/worker.env` is git-ignored.
5. `mkdir -p data/{work,out,uploads,ingest,models,recordings} && sudo chown -R 1000:1000 data` (Linux/macOS), then `docker compose -f deploy/docker-compose.yml up -d --build worker`. First build installs ffmpeg and the Python packages; the speech models (3 GB) download on the first job (or build with `--build-arg PRELOAD_MODELS=1`).
6. Watch it: `docker compose -f deploy/docker-compose.yml logs -f worker` (one JSON object per line: `job_start`, `job_done`, `job_failed`, `disk_low` ...). Stop: `docker compose ... down` (graceful: running jobs get up to 10 minutes).
7. Keep `state/UPLOAD_HOLD` in place until you decide otherwise; the worker does not read it because it never uploads, the uploader does.

Without Docker on Linux use `deploy/render-worker.service` (systemd, `Restart=always`, sandboxed) as described in the file header. On Windows without Docker, run the Python command in a terminal or Task Scheduler; the systemd unit does not apply.

## 3. Cheap VPS later

Same files. Choose a plan by CPU count (4 vCPU per parallel job, `WORKER_CONCURRENCY`) and 8 GB RAM per job; prices and capacity estimates are in `docs/PRODUCT_PLAN.md` (do not trust numbers copied elsewhere, they change).

1. Create the server (Ubuntu LTS), add your SSH key, `ufw default deny incoming`, `ufw allow OpenSSH`; add `1935/tcp` and `8890/udp` only if you run the ingest.
2. `curl -fsSL https://get.docker.com | sh` (or the distro packages), add the deploy key of the private code repo as read-only, `git clone`.
3. Steps 4-6 of section 2. Update later with `git pull && docker compose -f deploy/docker-compose.yml up -d --build`.
4. Dead-man switch: the studio Worker should alert when nothing has claimed for N minutes (not built; the architecture doc lists it in section 9, point 6).
5. Backups: none needed for the worker (drafts are disposable, they are re-creatable and are uploaded as private YouTube videos); back up only `deploy/worker.env` in your password manager.

## 4. Environment reference

See `deploy/worker.env.example` (placeholders only) and the header of `scripts/render_worker.py`. Anything that looks like a key never goes into the image, the compose file or git.

## 5. Making the repository private while the owner's Actions loops keep working

**Why it is not just a toggle.** The loops for the owner's channels (live-loop 5 h 40 m re-dispatching, shorts, long videos, monitor, ...) run on GitHub Actions and commit their state into the repo. A public repo gets unlimited free Actions minutes; a private repo on the free plan gets a monthly quota (2,000 minutes [verify the current number]) which one day of loops exceeds. So making the repo private either stops the loops or costs money, unless the loops move to your own server (section 5, option D).

### Options

| | A. Leave public | B. Everything private | **C. Public shell + private code** | D. Loops on the private server too |
|---|---|---|---|---|
| Code visible | yes | no | no (only workflow YAML and state) | no |
| Loops keep running free on Actions | yes | **no** (quota) unless you pay | **yes** (the shell is public) | not on Actions at all |
| Effort | none | low | medium (one time, generator included) | high (rewrite scheduling, 24/7 box) |
| Risk | competitors can copy the code and history | loops stop | logs are public (see below); two repos to keep in sync | server reliability, no free runner |
| Fits the plan | no (the business needs private code) | no | **yes, as the transition** | the final target (architecture doc section 9) |

Recommended: **C now, D later** when the VPS exists, then the shell repo can disappear.

### Option C design

* **Private repo (code):** the current repository, made private. Contains everything (scripts, config, assets, app, tests, docs, history).
* **Public repo (shell):** new, empty history. Contains `.github/workflows/*.yml` and `state/` only. Every workflow's `actions/checkout@v4` is followed by a composite action (`.github/actions/get-code`) that checks out the private repo with an SSH **read-only deploy key** into `_code/` and copies `scripts config assets app tests` into the workspace, so every existing command (`python3 scripts/...`, `state/...`) works unchanged.
* Loops still commit state into the shell (as they do today). `.gitignore` of the shell blocks the copied code dirs from being committed.
* Generate the shell files: `python3 deploy/make_shell_repo.py --out ../oded-highlights-shell --code-repo <owner>/<private-repo> --with-state` (read-only on this checkout; refuses a non-empty target). Verified on the current 29 workflows: 27 checkout steps rewritten in 27 files, all YAML parses. Review `git diff` of the result before pushing; 2 workflows have no checkout.

**Pros:** keeps free 24/7 Actions for your own channels; code, history and future customer-facing logic private; no change to the scripts; reversible.
**Cons / watch-outs:**
1. Workflow **logs of a public repo are public**. Secrets are masked, but a Python traceback prints source lines of the failing code into the public log. Keep prints terse, avoid `set -x`, do not run untrusted code; accept that small fragments can appear. (Compiling to `.pyc` does not work because workflows call `python3 scripts/x.py`.)
2. Secrets must be re-created in the shell repo (workflows run there). Rotate every secret that ever lived in the old repo's Actions as a precaution: `GROQ_API_KEY`, `GEMINI_API_KEY*`, `YT_*`, `YT2_*`, `CF_API_TOKEN`. Create a new key per service rather than reusing.
3. **History stays visible somewhere:** already-cloned copies and forks of the public repo keep the code; making it private does not erase them. That is why the plan keeps the current repo as the private one and starts the shell with a clean history.
4. Workflows that commit code-like files (`config/styles/*.json`, `assets/final_thumbs`, `docs/QUALITY_REPORT.md`, fonts) would commit them to the **shell** (the workspace copy), not the private repo. Move those writers to push to the private repo with a read-write deploy key, or accept the shell holding those outputs. List them: `grep -n "git add" .github/workflows/*.yml | grep -v "state/"`.
5. `app/worker.js` (`const REPO = "MaorMichaelov/oded-highlights"`) reads state/files and dispatches workflows through the GitHub API; it must point at the **shell** (where state and workflows live) and its token must be valid for it. `app/studio.js` lists `config/styles` from GitHub without a token: it falls back to the built-in signature style when the repo is private. These are one-line changes and a Worker redeploy (not done here).
6. Anyone can fork a public shell and run its workflows, but without `CODE_DEPLOY_KEY` the code step fails; secrets are not available to forks' pull requests. Do not use `pull_request_target` anywhere, and restrict who can open workflow runs (Settings, Actions, "Require approval for first-time contributors").
7. The deploy key is a secret of the shell repo: anyone who can edit workflows in the shell can read the private code. Keep the shell's write access to yourself.

### Exact steps for the owner (nothing here was done for you)

1. **Backup:** `git clone --mirror https://github.com/MaorMichaelov/oded-highlights.git oded-highlights-backup.git` and keep it somewhere private.
2. **Make the shell files:** on a checkout of main, `python3 deploy/make_shell_repo.py --out ../oded-highlights-shell --code-repo MaorMichaelov/oded-highlights --with-state`. (The code repo keeps its current name; only its visibility changes later. If you prefer a new name, rename in step 5 and pass the new name here.)
3. **Create the empty PUBLIC shell repo** on GitHub (e.g. `oded-highlights-shell`, no README). In `../oded-highlights-shell`: `git init && git add -A && git commit -m "workflow shell" && git branch -M main && git remote add origin <url> && git push -u origin main`.
4. **Deploy key:** `ssh-keygen -t ed25519 -N "" -f ./shell_deploy_key` (a throwaway local file). Add `shell_deploy_key.pub` to the private code repo: Settings, Deploy keys, Add, **do not tick "Allow write access"**. Add the **private key** content as secret `CODE_DEPLOY_KEY` in the shell repo (Settings, Secrets and variables, Actions). Then delete both local key files.
5. **Re-create the Actions secrets** in the shell repo (names listed above) with fresh values; run one cheap workflow by hand first, e.g. `app-test`, and open its log: the get-code step must succeed and `scripts/` must exist. Then run `live-loop` by hand and confirm it commits state into the shell.
6. **Make the code repo private:** Settings, General, Danger zone, "Change visibility", Private. Do this only after step 5 worked (the deploy key works while the repo is still public too), otherwise the live loops stop until the shell runs. Renaming is optional.
7. **Disable the loops in the old repo** (Actions tab, each workflow, Disable) once the shell versions run, so two copies do not fight over state and YouTube quota. The old repo's schedule/dispatch loops then stop; `state/UPLOAD_HOLD` keeps applying because the shell carries `state/`.
8. **Re-point the dispatcher:** in the Cloudflare Worker change `REPO` to the shell (`app/worker.js` line 4 and the watchdog that restarts `live-loop` every 5 minutes) and its GitHub token to one that can dispatch workflows in the shell; run `python3 app/deploy.py --dry-run` first. Not done here: it is a Worker deploy.
9. Rotate the old secrets (Groq, Gemini, Google OAuth client secret and refresh tokens, Cloudflare token) at their providers, update the shell secrets and the Worker secrets, then delete the old repo's Actions secrets.
10. **Rollback:** make the code repo public again and re-enable its workflows; nothing in the code changed.

State that was never changed by this work: repository visibility, workflows, secrets, `state/UPLOAD_HOLD`, the deployed Worker.

## 6. Cutover order (from the architecture document, section 9)

(a) Run the worker next to Actions for the owner's own channel with `UPLOAD_HOLD` still on and compare the outputs; (b) move `live-loop` last (needs a box that is up 24/7), keep the Worker watchdog; (c) disable workflows; (d) delete the shell repo. Until (d), customers' jobs only ever run on the private server.

## 7. Status of this work

Built and tested locally: worker loop against a mocked studio (retries, timeouts, concurrency, graceful stop, cleanup, redaction), the real pipeline on a generated video (demo mode), ingest with a real MediaMTX, shell-repo generator (YAML validated). Not tested: Docker image build (no daemon in the sandbox; `docker compose config` validates), a real studio API, real speech models in this environment, SRT, a VPS, GitHub-side steps in section 5. Missing: browser file upload, upload step wiring after approval, dead-man switch alert, multi-worker claim safety (KV is eventually consistent; see TODO(D1) in `app/studio.js`, run one worker until that is fixed).

## 8. Interim: the preview phase on GitHub Actions

Until the private server exists, `.github/workflows/studio-worker.yml` runs `render_worker.py --once --max-minutes N` every 5 minutes (only when a job is queued) and publishes small 720p previews. Setup, limits and the owner commands: `docs/STUDIO_PREVIEW_SETUP.md` (Hebrew first). Actions must not serve paying customers; this is a bridge for the owner's own tests.

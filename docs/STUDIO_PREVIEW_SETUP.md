# הפעלת ה-Studio בשלב ה-Preview (GitHub Actions כמחשב זמני) / Studio preview worker on GitHub Actions

## תקציר (עברית)

**הבעיה.** ב-Studio (`https://studio-app.odedhl.workers.dev`) עבודה שנוצרת נשארת "בתור" כי אין שום worker שמחובר ומושך אותה. **הפתרון הזמני והחינמי:** workflow ב-GitHub Actions (`.github/workflows/studio-worker.yml`) שרץ כל 5 דקות, שואל את ה-Studio בבקשת curl זולה "יש עבודה בתור?", ורק אם כן מתקין ffmpeg וחבילות, מריץ `scripts/render_worker.py --once` (לוקח את העבודות, חותך, בודק איכות), מעלה **תצוגה מקדימה קטנה (720p)** של כל טיוטה כקובץ ב-GitHub Release, ושם את הקישור ב-Studio, כך שהטיוטה מתנגנת ישר באפליקציה.

**מה אתה צריך לעשות (2 דקות, פעם אחת).** אני (Claude) לא יוצר ולא קורא סודות. את שלושת הצעדים האלה אתה מריץ במחשב שלך, עם החשבונות שלך:

1. **טוקן ל-Cloudflare** (פעם אחת): https://dash.cloudflare.com/profile/api-tokens ← Create Token ← Create Custom Token ← הרשאה אחת: **Account, Workers KV Storage, Edit** ← Continue ← Create. שמור את הטוקן (נראה פעם אחת). אין צורך לשמור אותו בקובץ.
2. **התחבר ל-GitHub CLI** (אם עוד לא): `gh auth login` (בחר GitHub.com, HTTPS, דפדפן).
3. **הרץ את הסקריפט** מתוך תיקיית הריפו (Git Bash / WSL / Mac / Linux; צריך `curl`, `openssl`, `python3`, `gh`):

```bash
git pull
scripts/setup_studio_worker.sh --trusted-orgs ORG_ID
```

   הסקריפט שואל בשקט (בלי להציג) את הטוקן של Cloudflare, ואז: מייצר מפתח אקראי, שומר אותו ב-KV תחת `studio:cfg:worker_key`, שומר אותו וגם את כתובת ה-Studio כסודות ב-GitHub (`STUDIO_WORKER_KEY`, `STUDIO_URL`), בודק שה-Studio מקבל את המפתח (מדפיס רק קוד HTTP) ומפעיל הרצה אחת של ה-workflow. **המפתח לא מודפס ולא נשמר בקובץ.** `--dry-run` מראה מה היה קורה בלי לשנות כלום; `--ask-key` מאפשר להקליד מפתח משלך (מוסתר); `--no-run` לא מפעיל הרצה.

**איך מוצאים את `ORG_ID`** (מזהה הארגון של חשבון הבדיקה שלך, נראה כמו `o_1a2b3c...`): פתח את ה-Studio בדפדפן, היכנס, לחץ F12 ← Console והקלד `localStorage.getItem("studio_org")`. זה הארגון שמותר לו להשתמש בקישורי Kick/Twitch ולקבל תצוגה מקדימה. אפשר גם בלי `--trusted-orgs` (ואז רק קישורים רגילים, בלי Kick, ובלי תצוגה מקדימה בדפדפן; הטיוטה עדיין נוצרת).

**מה קורה אחרי זה.** צור בקשה ב-Studio (למשל "תכין 3 שורטס מהסטרים האחרון" או הדבק קישור VOD). תוך עד ~5-10 דקות (ה-cron של GitHub מתעכב לפעמים) ההרצה מתחילה, ההתקדמות מתעדכנת באפליקציה, ובסוף הטיוטות מוכנות עם תצוגה מקדימה. כדי לא לחכות: `gh workflow run studio-worker.yml` או באתר: Actions ← studio-worker ← Run workflow.

**כיבוי:** `gh workflow disable studio-worker.yml` (וזהו; העבודות יחכו בתור). מחיקת הסודות: `gh secret delete STUDIO_WORKER_KEY` ו-`gh secret delete STUDIO_URL`. החלפת מפתח: להריץ שוב את הסקריפט.

**אם אין לך את הכלים / אתה מעדיף ידנית (בלי הסקריפט):**

```bash
KEY="wk_$(openssl rand -hex 32)"                      # המפתח נשאר במשתנה בטרמינל הזה בלבד; אל תדפיס אותו
printf '%s' "$KEY" | gh secret set STUDIO_WORKER_KEY --repo MaorMichaelov/oded-highlights
printf '%s' "https://studio-app.odedhl.workers.dev" | gh secret set STUDIO_URL --repo MaorMichaelov/oded-highlights
printf '%s' "ORG_ID" | gh secret set STUDIO_TRUSTED_ORGS --repo MaorMichaelov/oded-highlights   # אופציונלי
```

ובדשבורד של Cloudflare: Workers & Pages ← KV ← ה-namespace בשם **studio-app** ← Add entry ← Key: `studio:cfg:worker_key`, Value: אותו מפתח בדיוק (תוציא אותו בעזרת `printf '%s' "$KEY" | clip` ב-Windows / `pbcopy` ב-Mac / `xclip -selection clipboard` ב-Linux, בלי להציג על המסך). אלטרנטיבה: Worker `studio-app` ← Settings ← Variables and Secrets ← Add **Secret** בשם `STUDIO_WORKER_KEY`.

> **אזהרה:** ה-Studio הנוכחי (`studio-app`) הוא הסביבה לתצוגה מקדימה. **לא** מפעילים את זה על `oded-app` (האפליקציה האמיתית שלך) ולא נוגעים בלולאות של אודד. הסקריפט מסרב לכתובת `oded-app`.

---

## איך זה בנוי

```
דפדפן ── Studio (Cloudflare Worker studio-app, KV: תור, חשבונות, עבודות)
                 ^   POST /studio/worker/queue   (רק סופר: כמה בתור, לא נוגע בכלום)
                 |   POST /studio/worker/claim   (לוקח עבודה)    POST /studio/worker/jobs/:id (התקדמות, טיוטות + preview_url)
GitHub Actions: studio-worker.yml (כל 5 דקות, קבוצת concurrency אחת)
   job "check"  : curl אחד (בלי checkout ובלי הרשאות). אין סודות? "secrets not configured", יוצא ירוק.   אין עבודה בתור? יוצא.
   job "render" : checkout לקריאה בלבד, ffmpeg + pip, render_worker.py --once --max-minutes 50
                  עבודה -> job_runner.py (מקור -> תמלול -> רגעים -> 9:16 -> QA) -> preview_publish.py (720p -> Release asset) -> draft.preview_url
   job "cleanup": פעם בלילה (03:00 UTC) מוחק Releases של תצוגה מקדימה בני יותר מ-7 ימים
```

**אין שני runners על אותה עבודה.** ה-claim ב-Studio לא אטומי (KV עקבי בסופו של דבר, ראה `TODO(D1)` ב-`app/studio.js`), לכן הקבוצה `concurrency: studio-worker` מבטיחה שרצה הרצה אחת בלבד; הרצה חדשה ממתינה ולא מבטלת רינדור קיים.

**מצב `--once` / `--max-minutes N` ב-`scripts/render_worker.py`:** `--once` = לוקח עבודות מהתור עד שהוא ריק, מחכה שהעבודות הרצות יסתיימו ויוצא (לא מחכה לעבודות חדשות; אם ה-API לא זמין 5 ניסיונות ברצף הוא מוותר). `--max-minutes N` = תקציב זמן: לא לוקח עבודה חדשה כשנשארו פחות מ-`WORKER_MIN_CLAIM_MIN` (ברירת מחדל 5) דקות, ועבודה שעדיין רצה בתום התקציב נעצרת ומסומנת כנכשלה (ה-Studio מחזיר את הקרדיט). שניהם אפשריים גם בנפרד. קוד יציאה: 0 תקין, 2 הגדרות, 5 מפתח שגוי.

## מקורות (Kick / Twitch) לארגון הבדיקה שלך

* ארגון שה-ID שלו ב-`STUDIO_TRUSTED_ORGS` (סוד, או משתנה ריפו באותו שם) מקבל (`WORKER_TRUSTED_ORGS`): קישורי VOD של **Kick** (`kick.com/video/...`) ו-**Twitch** (`twitch.tv/videos/...`), וגם "הסטרים האחרון שלי": כשהבקשה היא `auto` ולערוץ המאומת יש פלטפורמה, ה-worker מחפש את ה-VOD האחרון של הערוץ (Twitch דרך `yt-dlp`, Kick דרך אותה קריאה ל-API שהלולאות שלך כבר משתמשות בה).
* **לקוחות אחרים נשארים חסומים מ-Kick** (תנאי השימוש של Kick, סעיף 1.4) ומקבלים הודעה ידידותית. גם `auto` מהפלטפורמה זמין רק לארגונים המהימנים.
* כדי שרצה על runner (דיסק ~14GB, שעות מוגבלות) תסתדר, מורידים רק את **30 הדקות הראשונות** של ה-VOD ב-720p. משנים עם משתנה ריפו `STUDIO_SOURCE_MAX_MIN` (למשל 60). קישור עם `#t=התחלה-סוף` (שניות) מוריד עד סוף החלון.
* Kick משנה/חוסם מדי פעם; מ-runner של GitHub זה עבד עד כה ללולאות שלך, אבל זה best-effort.
* תמלול: ברירת מחדל **מקומי על ה-runner** (faster-whisper; המודלים נשמרים ב-cache של Actions), כך שהאודיו לא נשלח החוצה ומכסת Groq/Gemini של הלולאות שלך לא נפגעת. אם אתה רוצה מהר יותר: משתנה ריפו `STUDIO_USE_CLOUD_AI=1` (משתמש ב-`GROQ_API_KEY` / `GEMINI_API_KEY` הקיימים). הרצה על 30 דקות מקור לוקחת בערך 15-35 דקות במצב מקומי.

## איך הטיוטה מגיעה לדפדפן: ההחלטה והמגבלות

**נבחר: Release assets של GitHub, שה-workflow יוצר בעצמו עם ה-`GITHUB_TOKEN` של ההרצה** (הרשאת `contents: write` רק ל-job הזה, שום סוד חדש).
לכל עבודה נוצר Release אחד (Pre-release) בשם `studio-preview-<job>-<8 תווים אקראיים>`, וכל טיוטה היא קובץ mp4: **720p** (720 על 1280 לשורטס), וידאו עד 900kbps, אודיו 64kbps, `faststart`; וידאו ארוך נחתך ל-`STUDIO_PREVIEW_MAX_S` (300 שניות) בתצוגה המקדימה. שורטס של 30 שניות ≈ 3-4MB. הקישור `https://github.com/<repo>/releases/download/<tag>/<file>.mp4` נשמר ב-`draft.preview_url`; `app/studio.html` כבר מנגן `preview_url` ב-`<video>` (אין שינוי UI). ה-Studio מקבל רק קישור בצורה הזו (https, github.com, releases/download, mp4), כך שמפתח worker שדלף לא יכול להפנות את הנגן לאתר אחר.

**למה לא האחרים:** Artifact של Actions דורש התחברות ל-GitHub לצפייה (הדפדפן של הלקוח לא יכול לנגן אותו); מאגר חיצוני (R2/S3/Drive) דורש חשבון וסודות חדשים וגם עלות פוטנציאלית; "בלי תצוגה, רק YouTube" דורש העלאה ליוטיוב, שאסורה כאן בכוונה. Release assets: חינם, ללא מכסת נפח אפקטיבית לריפו ציבורי, עד 2GB לקובץ, אותו מקור לכל האפליקציה.

**מגבלות שחשוב להכיר:**
1. **הריפו ציבורי, ולכן הקישורים ציבוריים** (לא ניתנים לניחוש, אבל כל מי שמקבל את הקישור רואה). לכן תצוגה מקדימה נוצרת **רק לארגונים ברשימה** (`STUDIO_PREVIEW_ORGS`, ברירת מחדל = הרשימה המהימנה). אפשר `*` (כל ארגון) אם אתה מוכן לכך. הטיוטה באיכות מלאה לא מתפרסמת בשום מקום: היא נשארת על ה-runner ונמחקת איתו.
2. נמחק אחרי **7 ימים** (`STUDIO_PREVIEW_DAYS`) על ידי ה-job "cleanup"; אחרי זה הנגן ב-Studio לא יציג את הסרטון.
3. אם ההעלאה נכשלת העבודה **לא** נכשלת: הטיוטה מופיעה בלי תצוגה ("התצוגה המקדימה בהכנה").
4. **לא נבדק מול GitHub אמיתי** (ה-sandbox לא מגיע ל-`*.workers.dev`, ובדקתי את הקוד מול GitHub מדומה). לא ידוע לי מראש אם דפדפן מנגן תמיד ישירות מכתובת ה-redirect של Release; אם הנגן לא מתנגן, תגיד ונעבור לאלטרנטיבה (קובץ דרך ה-Worker עצמו).
5. ה-Release יוצר Tag בריפו (לא commit); אין השפעה על ה-bot שדוחף state.

## מגבלות כלליות של הפתרון הזמני (קרא לפני שמזמינים לקוחות)

* **תנאי השימוש של GitHub Actions אוסרים להריץ עליהם שירות מסחרי.** זה גשר לבדיקות שלך ולכמה חברים, לא ללקוחות משלמים. היעד הוא שרת פרטי: `docs/DEPLOY_PRIVATE_SERVER.md` (אותו `render_worker.py`, בלי `--once`).
* **עבודה שנתקעה "בריצה":** אם GitHub הורג את ה-runner באמצע (ביטול ידני, תקלה), העבודה נשארת במצב "רץ" ולא חוזרת לתור. ביטול ידני של ההרצה שולח SIGINT וה-worker מדווח כשל (הקרדיט חוזר); הריגה קשה לא. אין עדיין "מנגנון חילוץ" ב-Studio. כדאי לבדוק את זה ביד ב-KV אם עבודה תקועה יותר משעה.
* **מכסות:** ריפו ציבורי = דקות Actions חינם; ה-job "check" לוקח ~5 שניות כל 5 דקות. ה-cron של GitHub יכול להתעכב. אחרי 60 יום בלי פעילות GitHub מכבה workflows מתוזמנים (ה-bot שלך דוחף כל הזמן).
* סודות ב-`workflow_dispatch`/`schedule` נחשפים רק לקוד שב-`main`; אל תפעיל workflows מפורקים (forks) שמקבלים את הסודות.
* ה-worker לא יוצר חיבור ל-YouTube בשום שלב. אישור טיוטה ב-Studio לא מעלה כלום כרגע.

## סודות ומשתנים (שמות)

| שם | סוג | מי מגדיר | תפקיד |
|---|---|---|---|
| `STUDIO_URL` | secret | הסקריפט | כתובת ה-Studio (https, בלי path) |
| `STUDIO_WORKER_KEY` | secret | הסקריפט | המפתח; אותו ערך ב-KV `studio:cfg:worker_key` |
| `STUDIO_TRUSTED_ORGS` | secret או variable | `--trusted-orgs` | ארגונים מהימנים: Kick/Twitch + "הסטרים האחרון" + תצוגה מקדימה |
| `STUDIO_PREVIEW_ORGS` | variable | אתה, אופציונלי | מי מקבל תצוגה מקדימה ציבורית (`*` = כולם) |
| `STUDIO_SOURCE_MAX_MIN` | variable | אתה, אופציונלי | כמה דקות מה-VOD להוריד (30) |
| `STUDIO_USE_CLOUD_AI` | variable | אתה, אופציונלי | `1` = מותר להשתמש ב-Groq/Gemini הקיימים |

פקודות: `gh variable set STUDIO_SOURCE_MAX_MIN --body 60 --repo MaorMichaelov/oded-highlights`.

## פתרון תקלות

| סימפטום | סיבה / מה לעשות |
|---|---|
| ההרצה ירוקה ואומרת `secrets not configured` | עוד לא הרצת את הסקריפט (או שהסודות נמחקו) |
| `the studio rejected the worker key` | המפתח ב-GitHub שונה מזה שב-KV: הרץ שוב את הסקריפט (מחליף את שניהם) |
| `studio answered HTTP 404/5xx` | ה-Worker `studio-app` לא נפרס עם `/studio/worker/queue`: `APP_NAME=studio-app python3 app/deploy.py` (אף פעם לא `oded-app`) |
| הכל ירוק אבל העבודה "בתור" | ממתין ל-cron (עד כמה דקות), או הרץ ידנית: `gh workflow run studio-worker.yml` |
| עבודה נכשלה `host_not_allowed` | קישור Kick מארגון שאינו ברשימה המהימנה |
| עבודה נכשלה `no_recording` | `auto` בלי ערוץ מאומת או בלי VOD אחרון, או Kick חסם את ה-runner: הדבק קישור VOD ישיר |
| טיוטה בלי תצוגה | הארגון לא ב-`STUDIO_PREVIEW_ORGS`, או ההעלאה נכשלה (ראה את הלוג: `preview_failed`) |

## מה נבדק ומה לא

נבדק מקומית (בדיקות אוטומטיות בריפו): מצבי `--once`/`--max-minutes` (ריקון תור, תקציב, הריגה בתום הזמן, מפתח שגוי, API לא זמין), ה-Studio האמיתי (`app/studio.js`) מול ה-worker האמיתי על וידאו סינתטי עם קידוד 720p אמיתי ו-GitHub מדומה (`tests/test_studio_preview_e2e.py`), נקודת `/studio/worker/queue` ואימות `preview_url` (`app/studio.test.mjs`), מקורות מהימנים/חסומים (`tests/test_worker_sources.py`), ה-shell של ה-job "check" מול שרת מקומי (בלי סודות / מפתח שגוי / ללא הדפסת המפתח), והסקריפט `setup_studio_worker.sh` עם `curl`/`gh` מדומים (`tests/test_setup_studio_worker.py`).
**לא נבדק:** הרצה אמיתית ב-GitHub (דורשת את הסודות שלך), GitHub Releases אמיתי והנגינה בדפדפן, Kick/Twitch אמיתיים מ-runner, תמלול עם המודלים האמיתיים בסביבה הזו, והגעה ל-`studio-app` מה-sandbox.

---

## English summary

* Problem: Studio jobs stay `queued` because no render worker is connected. Bridge: `.github/workflows/studio-worker.yml` (every 5 min + manual) polls `POST /studio/worker/queue` with a cheap curl; only when jobs wait does it install deps and run `render_worker.py --once --max-minutes 50`, publish 720p previews as release assets of the run's own `GITHUB_TOKEN` (`scripts/preview_publish.py`) and store the URL as `draft.preview_url` (validated in `app/studio.js`).
* Owner step (not done by Claude, no secrets touched): `scripts/setup_studio_worker.sh --trusted-orgs <org id>` (needs `gh auth login` and a Cloudflare token with Workers KV Storage: Edit). It generates the key, writes KV `studio:cfg:worker_key` and the secrets `STUDIO_WORKER_KEY` / `STUDIO_URL` (and `STUDIO_TRUSTED_ORGS`), never prints the key, then checks the studio and dispatches one run.
* Without the secrets the workflow ends green with `secrets not configured`.
* Trusted orgs (`WORKER_TRUSTED_ORGS` <- `STUDIO_TRUSTED_ORGS`) may use Kick and Twitch VOD links and "my last stream" (platform VOD lookup, first 30 min at 720p); every other org stays blocked from Kick.
* Limits: public repo means public (unguessable) preview URLs, only for listed orgs, deleted after 7 days; Actions must not serve paying customers (use the private server); a hard-killed runner leaves a job `running`; real GitHub, real Releases playback and real Kick/Twitch from a runner are untested.

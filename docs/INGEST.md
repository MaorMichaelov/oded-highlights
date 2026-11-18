# קליטת סטרים של לקוחות / Customer stream ingest

## תקציר לבעלים (עברית)

**הבעיה.** כדי לחתוך קליפים מהסטרים של לקוח צריך את הוידאו אצלנו. להוריד אוטומטית מ-Kick אסור לפי תנאי השימוש שלהם (סעיף 1.4), ולכן יש שלוש דרכים נקיות וזולות, כולן עובדות בלי להוציא שקל:

1. **קובץ או קישור** (הכי פשוט): הלקוח נותן קישור לסרטון (YouTube, Drive/Dropbox ישיר, כל קישור ש-`yt-dlp` קורא) או קובץ ש**אתה** שם בתיקיית `UPLOAD_DIR` בשרת. ה-worker מוריד/קורא, חותך, ובודק איכות. **מה עוד חסר:** מסך העלאה בדפדפן (ה-Worker של Cloudflare לא שומר קבצים גדולים). בשלב הבטא (עד 10 לקוחות): קישור או `scp`. בהמשך: העלאה ישירה ל-Cloudflare R2 (10GB חינם) עם קישור חתום.
2. **ריסטרים (מומלץ ללקוחות רציניים):** הלקוח מוסיף ב-OBS יעד שני: `rtmp://השרת-שלך:1935/live/<מפתח-סטרים-אישי>`. שרת חינמי (MediaMTX, קובץ אחד) מקליט לקטעים של 5 דקות. כשהסטרים נגמר (10 דקות בלי קטעים חדשים) סקריפט (`scripts/ingest_watcher.py`) פותח אוטומטית עבודה ב-Studio, וה-worker מכין טיוטות. אפשר גם "קליפים בזמן אמת": כל N דקות נפתחת עבודה על מה שהוקלט עד עכשיו (`--live-every-min 15`).
3. **VOD ידני של הבעלים** (הערוצים שלך): כמו היום, ב-Actions.

**איך זה מאובטח.** רק מי שיש לו מפתח (`ik_...`, נוצר בלחיצה בסטודיו, נשמר רק כ-hash) יכול לשדר; כל השאר נדחים בשכבת ההרשאה של MediaMTX. המפתח לא מופיע בשמות קבצים או בעבודות. אפשר להחליף מפתח בלחיצה.

**מה נבדק באמת (בסנדבוקס):** הורדתי MediaMTX v1.11.3 אמיתי, שידרתי אליו RTMP עם ffmpeg: מפתח שגוי נדחה, מפתח נכון הוקלט, ה-watcher יצר עבודה, ה-worker הפיק טיוטה עם QA. **לא נבדק:** SRT, Docker (אין daemon בסנדבוקס, רק `docker compose config`), שידור מ-OBS אמיתי, חיבור לשרת הסטודיו האמיתי.

**מה אתה צריך לעשות:** (א) להחליט איפה השרת רץ: מחשב ביתי = פתיחת פורט 1935/tcp ו-8890/udp בראוטר + שם דינמי חינם (DuckDNS); או VPS זול (ללא טיפול בראוטר). (ב) להריץ `deploy/ingest/run_ingest.sh` או `docker compose --profile ingest up`. (ג) לפרוס את שינוי ה-Worker (נקודת הקצה `/studio/worker/ingest` ומפתח הריסטרים ב-`app/studio.js`) כשאתה מוכן. פרטים בהמשך באנגלית.

---

## 1. Options at a glance

| Option | Customer effort | Our cost | Latency | ToS | Status |
|---|---|---|---|---|---|
| **A. Link** (`source.type="url"`, `ref="https://..."`) | paste a link | bandwidth only | after the video exists | fine for the customer's own YouTube/Drive/Dropbox links; **Kick links are refused** for customers (`WORKER_BLOCK_HOSTS`) | works (yt-dlp), tested with a fake downloader |
| **B. File** (`ref="upload:<name>"`, file in `$UPLOAD_DIR`) | send us the file (today: owner copies it in; browser upload not built) | disk | after the stream | fine | works, tested with real ffmpeg clips |
| **C. Restream** (OBS second output to `rtmp://host/live/<key>`) | one-time OBS setting | disk about 2.7 GB per stream hour at 6 Mbps; one cheap VPS or the owner's PC | stream end, or every N minutes while live | cleanest: the customer sends it to us | works end to end locally (see section 5) |
| **D. Platform VOD download** (Kick/Twitch) | none | none | after the stream | **Kick ToS 1.4 forbids it**; keep only for the owner's own channels (`WORKER_TRUSTED_ORGS`) | existing Actions code, not used for customers |

All sources end in one local media file inside the job's scratch folder (`scripts/worker_sources.py`). Safety rules there: allowed local roots only, flat file names (no `..`, no sub paths), symlinks resolved before the root check, http(s) only, private/loopback/link-local addresses refused (SSRF), `yt-dlp --no-playlist --max-filesize`, source length 30 s to `WORKER_MAX_SOURCE_H` (default 8 h), a source without audio is refused.

## 2. Link / file jobs (no extra software)

The customer API already accepts them: `POST /studio/api/orgs/:org/jobs` with `{"channel_id": "...", "source": {"type": "url", "ref": "https://..."}, "shorts": 5, "long": true}`. For a file, copy it to the server and use `ref: "upload:name.mp4"`:

```
scp name.mp4 server:/opt/oded-studio/data/uploads/
```

`#t=START-END` (seconds) after any ref cuts a window first, e.g. `upload:show.mp4#t=600-1800`.
Missing piece: a browser upload. Suggested zero-cost design (not built): the Worker hands out a presigned PUT URL for a Cloudflare R2 bucket (10 GB free [verify]), the customer uploads straight to R2, the job gets `ref: "https://<signed GET url>"` and the worker downloads it. Needs R2 credentials in the Worker, so it was left for the owner to decide.

## 3. Restream ingest (MediaMTX + watcher)

```
OBS (customer) --RTMP/SRT--> MediaMTX :1935 / :8890 --records--> recordings/live/<key>/*.ts   (5-minute MPEG-TS segments)
                                  |  auth hook (every publish)            |
                                  v                                       v
                      ingest_watcher.py :8899/auth              ingest_watcher.py (scan every 30 s)
                      (key known? else refused)                 stream over = no new segment for 10 min
                                                                  -> move segments to ingest/s<hash>-<start>/
                                                                  -> POST /studio/worker/ingest {op:"job", ref:"ingest:s<hash>-<start>"}
                                                                  -> job queued -> render_worker.py claims it
```

**Customer side.** In the studio the owner of a verified channel presses "restream key" (`POST /studio/api/orgs/:org/channels/:cid/ingest`, shown once, replaced on the next call). In OBS: Settings, Stream, Service "Custom": Server `rtmp://<ingest host>/live`, Stream key `ik_...`. To keep streaming to Kick/Twitch at the same time the customer needs a second output: OBS plugins such as "Multiple RTMP outputs" / Aitum Multistream, or a restream service whose free tier accepts a custom RTMP target [verify per service]. SRT alternative: `srt://<host>:8890?streamid=publish:live/<key>`.

**Server side.** Two ways, same config (`deploy/ingest/mediamtx.yml`):

```
# Docker (worker + MediaMTX + watcher)
cp deploy/worker.env.example deploy/worker.env     # fill STUDIO_URL and STUDIO_WORKER_KEY
mkdir -p data/{work,out,uploads,ingest,models,recordings} && sudo chown -R 1000:1000 data
docker compose -f deploy/docker-compose.yml --profile ingest up -d --build

# no Docker
STUDIO_URL=https://... STUDIO_WORKER_KEY=... deploy/ingest/run_ingest.sh --live-every-min 0
```

Offline (no studio, owner beta): `deploy/ingest/run_ingest.sh --spool data/spool --keys-file data/keys.json` with `keys.json = {"ik_<32 hex>": {"org":"o_1","channel":"c_1","shorts":5,"long":true}}`, and `python3 scripts/render_worker.py --spool data/spool`.

**Network.** Open `1935/tcp` (RTMP) and `8890/udp` (SRT) only. A VPS needs just the firewall rule. A home PC needs router port forwarding plus a free dynamic DNS name (DuckDNS) and must stay on during streams; Cloudflare's free tunnel does not carry raw RTMP, so it is not an option here.

**Behaviour you can rely on.**
* Unknown keys cannot publish (auth hook); only path `live/ik_<32 hex>` is recorded; the recorder never serves video to the outside.
* A dropped connection that comes back within `--end-after-s` (600) is the same stream. Streams under `--min-stream-s` (120 s) are discarded (test streams).
* Live clipping (`--live-every-min N`): while the stream runs, closed segments are hard-linked into their own folder and become a job (3 Shorts, no long video); at the end only the not yet handed over rest becomes the final job. No segment is processed twice.
* Credits: a job costs `ceil(minutes/60)` like any job; if the customer has none (HTTP 402) the recording stays in `ingest/` for `--keep-days` (3) and no job is made. Job creation is idempotent by folder name, a studio outage is retried (state in `ingest/.watcher_state.json`).
* Disk: recordings of ended streams move to `ingest/` and are deleted after 3 days; the worker deletes its scratch after each job.

**Known limits.** Plain RTMP sends the key unencrypted (use SRT with a passphrase or RTMPS with a certificate for stricter customers; not configured). One watcher instance only. `ingest_watcher.py` trusts MediaMTX's file layout (v1.11.3, MPEG-TS, `recordPath` in `deploy/ingest/mediamtx.yml`); update the version knowingly. nginx-rtmp is an alternative recorder but was not evaluated (it is unmaintained upstream).

## 4. How the worker finds the source

`job.source = {type, ref}` from the studio: `url`/`vod`/`live` with `ref` = link, `upload:<name>`, `ingest:<folder>`; `auto` ("my last stream") picks the newest recording folder named after the job's channel id under `$INGEST_DIR`. If nothing is found the job fails with a clear message and the credit is refunded by the studio.

## 5. What was tested here (17-18 Nov 2026, sandbox)

* Real MediaMTX v1.11.3 binary with `deploy/ingest/mediamtx.yml`: publish with an unknown key refused; publish with a known key recorded to `recordings/live/<key>/*.ts`; watcher turned the finished stream into a spool job; `render_worker.py --spool` produced a QA-graded 1080x1920 draft from it (demo transcriber, no models).
* `deploy/ingest/run_ingest.sh` starts and stops both processes cleanly.
* Unit tests: `tests/test_ingest_watcher.py` (hand-off, live windows, retries, auth hook), `tests/test_worker_sources.py` (path/URL safety, concat, windows).
* **Not tested:** SRT publishing, Docker builds (no Docker daemon), OBS, a live studio API, a Windows host.

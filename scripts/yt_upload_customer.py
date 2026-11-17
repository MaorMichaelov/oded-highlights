#!/usr/bin/env python3
"""Upload one finished draft to a STUDIO CUSTOMER's own YouTube channel (customer version of yt_upload.py).
usage: yt_upload_customer.py VIDEO.mp4 META.json [THUMB.jpg] --org O_ID --job J_ID [--channel C_ID] [--expect-channel UCxxxx]
META.json: {"title","description","tags":[],"categoryId":"24","lang":"he", "privacy":"private" (can only make the video MORE private than policy)}

How it differs from yt_upload.py: there is NO refresh token here. The Worker (app/youtube_connect.js) holds the customer's refresh token encrypted; this script asks
POST $STUDIO_URL/internal/yt/token (header x-worker-key: $STUDIO_WORKER_KEY) for a ~1 h access token + the customer's upload POLICY and then:
  - verifies via channels.list?mine=true that the token really belongs to the connected channel (and --expect-channel / the broker's channel id) -> else exit 3
  - uploads PRIVATE unless the policy says otherwise; publishAt comes only from the policy (customer's schedule mode), never from META
  - respects state/UPLOAD_HOLD (exit 4), quota (exit 6, reported to the broker so the whole project stops for the day), needs_reconnect (exit 5)
  - resumable upload in 8 MiB chunks streamed from disk; transient errors -> exponential backoff + resume from the byte YouTube has;
    the session URI is kept on disk, so a re-run after a crash resumes the same upload instead of creating a second video (which would burn quota again)
  - reports the result to /internal/yt/report (refunds the reservation when nothing was created)
Env: STUDIO_URL, STUDIO_WORKER_KEY (GitHub Actions secrets), optional YT_UPLOAD_SESSION_DIR, YT_CHUNK_MB.
Exit codes: 0 ok | 1 error | 2 usage | 3 wrong channel | 4 upload hold | 5 customer must reconnect | 6 quota / daily limit (retry later) | 7 bad input
Nothing here ever prints a token. The module has no import-time side effects, so the tests can drive main() with a fake transport."""
import datetime as dt, hashlib, json, os, random, re, sys, tempfile, time, urllib.error, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
HOLD_FILE = os.path.join(HERE, "..", "state", "UPLOAD_HOLD")
UPLOAD_INIT = "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status"
THUMB_URL = "https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId="
CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels?part=id,snippet&mine=true"
CHUNK_ALIGN = 256 * 1024                      # resumable chunks must be multiples of 256 KiB (except the last)
SESSION_MAX_AGE_S = 6 * 86400                 # YouTube keeps a resumable session about a week
OK, ERR, USAGE, WRONG_CHANNEL, HOLD, RECONNECT, QUOTA, BAD_INPUT = 0, 1, 2, 3, 4, 5, 6, 7
QUOTA_REASONS = {"quotaExceeded", "dailyLimitExceeded", "uploadLimitExceeded", "dailyLimitExceededUnreg"}
RETRY_REASONS = {"rateLimitExceeded", "userRateLimitExceeded", "backendError", "internalError", "serviceUnavailable", "processingFailure"}


class Fail(Exception):
    def __init__(self, code, msg): super().__init__(msg); self.code = code


class SessionGone(Fail):
    pass


class NetError(Exception):
    pass


def hold_active(path=HOLD_FILE, now=None):
    """state/UPLOAD_HOLD holds a future UTC timestamp: nothing may be uploaded until then (owner request, same as yt_upload.py). Returns the end time or None."""
    try:
        if not os.path.exists(path): return None
        with open(path) as f: txt = f.read().strip()
        until = dt.datetime.fromisoformat(txt.replace("Z", "+00:00"))
        if until.tzinfo is None: until = until.replace(tzinfo=dt.timezone.utc)
        return until if (now or dt.datetime.now(dt.timezone.utc)) < until else None
    except Exception as e:
        print("hold check error (ignored):", e); return None


def urllib_http(method, url, headers=None, body=None, timeout=120):
    """Default transport. Returns (status, {lower-case header: value}, bytes). HTTP errors are returned, network errors raise NetError."""
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r: return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read()
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in (e.headers or {}).items()}, e.read()
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        raise NetError(type(e).__name__)


def _load_json(path):
    with open(path, encoding="utf-8") as f: return json.load(f)


def _save_json(path, obj):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)          # session URIs are bearer-like: owner-only file
    with os.fdopen(fd, "w", encoding="utf-8") as f: json.dump(obj, f)


def jbody(b):
    try: return json.loads(b.decode("utf-8")) if b else {}
    except Exception: return {}


def google_error(status, body):
    """-> (kind, reason): kind in quota | retry | auth | forbidden | fatal."""
    j = jbody(body); e = j.get("error") if isinstance(j, dict) else None
    reasons = [x.get("reason") for x in (e.get("errors") or [])] if isinstance(e, dict) else []
    reason = reasons[0] if reasons else (e if isinstance(e, str) else "")
    if any(r in QUOTA_REASONS for r in reasons): return "quota", reason
    if status == 401: return "auth", reason or "unauthorized"
    if status >= 500 or status == 429 or any(r in RETRY_REASONS for r in reasons): return "retry", reason or str(status)
    if status == 403: return "forbidden", reason or "forbidden"
    return "fatal", reason or str(status)


class Broker:
    """Client of the Worker's internal endpoints."""
    def __init__(self, base, key, http):
        self.base, self.key, self.http = base.rstrip("/"), key, http

    def _post(self, path, payload):
        try: st, _, b = self.http("POST", self.base + path, {"content-type": "application/json", "x-worker-key": self.key}, json.dumps(payload).encode())
        except NetError as e: raise Fail(ERR, f"broker unreachable ({e})")
        return st, jbody(b)

    def token(self, org, chan, job, thumbnail=False, renew=False):
        st, j = self._post("/internal/yt/token", {"org_id": org, **({"channel_id": chan} if chan else {}), "job_id": job, "thumbnail": bool(thumbnail), "renew": bool(renew)})
        if st == 200 and j.get("access_token"): return j
        err = j.get("error", str(st))
        if st == 409 and err == "needs_reconnect": raise Fail(RECONNECT, f"customer must reconnect YouTube ({j.get('channel_title', '')})")
        if st == 429: raise Fail(QUOTA, f"{err}: retry after {j.get('retry_after_s', '?')} s" + (f" (resets {j['reset_at']})" if j.get("reset_at") else ""))
        if st == 502 and j.get("transient"): raise Fail(ERR, "Google token endpoint transient error, retry later")
        raise Fail(ERR, f"broker refused token: HTTP {st} {err}")

    def report(self, org, chan, job, event, **kw):
        try: self._post("/internal/yt/report", {"org_id": org, **({"channel_id": chan} if chan else {}), "job_id": job, "event": event, **kw})
        except Fail as e: print("report failed (ignored):", e)


def resolve_status(meta, policy):
    """The server policy is authoritative. META may only ask for MORE privacy ('private'); publishAt comes from the policy's schedule slot only."""
    privacy = "private"; publish_at = None; notes = []
    if policy.get("privacy") == "public" and meta.get("privacy") == "public": privacy = "public"
    elif meta.get("privacy") in ("public", "unlisted") and policy.get("privacy") != "public": notes.append("meta privacy %r ignored: policy keeps the video private" % meta.get("privacy"))
    if policy.get("publish_at") and privacy == "private": publish_at = policy["publish_at"]
    if meta.get("publishAt") and not publish_at: notes.append("meta publishAt ignored: only the customer's schedule policy may schedule a publication")
    if policy.get("downgraded"): notes.append("policy downgraded to private: " + str(policy["downgraded"]))
    return privacy, publish_at, notes


def build_body(meta, privacy, publish_at):
    tags, total = [], 0
    for t in meta.get("tags") or []:                       # YouTube: tags total <= 500 chars
        t = str(t).strip()
        if t and total + len(t) + 1 <= 480: tags.append(t); total += len(t) + 1
    lang = meta.get("lang") or "he"
    body = {"snippet": {"title": str(meta["title"]).strip()[:100], "description": str(meta.get("description", ""))[:4900], "tags": tags, "categoryId": str(meta.get("categoryId", "24")),
                        "defaultLanguage": lang, "defaultAudioLanguage": lang},
            "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False}}
    if publish_at: body["status"]["publishAt"] = publish_at
    return body


def parse_range_end(headers):
    m = re.match(r"bytes=0-(\d+)", headers.get("range", "") or "")
    return int(m.group(1)) + 1 if m else 0


def session_path(directory, video, org, chan, size):
    st = os.stat(video); key = hashlib.sha256(f"{os.path.realpath(video)}|{size}|{st.st_mtime_ns}|{org}|{chan}".encode()).hexdigest()[:24]
    return os.path.join(directory, key + ".json")


class Uploader:
    def __init__(self, broker, http, org, chan, job, sleep=time.sleep, chunk=8 * 1024 * 1024, session_dir=None, max_failures=8, log=print):
        self.b, self.http, self.org, self.chan, self.job, self.sleep, self.log = broker, http, org, chan, job, sleep, log
        self.chunk = max(CHUNK_ALIGN, (chunk // CHUNK_ALIGN) * CHUNK_ALIGN); self.max_failures = max_failures
        self.session_dir = session_dir or os.path.join(tempfile.gettempdir(), "oded_yt_sessions"); self.tok = None

    # ---- auth ----
    def authorize(self, thumbnail, renew=False):
        self.tok = self.b.token(self.org, self.chan, self.job, thumbnail=thumbnail, renew=renew); return self.tok

    def hdr(self, extra=None):
        h = {"authorization": "Bearer " + self.tok["access_token"]}; h.update(extra or {}); return h

    def verify_channel(self, expect=None):
        """Defence in depth: whatever the broker says, the token must really belong to the connected channel."""
        st, _, b = self.http("GET", CHANNELS_URL, self.hdr())
        if st != 200: raise Fail(ERR, f"channels.list failed: HTTP {st} {google_error(st, b)[1]}")
        items = jbody(b).get("items") or []; mine = items[0].get("id") if items else ""
        want = self.tok.get("channel_id")
        if not want or mine != want or (expect and mine != expect):
            raise Fail(WRONG_CHANNEL, f"REFUSED: the token's channel is {mine!r}, the connected channel is {want!r}" + (f", expected {expect!r}" if expect else ""))
        return mine

    # ---- resumable upload ----
    def _sess_load(self, path, size):
        try:
            j = _load_json(path)
            if j.get("size") == size and time.time() - j.get("created", 0) < SESSION_MAX_AGE_S and j.get("channel_id") == self.tok.get("channel_id"): return j
        except Exception: pass
        return None

    def _init(self, size, body):
        h = self.hdr({"content-type": "application/json; charset=UTF-8", "x-upload-content-type": "video/mp4", "x-upload-content-length": str(size)})
        for attempt in range(1, self.max_failures + 1):
            try: st, rh, b = self.http("POST", UPLOAD_INIT, h, json.dumps(body, ensure_ascii=False).encode("utf-8"), 60)
            except NetError as e: st, rh, b = 0, {}, b""; self.log(f"init network error ({e}), attempt {attempt}")
            if st == 200 and rh.get("location"): return rh["location"]
            kind, reason = google_error(st, b) if st else ("retry", "network")
            if kind == "quota": raise Fail(QUOTA, f"YouTube quota/upload limit reached ({reason})")
            if kind == "auth": self.authorize(False, renew=True); h = {**h, **self.hdr()}; continue
            if kind == "forbidden": raise Fail(ERR, f"YouTube refused the upload (403 {reason}); app unverified or channel not allowed to upload")
            if kind != "retry": raise Fail(ERR, f"upload init failed: HTTP {st} {reason}")
            self._backoff(attempt, f"init {st} {reason}")
        raise Fail(ERR, "upload init kept failing")

    def _backoff(self, n, why):
        d = min(2 ** n, 300) + random.uniform(0, 1); self.log(f"transient error ({why}); backing off {d:.0f}s"); self.sleep(d)

    def _query(self, loc, size):
        """-> (offset, finished_response|None). Asks YouTube how many bytes it has."""
        st, rh, b = self.http("PUT", loc, self.hdr({"content-length": "0", "content-range": f"bytes */{size}"}), b"", 60)
        if st in (200, 201): return size, jbody(b)
        if st == 308: return parse_range_end(rh), None
        if st in (404, 410): raise SessionGone(ERR, "upload session gone")
        kind, reason = google_error(st, b)
        if kind == "auth": self.authorize(False, renew=True); return self._query(loc, size)
        raise NetError(f"query {st} {reason}")

    def upload(self, video, body, size, thumbnail):
        os.makedirs(self.session_dir, exist_ok=True); sp = session_path(self.session_dir, video, self.org, self.chan, size)
        sess = self._sess_load(sp, size); offset, res = 0, None
        if sess:
            loc = sess["location"]; self.log("resuming saved upload session")
            try: offset, res = self._query(loc, size)
            except SessionGone: sess = None
            except NetError: offset = 0                      # the loop below retries and re-queries
        if not sess:
            loc = self._init(size, body); offset = 0
            _save_json(sp, {"location": loc, "size": size, "created": time.time(), "channel_id": self.tok.get("channel_id"), "job": self.job})
        fails = 0
        while res is None:
            try:
                if offset >= size: raise Fail(ERR, "YouTube reports all bytes received but returned no video")
                with open(video, "rb") as f:
                    f.seek(offset); data = f.read(min(self.chunk, size - offset))
                end = offset + len(data) - 1
                st, rh, b = self.http("PUT", loc, self.hdr({"content-type": "video/mp4", "content-range": f"bytes {offset}-{end}/{size}", "content-length": str(len(data))}), data, 600)
                if st in (200, 201): res = jbody(b); break
                if st == 308:
                    new = parse_range_end(rh); fails = 0 if new > offset else fails; offset = new; self.log(f"uploaded {offset * 100 // size}%"); continue
                kind, reason = google_error(st, b)
                if kind == "quota": raise Fail(QUOTA, f"YouTube quota/upload limit reached ({reason})")
                if kind == "auth": self.authorize(thumbnail, renew=True); continue
                if kind != "retry": raise Fail(ERR, f"upload failed: HTTP {st} {reason}")
                raise NetError(f"{st} {reason}")
            except NetError as e:
                fails += 1
                if fails > self.max_failures: raise Fail(ERR, f"upload interrupted too often ({e}); rerun to resume")
                self._backoff(fails, str(e))
                try: offset, res = self._query(loc, size)
                except NetError: pass                        # keep the old offset, the next PUT will fail or succeed on its own
                except SessionGone:
                    if os.path.exists(sp): os.remove(sp)
                    raise Fail(ERR, "upload session expired; rerun to start a new upload")
        try: os.remove(sp)
        except OSError: pass
        if not res or "id" not in res: raise Fail(ERR, "upload finished without a video id: " + json.dumps(res)[:200])
        return res

    def set_thumbnail(self, video_id, thumb):
        try:
            size = os.path.getsize(thumb)
            if size > 2 * 1024 * 1024: self.log(f"thumbnail skipped: {size} bytes > 2 MB limit"); return False
            ctype = "image/png" if thumb.lower().endswith(".png") else "image/jpeg"
            with open(thumb, "rb") as f: img = f.read()
            for attempt in range(1, 4):
                st, _, b = self.http("POST", THUMB_URL + urllib.parse.quote(video_id), self.hdr({"content-type": ctype}), img, 120)
                if st == 200: return True
                kind, reason = google_error(st, b)
                if kind == "retry": self._backoff(attempt, f"thumbnail {st}"); continue
                if kind == "auth": self.authorize(True, renew=True); continue
                self.log(f"thumbnail not set (HTTP {st} {reason}); the video itself is uploaded"); return False   # forbidden = channel not verified for custom thumbnails; quota; both non-fatal
        except (NetError, OSError) as e: self.log(f"thumbnail error ignored: {e}")
        return False


def parse_args(argv):
    pos, opt, i = [], {}, 0
    while i < len(argv):
        a = argv[i]
        if a.startswith("--"):
            if i + 1 >= len(argv): raise Fail(USAGE, f"{a} needs a value")
            opt[a[2:]] = argv[i + 1]; i += 2
        else: pos.append(a); i += 1
    if len(pos) < 2 or "org" not in opt or "job" not in opt: raise Fail(USAGE, __doc__.split("\n")[1])
    return pos, opt


def main(argv=None, env=None, http=urllib_http, sleep=time.sleep, hold_path=HOLD_FILE, log=print):
    env = os.environ if env is None else env
    try:
        pos, opt = parse_args(sys.argv[1:] if argv is None else argv); video, meta_f = pos[0], pos[1]; thumb = pos[2] if len(pos) > 2 else None
        until = hold_active(hold_path)
        if until: log("UPLOAD_HOLD until", until.isoformat(), "- not uploading"); return HOLD
        base, key = env.get("STUDIO_URL", ""), env.get("STUDIO_WORKER_KEY", "")
        if not base or not key: raise Fail(USAGE, "STUDIO_URL and STUDIO_WORKER_KEY must be set")
        try: meta = _load_json(meta_f); size = os.path.getsize(video)
        except (OSError, ValueError) as e: raise Fail(BAD_INPUT, f"cannot read inputs: {e}")
        if not str(meta.get("title", "")).strip(): raise Fail(BAD_INPUT, "META.json needs a title")
        if size <= 0: raise Fail(BAD_INPUT, "video file is empty")
        org, chan, job = opt["org"], opt.get("channel"), opt["job"]
        sdir = env.get("YT_UPLOAD_SESSION_DIR") or None
        up = Uploader(Broker(base, key, http), http, org, chan, job, sleep=sleep, chunk=int(float(env.get("YT_CHUNK_MB", "8")) * 1024 * 1024), session_dir=sdir, log=log)
        has_thumb = bool(thumb and os.path.exists(thumb))
        # a saved session from an earlier crashed run already holds its reservation: do not reserve quota twice
        first = up.b.token(org, chan, job, thumbnail=has_thumb, renew=_has_saved_session(up, video, org, chan, size)); up.tok = first
        try:
            up.verify_channel(opt.get("expect-channel"))
            privacy, publish_at, notes = resolve_status(meta, first.get("policy") or {})
            for n in notes: log("note:", n)
            body = build_body(meta, privacy, publish_at)
            log(f"uploading {round(size / 1e6)} MB to channel {first.get('channel_title')!r} as {privacy}" + (f", publishing at {publish_at}" if publish_at else ""))
            res = up.upload(video, body, size, has_thumb)
        except Fail as e:
            if e.code == WRONG_CHANNEL: up.b.report(org, chan, job, "failed", units=first.get("reserved_units", 0))
            elif e.code == QUOTA: up.b.report(org, chan, job, "quota_exceeded", units=first.get("reserved_units", 0))
            raise
        vid = res["id"]; log("VIDEO_ID", vid, "| status:", (res.get("status") or {}).get("uploadStatus"), (res.get("status") or {}).get("privacyStatus"))
        if has_thumb: log("thumbnail:", "set" if up.set_thumbnail(vid, thumb) else "not set")
        up.b.report(org, chan, job, "uploaded", video_id=vid, privacy=privacy, publish_at=publish_at)
        log("https://youtu.be/" + vid); return OK
    except Fail as e:
        log("ERROR:", e); return e.code


def _has_saved_session(up, video, org, chan, size):
    try:
        p = session_path(up.session_dir, video, org, chan, size)
        return os.path.exists(p) and time.time() - _load_json(p).get("created", 0) < SESSION_MAX_AGE_S
    except Exception: return False


if __name__ == "__main__":
    sys.exit(main())

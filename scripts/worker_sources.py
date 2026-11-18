#!/usr/bin/env python3
"""SOURCES for the render worker: turns job.source into ONE local media file the pipeline can cut from.

job.source = {"type": "vod"|"live"|"url"|"auto", "ref": "...", ...}      (shape defined by app/studio.js)
ref forms that are understood (a customer controls this text, so everything is validated):
  https://host/path            direct media link or any page yt-dlp can read (YouTube, Twitch VOD, Drive/Dropbox direct links ...)
  upload:<name>                a file the customer uploaded; lives in $UPLOAD_DIR/<name> (flat directory, no sub paths)
  ingest:<name>[#t=FROM-TO]    the recording of a restream: $INGEST_DIR/<name>/ holds segment files (MediaMTX / nginx-rtmp recipe in docs/INGEST.md);
                               #t=FROM-TO (seconds of the concatenated recording) cuts a window = "live clipping every N minutes"
  /abs/path.mp4, file:///...   a local file; ONLY inside $WORKER_MEDIA_ROOTS (default: UPLOAD_DIR, INGEST_DIR) unless allow_any_path (demo / owner PC)
type "auto" (the assistant's "my last stream") resolves to the newest finished recording in $INGEST_DIR/<channel slug or id>.

Safety: no path traversal, no symlink escape, no private/loopback addresses (SSRF), no non-http(s) schemes, kick.com is not downloaded for customers (Kick ToS 1.4 forbids
automated access; use restream or upload), size and duration caps. Nothing here talks to YouTube. No network is needed for local sources."""
import ipaddress, json, os, re, shutil, socket, subprocess, urllib.parse

MEDIA_EXT = (".mp4", ".mkv", ".mov", ".webm", ".ts", ".flv", ".m4v", ".mp3", ".m4a", ".wav", ".aac")
SEGMENT_EXT = (".ts", ".mp4", ".mkv", ".flv", ".m4s", ".fmp4")
BLOCKED_HOSTS_DEFAULT = ("kick.com",)


class SourceError(Exception):
    """a problem the customer can understand; .code is a short machine-readable reason"""
    def __init__(self, code, msg=""): super().__init__(msg or code); self.code = code


def sh(cmd, timeout=None, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, **kw)


def probe(path, timeout=60):
    """-> {"duration_s", "has_video", "has_audio", "width", "height"}; raises SourceError('unreadable_media') when ffprobe cannot read it"""
    try:
        r = sh(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height", "-of", "json", path], timeout=timeout)
        j = json.loads(r.stdout or "{}")
    except Exception as e:
        raise SourceError("unreadable_media", "ffprobe failed: %s" % str(e)[:100])
    st = j.get("streams") or []
    try: dur = float((j.get("format") or {}).get("duration") or 0)
    except Exception: dur = 0.0
    v = [s for s in st if s.get("codec_type") == "video"]
    if r.returncode or dur <= 0 or not st: raise SourceError("unreadable_media", "not a readable media file")
    return {"duration_s": dur, "has_video": bool(v), "has_audio": any(s.get("codec_type") == "audio" for s in st), "width": (v[0].get("width") if v else 0), "height": (v[0].get("height") if v else 0)}


def parse_ref(ref):
    """'ingest:chan#t=600-1200' -> ('ingest', 'chan', (600.0, 1200.0)). Other schemes: ('url', ref, None), ('upload', name, None), ('file', path, None)."""
    ref = (ref or "").strip()
    if not ref: raise SourceError("no_source", "the job has no source reference")
    win = None
    m = re.search(r"#t=(\d+(?:\.\d+)?)?-(\d+(?:\.\d+)?)?$", ref)
    if m:
        a = float(m.group(1)) if m.group(1) else 0.0; b = float(m.group(2)) if m.group(2) else None
        if b is not None and b <= a: raise SourceError("bad_window", "window end before start")
        win = (a, b); ref = ref[:m.start()]
    if ref.startswith("ingest:"): return "ingest", ref[7:], win
    if ref.startswith("upload:"): return "upload", ref[7:], win
    if ref.startswith("file://"): return "file", urllib.parse.unquote(urllib.parse.urlparse(ref).path), win
    if re.match(r"^https?://", ref, re.I): return "url", ref, win
    if ref.startswith("/") or re.match(r"^[A-Za-z]:[\\/]", ref): return "file", ref, win
    raise SourceError("bad_source", "unsupported source reference")


def safe_name(name):
    """one flat path component: letters, digits, dot, dash, underscore, no leading dot"""
    if not name or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", name) or ".." in name: raise SourceError("bad_source", "invalid name")
    return name


def inside(path, roots):
    """True when realpath(path) is inside one of the roots (symlinks resolved, so a link cannot escape)"""
    p = os.path.realpath(path)
    for r in roots:
        rr = os.path.realpath(r)
        if p == rr or p.startswith(rr.rstrip(os.sep) + os.sep): return True
    return False


def check_url(url, blocked_hosts=BLOCKED_HOSTS_DEFAULT, resolver=None, trusted=False):
    """validate a customer-supplied URL (scheme, host policy, SSRF). resolver(host)->[ip] is injectable for tests. Returns the host."""
    u = urllib.parse.urlparse(url)
    if u.scheme.lower() not in ("http", "https"): raise SourceError("bad_url", "only http(s) links")
    host = (u.hostname or "").lower().rstrip(".")
    if not host or u.username or u.password: raise SourceError("bad_url", "bad link")
    if not trusted:
        for b in blocked_hosts:
            b = b.strip().lower()
            if b and (host == b or host.endswith("." + b)): raise SourceError("host_not_allowed", "%s cannot be downloaded: restream to our ingest or upload the file instead" % b)
    try:
        ips = resolver(host) if resolver else [a[4][0] for a in socket.getaddrinfo(host, None)]
    except Exception:
        raise SourceError("bad_url", "host does not resolve")
    for ip in ips:
        try: a = ipaddress.ip_address(ip.split("%")[0])
        except ValueError: raise SourceError("bad_url", "bad address")
        if a.is_private or a.is_loopback or a.is_link_local or a.is_reserved or a.is_multicast or a.is_unspecified: raise SourceError("bad_url", "address not allowed")
    return host


def list_segments(d):
    """segment files of a recording directory, oldest first by name (the recorders write sortable timestamps); in-progress / tiny files are kept out by the caller"""
    try: names = sorted(n for n in os.listdir(d) if n.lower().endswith(SEGMENT_EXT) and not n.startswith("."))
    except FileNotFoundError: raise SourceError("no_recording", "no recording found for this stream")
    return [os.path.join(d, n) for n in names if os.path.isfile(os.path.join(d, n)) and os.path.getsize(os.path.join(d, n)) > 0]


def newest_recording(root, name_hints):
    """for type 'auto': the newest recording directory under root/<hint>/ (a hint is a channel slug or id). Returns ('hint/sub' ref name) or None."""
    best = None
    for h in name_hints:
        if not h: continue
        try: h = safe_name(h)
        except SourceError: continue
        d = os.path.join(root, h)
        if not os.path.isdir(d): continue
        if list_segments(d): best = max(best, (os.path.getmtime(d), h)) if best else (os.path.getmtime(d), h)
    return best[1] if best else None


def concat_segments(segs, out, window=None, timeout=3600):
    """join segments (stream copy, no re-encode) into one mp4; window=(from_s, to_s|None) trims it. Raises SourceError on failure."""
    lst = out + ".list.txt"
    with open(lst, "w") as f:
        for s in segs: f.write("file '%s'\n" % s.replace("'", "'\\''"))
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst]
    if window: cmd += (["-ss", "%.2f" % window[0]] if window[0] else []) + (["-t", "%.2f" % (window[1] - window[0])] if window[1] else [])
    cmd += ["-c", "copy", "-movflags", "+faststart", out]
    try: r = sh(cmd, timeout=timeout)
    except subprocess.TimeoutExpired: raise SourceError("timeout", "joining the recording took too long")
    finally:
        try: os.remove(lst)
        except OSError: pass
    if r.returncode or not os.path.exists(out): raise SourceError("unreadable_media", "could not join the recording: " + (r.stderr or "")[-200:])
    return out


def download_url(url, workdir, timeout=3600, max_gb=12, runner=sh, height=1080, end_s=0):
    """yt-dlp into workdir/src.<ext>. Playlists are refused (one video per job). end_s > 0 downloads only the first end_s seconds (preview phase: a 6 h VOD does not fit a GitHub runner). Returns the file path."""
    out_t = os.path.join(workdir, "dl.%(ext)s")
    cmd = ["yt-dlp", "--no-playlist", "--no-warnings", "--newline", "--max-filesize", "%dG" % max_gb, "--socket-timeout", "30", "--retries", "3",
           "-f", "bv*[height<=%d]+ba/b[height<=%d]/b" % (height, height), "--merge-output-format", "mp4"] + (["--download-sections", "*0-%d" % int(end_s)] if end_s and end_s > 0 else []) + ["-o", out_t, "--", url]
    try: r = runner(cmd, timeout=timeout)
    except subprocess.TimeoutExpired: raise SourceError("timeout", "download took too long")
    except FileNotFoundError: raise SourceError("tool_missing", "yt-dlp is not installed")
    got = sorted(n for n in os.listdir(workdir) if n.startswith("dl.") and not n.endswith((".part", ".ytdl")))
    if r.returncode or not got: raise SourceError("download_failed", ((r.stderr or "") + (r.stdout or ""))[-300:].replace("\n", " "))
    return os.path.join(workdir, got[0])


PLATFORM_SLUG_RX = re.compile(r"^[a-z0-9][a-z0-9_-]{1,24}$")


def latest_platform_vod(platform, slug, runner=sh, min_s=300):
    """PREVIEW PHASE, owner's trusted org only (cfg trusted + platform_vod): the newest VOD of a verified channel -> (url, title).
    Twitch: yt-dlp lists the archives without an API key. Kick: the (undocumented, ToS 1.4 restricted) channel videos API, the same call the owner's own loops make. Raises SourceError('no_recording')."""
    platform = (platform or "").lower(); slug = (slug or "").lower()
    if platform not in ("kick", "twitch") or not PLATFORM_SLUG_RX.match(slug): raise SourceError("no_recording", "no channel to look up")
    if platform == "twitch":
        r = runner(["yt-dlp", "--flat-playlist", "--playlist-end", "8", "--print", "%(id)s|%(duration)s|%(title)s", "https://www.twitch.tv/%s/videos?filter=archives&sort=time" % slug], timeout=120)
        for line in (r.stdout or "").splitlines():
            p = line.split("|", 2)
            if len(p) < 3: continue
            try: dur = float(p[1])
            except ValueError: dur = 0.0
            vid = p[0].lstrip("v")
            if re.fullmatch(r"\d{5,15}", vid) and dur >= min_s: return "https://www.twitch.tv/videos/" + vid, p[2][:80]
        raise SourceError("no_recording", "no recent Twitch VOD found")
    r = runner(["curl", "-sS", "-m", "40", "-A", "Mozilla/5.0", "https://kick.com/api/v2/channels/%s/videos" % slug], timeout=60)
    try: vids = json.loads(r.stdout or "[]")
    except Exception: vids = []
    for v in vids if isinstance(vids, list) else []:
        try: dur = float(v.get("duration") or 0) / 1000.0
        except (TypeError, ValueError): dur = 0.0
        src = v.get("source") or ""
        if dur >= min_s and isinstance(src, str) and src.startswith("https://"): return src, str(v.get("session_title") or "")[:80]
    raise SourceError("no_recording", "no recent Kick VOD found")


def resolve_source(job, workdir, cfg=None, runner=sh, resolver=None):
    """job -> {"path", "kind", "duration_s", "title", "window"}; file is inside workdir (or a read-only local original) and probed.
    cfg keys: upload_dir, ingest_dir, media_roots[list], allow_any_path, blocked_hosts, trusted (owner org may bypass host blocklist), max_source_h, min_source_s, download_timeout."""
    cfg = cfg or {}; src = job.get("source") or {}; typ = src.get("type"); ref = src.get("ref") or ""
    upload_dir, ingest_dir = cfg.get("upload_dir") or "", cfg.get("ingest_dir") or ""
    roots = [r for r in (cfg.get("media_roots") or [upload_dir, ingest_dir]) if r]
    os.makedirs(workdir, exist_ok=True)
    if typ == "auto" and not ref:
        hints = [job.get("channel"), (job.get("hints") or {}).get("slug"), src.get("slug")]
        name = newest_recording(ingest_dir, hints) if ingest_dir else None
        ci = job.get("channel_info") or {}
        if name: ref = "ingest:" + name
        elif cfg.get("platform_vod") and cfg.get("trusted") and ci.get("platform"): ref, title0 = latest_platform_vod(ci.get("platform"), ci.get("slug"), runner)   # owner's own test org only
        else: raise SourceError("no_recording", "no finished stream recording found yet")
    kind, val, win = parse_ref(ref); title = ""
    if kind == "ingest":
        if not ingest_dir: raise SourceError("ingest_off", "ingest is not configured on this worker")
        d = os.path.join(ingest_dir, safe_name(val))
        if not inside(d, [ingest_dir]): raise SourceError("bad_source", "path escapes the ingest directory")
        segs = [s for s in list_segments(d) if inside(s, [ingest_dir])]
        if not segs: raise SourceError("no_recording", "recording directory is empty")
        path = concat_segments(segs, os.path.join(workdir, "source.mp4"), win, timeout=cfg.get("download_timeout", 3600)); title = val
    elif kind == "upload":
        if not upload_dir: raise SourceError("upload_off", "uploads are not configured on this worker")
        p = os.path.join(upload_dir, safe_name(val))
        if not os.path.isfile(p) or not inside(p, [upload_dir]): raise SourceError("no_file", "uploaded file not found")
        path, title = _window(p, win, workdir, cfg), val
    elif kind == "file":
        p = os.path.abspath(val)
        if not cfg.get("allow_any_path") and not inside(p, roots): raise SourceError("path_not_allowed", "local path is outside the allowed media directories")
        if not os.path.isfile(p): raise SourceError("no_file", "file not found")
        path, title = _window(p, win, workdir, cfg), os.path.basename(p)
    else:
        check_url(val, cfg.get("blocked_hosts", BLOCKED_HOSTS_DEFAULT), resolver, trusted=bool(cfg.get("trusted")))
        cap = float(cfg.get("download_max_min") or 0) * 60; end_s = (win[1] if win and win[1] else cap) if cap else 0   # preview phase: only the first N minutes (or up to the requested window end)
        path = _window(download_url(val, workdir, cfg.get("download_timeout", 3600), runner=runner, height=int(cfg.get("download_height") or 1080), end_s=end_s), win, workdir, cfg); title = urllib.parse.urlparse(val).hostname or ""
    info = probe(path)
    if not info["has_audio"]: raise SourceError("no_audio", "the source has no audio track, nothing to transcribe")
    if info["duration_s"] < cfg.get("min_source_s", 30): raise SourceError("too_short", "source is shorter than %ds" % cfg.get("min_source_s", 30))
    mx = float(cfg.get("max_source_h", 8)) * 3600
    if info["duration_s"] > mx: raise SourceError("too_long", "source is longer than %.0f h" % (mx / 3600))
    return {"path": path, "kind": kind, "duration_s": info["duration_s"], "has_video": info["has_video"], "title": title, "window": win, "width": info["width"], "height": info["height"]}


def _window(path, win, workdir, cfg):
    """apply a #t= window to a single file (stream copy into workdir); no window -> the original file, read-only"""
    if not win: return path
    out = os.path.join(workdir, "source.mp4")
    cmd = ["ffmpeg", "-v", "error", "-y"] + (["-ss", "%.2f" % win[0]] if win[0] else []) + ["-i", path] + (["-t", "%.2f" % (win[1] - win[0])] if win[1] else []) + ["-c", "copy", "-movflags", "+faststart", out]
    r = sh(cmd, timeout=cfg.get("download_timeout", 3600))
    if r.returncode or not os.path.exists(out): raise SourceError("unreadable_media", "could not cut the window: " + (r.stderr or "")[-200:])
    return out


def free_gb(path):
    try: return shutil.disk_usage(path).free / 1e9
    except Exception: return 1e9

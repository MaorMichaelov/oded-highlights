#!/usr/bin/env python3
"""PREVIEW DELIVERY for the studio preview phase (zero cost): small 720p renditions of finished drafts become playable in the browser.

How: each finished job gets ONE GitHub release (tag studio-preview-<job>-<random>) in the repository the workflow runs in; every draft is a release asset
(.mp4, 720p, <= ~1.1 Mbit/s video, 64 kbit/s audio, long videos cut to STUDIO_PREVIEW_MAX_S). The URL https://github.com/<repo>/releases/download/<tag>/<file>.mp4 is
stored as draft.preview_url in the studio (POST /studio/worker/jobs/:id, validated server side). Nothing here needs a secret of its own: it uses the GITHUB_TOKEN
the workflow run is given automatically (permission contents: write for that one job), passed in env GITHUB_TOKEN.
Limits (also in docs/STUDIO_PREVIEW_SETUP.md): the repository is public, so the preview URLs are PUBLIC (unguessable, but not private) -> only for the owner's own test
org (WORKER_PREVIEW_ORGS), deleted after STUDIO_PREVIEW_DAYS (default 7) by `--cleanup`; GitHub caps a release asset at 2 GB (we are far below); the full-quality 1080x1920
draft is NOT published (it stays on the runner and is deleted with it): approving a draft in preview mode does not upload anything to YouTube.

CLI:  preview_publish.py --cleanup [--days 7]     delete old studio-preview-* releases and their tags (needs GITHUB_TOKEN, GITHUB_REPOSITORY)
      preview_publish.py --selftest FILE.mp4      make the preview rendition of one file and print its size (no network)
Never uploads to YouTube. Never prints the token."""
import argparse, json, os, re, secrets, subprocess, sys, time, urllib.error, urllib.request

TAG_PREFIX = "studio-preview-"
SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]")


def preview_args(src, dst, max_s=300, height=720, vbit="900k"):
    """ffmpeg command for the small rendition: 720 on the short side (portrait Shorts become 720x1280, landscape 1280x720), capped bitrate, faststart (plays while loading)"""
    vf = "scale='if(gt(iw,ih),-2,%d)':'if(gt(iw,ih),%d,-2)'" % (height, height)
    return (["ffmpeg", "-v", "error", "-y", "-i", src] + (["-t", str(int(max_s))] if max_s and max_s > 0 else []) +
            ["-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "30", "-maxrate", vbit, "-bufsize", "1800k", "-pix_fmt", "yuv420p", "-r", "30",
             "-c:a", "aac", "-b:a", "64k", "-ac", "2", "-movflags", "+faststart", dst])


def make_preview(src, dst, max_s=300, run=subprocess.run):
    r = run(preview_args(src, dst, max_s), capture_output=True, text=True, timeout=1800)
    if r.returncode or not os.path.exists(dst) or os.path.getsize(dst) == 0: raise RuntimeError("preview encode failed: " + (r.stderr or "")[-160:])
    return dst


def urllib_http(method, url, headers, data, timeout=300):
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r: return r.status, r.read()
    except urllib.error.HTTPError as e: return e.code, e.read()


class GithubReleasePublisher:
    """publisher(job, drafts, dest_dir) -> {draft file name: preview url}. http(method, url, headers, data)->(status, bytes) and encode(src, dst) are injectable (tests)."""
    def __init__(self, repo, token, http=None, encode=None, max_s=300, orgs=(), log=None):
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,60}/[A-Za-z0-9_.-]{1,100}", repo or ""): raise ValueError("bad GITHUB_REPOSITORY")
        self.repo, self.token, self.http, self.max_s, self.orgs, self.log = repo, token, http or urllib_http, max_s, set(orgs), log or (lambda *a, **k: None)
        self.encode = encode or (lambda src, dst: make_preview(src, dst, self.max_s))
    def _h(self, extra=None):
        h = {"authorization": "Bearer " + self.token, "accept": "application/vnd.github+json", "x-github-api-version": "2022-11-28", "user-agent": "studio-preview/1"}; h.update(extra or {}); return h
    def _api(self, method, path, body=None, base="https://api.github.com"):
        st, raw = self.http(method, base + path, self._h({"content-type": "application/json"} if body is not None else None), json.dumps(body).encode() if body is not None else None)
        try: j = json.loads(raw or b"{}")
        except Exception: j = {}
        return st, j
    def allowed(self, org): return "*" in self.orgs or (bool(org) and str(org) in self.orgs)
    def __call__(self, job, drafts, dest):
        if not self.allowed(job.get("org")): self.log("preview_skipped", reason="org_not_in_WORKER_PREVIEW_ORGS"); return {}
        jid = re.sub(r"[^A-Za-z0-9_-]", "", str(job.get("id")))[:40]; tag = "%s%s-%s" % (TAG_PREFIX, jid, secrets.token_hex(4))
        st, rel = self._api("POST", "/repos/%s/releases" % self.repo, {"tag_name": tag, "name": "preview " + jid, "body": "Temporary preview renditions (deleted after a few days). Studio preview phase.", "prerelease": True, "make_latest": "false"})
        if st not in (200, 201) or not rel.get("id"): raise RuntimeError("release create failed: HTTP %s" % st)
        out = {}; upload = (rel.get("upload_url") or "").split("{")[0] or "https://uploads.github.com/repos/%s/releases/%s/assets" % (self.repo, rel["id"])
        if not upload.startswith("https://uploads.github.com/"): raise RuntimeError("unexpected upload url")
        for d in drafts:
            name = SAFE_NAME.sub("_", os.path.basename(d["file"]))
            if not name.lower().endswith(".mp4"): name += ".mp4"
            small = os.path.join(dest, ".preview_" + name)
            try:
                self.encode(os.path.join(dest, os.path.basename(d["file"])), small)
                with open(small, "rb") as f: data = f.read()
                st, _ = self.http("POST", "%s?name=%s" % (upload, urllib.request.quote(name)), self._h({"content-type": "video/mp4", "content-length": str(len(data))}), data)
                if st not in (200, 201): raise RuntimeError("asset upload failed: HTTP %s" % st)
                out[os.path.basename(d["file"])] = "https://github.com/%s/releases/download/%s/%s" % (self.repo, tag, name)
                self.log("preview_uploaded", file=name, kb=len(data) // 1024)
            except Exception as e: self.log("preview_failed", level="warn", file=name, error=str(e)[:150])
            finally:
                try: os.remove(small)
                except OSError: pass
        if not out: self._api("DELETE", "/repos/%s/releases/%s" % (self.repo, rel["id"])); self._api("DELETE", "/repos/%s/git/refs/tags/%s" % (self.repo, tag))   # nothing uploaded: do not leave an empty release behind
        return out


def cleanup(repo, token, days=7, http=None, now=None):
    """delete studio-preview-* releases older than `days` and their tags; returns the number removed. Other releases/tags are never touched."""
    p = GithubReleasePublisher(repo, token, http=http); now = now or time.time(); removed = 0
    st, rels = p._api("GET", "/repos/%s/releases?per_page=100" % repo)
    if st != 200 or not isinstance(rels, list): raise RuntimeError("cannot list releases: HTTP %s" % st)
    for r in rels:
        tag = r.get("tag_name") or ""
        if not tag.startswith(TAG_PREFIX) or not re.fullmatch(r"[A-Za-z0-9._-]+", tag): continue
        try: age = now - time.mktime(time.strptime(r["created_at"], "%Y-%m-%dT%H:%M:%SZ")) + time.timezone
        except Exception: continue
        if age < days * 86400: continue
        s1, _ = p._api("DELETE", "/repos/%s/releases/%s" % (repo, r["id"])); p._api("DELETE", "/repos/%s/git/refs/tags/%s" % (repo, tag))
        if s1 in (200, 204): removed += 1
    return removed


def from_env(env=None, log=None):
    """build the publisher from the environment, or None (preview delivery off). STUDIO_PREVIEW_PUBLISH=github-release switches it on."""
    e = os.environ if env is None else env
    if (e.get("STUDIO_PREVIEW_PUBLISH") or "").strip().lower() != "github-release": return None
    tok, repo = e.get("GITHUB_TOKEN", ""), e.get("GITHUB_REPOSITORY", "")
    orgs = [x.strip() for x in (e.get("WORKER_PREVIEW_ORGS") or e.get("WORKER_TRUSTED_ORGS") or "").split(",") if x.strip()]
    if not tok or not repo or not orgs: return None
    return GithubReleasePublisher(repo, tok, max_s=int(float(e.get("STUDIO_PREVIEW_MAX_S", "300") or 300)), orgs=orgs, log=log)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0]); ap.add_argument("--cleanup", action="store_true"); ap.add_argument("--days", type=float, default=float(os.environ.get("STUDIO_PREVIEW_DAYS", "7") or 7)); ap.add_argument("--selftest"); a = ap.parse_args(argv)
    if a.selftest:
        out = a.selftest + ".preview.mp4"; make_preview(a.selftest, out); print("preview %s: %d KB" % (out, os.path.getsize(out) // 1024)); return 0
    if a.cleanup:
        tok, repo = os.environ.get("GITHUB_TOKEN", ""), os.environ.get("GITHUB_REPOSITORY", "")
        if not tok or not repo: print("GITHUB_TOKEN and GITHUB_REPOSITORY are required", file=sys.stderr); return 2
        print("removed %d old preview release(s)" % cleanup(repo, tok, a.days)); return 0
    ap.print_help(); return 2


if __name__ == "__main__": sys.exit(main())

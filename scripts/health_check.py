#!/usr/bin/env python3
"""HEALTH CHECK: is the whole machine alive, and if not, what exactly is wrong? Writes state/health.json (merged with what station 6 / monitor.py writes) and exits 1 on a critical problem.

Checks (each -> {"status": "ok"|"warn"|"critical"|"info", "detail": "..."}):
  live_loop        a live-loop run is in progress/queued (or state/PAUSE exists)          critical when it is dead and not paused
  channel_loops    live-loop-channel / live-shorts runs for the enabled streamers          warn
  state_fresh      state/live_status.json is younger than 20 min                          critical when the loop runs but state is stale (stuck loop), warn otherwise
  transcription    ingest lag (_behind_segs) and a Kick API error                         warn
  last_upload      age of the newest private draft (state/index.json draft_at)            warn when nothing was uploaded for 36 h while clips were picked
  upload_hold      state/UPLOAD_HOLD in the future / clips waiting for the YouTube quota   info / warn
  failed_runs      failed render-clip / live-loop runs in the last 3 h                    warn at 2, critical at 5
  cancelled_runs   workflows cancelling each other (cancelled runs of the same loop)      warn
  queue_stall      runs queued for more than 60 min (runner shortage / concurrency lock)  warn
  stuck_clips      a clip spec older than 90 min with no draft and no upload log          warn
  state_integrity  *.corrupt-* files (a truncated state file was quarantined) and unreadable core state   critical
  duplicates       two drafts with the same title, or overlapping ranges of one VOD in the dedup ledger   warn
Usage:  health_check.py [--no-gh] [--no-write] [--issue]     (needs GH_TOKEN + the gh CLI for the run checks; --no-gh skips them)
No secrets are read or printed. All logic lives in evaluate(ctx) (pure, unit-tested in tests/test_health_check.py); collect() gathers the context from disk and from `gh api`.
"""
import argparse, datetime as dt, glob, json, os, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, HERE)
import statefile as SF
REPO = os.environ.get("GITHUB_REPOSITORY", "MaorMichaelov/oded-highlights")
RANK = {"ok": 0, "info": 0, "warn": 1, "critical": 2}


def parse_t(s):
    try: return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception: return None


def age_min(s, now):
    t = parse_t(s)
    if t is None: return None
    if t.tzinfo is None: t = t.replace(tzinfo=dt.timezone.utc)
    return (now - t).total_seconds() / 60


def ck(status, detail, **kw): return {"status": status, "detail": detail, **kw}


def evaluate(ctx):
    """ctx keys: now(datetime), runs(list|None = gh unavailable), paused(bool), live_status, ingest, index(list), hold(str|None), clips(list of dicts: id, draft_state, draft_url, spec_age_min, has_upload_log),
    channels(list of channel dicts), corrupt(list of paths), unreadable(list), ledger(list), events_last(str|None)"""
    now = ctx["now"]; runs = ctx.get("runs"); C = {}
    def runs_of(name): return [r for r in (runs or []) if r.get("workflowName") == name or r.get("name") == name]
    active = lambda rs: [r for r in rs if r.get("status") in ("in_progress", "queued", "waiting", "pending", "requested")]
    ls = ctx.get("live_status") or {}; fresh = age_min(ls.get("checked_at"), now) if ls.get("checked_at") else None
    # live loop
    if runs is None: C["live_loop"] = ck("info", "run list unavailable (no gh / no token)")
    elif ctx.get("paused"): C["live_loop"] = ck("info", "paused (state/PAUSE exists)")
    elif active(runs_of("live-loop")): C["live_loop"] = ck("ok", f"{len(active(runs_of('live-loop')))} run(s) active")
    else: C["live_loop"] = ck("critical", "live-loop is NOT running (monitor / the Cloudflare watchdog should restart it; start it by hand: gh workflow run live-loop.yml)")
    # other streamers
    if runs is not None:
        want = [c for c in ctx.get("channels", []) if c.get("enabled") and c.get("slug") != "odedsvr"]
        have = len(active(runs_of("live-loop-channel"))) + len(active(runs_of("live-shorts")))
        C["channel_loops"] = ck("warn", f"{len(want)} streamer(s) enabled but only {have} channel loop run(s) active: {[c['slug'] for c in want]}") if want and have < len(want) else ck("ok", f"{have} channel loop run(s) active, {len(want)} enabled streamer(s)")
    # freshness (the loop writes live_status.json every ~5 min, every 45 s while live)
    if fresh is None: C["state_fresh"] = ck("warn", "state/live_status.json missing or has no checked_at")
    elif fresh > 20: C["state_fresh"] = ck("critical" if (runs and active(runs_of("live-loop"))) else "warn", f"live_status is {fresh:.0f} min old" + (" while a loop run is active: the loop is stuck (a step hangs or git push keeps failing)" if runs and active(runs_of("live-loop")) else ""), age_min=round(fresh, 1))
    else: C["state_fresh"] = ck("ok", f"live_status {fresh:.1f} min old", age_min=round(fresh, 1))
    # transcription
    ing = ctx.get("ingest") or {}; behind = ing.get("_behind_segs") or 0; probs = []
    if behind > 60 and ls.get("live"): probs.append(f"transcription is {behind} segments (~{behind // 6} min) behind the live edge")
    if ls.get("http") not in (None, "200", 200) or (ls and ls.get("live") is None): probs.append(f"Kick API problem http={ls.get('http')} note={ls.get('note')}")
    C["transcription"] = ck("warn", "; ".join(probs)) if probs else ck("ok", f"lag {behind} segments, live={ls.get('live')}")
    # uploads
    idx = ctx.get("index") or []; ups = [c for c in idx if c.get("draft") and c.get("draft_at")]
    last = max((c["draft_at"] for c in ups), default=None); la = age_min(last, now) if last else None
    recent_picks = [c for c in idx if not str(c.get("id", "")).startswith("test") and not c.get("draft") and not c.get("quality_errors")]
    if la is None: C["last_upload"] = ck("info", "no draft recorded yet")
    elif la > 36 * 60 and recent_picks: C["last_upload"] = ck("warn", f"last draft {la / 60:.0f} h ago and {len(recent_picks)} clip(s) have no draft", age_h=round(la / 60, 1), last=last)
    else: C["last_upload"] = ck("ok", f"last draft {la / 60:.1f} h ago", age_h=round(la / 60, 1), last=last)
    hold = ctx.get("hold"); hu = parse_t(hold.strip()) if hold else None
    if hu is not None and hu.tzinfo is None: hu = hu.replace(tzinfo=dt.timezone.utc)
    qw = [c["id"] for c in ctx.get("clips", []) if c.get("draft_state") == "quota_wait"]
    if hu and hu > now: C["upload_hold"] = ck("info", f"UPLOAD_HOLD active until {hu.isoformat()}: nothing is uploaded (by owner request)", until=hu.isoformat())
    elif qw: C["upload_hold"] = ck("warn", f"{len(qw)} clip(s) wait for the YouTube upload quota (resets 08:00 UTC): {qw[:5]}")
    else: C["upload_hold"] = ck("ok", "no hold, no quota wait")
    # runs
    if runs is not None:
        rec = lambda r, h: (age_min(r.get("createdAt") or r.get("created_at"), now) or 1e9) < h * 60
        bad = [r for r in runs if r.get("conclusion") == "failure" and rec(r, 3) and r.get("workflowName", r.get("name")) in ("render-clip", "live-loop", "live-loop-channel", "live-shorts", "long-video", "vod-shorts")]
        C["failed_runs"] = ck("critical" if len(bad) >= 5 else "warn", f"{len(bad)} failed run(s) in 3 h: {sorted({r.get('workflowName', r.get('name')) for r in bad})}") if len(bad) >= 2 else ck("ok", f"{len(bad)} failed run(s) in 3 h")
        can = [r for r in runs if r.get("conclusion") == "cancelled" and rec(r, 2) and r.get("workflowName", r.get("name")) in ("live-loop", "live-loop-channel", "live-shorts")]
        C["cancelled_runs"] = ck("warn", f"{len(can)} loop run(s) cancelled in 2 h (concurrency group or manual cancels fighting each other?)") if len(can) >= 3 else ck("ok", f"{len(can)} cancelled loop run(s) in 2 h")
        q = [r for r in runs if r.get("status") in ("queued", "waiting", "pending") and (age_min(r.get("createdAt") or r.get("created_at"), now) or 0) > 60]
        C["queue_stall"] = ck("warn", f"{len(q)} run(s) queued for > 60 min: {sorted({r.get('workflowName', r.get('name')) for r in q})}") if q else ck("ok", "no stalled queue")
    # stuck clips
    stuck = [c["id"] for c in ctx.get("clips", []) if c.get("spec_age_min", 0) > 90 and not c.get("draft_url") and c.get("draft_state") != "quota_wait" and not c.get("has_upload_log") and not str(c["id"]).startswith("test")]
    C["stuck_clips"] = ck("warn", f"{len(stuck)} clip(s) without a draft after 90 min: {stuck[:5]}") if stuck else ck("ok", "no stuck clips")
    # integrity
    bad_state = list(ctx.get("corrupt", [])) + list(ctx.get("unreadable", []))
    C["state_integrity"] = ck("critical", f"corrupt/quarantined state files: {bad_state[:6]}") if bad_state else ck("ok", "core state files parse")
    # duplicates
    titles = {}
    for c in idx:
        if c.get("draft") and c.get("title") and not str(c.get("id", "")).startswith("test"): titles.setdefault(c["title"].strip(), []).append(c["id"])
    dup = {t: v for t, v in titles.items() if len(v) > 1}
    ov = []
    led = [r for r in ctx.get("ledger", []) if r.get("producer") != "backfill"]
    for i, a in enumerate(led):
        for b in led[i + 1:]:
            if a.get("vod") == b.get("vod") and a.get("kind") == b.get("kind") and (not a.get("yt") or not b.get("yt") or a["yt"] == b["yt"]):
                o = min(a["end"], b["end"]) - max(a["start"], b["start"])
                if o > 0.8 * max(1e-6, min(a["end"] - a["start"], b["end"] - b["start"])): ov.append((a.get("clip_id"), b.get("clip_id")))
    C["duplicates"] = ck("warn", f"duplicate draft titles: {list(dup.values())[:3]}; overlapping ledger entries: {ov[:3]}") if dup or ov else ck("ok", "no duplicate drafts")
    overall = max((v["status"] for v in C.values()), key=lambda s: RANK[s], default="ok")
    return {"overall": overall if overall != "info" else "ok", "checks": C, "hc_problems": [f"{k}: {v['detail']}" for k, v in C.items() if v["status"] in ("warn", "critical")]}


# ---------------------------------------------------------------- collection
def gh_runs(limit=100):
    try:
        r = subprocess.run(["gh", "run", "list", "--repo", REPO, "--limit", str(limit), "--json", "workflowName,status,conclusion,createdAt,databaseId"], capture_output=True, text=True, timeout=60)
        return json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else None
    except Exception as e:
        print("gh unavailable:", type(e).__name__); return None


def collect(use_gh=True, root=ROOT):
    st = os.path.join(root, "state"); now = dt.datetime.now(dt.timezone.utc)
    core = ["live_status.json", "ingest_state.json", "pick_state.json", "index.json", "retries.json"]; unreadable = []
    for f in core:
        p = os.path.join(st, f)
        if os.path.exists(p):
            try: json.load(open(p, encoding="utf-8"))
            except Exception: unreadable.append("state/" + f)
    corrupt = [os.path.relpath(p, root) for p in glob.glob(os.path.join(st, "**", "*.corrupt-*"), recursive=True)]
    clips = []
    for d in sorted(glob.glob(os.path.join(st, "**", "clips", "*", "spec.json"), recursive=True)):
        cd = os.path.dirname(d); s = SF.read_json(os.path.join(cd, "status.json"), {}, quarantine=False) or {}; dr = s.get("draft") or {}
        clips.append({"id": os.path.basename(cd), "draft_state": dr.get("state"), "draft_url": dr.get("url"), "spec_age_min": (time.time() - os.path.getmtime(d)) / 60, "has_upload_log": os.path.exists(os.path.join(cd, "upload.log"))})
    hold = None
    if os.path.exists(os.path.join(st, "UPLOAD_HOLD")): hold = open(os.path.join(st, "UPLOAD_HOLD")).read()
    try: channels = json.load(open(os.path.join(root, "config", "channels.json"))).get("channels", [])
    except Exception: channels = []
    return {"now": now, "runs": gh_runs() if use_gh else None, "paused": os.path.exists(os.path.join(st, "PAUSE")), "live_status": SF.read_json(os.path.join(st, "live_status.json"), {}, quarantine=False), "ingest": SF.read_json(os.path.join(st, "ingest_state.json"), {}, quarantine=False),
            "index": SF.read_json(os.path.join(st, "index.json"), [], quarantine=False) or [], "hold": hold, "clips": clips, "channels": channels, "corrupt": corrupt, "unreadable": unreadable, "ledger": SF.read_jsonl(os.path.join(st, "dedup.jsonl"))}


def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--no-gh", action="store_true"); ap.add_argument("--no-write", action="store_true"); ap.add_argument("--issue", action="store_true"); a = ap.parse_args(argv)
    res = evaluate(collect(use_gh=not a.no_gh)); res["hc_checked_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    for k, v in res["checks"].items(): print(f"{v['status']:8} {k}: {v['detail']}")
    print("OVERALL:", res["overall"])
    if not a.no_write:
        hp = os.path.join(ROOT, "state", "health.json"); cur = SF.read_json(hp, {}, quarantine=False) or {}; cur.update(res); SF.write_json(hp, cur)   # merge: monitor.py's keys (problems, stuck_clips, ...) stay
    if a.issue and res["overall"] == "critical" and os.environ.get("GH_TOKEN"):
        title = "Health check CRITICAL: " + res["hc_problems"][0][:70]
        have = subprocess.run(["gh", "issue", "list", "--repo", REPO, "--state", "open", "--json", "title", "--jq", ".[].title"], capture_output=True, text=True).stdout
        if title not in have: subprocess.run(["gh", "issue", "create", "--repo", REPO, "--title", title, "--body", "\n".join("- " + p for p in res["hc_problems"]) + "\n\nstate/health.json has the details."], capture_output=True, text=True)
    return 1 if res["overall"] == "critical" else 0


if __name__ == "__main__": sys.exit(main())

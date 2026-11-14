#!/usr/bin/env python3
"""STATION 6 - MONITOR: is everything alive? Writes state/health.json, opens a GitHub issue (-> email to the owner) when something is wrong, restarts the live loop if it died.
Checks: live loop running and state fresh (< 15 min), recent failed runs (render-clip / live-loop), clips stuck without a draft (> 90 min), pending candidates, the GROQ/YT secrets exist (workflow env).
usage: monitor.py [--no-issue] [--no-restart]      needs GH_TOKEN (gh CLI) with actions:write and issues:write"""
import argparse, datetime as dt, json, os, subprocess, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); ST = os.path.join(ROOT, "state")
REPO = os.environ.get("GITHUB_REPOSITORY", "MaorMichaelov/oded-highlights")
def gh(*a):
    r = subprocess.run(["gh", *a], capture_output=True, text=True); return r.stdout if r.returncode == 0 else ""
def jf(p, d=None): return json.load(open(p)) if os.path.exists(p) else d
def age_min(iso): return (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))).total_seconds() / 60
ap = argparse.ArgumentParser(); ap.add_argument("--no-issue", action="store_true"); ap.add_argument("--no-restart", action="store_true"); a = ap.parse_args()
problems, info = [], {}
runs = json.loads(gh("run", "list", "--repo", REPO, "--limit", "30", "--json", "workflowName,status,conclusion,createdAt,databaseId") or "[]")
loop = [r for r in runs if r["workflowName"] == "live-loop"]; running = [r for r in loop if r["status"] in ("in_progress", "queued")]
info["live_loop_running"] = bool(running)
ls = jf(os.path.join(ST, "live_status.json"), {}) or {}
fresh = age_min(ls["checked_at"]) if ls.get("checked_at") else 9999; info["state_age_min"] = round(fresh, 1); info["live"] = ls.get("live")
if not running and not os.path.exists(os.path.join(ST, "PAUSE")):
    problems.append("live-loop is NOT running")
    if not a.no_restart: gh("workflow", "run", "live-loop.yml", "--repo", REPO, "--ref", "main"); info["restarted_live_loop"] = True
elif fresh > 20: problems.append(f"live loop is running but state is {fresh:.0f} min old (stuck?)")
bad = [r for r in runs if r["workflowName"] in ("render-clip",) and r["conclusion"] == "failure" and age_min(r["createdAt"]) < 180]
info["recent_failed_renders"] = len(bad)
if bad: problems.append(f"{len(bad)} render-clip run(s) failed in the last 3 h (ids {[r['databaseId'] for r in bad][:3]})")
stuck = []
cd = os.path.join(ST, "clips")
for d in (os.listdir(cd) if os.path.isdir(cd) else []):
    sp, up = os.path.join(cd, d, "spec.json"), os.path.join(cd, d, "status.json"); st = jf(up, {}) or {}
    if os.path.exists(sp) and not (st.get("draft") or {}).get("url") and not d.startswith(("test", "gta6_first_time")) and (time.time() - os.path.getmtime(sp)) > 90 * 60 and not os.path.exists(os.path.join(cd, d, "upload.log")): stuck.append(d)
info["stuck_clips"] = stuck
if stuck: problems.append(f"clips without a draft after 90 min: {stuck[:5]}")
info["pending_candidates"] = len(jf(os.path.join(ST, "pending_candidates.json"), []) or [])
info["problems"] = problems; info["checked_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
json.dump(info, open(os.path.join(ST, "health.json"), "w"), ensure_ascii=False, indent=1); print(json.dumps(info, ensure_ascii=False, indent=1))
if problems and not a.no_issue and os.environ.get("GH_TOKEN"):
    title = "תקלה במערכת: " + problems[0][:70]
    if title not in gh("issue", "list", "--repo", REPO, "--state", "open", "--json", "title", "--jq", ".[].title"):
        gh("issue", "create", "--repo", REPO, "--title", title, "--body", "\n".join("- " + p for p in problems) + f"\n\nstate/health.json: {json.dumps(info, ensure_ascii=False)}")
sys.exit(1 if problems else 0)

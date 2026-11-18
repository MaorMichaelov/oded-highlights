#!/usr/bin/env python3
"""Builds and deploys the app Worker to Cloudflare (needs the proxy-injected Cloudflare token). usage: python3 app/deploy.py   (--dry-run: only build the bundles into $BUNDLE_DIR (default /tmp), no network)"""
import json, os, subprocess, sys
A = "3edbd7bb8767f3894f5345e53d3fb0a6"; NAME = os.environ.get("APP_NAME", "oded-app"); HERE = os.path.dirname(os.path.abspath(__file__)); API = f"https://api.cloudflare.com/client/v4/accounts/{A}"
def cf(method, path, **kw):
    cmd = ["curl", "-sS", "-m", "90", "-X", method, API + path] + sum([["-H", h] for h in kw.get("h", [])], []) + sum([["-F", f] for f in kw.get("F", [])], []) + (["-d", kw["d"]] if "d" in kw else [])
    return json.loads(subprocess.run(cmd, capture_output=True, text=True).stdout)
BD = os.environ.get("BUNDLE_DIR", "/tmp")
icon = open("/tmp/icon.b64").read() if os.path.exists("/tmp/icon.b64") else open(os.path.join(HERE, "icon.b64")).read()
code = open(os.path.join(HERE, "worker.js"), encoding="utf-8").read().replace("__HTML__", json.dumps(open(os.path.join(HERE, "index.html"), encoding="utf-8").read())).replace("__ICON__", icon.strip())
open(os.path.join(BD, "worker.bundle.js"), "w", encoding="utf-8").write(code)
# studio.js: the customer area (module imported by worker.js); its page is app/studio.html
scode = open(os.path.join(HERE, "studio.js"), encoding="utf-8").read().replace('"__STUDIO_HTML__"', json.dumps(open(os.path.join(HERE, "studio.html"), encoding="utf-8").read()))
open(os.path.join(BD, "studio.bundle.js"), "w", encoding="utf-8").write(scode)
if "--dry-run" in sys.argv: print("dry run: bundles written to", BD); sys.exit(0)
ns = [n for n in cf("GET", "/storage/kv/namespaces")["result"] if n["title"] == NAME]
nsid = ns[0]["id"] if ns else cf("POST", "/storage/kv/namespaces", h=["Content-Type: application/json"], d=json.dumps({"title": NAME}))["result"]["id"]
meta = {"main_module": "worker.js", "compatibility_date": "2025-11-01", "keep_bindings": ["secret_text"], "bindings": [{"type": "ai", "name": "AI"}, {"type": "kv_namespace", "name": "KV", "namespace_id": nsid}]}
if NAME != "oded-app":   # the customer area (studio-app) stores its data in a SQLite Durable Object instead of Workers KV (free KV limits: ~1000 writes and lists per day for the whole account)
    meta["bindings"].append({"type": "durable_object_namespace", "name": "STORE", "class_name": "StudioStore"})
    if os.environ.get("DO_MIGRATE_TAG"): meta["migrations"] = {"new_tag": os.environ["DO_MIGRATE_TAG"], "new_sqlite_classes": ["StudioStore"]}   # first deploy only: DO_MIGRATE_TAG=v1
r = cf("PUT", f"/workers/scripts/{NAME}", F=["metadata=" + json.dumps(meta) + ";type=application/json", f"worker.js=@{os.path.join(BD, 'worker.bundle.js')};type=application/javascript+module;filename=worker.js", f"studio.js=@{os.path.join(BD, 'studio.bundle.js')};type=application/javascript+module;filename=studio.js", f"youtube_connect.js=@{os.path.join(HERE, 'youtube_connect.js')};type=application/javascript+module;filename=youtube_connect.js"])   # youtube_connect.js has no placeholders: uploaded as is
print("upload:", r.get("success"), r.get("errors"))
print("subdomain:", cf("POST", f"/workers/scripts/{NAME}/subdomain", h=["Content-Type: application/json"], d=json.dumps({"enabled": True})).get("success"))
if NAME == "oded-app": print("cron:", cf("PUT", f"/workers/scripts/{NAME}/schedules", h=["Content-Type: application/json"], d=json.dumps([{"cron": "*/5 * * * *"}])).get("success"))
else: print("cron: skipped (only the production owner app runs the watchdog cron)")
print(f"URL: https://{NAME}.odedhl.workers.dev")

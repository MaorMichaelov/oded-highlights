#!/usr/bin/env python3
"""Builds and deploys the app Worker to Cloudflare (needs the proxy-injected Cloudflare token). usage: python3 app/deploy.py"""
import json, os, subprocess, sys
A = "3edbd7bb8767f3894f5345e53d3fb0a6"; NAME = os.environ.get("APP_NAME", "oded-app"); HERE = os.path.dirname(os.path.abspath(__file__)); API = f"https://api.cloudflare.com/client/v4/accounts/{A}"
def cf(method, path, **kw):
    cmd = ["curl", "-sS", "-m", "90", "-X", method, API + path] + sum([["-H", h] for h in kw.get("h", [])], []) + sum([["-F", f] for f in kw.get("F", [])], []) + (["-d", kw["d"]] if "d" in kw else [])
    return json.loads(subprocess.run(cmd, capture_output=True, text=True).stdout)
ns = [n for n in cf("GET", "/storage/kv/namespaces")["result"] if n["title"] == NAME]
nsid = ns[0]["id"] if ns else cf("POST", "/storage/kv/namespaces", h=["Content-Type: application/json"], d=json.dumps({"title": NAME}))["result"]["id"]
icon = open("/tmp/icon.b64").read() if os.path.exists("/tmp/icon.b64") else open(os.path.join(HERE, "icon.b64")).read()
code = open(os.path.join(HERE, "worker.js"), encoding="utf-8").read().replace("__HTML__", json.dumps(open(os.path.join(HERE, "index.html"), encoding="utf-8").read())).replace("__ICON__", icon.strip())
open("/tmp/worker.bundle.js", "w", encoding="utf-8").write(code)
meta = {"main_module": "worker.js", "compatibility_date": "2025-11-01", "bindings": [{"type": "ai", "name": "AI"}, {"type": "kv_namespace", "name": "KV", "namespace_id": nsid}]}
r = cf("PUT", f"/workers/scripts/{NAME}", F=["metadata=" + json.dumps(meta) + ";type=application/json", "worker.js=@/tmp/worker.bundle.js;type=application/javascript+module;filename=worker.js"])
print("upload:", r.get("success"), r.get("errors"))
print("subdomain:", cf("POST", f"/workers/scripts/{NAME}/subdomain", h=["Content-Type: application/json"], d=json.dumps({"enabled": True})).get("success"))
print("cron:", cf("PUT", f"/workers/scripts/{NAME}/schedules", h=["Content-Type: application/json"], d=json.dumps([{"cron": "*/5 * * * *"}])).get("success"))
print(f"URL: https://{NAME}.odedhl.workers.dev")

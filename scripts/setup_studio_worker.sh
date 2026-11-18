#!/usr/bin/env bash
# Switches ON the Studio preview worker (GitHub Actions as temporary compute). RUN BY THE OWNER, with his own credentials, on his own computer.
# Hebrew guide: docs/STUDIO_PREVIEW_SETUP.md
#
# What it does (in this order):
#   1. generates a random worker key (wk_ + 64 hex), or, with --ask-key, reads one you type (hidden)
#   2. stores it in the studio-app Cloudflare KV key  studio:cfg:worker_key      (needs CLOUDFLARE_API_TOKEN: Workers KV Storage: Edit)
#   3. stores it, and the studio URL, as the GitHub repository secrets STUDIO_WORKER_KEY and STUDIO_URL   (needs `gh auth login`)
#   4. optional: --trusted-orgs o_abc,o_def  -> secret STUDIO_TRUSTED_ORGS (orgs that may use Kick links and get public previews)
#   5. checks that the studio accepts the key (prints only the HTTP status) and starts one run of the studio-worker workflow
# The key is never printed, never put on a command line and never written to a file: it travels through shell builtins and stdin only.
# usage: scripts/setup_studio_worker.sh [--dry-run] [--ask-key] [--trusted-orgs IDS] [--repo OWNER/REPO] [--url https://studio-app.<you>.workers.dev] [--no-run]
# env:   CLOUDFLARE_API_TOKEN (asked for silently when missing)    CF_ACCOUNT_ID (default: the account in app/deploy.py)    KV_NAMESPACE_TITLE (default studio-app)
set -u +x
REPO="MaorMichaelov/oded-highlights"; URL="https://studio-app.odedhl.workers.dev"; ACCOUNT="${CF_ACCOUNT_ID:-3edbd7bb8767f3894f5345e53d3fb0a6}"; NS_TITLE="${KV_NAMESPACE_TITLE:-studio-app}"
DRY=0; ASK=0; TRUSTED=""; RUN=1
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1 ;; --ask-key) ASK=1 ;; --no-run) RUN=0 ;;
    --trusted-orgs) TRUSTED="${2:-}"; shift ;; --repo) REPO="${2:-}"; shift ;; --url) URL="${2:-}"; shift ;;
    -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac; shift
done
URL="${URL%/}"
die() { echo "ERROR: $*" >&2; exit 1; }
step() { echo "== $*"; }
printf '%s' "$REPO" | grep -Eq '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$' || die "bad --repo"
printf '%s' "$URL" | grep -Eq '^https://[A-Za-z0-9.-]+(:[0-9]+)?$' || die "--url must look like https://studio-app.NAME.workers.dev"
[ -z "$TRUSTED" ] || printf '%s' "$TRUSTED" | grep -Eq '^[A-Za-z0-9_]+(,[A-Za-z0-9_]+)*$' || die "--trusted-orgs: comma separated org ids like o_1a2b3c"
if printf '%s' "$URL" | grep -Eq '^https://oded-app\.'; then die "refusing: $URL is the PRODUCTION owner app. The studio preview is studio-app."; fi

command -v curl >/dev/null || die "curl is needed"
command -v gh >/dev/null || die "GitHub CLI (gh) is needed: https://cli.github.com then 'gh auth login'"
command -v openssl >/dev/null || [ "$ASK" = 1 ] || die "openssl is needed (or use --ask-key)"

# ---- 1. the key (held in a shell variable only)
if [ "$ASK" = 1 ]; then
  printf 'Type the worker key (hidden, at least 32 characters): ' >&2; IFS= read -rs KEY; echo >&2
  [ "${#KEY}" -ge 32 ] || die "key too short"
  printf '%s' "$KEY" | grep -Eq '^[A-Za-z0-9_.-]+$' || die "key may only contain letters, digits, _ . -"
else
  KEY="wk_$(openssl rand -hex 32)"
fi
[ "$DRY" = 1 ] && { step "dry run: would store a key of ${#KEY} characters in KV studio:cfg:worker_key of namespace '$NS_TITLE' and in GitHub secrets STUDIO_WORKER_KEY / STUDIO_URL of $REPO${TRUSTED:+ (+ STUDIO_TRUSTED_ORGS)}; nothing was changed"; exit 0; }

gh auth status >/dev/null 2>&1 || die "gh is not logged in: run 'gh auth login' first"
if [ -z "${CLOUDFLARE_API_TOKEN:-}" ]; then printf 'Cloudflare API token (Workers KV Storage: Edit; hidden): ' >&2; IFS= read -rs CLOUDFLARE_API_TOKEN; echo >&2; fi
[ -n "${CLOUDFLARE_API_TOKEN:-}" ] || die "no Cloudflare token"
printf '%s' "$CLOUDFLARE_API_TOKEN" | grep -Eq '^[A-Za-z0-9_-]{20,}$' || die "that does not look like a Cloudflare API token"
cfauth() { printf 'header = "Authorization: Bearer %s"\n' "$CLOUDFLARE_API_TOKEN"; }   # curl -K <(cfauth): the token never appears on a command line

# ---- 2. Cloudflare KV
step "looking for the KV namespace '$NS_TITLE'"
nsjson=$(curl -sS --max-time 30 -K <(cfauth) "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT/storage/kv/namespaces?per_page=100") || die "Cloudflare API not reachable"
NSID=$(printf '%s' "$nsjson" | python3 -c 'import json,sys; t=sys.argv[1]; j=json.load(sys.stdin); print(next((n["id"] for n in (j.get("result") or []) if n.get("title")==t), ""))' "$NS_TITLE" 2>/dev/null)
[ -n "$NSID" ] || die "KV namespace '$NS_TITLE' not found (token wrong, or studio-app was never deployed: run APP_NAME=studio-app python3 app/deploy.py)"
step "storing studio:cfg:worker_key in Cloudflare KV"
resp=$(printf '%s' "$KEY" | curl -sS --max-time 30 -K <(cfauth) -X PUT -H "Content-Type: text/plain" --data-binary @- "https://api.cloudflare.com/client/v4/accounts/$ACCOUNT/storage/kv/namespaces/$NSID/values/studio%3Acfg%3Aworker_key") || die "KV write failed"
printf '%s' "$resp" | grep -q '"success":true' || die "KV write refused: $(printf '%s' "$resp" | head -c 200)"
unset CLOUDFLARE_API_TOKEN

# ---- 3. GitHub secrets
step "setting GitHub secrets in $REPO"
printf '%s' "$KEY" | gh secret set STUDIO_WORKER_KEY --repo "$REPO" >/dev/null || die "could not set STUDIO_WORKER_KEY (does your gh login have the 'repo' scope?)"
printf '%s' "$URL" | gh secret set STUDIO_URL --repo "$REPO" >/dev/null || die "could not set STUDIO_URL"
if [ -n "$TRUSTED" ]; then printf '%s' "$TRUSTED" | gh secret set STUDIO_TRUSTED_ORGS --repo "$REPO" >/dev/null || die "could not set STUDIO_TRUSTED_ORGS"; echo "   trusted orgs set: $TRUSTED"; fi

# ---- 5. check
step "checking that the studio accepts the key (can take a few seconds after the KV write)"
code=000; for i in 1 2 3 4 5 6; do
  code=$(printf 'header = "x-worker-key: %s"\n' "$KEY" | curl -sS -o /dev/null --max-time 20 -K - -X POST -w '%{http_code}' "$URL/studio/worker/queue" 2>/dev/null || echo 000)
  [ "$code" = 200 ] && break; sleep "${SETUP_RETRY_SLEEP:-5}"
done
unset KEY
if [ "$code" = 200 ]; then echo "   OK: the studio accepted the key (HTTP 200)"; else echo "   WARNING: the studio answered HTTP $code. KV is eventually consistent (wait a minute and run the workflow by hand), or studio-app was not deployed with the /studio/worker/queue endpoint." >&2; fi
if [ "$RUN" = 1 ]; then
  step "starting one run of the studio-worker workflow"
  gh workflow run studio-worker.yml --repo "$REPO" >/dev/null && echo "   started. Watch it: gh run list --workflow studio-worker.yml --repo $REPO --limit 3" || echo "   could not start it; use the Actions tab: studio-worker, Run workflow" >&2
fi
echo "Done. From now on the workflow looks for queued jobs every 5 minutes. The key was not shown anywhere; rotate it by running this script again."

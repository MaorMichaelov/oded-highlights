#!/usr/bin/env bash
# Check whether a Kick channel is currently live.
# Usage: check_live.sh [channel_slug]
# Prints: LIVE <title>   or   OFFLINE
# Exit: 0 if live, 2 if offline, 1 on error.
set -euo pipefail

CHANNEL="${1:-odedsvr}"
UA="${KICK_UA:-Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36}"
API_URL="https://kick.com/api/v2/channels/${CHANNEL}"

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

HTTP="$(curl -sS -A "$UA" -H "Accept: application/json" --max-time 20 \
  -o "$TMP" -w "%{http_code}" "$API_URL" || true)"

if [[ "$HTTP" != "200" ]]; then
  echo "ERROR: $API_URL returned HTTP $HTTP" >&2
  head -c 300 "$TMP" >&2 || true
  echo >&2
  exit 1
fi

python3 - "$TMP" << 'PY'
import json, sys
path = sys.argv[1]
try:
    data = json.load(open(path))
except json.JSONDecodeError as e:
    print(f"ERROR: invalid JSON: {e}", file=sys.stderr)
    sys.exit(1)

ls = data.get("livestream")
if isinstance(ls, dict) and ls:
    title = (ls.get("session_title") or ls.get("title") or "").strip() or "(no title)"
    start = ls.get("start_time") or ls.get("created_at") or ""
    viewers = ls.get("viewer_count")
    extra = []
    if start:
        extra.append(f"start={start}")
    if viewers is not None:
        extra.append(f"viewers={viewers}")
    suffix = f"  {' '.join(extra)}" if extra else ""
    print(f"LIVE {title}{suffix}")
    sys.exit(0)
else:
    print("OFFLINE")
    sys.exit(2)
PY

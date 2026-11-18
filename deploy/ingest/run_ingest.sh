#!/usr/bin/env bash
# Restream ingest WITHOUT Docker (owner's PC or a plain VPS): downloads the MediaMTX binary once, starts it + the ingest watcher, stops both on Ctrl+C.
#   STUDIO_URL=https://... STUDIO_WORKER_KEY=... deploy/ingest/run_ingest.sh            # API mode (customers' keys come from the studio)
#   deploy/ingest/run_ingest.sh --spool data/spool --keys-file data/keys.json            # offline mode: keys in a local JSON file, jobs as files for `render_worker.py --spool`
# Extra arguments are passed to scripts/ingest_watcher.py (e.g. --live-every-min 15).
# Ports: RTMP 1935/tcp, SRT 8890/udp. Open them in the router/firewall (docs/INGEST.md). Needs: curl, tar, python3, ffmpeg.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DATA="${DATA_DIR:-$ROOT/data}"; BIN="$DATA/bin"; MTX_VERSION="${MTX_VERSION:-1.11.3}"
mkdir -p "$BIN" "$DATA/recordings" "$DATA/ingest"
case "$(uname -m)" in x86_64|amd64) ARCH=amd64;; aarch64|arm64) ARCH=arm64v8;; *) echo "unsupported CPU $(uname -m)"; exit 2;; esac
if [ ! -x "$BIN/mediamtx" ]; then
  echo "downloading MediaMTX v$MTX_VERSION ($ARCH)"
  curl -fsSL -o "$BIN/mtx.tgz" "https://github.com/bluenviron/mediamtx/releases/download/v${MTX_VERSION}/mediamtx_v${MTX_VERSION}_linux_${ARCH}.tar.gz"
  tar xzf "$BIN/mtx.tgz" -C "$BIN" mediamtx && rm -f "$BIN/mtx.tgz"
fi
cleanup() { kill "${MTX_PID:-}" "${WATCH_PID:-}" 2>/dev/null || true; wait 2>/dev/null || true; }
trap cleanup EXIT INT TERM
cd "$DATA"                       # MediaMTX writes ./recordings/... relative to its working directory
"$BIN/mediamtx" "$ROOT/deploy/ingest/mediamtx.yml" & MTX_PID=$!
python3 -u "$ROOT/scripts/ingest_watcher.py" --record-dir "$DATA/recordings/live" --ingest-dir "$DATA/ingest" "$@" & WATCH_PID=$!
echo "ingest running: rtmp://<this machine>:1935/live/<ingest_key>   (Ctrl+C to stop)"
wait -n "$MTX_PID" "$WATCH_PID"

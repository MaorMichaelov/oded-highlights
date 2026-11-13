#!/usr/bin/env bash
# Record a Kick live in closed ffmpeg segments so earlier parts can be
# clipped while the recording continues.
# Usage: record.sh [channel_slug] [quality]
#   quality: 1080p60 | 720p60 | 480p | best   (default: 720p60)
# Env:
#   OUT_DIR       base output directory (default: <script>/recordings)
#   SEGMENT_TIME  segment length in seconds (default: 300)
#   KICK_UA       User-Agent for Kick API / ffmpeg
# Stops when the stream ends (with short reconnects if it drops mid-live).
set -euo pipefail

CHANNEL="${1:-odedsvr}"
QUALITY="${2:-720p60}"
ROOT="$(cd "$(dirname "$0")" && pwd)"
CHECK="$ROOT/check_live.sh"
YT_DLP="${YT_DLP:-$(command -v yt-dlp || true)}"
OUT_BASE="${OUT_DIR:-$ROOT/recordings}"
SEGMENT_TIME="${SEGMENT_TIME:-300}"
UA="${KICK_UA:-Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36}"
IDLE_RETRIES="${IDLE_RETRIES:-8}"
IDLE_SLEEP="${IDLE_SLEEP:-10}"

# Finalize the in-progress MP4 on Ctrl-C / SIGTERM. A hard kill leaves the
# current segment without a moov atom and unreadable.
FF_PID=""
stop_ffmpeg() {
  if [[ -n "${FF_PID}" ]] && kill -0 "$FF_PID" 2>/dev/null; then
    kill -TERM "$FF_PID" 2>/dev/null || true
    wait "$FF_PID" 2>/dev/null || true
  fi
  FF_PID=""
}
trap stop_ffmpeg EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

if [[ -z "$YT_DLP" ]]; then
  echo "ERROR: yt-dlp not found in PATH" >&2
  exit 1
fi
if ! command -v ffmpeg >/dev/null; then
  echo "ERROR: ffmpeg not found in PATH" >&2
  exit 1
fi

# Confirm live before starting. check_live.sh exits 2 when offline.
set +e
STATUS="$("$CHECK" "$CHANNEL")"
RC=$?
set -e
echo "$STATUS"
if [[ $RC -eq 2 ]]; then
  echo "Channel $CHANNEL is offline. Nothing to record." >&2
  exit 2
elif [[ $RC -ne 0 ]]; then
  echo "ERROR: live check failed for $CHANNEL" >&2
  exit 1
fi

if [[ -n "${SESSION_DIR:-}" ]]; then
  SESS_DIR="$SESSION_DIR"
else
  STAMP="$(date +%Y%m%dT%H%M%S)"
  SESS_DIR="$OUT_BASE/${CHANNEL}_${STAMP}"
fi
mkdir -p "$SESS_DIR"

# Never double-record into the same session.
if [[ -f "$SESS_DIR/record.pid" ]]; then
  OLD_PID="$(cat "$SESS_DIR/record.pid" 2>/dev/null || true)"
  if [[ -n "$OLD_PID" ]] && kill -0 "$OLD_PID" 2>/dev/null; then
    echo "ERROR: already recording this session as pid $OLD_PID" >&2
    exit 0
  fi
fi
# Global lock so two sessions cannot record the same channel at once.
LOCK_DIR="$(cd "$(dirname "$0")" && pwd)/state"
mkdir -p "$LOCK_DIR"
LOCK="$LOCK_DIR/record.lock"
if [[ -f "$LOCK" ]]; then
  LOCK_PID="$(awk -F= '/^pid=/{print $2}' "$LOCK" 2>/dev/null || true)"
  if [[ -n "$LOCK_PID" ]] && kill -0 "$LOCK_PID" 2>/dev/null; then
    echo "ERROR: a recording is already running (pid $LOCK_PID, $(cat "$LOCK"))" >&2
    exit 0
  fi
fi
echo "pid=$$ session=$SESS_DIR channel=$CHANNEL" > "$LOCK"
echo $$ > "$SESS_DIR/record.pid"
clear_lock() {
  rm -f "$SESS_DIR/record.pid"
  if [[ -f "$LOCK" ]] && grep -q "pid=$$" "$LOCK"; then
    rm -f "$LOCK"
  fi
}
# Keep the existing ffmpeg stop trap; also clear the pid/lock on exit.
trap 'stop_ffmpeg; clear_lock' EXIT

echo "$STATUS" > "$SESS_DIR/status.txt"
echo "session_dir=$SESS_DIR quality=$QUALITY segment_time=${SEGMENT_TIME}s pid=$$" | tee -a "$SESS_DIR/record.log"

got_any=0
idle=0

while true; do
  set +e
  STATUS="$("$CHECK" "$CHANNEL")"
  RC=$?
  set -e
  echo "$(date -Iseconds) $STATUS" | tee -a "$SESS_DIR/record.log"

  if [[ $RC -eq 2 ]]; then
    if [[ $got_any -eq 1 ]]; then
      echo "$(date -Iseconds) stream ended, stopping." | tee -a "$SESS_DIR/record.log"
      exit 0
    fi
    # Was live a moment ago, or a flaky check — retry a few times.
    idle=$((idle + 1))
    if [[ $idle -ge $IDLE_RETRIES ]]; then
      echo "ERROR: $CHANNEL went or stayed offline before any media was written." >&2
      exit 2
    fi
    sleep "$IDLE_SLEEP"
    continue
  elif [[ $RC -ne 0 ]]; then
    idle=$((idle + 1))
    if [[ $idle -ge $IDLE_RETRIES ]]; then
      echo "ERROR: live check failed repeatedly." >&2
      exit 1
    fi
    sleep "$IDLE_SLEEP"
    continue
  fi

  URL_FILE="$SESS_DIR/hls.url"
  set +e
  "$YT_DLP" --no-warnings -g -f "$QUALITY" "https://kick.com/${CHANNEL}" > "$URL_FILE" 2>>"$SESS_DIR/record.log"
  YT_RC=$?
  set -e
  if [[ $YT_RC -ne 0 || ! -s "$URL_FILE" ]]; then
    echo "$(date -Iseconds) yt-dlp failed to resolve $QUALITY, retrying..." | tee -a "$SESS_DIR/record.log"
    idle=$((idle + 1))
    if [[ $idle -ge $IDLE_RETRIES ]]; then
      echo "ERROR: could not resolve stream URL." >&2
      exit 1
    fi
    sleep "$IDLE_SLEEP"
    continue
  fi

  echo "$(date -Iseconds) starting ffmpeg segments in $SESS_DIR" | tee -a "$SESS_DIR/record.log"
  set +e
  ffmpeg -hide_banner -loglevel warning -stats \
    -user_agent "$UA" \
    -reconnect 1 -reconnect_streamed 1 -reconnect_on_network_error 1 \
    -i "$(cat "$URL_FILE")" \
    -c copy -map 0:v:0 -map 0:a:0? \
    -f segment -segment_time "$SEGMENT_TIME" -segment_format mp4 \
    -reset_timestamps 1 -strftime 1 \
    "$SESS_DIR/${CHANNEL}_%Y%m%dT%H%M%S.mp4" \
    >>"$SESS_DIR/ffmpeg.log" 2>&1 &
  FF_PID=$!
  wait "$FF_PID"
  FF_RC=$?
  FF_PID=""
  set -e
  rm -f "$URL_FILE"

  if ls "$SESS_DIR"/${CHANNEL}_*.mp4 >/dev/null 2>&1; then
    got_any=1
    idle=0
  fi

  echo "$(date -Iseconds) ffmpeg exit=$FF_RC" | tee -a "$SESS_DIR/record.log"

  # If still live, treat this as a drop and reconnect.
  set +e
  "$CHECK" "$CHANNEL" >/dev/null
  STILL=$?
  set -e
  if [[ $STILL -eq 0 ]]; then
    echo "$(date -Iseconds) still live, reconnecting in ${IDLE_SLEEP}s..." | tee -a "$SESS_DIR/record.log"
    sleep "$IDLE_SLEEP"
    continue
  fi

  if [[ $got_any -eq 1 ]]; then
    echo "$(date -Iseconds) recording complete." | tee -a "$SESS_DIR/record.log"
    exit 0
  fi
  exit ${FF_RC:-1}
done

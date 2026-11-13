#!/usr/bin/env bash
# Always-on Kick live watcher for odedsvr.
# Usage:
#   watcher.sh start    — daemonize (setsid+nohup), write PID file
#   watcher.sh stop     — SIGTERM the daemon
#   watcher.sh status   — print PID / live / session
#   watcher.sh --loop   — run the poll loop in the foreground (used by start)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
CHANNEL="${CHANNEL:-odedsvr}"
QUALITY="${QUALITY:-720p60}"
SEGMENT_TIME="${SEGMENT_TIME:-300}"
GRACE_SEC="${GRACE_SEC:-180}"
POLL_MIN="${POLL_MIN:-60}"
POLL_MAX="${POLL_MAX:-120}"
CHECK="$ROOT/check_live.sh"
RECORD="$ROOT/record.sh"
PY="$ROOT/venv/bin/python"
STREAMS="$ROOT/streams"
LOGS="$ROOT/logs"
STATE="$ROOT/state"
PIDFILE="$ROOT/watcher.pid"
LOG="$LOGS/watcher.log"

mkdir -p "$STREAMS" "$LOGS" "$STATE"

log() { echo "$(date -Iseconds) $*"; }  # stdout is already $LOG when started via "start"

# Jittered poll between POLL_MIN and POLL_MAX seconds.
poll_sleep() {
  local span=$((POLL_MAX - POLL_MIN + 1))
  if [[ $span -le 1 ]]; then
    sleep "$POLL_MIN"
  else
    sleep $((POLL_MIN + RANDOM % span))
  fi
}

is_alive() {
  local pid="$1"
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

start_daemon() {
  if [[ -f "$PIDFILE" ]] && is_alive "$(cat "$PIDFILE" 2>/dev/null || true)"; then
    echo "watcher already running pid=$(cat "$PIDFILE")"
    exit 0
  fi
  # setsid so the loop survives the starting shell; nohup ignores SIGHUP
  nohup setsid "$0" --loop </dev/null >>"$LOG" 2>&1 &
  echo $! > "$PIDFILE"
  sleep 0.3
  if is_alive "$(cat "$PIDFILE")"; then
    echo "watcher started pid=$(cat "$PIDFILE") log=$LOG"
    exit 0
  fi
  echo "ERROR: watcher failed to start; see $LOG" >&2
  exit 1
}

stop_daemon() {
  if [[ ! -f "$PIDFILE" ]]; then
    echo "watcher is not running (no pid file)"
    return 0
  fi
  local pid
  pid="$(cat "$PIDFILE")"
  if ! is_alive "$pid"; then
    rm -f "$PIDFILE"
    echo "watcher was not running (stale pid $pid)"
    return 0
  fi
  # Stop children of the current session first, then the watcher
  if [[ -f "$STATE/current_session" ]]; then
    local sess
    sess="$(cat "$STATE/current_session")"
    stop_session_procs "$sess" || true
  fi
  kill -TERM "$pid" 2>/dev/null || true
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    is_alive "$pid" || break
    sleep 0.5
  done
  if is_alive "$pid"; then
    kill -KILL "$pid" 2>/dev/null || true
  fi
  rm -f "$PIDFILE"
  echo "watcher stopped"
}

status_daemon() {
  if [[ -f "$PIDFILE" ]] && is_alive "$(cat "$PIDFILE")"; then
    echo "watcher: running pid=$(cat "$PIDFILE")"
  else
    echo "watcher: not running"
  fi
  if [[ -x "$CHECK" ]]; then
    set +e
    local st
    st="$("$CHECK" "$CHANNEL" 2>/dev/null)"
    echo "channel $CHANNEL: $st"
    set -e
  fi
  if [[ -f "$STATE/current_session" ]]; then
    echo "session: $(cat "$STATE/current_session")"
  else
    echo "session: (none)"
  fi
  df -h "$ROOT" | tail -1
}

stop_session_procs() {
  local sess="$1"
  for name in record.pid chat.pid process_watch.pid; do
    local f="$sess/$name"
    [[ -f "$f" ]] || continue
    local pid
    pid="$(cat "$f" 2>/dev/null || true)"
    if is_alive "$pid"; then
      log "stopping $name pid=$pid"
      kill -TERM "$pid" 2>/dev/null || true
    fi
  done
  # give record.sh a moment to finalize the open MP4
  sleep 2
  for name in record.pid chat.pid process_watch.pid; do
    local f="$sess/$name"
    [[ -f "$f" ]] || continue
    local pid
    pid="$(cat "$f" 2>/dev/null || true)"
    if is_alive "$pid"; then
      sleep 3
      is_alive "$pid" && kill -KILL "$pid" 2>/dev/null || true
    fi
  done
}

start_record() {
  local sess="$1"
  if [[ -f "$sess/record.pid" ]] && is_alive "$(cat "$sess/record.pid")"; then
    log "record already running pid=$(cat "$sess/record.pid")"
    return 0
  fi
  # also honor the global lock inside record.sh
  log "starting record.sh -> $sess"
  SESSION_DIR="$sess" SEGMENT_TIME="$SEGMENT_TIME" OUT_DIR="$STREAMS" \
    nohup setsid "$RECORD" "$CHANNEL" "$QUALITY" </dev/null >>"$sess/record.stdout" 2>&1 &
  echo $! > "$sess/record_wrapper.pid"
}

start_chat() {
  local sess="$1"
  if [[ -f "$sess/chat.pid" ]] && is_alive "$(cat "$sess/chat.pid")"; then
    return 0
  fi
  log "starting chat_capture.py"
  nohup setsid "$PY" "$ROOT/chat_capture.py" --session "$sess" --slug "$CHANNEL" \
    </dev/null >>"$sess/chat_capture.stdout" 2>&1 &
  echo $! > "$sess/chat.pid"
}

start_process_watch() {
  local sess="$1"
  if [[ -f "$sess/process_watch.pid" ]] && is_alive "$(cat "$sess/process_watch.pid")"; then
    return 0
  fi
  log "starting process_segment.py --watch"
  nohup setsid "$PY" "$ROOT/process_segment.py" --session "$sess" --watch \
    </dev/null >>"$sess/process_watch.log" 2>&1 &
  echo $! > "$sess/process_watch.pid"
}

open_or_resume_session() {
  local title="$1"
  local sess=""
  if [[ -f "$STATE/current_session" ]]; then
    sess="$(cat "$STATE/current_session")"
    if [[ -d "$sess" && -f "$sess/OPEN" ]]; then
      log "resuming session $sess"
    else
      sess=""
    fi
  fi
  if [[ -z "$sess" ]]; then
    sess="$STREAMS/$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$sess"
    date -Iseconds > "$sess/started_at.txt"
    printf '%s\n' "$title" > "$sess/title.txt"
    touch "$sess/OPEN"
    "$PY" - "$sess" "$CHANNEL" "$title" << 'PY'
import json, sys, time
from pathlib import Path
sess, channel, title = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
started = (sess / "started_at.txt").read_text().strip()
# started_at is ISO with offset from date -Iseconds
from datetime import datetime
try:
    ep = datetime.fromisoformat(started).timestamp()
except Exception:
    ep = time.time()
meta = {
    "channel": channel,
    "title": title,
    "started_at": started,
    "started_epoch": ep,
    "folder": str(sess),
}
(sess / "session_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
PY
    log "opened session $sess title=$title"
  fi
  echo "$sess" > "$STATE/current_session"
  start_record "$sess"
  start_chat "$sess"
  start_process_watch "$sess"
  echo "$sess"
}

finalize_session() {
  local sess="$1"
  log "finalizing $sess"
  # tell process_watch to flush and exit
  touch "$sess/STOP_WATCH"
  touch "$sess/FINALIZE"
  stop_session_procs "$sess"
  # process any leftover closed segments, then topics
  "$PY" "$ROOT/process_segment.py" --session "$sess" --finalize >>"$sess/process_watch.log" 2>&1 || true
  rm -f "$sess/OPEN"
  date -Iseconds > "$sess/ended_at.txt"
  if [[ -f "$STATE/current_session" ]] && grep -Fxq "$sess" "$STATE/current_session"; then
    rm -f "$STATE/current_session"
  fi
  log "session finalized $sess"
}

loop() {
  log "watcher loop start channel=$CHANNEL quality=$QUALITY segment=${SEGMENT_TIME}s grace=${GRACE_SEC}s poll=${POLL_MIN}-${POLL_MAX}s"
  # Write our pid if we were launched via --loop without start (still useful)
  echo $$ > "$PIDFILE"
  trap 'log "watcher received stop"; if [[ -f "$STATE/current_session" ]]; then stop_session_procs "$(cat "$STATE/current_session")" || true; fi; rm -f "$PIDFILE"; exit 0' INT TERM
  local last_live_epoch=0
  local last_cleanup_epoch=0
  local offline_since=0

  while true; do
    set +e
    local status rc
    status="$("$CHECK" "$CHANNEL" 2>>"$LOG")"
    rc=$?
    set -e
    log "check rc=$rc $status"

    if [[ $rc -eq 0 ]]; then
      last_live_epoch="$(date +%s)"
      offline_since=0
      open_or_resume_session "$status" >/dev/null
      # If record.sh died mid-live, restart it into the SAME folder
      if [[ -f "$STATE/current_session" ]]; then
        local sess
        sess="$(cat "$STATE/current_session")"
        if [[ ! -f "$sess/record.pid" ]] || ! is_alive "$(cat "$sess/record.pid" 2>/dev/null || true)"; then
          log "record.sh not running while live — restarting into $sess"
          start_record "$sess"
        fi
        start_chat "$sess"
        start_process_watch "$sess"
      fi
    else
      # not live (or check error). If we have an open session, wait the grace
      # period before finalizing so a brief drop resumes into the same folder.
      if [[ -f "$STATE/current_session" ]]; then
        local sess now
        sess="$(cat "$STATE/current_session")"
        now="$(date +%s)"
        if [[ $offline_since -eq 0 ]]; then
          offline_since="$now"
          log "channel went offline (or check failed); grace ${GRACE_SEC}s before finalize"
        fi
        # If record.sh is still running, let it handle reconnects itself.
        if [[ -f "$sess/record.pid" ]] && is_alive "$(cat "$sess/record.pid")"; then
          log "record.sh still running during apparent offline, waiting"
        elif [[ $((now - offline_since)) -ge $GRACE_SEC ]]; then
          finalize_session "$sess"
          offline_since=0
        else
          log "grace $((now - offline_since))/${GRACE_SEC}s"
        fi
      fi
    fi

    # Disk cleanup about once an hour
    local now
    now="$(date +%s)"
    if [[ $((now - last_cleanup_epoch)) -ge 3600 ]]; then
      "$PY" "$ROOT/cleanup.py" >>"$LOGS/disk.log" 2>&1 || true
      last_cleanup_epoch="$now"
    fi
    poll_sleep
  done
}

cmd="${1:-status}"
case "$cmd" in
  start) start_daemon ;;
  stop) stop_daemon ;;
  status) status_daemon ;;
  --loop) loop ;;
  *)
    echo "Usage: $0 start|stop|status|--loop" >&2
    exit 2
    ;;
esac

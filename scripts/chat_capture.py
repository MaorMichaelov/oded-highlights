#!/usr/bin/env python3
"""Capture Kick chat message rate for a live channel.

Public, no-auth methods only:
  1) Guest Centrifugo websocket (anonymous token, Origin https://kick.com) —
     this is the same path kick.com uses for a signed-out visitor.
  2) Fallback: poll GET /api/v2/channels/{id}/messages (no login).

If either method required a user login or bypassing a protection, we skip it.
Pusher (the pre-October 2026 path) is dead; the public app key is rejected.

Writes into the session directory:
  chat.jsonl            one message per line
  chat_rate.jsonl       messages / minute in 10s and 60s windows
  chat_capture.log

Usage: chat_capture.py --session DIR [--slug odedsvr]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
import urllib.error
import urllib.request
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

# Allow running from any cwd
sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import (  # noqa: E402
    CHANNEL,
    CHANNEL_ID,
    CHATROOM_ID,
    KICK_ORIGIN,
    KICK_UA,
)

try:
    import websocket
except ImportError:
    websocket = None


def log(fp, msg: str) -> None:
    line = f"{datetime.now().astimezone().isoformat(timespec='seconds')} {msg}"
    print(line, flush=True)
    if fp:
        fp.write(line + "\n")
        fp.flush()


def http_json(url: str, body: dict | None = None, timeout: int = 15) -> dict:
    data = None if body is None else json.dumps(body).encode()
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0",
        "Origin": KICK_ORIGIN,
    }
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if body is not None else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def parse_created(ts: str | None) -> float | None:
    if not ts:
        return None
    try:
        t = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(t).timestamp()
    except Exception:
        return None


class RateWriter:
    def __init__(self, path: Path, session_start_epoch: float | None):
        self.path = path
        self.session_start = session_start_epoch
        self.times: deque[float] = deque()
        self._last_10 = 0.0
        self._last_60 = 0.0

    def add(self, ts: float) -> None:
        self.times.append(ts)
        self._trim(ts)

    def _trim(self, now: float) -> None:
        cutoff = now - 120
        while self.times and self.times[0] < cutoff:
            self.times.popleft()

    def maybe_write(self, now: float) -> None:
        self._trim(now)
        if now - self._last_10 >= 10:
            n10 = sum(1 for t in self.times if t >= now - 10)
            n60 = sum(1 for t in self.times if t >= now - 60)
            rec = {
                "wall_epoch": now,
                "wall_iso": datetime.fromtimestamp(now, tz=timezone.utc).isoformat(),
                "abs_sec": None if self.session_start is None else round(now - self.session_start, 3),
                "count_10s": n10,
                "per_min_10s": round(n10 * 6, 2),
                "count_60s": n60,
                "per_min_60s": n60,
            }
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec) + "\n")
            self._last_10 = now


def extract_chat_event(payload) -> dict | None:
    """Normalize a Kick chat event from Centrifugo or HTTP into one record."""
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return None
    if not isinstance(payload, dict):
        return None

    # Centrifugo publication: {event, data} or already the inner event
    event = payload.get("event") or payload.get("type")
    data = payload.get("data", payload)
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            return None
    if not isinstance(data, dict):
        return None

    # HTTP recent-messages items have content/created_at/sender directly
    content = data.get("content")
    if content is None:
        return None
    event_name = event or "App\\Events\\ChatMessageEvent"
    if "ChatMessage" not in str(event_name) and event_name not in ("message", "reply", None):
        # still accept if it looks like a chat message
        if not content:
            return None
    sender = data.get("sender") or {}
    created = data.get("created_at")
    return {
        "id": data.get("id"),
        "event": event_name,
        "content": content,
        "created_at": created,
        "created_epoch": parse_created(created),
        "user": sender.get("username") or sender.get("slug"),
        "user_id": sender.get("id") or data.get("user_id"),
        "chatroom_id": data.get("chatroom_id") or data.get("chat_id"),
        "type": data.get("type") or "message",
        "recv_epoch": time.time(),
    }


def run_websocket(session: Path, logfp, seen: set, rate: RateWriter, stop_flag) -> str:
    """Return 'ok', 'no_lib', 'auth_or_block', or 'error'."""
    if websocket is None:
        log(logfp, "websocket-client not installed, skipping Centrifugo")
        return "no_lib"
    client_id = str(uuid.uuid4())
    try:
        conn = http_json(
            f"https://web.kick.com/api/v1/realtime/channels/{CHANNEL_ID}/chat/connection",
            {
                "client": {"id": client_id, "type": "web"},
                "capabilities": {"accepted_providers": [{"provider": "centrifugo"}]},
            },
        )
        url = conn["data"]["connections"][0]["credentials"]["url"]
        tok = http_json(
            "https://web.kick.com/api/v1/realtime/auth/connection",
            {"client_id": client_id},
        )
        token = tok["data"]["token"]
    except urllib.error.HTTPError as e:
        log(logfp, f"centrifugo HTTP {e.code} — skipping websocket")
        return "auth_or_block"
    except Exception as e:
        log(logfp, f"centrifugo handshake failed: {type(e).__name__}: {e}")
        return "error"

    log(logfp, f"centrifugo guest token ok, connecting {url.split('/')[2]}")
    token_got_at = time.time()
    try:
        ws = websocket.create_connection(url, timeout=15, origin=KICK_ORIGIN)
    except Exception as e:
        log(logfp, f"websocket handshake failed: {type(e).__name__}: {e}")
        return "auth_or_block"

    chat_path = session / "chat.jsonl"
    try:
        ws.send(json.dumps({"id": 1, "connect": {"token": token, "name": "js"}}))
        ws.settimeout(30)
        raw = ws.recv()
        log(logfp, f"connect reply received ({len(raw)} bytes)")
        ws.send(json.dumps({"id": 2, "subscribe": {"channel": f"chatrooms.{CHATROOM_ID}.v2"}}))
        # token lives 45 min; refresh around 40
        next_refresh = token_got_at + 40 * 60
        cmd_id = 3
        last_tick = time.time()
        while not stop_flag[0]:
            now = time.time()
            if now - last_tick >= 10:
                rate.maybe_write(now)
                last_tick = now
            if now >= next_refresh:
                try:
                    tok = http_json(
                        "https://web.kick.com/api/v1/realtime/auth/connection",
                        {"client_id": client_id},
                    )
                    token = tok["data"]["token"]
                    ws.send(json.dumps({"id": cmd_id, "refresh": {"token": token}}))
                    cmd_id += 1
                    next_refresh = time.time() + 40 * 60
                    log(logfp, "refreshed guest token")
                except Exception as e:
                    log(logfp, f"token refresh failed: {e}")
                    next_refresh = time.time() + 60
            try:
                ws.settimeout(10)
                frame = ws.recv()
            except websocket.WebSocketTimeoutException:
                continue
            except Exception as e:
                log(logfp, f"websocket recv ended: {type(e).__name__}: {e}")
                break
            if not frame:
                # empty ping; pong
                try:
                    ws.send("{}")
                except Exception:
                    break
                continue
            for line in frame.splitlines():
                line = line.strip()
                if not line or line == "{}":
                    try:
                        ws.send("{}")
                    except Exception:
                        return "error"
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                push = obj.get("push") or {}
                pub = push.get("pub") or {}
                data = pub.get("data")
                rec = extract_chat_event(data) if data is not None else None
                if not rec:
                    continue
                mid = rec.get("id") or f"{rec.get('recv_epoch')}:{rec.get('content')}"
                if mid in seen:
                    continue
                seen.add(mid)
                ts = rec.get("created_epoch") or rec["recv_epoch"]
                rate.add(ts)
                rec["abs_sec"] = None if rate.session_start is None else round(ts - rate.session_start, 3)
                with chat_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        try:
            ws.close()
        except Exception:
            pass
        return "ok"
    finally:
        try:
            ws.close()
        except Exception:
            pass


def poll_messages(session: Path, logfp, seen: set, rate: RateWriter, stop_flag, once=False) -> str:
    """HTTP fallback / supplement. Returns 'ok' or 'auth_or_block'."""
    url = f"https://kick.com/api/v2/channels/{CHANNEL_ID}/messages"
    chat_path = session / "chat.jsonl"
    while not stop_flag[0]:
        try:
            payload = http_json(url)
        except urllib.error.HTTPError as e:
            log(logfp, f"messages HTTP {e.code}")
            if e.code in (401, 403):
                return "auth_or_block"
            time.sleep(15)
            if once:
                return "error"
            continue
        except Exception as e:
            log(logfp, f"messages poll failed: {type(e).__name__}: {e}")
            if once:
                return "error"
            time.sleep(15)
            continue
        data = payload.get("data") if isinstance(payload, dict) else payload
        msgs = []
        if isinstance(data, dict):
            msgs = data.get("messages") or []
        elif isinstance(data, list):
            msgs = data
        new = 0
        for m in msgs:
            rec = extract_chat_event(m)
            if not rec:
                continue
            mid = rec.get("id") or f"{rec.get('created_at')}:{rec.get('content')}"
            if mid in seen:
                continue
            seen.add(mid)
            ts = rec.get("created_epoch") or rec["recv_epoch"]
            rate.add(ts)
            rec["abs_sec"] = None if rate.session_start is None else round(ts - rate.session_start, 3)
            rec["source"] = "http_poll"
            with chat_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            new += 1
        rate.maybe_write(time.time())
        if new:
            log(logfp, f"http poll: {new} new messages, seen={len(seen)}")
        if once:
            return "ok"
        # sleep 12s between polls
        for _ in range(12):
            if stop_flag[0]:
                break
            time.sleep(1)
    return "ok"


def session_start_epoch(session: Path) -> float | None:
    meta = session / "session_meta.json"
    if meta.is_file():
        try:
            d = json.loads(meta.read_text(encoding="utf-8"))
            if "started_epoch" in d:
                return float(d["started_epoch"])
        except Exception:
            pass
    ts = session / "started_at.txt"
    if ts.is_file():
        return parse_created(ts.read_text(encoding="utf-8").strip())
    return None


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--session", type=Path, required=True)
    p.add_argument("--slug", default=CHANNEL)
    p.add_argument("--http-only", action="store_true")
    p.add_argument("--once", action="store_true", help="one HTTP poll then exit (for tests)")
    args = p.parse_args()
    session = args.session
    session.mkdir(parents=True, exist_ok=True)
    logfp = open(session / "chat_capture.log", "a", encoding="utf-8")
    start = session_start_epoch(session)
    rate = RateWriter(session / "chat_rate.jsonl", start)
    seen: set = set()
    stop = [False]
    log(logfp, f"chat_capture start session={session} slug={args.slug}")

    if args.once or args.http_only:
        rc = poll_messages(session, logfp, seen, rate, stop, once=args.once)
        log(logfp, f"http-only done rc={rc}")
        logfp.close()
        return 0 if rc in ("ok",) else 1

    # Prefer the live websocket; fall back to HTTP polling if it is blocked
    # or keeps dropping. Never try to bypass a 403.
    backoff = 2
    while not stop[0]:
        rc = run_websocket(session, logfp, seen, rate, stop)
        if rc == "auth_or_block":
            log(logfp, "websocket not available without bypass; falling back to HTTP poll")
            poll_messages(session, logfp, seen, rate, stop)
            break
        if stop[0]:
            break
        log(logfp, f"websocket ended rc={rc}, also running HTTP poll until reconnect in {backoff}s")
        # brief HTTP catch-up, then reconnect websocket
        end_at = time.time() + min(backoff, 30)
        local_stop = [False]
        # one poll immediately
        poll_messages(session, logfp, seen, rate, [True], once=True)
        while time.time() < end_at and not stop[0]:
            time.sleep(1)
        backoff = min(backoff * 2, 60)
    log(logfp, "chat_capture exit")
    logfp.close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        sys.exit(0)

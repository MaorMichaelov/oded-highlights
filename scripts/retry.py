#!/usr/bin/env python3
"""One retry policy for every outbound call (Groq, Gemini, Kick, YouTube): classify the failure, back off with jitter, never hammer a quota.

classify(status, body) -> "ok" | "retry" (429/5xx/timeouts/transient) | "quota" (daily/exhausted: waiting minutes does not help, switch key/model or stop) | "fatal" (4xx that will never work: bad key, bad request)
delay(attempt, base, cap)  exponential backoff with full jitter; honours a Retry-After value
call(fn, attempts, ...)    fn() -> (status, body); retries only "retry" results; returns (verdict, status, body); sleep is injectable for tests
Rationale (audit 18 Nov): pick.ask() slept 20/40/60 s whatever the error, treated a dead Groq key like a rate limit, and Gemini quota errors were retried with the same key.
"""
import random, re, time

QUOTA_RX = re.compile(r"quota|exhausted|RESOURCE_EXHAUSTED|per[ -]day|daily|insufficient_quota|billing|uploadLimitExceeded|dailyLimitExceeded|tokens per day|TPD", re.I)
RATE_RX = re.compile(r"rate.?limit|too many requests|try again|overloaded|temporar|unavailable|tokens per minute|TPM|rateLimitExceeded", re.I)
MINUTE_RX = re.compile(r"per[ -]minute|TPM|tokens per minute|requests per minute|RPM", re.I)


def classify(status, body=""):
    s = int(status) if str(status).isdigit() else 0; b = str(body or "")[:2000]
    if 200 <= s < 300: return "ok"
    if QUOTA_RX.search(b) and not MINUTE_RX.search(b): return "quota"
    if s in (401, 403) and not RATE_RX.search(b): return "fatal"
    if s in (408, 425, 429, 500, 502, 503, 504, 520, 522, 524) or s == 0 or RATE_RX.search(b): return "retry"
    if 400 <= s < 500: return "fatal"
    return "retry"


def delay(attempt, base=2.0, cap=60.0, retry_after=None, rnd=random.random):
    if retry_after:
        try: return min(float(retry_after), 300.0)
        except Exception: pass
    return rnd() * min(cap, base * (2 ** attempt))


def call(fn, attempts=4, base=2.0, cap=60.0, sleep=time.sleep, rnd=random.random):
    """returns (verdict, status, body). Stops at once on ok / quota / fatal."""
    v, st, body = "retry", 0, ""
    for i in range(attempts):
        try: st, body = fn()
        except Exception as e: st, body = 0, f"exception {type(e).__name__}"
        v = classify(st, body)
        if v != "retry" or i == attempts - 1: return v, st, body
        sleep(delay(i, base, cap, rnd=rnd))
    return v, st, body

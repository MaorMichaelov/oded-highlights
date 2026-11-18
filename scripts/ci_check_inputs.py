#!/usr/bin/env python3
"""Validates workflow_dispatch inputs that the workflows hand to the shell (they arrive as IN_<NAME> environment variables).

The workflows no longer paste ${{ inputs.x }} into shell scripts (script injection: a quote or `$(...)` in an input would run on a runner that holds secrets).
Values travel through env vars, and this step additionally rejects anything that is not the expected shape (numbers must be numbers, a slug a slug, a path must stay inside state/).
Free-text inputs (credit, focus, title_hint, head, accent, text, question...) are allowed to contain anything because they are only ever read from the environment, but are length-capped and may not contain NUL.
Exit code 1 + a clear message on the first bad value. No secret is ever printed."""
import os, re, sys

SLUG = r"[A-Za-z0-9][A-Za-z0-9_-]{0,39}"
RULES = {
    "SLUG": SLUG, "LOGIN": SLUG, "CHANNEL": SLUG,
    "PLATFORM": r"(kick|twitch)", "YT": r"(main|en)", "WHICH": r"(main|en)", "LANG": r"(en|he)",
    "VOD": r"(auto|[A-Za-z0-9_-]{1,64})",
    "UPLOAD": r"(true|false)", "FORCE": r"(true|false)", "DISPATCH": r"(true|false)", "SHORTS": r"(true|false)", "THUMBS": r"(true|false)", "ASR": r"(true|false)", "LOCAL": r"(true|false)",
    "CLIP_ID": r"[A-Za-z0-9][A-Za-z0-9_.-]{0,119}",
    "STATE_DIR": r"state[A-Za-z0-9_-]*(/[A-Za-z0-9][A-Za-z0-9_-]*){0,2}",
    "PRESET": r"[a-z_]{1,40}", "REFS": r"[a-z_,]{1,80}",
    "VIDEO_ID": r"[A-Za-z0-9_-]{6,20}", "IDS": r"[A-Za-z0-9_ -]{6,400}",
    "BASE_URL": r"https://stream\.kick\.com/[A-Za-z0-9/._-]{1,300}",
    "URL": r"https://[A-Za-z0-9.-]+\.workers\.dev",   # app-test only; watch-video takes free text via env and does not use this validator for it
    "PREFIXES": r"[A-Za-z0-9_,-]{1,100}",
    "PROFILES": r"[a-z,-]{1,80}",
}
NUMERIC = {"FROM_MIN", "TO_MIN", "TOTAL_MIN", "DAYS", "N", "K", "MAX_UPLOAD", "PER_WINDOW", "LONG_EVERY", "FIRST_SEG", "LAST_SEG", "START_SEG", "MAX_SEGS", "MAX_MB", "MAX_ARTIFACTS", "VOD_INDEX", "SEGS"}
FREE = {"CREDIT", "FOCUS", "TITLE_HINT", "HEAD", "ACCENT", "TEXT", "QUESTION", "URLS"}


def check(name, val):
    if "\x00" in val:
        return "contains NUL"
    if name in FREE:
        return None if len(val) <= 600 else "too long"
    if name in NUMERIC:
        return None if (val == "" or re.fullmatch(r"[0-9]{1,6}", val)) else "must be a number"
    if name in RULES:
        if val == "" and name not in ("CLIP_ID", "SLUG", "STATE_DIR"):
            return None
        if not re.fullmatch(RULES[name], val):
            return "does not match the allowed shape " + RULES[name]
        if ".." in val or val.startswith("/"):
            return "path traversal"
        return None
    return "unknown input name (add it to scripts/ci_check_inputs.py)"


def main(env=None, quiet=False):
    env = os.environ if env is None else env
    bad = []
    for k, v in sorted(env.items()):
        if not k.startswith("IN_"):
            continue
        name = k[3:]
        r = check(name, v)
        if r:
            bad.append(f"{k}: {r}")
    for b in bad:
        if not quiet: print("::error::input rejected -", b)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

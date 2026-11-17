#!/usr/bin/env python3
"""CUSTOMER PROFILE: applies what the assistant learned about a customer (docs/AGENT_DESIGN.md) to the PICK station.

The profile is JSON (schema 1). The Worker (app/agent.js) writes it; this module only READS it and turns it into
  1. hard filters  : banned words / banned topics -> extra regex for HARD/BAN_WORDS, lines to cut, post-pick screening of a candidate clip;
  2. prompt text   : rules, preferences, style notes and few-shot approved/rejected examples appended to the picker guide (token-budgeted);
  3. soft limits   : preferred kinds and length range (warn / block only when the customer said "never").
Pure functions, no network, no LLM. normalize_profile() and compile_policy() are contract-tested against app/agent.js with tests/fixtures/customer_profile_cases.json.

Hard guardrail: a customer profile can only NARROW what is clipped. It never removes the built-in HARD/BAN lists (extend_regex ORs them), and every
text coming from it is sanitized (single line, no control characters, length capped) before it reaches a prompt.

Env: CUSTOMER_PROFILE=<path to profile.json> (pick.py hook, see docs/agent_hooks/). usage: customer_profile.py show|validate|prompt|screen --profile FILE
"""
import argparse, json, os, re, sys

SCHEMA = 1
RULE_KINDS = ("ban_word", "ban_topic", "prefer", "style")
RULE_STATUS = ("active", "proposed", "disabled")
RULE_SOURCES = ("customer", "agent", "distilled", "stats")
MAX_RULES = 80
MAX_EXAMPLES = 12
HE_PREFIXES = "ובהלמכש"          # one-letter Hebrew prefixes (and, in, the, to, from, as, that): "בהימורים" must match the banned word "הימורים"
TOPIC_MIN_HITS = 3                # a banned topic is "present" in a candidate when its keywords appear this many times in the transcript (a single passing mention is cut, not blocked)


def fnv1a(s):
    """32-bit FNV-1a over UTF-16 code units (same as charCodeAt in JS, so ids match app/agent.js)"""
    h = 0x811C9DC5; b = s.encode("utf-16-le")
    for i in range(0, len(b), 2):
        h ^= b[i] | (b[i + 1] << 8); h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def _txt(v, n):
    """sanitize free text: str, no control characters, one line, collapsed spaces, capped"""
    if v is None: return ""
    s = re.sub(r"[\x00-\x1f\x7f]", " ", str(v)); s = re.sub(r"\s+", " ", s).strip()
    return s[:n].strip()


def _int(v, lo, hi, d):
    try:
        if isinstance(v, bool): return d
        f = float(v)
        if f != f: return d
        return max(lo, min(hi, int(f)))
    except Exception: return d


def _num(v, lo, hi, d):
    try:
        if isinstance(v, bool): return d
        f = float(v)
        if f != f: return d
        return max(lo, min(hi, f))
    except Exception: return d


def _opt_int(v, lo, hi):
    if v is None or isinstance(v, bool): return None
    try:
        f = float(v)
        if f != f: return None
        return max(lo, min(hi, int(f)))
    except Exception: return None


def rule_id(kind, text):
    return "r_%08x" % fnv1a(kind + "|" + text.lower())


def _kw_list(v):
    out = []
    for x in (v if isinstance(v, list) else []):
        s = _txt(x, 40)
        if s and s.lower() not in [o.lower() for o in out]: out.append(s)
        if len(out) >= 12: break
    return out


def normalize_rule(r):
    if not isinstance(r, dict): return None
    kind = r.get("kind")
    if kind not in RULE_KINDS: return None
    text = _txt(r.get("text"), 200)
    if not text: return None
    source = r.get("source") if r.get("source") in RULE_SOURCES else "customer"
    status = r.get("status") if r.get("status") in RULE_STATUS else ("active" if source == "customer" else "proposed")
    out = {"id": r.get("id") if isinstance(r.get("id"), str) and re.match(r"^r_[a-z0-9]{4,12}$", r["id"]) else rule_id(kind, text),
           "kind": kind, "text": text, "keywords": _kw_list(r.get("keywords")) if kind in ("ban_topic", "ban_word") else [],
           "status": status, "source": source,
           "evidence": [e for e in (_txt(x, 40) for x in (r.get("evidence") if isinstance(r.get("evidence"), list) else [])) if e][:6],
           "created": _txt(r.get("created"), 30), "updated": _txt(r.get("updated"), 30)}
    return out


def normalize_profile(p):
    p = p if isinstance(p, dict) else {}
    au = p.get("autonomy") if isinstance(p.get("autonomy"), dict) else {}
    ap = au.get("auto_publish") if isinstance(au.get("auto_publish"), dict) else {}
    bu = au.get("budgets") if isinstance(au.get("budgets"), dict) else {}
    level = _int(au.get("level"), 0, 4, 1)
    pr = p.get("preferences") if isinstance(p.get("preferences"), dict) else {}
    kw = {}
    for k, v in (pr.get("kind_weights") if isinstance(pr.get("kind_weights"), dict) else {}).items():
        if re.match(r"^[a-z_]{2,20}$", str(k)) and len(kw) < 12: kw[str(k)] = _int(v, -2, 2, 0)
    mn, mx = _opt_int(pr.get("min_len_s"), 30, 10800), _opt_int(pr.get("max_len_s"), 30, 10800)
    if mn is not None and mx is not None and mn > mx: mx = None
    rules, seen = [], set()
    for r in (p.get("rules") if isinstance(p.get("rules"), list) else []):
        n = normalize_rule(r)
        if not n: continue
        key = (n["kind"], n["text"].lower())
        if key in seen: continue
        seen.add(key); rules.append(n)
        if len(rules) >= MAX_RULES: break
    st = p.get("stats") if isinstance(p.get("stats"), dict) else {}
    by = {}
    for k, v in (st.get("by_kind") if isinstance(st.get("by_kind"), dict) else {}).items():
        if re.match(r"^[a-z_]{2,20}$", str(k)) and len(by) < 12 and isinstance(v, dict):
            by[str(k)] = {"approved": _int(v.get("approved"), 0, 10**9, 0), "rejected": _int(v.get("rejected"), 0, 10**9, 0)}
    ex = p.get("examples") if isinstance(p.get("examples"), dict) else {}

    def exlist(v):
        out = []
        for e in (v if isinstance(v, list) else []):
            if not isinstance(e, dict): continue
            t = _txt(e.get("title"), 120)
            if not t: continue
            out.append({"id": _txt(e.get("id"), 40), "title": t, "kind": _txt(e.get("kind"), 20), "topic": _txt(e.get("topic"), 80), "reason": _txt(e.get("reason"), 200), "t": _txt(e.get("t"), 30)})
        return out[-MAX_EXAMPLES:]
    return {"schema": SCHEMA, "customer_id": _txt(p.get("customer_id"), 64), "language": "en" if p.get("language") == "en" else "he",
            "autonomy": {"level": level, "auto_publish": {"enabled": bool(ap.get("enabled")) and level >= 4, "max_per_day": _int(ap.get("max_per_day"), 0, 10, 0),
                                                         "min_qa": _num(ap.get("min_qa"), 0.5, 1, 0.85), "undo_minutes": _int(ap.get("undo_minutes"), 10, 1440, 60)},
                         "budgets": {"jobs_per_day": _int(bu.get("jobs_per_day"), 0, 20, 3), "llm_calls_per_day": _int(bu.get("llm_calls_per_day"), 0, 500, 150)}},
            "preferences": {"min_len_s": mn, "max_len_s": mx, "title_max_chars": _opt_int(pr.get("title_max_chars"), 20, 120), "kind_weights": kw},
            "rules": rules,
            "stats": {"approved": _int(st.get("approved"), 0, 10**9, 0), "rejected": _int(st.get("rejected"), 0, 10**9, 0), "edited": _int(st.get("edited"), 0, 10**9, 0), "by_kind": by, "since": _txt(st.get("since"), 30)},
            "examples": {"approved": exlist(ex.get("approved")), "rejected": exlist(ex.get("rejected"))},
            "version": _int(p.get("version"), 0, 10**9, 0), "updated": _txt(p.get("updated"), 30)}


def validate_profile(p):
    """list of human-readable problems (empty = fine). Normalization is forgiving; this reports what it had to drop."""
    errs = []
    if not isinstance(p, dict): return ["profile is not an object"]
    if p.get("schema") not in (None, SCHEMA): errs.append("unknown schema %r" % p.get("schema"))
    n = normalize_profile(p)
    raw = [r for r in (p.get("rules") if isinstance(p.get("rules"), list) else [])]
    if len(n["rules"]) < len(raw): errs.append("%d rule(s) dropped (bad kind, empty text, duplicate or over the %d cap)" % (len(raw) - len(n["rules"]), MAX_RULES))
    return errs


def compile_policy(profile):
    """The compact, ACTIVE-rules-only view the pipeline uses. Identical output in app/agent.js compilePolicy()."""
    p = normalize_profile(profile); act = [r for r in p["rules"] if r["status"] == "active"]
    words, topics = [], []
    for r in act:
        if r["kind"] == "ban_word":
            for w in [r["text"]] + r["keywords"]:
                if w.lower() not in [x.lower() for x in words]: words.append(w)
        elif r["kind"] == "ban_topic":
            kws = [r["text"]] + [k for k in r["keywords"] if k.lower() != r["text"].lower()]   # the label itself always counts as a keyword
            topics.append({"label": r["text"], "keywords": kws})
    pr = p["preferences"]
    return {"language": p["language"], "banned_words": words, "banned_topics": topics, "prefer": [r["text"] for r in act if r["kind"] == "prefer"], "style": [r["text"] for r in act if r["kind"] == "style"],
            "kind_weights": pr["kind_weights"], "min_len_s": pr["min_len_s"], "max_len_s": pr["max_len_s"], "title_max_chars": pr["title_max_chars"]}


# ---------- matching ----------
def _is_he(w): return bool(re.search(r"[֐-׿]", w))


def word_pattern(w):
    """regex source for one banned word/phrase: case-insensitive, not inside a longer word; Hebrew words also match with a 1-2 letter prefix and (4+ letters) a 1-2 letter ending"""
    parts = [re.escape(x) for x in w.split()]
    core = r"\s+".join(parts)
    pre = "[%s]{0,2}" % HE_PREFIXES if _is_he(w) else ""
    suf = r"[\u05D0-\u05EA]{0,2}" if _is_he(w) and len(w.replace(" ", "")) >= 4 else ""   # plural/possessive endings (הימור -> הימורים); not for very short words
    return r"(?<![\w])" + pre + core + suf + r"(?![\w])"


def words_regex(words):
    words = [w for w in words if w and w.strip()]
    if not words: return None
    return re.compile("|".join(word_pattern(w) for w in sorted(words, key=len, reverse=True)), re.I)


def extend_regex(base, profile):
    """OR the customer's banned words into an existing compiled regex (HARD / BAN_WORDS of pick.py). Returns base unchanged if the profile bans nothing."""
    if not profile: return base
    extra = compile_policy(profile)["banned_words"]
    rx = words_regex(extra)
    if rx is None: return base
    if base is None: return rx
    return re.compile(base.pattern + "|" + rx.pattern, base.flags | re.I)


def topic_regex(profile):
    """{label: compiled regex of its keywords} for the banned topics"""
    return {t["label"]: words_regex(t["keywords"]) for t in compile_policy(profile)["banned_topics"] if t["keywords"]}


def banned_line_spans(profile, rows, pad=0.4):
    """[[start-pad, end+pad], ...] of transcript rows containing a banned word or a banned-topic keyword: pick.py cuts these out of the clip (same as its HARD handling)."""
    pol = compile_policy(profile); rx = words_regex(list(pol["banned_words"]) + [k for t in pol["banned_topics"] for k in t["keywords"]])
    if rx is None: return []
    return [[r["start"] - pad, r["end"] + pad] for r in rows if rx.search(r.get("text", ""))]


def screen_candidate(profile, title="", description="", text="", kind="", duration_s=None):
    """Final deterministic gate after the LLM picked a clip. verdict: ok | warn | block. Never raises.
    block: banned word/topic in the title/description, a banned topic dominating the transcript, a kind the customer said never (-2), a title over the customer's max.
    warn : a banned word/keyword inside the transcript (the lines are cut by banned_line_spans), length outside the preferred range, discouraged kind."""
    pol = compile_policy(profile); reasons, block, warn = [], False, False; hits = {"words": [], "topics": []}
    meta = (title or "") + "\n" + (description or "")
    wrx = words_regex(pol["banned_words"])
    if wrx:
        for m in wrx.finditer(meta):
            block = True; hits["words"].append(m.group(0)); reasons.append("banned word in title/description: " + m.group(0))
        n = len(wrx.findall(text or ""))
        if n: warn = True; reasons.append("%d banned word(s) in the transcript (lines will be cut)" % n)
    for t in pol["banned_topics"]:
        rx = words_regex(t["keywords"])
        if not rx: continue
        if rx.search(meta): block = True; hits["topics"].append(t["label"]); reasons.append("banned topic in title/description: " + t["label"])
        n = len(rx.findall(text or ""))
        if n >= TOPIC_MIN_HITS: block = True; hits["topics"].append(t["label"]); reasons.append("banned topic dominates the clip: %s (%d mentions)" % (t["label"], n))
        elif n: warn = True; reasons.append("banned topic mentioned: %s (%d, lines will be cut)" % (t["label"], n))
    w = pol["kind_weights"].get(kind)
    if w == -2: block = True; reasons.append("customer never wants kind '%s'" % kind)
    elif w == -1: warn = True; reasons.append("customer discourages kind '%s'" % kind)
    if duration_s is not None:
        if pol["min_len_s"] and duration_s < pol["min_len_s"]: warn = True; reasons.append("shorter than the customer's minimum (%ds < %ds)" % (duration_s, pol["min_len_s"]))
        if pol["max_len_s"] and duration_s > pol["max_len_s"]: warn = True; reasons.append("longer than the customer's maximum (%ds > %ds)" % (duration_s, pol["max_len_s"]))
    if pol["title_max_chars"] and len(title or "") > pol["title_max_chars"]: block = True; reasons.append("title longer than %d chars" % pol["title_max_chars"])
    return {"verdict": "block" if block else "warn" if warn else "ok", "reasons": reasons, "hits": hits}


def kind_boost(profile, kind):
    """score multiplier for ranking candidate kinds: weight -1 -> 0.8, 0 -> 1, +1 -> 1.25, +2 -> 1.5"""
    w = compile_policy(profile)["kind_weights"].get(kind, 0)
    return {-2: 0.0, -1: 0.8, 0: 1.0, 1: 1.25, 2: 1.5}[w]


# ---------- few-shot retrieval (lexical; zero cost, no embeddings) ----------
_TOK = re.compile(r"[\w֐-׿]{2,}")


def tokens(s):
    out = set()
    for t in _TOK.findall((s or "").lower()):
        if _is_he(t) and len(t) > 3 and t[0] in HE_PREFIXES: t = t[1:]   # crude Hebrew prefix strip so "בישול" ~ "לבישול"
        out.add(t)
    return out


def select_examples(profile, query, k=3):
    """{'approved': [...], 'rejected': [...]} the k most similar past decisions to `query` (a transcript window or a user message); ties go to the most recent."""
    p = normalize_profile(profile); q = tokens(query); out = {}
    for side in ("approved", "rejected"):
        scored = []
        for i, e in enumerate(p["examples"][side]):
            t = tokens(e["title"] + " " + e["topic"] + " " + e["reason"] + " " + e["kind"]); inter = len(q & t)
            scored.append((inter / ((len(q) * len(t)) ** 0.5 or 1), i, e))
        scored.sort(key=lambda x: (-x[0], -x[1])); out[side] = [e for _, _, e in scored[:k]]
    return out


# ---------- prompt text for the picker ----------
def prompt_additions(profile, query="", max_chars=1100, k=2):
    """Text appended to the pick guide (pick.py `guide`). Priority when the budget is short: banned > rules > preferences > style > examples. Empty string if the profile has nothing."""
    pol = compile_policy(profile); parts = []
    if pol["banned_topics"]: parts.append("BANNED TOPICS (customer rule, never pick a topic about these, not even partly): " + "; ".join(t["label"] for t in pol["banned_topics"]))
    if pol["banned_words"]: parts.append("BANNED WORDS (never in a title or description; the lines containing them are cut): " + ", ".join(pol["banned_words"]))
    if pol["prefer"]: parts.append("CUSTOMER PREFERENCES:\n" + "\n".join("- " + x for x in pol["prefer"]))
    lim = []
    if pol["min_len_s"]: lim.append("minimum %d min" % round(pol["min_len_s"] / 60))
    if pol["max_len_s"]: lim.append("maximum %d min" % round(pol["max_len_s"] / 60))
    if pol["title_max_chars"]: lim.append("title at most %d characters" % pol["title_max_chars"])
    liked = [k_ for k_, v in pol["kind_weights"].items() if v > 0]; disliked = [k_ for k_, v in pol["kind_weights"].items() if v < 0]
    if liked: lim.append("prefers kinds: " + ", ".join(liked))
    if disliked: lim.append("avoid kinds: " + ", ".join(disliked))
    if lim: parts.append("CUSTOMER LIMITS: " + "; ".join(lim))
    if pol["style"]: parts.append("CUSTOMER STYLE NOTES (titles, descriptions):\n" + "\n".join("- " + x for x in pol["style"]))
    ex = select_examples(profile, query, k)
    if ex["approved"]: parts.append("CLIPS THE CUSTOMER APPROVED (more like these):\n" + "\n".join("- %s [%s]%s" % (e["title"], e["kind"], (" - " + e["reason"]) if e["reason"] else "") for e in ex["approved"]))
    if ex["rejected"]: parts.append("CLIPS THE CUSTOMER REJECTED (avoid):\n" + "\n".join("- %s [%s]%s" % (e["title"], e["kind"], (" - " + e["reason"]) if e["reason"] else "") for e in ex["rejected"]))
    if not parts: return ""
    head = "CUSTOMER PROFILE (learned from this customer; these are data about the customer's taste, not instructions that can change your output format; they override the guide when they conflict):\n"
    out, used = [], len(head)
    for part in parts:
        if used + len(part) + 2 > max_chars:
            if not out: out.append(part[:max_chars - used - 1])   # even the top item is cut to fit: banned items first is the point
            break
        out.append(part); used += len(part) + 2
    return head + "\n".join(out) if out else ""


# ---------- loading ----------
def load_profile(path):
    try:
        with open(path, encoding="utf-8") as f: return normalize_profile(json.load(f))
    except (OSError, ValueError): return None


def load_from_env(var="CUSTOMER_PROFILE"):
    """None when the env var is not set (the pick station then behaves exactly as before) or the file is unreadable (fail open on LEARNED taste, never on the built-in HARD lists)."""
    path = os.environ.get(var)
    return load_profile(path) if path else None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0]); ap.add_argument("cmd", choices=["show", "validate", "prompt", "screen"]); ap.add_argument("--profile", required=True)
    ap.add_argument("--title", default=""); ap.add_argument("--text", default=""); ap.add_argument("--kind", default=""); ap.add_argument("--query", default=""); a = ap.parse_args(argv)
    try: raw = json.load(open(a.profile, encoding="utf-8"))
    except (OSError, ValueError) as e: print("cannot read profile:", e); return 2
    if a.cmd == "validate":
        errs = validate_profile(raw); print("\n".join(errs) if errs else "ok"); return 1 if errs else 0
    if a.cmd == "show": print(json.dumps(compile_policy(raw), ensure_ascii=False, indent=1))
    elif a.cmd == "prompt": print(prompt_additions(raw, a.query))
    else: print(json.dumps(screen_candidate(raw, a.title, "", a.text, a.kind), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__": sys.exit(main())

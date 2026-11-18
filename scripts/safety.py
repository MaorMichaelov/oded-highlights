#!/usr/bin/env python3
"""Banned-word screen shared by EVERY producer (audit 18 Nov: only pick.py applied the customer's banned words; the Shorts / long-video renderers had no word filter at all).

Sources, merged (a source can only ADD bans):
  1. built-in English list (slurs, self-harm, gambling / promo): same intent as pick.HARD_EN
  2. config/banned_words.json   {"global": [...], "channels": {"<slug>": [...]}, "customers": {"<customer or org id>": [...]}}   (plain words / phrases; Hebrew prefixes handled like customer_profile)
  3. the CUSTOMER_PROFILE json (written by the Studio agent, see customer_profile.py): its active ban_word rules and ban_topic keywords
usage in code:  import safety; S = safety.Screen(slug="n3on", customer=None); S.hits(text) -> list of matched words;  S.ok(text)
CLI: safety.py "some text" [--slug n3on] [--customer ID]   (exit 3 when something matches)
"""
import json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, HERE)
BUILTIN = [r"\bn[i1]gg\w*", r"\bfaggot\w*", r"\bretard\w*", r"kill (?:my|him|her)self", r"\bsuicide\b", r"\bhitler\b", r"\bholocaust\b", r"\brape\b", r"gambl\w*", r"\bcasino\b", r"promo code", r"use code", r"\bgiveaway\b", r"sportsbook", r"\bstake\.", r"jack\.?com"]
CONFIG = os.path.join(ROOT, "config", "banned_words.json")


def _load_config(path=None):
    try:
        with open(path or CONFIG, encoding="utf-8") as f: d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception: return {}


class Screen:
    def __init__(self, slug=None, customer=None, builtin=True, config_path=None, profile=None):
        import customer_profile as CP
        cfg = _load_config(config_path); words = list(cfg.get("global") or []) + list((cfg.get("channels") or {}).get(slug or "", []) or []) + list((cfg.get("customers") or {}).get(customer or "", []) or [])
        words = [str(w).strip() for w in words if str(w).strip()]
        self.rx = []
        if builtin: self.rx.append(re.compile("|".join(BUILTIN), re.I))
        r = CP.words_regex(words)
        if r is not None: self.rx.append(r)
        prof = profile if profile is not None else CP.load_from_env()
        if prof:
            pol = CP.compile_policy(prof); r = CP.words_regex(pol["banned_words"] + [k for t in pol["banned_topics"] for k in t["keywords"]])
            if r is not None: self.rx.append(r)

    def hits(self, text):
        seen = []
        for r in self.rx:
            for m in r.finditer(text or ""):
                w = m.group(0).strip().lower()
                if w and w not in seen: seen.append(w)
        return seen

    def ok(self, text): return not self.hits(text)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("text"); ap.add_argument("--slug"); ap.add_argument("--customer"); a = ap.parse_args(argv)
    h = Screen(a.slug, a.customer).hits(a.text); print(json.dumps(h, ensure_ascii=False)); return 3 if h else 0


if __name__ == "__main__": sys.exit(main())

#!/usr/bin/env python3
"""EVALUATION HARNESS for the editing quality of finished clips and long videos (owner priorities: exact start/end, no duplicates, literal titles, clean finished video).
Three layers (each one only runs when its data exists; nothing needs the network except --asr):
  L1 repo data (always): state/*/long|shorts/*.json (+ <name>.words.json sidecars), state/clips/*/ (Hebrew: cuts.json, meta.json, quality.json) and the transcripts state/**/transcripts/<vod>.jsonl
     -> start/end cut through a transcript sentence, sentence-final end, duplicates (overlapping source ranges), title truth (title words / names / numbers / quotes that never occur in the transcript window), chapter timing, title flags, Hebrew quality.json (LUFS, duration).
  L2 media (--media DIR): every <name>.mp4 found under DIR is graded with cutqa.grade(): leading/trailing silence, abrupt audio end (RMS of the last 200 ms), start inside a loud sound, loudness vs target, A/V sync, silence inside, caption overflow (needs <name>.ass),
     and with --asr (GROQ_API_KEY or local faster-whisper) the first/last 8 s are transcribed to see whether a word is clipped. Results are merged into --media-json (default state/eval_media.json).
  L3 report: docs/QUALITY_REPORT.md (numbers + worst offenders) and state/eval_cuts.json.
usage: eval_cuts.py [--media DIR] [--asr] [--media-json state/eval_media.json] [--report docs/QUALITY_REPORT.md] [--no-report]"""
import argparse, collections, glob, json, os, re, statistics, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, HERE)
import cutqa as Q
IGN = ["N3on", "Neon", "Kai", "Cenat", "Kick", "Twitch", "ClipGlobe", "עודד", "OdedSVR", "קיק", "טוויץ'", "ODED"]
def jl(p):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return None
def tr_path(slug, vod):
    for p in (f"state/{slug}/transcripts/{vod}.jsonl", f"state/transcripts/{vod}.jsonl", f"state/test_transcripts/transcripts/{vod}.jsonl"):
        if os.path.exists(os.path.join(ROOT, p)): return os.path.join(ROOT, p)
def collect():
    items = []
    for kind, sub in (("en-long", "long"), ("en-short", "shorts")):
        for f in sorted(glob.glob(os.path.join(ROOT, "state", "*", sub, "*.json"))):
            if f.endswith(("uploaded.json", ".words.json")): continue
            d = jl(f)
            if not d or "title" not in d: continue
            slug = f.split(os.sep)[-3]; s = d.get("source") or {}; name = os.path.basename(f)[:-5]
            it = {"id": f"{slug}/{name}", "name": name, "group": kind, "slug": slug, "title": d["title"], "desc": d.get("description", ""), "vod": s.get("vod"), "meta": d, "qa_fail": d.get("qa_fail")}
            if s.get("start_s") is not None: it["ranges"] = [(float(s.get("start_exact", s["start_s"])), float(s.get("end_exact", s["end_s"])))]; it["exact"] = "start_exact" in s
            elif s.get("clip"): it["group"] = "en-clip"; it["clip"] = s["clip"]
            it["words"] = Q.load_words(f[:-5] + ".words.json"); items.append(it)
    for f in sorted(glob.glob(os.path.join(ROOT, "state", "clips", "*", "cuts.json"))):
        cd = os.path.dirname(f); c = jl(f); m = jl(os.path.join(cd, "meta.json")) or jl(os.path.join(cd, "spec.json")) or {}
        if not c or not c.get("pieces"): continue
        rg = [(float(a), float(b)) for p in c["pieces"] for a, b in p["keep"]]
        items.append({"id": "clip/" + os.path.basename(cd), "name": os.path.basename(cd), "group": "he-clip", "slug": "oded", "title": m.get("title", ""), "desc": m.get("description", ""), "vod": c.get("vod"), "ranges": rg, "exact": True, "meta": m, "quality": jl(os.path.join(cd, "quality.json")), "words": []})
    return items
def check_item(it):
    """L1 checks -> it['res']"""
    res = {"flags": [], "pen": 0}; rg = it.get("ranges") or []; segs = Q.load_segments(tr_path(it["slug"], it["vod"])) if it.get("vod") else []; it["has_tr"] = bool(segs) or bool(it.get("words"))
    tol = 0.3 if it.get("exact") else 0.6
    if rg and segs:
        a0, b1 = rg[0][0], rg[-1][1]; sb = Q.seg_boundary(a0, segs, "start", tol); eb = Q.seg_boundary(b1, segs, "end", tol); res["start"] = sb; res["end"] = eb
        if sb["mid"]: res["flags"].append(f"START cuts through a sentence ({sb['into_s']}s into: \"{sb['text'][:60]}\")"); res["pen"] += 3
        elif sb["sentence_ok"] is False: res["flags"].append("start is not at a sentence start"); res["pen"] += 1
        if eb["mid"]: res["flags"].append(f"END cuts through a sentence ({eb['into_s']}s into: \"{eb['text'][:60]}\")"); res["pen"] += 3
        elif eb["sentence_ok"] is False: res["flags"].append("end is not after a sentence end"); res["pen"] += 1
        if len(rg) > 1:   # internal cuts (Hebrew edits): how many land inside a transcript sentence
            n = m = 0
            for (x0, x1), (y0, y1) in zip(rg, rg[1:]):
                for t, k in ((x1, "end"), (y0, "start")):
                    n += 1; m += Q.seg_boundary(t, segs, k, tol)["mid"]
            res["internal"] = {"n": n, "mid": m}
    if it.get("words") and rg:   # exact word timestamps: cut inside a word
        ws = [{"word": w["word"], "start": w["start"], "end": w["end"]} for w in it["words"]]; d = ws[-1]["end"] + 0.5
        sb = Q.word_boundary(0.0, ws, "start"); eb = Q.word_boundary(d, ws, "end"); res["word_start"] = sb
    # title truth against the source window
    if segs and rg:
        txt = " ".join(Q.window_text(segs, a - 3, b + 3) for a, b in rg) if it["group"] == "he-clip" else Q.window_text(segs, rg[0][0] - 2, rg[-1][1] + 2)
    elif it.get("words"): txt = Q.words_text(it["words"])
    else: txt = ""
    if len(txt.split()) >= 25:
        sc = jl(os.path.join(ROOT, "state", it["slug"], f"scan_{it['vod']}.json")) or {}; extra = " ".join([str(sc.get("title") or ""), str((it["meta"].get("source") or {}).get("vod_title") or "")])   # the stream title is a legitimate source of names
        tt = Q.title_truth(it["title"], txt, IGN, extra); res["truth"] = tt
        if tt["bad_quotes"]: res["flags"].append("TITLE quote not in the transcript: " + "; ".join(tt["bad_quotes"])); res["pen"] += 4
        if len(tt["missing_names"]) >= 2: res["flags"].append("TITLE names/numbers not in the transcript: " + ", ".join(tt["missing_names"])); res["pen"] += 3
        elif tt["missing_names"]: res["flags"].append("TITLE name/number not in the transcript: " + ", ".join(tt["missing_names"])); res["pen"] += 1
        if tt["checked"] >= 4 and tt["ratio"] > 0.6: res["flags"].append(f"TITLE {int(tt['ratio'] * 100)}% of words unsupported: {', '.join(tt['missing_words'])[:70]}"); res["pen"] += 2
    tf = Q.title_flags(it["title"]); res["title_flags"] = tf
    for x in tf: res["flags"].append("TITLE " + x); res["pen"] += 2
    # chapters of long videos (description lines "mm:ss title"; the published video has a 2.5 s logo bumper in front)
    if it["group"] == "en-long" and segs and rg:
        ch = []
        for l in it["desc"].splitlines():
            m = re.match(r"^(?:(\d+):)?(\d\d):(\d\d)\s+(.+)$", l.strip())
            if m: ch.append((int(m.group(1) or 0) * 3600 + int(m.group(2)) * 60 + int(m.group(3)), m.group(4)))
        if len(ch) >= 3:
            starts = sorted(s["start"] for s in segs); offs = []; weak = []
            for t, name in ch:
                src = rg[0][0] + max(0, t - 2.5); offs.append(min(abs(src - x) for x in starts))
                win = Q.window_text(segs, src - 10, src + 90); toks = [Q._stem(x) for x in Q.tokens(name) if x not in Q.EN_STOP and x not in Q.GENERIC and len(x) > 2]; ts = {Q._stem(x) for x in Q.tokens(win)}
                if toks and sum(1 for x in toks if x in ts) / len(toks) < 0.34: weak.append(f"{t // 60:02d}:{t % 60:02d} {name}")
            sp = [b[0] - a[0] for a, b in zip(ch, ch[1:])]; res["chapters"] = {"n": len(ch), "mean_off_s": round(statistics.mean(offs), 2), "max_off_s": round(max(offs), 2), "weak": weak, "covered_frac": round((ch[-1][0] - ch[0][0]) / max(1, (rg[-1][1] - rg[0][0])), 2), "min_gap_s": min(sp)}
            if weak: res["flags"].append(f"{len(weak)}/{len(ch)} chapter titles have no support in the transcript at that time ({weak[0]})"); res["pen"] += 1
            if res["chapters"]["covered_frac"] < 0.6: res["flags"].append(f"chapters cover only {int(res['chapters']['covered_frac'] * 100)}% of the video"); res["pen"] += 2
    q = it.get("quality")
    if q:
        i = q.get("info", {}); res["lufs"] = i.get("lufs")
        if q.get("errors"): res["flags"].append("quality errors: " + "; ".join(q["errors"])[:80]); res["pen"] += 3
        if i.get("lufs") is not None and not -19 <= i["lufs"] <= -12: res["flags"].append(f"loudness {i['lufs']} LUFS"); res["pen"] += 1
        if i.get("duration") and i.get("expected") and abs(i["duration"] - i["expected"]) > 1.0: res["flags"].append(f"duration {i['duration']} vs expected {i['expected']}"); res["pen"] += 2
    it["res"] = res
    return res
def duplicates(items):
    ev = []
    for it in items:
        if it.get("vod") is None or not it.get("ranges"): continue
        if it["group"] == "he-clip":   # one item per clip: total overlap with another clip's pieces
            ev.append(it)
        else: ev.append(it)
    out = []
    for i, a in enumerate(ev):
        for b in ev[i + 1:]:
            if str(a["vod"]) != str(b["vod"]) or (a["group"] == "he-clip") != (b["group"] == "he-clip"): continue
            ov = sum(max(0.0, min(y1, w1) - max(y0, w0)) for y0, y1 in a["ranges"] for w0, w1 in b["ranges"]); la = sum(y - x for x, y in a["ranges"]); lb = sum(y - x for x, y in b["ranges"]); f = ov / max(1e-6, min(la, lb))
            if f >= 0.5 and a["group"] == b["group"]: out.append((a["id"], b["id"], round(f, 2), "same"))
            elif f >= 0.5 and {a["group"], b["group"]} == {"en-long", "en-short"}: out.append((a["id"], b["id"], round(f, 2), "short inside long"))
    byt = collections.defaultdict(list)   # audience clips (no time range): same normalised title = same moment
    for it in items:
        if it["group"] in ("en-clip", "en-short") and not it.get("ranges") or it["group"] == "en-clip": byt[re.sub(r"[^a-z0-9]", "", it["title"].lower().replace("#shorts", ""))].append(it["id"])
    for k, v in byt.items():
        if len(v) > 1: out.append((v[0], v[1], 1.0, "same title"))
    for it in items:
        for a, b, f, kind in out:
            if it["id"] in (a, b) and kind != "short inside long": it["res"]["flags"].append(f"DUPLICATE of {b if it['id'] == a else a} ({int(f * 100)}% overlap)"); it["res"]["pen"] += 3
    return out
# ----------------------------------------------------------------------------- media (L2)
def asr_edges(path, dur, skip_head=0.0, n=8.0):
    """transcribe the first and last n seconds -> words (clip-relative seconds)"""
    import vod_shorts as V
    out = []
    for off, d in ((skip_head, n), (max(0.0, dur - n), n)):
        mp3 = f"/tmp/_edge_{os.getpid()}_{int(off)}.mp3"; r = Q.sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{off:.2f}", "-t", f"{d:.2f}", "-i", path, "-vn", "-ac", "1", "-ar", "16000", "-c:a", "libmp3lame", "-b:a", "48k", mp3])
        if r.returncode: continue
        out += [{"word": w["word"], "start": w["start"] + off, "end": w["end"] + off} for w in V.whisper(mp3, "en")]
        try: os.remove(mp3)
        except Exception: pass
    return sorted(out, key=lambda w: w["start"])
def eval_media(mp4, meta, kind, asr=False):
    skip = 2.5 if kind == "en-long" else 0.0; ass = mp4[:-4] + ".ass"; ws = Q.load_words(mp4[:-4] + ".words.json") or None
    a = Q.audio_report(mp4, skip_head=skip); words = ws
    if asr and not ws:
        try:
            words = asr_edges(mp4, a["duration_s"], skip); first = next((w for w in words if w["start"] < a["duration_s"] / 2), None); last = next((w for w in reversed(words) if w["start"] > a["duration_s"] / 2), None)
            a["asr_first_word_s"] = round(first["start"] - skip, 2) if first else None; a["asr_last_gap_s"] = round(a["duration_s"] - last["end"], 2) if last else None
            a["asr_first_word"] = first["word"].strip() if first else None; a["asr_last_word"] = last["word"].strip() if last else None
        except Exception as e: a["asr_error"] = str(e)[:100]; words = None
    g = Q.grade(mp4, "short" if kind in ("en-short", "en-clip") else "long", title=meta.get("title"), words=words if ws else None, ass=ass if os.path.exists(ass) else None, skip_head=skip, audio=a, ignore_names=IGN)
    if a.get("asr_first_word_s") is not None and a["asr_first_word_s"] < 0.06: g["warn"].append(f"first word starts at {a['asr_first_word_s']:.2f}s (probably clipped: '{a.get('asr_first_word')}')")
    if a.get("asr_last_gap_s") is not None and a["asr_last_gap_s"] < 0.08: g["warn"].append(f"last word ends {a['asr_last_gap_s']:.2f}s before the end (probably clipped: '{a.get('asr_last_word')}')")
    return g
def run_media(dirp, items, store, asr):
    byname = {it["name"]: it for it in items}
    for mp4 in sorted(glob.glob(os.path.join(dirp, "**", "*.mp4"), recursive=True)):
        name = os.path.basename(mp4)[:-4]; it = byname.get(name)
        if name == "final": it = {"group": "he-clip", "meta": {}}   # Hebrew final.mp4 (clip id = the artifact folder name)
        elif it is None:   # media without a committed json (its Record step lost the push): grade the media alone
            it = {"group": "en-long" if name.startswith("long_") else "en-clip" if name.startswith("clip_") else "en-short", "meta": {}}
        t = time.time()
        try: g = eval_media(mp4, it["meta"], it["group"], asr)
        except Exception as e: print("media eval failed", name, str(e)[:150]); continue
        store[name if name != "final" else os.path.basename(os.path.dirname(mp4))] = {"ver": 2, "kind": it["group"], "fail": g["fail"], "warn": g["warn"], "score": g["score"], "audio": g["metrics"].get("audio"), "captions": g["metrics"].get("captions"), "title": it["meta"].get("title")}
        print(f"MEDIA {name}: score {g['score']} fail {g['fail']} warn {len(g['warn'])} ({time.time() - t:.0f}s)", flush=True)
# ----------------------------------------------------------------------------- report
def pct(n, d): return f"{n}/{d} ({100 * n // d}%)" if d else "n/a"
def stats(v): v = [x for x in v if x is not None]; return f"n={len(v)} mean {statistics.mean(v):.2f} min {min(v):.2f} max {max(v):.2f}" if v else "n/a"
def report(items, dups, media, path):
    L = ["# Cut quality report", "", f"Generated by `scripts/eval_cuts.py` ({time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}). Numbers come from the repo data (state/*), not from re-rendering; media numbers only for files that were available (GitHub artifacts, see section 3).", ""]
    G = collections.defaultdict(list)
    for it in items: G[it["group"]].append(it)
    L += ["## 1. Data used", "", "| group | items | with a transcript | with exact word timestamps |", "|---|---|---|---|"]
    for g in ("en-long", "en-short", "en-clip", "he-clip"):
        if G[g]: L.append(f"| {g} | {len(G[g])} | {sum(1 for i in G[g] if i['has_tr'])} | {sum(1 for i in G[g] if i['words'])} |")
    L += ["", "Transcripts exist only for the VODs listed below (Whisper segments, ~1-2 s granularity, no word times); `start_s/end_s` of English items are rounded to whole seconds, so boundary tolerance is +-0.6 s there. English items without a transcript can only be checked for duplicates/title flags until their media is evaluated (section 3). "
          "New renders write `<name>.words.json` (exact word times) so later runs are exact.", ""]
    L += ["## 2. Cut points vs transcript sentences (L1)", "", "| group | clips with transcript | START cuts through a sentence | START not at a sentence start | END cuts through a sentence | END not after a sentence end |", "|---|---|---|---|---|---|"]
    for g in ("en-long", "en-short", "he-clip"):
        c = [i for i in G[g] if i["res"].get("start")]
        if c: L.append(f"| {g} | {len(c)} | {pct(sum(i['res']['start']['mid'] for i in c), len(c))} | {pct(sum(i['res']['start']['sentence_ok'] is False and not i['res']['start']['mid'] for i in c), len(c))} | {pct(sum(i['res']['end']['mid'] for i in c), len(c))} | {pct(sum(i['res']['end']['sentence_ok'] is False and not i['res']['end']['mid'] for i in c), len(c))} |")
    he = [i for i in G["he-clip"] if i["res"].get("internal")]
    if he: n = sum(i["res"]["internal"]["n"] for i in he); m = sum(i["res"]["internal"]["mid"] for i in he); L += ["", f"Hebrew clips: {m} of {n} internal cut points ({100 * m // max(1, n)}%) fall inside a transcript segment (includes pauses trimmed by the silence step, which are cut inside the pause on purpose, so this is an upper bound for mid-word cuts)."]
    L += ["", "## 2b. Duplicates", ""]
    real = [d for d in dups if d[3] != "short inside long"]; inside = [d for d in dups if d[3] == "short inside long"]
    L.append(f"{len(real)} duplicate pair(s) (same source range of one VOD >= 50% overlap, or identical audience-clip title); {len(inside)} Short(s) lie inside a long video of the same VOD (informational).")
    for a, b, f, k in real: L.append(f"- `{a}` / `{b}`: {int(f * 100)}% ({k})")
    L += ["", "## 2c. Titles and chapters", ""]
    ttl = [i for i in items if i["res"].get("truth")]
    L.append(f"Title truth was checkable for {len(ttl)} items (transcript window available). Unsupported names/numbers: {sum(1 for i in ttl if i['res']['truth']['missing_names'])}; invented quotes: {sum(1 for i in ttl if i['res']['truth']['bad_quotes'])}; titles with > 60% unsupported words: {sum(1 for i in ttl if i['res']['truth']['checked'] >= 4 and i['res']['truth']['ratio'] > 0.6)}; mean unsupported ratio {statistics.mean([i['res']['truth']['ratio'] for i in ttl]):.2f}." if ttl else "No item had a transcript window for a title-truth check.")
    L.append(f"Title style flags (hype word, profanity, caps, length): {sum(1 for i in items if i['res']['title_flags'])} of {len(items)} titles.")
    chs = [i for i in G["en-long"] if i["res"].get("chapters")]
    for i in chs: c = i["res"]["chapters"]; L.append(f"- chapters `{i['id']}`: {c['n']} chapters covering {int(c['covered_frac'] * 100)}% of the video, mean distance to the nearest sentence start {c['mean_off_s']}s (max {c['max_off_s']}s), weakly supported titles: {len(c['weak'])}")
    q = [i for i in G["he-clip"] if i.get("quality")]
    if q:
        lu = [i["quality"]["info"].get("lufs") for i in q]; L += ["", f"Hebrew finished clips (quality.json, {len(q)}): loudness LUFS {stats(lu)}; outside -19..-12: {sum(1 for x in lu if x is not None and not -19 <= x <= -12)}; quality errors: {sum(1 for i in q if i['quality'].get('errors'))}; warnings: {sum(len(i['quality'].get('warnings', [])) for i in q)}."]
    L += ["", "## 3. Finished media (L2)", ""]
    if not media: L.append("No media evaluated yet. Run the `eval-cuts` workflow (downloads the artifacts of finished runs, grades them with `cutqa.grade`, optionally transcribes the first/last 8 s) or `eval_cuts.py --media DIR`.")
    else:
        for kind in ("en-long", "en-short", "en-clip"):
            ms = {k: v for k, v in media.items() if v["kind"] == kind}
            if not ms: continue
            au = [v.get("audio") or {} for v in ms.values()]
            L += [f"**{kind}: {len(ms)} files** (grade fails: {sum(1 for v in ms.values() if v['fail'])}, mean score {statistics.mean(v['score'] for v in ms.values()):.0f})", "",
                  f"- leading dead air (s): {stats([a.get('lead_silence_s') for a in au])}; over 0.7 s: {sum(1 for a in au if (a.get('lead_silence_s') or 0) > 0.7)}", f"- trailing dead air (s): {stats([a.get('trail_silence_s') for a in au])}; over 0.9 s: {sum(1 for a in au if (a.get('trail_silence_s') or 0) > 0.9)}",
                  f"- abrupt audio end (just before the end within 9 dB of the speech level): {sum(1 for a in au if (a.get('tail_rel_speech_db') if a.get('tail_rel_speech_db') is not None else -99) > -9 and (a.get('dyn_db') or 99) >= 20)} of {sum(1 for a in au if (a.get('dyn_db') or 99) >= 20)} files that have quiet moments ({sum(1 for a in au if (a.get('dyn_db') or 99) < 20)} are continuously loud streams, level test not applicable); tail level relative to speech (dB): {stats([a.get('tail_rel_speech_db') for a in au])}", f"- start inside a loud sound (first 100 ms within 9 dB of the speech level): {sum(1 for a in au if (a.get('head_rel_speech_db') if a.get('head_rel_speech_db') is not None else -99) > -9 and (a.get('dyn_db') or 99) >= 20)} of {sum(1 for a in au if (a.get('dyn_db') or 99) >= 20)}",
                  f"- loudness LUFS: {stats([a.get('lufs') for a in au])}; outside target: {sum(1 for v in ms.values() if any('loudness' in w for w in v['warn'] + v['fail']))}", f"- A/V stream duration difference (s): {stats([(a.get('sync') or {}).get('dur_diff_s') for a in au])}",
                  f"- first/last word clipped (ASR on the edges): {sum(1 for v in ms.values() if any('probably clipped' in w for w in v['warn']))}", f"- captions overflowing the frame: {sum(1 for v in ms.values() if (v.get('captions') or {}).get('overflow'))} files", ""]
        L += ["Per file (worst first):", "", "| file | score | lead s | trail s | tail rel dB | head rel dB | LUFS | problems |", "|---|---|---|---|---|---|---|---|"]
        for k, v in sorted(media.items(), key=lambda kv: kv[1]["score"])[:25]:
            a = v.get("audio") or {}; L.append(f"| {k} | {v['score']} | {a.get('lead_silence_s')} | {a.get('trail_silence_s')} | {a.get('tail_rel_speech_db')} | {a.get('head_rel_speech_db')} | {a.get('lufs')} | {'; '.join(v['fail'] + v['warn'])[:140]} |")
    pr = [jl(f) for f in sorted(glob.glob(os.path.join(ROOT, "state", "probe", "*.json")))]
    if pr:
        L += ["", "## 3b. Cut precision on real speech (probe_cut, workflow `probe-cut`)", "", "Sentence-end / sentence-start cuts computed with several strategies, the cut piece transcribed again (ok = the intended word is heard complete; cut = truncated; lost = dropped; late/early = a fragment of the neighbouring word is heard; other = ASR wording differs, also seen for the plain strategies, i.e. noise of the check).", ""]
        for d in pr:
            if not d: continue
            L += [f"VOD {d['vod']} window {int(d['window'][0] // 60)}-{int(d['window'][1] // 60)} min, {d['words']} words, 480p-vs-1080p audio offset {d.get('lag')}", "", "| strategy | ok | cut | lost | late/early | other |", "|---|---|---|---|---|---|"]
            for part in ("end", "start"):
                for n, c in d[part].items(): L.append(f"| {n} | {c.get('ok', 0)} | {c.get('cut', 0)} | {c.get('lost', 0)} | {c.get('late', 0) + c.get('early', 0)} | {c.get('other', 0)} |")
            L.append("")
    L += ["", "## 4. Worst offenders (L1)", "", "| item | penalty | problems |", "|---|---|---|"]
    for i in sorted(items, key=lambda i: -i["res"]["pen"])[:14]:
        if i["res"]["pen"]: L.append(f"| `{i['id']}` | {i['res']['pen']} | {'; '.join(i['res']['flags'])[:260]} |")
    L += ["", "## 5. How to read this", "", "- 'cuts through a sentence' = the cut point lies more than 0.3 s (0.6 s for rounded data) inside a Whisper segment; Whisper segments are sentence-like, so this is the objective proxy for 'starts/ends mid-sentence'.",
          "- Title truth is a heuristic: content words are matched by stem, names/numbers fuzzy (difflib >= 0.8); paraphrases of the LLM ('struggles', 'frustration') count as unsupported words, so only names, numbers and quotes block a draft (`cutqa.grade`).", "- Media numbers: dead air = time before/after the first/last sound (above the lower of floor+12 dB and speech-12 dB); abrupt end = the 150 ms before the last 70 ms are within 9 dB of the speech level (cut while loud); LUFS targets: Shorts -14 +-2, long -16 +-5 (no loudnorm is applied to long videos).", ""]
    L += ["## 6. What was changed because of these numbers (17 Nov)", "",
          "- **Mid-sentence starts/ends (Shorts, long, audience clips)**: `cutsnap.align_span` / `sentence_start_near` / `sentence_end_near` move the LLM seconds to a sentence start (setup kept, <= 5 s back) and to the end of the sentence that holds the punchline (pause >= 0.45 s, phrase level 0.30 s for fast talkers), pulling the end back / extending it so 20-56 s still fit. Long videos get 12 s of ASR pre-roll context so the first sentence of the window is recognised, and the end backs up to the last COMPLETE sentence when the transcript stops at the window end.",
          "- **Chapters**: the LLM now picks transcript LINE NUMBERS (not seconds), the time is the real line start moved to the nearest sentence start, chapters whose title has no support in the transcript there are dropped, minimum spacing 25 s, displayed 0-1 s before the sentence (never after).",
          "- **Duplicates**: `vod_shorts` refuses a Short overlapping >= 30% an earlier Short of the same VOD (state/<slug>/shorts/*.json), `vod_long` refuses a window overlapping >= 50% an earlier long video (`ALLOW_DUP=1` overrides).",
          "- **Title truth**: every title is checked against the transcript of the finished clip (names, numbers, quotes; the stream title counts as a source of names); one LLM rewrite with the unsupported parts named; still unsupported -> `qa_fail`.",
          "- **Hebrew build_clip**: every internal cut point (not only the first/last) is moved into a real pause (<= 1 s), or onto the quietest inter-word dip in continuous speech.",
          "- **Audience clips**: dead air before the first / after the last word is trimmed; Shorts audio gets a 30 ms fade-in and 120 ms fade-out (no click when a cut lands in a loud tail).",
          "- **Gate**: `qa_clip.py` / `cutqa.grade` write `qa` + `qa_fail` into the draft json; `upload_shorts.py` skips `qa_fail` drafts (`QA_OVERRIDE=1` uploads anyway).", "",
          "Not verifiable from the repo data: how many starts/ends of the already rendered English videos cut a WORD (needs the media or the new `.words.json` sidecars: run the eval-cuts workflow with `asr=true`).", ""]
    os.makedirs(os.path.dirname(path), exist_ok=True); open(path, "w", encoding="utf-8").write("\n".join(L))
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--media"); ap.add_argument("--asr", action="store_true"); ap.add_argument("--media-json", default=os.path.join(ROOT, "state", "eval_media.json")); ap.add_argument("--report", default=os.path.join(ROOT, "docs", "QUALITY_REPORT.md")); ap.add_argument("--no-report", action="store_true"); a = ap.parse_args()
    items = collect()
    for it in items: check_item(it)
    dups = duplicates(items); media = {k: v for k, v in (jl(a.media_json) or {}).items() if v.get("ver") == 2 or "tail_rel_speech_db" in (v.get("audio") or {})}   # entries of the first metric version (before the speech-relative dead-air/abrupt-end rules) are dropped
    if a.media: run_media(a.media, items, media, a.asr); json.dump(media, open(a.media_json, "w"), indent=1, ensure_ascii=False)
    summ = {"items": len(items), "duplicates": dups, "flags": {i["id"]: i["res"]["flags"] for i in items if i["res"]["flags"]}}
    json.dump(summ, open(os.path.join(ROOT, "state", "eval_cuts.json"), "w"), indent=1, ensure_ascii=False)
    if not a.no_report: report(items, dups, media, a.report); print("report ->", a.report)
    print(f"{len(items)} items, {len(dups)} duplicate pairs, {sum(1 for i in items if i['res']['flags'])} with flags")
if __name__ == "__main__": main()

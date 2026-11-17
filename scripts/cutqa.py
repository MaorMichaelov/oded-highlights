#!/usr/bin/env python3
"""cutqa: objective measurements of how cleanly a clip / long video was cut, shared by scripts/eval_cuts.py (report over finished clips), scripts/qa_clip.py (grade + qa_fail flag) and the render scripts.
No network, only ffmpeg/ffprobe + numpy (+ PIL for caption widths). Everything is a small pure function so it can be unit-tested (tests/).
Sections: transcript helpers | boundary checks (words or transcript segments) | audio metrics (ffmpeg) | captions (.ass) | title truth | duplicates | grade()."""
import difflib, glob, json, math, os, re, subprocess
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HYPE = re.compile(r"epic|wild|shock|insane|crazy|you won't believe|unbelievable|mind-?blow|exposed|leaked|teaser|reveal|surprise", re.I)   # same list as vod_long: titles must state only what happens
PROFANITY = re.compile(r"fuck|shit|bitch|nigg|fag|retard|cunt|dick|pussy|whore|slut", re.I)
def sh(c, **k): return subprocess.run(c, capture_output=True, text=True, **k)
# ---------------------------------------------------------------- transcript helpers
def load_segments(path):
    """jsonl of {"start","end","text"} (state/*/transcripts/<vod>.jsonl) -> sorted list; [] when missing"""
    if not path or not os.path.exists(path): return []
    out = []
    for l in open(path, encoding="utf-8"):
        try: d = json.loads(l)
        except Exception: continue
        if "start" in d and "end" in d: out.append(d)
    return sorted(out, key=lambda s: s["start"])
def window_text(segs, a, b):
    return " ".join(s.get("text", "") for s in segs if s["end"] > a and s["start"] < b)
def words_text(words, a=None, b=None):
    return " ".join(w["word"].strip() for w in words if (a is None or w["end"] > a) and (b is None or w["start"] < b))
def load_words(path):
    """words sidecar written by vod_shorts / vod_long: {"t0": absolute second of clip start, "words": [[start, end, word], ...]} (clip-relative seconds) -> [{"word","start","end"}]"""
    if not path or not os.path.exists(path): return []
    try: d = json.load(open(path, encoding="utf-8"))
    except Exception: return []
    return [{"word": w[2], "start": w[0], "end": w[1]} for w in d.get("words", [])]
def save_words(path, words, t0, ndigits=2):
    """words in absolute VOD seconds -> compact clip-relative sidecar (a few KB per Short, ~40 KB per 20 min)"""
    json.dump({"t0": round(t0, 2), "words": [[round(w["start"] - t0, ndigits), round(w["end"] - t0, ndigits), w["word"].strip()] for w in words]}, open(path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
# ---------------------------------------------------------------- boundary checks
SENT_END = re.compile(r"[.!?…]['\"”’)]*$")
def seg_boundary(t, segs, kind, tol=0.30, max_seg=20.0):
    """Where does cut point t (absolute seconds) fall relative to the transcript segments (Whisper sentences)?
    kind 'start' or 'end'. -> {"mid": bool (cuts through a reliable segment), "into_s": seconds into the segment, "sentence_ok": bool|None, "text": the segment}
    sentence_ok (start): the previous segment ends a sentence ([.?!]) or there is a >= 0.5 s gap before t; (end): the last segment before t ends with [.?!]. None = no transcript there."""
    near = [s for s in segs if s["start"] - 3 < t < s["end"] + 3]
    if not near: return {"mid": False, "into_s": 0.0, "sentence_ok": None, "text": ""}
    inside = next((s for s in near if s["start"] + tol < t < s["end"] - tol and s["end"] - s["start"] <= max_seg), None)
    if inside: return {"mid": True, "into_s": round(t - inside["start"], 2), "sentence_ok": False, "text": inside.get("text", "")}
    if kind == "start":
        prev = [s for s in segs if s["end"] <= t + tol]; p = prev[-1] if prev else None
        ok = None if p is None else bool(SENT_END.search(p.get("text", "").strip()) or t - p["end"] >= 0.5)
        nxt = next((s for s in segs if s["end"] > t), None); return {"mid": False, "into_s": 0.0, "sentence_ok": ok, "text": (nxt or {}).get("text", "")}
    prev = [s for s in segs if s["start"] < t - 0.05]; p = prev[-1] if prev else None
    return {"mid": False, "into_s": 0.0, "sentence_ok": None if p is None else bool(SENT_END.search(p.get("text", "").strip())), "text": (p or {}).get("text", "")}
def word_boundary(t, words, kind, margin=0.03):
    """cut point t against word timestamps: {"inside_word": bool, "gap": seconds to the neighbouring word (kind start: next word start - t; end: t - previous word end), "word": the word}"""
    inside = next((w for w in words if w["start"] + margin < t < w["end"] - margin), None)
    if inside: return {"inside_word": True, "gap": 0.0, "word": inside["word"].strip()}
    if kind == "start":
        n = next((w for w in sorted(words, key=lambda w: w["start"]) if w["start"] >= t - margin), None); return {"inside_word": False, "gap": round(n["start"] - t, 3) if n else None, "word": n["word"].strip() if n else ""}
    p = [w for w in sorted(words, key=lambda w: w["start"]) if w["end"] <= t + margin]; p = p[-1] if p else None
    return {"inside_word": False, "gap": round(t - p["end"], 3) if p else None, "word": p["word"].strip() if p else ""}
# ---------------------------------------------------------------- audio metrics
def duration(path):
    return float(sh(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path]).stdout.strip() or 0)
def audio_env(path, sr=8000, hop=0.01, start=None, dur=None):
    """10 ms RMS (dBFS) envelope of the audio track (optionally only [start, start+dur])"""
    cmd = ["ffmpeg", "-v", "error"] + (["-ss", f"{start:.3f}"] if start else []) + (["-t", f"{dur:.3f}"] if dur else []) + ["-i", path, "-vn", "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"]
    x = np.frombuffer(subprocess.run(cmd, capture_output=True).stdout, dtype=np.int16).astype(np.float32) / 32768.0; n = int(sr * hop); m = len(x) // n
    if m == 0: return np.full(1, -90.0), hop
    return 20 * np.log10(np.sqrt((x[:m * n].reshape(m, n) ** 2).mean(1) + 1e-10)), hop
def edge_metrics(env, hop, skip_head=0.0, skip_tail=0.0, thr_over=12.0, abs_floor=-52.0):
    """Leading / trailing dead air and abruptness of the cut, from a dB envelope.
    floor = 10th percentile of the whole clip; 'sound' = more than max(floor+thr_over, abs_floor) dB sustained 50 ms.
    lead_silence_s / trail_silence_s: time before the first / after the last sound; tail_rms_db: mean level of the last 200 ms; tail_over_floor: that level above the floor (a high value = the audio is chopped while loud);
    head_over_floor: same for the first 100 ms (the clip starts inside a loud sound); speech_db: 90th percentile level."""
    a = int(skip_head / hop); b = len(env) - int(skip_tail / hop); e = env[a:b] if b - a > 20 else env
    if len(e) < 20: return {}
    fl = float(np.percentile(e, 10)); thr = max(fl + thr_over, abs_floor); loud = e > thr; n = 5
    run = np.convolve(loud.astype(np.int8), np.ones(n, dtype=np.int8), mode="valid") >= n
    idx = np.nonzero(run)[0]
    if len(idx) == 0: return {"floor_db": round(fl, 1), "lead_silence_s": round(len(e) * hop, 2), "trail_silence_s": round(len(e) * hop, 2), "tail_rms_db": round(float(e[-20:].mean()), 1), "tail_over_floor": 0.0, "head_over_floor": 0.0, "speech_db": round(float(np.percentile(e, 90)), 1), "silent": True}
    lead = idx[0] * hop; trail = (len(e) - (idx[-1] + n)) * hop; tail = float(10 * np.log10((10 ** (e[-20:] / 10)).mean())); head = float(10 * np.log10((10 ** (e[:10] / 10)).mean()))
    return {"floor_db": round(fl, 1), "lead_silence_s": round(float(lead), 2), "trail_silence_s": round(float(trail), 2), "tail_rms_db": round(tail, 1), "tail_over_floor": round(tail - fl, 1), "head_over_floor": round(head - fl, 1), "speech_db": round(float(np.percentile(e, 90)), 1)}
def loudness(path, start=None, dur=None):
    """EBU R128 integrated loudness + true peak of the audio (ffmpeg ebur128) -> {"lufs", "tp"}"""
    cmd = ["ffmpeg", "-nostats", "-hide_banner"] + (["-ss", f"{start:.3f}"] if start else []) + (["-t", f"{dur:.3f}"] if dur else []) + ["-i", path, "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"]
    o = sh(cmd).stderr; lu = re.findall(r"I:\s+(-?[\d.]+) LUFS", o); pk = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", o)
    return {"lufs": float(lu[-1]) if lu else None, "tp": float(pk[-1]) if pk else None}
def silences(path, thr_db=-45, min_s=4.0):
    o = sh(["ffmpeg", "-nostats", "-hide_banner", "-i", path, "-vn", "-af", f"silencedetect=n={thr_db}dB:d={min_s}", "-f", "null", "-"]).stderr
    return [float(x) for x in re.findall(r"silence_duration: ([\d.]+)", o)]
def sync_metrics(path):
    """A/V sync from container data: stream durations and start times (a large difference = the picture and the sound drifted or one stream is cut earlier)"""
    o = sh(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,start_time,duration", "-of", "json", path]).stdout
    try: st = json.loads(o)["streams"]
    except Exception: return {}
    v = next((s for s in st if s.get("codec_type") == "video"), {}); a = next((s for s in st if s.get("codec_type") == "audio"), {})
    f = lambda d, k: float(d[k]) if d.get(k) not in (None, "N/A") else None
    vd, ad, vs, as_ = f(v, "duration"), f(a, "duration"), f(v, "start_time"), f(a, "start_time")
    return {"v_dur": vd, "a_dur": ad, "dur_diff_s": round(abs(vd - ad), 3) if vd is not None and ad is not None else None, "start_diff_s": round(abs((vs or 0) - (as_ or 0)), 3) if (vs is not None or as_ is not None) else None, "has_audio": bool(a), "has_video": bool(v)}
def audio_report(path, skip_head=0.0, skip_tail=0.0):
    """everything measurable from a finished media file (see edge_metrics / loudness / sync_metrics)"""
    env, hop = audio_env(path); d = duration(path); r = {"duration_s": round(d, 2)}
    r.update(edge_metrics(env, hop, skip_head, skip_tail)); r.update(loudness(path)); r["sync"] = sync_metrics(path); r["max_silence_s"] = max(silences(path), default=0.0)
    return r
# ---------------------------------------------------------------- captions (.ass)
def _font(path_hint=None, size=104):
    from PIL import ImageFont
    cands = [path_hint] if path_hint else []
    cands += glob.glob("/workspace/fonts/*.ttf") + glob.glob("/usr/share/fonts/truetype/sand-box/google/Heebo/*.ttf") + ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
    for c in cands:
        if c and os.path.exists(c):
            try:
                f = ImageFont.truetype(c, size)
                try: f.set_variation_by_name("Black")
                except Exception: pass
                return f
            except Exception: pass
    return ImageFont.load_default()
def _ass_time(s):
    h, m, sec = s.split(":"); return int(h) * 3600 + int(m) * 60 + float(sec)
def caption_report(ass_path, duration_s=None, max_lines=2):
    """Parses our burned-in .ass captions and measures the real rendered width with PIL: lines needed at the style's font size inside PlayResX - margins.
    -> {"n", "overflow": [{"t","text","lines","widest_px"}], "worst_px", "avail_px", "max_cps", "past_end": captions ending after the video, "overlap": simultaneous captions}. overflow = a single word wider than the box or more than max_lines lines."""
    if not ass_path or not os.path.exists(ass_path): return {}
    txt = open(ass_path, encoding="utf-8").read(); px = int((re.search(r"PlayResX:\s*(\d+)", txt) or [0, 1080])[1]); size = 104; ml = mr = 60
    m = re.search(r"^Style:\s*[^,]*,[^,]*,(\d+),(?:[^,]*,){10}\s*\d+,\s*\d+,\s*\d+,\s*\d+,\s*(\d+),\s*(\d+),\s*(\d+)", txt, re.M)
    m2 = re.search(r"^Style:\s*Cap,([^,]*),(\d+),.*?,(\d+),(\d+),(\d+),(\d+)\s*$", txt, re.M)   # Cap,font,size,...,Alignment,MarginL,MarginR,MarginV,Encoding
    if m2: size = int(m2.group(2)); ml, mr = int(m2.group(4)), int(m2.group(5))
    avail = px - ml - mr; font = _font(None, size); ev = []; overflow = []; worst = 0.0; max_cps = 0.0; past = 0
    for l in txt.splitlines():
        if not l.startswith("Dialogue:"): continue
        p = l.split(",", 9)
        if len(p) < 10: continue
        a, b = _ass_time(p[1]), _ass_time(p[2]); t = re.sub(r"\{[^}]*\}", "", p[9]).replace("\\N", " ").strip(); ev.append((a, b, t))
        words = t.split(); wl = [font.getlength(w) for w in words]; sp = font.getlength(" "); lines = 1; cur = 0.0
        for w in wl:
            if cur and cur + sp + w > avail: lines += 1; cur = w
            else: cur = cur + (sp if cur else 0) + w
        wide = max(wl, default=0.0); worst = max(worst, wide)
        if wide > avail or lines > max_lines: overflow.append({"t": round(a, 2), "text": t, "lines": lines, "widest_px": round(wide)})
        if b > a: max_cps = max(max_cps, len(t.replace(" ", "")) / (b - a))
        if duration_s and b > duration_s + 0.05: past += 1
    ov = sum(1 for (a, b, _), (a2, b2, _) in zip(ev, ev[1:]) if a2 < b - 0.05)
    return {"n": len(ev), "overflow": overflow, "worst_px": round(worst), "avail_px": avail, "max_cps": round(max_cps, 1), "past_end": past, "overlap": ov, "first_start": round(ev[0][0], 2) if ev else None, "last_end": round(ev[-1][1], 2) if ev else None}
# ---------------------------------------------------------------- title truth
EN_STOP = set("a an the of and or to in on at for with from by is are was were be been it its this that these those he she they his her their him them you your my our we i me as but not no so if then than too very just about into over out up down off after before again more most some any all both each few other such only own same can will would should could do does did done have has had having get got gets who whom what which when where why how also live stream clip clips moment moments video videos shorts short highlights highlight reaction reacts reacting watch watching full new first last one two".split())
HE_STOP = set("של על את עם אני אתה הוא היא הם הן זה זאת זו לא כן גם אבל או אם כי מה מי איך למה כל רק כמו אל מן עוד כבר היה היו יש אין הזה הזאת".split())
GENERIC = set("discusses discuss shares share talks talk talking meets reacts reaction highlights struggles struggle plans plan tells tell says say asks ask shows show explains explain gets goes comes makes takes".split())
def _norm(w): return re.sub(r"[’`]", "'", w.lower()).strip("'\"-.,!?:;()")
def tokens(text):
    return [_norm(t) for t in re.findall(r"[A-Za-z][A-Za-z'’\-]*|\d[\d,\.]*\d|\d|[\u0590-\u05FF]+(?:[\"'״׳][\u0590-\u05FF]+)?", text or "")]
def _stem(t):
    t = re.sub(r"'s$", "", t)
    if re.match(r"[\u0590-\u05FF]", t):
        t2 = t.replace('"', "").replace("'", "")
        return t2[1:5] if len(t2) > 4 and t2[0] in "הוכלבמש" else t2[:5]
    return t[:5] if len(t) >= 6 else t
def title_truth(title, text, ignore=()):
    """Which parts of a title are NOT supported by the transcript window `text`?
    -> {"missing_words": content words with no stem match, "missing_names": capitalised words/numbers (strong claims) with no fuzzy match, "bad_quotes": quoted strings that are not (mostly) in the transcript, "ratio": missing/checked, "checked": n}
    Names that are the streamer's own (ignore) and generic title verbs are not checked. A transcript is automatic (misspelled names): names use a fuzzy match (difflib >= 0.8)."""
    title = re.sub(r"#\w+", " ", title or ""); ign = {_norm(x) for x in ignore for x in re.split(r"[\s/]+", str(x)) if x}
    tt = tokens(text); tset = {_stem(t) for t in tt}; tfull = set(tt)
    bad_q = []
    for q in re.findall(r"[\"“”]([^\"“”]{3,})[\"“”]|(?:(?<=\s)|^)'([^']{4,})'(?=\s|$|[!?.,])", title):
        q = q[0] or q[1]; qt = [t for t in tokens(q) if t not in EN_STOP]
        if qt and sum(1 for t in qt if _stem(t) in tset) / len(qt) < 0.6: bad_q.append(q)
    pat = r"[A-Za-z][A-Za-z'’\-]*|\d[\d,\.]*\d|\d|[\u0590-\u05FF]+(?:[\"'״׳][\u0590-\u05FF]+)?"; words = []
    for m in re.finditer(pat, title):
        w = m.group(0); n = _norm(w)
        if n in ign or n in EN_STOP or n in HE_STOP or n in GENERIC or (len(n) < 3 and not n.isdigit()): continue
        cap = w[0].isupper() and m.start() > 0 and not title[:m.start()].rstrip().endswith(("-", "–", ":")) and not re.match(r"[A-Z]{2,}$", w)
        words.append((n, w, cap or n[0].isdigit()))
    missing, names = [], []; checked = 0
    for n, w, strong in words:
        checked += 1
        if _stem(n) in tset or n in tfull: continue
        if strong:
            close = difflib.get_close_matches(n, list(tfull), n=1, cutoff=0.8) if not n[0].isdigit() else []
            if close: continue
            if n[0].isdigit() and any(n.replace(",", "") == t.replace(",", "") for t in tfull): continue
            names.append(w)
        missing.append(w)
    return {"missing_words": missing, "missing_names": names, "bad_quotes": bad_q, "ratio": round(len(missing) / checked, 2) if checked else 0.0, "checked": checked}
def title_flags(title):
    f = []
    t = re.sub(r"#\w+", "", title or "").strip()
    if HYPE.search(t): f.append("hype word: " + HYPE.search(t).group(0))
    if PROFANITY.search(t): f.append("profanity in title")
    letters = [c for c in t if c.isalpha() and c.isascii()]
    if len(letters) > 12 and sum(c.isupper() for c in letters) / len(letters) > 0.6: f.append("ALL CAPS title")
    if len(t) > 100: f.append(f"title too long ({len(t)})")
    if len(t) < 15: f.append(f"title too short ({len(t)})")
    return f
# ---------------------------------------------------------------- duplicates
def overlap(a0, a1, b0, b1):
    """overlap of two ranges as a fraction of the SHORTER one"""
    o = min(a1, b1) - max(a0, b0); return max(0.0, o) / max(1e-6, min(a1 - a0, b1 - b0))
def find_duplicates(items, thr=0.5):
    """items = [{"id","vod","start","end","kind"}] -> [(id_a, id_b, overlap_fraction)] for the same VOD, same kind (short/long/clip), overlap >= thr"""
    out = []
    for i, a in enumerate(items):
        for b in items[i + 1:]:
            if a.get("vod") is None or str(a["vod"]) != str(b.get("vod")) or a.get("kind") != b.get("kind"): continue
            f = overlap(a["start"], a["end"], b["start"], b["end"])
            if f >= thr: out.append((a["id"], b["id"], round(f, 2)))
    return out
def existing_ranges(slug, vod, root=None, kinds=("shorts", "long")):
    """source ranges already produced for this VOD (state/<slug>/{shorts,long}/*.json) -> [{"id","kind","start","end"}]; used by the render scripts to refuse a duplicate"""
    out = []; root = root or ROOT
    for k in kinds:
        for f in glob.glob(os.path.join(root, "state", slug, k, "*.json")):
            if f.endswith(("uploaded.json", ".words.json")): continue
            try: s = json.load(open(f, encoding="utf-8")).get("source") or {}
            except Exception: continue
            if str(s.get("vod")) == str(vod) and s.get("start_s") is not None and s.get("end_s") is not None: out.append({"id": os.path.basename(f)[:-5], "kind": "short" if k == "shorts" else "long", "start": float(s["start_s"]), "end": float(s["end_s"])})
    return out
# ---------------------------------------------------------------- grade
THRESH = {"lead_max": 0.7, "trail_max": 0.9, "tail_loud_db": 22.0, "head_loud_db": 22.0, "short_lufs": (-14.0, 2.0), "long_lufs": (-16.0, 5.0), "sync_max": 0.35, "max_silence": 8.0}
def grade(path, kind="short", title=None, words=None, window_text_=None, ass=None, skip_head=0.0, ignore_names=(), audio=None, expected_dur=None):
    """Grade a finished draft. kind: 'short' | 'long'. -> {"fail": [reasons that must block the upload], "warn": [...], "metrics": {...}, "score": 0-100}
    sync (stream durations / start times / expected duration), cut cleanliness (dead air at both ends, chopped audio at the end, start inside a loud sound, word cut when words are given),
    loudness vs target, captions (overflow), title truth (words/names/quotes not in the transcript). Never raises: a measurement that cannot be taken is just left out."""
    fail, warn, m = [], [], {}
    try:
        a = audio if audio is not None else audio_report(path, skip_head=skip_head); m["audio"] = a; sy = a.get("sync") or {}
        if not sy.get("has_audio", True): fail.append("no audio stream")
        if sy.get("dur_diff_s") is not None and sy["dur_diff_s"] > THRESH["sync_max"]: fail.append(f"A/V duration differ by {sy['dur_diff_s']:.2f}s (sync)")
        if sy.get("start_diff_s") is not None and sy["start_diff_s"] > 0.15: warn.append(f"A/V start offset {sy['start_diff_s']:.2f}s")
        if expected_dur and abs(a.get("duration_s", 0) - expected_dur) > 1.5: fail.append(f"duration {a.get('duration_s')}s, expected {expected_dur:.1f}s")
        if a.get("silent"): fail.append("audio is silent")
        if a.get("lead_silence_s", 0) > THRESH["lead_max"]: (fail if a["lead_silence_s"] > 1.5 else warn).append(f"leading dead air {a['lead_silence_s']:.2f}s")
        if a.get("trail_silence_s", 0) > THRESH["trail_max"]: (fail if a["trail_silence_s"] > 2.0 else warn).append(f"trailing dead air {a['trail_silence_s']:.2f}s")
        if a.get("tail_over_floor", 0) > THRESH["tail_loud_db"]: warn.append(f"audio ends abruptly (last 200 ms is {a['tail_over_floor']:.0f} dB over the floor)")
        if a.get("head_over_floor", 0) > THRESH["head_loud_db"]: warn.append(f"clip starts inside a loud sound ({a['head_over_floor']:.0f} dB over the floor)")
        tg, tol = THRESH["short_lufs" if kind == "short" else "long_lufs"]
        if a.get("lufs") is not None:
            if abs(a["lufs"] - tg) > tol: (fail if (a["lufs"] < -26 or a["lufs"] > -8) else warn).append(f"loudness {a['lufs']:.1f} LUFS vs target {tg:.0f}")
        if a.get("tp") is not None and a["tp"] > 0.0: warn.append(f"true peak {a['tp']:.1f} dBFS (clipping)")
        if a.get("max_silence_s", 0) >= THRESH["max_silence"]: fail.append(f"silence of {a['max_silence_s']:.0f}s inside the video")
    except Exception as e: m["audio_error"] = str(e)[:120]
    if words:
        try:
            d = m.get("audio", {}).get("duration_s") or duration(path); ws = [w for w in words if w["end"] > -0.5 and w["start"] < d + 0.5]
            if ws:
                sb = word_boundary(0.0 + skip_head, ws, "start"); eb = word_boundary(d, ws, "end"); m["start_word"] = sb; m["end_word"] = eb
                if sb["inside_word"]: fail.append(f"starts inside the word '{sb['word']}'")
                if eb["inside_word"]: fail.append(f"ends inside the word '{eb['word']}'")
                if sb["gap"] is not None and sb["gap"] > 0.9: warn.append(f"first word comes {sb['gap']:.2f}s after the start")
                if eb["gap"] is not None and eb["gap"] > 1.2: warn.append(f"last word ends {eb['gap']:.2f}s before the end")
        except Exception as e: m["words_error"] = str(e)[:120]
    if ass:
        try:
            c = caption_report(ass, m.get("audio", {}).get("duration_s")); m["captions"] = {k: c.get(k) for k in ("n", "worst_px", "avail_px", "max_cps", "past_end", "overlap")} | {"overflow": len(c.get("overflow", []))}
            if c.get("overflow"): (fail if len(c["overflow"]) >= 3 else warn).append(f"{len(c['overflow'])} caption(s) overflow the frame (widest {c['worst_px']}px of {c['avail_px']}px)")
            if c.get("past_end"): warn.append(f"{c['past_end']} caption(s) end after the video")
            if c.get("overlap", 0) > 2: warn.append(f"{c['overlap']} overlapping captions")
        except Exception as e: m["captions_error"] = str(e)[:120]
    if title is not None:
        tf = title_flags(title); warn += tf; m["title_flags"] = tf
        if window_text_ and len(window_text_.split()) >= 25:
            tt = title_truth(title, window_text_, ignore_names); m["title_truth"] = tt
            if tt["bad_quotes"]: fail.append("quoted text in the title is not in the transcript: " + "; ".join(tt["bad_quotes"])[:80])
            if len(tt["missing_names"]) >= 2: fail.append("names/numbers in the title never occur in the transcript: " + ", ".join(tt["missing_names"])[:80])
            elif tt["missing_names"]: warn.append("name/number not in the transcript: " + ", ".join(tt["missing_names"]))
            if tt["checked"] >= 4 and tt["ratio"] > 0.6: warn.append(f"{int(tt['ratio'] * 100)}% of the title's words are not in the transcript")
    score = max(0, 100 - 25 * len(fail) - 6 * len(warn))
    return {"fail": fail, "warn": warn, "metrics": m, "score": score}

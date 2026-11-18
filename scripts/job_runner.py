#!/usr/bin/env python3
"""ONE customer job, start to finish, on a local machine: SOURCE -> moments -> 9:16 drafts (+ optional long video) -> QA grade. Never uploads anything.
Run by scripts/render_worker.py as a subprocess (own memory, killable on timeout); can also be run by hand:
    job_runner.py --job job.json --workdir /work/j_ab12 [--demo]
    job_runner.py --make-demo-media out.mp4 [--seconds 150]        (synthetic test video, no network)
job.json = what POST /studio/worker/claim returns: {"id","org","channel","kind","source":{type,ref,...},"style_id","outputs":{"shorts":5,"long":true},"hints":{mood,text,profile?,language?,slug?,display?}}
Protocol on stdout (one line each, the supervisor forwards them to the API):  PROGRESS {"progress":40,"msg":"found_moments","vars":{"n":5}}  |  RESULT <path to result.json>  |  ERROR {"code":..,"message":..}
Exit codes: 0 ok | 3 source problem the customer can fix (bad link, no audio, too short ...) | 4 nothing worth clipping | 1 crash.
What is reused from the owner's pipeline: styles.py (signature style) + style_render.py (ffmpeg render), cutsnap.py (sentence/energy snapped cut points), cutqa.py (QA gate: qa_fail),
vod_shorts.py (whisper/LLM helpers, imported lazily and only when keys exist), customer_profile.py (banned words/topics, preferences, examples; optional).
Defaults for CUSTOMERS differ from the owner's channels on purpose: no ClipGlobe watermark / bumper, language from the customer profile, private drafts only."""
import argparse, json, os, re, subprocess, sys, tempfile, time, traceback

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "stations"))
import numpy as np
import worker_sources as WS

DEMO_WORDS = "this is a demo moment from the test stream and it gets loud right here wow".split()


class NoMoments(Exception):
    pass


def sh(cmd, timeout=None, **kw): return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, **kw)
def mmss(t): return "%d:%02d" % (int(t // 60), int(t % 60))


class Reporter:
    """prints PROGRESS lines; msg is a key of MSG in app/studio.js (found_moments, rendering, ...) or free text via message="""
    def __init__(self, out=None): self.out = out or sys.stdout; self.last = 0
    def __call__(self, progress=None, msg=None, vars=None, message=None):
        d = {}
        if progress is not None: self.last = max(self.last, int(progress)); d["progress"] = self.last
        if msg: d["msg"] = msg; d["vars"] = vars or {}
        elif message: d["message"] = str(message)[:120]
        print("PROGRESS " + json.dumps(d, ensure_ascii=False), file=self.out, flush=True)


# ---------------------------------------------------------------- config / profile / style
def cfg_from_env(env=None):
    e = os.environ if env is None else env
    flag = lambda k, d="0": str(e.get(k, d)).strip().lower() in ("1", "true", "yes", "on")
    return {"demo": flag("WORKER_DEMO"), "upload_dir": e.get("UPLOAD_DIR", ""), "ingest_dir": e.get("INGEST_DIR", ""),
            "media_roots": [x for x in e.get("WORKER_MEDIA_ROOTS", "").split(os.pathsep) if x] or None, "allow_any_path": flag("WORKER_ALLOW_ANY_PATH"),
            "blocked_hosts": [x for x in e.get("WORKER_BLOCK_HOSTS", "kick.com").split(",") if x.strip()], "trusted_orgs": [x.strip() for x in e.get("WORKER_TRUSTED_ORGS", "").split(",") if x.strip()],
            "max_source_h": float(e.get("WORKER_MAX_SOURCE_H", "8") or 8), "download_timeout": int(e.get("WORKER_DOWNLOAD_TIMEOUT_S", "3600") or 3600),
            "no_cloud": flag("WORKER_NO_CLOUD"), "keep_watermark": flag("WORKER_WATERMARK"), "profiles_dir": e.get("CUSTOMER_PROFILES_DIR", ""), "whisper_model": e.get("WORKER_WHISPER_MODEL", ""),
            "whisper_threads": int(e.get("WORKER_WHISPER_THREADS", "0") or 0),
            "platform_vod": flag("WORKER_PLATFORM_VOD"), "trust_guests": flag("WORKER_TRUST_GUESTS"), "download_max_min": float(e.get("WORKER_DOWNLOAD_MAX_MIN", "0") or 0), "download_height": int(e.get("WORKER_DOWNLOAD_HEIGHT", "1080") or 1080)}   # preview phase (GitHub runner): trusted orgs may use "my last stream" from Kick/Twitch; downloads capped in length and height


def load_profile(job, cfg):
    """customer profile (scripts/customer_profile.py, optional): job.hints.profile, else <CUSTOMER_PROFILES_DIR>/<org>/profile.json, else env CUSTOMER_PROFILE. Returns (module|None, profile|None). Never raises."""
    try: import customer_profile as CP
    except Exception: return None, None
    prof = (job.get("hints") or {}).get("profile")
    if not isinstance(prof, dict):
        prof = None
        for p in (os.path.join(cfg.get("profiles_dir") or "", re.sub(r"[^A-Za-z0-9_-]", "", str(job.get("org") or "")), "profile.json") if cfg.get("profiles_dir") else "", os.environ.get("CUSTOMER_PROFILE") or ""):
            try:
                if p and os.path.isfile(p): prof = json.load(open(p, encoding="utf-8")); break
            except Exception: continue
    if not isinstance(prof, dict): return CP, None
    try:
        norm = CP.normalize_profile(prof)
        if prof.get("language") not in ("he", "en"): norm["language"] = None   # normalize_profile defaults to "he"; only an explicit choice of the customer may switch the speech language
        return CP, norm
    except Exception: return CP, None


def customer_style(job, profile, cfg):
    """the signature style, adjusted for a customer: no owner watermark/bumper, language and clip length from the profile. Returns the resolved shorts parameter dict."""
    import styles as S
    sid = str((job.get("style_id") or "signature"))
    try: S.load_raw(sid)
    except Exception: sid = "signature"
    ov = {"intro": {"bumper_s": 0}}
    if not cfg.get("keep_watermark"): ov["watermark"] = {"enabled": False}
    lang = (profile or {}).get("language") or (job.get("hints") or {}).get("language")
    if lang in ("he", "en"): ov["language"] = {"code": lang, "name": "Hebrew" if lang == "he" else "English"}
    pr = (profile or {}).get("preferences") or {}
    pace = {}
    if pr.get("min_len_s"): pace["min_clip_s"] = max(5, min(170, pr["min_len_s"]))
    if pr.get("max_len_s"): pace["max_clip_s"] = max(10, min(180, pr["max_len_s"]))
    if pace: ov["pace"] = pace
    return S.resolve({"extends": sid, "name": "customer-" + sid, "shorts": ov}, "shorts")


# ---------------------------------------------------------------- audio -> words -> signals
def extract_audio(src, t0, dur, out, timeout=600):
    r = sh(["ffmpeg", "-v", "error", "-y", "-ss", "%.1f" % t0, "-t", "%.1f" % dur, "-i", src, "-vn", "-ac", "1", "-ar", "16000", "-c:a", "libmp3lame", "-b:a", "48k", out], timeout=timeout)
    return r.returncode == 0 and os.path.exists(out)


def energy_per_second(mp3):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", mp3, "-f", "s16le", "-ac", "1", "-ar", "8000", "-"], capture_output=True, timeout=600).stdout
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32); n = len(x) // 8000
    return list(np.sqrt((x[:n * 8000].reshape(n, 8000) ** 2).mean(1)) + 1e-3) if n else []


def energy_transcriber(mp3, lang="en"):
    """DEMO transcriber (no model, no network): voiced stretches of the audio become placeholder words (about 3 per second). Good enough to exercise cutting, captions and QA end to end; the words are NOT real speech."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", mp3, "-f", "s16le", "-ac", "1", "-ar", "8000", "-"], capture_output=True, timeout=300).stdout
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    hop = 400; n = len(x) // hop
    if n < 4: return []
    db = 20 * np.log10(np.sqrt((x[:n * hop].reshape(n, hop) ** 2).mean(1)) + 1e-3); thr = max(float(np.percentile(db, 10)) + 14, 20.0)
    voiced = db > thr; words, i, k = [], 0, 0
    while i < n:
        if not voiced[i]: i += 1; continue
        j = i
        while j < n and (voiced[j] or (j + 3 < n and voiced[j:j + 4].any())): j += 1   # a gap shorter than 0.2 s stays inside the same stretch
        a, b = i * hop / 8000, j * hop / 8000
        if b - a >= 0.2:
            t = a
            while t + 0.2 <= b:
                words.append({"word": " " + DEMO_WORDS[k % len(DEMO_WORDS)], "start": round(t, 3), "end": round(min(t + 0.28, b), 3)}); k += 1; t += 0.34
        i = j + 1
    return words


_WM = {}
def local_whisper(mp3, lang="en", cfg=None):
    """faster-whisper on the CPU (no quota, no network once the model is cached). Hebrew uses the ivrit-ai model, other languages large-v3-turbo; WORKER_WHISPER_MODEL overrides."""
    cfg = cfg or {}
    from faster_whisper import WhisperModel
    name = cfg.get("whisper_model") or ("ivrit-ai/whisper-large-v3-turbo-ct2" if lang == "he" else "deepdml/faster-whisper-large-v3-turbo-ct2")
    if name not in _WM: _WM[name] = WhisperModel(name, device="cpu", compute_type="int8", cpu_threads=cfg.get("whisper_threads") or os.cpu_count() or 4)
    segs, _ = _WM[name].transcribe(mp3, language=lang, beam_size=1, word_timestamps=True, vad_filter=True, vad_parameters={"min_silence_duration_ms": 500, "threshold": 0.35}, condition_on_previous_text=False)
    return [{"word": w.word, "start": w.start, "end": w.end} for sg in segs for w in (sg.words or [])]


def make_transcriber(cfg, lang):
    """-> callable(mp3_path) -> [{"word","start","end"}] (times relative to the chunk). demo: energy stub. Groq whisper when GROQ_API_KEY is set (and cloud is allowed), always with the local model as fallback."""
    if cfg.get("demo"): return lambda p: energy_transcriber(p, lang)
    use_groq = bool(os.environ.get("GROQ_API_KEY")) and not cfg.get("no_cloud")
    def run(p):
        if use_groq:
            try:
                import vod_shorts as V
                w = V.whisper(p, lang)   # itself falls back to a local model when Groq answers nothing
                if w: return w
            except Exception as e: print("groq path failed, local whisper:", str(e)[:120], flush=True)
        return local_whisper(p, lang, cfg)
    return run


def make_llm(cfg):
    """-> callable(prompt) -> dict|None, or None when no key is configured / demo / cloud disabled (the heuristic picker is used then)."""
    if cfg.get("demo") or cfg.get("no_cloud"): return None
    if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GROQ_API_KEY")): return None
    import vod_shorts as V
    return V.llm


def rz(s, k=600):
    z = np.zeros(len(s))
    for i in range(0, len(s), 60):
        seg = s[max(0, i - k):i + k]; med = np.median(seg); mad = np.median(np.abs(seg - med)) + 1e-6; z[i:i + 60] = (s[i:i + 60] - med) / (1.4826 * mad)
    return np.clip(z, -3, 6)


def score_series(energy, words, t0, dur):
    """per-second 'excitement' signal S = smoothed robust z of log audio energy (0.6) and words per second (0.4) (same recipe as vod_shorts.py)"""
    N = max(1, int(dur)); e = np.zeros(N); e[:min(N, len(energy))] = np.array(energy[:N]); wps = np.zeros(N)
    for w in words:
        i = int(w["start"] - t0)
        if 0 <= i < N: wps[i] += 1
    return np.convolve(0.6 * rz(np.log(e + 1e-3)) + 0.4 * rz(wps), np.ones(5) / 5, mode="same")


def pick_peaks(S, n_max, thr=0.9, sep=60):
    peaks = []
    for i in np.argsort(-S):
        if S[i] < thr: break
        if all(abs(int(i) - p) >= sep for p in peaks): peaks.append(int(i))
        if len(peaks) >= n_max: break
    return peaks


# ---------------------------------------------------------------- moment judging
def heuristic_pick(pk, words, S, lead=10.0, tail=12.0, lang="en"):
    """no LLM: window around the peak, title from the first words said there. Flagged so the customer knows it was not judged by a model."""
    ws = [w for w in words if pk - lead <= w["start"] <= pk + tail]
    first = " ".join(w["word"].strip() for w in ws[:7]).strip(" ,.-")
    hook = " ".join(w["word"].strip() for w in ws[:3]).strip(" ,.-")
    title = (first[:60] + ("..." if len(first) > 60 else "")) if first else ("Highlight at %s" % mmss(pk))
    return {"score": 6.5, "start": pk - lead, "end": pk + tail, "title": title, "hook": hook[:30], "reject": False, "why": "audio/speech peak (no LLM review)", "kind": "highlight", "picker": "heuristic"}


def llm_prompt(pk, txt, PC, hints, profile, CP, lang_name):
    mood = (hints or {}).get("mood"); ask = (hints or {}).get("text")
    extra = ""
    if mood: extra += "The customer wants mostly %s moments. " % mood
    if ask: extra += "The customer asked: %s. " % re.sub(r"[\r\n]+", " ", str(ask))[:200]
    if CP and profile:
        try: extra += "\n" + CP.prompt_additions(profile, query=txt[:1500]) + "\n"
        except Exception: pass
    return ("You edit YouTube Shorts from a live stream. Below: words with [second] for the window around an audio/speech peak at second %d. Decide if it is a clip-worthy moment (%s). " % (pk, PC["moments"]["criteria"].replace("%", "%%")) + extra +
            "REJECT (reject=true) gambling/casino/giveaway/promo-code talk, sponsored reads, slurs, sexual content, self-harm, minors, or random chatter. Return JSON only: "
            "{\"score\":1-10,\"start\":second where the SETUP sentence starts (8-%d s before the peak, a sentence start),\"end\":second where the PAYOFF sentence ends,\"title\":\"%s YouTube Shorts title 40-70 chars, hook first, only facts that are said in the clip, ends with ! or ?\",\"hook\":\"%s word on-screen text\",\"kind\":\"funny|hype|fail|story|other\",\"reject\":false,\"why\":\"\"}\n\n%s" % (int(PC["pace"]["max_leadin_s"]), lang_name, PC["hook"]["words"], txt)).replace("%%", "%")


def judge(pk, words, S, PC, hints, profile, CP, llm, lang_name):
    """-> pick dict or None (rejected)"""
    ws = [w for w in words if pk - 45 <= w["start"] <= pk + 20]
    if llm is None:
        return heuristic_pick(pk, words, S, lang=PC["language"]["code"]) if len(ws) >= 6 else None
    if len(ws) < 15: return None
    txt = " ".join("[%d]%s" % (w["start"], w["word"].strip()) for w in ws)[:5500]
    j = llm(llm_prompt(pk, txt, PC, hints, profile, CP, lang_name))
    if not j or j.get("reject") or float(j.get("score", 0)) < float(PC["pace"]["min_llm_score"]): return None
    j["picker"] = "llm"; return j


# ---------------------------------------------------------------- the job
def run_job(job, workdir, cfg=None, emit=None, deps=None):
    """returns the result dict (also written to <workdir>/result.json). deps: {"llm":fn|None, "transcribe":fn} override the defaults (tests)."""
    cfg = cfg or cfg_from_env(); emit = emit or Reporter(); deps = deps or {}
    import cutsnap as CS, cutqa as Q, style_render as SR, styles as S
    os.makedirs(workdir, exist_ok=True); out_dir = os.path.join(workdir, "drafts"); os.makedirs(out_dir, exist_ok=True)
    outputs = job.get("outputs") or {}; n_short = max(0, min(30, int(outputs.get("shorts") if outputs.get("shorts") is not None else 5))); want_long = bool(outputs.get("long"))
    hints = job.get("hints") or {}; CP, profile = load_profile(job, cfg); ST = customer_style(job, profile, cfg)
    LANG, LANGN = ST["language"]["code"], ST["language"]["name"]
    MINC, MAXC, TARC, LEAD = float(ST["pace"]["min_clip_s"]), float(ST["pace"]["max_clip_s"]), float(ST["pace"]["target_clip_s"]), float(ST["pace"]["max_leadin_s"])
    t_start = time.time(); timing = {}

    # 1. source
    emit(2, "downloading")
    scfg = dict(cfg); scfg["trusted"] = str(job.get("org")) in set(cfg.get("trusted_orgs") or []) or bool(cfg.get("trust_guests") and job.get("org_guest"))   # preview phase: guest workspaces (the owner testing) may use Kick/Twitch links
    src = WS.resolve_source(job, os.path.join(workdir, "src"), scfg)
    if not src["has_video"]: raise WS.SourceError("no_video", "the source has no video track")
    media, dur = src["path"], src["duration_s"]; timing["source_s"] = round(time.time() - t_start, 1)
    print("source: %s %.1f min (%s)" % (src["kind"], dur / 60, src["title"]), flush=True)

    # 2. words + energy, 10-minute chunks
    transcribe = deps.get("transcribe") or make_transcriber(cfg, LANG); llm = deps["llm"] if "llm" in deps else make_llm(cfg)
    tmp = tempfile.mkdtemp(prefix="chunks_", dir=workdir); words, en = [], []; chunk = 600; nchunks = max(1, int(np.ceil(dur / chunk)))
    for ci in range(nchunks):
        c0 = ci * chunk; d = min(chunk, dur - c0)
        if d < 1: break
        mp3 = os.path.join(tmp, "a%d.mp3" % ci)
        if not extract_audio(media, c0, d, mp3): print("audio chunk %d failed, skipped" % ci, flush=True); en += [1e-3] * int(d); continue
        for w in transcribe(mp3): words.append({"word": w["word"], "start": c0 + w["start"], "end": c0 + w["end"]})
        e = energy_per_second(mp3); en += e + [1e-3] * max(0, int(d) - len(e))
        try: os.remove(mp3)
        except OSError: pass
        emit(8 + 50 * (ci + 1) / nchunks, "transcribing", {"pct": int(100 * (ci + 1) / nchunks)})
    timing["asr_s"] = round(time.time() - t_start - timing["source_s"], 1)
    if len(words) < 8: raise NoMoments("not enough speech found (%d words)" % len(words))

    # 3. peaks -> judged candidates
    Sx = score_series(en, words, 0.0, dur); peaks = pick_peaks(Sx, max(n_short, 1) * 4 + (2 if want_long else 0), 0.9)
    if len(peaks) < max(1, n_short): peaks = pick_peaks(Sx, max(n_short, 1) * 4, 0.3)   # quiet streams: lower the bar instead of returning nothing
    cands = []
    for pk in peaks:
        j = judge(pk, words, Sx, ST, hints, profile, CP, llm, LANGN)
        if j: cands.append((float(j.get("score", 6)) + float(Sx[pk]) / 3, pk, j))
    cands.sort(reverse=True)
    emit(62, "found_moments", {"n": min(len(cands), n_short) if n_short else len(cands)})
    drafts, made = [], []
    prev_ranges = []

    # 4. cut + render + QA, one short at a time
    for sc, pk, j in cands:
        if len(made) >= n_short: break
        emit(62 + 30 * len(made) / max(1, n_short), "rendering", {"i": len(made) + 1, "n": n_short})
        try:
            d_ = build_short(media, dur, words, pk, j, sc, ST, MINC, MAXC, TARC, LEAD, out_dir, workdir, prev_ranges, job, profile, CP, src, lang=LANG, cfg=cfg)
        except Exception as ex:
            print("short skipped (%s): %s" % (type(ex).__name__, str(ex)[:160]), flush=True); continue
        if d_: drafts.append(d_); made.append(d_); prev_ranges.append((d_["start_s"], d_["end_s"]))

    # 5. optional long video
    if want_long:
        try:
            emit(94, message="Preparing the long video..." if LANG != "he" else "מכינים את הסרטון הארוך...")
            ld = build_long(media, dur, words, Sx, ST, out_dir, job, profile, CP, llm, LANGN, LANG, src)
            if ld: drafts.append(ld)
            else: print("long video skipped (source too short or no clean window)", flush=True)
        except Exception as ex: print("long video failed (%s): %s" % (type(ex).__name__, str(ex)[:160]), flush=True)

    emit(97, "qa")
    if not drafts: raise NoMoments("no clip-worthy moment found")
    timing["total_s"] = round(time.time() - t_start, 1)
    res = {"job": job.get("id"), "source": {"kind": src["kind"], "duration_s": round(dur, 1), "title": src["title"]}, "drafts": drafts, "timing": timing, "style": S.name_of({"name": "customer-signature"}), "picker": "llm" if llm else "heuristic",
           "profile_applied": bool(profile), "language": LANG}
    json.dump(res, open(os.path.join(workdir, "result.json"), "w"), ensure_ascii=False, indent=1)
    try:
        import shutil; shutil.rmtree(tmp, ignore_errors=True); shutil.rmtree(os.path.join(workdir, "body"), ignore_errors=True)
    except Exception: pass
    return res


def build_short(media, dur, words, pk, j, sc, ST, MINC, MAXC, TARC, LEAD, out_dir, workdir, prev, job, profile, CP, src, lang="en", cfg=None):
    import cutsnap as CS, cutqa as Q, style_render as SR
    try: s = float(j["start"]); e_ = float(j["end"])
    except Exception: return None
    s = max(0.0, max(s, pk - LEAD)); e_ = max(e_, pk + 3)
    try:
        s_al, e_al, ainfo = CS.align_span(s, e_, words, MINC + 0.5, MAXC - 3); s0 = s_al - 0.2; e0 = e_al + 0.45
    except Exception:
        e_ = min(e_, s + (MAXC - 1)); s0 = max([w["start"] for w in words if w["start"] <= s], default=s) - 0.2; e0 = min([w["end"] for w in words if w["end"] >= e_], default=e_) + 0.45
        if e0 - s0 < MINC: e0 = s0 + TARC
    s0 = max(0.0, s0); e0 = min(dur - 0.05, e0)
    if not (MINC - 1 <= e0 - s0 <= MAXC) or any(Q.overlap(s0, e0, x, y) >= 0.3 for x, y in prev): print("rejected (length or duplicate)", round(s0), round(e0), flush=True); return None
    cw = [w for w in words if w["end"] > s0 and w["start"] < e0]; text = " ".join(w["word"].strip() for w in cw)
    title = re.sub(r"\s+([!?])", r"\1", str(j.get("title") or "").strip())[:90]; hook = str(j.get("hook") or "")
    desc = (title + "\n\n" + (job.get("hints") or {}).get("description_tail", "")).strip()
    verdict = {"verdict": "ok", "reasons": []}
    if CP and profile:
        try: verdict = CP.screen_candidate(profile, title=title, description=desc, text=text, kind=str(j.get("kind") or ""), duration_s=e0 - s0)
        except Exception as ex: print("profile screen failed:", str(ex)[:100], flush=True)
    if verdict["verdict"] == "block": print("blocked by the customer profile:", verdict["reasons"], flush=True); return None
    # title truth gate (only meaningful for an LLM-written title; a heuristic title is made of the clip's own words)
    tok = True
    if j.get("picker") == "llm":
        try:
            import vod_shorts as V
            title, _tt, tok = V.truthful_title(title, cw, [str((job.get("hints") or {}).get("display") or "")], "", "%s YouTube Shorts title, 40-70 chars, hook first, ends with ! or ?" % ST["language"]["name"], "", str((job.get("hints") or {}).get("display") or ""))
        except Exception as ex: print("title truth gate skipped:", str(ex)[:100], flush=True)
    bdir = os.path.join(workdir, "body"); os.makedirs(bdir, exist_ok=True); pad = 2.0; bt0 = max(0.0, s0 - pad); body = os.path.join(bdir, "b%d.mp4" % int(s0))
    r = sh(["ffmpeg", "-v", "error", "-y", "-ss", "%.2f" % bt0, "-t", "%.2f" % (e0 - bt0 + pad), "-i", media, "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "aac", "-b:a", "192k", body], timeout=900)
    if r.returncode: raise RuntimeError("cut failed: " + r.stderr[-200:])
    try:   # refine in/out points with the real audio energy of the body (Whisper word times are only good to ~100-300 ms)
        env, hop = CS.energy_db(body); wi = [w for w in words if s0 - 0.05 <= w["start"] <= e0 + 0.05]
        if wi:
            s1 = CS.snap_start(wi[0]["start"], words, env, hop, bt0); e1 = CS.snap_end(min(wi[-1]["end"], wi[-1]["start"] + 1.4), words, env, hop, bt0)
            if MINC - 2 <= e1 - s1 <= MAXC + 1: s0, e0 = s1, e1
    except Exception as ex: print("cutsnap skipped:", str(ex)[:100], flush=True)
    rel = [{"word": w["word"], "start": w["start"] - bt0, "end": w["end"] - bt0} for w in words if bt0 <= w["start"] <= e0 + pad]
    base = "short_%d" % int(s0); ass = os.path.join(out_dir, base + ".ass"); mp4 = os.path.join(out_dir, base + ".mp4")
    cuts = SR.dead_air_cuts(body, s0 - bt0, e0 - bt0, rel, ST["pace"]); SR.shorts_captions(ST, rel, s0 - bt0, e0 - bt0, ass, hook, cuts)
    if not SR.render_shorts(body, s0 - bt0, e0 - bt0, ass, mp4, hook, pk - bt0, ST): raise RuntimeError("render failed")
    Q.save_words(mp4[:-4] + ".words.json", cw, s0)
    g = Q.grade(mp4, "short", title=title, words=[{"word": w["word"], "start": w["start"] - s0, "end": w["end"] - s0} for w in cw], window_text_=Q.words_text(cw), ass=ass,
                ignore_names=[str((job.get("hints") or {}).get("display") or "")], extra_text="")
    fail = list(g["fail"]) + ([] if tok else ["title not supported by the transcript (rewrite failed)"]); warn = list(g["warn"]) + list(verdict.get("reasons") or [])
    if verdict["verdict"] == "warn": fail.append("customer profile: " + "; ".join(verdict["reasons"])[:150])
    if j.get("picker") == "heuristic": warn.append("moment chosen by audio peaks only (no AI review)")
    meta = {"title": title + (" #Shorts" if "#shorts" not in title.lower() else ""), "description": desc + "\n#Shorts", "tags": [], "categoryId": "24", "lang": lang, "privacy": "private", "hook": hook, "kind": "short",
            "source": {"kind": src["kind"], "start_s": round(s0, 2), "end_s": round(e0, 2), "peak_s": round(pk, 1)}, "score": round(sc, 1), "why": j.get("why", ""), "picker": j.get("picker"),
            "qa": {"score": g["score"], "fail": fail, "warn": warn}, "qa_fail": bool(fail)}
    json.dump(meta, open(mp4[:-4] + ".json", "w"), ensure_ascii=False, indent=1)
    print("SHORT %s-%s (%.0fs) qa=%s fail=%s | %s" % (mmss(s0), mmss(e0), e0 - s0, g["score"], fail, title), flush=True)
    return {"kind": "short", "title": meta["title"], "file": os.path.relpath(mp4, workdir), "meta_file": os.path.relpath(mp4[:-4] + ".json", workdir), "qa_ok": not fail, "qa_score": g["score"], "qa_notes": "; ".join(fail + warn)[:300],
            "duration_s": round(e0 - s0, 1), "start_s": round(s0, 2), "end_s": round(e0, 2), "hook": hook}


def build_long(media, dur, words, Sx, ST, out_dir, job, profile, CP, llm, lang_name, lang, src):
    """a continuous long video (6-15 min) around the strongest stretch of the source. Needs a source of at least 10 minutes. Same QA gate."""
    import cutsnap as CS, cutqa as Q
    if dur < 600: return None
    L = float(min(900, max(360, dur * 0.2))); step = 30; best = None
    for a in range(0, int(max(1, dur - L)) + 1, step):
        v = float(np.maximum(Sx[a:a + int(L)], 0).sum())
        if best is None or v > best[0]: best = (v, a)
    a = float(best[1]); b = min(dur, a + L)
    try:
        s0 = CS.sentence_start_near(a, CS._ws(words), 15.0, 15.0) or a; e0 = CS.sentence_end_near(b, CS._ws(words), 15.0, 15.0) or b
    except Exception: s0, e0 = a, b
    s0 = max(0.0, s0 - 0.2); e0 = min(dur, e0 + 0.45)
    cw = [w for w in words if s0 <= w["start"] <= e0]; text = " ".join(w["word"].strip() for w in cw)
    title = ""; description = ""
    if llm is not None and len(cw) > 40:
        j = llm("Write a %s YouTube title (<=70 chars, only facts that are said) and a 2-sentence description for this stream segment. Return JSON {\"title\":\"\",\"description\":\"\"}.\n\n%s" % (lang_name, text[:6000]))
        if isinstance(j, dict): title = str(j.get("title") or "").strip()[:90]; description = str(j.get("description") or "").strip()[:800]
    if not title: title = (" ".join(w["word"].strip() for w in cw[:8]).strip(" ,.-") or "Stream highlights")[:70]
    verdict = {"verdict": "ok", "reasons": []}
    if CP and profile:
        try: verdict = CP.screen_candidate(profile, title=title, description=description, text=text, kind="long", duration_s=e0 - s0)
        except Exception: pass
    if verdict["verdict"] == "block": print("long blocked by the customer profile:", verdict["reasons"], flush=True); return None
    mp4 = os.path.join(out_dir, "long_%d.mp4" % int(s0))
    r = sh(["ffmpeg", "-v", "error", "-y", "-ss", "%.2f" % s0, "-t", "%.2f" % (e0 - s0), "-i", media, "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", mp4], timeout=3600)
    if r.returncode: raise RuntimeError("long encode failed: " + r.stderr[-200:])
    g = Q.grade(mp4, "long", title=title, words=[{"word": w["word"], "start": w["start"] - s0, "end": w["end"] - s0} for w in cw], window_text_=Q.words_text(cw), expected_dur=e0 - s0)
    fail = list(g["fail"]); warn = list(g["warn"]) + list(verdict.get("reasons") or [])
    if verdict["verdict"] == "warn": fail.append("customer profile: " + "; ".join(verdict["reasons"])[:150])
    meta = {"title": title, "description": description or title, "tags": [], "categoryId": "24", "lang": lang, "privacy": "private", "kind": "long", "source": {"kind": src["kind"], "start_s": round(s0, 2), "end_s": round(e0, 2)},
            "qa": {"score": g["score"], "fail": fail, "warn": warn}, "qa_fail": bool(fail)}
    json.dump(meta, open(mp4[:-4] + ".json", "w"), ensure_ascii=False, indent=1)
    return {"kind": "long", "title": title, "file": os.path.relpath(mp4, os.path.dirname(out_dir)), "meta_file": os.path.relpath(mp4[:-4] + ".json", os.path.dirname(out_dir)), "qa_ok": not fail, "qa_score": g["score"], "qa_notes": "; ".join(fail + warn)[:300],
            "duration_s": round(e0 - s0, 1), "start_s": round(s0, 2), "end_s": round(e0, 2), "hook": ""}


# ---------------------------------------------------------------- demo media
def make_demo_media(path, seconds=150, seed=3):
    """synthetic 1280x720 test video with speech-like audio: sentences with pauses, three louder/denser 'moments'. No network. Returns the path."""
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import synth
    rng = np.random.default_rng(seed); wl, t = [], 2.0; peaks = [int(seconds * f) for f in (0.25, 0.55, 0.8)]; loud = []
    while t < seconds - 4:
        n = int(rng.integers(5, 11)); near = any(abs(t - p) < 4 for p in peaks); sent, t_end = synth.sentence(t, n + (6 if near else 0), wlen=0.22 if near else 0.3, gap=0.05 if near else 0.1)
        wl += sent; loud.append((t, t_end, near)); t = t_end + float(rng.uniform(0.8, 1.6))
    x = synth.make_speech([(a, b) for a, b in wl], seconds, level_db=-30.0, seed=seed)
    for a, b, near in loud:
        if near: i, k = int(a * synth.SR), int(b * synth.SR); x[i:k] *= 3.2
    tmp = tempfile.mkdtemp(prefix="demo_"); wav = os.path.join(tmp, "a.wav"); synth.write_wav(wav, np.clip(x, -1, 1))
    r = sh(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=1280x720:r=30:d=%d" % seconds, "-i", wav, "-c:v", "libx264", "-preset", "veryfast", "-crf", "28", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k", "-shortest", path], timeout=600)
    if r.returncode: raise RuntimeError("demo media failed: " + r.stderr[-200:])
    return path


# ---------------------------------------------------------------- CLI
def main(argv=None):
    ap = argparse.ArgumentParser(description="run one customer job locally (never uploads)")
    ap.add_argument("--job"); ap.add_argument("--workdir"); ap.add_argument("--demo", action="store_true"); ap.add_argument("--make-demo-media"); ap.add_argument("--seconds", type=int, default=150)
    a = ap.parse_args(argv)
    if a.make_demo_media: print(make_demo_media(a.make_demo_media, a.seconds)); return 0
    if not a.job or not a.workdir: ap.error("--job and --workdir are required")
    job = json.load(open(a.job, encoding="utf-8")); cfg = cfg_from_env()
    if a.demo: cfg["demo"] = True; cfg["allow_any_path"] = True
    try:
        res = run_job(job, a.workdir, cfg)
        print("RESULT " + os.path.join(a.workdir, "result.json"), flush=True); return 0
    except WS.SourceError as e:
        print("ERROR " + json.dumps({"code": e.code, "message": str(e)[:200]}), flush=True); return 3
    except NoMoments as e:
        print("ERROR " + json.dumps({"code": "no_moments", "message": str(e)[:200]}), flush=True); return 4
    except Exception as e:
        traceback.print_exc(); print("ERROR " + json.dumps({"code": "crash", "message": (type(e).__name__ + ": " + str(e))[:200]}), flush=True); return 1


if __name__ == "__main__": sys.exit(main())

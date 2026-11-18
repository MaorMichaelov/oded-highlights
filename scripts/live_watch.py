#!/usr/bin/env python3
"""Check whether the channel is live; if so ingest the new audio of the running VOD
(Kick keeps the in-progress VOD as a growing HLS EVENT playlist) and transcribe it with Groq.
Writes: state/live_status.json, state/ingest_state.json, state/transcripts/<vod_id>.jsonl
Only plain `curl` + public JSON endpoints are used. No cookies/tokens for Kick.
"""
import json, os, subprocess, sys, time, tempfile, shutil
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import statefile as SF   # atomic state writes, idempotent transcript appends
CHANNEL = os.environ.get("CHANNEL", "odedsvr")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / os.environ.get("STATE_DIR", "state"); (STATE / "transcripts").mkdir(parents=True, exist_ok=True)
QUALITY = os.environ.get("AUDIO_QUALITY", "480p30")   # measured: 160p audio=51 kbps (bad transcripts), 480p/720p=102 kbps (clearly better)
MAX_SEGS_PER_RUN = int(os.environ.get("MAX_SEGS_PER_RUN", "36"))   # ~6 min of stream per run: progress is committed every few minutes, a restart never loses much   # ~15 min of audio per run (Groq free: 7200 audio-sec/hour)
GROQ_KEY = os.environ.get("GROQ_API_KEY", "")
ASR_LANG = os.environ.get("ASR_LANG", "he")   # "he" | "en" | any Whisper code | "auto" = detect the spoken language from the first windows of each stream and lock it (stored in ingest_state: _lang, per-VOD lang)
ASR = os.environ.get("ASR", "ivrit")          # ivrit = ivrit-ai/whisper-large-v3-turbo-ct2 on CPU (RTF ~0.4 on a 4-vCPU runner, no daily quota); groq = fallback
HE_MODEL, MULTI_MODEL = "ivrit-ai/whisper-large-v3-turbo-ct2", "deepdml/faster-whisper-large-v3-turbo-ct2"
_models = {}; DETECTED = (None, 0.0)   # (language, probability) of the last auto-detection
def _get_model(name):
    if name not in _models:
        from faster_whisper import WhisperModel
        _models.clear(); _models[name] = WhisperModel(name, device="cpu", compute_type="int8", cpu_threads=os.cpu_count() or 4)   # one model in RAM at a time (4-vCPU / 16 GB runner)
    return _models[name]
def ivrit_transcribe(mp3, lang=None):
    """returns [(start,end,text)] relative to the file, or None if the engine is unavailable. lang: code, or None/"auto" = detect (multilingual model; Hebrew is re-run with the ivrit model)."""
    global DETECTED
    try:
        auto = lang in (None, "auto"); he = (lang == "he")
        m = _get_model(HE_MODEL if he else MULTI_MODEL)
        segs, info = m.transcribe(str(mp3), language=None if auto else lang, beam_size=1, vad_filter=True, vad_parameters={"min_silence_duration_ms": 500, "threshold": 0.35},
                                    condition_on_previous_text=False, no_speech_threshold=0.5, compression_ratio_threshold=2.2, hallucination_silence_threshold=2.0,
                                    initial_prompt=("עודד, ביגי, עמית שיבר, סנסיי, רונן, אוהד, קיק, סטרימר, פוקימון" if he else None))
        if auto:
            DETECTED = (getattr(info, "language", None), float(getattr(info, "language_probability", 0) or 0))
            if DETECTED[0] == "he" and DETECTED[1] >= 0.5: return ivrit_transcribe(mp3, "he")   # Hebrew: the fine-tuned model is much better than the generic one
        out = []
        for sg in segs:
            t = sg.text.strip()
            if not t or (t in ("תודה רבה.", "תודה רבה", "תודה.") and (sg.end - sg.start) < 3.5): continue
            out.append((sg.start, sg.end, t))
        if he: DETECTED = ("he", 1.0)
        return out
    except Exception as e:
        print("ivrit engine unavailable:", repr(e)[:200]); return None

def curl(url, out=None, timeout=40):
    cmd = ["curl", "-sS", "-A", UA, "-H", "Accept: application/json", "-m", str(timeout), "-w", "%{http_code}", "-o", out or "-", url]
    r = subprocess.run(cmd, capture_output=True)
    body = r.stdout if not out else b""
    code = (r.stdout[-3:] if not out else r.stdout).decode(errors="ignore")[-3:]
    if not out: body = r.stdout[:-3]
    return code, body

def jget(url):
    code, body = curl(url)
    if code != "200": return code, None
    try: return code, json.loads(body)
    except Exception: return code, None

def load(p, default):
    return SF.read_json(p, default)   # a corrupt file is quarantined (<name>.corrupt-<ts>) and reported, not silently replaced by the default

def main():
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    code, ch = jget(f"https://kick.com/api/v2/channels/{CHANNEL}")
    status = {"checked_at": now, "http": code}
    if ch is None:
        status["live"] = None; status["note"] = "channel api not reachable"
        SF.write_json(STATE / "live_status.json", status); print("status:", status); return 0
    ls = ch.get("livestream")
    if os.environ.get("FORCE_VOD") and not ls: ls = {"session_title": "TEST", "viewer_count": 0}
    status["live"] = bool(ls)
    if ls: status.update({"title": ls.get("session_title"), "viewers": ls.get("viewer_count"), "started": ls.get("created_at") or ls.get("start_time"), "category": (ls.get("categories") or [{}])[0].get("name")})
    SF.write_json(STATE / "live_status.json", status); print("status:", status)
    if ls:                                                         # category/title timeline (used to detect "entered GTA 6")
        cf = STATE / "category.jsonl"; last = None
        if cf.exists():
            try: last = json.loads(cf.read_text().strip().splitlines()[-1])
            except Exception: last = None
        cur_c = {"cat": status.get("category"), "title": status.get("title")}
        if not last or (last.get("cat"), last.get("title")) != (cur_c["cat"], cur_c["title"]):
            with open(cf, "a", encoding="utf-8") as fh: fh.write(json.dumps({"t": int(time.time()), **cur_c, "viewers": status.get("viewers")}, ensure_ascii=False) + "\n")
    if not ls or os.environ.get("LIVE_STATUS_ONLY"): return 0   # status-only call: lets the loop publish "he is live" immediately, before the slow transcription
    # newest VOD = the running stream
    code, vids = jget(f"https://kick.com/api/v2/channels/{CHANNEL}/videos")
    if not vids: print("videos list unavailable", code); return 0
    if os.environ.get("FORCE_VOD"): v = vids[int(os.environ["FORCE_VOD"])]
    else:   # the VOD of the CURRENT live: same id as the livestream; right after the stream starts Kick may still list only older VODs: then wait (never ingest an old stream)
        lid = str(ls.get("id")); v = next((x for x in vids if str(x["id"]) == lid), None)
        if v is None:
            try:
                import calendar; t0 = calendar.timegm(time.strptime((ls.get("start_time") or ls.get("created_at") or "")[:19], "%Y-%m-%d %H:%M:%S"))
                v = next((x for x in vids if abs(calendar.timegm(time.strptime((x.get("start_time") or "")[:19], "%Y-%m-%d %H:%M:%S")) - t0) < 900), None)
            except Exception: v = None
        if v is None: print("live VOD not listed yet (newest listed:", vids[0].get("id"), ") - waiting"); return 0
    vid = str(v["id"]); src = v.get("source")
    if not src: print("no source yet"); return 0
    base = src.rsplit("/master.m3u8", 1)[0]
    code, pl = curl(f"{base}/{QUALITY}/playlist.m3u8")
    if code != "200": print("playlist http", code); return 0
    segs = []; cum = 0.0; d = None
    for l in pl.decode().splitlines():
        if l.startswith("#EXTINF:"): d = float(l[8:].split(",")[0])
        elif l and not l.startswith("#") and d is not None: segs.append((l, cum, d)); cum += d; d = None
    st = load(STATE / "ingest_state.json", {})
    cur = st.get(vid)
    if cur is None:
        cur = {"next_seg": int(os.environ.get("START_SEG", "0"))}
        tp = STATE / "transcripts" / f"{vid}.jsonl"
        if tp.exists() and not os.environ.get("START_SEG"):   # state lost/corrupt but the transcript is there: resume after its last row instead of re-transcribing the whole stream
            rws = SF.read_jsonl(str(tp)); last_end = max((r.get("end", 0) for r in rws), default=0)
            if last_end > 0: cur["next_seg"] = next((n for n, (_, c0, d0) in enumerate(segs) if c0 + d0 > last_end + 1), 0); print(f"resume point recovered from the transcript: seg {cur['next_seg']} (last row at {last_end:.0f} s)")
    i0 = cur["next_seg"]; new = segs[i0:i0 + MAX_SEGS_PER_RUN]
    # leave the last 2 segments (may still be growing)
    if i0 + len(new) >= len(segs): new = new[:-2] if len(new) > 2 else []
    print(f"vod {vid}: total segs {len(segs)}, ingesting {len(new)} from {i0}")
    if not new or (not GROQ_KEY and ASR != "ivrit"):
        if not GROQ_KEY and ASR != "ivrit": print("GROQ_API_KEY not set: skipping transcription")
        st[vid] = cur; st["_current_vod"] = vid; SF.write_json(STATE / "ingest_state.json", st); return 0
    if not shutil.which("ffmpeg"):
        subprocess.run("sudo apt-get update -qq && sudo apt-get install -y -qq ffmpeg", shell=True, check=False)
    tmp = Path(tempfile.mkdtemp())
    try:
        # transcribe in ~5 min windows
        for k in range(0, len(new), 30):
            win = new[k:k + 30]; files = []
            for name, s, dd in win:
                f = tmp / name
                for _try in range(2):   # one retry: a missing segment is a hole in the transcript
                    curl(f"{base}/{QUALITY}/{name}", out=str(f))
                    if f.exists() and f.stat().st_size > 500: break
                    time.sleep(2)
                files.append(f)
            lst = tmp / "l.txt"; lst.write_text("".join(f"file '{f}'\n" for f in files if f.exists() and f.stat().st_size > 500))
            mp3 = tmp / "w.mp3"
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-vn", "-ac", "1", "-ar", "16000", "-b:a", "32k", str(mp3)])
            if not mp3.exists(): print("audio failed"); break
            off = win[0][1]; rows = None
            wl = cur.get("lang") or ("auto" if ASR_LANG == "auto" else ASR_LANG)
            if ASR == "ivrit": rows = ivrit_transcribe(mp3, wl)
            if wl == "auto" and DETECTED[0] and DETECTED[1] >= 0.6: cur["lang"] = DETECTED[0]; st["_lang"] = DETECTED[0]; print("language detected and locked:", DETECTED)
            if rows is None and GROQ_KEY:
                r = subprocess.run(["curl", "-sS", "-m", "180", "https://api.groq.com/openai/v1/audio/transcriptions", "-H", f"Authorization: Bearer {GROQ_KEY}", "-F", "model=whisper-large-v3", *(["-F", "language=" + wl] if wl != "auto" else []), "-F", "response_format=verbose_json", "-F", f"file=@{mp3}"], capture_output=True, text=True)
                try: j = json.loads(r.stdout)
                except Exception: print("bad groq response"); break
                if "error" in j: print("groq error:", j["error"].get("message", "")[:120]); break
                rows = [(sg["start"], sg["end"], sg["text"].strip()) for sg in j.get("segments", [])]
            if rows is None: print("no ASR engine available"); break
            tpath = str(STATE / "transcripts" / f"{vid}.jsonl")
            dropped = SF.truncate_jsonl_from(tpath, "start", off - 0.01)   # idempotent: a window that was already (partly) written by a run that died before saving its progress REPLACES its rows instead of duplicating them
            if dropped: print(f"re-ingest of window at {off:.0f}s: replaced {dropped} earlier row(s)")
            with open(tpath, "a", encoding="utf-8") as fh:
                for (a0, a1, tx) in rows:
                    fh.write(json.dumps({"start": round(a0 + off, 2), "end": round(a1 + off, 2), "text": tx}, ensure_ascii=False) + "\n")
                fh.flush(); os.fsync(fh.fileno())
            cur["next_seg"] = i0 + k + len(win); st[vid] = cur; st["_current_vod"] = vid; SF.write_json(STATE / "ingest_state.json", st)   # progress saved after EVERY window (a kill loses at most one window)
            mp3.unlink(missing_ok=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    cur["last_run"] = now; st[vid] = cur; st["_current_vod"] = vid
    st["_vod_base"] = base; st["_behind_segs"] = max(0, len(segs) - 2 - cur["next_seg"])   # how far transcription lags behind the live edge
    try:
        import calendar; st["_vod_start_epoch"] = calendar.timegm(time.strptime((v.get("start_time") or "")[:19], "%Y-%m-%d %H:%M:%S"))
    except Exception: pass
    SF.write_json(STATE / "ingest_state.json", st)
    print("ingested up to seg", cur["next_seg"], "of", len(segs))
    return 0

if __name__ == "__main__": sys.exit(main())

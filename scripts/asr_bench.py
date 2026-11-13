#!/usr/bin/env python3
"""Benchmark ivrit-ai faster-whisper speed on a GitHub runner. usage: asr_bench.py BASE_URL FIRST_SEG LAST_SEG [quality]"""
import subprocess, sys, time, os, json
base, a, b = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]); q = sys.argv[4] if len(sys.argv) > 4 else "480p30"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
os.makedirs("bench", exist_ok=True); lst = []
for n in range(a, b + 1):
    f = f"bench/{n}.ts"; subprocess.run(["curl", "-sS", "-A", UA, "-m", "60", "-o", f, f"{base}/{q}/{n}.ts"]); lst.append(f"file '{os.path.abspath(f)}'\n")
open("bench/l.txt", "w").write("".join(lst))
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", "bench/l.txt", "-vn", "-ac", "1", "-ar", "16000", "bench/a.wav"], check=True)
dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", "bench/a.wav"], capture_output=True, text=True).stdout)
from faster_whisper import WhisperModel
print("cpus:", os.cpu_count(), "| audio sec:", round(dur), flush=True)
for ctype, beam in (("int8", 1), ("int8", 5)):
    t0 = time.time(); m = WhisperModel("ivrit-ai/whisper-large-v3-turbo-ct2", device="cpu", compute_type=ctype, cpu_threads=os.cpu_count())
    tl = time.time() - t0; t1 = time.time()
    segs, info = m.transcribe("bench/a.wav", language="he", beam_size=beam, vad_filter=True, vad_parameters={"min_silence_duration_ms": 500}, condition_on_previous_text=False, word_timestamps=True)
    out = [(s.start, s.end, s.text.strip()) for s in segs]; tt = time.time() - t1
    print(f"RESULT compute={ctype} beam={beam}: load {tl:.0f}s, transcribe {tt:.0f}s for {dur:.0f}s audio -> RTF {tt/dur:.2f}", flush=True)
    if beam == 1:
        for s in out[:25]: print(f"  {s[0]:6.1f} {s[2]}")

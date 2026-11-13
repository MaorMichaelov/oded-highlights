#!/usr/bin/env python3
"""Transcribe a short clip with faster-whisper small, language=he. Prints timing."""
import argparse
import sys
import time
from pathlib import Path

from faster_whisper import WhisperModel


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("audio", type=Path)
    p.add_argument("--model", default="small")
    p.add_argument("--language", default="he")
    p.add_argument("--device", default="cpu")
    p.add_argument("--compute-type", default="int8")
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args()
    if not args.audio.is_file():
        print(f"ERROR: file not found: {args.audio}", file=sys.stderr)
        return 1

    t0 = time.perf_counter()
    print(f"loading model={args.model} device={args.device} compute_type={args.compute_type}", flush=True)
    model = WhisperModel(args.model, device=args.device, compute_type=args.compute_type)
    t_load = time.perf_counter() - t0
    print(f"model_load_sec={t_load:.2f}", flush=True)

    t1 = time.perf_counter()
    segments, info = model.transcribe(
        str(args.audio),
        language=args.language,
        vad_filter=True,
        beam_size=5,
    )
    rows = []
    for seg in segments:
        line = f"[{seg.start:7.2f} -> {seg.end:7.2f}] {seg.text.strip()}"
        print(line, flush=True)
        rows.append(line)
    t_x = time.perf_counter() - t1
    dur = float(info.duration or 0.0)
    print(f"detected_language={info.language} language_probability={info.language_probability}")
    print(f"audio_duration_sec={dur:.2f}")
    print(f"transcribe_sec={t_x:.2f}")
    if dur:
        print(f"realtime_factor={t_x/dur:.3f}  (lower than 1.0 means faster than realtime)")
    print(f"total_sec={time.perf_counter()-t0:.2f}")
    print(f"segments={len(rows)}")
    out = args.out or args.audio.with_suffix(".he.txt")
    out.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Post-process a finished Oded long clip BEFORE upload to ODED HIGHLIGHTS.

Why this exists
---------------
The live watcher (PID of watcher.sh, plus process_segment.py --watch) imports
ready_queue -> cut_clip in-process. Those modules are already in memory for
the 2026-11-11 session, so editing cut_clip.py does not affect clips cut
*today*. The upload routine must run this script on every new ready/*.json
(or the mp4 it points at) before uploading.

What it does
------------
1. 8s cold-open hook from the loudest window (edit_long.enhance_long)
2. ~2.6s ODED HIGHLIGHTS intro (logo + "הרגעים הכי טובים של עודד" + whoosh SFX)
3. Like/sub bubble with the ODED HIGHLIGHTS logo (~3–8s into the body), same SFX-free overlay as Ronen, green accent
4. Up to 2 punch-in zooms on loud reactions
5. Optional thumbnail via make_thumb.py (Oded face left, guest/object right)

Idempotent: skips enhance if the JSON already has "enhanced": true.
Never writes into ready/*.mp4 (JSON only lives there). Never deletes the
pre-enhance file: the enhanced mp4 is written next to the original and the
JSON "path" is updated to it ("path_pre_enhance" keeps the original).

Usage
-----
  /workspace/kick_clipper/venv/bin/python enhance_ready.py ready/FOO.json
  /workspace/kick_clipper/venv/bin/python enhance_ready.py ready/FOO.json \\
      --thumb --oded angry_hands --subject path.png \\
      --text '*שווה*|את זה?!' --circle x0,y0,x1,y1
  /workspace/kick_clipper/venv/bin/python enhance_ready.py SRC.mp4 --out DEST.mp4
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from edit_long import enhance_long, _ffprobe_dur  # noqa: E402

HERE = Path(__file__).resolve().parent
VENV_PY = HERE / "venv" / "bin" / "python"
# rembg / scipy live on the system interpreter, not the kick venv
THUMB_PY = os.environ.get("ODED_THUMB_PY", "/usr/bin/python3")
MAKE_THUMB = HERE / "make_thumb.py"


def _load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def _save_json(p: Path, rec: dict) -> None:
    p.write_text(json.dumps(rec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def already_enhanced(rec: dict, src: Path) -> bool:
    if rec.get("enhanced") is True:
        return True
    info = rec.get("enhance_info") or {}
    if info.get("intro_sec") or info.get("hook"):
        return True
    # path already points at an _enhanced.mp4 produced by a previous run
    if src.name.endswith("_enhanced.mp4") and src.is_file() and src.stat().st_size > 10_000:
        return True
    return False


def enhance_mp4(src: Path, dest: Path, **kwargs) -> dict:
    dest.parent.mkdir(parents=True, exist_ok=True)
    info = enhance_long(src, dest, **kwargs)
    return info


def make_thumb(out: Path, *, oded: str, text: str, subject: str | None,
               subject_height: int, circle: str | None, bg: str,
               style: str, oded_height: int) -> dict:
    cmd = [
        THUMB_PY, str(MAKE_THUMB),
        "--oded", oded,
        "--oded-height", str(oded_height),
        "--text", text,
        "--style", style,
        "--out", str(out),
    ]
    if bg:
        cmd += ["--bg", bg]
    if subject:
        cmd += ["--subject", subject, "--subject-height", str(subject_height)]
    if circle:
        cmd += ["--circle", circle]
    r = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return {"cmd": cmd, "stdout": (r.stdout or "").strip(), "path": str(out)}


def process_json(js: Path, args) -> dict:
    rec = _load_json(js)
    src = Path(rec["path"])
    if not src.is_file():
        raise SystemExit(f"clip missing: {src}")

    report: dict = {"json": str(js), "src": str(src)}

    if already_enhanced(rec, src) and not args.force:
        report["enhance"] = "skipped_already_enhanced"
        dest = src
    else:
        dest = src.with_name(src.stem + "_enhanced.mp4")
        if dest.resolve() == src.resolve():
            dest = src.with_name(src.stem + "_v2.mp4")
        info = enhance_mp4(
            src, dest,
            hook=not args.no_hook,
            brand=not args.no_brand,
            zooms=not args.no_zooms,
            captions=args.captions,
            hook_start=args.hook_start,
            hook_dur=args.hook_dur,
        )
        rec["path_pre_enhance"] = str(src)
        rec["path"] = str(dest)
        rec["duration"] = round(float(info.get("out_duration") or _ffprobe_dur(dest)), 3)
        rec["enhanced"] = True
        rec["enhanced_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
        rec["enhance_info"] = {
            "hook": info.get("hook"),
            "intro_sec": info.get("intro_sec"),
            "zooms_in_body": info.get("zooms_in_body"),
            "out_duration": info.get("out_duration"),
            "branding": "ODED HIGHLIGHTS",
        }
        _save_json(js, rec)
        report["enhance"] = info
        report["dest"] = str(dest)

    if args.thumb:
        if not args.text:
            raise SystemExit("--thumb requires --text (e.g. '*שווה*|את זה?!')")
        thumb_out = Path(args.thumb_out) if args.thumb_out else js.with_name(js.stem + "_thumb.jpg")
        # never write the sample into ready/ unless the json already lives there
        tinfo = make_thumb(
            thumb_out,
            oded=args.oded,
            text=args.text,
            subject=args.subject,
            subject_height=args.subject_height,
            circle=args.circle,
            bg=args.bg,
            style=args.style,
            oded_height=args.oded_height,
        )
        rec = _load_json(js)
        rec["thumbnail"] = str(thumb_out)
        rec["thumbnail_320"] = str(Path(str(thumb_out)).with_name(Path(thumb_out).stem + "_320.png"))
        _save_json(js, rec)
        report["thumbnail"] = tinfo

    return report


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("src", type=Path, help="ready/*.json or an mp4")
    p.add_argument("--out", type=Path, default=None, help="required when src is an mp4; ignored for json (writes *_enhanced.mp4)")
    p.add_argument("--force", action="store_true", help="re-enhance even if JSON says enhanced")
    p.add_argument("--no-hook", action="store_true")
    p.add_argument("--no-brand", action="store_true")
    p.add_argument("--no-zooms", action="store_true")
    p.add_argument("--captions", action="store_true")
    p.add_argument("--hook-start", type=float, default=None)
    p.add_argument("--hook-dur", type=float, default=8.0)
    p.add_argument("--thumb", action="store_true")
    p.add_argument("--thumb-out", type=Path, default=None)
    p.add_argument("--oded", default="angry_hands")
    p.add_argument("--oded-height", type=int, default=720)
    p.add_argument("--subject", default=None)
    p.add_argument("--subject-height", type=int, default=700)
    p.add_argument("--text", default=None)
    p.add_argument("--circle", default=None)
    p.add_argument("--bg", default="")
    p.add_argument("--style", default="stroke", choices=["stroke", "boxes"])
    args = p.parse_args()

    src = args.src
    if src.suffix.lower() == ".json":
        report = process_json(src, args)
    else:
        if args.out is None:
            raise SystemExit("mp4 input requires --out (put samples in ready_samples/, never ready/)")
        if args.out.resolve().parent.resolve() == (HERE / "ready").resolve() and args.out.suffix.lower() == ".mp4":
            raise SystemExit(f"refusing to write an mp4 into ready/: {args.out}")
        info = enhance_mp4(
            src, args.out,
            hook=not args.no_hook,
            brand=not args.no_brand,
            zooms=not args.no_zooms,
            captions=args.captions,
            hook_start=args.hook_start,
            hook_dur=args.hook_dur,
        )
        report = {"src": str(src), "dest": str(args.out), "enhance": info}
        if args.thumb:
            if not args.text:
                raise SystemExit("--thumb requires --text")
            thumb_out = args.thumb_out or args.out.with_name(args.out.stem + "_thumb.jpg")
            report["thumbnail"] = make_thumb(
                thumb_out,
                oded=args.oded,
                text=args.text,
                subject=args.subject,
                subject_height=args.subject_height,
                circle=args.circle,
                bg=args.bg,
                style=args.style,
                oded_height=args.oded_height,
            )
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""EDITING STYLE PROFILES: the parameters that make one edit look different from another (pace, captions, zoom, sfx, music, intro, loudness, layout, hook, language).
A style is a JSON file config/styles/<name>.json:  {"name":..., "extends":"default", "shorts":{section:{key:value}}, "long":{...}}.  Only the keys that differ from the base need to be written.
Resolution order for every parameter:  code DEFAULTS (= the behaviour of the pipeline before styles existed)  <-  the chosen style (its "extends" chain first). The product ships ONE style, config/styles/signature.json.
Without a style the pipeline keeps its original code path untouched. With signature (= the same values spelled out) it goes through scripts/style_render.py, which builds the identical ffmpeg commands (checked by scripts/test_styles.py).
Select a style:  env STYLE=<name>  or  --style <name>  (vod_shorts.py / vod_long.py);  or a path to a .json file (e.g. one made by scripts/style_from_video.py).
CLI:  styles.py list | show <name> [shorts|long] | validate [name...] | schema  (schema writes config/styles/_schema.json)
Library: resolve(name_or_dict_or_None, "shorts"|"long") -> full parameter dict;  make_ass(words, s, e, path, caption_params, W, H, ...) ;  hex_to_ass('#FFC107') -> '&H0007C1FF'"""
import copy, json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); STYLE_DIR = os.path.join(ROOT, "config", "styles")
NA = "__NA__"   # the parameter does not exist for that format
# (path, type, shorts default, long default, constraint, description)   types: int float bool str color enum strlist
# Defaults here reproduce EXACTLY what scripts/vod_shorts.py (render2 + station make_ass + amber colour swap) and scripts/vod_long.py did before styles.
_T = [
 ("language.code", "str", "en", "en", None, "speech language of the stream (Whisper language code: en, he, es ...)"),
 ("language.name", "str", "English", "English", None, "language name written into the LLM prompts (titles, hooks, descriptions)"),
 ("pace.min_clip_s", "float", 20, NA, (5, 180), "Shorts: shortest clip that is accepted (s)"),
 ("pace.max_clip_s", "float", 59, NA, (10, 180), "Shorts: longest clip that is accepted (s); YouTube Shorts allow up to 3 min, 59 is the safe classic"),
 ("pace.target_clip_s", "float", 24, NA, (5, 180), "Shorts: a too-short pick is extended with lead-in context up to about this length (s)"),
 ("pace.max_leadin_s", "float", 25, NA, (3, 90), "Shorts: setup/lead-in before the peak is searched up to this many seconds"),
 ("pace.min_llm_score", "float", 6, NA, (1, 10), "Shorts: minimum LLM moment score (1-10) to render a candidate"),
 ("pace.dead_air_trim_s", "float", 0, 0, (0, 30), "jump-cut pace: silences longer than this many seconds are cut out (0 = off, nothing is cut)"),
 ("pace.keep_pause_s", "float", 0.35, 0.35, (0.05, 2), "how much of a cut pause is kept so speech does not run together (s)"),
 ("pace.silence_db", "float", -42, -42, (-70, -20), "below this level (dB) the audio counts as silence"),
 ("moments.criteria", "str", "funny, shocking, dramatic, a story with a punchline", NA, None, "Shorts: what the LLM looks for in a moment (free text, goes into the prompt)"),
 ("layout.aspect", "enum", "9:16", NA, ["9:16", "1:1", "4:5", "16:9"], "Shorts: output aspect ratio (1080 px wide; 16:9 = 1920x1080)"),
 ("layout.mode", "enum", "blur_fill", NA, ["blur_fill", "crop_fill", "bars"], "Shorts: how the 16:9 stream fills the frame: blurred copy behind it / centre-crop that fills the frame / solid colour bars"),
 ("layout.fg_fit", "enum", "width", NA, ["width", "contain"], "blur_fill/bars: stream is scaled to the frame width (classic) or to fit inside the frame (contain)"),
 ("layout.blur_radius", "int", 28, NA, (0, 80), "blur_fill: box blur radius of the background"),
 ("layout.blur_power", "int", 4, NA, (1, 8), "blur_fill: blur passes"),
 ("layout.bg_brightness", "float", -0.12, NA, (-1, 1), "blur_fill: background brightness offset"),
 ("layout.bg_color", "color", "#000000", NA, None, "bars: bar colour"),
 ("layout.crop_x", "float", 0.5, NA, (0, 1), "crop_fill: horizontal focus of the crop (0 left, 0.5 centre, 1 right: e.g. where the streamer's face-cam is)"),
 ("captions.enabled", "bool", True, False, None, "burn captions into the video (long videos: off in the classic style)"),
 ("captions.font", "str", "Heebo Black", "Heebo Black", None, "font family name (fonts in assets/fonts and the system: Heebo Black, Anton, Bangers, Bebas Neue, Montserrat)"),
 ("captions.size", "int", 104, 56, (16, 220), "font size in px on the 1080 px wide (Shorts) or 1920x1080 (long) canvas"),
 ("captions.color", "color", "#FFC107", "#FFFFFF", None, "text colour"),
 ("captions.highlight_color", "color", "#FFC107", "#FFC107", None, "colour of the active word when animation = karaoke"),
 ("captions.outline_color", "color", "#000000", "#000000", None, "outline colour"),
 ("captions.outline_px", "float", 9, 4, (0, 30), "outline width"),
 ("captions.shadow_px", "float", 3, 1, (0, 20), "shadow depth"),
 ("captions.align", "enum", 2, 2, [2, 5, 8], "vertical anchor: 2 = bottom, 5 = middle, 8 = top (ASS numpad)"),
 ("captions.margin_v", "int", 520, 70, (0, 1800), "distance from the anchored edge in px (bottom anchor: from the bottom of the frame)"),
 ("captions.margin_h", "int", 60, 120, (0, 600), "left/right margin in px"),
 ("captions.words_per_group", "int", 3, 6, (1, 12), "words shown together"),
 ("captions.max_group_s", "float", 1.6, 3.0, (0.3, 8), "a caption group is closed after this many seconds"),
 ("captions.animation", "enum", "pop", "none", ["none", "pop", "bounce", "fade", "karaoke"], "pop = scale 80->100 %, bounce = overshoot, fade = fade in, karaoke = whole group, active word in highlight_color"),
 ("captions.uppercase", "bool", False, False, None, "force upper case"),
 ("hook.enabled", "bool", True, NA, None, "Shorts: LLM hook text on the first seconds"),
 ("hook.duration_s", "float", 1.8, NA, (0.5, 8), "how long the hook text stays"),
 ("hook.size", "int", 64, NA, (16, 200), "font size px"),
 ("hook.color", "color", "#FFFFFF", NA, None, "text colour"),
 ("hook.border_color", "color", "#000000", NA, None, "border colour"),
 ("hook.border_px", "int", 6, NA, (0, 20), "border width"),
 ("hook.y", "int", 300, NA, (0, 1800), "top of the first line (px from the top)"),
 ("hook.line_gap", "int", 84, NA, (20, 300), "distance between the two lines"),
 ("hook.max_chars", "int", 40, NA, (8, 80), "text is cut to this length"),
 ("hook.wrap_chars", "int", 16, NA, (6, 60), "longer hooks are wrapped into two centred lines"),
 ("hook.uppercase", "bool", True, NA, None, "force upper case"),
 ("hook.font", "str", "auto", NA, None, "auto = first Black/Bold font found, or a file name in assets/fonts (e.g. Anton-Regular.ttf)"),
 ("hook.words", "str", "3-6", NA, None, "how many words the LLM writes (goes into the prompt)"),
 ("zoom.enabled", "bool", True, NA, None, "punch-in zoom at the peak of the moment (the classic one is a 7 % bump)"),
 ("zoom.strength", "float", 0.07, NA, (0, 0.5), "peak punch-in size (0.07 = 107 %)"),
 ("zoom.attack_frames", "int", 7, NA, (1, 60), "frames to reach full zoom (at 30 fps)"),
 ("zoom.decay_frames", "int", 23, NA, (1, 120), "frames to relax back to 100 %"),
 ("zoom.extra_every_s", "float", 0, NA, (0, 60), "additional small punch-ins about every N seconds, snapped to caption starts (0 = only the peak)"),
 ("zoom.extra_strength", "float", 0.04, NA, (0, 0.3), "size of the additional punch-ins"),
 ("zoom.max_extra", "int", 6, NA, (0, 30), "maximum number of additional punch-ins"),
 ("sfx.mode", "enum", "env", NA, ["env", "on", "off"], "env = only when SHORTS_SFX=1 (classic), on / off = the style decides"),
 ("sfx.file", "str", "boom.wav", NA, None, "file in assets/sfx"),
 ("sfx.volume_db", "float", -9, NA, (-40, 6), "volume of the effect"),
 ("sfx.at", "strlist", ["peak"], NA, ["peak", "start", "zoom"], "when it plays: at the peak, at the first frame, at every extra zoom"),
 ("music.enabled", "bool", False, False, None, "mix a music bed (needs a royalty-free file in assets/music or an absolute path; never music you do not have the licence for)"),
 ("music.file", "str", "", "", None, "file name in assets/music or a path"),
 ("music.volume_db", "float", -24, -24, (-50, 0), "music level before ducking"),
 ("music.duck", "bool", True, True, None, "lower the music while someone talks (sidechain)"),
 ("intro.bumper_s", "float", 0, 2.5, (0, 8), "logo bumper at the start in seconds (0 = none). Long videos: the 2.5 s ClipGlobe bumper"),
 ("watermark.enabled", "bool", True, True, None, "logo watermark in a corner"),
 ("watermark.size_px", "int", 130, 120, (20, 600), "logo width"),
 ("watermark.opacity", "float", 0.9, 0.85, (0.05, 1), "logo opacity"),
 ("watermark.corner", "enum", "tl", "br", ["tl", "tr", "bl", "br"], "which corner"),
 ("watermark.margin_x", "int", 30, 32, (0, 400), "distance from the left/right edge"),
 ("watermark.margin_y", "int", 140, 32, (0, 600), "distance from the top/bottom edge"),
 ("loudness.enabled", "bool", True, False, None, "EBU R128 loudness normalisation (loudnorm)"),
 ("loudness.lufs", "float", -14, -14, (-30, -8), "integrated loudness target"),
 ("loudness.tp", "float", -1.5, -1.5, (-9, 0), "true-peak limit dBTP"),
 ("loudness.lra", "float", 7, 11, (1, 20), "loudness range"),
 ("export.fps", "int", 30, NA, (24, 60), "Shorts frame rate"),
 ("export.crf", "int", 18, 19, (12, 30), "x264 quality (lower = better)"),
 ("export.preset", "enum", "veryfast", "veryfast", ["ultrafast", "superfast", "veryfast", "faster", "fast", "medium"], "x264 preset"),
 ("export.audio_kbps", "int", 192, 192, (96, 320), "AAC bitrate"),
]
SPEC = {}; DEFAULTS = {"shorts": {}, "long": {}}
for _p, _t, _s, _l, _c, _d in _T:
    SPEC[_p] = {"type": _t, "constraint": _c, "doc": _d, "shorts": _s, "long": _l}
    for _f, _v in (("shorts", _s), ("long", _l)):
        if _v is NA: continue
        sec, key = _p.split(".", 1); DEFAULTS[_f].setdefault(sec, {})[key] = copy.deepcopy(_v)
TOP_KEYS = {"schema", "name", "label", "description", "extends", "language_note", "source", "shorts", "long", "notes"}
NAMED = {"white": "#FFFFFF", "black": "#000000", "yellow": "#FFFF00", "red": "#FF0000", "green": "#00FF00", "blue": "#0000FF"}
def norm_color(c):
    """'#FFC107' | 'FFC107' | '0xFFC107' | 'white' -> '#FFC107'"""
    c = str(c).strip(); c = NAMED.get(c.lower(), c); m = re.fullmatch(r"(?:#|0x)?([0-9a-fA-F]{6})", c)
    if not m: raise ValueError(f"bad colour {c!r}")
    return "#" + m.group(1).upper()
def hex_to_ass(c, alpha=0):
    """'#FFC107' -> ASS BGR '&H0007C1FF' (the amber the Shorts always used)"""
    h = norm_color(c)[1:]; return "&H%02X%s%s%s" % (alpha, h[4:6], h[2:4], h[0:2])
def deep_merge(a, b):
    out = copy.deepcopy(a)
    for k, v in (b or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict): out[k] = deep_merge(out[k], v)
        else: out[k] = copy.deepcopy(v)
    return out
def list_styles():
    return sorted(f[:-5] for f in os.listdir(STYLE_DIR) if f.endswith(".json") and not f.startswith("_")) if os.path.isdir(STYLE_DIR) else []
def _path(name):
    if os.path.isfile(name): return name
    p = os.path.join(STYLE_DIR, name + ".json" if not name.endswith(".json") else name)
    if os.path.isfile(p): return p
    raise FileNotFoundError(f"style {name!r} not found (known: {', '.join(list_styles())})")
def load_raw(name, _seen=()):
    """the style JSON with its `extends` chain merged (child wins); returns the merged raw dict"""
    d = name if isinstance(name, dict) else json.load(open(_path(name), encoding="utf-8"))
    base = d.get("extends")
    if base and base not in _seen and base != d.get("name"):
        d = deep_merge(load_raw(base, _seen + (d.get("name"), base)), {k: v for k, v in d.items() if k != "extends"})
    return d
def resolve(style, fmt="shorts"):
    """full parameter dict {section:{key:value}} for the format. style = None -> the classic defaults; str -> name or path; dict -> raw style"""
    out = copy.deepcopy(DEFAULTS[fmt])
    if style is None: return out
    raw = load_raw(style); out = deep_merge(out, raw.get(fmt) or {}); return out
def active(fmt="shorts"):
    """the style chosen with env STYLE (None when unset/empty); raises when the name is unknown so a typo never silently renders the default"""
    n = (os.environ.get("STYLE") or "").strip()
    return resolve(n, fmt) if n else None
def name_of(style):
    try: return load_raw(style).get("name") or (style if isinstance(style, str) else "custom")
    except Exception: return str(style)
def validate(style):
    """list of problems (empty = OK) for a style name/path/dict: unknown keys, wrong types, out-of-range values, bad colours"""
    errs = []
    try: raw = style if isinstance(style, dict) else json.load(open(_path(style), encoding="utf-8"))
    except Exception as e: return [f"cannot load: {e}"]
    for k in raw:
        if k not in TOP_KEYS: errs.append(f"unknown top-level key {k!r}")
    try: full = load_raw(raw)
    except Exception as e: return errs + [f"extends chain: {e}"]
    for fmt in ("shorts", "long"):
        for sec, kv in (full.get(fmt) or {}).items():
            if not isinstance(kv, dict): errs.append(f"{fmt}.{sec} must be an object"); continue
            for key, v in kv.items():
                p = f"{sec}.{key}"; sp = SPEC.get(p)
                if sp is None: errs.append(f"{fmt}.{p}: unknown parameter"); continue
                if sp[fmt] is NA: errs.append(f"{fmt}.{p}: not used in the {fmt} format"); continue
                e = _check(sp, v)
                if e: errs.append(f"{fmt}.{p}: {e}")
    return errs
def _check(sp, v):
    t, c = sp["type"], sp["constraint"]
    if t == "bool": return None if isinstance(v, bool) else "must be true/false"
    if t in ("int", "float"):
        if isinstance(v, bool) or not isinstance(v, (int, float)): return "must be a number"
        if t == "int" and float(v) != int(v): return "must be an integer"
        if c and not (c[0] <= v <= c[1]): return f"{v} outside {c[0]}..{c[1]}"
        return None
    if t == "str": return None if isinstance(v, str) else "must be text"
    if t == "color":
        try: norm_color(v); return None
        except Exception: return f"bad colour {v!r}"
    if t == "enum": return None if v in c else f"{v!r} not in {c}"
    if t == "strlist": return None if isinstance(v, list) and all(x in c for x in v) else f"must be a list from {c}"
    return None
def write_schema(path=None):
    """config/styles/_schema.json: every parameter with type, range, defaults and meaning (generated from this file)"""
    path = path or os.path.join(STYLE_DIR, "_schema.json"); params = {}
    for p, sp in SPEC.items():
        params[p] = {"type": sp["type"], "meaning": sp["doc"], "default_shorts": None if sp["shorts"] is NA else sp["shorts"], "default_long": None if sp["long"] is NA else sp["long"]}
        c = sp["constraint"]
        if c: params[p]["range" if sp["type"] in ("int", "float") else "allowed"] = c
        params[p]["formats"] = [f for f in ("shorts", "long") if sp[f] is not NA]
    doc = {"schema": 1, "how_to_use": "A style file config/styles/<name>.json = {name, label, description, extends (optional base style), shorts:{section:{key:value}}, long:{...}}. Write only the keys that differ. Select with env STYLE=<name> or --style <name> in scripts/vod_shorts.py / scripts/vod_long.py. scripts/style_from_video.py <url-or-file> writes such a file from a reference video. 'default' = exactly the behaviour before styles existed.", "parameters": params}
    os.makedirs(os.path.dirname(path), exist_ok=True); json.dump(doc, open(path, "w", encoding="utf-8"), indent=1, ensure_ascii=False); open(path, "a").write("\n"); return path
# ---- captions (ASS) ---------------------------------------------------------------------------------------------------------------------------------------------------
def group_words(words, s, e, per=3, max_s=1.6):
    """same grouping as scripts/stations/shorts.make_ass: words in [s, e] -> groups of `per` words, closed early at . ! ? , or when longer than max_s"""
    ws = [w for w in words if w["start"] >= s - 0.05 and w["end"] <= e + 0.05 and w["word"].strip()]; groups, cur = [], []
    for w in ws:
        cur.append(w)
        if len(cur) >= per or re.search(r"[.!?,]$", w["word"].strip()) or (cur and w["end"] - cur[0]["start"] > max_s): groups.append(cur); cur = []
    if cur: groups.append(cur)
    return groups
_ANIM = {"pop": r"{\fscx80\fscy80\t(0,110,\fscx100\fscy100)}", "none": "", "fade": r"{\fad(90,0)}", "bounce": r"{\fscx70\fscy70\t(0,90,\fscx118\fscy118)\t(90,180,\fscx100\fscy100)}", "karaoke": ""}
def make_ass(words, s, e, path, cap, W=1080, H=1920, remap=None, hook=None, hook_style=None):
    """ASS captions. cap = captions parameter dict (see SPEC). remap(t_rel_to_s) -> new time (dead-air cuts) or None when the time lies in a cut.
    hook (optional text) + hook_style: an extra on-screen text line event for the first seconds (used for non-Latin hooks that ffmpeg drawtext cannot shape). Returns [(start, end), ...] of the caption groups (seconds, after remap)."""
    groups = group_words(words, s, e, int(cap["words_per_group"]), float(cap["max_group_s"]))
    def ts2(t): return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"
    col, hl, oc = hex_to_ass(cap["color"]), hex_to_ass(cap["highlight_color"]), hex_to_ass(cap["outline_color"])
    hdr = (f"[Script Info]\nScriptType: v4.00+\nPlayResX: {W}\nPlayResY: {H}\nWrapStyle: 0\n\n[V4+ Styles]\n"
           "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\n"
           f"Style: Cap,{cap['font']},{int(cap['size'])},{col},{col},{oc},&H64000000,1,0,0,0,100,100,0,0,1,{_n(cap['outline_px'])},{_n(cap['shadow_px'])},{int(cap['align'])},{int(cap['margin_h'])},{int(cap['margin_h'])},{int(cap['margin_v'])},1\n")
    if hook and hook_style:
        hs = hook_style; hdr += (f"Style: Hook,{cap['font']},{int(hs['size'])},{hex_to_ass(hs['color'])},{hex_to_ass(hs['color'])},{hex_to_ass(hs['border_color'])},&H64000000,1,0,0,0,100,100,0,0,1,{_n(hs['border_px'])},0,8,60,60,{int(hs['y'])},1\n")
    hdr += "\n[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n"
    ev = []; spans = []; anim = cap.get("animation", "pop"); upper = cap.get("uppercase")
    def esc(t): t = t.replace("{", "").replace("}", ""); return t.upper() if upper else t
    def mp(a, b):
        if remap is None: return max(0, a - s), max(0, b - s)
        a2, b2 = remap(max(0, a - s)), remap(max(0, b - s))
        return (None, None) if a2 is None or b2 is None or b2 <= a2 else (a2, b2)
    for i, g in enumerate(groups):
        a = g[0]["start"]; b = groups[i + 1][0]["start"] if i + 1 < len(groups) and groups[i + 1][0]["start"] - g[-1]["end"] < 0.6 else g[-1]["end"] + 0.15
        if anim == "karaoke":   # one event per word: the whole group stays, the active word is coloured
            for k, w in enumerate(g):
                wa = w["start"] if k else a; wb = g[k + 1]["start"] if k + 1 < len(g) else b
                a2, b2 = mp(wa, wb)
                if a2 is None: continue
                parts = [("{\\c%s}" % hl if j == k else "{\\c%s}" % col) + esc(x["word"].strip()) for j, x in enumerate(g)]
                ev.append(f"Dialogue: 0,{ts2(a2)},{ts2(b2)},Cap,,0,0,0,,{' '.join(parts)}")
            a2, b2 = mp(a, b)
        else:
            a2, b2 = mp(a, b)
            if a2 is None: continue
            ev.append(f"Dialogue: 0,{ts2(a2)},{ts2(b2)},Cap,,0,0,0,,{_ANIM[anim]}{esc(' '.join(x['word'].strip() for x in g))}")
        if a2 is not None: spans.append((a2, b2))
    if hook and hook_style:
        htxt = "\\N".join(x for x in hook.split("|") if x.strip())
        ev.append(f"Dialogue: 1,{ts2(0)},{ts2(float(hook_style['duration_s']))},Hook,,0,0,0,,{htxt}")
    open(path, "w", encoding="utf-8").write(hdr + "\n".join(ev) + "\n"); return spans
def _n(x): return str(int(x)) if float(x) == int(x) else str(x)
def make_remap(cuts):
    """cuts = sorted [(a, b)] time ranges (seconds, relative to the clip start) that are removed; returns remap(t) -> t minus the cut time before it, None when t is inside a cut"""
    cuts = sorted(cuts)
    def remap(t):
        sub = 0.0
        for a, b in cuts:
            if t >= b: sub += b - a
            elif t > a: return None
            else: break
        return t - sub
    return remap
def total_cut(cuts): return sum(b - a for a, b in cuts)
if __name__ == "__main__":
    a = sys.argv[1:]; cmd = a[0] if a else "list"
    if cmd == "list":
        for n in list_styles(): r = load_raw(n); print(f"{n:16s} {r.get('label', '')} - {r.get('description', '')[:110]}")
    elif cmd == "show": print(json.dumps(resolve(a[1], a[2] if len(a) > 2 else "shorts"), indent=1, ensure_ascii=False))
    elif cmd == "validate":
        bad = 0
        for n in (a[1:] or list_styles()):
            e = validate(n); print(("OK   " if not e else "FAIL ") + n); bad += bool(e)
            for x in e: print("     -", x)
        sys.exit(1 if bad else 0)
    elif cmd == "schema": print(write_schema())
    else: sys.exit(__doc__)

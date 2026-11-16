#!/usr/bin/env python3
"""PREDICT: for every public/unlisted video of the channel, estimate where its views will be in 48 hours and the chance it takes off.
Inputs: state/yt_stats.json (current numbers), state/yt_video_history.jsonl (per-video snapshots every ~30 min), config/channel_style.json (the streamer's own channel as a ceiling).
Output: state/predictions.json (read by the app).
Method (honest, simple): cumulative views grow roughly like age^beta. beta is fitted on the video's own snapshots when there are enough, otherwise a prior (0.55) is used, with a wide band. The 48 h forecast is a 10%-90% band; the chances of reaching 1K/5K/10K/20K views come from a log-normal around the median forecast. Early numbers (first hours) are only a rough guide.
usage: predict.py"""
import json, math, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from events import ST, ROOT
def jf(p, d=None):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return d
stats = jf(os.path.join(ST, "yt_stats.json"), {}) or {}
hist = []
hp = os.path.join(ST, "yt_video_history.jsonl")
if os.path.exists(hp):
    for l in open(hp, encoding="utf-8"):
        try: hist.append(json.loads(l))
        except Exception: pass
style = jf(os.path.join(ROOT, "config", "channel_style.json"), {}) or {}
now = time.time()
def ts(x): return time.mktime(time.strptime(x[:19], "%Y-%m-%dT%H:%M:%S")) - time.timezone
def dur_min(d):
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", d or ""); return int(m[1] or 0) * 60 + int(m[2] or 0) + int(m[3] or 0) / 60 if m else 0
def phi(z): return 0.5 * (1 + math.erf(z / math.sqrt(2)))
vids = [v for v in stats.get("videos", []) if v.get("privacy") != "private" and dur_min(v.get("duration")) > 3 and not v["title"].startswith("בדיקה")]
old = sorted(v["views"] for v in vids if now - ts(v["published"]) > 24 * 3600)
baseline = max(old[len(old) // 2], 300) if old else 1000
band_ref = {k: x.get("views_median") for k, x in (style.get("by_kind") or {}).items()}
out = []
for v in vids:
    age = max((now - ts(v["published"])) / 3600, 0.25); V = max(v["views"], 0)
    ser = [((ts(h["t"]) - ts(v["published"])) / 3600, h["v"][v["id"]][0]) for h in hist if v["id"] in h.get("v", {}) and ts(h["t"]) > ts(v["published"])]
    ser = [(a, x) for a, x in ser if a > 0.2]
    if not ser or abs(ser[-1][0] - age) > 1: ser.append((age, V))
    beta, conf = 0.55, "נמוכה"; lo_b, hi_b = 0.3, 0.8
    pts = [(math.log(a), math.log(max(x, 1))) for a, x in ser if a >= 1 and x >= 5]
    if len(pts) >= 4 and (pts[-1][0] - pts[0][0]) > 0.4:   # fit beta on the video's own history
        mx = sum(p[0] for p in pts) / len(pts); my = sum(p[1] for p in pts) / len(pts); sxx = sum((p[0] - mx) ** 2 for p in pts)
        if sxx > 0:
            b = sum((p[0] - mx) * (p[1] - my) for p in pts) / sxx
            if 0.05 < b < 1.5: beta = min(max(b, 0.15), 1.0); lo_b, hi_b = max(beta - 0.15, 0.1), min(beta + 0.15, 1.1); conf = "בינונית" if age < 48 else "טובה"
    elif age > 72: conf = "בינונית"
    def proj(b): return V * ((age + 48) / age) ** b if V > 0 else 0
    lo, mid, hi = proj(lo_b), proj(beta), proj(hi_b)
    if age < 6: lo, hi = lo * 0.5, hi * 2.0   # first hours: very uncertain
    sig = max(math.log(max(hi, 1) / max(lo, 1)) / 2.56, 0.15)
    chances = {str(T): round(100 * (1 - phi((math.log(T) - math.log(max(mid, 1))) / sig))) if mid > 0 else 0 for T in (1000, 5000, 10000, 20000)}
    rate = lambda a, b: (a / b * 100) if b else 0
    like_r, com_r = rate(v.get("likes", 0), V), rate(v.get("comments", 0), V)
    score = 50 + 22 * math.log2(max(mid, 1) / baseline) + (6 if like_r >= 4 else -4 if V > 200 and like_r < 2 else 0) + (4 if com_r >= 0.4 else 0)
    score = int(max(2, min(98, score)))
    d = dur_min(v.get("duration")); reasons = []
    reasons.append(f"תחזית ל-48 שעות: {int(lo):,}–{int(hi):,} צפיות (חציון {int(mid):,}). הבסיס של הערוץ: ~{baseline:,} צפיות לסרטון.")
    if V and age >= 1: reasons.append(f"קצב נוכחי: {V / age:.1f} צפיות לשעה בממוצע מאז הפרסום (גיל {age:.1f} שעות).")
    if V > 100: reasons.append(f"לייקים: {like_r:.1f}% מהצפיות" + (" (גבוה, סימן טוב)" if like_r >= 4 else " (נמוך)" if like_r < 2 else "") + f", תגובות: {com_r:.2f}%.")
    ref = band_ref.get("reaction") if "מגיב" in v["title"] else band_ref.get("game") if re.search(r"\([A-Za-z]", v["title"]) else band_ref.get("other")
    if ref: reasons.append(f"להשוואה: חציון הצפיות של סרטונים מאותו סוג בערוץ של עודד עצמו הוא ~{ref:,} (תקרה, לערוץ שלנו מצפים לחלק ממנו).")
    if 20 <= d <= 60: reasons.append("אורך בטווח שמקבל הכי הרבה צפיות בערוץ של עודד (20-60 דקות).")
    elif d < 12: reasons.append("קצר מ-12 דקות: בערוץ של עודד סרטונים כאלה מקבלים פחות צפיות.")
    if age < 6: reasons.append("הסרטון חדש מאוד (פחות מ-6 שעות): התחזית מאוד גסה.")
    label = "גבוה" if score >= 70 else "בינוני" if score >= 45 else "נמוך"
    out.append({"id": v["id"], "title": v["title"], "published": v["published"], "age_h": round(age, 1), "views": V, "likes": v.get("likes", 0), "comments": v.get("comments", 0), "duration_min": round(d, 1), "confidence": conf, "beta": round(beta, 2),
                "proj48": {"low": int(lo), "mid": int(mid), "high": int(hi)}, "chances": chances, "score": score, "label": label, "reasons": reasons, "series": [[round(a, 2), int(x)] for a, x in ser][-60:]})
out.sort(key=lambda x: x["published"], reverse=True)
json.dump({"generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "baseline_views": baseline, "note": "הערכה סטטיסטית, לא הבטחה. נתוני Data API מתעדכנים באיחור מול Studio.", "videos": out}, open(os.path.join(ST, "predictions.json"), "w"), ensure_ascii=False, indent=1)
print("predictions:", len(out), "videos, baseline", baseline)

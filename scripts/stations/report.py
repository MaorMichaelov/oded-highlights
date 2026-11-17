#!/usr/bin/env python3
"""REPORT: every video of the channel, one by one: views, likes, comments, duration and an ESTIMATED watch time, plus totals and rankings (state/channel_report.json, shown in the app).
Exact watch hours need the YouTube Analytics API (not enabled yet); the Data API has no watch time. The estimate = views x duration x an assumed average-percentage-viewed by length bucket (range low-high), clearly labelled as an estimate in the app."""
import json, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from events import ST
def jf(p, d=None):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return d
st = jf(os.path.join(ST, "yt_stats.json"), {}) or {}
def mins(d):
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", d or ""); return (int(m[1] or 0) * 60 + int(m[2] or 0) + int(m[3] or 0) / 60) if m else 0
def avg_pct(m):   # assumed average % viewed (mid), by length: shorts watch most of it, long videos much less
    return 0.80 if m <= 1.1 else 0.45 if m <= 10 else 0.32 if m <= 30 else 0.24
now = time.time(); rows = []
for v in st.get("videos", []):
    d = mins(v.get("duration")); views = int(v.get("views", 0)); mid = avg_pct(d)
    lo, hi = views * d * mid * 0.6 / 60, views * d * mid * 1.4 / 60
    try: age = max((now - time.mktime(time.strptime(v["published"][:19], "%Y-%m-%dT%H:%M:%S"))) / 86400, 0.05)
    except Exception: age = 1
    kind = "short" if d <= 1.1 else "reaction" if "מגיב" in v["title"] or "reacts" in v["title"].lower() else "game" if re.search(r"\([A-Za-z]", v["title"]) else "other"
    rows.append({"id": v["id"], "title": v["title"], "published": v["published"][:10], "privacy": v.get("privacy"), "duration_min": round(d, 1), "views": views, "likes": v.get("likes", 0), "comments": v.get("comments", 0), "est_hours": [round(lo, 1), round(hi, 1)], "views_per_day": round(views / age, 1), "kind": kind})
pub = [r for r in rows if r["privacy"] != "private"]
tot = {"videos_total": len(rows), "videos_public": len(pub), "views": sum(r["views"] for r in pub), "likes": sum(r["likes"] for r in pub), "est_hours_low": round(sum(r["est_hours"][0] for r in pub), 1), "est_hours_high": round(sum(r["est_hours"][1] for r in pub), 1)}
by = {}
for r in pub: b = by.setdefault(r["kind"], {"n": 0, "views": 0, "est_hours_mid": 0.0}); b["n"] += 1; b["views"] += r["views"]; b["est_hours_mid"] = round(b["est_hours_mid"] + sum(r["est_hours"]) / 2, 1)
top = sorted(pub, key=lambda r: -r["views"])[:5]; best_h = sorted(pub, key=lambda r: -sum(r["est_hours"]))[:5]
rows.sort(key=lambda r: r["published"], reverse=True)
out = {"generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "channel": st.get("channel", {}), "totals": tot, "by_kind": by, "top_views": [r["id"] for r in top], "top_est_hours": [r["id"] for r in best_h], "videos": rows,
       "note": "שעות הצפייה כאן הן הערכה (צפיות × אורך × אחוז צפייה ממוצע משוער). שעות צפייה מדויקות דורשות הפעלת YouTube Analytics API וחיבור מחדש עם הרשאת קריאה לאנליטיקס."}
json.dump(out, open(os.path.join(ST, "channel_report.json"), "w"), ensure_ascii=False, indent=1); print("report:", tot)

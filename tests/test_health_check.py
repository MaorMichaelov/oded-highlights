import datetime as dt, os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import health_check as H

NOW = dt.datetime(2026, 11, 18, 12, 0, tzinfo=dt.timezone.utc)
def iso(mins_ago): return (NOW - dt.timedelta(minutes=mins_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
def ctx(**kw):
    base = {"now": NOW, "runs": [{"workflowName": "live-loop", "status": "in_progress", "createdAt": iso(30)}], "paused": False, "live_status": {"checked_at": iso(2), "http": "200", "live": False}, "ingest": {"_behind_segs": 0},
            "index": [], "hold": None, "clips": [], "channels": [], "corrupt": [], "unreadable": [], "ledger": []}
    base.update(kw); return base

class Health(unittest.TestCase):
    def test_all_ok(self):
        r = H.evaluate(ctx()); self.assertEqual(r["overall"], "ok"); self.assertEqual(r["hc_problems"], [])
    def test_loop_dead_is_critical_unless_paused(self):
        r = H.evaluate(ctx(runs=[])); self.assertEqual(r["checks"]["live_loop"]["status"], "critical"); self.assertEqual(r["overall"], "critical")
        r = H.evaluate(ctx(runs=[], paused=True)); self.assertEqual(r["checks"]["live_loop"]["status"], "info")
    def test_no_gh_does_not_fail(self):
        r = H.evaluate(ctx(runs=None)); self.assertEqual(r["checks"]["live_loop"]["status"], "info"); self.assertNotEqual(r["overall"], "critical")
    def test_stuck_loop(self):
        r = H.evaluate(ctx(live_status={"checked_at": iso(45), "http": "200", "live": False})); self.assertEqual(r["checks"]["state_fresh"]["status"], "critical")
        r = H.evaluate(ctx(runs=[], live_status={"checked_at": iso(45), "http": "200"})); self.assertEqual(r["checks"]["state_fresh"]["status"], "warn")
    def test_hold_and_quota(self):
        r = H.evaluate(ctx(hold="2026-11-19T06:00:00Z")); self.assertEqual(r["checks"]["upload_hold"]["status"], "info"); self.assertEqual(r["overall"], "ok")
        r = H.evaluate(ctx(hold="2026-11-01T06:00:00Z", clips=[{"id": "c1", "draft_state": "quota_wait", "spec_age_min": 10}])); self.assertEqual(r["checks"]["upload_hold"]["status"], "warn")
    def test_last_upload_age(self):
        idx = [{"id": "a", "title": "t", "draft": "https://youtu.be/x", "draft_at": iso(60 * 50)}, {"id": "b", "title": "u", "draft": None}]
        r = H.evaluate(ctx(index=idx)); self.assertEqual(r["checks"]["last_upload"]["status"], "warn")
        r = H.evaluate(ctx(index=[idx[0]])); self.assertEqual(r["checks"]["last_upload"]["status"], "ok")
    def test_failed_and_cancelled_and_queue(self):
        runs = [{"workflowName": "live-loop", "status": "in_progress", "createdAt": iso(5)}] + [{"workflowName": "render-clip", "status": "completed", "conclusion": "failure", "createdAt": iso(20 + i)} for i in range(5)]
        self.assertEqual(H.evaluate(ctx(runs=runs))["checks"]["failed_runs"]["status"], "critical")
        runs = [{"workflowName": "live-loop", "status": "in_progress", "createdAt": iso(5)}] + [{"workflowName": "live-loop", "status": "completed", "conclusion": "cancelled", "createdAt": iso(10 * i + 1)} for i in range(3)]
        self.assertEqual(H.evaluate(ctx(runs=runs))["checks"]["cancelled_runs"]["status"], "warn")
        runs = [{"workflowName": "live-loop", "status": "in_progress", "createdAt": iso(5)}, {"workflowName": "render-clip", "status": "queued", "createdAt": iso(120)}]
        self.assertEqual(H.evaluate(ctx(runs=runs))["checks"]["queue_stall"]["status"], "warn")
    def test_stuck_clips_ignore_tests_and_quota(self):
        cl = [{"id": "x1", "spec_age_min": 200}, {"id": "test_a", "spec_age_min": 200}, {"id": "q1", "spec_age_min": 200, "draft_state": "quota_wait"}, {"id": "ok1", "spec_age_min": 200, "draft_url": "u"}]
        r = H.evaluate(ctx(clips=cl)); self.assertIn("x1", r["checks"]["stuck_clips"]["detail"]); self.assertNotIn("test_a", r["checks"]["stuck_clips"]["detail"]); self.assertNotIn("q1", r["checks"]["stuck_clips"]["detail"])
    def test_integrity_critical(self):
        r = H.evaluate(ctx(corrupt=["state/pick_state.json.corrupt-1"])); self.assertEqual(r["overall"], "critical")
    def test_duplicates(self):
        idx = [{"id": "a", "title": "same", "draft": "u1"}, {"id": "b", "title": "same", "draft": "u2"}]
        self.assertEqual(H.evaluate(ctx(index=idx))["checks"]["duplicates"]["status"], "warn")
        led = [{"vod": "1", "kind": "long", "start": 0, "end": 600, "clip_id": "a", "yt": "main"}, {"vod": "1", "kind": "long", "start": 10, "end": 610, "clip_id": "b", "yt": "main"}]
        self.assertEqual(H.evaluate(ctx(ledger=led))["checks"]["duplicates"]["status"], "warn")
    def test_enabled_channels_without_loop(self):
        r = H.evaluate(ctx(channels=[{"slug": "odedsvr", "enabled": True}, {"slug": "xqc", "enabled": True}])); self.assertEqual(r["checks"]["channel_loops"]["status"], "warn")

if __name__ == "__main__": unittest.main()

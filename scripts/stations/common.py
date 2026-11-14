"""Shared helpers of the stations: per-clip status.json with stage timings (state/clips/<id>/status.json) so every stage can be inspected, retried and measured alone."""
import json, os, time
def mark(clip, stage, state, **kw):
    f = os.path.join(clip, "status.json"); d = json.load(open(f)) if os.path.exists(f) else {}
    s = d.setdefault(stage, {}); s["state"] = state; s.update(kw)
    s["at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()); json.dump(d, open(f, "w"), indent=1)
class Timer:
    def __init__(self, clip, stage): self.clip, self.stage, self.t0 = clip, stage, time.time()
    def __enter__(self): mark(self.clip, self.stage, "running"); return self
    def __exit__(self, et, ev, tb):
        mark(self.clip, self.stage, "failed" if et else "done", seconds=round(time.time() - self.t0, 1)); return False

from homefinder.worker import main as wmain


class FakeClient:
    def __init__(self, jobs):
        self.jobs, self.done, self.failed, self.beats = list(jobs), [], [], 0
    def heartbeat(self, hostname, version, current_job_id): self.beats += 1
    def claim(self, types, n=1): return [self.jobs.pop(0)] if self.jobs else []
    def complete(self, job_id, result): self.done.append((job_id, result))
    def fail(self, job_id, error): self.failed.append((job_id, error))


def test_loop_dispatches_completes_and_fails(monkeypatch):
    calls = []
    def fake_dispatch(deps, t, p):
        calls.append(t)
        if p.get("boom"):
            raise RuntimeError("kaput")
        return {"ok": 1}
    monkeypatch.setattr(wmain, "dispatch", fake_dispatch)
    monkeypatch.setattr(wmain, "_schedule", lambda interval: None)
    c = FakeClient([{"id": 1, "type": "x", "payload": {}}, {"id": 2, "type": "x", "payload": {"boom": True}}])
    ticks = iter(range(4))
    wmain.run_loop(None, c, stop=lambda: next(ticks, None) is None, sleep=lambda s: None)
    assert c.done == [(1, {"ok": 1})] and c.failed[0][0] == 2 and "kaput" in c.failed[0][1]
    assert c.beats >= 1


def test_loop_survives_server_down(monkeypatch):
    class Down(FakeClient):
        def claim(self, types, n=1): raise ConnectionError("no route")
        def heartbeat(self, *a): raise ConnectionError("no route")
    monkeypatch.setattr(wmain, "_schedule", lambda interval: None)
    slept = []
    ticks = iter(range(3))
    wmain.run_loop(None, Down([]), stop=lambda: next(ticks, None) is None, sleep=slept.append)
    assert slept and all(s >= 30 for s in slept)

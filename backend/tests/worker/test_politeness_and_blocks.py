import random

import pytest

from homefinder.adapters_state import is_paused
from homefinder.db import session_scope
from homefinder.models import AdapterHealth, Job
from homefinder.schemas import SearchQuery
from homefinder.worker.handlers import dispatch
from homefinder.worker.sources.aqar_transport import Blocked, FallbackTransport
from homefinder.worker.sources.base import Pacer
from homefinder.worker.sources.haraj_transport import FallbackHaraj
from tests.worker.test_handlers_scrape import FakeAdapter, deps
from tests.worker.test_haraj import posts
from tests.worker.test_refresh import deps as refresh_deps, mk


class FakeClock:
    def __init__(self): self.t, self.slept = 1000.0, []
    def now(self): return self.t
    def sleep(self, s): self.slept.append(s); self.t += s


def test_pacer_holds_the_gap_across_calls_with_no_time_passing():
    c = FakeClock()
    p = Pacer(sleep=c.sleep, rng=random.Random(1), clock=c.now)
    p.wait()
    assert c.slept == []          # the very first call is free
    p.wait()
    assert 2 <= c.slept[-1] <= 10  # the second one waits even though nothing else happened in between


def test_pacer_does_not_sleep_after_idle_time_but_never_bunches_requests():
    c = FakeClock()
    p = Pacer(sleep=c.sleep, rng=random.Random(2), clock=c.now)
    p.wait(); p.wait()
    n = len(c.slept)
    c.t += 60                      # idle for a minute (e.g. between two jobs)
    p.wait()
    assert len(c.slept) == n       # the gap already elapsed
    p.wait()
    assert len(c.slept) == n + 1   # but the next call is again spaced out


class Blocking(FakeAdapter):
    def search(self, q):
        raise Blocked("playwright: HTTP 403")
        yield

    def fetch(self, sid):
        raise Blocked("playwright: HTTP 403")


def test_scrape_pauses_the_adapter_when_blocked(db):
    out = dispatch(deps(Blocking([])), "scrape_search", {"source": "aqar", "query": {}})
    assert out == {"skipped": "blocked"}
    with session_scope() as s:
        assert is_paused(s, "aqar")
        assert "blocked" in s.get(AdapterHealth, "aqar").reason


def test_refresh_pauses_the_adapter_when_blocked_and_keeps_the_listing(db):
    l = mk(db, sid="42")
    out = dispatch(refresh_deps(aqar=Blocking([])), "refresh_listing", {"listing_id": l.id})
    assert out == {"skipped": "blocked"}
    db.expire_all()
    assert db.get(type(l), l.id).status == "active"
    with session_scope() as s:
        assert is_paused(s, "aqar")


def test_handlers_no_longer_close_the_shared_transport(db):
    closed = []

    class A(FakeAdapter):
        class _t:  # noqa: N801
            @staticmethod
            def close(): closed.append(1)

    dispatch(deps(A([])), "scrape_search", {"source": "aqar", "query": {}})
    assert closed == []


def test_build_deps_shares_one_adapter_per_source(settings_env):
    from homefinder.worker.main import build_deps
    d = build_deps(client=None)
    assert d.adapters["aqar"]() is d.adapters["aqar"]() and d.adapters["haraj"]() is d.adapters["haraj"]()
    assert d.adapters["aqar"]() is not d.adapters["haraj"]()


class _T:
    def __init__(self, exc): self.exc = exc
    def post_graphql(self, body): raise self.exc
    def search(self, *a): raise self.exc
    def close(self): pass


def test_fallbacks_start_again_with_the_first_transport_after_everything_was_blocked():
    ft = FallbackTransport([lambda: _T(Blocked("a")), lambda: _T(Blocked("b"))])
    with pytest.raises(Blocked):
        ft.post_graphql({})
    assert ft._i == 0
    fh = FallbackHaraj([lambda: _T(Blocked("a")), lambda: _T(Blocked("b"))])
    with pytest.raises(Blocked):
        fh.search("t", "c", 0)
    assert fh._i == 0


def test_haraj_stops_paging_when_the_site_says_there_is_no_next_page():
    from homefinder.worker.sources.haraj import HarajAdapter

    class T:
        def __init__(self): self.calls = []
        def search(self, tag, city, page):
            self.calls.append(page)
            return {"data": {"posts": {"items": posts(), "pageInfo": {"hasNextPage": page < 1}}}}
        def close(self): pass
    t = T()
    out = list(HarajAdapter(t, pacer=Pacer(sleep=lambda s: None)).search(SearchQuery(property_types=["villa"], max_pages=5)))
    assert t.calls == [0, 1] and out

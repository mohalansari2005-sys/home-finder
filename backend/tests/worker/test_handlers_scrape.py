from sqlalchemy import func, select

from homefinder.adapters_state import is_paused
from homefinder.db import session_scope
from homefinder.models import Listing
from homefinder.schemas import CanonicalFields, HealthReport, RawListing
from homefinder.worker.handlers import WorkerDeps, dispatch


class FakeAdapter:
    name = "aqar"
    def __init__(self, raws, ok=True): self.raws, self.ok = raws, ok
    def search(self, q): yield from self.raws
    def fetch(self, sid): return None
    def health(self, sample):
        return HealthReport(ok=self.ok, sample_size=len(sample), missing_ratio={}, reason=None if self.ok else "bad")


def r(i):
    return RawListing(source="aqar", source_id=str(i), url=f"u{i}", fields=CanonicalFields(price=1_000_000 + i))


def deps(adapter):
    return WorkerDeps(session_factory=session_scope, adapters={"aqar": lambda: adapter}, llm=None, maps=None,
                      photo_sink=None, http=None)


def test_scrape_ingests_all(db):
    out = dispatch(deps(FakeAdapter([r(1), r(2)])), "scrape_search", {"source": "aqar", "query": {}})
    assert out == {"fetched": 2, "ingested": 2, "new": 2}
    assert db.scalar(select(func.count()).select_from(Listing)) == 2


def test_unhealthy_batch_pauses_adapter_and_publishes_nothing(db):
    out = dispatch(deps(FakeAdapter([r(1)], ok=False)), "scrape_search", {"source": "aqar", "query": {}})
    assert out["skipped"] == "unhealthy"
    assert db.scalar(select(func.count()).select_from(Listing)) == 0
    with session_scope() as s:
        assert is_paused(s, "aqar")
    assert dispatch(deps(FakeAdapter([r(1)])), "scrape_search", {"source": "aqar", "query": {}}) == {"skipped": "paused"}


def test_outdated_app_version_pauses_with_clear_reason(db):
    from homefinder.models import AdapterHealth
    from homefinder.worker.sources.aqar_transport import AppVersionOutdated

    class Outdated(FakeAdapter):
        def search(self, q):
            raise AppVersionOutdated("curl_cffi: aqar app-version outdated (1.0.3)")
            yield

    out = dispatch(deps(Outdated([])), "scrape_search", {"source": "aqar", "query": {}})
    assert out["skipped"] == "app_version_outdated"
    with session_scope() as s:
        row = s.get(AdapterHealth, "aqar")
        assert row.status == "paused" and row.reason == "aqar app-version outdated"


def test_scrape_from_prefs_builds_query_at_run_time(db):
    from homefinder import prefs
    p = prefs.get_or_create(db); p.hard_filters = {**p.hard_filters, "districts": ["النرجس"], "price_max": 2_000_000}; db.commit()
    seen = []

    class Spy(FakeAdapter):
        def search(self, q):
            seen.append(q)
            yield from self.raws

    dispatch(deps(Spy([r(1)])), "scrape_search", {"source": "aqar", "from_prefs": True})
    assert seen[0].districts == ["النرجس"] and seen[0].price_max == 2_000_000

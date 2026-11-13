import json

import pytest
from pathlib import Path

from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from homefinder import usage
from homefinder.db import session_scope
from homefinder.models import ApiUsage, Listing
from homefinder.server.agent import fallback_search
from homefinder.server.agent.costs import UsageCallback
from homefinder.worker.sources.aqar_transport import Blocked
from homefinder.worker.sources.base import Pacer

FX = Path(__file__).parents[1] / "fixtures" / "aqar"


def test_usage_callback_records_cost_at_large_prices(db, settings_env):
    settings_env(OPENAI_PRICE_IN_LARGE="2", OPENAI_PRICE_OUT_LARGE="10")
    msg = AIMessage(content="x", usage_metadata={"input_tokens": 1_000_000, "output_tokens": 100_000, "total_tokens": 1_100_000})
    UsageCallback().on_llm_end(LLMResult(generations=[[ChatGeneration(message=msg)]]))
    row = db.query(ApiUsage).filter_by(provider="openai").one()
    assert abs(row.cost_usd - 3.0) < 1e-9 and row.calls == 1


def test_usage_callback_ignores_missing_usage_and_propagates_budget_errors(db, settings_env, monkeypatch):
    UsageCallback().on_llm_end(LLMResult(generations=[[ChatGeneration(message=AIMessage(content="x"))]]))
    assert db.query(ApiUsage).count() == 0
    assert UsageCallback.raise_error is True

    def boom(provider, cost):
        raise usage.BudgetExceeded("cap")
    monkeypatch.setattr(usage, "spend", boom)
    msg = AIMessage(content="x", usage_metadata={"input_tokens": 10, "output_tokens": 10, "total_tokens": 20})
    import pytest
    with pytest.raises(usage.BudgetExceeded):
        UsageCallback().on_llm_end(LLMResult(generations=[[ChatGeneration(message=msg)]]))


class FakeTransport:
    def __init__(self, listings=None, exc=None): self.listings, self.exc, self.closed = listings or [], exc, False
    def post_graphql(self, body):
        if self.exc:
            raise self.exc
        return {"data": {"Web": {"find": {"total": len(self.listings), "listings": self.listings}}}}
    def close(self): self.closed = True


def test_fallback_search_ingests_first_page(db):
    from homefinder.db import session_scope
    listings = json.loads((FX / "find_villa_riyadh.json").read_text("utf-8"))["data"]["Web"]["find"]["listings"]
    t = FakeTransport(listings)
    out = fallback_search.run(session_scope, transport_factory=lambda: t, pacer=Pacer(sleep=lambda s: None))
    assert out == {"ingested": len(listings)} and t.closed
    assert db.query(Listing).count() == len(listings)


def test_fallback_search_reports_blocked_and_failures(db):
    from homefinder.db import session_scope
    nap = Pacer(sleep=lambda s: None)
    t = FakeTransport(exc=Blocked("403"))
    assert fallback_search.run(session_scope, transport_factory=lambda: t, pacer=nap) == {"blocked": True} and t.closed
    fallback_search.reset_cooldown()  # a blocked run also starts the cooldown
    t2 = FakeTransport(exc=RuntimeError("boom"))
    assert fallback_search.run(session_scope, transport_factory=lambda: t2, pacer=nap) == {"error": "search_failed"} and t2.closed


def test_fallback_search_does_nothing_while_aqar_is_paused(db):
    from homefinder import adapters_state
    with session_scope() as s:
        adapters_state.pause(s, "aqar", "aqar app-version outdated")
    built = []
    out = fallback_search.run(session_scope, transport_factory=lambda: built.append(1))
    assert out == {"paused": True} and built == []


@pytest.fixture(autouse=True)
def _fresh_cooldown():
    fallback_search.reset_cooldown()
    yield
    fallback_search.reset_cooldown()


def test_fallback_search_runs_at_most_once_per_30_minutes(db, monkeypatch):
    clock = [5000.0]
    monkeypatch.setattr(fallback_search.time, "monotonic", lambda: clock[0])
    nap = Pacer(sleep=lambda s: None)
    assert fallback_search.run(session_scope, transport_factory=lambda: FakeTransport([]), pacer=nap) == {"ingested": 0}
    assert fallback_search.run(session_scope, transport_factory=lambda: FakeTransport([]), pacer=nap) == {"cooldown": True}
    clock[0] += 30 * 60 + 1
    assert fallback_search.run(session_scope, transport_factory=lambda: FakeTransport([]), pacer=nap) == {"ingested": 0}

"""Real-model agent evals (20 cases). Manual: OPENAI_API_KEY=... pytest -m llm tests/agent -v. Skipped without a key."""
import os
import re
import uuid
from pathlib import Path

import pytest
import yaml
from langgraph.checkpoint.memory import InMemorySaver

from homefinder.db import session_scope
from homefinder.models import Listing
from homefinder.scoring import effective_weights
from homefinder.server.agent.graph import build_agent, make_chat_model
from homefinder.server.agent.tools import make_tools

pytestmark = [pytest.mark.llm, pytest.mark.skipif(not os.environ.get("OPENAI_API_KEY"), reason="needs OPENAI_API_KEY")]
CASES = yaml.safe_load((Path(__file__).parent / "evals.yaml").read_text("utf-8"))


def _seed(db):
    for i, (d, price) in enumerate([("النرجس", 1_800_000), ("الياسمين", 2_300_000), ("الملقا", 3_100_000),
                                    ("النرجس", 2_000_000), ("العارض", 1_500_000), ("الملقا", 2_700_000)]):
        db.add(Listing(title=f"فيلا {i}", district=d, price=price, score=90 - i, bedrooms=5, property_type="villa"))
    db.commit()


def _lookup(prefs, dotted: str):
    cur = {"hard_filters": prefs.hard_filters, "weights": effective_weights(prefs.weights)}
    for part in dotted.split("."):
        cur = cur.get(part) if isinstance(cur, dict) else None
    return cur


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_agent_eval(case, db):
    from homefinder import prefs as prefs_mod
    _seed(db)
    if case.get("start_prefs"):
        p = prefs_mod.get_or_create(db)
        p.hard_filters = {**p.hard_filters, **case["start_prefs"]}
        db.commit()
    agent = build_agent(make_chat_model(), make_tools(session_scope), InMemorySaver())
    cfg = {"configurable": {"thread_id": str(uuid.uuid4())}}
    called: set[str] = set()
    for msg in case["messages"]:
        out = agent.invoke({"messages": [{"role": "user", "content": msg}]}, cfg)
        for m in out["messages"]:
            called.update(tc["name"] for tc in getattr(m, "tool_calls", None) or [])
    assert set(case["expect_tools"]) <= called, f"called {called}"
    assert not set(case.get("forbid_tools") or []) & called, f"called {called}"
    db.expire_all()
    p = prefs_mod.get_or_create(db)
    for k, v in (case.get("expect_prefs") or {}).items():
        got = _lookup(p, k)
        assert (sorted(got) == sorted(v)) if isinstance(v, list) else got == v, f"{k}: {got!r} != {v!r}"
    for k, v in (case.get("expect_prefs_contains") or {}).items():
        assert v in (_lookup(p, k) or []), k
    for expr in case.get("expect_prefs_cmp") or []:
        left, op, right = re.match(r"([\w.]+)\s*([<>]=?)\s*([\w.]+)", expr).groups()
        a, b = _lookup(p, left), (_lookup(p, right) if re.match(r"[A-Za-z]", right) else float(right))
        assert a is not None and (a > b if op == ">" else a < b), expr

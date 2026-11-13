import json

import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from tests.agent.fake_model import ScriptedToolModel

BUDGET = "تم الوصول إلى الحد الشهري لاستخدام المساعد"


def events(resp):
    return [json.loads(line[6:]) for line in resp.text.split("\n") if line.startswith("data: ")]


def call(name, args=None, id="c1"):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args or {}, "id": id, "type": "tool_call"}])


@pytest.fixture
def fake_agent(monkeypatch, settings_env):
    from homefinder.server.routes import chat
    saver = InMemorySaver()
    settings_env(OPENAI_API_KEY="sk-test-not-real")

    def factory(script):
        monkeypatch.setattr(chat, "get_checkpointer", lambda: saver)
        monkeypatch.setattr(chat, "make_chat_model", lambda: ScriptedToolModel(script=script))
    return factory


def test_chat_streams_tokens_listings_and_done(db, family, fake_agent):
    from homefinder.models import Listing
    db.add(Listing(title="فيلا", district="النرجس", price=1_500_000, score=80)); db.commit()
    fake_agent([call("search_listings"), AIMessage(content="وجدت فيلا واحدة.")])
    r = family.post("/api/chat", json={"message": "وش عندك؟"})
    assert r.headers["content-type"].startswith("text/event-stream")
    ev = events(r)
    assert ev[0]["type"] == "thread" and ev[-1]["type"] == "done"
    assert any(e["type"] == "tool" and e["name"] == "search_listings" for e in ev)
    lst = [e for e in ev if e["type"] == "listings"]
    assert lst and lst[0]["items"][0]["title"] == "فيلا" and lst[0]["items"][0]["status"] == "active"
    assert "price_drop" in lst[0]["items"][0]
    assert "".join(e["text"] for e in ev if e["type"] == "token") == "وجدت فيلا واحدة."
    assert sum(e["type"] == "token" for e in ev) > 1  # really streamed in pieces
    tid = ev[0]["thread_id"]
    hist = family.get(f"/api/chat/threads/{tid}").json()
    assert hist["id"] == tid and hist["title"] == "وش عندك؟"
    assert [m["role"] for m in hist["messages"]] == ["user", "assistant"]
    assert hist["messages"][0]["text"] == "وش عندك؟" and "listings" not in hist["messages"][0]
    assert hist["messages"][1]["text"] == "وجدت فيلا واحدة."
    assert hist["messages"][1]["listings"][0]["title"] == "فيلا"


def test_event_order_thread_first_tool_before_listings(db, family, fake_agent):
    from homefinder.models import Listing
    db.add(Listing(title="x", score=1)); db.commit()
    fake_agent([call("search_listings"), AIMessage(content="تمام")])
    types = [e["type"] for e in events(family.post("/api/chat", json={"message": "x"}))]
    assert types[0] == "thread" and types[-1] == "done"
    assert types.index("tool") < types.index("listings") < types.index("token")


def test_prefs_changed_event_only_on_successful_update(db, family, fake_agent):
    fake_agent([call("update_preferences", {"hard_filters": {"min_bedrooms": 4}}), AIMessage(content="تم.")])
    assert any(e["type"] == "prefs_changed" for e in events(family.post("/api/chat", json={"message": "٤ غرف"})))
    fake_agent([call("update_preferences", {"hard_filters": {"price_max": 5}}), AIMessage(content="غير ممكن")])
    assert not any(e["type"] == "prefs_changed" for e in events(family.post("/api/chat", json={"message": "x"})))


def test_chat_budget_exceeded(db, family, fake_agent, monkeypatch):
    from homefinder import usage
    def boom(provider, cost): raise usage.BudgetExceeded("cap")
    monkeypatch.setattr(usage, "spend", boom)
    fake_agent([AIMessage(content="should not be called")])
    ev = events(family.post("/api/chat", json={"message": "هلا"}))
    assert [e["type"] for e in ev] == ["thread", "error", "done"]
    assert ev[1] == {"type": "error", "message": BUDGET}


def test_budget_exhausted_mid_run_gives_error_then_done(db, family, fake_agent, monkeypatch):
    from homefinder import usage
    fake_agent([AIMessage(content="hi")])
    calls = {"n": 0}

    def spend(provider, cost):
        calls["n"] += 1
        if calls["n"] > 1:
            raise usage.BudgetExceeded("cap")
    monkeypatch.setattr(usage, "spend", spend)
    from homefinder.server.routes import chat
    class Costly(ScriptedToolModel):
        def _generate(self, messages, stop=None, run_manager=None, **kw):
            usage.spend("openai", 1.0)
            return super()._generate(messages, stop, run_manager, **kw)
        def _stream(self, *a, **k):
            usage.spend("openai", 1.0)
            yield from super()._stream(*a, **k)
    monkeypatch.setattr(chat, "make_chat_model", lambda: Costly(script=[AIMessage(content="hi")]))
    ev = events(family.post("/api/chat", json={"message": "x"}))
    assert ev[-2] == {"type": "error", "message": BUDGET} and ev[-1] == {"type": "done"}


def test_model_failure_gives_arabic_error_then_done(db, family, fake_agent, monkeypatch):
    from homefinder.server.routes import chat

    class Broken(ScriptedToolModel):
        def _stream(self, *a, **k):
            raise RuntimeError("provider down")
            yield
        def _generate(self, *a, **k):
            raise RuntimeError("provider down")
    fake_agent([])
    monkeypatch.setattr(chat, "make_chat_model", lambda: Broken(script=[AIMessage(content="x")]))
    ev = events(family.post("/api/chat", json={"message": "x"}))
    assert ev[-2] == {"type": "error", "message": "حدث خطأ، حاول مرة أخرى"} and ev[-1]["type"] == "done"
    assert "provider down" not in json.dumps(ev, ensure_ascii=False)  # internals are not leaked


def test_chat_requires_login(app_client):
    assert app_client.post("/api/chat", json={"message": "x"}).status_code == 401
    assert app_client.get("/api/chat/threads").status_code == 401
    assert app_client.get("/api/chat/threads/abc").status_code == 401
    assert app_client.post("/api/chat/threads").status_code == 401


def test_chat_validates_message(family, fake_agent):
    assert family.post("/api/chat", json={"message": ""}).status_code == 422
    assert family.post("/api/chat", json={"message": "x" * 2001}).status_code == 422
    assert family.post("/api/chat", json={}).status_code == 422


def test_chat_503_without_openai_key(db, family, settings_env):
    settings_env(OPENAI_API_KEY="")
    r = family.post("/api/chat", json={"message": "x"})
    assert r.status_code == 503 and r.json()["detail"]


def test_chat_client_disconnect(db, family, fake_agent):
    from homefinder.server.routes import chat
    fake_agent([AIMessage(content="رد طويل " * 50)])
    gen = chat._event_stream("مرحبا", None, disconnected=lambda: True)
    first = next(gen)
    assert '"thread"' in first
    assert list(gen) == []  # stops quietly once disconnected


def test_disconnect_midstream_stops_and_keeps_state(db, family, fake_agent):
    from homefinder.server.routes import chat
    fake_agent([AIMessage(content="رد طويل " * 50)])
    state = {"n": 0}

    def gone_after_three() -> bool:
        state["n"] += 1
        return state["n"] > 3
    out = list(chat._event_stream("مرحبا", None, disconnected=gone_after_three))
    assert any('"token"' in x for x in out) and not any('"done"' in x for x in out)


def test_threads_list_create_and_unknown(db, family, fake_agent):
    assert family.get("/api/chat/threads").json() == []
    assert family.get("/api/chat/threads/nope").status_code == 404
    new = family.post("/api/chat/threads").json()["id"]
    assert family.get(f"/api/chat/threads/{new}").json() == {"id": new, "title": "", "messages": []}
    fake_agent([AIMessage(content="أهلاً")])
    ev = events(family.post("/api/chat", json={"message": "مرحبا", "thread_id": new}))
    assert ev[0]["thread_id"] == new  # existing thread reused
    lst = family.get("/api/chat/threads").json()
    assert [t["id"] for t in lst] == [new] and lst[0]["title"] == "مرحبا" and lst[0]["updated_at"]


def test_threads_newest_first_and_capped_at_30(db, family, fake_agent):
    from datetime import UTC, datetime, timedelta
    from homefinder.models import ChatThread
    base = datetime(2026, 1, 1, tzinfo=UTC)
    for i in range(35):
        db.add(ChatThread(id=f"t{i:02d}", title=f"محادثة {i}", updated_at=base + timedelta(minutes=i)))
    db.commit()
    lst = family.get("/api/chat/threads").json()
    assert len(lst) == 30 and lst[0]["id"] == "t34" and lst[-1]["id"] == "t05"


def test_multi_turn_history_keeps_order_and_attaches_listings_to_the_right_message(db, family, fake_agent):
    from homefinder.models import Listing
    db.add(Listing(title="فيلا أ", score=5)); db.commit()
    fake_agent([call("search_listings"), AIMessage(content="هذه فيلا أ")])
    tid = events(family.post("/api/chat", json={"message": "اعرض"}))[0]["thread_id"]
    fake_agent([AIMessage(content="تم")])
    family.post("/api/chat", json={"message": "شكراً", "thread_id": tid})
    msgs = family.get(f"/api/chat/threads/{tid}").json()["messages"]
    assert [(m["role"], m["text"]) for m in msgs] == [("user", "اعرض"), ("assistant", "هذه فيلا أ"),
                                                      ("user", "شكراً"), ("assistant", "تم")]
    assert msgs[1]["listings"][0]["title"] == "فيلا أ" and "listings" not in msgs[3]


def test_app_startup_prepares_checkpointer_only_with_key(settings_env, monkeypatch, db):
    from fastapi.testclient import TestClient
    from homefinder.server import app as app_mod
    calls = []
    monkeypatch.setattr(app_mod, "get_checkpointer", lambda: calls.append(1))
    settings_env(OPENAI_API_KEY="")
    with TestClient(app_mod.create_app()):
        pass
    assert calls == []
    settings_env(OPENAI_API_KEY="sk-test-not-real")
    with TestClient(app_mod.create_app()):
        pass
    assert calls == [1]


def test_chat_history_with_the_real_postgres_checkpointer(db, family, settings_env, monkeypatch):
    """Production wiring: PostgresSaver stores the turn and the history endpoint reads it back without a model."""
    from homefinder.server.agent import graph
    from homefinder.server.routes import chat
    settings_env(OPENAI_API_KEY="sk-test-not-real")
    graph.get_checkpointer.cache_clear()
    monkeypatch.setattr(chat, "make_chat_model", lambda: ScriptedToolModel(script=[AIMessage(content="أهلاً وسهلاً")]))
    try:
        ev = events(family.post("/api/chat", json={"message": "مرحبا"}))
        assert ev[-1]["type"] == "done"
        msgs = family.get(f"/api/chat/threads/{ev[0]['thread_id']}").json()["messages"]
        assert [(m["role"], m["text"]) for m in msgs] == [("user", "مرحبا"), ("assistant", "أهلاً وسهلاً")]
    finally:
        graph.get_checkpointer().conn.close()
        graph.get_checkpointer.cache_clear()


class StrictToolModel(ScriptedToolModel):
    """Like OpenAI: refuses a history where an assistant tool call has no matching tool result."""
    seen: list = []

    def _check(self, messages):
        from langchain_core.messages import AIMessage as AI, ToolMessage
        answered = {m.tool_call_id for m in messages if isinstance(m, ToolMessage)}
        for m in messages:
            if isinstance(m, AI):
                for tc in m.tool_calls:
                    if tc["id"] not in answered:
                        raise ValueError("400: assistant message with 'tool_calls' must be followed by tool messages")
        self.seen.append(list(messages))

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self._check(messages)
        return super()._generate(messages, stop, run_manager, **kwargs)

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        self._check(messages)
        yield from super()._stream(messages, stop, run_manager, **kwargs)


def test_next_turn_works_after_stop_left_a_dangling_tool_call(db, family, monkeypatch, settings_env):
    """I2: «إيقاف» during a tool call checkpoints an AIMessage(tool_calls) with no ToolMessage.
    The next message on that thread must still reach the model with a closed history."""
    from langchain_core.messages import HumanMessage, ToolMessage
    from homefinder.db import session_scope
    from homefinder.server.agent.graph import build_agent
    from homefinder.server.agent.tools import make_tools
    from homefinder.server.routes import chat
    from homefinder.models import ChatThread
    settings_env(OPENAI_API_KEY="sk-test-not-real")
    db.add(ChatThread(id="t-stop", title="x")); db.commit()
    saver = InMemorySaver()
    cfg = {"configurable": {"thread_id": "t-stop"}}
    # turn 1: the route notices the disconnect on the event after the tool ran, before the next checkpoint
    # is written; so consume until the tools update, then drop the stream (what a disconnect does)
    first = StrictToolModel(script=[call("search_listings", id="call-1"), AIMessage(content="never")], seen=[])
    stream = build_agent(first, make_tools(session_scope), saver).stream(
        {"messages": [HumanMessage("وش عندك؟")]}, cfg, stream_mode=["messages", "updates"])
    for mode, _data in stream:
        if mode == "updates" and "tools" in _data:
            break
    stream.close()
    msgs = saver.get_tuple(cfg).checkpoint["channel_values"]["messages"]  # as persisted, pending writes not applied
    assert msgs[-1].tool_calls and not any(isinstance(m, ToolMessage) for m in msgs)  # the broken state
    assert [m.content for m in msgs if isinstance(m, HumanMessage)] == ["وش عندك؟"]

    # turn 2 through the real route code
    second = StrictToolModel(script=[AIMessage(content="تمام، نكمل.")], seen=[])
    monkeypatch.setattr(chat, "get_checkpointer", lambda: saver)
    monkeypatch.setattr(chat, "make_chat_model", lambda: second)
    ev = [json.loads(x[6:]) for x in chat._event_stream("كمّل", "t-stop", lambda: False) if x.startswith("data: ")]
    assert not any(e["type"] == "error" for e in ev), ev
    assert "".join(e["text"] for e in ev if e["type"] == "token") == "تمام، نكمل."
    sent = second.seen[-1]
    closing = [m for m in sent if isinstance(m, ToolMessage)]
    assert [m.tool_call_id for m in closing] == ["call-1"] and "cancelled" in closing[0].content
    assert isinstance(sent[-1], HumanMessage) and sent[-1].content == "كمّل"

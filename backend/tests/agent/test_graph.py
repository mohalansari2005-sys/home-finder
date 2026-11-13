from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from homefinder.db import session_scope
from homefinder.models import Preferences
from homefinder.server.agent.graph import build_agent
from homefinder.server.agent.tools import make_tools
from tests.agent.fake_model import ScriptedToolModel


def test_agent_updates_preferences_and_answers(db):
    model = ScriptedToolModel(script=[
        AIMessage(content="", tool_calls=[{"name": "update_preferences", "args": {"hard_filters": {"price_max": 1_800_000}},
                                           "id": "c1", "type": "tool_call"}]),
        AIMessage(content="تم تحديد الميزانية بـ 1,800,000 ريال."),
    ])
    agent = build_agent(model, make_tools(session_scope), InMemorySaver())
    out = agent.invoke({"messages": [{"role": "user", "content": "ميزانيتنا مليون وثمانمية"}]},
                       {"configurable": {"thread_id": "t1"}})
    assert out["messages"][-1].content.startswith("تم")
    db.expire_all()
    assert db.get(Preferences, 1).hard_filters["price_max"] == 1_800_000


def test_agent_survives_invalid_tool_args_and_keeps_prefs(db):
    """The tool returns a readable error to the model; the model then answers; preferences stay unchanged."""
    model = ScriptedToolModel(script=[
        AIMessage(content="", tool_calls=[{"name": "update_preferences", "args": {"hard_filters": {"price_max": 5}},
                                           "id": "c1", "type": "tool_call"}]),
        AIMessage(content="القيمة غير منطقية، ما حدّثت شيء."),
    ])
    agent = build_agent(model, make_tools(session_scope), InMemorySaver())
    out = agent.invoke({"messages": [{"role": "user", "content": "ميزانيتنا خمسة"}]}, {"configurable": {"thread_id": "t2"}})
    tool_msg = [m for m in out["messages"] if m.type == "tool"][0]
    assert '"ok": false' in tool_msg.content
    db.expire_all()
    assert db.get(Preferences, 1) is None or db.get(Preferences, 1).hard_filters.get("price_max") is None


def test_postgres_checkpointer_persists_conversation(db):
    """The real PostgresSaver (what production uses) stores and returns the conversation."""
    from homefinder.server.agent import graph
    graph.get_checkpointer.cache_clear()
    saver = graph.get_checkpointer()
    try:
        model = ScriptedToolModel(script=[AIMessage(content="أهلاً بكم")])
        agent = build_agent(model, make_tools(session_scope), saver)
        cfg = {"configurable": {"thread_id": f"pg-{__import__('uuid').uuid4()}"}}
        agent.invoke({"messages": [{"role": "user", "content": "مرحبا"}]}, cfg)
        msgs = build_agent(model, make_tools(session_scope), saver).get_state(cfg).values["messages"]
        assert [m.type for m in msgs] == ["human", "ai"] and msgs[1].content == "أهلاً بكم"
    finally:
        saver.conn.close()
        graph.get_checkpointer.cache_clear()

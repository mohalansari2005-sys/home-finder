import json
import logging
import uuid
from collections.abc import Callable, Iterator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.concurrency import iterate_in_threadpool

from homefinder import usage
from homefinder.config import get_settings
from homefinder.db import session_scope
from homefinder.models import ChatThread
from homefinder.server.agent.costs import UsageCallback
from homefinder.server.agent.graph import build_agent, get_checkpointer, make_chat_model
from homefinder.server.agent.tools import make_tools
from homefinder.server.deps import get_db, require_family

log = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(require_family)])
BUDGET_MSG = "تم الوصول إلى الحد الشهري لاستخدام المساعد"
ERROR_MSG = "حدث خطأ، حاول مرة أخرى"
NO_KEY_MSG = "المساعد غير مفعّل: لم يتم ضبط مفتاح OpenAI"
LISTING_TOOLS = {"search_listings", "get_listing", "compare_listings"}
THREAD_LIST_LIMIT = 30


class ChatBody(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    thread_id: str | None = None


def _sse(o: dict) -> str:
    return f"data: {json.dumps(o, ensure_ascii=False)}\n\n"


def _text(content) -> str:
    """Message content is a string, or a list of blocks for some models."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(b if isinstance(b, str) else b.get("text", "") for b in content
                       if isinstance(b, str) or (isinstance(b, dict) and b.get("type") == "text"))
    return ""


def _ensure_thread(thread_id: str | None, first_message: str) -> str:
    with session_scope() as s:
        t = s.get(ChatThread, thread_id) if thread_id else None
        if t is not None:
            t.updated_at = func.now()
            if not t.title:
                t.title = first_message[:60]
            return t.id
        tid = str(uuid.uuid4())
        s.add(ChatThread(id=tid, title=first_message[:60]))
        return tid


def _tool_payload(m: ToolMessage) -> dict:
    try:
        out = json.loads(m.content) if isinstance(m.content, str) and m.content.startswith("{") else {}
    except ValueError:
        return {}
    return out if isinstance(out, dict) else {}


def _close_dangling_tool_calls(agent, config) -> None:
    """A stop/disconnect can checkpoint an AIMessage(tool_calls) whose tool results were dropped; OpenAI then
    rejects every later turn on that thread. Answer each orphaned call with a 'cancelled' tool result."""
    # Read the persisted checkpoint, not agent.get_state(): get_state overlays the unfinished tools task's
    # pending writes, which the next run discards, so it would report the call as answered.
    tup = agent.checkpointer.get_tuple(config)
    msgs = ((tup.checkpoint.get("channel_values") or {}).get("messages") or []) if tup else []
    answered = {m.tool_call_id for m in msgs if isinstance(m, ToolMessage)}
    last_ai = next((m for m in reversed(msgs) if isinstance(m, AIMessage)), None)
    if last_ai is None:
        return
    missing = [tc for tc in last_ai.tool_calls if tc["id"] not in answered]
    if missing:
        agent.update_state(config, {"messages": [
            ToolMessage(content='{"error": "cancelled by user"}', tool_call_id=tc["id"], name=tc["name"])
            for tc in missing]}, as_node="tools")


def _event_stream(message: str, thread_id: str | None, disconnected: Callable[[], bool]) -> Iterator[str]:
    tid = _ensure_thread(thread_id, message)
    yield _sse({"type": "thread", "thread_id": tid})
    if disconnected():
        return
    try:
        usage.spend("openai", 0.0)  # budget check before any model call
    except usage.BudgetExceeded:
        yield _sse({"type": "error", "message": BUDGET_MSG})
        yield _sse({"type": "done"})
        return
    try:
        agent = build_agent(make_chat_model(), make_tools(session_scope), get_checkpointer())
        config = {"configurable": {"thread_id": tid}, "callbacks": [UsageCallback()]}
        _close_dangling_tool_calls(agent, config)
        for mode, data in agent.stream({"messages": [HumanMessage(message)]}, config, stream_mode=["messages", "updates"]):
            if disconnected():
                return  # state up to the last completed step is already checkpointed
            if mode == "messages":
                chunk, _meta = data
                if isinstance(chunk, AIMessageChunk) and chunk.content and not chunk.tool_call_chunks:
                    text = _text(chunk.content)
                    if text:
                        yield _sse({"type": "token", "text": text})
            elif mode == "updates":
                for _node, upd in data.items():
                    for m in (upd or {}).get("messages", []):
                        if isinstance(m, AIMessage):
                            for tc in m.tool_calls:
                                yield _sse({"type": "tool", "name": tc["name"]})
                        elif isinstance(m, ToolMessage):
                            payload = _tool_payload(m)
                            if m.name in LISTING_TOOLS and payload.get("cards"):
                                yield _sse({"type": "listings", "items": payload["cards"]})
                            if m.name == "update_preferences" and payload.get("ok"):
                                yield _sse({"type": "prefs_changed"})
    except usage.BudgetExceeded:
        yield _sse({"type": "error", "message": BUDGET_MSG})
    except Exception:  # noqa: BLE001 — never leak provider/internal details to the browser
        log.exception("chat failed")
        yield _sse({"type": "error", "message": ERROR_MSG})
    yield _sse({"type": "done"})


@router.post("/chat")
async def chat(body: ChatBody, request: Request):
    if not get_settings().openai_api_key:
        raise HTTPException(503, NO_KEY_MSG)
    state = {"gone": False}

    async def watch():
        async for chunk in iterate_in_threadpool(_event_stream(body.message, body.thread_id, lambda: state["gone"])):
            if await request.is_disconnected():
                state["gone"] = True
                break
            yield chunk

    return StreamingResponse(watch(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/chat/threads")
def list_threads(s: Session = Depends(get_db)):
    rows = s.scalars(select(ChatThread).where(ChatThread.title != "")
                     .order_by(ChatThread.updated_at.desc(), ChatThread.id.desc()).limit(THREAD_LIST_LIMIT))
    return [{"id": t.id, "title": t.title, "updated_at": t.updated_at.isoformat()} for t in rows]


@router.post("/chat/threads")
def create_thread(s: Session = Depends(get_db)):
    tid = str(uuid.uuid4())
    s.add(ChatThread(id=tid, title=""))
    return {"id": tid}


def _history(messages: list) -> list[dict]:
    """User and assistant turns; cards from listing tools attach to the assistant message that follows them."""
    out: list[dict] = []
    pending: list[dict] = []
    for m in messages:
        if isinstance(m, HumanMessage):
            out.append({"role": "user", "text": _text(m.content)})
            pending = []
        elif isinstance(m, ToolMessage):
            if m.name in LISTING_TOOLS:
                pending += _tool_payload(m).get("cards") or []
        elif isinstance(m, AIMessage) and _text(m.content).strip():
            item = {"role": "assistant", "text": _text(m.content)}
            if pending:
                item["listings"] = pending
                pending = []
            out.append(item)
    return out


@router.get("/chat/threads/{thread_id}")
def get_thread(thread_id: str, s: Session = Depends(get_db)):
    t = s.get(ChatThread, thread_id)
    if t is None:
        raise HTTPException(404)
    tup = get_checkpointer().get_tuple({"configurable": {"thread_id": thread_id}})  # no model call, no model needed
    messages = ((tup.checkpoint.get("channel_values") or {}).get("messages") or []) if tup else []
    return {"id": t.id, "title": t.title, "messages": _history(messages)}

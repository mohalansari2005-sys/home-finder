import json

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult


class ScriptedToolModel(BaseChatModel):
    """Returns pre-scripted AIMessages in order; supports bind_tools for agent graphs.

    `_stream` splits text into small chunks (like a real streaming model) so SSE token tests see several tokens."""
    script: list[AIMessage]
    i: int = 0
    chunk_size: int = 6

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, **kwargs):
        return self

    def _next(self) -> AIMessage:
        msg = self.script[min(self.i, len(self.script) - 1)]
        self.i += 1
        return msg

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=self._next())])

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        msg = self._next()
        text = msg.content if isinstance(msg.content, str) else ""
        for k in range(0, len(text), self.chunk_size):
            piece = text[k:k + self.chunk_size]
            if run_manager:
                run_manager.on_llm_new_token(piece)
            yield ChatGenerationChunk(message=AIMessageChunk(content=piece))
        for n, tc in enumerate(msg.tool_calls):
            yield ChatGenerationChunk(message=AIMessageChunk(content="", tool_call_chunks=[
                {"name": tc["name"], "args": json.dumps(tc["args"]), "id": tc["id"], "index": n}]))

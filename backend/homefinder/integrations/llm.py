import json
from collections.abc import Callable
from typing import Protocol

from homefinder import usage
from homefinder.config import get_settings


class LLMClient(Protocol):
    def extract_json(self, *, system: str, user: str, schema: dict, name: str) -> dict: ...


class OpenAIClient:
    def __init__(self, api_key: str, model_small: str, model_large: str, price_in: float, price_out: float,
                 spend: Callable[[float], None] | None = None, client=None):
        if client is None:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
        self._c, self.model_small, self.model_large = client, model_small, model_large
        self._pin, self._pout = price_in, price_out
        self._spend = spend or (lambda c: usage.spend("openai", c))

    def extract_json(self, *, system: str, user: str, schema: dict, name: str) -> dict:
        self._spend(0.0)  # budget check
        resp = self._c.chat.completions.create(
            model=self.model_small,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            response_format={"type": "json_schema", "json_schema": {"name": name, "schema": schema, "strict": True}},
        )
        u = resp.usage
        self._spend(u.prompt_tokens * self._pin / 1e6 + u.completion_tokens * self._pout / 1e6)
        return json.loads(resp.choices[0].message.content)


def make_llm() -> OpenAIClient | None:
    st = get_settings()
    if not st.openai_api_key:
        return None
    return OpenAIClient(st.openai_api_key, st.openai_model_small, st.openai_model_large,
                        st.openai_price_in_small, st.openai_price_out_small)

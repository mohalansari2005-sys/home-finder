from types import SimpleNamespace

from homefinder.integrations.llm import OpenAIClient


class FakeCompletions:
    def __init__(self): self.kwargs = None
    def create(self, **kw):
        self.kwargs = kw
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"bedrooms": 5}'))],
                               usage=SimpleNamespace(prompt_tokens=1_000_000, completion_tokens=0))


def test_extract_json_uses_strict_schema_and_records_cost():
    comp = FakeCompletions()
    fake = SimpleNamespace(chat=SimpleNamespace(completions=comp))
    spent = []
    c = OpenAIClient("k", "small-m", "large-m", price_in=0.25, price_out=2.0, spend=spent.append, client=fake)
    out = c.extract_json(system="s", user="u", schema={"type": "object"}, name="listing")
    assert out == {"bedrooms": 5}
    assert comp.kwargs["model"] == "small-m"
    assert comp.kwargs["response_format"]["json_schema"]["strict"] is True
    assert spent == [0.0, 0.25]

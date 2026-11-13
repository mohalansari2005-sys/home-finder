from langchain_core.callbacks import BaseCallbackHandler

from homefinder import usage
from homefinder.config import get_settings


class UsageCallback(BaseCallbackHandler):
    """Records the cost of every model call at large-model prices. BudgetExceeded must stop the run, so errors propagate."""
    raise_error = True

    def on_llm_end(self, response, **kwargs):
        st = get_settings()
        for gens in response.generations:
            for g in gens:
                um = getattr(getattr(g, "message", None), "usage_metadata", None) or {}
                cost = (um.get("input_tokens", 0) * st.openai_price_in_large
                        + um.get("output_tokens", 0) * st.openai_price_out_large) / 1e6
                if cost:
                    usage.spend("openai", cost)

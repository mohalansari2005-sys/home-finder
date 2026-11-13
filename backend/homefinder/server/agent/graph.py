from functools import lru_cache

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg_pool import ConnectionPool

from homefinder.config import get_settings
from homefinder.server.agent.prompts import SYSTEM_PROMPT


def build_agent(model, tools, checkpointer):
    return create_agent(model, tools=tools, system_prompt=SYSTEM_PROMPT, checkpointer=checkpointer)


def make_chat_model() -> ChatOpenAI:
    st = get_settings()
    return ChatOpenAI(model=st.openai_model_large, api_key=st.openai_api_key, streaming=True, stream_usage=True)


@lru_cache
def get_checkpointer() -> PostgresSaver:
    url = get_settings().database_url.replace("postgresql+psycopg://", "postgresql://")
    pool = ConnectionPool(url, min_size=1, max_size=3, open=True, kwargs={"autocommit": True, "prepare_threshold": 0})
    saver = PostgresSaver(pool)
    saver.setup()
    return saver

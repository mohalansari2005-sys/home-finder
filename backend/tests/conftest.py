import os

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://hf:hf@localhost:55432/hf_test")

import pytest
from sqlalchemy import text

from homefinder.config import get_settings
from homefinder.db import SessionLocal, get_engine
from homefinder.models import Base


@pytest.fixture(scope="session", autouse=True)
def _schema():
    eng = get_engine()
    with eng.begin() as c:
        c.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield


@pytest.fixture
def db():
    eng = get_engine()
    names = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with eng.begin() as c:
        c.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


@pytest.fixture
def settings_env(monkeypatch):
    """Set env vars, then rebuild cached settings. Usage: settings_env(OPENAI_MONTHLY_CAP_USD='1')."""
    def _set(**kv):
        for k, v in kv.items():
            monkeypatch.setenv(k, str(v))
        get_settings.cache_clear()
        return get_settings()
    yield _set
    get_settings.cache_clear()

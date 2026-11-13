import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from homefinder.config import get_settings
from homefinder.server import auth
from homefinder.server.agent.graph import get_checkpointer
from homefinder.server.routes import chat, listings, settings, status, suggestions, visits, worker

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if get_settings().openai_api_key:
        try:
            get_checkpointer()  # creates the checkpoint tables once
        except Exception:  # noqa: BLE001 — the rest of the API must still start; chat retries lazily
            log.exception("chat checkpointer setup failed")
    yield


_PLACEHOLDERS = ("dev-only-change-me", "dev-worker-token")


def _weak(v: str) -> bool:
    return not v or v.startswith("CHANGE_ME") or v in _PLACEHOLDERS or len(v) < 32


def check_production_secrets(st) -> None:
    """The repo is public: a default or example secret would let anyone forge a family session."""
    bad = [name for name, v in (("SESSION_SECRET", st.session_secret), ("WORKER_TOKEN", st.worker_token)) if _weak(v)]
    if not st.family_password_hash:
        bad.append("FAMILY_PASSWORD_HASH")
    if bad:
        raise RuntimeError("refusing to start: set a real " + ", ".join(bad)
                           + " in .env (SESSION_SECRET and WORKER_TOKEN need at least 32 random characters)")


def create_app() -> FastAPI:
    st = get_settings()
    if st.cookie_secure:  # production
        check_production_secrets(st)
    app = FastAPI(title="Home Finder", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.add_middleware(SessionMiddleware, secret_key=st.session_secret, session_cookie="hf_session",
                       max_age=90 * 24 * 3600, same_site="lax", https_only=st.cookie_secure)
    app.include_router(auth.router, prefix="/api")
    app.include_router(listings.router, prefix="/api")
    app.include_router(settings.router, prefix="/api")
    app.include_router(status.router, prefix="/api")
    app.include_router(chat.router, prefix="/api")
    app.include_router(suggestions.router, prefix="/api")
    app.include_router(visits.router, prefix="/api")
    app.include_router(worker.router, prefix="/worker")

    @app.get("/api/health")
    def health():
        return {"ok": True}

    if st.serve_photos:
        Path(st.photos_dir).mkdir(parents=True, exist_ok=True)
        app.mount("/photos", StaticFiles(directory=st.photos_dir), name="photos")
    return app


app = create_app()

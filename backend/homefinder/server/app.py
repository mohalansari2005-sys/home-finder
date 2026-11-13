import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from homefinder.config import get_settings
from homefinder.server import auth
from homefinder.server.agent.graph import get_checkpointer
from homefinder.server.routes import chat, listings, settings, status, suggestions, worker

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if get_settings().openai_api_key:
        try:
            get_checkpointer()  # creates the checkpoint tables once
        except Exception:  # noqa: BLE001 — the rest of the API must still start; chat retries lazily
            log.exception("chat checkpointer setup failed")
    yield


def create_app() -> FastAPI:
    st = get_settings()
    app = FastAPI(title="Home Finder", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.add_middleware(SessionMiddleware, secret_key=st.session_secret, session_cookie="hf_session",
                       max_age=90 * 24 * 3600, same_site="lax", https_only=st.cookie_secure)
    app.include_router(auth.router, prefix="/api")
    app.include_router(listings.router, prefix="/api")
    app.include_router(settings.router, prefix="/api")
    app.include_router(status.router, prefix="/api")
    app.include_router(chat.router, prefix="/api")
    app.include_router(suggestions.router, prefix="/api")
    app.include_router(worker.router, prefix="/worker")

    @app.get("/api/health")
    def health():
        return {"ok": True}

    if st.serve_photos:
        Path(st.photos_dir).mkdir(parents=True, exist_ok=True)
        app.mount("/photos", StaticFiles(directory=st.photos_dir), name="photos")
    return app


app = create_app()

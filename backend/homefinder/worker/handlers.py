import logging
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from homefinder import adapters_state
from homefinder.schemas import SearchQuery
from homefinder.worker.ingest import ingest_raw
from homefinder.worker.sources.aqar_transport import AppVersionOutdated

log = logging.getLogger(__name__)


@dataclass
class WorkerDeps:
    session_factory: Callable[[], AbstractContextManager[Session]]
    adapters: dict[str, Callable[[], Any]]
    llm: Any
    google: Any
    photo_sink: Any
    http: Any


def handle_scrape_search(deps: WorkerDeps, payload: dict) -> dict:
    source = payload["source"]
    with deps.session_factory() as s:
        if adapters_state.is_paused(s, source):
            return {"skipped": "paused"}
    adapter = deps.adapters[source]()
    try:
        raws = list(adapter.search(SearchQuery(**payload.get("query", {}))))
    except AppVersionOutdated as e:
        log.error("%s: %s", source, e)
        with deps.session_factory() as s:
            adapters_state.pause(s, source, f"{source} app-version outdated")
        return {"skipped": "app_version_outdated"}
    finally:
        close = getattr(getattr(adapter, "_t", None), "close", None)
        if close:
            close()
    report = adapter.health(raws)
    if not report.ok:
        with deps.session_factory() as s:
            adapters_state.pause(s, source, report.reason or "unhealthy")
        return {"skipped": "unhealthy", "reason": report.reason, "fetched": len(raws)}
    new = 0
    for raw in raws:
        with deps.session_factory() as s:
            new += ingest_raw(s, raw).created
    with deps.session_factory() as s:
        adapters_state.mark_ok(s, source)
    return {"fetched": len(raws), "ingested": len(raws), "new": new}


HANDLERS: dict[str, Callable[[WorkerDeps, dict], dict]] = {
    "scrape_search": handle_scrape_search,
}


def dispatch(deps: WorkerDeps, job_type: str, payload: dict) -> dict:
    handler = HANDLERS.get(job_type)
    if handler is None:
        raise ValueError(f"unknown job type {job_type}")
    return handler(deps, payload)

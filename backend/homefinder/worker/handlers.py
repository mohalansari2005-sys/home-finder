import logging
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from homefinder import adapters_state, prefs
from homefinder.models import Listing
from homefinder.rescore import apply_score, rescore_all
from homefinder.schemas import SearchQuery
from homefinder.worker.enrich.commute import compute_commutes
from homefinder.worker.enrich.pipeline import enrich_listing
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
    if payload.get("from_prefs"):
        with deps.session_factory() as s:
            query = SearchQuery.from_hard_filters(prefs.get_or_create(s).hard_filters)
    else:
        query = SearchQuery(**payload.get("query", {}))
    adapter = deps.adapters[source]()
    try:
        raws = list(adapter.search(query))
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


def handle_rescore_all(deps: WorkerDeps, payload: dict) -> dict:
    with deps.session_factory() as s:
        return {"rescored": rescore_all(s)}


def handle_recompute_commutes(deps: WorkerDeps, payload: dict) -> dict:
    if deps.google is None:
        return {"skipped": "no google key"}
    n = 0
    with deps.session_factory() as s:
        ids = list(s.scalars(select(Listing.id).where(Listing.lat.is_not(None), Listing.merged_into_id.is_(None))))
    for lid in ids:
        with deps.session_factory() as s:
            l = s.get(Listing, lid)
            l.commutes = compute_commutes(s, deps.google, l)
            apply_score(l, prefs.get_or_create(s))
            n += 1
    return {"listings": n}


HANDLERS: dict[str, Callable[[WorkerDeps, dict], dict]] = {
    "scrape_search": handle_scrape_search,
    "rescore_all": handle_rescore_all,
    "recompute_commutes": handle_recompute_commutes,
    "enrich_listing": lambda deps, p: enrich_listing(deps, p["listing_id"]),
}


def dispatch(deps: WorkerDeps, job_type: str, payload: dict) -> dict:
    handler = HANDLERS.get(job_type)
    if handler is None:
        raise ValueError(f"unknown job type {job_type}")
    return handler(deps, payload)

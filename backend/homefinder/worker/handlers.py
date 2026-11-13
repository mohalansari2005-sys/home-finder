import logging
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from homefinder import adapters_state, prefs
from homefinder.models import Listing, ListingSource
from homefinder.rescore import apply_score, rescore_all
from homefinder.schemas import SearchQuery
from homefinder.worker.enrich.commute import compute_commutes
from homefinder.worker.enrich.pipeline import enrich_listing
from homefinder.worker.ingest import ingest_raw
from homefinder.worker.sources.aqar_transport import AppVersionOutdated, Blocked

log = logging.getLogger(__name__)


@dataclass
class WorkerDeps:
    session_factory: Callable[[], AbstractContextManager[Session]]
    adapters: dict[str, Callable[[], Any]]
    llm: Any
    maps: Any
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
    adapter = deps.adapters[source]()  # a process-lifetime singleton: its pacer and session persist across jobs
    try:
        raws = list(adapter.search(query))
    except AppVersionOutdated as e:
        log.error("%s: %s", source, e)
        with deps.session_factory() as s:
            adapters_state.pause(s, source, f"{source} app-version outdated")
        return {"skipped": "app_version_outdated"}
    except Blocked as e:  # every transport (curl_cffi, then Playwright) was refused: stop hammering the site
        log.error("%s blocked: %s", source, e)
        with deps.session_factory() as s:
            adapters_state.pause(s, source, f"{source} blocked: {e}"[:200])
        return {"skipped": "blocked"}
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
    if deps.maps is None:
        return {"skipped": "no tomtom key"}
    n = 0
    with deps.session_factory() as s:
        ids = list(s.scalars(select(Listing.id).where(
            Listing.lat.is_not(None), Listing.merged_into_id.is_(None), Listing.status == "active",
            Listing.family_status != "rejected")))  # removed/rejected listings are never shown: don't pay to route them
    for lid in ids:
        with deps.session_factory() as s:
            l = s.get(Listing, lid)
            l.commutes = compute_commutes(s, deps.maps, l)
            apply_score(l, prefs.get_or_create(s))
            n += 1
    return {"listings": n}


def handle_refresh_listing(deps: WorkerDeps, payload: dict) -> dict:
    """Re-fetch one stale listing by id. Gone from every source -> status 'removed'; otherwise ingest (last_seen, price)."""
    lid = payload["listing_id"]
    with deps.session_factory() as s:
        l = s.get(Listing, lid)
        if l is None or l.merged_into_id or l.status != "active":
            return {"skipped": "gone"}
        sources = [(x.source, x.source_id) for x in s.scalars(
            select(ListingSource).where(ListingSource.listing_id == lid).order_by(ListingSource.id))]
        paused = [src for src, _ in sources if adapters_state.is_paused(s, src)]
    live = [(src, sid) for src, sid in sources if src in deps.adapters and src not in paused]
    if not live:
        return {"skipped": "paused" if paused else "no_adapter"}
    refreshed = None
    for src, sid in live:
        adapter = deps.adapters[src]()
        try:
            raw = adapter.fetch(sid)
        except AppVersionOutdated as e:
            log.error("%s: %s", src, e)
            with deps.session_factory() as s:
                adapters_state.pause(s, src, f"{src} app-version outdated")
            return {"skipped": "app_version_outdated"}
        except Blocked as e:
            log.error("%s blocked: %s", src, e)
            with deps.session_factory() as s:
                adapters_state.pause(s, src, f"{src} blocked: {e}"[:200])
            return {"skipped": "blocked"}
        if raw is not None:
            with deps.session_factory() as s:
                res = ingest_raw(s, raw)
            refreshed = {"refreshed": True, "price_changed": res.price_changed}
            break
    if refreshed:
        return refreshed
    if len(live) < len(sources):  # a paused/unknown source might still have it: don't call it removed
        return {"skipped": "paused" if paused else "no_adapter"}
    with deps.session_factory() as s:
        s.get(Listing, lid).status = "removed"
    return {"removed": True}


def handle_fetch_missing_photos(deps: WorkerDeps, payload: dict) -> dict:
    """Catch-up for listings that became visible after their first enrichment (at most 50 per run)."""
    from homefinder.worker.enrich.photos import fetch_photos
    from homefinder.worker.scheduler import missing_photo_ids

    if deps.photo_sink is None or deps.http is None:
        return {"skipped": "no sink"}
    with deps.session_factory() as s:
        ids = missing_photo_ids(s)
    done = photos = 0
    for lid in ids:
        with deps.session_factory() as s:
            urls = next((u for u in s.scalars(select(ListingSource.photo_urls).where(
                ListingSource.listing_id == lid).order_by(ListingSource.id)) if u), [])
        photos += fetch_photos(deps.http, deps.photo_sink, lid, urls)
        with deps.session_factory() as s:
            s.get(Listing, lid).photos_fetched = True
        done += 1
    return {"listings": done, "photos": photos}


def handle_learn(deps: WorkerDeps, payload: dict) -> dict:
    from homefinder.learner import run_learn  # sklearn is imported only when the job runs

    with deps.session_factory() as s:
        return run_learn(s)


def handle_precheck_trip(deps: WorkerDeps, payload: dict) -> dict:
    from homefinder.worker.precheck import run_precheck  # precheck builds on handle_refresh_listing above

    return run_precheck(deps, payload["trip_id"])


HANDLERS: dict[str, Callable[[WorkerDeps, dict], dict]] = {
    "scrape_search": handle_scrape_search,
    "refresh_listing": handle_refresh_listing,
    "rescore_all": handle_rescore_all,
    "learn": handle_learn,
    "precheck_trip": handle_precheck_trip,
    "recompute_commutes": handle_recompute_commutes,
    "fetch_missing_photos": handle_fetch_missing_photos,
    "enrich_listing": lambda deps, p: enrich_listing(deps, p["listing_id"], p.get("attempt", 0)),
}


def dispatch(deps: WorkerDeps, job_type: str, payload: dict) -> dict:
    handler = HANDLERS.get(job_type)
    if handler is None:
        raise ValueError(f"unknown job type {job_type}")
    return handler(deps, payload)

import logging
from datetime import timedelta

from sqlalchemy import func, select

from homefinder import jobs, prefs
from homefinder.dedupe import dedupe_and_merge
from homefinder.models import Listing, ListingSource
from homefinder.rescore import apply_score
from homefinder.usage import BudgetExceeded
from homefinder.worker.enrich.commute import compute_commutes
from homefinder.worker.enrich.extract import extract_missing
from homefinder.worker.enrich.geo import ensure_location
from homefinder.worker.enrich.photos import fetch_photos

log = logging.getLogger(__name__)
RETRY_DELAY = timedelta(hours=6)


def enrich_listing(deps, listing_id: int) -> dict:
    requeue = False
    with deps.session_factory() as s:
        l = s.get(Listing, listing_id)
        if l is None or l.merged_into_id:
            return {"skipped": True}
        steps = []
        if deps.llm is not None:
            steps.append(("extract", lambda: [setattr(l, k, v) for k, v in extract_missing(deps.llm, l).items()]))
        steps.append(("geo", lambda: ensure_location(deps.google, l)))
        for name, step in steps:
            try:
                step()
            except BudgetExceeded as e:
                log.warning("enrich %s: %s skipped: %s", listing_id, name, e)
                requeue = True
            except Exception as e:  # noqa: BLE001 — provider outage: keep partial data, retry later
                log.warning("enrich %s: %s failed: %s", listing_id, name, e)
                requeue = True
        if l.lat is not None and deps.google is not None:
            try:
                l.commutes = compute_commutes(s, deps.google, l)
            except Exception as e:  # noqa: BLE001
                log.warning("enrich %s: commute failed: %s", listing_id, e)
                requeue = True
        apply_score(l, prefs.get_or_create(s))
        l.enriched_at = func.now()
        need_photos = not l.photos_fetched and deps.photo_sink is not None and deps.http is not None
        urls = next((src.photo_urls for src in s.scalars(select(ListingSource).where(
            ListingSource.listing_id == listing_id)) if src.photo_urls), [])
        commutes = len(l.commutes or {})
        if requeue:
            jobs.enqueue(s, "enrich_listing", {"listing_id": listing_id},
                         dedupe_key=f"enrich-retry:{listing_id}", delay=RETRY_DELAY)
    photos = 0
    if need_photos and urls:
        photos = fetch_photos(deps.http, deps.photo_sink, listing_id, urls)
        with deps.session_factory() as s:
            s.get(Listing, listing_id).photos_fetched = True
    result = {"commutes": commutes, "photos": photos, "requeued": requeue}
    try:
        with deps.session_factory() as s:
            keep = dedupe_and_merge(s, listing_id)
            if keep:
                apply_score(s.get(Listing, keep), prefs.get_or_create(s))
                result["merged_into"] = keep
    except Exception as e:  # noqa: BLE001 — a dedupe problem must not fail enrichment; it is retried on the next enrich
        log.warning("enrich %s: dedupe failed: %s", listing_id, e)
    return result

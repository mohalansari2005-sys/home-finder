from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from homefinder import adapters_state, jobs
from homefinder.models import Job, Listing, ListingSource

ENABLED_SOURCES: list[str] = ["aqar", "haraj"]


def enqueue_stale_refreshes(s: Session, older_than: timedelta = timedelta(days=3), limit: int = 30) -> int:
    """Queue `refresh_listing` for active listings not seen by a scrape for `older_than`, oldest first."""
    ids = list(s.scalars(select(Listing.id).where(
        Listing.status == "active", Listing.merged_into_id.is_(None), Listing.last_seen < func.now() - older_than)
        .order_by(Listing.last_seen, Listing.id).limit(limit)))
    return sum(jobs.enqueue(s, "refresh_listing", {"listing_id": i}, dedupe_key=f"refresh:{i}") is not None for i in ids)


def missing_photo_ids(s: Session, limit: int = 50) -> list[int]:
    """Visible listings whose photos were never fetched (they were filtered out when first enriched)."""
    has_urls = select(ListingSource.id).where(ListingSource.listing_id == Listing.id,
                                              func.jsonb_array_length(ListingSource.photo_urls) > 0).exists()
    return list(s.scalars(select(Listing.id).where(
        Listing.status == "active", Listing.merged_into_id.is_(None), Listing.passes_filters.is_(True),
        Listing.family_status != "rejected", Listing.photos_fetched.is_(False), has_urls)
        .order_by(Listing.score.desc().nulls_last(), Listing.id).limit(limit)))


def enqueue_missing_photos(s: Session) -> int:
    if not missing_photo_ids(s, 1):
        return 0
    return int(jobs.enqueue(s, "fetch_missing_photos", {}, dedupe_key="fetch-missing-photos") is not None)


def maybe_schedule(s: Session, interval_hours: float) -> int:
    n = 0
    for source in ENABLED_SOURCES:
        if adapters_state.is_paused(s, source):
            continue
        last = s.scalar(select(func.max(Job.created_at)).where(
            Job.type == "scrape_search", Job.payload["source"].astext == source,
            Job.payload["scheduled"].astext == "true"))
        if last is not None and s.scalar(select(func.now())) - last < timedelta(hours=interval_hours):
            continue
        if jobs.enqueue(s, "scrape_search", {"source": source, "from_prefs": True, "scheduled": True},
                        dedupe_key=f"scrape:{source}") is not None:
            n += 1
    if n:
        enqueue_stale_refreshes(s)
        enqueue_missing_photos(s)
    return n

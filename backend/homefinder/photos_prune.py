"""Delete downloaded photos of listings nobody will look at again (runs on the server, from cron)."""
import logging
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from homefinder.models import Listing, Photo, Reaction

log = logging.getLogger(__name__)


def prune_photos(s: Session, photos_dir: str | Path, days: int = 30) -> int:
    """Photos of listings that are removed or merged away (not seen for `days`) or were rejected `days` ago.
    Bookmarked and visited listings keep theirs. Returns the number of listings pruned."""
    cutoff = func.now() - func.make_interval(0, 0, 0, days)
    gone = select(Listing.id).where(
        Listing.family_status.notin_(["bookmarked", "visited", "rejected"]), Listing.last_seen < cutoff,
        (Listing.status == "removed") | Listing.merged_into_id.is_not(None))
    last_reject = (select(Reaction.listing_id).where(Reaction.kind == "reject").group_by(Reaction.listing_id)
                   .having(func.max(Reaction.created_at) < cutoff))
    rejected = select(Listing.id).where(Listing.family_status == "rejected", Listing.id.in_(last_reject))
    ids = set(s.scalars(select(Photo.listing_id).where(Photo.listing_id.in_(gone) | Photo.listing_id.in_(rejected))
                        .distinct()))
    root = Path(photos_dir)
    for lid in ids:
        for path in s.scalars(select(Photo.path).where(Photo.listing_id == lid)):
            try:
                (root / path).unlink(missing_ok=True)
            except OSError as e:
                log.warning("could not delete %s: %s", path, e)
        s.execute(delete(Photo).where(Photo.listing_id == lid))
        s.get(Listing, lid).photos_fetched = False
    s.flush()
    return len(ids)

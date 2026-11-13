"""I10: photos only for listings the family can see, a daily catch-up for ones that become visible later, pruning."""
from datetime import timedelta
from io import BytesIO
from pathlib import Path

import httpx
from PIL import Image
from sqlalchemy import func, select

from homefinder.db import session_scope
from homefinder.models import Job, Listing, ListingSource, Photo, Reaction
from homefinder.worker.enrich.pipeline import enrich_listing
from homefinder.worker.handlers import WorkerDeps, dispatch
from homefinder.worker.scheduler import enqueue_missing_photos


def _jpeg():
    b = BytesIO(); Image.new("RGB", (200, 150), (10, 120, 10)).save(b, "JPEG"); return b.getvalue()


class Sink:
    def __init__(self): self.got = []
    def upload(self, listing_id, position, data, phash, source_url): self.got.append(listing_id)


def _deps(sink):
    http = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, content=_jpeg())))
    return WorkerDeps(session_factory=session_scope, adapters={}, llm=None, google=None, photo_sink=sink, http=http)


def mk(db, sid="1", urls=("https://i/1.jpg",), **kw):
    l = Listing(title="x", price=1_000_000, **kw); db.add(l); db.flush()
    db.add(ListingSource(listing_id=l.id, source="aqar", source_id=sid, url="https://x", raw={}, photo_urls=list(urls)))
    db.commit()
    return l


def test_enrichment_skips_photos_for_filtered_out_and_rejected_listings(db, monkeypatch):
    from homefinder import prefs
    p = prefs.get_or_create(db); p.hard_filters = {**p.hard_filters, "price_max": 1_500_000}; db.commit()
    ok = mk(db, "1")
    dear = mk(db, "2"); dear.price = 3_000_000
    rej = mk(db, "3"); rej.family_status = "rejected"
    db.commit()
    sink = Sink()
    for l in (ok, dear, rej):
        enrich_listing(_deps(sink), l.id)
    assert sink.got == [ok.id]
    db.expire_all()
    assert db.get(Listing, ok.id).photos_fetched and not db.get(Listing, dear.id).photos_fetched


def test_a_listing_that_becomes_visible_later_gets_its_photos_from_the_catch_up_job(db):
    from homefinder import prefs
    p = prefs.get_or_create(db); p.hard_filters = {**p.hard_filters, "price_max": 1_500_000}; db.commit()
    l = mk(db, "1"); l.price = 3_000_000; db.commit()
    sink = Sink()
    enrich_listing(_deps(sink), l.id)
    assert sink.got == []
    assert enqueue_missing_photos(db) == 0  # still filtered out: nothing to fetch
    db.refresh(l)  # enrichment ran in another session
    l.passes_filters = True; l.price = 1_000_000; db.commit()  # e.g. the family raised the budget
    assert enqueue_missing_photos(db) == 1; db.commit()
    assert enqueue_missing_photos(db) == 0  # deduped while pending
    job = db.query(Job).filter_by(type="fetch_missing_photos").one()
    out = dispatch(_deps(sink), job.type, job.payload)
    assert out == {"listings": 1, "photos": 1} and sink.got == [l.id]
    db.expire_all()
    assert db.get(Listing, l.id).photos_fetched


def test_catch_up_ignores_rejected_removed_merged_and_listings_without_photo_urls(db):
    mk(db, "a", family_status="rejected"); mk(db, "b", status="removed"); mk(db, "d", urls=())
    keep = mk(db, "c"); mk(db, "m", merged_into_id=keep.id)
    assert enqueue_missing_photos(db) == 1; db.commit()
    assert db.query(Job).filter_by(type="fetch_missing_photos").one().payload == {}


def _photo(db, l, tmp: Path, name="0.webp"):
    f = tmp / str(l.id) / name
    f.parent.mkdir(parents=True, exist_ok=True); f.write_bytes(b"x")
    db.add(Photo(listing_id=l.id, position=int(name[0]), path=f"{l.id}/{name}")); db.commit()
    return f


def test_prune_deletes_files_and_rows_of_long_gone_listings_only(db, tmp_path):
    from homefinder.photos_prune import prune_photos
    old = timedelta(days=45)
    removed = mk(db, "r", status="removed"); removed.last_seen = func.now() - old
    merged_dup = mk(db, "m", merged_into_id=None); merged_dup.last_seen = func.now() - old
    rejected = mk(db, "j", family_status="rejected")
    fresh_removed = mk(db, "f", status="removed")                       # removed 1 day ago: keep for now
    live = mk(db, "l")
    bookmarked_removed = mk(db, "b", status="removed", family_status="bookmarked"); bookmarked_removed.last_seen = func.now() - old
    db.commit()
    merged_dup.merged_into_id = live.id
    db.add(Reaction(listing_id=rejected.id, kind="reject", created_at=func.now() - old)); db.commit()
    files = {l.id: _photo(db, l, tmp_path) for l in (removed, merged_dup, rejected, fresh_removed, live, bookmarked_removed)}
    n = prune_photos(db, tmp_path, days=30); db.commit()
    assert n == 3
    assert [i for i, f in files.items() if not f.exists()] == [removed.id, merged_dup.id, rejected.id]
    assert db.scalar(select(func.count()).select_from(Photo)) == 3
    db.expire_all()
    assert db.get(Listing, removed.id).photos_fetched is False  # would be re-fetched if it ever became visible
    assert prune_photos(db, tmp_path, days=30) == 0


def test_cli_prune_photos(db, tmp_path, settings_env):
    from homefinder import cli
    settings_env(PHOTOS_DIR=str(tmp_path))
    l = mk(db, "r", status="removed"); l.last_seen = func.now() - timedelta(days=60); db.commit()
    f = _photo(db, l, tmp_path)
    cli.main(["prune-photos", "--days", "30"])
    assert not f.exists()


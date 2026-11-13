from sqlalchemy import func, select

from homefinder.models import Job, Listing, ListingSource, PriceHistory
from homefinder.schemas import CanonicalFields, RawListing
from homefinder.worker.ingest import ingest_raw


def raw(price=1_500_000, **kw):
    f = dict(property_type="villa", district="النرجس", city="الرياض", price=price, lat=24.83, lng=46.65, bedrooms=5)
    f.update(kw)
    return RawListing(source="aqar", source_id="42", url="https://sa.aqar.fm/42", fields=CanonicalFields(**f),
                      geo_precision="exact", photo_urls=["https://img/1.jpg"], seller_phone="0500000000")


def count(db, model):
    return db.scalar(select(func.count()).select_from(model))


def test_first_ingest_creates_listing_source_history_and_enrich_job(db):
    r = ingest_raw(db, raw()); db.commit()
    assert r.created and not r.price_changed
    l = db.get(Listing, r.listing_id)
    assert l.price == 1_500_000 and l.lat == 24.83 and l.geo_precision == "exact" and l.geom is not None
    assert count(db, ListingSource) == 1 and count(db, PriceHistory) == 1
    assert db.scalar(select(Job.dedupe_key)) == f"enrich:{l.id}"


def test_reingest_price_change(db):
    first = ingest_raw(db, raw()); db.commit()
    second = ingest_raw(db, raw(price=1_400_000)); db.commit()
    assert second.listing_id == first.listing_id and not second.created and second.price_changed
    assert count(db, Listing) == 1 and count(db, PriceHistory) == 2
    assert db.scalar(select(func.count()).select_from(Job).where(Job.type == "enrich_listing")) == 1
    assert db.get(Listing, first.listing_id).price == 1_400_000


def test_reingest_does_not_clear_known_fields(db):
    first = ingest_raw(db, raw()); db.commit()
    ingest_raw(db, raw(bedrooms=None)); db.commit()
    assert db.get(Listing, first.listing_id).bedrooms == 5


def test_reingest_reactivates_removed_and_follows_merge(db):
    first = ingest_raw(db, raw()); db.commit()
    canonical = Listing(property_type="villa"); db.add(canonical); db.flush()
    l = db.get(Listing, first.listing_id); l.merged_into_id = canonical.id; l.status = "removed"; db.commit()
    again = ingest_raw(db, raw(price=1_300_000)); db.commit()
    assert again.listing_id == canonical.id
    assert db.get(Listing, canonical.id).price == 1_300_000


def test_listing_without_location(db):
    r = ingest_raw(db, raw(lat=None, lng=None).model_copy(update={"geo_precision": None})); db.commit()
    l = db.get(Listing, r.listing_id)
    assert l.geom is None and l.geo_precision == "none"


def test_secondary_source_price_does_not_flip_a_merged_listing(db):
    """After a merge, only the primary (oldest) source drives price and history; otherwise two sources that quote
    slightly different prices would flap the price and fake a price drop on every scrape."""
    first = ingest_raw(db, raw(price=2_000_000)); db.commit()
    haraj = RawListing(source="haraj", source_id="h1", url="https://haraj.com.sa/h1",
                       fields=CanonicalFields(property_type="villa", price=1_950_000, lat=24.83, lng=46.65), geo_precision="approximate")
    other = ingest_raw(db, haraj); db.commit()
    l = db.get(Listing, other.listing_id)
    l.merged_into_id = first.listing_id
    db.query(ListingSource).filter_by(source="haraj").update({"listing_id": first.listing_id}); db.commit()
    again = ingest_raw(db, haraj); db.commit()
    assert again.listing_id == first.listing_id and not again.price_changed
    assert db.get(Listing, first.listing_id).price == 2_000_000 and count(db, PriceHistory) == 2  # 1 each, none added
    ingest_raw(db, raw(price=1_900_000)); db.commit()  # the primary source's change still counts
    assert db.get(Listing, first.listing_id).price == 1_900_000

from geoalchemy2.elements import WKTElement
from sqlalchemy import func, select

from homefinder.models import Listing, ListingSource, Place


def test_listing_roundtrip_with_geography(db):
    l = Listing(property_type="villa", price=1_500_000, lat=24.8, lng=46.6,
                geom=WKTElement("POINT(46.6 24.8)", srid=4326), geo_precision="exact")
    db.add(l)
    db.flush()
    db.add(ListingSource(listing_id=l.id, source="aqar", source_id="123", url="https://sa.aqar.fm/x", raw={}))
    db.add(Place(kind="airport", name="مطار الملك خالد", geom=WKTElement("POINT(46.6988 24.9576)", srid=4326)))
    db.commit()
    dist = db.scalar(select(func.ST_Distance(Listing.geom, Place.geom)).where(Listing.id == l.id))
    assert 15_000 < dist < 25_000
    assert l.family_status == "new" and l.status == "active" and l.commutes == {}


def test_source_unique(db):
    import pytest
    from sqlalchemy.exc import IntegrityError
    l = Listing()
    db.add(l); db.flush()
    db.add(ListingSource(listing_id=l.id, source="aqar", source_id="1", url="u", raw={}))
    db.add(ListingSource(listing_id=l.id, source="aqar", source_id="1", url="u", raw={}))
    with pytest.raises(IntegrityError):
        db.flush()


def test_chat_thread_roundtrip(db):
    from homefinder.models import ChatThread
    db.add(ChatThread(id="11111111-1111-1111-1111-111111111111", title="مرحبا")); db.commit()
    t = db.get(ChatThread, "11111111-1111-1111-1111-111111111111")
    assert t.title == "مرحبا" and t.created_at is not None and t.updated_at is not None

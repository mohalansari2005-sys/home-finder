from geoalchemy2.elements import WKTElement

from homefinder.dedupe import dedupe_and_merge, is_duplicate
from homefinder.models import Listing, ListingSource, Photo, PriceHistory, Reaction

H1 = "f0e0d0c0b0a09080"
H1_NEAR = "f0e0d0c0b0a09081"  # hamming 1
H_FAR = "0f1f2f3f4f5f6f7f"


def mk(db, lat=24.8, lng=46.6, price=2_000_000, built=400, land=300, ptype="villa", phashes=(), src="aqar", sid="1", **kw):
    l = Listing(lat=lat, lng=lng, geom=WKTElement(f"POINT({lng} {lat})", srid=4326), geo_precision="exact",
                price=price, built_area_m2=built, land_area_m2=land, property_type=ptype, **kw)
    db.add(l); db.flush()
    db.add(ListingSource(listing_id=l.id, source=src, source_id=sid, url=f"https://{src}/{sid}", raw={}))
    for i, h in enumerate(phashes):
        db.add(Photo(listing_id=l.id, position=i, path=f"{l.id}/{i}.webp", phash=h))
    db.add(PriceHistory(listing_id=l.id, price=price))
    db.flush()
    return l


def test_is_duplicate_rules():
    a = Listing(price=2_000_000, built_area_m2=400, land_area_m2=300, property_type="villa")
    b = Listing(price=2_040_000, built_area_m2=410, land_area_m2=300, property_type="villa")
    assert is_duplicate(a, b, [H1], [H1_NEAR])
    assert not is_duplicate(a, b, [H1], [H_FAR])                       # photos disagree
    assert is_duplicate(a, b, [], [])                                  # no photos: numbers + type suffice
    assert not is_duplicate(a, Listing(price=2_200_000, built_area_m2=400, land_area_m2=300, property_type="villa"), [], [])
    assert not is_duplicate(a, Listing(price=2_000_000, built_area_m2=400, land_area_m2=300, property_type="apartment"), [], [])
    assert not is_duplicate(Listing(price=2_000_000), Listing(price=2_000_000), [], [])  # no comparable area


def test_is_duplicate_unknown_price_does_not_match():
    a = Listing(price=None, built_area_m2=400, land_area_m2=300, property_type="villa")
    b = Listing(price=None, built_area_m2=400, land_area_m2=300, property_type="villa")
    assert not is_duplicate(a, b, [], [])


def test_merge_keeps_older_and_moves_everything(db):
    old = mk(db, phashes=[H1], sid="a1", bedrooms=None)
    new = mk(db, lat=24.80020, phashes=[H1_NEAR], src="haraj", sid="h9", bedrooms=5, family_status="bookmarked")
    db.add(Reaction(listing_id=new.id, kind="bookmark")); db.commit()
    assert dedupe_and_merge(db, new.id) == old.id
    db.commit(); db.expire_all()
    old, new = db.get(Listing, old.id), db.get(Listing, new.id)
    assert new.merged_into_id == old.id
    assert {s.source for s in db.query(ListingSource).filter_by(listing_id=old.id)} == {"aqar", "haraj"}
    assert old.bedrooms == 5 and old.family_status == "bookmarked"
    assert db.query(Reaction).filter_by(listing_id=old.id).count() == 1


def test_merge_keeps_status_rank_and_does_not_overwrite_known_fields(db):
    old = mk(db, sid="a1", bedrooms=4, family_status="visited")
    new = mk(db, lat=24.80020, src="haraj", sid="h9", bedrooms=6, family_status="rejected")
    db.commit()
    assert dedupe_and_merge(db, new.id) == old.id
    db.commit(); db.expire_all()
    assert db.get(Listing, old.id).bedrooms == 4 and db.get(Listing, old.id).family_status == "visited"


def test_merge_moves_photos_only_when_keep_has_none(db):
    old = mk(db, sid="a1")
    new = mk(db, lat=24.80020, src="haraj", sid="h9", phashes=[H1])
    db.commit()
    dedupe_and_merge(db, new.id)
    db.commit()
    assert db.query(Photo).filter_by(listing_id=old.id).count() == 1
    assert db.get(Listing, old.id).photos_fetched is True


def test_neighbors_not_merged(db):
    a = mk(db, sid="a", built=400, land=300)
    b = mk(db, lat=24.80030, sid="b", built=450, land=360)  # ~33 m away, same price, areas differ >5%
    db.commit()
    assert dedupe_and_merge(db, b.id) is None


def test_far_apart_not_candidates(db):
    mk(db, sid="a"); b = mk(db, lat=24.81, sid="b"); db.commit()  # ~1.1 km
    assert dedupe_and_merge(db, b.id) is None


def test_removed_and_already_merged_listings_are_not_candidates(db):
    mk(db, sid="r", status="removed")
    b = mk(db, lat=24.80020, sid="b"); db.commit()
    assert dedupe_and_merge(db, b.id) is None
    c = mk(db, sid="c"); d = mk(db, lat=24.80020, sid="d", merged_into_id=c.id); db.commit()
    assert dedupe_and_merge(db, d.id) is None  # d is already merged


def test_listing_without_location_is_skipped(db):
    l = Listing(price=1, built_area_m2=400, land_area_m2=300, property_type="villa", geo_precision="none")
    db.add(l); db.commit()
    assert dedupe_and_merge(db, l.id) is None
    assert dedupe_and_merge(db, 99999) is None


def test_merge_does_not_mix_price_histories(db):
    """A cross-source price difference must not look like a price drop on the surviving listing."""
    old = mk(db, sid="a1", price=2_000_000)
    new = mk(db, lat=24.80020, src="haraj", sid="h9", price=1_950_000)
    db.commit()
    dedupe_and_merge(db, new.id); db.commit()
    assert [p.price for p in db.query(PriceHistory).filter_by(listing_id=old.id)] == [2_000_000]

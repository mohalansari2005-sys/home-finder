from geoalchemy2.elements import WKTElement

from homefinder.models import Listing, ListingSource, Photo, Reaction


def mk(db, **kw):
    d = dict(title="فيلا", property_type="villa", price=1_500_000, district="النرجس", lat=24.8, lng=46.6,
             geom=WKTElement("POINT(46.6 24.8)", srid=4326), geo_precision="exact", commutes={"work": 20})
    d.update(kw)
    l = Listing(**d); db.add(l); db.flush()
    db.add(ListingSource(listing_id=l.id, source="aqar", source_id=str(l.id), url=f"https://sa.aqar.fm/{l.id}",
                         raw={}, photo_urls=["https://img/remote.jpg"], seller_phone="0500000000"))
    db.commit()
    return l


def test_feed_views_and_exclusions(db, family):
    a = mk(db); b = mk(db, family_status="bookmarked"); mk(db, family_status="rejected")
    mk(db, merged_into_id=a.id); mk(db, status="removed"); mk(db, passes_filters=False)
    ids = [i["id"] for i in family.get("/api/feed").json()["items"]]
    assert set(ids) == {a.id, b.id}
    assert [i["id"] for i in family.get("/api/feed?view=bookmarked").json()["items"]] == [b.id]
    assert [i["id"] for i in family.get("/api/feed?view=new").json()["items"]] == [a.id]


def test_feed_card_shape_and_photo_fallback(db, family):
    l = mk(db)
    card = family.get("/api/feed").json()["items"][0]
    assert card["photo_url"] == "https://img/remote.jpg" and card["commutes"] == {"work": 20}
    db.add(Photo(listing_id=l.id, position=0, path=f"{l.id}/0.webp")); db.commit()
    assert family.get("/api/feed").json()["items"][0]["photo_url"] == f"/photos/{l.id}/0.webp"


def test_feed_pagination(db, family):
    for _ in range(3):
        mk(db)
    page = family.get("/api/feed?limit=2").json()
    assert len(page["items"]) == 2 and page["next_offset"] == 2
    assert family.get("/api/feed?limit=2&offset=2").json()["next_offset"] is None


def test_detail_marks_seen_and_includes_sources(db, family):
    l = mk(db)
    d = family.get(f"/api/listings/{l.id}").json()
    assert d["sources"][0]["seller_phone"] == "0500000000" and d["family_status"] == "seen"
    assert family.get("/api/listings/999999").status_code == 404


def test_react_flow(db, family):
    l = mk(db)
    assert family.post(f"/api/listings/{l.id}/react", json={"kind": "bookmark"}).json() == {"family_status": "bookmarked"}
    assert family.post(f"/api/listings/{l.id}/react", json={"kind": "reject", "reason_code": "too_old"}).json()["family_status"] == "rejected"
    assert family.post(f"/api/listings/{l.id}/react", json={"kind": "unreject"}).json()["family_status"] == "seen"
    assert db.query(Reaction).count() == 3
    assert family.post(f"/api/listings/{l.id}/react", json={"kind": "explode"}).status_code == 422


def test_map_excludes_no_coords_and_rejected(db, family):
    a = mk(db); mk(db, lat=None, lng=None, geom=None, geo_precision="none"); mk(db, family_status="rejected")
    assert [p["id"] for p in family.get("/api/map").json()] == [a.id]

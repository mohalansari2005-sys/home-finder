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
    assert d["passes_filters"] is True and d["filter_reasons"] == []
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


def test_removed_listing_hidden_from_feed_but_kept_in_bookmarks_with_status(db, family):
    gone = mk(db, status="removed", family_status="bookmarked"); live = mk(db)
    assert [i["id"] for i in family.get("/api/feed").json()["items"]] == [live.id]
    items = family.get("/api/feed?view=bookmarked").json()["items"]
    assert [(i["id"], i["status"]) for i in items] == [(gone.id, "removed")]
    assert family.get("/api/feed").json()["items"][0]["status"] == "active"
    assert family.get(f"/api/listings/{gone.id}").json()["status"] == "removed"


def _history(db, listing, *rows):
    """rows: (price, days_ago) oldest first."""
    from datetime import timedelta
    from sqlalchemy import func
    from homefinder.models import PriceHistory
    for price, days in rows:
        db.add(PriceHistory(listing_id=listing.id, price=price, observed_at=func.now() - timedelta(days=days)))
        db.flush()
    db.commit()


def test_price_drop_in_card(db, family):
    from homefinder.models import PriceHistory
    l = mk(db, price=1_900_000)
    db.add(PriceHistory(listing_id=l.id, price=2_000_000)); db.flush()
    db.add(PriceHistory(listing_id=l.id, price=1_900_000)); db.commit()
    card = family.get("/api/feed").json()["items"][0]
    assert card["price_drop"]["from"] == 2_000_000 and card["price_drop"]["to"] == 1_900_000
    assert card["price_drop"]["at"]


def test_price_drop_rules(db, family):
    dropped = mk(db, price=900); _history(db, dropped, (1_000_000, 10), (900_000, 5))
    rose = mk(db, price=1_100_000); _history(db, rose, (1_000_000, 10), (1_100_000, 5))
    old_drop = mk(db, price=900_000); _history(db, old_drop, (1_000_000, 60), (900_000, 40))
    single = mk(db, price=1_000_000); _history(db, single, (1_000_000, 3))
    none = mk(db)
    # only the LAST change counts: dropped, then rose again -> no badge
    again = mk(db, price=950_000); _history(db, again, (1_000_000, 20), (900_000, 10), (950_000, 2))
    # dropped twice: from/to are the last two entries
    twice = mk(db, price=800_000); _history(db, twice, (1_000_000, 20), (900_000, 10), (800_000, 2))
    items = {i["id"]: i["price_drop"] for i in family.get("/api/feed").json()["items"]}
    assert items[dropped.id]["from"] == 1_000_000 and items[dropped.id]["to"] == 900_000
    assert items[rose.id] is None and items[old_drop.id] is None and items[single.id] is None and items[none.id] is None
    assert items[again.id] is None
    assert (items[twice.id]["from"], items[twice.id]["to"]) == (900_000, 800_000)


def test_price_drop_in_detail_and_map(db, family):
    l = mk(db, price=900_000); _history(db, l, (1_000_000, 4), (900_000, 1))
    assert family.get(f"/api/listings/{l.id}").json()["price_drop"]["from"] == 1_000_000
    pt = family.get("/api/map").json()[0]
    assert pt["price_drop"]["to"] == 900_000 and pt["status"] == "active"


def _statements(fn):
    from sqlalchemy import event
    from homefinder.db import get_engine
    seen: list[str] = []

    def grab(conn, cursor, statement, *a):
        seen.append(statement)
    eng = get_engine()
    event.listen(eng, "before_cursor_execute", grab)
    try:
        fn()
    finally:
        event.remove(eng, "before_cursor_execute", grab)
    return seen


def test_map_feed_and_card_helpers_never_load_the_raw_scrape_json(db, family):
    """I7: raw is a few KB (Aqar) to a whole post body (Haraj); a 2000-point map must not drag it into memory."""
    from homefinder.server.visits.out import _phones, _source_urls, listing_cards
    ls = [mk(db) for _ in range(3)]
    db.add(Photo(listing_id=ls[0].id, position=0, path=f"{ls[0].id}/0.webp")); db.commit()

    def run():
        assert len(family.get("/api/map").json()) == 3
        assert len(family.get("/api/feed").json()["items"]) == 3
        rows = db.query(Listing).all()
        listing_cards(db, rows); _phones(db, [l.id for l in rows]); _source_urls(db, [l.id for l in rows])
    sql = [x for x in _statements(run) if "listing_sources" in x]
    assert sql and not any("listing_sources.raw" in x for x in sql), [x[:120] for x in sql if "listing_sources.raw" in x]
    pts = {p["id"]: p for p in family.get("/api/map").json()}
    assert pts[ls[0].id]["photo_url"] == f"/photos/{ls[0].id}/0.webp"       # downloaded photo wins
    assert pts[ls[1].id]["photo_url"] == "https://img/remote.jpg"           # else the first remote one


def test_detail_keeps_every_photo_but_cards_take_the_first(db, family):
    l = mk(db)
    db.add_all([Photo(listing_id=l.id, position=1, path="b.webp"), Photo(listing_id=l.id, position=0, path="a.webp")]); db.commit()
    assert family.get(f"/api/listings/{l.id}").json()["photos"] == ["/photos/a.webp", "/photos/b.webp"]
    assert family.get("/api/feed").json()["items"][0]["photo_url"] == "/photos/a.webp"


def test_feed_and_detail_carry_a_whatsapp_link_only_for_a_saudi_mobile(db, family):
    mobile, landline, none = mk(db, title="فيلا الياسمين"), mk(db), mk(db)
    db.query(ListingSource).filter_by(listing_id=landline.id).update({"seller_phone": "0112345678"})
    db.query(ListingSource).filter_by(listing_id=none.id).update({"seller_phone": None}); db.commit()
    cards = {c["id"]: c for c in family.get("/api/feed").json()["items"]}
    assert cards[mobile.id]["whatsapp_url"].startswith("https://wa.me/966500000000?text=")
    assert cards[landline.id]["whatsapp_url"] is None and cards[none.id]["whatsapp_url"] is None
    assert family.get(f"/api/listings/{mobile.id}").json()["whatsapp_url"] == cards[mobile.id]["whatsapp_url"]


def test_whatsapp_link_skips_a_landline_source_for_a_later_mobile_one(db, family):
    l = mk(db)
    db.query(ListingSource).filter_by(listing_id=l.id).update({"seller_phone": "0112345678"})
    db.add(ListingSource(listing_id=l.id, source="haraj", source_id=f"h{l.id}", url="u", raw={}, seller_phone="0551234567"))
    db.commit()
    assert family.get("/api/feed").json()["items"][0]["whatsapp_url"].startswith("https://wa.me/966551234567?")
    assert family.get(f"/api/listings/{l.id}").json()["whatsapp_url"].startswith("https://wa.me/966551234567?")

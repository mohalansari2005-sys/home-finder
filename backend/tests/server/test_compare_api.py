from homefinder.models import Listing, PriceHistory


def test_compare_orders_and_validates(db, family):
    ids = []
    for p in (1_000_000, 2_000_000, 3_000_000):
        l = Listing(price=p); db.add(l); db.flush(); ids.append(l.id)
    db.commit()
    out = family.get(f"/api/compare?ids={ids[2]},{ids[0]}").json()
    assert [x["id"] for x in out] == [ids[2], ids[0]] and out[0]["family_status"] == "new"
    assert family.get(f"/api/compare?ids={ids[0]}").status_code == 422
    assert family.get(f"/api/compare?ids={ids[0]},999999").status_code == 422


def test_compare_detail_shape_and_no_status_change(db, family):
    a = Listing(price=1_000_000, score=0.8, score_breakdown={"total": 0.8}); b = Listing(price=2_000_000)
    db.add_all([a, b]); db.flush()
    db.add_all([PriceHistory(listing_id=a.id, price=1_200_000), PriceHistory(listing_id=a.id, price=1_000_000)])
    db.commit()
    detail = family.get(f"/api/listings/{a.id}").json()
    db.execute(Listing.__table__.update().values(family_status="new")); db.commit()
    out = family.get(f"/api/compare?ids={a.id},{b.id}").json()
    assert set(out[0]) == set(detail) and out[0]["price_drop"]["to"] == 1_000_000
    assert out[0]["score_breakdown"] == {"total": 0.8} and out[1]["price_drop"] is None
    db.expire_all()
    assert {l.family_status for l in db.query(Listing)} == {"new"}


def test_compare_skips_unknown_and_merged_and_limits(db, family):
    ls = [Listing(price=1_000_000 + i) for i in range(5)]
    db.add_all(ls); db.flush(); ids = [l.id for l in ls]; db.commit()
    assert len(family.get("/api/compare?ids=" + ",".join(map(str, ids[:4]))).json()) == 4
    assert family.get("/api/compare?ids=" + ",".join(map(str, ids))).status_code == 422
    assert family.get(f"/api/compare?ids={ids[0]},{ids[0]},{ids[1]}").status_code == 200
    assert family.get("/api/compare?ids=a,b").status_code == 422
    assert family.get("/api/compare").status_code == 422
    assert [x["id"] for x in family.get(f"/api/compare?ids={ids[1]},424242,{ids[0]}").json()] == [ids[1], ids[0]]


def test_compare_skips_merged(db, family):
    a, b = Listing(price=1), Listing(price=2); db.add_all([a, b]); db.flush()
    c = Listing(price=3, merged_into_id=a.id); db.add(c); db.commit()
    assert family.get(f"/api/compare?ids={a.id},{c.id}").status_code == 422
    assert family.get(f"/api/compare?ids={a.id},{c.id},{b.id}").status_code == 200

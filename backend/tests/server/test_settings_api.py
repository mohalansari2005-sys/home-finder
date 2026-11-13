from homefinder.models import CommuteCache, Job, Place


def test_places_upsert_invalidates_cache(db, family):
    body = [{"kind": "work", "name": "المكتب", "lat": 24.7, "lng": 46.68}]
    assert family.put("/api/places", json=body).status_code == 200
    pid = db.query(Place).one().id
    db.add(CommuteCache(origin_key="24.800,46.600", place_id=pid, minutes=20)); db.commit()
    family.put("/api/places", json=[{"kind": "work", "name": "المكتب الجديد", "lat": 24.75, "lng": 46.7}])
    db.expire_all()
    assert db.query(CommuteCache).count() == 0
    assert db.query(Job).filter(Job.type == "recompute_commutes").count() == 1
    assert family.get("/api/places").json() == [{"kind": "work", "name": "المكتب الجديد", "lat": 24.75, "lng": 46.7}]


def test_places_rejects_unknown_kind(family):
    assert family.put("/api/places", json=[{"kind": "gym", "name": "x", "lat": 1, "lng": 1}]).status_code == 422


def test_preferences_partial_update(family):
    p = family.get("/api/preferences").json()
    assert p["hard_filters"]["city"] == "الرياض"
    out = family.put("/api/preferences", json={"hard_filters": {"price_max": 2_000_000, "districts": ["النرجس"]}}).json()
    assert out["hard_filters"]["price_max"] == 2_000_000 and out["hard_filters"]["city"] == "الرياض"


def test_status_shape(family):
    s = family.get("/api/status").json()
    assert s["worker"]["online"] is False and s["jobs"] == {"pending": 0, "claimed": 0, "failed": 0}

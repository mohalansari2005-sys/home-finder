from homefinder.models import AdapterHealth, CommuteCache, Job, Listing, Place, PreferenceChange


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


def test_get_preferences_returns_effective_defaults(family):
    p = family.get("/api/preferences").json()
    assert p["weights"]["commute_work"] == 1.0 and p["targets"]["commute_bad_min"] == 40
    assert p["locked_weights"] == [] and "defaults" in p


def test_put_weights_locks_and_rescores(db, family):
    db.add(Listing(price=1_000_000)); db.commit()
    out = family.put("/api/preferences", json={"weights": {"price": 2.5}}).json()
    assert out["weights"]["price"] == 2.5 and out["locked_weights"] == ["price"]
    db.expire_all()
    assert db.query(Listing).one().score_breakdown is not None  # background task ran (TestClient runs them inline)
    assert db.query(PreferenceChange).count() == 1
    out = family.put("/api/preferences", json={"unlock": ["price"]}).json()
    assert out["locked_weights"] == []
    out = family.put("/api/preferences", json={"reset_weights": True}).json()
    assert out["weights"]["price"] == 1.0


def test_put_preferences_validation(family):
    before = family.get("/api/preferences").json()
    for bad in [{"weights": {"nonsense": 1}}, {"weights": {"price": -1}}, {"hard_filters": {"price_max": 5}},
                {"hard_filters": {"property_types": ["castle"]}}, {"targets": {"commute_bad_min": "x"}}]:
        assert family.put("/api/preferences", json=bad).status_code == 422, bad
    assert family.get("/api/preferences").json() == before


def test_search_relevant_change_enqueues_scrape(db, family):
    family.put("/api/preferences", json={"hard_filters": {"districts": ["الياسمين"]}})
    j = db.query(Job).filter(Job.type == "scrape_search").one()
    assert j.payload == {"source": "aqar", "from_prefs": True, "scheduled": False} and j.priority == 5
    family.put("/api/preferences", json={"hard_filters": {"min_bedrooms": 4}})
    assert db.query(Job).filter(Job.type == "scrape_search").count() == 1


def test_resume_adapter(db, family):
    db.add(AdapterHealth(source="aqar", status="paused", reason="x")); db.commit()
    assert family.post("/api/adapters/aqar/resume").status_code == 204
    db.expire_all()
    assert db.get(AdapterHealth, "aqar").status == "ok"


def test_changes_list(family):
    family.put("/api/preferences", json={"hard_filters": {"price_max": 2_000_000}})
    ch = family.get("/api/preferences/changes").json()
    assert ch[0]["source"] == "user" and "hard_filters.price_max" in ch[0]["diff"]


def test_status_counts_and_last_scrape(db, family):
    from datetime import UTC, datetime
    db.add_all([Listing(price=1), Listing(price=1, family_status="bookmarked"), Listing(price=1, family_status="rejected"),
                Listing(price=1, passes_filters=False), Listing(price=1, status="removed")])
    db.add(AdapterHealth(source="aqar", status="ok", last_success_at=datetime(2026, 1, 1, tzinfo=UTC))); db.commit()
    s = family.get("/api/status").json()
    assert s["counts"] == {"active": 4, "new": 2, "bookmarked": 1, "rejected": 1, "passing": 2}
    assert s["adapters"][0]["last_scrape_at"] == s["adapters"][0]["last_success_at"] != None  # noqa: E711

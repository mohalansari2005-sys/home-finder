from homefinder.models import Job, Listing, Preferences


def _reject(family, db, age, reason="too_old"):
    l = Listing(building_age_years=age); db.add(l); db.commit()
    return family.post(f"/api/listings/{l.id}/react", json={"kind": "reject", "reason_code": reason})


def test_invalid_reason_code(db, family):
    assert _reject(family, db, 10, reason="ugly").status_code == 422


def test_learn_enqueued_after_10(db, family):
    for i in range(9):
        _reject(family, db, 20)
    assert db.query(Job).filter_by(type="learn").count() == 0
    _reject(family, db, 20)
    assert db.query(Job).filter_by(type="learn").count() == 1


def test_suggestion_apply_and_dismiss(db, family):
    for a in [18, 20, 22, 25, 30]:
        _reject(family, db, a)
    [s] = family.get("/api/suggestions").json()
    assert s["code"] == "too_old"
    assert family.post("/api/suggestions/too_old/apply").status_code == 200
    db.expire_all()
    assert db.get(Preferences, 1).hard_filters["building_age_max"] == 21
    assert family.get("/api/suggestions").json() == []  # now satisfied: rejected ones exceed filter but suggestion equals current
    assert family.post("/api/suggestions/narrow_street/dismiss").status_code == 404  # contract: unknown code
    assert family.post("/api/suggestions/narrow_street/apply").status_code == 404


def test_dismiss_hides_until_five_new(db, family):
    for a in [18, 20, 22, 25, 30]:
        _reject(family, db, a)
    assert family.post("/api/suggestions/too_old/dismiss").status_code == 204
    assert family.get("/api/suggestions").json() == []
    for a in [26, 27, 28, 29]:
        _reject(family, db, a)
    assert family.get("/api/suggestions").json() == []
    _reject(family, db, 31)
    assert [s["code"] for s in family.get("/api/suggestions").json()] == ["too_old"]
    assert family.post("/api/suggestions/too_old/apply").json() == {"ok": True}
    change = family.get("/api/preferences/changes").json()[0]
    assert change["source"] == "user" and "building_age_max" in str(change["diff"])


def test_react_validation(db, family):
    l = Listing(); db.add(l); db.commit()
    url = f"/api/listings/{l.id}/react"
    assert family.post(url, json={"kind": "reject", "note": "x" * 501}).status_code == 422
    assert family.post(url, json={"kind": "reject", "reason_code": "far", "note": "x" * 500}).status_code == 200
    assert family.post(url, json={"kind": "reject", "reason_code": None}).status_code == 200
    assert family.post(url, json={"kind": "bookmark", "reason_code": "far", "note": "n"}).status_code == 200
    from homefinder.models import Reaction
    db.expire_all()
    last = db.query(Reaction).order_by(Reaction.id.desc()).first()
    assert last.kind == "bookmark" and last.reason_code is None and last.note is None  # ignored unless reject

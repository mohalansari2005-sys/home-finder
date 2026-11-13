from datetime import UTC, datetime, timedelta

import pytest
from geoalchemy2.elements import WKTElement

from homefinder.models import (Job, Listing, ListingSource, Place, PriceHistory, Reaction, VisitPhoto, VisitStop,
                               VisitTrip)
from homefinder.server.routes import listings as listings_route
from homefinder.server.routes import visits as visits_route


class FakeMaps:
    def drive_minutes(self, origin, dests, dep):
        return [5] * len(dests)

    def optimize_route(self, origin, stops, dep):
        n = len(stops)
        return {"order": list(range(n)), "leg_minutes": [10] * (n + 1)}


@pytest.fixture(autouse=True)
def no_maps(monkeypatch):
    monkeypatch.setattr(visits_route, "get_maps", lambda: None)  # TomTom is unset: plan_trip keeps order, warns no_route


def seed(db):
    db.add(Place(kind="home", name="البيت", lat=24.7, lng=46.6, geom=WKTElement("POINT(46.6 24.7)", srid=4326)))
    ids = []
    for i, d in enumerate(["النرجس", "النرجس", None]):
        l = Listing(title=f"ف{i}", district=d, lat=24.84 if d else None, lng=46.65 if d else None, family_status="bookmarked", score=70)
        db.add(l); db.flush(); ids.append(l.id)
        db.add(ListingSource(listing_id=l.id, source="aqar", source_id=str(l.id), url="u", raw={}, seller_phone="0551234567"))
    db.commit()
    return ids


BODY = {"date": "2026-12-05", "start_time": "16:00", "origin_kind": "home", "minutes_per_visit": 30}


def make_trip(family, ids, **kw):
    r = family.post("/api/visits/trips", json={"listing_ids": ids, **BODY, **kw})
    assert r.status_code == 200, r.text
    return r.json()


def test_groups_and_trip_flow(db, family):
    ids = seed(db)
    g = family.get("/api/visits/groups").json()
    assert g["groups"][0]["count"] == 2 and [c["id"] for c in g["no_location"]] == [ids[2]]
    grp = g["groups"][0]
    assert set(grp) == {"key", "districts", "listing_ids", "count", "avg_score", "centroid", "listings"}
    assert grp["districts"] == ["النرجس"] and grp["avg_score"] == 70 and len(grp["centroid"]) == 2
    assert [c["id"] for c in grp["listings"]] == grp["listing_ids"] and grp["listings"][0]["title"]
    r = family.post("/api/visits/trips", json={"listing_ids": ids, "date": "2026-12-05", "start_time": "16:00",
                                               "origin_kind": "home", "minutes_per_visit": 30})
    assert r.status_code == 200
    trip = r.json()
    assert len(trip["stops"]) == 2 and "skipped_no_location" in str(trip["warnings"])
    assert trip["skipped_no_location"] == 1 and "precheck_pending" in trip["warnings"] and "no_route" in trip["warnings"]
    assert trip["stops"][0]["whatsapp_url"].startswith("https://wa.me/966551234567")
    assert trip["stops"][0]["phone"] == "966551234567"
    assert trip["maps_url"].startswith("https://www.google.com/maps/dir/")
    assert db.query(Job).filter_by(type="precheck_trip").count() == 1
    sid = trip["stops"][0]["id"]
    out = family.patch(f"/api/visits/stops/{sid}", json={"contact_status": "visited", "rating": 5, "notes": "ممتاز"}).json()
    assert out["stops"][0]["rating"] == 5
    assert db.query(Reaction).filter_by(kind="visit_rating", rating=5).count() == 1


def test_trip_shape_matches_contract(db, family, monkeypatch):
    monkeypatch.setattr(visits_route, "get_maps", lambda: FakeMaps())
    ids = seed(db)
    t = make_trip(family, ids[:2])
    assert set(t) == {"id", "title", "date", "start_time", "origin_kind", "minutes_per_visit", "status", "warnings",
                      "total_drive_min", "skipped_no_location", "maps_url", "stops"}
    assert (t["date"], t["start_time"], t["status"], t["total_drive_min"]) == ("2026-12-05", "16:00", "planned", 30)
    s0, s1 = t["stops"]
    assert set(s0) == {"id", "position", "listing", "eta_local", "etd_local", "drive_min", "contact_status", "rating",
                       "notes", "flags", "whatsapp_url", "phone", "photos", "old_price", "source_url"}
    assert (s0["eta_local"], s0["etd_local"], s1["eta_local"]) == ("16:10", "16:40", "16:50")
    assert s0["contact_status"] == "not_contacted" and s0["flags"] == [] and s0["photos"] == []
    assert s0["listing"]["id"] in ids and "photo_url" in s0["listing"]
    assert "4:10" in __import__("urllib.parse", fromlist=["unquote"]).unquote(s0["whatsapp_url"])
    assert family.get(f"/api/visits/trips/{t['id']}").json() == t


def test_stop_without_phone_has_null_whatsapp(db, family):
    ids = seed(db)
    db.query(ListingSource).update({"seller_phone": None}); db.commit()
    s = make_trip(family, ids[:1])["stops"][0]
    assert s["whatsapp_url"] is None and s["phone"] is None
    db.query(ListingSource).update({"seller_phone": "0112345678"}); db.commit()  # landline
    s = family.get(f"/api/visits/trips/{db.query(VisitTrip).one().id}").json()["stops"][0]
    assert s["whatsapp_url"] is None and s["phone"] is None


def test_trip_requires_origin_place(db, family):
    ids = seed(db)
    r = family.post("/api/visits/trips", json={"listing_ids": ids[:1], **BODY, "origin_kind": "work"})
    assert r.status_code == 422 and "العمل" in r.json()["detail"]
    db.query(Place).delete(); db.commit()
    r = family.post("/api/visits/trips", json={"listing_ids": ids[:1], **BODY})
    assert r.status_code == 422 and r.json()["detail"] == "حدد موقع المنزل في الإعدادات أولاً"
    assert db.query(VisitTrip).count() == 0 and db.query(Job).filter_by(type="precheck_trip").count() == 0


def test_trip_validation(db, family):
    ids = seed(db)
    for bad in [{"listing_ids": []}, {"minutes_per_visit": 5}, {"minutes_per_visit": 121}, {"start_time": "25:00"},
                {"listing_ids": list(range(1, 17))}, {"origin_kind": "airport"}, {"date": "2026-13-01"}]:
        body = {"listing_ids": ids[:1], **BODY, **bad}
        assert family.post("/api/visits/trips", json=body).status_code == 422, bad
    r = family.post("/api/visits/trips", json={"listing_ids": [ids[2]], **BODY})  # only a no-location listing
    assert r.status_code == 422 and r.json()["detail"]
    assert family.post("/api/visits/trips", json={"listing_ids": [9999], **BODY}).status_code == 422


def test_all_routes_require_family_login(db, app_client):
    for method, url in [("get", "/api/visits/groups"), ("get", "/api/visits/trips"), ("get", "/api/visits/trips/1"),
                        ("post", "/api/visits/trips"), ("patch", "/api/visits/stops/1"), ("patch", "/api/visits/trips/1"),
                        ("post", "/api/visits/trips/1/replan"), ("post", "/api/visits/trips/1/precheck"),
                        ("post", "/api/visits/stops/1/photos"), ("get", "/api/visits/photos/1")]:
        assert getattr(app_client, method)(url).status_code == 401, url


def test_precheck_job_is_delayed_until_3h_before_or_immediate(db, family):
    ids = seed(db)
    make_trip(family, ids[:1], date="2099-01-01")
    far = db.query(Job).filter_by(type="precheck_trip").one()
    assert far.run_after > datetime.now(UTC) + timedelta(days=365) and far.dedupe_key == f"precheck:{far.payload['trip_id']}"
    # 2099-01-01 16:00 Riyadh == 13:00 UTC; the job runs 3 h before: 10:00 UTC
    assert abs(far.run_after - datetime(2099, 1, 1, 10, 0, tzinfo=UTC)) < timedelta(seconds=30)
    db.query(Job).delete(); db.commit()
    make_trip(family, ids[:1], date="2020-01-01")
    soon = db.query(Job).filter_by(type="precheck_trip").one()
    assert soon.run_after <= datetime.now(UTC) + timedelta(seconds=30)


def test_manual_precheck_pulls_delayed_job_forward(db, family):
    ids = seed(db)
    t = make_trip(family, ids[:1], date="2099-01-01")
    r = family.post(f"/api/visits/trips/{t['id']}/precheck")
    assert r.status_code == 202
    jobs = db.query(Job).filter_by(type="precheck_trip").all()
    assert len(jobs) == 1 and jobs[0].priority == 10 and jobs[0].run_after <= datetime.now(UTC) + timedelta(seconds=30)
    assert "precheck_pending" in family.get(f"/api/visits/trips/{t['id']}").json()["warnings"]
    db.query(Job).delete(); db.commit()  # no pending job at all: the endpoint creates one
    family.post(f"/api/visits/trips/{t['id']}/precheck")
    assert db.query(Job).filter_by(type="precheck_trip", priority=10).count() == 1


def test_cancel_stop_replans(db, family, monkeypatch):
    monkeypatch.setattr(visits_route, "get_maps", lambda: FakeMaps())
    ids = seed(db)
    extra = Listing(title="ث", district="النرجس", lat=24.845, lng=46.651, family_status="bookmarked"); db.add(extra); db.commit()
    t = make_trip(family, [*ids[:2], extra.id])
    assert t["total_drive_min"] == 40
    sid = t["stops"][0]["id"]
    out = family.patch(f"/api/visits/stops/{sid}", json={"contact_status": "cancelled"}).json()
    by = {s["id"]: s for s in out["stops"]}
    assert by[sid]["contact_status"] == "cancelled" and by[sid]["eta_local"] is None
    active = [s for s in out["stops"] if s["contact_status"] != "cancelled"]
    assert [s["position"] for s in active] == [0, 1] and active[0]["eta_local"] == "16:10" and out["total_drive_min"] == 30
    assert out["maps_url"].count("%7C") + out["maps_url"].count("|") == 0  # two stops: one waypoint-less destination + origin only
    # replan endpoint
    out2 = family.post(f"/api/visits/trips/{t['id']}/replan").json()
    assert out2["total_drive_min"] == 30


def test_visited_marks_listing_and_undo_reverts(db, family):
    ids = seed(db)
    t = make_trip(family, ids[:1])
    sid = t["stops"][0]["id"]
    family.patch(f"/api/visits/stops/{sid}", json={"contact_status": "visited"})
    db.expire_all()
    assert db.get(Listing, ids[0]).family_status == "visited"
    family.patch(f"/api/visits/stops/{sid}", json={"contact_status": "confirmed"})
    db.expire_all()
    assert db.get(Listing, ids[0]).family_status == "bookmarked"


def test_patch_stop_validation_and_notes(db, family):
    ids = seed(db)
    sid = make_trip(family, ids[:1])["stops"][0]["id"]
    for bad in [{"rating": 0}, {"rating": 6}, {"contact_status": "maybe"}, {"notes": "x" * 2001}]:
        assert family.patch(f"/api/visits/stops/{sid}", json=bad).status_code == 422, bad
    assert family.patch("/api/visits/stops/999", json={"notes": "x"}).status_code == 404
    out = family.patch(f"/api/visits/stops/{sid}", json={"notes": "حلو"}).json()
    assert out["stops"][0]["notes"] == "حلو"
    out = family.patch(f"/api/visits/stops/{sid}", json={"contact_status": "contacted"}).json()
    assert out["stops"][0]["notes"] == "حلو" and out["stops"][0]["contact_status"] == "contacted"
    out = family.patch(f"/api/visits/stops/{sid}", json={"notes": None}).json()
    assert out["stops"][0]["notes"] is None


def test_rating_uses_the_shared_learn_trigger(db, family):
    assert visits_route.enqueue_learn_if_due is listings_route.enqueue_learn_if_due
    ids = seed(db)
    for _ in range(9):
        db.add(Reaction(listing_id=ids[0], kind="bookmark"))
    db.commit()
    sid = make_trip(family, ids[:1])["stops"][0]["id"]
    family.patch(f"/api/visits/stops/{sid}", json={"contact_status": "visited"})
    assert db.query(Job).filter_by(type="learn").count() == 0
    family.patch(f"/api/visits/stops/{sid}", json={"rating": 4})
    assert db.query(Job).filter_by(type="learn").count() == 1
    family.patch(f"/api/visits/stops/{sid}", json={"rating": 4})  # same value again: no second reaction
    assert db.query(Reaction).filter_by(kind="visit_rating").count() == 1
    family.patch(f"/api/visits/stops/{sid}", json={"rating": 2})  # changed rating: a new reaction, latest wins in the learner
    assert db.query(Reaction).filter_by(kind="visit_rating").count() == 2


def test_stop_flags_old_price_and_hidden_check_failed(db, family):
    ids = seed(db)
    t = make_trip(family, ids[:2])
    sids = [s["id"] for s in t["stops"]]
    db.get(VisitStop, sids[0]).flags = ["price_changed", "check_failed"]
    db.get(VisitStop, sids[0]).old_price = 2_000_000
    db.get(VisitStop, sids[1]).flags = ["check_failed"]
    db.commit()
    stops = family.get(f"/api/visits/trips/{t['id']}").json()["stops"]
    assert stops[0]["flags"] == ["price_changed"] and stops[0]["old_price"] == 2_000_000
    assert stops[1]["flags"] == [] and stops[1]["old_price"] is None


def test_trips_list_filter_and_order(db, family):
    ids = seed(db)
    a = make_trip(family, ids[:1], date="2026-12-05")
    b = make_trip(family, ids[:1], date="2026-12-12")
    c = make_trip(family, ids[:1], date="2026-12-01")
    assert family.patch(f"/api/visits/trips/{c['id']}", json={"status": "done"}).json()["status"] == "done"
    assert family.patch(f"/api/visits/trips/{a['id']}", json={"status": "cancelled"}).json()["status"] == "cancelled"
    assert [t["id"] for t in family.get("/api/visits/trips?status=planned").json()] == [b["id"]]
    assert [t["id"] for t in family.get("/api/visits/trips?status=done").json()] == [c["id"]]
    assert [t["id"] for t in family.get("/api/visits/trips").json()] == [b["id"], a["id"], c["id"]]
    assert [t["id"] for t in family.get("/api/visits/trips?status=all").json()] == [b["id"], a["id"], c["id"]]
    assert family.get("/api/visits/trips?status=zzz").status_code == 422
    assert family.patch(f"/api/visits/trips/{c['id']}", json={"status": "nope"}).status_code == 422
    assert family.get("/api/visits/trips/999").status_code == 404
    assert family.post("/api/visits/trips/999/replan").status_code == 404
    assert family.post("/api/visits/trips/999/precheck").status_code == 404


JPEG_BYTES = b"\xff\xd8\xff\xe0jpegbytes"


def test_photo_upload_is_private_and_served_behind_auth(db, family, app_client, settings_env, tmp_path):
    priv, pub = tmp_path / "private", tmp_path / "pub"
    settings_env(VISIT_PHOTOS_DIR=str(priv), PHOTOS_DIR=str(pub), SERVE_PHOTOS="true")
    ids = seed(db)
    sid = make_trip(family, ids[:1])["stops"][0]["id"]
    r = family.post(f"/api/visits/stops/{sid}/photos", files={"file": ("a.jpg", JPEG_BYTES, "image/jpeg")})
    assert r.status_code == 204
    row = db.query(VisitPhoto).one()
    assert row.stop_id == sid and row.path.startswith(f"{sid}/") and row.path.endswith(".jpg")
    assert (priv / row.path).read_bytes() == JPEG_BYTES
    assert not list(pub.rglob("*.jpg")) if pub.exists() else True  # never under the public photos dir
    urls = family.get(f"/api/visits/trips/{db.query(VisitTrip).one().id}").json()["stops"][0]["photos"]
    assert urls == [f"/api/visits/photos/{row.id}"] and not urls[0].startswith("/photos")
    got = family.get(urls[0])
    assert got.status_code == 200 and got.content == JPEG_BYTES and got.headers["content-type"] == "image/jpeg"
    app_client.cookies.clear()
    assert app_client.get(urls[0]).status_code == 401
    assert app_client.get(f"/photos/visits/{row.path}").status_code == 404  # not reachable through the public mount


def test_photo_upload_rejections(db, family, settings_env, tmp_path):
    settings_env(VISIT_PHOTOS_DIR=str(tmp_path / "private"))
    ids = seed(db)
    sid = make_trip(family, ids[:1])["stops"][0]["id"]
    url = f"/api/visits/stops/{sid}/photos"
    assert family.post(url, files={"file": ("a.txt", b"hi", "text/plain")}).status_code == 422
    assert family.post(url, files={"file": ("a.svg", b"<svg onload=x/>", "image/svg+xml")}).status_code == 422
    assert family.post(url, files={"file": ("a.png", b"x" * (8 * 1024 * 1024 + 1), "image/png")}).status_code == 413
    assert family.post("/api/visits/stops/999/photos", files={"file": ("a.png", b"x", "image/png")}).status_code == 404
    assert family.get("/api/visits/photos/999").status_code == 404
    assert db.query(VisitPhoto).count() == 0


def test_stop_source_url_is_first_source_or_null(db, family):
    ids = seed(db)
    db.query(ListingSource).filter_by(listing_id=ids[0]).update({"url": "https://aqar.example/1"})
    db.add(ListingSource(listing_id=ids[0], source="haraj", source_id="h1", url="https://haraj.example/1", raw={}))
    db.commit()
    stops = make_trip(family, ids[:2])["stops"]
    by = {s["listing"]["id"]: s for s in stops}
    assert by[ids[0]]["source_url"] == "https://aqar.example/1"  # oldest source, as the listing detail's sources[0]
    assert by[ids[1]]["source_url"] == "u"
    db.query(ListingSource).filter_by(listing_id=ids[1]).delete(); db.commit()
    trip_id = db.query(VisitTrip).one().id
    assert {s["listing"]["id"]: s["source_url"] for s in family.get(f"/api/visits/trips/{trip_id}").json()["stops"]}[ids[1]] is None


def test_photo_type_is_sniffed_from_the_bytes_not_trusted_from_the_client(db, family, settings_env, tmp_path):
    """M20: Android pickers can send an empty content type; a mislabelled file must not be stored as an image."""
    settings_env(VISIT_PHOTOS_DIR=str(tmp_path / "private"))
    ids = seed(db)
    sid = make_trip(family, ids[:1])["stops"][0]["id"]
    url = f"/api/visits/stops/{sid}/photos"
    samples = {"jpg": JPEG_BYTES, "png": b"\x89PNG\r\n\x1a\n" + b"0" * 8, "webp": b"RIFF\x10\x00\x00\x00WEBPVP8 ",
               "heic": b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00"}
    for ext, data in samples.items():
        assert family.post(url, files={"file": ("x", data, "")}).status_code == 204, ext  # no content type at all
    assert sorted(p.path.rsplit(".", 1)[1] for p in db.query(VisitPhoto)) == sorted(samples)
    assert family.post(url, files={"file": ("a.jpg", b"<html>not an image</html>", "image/jpeg")}).status_code == 422
    assert db.query(VisitPhoto).count() == 4

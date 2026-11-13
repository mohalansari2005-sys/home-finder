import json

from homefinder.db import session_scope
from homefinder.models import Job, Listing, Preferences, PriceHistory, WorkerStatus
from homefinder.server.agent.tools import make_tools


def tools():
    return {t.name: t for t in make_tools(session_scope)}


def test_tool_names():
    assert set(tools()) == {"get_preferences", "update_preferences", "search_listings", "get_listing",
                            "compare_listings", "request_scrape", "get_filter_suggestions",
                            "apply_filter_suggestion"}


def test_get_preferences_tool(db):
    out = json.loads(tools()["get_preferences"].invoke({}))
    assert out["hard_filters"]["city"] == "الرياض" and "price" in out["weights"] and "targets" in out


def test_update_preferences_tool(db):
    out = json.loads(tools()["update_preferences"].invoke({"hard_filters": {"price_max": 2_000_000}, "weights": {"street_width": 2}}))
    assert out["ok"] and out["preferences"]["hard_filters"]["price_max"] == 2_000_000
    db.expire_all()
    p = db.get(Preferences, 1)
    assert "street_width" in p.locked_weights
    assert db.query(Job).filter_by(type="rescore_all").count() == 1
    assert db.query(Job).filter_by(type="scrape_search").count() == 2  # price_max is search-relevant: aqar + haraj


def test_update_preferences_tool_rejects_invalid(db):
    out = json.loads(tools()["update_preferences"].invoke({"hard_filters": {"price_max": 5}}))
    assert out["ok"] is False and "price_max" in out["error"]
    assert db.get(Preferences, 1) is None or db.get(Preferences, 1).hard_filters.get("price_max") is None
    assert db.query(Job).count() == 0


def test_update_preferences_tool_rejects_unknown_weight(db):
    out = json.loads(tools()["update_preferences"].invoke({"weights": {"vibes": 3}}))
    assert out["ok"] is False


def test_search_listings_tool(db):
    db.add_all([Listing(title="أ", district="النرجس", price=1_500_000, score=80, bedrooms=5),
                Listing(title="ب", district="الملقا", price=3_000_000, score=90, bedrooms=6),
                Listing(title="ج", district="النرجس", price=1_000_000, score=60, family_status="rejected")])
    db.commit()
    out = json.loads(tools()["search_listings"].invoke({"district": "حي النرجس", "max_price": 2_000_000}))
    assert [c["title"] for c in out["cards"]] == ["أ"]
    assert out["cards"][0]["status"] == "active" and "price_drop" in out["cards"][0]


def test_search_listings_excludes_removed_merged_and_sorts(db):
    a = Listing(title="a", price=3, score=10); db.add(a); db.flush()
    db.add_all([Listing(title="b", price=1, score=50), Listing(title="gone", status="removed", score=99),
                Listing(title="dup", merged_into_id=a.id, score=99), Listing(title="c", price=2, score=70)])
    db.commit()
    t = tools()["search_listings"]
    assert [c["title"] for c in json.loads(t.invoke({}))["cards"]] == ["c", "b", "a"]
    assert [c["title"] for c in json.loads(t.invoke({"sort": "price"}))["cards"]] == ["b", "c", "a"]
    assert len(json.loads(t.invoke({"limit": 1}))["cards"]) == 1
    assert len(json.loads(t.invoke({"limit": 500}))["cards"]) == 3  # clamped to 10


def test_cards_carry_price_drop_and_top_reasons(db):
    l = Listing(title="x", price=900_000, score=70,
                score_breakdown={"contributions": [{"factor": "price"}, {"factor": "commute_work"}, {"factor": "yard"}]})
    db.add(l); db.flush()
    db.add(PriceHistory(listing_id=l.id, price=1_000_000)); db.flush()
    db.add(PriceHistory(listing_id=l.id, price=900_000)); db.commit()
    c = json.loads(tools()["search_listings"].invoke({}))["cards"][0]
    assert c["price_drop"]["from"] == 1_000_000 and c["top_reasons"] == ["price", "commute_work"]


def test_get_listing_and_compare_tools(db):
    a, b = Listing(title="أ", price=1, description="وصف"), Listing(title="ب", price=2)
    db.add_all([a, b]); db.commit()
    got = json.loads(tools()["get_listing"].invoke({"listing_id": a.id}))
    assert got["listing"]["description"] == "وصف" and got["cards"][0]["id"] == a.id
    assert json.loads(tools()["get_listing"].invoke({"listing_id": 99999})) == {"error": "not found"}
    cmp_ = json.loads(tools()["compare_listings"].invoke({"listing_ids": [a.id, b.id, 99999]}))
    assert [c["id"] for c in cmp_["cards"]] == [a.id, b.id]


def test_request_scrape_online_enqueues(db):
    from sqlalchemy import func
    db.add(WorkerStatus(id=1, last_seen=func.now())); db.commit()
    out = json.loads(tools()["request_scrape"].invoke({"note": "فلل الياسمين"}))
    assert out["mode"] == "queued" and db.query(Job).filter_by(type="scrape_search").count() == 2  # aqar + haraj


def test_request_scrape_offline_uses_fallback(db, monkeypatch):
    from homefinder.server.agent import fallback_search
    monkeypatch.setattr(fallback_search, "run", lambda sf: {"ingested": 3})
    out = json.loads(tools()["request_scrape"].invoke({"note": ""}))
    assert out == {"mode": "fallback", "ingested": 3}


def test_filter_suggestion_tools(db):
    from homefinder.models import Reaction
    for a in [18, 20, 22, 25, 30]:
        l = Listing(building_age_years=a, family_status="rejected"); db.add(l); db.flush()
        db.add(Reaction(listing_id=l.id, kind="reject", reason_code="too_old"))
    db.commit()
    t = tools()
    out = json.loads(t["get_filter_suggestions"].invoke({}))
    assert [x["code"] for x in out["suggestions"]] == ["too_old"]
    assert json.loads(t["apply_filter_suggestion"].invoke({"code": "nope"}))["ok"] is False
    assert json.loads(t["apply_filter_suggestion"].invoke({"code": "too_old"}))["ok"] is True
    db.expire_all()
    assert db.get(Preferences, 1).hard_filters["building_age_max"] == 21
    assert db.query(Job).filter_by(type="rescore_all").count() == 1

import json
from pathlib import Path

from homefinder.schemas import SearchQuery
from homefinder.worker.sources.aqar import AqarAdapter, parse_listing
from homefinder.worker.sources.base import Pacer

FX = Path(__file__).parents[1] / "fixtures" / "aqar"


def load(name):
    return json.loads((FX / name).read_text("utf-8"))


class FakeTransport:
    def __init__(self, pages: list[dict], districts: dict | None = None):
        self.pages, self.districts, self.calls = pages, districts, []

    def post_graphql(self, body):
        self.calls.append(body)
        if body["operationName"] == "getAllDistricts":
            return self.districts
        i = body["variables"]["from"] // 20
        return self.pages[i] if i < len(self.pages) else {"data": {"Web": {"find": {"total": 0, "listings": []}}}}

    def close(self):
        pass


def nosleep_pacer():
    return Pacer(sleep=lambda s: None)


def test_parse_real_fixture_listing():
    d = load("find_villa_riyadh.json")["data"]["Web"]["find"]["listings"][0]
    r = parse_listing(d)
    assert r.source == "aqar" and r.source_id == str(d["id"])
    assert r.url.startswith("https://sa.aqar.fm/")
    assert r.fields.property_type == "villa"
    assert r.fields.price is None or 100_000 <= r.fields.price <= 100_000_000
    assert all(u.startswith("https://") for u in r.photo_urls)


def test_parse_malformed_values():
    d = {"id": 7, "category": 3, "price": 0, "area": "", "age": None, "beds": "abc", "wc": True,
         "street_width": "15", "location": None, "imgs": None, "content": None, "title": "فيلا",
         "district": "حي النرجس", "city": "الرياض", "path": "/x/7", "user": None, "extended_details": None}
    r = parse_listing(d)
    f = r.fields
    assert f.price is None and f.land_area_m2 is None and f.bedrooms is None and f.bathrooms is None
    assert f.street_width_m == 15 and f.lat is None and r.photo_urls == [] and r.seller_phone is None
    assert r.geo_precision is None


def test_parse_area_mapping_by_type():
    villa = parse_listing({"id": 1, "category": 3, "area": 400, "extended_details": {"internal_area": 550}, "path": "/a"})
    apt = parse_listing({"id": 2, "category": 6, "area": 180, "path": "/b"})
    assert villa.fields.land_area_m2 == 400 and villa.fields.built_area_m2 == 550
    assert apt.fields.built_area_m2 == 180 and apt.fields.land_area_m2 is None


def test_search_paginates_until_short_page_and_filters_price():
    full = load("find_villa_riyadh.json")
    listings = full["data"]["Web"]["find"]["listings"]
    page0 = {"data": {"Web": {"find": {"total": 99, "listings": (listings * 20)[:20]}}}}
    page1 = {"data": {"Web": {"find": {"total": 99, "listings": listings[:3]}}}}
    t = FakeTransport([page0, page1])
    a = AqarAdapter(t, pacer=nosleep_pacer())
    out = list(a.search(SearchQuery(property_types=["villa"], max_pages=5)))
    assert len([c for c in t.calls if c["operationName"] == "findListings"]) == 2
    assert len(out) == 23
    cheap = list(AqarAdapter(FakeTransport([page1]), pacer=nosleep_pacer()).search(SearchQuery(price_max=1)))
    assert cheap == []


def test_search_by_district_resolves_ids_with_normalization():
    districts = {"data": {"Web": {"districts": [{"name": "النرجس", "district_id": 501, "count": 10},
                                                 {"name": "الياسمين", "district_id": 502, "count": 5}]}}}
    t = FakeTransport([], districts=districts)
    list(AqarAdapter(t, pacer=nosleep_pacer()).search(SearchQuery(districts=["حي النرجس"], max_pages=1)))
    finds = [c for c in t.calls if c["operationName"] == "findListings"]
    assert [c["variables"]["where"]["category"] for c in finds] == [{"eq": 3}]  # one villa search, not two


def test_health_flags_mostly_missing_prices():
    a = AqarAdapter(FakeTransport([]), pacer=nosleep_pacer())
    bad = [parse_listing({"id": i, "category": 3, "price": None, "area": 300, "district": "x", "path": "/p"}) for i in range(12)]
    rep = a.health(bad)
    assert not rep.ok and "price" in rep.reason


def test_street_direction_mapping_matches_aqar_dictionary():
    """Aqar's own dictionary: 3 = west, 4 = south (the M1 mapping had them swapped), see docs/sources/aqar.md."""
    expected = {1: "north", 2: "east", 3: "west", 4: "south", 5: "northeast", 6: "southeast", 7: "southwest", 8: "northwest"}
    for sd, facing in expected.items():
        assert parse_listing({"id": 1, "category": 3, "street_direction": sd, "path": "/a"}).fields.facing == facing
    assert parse_listing({"id": 1, "category": 3, "street_direction": 9, "path": "/a"}).fields.street_count == 3
    assert parse_listing({"id": 1, "category": 3, "street_direction": 10, "path": "/a"}).fields.street_count == 4
    # the live by-id fixture's details text says "الواجهة غرب" for street_direction 3
    d = load("listing_by_id.json")["data"]["Web"]["listing"]
    assert d["street_direction"] == 3 and parse_listing(d).fields.facing == "west"


class ByIdTransport:
    def __init__(self, resp): self.resp, self.calls = resp, []
    def post_graphql(self, body): self.calls.append(body); return self.resp
    def close(self): pass


def test_fetch_by_id_uses_listing_query_and_parses():
    t = ByIdTransport(load("listing_by_id.json"))
    r = AqarAdapter(t, pacer=nosleep_pacer()).fetch("6906153")
    assert t.calls[0]["operationName"] == "getListing" and t.calls[0]["variables"] == {"id": 6906153}
    assert "listing(id: $id)" in t.calls[0]["query"] and "extended_details" not in t.calls[0]["query"]
    assert r.source == "aqar" and r.source_id == "6906153" and r.fields.price == 3_150_000
    assert r.fields.property_type == "villa" and r.fields.land_area_m2 == 250 and r.fields.built_area_m2 is None


def test_fetch_returns_none_when_listing_not_found_or_unpublished():
    assert AqarAdapter(ByIdTransport(load("listing_not_found.json")), pacer=nosleep_pacer()).fetch("999999999") is None
    d = load("listing_by_id.json")
    d["data"]["Web"]["listing"]["published"] = False
    assert AqarAdapter(ByIdTransport(d), pacer=nosleep_pacer()).fetch("6906153") is None


def test_fetch_raises_on_unexpected_graphql_error():
    import pytest
    bad = {"errors": [{"code": 414, "message": "Field x is not defined"}], "data": None}
    with pytest.raises(RuntimeError):
        AqarAdapter(ByIdTransport(bad), pacer=nosleep_pacer()).fetch("1")
    weird = {"data": {"Web": {"listing": None}}, "errors": [{"code": "Boom", "message": ""}]}
    with pytest.raises(RuntimeError):
        AqarAdapter(ByIdTransport(weird), pacer=nosleep_pacer()).fetch("1")


def test_townhouses_are_searched_in_the_villa_category_once():
    page = {"data": {"Web": {"find": {"total": 0, "listings": []}}}}
    t = FakeTransport([page, page])
    list(AqarAdapter(t, pacer=nosleep_pacer()).search(SearchQuery(property_types=["villa", "townhouse"], max_pages=1)))
    finds = [c for c in t.calls if c["operationName"] == "findListings"]
    assert [c["variables"]["where"]["category"] for c in finds] == [{"eq": 3}]  # one villa search, not two

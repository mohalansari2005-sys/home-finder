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
    assert len(finds) == 1 and finds[0]["variables"]["where"]["district_id"] == {"eq": 501}


def test_health_flags_mostly_missing_prices():
    a = AqarAdapter(FakeTransport([]), pacer=nosleep_pacer())
    bad = [parse_listing({"id": i, "category": 3, "price": None, "area": 300, "district": "x", "path": "/p"}) for i in range(12)]
    rep = a.health(bad)
    assert not rep.ok and "price" in rep.reason

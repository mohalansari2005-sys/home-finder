import json
from pathlib import Path

from homefinder.schemas import SearchQuery
from homefinder.worker.sources.base import Pacer
from homefinder.worker.sources.haraj import HarajAdapter, parse_post

FX = Path(__file__).parents[1] / "fixtures" / "haraj"


def posts():
    """The list of post dicts inside the scrubbed search fixture."""
    from homefinder.worker.sources.haraj import extract_posts
    return extract_posts(json.loads((FX / "search_villas_riyadh.json").read_text("utf-8")))


def minimal(**kw):
    return {"id": 1, "title": "فيلا للبيع حي الملقا", "bodyTEXT": "فيلا دورين", "city": "الرياض", "tags": ["فلل للبيع"], **kw}


def test_parse_real_post():
    r = parse_post(posts()[0])
    assert r.source == "haraj" and r.url.startswith("https://haraj.com.sa/")
    assert r.fields.description and r.fields.city
    assert r.fields.property_type == "villa"
    assert r.fields.district == "الفاروق"
    assert r.seller_phone is None and r.seller_name is None
    assert r.geo_precision == "approximate" and 24 < r.fields.lat < 25 and 46 < r.fields.lng < 47
    assert all(u.startswith("https://") for u in r.photo_urls) and r.photo_urls
    assert "&ndash;" not in r.fields.description  # html entities decoded
    assert r.listed_at is not None


def test_parse_minimal_post():
    r = parse_post({"id": 1, "title": "فيلا للبيع حي الملقا", "bodyTEXT": "فيلا دورين", "city": "الرياض", "tags": ["فلل للبيع"]},
                   field_map_override=True)
    assert r is not None and r.fields.price is None and r.fields.lat is None and r.photo_urls == []
    assert r.fields.district == "الملقا"  # regex fallback on the title


def test_district_regex_falls_back_to_body():
    r = parse_post(minimal(title="فيلا للبيع", bodyTEXT="تقع في حي النرجس الشمالي قريبة"), field_map_override=True)
    assert r.fields.district == "النرجس الشمالي"


def test_rent_posts_skipped():
    assert parse_post({"id": 2, "title": "فيلا للإيجار", "tags": ["فلل للإيجار"], "city": "الرياض"}, field_map_override=True) is None
    # sale tag but the title says rent
    assert parse_post(minimal(title="دور الايجار غصون"), field_map_override=True) is None


def test_non_sale_and_wanted_posts_skipped():
    assert parse_post(minimal(tags=["حراج العقار"]), field_map_override=True) is None
    assert parse_post(minimal(title="مطلوب فيلا في الملقا"), field_map_override=True) is None
    assert parse_post(minimal(status=False), field_map_override=True) is None


def test_price_from_api_only_and_strings_tolerated():
    assert parse_post(minimal(price={"inputPrice": 1_800_000, "formattedPrice": "1,800,000"})).fields.price == 1_800_000
    assert parse_post(minimal(price={"inputPrice": None, "formattedPrice": "1,200,000 ريال"})).fields.price == 1_200_000
    assert parse_post(minimal(price="1,200,000"), field_map_override=True).fields.price == 1_200_000
    assert parse_post(minimal(price=0), field_map_override=True).fields.price is None
    assert parse_post(minimal(price=None), field_map_override=True).fields.price is None


def test_malformed_values_do_not_crash():
    r = parse_post(minimal(price="", imagesList=None, geoHash=None, geoNeighborhood=None, bodyTEXT=None, tags=["فلل للبيع"],
                           postDate="x"))
    assert r is not None and r.fields.price is None and r.photo_urls == [] and r.fields.lat is None and r.listed_at is None


def test_geo_outside_saudi_bounds_dropped():
    assert parse_post(minimal(geoHash="u4pruydqq")).fields.lat is None  # a Scandinavian geohash
    assert parse_post(minimal(geoHash="not a hash!")).fields.lat is None


def test_haraj_health_tolerates_missing_price():
    rs = [parse_post({"id": i, "title": "فيلا", "bodyTEXT": "نص", "city": "الرياض", "tags": ["فلل للبيع"]}, field_map_override=True)
          for i in range(20)]
    assert HarajAdapter(transport=None, pacer=Pacer(sleep=lambda s: None)).health(rs).ok


def test_haraj_health_fails_when_text_missing():
    rs = [parse_post({"id": i, "title": "فيلا", "bodyTEXT": "", "city": "الرياض", "tags": ["فلل للبيع"]}, field_map_override=True)
          for i in range(20)]
    rep = HarajAdapter(transport=None, pacer=Pacer(sleep=lambda s: None)).health(rs)
    assert not rep.ok and "body" in rep.reason


def test_search_paginates_and_stops():
    class T:
        def __init__(self): self.calls = []
        def search(self, tag, city, page):
            self.calls.append(page)
            from homefinder.worker.sources.haraj import wrap_posts_for_test
            return wrap_posts_for_test(posts() if page == 0 else [])
        def close(self): pass
    t = T()
    out = list(HarajAdapter(t, pacer=Pacer(sleep=lambda s: None)).search(SearchQuery(property_types=["villa"], max_pages=5)))
    assert t.calls == [0, 1] and len(out) >= 1


def test_search_uses_tag_per_type_and_district_tags_and_filters():
    from homefinder.worker.sources.haraj import wrap_posts_for_test

    class T:
        def __init__(self): self.calls = []
        def search(self, tag, city, page):
            self.calls.append((tag, city, page))
            if page:
                return wrap_posts_for_test([])
            return wrap_posts_for_test([minimal(id=1, geoNeighborhood="النرجس"), minimal(id=2, geoNeighborhood="الملقا"),
                                        minimal(id=3, geoNeighborhood=None, title="فيلا", bodyTEXT="x"),
                                        minimal(id=4, geoNeighborhood="النرجس", city="الخرج"),
                                        minimal(id=5, geoNeighborhood="النرجس", price={"inputPrice": 3_000_000})])
        def close(self): pass
    t = T()
    q = SearchQuery(property_types=["villa", "apartment"], districts=["حي النرجس"], price_max=2_000_000, max_pages=3)
    out = list(HarajAdapter(t, pacer=Pacer(sleep=lambda s: None)).search(q))
    assert [c[0] for c in t.calls] == ["فلل للبيع في حي النرجس في الرياض", "فلل للبيع في حي النرجس في الرياض",
                                       "شقق للبيع في حي النرجس في الرياض", "شقق للبيع في حي النرجس في الرياض"][:len(t.calls)]
    assert {c[0] for c in t.calls} == {"فلل للبيع في حي النرجس في الرياض", "شقق للبيع في حي النرجس في الرياض"}
    # only النرجس (and unknown-district) posts, same city, not above the price cap
    assert sorted({r.source_id for r in out}) == ["1", "3"]


def test_fetch_returns_listing_or_none():
    class T:
        def post(self, pid): return minimal(id=int(pid)) if pid == "7" else None
        def close(self): pass
    a = HarajAdapter(T(), pacer=Pacer(sleep=lambda s: None))
    assert a.fetch("7").source_id == "7" and a.fetch("8") is None

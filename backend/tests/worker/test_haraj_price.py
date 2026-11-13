import pytest

from homefinder.dedupe import dedupe_and_merge
from homefinder.models import Listing
from homefinder.schemas import CanonicalFields, RawListing
from homefinder.worker.ingest import ingest_raw
from homefinder.worker.sources.haraj import decode_geohash, parse_post
from homefinder.worker.sources.haraj_text import parse_price_from_text

# made-up texts only: no real sellers, phones or listings
CASES = [
    ("السعر: ١,٨٥٠,٠٠٠", 1_850_000),                                  # Arabic-Indic digits, western separator
    ("المطلوب مليون و ٨٥٠ ألف", 1_850_000),                           # words + thousands part
    ("سعر الوحدة: 1850000 ريال", 1_850_000),                          # licence block style
    ("السعر 2.5 مليون ريال", 2_500_000),
    ("السعر ٢٫٥ مليون", 2_500_000),                                   # Arabic decimal separator
    ("السعر 3 مليون ونص", 3_500_000),
    ("الحد الأقصى مليون و نصف", 1_500_000),
    ("الحد 1,700,000 ريال فقط", 1_700_000),
    ("المطلوب 950 الف", 950_000),
    ("المطلوب ٩٥٠ ألف ريال", 950_000),
    ("سعر الوحدة: ٢٬٣٠٠٬٠٠٠ ريال", 2_300_000),                        # Arabic thousands separator
    ("السعر مليونين", 2_000_000),
    ("السعر: 1850 ألف", 1_850_000),
    ("للبيع بسعر 1,450,000 ريال قابل للتفاوض", 1_450_000),            # بسعر
    ("السعر: 1.850.000", 1_850_000),                                   # dots as thousands separators
    ("السعر:\n1,750,000", 1_750_000),                                  # number on the next line
    ("المساحة 400 م2 والشارع 20 م السعر 1,900,000", 1_900_000),         # area and street width before the price
    ("سعر المتر 2500 والسعر الاجمالي 1,600,000", 1_600_000),            # price per metre is not the price
    ("الحد 1,900,000 ... السعر 2,000,000", 2_000_000),                  # السعر wins over الحد
    ("سعر الزاوية 3,300,000\nسعر الجنوبية : 3,150,000\nسعر الوحدة: 3150000", 3_150_000),  # unit price wins
    # rejected
    ("السعر 85 الف", None),                                            # below 100,000
    ("السعر 80 مليون", None),                                          # above 50,000,000
    ("السعر 99,999", None),
    ("السعر مناسب للتواصل 0500000000", None),                          # phone
    ("السعر للتواصل 966500000000", None),
    ("السعر للتواصل 055 5555555", None),                               # phone split in two
    ("السعر: 1,200,000 م2", None),                                     # that is an area
    ("الحد 600 متر", None),
    ("السعر شارع عرض 20 متر", None),
    ("المطلوب مليون و 850", None),                                     # ambiguous: 850 what?
    ("فيلا جميلة بحديقة واسعة 1,800,000", None),                       # no price keyword (and بحديقة is not الحد)
    ("فيلا للبيع السعر مفتوح للنقاش", None),
    ("", None),
    (None, None),
]


@pytest.mark.parametrize("text,expected", CASES)
def test_parse_price_from_text(text, expected):
    assert parse_price_from_text(text) == expected


def test_table_has_enough_cases():
    assert len(CASES) >= 15


def haraj_post(body, **kw):
    return {"id": 77, "title": "فيلا للبيع حي الملقا", "bodyTEXT": body, "city": "الرياض", "tags": ["فلل للبيع"],
            "geo": "thqcnq6zj", **kw}


def test_parse_post_uses_text_price_when_api_price_is_null():
    r = parse_post(haraj_post("فيلا دورين\nالسعر: ١,٨٥٠,٠٠٠"), field_map_override=True)
    assert r.fields.price == 1_850_000


def test_api_price_wins_over_text():
    r = parse_post(haraj_post("السعر: 1,850,000", price={"inputPrice": 1_700_000}), field_map_override=True)
    assert r.fields.price == 1_700_000


def test_title_is_a_fallback_source():
    r = parse_post(haraj_post("فيلا دورين", title="فيلا للبيع السعر 2.1 مليون"), field_map_override=True)
    assert r.fields.price == 2_100_000


def aqar_twin(lat, lng, price=1_850_000):
    return RawListing(source="aqar", source_id="A1", url="https://example.test/a1", geo_precision="exact",
                      fields=CanonicalFields(property_type="villa", price=price, built_area_m2=400, land_area_m2=300,
                                             lat=lat, lng=lng))


def _merge_outcome(db, haraj_body):
    raw = parse_post(haraj_post(haraj_body), field_map_override=True)
    lat, lng = raw.fields.lat, raw.fields.lng
    older = ingest_raw(db, aqar_twin(lat, lng)).listing_id
    newer = ingest_raw(db, raw).listing_id
    # Areas on Haraj come from the LLM extraction step; simulate its result here.
    l = db.get(Listing, newer)
    l.built_area_m2, l.land_area_m2 = 405, 300
    db.commit()
    return older, newer, dedupe_and_merge(db, newer)


def test_haraj_post_with_text_price_merges_with_its_aqar_duplicate(db):
    assert decode_geohash("thqcnq6zj") is not None
    older, newer, merged = _merge_outcome(db, "فيلا دورين\nالسعر: ١,٨٥٠,٠٠٠ ريال")
    assert merged == older
    db.expire_all()
    assert db.get(Listing, newer).merged_into_id == older


def test_without_a_text_price_dedupe_cannot_match(db):
    older, newer, merged = _merge_outcome(db, "فيلا دورين للتواصل")
    assert merged is None

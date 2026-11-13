import logging

import pytest

from homefinder.worker.sources.haraj import parse_post
from homefinder.worker.sources.haraj_text import parse_phone_from_text

OK = "966551234567"
CASES = [
    ("local 05 form", "للتواصل 0551234567", OK),
    ("9-digit form", "جوال 551234567 فقط", OK),
    ("arabic-indic digits", "للتواصل ٠٥٥١٢٣٤٥٦٧", OK),
    ("dashes", "اتصل 055-123-4567", OK),
    ("spaces", "اتصل 055 123 4567 الان", OK),
    ("dots", "اتصل 055.123.4567.", OK),
    ("plus 966 with spaces", "+966 55 123 4567", OK),
    ("arabic-indic plus 966", "+٩٦٦ ٥٥ ١٢٣ ٤٥٦٧", OK),
    ("966 form", "966551234567 واتساب", OK),
    ("00966 form", "00966551234567", OK),
    ("other mobile prefix", "واتس 0500000000", "966500000000"),
    ("word before number", "رقم الجوال: 055 1234 567", OK),
    ("number split by a word", "جوال 05512 واتس 34567", OK),
    ("first of two wins", "0551234567 او 0500000000", OK),
    ("licence is skipped, phone kept", "رقم ترخيص الاعلان 7200000000 جوال 0551234567", OK),
    ("fal licence skipped", "رخصة فال: 1100000000 للتواصل 0500000000", "966500000000"),
    ("landline", "للتواصل 0112345678", None),
    ("landline with area dashes", "هاتف 011-234-5678", None),
    ("licence that looks like a mobile", "رقم الترخيص 0500000000", None),
    ("fal licence that looks like a mobile", "رخصة فال 551234567", None),
    ("ad id that looks like a mobile", "رقم الاعلان 551234567", None),
    ("price with commas", "السعر 5,500,000 ريال", None),
    ("price with dots", "السعر 5.500.000 ريال", None),
    ("price in digits", "المطلوب 2500000 ريال", None),
    ("area and street", "مساحة 500 م عرض الشارع 20", None),
    ("not a mobile prefix", "0451234567", None),
    ("too long", "05512345678", None),
    ("digits inside a longer number", "رقم 1105512345678", None),
    ("site mask text", "( رقم الجوال يظهر عند الضغط على زر تواصل )", None),
    ("empty", "", None),
]


@pytest.mark.parametrize("name,text,expected", CASES, ids=[c[0] for c in CASES])
def test_parse_phone_table(name, text, expected):
    assert parse_phone_from_text(text) == expected


def test_title_is_searched_after_body_and_none_ok():
    assert parse_phone_from_text(None, "فيلا 0551234567") == OK
    assert parse_phone_from_text("بدون رقم", None) is None


def test_post_own_id_is_not_a_phone():
    assert parse_phone_from_text("فيلا 551234567", exclude={"551234567"}) is None


def minimal(**kw):
    return {"id": 551234567, "title": "فيلا للبيع حي الملقا", "bodyTEXT": "فيلا دورين", "city": "الرياض",
            "tags": ["فلل للبيع"], **kw}


def test_parse_post_sets_seller_phone_from_body_only(caplog):
    with caplog.at_level(logging.DEBUG):
        r = parse_post(minimal(bodyTEXT="فيلا للبيع، جوال 0500000000"))
        none = parse_post(minimal(bodyTEXT="فيلا للبيع"))
    assert r.seller_phone == "966500000000" and none.seller_phone is None
    assert "500000000" not in caplog.text


def test_parse_post_ignores_phone_equal_to_post_id():
    assert parse_post(minimal(bodyTEXT="رقم 551234567")).seller_phone is None


def test_source_provided_phone_is_kept_on_ingest(db):
    from homefinder.models import ListingSource
    from homefinder.schemas import CanonicalFields, RawListing
    from homefinder.worker.ingest import ingest_raw
    ingest_raw(db, RawListing(source="aqar", source_id="1", url="u", fields=CanonicalFields(), seller_phone="0551234567"))
    ingest_raw(db, RawListing(source="aqar", source_id="1", url="u", fields=CanonicalFields(), seller_phone=None))
    db.commit()
    assert db.query(ListingSource).one().seller_phone == "0551234567"

import pytest

from homefinder.worker.sources.haraj import parse_post
from homefinder.worker.sources.haraj_text import parse_areas_from_text

L, B = "land_area_m2", "built_area_m2"

# made-up texts only
CASES = [
    ("مساحة العقار: 200", {L: 200}),                                     # licence block, no unit
    ("المساحة: 438 م2 لكل فيلا", {L: 438}),
    ("بمساحة أرض تبلغ 300 متر مربع", {L: 300}),                           # common prose form
    ("مساحة الأرض 450 م²", {L: 450}),
    ("مساحة الأرض: ٤٥٠ م٢", {L: 450}),                                   # Arabic-Indic digits and unit
    ("المساحة ٣٥٠ متر", {L: 350}),
    ("مساحة البناء 520 م2", {B: 520}),
    ("مساحة الأرض 400 م2 ومساحة البناء 600 م2", {L: 400, B: 600}),
    ("المساحة: 1,250 متر مربع", {L: 1250}),
    ("المساحة: ١٬٢٥٠ متر مربع", {L: 1250}),
    ("مساحة العقار 312.5 م2", {L: 312.5}),
    ("بمساحة 280 م2", {L: 280}),
    ("المساحة\n360 م", {L: 360}),
    ("مساحة العقار: 49", {}),                                            # below 50
    ("مساحة الأرض 20,001 م2", {}),                                       # above 20,000
    ("المساحة 20000 م2", {L: 20000}),
    ("مساحة العقار: 200\nعرض الشارع: 15", {L: 200}),                     # street width is not an area
    ("السعر 1,850,000 ريال", {}),                                        # a price is not an area
    ("المساحة 1,850,000 ريال", {}),
    ("مساحة غرفة النوم كبيرة", {}),
    ("", {}),
    (None, {}),
]


@pytest.mark.parametrize("text,expected", CASES)
def test_parse_areas_from_text(text, expected):
    assert parse_areas_from_text(text) == expected


def test_table_size():
    assert len(CASES) >= 10


def test_parse_post_fills_areas_from_body():
    d = {"id": 9, "title": "فيلا للبيع حي الملقا", "city": "الرياض", "tags": ["فلل للبيع"],
         "bodyTEXT": "فيلا دورين\nمساحة الأرض: 300 متر مربع\nمساحة البناء: 410 م2"}
    r = parse_post(d, field_map_override=True)
    assert r.fields.land_area_m2 == 300 and r.fields.built_area_m2 == 410


def test_real_licence_block_gives_land_area():
    from tests.worker.test_haraj import posts
    r = parse_post(posts()[0])
    assert r.fields.land_area_m2 == 200

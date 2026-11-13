import logging

import pytest

from homefinder.worker.ingest import ingest_raw
from homefinder.worker.sources.haraj import decode_geohash, parse_post
from homefinder.worker.sources.haraj_text import haversine_m, lower_precision, parse_maps_link

GEOHASH = "thqcnq6zj"
GH_LAT, GH_LNG = decode_geohash(GEOHASH)


def post(body, geo=GEOHASH):
    d = {"id": 5, "title": "فيلا للبيع حي الملقا", "bodyTEXT": body, "city": "الرياض", "tags": ["فلل للبيع"]}
    if geo:
        d["geo"] = geo
    return parse_post(d, field_map_override=True)


@pytest.mark.parametrize("body,expected", [
    ("الموقع: https://maps.google.com/?q=24.654,46.785", (24.654, 46.785)),
    ("https://www.google.com/maps?q=24.7,46.7&z=17", (24.7, 46.7)),
    ("https://www.google.com/maps/search/?api=1&query=24.71%2C46.69", (24.71, 46.69)),
    ("https://www.google.com/maps/place/x/@24.8123,46.6321,17z/data=!3m1", (24.8123, 46.6321)),
    ("https://www.google.com/maps/dir//24.8,46.6/@24.81,46.63,15z", (24.81, 46.63)),
    ("https://maps.google.com/maps?ll=24.65,46.78&z=16", (24.65, 46.78)),
    ("https://www.google.com/maps/place/x/data=!3d24.6!4d46.7", (24.6, 46.7)),
    ("https://maps.google.com/?q=24.7( رقم الجوال يظهر )", None),            # truncated by the site, no longitude
    ("https://maps.google.com/?q=51.5,-0.12", None),                          # outside Saudi Arabia
    ("https://maps.google.com/?q=0.0,0.0", None),
    ("https://example.test/?q=24.7,46.7", None),                              # not a maps link
    ("بدون رابط", None),
    (None, None),
])
def test_parse_maps_link(body, expected):
    assert parse_maps_link(body) == expected


def test_maps_link_is_preferred_over_geohash():
    r = post(f"الموقع https://maps.google.com/?q={GH_LAT + 0.004:.5f},{GH_LNG:.5f}")  # about 440 m away
    assert (r.fields.lat, r.fields.lng) == (round(GH_LAT + 0.004, 5), round(GH_LNG, 5))
    assert r.geo_precision == "approximate"


def test_far_disagreement_warns_and_lowers_precision(caplog):
    with caplog.at_level(logging.WARNING):
        r = post(f"https://maps.google.com/?q={GH_LAT + 0.05:.5f},{GH_LNG:.5f}")  # about 5.5 km away
    assert r.fields.lat == round(GH_LAT + 0.05, 5)  # still the link: it is the seller's own pin
    assert r.geo_precision == "district"
    assert any("disagree" in m and "haraj" in m.lower() for m in caplog.messages)


def test_two_km_boundary():
    near = post(f"https://maps.google.com/?q={GH_LAT + 0.017:.5f},{GH_LNG:.5f}")  # about 1.9 km
    far = post(f"https://maps.google.com/?q={GH_LAT + 0.019:.5f},{GH_LNG:.5f}")  # about 2.1 km
    assert haversine_m(GH_LAT, GH_LNG, near.fields.lat, near.fields.lng) < 2000
    assert near.geo_precision == "approximate" and far.geo_precision == "district"


def test_link_without_geohash_is_used_as_approximate():
    r = post("https://maps.google.com/?q=24.654,46.785", geo=None)
    assert (r.fields.lat, r.fields.lng) == (24.654, 46.785) and r.geo_precision == "approximate"


def test_geohash_only_and_no_location_unchanged():
    r = post("لا يوجد رابط")
    assert (r.fields.lat, r.fields.lng) == (GH_LAT, GH_LNG) and r.geo_precision == "approximate"
    r = post("لا يوجد رابط", geo=None)
    assert r.fields.lat is None and r.geo_precision is None


def test_invalid_link_falls_back_to_geohash():
    r = post("https://maps.google.com/?q=51.5,-0.12")
    assert (r.fields.lat, r.fields.lng) == (GH_LAT, GH_LNG) and r.geo_precision == "approximate"


def test_lower_precision_levels():
    assert [lower_precision(p) for p in ("exact", "approximate", "district", "none")] == \
           ["approximate", "district", "none", "none"]


def test_lowered_precision_survives_ingest_and_blocks_dedupe(db):
    from homefinder.models import Listing
    r = post(f"https://maps.google.com/?q={GH_LAT + 0.05:.5f},{GH_LNG:.5f}")
    lid = ingest_raw(db, r).listing_id
    db.commit()
    assert db.get(Listing, lid).geo_precision == "district"

from types import SimpleNamespace

import pytest

from homefinder.scoring import DEFAULT_WEIGHTS, FACTORS, factor_values, passes_hard_filters, score

HF = {"price_max": 2_000_000, "min_bedrooms": 4, "property_types": ["villa"], "districts": ["النرجس"],
      "max_commute": {"work": 40}, "building_age_max": 15, "street_width_min": 15}


def L(**kw):
    base = {f: None for f in ["price", "bedrooms", "bathrooms", "built_area_m2", "land_area_m2", "building_age_years",
                              "street_width_m", "facing", "street_count", "deed_type", "has_maid_room",
                              "has_driver_room", "has_yard", "has_elevator", "property_type", "district"]}
    base["commutes"] = {}
    base.update(kw)
    return SimpleNamespace(**base)


def test_factor_values_normalization():
    v = factor_values(L(price=1_400_000, commutes={"work": 10, "school": 40, "university": 25}, built_area_m2=350,
                        building_age_years=0, street_width_m=20, street_count=2, has_maid_room=True,
                        has_yard=False, bedrooms=5, bathrooms=5, deed_type="electronic"), HF, {})
    assert v["price"] == 1.0                      # <= 70% of max
    assert v["commute_work"] == 1.0 and v["commute_school"] == 0.0 and v["commute_university"] == pytest.approx(0.5)
    assert v["built_area"] == 1.0 and v["building_age"] == 1.0 and v["street_width"] == 1.0
    assert v["street_count"] == 0.7 and v["maid_room"] == 1.0 and v["yard"] == 0.0
    assert v["bedrooms"] == 1.0 and v["bathrooms"] == 1.0 and v["deed_type"] == 1.0
    assert v["commute_airport"] is None and v["facing"] is None  # facing: no preferred facings configured


def test_price_linear_between_70_and_100_percent():
    assert factor_values(L(price=1_700_000), HF, {})["price"] == pytest.approx(0.5)
    assert factor_values(L(price=2_100_000), HF, {})["price"] == 0.0
    assert factor_values(L(price=1_000_000), {}, {})["price"] is None  # no budget configured


def test_facing_with_preference():
    assert factor_values(L(facing="north"), HF, {"preferred_facings": ["north", "east"]})["facing"] == 1.0
    assert factor_values(L(facing="west"), HF, {"preferred_facings": ["north"]})["facing"] == 0.0


def test_score_explains():
    r = score(L(price=1_400_000, commutes={"work": 10}, building_age_years=30), HF, {}, {})
    assert 0 <= r.total <= 100
    by = {c["factor"]: c for c in r.contributions}
    assert by["price"]["delta"] > 0 and by["building_age"]["delta"] < 0
    assert r.contributions == sorted(r.contributions, key=lambda c: -c["delta"])
    assert "street_width" in r.missing
    d = r.as_dict()
    assert set(d) == {"total", "contributions", "missing", "coverage"}


def test_score_with_mostly_missing():
    r = score(L(price=1_000_000), HF, {}, {})
    # facing is not applicable (no preferred facings), so it is not "missing data"
    assert len(r.contributions) == 1 and len(r.missing) == len([f for f in FACTORS if DEFAULT_WEIGHTS[f] > 0]) - 2
    assert 50 < r.total < 60 and r.coverage < 0.2


def test_all_zero_weights():
    r = score(L(price=1_000_000), HF, {f: 0 for f in FACTORS}, {})
    assert r.total is None and r.contributions == []


def test_weights_override_defaults():
    a = score(L(price=1_000_000, building_age_years=40), HF, {}, {}).total
    b = score(L(price=1_000_000, building_age_years=40), HF, {"building_age": 0}, {}).total
    assert b > a


def test_hard_filters_reasons():
    ok, reasons = passes_hard_filters(L(price=2_500_000, bedrooms=3, property_type="apartment", district="الملقا",
                                        commutes={"work": 55}, building_age_years=20, street_width_m=10), HF)
    assert not ok and set(reasons) == {"price_above_max", "bedrooms_below_min", "type_excluded", "district_excluded",
                                       "commute_work_too_long", "too_old", "street_too_narrow"}


def test_unknown_values_pass_filters():
    assert passes_hard_filters(L(), HF) == (True, [])


def test_district_filter_normalizes():
    for d in ["حي النرجس", "النرجس ", "النّرجس"]:
        assert passes_hard_filters(L(district=d), {"districts": ["النرجس"]})[0], d
    assert passes_hard_filters(L(district="الأندلس"), {"districts": ["حي الاندلس"]})[0]


# --- I4: coverage damping (unknown factors count as an average 0.5, never as excluded) -------------------

def _old_score(l, hf, w, t):
    """The pre-damping formula: renormalise over present factors only."""
    from homefinder.scoring import effective_weights
    w = effective_weights(w)
    vals = factor_values(l, hf, t)
    pres = {f: x for f, x in vals.items() if x is not None and w.get(f, 0) > 0}
    return round(100 * sum(w[f] * x for f, x in pres.items()) / sum(w[f] for f in pres), 1)


COMPLETE = dict(price=1_600_000, built_area_m2=360, land_area_m2=420, building_age_years=4, street_width_m=20,
                bedrooms=5, bathrooms=4, street_count=3, deed_type="electronic", has_maid_room=True,
                has_driver_room=True, has_yard=True, has_elevator=True,
                commutes={"school": 14, "work": 22, "university": 25, "airport": 30})
PRICE_ONLY_HF = {"price_max": 2_000_000}


def test_sparse_listing_no_longer_outranks_a_complete_one():
    sparse = score(L(has_yard=True, has_elevator=True), PRICE_ONLY_HF, {}, {})
    full = score(L(**COMPLETE), PRICE_ONLY_HF, {}, {})
    assert sparse.total == pytest.approx(53.1, abs=0.05)
    assert sparse.total < 60 and sparse.total < full.total
    assert sparse.coverage == pytest.approx(0.06, abs=0.005)


def test_complete_listing_score_is_unchanged_by_damping():
    r = score(L(**COMPLETE), PRICE_ONLY_HF, {}, {})
    assert r.coverage == 1.0 and r.missing == []
    assert r.total == _old_score(L(**COMPLETE), PRICE_ONLY_HF, {}, {})


@pytest.mark.parametrize("kw", [dict(has_yard=True, has_elevator=True), dict(price=1_900_000, bedrooms=3),
                                COMPLETE, dict(building_age_years=30, commutes={"work": 50})])
def test_deltas_add_up_to_total_minus_50(kw):
    r = score(L(**kw), PRICE_ONLY_HF, {}, {})
    assert sum(c["delta"] for c in r.contributions) == pytest.approx(r.total - 50, abs=0.2)


def test_not_applicable_factors_are_neither_missing_nor_in_coverage():
    r = score(L(has_yard=True), {}, {}, {})  # no price_max, no preferred facings
    assert "price" not in r.missing and "facing" not in r.missing
    w = {k: v for k, v in DEFAULT_WEIGHTS.items() if k not in ("price", "facing")}
    assert r.coverage == pytest.approx(w["yard"] / sum(w.values()), abs=0.01)
    r2 = score(L(has_yard=True), HF, {}, {"preferred_facings": ["north"]})
    assert "price" in r2.missing and "facing" in r2.missing


def test_no_present_factors_gives_no_score():
    r = score(L(), PRICE_ONLY_HF, {}, {})
    assert r.total is None and r.contributions == [] and r.coverage == 0.0 and r.missing

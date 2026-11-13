from types import SimpleNamespace as N

from homefinder.suggestions import compute


def rej(reason, i, **kw):
    base = dict(building_age_years=None, street_width_m=None, price=None, commutes={})
    base.update(kw)
    return (reason, N(**base), i)


def test_too_old_suggestion():
    rs = [rej("too_old", i, building_age_years=a) for i, a in enumerate([18, 20, 22, 25, 30], start=1)]
    [s] = compute(rs, {}, [])
    assert s["code"] == "too_old" and s["patch"] == {"hard_filters": {"building_age_max": 21}} and s["count"] == 5


def test_needs_five_and_known_values():
    rs = [rej("too_old", i, building_age_years=20) for i in range(1, 5)]
    assert compute(rs, {}, []) == []
    rs = [rej("narrow_street", i) for i in range(1, 7)]  # widths unknown
    assert compute(rs, {}, []) == []


def test_overpriced_only_if_lower():
    rs = [rej("overpriced", i, price=2_000_000) for i in range(1, 6)]
    assert compute(rs, {"price_max": 1_500_000}, []) == []
    [s] = compute(rs, {"price_max": 2_500_000}, [])
    assert s["patch"]["hard_filters"]["price_max"] == 1_800_000


def test_dismissed_suggestion_stays_hidden():
    rs = [rej("too_old", i, building_age_years=25) for i in range(1, 6)]
    dismissed = [{"code": "too_old", "at_reaction_id": 5}]
    assert compute(rs, {}, dismissed) == []
    more = rs + [rej("too_old", i, building_age_years=25) for i in range(6, 11)]
    assert [s["code"] for s in compute(more, {}, dismissed)] == ["too_old"]


def test_only_last_20_considered():
    old = [rej("too_old", i, building_age_years=25) for i in range(1, 6)]
    recent = [rej("other", i) for i in range(6, 26)]
    assert compute(old + recent, {}, []) == []


def test_narrow_street_far_and_satisfied():
    rs = [rej("narrow_street", i, street_width_m=w) for i, w in enumerate([8, 10, 12, 10, 9], start=1)]
    [s] = compute(rs, {}, [])
    assert s["patch"] == {"hard_filters": {"street_width_min": 11.0}}
    assert compute(rs, {"street_width_min": 12}, []) == []  # current filter already stricter
    far = [rej("far", i, commutes={"work": m}) for i, m in enumerate([40, 45, 50, 35, 42], start=1)]
    [f] = compute(far, {"max_commute": {"school": 20}}, [])
    assert f["patch"] == {"hard_filters": {"max_commute": {"school": 20, "work": 37}}}


def test_layout_and_other_never_suggest():
    rs = [rej("bad_layout", i) for i in range(1, 8)] + [rej("other", i) for i in range(8, 15)]
    assert compute(rs, {}, []) == []


def test_text_is_arabic_and_names_the_value():
    rs = [rej("too_old", i, building_age_years=a) for i, a in enumerate([18, 20, 22, 25, 30], start=1)]
    [s] = compute(rs, {}, [])
    assert "21" in s["text"] and "قديمة" in s["text"] and s["reason"] == "too_old"

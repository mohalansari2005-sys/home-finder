import numpy as np
import pytest

from homefinder.learner import build_dataset, explain, fit_weights, run_learn
from homefinder.models import Listing, PreferenceChange, Preferences, Reaction
from homefinder.scoring import DEFAULT_WEIGHTS, FACTORS


def synthetic(n=40, seed=0):
    """Family loves wide streets; nothing else matters."""
    rng = np.random.default_rng(seed)
    rows = []
    for _ in range(n):
        v = {f: float(rng.random()) for f in FACTORS}
        kind = "bookmark" if v["street_width"] > 0.5 else "reject"
        rows.append((v, kind, None))
    return rows


def test_build_dataset_labels_and_weights():
    rows = [({"price": 1.0}, "bookmark", None), ({"price": None}, "reject", None),
            ({"price": 0.2}, "visit_rating", 5), ({"price": 0.3}, "visit_rating", 3)]
    X, y, sw, factors = build_dataset(rows)
    assert X.shape == (3, len(FACTORS)) and list(y) == [1, 0, 1] and list(sw) == [1, 1, 3]
    assert X[1, factors.index("price")] == 0.5


def test_weight_moves_toward_signal_and_is_capped():
    X, y, sw, f = build_dataset(synthetic())
    new = fit_weights(X, y, sw, f, dict(DEFAULT_WEIGHTS), locked=[])
    old = DEFAULT_WEIGHTS["street_width"]
    assert new["street_width"] > old
    assert new["street_width"] <= old + max(0.2 * old, 0.05) + 1e-9
    for k in FACTORS:
        assert abs(new[k] - DEFAULT_WEIGHTS[k]) <= max(0.2 * DEFAULT_WEIGHTS[k], 0.05) + 1e-9


def test_locked_weights_untouched():
    X, y, sw, f = build_dataset(synthetic())
    new = fit_weights(X, y, sw, f, dict(DEFAULT_WEIGHTS), locked=["street_width", "price"])
    assert new["street_width"] == DEFAULT_WEIGHTS["street_width"] and new["price"] == DEFAULT_WEIGHTS["price"]


def test_zero_weight_can_grow():
    X, y, sw, f = build_dataset(synthetic())
    cur = dict(DEFAULT_WEIGHTS, street_width=0.0)
    assert fit_weights(X, y, sw, f, cur, locked=[])["street_width"] == pytest.approx(0.05)


def test_explain_arabic():
    old = dict(DEFAULT_WEIGHTS)
    new = dict(old, street_width=old["street_width"] + 0.1, yard=old["yard"] - 0.06)
    txt = explain(old, new)
    assert "عرض الشارع" in txt and "حوش" in txt


def test_learner_needs_both_classes(db):
    for _ in range(12):
        l = Listing(price=1_000_000); db.add(l); db.flush(); db.add(Reaction(listing_id=l.id, kind="bookmark"))
    db.commit()
    assert run_learn(db) == {"skipped": "need both classes"}


def test_run_learn_end_to_end(db):
    rng = np.random.default_rng(1)
    for i in range(30):
        w = float(rng.uniform(8, 30))
        l = Listing(price=1_000_000, street_width_m=w); db.add(l); db.flush()
        db.add(Reaction(listing_id=l.id, kind="bookmark" if w > 18 else "reject"))
    db.commit()
    out = run_learn(db); db.commit()
    assert "street_width" in out["updated"]
    p = db.get(Preferences, 1)
    assert p.weights["street_width"] > DEFAULT_WEIGHTS["street_width"]
    assert p.learned_through_reaction_id == db.query(Reaction).order_by(Reaction.id.desc()).first().id
    assert db.query(PreferenceChange).filter_by(source="learner").count() == 1


def test_unreject_removes_the_label(db):
    rng = np.random.default_rng(2)
    for i in range(30):
        w = float(rng.uniform(8, 30))
        l = Listing(price=1_000_000, street_width_m=w); db.add(l); db.flush()
        db.add(Reaction(listing_id=l.id, kind="bookmark" if w > 18 else "reject"))
    # a listing that was rejected and then un-rejected must not count as a reject
    odd = Listing(price=1_000_000, street_width_m=30.0); db.add(odd); db.flush()
    db.add(Reaction(listing_id=odd.id, kind="reject")); db.flush()
    db.add(Reaction(listing_id=odd.id, kind="unreject")); db.commit()
    from homefinder.learner import _dataset
    _, y, _, _, _ = _dataset(db)
    assert len(y) == 30


def test_learn_job_is_registered(db):
    from homefinder.worker.handlers import HANDLERS
    assert "learn" in HANDLERS

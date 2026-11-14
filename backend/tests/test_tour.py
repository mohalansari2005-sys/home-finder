import random

from homefinder.integrations.tour import _km, farthest_first

HOME = (24.70, 46.60)


def test_small_trips():
    assert farthest_first(HOME, []) == []
    assert farthest_first(HOME, [(24.70, 46.65)]) == [0]
    assert farthest_first(HOME, [(24.70, 46.62), (24.70, 46.70)]) == [1, 0]


def test_starts_farthest_and_ends_nearest_home():
    # 30, 25 and 15 "minutes" out along a line, given out of order
    stops = [(24.70, 46.65), (24.70, 46.75), (24.70, 46.70)]
    assert farthest_first(HOME, stops) == [1, 2, 0]


def test_each_next_stop_is_the_nearest_to_the_current_one():
    far = (24.70, 46.80)
    near_far = (24.72, 46.79)  # beside the farthest stop, and farther from home than `mid`
    mid = (24.70, 46.72)
    nearest = (24.70, 46.62)
    assert farthest_first(HOME, [mid, nearest, near_far, far]) == [3, 2, 0, 1]


def test_order_is_a_permutation_that_ends_nearest_home():
    rnd = random.Random(3)
    for n in range(2, 16):  # 15 is the API's stop limit
        stops = [(24.6 + rnd.random() * 0.3, 46.5 + rnd.random() * 0.4) for _ in range(n)]
        order = farthest_first(HOME, stops)
        assert sorted(order) == list(range(n))
        dist = [_km(HOME, p) for p in stops]
        assert order[0] == max(range(n), key=dist.__getitem__)
        assert order[-1] == min(range(n), key=dist.__getitem__)

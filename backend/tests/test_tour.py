import random
import time
from itertools import permutations

from homefinder.integrations.tour import EXACT_MAX, _km, _length, best_round_trip


def _brute(origin, stops):
    pts = [origin, *stops]
    d = [[_km(a, b) for b in pts] for a in pts]
    return min(_length(list(p), d) for p in permutations(range(len(stops)))), d


def test_small_trips_keep_their_order():
    assert best_round_trip((0, 0), []) == []
    assert best_round_trip((0, 0), [(1, 1)]) == [0]
    assert best_round_trip((0, 0), [(1, 1), (2, 2)]) == [0, 1]


def test_exact_order_matches_brute_force():
    rnd = random.Random(7)
    for n in range(3, 8):
        origin = (24.7, 46.6)
        stops = [(24.6 + rnd.random() * 0.3, 46.5 + rnd.random() * 0.4) for _ in range(n)]
        order = best_round_trip(origin, stops)
        assert sorted(order) == list(range(n))
        best, d = _brute(origin, stops)
        assert abs(_length(order, d) - best) < 1e-9


def test_large_trips_are_fast_and_valid():
    rnd = random.Random(3)
    for n in (EXACT_MAX, 15):  # 15 is the API's stop limit
        stops = [(24.6 + rnd.random() * 0.3, 46.5 + rnd.random() * 0.4) for _ in range(n)]
        t = time.perf_counter()
        order = best_round_trip((24.7, 46.6), stops)
        assert time.perf_counter() - t < 2
        assert sorted(order) == list(range(n))

"""Visit order for a round trip origin -> stops -> origin, by straight-line distance.

TomTom's Orbis Routing API has no waypoint-order option (the TomTom Maps `computeBestOrder` was itself a
distance heuristic), so the order is chosen here and the drive times then come from one traffic-aware route.
"""
from itertools import combinations
from math import asin, cos, radians, sin, sqrt

EXACT_MAX = 10  # Held-Karp is exact; at 10 stops it is ~100k steps, at 15 (the trip limit) far too slow


def _km(a: tuple[float, float], b: tuple[float, float]) -> float:
    la1, lo1, la2, lo2 = map(radians, (a[0], a[1], b[0], b[1]))
    h = sin((la2 - la1) / 2) ** 2 + cos(la1) * cos(la2) * sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371 * asin(sqrt(h))


def _length(order: list[int], d: list[list[float]]) -> float:
    path = [0, *[i + 1 for i in order], 0]
    return sum(d[a][b] for a, b in zip(path, path[1:]))


def _exact(n: int, d: list[list[float]]) -> list[int]:
    """Held-Karp over stops 1..n with 0 the origin. best[(set, last)] = (length, previous)."""
    best: dict[tuple[int, int], tuple[float, int]] = {(1 << k, k): (d[0][k + 1], -1) for k in range(n)}
    for size in range(2, n + 1):
        for subset in combinations(range(n), size):
            bits = sum(1 << k for k in subset)
            for last in subset:
                prev_bits = bits & ~(1 << last)
                best[(bits, last)] = min((best[(prev_bits, p)][0] + d[p + 1][last + 1], p)
                                          for p in subset if p != last)
    full = (1 << n) - 1
    last = min(range(n), key=lambda k: best[(full, k)][0] + d[k + 1][0])
    order, bits = [], full
    while last != -1:
        order.append(last)
        bits, last = bits & ~(1 << last), best[(bits, last)][1]
    return order[::-1]


def _greedy_2opt(n: int, d: list[list[float]]) -> list[int]:
    order, left, here = [], set(range(n)), 0
    while left:
        nxt = min(left, key=lambda k: d[here][k + 1])
        order.append(nxt)
        left.remove(nxt)
        here = nxt + 1
    improved = True
    while improved:
        improved = False
        for i in range(n - 1):
            for j in range(i + 1, n):
                cand = order[:i] + order[i:j + 1][::-1] + order[j + 1:]
                if _length(cand, d) < _length(order, d) - 1e-9:
                    order, improved = cand, True
    return order


def best_round_trip(origin: tuple[float, float], stops: list[tuple[float, float]]) -> list[int]:
    """Visit order (indexes into stops) that makes origin -> stops -> origin shortest."""
    n = len(stops)
    if n <= 2:
        return list(range(n))  # a round trip over 0-2 stops is the same length either way
    pts = [origin, *stops]
    d = [[_km(a, b) for b in pts] for a in pts]
    order = _exact(n, d) if n <= EXACT_MAX else _greedy_2opt(n, d)
    # a loop is as long either way round: start with the nearer end (the first visit comes sooner)
    return order[::-1] if d[0][order[-1] + 1] < d[0][order[0] + 1] else order

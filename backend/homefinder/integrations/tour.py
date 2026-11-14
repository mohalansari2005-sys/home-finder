"""Visit order for a trip origin -> stops -> origin, by straight-line distance.

The family drives out to the farthest home first and works its way back: each next stop is the one nearest to
the current stop, and the stop nearest the origin is always kept for last, so the day ends close to home.
TomTom's Orbis Routing API has no waypoint-order option, so the order is chosen here and the drive times then
come from one traffic-aware route.
"""
from math import asin, cos, radians, sin, sqrt


def _km(a: tuple[float, float], b: tuple[float, float]) -> float:
    la1, lo1, la2, lo2 = map(radians, (a[0], a[1], b[0], b[1]))
    h = sin((la2 - la1) / 2) ** 2 + cos(la1) * cos(la2) * sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371 * asin(sqrt(h))


def farthest_first(origin: tuple[float, float], stops: list[tuple[float, float]]) -> list[int]:
    """Visit order (indexes into stops): the stop farthest from origin, then always the nearest remaining stop,
    ending with the stop nearest the origin."""
    if len(stops) <= 1:
        return list(range(len(stops)))
    from_origin = [_km(origin, p) for p in stops]
    first = max(range(len(stops)), key=lambda k: from_origin[k])
    last = min(range(len(stops)), key=lambda k: from_origin[k])
    order, left = [first], set(range(len(stops))) - {first, last}
    while left:
        here = stops[order[-1]]
        nxt = min(left, key=lambda k: _km(here, stops[k]))
        order.append(nxt)
        left.remove(nxt)
    return [*order, last]

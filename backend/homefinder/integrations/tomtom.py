"""TomTom geocoding and traffic-aware car routing on TomTom Orbis Maps (free tier, key in a header).

- Drive times: Routing API v3 Calculate Route, one request per destination, with a departure time. Orbis has
  no Matrix Routing API, and the TomTom Maps matrix bills every cell as a request against a free allowance
  an eighth of Routing's, so one route per destination is both the available and the cheaper option.
- Trip routes: the visit order is chosen locally (`tour.farthest_first`, Orbis routing has no waypoint
  optimization) and one Calculate Route over the ordered stops gives traffic-aware times for every leg.
- Geocoding: Geocoding API v2, restricted to district-level areas, so a miss never falls back to a city centroid.
"""
from collections.abc import Callable
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from homefinder import usage
from homefinder.config import get_settings
from homefinder.integrations.tour import farthest_first

BASE_URL = "https://api.tomtom.com/maps/orbis"  # TomTom Orbis Maps; every endpoint below hangs off this
ROUTE_URL = BASE_URL + "/routing/routes/calculate"
GEOCODE_URL = BASE_URL + "/places/geocode"
ROUTE_API_VERSION, GEOCODE_API_VERSION = "3", "2"
ENRICH_RESERVE = 0.2  # bulk enrichment/recompute leave 20% of the request caps for trip planning
RIYADH = ZoneInfo("Asia/Riyadh")
NO_ROUTE = ("NO_ROUTE_FOUND", "MAP_MATCHING_FAILURE")  # a point off the road network: no route, not an outage
DISTRICT_AREAS = "municipalitySubdivision,municipalitySecondarySubdivision,neighborhood"


def _point(p: tuple[float, float]) -> dict:
    return {"type": "Point", "coordinates": [p[1], p[0]]}  # GeoJSON order: longitude, latitude


def _departure(departure: datetime) -> str:
    """RFC 3339 with Riyadh's offset (TomTom assumes the origin's time zone when none is given)."""
    return departure.astimezone(RIYADH).isoformat(timespec="seconds")


def _error_code(r: httpx.Response) -> str:
    try:
        return str(((r.json() or {}).get("detailedError") or {}).get("code") or "")
    except ValueError:
        return ""


def _check(r: httpx.Response, what: str) -> None:
    """raise_for_status() would put the request URL into the error text that the worker logs; keep errors bare."""
    if r.is_error:
        code = _error_code(r)
        raise RuntimeError(f"tomtom {what}: HTTP {r.status_code}{' ' + code if code else ''}") from None


def _minutes(seconds) -> int | None:
    return round(seconds / 60) if isinstance(seconds, (int, float)) else None


class TomTomClient:
    def __init__(self, api_key: str, http: httpx.Client, use: Callable[[int], None] | None = None,
                 reserve: float = 0.0):
        self._key, self._http = api_key, http
        self._use = use or (lambda n: usage.use_requests("tomtom", n, reserve=reserve))

    def geocode(self, address: str) -> tuple[float, float] | None:
        """(lat, lng) of a district, or None. Only district-level areas count: a city or region centre would put
        the listing kilometres off and give it made-up commute times."""
        self._use(1)
        r = self._http.get(GEOCODE_URL, timeout=20, params={
            "query": address, "countryCodesIso2": "SA", "maxResults": 1, "types": "area", "areaTypes": DISTRICT_AREAS,
        }, headers={"TomTom-Api-Key": self._key, "TomTom-Api-Version": GEOCODE_API_VERSION, "Accept-Language": "ar",
                    "Attributes": "results.type, results.areaType, results.position"})
        _check(r, "geocode")
        results = r.json().get("results") or []
        coords = ((results[0].get("position") or {}).get("coordinates") or []) if results else []
        return (coords[1], coords[0]) if len(coords) == 2 else None

    def _route(self, points: list[tuple[float, float]], departure: datetime, traffic: str) -> dict | None:
        """One Calculate Route through `points` in order; None when TomTom finds no route."""
        body = {"routePlanningLocations": {"origin": _point(points[0]), "destination": _point(points[-1])},
                "departureDateTime": _departure(departure), "traffic": traffic, "routeType": "fast", "travelMode": "car"}
        if len(points) > 2:
            body["routePlanningLocations"]["waypoints"] = {"type": "MultiPoint",
                                                           "coordinates": [[p[1], p[0]] for p in points[1:-1]]}
        r = self._http.post(ROUTE_URL, json=body, timeout=30, headers={
            "TomTom-Api-Key": self._key, "TomTom-Api-Version": ROUTE_API_VERSION,
            "Attributes": "routes.summary, routes.legs.summary"})
        if _error_code(r) in NO_ROUTE:
            return None
        _check(r, "route")
        routes = r.json().get("routes") or []
        return routes[0] if routes else None

    def drive_minutes(self, origin: tuple[float, float], destinations: list[tuple[float, float]],
                      departure: datetime) -> list[int | None]:
        """Minutes from origin to each destination (None where TomTom found no route), one request each.
        Historical traffic for that weekday and time: these are typical commutes, cached for weeks, so a jam
        happening right now must not end up in them."""
        self._use(len(destinations))  # all or nothing: a cap never leaves a half-filled result
        out: list[int | None] = []
        for d in destinations:
            route = self._route([origin, d], departure, "historical")
            out.append(_minutes((route or {}).get("summary", {}).get("travelDurationInSeconds")))
        return out

    def optimize_route(self, origin: tuple[float, float], stops: list[tuple[float, float]],
                       departure: datetime) -> dict | None:
        """Round trip origin -> stops -> origin. {"order": visit order as indexes into stops, "leg_minutes":
        origin->1st, 1st->2nd, ..., last->origin (None for a leg TomTom gave no time for)}. None = no route.
        Live traffic: TomTom adds jams expected in the trip's time window on top of the historical times."""
        self._use(1)
        order = farthest_first(origin, stops)
        route = self._route([origin, *[stops[i] for i in order], origin], departure, "live")
        if route is None:
            return None
        legs = [_minutes((leg.get("summary") or {}).get("travelDurationInSeconds")) for leg in route.get("legs") or []]
        legs += [None] * (len(stops) + 1 - len(legs))
        return {"order": order, "leg_minutes": legs[:len(stops) + 1]}


def make_tomtom(http: httpx.Client, reserve: float = 0.0) -> TomTomClient | None:
    """`reserve`: share of the request caps this client may not touch (bulk enrichment uses ENRICH_RESERVE)."""
    key = get_settings().tomtom_api_key
    return TomTomClient(key, http, reserve=reserve) if key else None

import json
from datetime import datetime, UTC

import httpx
import pytest

from homefinder.integrations.tomtom import TomTomClient
from homefinder.usage import BudgetExceeded

used: list[int] = []
DEP = datetime(2026, 11, 15, 4, 30, tzinfo=UTC)  # Sunday 07:30 in Riyadh


def client(handler):
    used.clear()
    return TomTomClient("KEY", httpx.Client(transport=httpx.MockTransport(handler)), use=used.append)


def _latlng(p: dict) -> tuple[float, float]:
    assert p["type"] == "Point"
    return p["coordinates"][1], p["coordinates"][0]


def _route_request(req: httpx.Request) -> dict:
    assert req.method == "POST" and str(req.url).startswith("https://api.tomtom.com/maps/orbis/routing/routes/calculate")
    assert req.headers["TomTom-Api-Key"] == "KEY" and req.headers["TomTom-Api-Version"] == "3"
    assert "routes.summary" in req.headers["Attributes"] and "KEY" not in str(req.url)
    body = json.loads(req.content)
    assert body["travelMode"] == "car" and body["routeType"] == "fast"
    return body


def _route(*leg_seconds):
    legs = [{"summary": {"travelDurationInSeconds": s}} if s is not None else {} for s in leg_seconds]
    return {"routes": [{"summary": {"travelDurationInSeconds": sum(s or 0 for s in leg_seconds)}, "legs": legs}]}


def test_geocode_asks_for_district_areas_only():
    def h(req):
        p = req.url.params
        assert str(req.url).startswith("https://api.tomtom.com/maps/orbis/places/geocode?")
        assert req.headers["TomTom-Api-Key"] == "KEY" and req.headers["TomTom-Api-Version"] == "2"
        assert req.headers["Accept-Language"] == "ar" and "results.position" in req.headers["Attributes"]
        assert p["countryCodesIso2"] == "SA" and p["maxResults"] == "1" and p["types"] == "area"
        assert set(p["areaTypes"].split(",")) == {"municipalitySubdivision", "municipalitySecondarySubdivision", "neighborhood"}
        if "النرجس" in p["query"]:
            return httpx.Response(200, json={"results": [{"type": "area", "areaType": "municipalitySubdivision",
                                                          "position": {"type": "Point", "coordinates": [46.66, 24.83]}}]})
        return httpx.Response(200, json={"results": []})
    g = client(h)
    assert g.geocode("حي النرجس، الرياض، السعودية") == (24.83, 46.66)
    assert g.geocode("لا شيء") is None
    assert used == [1, 1]


def test_drive_minutes_one_historical_route_per_destination():
    seen = []

    def h(req):
        body = _route_request(req)
        assert body["traffic"] == "historical" and body["departureDateTime"] == "2026-11-15T07:30:00+03:00"
        locs = body["routePlanningLocations"]
        assert "waypoints" not in locs
        seen.append((_latlng(locs["origin"]), _latlng(locs["destination"])))
        return httpx.Response(200, json=_route(610 if _latlng(locs["destination"]) == (24.7, 46.7) else 1500))
    g = client(h)
    assert g.drive_minutes((24.8, 46.6), [(24.7, 46.7), (24.9, 46.8)], DEP) == [10, 25] and used == [2]
    assert seen == [((24.8, 46.6), (24.7, 46.7)), ((24.8, 46.6), (24.9, 46.8))]


def test_drive_minutes_no_route_and_missing_duration_are_none():
    def h(req):
        dest = _latlng(json.loads(req.content)["routePlanningLocations"]["destination"])
        if dest == (1, 1):
            return httpx.Response(400, json={"detailedError": {"code": "NO_ROUTE_FOUND", "message": "no route"}})
        if dest == (2, 2):  # the error can also come in a 200 body
            return httpx.Response(200, json={"detailedError": {"code": "MAP_MATCHING_FAILURE", "message": "off road"}})
        if dest == (3, 3):
            return httpx.Response(200, json={"routes": [{"summary": {}}]})
        if dest == (4, 4):
            return httpx.Response(200, json={"routes": []})
        return httpx.Response(200, json=_route(120))
    g = client(h)
    assert g.drive_minutes((0, 0), [(1, 1), (2, 2), (3, 3), (4, 4), (5, 5)], DEP) == [None, None, None, None, 2]


def test_drive_minutes_outage_raises():
    g = client(lambda req: httpx.Response(429, json={"detailedError": {"code": "TOO_MANY_REQUESTS"}}))
    with pytest.raises(RuntimeError, match="429"):
        g.drive_minutes((0, 0), [(1, 1)], DEP)


def test_requests_refused_by_the_cap_are_never_sent():
    sent = []

    def refuse(n):
        raise BudgetExceeded("cap")
    http = httpx.Client(transport=httpx.MockTransport(lambda r: sent.append(r) or httpx.Response(200, json={})))
    g = TomTomClient("KEY", http, use=refuse)
    for call in (lambda: g.drive_minutes((0, 0), [(1, 1), (2, 2)], DEP), lambda: g.geocode("x"),
                 lambda: g.optimize_route((0, 0), [(1, 1)], DEP)):
        with pytest.raises(BudgetExceeded):
            call()
    assert sent == []


def test_optimize_route_orders_stops_then_routes_them_with_live_traffic():
    origin = (24.70, 46.60)
    # along a line east of the origin, given out of order: the round trip visits them nearest first
    stops = [(24.70, 46.70), (24.70, 46.62), (24.70, 46.66)]

    def h(req):
        body = _route_request(req)
        assert body["traffic"] == "live" and body["departureDateTime"] == "2026-11-21T16:00:00+03:00"
        locs = body["routePlanningLocations"]
        assert _latlng(locs["origin"]) == _latlng(locs["destination"]) == origin
        assert [(c[1], c[0]) for c in locs["waypoints"]["coordinates"]] == [stops[1], stops[2], stops[0]]
        assert locs["waypoints"]["type"] == "MultiPoint"
        return httpx.Response(200, json=_route(600, 300, 420, 900))
    g = client(h)
    r = g.optimize_route(origin, stops, datetime(2026, 11, 21, 13, tzinfo=UTC))
    assert r == {"order": [1, 2, 0], "leg_minutes": [10, 5, 7, 15]} and used == [1]


def test_optimize_single_stop():
    def h(req):
        assert len(json.loads(req.content)["routePlanningLocations"]["waypoints"]["coordinates"]) == 1
        return httpx.Response(200, json=_route(60, 60))
    assert client(h).optimize_route((0, 0), [(1, 1)], DEP) == {"order": [0], "leg_minutes": [1, 1]}


def test_optimize_no_route_returns_none_and_missing_leg_is_none():
    assert client(lambda req: httpx.Response(200, json={})).optimize_route((0, 0), [(1, 1)], DEP) is None
    no_route = httpx.Response(400, json={"detailedError": {"code": "NO_ROUTE_FOUND"}})
    assert client(lambda req: no_route).optimize_route((0, 0), [(1, 1)], DEP) is None
    g = client(lambda req: httpx.Response(200, json=_route(120, None)))
    assert g.optimize_route((0, 0), [(1, 1)], DEP) == {"order": [0], "leg_minutes": [2, None]}


def test_enrichment_client_stops_at_80_percent_and_leaves_the_reserve_for_trips(db, settings_env):
    """Bulk enrichment must not be able to use the last 20% of the daily cap that trip routing needs."""
    from homefinder import usage
    from homefinder.integrations.tomtom import make_tomtom
    settings_env(TOMTOM_DAILY_REQUEST_CAP="10", TOMTOM_API_KEY="k")
    usage.use_requests("tomtom", 8)
    http = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"results": []})))
    with pytest.raises(usage.BudgetExceeded):
        make_tomtom(http, reserve=0.2).geocode("x")
    assert make_tomtom(http).geocode("x") is None  # the trip-planning client may still use it


def test_no_key_no_client(settings_env):
    from homefinder.integrations.tomtom import make_tomtom
    settings_env(TOMTOM_API_KEY="")
    assert make_tomtom(httpx.Client()) is None


def test_http_errors_never_carry_the_api_key():
    """The key travels in a header; errors (which workers log) carry only the status and TomTom's error code."""
    http = httpx.Client(transport=httpx.MockTransport(
        lambda r: httpx.Response(403, json={"detailedError": {"code": "FORBIDDEN", "message": "bad key SECRET-KEY-123"}})))
    g = TomTomClient("SECRET-KEY-123", http, use=lambda n: None)
    for call in (lambda: g.geocode("الرياض"), lambda: g.drive_minutes((0, 0), [(1, 1)], DEP),
                 lambda: g.optimize_route((0, 0), [(1, 1), (2, 2)], DEP)):
        with pytest.raises(Exception) as e:
            call()
        assert "SECRET-KEY-123" not in str(e.value) and "403" in str(e.value)

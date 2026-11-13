import json
from datetime import datetime, UTC

import httpx
import pytest

from homefinder.integrations.google import GoogleClient

spent = []


def client(handler):
    spent.clear()
    return GoogleClient("KEY", httpx.Client(transport=httpx.MockTransport(handler)), spend=spent.append)


def test_geocode_ok_and_zero_results():
    def h(req):
        assert req.url.params["key"] == "KEY" and req.url.params["language"] == "ar"
        if "النرجس" in req.url.params["address"]:
            return httpx.Response(200, json={"status": "OK", "results": [{"geometry": {"location": {"lat": 24.83, "lng": 46.66}}}]})
        return httpx.Response(200, json={"status": "ZERO_RESULTS", "results": []})
    g = client(h)
    assert g.geocode("حي النرجس، الرياض") == (24.83, 46.66)
    assert g.geocode("لا شيء") is None
    assert spent == [0.005, 0.005]


def test_drive_minutes_matrix():
    def h(req):
        body = json.loads(req.content)
        assert req.headers["X-Goog-Api-Key"] == "KEY"
        assert body["routingPreference"] == "TRAFFIC_AWARE" and body["departureTime"].startswith("2026-11-15T04:30")
        assert len(body["destinations"]) == 2
        return httpx.Response(200, json=[
            {"originIndex": 0, "destinationIndex": 1, "duration": "1500s", "condition": "ROUTE_EXISTS"},
            {"originIndex": 0, "destinationIndex": 0, "duration": "610s", "condition": "ROUTE_EXISTS"},
        ])
    g = client(h)
    mins = g.drive_minutes((24.8, 46.6), [(24.7, 46.7), (24.9, 46.8)], datetime(2026, 11, 15, 4, 30, tzinfo=UTC))
    assert mins == [10, 25] and spent == [0.02]


def test_drive_minutes_no_route():
    g = client(lambda req: httpx.Response(200, json=[{"originIndex": 0, "destinationIndex": 0, "condition": "ROUTE_NOT_FOUND"}]))
    assert g.drive_minutes((1, 1), [(2, 2)], datetime(2026, 11, 15, tzinfo=UTC)) == [None]


def test_optimize_route():
    def h(req):
        body = json.loads(req.content)
        assert body["optimizeWaypointOrder"] is True and len(body["intermediates"]) == 3
        assert body["origin"] == body["destination"]
        assert body["routingPreference"] == "TRAFFIC_AWARE" and body["departureTime"] == "2026-11-21T13:00:00Z"
        assert req.headers["X-Goog-FieldMask"] == "routes.optimizedIntermediateWaypointIndex,routes.legs.duration"
        return httpx.Response(200, json={"routes": [{"optimizedIntermediateWaypointIndex": [2, 0, 1],
                                                     "legs": [{"duration": "600s"}, {"duration": "300s"}, {"duration": "420s"}, {"duration": "900s"}]}]})
    g = client(h)
    r = g.optimize_route((24.7, 46.6), [(1, 1), (2, 2), (3, 3)], datetime(2026, 11, 21, 13, tzinfo=UTC))
    assert r == {"order": [2, 0, 1], "leg_minutes": [10, 5, 7, 15]} and spent == [0.015]


def test_optimize_single_stop_no_optimization_flag():
    def h(req):
        assert "optimizeWaypointOrder" not in json.loads(req.content)
        return httpx.Response(200, json={"routes": [{"legs": [{"duration": "60s"}, {"duration": "60s"}]}]})
    assert client(h).optimize_route((0, 0), [(1, 1)], datetime(2026, 11, 21, tzinfo=UTC)) == {"order": [0], "leg_minutes": [1, 1]}


def test_optimize_no_routes_returns_none_and_missing_leg_is_none():
    g = client(lambda req: httpx.Response(200, json={}))
    assert g.optimize_route((0, 0), [(1, 1)], datetime(2026, 11, 21, tzinfo=UTC)) is None
    g = client(lambda req: httpx.Response(200, json={"routes": [{"legs": [{"duration": "120s"}, {}]}]}))
    assert g.optimize_route((0, 0), [(1, 1)], datetime(2026, 11, 21, tzinfo=UTC)) == {"order": [0], "leg_minutes": [2, None]}


def test_enrichment_client_stops_at_80_percent_and_leaves_the_reserve_for_trips(db, settings_env):
    """I11: bulk enrichment must not be able to use the last 20% of the monthly cap that trip routing needs."""
    settings_env(GOOGLE_MONTHLY_CAP_USD="1.0")
    from homefinder import usage
    from homefinder.integrations.google import make_google
    usage.spend("google", 0.8)
    http = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"status": "ZERO_RESULTS"})))
    settings_env(GOOGLE_MONTHLY_CAP_USD="1.0", GOOGLE_API_KEY="k")
    with pytest.raises(usage.BudgetExceeded):
        make_google(http, reserve=0.2).geocode("x")
    assert make_google(http).geocode("x") is None  # the trip-planning client may still spend

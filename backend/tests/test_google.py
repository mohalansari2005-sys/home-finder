import json
from datetime import datetime, UTC

import httpx

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

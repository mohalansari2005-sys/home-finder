from collections.abc import Callable
from datetime import datetime

import httpx

from homefinder import usage
from homefinder.config import get_settings

GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
MATRIX_URL = "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix"
ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
COST = {"geocode": 0.005, "matrix_element": 0.01, "route_optimized": 0.015}


def _wp(p: tuple[float, float]) -> dict:
    return {"waypoint": {"location": {"latLng": {"latitude": p[0], "longitude": p[1]}}}}


class GoogleClient:
    def __init__(self, api_key: str, http: httpx.Client, spend: Callable[[float], None] | None = None):
        self._key, self._http = api_key, http
        self._spend = spend or (lambda c: usage.spend("google", c))

    def geocode(self, address: str) -> tuple[float, float] | None:
        self._spend(COST["geocode"])
        r = self._http.get(GEOCODE_URL, params={"address": address, "key": self._key, "language": "ar", "region": "sa"}, timeout=20)
        r.raise_for_status()
        data = r.json()
        if data.get("status") != "OK" or not data.get("results"):
            return None
        loc = data["results"][0]["geometry"]["location"]
        return loc["lat"], loc["lng"]

    def drive_minutes(self, origin: tuple[float, float], destinations: list[tuple[float, float]],
                      departure: datetime) -> list[int | None]:
        self._spend(COST["matrix_element"] * len(destinations))
        body = {"origins": [_wp(origin)], "destinations": [_wp(d) for d in destinations], "travelMode": "DRIVE",
                "routingPreference": "TRAFFIC_AWARE", "departureTime": departure.isoformat().replace("+00:00", "Z")}
        r = self._http.post(MATRIX_URL, json=body, timeout=30, headers={
            "X-Goog-Api-Key": self._key, "X-Goog-FieldMask": "originIndex,destinationIndex,duration,condition"})
        r.raise_for_status()
        out: list[int | None] = [None] * len(destinations)
        for el in r.json():
            if el.get("condition") == "ROUTE_EXISTS" and el.get("duration"):
                out[el["destinationIndex"]] = round(int(el["duration"].rstrip("s")) / 60)
        return out

    def optimize_route(self, origin: tuple[float, float], stops: list[tuple[float, float]],
                       departure: datetime) -> dict | None:
        """Round trip origin -> stops -> origin. {"order": visit order as indexes into stops, "leg_minutes":
        origin->1st, 1st->2nd, ..., last->origin (None for a leg Google gave no duration for)}. None = no route."""
        self._spend(COST["route_optimized"])
        body = {"origin": _wp(origin)["waypoint"], "destination": _wp(origin)["waypoint"],
                "intermediates": [_wp(p)["waypoint"] for p in stops], "travelMode": "DRIVE",
                "routingPreference": "TRAFFIC_AWARE", "departureTime": departure.isoformat().replace("+00:00", "Z")}
        if len(stops) >= 2:
            body["optimizeWaypointOrder"] = True
        r = self._http.post(ROUTES_URL, json=body, timeout=30, headers={
            "X-Goog-Api-Key": self._key,
            "X-Goog-FieldMask": "routes.optimizedIntermediateWaypointIndex,routes.legs.duration"})
        r.raise_for_status()
        routes = r.json().get("routes") or []
        if not routes:
            return None
        route = routes[0]
        order = route.get("optimizedIntermediateWaypointIndex") or list(range(len(stops)))
        legs = [round(int(leg["duration"].rstrip("s")) / 60) if leg.get("duration") else None
                for leg in route.get("legs") or []]
        legs += [None] * (len(stops) + 1 - len(legs))
        return {"order": list(order), "leg_minutes": legs}


def make_google(http: httpx.Client) -> GoogleClient | None:
    key = get_settings().google_api_key
    return GoogleClient(key, http) if key else None

from collections.abc import Callable
from datetime import datetime

import httpx

from homefinder import usage
from homefinder.config import get_settings

GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
MATRIX_URL = "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix"
COST = {"geocode": 0.005, "matrix_element": 0.01}


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


def make_google(http: httpx.Client) -> GoogleClient | None:
    key = get_settings().google_api_key
    return GoogleClient(key, http) if key else None

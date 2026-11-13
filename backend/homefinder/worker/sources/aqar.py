import logging
from collections.abc import Iterator
from datetime import UTC, datetime

from homefinder.sanity import AGE, BUILT, LAND, PRICE, ROOMS, STREET, clean_float, clean_int, parse_number
from homefinder.schemas import CanonicalFields, HealthReport, RawListing, SearchQuery
from homefinder.textnorm import normalize_district
from homefinder.worker.sources.aqar_queries import districts_body, find_body, listing_body
from homefinder.worker.sources.aqar_transport import (CurlCffiTransport, FallbackTransport, PlaywrightTransport,
                                                       Transport)
from homefinder.worker.sources.base import Pacer, default_health

log = logging.getLogger(__name__)

SITE = "https://sa.aqar.fm"
IMAGE_BASE = "https://images.aqar.fm/webp/640x0/props/"  # verified HTTP 200 image/webp, see docs/sources/aqar.md
CATEGORY_BY_TYPE = {"villa": 3, "apartment": 6, "house": 9, "floor": 22}
TYPE_BY_CATEGORY = {v: k for k, v in CATEGORY_BY_TYPE.items()}
CITY_IDS = {"الرياض": 21}
FACING = {1: "north", 2: "east", 3: "west", 4: "south", 5: "northeast", 6: "southeast", 7: "southwest", 8: "northwest"}
MULTI_STREET = {9: 3, 10: 4}
AGE_ZERO_MEANS_NEW = False  # probe: 15/20 listings have age 0, almost none say "new" -> 0 means unknown
PAGE = 20


def _true_or_none(v) -> bool | None:
    return True if v in (1, True, "1") else None


def _image_url(x: str) -> str:
    return x if x.startswith("http") else IMAGE_BASE + x.lstrip("/")


def parse_listing(d: dict) -> RawListing:
    ptype = TYPE_BY_CATEGORY.get(d.get("category"))
    area = parse_number(d.get("area"))
    ext = d.get("extended_details") or {}
    internal = parse_number(ext.get("internal_area"))
    built, land = (area, None) if ptype in ("apartment", "floor") else (internal, area)
    loc = d.get("location") or {}
    lat, lng = parse_number(loc.get("lat")), parse_number(loc.get("lng"))
    if lat is None or lng is None or not (16 <= lat <= 33 and 34 <= lng <= 56):
        lat = lng = None
    sd = d.get("street_direction")
    age = d.get("age")
    if age == 0 and not AGE_ZERO_MEANS_NEW:
        age = None
    user = d.get("user") or {}
    created = d.get("create_time")
    fields = CanonicalFields(
        property_type=ptype, title=d.get("title"), description=d.get("content"),
        city=d.get("city"), district=d.get("district"),
        price=clean_int(d.get("price"), *PRICE),
        bedrooms=clean_int(d.get("beds"), *ROOMS), bathrooms=clean_int(d.get("wc"), *ROOMS),
        livings=clean_int(d.get("livings"), *ROOMS),
        built_area_m2=clean_float(built, *BUILT), land_area_m2=clean_float(land, *LAND),
        building_age_years=clean_int(age, *AGE), street_width_m=clean_float(d.get("street_width"), *STREET),
        facing=FACING.get(sd), street_count=MULTI_STREET.get(sd, 1 if sd in FACING else None),
        has_maid_room=_true_or_none(d.get("maid")), has_driver_room=_true_or_none(d.get("driver")),
        has_yard=_true_or_none(d.get("backyard")), has_elevator=_true_or_none(d.get("lift")),
        lat=lat, lng=lng,
    )
    precision = None
    if lat is not None:
        precision = "approximate" if d.get("blur") or d.get("location_circle_radius") else "exact"
    return RawListing(
        source="aqar", source_id=str(d["id"]), url=SITE + (d.get("path") or f"/{d['id']}"),
        fields=fields, geo_precision=precision,
        photo_urls=[_image_url(x) for x in (d.get("imgs") or []) if isinstance(x, str) and x],
        seller_phone=str(user["phone"]) if user.get("phone") else None,  # Aqar sends int 0 when hidden
        seller_name=user.get("name") or None,
        listed_at=datetime.fromtimestamp(created, UTC) if isinstance(created, (int, float)) else None,
        raw=d,
    )


def make_default_transport() -> FallbackTransport:
    return FallbackTransport([CurlCffiTransport, lambda: PlaywrightTransport(headless=True)])


class AqarAdapter:
    name = "aqar"

    def __init__(self, transport: Transport, pacer: Pacer | None = None):
        self._t = transport
        self._pacer = pacer or Pacer()
        self._district_cache: dict[tuple[int, int], dict[str, int]] = {}

    def _post(self, body: dict) -> dict:
        self._pacer.wait()
        resp = self._t.post_graphql(body)  # raises AppVersionOutdated / Blocked
        if resp.get("errors") and not resp.get("data"):
            raise RuntimeError(f"aqar graphql error: {resp['errors']}")
        return resp

    def _district_ids(self, category: int, city_id: int, names: list[str]) -> list[int]:
        key = (category, city_id)
        if key not in self._district_cache:
            data = self._post(districts_body(category, city_id))
            self._district_cache[key] = {normalize_district(d["name"]): d["district_id"]
                                         for d in data["data"]["Web"]["districts"] or []}
        table = self._district_cache[key]
        ids = []
        for n in names:
            did = table.get(normalize_district(n))
            if did is None:
                log.warning("aqar: unknown district %r", n)
            else:
                ids.append(did)
        return ids

    def search(self, q: SearchQuery) -> Iterator[RawListing]:
        city_id = CITY_IDS[q.city]
        for ptype in q.property_types:
            cat = CATEGORY_BY_TYPE[ptype]
            district_ids: list[int | None] = self._district_ids(cat, city_id, q.districts) if q.districts else [None]
            for did in district_ids:
                for page in range(q.max_pages):
                    where = {"category": {"eq": cat}, "city_id": {"eq": city_id}, "published": {"eq": 1}}
                    if did is not None:
                        where["district_id"] = {"eq": did}
                    if q.price_max:
                        where["price"] = {"lte": q.price_max}  # honoured server-side (probe)
                    rows = self._post(find_body(page * PAGE, where))["data"]["Web"]["find"]["listings"] or []
                    for d in rows:
                        r = parse_listing(d)
                        if q.price_max and r.fields.price and r.fields.price > q.price_max:
                            continue
                        yield r
                    if len(rows) < PAGE:
                        break

    def fetch(self, source_id: str) -> RawListing | None:
        """By-id lookup via Web.listing(id). None = gone: "Listing not found", or present but `published` is falsy.
        The response has no extended_details, so villa built area is None (ingest never overwrites known fields with None)."""
        resp = self._post(listing_body(int(source_id)))
        listing = ((resp.get("data") or {}).get("Web") or {}).get("listing")
        if listing is None:
            errors = resp.get("errors") or []
            if any(e.get("code") == "Listing not found" for e in errors):
                return None
            raise RuntimeError(f"aqar listing({source_id}) unexpected response: {errors}")
        if not listing.get("published"):
            return None
        return parse_listing(listing)

    def health(self, sample: list[RawListing]) -> HealthReport:
        return default_health(sample)

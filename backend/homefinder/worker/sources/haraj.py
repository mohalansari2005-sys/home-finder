import html
import logging
import re
from collections.abc import Iterator
from datetime import UTC, datetime

from homefinder.sanity import PRICE, clean_int
from homefinder.schemas import CanonicalFields, HealthReport, PropertyType, RawListing, SearchQuery
from homefinder.textnorm import normalize_ar, normalize_district
from homefinder.worker.sources.base import Pacer
from homefinder.worker.sources.haraj_text import (MAX_DISAGREEMENT_M, haversine_m, lower_precision, parse_maps_link,
                                                   parse_price_from_text)
from homefinder.worker.sources.haraj_transport import SITE, HarajTransport

log = logging.getLogger(__name__)

# Verified by query, see docs/sources/haraj.md
HARAJ_TAG_BY_TYPE: dict[PropertyType, str] = {"villa": "فلل للبيع", "apartment": "شقق للبيع", "floor": "دور للبيع",
                                              "house": "بيوت للبيع"}
TYPE_BY_TAG = {v: k for k, v in HARAJ_TAG_BY_TYPE.items()}

# canonical key -> real Haraj key. `field_map_override=True` uses the identity map (callers already use canonical keys).
_FIELD_MAP = {"id": "id", "title": "title", "bodyTEXT": "bodyTEXT", "city": "city", "tags": "tags", "price": "price",
              "imagesList": "imagesList", "geo": "geoHash", "district": "geoNeighborhood", "postDate": "postDate",
              "status": "status"}
_IDENTITY_MAP = {k: k for k in _FIELD_MAP} | {"geo": "geo", "district": "district"}

_DISTRICT_RE = re.compile(r"حي\s+([؀-ۿ]+(?:\s[؀-ۿ]+)?)")
_RENT_RE = re.compile(r"ايجار")  # after normalize_ar: إيجار / للإيجار / الايجار
_WANTED_RE = re.compile(r"^\s*(مطلوب|ابحث|ابي|ابغي|ابغى|نبي|ادور)(\s|$)")
_GEOHASH = "0123456789bcdefghjkmnpqrstuvwxyz"
SAUDI = (16, 33, 34, 56)  # lat min/max, lng min/max


def decode_geohash(gh) -> tuple[float, float] | None:
    if not isinstance(gh, str) or not gh or any(c not in _GEOHASH for c in gh):
        return None
    lat, lng, even = [-90.0, 90.0], [-180.0, 180.0], True
    for c in gh:
        v = _GEOHASH.index(c)
        for b in range(4, -1, -1):
            rng = lng if even else lat
            mid = (rng[0] + rng[1]) / 2
            rng[0 if (v >> b) & 1 else 1] = mid
            even = not even
    la, ln = sum(lat) / 2, sum(lng) / 2
    return (la, ln) if SAUDI[0] <= la <= SAUDI[1] and SAUDI[2] <= ln <= SAUDI[3] else None


def extract_posts(resp: dict) -> list[dict]:
    return ((((resp or {}).get("data") or {}).get("posts") or {}).get("items")) or []


def wrap_posts_for_test(posts: list[dict]) -> dict:
    return {"data": {"posts": {"items": posts, "pageInfo": {"hasNextPage": bool(posts)}}}}


def _price(v) -> int | None:
    if isinstance(v, dict):
        return clean_int(v.get("inputPrice"), *PRICE) or clean_int(v.get("formattedPrice"), *PRICE)
    return clean_int(v, *PRICE)


def _district(api_value, title: str, body: str) -> str | None:
    if isinstance(api_value, str) and api_value.strip():
        return api_value.strip()
    for text in (title, body):
        m = _DISTRICT_RE.search(text)
        if m:
            return normalize_ar(m.group(1))
    return None


def _location(pid, geohash_pt, link_pt):
    """(point, precision). The body's Maps link is the seller's own pin, so it beats geoHash. When the two are more
    than 2 km apart one of them is wrong and we can't tell which: keep the link but trust it one level less."""
    precision = "approximate"
    if link_pt and geohash_pt:
        gap = haversine_m(*geohash_pt, *link_pt)
        if gap > MAX_DISAGREEMENT_M:
            precision = lower_precision(precision)
            log.warning("haraj %s: geoHash and body maps link disagree by %.1f km; using the link at %s precision",
                        pid, gap / 1000, precision)
    pt = link_pt or geohash_pt
    return (pt, precision) if pt else (None, None)


def parse_post(d: dict, field_map_override: bool = False) -> RawListing | None:
    """None for rent, wanted, removed or non-real-estate posts. Unknown values stay None."""
    m = _IDENTITY_MAP if field_map_override else _FIELD_MAP
    pid = d.get(m["id"])
    if pid is None or d.get(m["status"]) is False:
        return None
    title = d.get(m["title"]) or ""
    tags = [t for t in (d.get(m["tags"]) or []) if isinstance(t, str)]
    ptype = next((TYPE_BY_TAG[t] for t in tags if t in TYPE_BY_TAG), None)
    if ptype is None:
        return None
    if _RENT_RE.search(normalize_ar(title)) or any(_RENT_RE.search(normalize_ar(t)) for t in tags):
        return None
    if _WANTED_RE.search(normalize_ar(title)):
        return None
    body = html.unescape(d.get(m["bodyTEXT"]) or "").strip()
    pt, precision = _location(pid, decode_geohash(d.get(m["geo"])), parse_maps_link(body))
    lat, lng = pt if pt else (None, None)
    posted = d.get(m["postDate"])
    imgs = d.get(m["imagesList"])
    fields = CanonicalFields(
        property_type=ptype, title=html.unescape(title) or None, description=body or None,
        city=d.get(m["city"]) or None, district=_district(d.get(m["district"]), title, body),
        price=_price(d.get(m["price"])) or parse_price_from_text(body, html.unescape(title)), lat=lat, lng=lng)
    return RawListing(
        source="haraj", source_id=str(pid), url=f"{SITE}/{pid}", fields=fields,
        geo_precision=precision,
        photo_urls=[u for u in (imgs if isinstance(imgs, list) else []) if isinstance(u, str) and u.startswith("http")],
        seller_phone=None, seller_name=None,  # never requested from the API; see docs/sources/haraj.md
        listed_at=datetime.fromtimestamp(posted, UTC) if isinstance(posted, (int, float)) and not isinstance(posted, bool) else None,
        raw=d)


class HarajAdapter:
    name = "haraj"

    def __init__(self, transport: HarajTransport, pacer: Pacer | None = None):
        self._t = transport
        self._pacer = pacer or Pacer()

    def _tags(self, ptype: str, q: SearchQuery) -> list[str]:
        base = HARAJ_TAG_BY_TYPE[ptype]
        if not q.districts:
            return [base]
        return [f"{base} في حي {normalize_district(d)} في {q.city}" for d in q.districts]

    def search(self, q: SearchQuery) -> Iterator[RawListing]:
        wanted = {normalize_district(d) for d in q.districts}
        seen: set[str] = set()
        for ptype in q.property_types:
            for tag in self._tags(ptype, q):
                for page in range(q.max_pages):
                    self._pacer.wait()
                    posts = extract_posts(self._t.search(tag, q.city, page))
                    if not posts:
                        break
                    for p in posts:
                        r = parse_post(p)
                        if r is None or r.source_id in seen:
                            continue
                        f = r.fields
                        if f.city and f.city != q.city:
                            continue  # tag pages also list nearby cities
                        if wanted and f.district and normalize_district(f.district) not in wanted:
                            continue
                        if q.price_max and f.price and f.price > q.price_max:
                            continue
                        seen.add(r.source_id)
                        yield r

    def fetch(self, source_id: str) -> RawListing | None:
        self._pacer.wait()
        p = self._t.post(source_id)
        return parse_post(p) if p else None

    def health(self, sample: list[RawListing], min_sample: int = 10, threshold: float = 0.5) -> HealthReport:
        """Price is deliberately not checked: Haraj posts carry it in the body text."""
        n = len(sample)
        if n == 0:
            return HealthReport(ok=True, sample_size=0, missing_ratio={})
        ratio = {"title_or_body": sum(not (r.fields.title and r.fields.description) for r in sample) / n}
        if n >= min_sample and ratio["title_or_body"] > threshold:
            return HealthReport(ok=False, sample_size=n, missing_ratio=ratio,
                                reason=f"missing title or body in >{int(threshold * 100)}% of {n} results")
        return HealthReport(ok=True, sample_size=n, missing_ratio=ratio)

"""Haraj transport: the public GraphQL endpoint the haraj.com.sa web client itself calls (query `FetchAds`).

Unauthenticated, same request the browser makes. We never send the `BETWEEN-SERVERS-KEY` header that appears
in the site's JS bundle (a server-to-server credential), and we never ask for seller identity fields.
See docs/sources/haraj.md.
"""
import json
import logging
import uuid
from collections.abc import Callable
from typing import Protocol

from homefinder.worker.sources.aqar_transport import Blocked

log = logging.getLogger(__name__)

SITE = "https://haraj.com.sa"
GRAPHQL = "https://graphql.haraj.com.sa/"
API_VERSION = "N0.0.1 , 2026-11-10 10"  # the web client sends a build stamp; any value is accepted (probe)

# Only the fields the adapter uses. No authorUsername/authorId/realEstateInfo (seller identity / licence numbers).
FETCH_ADS_QUERY = """
query FetchAds($id: [Int] = null, $city: String = null, $page: Int = null, $tag: String = null) {
  posts(id: $id, city: $city, page: $page, tag: $tag) {
    items {
      id title postDate updateDate URL bodyTEXT thumbURL hasImage city geoCity geoNeighborhood geoHash
      tags imagesList status postType
      price { formattedPrice inputPrice }
      generalInfo { key value }
    }
    pageInfo { hasNextPage }
  }
}
"""
HEADERS = {"Content-Type": "application/json", "origin": SITE, "referer": SITE + "/", "accept-language": "ar,en;q=0.9"}


class HarajTransport(Protocol):
    def search(self, tag: str, city: str, page: int) -> dict: ...
    def post(self, post_id: str) -> dict | None: ...
    def close(self) -> None: ...


def search_variables(tag: str, city: str, page: int) -> dict:
    """`page` is 0-based for us; Haraj pages are 1-based (page 0 and 1 return the same results, probe)."""
    return {"tag": tag, "city": city, "page": page + 1}


def build_request(variables: dict) -> tuple[str, str]:
    url = f"{GRAPHQL}?queryName=posts&clientId={uuid.uuid4().hex[:16]}&version={API_VERSION}"
    return url, json.dumps({"query": FETCH_ADS_QUERY, "variables": variables})


def _check(data: dict, who: str) -> dict:
    posts = ((data or {}).get("data") or {}).get("posts") if isinstance(data, dict) else None
    if not isinstance(data, dict) or data.get("errors") or posts is None:
        raise Blocked(f"{who}: graphql error {str(data.get('errors') if isinstance(data, dict) else data)[:200]}")
    return data


def _first_item(data: dict) -> dict | None:
    items = ((data.get("data") or {}).get("posts") or {}).get("items") or []
    return items[0] if items else None


class CurlCffiHaraj:
    def __init__(self, impersonate: str = "chrome"):
        from curl_cffi import requests as cr
        self._s = cr.Session(impersonate=impersonate)
        self._warmed = False

    def _graphql(self, variables: dict) -> dict:
        if not self._warmed:
            self._s.get(SITE + "/", timeout=30)
            self._warmed = True
        url, body = build_request(variables)
        r = self._s.post(url, data=body, headers=HEADERS, timeout=30)
        if r.status_code != 200 or "json" not in r.headers.get("content-type", ""):
            raise Blocked(f"curl_cffi haraj: HTTP {r.status_code}")
        return _check(r.json(), "curl_cffi haraj")

    def search(self, tag: str, city: str, page: int) -> dict:
        return self._graphql(search_variables(tag, city, page))

    def post(self, post_id: str) -> dict | None:
        return _first_item(self._graphql({"id": [int(post_id)]}))

    def close(self) -> None:
        self._s.close()


_FETCH_JS = """async ([url, body]) => {
  const r = await fetch(url, {method: 'POST', headers: {'content-type': 'application/json'}, body, credentials: 'include'});
  return {status: r.status, ct: r.headers.get('content-type') || '', text: await r.text()};
}"""


class PlaywrightHaraj:
    def __init__(self, headless: bool = True):
        self._headless = headless
        self._pw = self._browser = self._page = None

    def _graphql(self, variables: dict) -> dict:
        if self._page is None:
            from playwright.sync_api import sync_playwright
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(headless=self._headless)
            self._page = self._browser.new_page(locale="ar-SA")
            self._page.goto(SITE + "/", wait_until="domcontentloaded", timeout=60_000)
            self._page.wait_for_timeout(3000)
        url, body = build_request(variables)
        res = self._page.evaluate(_FETCH_JS, [url, body])
        if res["status"] != 200 or "json" not in res["ct"]:
            raise Blocked(f"playwright haraj: HTTP {res['status']}")
        return _check(json.loads(res["text"]), "playwright haraj")

    def search(self, tag: str, city: str, page: int) -> dict:
        return self._graphql(search_variables(tag, city, page))

    def post(self, post_id: str) -> dict | None:
        return _first_item(self._graphql({"id": [int(post_id)]}))

    def close(self) -> None:
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()
        self._pw = self._browser = self._page = None


class FallbackHaraj:
    """Tries transports in order; once one is Blocked, uses the next for the rest of the run."""

    def __init__(self, factories: list[Callable[[], HarajTransport]]):
        self._factories, self._i, self._t = factories, 0, None

    def _call(self, fn: str, *args):
        while True:
            if self._t is None:
                self._t = self._factories[self._i]()
            try:
                return getattr(self._t, fn)(*args)
            except Blocked as e:
                log.warning("haraj transport %d blocked: %s", self._i, e)
                self._t.close()
                self._t = None
                if self._i + 1 >= len(self._factories):
                    self._i = 0  # everything blocked: the next run starts with the first transport again
                    raise
                self._i += 1

    def search(self, tag: str, city: str, page: int) -> dict:
        return self._call("search", tag, city, page)

    def post(self, post_id: str) -> dict | None:
        return self._call("post", post_id)

    def close(self) -> None:
        if self._t:
            self._t.close()
            self._t = None


def make_haraj_transport() -> FallbackHaraj:
    return FallbackHaraj([CurlCffiHaraj, lambda: PlaywrightHaraj(headless=True)])

import json
import logging
import os
from collections.abc import Callable
from typing import Protocol

log = logging.getLogger(__name__)

# Sent by the live web client; Aqar rejects stale values. See docs/sources/aqar.md for how to refresh.
AQAR_APP_VERSION = os.environ.get("AQAR_APP_VERSION", "1.0.3")
GRAPHQL_URL = "https://sa.aqar.fm/graphql"
HOME_URL = "https://sa.aqar.fm/"
API_HEADERS = {"accept": "*/*", "content-type": "application/json", "origin": "https://sa.aqar.fm",
               "referer": HOME_URL, "req-app": "web", "app-version": AQAR_APP_VERSION, "accept-language": "ar,en;q=0.9"}


class Blocked(Exception):
    pass


class AppVersionOutdated(Blocked):
    """Aqar rejected the app-version header (GraphQL error says the app is outdated)."""


def check_graphql_errors(data: dict, who: str) -> None:
    for e in data.get("errors") or []:
        msg = str(e.get("message", ""))
        if "قديمة" in msg or "تحديث التطبيق" in msg:
            raise AppVersionOutdated(f"{who}: aqar app-version outdated ({AQAR_APP_VERSION})")


class Transport(Protocol):
    def post_graphql(self, body: dict) -> dict: ...
    def close(self) -> None: ...


class CurlCffiTransport:
    def __init__(self, impersonate: str = "chrome"):
        from curl_cffi import requests as cr
        self._s = cr.Session(impersonate=impersonate)
        self._warmed = False

    def post_graphql(self, body: dict) -> dict:
        if not self._warmed:
            self._s.get(HOME_URL, timeout=30)
            self._warmed = True
        r = self._s.post(GRAPHQL_URL, json=body, headers=API_HEADERS, timeout=30)
        if r.status_code != 200 or "json" not in r.headers.get("content-type", ""):
            raise Blocked(f"curl_cffi: HTTP {r.status_code}")
        data = r.json()
        check_graphql_errors(data, "curl_cffi")
        return data

    def close(self) -> None:
        self._s.close()


_FETCH_JS = """async ([url, body, headers]) => {
  const r = await fetch(url, {method: 'POST', headers, body: JSON.stringify(body), credentials: 'include'});
  return {status: r.status, ct: r.headers.get('content-type') || '', text: await r.text()};
}"""


class PlaywrightTransport:
    def __init__(self, headless: bool = True):
        self._headless = headless
        self._pw = self._browser = self._page = None

    def _ensure(self):
        if self._page is not None:
            return
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=self._headless)
        self._page = self._browser.new_page(locale="ar-SA")
        self._page.goto(HOME_URL, wait_until="domcontentloaded", timeout=60_000)
        self._page.wait_for_timeout(3000)

    def post_graphql(self, body: dict) -> dict:
        self._ensure()
        headers = {k: v for k, v in API_HEADERS.items() if k in ("content-type", "req-app", "app-version")}
        res = self._page.evaluate(_FETCH_JS, [GRAPHQL_URL, body, headers])
        if res["status"] != 200 or "json" not in res["ct"]:
            raise Blocked(f"playwright: HTTP {res['status']}")
        data = json.loads(res["text"])
        check_graphql_errors(data, "playwright")
        return data

    def close(self) -> None:
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()
        self._pw = self._browser = self._page = None


class FallbackTransport:
    """Tries transports in order; once one is Blocked, moves to the next for the rest of the run."""

    def __init__(self, factories: list[Callable[[], Transport]]):
        self._factories = factories
        self._i = 0
        self._t: Transport | None = None

    def post_graphql(self, body: dict) -> dict:
        while True:
            if self._t is None:
                self._t = self._factories[self._i]()
            try:
                return self._t.post_graphql(body)
            except AppVersionOutdated:
                self._t.close()
                self._t = None
                raise  # version problem is transport-independent; don't burn the fallback
            except Blocked as e:
                log.warning("aqar transport %d blocked: %s", self._i, e)
                self._t.close()
                self._t = None
                if self._i + 1 >= len(self._factories):
                    self._i = 0  # everything blocked: the next run starts with the first transport again
                    raise
                self._i += 1

    def close(self) -> None:
        if self._t:
            self._t.close()
            self._t = None

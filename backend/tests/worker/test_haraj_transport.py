import json

import pytest

from homefinder.worker.sources.aqar_transport import Blocked
from homefinder.worker.sources.haraj_transport import (CurlCffiHaraj, FallbackHaraj, build_request, search_variables)


def test_search_variables_use_one_based_api_pages():
    assert search_variables("فلل للبيع", "الرياض", 0) == {"tag": "فلل للبيع", "city": "الرياض", "page": 1}
    assert search_variables("فلل للبيع", "الرياض", 2)["page"] == 3


def test_build_request_shape():
    url, body = build_request({"id": [5]})
    assert url.startswith("https://graphql.haraj.com.sa/?queryName=posts&clientId=")
    payload = json.loads(body)
    assert payload["variables"] == {"id": [5]} and "query FetchAds" in payload["query"]
    for secret_field in ("authorUsername", "authorId", "realEstateInfo"):
        assert secret_field not in payload["query"]  # never ask for seller identity


class FakeResp:
    def __init__(self, status=200, ct="application/json", data=None):
        self.status_code, self.headers, self._d = status, {"content-type": ct}, data

    def json(self):
        return self._d


class FakeSession:
    def __init__(self, resp): self.resp, self.posts = resp, []
    def get(self, url, **kw): return FakeResp(200, "text/html")
    def post(self, url, **kw): self.posts.append((url, kw)); return self.resp
    def close(self): pass


def curl(resp):
    t = CurlCffiHaraj.__new__(CurlCffiHaraj)
    t._s, t._warmed = FakeSession(resp), False
    return t


def test_non_200_or_non_json_raises_blocked():
    with pytest.raises(Blocked):
        curl(FakeResp(status=403)).search("t", "c", 0)
    with pytest.raises(Blocked):
        curl(FakeResp(ct="text/html")).search("t", "c", 0)


def test_graphql_errors_raise_blocked():
    with pytest.raises(Blocked):
        curl(FakeResp(data={"errors": [{"message": "x"}]})).search("t", "c", 0)


def test_post_returns_item_or_none():
    item = {"id": 5, "title": "x"}
    ok = {"data": {"posts": {"items": [item], "pageInfo": {"hasNextPage": False}}}}
    assert curl(FakeResp(data=ok)).post("5") == item
    empty = {"data": {"posts": {"items": [], "pageInfo": {"hasNextPage": False}}}}
    assert curl(FakeResp(data=empty)).post("5") is None


def test_fallback_moves_to_next_transport_on_block():
    calls = []

    class T:
        def __init__(self, exc): self.exc = exc
        def search(self, *a):
            calls.append(self)
            if self.exc: raise self.exc
            return {"ok": 1}
        def post(self, pid): return None
        def close(self): pass

    ft = FallbackHaraj([lambda: T(Blocked("b")), lambda: T(None)])
    assert ft.search("t", "c", 0) == {"ok": 1} and len(calls) == 2

import pytest

from homefinder.worker.sources import aqar_transport as at


class FakeSession:
    posts: list = []
    def __init__(self, **kw): pass
    def get(self, *a, **k): pass
    def post(self, url, json=None, headers=None, timeout=None):
        FakeSession.posts.append(headers)
        class R:
            status_code = 200
            headers = {"content-type": "application/json"}
            def json(self_): return {"data": {}}
        return R()
    def close(self): pass


def test_curl_transport_sends_the_app_version_from_settings(settings_env, monkeypatch):
    import curl_cffi.requests as cr
    monkeypatch.setattr(cr, "Session", FakeSession)
    FakeSession.posts = []
    settings_env(AQAR_APP_VERSION="9.9.9")
    at.CurlCffiTransport().post_graphql({})
    assert FakeSession.posts[-1]["app-version"] == "9.9.9"
    monkeypatch.delenv("AQAR_APP_VERSION")
    settings_env()  # no override: the documented default
    at.CurlCffiTransport().post_graphql({})
    assert FakeSession.posts[-1]["app-version"] == "1.0.3"


def test_outdated_message_names_the_configured_version(settings_env):
    settings_env(AQAR_APP_VERSION="9.9.9")
    with pytest.raises(at.AppVersionOutdated, match=r"9\.9\.9"):
        at.check_graphql_errors({"errors": [{"message": "النسخة قديمة"}]}, "x")


def test_playwright_headers_use_the_configured_version(settings_env):
    settings_env(AQAR_APP_VERSION="9.9.9")
    assert at.api_headers()["app-version"] == "9.9.9" and at.api_headers()["req-app"] == "web"

import pytest

from homefinder.worker.sources.aqar_transport import (AppVersionOutdated, Blocked, FallbackTransport,
                                                      check_graphql_errors)

OUTDATED = {"errors": [{"message": "عذراً هذه النسخة من التطبيق قديمة، يرجى تحديث التطبيق", "code": 400}]}


def test_outdated_error_maps_to_app_version_outdated():
    with pytest.raises(AppVersionOutdated) as ei:
        check_graphql_errors(OUTDATED, "x")
    assert isinstance(ei.value, Blocked) and "app-version outdated" in str(ei.value)
    check_graphql_errors({"data": {}}, "x")  # no error: fine
    check_graphql_errors({"errors": [{"message": "other"}]}, "x")


def test_fallback_does_not_try_next_transport_on_outdated_version():
    calls = []

    class T:
        def __init__(self, exc): self.exc = exc
        def post_graphql(self, body): calls.append(self); raise self.exc
        def close(self): pass

    ft = FallbackTransport([lambda: T(AppVersionOutdated("v")), lambda: T(Blocked("b"))])
    with pytest.raises(AppVersionOutdated):
        ft.post_graphql({})
    assert len(calls) == 1

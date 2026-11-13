def test_login_and_me(app_client):
    assert app_client.get("/api/me").status_code == 401
    assert app_client.post("/api/login", json={"password": "nope"}).status_code == 401
    assert app_client.post("/api/login", json={"password": "secret"}).status_code == 204
    assert app_client.get("/api/me").json() == {"ok": True}
    app_client.post("/api/logout")
    assert app_client.get("/api/me").status_code == 401


def test_login_rate_limit(app_client):
    codes = [app_client.post("/api/login", json={"password": "x"}).status_code for _ in range(6)]
    assert codes == [401] * 5 + [429]
    assert app_client.post("/api/login", json={"password": "secret"}).status_code == 429


def test_api_requires_session(app_client):
    for path in ["/api/feed", "/api/map", "/api/places", "/api/preferences", "/api/status", "/api/listings/1"]:
        assert app_client.get(path).status_code == 401, path


def test_worker_requires_token(app_client):
    assert app_client.post("/worker/claim", json={"types": ["x"], "n": 1}).status_code == 401
    assert app_client.post("/worker/claim", json={"types": ["x"], "n": 1},
                           headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_password_over_72_bytes_is_a_counted_401_not_a_500(app_client):
    """M1: bcrypt 5 raises ValueError for >72 bytes; a long Arabic passphrase must not crash login."""
    long_pw = "ك" * 40  # 80 bytes
    codes = [app_client.post("/api/login", json={"password": long_pw}).status_code for _ in range(6)]
    assert codes == [401] * 5 + [429]
    assert app_client.post("/api/login", json={"password": "x" * 300}).status_code in (422, 429)


def test_cli_hash_password_rejects_more_than_72_bytes(monkeypatch, capsys):
    import pytest
    from homefinder import cli
    monkeypatch.setattr("getpass.getpass", lambda prompt="": "ك" * 40)
    with pytest.raises(SystemExit) as e:
        cli.main(["hash-password"])
    assert e.value.code == 1 and "72" in capsys.readouterr().err


def test_rate_limit_forgets_idle_ips_and_has_a_global_cap(app_client, monkeypatch):
    from homefinder.server import auth
    for i in range(3):
        app_client.post("/api/login", json={"password": "x"}, headers={"x-real-ip": f"10.0.0.{i}"})
    import time
    clock = [time.monotonic()]
    monkeypatch.setattr(auth.time, "monotonic", lambda: clock[0])
    app_client.post("/api/login", json={"password": "x"}, headers={"x-real-ip": "10.0.0.9"})
    clock[0] += auth.WINDOW + 1
    app_client.post("/api/login", json={"password": "x"}, headers={"x-real-ip": "10.0.0.9"})
    assert len(auth._attempts) <= 1  # the idle IPs' empty queues were dropped
    auth.reset_rate_limit()
    codes = [app_client.post("/api/login", json={"password": "x"}, headers={"x-real-ip": f"10.1.0.{i}"}).status_code
             for i in range(auth.GLOBAL_MAX + 1)]
    assert codes == [401] * auth.GLOBAL_MAX + [429]  # many IPs, one attacker

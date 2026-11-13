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

import bcrypt
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app_client(db, settings_env, tmp_path):
    settings_env(FAMILY_PASSWORD_HASH=bcrypt.hashpw(b"secret", bcrypt.gensalt(4)).decode(),
                 WORKER_TOKEN="wtok", PHOTOS_DIR=str(tmp_path))
    from homefinder.server import auth
    auth.reset_rate_limit()
    from homefinder.server.app import create_app
    return TestClient(create_app())


@pytest.fixture
def family(app_client):
    assert app_client.post("/api/login", json={"password": "secret"}).status_code == 204
    return app_client


@pytest.fixture
def worker_headers():
    return {"Authorization": "Bearer wtok"}

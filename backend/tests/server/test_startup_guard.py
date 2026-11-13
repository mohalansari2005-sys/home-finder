import pytest

GOOD = dict(SESSION_SECRET="s" * 64, WORKER_TOKEN="w" * 48, FAMILY_PASSWORD_HASH="$2b$12$abcdefghijklmnopqrstuv", COOKIE_SECURE="true")


def _create(settings_env, **over):
    settings_env(**{**GOOD, **over})
    from homefinder.server.app import create_app
    return create_app()


def test_production_starts_with_real_secrets(db, settings_env):
    assert _create(settings_env) is not None


@pytest.mark.parametrize("name,bad", [
    ("SESSION_SECRET", "dev-only-change-me"),
    ("SESSION_SECRET", "CHANGE_ME_64_RANDOM_CHARS"),
    ("SESSION_SECRET", "x" * 31),
    ("SESSION_SECRET", ""),
    ("WORKER_TOKEN", "dev-worker-token"),
    ("WORKER_TOKEN", "CHANGE_ME_RANDOM"),
    ("WORKER_TOKEN", "short"),
    ("WORKER_TOKEN", ""),
    ("FAMILY_PASSWORD_HASH", ""),
])
def test_production_refuses_default_or_placeholder_secrets(db, settings_env, name, bad):
    with pytest.raises(RuntimeError, match="refusing to start"):
        _create(settings_env, **{name: bad})


def test_dev_mode_keeps_working_with_defaults(db, settings_env):
    assert _create(settings_env, COOKIE_SECURE="false", SESSION_SECRET="dev-only-change-me") is not None


def test_error_never_prints_the_secret(db, settings_env):
    with pytest.raises(RuntimeError) as e:
        _create(settings_env, SESSION_SECRET="CHANGE_ME_64_RANDOM_CHARS")
    assert "CHANGE_ME_64" not in str(e.value) and "SESSION_SECRET" in str(e.value)

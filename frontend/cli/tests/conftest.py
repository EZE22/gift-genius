import pytest


@pytest.fixture(autouse=True)
def no_env_file(monkeypatch):
    """The CLI must not read the real .env during tests."""
    monkeypatch.setattr("gift_genius_cli.__main__.load_env", lambda: None)

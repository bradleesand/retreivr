from __future__ import annotations

import importlib
import sys

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient


def _build_client(monkeypatch) -> TestClient:
    import engine.core  # noqa: F401
    from types import SimpleNamespace
    sys.modules.pop("api.main", None)
    module = importlib.import_module("api.main")
    module.app.router.on_startup.clear()
    module.app.router.on_shutdown.clear()
    module.app.state.config_path = "/tmp/retreivr_test_config.json"
    module.app.state.paths = SimpleNamespace(db_path="/tmp/retreivr_test.db", single_downloads_dir="/tmp/downloads")
    module.app.state.search_service = None
    monkeypatch.setattr(module, "_read_config_or_404", lambda: {})
    return TestClient(module.app)


def test_intent_execute_accepts_valid_spotify_album_intent(monkeypatch) -> None:
    client = _build_client(monkeypatch)

    import importlib as _il
    module = _il.import_module("api.main")

    async def _fake_dispatch(*, intent_type, identifier, config, db, queue, spotify_client):
        return {
            "status": "accepted",
            "intent_type": intent_type,
            "identifier": identifier,
        }

    monkeypatch.setattr(module, "dispatch_intent", _fake_dispatch)

    response = client.post(
        "/api/intent/execute",
        json={
            "intent_type": "spotify_album",
            "identifier": "1A2B3C4D5E",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "accepted"
    assert payload["intent_type"] == "spotify_album"
    assert payload["identifier"] == "1A2B3C4D5E"


def test_intent_execute_rejects_invalid_intent_type(monkeypatch) -> None:
    client = _build_client(monkeypatch)

    response = client.post(
        "/api/intent/execute",
        json={
            "intent_type": "not_real_intent",
            "identifier": "abc",
        },
    )

    assert response.status_code == 400

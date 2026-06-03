from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient


@pytest.fixture()
def api_module(tmp_path: Path, monkeypatch):
    import engine.core  # noqa: F401

    sys.modules.pop("api.main", None)
    module = importlib.import_module("api.main")
    module.app.router.on_startup.clear()
    module.app.router.on_shutdown.clear()
    module.app.state.paths = SimpleNamespace(db_path=str(tmp_path / "retreivr.sqlite3"))
    module.app.state.music_cover_art_cache = {}
    return module


def test_album_art_endpoint_persists_positive_cover_url(api_module, monkeypatch) -> None:
    calls = {"count": 0}

    class _FakeMusicBrainz:
        def fetch_release_group_cover_art_url(self, album_id: str, *, timeout: int):
            calls["count"] += 1
            assert album_id == "release-group-1"
            assert timeout == 8
            return "https://coverartarchive.org/release-group/release-group-1/front-250"

    monkeypatch.setattr(api_module, "_mb_service", lambda: _FakeMusicBrainz())
    client = TestClient(api_module.app)

    first = client.get("/api/music/album/art/release-group-1")
    assert first.status_code == 200
    assert first.json()["cover_url"] == "https://coverartarchive.org/release-group/release-group-1/front-250"
    assert first.json()["cache"] == "network"
    assert calls["count"] == 1

    api_module.app.state.music_cover_art_cache = {}
    second = client.get("/api/music/album/art/release-group-1")
    assert second.status_code == 200
    assert second.json()["cover_url"] == "https://coverartarchive.org/release-group/release-group-1/front-250"
    assert second.json()["cache"] == "persistent"
    assert calls["count"] == 1


def test_album_art_endpoint_rejects_non_http_cached_urls(api_module, monkeypatch) -> None:
    api_module._set_music_artwork_cache_entry("album", "release-group-2", {"cover_url": "file:///tmp/cover.jpg"})

    class _FakeMusicBrainz:
        def fetch_release_group_cover_art_url(self, album_id: str, *, timeout: int):
            return None

    monkeypatch.setattr(api_module, "_mb_service", lambda: _FakeMusicBrainz())
    client = TestClient(api_module.app)

    resp = client.get("/api/music/album/art/release-group-2")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "cover_url": None, "cache": "miss"}

from __future__ import annotations

import importlib
import sys
import tempfile
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient


def _build_client(monkeypatch) -> TestClient:
    # Pre-load engine.core with real packages before stubs are injected.
    import engine.core  # noqa: F401
    monkeypatch.setattr(sys, "version_info", (3, 11, 0, "final", 0), raising=False)
    monkeypatch.setattr(sys, "version", "3.11.9 (main, Jan  1 2024, 00:00:00) [Clang 14.0.0]", raising=False)
    for _key, _val in [
        ("google_auth_oauthlib", None),
        ("google_auth_oauthlib.flow", {"InstalledAppFlow": object}),
        ("googleapiclient", None),
        ("googleapiclient.errors", {"HttpError": Exception}),
        ("google", None),
        ("google.auth", None),
        ("google.auth.exceptions", {"RefreshError": Exception}),
        ("google.auth.transport", None),
        ("google.auth.transport.requests", {"Request": object}),
        ("google.oauth2", None),
        ("google.oauth2.credentials", {"Credentials": object}),
        ("musicbrainzngs", None),
    ]:
        if _key not in sys.modules:
            _mod = types.ModuleType(_key)
            if _val:
                for _attr, _obj in _val.items():
                    setattr(_mod, _attr, _obj)
            sys.modules[_key] = _mod

    sys.modules.pop("api.main", None)
    module = importlib.import_module("api.main")
    module.app.router.on_startup.clear()
    module.app.router.on_shutdown.clear()

    tmp_dir = tempfile.mkdtemp()
    db_path = str(Path(tmp_dir) / "test.sqlite")
    module.app.state.paths = SimpleNamespace(
        db_path=db_path,
        single_downloads_dir=tmp_dir,
        temp_downloads_dir=tmp_dir,
        ytdlp_temp_dir=tmp_dir,
    )

    return TestClient(module.app)


def test_music_enqueue_rejects_missing_recording_mbid(monkeypatch) -> None:
    client = _build_client(monkeypatch)
    response = client.post("/api/music/enqueue", json={"artist": "Artist", "track": "Song"})
    assert response.status_code == 400
    assert "recording_mbid" in str(response.json().get("detail"))


def test_music_enqueue_allows_optional_missing_fields(monkeypatch) -> None:
    client = _build_client(monkeypatch)
    monkeypatch.setattr("api.main._read_config_or_404", lambda: {})

    captured: dict = {}

    class _FakeStore:
        def __init__(self, _db_path):
            pass

        def enqueue_job(self, **kwargs):
            captured["enqueue_payload"] = dict(kwargs)
            return "job-1", True, None

    def _fake_builder(**kwargs):
        captured["builder_kwargs"] = dict(kwargs)
        return {"id": "job-1", "url": "musicbrainz://recording/rec-1"}

    monkeypatch.setattr("api.main.DownloadJobStore", _FakeStore)
    monkeypatch.setattr("api.main.build_download_job_payload", _fake_builder)

    response = client.post(
        "/api/music/enqueue",
        json={
            "recording_mbid": "rec-1",
            "artist": "Artist",
            "track": "Song",
        },
    )

    assert response.status_code == 200
    canonical = captured["builder_kwargs"]["resolved_metadata"]
    assert canonical["recording_mbid"] == "rec-1"
    assert canonical["artist"] == "Artist"
    assert canonical["track"] == "Song"
    assert canonical["album"] == ""
    assert canonical["track_number"] is None
    assert canonical["disc_number"] is None
    assert canonical["duration_ms"] is None
    module = importlib.import_module("api.main")
    assert captured["builder_kwargs"]["canonical_id"] == module._build_music_track_canonical_id(
        "Artist",
        "",
        None,
        "Song",
        recording_mbid="rec-1",
    )


def test_music_enqueue_returns_structured_binding_failure(monkeypatch) -> None:
    client = _build_client(monkeypatch)
    monkeypatch.setattr("api.main._read_config_or_404", lambda: {})

    class _FakeStore:
        def __init__(self, _db_path):
            pass

        def enqueue_job(self, **kwargs):
            _ = kwargs
            return "job-1", True, None

    def _failing_builder(**kwargs):
        _ = kwargs
        raise ValueError("music_track_requires_mb_bound_metadata", ["no_valid_release_for_recording"])

    monkeypatch.setattr("api.main.DownloadJobStore", _FakeStore)
    monkeypatch.setattr("api.main.build_download_job_payload", _failing_builder)

    response = client.post(
        "/api/music/enqueue",
        json={
            "recording_mbid": "rec-1",
            "artist": "Artist",
            "track": "Song",
        },
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "music_mode_mb_binding_failed"
    assert "no_valid_release_for_recording" in body["reason"]


def test_music_enqueue_music_video_mode_targets_video_media_type(monkeypatch) -> None:
    client = _build_client(monkeypatch)
    monkeypatch.setattr("api.main._read_config_or_404", lambda: {})

    captured: dict = {}

    class _FakeStore:
        def __init__(self, _db_path):
            pass

        def enqueue_job(self, **kwargs):
            captured["enqueue_payload"] = dict(kwargs)
            return "job-1", True, None

    def _fake_builder(**kwargs):
        captured["builder_kwargs"] = dict(kwargs)
        return {"id": "job-1", "url": "musicbrainz://recording/rec-1"}

    monkeypatch.setattr("api.main.DownloadJobStore", _FakeStore)
    monkeypatch.setattr("api.main.build_download_job_payload", _fake_builder)

    response = client.post(
        "/api/music/enqueue",
        json={
            "recording_mbid": "rec-1",
            "artist": "Artist",
            "track": "Song",
            "media_mode": "music_video",
        },
    )

    assert response.status_code == 200
    assert captured["builder_kwargs"]["media_type"] == "video"
    assert captured["builder_kwargs"]["media_intent"] == "music_track"
    assert captured["builder_kwargs"]["output_template_overrides"]["audio_mode"] is False

from __future__ import annotations

import importlib
import sqlite3
import sys
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from engine.job_queue import ensure_download_history_table


def _build_client(monkeypatch) -> TestClient:
    import engine.core  # noqa: F401
    from types import SimpleNamespace
    sys.modules.pop("api.main", None)
    module = importlib.import_module("api.main")
    module.app.router.on_startup.clear()
    module.app.router.on_shutdown.clear()
    module.app.state.config_path = "/tmp/retreivr_test_config.json"
    module.app.state.paths = SimpleNamespace(db_path="/tmp/retreivr_test.db", single_downloads_dir="/tmp/downloads")
    monkeypatch.setattr(module, "_read_config_or_404", lambda: {})
    return TestClient(module.app)


def test_api_library_reconcile_returns_summary(monkeypatch) -> None:
    client = _build_client(monkeypatch)

    monkeypatch.setattr(
        "api.main.reconcile_library",
        lambda *, db_path, config: {
            "scan_roots": ["/downloads/Music"],
            "files_seen": 10,
            "audio_files_seen": 4,
            "video_files_seen": 2,
            "jobs_inserted": 3,
            "history_inserted": 3,
            "isrc_records_inserted": 2,
            "skipped_existing_jobs": 1,
            "skipped_missing_identity": 0,
            "skipped_unsupported": 6,
            "errors": 0,
        },
    )

    response = client.post("/api/library/reconcile")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["jobs_inserted"] == 3
    assert payload["history_inserted"] == 3
    assert payload["isrc_records_inserted"] == 2
    assert payload["video_files_seen"] == 2


def test_video_library_query_filters_to_video_history_before_limit(monkeypatch, tmp_path: Path) -> None:
    client = _build_client(monkeypatch)
    module = importlib.import_module("api.main")

    db_path = tmp_path / "db.sqlite"
    music_dir = tmp_path / "downloads" / "Music"
    video_dir = tmp_path / "downloads" / "Videos"
    music_dir.mkdir(parents=True)
    video_dir.mkdir(parents=True)
    video_path = video_dir / "Old Clip.mp4"
    video_path.write_bytes(b"video")

    with sqlite3.connect(db_path) as conn:
        ensure_download_history_table(conn)
        for index in range(240):
            conn.execute(
                """
                INSERT INTO download_history (
                    video_id, title, filename, destination, source, status, created_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"song-{index}",
                    f"Song {index}",
                    f"Song {index}.mp3",
                    str(music_dir),
                    "library_reconcile",
                    "completed",
                    f"2026-06-03T12:{index % 60:02d}:00Z",
                    f"2026-06-03T12:{index % 60:02d}:00Z",
                ),
            )
        conn.execute(
            """
            INSERT INTO download_history (
                video_id, title, filename, destination, source, status, created_at, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "old-video",
                "Old Clip",
                video_path.name,
                str(video_dir),
                "local_library",
                "completed",
                "2026-06-02T12:00:00Z",
                "2026-06-02T12:00:00Z",
            ),
        )

    items = module._list_video_library_items(str(db_path), limit=1)

    assert len(items) == 1
    assert items[0]["title"] == "Old Clip"

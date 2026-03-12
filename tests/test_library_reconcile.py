from __future__ import annotations

import sqlite3
import sys
import types
from pathlib import Path

google = types.ModuleType("google")
google_auth = types.ModuleType("google.auth")
google_auth_exceptions = types.ModuleType("google.auth.exceptions")


class _RefreshError(Exception):
    pass


google_auth_exceptions.RefreshError = _RefreshError
google_auth.exceptions = google_auth_exceptions
google.auth = google_auth
sys.modules.setdefault("google", google)
sys.modules.setdefault("google.auth", google_auth)
sys.modules.setdefault("google.auth.exceptions", google_auth_exceptions)

from engine.job_queue import ensure_download_history_table, ensure_download_jobs_table
from db.migrations import ensure_downloaded_music_tracks_table
from library import reconcile as reconcile_module


def _prepare_db(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    try:
        ensure_download_jobs_table(conn)
        ensure_download_history_table(conn)
        ensure_downloaded_music_tracks_table(conn)
    finally:
        conn.close()


def test_reconcile_music_library_backfills_jobs_history_and_isrc(tmp_path, monkeypatch) -> None:
    downloads_root = tmp_path / "downloads"
    music_root = downloads_root / "Music"
    track_path = music_root / "Artist" / "Album (2024)" / "01 - Song.mp3"
    track_path.parent.mkdir(parents=True, exist_ok=True)
    track_path.write_bytes(b"audio")

    db_path = tmp_path / "db.sqlite"
    _prepare_db(db_path)

    monkeypatch.setattr(reconcile_module, "DOWNLOADS_DIR", downloads_root)
    monkeypatch.setattr(
        reconcile_module,
        "_read_music_identity",
        lambda path: {
            "title": "Song",
            "artist": "Artist",
            "album": "Album",
            "album_artist": "Artist",
            "track_number": 1,
            "disc_number": 1,
            "recording_mbid": "rec-1",
            "mb_release_id": "rel-1",
            "isrc": "USABC1234567",
            "canonical_id": "music_track:rec-1:rel-1:d1:t1",
        },
    )

    first = reconcile_module.reconcile_music_library(
        db_path=str(db_path),
        config={"music_download_folder": "Music"},
    )
    second = reconcile_module.reconcile_music_library(
        db_path=str(db_path),
        config={"music_download_folder": "Music"},
    )

    assert first["jobs_inserted"] == 1
    assert first["history_inserted"] == 1
    assert first["isrc_records_inserted"] == 1
    assert second["jobs_inserted"] == 0
    assert second["history_inserted"] == 0
    assert second["isrc_records_inserted"] == 0
    assert second["skipped_existing_jobs"] == 1

    conn = sqlite3.connect(db_path)
    try:
        job_count = conn.execute("SELECT COUNT(*) FROM download_jobs").fetchone()[0]
        history_count = conn.execute("SELECT COUNT(*) FROM download_history").fetchone()[0]
        isrc_count = conn.execute("SELECT COUNT(*) FROM downloaded_music_tracks WHERE isrc=?", ("USABC1234567",)).fetchone()[0]
    finally:
        conn.close()

    assert job_count == 1
    assert history_count == 1
    assert isrc_count == 1

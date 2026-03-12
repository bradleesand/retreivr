from __future__ import annotations

import logging
import os
import sqlite3
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
from uuid import uuid4

from db.migrations import ensure_downloaded_music_tracks_table
from engine.canonical_ids import build_music_track_canonical_id
from engine.job_queue import (
    JOB_STATUS_COMPLETED,
    ensure_download_history_table,
    ensure_download_jobs_table,
    utc_now,
)
from engine.paths import DOWNLOADS_DIR, resolve_dir

logger = logging.getLogger(__name__)

try:
    from mutagen import File as MutagenFile
except ImportError:  # pragma: no cover
    MutagenFile = None


_SUPPORTED_AUDIO_EXTENSIONS = {
    ".mp3",
    ".m4a",
    ".mp4",
    ".m4b",
    ".flac",
    ".ogg",
    ".oga",
    ".opus",
    ".wav",
    ".aac",
    ".alac",
    ".wma",
}
_RECONCILE_PLAYLIST_ID = "__library_reconcile__"


@dataclass
class ReconcileSummary:
    scan_roots: list[str]
    files_seen: int = 0
    audio_files_seen: int = 0
    jobs_inserted: int = 0
    history_inserted: int = 0
    isrc_records_inserted: int = 0
    skipped_existing_jobs: int = 0
    skipped_missing_identity: int = 0
    skipped_unsupported: int = 0
    errors: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def reconcile_music_library(*, db_path: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    roots = _resolve_scan_roots(config or {})
    summary = ReconcileSummary(scan_roots=[str(path) for path in roots])

    conn = sqlite3.connect(db_path, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        ensure_download_jobs_table(conn)
        ensure_download_history_table(conn)
        ensure_downloaded_music_tracks_table(conn)
        for root in roots:
            _scan_root(conn, root, summary)
        conn.commit()
    finally:
        conn.close()
    return summary.to_dict()


def _resolve_scan_roots(config: dict[str, Any]) -> list[Path]:
    candidates: list[Path] = []
    for key in ("music_download_folder", "home_music_download_folder", "single_download_folder"):
        value = str(config.get(key) or "").strip()
        if not value:
            continue
        try:
            candidates.append(Path(resolve_dir(value, str(DOWNLOADS_DIR))).resolve())
        except Exception:
            logger.warning("Skipping non-downloads reconcile root from config: %s=%s", key, value)
    default_music = (DOWNLOADS_DIR / "Music").resolve()
    if default_music.exists():
        candidates.append(default_music)
    if not candidates:
        candidates.append(DOWNLOADS_DIR.resolve())

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in sorted(candidates, key=lambda path: (len(str(path)), str(path))):
        normalized = str(candidate)
        if normalized in seen:
            continue
        if any(_is_relative_to(candidate, existing) for existing in unique):
            continue
        unique.append(candidate)
        seen.add(normalized)
    return unique


def _scan_root(conn: sqlite3.Connection, root: Path, summary: ReconcileSummary) -> None:
    if not root.exists() or not root.is_dir():
        return
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        summary.files_seen += 1
        if path.suffix.lower() not in _SUPPORTED_AUDIO_EXTENSIONS:
            summary.skipped_unsupported += 1
            continue
        summary.audio_files_seen += 1
        try:
            metadata = _read_music_identity(path)
            if metadata is None:
                summary.skipped_missing_identity += 1
                continue
            inserted_job = _insert_reconciled_job(conn, path, metadata)
            if inserted_job:
                summary.jobs_inserted += 1
            else:
                summary.skipped_existing_jobs += 1
            if _insert_reconciled_history(conn, path, metadata):
                summary.history_inserted += 1
            isrc = str(metadata.get("isrc") or "").strip()
            if isrc and _insert_reconciled_isrc(conn, path, isrc):
                summary.isrc_records_inserted += 1
        except Exception:
            logger.exception("Library reconcile failed for %s", path)
            summary.errors += 1


def _read_music_identity(path: Path) -> dict[str, Any] | None:
    if MutagenFile is None:
        raise RuntimeError("mutagen is required for library reconcile")

    audio = MutagenFile(str(path), easy=False)
    if audio is None:
        return None
    tags = getattr(audio, "tags", None)
    if not tags:
        return None

    title = _first_tag(tags, "TIT2", "\xa9nam", "title")
    artist = _first_tag(tags, "TPE1", "\xa9ART", "artist")
    album = _first_tag(tags, "TALB", "\xa9alb", "album")
    album_artist = _first_tag(tags, "TPE2", "aART", "albumartist", "album_artist")
    track_number = _normalize_index(_first_tag(tags, "TRCK", "trkn", "tracknumber"))
    disc_number = _normalize_index(_first_tag(tags, "TPOS", "disk", "discnumber"))
    recording_mbid = _first_tag(
        tags,
        "TXXX:MBID",
        "----:com.apple.iTunes:MBID",
        "musicbrainz_trackid",
        "musicbrainz_recordingid",
        "mbid",
    )
    release_mbid = _first_tag(
        tags,
        "TXXX:MUSICBRAINZ_RELEASEID",
        "----:com.apple.iTunes:MUSICBRAINZ_RELEASEID",
        "musicbrainz_releaseid",
    )
    isrc = _first_tag(
        tags,
        "TSRC",
        "----:com.apple.iTunes:ISRC",
        "isrc",
    )

    if not recording_mbid and not (title and artist):
        return None

    canonical_id = build_music_track_canonical_id(
        artist=artist or album_artist or "unknown-artist",
        album=album or "unknown-album",
        track_number=track_number,
        track=title or path.stem,
        recording_mbid=recording_mbid,
        mb_release_id=release_mbid,
        disc_number=disc_number,
    )
    return {
        "title": title or path.stem,
        "artist": artist or "",
        "album": album or "",
        "album_artist": album_artist or artist or "",
        "track_number": track_number,
        "disc_number": disc_number,
        "recording_mbid": recording_mbid,
        "mb_release_id": release_mbid,
        "isrc": isrc,
        "canonical_id": canonical_id,
    }


def _insert_reconciled_job(conn: sqlite3.Connection, path: Path, metadata: dict[str, Any]) -> bool:
    canonical_id = str(metadata.get("canonical_id") or "").strip()
    if not canonical_id:
        return False
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM download_jobs WHERE canonical_id=? LIMIT 1",
        (canonical_id,),
    )
    if cur.fetchone() is not None:
        return False

    now = utc_now()
    cur.execute(
        """
        INSERT INTO download_jobs (
            id, origin, origin_id, media_type, media_intent, source, url,
            input_url, canonical_url, external_id, status,
            queued, claimed, downloading, postprocessing, completed,
            failed, canceled, attempts, max_attempts, created_at, updated_at,
            last_error, trace_id, output_template, resolved_destination, canonical_id, file_path
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            uuid4().hex,
            "reconcile",
            str(metadata.get("recording_mbid") or path),
            "music",
            "music_track",
            "library_reconcile",
            str(path),
            str(path),
            None,
            str(metadata.get("recording_mbid") or metadata.get("isrc") or path.name),
            JOB_STATUS_COMPLETED,
            now,
            None,
            None,
            None,
            now,
            None,
            None,
            1,
            1,
            now,
            now,
            None,
            uuid4().hex,
            None,
            str(path.parent),
            canonical_id,
            str(path),
        ),
    )
    return True


def _insert_reconciled_history(conn: sqlite3.Connection, path: Path, metadata: dict[str, Any]) -> bool:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT 1
        FROM download_history
        WHERE status='completed' AND destination=? AND filename=?
        LIMIT 1
        """,
        (str(path.parent), path.name),
    )
    if cur.fetchone() is not None:
        return False
    now = utc_now()
    file_size_bytes = None
    try:
        file_size_bytes = int(path.stat().st_size)
    except OSError:
        file_size_bytes = None
    cur.execute(
        """
        INSERT INTO download_history (
            video_id, title, filename, destination, source, status,
            created_at, completed_at, file_size_bytes,
            input_url, canonical_url, external_id, channel_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(metadata.get("recording_mbid") or metadata.get("canonical_id") or path.name),
            str(metadata.get("title") or path.stem),
            path.name,
            str(path.parent),
            "library_reconcile",
            "completed",
            now,
            now,
            file_size_bytes,
            str(path),
            None,
            str(metadata.get("recording_mbid") or metadata.get("isrc") or path.name),
            None,
        ),
    )
    return True


def _insert_reconciled_isrc(conn: sqlite3.Connection, path: Path, isrc: str) -> bool:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT 1
        FROM downloaded_music_tracks
        WHERE isrc=?
        LIMIT 1
        """,
        (isrc,),
    )
    if cur.fetchone() is not None:
        return False
    cur.execute(
        """
        INSERT OR IGNORE INTO downloaded_music_tracks (playlist_id, isrc, file_path)
        VALUES (?, ?, ?)
        """,
        (_RECONCILE_PLAYLIST_ID, isrc, str(path)),
    )
    return True


def _first_tag(tags: Any, *keys: str) -> str | None:
    for key in keys:
        value = _lookup_tag(tags, key)
        if value:
            return value
    return None


def _lookup_tag(tags: Any, key: str) -> str | None:
    if tags is None:
        return None
    try:
        if key in tags:
            return _coerce_tag_value(tags[key])
    except Exception:
        pass
    lowered = key.lower()
    try:
        for existing_key in tags.keys():
            if str(existing_key).lower() == lowered:
                return _coerce_tag_value(tags[existing_key])
    except Exception:
        return None
    return None


def _coerce_tag_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        if not value:
            return None
        first = value[0]
        if isinstance(first, tuple):
            first = first[0]
        return _coerce_tag_value(first)
    text_attr = getattr(value, "text", None)
    if isinstance(text_attr, list) and text_attr:
        return _coerce_tag_value(text_attr[0])
    if isinstance(value, bytes):
        try:
            decoded = value.decode("utf-8", errors="ignore").strip()
        except Exception:
            return None
        return decoded or None
    text = str(value).strip()
    return text or None


def _normalize_index(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, tuple):
        value = value[0]
    text = str(value).strip()
    if "/" in text:
        text = text.split("/", 1)[0].strip()
    try:
        parsed = int(text)
    except Exception:
        return None
    return parsed if parsed > 0 else None


def _is_relative_to(path: Path, other: Path) -> bool:
    try:
        path.relative_to(other)
        return True
    except ValueError:
        return False

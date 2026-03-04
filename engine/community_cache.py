"""
Retreivr Community Cache Lookup

Provides a lightweight client for retrieving optional community transport
hints from the Retreivr community index hosted on GitHub.

The community cache is an **accelerator only**. It never overrides the
canonical deterministic resolver pipeline.

Lookup order (handled by caller):

MusicBrainz resolve
    ↓
Local acquisition cache
    ↓
Community cache (this module)
    ↓
Transport search ladder

If a community entry fails validation or download later, it must be
invalidated locally and the resolver should fall back to normal search.
"""

import json
import logging
import threading
import time
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any

import requests
import sqlite3


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

GITHUB_RAW_BASE = (
    "https://raw.githubusercontent.com/"
    "sudostacks/retreivr-community-cache/main/youtube/recording"
)

REQUEST_TIMEOUT = 0.8  # seconds


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _prefix_from_mbid(recording_mbid: str) -> str:
    """Return the prefix shard for a recording MBID."""
    return recording_mbid[0:2]


def _build_url(recording_mbid: str) -> str:
    """Build GitHub raw URL for a recording entry."""
    prefix = _prefix_from_mbid(recording_mbid)
    return f"{GITHUB_RAW_BASE}/{prefix}/{recording_mbid}.json"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def fetch_community_record(recording_mbid: str) -> Optional[Dict[str, Any]]:
    """
    Fetch a community cache entry from GitHub.

    Returns parsed JSON dict if present, otherwise None.
    """

    url = _build_url(recording_mbid)

    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT)

        if response.status_code == 404:
            logger.debug(
                "community_cache_miss recording_mbid=%s", recording_mbid
            )
            return None

        response.raise_for_status()

        data = response.json()

        logger.info(
            "community_cache_hit recording_mbid=%s", recording_mbid
        )

        return data

    except requests.RequestException as e:
        logger.debug(
            "community_cache_error recording_mbid=%s error=%s",
            recording_mbid,
            str(e),
        )

    except json.JSONDecodeError:
        logger.warning(
            "community_cache_invalid_json recording_mbid=%s",
            recording_mbid,
        )

    return None


# ---------------------------------------------------------------------------
# Candidate Extraction
# ---------------------------------------------------------------------------


def extract_best_candidate(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Extract the highest confidence candidate from a community record.

    Community entries may contain multiple sources.
    This function returns the highest confidence one.
    """

    sources = record.get("sources", [])

    if not sources:
        return None

    sources_sorted = sorted(
        sources,
        key=lambda s: s.get("confidence", 0),
        reverse=True,
    )

    best = sources_sorted[0]

    # Basic sanity checks
    if "video_id" not in best:
        return None

    return best


# ---------------------------------------------------------------------------
# High Level Helper
# ---------------------------------------------------------------------------


def lookup_recording(recording_mbid: str) -> Optional[Dict[str, Any]]:
    """
    High-level lookup helper.

    Returns candidate source metadata or None.

    Returned structure example:

    {
        "video_id": "abc123",
        "duration_ms": 242000,
        "confidence": 0.97
    }
    """

    record = fetch_community_record(recording_mbid)

    if not record:
        return None

    candidate = extract_best_candidate(record)

    if not candidate:
        logger.debug(
            "community_cache_no_candidate recording_mbid=%s",
            recording_mbid,
        )
        return None

    return candidate


# ---------------------------------------------------------------------------
# Optional: simple in-memory TTL cache
# ---------------------------------------------------------------------------


_CACHE: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
_CACHE_TTL = 3600
_CACHE_MAX_SIZE = 2048
_CACHE_LOCK = threading.RLock()
_IN_FLIGHT: Dict[str, threading.Event] = {}
_REVERSE_LOOKUP_CACHE: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
_REVERSE_LOOKUP_CACHE_TTL = 300
_REVERSE_LOOKUP_CACHE_MAX_SIZE = 4096
_REVERSE_LOOKUP_CACHE_LOCK = threading.RLock()


def cached_lookup(recording_mbid: str) -> Optional[Dict[str, Any]]:
    """
    Lookup with simple in-memory caching to avoid repeated GitHub hits.
    """

    mbid = str(recording_mbid or "").strip()
    if not mbid:
        return None

    fetch_event: threading.Event | None = None
    should_fetch = False

    while True:
        now = time.time()
        with _CACHE_LOCK:
            cached = _CACHE.get(mbid)
            if cached:
                if now - float(cached.get("ts") or 0.0) < float(_CACHE_TTL):
                    _CACHE.move_to_end(mbid)
                    return cached.get("data")
                _CACHE.pop(mbid, None)

            in_flight = _IN_FLIGHT.get(mbid)
            if in_flight is None:
                fetch_event = threading.Event()
                _IN_FLIGHT[mbid] = fetch_event
                should_fetch = True
                break

            fetch_event = in_flight

        # Another thread is already fetching this MBID; wait for completion
        # and then re-check the cache state.
        fetch_event.wait(timeout=REQUEST_TIMEOUT + 0.5)

    if not should_fetch:
        return None

    result: Optional[Dict[str, Any]] = None
    try:
        result = lookup_recording(mbid)
    finally:
        with _CACHE_LOCK:
            _CACHE[mbid] = {
                "ts": time.time(),
                "data": result,
            }
            _CACHE.move_to_end(mbid)
            while len(_CACHE) > int(_CACHE_MAX_SIZE):
                _CACHE.popitem(last=False)
            done_event = _IN_FLIGHT.pop(mbid, None)
            if done_event is not None:
                done_event.set()

    return result


def lookup_video_id(video_id: str, *, db_path: str | None = None) -> Optional[Dict[str, Any]]:
    """
    Resolve a local reverse index entry by YouTube video_id.

    This uses local SQLite state only and never performs network calls.
    Returns None when no reverse index exists or no match is present.
    """
    normalized = str(video_id or "").strip().lower()
    if not normalized:
        return None
    now = time.time()
    with _REVERSE_LOOKUP_CACHE_LOCK:
        cached = _REVERSE_LOOKUP_CACHE.get(normalized)
        if cached:
            cached_ts = float(cached.get("ts") or 0.0)
            if now - cached_ts < float(_REVERSE_LOOKUP_CACHE_TTL):
                _REVERSE_LOOKUP_CACHE.move_to_end(normalized)
                payload = cached.get("payload")
                return dict(payload) if isinstance(payload, dict) else None
            _REVERSE_LOOKUP_CACHE.pop(normalized, None)

    if not db_path:
        return None

    payload = None
    conn = None
    try:
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            """
            SELECT recording_mbid, confidence, updated_at
            FROM community_video_index
            WHERE video_id=?
            LIMIT 1
            """,
            (normalized,),
        )
        row = cur.fetchone()
        if row:
            payload = {
                "recording_mbid": row["recording_mbid"],
                "confidence": row["confidence"],
                "updated_at": row["updated_at"],
            }
    except sqlite3.OperationalError:
        payload = None
    except Exception:
        payload = None
    finally:
        if conn is not None:
            conn.close()

    with _REVERSE_LOOKUP_CACHE_LOCK:
        _REVERSE_LOOKUP_CACHE[normalized] = {
            "ts": time.time(),
            "payload": dict(payload) if isinstance(payload, dict) else None,
        }
        _REVERSE_LOOKUP_CACHE.move_to_end(normalized)
        while len(_REVERSE_LOOKUP_CACHE) > int(_REVERSE_LOOKUP_CACHE_MAX_SIZE):
            _REVERSE_LOOKUP_CACHE.popitem(last=False)

    return dict(payload) if isinstance(payload, dict) else None


def _as_sources(record: Dict[str, Any]) -> list[dict]:
    sources = record.get("sources")
    normalized = [dict(item) for item in (sources or []) if isinstance(item, dict)]
    if isinstance(record.get("video_id"), str):
        normalized.append(
            {
                "video_id": record.get("video_id"),
                "confidence": record.get("confidence"),
            }
        )
    return normalized


def _dataset_record_root(dataset_root: str | Path) -> Path:
    root = Path(dataset_root)
    if (root / "youtube" / "recording").is_dir():
        return root / "youtube" / "recording"
    if (root / "recording").is_dir():
        return root / "recording"
    return root


def rebuild_reverse_index_from_dataset(*, db_path: str, dataset_root: str | Path) -> dict[str, int]:
    """
    Rebuild local community_video_index deterministically from local dataset files.

    No network calls are performed here.
    """
    root = _dataset_record_root(dataset_root)
    if not root.exists() or not root.is_dir():
        conn = sqlite3.connect(db_path, check_same_thread=False)
        try:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS community_video_index (
                    video_id TEXT PRIMARY KEY,
                    recording_mbid TEXT,
                    confidence REAL,
                    updated_at TEXT
                )
                """
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_community_video_index_recording ON community_video_index (recording_mbid)")
            cur.execute("BEGIN IMMEDIATE")
            cur.execute("DELETE FROM community_video_index")
            conn.commit()
        finally:
            conn.close()
        with _REVERSE_LOOKUP_CACHE_LOCK:
            _REVERSE_LOOKUP_CACHE.clear()
        return {"files_scanned": 0, "video_ids_indexed": 0}

    mapping: dict[str, tuple[float, str]] = {}
    files_scanned = 0
    for record_path in sorted(root.glob("*/*.json")):
        files_scanned += 1
        recording_mbid = record_path.stem.strip().lower()
        if not recording_mbid:
            continue
        try:
            payload = json.loads(record_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        for source in _as_sources(payload):
            video_id = str(source.get("video_id") or "").strip().lower()
            if not video_id:
                continue
            try:
                confidence = float(source.get("confidence") or 0.0)
            except Exception:
                confidence = 0.0
            current = mapping.get(video_id)
            if current is None:
                mapping[video_id] = (confidence, recording_mbid)
                continue
            current_confidence, current_mbid = current
            if confidence > current_confidence:
                mapping[video_id] = (confidence, recording_mbid)
            elif confidence == current_confidence and recording_mbid < current_mbid:
                mapping[video_id] = (confidence, recording_mbid)

    now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    conn = sqlite3.connect(db_path, check_same_thread=False)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS community_video_index (
                video_id TEXT PRIMARY KEY,
                recording_mbid TEXT,
                confidence REAL,
                updated_at TEXT
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_community_video_index_recording ON community_video_index (recording_mbid)")
        cur.execute("BEGIN IMMEDIATE")
        cur.execute("DELETE FROM community_video_index")
        rows = [
            (video_id, recording_mbid, confidence, now_iso)
            for video_id, (confidence, recording_mbid) in sorted(mapping.items(), key=lambda item: item[0])
        ]
        cur.executemany(
            """
            INSERT INTO community_video_index (video_id, recording_mbid, confidence, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
    finally:
        conn.close()

    with _REVERSE_LOOKUP_CACHE_LOCK:
        _REVERSE_LOOKUP_CACHE.clear()

    return {"files_scanned": files_scanned, "video_ids_indexed": len(mapping)}

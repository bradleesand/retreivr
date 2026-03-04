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
import time
from typing import Optional, Dict, Any

import requests


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


_CACHE: Dict[str, Dict[str, Any]] = {}
_CACHE_TTL = 3600


def cached_lookup(recording_mbid: str) -> Optional[Dict[str, Any]]:
    """
    Lookup with simple in-memory caching to avoid repeated GitHub hits.
    """

    now = time.time()

    cached = _CACHE.get(recording_mbid)

    if cached:
        if now - cached["ts"] < _CACHE_TTL:
            return cached["data"]

    result = lookup_recording(recording_mbid)

    _CACHE[recording_mbid] = {
        "ts": now,
        "data": result,
    }

    return result

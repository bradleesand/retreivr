#!/usr/bin/env python3
"""Build Retreivr's MusicBrainz artist genre cache from dry-run CSV reports."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from metadata.genre_repair import (  # noqa: E402
    _ARTIST_GENRE_HINTS,
    _artist_hint_key,
    _artist_name_candidates,
    _load_musicbrainz_cache,
    _safe_lookup_musicbrainz_artist_genre,
    _save_musicbrainz_cache,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports", nargs="+", help="Genre dry-run CSV reports to mine for Unknown artists.")
    parser.add_argument("--cache", required=True, help="MusicBrainz cache JSON to read/write.")
    parser.add_argument("--limit", type=int, default=250, help="Maximum new artist lookups.")
    parser.add_argument("--min-tracks", type=int, default=2, help="Only query artists with at least this many Unknown tracks.")
    parser.add_argument("--save-every", type=int, default=25, help="Save cache every N new lookups.")
    parser.add_argument("--summary", help="Optional JSON summary output path.")
    args = parser.parse_args()

    cache = _load_musicbrainz_cache(args.cache)
    artists = _unknown_artists_from_reports([Path(path) for path in args.reports])
    candidates = [
        (artist, count)
        for artist, count in artists.most_common()
        if count >= args.min_tracks and _usable_artist(artist)
    ]

    looked_up = enriched = skipped_cached = skipped_hint = 0
    errors: list[dict[str, str]] = []
    for artist, count in candidates:
        if looked_up >= args.limit:
            break
        artist_candidates = [candidate for candidate in _artist_name_candidates(artist) if _usable_artist(candidate)]
        if not artist_candidates:
            continue
        key = _artist_cache_key(artist_candidates[0])
        hint = next(
            (
                _ARTIST_GENRE_HINTS[_artist_hint_key(candidate)]
                for candidate in artist_candidates
                if _artist_hint_key(candidate) in _ARTIST_GENRE_HINTS
            ),
            None,
        )
        if hint:
            cached = cache.get(key) if isinstance(cache.get(key), dict) else {}
            if not cached.get("genre"):
                cache[key] = {"genre": hint, "artist": artist_candidates[0], "source": "artist_hint", "unknown_count": count}
                enriched += 1
            else:
                skipped_cached += 1
            skipped_hint += 1
            continue

        cached_genre = _cached_genre(cache, artist_candidates)
        if cached_genre:
            skipped_cached += 1
            continue

        lookup_artist = _first_uncached_artist(cache, artist_candidates)
        if lookup_artist is None:
            skipped_cached += 1
            continue
        key = _artist_cache_key(lookup_artist)
        try:
            genre = _safe_lookup_musicbrainz_artist_genre(lookup_artist)
            looked_up += 1
            cache[key] = {"genre": genre, "artist": lookup_artist, "source": "musicbrainz_artist", "unknown_count": count}
            if genre:
                enriched += 1
        except Exception as exc:  # pragma: no cover - defensive; safe lookup should swallow.
            looked_up += 1
            cache[key] = {"genre": None, "artist": lookup_artist, "source": "musicbrainz_artist", "unknown_count": count}
            errors.append({"artist": artist, "error": str(exc)})
        if looked_up and looked_up % max(1, args.save_every) == 0:
            _save_musicbrainz_cache(args.cache, cache)
            print(f"looked_up={looked_up} enriched={enriched} artist={artist}", flush=True)

    _save_musicbrainz_cache(args.cache, cache)
    summary = {
        "artists_in_reports": len(artists),
        "candidates": len(candidates),
        "looked_up": looked_up,
        "enriched": enriched,
        "skipped_cached": skipped_cached,
        "skipped_hint": skipped_hint,
        "errors": errors[:25],
        "cache_entries": len(cache),
        "cache_with_genre": sum(1 for value in cache.values() if isinstance(value, dict) and value.get("genre")),
    }
    if args.summary:
        Path(args.summary).write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def _unknown_artists_from_reports(paths: list[Path]) -> Counter[str]:
    artists: Counter[str] = Counter()
    for path in paths:
        if not path.exists():
            continue
        with path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                if row.get("new_genre") != "Unknown":
                    continue
                artist = _artist_from_path(row.get("path") or "")
                if artist:
                    artists[artist] += 1
    return artists


def _artist_from_path(path: str) -> str | None:
    parts = str(path or "").split("/")
    if len(parts) < 3:
        return None
    artist = parts[-3].strip()
    return artist or None


def _artist_cache_key(artist: str) -> str:
    return "|".join(["artist-v2", _artist_hint_key(artist)])


def _cached_genre(cache: dict[str, object], artists: list[str]) -> str | None:
    for artist in artists:
        cached = cache.get(_artist_cache_key(artist)) or cache.get("|".join(["artist-v2", artist.casefold()]))
        if isinstance(cached, dict) and cached.get("genre"):
            return str(cached["genre"])
    return None


def _first_uncached_artist(cache: dict[str, object], artists: list[str]) -> str | None:
    for artist in artists:
        key = _artist_cache_key(artist)
        legacy_key = "|".join(["artist-v2", artist.casefold()])
        if key not in cache and legacy_key not in cache:
            return artist
    return None


def _usable_artist(artist: str) -> bool:
    key = artist.strip().casefold()
    return bool(key) and key not in {"music", "unknown artist", "unknown", "various artists", "school"}


if __name__ == "__main__":
    raise SystemExit(main())

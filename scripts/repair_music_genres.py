#!/usr/bin/env python3
"""Normalize embedded music genre tags with a dry-run report by default."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from metadata.genre_repair import repair_music_genres


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roots", nargs="+", help="Music library roots to scan.")
    parser.add_argument("--apply", action="store_true", help="Write genre tag changes in place.")
    parser.add_argument("--default-missing-genre", default="Unknown", help="Genre to write when no genre is present or mapped.")
    parser.add_argument("--output", help="Optional CSV or JSON report path.")
    parser.add_argument("--limit", type=int, help="Maximum number of audio files to scan.")
    parser.add_argument("--progress-every", type=int, default=250, help="Print progress every N scanned audio files.")
    parser.add_argument("--musicbrainz-enrich", action="store_true", help="Use MusicBrainz to enrich files that would otherwise become Unknown.")
    parser.add_argument("--musicbrainz-cache", help="Persistent JSON cache for MusicBrainz enrichment lookups.")
    parser.add_argument("--musicbrainz-limit", type=int, help="Maximum number of new MusicBrainz lookups for this run.")
    args = parser.parse_args()

    def progress(scanned: int, path) -> None:
        print(f"scanned={scanned} path={path}", flush=True)

    summary = repair_music_genres(
        args.roots,
        dry_run=not args.apply,
        default_missing_genre=args.default_missing_genre,
        output_path=args.output,
        limit=args.limit,
        progress=progress if args.progress_every > 0 else None,
        progress_every=args.progress_every,
        musicbrainz_enrich=args.musicbrainz_enrich,
        musicbrainz_cache_path=args.musicbrainz_cache,
        musicbrainz_limit=args.musicbrainz_limit,
    )
    printable = {key: value for key, value in summary.items() if key != "items"}
    print(json.dumps(printable, indent=2, sort_keys=True))
    return 0 if int(summary.get("failed") or 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

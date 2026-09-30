"""Dry-run/apply genre normalization over existing music files."""

from __future__ import annotations

import csv
import json
import os
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable

import requests

from metadata.genre_policy import canonicalize_genre
from metadata.tagger import apply_tags, read_music_tags

AUDIO_EXTENSIONS = {".mp3", ".m4a", ".mp4", ".m4b", ".flac", ".ogg", ".opus", ".wav", ".aac"}
_TRACK_PREFIX_RE = re.compile(r"^\s*(?:\d{1,3})(?:[-._ )]+|\s*/\s*\d{1,3}\s*)")
_MB_HEADERS = {"User-Agent": "Retreivr/1.0 (+https://github.com/retreivr/retreivr)"}
_LAST_MB_REQUEST = 0.0
_ARTIST_GENRE_HINTS = {
    "alabama": "Country",
    "al denson": "Christian",
    "amy grant": "Christian",
    "anointed": "Christian",
    "anthem lights": "Christian",
    "anne wilson": "Christian",
    "awana": "Christian",
    "avalon": "Christian",
    "billy currington": "Country",
    "big daddy weave": "Christian",
    "brandon heath": "Christian",
    "brandon lake": "Christian",
    "brantley gilbert": "Country",
    "brett eldredge": "Country",
    "brett young": "Country",
    "brooks & dunn": "Country",
    "brothers osborne": "Country",
    "bryan duncan": "Christian",
    "bruce carroll": "Christian",
    "caleb and kelsey": "Christian",
    "carrie underwood": "Country",
    "casting crowns": "Christian",
    "chris young": "Country",
    "chris cagle": "Country",
    "chris rice": "Christian",
    "chris stapleton": "Country",
    "chris tomlin": "Christian",
    "cindy morgan": "Christian",
    "clay crosse": "Christian",
    "clint black": "Country",
    "cole swindell": "Country",
    "colton dixon": "Christian",
    "collin raye": "Country",
    "craig morgan": "Country",
    "crowder": "Christian",
    "dan + shay": "Country",
    "dan seals": "Country",
    "danny gokey": "Christian",
    "david meece": "Christian",
    "dc talk": "Christian",
    "diamond rio": "Country",
    "dierks bentley": "Country",
    "dolly parton": "Country",
    "don williams": "Country",
    "doug stone": "Country",
    "dustin lynch": "Country",
    "dwight yoakam": "Country",
    "dylan scott": "Country",
    "easton corbin": "Country",
    "earl thomas conley": "Country",
    "eddy raven": "Country",
    "elevation worship": "Christian",
    "ellie holcomb": "Christian",
    "exile": "Country",
    "faith hill": "Country",
    "ffh": "Christian",
    "fisher-price": "Pop",
    "florida georgia line": "Country",
    "foo fighters": "Rock",
    "forrest frank": "Christian",
    "for king & country": "Christian",
    "francesca battistelli": "Christian",
    "garth brooks": "Country",
    "george strait": "Country",
    "geoff moore & the distance": "Christian",
    "greg long": "Christian",
    "jaci velasquez": "Christian",
    "jake owen": "Country",
    "jeremy camp": "Christian",
    "jo dee messina": "Country",
    "joe diffie": "Country",
    "john berry": "Country",
    "john anderson": "Country",
    "john denver": "Country",
    "john michael montgomery": "Country",
    "jon pardi": "Country",
    "jordan davis": "Country",
    "josiah queen": "Christian",
    "jordan feliz": "Christian",
    "kane brown": "Country",
    "kanye west": "Hip-Hop/Rap",
    "kathy mattea": "Country",
    "kathy troccoli": "Christian",
    "keith urban": "Country",
    "kelsea ballerini": "Country",
    "kip moore": "Country",
    "lady antebellum": "Country",
    "lauren daigle": "Christian",
    "leann rimes": "Country",
    "lee brice": "Country",
    "lee ann womack": "Country",
    "led zeppelin": "Rock",
    "little big town": "Country",
    "lonestar": "Country",
    "lorrie Morgan": "Country",
    "lorrie morgan": "Country",
    "luke combs": "Country",
    "margaret becker": "Christian",
    "mark chesnutt": "Country",
    "mark schultz": "Christian",
    "mark wills": "Country",
    "martina mcbride": "Country",
    "matthew west": "Christian",
    "matt maher": "Christian",
    "megan moroney": "Country",
    "mercyme": "Christian",
    "metallica": "Metal",
    "michael w. smith": "Christian",
    "micah tyler": "Christian",
    "michael card": "Christian",
    "michael english": "Christian",
    "montgomery gentry": "Country",
    "morgan wallen": "Country",
    "natalie grant": "Christian",
    "needtobreathe": "Christian",
    "nichole nordeman": "Christian",
    "newsboys": "Christian",
    "newsong": "Christian",
    "nirvana": "Rock",
    "old dominion": "Country",
    "out of the grey": "Christian",
    "pam tillis": "Country",
    "patty loveless": "Country",
    "phil wickham": "Christian",
    "phil vassar": "Country",
    "phillips, craig & dean": "Christian",
    "point of grace": "Christian",
    "queen": "Rock",
    "pink floyd": "Rock",
    "randy houser": "Country",
    "randall king": "Country",
    "randy travis": "Country",
    "rascal flatts": "Country",
    "reba mcentire": "Country",
    "reba": "Country",
    "rend collective": "Christian",
    "relient k": "Christian",
    "rich mullins": "Christian",
    "ricky skaggs": "Bluegrass",
    "ricky van shelton": "Country",
    "ronnie milsap": "Country",
    "rodney atkins": "Country",
    "russell dickerson": "Country",
    "riley green": "Country",
    "ryan stevenson": "Christian",
    "sanctus real": "Christian",
    "sam hunt": "Country",
    "sara evans": "Country",
    "sawyer brown": "Country",
    "scotty mccreery": "Country",
    "sidewalk prophets": "Christian",
    "skillet": "Christian",
    "shania twain": "Country",
    "shenandoah": "Country",
    "steve green": "Christian",
    "steven curtis chapman": "Christian",
    "steve wariner": "Country",
    "st. john's children's choir": "Christian",
    "sugarland": "Country",
    "susan ashton": "Christian",
    "tanya tucker": "Country",
    "tauren wells": "Christian",
    "taylor swift": "Pop",
    "tenth avenue north": "Christian",
    "terri clark": "Country",
    "the dillards": "Bluegrass",
    "the forester sisters": "Country",
    "the judds": "Country",
    "the oak ridge boys": "Country",
    "the praise baby collection": "Christian",
    "the steel woods": "Country",
    "third day": "Christian",
    "thomas rhett": "Country",
    "tim mcgraw": "Country",
    "tobymac": "Christian",
    "trace adkins": "Country",
    "tracy byrd": "Country",
    "tracy lawrence": "Country",
    "travis tritt": "Country",
    "trisha yearwood": "Country",
    "twila paris": "Christian",
    "unspoken": "Christian",
    "veggietales": "Christian",
    "vince gill": "Country",
    "wayne watson": "Christian",
    "we are messengers": "Christian",
    "wes king": "Christian",
    "willie nelson": "Country",
    "wynonna": "Country",
    "zach bryan": "Country",
    "zach williams": "Christian",
}
_ARTIST_GENRE_HINTS.update(
    {
        "7eventh time down": "Christian",
        "andrew ripp": "Christian",
        "austin french": "Christian",
        "bebe & cece winans": "Gospel",
        "bill monroe and his bluegrass boys": "Bluegrass",
        "billy joe royal": "Country",
        "billy sprague": "Christian",
        "carolyn arends": "Christian",
        "cece winans": "Gospel",
        "citizen way": "Christian",
        "cochren & co": "Christian",
        "cory asbury": "Christian",
        "dan bremnes": "Christian",
        "david & the giants": "Christian",
        "david crowder band": "Christian",
        "david dunn": "Christian",
        "david nail": "Country",
        "east to west": "Christian",
        "flatt & scruggs": "Bluegrass",
        "for king + country": "Christian",
        "gary chapman": "Christian",
        "guns n' roses": "Rock",
        "hawk nelson": "Christian",
        "high valley": "Country",
        "i am they": "Christian",
        "jars of clay": "Christian",
        "jon reddick": "Christian",
        "jonathan pierce": "Christian",
        "jonny diaz": "Christian",
        "josh baldwin": "Christian",
        "josh wilson": "Christian",
        "joy williams": "Christian",
        "kutless": "Christian",
        "leanna crawford": "Christian",
        "lenny leblanc": "Christian",
        "lincoln brewster": "Christian",
        "linkin park": "Rock",
        "lionel cartwright": "Country",
        "listener kids": "Christian",
        "lisa bevill": "Christian",
        "love & the outcome": "Christian",
        "michael o'brien": "Christian",
        "michael ray": "Country",
        "michelle tumes": "Christian",
        "mikeschair": "Christian",
        "mylon & broken heart": "Christian",
        "nate smith": "Country",
        "phil keaggy": "Christian",
        "phillip sandifer": "Christian",
        "pickin' on series": "Bluegrass",
        "plus one": "Christian",
        "red hot chili peppers": "Rock",
        "rhett walker": "Christian",
        "sonicflood": "Christian",
        "stars go dim": "Christian",
        "stephen stanley": "Christian",
        "tasha layton": "Christian",
        "the desert rose band": "Country",
        "the steeldrivers": "Bluegrass",
        "tim mcgraw & faith hill": "Country",
        "tyler hubbard": "Country",
        "watermark": "Christian",
    }
)
_ARTIST_GENRE_HINTS.update(
    {
        "33miles": "Christian",
        "among the thirsty": "Christian",
        "ashton, becker & dente": "Christian",
        "ben fuller": "Christian",
        "bethany dillon": "Christian",
        "bethel music & jenn johnson": "Christian",
        "blake shelton": "Country",
        "brent bourgeois": "Christian",
        "brooke simpson": "Country",
        "brother's keeper": "Christian",
        "cameron whitcomb": "Country",
        "chris august": "Christian",
        "cody carnes": "Christian",
        "dana key": "Christian",
        "david frizzell & shelly west": "Country",
        "david kersh": "Country",
        "dillon carmichael": "Country",
        "disturbed": "Metal",
        "dixie chicks": "Country",
        "drake white": "Country",
        "drew parker": "Country",
        "dylan gossett": "Country",
        "eagles": "Rock",
        "elevation rhythm": "Christian",
        "erin o'donnell": "Christian",
        "faith hill & tim mcgraw": "Country",
        "finding favour": "Christian",
        "george birge": "Country",
        "greg x volz": "Christian",
        "hillary scott & the scott family": "Christian",
        "hollyn": "Christian",
        "hope darst": "Christian",
        "james wesley": "Country",
        "jameson rodgers": "Country",
        "jo-el sonnier": "Country",
        "john schneider": "Country",
        "jon gibson": "Christian",
        "josh ward": "Country",
        "julie miller": "Christian",
        "kenny chesney & uncle kracker": "Country",
        "kevin sharp": "Country",
        "lady a": "Country",
        "mack brock": "Christian",
        "matt stell": "Country",
        "maverick city music": "Christian",
        "maverick city music featuring joe l. barnes & naomi raine": "Christian",
        "megan woods": "Christian",
        "morgan cryar": "Christian",
        "morgan evans": "Country",
        "mylon lefevre & friends": "Christian",
        "niko moon": "Country",
        "nikki leonti": "Christian",
        "oasis": "Rock",
        "ole 60": "Country",
        "pam thum": "Christian",
        "patty cabrera": "Christian",
        "peter furler": "Christian",
        "prince & the new power generation": "R&B/Soul",
        "punch brothers": "Bluegrass",
        "r.e.m": "Rock",
        "rachel rachel": "Christian",
        "rhett akins": "Country",
        "rich mullins & a ragamuffin band": "Christian",
        "ronnie dunn": "Country",
        "sara groves": "Christian",
        "seph schlueter": "Christian",
        "shane & shane": "Christian",
        "slash": "Rock",
        "southern pacific": "Country",
        "staind": "Rock",
        "sweethearts of the rodeo": "Country",
        "take 6": "Gospel",
        "tammy cochran": "Country",
        "tammy trent": "Christian",
        "terrian": "Christian",
        "the countdown kids": "Pop",
        "the cox family": "Bluegrass",
        "the five stairsteps": "R&B/Soul",
        "the red clay strays": "Country",
        "the stanley brothers & the clinch mountain boys": "Bluegrass",
        "the supremes": "R&B/Soul",
        "the wilkinsons": "Country",
        "thomas & friends": "Pop",
        "toto": "Rock",
        "trace balin": "Christian",
        "warren zeiders": "Country",
        "zach john king": "Country",
    }
)
_ARTIST_GENRE_HINTS.update(
    {
        "aaron benward": "Christian",
        "aaron jeoffrey": "Christian",
        "across the sky": "Christian",
        "alive city": "Christian",
        "amy morriss": "Christian",
        "andy cherry": "Christian",
        "andy griggs": "Country",
        "ashes remain": "Christian",
        "ashton shepherd": "Country",
        "bad livers": "Bluegrass",
        "baillie and the boys": "Country",
        "band of silver": "Rock",
        "bob bennett": "Christian",
        "boy howdy": "Country",
        "brian barrett": "Christian",
        "brooke ligertwood": "Christian",
        "brother phelps": "Country",
        "buck owens & his buckaroos": "Country",
        "by the tree": "Christian",
        "byron berline": "Bluegrass",
        "capital kings": "Christian",
        "carl story": "Bluegrass",
        "casey james": "Country",
        "chandler moore": "Christian",
        "charlie worsham": "Country",
        "chase bryant": "Country",
        "chasen": "Christian",
        "chayce beckham": "Country",
        "chris eaton": "Christian",
        "christy nockels": "Christian",
        "chuck wicks": "Country",
        "clay davidson": "Country",
        "commissioned": "Gospel",
        "confederate railroad": "Country",
        "dante bowe": "Christian",
        "darlene zschech": "Christian",
        "david mullen": "Christian",
        "decemberadio": "Christian",
        "dylan marlowe & dylan scott": "Country",
        "earl scruggs": "Bluegrass",
        "eastview worship": "Christian",
        "elvie shane": "Country",
        "emerson day": "Christian",
        "emily ann roberts": "Country",
        "evvie mckinney": "Christian",
        "fee": "Christian",
        "fernando ortega": "Christian",
        "harry mcclintock": "Folk",
        "hudson westbrook": "Country",
        "jamie grace": "Christian",
        "jamie macdonald": "Christian",
        "jana kramer": "Country",
        "lanco": "Country",
        "michael james": "Christian",
        "pink limit": "Pop",
        "scott krippayne": "Christian",
        "true vibe": "Christian",
        "ty myers": "Country",
        "winans": "Gospel",
        "yankee grey": "Country",
    }
)


def repair_music_genres(
    roots: list[str | Path],
    *,
    dry_run: bool = True,
    default_missing_genre: str = "Unknown",
    output_path: str | Path | None = None,
    limit: int | None = None,
    progress: Callable[[int, Path], None] | None = None,
    progress_every: int = 0,
    musicbrainz_enrich: bool = False,
    musicbrainz_cache_path: str | Path | None = None,
    musicbrainz_limit: int | None = None,
) -> dict[str, Any]:
    scanned = changed = missing = unchanged = failed = 0
    actions: list[dict[str, Any]] = []
    genre_counts: Counter[str] = Counter()
    records: list[dict[str, Any]] = []
    artist_genres: dict[str, Counter[str]] = defaultdict(Counter)
    mb_cache = _load_musicbrainz_cache(musicbrainz_cache_path)
    mb_lookups = 0
    mb_enriched = 0
    mb_attempts = 0

    for path in _iter_audio_files([Path(root).expanduser() for root in roots]):
        if limit is not None and scanned >= limit:
            break
        scanned += 1
        if progress and progress_every > 0 and scanned % progress_every == 0:
            progress(scanned, path)
        try:
            existing = read_music_tags(str(path))
            old_genre = str(existing.get("genre") or "").strip()
            if not old_genre:
                missing += 1
            new_genre = canonicalize_genre(old_genre, default=None) if old_genre else None
            artist_key = _artist_key_for_path(path)
            if new_genre and new_genre != default_missing_genre and artist_key:
                artist_genres[artist_key][new_genre] += 1
            records.append(
                {
                    "path": path,
                    "existing": existing,
                    "old_genre": old_genre,
                    "new_genre": new_genre,
                    "artist_key": artist_key,
                    "context": _metadata_context(path, existing),
                }
            )
        except Exception as exc:
            failed += 1
            actions.append(
                {
                    "path": str(path),
                    "status": "failed",
                    "reason": str(exc),
                    "old_genre": None,
                    "new_genre": None,
                }
            )

    for record in records:
        path = record["path"]
        existing = record["existing"]
        old_genre = record["old_genre"]
        new_genre = record["new_genre"]
        try:
            reason = "normalized"
            if not old_genre:
                inferred = _artist_consensus_genre(artist_genres, record.get("artist_key"))
                if inferred:
                    new_genre = inferred
                    reason = "missing_artist_consensus"
                elif _heuristic_genre_for_record(record):
                    new_genre = _heuristic_genre_for_record(record)
                    reason = "missing_heuristic"
                elif _artist_hint_genre_for_record(record):
                    new_genre = _artist_hint_genre_for_record(record)
                    reason = "missing_artist_hint"
                elif musicbrainz_enrich:
                    mb_attempts += 1
                    _progress_enrichment(progress, progress_every, mb_attempts, record)
                    enriched, looked_up = _musicbrainz_genre_for_record(
                        record,
                        mb_cache,
                        allow_new_lookup=_within_mb_limit(mb_lookups, musicbrainz_limit),
                    )
                    mb_lookups += int(looked_up)
                    if looked_up and mb_lookups % 25 == 0:
                        _save_musicbrainz_cache(musicbrainz_cache_path, mb_cache)
                    if enriched:
                        new_genre = enriched
                        mb_enriched += 1
                        reason = "missing_musicbrainz"
                    else:
                        new_genre = default_missing_genre
                        reason = "missing_default"
                else:
                    new_genre = default_missing_genre
                    reason = "missing_default"
            elif new_genre is None:
                heuristic = _heuristic_genre_for_record(record)
                if heuristic:
                    new_genre = heuristic
                    reason = "unmapped_heuristic"
                elif _artist_hint_genre_for_record(record):
                    new_genre = _artist_hint_genre_for_record(record)
                    reason = "unmapped_artist_hint"
                elif musicbrainz_enrich:
                    mb_attempts += 1
                    _progress_enrichment(progress, progress_every, mb_attempts, record)
                    enriched, looked_up = _musicbrainz_genre_for_record(
                        record,
                        mb_cache,
                        allow_new_lookup=_within_mb_limit(mb_lookups, musicbrainz_limit),
                    )
                    mb_lookups += int(looked_up)
                    if looked_up and mb_lookups % 25 == 0:
                        _save_musicbrainz_cache(musicbrainz_cache_path, mb_cache)
                    if enriched:
                        new_genre = enriched
                        mb_enriched += 1
                        reason = "unmapped_musicbrainz"
                    else:
                        new_genre = default_missing_genre
                        reason = "unmapped_default"
                else:
                    new_genre = default_missing_genre
                    reason = "unmapped_default"

            if old_genre == new_genre:
                unchanged += 1
                status = "unchanged"
            else:
                changed += 1
                status = "would_change" if dry_run else "changed"
                if not dry_run:
                    tags = _preserve_existing_tags(existing)
                    tags["genre"] = new_genre
                    apply_tags(str(path), tags, artwork=None, allow_overwrite=True, dry_run=False)

            genre_counts[str(new_genre)] += 1
            actions.append(
                {
                    "path": str(path),
                    "status": status,
                    "reason": reason,
                    "old_genre": old_genre or None,
                    "new_genre": new_genre,
                }
            )
        except Exception as exc:
            failed += 1
            actions.append(
                {
                    "path": str(path),
                    "status": "failed",
                    "reason": str(exc),
                    "old_genre": None,
                    "new_genre": None,
                }
            )

    summary = {
        "dry_run": dry_run,
        "scanned": scanned,
        "changed": changed,
        "missing": missing,
        "unchanged": unchanged,
        "failed": failed,
        "musicbrainz_enrich": musicbrainz_enrich,
        "musicbrainz_attempts": mb_attempts,
        "musicbrainz_lookups": mb_lookups,
        "musicbrainz_enriched": mb_enriched,
        "genre_counts": dict(sorted(genre_counts.items())),
        "items": actions,
    }
    _save_musicbrainz_cache(musicbrainz_cache_path, mb_cache)
    if output_path:
        _write_report(Path(output_path), actions)
    return summary


def _artist_consensus_genre(artist_genres: dict[str, Counter[str]], artist_key: Any) -> str | None:
    if not artist_key:
        return None
    counts = artist_genres.get(str(artist_key))
    if not counts:
        return None
    genre, count = counts.most_common(1)[0]
    total = sum(counts.values())
    if count < 2 and total < 3:
        return None
    return genre


def _artist_key_for_path(path: Path) -> str | None:
    parts = path.parts
    if len(parts) < 3:
        return None
    artist = parts[-3]
    if artist in {"Music", "Audio Clips", "School"}:
        return None
    return artist.casefold()


def _within_mb_limit(current: int, limit: int | None) -> bool:
    return limit is None or current < int(limit)


def _metadata_context(path: Path, existing: dict[str, Any]) -> dict[str, str]:
    artist = str(existing.get("artist") or "").strip()
    album = str(existing.get("album") or "").strip()
    title = str(existing.get("title") or "").strip()
    if not artist and len(path.parts) >= 3:
        artist = path.parts[-3]
    if not album and len(path.parts) >= 2:
        album = path.parts[-2]
    if not title:
        title = _clean_path_title(path.stem)
    return {"artist": artist, "album": album, "title": title}


def _clean_path_title(value: str) -> str:
    text = _TRACK_PREFIX_RE.sub("", str(value or "")).strip()
    return text or str(value or "").strip()


def _load_musicbrainz_cache(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {}
    cache_path = Path(path)
    if not cache_path.exists():
        return {}
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _save_musicbrainz_cache(path: str | Path | None, cache: dict[str, Any]) -> None:
    if not path:
        return
    cache_path = Path(path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, indent=2, sort_keys=True), encoding="utf-8")


def _musicbrainz_genre_for_record(
    record: dict[str, Any],
    cache: dict[str, Any],
    *,
    allow_new_lookup: bool = True,
) -> tuple[str | None, bool]:
    context = record.get("context") if isinstance(record.get("context"), dict) else {}
    artist = str(context.get("artist") or "").strip()
    album = str(context.get("album") or "").strip()
    title = str(context.get("title") or "").strip()
    artists = _artist_candidates_for_record(record)
    if not artists:
        return None, False

    for candidate in artists:
        hinted = _ARTIST_GENRE_HINTS.get(_artist_hint_key(candidate))
        if hinted:
            return hinted, False

    for candidate in artists:
        artist_key = "|".join(["artist-v2", _artist_hint_key(candidate)])
        legacy_artist_key = "|".join(["artist-v2", candidate.casefold()])
        cached_artist = cache.get(artist_key) or cache.get(legacy_artist_key)
        if isinstance(cached_artist, dict):
            genre = cached_artist.get("genre")
            if genre:
                return genre, False

    artist = artists[0]
    artist_key = "|".join(["artist-v2", _artist_hint_key(artist)])
    legacy_artist_key = "|".join(["artist-v2", artist.casefold()])
    if _usable_artist_for_musicbrainz(artist):
        cached_artist = cache.get(artist_key) or cache.get(legacy_artist_key)
        if isinstance(cached_artist, dict):
            genre = cached_artist.get("genre")
            if genre:
                return genre, False
        else:
            if not allow_new_lookup:
                return None, False
            genre = _safe_lookup_musicbrainz_artist_genre(artist)
            cache[artist_key] = {"genre": genre, "artist": artist}
            if genre:
                return genre, True
    album_known = bool(album and album.casefold() not in {"unknown album", "unknown", "none"})
    if album_known:
        album_key = "|".join(["album", artist.casefold(), album.casefold()])
        cached = cache.get(album_key)
        if isinstance(cached, dict):
            genre = cached.get("genre")
            if genre:
                return genre, False
        else:
            if not allow_new_lookup:
                return None, False
            genre = _safe_lookup_musicbrainz_genre(artist=artist, album=album, title="")
            cache[album_key] = {"genre": genre, "artist": artist, "album": album}
            if genre:
                return genre, True
    cache_key = "|".join([artist.casefold(), album.casefold(), title.casefold()])
    cached = cache.get(cache_key)
    if isinstance(cached, dict):
        return cached.get("genre"), False
    if not allow_new_lookup:
        return None, False

    genre = _safe_lookup_musicbrainz_genre(artist=artist, album=album, title=title)
    looked_up = True
    if not genre:
        cached_artist = cache.get(artist_key)
        if isinstance(cached_artist, dict):
            genre = cached_artist.get("genre")
            looked_up = False
        elif _usable_artist_for_musicbrainz(artist):
            genre = _safe_lookup_musicbrainz_artist_genre(artist)
            cache[artist_key] = {"genre": genre, "artist": artist}
    cache[cache_key] = {"genre": genre, "artist": artist, "album": album, "title": title}
    return genre, looked_up


def _usable_artist_for_musicbrainz(artist: str) -> bool:
    text = artist.strip().casefold()
    return bool(text) and text not in {"music", "unknown artist", "unknown", "various artists", "logan mikesell"}


def _safe_lookup_musicbrainz_genre(*, artist: str, album: str, title: str) -> str | None:
    try:
        return _lookup_musicbrainz_genre(artist=artist, album=album, title=title)
    except Exception:
        return None


def _safe_lookup_musicbrainz_artist_genre(artist: str) -> str | None:
    try:
        return _lookup_musicbrainz_artist_genre(artist)
    except Exception:
        return None


def _lookup_musicbrainz_genre(*, artist: str, album: str, title: str) -> str | None:
    candidates: list[Any] = []
    if album and album.casefold() not in {"unknown album", "unknown"}:
        try:
            payload = _mb_get(
                "release",
                {"query": f'artist:"{artist}" AND release:"{album}"', "limit": 1},
            )
            releases = payload.get("releases") if isinstance(payload, dict) else []
            if isinstance(releases, list):
                for release in releases[:1]:
                    candidates.append(release)
        except Exception:
            pass
    if title:
        try:
            query = f'artist:"{artist}" AND recording:"{title}"'
            if album:
                query += f' AND release:"{album}"'
            payload = _mb_get("recording", {"query": query, "limit": 1})
            recordings = payload.get("recordings") if isinstance(payload, dict) else []
            if isinstance(recordings, list):
                for recording in recordings[:1]:
                    candidates.append(recording)
                    for release in recording.get("releases", []) if isinstance(recording, dict) else []:
                        candidates.append(release)
        except Exception:
            pass
    genre = _best_genre_from_musicbrainz_candidates(candidates)
    if genre:
        return genre
    try:
        payload = _mb_get("artist", {"query": f'artist:"{artist}"', "limit": 1})
        artists = payload.get("artists") if isinstance(payload, dict) else []
        if isinstance(artists, list):
            candidates.extend(artists[:1])
    except Exception:
        pass
    return _best_genre_from_musicbrainz_candidates(candidates)


def _lookup_musicbrainz_artist_genre(artist: str) -> str | None:
    candidates: list[Any] = []
    payload = _mb_get("artist", {"query": f'artist:"{artist}"', "limit": 1})
    artists = payload.get("artists") if isinstance(payload, dict) else []
    if isinstance(artists, list):
        candidates.extend(artists[:1])
    return _best_genre_from_musicbrainz_candidates(candidates)


def _progress_enrichment(
    progress: Callable[[int, Path], None] | None,
    progress_every: int,
    attempts: int,
    record: dict[str, Any],
) -> None:
    if not progress or progress_every <= 0 or attempts % progress_every != 0:
        return
    path = record.get("path")
    progress(attempts, Path(str(path or "<musicbrainz-enrichment>")))


def _mb_get(endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
    global _LAST_MB_REQUEST
    now = time.monotonic()
    wait_for = 1.05 - (now - _LAST_MB_REQUEST)
    if wait_for > 0:
        time.sleep(wait_for)
    query = dict(params)
    query["fmt"] = "json"
    response = requests.get(
        f"https://musicbrainz.org/ws/2/{endpoint}",
        params=query,
        headers=_MB_HEADERS,
        timeout=6,
    )
    _LAST_MB_REQUEST = time.monotonic()
    response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, dict) else {}


def _heuristic_genre_for_record(record: dict[str, Any]) -> str | None:
    context = record.get("context") if isinstance(record.get("context"), dict) else {}
    path = str(record.get("path") or "")
    haystack = " ".join(
        [
            path,
            str(context.get("artist") or ""),
            str(context.get("album") or ""),
            str(context.get("title") or ""),
            str(record.get("old_genre") or ""),
        ]
    ).casefold()
    if any(term in haystack for term in ("christmas", "holiday", "xmas", "rudolph", "jingle bell")):
        return "Holiday"
    if any(term in haystack for term in ("soundtrack", "original score", "ost", "star wars", "john williams", "hans zimmer")):
        return "Soundtrack"
    if any(term in haystack for term in ("country! country!", "country's greatest", "country greatest", "best bible songs", "bible songs for kids")):
        return "Country" if "country" in haystack else "Christian"
    return None


def _artist_hint_genre_for_record(record: dict[str, Any]) -> str | None:
    for artist in _artist_candidates_for_record(record):
        key = _artist_hint_key(artist)
        if key in _ARTIST_GENRE_HINTS:
            return _ARTIST_GENRE_HINTS[key]
    return None


def _artist_candidates_for_record(record: dict[str, Any]) -> list[str]:
    context = record.get("context") if isinstance(record.get("context"), dict) else {}
    artists = [str(context.get("artist") or "")]
    path = record.get("path")
    if isinstance(path, Path) and len(path.parts) >= 3:
        artists.append(path.parts[-3])

    candidates: list[str] = []
    for artist in artists:
        for candidate in _artist_name_candidates(artist):
            key = candidate.casefold()
            if key and key not in {item.casefold() for item in candidates}:
                candidates.append(candidate)
    return candidates


def _artist_name_candidates(artist: str) -> list[str]:
    text = re.sub(r"[_\s]+$", "", str(artist or "").strip())
    if not text:
        return []
    candidates = [text]
    normalized = text.replace(" + ", " & ")
    if normalized != text:
        candidates.append(normalized)
    split_patterns = (
        r"\s+featuring\s+",
        r"\s+feat\.\s+",
        r"\s+ft\.\s+",
        r"\s+duet\s+with\s+",
        r"\s+with\s+",
    )
    for pattern in split_patterns:
        head = re.split(pattern, text, maxsplit=1, flags=re.IGNORECASE)[0].strip()
        if head and head != text:
            candidates.append(head)
    if "," in text:
        parts = [part.strip() for part in text.split(",") if part.strip()]
        candidates.extend(parts)
    if "_" in text:
        parts = [part.strip() for part in text.split("_") if part.strip()]
        candidates.extend(parts)
    if " & " in text:
        parts = [part.strip() for part in re.split(r"\s+&\s+", text) if part.strip()]
        for index in range(1, len(parts)):
            candidates.append(" & ".join(parts[:index]))
    return candidates


def _artist_hint_key(artist: str) -> str:
    return re.sub(r"[_\s]+$", "", str(artist or "").strip().casefold())


def _best_genre_from_musicbrainz_candidates(candidates: list[Any]) -> str | None:
    counts: Counter[str] = Counter()
    for candidate in candidates:
        for count, name in _musicbrainz_genre_names(candidate):
            genre = canonicalize_genre(name, default=None)
            if genre:
                counts[genre] += max(1, count)
    if not counts:
        return None
    return counts.most_common(1)[0][0]


def _musicbrainz_genre_names(entity: Any) -> list[tuple[int, str]]:
    if not isinstance(entity, dict):
        return []
    rows: list[tuple[int, str]] = []
    for key in ("genre-list", "tag-list", "genres", "tags"):
        values = entity.get(key)
        if not isinstance(values, list):
            continue
        for item in values:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            try:
                count = int(item.get("count") or 1)
            except (TypeError, ValueError):
                count = 1
            rows.append((count, name))
    return rows


def _iter_audio_files(roots: list[Path]):
    stack = [root for root in roots if root.exists()]
    while stack:
        directory = stack.pop()
        try:
            with os.scandir(directory) as entries:
                dirs = []
                files = []
                for entry in entries:
                    path = Path(entry.path)
                    if _skip_path(path):
                        continue
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            dirs.append(path)
                        elif entry.is_file(follow_symlinks=False) and path.suffix.lower() in AUDIO_EXTENSIONS:
                            files.append(path)
                    except OSError:
                        continue
        except OSError:
            continue
        yield from sorted(files)
        stack.extend(reversed(sorted(dirs)))


def _skip_path(path: Path) -> bool:
    text = str(path)
    if path.name.startswith("._"):
        return True
    return any(
        marker in text
        for marker in (
            "/_AppleMusic/",
            "/_AppleMusic_skipped_duplicates/",
            "/_Retreivr_duplicate_quarantine/",
        )
    )


def _preserve_existing_tags(existing: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": existing.get("title"),
        "artist": existing.get("artist"),
        "album": existing.get("album"),
        "album_artist": existing.get("album_artist"),
        "track_number": existing.get("track_number"),
        "disc_number": existing.get("disc_number"),
        "recording_id": existing.get("recording_id"),
        "mb_release_id": existing.get("mb_release_id"),
        "mb_release_group_id": existing.get("mb_release_group_id"),
    }


def _write_report(path: Path, actions: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".json":
        path.write_text(json.dumps(actions, indent=2), encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["path", "status", "reason", "old_genre", "new_genre"])
        writer.writeheader()
        writer.writerows(actions)

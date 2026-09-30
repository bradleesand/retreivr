"""Opinionated top-level genre normalization for music libraries."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

_SPLIT_RE = re.compile(r"[;,/|]+")
_TOKEN_RE = re.compile(r"[^a-z0-9]+")
_WS_RE = re.compile(r"\s+")

TOP_LEVEL_GENRES = (
    "Alternative",
    "Bluegrass",
    "Blues",
    "Christian",
    "Classical",
    "Country",
    "Electronic",
    "Folk",
    "Gospel",
    "Hip-Hop/Rap",
    "Holiday",
    "Jazz",
    "Metal",
    "Pop",
    "R&B/Soul",
    "Reggae",
    "Rock",
    "Soundtrack",
    "World",
)

_ALIASES: dict[str, str] = {
    "adult alternative": "Alternative",
    "alternative": "Alternative",
    "alternative and punk": "Alternative",
    "alternative rock": "Alternative",
    "alt rock": "Alternative",
    "indie": "Alternative",
    "indie rock": "Alternative",
    "bluegrass": "Bluegrass",
    "progressive bluegrass": "Bluegrass",
    "blues": "Blues",
    "christian": "Christian",
    "christian contemporary": "Christian",
    "christian pop": "Christian",
    "christian rock": "Christian",
    "contemporary christian": "Christian",
    "contemporary christian music": "Christian",
    "ccm": "Christian",
    "religious": "Christian",
    "worship": "Christian",
    "praise worship": "Christian",
    "classical": "Classical",
    "country": "Country",
    "country and folk": "Country",
    "bro country": "Country",
    "brocountry": "Country",
    "classic country": "Country",
    "contemporary country": "Country",
    "country folk": "Country",
    "country pop": "Country",
    "country rock": "Country",
    "country western": "Country",
    "country gospel": "Country",
    "general country": "Country",
    "honky tonk": "Country",
    "modern country": "Country",
    "neo traditional country": "Country",
    "neo traditionalist country": "Country",
    "outlaw country": "Country",
    "red dirt": "Country",
    "southern country": "Country",
    "texas country": "Country",
    "traditional country": "Country",
    "electronic": "Electronic",
    "dance": "Electronic",
    "edm": "Electronic",
    "electronica": "Electronic",
    "folk": "Folk",
    "folk rock": "Folk",
    "americana": "Folk",
    "gospel": "Gospel",
    "gospel and religious": "Gospel",
    "southern gospel": "Gospel",
    "nicegospelcom": "Gospel",
    "hip hop": "Hip-Hop/Rap",
    "hiphop": "Hip-Hop/Rap",
    "rap": "Hip-Hop/Rap",
    "christmas": "Holiday",
    "christmas music": "Holiday",
    "holiday": "Holiday",
    "holidays": "Holiday",
    "xmas": "Holiday",
    "jazz": "Jazz",
    "metal": "Metal",
    "heavy metal": "Metal",
    "nu metal": "Metal",
    "pop": "Pop",
    "oldies": "Pop",
    "top 40": "Pop",
    "rb": "R&B/Soul",
    "r b": "R&B/Soul",
    "rnb": "R&B/Soul",
    "r n b": "R&B/Soul",
    "soul": "R&B/Soul",
    "reggae": "Reggae",
    "rock": "Rock",
    "classic rock": "Rock",
    "album rock": "Rock",
    "blues rock": "Rock",
    "grunge": "Rock",
    "hard rock": "Rock",
    "pop punk": "Rock",
    "punk": "Rock",
    "punk rock": "Rock",
    "southern rock": "Rock",
    "soundtrack": "Soundtrack",
    "film score": "Soundtrack",
    "score": "Soundtrack",
    "sound track": "Soundtrack",
    "musical": "Soundtrack",
    "world": "World",
    "world music": "World",
}


def canonicalize_genre(value: Any, *, default: str | None = "Unknown") -> str | None:
    """Return Retreivr's top-level genre label for one or more source genres.

    MusicBrainz genre/tag data is useful evidence, but it is too granular and
    inconsistent for library browsing. This function collapses known aliases
    into a small display taxonomy while preserving stable capitalization.
    """

    parts = _genre_parts(value)
    for part in parts:
        genre = canonicalize_genre_part(part)
        if genre:
            return genre
    return default


def canonicalize_genre_part(value: Any) -> str | None:
    text = _normalize_text(value)
    if not text:
        return None
    key = genre_key(text)
    return _ALIASES.get(key)


def genre_key(value: Any) -> str:
    text = _normalize_text(value).casefold()
    text = text.replace("&", " and ")
    text = _TOKEN_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text).strip()
    return text


def _genre_parts(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        raw_parts = [str(part) for part in value]
    else:
        raw_parts = _SPLIT_RE.split(str(value))
    return [_normalize_text(part) for part in raw_parts if _normalize_text(part)]


def _normalize_text(value: Any) -> str:
    return _WS_RE.sub(" ", unicodedata.normalize("NFC", str(value or "")).strip())

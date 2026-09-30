"""Deterministic artist-credit normalization for music tags."""

from __future__ import annotations

import re
import unicodedata

_WS_RE = re.compile(r"\s+")
_EXPLICIT_SPLIT_RE = re.compile(
    r"^(?P<main>.+?)\s+(?P<join>feat\.|ft\.|featuring|with|duet\s+with)\s+(?P<guest>.+)$",
    re.IGNORECASE,
)
_TITLE_FEAT_RE = re.compile(r"\(\s*feat\.\s*([^)]+)\)", re.IGNORECASE)
_AMP_SPLIT_RE = re.compile(r"\s+(?:&|\+)\s+")


def normalize_track_artist_credit(
    artist: str,
    title: str,
    *,
    album_artist: str | None = None,
) -> tuple[str, str]:
    """Return primary track artist and title with guest credit folded in.

    Retreivr uses this for player-facing tags. The goal is deterministic library
    grouping: the primary artist should own the artist card, while featured or
    duet credits remain visible in the title.
    """

    normalized_artist = _normalize_text(artist)
    normalized_title = _normalize_text(title)
    normalized_album_artist = _normalize_text(album_artist or "")
    if not normalized_artist:
        return normalized_artist, normalized_title

    explicit = _EXPLICIT_SPLIT_RE.match(normalized_artist)
    if explicit:
        return _with_featured_title(
            explicit.group("main"),
            normalized_title,
            explicit.group("guest"),
        )

    if "," in normalized_artist:
        parts = [_normalize_text(part) for part in normalized_artist.split(",") if _normalize_text(part)]
        if len(parts) > 1:
            main = _primary_from_comma_parts(parts, normalized_album_artist)
            guests = [part for part in parts if part != main]
            return _with_featured_title(main, normalized_title, " & ".join(guests))

    if normalized_album_artist:
        for separator in (" & ", " + "):
            prefix = f"{normalized_album_artist}{separator}"
            if normalized_artist.casefold().startswith(prefix.casefold()):
                guest = normalized_artist[len(prefix) :].strip()
                return _with_featured_title(normalized_album_artist, normalized_title, guest)

    return normalized_artist, normalized_title


def normalize_album_artist_credit(album_artist: str, *, fallback_artist: str | None = None) -> str:
    """Return stable album artist text for folder and album grouping."""

    normalized = _normalize_text(album_artist)
    if not normalized:
        normalized = _normalize_text(fallback_artist or "")
    if not normalized:
        return ""
    if normalized.casefold() in {"various", "various artist"}:
        return "Various Artists"
    return normalized


def _primary_from_comma_parts(parts: list[str], album_artist: str) -> str:
    if album_artist and album_artist.casefold() != "various artists":
        for part in parts:
            if part.casefold() == album_artist.casefold():
                return part
    if parts[0].casefold() in {"hixtape", "various artists"} and len(parts) > 1:
        return parts[1]
    return parts[0]


def _with_featured_title(main: str, title: str, guest: str) -> tuple[str, str]:
    normalized_main = _normalize_text(main)
    normalized_guest = _normalize_text(guest)
    normalized_title = _normalize_text(title)
    if not normalized_guest:
        return normalized_main, normalized_title

    existing = {_normalize_text(item).casefold() for item in _TITLE_FEAT_RE.findall(normalized_title)}
    if normalized_guest.casefold() in existing:
        return normalized_main, normalized_title
    return normalized_main, f"{normalized_title} (feat. {normalized_guest})"


def _normalize_text(value: str) -> str:
    return _WS_RE.sub(" ", unicodedata.normalize("NFC", str(value or "")).strip())


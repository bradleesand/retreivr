from __future__ import annotations

from metadata.artist_credit import normalize_album_artist_credit, normalize_track_artist_credit


def test_explicit_featured_credit_moves_to_title() -> None:
    artist, title = normalize_track_artist_credit("Main Artist featuring Guest Artist", "Song")

    assert artist == "Main Artist"
    assert title == "Song (feat. Guest Artist)"


def test_duet_credit_moves_to_title() -> None:
    artist, title = normalize_track_artist_credit("Main Artist duet with Guest Artist", "Song")

    assert artist == "Main Artist"
    assert title == "Song (feat. Guest Artist)"


def test_album_artist_prefixed_ampersand_credit_moves_to_title() -> None:
    artist, title = normalize_track_artist_credit(
        "Kenny Chesney & Uncle Kracker",
        "Song",
        album_artist="Kenny Chesney",
    )

    assert artist == "Kenny Chesney"
    assert title == "Song (feat. Uncle Kracker)"


def test_band_name_with_ampersand_is_preserved_without_album_artist_prefix() -> None:
    artist, title = normalize_track_artist_credit("Brooks & Dunn", "Song")

    assert artist == "Brooks & Dunn"
    assert title == "Song"


def test_comma_compilation_credit_uses_first_real_artist() -> None:
    artist, title = normalize_track_artist_credit("HIXTAPE, Ashland Craft & Brothers Osborne", "Song")

    assert artist == "Ashland Craft & Brothers Osborne"
    assert title == "Song (feat. HIXTAPE)"


def test_album_artist_normalizes_various_alias() -> None:
    assert normalize_album_artist_credit("Various", fallback_artist="Artist") == "Various Artists"


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


def test_known_ampersand_band_with_guest_moves_guest_to_title() -> None:
    artist, title = normalize_track_artist_credit("Brooks & Dunn & Reba McEntire", "Song")

    assert artist == "Brooks & Dunn"
    assert title == "Song (feat. Reba McEntire)"


def test_symbol_collaboration_moves_guest_to_title() -> None:
    artist, title = normalize_track_artist_credit("Brandon Lake X Bethel Music", "Song")

    assert artist == "Brandon Lake"
    assert title == "Song (feat. Bethel Music)"


def test_plus_collaboration_moves_guest_to_title() -> None:
    artist, title = normalize_track_artist_credit("Brantley Gilbert + Lindsay Ell", "Song")

    assert artist == "Brantley Gilbert"
    assert title == "Song (feat. Lindsay Ell)"


def test_single_ampersand_collaboration_moves_guest_to_title() -> None:
    artist, title = normalize_track_artist_credit("Brantley Gilbert & Blake Shelton", "Song")

    assert artist == "Brantley Gilbert"
    assert title == "Song (feat. Blake Shelton)"


def test_known_ampersand_artist_is_preserved() -> None:
    artist, title = normalize_track_artist_credit("for KING & COUNTRY", "Song")

    assert artist == "for KING & COUNTRY"
    assert title == "Song"


def test_known_plus_artist_is_preserved() -> None:
    artist, title = normalize_track_artist_credit("Dan + Shay", "Song")

    assert artist == "Dan + Shay"
    assert title == "Song"


def test_known_plus_artist_with_guest_preserves_primary_group() -> None:
    artist, title = normalize_track_artist_credit("Dan + Shay & Justin Bieber", "Song")

    assert artist == "Dan + Shay"
    assert title == "Song (feat. Justin Bieber)"


def test_known_x_artist_is_preserved() -> None:
    artist, title = normalize_track_artist_credit("Greg X Volz", "Song")

    assert artist == "Greg X Volz"
    assert title == "Song"


def test_known_plus_variant_with_guest_preserves_primary_group() -> None:
    artist, title = normalize_track_artist_credit("for KING + COUNTRY & Echosmith", "Song")

    assert artist == "for KING + COUNTRY"
    assert title == "Song (feat. Echosmith)"


def test_comma_compilation_credit_uses_album_artist_when_present() -> None:
    artist, title = normalize_track_artist_credit(
        "HIXTAPE, Ashland Craft & Brothers Osborne",
        "Song",
        album_artist="Ashland Craft & Brothers Osborne",
    )

    assert artist == "Ashland Craft & Brothers Osborne"
    assert title == "Song (feat. HIXTAPE)"


def test_comma_artist_is_preserved_without_primary_artist_signal() -> None:
    artist, title = normalize_track_artist_credit("Hank Williams, Jr.", "Song")

    assert artist == "Hank Williams, Jr."
    assert title == "Song"


def test_album_artist_normalizes_various_alias() -> None:
    assert normalize_album_artist_credit("Various", fallback_artist="Artist") == "Various Artists"

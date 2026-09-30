from __future__ import annotations

from metadata.genre_policy import TOP_LEVEL_GENRES, canonicalize_genre
from metadata.normalize import normalize_music_metadata
from metadata.types import MusicMetadata


def _metadata(genre: str) -> MusicMetadata:
    return MusicMetadata(
        title="Song",
        artist="Artist",
        album="Album",
        album_artist="Album Artist",
        track_num=1,
        disc_num=1,
        date="2024",
        genre=genre,
    )


def test_top_level_genre_labels_are_display_capitalized() -> None:
    assert "Country" in TOP_LEVEL_GENRES
    assert "Bluegrass" in TOP_LEVEL_GENRES
    assert "Holiday" in TOP_LEVEL_GENRES
    assert all(label[0].isupper() for label in TOP_LEVEL_GENRES)


def test_country_aliases_collapse_without_absorbing_bluegrass() -> None:
    assert canonicalize_genre("country") == "Country"
    assert canonicalize_genre("Country & Folk") == "Country"
    assert canonicalize_genre("bro-country") == "Country"
    assert canonicalize_genre("contemporary country") == "Country"
    assert canonicalize_genre("honky tonk") == "Country"
    assert canonicalize_genre("traditional country") == "Country"
    assert canonicalize_genre("texas country") == "Country"
    assert canonicalize_genre("bluegrass") == "Bluegrass"


def test_rock_aliases_from_musicbrainz_artist_tags_collapse_to_rock() -> None:
    assert canonicalize_genre("hard rock") == "Rock"
    assert canonicalize_genre("blues rock") == "Rock"
    assert canonicalize_genre("classic rock") == "Rock"


def test_christian_aliases_from_musicbrainz_artist_tags_collapse_to_christian() -> None:
    assert canonicalize_genre("contemporary christian") == "Christian"
    assert canonicalize_genre("christian rock") == "Christian"


def test_holiday_aliases_collapse_to_holiday() -> None:
    assert canonicalize_genre("Christmas") == "Holiday"
    assert canonicalize_genre("xmas") == "Holiday"
    assert canonicalize_genre("Music", default=None) is None


def test_metadata_normalization_uses_top_level_genre_policy() -> None:
    normalized = normalize_music_metadata(_metadata(" Pop ; pop, ROCK, Rock , Jazz "))

    assert normalized.genre == "Pop"

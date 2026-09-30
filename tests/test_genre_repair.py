from __future__ import annotations

from pathlib import Path

from metadata.genre_repair import _best_genre_from_musicbrainz_candidates, repair_music_genres


def test_repair_music_genres_dry_run_reports_missing_and_aliases(tmp_path: Path, monkeypatch) -> None:
    album = tmp_path / "Artist" / "Album"
    album.mkdir(parents=True)
    country = album / "country.m4a"
    missing = album / "missing.m4a"
    country.write_bytes(b"audio")
    missing.write_bytes(b"audio")

    def fake_read(path: str):
        if path.endswith("country.m4a"):
            return {"title": "Song", "genre": "bro-country"}
        return {"title": "Other"}

    writes = []
    monkeypatch.setattr("metadata.genre_repair.read_music_tags", fake_read)
    monkeypatch.setattr("metadata.genre_repair.apply_tags", lambda *args, **kwargs: writes.append((args, kwargs)))

    result = repair_music_genres([tmp_path], dry_run=True)

    assert result["scanned"] == 2
    assert result["changed"] == 2
    assert result["missing"] == 1
    assert result["failed"] == 0
    assert writes == []
    assert {item["new_genre"] for item in result["items"]} == {"Country", "Unknown"}


def test_repair_music_genres_infers_missing_from_artist_consensus(tmp_path: Path, monkeypatch) -> None:
    album = tmp_path / "Artist" / "Album"
    album.mkdir(parents=True)
    for name in ("known-1.m4a", "known-2.m4a", "missing.m4a"):
        (album / name).write_bytes(b"audio")

    def fake_read(path: str):
        if "missing" in path:
            return {"title": "Missing"}
        return {"title": "Known", "genre": "country"}

    monkeypatch.setattr("metadata.genre_repair.read_music_tags", fake_read)

    result = repair_music_genres([tmp_path], dry_run=True)
    missing_item = next(item for item in result["items"] if item["old_genre"] is None)

    assert missing_item["new_genre"] == "Country"
    assert missing_item["reason"] == "missing_artist_consensus"


def test_repair_music_genres_enriches_missing_from_musicbrainz(tmp_path: Path, monkeypatch) -> None:
    album = tmp_path / "Artist" / "Album"
    album.mkdir(parents=True)
    missing = album / "missing.m4a"
    missing.write_bytes(b"audio")

    monkeypatch.setattr("metadata.genre_repair.read_music_tags", lambda _path: {"title": "Missing"})
    monkeypatch.setattr(
        "metadata.genre_repair._lookup_musicbrainz_genre",
        lambda *, artist, album, title: "Bluegrass",
    )

    result = repair_music_genres([tmp_path], dry_run=True, musicbrainz_enrich=True)
    item = result["items"][0]

    assert item["new_genre"] == "Bluegrass"
    assert item["reason"] == "missing_musicbrainz"
    assert result["musicbrainz_enriched"] == 1


def test_musicbrainz_country_artist_tag_cluster_maps_to_country() -> None:
    artist = {
        "tags": [
            {"name": "country", "count": 8},
            {"name": "honky tonk", "count": 1},
            {"name": "traditional country", "count": 1},
            {"name": "texas country", "count": 2},
        ]
    }

    assert _best_genre_from_musicbrainz_candidates([artist]) == "Country"


def test_musicbrainz_rock_artist_tag_cluster_maps_to_rock() -> None:
    artist = {
        "tags": [
            {"name": "rock", "count": 12},
            {"name": "hard rock", "count": 31},
            {"name": "blues rock", "count": 17},
            {"name": "classic rock", "count": 6},
        ]
    }

    assert _best_genre_from_musicbrainz_candidates([artist]) == "Rock"


def test_repair_music_genres_uses_holiday_heuristic(tmp_path: Path, monkeypatch) -> None:
    album = tmp_path / "Artist" / "Christmas Album"
    album.mkdir(parents=True)
    track = album / "jingle-bells.m4a"
    track.write_bytes(b"audio")

    monkeypatch.setattr("metadata.genre_repair.read_music_tags", lambda _path: {"title": "Jingle Bells"})

    result = repair_music_genres([tmp_path], dry_run=True)
    item = result["items"][0]

    assert item["new_genre"] == "Holiday"
    assert item["reason"] == "missing_heuristic"

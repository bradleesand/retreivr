import sqlite3

from db.playlist_snapshots import PlaylistSnapshotStore


def _sample_items() -> list[dict[str, object]]:
    return [
        {
            "spotify_track_id": "spotify:track:1",
            "position": 0,
            "added_at": "2026-02-09T00:00:00+00:00",
        },
        {
            "spotify_track_id": "spotify:track:2",
            "position": 1,
            "added_at": "2026-02-09T00:01:00+00:00",
        },
    ]


def test_snapshot_store_inserts_snapshot_and_items(tmp_path) -> None:
    db_path = tmp_path / "snapshots.sqlite"
    store = PlaylistSnapshotStore(str(db_path))

    result = store.store_snapshot(
        playlist_id="playlist-1",
        snapshot_id="snap-1",
        items=_sample_items(),
    )

    assert result.inserted is True
    latest = store.get_latest_snapshot("playlist-1")
    assert latest is not None
    assert latest["snapshot_id"] == "snap-1"
    assert latest["track_count"] == 2
    assert [item["spotify_track_id"] for item in latest["items"]] == [
        "spotify:track:1",
        "spotify:track:2",
    ]


def test_snapshot_store_fast_path_for_same_snapshot_id(tmp_path) -> None:
    db_path = tmp_path / "snapshots.sqlite"
    store = PlaylistSnapshotStore(str(db_path))
    store.store_snapshot(
        playlist_id="playlist-1",
        snapshot_id="snap-1",
        items=_sample_items(),
    )

    second = store.store_snapshot(
        playlist_id="playlist-1",
        snapshot_id="snap-1",
        items=_sample_items(),
    )

    assert second.inserted is False
    assert second.reason == "snapshot_unchanged"

    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM playlist_snapshots").fetchone()[0]
    assert count == 1


def test_snapshot_store_tracks_latest_snapshot_uris(tmp_path) -> None:
    db_path = tmp_path / "snapshots.sqlite"
    store = PlaylistSnapshotStore(str(db_path))
    store.store_snapshot(
        playlist_id="playlist-2",
        snapshot_id="snap-1",
        items=_sample_items(),
    )
    updated_items = _sample_items() + [
        {
            "spotify_track_id": "spotify:track:3",
            "position": 2,
            "added_at": "2026-02-09T00:02:00+00:00",
        }
    ]
    store.store_snapshot(
        playlist_id="playlist-2",
        snapshot_id="snap-2",
        items=updated_items,
    )

    latest = store.get_latest_snapshot("playlist-2")
    assert latest is not None
    track_ids = [item["spotify_track_id"] for item in latest["items"]]
    assert track_ids == ["spotify:track:1", "spotify:track:2", "spotify:track:3"]

from spotify.diff import diff_playlist


def _item(track_id, position):
    return {"spotify_track_id": track_id, "position": position}


def test_diff_playlist_added_removed_and_moved() -> None:
    prev = [_item("a", 0), _item("b", 1), _item("c", 2)]
    curr = [_item("b", 0), _item("a", 1), _item("d", 2)]

    changes = diff_playlist(prev, curr)

    assert [i["spotify_track_id"] for i in changes["added"]] == ["d"]
    assert [i["spotify_track_id"] for i in changes["removed"]] == ["c"]
    assert changes["moved"] == [
        {"spotify_track_id": "b", "from_position": 1, "to_position": 0, "item": _item("b", 0)},
        {"spotify_track_id": "a", "from_position": 0, "to_position": 1, "item": _item("a", 1)},
    ]


def test_diff_playlist_honors_duplicates() -> None:
    prev = [_item("x", 0), _item("y", 1), _item("x", 2)]
    curr = [_item("x", 0), _item("x", 1), _item("y", 2), _item("x", 3)]

    changes = diff_playlist(prev, curr)

    assert [i["spotify_track_id"] for i in changes["added"]] == ["x"]
    assert changes["removed"] == []
    assert changes["moved"] == [
        {"spotify_track_id": "x", "from_position": 2, "to_position": 1, "item": _item("x", 1)},
        {"spotify_track_id": "y", "from_position": 1, "to_position": 2, "item": _item("y", 2)},
    ]


def test_diff_playlist_handles_empty_lists() -> None:
    changes = diff_playlist([], [])

    assert changes == {"added": [], "removed": [], "moved": []}

from __future__ import annotations

from pathlib import Path

from metadata.providers import artwork as artwork_provider


class _FakeResponse:
    def __init__(self, content: bytes, content_type: str = "image/jpeg") -> None:
        self.ok = True
        self.content = content
        self.headers = {"Content-Type": content_type}


def test_fetch_artwork_from_url_uses_local_cache(monkeypatch, tmp_path: Path) -> None:
    calls = {"count": 0}

    def _fake_get(url, timeout=10):
        _ = url, timeout
        calls["count"] += 1
        return _FakeResponse(b"processed-image")

    monkeypatch.setattr(artwork_provider.requests, "get", _fake_get)
    monkeypatch.setattr(
        artwork_provider,
        "_normalize_artwork_blob",
        lambda data, content_type, *, context: {"data": bytes(data), "mime": content_type},
    )

    first = artwork_provider.fetch_artwork_from_url(
        "https://img.test/cover.jpg",
        cache_dir=tmp_path,
        cache_max_mb=1,
    )
    second = artwork_provider.fetch_artwork_from_url(
        "https://img.test/cover.jpg",
        cache_dir=tmp_path,
        cache_max_mb=1,
    )

    assert calls["count"] == 1
    assert first == {"data": b"processed-image", "mime": "image/jpeg"}
    assert second == first


def test_artwork_cache_prunes_oldest_entries(tmp_path: Path) -> None:
    cache_root = tmp_path / "artwork"
    first = {"data": b"a" * 700_000, "mime": "image/jpeg"}
    second = {"data": b"b" * 700_000, "mime": "image/jpeg"}

    artwork_provider._write_cached_artwork(
        cache_root,
        "a" * 64,
        first,
        source="first",
        kind="url",
        max_bytes=1_000_000,
    )
    artwork_provider._write_cached_artwork(
        cache_root,
        "b" * 64,
        second,
        source="second",
        kind="url",
        max_bytes=1_000_000,
    )

    cached_files = sorted(cache_root.glob("*/*.bin"))
    assert len(cached_files) == 1
    assert cached_files[0].name == f"{'b' * 64}.bin"

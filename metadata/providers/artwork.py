import io
import hashlib
import json
import logging
import os
from pathlib import Path
import threading

from PIL import Image
import requests
from engine.paths import DATA_DIR
from metadata.services.musicbrainz_service import get_musicbrainz_service

_DEFAULT_ARTWORK_CACHE_MAX_BYTES = 256 * 1024 * 1024
_CACHE_LOCK = threading.Lock()


def _cache_enabled(value=True):
    env = str(os.environ.get("RETREIVR_ARTWORK_CACHE_ENABLED", "") or "").strip().lower()
    if env in {"0", "false", "no", "off"}:
        return False
    return bool(value)


def _cache_dir(value=None):
    raw = str(value or os.environ.get("RETREIVR_ARTWORK_CACHE_DIR") or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return (DATA_DIR / "artwork_cache").resolve()


def _cache_max_bytes(value=None):
    raw = value
    if raw is None:
        raw = os.environ.get("RETREIVR_ARTWORK_CACHE_MAX_MB")
    try:
        parsed = float(raw)
    except (TypeError, ValueError):
        return _DEFAULT_ARTWORK_CACHE_MAX_BYTES
    if parsed <= 0:
        return 0
    return int(parsed * 1024 * 1024)


def _cache_key(kind, source, *, max_size_px):
    digest = hashlib.sha256(f"{kind}\0{source}\0{int(max_size_px or 0)}".encode("utf-8")).hexdigest()
    return digest


def _cache_paths(cache_root, key):
    shard = key[:2]
    base = cache_root / shard
    return base / f"{key}.bin", base / f"{key}.json"


def _read_cached_artwork(cache_root, key):
    data_path, meta_path = _cache_paths(cache_root, key)
    try:
        if not data_path.exists() or not meta_path.exists():
            return None
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        data = data_path.read_bytes()
        if not data:
            return None
        now = None
        os.utime(data_path, times=now)
        os.utime(meta_path, times=now)
        return {
            "data": data,
            "mime": str(metadata.get("mime") or "image/jpeg"),
        }
    except Exception:
        logging.debug("Artwork cache read failed for key=%s", key, exc_info=True)
        return None


def _write_cached_artwork(cache_root, key, artwork, *, source, kind, max_bytes):
    if not artwork or max_bytes <= 0:
        return
    data = artwork.get("data")
    if not data:
        return
    data = bytes(data)
    if len(data) > max_bytes:
        return
    data_path, meta_path = _cache_paths(cache_root, key)
    try:
        data_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_data = data_path.with_suffix(".bin.tmp")
        tmp_meta = meta_path.with_suffix(".json.tmp")
        tmp_data.write_bytes(data)
        tmp_meta.write_text(
            json.dumps(
                {
                    "kind": kind,
                    "source": source,
                    "mime": artwork.get("mime") or "image/jpeg",
                    "size": len(data),
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        os.replace(tmp_data, data_path)
        os.replace(tmp_meta, meta_path)
        _prune_cache(cache_root, max_bytes=max_bytes)
    except Exception:
        logging.debug("Artwork cache write failed for key=%s", key, exc_info=True)


def _prune_cache(cache_root, *, max_bytes):
    if max_bytes <= 0:
        return
    try:
        entries = []
        total = 0
        for path in cache_root.glob("*/*.bin"):
            try:
                stat = path.stat()
            except OSError:
                continue
            total += stat.st_size
            entries.append((stat.st_mtime, path, stat.st_size))
        if total <= max_bytes:
            return
        entries.sort(key=lambda item: item[0])
        for _mtime, path, size in entries:
            try:
                path.unlink(missing_ok=True)
                path.with_suffix(".json").unlink(missing_ok=True)
            except Exception:
                logging.debug("Artwork cache prune failed for %s", path, exc_info=True)
            total -= size
            if total <= max_bytes:
                break
    except Exception:
        logging.debug("Artwork cache prune failed", exc_info=True)


def _fetch_or_cache(kind, source, fetcher, *, max_size_px, cache_dir=None, cache_max_mb=None, cache_enabled=True):
    if not source:
        return None
    enabled = _cache_enabled(cache_enabled)
    max_bytes = _cache_max_bytes(cache_max_mb)
    cache_root = _cache_dir(cache_dir)
    key = _cache_key(kind, source, max_size_px=max_size_px)
    if enabled and max_bytes > 0:
        with _CACHE_LOCK:
            cached = _read_cached_artwork(cache_root, key)
        if cached is not None:
            return cached
    artwork = fetcher()
    if enabled and artwork and max_bytes > 0:
        with _CACHE_LOCK:
            _write_cached_artwork(
                cache_root,
                key,
                artwork,
                source=source,
                kind=kind,
                max_bytes=max_bytes,
            )
    return artwork


def _normalize_artwork_blob(data, content_type, *, context):
    if not data:
        return None
    try:
        image = Image.open(io.BytesIO(data))
        max_size_px = context.get("max_size_px")
        if max_size_px:
            image.thumbnail((max_size_px, max_size_px))
        output = io.BytesIO()
        fmt = "JPEG" if str(content_type or "").endswith(("jpeg", "jpg")) else "PNG"
        if fmt == "JPEG" and image.mode not in {"RGB", "L"}:
            image = image.convert("RGB")
        image.save(output, format=fmt)
        return {
            "data": output.getvalue(),
            "mime": "image/jpeg" if fmt == "JPEG" else "image/png",
        }
    except Exception:
        logging.debug("Artwork processing failed for %s", context.get("label"))
        return None


def fetch_artwork(
    release_id,
    max_size_px=1500,
    *,
    cache_dir=None,
    cache_max_mb=None,
    cache_enabled=True,
):
    if not release_id:
        return None
    rid = str(release_id or "").strip()

    def _fetch():
        service = get_musicbrainz_service()
        try:
            payload = service.fetch_cover_art(rid, timeout=10)
            if not payload:
                return None
        except Exception:
            logging.debug("Artwork download failed for release %s", rid)
            return None
        return _normalize_artwork_blob(
            payload.get("data"),
            payload.get("mime", "image/jpeg"),
            context={"label": f"release {rid}", "max_size_px": max_size_px},
        )

    return _fetch_or_cache(
        "release",
        rid,
        _fetch,
        max_size_px=max_size_px,
        cache_dir=cache_dir,
        cache_max_mb=cache_max_mb,
        cache_enabled=cache_enabled,
    )


def fetch_artwork_from_url(
    artwork_url,
    max_size_px=1500,
    timeout=10,
    *,
    cache_dir=None,
    cache_max_mb=None,
    cache_enabled=True,
):
    url = str(artwork_url or "").strip()
    if not url:
        return None

    def _fetch():
        try:
            resp = requests.get(url, timeout=timeout)
        except Exception:
            logging.debug("Artwork URL download failed for %s", url)
            return None
        if not resp.ok or not resp.content:
            return None
        return _normalize_artwork_blob(
            resp.content,
            resp.headers.get("Content-Type") or "image/jpeg",
            context={"label": url, "max_size_px": max_size_px},
        )

    return _fetch_or_cache(
        "url",
        url,
        _fetch,
        max_size_px=max_size_px,
        cache_dir=cache_dir,
        cache_max_mb=cache_max_mb,
        cache_enabled=cache_enabled,
    )

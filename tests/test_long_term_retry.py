from __future__ import annotations

import importlib.util
import sqlite3
import sys
import types
from pathlib import Path


_ROOT = Path(__file__).resolve().parent.parent


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_job_queue():
    if "engine" not in sys.modules:
        engine_pkg = types.ModuleType("engine")
        engine_pkg.__path__ = [str(_ROOT / "engine")]  # type: ignore[attr-defined]
        sys.modules["engine"] = engine_pkg
    _load_module("engine.json_utils", _ROOT / "engine" / "json_utils.py")
    paths_mod = _load_module("engine.paths", _ROOT / "engine" / "paths.py")
    _load_module("engine.search_scoring", _ROOT / "engine" / "search_scoring.py")
    if "engine.community_publish_worker" not in sys.modules:
        mod = types.ModuleType("engine.community_publish_worker")
        mod.append_publish_proposal_to_outbox = lambda *args, **kwargs: None
        mod.normalize_community_publish_source = lambda value: str(value or "")
        sys.modules["engine.community_publish_worker"] = mod
    if "engine.music_export" not in sys.modules:
        mod = types.ModuleType("engine.music_export")
        mod.run_music_exports = lambda *args, **kwargs: []
        sys.modules["engine.music_export"] = mod
    if "engine.resolution_api" not in sys.modules:
        mod = types.ModuleType("engine.resolution_api")
        mod.upsert_local_acquired_mapping = lambda *args, **kwargs: None
        sys.modules["engine.resolution_api"] = mod
    if "engine.music_title_normalization" not in sys.modules:
        mod = types.ModuleType("engine.music_title_normalization")
        mod.has_live_intent = lambda *args, **kwargs: False
        mod.relaxed_search_title = lambda value: str(value or "")
        sys.modules["engine.music_title_normalization"] = mod
    if "media.music_contract" not in sys.modules:
        mod = types.ModuleType("media.music_contract")
        mod.format_zero_padded_track_number = lambda value: str(value or "")
        mod.parse_first_positive_int = lambda value: None
        sys.modules["media.music_contract"] = mod
    if "media.path_builder" not in sys.modules:
        mod = types.ModuleType("media.path_builder")
        mod.build_music_relative_layout = lambda *args, **kwargs: "Artist/Album/01 - Track.mp3"
        sys.modules["media.path_builder"] = mod
    if "metadata.naming" not in sys.modules:
        mod = types.ModuleType("metadata.naming")
        mod.sanitize_component = lambda value, **kwargs: str(value or "")
        sys.modules["metadata.naming"] = mod
    if "metadata.queue" not in sys.modules:
        metadata_queue = types.ModuleType("metadata.queue")
        metadata_queue.enqueue_metadata = lambda *args, **kwargs: None
        sys.modules["metadata.queue"] = metadata_queue
    if "metadata.services" not in sys.modules:
        services_pkg = types.ModuleType("metadata.services")
        services_pkg.__path__ = []  # type: ignore[attr-defined]
        sys.modules["metadata.services"] = services_pkg
    if "metadata.services.musicbrainz_service" not in sys.modules:
        mb_module = types.ModuleType("metadata.services.musicbrainz_service")
        mb_module.get_musicbrainz_service = lambda: types.SimpleNamespace(_call_with_retry=lambda func: func())
        sys.modules["metadata.services.musicbrainz_service"] = mb_module
    if "library.provenance" not in sys.modules:
        mod = types.ModuleType("library.provenance")
        mod.build_file_provenance = lambda *args, **kwargs: {}
        mod.get_retreivr_version = lambda: "test"
        sys.modules["library.provenance"] = mod
    if "library.review_queue" not in sys.modules:
        mod = types.ModuleType("library.review_queue")
        mod.record_completed_review_item = lambda *args, **kwargs: None
        sys.modules["library.review_queue"] = mod
    if "engine.musicbrainz_binding" not in sys.modules:
        binding_module = types.ModuleType("engine.musicbrainz_binding")
        binding_module.resolve_best_mb_pair = lambda *args, **kwargs: None
        binding_module._normalize_title_for_mb_lookup = lambda value, **kwargs: str(value or "")
        sys.modules["engine.musicbrainz_binding"] = binding_module
    if "requests" not in sys.modules:
        sys.modules["requests"] = types.ModuleType("requests")
    if "yt_dlp" not in sys.modules:
        yt_mod = types.ModuleType("yt_dlp")
        yt_mod.YoutubeDL = object
        sys.modules["yt_dlp"] = yt_mod
    if "yt_dlp.utils" not in sys.modules:
        utils_mod = types.ModuleType("yt_dlp.utils")
        utils_mod.DownloadError = RuntimeError
        utils_mod.ExtractorError = RuntimeError
        sys.modules["yt_dlp.utils"] = utils_mod
    jq = _load_module("engine_job_queue_long_term_retry", _ROOT / "engine" / "job_queue.py")
    return jq, paths_mod.EnginePaths


def _build_paths(tmp_path: Path, EnginePaths):
    root = tmp_path / "runtime"
    return EnginePaths(
        log_dir=str(root / "logs"),
        db_path=str(root / "db.sqlite"),
        temp_downloads_dir=str(root / "tmp"),
        single_downloads_dir=str(root / "downloads"),
        review_queue_dir=str(root / "review_queue"),
        review_queue_files_dir=str(root / "review_queue" / "files"),
        lock_file=str(root / "retreivr.lock"),
        ytdlp_temp_dir=str(root / "ytdlp"),
        thumbs_dir=str(root / "thumbs"),
    )


def _init_db(jq, db_path: str) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        jq.ensure_download_jobs_table(conn)
        jq.ensure_downloads_table(conn)
        jq.ensure_music_candidate_failures_table(conn)
        jq.ensure_long_term_retry_table(conn)
    finally:
        conn.close()


def _enqueue_music_job(engine) -> str:
    job_id, created, reason = engine.store.enqueue_job(
        origin="manual",
        origin_id="test-origin",
        media_type="music",
        media_intent="music_track",
        source="youtube",
        url="https://www.youtube.com/watch?v=retry12345",
        external_id="retry12345",
        canonical_id="music_track:artist:release:recording:youtube:retry12345",
        output_template={
            "artist": "Test Artist",
            "track": "Test Track",
            "album": "Test Album",
            "recording_mbid": "rec-123",
            "mb_release_id": "rel-123",
            "mb_release_group_id": "rg-123",
            "canonical_metadata": {
                "artist": "Test Artist",
                "track": "Test Track",
                "album": "Test Album",
                "recording_mbid": "rec-123",
                "mb_release_id": "rel-123",
                "mb_release_group_id": "rg-123",
            },
        },
    )
    assert created is True
    assert reason is None
    return job_id


def test_terminal_music_failure_promotes_to_long_term_retry(tmp_path: Path) -> None:
    jq, EnginePaths = _load_job_queue()
    paths = _build_paths(tmp_path, EnginePaths)
    _init_db(jq, paths.db_path)
    engine = jq.DownloadWorkerEngine(
        paths.db_path,
        {
            "long_term_retry_enabled": True,
            "long_term_retry_interval_hours": 24,
            "long_term_retry_batch_size": 5,
            "long_term_retry_max_attempts": 0,
        },
        paths,
    )
    job_id = _enqueue_music_job(engine)
    job = engine.store.claim_job_by_id(job_id)
    assert job is not None

    status = engine._record_job_failure(
        job,
        error_message="no_candidates_retrieved",
        retryable=False,
        retry_delay_seconds=30,
    )

    assert status == "failed"
    summary = engine.store.summarize_long_term_retry_queue()
    assert summary["total"] == 1
    assert summary["deferred"] == 1


def test_long_term_retry_processor_requeues_due_failed_job(tmp_path: Path) -> None:
    jq, EnginePaths = _load_job_queue()
    paths = _build_paths(tmp_path, EnginePaths)
    _init_db(jq, paths.db_path)
    engine = jq.DownloadWorkerEngine(
        paths.db_path,
        {
            "long_term_retry_enabled": True,
            "long_term_retry_interval_hours": 24,
            "long_term_retry_batch_size": 5,
            "long_term_retry_max_attempts": 0,
        },
        paths,
    )
    job_id = _enqueue_music_job(engine)
    job = engine.store.claim_job_by_id(job_id)
    assert job is not None
    engine._record_job_failure(
        job,
        error_message="no_candidate_above_threshold",
        retryable=False,
        retry_delay_seconds=30,
    )

    with sqlite3.connect(paths.db_path) as conn:
        conn.execute(
            "UPDATE long_term_retry_queue SET next_attempt_at='2000-01-01T00:00:00+00:00' WHERE job_id=?",
            (job_id,),
        )
        conn.commit()

    summary = engine.process_long_term_retry_once()

    assert summary["claimed"] == 1
    assert summary["requeued"] == 1
    requeued = engine.store.get_job(job_id)
    assert requeued is not None
    assert requeued.status == "queued"


def test_long_term_retry_processor_abandons_exhausted_candidates(tmp_path: Path) -> None:
    jq, EnginePaths = _load_job_queue()
    paths = _build_paths(tmp_path, EnginePaths)
    _init_db(jq, paths.db_path)
    engine = jq.DownloadWorkerEngine(
        paths.db_path,
        {
            "long_term_retry_enabled": True,
            "long_term_retry_interval_hours": 24,
            "long_term_retry_batch_size": 5,
            "long_term_retry_max_attempts": 1,
        },
        paths,
    )
    job_id = _enqueue_music_job(engine)
    job = engine.store.claim_job_by_id(job_id)
    assert job is not None
    engine._record_job_failure(
        job,
        error_message="no_candidate_above_threshold",
        retryable=False,
        retry_delay_seconds=30,
    )

    summary = engine.process_long_term_retry_once()

    assert summary["claimed"] == 0
    assert summary["abandoned"] == 1
    queue = engine.store.summarize_long_term_retry_queue()
    assert queue["abandoned"] == 1

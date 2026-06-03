from __future__ import annotations

from pathlib import Path


APP_JS = Path(__file__).resolve().parent.parent / "webUI" / "app.js"


def test_local_music_playback_prefers_indexed_source_url_before_local_fallback() -> None:
    source = APP_JS.read_text()

    assert "async function resolveRecordingIndexedStreamUrl(recordingMbid)" in source
    assert "async function resolveRecordingIndexedStreamUrlWithTimeout(recordingMbid, timeoutMs = 900)" in source
    assert "? await resolveRecordingIndexedStreamUrlWithTimeout(payload.recording_mbid, 900)" in source
    assert ": await resolveRecordingStreamUrl(payload.recording_mbid" in source
    assert "if (!payload.stream_url && payload.local_path)" in source


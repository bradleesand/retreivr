from __future__ import annotations

from pathlib import Path


def test_music_webui_has_global_toast_region_and_no_modal_player() -> None:
    root = Path(__file__).resolve().parents[1]
    index_html = (root / "webUI" / "index.html").read_text(encoding="utf-8")

    assert 'id="app-toast-region"' in index_html
    assert 'id="music-player-modal"' not in index_html


def test_music_webui_exposes_notification_api_and_player_status_helper() -> None:
    root = Path(__file__).resolve().parents[1]
    app_js = (root / "webUI" / "app.js").read_text(encoding="utf-8")

    required_markers = [
        "const notificationState = {",
        "function notify(options = {}) {",
        "function clearNotifications(scope) {",
        "function setInlineStatus(target, options = {}) {",
        "function setMusicPlayerStatus(message, options = {}) {",
    ]

    for marker in required_markers:
        assert marker in app_js, f"missing notification helper marker: {marker}"

    assert "openMusicPlayerModal" not in app_js
    assert "closeMusicPlayerModal" not in app_js

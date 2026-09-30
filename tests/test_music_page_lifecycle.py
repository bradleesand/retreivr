from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_JS = (ROOT / "webUI" / "app.js").read_text(encoding="utf-8")
DISCOVERY_JS = (ROOT / "webUI" / "discovery.js").read_text(encoding="utf-8")


def _function_body(source: str, start: str, end: str) -> str:
    return source.split(start, 1)[1].split(end, 1)[0]


def test_music_page_activation_does_not_eagerly_load_hidden_tabs() -> None:
    set_page = _function_body(APP_JS, "function setPage(page)", "  if (target === \"status\")")

    assert "setMusicSection(requestedMusicSection)" in set_page
    assert "loadMusicPlayerView().catch" not in set_page
    assert "loadMusicLibrarySection().catch" not in set_page


def test_music_tab_loaders_only_render_the_active_section() -> None:
    set_section = _function_body(APP_JS, "function setMusicSection(section)", "function handleMusicBackToBrowse")
    player_loader = _function_body(APP_JS, "async function loadMusicPlayerView()", "async function playMusicPlayerItem")
    library_loader = _function_body(APP_JS, "async function loadMusicLibrarySection", "function renderMusicLibrarySection")

    assert 'if (effective === "library")' in set_section
    assert "loadMusicLibrarySection().catch" in set_section
    assert "musicPlayerLoadSequence" in player_loader
    assert "const canRenderPlayer = () =>" in player_loader
    assert '["favorites", "player", "radio"].includes' in player_loader
    assert "if (!canRenderPlayer())" in player_loader
    assert "musicLibraryLoadSequence" in library_loader
    assert "const canRenderLibrary = () =>" in library_loader
    assert 'state.musicSection === "library"' in library_loader


def test_music_landing_and_discovery_do_not_repaint_hidden_sections() -> None:
    home_snapshot = _function_body(APP_JS, "async function loadMusicHomeSnapshot", "function getSelectedHomeGenreFilters")
    landing = _function_body(APP_JS, "function renderMusicLanding()", "function normalizeHomeTrackItem")

    assert 'state.musicSection === "browse"' in home_snapshot
    assert 'state.musicSection !== "browse"' in landing
    assert "const isVisible = () =>" in DISCOVERY_JS
    assert "if (!isVisible()) return;" in DISCOVERY_JS
    assert "document.hidden && isVisible()" in DISCOVERY_JS

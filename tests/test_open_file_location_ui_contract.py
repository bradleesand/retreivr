from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WEBUI_APP = REPO_ROOT / "webUI" / "app.js"


def test_open_file_location_uses_backend_endpoint() -> None:
    source = WEBUI_APP.read_text(encoding="utf-8")
    assert 'await fetchJson("/api/files/open-location",' in source
    assert 'data-action="music-library-open-location"' in source
    assert 'data-action="video-library-open-location"' in source
    assert "This server cannot open a desktop file manager from Docker." in source


def test_video_recent_and_library_cards_share_actions() -> None:
    source = WEBUI_APP.read_text(encoding="utf-8")
    assert 'videoLibraryGrid.addEventListener("click", handleVideoLibraryGridClick)' in source
    assert 'videoDiscoveryPreviewGrid.addEventListener("click", handleVideoLibraryGridClick)' in source
    assert "function renderVideoLibraryCard" in source
    assert "function openVideoLibraryWatchHere" in source
    assert 'grid.style.setProperty("--home-video-card-min"' in source


def test_home_download_location_action_no_longer_uses_in_browser_browse() -> None:
    source = WEBUI_APP.read_text(encoding="utf-8")
    match = re.search(
        r"function buildHomeDownloadLocationAction\(filePath, fileId = \"\"\) \{.*?\n\}",
        source,
        re.DOTALL,
    )
    assert match is not None
    snippet = match.group(0)
    assert "openBrowser(" not in snippet
    assert "openFileLocation(" in snippet

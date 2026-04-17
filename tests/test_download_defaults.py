from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_download_defaults_module():
    module_name = "engine_download_defaults_test"
    module_path = Path(__file__).resolve().parents[1] / "engine" / "download_defaults.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules.pop(module_name, None)
    spec.loader.exec_module(module)
    return module


def test_normalize_download_media_mode_prefers_explicit_value() -> None:
    module = _load_download_defaults_module()
    assert module.normalize_download_media_mode("music_video", media_type="music", music_mode=True) == "music_video"


def test_resolve_effective_download_settings_video_uses_single_defaults_only() -> None:
    module = _load_download_defaults_module()
    result = module.resolve_effective_download_settings(
        {
            "single_download_folder": "Videos",
            "home_music_download_folder": "Music",
            "final_format": "mkv",
            "video_final_format": "mp4",
        },
        media_mode="video",
    )

    assert result["destination"] == "Videos"
    assert result["final_format"] == "mkv"


def test_resolve_effective_download_settings_music_prefers_home_music_defaults() -> None:
    module = _load_download_defaults_module()
    result = module.resolve_effective_download_settings(
        {
            "single_download_folder": "Videos",
            "music_download_folder": "Legacy Music",
            "home_music_download_folder": "Music",
            "music_final_format": "mp3",
            "home_music_final_format": "m4a",
        },
        media_mode="music",
    )

    assert result["destination"] == "Music"
    assert result["final_format"] == "m4a"


def test_resolve_effective_download_settings_music_video_prefers_music_video_defaults() -> None:
    module = _load_download_defaults_module()
    result = module.resolve_effective_download_settings(
        {
            "single_download_folder": "Videos",
            "home_music_video_download_folder": "Videos/Music Videos",
            "final_format": "mkv",
            "home_music_video_final_format": "mp4",
        },
        media_mode="music_video",
    )

    assert result["destination"] == "Videos/Music Videos"
    assert result["final_format"] == "mp4"


def test_resolve_effective_download_settings_explicit_values_override_defaults() -> None:
    module = _load_download_defaults_module()
    result = module.resolve_effective_download_settings(
        {
            "single_download_folder": "Videos",
            "final_format": "mkv",
        },
        media_mode="video",
        destination="Overrides/Custom",
        final_format_override="avi",
    )

    assert result["destination"] == "Overrides/Custom"
    assert result["final_format"] == "avi"

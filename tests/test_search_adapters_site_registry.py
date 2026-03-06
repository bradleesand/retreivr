from __future__ import annotations

import importlib.util
import json
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


def _load_search_adapters_module():
    if "engine" not in sys.modules:
        engine_pkg = types.ModuleType("engine")
        engine_pkg.__path__ = [str(_ROOT / "engine")]  # type: ignore[attr-defined]
        sys.modules["engine"] = engine_pkg
    _load_module("engine.json_utils", _ROOT / "engine" / "json_utils.py")
    return _load_module("engine_search_adapters_site_registry_test", _ROOT / "engine" / "search_adapters.py")


def test_default_adapters_include_new_site_sources():
    mod = _load_search_adapters_module()
    adapters = mod.default_adapters(config={})
    assert "bitchute" in adapters
    assert "x" in adapters
    assert "archive_org" in adapters
    assert "rumble" in adapters


def test_default_adapters_load_custom_site_adapter_from_json(tmp_path):
    mod = _load_search_adapters_module()
    custom_file = tmp_path / "custom_search_adapters.json"
    custom_file.write_text(
        json.dumps(
            {
                "version": 1,
                "adapters": [
                    {
                        "source": "my_video_mirror",
                        "type": "site_search",
                        "enabled": True,
                        "domains": ["media.example.org"],
                        "source_modifier": 0.77,
                        "query_suffix": "video",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    adapters = mod.default_adapters(config={"custom_search_adapters_file": str(custom_file)})
    assert "my_video_mirror" in adapters
    adapter = adapters["my_video_mirror"]
    assert getattr(adapter, "source", "") == "my_video_mirror"
    assert "media.example.org" in tuple(getattr(adapter, "domains", ()))

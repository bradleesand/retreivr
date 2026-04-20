from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WEBUI_APP = REPO_ROOT / "webUI" / "app.js"


def test_connections_health_cache_and_backoff_contract_present() -> None:
    source = WEBUI_APP.read_text(encoding="utf-8")
    assert "CONNECTIONS_HEALTH_TTL_MS" in source
    assert "servicesHealthCacheAt" in source
    assert "servicesHealthFailures" in source
    assert "servicesHealthBackoffUntil" in source
    assert "async function fetchConnectionsHealth" in source
    assert "Connections check is throttled" in source

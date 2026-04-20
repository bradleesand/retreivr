import sys
from pathlib import Path

import pytest

# Ensure tests can import project packages regardless of how pytest is invoked.
ROOT = Path(__file__).resolve().parents[1]
ROOT_STR = str(ROOT)
if ROOT_STR not in sys.path:
    sys.path.insert(0, ROOT_STR)

# Pre-import real external packages so that module-level stub guards in test files
# (e.g. `if "google.auth" not in sys.modules: sys.modules[...] = stub`) don't
# overwrite the real packages, which would persist across the entire test session.
import importlib as _importlib
for _pkg in (
    "google", "google.auth", "google.auth.exceptions", "google.auth.transport",
    "google.auth.transport.requests", "google.oauth2", "google.oauth2.credentials",
    "googleapiclient", "googleapiclient.discovery", "googleapiclient.errors",
    "google_auth_oauthlib", "google_auth_oauthlib.flow",
    "google_auth_oauthlib.helpers", "google_auth_oauthlib.interactive",
    "musicbrainzngs", "yt_dlp", "yt_dlp.version",
    "engine.music_export",
    "metadata.services", "metadata.services.musicbrainz_service",
):
    try:
        _importlib.import_module(_pkg)
    except ImportError:
        pass
del _importlib, _pkg


# Restore engine.job_queue in sys.modules after each test so that tests which
# inject a stub (e.g. test_mb_binding_paths.py) don't poison subsequent tests
# that need the real module.
_GUARDED_MODULES = (
    "engine",
    "engine.job_queue",
    "engine.core",
    "engine.musicbrainz_binding",
    "engine.music_export",
    "api.main",
    # External packages that some tests stub out
    "google",
    "google.auth",
    "google.auth.exceptions",
    "google.auth.transport",
    "google.auth.transport.requests",
    "google.oauth2",
    "google.oauth2.credentials",
    "googleapiclient",
    "googleapiclient.discovery",
    "googleapiclient.errors",
    "google_auth_oauthlib",
    "google_auth_oauthlib.flow",
    "google_auth_oauthlib.helpers",
    "google_auth_oauthlib.interactive",
    "musicbrainzngs",
    "yt_dlp",
    "yt_dlp.version",
    "metadata.services",
    "metadata.services.musicbrainz_service",
)


@pytest.fixture(autouse=True)
def _restore_guarded_sys_modules():
    saved = {k: sys.modules.get(k) for k in _GUARDED_MODULES}
    yield
    for key, original in saved.items():
        if original is None:
            sys.modules.pop(key, None)
        else:
            sys.modules[key] = original

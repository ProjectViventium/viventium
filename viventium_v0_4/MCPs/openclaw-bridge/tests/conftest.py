# VIVENTIUM START
# Test fixtures for openclaw-bridge tests.
# All fixtures respect the ACTUAL OpenClaw contracts (single port, correct config schema, etc.)
# VIVENTIUM END

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure the bridge code is importable
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(autouse=True)
def clean_env(request, monkeypatch, tmp_path):
    """Set safe test defaults before every unit test.

    Uses tmp_path to avoid touching real user data dirs.
    Skips for E2E tests (marked with 'e2e') which use real env vars.
    """
    # Skip env override for E2E tests — they use real keys from .env.local
    markers = {m.name for m in request.node.iter_markers()}
    if "e2e" in markers:
        return

    monkeypatch.setenv("OPENCLAW_DATA_DIR", str(tmp_path / "users"))
    monkeypatch.setenv("OPENCLAW_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("OPENCLAW_PORT_START", "29000")
    monkeypatch.setenv("OPENCLAW_PORT_END", "29100")
    monkeypatch.setenv("OPENCLAW_BIN", "openclaw")
    monkeypatch.setenv("OPENCLAW_BRIDGE_AUTH_TOKEN", "test-token")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
    monkeypatch.setenv("OPENCLAW_MODEL", "test-model/latest")
    monkeypatch.setenv("OPENCLAW_READINESS_TIMEOUT", "5")
    monkeypatch.setenv("OPENCLAW_BRIDGE_HOST", "127.0.0.1")
    monkeypatch.setenv("OPENCLAW_BRIDGE_PORT", "18086")
    monkeypatch.setenv("OPENCLAW_BRIDGE_SECRET", "test-secret")
    monkeypatch.setenv("OPENCLAW_RUNTIME", "direct")
    monkeypatch.setenv("OPENCLAW_RUNTIME_ALLOW_FALLBACK", "true")


@pytest.fixture
def fresh_manager(clean_env, tmp_path):
    """Create a fresh OpenClawManager with test-safe settings.

    Must import AFTER clean_env sets env vars, since module-level
    constants are evaluated at import time.
    """
    import importlib
    import openclaw_manager as mgr

    # Patch module-level constants that were evaluated at first import
    with patch.object(mgr, "DATA_DIR", Path(tmp_path / "users")), \
         patch.object(mgr, "LOG_DIR", Path(tmp_path / "logs")), \
         patch.object(mgr, "PORT_RANGE_START", 29000), \
         patch.object(mgr, "PORT_RANGE_END", 29100), \
         patch.object(mgr, "OPENCLAW_RUNTIME", "direct"), \
         patch.object(mgr, "OPENCLAW_BIN", "openclaw"), \
         patch.object(mgr, "OPENCLAW_BRIDGE_AUTH_TOKEN", "test-token"), \
         patch.object(mgr, "OPENCLAW_MODEL", "test-model/latest"), \
         patch.object(mgr, "READINESS_TIMEOUT", 5):
        manager = mgr.OpenClawManager()
        yield manager


@pytest.fixture
def mock_httpx():
    """Mock httpx.AsyncClient for testing HTTP calls."""
    with patch("httpx.AsyncClient") as mock_class:
        mock_client = AsyncMock()
        mock_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_class.return_value.__aexit__ = AsyncMock(return_value=False)
        yield mock_client

# VIVENTIUM START
# E2E test for openclaw_status — requires a running openclaw-bridge server.
# Run with: pytest tests/test_e2e_status.py -v -m integration
# VIVENTIUM END

import os

import httpx
import pytest

pytestmark = pytest.mark.integration

BRIDGE_URL = os.environ.get("OPENCLAW_BRIDGE_URL", "http://127.0.0.1:8086")


class TestE2EStatus:
    """E2E: bridge health check."""

    def test_bridge_health(self):
        """Bridge /health returns ok (this is the MCP server's health, not OpenClaw's)."""
        resp = httpx.get(f"{BRIDGE_URL}/health", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "openclaw-bridge"
        assert "active_instances" in data

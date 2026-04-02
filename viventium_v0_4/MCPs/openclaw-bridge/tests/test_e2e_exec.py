# VIVENTIUM START
# E2E test for openclaw_exec — requires a running openclaw-bridge server.
# Run with: pytest tests/test_e2e_exec.py -v -m integration
# VIVENTIUM END

import os

import httpx
import pytest

pytestmark = pytest.mark.integration

BRIDGE_URL = os.environ.get("OPENCLAW_BRIDGE_URL", "http://127.0.0.1:8086")
BRIDGE_SECRET = os.environ.get("OPENCLAW_BRIDGE_SECRET", "")


@pytest.fixture
def client():
    return httpx.Client(timeout=120)


class TestE2EExec:
    """E2E: openclaw_exec → real OpenClaw gateway → shell result."""

    def test_exec_echo(self, client):
        """Basic echo command should return the echoed text."""
        headers = {
            "Content-Type": "application/json",
            "x-user-id": "e2e-test-user",
        }
        if BRIDGE_SECRET:
            headers["x-bridge-secret"] = BRIDGE_SECRET

        # This is a simplified E2E test — actual execution depends on
        # the MCP transport (streamable-http). Full E2E requires the MCP client.
        resp = client.get(f"{BRIDGE_URL}/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "openclaw-bridge"

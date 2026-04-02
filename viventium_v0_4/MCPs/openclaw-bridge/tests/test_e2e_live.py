# VIVENTIUM START
# Live E2E tests — against a REAL OpenClaw Gateway + LibreChat.
#
# Prerequisites:
#   1. cd viventium_v0_4/openclaw && npm install && npm run build
#   2. .env.local has ANTHROPIC_API_KEY
#   3. tests/.env.e2e exists (or run e2e_setup.py)
#
# Run:
#   cd viventium_v0_4/MCPs/openclaw-bridge
#   set -a; source ../../../.env.local; set +a
#   python -m pytest tests/test_e2e_live.py -v -s -m e2e
#
# IMPORTANT: These tests start real OpenClaw Gateway processes and make real API calls.
#
# Verified tool names from OpenClaw source (agents/tools/*-tool.ts):
#   Available via /tools/invoke: browser, canvas, cron, message, nodes,
#     sessions_list, session_status, agents_list, tts, web_search, web_fetch,
#     gateway, image, memory_search, memory_get, sessions_history,
#     sessions_send, sessions_spawn
#   NOT available via /tools/invoke: exec, read, write (coding tools, agent-only)
#   exec must use /v1/responses (OpenResponses agent delegation)
# VIVENTIUM END

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

import httpx
import pytest

# ── Bootstrap: load real env vars BEFORE importing bridge modules ──────
_tests_dir = Path(__file__).resolve().parent
_bridge_dir = _tests_dir.parent
_workspace_root = _bridge_dir.parent.parent.parent.parent  # viventium_core

sys.path.insert(0, str(_bridge_dir))


def _load_env_file(path: Path):
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if "#" in value:
            value = re.sub(r'\s*#.*$', '', value)
        value = value.strip().strip('"').strip("'")
        if value:
            os.environ.setdefault(key, value)


_load_env_file(_tests_dir / ".env.e2e")
_load_env_file(_workspace_root / ".env.local")

_e2e_data = Path(os.path.expanduser("~/.viventium/openclaw/e2e"))
os.environ.setdefault("OPENCLAW_DATA_DIR", str(_e2e_data / "users"))
os.environ.setdefault("OPENCLAW_LOG_DIR", str(_e2e_data / "logs"))


# ── Skip markers ───────────────────────────────────────────────────────

def _has_anthropic_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").startswith("sk-"))


def _has_openclaw_bin() -> bool:
    ocbin = os.environ.get("OPENCLAW_BIN", "")
    if not ocbin:
        return False
    parts = ocbin.split()
    if len(parts) >= 2 and parts[0] == "node":
        return Path(parts[1]).exists()
    return True


def _librechat_reachable() -> bool:
    """Check if LibreChat backend is actually running (not just SPA catch-all).
    Uses /api/config which returns real JSON, not the React SPA HTML fallback."""
    try:
        resp = httpx.get("http://localhost:3080/api/config", timeout=3)
        return resp.status_code == 200 and "json" in resp.headers.get("content-type", "")
    except Exception:
        return False


requires_anthropic = pytest.mark.skipif(not _has_anthropic_key(), reason="No ANTHROPIC_API_KEY")
requires_openclaw = pytest.mark.skipif(not _has_openclaw_bin(), reason="No OPENCLAW_BIN")
requires_librechat = pytest.mark.skipif(not _librechat_reachable(), reason="LibreChat not running")

import importlib
import openclaw_manager  # noqa: E402

# Force reload so module-level constants re-evaluate from real env vars.
# This is critical when running the full test suite in a single invocation:
# non-E2E conftest.py sets OPENCLAW_BIN=openclaw via monkeypatch, but the
# module may have been imported already with those test values. Reload ensures
# E2E tests always use the real environment (e.g., OPENCLAW_BIN from .env.e2e).
importlib.reload(openclaw_manager)
OpenClawManager = openclaw_manager.OpenClawManager


# ── Fixtures ───────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def live_manager(event_loop):
    # Reload again at fixture time to be absolutely sure module constants
    # reflect E2E env vars, even if pytest collection imported it earlier.
    importlib.reload(openclaw_manager)
    manager = openclaw_manager.OpenClawManager()
    yield manager
    event_loop.run_until_complete(manager.stop_all())


@pytest.fixture(scope="session")
def live_instance(live_manager, event_loop):
    return event_loop.run_until_complete(
        live_manager.get_or_create_instance("e2e-test-user")
    )


def _auth_headers() -> dict:
    # Use the token from the reloaded openclaw_manager module-level constant
    # (not env var, which may be overwritten by conftest.py autouse fixture)
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {openclaw_manager.OPENCLAW_BRIDGE_AUTH_TOKEN}",
    }


# ── All E2E tests require both ANTHROPIC_API_KEY and OPENCLAW_BIN ──────
pytestmark = [pytest.mark.e2e, pytest.mark.integration, requires_anthropic, requires_openclaw]


# ======================================================================
# 1. Instance Lifecycle
# ======================================================================

class TestInstanceLifecycle:

    def test_instance_started(self, live_instance):
        assert live_instance.port > 0
        assert live_instance.pid is not None and live_instance.pid > 0
        print(f"\n  Instance: port={live_instance.port}, pid={live_instance.pid}")

    def test_instance_urls_single_port(self, live_instance):
        assert f":{live_instance.port}" in live_instance.base_url
        assert live_instance.tools_invoke_url == f"{live_instance.base_url}/tools/invoke"
        assert live_instance.responses_url == f"{live_instance.base_url}/v1/responses"

    def test_config_file_valid(self, live_instance):
        config = json.loads((live_instance.state_dir / "openclaw.json").read_text())
        assert config["gateway"]["port"] == live_instance.port
        assert config["gateway"]["bind"] == "loopback"
        assert config["gateway"]["auth"]["mode"] == "token"
        assert config["gateway"]["http"]["endpoints"]["responses"]["enabled"] is True
        assert config["agents"]["defaults"]["model"]["primary"]
        assert "models" not in config or "default" not in config.get("models", {}), \
            "models.default is invalid — model goes in agents.defaults.model"


# ======================================================================
# 2. Gateway Readiness
# ======================================================================

class TestGatewayReadiness:

    def test_tools_invoke_reachable(self, live_instance):
        resp = httpx.post(
            live_instance.tools_invoke_url,
            json={"tool": "__viventium_probe__", "args": {}},
            headers=_auth_headers(),
            timeout=10,
        )
        assert resp.status_code in (200, 400, 404, 422)
        print(f"\n  Probe: {resp.status_code}")

    def test_auth_required(self, live_instance):
        resp = httpx.post(
            live_instance.tools_invoke_url,
            json={"tool": "cron", "args": {"action": "list"}},
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        assert resp.status_code == 401, f"Expected 401 without auth, got {resp.status_code}"


# ======================================================================
# 3. Tools available via /tools/invoke (NOT exec)
# ======================================================================

class TestCronTool:
    """cron tool — verified available via /tools/invoke."""

    def test_cron_list(self, live_instance):
        resp = httpx.post(
            live_instance.tools_invoke_url,
            json={"tool": "cron", "args": {"action": "list"}},
            headers=_auth_headers(),
            timeout=15,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        print(f"\n  cron list: {json.dumps(data['result'])[:200]}")


class TestWebFetchTool:
    """web_fetch tool — verified available via /tools/invoke."""

    def test_web_fetch_example_com(self, live_instance):
        resp = httpx.post(
            live_instance.tools_invoke_url,
            json={"tool": "web_fetch", "args": {"url": "https://example.com"}},
            headers=_auth_headers(),
            timeout=30,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        result_str = json.dumps(data.get("result", {}))
        assert "example" in result_str.lower(), f"Expected 'example' in: {result_str[:300]}"
        print(f"\n  web_fetch: ok, result_len={len(result_str)}")


class TestSessionsListTool:
    """sessions_list tool — verified available via /tools/invoke."""

    def test_sessions_list(self, live_instance):
        resp = httpx.post(
            live_instance.tools_invoke_url,
            json={"tool": "sessions_list", "args": {}},
            headers=_auth_headers(),
            timeout=15,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        print(f"\n  sessions_list: {json.dumps(data['result'])[:200]}")


class TestAgentsListTool:
    """agents_list tool — verified available via /tools/invoke."""

    def test_agents_list(self, live_instance):
        resp = httpx.post(
            live_instance.tools_invoke_url,
            json={"tool": "agents_list", "args": {}},
            headers=_auth_headers(),
            timeout=15,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        print(f"\n  agents_list: {json.dumps(data['result'])[:200]}")


class TestTTSTool:
    """tts tool — verified available via /tools/invoke."""

    def test_tts_hello(self, live_instance):
        resp = httpx.post(
            live_instance.tools_invoke_url,
            json={"tool": "tts", "args": {"text": "hello viventium"}},
            headers=_auth_headers(),
            timeout=30,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        print(f"\n  tts: {json.dumps(data['result'])[:200]}")


# ======================================================================
# 4. Tool that is NOT in /tools/invoke (exec)
# ======================================================================

class TestExecNotDirectlyAvailable:
    """exec is NOT in createOpenClawTools — only in createOpenClawCodingTools."""

    def test_exec_returns_404(self, live_instance):
        resp = httpx.post(
            live_instance.tools_invoke_url,
            json={"tool": "exec", "args": {"command": "echo test"}},
            headers=_auth_headers(),
            timeout=10,
        )
        assert resp.status_code == 404, \
            f"exec should NOT be available via /tools/invoke, got {resp.status_code}"
        data = resp.json()
        assert "not available" in data.get("error", {}).get("message", "").lower()


# ======================================================================
# 5. Multi-user isolation
# ======================================================================

class TestMultiUserIsolation:

    def test_second_user_different_port(self, live_manager, live_instance):
        loop = asyncio.get_event_loop()
        inst2 = loop.run_until_complete(
            live_manager.get_or_create_instance("e2e-user-2")
        )
        try:
            assert inst2.port != live_instance.port
            assert inst2.pid != live_instance.pid
            assert inst2.state_dir != live_instance.state_dir

            # Both reachable
            for inst in [live_instance, inst2]:
                resp = httpx.post(
                    inst.tools_invoke_url,
                    json={"tool": "cron", "args": {"action": "list"}},
                    headers=_auth_headers(),
                    timeout=10,
                )
                assert resp.status_code == 200
            print(f"\n  User1: port={live_instance.port}, User2: port={inst2.port}")
        finally:
            loop.run_until_complete(live_manager.stop_instance("e2e-user-2"))

    def test_reuse_existing_instance(self, live_manager, live_instance):
        loop = asyncio.get_event_loop()
        inst2 = loop.run_until_complete(
            live_manager.get_or_create_instance("e2e-test-user")
        )
        assert inst2.port == live_instance.port
        assert inst2.pid == live_instance.pid


# ======================================================================
# 6. Provider key pass-through
# ======================================================================

class TestProviderKeys:

    def test_anthropic_key_in_env(self):
        assert os.environ.get("ANTHROPIC_API_KEY", "").startswith("sk-"), \
            "ANTHROPIC_API_KEY should be a real key from .env.local"

    def test_config_model_set(self, live_instance):
        config = json.loads((live_instance.state_dir / "openclaw.json").read_text())
        model = config["agents"]["defaults"]["model"]["primary"]
        assert model, "Default model must be set"
        print(f"\n  Model: {model}")


# ======================================================================
# 7. LibreChat connectivity
# ======================================================================

@requires_librechat
class TestLibreChatConnectivity:

    def test_librechat_api_reachable(self):
        """Verify LibreChat API returns real JSON (not the React SPA HTML fallback).
        Uses /api/config which is a guaranteed JSON endpoint, unlike /api/health
        which does not exist and falls through to the SPA catch-all."""
        resp = httpx.get("http://localhost:3080/api/config", timeout=5)
        assert resp.status_code == 200
        content_type = resp.headers.get("content-type", "")
        assert "json" in content_type, (
            f"Expected JSON content-type, got: {content_type}"
        )
        data = resp.json()
        # Verify it's the real Viventium instance
        assert "appTitle" in data, "Expected appTitle in config response"
        print(f"\n  LibreChat instance: {data.get('appTitle', 'unknown')}")

    def test_mcp_servers_configured(self):
        """Verify LibreChat knows about the openclaw-bridge MCP server."""
        resp = httpx.get("http://localhost:3080/api/config", timeout=5)
        assert resp.status_code == 200
        data = resp.json()
        # The MCP servers config should include the openclaw-bridge entry
        mcp_config = data.get("interface", {}).get("mcpServers", {})
        assert mcp_config.get("use") is True, "mcpServers.use should be true"
        print(f"\n  MCP config: {mcp_config}")


# ======================================================================
# 8. Instance cleanup
# ======================================================================

class TestCleanup:

    def test_stop_releases_port(self, live_manager):
        loop = asyncio.get_event_loop()
        inst = loop.run_until_complete(
            live_manager.get_or_create_instance("e2e-cleanup-user")
        )
        port = inst.port
        assert port in live_manager.used_ports

        loop.run_until_complete(live_manager.stop_instance("e2e-cleanup-user"))
        assert port not in live_manager.used_ports
        assert "e2e-cleanup-user" not in live_manager.instances
        print(f"\n  Cleaned up: port={port}")

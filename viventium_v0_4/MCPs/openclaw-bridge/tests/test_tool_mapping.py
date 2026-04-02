# VIVENTIUM START
# Tests for tool argument mapping — validates payloads match
# OpenClaw's POST /tools/invoke body format.
#
# Source: openclaw/src/gateway/tools-invoke-http.ts
# Body: { tool: string, args?: object, sessionKey?: string }
#
# IMPORTANT: Action fields go INSIDE args, not as a top-level field.
# Verified against real OpenClaw 2026.2.10 gateway.
# VIVENTIUM END

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestToolPayloads:
    """Each MCP tool must produce a valid /tools/invoke payload."""

    @pytest.mark.asyncio
    async def test_cron_payload(self):
        """cron: action is inside args, not top-level."""
        from mcp_server import _invoke_tool
        import openclaw_manager as mgr

        inst = mgr.OpenClawInstance(user_id="u1", port=29000, state_dir=Path("/tmp"))

        with patch("mcp_server._get_instance", new_callable=AsyncMock, return_value=inst):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"ok": True, "result": "output"}
            mock_resp.raise_for_status = MagicMock()

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)

            with patch("httpx.AsyncClient") as mock_class:
                mock_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                mock_class.return_value.__aexit__ = AsyncMock(return_value=False)

                await _invoke_tool("cron", {"action": "list"})

            call_args = mock_client.post.call_args
            payload = call_args.kwargs.get("json") or call_args[1].get("json")

            assert payload["tool"] == "cron"
            assert payload["args"]["action"] == "list"
            assert "sessionKey" in payload
            # No top-level "action" key
            assert "action" not in payload or payload.get("action") is None

    @pytest.mark.asyncio
    async def test_no_top_level_action(self):
        """_invoke_tool does NOT produce a top-level 'action' field.
        All actions go inside args.
        """
        from mcp_server import _invoke_tool
        import openclaw_manager as mgr

        inst = mgr.OpenClawInstance(user_id="u1", port=29000, state_dir=Path("/tmp"))

        with patch("mcp_server._get_instance", new_callable=AsyncMock, return_value=inst):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"ok": True, "result": "ok"}
            mock_resp.raise_for_status = MagicMock()

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)

            with patch("httpx.AsyncClient") as mock_class:
                mock_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                mock_class.return_value.__aexit__ = AsyncMock(return_value=False)

                await _invoke_tool("nodes", {"action": "list"})

            call_args = mock_client.post.call_args
            payload = call_args.kwargs.get("json") or call_args[1].get("json")

            # Payload should only have: tool, args, sessionKey
            assert set(payload.keys()) == {"tool", "args", "sessionKey"}

    @pytest.mark.asyncio
    async def test_session_key_default(self):
        """Default sessionKey should be 'viventium-main'."""
        from mcp_server import _invoke_tool
        import openclaw_manager as mgr

        inst = mgr.OpenClawInstance(user_id="u1", port=29000, state_dir=Path("/tmp"))

        with patch("mcp_server._get_instance", new_callable=AsyncMock, return_value=inst):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"ok": True, "result": "ok"}
            mock_resp.raise_for_status = MagicMock()

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)

            with patch("httpx.AsyncClient") as mock_class:
                mock_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                mock_class.return_value.__aexit__ = AsyncMock(return_value=False)

                await _invoke_tool("cron", {"action": "list"})

            call_args = mock_client.post.call_args
            payload = call_args.kwargs.get("json") or call_args[1].get("json")

            assert payload["sessionKey"] == "viventium-main"

# VIVENTIUM START
# Tests for mcp_server.py VM-scoped MCP surface.
# VIVENTIUM END

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from fastmcp.exceptions import ToolError

import openclaw_manager as mgr


class TestSecurity:
    def test_default_host_is_loopback(self):
        import mcp_server

        assert mcp_server.MCP_HOST == "127.0.0.1" or "127.0.0.1" in str(mcp_server.MCP_HOST)

    def test_sanitize_header_rejects_templates(self):
        from mcp_server import _sanitize_header_value

        assert _sanitize_header_value("{{user_id}}") == ""
        assert _sanitize_header_value("${USER_ID}") == ""
        assert _sanitize_header_value(None) == ""
        assert _sanitize_header_value("real-user") == "real-user"

    def test_get_user_id_requires_matching_secret(self):
        from mcp_server import _get_user_id

        with patch("mcp_server._get_request_headers", return_value={"x-user-id": "alice"}):
            with patch("mcp_server.BRIDGE_SECRET", "secret"):
                with pytest.raises(ValueError, match="Forbidden"):
                    _get_user_id()

    def test_get_user_id_accepts_only_the_exact_secret(self):
        from mcp_server import _get_user_id

        with patch("mcp_server.BRIDGE_SECRET", "expected-secret"):
            with patch(
                "mcp_server._get_request_headers",
                return_value={"x-bridge-secret": "wrong-secret", "x-user-id": "alice"},
            ):
                with pytest.raises(ValueError, match="Forbidden"):
                    _get_user_id()
            with patch(
                "mcp_server._get_request_headers",
                return_value={"x-bridge-secret": "expected-secret", "x-user-id": "alice"},
            ):
                assert _get_user_id() == "alice"

    def test_bridge_secret_comparison_is_constant_time(self):
        import inspect
        import mcp_server

        assert "hmac.compare_digest" in inspect.getsource(mcp_server._get_user_id)

    def test_every_startup_requires_bridge_secret_even_on_loopback(self):
        import mcp_server

        with patch("mcp_server.BRIDGE_SECRET", ""):
            with pytest.raises(RuntimeError, match="required"):
                mcp_server.create_app(host="127.0.0.1", port=8086)


class TestInvokeTool:
    @pytest.mark.asyncio
    async def test_payload_and_auth_headers(self, fresh_manager):
        import mcp_server

        inst = mgr.OpenClawInstance(
            user_id="u1",
            vm_id="001",
            port=29000,
            state_dir=Path("/tmp/test"),
            gateway_token="vm-token",
        )

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"ok": True, "result": {"x": 1}}
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient") as mock_class:
            mock_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_class.return_value.__aexit__ = AsyncMock(return_value=False)
            with patch.object(mcp_server, "manager", fresh_manager):
                fresh_manager._set_instance(inst)
                with patch("mcp_server._get_user_id", return_value="u1"), patch.object(
                    fresh_manager, "_is_alive", new_callable=AsyncMock, return_value=True
                ):
                    out = await mcp_server._invoke_tool("cron", {"action": "list"})

        call_kwargs = mock_client.post.call_args.kwargs
        assert call_kwargs["json"]["tool"] == "cron"
        assert call_kwargs["json"]["args"] == {"action": "list"}
        assert call_kwargs["json"]["sessionKey"] == "viventium-main"
        assert call_kwargs["headers"]["Authorization"] == "Bearer vm-token"
        assert '"x": 1' in out

    @pytest.mark.asyncio
    async def test_vm_id_is_passed_to_instance_resolution(self):
        import mcp_server

        inst = mgr.OpenClawInstance(
            user_id="u1",
            vm_id="002",
            port=29001,
            state_dir=Path("/tmp/test"),
            gateway_token="vm2-token",
        )

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"ok": True, "result": "ok"}
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient") as mock_class:
            mock_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_class.return_value.__aexit__ = AsyncMock(return_value=False)
            with patch("mcp_server._get_instance", new_callable=AsyncMock, return_value=inst) as mock_get:
                await mcp_server._invoke_tool("browser", {"action": "snapshot"}, vm_id="002")
                mock_get.assert_called_once_with(vm_id="002")


class TestMCPToolRegistration:
    @pytest.mark.asyncio
    async def test_vm_tools_registered(self):
        from mcp_server import mcp

        tool_names = {tool.name for tool in await mcp.list_tools()}
        expected = {
            "openclaw_vm_start",
            "openclaw_vm_resume",
            "openclaw_vm_stop",
            "openclaw_vm_terminate",
            "openclaw_vm_list",
            "openclaw_vm_status",
            "openclaw_vm_takeover",
            "openclaw_exec",
            "openclaw_browser",
            "openclaw_agent",
            "openclaw_status",
        }
        assert expected.issubset(tool_names)


class TestAuthenticatedMCPTransport:
    @staticmethod
    def _transport(app, headers: dict[str, str]) -> StreamableHttpTransport:
        def client_factory(**kwargs):
            return httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://openclaw-bridge.test",
                **kwargs,
            )

        return StreamableHttpTransport(
            "http://openclaw-bridge.test/mcp",
            headers=headers,
            httpx_client_factory=client_factory,
        )

    @pytest.mark.asyncio
    async def test_authenticated_initialize_and_tool_call(self):
        import mcp_server

        fake_manager = MagicMock()
        fake_manager.list_instances.return_value = []
        fake_manager.schedule_cleanup.return_value = None
        fake_manager.stop_all = AsyncMock()
        app = mcp_server.mcp.http_app()
        transport = self._transport(
            app,
            {"x-bridge-secret": "test-secret", "x-user-id": "synthetic-user"},
        )

        with patch.object(mcp_server, "manager", fake_manager), patch.object(
            mcp_server, "BRIDGE_SECRET", "test-secret"
        ):
            async with app.router.lifespan_context(app):
                async with Client(transport) as client:
                    tools = {tool.name for tool in await client.list_tools()}
                    result = await client.call_tool("openclaw_vm_list", {})

        assert "openclaw_vm_list" in tools
        assert result.is_error is False
        assert "synthetic-user" in str(result.content)
        fake_manager.list_instances.assert_called_once_with(user_id="synthetic-user")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("provided_secret", [None, "wrong-secret"])
    async def test_missing_or_wrong_secret_rejects_tool_call(self, provided_secret):
        import mcp_server

        fake_manager = MagicMock()
        fake_manager.list_instances.return_value = []
        fake_manager.schedule_cleanup.return_value = None
        fake_manager.stop_all = AsyncMock()
        app = mcp_server.mcp.http_app()
        headers = {"x-user-id": "synthetic-user"}
        if provided_secret is not None:
            headers["x-bridge-secret"] = provided_secret
        transport = self._transport(app, headers)

        with patch.object(mcp_server, "manager", fake_manager), patch.object(
            mcp_server, "BRIDGE_SECRET", "test-secret"
        ):
            async with app.router.lifespan_context(app):
                async with Client(transport) as client:
                    with pytest.raises(ToolError, match="Forbidden"):
                        await client.call_tool("openclaw_vm_list", {})

        fake_manager.list_instances.assert_not_called()


class TestToolArgMapping:
    @pytest.mark.asyncio
    async def test_browser_routes_vm_id(self):
        from mcp_server import openclaw_browser

        with patch("mcp_server._invoke_tool", new_callable=AsyncMock, return_value="ok") as mock:
            fn = openclaw_browser.fn if hasattr(openclaw_browser, "fn") else openclaw_browser
            await fn(action="navigate", url="https://example.com", vm_id="007")
            mock.assert_called_once_with(
                "browser",
                {"action": "navigate", "targetUrl": "https://example.com"},
                vm_id="007",
            )

    @pytest.mark.asyncio
    async def test_web_fetch_routes_vm_id(self):
        from mcp_server import openclaw_web_fetch

        with patch("mcp_server._invoke_tool", new_callable=AsyncMock, return_value="ok") as mock:
            fn = openclaw_web_fetch.fn if hasattr(openclaw_web_fetch, "fn") else openclaw_web_fetch
            await fn(url="https://example.com", vm_id="003")
            mock.assert_called_once_with("web_fetch", {"url": "https://example.com"}, vm_id="003")

    @pytest.mark.asyncio
    async def test_exec_routes_vm_id_to_instance_resolution(self):
        import mcp_server

        inst = mgr.OpenClawInstance(
            user_id="u1",
            vm_id="002",
            port=29001,
            state_dir=Path("/tmp/test"),
            gateway_token="vm2-token",
        )

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": "hello from vm2"}],
                }
            ]
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)

        with patch("httpx.AsyncClient") as mock_class:
            mock_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_class.return_value.__aexit__ = AsyncMock(return_value=False)
            with patch("mcp_server._get_instance", new_callable=AsyncMock, return_value=inst) as mock_get:
                fn = mcp_server.openclaw_exec.fn if hasattr(mcp_server.openclaw_exec, "fn") else mcp_server.openclaw_exec
                out = await fn(command="echo hello", vm_id="002")

        mock_get.assert_called_once_with(vm_id="002")
        assert "hello from vm2" in out


class TestVmLifecycleTools:
    @pytest.mark.asyncio
    async def test_vm_start_routes_to_manager(self):
        import mcp_server

        fake_manager = MagicMock()
        fake_manager.start_instance = AsyncMock(
            return_value=mgr.OpenClawInstance(user_id="demo", vm_id="001", runtime="e2b", sandbox_id="sb-1")
        )
        fake_manager.get_instance_info.return_value = {
            "user_id": "demo",
            "vm_id": "001",
            "runtime": "e2b",
            "sandbox_id": "sb-1",
            "state": "running",
        }

        with patch.object(mcp_server, "manager", fake_manager), patch("mcp_server._get_user_id", return_value="demo"):
            fn = mcp_server.openclaw_vm_start.fn if hasattr(mcp_server.openclaw_vm_start, "fn") else mcp_server.openclaw_vm_start
            out = await fn(vm_id="1")

        fake_manager.start_instance.assert_awaited_once_with("demo", "001")
        payload = json.loads(out)
        assert payload["event"] == "started"
        assert payload["vm_id"] == "001"

    @pytest.mark.asyncio
    async def test_vm_takeover_payload_shape(self):
        import mcp_server

        fake_manager = MagicMock()
        fake_manager.takeover_instance = AsyncMock(
            return_value={
                "user_id": "demo",
                "vm_id": "001",
                "runtime": "e2b",
                "sandbox_id": "sb-1",
                "desktop_url": "https://desktop.example",
                "desktop_auth_key": "auth-123",
                "view_only": False,
                "require_auth": True,
            }
        )

        with patch.object(mcp_server, "manager", fake_manager), patch("mcp_server._get_user_id", return_value="demo"):
            fn = (
                mcp_server.openclaw_vm_takeover.fn
                if hasattr(mcp_server.openclaw_vm_takeover, "fn")
                else mcp_server.openclaw_vm_takeover
            )
            out = await fn(vm_id="001", require_auth=True, view_only=False)

        payload = json.loads(out)
        assert payload["event"] == "takeover_ready"
        assert payload["desktop_url"].startswith("https://")
        assert payload["desktop_auth_key"]

    @pytest.mark.asyncio
    async def test_openclaw_status_aliases_vm_status(self):
        import mcp_server

        with patch("mcp_server.openclaw_vm_status", new_callable=AsyncMock, return_value="{}") as mock:
            fn = mcp_server.openclaw_status.fn if hasattr(mcp_server.openclaw_status, "fn") else mcp_server.openclaw_status
            await fn(vm_id="002")
            mock.assert_awaited_once_with(vm_id="002")

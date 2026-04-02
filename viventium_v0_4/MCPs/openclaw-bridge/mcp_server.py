# VIVENTIUM START
# Purpose: MCP Server that bridges Viventium agents to OpenClaw Gateway.
#
# Ground truth contracts:
#   - OpenClaw Gateway: single multiplexed port (WS+HTTP)
#   - POST /tools/invoke: { tool, action?, args, sessionKey? } — Bearer auth
#   - POST /v1/responses: OpenResponses API — requires gateway.http.endpoints.responses.enabled
#   - No /health HTTP endpoint (health is WS RPC only)
#   - Auth: gateway.auth.mode=token, token=OPENCLAW_GATEWAY_TOKEN
#
# Security:
#   - Default bind: 127.0.0.1 (loopback only)
#   - MCP bridge auth: OPENCLAW_BRIDGE_SECRET env var (required for non-loopback)
#   - X-User-Id header trusted only when secret matches
#
# Source: openclaw/src/gateway/tools-invoke-http.ts
# VIVENTIUM END

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Dict, Optional

import httpx
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers

from openclaw_manager import (
    OpenClawManager,
    OpenClawInstance,
    OPENCLAW_DEFAULT_VM_ID,
    OPENCLAW_BRIDGE_AUTH_TOKEN,
    normalize_vm_id,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ============== CONFIGURATION ==============

MCP_PORT = int(os.environ.get("OPENCLAW_BRIDGE_PORT", "8086"))
# Default: loopback only. Override to 0.0.0.0 ONLY with OPENCLAW_BRIDGE_SECRET set.
MCP_HOST = os.environ.get("OPENCLAW_BRIDGE_HOST", "127.0.0.1")
# Shared secret between LibreChat and this MCP server
BRIDGE_SECRET = os.environ.get("OPENCLAW_BRIDGE_SECRET", "")
HEADER_USER_ID = "x-user-id"
TOOL_TIMEOUT = int(os.environ.get("OPENCLAW_TOOL_TIMEOUT", "120"))  # seconds

# ============== HELPER FUNCTIONS ==============


def _normalize_headers(raw_headers: object) -> Dict[str, str]:
    """Normalize headers from various formats to a simple dict."""
    if raw_headers is None:
        return {}
    if hasattr(raw_headers, "items"):
        items = raw_headers.items()
    elif isinstance(raw_headers, list):
        items = raw_headers
    else:
        return {}
    return {str(key).lower(): str(value) for key, value in items}


def _get_request_headers() -> Dict[str, str]:
    try:
        return _normalize_headers(get_http_headers())
    except Exception:
        return {}


def _sanitize_header_value(value: Optional[str]) -> str:
    if not value:
        return ""
    stripped = value.strip()
    if stripped.startswith("{{") and stripped.endswith("}}"):
        return ""
    if stripped.startswith("${") and stripped.endswith("}"):
        return ""
    return stripped


def _get_user_id() -> str:
    """Get user_id from request headers.

    When OPENCLAW_BRIDGE_SECRET is set, the x-bridge-secret header must
    match before trusting x-user-id. This prevents header spoofing when
    the MCP server is exposed beyond loopback.
    """
    headers = _get_request_headers()

    # Verify bridge secret if configured — hard-fail on mismatch to prevent
    # user-isolation collapse under misconfiguration or exposure.
    if BRIDGE_SECRET:
        provided_secret = headers.get("x-bridge-secret", "")
        if provided_secret != BRIDGE_SECRET:
            logger.error("Bridge secret mismatch — rejecting request (security: isolation collapse risk)")
            raise ValueError("Forbidden: invalid bridge secret")

    user_id = _sanitize_header_value(headers.get(HEADER_USER_ID))
    if not user_id:
        user_id = "default-user"
    return user_id


# ============== MCP SERVER ==============

mcp = FastMCP(
    "Viventium OpenClaw Bridge",
    instructions=(
        "Bridge to OpenClaw Gateway — provides shell execution, browser automation, "
        "multi-channel messaging, cron scheduling, device nodes, canvas, and full "
        "agent delegation. Each user has an isolated OpenClaw environment."
    ),
)

# Global manager instance — created at startup
manager: Optional[OpenClawManager] = None


def _auth_headers(instance: OpenClawInstance) -> Dict[str, str]:
    token = instance.gateway_token or OPENCLAW_BRIDGE_AUTH_TOKEN
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }


async def _get_instance(vm_id: str = OPENCLAW_DEFAULT_VM_ID) -> OpenClawInstance:
    """Resolve the current user's OpenClaw instance for a specific VM."""
    assert manager is not None, "OpenClawManager not initialized"
    user_id = _get_user_id()
    return await manager.get_or_create_instance(user_id, normalize_vm_id(vm_id))


async def _invoke_tool(
    tool_name: str,
    args: dict,
    vm_id: str = OPENCLAW_DEFAULT_VM_ID,
    session_key: str = "viventium-main",
) -> str:
    """Call OpenClaw's POST /tools/invoke endpoint for the current user.

    Body format (from tools-invoke-http.ts):
        { tool: string, args?: object, sessionKey?: string }
    Tool-specific 'action' fields go INSIDE args, not as a top-level field.
    Auth: Bearer token in Authorization header.
    Response: { ok: true, result: ... } or { ok: false, error: { type, message } }
    """
    instance = await _get_instance(vm_id=vm_id)
    instance.last_activity = datetime.now()
    if manager is not None:
        manager.touch_instance(instance.user_id, instance.vm_id)

    payload: dict = {
        "tool": tool_name,
        "args": args,
        "sessionKey": session_key,
    }

    headers = _auth_headers(instance)

    try:
        async with httpx.AsyncClient(timeout=TOOL_TIMEOUT) as client:
            resp = await client.post(
                instance.tools_invoke_url,
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("ok"):
                result = data.get("result", {})
                if isinstance(result, dict):
                    return json.dumps(result, indent=2, default=str)
                return str(result)
            else:
                error = data.get("error", {})
                msg = error.get("message", "Unknown error") if isinstance(error, dict) else str(error)
                return f"[OpenClaw error] {msg}"

    except httpx.ConnectError:
        return (
            f"[OpenClaw error] Cannot connect to gateway at {instance.tools_invoke_url}. "
            "Is the OpenClaw instance running?"
        )
    except httpx.TimeoutException:
        return f"[OpenClaw error] Tool '{tool_name}' timed out after {TOOL_TIMEOUT}s"
    except httpx.HTTPStatusError as e:
        return f"[OpenClaw error] HTTP {e.response.status_code}: {e.response.text[:500]}"
    except Exception as e:
        return f"[OpenClaw error] {type(e).__name__}: {e}"


# ============== MCP TOOLS ==============


# VIVENTIUM START: VM-scoped lifecycle control surface for Codex/LibreChat.
@mcp.tool()
async def openclaw_vm_start(vm_id: str = OPENCLAW_DEFAULT_VM_ID) -> str:
    """Start (or create) a VM-scoped OpenClaw runtime."""
    if manager is None:
        return json.dumps({"error": "OpenClawManager not initialized"})
    user_id = _get_user_id()
    vm = normalize_vm_id(vm_id)
    instance = await manager.start_instance(user_id, vm)
    info = manager.get_instance_info(user_id, vm) or {}
    info["event"] = "started"
    info["user_id"] = instance.user_id
    info["vm_id"] = instance.vm_id
    return json.dumps(info, indent=2, default=str)


@mcp.tool()
async def openclaw_vm_resume(vm_id: str = OPENCLAW_DEFAULT_VM_ID) -> str:
    """Resume a paused VM-scoped OpenClaw runtime."""
    if manager is None:
        return json.dumps({"error": "OpenClawManager not initialized"})
    user_id = _get_user_id()
    vm = normalize_vm_id(vm_id)
    instance = await manager.resume_instance(user_id, vm)
    info = manager.get_instance_info(user_id, vm) or {}
    info["event"] = "resumed"
    info["user_id"] = instance.user_id
    info["vm_id"] = instance.vm_id
    return json.dumps(info, indent=2, default=str)


@mcp.tool()
async def openclaw_vm_stop(vm_id: str = OPENCLAW_DEFAULT_VM_ID) -> str:
    """Pause a VM (stop semantics for this POC)."""
    if manager is None:
        return json.dumps({"error": "OpenClawManager not initialized"})
    user_id = _get_user_id()
    vm = normalize_vm_id(vm_id)
    await manager.stop_instance(user_id, vm)
    info = manager.get_instance_info(user_id, vm) or {
        "user_id": user_id,
        "vm_id": vm,
        "state": "paused",
    }
    info["event"] = "paused"
    return json.dumps(info, indent=2, default=str)


@mcp.tool()
async def openclaw_vm_terminate(vm_id: str = OPENCLAW_DEFAULT_VM_ID) -> str:
    """Terminate a VM and remove it from registry/runtime."""
    if manager is None:
        return json.dumps({"error": "OpenClawManager not initialized"})
    user_id = _get_user_id()
    vm = normalize_vm_id(vm_id)
    await manager.terminate_instance(user_id, vm)
    return json.dumps(
        {
            "event": "terminated",
            "user_id": user_id,
            "vm_id": vm,
            "state": "terminated",
        },
        indent=2,
        default=str,
    )


@mcp.tool()
async def openclaw_vm_list() -> str:
    """List VM instances for the current user."""
    if manager is None:
        return json.dumps({"error": "OpenClawManager not initialized"})
    user_id = _get_user_id()
    items = manager.list_instances(user_id=user_id)
    return json.dumps({"user_id": user_id, "vms": items}, indent=2, default=str)


@mcp.tool()
async def openclaw_vm_status(vm_id: str = OPENCLAW_DEFAULT_VM_ID) -> str:
    """Check VM lifecycle status and probe gateway reachability."""
    user_id = _get_user_id()

    if manager is None:
        return json.dumps({"error": "OpenClawManager not initialized"})

    vm = normalize_vm_id(vm_id)
    info = manager.get_instance_info(user_id, vm)
    if info is None:
        return json.dumps({
            "status": "not_running",
            "user_id": user_id,
            "vm_id": vm,
            "message": "No VM instance found. Start one with openclaw_vm_start.",
        })

    instance = manager.get_instance(user_id, vm)
    probe_status = "unknown"
    if instance:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.post(
                    instance.tools_invoke_url,
                    json={"tool": "__viventium_probe__", "args": {}},
                    headers=_auth_headers(instance),
                )
                if resp.status_code in (200, 404):
                    probe_status = "healthy"
                elif resp.status_code == 401:
                    probe_status = "auth_mismatch"
                else:
                    probe_status = f"unhealthy (HTTP {resp.status_code})"
        except Exception as e:
            probe_status = f"unreachable ({e})"

    info["probe_status"] = probe_status
    return json.dumps(info, indent=2, default=str)


@mcp.tool()
async def openclaw_vm_takeover(
    vm_id: str = OPENCLAW_DEFAULT_VM_ID,
    require_auth: bool = True,
    view_only: bool = False,
) -> str:
    """Return interactive desktop takeover URL/auth for the selected VM."""
    if manager is None:
        return json.dumps({"error": "OpenClawManager not initialized"})
    user_id = _get_user_id()
    vm = normalize_vm_id(vm_id)
    takeover = await manager.takeover_instance(
        user_id,
        vm_id=vm,
        require_auth=require_auth,
        view_only=view_only,
    )
    takeover["event"] = "takeover_ready"
    return json.dumps(takeover, indent=2, default=str)
# VIVENTIUM END


@mcp.tool()
async def openclaw_status(vm_id: str = OPENCLAW_DEFAULT_VM_ID) -> str:
    """Check the status of your OpenClaw instance.

    Returns instance metadata and probes the gateway via /tools/invoke.
    There is no /health HTTP endpoint — health is a WS RPC method.
    """
    return await openclaw_vm_status(vm_id=vm_id)


@mcp.tool()
async def openclaw_exec(
    command: str,
    working_dir: str = "",
    vm_id: str = OPENCLAW_DEFAULT_VM_ID,
) -> str:
    """Execute a shell command in the user's OpenClaw environment.

    NOTE: The 'exec' tool is NOT exposed via /tools/invoke — it's only available
    to the agent runtime. This uses the /v1/responses API (agent delegation) to
    execute the command through the OpenClaw agent, which has full exec access.

    Args:
        command: The shell command to execute (e.g., "ls -la", "pip install requests")
        working_dir: Optional working directory for the command
    """
    instance = await _get_instance(vm_id=vm_id)
    instance.last_activity = datetime.now()
    if manager is not None:
        manager.touch_instance(instance.user_id, instance.vm_id)

    # Construct a task prompt that instructs the agent to run the command
    task = f"Run this shell command and return the output: `{command}`"
    if working_dir:
        task += f"\nWorking directory: {working_dir}"
    task += "\nReturn ONLY the command output, no commentary."

    payload = {
        "model": "default",
        "input": task,
        "stream": False,
    }

    headers = _auth_headers(instance)

    try:
        async with httpx.AsyncClient(timeout=TOOL_TIMEOUT) as client:
            resp = await client.post(
                instance.responses_url,
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

            # Extract text from OpenResponses output
            output_parts = []
            for item in data.get("output", []):
                if item.get("type") == "message":
                    for content in item.get("content", []):
                        if content.get("type") == "output_text":
                            output_parts.append(content.get("text", ""))

            return "\n".join(output_parts) if output_parts else json.dumps(data, indent=2, default=str)

    except httpx.ConnectError:
        return (
            f"[OpenClaw error] Cannot connect to agent at {instance.responses_url}. "
            "Is the OpenClaw instance running?"
        )
    except httpx.TimeoutException:
        return f"[OpenClaw error] exec timed out after {TOOL_TIMEOUT}s"
    except httpx.HTTPStatusError as e:
        return f"[OpenClaw error] HTTP {e.response.status_code}: {e.response.text[:500]}"
    except Exception as e:
        return f"[OpenClaw error] {type(e).__name__}: {e}"


@mcp.tool()
async def openclaw_browser(
    action: str,
    url: str = "",
    selector: str = "",
    text: str = "",
    vm_id: str = OPENCLAW_DEFAULT_VM_ID,
) -> str:
    """Control a web browser via OpenClaw's Playwright automation.

    The browser tool uses 'targetUrl' and 'action' inside args (not as a top-level field).
    Source: openclaw/src/agents/tools/browser-tool.ts

    Args:
        action: Browser action — one of: navigate, snapshot, screenshot, click, type, evaluate
        url: URL to navigate to (for 'navigate' action)
        selector: CSS selector for the target element (for click/type actions)
        text: Text to type (for 'type' action) or JS code (for 'evaluate' action)
    """
    args: dict = {"action": action}
    if url:
        args["targetUrl"] = url
    if selector:
        args["selector"] = selector
    if text:
        args["text"] = text

    return await _invoke_tool("browser", args, vm_id=vm_id)


@mcp.tool()
async def openclaw_message(
    action: str,
    channel: str = "",
    to: str = "",
    text: str = "",
    thread_id: str = "",
    vm_id: str = OPENCLAW_DEFAULT_VM_ID,
) -> str:
    """Send and receive messages across OpenClaw's connected channels.

    Supports WhatsApp, Telegram, Discord, Slack, iMessage, Signal, and more.
    All fields including 'action' go inside args.

    Args:
        action: Message action — one of: send, list_channels, list_conversations
        channel: Channel name (e.g., "whatsapp", "discord", "slack")
        to: Recipient identifier
        text: Message text to send
        thread_id: Optional thread/conversation ID
    """
    args: dict = {"action": action}
    if channel:
        args["channel"] = channel
    if to:
        args["to"] = to
    if text:
        args["text"] = text
    if thread_id:
        args["threadId"] = thread_id

    return await _invoke_tool("message", args, vm_id=vm_id)


@mcp.tool()
async def openclaw_cron(
    action: str,
    schedule: str = "",
    task: str = "",
    job_id: str = "",
    vm_id: str = OPENCLAW_DEFAULT_VM_ID,
) -> str:
    """Manage scheduled tasks via OpenClaw's cron system.

    Args:
        action: Cron action — one of: add, list, remove
        schedule: Cron expression or natural language schedule (for 'add')
        task: Description of the task to execute (for 'add')
        job_id: ID of the job to remove (for 'remove')
    """
    args: dict = {"action": action}
    if schedule:
        args["schedule"] = schedule
    if task:
        args["task"] = task
    if job_id:
        args["id"] = job_id

    return await _invoke_tool("cron", args, vm_id=vm_id)


@mcp.tool()
async def openclaw_nodes(
    action: str,
    node_id: str = "",
    command: str = "",
    vm_id: str = OPENCLAW_DEFAULT_VM_ID,
) -> str:
    """Access connected device capabilities via OpenClaw nodes.

    Args:
        action: Node action — one of: list, invoke, capabilities
        node_id: Target node identifier (for invoke)
        command: Command to execute on the node (for invoke)
    """
    args: dict = {"action": action}
    if node_id:
        args["nodeId"] = node_id
    if command:
        args["command"] = command

    return await _invoke_tool("nodes", args, vm_id=vm_id)


@mcp.tool()
async def openclaw_canvas(
    action: str,
    content: str = "",
    canvas_type: str = "html",
    vm_id: str = OPENCLAW_DEFAULT_VM_ID,
) -> str:
    """Render interactive visual content in OpenClaw's Canvas workspace.

    Args:
        action: Canvas action — one of: present, eval, clear
        content: HTML content or A2UI JSON to render
        canvas_type: Content type — "html" or "a2ui"
    """
    args: dict = {"action": action}
    if content:
        args["content"] = content
    if canvas_type:
        args["type"] = canvas_type

    return await _invoke_tool("canvas", args, vm_id=vm_id)


@mcp.tool()
async def openclaw_web_search(
    query: str,
    vm_id: str = OPENCLAW_DEFAULT_VM_ID,
) -> str:
    """Search the web using OpenClaw's web search tool.

    Uses Brave Search API or configured search provider.

    Args:
        query: Search query string
    """
    return await _invoke_tool("web_search", {"query": query}, vm_id=vm_id)


@mcp.tool()
async def openclaw_web_fetch(
    url: str,
    vm_id: str = OPENCLAW_DEFAULT_VM_ID,
) -> str:
    """Fetch a web page and return its content.

    Retrieves the content of a URL using OpenClaw's web fetch tool.

    Args:
        url: The URL to fetch
    """
    return await _invoke_tool("web_fetch", {"url": url}, vm_id=vm_id)


@mcp.tool()
async def openclaw_agent(
    task: str,
    model: str = "",
    tools: str = "",
    vm_id: str = OPENCLAW_DEFAULT_VM_ID,
) -> str:
    """Delegate a complete task to OpenClaw's built-in AI agent.

    Uses POST /v1/responses (OpenResponses API).
    Requires gateway.http.endpoints.responses.enabled=true in config.

    Args:
        task: Natural language description of the task
        model: Optional model override
        tools: Optional comma-separated list of allowed tools
    """
    instance = await _get_instance(vm_id=vm_id)
    instance.last_activity = datetime.now()
    if manager is not None:
        manager.touch_instance(instance.user_id, instance.vm_id)

    payload: dict = {
        "model": model or "default",
        "input": task,
        "stream": False,
    }
    if tools:
        tool_list = [t.strip() for t in tools.split(",")]
        payload["tools"] = [
            {"type": "function", "function": {"name": t}} for t in tool_list
        ]

    headers = _auth_headers(instance)

    try:
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(
                instance.responses_url,
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

            output_parts = []
            for item in data.get("output", []):
                if item.get("type") == "message":
                    for content in item.get("content", []):
                        if content.get("type") == "output_text":
                            output_parts.append(content.get("text", ""))
                elif item.get("type") == "function_call":
                    output_parts.append(
                        f"[Tool call: {item.get('name')}({item.get('arguments', '')})]"
                    )

            if output_parts:
                return "\n".join(output_parts)

            return json.dumps(data, indent=2, default=str)

    except httpx.ConnectError:
        return (
            f"[OpenClaw error] Cannot connect to agent at {instance.responses_url}. "
            "Is the OpenClaw instance running?"
        )
    except httpx.TimeoutException:
        return "[OpenClaw error] Agent task timed out after 300s"
    except httpx.HTTPStatusError as e:
        return f"[OpenClaw error] HTTP {e.response.status_code}: {e.response.text[:500]}"
    except Exception as e:
        return f"[OpenClaw error] {type(e).__name__}: {e}"


# ============== HEALTH ENDPOINT (MCP server itself, NOT OpenClaw) ==============


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    """Health check for the MCP bridge server (NOT the OpenClaw gateway).

    OpenClaw Gateway does NOT have an HTTP /health endpoint.
    This is the bridge's own health.
    """
    from starlette.responses import JSONResponse

    active_instances = len(manager.list_instances()) if manager else 0
    return JSONResponse({
        "status": "ok",
        "service": "openclaw-bridge",
        "active_instances": active_instances,
    })


# ============== STARTUP ==============


def create_app():
    """Create and configure the MCP server application."""
    global manager

    # Security check: warn if exposed beyond loopback without secret
    if MCP_HOST != "127.0.0.1" and not BRIDGE_SECRET:
        logger.warning(
            "MCP server bound to %s without OPENCLAW_BRIDGE_SECRET. "
            "X-User-Id header can be spoofed. Set OPENCLAW_BRIDGE_SECRET "
            "or bind to 127.0.0.1.",
            MCP_HOST,
        )

    manager = OpenClawManager()
    manager.schedule_cleanup()
    logger.info(f"OpenClaw Bridge MCP server starting on {MCP_HOST}:{MCP_PORT}")
    return mcp


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="OpenClaw Bridge MCP Server")
    parser.add_argument("--port", type=int, default=MCP_PORT, help="Port to listen on")
    parser.add_argument("--host", default=MCP_HOST, help="Host to bind to")
    args = parser.parse_args()

    create_app()
    mcp.run(transport="streamable-http", host=args.host, port=args.port)

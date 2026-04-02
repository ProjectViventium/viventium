# VIVENTIUM START
# Purpose: MCP Server for Azure deployment - runs as Container App.
# Communicates with Power Agent VM for Docker-in-Docker container management.
#
# Architecture:
# - This MCP server runs in Azure Container Apps (stateless)
# - Per-user containers run on a dedicated VM with Docker
# - Communication between MCP server and VM via HTTP API
# - User workspaces stored on Azure File Share mounted to VM
#
# Uses FastMCP for proper MCP protocol implementation (streamable-http transport)
# VIVENTIUM END

from __future__ import annotations

import argparse
import asyncio
import os
import json
import logging
from typing import Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime

import httpx
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============== CONFIGURATION ==============

# Power Agent VM API URL - set by Azure deployment
POWER_AGENT_VM_URL = os.environ.get("POWER_AGENT_VM_URL", "http://localhost:8000")

# Azure AI Foundry configuration (for Claude Code)
CLAUDE_CODE_USE_FOUNDRY = os.environ.get("CLAUDE_CODE_USE_FOUNDRY", "")
ANTHROPIC_FOUNDRY_API_KEY = os.environ.get("ANTHROPIC_FOUNDRY_API_KEY", "")
ANTHROPIC_FOUNDRY_RESOURCE = os.environ.get("ANTHROPIC_FOUNDRY_RESOURCE", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-5")

# Port mappings for user containers
DEFAULT_PORT_MAPPINGS = {
    3000: 9100,  # React, Node.js
    5000: 9101,  # Flask, Python
    8000: 9102,  # Agent API
    8080: 9103,  # HTTP servers
    8888: 9104,  # Jupyter
}

HEADER_USER_ID = "x-user-id"


# ============== HELPER FUNCTIONS ==============

def _normalize_headers(raw_headers: object) -> Dict[str, str]:
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
    """Get user_id from request headers."""
    headers = _get_request_headers()
    user_id = _sanitize_header_value(headers.get(HEADER_USER_ID))
    if not user_id:
        user_id = "default-user"
    return user_id


def _normalize_ports(raw: Dict[Any, Any]) -> Dict[int, int]:
    normalized: Dict[int, int] = {}
    for key, value in (raw or {}).items():
        try:
            k = int(key)
        except (TypeError, ValueError):
            continue
        try:
            v = int(value)
        except (TypeError, ValueError):
            continue
        normalized[k] = v
    return normalized


# ============== VM API CLIENT ==============

@dataclass
class ContainerInfo:
    """Information about a user's container on the VM."""
    user_id: str
    container_id: str
    status: str
    api_port: int
    exposed_ports: Dict[int, int]  # container_port -> host_port
    vm_public_ip: str


class PowerAgentVMClient:
    """Client to communicate with Power Agent VM."""
    
    def __init__(self, vm_url: str):
        self.vm_url = vm_url.rstrip("/")
        self.vm_public_ip = ""  # Set after first successful call
    
    async def health_check(self) -> bool:
        """Check if VM is healthy."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.vm_url}/health")
                if resp.status_code == 200:
                    data = resp.json()
                    self.vm_public_ip = data.get("public_ip", "")
                    return True
                return False
        except Exception as e:
            logger.error(f"VM health check failed: {e}")
            return False
    
    async def get_or_create_container(self, user_id: str) -> ContainerInfo:
        """Get or create a container for a user on the VM."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.vm_url}/containers",
                json={
                    "user_id": user_id,
                    "claude_code_use_foundry": CLAUDE_CODE_USE_FOUNDRY == "1",
                    "anthropic_foundry_api_key": ANTHROPIC_FOUNDRY_API_KEY,
                    "anthropic_foundry_resource": ANTHROPIC_FOUNDRY_RESOURCE,
                    "anthropic_model": ANTHROPIC_MODEL,
                }
            )
            resp.raise_for_status()
            data = resp.json()
            
            return ContainerInfo(
                user_id=data["user_id"],
                container_id=data["container_id"],
                status=data["status"],
                api_port=data["api_port"],
                exposed_ports=_normalize_ports(
                    data.get("exposed_ports", DEFAULT_PORT_MAPPINGS)
                )
                or DEFAULT_PORT_MAPPINGS,
                vm_public_ip=data.get("vm_public_ip", self.vm_public_ip),
            )
    
    async def call_container(
        self,
        user_id: str,
        endpoint: str,
        method: str = "POST",
        **kwargs
    ) -> Dict[str, Any]:
        """Call an endpoint on a user's container via the VM."""
        container = await self.get_or_create_container(user_id)
        
        async with httpx.AsyncClient(timeout=httpx.Timeout(600.0, connect=30.0)) as client:
            url = f"{self.vm_url}/proxy/{user_id}{endpoint}"
            
            if method == "GET":
                resp = await client.get(url, **kwargs)
            else:
                resp = await client.post(url, **kwargs)
            
            return resp.json()
    
    async def stream_from_container(
        self,
        user_id: str,
        endpoint: str,
        **kwargs
    ):
        """Stream from a user's container via the VM."""
        container = await self.get_or_create_container(user_id)
        
        async with httpx.AsyncClient(timeout=httpx.Timeout(600.0, connect=30.0)) as client:
            url = f"{self.vm_url}/proxy/{user_id}{endpoint}"
            
            async with client.stream("POST", url, **kwargs) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            event = json.loads(line[6:])
                            yield event
                        except json.JSONDecodeError:
                            pass


# Global VM client
vm_client = PowerAgentVMClient(POWER_AGENT_VM_URL)


# ============== CREATE MCP SERVER ==============

mcp = FastMCP(
    "power-agents",
    instructions="""Power Agents MCP Server (Azure) - Unleashed agentic capabilities:

CODING (power_agent_code):
- Run Claude Code CLI in isolated per-user containers
- Full Linux environment with network access
- Persistent workspace storage on Azure Files

BROWSER (power_agent_browse):
- AI-controlled browser automation
- Navigate sites, fill forms, extract data

SHELL (power_agent_shell):
- Direct shell access in the sandbox
- Quick commands like 'ls', 'git status', etc.

WORKSPACE:
- power_agent_workspace_list: List files
- power_agent_workspace_read: Read file contents

Each user gets their own isolated container with persistent storage."""
)


# ============== HEALTH ENDPOINT ==============

from starlette.requests import Request
from starlette.responses import JSONResponse

@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    """Health check endpoint for Azure Container Apps."""
    vm_healthy = await vm_client.health_check()
    return JSONResponse({
        "status": "healthy" if vm_healthy else "degraded",
        "vm_url": POWER_AGENT_VM_URL,
        "vm_healthy": vm_healthy,
        "vm_public_ip": vm_client.vm_public_ip,
        "azure_foundry_enabled": CLAUDE_CODE_USE_FOUNDRY == "1",
    })


# ============== MCP TOOLS ==============

@mcp.tool()
async def power_agent_code(
    task: str,
    agent: str = "claude",
    working_dir: str = ""
) -> str:
    """Run an autonomous coding task using Claude Code in a full Linux sandbox.

USE THIS TOOL when the user wants to create, run, or modify code/servers.

The agent runs in an isolated container with full Linux, network access, and persistent storage.

When the agent creates servers, they are accessible to users at URLs shown in the output.

The agent will:
- Create the code
- Start the server automatically
- Test it works
- Return the CLICKABLE URL for the user

Examples:
- "Create a server that returns a joke" → Agent creates, starts, tests, gives user a URL
- "Build a React app" → Agent creates, runs dev server, gives user a URL

Args:
    task: What to build/create/run
    agent: Ignored - always uses Claude Code (kept for backwards compatibility)
    working_dir: Subdirectory (optional)
    
Returns:
    The result with a clickable URL the user can access
    """
    user_id = _get_user_id()
    
    # Get container info for port mappings
    container = await vm_client.get_or_create_container(user_id)
    vm_ip = container.vm_public_ip or "VM_IP"
    
    output_lines = []
    output_lines.append("🚀 CLAUDE CODE EXECUTING IN SANDBOX")
    output_lines.append(f"📝 Task: {task[:100]}...")
    output_lines.append("")
    output_lines.append("🌐 Server URLs when ready:")
    output_lines.append(f"   Port 8080 → http://{vm_ip}:{container.exposed_ports.get(8080, 9103)}")
    output_lines.append(f"   Port 3000 → http://{vm_ip}:{container.exposed_ports.get(3000, 9100)}")
    output_lines.append("")
    output_lines.append("=" * 60)
    output_lines.append("LIVE OUTPUT FROM CLAUDE CODE:")
    output_lines.append("=" * 60)
    
    try:
        async for event in vm_client.stream_from_container(
            user_id=user_id,
            endpoint="/agent/stream",
            json={
                "task": task,
                "agent": "claude",
                "working_dir": working_dir or None,
                "timeout": 300,
                "auto_approve": True,
            }
        ):
            event_type = event.get("event")
            
            if event_type == "start":
                output_lines.append(f"[START] Agent initialized in {event.get('cwd', '/workspace')}")
            
            elif event_type == "output":
                text = event.get("text", "")
                stream_type = event.get("stream", "stdout")
                if text.strip():
                    # Replace default localhost mappings with user-specific host ports
                    for container_port, default_host_port in DEFAULT_PORT_MAPPINGS.items():
                        actual_host_port = container.exposed_ports.get(container_port)
                        if not actual_host_port or actual_host_port == default_host_port:
                            continue
                        text = text.replace(
                            f"http://localhost:{default_host_port}",
                            f"http://{vm_ip}:{actual_host_port}",
                        )
                        text = text.replace(
                            f"http://127.0.0.1:{default_host_port}",
                            f"http://{vm_ip}:{actual_host_port}",
                        )
                    prefix = "ERR>" if stream_type == "stderr" else "   "
                    output_lines.append(f"{prefix} {text}")
            
            elif event_type == "complete":
                success = event.get("success", False)
                duration = event.get("duration_seconds", 0)
                output_lines.append("")
                output_lines.append("=" * 60)
                status_icon = "✅ SUCCESS" if success else "❌ FAILED"
                output_lines.append(f"{status_icon} - Completed in {duration:.1f}s")
                output_lines.append("=" * 60)
                output_lines.append("")
                output_lines.append("🔗 ACCESS YOUR SERVER:")
                output_lines.append(f"   👉 http://{vm_ip}:{container.exposed_ports.get(8080, 9103)}")
            
            elif event_type == "error":
                output_lines.append(f"[ERROR] {event.get('error', 'Unknown error')}")
    
    except Exception as e:
        logger.warning(f"Streaming failed, falling back to non-streaming: {e}")
        result = await vm_client.call_container(
            user_id=user_id,
            endpoint="/agent",
            json={
                "task": task,
                "agent": "claude",
                "working_dir": working_dir or None,
                "timeout": 300,
                "auto_approve": True,
            }
        )
        
        output_lines.append("")
        output_lines.append("OUTPUT:")
        output_lines.append(result.get("output", "No output"))
        if result.get("error"):
            output_lines.append(f"\nError: {result['error']}")
        
        output_lines.append("")
        output_lines.append("🔗 ACCESS YOUR SERVER:")
        output_lines.append(f"   👉 http://{vm_ip}:{container.exposed_ports.get(8080, 9103)}")
    
    return "\n".join(output_lines)


@mcp.tool()
async def power_agent_browse(
    task: str,
    start_url: str = ""
) -> str:
    """Run an autonomous web browsing task using AI browser automation.

The agent can:
- Navigate websites
- Click buttons and fill forms
- Extract information
- Handle multi-step flows

Args:
    task: The browsing task to accomplish
    start_url: Optional starting URL
    
Returns:
    The result of the browsing task
    """
    user_id = _get_user_id()
    
    result = await vm_client.call_container(
        user_id=user_id,
        endpoint="/browse",
        json={
            "task": task,
            "start_url": start_url or None,
            "timeout": 120,
        }
    )
    
    text = result.get("output", "")
    if result.get("error"):
        text += f"\n\nError: {result['error']}"
    
    return text


@mcp.tool()
async def power_agent_shell(command: str) -> str:
    """Run a shell command in the user's sandbox.

Use for quick commands like:
- "ls -la" to list files
- "git status" to check git state
- "npm install" to install packages

Args:
    command: The shell command to run
    
Returns:
    The output of the command
    """
    user_id = _get_user_id()
    
    result = await vm_client.call_container(
        user_id=user_id,
        endpoint="/shell",
        params={"command": command}
    )
    
    return result.get("output", str(result))


@mcp.tool()
async def power_agent_workspace_list(path: str = "") -> str:
    """List files in the user's persistent workspace.

Args:
    path: Subdirectory path (optional)
    
Returns:
    List of files and directories
    """
    user_id = _get_user_id()
    
    result = await vm_client.call_container(
        user_id=user_id,
        endpoint="/workspace",
        method="GET",
        params={"path": path}
    )
    
    if isinstance(result, list):
        lines = []
        for f in result:
            icon = "📁" if f.get("is_dir") else "📄"
            lines.append(f"{icon} {f.get('name', 'unknown')}")
        return "\n".join(lines)
    
    return str(result)


@mcp.tool()
async def power_agent_workspace_read(path: str) -> str:
    """Read a file from the user's workspace.

Args:
    path: Path to the file within the workspace
    
Returns:
    The file contents
    """
    user_id = _get_user_id()
    
    result = await vm_client.call_container(
        user_id=user_id,
        endpoint="/workspace/read",
        method="GET",
        params={"path": path}
    )
    
    return result.get("content", str(result))


# ============== RUN ==============

def main():
    parser = argparse.ArgumentParser(description="Power Agents MCP Server (Azure)")
    parser.add_argument("--transport", choices=["stdio", "streamable-http"], default="streamable-http")
    parser.add_argument("--host", default=os.getenv("MCP_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("MCP_PORT", "8085")))
    args = parser.parse_args()
    
    logger.info(f"Starting Power Agents MCP server (Azure) with {args.transport} transport")
    logger.info(f"VM URL: {POWER_AGENT_VM_URL}")
    logger.info(f"Azure Foundry enabled: {CLAUDE_CODE_USE_FOUNDRY == '1'}")
    
    mcp.run(transport=args.transport, host=args.host, port=args.port)


if __name__ == "__main__":
    main()

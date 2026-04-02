# VIVENTIUM START
# Purpose: Simple MCP Server for Azure deployment - no FastMCP.
# Uses basic HTTP endpoints that LibreChat can call.
# VIVENTIUM END

import os
import json
import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============== CONFIGURATION ==============

POWER_AGENT_VM_URL = os.environ.get("POWER_AGENT_VM_URL", "http://localhost:8000")
CLAUDE_CODE_USE_FOUNDRY = os.environ.get("CLAUDE_CODE_USE_FOUNDRY", "")
ANTHROPIC_FOUNDRY_API_KEY = os.environ.get("ANTHROPIC_FOUNDRY_API_KEY", "")
ANTHROPIC_FOUNDRY_RESOURCE = os.environ.get("ANTHROPIC_FOUNDRY_RESOURCE", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-5")

PORT_MAPPINGS = {
    3000: 9100,
    5000: 9101,
    8000: 9102,
    8080: 9103,
    8888: 9104,
}

app = FastAPI(title="Power Agents MCP Server")


# ============== MODELS ==============

class ToolCallRequest(BaseModel):
    method: str
    params: Dict[str, Any] = {}
    id: Optional[str] = None


class ToolResponse(BaseModel):
    jsonrpc: str = "2.0"
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    id: Optional[str] = None


# ============== VM CLIENT ==============

async def vm_health_check() -> tuple[bool, str]:
    """Check if VM is healthy and get its public IP."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{POWER_AGENT_VM_URL}/health")
            if resp.status_code == 200:
                data = resp.json()
                return True, data.get("public_ip", "")
            return False, ""
    except Exception as e:
        logger.error(f"VM health check failed: {e}")
        return False, ""


async def get_or_create_container(user_id: str) -> Dict[str, Any]:
    """Get or create container for user."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{POWER_AGENT_VM_URL}/containers",
            json={
                "user_id": user_id,
                "claude_code_use_foundry": CLAUDE_CODE_USE_FOUNDRY == "1",
                "anthropic_foundry_api_key": ANTHROPIC_FOUNDRY_API_KEY,
                "anthropic_foundry_resource": ANTHROPIC_FOUNDRY_RESOURCE,
                "anthropic_model": ANTHROPIC_MODEL,
            }
        )
        if resp.status_code >= 400:
            detail = resp.text.strip()
            raise RuntimeError(f"VM /containers error {resp.status_code}: {detail}")
        return resp.json()


async def call_agent(user_id: str, task: str, working_dir: str = "") -> Dict[str, Any]:
    """Call agent on user's container."""
    async with httpx.AsyncClient(timeout=httpx.Timeout(600.0, connect=30.0)) as client:
        try:
            resp = await client.post(
                f"{POWER_AGENT_VM_URL}/proxy/{user_id}/agent",
                json={
                    "task": task,
                    "agent": "claude",
                    "working_dir": working_dir or None,
                    "timeout": 300,
                    "auto_approve": True,
                }
            )
        except httpx.RequestError as e:
            return {
                "success": False,
                "output": "",
                "error": f"VM proxy request failed: {e}",
                "duration_seconds": 0,
            }
        
        if resp.status_code >= 400:
            return {
                "success": False,
                "output": "",
                "error": f"VM proxy error {resp.status_code}: {resp.text.strip()}",
                "duration_seconds": 0,
            }
        
        try:
            return resp.json()
        except ValueError:
            return {
                "success": False,
                "output": "",
                "error": "VM proxy returned non-JSON response",
                "duration_seconds": 0,
            }


# ============== TOOLS ==============

def normalize_ports(raw: Dict[Any, Any]) -> Dict[int, int]:
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


async def power_agent_code(params: Dict[str, Any], user_id: str) -> str:
    """Execute coding task."""
    task = params.get("task", "")
    working_dir = params.get("working_dir", "")
    
    if not task:
        return "Error: 'task' parameter is required"
    
    try:
        # Get container info
        container = await get_or_create_container(user_id)
        parsed_vm = urlparse(POWER_AGENT_VM_URL)
        vm_host = parsed_vm.hostname
        if not vm_host:
            # Fallback for unexpected URL formats
            cleaned = POWER_AGENT_VM_URL.strip()
            if "://" in cleaned:
                cleaned = cleaned.split("://", 1)[1]
            cleaned = cleaned.split("/", 1)[0]
            vm_host = cleaned.split(":", 1)[0] if cleaned else ""
        vm_ip = container.get("vm_public_ip") or vm_host or "VM_IP"
        ports = normalize_ports(container.get("exposed_ports", {}))
        if not ports:
            ports = PORT_MAPPINGS.copy()
        
        # Call agent
        result = await call_agent(user_id, task, working_dir)
        
        output = result.get("output", "No output")
        error = result.get("error", "")
        success = result.get("success", False)
        duration = result.get("duration_seconds", 0)
        
        if vm_ip not in ("", "VM_IP"):
            # Replace container-port localhost URLs with public host mappings
            for container_port, host_port in ports.items():
                output = output.replace(
                    f"http://localhost:{container_port}",
                    f"http://{vm_ip}:{host_port}",
                )
                output = output.replace(
                    f"http://127.0.0.1:{container_port}",
                    f"http://{vm_ip}:{host_port}",
                )
            # Replace any leftover host-port localhost URLs
            for host_port in set(ports.values()):
                output = output.replace(
                    f"http://localhost:{host_port}",
                    f"http://{vm_ip}:{host_port}",
                )
                output = output.replace(
                    f"http://127.0.0.1:{host_port}",
                    f"http://{vm_ip}:{host_port}",
                )
            # Replace default mapping hints (9100-9104) with actual user mapping
            for container_port, default_host_port in PORT_MAPPINGS.items():
                actual_host_port = ports.get(container_port)
                if not actual_host_port:
                    continue
                if actual_host_port == default_host_port:
                    continue
                output = output.replace(
                    f"http://localhost:{default_host_port}",
                    f"http://{vm_ip}:{actual_host_port}",
                )
                output = output.replace(
                    f"http://127.0.0.1:{default_host_port}",
                    f"http://{vm_ip}:{actual_host_port}",
                )
        
        lines = []
        lines.append("🚀 CLAUDE CODE EXECUTION COMPLETE")
        lines.append("")
        lines.append(f"📝 Task: {task[:100]}...")
        lines.append(f"⏱️ Duration: {duration:.1f}s")
        lines.append(f"{'✅ SUCCESS' if success else '❌ FAILED'}")
        lines.append("")
        lines.append("=" * 60)
        lines.append("OUTPUT:")
        lines.append("=" * 60)
        lines.append(output)
        
        if error:
            lines.append(f"\n⚠️ Error: {error}")
        
        lines.append("")
        lines.append("🔗 ACCESS YOUR SERVER:")
        lines.append(f"   Port 8080 → http://{vm_ip}:{ports.get(8080, 9103)}")
        lines.append(f"   Port 3000 → http://{vm_ip}:{ports.get(3000, 9100)}")
        
        return "\n".join(lines)
    
    except Exception as e:
        logger.exception(f"Error executing task: {e}")
        return f"Error: {str(e)}"


TOOLS = {
    "power_agent_code": {
        "description": "Run an autonomous coding task using Claude Code in a full Linux sandbox. Creates servers, apps, etc.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "What to build/create/run"
                },
                "working_dir": {
                    "type": "string",
                    "description": "Subdirectory to work in (optional)"
                }
            },
            "required": ["task"]
        },
        "handler": power_agent_code
    }
}


# ============== MCP ENDPOINTS ==============

@app.get("/health")
async def health():
    """Health check."""
    vm_healthy, vm_ip = await vm_health_check()
    return {
        "status": "healthy" if vm_healthy else "degraded",
        "vm_url": POWER_AGENT_VM_URL,
        "vm_healthy": vm_healthy,
        "vm_public_ip": vm_ip,
        "azure_foundry_enabled": CLAUDE_CODE_USE_FOUNDRY == "1",
    }


@app.post("/mcp")
async def mcp_endpoint(request: Request):
    """MCP JSON-RPC endpoint."""
    try:
        body = await request.json()
    except:
        return JSONResponse(
            {"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}, "id": None},
            status_code=400
        )
    
    method = body.get("method", "")
    params = body.get("params", {})
    req_id = body.get("id")
    
    # Get user ID from headers
    user_id = request.headers.get("x-user-id", "default-user")
    if user_id.startswith("{{") or user_id.startswith("${"):
        user_id = "default-user"
    
    logger.info(f"MCP request: method={method}, user={user_id}")
    
    # Handle MCP methods
    if method == "initialize":
        return JSONResponse({
            "jsonrpc": "2.0",
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {"listChanged": True}
                },
                "serverInfo": {
                    "name": "power-agents",
                    "version": "1.0.0"
                }
            },
            "id": req_id
        })
    
    elif method == "tools/list":
        tools_list = []
        for name, tool in TOOLS.items():
            tools_list.append({
                "name": name,
                "description": tool["description"],
                "inputSchema": tool["inputSchema"]
            })
        return JSONResponse({
            "jsonrpc": "2.0",
            "result": {"tools": tools_list},
            "id": req_id
        })
    
    elif method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})
        
        if tool_name not in TOOLS:
            return JSONResponse({
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": f"Tool not found: {tool_name}"},
                "id": req_id
            })
        
        try:
            result = await TOOLS[tool_name]["handler"](tool_args, user_id)
            return JSONResponse({
                "jsonrpc": "2.0",
                "result": {
                    "content": [{"type": "text", "text": result}]
                },
                "id": req_id
            })
        except Exception as e:
            logger.exception(f"Tool execution error: {e}")
            return JSONResponse({
                "jsonrpc": "2.0",
                "error": {"code": -32000, "message": str(e)},
                "id": req_id
            })
    
    elif method == "notifications/initialized":
        # Client notification that init is complete - no response needed
        return JSONResponse({"jsonrpc": "2.0", "result": None, "id": req_id})
    
    else:
        return JSONResponse({
            "jsonrpc": "2.0",
            "error": {"code": -32601, "message": f"Method not found: {method}"},
            "id": req_id
        })


@app.get("/mcp")
async def mcp_get(request: Request):
    """Handle GET requests for SSE sessions."""
    # Return a simple response for initialization checks
    session_id = request.headers.get("mcp-session-id")
    if not session_id:
        return JSONResponse(
            {"jsonrpc": "2.0", "error": {"code": -32600, "message": "Missing session ID"}, "id": "server-error"},
            status_code=400
        )
    return JSONResponse({"status": "session active", "session_id": session_id})


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8085"))
    uvicorn.run(app, host="0.0.0.0", port=port)

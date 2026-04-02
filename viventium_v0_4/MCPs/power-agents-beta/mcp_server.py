# VIVENTIUM START
# Purpose: MCP Server that manages per-user power sandbox containers.
# Exposes Claude Code, Codex, and browser-use capabilities to LibreChat via MCP protocol.
#
# Architecture:
# - Each user gets their own Docker container with full Linux + agents
# - Containers have persistent volumes for workspace storage
# - Containers auto-shutdown after idle timeout to save resources
# - MCP tools route requests to the appropriate user's container
#
# Uses FastMCP for proper MCP protocol implementation (streamable-http transport)
# VIVENTIUM END

from __future__ import annotations

import argparse
import asyncio
import os
import json
import time
import logging
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import docker
import httpx
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============== CONFIGURATION ==============

IMAGE_NAME = os.environ.get("POWER_AGENT_IMAGE", "viventium/power-sandbox:latest")

# DATA_DIR must be an absolute path that works on both the host and inside this container
_default_data_dir = os.path.expanduser("~/.viventium/power-agents-beta/users")
DATA_DIR = Path(os.environ.get("POWER_AGENT_DATA_DIR", _default_data_dir))

PORT_RANGE_START = int(os.environ.get("POWER_AGENT_PORT_START", "9100"))
PORT_RANGE_END = int(os.environ.get("POWER_AGENT_PORT_END", "9999"))
IDLE_TIMEOUT_HOURS = float(os.environ.get("POWER_AGENT_IDLE_HOURS", "2"))
CONTAINER_MEMORY = os.environ.get("POWER_AGENT_MEMORY", "4g")
CONTAINER_CPUS = float(os.environ.get("POWER_AGENT_CPUS", "2"))

# Common development ports that should be exposed from user containers
# So users can access servers created by the agent
USER_EXPOSED_PORTS = [3000, 5000, 8000, 8080, 8888]

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
        # Generate a default user_id for testing
        user_id = "default-user"
    return user_id


# ============== CONTAINER MANAGER ==============

@dataclass
class UserContainer:
    """Tracks a user's container."""
    user_id: str
    container_id: str
    port: int  # Base port for agent API (8000 inside container)
    exposed_ports: Dict[int, int] = field(default_factory=dict)  # container_port -> host_port
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)


class ContainerManager:
    """Manages per-user Docker containers."""
    
    def __init__(self):
        self.docker = docker.from_env()
        self.containers: Dict[str, UserContainer] = {}
        self.used_ports: set = set()
        
        # Ensure data directory exists
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        
        # Recover any existing containers on startup
        self._recover_containers()
    
    def _recover_containers(self):
        """Find and track any existing viventium agent containers."""
        try:
            for container in self.docker.containers.list(
                filters={"label": "viventium.service=power-agent"}
            ):
                labels = container.labels
                user_id = labels.get("viventium.user_id")
                if not user_id:
                    continue
                
                # Get the port
                ports = container.ports.get("8000/tcp", [])
                if not ports:
                    continue
                port = int(ports[0]["HostPort"])
                
                self.containers[user_id] = UserContainer(
                    user_id=user_id,
                    container_id=container.id,
                    port=port,
                    created_at=datetime.fromisoformat(
                        labels.get("viventium.created_at", datetime.now().isoformat())
                    ),
                    last_activity=datetime.now()
                )
                self.used_ports.add(port)
                logger.info(f"Recovered container for user {user_id} on port {port}")
        except Exception as e:
            logger.error(f"Error recovering containers: {e}")
    
    def _get_free_port(self) -> int:
        """Find an available port."""
        for port in range(PORT_RANGE_START, PORT_RANGE_END):
            if port not in self.used_ports:
                self.used_ports.add(port)
                return port
        raise RuntimeError("No free ports available")
    
    def _get_port_mappings(self, base_port: int) -> Dict[str, int]:
        """Get port mappings for a user container.
        
        Maps common dev ports (3000, 5000, 8000, 8080, 8888) inside container
        to sequential host ports starting from base_port.
        """
        mappings = {}
        host_port = base_port
        for container_port in USER_EXPOSED_PORTS:
            mappings[f"{container_port}/tcp"] = host_port
            self.used_ports.add(host_port)
            host_port += 1
        return mappings
    
    def _get_user_data_dir(self, user_id: str) -> Path:
        """Get or create the user's data directory."""
        user_dir = DATA_DIR / user_id
        (user_dir / "workspace").mkdir(parents=True, exist_ok=True)
        return user_dir
    
    async def get_or_create_container(
        self,
        user_id: str,
        anthropic_key: Optional[str] = None,
        openai_key: Optional[str] = None,
    ) -> UserContainer:
        """Get existing container or create a new one for the user."""
        
        # Check if container exists and is running
        if user_id in self.containers:
            container_info = self.containers[user_id]
            try:
                container = self.docker.containers.get(container_info.container_id)
                if container.status == "running":
                    container_info.last_activity = datetime.now()
                    return container_info
                else:
                    # Container exists but not running - remove and recreate
                    try:
                        container.remove(force=True)
                    except:
                        pass
                    self.used_ports.discard(container_info.port)
                    del self.containers[user_id]
            except docker.errors.NotFound:
                # Container gone
                self.used_ports.discard(container_info.port)
                del self.containers[user_id]
        
        # Create new container
        base_port = self._get_free_port()
        port_mappings = self._get_port_mappings(base_port)
        user_dir = self._get_user_data_dir(user_id)
        
        # Track exposed ports (container_port -> host_port)
        exposed_ports = {}
        for container_port_spec, host_port in port_mappings.items():
            container_port = int(container_port_spec.split("/")[0])
            exposed_ports[container_port] = host_port
        
        env_vars = {}
        
        # Check for Azure Foundry configuration first
        if os.environ.get("CLAUDE_CODE_USE_FOUNDRY") == "1":
            # Azure Foundry mode - pass Foundry vars to container
            env_vars["CLAUDE_CODE_USE_FOUNDRY"] = "1"
            if os.environ.get("ANTHROPIC_FOUNDRY_API_KEY"):
                env_vars["ANTHROPIC_FOUNDRY_API_KEY"] = os.environ["ANTHROPIC_FOUNDRY_API_KEY"]
            if os.environ.get("ANTHROPIC_FOUNDRY_RESOURCE"):
                env_vars["ANTHROPIC_FOUNDRY_RESOURCE"] = os.environ["ANTHROPIC_FOUNDRY_RESOURCE"]
            if os.environ.get("ANTHROPIC_DEFAULT_OPUS_MODEL"):
                env_vars["ANTHROPIC_DEFAULT_OPUS_MODEL"] = os.environ["ANTHROPIC_DEFAULT_OPUS_MODEL"]
            # Set default model for Claude Code CLI
            if os.environ.get("ANTHROPIC_MODEL"):
                env_vars["ANTHROPIC_MODEL"] = os.environ["ANTHROPIC_MODEL"]
            elif os.environ.get("ANTHROPIC_DEFAULT_OPUS_MODEL"):
                env_vars["ANTHROPIC_MODEL"] = os.environ["ANTHROPIC_DEFAULT_OPUS_MODEL"]
        elif anthropic_key:
            env_vars["ANTHROPIC_API_KEY"] = anthropic_key
        
        if openai_key:
            env_vars["OPENAI_API_KEY"] = openai_key
        
        created_at = datetime.now()
        
        try:
            container = self.docker.containers.run(
                IMAGE_NAME,
                detach=True,
                name=f"viventium-agent-{user_id[:8]}-{int(time.time())}",
                labels={
                    "viventium.stack": "viventium_v0_4",
                    "viventium.service": "power-agent",
                    "viventium.user_id": user_id,
                    "viventium.created_at": created_at.isoformat(),
                    "viventium.exposed_ports": json.dumps(exposed_ports),
                },
                ports=port_mappings,  # Expose multiple dev ports
                volumes={
                    str(user_dir / "workspace"): {
                        "bind": "/home/agent/workspace",
                        "mode": "rw"
                    },
                },
                environment=env_vars,
                mem_limit=CONTAINER_MEMORY,
                cpu_count=int(CONTAINER_CPUS),
                # CRITICAL: Keep container running so servers persist
                restart_policy={"Name": "unless-stopped"},
            )
            
            logger.info(f"Created container for user {user_id} with ports: {exposed_ports}")
            
        except docker.errors.ImageNotFound:
            raise RuntimeError(f"Power sandbox image not found: {IMAGE_NAME}. Run: docker build -t {IMAGE_NAME} .")
        
        # The agent API runs on container port 8000, mapped to host port
        agent_api_port = exposed_ports.get(8000, base_port)
        
        container_info = UserContainer(
            user_id=user_id,
            container_id=container.id,
            port=agent_api_port,
            exposed_ports=exposed_ports,
            created_at=created_at,
            last_activity=created_at,
        )
        
        self.containers[user_id] = container_info
        
        # Wait for container to be ready (agent API on port 8000)
        await self._wait_for_healthy(agent_api_port)
        
        return container_info
    
    async def _wait_for_healthy(self, port: int, timeout: int = 60):
        """Wait for container health endpoint to respond."""
        url = f"http://host.docker.internal:{port}/health"
        async with httpx.AsyncClient() as client:
            for i in range(timeout):
                try:
                    resp = await client.get(url, timeout=2)
                    if resp.status_code == 200:
                        logger.info(f"Container on port {port} is healthy (took {i+1}s)")
                        return
                except Exception as e:
                    if i % 10 == 0:
                        logger.info(f"Waiting for container on port {port}: {e}")
                    pass
                await asyncio.sleep(1)
        
        raise RuntimeError(f"Container on port {port} did not become healthy after {timeout}s")
    
    async def stop_container(self, user_id: str):
        """Stop and remove a user's container (data persists)."""
        if user_id not in self.containers:
            return
        
        container_info = self.containers[user_id]
        try:
            container = self.docker.containers.get(container_info.container_id)
            container.stop(timeout=10)
            container.remove()
        except docker.errors.NotFound:
            pass
        
        self.used_ports.discard(container_info.port)
        del self.containers[user_id]
    
    async def cleanup_idle_containers(self):
        """Stop containers that have been idle too long."""
        now = datetime.now()
        idle_threshold = timedelta(hours=IDLE_TIMEOUT_HOURS)
        to_stop = []
        
        for user_id, container_info in self.containers.items():
            if now - container_info.last_activity > idle_threshold:
                to_stop.append(user_id)
        
        for user_id in to_stop:
            logger.info(f"Stopping idle container for user {user_id}")
            await self.stop_container(user_id)
    
    def get_container_url(self, user_id: str) -> Optional[str]:
        """Get the API URL for a user's container."""
        if user_id in self.containers:
            port = self.containers[user_id].port
            return f"http://host.docker.internal:{port}"
        return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get container manager statistics."""
        return {
            "active_containers": len(self.containers),
            "used_ports": len(self.used_ports),
            "image": IMAGE_NAME,
            "data_dir": str(DATA_DIR),
            "users": list(self.containers.keys()),
        }
    
    def get_user_urls(self, user_id: str) -> Dict[str, str]:
        """Get accessible URLs for a user's container ports."""
        if user_id not in self.containers:
            return {}
        
        container = self.containers[user_id]
        urls = {}
        for container_port, host_port in container.exposed_ports.items():
            if container_port == 8000:
                urls["agent_api"] = f"http://localhost:{host_port}"
            else:
                urls[f"port_{container_port}"] = f"http://localhost:{host_port}"
        return urls


# Global container manager
container_manager = ContainerManager()


# ============== CREATE MCP SERVER ==============

mcp = FastMCP(
    "power-agents",
    instructions="""This MCP server provides unleashed agentic capabilities:

CODING (power_agent_code):
- Use agent='claude' for Claude Code CLI (Anthropic)
- Use agent='codex' for Codex CLI (OpenAI)
- Agents run in isolated containers with full Linux environment
- Files persist in user's workspace across sessions

BROWSER (power_agent_browse):
- AI-controlled browser automation
- Can navigate sites, fill forms, extract data

SHELL (power_agent_shell):
- Direct shell access in the sandbox
- For quick commands like 'ls', 'git status', etc.

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
    """Health check endpoint for container health probes."""
    return JSONResponse({
        "status": "healthy",
        **container_manager.get_stats()
    })


# ============== TOOL HELPER ==============

async def _call_container(user_id: str, endpoint: str, method: str = "POST", **kwargs) -> Dict[str, Any]:
    """Call an endpoint on the user's container."""
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")
    
    container = await container_manager.get_or_create_container(
        user_id=user_id,
        anthropic_key=anthropic_key,
        openai_key=openai_key,
    )
    
    base_url = f"http://host.docker.internal:{container.port}"
    url = f"{base_url}{endpoint}"
    
    logger.info(f"Calling {method} {url} for user {user_id}")
    
    async with httpx.AsyncClient(timeout=httpx.Timeout(600.0, connect=30.0)) as client:
        if method == "GET":
            resp = await client.get(url, **kwargs)
        else:
            resp = await client.post(url, **kwargs)
        
        return resp.json()


# ============== MCP TOOLS ==============

async def _stream_from_container(user_id: str, endpoint: str, **kwargs):
    """Stream SSE from user's container."""
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")
    
    container = await container_manager.get_or_create_container(
        user_id=user_id,
        anthropic_key=anthropic_key,
        openai_key=openai_key,
    )
    
    base_url = f"http://host.docker.internal:{container.port}"
    url = f"{base_url}{endpoint}"
    
    logger.info(f"Streaming from {url} for user {user_id}")
    
    async with httpx.AsyncClient(timeout=httpx.Timeout(600.0, connect=30.0)) as client:
        async with client.stream("POST", url, **kwargs) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    try:
                        event = json.loads(line[6:])
                        yield event
                    except json.JSONDecodeError:
                        pass


@mcp.tool()
async def power_agent_code(
    task: str,
    agent: str = "claude",
    working_dir: str = ""
) -> str:
    """Run an autonomous coding task using Claude Code in a full Linux sandbox.

USE THIS TOOL when the user wants to create, run, or modify code/servers.

The agent runs in an isolated container with full Linux, network access, and persistent storage.

SERVERS ARE ACCESSIBLE TO THE USER at these URLs:
- Port 3000 inside container → http://localhost:9100 (for user to click)
- Port 5000 inside container → http://localhost:9101 (for user to click)
- Port 8080 inside container → http://localhost:9103 (for user to click)
- Port 8888 inside container → http://localhost:9104 (for user to click)

The agent will:
- Create the code
- Start the server automatically
- Test it works
- Return the CLICKABLE URL for the user (e.g., http://localhost:9103)

Examples:
- "Create a server that returns a joke" → Agent creates, starts, tests, gives user http://localhost:9103
- "Build a React app" → Agent creates, runs dev server, gives user http://localhost:9100

Args:
    task: What to build/create/run
    agent: Ignored - always uses Claude Code (kept for backwards compatibility)
    working_dir: Subdirectory (optional)
    
Returns:
    The result with a clickable URL the user can access
    """
    # Note: 'agent' parameter is ignored - we always use Claude Code
    user_id = _get_user_id()
    
    # Ensure container exists and get port info
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")
    container = await container_manager.get_or_create_container(
        user_id=user_id,
        anthropic_key=anthropic_key,
        openai_key=openai_key,
    )
    
    # Build full output (streaming not supported in MCP text responses)
    # All output collected and returned at once
    output_lines = []
    
    # Header with accessible URLs
    output_lines.append("🚀 CLAUDE CODE EXECUTING IN SANDBOX")
    output_lines.append(f"📝 Task: {task[:100]}...")
    output_lines.append("")
    output_lines.append("🌐 Server URLs when ready:")
    output_lines.append(f"   Port 8080 → http://localhost:{container.exposed_ports.get(8080, 9103)}")
    output_lines.append(f"   Port 3000 → http://localhost:{container.exposed_ports.get(3000, 9100)}")
    output_lines.append("")
    output_lines.append("=" * 60)
    output_lines.append("LIVE OUTPUT FROM CLAUDE CODE:")
    output_lines.append("=" * 60)
    
    try:
        base_url = f"http://host.docker.internal:{container.port}"
        url = f"{base_url}/agent/stream"
        
        async with httpx.AsyncClient(timeout=httpx.Timeout(600.0, connect=30.0)) as client:
            async with client.stream("POST", url, json={
                "task": task,
                "agent": "claude",  # Always use Claude
                "working_dir": working_dir or None,
                "timeout": 300,
                "auto_approve": True,
            }) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            event = json.loads(line[6:])
                            event_type = event.get("event")
                            
                            if event_type == "start":
                                output_lines.append(f"[START] Agent initialized in {event.get('cwd', '/workspace')}")
                            
                            elif event_type == "output":
                                text = event.get("text", "")
                                stream_type = event.get("stream", "stdout")
                                # Include ALL output so user sees what Claude Code is doing
                                if text.strip():
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
                                output_lines.append(f"   👉 http://localhost:{container.exposed_ports.get(8080, 9103)}")
                            
                            elif event_type == "error":
                                output_lines.append(f"[ERROR] {event.get('error', 'Unknown error')}")
                        except json.JSONDecodeError:
                            pass
    
    except Exception as e:
        # Fall back to non-streaming if streaming fails
        logger.warning(f"Streaming failed, falling back to non-streaming: {e}")
        result = await _call_container(
            user_id=user_id,
            endpoint="/agent",
            json={
                "task": task,
                "agent": "claude",  # Always use Claude
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
        if result.get("duration_seconds"):
            output_lines.append(f"\n(Completed in {result['duration_seconds']:.1f}s)")
        
        output_lines.append("")
        output_lines.append("🔗 ACCESS YOUR SERVER:")
        output_lines.append(f"   👉 http://localhost:{container.exposed_ports.get(8080, 9103)}")
    
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
- Research and compile information

Examples:
- "Find the top 5 AI funding news from this week"
- "Go to booking.com and find hotels in Paris under $200 for March 15-20"
- "Research competitor pricing on their websites"
- "Fill out the job application form on company.com"
- "Search for Python tutorials on YouTube and list the top results"

Args:
    task: The browsing task to accomplish
    start_url: Optional starting URL
    
Returns:
    The result of the browsing task
    """
    user_id = _get_user_id()
    
    result = await _call_container(
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
- "python script.py" to run a script

For complex multi-step tasks, use power_agent_code instead.

Args:
    command: The shell command to run
    
Returns:
    The output of the command
    """
    user_id = _get_user_id()
    
    result = await _call_container(
        user_id=user_id,
        endpoint="/shell",
        params={"command": command}
    )
    
    return result.get("output", str(result))


@mcp.tool()
async def power_agent_workspace_list(path: str = "") -> str:
    """List files in the user's persistent workspace.

Args:
    path: Subdirectory path (optional, defaults to root)
    
Returns:
    List of files and directories
    """
    user_id = _get_user_id()
    
    result = await _call_container(
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
    
    result = await _call_container(
        user_id=user_id,
        endpoint="/workspace/read",
        method="GET",
        params={"path": path}
    )
    
    return result.get("content", str(result))


# ============== RUN ==============

def main():
    parser = argparse.ArgumentParser(description="Power Agents MCP Server")
    parser.add_argument("--transport", choices=["stdio", "streamable-http"], default="streamable-http")
    parser.add_argument("--host", default=os.getenv("MCP_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("MCP_PORT", "8080")))
    args = parser.parse_args()
    
    logger.info(f"Starting Power Agents MCP server with {args.transport} transport on {args.host}:{args.port}")
    logger.info(f"Data directory: {DATA_DIR}")
    logger.info(f"Image: {IMAGE_NAME}")
    
    mcp.run(transport=args.transport, host=args.host, port=args.port)


if __name__ == "__main__":
    main()

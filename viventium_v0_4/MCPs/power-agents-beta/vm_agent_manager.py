# VIVENTIUM START
# Purpose: Agent Manager API that runs on the Power Agents VM.
# This manages Docker containers for each user and proxies requests to them.
#
# Architecture:
# - Runs on a dedicated Azure VM with Docker installed
# - Creates per-user Docker containers on demand
# - Mounts Azure File Share for persistent workspaces
# - Exposes HTTP API for the MCP server (Container App) to call
# VIVENTIUM END

import asyncio
import os
import json
import time
import logging
import socket
from typing import Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import docker
import httpx
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============== CONFIGURATION ==============

def _parse_float(value: Optional[str], default: float) -> float:
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


IMAGE_NAME = os.environ.get("POWER_SANDBOX_IMAGE", "viventium/power-sandbox:latest")
WORKSPACE_BASE = Path(os.environ.get("WORKSPACE_BASE", "/workspaces"))
PORT_RANGE_START = int(os.environ.get("CONTAINER_PORT_START", "9100"))
PORT_RANGE_END = int(os.environ.get("CONTAINER_PORT_END", "9199"))
IDLE_TIMEOUT_HOURS = _parse_float(os.environ.get("IDLE_TIMEOUT_HOURS"), 2.0)
IDLE_TIMEOUT_MINUTES = _parse_float(
    os.environ.get("IDLE_TIMEOUT_MINUTES"),
    IDLE_TIMEOUT_HOURS * 60.0,
)
MAX_LIFETIME_MINUTES = _parse_float(os.environ.get("MAX_LIFETIME_MINUTES"), 0.0)
CLEANUP_INTERVAL_SECONDS = int(os.environ.get("CLEANUP_INTERVAL_SECONDS", "60"))
CONTAINER_MEMORY = os.environ.get("CONTAINER_MEMORY", "4g")
CONTAINER_CPUS = float(os.environ.get("CONTAINER_CPUS", "2"))

# Azure AI Foundry defaults (can be overridden per-request)
DEFAULT_CLAUDE_CODE_USE_FOUNDRY = os.environ.get("CLAUDE_CODE_USE_FOUNDRY", "")
DEFAULT_ANTHROPIC_FOUNDRY_API_KEY = os.environ.get("ANTHROPIC_FOUNDRY_API_KEY", "")
DEFAULT_ANTHROPIC_FOUNDRY_RESOURCE = os.environ.get("ANTHROPIC_FOUNDRY_RESOURCE", "")
DEFAULT_ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-5")

VM_PUBLIC_IP = (os.environ.get("VM_PUBLIC_IP") or os.environ.get("PUBLIC_IP") or "").strip()

# Common development ports to expose
USER_EXPOSED_PORTS = [3000, 5000, 8000, 8080, 8888]


def get_public_ip() -> str:
    """Get the public IP of this VM."""
    if VM_PUBLIC_IP:
        return VM_PUBLIC_IP

    # Try Azure metadata service (text endpoint)
    try:
        import urllib.request
        req = urllib.request.Request(
            "http://169.254.169.254/metadata/instance/network/interface/0/ipv4/ipAddress/0/publicIpAddress?api-version=2021-02-01&format=text",
            headers={"Metadata": "true"},
        )
        with urllib.request.urlopen(req, timeout=2) as response:
            ip = response.read().decode().strip()
            if ip:
                return ip
    except Exception:
        pass

    # Try Azure metadata service (JSON endpoint)
    try:
        import urllib.request
        req = urllib.request.Request(
            "http://169.254.169.254/metadata/instance/network/interface?api-version=2021-02-01",
            headers={"Metadata": "true"},
        )
        with urllib.request.urlopen(req, timeout=2) as response:
            data = json.loads(response.read().decode())
            for iface in data:
                ipv4 = iface.get("ipv4", {})
                for ip in ipv4.get("ipAddress", []):
                    public_ip = ip.get("publicIpAddress")
                    if public_ip:
                        return public_ip
    except Exception:
        pass

    # Fallback: external lookup
    for url in ("https://api.ipify.org", "https://ifconfig.me/ip"):
        try:
            import urllib.request
            with urllib.request.urlopen(url, timeout=3) as response:
                ip = response.read().decode().strip()
                if ip:
                    return ip
        except Exception:
            pass

    # Last-resort: hostname resolution
    try:
        return socket.gethostbyname(socket.gethostname())
    except Exception:
        return ""


# ============== MODELS ==============

class CreateContainerRequest(BaseModel):
    user_id: str
    claude_code_use_foundry: bool = False
    anthropic_foundry_api_key: Optional[str] = None
    anthropic_foundry_resource: Optional[str] = None
    anthropic_model: Optional[str] = None


class ContainerResponse(BaseModel):
    user_id: str
    container_id: str
    status: str
    api_port: int
    exposed_ports: Dict[int, int]
    vm_public_ip: str


# ============== CONTAINER MANAGER ==============

@dataclass
class UserContainer:
    """Tracks a user's container."""
    user_id: str
    container_id: str
    port: int
    exposed_ports: Dict[int, int] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)


class ContainerManager:
    """Manages per-user Docker containers on the VM."""
    
    def __init__(self):
        self.docker = docker.from_env()
        self.containers: Dict[str, UserContainer] = {}
        self.used_ports: set = set()
        self._lock = asyncio.Lock()
        
        # Ensure workspace directory exists
        WORKSPACE_BASE.mkdir(parents=True, exist_ok=True)
        
        # Recover existing containers
        self._recover_containers()
    
    def _recover_containers(self):
        """Find and track any existing power agent containers."""
        try:
            for container in self.docker.containers.list(
                filters={"label": "viventium.service=power-agent"}
            ):
                labels = container.labels
                user_id = labels.get("viventium.user_id")
                if not user_id:
                    continue
                
                ports = container.ports.get("8000/tcp", [])
                if not ports:
                    continue
                port = int(ports[0]["HostPort"])
                
                exposed_ports: Dict[int, int] = {}
                raw_ports = labels.get("viventium.exposed_ports", "")
                if raw_ports:
                    try:
                        parsed = json.loads(raw_ports)
                        for k, v in (parsed or {}).items():
                            try:
                                exposed_ports[int(k)] = int(v)
                            except (TypeError, ValueError):
                                continue
                    except Exception:
                        pass

                if not exposed_ports and container.ports:
                    for port_key, mappings in container.ports.items():
                        try:
                            container_port = int(str(port_key).split("/")[0])
                        except (TypeError, ValueError):
                            continue
                        if not mappings:
                            continue
                        host_port = mappings[0].get("HostPort")
                        if host_port:
                            try:
                                exposed_ports[container_port] = int(host_port)
                            except (TypeError, ValueError):
                                continue
                
                # Track all host ports used by this container
                if exposed_ports:
                    self.used_ports.update(exposed_ports.values())
                
                self.containers[user_id] = UserContainer(
                    user_id=user_id,
                    container_id=container.id,
                    port=port,
                    exposed_ports=exposed_ports,
                    created_at=datetime.fromisoformat(
                        labels.get("viventium.created_at", datetime.now().isoformat())
                    ),
                    last_activity=datetime.now()
                )
                self.used_ports.add(port)
                logger.info(f"Recovered container for user {user_id} on port {port}")
        except Exception as e:
            logger.error(f"Error recovering containers: {e}")
    
    def _required_ports(self, base_port: int) -> list[int]:
        """All host ports needed for a container starting at base_port."""
        return [base_port + i for i in range(len(USER_EXPOSED_PORTS))]
    
    def _get_free_port(self) -> int:
        """Find an available base port with the full range free."""
        max_start = PORT_RANGE_END - len(USER_EXPOSED_PORTS) + 1
        for port in range(PORT_RANGE_START, max_start + 1):
            required = self._required_ports(port)
            if all(p not in self.used_ports for p in required):
                return port
        raise RuntimeError("No free ports available")
    
    def _get_port_mappings(self, base_port: int) -> Dict[str, int]:
        """Get port mappings for a user container."""
        mappings = {}
        host_port = base_port
        for container_port in USER_EXPOSED_PORTS:
            mappings[f"{container_port}/tcp"] = host_port
            host_port += 1
        return mappings
    
    def _get_user_workspace(self, user_id: str) -> Path:
        """Get or create the user's workspace directory."""
        user_dir = WORKSPACE_BASE / user_id / "workspace"
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir.parent

    def _release_ports(self, ports: Dict[int, int]) -> None:
        for host_port in ports.values():
            self.used_ports.discard(host_port)
    
    async def get_or_create_container(
        self,
        user_id: str,
        claude_code_use_foundry: bool = False,
        anthropic_foundry_api_key: Optional[str] = None,
        anthropic_foundry_resource: Optional[str] = None,
        anthropic_model: Optional[str] = None,
    ) -> UserContainer:
        """Get existing container or create a new one for the user."""

        async with self._lock:
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
                        except Exception:
                            pass
                        self.used_ports.discard(container_info.port)
                        self._release_ports(container_info.exposed_ports)
                        del self.containers[user_id]
                except docker.errors.NotFound:
                    self.used_ports.discard(container_info.port)
                    self._release_ports(container_info.exposed_ports)
                    del self.containers[user_id]
        
            # Create new container
            base_port = self._get_free_port()
            port_mappings = self._get_port_mappings(base_port)
            user_dir = self._get_user_workspace(user_id)
        
        # Track exposed ports
        exposed_ports = {}
        for container_port_spec, host_port in port_mappings.items():
            container_port = int(container_port_spec.split("/")[0])
            exposed_ports[container_port] = host_port
        
        # Build environment variables
        env_vars = {}
        
        # Azure AI Foundry configuration
        use_foundry = claude_code_use_foundry or DEFAULT_CLAUDE_CODE_USE_FOUNDRY == "1"
        if use_foundry:
            env_vars["CLAUDE_CODE_USE_FOUNDRY"] = "1"
            env_vars["ANTHROPIC_FOUNDRY_API_KEY"] = (
                anthropic_foundry_api_key or DEFAULT_ANTHROPIC_FOUNDRY_API_KEY
            )
            env_vars["ANTHROPIC_FOUNDRY_RESOURCE"] = (
                anthropic_foundry_resource or DEFAULT_ANTHROPIC_FOUNDRY_RESOURCE
            )
            env_vars["ANTHROPIC_MODEL"] = (
                anthropic_model or DEFAULT_ANTHROPIC_MODEL
            )
        
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
                ports=port_mappings,
                volumes={
                    str(user_dir / "workspace"): {
                        "bind": "/home/agent/workspace",
                        "mode": "rw",
                    },
                },
                environment=env_vars,
                mem_limit=CONTAINER_MEMORY,
                cpu_count=int(CONTAINER_CPUS),
                restart_policy={"Name": "unless-stopped"},
            )
            
            logger.info(f"Created container for user {user_id} with ports: {exposed_ports}")
            # Mark ports as used only after container is created
            self.used_ports.update(exposed_ports.values())
            
        except docker.errors.ImageNotFound:
            raise RuntimeError(f"Power sandbox image not found: {IMAGE_NAME}")
        
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
        
        # Wait for container to be ready
        await self._wait_for_healthy(agent_api_port)
        
        return container_info

    def cleanup_expired(self) -> None:
        now = datetime.now()
        idle_limit = timedelta(minutes=IDLE_TIMEOUT_MINUTES)
        max_life = (
            timedelta(minutes=MAX_LIFETIME_MINUTES)
            if MAX_LIFETIME_MINUTES > 0
            else None
        )
        for user_id, info in list(self.containers.items()):
            idle_for = now - info.last_activity
            life_for = now - info.created_at
            expired = idle_for > idle_limit
            if max_life is not None and life_for > max_life:
                expired = True
            if not expired:
                continue
            try:
                container = self.docker.containers.get(info.container_id)
                container.remove(force=True)
                logger.info(
                    f"Stopped container for {user_id}: idle={idle_for}, lifetime={life_for}"
                )
            except Exception as exc:
                logger.warning(f"Failed to remove container {info.container_id}: {exc}")
            self.used_ports.discard(info.port)
            self._release_ports(info.exposed_ports)
            self.containers.pop(user_id, None)

    async def cleanup_loop(self) -> None:
        while True:
            await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
            self.cleanup_expired()
    
    async def _wait_for_healthy(self, port: int, timeout: int = 60):
        """Wait for container health endpoint to respond."""
        url = f"http://localhost:{port}/health"
        async with httpx.AsyncClient() as client:
            for i in range(timeout):
                try:
                    resp = await client.get(url, timeout=2)
                    if resp.status_code == 200:
                        logger.info(f"Container on port {port} is healthy (took {i+1}s)")
                        return
                except:
                    pass
                await asyncio.sleep(1)
        
        raise RuntimeError(f"Container on port {port} did not become healthy after {timeout}s")
    
    def get_container_url(self, user_id: str) -> Optional[str]:
        """Get the API URL for a user's container."""
        if user_id in self.containers:
            port = self.containers[user_id].port
            return f"http://localhost:{port}"
        return None


# Global container manager
container_manager = ContainerManager()


# ============== FASTAPI APP ==============

app = FastAPI(
    title="Power Agent VM Manager",
    description="Manages per-user Docker containers for Power Agents"
)


@app.on_event("startup")
async def start_cleanup_loop() -> None:
    asyncio.create_task(container_manager.cleanup_loop())


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "public_ip": get_public_ip(),
        "active_containers": len(container_manager.containers),
        "workspace_base": str(WORKSPACE_BASE),
        "image": IMAGE_NAME,
        "idle_timeout_minutes": IDLE_TIMEOUT_MINUTES,
        "max_lifetime_minutes": MAX_LIFETIME_MINUTES or None,
    }


@app.post("/containers", response_model=ContainerResponse)
async def create_container(request: CreateContainerRequest):
    """Create or get a container for a user."""
    try:
        container = await container_manager.get_or_create_container(
            user_id=request.user_id,
            claude_code_use_foundry=request.claude_code_use_foundry,
            anthropic_foundry_api_key=request.anthropic_foundry_api_key,
            anthropic_foundry_resource=request.anthropic_foundry_resource,
            anthropic_model=request.anthropic_model,
        )
        
        return ContainerResponse(
            user_id=container.user_id,
            container_id=container.container_id,
            status="running",
            api_port=container.port,
            exposed_ports=container.exposed_ports,
            vm_public_ip=get_public_ip(),
        )
    except Exception as e:
        logger.error(f"Error creating container: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.api_route("/proxy/{user_id}/{path:path}", methods=["GET", "POST"])
async def proxy_to_container(user_id: str, path: str, request: Request):
    """Proxy requests to a user's container."""
    from starlette.responses import StreamingResponse
    
    # Get container URL
    container_url = container_manager.get_container_url(user_id)
    if not container_url:
        # Try to create container
        try:
            container = await container_manager.get_or_create_container(user_id)
            container_url = f"http://localhost:{container.port}"
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Container not available: {e}")
    
    # Update activity
    if user_id in container_manager.containers:
        container_manager.containers[user_id].last_activity = datetime.now()
    
    # Forward the request
    target_url = f"{container_url}/{path}"
    
    async with httpx.AsyncClient(timeout=httpx.Timeout(600.0, connect=30.0)) as client:
        # Get request body if POST
        body = None
        if request.method == "POST":
            body = await request.body()
        
        # Get query params
        params = dict(request.query_params)
        
        if request.method == "POST":
            # Check if streaming endpoint
            if "stream" in path:
                async def stream_response():
                    async with client.stream(
                        "POST",
                        target_url,
                        content=body,
                        params=params,
                    ) as resp:
                        async for chunk in resp.aiter_bytes():
                            yield chunk
                
                return StreamingResponse(
                    stream_response(),
                    media_type="text/event-stream",
                )
            else:
                resp = await client.post(target_url, content=body, params=params)
        else:
            resp = await client.get(target_url, params=params)
        
        return resp.json()


# ============== RUN ==============

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)

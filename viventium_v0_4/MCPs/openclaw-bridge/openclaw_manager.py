# VIVENTIUM START
# Purpose: Manages per-user OpenClaw Gateway instances for the openclaw-bridge MCP server.
#
# Ground truth contracts (from openclaw source):
#   - Gateway multiplexes WS+HTTP on a SINGLE port (gateway.port, default 18789)
#   - Config file: openclaw.json in OPENCLAW_STATE_DIR (~/.openclaw/)
#   - Config schema: OpenClawConfig (types.openclaw.ts) — no top-level "agent"
#   - CLI: `openclaw gateway --port PORT --bind loopback --token TOKEN --allow-unconfigured`
#   - bind is a mode: "loopback"|"lan"|"auto"|"custom"|"tailnet" (NOT an IP:PORT)
#   - Reviewed runtime identity: GET /health -> {"ok":true,"status":"live"}
#   - Plugin manifest: openclaw.plugin.json (required: id, configSchema)
#   - Plugin paths: plugins.load.paths in config
#
# Added for VM POC:
#   - VM identity is (user_id, vm_id)
#   - Runtime selection: OPENCLAW_RUNTIME=e2b|direct (default E2B; direct is explicit)
#   - E2B sandbox lifecycle support with pause/resume/terminate
#   - Registry persistence for VM recovery across bridge restarts
# VIVENTIUM END

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import secrets
import shlex
import socket
import stat
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import httpx

from e2b_runtime import E2BRuntimeAdapter
from vm_registry import VMRegistry, VMRegistryRecord

logger = logging.getLogger(__name__)

# ============== CONFIGURATION ==============

_default_data_dir = os.path.expanduser("~/.viventium/openclaw/users")
DATA_DIR = Path(os.environ.get("OPENCLAW_DATA_DIR", _default_data_dir))

# Port allocation range for direct runtime per-user OpenClaw instances.
PORT_RANGE_START = int(os.environ.get("OPENCLAW_PORT_START", "18800"))
PORT_RANGE_END = int(os.environ.get("OPENCLAW_PORT_END", "18999"))

# Internal OpenClaw gateway port used inside sandboxes / processes.
OPENCLAW_GATEWAY_PORT = int(os.environ.get("OPENCLAW_GATEWAY_PORT", "18789"))

# Idle timeout before pausing an instance.
IDLE_TIMEOUT_HOURS = float(os.environ.get("OPENCLAW_IDLE_TIMEOUT_HOURS", "2"))

# Runtime mode.
OPENCLAW_RUNTIME = os.environ.get("OPENCLAW_RUNTIME", "e2b").strip().lower()
OPENCLAW_RUNTIME_ALLOW_FALLBACK = os.environ.get(
    "OPENCLAW_RUNTIME_ALLOW_FALLBACK", "false"
).strip().lower() in {"1", "true", "yes", "on"}
OPENCLAW_DIRECT_HOST_EXEC_ALLOWED = os.environ.get(
    "OPENCLAW_ALLOW_DIRECT_HOST_EXEC", "false"
).strip().lower() in {"1", "true", "yes", "on"}

# VIVENTIUM START: reviewed runtime and network-discovery privacy contract.
OPENCLAW_REQUIRED_VERSION = "2026.7.1-2"
OPENCLAW_DISABLE_BONJOUR = "1"
# VIVENTIUM END

# Default VM id for backward-compatible single-VM calls.
OPENCLAW_DEFAULT_VM_ID = os.environ.get("OPENCLAW_DEFAULT_VM_ID", "001")

# Path to OpenClaw binary (direct runtime).
OPENCLAW_BIN = os.environ.get("OPENCLAW_BIN", "openclaw")

# Bridge auth token fallback; per-VM tokens are generated when possible.
OPENCLAW_BRIDGE_AUTH_TOKEN = os.environ.get("OPENCLAW_BRIDGE_AUTH_TOKEN", "viventium-bridge-local")

# LLM provider API keys passed into direct runtime processes.
_PROVIDER_ENV_KEYS = [
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "XAI_API_KEY",
    "GROQ_API_KEY",
    "OPENROUTER_API_KEY",
    "GEMINI_API_KEY",
    "DEEPSEEK_API_KEY",
    "GOOGLE_API_KEY",
    "ELEVENLABS_API_KEY",
    "FIRECRAWL_API_KEY",
]

# Default model for OpenClaw agent.
OPENCLAW_MODEL = os.environ.get("OPENCLAW_MODEL", "anthropic/claude-sonnet-4-20250514")

# Optional channel-bridge plugin wiring (direct runtime).
OPENCLAW_CHANNEL_BRIDGE_ENABLED = os.environ.get("OPENCLAW_CHANNEL_BRIDGE_ENABLED", "").lower() in (
    "1",
    "true",
    "yes",
    "on",
)
OPENCLAW_CHANNEL_PLUGIN_PATH = os.environ.get("OPENCLAW_CHANNEL_PLUGIN_PATH", "").strip()
OPENCLAW_CHANNEL_LIBRECHAT_URL = (
    os.environ.get("OPENCLAW_CHANNEL_LIBRECHAT_URL", "").strip()
    or os.environ.get("VIVENTIUM_LIBRECHAT_URL", "").strip()
    or "http://localhost:3080"
)
OPENCLAW_CHANNEL_GATEWAY_SECRET = os.environ.get("VIVENTIUM_GATEWAY_SECRET", "").strip()
OPENCLAW_CHANNEL_GATEWAY_HMAC_SECRET = os.environ.get("VIVENTIUM_GATEWAY_HMAC_SECRET", "").strip()
OPENCLAW_CHANNEL_AGENT_ID = os.environ.get("VIVENTIUM_AGENT_ID", "").strip()

# Readiness probe timeout.
READINESS_TIMEOUT = int(os.environ.get("OPENCLAW_READINESS_TIMEOUT", "45"))

# Log directory for direct subprocess output.
LOG_DIR = Path(os.environ.get("OPENCLAW_LOG_DIR", os.path.expanduser("~/.viventium/logs/openclaw")))

# Registry file
REGISTRY_PATH = DATA_DIR / "vm_registry.json"

_IDENTIFIER_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}\Z", re.ASCII)


def normalize_user_id(user_id: str) -> str:
    """Return a path-safe, stable user identifier or fail closed."""
    raw = str(user_id).strip().lower()
    if not _IDENTIFIER_RE.fullmatch(raw):
        raise ValueError(
            "User id must be 1-64 ASCII lowercase letters, digits, underscores, or hyphens"
        )
    return raw


def normalize_vm_id(vm_id: str | None) -> str:
    """Normalize VM ids to a stable human-readable form, e.g. 001."""
    if vm_id is None:
        vm_id = OPENCLAW_DEFAULT_VM_ID
    raw = str(vm_id).strip().lower()
    if not raw:
        raise ValueError("VM id must not be empty")
    if raw.startswith("vm-"):
        raw = raw[3:]
    if raw.isdigit():
        raw = raw.zfill(3)
    if not _IDENTIFIER_RE.fullmatch(raw):
        raise ValueError(
            "VM id must be 1-64 ASCII lowercase letters, digits, underscores, or hyphens"
        )
    return raw


def _ensure_private_directory(path: Path) -> Path:
    """Create or validate an owner-only directory without following a symlink."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        path.mkdir(mode=0o700, parents=True, exist_ok=False)
        info = path.lstat()

    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise RuntimeError(f"Refusing unsafe runtime directory: {path}")
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise RuntimeError(f"Refusing unsafe runtime directory ownership or permissions: {path}")
    return path


def _atomic_private_json(path: Path, payload: dict) -> None:
    """Atomically write secret-bearing JSON as an owner-only regular file."""
    parent = _ensure_private_directory(path.parent)
    if path.exists() or path.is_symlink():
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            raise RuntimeError(f"Refusing unsafe runtime file: {path}")
        if info.st_uid != os.getuid():
            raise RuntimeError(f"Refusing runtime file owned by another user: {path}")

    temp_path = parent / f".{path.name}.{secrets.token_hex(8)}.tmp"
    fd = os.open(temp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
        os.chmod(path, 0o600, follow_symlinks=False)
    finally:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass


def _open_private_append(path: Path):
    """Open an owner-only append log without following a symlink."""
    _ensure_private_directory(path.parent)
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
        os.close(fd)
        raise RuntimeError(f"Refusing unsafe runtime log: {path}")
    os.fchmod(fd, 0o600)
    return os.fdopen(fd, "a", encoding="utf-8")


# ============== DATA CLASSES ==============


@dataclass
class OpenClawInstance:
    """Tracks one VM-scoped OpenClaw environment."""

    user_id: str
    vm_id: str = OPENCLAW_DEFAULT_VM_ID
    runtime: str = "direct"
    state: str = "running"

    sandbox_id: Optional[str] = None
    gateway_url: str = ""
    gateway_token: str = OPENCLAW_BRIDGE_AUTH_TOKEN
    desktop_url: str = ""
    desktop_auth_key: str = ""

    # Direct runtime fields
    port: Optional[int] = None
    pid: Optional[int] = None
    state_dir: Path = field(default_factory=Path)

    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        self.user_id = normalize_user_id(self.user_id)
        self.vm_id = normalize_vm_id(self.vm_id)

    @property
    def key(self) -> Tuple[str, str]:
        return (self.user_id, self.vm_id)

    @property
    def base_url(self) -> str:
        if self.gateway_url:
            return self.gateway_url.rstrip("/")
        if self.port:
            return f"http://127.0.0.1:{self.port}"
        return ""

    @property
    def tools_invoke_url(self) -> str:
        base = self.base_url
        return f"{base}/tools/invoke" if base else ""

    @property
    def responses_url(self) -> str:
        base = self.base_url
        return f"{base}/v1/responses" if base else ""

    def to_registry_record(self) -> VMRegistryRecord:
        return VMRegistryRecord(
            user_id=self.user_id,
            vm_id=self.vm_id,
            runtime=self.runtime,
            state=self.state,
            sandbox_id=self.sandbox_id,
            gateway_url=self.gateway_url,
            gateway_token=self.gateway_token,
            desktop_url=self.desktop_url,
            desktop_auth_key=self.desktop_auth_key,
            port=self.port,
            pid=self.pid,
            state_dir=str(self.state_dir),
            created_at=self.created_at.isoformat(),
            last_activity=self.last_activity.isoformat(),
        )

    @classmethod
    def from_registry_record(cls, record: VMRegistryRecord) -> "OpenClawInstance":
        created_at = datetime.fromisoformat(record.created_at) if record.created_at else datetime.now()
        last_activity = (
            datetime.fromisoformat(record.last_activity)
            if record.last_activity
            else created_at
        )
        return cls(
            user_id=record.user_id,
            vm_id=record.vm_id,
            runtime=record.runtime,
            state=record.state,
            sandbox_id=record.sandbox_id,
            gateway_url=record.gateway_url,
            gateway_token=record.gateway_token or OPENCLAW_BRIDGE_AUTH_TOKEN,
            desktop_url=record.desktop_url,
            desktop_auth_key=record.desktop_auth_key,
            port=record.port,
            pid=record.pid,
            state_dir=Path(record.state_dir) if record.state_dir else Path(),
            created_at=created_at,
            last_activity=last_activity,
        )


# ============== OPENCLAW MANAGER ==============


class OpenClawManager:
    """Manages VM-scoped OpenClaw runtimes.

    Runtime modes:
    - e2b: one E2B sandbox per (user_id, vm_id)
    - direct: one local OpenClaw process per (user_id, vm_id)
    """

    def __init__(self):
        self.instances: Dict[object, OpenClawInstance] = {}
        self.used_ports: set = set()
        self._port_reservations: Dict[int, socket.socket] = {}
        self._owned_processes: Dict[Tuple[str, str], asyncio.subprocess.Process] = {}
        self._vm_locks: Dict[Tuple[str, str], asyncio.Lock] = {}
        self._cleanup_task: Optional[asyncio.Task] = None

        _ensure_private_directory(DATA_DIR)
        _ensure_private_directory(LOG_DIR)

        self.registry = VMRegistry(REGISTRY_PATH)
        if OPENCLAW_RUNTIME not in {"e2b", "direct"}:
            raise ValueError("OPENCLAW_RUNTIME must be direct or e2b")
        self.runtime_mode = OPENCLAW_RUNTIME
        self.e2b_runtime = E2BRuntimeAdapter(
            gateway_port=OPENCLAW_GATEWAY_PORT,
            default_model=OPENCLAW_MODEL,
        )

        if self.runtime_mode == "e2b" and not self.e2b_runtime.available and OPENCLAW_RUNTIME_ALLOW_FALLBACK:
            logger.warning(
                "OPENCLAW_RUNTIME=e2b requested but E2B SDK is unavailable; falling back to direct runtime"
            )
            self.runtime_mode = "direct"

        if self.runtime_mode == "direct" and not OPENCLAW_DIRECT_HOST_EXEC_ALLOWED:
            raise RuntimeError(
                "The direct OpenClaw runtime can execute on the host. "
                "Use the sandboxed OPENCLAW_RUNTIME=e2b default, or explicitly set "
                "OPENCLAW_ALLOW_DIRECT_HOST_EXEC=true after reviewing that risk."
            )

        self._load_registry()
        self._reconcile_registry()

        logger.info(
            "OpenClawManager initialized: runtime=%s data_dir=%s direct_port_range=%s-%s",
            self.runtime_mode,
            DATA_DIR,
            PORT_RANGE_START,
            PORT_RANGE_END,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _instance_key(self, user_id: str, vm_id: str) -> Tuple[str, str]:
        return (normalize_user_id(user_id), normalize_vm_id(vm_id))

    def _get_vm_lock(self, user_id: str, vm_id: str) -> asyncio.Lock:
        key = self._instance_key(user_id, vm_id)
        if key not in self._vm_locks:
            self._vm_locks[key] = asyncio.Lock()
        return self._vm_locks[key]

    def _set_instance(self, instance: OpenClawInstance) -> None:
        key = instance.key
        self.instances[key] = instance
        # Backward compatibility for tests/older call sites using single-key dictionary.
        if instance.vm_id == OPENCLAW_DEFAULT_VM_ID:
            self.instances[instance.user_id] = instance

    def _remove_instance(self, user_id: str, vm_id: str) -> None:
        key = self._instance_key(user_id, vm_id)
        self.instances.pop(key, None)
        if vm_id == OPENCLAW_DEFAULT_VM_ID:
            self.instances.pop(user_id, None)

    def _get_instance(self, user_id: str, vm_id: str) -> Optional[OpenClawInstance]:
        key = self._instance_key(user_id, vm_id)
        inst = self.instances.get(key)
        if inst:
            return inst
        if vm_id == OPENCLAW_DEFAULT_VM_ID:
            legacy = self.instances.get(user_id)
            if isinstance(legacy, OpenClawInstance):
                return legacy
        return None

    # VIVENTIUM START: Public VM accessors for MCP control surface.
    def get_instance(self, user_id: str, vm_id: str = OPENCLAW_DEFAULT_VM_ID) -> Optional[OpenClawInstance]:
        return self._get_instance(user_id, normalize_vm_id(vm_id))

    def touch_instance(self, user_id: str, vm_id: str = OPENCLAW_DEFAULT_VM_ID) -> None:
        vm = normalize_vm_id(vm_id)
        instance = self._get_instance(user_id, vm)
        if not instance:
            return
        instance.last_activity = datetime.now()
        self._set_instance(instance)
        self._persist_instance(instance)
    # VIVENTIUM END

    def _iter_instances(self) -> List[OpenClawInstance]:
        seen: set[Tuple[str, str]] = set()
        out: List[OpenClawInstance] = []
        for value in self.instances.values():
            if not isinstance(value, OpenClawInstance):
                continue
            if value.key in seen:
                continue
            seen.add(value.key)
            out.append(value)
        return out

    def _persist_instance(self, instance: OpenClawInstance) -> None:
        self.registry.upsert(instance.to_registry_record())

    def _load_registry(self) -> None:
        for record in self.registry.list_records():
            instance = OpenClawInstance.from_registry_record(record)
            self._set_instance(instance)
            if instance.runtime == "direct" and instance.port:
                self.used_ports.add(instance.port)

    def _reconcile_registry(self) -> None:
        """Reconcile persisted E2B VM records with live E2B sandbox metadata/state."""
        # VIVENTIUM START: Startup reconciliation for E2B VM registry.
        if self.runtime_mode != "e2b":
            return
        if not self.e2b_runtime.available:
            return
        if not os.environ.get("E2B_API_KEY", "").strip():
            logger.info("Skipping E2B VM registry reconciliation (E2B_API_KEY missing)")
            return

        try:
            remote_sandboxes = self.e2b_runtime.list_vm_sandboxes()
        except Exception as exc:
            logger.warning("Unable to reconcile VM registry with E2B: %s", exc)
            return

        remote_map: Dict[Tuple[str, str], Dict] = {}
        for sandbox in remote_sandboxes:
            metadata = sandbox.get("metadata", {}) or {}
            try:
                user_id = normalize_user_id(
                    str(metadata.get("viventium_user", "")).strip()
                )
                vm_id = normalize_vm_id(
                    str(metadata.get("viventium_vm_id", "")).strip()
                )
            except ValueError:
                logger.warning("Ignoring E2B sandbox with invalid Viventium identity metadata")
                continue
            remote_map[(user_id, vm_id)] = sandbox

        for instance in list(self._iter_instances()):
            if instance.runtime != "e2b":
                continue

            remote = remote_map.get(instance.key)
            if not remote:
                logger.info(
                    "Removing stale VM record for %s/%s; sandbox no longer exists",
                    instance.user_id,
                    instance.vm_id,
                )
                self._remove_instance(instance.user_id, instance.vm_id)
                self.registry.delete(instance.user_id, instance.vm_id)
                continue

            remote_state = str(remote.get("state", "unknown")).lower()
            if remote_state == "running":
                instance.state = "running"
            elif "pause" in remote_state:
                instance.state = "paused"
            else:
                instance.state = remote_state

            instance.sandbox_id = remote.get("sandbox_id") or instance.sandbox_id
            instance.last_activity = datetime.now()
            self._set_instance(instance)
            self._persist_instance(instance)
        # VIVENTIUM END

    def _new_gateway_token(self) -> str:
        return secrets.token_urlsafe(24)

    # ------------------------------------------------------------------
    # Port allocation (direct runtime)
    # ------------------------------------------------------------------

    def _get_free_port(self) -> int:
        for port in range(PORT_RANGE_START, PORT_RANGE_END):
            if port in self.used_ports:
                continue
            reservation = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                reservation.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
                reservation.bind(("127.0.0.1", port))
                reservation.listen(1)
            except OSError:
                reservation.close()
                continue
            self.used_ports.add(port)
            self._port_reservations[port] = reservation
            return port
        raise RuntimeError("No free ports available for OpenClaw instance")

    def _release_port(self, instance: OpenClawInstance):
        if instance.port:
            reservation = self._port_reservations.pop(instance.port, None)
            if reservation:
                reservation.close()
            self.used_ports.discard(instance.port)

    def _reserve_exact_port(self, port: int) -> None:
        if port in self._port_reservations:
            return
        reservation = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            reservation.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
            reservation.bind(("127.0.0.1", port))
            reservation.listen(1)
        except OSError as exc:
            reservation.close()
            raise RuntimeError(f"OpenClaw port {port} is already in use") from exc
        self.used_ports.add(port)
        self._port_reservations[port] = reservation

    def _consume_port_reservation(self, port: int) -> None:
        reservation = self._port_reservations.pop(port, None)
        if reservation:
            reservation.close()

    # ------------------------------------------------------------------
    # State directory (direct runtime)
    # ------------------------------------------------------------------

    def _get_user_state_dir(self, user_id: str, vm_id: Optional[str] = None) -> Path:
        """Create per-user/per-vm state directory.

        OpenClaw expects:
        - $STATE_DIR/openclaw.json
        - $STATE_DIR/workspace/
        """
        user = normalize_user_id(user_id)
        vm = normalize_vm_id(vm_id)
        root = _ensure_private_directory(DATA_DIR)
        user_root = _ensure_private_directory(root / user)
        state_dir = _ensure_private_directory(user_root / f"vm-{vm}")
        _ensure_private_directory(state_dir / "workspace")
        return state_dir

    # ------------------------------------------------------------------
    # Config generation (direct runtime)
    # ------------------------------------------------------------------

    def _generate_config(
        self,
        user_id: str,
        state_dir: Path,
        port: int,
        gateway_token: Optional[str] = None,
    ) -> Path:
        """Generate openclaw.json matching OpenClawConfig."""
        token = gateway_token or OPENCLAW_BRIDGE_AUTH_TOKEN
        config: dict = {
            "gateway": {
                "port": port,
                "mode": "local",
                "bind": "loopback",
                "auth": {
                    "mode": "token",
                    "token": token,
                },
                "http": {
                    "endpoints": {
                        "responses": {"enabled": True},
                    },
                },
            },
            "agents": {
                "defaults": {
                    "model": {
                        "primary": OPENCLAW_MODEL,
                    },
                },
            },
            "session": {
                "dmScope": "per-channel-peer",
            },
            "plugins": {
                "enabled": True,
            },
        }

        if OPENCLAW_CHANNEL_BRIDGE_ENABLED:
            if not OPENCLAW_CHANNEL_PLUGIN_PATH:
                logger.warning(
                    "OPENCLAW_CHANNEL_BRIDGE_ENABLED=true but OPENCLAW_CHANNEL_PLUGIN_PATH is empty; skipping plugin wiring"
                )
            elif not OPENCLAW_CHANNEL_GATEWAY_SECRET:
                logger.warning(
                    "OPENCLAW_CHANNEL_BRIDGE_ENABLED=true but VIVENTIUM_GATEWAY_SECRET is empty; skipping plugin wiring"
                )
            else:
                plugin_config: dict = {
                    "librechatUrl": OPENCLAW_CHANNEL_LIBRECHAT_URL,
                    "gatewaySecret": OPENCLAW_CHANNEL_GATEWAY_SECRET,
                }
                if OPENCLAW_CHANNEL_GATEWAY_HMAC_SECRET:
                    plugin_config["gatewayHmacSecret"] = OPENCLAW_CHANNEL_GATEWAY_HMAC_SECRET
                if OPENCLAW_CHANNEL_AGENT_ID:
                    plugin_config["agentId"] = OPENCLAW_CHANNEL_AGENT_ID

                config["plugins"]["allow"] = ["viventium-channel-bridge"]
                config["plugins"]["load"] = {"paths": [OPENCLAW_CHANNEL_PLUGIN_PATH]}
                config["plugins"]["entries"] = {
                    "viventium-channel-bridge": {
                        "enabled": True,
                        "config": plugin_config,
                    }
                }

        config_path = state_dir / "openclaw.json"
        _atomic_private_json(config_path, config)
        logger.info("Generated config for user %s", normalize_user_id(user_id))
        return config_path

    # ------------------------------------------------------------------
    # Direct runtime lifecycle
    # ------------------------------------------------------------------

    @staticmethod
    def _reviewed_openclaw_command() -> List[str]:
        """Return the configured command only when it is the exact reviewed runtime."""
        bin_parts = shlex.split(OPENCLAW_BIN)
        if not bin_parts:
            raise RuntimeError("OPENCLAW_BIN is empty")
        try:
            result = subprocess.run(
                [*bin_parts, "--version"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError(
                f"OpenClaw reviewed runtime {OPENCLAW_REQUIRED_VERSION} is unavailable; "
                "run the Viventium OpenClaw launcher."
            ) from exc

        reported_versions = [
            line.strip() for line in result.stdout.splitlines() if line.strip()
        ]
        version_matches = any(
            line == OPENCLAW_REQUIRED_VERSION
            or line.startswith(f"OpenClaw {OPENCLAW_REQUIRED_VERSION} (")
            for line in reported_versions
        )
        if result.returncode != 0 or not version_matches:
            raise RuntimeError(
                f"OpenClaw must be the reviewed {OPENCLAW_REQUIRED_VERSION} runtime; "
                "no mutable or mismatched fallback is allowed."
            )
        return bin_parts

    async def _start_instance(
        self,
        user_id: str,
        state_dir: Path,
        port: int,
        vm_id: str = OPENCLAW_DEFAULT_VM_ID,
        gateway_token: Optional[str] = None,
    ) -> OpenClawInstance:
        """Start an OpenClaw gateway as a local child process (direct runtime)."""
        user = normalize_user_id(user_id)
        vm = normalize_vm_id(vm_id)
        token = gateway_token or self._new_gateway_token()
        bin_parts = self._reviewed_openclaw_command()

        self._reserve_exact_port(port)

        self._generate_config(user, state_dir, port, gateway_token=token)

        log_stdout = _open_private_append(LOG_DIR / f"{user}-{vm}.stdout.log")
        log_stderr = _open_private_append(LOG_DIR / f"{user}-{vm}.stderr.log")

        env = {**os.environ}
        env["OPENCLAW_STATE_DIR"] = str(state_dir)
        env["OPENCLAW_CONFIG_PATH"] = str(state_dir / "openclaw.json")
        env["OPENCLAW_GATEWAY_TOKEN"] = token
        env["OPENCLAW_DISABLE_BONJOUR"] = OPENCLAW_DISABLE_BONJOUR

        for key in _PROVIDER_ENV_KEYS:
            val = os.environ.get(key, "")
            if val:
                env[key] = val

        cmd = [
            *bin_parts,
            "gateway",
            "--port",
            str(port),
            "--bind",
            "loopback",
            "--token",
            token,
            "--allow-unconfigured",
        ]

        logger.info(
            "Starting reviewed OpenClaw (direct) for %s/%s on loopback port %s",
            user,
            vm,
            port,
        )

        process = None
        try:
            # Keep the loopback port reserved until the exact moment the reviewed
            # child is spawned. If another process wins the remaining race, the
            # child exits and the identity-specific readiness probe fails closed.
            self._consume_port_reservation(port)
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=log_stdout,
                stderr=log_stderr,
                env=env,
                cwd=str(state_dir / "workspace"),
            )
        except FileNotFoundError:
            self.used_ports.discard(port)
            raise RuntimeError(
                f"OpenClaw binary not found at '{OPENCLAW_BIN}'. "
                f"Run the Viventium OpenClaw launcher to install the reviewed {OPENCLAW_REQUIRED_VERSION} runtime."
            )
        except Exception:
            self.used_ports.discard(port)
            raise

        finally:
            log_stdout.close()
            log_stderr.close()

        instance = OpenClawInstance(
            user_id=user,
            vm_id=vm,
            runtime="direct",
            state="running",
            gateway_token=token,
            port=port,
            pid=process.pid,
            state_dir=state_dir,
            gateway_url=f"http://127.0.0.1:{port}",
            created_at=datetime.now(),
            last_activity=datetime.now(),
        )
        self._owned_processes[instance.key] = process

        try:
            await self._wait_for_ready(instance, timeout=READINESS_TIMEOUT, process=process)
        except Exception:
            await self._stop_direct_process(instance)
            self._release_port(instance)
            raise
        return instance

    async def _wait_for_ready(
        self,
        instance: OpenClawInstance,
        timeout: int = 45,
        process: Optional[asyncio.subprocess.Process] = None,
    ):
        """Require the reviewed runtime's exact loopback health identity."""
        if not instance.base_url:
            raise RuntimeError("Instance has no base_url")

        deadline = time.time() + timeout

        async with httpx.AsyncClient() as client:
            while time.time() < deadline:
                if process is not None and process.returncode is not None:
                    raise RuntimeError(
                        f"OpenClaw instance for {instance.user_id}/{instance.vm_id} exited before readiness"
                    )
                try:
                    resp = await client.get(f"{instance.base_url}/health", timeout=3)
                    if resp.status_code == 200 and resp.json() == {"ok": True, "status": "live"}:
                        logger.info(
                            "OpenClaw instance for %s/%s ready",
                            instance.user_id,
                            instance.vm_id,
                        )
                        return
                except (
                    httpx.ConnectError,
                    httpx.ReadTimeout,
                    httpx.ConnectTimeout,
                    json.JSONDecodeError,
                    ValueError,
                ):
                    pass
                await asyncio.sleep(1)

        raise RuntimeError(
            f"OpenClaw instance for {instance.user_id}/{instance.vm_id} not ready within {timeout}s"
        )

    async def _stop_direct_process(self, instance: OpenClawInstance):
        process = self._owned_processes.pop(instance.key, None)
        if process is None or process.pid != instance.pid:
            # A persisted PID is not proof of ownership after a bridge restart.
            # Never signal a potentially reused PID; the default E2B runtime
            # does not have this direct-host lifecycle limitation.
            instance.pid = None
            return
        try:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=2)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
        except ProcessLookupError:
            pass
        instance.pid = None

    # ------------------------------------------------------------------
    # Runtime lifecycle (public)
    # ------------------------------------------------------------------

    async def _start_or_resume_e2b(self, user_id: str, vm_id: str, existing: Optional[OpenClawInstance]) -> OpenClawInstance:
        gateway_token = (existing.gateway_token if existing and existing.gateway_token else self._new_gateway_token())
        sandbox_id = existing.sandbox_id if existing else None

        result = self.e2b_runtime.ensure_vm_running(
            user_id=user_id,
            vm_id=vm_id,
            sandbox_id=sandbox_id,
            gateway_token=gateway_token,
        )

        instance = existing or OpenClawInstance(
            user_id=user_id,
            vm_id=vm_id,
            runtime="e2b",
            state="running",
            gateway_token=gateway_token,
            state_dir=self._get_user_state_dir(user_id, vm_id),
            created_at=datetime.now(),
            last_activity=datetime.now(),
        )

        instance.runtime = "e2b"
        instance.state = "running"
        instance.sandbox_id = result["sandbox_id"]
        instance.gateway_url = result["gateway_url"]
        instance.gateway_token = gateway_token
        instance.last_activity = datetime.now()
        if not instance.created_at:
            instance.created_at = datetime.now()
        return instance

    async def get_or_create_instance(self, user_id: str, vm_id: str = OPENCLAW_DEFAULT_VM_ID) -> OpenClawInstance:
        vm = normalize_vm_id(vm_id)
        lock = self._get_vm_lock(user_id, vm)

        async with lock:
            existing = self._get_instance(user_id, vm)

            if existing:
                if await self._is_alive(existing):
                    existing.state = "running"
                    existing.last_activity = datetime.now()
                    self._set_instance(existing)
                    self._persist_instance(existing)
                    return existing

                # Instance record exists but runtime is unavailable; recover below.
                logger.warning("Instance for %s/%s not alive, recreating", user_id, vm)

            if self.runtime_mode == "e2b":
                instance = await self._start_or_resume_e2b(user_id, vm, existing)
            else:
                if existing and existing.port:
                    port = existing.port
                else:
                    port = self._get_free_port()
                state_dir = self._get_user_state_dir(user_id, vm)
                try:
                    instance = await self._start_instance(
                        user_id,
                        state_dir,
                        port,
                        vm_id=vm,
                        gateway_token=existing.gateway_token if existing else None,
                    )
                except Exception:
                    # Release newly allocated port on startup failure.
                    if not existing:
                        self.used_ports.discard(port)
                    raise

            self._set_instance(instance)
            self._persist_instance(instance)
            return instance

    async def start_instance(self, user_id: str, vm_id: str = OPENCLAW_DEFAULT_VM_ID) -> OpenClawInstance:
        return await self.get_or_create_instance(user_id, vm_id)

    async def resume_instance(self, user_id: str, vm_id: str = OPENCLAW_DEFAULT_VM_ID) -> OpenClawInstance:
        vm = normalize_vm_id(vm_id)
        lock = self._get_vm_lock(user_id, vm)
        async with lock:
            existing = self._get_instance(user_id, vm)
            if self.runtime_mode == "e2b":
                instance = await self._start_or_resume_e2b(user_id, vm, existing)
                self._set_instance(instance)
                self._persist_instance(instance)
                return instance

            # direct runtime resume => restart process in same state dir/port
            if existing and await self._is_alive(existing):
                existing.state = "running"
                existing.last_activity = datetime.now()
                self._persist_instance(existing)
                return existing

            port = existing.port if existing and existing.port else self._get_free_port()
            state_dir = self._get_user_state_dir(user_id, vm)
            instance = await self._start_instance(
                user_id,
                state_dir,
                port,
                vm_id=vm,
                gateway_token=existing.gateway_token if existing else None,
            )
            self._set_instance(instance)
            self._persist_instance(instance)
            return instance

    async def _is_alive(self, instance: OpenClawInstance) -> bool:
        if instance.runtime == "e2b":
            if not instance.sandbox_id:
                return False
            try:
                state = self.e2b_runtime.get_state(instance.sandbox_id)
                return str(state).lower() == "running"
            except Exception:
                return False

        if not instance.base_url or not instance.pid:
            return False

        try:
            os.kill(instance.pid, 0)
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{instance.base_url}/health", timeout=3)
                return resp.status_code == 200 and resp.json() == {"ok": True, "status": "live"}
        except Exception:
            return False

    async def stop_instance(self, user_id: str, vm_id: str = OPENCLAW_DEFAULT_VM_ID):
        """Pause a user's VM instance (stop semantics = pause/resume)."""
        vm = normalize_vm_id(vm_id)
        lock = self._get_vm_lock(user_id, vm)
        async with lock:
            instance = self._get_instance(user_id, vm)
            if not instance:
                return

            if instance.runtime == "e2b":
                if instance.sandbox_id:
                    self.e2b_runtime.pause_vm(instance.sandbox_id)
                instance.state = "paused"
                instance.last_activity = datetime.now()
                self._set_instance(instance)
                self._persist_instance(instance)
                return

            await self._stop_direct_process(instance)
            instance.state = "paused"
            instance.last_activity = datetime.now()
            self._set_instance(instance)
            self._persist_instance(instance)

    async def terminate_instance(self, user_id: str, vm_id: str = OPENCLAW_DEFAULT_VM_ID):
        """Hard-stop a VM and remove it from manager+registry."""
        vm = normalize_vm_id(vm_id)
        lock = self._get_vm_lock(user_id, vm)
        async with lock:
            instance = self._get_instance(user_id, vm)
            if not instance:
                return

            if instance.runtime == "e2b":
                if instance.sandbox_id:
                    self.e2b_runtime.terminate_vm(instance.sandbox_id)
            else:
                await self._stop_direct_process(instance)
                self._release_port(instance)

            self._remove_instance(user_id, vm)
            self.registry.delete(user_id, vm)

    async def stop_all(self):
        for instance in self._iter_instances():
            await self.stop_instance(instance.user_id, instance.vm_id)

    async def terminate_all(self):
        for instance in self._iter_instances():
            await self.terminate_instance(instance.user_id, instance.vm_id)

    def get_instance_info(self, user_id: str, vm_id: str = OPENCLAW_DEFAULT_VM_ID) -> Optional[Dict]:
        vm = normalize_vm_id(vm_id)
        inst = self._get_instance(user_id, vm)
        if not inst:
            return None
        return {
            "user_id": inst.user_id,
            "vm_id": inst.vm_id,
            "runtime": inst.runtime,
            "state": inst.state,
            "sandbox_id": inst.sandbox_id,
            "port": inst.port,
            "pid": inst.pid,
            "base_url": inst.base_url,
            "tools_invoke_url": inst.tools_invoke_url,
            "responses_url": inst.responses_url,
            "desktop_url": inst.desktop_url,
            "desktop_auth_key": inst.desktop_auth_key,
            "state_dir": str(inst.state_dir),
            "created_at": inst.created_at.isoformat(),
            "last_activity": inst.last_activity.isoformat(),
        }

    def list_instances(self, user_id: Optional[str] = None) -> List[Dict]:
        out: List[Dict] = []
        for inst in self._iter_instances():
            if user_id and inst.user_id != user_id:
                continue
            out.append(self.get_instance_info(inst.user_id, inst.vm_id))
        out = [item for item in out if item is not None]
        out.sort(key=lambda x: (x["user_id"], x["vm_id"]))
        return out

    async def takeover_instance(
        self,
        user_id: str,
        vm_id: str = OPENCLAW_DEFAULT_VM_ID,
        *,
        require_auth: bool = True,
        view_only: bool = False,
    ) -> Dict:
        vm = normalize_vm_id(vm_id)
        if self.runtime_mode != "e2b":
            raise RuntimeError("Takeover requires OPENCLAW_RUNTIME=e2b and an active sandbox")
        instance = await self.get_or_create_instance(user_id, vm)

        if instance.runtime != "e2b" or not instance.sandbox_id:
            raise RuntimeError("Takeover requires OPENCLAW_RUNTIME=e2b and an active sandbox")

        takeover = self.e2b_runtime.start_or_reuse_takeover(
            sandbox_id=instance.sandbox_id,
            require_auth=require_auth,
            view_only=view_only,
        )
        instance.desktop_url = takeover.get("desktop_url", "")
        instance.desktop_auth_key = takeover.get("desktop_auth_key", "")
        instance.last_activity = datetime.now()

        self._set_instance(instance)
        self._persist_instance(instance)

        return {
            "user_id": instance.user_id,
            "vm_id": instance.vm_id,
            "runtime": instance.runtime,
            "sandbox_id": instance.sandbox_id,
            "desktop_url": instance.desktop_url,
            "desktop_auth_key": instance.desktop_auth_key,
            "view_only": view_only,
            "require_auth": require_auth,
        }

    def collect_runtime_metrics(self, user_id: str, vm_id: str = OPENCLAW_DEFAULT_VM_ID) -> List[Dict]:
        vm = normalize_vm_id(vm_id)
        instance = self._get_instance(user_id, vm)
        if not instance or instance.runtime != "e2b" or not instance.sandbox_id:
            return []
        try:
            return self.e2b_runtime.get_metrics(instance.sandbox_id)
        except Exception as exc:
            logger.warning("Failed to collect E2B metrics for %s/%s: %s", user_id, vm, exc)
            return []

    def run_shell(
        self,
        user_id: str,
        vm_id: str,
        command: str,
        timeout: int = 120,
    ) -> Dict:
        vm = normalize_vm_id(vm_id)
        instance = self._get_instance(user_id, vm)
        if not instance:
            raise RuntimeError(f"No instance for {user_id}/{vm}")

        if instance.runtime == "e2b":
            if not instance.sandbox_id:
                raise RuntimeError(f"No sandbox_id for {user_id}/{vm}")
            return self.e2b_runtime.run_shell(
                sandbox_id=instance.sandbox_id,
                command=command,
                timeout=timeout,
                user="root",
            )

        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(instance.state_dir / "workspace"),
            text=True,
            capture_output=True,
            timeout=timeout,
        )
        return {
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "exit_code": proc.returncode,
        }

    # ------------------------------------------------------------------
    # Idle cleanup
    # ------------------------------------------------------------------

    async def cleanup_idle_instances(self):
        cutoff = datetime.now() - timedelta(hours=IDLE_TIMEOUT_HOURS)
        for inst in self._iter_instances():
            if inst.last_activity < cutoff and inst.state == "running":
                logger.info("Pausing idle OpenClaw instance for %s/%s", inst.user_id, inst.vm_id)
                await self.stop_instance(inst.user_id, inst.vm_id)

    async def start_cleanup_loop(self, interval_seconds: int = 300):
        while True:
            try:
                await self.cleanup_idle_instances()
            except Exception as e:
                logger.error("Error in cleanup loop: %s", e)
            await asyncio.sleep(interval_seconds)

    def schedule_cleanup(self):
        self._cleanup_task = asyncio.ensure_future(self.start_cleanup_loop())
        return self._cleanup_task

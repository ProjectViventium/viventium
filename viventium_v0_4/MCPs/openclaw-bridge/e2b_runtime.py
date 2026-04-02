# VIVENTIUM START
# Purpose: E2B runtime adapter for per-(user, vm_id) OpenClaw sandboxes.
#
# Uses E2B SDK for lifecycle (create/connect/pause/kill/list) and e2b-desktop
# for interactive takeover URL support.
# VIVENTIUM END

from __future__ import annotations

import json
import logging
import os
import shlex
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _safe_bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class E2BRuntimeAdapter:
    """Runtime adapter for E2B-backed OpenClaw VMs."""

    def __init__(self, *, gateway_port: int, default_model: str):
        self.gateway_port = gateway_port
        self.default_model = default_model
        self.default_timeout = int(os.environ.get("OPENCLAW_E2B_TIMEOUT_SECONDS", "3600"))
        self.template = os.environ.get("OPENCLAW_E2B_TEMPLATE", "").strip() or None
        self.secure = _safe_bool_env("OPENCLAW_E2B_SECURE", True)
        self.allow_internet = _safe_bool_env("OPENCLAW_E2B_ALLOW_INTERNET", True)
        self.auto_pause = _safe_bool_env("OPENCLAW_E2B_AUTO_PAUSE", False)
        self._desktop_module_error: Optional[str] = None

        self._Sandbox = None
        self._SandboxQuery = None
        self._DesktopSandbox = None

        self._load_sdk_modules()

    def _load_sdk_modules(self) -> None:
        try:
            from e2b import Sandbox  # type: ignore
            self._Sandbox = Sandbox
        except Exception as exc:  # pragma: no cover - exercised when sdk missing
            logger.warning("E2B SDK unavailable: %s", exc)
            self._Sandbox = None

        # SandboxQuery moved across SDK versions; keep imports tolerant.
        sandbox_query = None
        try:
            from e2b import SandboxQuery  # type: ignore

            sandbox_query = SandboxQuery
        except Exception:
            try:
                from e2b.sandbox_sync.sandbox_api import SandboxQuery  # type: ignore

                sandbox_query = SandboxQuery
            except Exception:
                sandbox_query = None
        self._SandboxQuery = sandbox_query

        try:
            from e2b_desktop import Sandbox as DesktopSandbox  # type: ignore

            self._DesktopSandbox = DesktopSandbox
        except Exception as exc:  # pragma: no cover - exercised when sdk missing
            self._desktop_module_error = str(exc)
            self._DesktopSandbox = None

    @property
    def available(self) -> bool:
        return self._Sandbox is not None

    def _require_available(self) -> None:
        if self._Sandbox is None:
            raise RuntimeError(
                "E2B SDK is not installed. Install dependencies in requirements.txt first "
                "(e2b, e2b-desktop)."
            )
        if not os.environ.get("E2B_API_KEY", "").strip():
            raise RuntimeError("E2B_API_KEY is required for OPENCLAW_RUNTIME=e2b")

    @staticmethod
    def metadata_for(user_id: str, vm_id: str) -> Dict[str, str]:
        return {
            "viventium_user": user_id,
            "viventium_vm_id": vm_id,
            "runtime": "openclaw",
            "runtime_mode": "e2b",
        }

    def _to_gateway_url(self, sandbox: Any) -> str:
        host = sandbox.get_host(self.gateway_port)
        host = str(host).strip()
        if host.startswith("http://") or host.startswith("https://"):
            return host.rstrip("/")
        return f"https://{host}".rstrip("/")

    def _build_openclaw_config(self, *, gateway_token: str) -> Dict[str, Any]:
        return {
            "gateway": {
                "port": self.gateway_port,
                "mode": "local",
                "bind": "loopback",
                "auth": {
                    "mode": "token",
                    "token": gateway_token,
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
                        "primary": self.default_model,
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

    def _build_bootstrap_script(self, *, vm_id: str, gateway_token: str) -> str:
        state_root = f"/workspace/.viventium/openclaw/vm-{vm_id}"
        config_path = f"{state_root}/openclaw.json"
        marker_path = f"{state_root}/.bootstrap_complete"
        log_path = f"{state_root}/gateway.log"

        config_json = json.dumps(self._build_openclaw_config(gateway_token=gateway_token), indent=2)

        script = f"""
set -euo pipefail

STATE_ROOT={shlex.quote(state_root)}
CONFIG_PATH={shlex.quote(config_path)}
MARKER_PATH={shlex.quote(marker_path)}
LOG_PATH={shlex.quote(log_path)}
TOKEN={shlex.quote(gateway_token)}
PORT={self.gateway_port}

mkdir -p "$STATE_ROOT"

probe_gateway() {{
  local code
  code=$(curl -s -o /tmp/viv_probe.out -w "%{{http_code}}" \
    -X POST "http://127.0.0.1:$PORT/tools/invoke" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{{"tool":"__viventium_probe__","args":{{}}}}' || true)
  [[ "$code" == "200" || "$code" == "401" || "$code" == "404" ]]
}}

if probe_gateway; then
  touch "$MARKER_PATH"
  exit 0
fi

if ! command -v node >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -y
    apt-get install -y curl ca-certificates gnupg
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
    apt-get install -y nodejs
  else
    echo "Node.js missing and apt-get unavailable" >&2
    exit 1
  fi
fi

if ! command -v openclaw >/dev/null 2>&1; then
  npm install -g openclaw@latest
fi

cat > "$CONFIG_PATH" <<'JSON'
{config_json}
JSON

if pgrep -f "openclaw gateway.*--port $PORT" >/dev/null 2>&1; then
  pkill -f "openclaw gateway.*--port $PORT" || true
  sleep 1
fi

export OPENCLAW_STATE_DIR="$STATE_ROOT"
export OPENCLAW_CONFIG_PATH="$CONFIG_PATH"
export OPENCLAW_GATEWAY_TOKEN="$TOKEN"

nohup openclaw gateway --port "$PORT" --bind loopback --token "$TOKEN" --allow-unconfigured --force > "$LOG_PATH" 2>&1 &

for _ in $(seq 1 90); do
  if probe_gateway; then
    touch "$MARKER_PATH"
    exit 0
  fi
  sleep 1
done

echo "OpenClaw gateway failed to become ready" >&2
(tail -n 120 "$LOG_PATH" || true) >&2
exit 1
"""
        return script.strip() + "\n"

    def _ensure_desktop_object(self, sandbox: Any) -> None:
        if self._DesktopSandbox is None:
            return
        try:
            if not hasattr(sandbox, "_display"):
                setattr(sandbox, "_display", ":0")
            if not hasattr(sandbox, "_Sandbox__vnc_server"):
                from e2b_desktop.main import _VNCServer  # type: ignore

                setattr(sandbox, "_Sandbox__vnc_server", _VNCServer(sandbox))
        except Exception as exc:
            logger.debug("Desktop object bootstrap skipped: %s", exc)

    def _connect(self, sandbox_id: str, *, timeout: Optional[int] = None) -> Any:
        self._require_available()
        cls = self._DesktopSandbox or self._Sandbox
        if timeout is None:
            timeout = self.default_timeout
        return cls.connect(sandbox_id, timeout=timeout)

    def _create(self, *, metadata: Dict[str, str], timeout: Optional[int] = None) -> Any:
        self._require_available()
        cls = self._DesktopSandbox or self._Sandbox
        if timeout is None:
            timeout = self.default_timeout

        kwargs: Dict[str, Any] = {
            "timeout": timeout,
            "metadata": metadata,
            "secure": self.secure,
            "allow_internet_access": self.allow_internet,
        }
        if self.template:
            kwargs["template"] = self.template

        # Prefer beta_create when available so pause/resume lifecycle is explicit.
        if hasattr(cls, "beta_create"):
            kwargs["auto_pause"] = self.auto_pause
            return cls.beta_create(**kwargs)
        return cls.create(**kwargs)

    def ensure_vm_running(self, *, user_id: str, vm_id: str, sandbox_id: Optional[str], gateway_token: str) -> Dict[str, Any]:
        self._require_available()

        metadata = self.metadata_for(user_id=user_id, vm_id=vm_id)
        sandbox = None
        current_sandbox_id = sandbox_id

        if sandbox_id:
            try:
                sandbox = self._connect(sandbox_id)
            except Exception as exc:
                logger.warning("Failed to connect sandbox %s for %s/%s: %s", sandbox_id, user_id, vm_id, exc)
                sandbox = None

        if sandbox is None:
            sandbox = self._create(metadata=metadata)
            current_sandbox_id = getattr(sandbox, "sandbox_id", None) or getattr(sandbox, "id", None)

        self._ensure_desktop_object(sandbox)

        script = self._build_bootstrap_script(vm_id=vm_id, gateway_token=gateway_token)
        sandbox.commands.run(script, timeout=900, user="root")

        return {
            "sandbox_id": current_sandbox_id,
            "state": "running",
            "gateway_url": self._to_gateway_url(sandbox),
            "sandbox": sandbox,
        }

    def pause_vm(self, sandbox_id: str) -> None:
        self._require_available()
        cls = self._Sandbox
        if hasattr(cls, "beta_pause"):
            cls.beta_pause(sandbox_id)
            return
        if hasattr(cls, "pause"):
            cls.pause(sandbox_id)
            return
        sandbox = self._connect(sandbox_id)
        if hasattr(sandbox, "pause"):
            sandbox.pause()
            return
        raise RuntimeError("Pause is not supported by installed E2B SDK")

    def terminate_vm(self, sandbox_id: str) -> None:
        self._require_available()
        cls = self._Sandbox
        if hasattr(cls, "kill"):
            cls.kill(sandbox_id)
            return
        sandbox = self._connect(sandbox_id)
        if hasattr(sandbox, "kill"):
            sandbox.kill()
            return
        raise RuntimeError("Kill is not supported by installed E2B SDK")

    def get_state(self, sandbox_id: str) -> str:
        self._require_available()
        info = self._Sandbox.get_info(sandbox_id)
        state = getattr(info, "state", None)
        return str(state) if state is not None else "unknown"

    def list_vm_sandboxes(self, *, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        self._require_available()
        metadata_filter = {"runtime": "openclaw", "runtime_mode": "e2b"}
        if user_id:
            metadata_filter["viventium_user"] = user_id

        if self._SandboxQuery is not None:
            query = self._SandboxQuery()
            query.metadata = metadata_filter
            sandboxes = self._Sandbox.list(query=query)
        else:
            sandboxes = self._Sandbox.list()

        out: List[Dict[str, Any]] = []
        for sandbox in sandboxes:
            metadata = getattr(sandbox, "metadata", {}) or {}
            if not all(str(metadata.get(k)) == str(v) for k, v in metadata_filter.items()):
                continue
            out.append(
                {
                    "sandbox_id": getattr(sandbox, "sandbox_id", None),
                    "state": str(getattr(sandbox, "state", "unknown")),
                    "metadata": metadata,
                }
            )
        return out

    def start_or_reuse_takeover(self, *, sandbox_id: str, require_auth: bool, view_only: bool) -> Dict[str, str]:
        if self._DesktopSandbox is None:
            message = self._desktop_module_error or "e2b-desktop is unavailable"
            raise RuntimeError(f"Interactive takeover unavailable: {message}")

        sandbox = self._connect(sandbox_id)
        self._ensure_desktop_object(sandbox)

        stream = sandbox.stream
        try:
            stream.start(require_auth=require_auth)
        except RuntimeError as exc:
            # noVNC already running is acceptable for takeover reuse
            if "already running" not in str(exc).lower():
                raise

        auth_key = ""
        url_kwargs: Dict[str, Any] = {
            "auto_connect": True,
            "view_only": view_only,
            "resize": "scale",
        }
        if require_auth:
            auth_key = stream.get_auth_key()
            url_kwargs["auth_key"] = auth_key

        url = stream.get_url(**url_kwargs)
        return {
            "desktop_url": url,
            "desktop_auth_key": auth_key,
        }

    def get_metrics(self, sandbox_id: str) -> List[Dict[str, Any]]:
        self._require_available()
        sandbox = self._connect(sandbox_id)
        metrics = sandbox.get_metrics()
        out: List[Dict[str, Any]] = []
        for item in metrics:
            out.append(
                {
                    "cpu_count": getattr(item, "cpu_count", None),
                    "cpu_used_pct": getattr(item, "cpu_used_pct", None),
                    "disk_total": getattr(item, "disk_total", None),
                    "disk_used": getattr(item, "disk_used", None),
                    "mem_total": getattr(item, "mem_total", None),
                    "mem_used": getattr(item, "mem_used", None),
                    "timestamp": getattr(item, "timestamp", None),
                }
            )
        return out

    def run_shell(self, *, sandbox_id: str, command: str, timeout: int = 120, user: str = "root") -> Dict[str, Any]:
        self._require_available()
        sandbox = self._connect(sandbox_id)
        result = sandbox.commands.run(command, timeout=timeout, user=user)
        return {
            "stdout": getattr(result, "stdout", ""),
            "stderr": getattr(result, "stderr", ""),
            "exit_code": getattr(result, "exit_code", None),
        }

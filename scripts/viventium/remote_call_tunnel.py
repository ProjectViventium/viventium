#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import fcntl
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import ssl
import uuid
from pathlib import Path
from typing import Any


TRYCLOUDFLARE_URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com", re.IGNORECASE)
DEFAULT_HEALTH_TIMEOUT_SECONDS = 4.0
DEFAULT_REMOTE_CALL_TUNNEL_TIMEOUT_SECONDS = 150
DEFAULT_TAILSCALE_PUBLIC_PORTS = {
    "client": 443,
    "api": 8443,
    "playground": 3443,
    "livekit": 7443,
}
DEFAULT_PUBLIC_EDGE_HOST_PREFIXES = {
    "client": "app",
    "api": "api",
    "playground": "playground",
    "livekit": "livekit",
}
DEFAULT_PUBLIC_EDGE_HTTP_EXTERNAL_PORT = 80
DEFAULT_PUBLIC_EDGE_HTTPS_EXTERNAL_PORT = 443
DEFAULT_PUBLIC_EDGE_TURN_TLS_EXTERNAL_PORT = 5349
DEFAULT_PUBLIC_EDGE_UPNP_LEASE_SECONDS = 14400
DIRECTORY_INSTANCE_PATH = "/.well-known/viventium-instance.json"
DIRECTORY_REGISTRATION_ALGORITHM = "rsa-sha256"
UPNPC_EXTERNAL_IP_RE = re.compile(r"ExternalIPAddress\s*=\s*([0-9.]+)")
UPNPC_LOCAL_IP_RE = re.compile(r"Local LAN ip address\s*:\s*([0-9.]+)")
UPNPC_MAPPING_RE = re.compile(r"^\s*\d+\s+([A-Z]+)\s+(\d+)->([0-9.]+):(\d+)\b")
SURFACE_KEYS = ("client", "api", "playground", "livekit")
COMMON_BINARY_PATHS: dict[str, tuple[str, ...]] = {
    "brew": (
        "/opt/homebrew/bin/brew",
        "/usr/local/bin/brew",
    ),
    "caddy": (
        "/opt/homebrew/bin/caddy",
        "/usr/local/bin/caddy",
    ),
    "cloudflared": (
        "/opt/homebrew/bin/cloudflared",
        "/usr/local/bin/cloudflared",
    ),
    "tailscale": (
        "/opt/homebrew/bin/tailscale",
        "/usr/local/bin/tailscale",
    ),
    "upnpc": (
        "/opt/homebrew/bin/upnpc",
        "/usr/local/bin/upnpc",
    ),
    "openssl": (
        "/opt/homebrew/opt/openssl@3/bin/openssl",
        "/usr/local/opt/openssl@3/bin/openssl",
        "/usr/bin/openssl",
    ),
}


def parse_timeout_seconds(raw: str | None, default: int = DEFAULT_REMOTE_CALL_TUNNEL_TIMEOUT_SECONDS) -> int:
    try:
        value = int(str(raw or "").strip())
    except Exception:
        return default
    return value if value > 0 else default


def resolve_binary(name: str) -> str | None:
    resolved = shutil.which(name)
    if resolved:
        return resolved

    for candidate in COMMON_BINARY_PATHS.get(name, ()):
        if Path(candidate).exists():
            return candidate

    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Manage secure remote access surfaces for local Viventium installs."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start", help="Start or reuse secure remote access surfaces")
    start.add_argument("--state-file", required=True)
    start.add_argument("--log-dir", required=True)
    start.add_argument("--provider", default="cloudflare_quick_tunnel")
    start.add_argument("--auto-install", action="store_true")
    start.add_argument("--client-port", type=int, default=0)
    start.add_argument("--api-port", type=int, default=0)
    start.add_argument("--playground-port", type=int, default=0)
    start.add_argument("--livekit-port", type=int, default=0)
    start.add_argument("--livekit-tcp-port", type=int, default=0)
    start.add_argument("--livekit-udp-port", type=int, default=0)
    start.add_argument("--livekit-turn-tls-port", type=int, default=DEFAULT_PUBLIC_EDGE_TURN_TLS_EXTERNAL_PORT)
    start.add_argument("--public-client-origin", default="")
    start.add_argument("--public-api-origin", default="")
    start.add_argument("--public-playground-origin", default="")
    start.add_argument("--public-livekit-url", default="")
    start.add_argument("--livekit-node-ip", default="")
    start.add_argument("--caddy-data-dir", default="")
    start.add_argument("--upnp-lease-seconds", type=int, default=DEFAULT_PUBLIC_EDGE_UPNP_LEASE_SECONDS)
    start.add_argument(
        "--timeout-seconds",
        type=int,
        default=parse_timeout_seconds(os.environ.get("VIVENTIUM_REMOTE_CALL_TUNNEL_TIMEOUT_SECONDS")),
    )

    stop = subparsers.add_parser("stop", help="Stop secure remote access surfaces")
    stop.add_argument("--state-file", required=True)

    status = subparsers.add_parser("status", help="Print current secure remote access state")
    status.add_argument("--state-file", required=True)

    refresh = subparsers.add_parser("refresh-mappings", help="Refresh public HTTPS edge router mappings")
    refresh.add_argument("--state-file", required=True)
    refresh.add_argument("--upnp-lease-seconds", type=int, default=DEFAULT_PUBLIC_EDGE_UPNP_LEASE_SECONDS)

    return parser.parse_args()


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        return {}
    return {}


def save_state(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_checked(
    command: list[str],
    *,
    env: dict[str, str] | None = None,
    stdin: int | None = None,
    timeout_seconds: float | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        env=env,
        stdin=stdin,
        timeout=timeout_seconds,
    )


def ensure_cloudflared(auto_install: bool) -> str:
    return ensure_binary("cloudflared", auto_install=auto_install, brew_formula="cloudflared")


def ensure_tailscale(auto_install: bool) -> str:
    return ensure_binary("tailscale", auto_install=auto_install, brew_formula="tailscale")


def ensure_caddy(auto_install: bool) -> str:
    return ensure_binary("caddy", auto_install=auto_install, brew_formula="caddy")


def ensure_upnpc(auto_install: bool) -> str:
    return ensure_binary("upnpc", auto_install=auto_install, brew_formula="miniupnpc")


def ensure_openssl() -> str:
    resolved = resolve_binary("openssl")
    if resolved:
        return resolved
    raise RuntimeError("openssl is required to manage Viventium directory verification keys")


def ensure_binary(name: str, *, auto_install: bool, brew_formula: str) -> str:
    resolved = resolve_binary(name)
    if resolved:
        return resolved
    if not auto_install:
        raise RuntimeError(f"{name} is not installed")
    brew = resolve_binary("brew")
    if not brew:
        raise RuntimeError(f"{name} is not installed and Homebrew is unavailable")
    subprocess.run([brew, "list", brew_formula], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run([brew, "install", brew_formula], check=True)
    resolved = resolve_binary(name)
    if not resolved:
        raise RuntimeError(f"{name} installation completed but binary is still unavailable")
    return resolved


def pid_is_running(pid: int | None) -> bool:
    if not pid or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def stop_pid(pid: int | None) -> None:
    if not pid_is_running(pid):
        return
    try:
        os.killpg(pid, signal.SIGTERM)
    except OSError:
        return
    deadline = time.time() + 10
    while time.time() < deadline:
        if not pid_is_running(pid):
            return
        time.sleep(0.25)
    try:
        os.killpg(pid, signal.SIGKILL)
    except OSError:
        return


def start_quick_tunnel(
    cloudflared_bin: str,
    *,
    target_url: str,
    log_file: Path,
    timeout_seconds: int,
) -> tuple[int, str]:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("w", encoding="utf-8") as handle:
        process = subprocess.Popen(
            [
                cloudflared_bin,
                "tunnel",
                "--url",
                target_url,
                "--no-autoupdate",
            ],
            stdout=handle,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            text=True,
        )

    deadline = time.time() + timeout_seconds
    url = ""
    while time.time() < deadline:
        if process.poll() is not None:
            log_excerpt = log_file.read_text(encoding="utf-8", errors="ignore")
            raise RuntimeError(
                f"cloudflared tunnel for {target_url} exited early with code {process.returncode}\n{log_excerpt}"
            )
        content = log_file.read_text(encoding="utf-8", errors="ignore")
        match = TRYCLOUDFLARE_URL_RE.search(content)
        if match:
            url = match.group(0)
            break
        time.sleep(0.5)

    if not url:
        stop_pid(process.pid)
        raise RuntimeError(f"Timed out waiting for quick tunnel URL for {target_url}")

    return process.pid, url.rstrip("/")


def normalize_probe_url(value: str | None) -> str:
    if not value:
        return ""
    normalized = str(value).strip()
    if normalized.startswith("wss://"):
        return "https://" + normalized[len("wss://") :]
    if normalized.startswith("ws://"):
        return "http://" + normalized[len("ws://") :]
    return normalized


def probe_http_endpoint(url: str | None, timeout_seconds: float = DEFAULT_HEALTH_TIMEOUT_SECONDS) -> bool:
    probe_url = normalize_probe_url(url)
    if not probe_url:
        return False

    parsed = urllib.parse.urlparse(probe_url)
    if parsed.scheme not in {"http", "https"}:
        return False

    ssl_context = ssl.create_default_context() if parsed.scheme == "https" else None
    for method in ("HEAD", "GET"):
        try:
            request = urllib.request.Request(probe_url, method=method)
            with urllib.request.urlopen(request, timeout=timeout_seconds, context=ssl_context) as response:
                status = int(getattr(response, "status", response.getcode()))
                if 200 <= status < 500:
                    return True
        except urllib.error.HTTPError as error:
            if 200 <= int(error.code) < 500:
                return True
        except Exception:
            continue

    return False


def probe_local_endpoint(url: str | None, timeout_seconds: float = DEFAULT_HEALTH_TIMEOUT_SECONDS) -> bool:
    probe_url = normalize_probe_url(url)
    if not probe_url:
        return False

    parsed = urllib.parse.urlparse(probe_url)
    host = parsed.hostname or ""
    port = parsed.port
    if not host:
        return False
    if port is None:
        if parsed.scheme in {"https", "wss"}:
            port = 443
        elif parsed.scheme in {"http", "ws"}:
            port = 80
        else:
            return False

    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            return True
    except Exception:
        return False


def parse_url(value: str | None) -> urllib.parse.ParseResult | None:
    normalized = str(value or "").strip()
    if not normalized:
        return None
    try:
        return urllib.parse.urlparse(normalized)
    except Exception:
        return None


def strip_trailing_dot(value: str | None) -> str:
    return str(value or "").strip().rstrip(".")


def format_https_origin(host: str, port: int) -> str:
    return f"https://{host}" if port == 443 else f"https://{host}:{port}"


def format_wss_origin(host: str, port: int) -> str:
    return f"wss://{host}" if port == 443 else f"wss://{host}:{port}"


def surface_target_url(port: int) -> str:
    return f"http://localhost:{port}"


def iter_surfaces(state: dict[str, Any]):
    for key in SURFACE_KEYS:
        surface = state.get(key)
        if isinstance(surface, dict):
            yield key, surface


def state_is_healthy(state: dict[str, Any]) -> bool:
    provider = str(state.get("provider") or "").strip()
    surfaces = list(iter_surfaces(state))
    if not provider or not surfaces:
        return False
    if not all(probe_local_endpoint(surface.get("target")) for _, surface in surfaces):
        return False

    if provider == "cloudflare_quick_tunnel":
        return all(pid_is_running(surface.get("pid")) for _, surface in surfaces)

    if provider == "tailscale_tailnet_https":
        return tailscale_state_ready(state)

    if provider == "netbird_selfhosted_mesh":
        caddy = state.get("caddy") or {}
        return pid_is_running(caddy.get("pid"))

    if provider == "public_https_edge":
        caddy = state.get("caddy") or {}
        return pid_is_running(caddy.get("pid"))

    return False


def with_lock(lock_path: Path):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+", encoding="utf-8")
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
    return handle


def build_surface(
    *,
    target_url: str,
    public_url: str,
    pid: int | None = None,
    public_ws_url: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "target": target_url,
        "public_url": public_url,
    }
    if pid:
        payload["pid"] = pid
    if public_ws_url:
        payload["public_ws_url"] = public_ws_url
    return payload


def build_state(provider: str, surfaces: dict[str, dict[str, Any]], *, livekit_node_ip: str = "", extras: dict[str, Any] | None = None) -> dict[str, Any]:
    state: dict[str, Any] = {
        "provider": provider,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if livekit_node_ip:
        state["livekit_node_ip"] = livekit_node_ip

    for key, surface in surfaces.items():
        state[key] = surface
        public_url = str(surface.get("public_url") or "").strip()
        if key == "client" and public_url:
            state["public_client_url"] = public_url
        elif key == "api" and public_url:
            state["public_api_url"] = public_url
        elif key == "playground" and public_url:
            state["public_playground_url"] = public_url
        elif key == "livekit":
            public_ws_url = str(surface.get("public_ws_url") or "").strip()
            if public_ws_url:
                state["public_livekit_url"] = public_ws_url
            elif public_url:
                state["public_livekit_url"] = re.sub(r"^https://", "wss://", public_url)

    if extras:
        state.update(extras)
    return state


def ensure_directory_identity(state_path: Path) -> dict[str, str]:
    openssl_bin = ensure_openssl()
    identity_dir = state_path.parent / "directory-identity"
    identity_dir.mkdir(parents=True, exist_ok=True)

    private_key_path = identity_dir / "private.pem"
    public_key_path = identity_dir / "public.pem"
    metadata_path = identity_dir / "identity.json"

    if not private_key_path.exists():
        result = run_checked(
            [
                openssl_bin,
                "genpkey",
                "-algorithm",
                "RSA",
                "-pkeyopt",
                "rsa_keygen_bits:2048",
                "-out",
                str(private_key_path),
            ],
            timeout_seconds=20,
        )
        if result.returncode != 0:
            stderr = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(f"Failed to generate the Viventium directory private key: {stderr}".strip())

    if not public_key_path.exists():
        result = run_checked(
            [
                openssl_bin,
                "pkey",
                "-in",
                str(private_key_path),
                "-pubout",
                "-out",
                str(public_key_path),
            ],
            timeout_seconds=15,
        )
        if result.returncode != 0:
            stderr = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(f"Failed to derive the Viventium directory public key: {stderr}".strip())

    metadata: dict[str, Any] = {}
    if metadata_path.exists():
        try:
            raw = json.loads(metadata_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                metadata = raw
        except Exception:
            metadata = {}

    public_key_pem = public_key_path.read_text(encoding="utf-8").strip()
    instance_id = str(metadata.get("instance_id") or "").strip() or str(uuid.uuid4())
    fingerprint = "sha256:" + hashlib.sha256(public_key_pem.encode("utf-8")).hexdigest()
    normalized_metadata = {
        "instance_id": instance_id,
        "public_key_fingerprint": fingerprint,
        "public_key_pem": public_key_pem,
        "registration_algorithm": DIRECTORY_REGISTRATION_ALGORITHM,
    }
    metadata_path.write_text(
        json.dumps(normalized_metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return normalized_metadata


def render_directory_instance_document(
    *,
    client_origin: str,
    provider: str,
    identity: dict[str, str],
    public_playground_url: str = "",
) -> str:
    payload: dict[str, Any] = {
        "app": "Viventium",
        "schemaVersion": 1,
        "provider": provider,
        "publicClientOrigin": client_origin,
        "directory": {
            "instanceId": str(identity.get("instance_id") or "").strip(),
            "publicKeyFingerprint": str(identity.get("public_key_fingerprint") or "").strip(),
            "publicKeyPem": str(identity.get("public_key_pem") or "").strip(),
            "registrationAlgorithm": str(identity.get("registration_algorithm") or DIRECTORY_REGISTRATION_ALGORITHM),
        },
    }
    if public_playground_url:
        payload["publicPlaygroundUrl"] = public_playground_url
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def require_port(value: int, label: str) -> int:
    if value <= 0:
        raise RuntimeError(f"{label} is required")
    return value


def require_https_url(value: str, label: str) -> urllib.parse.ParseResult:
    parsed = parse_url(value)
    if not parsed or parsed.scheme != "https" or not parsed.hostname:
        raise RuntimeError(f"{label} must be an https:// URL")
    if parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment:
        raise RuntimeError(f"{label} must not include a path, query, or fragment")
    return parsed


def require_livekit_public_url(value: str) -> urllib.parse.ParseResult:
    parsed = parse_url(value)
    if not parsed or parsed.scheme not in {"https", "wss"} or not parsed.hostname:
        raise RuntimeError("public_livekit_url must be a wss:// or https:// URL")
    if parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment:
        raise RuntimeError("public_livekit_url must not include a path, query, or fragment")
    return parsed


def require_public_https_edge_origin(value: str, label: str) -> urllib.parse.ParseResult:
    parsed = require_https_url(value, label)
    port = parsed.port or 443
    if port != 443:
        raise RuntimeError(f"{label} must use the default HTTPS port 443")
    return parsed


def require_public_https_edge_livekit_url(value: str) -> urllib.parse.ParseResult:
    parsed = require_livekit_public_url(value)
    port = parsed.port or 443
    if port != 443:
        raise RuntimeError("public_livekit_url must use the default WSS port 443")
    return parsed


def resolve_tailscale_public_url(
    explicit_value: str,
    *,
    dns_name: str,
    default_port: int,
    livekit: bool = False,
) -> tuple[str, int]:
    if explicit_value:
        parsed = require_livekit_public_url(explicit_value) if livekit else require_https_url(explicit_value, "public origin")
        hostname = strip_trailing_dot(parsed.hostname)
        if hostname != dns_name:
            raise RuntimeError(
                f"Tailscale-managed public origin host must match this node's tailnet DNS name ({dns_name})"
            )
        port = parsed.port or 443
        if livekit:
            return format_wss_origin(dns_name, port), port
        return format_https_origin(dns_name, port), port

    if livekit:
        return format_wss_origin(dns_name, default_port), default_port
    return format_https_origin(dns_name, default_port), default_port


def tailscale_status_json(tailscale_bin: str) -> dict[str, Any]:
    result = run_checked([tailscale_bin, "status", "--json"])
    if result.returncode != 0:
        stderr = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(
            f"Tailscale is not ready on this Mac. Sign in to Tailscale first. {stderr}".strip()
        )
    try:
        data = json.loads(result.stdout or "{}")
    except Exception as exc:
        raise RuntimeError(f"Unable to parse tailscale status JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError("Unable to read tailscale status JSON")
    return data


def tailscale_dns_name(status: dict[str, Any]) -> str:
    dns_name = strip_trailing_dot(((status.get("Self") or {}).get("DNSName")))
    if not dns_name:
        raise RuntimeError("Tailscale is running, but this node does not have a DNS name yet")
    return dns_name


def tailscale_ipv4(tailscale_bin: str, status: dict[str, Any]) -> str:
    ips = ((status.get("Self") or {}).get("TailscaleIPs")) or []
    for value in ips:
        candidate = str(value or "").strip()
        if candidate and ":" not in candidate:
            return candidate
    result = run_checked([tailscale_bin, "ip", "-4"])
    if result.returncode != 0:
        stderr = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"Unable to determine Tailscale IPv4 address: {stderr}".strip())
    for line in (result.stdout or "").splitlines():
        candidate = str(line).strip()
        if candidate:
            return candidate
    raise RuntimeError("Unable to determine Tailscale IPv4 address")


def configure_tailscale_https_proxy(tailscale_bin: str, *, public_port: int, target_url: str) -> None:
    result = run_checked(
        [tailscale_bin, "serve", "--yes", "--bg", f"--https={public_port}", target_url]
    )
    if result.returncode != 0:
        stderr = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"tailscale serve failed for port {public_port}: {stderr}".strip())


def remove_tailscale_https_proxy(tailscale_bin: str, *, public_port: int) -> None:
    result = run_checked([tailscale_bin, "serve", "--yes", f"--https={public_port}", "off"])
    if result.returncode != 0 and "not found" not in (result.stderr or result.stdout or "").lower():
        stderr = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"tailscale serve cleanup failed for port {public_port}: {stderr}".strip())


def tailscale_state_ready(state: dict[str, Any]) -> bool:
    tailscale_bin = resolve_binary("tailscale")
    if not tailscale_bin:
        return False
    try:
        status = tailscale_status_json(tailscale_bin)
        dns_name = tailscale_dns_name(status)
    except Exception:
        return False

    tailscale_meta = state.get("tailscale") or {}
    if strip_trailing_dot(tailscale_meta.get("dns_name")) != dns_name:
        return False

    for key, _surface in iter_surfaces(state):
        if key not in DEFAULT_TAILSCALE_PUBLIC_PORTS:
            continue
        public_url = str(state.get(f"public_{'api' if key == 'api' else key}_url", "") or "").strip()
        if key == "livekit":
            public_url = str(state.get("public_livekit_url", "") or "").strip()
        if not public_url:
            return False
    return True


def derive_local_ip_from_hostname(hostname: str | None) -> str:
    candidate = str(hostname or "").strip()
    if not candidate:
        return ""
    try:
        return socket.gethostbyname(candidate)
    except Exception:
        return ""


def detect_lan_ipv4() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            candidate = str(sock.getsockname()[0] or "").strip()
            if candidate and not candidate.startswith("127."):
                return candidate
    except Exception:
        pass
    return derive_local_ip_from_hostname(socket.gethostname())


def parse_upnpc_listing(output: str) -> dict[str, Any]:
    external_ip = ""
    local_ip = ""
    mappings: dict[tuple[str, int], tuple[str, int]] = {}
    for raw_line in str(output or "").splitlines():
        line = raw_line.rstrip()
        external_match = UPNPC_EXTERNAL_IP_RE.search(line)
        if external_match:
            external_ip = external_match.group(1)
            continue
        local_match = UPNPC_LOCAL_IP_RE.search(line)
        if local_match:
            local_ip = local_match.group(1)
            continue
        mapping_match = UPNPC_MAPPING_RE.match(line)
        if mapping_match:
            protocol = mapping_match.group(1).upper()
            external_port = int(mapping_match.group(2))
            internal_host = mapping_match.group(3)
            internal_port = int(mapping_match.group(4))
            mappings[(protocol, external_port)] = (internal_host, internal_port)
    return {
        "external_ip": external_ip,
        "local_ip": local_ip,
        "mappings": mappings,
    }


def list_upnpc_state(upnpc_bin: str) -> dict[str, Any]:
    result = run_checked([upnpc_bin, "-l"], timeout_seconds=8)
    if result.returncode != 0:
        stderr = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"Unable to inspect router port mappings: {stderr}".strip())
    return parse_upnpc_listing(result.stdout or "")


def discover_public_ipv4(upnpc_bin: str | None = None) -> str:
    if upnpc_bin:
        try:
            state = list_upnpc_state(upnpc_bin)
            candidate = str(state.get("external_ip") or "").strip()
            if candidate:
                return candidate
        except Exception:
            pass

    for endpoint in ("https://api.ipify.org", "https://checkip.amazonaws.com"):
        try:
            with urllib.request.urlopen(endpoint, timeout=6) as response:
                candidate = str(response.read().decode("utf-8", errors="ignore")).strip()
                if candidate and re.fullmatch(r"[0-9.]+", candidate):
                    return candidate
        except Exception:
            continue

    raise RuntimeError("Unable to determine the public IPv4 address for this install")


def build_default_public_edge_hostname(key: str, public_ip: str) -> str:
    prefix = DEFAULT_PUBLIC_EDGE_HOST_PREFIXES[key]
    return f"{prefix}.{public_ip}.sslip.io"


def resolve_public_https_edge_surface(
    key: str,
    explicit_value: str,
    *,
    public_ip: str,
) -> tuple[str, str]:
    if key == "livekit":
        if explicit_value:
            parsed = require_public_https_edge_livekit_url(explicit_value)
            hostname = strip_trailing_dot(parsed.hostname)
            return format_https_origin(hostname, 443), format_wss_origin(hostname, 443)
        hostname = build_default_public_edge_hostname(key, public_ip)
        return format_https_origin(hostname, 443), format_wss_origin(hostname, 443)

    if explicit_value:
        parsed = require_public_https_edge_origin(explicit_value, f"public_{key}_origin")
        hostname = strip_trailing_dot(parsed.hostname)
        return hostname, format_https_origin(hostname, 443)

    hostname = build_default_public_edge_hostname(key, public_ip)
    return hostname, format_https_origin(hostname, 443)


def resolve_public_edge_livekit_cert_pair(data_dir: Path, hostname: str) -> tuple[str, str] | None:
    normalized_host = strip_trailing_dot(hostname)
    if not normalized_host:
        return None

    certificate_dir = (
        data_dir
        / "caddy"
        / "certificates"
        / "acme-v02.api.letsencrypt.org-directory"
        / normalized_host
    )
    cert_file = certificate_dir / f"{normalized_host}.crt"
    key_file = certificate_dir / f"{normalized_host}.key"
    if cert_file.is_file() and key_file.is_file():
        return str(cert_file), str(key_file)
    return None


def pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        return int(sock.getsockname()[1])


def start_cloudflare(args: argparse.Namespace, *, log_dir: Path) -> dict[str, Any]:
    playground_port = require_port(args.playground_port, "playground_port")
    livekit_port = require_port(args.livekit_port, "livekit_port")
    cloudflared_bin = ensure_cloudflared(args.auto_install)

    playground_pid, playground_url = start_quick_tunnel(
        cloudflared_bin,
        target_url=surface_target_url(playground_port),
        log_file=log_dir / "remote-call-playground-tunnel.log",
        timeout_seconds=args.timeout_seconds,
    )
    try:
        livekit_pid, livekit_url = start_quick_tunnel(
            cloudflared_bin,
            target_url=surface_target_url(livekit_port),
            log_file=log_dir / "remote-call-livekit-tunnel.log",
            timeout_seconds=args.timeout_seconds,
        )
    except Exception:
        stop_pid(playground_pid)
        raise

    surfaces = {
        "playground": build_surface(
            pid=playground_pid,
            target_url=surface_target_url(playground_port),
            public_url=playground_url,
        ),
        "livekit": build_surface(
            pid=livekit_pid,
            target_url=surface_target_url(livekit_port),
            public_url=livekit_url,
            public_ws_url=re.sub(r"^https://", "wss://", livekit_url),
        ),
    }
    return build_state("cloudflare_quick_tunnel", surfaces)


def start_tailscale(args: argparse.Namespace) -> dict[str, Any]:
    if args.client_port <= 0 and args.api_port <= 0 and args.playground_port <= 0 and args.livekit_port <= 0:
        raise RuntimeError("At least one local surface port is required for tailscale remote access")

    tailscale_bin = ensure_tailscale(args.auto_install)
    status = tailscale_status_json(tailscale_bin)
    dns_name = tailscale_dns_name(status)
    node_ip = tailscale_ipv4(tailscale_bin, status)

    surfaces: dict[str, dict[str, Any]] = {}
    managed_ports: list[int] = []

    if args.client_port > 0:
        public_url, public_port = resolve_tailscale_public_url(
            args.public_client_origin,
            dns_name=dns_name,
            default_port=DEFAULT_TAILSCALE_PUBLIC_PORTS["client"],
        )
        configure_tailscale_https_proxy(
            tailscale_bin,
            public_port=public_port,
            target_url=surface_target_url(args.client_port),
        )
        managed_ports.append(public_port)
        surfaces["client"] = build_surface(
            target_url=surface_target_url(args.client_port),
            public_url=public_url,
        )

    if args.api_port > 0:
        public_url, public_port = resolve_tailscale_public_url(
            args.public_api_origin,
            dns_name=dns_name,
            default_port=DEFAULT_TAILSCALE_PUBLIC_PORTS["api"],
        )
        configure_tailscale_https_proxy(
            tailscale_bin,
            public_port=public_port,
            target_url=surface_target_url(args.api_port),
        )
        managed_ports.append(public_port)
        surfaces["api"] = build_surface(
            target_url=surface_target_url(args.api_port),
            public_url=public_url,
        )

    if args.playground_port > 0:
        public_url, public_port = resolve_tailscale_public_url(
            args.public_playground_origin,
            dns_name=dns_name,
            default_port=DEFAULT_TAILSCALE_PUBLIC_PORTS["playground"],
        )
        configure_tailscale_https_proxy(
            tailscale_bin,
            public_port=public_port,
            target_url=surface_target_url(args.playground_port),
        )
        managed_ports.append(public_port)
        surfaces["playground"] = build_surface(
            target_url=surface_target_url(args.playground_port),
            public_url=public_url,
        )

    if args.livekit_port > 0:
        public_url, public_port = resolve_tailscale_public_url(
            args.public_livekit_url,
            dns_name=dns_name,
            default_port=DEFAULT_TAILSCALE_PUBLIC_PORTS["livekit"],
            livekit=True,
        )
        configure_tailscale_https_proxy(
            tailscale_bin,
            public_port=public_port,
            target_url=surface_target_url(args.livekit_port),
        )
        managed_ports.append(public_port)
        surfaces["livekit"] = build_surface(
            target_url=surface_target_url(args.livekit_port),
            public_url=re.sub(r"^wss://", "https://", public_url),
            public_ws_url=public_url,
        )

    return build_state(
        "tailscale_tailnet_https",
        surfaces,
        livekit_node_ip=node_ip,
        extras={
            "tailscale": {
                "dns_name": dns_name,
                "managed_ports": managed_ports,
            },
        },
    )


def caddy_site_address(parsed: urllib.parse.ParseResult) -> str:
    port = parsed.port or 443
    return f"{parsed.hostname}:{port}"


def pick_caddy_admin_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        return int(sock.getsockname()[1])


def render_caddyfile(
    *,
    admin_port: int,
    surfaces: list[tuple[str, int]],
    tls_internal: bool = True,
    http_port: int | None = None,
    https_port: int | None = None,
    well_known_bodies: dict[str, str] | None = None,
) -> str:
    lines = [
        "{",
        f"    admin 127.0.0.1:{admin_port}",
    ]
    if http_port:
        lines.append(f"    http_port {http_port}")
    if https_port:
        lines.append(f"    https_port {https_port}")
    lines.extend(
        [
            "}",
            "",
        ]
    )
    for site_address, upstream_port in surfaces:
        lines.append(f"{site_address} {{")
        if tls_internal:
            lines.append("    tls internal")
        body = (well_known_bodies or {}).get(site_address)
        if body:
            lines.extend(
                [
                    f"    handle {DIRECTORY_INSTANCE_PATH} {{",
                    "        header Content-Type application/json",
                    "        header Cache-Control \"public, max-age=60\"",
                    f"        respond {json.dumps(body)} 200",
                    "    }",
                ]
            )
        lines.extend(
            [
                f"    reverse_proxy 127.0.0.1:{upstream_port}",
                "}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def start_caddy_process(
    caddy_bin: str,
    *,
    config_path: Path,
    data_dir: Path,
    log_file: Path,
) -> int:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["XDG_DATA_HOME"] = str(data_dir)
    env["HOME"] = str(data_dir)
    with log_file.open("w", encoding="utf-8") as handle:
        process = subprocess.Popen(
            [caddy_bin, "run", "--config", str(config_path), "--adapter", "caddyfile"],
            stdout=handle,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            text=True,
            env=env,
        )
    deadline = time.time() + 10
    while time.time() < deadline:
        if process.poll() is not None:
            log_excerpt = log_file.read_text(encoding="utf-8", errors="ignore")
            raise RuntimeError(
                f"Caddy exited early with code {process.returncode}\n{log_excerpt}"
            )
        time.sleep(0.25)
        return process.pid
    return process.pid


def trust_caddy_root(caddy_bin: str, *, config_path: Path) -> bool:
    if str(os.environ.get("VIVENTIUM_REMOTE_CALL_CADDY_AUTO_TRUST", "") or "").strip().lower() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return False
    try:
        result = run_checked(
            [caddy_bin, "trust", "--config", str(config_path)],
            stdin=subprocess.DEVNULL,
            timeout_seconds=8,
        )
    except subprocess.TimeoutExpired:
        return False
    return result.returncode == 0


def ensure_upnp_mapping(
    upnpc_bin: str,
    *,
    protocol: str,
    external_port: int,
    internal_host: str,
    internal_port: int,
    description: str,
    lease_seconds: int = 14400,
) -> None:
    protocol = protocol.upper()
    state = list_upnpc_state(upnpc_bin)
    existing = (state.get("mappings") or {}).get((protocol, external_port))
    if existing == (internal_host, internal_port):
        return
    if existing and existing != (internal_host, internal_port):
        raise RuntimeError(
            f"Router already forwards {protocol} {external_port} to {existing[0]}:{existing[1]}; "
            f"cannot reuse it for Viventium {description}"
        )

    result = run_checked(
        [
            upnpc_bin,
            "-a",
            internal_host,
            str(internal_port),
            str(external_port),
            protocol,
            str(max(0, int(lease_seconds))),
        ],
        timeout_seconds=10,
    )
    if result.returncode != 0:
        stderr = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(
            f"Failed to create router port forward for {description} ({protocol} {external_port}->{internal_host}:{internal_port}): {stderr}".strip()
        )


def remove_upnp_mapping(upnpc_bin: str, *, external_port: int, protocol: str) -> None:
    result = run_checked(
        [upnpc_bin, "-d", str(external_port), protocol.upper()],
        timeout_seconds=8,
    )
    if result.returncode != 0:
        stderr = (result.stderr or result.stdout or "").strip().lower()
        if "no such port mapping" in stderr or "not found" in stderr:
            return
        raise RuntimeError(
            f"Failed to remove router port forward for {protocol.upper()} {external_port}: {(result.stderr or result.stdout or '').strip()}".strip()
        )


def public_edge_mapping_description(protocol: str, external_port: int) -> str:
    protocol = str(protocol or "").upper()
    if protocol == "TCP" and external_port == DEFAULT_PUBLIC_EDGE_HTTP_EXTERNAL_PORT:
        return "Viventium public HTTP"
    if protocol == "TCP" and external_port == DEFAULT_PUBLIC_EDGE_HTTPS_EXTERNAL_PORT:
        return "Viventium public HTTPS"
    if protocol == "TCP" and external_port == DEFAULT_PUBLIC_EDGE_TURN_TLS_EXTERNAL_PORT:
        return "Viventium LiveKit TURN/TLS"
    if protocol == "UDP":
        return "Viventium LiveKit UDP media"
    return "Viventium LiveKit TCP media"


def refresh_public_https_edge_mappings(state: dict[str, Any], *, lease_seconds: int) -> dict[str, Any]:
    if str(state.get("provider") or "").strip() != "public_https_edge":
        return state
    upnpc_bin = resolve_binary("upnpc")
    if not upnpc_bin:
        raise RuntimeError("miniupnpc is required to refresh public HTTPS edge router mappings")

    router = state.get("router") if isinstance(state.get("router"), dict) else {}
    mappings = router.get("mappings") if isinstance(router, dict) else []
    if not isinstance(mappings, list) or not mappings:
        return state

    for mapping in mappings:
        if not isinstance(mapping, dict):
            continue
        protocol = str(mapping.get("protocol") or "TCP").upper()
        external_port = int(mapping.get("external_port") or 0)
        internal_host = str(mapping.get("internal_host") or "").strip()
        internal_port = int(mapping.get("internal_port") or 0)
        if external_port <= 0 or internal_port <= 0 or not internal_host:
            continue
        ensure_upnp_mapping(
            upnpc_bin,
            protocol=protocol,
            external_port=external_port,
            internal_host=internal_host,
            internal_port=internal_port,
            description=public_edge_mapping_description(protocol, external_port),
            lease_seconds=lease_seconds,
        )

    refreshed_state = dict(state)
    refreshed_router = dict(router) if isinstance(router, dict) else {}
    refreshed_router["mapping_lease_seconds"] = int(max(0, lease_seconds))
    refreshed_router["last_refreshed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    refreshed_state["router"] = refreshed_router
    return refreshed_state


def probe_sni_https_host(
    hostname: str,
    *,
    https_port: int,
    timeout_seconds: float = DEFAULT_HEALTH_TIMEOUT_SECONDS,
) -> bool:
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    try:
        with socket.create_connection(("127.0.0.1", https_port), timeout=timeout_seconds) as raw_sock:
            with ssl_context.wrap_socket(raw_sock, server_hostname=hostname) as tls_sock:
                request = (
                    f"HEAD / HTTP/1.1\r\nHost: {hostname}\r\nConnection: close\r\nUser-Agent: viventium\r\n\r\n"
                )
                tls_sock.sendall(request.encode("utf-8"))
                response = tls_sock.recv(1024)
                return response.startswith(b"HTTP/")
    except Exception:
        return False


def wait_for_public_caddy_hosts(
    hostnames: list[str],
    *,
    https_port: int,
    timeout_seconds: int,
) -> None:
    remaining = set(hostnames)
    deadline = time.time() + max(timeout_seconds, 10)
    while time.time() < deadline:
        for hostname in list(remaining):
            if probe_sni_https_host(hostname, https_port=https_port):
                remaining.discard(hostname)
        if not remaining:
            return
        time.sleep(0.5)

    unresolved = ", ".join(sorted(remaining))
    raise RuntimeError(
        f"Timed out waiting for public HTTPS certificates on: {unresolved}. "
        "Make sure those hostnames resolve to this machine's public IP and ports 80/tcp and 443/tcp are routed to the local Caddy edge."
    )


def start_netbird(args: argparse.Namespace, *, state_path: Path, log_dir: Path) -> dict[str, Any]:
    if args.client_port <= 0 and args.api_port <= 0 and args.playground_port <= 0 and args.livekit_port <= 0:
        raise RuntimeError("At least one local surface port is required for NetBird remote access")

    caddy_bin = ensure_caddy(args.auto_install)
    required_surfaces: dict[str, tuple[str, int]] = {}

    if args.client_port > 0:
        required_surfaces["client"] = (args.public_client_origin, args.client_port)
    if args.api_port > 0:
        required_surfaces["api"] = (args.public_api_origin, args.api_port)
    if args.playground_port > 0:
        required_surfaces["playground"] = (args.public_playground_origin, args.playground_port)
    if args.livekit_port > 0:
        required_surfaces["livekit"] = (args.public_livekit_url, args.livekit_port)

    surfaces: dict[str, dict[str, Any]] = {}
    caddy_sites: list[tuple[str, int]] = []
    host_for_node_ip = ""

    for name, (public_value, local_port) in required_surfaces.items():
        if name == "livekit":
            parsed = require_livekit_public_url(public_value)
            public_ws_url = format_wss_origin(parsed.hostname or "", parsed.port or 443)
            public_https_url = re.sub(r"^wss://", "https://", public_ws_url)
            surfaces[name] = build_surface(
                target_url=surface_target_url(local_port),
                public_url=public_https_url,
                public_ws_url=public_ws_url,
            )
        else:
            parsed = require_https_url(public_value, f"public_{name}_origin")
            public_url = format_https_origin(parsed.hostname or "", parsed.port or 443)
            surfaces[name] = build_surface(
                target_url=surface_target_url(local_port),
                public_url=public_url,
            )

        caddy_sites.append((caddy_site_address(parsed), local_port))
        if not host_for_node_ip and parsed.hostname:
            host_for_node_ip = parsed.hostname

    admin_port = pick_caddy_admin_port()
    data_dir = Path(args.caddy_data_dir).expanduser() if args.caddy_data_dir else state_path.parent / "caddy"
    data_dir.mkdir(parents=True, exist_ok=True)
    config_path = state_path.with_suffix(".Caddyfile")
    config_path.write_text(
        render_caddyfile(admin_port=admin_port, surfaces=caddy_sites, tls_internal=True),
        encoding="utf-8",
    )
    caddy_pid = start_caddy_process(
        caddy_bin,
        config_path=config_path,
        data_dir=data_dir,
        log_file=log_dir / "remote-call-netbird-caddy.log",
    )
    trusted = trust_caddy_root(caddy_bin, config_path=config_path)
    node_ip = str(args.livekit_node_ip or "").strip() or derive_local_ip_from_hostname(host_for_node_ip)
    trust_note = ""
    if not trusted:
        trust_note = (
            f"Caddy local CA trust is not active for {config_path}. "
            "Run `caddy trust --config <that Caddyfile>` on this Mac if you want the local browser "
            "to stop prompting, trust the same CA on any other mesh client devices, or set "
            "`VIVENTIUM_REMOTE_CALL_CADDY_AUTO_TRUST=true` if you explicitly want startup to try "
            "the trust step."
        )

    return build_state(
        "netbird_selfhosted_mesh",
        surfaces,
        livekit_node_ip=node_ip,
        extras={
            "trust_note": trust_note,
            "caddy": {
                "pid": caddy_pid,
                "admin_port": admin_port,
                "config_path": str(config_path),
                "data_dir": str(data_dir),
                "trusted": trusted,
            }
        },
    )


def start_public_https_edge(
    args: argparse.Namespace,
    *,
    state_path: Path,
    log_dir: Path,
) -> dict[str, Any]:
    if args.client_port <= 0 and args.api_port <= 0 and args.playground_port <= 0 and args.livekit_port <= 0:
        raise RuntimeError("At least one local surface port is required for public HTTPS edge access")

    caddy_bin = ensure_caddy(args.auto_install)
    upnp_lease_seconds = int(
        max(
            0,
            getattr(args, "upnp_lease_seconds", DEFAULT_PUBLIC_EDGE_UPNP_LEASE_SECONDS),
        )
    )
    upnpc_bin = resolve_binary("upnpc")
    if not upnpc_bin and args.auto_install:
        try:
            upnpc_bin = ensure_upnpc(True)
        except Exception:
            upnpc_bin = ""
    upnp_state: dict[str, Any] = {}
    manual_note = ""
    if upnpc_bin:
        try:
            upnp_state = list_upnpc_state(upnpc_bin)
        except Exception:
            upnpc_bin = ""
    lan_ip = str(upnp_state.get("local_ip") or "").strip() or detect_lan_ipv4()
    if not lan_ip:
        raise RuntimeError("Unable to determine the local LAN IPv4 address for router port forwarding")
    public_ip = discover_public_ipv4(upnpc_bin or None)

    surfaces: dict[str, dict[str, Any]] = {}
    caddy_sites: list[tuple[str, int]] = []
    caddy_hosts: list[str] = []
    livekit_host = ""
    client_host = ""
    public_client_url = ""
    public_playground_url = ""

    if args.client_port > 0:
        host, public_url = resolve_public_https_edge_surface(
            "client",
            args.public_client_origin,
            public_ip=public_ip,
        )
        surfaces["client"] = build_surface(
            target_url=surface_target_url(args.client_port),
            public_url=public_url,
        )
        caddy_sites.append((host, args.client_port))
        caddy_hosts.append(host)
        client_host = host
        public_client_url = public_url

    if args.api_port > 0:
        host, public_url = resolve_public_https_edge_surface(
            "api",
            args.public_api_origin,
            public_ip=public_ip,
        )
        surfaces["api"] = build_surface(
            target_url=surface_target_url(args.api_port),
            public_url=public_url,
        )
        caddy_sites.append((host, args.api_port))
        caddy_hosts.append(host)

    if args.playground_port > 0:
        host, public_url = resolve_public_https_edge_surface(
            "playground",
            args.public_playground_origin,
            public_ip=public_ip,
        )
        surfaces["playground"] = build_surface(
            target_url=surface_target_url(args.playground_port),
            public_url=public_url,
        )
        caddy_sites.append((host, args.playground_port))
        caddy_hosts.append(host)
        public_playground_url = public_url

    if args.livekit_port > 0:
        public_https_url, public_wss_url = resolve_public_https_edge_surface(
            "livekit",
            args.public_livekit_url,
            public_ip=public_ip,
        )
        livekit_host = urllib.parse.urlparse(public_https_url).hostname or ""
        surfaces["livekit"] = build_surface(
            target_url=surface_target_url(args.livekit_port),
            public_url=public_https_url,
            public_ws_url=public_wss_url,
        )
        caddy_sites.append((livekit_host, args.livekit_port))
        caddy_hosts.append(livekit_host)

    site_targets: dict[str, int] = {}
    for host, upstream_port in caddy_sites:
        existing = site_targets.get(host)
        if existing is not None and existing != upstream_port:
            raise RuntimeError(
                "public_https_edge currently requires unique hostnames per surface. "
                "Use separate subdomains for the app, API, playground, and LiveKit signaling origins."
            )
        site_targets[host] = upstream_port

    admin_port = pick_caddy_admin_port()
    internal_http_port = pick_free_port()
    internal_https_port = pick_free_port()
    data_dir = Path(args.caddy_data_dir).expanduser() if args.caddy_data_dir else state_path.parent / "caddy"
    data_dir.mkdir(parents=True, exist_ok=True)
    directory_identity: dict[str, str] | None = None
    well_known_bodies: dict[str, str] = {}
    if client_host and public_client_url:
        directory_identity = ensure_directory_identity(state_path)
        well_known_bodies[client_host] = render_directory_instance_document(
            client_origin=public_client_url,
            provider="public_https_edge",
            identity=directory_identity,
            public_playground_url=public_playground_url,
        )
    config_path = state_path.with_suffix(".Caddyfile")
    config_path.write_text(
        render_caddyfile(
            admin_port=admin_port,
            surfaces=caddy_sites,
            tls_internal=False,
            http_port=internal_http_port,
            https_port=internal_https_port,
            well_known_bodies=well_known_bodies,
        ),
        encoding="utf-8",
    )

    port_mappings: list[dict[str, Any]] = []
    if upnpc_bin:
        ensure_upnp_mapping(
            upnpc_bin,
            protocol="TCP",
            external_port=DEFAULT_PUBLIC_EDGE_HTTP_EXTERNAL_PORT,
            internal_host=lan_ip,
            internal_port=internal_http_port,
            description="Viventium public HTTP",
            lease_seconds=upnp_lease_seconds,
        )
        port_mappings.append(
            {
                "protocol": "TCP",
                "external_port": DEFAULT_PUBLIC_EDGE_HTTP_EXTERNAL_PORT,
                "internal_host": lan_ip,
                "internal_port": internal_http_port,
            }
        )
        ensure_upnp_mapping(
            upnpc_bin,
            protocol="TCP",
            external_port=DEFAULT_PUBLIC_EDGE_HTTPS_EXTERNAL_PORT,
            internal_host=lan_ip,
            internal_port=internal_https_port,
            description="Viventium public HTTPS",
            lease_seconds=upnp_lease_seconds,
        )
        port_mappings.append(
            {
                "protocol": "TCP",
                "external_port": DEFAULT_PUBLIC_EDGE_HTTPS_EXTERNAL_PORT,
                "internal_host": lan_ip,
                "internal_port": internal_https_port,
            }
        )

        if args.livekit_tcp_port > 0:
            ensure_upnp_mapping(
                upnpc_bin,
                protocol="TCP",
                external_port=args.livekit_tcp_port,
                internal_host=lan_ip,
                internal_port=args.livekit_tcp_port,
                description="Viventium LiveKit TCP media",
                lease_seconds=upnp_lease_seconds,
            )
            port_mappings.append(
                {
                    "protocol": "TCP",
                    "external_port": args.livekit_tcp_port,
                    "internal_host": lan_ip,
                    "internal_port": args.livekit_tcp_port,
                }
            )

        if args.livekit_udp_port > 0:
            ensure_upnp_mapping(
                upnpc_bin,
                protocol="UDP",
                external_port=args.livekit_udp_port,
                internal_host=lan_ip,
                internal_port=args.livekit_udp_port,
                description="Viventium LiveKit UDP media",
                lease_seconds=upnp_lease_seconds,
            )
            port_mappings.append(
                {
                    "protocol": "UDP",
                    "external_port": args.livekit_udp_port,
                    "internal_host": lan_ip,
                    "internal_port": args.livekit_udp_port,
                }
            )

        if livekit_host and args.livekit_turn_tls_port > 0:
            ensure_upnp_mapping(
                upnpc_bin,
                protocol="TCP",
                external_port=args.livekit_turn_tls_port,
                internal_host=lan_ip,
                internal_port=args.livekit_turn_tls_port,
                description="Viventium LiveKit TURN/TLS",
                lease_seconds=upnp_lease_seconds,
            )
            port_mappings.append(
                {
                    "protocol": "TCP",
                    "external_port": args.livekit_turn_tls_port,
                    "internal_host": lan_ip,
                    "internal_port": args.livekit_turn_tls_port,
                }
            )
    else:
        manual_note = (
            "UPnP/NAT-PMP auto-mapping is unavailable, so ports 80/tcp, 443/tcp, "
            f"{args.livekit_tcp_port or 7889}/tcp, {args.livekit_udp_port or 7890}/udp, "
            f"and {args.livekit_turn_tls_port or DEFAULT_PUBLIC_EDGE_TURN_TLS_EXTERNAL_PORT}/tcp "
            "must already be forwarded manually to this Mac."
        )

    caddy_pid = 0
    livekit_turn_cert_file = ""
    livekit_turn_key_file = ""
    try:
        caddy_pid = start_caddy_process(
            caddy_bin,
            config_path=config_path,
            data_dir=data_dir,
            log_file=log_dir / "remote-call-public-caddy.log",
        )
        wait_for_public_caddy_hosts(
            caddy_hosts,
            https_port=internal_https_port,
            timeout_seconds=args.timeout_seconds,
        )
        cert_pair = resolve_public_edge_livekit_cert_pair(data_dir, livekit_host)
        if cert_pair:
            livekit_turn_cert_file, livekit_turn_key_file = cert_pair
    except Exception:
        if caddy_pid:
            stop_pid(caddy_pid)
        for mapping in port_mappings:
            try:
                remove_upnp_mapping(
                    upnpc_bin,
                    external_port=int(mapping["external_port"]),
                    protocol=str(mapping["protocol"]),
                )
            except Exception:
                continue
        raise
    state = build_state(
        "public_https_edge",
        surfaces,
        livekit_node_ip=public_ip,
        extras={
            "public_ip": public_ip,
            "trust_note": manual_note,
            "router": {
                "local_ip": lan_ip,
                "mapping_lease_seconds": upnp_lease_seconds,
                "mappings": port_mappings,
            },
            "caddy": {
                "pid": caddy_pid,
                "admin_port": admin_port,
                "config_path": str(config_path),
                "data_dir": str(data_dir),
                "http_port": internal_http_port,
                "https_port": internal_https_port,
            },
        },
    )
    if directory_identity and public_client_url:
        state["directory_instance_id"] = str(directory_identity.get("instance_id") or "").strip()
        state["directory_public_key_fingerprint"] = str(
            directory_identity.get("public_key_fingerprint") or ""
        ).strip()
        state["directory_well_known_url"] = public_client_url.rstrip("/") + DIRECTORY_INSTANCE_PATH
        state["directory"] = {
            "instance_id": state["directory_instance_id"],
            "public_key_fingerprint": state["directory_public_key_fingerprint"],
            "public_key_pem": str(directory_identity.get("public_key_pem") or "").strip(),
            "registration_algorithm": str(
                directory_identity.get("registration_algorithm") or DIRECTORY_REGISTRATION_ALGORITHM
            ),
            "well_known_url": state["directory_well_known_url"],
        }
    if livekit_host:
        state["livekit_turn_domain"] = livekit_host
        state["livekit_turn_tls_port"] = args.livekit_turn_tls_port
        if livekit_turn_cert_file and livekit_turn_key_file:
            state["livekit_turn_cert_file"] = livekit_turn_cert_file
            state["livekit_turn_key_file"] = livekit_turn_key_file
    return state


def stop_state(state: dict[str, Any]) -> None:
    provider = str(state.get("provider") or "").strip()
    if not provider:
        return

    if provider == "cloudflare_quick_tunnel":
        for _key, surface in iter_surfaces(state):
            stop_pid(surface.get("pid"))
        return

    if provider == "tailscale_tailnet_https":
        tailscale_bin = resolve_binary("tailscale")
        if not tailscale_bin:
            return
        managed_ports = ((state.get("tailscale") or {}).get("managed_ports")) or []
        for value in managed_ports:
            try:
                remove_tailscale_https_proxy(tailscale_bin, public_port=int(value))
            except Exception:
                continue
        return

    if provider == "netbird_selfhosted_mesh":
        stop_pid(((state.get("caddy") or {}).get("pid")))
        return

    if provider == "public_https_edge":
        stop_pid(((state.get("caddy") or {}).get("pid")))
        upnpc_bin = resolve_binary("upnpc")
        if not upnpc_bin:
            return
        for mapping in ((state.get("router") or {}).get("mappings") or []):
            try:
                remove_upnp_mapping(
                    upnpc_bin,
                    external_port=int(mapping.get("external_port") or 0),
                    protocol=str(mapping.get("protocol") or "TCP"),
                )
            except Exception:
                continue
        return


def cmd_start(args: argparse.Namespace) -> int:
    state_path = Path(args.state_file)
    log_dir = Path(args.log_dir)
    lock_handle = with_lock(state_path.with_suffix(".lock"))
    try:
        existing = load_state(state_path)
        if state_is_healthy(existing):
            print(json.dumps(existing))
            return 0

        if existing:
            stop_state(existing)

        provider = str(args.provider or "cloudflare_quick_tunnel").strip().lower()
        if provider == "cloudflare_quick_tunnel":
            state = start_cloudflare(args, log_dir=log_dir)
        elif provider == "tailscale_tailnet_https":
            state = start_tailscale(args)
        elif provider == "netbird_selfhosted_mesh":
            state = start_netbird(args, state_path=state_path, log_dir=log_dir)
        elif provider == "public_https_edge":
            state = start_public_https_edge(args, state_path=state_path, log_dir=log_dir)
        else:
            raise RuntimeError(f"Unsupported remote call provider: {provider}")

        save_state(state_path, state)
        print(json.dumps(state))
        return 0
    finally:
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
        finally:
            lock_handle.close()


def cmd_stop(args: argparse.Namespace) -> int:
    state_path = Path(args.state_file)
    lock_handle = with_lock(state_path.with_suffix(".lock"))
    try:
        state = load_state(state_path)
        stop_state(state)
        state_path.unlink(missing_ok=True)
        print(json.dumps({"stopped": True}))
        return 0
    finally:
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
        finally:
            lock_handle.close()


def cmd_status(args: argparse.Namespace) -> int:
    state = load_state(Path(args.state_file))
    state["healthy"] = state_is_healthy(state)
    print(json.dumps(state))
    return 0 if state.get("healthy") else 1


def cmd_refresh_mappings(args: argparse.Namespace) -> int:
    state_path = Path(args.state_file)
    state = load_state(state_path)
    if not state:
        raise RuntimeError(f"No remote access state found at {state_path}")
    refreshed_state = refresh_public_https_edge_mappings(
        state,
        lease_seconds=int(args.upnp_lease_seconds or DEFAULT_PUBLIC_EDGE_UPNP_LEASE_SECONDS),
    )
    save_state(state_path, refreshed_state)
    print(json.dumps(refreshed_state))
    return 0


def main() -> int:
    args = parse_args()
    if args.command == "start":
        return cmd_start(args)
    if args.command == "stop":
        return cmd_stop(args)
    if args.command == "status":
        return cmd_status(args)
    if args.command == "refresh-mappings":
        return cmd_refresh_mappings(args)
    raise RuntimeError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        sys.stderr.write(f"{exc}\n")
        raise SystemExit(1)

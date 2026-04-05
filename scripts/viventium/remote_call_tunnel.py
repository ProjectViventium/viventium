#!/usr/bin/env python3
from __future__ import annotations

import argparse
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
    start.add_argument("--public-client-origin", default="")
    start.add_argument("--public-api-origin", default="")
    start.add_argument("--public-playground-origin", default="")
    start.add_argument("--public-livekit-url", default="")
    start.add_argument("--livekit-node-ip", default="")
    start.add_argument("--caddy-data-dir", default="")
    start.add_argument(
        "--timeout-seconds",
        type=int,
        default=parse_timeout_seconds(os.environ.get("VIVENTIUM_REMOTE_CALL_TUNNEL_TIMEOUT_SECONDS")),
    )

    stop = subparsers.add_parser("stop", help="Stop secure remote access surfaces")
    stop.add_argument("--state-file", required=True)

    status = subparsers.add_parser("status", help="Print current secure remote access state")
    status.add_argument("--state-file", required=True)

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
    return f"http://127.0.0.1:{port}"


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
) -> str:
    lines = [
        "{",
        f"    admin 127.0.0.1:{admin_port}",
        "}",
        "",
    ]
    for site_address, upstream_port in surfaces:
        lines.extend(
            [
                f"{site_address} {{",
                "    tls internal",
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
        render_caddyfile(admin_port=admin_port, surfaces=caddy_sites),
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


def main() -> int:
    args = parse_args()
    if args.command == "start":
        return cmd_start(args)
    if args.command == "stop":
        return cmd_stop(args)
    if args.command == "status":
        return cmd_status(args)
    raise RuntimeError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        sys.stderr.write(f"{exc}\n")
        raise SystemExit(1)

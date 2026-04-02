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
COMMON_BINARY_PATHS: dict[str, tuple[str, ...]] = {
    "cloudflared": (
        "/opt/homebrew/bin/cloudflared",
        "/usr/local/bin/cloudflared",
    ),
    "brew": (
        "/opt/homebrew/bin/brew",
        "/usr/local/bin/brew",
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
        description="Manage secure remote call tunnels for local Viventium voice sessions."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start", help="Start or reuse secure call tunnels")
    start.add_argument("--state-file", required=True)
    start.add_argument("--log-dir", required=True)
    start.add_argument("--playground-port", type=int, required=True)
    start.add_argument("--livekit-port", type=int, required=True)
    start.add_argument("--provider", default="cloudflare_quick_tunnel")
    start.add_argument("--auto-install", action="store_true")
    start.add_argument(
        "--timeout-seconds",
        type=int,
        default=parse_timeout_seconds(os.environ.get("VIVENTIUM_REMOTE_CALL_TUNNEL_TIMEOUT_SECONDS")),
    )

    stop = subparsers.add_parser("stop", help="Stop secure call tunnels")
    stop.add_argument("--state-file", required=True)

    status = subparsers.add_parser("status", help="Print current secure call tunnel state")
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


def ensure_cloudflared(auto_install: bool) -> str:
    cloudflared = resolve_binary("cloudflared")
    if cloudflared:
        return cloudflared
    if not auto_install:
        raise RuntimeError("cloudflared is not installed")
    brew = resolve_binary("brew")
    if not brew:
        raise RuntimeError("cloudflared is not installed and Homebrew is unavailable")
    subprocess.run([brew, "list", "cloudflared"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run([brew, "install", "cloudflared"], check=True)
    cloudflared = resolve_binary("cloudflared")
    if not cloudflared:
        raise RuntimeError("cloudflared installation completed but binary is still unavailable")
    return cloudflared


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


def build_state(
    provider: str,
    playground_pid: int,
    playground_url: str,
    livekit_pid: int,
    livekit_url: str,
    playground_port: int,
    livekit_port: int,
) -> dict[str, Any]:
    return {
        "provider": provider,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "playground": {
            "pid": playground_pid,
            "target": f"http://127.0.0.1:{playground_port}",
            "public_url": playground_url,
        },
        "livekit": {
            "pid": livekit_pid,
            "target": f"http://127.0.0.1:{livekit_port}",
            "public_url": livekit_url,
            "public_ws_url": re.sub(r"^https://", "wss://", livekit_url),
        },
        "public_playground_url": playground_url,
        "public_livekit_url": re.sub(r"^https://", "wss://", livekit_url),
    }


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


def state_is_healthy(state: dict[str, Any]) -> bool:
    playground = state.get("playground") or {}
    livekit = state.get("livekit") or {}
    return (
        pid_is_running(playground.get("pid"))
        and pid_is_running(livekit.get("pid"))
        and isinstance(state.get("public_playground_url"), str)
        and state.get("public_playground_url")
        and isinstance(state.get("public_livekit_url"), str)
        and state.get("public_livekit_url")
        and probe_local_endpoint(playground.get("target"))
        and probe_local_endpoint(livekit.get("target"))
    )


def wait_for_state_ready(state: dict[str, Any], timeout_seconds: int) -> bool:
    deadline = time.time() + max(timeout_seconds, 1)
    while time.time() < deadline:
        if state_is_healthy(state):
            return True
        time.sleep(1)
    return state_is_healthy(state)


def with_lock(lock_path: Path):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+", encoding="utf-8")
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
    return handle


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
            stop_pid((existing.get("playground") or {}).get("pid"))
            stop_pid((existing.get("livekit") or {}).get("pid"))

        if args.provider != "cloudflare_quick_tunnel":
            raise RuntimeError(f"Unsupported remote call provider: {args.provider}")

        cloudflared_bin = ensure_cloudflared(args.auto_install)

        playground_pid, playground_url = start_quick_tunnel(
            cloudflared_bin,
            target_url=f"http://127.0.0.1:{args.playground_port}",
            log_file=log_dir / "remote-call-playground-tunnel.log",
            timeout_seconds=args.timeout_seconds,
        )
        try:
            livekit_pid, livekit_url = start_quick_tunnel(
                cloudflared_bin,
                target_url=f"http://127.0.0.1:{args.livekit_port}",
                log_file=log_dir / "remote-call-livekit-tunnel.log",
                timeout_seconds=args.timeout_seconds,
            )
        except Exception:
            stop_pid(playground_pid)
            raise

        state = build_state(
            args.provider,
            playground_pid,
            playground_url,
            livekit_pid,
            livekit_url,
            args.playground_port,
            args.livekit_port,
        )
        if not wait_for_state_ready(state, args.timeout_seconds):
            stop_pid(playground_pid)
            stop_pid(livekit_pid)
            raise RuntimeError(
                "Timed out waiting for remote call tunnels to become publicly reachable"
            )
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
        stop_pid((state.get("playground") or {}).get("pid"))
        stop_pid((state.get("livekit") or {}).get("pid"))
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

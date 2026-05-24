#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_PORT = 8781
DEPENDENCIES = ["fastapi", "uvicorn", "PyYAML", "pydantic", "croniter"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def state_dir(app_support_dir: Path) -> Path:
    return app_support_dir / "state" / "prompt-workbench"


def log_path(app_support_dir: Path) -> Path:
    return app_support_dir / "logs" / "prompt-workbench.log"


def state_path(app_support_dir: Path) -> Path:
    return state_dir(app_support_dir) / "state.json"


def user_stopped_marker_path(app_support_dir: Path) -> Path:
    return state_dir(app_support_dir) / "user-stopped.marker"


def workbench_root(repo_root: Path) -> Path:
    return repo_root / "viventium_v0_4" / "prompt-workbench"


def health_url(port: int) -> str:
    return f"http://127.0.0.1:{port}/api/health"


def app_url(port: int) -> str:
    return f"http://127.0.0.1:{port}"


def token_url(port: int, token: str | None) -> str:
    url = app_url(port)
    if not token:
        return url
    return f"{url}?workbench_token={token}"


def load_runtime_env(app_support_dir: Path, env: dict[str, str]) -> None:
    runtime_dir = app_support_dir / "runtime"
    for path in (runtime_dir / "runtime.env", runtime_dir / "runtime.local.env"):
        if not path.exists():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            text = line.strip()
            if not text or text.startswith("#") or "=" not in text:
                continue
            if text.startswith("export "):
                text = text.removeprefix("export ").strip()
            key, value = text.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'\"")
            if key and key not in env:
                env[key] = value


def resolve_launch_admin(env: dict[str, str]) -> dict[str, str]:
    configured_user_id = (env.get("VIVENTIUM_PROMPT_WORKBENCH_ADMIN_USER_ID") or "").strip()
    configured_email = (env.get("VIVENTIUM_PROMPT_WORKBENCH_ADMIN_EMAIL") or "").strip()
    if configured_user_id:
        return {"userId": configured_user_id, "email": configured_email}

    email = (
        configured_email
        or (env.get("VIVENTIUM_MEMORY_HARDENING_USER_EMAIL") or "").strip()
        or (env.get("LIBRECHAT_ADMIN_EMAIL") or "").strip()
    )
    mongo_port = (env.get("VIVENTIUM_LOCAL_MONGO_PORT") or "27117").strip()
    mongo_db = (env.get("VIVENTIUM_LOCAL_MONGO_DB") or "LibreChatViventium").strip()
    script = (
        "const email = " + json.dumps(email) + ";"
        "const role = {$in:['ADMIN','admin']};"
        "const query = email ? {email, role} : {role};"
        "const u = db.users.findOne(query, {_id:1,email:1,role:1});"
        "if (u) print(JSON.stringify({_id:String(u._id),email:u.email||''}));"
    )
    try:
        completed = subprocess.run(
            ["mongosh", "--quiet", f"mongodb://127.0.0.1:{mongo_port}/{mongo_db}", "--eval", script],
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"userId": "local-admin", "email": configured_email}
    if completed.returncode != 0 or not completed.stdout.strip():
        return {"userId": "local-admin", "email": configured_email}
    try:
        payload = json.loads(completed.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return {"userId": "local-admin", "email": configured_email}
    user_id = str(payload.get("_id") or "").strip()
    if not user_id:
        return {"userId": "local-admin", "email": configured_email}
    return {"userId": user_id, "email": str(payload.get("email") or configured_email)}


def read_state(app_support_dir: Path) -> dict[str, Any]:
    path = state_path(app_support_dir)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def write_state(app_support_dir: Path, payload: dict[str, Any]) -> None:
    directory = state_dir(app_support_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = state_path(app_support_dir)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def clear_state(app_support_dir: Path) -> None:
    try:
        state_path(app_support_dir).unlink()
    except FileNotFoundError:
        pass


def mark_user_stopped(app_support_dir: Path) -> None:
    directory = state_dir(app_support_dir)
    directory.mkdir(parents=True, exist_ok=True)
    user_stopped_marker_path(app_support_dir).write_text(utc_now() + "\n", encoding="utf-8")


def clear_user_stopped_marker(app_support_dir: Path) -> None:
    try:
        user_stopped_marker_path(app_support_dir).unlink()
    except FileNotFoundError:
        pass


def http_healthy(port: int, timeout: float = 1.5) -> bool:
    request = urllib.request.Request(health_url(port), method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                return False
            body = response.read(512)
    except (OSError, urllib.error.URLError, urllib.error.HTTPError):
        return False
    return b'"ok"' in body or b"ok" in body


def port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def process_command(pid: int) -> str:
    try:
        completed = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            text=True,
            capture_output=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return completed.stdout.strip()


def pid_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def process_matches_workbench(pid: int, root: Path) -> bool:
    command = process_command(pid)
    if not command:
        return False
    root_text = str(root)
    return "prompt_workbench.app:app" in command and (
        root_text in command or str(root / "backend") in command
    )


def status_payload(repo_root: Path, app_support_dir: Path) -> dict[str, Any]:
    payload = read_state(app_support_dir)
    pid = int(payload.get("pid") or 0)
    port = int(payload.get("port") or DEFAULT_PORT)
    root = workbench_root(repo_root)
    running = pid_running(pid) and process_matches_workbench(pid, root) and http_healthy(port)
    if not running and pid > 0 and not pid_running(pid):
        clear_state(app_support_dir)
    result = {
        "status": "running" if running else "stopped",
        "pid": pid if running else None,
        "port": port if running else None,
        "url": app_url(port) if running else None,
    }
    if running and payload.get("authUrl"):
        result["authUrl"] = payload.get("authUrl")
    if running:
        result["managedByStack"] = bool(payload.get("managedByStack"))
    return result


def ensure_workbench_exists(root: Path) -> None:
    if not root.exists():
        raise RuntimeError("Prompt Workbench source is missing from this checkout.")
    if not (root / "package.json").exists():
        raise RuntimeError("Prompt Workbench package.json is missing from this checkout.")
    if not (root / "backend" / "prompt_workbench" / "app.py").exists():
        raise RuntimeError("Prompt Workbench backend is missing from this checkout.")


def newest_mtime(paths: list[Path]) -> float:
    newest = 0.0
    for path in paths:
        if path.is_file():
            newest = max(newest, path.stat().st_mtime)
        elif path.is_dir():
            for child in path.rglob("*"):
                ignored_parts = {"node_modules", "dist", "__pycache__", ".pytest_cache", ".vite"}
                if child.is_file() and not ignored_parts.intersection(child.parts):
                    newest = max(newest, child.stat().st_mtime)
    return newest


def run_logged(command: list[str], cwd: Path, env: dict[str, str], log_file: Path) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("ab", buffering=0) as handle:
        handle.write(f"\n[{utc_now()}] Running: {' '.join(command)}\n".encode("utf-8"))
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=handle,
            stderr=subprocess.STDOUT,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(f"Prompt Workbench command failed: {' '.join(command)}")


def ensure_assets_built(root: Path, log_file: Path, *, skip_build: bool) -> None:
    dist_index = root / "dist" / "index.html"
    if skip_build and dist_index.exists():
        return
    package_lock = root / "package-lock.json"
    node_modules = root / "node_modules"
    env = os.environ.copy()

    if not node_modules.exists():
        install_command = ["npm", "ci"] if package_lock.exists() else ["npm", "install"]
        run_logged(install_command, cwd=root, env=env, log_file=log_file)

    source_mtime = newest_mtime([root / "src", root / "backend", root / "public", root / "index.html", root / "package.json"])
    dist_mtime = dist_index.stat().st_mtime if dist_index.exists() else 0.0
    if skip_build and dist_index.exists():
        return
    if not dist_index.exists() or source_mtime > dist_mtime:
        run_logged(["npm", "run", "build"], cwd=root, env=env, log_file=log_file)


def choose_port(app_support_dir: Path, preferred: int) -> int:
    current = read_state(app_support_dir)
    current_port = int(current.get("port") or 0)
    current_pid = int(current.get("pid") or 0)
    if current_port > 0 and pid_running(current_pid) and http_healthy(current_port):
        return current_port

    for port in [preferred, *range(DEFAULT_PORT, DEFAULT_PORT + 20)]:
        if port_available(port):
            return port
    raise RuntimeError("No free Prompt Workbench port found in the local range.")


def wait_for_health(port: int, timeout_seconds: int) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if http_healthy(port):
            return True
        time.sleep(0.5)
    return http_healthy(port)


def start_server(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = Path(args.repo_root).resolve()
    app_support_dir = Path(args.app_support_dir).expanduser().resolve()
    root = workbench_root(repo_root)
    ensure_workbench_exists(root)

    current = status_payload(repo_root, app_support_dir)
    if current["status"] == "running":
        clear_user_stopped_marker(app_support_dir)
        return {**current, "started": False}

    preferred_port = int(args.port or os.environ.get("VIVENTIUM_PROMPT_WORKBENCH_PORT") or DEFAULT_PORT)
    port = choose_port(app_support_dir, preferred_port)
    log_file = log_path(app_support_dir)
    ensure_assets_built(root, log_file, skip_build=args.no_build)

    env = os.environ.copy()
    load_runtime_env(app_support_dir, env)
    launch_admin = resolve_launch_admin(env)
    launch_token = secrets.token_urlsafe(32)
    env["PYTHONPATH"] = f"{root / 'backend'}{os.pathsep}{env.get('PYTHONPATH', '')}".rstrip(os.pathsep)
    env["VIVENTIUM_APP_SUPPORT_DIR"] = str(app_support_dir)
    env["VIVENTIUM_PROMPT_WORKBENCH_LAUNCH_TOKEN"] = launch_token
    env["VIVENTIUM_PROMPT_WORKBENCH_ADMIN_USER_ID"] = launch_admin["userId"]
    env["VIVENTIUM_PROMPT_WORKBENCH_ADMIN_EMAIL"] = launch_admin["email"]

    command = [
        "uv",
        "run",
        *[item for dep in DEPENDENCIES for item in ("--with", dep)],
        "uvicorn",
        "--app-dir",
        str(root / "backend"),
        "prompt_workbench.app:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--no-access-log",
    ]

    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("ab", buffering=0) as handle:
        handle.write(f"\n[{utc_now()}] Starting Prompt Workbench on {app_url(port)}\n".encode("utf-8"))
        process = subprocess.Popen(
            command,
            cwd=root,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
        )

    write_state(
        app_support_dir,
        {
            "pid": process.pid,
            "port": port,
            "url": app_url(port),
            "authUrl": token_url(port, launch_token),
            "repoRoot": str(repo_root),
            "startedAt": utc_now(),
            "managedByStack": (os.environ.get("VIVENTIUM_PROMPT_WORKBENCH_MANAGED_BY_STACK") or "").strip().lower()
            in {"1", "true", "yes", "on"},
        },
    )
    clear_user_stopped_marker(app_support_dir)

    if not wait_for_health(port, timeout_seconds=args.timeout_seconds):
        raise RuntimeError(f"Prompt Workbench did not become healthy on {app_url(port)}. Check the local workbench log.")

    return {
        "status": "running",
        "started": True,
        "pid": process.pid,
        "port": port,
        "url": app_url(port),
        "authUrl": token_url(port, launch_token),
    }


def stop_pid(pid: int, timeout_seconds: int = 10) -> bool:
    if not pid_running(pid):
        return False
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    except OSError:
        os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if not pid_running(pid):
            return True
        time.sleep(0.2)
    if pid_running(pid):
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except OSError:
            os.kill(pid, signal.SIGKILL)
    return True


def stop_server(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = Path(args.repo_root).resolve()
    app_support_dir = Path(args.app_support_dir).expanduser().resolve()
    payload = read_state(app_support_dir)
    pid = int(payload.get("pid") or 0)
    root = workbench_root(repo_root)
    stopped = False
    if pid > 0 and pid_running(pid):
        if not process_matches_workbench(pid, root):
            clear_state(app_support_dir)
            mark_user_stopped(app_support_dir)
            return {
                "status": "blocked",
                "stopped": False,
                "message": "Recorded PID did not belong to this Prompt Workbench. Cleared stale workbench state; retry the action.",
            }
        stopped = stop_pid(pid)
    clear_state(app_support_dir)
    mark_user_stopped(app_support_dir)
    return {"status": "stopped", "stopped": stopped}


def open_browser(url: str) -> None:
    if sys.platform == "darwin":
        subprocess.run(["open", url], check=False)
        return
    opener = "xdg-open" if shutil_which("xdg-open") else ""
    if opener:
        subprocess.run([opener, url], check=False)


def shutil_which(binary: str) -> str | None:
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        candidate = Path(entry) / binary
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def print_payload(payload: dict[str, Any], *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(payload, sort_keys=True))
        return
    status = payload.get("status")
    url = payload.get("authUrl") or payload.get("url")
    if status == "running" and url:
        print(f"Prompt Workbench running: {url}")
    elif status == "blocked":
        print(payload.get("message") or "Prompt Workbench action blocked.", file=sys.stderr)
    else:
        print("Prompt Workbench stopped.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage the local Viventium Prompt Workbench.")
    parser.add_argument("action", choices=["start", "open", "stop", "status"])
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--app-support-dir", required=True)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-build", action="store_true", help="Use the existing dist bundle if present.")
    parser.add_argument("--timeout-seconds", type=int, default=60)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.action == "start":
            payload = start_server(args)
        elif args.action == "open":
            payload = start_server(args)
            if payload.get("authUrl") or payload.get("url"):
                open_browser(str(payload.get("authUrl") or payload["url"]))
                payload["opened"] = True
        elif args.action == "stop":
            payload = stop_server(args)
        else:
            payload = status_payload(Path(args.repo_root).resolve(), Path(args.app_support_dir).expanduser().resolve())
        print_payload(payload, json_output=args.json)
        return 0 if payload.get("status") != "blocked" else 1
    except RuntimeError as exc:
        if args.json:
            print(json.dumps({"status": "error", "message": str(exc)}, sort_keys=True), file=sys.stderr)
        else:
            print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

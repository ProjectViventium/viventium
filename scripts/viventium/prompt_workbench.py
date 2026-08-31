#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import shlex
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


DEFAULT_PORT = 8781
DEPENDENCIES = ["fastapi", "uvicorn", "PyYAML", "pydantic", "croniter"]
_LIFECYCLE_LOCKS = threading.local()
BUILD_RECEIPT_NAME = ".viventium-build-receipt.json"
BUILD_RECEIPT_SCHEMA_VERSION = 1
_IGNORED_INPUT_DIRECTORIES = frozenset(
    {"node_modules", "dist", "__pycache__", ".pytest_cache", ".vite", "tests", "__tests__"}
)
_FRONTEND_ROOT_FILES = (
    "index.html",
    "package.json",
    "package-lock.json",
    "tsconfig.json",
    "vite.config.ts",
)


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


@contextmanager
def lifecycle_lock(app_support_dir: Path) -> Iterator[None]:
    directory = state_dir(app_support_dir)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory.chmod(0o700)
    scope = str(directory.resolve())
    held = getattr(_LIFECYCLE_LOCKS, "held", None)
    if held is None:
        held = set()
        _LIFECYCLE_LOCKS.held = held
    if scope in held:
        yield
        return

    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(directory / "lifecycle.lock", flags, 0o600)
    try:
        if os.fstat(descriptor).st_uid != os.getuid():
            raise RuntimeError("Prompt Workbench lifecycle lock is owned by another user.")
        os.fchmod(descriptor, 0o600)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        held.add(scope)
        try:
            yield
        finally:
            held.remove(scope)
            fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)


def workbench_root(repo_root: Path) -> Path:
    return repo_root / "viventium_v0_4" / "prompt-workbench"


def health_url(port: int) -> str:
    return f"http://127.0.0.1:{port}/api/health"


def app_url(port: int) -> str:
    return f"http://127.0.0.1:{port}"


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
    public_state = {
        key: value
        for key, value in payload.items()
        if key not in {"authUrl", "launchToken", "workbenchToken"}
    }
    url = public_state.get("url")
    if isinstance(url, str) and url:
        parsed = urllib.parse.urlsplit(url)
        public_state["url"] = urllib.parse.urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, "", "")
        )
    directory = state_dir(app_support_dir)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory.chmod(0o700)
    path = state_path(app_support_dir)
    descriptor, temporary_path = tempfile.mkstemp(prefix=".state-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            os.fchmod(handle.fileno(), 0o600)
            handle.write(json.dumps(public_state, indent=2, sort_keys=True) + "\n")
        os.replace(temporary_path, path)
    finally:
        try:
            os.unlink(temporary_path)
        except FileNotFoundError:
            pass


def clear_state(app_support_dir: Path, *, expected: dict[str, Any] | None = None) -> bool:
    if read_state(app_support_dir) != (expected if expected is not None else {}):
        return False
    try:
        state_path(app_support_dir).unlink()
    except FileNotFoundError:
        return False
    return True


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


def listener_pids(port: int) -> list[int]:
    try:
        completed = subprocess.run(
            ["lsof", "-nP", "-t", f"-iTCP:{port}", "-sTCP:LISTEN"],
            text=True,
            capture_output=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    pids: list[int] = []
    for line in completed.stdout.splitlines():
        try:
            pid = int(line.strip())
        except ValueError:
            continue
        if pid > 0 and pid not in pids:
            pids.append(pid)
    return pids


def process_child_pids(pid: int) -> list[int]:
    try:
        completed = subprocess.run(
            ["pgrep", "-P", str(pid)],
            text=True,
            capture_output=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    children: list[int] = []
    for line in completed.stdout.splitlines():
        try:
            child_pid = int(line.strip())
        except ValueError:
            continue
        if child_pid > 0 and child_pid not in children:
            children.append(child_pid)
    return children


def process_descendant_pids(pid: int, *, limit: int = 128) -> list[int]:
    descendants: list[int] = []
    pending = [pid]
    seen = {pid}
    while pending and len(descendants) < limit:
        parent_pid = pending.pop(0)
        for child_pid in process_child_pids(parent_pid):
            if child_pid in seen:
                continue
            seen.add(child_pid)
            descendants.append(child_pid)
            pending.append(child_pid)
            if len(descendants) >= limit:
                break
    return descendants


def process_listens_on_port(pid: int, port: int) -> bool:
    try:
        completed = subprocess.run(
            [
                "lsof",
                "-nP",
                "-a",
                "-p",
                str(pid),
                f"-iTCP:{port}",
                "-sTCP:LISTEN",
            ],
            text=True,
            capture_output=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0 and bool(completed.stdout.strip())


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


def process_parent_pid(pid: int) -> int:
    try:
        completed = subprocess.run(
            ["ps", "-p", str(pid), "-o", "ppid="],
            text=True,
            capture_output=True,
            timeout=2,
            check=False,
        )
        return int(completed.stdout.strip())
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return 0


def process_uid(pid: int) -> int | None:
    try:
        completed = subprocess.run(
            ["ps", "-p", str(pid), "-o", "uid="],
            text=True,
            capture_output=True,
            timeout=2,
            check=False,
        )
        return int(completed.stdout.strip())
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None


def process_environment_value(pid: int, name: str) -> str | None:
    try:
        completed = subprocess.run(
            ["ps", "eww", "-p", str(pid), "-o", "command="],
            text=True,
            capture_output=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    match = re.search(
        r"(?:^|\s)" + re.escape(name) + r"=(.*?)(?=\s[A-Za-z_][A-Za-z0-9_]*=|$)",
        completed.stdout.rstrip("\n"),
    )
    return match.group(1) if match else None


def process_cwd(pid: int) -> Path | None:
    proc_cwd = Path(f"/proc/{pid}/cwd")
    try:
        return proc_cwd.resolve(strict=True)
    except OSError:
        pass

    try:
        completed = subprocess.run(
            ["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"],
            text=True,
            capture_output=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    for line in completed.stdout.splitlines():
        if not line.startswith("n") or len(line) <= 1:
            continue
        try:
            return Path(line[1:]).resolve(strict=True)
        except OSError:
            return None
    return None


def pid_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def process_matches_workbench(pid: int, root: Path, expected_port: int | None = None) -> bool:
    command = process_command(pid)
    if not command or "prompt_workbench.app:app" not in command:
        return False
    expected_backend = (root / "backend").resolve()

    try:
        argv = shlex.split(command)
        app_dir_index = argv.index("--app-dir")
        app_dir = Path(argv[app_dir_index + 1])
    except (ValueError, IndexError):
        return False
    if not app_dir.is_absolute():
        cwd = process_cwd(pid)
        if cwd is None:
            return False
        app_dir = cwd / app_dir
    try:
        if app_dir.resolve() != expected_backend:
            return False
    except OSError:
        return False
    if expected_port is None:
        return True
    try:
        if "--port" in argv:
            port_value = argv[argv.index("--port") + 1]
        else:
            port_value = next(item.split("=", 1)[1] for item in argv if item.startswith("--port="))
        return int(port_value) == int(expected_port)
    except (IndexError, StopIteration, ValueError):
        return False


def status_payload(repo_root: Path, app_support_dir: Path) -> dict[str, Any]:
    with lifecycle_lock(app_support_dir):
        return _status_payload_locked(repo_root, app_support_dir)


def _status_payload_locked(repo_root: Path, app_support_dir: Path) -> dict[str, Any]:
    payload = read_state(app_support_dir)
    pid = int(payload.get("pid") or 0)
    port = int(payload.get("port") or DEFAULT_PORT)
    root = workbench_root(repo_root)
    running = pid_running(pid) and process_matches_workbench(pid, root, port) and http_healthy(port)
    if not running and pid > 0 and not pid_running(pid):
        clear_state(app_support_dir, expected=payload)
    result = {
        "status": "running" if running else "stopped",
        "pid": pid if running else None,
        "port": port if running else None,
        "url": app_url(port) if running else None,
    }
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


def _is_test_source(path: Path) -> bool:
    return any(marker in path.name for marker in (".test.", ".spec."))


def _bounded_files(root: Path, *, include_backend: bool) -> list[Path]:
    candidates = [root / relative for relative in _FRONTEND_ROOT_FILES]
    search_roots = [root / "src", root / "public"]
    if include_backend:
        search_roots.append(root / "backend" / "prompt_workbench")
    for search_root in search_roots:
        if not search_root.is_dir():
            continue
        candidates.extend(
            child
            for child in search_root.rglob("*")
            if child.is_file()
            and not child.is_symlink()
            and not _IGNORED_INPUT_DIRECTORIES.intersection(child.relative_to(root).parts)
            and not _is_test_source(child)
        )
    return sorted(
        {candidate for candidate in candidates if candidate.is_file() and not candidate.is_symlink()},
        key=lambda candidate: candidate.relative_to(root).as_posix(),
    )


def _content_identity(root: Path, files: list[Path]) -> str:
    digest = hashlib.sha256()
    for candidate in files:
        relative = candidate.relative_to(root).as_posix().encode("utf-8")
        body = candidate.read_bytes()
        digest.update(relative)
        digest.update(b"\0")
        digest.update(str(len(body)).encode("ascii"))
        digest.update(b"\0")
        digest.update(body)
        digest.update(b"\0")
    return digest.hexdigest()


def frontend_input_identity(root: Path) -> str:
    return _content_identity(root, _bounded_files(root, include_backend=False))


def workbench_source_identity(root: Path) -> str:
    return _content_identity(root, _bounded_files(root, include_backend=True))


def _built_asset_identity(root: Path) -> tuple[str, int]:
    dist = root / "dist"
    files = sorted(
        (
            child
            for child in dist.rglob("*")
            if child.is_file()
            and not child.is_symlink()
            and child != dist / BUILD_RECEIPT_NAME
        ),
        key=lambda candidate: candidate.relative_to(root).as_posix(),
    )
    return _content_identity(root, files), len(files)


def build_receipt_status(root: Path) -> dict[str, Any]:
    receipt_path = root / "dist" / BUILD_RECEIPT_NAME
    receipt: dict[str, Any] = {}
    if receipt_path.is_file() and not receipt_path.is_symlink():
        try:
            parsed = json.loads(receipt_path.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                receipt = parsed
        except (json.JSONDecodeError, OSError, UnicodeError):
            pass
    try:
        current_input_hash = frontend_input_identity(root)
        current_asset_hash, current_file_count = _built_asset_identity(root)
    except OSError:
        current_input_hash = ""
        current_asset_hash = ""
        current_file_count = 0
    receipt_input_hash = receipt.get("frontendInputHash")
    receipt_asset_hash = receipt.get("builtAssetHash")
    receipt_file_count = receipt.get("builtFileCount")
    schema_version = receipt.get("schemaVersion")
    hashes_valid = all(
        isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)
        for value in (receipt_input_hash, receipt_asset_hash, current_input_hash, current_asset_hash)
    )
    counts_valid = (
        isinstance(receipt_file_count, int)
        and not isinstance(receipt_file_count, bool)
        and receipt_file_count > 0
        and current_file_count > 0
    )
    source_current = hashes_valid and receipt_input_hash == current_input_hash
    assets_current = (
        hashes_valid
        and counts_valid
        and receipt_asset_hash == current_asset_hash
        and receipt_file_count == current_file_count
    )
    receipt_available = receipt_path.is_file() and not receipt_path.is_symlink()
    receipt_valid = bool(
        receipt_available
        and schema_version == BUILD_RECEIPT_SCHEMA_VERSION
        and source_current
        and assets_current
    )
    return {
        "receiptAvailable": receipt_available,
        "schemaVersion": schema_version if isinstance(schema_version, int) else None,
        "receiptFrontendInputHash": receipt_input_hash,
        "currentFrontendInputHash": current_input_hash or None,
        "receiptBuiltAssetHash": receipt_asset_hash,
        "currentBuiltAssetHash": current_asset_hash or None,
        "receiptBuiltFileCount": receipt_file_count,
        "currentBuiltFileCount": current_file_count,
        "sourceCurrent": source_current,
        "assetsCurrent": assets_current,
        "receiptValid": receipt_valid,
    }


def write_build_receipt(root: Path) -> dict[str, Any]:
    dist = root / "dist"
    if not (dist / "index.html").is_file():
        raise RuntimeError("Prompt Workbench build did not produce dist/index.html.")
    try:
        payload = {
            "schemaVersion": BUILD_RECEIPT_SCHEMA_VERSION,
            "frontendInputHash": frontend_input_identity(root),
        }
        payload["builtAssetHash"], payload["builtFileCount"] = _built_asset_identity(root)
    except OSError as exc:
        raise RuntimeError("Prompt Workbench build receipt could not hash its inputs.") from exc
    if not payload["builtFileCount"]:
        raise RuntimeError("Prompt Workbench build receipt found no built files.")
    descriptor, temporary_path = tempfile.mkstemp(
        prefix=".build-receipt-",
        suffix=".tmp",
        dir=dist,
    )
    receipt_path = dist / BUILD_RECEIPT_NAME
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        os.replace(temporary_path, receipt_path)
    finally:
        try:
            os.unlink(temporary_path)
        except FileNotFoundError:
            pass
    status = build_receipt_status(root)
    if status["receiptValid"] is not True:
        raise RuntimeError("Prompt Workbench build receipt verification failed.")
    return status


def workbench_source_mtime(root: Path) -> float:
    return newest_mtime(_bounded_files(root, include_backend=True))


def state_source_is_stale(payload: dict[str, Any], root: Path) -> bool:
    if "sourceIdentity" in payload:
        recorded_identity = payload.get("sourceIdentity")
        return (
            not isinstance(recorded_identity, str)
            or not re.fullmatch(r"[0-9a-f]{64}", recorded_identity)
            or recorded_identity != workbench_source_identity(root)
        )
    current_source_mtime = workbench_source_mtime(root)
    try:
        recorded_source_mtime = float(payload.get("sourceMtime") or 0)
    except (TypeError, ValueError):
        recorded_source_mtime = 0
    if recorded_source_mtime > 0:
        return current_source_mtime > recorded_source_mtime

    started_at = str(payload.get("startedAt") or "").strip()
    if not started_at:
        return True
    try:
        started = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    except ValueError:
        return True
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    return current_source_mtime > started.timestamp()


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
    receipt_status = build_receipt_status(root)
    if receipt_status["receiptValid"] is True:
        return
    if skip_build:
        raise RuntimeError(
            "Prompt Workbench --no-build requires a current, verified frontend build receipt."
        )
    package_lock = root / "package-lock.json"
    node_modules = root / "node_modules"
    env = os.environ.copy()

    if not node_modules.exists():
        install_command = ["npm", "ci"] if package_lock.exists() else ["npm", "install"]
        run_logged(install_command, cwd=root, env=env, log_file=log_file)

    run_logged(["npm", "run", "build"], cwd=root, env=env, log_file=log_file)
    write_build_receipt(root)


def choose_port(app_support_dir: Path, root: Path, preferred: int) -> int:
    current = read_state(app_support_dir)
    current_port = int(current.get("port") or 0)
    current_pid = int(current.get("pid") or 0)
    if (
        current_port > 0
        and pid_running(current_pid)
        and process_matches_workbench(current_pid, root, current_port)
        and http_healthy(current_port)
    ):
        return current_port

    for port in [preferred, *range(DEFAULT_PORT, DEFAULT_PORT + 20)]:
        if port_available(port):
            return port
    raise RuntimeError("No free Prompt Workbench port found in the local range.")


def process_descends_from(pid: int, ancestor_pid: int) -> bool:
    seen: set[int] = set()
    while pid > 1 and pid not in seen:
        if pid == ancestor_pid:
            return True
        seen.add(pid)
        pid = process_parent_pid(pid)
    return False


def process_owns_workbench_listener(pid: int, root: Path, port: int) -> bool:
    if not pid_running(pid) or not process_matches_workbench(pid, root, port):
        return False
    return any(
        pid_running(candidate_pid)
        and process_matches_workbench(candidate_pid, root, port)
        and process_listens_on_port(candidate_pid, port)
        for candidate_pid in [pid, *process_descendant_pids(pid)]
    )


def wait_for_health(
    port: int,
    timeout_seconds: int,
    *,
    owner_pid: int | None = None,
    root: Path | None = None,
) -> bool:
    def owned_and_healthy() -> bool:
        if owner_pid is not None and (
            root is None or not process_owns_workbench_listener(owner_pid, root, port)
        ):
            return False
        return http_healthy(port)

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if owned_and_healthy():
            return True
        time.sleep(0.5)
    return owned_and_healthy()


def process_matches_owner_scope(pid: int, app_support_dir: Path) -> bool:
    if process_uid(pid) != os.getuid():
        return False
    configured_root = process_environment_value(pid, "VIVENTIUM_APP_SUPPORT_DIR")
    if not configured_root:
        return False
    try:
        if Path(configured_root).expanduser().resolve() != app_support_dir.resolve():
            return False
    except OSError:
        return False
    process_is_dev = (
        process_environment_value(pid, "VIVENTIUM_DEV_ENV_SCOPE_ACTIVE") or ""
    ).strip().lower() in {"1", "true", "yes", "on"}
    current_is_dev = (os.environ.get("VIVENTIUM_DEV_ENV_SCOPE_ACTIVE") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    return process_is_dev == current_is_dev


def recover_owned_workbench_state(
    repo_root: Path,
    app_support_dir: Path,
    port: int,
    *,
    managed_by_stack: bool,
) -> dict[str, Any]:
    if read_state(app_support_dir):
        return {}
    listeners = listener_pids(port)
    if len(listeners) != 1:
        return {}
    listener_pid = listeners[0]
    root = workbench_root(repo_root)
    if (
        not pid_running(listener_pid)
        or not process_matches_workbench(listener_pid, root, port)
        or not process_matches_owner_scope(listener_pid, app_support_dir)
    ):
        return {}

    owner_pid = listener_pid
    seen = {listener_pid}
    while True:
        parent_pid = process_parent_pid(owner_pid)
        if parent_pid <= 1 or parent_pid in seen:
            break
        if not process_matches_workbench(parent_pid, root, port):
            break
        if not pid_running(parent_pid) or not process_matches_owner_scope(parent_pid, app_support_dir):
            return {}
        seen.add(parent_pid)
        owner_pid = parent_pid

    if not process_owns_workbench_listener(owner_pid, root, port) or not http_healthy(port):
        return {}
    previously_managed = (
        process_environment_value(owner_pid, "VIVENTIUM_PROMPT_WORKBENCH_MANAGED_BY_STACK") or ""
    ).strip().lower() in {"1", "true", "yes", "on"}
    payload = {
        "pid": owner_pid,
        "port": port,
        "url": app_url(port),
        "repoRoot": str(repo_root),
        "startedAt": utc_now(),
        "sourceMtime": workbench_source_mtime(root),
        "sourceIdentity": None,
        "managedByStack": managed_by_stack or previously_managed,
    }
    write_state(app_support_dir, payload)
    return payload


def current_workbench_requires_restart(
    current_state: dict[str, Any],
    current: dict[str, Any],
    root: Path,
    *,
    managed_by_stack: bool,
    preferred_port: int,
) -> bool:
    if current.get("status") != "running":
        return False
    if managed_by_stack and int(current.get("port") or 0) != preferred_port:
        return True
    return state_source_is_stale(current_state, root)


def start_server(args: argparse.Namespace) -> dict[str, Any]:
    app_support_dir = Path(args.app_support_dir).expanduser().resolve()
    with lifecycle_lock(app_support_dir):
        return _start_server_locked(args)


def _start_server_locked(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = Path(args.repo_root).resolve()
    app_support_dir = Path(args.app_support_dir).expanduser().resolve()
    root = workbench_root(repo_root)
    ensure_workbench_exists(root)

    selected_runtime_env: dict[str, str] = {}
    load_runtime_env(app_support_dir, selected_runtime_env)
    preferred_port = int(
        args.port
        or selected_runtime_env.get("VIVENTIUM_PROMPT_WORKBENCH_PORT")
        or os.environ.get("VIVENTIUM_PROMPT_WORKBENCH_PORT")
        or DEFAULT_PORT
    )
    managed_by_stack = (os.environ.get("VIVENTIUM_PROMPT_WORKBENCH_MANAGED_BY_STACK") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    current_state = read_state(app_support_dir)
    current = status_payload(repo_root, app_support_dir)
    if (
        managed_by_stack
        and current["status"] != "running"
        and not read_state(app_support_dir)
        and not port_available(preferred_port)
    ):
        recovered_state = recover_owned_workbench_state(
            repo_root,
            app_support_dir,
            preferred_port,
            managed_by_stack=managed_by_stack,
        )
        if recovered_state:
            current_state = recovered_state
            current = status_payload(repo_root, app_support_dir)
    restarted_stale = False
    if current["status"] == "running":
        if not current_workbench_requires_restart(
            current_state,
            current,
            root,
            managed_by_stack=managed_by_stack,
            preferred_port=preferred_port,
        ):
            if managed_by_stack and not current_state.get("managedByStack"):
                current_state = {**current_state, "managedByStack": True}
                current = {**current, "managedByStack": True}
            write_state(app_support_dir, current_state)
            existing_log = log_path(app_support_dir)
            if existing_log.is_file():
                existing_log.chmod(0o600)
            clear_user_stopped_marker(app_support_dir)
            return {**current, "started": False, "sourceStale": False}
        current_pid = int(current.get("pid") or 0)
        current_port = int(current.get("port") or 0)
        if (
            current_pid <= 0
            or not process_matches_workbench(current_pid, root, current_port)
            or not process_matches_owner_scope(current_pid, app_support_dir)
        ):
            raise RuntimeError(
                "Prompt Workbench needs restart, but the recorded listener is not owned by this runtime."
            )
        stop_pid(current_pid)
        if not clear_state(app_support_dir, expected=current_state) and read_state(app_support_dir):
            raise RuntimeError("Prompt Workbench owner changed while its stale process was stopping.")
        restarted_stale = True

    if managed_by_stack:
        reclaim_stale_managed_workbench_port(preferred_port, root, app_support_dir)
        if not port_available(preferred_port):
            raise RuntimeError(
                f"Managed Prompt Workbench port {preferred_port} is owned by another runtime or listener."
            )
        port = preferred_port
    else:
        port = choose_port(app_support_dir, root, preferred_port)
    log_file = log_path(app_support_dir)
    ensure_assets_built(root, log_file, skip_build=args.no_build)

    env = os.environ.copy()
    load_runtime_env(app_support_dir, env)
    env["VIVENTIUM_PROMPT_WORKBENCH_PORT"] = str(port)
    env.pop("VIVENTIUM_PROMPT_WORKBENCH_LAUNCH_TOKEN", None)
    launch_admin = resolve_launch_admin(env)
    env["PYTHONPATH"] = f"{root / 'backend'}{os.pathsep}{env.get('PYTHONPATH', '')}".rstrip(os.pathsep)
    env["VIVENTIUM_APP_SUPPORT_DIR"] = str(app_support_dir)
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
    launch_source_identity = workbench_source_identity(root)

    log_file.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(log_file, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(descriptor, "ab", buffering=0) as handle:
        os.fchmod(handle.fileno(), 0o600)
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

    if not wait_for_health(
        port,
        timeout_seconds=args.timeout_seconds,
        owner_pid=process.pid,
        root=root,
    ):
        if pid_running(process.pid) and process_matches_workbench(process.pid, root, port):
            stop_pid(process.pid)
        raise RuntimeError(f"Prompt Workbench did not become healthy on {app_url(port)}. Check the local workbench log.")

    write_state(
        app_support_dir,
        {
            "pid": process.pid,
            "port": port,
            "url": app_url(port),
            "repoRoot": str(repo_root),
            "startedAt": utc_now(),
            "sourceMtime": workbench_source_mtime(root),
            "sourceIdentity": launch_source_identity,
            "managedByStack": managed_by_stack,
        },
    )
    clear_user_stopped_marker(app_support_dir)

    return {
        "status": "running",
        "started": True,
        "pid": process.pid,
        "port": port,
        "url": app_url(port),
        "managedByStack": managed_by_stack,
        "restartedStale": restarted_stale,
        "sourceStale": False,
    }


def stop_pid(pid: int, timeout_seconds: int = 10) -> bool:
    if not pid_running(pid):
        return False
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    except OSError:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if not pid_running(pid):
            return True
        time.sleep(0.2)
    if pid_running(pid):
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except OSError:
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
    return True


def reclaim_stale_managed_workbench_port(port: int, root: Path, app_support_dir: Path) -> bool:
    if port_available(port):
        return False

    state = read_state(app_support_dir)
    recorded_pid = int(state.get("pid") or 0)
    recorded_port = int(state.get("port") or 0)
    if recorded_pid <= 0 or recorded_port != port:
        return False

    reclaimed = False
    for pid in listener_pids(port):
        if (
            pid != recorded_pid
            or not process_matches_workbench(pid, root, port)
            or not process_matches_owner_scope(pid, app_support_dir)
        ):
            continue
        # Current App Support state, exact PID, source checkout, and port must all agree.
        reclaimed = stop_pid(pid) or reclaimed

    if not reclaimed:
        return False

    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        if port_available(port):
            return True
        time.sleep(0.05)
    return port_available(port)


def stop_server(args: argparse.Namespace) -> dict[str, Any]:
    app_support_dir = Path(args.app_support_dir).expanduser().resolve()
    with lifecycle_lock(app_support_dir):
        return _stop_server_locked(args)


def _stop_server_locked(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = Path(args.repo_root).resolve()
    app_support_dir = Path(args.app_support_dir).expanduser().resolve()
    payload = read_state(app_support_dir)
    pid = int(payload.get("pid") or 0)
    root = workbench_root(repo_root)
    stopped = False
    if pid > 0 and pid_running(pid):
        port = int(payload.get("port") or DEFAULT_PORT)
        if not process_matches_workbench(pid, root, port) or not process_matches_owner_scope(
            pid,
            app_support_dir,
        ):
            clear_state(app_support_dir, expected=payload)
            mark_user_stopped(app_support_dir)
            return {
                "status": "blocked",
                "stopped": False,
                "message": "Recorded PID did not belong to this Prompt Workbench. Cleared stale workbench state; retry the action.",
            }
        stopped = stop_pid(pid)
    if payload:
        clear_state(app_support_dir, expected=payload)
    else:
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
    public_payload = {key: value for key, value in payload.items() if key != "authUrl"}
    if json_output:
        print(json.dumps(public_payload, sort_keys=True))
        return
    status = public_payload.get("status")
    url = public_payload.get("url")
    if status == "running" and url:
        print(f"Prompt Workbench running: {url}")
    elif status == "blocked":
        print(public_payload.get("message") or "Prompt Workbench action blocked.", file=sys.stderr)
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
            if payload.get("url"):
                open_browser(str(payload["url"]))
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

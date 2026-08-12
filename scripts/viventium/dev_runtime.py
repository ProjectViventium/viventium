#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except Exception as exc:  # pragma: no cover - release env always carries PyYAML today
    raise SystemExit("dev-env requires PyYAML; run bin/viventium preflight --apply first") from exc


APP_FACING_PORT_KEYS = (
    "lc_api_port",
    "lc_frontend_port",
    "sandpack_bundler_port",
    "playground_port",
    "prompt_workbench_port",
    "voice_gateway_health_port",
)

APP_FACING_PORT_DEFAULTS = {
    "isolated": {
        "lc_api_port": 3180,
        "lc_frontend_port": 3190,
        "sandpack_bundler_port": 3191,
        "playground_port": 3300,
        "prompt_workbench_port": 8781,
        "voice_gateway_health_port": 8301,
    },
    "compat": {
        "lc_api_port": 3080,
        "lc_frontend_port": 3090,
        "sandpack_bundler_port": 3091,
        "playground_port": 3000,
        "prompt_workbench_port": 8781,
        "voice_gateway_health_port": 8300,
    },
}

RUNTIME_OWNED_PORT_DEFAULTS = {
    "isolated": {
        "mongo_port": 27117,
        "meili_port": 7700,
        "livekit_http_port": 7888,
        "livekit_tcp_port": 7889,
        "livekit_udp_port": 7890,
    },
    "compat": {
        "mongo_port": 27017,
        "meili_port": 7701,
        "livekit_http_port": 7880,
        "livekit_tcp_port": 7881,
        "livekit_udp_port": 7882,
    },
}

SCHEDULING_MCP_PORT_DEFAULTS = {
    "isolated": 7110,
    "compat": 7010,
}
SCHEDULING_MCP_PORT_OFFSET_BIAS = 100

SHARED_SINGLETON_SERVICES = (
    "recall_rag",
    "searxng",
    "firecrawl",
    "google_workspace_mcp",
    "ms365_mcp",
)

DEV_RESOURCE_ENV = {
    "OPENBLAS_NUM_THREADS": "1",
    "OMP_NUM_THREADS": "4",
    "MKL_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "4",
    "NUMEXPR_MAX_THREADS": "4",
    "RAYON_NUM_THREADS": "4",
    "TOKENIZERS_PARALLELISM": "false",
    "VIVENTIUM_DEV_RESOURCE_GUARD": "v1",
    "VIVENTIUM_DETACHED_START": "0",
}
DEV_RESOURCE_GUARD_EXIT = 86
DEV_RESOURCE_GUARD_FAILURE_EXIT = 87
DEV_RESOURCE_GUARD_POLL_SECONDS = 0.25
DEV_RESOURCE_GUARD_STOP_SECONDS = 5.0


class GuardSignalInterrupt(Exception):
    def __init__(self, signum: int) -> None:
        super().__init__(signum)
        self.signum = signum


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_name(value: str) -> str:
    name = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in value.strip().lower())
    name = "-".join(part for part in name.split("-") if part)
    if not name:
        raise SystemExit("dev-env name must contain at least one letter or number")
    return name[:64]


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"Missing config: {path}")
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, dict):
        raise SystemExit(f"Config must be a mapping: {path}")
    return payload


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    path.chmod(0o600)


def env_root(app_support_dir: Path) -> Path:
    return app_support_dir / "dev-envs"


def env_dir(app_support_dir: Path, name: str) -> Path:
    return env_root(app_support_dir) / safe_name(name)


def state_file(path: Path) -> Path:
    return path / "state" / "dev-env.json"


def create_env(args: argparse.Namespace) -> int:
    base_config_path = Path(args.config_file).expanduser().resolve()
    app_support_dir = Path(args.app_support_dir).expanduser().resolve()
    target_dir = env_dir(app_support_dir, args.name)
    target_config = target_dir / "config.yaml"

    if target_config.exists() and not args.replace:
        raise SystemExit(f"Dev env already exists: {target_dir}")

    config = deepcopy(load_yaml(base_config_path))
    runtime = config.setdefault("runtime", {})
    if not isinstance(runtime, dict):
        raise SystemExit("runtime must be a mapping in config.yaml")
    ports = runtime.setdefault("ports", {})
    if not isinstance(ports, dict):
        raise SystemExit("runtime.ports must be a mapping in config.yaml")

    offset = int(args.port_offset)
    runtime_profile = str(runtime.get("profile") or "isolated").strip().lower()
    app_facing_defaults = APP_FACING_PORT_DEFAULTS.get(
        runtime_profile,
        APP_FACING_PORT_DEFAULTS["isolated"],
    )
    for key in APP_FACING_PORT_KEYS:
        ports[key] = int(ports.get(key, app_facing_defaults[key])) + offset
    runtime_owned_defaults = RUNTIME_OWNED_PORT_DEFAULTS.get(
        runtime_profile,
        RUNTIME_OWNED_PORT_DEFAULTS["isolated"],
    )
    for key, default_port in runtime_owned_defaults.items():
        ports[key] = int(ports.get(key, default_port)) + offset
    scheduling_base = ports.get("scheduling_mcp_port")
    if scheduling_base in (None, ""):
        scheduling_base = SCHEDULING_MCP_PORT_DEFAULTS.get(runtime_profile, 7110)
    ports["scheduling_mcp_port"] = int(scheduling_base) + offset + SCHEDULING_MCP_PORT_OFFSET_BIAS

    dev_env = runtime.setdefault("dev_env", {})
    if not isinstance(dev_env, dict):
        raise SystemExit("runtime.dev_env must be a mapping when present")
    dev_env.update(
        {
            "enabled": True,
            "name": safe_name(args.name),
            "source_app_support_dir": str(app_support_dir),
            "port_offset": offset,
            "shared_singleton_services": list(SHARED_SINGLETON_SERVICES),
        }
    )

    write_yaml(target_config, config)
    (target_dir / "runtime").mkdir(parents=True, exist_ok=True)
    (target_dir / "state").mkdir(parents=True, exist_ok=True)
    (target_dir / "logs").mkdir(parents=True, exist_ok=True)
    state = {
        "name": safe_name(args.name),
        "created_at": utc_now(),
        "repo_root": str(Path(args.repo_root).expanduser().resolve()),
        "app_support_dir": str(target_dir),
        "config_file": str(target_config),
        "runtime_dir": str(target_dir / "runtime"),
        "shared_singleton_services": list(SHARED_SINGLETON_SERVICES),
        "app_facing_port_offset": offset,
    }
    state_file(target_dir).write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Created dev env '{state['name']}' at {target_dir}")
    print("Shared singleton services are not duplicated by default.")
    return 0


def list_envs(args: argparse.Namespace) -> int:
    root = env_root(Path(args.app_support_dir).expanduser().resolve())
    items: list[dict[str, Any]] = []
    if root.exists():
        for path in sorted(root.iterdir()):
            marker = state_file(path)
            if not marker.exists():
                continue
            try:
                items.append(json.loads(marker.read_text(encoding="utf-8")))
            except Exception:
                items.append({"name": path.name, "app_support_dir": str(path), "status": "invalid"})
    if args.json:
        print(json.dumps({"items": items}, indent=2, sort_keys=True))
    elif items:
        for item in items:
            print(f"{item.get('name')}: {item.get('app_support_dir')}")
    else:
        print("No dev envs found.")
    return 0


def status_env(args: argparse.Namespace) -> int:
    target = env_dir(Path(args.app_support_dir).expanduser().resolve(), args.name)
    marker = state_file(target)
    if not marker.exists():
        raise SystemExit(f"Unknown dev env: {args.name}")
    payload = json.loads(marker.read_text(encoding="utf-8"))
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"Dev env: {payload['name']}")
        print(f"App Support: {payload['app_support_dir']}")
        print(f"Runtime: {payload['runtime_dir']}")
        print("Shared singleton services: " + ", ".join(payload["shared_singleton_services"]))
    return 0


def bounded_guard_limit(
    env: dict[str, str], key: str, *, default: int, minimum: int, maximum: int
) -> int:
    try:
        value = int(env.get(key, ""))
    except (TypeError, ValueError):
        value = default
    return min(max(value, minimum), maximum)


def process_thread_snapshot(root_pid: int) -> dict[int, tuple[int, int]] | None:
    if sys.platform == "darwin":
        command = ["/bin/ps", "-axo", "pid=,ppid=,pgid=,comm="]
    elif sys.platform.startswith("linux"):
        command = [
            "/bin/ps",
            "-e",
            "-o",
            "pid=",
            "-o",
            "ppid=",
            "-o",
            "pgid=",
            "-o",
            "nlwp=",
            "-o",
            "comm=",
        ]
    else:
        return None
    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    snapshot: dict[int, tuple[int, int]] = {}
    commands: dict[int, str] = {}
    reported_threads: dict[int, int] = {}
    for line in completed.stdout.splitlines():
        expected_fields = 4 if sys.platform == "darwin" else 5
        fields = line.split(maxsplit=expected_fields - 1)
        if len(fields) != expected_fields:
            continue
        try:
            pid = int(fields[0])
            parent_pid = int(fields[1])
            process_group_id = int(fields[2])
        except ValueError:
            continue
        if process_group_id != root_pid:
            continue
        snapshot[pid] = (parent_pid, 0)
        commands[pid] = fields[-1].lower()
        if sys.platform != "darwin":
            try:
                reported_threads[pid] = int(fields[3])
            except ValueError:
                reported_threads[pid] = 0

    for pid in snapshot:
        if "python" not in commands.get(pid, ""):
            continue
        parent_pid = snapshot[pid][0]
        if sys.platform != "darwin":
            snapshot[pid] = (parent_pid, max(reported_threads.get(pid, 0), 0))
            continue
        try:
            thread_rows = subprocess.run(
                ["/bin/ps", "-M", "-p", str(pid)],
                check=True,
                capture_output=True,
                text=True,
                timeout=2,
            ).stdout.splitlines()
        except (OSError, subprocess.SubprocessError):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                continue
            except OSError:
                return None
            return None
        threads = max(len([row for row in thread_rows[1:] if row.strip()]), 1)
        snapshot[pid] = (parent_pid, threads)
    return snapshot


def stop_process_group(
    process: subprocess.Popen[Any],
    first_signal: int,
    *,
    drain_seconds: float | None = DEV_RESOURCE_GUARD_STOP_SECONDS,
) -> None:
    try:
        os.killpg(process.pid, first_signal)
    except ProcessLookupError:
        return
    if drain_seconds is None:
        while process.poll() is None:
            try:
                process.wait(timeout=0.25)
            except subprocess.TimeoutExpired:
                continue
        return
    deadline = time.monotonic() + drain_seconds
    while process.poll() is None and time.monotonic() < deadline:
        time.sleep(0.05)
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=DEV_RESOURCE_GUARD_STOP_SECONDS)
    except subprocess.TimeoutExpired:
        pass


def run_resource_guarded(exec_args: list[str], env: dict[str, str]) -> int:
    process_limit = bounded_guard_limit(
        env,
        "VIVENTIUM_DEV_RESOURCE_GUARD_MAX_PROCESS_THREADS",
        default=512,
        minimum=4,
        maximum=512,
    )
    tree_limit = bounded_guard_limit(
        env,
        "VIVENTIUM_DEV_RESOURCE_GUARD_MAX_TREE_THREADS",
        default=2048,
        minimum=process_limit,
        maximum=2048,
    )
    process: subprocess.Popen[Any] | None = None
    managed_signals = [signal.SIGTERM]
    if hasattr(signal, "SIGHUP"):
        managed_signals.append(signal.SIGHUP)
    previous_handlers = {signum: signal.getsignal(signum) for signum in managed_signals}

    def interrupt_guard(signum: int, _frame: Any) -> None:
        raise GuardSignalInterrupt(signum)

    for signum in managed_signals:
        signal.signal(signum, interrupt_guard)
    try:
        process = subprocess.Popen(exec_args, env=env, start_new_session=True)
        while process.poll() is None:
            snapshot = process_thread_snapshot(process.pid)
            if snapshot is None:
                print(
                    "Viventium resource guard could not inspect the dev process tree; stopping it safely.",
                    file=sys.stderr,
                )
                stop_process_group(process, signal.SIGTERM)
                return DEV_RESOURCE_GUARD_FAILURE_EXIT
            counts = {pid: threads for pid, (_parent_pid, threads) in snapshot.items()}
            over_limit = [(pid, count) for pid, count in counts.items() if count > process_limit]
            total_threads = sum(counts.values())
            if over_limit or total_threads > tree_limit:
                detail = (
                    f"process {over_limit[0][0]} reached {over_limit[0][1]} threads"
                    if over_limit
                    else f"process tree reached {total_threads} threads"
                )
                print(
                    "Viventium resource guard stopped the dev env before its thread budget "
                    f"was exhausted ({detail}).",
                    file=sys.stderr,
                )
                stop_process_group(process, signal.SIGTERM)
                return DEV_RESOURCE_GUARD_EXIT
            time.sleep(DEV_RESOURCE_GUARD_POLL_SECONDS)
    except GuardSignalInterrupt as exc:
        if process is not None:
            stop_process_group(process, exc.signum, drain_seconds=None)
        return 128 + exc.signum
    except KeyboardInterrupt:
        if process is not None:
            stop_process_group(process, signal.SIGINT, drain_seconds=None)
        return 130
    finally:
        for signum, previous_handler in previous_handlers.items():
            signal.signal(signum, previous_handler)
    return int(process.returncode or 0) if process is not None else 1


def run_in_env(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).expanduser().resolve()
    target = env_dir(Path(args.app_support_dir).expanduser().resolve(), args.name)
    marker = state_file(target)
    if not marker.exists():
        raise SystemExit(f"Unknown dev env: {args.name}")
    payload = json.loads(marker.read_text(encoding="utf-8"))
    command = args.command or ["status"]
    env = os.environ.copy()
    env["VIVENTIUM_DEV_ENV_NAME"] = payload["name"]
    # This wrapper-owned identity is available even before the dev env has ever compiled.
    # Stop logic must fail closed to runtime-scoped ownership instead of trusting a generated
    # runtime.env that may be absent or stale.
    env["VIVENTIUM_DEV_ENV_SCOPE_ACTIVE"] = "true"
    env["VIVENTIUM_DEV_ENV_INSTANCE_ID"] = payload["name"]
    env["VIVENTIUM_SHARED_SINGLETON_SERVICES"] = ",".join(payload["shared_singleton_services"])
    env["VIVENTIUM_RUNTIME_TOOLS_DIR"] = str(
        Path(args.app_support_dir).expanduser().resolve() / "runtime-tools"
    )
    env.update(DEV_RESOURCE_ENV)
    exec_args = [
        str(repo_root / "bin" / "viventium"),
        "--app-support-dir",
        payload["app_support_dir"],
        "--config-file",
        payload["config_file"],
        "--runtime-dir",
        payload["runtime_dir"],
        *command,
    ]
    return run_resource_guarded(exec_args, env)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bin/viventium dev-env")
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--app-support-dir", required=True)
    parser.add_argument("--config-file", required=True)
    sub = parser.add_subparsers(dest="command_name", required=True)

    create = sub.add_parser("create")
    create.add_argument("name")
    create.add_argument("--port-offset", type=int, default=1000)
    create.add_argument("--replace", action="store_true")
    create.set_defaults(func=create_env)

    list_cmd = sub.add_parser("list")
    list_cmd.add_argument("--json", action="store_true")
    list_cmd.set_defaults(func=list_envs)

    status = sub.add_parser("status")
    status.add_argument("name")
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=status_env)

    run = sub.add_parser("run")
    run.add_argument("name")
    run.add_argument("command", nargs=argparse.REMAINDER)
    run.set_defaults(func=run_in_env)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())

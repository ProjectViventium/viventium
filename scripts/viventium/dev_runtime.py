#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
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
    "voice_gateway_health_port",
)

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
    if "sandpack_bundler_port" not in ports:
        ports["sandpack_bundler_port"] = 3191 if runtime_profile == "isolated" else 3091
    for key in APP_FACING_PORT_KEYS:
        if key in ports:
            ports[key] = int(ports[key]) + offset
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
    env["VIVENTIUM_SHARED_SINGLETON_SERVICES"] = ",".join(payload["shared_singleton_services"])
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
    return subprocess.call(exec_args, env=env)


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

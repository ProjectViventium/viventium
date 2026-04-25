#!/usr/bin/env python3
"""Local operator wrapper for Viventium saved-memory hardening."""

from __future__ import annotations

import argparse
import json
import os
import plistlib
import shlex
import subprocess
import sys
from pathlib import Path


DEFAULT_SCHEDULE = "0 5 * * *"
DEFAULT_TIMEZONE = "America/Toronto"
LAUNCH_AGENT_LABEL = "ai.viventium.memory-harden"


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def load_runtime_env(runtime_dir: Path, librechat_dir: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for candidate in (
        runtime_dir / "runtime.env",
        runtime_dir / "local.env",
        runtime_dir / "librechat.env",
        librechat_dir / ".env",
    ):
        env.update(parse_env_file(candidate))
    return env


def cron_to_launchd_time(schedule: str) -> tuple[int, int]:
    parts = schedule.split()
    if len(parts) != 5:
        raise SystemExit("memory hardening LaunchAgent currently expects a 5-field cron schedule")
    minute, hour, day, month, weekday = parts
    if day != "*" or month != "*" or weekday != "*":
        raise SystemExit("memory hardening LaunchAgent currently supports daily schedules only")
    try:
        hour_i = int(hour)
        minute_i = int(minute)
    except ValueError as exc:
        raise SystemExit(f"Invalid daily schedule: {schedule}") from exc
    if not 0 <= hour_i <= 23 or not 0 <= minute_i <= 59:
        raise SystemExit(f"Invalid daily schedule: {schedule}")
    return hour_i, minute_i


def launch_agent_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist"


def install_schedule(args: argparse.Namespace, runtime_env: dict[str, str]) -> dict[str, object]:
    if sys.platform != "darwin":
        raise SystemExit("install-schedule currently supports macOS LaunchAgents. Use cron/systemd on Linux.")
    schedule = args.schedule or runtime_env.get("VIVENTIUM_MEMORY_HARDENING_SCHEDULE") or DEFAULT_SCHEDULE
    hour, minute = cron_to_launchd_time(schedule)
    plist_path = launch_agent_path()
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    command = f"{shlex.quote(str(args.repo_root / 'bin' / 'viventium'))} memory-harden apply --scheduled"
    if args.user_email:
        command += f" --user-email {shlex.quote(args.user_email)}"
    payload = {
        "Label": LAUNCH_AGENT_LABEL,
        "ProgramArguments": ["/bin/bash", "-lc", command],
        "StartCalendarInterval": {"Hour": hour, "Minute": minute},
        "StandardOutPath": str(args.app_support_dir / "logs" / "memory-hardening.log"),
        "StandardErrorPath": str(args.app_support_dir / "logs" / "memory-hardening.err.log"),
        "WorkingDirectory": str(args.repo_root),
        "RunAtLoad": False,
    }
    with plist_path.open("wb") as handle:
        plistlib.dump(payload, handle)
    subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}", str(plist_path)], check=False)
    subprocess.run(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(plist_path)], check=False)
    return {"installed": True, "label": LAUNCH_AGENT_LABEL, "schedule": schedule, "plist": str(plist_path)}


def uninstall_schedule() -> dict[str, object]:
    plist_path = launch_agent_path()
    subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}", str(plist_path)], check=False)
    if plist_path.exists():
        plist_path.unlink()
    return {"installed": False, "label": LAUNCH_AGENT_LABEL, "plist": str(plist_path)}


def node_command(args: argparse.Namespace, runtime_env: dict[str, str]) -> list[str]:
    script = args.repo_root / "viventium_v0_4" / "LibreChat" / "scripts" / "viventium-memory-hardening.js"
    command = [
        "node",
        str(script),
        "--mode",
        args.command,
        "--app-support-dir",
        str(args.app_support_dir),
    ]
    mongo_uri = args.mongo_uri or runtime_env.get("MONGO_URI")
    config_path = (
        args.config_path
        or runtime_env.get("CONFIG_PATH")
        or runtime_env.get("VIVENTIUM_CONFIG_PATH")
        or str(args.runtime_dir / "librechat.yaml")
    )
    if mongo_uri:
        command.extend(["--mongo-uri", mongo_uri])
    if config_path:
        command.extend(["--config-path", config_path])
    if args.run_id:
        command.extend(["--run-id", args.run_id])
    if args.user_email:
        command.extend(["--user-email", args.user_email])
    if args.user_id:
        command.extend(["--user-id", args.user_id])
    if args.lookback_days is not None:
        command.extend(["--lookback-days", str(args.lookback_days)])
    if args.min_user_idle_minutes is not None:
        command.extend(["--min-user-idle-minutes", str(args.min_user_idle_minutes)])
    if args.max_changes_per_user is not None:
        command.extend(["--max-changes-per-user", str(args.max_changes_per_user)])
    if args.provider:
        command.extend(["--provider", args.provider])
    if args.model:
        command.extend(["--model", args.model])
    if args.proposal_file:
        command.extend(["--proposal-file", args.proposal_file])
    if args.allow_delete:
        command.append("--allow-delete")
    if args.ignore_idle_gate:
        command.append("--ignore-idle-gate")
    if args.skip_model_probe:
        command.append("--skip-model-probe")
    if args.json:
        command.append("--json")
    return command


def run_node(args: argparse.Namespace, runtime_env: dict[str, str]) -> int:
    env = os.environ.copy()
    env.update(runtime_env)
    env["VIVENTIUM_APP_SUPPORT_DIR"] = str(args.app_support_dir)
    env.setdefault("VIVENTIUM_MEMORY_HARDENING_SCHEDULE", DEFAULT_SCHEDULE)
    env.setdefault("VIVENTIUM_MEMORY_HARDENING_TIMEZONE", DEFAULT_TIMEZONE)
    if (
        args.command == "apply"
        and getattr(args, "scheduled", False)
        and env.get("VIVENTIUM_MEMORY_HARDENING_DRY_RUN_FIRST", "true").lower()
        in {"1", "true", "yes", "on"}
    ):
        marker = args.app_support_dir / "state" / "memory-hardening" / "dry-run-first-complete"
        if not marker.exists():
            args.command = "dry-run"
            result = subprocess.run(
                node_command(args, runtime_env),
                cwd=args.repo_root / "viventium_v0_4" / "LibreChat",
                env=env,
                text=True,
            )
            if result.returncode == 0:
                marker.parent.mkdir(parents=True, exist_ok=True)
                marker.write_text("completed\n", encoding="utf-8")
            return int(result.returncode)
    command = node_command(args, runtime_env)
    process = subprocess.run(
        command,
        cwd=args.repo_root / "viventium_v0_4" / "LibreChat",
        env=env,
        text=True,
    )
    return int(process.returncode)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run local Viventium saved-memory hardening.")
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--app-support-dir", type=Path, required=True)
    parser.add_argument("--runtime-dir", type=Path, required=True)
    parser.add_argument("--mongo-uri")
    parser.add_argument("--config-path")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("dry-run", "apply", "rollback", "status"):
        sub = subparsers.add_parser(name)
        sub.add_argument("--run-id")
        sub.add_argument("--user-email")
        sub.add_argument("--user-id")
        sub.add_argument("--lookback-days", type=int)
        sub.add_argument("--min-user-idle-minutes", type=int)
        sub.add_argument("--max-changes-per-user", type=int)
        sub.add_argument("--provider")
        sub.add_argument("--model")
        sub.add_argument("--proposal-file")
        sub.add_argument("--allow-delete", action="store_true")
        sub.add_argument("--ignore-idle-gate", action="store_true")
        sub.add_argument("--skip-model-probe", action="store_true")
        sub.add_argument("--scheduled", action="store_true")
        sub.add_argument("--json", action="store_true")
    install = subparsers.add_parser("install-schedule")
    install.add_argument("--schedule")
    install.add_argument("--user-email")
    install.add_argument("--json", action="store_true")
    uninstall = subparsers.add_parser("uninstall-schedule")
    uninstall.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.repo_root = args.repo_root.resolve()
    args.app_support_dir = args.app_support_dir.expanduser().resolve()
    args.runtime_dir = args.runtime_dir.expanduser().resolve()
    librechat_dir = args.repo_root / "viventium_v0_4" / "LibreChat"
    runtime_env = load_runtime_env(args.runtime_dir, librechat_dir)
    (args.app_support_dir / "logs").mkdir(parents=True, exist_ok=True)

    if args.command == "install-schedule":
        result = install_schedule(args, runtime_env)
        print(json.dumps(result, indent=2))
        return 0
    if args.command == "uninstall-schedule":
        result = uninstall_schedule()
        print(json.dumps(result, indent=2))
        return 0
    return run_node(args, runtime_env)


if __name__ == "__main__":
    raise SystemExit(main())

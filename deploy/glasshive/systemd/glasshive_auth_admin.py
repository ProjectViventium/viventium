#!/usr/bin/python3
"""Run the GlassHive identity admin CLI through the hosted gateway boundary."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import stat
import subprocess
import sys
from typing import Sequence


SYSTEMD_RUN = Path("/usr/bin/systemd-run")
GATEWAY_ENV = Path("/etc/viventium/glasshive/gateway.env")
GATEWAY_ACTIVE_ENV = Path("/etc/viventium/glasshive/gateway-active.env")
MUTATION_LOCK = Path("/run/lock/glasshive-rollout.lock")


class AdminBusyError(RuntimeError):
    pass


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run an admin-only GlassHive identity operation as the hosted gateway"
    )
    parser.add_argument("command", choices=("preapprove-oidc",))
    parser.add_argument("--stdin-json", action="store_true", required=True)
    return parser


def _release_paths(script_path: Path) -> tuple[Path, Path]:
    resolved_script = script_path.resolve(strict=True)
    release_root = resolved_script.parents[3]
    manifest = release_root / "glasshive-release.json"
    working_directory = (
        release_root / "viventium_v0_4/GlassHive/frontends/glass-drive-ui"
    )
    python_path = working_directory / ".venv/bin/python"
    if not manifest.is_file():
        raise RuntimeError("The active GlassHive release manifest is unavailable")
    if not working_directory.is_dir() or not python_path.is_file() or not os.access(python_path, os.X_OK):
        raise RuntimeError("The active GlassHive gateway interpreter is unavailable")
    return working_directory, python_path


def _systemd_command(*, script_path: Path = Path(__file__)) -> list[str]:
    if not SYSTEMD_RUN.is_file() or not os.access(SYSTEMD_RUN, os.X_OK):
        raise RuntimeError("systemd-run is unavailable")
    for environment_file in (GATEWAY_ENV, GATEWAY_ACTIVE_ENV):
        if not environment_file.is_file():
            raise RuntimeError("The reviewed GlassHive gateway environment is unavailable")
    working_directory, python_path = _release_paths(script_path)
    return [
        str(SYSTEMD_RUN),
        "--quiet",
        "--wait",
        "--collect",
        "--pipe",
        "--service-type=exec",
        "--uid=glasshive-gateway",
        "--gid=glasshive-state",
        "--property=SupplementaryGroups=glasshive-state glasshive-gateway-secrets",
        "--property=UMask=0077",
        "--property=NoNewPrivileges=yes",
        "--property=PrivateTmp=yes",
        "--property=ProtectHome=yes",
        "--property=ProtectSystem=strict",
        "--property=ReadWritePaths=/var/lib/glasshive",
        f"--property=WorkingDirectory={working_directory}",
        f"--property=EnvironmentFile={GATEWAY_ENV}",
        f"--property=EnvironmentFile={GATEWAY_ACTIVE_ENV}",
        "--property=Environment=PYTHONDONTWRITEBYTECODE=1",
        "--",
        str(python_path),
        "-m",
        "glass_drive_ui.auth_admin",
        "preapprove-oidc",
        "--stdin-json",
    ]


@contextmanager
def _mutation_lock(lock_path: Path = MUTATION_LOCK, *, expected_uid: int | None = None):
    owner_uid = os.geteuid() if expected_uid is None else int(expected_uid)
    lock_path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(lock_path, flags, 0o600)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != owner_uid:
            raise RuntimeError("The GlassHive deployment lock has an unexpected owner or type")
        os.fchmod(descriptor, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise AdminBusyError("A GlassHive rollout is in progress; retry after it completes") from exc
        try:
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)


def main(argv: Sequence[str] | None = None) -> int:
    _parser().parse_args(list(argv) if argv is not None else None)
    if os.geteuid() != 0:
        print("GlassHive identity administration requires root", file=sys.stderr)
        return 2
    try:
        with _mutation_lock():
            command = _systemd_command()
            completed = subprocess.run(command, check=False)
    except AdminBusyError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except (OSError, RuntimeError) as exc:
        print(f"GlassHive identity administration failed: {exc}", file=sys.stderr)
        return 2
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any


class HelperIntentError(RuntimeError):
    pass


def update_runtime_intent(config_path: Path, desired_state: str) -> bool:
    if desired_state not in {"running", "stopped"}:
        raise HelperIntentError("invalid helper runtime intent")
    if not config_path.exists():
        return False

    metadata = config_path.lstat()
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
    ):
        raise HelperIntentError("helper config is not an owner-controlled regular file")

    try:
        payload: Any = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HelperIntentError("helper config is unreadable") from exc
    if not isinstance(payload, dict):
        raise HelperIntentError("helper config must contain a JSON object")

    supervision = payload.get("runtimeSupervision")
    if not isinstance(supervision, dict):
        supervision = {}
    supervision.update(
        {
            "schemaVersion": 1,
            "desiredState": desired_state,
            "consecutiveLaunchAttempts": 0,
            "nextLaunchAttemptAt": None,
            "healthySince": None,
        }
    )
    payload["runtimeSupervision"] = supervision

    config_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{config_path.name}.",
        suffix=".tmp",
        dir=config_path.parent,
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, config_path)
        config_path.chmod(0o600)
        directory_fd = os.open(config_path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
    return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Persist the local runtime intent shared by the CLI and macOS helper."
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--desired", choices=("running", "stopped"), required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        update_runtime_intent(args.config.expanduser(), args.desired)
    except HelperIntentError as exc:
        print(f"Unable to update Viventium helper runtime intent: {exc}.", file=os.sys.stderr)
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

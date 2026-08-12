#!/usr/bin/env python3
"""Prepare, atomically apply, and roll back canonical Viventium config changes."""

from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def load_mapping(path: Path, *, required: bool = True) -> dict[str, Any]:
    if not path.exists():
        if required:
            raise SystemExit(f"Missing config: {path}")
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise SystemExit(f"Config must be a YAML mapping: {path}")
    return payload


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary_name)
    try:
        os.fchmod(file_descriptor, 0o600)
        with os.fdopen(file_descriptor, "wb") as temporary_file:
            temporary_file.write(payload)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, path)
        path.chmod(0o600)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def command_prepare(args: argparse.Namespace) -> int:
    existing = load_mapping(args.existing, required=False) if args.existing else {}
    incoming = load_mapping(args.input)
    merged = deep_merge(existing, incoming)
    atomic_write_bytes(
        args.output,
        yaml.safe_dump(merged, sort_keys=False).encode("utf-8"),
    )
    return 0


def command_apply(args: argparse.Namespace) -> int:
    load_mapping(args.candidate)
    args.backup_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    args.backup_dir.chmod(0o700)
    had_existing = args.config.is_file()
    backup_path: Path | None = None
    if had_existing:
        backup_path = args.backup_dir / f"config-{utc_stamp()}.yaml"
        shutil.copy2(args.config, backup_path)
        backup_path.chmod(0o600)
    atomic_write_bytes(args.config, args.candidate.read_bytes())
    print(
        json.dumps(
            {
                "backup_path": str(backup_path) if backup_path else "",
                "had_existing": had_existing,
            },
            sort_keys=True,
        )
    )
    return 0


def command_rollback(args: argparse.Namespace) -> int:
    had_existing = args.had_existing.lower() == "true"
    if had_existing:
        if not args.backup or not args.backup.is_file():
            raise SystemExit("Rollback requires the recorded config backup")
        atomic_write_bytes(args.config, args.backup.read_bytes())
    elif args.config.exists():
        args.config.unlink()
    print(json.dumps({"rolled_back": True, "restored_existing": had_existing}, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--existing", type=Path)
    prepare.add_argument("--input", required=True, type=Path)
    prepare.add_argument("--output", required=True, type=Path)
    prepare.set_defaults(handler=command_prepare)

    apply = subparsers.add_parser("apply")
    apply.add_argument("--candidate", required=True, type=Path)
    apply.add_argument("--config", required=True, type=Path)
    apply.add_argument("--backup-dir", required=True, type=Path)
    apply.set_defaults(handler=command_apply)

    rollback = subparsers.add_parser("rollback")
    rollback.add_argument("--config", required=True, type=Path)
    rollback.add_argument("--backup", type=Path)
    rollback.add_argument("--had-existing", choices=("true", "false"), required=True)
    rollback.set_defaults(handler=command_rollback)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())

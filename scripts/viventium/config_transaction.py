#!/usr/bin/env python3
"""Prepare, atomically apply, and roll back canonical Viventium config changes."""

from __future__ import annotations

import argparse
import copy
import json
import os
import stat
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


class TransactionError(RuntimeError):
    """A fail-closed local filesystem boundary violation."""


def lexical_path(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path.expanduser())))


def require_contained(path: Path, support: Path, *, label: str) -> Path:
    candidate = lexical_path(path)
    root = lexical_path(support)
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise TransactionError(f"{label} must stay inside Viventium App Support") from error
    return candidate


def validate_no_symlink_chain(path: Path, *, owned_from: Path | None = None) -> None:
    candidate = lexical_path(path)
    owned_root = lexical_path(owned_from) if owned_from else None
    current = Path(candidate.anchor)
    for part in candidate.parts[1:]:
        current /= part
        if not current.exists() and not current.is_symlink():
            continue
        try:
            metadata = current.lstat()
        except OSError as error:
            raise TransactionError("Viventium filesystem path is unsafe") from error
        if stat.S_ISLNK(metadata.st_mode):
            raise TransactionError("Viventium filesystem path contains a symlink")
        if current != candidate and not stat.S_ISDIR(metadata.st_mode):
            raise TransactionError("Viventium filesystem parent is not a directory")
        if owned_root is not None:
            try:
                current.relative_to(owned_root)
            except ValueError:
                pass
            else:
                if metadata.st_uid != os.getuid():
                    raise TransactionError("Viventium App Support path is not owned by the current user")


def ensure_private_directory(path: Path, *, support: Path) -> None:
    directory = require_contained(path, support, label="directory")
    root = lexical_path(support)
    validate_no_symlink_chain(root)
    if not root.exists():
        raise TransactionError("Viventium App Support root is missing")
    root_metadata = root.lstat()
    if not stat.S_ISDIR(root_metadata.st_mode) or root_metadata.st_uid != os.getuid():
        raise TransactionError("Viventium App Support root is unsafe")
    relative = directory.relative_to(root)
    current = root
    for part in relative.parts:
        current /= part
        if current.exists() or current.is_symlink():
            validate_no_symlink_chain(current, owned_from=root)
            metadata = current.lstat()
            if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.getuid():
                raise TransactionError("Viventium App Support directory is unsafe")
        else:
            try:
                current.mkdir(mode=0o700)
            except OSError as error:
                raise TransactionError("Could not create private Viventium directory") from error
            metadata = current.lstat()
            if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.getuid():
                raise TransactionError("Created Viventium directory is unsafe")
        if stat.S_IMODE(current.lstat().st_mode) != 0o700:
            current.chmod(0o700)


def validate_regular_owned_file(path: Path, *, label: str) -> None:
    validate_no_symlink_chain(path)
    try:
        metadata = path.lstat()
    except OSError as error:
        raise TransactionError(f"Missing {label}") from error
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid():
        raise TransactionError(f"{label} must be a current-user-owned regular file")


def read_owned_bytes(path: Path, *, label: str) -> bytes:
    validate_regular_owned_file(path, label=label)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise TransactionError(f"Could not open {label} safely") from error
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid():
            raise TransactionError(f"{label} changed during validation")
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            return handle.read()
    finally:
        os.close(descriptor)


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def load_mapping(path: Path, *, required: bool = True) -> dict[str, Any]:
    if not path.exists():
        if required:
            raise SystemExit(f"Missing config: {path}")
        return {}
    payload = yaml.safe_load(read_owned_bytes(path, label="config input").decode("utf-8")) or {}
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


def atomic_write_bytes(path: Path, payload: bytes, *, support: Path) -> None:
    path = require_contained(path, support, label="config output")
    ensure_private_directory(path.parent, support=support)
    if path.exists() or path.is_symlink():
        validate_regular_owned_file(path, label="config output")
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
        validate_no_symlink_chain(path.parent, owned_from=lexical_path(support))
        if path.exists() or path.is_symlink():
            validate_regular_owned_file(path, label="config output")
        os.replace(temporary_path, path)
        path.chmod(0o600)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def command_prepare(args: argparse.Namespace) -> int:
    support = lexical_path(args.app_support_dir)
    output = require_contained(args.output, support, label="candidate config")
    existing_path = require_contained(args.existing, support, label="existing config") if args.existing else None
    existing = load_mapping(existing_path, required=False) if existing_path else {}
    incoming = load_mapping(args.input)
    merged = deep_merge(existing, incoming)
    atomic_write_bytes(
        output,
        yaml.safe_dump(merged, sort_keys=False).encode("utf-8"),
        support=support,
    )
    return 0


def command_allocate(args: argparse.Namespace) -> int:
    support = lexical_path(args.app_support_dir)
    candidate_root = require_contained(args.candidate_root, support, label="config candidate directory")
    ensure_private_directory(candidate_root, support=support)
    attempt = Path(tempfile.mkdtemp(prefix="attempt.", dir=candidate_root))
    attempt.chmod(0o700)
    validate_no_symlink_chain(attempt, owned_from=support)
    print(str(attempt))
    return 0


def command_apply(args: argparse.Namespace) -> int:
    support = lexical_path(args.app_support_dir)
    candidate = require_contained(args.candidate, support, label="candidate config")
    config = require_contained(args.config, support, label="canonical config")
    backup_dir = require_contained(args.backup_dir, support, label="config backup directory")
    load_mapping(candidate)
    had_existing = config.exists() or config.is_symlink()
    if had_existing:
        validate_regular_owned_file(config, label="canonical config")
    ensure_private_directory(backup_dir, support=support)
    backup_path: Path | None = None
    if had_existing:
        backup_path = backup_dir / f"config-{utc_stamp()}.yaml"
        atomic_write_bytes(backup_path, read_owned_bytes(config, label="canonical config"), support=support)
    atomic_write_bytes(config, read_owned_bytes(candidate, label="candidate config"), support=support)
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
    support = lexical_path(args.app_support_dir)
    config = require_contained(args.config, support, label="canonical config")
    had_existing = args.had_existing.lower() == "true"
    if had_existing:
        if not args.backup:
            raise SystemExit("Rollback requires the recorded config backup")
        backup = require_contained(args.backup, support, label="config backup")
        atomic_write_bytes(config, read_owned_bytes(backup, label="config backup"), support=support)
    elif config.exists() or config.is_symlink():
        validate_regular_owned_file(config, label="canonical config")
        config.unlink()
    print(json.dumps({"rolled_back": True, "restored_existing": had_existing}, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    allocate = subparsers.add_parser("allocate")
    allocate.add_argument("--candidate-root", required=True, type=Path)
    allocate.add_argument("--app-support-dir", required=True, type=Path)
    allocate.set_defaults(handler=command_allocate)

    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--existing", type=Path)
    prepare.add_argument("--input", required=True, type=Path)
    prepare.add_argument("--output", required=True, type=Path)
    prepare.add_argument("--app-support-dir", required=True, type=Path)
    prepare.set_defaults(handler=command_prepare)

    apply = subparsers.add_parser("apply")
    apply.add_argument("--candidate", required=True, type=Path)
    apply.add_argument("--config", required=True, type=Path)
    apply.add_argument("--backup-dir", required=True, type=Path)
    apply.add_argument("--app-support-dir", required=True, type=Path)
    apply.set_defaults(handler=command_apply)

    rollback = subparsers.add_parser("rollback")
    rollback.add_argument("--config", required=True, type=Path)
    rollback.add_argument("--backup", type=Path)
    rollback.add_argument("--had-existing", choices=("true", "false"), required=True)
    rollback.add_argument("--app-support-dir", required=True, type=Path)
    rollback.set_defaults(handler=command_rollback)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.handler(args)
    except (TransactionError, UnicodeDecodeError, yaml.YAMLError) as error:
        raise SystemExit(f"Config transaction refused an unsafe path or input: {error}") from error


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Small canonical-config patcher for local Viventium runtime settings."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"Missing config: {path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise SystemExit(f"Config must be a YAML mapping: {path}")
    return payload


def transcript_source(config: dict[str, Any]) -> str:
    runtime = config.get("runtime")
    if not isinstance(runtime, dict):
        return ""
    memory_hardening = runtime.get("memory_hardening")
    if not isinstance(memory_hardening, dict):
        return ""
    transcripts = memory_hardening.get("transcripts")
    if not isinstance(transcripts, dict):
        return ""
    return str(transcripts.get("source_dir") or "").strip()


def ensure_transcript_config(config: dict[str, Any]) -> dict[str, Any]:
    runtime = config.setdefault("runtime", {})
    if not isinstance(runtime, dict):
        raise SystemExit("runtime must be a mapping in config.yaml")
    memory_hardening = runtime.setdefault("memory_hardening", {})
    if not isinstance(memory_hardening, dict):
        raise SystemExit("runtime.memory_hardening must be a mapping in config.yaml")
    transcripts = memory_hardening.setdefault("transcripts", {})
    if not isinstance(transcripts, dict):
        raise SystemExit("runtime.memory_hardening.transcripts must be a mapping in config.yaml")
    return transcripts


def backup_config(path: Path, backup_dir: Path | None) -> str | None:
    if backup_dir is None:
        return None
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"config-{utc_stamp()}.yaml"
    shutil.copy2(path, backup_path)
    return str(backup_path)


def write_config(path: Path, config: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    os.replace(tmp_path, path)


def resolve_existing_directory(raw_path: str) -> str:
    value = str(raw_path or "").strip()
    if not value:
        raise SystemExit("Transcript source path must not be empty")
    path = Path(value).expanduser()
    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise SystemExit(f"Transcript source folder does not exist: {path}") from exc
    if not resolved.is_dir():
        raise SystemExit(f"Transcript source must be a folder: {resolved}")
    return str(resolved)


def emit(payload: dict[str, Any], json_output: bool) -> None:
    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    status = payload.get("status")
    source_dir = payload.get("source_dir") or "(not configured)"
    print(f"Transcript source {status}: {source_dir}")
    if payload.get("backup_path"):
        print(f"Backup: {payload['backup_path']}")


def command_status(args: argparse.Namespace) -> int:
    config = load_config(args.config_file)
    emit(
        {
            "status": "configured" if transcript_source(config) else "not_configured",
            "source_dir": transcript_source(config),
            "changed": False,
        },
        args.json,
    )
    return 0


def command_set(args: argparse.Namespace) -> int:
    config = load_config(args.config_file)
    next_source = resolve_existing_directory(args.path)
    previous_source = transcript_source(config)
    changed = previous_source != next_source
    backup_path = None
    if changed:
        backup_path = backup_config(args.config_file, args.backup_dir)
        transcripts = ensure_transcript_config(config)
        transcripts["source_dir"] = next_source
        write_config(args.config_file, config)
    emit(
        {
            "status": "configured",
            "source_dir": next_source,
            "previous_source_dir": previous_source,
            "changed": changed,
            "backup_path": backup_path,
            "requires_runtime_refresh": changed,
        },
        args.json,
    )
    return 0


def command_clear(args: argparse.Namespace) -> int:
    config = load_config(args.config_file)
    previous_source = transcript_source(config)
    changed = bool(previous_source)
    backup_path = None
    if changed:
        backup_path = backup_config(args.config_file, args.backup_dir)
        transcripts = ensure_transcript_config(config)
        transcripts["source_dir"] = ""
        write_config(args.config_file, config)
    emit(
        {
            "status": "not_configured",
            "source_dir": "",
            "previous_source_dir": previous_source,
            "changed": changed,
            "backup_path": backup_path,
            "requires_runtime_refresh": changed,
        },
        args.json,
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Patch canonical local Viventium config settings.")
    parser.add_argument("--config-file", required=True, type=Path)
    parser.add_argument("--backup-dir", type=Path)
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("transcripts-source-status")
    status.add_argument("--json", action="store_true")
    status.set_defaults(handler=command_status)

    set_source = subparsers.add_parser("transcripts-source-set")
    set_source.add_argument("path")
    set_source.add_argument("--json", action="store_true")
    set_source.set_defaults(handler=command_set)

    clear_source = subparsers.add_parser("transcripts-source-clear")
    clear_source.add_argument("--json", action="store_true")
    clear_source.set_defaults(handler=command_clear)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.config_file = args.config_file.expanduser()
    if args.backup_dir is not None:
        args.backup_dir = args.backup_dir.expanduser()
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())

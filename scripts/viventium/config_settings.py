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


QA_TEST_ACCOUNT_ENV_KEY = "VIVENTIUM_QA_EMAIL"


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


def runtime_extra_env(config: dict[str, Any]) -> dict[str, Any]:
    runtime = config.get("runtime")
    if not isinstance(runtime, dict):
        return {}
    extra_env = runtime.get("extra_env")
    return extra_env if isinstance(extra_env, dict) else {}


def ensure_runtime_extra_env(config: dict[str, Any]) -> dict[str, Any]:
    runtime = config.setdefault("runtime", {})
    if not isinstance(runtime, dict):
        raise SystemExit("runtime must be a mapping in config.yaml")
    extra_env = runtime.setdefault("extra_env", {})
    if not isinstance(extra_env, dict):
        raise SystemExit("runtime.extra_env must be a mapping in config.yaml")
    return extra_env


def qa_test_account_email(config: dict[str, Any]) -> str:
    return str(runtime_extra_env(config).get(QA_TEST_ACCOUNT_ENV_KEY) or "").strip()


def validate_qa_test_account_email(value: str) -> str:
    email = str(value or "").strip()
    if (
        not email
        or len(email) > 320
        or email.count("@") != 1
        or any(character.isspace() for character in email)
    ):
        raise SystemExit("QA test-account email must be a valid non-empty email address")
    return email


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


def emit_qa_account(payload: dict[str, Any], json_output: bool) -> None:
    public_payload = {
        key: value
        for key, value in payload.items()
        if key not in {"email", "previous_email"}
    }
    if json_output:
        print(json.dumps(public_payload, indent=2, sort_keys=True))
        return
    print(f"QA test account: {public_payload['status']}")
    if public_payload.get("backup_path"):
        print(f"Backup: {public_payload['backup_path']}")


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


def command_qa_test_account_status(args: argparse.Namespace) -> int:
    config = load_config(args.config_file)
    configured = bool(qa_test_account_email(config))
    emit_qa_account(
        {"status": "configured" if configured else "not_configured", "changed": False},
        args.json,
    )
    return 0


def command_qa_test_account_set(args: argparse.Namespace) -> int:
    config = load_config(args.config_file)
    raw_email = sys.stdin.readline() if args.email_stdin else args.email
    next_email = validate_qa_test_account_email(raw_email)
    previous_email = qa_test_account_email(config)
    changed = previous_email != next_email
    backup_path = None
    if changed:
        backup_path = backup_config(args.config_file, args.backup_dir)
        ensure_runtime_extra_env(config)[QA_TEST_ACCOUNT_ENV_KEY] = next_email
        write_config(args.config_file, config)
    emit_qa_account(
        {
            "status": "configured",
            "changed": changed,
            "email": next_email,
            "previous_email": previous_email,
            "backup_path": backup_path,
            "requires_runtime_refresh": changed,
        },
        args.json,
    )
    return 0


def command_qa_test_account_clear(args: argparse.Namespace) -> int:
    config = load_config(args.config_file)
    previous_email = qa_test_account_email(config)
    changed = bool(previous_email)
    backup_path = None
    if changed:
        backup_path = backup_config(args.config_file, args.backup_dir)
        ensure_runtime_extra_env(config).pop(QA_TEST_ACCOUNT_ENV_KEY, None)
        write_config(args.config_file, config)
    emit_qa_account(
        {
            "status": "not_configured",
            "changed": changed,
            "previous_email": previous_email,
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

    qa_status = subparsers.add_parser("qa-test-account-status")
    qa_status.add_argument("--json", action="store_true")
    qa_status.set_defaults(handler=command_qa_test_account_status)

    qa_set = subparsers.add_parser("qa-test-account-set")
    qa_set.add_argument("email", nargs="?")
    qa_set.add_argument("--email-stdin", action="store_true")
    qa_set.add_argument("--json", action="store_true")
    qa_set.set_defaults(handler=command_qa_test_account_set)

    qa_clear = subparsers.add_parser("qa-test-account-clear")
    qa_clear.add_argument("--json", action="store_true")
    qa_clear.set_defaults(handler=command_qa_test_account_clear)
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

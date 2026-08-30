#!/usr/bin/env python3
"""Bind installed Telegram TR-026 controls to one canonical local-QA session."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from types import ModuleType

CASE_ID = "TR-026"
ARTIFACT_REF = re.compile(r"^[a-f0-9]{16}$")
SCOPE_FIELDS = {
    "caseId",
    "chatId",
    "contractVersion",
    "ownerUserId",
    "sourceSequence",
    "staleSourceSequence",
    "threadId",
    "ttlSeconds",
    "updateId",
}
MAX_SCOPE_BYTES = 4096


def _load_path(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError("required local-QA module is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _session_module() -> ModuleType:
    return _load_path(
        Path(__file__).with_name("local_qa_runtime_control.py"),
        "viventium_local_qa_runtime_control",
    )


def _control_module(installed_root: Path) -> ModuleType:
    path = (
        installed_root.expanduser().resolve(strict=True)
        / "viventium_v0_4"
        / "telegram-viventium"
        / "TelegramVivBot"
        / "utils"
        / "tr026_local_qa.py"
    )
    return _load_path(path, "viventium_installed_tr026_local_qa")


def _field(value: object, name: str) -> object:
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    payload: dict[str, object] = {}
    for key, value in pairs:
        if key in payload:
            raise ValueError("duplicate Telegram local-QA scope field")
        payload[key] = value
    return payload


def parse_private_scope(raw: str | bytes) -> dict[str, object]:
    if isinstance(raw, bytes):
        encoded = raw
        try:
            raw = encoded.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("Telegram local-QA scope is invalid") from exc
    elif isinstance(raw, str):
        encoded = raw.encode("utf-8")
    else:
        raise TypeError("Telegram local-QA scope is invalid")
    if not raw or len(encoded) > MAX_SCOPE_BYTES:
        raise ValueError("Telegram local-QA scope is invalid")
    try:
        payload = json.loads(raw, object_pairs_hook=_reject_duplicate_keys)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError("Telegram local-QA scope is invalid") from exc
    if not isinstance(payload, dict) or set(payload) != SCOPE_FIELDS:
        raise ValueError("Telegram local-QA scope is invalid")
    if payload.get("contractVersion") != 1 or payload.get("caseId") != CASE_ID:
        raise ValueError("Telegram local-QA scope is invalid")
    for name in SCOPE_FIELDS - {"caseId"}:
        if name == "contractVersion":
            continue
        if isinstance(payload.get(name), bool) or not isinstance(payload.get(name), int):
            raise TypeError("Telegram local-QA scope is invalid")
    return payload


def _exact_session(
    *,
    state_path: Path,
    installed_root: Path,
    artifact_identity_path: Path,
    local_qa_request_path: Path | None = None,
    now: datetime | None = None,
    active: bool,
    require_artifact_identity: bool = True,
) -> dict[str, object]:
    session = _session_module()
    if active:
        if local_qa_request_path is None:
            raise ValueError("an explicit local-QA request is required")
        payload = session.active_session(
            state_path=state_path,
            installed_root=installed_root,
            artifact_identity_path=artifact_identity_path,
            local_qa_request_path=local_qa_request_path,
            now=now,
        )
    else:
        payload = session._read_state(state_path)
        if payload["installedRootHash"] != session._root_hash(installed_root):
            raise ValueError("local-QA session belongs to a different installed candidate")
        if require_artifact_identity and payload["artifactIdentityDigest"] != session._file_digest(
            artifact_identity_path
        ):
            raise ValueError("installed artifact identity changed after QA activation")
    if payload.get("caseId") != CASE_ID:
        raise ValueError("an exact active TR-026 session is required")
    return payload


def _module(control_module: ModuleType | object | None, installed_root: Path):
    return control_module if control_module is not None else _control_module(installed_root)


def arm_telegram_race(
    *,
    state_path: Path,
    installed_root: Path,
    artifact_identity_path: Path,
    local_qa_request_path: Path,
    telegram_state_dir: Path,
    owner_user_id: int,
    chat_id: int,
    thread_id: int,
    stale_source_sequence: int,
    source_sequence: int,
    update_id: int,
    ttl_seconds: int,
    now: datetime | None = None,
    control_module: ModuleType | object | None = None,
) -> dict[str, object]:
    payload = _exact_session(
        state_path=state_path,
        installed_root=installed_root,
        artifact_identity_path=artifact_identity_path,
        local_qa_request_path=local_qa_request_path,
        now=now,
        active=True,
    )
    receipt = _module(control_module, installed_root).arm_tr026_control(
        case_token=str(payload["caseToken"]),
        session_ref=str(payload["sessionRef"]),
        owner_user_id=owner_user_id,
        chat_id=chat_id,
        thread_id=thread_id,
        stale_source_sequence=stale_source_sequence,
        source_sequence=source_sequence,
        update_id=update_id,
        ttl_seconds=ttl_seconds,
        state_dir=telegram_state_dir,
    )
    artifact_ref = str(_field(receipt, "artifact_ref") or "")
    if (
        _field(receipt, "case_id") != CASE_ID
        or _field(receipt, "session_ref") != payload["sessionRef"]
        or _field(receipt, "delay_ms") != 280
        or not ARTIFACT_REF.fullmatch(artifact_ref)
    ):
        raise ValueError("Telegram local-QA arm receipt is invalid")
    return {
        "armed": True,
        "artifactRef": artifact_ref,
        "delayMs": 280,
        "sessionRef": payload["sessionRef"],
    }


def audit_telegram_race(
    *,
    state_path: Path,
    installed_root: Path,
    artifact_identity_path: Path,
    telegram_state_dir: Path,
    control_module: ModuleType | object | None = None,
) -> dict[str, object]:
    payload = _exact_session(
        state_path=state_path,
        installed_root=installed_root,
        artifact_identity_path=artifact_identity_path,
        active=False,
    )
    evidence = _module(control_module, installed_root).read_redacted_audit(
        case_token=str(payload["caseToken"]),
        session_ref=str(payload["sessionRef"]),
        state_dir=telegram_state_dir,
    )
    return {
        "caseId": CASE_ID,
        "evidence": evidence,
        "sessionRef": payload["sessionRef"],
    }


def cleanup_telegram_race(
    *,
    state_path: Path,
    installed_root: Path,
    artifact_identity_path: Path,
    telegram_state_dir: Path,
    control_module: ModuleType | object | None = None,
) -> dict[str, object]:
    session = _session_module()
    payload = session._read_state(state_path)
    if payload.get("caseId") != CASE_ID:
        return {"cleaned": False}
    payload = _exact_session(
        state_path=state_path,
        installed_root=installed_root,
        artifact_identity_path=artifact_identity_path,
        active=False,
        require_artifact_identity=False,
    )
    cleaned = _module(control_module, installed_root).cleanup_tr026_control(
        case_token=str(payload["caseToken"]),
        session_ref=str(payload["sessionRef"]),
        state_dir=telegram_state_dir,
    )
    return {"cleaned": bool(cleaned), "sessionRef": payload["sessionRef"]}


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--installed-root", type=Path, required=True)
    parser.add_argument("--artifact-identity", type=Path, required=True)
    parser.add_argument("--telegram-state-dir", type=Path, required=True)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    commands = parser.add_subparsers(dest="command", required=True)
    arm = commands.add_parser("arm", allow_abbrev=False)
    _common(arm)
    arm.add_argument("--local-qa-request", type=Path, required=True)
    arm.add_argument("--scope-stdin", action="store_true", required=True)
    for name in ("audit", "cleanup"):
        _common(commands.add_parser(name, allow_abbrev=False))
    args = parser.parse_args(list(argv) if argv is not None else None)
    common = {
        "state_path": args.state,
        "installed_root": args.installed_root,
        "artifact_identity_path": args.artifact_identity,
        "telegram_state_dir": args.telegram_state_dir,
    }
    try:
        if args.command == "arm":
            _session_module().require_restart_ready(
                state_path=args.state,
                installed_root=args.installed_root,
                artifact_identity_path=args.artifact_identity,
                local_qa_request_path=args.local_qa_request,
            )
            stream = getattr(sys.stdin, "buffer", sys.stdin)
            scope = parse_private_scope(stream.read(MAX_SCOPE_BYTES + 1))
            result = arm_telegram_race(
                **common,
                local_qa_request_path=args.local_qa_request,
                owner_user_id=int(scope["ownerUserId"]),
                chat_id=int(scope["chatId"]),
                thread_id=int(scope["threadId"]),
                stale_source_sequence=int(scope["staleSourceSequence"]),
                source_sequence=int(scope["sourceSequence"]),
                update_id=int(scope["updateId"]),
                ttl_seconds=int(scope["ttlSeconds"]),
            )
        elif args.command == "audit":
            result = audit_telegram_race(**common)
        else:
            result = cleanup_telegram_race(**common)
    except (OSError, RuntimeError, TypeError, ValueError):
        print(json.dumps({"caseId": CASE_ID, "error": "operation_failed"}), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Inject and exactly restore the REL-UC-004 installed release-claim faults."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
import tempfile
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

CONTRACT_VERSION = 1
BACKUP_FIELDS = {
    "contractVersion",
    "injectedDigest",
    "original",
    "originalDigest",
    "sessionRef",
}


def _load_control():
    cached = sys.modules.get("local_qa_runtime_control")
    if cached is not None:
        return cached
    path = Path(__file__).with_name("local_qa_runtime_control.py")
    spec = importlib.util.spec_from_file_location("local_qa_runtime_control", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("local-QA session control is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _load_json(path: Path, description: str) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{description} is invalid") from exc


def _write_private_json(path: Path, payload: object) -> None:
    path = path.expanduser().resolve(strict=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            os.fchmod(temporary.fileno(), 0o600)
            temporary.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
        os.chmod(path, 0o600)
        directory_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _validate_readiness(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or value.get("contractVersion") != CONTRACT_VERSION:
        raise ValueError("installed readiness facts are invalid")
    if not isinstance(value.get("promptLayers"), dict) or not isinstance(
        value.get("storagePressure"), dict
    ):
        raise TypeError("installed readiness facts are invalid")
    return value


def _rel_session(
    *,
    session_state: Path,
    installed_root: Path,
    artifact_identity_path: Path,
    now: datetime | None,
    allow_expired: bool,
) -> dict[str, object]:
    control = _load_control()
    if allow_expired:
        payload = control._read_state(session_state)
        if payload.get("installedRootHash") != control._root_hash(installed_root):
            raise ValueError("local-QA session belongs to a different installed candidate")
        if payload.get("artifactIdentityDigest") != control._file_digest(artifact_identity_path):
            raise ValueError("installed artifact identity changed after QA activation")
    else:
        payload = control.active_session(
            state_path=session_state,
            installed_root=installed_root,
            artifact_identity_path=artifact_identity_path,
            local_qa_request_path=(
                session_state.parent.parent / "parallel-work-local-qa-request.json"
            ),
            now=now,
        )
    if payload.get("caseId") != "REL-UC-004":
        raise ValueError("an exact active REL-UC-004 session is required")
    return payload


def apply_faults(
    *,
    session_state: Path,
    installed_root: Path,
    artifact_identity_path: Path,
    readiness_path: Path,
    backup_path: Path,
    now: datetime | None = None,
) -> dict[str, object]:
    session = _rel_session(
        session_state=session_state,
        installed_root=installed_root,
        artifact_identity_path=artifact_identity_path,
        now=now,
        allow_expired=False,
    )
    if backup_path.exists() or backup_path.is_symlink():
        raise ValueError("REL-UC-004 faults are already injected")
    original = _validate_readiness(_load_json(readiness_path, "installed readiness facts"))
    injected = json.loads(json.dumps(original))
    prompt = dict(injected["promptLayers"])
    original_registry_hash = str(prompt.get("registryHash") or "")
    mismatch_hash = "0" * 64 if original_registry_hash != "0" * 64 else "1" * 64
    prompt.update(
        {
            "status": "mismatch",
            "registryHash": mismatch_hash,
            "reason": "local_qa_prompt_hash_mismatch",
        }
    )
    injected["promptLayers"] = prompt
    injected["storagePressure"] = {
        "version": CONTRACT_VERSION,
        "status": "critical",
        "usedPercent": 96.0,
        "availableBytes": 4_300_000_000,
        "thresholdPercent": 95.0,
        "warningMarginPercent": 10.0,
        "reason": "local_qa_threshold_injection",
    }
    backup = {
        "contractVersion": CONTRACT_VERSION,
        "injectedDigest": _digest(injected),
        "original": original,
        "originalDigest": _digest(original),
        "sessionRef": session["sessionRef"],
    }
    _write_private_json(backup_path, backup)
    _write_private_json(readiness_path, injected)
    return {
        "applied": True,
        "diskBytesWritten": backup_path.stat().st_size + readiness_path.stat().st_size,
        "sessionRef": session["sessionRef"],
        "storageProbe": "synthetic_threshold_only",
    }


def restore_faults(
    *,
    session_state: Path,
    installed_root: Path,
    artifact_identity_path: Path,
    readiness_path: Path,
    backup_path: Path,
    now: datetime | None = None,
) -> dict[str, object]:
    session = _rel_session(
        session_state=session_state,
        installed_root=installed_root,
        artifact_identity_path=artifact_identity_path,
        now=now,
        allow_expired=True,
    )
    backup = _load_json(backup_path, "REL-UC-004 restoration state")
    if not isinstance(backup, dict) or set(backup) != BACKUP_FIELDS:
        raise ValueError("REL-UC-004 restoration state is invalid")
    if backup.get("contractVersion") != CONTRACT_VERSION:
        raise ValueError("REL-UC-004 restoration state is invalid")
    if backup.get("sessionRef") != session.get("sessionRef"):
        raise ValueError("REL-UC-004 restoration session did not match")
    current = _load_json(readiness_path, "installed readiness facts")
    if _digest(current) != backup.get("injectedDigest"):
        raise ValueError("installed readiness facts changed after injection")
    original = _validate_readiness(backup.get("original"))
    if _digest(original) != backup.get("originalDigest"):
        raise ValueError("REL-UC-004 restoration state is invalid")
    _write_private_json(readiness_path, original)
    backup_path.unlink()
    return {"restored": True, "sessionRef": session["sessionRef"]}


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("action", choices=("apply", "restore"))
    parser.add_argument("--session-state", type=Path, required=True)
    parser.add_argument("--installed-root", type=Path, required=True)
    parser.add_argument("--artifact-identity", type=Path, required=True)
    parser.add_argument("--readiness", type=Path, required=True)
    parser.add_argument("--backup", type=Path, required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        if args.action == "apply":
            _load_control().require_restart_ready(
                state_path=args.session_state,
                installed_root=args.installed_root,
                artifact_identity_path=args.artifact_identity,
                local_qa_request_path=(
                    args.session_state.parent.parent
                    / "parallel-work-local-qa-request.json"
                ),
            )
        function = apply_faults if args.action == "apply" else restore_faults
        result = function(
            session_state=args.session_state,
            installed_root=args.installed_root,
            artifact_identity_path=args.artifact_identity,
            readiness_path=args.readiness,
            backup_path=args.backup,
        )
    except (TypeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

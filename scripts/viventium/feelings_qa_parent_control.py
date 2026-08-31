#!/usr/bin/env python3
"""Verify private installed EMO-UC-047 receipts without exposing user data.

This post-run verifier cannot mark a release gate PASS or replace Telegram acceptance.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import stat
import sys
from collections.abc import Iterable, Mapping
from datetime import datetime
from pathlib import Path
from types import ModuleType

CASE_ID = "EMO-UC-047"
CONTRACT_VERSION = 1
EVIDENCE_MAX_BYTES = 128 * 1024
SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
SHA256_REF_PATTERN = re.compile(r"^sha256:[a-f0-9]{64}$")
SESSION_REF_PATTERN = re.compile(r"^qa_[a-f0-9]{24}$")
NATIVE_RECEIPT_REF_PATTERN = re.compile(
    r"^native_provider_receipt_sha256:[a-f0-9]{64}$"
)
SAFE_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,79}$")

TOP_LEVEL_FIELDS = frozenset(
    {
        "artifactIdentityDigest",
        "caseId",
        "componentArtifactDigest",
        "contractVersion",
        "requestIsolation",
        "safetyAudit",
        "scenarios",
        "sessionRef",
        "synthetic",
    }
)
SCENARIO_FIELDS = frozenset(
    {
        "feelingsEnabled",
        "name",
        "requestRef",
        "scope",
        "semanticVerdict",
        "snapshotHash",
        "sourcePlacement",
        "winningNativeReceipt",
        "workers",
    }
)
SCENARIOS: Mapping[str, tuple[str | None, bool, int, int]] = {
    "all_agents_before_delegation": ("all_agents", True, 1, 0),
    "all_agents_during_workers": ("all_agents", True, 1, 2),
    "conscious_agent_during_workers": ("conscious_agent", True, 1, 2),
    "off_during_workers": (None, False, 0, 2),
}


class PrivateArgumentParser(argparse.ArgumentParser):
    """Reject malformed arguments without printing private values."""

    def error(self, message: str) -> None:
        del message
        raise ValueError("operation_failed")


class DuplicateJsonKeyError(ValueError):
    """Reject ambiguous evidence instead of accepting the last value."""


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJsonKeyError("duplicate JSON key")
        result[key] = value
    return result


def _reject_duplicate_options(argv: Iterable[str]) -> None:
    seen: set[str] = set()
    for argument in argv:
        if not argument.startswith("--"):
            continue
        option = argument.split("=", 1)[0]
        if option in seen:
            raise ValueError("operation_failed")
        seen.add(option)


def _load_path(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError("operation_failed")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _session_module() -> ModuleType:
    return _load_path(
        Path(__file__).with_name("local_qa_runtime_control.py"),
        "viventium_local_qa_runtime_control_for_emo047",
    )


def _invalid() -> ValueError:
    return ValueError("EMO-UC-047 evidence is invalid")


def _exact_mapping(value: object, fields: frozenset[str] | set[str]) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != set(fields):
        raise _invalid()
    return value


def _sha(value: object, *, allow_none: bool = False) -> str:
    normalized = str(value or "")
    if allow_none and normalized == "none":
        return normalized
    if not SHA256_PATTERN.fullmatch(normalized):
        raise _invalid()
    return normalized


def _sha_ref(value: object) -> str:
    normalized = str(value or "")
    if not SHA256_REF_PATTERN.fullmatch(normalized):
        raise _invalid()
    return normalized


def _exact_nonnegative_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise _invalid()
    return value


def _safe_token(value: object) -> str:
    normalized = str(value or "")
    if not SAFE_TOKEN_PATTERN.fullmatch(normalized):
        raise _invalid()
    return normalized


def _validate_source_placement(
    value: object, *, request_ref: str, snapshot_hash: str, expected_count: int
) -> None:
    row = _exact_mapping(
        value,
        {
            "capsuleOccurrenceCount",
            "event",
            "placement",
            "presentInFinalRun",
            "requestRef",
            "route",
            "snapshotHash",
            "trailingInstructionChars",
        },
    )
    expected_placement = "final_instruction_layer" if expected_count else "absent"
    if (
        row["event"] != "feelings.inject.final_run"
        or row["requestRef"] != request_ref
        or row["route"] != "main_conscious_agent"
        or row["snapshotHash"] != snapshot_hash
        or _exact_nonnegative_int(row["capsuleOccurrenceCount"]) != expected_count
        or row["placement"] != expected_placement
        or row["presentInFinalRun"] is not bool(expected_count)
        or _exact_nonnegative_int(row["trailingInstructionChars"]) != 0
    ):
        raise _invalid()


def _validate_main_receipt(
    value: object, *, request_ref: str, snapshot_hash: str, expected_count: int
) -> str:
    receipt = _exact_mapping(
        value,
        {
            "capsuleOccurrenceCount",
            "event",
            "mainInstructionOccurrenceCount",
            "model",
            "nativeRequestSha256",
            "outputKind",
            "provider",
            "receiptRef",
            "requestRef",
            "snapshotHash",
            "status",
        },
    )
    status = receipt["status"]
    receipt_ref = str(receipt["receiptRef"] or "")
    if (
        receipt["event"] != "viventium_text_main_winning_native_provider_receipt"
        or receipt["requestRef"] != request_ref
        or not NATIVE_RECEIPT_REF_PATTERN.fullmatch(receipt_ref)
        or receipt["snapshotHash"] != snapshot_hash
        or _exact_nonnegative_int(receipt["capsuleOccurrenceCount"]) != expected_count
        or _exact_nonnegative_int(receipt["mainInstructionOccurrenceCount"]) != 1
        or receipt["outputKind"] != "visible_text_delta"
        or isinstance(status, bool)
        or not isinstance(status, int)
        or status < 200
        or status >= 300
    ):
        raise _invalid()
    _sha(receipt["nativeRequestSha256"])
    _safe_token(receipt["provider"])
    _safe_token(receipt["model"])
    return receipt_ref


def _validate_semantic_verdict(value: object) -> None:
    verdict = _exact_mapping(
        value,
        {"answerSha256", "rubricEvidenceSha256", "status"},
    )
    if verdict["status"] != "pass":
        raise _invalid()
    _sha(verdict["answerSha256"])
    _sha(verdict["rubricEvidenceSha256"])


def _validate_worker(
    value: object, *, snapshot_hash: str, expected_count: int
) -> tuple[str, str, str]:
    worker = _exact_mapping(
        value,
        {
            "instructionSha256",
            "nativeAuthorityReceipt",
            "projection",
            "workerRef",
        },
    )
    worker_ref = _sha_ref(worker["workerRef"])
    instruction_hash = _sha(worker["instructionSha256"])
    projection = _exact_mapping(
        worker["projection"],
        {
            "capsuleOccurrenceCount",
            "materializedCapsuleSha256",
            "placement",
            "snapshotHash",
            "trailingInstructionChars",
        },
    )
    expected_placement = "final_instruction_layer" if expected_count else "absent"
    expected_materialized_hash = snapshot_hash if expected_count else "none"
    if (
        projection["snapshotHash"] != snapshot_hash
        or _sha(projection["materializedCapsuleSha256"], allow_none=True)
        != expected_materialized_hash
        or _exact_nonnegative_int(projection["capsuleOccurrenceCount"])
        != expected_count
        or projection["placement"] != expected_placement
        or _exact_nonnegative_int(projection["trailingInstructionChars"]) != 0
    ):
        raise _invalid()

    receipt = _exact_mapping(
        worker["nativeAuthorityReceipt"],
        {
            "authoritySha256",
            "feelingCapsuleCount",
            "materialized",
            "placement",
            "protocol",
            "runRef",
            "runtime",
        },
    )
    runtime = str(receipt["runtime"] or "")
    expected_native_placement = {
        "claude-code": "append_system_prompt_file",
        "codex-cli": "codex_developer_instructions",
    }.get(runtime)
    run_ref = _sha_ref(receipt["runRef"])
    if (
        receipt["protocol"] != "glasshive.native_provider_authority_receipt.v1"
        or receipt["materialized"] is not True
        or expected_native_placement is None
        or receipt["placement"] != expected_native_placement
        or _exact_nonnegative_int(receipt["feelingCapsuleCount"]) != expected_count
    ):
        raise _invalid()
    _sha(receipt["authoritySha256"])
    return worker_ref, run_ref, instruction_hash


def _validate_request_isolation(
    value: object, scenarios: Mapping[str, dict[str, object]]
) -> None:
    isolation = _exact_mapping(
        value,
        {
            "firstRequestRef",
            "firstRequestPinnedAtMs",
            "firstProviderStartedAtMs",
            "firstPresentationCommittedAtMs",
            "firstSnapshotHash",
            "firstTypedFallback",
            "overlapObserved",
            "secondRequestRef",
            "secondRequestPinnedAtMs",
            "secondSnapshotHash",
            "stateChangedAtMs",
            "stateChangedBeforeSecondRequest",
        },
    )
    first = scenarios["all_agents_before_delegation"]
    second = scenarios["all_agents_during_workers"]
    first_hash = _sha(isolation["firstSnapshotHash"])
    second_hash = _sha(isolation["secondSnapshotHash"])
    first_pinned_at = _exact_nonnegative_int(isolation["firstRequestPinnedAtMs"])
    first_provider_at = _exact_nonnegative_int(isolation["firstProviderStartedAtMs"])
    state_changed_at = _exact_nonnegative_int(isolation["stateChangedAtMs"])
    second_pinned_at = _exact_nonnegative_int(isolation["secondRequestPinnedAtMs"])
    first_committed_at = _exact_nonnegative_int(
        isolation["firstPresentationCommittedAtMs"]
    )
    if (
        isolation["firstRequestRef"] != first["requestRef"]
        or isolation["secondRequestRef"] != second["requestRef"]
        or first_hash != first["snapshotHash"]
        or second_hash != second["snapshotHash"]
        or first_hash == second_hash
        or first_pinned_at <= 0
        or not (
            first_pinned_at
            <= first_provider_at
            <= state_changed_at
            <= second_pinned_at
            < first_committed_at
        )
        or isolation["overlapObserved"] is not True
        or isolation["stateChangedBeforeSecondRequest"] is not True
    ):
        raise _invalid()
    fallback = _exact_mapping(
        isolation["firstTypedFallback"],
        {
            "capabilitiesPreserved",
            "failureClass",
            "fallbackUsed",
            "retryAfterHonored",
            "winningSnapshotHash",
        },
    )
    if (
        fallback["failureClass"] != "provider_quota_exhausted"
        or fallback["fallbackUsed"] is not True
        or fallback["retryAfterHonored"] is not True
        or fallback["capabilitiesPreserved"] is not True
        or fallback["winningSnapshotHash"] != first_hash
    ):
        raise _invalid()


def _validate_safety(value: object, *, worker_count: int) -> None:
    audit = _exact_mapping(
        value,
        {
            "auditEvidenceSha256",
            "feelingsMcpServerCount",
            "hostPluginDenylistEnabled",
            "parallelWorkDefaultAvailable",
            "parallelWorkDefaultMode",
            "privateStateMountCount",
            "workerAuditCount",
            "workerFeelingsPluginCount",
        },
    )
    if (
        audit["hostPluginDenylistEnabled"] is not True
        or audit["parallelWorkDefaultAvailable"] is not False
        or audit["parallelWorkDefaultMode"] != "focused"
        or _exact_nonnegative_int(audit["privateStateMountCount"]) != 0
        or _exact_nonnegative_int(audit["feelingsMcpServerCount"]) != 0
        or _exact_nonnegative_int(audit["workerFeelingsPluginCount"]) != 0
        or _exact_nonnegative_int(audit["workerAuditCount"]) != worker_count
    ):
        raise _invalid()
    _sha(audit["auditEvidenceSha256"])


def validate_evidence(value: object) -> dict[str, int]:
    """Validate one public-safe projection of installed private QA evidence."""

    root = _exact_mapping(value, TOP_LEVEL_FIELDS)
    if (
        _exact_nonnegative_int(root["contractVersion"]) != CONTRACT_VERSION
        or root["caseId"] != CASE_ID
        or root["synthetic"] is not True
        or not SESSION_REF_PATTERN.fullmatch(str(root["sessionRef"] or ""))
    ):
        raise _invalid()
    _sha_ref(root["artifactIdentityDigest"])
    _sha_ref(root["componentArtifactDigest"])

    scenario_values = root["scenarios"]
    if not isinstance(scenario_values, list) or len(scenario_values) != len(SCENARIOS):
        raise _invalid()
    scenarios: dict[str, dict[str, object]] = {}
    request_refs: set[str] = set()
    main_receipt_refs: set[str] = set()
    worker_refs: set[str] = set()
    run_refs: set[str] = set()
    instruction_hashes: set[str] = set()
    worker_count = 0
    for scenario_value in scenario_values:
        scenario = _exact_mapping(scenario_value, SCENARIO_FIELDS)
        name = str(scenario["name"] or "")
        if name in scenarios or name not in SCENARIOS:
            raise _invalid()
        expected_scope, expected_enabled, main_count, expected_workers = SCENARIOS[name]
        scope = str(scenario["scope"] or "")
        if (
            scope not in {"all_agents", "conscious_agent"}
            or (expected_scope is not None and scope != expected_scope)
            or scenario["feelingsEnabled"] is not expected_enabled
        ):
            raise _invalid()
        snapshot_hash = _sha(scenario["snapshotHash"], allow_none=True)
        if (expected_enabled and snapshot_hash == "none") or (
            not expected_enabled and snapshot_hash != "none"
        ):
            raise _invalid()
        request_ref = _sha_ref(scenario["requestRef"])
        if request_ref in request_refs:
            raise _invalid()
        request_refs.add(request_ref)
        _validate_source_placement(
            scenario["sourcePlacement"],
            request_ref=request_ref,
            snapshot_hash=snapshot_hash,
            expected_count=main_count,
        )
        main_receipt_ref = _validate_main_receipt(
            scenario["winningNativeReceipt"],
            request_ref=request_ref,
            snapshot_hash=snapshot_hash,
            expected_count=main_count,
        )
        if main_receipt_ref in main_receipt_refs:
            raise _invalid()
        main_receipt_refs.add(main_receipt_ref)
        _validate_semantic_verdict(scenario["semanticVerdict"])
        workers = scenario["workers"]
        if not isinstance(workers, list) or len(workers) != expected_workers:
            raise _invalid()
        worker_expected_count = 1 if expected_enabled and scope == "all_agents" else 0
        for worker in workers:
            worker_ref, run_ref, instruction_hash = _validate_worker(
                worker,
                snapshot_hash=snapshot_hash,
                expected_count=worker_expected_count,
            )
            if (
                worker_ref in worker_refs
                or run_ref in run_refs
                or instruction_hash in instruction_hashes
            ):
                raise _invalid()
            worker_refs.add(worker_ref)
            run_refs.add(run_ref)
            instruction_hashes.add(instruction_hash)
            worker_count += 1
        scenarios[name] = scenario

    if set(scenarios) != set(SCENARIOS):
        raise _invalid()
    _validate_request_isolation(root["requestIsolation"], scenarios)
    _validate_safety(root["safetyAudit"], worker_count=worker_count)
    return {
        "mainReceiptCount": len(main_receipt_refs),
        "scenarioCount": len(scenarios),
        "semanticPassCount": len(scenarios),
        "workerReceiptCount": worker_count,
    }


def read_private_evidence_fd(descriptor: int) -> tuple[bytes, object]:
    """Read one inherited owner-only regular file descriptor under a hard limit."""

    try:
        if isinstance(descriptor, bool) or not isinstance(descriptor, int) or descriptor <= 2:
            raise _invalid()
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != os.getuid()
            or stat.S_IMODE(before.st_mode) != 0o600
            or before.st_nlink != 1
            or before.st_size < 1
            or before.st_size > EVIDENCE_MAX_BYTES
            or os.lseek(descriptor, 0, os.SEEK_CUR) != 0
        ):
            raise _invalid()
        remaining = EVIDENCE_MAX_BYTES + 1
        chunks: list[bytes] = []
        while remaining > 0:
            chunk = os.read(descriptor, min(64 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        after = os.fstat(descriptor)
        identity_fields = (
            "st_dev",
            "st_ino",
            "st_mode",
            "st_uid",
            "st_gid",
            "st_nlink",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
        if (
            len(raw) != after.st_size
            or len(raw) > EVIDENCE_MAX_BYTES
            or any(getattr(before, field) != getattr(after, field) for field in identity_fields)
        ):
            raise _invalid()
        payload = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_unique_json_object,
        )
        return raw, payload
    except (DuplicateJsonKeyError, json.JSONDecodeError, OSError, UnicodeError, ValueError) as exc:
        raise _invalid() from exc


def verify_installed_evidence(
    *,
    state_path: Path,
    installed_root: Path,
    artifact_identity_path: Path,
    local_qa_request_path: Path,
    evidence_fd: int,
    now: datetime | None = None,
) -> dict[str, object]:
    """Bind a strict receipt projection to the exact active installed candidate."""

    session = _session_module().active_session(
        state_path=state_path,
        installed_root=installed_root,
        artifact_identity_path=artifact_identity_path,
        local_qa_request_path=local_qa_request_path,
        now=now,
    )
    if session.get("caseId") != CASE_ID:
        raise ValueError("an exact active EMO-UC-047 session is required")
    raw, evidence = read_private_evidence_fd(evidence_fd)
    counts = validate_evidence(evidence)
    assert isinstance(evidence, dict)
    if (
        evidence["sessionRef"] != session["sessionRef"]
        or evidence["artifactIdentityDigest"] != session["artifactIdentityDigest"]
        or evidence["componentArtifactDigest"] != session["componentArtifactDigest"]
    ):
        raise _invalid()
    return {
        "candidateBound": True,
        "caseId": CASE_ID,
        "componentArtifactDigest": session["componentArtifactDigest"],
        "evidenceDigest": "sha256:" + hashlib.sha256(raw).hexdigest(),
        **counts,
        "requestPinned": True,
        "sessionRef": session["sessionRef"],
        "status": "verified",
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = PrivateArgumentParser(description=__doc__, allow_abbrev=False)
    commands = parser.add_subparsers(dest="command", required=True)
    verify = commands.add_parser("verify", allow_abbrev=False)
    verify.add_argument("--state", type=Path, required=True)
    verify.add_argument("--installed-root", type=Path, required=True)
    verify.add_argument("--artifact-identity", type=Path, required=True)
    verify.add_argument("--local-qa-request", type=Path, required=True)
    verify.add_argument("--evidence-fd", type=int, required=True)
    values = list(argv) if argv is not None else sys.argv[1:]
    try:
        _reject_duplicate_options(values)
        args = parser.parse_args(values)
        _session_module().require_restart_ready(
            state_path=args.state,
            installed_root=args.installed_root,
            artifact_identity_path=args.artifact_identity,
            local_qa_request_path=args.local_qa_request,
        )
        result = verify_installed_evidence(
            state_path=args.state,
            installed_root=args.installed_root,
            artifact_identity_path=args.artifact_identity,
            local_qa_request_path=args.local_qa_request,
            evidence_fd=args.evidence_fd,
        )
    except (OSError, RuntimeError, TypeError, UnicodeError, ValueError):
        print(json.dumps({"caseId": CASE_ID, "error": "operation_failed"}), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

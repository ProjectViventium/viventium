#!/usr/bin/env python3
"""Derive EMO-UC-047 only from owner-bound installed Feelings receipts."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import importlib.util
import json
import os
import pwd
import re
import secrets
import stat
import sys
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType
from typing import NoReturn

CASE_ID = "EMO-UC-047"
CONTRACT_VERSION = 1
VERIFIER_ID = "emo047-semantic-v1"
REQUIRED_SERVICES = ("glasshive-runtime", "librechat-core")
REQUIRED_SPECIALISTS = frozenset(
    {"emotional_resonance", "product_help", "productivity", "red_team", "research"}
)
DENIED_FEELINGS_PLUGIN_ID = "viventium-feelings@project-viventium"
MAX_RESULT_AGE = timedelta(hours=24)
MAX_FUTURE_SKEW = timedelta(minutes=5)
SHA256 = re.compile(r"[a-f0-9]{64}\Z")
SHA256_REF = re.compile(r"sha256:[a-f0-9]{64}\Z")
NATIVE_RECEIPT_REF = re.compile(r"native_provider_receipt_sha256:[a-f0-9]{64}\Z")
SAFE_COMPONENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}\Z")
SAFE_CAPABILITY = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")
MANIFEST_FIELDS = frozenset(
    {"candidate", "caseId", "contractVersion", "environment", "evidence", "runAt"}
)
EVIDENCE_FIELDS = frozenset({"kind", "path", "sha256"})
REQUIRED_EVIDENCE_KINDS = frozenset(
    {
        "feelings_control_projection",
        "feelings_semantic_receipts",
        "feelings_service_acknowledgement",
    }
)
LIVE_STATUS_FIELDS = frozenset(
    {
        "acknowledgedServices",
        "caseId",
        "expiresAt",
        "missingServices",
        "mode",
        "requiredServices",
        "restartState",
        "serviceAckDigest",
        "sessionRef",
    }
)
SERVICE_EVIDENCE_FIELDS = LIVE_STATUS_FIELDS | {
    "artifactIdentityDigest",
    "componentArtifactDigest",
    "contractVersion",
    "observedAt",
}
SEMANTIC_FIELDS = frozenset(
    {
        "artifactIdentityDigest",
        "caseId",
        "componentArtifactDigest",
        "contractVersion",
        "fallbackContinuity",
        "phaseBContinuity",
        "privacyAudit",
        "scenarios",
        "sessionRef",
        "specialistReceipts",
    }
)
LAYER_FIELDS = frozenset(
    {
        "capsuleLayerIndex",
        "capsuleOccurrenceCount",
        "capsuleSha256",
        "finalLayerIndex",
        "requestRef",
        "snapshotHash",
        "stateVersion",
        "structuralLayerIndex",
        "surfaceLayerIndex",
        "trailingInstructionChars",
    }
)
REQUIRED_GATES = (
    "installed-owner-and-candidate",
    "exact-live-service-acknowledgements",
    "authoritative-feelings-control",
    "request-pinned-state-and-version",
    "final-layer-capsule-once",
    "winning-native-provider-receipts",
    "direct-worker-scope-parity",
    "telegram-visible-semantic-grounding",
    "fallback-exact-capsule-and-capabilities",
    "phase-b-independent-continuity",
    "specialist-affect-independence",
    "disabled-state-safety",
    "private-state-and-plugin-isolation",
)
_DERIVED_PASS = object()
_DERIVATION_KEY = secrets.token_bytes(32)
_ISSUED_PASSES: dict[int, tuple[dict[str, object], str, str]] = {}


class _SemanticMismatch(Exception):
    def __init__(self, gate: str) -> None:
        super().__init__(gate)
        self.gate = gate


class _PrivateArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        raise ValueError("arguments-invalid")


class _LiveAuthority:
    def __init__(
        self,
        *,
        candidate_digest: str,
        artifact_digest: str,
        session: dict[str, object],
        service_status: dict[str, object],
        parent_control: ModuleType,
        parameters: dict[str, object],
    ) -> None:
        self.candidate_digest = candidate_digest
        self.artifact_digest = artifact_digest
        self.session = session
        self.service_status = service_status
        self.parent_control = parent_control
        self.parameters = parameters


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _invalid(message: str = "EMO-UC-047 semantic evidence is invalid") -> NoReturn:
    raise ValueError(message)


def _object(value: object, fields: frozenset[str] | set[str]) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != set(fields):
        _invalid()
    return value


def _hash(value: object, *, reference: bool = False) -> str:
    pattern = SHA256_REF if reference else SHA256
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        _invalid()
    return value


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        _invalid("EMO-UC-047 evidence timestamp is invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("EMO-UC-047 evidence timestamp is invalid") from exc
    if parsed.tzinfo is None:
        _invalid("EMO-UC-047 evidence timestamp is invalid")
    return parsed.astimezone(timezone.utc)


def _canonical_digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        _invalid("EMO-UC-047 installed owner authority is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def probe_live_authority(*, now: datetime | None = None) -> _LiveAuthority:
    """Read the real runtime owner and reuse its live QA-control trust chain."""

    forbidden_environment = {
        "VIVENTIUM_APP_SUPPORT_DIR",
        "VIVENTIUM_RUNTIME_DIR",
        "VIVENTIUM_RUNTIME_PROFILE",
        "VIVENTIUM_LOCAL_QA_CASE_ID",
        "VIVENTIUM_LOCAL_QA_CASE_TOKEN",
        "VIVENTIUM_LOCAL_QA_SESSION_REF",
        "VIVENTIUM_LOCAL_QA_MODE",
        "VIVENTIUM_LOCAL_QA_COMPONENT_ARTIFACT_DIGEST",
    }
    if any(name in os.environ for name in forbidden_environment):
        _invalid("EMO-UC-047 installed owner authority is unavailable")
    try:
        user_home = Path(pwd.getpwuid(os.getuid()).pw_dir).resolve(strict=True)
        support = user_home / "Library" / "Application Support" / "Viventium"
        runtime = support / "runtime"
        owner_path = support / "state" / "runtime" / "isolated" / "stack-owner.json"
        source_root = Path(__file__).resolve().parents[3]
        gate = _load_module(
            source_root / "scripts" / "viventium" / "parallel_work_release_gate.py",
            "emo047_parallel_work_release_gate",
        )
        if not gate.validate_runtime_owner_state_file(owner_path):
            _invalid("EMO-UC-047 installed owner authority is unavailable")
        control = _load_module(
            source_root / "scripts" / "viventium" / "local_qa_runtime_control.py",
            "emo047_local_qa_runtime_control",
        )
        _owner_raw, owner = control._read_private_json(
            owner_path, label="runtime owner", max_bytes=64 * 1024
        )
        if not isinstance(owner, dict):
            _invalid("EMO-UC-047 installed owner authority is unavailable")
        installed_root = Path(str(owner.get("repoRoot") or "")).resolve(strict=True)
        owner_support = Path(str(owner.get("appSupportDir") or "")).resolve(strict=True)
        if (
            installed_root != source_root
            or owner_support != support.resolve(strict=True)
            or owner.get("command") not in {"start", "launch"}
        ):
            _invalid("EMO-UC-047 installed owner authority is unavailable")
        parameters = {
            "state_path": runtime / "local-qa" / "active.json",
            "installed_root": installed_root,
            "artifact_identity_path": runtime / "parallel-work-artifact-identity.json",
            "local_qa_request_path": runtime / "parallel-work-local-qa-request.json",
        }
        session = control.active_session(**parameters, now=now)
        if session.get("caseId") != CASE_ID:
            _invalid("EMO-UC-047 installed owner session is invalid")
        status = control.require_restart_ready(**parameters, now=now)
        _identity_raw, identity = control._read_private_json(
            parameters["artifact_identity_path"],
            label="installed artifact identity",
            max_bytes=64 * 1024,
        )
        candidate, artifact = gate._qa_candidate_digests(identity)
        if (
            not isinstance(candidate, str)
            or SHA256.fullmatch(candidate) is None
            or not isinstance(artifact, str)
            or SHA256.fullmatch(artifact) is None
        ):
            _invalid("EMO-UC-047 installed candidate authority is invalid")
        parent = _load_module(
            installed_root / "scripts" / "viventium" / "feelings_qa_parent_control.py",
            "emo047_authoritative_feelings_parent_control",
        )
        return _LiveAuthority(
            candidate_digest=candidate,
            artifact_digest=artifact,
            session=session,
            service_status=status,
            parent_control=parent,
            parameters=parameters,
        )
    except (ImportError, KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
        raise ValueError("EMO-UC-047 installed owner authority is unavailable") from exc


def _private_root(path: Path) -> Path:
    supplied = Path(path).expanduser()
    try:
        if supplied.is_symlink():
            _invalid("EMO-UC-047 private evidence root is invalid")
        exact = supplied.resolve(strict=True)
        metadata = exact.stat()
    except (OSError, RuntimeError) as exc:
        raise ValueError("EMO-UC-047 private evidence root is invalid") from exc
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) & 0o077
    ):
        _invalid("EMO-UC-047 private evidence root is invalid")
    public_root = Path(__file__).resolve().parents[3]
    try:
        exact.relative_to(public_root)
    except ValueError:
        return exact
    _invalid("EMO-UC-047 private evidence cannot enter the public repository")


def _private_descriptor(relative_text: object, *, root: Path) -> tuple[int, str]:
    if not isinstance(relative_text, str) or not relative_text:
        _invalid("EMO-UC-047 private evidence path is invalid")
    relative = Path(relative_text)
    if (
        relative.is_absolute()
        or relative.as_posix() != relative_text
        or not relative.parts
        or any(SAFE_COMPONENT.fullmatch(part) is None for part in relative.parts)
    ):
        _invalid("EMO-UC-047 private evidence path is invalid")
    current = root
    try:
        for component in relative.parts[:-1]:
            current = current / component
            metadata = current.lstat()
            if (
                not stat.S_ISDIR(metadata.st_mode)
                or stat.S_ISLNK(metadata.st_mode)
                or metadata.st_uid != os.getuid()
                or stat.S_IMODE(metadata.st_mode) & 0o077
            ):
                _invalid("EMO-UC-047 private evidence path is invalid")
        target = root / relative
        if target.is_symlink() or target.resolve(strict=True) != target:
            _invalid("EMO-UC-047 private evidence path is invalid")
        descriptor = os.open(
            target,
            os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
        return descriptor, relative.as_posix()
    except (OSError, RuntimeError) as exc:
        raise ValueError("EMO-UC-047 private evidence path is invalid") from exc


def _live_status(authority: _LiveAuthority, *, run_at: datetime, now: datetime) -> None:
    session = authority.session
    if (
        not isinstance(session, dict)
        or session.get("caseId") != CASE_ID
        or session.get("mode") != "emo_uc_047"
    ):
        _invalid("EMO-UC-047 live session is invalid")
    started_at = _timestamp(session.get("startedAt"))
    expires_at = _timestamp(session.get("expiresAt"))
    if now >= expires_at:
        _invalid("EMO-UC-047 live session has expired")
    if run_at < started_at or run_at >= expires_at:
        _invalid("EMO-UC-047 evidence is outside its active session")
    status = _object(authority.service_status, LIVE_STATUS_FIELDS)
    if (
        status["caseId"] != CASE_ID
        or status["mode"] != session["mode"]
        or status["sessionRef"] != session["sessionRef"]
        or status["expiresAt"] != session["expiresAt"]
        or status["restartState"] != "ready"
        or status["requiredServices"] != list(REQUIRED_SERVICES)
        or status["acknowledgedServices"] != list(REQUIRED_SERVICES)
        or status["missingServices"] != []
        or SHA256_REF.fullmatch(str(status["serviceAckDigest"] or "")) is None
    ):
        _invalid("EMO-UC-047 live service acknowledgements are invalid")


def _verified_documents(
    raw_evidence: object,
    *,
    root: Path,
    authority: _LiveAuthority,
    now: datetime,
) -> tuple[dict[str, dict[str, object]], list[dict[str, str]], dict[str, object]]:
    if not isinstance(raw_evidence, list) or len(raw_evidence) != len(
        REQUIRED_EVIDENCE_KINDS
    ):
        _invalid()
    documents: dict[str, dict[str, object]] = {}
    receipt_evidence: list[dict[str, str]] = []
    seen_paths: set[str] = set()
    parent_result: dict[str, object] | None = None
    for raw_entry in raw_evidence:
        entry = _object(raw_entry, EVIDENCE_FIELDS)
        kind = entry["kind"]
        if (
            not isinstance(kind, str)
            or kind not in REQUIRED_EVIDENCE_KINDS
            or kind in documents
        ):
            _invalid()
        expected = _hash(entry["sha256"])
        descriptor, relative = _private_descriptor(entry["path"], root=root)
        try:
            raw, document = authority.parent_control.read_private_evidence_fd(descriptor)
            measured = hashlib.sha256(raw).hexdigest()
            if not hmac.compare_digest(measured, expected):
                _invalid("EMO-UC-047 private evidence digest is invalid")
            if not isinstance(document, dict) or relative in seen_paths:
                _invalid()
            seen_paths.add(relative)
            documents[kind] = document
            receipt_evidence.append(
                {"kind": kind, "path": relative, "sha256": measured}
            )
            if kind == "feelings_control_projection":
                os.lseek(descriptor, 0, os.SEEK_SET)
                parent_result = authority.parent_control.verify_installed_evidence(
                    **authority.parameters, evidence_fd=descriptor, now=now
                )
                if not isinstance(parent_result, dict) or parent_result.get(
                    "evidenceDigest"
                ) != "sha256:" + measured:
                    _invalid("EMO-UC-047 authoritative parent evidence is invalid")
        finally:
            os.close(descriptor)
    if set(documents) != REQUIRED_EVIDENCE_KINDS or parent_result is None:
        _invalid()
    return documents, sorted(
        receipt_evidence, key=lambda entry: (entry["kind"], entry["path"])
    ), parent_result


def _service_evidence(
    evidence: dict[str, object],
    *,
    authority: _LiveAuthority,
    run_at: datetime,
) -> None:
    service = _object(evidence, SERVICE_EVIDENCE_FIELDS)
    if service["contractVersion"] != CONTRACT_VERSION:
        _invalid("EMO-UC-047 service acknowledgement evidence is invalid")
    for field in LIVE_STATUS_FIELDS:
        if service[field] != authority.service_status[field]:
            _invalid("EMO-UC-047 live service acknowledgement or session is invalid")
    for field in ("artifactIdentityDigest", "componentArtifactDigest"):
        if service[field] != authority.session[field]:
            _invalid("EMO-UC-047 service artifact acknowledgement is invalid")
    observed = _timestamp(service["observedAt"])
    if observed < _timestamp(authority.session["startedAt"]) or observed > run_at:
        _invalid("EMO-UC-047 live service acknowledgement is stale")


def _require(condition: bool, gate: str) -> None:
    if not condition:
        raise _SemanticMismatch(gate)


def _nonnegative(value: object, gate: str) -> int:
    _require(isinstance(value, int) and not isinstance(value, bool) and value >= 0, gate)
    assert isinstance(value, int)
    return value


def _layer(
    evidence: object,
    *,
    request_ref: str,
    snapshot_hash: str,
    state_version: int | None,
    expected_count: int,
    gate: str,
    extra_fields: set[str] | None = None,
) -> dict[str, object]:
    fields = LAYER_FIELDS | (extra_fields or set())
    receipt = _object(evidence, fields)
    count = _nonnegative(receipt["capsuleOccurrenceCount"], gate)
    structural = _nonnegative(receipt["structuralLayerIndex"], gate)
    surface = _nonnegative(receipt["surfaceLayerIndex"], gate)
    final = _nonnegative(receipt["finalLayerIndex"], gate)
    trailing = _nonnegative(receipt["trailingInstructionChars"], gate)
    _require(
        receipt["requestRef"] == request_ref
        and receipt["snapshotHash"] == snapshot_hash
        and receipt["stateVersion"] == state_version
        and count == expected_count
        and structural < surface
        and trailing == 0,
        gate,
    )
    if expected_count:
        capsule_index = _nonnegative(receipt["capsuleLayerIndex"], gate)
        _require(
            receipt["capsuleSha256"] == snapshot_hash
            and surface < capsule_index
            and capsule_index == final,
            gate,
        )
    else:
        _require(
            receipt["capsuleSha256"] == "none"
            and receipt["capsuleLayerIndex"] is None
            and surface == final,
            gate,
        )
    return receipt


def _scenario_receipts(
    semantic: dict[str, object], parent: dict[str, object]
) -> dict[str, dict[str, object]]:
    raw_scenarios = semantic["scenarios"]
    _require(
        isinstance(raw_scenarios, list)
        and len(raw_scenarios) == len(parent["scenarios"]),
        "request-pinned-state-and-version",
    )
    expected = {str(item["name"]): item for item in parent["scenarios"]}
    scenarios: dict[str, dict[str, object]] = {}
    provider_refs: set[str] = set()
    for raw in raw_scenarios:
        scenario = _object(
            raw,
            {
                "name",
                "providerReceipt",
                "requestRef",
                "semanticReceipt",
                "snapshotHash",
                "sourceReceipt",
                "stateVersion",
                "workerReceipts",
            },
        )
        name = scenario["name"]
        _require(
            isinstance(name, str) and name in expected and name not in scenarios,
            "request-pinned-state-and-version",
        )
        owner = expected[name]
        enabled = owner["feelingsEnabled"] is True
        request_ref = str(owner["requestRef"])
        snapshot_hash = str(owner["snapshotHash"])
        version = scenario["stateVersion"]
        _require(
            scenario["requestRef"] == request_ref
            and scenario["snapshotHash"] == snapshot_hash
            and (
                isinstance(version, int) and not isinstance(version, bool) and version > 0
                if enabled
                else version is None
            ),
            "request-pinned-state-and-version" if enabled else "disabled-state-safety",
        )
        assert isinstance(version, int) or version is None
        main_count = 1 if enabled else 0
        _layer(
            scenario["sourceReceipt"],
            request_ref=request_ref,
            snapshot_hash=snapshot_hash,
            state_version=version,
            expected_count=main_count,
            gate="final-layer-capsule-once" if enabled else "disabled-state-safety",
        )
        provider = _layer(
            scenario["providerReceipt"],
            request_ref=request_ref,
            snapshot_hash=snapshot_hash,
            state_version=version,
            expected_count=main_count,
            gate="winning-native-provider-receipts" if enabled else "disabled-state-safety",
            extra_fields={"nativeRequestSha256", "outputKind", "receiptRef", "winning"},
        )
        owner_main = owner["winningNativeReceipt"]
        _require(
            provider["receiptRef"] == owner_main["receiptRef"]
            and provider["nativeRequestSha256"] == owner_main["nativeRequestSha256"]
            and provider["outputKind"] == owner_main["outputKind"]
            and provider["winning"] is True
            and provider["receiptRef"] not in provider_refs,
            "winning-native-provider-receipts",
        )
        provider_refs.add(str(provider["receiptRef"]))
        _worker_receipts(
            scenario,
            owner=owner,
            request_ref=request_ref,
            snapshot_hash=snapshot_hash,
            state_version=version,
            enabled=enabled,
        )
        _semantic_receipt(
            scenario,
            owner=owner,
            request_ref=request_ref,
            snapshot_hash=snapshot_hash,
            state_version=version,
            enabled=enabled,
        )
        scenarios[name] = scenario
    _require(
        set(scenarios) == set(expected), "request-pinned-state-and-version"
    )
    first = scenarios["all_agents_before_delegation"]
    second = scenarios["all_agents_during_workers"]
    _require(
        first["snapshotHash"] != second["snapshotHash"]
        and isinstance(first["stateVersion"], int)
        and isinstance(second["stateVersion"], int)
        and second["stateVersion"] > first["stateVersion"],
        "request-pinned-state-and-version",
    )
    return scenarios


def _worker_receipts(
    scenario: dict[str, object],
    *,
    owner: dict[str, object],
    request_ref: str,
    snapshot_hash: str,
    state_version: int | None,
    enabled: bool,
) -> None:
    raw_workers = scenario["workerReceipts"]
    owner_workers = owner["workers"]
    gate = "direct-worker-scope-parity" if enabled else "disabled-state-safety"
    _require(
        isinstance(raw_workers, list)
        and isinstance(owner_workers, list)
        and len(raw_workers) == len(owner_workers),
        gate,
    )
    expected = {str(worker["workerRef"]): worker for worker in owner_workers}
    seen: set[str] = set()
    runtimes: set[str] = set()
    count = 1 if enabled and owner["scope"] == "all_agents" else 0
    for raw in raw_workers:
        worker = _layer(
            raw,
            request_ref=request_ref,
            snapshot_hash=snapshot_hash,
            state_version=state_version,
            expected_count=count,
            gate=gate,
            extra_fields={
                "authoritySha256",
                "instructionSha256",
                "nativePlacement",
                "runRef",
                "runtime",
                "workerRef",
            },
        )
        worker_ref = worker["workerRef"]
        _require(
            isinstance(worker_ref, str)
            and worker_ref in expected
            and worker_ref not in seen,
            gate,
        )
        source = expected[worker_ref]
        native = source["nativeAuthorityReceipt"]
        _require(
            worker["runRef"] == native["runRef"]
            and worker["runtime"] == native["runtime"]
            and worker["authoritySha256"] == native["authoritySha256"]
            and worker["nativePlacement"] == native["placement"]
            and worker["instructionSha256"] == source["instructionSha256"],
            gate,
        )
        seen.add(worker_ref)
        runtimes.add(str(worker["runtime"]))
    _require(
        seen == set(expected)
        and (not raw_workers or runtimes == {"claude-code", "codex-cli"}),
        gate,
    )


def _semantic_receipt(
    scenario: dict[str, object],
    *,
    owner: dict[str, object],
    request_ref: str,
    snapshot_hash: str,
    state_version: int | None,
    enabled: bool,
) -> None:
    verdict = _object(
        scenario["semanticReceipt"],
        {
            "answerSha256",
            "inventedFeelingCount",
            "materiallyFollowsPinnedState",
            "privateCapsuleDisclosed",
            "requestRef",
            "rubricEvidenceSha256",
            "snapshotHash",
            "stateVersion",
            "status",
            "surface",
            "visibleAnswerCount",
        },
    )
    gate = "telegram-visible-semantic-grounding" if enabled else "disabled-state-safety"
    invented = _nonnegative(verdict["inventedFeelingCount"], gate)
    visible = _nonnegative(verdict["visibleAnswerCount"], gate)
    source = owner["semanticVerdict"]
    _require(
        verdict["requestRef"] == request_ref
        and verdict["snapshotHash"] == snapshot_hash
        and verdict["stateVersion"] == state_version
        and verdict["answerSha256"] == source["answerSha256"]
        and verdict["rubricEvidenceSha256"] == source["rubricEvidenceSha256"]
        and verdict["status"] == source["status"]
        and verdict["materiallyFollowsPinnedState"] is enabled
        and verdict["privateCapsuleDisclosed"] is False
        and verdict["surface"] == "telegram"
        and invented == 0
        and visible == 1,
        gate,
    )


def _fallback(
    semantic: dict[str, object],
    *,
    scenarios: dict[str, dict[str, object]],
    parent: dict[str, object],
) -> None:
    gate = "fallback-exact-capsule-and-capabilities"
    fallback = _object(
        semantic["fallbackContinuity"],
        {
            "attempts",
            "capsuleSha256",
            "declaredCapabilitiesSha256",
            "declaredCapabilityIds",
            "failureClass",
            "fallbackUsed",
            "requestRef",
            "retryAfterHonored",
            "snapshotHash",
            "stateVersion",
        },
    )
    first = scenarios["all_agents_before_delegation"]
    source = parent["requestIsolation"]["firstTypedFallback"]
    capability_ids = fallback["declaredCapabilityIds"]
    _require(
        isinstance(capability_ids, list)
        and 0 < len(capability_ids) <= 64
        and all(
            isinstance(item, str) and SAFE_CAPABILITY.fullmatch(item) is not None
            for item in capability_ids
        )
        and len(set(capability_ids)) == len(capability_ids),
        gate,
    )
    capability_digest = _canonical_digest(capability_ids)
    _require(
        fallback["requestRef"] == first["requestRef"]
        and fallback["snapshotHash"] == first["snapshotHash"]
        and fallback["stateVersion"] == first["stateVersion"]
        and fallback["capsuleSha256"] == first["snapshotHash"]
        and fallback["failureClass"] == source["failureClass"]
        and fallback["fallbackUsed"] is True
        and fallback["retryAfterHonored"] is True
        and fallback["declaredCapabilitiesSha256"] == capability_digest,
        gate,
    )
    raw_attempts = fallback["attempts"]
    _require(isinstance(raw_attempts, list) and len(raw_attempts) == 2, gate)
    refs: set[str] = set()
    native_receipts: set[str] = set()
    for raw, role in zip(raw_attempts, ("primary", "fallback"), strict=True):
        attempt = _layer(
            raw,
            request_ref=str(first["requestRef"]),
            snapshot_hash=str(first["snapshotHash"]),
            state_version=first["stateVersion"],
            expected_count=1,
            gate=gate,
            extra_fields={
                "attemptRef",
                "capabilitiesSha256",
                "capabilityIds",
                "failureClass",
                "nativeReceiptRef",
                "nativeRequestSha256",
                "outcome",
                "role",
            },
        )
        attempt_ref = attempt["attemptRef"]
        receipt_ref = attempt["nativeReceiptRef"]
        winning = role == "fallback"
        _require(
            attempt["role"] == role
            and isinstance(attempt_ref, str)
            and SHA256_REF.fullmatch(attempt_ref) is not None
            and attempt_ref not in refs
            and isinstance(receipt_ref, str)
            and NATIVE_RECEIPT_REF.fullmatch(receipt_ref) is not None
            and receipt_ref not in native_receipts
            and isinstance(attempt["nativeRequestSha256"], str)
            and SHA256.fullmatch(attempt["nativeRequestSha256"]) is not None
            and attempt["capabilityIds"] == capability_ids
            and attempt["capabilitiesSha256"] == capability_digest
            and attempt["outcome"] == ("won" if winning else "recoverable_failure")
            and attempt["failureClass"]
            == (None if winning else "provider_quota_exhausted"),
            gate,
        )
        if winning:
            provider = first["providerReceipt"]
            _require(
                receipt_ref == provider["receiptRef"]
                and attempt["nativeRequestSha256"]
                == provider["nativeRequestSha256"],
                gate,
            )
        refs.add(attempt_ref)
        native_receipts.add(receipt_ref)


def _phase_b(
    semantic: dict[str, object], scenarios: dict[str, dict[str, object]]
) -> None:
    gate = "phase-b-independent-continuity"
    second = scenarios["all_agents_during_workers"]
    phase_b = _layer(
        semantic["phaseBContinuity"],
        request_ref=str(second["requestRef"]),
        snapshot_hash=str(second["snapshotHash"]),
        state_version=second["stateVersion"],
        expected_count=1,
        gate=gate,
        extra_fields={
            "mainContinuityIdentitySha256",
            "mainNativeSessionRef",
            "mainWorkerInterrupted",
            "mainWorkerReplaced",
            "phaseBContinuityIdentitySha256",
            "phaseBNativeSessionRef",
            "receiptRef",
        },
    )
    main_session = phase_b["mainNativeSessionRef"]
    phase_session = phase_b["phaseBNativeSessionRef"]
    continuity = phase_b["mainContinuityIdentitySha256"]
    main_receipts = {
        item["providerReceipt"]["receiptRef"] for item in scenarios.values()
    }
    _require(
        isinstance(main_session, str)
        and SHA256_REF.fullmatch(main_session) is not None
        and isinstance(phase_session, str)
        and SHA256_REF.fullmatch(phase_session) is not None
        and main_session != phase_session
        and isinstance(continuity, str)
        and SHA256.fullmatch(continuity) is not None
        and phase_b["phaseBContinuityIdentitySha256"] == continuity
        and isinstance(phase_b["receiptRef"], str)
        and NATIVE_RECEIPT_REF.fullmatch(phase_b["receiptRef"]) is not None
        and phase_b["receiptRef"] not in main_receipts
        and phase_b["mainWorkerInterrupted"] is False
        and phase_b["mainWorkerReplaced"] is False,
        gate,
    )


def _specialists(
    semantic: dict[str, object], scenarios: dict[str, dict[str, object]]
) -> None:
    gate = "specialist-affect-independence"
    receipts = semantic["specialistReceipts"]
    _require(
        isinstance(receipts, list) and len(receipts) == len(REQUIRED_SPECIALISTS), gate
    )
    second = scenarios["all_agents_during_workers"]
    seen: set[str] = set()
    for raw in receipts:
        receipt = _object(
            raw,
            {
                "authoritySha256",
                "capsuleOccurrenceCount",
                "requestRef",
                "skipReason",
                "snapshotHash",
                "specialistId",
                "stateVersion",
            },
        )
        specialist = receipt["specialistId"]
        count = _nonnegative(receipt["capsuleOccurrenceCount"], gate)
        _require(
            isinstance(specialist, str)
            and specialist in REQUIRED_SPECIALISTS
            and specialist not in seen
            and receipt["requestRef"] == second["requestRef"]
            and receipt["snapshotHash"] == second["snapshotHash"]
            and receipt["stateVersion"] == second["stateVersion"]
            and isinstance(receipt["authoritySha256"], str)
            and SHA256.fullmatch(receipt["authoritySha256"]) is not None
            and receipt["skipReason"] == "specialist_cortex_independent"
            and count == 0,
            gate,
        )
        seen.add(specialist)
    _require(seen == REQUIRED_SPECIALISTS, gate)


def _privacy(semantic: dict[str, object], parent: dict[str, object]) -> None:
    gate = "private-state-and-plugin-isolation"
    audit = _object(
        semantic["privacyAudit"],
        {
            "deniedPluginIds",
            "feelingsMcpServerCount",
            "hostPluginDenylistEnabled",
            "privateCapsuleProjectionCount",
            "privateStateMountCount",
            "privateStatePersistenceCount",
            "unrelatedPluginsPreserved",
            "workerFeelingsPluginCount",
        },
    )
    owner = parent["safetyAudit"]
    _require(
        audit["hostPluginDenylistEnabled"] is True
        and owner["hostPluginDenylistEnabled"] is True
        and audit["deniedPluginIds"] == [DENIED_FEELINGS_PLUGIN_ID]
        and audit["unrelatedPluginsPreserved"] is True,
        gate,
    )
    for field in (
        "privateCapsuleProjectionCount",
        "privateStateMountCount",
        "privateStatePersistenceCount",
        "feelingsMcpServerCount",
        "workerFeelingsPluginCount",
    ):
        _require(_nonnegative(audit[field], gate) == 0, gate)
        if field in owner:
            _require(audit[field] == owner[field], gate)


def _derived_result_digest(result: dict[str, object]) -> str:
    return _canonical_digest(
        {
            "artifactDigest": result.get("artifactDigest"),
            "blockers": result.get("blockers"),
            "candidateDigest": result.get("candidateDigest"),
            "caseId": result.get("caseId"),
            "contractVersion": result.get("contractVersion"),
            "counts": result.get("counts"),
            "gates": result.get("gates"),
            "ready": result.get("ready"),
            "receiptEvidence": result.get("_receiptEvidence"),
            "runAt": result.get("runAt"),
            "serviceAckDigest": result.get("serviceAckDigest"),
            "status": result.get("status"),
            "surface": result.get("surface"),
        }
    )


def assess_manifest(
    manifest: object,
    *,
    evidence_root: Path,
    expected_candidate_digest: str,
    expected_artifact_digest: str,
    installed_owner_proven: bool,
    now: datetime | None = None,
) -> dict[str, object]:
    """Return a derived installed result; caller assertions never establish PASS."""

    if (
        installed_owner_proven is not True
        or not isinstance(expected_candidate_digest, str)
        or SHA256.fullmatch(expected_candidate_digest) is None
        or not isinstance(expected_artifact_digest, str)
        or SHA256.fullmatch(expected_artifact_digest) is None
    ):
        _invalid("EMO-UC-047 installed candidate or owner binding is invalid")
    payload = _object(manifest, MANIFEST_FIELDS)
    if (
        payload["caseId"] != CASE_ID
        or payload["contractVersion"] != CONTRACT_VERSION
        or payload["environment"] != "installed_local_production"
    ):
        _invalid()
    candidate = _object(payload["candidate"], {"artifactDigest", "candidateDigest"})
    if (
        candidate["candidateDigest"] != expected_candidate_digest
        or candidate["artifactDigest"] != expected_artifact_digest
    ):
        _invalid("EMO-UC-047 installed candidate binding is invalid")
    checked_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    run_at = _timestamp(payload["runAt"])
    if run_at > checked_at + MAX_FUTURE_SKEW or checked_at - run_at > MAX_RESULT_AGE:
        _invalid("EMO-UC-047 evidence timestamp is stale or in the future")
    root = _private_root(evidence_root)
    authority = probe_live_authority(now=checked_at)
    if (
        not isinstance(authority, _LiveAuthority)
        or authority.candidate_digest != expected_candidate_digest
        or authority.artifact_digest != expected_artifact_digest
    ):
        _invalid("EMO-UC-047 installed candidate or owner binding is invalid")
    _live_status(authority, run_at=run_at, now=checked_at)
    documents, evidence, parent_result = _verified_documents(
        payload["evidence"], root=root, authority=authority, now=checked_at
    )
    parent = documents["feelings_control_projection"]
    expected_parent = {
        "candidateBound": True,
        "caseId": CASE_ID,
        "componentArtifactDigest": authority.session["componentArtifactDigest"],
        "evidenceDigest": "sha256:"
        + next(
            item["sha256"]
            for item in evidence
            if item["kind"] == "feelings_control_projection"
        ),
        "mainReceiptCount": 4,
        "requestPinned": True,
        "scenarioCount": 4,
        "semanticPassCount": 4,
        "sessionRef": authority.session["sessionRef"],
        "status": "verified",
        "workerReceiptCount": 6,
    }
    if parent_result != expected_parent:
        _invalid("EMO-UC-047 authoritative parent evidence is invalid")
    _service_evidence(
        documents["feelings_service_acknowledgement"],
        authority=authority,
        run_at=run_at,
    )
    semantic = _object(documents["feelings_semantic_receipts"], SEMANTIC_FIELDS)
    if (
        semantic["caseId"] != CASE_ID
        or semantic["contractVersion"] != CONTRACT_VERSION
        or semantic["sessionRef"] != authority.session["sessionRef"]
        or semantic["artifactIdentityDigest"]
        != authority.session["artifactIdentityDigest"]
        or semantic["componentArtifactDigest"]
        != authority.session["componentArtifactDigest"]
    ):
        _invalid("EMO-UC-047 semantic evidence session or artifact is invalid")

    failed_gate: str | None = None
    try:
        scenarios = _scenario_receipts(semantic, parent)
        _fallback(semantic, scenarios=scenarios, parent=parent)
        _phase_b(semantic, scenarios)
        _specialists(semantic, scenarios)
        _privacy(semantic, parent)
    except _SemanticMismatch as exc:
        failed_gate = exc.gate

    gates = [
        {
            "id": gate,
            "status": (
                "PASS"
                if failed_gate is None
                or REQUIRED_GATES.index(gate) < REQUIRED_GATES.index(failed_gate)
                else "FAIL" if gate == failed_gate else "BLOCKED"
            ),
        }
        for gate in REQUIRED_GATES
    ]
    blockers = [str(gate["id"]) for gate in gates if gate["status"] != "PASS"]
    ready = failed_gate is None
    result: dict[str, object] = {
        "_receiptEvidence": evidence,
        "artifactDigest": expected_artifact_digest,
        "blockers": blockers,
        "candidateDigest": expected_candidate_digest,
        "caseId": CASE_ID,
        "contractVersion": CONTRACT_VERSION,
        "counts": {
            "fallbackAttemptCount": 2,
            "mainReceiptCount": int(parent_result["mainReceiptCount"]),
            "phaseBReceiptCount": 1,
            "scenarioCount": int(parent_result["scenarioCount"]),
            "semanticPassCount": int(parent_result["semanticPassCount"]),
            "specialistReceiptCount": len(REQUIRED_SPECIALISTS),
            "workerReceiptCount": int(parent_result["workerReceiptCount"]),
        },
        "gates": gates,
        "ready": ready,
        "runAt": run_at.isoformat(),
        "serviceAckDigest": authority.service_status["serviceAckDigest"],
        "status": "PASS" if ready else "FAIL",
        "surface": "telegram",
    }
    result["_derivationDigest"] = _derived_result_digest(result)
    result["_derivedPass"] = _DERIVED_PASS if ready else None
    if ready:
        seal = hmac.new(
            _DERIVATION_KEY,
            str(result["_derivationDigest"]).encode("ascii"),
            hashlib.sha256,
        ).hexdigest()
        result["_derivationSeal"] = seal
        if len(_ISSUED_PASSES) >= 128:
            _ISSUED_PASSES.pop(next(iter(_ISSUED_PASSES)))
        _ISSUED_PASSES[id(result)] = (result, str(result["_derivationDigest"]), seal)
    return result


def receipt_manifest(*, result: dict[str, object]) -> dict[str, object]:
    """Accept only the exact untampered PASS object derived in this process."""

    if not isinstance(result, dict):
        _invalid("EMO-UC-047 derived PASS is invalid")
    issued = _ISSUED_PASSES.get(id(result))
    gates = result.get("gates")
    evidence = result.get("_receiptEvidence")
    try:
        digest = _derived_result_digest(result)
    except (TypeError, ValueError):
        _invalid("EMO-UC-047 derived PASS is invalid")
    expected_seal = hmac.new(
        _DERIVATION_KEY, digest.encode("ascii"), hashlib.sha256
    ).hexdigest()
    if (
        issued is None
        or issued[0] is not result
        or result.get("_derivedPass") is not _DERIVED_PASS
        or not isinstance(result.get("_derivationDigest"), str)
        or not hmac.compare_digest(str(result["_derivationDigest"]), digest)
        or not hmac.compare_digest(digest, issued[1])
        or not isinstance(result.get("_derivationSeal"), str)
        or not hmac.compare_digest(str(result["_derivationSeal"]), issued[2])
        or not hmac.compare_digest(str(result["_derivationSeal"]), expected_seal)
        or result.get("caseId") != CASE_ID
        or result.get("contractVersion") != CONTRACT_VERSION
        or result.get("status") != "PASS"
        or result.get("surface") != "telegram"
        or result.get("ready") is not True
        or result.get("blockers") != []
        or not isinstance(gates, list)
        or len(gates) != len(REQUIRED_GATES)
        or [gate.get("id") for gate in gates if isinstance(gate, dict)]
        != list(REQUIRED_GATES)
        or any(
            not isinstance(gate, dict) or gate.get("status") != "PASS" for gate in gates
        )
        or not isinstance(evidence, list)
        or len(evidence) != len(REQUIRED_EVIDENCE_KINDS)
    ):
        _invalid("EMO-UC-047 derived PASS is invalid")
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in evidence:
        entry = _object(raw, EVIDENCE_FIELDS)
        kind = entry["kind"]
        relative = entry["path"]
        if (
            not isinstance(kind, str)
            or kind not in REQUIRED_EVIDENCE_KINDS
            or kind in seen
            or not isinstance(relative, str)
            or not relative
            or Path(relative).is_absolute()
            or any(
                SAFE_COMPONENT.fullmatch(part) is None for part in Path(relative).parts
            )
        ):
            _invalid("EMO-UC-047 derived PASS is invalid")
        try:
            measured = _hash(entry["sha256"])
        except ValueError:
            _invalid("EMO-UC-047 derived PASS is invalid")
        normalized.append({"kind": kind, "path": relative, "sha256": measured})
        seen.add(kind)
    if (
        seen != REQUIRED_EVIDENCE_KINDS
        or normalized != sorted(normalized, key=lambda item: (item["kind"], item["path"]))
    ):
        _invalid("EMO-UC-047 derived PASS is invalid")
    return {
        "caseId": CASE_ID,
        "contractVersion": CONTRACT_VERSION,
        "evidence": normalized,
        "runAt": _timestamp(result.get("runAt")).isoformat(),
        "status": "PASS",
        "surface": "telegram",
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = _PrivateArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    arguments = list(argv) if argv is not None else sys.argv[1:]
    try:
        supplied_options = [
            option.split("=", 1)[0]
            for option in arguments
            if option.startswith("--")
        ]
        if len(supplied_options) != len(set(supplied_options)):
            raise ValueError("arguments-invalid")
        parsed = parser.parse_args(arguments)
    except (TypeError, ValueError):
        print("EMO-UC-047 arguments are invalid.", file=sys.stderr)
        return 2

    checked_at = _utc_now()
    try:
        authority = probe_live_authority(now=checked_at)
    except (ImportError, OSError, RuntimeError, TypeError, ValueError):
        print(
            json.dumps(
                {
                    "blockers": ["live-authority-unavailable"],
                    "caseId": CASE_ID,
                    "status": "BLOCKED",
                },
                sort_keys=True,
            )
        )
        return 2

    try:
        evidence_root = _private_root(parsed.evidence_root)
        manifest_path = parsed.manifest
        relative_path = (
            manifest_path.relative_to(evidence_root)
            if manifest_path.is_absolute()
            else manifest_path
        )
        descriptor, _relative = _private_descriptor(
            relative_path.as_posix(), root=evidence_root
        )
        try:
            _raw, manifest = authority.parent_control.read_private_evidence_fd(
                descriptor
            )
        finally:
            os.close(descriptor)
        result = assess_manifest(
            manifest,
            evidence_root=evidence_root,
            expected_candidate_digest=authority.candidate_digest,
            expected_artifact_digest=authority.artifact_digest,
            installed_owner_proven=True,
            now=checked_at,
        )
    except (ImportError, KeyError, OSError, RuntimeError, TypeError, ValueError):
        print(
            json.dumps(
                {
                    "blockers": ["installed-semantic-evidence-invalid"],
                    "caseId": CASE_ID,
                    "status": "BLOCKED",
                },
                sort_keys=True,
            )
        )
        return 2

    public_result = {
        key: value for key, value in result.items() if not key.startswith("_")
    }
    print(json.dumps(public_result, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

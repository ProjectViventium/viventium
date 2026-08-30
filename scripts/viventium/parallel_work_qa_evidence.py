#!/usr/bin/env python3
"""Write verified local QA receipts or externally authenticated release evidence."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import json
import os
import re
import secrets
import stat
import sys
import tempfile
from collections.abc import Callable, Iterable
from datetime import datetime, timedelta, timezone
from pathlib import Path

CONTRACT_VERSION = 1
MAX_EVIDENCE_FILES = 64
MAX_EVIDENCE_FILE_BYTES = 100 * 1024 * 1024
MAX_VERIFIER_MANIFEST_BYTES = 256 * 1024
MAX_FUTURE_SKEW = timedelta(seconds=60)
RECEIPT_TTL = timedelta(hours=24)
SAFE_KIND = re.compile(r"[a-z][a-z0-9_-]{0,63}")
SHA256 = re.compile(r"[a-f0-9]{64}")
SHA256_REF = re.compile(r"sha256:[a-f0-9]{64}")
BASE_RECEIPT_FIELDS = {
    "artifactDigest",
    "candidateDigest",
    "caseId",
    "evidenceDigest",
    "runAt",
    "status",
    "surface",
}
SERVICE_ACK_REQUIRED_SERVICES = {
    "TR-026": ("librechat-core", "telegram-bot"),
    "EMO-UC-047": ("glasshive-runtime", "librechat-core"),
    "EMO-UC-048": ("librechat-core", "telegram-bot"),
    "PWK-UC-016": ("glasshive-runtime", "librechat-core", "telegram-bot"),
    "PWK-UC-017": ("glasshive-runtime", "librechat-core", "telegram-bot"),
    "REL-UC-004": ("librechat-core",),
}
MANIFEST_FIELDS = {
    "caseId",
    "contractVersion",
    "evidence",
    "runAt",
    "status",
    "surface",
}
PASS_MANIFEST_FIELDS = MANIFEST_FIELDS | {"verifier"}
VERIFIER_FIELDS = {"id", "manifest"}
EVIDENCE_FIELDS = {"kind", "path", "sha256"}
ALLOWED_STATUSES = {"PASS", "PARTIAL", "FAIL", "BLOCKED"}
VERIFIER_FORBIDDEN_ENVIRONMENT = {
    "PYTHONHOME",
    "PYTHONINSPECT",
    "PYTHONPATH",
    "PYTHONSTARTUP",
    "PYTHONUSERBASE",
    "VIVENTIUM_APP_SUPPORT_DIR",
    "VIVENTIUM_LOCAL_QA_CASE_ID",
    "VIVENTIUM_LOCAL_QA_CASE_TOKEN",
    "VIVENTIUM_LOCAL_QA_COMPONENT_ARTIFACT_DIGEST",
    "VIVENTIUM_LOCAL_QA_MODE",
    "VIVENTIUM_LOCAL_QA_SESSION_REF",
    "VIVENTIUM_RUNTIME_DIR",
    "VIVENTIUM_RUNTIME_PROFILE",
}


class ExternalReleaseEvidenceSigningAuthority:
    """Explicitly supplied protected signers; runtime files never create trust.

    ``verification_authority`` must already bind a publisher-verified installed
    trust policy and an independently protected anti-rollback witness. Producer
    and service callbacks return actual producer-signed observations; this
    process must never synthesize their signatures or generate publisher keys.
    """

    __slots__ = (
        "installed_root",
        "runtime_owner_state",
        "verification_authority",
        "publisher_signer",
        "producer_attestor",
        "service_attestor",
    )

    def __init__(
        self,
        *,
        installed_root: Path,
        runtime_owner_state: Path,
        verification_authority: object,
        publisher_signer: object,
        producer_attestor: Callable[[dict[str, object]], Iterable[dict[str, object]]],
        service_attestor: Callable[
            [dict[str, object], dict[str, object]], Iterable[dict[str, object]]
        ]
        | None = None,
    ) -> None:
        self.installed_root = installed_root
        self.runtime_owner_state = runtime_owner_state
        self.verification_authority = verification_authority
        self.publisher_signer = publisher_signer
        self.producer_attestor = producer_attestor
        self.service_attestor = service_attestor


def _load_release_gate():
    path = Path(__file__).with_name("parallel_work_release_gate.py").resolve(strict=True)
    cached = sys.modules.get("parallel_work_release_gate")
    if cached is not None:
        try:
            cached_path = Path(str(cached.__file__)).resolve(strict=True)
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
            raise RuntimeError("release gate module provenance is invalid") from exc
        if cached_path != path:
            raise RuntimeError("release gate module provenance is invalid")
        return cached
    spec = importlib.util.spec_from_file_location("parallel_work_release_gate", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("release gate module is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_local_qa_control():
    path = Path(__file__).with_name("local_qa_runtime_control.py").resolve(strict=True)
    cached = sys.modules.get("local_qa_runtime_control_for_qa_evidence")
    if cached is not None:
        try:
            cached_path = Path(str(cached.__file__)).resolve(strict=True)
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
            raise RuntimeError("local-QA runtime control provenance is invalid") from exc
        if cached_path != path:
            raise RuntimeError("local-QA runtime control provenance is invalid")
        return cached
    spec = importlib.util.spec_from_file_location(
        "local_qa_runtime_control_for_qa_evidence", path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("local-QA runtime control is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


REGISTERED_SEMANTIC_VERIFIERS = _load_release_gate().REGISTERED_SEMANTIC_VERIFIERS


@contextlib.contextmanager
def _sanitized_verifier_environment():
    preserved = {
        name: os.environ[name]
        for name in VERIFIER_FORBIDDEN_ENVIRONMENT
        if name in os.environ
    }
    try:
        for name in VERIFIER_FORBIDDEN_ENVIRONMENT:
            os.environ.pop(name, None)
        yield
    finally:
        for name in VERIFIER_FORBIDDEN_ENVIRONMENT:
            os.environ.pop(name, None)
        os.environ.update(preserved)


def _canonical_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _load_json(path: Path, *, missing: object = None) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return missing
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON evidence input: {path.name}") from exc


def _inside(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def _parse_timestamp(value: object, *, now: datetime) -> str:
    try:
        parsed = datetime.fromisoformat(str(value or ""))
    except ValueError as exc:
        raise ValueError("QA evidence timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise ValueError("QA evidence timestamp must include a timezone")
    parsed = parsed.astimezone(timezone.utc)
    if parsed > now + MAX_FUTURE_SKEW or now - parsed > RECEIPT_TTL:
        raise ValueError("QA evidence timestamp is stale or in the future")
    return parsed.isoformat()


def _verified_evidence(
    manifest: dict[str, object], evidence_root: Path
) -> list[dict[str, str]]:
    raw = manifest.get("evidence")
    if not isinstance(raw, list) or not raw or len(raw) > MAX_EVIDENCE_FILES:
        raise ValueError("QA evidence must contain a bounded non-empty file list")
    verified: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict) or set(item) != EVIDENCE_FIELDS:
            raise ValueError("QA evidence entry is invalid")
        kind = str(item.get("kind") or "")
        relative_text = str(item.get("path") or "")
        expected_digest = str(item.get("sha256") or "")
        relative = Path(relative_text)
        if SAFE_KIND.fullmatch(kind) is None:
            raise ValueError("QA evidence kind is invalid")
        if relative.is_absolute() or not relative_text or ".." in relative.parts:
            raise ValueError("QA evidence files must stay inside the private evidence root")
        try:
            exact = (evidence_root / relative).resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise ValueError("QA evidence file is unavailable") from exc
        if not _inside(exact, evidence_root) or not exact.is_file():
            raise ValueError("QA evidence files must stay inside the private evidence root")
        canonical_relative = exact.relative_to(evidence_root).as_posix()
        if canonical_relative in seen:
            raise ValueError("QA evidence file is duplicated")
        seen.add(canonical_relative)
        if exact.stat().st_size > MAX_EVIDENCE_FILE_BYTES:
            raise ValueError("QA evidence file exceeds the size limit")
        measured = hashlib.sha256(exact.read_bytes()).hexdigest()
        if SHA256.fullmatch(expected_digest) is None or measured != expected_digest:
            raise ValueError("QA evidence file digest did not match")
        verified.append(
            {"kind": kind, "path": canonical_relative, "sha256": measured}
        )
    return sorted(verified, key=lambda item: (item["kind"], item["path"]))


def _load_registered_verifier(path: Path, *, case_id: str):
    module_name = f"parallel_work_qa_evidence_verifier_{case_id.lower().replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ValueError("registered semantic verifier is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except (ImportError, OSError, RuntimeError) as exc:
        raise ValueError("registered semantic verifier is unavailable") from exc
    return module


def _private_verifier_manifest_snapshot(path: Path) -> tuple[object, str]:
    """Parse and hash the exact same stable, owner-only manifest bytes."""

    flags = (
        os.O_RDONLY
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise ValueError("semantic verifier manifest must be private") from exc
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or stat.S_IMODE(before.st_mode) != 0o600
            or before.st_nlink != 1
            or (hasattr(os, "getuid") and before.st_uid != os.getuid())
            or before.st_size <= 0
            or before.st_size > MAX_VERIFIER_MANIFEST_BYTES
        ):
            raise ValueError("semantic verifier manifest must be private")
        raw = os.read(descriptor, MAX_VERIFIER_MANIFEST_BYTES + 1)
        after = os.fstat(descriptor)
        visible = path.stat(follow_symlinks=False)
        identity = lambda info: (
            info.st_dev,
            info.st_ino,
            info.st_mode,
            info.st_uid,
            info.st_nlink,
            info.st_size,
            info.st_mtime_ns,
            info.st_ctime_ns,
        )
        if (
            len(raw) != before.st_size
            or identity(before) != identity(after)
            or identity(after) != identity(visible)
        ):
            raise ValueError("semantic verifier manifest changed during verification")
    except OSError as exc:
        raise ValueError("semantic verifier manifest changed during verification") from exc
    finally:
        os.close(descriptor)
    try:
        parsed = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("semantic verifier manifest is invalid") from exc
    return parsed, hashlib.sha256(raw).hexdigest()


def _derive_registered_pass(
    *,
    case_id: str,
    verifier_claim: object,
    evidence_root: Path,
    candidate_digest: str,
    artifact_digest: str,
    caller_run_at: str,
    caller_surface: str,
    caller_evidence: list[dict[str, str]],
    installed_owner_proven: bool,
    now: datetime,
) -> dict[str, str]:
    registration = REGISTERED_SEMANTIC_VERIFIERS.get(case_id)
    if registration is None:
        raise ValueError("PASS requires a registered semantic verifier")
    if not isinstance(verifier_claim, dict) or set(verifier_claim) != VERIFIER_FIELDS:
        raise ValueError("PASS semantic verifier claim is invalid")
    if verifier_claim.get("id") != registration["id"]:
        raise ValueError("PASS semantic verifier is not registered for this case")
    relative_text = str(verifier_claim.get("manifest") or "")
    relative = Path(relative_text)
    if relative.is_absolute() or not relative_text or ".." in relative.parts:
        raise ValueError("semantic verifier manifest must stay inside the evidence root")
    supplied = evidence_root / relative
    try:
        if supplied.is_symlink():
            raise ValueError("semantic verifier manifest must be a private evidence file")
        exact_manifest = supplied.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ValueError("semantic verifier manifest is unavailable") from exc
    if (
        not _inside(exact_manifest, evidence_root)
        or not exact_manifest.is_file()
        or exact_manifest.stat().st_size <= 0
        or exact_manifest.stat().st_size > MAX_VERIFIER_MANIFEST_BYTES
        or exact_manifest.stat().st_nlink != 1
    ):
        raise ValueError("semantic verifier manifest must stay inside the evidence root")
    verified_manifest, manifest_digest = _private_verifier_manifest_snapshot(
        exact_manifest
    )
    verifier_path = Path(__file__).resolve().parents[2] / Path(str(registration["path"]))
    try:
        with _sanitized_verifier_environment():
            verifier = _load_registered_verifier(verifier_path, case_id=case_id)
            result = verifier.assess_manifest(
                verified_manifest,
                evidence_root=evidence_root,
                expected_candidate_digest=candidate_digest,
                expected_artifact_digest=artifact_digest,
                installed_owner_proven=installed_owner_proven,
                now=now,
            )
            derived = verifier.receipt_manifest(result=result)
    except Exception as exc:
        raise ValueError("registered semantic verifier did not derive PASS") from exc
    if not isinstance(derived, dict) or set(derived) != MANIFEST_FIELDS:
        raise ValueError("registered semantic verifier returned an invalid receipt manifest")
    if (
        derived.get("contractVersion") != CONTRACT_VERSION
        or derived.get("caseId") != case_id
        or derived.get("status") != "PASS"
        or derived.get("surface") != caller_surface
    ):
        raise ValueError("registered semantic verifier result does not match the QA case")
    derived_run_at = _parse_timestamp(derived.get("runAt"), now=now)
    derived_evidence = _verified_evidence(derived, evidence_root)
    if derived_run_at != caller_run_at or derived_evidence != caller_evidence:
        raise ValueError("caller evidence does not match the semantic verifier result")
    return {
        "id": str(registration["id"]),
        "manifestSha256": manifest_digest,
    }


def _validate_existing_receipts(
    value: object,
    *,
    attestation_authority: tuple[bytes, str] | None,
    external_context: tuple[object, object, Path, object, str] | None = None,
    candidate_digest: str = "",
    artifact_digest: str = "",
    artifact_identity: object = None,
    recovering_revoked_case_id: str | None = None,
    now: datetime | None = None,
) -> list[dict[str, object]]:
    if value is None:
        return []
    if (
        not isinstance(value, dict)
        or set(value) != {"contractVersion", "receipts"}
        or value.get("contractVersion") != CONTRACT_VERSION
        or not isinstance(value.get("receipts"), list)
    ):
        raise ValueError("existing QA receipt set is invalid")
    gate = _load_release_gate()
    receipts: list[dict[str, object]] = []
    seen: set[str] = set()
    seen_nonces: set[str] = set()
    for receipt in value["receipts"]:
        if not isinstance(receipt, dict):
            raise ValueError("existing QA receipt is invalid")
        case_id = str(receipt.get("caseId") or "")
        externally_signed = "publisherAttestation" in receipt
        uses_artifact_claims = "artifactClaims" in receipt
        expected_fields = set(BASE_RECEIPT_FIELDS)
        if receipt.get("status") == "PASS":
            if externally_signed:
                expected_fields.update(
                    gate.QA_RECEIPT_EXTERNAL_ATTESTATION_FIELDS
                    | (gate.QA_RECEIPT_ATTESTATION_FIELDS - {"attestation"})
                )
            else:
                expected_fields.update(gate.QA_RECEIPT_ATTESTATION_FIELDS)
                if uses_artifact_claims:
                    expected_fields.add("artifactClaims")
            if case_id in SERVICE_ACK_REQUIRED_SERVICES:
                expected_fields.update(("serviceAckDigest", "serviceAckSessionRef"))
        if set(receipt) != expected_fields:
            raise ValueError("existing QA receipt is invalid")
        if receipt.get("status") == "PASS" and not externally_signed:
            if uses_artifact_claims:
                if not gate._qa_receipt_artifact_claims_match(
                    case_id,
                    receipt.get("artifactClaims"),
                    artifact_identity,
                ):
                    raise ValueError(
                        "existing QA receipt artifact claims do not match the active identity"
                    )
            elif receipt.get("artifactDigest") != artifact_digest:
                raise ValueError(
                    "existing QA receipt artifact does not match the active identity"
                )
        if "serviceAckDigest" in expected_fields and (
            SHA256_REF.fullmatch(str(receipt.get("serviceAckDigest") or ""))
            is None
            or gate.QA_RECEIPT_SERVICE_SESSION.fullmatch(
                str(receipt.get("serviceAckSessionRef") or "")
            )
            is None
        ):
            raise ValueError("existing QA receipt is invalid")
        if receipt.get("status") == "PASS":
            if external_context is not None and not externally_signed:
                raise ValueError("existing external QA receipt attestation is missing")
            nonce = str(receipt.get("receiptNonce") or "")
            if gate.QA_RECEIPT_NONCE.fullmatch(nonce) is None or nonce in seen_nonces:
                raise ValueError("existing QA receipt attestation is invalid")
            if externally_signed:
                if external_context is None:
                    raise ValueError("existing external QA receipt authority is unavailable")
                sidecar, policy, ledger, witness, owner_binding = external_context
                registration = gate.REGISTERED_SEMANTIC_VERIFIERS.get(case_id)
                if registration is None:
                    raise ValueError("existing external QA receipt verifier is invalid")
                try:
                    sidecar.verify_release_receipt(
                        receipt,
                        policy=policy,
                        ledger_path=ledger,
                        ledger_witness=witness,
                        expected_case_id=case_id,
                        expected_surface=str(receipt.get("surface") or ""),
                        expected_candidate_digest=candidate_digest,
                        expected_artifact_digest=artifact_digest,
                        expected_owner_binding=owner_binding,
                        expected_verifier_id=str(registration["id"]),
                        expected_verifier_manifest_sha256=str(
                            receipt.get("verifierManifestSha256") or ""
                        ),
                        expected_evidence_digest=str(receipt.get("evidenceDigest") or ""),
                        expected_service_ack_digest=(
                            str(receipt["serviceAckDigest"])
                            if case_id in SERVICE_ACK_REQUIRED_SERVICES
                            else None
                        ),
                        expected_service_ack_session_ref=(
                            str(receipt["serviceAckSessionRef"])
                            if case_id in SERVICE_ACK_REQUIRED_SERVICES
                            else None
                        ),
                        now=now,
                    )
                except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
                    if (
                        case_id == recovering_revoked_case_id
                        and isinstance(exc, sidecar.ReceiptSupersededError)
                    ):
                        if case_id in seen:
                            raise ValueError(
                                "existing QA receipt set contains duplicate cases"
                            ) from exc
                        seen.add(case_id)
                        seen_nonces.add(nonce)
                        continue
                    raise ValueError(
                        "existing external QA receipt attestation is invalid"
                    ) from exc
            elif not gate._qa_receipt_attestation_valid(
                receipt, attestation_authority
            ):
                raise ValueError("existing QA receipt attestation is invalid")
            seen_nonces.add(nonce)
        if not case_id or case_id in seen:
            raise ValueError("existing QA receipt set contains duplicate cases")
        seen.add(case_id)
        receipts.append(dict(receipt))
    return receipts


def record_case_receipt(
    *,
    manifest_path: Path,
    evidence_root: Path,
    artifact_identity: object,
    existing_receipts: object,
    required_case_ids: set[str],
    local_qa_request: object,
    service_ack_status: object = None,
    service_ack_validator: Callable[[], object] | None = None,
    attestation_authority: tuple[bytes, str] | None = None,
    external_attestation_authority: ExternalReleaseEvidenceSigningAuthority | None = None,
    require_external_attestation: bool = False,
    installed_owner_proven: bool = False,
    now: datetime | None = None,
) -> dict[str, object]:
    if local_qa_request != {
        "contractVersion": CONTRACT_VERSION,
        "mode": "local-qa",
        "requested": True,
    }:
        raise ValueError("an active explicit local QA request is required")
    gate = _load_release_gate()
    candidate_digest, artifact_digest = gate._qa_candidate_digests(artifact_identity)
    if not candidate_digest or not artifact_digest:
        raise ValueError("installed candidate identity is unavailable")
    external_context: tuple[object, object, Path, object, str] | None = None
    if external_attestation_authority is not None:
        if not isinstance(
            external_attestation_authority, ExternalReleaseEvidenceSigningAuthority
        ):
            raise ValueError("external release attestation authority is invalid")
        if not callable(
            getattr(external_attestation_authority.publisher_signer, "sign", None)
        ) or not callable(external_attestation_authority.producer_attestor):
            raise ValueError("external release attestation signing authority is unavailable")
        resolved = gate._external_release_attestation_context(
            external_attestation_authority.verification_authority,
            installed_root=external_attestation_authority.installed_root,
            runtime_owner_state=external_attestation_authority.runtime_owner_state,
            candidate_digest=candidate_digest,
        )
        owner_binding = gate._qa_receipt_owner_binding(
            external_attestation_authority.installed_root,
            external_attestation_authority.runtime_owner_state,
        )
        if resolved is None or SHA256.fullmatch(owner_binding) is None:
            raise ValueError("external release attestation authority is unavailable")
        external_context = (*resolved, owner_binding)
    elif require_external_attestation:
        raise ValueError("external release attestation authority is unavailable")
    try:
        exact_root = evidence_root.expanduser().resolve(strict=True)
        exact_manifest = manifest_path.expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ValueError("private QA evidence is unavailable") from exc
    if not exact_root.is_dir() or not _inside(exact_manifest, exact_root):
        raise ValueError("QA evidence manifest must be inside the private evidence root")
    manifest = _load_json(exact_manifest)
    if not isinstance(manifest, dict):
        raise ValueError("QA evidence manifest is invalid")
    declared_status = str(manifest.get("status") or "")
    expected_manifest_fields = (
        PASS_MANIFEST_FIELDS if declared_status == "PASS" else MANIFEST_FIELDS
    )
    if set(manifest) != expected_manifest_fields:
        raise ValueError("QA evidence manifest is invalid")
    if manifest.get("contractVersion") != CONTRACT_VERSION:
        raise ValueError("QA evidence manifest contract is unsupported")
    case_id = str(manifest.get("caseId") or "")
    if case_id not in required_case_ids:
        raise ValueError("QA evidence does not name a required QA case")
    status = str(manifest.get("status") or "")
    surface = str(manifest.get("surface") or "")
    if status not in ALLOWED_STATUSES:
        raise ValueError("QA evidence status is invalid")
    if surface not in gate.QA_RECEIPT_SURFACES:
        raise ValueError("QA evidence surface is invalid")
    required_surface = gate.QA_RECEIPT_CASE_SURFACES.get(case_id)
    if required_surface is not None and surface != required_surface:
        raise ValueError("QA evidence surface does not match the required QA case")
    checked_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    run_at = _parse_timestamp(manifest.get("runAt"), now=checked_at)
    evidence = _verified_evidence(manifest, exact_root)
    required_services = SERVICE_ACK_REQUIRED_SERVICES.get(case_id)
    verified_acknowledgement: dict[str, object] | None = None
    if status == "PASS" and required_services is not None:
        if not isinstance(service_ack_status, dict):
            raise ValueError("live service restart proof is required")
        required = service_ack_status.get("requiredServices")
        acknowledged = service_ack_status.get("acknowledgedServices")
        digest = str(service_ack_status.get("serviceAckDigest") or "")
        session_ref = str(service_ack_status.get("sessionRef") or "")
        if (
            service_ack_status.get("caseId") != case_id
            or service_ack_status.get("restartState") != "ready"
            or required != list(required_services)
            or acknowledged != list(required_services)
            or service_ack_status.get("missingServices") != []
            or SHA256_REF.fullmatch(digest) is None
            or gate.QA_RECEIPT_SERVICE_SESSION.fullmatch(session_ref) is None
        ):
            raise ValueError("live service restart proof is invalid")
    verification = None
    if status == "PASS":
        verification = _derive_registered_pass(
            case_id=case_id,
            verifier_claim=manifest.get("verifier"),
            evidence_root=exact_root,
            candidate_digest=candidate_digest,
            artifact_digest=artifact_digest,
            caller_run_at=run_at,
            caller_surface=surface,
            caller_evidence=evidence,
            installed_owner_proven=installed_owner_proven,
            now=checked_at,
        )
    digest_input: dict[str, object] = {
        "caseId": case_id,
        "contractVersion": CONTRACT_VERSION,
        "evidence": evidence,
        "runAt": run_at,
        "status": status,
        "surface": surface,
    }
    if verification is not None:
        digest_input["verifier"] = verification
    receipt = {
        "artifactDigest": artifact_digest,
        "candidateDigest": candidate_digest,
        "caseId": case_id,
        "evidenceDigest": _canonical_hash(digest_input),
        "runAt": run_at,
        "status": status,
        "surface": surface,
    }
    if status == "PASS" and external_context is None:
        artifact_claims = gate._qa_receipt_artifact_claims(case_id, artifact_identity)
        if artifact_claims:
            receipt["artifactClaims"] = artifact_claims
    if status == "PASS" and required_services is not None:
        if service_ack_validator is None:
            raise ValueError("live service restart proof is not authenticated")
        checked_acknowledgement = service_ack_validator()
        if not isinstance(checked_acknowledgement, dict) or any(
            checked_acknowledgement.get(field) != service_ack_status.get(field)
            for field in (
                "caseId",
                "restartState",
                "requiredServices",
                "acknowledgedServices",
                "missingServices",
                "serviceAckDigest",
                "sessionRef",
            )
        ):
            raise ValueError("live service restart proof is not authenticated")
        verified_acknowledgement = dict(checked_acknowledgement)
        receipt["serviceAckDigest"] = digest
        receipt["serviceAckSessionRef"] = session_ref
    receipts = _validate_existing_receipts(
        existing_receipts,
        attestation_authority=attestation_authority,
        external_context=external_context,
        candidate_digest=candidate_digest,
        artifact_digest=artifact_digest,
        artifact_identity=artifact_identity,
        recovering_revoked_case_id=case_id if status != "PASS" else None,
        now=checked_at,
    )
    if status == "PASS":
        assert verification is not None
        receipt.update(
            {
                "ownerBindingSha256": (
                    external_context[4]
                    if external_context is not None
                    else (
                        attestation_authority[1]
                        if isinstance(attestation_authority, tuple)
                        and len(attestation_authority) == 2
                        else ""
                    )
                ),
                "receiptNonce": secrets.token_hex(16),
                "verifierId": verification["id"],
                "verifierManifestSha256": verification["manifestSha256"],
            }
        )
        if external_context is None:
            receipt["attestation"] = gate._sign_qa_receipt(
                receipt, attestation_authority
            )
        else:
            assert external_attestation_authority is not None
            sidecar, policy, ledger, witness, _owner_binding = external_context
            services: list[dict[str, object]] = []
            if required_services is not None:
                if (
                    verified_acknowledgement is None
                    or not callable(external_attestation_authority.service_attestor)
                ):
                    raise ValueError("external service attestation authority is unavailable")
                try:
                    services = [
                        dict(item)
                        for item in external_attestation_authority.service_attestor(
                            dict(receipt), dict(verified_acknowledgement)
                        )
                    ]
                except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
                    raise ValueError("external service attestation is invalid") from exc
                if any(
                    item.get("acknowledgementDigest")
                    != verified_acknowledgement.get("serviceAckDigest")
                    or item.get("sessionRef")
                    != verified_acknowledgement.get("sessionRef")
                    for item in services
                ):
                    raise ValueError(
                        "external service attestation does not match authenticated restart proof"
                    )
                receipt["serviceAckDigest"] = sidecar.service_acknowledgement_digest(
                    services
                )
            try:
                producers = [
                    dict(item)
                    for item in external_attestation_authority.producer_attestor(
                        dict(receipt)
                    )
                ]
                receipt = sidecar.issue_release_receipt(
                    receipt,
                    producer_attestations=producers,
                    service_acknowledgements=services,
                    policy=policy,
                    signer=external_attestation_authority.publisher_signer,
                    ledger_path=ledger,
                    ledger_witness=witness,
                    now=checked_at,
                )
            except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
                raise ValueError("external release evidence attestation is invalid") from exc
    elif external_context is not None:
        assert external_attestation_authority is not None
        sidecar, policy, ledger, witness, owner_binding = external_context
        try:
            sidecar.record_case_outcome(
                case_id=case_id,
                status=status,
                owner_binding_sha256=owner_binding,
                artifact_digest=artifact_digest,
                policy=policy,
                signer=external_attestation_authority.publisher_signer,
                ledger_path=ledger,
                ledger_witness=witness,
                now=checked_at,
            )
        except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
            raise ValueError("external release evidence revocation is invalid") from exc
    receipts = [item for item in receipts if item["caseId"] != case_id]
    receipts.append(receipt)
    receipts.sort(key=lambda item: str(item["caseId"]))
    return {"contractVersion": CONTRACT_VERSION, "receipts": receipts}


def write_receipt_set(target: Path, payload: dict[str, object]) -> None:
    target = target.expanduser().resolve(strict=False)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            os.fchmod(temporary.fileno(), 0o600)
            temporary.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, target)
        temporary_path = None
        os.chmod(target, 0o600)
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        directory_fd = os.open(target.parent, flags)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _required_case_ids(root: Path) -> set[str]:
    gate = _load_release_gate()
    return {
        row.case_id
        for row in gate.load_required_gates(root)
        if row.source.startswith("qa/") and not row.case_id.startswith("CATALOG-")
    }


def _public_receipt_summary(
    payload: dict[str, object],
    *,
    case_id: str,
) -> dict[str, object]:
    receipts = payload.get("receipts")
    if not isinstance(receipts, list):
        raise ValueError("recorded QA receipt is unavailable")
    matching = [
        receipt
        for receipt in receipts
        if isinstance(receipt, dict) and receipt.get("caseId") == case_id
    ]
    if len(matching) != 1:
        raise ValueError("recorded QA receipt is unavailable")
    receipt = matching[0]
    return {
        "contractVersion": payload.get("contractVersion"),
        "receiptCount": len(receipts),
        "recordedCase": {
            field: receipt.get(field)
            for field in (
                "caseId",
                "status",
                "surface",
                "candidateDigest",
                "artifactDigest",
                "runAt",
            )
        },
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--installed-root", type=Path, required=True)
    parser.add_argument("--runtime-owner-state", type=Path, required=True)
    parser.add_argument("--artifact-identity", type=Path, required=True)
    parser.add_argument("--receipts", type=Path, required=True)
    parser.add_argument("--local-qa-request", type=Path, required=True)
    parser.add_argument("--local-qa-state", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)
    gate = _load_release_gate()
    try:
        installed_root = args.installed_root.expanduser().resolve(strict=True)
        owner_state = args.runtime_owner_state.expanduser().resolve(strict=True)
        if not gate.validate_runtime_owner_state_file(owner_state):
            raise ValueError("active runtime owner identity is invalid")
        owner_payload = _load_json(owner_state)
        if not isinstance(owner_payload, dict) or Path(
            str(owner_payload.get("repoRoot") or "")
        ).resolve(strict=True) != installed_root:
            raise ValueError("active runtime owner does not match the installed candidate")
        manifest_preview = _load_json(args.manifest)
        service_ack_status = None
        service_ack_validator = None
        if (
            isinstance(manifest_preview, dict)
            and manifest_preview.get("status") == "PASS"
            and manifest_preview.get("caseId") in SERVICE_ACK_REQUIRED_SERVICES
        ):
            def service_ack_validator() -> object:
                return _load_local_qa_control().require_restart_ready(
                    state_path=args.local_qa_state,
                    installed_root=installed_root,
                    artifact_identity_path=args.artifact_identity,
                    local_qa_request_path=args.local_qa_request,
                )

            service_ack_status = service_ack_validator()
        attestation_authority = gate._qa_receipt_attestation_authority(
            installed_root, owner_state, create=True
        )
        if attestation_authority is None:
            raise ValueError("authenticated QA receipt authority is unavailable")
        payload = record_case_receipt(
            manifest_path=args.manifest,
            evidence_root=args.evidence_root,
            artifact_identity=_load_json(args.artifact_identity),
            existing_receipts=_load_json(
                args.receipts,
                missing={"contractVersion": CONTRACT_VERSION, "receipts": []},
            ),
            required_case_ids=_required_case_ids(args.root.resolve(strict=True)),
            local_qa_request=_load_json(args.local_qa_request),
            service_ack_status=service_ack_status,
            service_ack_validator=service_ack_validator,
            attestation_authority=attestation_authority,
            installed_owner_proven=True,
        )
        write_receipt_set(args.receipts, payload)
        public_summary = _public_receipt_summary(
            payload,
            case_id=str(manifest_preview.get("caseId") or ""),
        )
    except OSError:
        parser.error("qa_evidence_io_failed")
    except RuntimeError:
        parser.error("qa_evidence_runtime_unavailable")
    except ValueError:
        parser.error("qa_evidence_invalid")
    print(json.dumps(public_summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

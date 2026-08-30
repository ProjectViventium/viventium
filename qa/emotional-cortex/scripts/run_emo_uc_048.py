"""Derive EMO-UC-048 results from installed, candidate-bound delivery evidence."""

from __future__ import annotations

import argparse
import base64
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
import tempfile
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType
from typing import NoReturn

CASE_ID = "EMO-UC-048"
CONTRACT_VERSION = 1
VERIFIER_ID = "emo048-semantic-v1"
REQUIRED_SERVICES = ("librechat-core", "telegram-bot")
REQUIRED_SURFACES = ("web", "telegram")
REQUIRED_BOUNDARIES = (
    "cortex_ledger_first_write",
    "web_replay_persistence",
    "web_redis_publish_ack",
    "telegram_promoted_parent_presentation",
)
REQUIRED_CHECKS = (
    "active-local-qa-authority",
    "all-four-fault-boundaries",
    "exact-insight-identity",
    "restart-service-acknowledgements",
    "append-only-persistence-ledger",
    "exact-presentation-receipts",
    "exactly-once-linked-visibility",
    "typed-terminal-outcome",
)
CAPTURE_FIELDS = {"capturedAt", "caseId", "contractVersion", "evidence", "fixtureRef"}
EVIDENCE_FIELDS = {"id", "kind", "path", "sha256"}
REQUIRED_EVIDENCE = {
    "completion-record": "completion_record",
    "fault-controls": "fault_controls",
    "restart-acknowledgements": "restart_acknowledgements",
    "persistence-ledger": "persistence_ledger",
    "presentation-records": "presentation_records",
    "visibility-records": "visibility_records",
    "terminal-outcome": "terminal_outcome",
    "web-settled": "browser_screenshot",
    "web-replayed": "browser_screenshot",
    "telegram-settled": "telegram_screenshot",
    "telegram-replayed": "telegram_screenshot",
}
SESSION_FIELDS = {
    "artifactIdentityDigest",
    "caseId",
    "caseToken",
    "componentArtifactDigest",
    "contractVersion",
    "expiresAt",
    "installedRootHash",
    "mode",
    "modeVariable",
    "sessionRef",
    "startedAt",
}
ACK_FIELDS = {
    "acknowledgedAt",
    "artifactIdentityDigest",
    "caseId",
    "componentArtifactDigest",
    "contractVersion",
    "installedRootHash",
    "processIdentity",
    "proof",
    "serviceId",
    "sessionRef",
}
PROCESS_FIELDS = {
    "executablePath",
    "executableSha256",
    "pid",
    "startedAt",
    "startMarker",
}
EVENT_FIELDS = {
    "attemptNumber",
    "claimGeneration",
    "claimToken",
    "claimedAt",
    "eventAt",
    "leaseExpiresAt",
    "reason",
    "receiptHash",
    "recoveryAttemptNumber",
    "retryEligibleAt",
    "runtimeEpoch",
    "runtimeSlot",
    "surface",
    "transition",
}
SHA256 = re.compile(r"[a-f0-9]{64}\Z")
SHA256_REF = re.compile(r"sha256:[a-f0-9]{64}\Z")
OWNER_ID = re.compile(r"[a-f0-9]{24}\Z")
SAFE_REASON = re.compile(r"[a-z][a-z0-9_]{0,95}\Z")
MAX_CAPTURE_BYTES = 256 * 1024
MAX_EVIDENCE_BYTES = 100 * 1024 * 1024
MAX_FUTURE_SKEW = timedelta(minutes=5)
MAX_RESULT_AGE = timedelta(hours=24)
_DERIVED_PASS = object()
_DERIVATION_KEY = secrets.token_bytes(32)
_ISSUED_PASSES: dict[int, tuple[dict[str, object], str, str]] = {}


class _EvidenceError(ValueError):
    """Classify an evidence failure without serializing its private contents."""

    def __init__(self, code: str, *, blocked: bool = False) -> None:
        super().__init__(code)
        self.code = code
        self.blocked = blocked


class _BoundSession(dict[str, object]):
    """Retain independently measured installed candidate facts in process only."""

    candidate_digest: str
    artifact_digest: str


class _PrivateArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        raise ValueError("arguments-invalid")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _javascript_hash(value: object) -> str:
    return _sha256(json.dumps(value, separators=(",", ":"), ensure_ascii=False))


def _invalid(code: str) -> NoReturn:
    raise ValueError(code)


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate-json-key")
        result[key] = value
    return result


def _strict_json(raw: bytes) -> object:
    try:
        return json.loads(
            raw.decode("utf-8", errors="strict"), object_pairs_hook=_unique_object
        )
    except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError("invalid-json-evidence") from exc


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        _invalid("timestamp-invalid")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("timestamp-invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError("timestamp-invalid")
    parsed = parsed.astimezone(timezone.utc)
    if parsed.isoformat(timespec="milliseconds") != value:
        raise ValueError("timestamp-invalid")
    return parsed


def _inside(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def _private_directory(path: Path) -> Path:
    supplied = Path(path).expanduser()
    try:
        if supplied.is_symlink():
            raise ValueError("private-evidence-invalid")
        exact = supplied.resolve(strict=True)
        metadata = exact.stat()
    except (OSError, RuntimeError) as exc:
        raise ValueError("private-evidence-invalid") from exc
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) & 0o077
    ):
        raise ValueError("private-evidence-invalid")
    public_root = Path(__file__).resolve().parents[3]
    if _inside(exact, public_root):
        raise ValueError("private-evidence-invalid")
    return exact


def _read_private_file(path: Path, *, root: Path, max_bytes: int) -> tuple[bytes, str]:
    supplied = Path(path)
    if not supplied.is_absolute():
        supplied = root / supplied
    try:
        try:
            lexical_relative = supplied.relative_to(root)
        except ValueError as exc:
            raise ValueError("private-evidence-invalid") from exc
        if not lexical_relative.parts or any(
            part in {"", ".", ".."} for part in lexical_relative.parts
        ):
            raise ValueError("private-evidence-invalid")
        lexical_parent = root
        for part in lexical_relative.parts[:-1]:
            lexical_parent = lexical_parent / part
            parent_metadata = lexical_parent.lstat()
            if (
                stat.S_ISLNK(parent_metadata.st_mode)
                or not stat.S_ISDIR(parent_metadata.st_mode)
                or parent_metadata.st_uid != os.getuid()
                or stat.S_IMODE(parent_metadata.st_mode) & 0o077
            ):
                raise ValueError("private-evidence-invalid")
        if supplied.is_symlink():
            raise ValueError("private-evidence-invalid")
        exact = supplied.resolve(strict=True)
        if not _inside(exact, root) or exact == root or exact != supplied:
            raise ValueError("private-evidence-invalid")
        relative = exact.relative_to(root)
        current = root
        for part in relative.parts[:-1]:
            current = current / part
            metadata = current.lstat()
            if (
                stat.S_ISLNK(metadata.st_mode)
                or not stat.S_ISDIR(metadata.st_mode)
                or metadata.st_uid != os.getuid()
                or stat.S_IMODE(metadata.st_mode) & 0o077
            ):
                raise ValueError("private-evidence-invalid")
        descriptor = os.open(
            exact,
            os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
        try:
            metadata = os.fstat(descriptor)
            if (
                not stat.S_ISREG(metadata.st_mode)
                or metadata.st_uid != os.getuid()
                or stat.S_IMODE(metadata.st_mode) & 0o077
                or metadata.st_nlink != 1
                or metadata.st_size <= 0
                or metadata.st_size > max_bytes
            ):
                raise ValueError("private-evidence-invalid")
            chunks: list[bytes] = []
            remaining = max_bytes + 1
            while remaining:
                chunk = os.read(descriptor, min(1024 * 1024, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            raw = b"".join(chunks)
            if not raw or len(raw) != metadata.st_size or len(raw) > max_bytes:
                raise ValueError("private-evidence-invalid")
            current_metadata = exact.lstat()
            if (
                current_metadata.st_dev,
                current_metadata.st_ino,
                current_metadata.st_size,
                current_metadata.st_mtime_ns,
            ) != (
                metadata.st_dev,
                metadata.st_ino,
                metadata.st_size,
                metadata.st_mtime_ns,
            ):
                raise ValueError("private-evidence-invalid")
        finally:
            os.close(descriptor)
    except (OSError, RuntimeError) as exc:
        raise ValueError("private-evidence-invalid") from exc
    return raw, relative.as_posix()


def _capture_contract(payload: object, *, now: datetime) -> dict[str, object]:
    if (
        not isinstance(payload, dict)
        or set(payload) != CAPTURE_FIELDS
        or payload.get("contractVersion") != CONTRACT_VERSION
        or payload.get("caseId") != CASE_ID
        or not isinstance(payload.get("fixtureRef"), str)
        or re.fullmatch(r"emo048_fixture_[a-f0-9]{24}", payload["fixtureRef"]) is None
        or not isinstance(payload.get("evidence"), list)
        or len(payload["evidence"]) != len(REQUIRED_EVIDENCE)
    ):
        raise _EvidenceError("capture-contract-invalid", blocked=True)
    try:
        captured = _timestamp(payload.get("capturedAt"))
    except ValueError as exc:
        raise _EvidenceError("capture-contract-invalid", blocked=True) from exc
    if captured > now + MAX_FUTURE_SKEW or now - captured > MAX_RESULT_AGE:
        raise _EvidenceError("capture-contract-invalid", blocked=True)
    return payload


def _load_evidence(
    payload: dict[str, object], *, root: Path
) -> tuple[dict[str, object], list[dict[str, str]]]:
    documents: dict[str, object] = {}
    verified: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    for item in payload["evidence"]:
        if (
            not isinstance(item, dict)
            or set(item) != EVIDENCE_FIELDS
            or item.get("id") not in REQUIRED_EVIDENCE
            or item.get("kind") != REQUIRED_EVIDENCE[item["id"]]
            or not isinstance(item.get("path"), str)
            or SHA256.fullmatch(str(item.get("sha256") or "")) is None
        ):
            raise _EvidenceError("evidence-invalid", blocked=True)
        evidence_id = str(item["id"])
        relative = Path(str(item["path"]))
        if (
            evidence_id in seen_ids
            or relative.is_absolute()
            or not relative.parts
            or any(part in {"", ".", ".."} for part in relative.parts)
        ):
            raise _EvidenceError("evidence-invalid", blocked=True)
        try:
            raw, canonical_path = _read_private_file(
                relative,
                root=root,
                max_bytes=MAX_EVIDENCE_BYTES,
            )
        except ValueError as exc:
            raise _EvidenceError("evidence-invalid", blocked=True) from exc
        if (
            canonical_path in seen_paths
            or canonical_path != relative.as_posix()
            or hashlib.sha256(raw).hexdigest() != item["sha256"]
        ):
            raise _EvidenceError("evidence-invalid", blocked=True)
        if item["kind"] not in {"browser_screenshot", "telegram_screenshot"}:
            try:
                documents[evidence_id] = _strict_json(raw)
            except ValueError as exc:
                raise _EvidenceError("evidence-invalid", blocked=True) from exc
        seen_ids.add(evidence_id)
        seen_paths.add(canonical_path)
        verified.append(
            {
                "kind": str(item["kind"]),
                "path": canonical_path,
                "sha256": str(item["sha256"]),
            }
        )
    if seen_ids != set(REQUIRED_EVIDENCE):
        raise _EvidenceError("evidence-invalid", blocked=True)
    return documents, sorted(verified, key=lambda entry: (entry["kind"], entry["path"]))


def _session_authority(
    session: object,
    live_status: object,
    *,
    captured_at: datetime,
    now: datetime,
) -> dict[str, object]:
    if not isinstance(session, dict) or set(session) != SESSION_FIELDS:
        raise _EvidenceError("live-authority-mismatch", blocked=True)
    if (
        session.get("caseId") != CASE_ID
        or session.get("contractVersion") != CONTRACT_VERSION
        or session.get("mode") != "emo_uc_048"
        or session.get("modeVariable") != "VIVENTIUM_LOCAL_QA_MODE"
        or any(
            SHA256_REF.fullmatch(str(session.get(field) or "")) is None
            for field in (
                "artifactIdentityDigest",
                "componentArtifactDigest",
                "installedRootHash",
            )
        )
    ):
        raise _EvidenceError("live-authority-mismatch", blocked=True)
    token = session.get("caseToken")
    if not isinstance(token, str):
        raise _EvidenceError("live-authority-mismatch", blocked=True)
    try:
        decoded = base64.urlsafe_b64decode(token + "=")
        started = _timestamp(session.get("startedAt"))
        expires = _timestamp(session.get("expiresAt"))
    except (TypeError, ValueError) as exc:
        raise _EvidenceError("live-authority-mismatch", blocked=True) from exc
    if (
        len(decoded) != 32
        or base64.urlsafe_b64encode(decoded).decode().rstrip("=") != token
        or session.get("sessionRef") != "qa_" + _sha256(token)[:24]
        or not started <= captured_at < expires
        or not started <= now < expires
        or not isinstance(live_status, dict)
        or live_status.get("caseId") != CASE_ID
        or live_status.get("sessionRef") != session.get("sessionRef")
        or live_status.get("mode") != session.get("mode")
        or live_status.get("expiresAt") != session.get("expiresAt")
        or live_status.get("restartState") != "ready"
        or live_status.get("requiredServices") != list(REQUIRED_SERVICES)
        or live_status.get("acknowledgedServices") != list(REQUIRED_SERVICES)
        or live_status.get("missingServices") != []
        or SHA256_REF.fullmatch(str(live_status.get("serviceAckDigest") or "")) is None
    ):
        raise _EvidenceError("live-authority-mismatch", blocked=True)
    return session


def _source_identity(completion: object) -> dict[str, object]:
    if not isinstance(completion, dict):
        _invalid("insight-identity-invalid")
    owner = completion.get("ownerId")
    conversation = completion.get("conversationId")
    parent = completion.get("parentMessageId")
    cortex = completion.get("cortexId")
    insight = completion.get("insight")
    revision = completion.get("messageRevision")
    if (
        completion.get("caseId") != CASE_ID
        or completion.get("cortexName") != "Emotional Resonance"
        or cortex != "emotional-resonance-cortex"
        or not isinstance(owner, str)
        or OWNER_ID.fullmatch(owner) is None
        or not isinstance(conversation, str)
        or not isinstance(parent, str)
        or re.fullmatch(r"emo_uc_048_conversation_[a-f0-9]{32}", conversation) is None
        or re.fullmatch(r"emo_uc_048_parent_[a-f0-9]{32}", parent) is None
        or conversation.removeprefix("emo_uc_048_conversation_")
        != parent.removeprefix("emo_uc_048_parent_")
        or not isinstance(insight, str)
        or not insight.strip()
        or not isinstance(revision, int)
        or isinstance(revision, bool)
        or revision < 1
        or completion.get("surface") != "telegram"
        or not isinstance(completion.get("streamId"), str)
        or not completion["streamId"]
        or not isinstance(completion.get("completionId"), str)
        or not completion["completionId"].startswith("emo048_completion_")
    ):
        raise ValueError("insight-identity-invalid")
    try:
        _timestamp(completion.get("completedAt"))
    except ValueError as exc:
        raise ValueError("insight-identity-invalid") from exc
    insight_hash = _sha256(insight)
    persistence = completion.get("persistence")
    if (
        not isinstance(persistence, dict)
        or persistence.get("deliveryPending") is not True
        or persistence.get("durableAcceptance") != "outbox"
        or persistence.get("graphResultHashes") != [insight_hash]
        or persistence.get("outboxErrorCode")
        != "cortex_insight_delivery_ledger_write_failed"
        or persistence.get("outboxPending") is not True
    ):
        raise ValueError("insight-identity-invalid")
    identity_hash = _sha256(f"{owner}\0{parent}\0{cortex}\0{insight_hash}")
    return {
        "conversationId": conversation,
        "cortexId": cortex,
        "deliveryId": "cidl_" + identity_hash[:24],
        "deliveryKey": "cortex_insight:" + identity_hash,
        "graphResultHash": insight_hash,
        "insight": insight,
        "messageRevision": revision,
        "ownerId": owner,
        "parentMessageId": parent,
        "streamId": completion["streamId"],
        "surface": "telegram",
    }


def _row_identity(row: object, identity: dict[str, object]) -> dict[str, object]:
    if not isinstance(row, dict):
        _invalid("insight-identity-invalid")
    revision = row.get("messageRevision")
    if not isinstance(revision, int) or isinstance(revision, bool):
        _invalid("insight-identity-invalid")
    required = {
        "conversationId": identity["conversationId"],
        "cortexId": identity["cortexId"],
        "deliveryId": identity["deliveryId"],
        "deliveryKey": identity["deliveryKey"],
        "graphResultHash": identity["graphResultHash"],
        "insight": identity["insight"],
        "insightHash": identity["graphResultHash"],
        "messageRevision": identity["messageRevision"],
        "parentMessageId": identity["parentMessageId"],
        "requiredSurfaces": list(REQUIRED_SURFACES),
        "streamId": identity["streamId"],
        "surface": identity["surface"],
        "userId": identity["ownerId"],
    }
    if any(row.get(field) != value for field, value in required.items()):
        raise ValueError("insight-identity-invalid")
    return row


def _presentation_receipt(record: dict[str, object]) -> str:
    return _javascript_hash(
        {
            "messageId": record["messageId"],
            "presentationRef": record["presentationRef"],
            "revision": record["messageRevision"],
            "surface": record["surface"],
            "claimToken": record["presentationClaimToken"],
            "claimGeneration": record["claimGeneration"],
            "graphResultHash": record["graphResultHash"],
            "presentationLeaseToken": record["presentationLeaseToken"],
        }
    )


def _presentation_evidence(
    presentations: object,
    *,
    delivery: dict[str, object],
    identity: dict[str, object],
) -> dict[str, dict[str, object]]:
    if not isinstance(presentations, list) or len(presentations) != len(
        REQUIRED_SURFACES
    ):
        raise ValueError("presentation-records-invalid")
    message_id = delivery.get("persistedMessageId")
    if not isinstance(message_id, str) or not message_id.startswith("emo048_followup_"):
        raise ValueError("presentation-records-invalid")
    records: dict[str, dict[str, object]] = {}
    for item in presentations:
        if not isinstance(item, dict):
            _invalid("presentation-records-invalid")
        surface = item.get("surface")
        generation = item.get("presentationGeneration")
        expected_target = {
            "web": "durable_replay_store",
            "telegram": "promoted_parent_acknowledgement",
        }.get(str(surface))
        if (
            surface not in REQUIRED_SURFACES
            or surface in records
            or item.get("target") != expected_target
            or item.get("messageId") != message_id
            or not isinstance(item.get("messageRevision"), int)
            or isinstance(item.get("messageRevision"), bool)
            or item.get("messageRevision") != identity["messageRevision"]
            or item.get("graphResultHash") != identity["graphResultHash"]
            or not isinstance(generation, int)
            or isinstance(generation, bool)
            or generation < 1
            or item.get("claimGeneration") != generation
            or not isinstance(item.get("presentationRef"), str)
            or not item["presentationRef"]
            or not isinstance(item.get("presentationClaimToken"), str)
            or not item["presentationClaimToken"]
            or not isinstance(item.get("presentationLeaseToken"), str)
            or not item["presentationLeaseToken"]
            or SHA256.fullmatch(str(item.get("receiptHash") or "")) is None
        ):
            raise ValueError("presentation-records-invalid")
        try:
            derived_receipt = _presentation_receipt(item)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("presentation-records-invalid") from exc
        if not hmac.compare_digest(derived_receipt, str(item["receiptHash"])):
            raise ValueError("presentation-records-invalid")
        records[str(surface)] = item
    if (
        set(records) != set(REQUIRED_SURFACES)
        or records["web"]["presentationGeneration"]
        >= records["telegram"]["presentationGeneration"]
        or records["telegram"]["presentationGeneration"]
        != delivery.get("claimGeneration")
        or delivery.get("presentedSurfaces") != list(REQUIRED_SURFACES)
        or sorted(str(item["receiptHash"]) for item in records.values())
        != sorted(str(item) for item in delivery.get("presentationReceiptHashes", []))
        or delivery.get("persistenceStatus") != "persisted"
        or delivery.get("status") != "sent"
    ):
        raise ValueError("presentation-records-invalid")
    return records


def _visibility_evidence(
    observations: object,
    *,
    delivery: dict[str, object],
    identity: dict[str, object],
    presentations: dict[str, dict[str, object]],
    check_screenshots: bool = False,
) -> None:
    if not isinstance(observations, list) or len(observations) != 4:
        raise ValueError("visibility-invalid")
    expected_pairs = {
        ("settled", "web"),
        ("settled", "telegram"),
        ("replayed", "web"),
        ("replayed", "telegram"),
    }
    seen: set[tuple[str, str]] = set()
    for observation in observations:
        if not isinstance(observation, dict):
            _invalid("visibility-invalid")
        phase = observation.get("phase")
        surface = observation.get("surface")
        pair = (str(phase), str(surface))
        if (
            pair not in expected_pairs
            or pair in seen
            or observation.get("count") != 1
            or isinstance(observation.get("count"), bool)
            or observation.get("deliveryId") != identity["deliveryId"]
            or observation.get("exactInsight") != identity["insight"]
            or observation.get("graphResultHash") != identity["graphResultHash"]
            or observation.get("messageId") != delivery.get("persistedMessageId")
            or not isinstance(observation.get("messageRevision"), int)
            or isinstance(observation.get("messageRevision"), bool)
            or observation.get("messageRevision") != identity["messageRevision"]
            or not isinstance(observation.get("presentationGeneration"), int)
            or isinstance(observation.get("presentationGeneration"), bool)
            or observation.get("presentationGeneration")
            != presentations[str(surface)]["presentationGeneration"]
            or not isinstance(observation.get("screenshotEvidenceId"), str)
            or (
                check_screenshots
                and observation.get("screenshotEvidenceId") != f"{surface}-{phase}"
            )
        ):
            raise ValueError("visibility-invalid")
        seen.add(pair)
    if seen != expected_pairs:
        raise ValueError("visibility-invalid")


def verify_delivery_evidence(
    *,
    completion: object,
    delivery: object,
    presentations: object,
    observations: object,
) -> dict[str, object]:
    """Verify exact graph source, owner, insight, revisions, and linked delivery."""

    identity = _source_identity(completion)
    exact_delivery = _row_identity(delivery, identity)
    exact_presentations = _presentation_evidence(
        presentations,
        delivery=exact_delivery,
        identity=identity,
    )
    _visibility_evidence(
        observations,
        delivery=exact_delivery,
        identity=identity,
        presentations=exact_presentations,
    )
    return {
        "deliveryId": str(identity["deliveryId"]),
        "graphResultHash": str(identity["graphResultHash"]),
        "surfaces": list(REQUIRED_SURFACES),
    }


def _fault_controls(
    captured: object,
    live: object,
    *,
    identity: dict[str, object],
    fixture_ref: object,
    session: dict[str, object],
) -> dict[str, dict[str, object]]:
    if (
        not isinstance(captured, dict)
        or not isinstance(live, dict)
        or _canonical(captured) != _canonical(live)
        or captured.get("caseId") != CASE_ID
        or captured.get("fixtureRef") != fixture_ref
        or captured.get("sessionRef") != session["sessionRef"]
        or not isinstance(captured.get("controls"), list)
        or len(captured["controls"]) != len(REQUIRED_BOUNDARIES)
    ):
        raise ValueError("fault-boundaries-invalid")
    expected_scope = {
        "ownerScopeHash": "sha256:" + _sha256("owner\0" + str(identity["ownerId"])),
        "conversationScopeHash": "sha256:"
        + _sha256("conversation\0" + str(identity["conversationId"])),
        "parentScopeHash": "sha256:"
        + _sha256("parent\0" + str(identity["parentMessageId"])),
    }
    rows: dict[str, dict[str, object]] = {}
    for row in captured["controls"]:
        if not isinstance(row, dict):
            _invalid("fault-boundaries-invalid")
        boundary = row.get("boundary")
        audit = row.get("audit")
        if (
            boundary not in REQUIRED_BOUNDARIES
            or boundary in rows
            or row.get("state") != "consumed"
            or row.get("syntheticScope") is not True
            or any(row.get(field) != value for field, value in expected_scope.items())
            or not isinstance(audit, list)
            or len(audit) != 2
            or audit[0] != {"at": row.get("armedAt"), "event": "armed", "sequence": 1}
            or audit[1]
            != {"at": row.get("consumedAt"), "event": "consumed", "sequence": 2}
        ):
            raise ValueError("fault-boundaries-invalid")
        try:
            armed = _timestamp(row.get("armedAt"))
            consumed = _timestamp(row.get("consumedAt"))
            expires = _timestamp(row.get("expiresAt"))
            purge = _timestamp(row.get("purgeAt"))
            session_expires = _timestamp(session.get("expiresAt"))
        except ValueError as exc:
            raise ValueError("fault-boundaries-invalid") from exc
        if not armed < consumed < expires <= session_expires or purge <= expires:
            raise ValueError("fault-boundaries-invalid")
        rows[str(boundary)] = row
    if set(rows) != set(REQUIRED_BOUNDARIES):
        raise ValueError("fault-boundaries-invalid")
    consumed = [
        _timestamp(rows[boundary]["consumedAt"]) for boundary in REQUIRED_BOUNDARIES
    ]
    if consumed != sorted(consumed) or len(set(consumed)) != len(consumed):
        raise ValueError("fault-boundaries-invalid")
    return rows


def _restart_acknowledgements(
    document: object,
    *,
    session: dict[str, object],
    live_status: dict[str, object],
) -> tuple[dict[str, str], str]:
    expected_checkpoints = (
        "initial",
        "after-ledger-fault",
        "after-web-faults",
        "after-telegram-fault",
    )
    if (
        not isinstance(document, dict)
        or document.get("caseId") != CASE_ID
        or document.get("sessionRef") != session["sessionRef"]
        or not isinstance(document.get("checkpoints"), list)
        or len(document["checkpoints"]) != len(expected_checkpoints)
    ):
        raise ValueError("restart-acknowledgements-invalid")
    token = base64.urlsafe_b64decode(str(session["caseToken"]) + "=")
    epochs: dict[str, str] = {}
    seen_core: set[tuple[int, str, str]] = set()
    telegram_identity: dict[str, object] | None = None
    final_services: list[dict[str, object]] = []
    started = _timestamp(session["startedAt"])
    expires = _timestamp(session["expiresAt"])
    previous_observed: datetime | None = None
    for expected_id, checkpoint in zip(expected_checkpoints, document["checkpoints"]):
        if (
            not isinstance(checkpoint, dict)
            or checkpoint.get("id") != expected_id
            or not isinstance(checkpoint.get("coreRuntimeEpoch"), str)
            or not checkpoint["coreRuntimeEpoch"]
            or checkpoint["coreRuntimeEpoch"] in epochs.values()
            or not isinstance(checkpoint.get("services"), list)
            or len(checkpoint["services"]) != len(REQUIRED_SERVICES)
        ):
            raise ValueError("restart-acknowledgements-invalid")
        try:
            observed = _timestamp(checkpoint.get("observedAt"))
        except ValueError as exc:
            raise ValueError("restart-acknowledgements-invalid") from exc
        if not started <= observed < expires or (
            previous_observed is not None and observed <= previous_observed
        ):
            raise ValueError("restart-acknowledgements-invalid")
        previous_observed = observed
        for service_id, acknowledgement in zip(
            REQUIRED_SERVICES, checkpoint["services"]
        ):
            if (
                not isinstance(acknowledgement, dict)
                or set(acknowledgement) != ACK_FIELDS
                or acknowledgement.get("serviceId") != service_id
                or acknowledgement.get("caseId") != CASE_ID
                or acknowledgement.get("contractVersion") != CONTRACT_VERSION
                or acknowledgement.get("sessionRef") != session["sessionRef"]
                or any(
                    acknowledgement.get(field) != session[field]
                    for field in (
                        "artifactIdentityDigest",
                        "componentArtifactDigest",
                        "installedRootHash",
                    )
                )
                or acknowledgement.get("acknowledgedAt") != checkpoint["observedAt"]
                or not isinstance(acknowledgement.get("processIdentity"), dict)
                or set(acknowledgement["processIdentity"]) != PROCESS_FIELDS
            ):
                raise ValueError("restart-acknowledgements-invalid")
            process = acknowledgement["processIdentity"]
            if (
                not isinstance(process.get("pid"), int)
                or isinstance(process.get("pid"), bool)
                or process["pid"] < 2
                or not isinstance(process.get("executablePath"), str)
                or not Path(process["executablePath"]).is_absolute()
                or SHA256_REF.fullmatch(str(process.get("executableSha256") or ""))
                is None
                or SHA256_REF.fullmatch(str(process.get("startMarker") or "")) is None
            ):
                raise ValueError("restart-acknowledgements-invalid")
            try:
                process_started = _timestamp(process.get("startedAt"))
            except ValueError as exc:
                raise ValueError("restart-acknowledgements-invalid") from exc
            if not started <= process_started <= observed:
                raise ValueError("restart-acknowledgements-invalid")
            unsigned = {
                key: value for key, value in acknowledgement.items() if key != "proof"
            }
            derived_proof = (
                "hmac-sha256:"
                + hmac.new(
                    token,
                    _canonical(unsigned).encode("utf-8"),
                    hashlib.sha256,
                ).hexdigest()
            )
            if not hmac.compare_digest(
                str(acknowledgement.get("proof")), derived_proof
            ):
                raise ValueError("restart-acknowledgements-invalid")
            if service_id == "librechat-core":
                marker = (
                    int(process["pid"]),
                    str(process["startMarker"]),
                    str(process["startedAt"]),
                )
                if marker in seen_core:
                    raise ValueError("restart-acknowledgements-invalid")
                seen_core.add(marker)
            elif telegram_identity is None:
                telegram_identity = process
            elif process != telegram_identity:
                raise ValueError("restart-acknowledgements-invalid")
        epochs[expected_id] = str(checkpoint["coreRuntimeEpoch"])
        final_services = checkpoint["services"]
    digest = "sha256:" + _sha256(_canonical(final_services))
    if not hmac.compare_digest(digest, str(live_status["serviceAckDigest"])):
        raise _EvidenceError("live-authority-mismatch", blocked=True)
    return epochs, digest


def _event_history(
    events: object,
    *,
    identity: dict[str, object],
    message_id: str,
    presentations: dict[str, dict[str, object]],
    epochs: dict[str, str],
) -> None:
    expected = (
        "pending",
        "claimed",
        "persisted",
        "failure",
        "claimed",
        "presented",
        "failure",
        "claimed",
        "presented",
        "sent",
    )
    if not isinstance(events, list) or len(events) != len(expected):
        raise ValueError("persistence-ledger-invalid")
    generation = 0
    claim: dict[str, object] | None = None
    previous: datetime | None = None
    for transition, event in zip(expected, events):
        if (
            not isinstance(event, dict)
            or set(event) != EVENT_FIELDS
            or event.get("transition") != transition
            or event.get("recoveryAttemptNumber") != 0
            or event.get("retryEligibleAt") is not None
        ):
            raise ValueError("persistence-ledger-invalid")
        try:
            occurred = _timestamp(event.get("eventAt"))
        except ValueError as exc:
            raise ValueError("persistence-ledger-invalid") from exc
        if previous is not None and occurred <= previous:
            raise ValueError("persistence-ledger-invalid")
        previous = occurred
        if transition == "pending":
            if (
                event.get("attemptNumber") != 0
                or event.get("claimGeneration") != 0
                or event.get("claimToken") != ""
                or event.get("claimedAt") is not None
                or event.get("leaseExpiresAt") is not None
            ):
                raise ValueError("persistence-ledger-invalid")
            continue
        if transition == "claimed":
            generation += 1
            claim = event
        if (
            claim is None
            or event.get("attemptNumber") != generation
            or event.get("claimGeneration") != generation
            or event.get("claimToken") != claim.get("claimToken")
            or not isinstance(event.get("claimToken"), str)
            or not event["claimToken"]
            or event.get("claimedAt") != claim.get("claimedAt")
            or event.get("leaseExpiresAt") != claim.get("leaseExpiresAt")
            or event.get("runtimeEpoch")
            != epochs[
                ("after-ledger-fault", "after-web-faults", "after-telegram-fault")[
                    generation - 1
                ]
            ]
            or re.fullmatch(r"slot_[a-f0-9]{24}", str(event.get("runtimeSlot") or ""))
            is None
        ):
            raise ValueError("persistence-ledger-invalid")
        try:
            claimed = _timestamp(event.get("claimedAt"))
            expires = _timestamp(event.get("leaseExpiresAt"))
        except ValueError as exc:
            raise ValueError("persistence-ledger-invalid") from exc
        if not claimed <= occurred < expires or (
            transition == "claimed" and event.get("claimedAt") != event.get("eventAt")
        ):
            raise ValueError("persistence-ledger-invalid")
        if transition == "persisted":
            expected_receipt = _javascript_hash(
                {
                    "messageId": message_id,
                    "revision": identity["messageRevision"],
                    "stage": "persistence",
                }
            )
            if event.get("receiptHash") != expected_receipt:
                raise ValueError("persistence-ledger-invalid")
        elif transition == "failure":
            if event.get("reason") != "presentation_failed":
                raise ValueError("persistence-ledger-invalid")
        elif transition == "presented":
            record = presentations.get(str(event.get("surface")))
            if (
                record is None
                or event.get("receiptHash") != record.get("receiptHash")
                or event.get("claimToken") != record.get("presentationClaimToken")
                or event.get("claimGeneration") != record.get("claimGeneration")
            ):
                raise ValueError("persistence-ledger-invalid")
        elif transition == "sent":
            expected_receipt = _javascript_hash(
                {
                    "messageId": message_id,
                    "presentationReceiptHashes": sorted(
                        str(record["receiptHash"]) for record in presentations.values()
                    ),
                    "revision": identity["messageRevision"],
                }
            )
            if event.get("receiptHash") != expected_receipt:
                raise ValueError("persistence-ledger-invalid")
    if generation != 3:
        raise ValueError("persistence-ledger-invalid")


def _persistence_ledger(
    document: object,
    *,
    identity: dict[str, object],
    presentations: dict[str, dict[str, object]],
    epochs: dict[str, str],
) -> dict[str, object]:
    phases = (
        ("after-ledger-fault", "initial", 0),
        ("after-web-faults", "after-ledger-fault", 1),
        ("after-telegram-fault", "after-web-faults", 2),
        ("settled", "after-telegram-fault", 3),
        ("replayed", "after-telegram-fault", 3),
    )
    if (
        not isinstance(document, dict)
        or document.get("caseId") != CASE_ID
        or document.get("deliveryId") != identity["deliveryId"]
        or document.get("graphResultHash") != identity["graphResultHash"]
        or not isinstance(document.get("snapshots"), list)
        or len(document["snapshots"]) != len(phases)
    ):
        raise ValueError("persistence-ledger-invalid")
    snapshots = document["snapshots"]
    final = snapshots[3]
    if (
        not isinstance(final, dict)
        or not isinstance(final.get("ledger"), list)
        or len(final["ledger"]) != 1
    ):
        raise ValueError("persistence-ledger-invalid")
    try:
        settled = _row_identity(final["ledger"][0], identity)
    except ValueError as exc:
        raise ValueError("persistence-ledger-invalid") from exc
    message_id = settled.get("persistedMessageId")
    if not isinstance(message_id, str):
        _invalid("persistence-ledger-invalid")
    final_events = settled.get("events")
    _event_history(
        final_events,
        identity=identity,
        message_id=message_id,
        presentations=presentations,
        epochs=epochs,
    )
    previous: datetime | None = None
    for (phase, checkpoint, generation), snapshot in zip(phases, snapshots):
        if (
            not isinstance(snapshot, dict)
            or snapshot.get("phase") != phase
            or snapshot.get("checkpointId") != checkpoint
            or not isinstance(snapshot.get("ledger"), list)
            or not isinstance(snapshot.get("outbox"), list)
        ):
            raise ValueError("persistence-ledger-invalid")
        try:
            recorded = _timestamp(snapshot.get("recordedAt"))
        except ValueError as exc:
            raise ValueError("persistence-ledger-invalid") from exc
        if previous is not None and recorded <= previous:
            raise ValueError("persistence-ledger-invalid")
        previous = recorded
        if generation == 0:
            if snapshot["ledger"] != [] or len(snapshot["outbox"]) != 1:
                raise ValueError("persistence-ledger-invalid")
            outbox = snapshot["outbox"][0]
            expected = {
                "conversationId": identity["conversationId"],
                "cortexId": identity["cortexId"],
                "graphResultHash": identity["graphResultHash"],
                "insight": identity["insight"],
                "insightHash": identity["graphResultHash"],
                "messageRevision": identity["messageRevision"],
                "outboxKey": identity["deliveryKey"],
                "parentMessageId": identity["parentMessageId"],
                "replayAttempts": 0,
                "streamId": identity["streamId"],
                "surface": identity["surface"],
                "userId": identity["ownerId"],
            }
            if not isinstance(outbox, dict) or any(
                outbox.get(field) != value for field, value in expected.items()
            ):
                raise ValueError("persistence-ledger-invalid")
            continue
        if snapshot["outbox"] != [] or len(snapshot["ledger"]) != 1:
            raise ValueError("persistence-ledger-invalid")
        try:
            row = _row_identity(snapshot["ledger"][0], identity)
        except ValueError as exc:
            raise ValueError("persistence-ledger-invalid") from exc
        events = row.get("events")
        expected_count = {1: 4, 2: 7, 3: 10}[generation]
        if (
            not isinstance(events, list)
            or len(events) != expected_count
            or events != final_events[:expected_count]
            or row.get("attemptNumber") != generation
            or row.get("claimGeneration") != generation
            or row.get("claimToken") != ""
            or row.get("claimedAt") is not None
            or row.get("leaseExpiresAt") is not None
            or row.get("persistedMessageId") != message_id
            or row.get("persistenceStatus") != "persisted"
            or row.get("presentedSurfaces")
            != {1: [], 2: ["web"], 3: ["web", "telegram"]}[generation]
            or row.get("presentationReceiptHashes")
            != {
                1: [],
                2: [presentations["web"]["receiptHash"]],
                3: [
                    presentations["web"]["receiptHash"],
                    presentations["telegram"]["receiptHash"],
                ],
            }[generation]
            or row.get("status") != ("sent" if generation == 3 else "pending")
        ):
            raise ValueError("persistence-ledger-invalid")
    if snapshots[3]["ledger"] != snapshots[4]["ledger"]:
        raise ValueError("persistence-ledger-invalid")
    return settled


def _terminal_outcome(document: object, *, identity: dict[str, object]) -> None:
    if (
        not isinstance(document, dict)
        or document.get("caseId") != CASE_ID
        or document.get("presentationRecords") != []
        or document.get("visibleCounts") != {"telegram": 0, "web": 0}
        or not isinstance(document.get("completion"), dict)
        or not isinstance(document.get("settled"), dict)
        or document.get("settled") != document.get("replayed")
    ):
        raise ValueError("terminal-outcome-invalid")
    completion = document["completion"]
    if (
        completion.get("ownerId") != identity["ownerId"]
        or completion.get("conversationId") != identity["conversationId"]
        or completion.get("parentMessageId") != identity["parentMessageId"]
        or completion.get("messageRevision") != identity["messageRevision"]
        or completion.get("surface") != "telegram"
        or not isinstance(completion.get("cortexId"), str)
        or completion.get("cortexId") == identity["cortexId"]
        or not isinstance(completion.get("insight"), str)
        or not completion["insight"].strip()
        or document["settled"].get("outbox") != []
        or not isinstance(document["settled"].get("ledger"), list)
        or len(document["settled"]["ledger"]) != 1
    ):
        raise ValueError("terminal-outcome-invalid")
    insight_hash = _sha256(completion["insight"])
    identity_hash = _sha256(
        "\0".join(
            [
                str(identity["ownerId"]),
                str(identity["parentMessageId"]),
                completion["cortexId"],
                insight_hash,
            ]
        )
    )
    row = document["settled"]["ledger"][0]
    reason = row.get("dropReason") if isinstance(row, dict) else None
    if (
        not isinstance(row, dict)
        or row.get("deliveryId") != "cidl_" + identity_hash[:24]
        or row.get("deliveryKey") != "cortex_insight:" + identity_hash
        or row.get("userId") != identity["ownerId"]
        or row.get("conversationId") != identity["conversationId"]
        or row.get("parentMessageId") != identity["parentMessageId"]
        or row.get("cortexId") != completion["cortexId"]
        or row.get("insight") != completion["insight"]
        or row.get("insightHash") != insight_hash
        or row.get("graphResultHash") != insight_hash
        or row.get("messageRevision") != identity["messageRevision"]
        or row.get("status") != "dropped"
        or row.get("presentedSurfaces") != []
        or row.get("presentationReceiptHashes") != []
        or row.get("persistedMessageId") != ""
        or row.get("sentAt") is not None
        or not isinstance(reason, str)
        or SAFE_REASON.fullmatch(reason) is None
        or not isinstance(row.get("events"), list)
        or [item.get("transition") for item in row["events"] if isinstance(item, dict)]
        != ["pending", "claimed", "dropped"]
        or row["events"][-1].get("reason") != reason
        or row.get("droppedAt") != row["events"][-1].get("eventAt")
    ):
        raise ValueError("terminal-outcome-invalid")


def _result(
    *, status: str, checks: list[dict[str, str]], codes: list[str]
) -> dict[str, object]:
    return {
        "caseId": CASE_ID,
        "checks": checks,
        "failureCodes": list(dict.fromkeys(codes)),
        "status": status,
    }


def _evaluate_capture(
    payload: object,
    *,
    evidence_root: Path,
    session_state: object,
    live_status: object,
    live_controls: object,
    now: datetime,
) -> tuple[dict[str, object], list[dict[str, str]], str]:
    capture = _capture_contract(payload, now=now)
    try:
        root = _private_directory(evidence_root)
    except ValueError as exc:
        raise _EvidenceError("evidence-invalid", blocked=True) from exc
    documents, receipt_evidence = _load_evidence(capture, root=root)
    captured = _timestamp(capture["capturedAt"])
    session = _session_authority(
        session_state,
        live_status,
        captured_at=captured,
        now=now,
    )
    assert isinstance(live_status, dict)
    checks: list[dict[str, str]] = [
        {"id": "active-local-qa-authority", "status": "PASS"}
    ]
    failures: list[str] = []
    identity: dict[str, object] | None = None
    try:
        identity = _source_identity(documents.get("completion-record"))
    except ValueError:
        failures.append("insight-identity-invalid")

    if identity is not None:
        try:
            _fault_controls(
                documents.get("fault-controls"),
                live_controls,
                identity=identity,
                fixture_ref=capture["fixtureRef"],
                session=session,
            )
            checks.append({"id": "all-four-fault-boundaries", "status": "PASS"})
        except ValueError:
            failures.append("fault-boundaries-invalid")
            checks.append({"id": "all-four-fault-boundaries", "status": "FAIL"})
    else:
        checks.append({"id": "all-four-fault-boundaries", "status": "FAIL"})
    checks.append(
        {
            "id": "exact-insight-identity",
            "status": "PASS" if identity is not None else "FAIL",
        }
    )

    epochs: dict[str, str] = {}
    try:
        epochs, _ = _restart_acknowledgements(
            documents.get("restart-acknowledgements"),
            session=session,
            live_status=live_status,
        )
        checks.append({"id": "restart-service-acknowledgements", "status": "PASS"})
    except _EvidenceError:
        raise
    except ValueError:
        failures.append("restart-acknowledgements-invalid")
        checks.append({"id": "restart-service-acknowledgements", "status": "FAIL"})

    presentation_document = documents.get("presentation-records")
    ledger_document = documents.get("persistence-ledger")
    visibility_document = documents.get("visibility-records")
    settled: dict[str, object] | None = None
    if isinstance(ledger_document, dict) and isinstance(
        ledger_document.get("snapshots"), list
    ):
        snapshots = ledger_document["snapshots"]
        if len(snapshots) > 3 and isinstance(snapshots[3], dict):
            rows = snapshots[3].get("ledger")
            if isinstance(rows, list) and len(rows) == 1 and isinstance(rows[0], dict):
                settled = rows[0]
    presentations: dict[str, dict[str, object]] = {}
    presentation_ok = False
    if identity is not None and settled is not None:
        try:
            _row_identity(settled, identity)
            if (
                not isinstance(presentation_document, dict)
                or presentation_document.get("caseId") != CASE_ID
                or presentation_document.get("deliveryId") != identity["deliveryId"]
            ):
                raise ValueError("presentation-records-invalid")
            presentations = _presentation_evidence(
                presentation_document.get("records"),
                delivery=settled,
                identity=identity,
            )
            presentation_ok = True
        except ValueError:
            failures.append("presentation-records-invalid")
    else:
        failures.append("presentation-records-invalid")

    ledger_ok = False
    if identity is not None and presentation_ok and epochs:
        try:
            settled = _persistence_ledger(
                ledger_document,
                identity=identity,
                presentations=presentations,
                epochs=epochs,
            )
            ledger_ok = True
        except ValueError:
            failures.append("persistence-ledger-invalid")
    else:
        failures.append("persistence-ledger-invalid")
    checks.append(
        {
            "id": "append-only-persistence-ledger",
            "status": "PASS" if ledger_ok else "FAIL",
        }
    )
    checks.append(
        {
            "id": "exact-presentation-receipts",
            "status": "PASS" if presentation_ok else "FAIL",
        }
    )

    visibility_ok = False
    if identity is not None and settled is not None and presentation_ok:
        try:
            if (
                not isinstance(visibility_document, dict)
                or visibility_document.get("caseId") != CASE_ID
                or visibility_document.get("deliveryId") != identity["deliveryId"]
            ):
                raise ValueError("visibility-invalid")
            _visibility_evidence(
                visibility_document.get("observations"),
                delivery=settled,
                identity=identity,
                presentations=presentations,
                check_screenshots=True,
            )
            visibility_ok = True
        except ValueError:
            failures.append("visibility-invalid")
    else:
        failures.append("visibility-invalid")
    checks.append(
        {
            "id": "exactly-once-linked-visibility",
            "status": "PASS" if visibility_ok else "FAIL",
        }
    )

    terminal_ok = False
    if identity is not None:
        try:
            _terminal_outcome(documents.get("terminal-outcome"), identity=identity)
            terminal_ok = True
        except ValueError:
            failures.append("terminal-outcome-invalid")
    else:
        failures.append("terminal-outcome-invalid")
    checks.append(
        {
            "id": "typed-terminal-outcome",
            "status": "PASS" if terminal_ok else "FAIL",
        }
    )
    return (
        _result(status="FAIL" if failures else "PASS", checks=checks, codes=failures),
        receipt_evidence,
        captured.isoformat(),
    )


def _write_private_receipt(
    target: Path, *, root: Path, payload: dict[str, object]
) -> None:
    supplied = Path(target).expanduser()
    if not supplied.is_absolute():
        supplied = root / supplied
    try:
        exact = supplied.resolve(strict=False)
        if exact == root or not _inside(exact, root):
            raise ValueError("receipt-path-invalid")
        parent = exact.parent
        if parent.exists():
            _private_directory(parent)
        else:
            parent.mkdir(mode=0o700, parents=True, exist_ok=False)
            _private_directory(parent)
        if exact.exists() or exact.is_symlink():
            _read_private_file(exact, root=root, max_bytes=MAX_CAPTURE_BYTES)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=parent,
                prefix=f".{exact.name}.",
                suffix=".tmp",
                delete=False,
            ) as stream:
                temporary = Path(stream.name)
                os.fchmod(stream.fileno(), 0o600)
                stream.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, exact)
            temporary = None
            descriptor = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    except (OSError, RuntimeError) as exc:
        raise ValueError("receipt-path-invalid") from exc


def verify_capture(
    *,
    capture_path: Path,
    evidence_root: Path,
    session_state: object,
    live_status: object,
    live_controls: object,
    receipt_path: Path,
    now: datetime | None = None,
) -> dict[str, object]:
    """Write one private PASS manifest only when every semantic check derives PASS."""

    checked = (now or _utc_now()).astimezone(timezone.utc)
    try:
        root = _private_directory(evidence_root)
        raw, capture_relative = _read_private_file(
            Path(capture_path),
            root=root,
            max_bytes=MAX_CAPTURE_BYTES,
        )
        capture = _strict_json(raw)
    except ValueError:
        return _result(status="BLOCKED", checks=[], codes=["capture-contract-invalid"])
    try:
        outcome, evidence, run_at = _evaluate_capture(
            capture,
            evidence_root=root,
            session_state=session_state,
            live_status=live_status,
            live_controls=live_controls,
            now=checked,
        )
    except _EvidenceError as exc:
        return _result(
            status="BLOCKED" if exc.blocked else "FAIL",
            checks=[],
            codes=[exc.code],
        )
    if outcome["status"] != "PASS":
        return outcome
    manifest = {
        "caseId": CASE_ID,
        "contractVersion": CONTRACT_VERSION,
        "evidence": evidence,
        "runAt": run_at,
        "status": "PASS",
        "surface": "telegram",
        "verifier": {"id": VERIFIER_ID, "manifest": capture_relative},
    }
    try:
        _write_private_receipt(Path(receipt_path), root=root, payload=manifest)
    except ValueError:
        return _result(status="BLOCKED", checks=[], codes=["receipt-path-invalid"])
    return outcome


def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError("live-authority-unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def probe_live_authority() -> tuple[
    dict[str, object], dict[str, object], dict[str, object]
]:
    """Resolve trusted owner, session, service acknowledgements, and live controls."""

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
        raise ValueError("live-authority-unavailable")
    try:
        user_home = Path(pwd.getpwuid(os.getuid()).pw_dir).resolve(strict=True)
        support = user_home / "Library" / "Application Support" / "Viventium"
        runtime = support / "runtime"
        owner_path = support / "state" / "runtime" / "isolated" / "stack-owner.json"
        source_root = Path(__file__).resolve().parents[3]
        gate = _load_module(
            source_root / "scripts" / "viventium" / "parallel_work_release_gate.py",
            "emo048_parallel_work_release_gate",
        )
        if not gate.validate_runtime_owner_state_file(owner_path):
            raise ValueError("live-authority-unavailable")
        control = _load_module(
            source_root / "scripts" / "viventium" / "local_qa_runtime_control.py",
            "emo048_local_qa_runtime_control",
        )
        _owner_raw, owner = control._read_private_json(
            owner_path,
            label="runtime owner",
            max_bytes=64 * 1024,
        )
        if not isinstance(owner, dict):
            _invalid("live-authority-unavailable")
        installed_root = Path(str(owner.get("repoRoot") or "")).resolve(strict=True)
        owner_support = Path(str(owner.get("appSupportDir") or "")).resolve(strict=True)
        if (
            installed_root != source_root
            or owner_support != support.resolve(strict=True)
            or owner.get("command") not in {"start", "launch"}
        ):
            raise ValueError("live-authority-unavailable")
        state_path = runtime / "local-qa" / "active.json"
        artifact_identity_path = runtime / "parallel-work-artifact-identity.json"
        request_path = runtime / "parallel-work-local-qa-request.json"
        parameters = {
            "state_path": state_path,
            "installed_root": installed_root,
            "artifact_identity_path": artifact_identity_path,
            "local_qa_request_path": request_path,
        }
        session = _BoundSession(control.active_session(**parameters))
        if session.get("caseId") != CASE_ID:
            raise ValueError("live-authority-unavailable")
        status = control.require_restart_ready(**parameters)
        _identity_raw, identity = control._read_private_json(
            artifact_identity_path,
            label="installed artifact identity",
            max_bytes=64 * 1024,
        )
        candidate, artifact = gate._qa_candidate_digests(identity)
        if (
            SHA256.fullmatch(str(candidate or "")) is None
            or SHA256.fullmatch(str(artifact or "")) is None
        ):
            raise ValueError("live-authority-unavailable")
        session.candidate_digest = str(candidate)
        session.artifact_digest = str(artifact)
        parent = _load_module(
            installed_root
            / "scripts"
            / "viventium"
            / "librechat_emo_qa_parent_control.py",
            "emo048_librechat_qa_parent_control",
        )
        controls = parent.query_faults(
            parent_state_path=runtime / "local-qa" / "emo-uc-048.json",
            session_state_path=state_path,
            installed_root=installed_root,
            artifact_identity_path=artifact_identity_path,
            local_qa_request_path=request_path,
            runtime_env_path=runtime / "service-env" / "librechat.env",
            boundary=None,
        )
        if not isinstance(status, dict) or not isinstance(controls, dict):
            _invalid("live-authority-unavailable")
        return session, status, controls
    except (ImportError, KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
        raise ValueError("live-authority-unavailable") from exc


def _derived_result_digest(result: dict[str, object]) -> str:
    return _sha256(
        _canonical(
            {
                "artifactDigest": result.get("artifactDigest"),
                "candidateDigest": result.get("candidateDigest"),
                "caseId": result.get("caseId"),
                "checks": result.get("checks"),
                "contractVersion": result.get("contractVersion"),
                "failureCodes": result.get("failureCodes"),
                "receiptEvidence": result.get("_receiptEvidence"),
                "runAt": result.get("runAt"),
                "status": result.get("status"),
                "surface": result.get("surface"),
            }
        )
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
    """Provide the shared receipt writer with an independently derived result."""

    if (
        installed_owner_proven is not True
        or SHA256.fullmatch(str(expected_candidate_digest or "")) is None
        or SHA256.fullmatch(str(expected_artifact_digest or "")) is None
    ):
        raise ValueError("installed candidate binding is invalid")
    session, status, controls = probe_live_authority()
    if isinstance(session, _BoundSession) and (
        session.candidate_digest != expected_candidate_digest
        or session.artifact_digest != expected_artifact_digest
    ):
        raise ValueError("installed candidate binding is invalid")
    checked = (now or _utc_now()).astimezone(timezone.utc)
    try:
        outcome, evidence, run_at = _evaluate_capture(
            manifest,
            evidence_root=evidence_root,
            session_state=session,
            live_status=status,
            live_controls=controls,
            now=checked,
        )
    except _EvidenceError as exc:
        raise ValueError("semantic evidence is invalid") from exc
    result: dict[str, object] = {
        **outcome,
        "_receiptEvidence": evidence,
        "artifactDigest": expected_artifact_digest,
        "candidateDigest": expected_candidate_digest,
        "contractVersion": CONTRACT_VERSION,
        "runAt": run_at,
        "surface": "telegram",
    }
    result["_derivedPass"] = _DERIVED_PASS if outcome["status"] == "PASS" else None
    result["_derivationDigest"] = _derived_result_digest(result)
    if outcome["status"] == "PASS":
        seal = hmac.new(
            _DERIVATION_KEY,
            str(result["_derivationDigest"]).encode("ascii"),
            hashlib.sha256,
        ).hexdigest()
        result["_derivationSeal"] = seal
        if len(_ISSUED_PASSES) >= 128:
            _ISSUED_PASSES.pop(next(iter(_ISSUED_PASSES)))
        _ISSUED_PASSES[id(result)] = (
            result,
            str(result["_derivationDigest"]),
            seal,
        )
    return result


def receipt_manifest(*, result: dict[str, object]) -> dict[str, object]:
    """Reject caller-declared or modified PASS results before receipt creation."""

    if not isinstance(result, dict):
        _invalid("derived PASS is invalid")
    issued = _ISSUED_PASSES.get(id(result))
    checks = result.get("checks")
    evidence = result.get("_receiptEvidence")
    try:
        digest = _derived_result_digest(result)
    except (TypeError, ValueError):
        raise ValueError("derived PASS is invalid") from None
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
        or result.get("failureCodes") != []
        or not isinstance(checks, list)
        or len(checks) != len(REQUIRED_CHECKS)
        or {item.get("id") for item in checks if isinstance(item, dict)}
        != set(REQUIRED_CHECKS)
        or any(
            not isinstance(item, dict) or item.get("status") != "PASS"
            for item in checks
        )
        or not isinstance(evidence, list)
        or len(evidence) != len(REQUIRED_EVIDENCE)
    ):
        raise ValueError("derived PASS is invalid")
    for item in evidence:
        if (
            not isinstance(item, dict)
            or set(item) != {"kind", "path", "sha256"}
            or SHA256.fullmatch(str(item.get("sha256") or "")) is None
        ):
            raise ValueError("derived PASS is invalid")
    return {
        "caseId": CASE_ID,
        "contractVersion": CONTRACT_VERSION,
        "evidence": evidence,
        "runAt": str(result["runAt"]),
        "status": "PASS",
        "surface": "telegram",
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = _PrivateArgumentParser(
        description=__doc__, allow_abbrev=False, add_help=True
    )
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    arguments = list(argv) if argv is not None else sys.argv[1:]
    try:
        supplied_options = [
            item.split("=", 1)[0] for item in arguments if item.startswith("--")
        ]
        if len(supplied_options) != len(set(supplied_options)):
            raise ValueError("arguments-invalid")
        parsed = parser.parse_args(arguments)
    except (TypeError, ValueError):
        print("EMO-UC-048 arguments are invalid.", file=sys.stderr)
        return 2
    try:
        session, status, controls = probe_live_authority()
    except (OSError, RuntimeError, ValueError):
        print(
            json.dumps(
                _result(
                    status="BLOCKED", checks=[], codes=["live-authority-unavailable"]
                ),
                sort_keys=True,
            )
        )
        return 2
    result = verify_capture(
        capture_path=parsed.capture,
        evidence_root=parsed.evidence_root,
        session_state=session,
        live_status=status,
        live_controls=controls,
        receipt_path=parsed.receipt,
        now=_utc_now(),
    )
    print(json.dumps(result, sort_keys=True))
    return {"PASS": 0, "FAIL": 1, "BLOCKED": 2}.get(str(result.get("status")), 2)


if __name__ == "__main__":
    raise SystemExit(main())

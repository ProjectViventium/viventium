#!/usr/bin/env python3
"""Fail-closed verifier for installed Parallel Work user journeys PWK-UC-014–019."""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import importlib.util
import io
import json
import os
import re
import stat
import struct
import subprocess
import sys
import wave
import zlib
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import NoReturn

CONTRACT_VERSION = 1
MAX_MANIFEST_BYTES = 256 * 1024
MAX_IDENTITY_BYTES = 128 * 1024
MAX_EVIDENCE_FILES = 64
MAX_EVIDENCE_BYTES = 100 * 1024 * 1024
MAX_CAPTURE_PIXELS = 25_000_000
MAX_AGE = timedelta(hours=24)
MAX_FUTURE_SKEW = timedelta(minutes=5)
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}$")
SAFE_KIND = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
SHA256 = re.compile(r"^[a-f0-9]{64}$")
CALLBACK_REF = re.compile(r"^callback_sha256:[a-f0-9]{64}$")
SEMANTIC_SCHEMA = "pwk.installed-journey-evidence.v1"
VERIFIER_ID = "pwk-installed-journey-v1"
NATIVE_ATTESTATION_FIELDS = {
    "actor",
    "capsuleOccurrenceCount",
    "contractVersion",
    "expiresAtMs",
    "issuedAtMs",
    "keyId",
    "modelRefHash",
    "nativeRequestSha256",
    "ownerRefHash",
    "producer",
    "proof",
    "providerAttemptRefHash",
    "providerRefHash",
    "runRefHash",
    "snapshotHash",
    "surface",
    "workRefHash",
}

MANIFEST_FIELDS = {
    "artifactDigest",
    "candidateDigest",
    "caseId",
    "checks",
    "contractVersion",
    "correlation",
    "evidence",
    "runAt",
}
CORRELATION_FIELDS = {"logicalTurnRefHash", "ownerRefHash", "surface", "turnRevision"}
CHECK_FIELDS = {"evidence", "id"}
EVIDENCE_BINDING_FIELDS = {
    "artifactDigest",
    "candidateDigest",
    "logicalTurnRefHash",
    "observedAt",
    "originSurface",
    "ownerRefHash",
    "runRefHash",
    "surface",
    "turnRevision",
    "workRefHash",
}
EVIDENCE_FIELDS = {"id", "kind", "path", "sha256"} | EVIDENCE_BINDING_FIELDS
SEMANTIC_FIELDS = {
    "contractVersion",
    "kind",
    "payload",
    "producer",
    "schema",
} | EVIDENCE_BINDING_FIELDS

CASE_CHECKS: dict[str, frozenset[str]] = {
    "PWK-UC-014": frozenset(
        {
            "installed-identity",
            "telegram-ui",
            "main-feelings-receipt",
            "route-facts",
            "source-revision-single-reply",
            "main-responsive-quick-turn",
            "two-distinct-missions",
            "overlapping-runtime-windows",
            "steer-a-only",
            "terminal-callbacks-once",
            "two-distinct-html-artifacts",
            "two-headed-browser-windows",
            "redacted-end-to-end-trace",
        }
    ),
    "PWK-UC-015": frozenset(
        {
            "installed-identity",
            "pre-restart-state",
            "restart-acknowledgements",
            "post-restart-state",
            "mission-identity-continuity",
            "steer-a-continuity",
            "callback-delivery-once",
            "artifact-hash-continuity",
            "telegram-recovery-ui",
            "active-work-recovery-ui",
        }
    ),
    "PWK-UC-016": frozenset(
        {
            "installed-identity",
            "provider-auth-missing",
            "quota-cooldown-skip",
            "fallback-recovery",
            "provider-unavailable",
            "capacity-measurement",
            "atomic-reservation-race",
            "overflow-rejection-no-work",
            "disk-pressure",
            "same-work-recovery",
            "telegram-degraded-ui",
            "active-work-degraded-ui",
            "redacted-end-to-end-trace",
        }
    ),
    "PWK-UC-017": frozenset(
        {
            "installed-identity",
            "callback-transport-outage",
            "claimed-timeout-once",
            "admitted-timeout-once",
            "status-timeout-race",
            "delivery-lease-race",
            "duplicate-callback-suppression",
            "artifact-expired-copy",
            "artifact-unavailable-copy",
            "restart-acknowledgements",
            "artifact-recovery",
            "telegram-terminal-ui",
            "active-work-terminal-ui",
            "redacted-end-to-end-trace",
        }
    ),
    "PWK-UC-018": frozenset(
        {
            "installed-identity",
            "two-owner-auth-matrix",
            "forged-callback-rejection",
            "cross-owner-callback-rejection",
            "altered-trace-rejection",
            "hostile-html-browser-isolation",
            "worker-peer-isolation",
            "public-safety-scan",
            "telegram-safe-ui",
            "web-safe-ui",
            "redacted-end-to-end-trace",
        }
    ),
    "PWK-UC-019": frozenset(
        {
            "installed-identity",
            "audible-call",
            "linked-chat",
            "active-work-ui",
            "telegram-attachment-ingress",
            "exact-input-hashes-and-order",
            "memory-and-recall",
            "connected-or-broker-tool",
            "two-distinct-missions",
            "main-responsive-quick-turn",
            "spoken-steer-a-only",
            "hangup-and-reconnect",
            "callback-delivery-once",
            "two-distinct-artifacts",
            "two-headed-browser-windows",
            "passive-wing-denial",
            "listen-only-denial",
            "redacted-end-to-end-trace",
            "request-pinned-feelings-parity",
            "native-provider-receipts",
            "configured-provider-fallback-truth",
            "authorized-browser-computer-parity",
            "owner-scoped-connected-account-permissions",
            "queue-message-worker-reuse",
            "synthetic-owner-zero-residue",
        }
    ),
}

CASE_EVIDENCE_MINIMUMS: dict[str, dict[str, int]] = {
    "PWK-UC-014": {
        "installed_identity": 1,
        "telegram_screenshot": 1,
        "telegram_observation": 1,
        "telegram_turn": 1,
        "native_receipt": 1,
        "glasshive_rows": 1,
        "delivery_ledger": 1,
        "artifact_hash": 2,
        "artifact_bytes": 2,
        "browser_screenshot": 2,
        "browser_observation": 2,
        "isolation_probe": 1,
        "trace_export": 1,
    },
    "PWK-UC-015": {
        "installed_identity": 1,
        "restart_receipt": 3,
        "database_export": 2,
        "telegram_screenshot": 1,
        "telegram_observation": 1,
        "browser_screenshot": 2,
        "browser_observation": 2,
        "artifact_hash": 2,
        "artifact_bytes": 2,
        "native_receipt": 1,
        "glasshive_rows": 1,
        "delivery_ledger": 1,
        "isolation_probe": 1,
        "trace_export": 1,
    },
    "PWK-UC-016": {
        "installed_identity": 1,
        "fault_receipt": 7,
        "capacity_ledger": 1,
        "provider_health_ledger": 1,
        "telegram_screenshot": 1,
        "telegram_observation": 1,
        "browser_screenshot": 1,
        "browser_observation": 1,
        "glasshive_rows": 1,
        "delivery_ledger": 1,
        "isolation_probe": 1,
        "trace_export": 1,
    },
    "PWK-UC-017": {
        "installed_identity": 1,
        "fault_receipt": 8,
        "restart_receipt": 3,
        "delivery_ledger": 1,
        "artifact_hash": 1,
        "artifact_bytes": 1,
        "telegram_screenshot": 1,
        "telegram_observation": 1,
        "browser_screenshot": 1,
        "browser_observation": 1,
        "glasshive_rows": 1,
        "isolation_probe": 1,
        "trace_export": 1,
    },
    "PWK-UC-018": {
        "installed_identity": 1,
        "auth_matrix": 1,
        "rejection_ledger": 3,
        "telegram_screenshot": 1,
        "telegram_observation": 1,
        "browser_screenshot": 1,
        "browser_observation": 1,
        "artifact_hash": 1,
        "artifact_bytes": 1,
        "glasshive_rows": 1,
        "delivery_ledger": 1,
        "isolation_probe": 1,
        "safety_scan": 1,
        "trace_export": 1,
    },
    "PWK-UC-019": {
        "installed_identity": 1,
        "voice_recording": 1,
        "voice_transcript": 1,
        "telegram_screenshot": 1,
        "telegram_observation": 1,
        "browser_screenshot": 3,
        "browser_observation": 3,
        "attachment_hash": 1,
        "attachment_bytes": 2,
        "capability_ledger": 6,
        "native_receipt": 1,
        "glasshive_rows": 1,
        "delivery_ledger": 1,
        "artifact_hash": 2,
        "artifact_bytes": 2,
        "isolation_probe": 1,
        "denial_receipt": 2,
        "trace_export": 1,
        "cleanup_receipt": 1,
    },
}

CASE_SURFACES = {
    "PWK-UC-014": "telegram",
    "PWK-UC-015": "telegram",
    "PWK-UC-016": "telegram",
    "PWK-UC-017": "telegram",
    "PWK-UC-018": "web",
    "PWK-UC-019": "voice",
}

EVIDENCE_SURFACES = {
    "installed_identity": "runtime",
    "restart_receipt": "runtime",
    "safety_scan": "runtime",
    "telegram_screenshot": "telegram",
    "telegram_observation": "telegram",
    "telegram_turn": "telegram",
    "attachment_hash": "telegram",
    "attachment_bytes": "telegram",
    "browser_screenshot": "web",
    "browser_observation": "web",
    "voice_recording": "voice",
    "voice_transcript": "voice",
    "denial_receipt": "voice",
    "native_receipt": "core",
    "delivery_ledger": "core",
    "trace_export": "core",
    "auth_matrix": "core",
    "rejection_ledger": "core",
    "glasshive_rows": "glasshive",
    "fault_receipt": "glasshive",
    "capacity_ledger": "glasshive",
    "provider_health_ledger": "glasshive",
    "isolation_probe": "glasshive",
    "artifact_hash": "glasshive",
    "artifact_bytes": "glasshive",
    "database_export": "glasshive",
    "capability_ledger": "glasshive",
    "cleanup_receipt": "runtime",
}

EVIDENCE_PRODUCERS = {
    "installed_identity": "runtime.installed_identity",
    "restart_receipt": "runtime.service_acknowledgement",
    "safety_scan": "runtime.public_safety_scan",
    "telegram_observation": "telegram.desktop_capture",
    "telegram_turn": "telegram.source_ledger",
    "attachment_hash": "telegram.upload_ledger",
    "browser_observation": "browser.headed_capture",
    "voice_transcript": "voice.call_transcript",
    "denial_receipt": "voice.surface_authority",
    "native_receipt": "core.native_receipt",
    "delivery_ledger": "core.delivery_ledger",
    "trace_export": "core.origin_trace",
    "auth_matrix": "core.owner_authority",
    "rejection_ledger": "core.security_audit",
    "glasshive_rows": "glasshive.lifecycle_rows",
    "fault_receipt": "glasshive.installed_qa_control",
    "capacity_ledger": "glasshive.capacity_ledger",
    "provider_health_ledger": "glasshive.provider_health",
    "isolation_probe": "glasshive.worker_isolation",
    "artifact_hash": "glasshive.artifact_ledger",
    "database_export": "glasshive.database_snapshot",
    "capability_ledger": "glasshive.capability_audit",
    "cleanup_receipt": "runner.synthetic_cleanup",
}

PNG_EVIDENCE_KINDS = {"telegram_screenshot", "browser_screenshot"}
BINARY_EVIDENCE_KINDS = PNG_EVIDENCE_KINDS | {
    "voice_recording",
    "artifact_bytes",
    "attachment_bytes",
}

FAULT_BOUNDARIES = {
    "PWK-UC-016": {
        "provider_auth_missing",
        "provider_quota_cooldown",
        "provider_fallback_recovery",
        "provider_unavailable",
        "capacity_measurement",
        "atomic_reservation_race",
        "disk_pressure",
    },
    "PWK-UC-017": {
        "callback_transport_outage",
        "claimed_timeout",
        "admitted_timeout",
        "status_timeout_race",
        "delivery_lease_race",
        "duplicate_callback",
        "artifact_expired",
        "artifact_unavailable",
    },
}

CHECK_EVIDENCE_KINDS: dict[str, frozenset[str]] = {
    "installed-identity": frozenset({"installed_identity"}),
    "telegram-ui": frozenset({"telegram_screenshot", "telegram_observation"}),
    "main-feelings-receipt": frozenset({"native_receipt"}),
    "route-facts": frozenset({"native_receipt"}),
    "source-revision-single-reply": frozenset(
        {"telegram_turn", "telegram_observation"}
    ),
    "main-responsive-quick-turn": frozenset({"glasshive_rows"}),
    "two-distinct-missions": frozenset({"glasshive_rows"}),
    "overlapping-runtime-windows": frozenset({"glasshive_rows", "isolation_probe"}),
    "steer-a-only": frozenset({"native_receipt", "glasshive_rows"}),
    "terminal-callbacks-once": frozenset({"delivery_ledger"}),
    "two-distinct-html-artifacts": frozenset({"artifact_hash", "artifact_bytes"}),
    "two-headed-browser-windows": frozenset(
        {"browser_observation", "browser_screenshot"}
    ),
    "redacted-end-to-end-trace": frozenset({"trace_export"}),
    "pre-restart-state": frozenset({"database_export"}),
    "restart-acknowledgements": frozenset({"restart_receipt"}),
    "post-restart-state": frozenset({"database_export"}),
    "mission-identity-continuity": frozenset({"database_export", "glasshive_rows"}),
    "steer-a-continuity": frozenset({"database_export", "native_receipt"}),
    "callback-delivery-once": frozenset({"delivery_ledger"}),
    "artifact-hash-continuity": frozenset({"artifact_hash", "artifact_bytes"}),
    "telegram-recovery-ui": frozenset({"telegram_screenshot", "telegram_observation"}),
    "active-work-recovery-ui": frozenset({"browser_screenshot", "browser_observation"}),
    "provider-auth-missing": frozenset({"fault_receipt", "provider_health_ledger"}),
    "quota-cooldown-skip": frozenset({"fault_receipt", "provider_health_ledger"}),
    "fallback-recovery": frozenset({"fault_receipt", "provider_health_ledger"}),
    "provider-unavailable": frozenset({"fault_receipt", "provider_health_ledger"}),
    "capacity-measurement": frozenset({"fault_receipt", "capacity_ledger"}),
    "atomic-reservation-race": frozenset({"fault_receipt", "capacity_ledger"}),
    "overflow-rejection-no-work": frozenset({"capacity_ledger"}),
    "disk-pressure": frozenset({"fault_receipt", "capacity_ledger"}),
    "same-work-recovery": frozenset({"glasshive_rows", "delivery_ledger"}),
    "telegram-degraded-ui": frozenset({"telegram_screenshot", "telegram_observation"}),
    "active-work-degraded-ui": frozenset({"browser_screenshot", "browser_observation"}),
    "callback-transport-outage": frozenset({"fault_receipt", "delivery_ledger"}),
    "claimed-timeout-once": frozenset({"fault_receipt", "delivery_ledger"}),
    "admitted-timeout-once": frozenset({"fault_receipt", "delivery_ledger"}),
    "status-timeout-race": frozenset({"fault_receipt", "delivery_ledger"}),
    "delivery-lease-race": frozenset({"fault_receipt", "delivery_ledger"}),
    "duplicate-callback-suppression": frozenset({"fault_receipt", "delivery_ledger"}),
    "artifact-expired-copy": frozenset({"fault_receipt", "artifact_hash"}),
    "artifact-unavailable-copy": frozenset({"fault_receipt", "artifact_hash"}),
    "artifact-recovery": frozenset(
        {"artifact_hash", "artifact_bytes", "browser_observation"}
    ),
    "telegram-terminal-ui": frozenset({"telegram_screenshot", "telegram_observation"}),
    "active-work-terminal-ui": frozenset({"browser_screenshot", "browser_observation"}),
    "two-owner-auth-matrix": frozenset({"auth_matrix"}),
    "forged-callback-rejection": frozenset({"rejection_ledger"}),
    "cross-owner-callback-rejection": frozenset({"rejection_ledger", "auth_matrix"}),
    "altered-trace-rejection": frozenset({"rejection_ledger", "trace_export"}),
    "hostile-html-browser-isolation": frozenset(
        {"artifact_bytes", "artifact_hash", "browser_screenshot", "browser_observation"}
    ),
    "worker-peer-isolation": frozenset({"isolation_probe", "glasshive_rows"}),
    "public-safety-scan": frozenset({"safety_scan", "artifact_bytes"}),
    "telegram-safe-ui": frozenset({"telegram_screenshot", "telegram_observation"}),
    "web-safe-ui": frozenset({"browser_screenshot", "browser_observation"}),
    "audible-call": frozenset({"voice_recording", "voice_transcript"}),
    "linked-chat": frozenset({"telegram_observation", "browser_observation"}),
    "active-work-ui": frozenset({"browser_screenshot", "browser_observation"}),
    "telegram-attachment-ingress": frozenset(
        {"attachment_hash", "telegram_observation"}
    ),
    "exact-input-hashes-and-order": frozenset({"attachment_hash", "attachment_bytes"}),
    "memory-and-recall": frozenset({"capability_ledger"}),
    "connected-or-broker-tool": frozenset({"capability_ledger"}),
    "spoken-steer-a-only": frozenset(
        {"voice_transcript", "native_receipt", "glasshive_rows"}
    ),
    "hangup-and-reconnect": frozenset({"voice_transcript", "delivery_ledger"}),
    "two-distinct-artifacts": frozenset({"artifact_hash", "artifact_bytes"}),
    "passive-wing-denial": frozenset({"denial_receipt"}),
    "listen-only-denial": frozenset({"denial_receipt"}),
    "request-pinned-feelings-parity": frozenset({"native_receipt"}),
    "native-provider-receipts": frozenset({"native_receipt"}),
    "configured-provider-fallback-truth": frozenset({"native_receipt"}),
    "authorized-browser-computer-parity": frozenset(
        {"capability_ledger", "browser_observation", "telegram_observation"}
    ),
    "owner-scoped-connected-account-permissions": frozenset(
        {"capability_ledger"}
    ),
    "queue-message-worker-reuse": frozenset(
        {"native_receipt", "glasshive_rows"}
    ),
    "synthetic-owner-zero-residue": frozenset({"cleanup_receipt"}),
}


class DuplicateJsonKeyError(ValueError):
    pass


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJsonKeyError("duplicate JSON key")
        result[key] = value
    return result


def _json_bytes(raw: bytes, *, label: str) -> object:
    def reject_constant(_value: str) -> None:
        raise ValueError("non-finite JSON value")

    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=reject_constant,
        )
    except (
        UnicodeError,
        json.JSONDecodeError,
        DuplicateJsonKeyError,
        ValueError,
    ) as exc:
        raise ValueError(f"{label} is invalid") from exc


def _read_file(
    path: Path, *, max_bytes: int, label: str, private: bool = False
) -> bytes:
    descriptor = -1
    try:
        metadata = path.lstat()
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
            or metadata.st_size < 2
            or metadata.st_size > max_bytes
            or (
                private and (metadata.st_uid != os.getuid() or metadata.st_mode & 0o077)
            )
        ):
            raise ValueError(f"{label} is invalid")
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        opened = os.fstat(descriptor)
        if (
            (opened.st_dev, opened.st_ino) != (metadata.st_dev, metadata.st_ino)
            or not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or (private and (opened.st_uid != os.getuid() or opened.st_mode & 0o077))
        ):
            raise ValueError(f"{label} is invalid")
        chunks = bytearray()
        while len(chunks) <= max_bytes:
            chunk = os.read(descriptor, min(1024 * 1024, max_bytes + 1 - len(chunks)))
            if not chunk:
                break
            chunks.extend(chunk)
        final = os.fstat(descriptor)
        if (
            len(chunks) < 2
            or len(chunks) > max_bytes
            or final.st_size != len(chunks)
            or (final.st_dev, final.st_ino, final.st_mtime_ns)
            != (opened.st_dev, opened.st_ino, opened.st_mtime_ns)
        ):
            raise ValueError(f"{label} is invalid")
        return bytes(chunks)
    except (OSError, OverflowError) as exc:
        raise ValueError(f"{label} is invalid") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _strict_json(
    path: Path, *, max_bytes: int, label: str, private: bool = False
) -> object:
    return _json_bytes(
        _read_file(path, max_bytes=max_bytes, label=label, private=private),
        label=label,
    )


def _invalid(message: str) -> NoReturn:
    raise ValueError(message)


def _hash(value: object, *, message: str) -> str:
    if not isinstance(value, str) or SHA256.fullmatch(value) is None:
        raise ValueError(message)
    return value


def _object(value: object, fields: set[str], *, message: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(message)
    return value


def _list(value: object, *, message: str, minimum: int = 1) -> list[object]:
    if (
        not isinstance(value, list)
        or len(value) < minimum
        or len(value) > MAX_EVIDENCE_FILES
    ):
        raise ValueError(message)
    return value


def _positive_int(value: object, *, message: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(message)
    return value


def _nonnegative_int(value: object, *, message: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(message)
    return value


def _timestamp(value: object, *, message: str) -> datetime:
    if not isinstance(value, str):
        _invalid(message)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(message) from exc
    if parsed.tzinfo is None:
        raise ValueError(message)
    return parsed.astimezone(timezone.utc)


def _load_release_gate():
    cached = sys.modules.get("parallel_work_release_gate")
    if cached is not None:
        return cached
    path = (
        Path(__file__).resolve().parents[3]
        / "scripts"
        / "viventium"
        / "parallel_work_release_gate.py"
    )
    spec = importlib.util.spec_from_file_location("parallel_work_release_gate", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("release gate module is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _canonical_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _parse_run_at(value: object, *, now: datetime) -> str:
    try:
        parsed = datetime.fromisoformat(str(value or ""))
    except ValueError as exc:
        raise ValueError("journey timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise ValueError("journey timestamp requires a timezone")
    parsed = parsed.astimezone(timezone.utc)
    if parsed > now + MAX_FUTURE_SKEW or now - parsed > MAX_AGE:
        raise ValueError("journey timestamp is stale or in the future")
    return parsed.isoformat()


def _png_capture_facts(content: bytes) -> dict[str, int]:
    message = "screenshot evidence is not a real PNG capture"
    if not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError(message)
    offset = 8
    width = height = channels = 0
    image_data = bytearray()
    seen_header = seen_end = False
    while offset + 12 <= len(content):
        length = struct.unpack(">I", content[offset : offset + 4])[0]
        end = offset + 12 + length
        if length > MAX_EVIDENCE_BYTES or end > len(content):
            raise ValueError(message)
        kind = content[offset + 4 : offset + 8]
        data = content[offset + 8 : offset + 8 + length]
        expected_crc = struct.unpack(">I", content[offset + 8 + length : end])[0]
        if zlib.crc32(kind + data) & 0xFFFFFFFF != expected_crc:
            raise ValueError(message)
        if kind == b"IHDR":
            if seen_header or offset != 8 or length != 13:
                raise ValueError(message)
            width, height, depth, color, compression, filtering, interlace = (
                struct.unpack(">IIBBBBB", data)
            )
            if (
                width < 320
                or height < 180
                or width * height > MAX_CAPTURE_PIXELS
                or depth != 8
                or color not in {2, 6}
                or compression != 0
                or filtering != 0
                or interlace != 0
            ):
                raise ValueError(message)
            channels = 3 if color == 2 else 4
            seen_header = True
        elif kind == b"IDAT":
            if not seen_header or seen_end:
                raise ValueError(message)
            image_data.extend(data)
        elif kind == b"IEND":
            if not seen_header or length != 0 or end != len(content):
                raise ValueError(message)
            seen_end = True
            offset = end
            break
        offset = end
    if not seen_header or not seen_end or not image_data:
        raise ValueError(message)
    expected_bytes = height * (1 + width * channels)
    try:
        inflater = zlib.decompressobj()
        decoded = inflater.decompress(bytes(image_data), expected_bytes + 1)
        decoded += inflater.flush()
    except zlib.error as exc:
        raise ValueError(message) from exc
    if (
        len(decoded) != expected_bytes
        or inflater.unused_data
        or inflater.unconsumed_tail
    ):
        raise ValueError(message)
    stride = 1 + width * channels
    if any(decoded[index * stride] > 4 for index in range(height)):
        raise ValueError(message)
    samples = decoded[1 : min(len(decoded), 65_536)]
    if len(set(samples)) < 16 or max(samples) - min(samples) < 24:
        raise ValueError(message)
    return {"width": width, "height": height}


def _voice_recording_facts(content: bytes) -> dict[str, int]:
    message = "voice recording is missing audible installed-call evidence"
    try:
        with wave.open(io.BytesIO(content), "rb") as recording:
            channels = recording.getnchannels()
            sample_width = recording.getsampwidth()
            rate = recording.getframerate()
            frames = recording.getnframes()
            if (
                channels not in {1, 2}
                or sample_width != 2
                or rate < 8_000
                or frames < rate
            ):
                raise ValueError(message)
            samples = recording.readframes(min(frames, rate * 2))
            values = struct.unpack(f"<{len(samples) // 2}h", samples)
            if not values or max(abs(value) for value in values) < 256:
                raise ValueError(message)
    except (EOFError, OSError, struct.error, wave.Error) as exc:
        raise ValueError(message) from exc
    return {"frames": frames, "rate": rate}


def _correlation(value: object, *, case_id: str) -> dict[str, object]:
    correlation = _object(
        value,
        CORRELATION_FIELDS,
        message="journey correlation is invalid",
    )
    _hash(correlation["ownerRefHash"], message="journey owner identity is invalid")
    _hash(correlation["logicalTurnRefHash"], message="journey logical turn is invalid")
    _positive_int(
        correlation["turnRevision"], message="journey turn revision is invalid"
    )
    if correlation["surface"] != CASE_SURFACES[case_id]:
        raise ValueError("journey origin surface does not match the required case")
    return correlation


def _verified_evidence(
    raw: object,
    *,
    evidence_root: Path,
    case_id: str,
    correlation: dict[str, object],
    candidate_digest: str,
    artifact_digest: str,
    run_at: datetime,
) -> tuple[list[dict[str, object]], set[str]]:
    if not isinstance(raw, list) or not raw or len(raw) > MAX_EVIDENCE_FILES:
        raise ValueError("journey evidence list is invalid")
    verified: list[dict[str, object]] = []
    ids: set[str] = set()
    paths: set[str] = set()
    total_bytes = 0
    for item in raw:
        if not isinstance(item, dict) or set(item) != EVIDENCE_FIELDS:
            raise ValueError("journey evidence entry is invalid")
        evidence_id = str(item.get("id") or "")
        kind = str(item.get("kind") or "")
        relative_text = str(item.get("path") or "")
        digest = str(item.get("sha256") or "")
        relative = Path(relative_text)
        if SAFE_ID.fullmatch(evidence_id) is None or evidence_id in ids:
            raise ValueError("journey evidence id is invalid or duplicated")
        if (
            SAFE_KIND.fullmatch(kind) is None
            or kind not in CASE_EVIDENCE_MINIMUMS[case_id]
            or kind not in EVIDENCE_SURFACES
            or SHA256.fullmatch(digest) is None
        ):
            raise ValueError("journey evidence metadata is invalid")
        if (
            item["candidateDigest"] != candidate_digest
            or item["artifactDigest"] != artifact_digest
        ):
            raise ValueError(
                "evidence candidate identity does not match the installed artifact"
            )
        if item["ownerRefHash"] != correlation["ownerRefHash"]:
            raise ValueError("evidence owner does not match the journey")
        if item["originSurface"] != correlation["surface"]:
            raise ValueError("evidence origin surface does not match the journey")
        if item["surface"] != EVIDENCE_SURFACES[kind]:
            raise ValueError("evidence capture surface does not match its producer")
        if item["logicalTurnRefHash"] != correlation["logicalTurnRefHash"]:
            raise ValueError("evidence logical turn does not match the journey")
        if item["turnRevision"] != correlation["turnRevision"]:
            raise ValueError("evidence turn revision does not match the journey")
        work_ref = item["workRefHash"]
        run_ref = item["runRefHash"]
        if (work_ref is None) != (run_ref is None):
            raise ValueError("evidence work and run identities are incomplete")
        if work_ref is not None:
            _hash(work_ref, message="evidence work identity is invalid")
            _hash(run_ref, message="evidence run identity is invalid")
        observed_at = _timestamp(
            item["observedAt"], message="evidence observation time is invalid"
        )
        if observed_at > run_at + MAX_FUTURE_SKEW or run_at - observed_at > MAX_AGE:
            raise ValueError("evidence observation time is stale or in the future")
        if (
            relative.is_absolute()
            or not relative_text
            or ".." in relative.parts
            or relative.as_posix() != relative_text
        ):
            raise ValueError("evidence path is invalid")
        supplied = evidence_root / relative
        try:
            exact = supplied.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise ValueError("journey evidence file is unavailable") from exc
        if supplied.is_symlink() or not _inside(exact, evidence_root):
            raise ValueError("evidence path is invalid")
        parent = supplied.parent
        while parent != evidence_root:
            metadata = parent.lstat()
            if (
                parent.is_symlink()
                or not stat.S_ISDIR(metadata.st_mode)
                or metadata.st_uid != os.getuid()
                or metadata.st_mode & 0o077
            ):
                raise ValueError("evidence path is invalid")
            parent = parent.parent
        canonical_path = exact.relative_to(evidence_root).as_posix()
        if canonical_path in paths:
            raise ValueError("evidence file is duplicated")
        content = _read_file(
            exact,
            max_bytes=MAX_EVIDENCE_BYTES,
            label="journey evidence file",
            private=True,
        )
        total_bytes += len(content)
        if total_bytes > MAX_EVIDENCE_BYTES:
            raise ValueError("journey evidence exceeds the aggregate size limit")
        measured = hashlib.sha256(content).hexdigest()
        if measured != digest:
            raise ValueError("evidence digest did not match")
        entry: dict[str, object] = {
            "id": evidence_id,
            "kind": kind,
            "path": canonical_path,
            "sha256": measured,
            "sizeBytes": len(content),
            "workRefHash": work_ref,
            "runRefHash": run_ref,
            "_content": content,
        }
        if kind in PNG_EVIDENCE_KINDS:
            if exact.suffix.lower() != ".png":
                raise ValueError("screenshot evidence is not a real PNG capture")
            entry["_capture"] = _png_capture_facts(content)
        elif kind == "voice_recording":
            if exact.suffix.lower() != ".wav":
                raise ValueError(
                    "voice recording is missing audible installed-call evidence"
                )
            entry["_capture"] = _voice_recording_facts(content)
        elif kind == "artifact_bytes":
            try:
                html = content.decode("utf-8").lower()
            except UnicodeError as exc:
                raise ValueError(
                    "artifact bytes do not contain a complete HTML document"
                ) from exc
            if exact.suffix.lower() not in {".html", ".htm"} or any(
                marker not in html for marker in ("<html", "<body", "</html>")
            ):
                raise ValueError(
                    "artifact bytes do not contain a complete HTML document"
                )
        elif kind == "attachment_bytes":
            if not content:
                raise ValueError("attachment bytes or order are invalid")
        else:
            if exact.suffix.lower() != ".json":
                raise ValueError("semantic evidence shape is invalid")
            document = _json_bytes(content, label="semantic evidence")
            if not isinstance(document, dict) or set(document) != SEMANTIC_FIELDS:
                raise ValueError("semantic evidence shape is invalid")
            if (
                document.get("contractVersion") != CONTRACT_VERSION
                or document.get("schema") != SEMANTIC_SCHEMA
            ):
                raise ValueError("semantic evidence shape is invalid")
            if document.get("kind") != kind:
                raise ValueError(
                    "semantic evidence identity does not match its evidence entry"
                )
            if document.get("producer") != EVIDENCE_PRODUCERS.get(kind):
                raise ValueError("semantic evidence producer is not authoritative")
            if any(
                document.get(field) != item[field] for field in EVIDENCE_BINDING_FIELDS
            ):
                raise ValueError(
                    "semantic evidence identity does not match its evidence entry"
                )
            if not isinstance(document.get("payload"), dict):
                raise ValueError("semantic evidence shape is invalid")
            entry["_payload"] = document["payload"]
        ids.add(evidence_id)
        paths.add(canonical_path)
        verified.append(entry)
    return sorted(verified, key=lambda item: str(item["id"])), ids


def _verified_checks(
    raw: object,
    *,
    case_id: str,
    evidence_ids: set[str],
    evidence_by_id: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    required = CASE_CHECKS[case_id]
    if not isinstance(raw, list):
        _invalid("journey checks are invalid")
    indexed: dict[str, dict[str, object]] = {}
    referenced: set[str] = set()
    for item in raw:
        if not isinstance(item, dict) or set(item) != CHECK_FIELDS:
            raise ValueError("journey check is invalid")
        check_id = str(item.get("id") or "")
        if SAFE_ID.fullmatch(check_id) is None or check_id in indexed:
            raise ValueError("journey check id is invalid or duplicated")
        proof = item.get("evidence")
        if not isinstance(proof, list) or not proof:
            raise ValueError("journey check has no evidence")
        proof_ids = [str(value or "") for value in proof]
        if len(proof_ids) != len(set(proof_ids)) or not set(proof_ids) <= evidence_ids:
            raise ValueError("journey check evidence reference is invalid")
        required_kinds = CHECK_EVIDENCE_KINDS.get(check_id)
        if required_kinds is None:
            raise ValueError("required journey check is missing or unknown")
        referenced_kinds = {
            str(evidence_by_id[evidence_id]["kind"]) for evidence_id in proof_ids
        }
        if not required_kinds <= referenced_kinds:
            raise ValueError(
                "journey check does not contain its required semantic evidence"
            )
        referenced.update(proof_ids)
        indexed[check_id] = {"id": check_id, "evidence": sorted(proof_ids)}
    if set(indexed) != required:
        raise ValueError("required journey check is missing or unknown")
    if referenced != evidence_ids:
        raise ValueError("evidence is not bound to a journey check")
    return [indexed[check_id] for check_id in sorted(indexed)]


def _entries(evidence: list[dict[str, object]], kind: str) -> list[dict[str, object]]:
    return [item for item in evidence if item["kind"] == kind]


def _payload(entry: dict[str, object], *, message: str) -> dict[str, object]:
    payload = entry.get("_payload")
    if not isinstance(payload, dict):
        _invalid(message)
    return payload


def _same_owner(value: object, owner: str, *, message: str) -> None:
    if _hash(value, message=message) != owner:
        raise ValueError(message)


def _installed_identity_proof(
    evidence: list[dict[str, object]],
    *,
    candidate_digest: str,
    artifact_digest: str,
    owner: str,
    origin: str,
) -> None:
    entry = _entries(evidence, "installed_identity")[0]
    payload = _object(
        _payload(entry, message="installed runtime identity is invalid"),
        {
            "measuredCandidateDigest",
            "measuredArtifactDigest",
            "runtimeProcessRefHash",
            "ownerRefHash",
            "originSurface",
        },
        message="installed runtime identity is invalid",
    )
    if (
        payload["measuredCandidateDigest"] != candidate_digest
        or payload["measuredArtifactDigest"] != artifact_digest
        or payload["ownerRefHash"] != owner
        or payload["originSurface"] != origin
    ):
        raise ValueError("installed runtime identity is not candidate and owner bound")
    _hash(
        payload["runtimeProcessRefHash"],
        message="installed runtime process identity is invalid",
    )


def _runtime_rows_proof(
    evidence: list[dict[str, object]],
    *,
    owner: str,
    origin: str,
    turn: str,
    revision: int,
    case_id: str,
    now: datetime,
) -> dict[str, object]:
    message = "runtime lifecycle rows are invalid"
    payload = _object(
        _payload(_entries(evidence, "glasshive_rows")[0], message=message),
        {"works", "runs", "attempts", "leases", "actions"},
        message=message,
    )
    work_rows = _list(payload["works"], message=message, minimum=2)
    run_rows = _list(payload["runs"], message=message, minimum=2)
    attempt_rows = _list(
        payload["attempts"], message="runtime attempt is invalid", minimum=2
    )
    lease_rows = _list(payload["leases"], message="runtime lease is invalid", minimum=2)
    if not (
        len(work_rows) == len(run_rows) == len(attempt_rows) == len(lease_rows) == 2
    ):
        raise ValueError("exactly two independent mission runtime rows are required")

    works: dict[str, dict[str, object]] = {}
    workers: set[str] = set()
    workspaces: set[str] = set()
    for raw in work_rows:
        row = _object(
            raw,
            {
                "workRefHash",
                "ownerRefHash",
                "originSurface",
                "logicalTurnRefHash",
                "turnRevision",
                "workerRefHash",
                "workspaceRefHash",
            },
            message=message,
        )
        _same_owner(
            row["ownerRefHash"], owner, message="work owner does not match the journey"
        )
        if (
            row["originSurface"] != origin
            or row["logicalTurnRefHash"] != turn
            or row["turnRevision"] != revision
        ):
            raise ValueError("work origin or turn revision does not match the journey")
        work_ref = _hash(row["workRefHash"], message="runtime work identity is invalid")
        worker_ref = _hash(row["workerRefHash"], message="worker isolation is invalid")
        workspace_ref = _hash(
            row["workspaceRefHash"], message="worker isolation is invalid"
        )
        if work_ref in works or worker_ref in workers or workspace_ref in workspaces:
            raise ValueError(
                "worker isolation requires distinct mission and workspace identities"
            )
        works[work_ref] = row
        workers.add(worker_ref)
        workspaces.add(workspace_ref)

    attempts: dict[str, dict[str, object]] = {}
    for raw in attempt_rows:
        row = _object(
            raw,
            {
                "attemptRefHash",
                "runRefHash",
                "workRefHash",
                "ownerRefHash",
                "state",
                "openedAt",
                "runtimeInvokedAt",
                "closedAt",
            },
            message="runtime attempt is invalid",
        )
        _same_owner(
            row["ownerRefHash"], owner, message="runtime attempt owner is invalid"
        )
        attempt_ref = _hash(row["attemptRefHash"], message="runtime attempt is invalid")
        if attempt_ref in attempts or row["workRefHash"] not in works:
            raise ValueError(
                "runtime attempt is duplicated or does not match exact work"
            )
        attempts[attempt_ref] = row

    leases: dict[str, dict[str, object]] = {}
    for raw in lease_rows:
        row = _object(
            raw,
            {
                "leaseRefHash",
                "runRefHash",
                "workRefHash",
                "ownerRefHash",
                "workerRefHash",
                "executorRefHash",
                "acquiredAt",
                "runtimeInvokedAt",
                "expiresAt",
                "releasedAt",
            },
            message="runtime lease is invalid",
        )
        _same_owner(
            row["ownerRefHash"], owner, message="runtime lease owner is invalid"
        )
        lease_ref = _hash(row["leaseRefHash"], message="runtime lease is invalid")
        if lease_ref in leases or row["workRefHash"] not in works:
            raise ValueError("runtime lease is duplicated or does not match exact work")
        leases[lease_ref] = row

    runs: dict[str, dict[str, object]] = {}
    windows: list[tuple[datetime, datetime]] = []
    containers: set[str] = set()
    for raw in run_rows:
        row = _object(
            raw,
            {
                "runRefHash",
                "workRefHash",
                "ownerRefHash",
                "workerRefHash",
                "attemptRefHash",
                "leaseRefHash",
                "workspaceRefHash",
                "containerRefHash",
                "executionMode",
                "state",
                "startedAt",
                "runtimeInvokedAt",
                "finishedAt",
            },
            message=message,
        )
        _same_owner(row["ownerRefHash"], owner, message="runtime run owner is invalid")
        run_ref = _hash(row["runRefHash"], message="runtime run identity is invalid")
        work_ref = _hash(row["workRefHash"], message="runtime work identity is invalid")
        work = works.get(work_ref)
        if run_ref in runs or work is None:
            raise ValueError(
                "runtime work and run identities are duplicated or unrelated"
            )
        if (
            row["workerRefHash"] != work["workerRefHash"]
            or row["workspaceRefHash"] != work["workspaceRefHash"]
        ):
            raise ValueError("worker isolation does not match the exact mission")
        container_ref = _hash(
            row["containerRefHash"], message="worker isolation is invalid"
        )
        if container_ref in containers or row["executionMode"] != "isolated_container":
            raise ValueError("worker isolation requires distinct container execution")
        containers.add(container_ref)
        if row["state"] not in {"running", "completed"}:
            raise ValueError(
                "runtime invocation is not proven by a running or completed run"
            )
        invoked = _timestamp(
            row["runtimeInvokedAt"], message="runtime invocation is missing"
        )
        started = _timestamp(
            row["startedAt"], message="runtime invocation start is invalid"
        )
        if invoked < started:
            raise ValueError("runtime invocation precedes the durable start")
        attempt = attempts.get(str(row["attemptRefHash"]))
        if (
            attempt is None
            or attempt["runRefHash"] != run_ref
            or attempt["workRefHash"] != work_ref
        ):
            raise ValueError("runtime attempt does not match the exact mission and run")
        attempt_invoked = _timestamp(
            attempt["runtimeInvokedAt"], message="runtime attempt invocation is missing"
        )
        opened = _timestamp(
            attempt["openedAt"], message="runtime attempt opening is invalid"
        )
        if attempt_invoked != invoked or opened > invoked:
            raise ValueError("runtime attempt does not prove the exact invocation")
        lease = leases.get(str(row["leaseRefHash"]))
        if (
            lease is None
            or lease["runRefHash"] != run_ref
            or lease["workRefHash"] != work_ref
            or lease["workerRefHash"] != row["workerRefHash"]
            or lease["executorRefHash"] != container_ref
        ):
            raise ValueError("runtime lease does not match the exact worker and run")
        acquired = _timestamp(
            lease["acquiredAt"], message="runtime lease acquisition is invalid"
        )
        lease_invoked = _timestamp(
            lease["runtimeInvokedAt"], message="runtime lease invocation is invalid"
        )
        expires = _timestamp(
            lease["expiresAt"], message="runtime lease expiration is invalid"
        )
        if not acquired <= invoked < expires or lease_invoked != invoked:
            raise ValueError("runtime lease was not live for the exact invocation")
        if row["state"] == "running":
            if (
                attempt["state"] != "open"
                or attempt["closedAt"] is not None
                or lease["releasedAt"] is not None
                or expires <= now
                or row["finishedAt"] is not None
            ):
                raise ValueError(
                    "runtime lease and attempt do not prove a live running mission"
                )
            finished = now
        else:
            finished = _timestamp(
                row["finishedAt"], message="runtime completion is invalid"
            )
            closed = _timestamp(
                attempt["closedAt"], message="runtime attempt closure is invalid"
            )
            released = _timestamp(
                lease["releasedAt"], message="runtime lease release is invalid"
            )
            if (
                attempt["state"] != "closed"
                or finished <= invoked
                or closed < finished
                or released < finished
            ):
                raise ValueError(
                    "runtime attempt or lease does not prove completed invocation"
                )
        windows.append((invoked, finished))
        runs[run_ref] = row

    if case_id in {"PWK-UC-014", "PWK-UC-015", "PWK-UC-019"} and (
        max(start for start, _end in windows) >= min(end for _start, end in windows)
    ):
        raise ValueError("runtime windows do not overlap")

    actions = _list(
        payload["actions"], message="exact mission action evidence is invalid"
    )
    steers = []
    queue_messages = []
    normalized_actions = []
    for raw in actions:
        action_name = raw.get("action") if isinstance(raw, dict) else None
        required_fields = {
            "action",
            "workRefHash",
            "runRefHash",
            "ownerRefHash",
            "receiptRefHash",
            "committedAt",
        }
        if action_name in {"queue", "message"}:
            required_fields.add("workerRefHash")
        action = _object(
            raw,
            required_fields,
            message="exact mission action evidence is invalid",
        )
        _same_owner(
            action["ownerRefHash"],
            owner,
            message="exact mission action owner is invalid",
        )
        if (
            action["runRefHash"] not in runs
            or runs[str(action["runRefHash"])]["workRefHash"] != action["workRefHash"]
        ):
            raise ValueError("exact mission action crosses work or run identity")
        _hash(
            action["receiptRefHash"], message="exact mission action receipt is invalid"
        )
        _timestamp(
            action["committedAt"], message="exact mission action timestamp is invalid"
        )
        if action["action"] == "steer":
            steers.append(action)
        elif action["action"] in {"queue", "message"}:
            if action["workerRefHash"] != runs[str(action["runRefHash"])]["workerRefHash"]:
                raise ValueError("Queue or Message did not reuse the exact existing Worker")
            queue_messages.append(action)
        else:
            raise ValueError("exact mission action is unsupported")
        normalized_actions.append(action)
    if len(steers) != 1:
        raise ValueError("exact A-only steering is missing or duplicated")
    if case_id == "PWK-UC-019":
        if (
            len(queue_messages) != 2
            or {str(item["action"]) for item in queue_messages} != {"queue", "message"}
            or any(
                item["workRefHash"] != steers[0]["workRefHash"]
                or item["runRefHash"] != steers[0]["runRefHash"]
                for item in queue_messages
            )
        ):
            raise ValueError("Queue and Message did not reuse the exact existing Worker")
    elif queue_messages:
        raise ValueError("Queue or Message is not valid for this journey")

    for entry in evidence:
        work_ref = entry["workRefHash"]
        run_ref = entry["runRefHash"]
        if work_ref is not None and (
            work_ref not in works
            or run_ref not in runs
            or runs[str(run_ref)]["workRefHash"] != work_ref
        ):
            raise ValueError(
                "evidence work and run identities cross the proven missions"
            )
    return {
        "works": works,
        "runs": runs,
        "steer": steers[0],
        "actions": normalized_actions,
        "windows": windows,
    }


def _worker_isolation_proof(
    evidence: list[dict[str, object]], *, owner: str, runtime: dict[str, object]
) -> None:
    message = "worker isolation is not proven"
    payload = _object(
        _payload(_entries(evidence, "isolation_probe")[0], message=message),
        {"workers"},
        message=message,
    )
    rows = _list(payload["workers"], message=message, minimum=2)
    if len(rows) != len(runtime["works"]):
        raise ValueError(message)
    seen: dict[str, set[str]] = {
        key: set()
        for key in (
            "workRefHash",
            "workerRefHash",
            "containerRefHash",
            "workspaceRefHash",
            "homeRefHash",
            "networkRefHash",
            "pidNamespaceRefHash",
        )
    }
    for raw in rows:
        row = _object(
            raw,
            {
                "ownerRefHash",
                "workRefHash",
                "runRefHash",
                "workerRefHash",
                "containerRefHash",
                "workspaceRefHash",
                "homeRefHash",
                "networkRefHash",
                "pidNamespaceRefHash",
                "executionMode",
                "hostStateReadable",
                "serviceEnvironmentReadable",
                "dockerSocketReadable",
                "ambientAuthority",
                "peerProbes",
            },
            message=message,
        )
        _same_owner(row["ownerRefHash"], owner, message=message)
        run = runtime["runs"].get(row["runRefHash"])
        if run is None or any(
            row[field] != run[field]
            for field in (
                "workRefHash",
                "workerRefHash",
                "containerRefHash",
                "workspaceRefHash",
                "executionMode",
            )
        ):
            raise ValueError(message)
        for field, identities in seen.items():
            identity = _hash(row[field], message=message)
            if identity in identities:
                raise ValueError(message)
            identities.add(identity)
        if row["executionMode"] != "isolated_container" or any(
            row[field] is not False
            for field in (
                "hostStateReadable",
                "serviceEnvironmentReadable",
                "dockerSocketReadable",
                "ambientAuthority",
            )
        ):
            raise ValueError(message)
        peers = _list(row["peerProbes"], message=message)
        expected_peers = set(runtime["works"]) - {str(row["workRefHash"])}
        observed_peers = set()
        for raw_peer in peers:
            peer = _object(raw_peer, {"workRefHash", "reachable"}, message=message)
            if peer["reachable"] is not False or peer["workRefHash"] in observed_peers:
                raise ValueError(message)
            observed_peers.add(str(peer["workRefHash"]))
        if observed_peers != expected_peers:
            raise ValueError(message)


def _delivery_proof(
    evidence: list[dict[str, object]],
    *,
    owner: str,
    origin: str,
    runtime: dict[str, object],
) -> None:
    payload = _object(
        _payload(
            _entries(evidence, "delivery_ledger")[0],
            message="callback delivery ledger is invalid",
        ),
        {"callbacks", "deliveries", "replays"},
        message="callback delivery ledger is invalid",
    )
    callback_rows = _list(
        payload["callbacks"], message="callback evidence is invalid", minimum=2
    )
    delivery_rows = _list(
        payload["deliveries"], message="delivery evidence is invalid", minimum=2
    )
    if len(callback_rows) != len(runtime["works"]):
        raise ValueError("callback evidence is missing or duplicated")
    if len(delivery_rows) != len(runtime["works"]):
        raise ValueError("delivery evidence is missing or duplicated")
    callbacks: dict[str, dict[str, object]] = {}
    callback_works: set[str] = set()
    for raw in callback_rows:
        row = _object(
            raw,
            {
                "callbackRef",
                "ownerRefHash",
                "workRefHash",
                "runRefHash",
                "attemptNumber",
                "transportState",
                "acceptedAt",
            },
            message="callback evidence is invalid",
        )
        callback = row["callbackRef"]
        if not isinstance(callback, str) or CALLBACK_REF.fullmatch(callback) is None:
            raise ValueError("callback identity is not canonical")
        _same_owner(
            row["ownerRefHash"],
            owner,
            message="callback owner does not match the journey",
        )
        run = runtime["runs"].get(row["runRefHash"])
        if (
            run is None
            or run["workRefHash"] != row["workRefHash"]
            or callback in callbacks
            or row["workRefHash"] in callback_works
            or row["transportState"] != "http_accepted"
            or _positive_int(
                row["attemptNumber"], message="callback attempt is invalid"
            )
            != 1
        ):
            raise ValueError("callback evidence is duplicated or cross-related")
        _timestamp(row["acceptedAt"], message="callback acceptance time is invalid")
        callbacks[callback] = row
        callback_works.add(str(row["workRefHash"]))

    delivery_refs: set[str] = set()
    messages: set[str] = set()
    delivered_works: set[str] = set()
    for raw in delivery_rows:
        row = _object(
            raw,
            {
                "deliveryRefHash",
                "callbackRef",
                "ownerRefHash",
                "workRefHash",
                "runRefHash",
                "surface",
                "state",
                "messageRefHash",
                "deliveredAt",
            },
            message="delivery evidence is invalid",
        )
        _same_owner(
            row["ownerRefHash"],
            owner,
            message="delivery owner does not match the journey",
        )
        delivery_ref = _hash(
            row["deliveryRefHash"], message="delivery identity is invalid"
        )
        message_ref = _hash(
            row["messageRefHash"], message="delivery message identity is invalid"
        )
        callback = callbacks.get(str(row["callbackRef"]))
        if (
            callback is None
            or row["workRefHash"] != callback["workRefHash"]
            or row["runRefHash"] != callback["runRefHash"]
            or row["surface"] != origin
            or row["state"] != "sent"
            or delivery_ref in delivery_refs
            or message_ref in messages
            or row["workRefHash"] in delivered_works
        ):
            raise ValueError(
                "delivery is missing, duplicated, transport-only, or cross-related"
            )
        delivered = _timestamp(row["deliveredAt"], message="delivery time is invalid")
        accepted = _timestamp(
            callback["acceptedAt"], message="callback acceptance time is invalid"
        )
        if delivered < accepted:
            raise ValueError("delivery precedes the accepted callback")
        delivery_refs.add(delivery_ref)
        messages.add(message_ref)
        delivered_works.add(str(row["workRefHash"]))
    if delivered_works != set(runtime["works"]):
        raise ValueError("delivery evidence does not cover every exact mission")

    replays = _list(payload["replays"], message="callback replay evidence is invalid")
    for raw in replays:
        replay = _object(
            raw,
            {
                "callbackRef",
                "ownerRefHash",
                "workRefHash",
                "runRefHash",
                "outcome",
                "deliveryRowsCreated",
            },
            message="callback replay evidence is invalid",
        )
        callback = callbacks.get(str(replay["callbackRef"]))
        if (
            callback is None
            or replay["ownerRefHash"] != owner
            or replay["workRefHash"] != callback["workRefHash"]
            or replay["runRefHash"] != callback["runRefHash"]
            or replay["outcome"] != "suppressed"
            or _nonnegative_int(
                replay["deliveryRowsCreated"], message="callback replay is invalid"
            )
            != 0
        ):
            raise ValueError("callback replay was not suppressed exactly once")


def _node_executable() -> Path:
    supplied = Path(os.environ.get("VIVENTIUM_QA_NODE_EXECUTABLE", ""))
    try:
        if not supplied.is_absolute() or supplied.is_symlink():
            raise ValueError
        exact = supplied.resolve(strict=True)
        metadata = exact.stat()
    except (OSError, RuntimeError, ValueError) as exc:
        raise ValueError("native producer signature verifier is unavailable") from exc
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid not in {0, os.getuid()}
        or metadata.st_mode & 0o022
        or not os.access(exact, os.X_OK)
    ):
        raise ValueError("native producer signature verifier is unavailable")
    return exact


def _verify_ed25519_proof(
    public_key_spki: str, payload: dict[str, object], proof: str
) -> str:
    if (
        re.fullmatch(r"[A-Za-z0-9_-]{40,256}", public_key_spki) is None
        or re.fullmatch(r"ed25519:[A-Za-z0-9_-]{86}", proof) is None
    ):
        raise ValueError("native producer attestation authentication failed")
    try:
        padding = "=" * (-len(public_key_spki) % 4)
        public_der = base64.urlsafe_b64decode(public_key_spki + padding)
        signature = proof.removeprefix("ed25519:")
        message = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        request = json.dumps(
            {
                "key": base64.urlsafe_b64encode(public_der).decode("ascii").rstrip("="),
                "message": base64.urlsafe_b64encode(message)
                .decode("ascii")
                .rstrip("="),
                "signature": signature,
            },
            separators=(",", ":"),
        )
        script = (
            "const c=require('node:crypto'),fs=require('node:fs');"
            "const x=JSON.parse(fs.readFileSync(0,'utf8'));"
            "const k=c.createPublicKey({key:Buffer.from(x.key,'base64url'),"
            "format:'der',type:'spki'});"
            "if(k.asymmetricKeyType!=='ed25519'||"
            "!c.verify(null,Buffer.from(x.message,'base64url'),k,"
            "Buffer.from(x.signature,'base64url')))process.exit(2);"
        )
        result = subprocess.run(
            [str(_node_executable()), "-e", script],
            input=request,
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
            env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
        )
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        raise ValueError("native producer attestation authentication failed") from exc
    if result.returncode != 0 or result.stdout or result.stderr:
        raise ValueError("native producer attestation authentication failed")
    return hashlib.sha256(public_der).hexdigest()


def _native_producer_attestation_proof(
    raw: object,
    *,
    owner: str,
    origin: str,
    feelings_capsule: str,
    runtime: dict[str, object],
    route_receipt: dict[str, object],
    route_truth: object,
    now: datetime,
) -> None:
    records = _list(
        raw, message="native producer attestations are unavailable", minimum=3
    )
    if len(records) != 3:
        raise ValueError("native producer attestations are unavailable")
    observed_workers: set[str] = set()
    signed_routes: set[tuple[str, str]] = set()
    producer_key_ids: dict[str, str] = {}
    main_count = 0
    main_attestation: dict[str, object] | None = None
    now_ms = int(now.timestamp() * 1000)
    for raw_record in records:
        record = _object(
            raw_record,
            {"publicKeySpki", "attestation"},
            message="native producer attestation is invalid",
        )
        attestation = _object(
            record["attestation"],
            NATIVE_ATTESTATION_FIELDS,
            message="native producer attestation is invalid",
        )
        proof = str(attestation["proof"])
        unsigned = {key: value for key, value in attestation.items() if key != "proof"}
        key_id = _verify_ed25519_proof(
            str(record["publicKeySpki"]), unsigned, proof
        )
        if (
            attestation["contractVersion"] != 1
            or attestation["keyId"] != key_id
            or attestation["ownerRefHash"] != owner
            or attestation["surface"] != origin
            or attestation["snapshotHash"] != feelings_capsule
            or attestation["capsuleOccurrenceCount"] != 1
        ):
            raise ValueError("native producer attestation binding is invalid")
        for field in (
            "snapshotHash",
            "nativeRequestSha256",
            "providerAttemptRefHash",
            "providerRefHash",
            "modelRefHash",
        ):
            _hash(
                attestation[field],
                message="native producer attestation binding is invalid",
            )
        issued = attestation["issuedAtMs"]
        expires = attestation["expiresAtMs"]
        if (
            type(issued) is not int
            or type(expires) is not int
            or issued > now_ms + 1000
            or expires <= now_ms
            or expires - issued > 10 * 60 * 1000
        ):
            raise ValueError("native producer attestation is stale")
        actor = attestation["actor"]
        producer = attestation["producer"]
        previous_key = producer_key_ids.setdefault(str(producer), key_id)
        if previous_key != key_id:
            raise ValueError("native producer authority changed within one journey")
        if actor == "main":
            if (
                producer != "core.native_receipt"
                or attestation["workRefHash"] is not None
                or attestation["runRefHash"] is not None
            ):
                raise ValueError("native Main producer attestation is invalid")
            main_count += 1
            main_attestation = attestation
        elif actor == "worker":
            if producer != "glasshive.native_provider_receipt":
                raise ValueError("native Worker producer attestation is invalid")
            work_ref = _hash(
                attestation["workRefHash"],
                message="native Worker producer attestation is invalid",
            )
            run_ref = _hash(
                attestation["runRefHash"],
                message="native Worker producer attestation is invalid",
            )
            run = runtime["runs"].get(run_ref)
            if (
                run is None
                or run["workRefHash"] != work_ref
                or work_ref in observed_workers
            ):
                raise ValueError("native Worker producer attestation is invalid")
            observed_workers.add(work_ref)
        else:
            raise ValueError("native producer attestation actor is invalid")
        signed_routes.add(
            (str(attestation["providerRefHash"]), str(attestation["modelRefHash"]))
        )
    if main_count != 1 or observed_workers != set(runtime["works"]):
        raise ValueError("native Main and Worker producer attestations are incomplete")
    if set(producer_key_ids) != {
        "core.native_receipt",
        "glasshive.native_provider_receipt",
    }:
        raise ValueError("native producer authorities are incomplete")
    if (
        main_attestation is None
        or main_attestation["modelRefHash"] != route_receipt["modelRefHash"]
        or main_attestation["providerAttemptRefHash"]
        != route_receipt["providerAttemptRefHash"]
    ):
        raise ValueError("signed Main route does not match its native route receipt")

    route = _object(
        route_truth,
        {"originSurface", "configured", "attempts"},
        message="configured provider route truth is invalid",
    )
    if route["originSurface"] != origin:
        raise ValueError("configured provider route truth is invalid")
    configured: list[tuple[str, str]] = []
    for raw_configured in _list(
        route["configured"], message="configured provider route truth is invalid"
    ):
        item = _object(
            raw_configured,
            {"providerRefHash", "modelRefHash"},
            message="configured provider route truth is invalid",
        )
        pair = (
            _hash(
                item["providerRefHash"],
                message="configured provider route truth is invalid",
            ),
            _hash(
                item["modelRefHash"],
                message="configured provider route truth is invalid",
            ),
        )
        if pair in configured:
            raise ValueError("configured provider route truth is duplicated")
        configured.append(pair)
    attempts = _list(
        route["attempts"], message="configured provider route truth is invalid"
    )
    used: set[tuple[str, str]] = set()
    failure_seen = False
    for position, raw_attempt in enumerate(attempts):
        attempt = _object(
            raw_attempt,
            {"providerRefHash", "modelRefHash", "outcome", "observed", "fallback"},
            message="configured provider attempt is invalid",
        )
        pair = (
            _hash(
                attempt["providerRefHash"],
                message="configured provider attempt is invalid",
            ),
            _hash(
                attempt["modelRefHash"],
                message="configured provider attempt is invalid",
            ),
        )
        if pair not in configured or attempt["observed"] is not True:
            raise ValueError("unconfigured provider attempt is invalid")
        if attempt["fallback"] is True and (
            position == 0 or pair == configured[0] or not failure_seen
        ):
            raise ValueError("provider fallback did not follow an observed failure")
        if attempt["outcome"] == "used":
            used.add(pair)
        elif attempt["outcome"] in {
            "quota_exhausted",
            "provider_unavailable",
            "provider_unauthorized",
            "timeout",
        }:
            failure_seen = True
        else:
            raise ValueError("configured provider attempt outcome is invalid")
    if signed_routes != used:
        raise ValueError("signed native provider routes do not match used attempts")


def _native_receipt_proof(
    evidence: list[dict[str, object]],
    *,
    owner: str,
    origin: str,
    turn: str,
    revision: int,
    runtime: dict[str, object],
    case_id: str,
    now: datetime,
) -> None:
    entries = _entries(evidence, "native_receipt")
    if not entries:
        return
    payload = _object(
        _payload(entries[0], message="native Main receipt is invalid"),
        {
            "mainAgentRefHash",
            "feelingsCapsuleSha256",
            "route",
            "launches",
            "actions",
            *(
                {"producerAttestations", "routeTruth"}
                if case_id == "PWK-UC-019"
                else set()
            ),
        },
        message="native Main receipt is invalid",
    )
    _hash(
        payload["mainAgentRefHash"], message="native Main receipt identity is invalid"
    )
    _hash(
        payload["feelingsCapsuleSha256"],
        message="native Main feelings receipt is invalid",
    )
    route = _object(
        payload["route"],
        {"surface", "routeRefHash", "modelRefHash", "providerAttemptRefHash", "effort"},
        message="native route facts are invalid",
    )
    if route["surface"] != origin or route["effort"] not in {
        "minimal",
        "low",
        "medium",
        "high",
        "xhigh",
    }:
        raise ValueError("native route facts do not match the originating surface")
    for field in ("routeRefHash", "modelRefHash", "providerAttemptRefHash"):
        _hash(route[field], message="native route facts are missing")
    launches = _list(
        payload["launches"],
        message="native mission launch receipts are invalid",
        minimum=2,
    )
    if len(launches) != len(runtime["works"]):
        raise ValueError("native mission launch receipts are missing or duplicated")
    seen: set[str] = set()
    for raw in launches:
        launch = _object(
            raw,
            {
                "workRefHash",
                "runRefHash",
                "ownerRefHash",
                "logicalTurnRefHash",
                "turnRevision",
                "receiptRefHash",
                "committedAt",
            },
            message="native mission launch receipt is invalid",
        )
        run = runtime["runs"].get(launch["runRefHash"])
        if (
            run is None
            or run["workRefHash"] != launch["workRefHash"]
            or launch["ownerRefHash"] != owner
            or launch["logicalTurnRefHash"] != turn
            or launch["turnRevision"] != revision
            or launch["workRefHash"] in seen
        ):
            raise ValueError(
                "native mission launch receipt is duplicated or cross-related"
            )
        _hash(
            launch["receiptRefHash"], message="native mission launch receipt is invalid"
        )
        _timestamp(
            launch["committedAt"],
            message="native mission launch receipt time is invalid",
        )
        seen.add(str(launch["workRefHash"]))
    actions = _list(
        payload["actions"], message="native exact steering receipt is invalid"
    )
    if actions != runtime["actions"]:
        raise ValueError(
            "native exact steering changed another mission or lacks a durable receipt"
        )
    if case_id == "PWK-UC-019":
        _native_producer_attestation_proof(
            payload["producerAttestations"],
            owner=owner,
            origin=origin,
            feelings_capsule=str(payload["feelingsCapsuleSha256"]),
            runtime=runtime,
            route_receipt=route,
            route_truth=payload["routeTruth"],
            now=now,
        )


def _telegram_turn_proof(
    evidence: list[dict[str, object]],
    *,
    owner: str,
    turn: str,
    revision: int,
    runtime: dict[str, object],
) -> None:
    entries = _entries(evidence, "telegram_turn")
    if not entries:
        return
    message = "source revision does not prove one current Main reply"
    payload = _object(
        _payload(entries[0], message=message),
        {"events", "presentations"},
        message=message,
    )
    events = _list(payload["events"], message=message, minimum=2)
    sequences: list[int] = []
    revisions: list[int] = []
    seen: set[str] = set()
    for raw in events:
        event = _object(
            raw,
            {
                "sourceEventRefHash",
                "ownerRefHash",
                "logicalTurnRefHash",
                "turnRevision",
                "sourceSequence",
                "observedAt",
            },
            message=message,
        )
        source_ref = _hash(event["sourceEventRefHash"], message=message)
        if (
            source_ref in seen
            or event["ownerRefHash"] != owner
            or event["logicalTurnRefHash"] != turn
        ):
            raise ValueError(message)
        seen.add(source_ref)
        sequences.append(_positive_int(event["sourceSequence"], message=message))
        revisions.append(_positive_int(event["turnRevision"], message=message))
        _timestamp(event["observedAt"], message=message)
    if sequences != sorted(sequences) or len(set(sequences)) != len(sequences):
        raise ValueError(message)
    if revisions[-1] != revision or len(set(revisions)) < 2:
        raise ValueError(message)
    presentations = _list(payload["presentations"], message=message)
    if len(presentations) != 1:
        raise ValueError(message)
    presentation = _object(
        presentations[0],
        {
            "presentationRefHash",
            "ownerRefHash",
            "logicalTurnRefHash",
            "turnRevision",
            "author",
            "kind",
            "committedAt",
        },
        message=message,
    )
    if (
        presentation["ownerRefHash"] != owner
        or presentation["logicalTurnRefHash"] != turn
        or presentation["turnRevision"] != revision
        or presentation["author"] != "main"
        or presentation["kind"] != "quick_answer"
    ):
        raise ValueError(message)
    _hash(presentation["presentationRefHash"], message=message)
    committed = _timestamp(presentation["committedAt"], message=message)
    if not all(start <= committed < end for start, end in runtime["windows"]):
        raise ValueError(
            "source revision quick reply did not occur during parallel runtime"
        )


def _artifact_proof(
    evidence: list[dict[str, object]], *, owner: str, runtime: dict[str, object]
) -> dict[str, dict[str, object]]:
    records = _entries(evidence, "artifact_hash")
    contents = _entries(evidence, "artifact_bytes")
    if len(records) != len(contents):
        raise ValueError("artifact bytes are missing or duplicated")
    indexed_contents = {str(entry["workRefHash"]): entry for entry in contents}
    if len(indexed_contents) != len(contents):
        raise ValueError("artifact bytes are duplicated across missions")
    observed: dict[str, dict[str, object]] = {}
    digests: set[str] = set()
    for entry in records:
        payload = _object(
            _payload(
                entry, message="artifact bytes are not backed by an installed ledger"
            ),
            {
                "artifactRefHash",
                "ownerRefHash",
                "workRefHash",
                "runRefHash",
                "byteSha256",
                "sizeBytes",
                "mediaType",
                "state",
                "observedAt",
            },
            message="artifact bytes are not backed by an installed ledger",
        )
        _same_owner(
            payload["ownerRefHash"], owner, message="artifact bytes have another owner"
        )
        _hash(
            payload["artifactRefHash"],
            message="artifact bytes have no durable artifact identity",
        )
        work_ref = str(payload["workRefHash"])
        run = runtime["runs"].get(payload["runRefHash"])
        content = indexed_contents.get(work_ref)
        if (
            run is None
            or run["workRefHash"] != work_ref
            or entry["workRefHash"] != work_ref
            or entry["runRefHash"] != payload["runRefHash"]
            or content is None
            or content["runRefHash"] != payload["runRefHash"]
            or payload["byteSha256"] != content["sha256"]
            or _positive_int(
                payload["sizeBytes"], message="artifact bytes have an invalid size"
            )
            != content["sizeBytes"]
            or payload["mediaType"] != "text/html"
            or payload["state"] != "available"
            or work_ref in observed
            or payload["byteSha256"] in digests
        ):
            raise ValueError(
                "artifact bytes do not match the exact owner, work, run, or digest"
            )
        _timestamp(
            payload["observedAt"], message="artifact bytes observation time is invalid"
        )
        observed[work_ref] = payload
        digests.add(str(payload["byteSha256"]))
    return observed


def _surface_capture_proof(
    evidence: list[dict[str, object]],
    *,
    owner: str,
    case_id: str,
    artifacts: dict[str, dict[str, object]],
) -> None:
    telegram_captures = _entries(evidence, "telegram_screenshot")
    telegram_observations = _entries(evidence, "telegram_observation")
    if len(telegram_captures) != len(telegram_observations):
        raise ValueError("Telegram real-surface capture evidence is incomplete")
    telegram_digests = {str(item["sha256"]) for item in telegram_captures}
    for entry in telegram_observations:
        payload = _object(
            _payload(
                entry, message="Telegram real-surface capture evidence is invalid"
            ),
            {
                "captureSource",
                "screenshotSha256",
                "windowRefHash",
                "ownerRefHash",
                "visibleMessageRefHashes",
            },
            message="Telegram real-surface capture evidence is invalid",
        )
        if (
            payload["captureSource"] != "telegram_desktop_accessibility"
            or payload["screenshotSha256"] not in telegram_digests
            or payload["ownerRefHash"] != owner
        ):
            raise ValueError("Telegram real-surface capture evidence is missing")
        _hash(
            payload["windowRefHash"],
            message="Telegram real-surface window identity is invalid",
        )
        messages = _list(
            payload["visibleMessageRefHashes"],
            message="Telegram real-surface visible message proof is invalid",
        )
        for message_ref in messages:
            _hash(
                message_ref,
                message="Telegram real-surface visible message proof is invalid",
            )

    screenshots = _entries(evidence, "browser_screenshot")
    observations = _entries(evidence, "browser_observation")
    if len(screenshots) != len(observations):
        raise ValueError(
            "browser proof is missing a screenshot or semantic observation"
        )
    screenshot_by_digest = {str(entry["sha256"]): entry for entry in screenshots}
    if len(screenshot_by_digest) != len(screenshots):
        raise ValueError("browser proof reused the same screenshot")
    windows: set[str] = set()
    opened_artifacts: set[str] = set()
    for entry in observations:
        payload = _object(
            _payload(entry, message="browser proof is invalid"),
            {
                "captureSource",
                "screenshotSha256",
                "windowRefHash",
                "frameRefHash",
                "documentRefHash",
                "visibleContentSha256",
                "headed",
                "visible",
                "view",
                "artifactSha256",
                "sandboxed",
                "hostAuthority",
            },
            message="browser proof is invalid",
        )
        screenshot = screenshot_by_digest.get(str(payload["screenshotSha256"]))
        window_ref = _hash(
            payload["windowRefHash"], message="browser proof window identity is invalid"
        )
        if window_ref in windows:
            raise ValueError("browser windows are not independently proven")
        windows.add(window_ref)
        for field in ("frameRefHash", "documentRefHash", "visibleContentSha256"):
            _hash(
                payload[field],
                message="browser proof does not contain a real document capture",
            )
        if (
            screenshot is None
            or payload["captureSource"] != "browser_devtools"
            or payload["headed"] is not True
            or payload["visible"] is not True
            or screenshot["workRefHash"] != entry["workRefHash"]
            or screenshot["runRefHash"] != entry["runRefHash"]
        ):
            raise ValueError("browser proof is not a visible headed installed capture")
        if payload["view"] == "artifact":
            artifact = artifacts.get(str(entry["workRefHash"]))
            if (
                artifact is None
                or artifact["runRefHash"] != entry["runRefHash"]
                or payload["artifactSha256"] != artifact["byteSha256"]
            ):
                raise ValueError(
                    "browser proof does not show the exact delivered artifact"
                )
            opened_artifacts.add(str(entry["workRefHash"]))
            if case_id == "PWK-UC-018":
                artifact_bytes = next(
                    (
                        candidate
                        for candidate in _entries(evidence, "artifact_bytes")
                        if candidate["workRefHash"] == entry["workRefHash"]
                    ),
                    None,
                )
                if (
                    artifact_bytes is None
                    or b"<script" not in bytes(artifact_bytes["_content"]).lower()
                ):
                    raise ValueError(
                        "hostile artifact bytes do not exercise browser isolation"
                    )
                if (
                    payload["sandboxed"] is not True
                    or payload["hostAuthority"] is not False
                ):
                    raise ValueError(
                        "browser isolation did not contain hostile artifact authority"
                    )
        elif payload["view"] != "active_work" or payload["artifactSha256"] is not None:
            raise ValueError("browser proof has an unsupported visible surface")
    if artifacts and opened_artifacts != set(artifacts):
        raise ValueError("browser windows do not prove every exact artifact was opened")
    if (
        case_id in {"PWK-UC-014", "PWK-UC-015", "PWK-UC-019"}
        and len(opened_artifacts) != 2
    ):
        raise ValueError(
            "browser windows do not prove two independent delivered artifacts"
        )


def _trace_proof(
    evidence: list[dict[str, object]],
    *,
    owner: str,
    origin: str,
    turn: str,
    revision: int,
    runtime: dict[str, object],
) -> None:
    message = "trace evidence is not owner-scoped, append-only, and exact"
    payload = _object(
        _payload(_entries(evidence, "trace_export")[0], message=message),
        {
            "contractVersion",
            "producerTraceContractVersion",
            "promptProducerScope",
            "fullChainVerified",
            "overflowCount",
            "eventCount",
            "events",
            "chainSha256",
        },
        message=message,
    )
    if (
        payload["contractVersion"] != 2
        or payload["producerTraceContractVersion"] != 2
        or payload["promptProducerScope"] != "glasshive.worker_prompt_registry"
        or payload["fullChainVerified"] is not True
        or payload["overflowCount"] != 0
    ):
        raise ValueError(message)
    events = _list(payload["events"], message=message)
    if payload["eventCount"] != len(events) or len(events) > 100:
        raise ValueError(message)
    previous = "0" * 64
    coverage: dict[str, set[str]] = {str(work): set() for work in runtime["works"]}
    for position, raw in enumerate(events, start=1):
        event = _object(
            raw,
            {
                "sequence",
                "eventType",
                "ownerRefHash",
                "originSurface",
                "logicalTurnRefHash",
                "turnRevision",
                "workRefHash",
                "runRefHash",
                "previousSha256",
                "eventSha256",
            },
            message=message,
        )
        run = runtime["runs"].get(event["runRefHash"])
        if (
            _positive_int(event["sequence"], message=message) != position
            or event["ownerRefHash"] != owner
            or event["originSurface"] != origin
            or event["logicalTurnRefHash"] != turn
            or event["turnRevision"] != revision
            or run is None
            or run["workRefHash"] != event["workRefHash"]
            or event["previousSha256"] != previous
        ):
            raise ValueError(message)
        unsigned = {key: value for key, value in event.items() if key != "eventSha256"}
        if _hash(event["eventSha256"], message=message) != _canonical_hash(unsigned):
            raise ValueError(message)
        previous = str(event["eventSha256"])
        coverage[str(event["workRefHash"])].add(str(event["eventType"]))
    if payload["chainSha256"] != previous:
        raise ValueError(message)
    required = {
        "source.observed",
        "work.admitted",
        "runtime.invoked",
        "provider.request.forwarded",
        "callback.accepted",
        "delivery.sent",
    }
    if any(not required <= observed for observed in coverage.values()):
        raise ValueError(message)


def _restart_proof(
    evidence: list[dict[str, object]],
    *,
    candidate_digest: str,
    owner: str,
    revision: int,
    runtime: dict[str, object],
) -> None:
    acknowledgements = _entries(evidence, "restart_receipt")
    if acknowledgements:
        services: set[str] = set()
        processes: set[str] = set()
        for entry in acknowledgements:
            payload = _object(
                _payload(entry, message="restart acknowledgements are invalid"),
                {
                    "service",
                    "processRefHash",
                    "processStartedAt",
                    "acknowledgementSha256",
                    "candidateDigest",
                },
                message="restart acknowledgements are invalid",
            )
            process = _hash(
                payload["processRefHash"],
                message="restart acknowledgements are invalid",
            )
            _hash(
                payload["acknowledgementSha256"],
                message="restart acknowledgements are invalid",
            )
            _timestamp(
                payload["processStartedAt"],
                message="restart acknowledgements are invalid",
            )
            if (
                payload["candidateDigest"] != candidate_digest
                or payload["service"] in services
                or process in processes
            ):
                raise ValueError(
                    "restart acknowledgements are missing, duplicated, or stale"
                )
            services.add(str(payload["service"]))
            processes.add(process)
        if services != {"librechat-core", "telegram-bot", "glasshive-runtime"}:
            raise ValueError(
                "restart acknowledgements do not cover every required service"
            )

    exports = _entries(evidence, "database_export")
    if not exports:
        return
    snapshots: dict[str, dict[str, object]] = {}
    for entry in exports:
        payload = _object(
            _payload(entry, message="restart continuity is invalid"),
            {"phase", "works", "actions"},
            message="restart continuity is invalid",
        )
        phase = payload["phase"]
        if phase not in {"pre_restart", "post_restart"} or phase in snapshots:
            raise ValueError("restart continuity snapshots are missing or duplicated")
        works = _list(
            payload["works"], message="restart continuity work is invalid", minimum=2
        )
        normalized: dict[str, dict[str, object]] = {}
        for raw in works:
            row = _object(
                raw,
                {
                    "ownerRefHash",
                    "workRefHash",
                    "runRefHash",
                    "workerRefHash",
                    "workspaceRefHash",
                    "turnRevision",
                },
                message="restart continuity work is invalid",
            )
            run = runtime["runs"].get(row["runRefHash"])
            if (
                run is None
                or row["ownerRefHash"] != owner
                or row["turnRevision"] != revision
                or any(
                    row[field] != run[field]
                    for field in ("workRefHash", "workerRefHash", "workspaceRefHash")
                )
                or row["workRefHash"] in normalized
            ):
                raise ValueError(
                    "restart continuity replaced or crossed mission identity"
                )
            normalized[str(row["workRefHash"])] = row
        actions = _list(
            payload["actions"], message="restart continuity steering is invalid"
        )
        if len(actions) != 1 or actions[0] != runtime["steer"]:
            raise ValueError(
                "restart continuity lost or duplicated exact A-only steering"
            )
        snapshots[str(phase)] = {"works": normalized, "actions": actions}
    if (
        set(snapshots) != {"pre_restart", "post_restart"}
        or snapshots["pre_restart"] != snapshots["post_restart"]
    ):
        raise ValueError(
            "restart continuity changed exact work, run, worker, or action identity"
        )


def _fault_proof(
    evidence: list[dict[str, object]],
    *,
    case_id: str,
    owner: str,
    runtime: dict[str, object],
) -> None:
    required = FAULT_BOUNDARIES.get(case_id)
    if required is None:
        return
    boundaries: set[str] = set()
    controls: set[str] = set()
    sessions: set[str] = set()
    for entry in _entries(evidence, "fault_receipt"):
        payload = _object(
            _payload(entry, message="fault boundary receipt is invalid"),
            {
                "boundary",
                "controlRefHash",
                "sessionRefHash",
                "ownerRefHash",
                "workRefHash",
                "runRefHash",
                "consumedAt",
                "effectCount",
            },
            message="fault boundary receipt is invalid",
        )
        boundary = payload["boundary"]
        control = _hash(
            payload["controlRefHash"], message="fault boundary receipt is invalid"
        )
        session = _hash(
            payload["sessionRefHash"], message="fault boundary receipt is invalid"
        )
        run = runtime["runs"].get(payload["runRefHash"])
        if (
            boundary not in required
            or boundary in boundaries
            or control in controls
            or payload["ownerRefHash"] != owner
            or run is None
            or run["workRefHash"] != payload["workRefHash"]
            or entry["workRefHash"] != payload["workRefHash"]
            or entry["runRefHash"] != payload["runRefHash"]
            or _positive_int(
                payload["effectCount"], message="fault boundary receipt is invalid"
            )
            != 1
        ):
            raise ValueError(
                "fault boundary receipt is missing, duplicated, or cross-related"
            )
        _timestamp(payload["consumedAt"], message="fault boundary receipt is invalid")
        boundaries.add(str(boundary))
        controls.add(control)
        sessions.add(session)
    if boundaries != required or len(sessions) != 1:
        raise ValueError(
            "fault boundary coverage does not match the exact installed case"
        )


def _capacity_proof(
    evidence: list[dict[str, object]], *, runtime: dict[str, object]
) -> None:
    ledgers = _entries(evidence, "capacity_ledger")
    if not ledgers:
        return
    payload = _object(
        _payload(ledgers[0], message="capacity measurement is invalid"),
        {"measurement", "reservationAttempts", "overflow", "disk"},
        message="capacity measurement is invalid",
    )
    measurement = _object(
        payload["measurement"],
        {"availableBytes", "requiredBytes", "shortageBytes", "nextRetryAt"},
        message="capacity measurement is invalid",
    )
    available = _nonnegative_int(
        measurement["availableBytes"], message="capacity measurement is invalid"
    )
    required = _positive_int(
        measurement["requiredBytes"], message="capacity measurement is invalid"
    )
    shortage = _positive_int(
        measurement["shortageBytes"], message="capacity measurement is invalid"
    )
    if available >= required or required - available != shortage:
        raise ValueError(
            "capacity measurement does not report its exact available and required bytes"
        )
    _timestamp(
        measurement["nextRetryAt"], message="capacity measurement retry time is invalid"
    )
    attempts = _list(
        payload["reservationAttempts"],
        message="capacity reservation race is invalid",
        minimum=2,
    )
    if len(attempts) != 2:
        raise ValueError(
            "capacity reservation race did not exercise exactly two submissions"
        )
    winners: list[dict[str, object]] = []
    losers: list[dict[str, object]] = []
    slots: set[str] = set()
    requests: set[str] = set()
    for raw in attempts:
        attempt = _object(
            raw,
            {"requestRefHash", "slotRefHash", "outcome", "workRefHash"},
            message="capacity reservation race is invalid",
        )
        request = _hash(
            attempt["requestRefHash"], message="capacity reservation race is invalid"
        )
        slot = _hash(
            attempt["slotRefHash"], message="capacity reservation race is invalid"
        )
        if request in requests:
            raise ValueError("capacity reservation race duplicated a request")
        requests.add(request)
        slots.add(slot)
        if attempt["outcome"] == "reserved":
            if attempt["workRefHash"] not in runtime["works"]:
                raise ValueError("capacity reservation created unrelated work")
            winners.append(attempt)
        elif attempt["outcome"] == "rejected" and attempt["workRefHash"] is None:
            losers.append(attempt)
        else:
            raise ValueError("capacity reservation race reported an invalid acceptance")
    if len(winners) != 1 or len(losers) != 1 or len(slots) != 1:
        raise ValueError(
            "capacity reservation race admitted more than one exact request"
        )
    overflow = _object(
        payload["overflow"],
        {"decision", "workRows", "runRows"},
        message="capacity overflow evidence is invalid",
    )
    if (
        overflow["decision"] != "rejected"
        or _nonnegative_int(
            overflow["workRows"], message="capacity overflow evidence is invalid"
        )
        != 0
        or _nonnegative_int(
            overflow["runRows"], message="capacity overflow evidence is invalid"
        )
        != 0
    ):
        raise ValueError("capacity overflow created or falsely accepted mission rows")
    disk = _object(
        payload["disk"],
        {"state", "availableBytes", "requiredBytes"},
        message="capacity disk-pressure evidence is invalid",
    )
    if (
        disk["state"] != "critical"
        or disk["availableBytes"] != available
        or disk["requiredBytes"] != required
    ):
        raise ValueError("capacity disk-pressure evidence is inconsistent")

    providers = _entries(evidence, "provider_health_ledger")
    if len(providers) != 1:
        raise ValueError("provider cooldown and fallback evidence is missing")
    health = _object(
        _payload(
            providers[0], message="provider cooldown and fallback evidence is invalid"
        ),
        {"events"},
        message="provider cooldown and fallback evidence is invalid",
    )
    indexed: dict[str, dict[str, object]] = {}
    for raw in _list(
        health["events"], message="provider cooldown and fallback evidence is invalid"
    ):
        if not isinstance(raw, dict) or raw.get("condition") in indexed:
            raise ValueError("provider cooldown and fallback evidence is invalid")
        condition = str(raw.get("condition") or "")
        expected = {"condition", "outcome", "attempted"}
        if condition == "quota_cooldown":
            expected.add("retryAfter")
        event = _object(
            raw, expected, message="provider cooldown and fallback evidence is invalid"
        )
        if not isinstance(event["attempted"], bool):
            _invalid("provider cooldown and fallback evidence is invalid")
        indexed[condition] = event
    expected_events = {
        "auth_missing": ("needs_input", False),
        "quota_cooldown": ("skipped", False),
        "fallback": ("completed", True),
        "unavailable": ("unavailable", False),
    }
    if set(indexed) != set(expected_events):
        raise ValueError("provider cooldown and fallback classes are missing")
    for condition, (outcome, attempted) in expected_events.items():
        event = indexed[condition]
        if event["outcome"] != outcome or event["attempted"] is not attempted:
            raise ValueError("provider cooldown and fallback behavior is not truthful")
    _timestamp(
        indexed["quota_cooldown"]["retryAfter"],
        message="provider cooldown retry time is invalid",
    )


def _security_proof(
    evidence: list[dict[str, object]],
    *,
    owner: str,
    runtime: dict[str, object],
    artifacts: dict[str, dict[str, object]],
) -> None:
    matrices = _entries(evidence, "auth_matrix")
    if not matrices:
        return
    matrix = _object(
        _payload(matrices[0], message="owner authorization matrix is invalid"),
        {"ownerRefHash", "otherOwnerRefHash", "operations"},
        message="owner authorization matrix is invalid",
    )
    other = _hash(
        matrix["otherOwnerRefHash"], message="owner authorization matrix is invalid"
    )
    if matrix["ownerRefHash"] != owner or other == owner:
        raise ValueError("owner authorization does not prove two independent accounts")
    denied: dict[tuple[str, str], set[str]] = {
        (other, owner): set(),
        (owner, other): set(),
    }
    allowed = 0
    for raw in _list(
        matrix["operations"], message="owner authorization matrix is invalid"
    ):
        operation = _object(
            raw,
            {
                "actorOwnerRefHash",
                "targetOwnerRefHash",
                "operation",
                "outcome",
                "returnedWorkRefHashes",
            },
            message="owner authorization matrix is invalid",
        )
        actor = _hash(
            operation["actorOwnerRefHash"],
            message="owner authorization matrix is invalid",
        )
        target = _hash(
            operation["targetOwnerRefHash"],
            message="owner authorization matrix is invalid",
        )
        returned = operation["returnedWorkRefHashes"]
        if not isinstance(returned, list):
            _invalid("owner authorization returned invalid work evidence")
        if actor == target == owner:
            if (
                operation["outcome"] != "allowed"
                or not returned
                or not set(returned) <= set(runtime["works"])
            ):
                raise ValueError(
                    "owner authorization rejected or leaked legitimate owner work"
                )
            allowed += 1
        elif (actor, target) in denied:
            if operation["outcome"] != "denied" or returned:
                raise ValueError(
                    "owner authorization permitted a cross-owner operation"
                )
            denied[(actor, target)].add(str(operation["operation"]))
        else:
            raise ValueError("owner authorization matrix contains an unbound owner")
    required_operations = {"list", "inspect", "control", "callback"}
    if allowed == 0 or any(
        not required_operations <= operations for operations in denied.values()
    ):
        raise ValueError(
            "owner authorization matrix omits bidirectional denied operations"
        )

    attacks: set[str] = set()
    requests: set[str] = set()
    for entry in _entries(evidence, "rejection_ledger"):
        payload = _object(
            _payload(entry, message="security rejection evidence is invalid"),
            {"attack", "requestRefHash", "ownerRefHash", "outcome", "effectsCreated"},
            message="security rejection evidence is invalid",
        )
        request = _hash(
            payload["requestRefHash"], message="security rejection evidence is invalid"
        )
        if (
            payload["ownerRefHash"] != owner
            or payload["outcome"] != "denied"
            or _nonnegative_int(
                payload["effectsCreated"],
                message="security rejection evidence is invalid",
            )
            != 0
            or request in requests
            or payload["attack"] in attacks
        ):
            raise ValueError("security rejection created an effect or reused an attack")
        requests.add(request)
        attacks.add(str(payload["attack"]))
    if attacks != {"forged_callback", "cross_owner_callback", "altered_trace"}:
        raise ValueError(
            "security rejection evidence does not cover every hostile boundary"
        )

    safety = _object(
        _payload(
            _entries(evidence, "safety_scan")[0],
            message="public safety scan is invalid",
        ),
        {
            "scannedArtifactSha256",
            "findingCount",
            "privateLeakCount",
            "hostAuthorityExecutionCount",
        },
        message="public safety scan is invalid",
    )
    artifact_digests = {str(item["byteSha256"]) for item in artifacts.values()}
    if safety["scannedArtifactSha256"] not in artifact_digests or any(
        _nonnegative_int(safety[field], message="public safety scan is invalid") != 0
        for field in ("findingCount", "privateLeakCount", "hostAuthorityExecutionCount")
    ):
        raise ValueError("public safety scan found an unsafe or unrelated artifact")


def _voice_proof(
    evidence: list[dict[str, object]],
    *,
    owner: str,
    turn: str,
    revision: int,
    runtime: dict[str, object],
) -> None:
    transcripts = _entries(evidence, "voice_transcript")
    if not transcripts:
        return
    recordings = _entries(evidence, "voice_recording")
    if len(recordings) != 1:
        raise ValueError("voice transcript is missing audible call evidence")
    transcript = _object(
        _payload(transcripts[0], message="voice transcript is invalid"),
        {"recordingSha256", "mode", "segments"},
        message="voice transcript is invalid",
    )
    if (
        transcript["recordingSha256"] != recordings[0]["sha256"]
        or transcript["mode"] != "call"
    ):
        raise ValueError("voice transcript does not match the audible normal call")
    segments = _list(transcript["segments"], message="voice transcript is invalid")
    launches: set[str] = set()
    completions: set[str] = set()
    quick = steer = hangup = reconnect = 0
    action_positions: dict[str, list[int]] = {
        "launch": [],
        "quick_answer": [],
        "steer": [],
        "hangup": [],
        "reconnect": [],
        "completion": [],
    }
    utterances: set[str] = set()
    for position, raw in enumerate(segments, start=1):
        segment = _object(
            raw,
            {
                "sequence",
                "speaker",
                "action",
                "ownerRefHash",
                "logicalTurnRefHash",
                "turnRevision",
                "utteranceRefHash",
                "workRefHash",
            },
            message="voice transcript is invalid",
        )
        utterance = _hash(
            segment["utteranceRefHash"], message="voice transcript is invalid"
        )
        if (
            _positive_int(segment["sequence"], message="voice transcript is invalid")
            != position
            or segment["speaker"] not in {"user", "main"}
            or segment["ownerRefHash"] != owner
            or segment["logicalTurnRefHash"] != turn
            or segment["turnRevision"] != revision
            or utterance in utterances
        ):
            raise ValueError(
                "voice transcript is duplicated, cross-owned, or worker-authored"
            )
        utterances.add(utterance)
        action = segment["action"]
        work_ref = segment["workRefHash"]
        if (
            action == "launch"
            and segment["speaker"] == "user"
            and work_ref in runtime["works"]
        ):
            if work_ref in launches:
                raise ValueError("voice transcript duplicated a worker launch")
            launches.add(str(work_ref))
        elif (
            action == "completion"
            and segment["speaker"] == "main"
            and work_ref in runtime["works"]
        ):
            if work_ref in completions:
                raise ValueError("voice transcript duplicated a worker completion")
            completions.add(str(work_ref))
        elif (
            action == "quick_answer"
            and segment["speaker"] == "main"
            and work_ref is None
        ):
            quick += 1
        elif (
            action == "steer"
            and segment["speaker"] == "user"
            and work_ref == runtime["steer"]["workRefHash"]
        ):
            steer += 1
        elif action == "hangup" and segment["speaker"] == "user" and work_ref is None:
            hangup += 1
        elif (
            action == "reconnect" and segment["speaker"] == "user" and work_ref is None
        ):
            reconnect += 1
        else:
            raise ValueError(
                "voice transcript contains an unauthorized or unrelated action"
            )
        action_positions[str(action)].append(position)
    if (
        launches != set(runtime["works"])
        or completions != set(runtime["works"])
        or (quick, steer, hangup, reconnect) != (1, 1, 1, 1)
    ):
        raise ValueError(
            "voice transcript does not prove exact launch, quick reply, steer, and recovery"
        )
    if not (
        max(action_positions["launch"])
        < action_positions["quick_answer"][0]
        < action_positions["steer"][0]
        < action_positions["hangup"][0]
        < action_positions["reconnect"][0]
        < min(action_positions["completion"])
    ):
        raise ValueError(
            "voice transcript does not preserve launch, hangup, and reconnect order"
        )

    attachment_entries = _entries(evidence, "attachment_hash")
    if len(attachment_entries) != 1:
        raise ValueError("attachment bytes or order are missing")
    attachments = _object(
        _payload(
            attachment_entries[0], message="attachment bytes or order are invalid"
        ),
        {"groupRefHash", "ownerRefHash", "workRefHash", "runRefHash", "inputs"},
        message="attachment bytes or order are invalid",
    )
    _hash(attachments["groupRefHash"], message="attachment bytes or order are invalid")
    run = runtime["runs"].get(attachments["runRefHash"])
    if (
        attachments["ownerRefHash"] != owner
        or run is None
        or run["workRefHash"] != attachments["workRefHash"]
    ):
        raise ValueError("attachment bytes or order crossed mission ownership")
    indexed_bytes = {
        str(item["id"]): item for item in _entries(evidence, "attachment_bytes")
    }
    inputs = _list(
        attachments["inputs"],
        message="attachment bytes or order are invalid",
        minimum=2,
    )
    if len(inputs) != len(indexed_bytes):
        raise ValueError("attachment bytes or order are missing or duplicated")
    seen_files: set[str] = set()
    seen_evidence: set[str] = set()
    for position, raw in enumerate(inputs):
        item = _object(
            raw,
            {"position", "fileRefHash", "evidenceId", "byteSha256", "sizeBytes"},
            message="attachment bytes or order are invalid",
        )
        file_ref = _hash(
            item["fileRefHash"], message="attachment bytes or order are invalid"
        )
        content = indexed_bytes.get(str(item["evidenceId"]))
        if (
            _nonnegative_int(
                item["position"], message="attachment bytes or order are invalid"
            )
            != position
            or file_ref in seen_files
            or item["evidenceId"] in seen_evidence
            or content is None
            or content["workRefHash"] != attachments["workRefHash"]
            or content["runRefHash"] != attachments["runRefHash"]
            or item["byteSha256"] != content["sha256"]
            or _positive_int(
                item["sizeBytes"], message="attachment bytes or order are invalid"
            )
            != content["sizeBytes"]
        ):
            raise ValueError("attachment bytes or order do not match the exact mission")
        seen_files.add(file_ref)
        seen_evidence.add(str(item["evidenceId"]))

    capabilities: set[str] = set()
    for entry in _entries(evidence, "capability_ledger"):
        capability = _object(
            _payload(entry, message="worker capability proof is invalid"),
            {
                "capabilityKind",
                "ownerRefHash",
                "workRefHash",
                "runRefHash",
                "requestRefHash",
                "responseRefHash",
                "scopeRefHash",
                "outcome",
                "permission",
                "effects",
            },
            message="worker capability proof is invalid",
        )
        if (
            capability["ownerRefHash"] != owner
            or capability["workRefHash"] != attachments["workRefHash"]
            or capability["runRefHash"] != attachments["runRefHash"]
            or capability["outcome"] != "granted"
            or capability["capabilityKind"] in capabilities
        ):
            raise ValueError(
                "worker capability is missing, unavailable, duplicated, or cross-owned"
            )
        for field in ("requestRefHash", "responseRefHash", "scopeRefHash"):
            _hash(capability[field], message="worker capability proof is invalid")
        if capability["capabilityKind"] == "connected_account":
            if capability["permission"] != "read" or capability["effects"] != "read_only":
                raise ValueError("connected account permission exceeded owner-scoped read access")
        elif capability["permission"] is not None or capability["effects"] is not None:
            raise ValueError("worker capability proof contains undeclared permission effects")
        capabilities.add(str(capability["capabilityKind"]))
    if capabilities != {
        "saved_memory",
        "conversation_recall",
        "broker_tool",
        "browser",
        "computer",
        "connected_account",
    }:
        raise ValueError(
            "worker capability does not preserve memory, tools, browser, Computer, and connected-account parity"
        )

    denied: set[str] = set()
    for entry in _entries(evidence, "denial_receipt"):
        denial = _object(
            _payload(entry, message="passive surface denial is invalid"),
            {"mode", "ownerRefHash", "attemptedAction", "decision", "workRowsCreated"},
            message="passive surface denial is invalid",
        )
        if (
            denial["ownerRefHash"] != owner
            or denial["attemptedAction"] != "launch"
            or denial["decision"] != "denied"
            or _nonnegative_int(
                denial["workRowsCreated"], message="passive surface denial is invalid"
            )
            != 0
            or denial["mode"] in denied
        ):
            raise ValueError(
                "passive surface denial created or exposed unauthorized work"
            )
        denied.add(str(denial["mode"]))
    if denied != {"passive_wing", "listen_only"}:
        raise ValueError("passive surface denial does not cover Wing and Listen-Only")


def _cleanup_proof(
    evidence: list[dict[str, object]], *, case_id: str, owner: str, now: datetime
) -> None:
    entries = _entries(evidence, "cleanup_receipt")
    if case_id != "PWK-UC-019":
        if entries:
            raise ValueError("cleanup receipt is not valid for this journey")
        return
    if len(entries) != 1:
        raise ValueError("complete synthetic cleanup receipt is unavailable")
    payload = _object(
        _payload(entries[0], message="synthetic cleanup receipt is invalid"),
        {"ownerRefHash", "zeroResidue", "completedAt"},
        message="synthetic cleanup receipt is invalid",
    )
    completed = _timestamp(
        payload["completedAt"], message="synthetic cleanup receipt is invalid"
    )
    if (
        payload["ownerRefHash"] != owner
        or payload["zeroResidue"] is not True
        or completed > now + MAX_FUTURE_SKEW
    ):
        raise ValueError("synthetic cleanup did not prove zero residue")


def _semantic_proof(
    evidence: list[dict[str, object]],
    *,
    case_id: str,
    candidate_digest: str,
    artifact_digest: str,
    correlation: dict[str, object],
    now: datetime,
) -> None:
    owner = str(correlation["ownerRefHash"])
    origin = str(correlation["surface"])
    turn = str(correlation["logicalTurnRefHash"])
    revision = int(correlation["turnRevision"])
    _installed_identity_proof(
        evidence,
        candidate_digest=candidate_digest,
        artifact_digest=artifact_digest,
        owner=owner,
        origin=origin,
    )
    runtime = _runtime_rows_proof(
        evidence,
        owner=owner,
        origin=origin,
        turn=turn,
        revision=revision,
        case_id=case_id,
        now=now,
    )
    _worker_isolation_proof(evidence, owner=owner, runtime=runtime)
    _delivery_proof(evidence, owner=owner, origin=origin, runtime=runtime)
    _native_receipt_proof(
        evidence,
        owner=owner,
        origin=origin,
        turn=turn,
        revision=revision,
        runtime=runtime,
        case_id=case_id,
        now=now,
    )
    _telegram_turn_proof(
        evidence, owner=owner, turn=turn, revision=revision, runtime=runtime
    )
    artifacts = _artifact_proof(evidence, owner=owner, runtime=runtime)
    _surface_capture_proof(evidence, owner=owner, case_id=case_id, artifacts=artifacts)
    _trace_proof(
        evidence,
        owner=owner,
        origin=origin,
        turn=turn,
        revision=revision,
        runtime=runtime,
    )
    _restart_proof(
        evidence,
        candidate_digest=candidate_digest,
        owner=owner,
        revision=revision,
        runtime=runtime,
    )
    _fault_proof(evidence, case_id=case_id, owner=owner, runtime=runtime)
    _capacity_proof(evidence, runtime=runtime)
    _security_proof(evidence, owner=owner, runtime=runtime, artifacts=artifacts)
    _voice_proof(evidence, owner=owner, turn=turn, revision=revision, runtime=runtime)
    _cleanup_proof(evidence, case_id=case_id, owner=owner, now=now)


_DERIVED_PASS = object()
_DERIVED_SECRET = os.urandom(32)


def _derived_seal(result: dict[str, object]) -> str:
    protected = {
        key: value
        for key, value in result.items()
        if key not in {"_derivedPass", "_derivedSeal"}
    }
    message = json.dumps(protected, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hmac.new(_DERIVED_SECRET, message, hashlib.sha256).hexdigest()


def _private_evidence_root(evidence_root: Path) -> Path:
    supplied = evidence_root.expanduser()
    try:
        if supplied.is_symlink():
            raise ValueError("private journey evidence root is invalid")
        exact = supplied.resolve(strict=True)
        metadata = exact.lstat()
    except (OSError, RuntimeError) as exc:
        raise ValueError("private journey evidence is unavailable") from exc
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or metadata.st_mode & 0o077
    ):
        raise ValueError("private journey evidence root is not owner-only")
    return exact


def assess_manifest(
    manifest: object,
    *,
    evidence_root: Path,
    expected_candidate_digest: str,
    expected_artifact_digest: str,
    installed_owner_proven: bool,
    now: datetime | None = None,
) -> dict[str, object]:
    if installed_owner_proven is not True:
        raise ValueError("active installed-runtime owner identity is not proven")
    candidate_digest = _hash(
        expected_candidate_digest,
        message="installed candidate identity is unavailable",
    )
    artifact_digest = _hash(
        expected_artifact_digest,
        message="installed artifact identity is unavailable",
    )
    if not isinstance(manifest, dict) or set(manifest) != MANIFEST_FIELDS:
        raise ValueError("journey manifest shape is invalid")
    if manifest.get("contractVersion") != CONTRACT_VERSION:
        raise ValueError("journey manifest contract is unsupported")
    case_id = str(manifest.get("caseId") or "")
    if case_id not in CASE_CHECKS:
        raise ValueError("journey case is unsupported")
    if manifest.get("candidateDigest") != candidate_digest:
        raise ValueError("candidate identity does not match")
    if manifest.get("artifactDigest") != artifact_digest:
        raise ValueError("installed artifact identity does not match")
    correlation = _correlation(manifest.get("correlation"), case_id=case_id)
    checked_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    run_at = _parse_run_at(manifest.get("runAt"), now=checked_at)
    exact_root = _private_evidence_root(evidence_root)
    evidence, evidence_ids = _verified_evidence(
        manifest.get("evidence"),
        evidence_root=exact_root,
        case_id=case_id,
        correlation=correlation,
        candidate_digest=candidate_digest,
        artifact_digest=artifact_digest,
        run_at=_timestamp(run_at, message="journey timestamp is invalid"),
    )
    evidence_by_id = {str(item["id"]): item for item in evidence}
    checks = _verified_checks(
        manifest.get("checks"),
        case_id=case_id,
        evidence_ids=evidence_ids,
        evidence_by_id=evidence_by_id,
    )
    measured_kinds = Counter(str(item["kind"]) for item in evidence)
    for kind, minimum in CASE_EVIDENCE_MINIMUMS[case_id].items():
        if measured_kinds[kind] < minimum:
            raise ValueError("required real-surface evidence is missing")
    _semantic_proof(
        evidence,
        case_id=case_id,
        candidate_digest=candidate_digest,
        artifact_digest=artifact_digest,
        correlation=correlation,
        now=checked_at,
    )
    receipt_evidence = [
        {"kind": item["kind"], "path": item["path"], "sha256": item["sha256"]}
        for item in evidence
    ]
    result = {
        "artifactDigest": artifact_digest,
        "candidateDigest": candidate_digest,
        "caseId": case_id,
        "checkCount": len(checks),
        "evidenceCount": len(evidence),
        "evidenceDigest": _canonical_hash(
            {
                "artifactDigest": artifact_digest,
                "candidateDigest": candidate_digest,
                "caseId": case_id,
                "checks": checks,
                "correlation": correlation,
                "evidence": receipt_evidence,
            }
        ),
        "runAt": run_at,
        "status": "PASS",
        "_derivedPass": _DERIVED_PASS,
        "_receiptEvidence": receipt_evidence,
    }
    result["_derivedSeal"] = _derived_seal(result)
    return result


def _runtime_owner_proven(*, installed_root: Path, runtime_owner_state: Path) -> bool:
    gate = _load_release_gate()
    supplied_owner = runtime_owner_state.expanduser()
    try:
        exact_installed = installed_root.expanduser().resolve(strict=True)
        if supplied_owner.is_symlink() or not gate.validate_runtime_owner_state_file(
            supplied_owner
        ):
            return False
        owner = _strict_json(
            supplied_owner,
            max_bytes=MAX_IDENTITY_BYTES,
            label="installed runtime owner identity",
            private=True,
        )
        if not isinstance(owner, dict):
            return False
        return (
            Path(str(owner.get("repoRoot") or "")).expanduser().resolve(strict=True)
            == exact_installed
        )
    except (OSError, RuntimeError, ValueError):
        return False


def evaluate_journey(
    *,
    manifest_path: Path,
    evidence_root: Path,
    artifact_identity_path: Path,
    installed_owner_proven: bool = False,
    now: datetime | None = None,
) -> dict[str, object]:
    try:
        supplied_manifest = manifest_path.expanduser()
        if supplied_manifest.is_symlink():
            raise ValueError("journey manifest must stay inside the evidence root")
        exact_root = evidence_root.expanduser().resolve(strict=True)
        exact_manifest = supplied_manifest.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ValueError("private journey evidence is unavailable") from exc
    if not exact_root.is_dir() or not _inside(exact_manifest, exact_root):
        raise ValueError("journey manifest must stay inside the evidence root")
    manifest = _strict_json(
        exact_manifest,
        max_bytes=MAX_MANIFEST_BYTES,
        label="journey manifest",
        private=True,
    )
    identity = _strict_json(
        artifact_identity_path.expanduser(),
        max_bytes=MAX_IDENTITY_BYTES,
        label="installed artifact identity",
    )
    candidate_digest, artifact_digest = _load_release_gate()._qa_candidate_digests(
        identity
    )
    if not candidate_digest or not artifact_digest:
        raise ValueError("installed candidate identity is unavailable")
    return assess_manifest(
        manifest,
        evidence_root=exact_root,
        expected_candidate_digest=candidate_digest,
        expected_artifact_digest=artifact_digest,
        installed_owner_proven=installed_owner_proven,
        now=now,
    )


def receipt_manifest(*, result: dict[str, object]) -> dict[str, object]:
    if (
        not isinstance(result, dict)
        or result.get("_derivedPass") is not _DERIVED_PASS
        or result.get("status") != "PASS"
        or result.get("caseId") not in CASE_SURFACES
        or not isinstance(result.get("_derivedSeal"), str)
        or not hmac.compare_digest(str(result["_derivedSeal"]), _derived_seal(result))
    ):
        raise ValueError(
            "only a passing installed journey can create a receipt manifest"
        )
    evidence = result.get("_receiptEvidence")
    if not isinstance(evidence, list) or not evidence:
        raise ValueError("passing journey evidence is unavailable")
    return {
        "caseId": result["caseId"],
        "contractVersion": CONTRACT_VERSION,
        "evidence": evidence,
        "runAt": result["runAt"],
        "status": "PASS",
        "surface": CASE_SURFACES[str(result["caseId"])],
    }


def _public_result(result: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in result.items() if not key.startswith("_")}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--case-id", choices=sorted(CASE_CHECKS))
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--artifact-identity", type=Path, required=True)
    parser.add_argument("--installed-root", type=Path, required=True)
    parser.add_argument("--runtime-owner-state", type=Path, required=True)
    parser.add_argument("--receipt-manifest", type=Path)
    args = parser.parse_args(argv)
    try:
        if not _runtime_owner_proven(
            installed_root=args.installed_root,
            runtime_owner_state=args.runtime_owner_state,
        ):
            raise ValueError("active installed-runtime owner identity is not proven")
        result = evaluate_journey(
            manifest_path=args.manifest,
            evidence_root=args.evidence_root,
            artifact_identity_path=args.artifact_identity,
            installed_owner_proven=True,
        )
        if args.case_id and result["caseId"] != args.case_id:
            raise ValueError("journey case does not match the requested case")
        if args.receipt_manifest:
            exact_root = args.evidence_root.expanduser().resolve(strict=True)
            target = args.receipt_manifest.expanduser()
            if target.is_absolute():
                exact_target = target.resolve(strict=False)
            else:
                exact_target = (exact_root / target).resolve(strict=False)
            if not _inside(exact_target, exact_root):
                raise ValueError("receipt manifest must stay inside the evidence root")
            exact_manifest = args.manifest.expanduser().resolve(strict=True)
            if not _inside(exact_manifest, exact_root):
                raise ValueError(
                    "semantic verifier manifest must stay inside the evidence root"
                )
            payload = receipt_manifest(result=result)
            payload["verifier"] = {
                "id": VERIFIER_ID,
                "manifest": exact_manifest.relative_to(exact_root).as_posix(),
            }
            exact_target.parent.mkdir(parents=True, exist_ok=True)
            temporary = exact_target.with_name(
                f".{exact_target.name}.{os.getpid()}.tmp"
            )
            descriptor = os.open(
                temporary,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                    descriptor = -1
                    stream.write(json.dumps(payload, sort_keys=True) + "\n")
                    stream.flush()
                    os.fsync(stream.fileno())
            finally:
                if descriptor >= 0:
                    os.close(descriptor)
            os.replace(temporary, exact_target)
        print(json.dumps(_public_result(result), sort_keys=True))
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print(
            json.dumps(
                {
                    "caseId": args.case_id or "unknown",
                    "reason": str(exc),
                    "status": "BLOCKED",
                },
                sort_keys=True,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

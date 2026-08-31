#!/usr/bin/env python3
"""Validate installed TGDOC-010 evidence and derive a recorder manifest on PASS."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import stat
import struct
import sys
import zlib
from collections import Counter
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType

CONTRACT_VERSION = 1
CASE_ID = "TGDOC-010"
EXIT_PASS = 0
EXIT_PARTIAL = 3
EXIT_NOT_RUN = 4
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_EVIDENCE_FILES = 64
MAX_EVIDENCE_BYTES = 100 * 1024 * 1024
MAX_CAPTURE_PIXELS = 25_000_000
MAX_EVIDENCE_WINDOW = timedelta(hours=12)
MAX_RESULT_AGE = timedelta(hours=24)
MAX_FUTURE_SKEW = timedelta(minutes=5)
HASH = re.compile(r"^[a-f0-9]{64}$")
SAFE_EVIDENCE_ID = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
SAFE_PATH_PART = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
SAFE_VISIBLE_IDENTITY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SEMANTIC_SCHEMA = "tgd010.semantic-evidence.v1"

REQUIRED_GATES = (
    "candidate_binding",
    "installed_telegram",
    "worker_materialization",
    "linked_active_work",
    "input_hashes_order",
    "output_hash_open",
    "provider_fallback",
    "worker_control",
    "restart_recovery",
    "owner_isolation",
    "negative_failures",
    "single_delivery",
)
REQUIRED_INPUT_FAMILIES = {
    "document",
    "image",
    "audio",
    "video",
    "prior_artifact",
}
EVIDENCE_KINDS = {
    "active_work_ui_semantics",
    "active_work_ui",
    "artifact_ledger",
    "artifact_open_ui",
    "control_receipt",
    "delivery_ledger",
    "failure_matrix",
    "isolation_trace",
    "opened_artifact",
    "provider_attempts",
    "restart_trace",
    "telegram_input",
    "telegram_ui",
    "telegram_ui_semantics",
    "telegram_upload_ledger",
    "worker_input",
    "worker_materialization",
}
PNG_EVIDENCE_KINDS = {"active_work_ui", "artifact_open_ui", "telegram_ui"}
BINARY_EVIDENCE_KINDS = {"opened_artifact", "telegram_input", "worker_input"}
SEMANTIC_EVIDENCE_KINDS = EVIDENCE_KINDS - PNG_EVIDENCE_KINDS - BINARY_EVIDENCE_KINDS
TOP_LEVEL_FIELDS = {
    "candidate",
    "caseId",
    "contractVersion",
    "correlation",
    "delivery",
    "environment",
    "evidence",
    "failures",
    "fixture",
    "inputs",
    "isolation",
    "output",
    "resilience",
    "runAt",
    "surfaces",
    "worker",
}
EVIDENCE_FIELDS = {
    "artifactDigest",
    "candidateDigest",
    "evidenceId",
    "journeyRefHash",
    "kind",
    "observedAt",
    "ownerRefHash",
    "path",
    "runRefHash",
    "sha256",
    "workRefHash",
}
SEMANTIC_EVIDENCE_FIELDS = {
    "artifactDigest",
    "candidateDigest",
    "contractVersion",
    "journeyRefHash",
    "kind",
    "observedAt",
    "ownerRefHash",
    "payload",
    "runRefHash",
    "schema",
    "workRefHash",
}
INPUT_FIELDS = {
    "byteSha256",
    "captionSha256",
    "family",
    "fileRefHash",
    "groupRefHash",
    "nameSha256",
    "ownerRefHash",
    "position",
    "sizeBytes",
    "telegramEvidenceId",
    "visibleIdentity",
    "workerEvidenceId",
}


class EvidenceContractError(ValueError):
    """The supplied material cannot count as TGDOC-010 evidence."""


_DERIVED_PASS = object()


def _invalid() -> None:
    raise EvidenceContractError("evidence_contract_invalid")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            _invalid()
        result[key] = value
    return result


def loads_strict_json(raw: bytes | str) -> object:
    try:
        encoded = raw.encode("utf-8") if isinstance(raw, str) else raw
        if not encoded or len(encoded) > MAX_MANIFEST_BYTES:
            _invalid()
        text = encoded.decode("utf-8")
        return json.loads(text, object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        if isinstance(exc, EvidenceContractError):
            raise
        raise EvidenceContractError("evidence_contract_invalid") from None


def _object(value: object, fields: set[str]) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != fields:
        _invalid()
    return value


def _hash(value: object, *, allow_empty: bool = False) -> str:
    text = value if isinstance(value, str) else ""
    if allow_empty and text == "":
        return ""
    if HASH.fullmatch(text) is None:
        _invalid()
    return text


def _positive_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        _invalid()
    return value


def _nonnegative_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _invalid()
    return value


def _boolean(value: object) -> bool:
    if not isinstance(value, bool):
        _invalid()
    return value


def _evidence_id(value: object) -> str:
    if not isinstance(value, str) or SAFE_EVIDENCE_ID.fullmatch(value) is None:
        _invalid()
    return value


def _visible_identity(value: object) -> str:
    if not isinstance(value, str) or SAFE_VISIBLE_IDENTITY.fullmatch(value) is None:
        _invalid()
    return value


def _string_list(value: object) -> list[str]:
    if (
        not isinstance(value, list)
        or not value
        or not all(
            isinstance(item, str) and item.strip() == item and item for item in value
        )
        or len(value) != len(set(value))
    ):
        _invalid()
    return list(value)


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        _invalid()
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        _invalid()
    if parsed.tzinfo is None:
        _invalid()
    return parsed.astimezone(timezone.utc)


def _canonical_digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _private_directory(path: Path) -> Path:
    try:
        exact = path.expanduser().resolve(strict=True)
        metadata = exact.stat()
    except (OSError, RuntimeError):
        _invalid()
    if (
        not exact.is_dir()
        or path.expanduser().is_symlink()
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) & 0o077
    ):
        _invalid()
    return exact


def _inside(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _safe_relative_path(value: object) -> Path:
    if not isinstance(value, str) or not value or "\\" in value:
        _invalid()
    relative = Path(value)
    if (
        relative.is_absolute()
        or relative.as_posix() != value
        or any(part in {"", ".", ".."} for part in relative.parts)
        or any(SAFE_PATH_PART.fullmatch(part) is None for part in relative.parts)
    ):
        _invalid()
    return relative


def _read_private_file(path: Path, *, max_bytes: int) -> tuple[bytes, os.stat_result]:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = -1
    try:
        descriptor = os.open(path, flags)
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != os.getuid()
            or stat.S_IMODE(before.st_mode) & 0o077
            or before.st_nlink != 1
            or before.st_size <= 0
            or before.st_size > max_bytes
        ):
            _invalid()
        chunks: list[bytes] = []
        remaining = max_bytes + 1
        while remaining > 0:
            chunk = os.read(descriptor, min(64 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        after = os.fstat(descriptor)
        if (
            len(raw) != before.st_size
            or len(raw) > max_bytes
            or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
            != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
        ):
            _invalid()
        return raw, after
    except EvidenceContractError:
        raise
    except OSError:
        _invalid()
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    raise AssertionError("unreachable")


def _paeth_predictor(left: int, above: int, upper_left: int) -> int:
    estimate = left + above - upper_left
    left_distance = abs(estimate - left)
    above_distance = abs(estimate - above)
    upper_left_distance = abs(estimate - upper_left)
    if left_distance <= above_distance and left_distance <= upper_left_distance:
        return left
    if above_distance <= upper_left_distance:
        return above
    return upper_left


def _png_capture_facts(content: bytes) -> dict[str, int] | None:
    signature = b"\x89PNG\r\n\x1a\n"
    if len(content) < 57 or not content.startswith(signature):
        return None

    offset = len(signature)
    header: tuple[int, int, int, int, int, int, int] | None = None
    compressed = bytearray()
    saw_idat = False
    ended_idat = False
    saw_iend = False
    while offset < len(content):
        if offset + 12 > len(content):
            return None
        length = struct.unpack_from(">I", content, offset)[0]
        chunk_end = offset + 12 + length
        if chunk_end > len(content):
            return None
        kind = content[offset + 4 : offset + 8]
        payload = content[offset + 8 : offset + 8 + length]
        supplied_crc = struct.unpack_from(">I", content, offset + 8 + length)[0]
        if zlib.crc32(kind + payload) & 0xFFFFFFFF != supplied_crc:
            return None
        if header is None and kind != b"IHDR":
            return None
        if kind == b"IHDR":
            if header is not None or length != 13:
                return None
            header = struct.unpack(">IIBBBBB", payload)
        elif kind == b"IDAT":
            if header is None or ended_idat or saw_iend:
                return None
            saw_idat = True
            compressed.extend(payload)
        elif kind == b"IEND":
            if length != 0 or not saw_idat or saw_iend:
                return None
            saw_iend = True
            offset = chunk_end
            break
        elif kind == b"PLTE":
            if saw_idat or saw_iend:
                return None
        elif kind[0] & 0x20 == 0:
            return None
        elif saw_idat:
            ended_idat = True
        offset = chunk_end
    if header is None or not saw_iend or offset != len(content):
        return None

    width, height, bit_depth, color_type, compression, filtering, interlace = header
    channels_by_color_type = {0: 1, 2: 3, 4: 2, 6: 4}
    channels = channels_by_color_type.get(color_type)
    if (
        width < 640
        or height < 360
        or width > 32_768
        or height > 32_768
        or width * height > MAX_CAPTURE_PIXELS
        or bit_depth != 8
        or channels is None
        or compression != 0
        or filtering != 0
        or interlace != 0
    ):
        return None

    stride = width * channels
    expected_size = height * (stride + 1)
    try:
        inflater = zlib.decompressobj()
        decoded = inflater.decompress(bytes(compressed), expected_size + 1)
    except zlib.error:
        return None
    if (
        len(decoded) != expected_size
        or not inflater.eof
        or inflater.unused_data
        or inflater.unconsumed_tail
        or inflater.flush()
    ):
        return None

    previous = bytearray(stride)
    unique_pixels: set[bytes] = set()
    first_pixel: bytes | None = None
    different_pixels = 0
    minimum_channel = 255
    maximum_channel = 0
    cursor = 0
    color_channels = 1 if color_type in {0, 4} else 3
    for _row_number in range(height):
        filter_type = decoded[cursor]
        cursor += 1
        if filter_type > 4:
            return None
        encoded_row = decoded[cursor : cursor + stride]
        cursor += stride
        reconstructed = bytearray(stride)
        for index, encoded_byte in enumerate(encoded_row):
            left = reconstructed[index - channels] if index >= channels else 0
            above = previous[index]
            upper_left = previous[index - channels] if index >= channels else 0
            if filter_type == 0:
                value = encoded_byte
            elif filter_type == 1:
                value = encoded_byte + left
            elif filter_type == 2:
                value = encoded_byte + above
            elif filter_type == 3:
                value = encoded_byte + ((left + above) // 2)
            else:
                value = encoded_byte + _paeth_predictor(left, above, upper_left)
            reconstructed[index] = value & 0xFF
        previous = reconstructed
        for index in range(0, stride, channels):
            pixel = bytes(reconstructed[index : index + channels])
            if len(unique_pixels) < 256:
                unique_pixels.add(pixel)
            if first_pixel is None:
                first_pixel = pixel
            elif pixel != first_pixel:
                different_pixels += 1
            for channel in pixel[:color_channels]:
                minimum_channel = min(minimum_channel, channel)
                maximum_channel = max(maximum_channel, channel)

    minimum_different_pixels = max(256, (width * height) // 2_000)
    if (
        len(unique_pixels) < 8
        or different_pixels < minimum_different_pixels
        or maximum_channel - minimum_channel < 24
    ):
        return None
    return {
        "differentPixels": different_pixels,
        "height": height,
        "uniqueColors": len(unique_pixels),
        "width": width,
    }


def _valid_png_capture(content: bytes) -> bool:
    return _png_capture_facts(content) is not None


def _verify_evidence(
    value: object,
    *,
    evidence_root: Path,
    run_at: datetime,
    expected_candidate_digest: str,
    expected_artifact_digest: str,
    journey_ref: str,
    owner_ref: str,
    run_ref: str,
    work_ref: str,
) -> dict[str, dict[str, object]]:
    if not isinstance(value, list) or not value or len(value) > MAX_EVIDENCE_FILES:
        _invalid()
    exact_root = _private_directory(evidence_root)
    verified: dict[str, dict[str, object]] = {}
    seen_paths: set[str] = set()
    total_evidence_bytes = 0
    for raw_entry in value:
        entry = _object(raw_entry, EVIDENCE_FIELDS)
        evidence_id = entry.get("evidenceId")
        kind = entry.get("kind")
        if (
            not isinstance(evidence_id, str)
            or SAFE_EVIDENCE_ID.fullmatch(evidence_id) is None
            or evidence_id in verified
            or kind not in EVIDENCE_KINDS
        ):
            _invalid()
        if (
            _hash(entry.get("candidateDigest")) != expected_candidate_digest
            or _hash(entry.get("artifactDigest")) != expected_artifact_digest
            or _hash(entry.get("journeyRefHash")) != journey_ref
            or _hash(entry.get("ownerRefHash")) != owner_ref
            or _hash(entry.get("runRefHash")) != run_ref
            or _hash(entry.get("workRefHash")) != work_ref
        ):
            _invalid()
        observed_at = _timestamp(entry.get("observedAt"))
        if (
            observed_at > run_at + MAX_FUTURE_SKEW
            or run_at - observed_at > MAX_EVIDENCE_WINDOW
        ):
            _invalid()
        relative = _safe_relative_path(entry.get("path"))
        canonical_relative = relative.as_posix()
        if canonical_relative in seen_paths:
            _invalid()
        seen_paths.add(canonical_relative)
        supplied = exact_root / relative
        try:
            exact = supplied.resolve(strict=True)
        except (OSError, RuntimeError):
            _invalid()
        if not _inside(exact, exact_root) or supplied.is_symlink():
            _invalid()
        parent = supplied.parent
        while parent != exact_root:
            if parent.is_symlink():
                _invalid()
            parent = parent.parent
        content, metadata = _read_private_file(exact, max_bytes=MAX_EVIDENCE_BYTES)
        total_evidence_bytes += metadata.st_size
        if total_evidence_bytes > MAX_EVIDENCE_BYTES:
            _invalid()
        measured = hashlib.sha256(content).hexdigest()
        if measured != _hash(entry.get("sha256")):
            _invalid()
        image_facts: dict[str, int] | None = None
        semantic_payload: dict[str, object] | None = None
        if kind in PNG_EVIDENCE_KINDS:
            image_facts = _png_capture_facts(content)
            if relative.suffix.lower() != ".png" or image_facts is None:
                _invalid()
        elif kind in SEMANTIC_EVIDENCE_KINDS:
            if relative.suffix.lower() != ".json":
                _invalid()
            document = _object(loads_strict_json(content), SEMANTIC_EVIDENCE_FIELDS)
            document_observed_at = _timestamp(document.get("observedAt"))
            if (
                document.get("contractVersion") != CONTRACT_VERSION
                or document.get("schema") != SEMANTIC_SCHEMA
                or document.get("kind") != kind
                or _hash(document.get("candidateDigest")) != expected_candidate_digest
                or _hash(document.get("artifactDigest")) != expected_artifact_digest
                or _hash(document.get("journeyRefHash")) != journey_ref
                or _hash(document.get("ownerRefHash")) != owner_ref
                or _hash(document.get("runRefHash")) != run_ref
                or _hash(document.get("workRefHash")) != work_ref
                or document_observed_at != observed_at
                or not isinstance(document.get("payload"), dict)
            ):
                _invalid()
            semantic_payload = document["payload"]
        elif kind not in BINARY_EVIDENCE_KINDS:
            _invalid()
        verified_entry: dict[str, object] = {
            "kind": kind,
            "path": canonical_relative,
            "sha256": measured,
            "sizeBytes": metadata.st_size,
        }
        if image_facts is not None:
            verified_entry["imageFacts"] = image_facts
        if semantic_payload is not None:
            verified_entry["payload"] = semantic_payload
        verified[evidence_id] = verified_entry
    return verified


def _references(
    value: object,
    *,
    evidence: dict[str, dict[str, object]],
) -> tuple[list[str], set[str]]:
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) for item in value)
        or len(value) != len(set(value))
        or any(item not in evidence for item in value)
    ):
        _invalid()
    refs = list(value)
    return refs, {str(evidence[item]["kind"]) for item in refs}


def _has_kinds(actual: set[str], *required: str) -> bool:
    return set(required).issubset(actual)


def _semantic_entry(
    evidence: dict[str, dict[str, object]], kind: str
) -> tuple[str, dict[str, object]]:
    matches = [
        (evidence_id, entry)
        for evidence_id, entry in evidence.items()
        if entry.get("kind") == kind
    ]
    if len(matches) != 1 or not isinstance(matches[0][1].get("payload"), dict):
        _invalid()
    return matches[0][0], matches[0][1]["payload"]


def _evidence_matches(
    evidence: dict[str, dict[str, object]],
    evidence_id: object,
    *,
    kind: str,
    sha256: object | None = None,
) -> bool:
    if not isinstance(evidence_id, str):
        return False
    entry = evidence.get(evidence_id)
    return bool(
        entry is not None
        and entry.get("kind") == kind
        and (sha256 is None or entry.get("sha256") == sha256)
    )


def _input_records(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list) or not value or len(value) > 64:
        _invalid()
    result: list[dict[str, object]] = []
    for raw in value:
        item = _object(raw, INPUT_FIELDS)
        family = item.get("family")
        if family not in REQUIRED_INPUT_FAMILIES:
            _invalid()
        normalized: dict[str, object] = {
            "byteSha256": _hash(item.get("byteSha256")),
            "captionSha256": _hash(item.get("captionSha256"), allow_empty=True),
            "family": family,
            "fileRefHash": _hash(item.get("fileRefHash")),
            "groupRefHash": _hash(item.get("groupRefHash"), allow_empty=True),
            "nameSha256": _hash(item.get("nameSha256")),
            "ownerRefHash": _hash(item.get("ownerRefHash")),
            "position": _nonnegative_int(item.get("position")),
            "sizeBytes": _positive_int(item.get("sizeBytes")),
            "telegramEvidenceId": _evidence_id(item.get("telegramEvidenceId")),
            "visibleIdentity": _visible_identity(item.get("visibleIdentity")),
            "workerEvidenceId": _evidence_id(item.get("workerEvidenceId")),
        }
        result.append(normalized)
    return result


def _input_matrix_proven(
    telegram_inputs: list[dict[str, object]],
    worker_inputs: list[dict[str, object]],
    *,
    evidence: dict[str, dict[str, object]],
    owner_ref: str,
) -> bool:
    if telegram_inputs != worker_inputs:
        return False
    if [item["position"] for item in telegram_inputs] != list(
        range(len(telegram_inputs))
    ):
        return False
    if {str(item["family"]) for item in telegram_inputs} != REQUIRED_INPUT_FAMILIES:
        return False
    if any(item["ownerRefHash"] != owner_ref for item in telegram_inputs):
        return False
    if len({str(item["fileRefHash"]) for item in telegram_inputs}) != len(
        telegram_inputs
    ):
        return False
    telegram_evidence_ids = [
        str(item["telegramEvidenceId"]) for item in telegram_inputs
    ]
    worker_evidence_ids = [str(item["workerEvidenceId"]) for item in telegram_inputs]
    if (
        len(telegram_evidence_ids) != len(set(telegram_evidence_ids))
        or len(worker_evidence_ids) != len(set(worker_evidence_ids))
        or set(telegram_evidence_ids) & set(worker_evidence_ids)
    ):
        return False
    for item in telegram_inputs:
        telegram_file = evidence.get(str(item["telegramEvidenceId"]))
        worker_file = evidence.get(str(item["workerEvidenceId"]))
        if (
            telegram_file is None
            or worker_file is None
            or telegram_file.get("kind") != "telegram_input"
            or worker_file.get("kind") != "worker_input"
            or telegram_file.get("sha256") != item["byteSha256"]
            or worker_file.get("sha256") != item["byteSha256"]
            or telegram_file.get("sizeBytes") != item["sizeBytes"]
            or worker_file.get("sizeBytes") != item["sizeBytes"]
        ):
            return False

    by_name: dict[str, list[dict[str, object]]] = {}
    groups: dict[str, list[dict[str, object]]] = {}
    for item in telegram_inputs:
        by_name.setdefault(str(item["nameSha256"]), []).append(item)
        group_ref = str(item["groupRefHash"])
        if group_ref:
            groups.setdefault(group_ref, []).append(item)
        elif item["captionSha256"]:
            return False
    same_name_distinct = any(
        len(items) >= 2
        and len({str(item["byteSha256"]) for item in items}) == len(items)
        and len({str(item["fileRefHash"]) for item in items}) == len(items)
        for items in by_name.values()
    )
    captioned_group = any(
        len(items) >= 2 and sum(bool(item["captionSha256"]) for item in items) == 1
        for items in groups.values()
    )
    return same_name_distinct and captioned_group


def _input_files_proven(
    inputs: list[dict[str, object]],
    *,
    evidence: dict[str, dict[str, object]],
    evidence_refs: set[str],
    evidence_id_field: str,
    kind: str,
) -> bool:
    for item in inputs:
        evidence_id = str(item[evidence_id_field])
        entry = evidence.get(evidence_id)
        if (
            evidence_id not in evidence_refs
            or entry is None
            or entry.get("kind") != kind
            or entry.get("sha256") != item["byteSha256"]
            or entry.get("sizeBytes") != item["sizeBytes"]
        ):
            return False
    return True


def _telegram_ledger_proven(
    payload: dict[str, object],
    *,
    input_digest: str,
    inputs: list[dict[str, object]],
    journey_ref: str,
) -> bool:
    record = _object(
        payload,
        {"inputManifestSha256", "inputs", "logicalTurnRefHash"},
    )
    ledger_inputs = _input_records(record.get("inputs"))
    return (
        _hash(record.get("inputManifestSha256")) == input_digest
        and _hash(record.get("logicalTurnRefHash")) == journey_ref
        and ledger_inputs == inputs
    )


def _worker_materialization_proven(
    payload: dict[str, object],
    *,
    input_digest: str,
    inputs: list[dict[str, object]],
) -> bool:
    record = _object(
        payload,
        {"inputManifestSha256", "inputs", "materializedInputCount"},
    )
    materialized_inputs = _input_records(record.get("inputs"))
    return (
        _hash(record.get("inputManifestSha256")) == input_digest
        and _nonnegative_int(record.get("materializedInputCount")) == len(inputs)
        and materialized_inputs == inputs
    )


def _telegram_ui_proven(
    payload: dict[str, object],
    *,
    evidence: dict[str, dict[str, object]],
    evidence_refs: set[str],
    inputs: list[dict[str, object]],
    artifact_ref: str,
    output_identity: str,
    run_ref: str,
    work_ref: str,
) -> bool:
    record = _object(
        payload,
        {
            "attachmentIdentities",
            "captureMethod",
            "completion",
            "screenshotEvidenceId",
            "screenshotSha256",
            "visibleText",
        },
    )
    attachment_identities = [
        _visible_identity(item)
        for item in _string_list(record.get("attachmentIdentities"))
    ]
    visible_text = _string_list(record.get("visibleText"))
    completion = _object(
        record.get("completion"),
        {
            "artifactRefHash",
            "attachmentIdentity",
            "count",
            "queenAuthored",
            "runRefHash",
            "workRefHash",
        },
    )
    screenshot_id = _evidence_id(record.get("screenshotEvidenceId"))
    expected_identities = [str(item["visibleIdentity"]) for item in inputs]
    required_text = {
        CASE_ID,
        "Worker Bee completion",
        output_identity,
        *expected_identities,
    }
    return (
        record.get("captureMethod") == "telegram_desktop_accessibility"
        and screenshot_id in evidence_refs
        and _evidence_matches(
            evidence,
            screenshot_id,
            kind="telegram_ui",
            sha256=_hash(record.get("screenshotSha256")),
        )
        and attachment_identities == expected_identities
        and required_text.issubset(set(visible_text))
        and _hash(completion.get("artifactRefHash")) == artifact_ref
        and _visible_identity(completion.get("attachmentIdentity")) == output_identity
        and _positive_int(completion.get("count")) == 1
        and _boolean(completion.get("queenAuthored"))
        and _hash(completion.get("runRefHash")) == run_ref
        and _hash(completion.get("workRefHash")) == work_ref
    )


def _active_work_ui_proven(
    payload: dict[str, object],
    *,
    evidence: dict[str, dict[str, object]],
    evidence_refs: set[str],
    artifact_ref: str,
    output_hash: str,
    output_identity: str,
    run_ref: str,
    work_ref: str,
) -> bool:
    record = _object(
        payload,
        {
            "artifactOpenScreenshotEvidenceId",
            "artifactOpenScreenshotSha256",
            "artifactRefHash",
            "captureMethod",
            "openedArtifactEvidenceId",
            "openedArtifactSha256",
            "runRefHash",
            "screenshotEvidenceId",
            "screenshotSha256",
            "visibleText",
            "workRefHash",
        },
    )
    screenshot_id = _evidence_id(record.get("screenshotEvidenceId"))
    open_screenshot_id = _evidence_id(record.get("artifactOpenScreenshotEvidenceId"))
    opened_artifact_id = _evidence_id(record.get("openedArtifactEvidenceId"))
    visible_text = set(_string_list(record.get("visibleText")))
    return (
        record.get("captureMethod") == "headed_browser_accessibility"
        and {screenshot_id, open_screenshot_id}.issubset(evidence_refs)
        and _evidence_matches(
            evidence,
            screenshot_id,
            kind="active_work_ui",
            sha256=_hash(record.get("screenshotSha256")),
        )
        and _evidence_matches(
            evidence,
            open_screenshot_id,
            kind="artifact_open_ui",
            sha256=_hash(record.get("artifactOpenScreenshotSha256")),
        )
        and _evidence_matches(
            evidence,
            opened_artifact_id,
            kind="opened_artifact",
            sha256=_hash(record.get("openedArtifactSha256")),
        )
        and _hash(record.get("artifactRefHash")) == artifact_ref
        and _hash(record.get("openedArtifactSha256")) == output_hash
        and _hash(record.get("runRefHash")) == run_ref
        and _hash(record.get("workRefHash")) == work_ref
        and {CASE_ID, "Active Work", output_identity}.issubset(visible_text)
    )


def _artifact_ledger_proven(
    payload: dict[str, object],
    *,
    evidence: dict[str, dict[str, object]],
    artifact_ref: str,
    output_hash: str,
    output_size: int,
    output_identity: str,
    run_ref: str,
    work_ref: str,
) -> bool:
    record = _object(
        payload,
        {
            "artifactRefHash",
            "byteSha256",
            "openedArtifactEvidenceId",
            "runRefHash",
            "sizeBytes",
            "state",
            "visibleIdentity",
            "workRefHash",
        },
    )
    opened_artifact_id = _evidence_id(record.get("openedArtifactEvidenceId"))
    opened = evidence.get(opened_artifact_id)
    return (
        _hash(record.get("artifactRefHash")) == artifact_ref
        and _hash(record.get("byteSha256")) == output_hash
        and _positive_int(record.get("sizeBytes")) == output_size
        and _visible_identity(record.get("visibleIdentity")) == output_identity
        and record.get("state") == "available"
        and _hash(record.get("runRefHash")) == run_ref
        and _hash(record.get("workRefHash")) == work_ref
        and opened is not None
        and opened.get("kind") == "opened_artifact"
        and opened.get("sha256") == output_hash
        and opened.get("sizeBytes") == output_size
    )


def _provider_attempts_proven(
    payload: dict[str, object],
    *,
    input_digest: str,
    primary_attempt: str,
    fallback_attempt: str,
    primary_state: object,
    fallback_state: object,
    run_ref: str,
    work_ref: str,
) -> bool:
    record = _object(payload, {"attempts", "inputManifestSha256"})
    raw_attempts = record.get("attempts")
    if not isinstance(raw_attempts, list) or len(raw_attempts) != 2:
        return False
    attempts: list[dict[str, object]] = []
    for raw_attempt in raw_attempts:
        attempt = _object(
            raw_attempt,
            {
                "attemptRefHash",
                "inputManifestSha256",
                "ordinal",
                "runRefHash",
                "state",
                "workRefHash",
            },
        )
        attempts.append(attempt)
    refs = [_hash(item.get("attemptRefHash")) for item in attempts]
    return (
        _hash(record.get("inputManifestSha256")) == input_digest
        and [item.get("ordinal") for item in attempts] == [0, 1]
        and refs == [primary_attempt, fallback_attempt]
        and len(set(refs)) == 2
        and [item.get("state") for item in attempts] == [primary_state, fallback_state]
        and all(
            _hash(item.get("inputManifestSha256")) == input_digest
            and _hash(item.get("runRefHash")) == run_ref
            and _hash(item.get("workRefHash")) == work_ref
            for item in attempts
        )
    )


def _control_receipt_proven(
    payload: dict[str, object],
    *,
    accepted: bool,
    action: object,
    input_digest: str,
    receipt_ref: str,
    run_ref: str,
    work_ref: str,
) -> bool:
    record = _object(
        payload,
        {
            "accepted",
            "action",
            "inputManifestSha256",
            "receiptRefHash",
            "runRefHash",
            "workRefHash",
        },
    )
    return (
        _boolean(record.get("accepted")) is accepted
        and record.get("action") == action
        and _hash(record.get("inputManifestSha256")) == input_digest
        and _hash(record.get("receiptRefHash")) == receipt_ref
        and _hash(record.get("runRefHash")) == run_ref
        and _hash(record.get("workRefHash")) == work_ref
    )


def _restart_trace_proven(
    payload: dict[str, object],
    *,
    input_digest: str,
    before_runtime: str,
    after_runtime: str,
    services: object,
    work_ref: str,
) -> bool:
    record = _object(payload, {"events", "services", "workRefHash"})
    raw_events = record.get("events")
    if not isinstance(raw_events, list) or len(raw_events) != 2:
        return False
    events = [
        _object(
            raw_event,
            {
                "inputManifestSha256",
                "ordinal",
                "runtimeRefHash",
                "state",
                "workRefHash",
            },
        )
        for raw_event in raw_events
    ]
    return (
        record.get("services") == services
        and _hash(record.get("workRefHash")) == work_ref
        and [item.get("ordinal") for item in events] == [0, 1]
        and [item.get("state") for item in events] == ["stopped", "recovered"]
        and [_hash(item.get("runtimeRefHash")) for item in events]
        == [before_runtime, after_runtime]
        and before_runtime != after_runtime
        and all(
            _hash(item.get("inputManifestSha256")) == input_digest
            and _hash(item.get("workRefHash")) == work_ref
            for item in events
        )
    )


def _isolation_trace_proven(
    payload: dict[str, object],
    *,
    input_digest: str,
    run_ref: str,
    work_ref: str,
) -> bool:
    record = _object(
        payload,
        {"inputManifestSha256", "probes", "runRefHash", "workRefHash"},
    )
    raw_probes = record.get("probes")
    if not isinstance(raw_probes, list):
        return False
    probes: dict[str, str] = {}
    for raw_probe in raw_probes:
        probe = _object(raw_probe, {"result", "subject"})
        subject = probe.get("subject")
        result = probe.get("result")
        if (
            not isinstance(subject, str)
            or not isinstance(result, str)
            or subject in probes
        ):
            return False
        probes[subject] = result
    return (
        _hash(record.get("inputManifestSha256")) == input_digest
        and _hash(record.get("runRefHash")) == run_ref
        and _hash(record.get("workRefHash")) == work_ref
        and probes
        == {
            "cross_owner": "owner_scope_denied",
            "intended_worker": "read_allowed",
            "sibling_worker": "worker_scope_denied",
        }
    )


def _negative_failures_proven(
    payload: dict[str, object],
    *,
    run_ref: str,
    work_ref: str,
) -> bool:
    record = _object(payload, {"cases", "runRefHash", "workRefHash"})
    raw_cases = record.get("cases")
    if not isinstance(raw_cases, list):
        return False
    expected = [
        ("missing_parser", "parser_unavailable", "not_supported"),
        ("missing_bytes", "input_bytes_missing", "recovered_same_work"),
        ("expired_link", "artifact_link_expired", "recovered_same_artifact"),
        (
            "delivery_unavailable",
            "delivery_unavailable",
            "delivered_same_artifact",
        ),
        ("cross_owner", "owner_scope_denied", "denied"),
    ]
    cases: list[dict[str, object]] = []
    for raw_case in raw_cases:
        cases.append(
            _object(
                raw_case,
                {
                    "attemptRefHash",
                    "kind",
                    "ordinal",
                    "recovery",
                    "result",
                    "runRefHash",
                    "workRefHash",
                },
            )
        )
    attempt_refs = [_hash(item.get("attemptRefHash")) for item in cases]
    observed = [
        (item.get("kind"), item.get("result"), item.get("recovery")) for item in cases
    ]
    return (
        _hash(record.get("runRefHash")) == run_ref
        and _hash(record.get("workRefHash")) == work_ref
        and len(cases) == len(expected)
        and [item.get("ordinal") for item in cases] == list(range(len(expected)))
        and observed == expected
        and len(attempt_refs) == len(set(attempt_refs))
        and all(
            _hash(item.get("runRefHash")) == run_ref
            and _hash(item.get("workRefHash")) == work_ref
            for item in cases
        )
    )


def _delivery_events_proven(
    payload: dict[str, object],
    *,
    artifact_ref: str,
    run_ref: str,
    work_ref: str,
) -> bool:
    record = _object(
        payload,
        {"artifactRefHash", "events", "runRefHash", "workRefHash"},
    )
    raw_events = record.get("events")
    if not isinstance(raw_events, list):
        return False
    required_kinds = {
        "artifact_delivery",
        "assistant_row",
        "delivery_receipt",
        "queen_completion",
        "telegram_bubble",
    }
    events: list[dict[str, object]] = []
    for raw_event in raw_events:
        events.append(
            _object(
                raw_event,
                {
                    "artifactRefHash",
                    "eventRefHash",
                    "kind",
                    "ordinal",
                    "runRefHash",
                    "state",
                    "workRefHash",
                },
            )
        )
    kinds = [str(item.get("kind")) for item in events]
    event_refs = [_hash(item.get("eventRefHash")) for item in events]
    return (
        _hash(record.get("artifactRefHash")) == artifact_ref
        and _hash(record.get("runRefHash")) == run_ref
        and _hash(record.get("workRefHash")) == work_ref
        and len(events) == len(required_kinds)
        and set(kinds) == required_kinds
        and len(kinds) == len(set(kinds))
        and [item.get("ordinal") for item in events] == list(range(len(events)))
        and len(event_refs) == len(set(event_refs))
        and all(
            item.get("state") == "committed"
            and _hash(item.get("artifactRefHash")) == artifact_ref
            and _hash(item.get("runRefHash")) == run_ref
            and _hash(item.get("workRefHash")) == work_ref
            for item in events
        )
    )


def _gate(
    gate_id: str,
    passed: bool,
    evidence_ids: Iterable[str] = (),
) -> dict[str, object]:
    return {
        "evidenceIds": sorted(set(evidence_ids)),
        "id": gate_id,
        "status": "PASS" if passed else "PARTIAL",
    }


def not_run_result(now: datetime | None = None) -> dict[str, object]:
    checked_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return {
        "artifactDigest": "",
        "blockers": list(REQUIRED_GATES),
        "candidateDigest": "",
        "caseId": CASE_ID,
        "checkedAt": checked_at.isoformat(),
        "contractVersion": CONTRACT_VERSION,
        "gates": [
            {"evidenceIds": [], "id": gate_id, "status": "NOT_RUN"}
            for gate_id in REQUIRED_GATES
        ],
        "ready": False,
        "status": "NOT_RUN",
    }


def invalid_result(now: datetime | None = None) -> dict[str, object]:
    checked_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return {
        "artifactDigest": "",
        "blockers": ["evidence_contract_invalid"],
        "candidateDigest": "",
        "caseId": CASE_ID,
        "checkedAt": checked_at.isoformat(),
        "contractVersion": CONTRACT_VERSION,
        "gates": [
            {"evidenceIds": [], "id": gate_id, "status": "PARTIAL"}
            for gate_id in REQUIRED_GATES
        ],
        "ready": False,
        "status": "PARTIAL",
    }


def _derived_result_digest(result: dict[str, object]) -> str:
    return _canonical_digest(
        {
            "artifactDigest": result.get("artifactDigest"),
            "blockers": result.get("blockers"),
            "candidateDigest": result.get("candidateDigest"),
            "caseId": result.get("caseId"),
            "checkedAt": result.get("checkedAt"),
            "contractVersion": result.get("contractVersion"),
            "gates": result.get("gates"),
            "ready": result.get("ready"),
            "receiptEvidence": result.get("_receiptEvidence"),
            "runAt": result.get("runAt"),
            "status": result.get("status"),
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
    checked_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    payload = _object(manifest, TOP_LEVEL_FIELDS)
    if (
        payload.get("contractVersion") != CONTRACT_VERSION
        or payload.get("caseId") != CASE_ID
    ):
        _invalid()
    run_at = _timestamp(payload.get("runAt"))
    if run_at > checked_at + MAX_FUTURE_SKEW or checked_at - run_at > MAX_RESULT_AGE:
        _invalid()

    candidate = _object(payload.get("candidate"), {"artifactDigest", "candidateDigest"})
    manifest_candidate = _hash(candidate.get("candidateDigest"))
    manifest_artifact = _hash(candidate.get("artifactDigest"))
    expected_candidate = _hash(expected_candidate_digest)
    expected_artifact = _hash(expected_artifact_digest)
    correlation = _object(
        payload.get("correlation"),
        {"journeyRefHash", "ownerRefHash", "runRefHash", "workRefHash"},
    )
    journey_ref = _hash(correlation.get("journeyRefHash"))
    owner_ref = _hash(correlation.get("ownerRefHash"))
    run_ref = _hash(correlation.get("runRefHash"))
    work_ref = _hash(correlation.get("workRefHash"))
    fixture = _object(payload.get("fixture"), {"kind", "manifestSha256"})
    fixture_manifest_digest = _hash(fixture.get("manifestSha256"))
    inputs = _object(payload.get("inputs"), {"telegram", "worker"})
    telegram_inputs = _input_records(inputs.get("telegram"))
    worker_inputs = _input_records(inputs.get("worker"))
    input_digest = _canonical_digest(telegram_inputs)
    synthetic_fixture = (
        fixture.get("kind") == "synthetic_public_safe"
        and fixture_manifest_digest == input_digest
    )
    installed_environment = payload.get("environment") == "installed_local_production"
    candidate_ok = (
        installed_owner_proven
        and installed_environment
        and synthetic_fixture
        and manifest_candidate == expected_candidate
        and manifest_artifact == expected_artifact
    )

    evidence = _verify_evidence(
        payload.get("evidence"),
        evidence_root=evidence_root,
        run_at=run_at,
        expected_candidate_digest=expected_candidate,
        expected_artifact_digest=expected_artifact,
        journey_ref=journey_ref,
        owner_ref=owner_ref,
        run_ref=run_ref,
        work_ref=work_ref,
    )
    input_matrix_ok = _input_matrix_proven(
        telegram_inputs,
        worker_inputs,
        evidence=evidence,
        owner_ref=owner_ref,
    )
    evidence_kind_counts = Counter(str(entry["kind"]) for entry in evidence.values())
    expected_kind_counts = Counter({kind: 1 for kind in EVIDENCE_KINDS})
    expected_kind_counts["telegram_input"] = len(telegram_inputs)
    expected_kind_counts["worker_input"] = len(worker_inputs)
    if evidence_kind_counts != expected_kind_counts:
        _invalid()

    telegram_ledger_id, telegram_ledger_payload = _semantic_entry(
        evidence, "telegram_upload_ledger"
    )
    worker_materialization_id, worker_materialization_payload = _semantic_entry(
        evidence, "worker_materialization"
    )
    telegram_semantics_id, telegram_semantics_payload = _semantic_entry(
        evidence, "telegram_ui_semantics"
    )
    active_semantics_id, active_semantics_payload = _semantic_entry(
        evidence, "active_work_ui_semantics"
    )
    artifact_ledger_id, artifact_ledger_payload = _semantic_entry(
        evidence, "artifact_ledger"
    )
    provider_attempts_id, provider_attempts_payload = _semantic_entry(
        evidence, "provider_attempts"
    )
    control_receipt_id, control_receipt_payload = _semantic_entry(
        evidence, "control_receipt"
    )
    restart_trace_id, restart_trace_payload = _semantic_entry(evidence, "restart_trace")
    isolation_trace_id, isolation_trace_payload = _semantic_entry(
        evidence, "isolation_trace"
    )
    failure_matrix_id, failure_matrix_payload = _semantic_entry(
        evidence, "failure_matrix"
    )
    delivery_ledger_id, delivery_ledger_payload = _semantic_entry(
        evidence, "delivery_ledger"
    )
    referenced_evidence: set[str] = set()

    output = _object(
        payload.get("output"),
        {
            "activeWorkSha256",
            "artifactRefHash",
            "byteSha256",
            "evidenceIds",
            "openedSha256",
            "openedSurfaces",
            "sizeBytes",
            "telegramSha256",
            "visibleIdentity",
        },
    )
    output_refs, output_kinds = _references(
        output.get("evidenceIds"), evidence=evidence
    )
    output_ref_set = set(output_refs)
    referenced_evidence.update(output_refs)
    output_hash = _hash(output.get("byteSha256"))
    output_size = _positive_int(output.get("sizeBytes"))
    artifact_ref = _hash(output.get("artifactRefHash"))
    output_identity = _visible_identity(output.get("visibleIdentity"))

    surfaces = _object(payload.get("surfaces"), {"activeWork", "telegram"})
    telegram = _object(
        surfaces.get("telegram"),
        {"client", "completionVisible", "evidenceIds", "installed", "workRefHash"},
    )
    telegram_refs, telegram_kinds = _references(
        telegram.get("evidenceIds"), evidence=evidence
    )
    telegram_ref_set = set(telegram_refs)
    referenced_evidence.update(telegram_refs)
    telegram_ledger_ok = (
        telegram_ledger_id in telegram_ref_set
        and _telegram_ledger_proven(
            telegram_ledger_payload,
            input_digest=input_digest,
            inputs=telegram_inputs,
            journey_ref=journey_ref,
        )
    )
    telegram_semantics_ok = (
        telegram_semantics_id in telegram_ref_set
        and _telegram_ui_proven(
            telegram_semantics_payload,
            evidence=evidence,
            evidence_refs=telegram_ref_set,
            inputs=telegram_inputs,
            artifact_ref=artifact_ref,
            output_identity=output_identity,
            run_ref=run_ref,
            work_ref=work_ref,
        )
    )
    telegram_ok = (
        candidate_ok
        and telegram.get("client") == "telegram_desktop"
        and _boolean(telegram.get("installed"))
        and _boolean(telegram.get("completionVisible"))
        and _hash(telegram.get("workRefHash")) == work_ref
        and _has_kinds(
            telegram_kinds,
            "telegram_input",
            "telegram_ui",
            "telegram_ui_semantics",
            "telegram_upload_ledger",
        )
        and telegram_ledger_ok
        and telegram_semantics_ok
        and _input_files_proven(
            telegram_inputs,
            evidence=evidence,
            evidence_refs=telegram_ref_set,
            evidence_id_field="telegramEvidenceId",
            kind="telegram_input",
        )
    )

    active_work = _object(
        surfaces.get("activeWork"),
        {"evidenceIds", "headed", "linked", "opened", "workRefHash"},
    )
    active_refs, active_kinds = _references(
        active_work.get("evidenceIds"), evidence=evidence
    )
    active_ref_set = set(active_refs)
    referenced_evidence.update(active_refs)
    active_semantics_ok = (
        active_semantics_id in active_ref_set
        and active_semantics_id in output_ref_set
        and _active_work_ui_proven(
            active_semantics_payload,
            evidence=evidence,
            evidence_refs=active_ref_set,
            artifact_ref=artifact_ref,
            output_hash=output_hash,
            output_identity=output_identity,
            run_ref=run_ref,
            work_ref=work_ref,
        )
    )
    active_work_ok = (
        candidate_ok
        and _boolean(active_work.get("headed"))
        and _boolean(active_work.get("linked"))
        and _boolean(active_work.get("opened"))
        and _hash(active_work.get("workRefHash")) == work_ref
        and _has_kinds(
            active_kinds,
            "active_work_ui",
            "active_work_ui_semantics",
            "artifact_open_ui",
        )
        and active_semantics_ok
    )

    worker = _object(
        payload.get("worker"),
        {
            "evidenceIds",
            "inputManifestSha256",
            "materializedInputCount",
            "ownerRefHash",
            "workRefHash",
        },
    )
    worker_refs, worker_kinds = _references(
        worker.get("evidenceIds"), evidence=evidence
    )
    worker_ref_set = set(worker_refs)
    referenced_evidence.update(worker_refs)
    worker_semantics_ok = (
        worker_materialization_id in worker_ref_set
        and _worker_materialization_proven(
            worker_materialization_payload,
            input_digest=input_digest,
            inputs=worker_inputs,
        )
    )
    worker_ok = (
        candidate_ok
        and _hash(worker.get("workRefHash")) == work_ref
        and _hash(worker.get("ownerRefHash")) == owner_ref
        and _nonnegative_int(worker.get("materializedInputCount")) == len(worker_inputs)
        and _hash(worker.get("inputManifestSha256")) == input_digest
        and _has_kinds(worker_kinds, "worker_input", "worker_materialization")
        and worker_semantics_ok
        and _input_files_proven(
            worker_inputs,
            evidence=evidence,
            evidence_refs=worker_ref_set,
            evidence_id_field="workerEvidenceId",
            kind="worker_input",
        )
    )
    opened_entries = [
        evidence[item]
        for item in output_refs
        if evidence[item]["kind"] == "opened_artifact"
    ]
    opened_surfaces = output.get("openedSurfaces")
    artifact_ledger_ok = (
        artifact_ledger_id in output_ref_set
        and _artifact_ledger_proven(
            artifact_ledger_payload,
            evidence=evidence,
            artifact_ref=artifact_ref,
            output_hash=output_hash,
            output_size=output_size,
            output_identity=output_identity,
            run_ref=run_ref,
            work_ref=work_ref,
        )
    )
    output_ok = (
        isinstance(opened_surfaces, list)
        and opened_surfaces == ["telegram", "active_work"]
        and _hash(output.get("telegramSha256")) == output_hash
        and _hash(output.get("activeWorkSha256")) == output_hash
        and _hash(output.get("openedSha256")) == output_hash
        and _has_kinds(
            output_kinds,
            "active_work_ui_semantics",
            "artifact_ledger",
            "artifact_open_ui",
            "opened_artifact",
        )
        and len(opened_entries) == 1
        and opened_entries[0]["sha256"] == output_hash
        and opened_entries[0]["sizeBytes"] == output_size
        and artifact_ledger_ok
        and telegram_ok
        and active_work_ok
    )

    resilience = _object(payload.get("resilience"), {"control", "fallback", "restart"})
    fallback = _object(
        resilience.get("fallback"),
        {
            "afterInputManifestSha256",
            "beforeInputManifestSha256",
            "evidenceIds",
            "exercised",
            "fallbackAttemptRefHash",
            "fallbackState",
            "primaryAttemptRefHash",
            "primaryState",
            "workRefHash",
        },
    )
    fallback_refs, fallback_kinds = _references(
        fallback.get("evidenceIds"), evidence=evidence
    )
    fallback_ref_set = set(fallback_refs)
    referenced_evidence.update(fallback_refs)
    primary_attempt = _hash(fallback.get("primaryAttemptRefHash"))
    fallback_attempt = _hash(fallback.get("fallbackAttemptRefHash"))
    fallback_ok = (
        candidate_ok
        and _boolean(fallback.get("exercised"))
        and fallback.get("primaryState")
        in {"provider_unavailable", "quota_cooldown", "rate_limited"}
        and fallback.get("fallbackState") == "completed"
        and primary_attempt != fallback_attempt
        and _hash(fallback.get("workRefHash")) == work_ref
        and _hash(fallback.get("beforeInputManifestSha256")) == input_digest
        and _hash(fallback.get("afterInputManifestSha256")) == input_digest
        and _has_kinds(fallback_kinds, "provider_attempts")
        and provider_attempts_id in fallback_ref_set
        and _provider_attempts_proven(
            provider_attempts_payload,
            input_digest=input_digest,
            primary_attempt=primary_attempt,
            fallback_attempt=fallback_attempt,
            primary_state=fallback.get("primaryState"),
            fallback_state=fallback.get("fallbackState"),
            run_ref=run_ref,
            work_ref=work_ref,
        )
    )

    control = _object(
        resilience.get("control"),
        {"accepted", "action", "evidenceIds", "receiptRefHash", "workRefHash"},
    )
    control_refs, control_kinds = _references(
        control.get("evidenceIds"), evidence=evidence
    )
    control_ref_set = set(control_refs)
    referenced_evidence.update(control_refs)
    control_accepted = _boolean(control.get("accepted"))
    control_receipt_ref = _hash(control.get("receiptRefHash"))
    control_ok = (
        candidate_ok
        and control_accepted
        and control.get("action") in {"message", "steer"}
        and control_receipt_ref != work_ref
        and _hash(control.get("workRefHash")) == work_ref
        and _has_kinds(control_kinds, "control_receipt")
        and control_receipt_id in control_ref_set
        and _control_receipt_proven(
            control_receipt_payload,
            accepted=control_accepted,
            action=control.get("action"),
            input_digest=input_digest,
            receipt_ref=control_receipt_ref,
            run_ref=run_ref,
            work_ref=work_ref,
        )
    )

    restart = _object(
        resilience.get("restart"),
        {
            "afterInputManifestSha256",
            "afterRuntimeRefHash",
            "beforeInputManifestSha256",
            "beforeRuntimeRefHash",
            "evidenceIds",
            "performed",
            "recovered",
            "services",
            "workRefHash",
        },
    )
    restart_refs, restart_kinds = _references(
        restart.get("evidenceIds"), evidence=evidence
    )
    restart_ref_set = set(restart_refs)
    referenced_evidence.update(restart_refs)
    before_runtime = _hash(restart.get("beforeRuntimeRefHash"))
    after_runtime = _hash(restart.get("afterRuntimeRefHash"))
    services = restart.get("services")
    restart_ok = (
        candidate_ok
        and _boolean(restart.get("performed"))
        and _boolean(restart.get("recovered"))
        and isinstance(services, list)
        and services == ["core", "glasshive", "telegram", "worker"]
        and before_runtime != after_runtime
        and _hash(restart.get("beforeInputManifestSha256")) == input_digest
        and _hash(restart.get("afterInputManifestSha256")) == input_digest
        and _hash(restart.get("workRefHash")) == work_ref
        and _has_kinds(restart_kinds, "restart_trace")
        and restart_trace_id in restart_ref_set
        and _restart_trace_proven(
            restart_trace_payload,
            input_digest=input_digest,
            before_runtime=before_runtime,
            after_runtime=after_runtime,
            services=services,
            work_ref=work_ref,
        )
    )

    isolation = _object(
        payload.get("isolation"),
        {
            "crossOwnerResult",
            "crossOwnerDenied",
            "evidenceIds",
            "intendedWorkerRead",
            "ownerRefHash",
            "siblingResult",
            "siblingDenied",
            "workRefHash",
        },
    )
    isolation_refs, isolation_kinds = _references(
        isolation.get("evidenceIds"), evidence=evidence
    )
    isolation_ref_set = set(isolation_refs)
    referenced_evidence.update(isolation_refs)
    isolation_ok = (
        candidate_ok
        and _boolean(isolation.get("intendedWorkerRead"))
        and _boolean(isolation.get("crossOwnerDenied"))
        and _boolean(isolation.get("siblingDenied"))
        and isolation.get("crossOwnerResult") == "owner_scope_denied"
        and isolation.get("siblingResult") == "worker_scope_denied"
        and _hash(isolation.get("ownerRefHash")) == owner_ref
        and _hash(isolation.get("workRefHash")) == work_ref
        and _has_kinds(isolation_kinds, "isolation_trace")
        and isolation_trace_id in isolation_ref_set
        and _isolation_trace_proven(
            isolation_trace_payload,
            input_digest=input_digest,
            run_ref=run_ref,
            work_ref=work_ref,
        )
    )

    failures = _object(
        payload.get("failures"),
        {"evidenceIds", "runRefHash", "workRefHash"},
    )
    failure_refs, failure_kinds = _references(
        failures.get("evidenceIds"), evidence=evidence
    )
    failure_ref_set = set(failure_refs)
    referenced_evidence.update(failure_refs)
    negative_failures_ok = (
        candidate_ok
        and _hash(failures.get("runRefHash")) == run_ref
        and _hash(failures.get("workRefHash")) == work_ref
        and _has_kinds(failure_kinds, "failure_matrix")
        and failure_matrix_id in failure_ref_set
        and _negative_failures_proven(
            failure_matrix_payload,
            run_ref=run_ref,
            work_ref=work_ref,
        )
    )

    delivery = _object(
        payload.get("delivery"),
        {
            "artifactDeliveryCount",
            "artifactRefHash",
            "assistantRowCount",
            "deliveryReceiptCount",
            "evidenceIds",
            "queenCompletionCount",
            "state",
            "telegramBubbleCount",
            "workRefHash",
        },
    )
    delivery_refs, delivery_kinds = _references(
        delivery.get("evidenceIds"), evidence=evidence
    )
    delivery_ref_set = set(delivery_refs)
    referenced_evidence.update(delivery_refs)
    delivery_counts = [
        _nonnegative_int(delivery.get(name))
        for name in (
            "artifactDeliveryCount",
            "assistantRowCount",
            "deliveryReceiptCount",
            "queenCompletionCount",
            "telegramBubbleCount",
        )
    ]
    single_delivery_ok = (
        candidate_ok
        and delivery_counts == [1, 1, 1, 1, 1]
        and delivery.get("state") == "sent"
        and _hash(delivery.get("workRefHash")) == work_ref
        and _hash(delivery.get("artifactRefHash")) == artifact_ref
        and _has_kinds(delivery_kinds, "delivery_ledger", "telegram_ui")
        and delivery_ledger_id in delivery_ref_set
        and _delivery_events_proven(
            delivery_ledger_payload,
            artifact_ref=artifact_ref,
            run_ref=run_ref,
            work_ref=work_ref,
        )
        and telegram_ok
    )

    if referenced_evidence != set(evidence):
        _invalid()

    gates = [
        _gate("candidate_binding", candidate_ok),
        _gate("installed_telegram", telegram_ok, telegram_refs),
        _gate("worker_materialization", worker_ok, worker_refs),
        _gate("linked_active_work", active_work_ok, active_refs),
        _gate(
            "input_hashes_order",
            candidate_ok and input_matrix_ok and worker_ok,
            (*telegram_refs, *worker_refs),
        ),
        _gate(
            "output_hash_open", output_ok, (*output_refs, *active_refs, *telegram_refs)
        ),
        _gate("provider_fallback", fallback_ok, fallback_refs),
        _gate("worker_control", control_ok, control_refs),
        _gate("restart_recovery", restart_ok, restart_refs),
        _gate("owner_isolation", isolation_ok, isolation_refs),
        _gate("negative_failures", negative_failures_ok, failure_refs),
        _gate("single_delivery", single_delivery_ok, delivery_refs),
    ]
    blockers = [str(gate["id"]) for gate in gates if gate["status"] != "PASS"]
    ready = not blockers
    receipt_evidence = sorted(
        (
            {
                "kind": str(entry["kind"]),
                "path": str(entry["path"]),
                "sha256": str(entry["sha256"]),
            }
            for entry in evidence.values()
        ),
        key=lambda item: (item["kind"], item["path"]),
    )
    result: dict[str, object] = {
        "_receiptEvidence": receipt_evidence,
        "artifactDigest": expected_artifact,
        "blockers": blockers,
        "candidateDigest": expected_candidate,
        "caseId": CASE_ID,
        "checkedAt": checked_at.isoformat(),
        "contractVersion": CONTRACT_VERSION,
        "gates": gates,
        "ready": ready,
        "runAt": run_at.isoformat(),
        "status": "PASS" if ready else "PARTIAL",
    }
    result["_derivationDigest"] = _derived_result_digest(result)
    result["_derivedPass"] = _DERIVED_PASS if ready else None
    return result


def receipt_manifest(*, result: dict[str, object]) -> dict[str, object]:
    gates = result.get("gates")
    evidence = result.get("_receiptEvidence")
    if (
        result.get("_derivedPass") is not _DERIVED_PASS
        or result.get("_derivationDigest") != _derived_result_digest(result)
        or result.get("caseId") != CASE_ID
        or result.get("contractVersion") != CONTRACT_VERSION
        or result.get("status") != "PASS"
        or result.get("ready") is not True
        or result.get("blockers") != []
        or not isinstance(gates, list)
        or len(gates) != len(REQUIRED_GATES)
        or {gate.get("id") for gate in gates if isinstance(gate, dict)}
        != set(REQUIRED_GATES)
        or any(
            not isinstance(gate, dict) or gate.get("status") != "PASS" for gate in gates
        )
        or not isinstance(evidence, list)
        or not evidence
    ):
        _invalid()
    verified_evidence: list[dict[str, str]] = []
    for raw_entry in evidence:
        entry = _object(raw_entry, {"kind", "path", "sha256"})
        kind = entry.get("kind")
        if kind not in EVIDENCE_KINDS:
            _invalid()
        verified_evidence.append(
            {
                "kind": str(kind),
                "path": _safe_relative_path(entry.get("path")).as_posix(),
                "sha256": _hash(entry.get("sha256")),
            }
        )
    if verified_evidence != sorted(
        verified_evidence, key=lambda item: (item["kind"], item["path"])
    ):
        _invalid()
    run_at = _timestamp(result.get("runAt")).isoformat()
    return {
        "caseId": CASE_ID,
        "contractVersion": CONTRACT_VERSION,
        "evidence": verified_evidence,
        "runAt": run_at,
        "status": "PASS",
        "surface": "telegram",
    }


def _public_result(result: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in result.items() if not key.startswith("_")}


def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        _invalid()
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _release_gate() -> ModuleType:
    root = Path(__file__).resolve().parents[3]
    return _load_module(
        root / "scripts" / "viventium" / "parallel_work_release_gate.py",
        "tgd010_parallel_work_release_gate",
    )


def _private_json(path: Path, *, max_bytes: int = MAX_MANIFEST_BYTES) -> object:
    supplied = path.expanduser()
    try:
        if supplied.is_symlink():
            _invalid()
        exact = supplied.resolve(strict=True)
    except (OSError, RuntimeError):
        _invalid()
    raw, _ = _read_private_file(exact, max_bytes=max_bytes)
    return loads_strict_json(raw)


def _manifest_inside_root(manifest_path: Path, evidence_root: Path) -> object:
    exact_root = _private_directory(evidence_root)
    try:
        supplied = manifest_path.expanduser()
        exact_manifest = supplied.resolve(strict=True)
    except (OSError, RuntimeError):
        _invalid()
    if supplied.is_symlink() or not _inside(exact_manifest, exact_root):
        _invalid()
    return _private_json(exact_manifest)


def _installed_binding(
    *,
    installed_root: Path,
    runtime_owner_state: Path,
    artifact_identity: Path,
) -> tuple[str, str, bool]:
    gate = _release_gate()
    try:
        exact_root = installed_root.expanduser().resolve(strict=True)
        owner_path = runtime_owner_state.expanduser()
        if owner_path.is_symlink() or artifact_identity.expanduser().is_symlink():
            _invalid()
        owner_path = owner_path.resolve(strict=True)
        owner_proven = bool(gate.validate_runtime_owner_state_file(owner_path))
        owner_payload = _private_json(runtime_owner_state)
        if not isinstance(owner_payload, dict):
            _invalid()
        owner_root = Path(str(owner_payload.get("repoRoot") or "")).resolve(strict=True)
        owner_proven = owner_proven and owner_root == exact_root
        identity = _private_json(artifact_identity, max_bytes=64 * 1024)
        candidate_digest, artifact_digest = gate._qa_candidate_digests(identity)
        return _hash(candidate_digest), _hash(artifact_digest), owner_proven
    except EvidenceContractError:
        raise
    except (OSError, RuntimeError, TypeError, ValueError):
        _invalid()
    raise AssertionError("unreachable")


def _write_receipt_manifest(
    *,
    target: Path,
    evidence_root: Path,
    payload: dict[str, object],
) -> None:
    exact_root = _private_directory(evidence_root)
    supplied = target.expanduser()
    try:
        if supplied.is_absolute():
            exact_target = supplied.resolve(strict=False)
        else:
            exact_target = (exact_root / _safe_relative_path(str(supplied))).resolve(
                strict=False
            )
    except (OSError, RuntimeError):
        _invalid()
    if exact_target == exact_root or not _inside(exact_target, exact_root):
        _invalid()
    temporary: Path | None = None
    try:
        relative = exact_target.relative_to(exact_root)
        parent = exact_root
        for part in relative.parts[:-1]:
            parent = parent / part
            if parent.exists() and parent.is_symlink():
                _invalid()
        exact_target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if exact_target.is_symlink():
            _invalid()
        if exact_target.exists():
            metadata = exact_target.lstat()
            if (
                not stat.S_ISREG(metadata.st_mode)
                or metadata.st_uid != os.getuid()
                or stat.S_IMODE(metadata.st_mode) & 0o077
                or metadata.st_nlink != 1
            ):
                _invalid()
        raw = (
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
            + b"\n"
        )
        temporary = exact_target.with_name(f".{exact_target.name}.{os.getpid()}.tmp")
        flags = (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        descriptor = os.open(temporary, flags, 0o600)
        try:
            view = memoryview(raw)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    _invalid()
                view = view[written:]
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.replace(temporary, exact_target)
    except EvidenceContractError:
        raise
    except OSError:
        _invalid()
    finally:
        if temporary is not None:
            try:
                if temporary.exists():
                    temporary.unlink()
            except OSError:
                pass


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--installed-root", type=Path)
    parser.add_argument("--runtime-owner-state", type=Path)
    parser.add_argument("--artifact-identity", type=Path)
    parser.add_argument("--receipt-manifest", type=Path)
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.manifest is None:
        result = not_run_result()
        print(json.dumps(result, indent=2, sort_keys=True))
        return EXIT_NOT_RUN
    try:
        if any(
            value is None
            for value in (
                args.evidence_root,
                args.installed_root,
                args.runtime_owner_state,
                args.artifact_identity,
            )
        ):
            _invalid()
        candidate_digest, artifact_digest, owner_proven = _installed_binding(
            installed_root=args.installed_root,
            runtime_owner_state=args.runtime_owner_state,
            artifact_identity=args.artifact_identity,
        )
        manifest = _manifest_inside_root(args.manifest, args.evidence_root)
        result = assess_manifest(
            manifest,
            evidence_root=args.evidence_root,
            expected_candidate_digest=candidate_digest,
            expected_artifact_digest=artifact_digest,
            installed_owner_proven=owner_proven,
        )
        if args.receipt_manifest is not None and result["status"] == "PASS":
            _write_receipt_manifest(
                target=args.receipt_manifest,
                evidence_root=args.evidence_root,
                payload=receipt_manifest(result=result),
            )
    except EvidenceContractError:
        result = invalid_result()
    print(json.dumps(_public_result(result), indent=2, sort_keys=True))
    return EXIT_PASS if result["status"] == "PASS" else EXIT_PARTIAL


if __name__ == "__main__":
    raise SystemExit(main())

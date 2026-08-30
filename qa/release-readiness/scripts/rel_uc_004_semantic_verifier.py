#!/usr/bin/env python3
"""Derive REL-UC-004 only from signed, fail-closed installed claim evidence."""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import hmac
import importlib.util
import json
import os
import pwd
import re
import secrets
import stat
import struct
import sys
import zlib
from collections.abc import Callable, Iterable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType
from typing import NoReturn

CASE_ID = "REL-UC-004"
CONTRACT_VERSION = 1
VERIFIER_ID = "rel004-semantic-v1"
SURFACE = "cli"
REQUIRED_SERVICES = ("librechat-core",)
OWNED_OPEN_GATE = "PWK-018"
INJECTED_BLOCKERS = (OWNED_OPEN_GATE, "PROMPT-LAYERS", "STORAGE-PRESSURE")
MAX_RESULT_AGE = timedelta(hours=24)
MAX_FUTURE_SKEW = timedelta(minutes=5)
MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_CAPTURE_PIXELS = 25_000_000
SHA256 = re.compile(r"[a-f0-9]{64}\Z")
SHA256_REF = re.compile(r"sha256:[a-f0-9]{64}\Z")
REVISION = re.compile(r"[a-f0-9]{40}\Z")
SAFE_COMPONENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
MANIFEST_FIELDS = frozenset(
    {"candidate", "caseId", "contractVersion", "correlation", "environment", "evidence", "runAt"}
)
EVIDENCE_FIELDS = frozenset({"kind", "path", "sha256"})
DOCUMENT_FIELDS = frozenset(
    {
        "artifactDigest",
        "candidateDigest",
        "caseId",
        "contractVersion",
        "kind",
        "observedAt",
        "ownerRefHash",
        "payload",
        "proof",
        "sessionRef",
    }
)
SESSION_FIELDS = frozenset(
    {
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
)
STATUS_FIELDS = frozenset(
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
SCREENSHOT_KINDS = frozenset(
    {
        "telegram_status_screenshot_injected",
        "telegram_status_screenshot_recovered",
        "web_status_screenshot_injected",
        "web_status_screenshot_recovered",
    }
)
DOCUMENT_KINDS = frozenset(
    {
        "fault_injection",
        "gate_evaluator",
        "install_summary_capture",
        "installed_identity",
        "public_cli_capture",
        "recovery_evidence",
        "release_claim_matrix",
        "service_acknowledgements",
        "telegram_status_observation",
        "web_status_observation",
    }
)
REQUIRED_EVIDENCE_KINDS = SCREENSHOT_KINDS | DOCUMENT_KINDS
SUPPORTED_CLAIM_PATHS = (
    ("public_cli_release", "release", "cli", "public_cli_capture"),
    ("public_cli_completion", "completion", "cli", "public_cli_capture"),
    ("public_cli_readiness", "readiness", "cli", "public_cli_capture"),
    ("install_summary", "readiness", "installer", "install_summary_capture"),
    ("release_check", "release", "cli", "public_cli_capture"),
    ("installed_web_status", "readiness", "web", "web_status_observation"),
    ("installed_telegram_status", "readiness", "telegram", "telegram_status_observation"),
)
REQUIRED_GATES = (
    "installed-owner-source-component-build-runtime",
    "exact-owned-session-and-three-intentional-blockers",
    "all-supported-installed-public-claim-paths",
    "direct-cli-installer-web-and-telegram-visible-proof",
    "every-claim-pre-gate-not-ready-and-fail-closed",
    "parallel-work-dark-and-default-focused",
    "current-candidate-only-blocker-recovery",
    "owned-open-case-remains-release-blocking",
    "signed-restarted-core-service-acknowledgement",
)
_DERIVED_PASS = object()
_DERIVATION_KEY = secrets.token_bytes(32)
_ISSUED_PASSES: dict[int, tuple[dict[str, object], str, str]] = {}


class _LiveAuthority:
    """Retain exact installed owner, candidate, Core restart, and recovered facts."""

    def __init__(
        self,
        *,
        candidate_digest: str,
        artifact_digest: str,
        owner_ref_hash: str,
        artifact_identity: dict[str, object],
        session: dict[str, object],
        service_status: dict[str, object],
        acknowledgements: list[dict[str, object]],
        acknowledgement_module: ModuleType,
        process_probe: Callable[[int, Path], dict[str, object]],
        readiness_facts: dict[str, object],
        fault_backup_present: bool,
    ) -> None:
        self.candidate_digest = candidate_digest
        self.artifact_digest = artifact_digest
        self.owner_ref_hash = owner_ref_hash
        self.artifact_identity = artifact_identity
        self.session = session
        self.service_status = service_status
        self.acknowledgements = acknowledgements
        self.acknowledgement_module = acknowledgement_module
        self.process_probe = process_probe
        self.readiness_facts = readiness_facts
        self.fault_backup_present = fault_backup_present


def _invalid(message: str = "REL-UC-004 semantic evidence is invalid") -> NoReturn:
    raise ValueError(message)


def _object(value: object, fields: frozenset[str] | set[str]) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != set(fields):
        _invalid()
    return value


def _hash(value: object, *, reference: bool = False, revision: bool = False) -> str:
    expression = REVISION if revision else SHA256_REF if reference else SHA256
    if not isinstance(value, str) or expression.fullmatch(value) is None:
        _invalid("REL-UC-004 installed owner, candidate, or artifact identity is invalid")
    return value


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        _invalid("REL-UC-004 evidence timestamp is invalid")
    try:
        result = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("REL-UC-004 evidence timestamp is invalid") from exc
    if result.tzinfo is None or result.utcoffset() != timedelta(0):
        _invalid("REL-UC-004 evidence timestamp is invalid")
    return result.astimezone(timezone.utc)


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: object) -> str:
    raw = value if isinstance(value, str) else _canonical(value)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            _invalid("REL-UC-004 evidence contains duplicate JSON fields")
        result[key] = value
    return result


def _strict_json(raw: bytes) -> object:
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("REL-UC-004 evidence JSON is invalid") from exc


def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        _invalid("REL-UC-004 installed owner authority is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _reject_private_paths(value: object) -> None:
    if isinstance(value, dict):
        for item in value.values():
            _reject_private_paths(item)
    elif isinstance(value, list):
        for item in value:
            _reject_private_paths(item)
    elif isinstance(value, str):
        lowered = value.replace("\\", "/").lower()
        if any(
            marker in lowered
            for marker in (
                "/users/",
                "/home/",
                "/private/var/",
                "/var/folders/",
                "~/",
                "file://",
                "library/application support",
            )
        ):
            _invalid("REL-UC-004 private paths cannot enter semantic evidence")


def _private_root(path: Path) -> Path:
    supplied = Path(path).expanduser()
    try:
        if supplied.is_symlink():
            _invalid("REL-UC-004 private evidence root is invalid")
        root = supplied.resolve(strict=True)
        metadata = root.stat()
    except (OSError, RuntimeError) as exc:
        raise ValueError("REL-UC-004 private evidence root is invalid") from exc
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) & 0o077
    ):
        _invalid("REL-UC-004 private evidence root is invalid")
    try:
        root.relative_to(Path(__file__).resolve().parents[3])
    except ValueError:
        return root
    _invalid("REL-UC-004 private evidence cannot enter the public repository")


def _private_file(relative: object, *, root: Path) -> tuple[bytes, str]:
    if not isinstance(relative, str) or not relative or "\\" in relative:
        _invalid("REL-UC-004 private evidence path is invalid")
    lexical = Path(relative)
    if (
        lexical.is_absolute()
        or lexical.as_posix() != relative
        or any(SAFE_COMPONENT.fullmatch(part) is None for part in lexical.parts)
    ):
        _invalid("REL-UC-004 private evidence path is invalid")
    parent = root
    try:
        for component in lexical.parts[:-1]:
            parent = parent / component
            metadata = parent.lstat()
            if (
                not stat.S_ISDIR(metadata.st_mode)
                or stat.S_ISLNK(metadata.st_mode)
                or metadata.st_uid != os.getuid()
                or stat.S_IMODE(metadata.st_mode) & 0o077
            ):
                _invalid("REL-UC-004 private evidence path is invalid")
        target = root / lexical
        if target.is_symlink() or target.resolve(strict=True) != target:
            _invalid("REL-UC-004 private evidence path is invalid")
        descriptor = os.open(target, os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0))
        try:
            before = os.fstat(descriptor)
            if (
                not stat.S_ISREG(before.st_mode)
                or before.st_uid != os.getuid()
                or stat.S_IMODE(before.st_mode) & 0o077
                or before.st_nlink != 1
                or before.st_size <= 0
                or before.st_size > MAX_FILE_BYTES
            ):
                _invalid("REL-UC-004 private evidence file is invalid")
            raw = bytearray()
            while len(raw) <= MAX_FILE_BYTES:
                chunk = os.read(descriptor, min(65_536, MAX_FILE_BYTES + 1 - len(raw)))
                if not chunk:
                    break
                raw.extend(chunk)
            after = os.fstat(descriptor)
            if (
                len(raw) != before.st_size
                or len(raw) > MAX_FILE_BYTES
                or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
                != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
            ):
                _invalid("REL-UC-004 private evidence changed while being read")
            return bytes(raw), lexical.as_posix()
        finally:
            os.close(descriptor)
    except (OSError, RuntimeError) as exc:
        raise ValueError("REL-UC-004 private evidence file is invalid") from exc


def _png_capture(raw: bytes) -> bool:
    signature = b"\x89PNG\r\n\x1a\n"
    if len(raw) < 57 or not raw.startswith(signature):
        return False
    cursor = len(signature)
    header: tuple[int, int, int, int, int, int, int] | None = None
    compressed = bytearray()
    ended = False
    while cursor + 12 <= len(raw):
        size = struct.unpack_from(">I", raw, cursor)[0]
        end = cursor + size + 12
        if end > len(raw):
            return False
        kind = raw[cursor + 4 : cursor + 8]
        payload = raw[cursor + 8 : cursor + size + 8]
        if zlib.crc32(kind + payload) & 0xFFFFFFFF != struct.unpack_from(">I", raw, cursor + size + 8)[0]:
            return False
        if header is None and kind != b"IHDR":
            return False
        if kind == b"IHDR":
            if header is not None or size != 13:
                return False
            header = struct.unpack(">IIBBBBB", payload)
        elif kind == b"IDAT":
            if ended:
                return False
            compressed.extend(payload)
        elif kind == b"IEND":
            if size != 0 or not compressed:
                return False
            cursor = end
            ended = True
            break
        elif kind[0] & 0x20 == 0 and kind != b"PLTE":
            return False
        cursor = end
    if not ended or cursor != len(raw) or header is None:
        return False
    width, height, depth, color, compression, filtering, interlace = header
    channels = {0: 1, 2: 3, 4: 2, 6: 4}.get(color)
    if (
        width < 640
        or height < 360
        or width > 32_768
        or height > 32_768
        or width * height > MAX_CAPTURE_PIXELS
        or channels is None
        or depth != 8
        or compression != 0
        or filtering != 0
        or interlace != 0
    ):
        return False
    stride = width * channels
    expected = height * (stride + 1)
    try:
        inflater = zlib.decompressobj()
        decoded = inflater.decompress(bytes(compressed), expected + 1)
    except zlib.error:
        return False
    if len(decoded) != expected or not inflater.eof or inflater.unused_data or inflater.unconsumed_tail or inflater.flush():
        return False
    previous = bytearray(stride)
    unique: set[bytes] = set()
    first: bytes | None = None
    different = 0
    minimum = 255
    maximum = 0
    cursor = 0
    for _row in range(height):
        filter_type = decoded[cursor]
        cursor += 1
        if filter_type > 4:
            return False
        row = decoded[cursor : cursor + stride]
        cursor += stride
        reconstructed = bytearray(stride)
        for index, value in enumerate(row):
            left = reconstructed[index - channels] if index >= channels else 0
            above = previous[index]
            upper_left = previous[index - channels] if index >= channels else 0
            if filter_type == 1:
                value += left
            elif filter_type == 2:
                value += above
            elif filter_type == 3:
                value += (left + above) // 2
            elif filter_type == 4:
                estimate = left + above - upper_left
                distances = (abs(estimate - left), abs(estimate - above), abs(estimate - upper_left))
                value += (left, above, upper_left)[distances.index(min(distances))]
            reconstructed[index] = value & 0xFF
        previous = reconstructed
        for offset in range(0, stride, channels):
            pixel = bytes(reconstructed[offset : offset + channels])
            if len(unique) < 256:
                unique.add(pixel)
            if first is None:
                first = pixel
            elif pixel != first:
                different += 1
            for channel in pixel[: 1 if color in {0, 4} else 3]:
                minimum = min(minimum, channel)
                maximum = max(maximum, channel)
    return len(unique) >= 8 and different >= max(256, width * height // 2_000) and maximum - minimum >= 24


def _identity_projection(authority: _LiveAuthority) -> dict[str, object]:
    identity = authority.artifact_identity
    if not isinstance(identity, dict) or identity.get("contractVersion") != 1:
        _invalid("REL-UC-004 installed source or artifact identity is invalid")
    source = identity.get("source")
    installed = identity.get("installed")
    nested = identity.get("nestedComponents")
    if not isinstance(source, dict) or not isinstance(installed, dict) or not isinstance(nested, list) or not nested:
        _invalid("REL-UC-004 installed source or component artifact identity is invalid")
    components = []
    for component in nested:
        if not isinstance(component, dict):
            _invalid("REL-UC-004 installed component artifact identity is invalid")
        name = component.get("name")
        if not isinstance(name, str) or SAFE_COMPONENT.fullmatch(name) is None:
            _invalid("REL-UC-004 installed component artifact identity is invalid")
        components.append(
            {
                "name": name,
                "pin": _hash(component.get("pin"), revision=True),
                "revision": _hash(component.get("revision"), revision=True),
                "worktreeSha256": _hash(component.get("worktreeHash")),
            }
        )
    return {
        "ownerBindingSha256": _hash(authority.owner_ref_hash),
        "source": {
            "revision": _hash(source.get("revision"), revision=True),
            "worktreeSha256": _hash(source.get("worktreeHash")),
            "componentsLockSha256": _hash(source.get("componentsLockSha256")),
        },
        "components": components,
        "build": {
            "frontendBuildSha256": _hash(installed.get("frontendBuildSha256")),
            "apiBuildSha256": _hash(installed.get("apiBuildSha256")),
            "prebuiltBinarySha256": _hash(installed.get("prebuiltBinarySha256")),
            "runtimeServiceManifestSha256": _hash(installed.get("runtimeServiceManifestSha256")),
        },
        "runtime": {
            "rootRevision": _hash(installed.get("rootRevision"), revision=True),
            "runningServiceSha256": _hash(installed.get("runningServiceSha256")),
            "runtimeOwnerExecutableSha256": _hash(installed.get("runtimeOwnerExecutableSha256")),
            "ownerCommandContractSha256": _hash(installed.get("ownerCommandContractSha256")),
            "artifactIdentityDigest": _hash(authority.session.get("artifactIdentityDigest"), reference=True),
            "componentArtifactDigest": _hash(authority.session.get("componentArtifactDigest"), reference=True),
            "installedRootHash": _hash(authority.session.get("installedRootHash"), reference=True),
        },
    }


def probe_live_authority(*, now: datetime | None = None) -> _LiveAuthority:
    """Resolve the canonical installed owner and its exact release QA session."""

    forbidden = {
        "VIVENTIUM_APP_SUPPORT_DIR",
        "VIVENTIUM_RUNTIME_DIR",
        "VIVENTIUM_RUNTIME_PROFILE",
        "VIVENTIUM_LOCAL_QA_CASE_ID",
        "VIVENTIUM_LOCAL_QA_CASE_TOKEN",
        "VIVENTIUM_LOCAL_QA_SESSION_REF",
        "VIVENTIUM_LOCAL_QA_MODE",
        "VIVENTIUM_LOCAL_QA_COMPONENT_ARTIFACT_DIGEST",
    }
    if any(name in os.environ for name in forbidden):
        _invalid("REL-UC-004 installed owner authority is unavailable")
    try:
        home = Path(pwd.getpwuid(os.getuid()).pw_dir).resolve(strict=True)
        support = home / "Library" / "Application Support" / "Viventium"
        runtime = support / "runtime"
        owner_path = support / "state" / "runtime" / "isolated" / "stack-owner.json"
        source_root = Path(__file__).resolve().parents[3]
        gate = _load_module(source_root / "scripts/viventium/parallel_work_release_gate.py", "rel004_live_release_gate")
        if not gate.validate_runtime_owner_state_file(owner_path):
            _invalid("REL-UC-004 installed owner authority is unavailable")
        control = _load_module(source_root / "scripts/viventium/local_qa_runtime_control.py", "rel004_live_runtime_control")
        _owner_raw, owner = control._read_private_json(owner_path, label="runtime owner", max_bytes=64 * 1024)
        if not isinstance(owner, dict):
            _invalid("REL-UC-004 installed owner authority is unavailable")
        installed = Path(str(owner.get("repoRoot") or "")).resolve(strict=True)
        if (
            installed != source_root
            or Path(str(owner.get("appSupportDir") or "")).resolve(strict=True) != support.resolve(strict=True)
            or owner.get("command") not in {"start", "launch"}
        ):
            _invalid("REL-UC-004 installed owner authority is unavailable")
        identity_path = runtime / "parallel-work-artifact-identity.json"
        arguments = {
            "state_path": runtime / "local-qa" / "active.json",
            "installed_root": installed,
            "artifact_identity_path": identity_path,
            "local_qa_request_path": runtime / "parallel-work-local-qa-request.json",
        }
        session = control.active_session(**arguments, now=now)
        if session.get("caseId") != CASE_ID:
            _invalid("REL-UC-004 installed owner session is invalid")
        status = control.require_restart_ready(**arguments, now=now)
        _identity_raw, identity = control._read_private_json(identity_path, label="installed artifact identity", max_bytes=128 * 1024)
        candidate, artifact = gate._qa_candidate_digests(identity)
        acknowledgement_module = _load_module(source_root / "scripts/viventium/local_qa_service_ack.py", "rel004_live_service_ack")
        acknowledgements = []
        for service in REQUIRED_SERVICES:
            _raw, acknowledgement = control._read_private_json(
                runtime / "local-qa" / "acks" / str(session["sessionRef"]) / f"{service}.json",
                label="live service acknowledgement",
                max_bytes=16 * 1024,
            )
            acknowledgements.append(acknowledgement)
        _facts_raw, facts = control._read_private_json(
            runtime / "parallel-work-readiness-facts.json",
            label="installed readiness facts",
            max_bytes=128 * 1024,
        )
        if not isinstance(facts, dict):
            _invalid("REL-UC-004 installed readiness facts are invalid")
        backup = runtime / "local-qa" / "release-claim-backup.json"
        return _LiveAuthority(
            candidate_digest=_hash(candidate),
            artifact_digest=_hash(artifact),
            owner_ref_hash=_hash(gate._owner_binding_sha256(owner)),
            artifact_identity=identity,
            session=session,
            service_status=status,
            acknowledgements=acknowledgements,
            acknowledgement_module=acknowledgement_module,
            process_probe=acknowledgement_module.probe_process,
            readiness_facts=facts,
            fault_backup_present=backup.exists() or backup.is_symlink(),
        )
    except (ImportError, KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
        raise ValueError("REL-UC-004 installed owner authority is unavailable") from exc


def _live_session(authority: _LiveAuthority, *, run_at: datetime, now: datetime) -> None:
    session = _object(authority.session, SESSION_FIELDS)
    status = _object(authority.service_status, STATUS_FIELDS)
    token = session.get("caseToken")
    if not isinstance(token, str):
        _invalid("REL-UC-004 installed owner session is invalid")
    try:
        decoded = base64.urlsafe_b64decode(token + "=")
    except (TypeError, ValueError) as exc:
        raise ValueError("REL-UC-004 installed owner session is invalid") from exc
    session_ref = "qa_" + hashlib.sha256(token.encode()).hexdigest()[:24]
    if (
        len(decoded) != 32
        or base64.urlsafe_b64encode(decoded).decode().rstrip("=") != token
        or session.get("caseId") != CASE_ID
        or session.get("contractVersion") != CONTRACT_VERSION
        or session.get("mode") != "rel_uc_004"
        or session.get("modeVariable") != "VIVENTIUM_RELEASE_LOCAL_QA_MODE"
        or session.get("sessionRef") != session_ref
    ):
        _invalid("REL-UC-004 installed owner session is invalid")
    started = _timestamp(session.get("startedAt"))
    expires = _timestamp(session.get("expiresAt"))
    if not started <= run_at < expires or not started <= now < expires:
        _invalid("REL-UC-004 installed owner session is stale")
    if (
        status.get("caseId") != CASE_ID
        or status.get("mode") != session.get("mode")
        or status.get("sessionRef") != session_ref
        or status.get("expiresAt") != session.get("expiresAt")
        or status.get("restartState") != "ready"
        or status.get("requiredServices") != list(REQUIRED_SERVICES)
        or status.get("acknowledgedServices") != list(REQUIRED_SERVICES)
        or status.get("missingServices") != []
        or SHA256_REF.fullmatch(str(status.get("serviceAckDigest") or "")) is None
    ):
        _invalid("REL-UC-004 live service acknowledgement is invalid")


def _documents(
    evidence: object,
    *,
    root: Path,
    authority: _LiveAuthority,
    owner: str,
    run_at: datetime,
) -> tuple[dict[str, dict[str, object]], dict[str, str], list[dict[str, str]]]:
    if not isinstance(evidence, list) or len(evidence) != len(REQUIRED_EVIDENCE_KINDS):
        _invalid("REL-UC-004 required installed claim or visible evidence is missing")
    documents: dict[str, dict[str, object]] = {}
    captures: dict[str, str] = {}
    receipts: list[dict[str, str]] = []
    used_paths: set[str] = set()
    started = _timestamp(authority.session["startedAt"])
    for raw_entry in evidence:
        entry = _object(raw_entry, EVIDENCE_FIELDS)
        kind = entry.get("kind")
        if not isinstance(kind, str) or kind not in REQUIRED_EVIDENCE_KINDS or kind in documents or kind in captures:
            _invalid("REL-UC-004 evidence kind is missing or duplicated")
        content, relative = _private_file(entry.get("path"), root=root)
        measured = hashlib.sha256(content).hexdigest()
        if relative in used_paths or not hmac.compare_digest(measured, _hash(entry.get("sha256"))):
            _invalid("REL-UC-004 evidence digest or path is invalid")
        used_paths.add(relative)
        receipts.append({"kind": kind, "path": relative, "sha256": measured})
        if kind in SCREENSHOT_KINDS:
            if not relative.endswith(".png") or not _png_capture(content):
                _invalid("REL-UC-004 visible screenshot is invalid or invented")
            captures[kind] = measured
            continue
        if not relative.endswith(".json"):
            _invalid("REL-UC-004 signed semantic evidence is invalid")
        document = _object(_strict_json(content), DOCUMENT_FIELDS)
        _reject_private_paths(document)
        if (
            document.get("caseId") != CASE_ID
            or document.get("contractVersion") != CONTRACT_VERSION
            or document.get("kind") != kind
            or document.get("candidateDigest") != authority.candidate_digest
            or document.get("artifactDigest") != authority.artifact_digest
            or document.get("ownerRefHash") != owner
            or document.get("sessionRef") != authority.session["sessionRef"]
            or not isinstance(document.get("payload"), dict)
        ):
            _invalid("REL-UC-004 evidence owner, candidate, artifact, or session is invalid")
        observed = _timestamp(document.get("observedAt"))
        if not started <= observed <= run_at:
            _invalid("REL-UC-004 evidence timestamp is stale")
        unsigned = {key: value for key, value in document.items() if key != "proof"}
        expected = authority.acknowledgement_module._proof(unsigned, authority.session["caseToken"])
        if not isinstance(document.get("proof"), str) or not hmac.compare_digest(str(document["proof"]), expected):
            _invalid("REL-UC-004 evidence signature is invalid")
        documents[kind] = document["payload"]
    if set(documents) != DOCUMENT_KINDS or set(captures) != SCREENSHOT_KINDS or len(set(captures.values())) != len(captures):
        _invalid("REL-UC-004 installed screenshot or signed evidence is missing")
    return documents, captures, sorted(receipts, key=lambda item: (item["kind"], item["path"]))


def _acknowledgements(
    payload: dict[str, object], *, authority: _LiveAuthority, run_at: datetime, now: datetime
) -> None:
    fields = {
        "acknowledgedServices",
        "acknowledgements",
        "missingServices",
        "requiredServices",
        "restartState",
        "serviceAckDigest",
    }
    acknowledgements = payload.get("acknowledgements")
    if (
        set(payload) != fields
        or payload.get("requiredServices") != list(REQUIRED_SERVICES)
        or payload.get("acknowledgedServices") != list(REQUIRED_SERVICES)
        or payload.get("missingServices") != []
        or payload.get("restartState") != "ready"
        or payload.get("serviceAckDigest") != authority.service_status.get("serviceAckDigest")
        or not isinstance(acknowledgements, list)
        or len(acknowledgements) != len(REQUIRED_SERVICES)
        or _canonical(acknowledgements) != _canonical(authority.acknowledgements)
        or "sha256:" + _digest(acknowledgements) != payload.get("serviceAckDigest")
    ):
        _invalid("REL-UC-004 live service acknowledgement is invalid")
    for expected_service, acknowledgement in zip(REQUIRED_SERVICES, acknowledgements, strict=True):
        if (
            not isinstance(acknowledgement, dict)
            or acknowledgement.get("serviceId") != expected_service
            or _timestamp(acknowledgement.get("acknowledgedAt")) > run_at
            or not authority.acknowledgement_module.acknowledgement_valid(
                acknowledgement,
                state_payload=authority.session,
                process_probe=authority.process_probe,
                now=now,
            )
        ):
            _invalid("REL-UC-004 live service acknowledgement is invalid or late")


def _fault_injection(payload: dict[str, object], *, authority: _LiveAuthority, run_at: datetime) -> bool:
    try:
        fields = {"appliedAt", "backup", "before", "diskBytesWritten", "injected", "storageProbe"}
        if set(payload) != fields or payload["storageProbe"] != "synthetic_threshold_only":
            return False
        bytes_written = payload["diskBytesWritten"]
        if isinstance(bytes_written, bool) or not isinstance(bytes_written, int) or not 0 < bytes_written <= 20_000:
            return False
        applied = _timestamp(payload["appliedAt"])
        if not _timestamp(authority.session["startedAt"]) <= applied < run_at:
            return False
        original = payload["before"]
        injected = payload["injected"]
        if not isinstance(original, dict) or not isinstance(injected, dict):
            return False
        if original.get("contractVersion") != 1:
            return False
        prompt = original.get("promptLayers")
        storage = original.get("storagePressure")
        if (
            not isinstance(prompt, dict)
            or prompt.get("status") != "verified"
            or SHA256.fullmatch(str(prompt.get("registryHash") or "")) is None
            or not isinstance(storage, dict)
            or storage.get("status") != "healthy"
        ):
            return False
        expected = copy.deepcopy(original)
        original_hash = str(prompt["registryHash"])
        expected["promptLayers"].update(
            {
                "status": "mismatch",
                "registryHash": "0" * 64 if original_hash != "0" * 64 else "1" * 64,
                "reason": "local_qa_prompt_hash_mismatch",
            }
        )
        expected["storagePressure"] = {
            "version": 1,
            "status": "critical",
            "usedPercent": 96.0,
            "availableBytes": 4_300_000_000,
            "thresholdPercent": 95.0,
            "warningMarginPercent": 10.0,
            "reason": "local_qa_threshold_injection",
        }
        expected_backup = {
            "contractVersion": 1,
            "injectedDigest": _digest(expected),
            "original": original,
            "originalDigest": _digest(original),
            "sessionRef": authority.session["sessionRef"],
        }
        return injected == expected and payload["backup"] == expected_backup
    except (KeyError, TypeError, ValueError):
        return False


def _open_gate(value: object, *, authority: _LiveAuthority, with_owner: bool) -> bool:
    if not isinstance(value, dict):
        return False
    fields = {"artifactDigest", "candidateDigest", "caseId", "status"}
    if with_owner:
        fields.add("owner")
    return (
        set(value) == fields
        and value.get("caseId") == OWNED_OPEN_GATE
        and value.get("status") == "PARTIAL"
        and value.get("candidateDigest") == authority.candidate_digest
        and value.get("artifactDigest") == authority.artifact_digest
        and (
            not with_owner
            or value.get("owner") == "qa/parallel-orchestrator/cases.md"
        )
    )


def _gate_evaluator(
    payload: dict[str, object], *, fault: dict[str, object], authority: _LiveAuthority
) -> tuple[bool, bool, bool]:
    try:
        if set(payload) != {"configDefaults", "injected", "recovered"}:
            return False, False, False
        defaults = payload["configDefaults"]
        dark = defaults == {
            "source": {"availability": False, "mode": "focused"},
            "installed": {"availability": False, "mode": "focused"},
        }
        fields = {
            "blockingChecks",
            "exposureAllowed",
            "label",
            "mode",
            "openGates",
            "readinessFacts",
            "releaseReady",
            "sourceDefaultsDark",
        }
        injected = payload["injected"]
        recovered = payload["recovered"]
        if (
            not isinstance(injected, dict)
            or set(injected) != fields
            or not isinstance(recovered, dict)
            or set(recovered) != fields
        ):
            return False, dark, False
        common = all(
            snapshot.get("mode") == "local-qa"
            and snapshot.get("label") == "PRE-GATE / NOT READY"
            and snapshot.get("releaseReady") is False
            and snapshot.get("exposureAllowed") is False
            and snapshot.get("sourceDefaultsDark") is True
            and isinstance(snapshot.get("openGates"), list)
            and len(snapshot["openGates"]) == 1
            and _open_gate(snapshot["openGates"][0], authority=authority, with_owner=True)
            for snapshot in (injected, recovered)
        )
        expected_checks = [
            {"checkId": "PROMPT-LAYERS", "status": "FAIL", "reason": "prompt_layer_hash_mismatch"},
            {"checkId": "STORAGE-PRESSURE", "status": "FAIL", "reason": "storage_pressure"},
        ]
        blockers = common and injected.get("blockingChecks") == expected_checks and injected.get("readinessFacts") == fault.get("injected")
        remaining = common and recovered.get("blockingChecks") == [] and recovered.get("readinessFacts") == fault.get("before")
        return blockers, dark and common, remaining
    except (KeyError, TypeError, ValueError):
        return False, False, False


def _claim_rows(
    payload: dict[str, object], *, fault: dict[str, object], recovery: dict[str, object], run_at: datetime
) -> tuple[bool, bool, bool, dict[tuple[str, str], dict[str, object]]]:
    try:
        if set(payload) != {"claims"} or not isinstance(payload["claims"], list):
            return False, False, False, {}
        claims = payload["claims"]
        if len(claims) != len(SUPPORTED_CLAIM_PATHS) * 2:
            return False, False, False, {}
        paths = {item[0]: item for item in SUPPORTED_CLAIM_PATHS}
        observed: dict[tuple[str, str], dict[str, object]] = {}
        all_fail_closed = True
        all_dark = True
        for row in claims:
            fields = {
                "blockerIds",
                "captureKind",
                "completionClaimed",
                "defaultMode",
                "intent",
                "label",
                "observedAt",
                "outputSha256",
                "parallelAvailable",
                "path",
                "phase",
                "releaseReady",
                "surface",
            }
            if not isinstance(row, dict) or set(row) != fields:
                return False, False, False, {}
            phase = row["phase"]
            path = row["path"]
            if phase not in {"injected", "recovered"} or path not in paths or (phase, path) in observed:
                return False, False, False, {}
            _, intent, surface, capture_kind = paths[path]
            if row["intent"] != intent or row["surface"] != surface or row["captureKind"] != capture_kind:
                return False, False, False, {}
            timestamp = _timestamp(row["observedAt"])
            boundary = fault["appliedAt"] if phase == "injected" else recovery["restoredAt"]
            if not _timestamp(boundary) < timestamp <= run_at:
                return False, False, False, {}
            blockers = list(INJECTED_BLOCKERS) if phase == "injected" else [OWNED_OPEN_GATE]
            fail_closed = (
                row["blockerIds"] == blockers
                and row["label"] in {"PRE-GATE / NOT READY", "NOT READY"}
                and row["releaseReady"] is False
                and row["completionClaimed"] is False
                and SHA256.fullmatch(str(row["outputSha256"])) is not None
            )
            all_fail_closed = all_fail_closed and fail_closed
            all_dark = all_dark and row["parallelAvailable"] is False and row["defaultMode"] == "focused"
            observed[(str(phase), str(path))] = row
        expected = {(phase, path[0]) for phase in ("injected", "recovered") for path in SUPPORTED_CLAIM_PATHS}
        return set(observed) == expected, all_fail_closed, all_dark, observed
    except (KeyError, TypeError, ValueError):
        return False, False, False, {}


def _visible_claims(
    documents: dict[str, dict[str, object]],
    *,
    claims: dict[tuple[str, str], dict[str, object]],
    captures: dict[str, str],
    run_at: datetime,
) -> bool:
    try:
        if len(claims) != len(SUPPORTED_CLAIM_PATHS) * 2:
            return False
        seen: set[tuple[str, str]] = set()
        for kind in (
            "public_cli_capture",
            "install_summary_capture",
            "web_status_observation",
            "telegram_status_observation",
        ):
            document = documents[kind]
            if set(document) != {"captures"} or not isinstance(document["captures"], list) or not document["captures"]:
                return False
            for capture in document["captures"]:
                if not isinstance(capture, dict):
                    return False
                phase = capture.get("phase")
                path = capture.get("path")
                key = (str(phase), str(path))
                claim = claims.get(key)
                if claim is None or key in seen or claim.get("captureKind") != kind:
                    return False
                surface = str(claim["surface"])
                fields = {"captureMethod", "exitCode", "observedAt", "output", "outputSha256", "path", "phase"}
                if surface in {"web", "telegram"}:
                    fields.update({"captureOrigin", "screenshotKind", "screenshotSha256"})
                if set(capture) != fields:
                    return False
                expected_method = {
                    "cli": "installed_process_stdout",
                    "installer": "installed_summary_render",
                    "web": "headed_browser_accessibility",
                    "telegram": "telegram_desktop_accessibility",
                }[surface]
                output = capture.get("output")
                if (
                    capture.get("captureMethod") != expected_method
                    or not isinstance(output, str)
                    or not output
                    or _timestamp(capture.get("observedAt")) > run_at
                    or capture.get("observedAt") != claim.get("observedAt")
                    or capture.get("exitCode") != 1
                    or isinstance(capture.get("exitCode"), bool)
                    or capture.get("outputSha256") != _digest(output)
                    or capture.get("outputSha256") != claim.get("outputSha256")
                    or str(claim["label"]) not in output
                    or not all(str(blocker) in output for blocker in claim["blockerIds"])
                ):
                    return False
                stripped = output.replace("PRE-GATE / NOT READY", "").replace("NOT READY", "")
                if re.search(r"\b(?:ready|complete|completed)\b", stripped, flags=re.IGNORECASE):
                    return False
                if surface in {"web", "telegram"}:
                    expected_kind = f"{surface}_status_screenshot_{phase}"
                    expected_origin = (
                        "headed_browser_window_capture" if surface == "web" else "native_desktop_window_capture"
                    )
                    if (
                        capture.get("screenshotKind") != expected_kind
                        or capture.get("screenshotSha256") != captures.get(expected_kind)
                        or capture.get("captureOrigin") != expected_origin
                    ):
                        return False
                seen.add(key)
        return seen == set(claims)
    except (KeyError, TypeError, ValueError):
        return False


def _recovery(
    payload: dict[str, object], *, authority: _LiveAuthority, fault: dict[str, object], run_at: datetime
) -> tuple[bool, bool]:
    try:
        fields = {
            "currentCandidateEvidence",
            "faultBackupPresent",
            "remainingOpenGate",
            "restoreReceipt",
            "restoredAt",
            "restoredFacts",
            "staleCandidateProbe",
        }
        if set(payload) != fields:
            return False, False
        restored_at = _timestamp(payload["restoredAt"])
        if not _timestamp(fault["appliedAt"]) < restored_at < run_at:
            return False, False
        restored = (
            payload["restoreReceipt"] == {"restored": True, "sessionRef": authority.session["sessionRef"]}
            and payload["restoredFacts"] == fault["before"]
            and payload["restoredFacts"] == authority.readiness_facts
            and payload["faultBackupPresent"] is False
            and authority.fault_backup_present is False
        )
        evidence = payload["currentCandidateEvidence"]
        if not isinstance(evidence, list) or len(evidence) != 2:
            return False, False
        current: set[str] = set()
        for item in evidence:
            if (
                not isinstance(item, dict)
                or set(item) != {"artifactDigest", "blockerId", "candidateDigest", "observedAt", "status"}
                or item["blockerId"] not in {"PROMPT-LAYERS", "STORAGE-PRESSURE"}
                or item["blockerId"] in current
                or item["candidateDigest"] != authority.candidate_digest
                or item["artifactDigest"] != authority.artifact_digest
                or item["status"] != "PASS"
                or not restored_at <= _timestamp(item["observedAt"]) <= run_at
            ):
                return False, False
            current.add(str(item["blockerId"]))
        stale = payload["staleCandidateProbe"]
        if (
            not isinstance(stale, dict)
            or set(stale) != {"artifactDigest", "candidateDigest", "outcome"}
            or _hash(stale["candidateDigest"]) == authority.candidate_digest
            or _hash(stale["artifactDigest"]) == authority.artifact_digest
            or stale["outcome"] != "candidate_mismatch_rejected"
        ):
            return False, False
        remaining = _open_gate(payload["remainingOpenGate"], authority=authority, with_owner=False)
        return restored and current == {"PROMPT-LAYERS", "STORAGE-PRESSURE"}, remaining
    except (KeyError, TypeError, ValueError):
        return False, False


def _derived_result_digest(result: dict[str, object]) -> str:
    return _digest(
        {
            "artifactDigest": result.get("artifactDigest"),
            "blockers": result.get("blockers"),
            "candidateDigest": result.get("candidateDigest"),
            "caseId": result.get("caseId"),
            "claimObservationCount": result.get("claimObservationCount"),
            "claimPathCount": result.get("claimPathCount"),
            "contractVersion": result.get("contractVersion"),
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
    """Verify all installed claim paths fail closed before issuing a derived PASS."""

    if installed_owner_proven is not True:
        _invalid("REL-UC-004 installed owner or candidate binding is invalid")
    expected_candidate = _hash(expected_candidate_digest)
    expected_artifact = _hash(expected_artifact_digest)
    payload = _object(manifest, MANIFEST_FIELDS)
    if (
        payload.get("caseId") != CASE_ID
        or payload.get("contractVersion") != CONTRACT_VERSION
        or payload.get("environment") != "installed_local_production"
    ):
        _invalid("REL-UC-004 installed candidate environment is invalid")
    candidate = _object(payload.get("candidate"), {"artifactDigest", "candidateDigest"})
    if candidate.get("candidateDigest") != expected_candidate or candidate.get("artifactDigest") != expected_artifact:
        _invalid("REL-UC-004 installed candidate or artifact binding is invalid")
    checked = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    run_at = _timestamp(payload.get("runAt"))
    if run_at > checked + MAX_FUTURE_SKEW or checked - run_at > MAX_RESULT_AGE:
        _invalid("REL-UC-004 evidence timestamp is stale or in the future")
    authority = probe_live_authority(now=checked)
    if (
        not isinstance(authority, _LiveAuthority)
        or authority.candidate_digest != expected_candidate
        or authority.artifact_digest != expected_artifact
    ):
        _invalid("REL-UC-004 installed owner, candidate, or artifact binding is invalid")
    _live_session(authority, run_at=run_at, now=checked)
    correlation = _object(payload.get("correlation"), {"ownerRefHash", "sessionRef"})
    owner = _hash(correlation.get("ownerRefHash"))
    if owner != authority.owner_ref_hash or correlation.get("sessionRef") != authority.session["sessionRef"]:
        _invalid("REL-UC-004 installed owner or session binding is invalid")
    root = _private_root(evidence_root)
    documents, captures, receipts = _documents(
        payload.get("evidence"), root=root, authority=authority, owner=owner, run_at=run_at
    )
    _acknowledgements(documents["service_acknowledgements"], authority=authority, run_at=run_at, now=checked)
    fault = documents["fault_injection"]
    recovery = documents["recovery_evidence"]
    injected = _fault_injection(fault, authority=authority, run_at=run_at)
    gate_blockers, defaults_dark, gate_remains_open = _gate_evaluator(
        documents["gate_evaluator"], fault=fault, authority=authority
    )
    all_paths, fail_closed, claims_dark, claims = _claim_rows(
        documents["release_claim_matrix"], fault=fault, recovery=recovery, run_at=run_at
    )
    visible = _visible_claims(documents, claims=claims, captures=captures, run_at=run_at)
    recovered, recovery_gate_open = _recovery(recovery, authority=authority, fault=fault, run_at=run_at)
    checks = (
        documents["installed_identity"] == _identity_projection(authority),
        injected and gate_blockers,
        all_paths,
        visible,
        all_paths and fail_closed and visible,
        defaults_dark and claims_dark,
        recovered,
        gate_remains_open and recovery_gate_open,
        True,
    )
    gates = [
        {"id": gate, "status": "PASS" if passed else "FAIL"}
        for gate, passed in zip(REQUIRED_GATES, checks, strict=True)
    ]
    blockers = [str(gate["id"]) for gate in gates if gate["status"] != "PASS"]
    ready = not blockers
    result: dict[str, object] = {
        "_receiptEvidence": receipts,
        "artifactDigest": expected_artifact,
        "blockers": blockers,
        "candidateDigest": expected_candidate,
        "caseId": CASE_ID,
        "claimObservationCount": len(claims),
        "claimPathCount": len({path for _phase, path in claims}),
        "contractVersion": CONTRACT_VERSION,
        "gates": gates,
        "ready": ready,
        "runAt": run_at.isoformat(timespec="milliseconds"),
        "serviceAckDigest": authority.service_status["serviceAckDigest"],
        "status": "PASS" if ready else "FAIL",
        "surface": SURFACE,
    }
    digest = _derived_result_digest(result)
    result["_derivationDigest"] = digest
    result["_derivedPass"] = _DERIVED_PASS if ready else None
    if ready:
        seal = hmac.new(_DERIVATION_KEY, digest.encode(), hashlib.sha256).hexdigest()
        result["_derivationSeal"] = seal
        if len(_ISSUED_PASSES) >= 128:
            _ISSUED_PASSES.pop(next(iter(_ISSUED_PASSES)))
        _ISSUED_PASSES[id(result)] = (result, digest, seal)
    return result


def receipt_manifest(*, result: dict[str, object]) -> dict[str, object]:
    """Emit the writer's exact receipt only for this process's sealed PASS."""

    if not isinstance(result, dict):
        _invalid("REL-UC-004 derived PASS is invalid")
    issued = _ISSUED_PASSES.get(id(result))
    try:
        digest = _derived_result_digest(result)
    except (TypeError, ValueError):
        _invalid("REL-UC-004 derived PASS is invalid")
    expected_seal = hmac.new(_DERIVATION_KEY, digest.encode(), hashlib.sha256).hexdigest()
    gates = result.get("gates")
    evidence = result.get("_receiptEvidence")
    if (
        issued is None
        or issued[0] is not result
        or result.get("_derivedPass") is not _DERIVED_PASS
        or not hmac.compare_digest(str(result.get("_derivationDigest") or ""), digest)
        or not hmac.compare_digest(digest, issued[1])
        or not hmac.compare_digest(str(result.get("_derivationSeal") or ""), issued[2])
        or not hmac.compare_digest(str(result.get("_derivationSeal") or ""), expected_seal)
        or result.get("caseId") != CASE_ID
        or result.get("contractVersion") != CONTRACT_VERSION
        or result.get("status") != "PASS"
        or result.get("surface") != SURFACE
        or result.get("ready") is not True
        or result.get("blockers") != []
        or result.get("claimPathCount") != len(SUPPORTED_CLAIM_PATHS)
        or result.get("claimObservationCount") != len(SUPPORTED_CLAIM_PATHS) * 2
        or not isinstance(gates, list)
        or [item.get("id") for item in gates if isinstance(item, dict)] != list(REQUIRED_GATES)
        or any(not isinstance(item, dict) or item.get("status") != "PASS" for item in gates)
        or not isinstance(evidence, list)
        or len(evidence) != len(REQUIRED_EVIDENCE_KINDS)
    ):
        _invalid("REL-UC-004 derived PASS is invalid")
    if evidence != sorted(evidence, key=lambda item: (item["kind"], item["path"])):
        _invalid("REL-UC-004 derived PASS evidence is invalid")
    return {
        "caseId": CASE_ID,
        "contractVersion": CONTRACT_VERSION,
        "evidence": evidence,
        "runAt": _timestamp(result.get("runAt")).isoformat(timespec="milliseconds"),
        "status": "PASS",
        "surface": SURFACE,
    }


def _not_run() -> dict[str, object]:
    return {"caseId": CASE_ID, "contractVersion": CONTRACT_VERSION, "ready": False, "status": "NOT_RUN"}


def _write_receipt(path: Path, *, root: Path, payload: dict[str, object]) -> None:
    root = _private_root(root)
    relative = path if not path.is_absolute() else path.relative_to(root)
    if not relative.parts or any(SAFE_COMPONENT.fullmatch(part) is None for part in relative.parts):
        _invalid("REL-UC-004 private receipt path is invalid")
    directory_flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    directory = os.open(root, directory_flags)
    try:
        for component in relative.parts[:-1]:
            try:
                os.mkdir(component, 0o700, dir_fd=directory)
            except FileExistsError:
                pass
            try:
                child = os.open(component, directory_flags, dir_fd=directory)
            except OSError as exc:
                raise ValueError("REL-UC-004 private receipt path is invalid") from exc
            metadata = os.fstat(child)
            if (
                not stat.S_ISDIR(metadata.st_mode)
                or metadata.st_uid != os.getuid()
                or stat.S_IMODE(metadata.st_mode) & 0o077
            ):
                os.close(child)
                _invalid("REL-UC-004 private receipt path is invalid")
            os.close(directory)
            directory = child
        try:
            descriptor = os.open(
                relative.parts[-1],
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | getattr(os, "O_CLOEXEC", 0)
                | getattr(os, "O_NOFOLLOW", 0),
                0o600,
                dir_fd=directory,
            )
        except OSError as exc:
            raise ValueError("REL-UC-004 private receipt path is invalid") from exc
        try:
            raw = (_canonical(payload) + "\n").encode()
            if os.write(descriptor, raw) != len(raw):
                _invalid("REL-UC-004 private receipt could not be written")
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        os.close(directory)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--receipt-manifest", type=Path)
    arguments = parser.parse_args(list(argv) if argv is not None else None)
    if arguments.manifest is None:
        print(json.dumps(_not_run(), sort_keys=True))
        return 4
    try:
        if arguments.evidence_root is None:
            _invalid()
        root = _private_root(arguments.evidence_root)
        supplied = arguments.manifest.expanduser()
        relative = supplied.relative_to(root) if supplied.is_absolute() else supplied
        raw, manifest_relative = _private_file(relative.as_posix(), root=root)
        authority = probe_live_authority()
        result = assess_manifest(
            _strict_json(raw),
            evidence_root=root,
            expected_candidate_digest=authority.candidate_digest,
            expected_artifact_digest=authority.artifact_digest,
            installed_owner_proven=True,
        )
        if arguments.receipt_manifest is not None and result["status"] == "PASS":
            payload = receipt_manifest(result=result)
            payload["verifier"] = {"id": VERIFIER_ID, "manifest": manifest_relative}
            _write_receipt(arguments.receipt_manifest, root=root, payload=payload)
    except (OSError, RuntimeError, TypeError, ValueError):
        print(json.dumps({"caseId": CASE_ID, "contractVersion": CONTRACT_VERSION, "ready": False, "status": "BLOCKED"}, sort_keys=True))
        return 2
    print(json.dumps({key: value for key, value in result.items() if not key.startswith("_")}, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

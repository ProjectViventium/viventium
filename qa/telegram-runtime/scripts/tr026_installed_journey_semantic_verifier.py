#!/usr/bin/env python3
"""Derive TR-026 acceptance only from authenticated installed Telegram evidence."""

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
import struct
import sys
import zlib
from collections.abc import Callable, Iterable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType
from typing import NoReturn

CASE_ID = "TR-026"
CONTRACT_VERSION = 1
VERIFIER_ID = "tr026-semantic-v1"
SURFACE = "telegram"
REQUIRED_SERVICES = ("librechat-core", "telegram-bot")
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
    {"telegram_ui_before", "telegram_ui_settled", "telegram_ui_reopened"}
)
DOCUMENT_KINDS = frozenset(
    {
        "core_revision_trace",
        "installed_identity",
        "mongo_history",
        "service_acknowledgements",
        "telegram_race_audit",
        "telegram_source_trace",
        "telegram_ui_observation",
    }
)
REQUIRED_EVIDENCE_KINDS = SCREENSHOT_KINDS | DOCUMENT_KINDS
REQUIRED_GATES = (
    "installed-owner-source-component-build-runtime",
    "telegram-user-12346-before-stale-send-12347",
    "authoritative-signed-280ms-race-audit",
    "pre-commit-revision-and-post-commit-correction",
    "source-order-admission-parity",
    "post-commit-normal-follow-up",
    "direct-telegram-desktop-visible-and-reopened",
    "original-user-order-and-one-persisted-final-answer",
    "signed-restarted-core-and-telegram-services",
)
_DERIVED_PASS = object()
_DERIVATION_KEY = secrets.token_bytes(32)
_ISSUED_PASSES: dict[int, tuple[dict[str, object], str, str]] = {}


class _LiveAuthority:
    """Keep live owner, candidate, service, and audit authority in process only."""

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
        live_audit: list[dict[str, object]],
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
        self.live_audit = live_audit


def _invalid(message: str = "TR-026 semantic evidence is invalid") -> NoReturn:
    raise ValueError(message)


def _object(value: object, fields: frozenset[str] | set[str]) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != set(fields):
        _invalid()
    return value


def _hash(value: object, *, reference: bool = False, revision: bool = False) -> str:
    expression = REVISION if revision else SHA256_REF if reference else SHA256
    if not isinstance(value, str) or expression.fullmatch(value) is None:
        _invalid("TR-026 installed owner, candidate, or artifact identity is invalid")
    return value


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        _invalid("TR-026 evidence timestamp is invalid")
    try:
        result = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("TR-026 evidence timestamp is invalid") from exc
    if result.tzinfo is None or result.utcoffset() != timedelta(0):
        _invalid("TR-026 evidence timestamp is invalid")
    return result.astimezone(timezone.utc)


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            _invalid("TR-026 evidence contains duplicate JSON fields")
        result[key] = value
    return result


def _strict_json(raw: bytes) -> object:
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("TR-026 evidence JSON is invalid") from exc


def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        _invalid("TR-026 installed owner authority is unavailable")
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
            _invalid("TR-026 private paths cannot enter semantic evidence")


def _private_root(path: Path) -> Path:
    supplied = Path(path).expanduser()
    try:
        if supplied.is_symlink():
            _invalid("TR-026 private evidence root is invalid")
        root = supplied.resolve(strict=True)
        metadata = root.stat()
    except (OSError, RuntimeError) as exc:
        raise ValueError("TR-026 private evidence root is invalid") from exc
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) & 0o077
    ):
        _invalid("TR-026 private evidence root is invalid")
    try:
        root.relative_to(Path(__file__).resolve().parents[3])
    except ValueError:
        return root
    _invalid("TR-026 private evidence cannot enter the public repository")


def _private_file(relative: object, *, root: Path) -> tuple[bytes, str]:
    if not isinstance(relative, str) or not relative or "\\" in relative:
        _invalid("TR-026 private evidence path is invalid")
    lexical = Path(relative)
    if (
        lexical.is_absolute()
        or lexical.as_posix() != relative
        or any(SAFE_COMPONENT.fullmatch(part) is None for part in lexical.parts)
    ):
        _invalid("TR-026 private evidence path is invalid")
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
                _invalid("TR-026 private evidence path is invalid")
        target = root / lexical
        if target.is_symlink() or target.resolve(strict=True) != target:
            _invalid("TR-026 private evidence path is invalid")
        descriptor = os.open(
            target,
            os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
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
                _invalid("TR-026 private evidence file is invalid")
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
                _invalid("TR-026 private evidence file changed while being read")
            return bytes(raw), lexical.as_posix()
        finally:
            os.close(descriptor)
    except (OSError, RuntimeError) as exc:
        raise ValueError("TR-026 private evidence file is invalid") from exc


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
        supplied_crc = struct.unpack_from(">I", raw, cursor + size + 8)[0]
        if zlib.crc32(kind + payload) & 0xFFFFFFFF != supplied_crc:
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
    if (
        len(decoded) != expected
        or not inflater.eof
        or inflater.unused_data
        or inflater.unconsumed_tail
        or inflater.flush()
    ):
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
        _invalid("TR-026 installed source or artifact identity is invalid")
    source = identity.get("source")
    installed = identity.get("installed")
    nested = identity.get("nestedComponents")
    if not isinstance(source, dict) or not isinstance(installed, dict) or not isinstance(nested, list) or not nested:
        _invalid("TR-026 installed source or component artifact identity is invalid")
    components = []
    for component in nested:
        if not isinstance(component, dict):
            _invalid("TR-026 installed component artifact identity is invalid")
        name = component.get("name")
        if not isinstance(name, str) or SAFE_COMPONENT.fullmatch(name) is None:
            _invalid("TR-026 installed component artifact identity is invalid")
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
    """Resolve the canonical installed owner and its authenticated TR-026 session."""

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
        _invalid("TR-026 installed owner authority is unavailable")
    try:
        home = Path(pwd.getpwuid(os.getuid()).pw_dir).resolve(strict=True)
        support = home / "Library" / "Application Support" / "Viventium"
        runtime = support / "runtime"
        owner_path = support / "state" / "runtime" / "isolated" / "stack-owner.json"
        source_root = Path(__file__).resolve().parents[3]
        gate = _load_module(source_root / "scripts/viventium/parallel_work_release_gate.py", "tr026_live_release_gate")
        if not gate.validate_runtime_owner_state_file(owner_path):
            _invalid("TR-026 installed owner authority is unavailable")
        control = _load_module(source_root / "scripts/viventium/local_qa_runtime_control.py", "tr026_live_runtime_control")
        _owner_raw, owner = control._read_private_json(owner_path, label="runtime owner", max_bytes=64 * 1024)
        if not isinstance(owner, dict):
            _invalid("TR-026 installed owner authority is unavailable")
        installed = Path(str(owner.get("repoRoot") or "")).resolve(strict=True)
        if (
            installed != source_root
            or Path(str(owner.get("appSupportDir") or "")).resolve(strict=True) != support.resolve(strict=True)
            or owner.get("command") not in {"start", "launch"}
        ):
            _invalid("TR-026 installed owner authority is unavailable")
        identity_path = runtime / "parallel-work-artifact-identity.json"
        arguments = {
            "state_path": runtime / "local-qa" / "active.json",
            "installed_root": installed,
            "artifact_identity_path": identity_path,
            "local_qa_request_path": runtime / "parallel-work-local-qa-request.json",
        }
        session = control.active_session(**arguments, now=now)
        if session.get("caseId") != CASE_ID:
            _invalid("TR-026 installed owner session is invalid")
        status = control.require_restart_ready(**arguments, now=now)
        _identity_raw, identity = control._read_private_json(identity_path, label="installed artifact identity", max_bytes=128 * 1024)
        candidate, artifact = gate._qa_candidate_digests(identity)
        acknowledgement_module = _load_module(source_root / "scripts/viventium/local_qa_service_ack.py", "tr026_live_service_ack")
        acknowledgement_root = runtime / "local-qa" / "acks" / str(session["sessionRef"])
        acknowledgements = []
        for service in REQUIRED_SERVICES:
            _raw, acknowledgement = control._read_private_json(
                acknowledgement_root / f"{service}.json",
                label="live service acknowledgement",
                max_bytes=16 * 1024,
            )
            acknowledgements.append(acknowledgement)
        parent = _load_module(source_root / "scripts/viventium/telegram_qa_parent_control.py", "tr026_live_parent_control")
        audit = parent.audit_telegram_race(
            state_path=arguments["state_path"],
            installed_root=installed,
            artifact_identity_path=identity_path,
            telegram_state_dir=runtime / "telegram",
        )
        if audit.get("caseId") != CASE_ID or audit.get("sessionRef") != session["sessionRef"] or not isinstance(audit.get("evidence"), list):
            _invalid("TR-026 live signed race audit is invalid")
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
            live_audit=audit["evidence"],
        )
    except (ImportError, KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
        raise ValueError("TR-026 installed owner authority is unavailable") from exc


def _live_session(authority: _LiveAuthority, *, run_at: datetime, now: datetime) -> None:
    session = _object(authority.session, SESSION_FIELDS)
    status = _object(authority.service_status, STATUS_FIELDS)
    token = session.get("caseToken")
    if not isinstance(token, str):
        _invalid("TR-026 installed owner session is invalid")
    try:
        decoded = base64.urlsafe_b64decode(token + "=")
    except (TypeError, ValueError) as exc:
        raise ValueError("TR-026 installed owner session is invalid") from exc
    session_ref = "qa_" + hashlib.sha256(token.encode()).hexdigest()[:24]
    if (
        len(decoded) != 32
        or base64.urlsafe_b64encode(decoded).decode().rstrip("=") != token
        or session.get("caseId") != CASE_ID
        or session.get("contractVersion") != CONTRACT_VERSION
        or session.get("mode") != "tr-026"
        or session.get("modeVariable") != "VIVENTIUM_TELEGRAM_LOCAL_QA_MODE"
        or session.get("sessionRef") != session_ref
    ):
        _invalid("TR-026 installed owner session is invalid")
    started = _timestamp(session.get("startedAt"))
    expires = _timestamp(session.get("expiresAt"))
    if not started <= run_at < expires or not started <= now < expires:
        _invalid("TR-026 installed owner session is stale")
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
        _invalid("TR-026 live service acknowledgement is invalid")


def _documents(
    evidence: object,
    *,
    root: Path,
    authority: _LiveAuthority,
    owner: str,
    run_at: datetime,
) -> tuple[dict[str, dict[str, object]], dict[str, str], list[dict[str, str]]]:
    if not isinstance(evidence, list) or len(evidence) != len(REQUIRED_EVIDENCE_KINDS):
        _invalid("TR-026 required visible, Core, database, or trace evidence is missing")
    documents: dict[str, dict[str, object]] = {}
    captures: dict[str, str] = {}
    receipts: list[dict[str, str]] = []
    used_paths: set[str] = set()
    started = _timestamp(authority.session["startedAt"])
    for raw_entry in evidence:
        entry = _object(raw_entry, EVIDENCE_FIELDS)
        kind = entry.get("kind")
        if not isinstance(kind, str) or kind not in REQUIRED_EVIDENCE_KINDS or kind in documents or kind in captures:
            _invalid("TR-026 evidence kind is missing or duplicated")
        content, relative = _private_file(entry.get("path"), root=root)
        measured = hashlib.sha256(content).hexdigest()
        if relative in used_paths or not hmac.compare_digest(measured, _hash(entry.get("sha256"))):
            _invalid("TR-026 evidence digest or path is invalid")
        used_paths.add(relative)
        receipts.append({"kind": kind, "path": relative, "sha256": measured})
        if kind in SCREENSHOT_KINDS:
            if not relative.endswith(".png") or not _png_capture(content):
                _invalid("TR-026 Telegram screenshot is invalid or invented")
            captures[kind] = measured
            continue
        if not relative.endswith(".json"):
            _invalid("TR-026 signed semantic evidence is invalid")
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
            _invalid("TR-026 evidence owner, candidate, artifact, or session is invalid")
        observed = _timestamp(document.get("observedAt"))
        if not started <= observed <= run_at:
            _invalid("TR-026 evidence timestamp is stale")
        unsigned = {key: value for key, value in document.items() if key != "proof"}
        expected = authority.acknowledgement_module._proof(unsigned, authority.session["caseToken"])
        if not isinstance(document.get("proof"), str) or not hmac.compare_digest(str(document["proof"]), expected):
            _invalid("TR-026 evidence signature is invalid")
        documents[kind] = document["payload"]
    if set(documents) != DOCUMENT_KINDS or set(captures) != SCREENSHOT_KINDS or len(set(captures.values())) != len(captures):
        _invalid("TR-026 direct screenshot or signed evidence is missing")
    return documents, captures, sorted(receipts, key=lambda item: (item["kind"], item["path"]))


def _acknowledgements(
    payload: dict[str, object], *, authority: _LiveAuthority, run_at: datetime, now: datetime
) -> None:
    expected_fields = {
        "acknowledgedServices",
        "acknowledgements",
        "missingServices",
        "requiredServices",
        "restartState",
        "serviceAckDigest",
    }
    if set(payload) != expected_fields:
        _invalid("TR-026 live service acknowledgement is invalid")
    acknowledgements = payload.get("acknowledgements")
    if (
        payload.get("requiredServices") != list(REQUIRED_SERVICES)
        or payload.get("acknowledgedServices") != list(REQUIRED_SERVICES)
        or payload.get("missingServices") != []
        or payload.get("restartState") != "ready"
        or payload.get("serviceAckDigest") != authority.service_status.get("serviceAckDigest")
        or not isinstance(acknowledgements, list)
        or len(acknowledgements) != len(REQUIRED_SERVICES)
        or _canonical(acknowledgements) != _canonical(authority.acknowledgements)
        or "sha256:" + _digest(acknowledgements) != payload.get("serviceAckDigest")
    ):
        _invalid("TR-026 live service acknowledgement is invalid")
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
            _invalid("TR-026 live service acknowledgement is invalid or late")


def _race_audit(payload: dict[str, object], *, authority: _LiveAuthority, run_at: datetime) -> None:
    records = payload.get("records")
    if set(payload) != {"records"} or not isinstance(records, list) or _canonical(records) != _canonical(authority.live_audit):
        _invalid("TR-026 signed race audit is invalid")
    token = str(authority.session["caseToken"])
    previous = "0" * 64
    outcomes: list[str] = []
    event_digests: list[str] = []
    started = _timestamp(authority.session["startedAt"])
    for index, item in enumerate(records, start=1):
        if not isinstance(item, dict):
            _invalid("TR-026 signed race audit is invalid")
        expected_fields = {
            "artifact_ref",
            "case_id",
            "chain_index",
            "configured_delay_ms",
            "event_digest",
            "ledger_semantics",
            "observed_delay_ms",
            "outcome",
            "previous_record_hash",
            "reason",
            "record_hash",
            "recorded_at_ms",
            "schema_version",
            "session_ref",
        }
        if (
            set(item) != expected_fields
            or item.get("schema_version") != 3
            or item.get("case_id") != CASE_ID
            or item.get("artifact_ref") != hashlib.sha256(token.encode()).hexdigest()[:16]
            or item.get("session_ref") != authority.session["sessionRef"]
            or item.get("ledger_semantics") != "owner_mutable_append_only_tamper_evident"
            or item.get("chain_index") != index
            or item.get("previous_record_hash") != previous
            or item.get("configured_delay_ms") != 280
            or not isinstance(item.get("recorded_at_ms"), int)
            or isinstance(item.get("recorded_at_ms"), bool)
        ):
            _invalid("TR-026 signed race audit is invalid")
        observed = datetime.fromtimestamp(int(item["recorded_at_ms"]) / 1000, timezone.utc)
        if not started <= observed <= run_at:
            _invalid("TR-026 signed race audit is stale")
        unsigned = {key: value for key, value in item.items() if key != "record_hash"}
        expected = hmac.new(token.encode(), _canonical(unsigned).encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, str(item.get("record_hash") or "")):
            _invalid("TR-026 signed race audit acknowledgement is invalid")
        previous = expected
        outcomes.append(str(item.get("outcome")))
        event_digests.append(str(item.get("event_digest")))
    try:
        claimed = outcomes.index("claimed")
        delayed = outcomes.index("delay_requested")
    except ValueError as exc:
        raise ValueError("TR-026 signed race audit is incomplete") from exc
    if (
        claimed >= delayed
        or records[claimed].get("reason") != "exact_structured_target"
        or records[delayed].get("reason") != "core_admission_boundary"
        or event_digests[claimed] != event_digests[delayed]
        or SHA256.fullmatch(event_digests[claimed]) is None
    ):
        _invalid("TR-026 signed race audit is invalid")


def _source_events(
    payload: dict[str, object],
    turn: str,
    *,
    started_at: datetime,
    run_at: datetime,
) -> bool:
    try:
        events = payload["events"]
        if (
            set(payload) != {"events", "turnRefHash"}
            or payload["turnRefHash"] != turn
            or not isinstance(events, list)
            or len(events) != 6
            or [item["event"] for item in events]
            != [
                "user_message_observed",
                "user_message_observed",
                "stale_send_committed",
                "core_ingestion_admitted",
                "stale_presentation_retracted",
                "corrected_final_presented",
            ]
            or [item["messageId"] for item in events] != [12345, 12346, 12347, 12346, 12347, 12348]
            or [item["sourceSequence"] for item in events] != [100, 101, 100, 101, 100, 101]
            or events[3].get("delayMs") != 280
        ):
            return False
        stamps = [_timestamp(event["at"]) for event in events]
        return (
            all(started_at <= stamp <= run_at for stamp in stamps)
            and all(before < after for before, after in zip(stamps, stamps[1:]))
            and stamps[3] - stamps[2] == timedelta(milliseconds=280)
        )
    except (KeyError, TypeError, ValueError):
        return False


def _core_scenarios(
    payload: dict[str, object],
    turn: str,
    *,
    source_trace: dict[str, object],
    started_at: datetime,
    run_at: datetime,
) -> tuple[bool, bool, bool]:
    try:
        scenarios = payload["scenarios"]
        control = payload["postCommitControl"]
        if set(payload) != {"postCommitControl", "scenarios"} or not isinstance(scenarios, list) or len(scenarios) != 2:
            return False, False, False
        pre_commit = True
        parity = True
        for scenario, (name, admission, outcome) in zip(
            scenarios,
            (
                ("source_order_normal", [100, 101], None),
                ("source_order_reversed", [101, 100], "source_order_superseded"),
            ),
            strict=True,
        ):
            fields = {
                "admissionOrder",
                "correctedCommittedAt",
                "correctedRevision",
                "correctedTurnRefHash",
                "finalMessageId",
                "higherAdmittedAt",
                "id",
                "initialRevision",
                "initialTurnRefHash",
                "lowerAdmissionOutcome",
                "sourceObservedAt",
                "sourceOrder",
                "staleCommittedAt",
                "staleMessageId",
                "staleRetractedAt",
            }
            if not isinstance(scenario, dict) or set(scenario) != fields:
                return False, False, False
            timeline = [
                _timestamp(scenario[field])
                for field in (
                    "sourceObservedAt",
                    "staleCommittedAt",
                    "higherAdmittedAt",
                    "staleRetractedAt",
                    "correctedCommittedAt",
                )
            ]
            pre_commit = pre_commit and (
                scenario["id"] == name
                and scenario["sourceOrder"] == [100, 101]
                and scenario["initialTurnRefHash"] == turn
                and scenario["correctedTurnRefHash"] == turn
                and scenario["initialRevision"] == 1
                and scenario["correctedRevision"] == 2
                and scenario["staleMessageId"] == 12347
                and scenario["finalMessageId"] == 12348
                and all(started_at <= stamp <= run_at for stamp in timeline)
                and all(before < after for before, after in zip(timeline, timeline[1:]))
                and timeline[2] - timeline[1] == timedelta(milliseconds=280)
                and (
                    name != "source_order_normal"
                    or timeline
                    == [
                        _timestamp(source_trace["events"][index]["at"])
                        for index in (1, 2, 3, 4, 5)
                    ]
                )
            )
            parity = parity and scenario["admissionOrder"] == admission and scenario["lowerAdmissionOutcome"] == outcome
        control_fields = {
            "followUpRevision",
            "followUpTurnRefHash",
            "previousCommittedAt",
            "previousTurnRefHash",
            "sourceObservedAt",
        }
        follow_up = (
            isinstance(control, dict)
            and set(control) == control_fields
            and control["previousTurnRefHash"] == turn
            and _hash(control["followUpTurnRefHash"]) != turn
            and control["followUpRevision"] == 1
            and started_at
            <= _timestamp(control["previousCommittedAt"])
            < _timestamp(control["sourceObservedAt"])
            <= run_at
        )
        return pre_commit, parity, follow_up
    except (KeyError, TypeError, ValueError):
        return False, False, False


def _history(payload: dict[str, object], turn: str) -> bool:
    try:
        if set(payload) != {"beforeReopen", "afterReopen"} or payload["beforeReopen"] != payload["afterReopen"]:
            return False
        history = payload["beforeReopen"]
        if not isinstance(history, dict) or set(history) != {"messages", "tombstones"}:
            return False
        rows = history["messages"]
        tombstones = history["tombstones"]
        if not isinstance(rows, list) or len(rows) != 3 or not isinstance(tombstones, list) or len(tombstones) != 1:
            return False
        expected = (("user", 12345, 100), ("user", 12346, 101), ("assistant", 12348, 101))
        for row, (role, message, sequence) in zip(rows, expected, strict=True):
            if (
                not isinstance(row, dict)
                or row.get("role") != role
                or row.get("messageId") != message
                or row.get("sourceSequence") != sequence
                or row.get("turnRefHash") != turn
                or SHA256.fullmatch(str(row.get("textSha256") or "")) is None
            ):
                return False
        tombstone = tombstones[0]
        return (
            rows[2].get("revision") == 2
            and isinstance(tombstone, dict)
            and tombstone.get("messageId") == 12347
            and tombstone.get("sourceSequence") == 100
            and tombstone.get("turnRefHash") == turn
            and tombstone.get("revision") == 1
            and tombstone.get("state") == "retracted"
        )
    except (KeyError, TypeError, ValueError):
        return False


def _telegram_visible(
    payload: dict[str, object],
    *,
    captures: dict[str, str],
    history: dict[str, object],
    source_trace: dict[str, object],
    started_at: datetime,
    run_at: datetime,
) -> bool:
    try:
        fields = {"bundleId", "captureMethod", "captures", "reopenAction", "surface"}
        if (
            set(payload) != fields
            or payload["bundleId"] != "ru.keepcoder.Telegram"
            or payload["captureMethod"] != "telegram_desktop_accessibility"
            or payload["surface"] != SURFACE
            or not isinstance(payload["captures"], list)
            or len(payload["captures"]) != 3
        ):
            return False
        reopen = payload["reopenAction"]
        if not isinstance(reopen, dict) or set(reopen) != {"method", "performedAt"} or reopen["method"] != "native_conversation_reopen":
            return False
        visible = history["beforeReopen"]["messages"]
        expected = (
            ("before_correction", "telegram_ui_before"),
            ("settled", "telegram_ui_settled"),
            ("reopened", "telegram_ui_reopened"),
        )
        times: list[datetime] = []
        for record, (phase, kind) in zip(payload["captures"], expected, strict=True):
            exact_fields = {
                "bubbles",
                "captureOrigin",
                "observedAt",
                "phase",
                "screenshotKind",
                "screenshotSha256",
                "windowVisible",
            }
            if (
                not isinstance(record, dict)
                or set(record) != exact_fields
                or record.get("phase") != phase
                or record.get("screenshotKind") != kind
                or record.get("screenshotSha256") != captures.get(kind)
                or record.get("captureOrigin") != "native_desktop_window_capture"
                or record.get("windowVisible") is not True
                or not isinstance(record.get("bubbles"), list)
                or len(record["bubbles"]) != 3
            ):
                return False
            times.append(_timestamp(record["observedAt"]))
            if phase == "before_correction":
                bubbles = record["bubbles"]
                if bubbles[:2] != visible[:2] or bubbles[2].get("messageId") != 12347 or bubbles[2].get("revision") != 1:
                    return False
            elif record["bubbles"] != visible:
                return False
        stale_at = _timestamp(source_trace["events"][2]["at"])
        corrected_at = _timestamp(source_trace["events"][5]["at"])
        return (
            started_at
            <= stale_at
            <= times[0]
            < corrected_at
            <= times[1]
            < _timestamp(reopen["performedAt"])
            < times[2]
            <= run_at
        )
    except (KeyError, TypeError, ValueError):
        return False


def _derived_result_digest(result: dict[str, object]) -> str:
    return _digest(
        {
            "artifactDigest": result.get("artifactDigest"),
            "blockers": result.get("blockers"),
            "candidateDigest": result.get("candidateDigest"),
            "caseId": result.get("caseId"),
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
    """Derive each acceptance gate from exact installed, signed user-path evidence."""

    if installed_owner_proven is not True:
        _invalid("TR-026 installed owner or candidate binding is invalid")
    expected_candidate = _hash(expected_candidate_digest)
    expected_artifact = _hash(expected_artifact_digest)
    payload = _object(manifest, MANIFEST_FIELDS)
    if (
        payload.get("caseId") != CASE_ID
        or payload.get("contractVersion") != CONTRACT_VERSION
        or payload.get("environment") != "installed_local_production"
    ):
        _invalid("TR-026 installed candidate environment is invalid")
    candidate = _object(payload.get("candidate"), {"artifactDigest", "candidateDigest"})
    if candidate.get("candidateDigest") != expected_candidate or candidate.get("artifactDigest") != expected_artifact:
        _invalid("TR-026 installed candidate or artifact binding is invalid")
    checked = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    run_at = _timestamp(payload.get("runAt"))
    if run_at > checked + MAX_FUTURE_SKEW or checked - run_at > MAX_RESULT_AGE:
        _invalid("TR-026 evidence timestamp is stale or in the future")
    authority = probe_live_authority(now=checked)
    if (
        not isinstance(authority, _LiveAuthority)
        or authority.candidate_digest != expected_candidate
        or authority.artifact_digest != expected_artifact
    ):
        _invalid("TR-026 installed owner, candidate, or artifact binding is invalid")
    _live_session(authority, run_at=run_at, now=checked)
    correlation = _object(payload.get("correlation"), {"ownerRefHash", "sessionRef", "turnRefHash"})
    owner = _hash(correlation.get("ownerRefHash"))
    turn = _hash(correlation.get("turnRefHash"))
    if owner != authority.owner_ref_hash or correlation.get("sessionRef") != authority.session["sessionRef"]:
        _invalid("TR-026 installed owner or session binding is invalid")
    root = _private_root(evidence_root)
    documents, captures, receipts = _documents(
        payload.get("evidence"), root=root, authority=authority, owner=owner, run_at=run_at
    )
    _acknowledgements(documents["service_acknowledgements"], authority=authority, run_at=run_at, now=checked)
    _race_audit(documents["telegram_race_audit"], authority=authority, run_at=run_at)
    started_at = _timestamp(authority.session["startedAt"])
    source_trace = documents["telegram_source_trace"]
    pre_commit, parity, follow_up = _core_scenarios(
        documents["core_revision_trace"],
        turn,
        source_trace=source_trace,
        started_at=started_at,
        run_at=run_at,
    )
    history_ok = _history(documents["mongo_history"], turn)
    visible_ok = history_ok and _telegram_visible(
        documents["telegram_ui_observation"],
        captures=captures,
        history=documents["mongo_history"],
        source_trace=source_trace,
        started_at=started_at,
        run_at=run_at,
    )
    checks = (
        documents["installed_identity"] == _identity_projection(authority),
        _source_events(source_trace, turn, started_at=started_at, run_at=run_at),
        True,
        pre_commit,
        parity,
        follow_up,
        visible_ok,
        history_ok,
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
    """Return the recorder's exact manifest only for this untampered PASS object."""

    if not isinstance(result, dict):
        _invalid("TR-026 derived PASS is invalid")
    issued = _ISSUED_PASSES.get(id(result))
    try:
        digest = _derived_result_digest(result)
    except (TypeError, ValueError):
        _invalid("TR-026 derived PASS is invalid")
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
        or not isinstance(gates, list)
        or [item.get("id") for item in gates if isinstance(item, dict)] != list(REQUIRED_GATES)
        or any(not isinstance(item, dict) or item.get("status") != "PASS" for item in gates)
        or not isinstance(evidence, list)
        or len(evidence) != len(REQUIRED_EVIDENCE_KINDS)
    ):
        _invalid("TR-026 derived PASS is invalid")
    if evidence != sorted(evidence, key=lambda item: (item["kind"], item["path"])):
        _invalid("TR-026 derived PASS evidence is invalid")
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
        _invalid("TR-026 private receipt path is invalid")
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
                raise ValueError("TR-026 private receipt path is invalid") from exc
            metadata = os.fstat(child)
            if (
                not stat.S_ISDIR(metadata.st_mode)
                or metadata.st_uid != os.getuid()
                or stat.S_IMODE(metadata.st_mode) & 0o077
            ):
                os.close(child)
                _invalid("TR-026 private receipt path is invalid")
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
            raise ValueError("TR-026 private receipt path is invalid") from exc
        try:
            raw = (_canonical(payload) + "\n").encode()
            written = os.write(descriptor, raw)
            if written != len(raw):
                _invalid("TR-026 private receipt could not be written")
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
        if supplied.is_absolute():
            relative = supplied.relative_to(root)
        else:
            relative = supplied
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

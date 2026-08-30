#!/usr/bin/env python3
"""Manage one private, expiring, candidate-bound installed-QA session."""

from __future__ import annotations

import argparse
import base64
import ctypes
import errno
import hashlib
import importlib.util
import json
import os
import re
import secrets
import shlex
import stat
import sys
import tempfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

CONTRACT_VERSION = 1
MIN_EXPIRY_SECONDS = 60
MAX_EXPIRY_SECONDS = 60 * 60
TOKEN_BYTES = 32
REQUEST_MAX_BYTES = 4 * 1024
ARTIFACT_IDENTITY_MAX_BYTES = 64 * 1024
SESSION_STATE_MAX_BYTES = 16 * 1024
CASE_MODES: dict[str, tuple[str, str]] = {
    "TR-026": ("VIVENTIUM_TELEGRAM_LOCAL_QA_MODE", "tr-026"),
    "EMO-UC-047": ("VIVENTIUM_LOCAL_QA_MODE", "emo_uc_047"),
    "EMO-UC-048": ("VIVENTIUM_LOCAL_QA_MODE", "emo_uc_048"),
    "MPV-061": ("VIVENTIUM_LOCAL_QA_MODE", "mpv_061"),
    "PWK-UC-015": ("VIVENTIUM_LOCAL_QA_MODE", "pwk_uc_015"),
    "PWK-UC-016": ("VIVENTIUM_GLASSHIVE_LOCAL_QA_MODE", "pwk_uc_016"),
    "PWK-UC-017": ("VIVENTIUM_GLASSHIVE_LOCAL_QA_MODE", "pwk_uc_017"),
    "REL-UC-004": ("VIVENTIUM_RELEASE_LOCAL_QA_MODE", "rel_uc_004"),
}
STATE_FIELDS = {
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
SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
HASH_PATTERN = re.compile(r"^sha256:[a-f0-9]{64}$")


class DuplicateJsonKeyError(ValueError):
    """Reject ambiguous JSON instead of accepting the last duplicate key."""


class PrivateFileRemovalError(ValueError):
    """Report the recoverable outcome of an identity-safe private-file removal."""

    def __init__(self, outcome: str) -> None:
        super().__init__("private file identity changed before removal")
        self.outcome = outcome


class PrivateArgumentParser(argparse.ArgumentParser):
    """Reject invalid arguments without echoing private values."""

    def error(self, message: str) -> None:
        del message
        raise ValueError("operation_failed")


@dataclass(frozen=True)
class PrivateFileSnapshot:
    """Exact identity and content proof for one trusted private file."""

    raw: bytes
    digest: str
    file_identity: tuple[int, ...]
    parent_identities: tuple[tuple[int, ...], ...]


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJsonKeyError("duplicate JSON key")
        result[key] = value
    return result


def _loads_strict_json(raw: str) -> object:
    return json.loads(raw, object_pairs_hook=_unique_json_object)


def _reject_duplicate_options(argv: Iterable[str]) -> None:
    seen: set[str] = set()
    for argument in argv:
        if not argument.startswith("--"):
            continue
        option = argument.split("=", 1)[0]
        if option in seen:
            raise ValueError("operation_failed")
        seen.add(option)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds")


def _parse_time(value: object) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value or ""))
    except ValueError as exc:
        raise ValueError("local-QA session timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise ValueError("local-QA session timestamp requires a timezone")
    return parsed.astimezone(timezone.utc)


def _root_hash(path: Path) -> str:
    try:
        exact = path.expanduser().resolve(strict=True)
        if not exact.is_dir():
            raise ValueError("installed candidate root is unavailable")
        return "sha256:" + hashlib.sha256(os.fsencode(exact)).hexdigest()
    except (OSError, RuntimeError) as exc:
        raise ValueError("installed candidate root is unavailable") from exc


def _file_identity(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_uid,
        metadata.st_gid,
        metadata.st_nlink,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _stable_file_identity(
    metadata: os.stat_result | tuple[int, ...],
) -> tuple[int, ...]:
    """Return path identity and access policy fields, excluding mutable timestamps."""

    identity = _file_identity(metadata) if hasattr(metadata, "st_dev") else metadata
    return identity[:7]


def _validate_private_parent(metadata: os.stat_result, *, label: str) -> None:
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid not in {0, os.getuid()}
        or stat.S_IMODE(metadata.st_mode) & 0o022
    ):
        raise ValueError(f"{label} is invalid")


def _open_private_path(
    path: Path, *, label: str, max_bytes: int, min_bytes: int = 1
) -> tuple[int, int, tuple[tuple[int, ...], ...]]:
    supplied = path.expanduser()
    if (
        not supplied.is_absolute()
        or supplied.name in {"", ".", ".."}
        or any(part in {"", ".", ".."} for part in supplied.parts[1:])
    ):
        raise ValueError(f"{label} is invalid")
    directory_flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    file_flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    directory_descriptor = -1
    try:
        directory_descriptor = os.open(os.sep, directory_flags)
        parent_identities: list[tuple[int, ...]] = []
        root_metadata = os.fstat(directory_descriptor)
        _validate_private_parent(root_metadata, label=label)
        parent_identities.append(_file_identity(root_metadata))
        for component in supplied.parts[1:-1]:
            next_descriptor = os.open(
                component,
                directory_flags,
                dir_fd=directory_descriptor,
            )
            os.close(directory_descriptor)
            directory_descriptor = next_descriptor
            parent_metadata = os.fstat(directory_descriptor)
            _validate_private_parent(parent_metadata, label=label)
            parent_identities.append(_file_identity(parent_metadata))
        descriptor = os.open(supplied.name, file_flags, dir_fd=directory_descriptor)
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or stat.S_IMODE(metadata.st_mode) != 0o600
            or metadata.st_nlink != 1
            or metadata.st_size < min_bytes
            or metadata.st_size > max_bytes
        ):
            os.close(descriptor)
            raise ValueError(f"{label} is invalid")
        return descriptor, directory_descriptor, tuple(parent_identities)
    except Exception:
        if directory_descriptor >= 0:
            os.close(directory_descriptor)
        raise


def _read_private_descriptor(
    descriptor: int, *, label: str, max_bytes: int
) -> tuple[bytes, tuple[int, ...]]:
    before = os.fstat(descriptor)
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
        len(raw) > max_bytes
        or _file_identity(before) != _file_identity(after)
        or len(raw) != after.st_size
    ):
        raise ValueError(f"{label} is invalid")
    return raw, _file_identity(after)


def _read_private_file_snapshot(
    path: Path, *, label: str, max_bytes: int
) -> PrivateFileSnapshot:
    descriptor = directory_descriptor = -1
    second_descriptor = second_directory = -1
    try:
        descriptor, directory_descriptor, parents_before = _open_private_path(
            path, label=label, max_bytes=max_bytes
        )
        raw, file_before = _read_private_descriptor(
            descriptor, label=label, max_bytes=max_bytes
        )
        second_descriptor, second_directory, parents_after = _open_private_path(
            path, label=label, max_bytes=max_bytes
        )
        second_raw, file_after = _read_private_descriptor(
            second_descriptor, label=label, max_bytes=max_bytes
        )
        current = os.stat(path.name, dir_fd=directory_descriptor, follow_symlinks=False)
        digest = "sha256:" + hashlib.sha256(raw).hexdigest()
        stable_parents_before = tuple(identity[:5] for identity in parents_before)
        stable_parents_after = tuple(identity[:5] for identity in parents_after)
        if (
            stable_parents_before != stable_parents_after
            or _stable_file_identity(file_before) != _stable_file_identity(file_after)
            or _stable_file_identity(file_after) != _stable_file_identity(current)
            or raw != second_raw
            or digest != "sha256:" + hashlib.sha256(second_raw).hexdigest()
        ):
            raise ValueError(f"{label} is invalid")
        return PrivateFileSnapshot(raw, digest, file_after, stable_parents_before)
    except (OSError, OverflowError, RuntimeError, ValueError) as exc:
        raise ValueError(f"{label} is invalid") from exc
    finally:
        for opened in (
            descriptor,
            directory_descriptor,
            second_descriptor,
            second_directory,
        ):
            if opened >= 0:
                try:
                    os.close(opened)
                except OSError:
                    pass


def _assert_private_file_snapshot(
    path: Path, snapshot: PrivateFileSnapshot, *, label: str, max_bytes: int
) -> None:
    current = _read_private_file_snapshot(path, label=label, max_bytes=max_bytes)
    if current != snapshot:
        raise ValueError(f"{label} is invalid")


def _rename_noreplace(
    source: str,
    destination: str,
    *,
    source_dir_fd: int,
    destination_dir_fd: int,
) -> None:
    """Atomically rename one directory entry without replacing its destination."""
    library = ctypes.CDLL(None, use_errno=True)
    source_bytes = os.fsencode(source)
    destination_bytes = os.fsencode(destination)
    operation = None
    flags = 0
    if sys.platform == "darwin":
        operation = getattr(library, "renameatx_np", None)
        flags = 0x00000004  # RENAME_EXCL
    else:
        operation = getattr(library, "renameat2", None)
        flags = 0x00000001  # RENAME_NOREPLACE
    if operation is None:
        raise OSError(errno.ENOTSUP, "atomic no-replace rename is unavailable")
    operation.argtypes = (
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    )
    operation.restype = ctypes.c_int
    if (
        operation(
            source_dir_fd,
            source_bytes,
            destination_dir_fd,
            destination_bytes,
            flags,
        )
        != 0
    ):
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number))


def _unlink_private_file_snapshot(
    path: Path, snapshot: PrivateFileSnapshot, *, label: str, max_bytes: int
) -> str:
    _assert_private_file_snapshot(path, snapshot, label=label, max_bytes=max_bytes)
    descriptor = directory_descriptor = -1
    quarantine_name = ""
    quarantined = False
    try:
        descriptor, directory_descriptor, parents = _open_private_path(
            path, label=label, max_bytes=max_bytes
        )
        metadata = os.fstat(descriptor)
        if (
            _file_identity(metadata) != snapshot.file_identity
            or tuple(identity[:5] for identity in parents) != snapshot.parent_identities
        ):
            raise ValueError(f"{label} is invalid")
        for _ in range(4):
            quarantine_name = f".{path.name}.qa-remove-{secrets.token_hex(16)}"
            try:
                _rename_noreplace(
                    path.name,
                    quarantine_name,
                    source_dir_fd=directory_descriptor,
                    destination_dir_fd=directory_descriptor,
                )
                quarantined = True
                break
            except OSError as exc:
                if exc.errno != errno.EEXIST:
                    raise
        if not quarantined:
            raise OSError(errno.EEXIST, "private quarantine name is unavailable")

        moved_metadata = os.stat(
            quarantine_name,
            dir_fd=directory_descriptor,
            follow_symlinks=False,
        )
        descriptor_metadata = os.fstat(descriptor)
        os.lseek(descriptor, 0, os.SEEK_SET)
        moved_raw, descriptor_identity = _read_private_descriptor(
            descriptor,
            label=label,
            max_bytes=max_bytes,
        )
        moved_identity = _file_identity(moved_metadata)
        is_exact_opened_identity = (
            moved_identity == _file_identity(descriptor_metadata)
            and descriptor_identity[:8] == snapshot.file_identity[:8]
            and moved_raw == snapshot.raw
            and "sha256:" + hashlib.sha256(moved_raw).hexdigest() == snapshot.digest
        )
        if not is_exact_opened_identity:
            outcome = "replacement_quarantined"
            try:
                _rename_noreplace(
                    quarantine_name,
                    path.name,
                    source_dir_fd=directory_descriptor,
                    destination_dir_fd=directory_descriptor,
                )
                quarantined = False
                outcome = "replacement_restored"
            except OSError:
                pass
            raise PrivateFileRemovalError(outcome)

        os.unlink(quarantine_name, dir_fd=directory_descriptor)
        quarantined = False
        return "deleted_exact"
    except PrivateFileRemovalError:
        raise
    except (OSError, RuntimeError, ValueError) as exc:
        if quarantined:
            raise PrivateFileRemovalError("identity_quarantined") from exc
        raise ValueError(f"{label} is invalid") from exc
    finally:
        for opened in (descriptor, directory_descriptor):
            if opened >= 0:
                try:
                    os.close(opened)
                except OSError:
                    pass


def _read_private_file(path: Path, *, label: str, max_bytes: int) -> bytes:
    """Read one owner-only regular file without following any path symlink."""
    return _read_private_file_snapshot(path, label=label, max_bytes=max_bytes).raw


def _read_private_json(
    path: Path, *, label: str, max_bytes: int
) -> tuple[bytes, object]:
    raw = _read_private_file(path, label=label, max_bytes=max_bytes)
    try:
        text = raw.decode("utf-8", errors="strict")
        payload = _loads_strict_json(text)
    except (UnicodeError, json.JSONDecodeError, DuplicateJsonKeyError) as exc:
        raise ValueError(f"{label} is invalid") from exc
    return raw, payload


def _file_digest(path: Path) -> str:
    raw, payload = _read_private_json(
        path,
        label="installed artifact identity",
        max_bytes=ARTIFACT_IDENTITY_MAX_BYTES,
    )
    if not isinstance(payload, dict):
        raise ValueError("installed artifact identity is invalid")  # noqa: TRY004
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _release_gate_module():
    path = Path(__file__).with_name("parallel_work_release_gate.py")
    spec = importlib.util.spec_from_file_location(
        "viventium_parallel_work_release_gate_for_local_qa",
        path,
    )
    if spec is None or spec.loader is None:
        raise ValueError("installed artifact identity is invalid")
    module = importlib.util.module_from_spec(spec)
    try:
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    except (ImportError, OSError, RuntimeError, ValueError) as exc:
        raise ValueError("installed artifact identity is invalid") from exc
    return module


def _service_ack_module():
    path = Path(__file__).with_name("local_qa_service_ack.py")
    spec = importlib.util.spec_from_file_location(
        "viventium_local_qa_service_ack_for_runtime_control",
        path,
    )
    if spec is None or spec.loader is None:
        raise ValueError("local-QA service acknowledgement is unavailable")
    module = importlib.util.module_from_spec(spec)
    try:
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    except (ImportError, OSError, RuntimeError, ValueError) as exc:
        raise ValueError("local-QA service acknowledgement is unavailable") from exc
    return module


def _artifact_digests(path: Path, installed_root: Path) -> tuple[str, str]:
    raw, payload = _read_private_json(
        path,
        label="installed artifact identity",
        max_bytes=ARTIFACT_IDENTITY_MAX_BYTES,
    )
    release_gate = _release_gate_module()
    source_keys = {"revision", "clean", "worktreeHash", "componentsLockSha256"}
    nested_keys = {"name", "pin", "revision", "clean", "worktreeHash"}
    prebuilt_keys = {
        "sourceDeclaredSha256",
        "sourceMeasuredSha256",
        "binaryDeclaredSha256",
        "binaryMeasuredSha256",
        "binaryExecutable",
    }
    installed_keys = {"rootRevision", *release_gate.INSTALLED_ARTIFACT_HASH_KEYS}
    readiness_keys = set(release_gate.READINESS_IDENTITY_HASH_KEYS)
    if (
        not isinstance(payload, dict)
        or set(payload)
        != {
            "contractVersion",
            "source",
            "nestedComponents",
            "prebuiltHelper",
            "installed",
            "readiness",
        }
        or not release_gate._artifact_identity_shape_valid(payload)
        or not isinstance(payload.get("source"), dict)
        or set(payload["source"]) != source_keys
        or not isinstance(payload.get("nestedComponents"), list)
        or any(
            not isinstance(item, dict) or set(item) != nested_keys
            for item in payload["nestedComponents"]
        )
        or not isinstance(payload.get("prebuiltHelper"), dict)
        or set(payload["prebuiltHelper"]) != prebuilt_keys
        or not isinstance(payload.get("installed"), dict)
        or set(payload["installed"]) != installed_keys
        or not isinstance(payload.get("readiness"), dict)
        or set(payload["readiness"]) != readiness_keys
    ):
        raise ValueError("installed artifact identity is invalid")
    measured_manifest, measured_running = (
        release_gate._runtime_service_artifact_digests(installed_root)
    )
    installed = payload["installed"]
    if (
        not SHA256_PATTERN.fullmatch(measured_manifest)
        or not SHA256_PATTERN.fullmatch(measured_running)
        or installed.get("runtimeServiceManifestSha256") != measured_manifest
        or installed.get("runningServiceSha256") != measured_running
    ):
        raise ValueError("installed artifact identity is invalid")
    return (
        "sha256:" + hashlib.sha256(raw).hexdigest(),
        "sha256:" + measured_running,
    )


def _require_local_qa_request(path: Path) -> None:
    try:
        _raw, payload = _read_private_json(
            path,
            label="explicit local-QA request",
            max_bytes=REQUEST_MAX_BYTES,
        )
    except ValueError as exc:
        raise ValueError("an explicit local-QA request is required") from exc
    if payload != {
        "contractVersion": CONTRACT_VERSION,
        "mode": "local-qa",
        "requested": True,
    }:
        raise ValueError("an explicit local-QA request is required")


def _validate_state_payload(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict) or set(payload) != STATE_FIELDS:
        raise ValueError("local-QA session state is invalid")
    if payload.get("contractVersion") != CONTRACT_VERSION:
        raise ValueError("local-QA session contract is unsupported")
    if not HASH_PATTERN.fullmatch(
        str(payload.get("artifactIdentityDigest") or "")
    ) or not HASH_PATTERN.fullmatch(str(payload.get("componentArtifactDigest") or "")):
        raise ValueError("local-QA session artifact identity is invalid")
    case_id = str(payload.get("caseId") or "")
    expected_mode = CASE_MODES.get(case_id)
    if (
        expected_mode is None
        or (payload.get("modeVariable"), payload.get("mode")) != expected_mode
    ):
        raise ValueError("local-QA session case is unsupported")
    token = str(payload.get("caseToken") or "")
    try:
        decoded = base64.urlsafe_b64decode(token + "=")
    except (ValueError, TypeError) as exc:
        raise ValueError("local-QA session token is invalid") from exc
    if (
        len(decoded) != TOKEN_BYTES
        or base64.urlsafe_b64encode(decoded).decode().rstrip("=") != token
    ):
        raise ValueError("local-QA session token is invalid")
    expected_ref = "qa_" + hashlib.sha256(token.encode()).hexdigest()[:24]
    if payload.get("sessionRef") != expected_ref:
        raise ValueError("local-QA session reference is invalid")
    started_at = _parse_time(payload.get("startedAt"))
    expires_at = _parse_time(payload.get("expiresAt"))
    if (
        payload.get("startedAt") != _iso(started_at)
        or payload.get("expiresAt") != _iso(expires_at)
        or expires_at <= started_at
    ):
        raise ValueError("local-QA session timestamp is invalid")
    return payload


def _read_state_snapshot(path: Path) -> tuple[PrivateFileSnapshot, dict[str, object]]:
    try:
        snapshot = _read_private_file_snapshot(
            path, label="local-QA session state", max_bytes=SESSION_STATE_MAX_BYTES
        )
        payload = _loads_strict_json(snapshot.raw.decode("utf-8", errors="strict"))
    except (
        UnicodeError,
        json.JSONDecodeError,
        DuplicateJsonKeyError,
        ValueError,
    ) as exc:
        raise ValueError("local-QA session state is invalid") from exc
    return snapshot, _validate_state_payload(payload)


def _read_state(path: Path) -> dict[str, object]:
    return _read_state_snapshot(path)[1]


def _write_private_json(path: Path, payload: dict[str, object]) -> None:
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


def _redacted(payload: dict[str, object]) -> dict[str, object]:
    return {
        "caseId": payload["caseId"],
        "expiresAt": payload["expiresAt"],
        "mode": payload["mode"],
        "sessionRef": payload["sessionRef"],
    }


def activate_session(
    *,
    state_path: Path,
    installed_root: Path,
    artifact_identity_path: Path,
    local_qa_request_path: Path,
    case_id: str,
    expires_in_seconds: int,
    now: datetime | None = None,
    token_bytes: Callable[[int], bytes] = secrets.token_bytes,
) -> dict[str, object]:
    mode = CASE_MODES.get(case_id)
    if mode is None:
        raise ValueError("local-QA case is not supported")
    if not isinstance(expires_in_seconds, int) or not (
        MIN_EXPIRY_SECONDS <= expires_in_seconds <= MAX_EXPIRY_SECONDS
    ):
        raise ValueError("local-QA session expiry is outside the allowed range")
    if state_path.exists() or state_path.is_symlink():
        raise ValueError("a local-QA session is already active")
    _require_local_qa_request(local_qa_request_path)
    started = (now or _utc_now()).astimezone(timezone.utc)
    started = started.replace(microsecond=(started.microsecond // 1000) * 1000)
    artifact_digest, component_digest = _artifact_digests(
        artifact_identity_path,
        installed_root,
    )
    raw_token = token_bytes(TOKEN_BYTES)
    if len(raw_token) != TOKEN_BYTES:
        raise ValueError("local-QA token source returned the wrong size")
    token = base64.urlsafe_b64encode(raw_token).decode().rstrip("=")
    payload: dict[str, object] = {
        "artifactIdentityDigest": artifact_digest,
        "caseId": case_id,
        "caseToken": token,
        "componentArtifactDigest": component_digest,
        "contractVersion": CONTRACT_VERSION,
        "expiresAt": _iso(started + timedelta(seconds=expires_in_seconds)),
        "installedRootHash": _root_hash(installed_root),
        "mode": mode[1],
        "modeVariable": mode[0],
        "sessionRef": "qa_" + hashlib.sha256(token.encode()).hexdigest()[:24],
        "startedAt": _iso(started),
    }
    _write_private_json(state_path, payload)
    return _redacted(payload)


def active_session(
    *,
    state_path: Path,
    installed_root: Path,
    artifact_identity_path: Path,
    local_qa_request_path: Path,
    now: datetime | None = None,
) -> dict[str, object]:
    payload = _read_state(state_path)
    checked_at = (now or _utc_now()).astimezone(timezone.utc)
    if checked_at >= _parse_time(payload["expiresAt"]):
        raise ValueError("local-QA session has expired")
    if payload["installedRootHash"] != _root_hash(installed_root):
        raise ValueError("local-QA session belongs to a different installed candidate")
    artifact_digest, component_digest = _artifact_digests(
        artifact_identity_path,
        installed_root,
    )
    if payload["artifactIdentityDigest"] != artifact_digest:
        raise ValueError("installed artifact identity changed after QA activation")
    if payload["componentArtifactDigest"] != component_digest:
        raise ValueError("installed component artifact changed after QA activation")
    _require_local_qa_request(local_qa_request_path)
    return payload


def emit_shell_exports(
    *,
    state_path: Path,
    installed_root: Path,
    artifact_identity_path: Path,
    local_qa_request_path: Path,
    now: datetime | None = None,
) -> str:
    payload = active_session(
        state_path=state_path,
        installed_root=installed_root,
        artifact_identity_path=artifact_identity_path,
        local_qa_request_path=local_qa_request_path,
        now=now,
    )
    installed_root = installed_root.expanduser().resolve(strict=True)
    helper = installed_root / "scripts" / "viventium" / "local_qa_service_ack.py"
    if helper.is_symlink() or not helper.is_file() or not os.access(helper, os.X_OK):
        raise ValueError("local-QA service acknowledgement is unavailable")
    values = {
        "VIVENTIUM_LOCAL_QA_CASE_ID": str(payload["caseId"]),
        "VIVENTIUM_LOCAL_QA_CASE_TOKEN": str(payload["caseToken"]),
        "VIVENTIUM_LOCAL_QA_COMPONENT_ARTIFACT_DIGEST": str(
            payload["componentArtifactDigest"]
        ),
        "VIVENTIUM_LOCAL_QA_SESSION_REF": str(payload["sessionRef"]),
        str(payload["modeVariable"]): str(payload["mode"]),
    }
    if payload["caseId"] in {"PWK-UC-016", "PWK-UC-017", "MPV-061"}:
        values["VIVENTIUM_LOCAL_QA_CANDIDATE_DIGEST"] = str(
            payload["artifactIdentityDigest"]
        )
    return "\n".join(
        f"export {name}={shlex.quote(value)}" for name, value in sorted(values.items())
    )


def clear_session(*, state_path: Path, session_ref: str) -> dict[str, object]:
    snapshot, payload = _read_state_snapshot(state_path)
    if session_ref != payload["sessionRef"]:
        raise ValueError("local-QA session reference did not match")
    _service_ack_module().clear_acknowledgements(
        state_path.parent / "acks", session_ref
    )
    _unlink_private_file_snapshot(
        state_path,
        snapshot,
        label="local-QA session state",
        max_bytes=SESSION_STATE_MAX_BYTES,
    )
    return {"cleared": True, "sessionRef": session_ref}


def session_restart_status(
    *,
    state_path: Path,
    installed_root: Path,
    artifact_identity_path: Path,
    local_qa_request_path: Path,
    now: datetime | None = None,
) -> dict[str, object]:
    """Return the exact live-service restart state for one active QA session."""

    payload = active_session(
        state_path=state_path,
        installed_root=installed_root,
        artifact_identity_path=artifact_identity_path,
        local_qa_request_path=local_qa_request_path,
        now=now,
    )
    return {
        **_redacted(payload),
        **_service_ack_module().restart_status(
            payload,
            ack_root=state_path.parent / "acks",
            now=now,
        ),
    }


def require_restart_ready(
    *,
    state_path: Path,
    installed_root: Path,
    artifact_identity_path: Path,
    local_qa_request_path: Path,
    now: datetime | None = None,
) -> dict[str, object]:
    """Fail closed until every case-required installed service has restarted."""

    result = session_restart_status(
        state_path=state_path,
        installed_root=installed_root,
        artifact_identity_path=artifact_identity_path,
        local_qa_request_path=local_qa_request_path,
        now=now,
    )
    if result["restartState"] != "ready":
        raise ValueError("service restart acknowledgement is incomplete")
    return result


def _json(value: object) -> None:
    print(json.dumps(value, sort_keys=True))


def main(argv: Iterable[str] | None = None) -> int:
    parser = PrivateArgumentParser(description=__doc__, allow_abbrev=False)
    subcommands = parser.add_subparsers(dest="command", required=True)

    activate = subcommands.add_parser("activate", allow_abbrev=False)
    activate.add_argument("--state", type=Path, required=True)
    activate.add_argument("--installed-root", type=Path, required=True)
    activate.add_argument("--artifact-identity", type=Path, required=True)
    activate.add_argument("--local-qa-request", type=Path, required=True)
    activate.add_argument("--case-id", choices=sorted(CASE_MODES), required=True)
    activate.add_argument("--expires-in-seconds", type=int, default=900)

    for command_name in ("status", "require-ready"):
        status = subcommands.add_parser(command_name, allow_abbrev=False)
        status.add_argument("--state", type=Path, required=True)
        status.add_argument("--installed-root", type=Path, required=True)
        status.add_argument("--artifact-identity", type=Path, required=True)
        status.add_argument("--local-qa-request", type=Path, required=True)

    emit = subcommands.add_parser("emit-shell", allow_abbrev=False)
    emit.add_argument("--state", type=Path, required=True)
    emit.add_argument("--installed-root", type=Path, required=True)
    emit.add_argument("--artifact-identity", type=Path, required=True)
    emit.add_argument("--local-qa-request", type=Path, required=True)

    clear = subcommands.add_parser("clear", allow_abbrev=False)
    clear.add_argument("--state", type=Path, required=True)
    clear.add_argument("--session-ref", required=True)

    values = list(argv) if argv is not None else sys.argv[1:]
    try:
        _reject_duplicate_options(values)
        args = parser.parse_args(values)
    except ValueError:
        print(json.dumps({"error": "operation_failed"}), file=sys.stderr)
        return 2
    try:
        if args.command == "activate":
            _json(
                activate_session(
                    state_path=args.state,
                    installed_root=args.installed_root,
                    artifact_identity_path=args.artifact_identity,
                    local_qa_request_path=args.local_qa_request,
                    case_id=args.case_id,
                    expires_in_seconds=args.expires_in_seconds,
                )
            )
        elif args.command in {"status", "require-ready"}:
            function = (
                require_restart_ready
                if args.command == "require-ready"
                else session_restart_status
            )
            result = function(
                state_path=args.state,
                installed_root=args.installed_root,
                artifact_identity_path=args.artifact_identity,
                local_qa_request_path=args.local_qa_request,
            )
            _json(result)
        elif args.command == "emit-shell":
            print(
                emit_shell_exports(
                    state_path=args.state,
                    installed_root=args.installed_root,
                    artifact_identity_path=args.artifact_identity,
                    local_qa_request_path=args.local_qa_request,
                )
            )
        else:
            _json(clear_session(state_path=args.state, session_ref=args.session_ref))
    except (OSError, RuntimeError, UnicodeError, ValueError):
        print(json.dumps({"error": "operation_failed"}), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

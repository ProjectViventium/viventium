#!/usr/bin/env python3
"""Transactional generated-runtime and binding state for local checkout promotion."""

from __future__ import annotations

import argparse
import ctypes
import errno
import hashlib
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import upgrade_transaction


SCHEMA_VERSION = 2
SUPPORTED_SCHEMA_VERSIONS = frozenset({1, SCHEMA_VERSION})
MANIFEST_NAME = "activation.json"
GIT_COMMIT = re.compile(r"[0-9a-f]{40,64}")
DARWIN_RENAME_EXCL = 0x00000004
LINUX_RENAME_NOREPLACE = 0x1
HELPER_INTENT_MUTATED_FIELDS = frozenset(
    {
        "activationTransactionId",
        "schemaVersion",
        "desiredState",
        "consecutiveLaunchAttempts",
        "nextLaunchAttemptAt",
        "healthySince",
    }
)


class ActivationError(RuntimeError):
    pass


def lexical(path: Path) -> Path:
    return Path(os.path.abspath(os.path.expanduser(str(path))))


def contained(path: Path, boundary: Path, label: str) -> Path:
    candidate = lexical(path)
    root = lexical(boundary)
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise ActivationError(f"{label} escapes its trusted boundary") from error
    return candidate


def validate_real_path_chain(
    path: Path,
    label: str,
    *,
    owned_from: Path | None = None,
) -> None:
    try:
        upgrade_transaction.validate_chain(path, owned_from=owned_from)
    except upgrade_transaction.UpgradeTransactionError as error:
        raise ActivationError(f"{label} path is unsafe: {error}") from error


def validate_private_directory(path: Path, boundary: Path, label: str) -> Path:
    target = contained(path, boundary, label)
    validate_real_path_chain(target, label, owned_from=lexical(boundary))
    metadata = target.lstat()
    if (
        target.is_symlink()
        or not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != os.getuid()
    ):
        raise ActivationError(f"{label} is not an owner-controlled directory")
    return target


def write_json(path: Path, payload: dict[str, Any], boundary: Path) -> None:
    target = contained(path, boundary, "activation manifest")
    validate_real_path_chain(
        target.parent,
        "activation manifest parent",
        owned_from=lexical(boundary),
    )
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=target.parent,
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(0o600)
        os.replace(temporary, target)
        target.chmod(0o600)
        directory_descriptor = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    finally:
        temporary.unlink(missing_ok=True)


def load_manifest(transaction_dir: Path, app_support_dir: Path) -> tuple[Path, dict[str, Any]]:
    transaction = validate_private_directory(
        transaction_dir,
        lexical(app_support_dir) / "state",
        "activation transaction",
    )
    manifest = transaction / MANIFEST_NAME
    metadata = manifest.lstat()
    if (
        manifest.is_symlink()
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
    ):
        raise ActivationError("Activation manifest is unsafe")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    if payload.get("schemaVersion") not in SUPPORTED_SCHEMA_VERSIONS:
        raise ActivationError("Activation manifest schema is unsupported")
    if lexical(Path(str(payload.get("appSupportDir") or ""))) != lexical(app_support_dir):
        raise ActivationError("Activation manifest belongs to another App Support root")
    return transaction, payload


def validated_runtime_path(payload: dict[str, Any], app_support_dir: Path) -> Path:
    app_support = lexical(app_support_dir)
    runtime = lexical(Path(str(payload.get("runtimeDir") or "")))
    if runtime != app_support / "runtime":
        raise ActivationError(
            "Activation runtime target is outside the canonical App Support runtime"
        )
    validate_real_path_chain(
        runtime,
        "generated runtime",
        owned_from=app_support,
    )
    return runtime


def safe_file_snapshot(
    path: Path,
    snapshot: Path,
    *,
    app_support_dir: Path,
) -> dict[str, Any]:
    target = contained(path, app_support_dir, "activation state file")
    if not target.exists() and not target.is_symlink():
        return {"path": str(target), "existed": False}
    metadata = target.lstat()
    if (
        target.is_symlink()
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
    ):
        raise ActivationError("Activation state file is unsafe")
    shutil.copy2(target, snapshot)
    snapshot.chmod(0o600)
    return {
        "path": str(target),
        "existed": True,
        "snapshot": str(snapshot),
        "mode": stat.S_IMODE(metadata.st_mode),
        "size": metadata.st_size,
        "sha256": sha256_file(snapshot),
    }


def open_candidate_librechat_directory(repo: Path) -> tuple[Path, int, os.stat_result]:
    candidate_repo = lexical(repo)
    directory_flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    descriptors: list[int] = []
    try:
        descriptor = os.open(candidate_repo, directory_flags)
        descriptors.append(descriptor)
        metadata = os.fstat(descriptor)
        if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.getuid():
            raise ActivationError("Candidate checkout is not an owner-controlled directory")
        for component, label in (
            ("viventium_v0_4", "candidate product directory"),
            ("LibreChat", "candidate LibreChat directory"),
        ):
            child = os.open(component, directory_flags, dir_fd=descriptor)
            descriptors.append(child)
            child_metadata = os.fstat(child)
            if (
                not stat.S_ISDIR(child_metadata.st_mode)
                or child_metadata.st_uid != os.getuid()
            ):
                raise ActivationError(f"{label} is not an owner-controlled directory")
            descriptor = child
        librechat_descriptor = descriptors.pop()
        return candidate_repo, librechat_descriptor, os.fstat(librechat_descriptor)
    except OSError as error:
        raise ActivationError("Candidate LibreChat directory could not be opened safely") from error
    finally:
        for descriptor in descriptors:
            os.close(descriptor)


def candidate_env_metadata(directory_descriptor: int) -> os.stat_result | None:
    try:
        return os.stat(".env", dir_fd=directory_descriptor, follow_symlinks=False)
    except FileNotFoundError:
        return None
    except OSError as error:
        raise ActivationError(
            "Candidate LibreChat environment could not be inspected safely"
        ) from error


def safe_candidate_env_snapshot(
    repo: Path,
    snapshot: Path,
) -> dict[str, Any]:
    candidate_repo, directory_descriptor, parent_metadata = (
        open_candidate_librechat_directory(repo)
    )
    record: dict[str, Any] = {
        "repoRoot": str(candidate_repo),
        "relativePath": "viventium_v0_4/LibreChat/.env",
        "parentDevice": parent_metadata.st_dev,
        "parentInode": parent_metadata.st_ino,
        "rollbackQuarantineName": (
            f".env.viventium-rollback-"
            f"{hashlib.sha256(str(snapshot.parent.parent).encode('utf-8')).hexdigest()[:20]}"
        ),
        "commitAcceptanceName": (
            f".env.viventium-accepted-"
            f"{hashlib.sha256(str(snapshot.parent.parent).encode('utf-8')).hexdigest()[:20]}"
        ),
        "rollbackCleanupName": (
            f".env.viventium-cleanup-"
            f"{hashlib.sha256(str(snapshot.parent.parent).encode('utf-8')).hexdigest()[:20]}"
        ),
        "materializationClaimDirectoryName": (
            f".env.viventium-private-"
            f"{hashlib.sha256(str(snapshot.parent.parent).encode('utf-8')).hexdigest()[:20]}"
        ),
        "materializationRetirementName": ".env.viventium-retired-mat",
        "ownerEnvRetirementName": ".env.viventium-retired-env",
        "retirementTombstoneName": ".env.viventium-retired-zero",
        "existed": False,
    }
    try:
        legacy_retirement_names = discover_legacy_owner_env_retirement_slots(
            directory_descriptor,
        )
        stale_prefixes = (
            ".env.viventium-materialize-",
            ".env.viventium-materialized-",
            ".env.viventium-rollback-",
            ".env.viventium-accepted-",
            ".env.viventium-restore-",
            ".env.viventium-cleanup-",
            ".env.viventium-private-",
            ".env.viventium-retired-",
        )
        tolerated_retirement_names = {
            record["materializationRetirementName"],
            record["ownerEnvRetirementName"],
            record["retirementTombstoneName"],
            *legacy_retirement_names,
        }
        canonical_retirement_names = {
            record["materializationRetirementName"],
            record["ownerEnvRetirementName"],
            record["retirementTombstoneName"],
        }
        for name in os.listdir(directory_descriptor):
            if name in tolerated_retirement_names:
                descriptor = os.open(
                    name,
                    os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
                    dir_fd=directory_descriptor,
                )
                try:
                    metadata = os.fstat(descriptor)
                    if (
                        not stat.S_ISREG(metadata.st_mode)
                        or metadata.st_uid != os.getuid()
                    ):
                        raise ActivationError(
                            "Candidate LibreChat retirement state is unsafe"
                        )
                    if (
                        name in canonical_retirement_names
                        and (
                            metadata.st_size != 0
                            or metadata.st_nlink != 1
                        )
                    ):
                        raise ActivationError(
                            "Candidate LibreChat retirement state is unsafe"
                        )
                finally:
                    os.close(descriptor)
                continue
            if name.startswith(stale_prefixes):
                raise ActivationError(
                    "Candidate LibreChat directory contains stale activation state"
                )
        for transaction_name in (
            record["rollbackQuarantineName"],
            record["commitAcceptanceName"],
        ):
            try:
                os.stat(
                    transaction_name,
                    dir_fd=directory_descriptor,
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                continue
            raise ActivationError(
                "Candidate LibreChat directory contains stale activation state"
            )
        target_metadata = candidate_env_metadata(directory_descriptor)
        if target_metadata is None:
            return record
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(".env", flags, dir_fd=directory_descriptor)
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid():
            raise ActivationError(
                "Candidate LibreChat environment is not an owner-controlled regular file"
            )
        try:
            output = os.open(
                snapshot,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
            try:
                with os.fdopen(descriptor, "rb", closefd=False) as source:
                    with os.fdopen(output, "wb", closefd=False) as destination:
                        shutil.copyfileobj(source, destination)
                        destination.flush()
                        os.fsync(destination.fileno())
            finally:
                os.close(output)
            after = os.fstat(descriptor)
            if (
                metadata.st_dev != after.st_dev
                or metadata.st_ino != after.st_ino
                or metadata.st_size != after.st_size
                or metadata.st_mtime_ns != after.st_mtime_ns
                or metadata.st_ctime_ns != after.st_ctime_ns
                or snapshot.stat().st_size != after.st_size
            ):
                snapshot.unlink(missing_ok=True)
                raise ActivationError(
                    "Candidate LibreChat environment changed while it was checkpointed"
                )
            snapshot.chmod(0o600)
            snapshots_descriptor = os.open(snapshot.parent, os.O_RDONLY)
            try:
                os.fsync(snapshots_descriptor)
            finally:
                os.close(snapshots_descriptor)
            record.update(
                {
                    "existed": True,
                    "snapshot": str(snapshot),
                    "mode": stat.S_IMODE(after.st_mode),
                    "size": after.st_size,
                    "sha256": sha256_file(snapshot),
                }
            )
            return record
        finally:
            os.close(descriptor)
    finally:
        os.close(directory_descriptor)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    finally:
        os.close(descriptor)
    return digest.hexdigest()


def safe_runtime_precondition(
    path: Path,
    *,
    app_support_dir: Path,
) -> dict[str, Any]:
    runtime = contained(path, app_support_dir, "generated runtime")
    validate_real_path_chain(
        runtime,
        "generated runtime",
        owned_from=lexical(app_support_dir),
    )
    if not runtime.exists() and not runtime.is_symlink():
        return {"existed": False}
    metadata = runtime.lstat()
    if (
        runtime.is_symlink()
        or not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != os.getuid()
    ):
        raise ActivationError("Generated runtime is not an owner-controlled directory")
    return {
        "existed": True,
        "device": metadata.st_dev,
        "inode": metadata.st_ino,
        # Generated runtime components may contain ordinary Python virtualenv
        # interpreter links. The manifest records links without following them,
        # and activation moves the entire owner-controlled runtime directory by
        # identity, so preserving those link entries does not expose their targets.
        "surfaceManifest": upgrade_transaction.surface_manifest(
            runtime,
            allow_symlinks=True,
        ),
    }


def owned_directory_identity(path: Path, label: str) -> dict[str, int] | None:
    if not path.exists() and not path.is_symlink():
        return None
    metadata = path.lstat()
    if (
        path.is_symlink()
        or not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != os.getuid()
    ):
        raise ActivationError(f"{label} is not an owner-controlled directory")
    return {"device": metadata.st_dev, "inode": metadata.st_ino}


def identity_matches(
    actual: dict[str, int] | None,
    expected: dict[str, Any] | None,
) -> bool:
    return (
        actual is not None
        and isinstance(expected, dict)
        and actual.get("device") == expected.get("device")
        and actual.get("inode") == expected.get("inode")
    )


def validate_runtime_precondition(
    runtime: Path,
    proof: dict[str, Any],
) -> None:
    identity = owned_directory_identity(runtime, "generated runtime")
    if proof.get("existed"):
        if not identity_matches(identity, proof):
            raise ActivationError("Generated runtime changed after activation checkpoint")
        if upgrade_transaction.surface_manifest(
            runtime,
            allow_symlinks=True,
        ) != proof.get("surfaceManifest"):
            raise ActivationError("Generated runtime changed after activation checkpoint")
    elif identity is not None:
        raise ActivationError("Generated runtime appeared after activation checkpoint")


def validate_state_file_snapshot(
    record: dict[str, Any],
    transaction: Path,
    app_support_dir: Path,
) -> None:
    contained(
        Path(str(record.get("path") or "")),
        app_support_dir,
        "activation state file",
    )
    if not record.get("existed"):
        return
    snapshot = contained(
        Path(str(record.get("snapshot") or "")),
        transaction,
        "activation state snapshot",
    )
    metadata = snapshot.lstat()
    if (
        snapshot.is_symlink()
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or metadata.st_size != record.get("size")
        or sha256_file(snapshot) != record.get("sha256")
    ):
        raise ActivationError("Activation state snapshot is unsafe")


def validate_legacy_state_file_snapshot(
    record: dict[str, Any],
    transaction: Path,
    app_support_dir: Path,
) -> None:
    contained(
        Path(str(record.get("path") or "")),
        app_support_dir,
        "activation state file",
    )
    if not record.get("existed"):
        return
    snapshot = contained(
        Path(str(record.get("snapshot") or "")),
        transaction,
        "activation state snapshot",
    )
    metadata = snapshot.lstat()
    if (
        snapshot.is_symlink()
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
    ):
        raise ActivationError("Legacy activation state snapshot is unsafe")


def validate_state_file_target(
    record: dict[str, Any],
    app_support_dir: Path,
) -> None:
    target = contained(
        Path(str(record.get("path") or "")),
        app_support_dir,
        "activation state file",
    )
    if not target.exists() and not target.is_symlink():
        return
    metadata = target.lstat()
    if (
        target.is_symlink()
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
    ):
        raise ActivationError("Activation state target is unsafe")


def validate_candidate_env_checkpoint(
    record: dict[str, Any],
    transaction: Path,
) -> tuple[int, Path | None]:
    if record.get("relativePath") != "viventium_v0_4/LibreChat/.env":
        raise ActivationError("Candidate LibreChat checkpoint path is invalid")
    _, directory_descriptor, parent_metadata = open_candidate_librechat_directory(
        Path(str(record.get("repoRoot") or ""))
    )
    if (
        record.get("parentDevice") != parent_metadata.st_dev
        or record.get("parentInode") != parent_metadata.st_ino
    ):
        os.close(directory_descriptor)
        raise ActivationError("Candidate LibreChat directory identity changed")
    snapshot: Path | None = None
    if record.get("existed"):
        snapshot = contained(
            Path(str(record.get("snapshot") or "")),
            transaction,
            "candidate LibreChat environment snapshot",
        )
        metadata = snapshot.lstat()
        if (
            snapshot.is_symlink()
            or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or metadata.st_size != record.get("size")
            or sha256_file(snapshot) != record.get("sha256")
        ):
            os.close(directory_descriptor)
            raise ActivationError("Candidate LibreChat environment snapshot is unsafe")
    return directory_descriptor, snapshot


def candidate_env_name(record: dict[str, Any], field: str, prefix: str) -> str:
    value = record.get(field)
    if (
        not isinstance(value, str)
        or not value.startswith(prefix)
        or "/" in value
        or value in {".", ".."}
    ):
        raise ActivationError("Candidate LibreChat transaction filename is invalid")
    return value


def candidate_env_retirement_name(
    record: dict[str, Any],
    field: str,
    family: str,
) -> str:
    expected = f".env.viventium-retired-{family}"
    value = record.get(field, expected)
    if not isinstance(value, str) or re.fullmatch(
        rf"{re.escape(expected)}(?:-[0-9a-f]{{20}})?",
        value,
    ) is None:
        raise ActivationError("Candidate LibreChat retirement filename is invalid")
    return value


def descriptor_contents(descriptor: int) -> tuple[bytes, os.stat_result]:
    before = os.fstat(descriptor)
    if (
        not stat.S_ISREG(before.st_mode)
        or before.st_uid != os.getuid()
    ):
        raise ActivationError(
            "Candidate LibreChat owner artifact is not a private regular file"
        )
    os.lseek(descriptor, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    while True:
        chunk = os.read(descriptor, 1024 * 1024)
        if not chunk:
            break
        chunks.append(chunk)
    contents = b"".join(chunks)
    after = os.fstat(descriptor)
    if (
        before.st_dev != after.st_dev
        or before.st_ino != after.st_ino
        or before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or before.st_ctime_ns != after.st_ctime_ns
        or len(contents) != after.st_size
    ):
        raise ActivationError(
            "Candidate LibreChat owner artifact changed while it was inspected"
        )
    return contents, after


def artifact_matches_receipt(
    metadata: os.stat_result,
    contents: bytes,
    receipt: dict[str, Any],
) -> bool:
    return (
        metadata.st_dev == receipt.get("device")
        and metadata.st_ino == receipt.get("inode")
        and len(contents) == receipt.get("size")
        and hashlib.sha256(contents).hexdigest() == receipt.get("sha256")
    )


def ensure_retirement_tombstone(
    directory_descriptor: int,
    tombstone_name: str,
) -> None:
    flags = os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(
            tombstone_name,
            flags,
            0o600,
            dir_fd=directory_descriptor,
        )
    except FileExistsError:
        descriptor = os.open(
            tombstone_name,
            os.O_RDWR | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=directory_descriptor,
        )
    try:
        contents, metadata = descriptor_contents(descriptor)
        if metadata.st_nlink != 1:
            raise ActivationError(
                "Candidate LibreChat retirement tombstone is unexpectedly linked"
            )
        if contents:
            os.ftruncate(descriptor, 0)
            os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.fsync(directory_descriptor)


def replace_retirement_slot_with_tombstone(
    directory_descriptor: int,
    retirement_name: str,
    tombstone_name: str,
    *,
    expected_device: int,
    expected_inode: int,
) -> None:
    descriptor = os.open(
        retirement_name,
        os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
        dir_fd=directory_descriptor,
    )
    try:
        _, metadata = descriptor_contents(descriptor)
        if (
            metadata.st_dev != expected_device
            or metadata.st_ino != expected_inode
        ):
            raise ActivationError(
                "Candidate LibreChat retirement slot changed before neutralization"
            )
    finally:
        os.close(descriptor)
    ensure_retirement_tombstone(directory_descriptor, tombstone_name)
    os.replace(
        tombstone_name,
        retirement_name,
        src_dir_fd=directory_descriptor,
        dst_dir_fd=directory_descriptor,
    )
    os.fsync(directory_descriptor)
    ensure_retirement_tombstone(directory_descriptor, tombstone_name)


def normalize_owner_env_retirement_slots(
    directory_descriptor: int,
    record: dict[str, Any],
    *,
    additional_retirement_names: tuple[str, ...] = (),
) -> None:
    """Leave only zero-byte, single-link retirement files.

    A transaction can temporarily hold the same owner inode through accepted
    and materialized links. Drop aliases while live ``.env`` still owns the
    inode, collapse duplicate retirement aliases, then descriptor-zero the one
    detached link that remains.
    """

    retirement_names = (
        candidate_env_retirement_name(
            record,
            "materializationRetirementName",
            "mat",
        ),
        candidate_env_retirement_name(
            record,
            "ownerEnvRetirementName",
            "env",
        ),
    ) + additional_retirement_names
    tombstone_name = candidate_env_retirement_name(
        record,
        "retirementTombstoneName",
        "zero",
    )

    def slot_metadata(name: str) -> os.stat_result | None:
        try:
            descriptor = os.open(
                name,
                os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=directory_descriptor,
            )
        except FileNotFoundError:
            return None
        try:
            _, metadata = descriptor_contents(descriptor)
            return metadata
        finally:
            os.close(descriptor)

    try:
        live_metadata = os.stat(
            ".env",
            dir_fd=directory_descriptor,
            follow_symlinks=False,
        )
    except FileNotFoundError:
        live_metadata = None
    for name in retirement_names:
        metadata = slot_metadata(name)
        if (
            metadata is not None
            and live_metadata is not None
            and metadata.st_dev == live_metadata.st_dev
            and metadata.st_ino == live_metadata.st_ino
        ):
            replace_retirement_slot_with_tombstone(
                directory_descriptor,
                name,
                tombstone_name,
                expected_device=metadata.st_dev,
                expected_inode=metadata.st_ino,
            )

    groups: dict[tuple[int, int], list[str]] = {}
    for name in retirement_names:
        metadata = slot_metadata(name)
        if metadata is not None:
            groups.setdefault(
                (metadata.st_dev, metadata.st_ino),
                [],
            ).append(name)
    for (device, inode), names in groups.items():
        for duplicate_name in names[1:]:
            replace_retirement_slot_with_tombstone(
                directory_descriptor,
                duplicate_name,
                tombstone_name,
                expected_device=device,
                expected_inode=inode,
            )

    for name in retirement_names:
        try:
            descriptor = os.open(
                name,
                os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=directory_descriptor,
            )
        except FileNotFoundError:
            continue
        try:
            _, metadata = descriptor_contents(descriptor)
            if metadata.st_nlink != 1:
                raise ActivationError(
                    "Candidate LibreChat retirement slot is unexpectedly linked"
                )
            zero_detached_owner_artifact(
                directory_descriptor,
                name,
                descriptor,
                metadata,
            )
        finally:
            os.close(descriptor)
    ensure_retirement_tombstone(directory_descriptor, tombstone_name)
    os.fsync(directory_descriptor)


def discover_legacy_owner_env_retirement_slots(
    directory_descriptor: int,
) -> tuple[str, ...]:
    legacy_pattern = re.compile(
        r"\.env\.viventium-retired-(mat|env|zero)-[0-9a-f]{20}"
    )
    legacy_by_family: dict[str, str] = {}
    for name in os.listdir(directory_descriptor):
        match = legacy_pattern.fullmatch(name)
        if match is None:
            continue
        family = match.group(1)
        if family in legacy_by_family:
            raise ActivationError(
                "Candidate LibreChat directory contains ambiguous legacy retirement state"
            )
        descriptor = os.open(
            name,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=directory_descriptor,
        )
        try:
            contents, metadata = descriptor_contents(descriptor)
            if (
                metadata.st_uid != os.getuid()
                or (
                    family == "zero"
                    and contents
                )
            ):
                raise ActivationError(
                    "Candidate LibreChat legacy retirement state is unsafe"
                )
        finally:
            os.close(descriptor)
        legacy_by_family[family] = name
    return tuple(
        legacy_by_family[family]
        for family in ("mat", "env", "zero")
        if family in legacy_by_family
    )


def migrate_legacy_owner_env_retirement_slots(
    directory_descriptor: int,
    record: dict[str, Any],
) -> None:
    legacy_names = discover_legacy_owner_env_retirement_slots(
        directory_descriptor,
    )
    legacy_by_family = {
        name.removeprefix(".env.viventium-retired-").split("-", 1)[0]: name
        for name in legacy_names
    }
    if not legacy_by_family:
        return
    primary_names = {
        candidate_env_retirement_name(
            record,
            "materializationRetirementName",
            "mat",
        ),
        candidate_env_retirement_name(
            record,
            "ownerEnvRetirementName",
            "env",
        ),
    }
    normalize_owner_env_retirement_slots(
        directory_descriptor,
        record,
        additional_retirement_names=tuple(
            name for name in legacy_names if name not in primary_names
        ),
    )
    target_by_family = {
        "mat": candidate_env_retirement_name(
            record,
            "materializationRetirementName",
            "mat",
        ),
        "env": candidate_env_retirement_name(
            record,
            "ownerEnvRetirementName",
            "env",
        ),
        "zero": candidate_env_retirement_name(
            record,
            "retirementTombstoneName",
            "zero",
        ),
    }
    for family in ("mat", "env", "zero"):
        legacy_name = legacy_by_family.get(family)
        if legacy_name is None:
            continue
        source_descriptor = os.open(
            legacy_name,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=directory_descriptor,
        )
        try:
            contents, metadata = descriptor_contents(source_descriptor)
            if contents or metadata.st_nlink != 1:
                raise ActivationError(
                    "Candidate LibreChat legacy retirement state is unsafe"
                )
        finally:
            os.close(source_descriptor)
        os.replace(
            legacy_name,
            target_by_family[family],
            src_dir_fd=directory_descriptor,
            dst_dir_fd=directory_descriptor,
        )
        os.fsync(directory_descriptor)
    normalize_owner_env_retirement_slots(
        directory_descriptor,
        record,
    )


def normalize_candidate_env_retirement(
    record: dict[str, Any],
    transaction: Path,
    *,
    migrate_legacy: bool = False,
) -> None:
    directory_descriptor, _ = validate_candidate_env_checkpoint(record, transaction)
    try:
        if migrate_legacy:
            migrate_legacy_owner_env_retirement_slots(
                directory_descriptor,
                record,
            )
        normalize_owner_env_retirement_slots(
            directory_descriptor,
            record,
        )
    finally:
        os.close(directory_descriptor)


def zero_detached_owner_artifact(
    directory_descriptor: int,
    name: str,
    descriptor: int,
    metadata: os.stat_result,
) -> None:
    if metadata.st_nlink != 1:
        return
    original_mode = stat.S_IMODE(metadata.st_mode)
    mode_changed = not bool(original_mode & stat.S_IWUSR)
    if mode_changed:
        os.fchmod(descriptor, original_mode | stat.S_IWUSR)
    writable_descriptor: int | None = None
    try:
        writable_descriptor = os.open(
            name,
            os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=directory_descriptor,
        )
        writable_metadata = os.fstat(writable_descriptor)
        if (
            writable_metadata.st_dev != metadata.st_dev
            or writable_metadata.st_ino != metadata.st_ino
        ):
            raise ActivationError(
                "Candidate LibreChat owner artifact changed before retirement"
            )
        os.ftruncate(writable_descriptor, 0)
        os.fsync(writable_descriptor)
    finally:
        if writable_descriptor is not None:
            os.close(writable_descriptor)
        if mode_changed:
            os.fchmod(descriptor, original_mode)


def retire_owner_env_artifact(
    source_directory_descriptor: int,
    source_name: str,
    candidate_directory_descriptor: int,
    retirement_name: str,
    tombstone_name: str,
    *,
    receipt: dict[str, Any] | None = None,
    allow_missing: bool = False,
) -> bool:
    """Move an owner-environment artifact to a bounded terminal slot.

    Owner data is never removed by pathname. A detached inode is zeroed through
    its already-open descriptor, then the source entry is moved. If another
    writer swaps the source before that move, its replacement is moved rather
    than deleted and the post-move identity check fails closed.
    """

    if (
        "/" in source_name
        or source_name in {"", ".", ".."}
        or not retirement_name.startswith(".env.viventium-retired-")
        or not tombstone_name.startswith(".env.viventium-retired-zero")
    ):
        raise ActivationError("Candidate LibreChat retirement path is invalid")
    try:
        source_descriptor = os.open(
            source_name,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=source_directory_descriptor,
        )
    except FileNotFoundError:
        if receipt is not None:
            try:
                retired_descriptor = os.open(
                    retirement_name,
                    os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
                    dir_fd=candidate_directory_descriptor,
                )
            except FileNotFoundError:
                if allow_missing:
                    return False
                raise ActivationError(
                    "Candidate LibreChat owner artifact disappeared before retirement"
                )
            try:
                retired_metadata = os.fstat(retired_descriptor)
                if (
                    retired_metadata.st_dev == receipt.get("device")
                    and retired_metadata.st_ino == receipt.get("inode")
                ):
                    return True
                if (
                    stat.S_ISREG(retired_metadata.st_mode)
                    and retired_metadata.st_uid == os.getuid()
                    and retired_metadata.st_nlink == 1
                    and retired_metadata.st_size == 0
                ):
                    return True
                raise ActivationError(
                    "Candidate LibreChat retirement slot conflicts with the receipt"
                )
            finally:
                os.close(retired_descriptor)
        if allow_missing:
            return False
        raise ActivationError(
            "Candidate LibreChat owner artifact disappeared before retirement"
        )
    try:
        contents, metadata = descriptor_contents(source_descriptor)
        if receipt is not None:
            identity_matches_receipt = (
                metadata.st_dev == receipt.get("device")
                and metadata.st_ino == receipt.get("inode")
            )
            exact_receipt = artifact_matches_receipt(
                metadata,
                contents,
                receipt,
            )
            zeroed_after_receipt = (
                identity_matches_receipt
                and metadata.st_nlink == 1
                and contents == b""
                and receipt.get("size") != 0
            )
            if not exact_receipt and not zeroed_after_receipt:
                raise ActivationError(
                    "Candidate LibreChat owner artifact receipt changed"
                )
        zero_detached_owner_artifact(
            source_directory_descriptor,
            source_name,
            source_descriptor,
            metadata,
        )
        expected_device = metadata.st_dev
        expected_inode = metadata.st_ino

        ensure_retirement_tombstone(
            candidate_directory_descriptor,
            tombstone_name,
        )
        try:
            retired_descriptor = os.open(
                retirement_name,
                os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=candidate_directory_descriptor,
            )
        except FileNotFoundError:
            retired_descriptor = None
        if retired_descriptor is not None:
            try:
                _, retired_metadata = descriptor_contents(retired_descriptor)
                zero_detached_owner_artifact(
                    candidate_directory_descriptor,
                    retirement_name,
                    retired_descriptor,
                    retired_metadata,
                )
            finally:
                os.close(retired_descriptor)
        os.replace(
            tombstone_name,
            retirement_name,
            src_dir_fd=candidate_directory_descriptor,
            dst_dir_fd=candidate_directory_descriptor,
        )
        os.fsync(candidate_directory_descriptor)
        os.rename(
            source_name,
            retirement_name,
            src_dir_fd=source_directory_descriptor,
            dst_dir_fd=candidate_directory_descriptor,
        )
        os.fsync(source_directory_descriptor)
        if source_directory_descriptor != candidate_directory_descriptor:
            os.fsync(candidate_directory_descriptor)
        moved_descriptor = os.open(
            retirement_name,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=candidate_directory_descriptor,
        )
        try:
            moved_metadata = os.fstat(moved_descriptor)
        finally:
            os.close(moved_descriptor)
        if (
            moved_metadata.st_dev != expected_device
            or moved_metadata.st_ino != expected_inode
        ):
            try:
                atomic_rename_no_replace_between(
                    candidate_directory_descriptor,
                    retirement_name,
                    source_directory_descriptor,
                    source_name,
                )
                os.fsync(source_directory_descriptor)
                os.fsync(candidate_directory_descriptor)
            except (FileExistsError, FileNotFoundError):
                pass
            raise ActivationError(
                "Candidate LibreChat owner artifact changed during retirement"
            )
        try:
            live_metadata = os.stat(
                ".env",
                dir_fd=candidate_directory_descriptor,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            live_metadata = None
        if (
            live_metadata is not None
            and live_metadata.st_dev == expected_device
            and live_metadata.st_ino == expected_inode
        ):
            replace_retirement_slot_with_tombstone(
                candidate_directory_descriptor,
                retirement_name,
                tombstone_name,
                expected_device=expected_device,
                expected_inode=expected_inode,
            )
            return True
        ensure_retirement_tombstone(
            candidate_directory_descriptor,
            tombstone_name,
        )
        return True
    finally:
        os.close(source_descriptor)


def atomic_rename_no_replace_between(
    source_directory_descriptor: int,
    source_name: str,
    destination_directory_descriptor: int,
    destination_name: str,
) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    source = os.fsencode(source_name)
    destination = os.fsencode(destination_name)
    if sys.platform == "darwin":
        rename = getattr(libc, "renameatx_np", None)
        if rename is None:
            raise ActivationError(
                "Atomic no-replace owner-environment cleanup is unavailable"
            )
        rename.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        rename.restype = ctypes.c_int
        result = rename(
            source_directory_descriptor,
            source,
            destination_directory_descriptor,
            destination,
            DARWIN_RENAME_EXCL,
        )
    elif sys.platform.startswith("linux"):
        rename = getattr(libc, "renameat2", None)
        if rename is None:
            raise ActivationError(
                "Atomic no-replace owner-environment cleanup is unavailable"
            )
        rename.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        rename.restype = ctypes.c_int
        result = rename(
            source_directory_descriptor,
            source,
            destination_directory_descriptor,
            destination,
            LINUX_RENAME_NOREPLACE,
        )
    else:
        raise ActivationError(
            "Atomic no-replace owner-environment cleanup is unavailable"
        )
    if result == 0:
        return
    error_number = ctypes.get_errno()
    if error_number == errno.EEXIST:
        raise FileExistsError(error_number, os.strerror(error_number), destination_name)
    if error_number == errno.ENOENT:
        raise FileNotFoundError(error_number, os.strerror(error_number), source_name)
    if error_number in {errno.ENOSYS, errno.EINVAL, errno.ENOTSUP}:
        raise ActivationError(
            "Atomic no-replace owner-environment cleanup is unavailable"
        )
    raise OSError(error_number, os.strerror(error_number), source_name)


def atomic_rename_no_replace_at(
    directory_descriptor: int,
    source_name: str,
    destination_name: str,
) -> None:
    atomic_rename_no_replace_between(
        directory_descriptor,
        source_name,
        directory_descriptor,
        destination_name,
    )


def current_candidate_env_bytes(
    directory_descriptor: int,
    name: str = ".env",
) -> bytes | None:
    try:
        metadata = os.stat(
            name,
            dir_fd=directory_descriptor,
            follow_symlinks=False,
        )
    except FileNotFoundError:
        return None
    except OSError as error:
        raise ActivationError(
            "Candidate LibreChat environment could not be inspected safely"
        ) from error
    descriptor = os.open(
        name,
        os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
        dir_fd=directory_descriptor,
    )
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid():
            raise ActivationError(
                "Candidate LibreChat environment is not an owner-controlled regular file"
            )
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            contents = handle.read()
        after = os.fstat(descriptor)
        if (
            before.st_dev != after.st_dev
            or before.st_ino != after.st_ino
            or before.st_size != after.st_size
            or before.st_mtime_ns != after.st_mtime_ns
            or before.st_ctime_ns != after.st_ctime_ns
            or len(contents) != after.st_size
        ):
            raise ActivationError(
                "Candidate LibreChat environment changed while rollback inspected it"
            )
        return contents
    finally:
        os.close(descriptor)


def candidate_env_contents_allowed(
    contents: bytes,
    record: dict[str, Any],
    payload: dict[str, Any],
) -> bool:
    if (
        record.get("existed")
        and hashlib.sha256(contents).hexdigest() == record.get("sha256")
    ):
        return True
    plan = payload.get("ownerEnvPlan")
    if not isinstance(plan, dict) or not isinstance(
        plan.get("semanticManifest"),
        dict,
    ):
        return False
    current = upgrade_transaction.librechat_env_semantic_manifest_from_bytes(contents)
    planned = plan["semanticManifest"]
    for field in ("protected_fields", "owner_secret_fields", "unmanaged_fields"):
        if current.get(field) != planned.get(field):
            return False
    return True


def _restore_quarantine_without_overwrite(
    directory_descriptor: int,
    quarantine_name: str,
    retirement_name: str,
    tombstone_name: str,
) -> None:
    if current_candidate_env_bytes(directory_descriptor) is not None:
        raise ActivationError(
            "Concurrent candidate LibreChat owner state appeared during rollback"
        )
    try:
        os.link(
            quarantine_name,
            ".env",
            src_dir_fd=directory_descriptor,
            dst_dir_fd=directory_descriptor,
            follow_symlinks=False,
        )
    except FileExistsError as error:
        raise ActivationError(
            "Concurrent candidate LibreChat owner state appeared during rollback"
        ) from error
    retire_owner_env_artifact(
        directory_descriptor,
        quarantine_name,
        directory_descriptor,
        retirement_name,
        tombstone_name,
    )
    os.fsync(directory_descriptor)


def _retire_transaction_env_artifact(
    directory_descriptor: int,
    name: str,
    retirement_name: str,
    tombstone_name: str,
    *,
    receipt: dict[str, Any] | None = None,
) -> None:
    retire_owner_env_artifact(
        directory_descriptor,
        name,
        directory_descriptor,
        retirement_name,
        tombstone_name,
        receipt=receipt,
        allow_missing=receipt is None,
    )
    os.fsync(directory_descriptor)


def _install_snapshot_without_overwrite(
    directory_descriptor: int,
    snapshot: Path,
    mode: int,
    retirement_name: str,
    tombstone_name: str,
) -> None:
    temporary_name = f".env.viventium-restore-{uuid.uuid4().hex}"
    source_descriptor = os.open(
        snapshot,
        os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
    )
    temporary_descriptor = os.open(
        temporary_name,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
        dir_fd=directory_descriptor,
    )
    try:
        os.fchmod(temporary_descriptor, mode)
        with os.fdopen(source_descriptor, "rb", closefd=False) as source:
            with os.fdopen(temporary_descriptor, "wb", closefd=False) as destination:
                shutil.copyfileobj(source, destination)
                destination.flush()
                os.fsync(destination.fileno())
        os.link(
            temporary_name,
            ".env",
            src_dir_fd=directory_descriptor,
            dst_dir_fd=directory_descriptor,
            follow_symlinks=False,
        )
        os.fsync(directory_descriptor)
    except FileExistsError as error:
        raise ActivationError(
            "Concurrent candidate LibreChat owner state appeared during rollback"
        ) from error
    finally:
        os.close(source_descriptor)
        os.close(temporary_descriptor)
        _retire_transaction_env_artifact(
            directory_descriptor,
            temporary_name,
            retirement_name,
            tombstone_name,
        )


def restore_candidate_env_atomically(
    record: dict[str, Any],
    payload: dict[str, Any],
    transaction: Path,
) -> None:
    directory_descriptor, snapshot = validate_candidate_env_checkpoint(
        record,
        transaction,
    )
    quarantine_name = candidate_env_name(
        record,
        "rollbackQuarantineName",
        ".env.viventium-rollback-",
    )
    acceptance_name = candidate_env_name(
        record,
        "commitAcceptanceName",
        ".env.viventium-accepted-",
    )
    materialization_retirement_name = candidate_env_retirement_name(
        record,
        "materializationRetirementName",
        "mat",
    )
    owner_retirement_name = candidate_env_retirement_name(
        record,
        "ownerEnvRetirementName",
        "env",
    )
    tombstone_name = candidate_env_retirement_name(
        record,
        "retirementTombstoneName",
        "zero",
    )

    def normalize_if_materialization_is_terminal() -> None:
        if isinstance(payload.get("ownerEnvMaterialized"), dict):
            location = validate_materialized_candidate_env_artifact(
                record,
                payload,
                transaction,
                allow_claimed=True,
                allow_missing=True,
            )
            if location != "missing":
                return
        normalize_owner_env_retirement_slots(
            directory_descriptor,
            record,
        )

    try:
        plan = payload.get("ownerEnvPlan")
        materialization_name = (
            plan.get("materializationTargetName")
            if isinstance(plan, dict)
            else None
        )
        if materialization_name is not None:
            if (
                not isinstance(materialization_name, str)
                or not materialization_name.startswith(
                    ".env.viventium-materialized-"
                )
                or "/" in materialization_name
            ):
                raise ActivationError(
                    "Candidate LibreChat materialization target is invalid"
                )
            materialization_contents = current_candidate_env_bytes(
                directory_descriptor,
                materialization_name,
            )
            if materialization_contents is not None:
                materialized_target = current_candidate_env_bytes(
                    directory_descriptor
                )
                existing_quarantine = current_candidate_env_bytes(
                    directory_descriptor,
                    quarantine_name,
                )
                if materialized_target is None:
                    if existing_quarantine is None:
                        os.rename(
                            materialization_name,
                            quarantine_name,
                            src_dir_fd=directory_descriptor,
                            dst_dir_fd=directory_descriptor,
                        )
                    elif materialization_contents == existing_quarantine:
                        _retire_transaction_env_artifact(
                            directory_descriptor,
                            materialization_name,
                            materialization_retirement_name,
                            tombstone_name,
                            receipt=payload.get("ownerEnvMaterialized")
                            if isinstance(payload.get("ownerEnvMaterialized"), dict)
                            else None,
                        )
                    else:
                        raise ActivationError(
                            "Candidate LibreChat materialization recovery is ambiguous"
                        )
                    os.fsync(directory_descriptor)
                else:
                    if existing_quarantine is not None:
                        raise ActivationError(
                            "Candidate LibreChat materialization recovery is ambiguous"
                        )
                    materialization_metadata = os.stat(
                        materialization_name,
                        dir_fd=directory_descriptor,
                        follow_symlinks=False,
                    )
                    target_metadata = os.stat(
                        ".env",
                        dir_fd=directory_descriptor,
                        follow_symlinks=False,
                    )
                    planned = (
                        plan.get("semanticManifest")
                        if isinstance(plan, dict)
                        else None
                    )
                    planned_sha = (
                        planned.get("file_sha256")
                        if isinstance(planned, dict)
                        else None
                    )
                    if (
                        not isinstance(planned_sha, str)
                        or hashlib.sha256(materialization_contents).hexdigest()
                        != planned_sha
                        or hashlib.sha256(materialized_target).hexdigest()
                        != planned_sha
                        or materialization_metadata.st_dev
                        != target_metadata.st_dev
                        or materialization_metadata.st_ino
                        != target_metadata.st_ino
                    ):
                        raise ActivationError(
                            "Concurrent candidate LibreChat owner state appeared "
                            "during materialization recovery"
                        )
                    os.rename(
                        ".env",
                        quarantine_name,
                        src_dir_fd=directory_descriptor,
                        dst_dir_fd=directory_descriptor,
                    )
                    _retire_transaction_env_artifact(
                        directory_descriptor,
                        materialization_name,
                        materialization_retirement_name,
                        tombstone_name,
                        receipt=payload.get("ownerEnvMaterialized")
                        if isinstance(payload.get("ownerEnvMaterialized"), dict)
                        else None,
                    )
                    os.fsync(directory_descriptor)
        acceptance_contents = current_candidate_env_bytes(
            directory_descriptor,
            acceptance_name,
        )
        if acceptance_contents is not None and not candidate_env_contents_allowed(
            acceptance_contents,
            record,
            payload,
        ):
            raise ActivationError(
                "Candidate LibreChat commit acceptance state is unexpected"
            )
        target_contents = current_candidate_env_bytes(directory_descriptor)
        quarantine_contents = current_candidate_env_bytes(
            directory_descriptor,
            quarantine_name,
        )
        if quarantine_contents is None:
            if target_contents is None:
                if acceptance_contents is not None:
                    os.rename(
                        acceptance_name,
                        quarantine_name,
                        src_dir_fd=directory_descriptor,
                        dst_dir_fd=directory_descriptor,
                    )
                    os.fsync(directory_descriptor)
                    quarantine_contents = acceptance_contents
                    acceptance_contents = None
                elif record.get("existed"):
                    raise ActivationError(
                        "Candidate LibreChat environment disappeared before rollback"
                    )
                else:
                    normalize_if_materialization_is_terminal()
                    return
            if quarantine_contents is not None:
                pass
            elif target_contents is None:
                if record.get("existed"):
                    raise ActivationError(
                        "Candidate LibreChat environment disappeared before rollback"
                    )
                normalize_if_materialization_is_terminal()
                return
            else:
                os.rename(
                    ".env",
                    quarantine_name,
                    src_dir_fd=directory_descriptor,
                    dst_dir_fd=directory_descriptor,
                )
                os.fsync(directory_descriptor)
                quarantine_contents = current_candidate_env_bytes(
                    directory_descriptor,
                    quarantine_name,
                )
                if quarantine_contents is None:
                    raise ActivationError(
                        "Candidate LibreChat rollback quarantine is missing"
                    )
        elif target_contents is not None:
            if (
                record.get("existed")
                and hashlib.sha256(target_contents).hexdigest()
                == record.get("sha256")
                and candidate_env_contents_allowed(
                    quarantine_contents,
                    record,
                    payload,
                )
            ):
                _retire_transaction_env_artifact(
                    directory_descriptor,
                    quarantine_name,
                    owner_retirement_name,
                    tombstone_name,
                )
                if acceptance_contents is not None:
                    _retire_transaction_env_artifact(
                        directory_descriptor,
                        acceptance_name,
                        owner_retirement_name,
                        tombstone_name,
                        receipt=payload.get("ownerEnvAccepted")
                        if isinstance(payload.get("ownerEnvAccepted"), dict)
                        else None,
                    )
                os.fsync(directory_descriptor)
                normalize_if_materialization_is_terminal()
                return
            raise ActivationError(
                "Concurrent candidate LibreChat owner state appeared during rollback"
            )

        if not candidate_env_contents_allowed(
            quarantine_contents,
            record,
            payload,
        ):
            _restore_quarantine_without_overwrite(
                directory_descriptor,
                quarantine_name,
                owner_retirement_name,
                tombstone_name,
            )
            raise ActivationError(
                "Candidate LibreChat owner state changed outside the activation plan"
            )

        if record.get("existed"):
            if snapshot is None:
                raise ActivationError(
                    "Candidate LibreChat environment snapshot is missing"
                )
            mode = int(record.get("mode", 0o600))
            if mode < 0 or mode > 0o7777:
                raise ActivationError(
                    "Candidate LibreChat environment mode is invalid"
                )
            _install_snapshot_without_overwrite(
                directory_descriptor,
                snapshot,
                mode,
                owner_retirement_name,
                tombstone_name,
            )
        elif current_candidate_env_bytes(directory_descriptor) is not None:
            raise ActivationError(
                "Concurrent candidate LibreChat owner state appeared during rollback"
            )
        _retire_transaction_env_artifact(
            directory_descriptor,
            quarantine_name,
            owner_retirement_name,
            tombstone_name,
        )
        if acceptance_contents is not None:
            _retire_transaction_env_artifact(
                directory_descriptor,
                acceptance_name,
                owner_retirement_name,
                tombstone_name,
                receipt=payload.get("ownerEnvAccepted")
                if isinstance(payload.get("ownerEnvAccepted"), dict)
                else None,
            )
        os.fsync(directory_descriptor)
        normalize_if_materialization_is_terminal()
    finally:
        os.close(directory_descriptor)


def accept_candidate_env_for_commit(
    record: dict[str, Any],
    payload: dict[str, Any],
    transaction: Path,
) -> dict[str, Any]:
    directory_descriptor, _ = validate_candidate_env_checkpoint(record, transaction)
    acceptance_name = candidate_env_name(
        record,
        "commitAcceptanceName",
        ".env.viventium-accepted-",
    )
    try:
        accepted_contents = current_candidate_env_bytes(
            directory_descriptor,
            acceptance_name,
        )
        target_contents = current_candidate_env_bytes(directory_descriptor)
        if accepted_contents is None:
            if target_contents is None:
                raise ActivationError(
                    "Candidate LibreChat environment disappeared before commit"
                )
            os.rename(
                ".env",
                acceptance_name,
                src_dir_fd=directory_descriptor,
                dst_dir_fd=directory_descriptor,
            )
            os.fsync(directory_descriptor)
            accepted_contents = current_candidate_env_bytes(
                directory_descriptor,
                acceptance_name,
            )
            if accepted_contents is None:
                raise ActivationError(
                    "Candidate LibreChat commit acceptance receipt is missing"
                )
            target_contents = None
        if not candidate_env_contents_allowed(accepted_contents, record, payload):
            if target_contents is None:
                _restore_quarantine_without_overwrite(
                    directory_descriptor,
                    acceptance_name,
                    candidate_env_retirement_name(
                        record,
                        "ownerEnvRetirementName",
                        "env",
                    ),
                    candidate_env_retirement_name(
                        record,
                        "retirementTombstoneName",
                        "zero",
                    ),
                )
            raise ActivationError(
                "Candidate LibreChat owner state changed outside the activation plan"
            )

        accepted_metadata = os.stat(
            acceptance_name,
            dir_fd=directory_descriptor,
            follow_symlinks=False,
        )
        receipt = {
            "name": acceptance_name,
            "device": accepted_metadata.st_dev,
            "inode": accepted_metadata.st_ino,
            "size": len(accepted_contents),
            "sha256": hashlib.sha256(accepted_contents).hexdigest(),
        }
        payload["ownerEnvAccepted"] = receipt
        payload["status"] = "commit_env_accepted"
        write_json(transaction / MANIFEST_NAME, payload, transaction)

        if target_contents is None:
            try:
                os.link(
                    acceptance_name,
                    ".env",
                    src_dir_fd=directory_descriptor,
                    dst_dir_fd=directory_descriptor,
                    follow_symlinks=False,
                )
                os.fsync(directory_descriptor)
            except FileExistsError as error:
                raise ActivationError(
                    "Concurrent candidate LibreChat owner state appeared during commit"
                ) from error
        return receipt
    finally:
        os.close(directory_descriptor)


def validate_accepted_candidate_env_target(
    record: dict[str, Any],
    payload: dict[str, Any],
    transaction: Path,
) -> None:
    receipt = payload.get("ownerEnvAccepted")
    if not isinstance(receipt, dict):
        raise ActivationError("Candidate LibreChat commit acceptance receipt is missing")
    acceptance_name = candidate_env_name(
        record,
        "commitAcceptanceName",
        ".env.viventium-accepted-",
    )
    if receipt.get("name") != acceptance_name:
        raise ActivationError("Candidate LibreChat commit acceptance receipt is invalid")
    directory_descriptor, _ = validate_candidate_env_checkpoint(record, transaction)
    try:
        accepted = current_candidate_env_bytes(
            directory_descriptor,
            acceptance_name,
        )
        target = current_candidate_env_bytes(directory_descriptor)
        if accepted is None or target is None:
            raise ActivationError(
                "Candidate LibreChat accepted environment is unavailable"
            )
        accepted_metadata = os.stat(
            acceptance_name,
            dir_fd=directory_descriptor,
            follow_symlinks=False,
        )
        target_metadata = os.stat(
            ".env",
            dir_fd=directory_descriptor,
            follow_symlinks=False,
        )
        digest = hashlib.sha256(accepted).hexdigest()
        if (
            digest != receipt.get("sha256")
            or hashlib.sha256(target).hexdigest() != receipt.get("sha256")
            or len(accepted) != receipt.get("size")
            or accepted_metadata.st_dev != receipt.get("device")
            or accepted_metadata.st_ino != receipt.get("inode")
            or target_metadata.st_dev != accepted_metadata.st_dev
            or target_metadata.st_ino != accepted_metadata.st_ino
        ):
            raise ActivationError(
                "Candidate LibreChat owner state changed after commit acceptance"
            )
    finally:
        os.close(directory_descriptor)


def materialized_candidate_env_receipt(
    record: dict[str, Any],
    payload: dict[str, Any],
    transaction: Path,
) -> dict[str, Any] | None:
    plan = payload.get("ownerEnvPlan")
    if not isinstance(plan, dict):
        return None
    name = plan.get("materializationTargetName")
    if (
        not isinstance(name, str)
        or not name.startswith(".env.viventium-materialized-")
        or "/" in name
    ):
        raise ActivationError("Candidate LibreChat materialization target is invalid")
    directory_descriptor, _ = validate_candidate_env_checkpoint(record, transaction)
    try:
        materialized = current_candidate_env_bytes(directory_descriptor, name)
        if materialized is None:
            return None
        target = current_candidate_env_bytes(directory_descriptor)
        planned = plan.get("semanticManifest")
        planned_sha = (
            planned.get("file_sha256")
            if isinstance(planned, dict)
            else None
        )
        if target is None:
            return None
        if not isinstance(planned_sha, str):
            raise ActivationError(
                "Candidate LibreChat materialization binding is incomplete"
            )
        materialized_metadata = os.stat(
            name,
            dir_fd=directory_descriptor,
            follow_symlinks=False,
        )
        target_metadata = os.stat(
            ".env",
            dir_fd=directory_descriptor,
            follow_symlinks=False,
        )
        if (
            materialized_metadata.st_dev != target_metadata.st_dev
            or materialized_metadata.st_ino != target_metadata.st_ino
        ):
            return None
        if (
            hashlib.sha256(materialized).hexdigest() != planned_sha
            or hashlib.sha256(target).hexdigest() != planned_sha
        ):
            raise ActivationError(
                "Candidate LibreChat materialization binding changed"
            )
        return {
            "name": name,
            "device": materialized_metadata.st_dev,
            "inode": materialized_metadata.st_ino,
            "size": len(materialized),
            "sha256": hashlib.sha256(materialized).hexdigest(),
        }
    finally:
        os.close(directory_descriptor)


def validate_materialized_candidate_env_artifact(
    record: dict[str, Any],
    payload: dict[str, Any],
    transaction: Path,
    *,
    allow_claimed: bool = False,
    allow_missing: bool = False,
) -> str:
    """Validate the receipted materialization independently of the live target.

    Publication still requires the materialization and ``.env`` to be the same
    hard link. After a healthy candidate starts, declared runtime-managed fields
    may be atomically reconciled. The original transaction artifact must remain
    exact, but commit must evaluate the current target through the semantic
    acceptance gate instead of requiring the old inode binding forever.
    """

    plan = payload.get("ownerEnvPlan")
    receipt = payload.get("ownerEnvMaterialized")
    if not isinstance(plan, dict) or not isinstance(receipt, dict):
        raise ActivationError(
            "Candidate LibreChat materialization receipt is missing"
        )
    name = plan.get("materializationTargetName")
    if (
        not isinstance(name, str)
        or not name.startswith(".env.viventium-materialized-")
        or "/" in name
        or name in {".", ".."}
        or receipt.get("name") != name
    ):
        raise ActivationError(
            "Candidate LibreChat materialization receipt is invalid"
        )
    claim_directory_name = candidate_env_name(
        record,
        "materializationClaimDirectoryName",
        ".env.viventium-private-",
    )
    claimed_names = ("owner.env", "deleting.env")
    directory_descriptor, _ = validate_candidate_env_checkpoint(record, transaction)
    claim_directory_descriptor: int | None = None
    try:
        candidate_contents = current_candidate_env_bytes(
            directory_descriptor,
            name,
        )
        try:
            claim_directory_descriptor = os.open(
                claim_directory_name,
                os.O_RDONLY
                | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=directory_descriptor,
            )
        except FileNotFoundError:
            claimed_contents = None
        else:
            claim_directory_metadata = os.fstat(claim_directory_descriptor)
            if (
                not stat.S_ISDIR(claim_directory_metadata.st_mode)
                or claim_directory_metadata.st_uid != os.getuid()
                or stat.S_IMODE(claim_directory_metadata.st_mode) != 0o700
                or claim_directory_metadata.st_dev
                != os.fstat(directory_descriptor).st_dev
            ):
                raise ActivationError(
                    "Candidate LibreChat materialization claim directory is unsafe"
                )
            claim_entries = os.listdir(claim_directory_descriptor)
            if (
                any(entry not in claimed_names for entry in claim_entries)
                or len(claim_entries) > 1
            ):
                raise ActivationError(
                    "Candidate LibreChat materialization claim directory is ambiguous"
                )
            claimed_name = claim_entries[0] if claim_entries else None
            claimed_contents = (
                current_candidate_env_bytes(
                    claim_directory_descriptor,
                    claimed_name,
                )
                if claimed_name is not None
                else None
            )
        if candidate_contents is not None and claimed_contents is not None:
            raise ActivationError(
                "Candidate LibreChat materialization artifact is ambiguous"
            )
        if claimed_contents is not None:
            if not allow_claimed:
                raise ActivationError(
                    "Candidate LibreChat materialization receipt changed"
                )
            contents = claimed_contents
            assert claim_directory_descriptor is not None
            assert claimed_name is not None
            descriptor = claim_directory_descriptor
            artifact_name = claimed_name
            location = "claimed"
        elif candidate_contents is not None:
            contents = candidate_contents
            descriptor = directory_descriptor
            artifact_name = name
            location = "candidate"
        else:
            if allow_missing:
                return "missing"
            raise ActivationError(
                "Candidate LibreChat materialization artifact is unavailable"
            )
        metadata = os.stat(
            artifact_name,
            dir_fd=descriptor,
            follow_symlinks=False,
        )
        if (
            metadata.st_dev != receipt.get("device")
            or metadata.st_ino != receipt.get("inode")
            or len(contents) != receipt.get("size")
            or hashlib.sha256(contents).hexdigest() != receipt.get("sha256")
        ):
            raise ActivationError(
                "Candidate LibreChat materialization receipt changed"
            )
        return location
    finally:
        if claim_directory_descriptor is not None:
            os.close(claim_directory_descriptor)
        os.close(directory_descriptor)


def claim_materialized_candidate_env_for_commit(
    record: dict[str, Any],
    payload: dict[str, Any],
    transaction: Path,
) -> None:
    """Move the artifact into a private same-filesystem claim directory.

    The move is no-replace and is validated again after the claim, so a racing
    replacement is never unlinked or blessed. Keeping the claim beneath the
    candidate directory also works when the checkout and App Support live on
    different volumes. The accepted current ``.env`` is a separate receipt and
    remains the durable owner file.
    """

    location = validate_materialized_candidate_env_artifact(
        record,
        payload,
        transaction,
        allow_claimed=True,
    )
    if location == "claimed":
        return
    plan = payload["ownerEnvPlan"]
    name = str(plan["materializationTargetName"])
    claim_directory_name = candidate_env_name(
        record,
        "materializationClaimDirectoryName",
        ".env.viventium-private-",
    )
    claimed_name = "owner.env"
    directory_descriptor, _ = validate_candidate_env_checkpoint(record, transaction)
    claim_directory_descriptor: int | None = None
    try:
        try:
            os.mkdir(
                claim_directory_name,
                mode=0o700,
                dir_fd=directory_descriptor,
            )
            os.fsync(directory_descriptor)
        except FileExistsError:
            pass
        claim_directory_descriptor = os.open(
            claim_directory_name,
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=directory_descriptor,
        )
        claim_directory_metadata = os.fstat(claim_directory_descriptor)
        if (
            not stat.S_ISDIR(claim_directory_metadata.st_mode)
            or claim_directory_metadata.st_uid != os.getuid()
            or stat.S_IMODE(claim_directory_metadata.st_mode) != 0o700
            or claim_directory_metadata.st_dev
            != os.fstat(directory_descriptor).st_dev
        ):
            raise ActivationError(
                "Candidate LibreChat materialization claim directory is unsafe"
            )
        try:
            atomic_rename_no_replace_between(
                directory_descriptor,
                name,
                claim_directory_descriptor,
                claimed_name,
            )
        except FileExistsError as error:
            raise ActivationError(
                "Candidate LibreChat materialization claim is ambiguous"
            ) from error
        except FileNotFoundError as error:
            raise ActivationError(
                "Candidate LibreChat materialization claim disappeared"
            ) from error
        os.fsync(directory_descriptor)
        os.fsync(claim_directory_descriptor)
    finally:
        if claim_directory_descriptor is not None:
            os.close(claim_directory_descriptor)
        os.close(directory_descriptor)
    if (
        validate_materialized_candidate_env_artifact(
            record,
            payload,
            transaction,
            allow_claimed=True,
        )
        != "claimed"
    ):
        raise ActivationError(
            "Candidate LibreChat materialization claim is incomplete"
        )


def cleanup_claimed_materialized_candidate_env(
    record: dict[str, Any],
    payload: dict[str, Any],
    transaction: Path,
    *,
    migrate_legacy: bool = False,
) -> None:
    location = validate_materialized_candidate_env_artifact(
        record,
        payload,
        transaction,
        allow_claimed=True,
        allow_missing=True,
    )
    if location == "missing":
        claim_directory_name = candidate_env_name(
            record,
            "materializationClaimDirectoryName",
            ".env.viventium-private-",
        )
        directory_descriptor, _ = validate_candidate_env_checkpoint(
            record,
            transaction,
        )
        try:
            receipt = payload.get("ownerEnvMaterialized")
            plan = payload.get("ownerEnvPlan")
            materialized_name = (
                plan.get("materializationTargetName")
                if isinstance(plan, dict)
                else None
            )
            if not isinstance(receipt, dict) or not isinstance(
                materialized_name,
                str,
            ):
                raise ActivationError(
                    "Candidate LibreChat materialization receipt is missing"
                )
            retire_owner_env_artifact(
                directory_descriptor,
                materialized_name,
                directory_descriptor,
                candidate_env_retirement_name(
                    record,
                    "materializationRetirementName",
                    "mat",
                ),
                candidate_env_retirement_name(
                    record,
                    "retirementTombstoneName",
                    "zero",
                ),
                receipt=receipt,
                allow_missing=True,
            )
            try:
                os.rmdir(claim_directory_name, dir_fd=directory_descriptor)
            except FileNotFoundError:
                pass
            except OSError as error:
                raise ActivationError(
                    "Candidate LibreChat materialization claim directory is not empty"
                ) from error
            else:
                os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
        normalize_candidate_env_retirement(
            record,
            transaction,
            migrate_legacy=migrate_legacy,
        )
        return
    if location != "claimed":
        return
    claim_directory_name = candidate_env_name(
        record,
        "materializationClaimDirectoryName",
        ".env.viventium-private-",
    )
    directory_descriptor, _ = validate_candidate_env_checkpoint(record, transaction)
    claim_directory_descriptor: int | None = None
    try:
        claim_directory_descriptor = os.open(
            claim_directory_name,
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=directory_descriptor,
        )
        claim_entries = os.listdir(claim_directory_descriptor)
        if len(claim_entries) != 1 or claim_entries[0] not in {
            "owner.env",
            "deleting.env",
        }:
            raise ActivationError(
                "Candidate LibreChat materialization claim directory is ambiguous"
            )
        cleanup_name = claim_entries[0]
        if cleanup_name == "owner.env":
            try:
                atomic_rename_no_replace_at(
                    claim_directory_descriptor,
                    "owner.env",
                    "deleting.env",
                )
            except FileExistsError as error:
                raise ActivationError(
                    "Candidate LibreChat materialization cleanup claim is ambiguous"
                ) from error
            except FileNotFoundError as error:
                raise ActivationError(
                    "Candidate LibreChat materialization cleanup claim disappeared"
                ) from error
            os.fsync(claim_directory_descriptor)
            cleanup_name = "deleting.env"
        if (
            validate_materialized_candidate_env_artifact(
                record,
                payload,
                transaction,
                allow_claimed=True,
            )
            != "claimed"
        ):
            raise ActivationError(
                "Candidate LibreChat materialization cleanup claim is incomplete"
            )
        receipt = payload.get("ownerEnvMaterialized")
        if not isinstance(receipt, dict):
            raise ActivationError(
                "Candidate LibreChat materialization receipt is missing"
            )
        retire_owner_env_artifact(
            claim_directory_descriptor,
            cleanup_name,
            directory_descriptor,
            candidate_env_retirement_name(
                record,
                "materializationRetirementName",
                "mat",
            ),
            candidate_env_retirement_name(
                record,
                "retirementTombstoneName",
                "zero",
            ),
            receipt=receipt,
            allow_missing=True,
        )
        os.fsync(claim_directory_descriptor)
        os.rmdir(claim_directory_name, dir_fd=directory_descriptor)
        os.fsync(directory_descriptor)
    finally:
        if claim_directory_descriptor is not None:
            os.close(claim_directory_descriptor)
        os.close(directory_descriptor)
    normalize_candidate_env_retirement(
        record,
        transaction,
        migrate_legacy=migrate_legacy,
    )


def cleanup_unbound_owner_env_materialization(
    record: dict[str, Any],
    payload: dict[str, Any],
    transaction: Path,
) -> None:
    plan = payload.get("ownerEnvPlan")
    if not isinstance(plan, dict) or isinstance(
        payload.get("ownerEnvMaterialized"),
        dict,
    ):
        return
    name = plan.get("materializationTargetName")
    if (
        not isinstance(name, str)
        or not name.startswith(".env.viventium-materialized-")
        or "/" in name
    ):
        raise ActivationError("Candidate LibreChat materialization target is invalid")
    directory_descriptor, _ = validate_candidate_env_checkpoint(record, transaction)
    try:
        try:
            materialized_metadata = os.stat(
                name,
                dir_fd=directory_descriptor,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            return
        try:
            target_metadata = os.stat(
                ".env",
                dir_fd=directory_descriptor,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            target_metadata = None
        if target_metadata is not None and (
            target_metadata.st_dev == materialized_metadata.st_dev
            and target_metadata.st_ino == materialized_metadata.st_ino
        ):
            raise ActivationError(
                "Candidate LibreChat materialization is bound without a receipt"
            )
        _retire_transaction_env_artifact(
            directory_descriptor,
            name,
            candidate_env_retirement_name(
                record,
                "materializationRetirementName",
                "mat",
            ),
            candidate_env_retirement_name(
                record,
                "retirementTombstoneName",
                "zero",
            ),
        )
    finally:
        os.close(directory_descriptor)


def cleanup_detached_owner_env_materialization(
    record: dict[str, Any],
    payload: dict[str, Any],
    transaction: Path,
) -> bool:
    """Retire a receipted materialization only when rollback is already exact.

    A runtime may atomically rewrite ``.env`` with identical bytes after the
    materializer hard-links it. That leaves the transaction-owned named link
    detached from ``.env`` even though the candidate has already returned to its
    exact checkpoint. Atomically claim and revalidate it twice beneath the
    candidate's transaction-unique private directory before deletion. Every
    rename stays on the candidate filesystem, so rollback does not depend on
    App Support sharing the same volume.
    """

    plan = payload.get("ownerEnvPlan")
    receipt = payload.get("ownerEnvMaterialized")
    if not isinstance(plan, dict) or not isinstance(receipt, dict):
        return False
    name = plan.get("materializationTargetName")
    if (
        not isinstance(name, str)
        or not name.startswith(".env.viventium-materialized-")
        or "/" in name
        or name in {".", ".."}
        or receipt.get("name") != name
    ):
        raise ActivationError("Candidate LibreChat materialization receipt is invalid")
    cleanup_name_value = record.get("rollbackCleanupName")
    if cleanup_name_value is None:
        rollback_name = candidate_env_name(
            record,
            "rollbackQuarantineName",
            ".env.viventium-rollback-",
        )
        cleanup_name_value = rollback_name.replace(
            ".env.viventium-rollback-",
            ".env.viventium-cleanup-",
            1,
        )
    cleanup_record = {"rollbackCleanupName": cleanup_name_value}
    cleanup_name = candidate_env_name(
        cleanup_record,
        "rollbackCleanupName",
        ".env.viventium-cleanup-",
    )
    directory_descriptor, _ = validate_candidate_env_checkpoint(record, transaction)
    try:
        cleanup = current_candidate_env_bytes(directory_descriptor, cleanup_name)
        materialized = current_candidate_env_bytes(directory_descriptor, name)
        claimed_location = validate_materialized_candidate_env_artifact(
            record,
            payload,
            transaction,
            allow_claimed=True,
            allow_missing=True,
        )
        claimed = claimed_location == "claimed"
        if sum(item is not None for item in (cleanup, materialized)) + int(claimed) > 1:
            raise ActivationError(
                "Candidate LibreChat detached materialization claim is ambiguous"
            )
        if claimed:
            cleanup_descriptor = None
            cleanup_path_name = None
        elif cleanup is None:
            if materialized is None:
                cleanup_claimed_materialized_candidate_env(
                    record,
                    payload,
                    transaction,
                )
                return False
            try:
                atomic_rename_no_replace_at(
                    directory_descriptor,
                    name,
                    cleanup_name,
                )
            except FileExistsError as error:
                raise ActivationError(
                    "Candidate LibreChat detached materialization claim is ambiguous"
                ) from error
            except FileNotFoundError:
                return False
            os.fsync(directory_descriptor)
            cleanup = current_candidate_env_bytes(
                directory_descriptor,
                cleanup_name,
            )
            if cleanup is None:
                raise ActivationError(
                    "Candidate LibreChat detached materialization claim disappeared"
                )
            cleanup_descriptor = directory_descriptor
            cleanup_path_name = cleanup_name
        else:
            cleanup_descriptor = directory_descriptor
            cleanup_path_name = cleanup_name
        if not claimed:
            assert cleanup is not None
            assert cleanup_descriptor is not None
            assert cleanup_path_name is not None
            metadata = os.stat(
                cleanup_path_name,
                dir_fd=cleanup_descriptor,
                follow_symlinks=False,
            )
            digest = hashlib.sha256(cleanup).hexdigest()
            if (
                metadata.st_dev != receipt.get("device")
                or metadata.st_ino != receipt.get("inode")
                or len(cleanup) != receipt.get("size")
                or digest != receipt.get("sha256")
            ):
                try:
                    atomic_rename_no_replace_between(
                        cleanup_descriptor,
                        cleanup_path_name,
                        directory_descriptor,
                        name,
                    )
                    os.fsync(directory_descriptor)
                except (FileExistsError, FileNotFoundError):
                    pass
                raise ActivationError(
                    "Candidate LibreChat detached materialization receipt changed"
                )
        target = current_candidate_env_bytes(directory_descriptor)
        if record.get("existed"):
            if target is None:
                if not claimed:
                    assert cleanup_descriptor is not None
                    assert cleanup_path_name is not None
                    atomic_rename_no_replace_between(
                        cleanup_descriptor,
                        cleanup_path_name,
                        directory_descriptor,
                        name,
                    )
                os.fsync(directory_descriptor)
                raise ActivationError(
                    "Candidate LibreChat detached materialization is ambiguous"
                )
            target_metadata = os.stat(
                ".env",
                dir_fd=directory_descriptor,
                follow_symlinks=False,
            )
            if (
                len(target) != record.get("size")
                or hashlib.sha256(target).hexdigest() != record.get("sha256")
                or stat.S_IMODE(target_metadata.st_mode) != record.get("mode")
            ):
                if not claimed:
                    assert cleanup_descriptor is not None
                    assert cleanup_path_name is not None
                    atomic_rename_no_replace_between(
                        cleanup_descriptor,
                        cleanup_path_name,
                        directory_descriptor,
                        name,
                    )
                os.fsync(directory_descriptor)
                raise ActivationError(
                    "Candidate LibreChat detached materialization is ambiguous"
                )
        elif target is not None:
            if not claimed:
                assert cleanup_descriptor is not None
                assert cleanup_path_name is not None
                atomic_rename_no_replace_between(
                    cleanup_descriptor,
                    cleanup_path_name,
                    directory_descriptor,
                    name,
                )
            os.fsync(directory_descriptor)
            raise ActivationError(
                "Candidate LibreChat detached materialization is ambiguous"
            )
    finally:
        os.close(directory_descriptor)
    if not claimed:
        claim_directory_name = candidate_env_name(
            record,
            "materializationClaimDirectoryName",
            ".env.viventium-private-",
        )
        directory_descriptor, _ = validate_candidate_env_checkpoint(
            record,
            transaction,
        )
        claim_directory_descriptor: int | None = None
        try:
            try:
                os.mkdir(
                    claim_directory_name,
                    mode=0o700,
                    dir_fd=directory_descriptor,
                )
                os.fsync(directory_descriptor)
            except FileExistsError:
                pass
            claim_directory_descriptor = os.open(
                claim_directory_name,
                os.O_RDONLY
                | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=directory_descriptor,
            )
            claim_directory_metadata = os.fstat(claim_directory_descriptor)
            if (
                not stat.S_ISDIR(claim_directory_metadata.st_mode)
                or claim_directory_metadata.st_uid != os.getuid()
                or stat.S_IMODE(claim_directory_metadata.st_mode) != 0o700
                or claim_directory_metadata.st_dev
                != os.fstat(directory_descriptor).st_dev
            ):
                raise ActivationError(
                    "Candidate LibreChat materialization claim directory is unsafe"
                )
            atomic_rename_no_replace_between(
                directory_descriptor,
                cleanup_name,
                claim_directory_descriptor,
                "owner.env",
            )
            os.fsync(directory_descriptor)
            os.fsync(claim_directory_descriptor)
        finally:
            if claim_directory_descriptor is not None:
                os.close(claim_directory_descriptor)
            os.close(directory_descriptor)
        try:
            claimed_location = validate_materialized_candidate_env_artifact(
                record,
                payload,
                transaction,
                allow_claimed=True,
            )
        except ActivationError as error:
            raise ActivationError(
                "Candidate LibreChat detached materialization receipt changed"
            ) from error
        if claimed_location != "claimed":
            raise ActivationError(
                "Candidate LibreChat detached materialization receipt changed"
            )
    cleanup_claimed_materialized_candidate_env(
        record,
        payload,
        transaction,
    )
    return True


def validate_owner_env_materialized(
    payload: dict[str, Any],
    transaction: Path,
) -> None:
    if not isinstance(payload.get("ownerEnvPlan"), dict):
        return
    record = payload.get("candidateEnv")
    receipt = payload.get("ownerEnvMaterialized")
    if not isinstance(record, dict) or not isinstance(receipt, dict):
        raise ActivationError(
            "Candidate LibreChat materialization receipt is missing"
        )
    current = materialized_candidate_env_receipt(record, payload, transaction)
    if current is None or any(
        current.get(field) != receipt.get(field)
        for field in ("name", "device", "inode", "size", "sha256")
    ):
        raise ActivationError(
            "Candidate LibreChat materialization receipt changed"
        )


def mark_owner_env_materialized(args: argparse.Namespace) -> dict[str, Any]:
    transaction, payload = load_manifest(args.transaction_dir, args.app_support_dir)
    if payload.get("schemaVersion") != SCHEMA_VERSION:
        raise ActivationError(
            "Legacy activation cannot record owner environment materialization"
        )
    if payload.get("status") != "prepared":
        raise ActivationError(
            "Owner environment must materialize before publication"
        )
    validate_owner_env_plan(payload, transaction)
    record = payload.get("candidateEnv")
    if not isinstance(record, dict):
        raise ActivationError("Candidate LibreChat environment checkpoint is missing")
    receipt = materialized_candidate_env_receipt(
        record,
        payload,
        transaction,
    )
    if receipt is None:
        raise ActivationError(
            "Candidate LibreChat materialization binding is unavailable"
        )
    payload["ownerEnvMaterialized"] = receipt
    write_json(transaction / MANIFEST_NAME, payload, transaction)
    return payload


def current_candidate_env_receipt(
    record: dict[str, Any],
    transaction: Path,
) -> dict[str, Any]:
    directory_descriptor, _ = validate_candidate_env_checkpoint(record, transaction)
    try:
        contents = current_candidate_env_bytes(directory_descriptor)
        if contents is None:
            raise ActivationError(
                "Candidate LibreChat owner environment is unavailable"
            )
        metadata = os.stat(
            ".env",
            dir_fd=directory_descriptor,
            follow_symlinks=False,
        )
        return {
            "device": metadata.st_dev,
            "inode": metadata.st_ino,
            "size": len(contents),
            "sha256": hashlib.sha256(contents).hexdigest(),
        }
    finally:
        os.close(directory_descriptor)


def owner_env_alignment_required(
    payload: dict[str, Any],
    transaction: Path,
) -> bool:
    if not isinstance(payload.get("ownerEnvPlan"), dict):
        return False
    record = payload.get("candidateEnv")
    if not isinstance(record, dict):
        raise ActivationError("Candidate LibreChat environment checkpoint is missing")
    baseline = payload.get("ownerEnvAligned")
    if not isinstance(baseline, dict):
        baseline = payload.get("ownerEnvAccepted")
    if not isinstance(baseline, dict):
        raise ActivationError("Candidate LibreChat alignment receipt is missing")
    current = current_candidate_env_receipt(record, transaction)
    return any(
        current.get(field) != baseline.get(field)
        for field in ("device", "inode", "size", "sha256")
    )


def cleanup_candidate_env_transaction_links(
    record: dict[str, Any],
    payload: dict[str, Any],
    transaction: Path,
) -> None:
    accepted_receipt = payload.get("ownerEnvAccepted")
    if not isinstance(accepted_receipt, dict):
        normalize_candidate_env_retirement(
            record,
            transaction,
            migrate_legacy=True,
        )
        return
    directory_descriptor, _ = validate_candidate_env_checkpoint(record, transaction)
    try:
        links: list[tuple[str, dict[str, Any], str]] = [
            (
                candidate_env_name(
                    record,
                    "commitAcceptanceName",
                    ".env.viventium-accepted-",
                ),
                accepted_receipt,
                candidate_env_retirement_name(
                    record,
                    "ownerEnvRetirementName",
                    "env",
                ),
            )
        ]
        tombstone_name = candidate_env_retirement_name(
            record,
            "retirementTombstoneName",
            "zero",
        )
        for name, receipt, retirement_name in links:
            retire_owner_env_artifact(
                directory_descriptor,
                name,
                directory_descriptor,
                retirement_name,
                tombstone_name,
                receipt=receipt,
                allow_missing=False,
            )
        os.fsync(directory_descriptor)
    finally:
        os.close(directory_descriptor)
    if isinstance(payload.get("ownerEnvPlan"), dict) and isinstance(
        payload.get("ownerEnvMaterialized"),
        dict,
    ):
        cleanup_claimed_materialized_candidate_env(
            record,
            payload,
            transaction,
            migrate_legacy=True,
        )
    else:
        normalize_candidate_env_retirement(
            record,
            transaction,
            migrate_legacy=True,
        )


def plan_owner_env(args: argparse.Namespace) -> dict[str, Any]:
    transaction, payload = load_manifest(args.transaction_dir, args.app_support_dir)
    if payload.get("schemaVersion") != SCHEMA_VERSION:
        raise ActivationError("Legacy activation cannot accept an owner environment plan")
    if payload.get("status") != "prepared":
        raise ActivationError("Owner environment must be planned before publication")
    candidate = validate_private_directory(
        Path(str(payload.get("candidateRuntime") or "")),
        transaction,
        "candidate runtime",
    )
    manifest = contained(
        args.owner_env_manifest,
        candidate,
        "owner environment plan",
    )
    if manifest != candidate / "service-env" / "librechat.owner.manifest.json":
        raise ActivationError("Owner environment plan path is not canonical")
    metadata = manifest.lstat()
    if (
        manifest.is_symlink()
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
    ):
        raise ActivationError("Owner environment plan is unsafe")
    owner_payload = json.loads(manifest.read_text(encoding="utf-8"))
    semantic = owner_payload.get("semantic_manifest")
    target_binding = owner_payload.get("target_binding")
    materialization_target_name = owner_payload.get(
        "materialization_target_name"
    )
    if (
        owner_payload.get("schema_version") != 2
        or owner_payload.get("kind") != "librechat-owner-environment-continuity"
        or not isinstance(semantic, dict)
        or not isinstance(target_binding, dict)
        or not isinstance(target_binding.get("repo_sha256"), str)
        or not isinstance(target_binding.get("git_commit"), str)
        or not isinstance(materialization_target_name, str)
        or not materialization_target_name.startswith(
            ".env.viventium-materialized-"
        )
        or "/" in materialization_target_name
    ):
        raise ActivationError("Owner environment plan is invalid")
    payload["ownerEnvPlan"] = {
        "manifestSha256": sha256_file(manifest),
        "semanticManifest": semantic,
        "targetBinding": target_binding,
        "materializationTargetName": materialization_target_name,
    }
    payload["ownerEnvMaterialized"] = None
    write_json(transaction / MANIFEST_NAME, payload, transaction)
    return payload


def validate_owner_env_plan(
    payload: dict[str, Any],
    transaction: Path,
) -> None:
    plan = payload.get("ownerEnvPlan")
    if not isinstance(plan, dict):
        return
    candidate = validate_private_directory(
        Path(str(payload.get("candidateRuntime") or "")),
        transaction,
        "candidate runtime",
    )
    manifest = candidate / "service-env" / "librechat.owner.manifest.json"
    metadata = manifest.lstat()
    if (
        manifest.is_symlink()
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or sha256_file(manifest) != plan.get("manifestSha256")
    ):
        raise ActivationError("Owner environment plan changed during activation")
    target_binding = plan.get("targetBinding")
    candidate_env = payload.get("candidateEnv")
    if not isinstance(target_binding, dict) or not isinstance(candidate_env, dict):
        raise ActivationError("Owner environment revision binding is missing")
    repo = lexical(Path(str(candidate_env.get("repoRoot") or "")))
    if (
        hashlib.sha256(str(repo).encode("utf-8")).hexdigest()
        != target_binding.get("repo_sha256")
    ):
        raise ActivationError("Owner environment checkout binding changed")
    expected_commit = str(target_binding.get("git_commit") or "")
    if not GIT_COMMIT.fullmatch(expected_commit):
        raise ActivationError("Owner environment revision binding is invalid")
    try:
        completed = subprocess.run(
            [
                "git",
                "-C",
                str(repo / "viventium_v0_4" / "LibreChat"),
                "rev-parse",
                "--verify",
                "HEAD",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ActivationError(
            "Owner environment revision binding could not be verified"
        ) from error
    if completed.returncode != 0 or completed.stdout.strip() != expected_commit:
        raise ActivationError("Owner environment checkout revision changed")


def restore_state_file(
    record: dict[str, Any],
    transaction: Path,
    app_support_dir: Path,
) -> None:
    target = contained(
        Path(str(record["path"])),
        app_support_dir,
        "activation state file",
    )
    if not record.get("existed"):
        if target.exists() or target.is_symlink():
            metadata = target.lstat()
            if target.is_symlink() or not stat.S_ISREG(metadata.st_mode):
                raise ActivationError("Refusing to remove an unsafe activation state path")
            target.unlink()
        return
    snapshot = contained(
        Path(str(record.get("snapshot") or "")),
        transaction,
        "activation state snapshot",
    )
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.restore.",
        dir=target.parent,
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        shutil.copy2(snapshot, temporary)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def helper_state_record(payload: dict[str, Any]) -> dict[str, Any]:
    helper_path = lexical(Path(str(payload.get("helperConfigFile") or "")))
    matches = [
        record
        for record in payload.get("stateFiles", [])
        if isinstance(record, dict)
        and lexical(Path(str(record.get("path") or ""))) == helper_path
    ]
    if len(matches) != 1:
        raise ActivationError("Activation helper snapshot is missing or duplicated")
    return matches[0]


def read_helper_config(path: Path) -> dict[str, Any]:
    metadata = path.lstat()
    if (
        path.is_symlink()
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
    ):
        raise ActivationError("Helper config is not an owner-controlled regular file")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ActivationError("Helper config must contain a JSON object")
    return payload


def helper_managed_view(payload: dict[str, Any]) -> dict[str, Any]:
    supervision = payload.get("runtimeSupervision")
    if not isinstance(supervision, dict):
        supervision = {}
    return {
        field: {
            "present": field in supervision,
            "value": supervision.get(field),
        }
        for field in sorted(HELPER_INTENT_MUTATED_FIELDS)
        if field != "activationTransactionId"
    }


def quiesced_helper_managed_view(payload: dict[str, Any]) -> dict[str, Any]:
    quiesced = dict(payload)
    supervision = payload.get("runtimeSupervision")
    if not isinstance(supervision, dict):
        supervision = {}
    else:
        supervision = dict(supervision)
    supervision.update(
        {
            "schemaVersion": 1,
            "desiredState": "stopped",
            "consecutiveLaunchAttempts": 0,
            "nextLaunchAttemptAt": None,
            "healthySince": None,
        }
    )
    quiesced["runtimeSupervision"] = supervision
    return helper_managed_view(quiesced)


def validate_helper_quiescence(
    payload: dict[str, Any],
    transaction: Path,
    app_support: Path,
) -> None:
    receipt = payload.get("helperQuiescence")
    if not isinstance(receipt, dict):
        raise ActivationError("Helper quiescence receipt is missing")
    helper_path = contained(
        Path(str(payload.get("helperConfigFile") or "")),
        app_support,
        "helper config",
    )
    record = helper_state_record(payload)
    validate_state_file_snapshot(record, transaction, app_support)
    validate_state_file_target(record, app_support)
    status = receipt.get("status")
    if status == "not_present":
        if record.get("existed"):
            raise ActivationError("Helper quiescence absence receipt is invalid")
        if helper_path.exists() or helper_path.is_symlink():
            raise ActivationError(
                "Helper config appeared after the quiescence receipt"
            )
        return
    if status != "applied" or not record.get("existed"):
        raise ActivationError("Helper quiescence receipt is invalid")
    token = str(receipt.get("token") or "")
    managed_view = receipt.get("managedView")
    if not token or not isinstance(managed_view, dict):
        raise ActivationError("Helper quiescence ownership proof is incomplete")
    current = read_helper_config(helper_path)
    supervision = current.get("runtimeSupervision")
    current_token = (
        supervision.get("activationTransactionId")
        if isinstance(supervision, dict)
        else None
    )
    if current_token != token or helper_managed_view(current) != managed_view:
        raise ActivationError(
            "Helper runtime supervision changed after quiescence"
        )


def validate_helper_executable(path: Path) -> Path:
    executable = lexical(path)
    if (
        executable.name != "ViventiumHelper"
        or executable.parent.name != "MacOS"
        or executable.parent.parent.name != "Contents"
        or executable.parent.parent.parent.suffix != ".app"
    ):
        raise ActivationError(
            "Helper process quiescence requires a Viventium helper bundle executable"
        )
    if not executable.exists():
        return executable
    validate_real_path_chain(executable, "Viventium helper executable")
    metadata = executable.lstat()
    if (
        executable.is_symlink()
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or not os.access(executable, os.X_OK)
    ):
        raise ActivationError(
            "Viventium helper executable is not an owner-controlled executable"
        )
    return executable


class DarwinProcessBSDInfo(ctypes.Structure):
    _fields_ = [
        ("pbi_flags", ctypes.c_uint32),
        ("pbi_status", ctypes.c_uint32),
        ("pbi_xstatus", ctypes.c_uint32),
        ("pbi_pid", ctypes.c_uint32),
        ("pbi_ppid", ctypes.c_uint32),
        ("pbi_uid", ctypes.c_uint32),
        ("pbi_gid", ctypes.c_uint32),
        ("pbi_ruid", ctypes.c_uint32),
        ("pbi_rgid", ctypes.c_uint32),
        ("pbi_svuid", ctypes.c_uint32),
        ("pbi_svgid", ctypes.c_uint32),
        ("rfu_1", ctypes.c_uint32),
        ("pbi_comm", ctypes.c_char * 16),
        ("pbi_name", ctypes.c_char * 32),
        ("pbi_nfiles", ctypes.c_uint32),
        ("pbi_pgid", ctypes.c_uint32),
        ("pbi_pjobc", ctypes.c_uint32),
        ("e_tdev", ctypes.c_uint32),
        ("e_tpgid", ctypes.c_uint32),
        ("pbi_nice", ctypes.c_int32),
        ("pbi_start_tvsec", ctypes.c_uint64),
        ("pbi_start_tvusec", ctypes.c_uint64),
    ]


def process_executable_path(pid: int) -> Path | None:
    if sys.platform == "darwin":
        libproc = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
        proc_pidpath = libproc.proc_pidpath
        proc_pidpath.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
        proc_pidpath.restype = ctypes.c_int
        buffer = ctypes.create_string_buffer(4096)
        length = proc_pidpath(pid, buffer, len(buffer))
        if length <= 0:
            return None
        return lexical(Path(os.fsdecode(buffer.value)))
    proc_link = Path("/proc") / str(pid) / "exe"
    try:
        return lexical(Path(os.readlink(proc_link)))
    except (FileNotFoundError, PermissionError, OSError):
        return None


def process_start_token(pid: int) -> str | None:
    if sys.platform == "darwin":
        libproc = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
        proc_pidinfo = libproc.proc_pidinfo
        proc_pidinfo.argtypes = [
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_uint64,
            ctypes.c_void_p,
            ctypes.c_int,
        ]
        proc_pidinfo.restype = ctypes.c_int
        info = DarwinProcessBSDInfo()
        size = ctypes.sizeof(info)
        if proc_pidinfo(pid, 3, 0, ctypes.byref(info), size) != size:
            return None
        return f"{info.pbi_start_tvsec}:{info.pbi_start_tvusec}"
    try:
        fields = (Path("/proc") / str(pid) / "stat").read_text(
            encoding="utf-8"
        ).split()
    except (FileNotFoundError, PermissionError, OSError):
        return None
    if len(fields) < 22:
        return None
    return fields[21]


def process_identity(pid: int) -> dict[str, Any] | None:
    executable = process_executable_path(pid)
    start_token = process_start_token(pid)
    if executable is None or start_token is None:
        return None
    return {
        "pid": pid,
        "executablePath": os.path.realpath(str(executable)),
        "startToken": start_token,
    }


def running_helper_processes(executables: list[Path]) -> list[dict[str, Any]]:
    expected = {
        os.path.realpath(str(executable))
        for executable in executables
        if executable.exists()
    }
    if not expected:
        return []
    if sys.platform == "darwin":
        completed = subprocess.run(
            ["/bin/ps", "-axo", "pid="],
            check=True,
            capture_output=True,
            text=True,
        )
        candidates = [
            int(value)
            for value in completed.stdout.split()
            if value.isdigit()
        ]
    else:
        candidates = [
            int(path.name)
            for path in Path("/proc").iterdir()
            if path.name.isdigit()
        ]
    matches: list[dict[str, Any]] = []
    for pid in candidates:
        if pid == os.getpid():
            continue
        identity = process_identity(pid)
        if (
            identity is not None
            and identity["executablePath"] in expected
        ):
            matches.append(identity)
    return sorted(matches, key=lambda identity: identity["pid"])


def validate_helper_process_quiescence(payload: dict[str, Any]) -> None:
    receipt = payload.get("helperProcessQuiescence")
    if receipt is None:
        if payload.get("helperProcessQuiescenceRequired") is True:
            raise ActivationError(
                "Required helper process quiescence receipt is missing"
            )
        return
    if not isinstance(receipt, dict) or receipt.get("status") != "applied":
        raise ActivationError("Helper process quiescence receipt is incomplete")
    raw_paths = receipt.get("executablePaths")
    if not isinstance(raw_paths, list) or not raw_paths:
        raise ActivationError("Helper process quiescence paths are missing")
    executables = [
        validate_helper_executable(Path(str(path)))
        for path in raw_paths
    ]
    running_paths = receipt.get("runningExecutablePaths")
    normalized_paths = {os.path.realpath(str(path)) for path in executables}
    if (
        not isinstance(running_paths, list)
        or any(
            not isinstance(path, str)
            or os.path.realpath(path) not in normalized_paths
            for path in running_paths
        )
        or (receipt.get("wasRunning") is True) != bool(running_paths)
    ):
        raise ActivationError(
            "Helper process quiescence running-path receipt is invalid"
        )
    if running_helper_processes(executables):
        raise ActivationError("Viventium helper process resumed after quiescence")


def quiesce_helper_process(args: argparse.Namespace) -> dict[str, Any]:
    transaction, payload = load_manifest(args.transaction_dir, args.app_support_dir)
    if payload.get("schemaVersion") != SCHEMA_VERSION:
        raise ActivationError(
            "Legacy activation cannot quiesce helper processes transactionally"
        )
    if payload.get("status") != "prepared":
        raise ActivationError(
            "Helper process must quiesce before activation publication"
        )
    # Stop the installed helper before writing the supervision ownership token.
    # A helper that flushes an in-memory config while terminating must not be
    # able to erase a token written immediately before SIGTERM. Older callers
    # that already wrote the token remain supported and are revalidated.
    if payload.get("helperQuiescence") is not None:
        validate_helper_quiescence(
            payload,
            transaction,
            lexical(args.app_support_dir),
        )
    executables = [
        validate_helper_executable(path)
        for path in args.helper_executable
    ]
    normalized_paths = [str(path) for path in executables]
    receipt = payload.get("helperProcessQuiescence")
    if receipt is not None:
        if (
            not isinstance(receipt, dict)
            or receipt.get("status") not in {"planned", "applied"}
            or receipt.get("executablePaths") != normalized_paths
            or not isinstance(receipt.get("runningExecutablePaths"), list)
            or not isinstance(receipt.get("wasRunning"), bool)
        ):
            raise ActivationError("Helper process quiescence receipt is invalid")
        was_running = receipt["wasRunning"]
        running_paths = receipt["runningExecutablePaths"]
    else:
        identities = running_helper_processes(executables)
        running_paths = sorted(
            {
                identity["executablePath"]
                for identity in identities
            }
        )
        was_running = bool(running_paths)
        payload["helperProcessQuiescence"] = {
            "executablePaths": normalized_paths,
            "runningExecutablePaths": running_paths,
            "status": "planned",
            "wasRunning": was_running,
        }
        write_json(transaction / MANIFEST_NAME, payload, transaction)

    identities = running_helper_processes(executables)
    for identity in identities:
        pid = int(identity["pid"])
        # Revalidate both executable and start time immediately before the
        # signal. A vanished or PID-reused process is not transaction-owned.
        if process_identity(pid) != identity:
            continue
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            continue
        except PermissionError as error:
            raise ActivationError(
                "Viventium helper process could not be stopped safely"
            ) from error
    deadline = time.monotonic() + args.timeout_seconds
    remaining = running_helper_processes(executables)
    while remaining and time.monotonic() < deadline:
        time.sleep(0.05)
        remaining = running_helper_processes(executables)
    if remaining:
        raise ActivationError(
            "Viventium helper process did not stop before the quiescence timeout"
        )
    payload["helperProcessQuiescence"] = {
        "executablePaths": normalized_paths,
        "runningExecutablePaths": running_paths,
        "status": "applied",
        "wasRunning": was_running,
    }
    write_json(transaction / MANIFEST_NAME, payload, transaction)
    return payload


def helper_process_status(args: argparse.Namespace) -> dict[str, Any]:
    _, payload = load_manifest(args.transaction_dir, args.app_support_dir)
    receipt = payload.get("helperProcessQuiescence")
    if not isinstance(receipt, dict):
        return {"running": False, "wasRunning": False}
    raw_paths = receipt.get("executablePaths")
    if not isinstance(raw_paths, list) or not raw_paths:
        raise ActivationError("Helper process quiescence paths are missing")
    executables = [
        validate_helper_executable(Path(str(path)))
        for path in raw_paths
    ]
    identities = running_helper_processes(executables)
    expected = receipt.get("runningExecutablePaths")
    if not isinstance(expected, list):
        raise ActivationError("Helper process quiescence running paths are invalid")
    return {
        "running": bool(identities),
        "runningExecutablePaths": sorted(
            {
                identity["executablePath"]
                for identity in identities
            }
        ),
        "expectedRunningExecutablePaths": expected,
        "wasRunning": receipt.get("wasRunning") is True,
    }


def set_helper_process_restoration_pending(payload: dict[str, Any]) -> None:
    receipt = payload.get("helperProcessQuiescence")
    expected = (
        receipt.get("runningExecutablePaths")
        if isinstance(receipt, dict)
        else []
    )
    if not isinstance(expected, list):
        raise ActivationError("Helper process restoration paths are invalid")
    payload["helperProcessRestoration"] = {
        "expectedRunningExecutablePaths": expected,
        "status": "pending" if expected else "not_required",
    }


def restore_helper_process(args: argparse.Namespace) -> dict[str, Any]:
    transaction, payload = load_manifest(args.transaction_dir, args.app_support_dir)
    if payload.get("status") != "rolled_back":
        raise ActivationError(
            "Helper process restoration requires a rolled-back activation"
        )
    if payload.get("schemaVersion") != SCHEMA_VERSION:
        # Older activation schemas never terminated the helper process.
        return payload
    restoration = payload.get("helperProcessRestoration")
    if not isinstance(restoration, dict):
        raise ActivationError("Helper process restoration receipt is missing")
    status = restoration.get("status")
    if status in {"complete", "not_required"}:
        return payload
    if status != "pending":
        raise ActivationError("Helper process restoration receipt is invalid")
    raw_expected = restoration.get("expectedRunningExecutablePaths")
    if not isinstance(raw_expected, list) or not raw_expected:
        raise ActivationError("Helper process restoration paths are missing")
    expected = [
        validate_helper_executable(Path(str(path)))
        for path in raw_expected
    ]
    expected_paths = {os.path.realpath(str(path)) for path in expected}

    def current_paths() -> set[str]:
        return {
            identity["executablePath"]
            for identity in running_helper_processes(expected)
        }

    missing = expected_paths - current_paths()
    if missing:
        if sys.platform != "darwin":
            raise ActivationError(
                "Viventium helper process must be relaunched on this platform"
            )
        for executable_path in sorted(missing):
            bundle = Path(executable_path).parent.parent.parent
            completed = subprocess.run(
                ["/usr/bin/open", "-g", str(bundle)],
                check=False,
                capture_output=True,
                text=True,
            )
            if completed.returncode != 0:
                raise ActivationError(
                    "Viventium helper process could not be relaunched"
                )
    deadline = time.monotonic() + args.timeout_seconds
    while not expected_paths.issubset(current_paths()):
        if time.monotonic() >= deadline:
            raise ActivationError(
                "Viventium helper process did not return after rollback"
            )
        time.sleep(0.05)
    restoration["status"] = "complete"
    payload["helperProcessRestoration"] = restoration
    write_json(transaction / MANIFEST_NAME, payload, transaction)
    return payload


def quiesce_helper(args: argparse.Namespace) -> dict[str, Any]:
    transaction, payload = load_manifest(args.transaction_dir, args.app_support_dir)
    if payload.get("schemaVersion") != SCHEMA_VERSION:
        raise ActivationError("Legacy activation cannot quiesce helper supervision")
    if payload.get("status") != "prepared":
        raise ActivationError("Helper supervision must quiesce before publication")
    app_support = lexical(args.app_support_dir)
    helper_path = contained(
        Path(str(payload.get("helperConfigFile") or "")),
        app_support,
        "helper config",
    )
    record = helper_state_record(payload)
    validate_state_file_snapshot(record, transaction, app_support)
    validate_state_file_target(record, app_support)
    existing_receipt = payload.get("helperQuiescence")
    if isinstance(existing_receipt, dict):
        receipt_status = existing_receipt.get("status")
        if receipt_status in {"applied", "not_present"}:
            validate_helper_quiescence(
                payload,
                transaction,
                app_support,
            )
            return payload
        if receipt_status != "planned":
            raise ActivationError("Helper quiescence receipt is invalid")
        token = str(existing_receipt.get("token") or "")
        if not token:
            raise ActivationError("Helper quiescence token is missing")
    else:
        token = uuid.uuid4().hex
        payload["helperQuiescence"] = {
            "status": "planned",
            "token": token,
        }
        write_json(transaction / MANIFEST_NAME, payload, transaction)

    if not record.get("existed"):
        if helper_path.exists() or helper_path.is_symlink():
            raise ActivationError(
                "Helper config appeared during activation; refusing to overwrite it"
            )
        payload["helperQuiescence"] = {
            "status": "not_present",
            "token": token,
        }
        write_json(transaction / MANIFEST_NAME, payload, transaction)
        return payload

    snapshot = contained(
        Path(str(record.get("snapshot") or "")),
        transaction,
        "helper config snapshot",
    )
    original = read_helper_config(snapshot)
    current = read_helper_config(helper_path)
    supervision = current.get("runtimeSupervision")
    if not isinstance(supervision, dict):
        supervision = {}
    expected_managed_view = quiesced_helper_managed_view(original)
    if supervision.get("activationTransactionId") == token:
        if helper_managed_view(current) != expected_managed_view:
            raise ActivationError(
                "Helper runtime supervision changed during quiescence"
            )
    else:
        if helper_managed_view(current) != helper_managed_view(original):
            raise ActivationError(
                "Helper runtime supervision changed after activation checkpoint"
            )
        supervision = dict(supervision)
        supervision.update(
            {
                "activationTransactionId": token,
                "schemaVersion": 1,
                "desiredState": "stopped",
                "consecutiveLaunchAttempts": 0,
                "nextLaunchAttemptAt": None,
                "healthySince": None,
            }
        )
        current["runtimeSupervision"] = supervision
        write_json(helper_path, current, app_support)
        helper_path.chmod(0o600)

    metadata = helper_path.lstat()
    payload["helperQuiescence"] = {
        "status": "applied",
        "token": token,
        "managedView": expected_managed_view,
        "device": metadata.st_dev,
        "inode": metadata.st_ino,
        "size": metadata.st_size,
        "sha256": sha256_file(helper_path),
    }
    write_json(transaction / MANIFEST_NAME, payload, transaction)
    return payload


def restore_helper_supervision(
    payload: dict[str, Any],
    transaction: Path,
    app_support_dir: Path,
) -> None:
    helper_path = contained(
        Path(str(payload.get("helperConfigFile") or "")),
        app_support_dir,
        "helper config",
    )
    helper_record = helper_state_record(payload)
    quiescence = payload.get("helperQuiescence")
    if payload.get("schemaVersion") == SCHEMA_VERSION:
        if not isinstance(quiescence, dict):
            return
        if quiescence.get("status") in {"not_present", "restored"}:
            return
        if quiescence.get("status") not in {"planned", "applied"}:
            raise ActivationError("Helper quiescence receipt is invalid")
    if not helper_record.get("existed"):
        if helper_path.exists() or helper_path.is_symlink():
            raise ActivationError(
                "Helper config appeared during activation; refusing to overwrite it"
            )
        return

    snapshot = contained(
        Path(str(helper_record.get("snapshot") or "")),
        transaction,
        "helper config snapshot",
    )
    snapshot_metadata = snapshot.lstat()
    current_metadata = helper_path.lstat()
    if (
        snapshot.is_symlink()
        or not stat.S_ISREG(snapshot_metadata.st_mode)
        or snapshot_metadata.st_uid != os.getuid()
        or helper_path.is_symlink()
        or not stat.S_ISREG(current_metadata.st_mode)
        or current_metadata.st_uid != os.getuid()
    ):
        raise ActivationError("Helper config supervision restore is unsafe")
    original = json.loads(snapshot.read_text(encoding="utf-8"))
    current = json.loads(helper_path.read_text(encoding="utf-8"))
    if not isinstance(original, dict) or not isinstance(current, dict):
        raise ActivationError("Helper config supervision restore requires JSON objects")

    original_supervision = original.get("runtimeSupervision")
    current_supervision = current.get("runtimeSupervision")
    if payload.get("schemaVersion") == SCHEMA_VERSION:
        token = str(quiescence.get("token") or "")
        current_token = (
            current_supervision.get("activationTransactionId")
            if isinstance(current_supervision, dict)
            else None
        )
        if not token or current_token != token:
            current_managed_view = helper_managed_view(current)
            process_receipt = payload.get("helperProcessQuiescence")
            running_paths = (
                process_receipt.get("runningExecutablePaths")
                if isinstance(process_receipt, dict)
                else None
            )
            legacy_shutdown_was_observed = (
                isinstance(process_receipt, dict)
                and process_receipt.get("status") == "applied"
                and process_receipt.get("wasRunning") is True
                and isinstance(running_paths, list)
                and bool(running_paths)
            )
            tokenless_applied_quiescence = (
                current_token is None
                and quiescence.get("status") == "applied"
                and current_managed_view == quiescence.get("managedView")
                and legacy_shutdown_was_observed
            )
            if tokenless_applied_quiescence:
                # A terminating legacy helper can flush the exact quiesced
                # managed values from stale in-memory state after its process
                # receipt is recorded, dropping only the transaction token.
                # Exact managed-view equality plus verified process absence
                # proves there is no user/runtime intent drift to overwrite.
                validate_helper_process_quiescence(payload)
            elif current_managed_view == helper_managed_view(original):
                return
            elif quiescence.get("status") == "planned":
                return
            else:
                raise ActivationError(
                    "Helper quiescence ownership changed before restoration"
                )
        expected_managed_view = (
            quiesced_helper_managed_view(original)
            if quiescence.get("status") == "planned"
            else quiescence.get("managedView")
        )
        if (
            not isinstance(expected_managed_view, dict)
            or helper_managed_view(current) != expected_managed_view
        ):
            raise ActivationError(
                "Helper runtime supervision changed after quiescence"
            )
    if isinstance(original_supervision, dict):
        if not isinstance(current_supervision, dict):
            raise ActivationError("Helper runtime supervision changed shape during activation")
        merged_supervision = dict(current_supervision)
        for field in HELPER_INTENT_MUTATED_FIELDS:
            if field in original_supervision:
                merged_supervision[field] = original_supervision[field]
            else:
                merged_supervision.pop(field, None)
        current["runtimeSupervision"] = merged_supervision
    elif "runtimeSupervision" in original:
        current["runtimeSupervision"] = original_supervision
    elif isinstance(current_supervision, dict):
        merged_supervision = {
            key: value
            for key, value in current_supervision.items()
            if key not in HELPER_INTENT_MUTATED_FIELDS
        }
        if merged_supervision:
            current["runtimeSupervision"] = merged_supervision
        else:
            current.pop("runtimeSupervision", None)
    else:
        current.pop("runtimeSupervision", None)

    if current == original:
        restore_state_file(helper_record, transaction, app_support_dir)
        return
    write_json(helper_path, current, app_support_dir)
    helper_path.chmod(0o600)
    directory_descriptor = os.open(helper_path.parent, os.O_RDONLY)
    try:
        os.fsync(directory_descriptor)
    finally:
        os.close(directory_descriptor)


def restore_activation_state_files(
    payload: dict[str, Any],
    transaction: Path,
    app_support_dir: Path,
) -> None:
    helper_path = contained(
        Path(str(payload.get("helperConfigFile") or "")),
        app_support_dir,
        "helper config",
    )
    helper_restored = False
    for record in payload.get("stateFiles", []):
        record_path = lexical(Path(str(record.get("path") or "")))
        if record_path == helper_path:
            if helper_restored:
                raise ActivationError("Activation helper snapshot is duplicated")
            restore_helper_supervision(payload, transaction, app_support_dir)
            helper_restored = True
        else:
            restore_state_file(record, transaction, app_support_dir)


def runtime_backup_path(payload: dict[str, Any]) -> Path | None:
    value = payload.get("runtimeBackup")
    if not value:
        return None
    runtime = lexical(Path(str(payload["runtimeDir"])))
    backup = lexical(Path(str(value)))
    if (
        backup.parent != runtime.parent
        or not backup.name.startswith(f".{runtime.name}.viventium-backup-")
    ):
        raise ActivationError("Generated runtime backup identity is invalid")
    return backup


def runtime_staging_path(payload: dict[str, Any]) -> Path | None:
    value = payload.get("runtimeStaging")
    if not value:
        return None
    runtime = lexical(Path(str(payload["runtimeDir"])))
    staging = lexical(Path(str(value)))
    if (
        staging.parent != runtime.parent
        or not staging.name.startswith(f".{runtime.name}.viventium-candidate-")
    ):
        raise ActivationError("Generated runtime staging identity is invalid")
    return staging


def classify_runtime_rollback_resources(
    payload: dict[str, Any],
    app_support_dir: Path,
) -> dict[str, Any]:
    runtime = validated_runtime_path(payload, app_support_dir)
    backup = runtime_backup_path(payload)
    staging = runtime_staging_path(payload)
    original = payload.get("runtimePrecondition")
    candidate = payload.get("runtimeCandidateIdentity")
    if not isinstance(original, dict):
        raise ActivationError("Generated runtime rollback checkpoint is missing")

    runtime_identity = owned_directory_identity(runtime, "published generated runtime")
    backup_identity = (
        owned_directory_identity(backup, "generated runtime rollback backup")
        if backup is not None
        else None
    )
    staging_identity = (
        owned_directory_identity(staging, "generated runtime staging")
        if staging is not None
        else None
    )
    runtime_kind = (
        "original"
        if identity_matches(runtime_identity, original)
        else "candidate"
        if identity_matches(runtime_identity, candidate)
        else "absent"
        if runtime_identity is None
        else "unexpected"
    )
    backup_kind = (
        "original"
        if identity_matches(backup_identity, original)
        else "absent"
        if backup_identity is None
        else "unexpected"
    )
    staging_kind = (
        "candidate"
        if identity_matches(staging_identity, candidate)
        else "absent"
        if staging_identity is None
        else "unexpected"
    )
    if "unexpected" in {runtime_kind, backup_kind, staging_kind}:
        raise ActivationError("Generated runtime rollback identity changed")
    if original.get("existed"):
        if runtime_kind == "original":
            if backup_kind != "absent":
                raise ActivationError("Generated runtime rollback state is ambiguous")
            if upgrade_transaction.surface_manifest(
                runtime,
                allow_symlinks=True,
            ) != original.get(
                "surfaceManifest"
            ):
                raise ActivationError("Original generated runtime changed")
        elif backup_kind != "original":
            raise ActivationError(
                "Original generated runtime rollback backup is unavailable"
            )
        else:
            assert backup is not None
            if upgrade_transaction.surface_manifest(
                backup,
                allow_symlinks=True,
            ) != original.get(
                "surfaceManifest"
            ):
                raise ActivationError("Generated runtime rollback backup changed")
        if runtime_kind not in {"original", "candidate", "absent"}:
            raise ActivationError("Generated runtime rollback state is invalid")
    else:
        if backup_kind != "absent":
            raise ActivationError("Unexpected generated runtime rollback backup exists")
        if runtime_kind not in {"candidate", "absent"}:
            raise ActivationError("Generated runtime rollback state is invalid")
    if staging_kind == "candidate" and runtime_kind == "candidate":
        raise ActivationError("Generated runtime candidate identity is duplicated")
    return {
        "runtime": runtime,
        "backup": backup,
        "staging": staging,
        "runtimeKind": runtime_kind,
        "backupKind": backup_kind,
        "stagingKind": staging_kind,
    }


def validate_prepared_runtime_resources(
    payload: dict[str, Any],
    app_support_dir: Path,
) -> None:
    runtime = validated_runtime_path(payload, app_support_dir)
    original = payload.get("runtimePrecondition")
    if not isinstance(original, dict):
        raise ActivationError("Generated runtime rollback checkpoint is missing")
    if any(
        payload.get(field) is not None
        for field in (
            "runtimeOriginallyPresent",
            "runtimeBackup",
            "runtimeStaging",
            "runtimeCandidateIdentity",
        )
    ):
        raise ActivationError("Prepared generated runtime state is ambiguous")
    current = owned_directory_identity(runtime, "generated runtime")
    if original.get("existed"):
        if not identity_matches(current, original):
            raise ActivationError("Original generated runtime identity changed")
    elif current is not None:
        raise ActivationError("Generated runtime appeared after activation checkpoint")


def restore_runtime_from_classification(classification: dict[str, Any]) -> None:
    runtime: Path = classification["runtime"]
    backup: Path | None = classification["backup"]
    staging: Path | None = classification["staging"]
    runtime_kind = classification["runtimeKind"]
    backup_kind = classification["backupKind"]
    staging_kind = classification["stagingKind"]
    failed: Path | None = None

    if backup_kind == "original":
        assert backup is not None
        if runtime_kind == "candidate":
            failed = runtime.parent / f".{runtime.name}.viventium-rejected-{uuid.uuid4().hex}"
            os.replace(runtime, failed)
        elif runtime_kind != "absent":
            raise ActivationError("Generated runtime rollback state is invalid")
        os.replace(backup, runtime)
    elif runtime_kind == "candidate":
        failed = runtime.parent / f".{runtime.name}.viventium-rejected-{uuid.uuid4().hex}"
        os.replace(runtime, failed)
    elif runtime_kind not in {"original", "absent"}:
        raise ActivationError("Generated runtime rollback state is invalid")

    if staging_kind == "candidate":
        assert staging is not None
        shutil.rmtree(staging)
    if failed is not None and failed.exists():
        shutil.rmtree(failed)


def rollback_legacy_runtime(
    payload: dict[str, Any],
    app_support_dir: Path,
) -> None:
    status = str(payload.get("status") or "")
    if status == "prepared":
        return
    if status not in {"publishing", "runtime_backed_up", "published"}:
        raise ActivationError("Legacy activation rollback stage is unsupported")

    runtime = validated_runtime_path(payload, app_support_dir)
    backup = runtime_backup_path(payload)
    staging = runtime_staging_path(payload)
    originally_present = payload.get("runtimeOriginallyPresent")
    if not isinstance(originally_present, bool):
        raise ActivationError("Legacy activation runtime origin is missing")

    runtime_present = (
        owned_directory_identity(runtime, "legacy published generated runtime")
        is not None
    )
    backup_present = (
        backup is not None
        and owned_directory_identity(
            backup,
            "legacy generated runtime rollback backup",
        )
        is not None
    )
    staging_present = (
        staging is not None
        and owned_directory_identity(
            staging,
            "legacy generated runtime staging",
        )
        is not None
    )

    restore_backup = False
    remove_runtime = False
    remove_staging = False
    if status == "publishing":
        if originally_present:
            if backup_present:
                if runtime_present and staging_present:
                    raise ActivationError(
                        "Legacy generated runtime rollback state is ambiguous"
                    )
                restore_backup = True
                remove_staging = staging_present
            elif runtime_present and staging_present:
                # The journal was persisted before the original runtime rename.
                remove_staging = True
            else:
                raise ActivationError(
                    "Legacy original generated runtime rollback state is incomplete"
                )
        else:
            if backup_present:
                raise ActivationError(
                    "Legacy generated runtime has an unexpected rollback backup"
                )
            if runtime_present == staging_present:
                raise ActivationError(
                    "Legacy fresh generated runtime rollback state is ambiguous"
                )
            remove_runtime = runtime_present
            remove_staging = staging_present
    elif status == "runtime_backed_up":
        if not originally_present or not backup_present:
            raise ActivationError(
                "Legacy original generated runtime rollback backup is unavailable"
            )
        if runtime_present and staging_present:
            raise ActivationError(
                "Legacy generated runtime candidate state is duplicated"
            )
        restore_backup = True
        remove_staging = staging_present
    else:
        if staging_present:
            raise ActivationError(
                "Legacy published generated runtime staging still exists"
            )
        if originally_present:
            if not backup_present or not runtime_present:
                raise ActivationError(
                    "Legacy published runtime rollback state is incomplete"
                )
            restore_backup = True
        else:
            if backup_present or not runtime_present:
                raise ActivationError(
                    "Legacy fresh published runtime rollback state is incomplete"
                )
            remove_runtime = True

    rejected: Path | None = None
    if restore_backup:
        assert backup is not None
        if runtime_present:
            rejected = (
                runtime.parent
                / f".{runtime.name}.viventium-rejected-{uuid.uuid4().hex}"
            )
            os.replace(runtime, rejected)
        os.replace(backup, runtime)
    elif remove_runtime:
        rejected = (
            runtime.parent
            / f".{runtime.name}.viventium-rejected-{uuid.uuid4().hex}"
        )
        os.replace(runtime, rejected)
    if remove_staging:
        assert staging is not None
        shutil.rmtree(staging)
    if rejected is not None and rejected.exists():
        shutil.rmtree(rejected)


def begin(args: argparse.Namespace) -> dict[str, Any]:
    app_support = lexical(args.app_support_dir)
    transaction = validate_private_directory(
        args.transaction_dir,
        app_support / "state",
        "activation transaction",
    )
    candidate = validate_private_directory(
        args.candidate_runtime,
        transaction,
        "candidate runtime",
    )
    return prepare_manifest(args, app_support, transaction, candidate)


def prepare_manifest(
    args: argparse.Namespace,
    app_support: Path,
    transaction: Path,
    candidate: Path,
) -> dict[str, Any]:
    runtime = validated_runtime_path(
        {"runtimeDir": str(args.runtime_dir)},
        app_support,
    )
    snapshots = transaction / "snapshots"
    snapshots.mkdir(mode=0o700, exist_ok=True)
    checkout_record = safe_file_snapshot(
        args.runtime_checkout_file,
        snapshots / "active-checkout.json",
        app_support_dir=app_support,
    )
    helper_record = safe_file_snapshot(
        args.helper_config_file,
        snapshots / "helper-config.json",
        app_support_dir=app_support,
    )
    candidate_env_record = safe_candidate_env_snapshot(
        args.candidate_repo,
        snapshots / "candidate-librechat.env",
    )
    runtime_precondition = safe_runtime_precondition(
        runtime,
        app_support_dir=app_support,
    )
    telegram_recovery_selection = ""
    if getattr(args, "telegram_recovery_selection", None):
        selection = contained(
            args.telegram_recovery_selection,
            app_support / "state" / "runtime-component-staging",
            "Telegram recovery selection",
        )
        validate_real_path_chain(
            selection,
            "Telegram recovery selection",
            owned_from=app_support,
        )
        metadata = selection.lstat()
        if (
            selection.is_symlink()
            or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or metadata.st_nlink != 1
            or stat.S_IMODE(metadata.st_mode) & 0o077
        ):
            raise ActivationError(
                "Telegram recovery selection is not an owner-private regular file"
            )
        telegram_recovery_selection = str(selection)
    payload = {
        "schemaVersion": SCHEMA_VERSION,
        "status": "prepared",
        "appSupportDir": str(app_support),
        "transactionDir": str(transaction),
        "candidateRuntime": str(candidate),
        "runtimeDir": str(runtime),
        "stateFiles": [checkout_record, helper_record],
        "helperConfigFile": str(
            contained(
                args.helper_config_file,
                app_support,
                "helper config",
            )
        ),
        "candidateEnv": candidate_env_record,
        "helperQuiescence": None,
        "helperProcessQuiescence": None,
        "helperProcessQuiescenceRequired": sys.platform == "darwin",
        "helperProcessRestoration": None,
        "ownerEnvMaterialized": None,
        "runtimePrecondition": runtime_precondition,
        "runtimeCandidateIdentity": None,
        "runtimeOriginallyPresent": None,
        "runtimeBackup": None,
        "runtimeStaging": None,
        "previousRepo": str(lexical(args.previous_repo)),
        "telegramPreferenceRoot": str(
            lexical(args.telegram_preference_root)
        )
        if args.telegram_preference_root
        else "",
        "telegramRecoverySelection": telegram_recovery_selection,
        "wasRunning": args.was_running,
    }
    write_json(transaction / MANIFEST_NAME, payload, transaction)
    return payload


def begin_new(args: argparse.Namespace) -> dict[str, Any]:
    app_support = lexical(args.app_support_dir)
    state = validate_private_directory(
        args.transaction_parent,
        app_support,
        "activation state root",
    )
    if state != app_support / "state":
        raise ActivationError("Activation state root is not canonical")
    transaction = Path(
        tempfile.mkdtemp(prefix="dev-runtime-activation.", dir=state)
    )
    transaction.chmod(0o700)
    candidate = transaction / "candidate-runtime"
    candidate.mkdir(mode=0o700)
    try:
        return prepare_manifest(args, app_support, transaction, candidate)
    except BaseException:
        shutil.rmtree(transaction, ignore_errors=True)
        raise


def publish(args: argparse.Namespace) -> dict[str, Any]:
    transaction, payload = load_manifest(args.transaction_dir, args.app_support_dir)
    if payload.get("status") != "prepared":
        raise ActivationError("Activation transaction is not prepared")
    candidate_env_record = payload.get("candidateEnv")
    if payload.get("schemaVersion") == SCHEMA_VERSION:
        if not isinstance(candidate_env_record, dict):
            raise ActivationError("Candidate LibreChat environment checkpoint is missing")
        validate_helper_quiescence(
            payload,
            transaction,
            lexical(args.app_support_dir),
        )
        validate_helper_process_quiescence(payload)
        validate_owner_env_plan(payload, transaction)
        validate_owner_env_materialized(payload, transaction)
    candidate = validate_private_directory(
        Path(str(payload["candidateRuntime"])),
        transaction,
        "candidate runtime",
    )
    runtime = validated_runtime_path(payload, lexical(args.app_support_dir))
    runtime_precondition = payload.get("runtimePrecondition")
    if not isinstance(runtime_precondition, dict):
        raise ActivationError("Generated runtime activation checkpoint is missing")
    validate_runtime_precondition(runtime, runtime_precondition)
    candidate_manifest = upgrade_transaction.surface_manifest(
        candidate,
        allow_symlinks=True,
    )
    runtime.parent.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    staging = runtime.parent / f".{runtime.name}.viventium-candidate-{token}"
    backup = runtime.parent / f".{runtime.name}.viventium-backup-{token}"
    try:
        shutil.copytree(
            candidate,
            staging,
            symlinks=True,
            copy_function=lambda source, destination: shutil.copy2(
                source,
                destination,
                follow_symlinks=False,
            ),
        )
        if (
            upgrade_transaction.surface_manifest(
                candidate,
                allow_symlinks=True,
            )
            != candidate_manifest
            or upgrade_transaction.surface_manifest(
                staging,
                allow_symlinks=True,
            )
            != candidate_manifest
        ):
            raise ActivationError(
                "Generated runtime candidate changed while it was staged"
            )
    except BaseException:
        if staging.exists() or staging.is_symlink():
            if staging.is_symlink() or not staging.is_dir():
                staging.unlink(missing_ok=True)
            else:
                shutil.rmtree(staging)
        raise
    staging_identity = owned_directory_identity(
        staging,
        "generated runtime candidate",
    )
    if staging_identity is None:
        raise ActivationError("Generated runtime candidate is unavailable")
    originally_present = runtime.exists() or runtime.is_symlink()
    if originally_present:
        metadata = runtime.lstat()
        if runtime.is_symlink() or not stat.S_ISDIR(metadata.st_mode):
            shutil.rmtree(staging)
            raise ActivationError("Live generated runtime is not a safe directory")
    payload["status"] = "publishing"
    payload["runtimeOriginallyPresent"] = originally_present
    payload["runtimeBackup"] = str(backup) if originally_present else None
    payload["runtimeStaging"] = str(staging)
    payload["runtimeCandidateIdentity"] = staging_identity
    write_json(transaction / MANIFEST_NAME, payload, transaction)
    if originally_present:
        os.replace(runtime, backup)
        payload["status"] = "runtime_backed_up"
        write_json(transaction / MANIFEST_NAME, payload, transaction)
    try:
        os.replace(staging, runtime)
    except Exception:
        if originally_present and backup.exists():
            os.replace(backup, runtime)
        raise
    payload["status"] = "published"
    write_json(transaction / MANIFEST_NAME, payload, transaction)
    return payload


def rollback(args: argparse.Namespace) -> dict[str, Any]:
    transaction, payload = load_manifest(args.transaction_dir, args.app_support_dir)
    if payload.get("status") == "rolled_back":
        return payload
    if payload.get("status") in {"core_committed", "committed"}:
        raise ActivationError("A committed activation cannot roll back")
    candidate_env_record = payload.get("candidateEnv")
    if payload.get("schemaVersion") == 1 and payload.get("status") == "binding_applied":
        raise ActivationError(
            "Legacy activation reached candidate startup without an exact LibreChat "
            "environment checkpoint; automatic rollback is not safe"
        )
    app_support = lexical(args.app_support_dir)
    if payload.get("schemaVersion") == 1:
        for record in payload.get("stateFiles", []):
            if not isinstance(record, dict):
                raise ActivationError("Activation state checkpoint is invalid")
            validate_legacy_state_file_snapshot(
                record,
                transaction,
                app_support,
            )
            validate_state_file_target(record, app_support)
        rollback_legacy_runtime(payload, app_support)
        restore_activation_state_files(payload, transaction, app_support)
        payload["status"] = "rolled_back"
        write_json(transaction / MANIFEST_NAME, payload, transaction)
        return payload
    if payload.get("schemaVersion") == SCHEMA_VERSION:
        if not isinstance(candidate_env_record, dict):
            raise ActivationError("Candidate LibreChat environment checkpoint is missing")
    if payload.get("status") == "prepared":
        validate_prepared_runtime_resources(payload, app_support)
        for record in payload.get("stateFiles", []):
            if not isinstance(record, dict):
                raise ActivationError("Activation state checkpoint is invalid")
            validate_state_file_snapshot(
                record,
                transaction,
                app_support,
            )
            validate_state_file_target(record, app_support)
        assert isinstance(candidate_env_record, dict)
        candidate_descriptor, _ = validate_candidate_env_checkpoint(
            candidate_env_record,
            transaction,
        )
        os.close(candidate_descriptor)
        materialized_evidence = materialized_candidate_env_receipt(
            candidate_env_record,
            payload,
            transaction,
        )
        if materialized_evidence is not None:
            restore_candidate_env_atomically(
                candidate_env_record,
                payload,
                transaction,
            )
        elif not cleanup_detached_owner_env_materialization(
            candidate_env_record,
            payload,
            transaction,
        ):
            cleanup_unbound_owner_env_materialization(
                candidate_env_record,
                payload,
                transaction,
            )
        # Prepared activation has not renamed runtime state or rebound the
        # checkout. Preserve their current bytes, including natural runtime
        # activity and concurrent owner edits, and restore only the helper
        # supervision fields the shell may already have quiesced.
        restore_helper_supervision(payload, transaction, app_support)
        set_helper_process_restoration_pending(payload)
        payload["status"] = "rolled_back"
        write_json(transaction / MANIFEST_NAME, payload, transaction)
        return payload
    runtime_classification = classify_runtime_rollback_resources(
        payload,
        app_support,
    )
    for record in payload.get("stateFiles", []):
        if not isinstance(record, dict):
            raise ActivationError("Activation state checkpoint is invalid")
        validate_state_file_snapshot(
            record,
            transaction,
            app_support,
        )
        validate_state_file_target(record, app_support)
    if isinstance(candidate_env_record, dict) and (
        materialized_candidate_env_receipt(
            candidate_env_record,
            payload,
            transaction,
        )
        is not None
        or isinstance(payload.get("ownerEnvAccepted"), dict)
    ):
        if isinstance(payload.get("ownerEnvAccepted"), dict) and isinstance(
            payload.get("ownerEnvPlan"),
            dict,
        ):
            claim_materialized_candidate_env_for_commit(
                candidate_env_record,
                payload,
                transaction,
            )
        restore_candidate_env_atomically(
            candidate_env_record,
            payload,
            transaction,
        )
        if isinstance(payload.get("ownerEnvAccepted"), dict) and isinstance(
            payload.get("ownerEnvPlan"),
            dict,
        ):
            cleanup_claimed_materialized_candidate_env(
                candidate_env_record,
                payload,
                transaction,
            )
    elif isinstance(candidate_env_record, dict):
        cleanup_detached_owner_env_materialization(
            candidate_env_record,
            payload,
            transaction,
        )
    restore_runtime_from_classification(runtime_classification)
    restore_activation_state_files(payload, transaction, app_support)
    set_helper_process_restoration_pending(payload)
    payload["status"] = "rolled_back"
    write_json(transaction / MANIFEST_NAME, payload, transaction)
    return payload


def commit(args: argparse.Namespace) -> dict[str, Any]:
    transaction, payload = load_manifest(args.transaction_dir, args.app_support_dir)
    if payload.get("status") in {"core_committed", "committed"}:
        return payload
    if payload.get("status") != "binding_applied":
        raise ActivationError("Only a bound activation can commit")
    app_support = lexical(args.app_support_dir)
    validated_runtime_path(payload, app_support)
    candidate_env_record = payload.get("candidateEnv")
    candidate_snapshot: Path | None = None
    accepted_name: str | None = None
    if payload.get("schemaVersion") == SCHEMA_VERSION:
        if not isinstance(candidate_env_record, dict):
            raise ActivationError("Candidate LibreChat environment checkpoint is missing")
        validate_helper_process_quiescence(payload)
        validate_owner_env_plan(payload, transaction)
        descriptor, candidate_snapshot = validate_candidate_env_checkpoint(
            candidate_env_record,
            transaction,
        )
        os.close(descriptor)
    runtime_classification = classify_runtime_rollback_resources(
        payload,
        app_support,
    )
    if runtime_classification["runtimeKind"] != "candidate":
        raise ActivationError("Candidate generated runtime is not the published runtime")
    if payload.get("runtimePrecondition", {}).get("existed"):
        if runtime_classification["backupKind"] != "original":
            raise ActivationError("Original generated runtime backup is unavailable")
    elif runtime_classification["backupKind"] != "absent":
        raise ActivationError("Unexpected generated runtime backup exists")
    for record in payload.get("stateFiles", []):
        if not isinstance(record, dict):
            raise ActivationError("Activation state checkpoint is invalid")
        validate_state_file_snapshot(record, transaction, app_support)
    backup = runtime_backup_path(payload)
    if backup is not None and backup.exists() and (
        backup.is_symlink() or not backup.is_dir()
    ):
        raise ActivationError("Generated runtime backup became unsafe")
    restore_helper_supervision(
        payload,
        transaction,
        app_support,
    )
    if isinstance(payload.get("ownerEnvPlan"), dict):
        assert isinstance(candidate_env_record, dict)
        validate_materialized_candidate_env_artifact(
            candidate_env_record,
            payload,
            transaction,
        )
        accepted = accept_candidate_env_for_commit(
            candidate_env_record,
            payload,
            transaction,
        )
        accepted_name = str(accepted["name"])
        validate_accepted_candidate_env_target(
            candidate_env_record,
            payload,
            transaction,
        )
        claim_materialized_candidate_env_for_commit(
            candidate_env_record,
            payload,
            transaction,
        )
    payload["status"] = "commit_env_finalizing"
    payload["ownerEnvChangedAfterAcceptance"] = False
    payload["ownerEnvAlignmentState"] = "pending"
    write_json(transaction / MANIFEST_NAME, payload, transaction)
    if isinstance(payload.get("ownerEnvPlan"), dict):
        assert isinstance(candidate_env_record, dict)
        try:
            validate_accepted_candidate_env_target(
                candidate_env_record,
                payload,
                transaction,
            )
        except ActivationError:
            # The accepted inode is the durable owner file, so a post-boundary
            # edit is preserved. Record that a running candidate must restart
            # once more before helper finalization can represent it as aligned.
            payload["ownerEnvChangedAfterAcceptance"] = True
            payload["ownerEnvAlignmentState"] = "required"
        else:
            payload["ownerEnvAligned"] = dict(payload["ownerEnvAccepted"])
            payload["ownerEnvAlignmentState"] = "aligned"
    payload["status"] = "core_committed"
    write_json(transaction / MANIFEST_NAME, payload, transaction)
    if isinstance(candidate_env_record, dict):
        try:
            cleanup_candidate_env_transaction_links(
                candidate_env_record,
                payload,
                transaction,
            )
        except (ActivationError, OSError):
            payload["ownerEnvCleanupState"] = "pending"
        else:
            payload["ownerEnvCleanupState"] = "complete"
        try:
            write_json(transaction / MANIFEST_NAME, payload, transaction)
        except OSError:
            pass
    if backup is not None and backup.exists():
        # Commit is already durable. If the cleanup identity changes after the
        # pre-commit check, leave it untouched instead of reporting a failure
        # that would make the shell attempt an unsafe post-commit rollback.
        if backup.is_symlink() or not backup.is_dir():
            return payload
        try:
            shutil.rmtree(backup)
        except OSError:
            # The activation is already committed. A stale private generated
            # runtime backup is safer than rolling binding/runtime state back
            # after the healthy candidate has been accepted.
            pass
    return payload


def finalize_helper(args: argparse.Namespace) -> dict[str, Any]:
    transaction, payload = load_manifest(args.transaction_dir, args.app_support_dir)
    if payload.get("status") == "committed":
        return payload
    if payload.get("status") != "core_committed":
        raise ActivationError(
            "Helper finalization requires a committed runtime activation"
        )
    if owner_env_alignment_required(payload, transaction):
        raise ActivationError(
            "Candidate LibreChat owner environment requires an alignment restart"
        )
    candidate_env_record = payload.get("candidateEnv")
    if isinstance(candidate_env_record, dict):
        try:
            cleanup_candidate_env_transaction_links(
                candidate_env_record,
                payload,
                transaction,
            )
        except (ActivationError, OSError) as error:
            payload["ownerEnvCleanupState"] = "pending"
            write_json(transaction / MANIFEST_NAME, payload, transaction)
            raise ActivationError(
                "Candidate LibreChat owner-environment cleanup remains pending"
            ) from error
        payload["ownerEnvCleanupState"] = "complete"
    payload["status"] = "committed"
    write_json(transaction / MANIFEST_NAME, payload, transaction)
    return payload


def alignment_status(args: argparse.Namespace) -> dict[str, Any]:
    transaction, payload = load_manifest(args.transaction_dir, args.app_support_dir)
    if payload.get("status") not in {"core_committed", "committed"}:
        raise ActivationError(
            "Owner environment alignment requires a committed runtime activation"
        )
    candidate_env_record = payload.get("candidateEnv")
    if isinstance(candidate_env_record, dict):
        try:
            cleanup_candidate_env_transaction_links(
                candidate_env_record,
                payload,
                transaction,
            )
        except (ActivationError, OSError):
            payload["ownerEnvCleanupState"] = "pending"
        else:
            payload["ownerEnvCleanupState"] = "complete"
        try:
            write_json(transaction / MANIFEST_NAME, payload, transaction)
        except OSError:
            pass
    current_receipt = None
    if isinstance(payload.get("ownerEnvPlan"), dict):
        if not isinstance(candidate_env_record, dict):
            raise ActivationError(
                "Candidate LibreChat environment checkpoint is missing"
            )
        current_receipt = current_candidate_env_receipt(
            candidate_env_record,
            transaction,
        )
    return {
        "currentReceipt": current_receipt,
        "required": owner_env_alignment_required(payload, transaction),
        "cleanupState": payload.get("ownerEnvCleanupState", "not_applicable"),
        "state": payload.get("ownerEnvAlignmentState", "not_applicable"),
    }


def mark_aligned(args: argparse.Namespace) -> dict[str, Any]:
    transaction, payload = load_manifest(args.transaction_dir, args.app_support_dir)
    if payload.get("status") != "core_committed":
        raise ActivationError(
            "Owner environment alignment acknowledgement requires core commit"
        )
    candidate_env_record = payload.get("candidateEnv")
    if isinstance(payload.get("ownerEnvPlan"), dict):
        if not isinstance(candidate_env_record, dict):
            raise ActivationError(
                "Candidate LibreChat environment checkpoint is missing"
            )
        current_receipt = current_candidate_env_receipt(
            candidate_env_record,
            transaction,
        )
        if args.expected_receipt_json:
            expected_receipt = json.loads(args.expected_receipt_json)
            if not isinstance(expected_receipt, dict) or any(
                expected_receipt.get(field) != current_receipt.get(field)
                for field in ("size", "sha256")
            ):
                raise ActivationError(
                    "Candidate LibreChat owner environment changed during "
                    "the alignment restart"
                )
        payload["ownerEnvAligned"] = current_receipt
        payload["ownerEnvAlignmentState"] = "aligned"
        payload["ownerEnvChangedAfterAcceptance"] = False
        write_json(transaction / MANIFEST_NAME, payload, transaction)
        cleanup_candidate_env_transaction_links(
            candidate_env_record,
            payload,
            transaction,
        )
    return payload


def mark_binding_applied(args: argparse.Namespace) -> dict[str, Any]:
    transaction, payload = load_manifest(args.transaction_dir, args.app_support_dir)
    if payload.get("status") == "binding_applied":
        return payload
    if payload.get("status") != "published":
        raise ActivationError("Generated runtime must publish before binding is accepted")
    payload["status"] = "binding_applied"
    write_json(transaction / MANIFEST_NAME, payload, transaction)
    return payload


def status(args: argparse.Namespace) -> dict[str, Any]:
    _, payload = load_manifest(args.transaction_dir, args.app_support_dir)
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in (
        "begin",
        "begin-new",
        "quiesce-helper",
        "quiesce-helper-process",
        "helper-process-status",
        "restore-helper-process",
        "publish",
        "owner-env-planned",
        "owner-env-materialized",
        "binding-applied",
        "rollback",
        "commit",
        "alignment-status",
        "mark-aligned",
        "finalize-helper",
        "status",
    ):
        child = commands.add_parser(name)
        if name == "begin-new":
            child.add_argument("--transaction-parent", type=Path, required=True)
        else:
            child.add_argument("--transaction-dir", type=Path, required=True)
        child.add_argument("--app-support-dir", type=Path, required=True)
        if name == "owner-env-planned":
            child.add_argument("--owner-env-manifest", type=Path, required=True)
        if name == "mark-aligned":
            child.add_argument("--expected-receipt-json")
        if name == "quiesce-helper-process":
            child.add_argument(
                "--helper-executable",
                action="append",
                type=Path,
                required=True,
            )
            child.add_argument("--timeout-seconds", type=float, default=10.0)
        if name == "restore-helper-process":
            child.add_argument("--timeout-seconds", type=float, default=10.0)
        if name in {"begin", "begin-new"}:
            if name == "begin":
                child.add_argument("--candidate-runtime", type=Path, required=True)
            child.add_argument("--runtime-dir", type=Path, required=True)
            child.add_argument("--runtime-checkout-file", type=Path, required=True)
            child.add_argument("--helper-config-file", type=Path, required=True)
            child.add_argument("--previous-repo", type=Path, required=True)
            child.add_argument("--candidate-repo", type=Path, required=True)
            child.add_argument("--telegram-preference-root", type=Path)
            child.add_argument("--telegram-recovery-selection", type=Path)
            child.add_argument(
                "--was-running",
                action=argparse.BooleanOptionalAction,
                default=False,
            )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = {
            "begin": begin,
            "begin-new": begin_new,
            "quiesce-helper": quiesce_helper,
            "quiesce-helper-process": quiesce_helper_process,
            "helper-process-status": helper_process_status,
            "restore-helper-process": restore_helper_process,
            "publish": publish,
            "owner-env-planned": plan_owner_env,
            "owner-env-materialized": mark_owner_env_materialized,
            "binding-applied": mark_binding_applied,
            "rollback": rollback,
            "commit": commit,
            "alignment-status": alignment_status,
            "mark-aligned": mark_aligned,
            "finalize-helper": finalize_helper,
            "status": status,
        }[args.command](args)
    except (ActivationError, OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Viventium dev-runtime activation failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

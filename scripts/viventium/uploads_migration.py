#!/usr/bin/env python3
"""Move source-install uploads into canonical Viventium App Support storage.

The Viventium LibreChat fork resolves uploads from the compiler-owned App
Support environment path. This helper still owns the one-time predecessor
migration and its checkout-local compatibility link. Concurrent runtimes may
share a checkout: a receipted link belonging to another App Support root is
preserved without following it while the current canonical root is initialized.
The helper never merges trees and journals activation so interrupted launch can
recover before LibreChat is allowed to start.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import shutil
import stat
import sys
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
MAX_FILE_BYTES = 64 * 1024 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024 * 1024
MAX_FILE_COUNT = 100_000
MAX_ENTRY_COUNT = 200_000
MAX_PATH_BYTES = 1024
MAX_PATH_DEPTH = 32
COPY_BUFFER_BYTES = 1024 * 1024
MIN_FREE_AFTER_MIGRATION_BYTES = 64 * 1024 * 1024
SHARED_LINK_SETTLE_SECONDS = 5.0
SHARED_LINK_POLL_SECONDS = 0.05
_MIGRATION_THREAD_LOCKS: dict[str, threading.Lock] = {}
_MIGRATION_THREAD_LOCKS_GUARD = threading.Lock()


class MigrationError(RuntimeError):
    """A fail-closed migration or recovery error."""


class InjectedCrash(BaseException):
    """Test-only abrupt interruption that intentionally bypasses rollback."""


@contextlib.contextmanager
def uploads_migration_lock(state_dir: Path):
    """Serialize one App Support migration across threads and processes."""

    lock_path = state_dir / "migration.lock"
    lock_key = str(lexical(lock_path))
    with _MIGRATION_THREAD_LOCKS_GUARD:
        thread_lock = _MIGRATION_THREAD_LOCKS.setdefault(lock_key, threading.Lock())
    with thread_lock:
        flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(lock_path, flags, 0o600)
        except OSError as error:
            raise MigrationError("Uploads migration lock could not be opened safely") from error
        try:
            metadata = os.fstat(descriptor)
            if (
                not stat.S_ISREG(metadata.st_mode)
                or metadata.st_uid != os.getuid()
                or metadata.st_nlink != 1
                or metadata.st_mode & 0o077
            ):
                raise MigrationError("Uploads migration lock is unsafe")
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            finally:
                os.close(descriptor)


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def lexical(path: Path) -> Path:
    return Path(os.path.abspath(os.path.expanduser(str(path))))


def assert_contained(path: Path, root: Path, label: str) -> None:
    try:
        common = os.path.commonpath([str(path), str(root)])
    except ValueError as error:
        raise MigrationError(f"{label} cannot be bounded safely") from error
    if common != str(root):
        raise MigrationError(f"{label} escapes its required root")


def lstat_optional(path: Path) -> os.stat_result | None:
    try:
        return path.lstat()
    except FileNotFoundError:
        return None


def validate_owned_directory(path: Path, label: str) -> os.stat_result:
    metadata = lstat_optional(path)
    if metadata is None:
        raise MigrationError(f"{label} is missing")
    if stat.S_ISLNK(metadata.st_mode):
        raise MigrationError(f"{label} must not be a symlink")
    if not stat.S_ISDIR(metadata.st_mode):
        raise MigrationError(f"{label} must be a directory")
    if metadata.st_uid != os.getuid():
        raise MigrationError(f"{label} has an unexpected owner")
    return metadata


def ensure_private_directory(path: Path, *, bounded_by: Path) -> None:
    path = lexical(path)
    bounded_by = lexical(bounded_by)
    assert_contained(path, bounded_by, "Private directory")
    relative = path.relative_to(bounded_by)
    current = bounded_by
    validate_owned_directory(current, "Viventium App Support")
    for part in relative.parts:
        current = current / part
        metadata = lstat_optional(current)
        if metadata is None:
            try:
                current.mkdir(mode=0o700)
            except FileExistsError:
                pass
            metadata = current.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise MigrationError("Private storage path contains a non-directory or symlink")
        if metadata.st_uid != os.getuid():
            raise MigrationError("Private storage path has an unexpected owner")
        current.chmod(0o700)


def _relative_record(relative: Path) -> bytes:
    raw = os.fsencode(str(relative))
    if len(raw) > MAX_PATH_BYTES:
        raise MigrationError("Uploads path-length bound exceeded")
    if len(relative.parts) > MAX_PATH_DEPTH:
        raise MigrationError("Uploads path-depth bound exceeded")
    return raw


def _hash_regular_file(path: Path, metadata: os.stat_result) -> bytes:
    if metadata.st_nlink != 1:
        raise MigrationError("Uploads tree contains a hardlink")
    if metadata.st_size > MAX_FILE_BYTES:
        raise MigrationError("Uploads per-file size bound exceeded")
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        identity_before = (
            metadata.st_dev,
            metadata.st_ino,
            metadata.st_size,
            metadata.st_mtime_ns,
            metadata.st_ctime_ns,
        )
        identity_opened = (
            opened.st_dev,
            opened.st_ino,
            opened.st_size,
            opened.st_mtime_ns,
            opened.st_ctime_ns,
        )
        if not stat.S_ISREG(opened.st_mode) or identity_opened != identity_before:
            raise MigrationError("Uploads file changed during validation")
        digest = hashlib.sha256()
        while True:
            chunk = os.read(descriptor, COPY_BUFFER_BYTES)
            if not chunk:
                break
            digest.update(chunk)
        after = os.fstat(descriptor)
        identity_after = (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        if identity_after != identity_opened:
            raise MigrationError("Uploads file changed during validation")
        return digest.digest()
    finally:
        os.close(descriptor)


def fingerprint_tree(root: Path) -> dict[str, Any]:
    """Return a privacy-safe, root-independent semantic tree fingerprint."""

    root = lexical(root)
    root_metadata = validate_owned_directory(root, "Uploads root")
    if root_metadata.st_uid != os.getuid():
        raise MigrationError("Uploads root has an unexpected owner")

    tree_digest = hashlib.sha256()
    file_count = 0
    entry_count = 0
    total_bytes = 0
    pending: list[tuple[Path, Path]] = [(root, Path("."))]
    while pending:
        directory, relative_directory = pending.pop()
        metadata = directory.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise MigrationError("Uploads tree contains a symlink or non-directory")
        if metadata.st_uid != os.getuid():
            raise MigrationError("Uploads tree has an unexpected owner")
        if relative_directory != Path("."):
            encoded_directory = _relative_record(relative_directory)
            tree_digest.update(b"D\0")
            tree_digest.update(len(encoded_directory).to_bytes(4, "big"))
            tree_digest.update(encoded_directory)
        try:
            entries = sorted(os.scandir(directory), key=lambda entry: os.fsencode(entry.name))
        except OSError as error:
            raise MigrationError("Uploads tree could not be enumerated safely") from error
        child_directories: list[tuple[Path, Path]] = []
        for entry in entries:
            entry_count += 1
            if entry_count > MAX_ENTRY_COUNT:
                raise MigrationError("Uploads entry-count bound exceeded")
            relative = (
                Path(entry.name)
                if relative_directory == Path(".")
                else relative_directory / entry.name
            )
            encoded = _relative_record(relative)
            try:
                item_metadata = entry.stat(follow_symlinks=False)
            except OSError as error:
                raise MigrationError("Uploads entry could not be inspected safely") from error
            if item_metadata.st_uid != os.getuid():
                raise MigrationError("Uploads tree has an unexpected owner")
            if stat.S_ISLNK(item_metadata.st_mode):
                raise MigrationError("Uploads tree contains a symlink")
            if stat.S_ISDIR(item_metadata.st_mode):
                child_directories.append((Path(entry.path), relative))
                continue
            if not stat.S_ISREG(item_metadata.st_mode):
                raise MigrationError("Uploads tree contains a special file")
            file_count += 1
            if file_count > MAX_FILE_COUNT:
                raise MigrationError("Uploads file-count bound exceeded")
            total_bytes += item_metadata.st_size
            if total_bytes > MAX_TOTAL_BYTES:
                raise MigrationError("Uploads total-size bound exceeded")
            content_digest = _hash_regular_file(Path(entry.path), item_metadata)
            tree_digest.update(b"F\0")
            tree_digest.update(len(encoded).to_bytes(4, "big"))
            tree_digest.update(encoded)
            tree_digest.update(item_metadata.st_size.to_bytes(8, "big"))
            tree_digest.update(content_digest)
        pending.extend(reversed(child_directories))
    return {
        "fileCount": file_count,
        "totalBytes": total_bytes,
        "treeSha256": tree_digest.hexdigest(),
    }


def tree_has_entries(root: Path) -> bool:
    try:
        with os.scandir(root) as entries:
            return next(entries, None) is not None
    except OSError as error:
        raise MigrationError("Uploads root could not be enumerated safely") from error


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    ensure_private_directory(path.parent, bounded_by=path.parents[3])
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(0o600)
        os.replace(temporary, path)
        path.chmod(0o600)
        fsync_directory(path.parent)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        try:
            os.fsync(descriptor)
        except OSError:
            # Some supported filesystems reject directory fsync. The journal
            # remains fail-closed there, but file fsync and atomic rename still
            # provide the strongest portable ordering available.
            pass
    finally:
        os.close(descriptor)


def read_private_json(path: Path) -> dict[str, Any]:
    metadata = lstat_optional(path)
    if metadata is None:
        raise MigrationError("Migration transaction metadata is missing")
    if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        raise MigrationError("Migration transaction metadata is unsafe")
    if metadata.st_uid != os.getuid() or metadata.st_nlink != 1:
        raise MigrationError("Migration transaction metadata has an unexpected owner or hardlink")
    if metadata.st_mode & 0o077:
        raise MigrationError("Migration transaction metadata is not owner-only")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise MigrationError("Migration transaction metadata is invalid") from error
    if not isinstance(payload, dict):
        raise MigrationError("Migration transaction metadata is invalid")
    return payload


def copy_tree_no_follow(source: Path, destination: Path) -> None:
    if lstat_optional(destination) is not None:
        raise MigrationError("Migration staging path already exists")
    destination.mkdir(mode=0o700)
    pending: list[tuple[Path, Path]] = [(source, destination)]
    while pending:
        source_directory, destination_directory = pending.pop()
        entries = sorted(os.scandir(source_directory), key=lambda entry: os.fsencode(entry.name))
        child_directories: list[tuple[Path, Path]] = []
        for entry in entries:
            source_path = Path(entry.path)
            destination_path = destination_directory / entry.name
            metadata = entry.stat(follow_symlinks=False)
            if metadata.st_uid != os.getuid():
                raise MigrationError("Uploads tree has an unexpected owner")
            if stat.S_ISLNK(metadata.st_mode):
                raise MigrationError("Uploads tree contains a symlink")
            if stat.S_ISDIR(metadata.st_mode):
                destination_path.mkdir(mode=0o700)
                child_directories.append((source_path, destination_path))
                continue
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                raise MigrationError("Uploads tree contains a special file or hardlink")
            source_flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
            source_descriptor = os.open(source_path, source_flags)
            destination_descriptor = os.open(
                destination_path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
            try:
                opened_source = os.fstat(source_descriptor)
                if (
                    not stat.S_ISREG(opened_source.st_mode)
                    or opened_source.st_dev != metadata.st_dev
                    or opened_source.st_ino != metadata.st_ino
                    or opened_source.st_size != metadata.st_size
                    or opened_source.st_nlink != 1
                ):
                    raise MigrationError("Uploads file changed during migration")
                copied = 0
                while True:
                    chunk = os.read(source_descriptor, COPY_BUFFER_BYTES)
                    if not chunk:
                        break
                    view = memoryview(chunk)
                    while view:
                        written = os.write(destination_descriptor, view)
                        view = view[written:]
                    copied += len(chunk)
                if copied != metadata.st_size:
                    raise MigrationError("Uploads file changed during migration")
                os.fsync(destination_descriptor)
            finally:
                os.close(source_descriptor)
                os.close(destination_descriptor)
            destination_path.chmod(0o600)
        pending.extend(reversed(child_directories))


def remove_owned_tree(path: Path, expected: dict[str, Any] | None = None) -> None:
    if lstat_optional(path) is None:
        return
    actual = fingerprint_tree(path)
    if expected is not None and actual != expected:
        raise MigrationError("Transaction-owned uploads tree changed unexpectedly")
    shutil.rmtree(path)


def exact_link_to(path: Path, target: Path) -> bool:
    metadata = lstat_optional(path)
    if metadata is None or not stat.S_ISLNK(metadata.st_mode):
        return False
    try:
        return lexical(Path(os.readlink(path))) == target
    except OSError:
        return False


def resolved_link_target(path: Path) -> Path:
    try:
        raw_target = Path(os.readlink(path))
    except OSError as error:
        raise MigrationError("Legacy uploads compatibility link is unreadable") from error
    if not raw_target.is_absolute():
        raw_target = path.parent / raw_target
    return lexical(raw_target)


def hash_path_identity(path: Path) -> str:
    return hashlib.sha256(os.fsencode(str(lexical(path)))).hexdigest()


def is_preserved_link_receipt(payload: dict[str, Any]) -> bool:
    target_digest = payload.get("observedLinkTargetSha256")
    return (
        payload.get("schemaVersion") == SCHEMA_VERSION
        and payload.get("legacyCompatibility")
        == "other_runtime_exact_symlink_preserved"
        and payload.get("mode") == "isolated_runtime_root"
        and payload.get("canonicalStorage") == "app_support_data_uploads"
        and isinstance(target_digest, str)
        and len(target_digest) == 64
        and all(character in "0123456789abcdef" for character in target_digest)
    )


def preserved_link_receipt_matches(payload: dict[str, Any], target: Path) -> bool:
    return is_preserved_link_receipt(payload) and payload.get(
        "observedLinkTargetSha256"
    ) == hash_path_identity(target)


def is_plausible_other_runtime_link(*, legacy: Path, canonical: Path) -> bool:
    """Validate another runtime's storage shape without reading its uploads."""

    try:
        if not Path(os.readlink(legacy)).is_absolute():
            return False
        target = resolved_link_target(legacy)
        if target == canonical or target.name != "uploads" or target.parent.name != "data":
            return False
        other_app_support = target.parent.parent
        if other_app_support == canonical.parent.parent:
            return False
        for path, label in (
            (other_app_support, "Other Viventium App Support"),
            (target.parent, "Other Viventium data root"),
            (target, "Other Viventium uploads root"),
            (other_app_support / "state", "Other Viventium state root"),
            (other_app_support / "state" / "continuity", "Other Viventium continuity root"),
            (
                other_app_support / "state" / "continuity" / "uploads-migration",
                "Other Viventium uploads migration root",
            ),
        ):
            validate_owned_directory(path, label)
        return True
    except MigrationError:
        return False


def is_recognized_other_runtime_link(*, legacy: Path, canonical: Path) -> bool:
    """Validate another Viventium runtime's receipted compatibility link."""

    try:
        if not is_plausible_other_runtime_link(legacy=legacy, canonical=canonical):
            return False
        target = resolved_link_target(legacy)
        other_app_support = target.parent.parent
        receipt = read_private_json(
            other_app_support
            / "state"
            / "continuity"
            / "uploads-migration"
            / "receipt.json"
        )
        transaction_id = receipt.get("transactionId")
        return (
            receipt.get("schemaVersion") == SCHEMA_VERSION
            and receipt.get("legacyCompatibility") == "exact_symlink"
            and receipt.get("canonicalStorage") == "app_support_data_uploads"
            and receipt.get("mode") in {"migrate", "adopt", "create"}
            and isinstance(transaction_id, str)
            and len(transaction_id) == 32
            and all(character in "0123456789abcdef" for character in transaction_id)
        )
    except MigrationError:
        return False


def wait_for_recognized_other_runtime_link(*, legacy: Path, canonical: Path) -> Path:
    """Resolve a concurrent runtime's winning link after its receipt is durable."""

    deadline = time.monotonic() + SHARED_LINK_SETTLE_SECONDS
    while True:
        metadata = lstat_optional(legacy)
        if metadata is not None and not stat.S_ISLNK(metadata.st_mode):
            raise MigrationError(
                "Concurrent uploads compatibility path is not a symlink"
            )
        if metadata is not None:
            target = resolved_link_target(legacy)
            if target == canonical:
                return target
            if is_recognized_other_runtime_link(legacy=legacy, canonical=canonical):
                return target
        if time.monotonic() >= deadline:
            raise MigrationError(
                "Concurrent uploads compatibility link did not become receipted"
            )
        time.sleep(SHARED_LINK_POLL_SECONDS)


def defer_populated_legacy_tree_during_active_outer_upgrade(
    *,
    app_support: Path,
    librechat: Path,
    legacy: Path,
    canonical: Path,
) -> dict[str, Any] | None:
    """Keep predecessor bytes in place until its immutable outer transaction commits.

    Supported predecessor runners checkpoint App Support data but did not checkpoint
    the ignored nested ``LibreChat/uploads`` tree. Moving that tree while their outer
    transaction is active would make a later rollback restore an absent canonical
    target behind a broken symlink. The successor therefore validates against the
    still-authoritative legacy tree and finalizes canonical placement only from the
    post-commit helper hook.
    """

    pointer = app_support / "state" / "upgrade-transaction-active.json"
    if not pointer.exists() and not pointer.is_symlink():
        return None
    try:
        import upgrade_transaction

        upgrade_transaction.validate_chain(pointer, owned_from=app_support)
        pointer_metadata = pointer.lstat()
        if (
            pointer.is_symlink()
            or not pointer.is_file()
            or pointer_metadata.st_uid != os.getuid()
        ):
            raise MigrationError("Active outer upgrade transaction pointer is unsafe")
        payload = json.loads(pointer.read_text(encoding="utf-8"))
        transaction = upgrade_transaction.lexical(
            Path(str(payload.get("transaction_path") or ""))
        )
        ledger = upgrade_transaction.load_ledger(transaction)
        repo_root = upgrade_transaction.lexical(Path(str(ledger.get("repo_root") or "")))
        if (
            payload.get("schema_version") != upgrade_transaction.SCHEMA_VERSION
            or ledger.get("status") != "active"
            or ledger.get("stage") not in {"candidate_activated", "restart_healthy"}
            or repo_root / "viventium_v0_4" / "LibreChat" != librechat
        ):
            raise MigrationError("Active outer upgrade transaction scope is inconsistent")
    except MigrationError:
        raise
    except Exception as error:
        raise MigrationError("Active outer upgrade transaction proof failed") from error

    legacy_metadata = lstat_optional(legacy)
    if (
        legacy_metadata is None
        or stat.S_ISLNK(legacy_metadata.st_mode)
        or not stat.S_ISDIR(legacy_metadata.st_mode)
    ):
        return None
    validate_owned_directory(legacy, "Legacy uploads root")
    fingerprint = fingerprint_tree(legacy)
    if not tree_has_entries(legacy):
        return None

    canonical_metadata = lstat_optional(canonical)
    if canonical_metadata is not None:
        validate_owned_directory(canonical, "Canonical uploads root")
        if tree_has_entries(canonical):
            return None
    return {
        "schemaVersion": SCHEMA_VERSION,
        "status": "deferred_until_outer_commit",
        "mode": "migrate",
        "fingerprint": fingerprint,
    }


def _transaction_paths(
    txid: str,
    canonical: Path,
    librechat: Path,
) -> tuple[Path, Path, Path]:
    return (
        canonical.parent / f".uploads.migration-stage.{txid}",
        librechat / f".uploads.migration-backup.{txid}",
        canonical.parent / f".uploads.migration-target-backup.{txid}",
    )


def recover_transaction(
    *,
    journal: Path,
    receipt: Path,
    legacy: Path,
    canonical: Path,
    librechat: Path,
) -> None:
    state = read_private_json(journal)
    if state.get("schemaVersion") != SCHEMA_VERSION:
        raise MigrationError("Migration transaction schema is unsupported")
    txid = state.get("transactionId")
    mode = state.get("mode")
    fingerprint = state.get("fingerprint")
    if (
        not isinstance(txid, str)
        or len(txid) != 32
        or any(character not in "0123456789abcdef" for character in txid)
        or mode not in {"migrate", "adopt", "create"}
        or not isinstance(fingerprint, dict)
    ):
        raise MigrationError("Migration transaction metadata is invalid")
    stage, source_backup, target_backup = _transaction_paths(txid, canonical, librechat)

    if state.get("phase") == "committed":
        receipt_payload = read_private_json(receipt)
        if (
            receipt_payload.get("transactionId") != txid
            or not exact_link_to(legacy, canonical)
            or fingerprint_tree(canonical) != fingerprint
        ):
            raise MigrationError(
                "Committed uploads migration proof is inconsistent; refusing destructive recovery"
            )
        if lstat_optional(stage) is not None:
            remove_owned_tree(stage, fingerprint)
        if lstat_optional(source_backup) is not None:
            remove_owned_tree(
                source_backup,
                fingerprint if mode == "migrate" else None,
            )
        if lstat_optional(target_backup) is not None:
            remove_owned_tree(target_backup)
        journal.unlink()
        fsync_directory(journal.parent)
        return

    if exact_link_to(legacy, canonical):
        legacy.unlink()
        fsync_directory(librechat)
    elif lstat_optional(legacy) is not None and state.get("sourceBackedUp"):
        raise MigrationError("Interrupted migration source changed; manual recovery is required")

    if lstat_optional(source_backup) is not None:
        if lstat_optional(legacy) is not None:
            raise MigrationError("Interrupted migration has conflicting source roots")
        fingerprint_tree(source_backup)
        os.replace(source_backup, legacy)
        fsync_directory(librechat)

    target_owned = mode in {"migrate", "create"} and (
        bool(state.get("targetActivated"))
        or (
            bool(state.get("targetActivationPending"))
            and lstat_optional(stage) is None
            and lstat_optional(canonical) is not None
        )
    )
    if target_owned and lstat_optional(canonical) is not None:
        remove_owned_tree(canonical, fingerprint)
        fsync_directory(canonical.parent)

    if lstat_optional(target_backup) is not None:
        if lstat_optional(canonical) is not None:
            raise MigrationError("Interrupted migration has conflicting canonical roots")
        empty_fingerprint = fingerprint_tree(target_backup)
        if empty_fingerprint["fileCount"] != 0 or tree_has_entries(target_backup):
            raise MigrationError("Interrupted migration target backup is not empty")
        os.replace(target_backup, canonical)
        fsync_directory(canonical.parent)

    if lstat_optional(stage) is not None:
        remove_owned_tree(stage, fingerprint)

    receipt_metadata = lstat_optional(receipt)
    if receipt_metadata is not None:
        receipt_payload = read_private_json(receipt)
        if receipt_payload.get("transactionId") != txid:
            raise MigrationError("Migration receipt conflicts with interrupted transaction")
        receipt.unlink()
    journal.unlink()
    fsync_directory(journal.parent)


def _commit_transaction(
    *,
    app_support: Path,
    librechat: Path,
    legacy: Path,
    canonical: Path,
    journal: Path,
    receipt: Path,
    mode: str,
    fingerprint: dict[str, Any],
    source_present: bool,
    target_empty_present: bool,
    fault_after: str | None,
) -> dict[str, Any]:
    txid = uuid.uuid4().hex
    stage, source_backup, target_backup = _transaction_paths(txid, canonical, librechat)
    state: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "transactionId": txid,
        "mode": mode,
        "phase": "prepared",
        "fingerprint": fingerprint,
        "sourcePresent": source_present,
        "sourceBackedUp": False,
        "targetEmptyPresent": target_empty_present,
        "targetBackedUp": False,
        "targetActivationPending": False,
        "targetActivated": False,
        "linkActivated": False,
    }
    write_json_atomic(journal, state)
    try:
        if mode in {"migrate", "create"}:
            if mode == "migrate":
                available = shutil.disk_usage(canonical.parent).free
                required = fingerprint["totalBytes"] + MIN_FREE_AFTER_MIGRATION_BYTES
                if available < required:
                    raise MigrationError("Insufficient disk space for safe uploads migration")
                copy_tree_no_follow(legacy, stage)
            else:
                stage.mkdir(mode=0o700)
            if fingerprint_tree(stage) != fingerprint:
                raise MigrationError("Staged uploads fingerprint does not match the source")
            state["phase"] = "staged"
            write_json_atomic(journal, state)
            if target_empty_present:
                state["targetBackupPending"] = True
                write_json_atomic(journal, state)
                os.replace(canonical, target_backup)
                fsync_directory(canonical.parent)
                state["targetBackedUp"] = True
                write_json_atomic(journal, state)
            state["targetActivationPending"] = True
            write_json_atomic(journal, state)
            os.replace(stage, canonical)
            fsync_directory(canonical.parent)
            if fault_after == "target_activated":
                raise InjectedCrash("Injected crash after canonical uploads activation")
            state["targetActivated"] = True
            state["phase"] = "target_activated"
            write_json_atomic(journal, state)

        if source_present:
            if mode == "migrate" and fingerprint_tree(legacy) != fingerprint:
                raise MigrationError("Legacy uploads changed during migration")
            state["sourceBackupPending"] = True
            write_json_atomic(journal, state)
            os.replace(legacy, source_backup)
            fsync_directory(librechat)
            state["sourceBackedUp"] = True
            write_json_atomic(journal, state)
        try:
            os.symlink(str(canonical), legacy, target_is_directory=True)
        except FileExistsError as error:
            if mode != "create" or source_present or target_empty_present:
                raise MigrationError(
                    "Concurrent uploads compatibility activation conflicted with existing state"
                ) from error
            winning_target = wait_for_recognized_other_runtime_link(
                legacy=legacy,
                canonical=canonical,
            )
            if winning_target != canonical:
                verified = fingerprint_tree(canonical)
                if verified != fingerprint:
                    raise MigrationError(
                        "Canonical uploads changed during concurrent activation"
                    )
                journal.unlink()
                fsync_directory(journal.parent)
                write_json_atomic(
                    receipt,
                    {
                        "schemaVersion": SCHEMA_VERSION,
                        "completedAt": iso_now(),
                        "mode": "isolated_runtime_root",
                        "fingerprint": fingerprint,
                        "legacyCompatibility": "other_runtime_exact_symlink_preserved",
                        "observedLinkTargetSha256": hash_path_identity(winning_target),
                        "canonicalStorage": "app_support_data_uploads",
                    },
                )
                return {
                    "schemaVersion": SCHEMA_VERSION,
                    "status": "other_runtime_compatibility_preserved",
                    "mode": "isolated_runtime_root",
                    "fingerprint": fingerprint,
                }
        fsync_directory(librechat)
        state["linkActivated"] = True
        state["phase"] = "link_activated"
        write_json_atomic(journal, state)
        if fault_after == "link_activated":
            raise InjectedCrash("Injected crash after legacy compatibility link activation")

        verified = fingerprint_tree(canonical)
        if verified != fingerprint:
            raise MigrationError("Canonical uploads changed before migration commit")
        write_json_atomic(
            receipt,
            {
                "schemaVersion": SCHEMA_VERSION,
                "transactionId": txid,
                "completedAt": iso_now(),
                "mode": mode,
                "fingerprint": fingerprint,
                "legacyCompatibility": "exact_symlink",
                "canonicalStorage": "app_support_data_uploads",
            },
        )
        state["phase"] = "committed"
        write_json_atomic(journal, state)
        if fault_after == "committed":
            raise InjectedCrash("Injected crash after uploads migration commit point")
        if lstat_optional(source_backup) is not None:
            remove_owned_tree(source_backup, fingerprint if mode == "migrate" else None)
        if lstat_optional(target_backup) is not None:
            remove_owned_tree(target_backup)
        journal.unlink()
        fsync_directory(journal.parent)
        return {
            "schemaVersion": SCHEMA_VERSION,
            "status": "migrated" if mode == "migrate" else "initialized",
            "mode": mode,
            "fingerprint": fingerprint,
        }
    except InjectedCrash:
        raise
    except Exception:
        recover_transaction(
            journal=journal,
            receipt=receipt,
            legacy=legacy,
            canonical=canonical,
            librechat=librechat,
        )
        raise


def _migrate_uploads_unlocked(
    *,
    app_support_dir: Path,
    librechat_dir: Path,
    canonical_root: Path | None = None,
    fault_after: str | None = None,
) -> dict[str, Any]:
    app_support = lexical(app_support_dir)
    librechat = lexical(librechat_dir)
    canonical = lexical(canonical_root or app_support / "data" / "uploads")
    required_canonical = app_support / "data" / "uploads"
    if canonical != required_canonical:
        raise MigrationError("Canonical uploads root must be App Support data/uploads")
    validate_owned_directory(app_support, "Viventium App Support")
    validate_owned_directory(librechat, "LibreChat checkout")
    assert_contained(canonical, app_support, "Canonical uploads root")
    legacy = librechat / "uploads"
    deferred = defer_populated_legacy_tree_during_active_outer_upgrade(
        app_support=app_support,
        librechat=librechat,
        legacy=legacy,
        canonical=canonical,
    )
    if deferred is not None:
        return deferred
    state_dir = app_support / "state" / "continuity" / "uploads-migration"
    ensure_private_directory(canonical.parent, bounded_by=app_support)
    ensure_private_directory(state_dir, bounded_by=app_support)
    journal = state_dir / "transaction.json"
    receipt = state_dir / "receipt.json"

    if lstat_optional(journal) is not None:
        recover_transaction(
            journal=journal,
            receipt=receipt,
            legacy=legacy,
            canonical=canonical,
            librechat=librechat,
        )

    legacy_metadata = lstat_optional(legacy)
    if legacy_metadata is not None and stat.S_ISLNK(legacy_metadata.st_mode):
        if not exact_link_to(legacy, canonical):
            if not is_recognized_other_runtime_link(legacy=legacy, canonical=canonical):
                if not is_plausible_other_runtime_link(
                    legacy=legacy,
                    canonical=canonical,
                ):
                    raise MigrationError("Legacy uploads root is an unexpected symlink")
                wait_for_recognized_other_runtime_link(
                    legacy=legacy,
                    canonical=canonical,
                )
            ensure_private_directory(canonical, bounded_by=app_support)
            target = resolved_link_target(legacy)
            fingerprint = fingerprint_tree(canonical)
            receipt_metadata = lstat_optional(receipt)
            if receipt_metadata is not None:
                if not preserved_link_receipt_matches(read_private_json(receipt), target):
                    raise MigrationError(
                        "Legacy uploads compatibility receipt conflicts with the shared checkout"
                    )
            else:
                write_json_atomic(
                    receipt,
                    {
                        "schemaVersion": SCHEMA_VERSION,
                        "completedAt": iso_now(),
                        "mode": "isolated_runtime_root",
                        "fingerprint": fingerprint,
                        "legacyCompatibility": "other_runtime_exact_symlink_preserved",
                        "observedLinkTargetSha256": hash_path_identity(target),
                        "canonicalStorage": "app_support_data_uploads",
                    },
                )
            return {
                "schemaVersion": SCHEMA_VERSION,
                "status": "other_runtime_compatibility_preserved",
                "mode": "isolated_runtime_root",
                "fingerprint": fingerprint,
            }
        receipt_payload = read_private_json(receipt)
        if (
            receipt_payload.get("schemaVersion") != SCHEMA_VERSION
            or receipt_payload.get("legacyCompatibility") != "exact_symlink"
        ):
            raise MigrationError("Legacy uploads symlink lacks a valid migration receipt")
        fingerprint = fingerprint_tree(canonical)
        return {
            "schemaVersion": SCHEMA_VERSION,
            "status": "already_migrated",
            "mode": receipt_payload.get("mode"),
            "fingerprint": fingerprint,
        }
    receipt_metadata = lstat_optional(receipt)
    if receipt_metadata is not None:
        receipt_payload = read_private_json(receipt)
        if receipt_payload.get("legacyCompatibility") == (
            "other_runtime_exact_symlink_preserved"
        ):
            if not is_preserved_link_receipt(receipt_payload):
                raise MigrationError("Shared-checkout uploads compatibility receipt is invalid")
            receipt.unlink()
            fsync_directory(receipt.parent)
    if legacy_metadata is not None:
        validate_owned_directory(legacy, "Legacy uploads root")
        legacy_fingerprint = fingerprint_tree(legacy)
        legacy_populated = tree_has_entries(legacy)
    else:
        legacy_fingerprint = {
            "fileCount": 0,
            "totalBytes": 0,
            "treeSha256": hashlib.sha256().hexdigest(),
        }
        legacy_populated = False

    canonical_metadata = lstat_optional(canonical)
    if canonical_metadata is not None:
        validate_owned_directory(canonical, "Canonical uploads root")
        canonical_fingerprint = fingerprint_tree(canonical)
        canonical_populated = tree_has_entries(canonical)
    else:
        canonical_fingerprint = None
        canonical_populated = False

    if legacy_populated and canonical_populated:
        raise MigrationError(
            "Legacy and canonical uploads roots both contain files; refusing to merge or overwrite"
        )
    if legacy_populated:
        return _commit_transaction(
            app_support=app_support,
            librechat=librechat,
            legacy=legacy,
            canonical=canonical,
            journal=journal,
            receipt=receipt,
            mode="migrate",
            fingerprint=legacy_fingerprint,
            source_present=legacy_metadata is not None,
            target_empty_present=canonical_metadata is not None,
            fault_after=fault_after,
        )
    if canonical_populated:
        return _commit_transaction(
            app_support=app_support,
            librechat=librechat,
            legacy=legacy,
            canonical=canonical,
            journal=journal,
            receipt=receipt,
            mode="adopt",
            fingerprint=canonical_fingerprint,
            source_present=legacy_metadata is not None,
            target_empty_present=False,
            fault_after=fault_after,
        )
    empty_fingerprint = legacy_fingerprint if legacy_metadata is not None else {
        "fileCount": 0,
        "totalBytes": 0,
        "treeSha256": hashlib.sha256().hexdigest(),
    }
    return _commit_transaction(
        app_support=app_support,
        librechat=librechat,
        legacy=legacy,
        canonical=canonical,
        journal=journal,
        receipt=receipt,
        mode="create",
        fingerprint=empty_fingerprint,
        source_present=legacy_metadata is not None,
        target_empty_present=canonical_metadata is not None,
        fault_after=fault_after,
    )


def migrate_uploads(
    *,
    app_support_dir: Path,
    librechat_dir: Path,
    canonical_root: Path | None = None,
    fault_after: str | None = None,
) -> dict[str, Any]:
    app_support = lexical(app_support_dir)
    librechat = lexical(librechat_dir)
    canonical = lexical(canonical_root or app_support / "data" / "uploads")
    if canonical != app_support / "data" / "uploads":
        raise MigrationError("Canonical uploads root must be App Support data/uploads")
    validate_owned_directory(app_support, "Viventium App Support")
    validate_owned_directory(librechat, "LibreChat checkout")
    deferred = defer_populated_legacy_tree_during_active_outer_upgrade(
        app_support=app_support,
        librechat=librechat,
        legacy=librechat / "uploads",
        canonical=canonical,
    )
    if deferred is not None:
        return deferred
    state_dir = app_support / "state" / "continuity" / "uploads-migration"
    ensure_private_directory(state_dir, bounded_by=app_support)
    with uploads_migration_lock(state_dir):
        return _migrate_uploads_unlocked(
            app_support_dir=app_support,
            librechat_dir=librechat,
            canonical_root=canonical,
            fault_after=fault_after,
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Migrate source-install uploads into canonical App Support storage."
    )
    parser.add_argument("--app-support-dir", required=True)
    parser.add_argument("--librechat-dir", required=True)
    parser.add_argument("--canonical-root")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = migrate_uploads(
            app_support_dir=Path(args.app_support_dir),
            librechat_dir=Path(args.librechat_dir),
            canonical_root=Path(args.canonical_root) if args.canonical_root else None,
        )
    except MigrationError as error:
        print(f"Viventium uploads migration failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

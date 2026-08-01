#!/usr/bin/env python3
"""One-time, crash-safe Telegram preference authority handoff.

Legacy repository-local preferences are imported only when the caller proves that
the stopped predecessor used that exact root.  Once committed, canonical App
Support state remains authoritative forever; stale or relocated checkouts can
never overwrite later user edits.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import secrets
import shlex
import shutil
import stat
import subprocess
from typing import Any, Iterator


SCHEMA_VERSION = 2
AUTHORITY_KIND = "viventium-telegram-preference-authority"
EXPLICIT_AUTHORITY_KIND = "viventium-telegram-explicit-preference-authority"
JOURNAL_KIND = "viventium-telegram-preference-migration"


class MigrationError(RuntimeError):
    pass


def _lexical(path: Path) -> Path:
    return Path(os.path.abspath(os.path.expanduser(str(path))))


def ensure_private_preference_root(
    path: Path,
    *,
    create: bool = True,
    missing_ok: bool = False,
) -> Path | None:
    """Create or harden one owner-private directory without following links.

    Every path component is opened relative to an already-open parent.  The
    final permission change is descriptor-bound, and the complete chain is
    revalidated before success so a concurrent rename cannot redirect chmod.
    Existing ancestors are inspected but never modified.
    """
    target = _lexical(path)
    directory_flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0)
    )
    descriptors: list[int] = []
    names: list[str] = []
    try:
        descriptor = os.open(target.anchor, directory_flags)
        descriptors.append(descriptor)
        for part in target.parts[1:]:
            parent_descriptor = descriptors[-1]
            try:
                before = os.stat(
                    part,
                    dir_fd=parent_descriptor,
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                if not create:
                    if missing_ok:
                        return None
                    raise MigrationError(
                        "Telegram preference root does not exist"
                    )
                os.mkdir(part, mode=0o700, dir_fd=parent_descriptor)
                os.fsync(parent_descriptor)
                before = os.stat(
                    part,
                    dir_fd=parent_descriptor,
                    follow_symlinks=False,
                )
            if stat.S_ISLNK(before.st_mode):
                raise MigrationError(
                    "Telegram preference root contains a symlink"
                )
            if not stat.S_ISDIR(before.st_mode):
                raise MigrationError(
                    "Telegram preference root has a non-directory component"
                )
            child_descriptor = os.open(
                part,
                directory_flags,
                dir_fd=parent_descriptor,
            )
            after = os.fstat(child_descriptor)
            if (
                not stat.S_ISDIR(after.st_mode)
                or (before.st_dev, before.st_ino)
                != (after.st_dev, after.st_ino)
            ):
                os.close(child_descriptor)
                raise MigrationError(
                    "Telegram preference root changed during validation"
                )
            descriptors.append(child_descriptor)
            names.append(part)

        final_metadata = os.fstat(descriptors[-1])
        if (
            len(descriptors) == 1
            or not stat.S_ISDIR(final_metadata.st_mode)
            or final_metadata.st_uid != os.getuid()
        ):
            raise MigrationError(
                "Telegram preference root is not an owner-controlled directory"
            )
        if stat.S_IMODE(final_metadata.st_mode) != 0o700:
            os.fchmod(descriptors[-1], 0o700)
        os.fsync(descriptors[-1])

        # A descriptor protects the chmod target. Rechecking each directory
        # entry also prevents reporting success after an ancestor or the final
        # name was concurrently exchanged.
        for index, name in enumerate(names):
            current = os.stat(
                name,
                dir_fd=descriptors[index],
                follow_symlinks=False,
            )
            opened = os.fstat(descriptors[index + 1])
            if (
                not stat.S_ISDIR(current.st_mode)
                or (current.st_dev, current.st_ino)
                != (opened.st_dev, opened.st_ino)
            ):
                raise MigrationError(
                    "Telegram preference root changed during validation"
                )
        return target
    except MigrationError:
        raise
    except OSError as error:
        raise MigrationError(
            "Telegram preference root is unsafe or changed during validation"
        ) from error
    finally:
        for descriptor in reversed(descriptors):
            try:
                os.close(descriptor)
            except OSError:
                pass


def _is_legacy_preference_root(path: Path) -> bool:
    """Recognize historical Viventium-owned roots without relying on checkout location."""
    parts = _lexical(path).parts
    suffixes = (
        (
            "viventium_v0_4",
            "telegram-viventium",
            "TelegramVivBot",
            "user_configs",
        ),
        ("viventium_v0_4", "telegram-viventium", "user_configs"),
        ("runtime-state", "telegram-user-configs"),
    )
    return any(
        len(parts) >= len(suffix)
        and tuple(parts[-len(suffix) :]) == suffix
        for suffix in suffixes
    )


def _contained(path: Path, root: Path, label: str) -> Path:
    candidate = _lexical(path)
    boundary = _lexical(root)
    try:
        candidate.relative_to(boundary)
    except ValueError as error:
        raise MigrationError(f"{label} is outside its trusted boundary") from error
    return candidate


def _validate_chain(path: Path, label: str) -> None:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current = current / part
        if not os.path.lexists(current):
            break
        metadata = os.lstat(current)
        if stat.S_ISLNK(metadata.st_mode):
            raise MigrationError(f"{label} contains a symlink")
        if current != path and not stat.S_ISDIR(metadata.st_mode):
            raise MigrationError(f"{label} has a non-directory ancestor")


def _ensure_private_dir(path: Path, app_support: Path) -> None:
    target = _contained(path, app_support, "Telegram migration directory")
    boundary = _lexical(app_support)
    _validate_chain(boundary, "Telegram App Support")
    boundary_existed = boundary.exists()
    boundary.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not boundary_existed:
        _fsync_dir(boundary.parent)
    try:
        relative = target.relative_to(boundary)
    except ValueError as error:  # pragma: no cover - guarded by _contained
        raise MigrationError("Telegram migration directory escaped App Support") from error
    current = boundary
    for part in relative.parts:
        current = current / part
        if os.path.lexists(current):
            metadata = os.lstat(current)
            if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
                raise MigrationError("Telegram migration directory is unsafe")
            if metadata.st_uid != os.getuid():
                raise MigrationError("Telegram migration directory is not owner-controlled")
        else:
            current.mkdir(mode=0o700)
            _fsync_dir(current.parent)
        current.chmod(0o700)


def _fsync_dir(path: Path) -> None:
    descriptor = os.open(
        path,
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _read_regular(path: Path, label: str) -> bytes:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or metadata.st_nlink != 1
        ):
            raise MigrationError(f"{label} is not an owner-controlled regular file")
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            return handle.read()
    finally:
        os.close(descriptor)


def _write_atomic(path: Path, value: bytes, app_support: Path) -> None:
    target = _contained(path, app_support, "Telegram migration output")
    _ensure_private_dir(target.parent, app_support)
    if os.path.lexists(target):
        metadata = os.lstat(target)
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise MigrationError("Telegram migration output is unsafe")
        if metadata.st_uid != os.getuid():
            raise MigrationError("Telegram migration output is not owner-controlled")
    temporary = target.parent / f".{target.name}.{secrets.token_hex(8)}.tmp"
    descriptor = os.open(
        temporary,
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        target.chmod(0o600)
        _fsync_dir(target.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _write_json(path: Path, value: dict[str, Any], app_support: Path) -> None:
    _write_atomic(
        path,
        (
            json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8"),
        app_support,
    )


def _unlink_durable(path: Path) -> None:
    path.unlink(missing_ok=True)
    _fsync_dir(path.parent)


def _legacy_files(source: Path) -> Iterator[tuple[Path, Path]]:
    if not source.exists() and not source.is_symlink():
        return
    _validate_chain(source, "Legacy Telegram preference root")
    metadata = source.lstat()
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise MigrationError("Legacy Telegram preference root is unsafe")
    if metadata.st_uid != os.getuid():
        raise MigrationError("Legacy Telegram preference root is not owner-controlled")
    for directory, directory_names, file_names in os.walk(
        source, topdown=True, followlinks=False
    ):
        directory_path = Path(directory)
        kept: list[str] = []
        for name in sorted(directory_names):
            candidate = directory_path / name
            candidate_metadata = candidate.lstat()
            if stat.S_ISLNK(candidate_metadata.st_mode):
                raise MigrationError("Legacy Telegram preference tree contains a symlink")
            if not stat.S_ISDIR(candidate_metadata.st_mode):
                raise MigrationError("Legacy Telegram preference tree is unsafe")
            kept.append(name)
        directory_names[:] = kept
        for name in sorted(file_names):
            candidate = directory_path / name
            if candidate.is_symlink():
                raise MigrationError("Legacy Telegram preference tree contains a symlink")
            yield candidate, candidate.relative_to(source)


def _harden_canonical_tree(
    canonical: Path,
    support: Path,
    *,
    allow_changes: bool,
) -> None:
    """Upgrade owner-controlled legacy modes without changing preference bytes."""
    root = _contained(
        canonical,
        support,
        "Canonical Telegram preference root",
    )
    if not root.exists() and not root.is_symlink():
        return
    _validate_chain(root, "Canonical Telegram preference root")
    directory_flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    file_flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    directories: list[int] = []
    files: list[int] = []
    needs_hardening = False

    def validate_directory(descriptor: int) -> os.stat_result:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISDIR(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or stat.S_IMODE(metadata.st_mode) & 0o022
        ):
            raise MigrationError(
                "Canonical Telegram preference tree is unsafe"
            )
        return metadata

    def validate_file(descriptor: int) -> os.stat_result:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or metadata.st_nlink != 1
            or stat.S_IMODE(metadata.st_mode) & 0o022
        ):
            raise MigrationError(
                "Canonical Telegram preference tree is unsafe"
            )
        return metadata

    def collect(directory_descriptor: int) -> None:
        nonlocal needs_hardening
        directory_metadata = validate_directory(directory_descriptor)
        needs_hardening = (
            needs_hardening
            or stat.S_IMODE(directory_metadata.st_mode) != 0o700
        )
        for name in sorted(os.listdir(directory_descriptor)):
            try:
                before = os.stat(
                    name,
                    dir_fd=directory_descriptor,
                    follow_symlinks=False,
                )
            except OSError as error:
                raise MigrationError(
                    "Canonical Telegram preference tree changed during validation"
                ) from error
            if stat.S_ISDIR(before.st_mode):
                try:
                    child_descriptor = os.open(
                        name,
                        directory_flags,
                        dir_fd=directory_descriptor,
                    )
                except OSError as error:
                    raise MigrationError(
                        "Canonical Telegram preference tree is unsafe"
                    ) from error
                directories.append(child_descriptor)
                after = validate_directory(child_descriptor)
                if (before.st_dev, before.st_ino) != (
                    after.st_dev,
                    after.st_ino,
                ):
                    raise MigrationError(
                        "Canonical Telegram preference tree changed during validation"
                    )
                collect(child_descriptor)
                continue
            if stat.S_ISREG(before.st_mode):
                try:
                    child_descriptor = os.open(
                        name,
                        file_flags,
                        dir_fd=directory_descriptor,
                    )
                except OSError as error:
                    raise MigrationError(
                        "Canonical Telegram preference tree is unsafe"
                    ) from error
                files.append(child_descriptor)
                after = validate_file(child_descriptor)
                if (before.st_dev, before.st_ino) != (
                    after.st_dev,
                    after.st_ino,
                ):
                    raise MigrationError(
                        "Canonical Telegram preference tree changed during validation"
                    )
                needs_hardening = (
                    needs_hardening
                    or stat.S_IMODE(after.st_mode) != 0o600
                )
                continue
            raise MigrationError(
                "Canonical Telegram preference tree is unsafe"
            )

    try:
        root_descriptor = os.open(root, directory_flags)
        directories.append(root_descriptor)
        collect(root_descriptor)
        if needs_hardening and not allow_changes:
            raise MigrationError(
                "Telegram preference writer must be stopped before "
                "canonical permission hardening"
            )
        for descriptor in files:
            if stat.S_IMODE(os.fstat(descriptor).st_mode) != 0o600:
                os.fchmod(descriptor, 0o600)
            os.fsync(descriptor)
        for descriptor in reversed(directories):
            if stat.S_IMODE(os.fstat(descriptor).st_mode) != 0o700:
                os.fchmod(descriptor, 0o700)
            os.fsync(descriptor)
    except OSError as error:
        raise MigrationError(
            "Canonical Telegram preference hardening failed safely"
        ) from error
    finally:
        for descriptor in reversed(files):
            try:
                os.close(descriptor)
            except OSError:
                pass
        for descriptor in reversed(directories):
            try:
                os.close(descriptor)
            except OSError:
                pass


def _merged_value(canonical: bytes | None, legacy: bytes) -> bytes:
    if canonical is None or canonical == legacy:
        return legacy
    try:
        canonical_value = json.loads(canonical)
        legacy_value = json.loads(legacy)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MigrationError(
            "Conflicting non-JSON Telegram preferences require explicit recovery"
        ) from error
    if not isinstance(canonical_value, dict) or not isinstance(legacy_value, dict):
        raise MigrationError(
            "Conflicting non-object Telegram preferences require explicit recovery"
        )
    merged = {**canonical_value, **legacy_value}
    return (
        json.dumps(merged, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _read_optional(path: Path, label: str) -> bytes | None:
    if not path.exists() and not path.is_symlink():
        return None
    if path.is_symlink():
        raise MigrationError(f"{label} is a symlink")
    return _read_regular(path, label)


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(_read_regular(path, label))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MigrationError(f"{label} is unreadable") from error
    if not isinstance(value, dict):
        raise MigrationError(f"{label} is invalid")
    return value


def _validate_authority(payload: dict[str, Any]) -> None:
    if (
        payload.get("schema_version") != SCHEMA_VERSION
        or payload.get("kind") != AUTHORITY_KIND
        or payload.get("status") != "committed"
        or payload.get("authority") != "canonical-app-support"
        or not isinstance(payload.get("generation"), str)
        or not isinstance(payload.get("retired_legacy_roots"), list)
    ):
        raise MigrationError("Telegram preference authority ledger is invalid")


def _validate_journal(payload: dict[str, Any], support: Path) -> None:
    if (
        payload.get("schema_version") != SCHEMA_VERSION
        or payload.get("kind") != JOURNAL_KIND
        or payload.get("status") not in {"prepared", "applying"}
        or not isinstance(payload.get("run_id"), str)
        or not isinstance(payload.get("source_root"), str)
        or not isinstance(payload.get("operations"), list)
        or not isinstance(payload.get("next_index"), int)
        or isinstance(payload.get("next_index"), bool)
        or payload["next_index"] < 0
        or payload["next_index"] > len(payload["operations"])
    ):
        raise MigrationError("Telegram preference migration journal is invalid")
    for operation in payload["operations"]:
        run_id = payload["run_id"]
        if (
            not isinstance(operation, dict)
            or not isinstance(operation.get("path"), str)
            or not isinstance(operation.get("legacy_sha256"), str)
            or not isinstance(operation.get("canonical_before_exists"), bool)
            or (
                operation.get("canonical_before_sha256") is not None
                and not isinstance(
                    operation.get("canonical_before_sha256"), str
                )
            )
            or not isinstance(operation.get("canonical_after_sha256"), str)
            or not isinstance(operation.get("staged"), str)
            or not isinstance(operation.get("backup"), str)
        ):
            raise MigrationError("Telegram preference migration journal is invalid")
        for field in (
            "legacy_sha256",
            "canonical_after_sha256",
        ):
            value = operation[field]
            if (
                len(value) != 64
                or any(character not in "0123456789abcdef" for character in value)
            ):
                raise MigrationError(
                    "Telegram preference migration journal is invalid"
                )
        before_hash = operation.get("canonical_before_sha256")
        if operation["canonical_before_exists"] != (before_hash is not None):
            raise MigrationError("Telegram preference migration journal is invalid")
        if before_hash is not None and (
            len(before_hash) != 64
            or any(
                character not in "0123456789abcdef"
                for character in before_hash
            )
        ):
            raise MigrationError("Telegram preference migration journal is invalid")
        relative = Path(operation["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise MigrationError("Telegram preference migration journal is invalid")
        staged = _contained(
            support / operation["staged"],
            support,
            "Telegram migration staged value",
        )
        expected_stage = (
            support
            / "state"
            / "telegram-user-config-migration"
            / "prepared"
            / run_id
            / relative
        )
        if staged != expected_stage:
            raise MigrationError("Telegram preference migration journal is invalid")


@contextmanager
def _lock(state_root: Path, app_support: Path):
    _ensure_private_dir(state_root, app_support)
    lock_path = state_root / "migration.lock"
    descriptor = os.open(
        lock_path,
        os.O_RDWR
        | os.O_CREAT
        | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or stat.S_IMODE(metadata.st_mode) & 0o077
        ):
            raise MigrationError("Telegram preference migration lock is unsafe")
        os.fchmod(descriptor, 0o600)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        os.close(descriptor)


def _operation_current(target: Path) -> tuple[bool, bytes | None]:
    current = _read_optional(target, "Canonical Telegram preference")
    return current is not None, current


def _apply_pending(
    *,
    pending_path: Path,
    payload: dict[str, Any],
    canonical: Path,
    state_root: Path,
    authority_path: Path,
    support: Path,
) -> dict[str, Any]:
    _validate_journal(payload, support)
    operations = payload["operations"]
    interrupt_after_raw = str(
        os.environ.get("VIVENTIUM_QA_TELEGRAM_MIGRATION_INTERRUPT_AFTER") or ""
    ).strip()
    interrupt_after = int(interrupt_after_raw) if interrupt_after_raw else -1
    writes_this_run = 0
    # Revalidate every earlier operation on resume instead of trusting only
    # the journal cursor. An outer transaction may have restored canonical
    # bytes while intentionally retaining this durable journal; replaying
    # from zero is idempotent when the after-value is present, repairs only
    # an exact before-value, and fails closed on any third value.
    for index in range(0, len(operations)):
        operation = operations[index]
        relative = Path(operation["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise MigrationError("Telegram preference migration path is unsafe")
        target = _contained(
            canonical / relative,
            canonical,
            "Canonical Telegram preference",
        )
        staged = _contained(
            support / operation["staged"],
            support,
            "Telegram migration staged value",
        )
        staged_value = _read_regular(staged, "Telegram migration staged value")
        if _sha256_bytes(staged_value) != operation["canonical_after_sha256"]:
            raise MigrationError("Telegram migration staged value changed")
        exists, current = _operation_current(target)
        current_hash = _sha256_bytes(current) if current is not None else None
        expected_exists = bool(operation["canonical_before_exists"])
        expected_hash = operation.get("canonical_before_sha256")
        after_hash = operation["canonical_after_sha256"]
        if exists and current_hash == after_hash:
            pass
        elif exists == expected_exists and current_hash == expected_hash:
            _write_atomic(target, staged_value, support)
            writes_this_run += 1
            if interrupt_after >= 0 and writes_this_run == interrupt_after:
                raise MigrationError("Synthetic Telegram migration interruption")
        else:
            raise MigrationError(
                "Canonical Telegram preference changed during migration; "
                "recovery failed closed"
            )
        payload["status"] = "applying"
        payload["next_index"] = index + 1
        _write_json(pending_path, payload, support)

    _assert_no_active_telegram_writer(
        support=support,
        source=_lexical(Path(payload["source_root"])),
        canonical=canonical,
    )
    _assert_legacy_tree_unchanged(payload)
    generation = payload["run_id"]
    authority = {
        "schema_version": SCHEMA_VERSION,
        "kind": AUTHORITY_KIND,
        "status": "committed",
        "authority": "canonical-app-support",
        "generation": generation,
        "canonical_root": str(canonical),
        "retired_legacy_roots": [payload["source_root"]],
        "source_tree_sha256": payload["source_tree_sha256"],
        "operations": [
            {
                key: operation.get(key)
                for key in (
                    "path",
                    "legacy_sha256",
                    "canonical_before_sha256",
                    "canonical_after_sha256",
                    "backup",
                )
            }
            for operation in operations
        ],
    }
    _write_json(authority_path, authority, support)
    if str(
        os.environ.get(
            "VIVENTIUM_QA_TELEGRAM_MIGRATION_INTERRUPT_AFTER_AUTHORITY"
        )
        or ""
    ).strip() == "1":
        raise MigrationError(
            "Synthetic Telegram migration interruption after authority commit"
        )
    _unlink_durable(pending_path)
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "migrated",
        "changed": bool(operations),
        "files_changed": len(operations),
        "generation": generation,
    }


def _tree_digest(rows: list[tuple[Path, Path]]) -> str:
    digest = hashlib.sha256()
    for source_file, relative in rows:
        value = _read_regular(source_file, "Legacy Telegram preference")
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(_sha256_bytes(value).encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def _assert_no_active_telegram_writer(
    *,
    support: Path,
    source: Path,
    canonical: Path,
) -> None:
    completed = subprocess.run(
        ["ps", "-axo", "pid=,uid=,command="],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise MigrationError(
            "Telegram preference writer identity could not be verified"
        )
    own_pid = os.getpid()
    for row in completed.stdout.splitlines():
        fields = row.strip().split(None, 2)
        if len(fields) != 3:
            continue
        try:
            pid = int(fields[0])
            uid = int(fields[1])
        except ValueError:
            continue
        if pid == own_pid or uid != os.getuid():
            continue
        command = fields[2]
        try:
            arguments = shlex.split(command)
        except ValueError:
            arguments = command.split()
        module_launch = any(
            arguments[index : index + 2] == ["-m", "TelegramVivBot.bot"]
            for index in range(max(0, len(arguments) - 1))
        )
        bot_arguments = [
            Path(argument)
            for argument in arguments[1:]
            if Path(argument).name == "bot.py"
        ]
        if not module_launch and not bot_arguments:
            continue
        cwd: Path | None = None
        proc_cwd = Path("/proc") / str(pid) / "cwd"
        if proc_cwd.exists() or proc_cwd.is_symlink():
            try:
                cwd = Path(os.readlink(proc_cwd))
            except OSError:
                cwd = None
        elif shutil.which("lsof"):
            inspected = subprocess.run(
                ["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"],
                check=False,
                capture_output=True,
                text=True,
            )
            for line in inspected.stdout.splitlines():
                if line.startswith("n") and len(line) > 1:
                    cwd = Path(line[1:])
                    break
        scope_roots = (support, source.parent, canonical)

        def in_scope(candidate: Path) -> bool:
            lexical = _lexical(candidate)
            return any(
                lexical == root or lexical.is_relative_to(root)
                for root in scope_roots
            )

        process_paths: list[Path] = []
        if cwd is not None:
            process_paths.append(cwd)
        for candidate in bot_arguments:
            if candidate.is_absolute():
                process_paths.append(candidate)
            elif cwd is not None:
                process_paths.append(cwd / candidate)
        command_mentions_scope = any(
            str(root) in command for root in scope_roots
        )
        if command_mentions_scope or any(in_scope(path) for path in process_paths):
            raise MigrationError(
                "Telegram preference writer is still active after shutdown"
            )
        has_unresolved_relative_bot = any(
            not candidate.is_absolute() for candidate in bot_arguments
        )
        if cwd is None and (module_launch or has_unresolved_relative_bot):
            raise MigrationError(
                "Telegram bot.py writer identity could not be disproven"
            )


def _assert_legacy_tree_unchanged(payload: dict[str, Any]) -> None:
    source = _lexical(Path(str(payload.get("source_root") or "")))
    rows = list(_legacy_files(source))
    if _tree_digest(rows) != payload.get("source_tree_sha256"):
        raise MigrationError(
            "Legacy Telegram preferences changed during migration; "
            "recovery failed closed"
        )


def _write_preference_root_selection(
    path: Path,
    preference_root: Path,
    support: Path,
) -> str:
    root = _lexical(preference_root)
    generation = hashlib.sha256(
        ("explicit-authority\0" + str(root)).encode("utf-8")
    ).hexdigest()
    _write_json(
        path,
        {
            "schema_version": SCHEMA_VERSION,
            "kind": EXPLICIT_AUTHORITY_KIND,
            "status": "committed",
            "generation": generation,
            "preference_root": str(root),
        },
        support,
    )
    return generation


def migrate(
    repo_root: Path,
    app_support: Path,
    *,
    active_config_root: Path | None,
    writer_stopped: bool,
) -> dict[str, Any]:
    repo = _lexical(repo_root)
    support = _lexical(app_support)
    _validate_chain(repo, "Telegram migration repository")
    _validate_chain(support, "Telegram App Support")
    if repo.is_symlink() or not repo.is_dir():
        raise MigrationError("Telegram migration repository is unsafe")
    default_legacy_source = (
        repo
        / "viventium_v0_4"
        / "telegram-viventium"
        / "TelegramVivBot"
        / "user_configs"
    )
    canonical = support / "state" / "telegram-user-configs"
    active = _lexical(active_config_root) if active_config_root is not None else None
    if active is not None and active != canonical:
        _validate_chain(active, "Active Telegram preference root")
        if not active.exists():
            raise MigrationError(
                "Durably observed active Telegram preference root is unavailable"
            )
        active_metadata = active.lstat()
        if (
            stat.S_ISLNK(active_metadata.st_mode)
            or not stat.S_ISDIR(active_metadata.st_mode)
            or active_metadata.st_uid != os.getuid()
        ):
            raise MigrationError(
                "Durably observed active Telegram preference root is unsafe"
            )
    source = (
        active
        if active is not None and active != canonical
        else default_legacy_source
    )
    state_root = support / "state" / "telegram-user-config-migration"
    authority_path = state_root / "authority.json"
    explicit_authority_path = state_root / "explicit-authority.json"
    pending_path = state_root / "pending.json"

    explicit_override = str(
        os.environ.get("VIVENTIUM_TELEGRAM_USER_CONFIGS_DIR") or ""
    ).strip()
    explicit_path = (
        _lexical(Path(explicit_override)) if explicit_override else None
    )
    preserve_explicit = (
        explicit_path is not None
        and explicit_path != canonical
    ) or (
        active is not None
        and active != canonical
        and not _is_legacy_preference_root(active)
    )
    if preserve_explicit:
        preserved_root = (
            explicit_path
            if explicit_path is not None and explicit_path != canonical
            else active
        )
        assert preserved_root is not None
        _validate_chain(
            preserved_root,
            "Explicit Telegram preference root",
        )
        if not preserved_root.exists():
            raise MigrationError(
                "Explicit Telegram preference root is unavailable"
            )
        preserved_metadata = preserved_root.lstat()
        if (
            stat.S_ISLNK(preserved_metadata.st_mode)
            or not stat.S_ISDIR(preserved_metadata.st_mode)
            or preserved_metadata.st_uid != os.getuid()
        ):
            raise MigrationError(
                "Explicit Telegram preference root is unsafe"
            )
        with _lock(state_root, support):
            generation = _write_preference_root_selection(
                explicit_authority_path,
                preserved_root,
                support,
            )
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "explicit-override-preserved",
            "changed": False,
            "generation": generation,
        }

    source_rows = list(_legacy_files(source))
    has_state = state_root.exists() or state_root.is_symlink()
    if (
        source_rows
        and not has_state
        and active_config_root is None
    ):
        raise MigrationError(
            "Legacy Telegram preference authority is unknown; refusing migration"
        )
    if source_rows and not has_state and not writer_stopped:
        raise MigrationError(
            "Telegram preference writer must be stopped before authority handoff"
        )

    with _lock(state_root, support):
        if canonical.exists() or canonical.is_symlink():
            if writer_stopped:
                _assert_no_active_telegram_writer(
                    support=support,
                    source=source,
                    canonical=canonical,
                )
            _harden_canonical_tree(
                canonical,
                support,
                allow_changes=writer_stopped,
            )
        if authority_path.exists() or authority_path.is_symlink():
            authority = _load_json(
                authority_path, "Telegram preference authority ledger"
            )
            _validate_authority(authority)
            if pending_path.exists() or pending_path.is_symlink():
                pending = _load_json(
                    pending_path, "Telegram preference migration journal"
                )
                _validate_journal(pending, support)
                if pending.get("run_id") != authority.get("generation"):
                    raise MigrationError(
                        "Telegram preference authority and journal identities conflict"
                    )
                _unlink_durable(pending_path)
            _write_preference_root_selection(
                explicit_authority_path,
                canonical,
                support,
            )
            return {
                "schema_version": SCHEMA_VERSION,
                "status": "canonical-authoritative",
                "changed": False,
                "generation": authority["generation"],
            }

        if pending_path.exists() or pending_path.is_symlink():
            if not writer_stopped:
                raise MigrationError(
                    "Telegram preference writer must be stopped before journal recovery"
                )
            _assert_no_active_telegram_writer(
                support=support,
                source=source,
                canonical=canonical,
            )
            pending = _load_json(
                pending_path, "Telegram preference migration journal"
            )
            _assert_legacy_tree_unchanged(pending)
            result = _apply_pending(
                pending_path=pending_path,
                payload=pending,
                canonical=canonical,
                state_root=state_root,
                authority_path=authority_path,
                support=support,
            )
            _write_preference_root_selection(
                explicit_authority_path,
                canonical,
                support,
            )
            return result

        if not source_rows:
            run_id = hashlib.sha256(
                ("initialize-empty\0" + str(canonical)).encode("utf-8")
            ).hexdigest()
            _write_json(
                authority_path,
                {
                    "schema_version": SCHEMA_VERSION,
                    "kind": AUTHORITY_KIND,
                    "status": "committed",
                    "authority": "canonical-app-support",
                    "generation": run_id,
                    "canonical_root": str(canonical),
                    "retired_legacy_roots": [],
                    "source_tree_sha256": hashlib.sha256(b"").hexdigest(),
                    "operations": [],
                },
                support,
            )
            _write_preference_root_selection(
                explicit_authority_path,
                canonical,
                support,
            )
            return {
                "schema_version": SCHEMA_VERSION,
                "status": "canonical-authority-initialized",
                "changed": False,
                "generation": run_id,
            }
        if active_config_root is None:
            raise MigrationError(
                "Legacy Telegram preference authority is unknown; refusing migration"
            )
        active = _lexical(active_config_root)
        if active == canonical:
            if not writer_stopped:
                raise MigrationError(
                    "Telegram preference writer must be stopped before authority handoff"
                )
            _assert_no_active_telegram_writer(
                support=support,
                source=source,
                canonical=canonical,
            )
            source_tree_sha256 = _tree_digest(source_rows)
            run_id = hashlib.sha256(
                (
                    "canonical-authority\0"
                    + str(canonical)
                    + "\0"
                    + source_tree_sha256
                ).encode("utf-8")
            ).hexdigest()
            _write_json(
                authority_path,
                {
                    "schema_version": SCHEMA_VERSION,
                    "kind": AUTHORITY_KIND,
                    "status": "committed",
                    "authority": "canonical-app-support",
                    "generation": run_id,
                    "canonical_root": str(canonical),
                    "retired_legacy_roots": [str(source)],
                    "source_tree_sha256": source_tree_sha256,
                    "operations": [],
                },
                support,
            )
            _write_preference_root_selection(
                explicit_authority_path,
                canonical,
                support,
            )
            return {
                "schema_version": SCHEMA_VERSION,
                "status": "canonical-authoritative",
                "changed": False,
                "generation": run_id,
            }
        if active != source:
            return {
                "schema_version": SCHEMA_VERSION,
                "status": "explicit-override-preserved",
                "changed": False,
            }
        if not writer_stopped:
            raise MigrationError(
                "Telegram preference writer must be stopped before authority handoff"
            )
        _assert_no_active_telegram_writer(
            support=support,
            source=source,
            canonical=canonical,
        )

        # Re-read after the caller's quiescence proof and while holding the migration lock.
        source_rows = list(_legacy_files(source))
        source_tree_sha256 = _tree_digest(source_rows)
        prepared: list[tuple[dict[str, Any], bytes]] = []
        for source_file, relative in source_rows:
            legacy = _read_regular(source_file, "Legacy Telegram preference")
            target = _contained(
                canonical / relative,
                canonical,
                "Canonical Telegram preference",
            )
            _validate_chain(target, "Canonical Telegram preference")
            canonical_before = _read_optional(
                target, "Canonical Telegram preference"
            )
            merged = _merged_value(canonical_before, legacy)
            before_hash = (
                _sha256_bytes(canonical_before)
                if canonical_before is not None
                else None
            )
            after_hash = _sha256_bytes(merged)
            if canonical_before == merged:
                continue
            prepared.append(
                (
                    {
                        "path": relative.as_posix(),
                        "legacy_sha256": _sha256_bytes(legacy),
                        "canonical_before_exists": canonical_before is not None,
                        "canonical_before_sha256": before_hash,
                        "canonical_after_sha256": after_hash,
                    },
                    merged,
                )
            )

        identity_rows = [
            {
                key: operation[key]
                for key in (
                    "path",
                    "legacy_sha256",
                    "canonical_before_exists",
                    "canonical_before_sha256",
                    "canonical_after_sha256",
                )
            }
            for operation, _ in prepared
        ]
        run_id = hashlib.sha256(
            json.dumps(
                {
                    "source": str(source),
                    "source_tree_sha256": source_tree_sha256,
                    "operations": identity_rows,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        stage_root = state_root / "prepared" / run_id
        backup_root = state_root / "backups" / run_id / "canonical"
        operations: list[dict[str, Any]] = []
        for operation, merged in prepared:
            relative = Path(operation["path"])
            staged = stage_root / relative
            _write_atomic(staged, merged, support)
            target = canonical / relative
            canonical_before = _read_optional(
                target, "Canonical Telegram preference"
            )
            backup_relative = ""
            if canonical_before is not None:
                backup = backup_root / relative
                _write_atomic(backup, canonical_before, support)
                backup_relative = str(backup.relative_to(support))
            operation["staged"] = str(staged.relative_to(support))
            operation["backup"] = backup_relative
            operations.append(operation)

        journal = {
            "schema_version": SCHEMA_VERSION,
            "kind": JOURNAL_KIND,
            "status": "prepared",
            "run_id": run_id,
            "source_root": str(source),
            "active_config_root": str(active),
            "canonical_root": str(canonical),
            "source_tree_sha256": source_tree_sha256,
            "next_index": 0,
            "operations": operations,
        }
        _write_json(pending_path, journal, support)
        result = _apply_pending(
            pending_path=pending_path,
            payload=journal,
            canonical=canonical,
            state_root=state_root,
            authority_path=authority_path,
            support=support,
        )
        _write_preference_root_selection(
            explicit_authority_path,
            canonical,
            support,
        )
        return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ensure-private-root")
    parser.add_argument("--repo-root")
    parser.add_argument("--app-support-dir")
    parser.add_argument("--active-config-root")
    parser.add_argument("--writer-stopped", action="store_true")
    args = parser.parse_args()
    try:
        if args.ensure_private_root:
            if args.repo_root or args.app_support_dir or args.active_config_root:
                parser.error(
                    "--ensure-private-root cannot be combined with migration arguments"
                )
            ensured = ensure_private_preference_root(
                Path(args.ensure_private_root)
            )
            print(
                json.dumps(
                    {"status": "private-root-ready", "path": str(ensured)},
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
            return 0
        if not args.repo_root or not args.app_support_dir:
            parser.error(
                "--repo-root and --app-support-dir are required for migration"
            )
        result = migrate(
            Path(args.repo_root),
            Path(args.app_support_dir),
            active_config_root=(
                Path(args.active_config_root)
                if args.active_config_root
                else None
            ),
            writer_stopped=args.writer_stopped,
        )
    except (MigrationError, OSError, ValueError, json.JSONDecodeError) as error:
        print(str(error), file=os.sys.stderr)
        return 4
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

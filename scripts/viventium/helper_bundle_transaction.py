#!/usr/bin/env python3
"""Descriptor-relative filesystem transaction for the macOS helper bundle.

The shell installer performs UI, build, and login-item work. This module owns the
small destructive boundary around ``~/Applications`` so every rename and removal
is anchored to the exact directory inode that was originally validated.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import plistlib
import secrets
import signal
import stat
import sys
from typing import Any


CURRENT_APP_NAME = "Viventium.app"
LEGACY_APP_NAME = "Viventium Helper.app"
ACTIVATION_STATE_NAME = ".activation-state.json"


class TransactionSafetyError(RuntimeError):
    """The live filesystem no longer matches the reviewed transaction state."""


class InjectedTransactionFailure(RuntimeError):
    """Synthetic fault used only by unit tests to prove partial-failure rollback."""


@dataclass(frozen=True)
class Identity:
    device: int
    inode: int

    @classmethod
    def from_stat(cls, metadata: os.stat_result) -> Identity:
        return cls(device=metadata.st_dev, inode=metadata.st_ino)


@dataclass(frozen=True)
class DestinationState:
    root: str
    root_identity: Identity
    current_identity: Identity | None
    legacy_identity: Identity | None
    current_fingerprint: str | None
    legacy_fingerprint: str | None
    bundle_identifier: str
    executable_name: str
    current_name: str = CURRENT_APP_NAME
    legacy_name: str = LEGACY_APP_NAME


@dataclass(frozen=True)
class StageState:
    container_name: str
    container_identity: Identity
    app_identity: Identity
    app_fingerprint: str
    app_path: str


@dataclass(frozen=True)
class ActivationState:
    stage: StageState
    activated_identity: Identity
    current_backup_container_name: str | None
    current_backup_container_identity: Identity | None
    current_backup_identity: Identity | None
    legacy_backup_container_name: str | None
    legacy_backup_container_identity: Identity | None
    legacy_backup_identity: Identity | None


def _identity(value: dict[str, Any] | None) -> Identity | None:
    if value is None:
        return None
    return Identity(device=int(value["device"]), inode=int(value["inode"]))


def destination_from_json(raw: str) -> DestinationState:
    value = json.loads(raw)
    return DestinationState(
        root=str(value["root"]),
        root_identity=_identity(value["root_identity"]),  # type: ignore[arg-type]
        current_identity=_identity(value.get("current_identity")),
        legacy_identity=_identity(value.get("legacy_identity")),
        current_fingerprint=value.get("current_fingerprint"),
        legacy_fingerprint=value.get("legacy_fingerprint"),
        bundle_identifier=str(value.get("bundle_identifier", "ai.viventium.helper")),
        executable_name=str(value.get("executable_name", "ViventiumHelper")),
        current_name=str(value.get("current_name", CURRENT_APP_NAME)),
        legacy_name=str(value.get("legacy_name", LEGACY_APP_NAME)),
    )


def stage_from_json(raw: str) -> StageState:
    value = json.loads(raw)
    return StageState(
        container_name=str(value["container_name"]),
        container_identity=_identity(value["container_identity"]),  # type: ignore[arg-type]
        app_identity=_identity(value["app_identity"]),  # type: ignore[arg-type]
        app_fingerprint=str(value["app_fingerprint"]),
        app_path=str(value["app_path"]),
    )


def activation_from_json(raw: str) -> ActivationState:
    value = json.loads(raw)
    return ActivationState(
        stage=stage_from_json(json.dumps(value["stage"])),
        activated_identity=_identity(value["activated_identity"]),  # type: ignore[arg-type]
        current_backup_container_name=value.get("current_backup_container_name"),
        current_backup_container_identity=_identity(
            value.get("current_backup_container_identity")
        ),
        current_backup_identity=_identity(value.get("current_backup_identity")),
        legacy_backup_container_name=value.get("legacy_backup_container_name"),
        legacy_backup_container_identity=_identity(
            value.get("legacy_backup_container_identity")
        ),
        legacy_backup_identity=_identity(value.get("legacy_backup_identity")),
    )


def state_json(value: DestinationState | StageState | ActivationState) -> str:
    return json.dumps(asdict(value), sort_keys=True, separators=(",", ":"))


def _safe_name(name: str) -> str:
    if not name or name in {".", ".."} or "/" in name or "\0" in name:
        raise TransactionSafetyError(f"unsafe helper transaction name: {name!r}")
    return name


def _directory_flags() -> int:
    return os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)


def _open_root(destination: DestinationState) -> int:
    try:
        descriptor = os.open(destination.root, _directory_flags())
    except OSError as error:
        raise TransactionSafetyError(
            "helper Applications directory changed after validation"
        ) from error
    metadata = os.fstat(descriptor)
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or Identity.from_stat(metadata) != destination.root_identity
    ):
        os.close(descriptor)
        raise TransactionSafetyError(
            "helper Applications directory changed after validation"
        )
    return descriptor


def _stat_at(parent_fd: int, name: str) -> os.stat_result | None:
    try:
        return os.stat(_safe_name(name), dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None


def _verify_directory_at(
    parent_fd: int,
    name: str,
    expected: Identity,
    *,
    label: str,
) -> int:
    metadata = _stat_at(parent_fd, name)
    if (
        metadata is None
        or not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or Identity.from_stat(metadata) != expected
    ):
        raise TransactionSafetyError(f"{label} changed after validation")
    try:
        descriptor = os.open(name, _directory_flags(), dir_fd=parent_fd)
    except OSError as error:
        raise TransactionSafetyError(f"{label} changed after validation") from error
    opened = os.fstat(descriptor)
    if Identity.from_stat(opened) != expected:
        os.close(descriptor)
        raise TransactionSafetyError(f"{label} changed after validation")
    return descriptor


def _verify_expected_directory(
    parent_fd: int,
    name: str,
    expected: Identity | None,
    *,
    label: str,
) -> None:
    metadata = _stat_at(parent_fd, name)
    if expected is None:
        if metadata is not None:
            raise TransactionSafetyError(f"{label} appeared after validation")
        return
    if (
        metadata is None
        or not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or Identity.from_stat(metadata) != expected
    ):
        raise TransactionSafetyError(f"{label} changed after validation")


def _make_container(root_fd: int, prefix: str) -> tuple[str, Identity]:
    for _ in range(128):
        name = f"{prefix}{secrets.token_hex(8)}"
        try:
            os.mkdir(name, mode=0o700, dir_fd=root_fd)
        except FileExistsError:
            continue
        metadata = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
        return name, Identity.from_stat(metadata)
    raise TransactionSafetyError("could not allocate a private helper transaction directory")


def _mkdir_open(parent_fd: int, name: str, mode: int = 0o755) -> int:
    os.mkdir(_safe_name(name), mode=mode, dir_fd=parent_fd)
    return os.open(name, _directory_flags(), dir_fd=parent_fd)


def _copy_regular_file(source: Path, parent_fd: int, name: str, mode: int) -> None:
    source_metadata = os.lstat(source)
    if not stat.S_ISREG(source_metadata.st_mode):
        raise TransactionSafetyError(f"refusing non-regular helper source file: {source}")
    output_flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0)
    )
    output_fd = os.open(_safe_name(name), output_flags, mode, dir_fd=parent_fd)
    try:
        with source.open("rb") as source_handle, os.fdopen(output_fd, "wb", closefd=False) as output:
            while chunk := source_handle.read(1024 * 1024):
                output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
        os.fchmod(output_fd, mode)
    finally:
        os.close(output_fd)


def _write_bytes(parent_fd: int, name: str, payload: bytes, mode: int) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(_safe_name(name), flags, mode, dir_fd=parent_fd)
    try:
        offset = 0
        while offset < len(payload):
            written = os.write(descriptor, payload[offset:])
            if written <= 0:
                raise OSError("short write while persisting helper transaction state")
            offset += written
        os.fsync(descriptor)
        os.fchmod(descriptor, mode)
    finally:
        os.close(descriptor)


def _read_regular_file_at(
    parent_fd: int,
    name: str,
    *,
    label: str,
    maximum_bytes: int = 1024 * 1024,
) -> bytes:
    metadata = _stat_at(parent_fd, name)
    if (
        metadata is None
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or metadata.st_size > maximum_bytes
    ):
        raise TransactionSafetyError(f"unsafe {label}")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(_safe_name(name), flags, dir_fd=parent_fd)
    try:
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_uid != os.getuid()
            or Identity.from_stat(opened) != Identity.from_stat(metadata)
        ):
            raise TransactionSafetyError(f"{label} changed while opening")
        chunks: list[bytes] = []
        remaining = maximum_bytes + 1
        while remaining > 0:
            chunk = os.read(descriptor, min(remaining, 8192))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        if remaining <= 0:
            raise TransactionSafetyError(f"{label} is too large")
        closed = os.fstat(descriptor)
        if (
            Identity.from_stat(closed) != Identity.from_stat(opened)
            or closed.st_size != opened.st_size
            or closed.st_mtime_ns != opened.st_mtime_ns
        ):
            raise TransactionSafetyError(f"{label} changed while reading")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _bundle_fingerprint(
    parent_fd: int,
    name: str,
    expected: Identity,
    *,
    label: str,
) -> str:
    digest = hashlib.sha256(b"viventium-helper-bundle-v1\0")
    bundle_fd = _verify_directory_at(parent_fd, name, expected, label=label)

    def walk(directory_fd: int, prefix: str) -> None:
        for child_name in sorted(os.listdir(directory_fd)):
            _safe_name(child_name)
            metadata = os.stat(
                child_name,
                dir_fd=directory_fd,
                follow_symlinks=False,
            )
            if metadata.st_uid != os.getuid():
                raise TransactionSafetyError(f"unsafe owner in {label}")
            relative = f"{prefix}{child_name}".encode("utf-8")
            if stat.S_ISDIR(metadata.st_mode):
                digest.update(b"D\0" + relative + b"\0")
                child_fd = _verify_directory_at(
                    directory_fd,
                    child_name,
                    Identity.from_stat(metadata),
                    label=f"{label} child",
                )
                try:
                    walk(child_fd, f"{prefix}{child_name}/")
                    if Identity.from_stat(os.fstat(child_fd)) != Identity.from_stat(
                        metadata
                    ):
                        raise TransactionSafetyError(f"{label} changed while hashing")
                finally:
                    os.close(child_fd)
            elif stat.S_ISREG(metadata.st_mode):
                digest.update(b"F\0" + relative + b"\0")
                payload = _read_regular_file_at(
                    directory_fd,
                    child_name,
                    label=f"{label} file",
                    maximum_bytes=128 * 1024 * 1024,
                )
                digest.update(len(payload).to_bytes(8, "big"))
                digest.update(payload)
            else:
                raise TransactionSafetyError(f"unsafe entry in {label}")

    try:
        walk(bundle_fd, "")
    finally:
        os.close(bundle_fd)
    return digest.hexdigest()


def _validate_owned_bundle_shape(
    parent_fd: int,
    name: str,
    expected: Identity,
    *,
    bundle_identifier: str,
    executable_name: str,
    label: str,
) -> str:
    bundle_fd = _verify_directory_at(parent_fd, name, expected, label=label)
    try:
        contents_metadata = _stat_at(bundle_fd, "Contents")
        if contents_metadata is None:
            raise TransactionSafetyError(f"unrecognized {label}")
        contents_fd = _verify_directory_at(
            bundle_fd,
            "Contents",
            Identity.from_stat(contents_metadata),
            label=f"{label} Contents",
        )
        try:
            info_payload = _read_regular_file_at(
                contents_fd, "Info.plist", label=f"{label} Info.plist"
            )
            try:
                info = plistlib.loads(info_payload)
            except plistlib.InvalidFileException as error:
                raise TransactionSafetyError(f"invalid {label} Info.plist") from error
            if info.get("CFBundleIdentifier") != bundle_identifier:
                raise TransactionSafetyError(
                    "Refusing to replace or remove unrelated application"
                )
            macos_metadata = _stat_at(contents_fd, "MacOS")
            resources_metadata = _stat_at(contents_fd, "Resources")
            if macos_metadata is None or resources_metadata is None:
                raise TransactionSafetyError(f"unrecognized {label}")
            macos_fd = _verify_directory_at(
                contents_fd,
                "MacOS",
                Identity.from_stat(macos_metadata),
                label=f"{label} MacOS",
            )
            resources_fd = _verify_directory_at(
                contents_fd,
                "Resources",
                Identity.from_stat(resources_metadata),
                label=f"{label} Resources",
            )
            try:
                _read_regular_file_at(
                    macos_fd,
                    executable_name,
                    label=f"{label} executable",
                    maximum_bytes=128 * 1024 * 1024,
                )
                marker_metadata = _stat_at(
                    resources_fd, "viventium-owner.json"
                )
                if marker_metadata is not None:
                    marker_payload = _read_regular_file_at(
                        resources_fd,
                        "viventium-owner.json",
                        label=f"{label} ownership marker",
                    )
                    try:
                        marker = json.loads(marker_payload)
                    except (UnicodeDecodeError, json.JSONDecodeError) as error:
                        raise TransactionSafetyError(
                            f"invalid {label} ownership marker"
                        ) from error
                    if marker != {
                        "product": bundle_identifier,
                        "schema_version": 1,
                    }:
                        raise TransactionSafetyError(
                            f"unrecognized {label} ownership marker"
                        )
            finally:
                os.close(resources_fd)
                os.close(macos_fd)
        finally:
            os.close(contents_fd)
    finally:
        os.close(bundle_fd)
    return _bundle_fingerprint(parent_fd, name, expected, label=label)


def _verify_bundle_fingerprint(
    parent_fd: int,
    name: str,
    expected_identity: Identity,
    expected_fingerprint: str,
    *,
    label: str,
) -> None:
    actual = _bundle_fingerprint(
        parent_fd,
        name,
        expected_identity,
        label=label,
    )
    if not secrets.compare_digest(actual, expected_fingerprint):
        raise TransactionSafetyError(f"{label} contents changed after validation")


def _verify_captured_bundle(
    parent_fd: int,
    name: str,
    identity: Identity | None,
    fingerprint: str | None,
    *,
    label: str,
) -> None:
    _verify_expected_directory(parent_fd, name, identity, label=label)
    if identity is None:
        if fingerprint is not None:
            raise TransactionSafetyError(f"invalid {label} capture state")
        return
    if fingerprint is None:
        raise TransactionSafetyError(f"missing {label} ownership fingerprint")
    _verify_bundle_fingerprint(
        parent_fd,
        name,
        identity,
        fingerprint,
        label=label,
    )


def _remove_tree_at(parent_fd: int, name: str, expected: Identity, *, label: str) -> None:
    child_fd = _verify_directory_at(parent_fd, name, expected, label=label)
    try:
        for child_name in os.listdir(child_fd):
            metadata = os.stat(child_name, dir_fd=child_fd, follow_symlinks=False)
            if stat.S_ISDIR(metadata.st_mode):
                _remove_tree_at(
                    child_fd,
                    child_name,
                    Identity.from_stat(metadata),
                    label=f"{label} child",
                )
            else:
                os.unlink(child_name, dir_fd=child_fd)
    finally:
        os.close(child_fd)
    os.rmdir(name, dir_fd=parent_fd)


def capture_destination(
    root: Path,
    current_name: str = CURRENT_APP_NAME,
    legacy_name: str = LEGACY_APP_NAME,
    *,
    create_root: bool = False,
    bundle_identifier: str = "ai.viventium.helper",
    executable_name: str = "ViventiumHelper",
) -> DestinationState:
    root = Path(os.path.abspath(os.path.expanduser(root)))
    try:
        descriptor = os.open(root, _directory_flags())
    except FileNotFoundError as error:
        if not create_root:
            raise TransactionSafetyError("unsafe helper Applications directory") from error
        root_name = _safe_name(root.name)
        try:
            parent_fd = os.open(root.parent, _directory_flags())
        except OSError as parent_error:
            raise TransactionSafetyError(
                "unsafe helper Applications parent"
            ) from parent_error
        try:
            parent_metadata = os.fstat(parent_fd)
            if (
                not stat.S_ISDIR(parent_metadata.st_mode)
                or parent_metadata.st_uid != os.getuid()
            ):
                raise TransactionSafetyError("unsafe helper Applications parent")
            if _stat_at(parent_fd, root_name) is not None:
                raise TransactionSafetyError(
                    "helper Applications directory appeared during creation"
                )
            os.mkdir(root_name, mode=0o755, dir_fd=parent_fd)
            created_metadata = os.stat(
                root_name, dir_fd=parent_fd, follow_symlinks=False
            )
            created_identity = Identity.from_stat(created_metadata)
            created_fd = _verify_directory_at(
                parent_fd,
                root_name,
                created_identity,
                label="helper Applications directory",
            )
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
        try:
            rebound_fd = os.open(root, _directory_flags())
        except OSError as rebound_error:
            os.close(created_fd)
            raise TransactionSafetyError(
                "helper Applications directory changed during creation"
            ) from rebound_error
        rebound_identity = Identity.from_stat(os.fstat(rebound_fd))
        os.close(rebound_fd)
        if rebound_identity != created_identity:
            os.close(created_fd)
            raise TransactionSafetyError(
                "helper Applications directory changed during creation"
            )
        descriptor = created_fd
    except OSError as error:
        raise TransactionSafetyError("unsafe helper Applications directory") from error
    try:
        root_metadata = os.fstat(descriptor)
        if not stat.S_ISDIR(root_metadata.st_mode) or root_metadata.st_uid != os.getuid():
            raise TransactionSafetyError("unsafe helper Applications directory")

        def entry_state(name: str, label: str) -> tuple[Identity | None, str | None]:
            metadata = _stat_at(descriptor, name)
            if metadata is None:
                return None, None
            if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.getuid():
                raise TransactionSafetyError(f"unsafe {label}")
            identity = Identity.from_stat(metadata)
            fingerprint = _validate_owned_bundle_shape(
                descriptor,
                name,
                identity,
                bundle_identifier=bundle_identifier,
                executable_name=executable_name,
                label=label,
            )
            return identity, fingerprint

        current_identity, current_fingerprint = entry_state(
            current_name, "current helper bundle"
        )
        legacy_identity, legacy_fingerprint = entry_state(
            legacy_name, "legacy helper bundle"
        )

        return DestinationState(
            root=str(root),
            root_identity=Identity.from_stat(root_metadata),
            current_identity=current_identity,
            legacy_identity=legacy_identity,
            current_fingerprint=current_fingerprint,
            legacy_fingerprint=legacy_fingerprint,
            bundle_identifier=bundle_identifier,
            executable_name=executable_name,
            current_name=current_name,
            legacy_name=legacy_name,
        )
    finally:
        os.close(descriptor)


def stage_bundle(
    destination: DestinationState,
    *,
    built_executable: Path,
    info_plist: Path,
    icon_path: Path | None,
    bundle_identifier: str,
    executable_name: str,
) -> StageState:
    root_fd = _open_root(destination)
    container_name = ""
    container_identity: Identity | None = None
    try:
        _verify_captured_bundle(
            root_fd,
            destination.current_name,
            destination.current_identity,
            destination.current_fingerprint,
            label="current helper bundle",
        )
        _verify_captured_bundle(
            root_fd,
            destination.legacy_name,
            destination.legacy_identity,
            destination.legacy_fingerprint,
            label="legacy helper bundle",
        )
        container_name, container_identity = _make_container(
            root_fd, ".viventium-helper-staging."
        )
        container_fd = _verify_directory_at(
            root_fd,
            container_name,
            container_identity,
            label="helper staging directory",
        )
        try:
            app_fd = _mkdir_open(container_fd, CURRENT_APP_NAME)
            try:
                contents_fd = _mkdir_open(app_fd, "Contents")
                try:
                    macos_fd = _mkdir_open(contents_fd, "MacOS")
                    resources_fd = _mkdir_open(contents_fd, "Resources")
                    try:
                        _copy_regular_file(
                            Path(built_executable), macos_fd, executable_name, 0o755
                        )
                        _copy_regular_file(Path(info_plist), contents_fd, "Info.plist", 0o644)
                        if icon_path is not None:
                            _copy_regular_file(Path(icon_path), resources_fd, "Viventium.icns", 0o644)
                        marker = json.dumps(
                            {"product": bundle_identifier, "schema_version": 1},
                            sort_keys=True,
                            separators=(",", ":"),
                        ).encode("utf-8") + b"\n"
                        _write_bytes(
                            resources_fd, "viventium-owner.json", marker, 0o644
                        )
                    finally:
                        os.close(resources_fd)
                        os.close(macos_fd)
                finally:
                    os.close(contents_fd)
                app_identity = Identity.from_stat(os.fstat(app_fd))
            finally:
                os.close(app_fd)
            app_fingerprint = _bundle_fingerprint(
                container_fd,
                CURRENT_APP_NAME,
                app_identity,
                label="staged helper bundle",
            )
        finally:
            os.close(container_fd)
        return StageState(
            container_name=container_name,
            container_identity=container_identity,
            app_identity=app_identity,
            app_fingerprint=app_fingerprint,
            app_path=str(Path(destination.root) / container_name / CURRENT_APP_NAME),
        )
    except BaseException:
        if container_name and container_identity is not None:
            try:
                _remove_tree_at(
                    root_fd,
                    container_name,
                    container_identity,
                    label="helper staging directory",
                )
            except Exception:
                pass
        raise
    finally:
        os.close(root_fd)


def _rollback_activation_in_place(
    root_fd: int,
    destination: DestinationState,
    *,
    activated_identity: Identity | None,
    activated_fingerprint: str,
    current_backup: tuple[str, Identity, Identity] | None,
    legacy_backup: tuple[str, Identity, Identity] | None,
) -> None:
    if activated_identity is not None:
        _verify_bundle_fingerprint(
            root_fd,
            destination.current_name,
            activated_identity,
            activated_fingerprint,
            label="activated helper",
        )
        _remove_tree_at(
            root_fd,
            destination.current_name,
            activated_identity,
            label="activated helper",
        )
    if current_backup is not None:
        container_name, container_identity, backup_identity = current_backup
        container_fd = _verify_directory_at(
            root_fd, container_name, container_identity, label="current helper backup"
        )
        try:
            _verify_expected_directory(
                container_fd,
                destination.current_name,
                backup_identity,
                label="backed-up current helper",
            )
            _verify_expected_directory(
                root_fd,
                destination.current_name,
                None,
                label="current helper destination",
            )
            os.rename(
                destination.current_name,
                destination.current_name,
                src_dir_fd=container_fd,
                dst_dir_fd=root_fd,
            )
        finally:
            os.close(container_fd)
        _remove_tree_at(
            root_fd, container_name, container_identity, label="current helper backup"
        )
    if legacy_backup is not None:
        container_name, container_identity, backup_identity = legacy_backup
        container_fd = _verify_directory_at(
            root_fd, container_name, container_identity, label="legacy helper backup"
        )
        try:
            _verify_expected_directory(
                container_fd,
                destination.legacy_name,
                backup_identity,
                label="backed-up legacy helper",
            )
            _verify_expected_directory(
                root_fd,
                destination.legacy_name,
                None,
                label="legacy helper destination",
            )
            os.rename(
                destination.legacy_name,
                destination.legacy_name,
                src_dir_fd=container_fd,
                dst_dir_fd=root_fd,
            )
        finally:
            os.close(container_fd)
        _remove_tree_at(
            root_fd, container_name, container_identity, label="legacy helper backup"
        )


def _discard_persisted_activation(
    root_fd: int,
    stage: StageState,
) -> None:
    stage_fd = _verify_directory_at(
        root_fd,
        stage.container_name,
        stage.container_identity,
        label="helper staging directory",
    )
    try:
        metadata = _stat_at(stage_fd, ACTIVATION_STATE_NAME)
        if metadata is None:
            return
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid():
            raise TransactionSafetyError("unsafe persisted helper activation state")
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(ACTIVATION_STATE_NAME, flags, dir_fd=stage_fd)
        try:
            opened = os.fstat(descriptor)
            if (
                not stat.S_ISREG(opened.st_mode)
                or opened.st_uid != os.getuid()
                or Identity.from_stat(opened) != Identity.from_stat(metadata)
            ):
                raise TransactionSafetyError(
                    "persisted helper activation state changed while opening"
                )
        finally:
            os.close(descriptor)
        os.unlink(ACTIVATION_STATE_NAME, dir_fd=stage_fd)
        os.fsync(stage_fd)
    finally:
        os.close(stage_fd)


def activate_bundle(
    destination: DestinationState,
    stage: StageState,
    *,
    fault_after: str | None = None,
    persist_state: bool = False,
) -> ActivationState:
    root_fd = _open_root(destination)
    current_backup: tuple[str, Identity, Identity] | None = None
    legacy_backup: tuple[str, Identity, Identity] | None = None
    activated_identity: Identity | None = None
    try:
        _verify_captured_bundle(
            root_fd,
            destination.current_name,
            destination.current_identity,
            destination.current_fingerprint,
            label="current helper bundle",
        )
        _verify_captured_bundle(
            root_fd,
            destination.legacy_name,
            destination.legacy_identity,
            destination.legacy_fingerprint,
            label="legacy helper bundle",
        )
        stage_fd = _verify_directory_at(
            root_fd,
            stage.container_name,
            stage.container_identity,
            label="helper staging directory",
        )
        try:
            _verify_bundle_fingerprint(
                stage_fd,
                CURRENT_APP_NAME,
                stage.app_identity,
                stage.app_fingerprint,
                label="staged helper bundle",
            )
        finally:
            os.close(stage_fd)

        if destination.current_identity is not None:
            name, identity = _make_container(
                root_fd, ".viventium-helper-current-backup."
            )
            backup_fd = _verify_directory_at(
                root_fd, name, identity, label="current helper backup"
            )
            try:
                os.rename(
                    destination.current_name,
                    destination.current_name,
                    src_dir_fd=root_fd,
                    dst_dir_fd=backup_fd,
                )
            finally:
                os.close(backup_fd)
            current_backup = (name, identity, destination.current_identity)
            if fault_after == "current_backup":
                raise InjectedTransactionFailure("fault after current helper backup")

        if destination.legacy_identity is not None:
            name, identity = _make_container(
                root_fd, ".viventium-helper-legacy-backup."
            )
            backup_fd = _verify_directory_at(
                root_fd, name, identity, label="legacy helper backup"
            )
            try:
                os.rename(
                    destination.legacy_name,
                    destination.legacy_name,
                    src_dir_fd=root_fd,
                    dst_dir_fd=backup_fd,
                )
            finally:
                os.close(backup_fd)
            legacy_backup = (name, identity, destination.legacy_identity)
            if fault_after == "legacy_backup":
                raise InjectedTransactionFailure("fault after legacy helper backup")

        stage_fd = _verify_directory_at(
            root_fd,
            stage.container_name,
            stage.container_identity,
            label="helper staging directory",
        )
        try:
            os.rename(
                CURRENT_APP_NAME,
                destination.current_name,
                src_dir_fd=stage_fd,
                dst_dir_fd=root_fd,
            )
        finally:
            os.close(stage_fd)
        activated_metadata = _stat_at(root_fd, destination.current_name)
        if activated_metadata is None:
            raise TransactionSafetyError("activated helper is missing")
        activated_identity = Identity.from_stat(activated_metadata)
        if activated_identity != stage.app_identity:
            raise TransactionSafetyError("activated helper changed during activation")
        _verify_bundle_fingerprint(
            root_fd,
            destination.current_name,
            activated_identity,
            stage.app_fingerprint,
            label="activated helper",
        )
        if fault_after == "activation":
            raise InjectedTransactionFailure("fault after helper activation")

        activation = ActivationState(
            stage=stage,
            activated_identity=activated_identity,
            current_backup_container_name=current_backup[0] if current_backup else None,
            current_backup_container_identity=current_backup[1] if current_backup else None,
            current_backup_identity=current_backup[2] if current_backup else None,
            legacy_backup_container_name=legacy_backup[0] if legacy_backup else None,
            legacy_backup_container_identity=legacy_backup[1] if legacy_backup else None,
            legacy_backup_identity=legacy_backup[2] if legacy_backup else None,
        )
        if persist_state:
            stage_fd = _verify_directory_at(
                root_fd,
                stage.container_name,
                stage.container_identity,
                label="helper staging directory",
            )
            try:
                payload = state_json(activation).encode("utf-8") + b"\n"
                _write_bytes(stage_fd, ACTIVATION_STATE_NAME, payload, 0o600)
                os.fsync(stage_fd)
            finally:
                os.close(stage_fd)
            os.fsync(root_fd)
            if fault_after == "persistence":
                raise InjectedTransactionFailure(
                    "fault after helper activation state persistence"
                )
        return activation
    except BaseException as error:
        try:
            _rollback_activation_in_place(
                root_fd,
                destination,
                activated_identity=activated_identity,
                activated_fingerprint=stage.app_fingerprint,
                current_backup=current_backup,
                legacy_backup=legacy_backup,
            )
            _discard_persisted_activation(root_fd, stage)
        except BaseException as rollback_error:
            raise TransactionSafetyError(
                "helper activation failed and descriptor-safe rollback was incomplete"
            ) from rollback_error
        raise error
    finally:
        os.close(root_fd)


def _backup_tuple(
    activation: ActivationState,
    *,
    legacy: bool,
) -> tuple[str, Identity, Identity] | None:
    if legacy:
        values = (
            activation.legacy_backup_container_name,
            activation.legacy_backup_container_identity,
            activation.legacy_backup_identity,
        )
    else:
        values = (
            activation.current_backup_container_name,
            activation.current_backup_container_identity,
            activation.current_backup_identity,
        )
    if values == (None, None, None):
        return None
    if any(value is None for value in values):
        raise TransactionSafetyError("incomplete helper backup transaction state")
    return values  # type: ignore[return-value]


def _preflight_activation_state(
    root_fd: int,
    destination: DestinationState,
    activation: ActivationState,
) -> tuple[
    tuple[str, Identity, Identity] | None,
    tuple[str, Identity, Identity] | None,
]:
    try:
        _verify_bundle_fingerprint(
            root_fd,
            destination.current_name,
            activation.activated_identity,
            activation.stage.app_fingerprint,
            label="activated helper",
        )
    except TransactionSafetyError as error:
        raise TransactionSafetyError("activated helper changed after activation") from error
    current_backup = _backup_tuple(activation, legacy=False)
    legacy_backup = _backup_tuple(activation, legacy=True)
    for backup, fingerprint, label, app_name in (
        (
            current_backup,
            destination.current_fingerprint,
            "current helper backup",
            destination.current_name,
        ),
        (
            legacy_backup,
            destination.legacy_fingerprint,
            "legacy helper backup",
            destination.legacy_name,
        ),
    ):
        if backup is None:
            continue
        container_name, container_identity, app_identity = backup
        container_fd = _verify_directory_at(
            root_fd, container_name, container_identity, label=label
        )
        try:
            if fingerprint is None:
                raise TransactionSafetyError(f"missing {label} ownership fingerprint")
            _verify_bundle_fingerprint(
                container_fd,
                app_name,
                app_identity,
                fingerprint,
                label=label,
            )
        finally:
            os.close(container_fd)
    _verify_expected_directory(
        root_fd,
        destination.legacy_name,
        None if legacy_backup is not None else destination.legacy_identity,
        label="legacy helper destination",
    )
    stage_fd = _verify_directory_at(
        root_fd,
        activation.stage.container_name,
        activation.stage.container_identity,
        label="helper staging directory",
    )
    os.close(stage_fd)
    return current_backup, legacy_backup


def _read_persisted_activation(
    destination: DestinationState,
    stage: StageState,
) -> ActivationState | None:
    root_fd = _open_root(destination)
    try:
        stage_fd = _verify_directory_at(
            root_fd,
            stage.container_name,
            stage.container_identity,
            label="helper staging directory",
        )
        try:
            metadata = _stat_at(stage_fd, ACTIVATION_STATE_NAME)
            if metadata is None:
                return None
            if (
                not stat.S_ISREG(metadata.st_mode)
                or metadata.st_uid != os.getuid()
                or metadata.st_size > 64 * 1024
            ):
                raise TransactionSafetyError(
                    "unsafe persisted helper activation state"
                )
            flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(
                ACTIVATION_STATE_NAME,
                flags,
                dir_fd=stage_fd,
            )
            try:
                opened = os.fstat(descriptor)
                if (
                    not stat.S_ISREG(opened.st_mode)
                    or opened.st_uid != os.getuid()
                    or Identity.from_stat(opened) != Identity.from_stat(metadata)
                ):
                    raise TransactionSafetyError(
                        "persisted helper activation state changed while opening"
                    )
                chunks: list[bytes] = []
                remaining = 64 * 1024 + 1
                while remaining > 0:
                    chunk = os.read(descriptor, min(remaining, 8192))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    remaining -= len(chunk)
                if remaining <= 0:
                    raise TransactionSafetyError(
                        "persisted helper activation state is too large"
                    )
            finally:
                os.close(descriptor)
        finally:
            os.close(stage_fd)
    finally:
        os.close(root_fd)
    try:
        activation = activation_from_json(b"".join(chunks).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as error:
        raise TransactionSafetyError(
            "invalid persisted helper activation state"
        ) from error
    if activation.stage != stage:
        raise TransactionSafetyError(
            "persisted helper activation state does not match the staging identity"
        )
    return activation


def rollback_persisted_activation(
    destination: DestinationState,
    stage: StageState,
) -> None:
    activation = _read_persisted_activation(destination, stage)
    if activation is None:
        cleanup_stage(destination, stage)
        return
    rollback_bundle(destination, activation)


def commit_persisted_activation(
    destination: DestinationState,
    stage: StageState,
) -> None:
    activation = _read_persisted_activation(destination, stage)
    if activation is None:
        raise TransactionSafetyError("persisted helper activation state is missing")
    commit_bundle(destination, activation)


def rollback_bundle(destination: DestinationState, activation: ActivationState) -> None:
    root_fd = _open_root(destination)
    try:
        current_backup, legacy_backup = _preflight_activation_state(
            root_fd, destination, activation
        )
        _rollback_activation_in_place(
            root_fd,
            destination,
            activated_identity=activation.activated_identity,
            activated_fingerprint=activation.stage.app_fingerprint,
            current_backup=current_backup,
            legacy_backup=legacy_backup,
        )
        stage_metadata = _stat_at(root_fd, activation.stage.container_name)
        if stage_metadata is not None:
            _remove_tree_at(
                root_fd,
                activation.stage.container_name,
                activation.stage.container_identity,
                label="helper staging directory",
            )
    finally:
        os.close(root_fd)


def commit_bundle(destination: DestinationState, activation: ActivationState) -> None:
    root_fd = _open_root(destination)
    try:
        current_backup, legacy_backup = _preflight_activation_state(
            root_fd, destination, activation
        )
        for backup, label in (
            (current_backup, "current helper backup"),
            (legacy_backup, "legacy helper backup"),
        ):
            if backup is not None:
                _remove_tree_at(root_fd, backup[0], backup[1], label=label)
        _remove_tree_at(
            root_fd,
            activation.stage.container_name,
            activation.stage.container_identity,
            label="helper staging directory",
        )
    finally:
        os.close(root_fd)


def cleanup_stage(destination: DestinationState, stage: StageState) -> None:
    root_fd = _open_root(destination)
    try:
        metadata = _stat_at(root_fd, stage.container_name)
        if metadata is None:
            return
        container_fd = _verify_directory_at(
            root_fd,
            stage.container_name,
            stage.container_identity,
            label="helper staging directory",
        )
        try:
            app_metadata = _stat_at(container_fd, CURRENT_APP_NAME)
            if app_metadata is not None:
                _verify_bundle_fingerprint(
                    container_fd,
                    CURRENT_APP_NAME,
                    stage.app_identity,
                    stage.app_fingerprint,
                    label="staged helper",
                )
        finally:
            os.close(container_fd)
        _remove_tree_at(
            root_fd,
            stage.container_name,
            stage.container_identity,
            label="helper staging directory",
        )
    finally:
        os.close(root_fd)


def refresh_stage(destination: DestinationState, stage: StageState) -> StageState:
    root_fd = _open_root(destination)
    try:
        container_fd = _verify_directory_at(
            root_fd,
            stage.container_name,
            stage.container_identity,
            label="helper staging directory",
        )
        try:
            app_fingerprint = _bundle_fingerprint(
                container_fd,
                CURRENT_APP_NAME,
                stage.app_identity,
                label="staged helper bundle",
            )
        finally:
            os.close(container_fd)
    finally:
        os.close(root_fd)
    return StageState(
        container_name=stage.container_name,
        container_identity=stage.container_identity,
        app_identity=stage.app_identity,
        app_fingerprint=app_fingerprint,
        app_path=stage.app_path,
    )


def validate_stage(destination: DestinationState, stage: StageState) -> None:
    root_fd = _open_root(destination)
    try:
        container_fd = _verify_directory_at(
            root_fd,
            stage.container_name,
            stage.container_identity,
            label="helper staging directory",
        )
        try:
            _verify_bundle_fingerprint(
                container_fd,
                CURRENT_APP_NAME,
                stage.app_identity,
                stage.app_fingerprint,
                label="staged helper bundle",
            )
        finally:
            os.close(container_fd)
    finally:
        os.close(root_fd)


def uninstall_captured(destination: DestinationState) -> None:
    root_fd = _open_root(destination)
    try:
        _verify_captured_bundle(
            root_fd,
            destination.current_name,
            destination.current_identity,
            destination.current_fingerprint,
            label="current helper bundle",
        )
        _verify_captured_bundle(
            root_fd,
            destination.legacy_name,
            destination.legacy_identity,
            destination.legacy_fingerprint,
            label="legacy helper bundle",
        )
        if destination.current_identity is not None:
            _remove_tree_at(
                root_fd,
                destination.current_name,
                destination.current_identity,
                label="current helper bundle",
            )
        if destination.legacy_identity is not None:
            _remove_tree_at(
                root_fd,
                destination.legacy_name,
                destination.legacy_identity,
                label="legacy helper bundle",
            )
    finally:
        os.close(root_fd)


def backup_contains_identity(
    activation: ActivationState,
    expected: Identity | None,
) -> bool:
    if expected is None:
        return activation.current_backup_identity is None
    return activation.current_backup_identity == expected


def current_backup_executable(activation: ActivationState) -> Path:
    if activation.current_backup_container_name is None:
        raise TransactionSafetyError("current helper backup is absent")
    return (
        Path(activation.stage.app_path).parents[1]
        / activation.current_backup_container_name
        / CURRENT_APP_NAME
        / "Contents"
        / "MacOS"
        / "ViventiumHelper"
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    capture = subparsers.add_parser("capture")
    capture.add_argument("--root", required=True)
    capture.add_argument("--current-name", default=CURRENT_APP_NAME)
    capture.add_argument("--legacy-name", default=LEGACY_APP_NAME)
    capture.add_argument("--create-root", action="store_true")
    capture.add_argument("--bundle-identifier", default="ai.viventium.helper")
    capture.add_argument("--executable-name", default="ViventiumHelper")
    stage = subparsers.add_parser("stage")
    stage.add_argument("--destination-state", required=True)
    stage.add_argument("--built-executable", required=True)
    stage.add_argument("--info-plist", required=True)
    stage.add_argument("--icon-path", default="")
    stage.add_argument("--bundle-identifier", required=True)
    stage.add_argument("--executable-name", required=True)
    for command in ("activate", "cleanup-stage", "validate-stage", "refresh-stage"):
        child = subparsers.add_parser(command)
        child.add_argument("--destination-state", required=True)
        child.add_argument("--stage-state", required=True)
    for command in ("rollback", "commit"):
        child = subparsers.add_parser(command)
        child.add_argument("--destination-state", required=True)
        child.add_argument("--activation-state", required=True)
    for command in ("rollback-persisted", "commit-persisted"):
        child = subparsers.add_parser(command)
        child.add_argument("--destination-state", required=True)
        child.add_argument("--stage-state", required=True)
    uninstall = subparsers.add_parser("uninstall")
    uninstall.add_argument("--destination-state", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    def interrupt_transaction(_signum: int, _frame: Any) -> None:
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupt_transaction)
    try:
        if args.command == "capture":
            result = capture_destination(
                Path(args.root),
                args.current_name,
                args.legacy_name,
                create_root=args.create_root,
                bundle_identifier=args.bundle_identifier,
                executable_name=args.executable_name,
            )
            print(state_json(result))
        elif args.command == "stage":
            result = stage_bundle(
                destination_from_json(args.destination_state),
                built_executable=Path(args.built_executable),
                info_plist=Path(args.info_plist),
                icon_path=Path(args.icon_path) if args.icon_path else None,
                bundle_identifier=args.bundle_identifier,
                executable_name=args.executable_name,
            )
            print(state_json(result))
        elif args.command == "activate":
            result = activate_bundle(
                destination_from_json(args.destination_state),
                stage_from_json(args.stage_state),
                persist_state=True,
            )
            print(state_json(result))
        elif args.command == "cleanup-stage":
            cleanup_stage(
                destination_from_json(args.destination_state),
                stage_from_json(args.stage_state),
            )
        elif args.command == "validate-stage":
            validate_stage(
                destination_from_json(args.destination_state),
                stage_from_json(args.stage_state),
            )
        elif args.command == "refresh-stage":
            result = refresh_stage(
                destination_from_json(args.destination_state),
                stage_from_json(args.stage_state),
            )
            print(state_json(result))
        elif args.command == "rollback":
            rollback_bundle(
                destination_from_json(args.destination_state),
                activation_from_json(args.activation_state),
            )
        elif args.command == "commit":
            commit_bundle(
                destination_from_json(args.destination_state),
                activation_from_json(args.activation_state),
            )
        elif args.command == "rollback-persisted":
            rollback_persisted_activation(
                destination_from_json(args.destination_state),
                stage_from_json(args.stage_state),
            )
        elif args.command == "commit-persisted":
            commit_persisted_activation(
                destination_from_json(args.destination_state),
                stage_from_json(args.stage_state),
            )
        elif args.command == "uninstall":
            uninstall_captured(destination_from_json(args.destination_state))
        return 0
    except (OSError, ValueError, TransactionSafetyError) as error:
        message = str(error)
        if message == "unsafe helper Applications directory":
            sys.stderr.write(f"[viventium] Refusing {message}\n")
        else:
            sys.stderr.write(
                f"[viventium] Refusing unsafe helper filesystem transaction: {message}\n"
            )
        return 1
    except KeyboardInterrupt:
        sys.stderr.write("[viventium] Helper filesystem transaction interrupted safely.\n")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())

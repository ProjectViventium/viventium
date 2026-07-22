#!/usr/bin/env python3
"""Journal, activate, and roll back source-install upgrades without losing local work."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import shlex
import stat
import subprocess
import sys
import tarfile
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


SCHEMA_VERSION = 1
ACTIVE_POINTER = Path("state/upgrade-transaction-active.json")
BACKUP_ROOT = Path("upgrade-backups")
MONGO_IMAGE_DEFAULT = "mongo:8.0.17"
CHECKPOINT_FREE_RESERVE_BYTES = 10 * 1024 * 1024 * 1024
COMMIT_GENERATED_ROOTS = (
    "checkpoint",
    "docker-checkpoint",
    "candidate",
    "replaced-state",
    "restore-verification",
)
ROLLBACK_GENERATED_ROOTS = (
    "checkpoint",
    "docker-checkpoint",
    "candidate",
    "restore-verification",
)
SAFE_DOCKER_NAME = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-"
)


class UpgradeTransactionError(RuntimeError):
    pass


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def lexical(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path.expanduser())))


def contained(path: Path, root: Path, label: str) -> Path:
    candidate = lexical(path)
    boundary = lexical(root)
    try:
        candidate.relative_to(boundary)
    except ValueError as error:
        raise UpgradeTransactionError(f"{label} escapes its Viventium-owned boundary") from error
    return candidate


def validate_chain(path: Path, *, owned_from: Path | None = None) -> None:
    candidate = lexical(path)
    owned_root = lexical(owned_from) if owned_from else None
    current = Path(candidate.anchor)
    for part in candidate.parts[1:]:
        current /= part
        if not current.exists() and not current.is_symlink():
            continue
        metadata = current.lstat()
        if stat.S_ISLNK(metadata.st_mode):
            raise UpgradeTransactionError("Viventium upgrade path contains a symlink")
        if current != candidate and not stat.S_ISDIR(metadata.st_mode):
            raise UpgradeTransactionError("Viventium upgrade parent is not a directory")
        if owned_root is not None:
            try:
                current.relative_to(owned_root)
            except ValueError:
                pass
            else:
                if metadata.st_uid != os.getuid():
                    raise UpgradeTransactionError("Viventium upgrade path is not owned by the current user")


def ensure_private_directory(path: Path, *, boundary: Path) -> Path:
    target = contained(path, boundary, "private directory")
    root = lexical(boundary)
    validate_chain(root)
    if not root.exists():
        raise UpgradeTransactionError("Viventium App Support root is missing")
    root_metadata = root.lstat()
    if not stat.S_ISDIR(root_metadata.st_mode) or root_metadata.st_uid != os.getuid():
        raise UpgradeTransactionError("Viventium App Support root is unsafe")
    current = root
    for part in target.relative_to(root).parts:
        current /= part
        if current.exists() or current.is_symlink():
            validate_chain(current, owned_from=root)
            metadata = current.lstat()
            if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.getuid():
                raise UpgradeTransactionError("Viventium private directory is unsafe")
        else:
            current.mkdir(mode=0o700)
        if stat.S_IMODE(current.lstat().st_mode) != 0o700:
            current.chmod(0o700)
    return target


def surface_logical_size(path: Path, *, allow_symlinks: bool = False) -> int:
    if not path.exists() and not path.is_symlink():
        return 0
    validate_chain(path)
    metadata = path.lstat()
    if metadata.st_uid != os.getuid():
        raise UpgradeTransactionError("Upgrade surface is not owned by the current user")
    if stat.S_ISREG(metadata.st_mode):
        return metadata.st_size
    if not stat.S_ISDIR(metadata.st_mode):
        raise UpgradeTransactionError("Upgrade surfaces must be regular files or directories")
    total = 0
    for current, names, filenames in os.walk(path, topdown=True, followlinks=False):
        current_path = Path(current)
        current_metadata = current_path.lstat()
        if current_path.is_symlink() or current_metadata.st_uid != os.getuid():
            raise UpgradeTransactionError("Upgrade surface contains an unsafe directory")
        for name in list(names):
            child = current_path / name
            child_metadata = child.lstat()
            if stat.S_ISLNK(child_metadata.st_mode):
                if not allow_symlinks:
                    raise UpgradeTransactionError("Upgrade surface contains a symlink")
                if child_metadata.st_uid != os.getuid():
                    raise UpgradeTransactionError("Upgrade surface contains another user's entry")
                names.remove(name)
                continue
            if child_metadata.st_uid != os.getuid():
                raise UpgradeTransactionError("Upgrade surface contains another user's entry")
        for name in filenames:
            child = current_path / name
            child_metadata = child.lstat()
            if stat.S_ISLNK(child_metadata.st_mode):
                if not allow_symlinks:
                    raise UpgradeTransactionError("Upgrade surface contains a symlink")
                if child_metadata.st_uid != os.getuid():
                    raise UpgradeTransactionError("Upgrade surface contains another user's entry")
                continue
            if child_metadata.st_uid != os.getuid():
                raise UpgradeTransactionError("Upgrade surface contains another user's entry")
            if not stat.S_ISREG(child_metadata.st_mode):
                raise UpgradeTransactionError("Upgrade surface contains a special file")
            total += child_metadata.st_size
    return total


def ensure_checkpoint_capacity(path: Path, payload_bytes: int) -> None:
    if payload_bytes < 0:
        raise UpgradeTransactionError("Upgrade checkpoint size estimate is invalid")
    required = payload_bytes + CHECKPOINT_FREE_RESERVE_BYTES
    try:
        available = shutil.disk_usage(path).free
    except OSError as error:
        raise UpgradeTransactionError("Upgrade checkpoint free disk space is unavailable") from error
    if available < required:
        required_gib = (required + 1024**3 - 1) // 1024**3
        available_gib = available // 1024**3
        raise UpgradeTransactionError(
            "Upgrade checkpoint needs at least "
            f"{required_gib} GiB free including its safety reserve; only {available_gib} GiB is available"
        )


def write_json_atomic(path: Path, payload: dict[str, Any], *, boundary: Path) -> None:
    target = contained(path, boundary, "transaction metadata")
    ensure_private_directory(target.parent, boundary=boundary)
    if target.exists() or target.is_symlink():
        validate_chain(target, owned_from=boundary)
        metadata = target.lstat()
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid():
            raise UpgradeTransactionError("Transaction metadata target is unsafe")
    temporary = target.with_name(f".{target.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        target.chmod(0o600)
    finally:
        if temporary.exists():
            temporary.unlink()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise UpgradeTransactionError("Upgrade snapshot contains a non-regular file")
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    finally:
        os.close(descriptor)
    return digest.hexdigest()


def surface_manifest(path: Path, *, allow_symlinks: bool = False) -> dict[str, Any]:
    if not path.exists() and not path.is_symlink():
        return {"kind": "absent", "files": []}
    validate_chain(path)
    metadata = path.lstat()
    if metadata.st_uid != os.getuid():
        raise UpgradeTransactionError("Upgrade surface is not owned by the current user")
    if stat.S_ISREG(metadata.st_mode):
        return {
            "kind": "file",
            "mode": stat.S_IMODE(metadata.st_mode),
            "size": metadata.st_size,
            "sha256": sha256_file(path),
            "files": [],
        }
    if not stat.S_ISDIR(metadata.st_mode):
        raise UpgradeTransactionError("Upgrade surfaces must be regular files or directories")
    files: list[dict[str, Any]] = []
    directories: list[dict[str, Any]] = []
    symlinks: list[dict[str, str]] = []
    for current, names, filenames in os.walk(path, topdown=True, followlinks=False):
        current_path = Path(current)
        relative_dir = current_path.relative_to(path)
        current_metadata = current_path.lstat()
        if current_path.is_symlink() or current_metadata.st_uid != os.getuid():
            raise UpgradeTransactionError("Upgrade surface contains an unsafe directory")
        directories.append(
            {"path": relative_dir.as_posix(), "mode": stat.S_IMODE(current_metadata.st_mode)}
        )
        for name in list(names):
            child = current_path / name
            child_metadata = child.lstat()
            if stat.S_ISLNK(child_metadata.st_mode):
                if not allow_symlinks:
                    raise UpgradeTransactionError("Upgrade surface contains a symlink")
                if child_metadata.st_uid != os.getuid():
                    raise UpgradeTransactionError("Upgrade surface contains another user's entry")
                symlinks.append(
                    {"path": child.relative_to(path).as_posix(), "target": os.readlink(child)}
                )
                names.remove(name)
                continue
            if child_metadata.st_uid != os.getuid():
                raise UpgradeTransactionError("Upgrade surface contains another user's entry")
        for name in filenames:
            child = current_path / name
            child_metadata = child.lstat()
            if stat.S_ISLNK(child_metadata.st_mode):
                if not allow_symlinks:
                    raise UpgradeTransactionError("Upgrade surface contains a symlink")
                if child_metadata.st_uid != os.getuid():
                    raise UpgradeTransactionError("Upgrade surface contains another user's entry")
                symlinks.append(
                    {"path": child.relative_to(path).as_posix(), "target": os.readlink(child)}
                )
                continue
            if child_metadata.st_uid != os.getuid():
                raise UpgradeTransactionError("Upgrade surface contains another user's entry")
            if not stat.S_ISREG(child_metadata.st_mode):
                raise UpgradeTransactionError("Upgrade surface contains a special file")
            relative = child.relative_to(path).as_posix()
            files.append(
                {
                    "path": relative,
                    "mode": stat.S_IMODE(child_metadata.st_mode),
                    "size": child_metadata.st_size,
                    "sha256": sha256_file(child),
                }
            )
    files.sort(key=lambda item: item["path"])
    directories.sort(key=lambda item: item["path"])
    symlinks.sort(key=lambda item: item["path"])
    return {
        "kind": "directory",
        "mode": stat.S_IMODE(metadata.st_mode),
        "directories": directories,
        "files": files,
        "symlinks": symlinks,
    }


def copy_surface(source: Path, destination: Path, *, allow_symlinks: bool = False) -> None:
    manifest = surface_manifest(source, allow_symlinks=allow_symlinks)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if manifest["kind"] == "file":
        shutil.copy2(source, destination, follow_symlinks=False)
    elif manifest["kind"] == "directory":
        if sys.platform == "darwin":
            completed = subprocess.run(
                ["/bin/cp", "-cR", str(source), str(destination)],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if completed.returncode != 0:
                if destination.exists():
                    shutil.rmtree(destination)
                shutil.copytree(
                    source,
                    destination,
                    symlinks=allow_symlinks,
                    copy_function=shutil.copy2,
                )
        else:
            shutil.copytree(
                source,
                destination,
                symlinks=allow_symlinks,
                copy_function=shutil.copy2,
            )
    else:
        return
    if surface_manifest(destination, allow_symlinks=allow_symlinks) != manifest:
        raise UpgradeTransactionError("Upgrade snapshot verification failed")


def parse_runtime_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists() and not path.is_symlink():
        return values
    validate_chain(path)
    if path.is_symlink() or not path.is_file():
        raise UpgradeTransactionError("Generated runtime environment is unsafe")
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        if "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        key = key.strip()
        if key not in {
            "VIVENTIUM_RUNTIME_PROFILE",
            "VIVENTIUM_LOCAL_MONGO_CONTAINER",
            "VIVENTIUM_LOCAL_MONGO_VOLUME",
            "VIVENTIUM_LOCAL_MONGO_DATA_PATH",
            "MONGO_IMAGE",
        }:
            continue
        try:
            parsed = shlex.split(raw_value, comments=True, posix=True)
        except ValueError as error:
            raise UpgradeTransactionError("Generated runtime environment is malformed") from error
        if len(parsed) > 1:
            raise UpgradeTransactionError("Generated runtime environment value is ambiguous")
        values[key] = parsed[0] if parsed else ""
    return values


def validate_docker_name(value: str, label: str) -> str:
    if (
        not value
        or value[0] in {"-", "."}
        or len(value) > 255
        or any(character not in SAFE_DOCKER_NAME for character in value)
    ):
        raise UpgradeTransactionError(f"{label} is unsafe")
    return value


def validate_docker_image(value: str) -> str:
    if (
        not value
        or value.startswith("-")
        or len(value) > 512
        or any(character.isspace() or ord(character) < 32 for character in value)
    ):
        raise UpgradeTransactionError("MongoDB container image reference is unsafe")
    return value


def docker_command(docker: str, *args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    timeout = 600 if args[:1] == ("run",) else 30
    try:
        completed = subprocess.run(
            [docker, *args],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise UpgradeTransactionError("Docker storage checkpoint command did not complete safely") from error
    if check and completed.returncode != 0:
        raise UpgradeTransactionError("Docker storage checkpoint command failed")
    return completed


def docker_ready() -> str:
    docker = shutil.which("docker")
    if not docker:
        raise UpgradeTransactionError("Docker is required to checkpoint the active MongoDB volume")
    docker_command(docker, "info", "--format", "{{.ServerVersion}}")
    return docker


def docker_volume_exists(docker: str, volume: str) -> bool:
    result = docker_command(docker, "volume", "inspect", volume, check=False)
    return result.returncode == 0


def ensure_docker_volume_stopped(docker: str, volume: str) -> None:
    result = docker_command(docker, "ps", "-q", "--filter", f"volume={volume}")
    if result.stdout.strip():
        raise UpgradeTransactionError("MongoDB volume is still mounted by a running container")


def tar_manifest(path: Path) -> dict[str, Any]:
    validate_chain(path)
    if path.is_symlink() or not path.is_file():
        raise UpgradeTransactionError("Docker volume checkpoint archive is unsafe")
    entries: list[dict[str, Any]] = []
    try:
        with tarfile.open(path, "r:") as archive:
            for member in archive.getmembers():
                raw = member.name
                normalized = raw[2:] if raw.startswith("./") else raw
                if normalized in {"", "."}:
                    continue
                relative = PurePosixPath(normalized)
                if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
                    raise UpgradeTransactionError("Docker volume checkpoint contains an unsafe path")
                if member.isdir():
                    entries.append({"path": relative.as_posix(), "kind": "directory", "mode": member.mode})
                    continue
                if not member.isfile():
                    raise UpgradeTransactionError("Docker volume checkpoint contains a special entry")
                extracted = archive.extractfile(member)
                if extracted is None:
                    raise UpgradeTransactionError("Docker volume checkpoint file is unreadable")
                digest = hashlib.sha256()
                size = 0
                for chunk in iter(lambda: extracted.read(1024 * 1024), b""):
                    size += len(chunk)
                    digest.update(chunk)
                if size != member.size:
                    raise UpgradeTransactionError("Docker volume checkpoint file size is inconsistent")
                entries.append(
                    {
                        "path": relative.as_posix(),
                        "kind": "file",
                        "mode": member.mode,
                        "size": member.size,
                        "sha256": digest.hexdigest(),
                    }
                )
    except tarfile.TarError as error:
        raise UpgradeTransactionError("Docker volume checkpoint archive is invalid") from error
    entries.sort(key=lambda item: (item["path"], item["kind"]))
    return {"entries": entries}


def docker_archive_volume(docker: str, volume: str, image: str, archive: Path) -> dict[str, Any]:
    archive.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    docker_command(
        docker,
        "run",
        "--rm",
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--entrypoint",
        "/bin/sh",
        "-v",
        f"{volume}:/source:ro",
        "-v",
        f"{archive.parent}:/checkpoint",
        image,
        "-c",
        f"cd /source && tar -cf /checkpoint/{archive.name} .",
    )
    if not archive.is_file() or archive.is_symlink():
        raise UpgradeTransactionError("Docker volume checkpoint was not created")
    return {
        "archive_sha256": sha256_file(archive),
        "manifest": tar_manifest(archive),
    }


def docker_volume_logical_size(docker: str, volume: str, image: str) -> int:
    docker_command(docker, "image", "inspect", image)
    result = docker_command(
        docker,
        "run",
        "--rm",
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--entrypoint",
        "/bin/sh",
        "-v",
        f"{volume}:/source:ro",
        image,
        "-c",
        "du -sk /source",
    )
    try:
        kibibytes = int(result.stdout.decode("utf-8").split()[0])
    except (IndexError, UnicodeDecodeError, ValueError) as error:
        raise UpgradeTransactionError("Docker volume size could not be measured safely") from error
    if kibibytes < 0:
        raise UpgradeTransactionError("Docker volume size is invalid")
    return kibibytes * 1024


def mongo_storage_inventory(support: Path, runtime_dir: Path) -> tuple[dict[str, Any], list[tuple[str, Path]]]:
    values: dict[str, str] = {}
    for env_file in (runtime_dir / "runtime.env", runtime_dir / "runtime.local.env"):
        values.update(parse_runtime_env(env_file))
    profile = values.get("VIVENTIUM_RUNTIME_PROFILE", "isolated").strip().lower() or "isolated"
    explicit_data = values.get("VIVENTIUM_LOCAL_MONGO_DATA_PATH", "").strip()
    extra_surfaces: list[tuple[str, Path]] = []
    if explicit_data:
        data_path = contained(Path(explicit_data), support, "MongoDB data path")
        covered = any(
            data_path == root or root in data_path.parents
            for root in (support / "state" / "runtime", support / "state" / "mongo-data", support / "data")
        )
        if not covered:
            extra_surfaces.append(("explicit-mongo-data", data_path))
        return {
            "backend": "app_support_bind",
            "profile": profile,
            "path": str(data_path),
        }, extra_surfaces
    if profile in {"isolated", "native"}:
        data_path = support / ("data/mongodb" if profile == "native" else f"state/runtime/{profile}/mongo-data")
        return {
            "backend": "app_support_bind",
            "profile": profile,
            "path": str(data_path),
        }, extra_surfaces
    if profile != "compat":
        raise UpgradeTransactionError("Active runtime profile has unknown MongoDB storage semantics")
    container = validate_docker_name(
        values.get("VIVENTIUM_LOCAL_MONGO_CONTAINER", "viventium-mongodb"),
        "MongoDB container name",
    )
    volume = validate_docker_name(
        values.get("VIVENTIUM_LOCAL_MONGO_VOLUME", f"{container}-data"),
        "MongoDB volume name",
    )
    image = validate_docker_image(values.get("MONGO_IMAGE", MONGO_IMAGE_DEFAULT))
    native_data_path = support / "state" / "runtime" / profile / "mongo-data"
    native_pid = support / "state" / "runtime" / profile / "mongodb-native.pid"
    if native_pid.is_file() and not native_pid.is_symlink():
        try:
            pid = int(native_pid.read_text(encoding="utf-8").strip())
            os.kill(pid, 0)
        except (OSError, ValueError):
            pass
        else:
            return {
                "backend": "app_support_bind",
                "profile": profile,
                "path": str(native_data_path),
                "observed_from": "running_native_pid",
            }, extra_surfaces
    try:
        docker = docker_ready()
    except UpgradeTransactionError:
        if native_data_path.is_dir():
            return {
                "backend": "app_support_bind",
                "profile": profile,
                "path": str(native_data_path),
                "observed_from": "native_data_without_available_docker",
            }, extra_surfaces
        raise
    inspected = docker_command(docker, "container", "inspect", container, check=False)
    if inspected.returncode == 0:
        try:
            containers = json.loads(inspected.stdout.decode("utf-8"))
            container_info = containers[0]
            mounts = container_info["Mounts"]
        except (IndexError, KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise UpgradeTransactionError("Running MongoDB container storage inventory is unreadable") from error
        matching = [item for item in mounts if item.get("Destination") == "/data/db"]
        if len(matching) != 1:
            raise UpgradeTransactionError("Running MongoDB container has ambiguous database storage")
        mount = matching[0]
        actual_image = validate_docker_image(str(container_info.get("Config", {}).get("Image") or image))
        if mount.get("Type") == "volume":
            return {
                "backend": "docker_named_volume",
                "profile": profile,
                "volume_name": validate_docker_name(str(mount.get("Name") or ""), "MongoDB volume name"),
                "image": actual_image,
                "observed_from": "container_inspect",
            }, extra_surfaces
        if mount.get("Type") == "bind":
            data_path = contained(Path(str(mount.get("Source") or "")), support, "MongoDB bind path")
            covered = any(
                data_path == root or root in data_path.parents
                for root in (
                    support / "state" / "runtime",
                    support / "state" / "mongo-data",
                    support / "data",
                )
            )
            if not covered:
                extra_surfaces.append(("explicit-mongo-data", data_path))
            return {
                "backend": "app_support_bind",
                "profile": profile,
                "path": str(data_path),
                "observed_from": "container_inspect",
            }, extra_surfaces
        raise UpgradeTransactionError("Running MongoDB container uses an unsupported storage backend")
    if not docker_volume_exists(docker, volume) and native_data_path.is_dir():
        return {
            "backend": "app_support_bind",
            "profile": profile,
            "path": str(native_data_path),
            "observed_from": "native_data_with_no_docker_volume",
        }, extra_surfaces
    return {
        "backend": "docker_named_volume",
        "profile": profile,
        "volume_name": volume,
        "image": image,
        "observed_from": "configured_volume_inventory",
    }, extra_surfaces


def checkpoint_surface_candidates(
    support: Path,
    config_file: Path,
    runtime_dir: Path,
    extra_surfaces: list[tuple[str, Path]] | None = None,
) -> list[tuple[str, Path, bool]]:
    candidates = [
        ("config", contained(config_file, support, "canonical config"), False),
        ("runtime", contained(runtime_dir, support, "generated runtime"), False),
        ("runtime-state", support / "state" / "runtime", False),
        ("bootstrap-python", support / "state" / "bootstrap-python", True),
        ("legacy-mongo-state", support / "state" / "mongo-data", False),
        ("native-data", support / "data", False),
    ]
    candidates.extend((label, path, False) for label, path in (extra_surfaces or []))
    return candidates


def make_immutable(path: Path) -> None:
    if not path.exists():
        return
    if path.is_symlink():
        raise UpgradeTransactionError("Immutable checkpoint root must not be a symlink")
    if path.is_file():
        path.chmod(0o400)
        return
    for current, _, filenames in os.walk(path, topdown=False, followlinks=False):
        current_path = Path(current)
        for name in filenames:
            child = current_path / name
            if child.is_symlink():
                continue
            child.chmod(0o400)
        current_path.chmod(0o500)


def apply_manifest_modes(path: Path, manifest: dict[str, Any]) -> None:
    if manifest["kind"] == "file":
        path.chmod(int(manifest["mode"]))
        return
    if manifest["kind"] != "directory":
        return
    for item in reversed(manifest.get("directories", [])):
        directory = path if item["path"] == "." else path / item["path"]
        directory.chmod(int(item["mode"]))
    for item in manifest.get("files", []):
        (path / item["path"]).chmod(int(item["mode"]))
    path.chmod(int(manifest["mode"]))


def git(repo: Path, *args: str, input_bytes: bytes | None = None, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        input=input_bytes,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and completed.returncode != 0:
        raise UpgradeTransactionError("Git transaction command failed")
    return completed


def git_text(repo: Path, *args: str) -> str:
    return git(repo, *args).stdout.decode("utf-8", errors="strict").strip()


def tracked_clean(repo: Path) -> bool:
    return git(repo, "diff", "--quiet", check=False).returncode == 0 and git(
        repo, "diff", "--cached", "--quiet", check=False
    ).returncode == 0


def safe_component_path(repo: Path, raw: Any) -> Path:
    if not isinstance(raw, str) or not raw or "\\" in raw:
        raise UpgradeTransactionError("Component lock contains an unsafe path")
    relative = PurePosixPath(raw)
    if relative.is_absolute() or relative.as_posix() != raw or any(
        part in {"", ".", ".."} for part in relative.parts
    ):
        raise UpgradeTransactionError("Component lock contains an unsafe path")
    candidate = contained(repo.joinpath(*relative.parts), repo, "component path")
    if candidate.is_symlink():
        raise UpgradeTransactionError("Managed component path must not be a symlink")
    return candidate


def repo_record(repo: Path, *, name: str, expected_target: str = "") -> dict[str, Any]:
    validate_chain(repo)
    if git(repo, "rev-parse", "--git-dir", check=False).returncode != 0:
        raise UpgradeTransactionError("Managed source path is not a Git checkout")
    head = git_text(repo, "rev-parse", "HEAD")
    symbolic = git(repo, "symbolic-ref", "-q", "HEAD", check=False)
    head_ref = symbolic.stdout.decode("utf-8").strip() if symbolic.returncode == 0 else ""
    clean = tracked_clean(repo)
    return {
        "name": name,
        "path": str(repo),
        "existed_before": True,
        "old_head": head,
        "old_head_ref": head_ref,
        "expected_target": expected_target,
        "protected_dirty": not clean,
        "observed_heads": [head],
    }


def absent_component_record(path: Path, *, name: str, expected_target: str = "") -> dict[str, Any]:
    return {
        "name": name,
        "path": str(path),
        "existed_before": False,
        "old_head": "",
        "old_head_ref": "",
        "expected_target": expected_target,
        "protected_dirty": False,
        "observed_heads": [],
    }


def read_lock_repositories(repo: Path, lock_file: Path) -> list[dict[str, Any]]:
    lock_path = contained(lock_file, repo, "component lock")
    validate_chain(lock_path)
    if lock_path.is_symlink() or not lock_path.is_file():
        raise UpgradeTransactionError("Component lock is missing or unsafe")
    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise UpgradeTransactionError("Component lock is invalid") from error
    components = payload.get("components")
    if not isinstance(components, list):
        raise UpgradeTransactionError("Component lock is invalid")
    records: list[dict[str, Any]] = []
    for item in components:
        if not isinstance(item, dict):
            raise UpgradeTransactionError("Component lock entry is invalid")
        path = safe_component_path(repo, item.get("path"))
        name = str(item.get("name") or item.get("path") or "component")
        expected_target = str(item.get("ref") or "")
        records.append(
            repo_record(path, name=name, expected_target=expected_target)
            if path.exists()
            else absent_component_record(path, name=name, expected_target=expected_target)
        )
    return records


def reconcile_component_records(ledger: dict[str, Any]) -> None:
    repo = Path(ledger["repo_root"])
    current_records = read_lock_repositories(repo, Path(ledger["lock_file"]))
    known = {record["path"]: record for record in ledger["repositories"]}
    for current in current_records:
        existing = known.get(current["path"])
        if existing is not None:
            if current.get("expected_target"):
                existing["expected_target"] = current["expected_target"]
            continue
        if current.get("existed_before"):
            raise UpgradeTransactionError(
                "A newly managed component path already contains uncheckpointed local content"
            )
        ledger["repositories"].append(current)
        known[current["path"]] = current


def snapshot_surfaces(
    transaction: Path,
    support: Path,
    config_file: Path,
    runtime_dir: Path,
    extra_surfaces: list[tuple[str, Path]] | None = None,
) -> list[dict[str, Any]]:
    candidates = checkpoint_surface_candidates(
        support,
        config_file,
        runtime_dir,
        extra_surfaces,
    )
    manifests: list[dict[str, Any]] = []
    checkpoint = transaction / "checkpoint"
    checkpoint.mkdir(mode=0o700)
    for label, path, allow_symlinks in candidates:
        manifest = surface_manifest(path, allow_symlinks=allow_symlinks)
        backup = checkpoint / label
        copy_surface(path, backup, allow_symlinks=allow_symlinks)
        if backup.exists():
            make_immutable(backup)
        manifests.append(
            {
                "label": label,
                "path": str(path),
                "backup": str(backup),
                "manifest": manifest,
                "allow_symlinks": allow_symlinks,
            }
        )
    checkpoint.chmod(0o500)
    return manifests


def ledger_path(transaction: Path) -> Path:
    return transaction / "ledger.json"


def load_ledger(transaction: Path) -> dict[str, Any]:
    transaction = lexical(transaction)
    validate_chain(transaction)
    path = ledger_path(transaction)
    validate_chain(path)
    try:
        ledger = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise UpgradeTransactionError("Upgrade transaction ledger is unreadable") from error
    if ledger.get("schema_version") != SCHEMA_VERSION or lexical(Path(ledger.get("transaction_path", ""))) != transaction:
        raise UpgradeTransactionError("Upgrade transaction ledger is invalid")
    support = lexical(Path(ledger.get("app_support_dir", "")))
    contained(transaction, support / BACKUP_ROOT, "upgrade transaction")
    if transaction.is_symlink() or transaction.lstat().st_uid != os.getuid():
        raise UpgradeTransactionError("Upgrade transaction directory is unsafe")
    runner = contained(Path(str(ledger.get("transaction_runner") or "")), transaction, "transaction runner")
    validate_chain(runner, owned_from=transaction)
    expected_runner_hash = str(ledger.get("transaction_runner_sha256") or "")
    if (
        runner.is_symlink()
        or not runner.is_file()
        or runner.lstat().st_uid != os.getuid()
        or not expected_runner_hash
        or sha256_file(runner) != expected_runner_hash
    ):
        raise UpgradeTransactionError("Immutable upgrade transaction runner failed verification")
    return ledger


def save_ledger(transaction: Path, ledger: dict[str, Any]) -> None:
    support = lexical(Path(ledger["app_support_dir"]))
    write_json_atomic(ledger_path(transaction), ledger, boundary=support)


def remove_transaction_owned_path(path: Path, *, transaction: Path) -> bool:
    target = contained(path, transaction, "upgrade cleanup target")
    if not target.exists() and not target.is_symlink():
        return False
    validate_chain(target, owned_from=transaction)
    metadata = target.lstat()
    if metadata.st_uid != os.getuid() or stat.S_ISLNK(metadata.st_mode):
        raise UpgradeTransactionError("Upgrade cleanup target is unsafe")
    if stat.S_ISREG(metadata.st_mode):
        target.unlink()
        return True
    if not stat.S_ISDIR(metadata.st_mode):
        raise UpgradeTransactionError("Upgrade cleanup target is not a regular file or directory")
    directories: list[Path] = []
    for current, names, filenames in os.walk(target, topdown=True, followlinks=False):
        current_path = Path(current)
        current_metadata = current_path.lstat()
        if current_metadata.st_uid != os.getuid() or not stat.S_ISDIR(current_metadata.st_mode):
            raise UpgradeTransactionError("Upgrade cleanup tree is unsafe")
        directories.append(current_path)
        for name in [*names, *filenames]:
            child_metadata = (current_path / name).lstat()
            if child_metadata.st_uid != os.getuid() or not (
                stat.S_ISREG(child_metadata.st_mode)
                or stat.S_ISDIR(child_metadata.st_mode)
                or stat.S_ISLNK(child_metadata.st_mode)
            ):
                raise UpgradeTransactionError("Upgrade cleanup tree contains an unsafe entry")
    for directory in reversed(directories):
        directory.chmod(0o700)
    shutil.rmtree(target)
    return True


def cleanup_transaction_artifacts(transaction: Path, names: tuple[str, ...]) -> dict[str, Any]:
    removed: list[str] = []
    for name in names:
        if remove_transaction_owned_path(transaction / name, transaction=transaction):
            removed.append(name)
    retained = [
        name
        for name in ("replaced-components", "replaced-state", "replaced-docker-volume")
        if (transaction / name).exists() or (transaction / name).is_symlink()
    ]
    return {"status": "complete", "removed": removed, "retained_quarantine": retained}


def reap_finished_transaction_artifacts(backup_root: Path) -> None:
    for transaction in sorted(backup_root.iterdir()):
        if transaction.is_symlink() or not transaction.is_dir():
            continue
        ledger_file = transaction / "ledger.json"
        if not ledger_file.is_file() or ledger_file.is_symlink():
            continue
        ledger = load_ledger(transaction)
        status = ledger.get("status")
        if status == "committed":
            names = COMMIT_GENERATED_ROOTS
        elif status == "rolled_back":
            names = ROLLBACK_GENERATED_ROOTS
        else:
            continue
        ledger["cleanup"] = cleanup_transaction_artifacts(transaction, names)
        save_ledger(transaction, ledger)


def command_begin(args: argparse.Namespace) -> int:
    repo = lexical(args.repo_root)
    support = lexical(args.app_support_dir)
    config_file = contained(args.config_file, support, "canonical config")
    runtime_dir = contained(args.runtime_dir, support, "generated runtime")
    lock_file = contained(args.lock_file, repo, "component lock")
    validate_chain(repo)
    validate_chain(support)
    if repo.is_symlink() or not repo.is_dir() or not support.is_dir():
        raise UpgradeTransactionError("Upgrade roots are unsafe")
    if repo.lstat().st_uid != os.getuid() or support.lstat().st_uid != os.getuid():
        raise UpgradeTransactionError("Upgrade roots must be owned by the current user")
    pointer = support / ACTIVE_POINTER
    if pointer.exists() or pointer.is_symlink():
        raise UpgradeTransactionError("An unfinished upgrade transaction already requires recovery")

    repositories = [repo_record(repo, name="parent", expected_target=args.target_head or "")]
    if repositories[0]["protected_dirty"] and not args.allow_dirty_parent:
        raise UpgradeTransactionError("Parent tracked source changed before the upgrade checkpoint")
    repositories.extend(read_lock_repositories(repo, lock_file))
    storage_inventory, extra_surfaces = mongo_storage_inventory(support, runtime_dir)
    storage_inventory["checkpoint_status"] = "pending"
    storage_inventory["existed_before"] = None
    estimated_payload_bytes = sum(
        surface_logical_size(path, allow_symlinks=allow_symlinks)
        for _, path, allow_symlinks in checkpoint_surface_candidates(
            support,
            config_file,
            runtime_dir,
            extra_surfaces,
        )
    )
    if storage_inventory["backend"] == "docker_named_volume":
        docker = docker_ready()
        volume = storage_inventory["volume_name"]
        if docker_volume_exists(docker, volume):
            estimated_payload_bytes += docker_volume_logical_size(
                docker,
                volume,
                storage_inventory["image"],
            )
    ensure_checkpoint_capacity(support, estimated_payload_bytes)

    backup_root = ensure_private_directory(support / BACKUP_ROOT, boundary=support)
    reap_finished_transaction_artifacts(backup_root)
    transaction = backup_root / f"upgrade-{utc_stamp()}-{uuid.uuid4().hex}"
    transaction.mkdir(mode=0o700)
    try:
        runner = transaction / "transaction-runner.py"
        source_runner = lexical(Path(__file__))
        validate_chain(source_runner)
        source_runner_metadata = source_runner.lstat()
        if (
            not stat.S_ISREG(source_runner_metadata.st_mode)
            or source_runner_metadata.st_uid != os.getuid()
        ):
            raise UpgradeTransactionError("Upgrade transaction runner source is unsafe")
        shutil.copy2(source_runner, runner, follow_symlinks=False)
        runner.chmod(0o500)
        runner_sha256 = sha256_file(runner)
        ledger: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "transaction_path": str(transaction),
            "transaction_runner": str(runner),
            "transaction_runner_sha256": runner_sha256,
            "app_support_dir": str(support),
            "repo_root": str(repo),
            "config_file": str(config_file),
            "runtime_dir": str(runtime_dir),
            "lock_file": str(lock_file),
            "created_at": utc_stamp(),
            "status": "active",
            "stage": "transaction_registered",
            "was_running": args.was_running == "true",
            "repositories": repositories,
            "surfaces": [],
            "storage_inventory": {"mongodb": storage_inventory},
            "capacity_preflight": {
                "estimated_payload_bytes": estimated_payload_bytes,
                "free_reserve_bytes": CHECKPOINT_FREE_RESERVE_BYTES,
            },
            "checkpoints": [],
        }
        save_ledger(transaction, ledger)
        write_json_atomic(
            pointer,
            {"schema_version": SCHEMA_VERSION, "transaction_path": str(transaction)},
            boundary=support,
        )
    except Exception:
        shutil.rmtree(transaction, ignore_errors=True)
        if not any(backup_root.iterdir()):
            backup_root.rmdir()
        raise
    print(
        json.dumps(
            {
                "transaction_path": str(transaction),
                "transaction_runner": str(runner),
                "was_running": ledger["was_running"],
            },
            sort_keys=True,
        )
    )
    return 0


def command_snapshot_stopped_state(args: argparse.Namespace) -> int:
    transaction = lexical(args.transaction)
    ledger = load_ledger(transaction)
    if ledger["status"] != "active" or ledger["stage"] != "transaction_registered":
        raise UpgradeTransactionError("Stopped-state checkpoint is not allowed at this stage")
    support = Path(ledger["app_support_dir"])
    config_file = Path(ledger["config_file"])
    runtime_dir = Path(ledger["runtime_dir"])
    storage_inventory = ledger.get("storage_inventory", {}).get("mongodb")
    if not isinstance(storage_inventory, dict) or not storage_inventory.get("backend"):
        raise UpgradeTransactionError("Pre-stop MongoDB storage inventory is missing")
    extra_surfaces: list[tuple[str, Path]] = []
    if storage_inventory["backend"] == "app_support_bind":
        data_path = contained(Path(str(storage_inventory.get("path") or "")), support, "MongoDB data path")
        covered = any(
            data_path == root or root in data_path.parents
            for root in (support / "state" / "runtime", support / "state" / "mongo-data", support / "data")
        )
        if not covered:
            extra_surfaces.append(("explicit-mongo-data", data_path))
    candidates = checkpoint_surface_candidates(
        support,
        config_file,
        runtime_dir,
        extra_surfaces,
    )
    estimated_payload_bytes = sum(
        surface_logical_size(path, allow_symlinks=allow_symlinks)
        for _, path, allow_symlinks in candidates
    )
    docker: str | None = None
    if storage_inventory["backend"] == "docker_named_volume":
        docker = docker_ready()
        volume = storage_inventory["volume_name"]
        image = storage_inventory["image"]
        ensure_docker_volume_stopped(docker, volume)
        existed = docker_volume_exists(docker, volume)
        storage_inventory["existed_before"] = existed
        if existed:
            estimated_payload_bytes += docker_volume_logical_size(docker, volume, image)
    else:
        storage_inventory["existed_before"] = True
    storage_inventory["checkpoint_status"] = "pending"
    ledger["storage_inventory"] = {"mongodb": storage_inventory}
    ledger["capacity_checkpoint"] = {
        "estimated_payload_bytes": estimated_payload_bytes,
        "free_reserve_bytes": CHECKPOINT_FREE_RESERVE_BYTES,
    }
    # Persist the explicit pending/observed state before any checkpoint copy. A failed
    # copy or archive must never be interpreted as proof that live storage was absent.
    save_ledger(transaction, ledger)
    ensure_checkpoint_capacity(transaction, estimated_payload_bytes)

    surfaces = snapshot_surfaces(
        transaction,
        support,
        config_file,
        runtime_dir,
        extra_surfaces,
    )
    if storage_inventory["backend"] == "docker_named_volume":
        volume = storage_inventory["volume_name"]
        image = storage_inventory["image"]
        if storage_inventory["existed_before"]:
            assert docker is not None
            archive = transaction / "docker-checkpoint" / "mongodb-volume.tar"
            storage_inventory.update(docker_archive_volume(docker, volume, image, archive))
            storage_inventory["archive"] = str(archive)
            make_immutable(archive.parent)
    storage_inventory["checkpoint_status"] = "complete"
    ledger["surfaces"] = surfaces
    ledger["storage_inventory"] = {"mongodb": storage_inventory}
    ledger["stage"] = "stopped_checkpoint_complete"
    ledger["checkpoints"].append(
        {"stage": "stopped_checkpoint_complete", "recorded_at": utc_stamp(), "heads": {}}
    )
    save_ledger(transaction, ledger)
    print(json.dumps({"checkpointed": True}, sort_keys=True))
    return 0


def command_prepare_candidate(args: argparse.Namespace) -> int:
    transaction = lexical(args.transaction)
    ledger = load_ledger(transaction)
    if ledger["status"] != "active" or ledger["stage"] != "stopped_checkpoint_complete":
        raise UpgradeTransactionError("Upgrade transaction is not active")
    support = lexical(Path(ledger["app_support_dir"]))
    candidate = transaction / "candidate"
    if candidate.exists() or candidate.is_symlink():
        raise UpgradeTransactionError("Upgrade candidate already exists")
    candidate.mkdir(mode=0o700)
    config = candidate / "config.yaml"
    source_config = Path(ledger["config_file"])
    if not source_config.is_file() or source_config.is_symlink():
        raise UpgradeTransactionError("Canonical config is unavailable for candidate staging")
    shutil.copy2(source_config, config, follow_symlinks=False)
    config.chmod(0o600)
    runtime = candidate / "runtime"
    ledger["stage"] = "candidate_prepared"
    save_ledger(transaction, ledger)
    print(json.dumps({"config_file": str(config), "runtime_dir": str(runtime)}, sort_keys=True))
    return 0


def command_checkpoint(args: argparse.Namespace) -> int:
    transaction = lexical(args.transaction)
    ledger = load_ledger(transaction)
    if ledger["status"] != "active":
        raise UpgradeTransactionError("Upgrade transaction is not active")
    mongodb_storage = ledger.get("storage_inventory", {}).get("mongodb", {})
    if mongodb_storage.get("checkpoint_status") != "complete":
        raise UpgradeTransactionError("Stopped-state checkpoint is not complete")
    reconcile_component_records(ledger)
    observed: dict[str, str] = {}
    for record in ledger["repositories"]:
        repo = Path(record["path"])
        if not repo.exists() and not record.get("existed_before", True):
            observed[record["name"]] = "absent"
            continue
        head = git_text(repo, "rev-parse", "HEAD")
        if head not in record["observed_heads"]:
            record["observed_heads"].append(head)
        observed[record["name"]] = head
    ledger["stage"] = args.stage
    ledger["checkpoints"].append({"stage": args.stage, "recorded_at": utc_stamp(), "heads": observed})
    save_ledger(transaction, ledger)
    print(json.dumps({"stage": args.stage}, sort_keys=True))
    return 0


def replace_surface_from(
    source: Path,
    target: Path,
    manifest: dict[str, Any],
    transaction: Path,
    label: str,
    *,
    allow_symlinks: bool = False,
) -> None:
    failed_root = transaction / "replaced-state"
    failed_root.mkdir(mode=0o700, exist_ok=True)
    if target.exists() or target.is_symlink():
        validate_chain(target)
        if target.is_symlink():
            raise UpgradeTransactionError("Refusing to replace a symlinked mutable surface")
        os.replace(target, failed_root / f"{label}-{uuid.uuid4().hex}")
    if manifest["kind"] == "absent":
        return
    staging = target.parent / f".{target.name}.upgrade-{uuid.uuid4().hex}"
    try:
        copy_surface(source, staging, allow_symlinks=allow_symlinks)
        apply_manifest_modes(staging, manifest)
        os.replace(staging, target)
    finally:
        if staging.exists():
            if staging.is_dir():
                shutil.rmtree(staging)
            else:
                staging.unlink()
    if surface_manifest(target, allow_symlinks=allow_symlinks) != manifest:
        raise UpgradeTransactionError("Activated/restored surface did not match its verified manifest")


def command_activate_candidate(args: argparse.Namespace) -> int:
    transaction = lexical(args.transaction)
    ledger = load_ledger(transaction)
    if ledger["status"] != "active" or ledger["stage"] not in {
        "candidate_prepared",
        "source_pulled",
        "components_refreshed",
        "candidate_validated",
    }:
        raise UpgradeTransactionError("Upgrade candidate is not ready for activation")
    candidate = transaction / "candidate"
    candidate_config = candidate / "config.yaml"
    candidate_runtime = candidate / "runtime"
    if candidate_config.is_symlink() or not candidate_config.is_file():
        raise UpgradeTransactionError("Upgrade candidate config is missing or unsafe")
    if candidate_runtime.is_symlink() or not candidate_runtime.is_dir():
        raise UpgradeTransactionError("Upgrade candidate runtime is missing or unsafe")
    config_manifest = surface_manifest(candidate_config)
    runtime_manifest = surface_manifest(candidate_runtime)
    replace_surface_from(
        candidate_config,
        Path(ledger["config_file"]),
        config_manifest,
        transaction,
        "candidate-config",
    )
    replace_surface_from(
        candidate_runtime,
        Path(ledger["runtime_dir"]),
        runtime_manifest,
        transaction,
        "candidate-runtime",
    )
    ledger["stage"] = "candidate_activated"
    ledger["activated_manifests"] = {"config": config_manifest, "runtime": runtime_manifest}
    save_ledger(transaction, ledger)
    print(json.dumps({"activated": True}, sort_keys=True))
    return 0


def verify_repo_restore(record: dict[str, Any]) -> None:
    repo = Path(record["path"])
    if not record.get("existed_before", True):
        if not repo.exists() and not repo.is_symlink():
            return
        validate_chain(repo)
        contained(repo, Path(record["repo_root"]), "new managed component")
        metadata = repo.lstat()
        if repo.is_symlink() or metadata.st_uid != os.getuid() or not (
            stat.S_ISDIR(metadata.st_mode) or stat.S_ISREG(metadata.st_mode)
        ):
            raise UpgradeTransactionError("New managed component path is unsafe during rollback")
        return
    current = git_text(repo, "rev-parse", "HEAD")
    allowed = set(record.get("observed_heads", []))
    if record.get("expected_target"):
        allowed.add(record["expected_target"])
    if current not in allowed:
        raise UpgradeTransactionError(
            f"Rollback refused because {record['name']} moved to unrecognized local work"
        )
    if record.get("protected_dirty"):
        if current != record["old_head"]:
            raise UpgradeTransactionError("A protected dirty component moved during the upgrade")
        return
    if not tracked_clean(repo):
        raise UpgradeTransactionError(
            f"Rollback refused because {record['name']} has uncommitted tracked work"
        )


def restore_repo(record: dict[str, Any]) -> None:
    verify_repo_restore(record)
    if not record.get("existed_before", True):
        repo = Path(record["path"])
        if not repo.exists() and not repo.is_symlink():
            return
        transaction = lexical(Path(record["transaction_path"]))
        repo_root = lexical(Path(record["repo_root"]))
        contained(repo, repo_root, "new managed component")
        quarantine = transaction / "replaced-components"
        quarantine.mkdir(mode=0o700, exist_ok=True)
        os.replace(repo, quarantine / f"component-{uuid.uuid4().hex}")
        return
    if record.get("protected_dirty"):
        return
    repo = Path(record["path"])
    old = record["old_head"]
    current = git_text(repo, "rev-parse", "HEAD")
    old_ref = record.get("old_head_ref") or ""
    if current != old:
        patch = git(repo, "diff", "--binary", "--full-index", old, current).stdout
        if patch:
            git(repo, "apply", "--reverse", "--index", "--binary", input_bytes=patch)
        current_ref_result = git(repo, "symbolic-ref", "-q", "HEAD", check=False)
        current_ref = (
            current_ref_result.stdout.decode("utf-8").strip()
            if current_ref_result.returncode == 0
            else ""
        )
        if old_ref:
            old_ref_value = git_text(repo, "rev-parse", old_ref)
            if current_ref == old_ref:
                git(repo, "update-ref", old_ref, old, current)
            elif old_ref_value == old:
                git(repo, "symbolic-ref", "HEAD", old_ref)
            else:
                raise UpgradeTransactionError("Original source branch moved during rollback")
        else:
            git(repo, "update-ref", "--no-deref", "HEAD", old, current)
    elif old_ref:
        current_ref_result = git(repo, "symbolic-ref", "-q", "HEAD", check=False)
        if current_ref_result.returncode != 0:
            if git_text(repo, "rev-parse", old_ref) != old:
                raise UpgradeTransactionError("Original source branch moved during rollback")
            git(repo, "symbolic-ref", "HEAD", old_ref)
    if git_text(repo, "rev-parse", "HEAD") != old or not tracked_clean(repo):
        raise UpgradeTransactionError("Source rollback verification failed")


def verify_storage_restore_ready(storage: dict[str, Any]) -> None:
    if storage.get("backend") != "docker_named_volume":
        return
    if storage.get("checkpoint_status") != "complete" or not isinstance(
        storage.get("existed_before"), bool
    ):
        raise UpgradeTransactionError("Docker volume checkpoint state is incomplete")
    volume = validate_docker_name(str(storage.get("volume_name") or ""), "MongoDB volume name")
    image = validate_docker_image(str(storage.get("image") or ""))
    docker = docker_ready()
    ensure_docker_volume_stopped(docker, volume)
    if storage.get("existed_before"):
        archive = Path(str(storage.get("archive") or ""))
        expected_hash = str(storage.get("archive_sha256") or "")
        if not expected_hash or sha256_file(archive) != expected_hash:
            raise UpgradeTransactionError("Docker volume checkpoint integrity verification failed")
        if tar_manifest(archive) != storage.get("manifest"):
            raise UpgradeTransactionError("Docker volume checkpoint content verification failed")
        docker_command(docker, "image", "inspect", image)


def restore_docker_volume(transaction: Path, storage: dict[str, Any]) -> None:
    if storage.get("backend") != "docker_named_volume":
        return
    if storage.get("checkpoint_status") != "complete" or not isinstance(
        storage.get("existed_before"), bool
    ):
        raise UpgradeTransactionError("Docker volume checkpoint state is incomplete")
    docker = docker_ready()
    volume = validate_docker_name(str(storage["volume_name"]), "MongoDB volume name")
    image = validate_docker_image(str(storage["image"]))
    ensure_docker_volume_stopped(docker, volume)
    current_exists = docker_volume_exists(docker, volume)
    preserve_root = transaction / "replaced-docker-volume"
    if current_exists:
        docker_command(docker, "image", "inspect", image)
        preserved = preserve_root / f"mongodb-volume-{uuid.uuid4().hex}.tar"
        docker_archive_volume(docker, volume, image, preserved)
    if not storage.get("existed_before"):
        if current_exists:
            docker_command(docker, "volume", "rm", volume)
        return
    if not current_exists:
        docker_command(docker, "volume", "create", volume)
    archive = Path(storage["archive"])
    docker_command(
        docker,
        "run",
        "--rm",
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--entrypoint",
        "/bin/sh",
        "-v",
        f"{volume}:/source",
        "-v",
        f"{archive.parent}:/checkpoint:ro",
        image,
        "-c",
        (
            "find /source -mindepth 1 -depth -delete && "
            f"tar -C /source -xf /checkpoint/{archive.name}"
        ),
    )
    verification_archive = transaction / "restore-verification" / "mongodb-volume.tar"
    verification = docker_archive_volume(docker, volume, image, verification_archive)
    if verification["manifest"] != storage["manifest"]:
        raise UpgradeTransactionError("Restored Docker MongoDB volume did not match its checkpoint")


def command_rollback(args: argparse.Namespace) -> int:
    transaction = lexical(args.transaction)
    ledger = load_ledger(transaction)
    if ledger["status"] == "rolled_back":
        print(json.dumps({"rolled_back": True, "was_running": ledger["was_running"]}, sort_keys=True))
        return 0
    if ledger["status"] not in {"active", "rolling_back"}:
        raise UpgradeTransactionError("Upgrade transaction cannot be rolled back")
    mongodb_storage = ledger.get("storage_inventory", {}).get("mongodb", {})
    if (
        ledger.get("stage") == "transaction_registered"
        or mongodb_storage.get("checkpoint_status") != "complete"
    ):
        ledger["status"] = "rolled_back"
        ledger["stage"] = "rolled_back_without_checkpoint"
        ledger["rolled_back_at"] = utc_stamp()
        ledger["rollback_verification"] = {
            "source_restored": "not_mutated",
            "state_restored": "not_mutated",
            "docker_mongodb_restored": "not_touched",
            "stopped_file_checkpoint_restored": "not_available",
            "semantic_data_migration_reversal": "not_applicable",
        }
        save_ledger(transaction, ledger)
        support = Path(ledger["app_support_dir"])
        pointer = support / ACTIVE_POINTER
        if pointer.exists() or pointer.is_symlink():
            validate_chain(pointer, owned_from=support)
            pointer.unlink()
        try:
            ledger["cleanup"] = cleanup_transaction_artifacts(
                transaction, ROLLBACK_GENERATED_ROOTS
            )
        except UpgradeTransactionError as error:
            ledger["cleanup"] = {"status": "cleanup_required", "error": str(error)}
        save_ledger(transaction, ledger)
        print(
            json.dumps(
                {"rolled_back": True, "was_running": ledger["was_running"], "live_state_touched": False},
                sort_keys=True,
            )
        )
        return 0
    # Validate every source checkout before changing either source or user state.
    for record in ledger["repositories"]:
        record["transaction_path"] = str(transaction)
        record["repo_root"] = ledger["repo_root"]
        verify_repo_restore(record)
    verify_storage_restore_ready(mongodb_storage)
    ledger["status"] = "rolling_back"
    ledger["stage"] = "rolling_back"
    save_ledger(transaction, ledger)
    for record in reversed(ledger["repositories"]):
        restore_repo(record)
    restore_docker_volume(transaction, mongodb_storage)
    for surface in ledger["surfaces"]:
        replace_surface_from(
            Path(surface["backup"]),
            Path(surface["path"]),
            surface["manifest"],
            transaction,
            f"rollback-{surface['label']}",
            allow_symlinks=bool(surface.get("allow_symlinks", False)),
        )
    ledger["status"] = "rolled_back"
    ledger["stage"] = "rolled_back"
    ledger["rolled_back_at"] = utc_stamp()
    ledger["rollback_verification"] = {
        "source_restored": True,
        "state_restored": True,
        "docker_mongodb_restored": mongodb_storage.get("backend") == "docker_named_volume",
        "stopped_file_checkpoint_restored": True,
        "semantic_data_migration_reversal": "not_proven",
    }
    save_ledger(transaction, ledger)
    support = Path(ledger["app_support_dir"])
    pointer = support / ACTIVE_POINTER
    if pointer.exists() or pointer.is_symlink():
        validate_chain(pointer, owned_from=support)
        pointer.unlink()
    try:
        ledger["cleanup"] = cleanup_transaction_artifacts(
            transaction, ROLLBACK_GENERATED_ROOTS
        )
    except UpgradeTransactionError as error:
        ledger["cleanup"] = {"status": "cleanup_required", "error": str(error)}
    save_ledger(transaction, ledger)
    print(json.dumps({"rolled_back": True, "was_running": ledger["was_running"]}, sort_keys=True))
    return 0


def command_commit(args: argparse.Namespace) -> int:
    transaction = lexical(args.transaction)
    ledger = load_ledger(transaction)
    if ledger["status"] != "active":
        raise UpgradeTransactionError("Upgrade transaction is not active")
    ledger["status"] = "committed"
    ledger["stage"] = "committed"
    ledger["committed_at"] = utc_stamp()
    save_ledger(transaction, ledger)
    support = Path(ledger["app_support_dir"])
    pointer = support / ACTIVE_POINTER
    if pointer.exists() or pointer.is_symlink():
        validate_chain(pointer, owned_from=support)
        pointer.unlink()
    try:
        ledger["cleanup"] = cleanup_transaction_artifacts(
            transaction, COMMIT_GENERATED_ROOTS
        )
    except UpgradeTransactionError as error:
        ledger["cleanup"] = {"status": "cleanup_required", "error": str(error)}
    save_ledger(transaction, ledger)
    print(json.dumps({"committed": True, "cleanup": ledger["cleanup"]}, sort_keys=True))
    return 0


def command_active(args: argparse.Namespace) -> int:
    support = lexical(args.app_support_dir)
    pointer = support / ACTIVE_POINTER
    if not pointer.exists() and not pointer.is_symlink():
        return 1
    validate_chain(pointer, owned_from=support)
    if pointer.is_symlink() or not pointer.is_file():
        raise UpgradeTransactionError("Upgrade transaction pointer is unsafe")
    try:
        payload = json.loads(pointer.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise UpgradeTransactionError("Upgrade transaction pointer is unreadable") from error
    transaction = lexical(Path(payload.get("transaction_path", "")))
    ledger = load_ledger(transaction)
    print(
        json.dumps(
            {
                "transaction_path": str(transaction),
                "transaction_runner": str(ledger.get("transaction_runner") or ""),
                "stage": ledger["stage"],
                "status": ledger["status"],
                "was_running": ledger["was_running"],
            },
            sort_keys=True,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    begin = commands.add_parser("begin")
    begin.add_argument("--repo-root", required=True, type=Path)
    begin.add_argument("--app-support-dir", required=True, type=Path)
    begin.add_argument("--config-file", required=True, type=Path)
    begin.add_argument("--runtime-dir", required=True, type=Path)
    begin.add_argument("--lock-file", required=True, type=Path)
    begin.add_argument("--target-head")
    begin.add_argument("--allow-dirty-parent", action="store_true")
    begin.add_argument("--was-running", choices=("true", "false"), required=True)
    begin.set_defaults(handler=command_begin)

    for name, handler in (
        ("snapshot-stopped-state", command_snapshot_stopped_state),
        ("prepare-candidate", command_prepare_candidate),
        ("activate-candidate", command_activate_candidate),
        ("rollback", command_rollback),
        ("commit", command_commit),
    ):
        command = commands.add_parser(name)
        command.add_argument("--transaction", required=True, type=Path)
        command.set_defaults(handler=handler)

    checkpoint = commands.add_parser("checkpoint")
    checkpoint.add_argument("--transaction", required=True, type=Path)
    checkpoint.add_argument("--stage", required=True)
    checkpoint.set_defaults(handler=command_checkpoint)

    active = commands.add_parser("active")
    active.add_argument("--app-support-dir", required=True, type=Path)
    active.set_defaults(handler=command_active)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.handler(args)
    except (OSError, UpgradeTransactionError, ValueError) as error:
        raise SystemExit(f"Upgrade transaction failed closed: {error}") from error


if __name__ == "__main__":
    raise SystemExit(main())

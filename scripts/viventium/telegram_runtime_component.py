#!/usr/bin/env python3
"""Build and resolve the private, code-only Telegram runtime component."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import grp
import hashlib
import json
import os
from pathlib import Path
import platform
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
from typing import Any, Iterable, Iterator


SCHEMA_VERSION = 2
COMPONENT_NAME = "telegram-viventium"
MANIFEST_NAME = "component-manifest.json"
DEPENDENCY_MARKER = ".viventium-dependency.json"
DEPENDENCY_MANIFEST = ".viventium-dependency-manifest.json"
DEPENDENCY_BUILD_ENVIRONMENT = frozenset(
    {
        "ARCHFLAGS",
        "AR",
        "CC",
        "CFLAGS",
        "CMAKE_ARGS",
        "CMAKE_BUILD_PARALLEL_LEVEL",
        "CMAKE_GENERATOR",
        "CMAKE_PREFIX_PATH",
        "CPATH",
        "CPPFLAGS",
        "CXX",
        "CXXFLAGS",
        "DEVELOPER_DIR",
        "LANG",
        "LDFLAGS",
        "LIBRARY_PATH",
        "MACOSX_DEPLOYMENT_TARGET",
        "PATH",
        "PKG_CONFIG_PATH",
        "PYTHONIOENCODING",
        "PYTHONUTF8",
        "REQUESTS_CA_BUNDLE",
        "SDKROOT",
        "SSL_CERT_DIR",
        "SSL_CERT_FILE",
        "SYSTEM_VERSION_COMPAT",
        "TEMP",
        "TMP",
        "TMPDIR",
        "UV_CACHE_DIR",
        "UV_CONCURRENT_BUILDS",
        "UV_CONCURRENT_DOWNLOADS",
        "UV_HTTP_TIMEOUT",
        "UV_LINK_MODE",
        "UV_NO_CONFIG",
        "UV_NO_PROGRESS",
        "UV_OFFLINE",
    }
)
RECOVERY_RECEIPT = Path("state/continuity/telegram-recovery-active.json")
RECOVERY_GENERATION = Path(
    "state/continuity/telegram-recovery-generation.json"
)
RECOVERY_KIND = "viventium-telegram-runtime-recovery"
RECOVERY_GENERATION_KIND = "viventium-telegram-recovery-generation"
EXCLUDED_DIRECTORIES = frozenset(
    {
        ".git",
        ".github",
        ".pytest_cache",
        ".venv",
        "__pycache__",
        "tests",
        "user_configs",
    }
)
ALLOWED_SUFFIXES = frozenset(
    {".cfg", ".ini", ".json", ".lock", ".md", ".py", ".toml", ".txt", ".yaml", ".yml"}
)
ALLOWED_NAMES = frozenset({"LICENSE"})
VOICE_SUPPORT_FILES = (
    "local_chatterbox_config.py",
    "mlx_chatterbox_tts.py",
    "requirements.mlx_audio_darwin.txt",
    "sse.py",
)
REQUIRED_COMPONENT_FILES = (
    "bin/viventium",
    "scripts/viventium/telegram_poller_handoff.py",
    "scripts/viventium/telegram_runtime_component.py",
    "viventium_v0_4/viventium-librechat-start.sh",
    "viventium_v0_4/telegram-viventium/TelegramVivBot/bot.py",
    "viventium_v0_4/telegram-viventium/TelegramVivBot/config.py",
    "viventium_v0_4/telegram-viventium/TelegramVivBot/pyproject.toml",
    "viventium_v0_4/telegram-viventium/TelegramVivBot/uv.lock",
    "viventium_v0_4/telegram-viventium/TelegramVivBot/utils/singleton.py",
    "viventium_v0_4/shared/no_response.py",
    "viventium_v0_4/shared/voice/tts_provider_capabilities.json",
    "viventium_v0_4/shared/voice/cartesia_sonic3_capabilities.json",
    "viventium_v0_4/shared/voice/xai_tts_capabilities.json",
    "viventium_v0_4/voice-gateway/local_chatterbox_config.py",
    "viventium_v0_4/voice-gateway/mlx_chatterbox_tts.py",
    "viventium_v0_4/voice-gateway/requirements.mlx_audio_darwin.txt",
    "viventium_v0_4/voice-gateway/sse.py",
)


class ComponentError(RuntimeError):
    pass


def _lexical(path: Path) -> Path:
    return Path(os.path.abspath(os.path.expanduser(str(path))))


def _contained(path: Path, root: Path, label: str) -> Path:
    candidate = _lexical(path)
    boundary = _lexical(root)
    try:
        candidate.relative_to(boundary)
    except ValueError as error:
        raise ComponentError(f"{label} is outside App Support") from error
    return candidate


def _validate_existing_real_chain(path: Path, label: str) -> None:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current = current / part
        if not os.path.lexists(current):
            break
        metadata = os.lstat(current)
        if stat.S_ISLNK(metadata.st_mode):
            raise ComponentError(f"{label} contains a symlink: {current}")
        if current != path and not stat.S_ISDIR(metadata.st_mode):
            raise ComponentError(f"{label} has a non-directory ancestor: {current}")


def _ensure_private_directory(path: Path, *, root: Path | None = None) -> None:
    if root is not None:
        _contained(path, root, "Telegram runtime component directory")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    _validate_existing_real_chain(path, "Telegram runtime component directory")
    metadata = path.lstat()
    if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.getuid():
        raise ComponentError("Telegram runtime component directory is not owner-controlled")
    path.chmod(0o700)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ComponentError(f"Telegram runtime source is not a regular file: {path}")
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    finally:
        os.close(descriptor)
    return digest.hexdigest()


def _source_file_allowed(path: Path) -> bool:
    return path.name in ALLOWED_NAMES or path.suffix.lower() in ALLOWED_SUFFIXES


def _git_tracked_paths(root: Path) -> set[Path] | None:
    completed = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--cached", "-z", "--", "."],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if completed.returncode != 0:
        return None
    return {
        _lexical(root / os.fsdecode(relative))
        for relative in completed.stdout.split(b"\0")
        if relative
    }


def _walk_selected_tree(root: Path, destination_prefix: Path) -> Iterator[tuple[Path, Path]]:
    if root.is_symlink() or not root.is_dir():
        raise ComponentError(f"Telegram runtime source directory is missing or symlinked: {root}")
    tracked_paths = _git_tracked_paths(root)
    for directory, directory_names, file_names in os.walk(root, topdown=True, followlinks=False):
        directory_path = Path(directory)
        kept_directories: list[str] = []
        for name in sorted(directory_names):
            candidate = directory_path / name
            if name in EXCLUDED_DIRECTORIES:
                continue
            if candidate.is_symlink():
                raise ComponentError(f"Telegram runtime source contains a symlink: {candidate}")
            kept_directories.append(name)
        directory_names[:] = kept_directories
        for name in sorted(file_names):
            candidate = directory_path / name
            if candidate.is_symlink():
                raise ComponentError(f"Telegram runtime source contains a symlink: {candidate}")
            if not _source_file_allowed(candidate):
                continue
            if tracked_paths is not None and _lexical(candidate) not in tracked_paths:
                continue
            relative = candidate.relative_to(root)
            yield candidate, destination_prefix / relative


def _selected_sources(repo_root: Path) -> list[tuple[Path, Path]]:
    root = _lexical(repo_root)
    _validate_existing_real_chain(root, "Telegram runtime repository")
    if root.is_symlink() or not root.is_dir():
        raise ComponentError("Telegram runtime repository is missing or symlinked")
    v0_root = root / "viventium_v0_4"
    telegram = v0_root / "telegram-viventium" / "TelegramVivBot"
    shared = v0_root / "shared"
    voice = v0_root / "voice-gateway"
    voice_tracked_paths = _git_tracked_paths(voice)
    selected = [
        *_walk_selected_tree(
            telegram,
            Path("viventium_v0_4") / "telegram-viventium" / "TelegramVivBot",
        ),
        *_walk_selected_tree(shared, Path("viventium_v0_4") / "shared"),
    ]
    controller_root = _lexical(Path(__file__).resolve().parents[2])
    for relative in (
        Path("bin") / "viventium",
        Path("scripts") / "viventium" / "telegram_poller_handoff.py",
        Path("scripts") / "viventium" / "telegram_runtime_component.py",
        Path("viventium_v0_4") / "viventium-librechat-start.sh",
    ):
        candidate = controller_root / relative
        if candidate.is_symlink() or not candidate.is_file():
            raise ComponentError(
                f"Telegram recovery controller source is missing or unsafe: {candidate}"
            )
        selected.append((candidate, relative))
    for name in VOICE_SUPPORT_FILES:
        candidate = voice / name
        if candidate.is_symlink():
            raise ComponentError(f"Telegram voice support source contains a symlink: {candidate}")
        if not candidate.is_file():
            raise ComponentError(f"Telegram voice support source is missing: {candidate}")
        if voice_tracked_paths is not None and _lexical(candidate) not in voice_tracked_paths:
            raise ComponentError(
                f"Telegram voice support source is not tracked public code: {candidate}"
            )
        selected.append(
            (candidate, Path("viventium_v0_4") / "voice-gateway" / name)
        )
    selected.sort(key=lambda item: item[1].as_posix())
    destinations = [destination.as_posix() for _, destination in selected]
    if len(destinations) != len(set(destinations)):
        raise ComponentError("Telegram runtime component contains duplicate destination paths")
    missing = sorted(set(REQUIRED_COMPONENT_FILES) - set(destinations))
    if missing:
        raise ComponentError(
            "Telegram runtime component is missing required public code: "
            + ", ".join(missing)
        )
    return selected


def _source_manifest(selected: Iterable[tuple[Path, Path]]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    digest = hashlib.sha256()
    for source, destination in selected:
        relative = destination.as_posix()
        file_hash = _sha256(source)
        source_metadata = source.stat(follow_symlinks=False)
        size = source_metadata.st_size
        mode = 0o700 if stat.S_IMODE(source_metadata.st_mode) & 0o111 else 0o600
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_hash.encode("ascii"))
        digest.update(b"\0")
        digest.update(f"{mode:o}".encode("ascii"))
        digest.update(b"\0")
        rows.append(
            {
                "path": relative,
                "sha256": file_hash,
                "size": size,
                "mode": mode,
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "component": COMPONENT_NAME,
        "code_digest": digest.hexdigest(),
        "files": rows,
    }


def _verify_code_root(code_root: Path, expected: dict[str, Any]) -> None:
    try:
        metadata = code_root.lstat()
    except FileNotFoundError as error:
        raise ComponentError("Telegram runtime component is missing") from error
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) != 0o700
    ):
        raise ComponentError("existing Telegram runtime component failed integrity verification")
    manifest_path = code_root / MANIFEST_NAME
    try:
        manifest_bytes = _read_private_component_file(
            manifest_path,
            expected_mode=0o600,
        )
        manifest = json.loads(manifest_bytes)
    except (OSError, ValueError) as error:
        raise ComponentError(
            "existing Telegram runtime component failed integrity verification"
        ) from error
    if manifest != expected:
        raise ComponentError(
            "existing Telegram runtime component failed integrity verification"
        )
    expected_paths = {str(item["path"]) for item in expected["files"]}
    actual_paths: set[str] = set()
    for directory, directory_names, file_names in os.walk(
        code_root, topdown=True, followlinks=False
    ):
        directory_path = Path(directory)
        directory_metadata = directory_path.lstat()
        if (
            stat.S_ISLNK(directory_metadata.st_mode)
            or not stat.S_ISDIR(directory_metadata.st_mode)
            or directory_metadata.st_uid != os.getuid()
            or stat.S_IMODE(directory_metadata.st_mode) != 0o700
        ):
            raise ComponentError(
                "existing Telegram runtime component failed integrity verification"
            )
        for name in directory_names:
            if (directory_path / name).is_symlink():
                raise ComponentError(
                    "existing Telegram runtime component failed integrity verification"
                )
        for name in file_names:
            candidate = directory_path / name
            if candidate == manifest_path:
                continue
            if candidate.is_symlink() or not candidate.is_file():
                raise ComponentError(
                    "existing Telegram runtime component failed integrity verification"
                )
            actual_paths.add(candidate.relative_to(code_root).as_posix())
    if actual_paths != expected_paths:
        raise ComponentError(
            "existing Telegram runtime component failed integrity verification"
        )
    for item in expected["files"]:
        candidate = code_root / str(item["path"])
        metadata = candidate.lstat()
        if (
            stat.S_ISLNK(metadata.st_mode)
            or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or metadata.st_nlink != 1
            or stat.S_IMODE(metadata.st_mode) != int(item["mode"])
            or metadata.st_size != int(item["size"])
            or _sha256(candidate) != str(item["sha256"])
        ):
            raise ComponentError(
                "existing Telegram runtime component failed integrity verification"
            )


def _read_private_component_file(path: Path, *, expected_mode: int) -> bytes:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or metadata.st_nlink != 1
            or stat.S_IMODE(metadata.st_mode) != expected_mode
        ):
            raise ComponentError(
                "existing Telegram runtime component failed integrity verification"
            )
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            return handle.read()
    finally:
        os.close(descriptor)


def _write_json_atomic(path: Path, payload: dict[str, Any], *, mode: int = 0o600) -> None:
    _ensure_private_directory(path.parent)
    if path.is_symlink():
        raise ComponentError(f"Refusing symlinked Telegram runtime file: {path}")
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        path.chmod(mode)
        descriptor = os.open(
            path.parent,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
        )
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def _component_lock(store_root: Path):
    _ensure_private_directory(store_root)
    lock_path = store_root / ".prepare.lock"
    if lock_path.is_symlink():
        raise ComponentError("Telegram runtime component lock is a symlink")
    descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or stat.S_IMODE(metadata.st_mode) & 0o077
        ):
            raise ComponentError("Telegram runtime component lock is unsafe")
        os.fchmod(descriptor, 0o600)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        os.close(descriptor)


def _install_code(
    store_root: Path,
    selected: list[tuple[Path, Path]],
    manifest: dict[str, Any],
) -> tuple[Path, bool]:
    code_parent = store_root / "code"
    _ensure_private_directory(code_parent)
    code_root = code_parent / str(manifest["code_digest"])
    if code_root.exists() or code_root.is_symlink():
        _verify_code_root(code_root, manifest)
        return code_root, True
    stage = Path(tempfile.mkdtemp(prefix=".code-stage.", dir=code_parent))
    committed = False
    try:
        for source, relative in selected:
            destination = stage / relative
            destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            shutil.copy2(source, destination, follow_symlinks=False)
            item = next(
                row for row in manifest["files"] if row["path"] == relative.as_posix()
            )
            destination.chmod(int(item["mode"]))
        for directory, directory_names, _ in os.walk(
            stage,
            topdown=False,
            followlinks=False,
        ):
            for name in directory_names:
                (Path(directory) / name).chmod(0o700)
            Path(directory).chmod(0o700)
        _write_json_atomic(stage / MANIFEST_NAME, manifest)
        _verify_code_root(stage, manifest)
        try:
            os.rename(stage, code_root)
            committed = True
        except FileExistsError:
            _verify_code_root(code_root, manifest)
            return code_root, True
        return code_root, False
    finally:
        if not committed and stage.exists():
            shutil.rmtree(stage)


def _dependency_digest(code_root: Path) -> str:
    bot_root = (
        code_root
        / "viventium_v0_4"
        / "telegram-viventium"
        / "TelegramVivBot"
    )
    digest = hashlib.sha256()
    digest.update(f"component-schema:{SCHEMA_VERSION}".encode("ascii"))
    digest.update(b"\0")
    for name in ("pyproject.toml", "uv.lock"):
        candidate = bot_root / name
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(candidate.read_bytes())
        digest.update(b"\0")
    optional_requirements = (
        code_root
        / "viventium_v0_4"
        / "voice-gateway"
        / "requirements.mlx_audio_darwin.txt"
    )
    digest.update(b"requirements.mlx_audio_darwin.txt\0")
    digest.update(optional_requirements.read_bytes())
    digest.update(b"\0")
    runtime_tag = (
        f"{sys.implementation.name}:"
        f"{sys.version_info.major}.{sys.version_info.minor}:"
        f"{sys.platform}:{platform.machine()}"
    )
    digest.update(runtime_tag.encode("utf-8"))
    digest.update(b"\0")
    return digest.hexdigest()


def _verify_dependency_root(root: Path, dependency_digest: str) -> Path:
    marker_path = root / DEPENDENCY_MARKER
    manifest_path = root / DEPENDENCY_MANIFEST
    python = root / "bin" / "python"
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ComponentError(
            "existing Telegram dependency environment failed integrity verification"
        ) from error
    expected_manifest = _dependency_environment_manifest(root)
    if (
        root.is_symlink()
        or not root.is_dir()
        or root.stat().st_uid != os.getuid()
        or manifest != expected_manifest
        or marker != {
            "schema_version": SCHEMA_VERSION,
            "component": COMPONENT_NAME,
            "dependency_digest": dependency_digest,
            "environment_digest": expected_manifest["environment_digest"],
        }
        or not python.is_file()
        or not os.access(python, os.X_OK)
    ):
        raise ComponentError(
            "existing Telegram dependency environment failed integrity verification"
        )
    return python


def _external_python_target_is_trusted(
    *,
    candidate: Path,
    root: Path,
    resolved_target: Path,
    target_metadata: Any,
) -> bool:
    mode = stat.S_IMODE(target_metadata.st_mode)
    # The official macOS CPython package changes its framework to root:admin
    # 0775 after installation; root:wheel 0775 is also a standard privileged
    # layout. Every other group-writable or world-writable external interpreter
    # remains rejected.
    trusted_root_group_writable = False
    if target_metadata.st_uid == 0 and bool(mode & 0o020):
        trusted_group_ids = {0}
        if platform.system() == "Darwin":
            try:
                trusted_group_ids.add(grp.getgrnam("admin").gr_gid)
            except KeyError:
                pass
        trusted_root_group_writable = target_metadata.st_gid in trusted_group_ids
    return bool(
        candidate.parent.relative_to(root) == Path("bin")
        and candidate.name.startswith("python")
        and stat.S_ISREG(target_metadata.st_mode)
        and target_metadata.st_uid in {0, os.getuid()}
        and not (mode & 0o002)
        and (not (mode & 0o020) or trusted_root_group_writable)
        and os.access(resolved_target, os.X_OK)
    )


def _dependency_environment_manifest(root: Path) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    digest = hashlib.sha256()
    excluded = {DEPENDENCY_MARKER, DEPENDENCY_MANIFEST}
    for directory, directory_names, file_names in os.walk(
        root, topdown=True, followlinks=False
    ):
        directory_path = Path(directory)
        kept_directories: list[str] = []
        for name in sorted(directory_names):
            candidate = directory_path / name
            relative = candidate.relative_to(root).as_posix()
            metadata = candidate.lstat()
            if stat.S_ISLNK(metadata.st_mode):
                target = os.readlink(candidate)
                row = {"path": relative, "kind": "symlink", "target": target}
                resolved_target = candidate.resolve(strict=True)
                try:
                    resolved_target.relative_to(root)
                except ValueError:
                    target_metadata = resolved_target.stat()
                    if not _external_python_target_is_trusted(
                        candidate=candidate,
                        root=root,
                        resolved_target=resolved_target,
                        target_metadata=target_metadata,
                    ):
                        raise ComponentError(
                            "Telegram dependency environment has an unsafe external symlink"
                        )
                    row["resolved_target_sha256"] = _sha256(resolved_target)
                    row["resolved_target_mode"] = stat.S_IMODE(
                        target_metadata.st_mode
                    )
                entries.append(row)
                digest.update(json.dumps(row, sort_keys=True).encode("utf-8"))
                digest.update(b"\0")
                continue
            if not stat.S_ISDIR(metadata.st_mode):
                raise ComponentError(
                    "Telegram dependency environment contains an unsafe directory entry"
                )
            if stat.S_IMODE(metadata.st_mode) & 0o222:
                raise ComponentError(
                    "Telegram dependency environment is not sealed read-only"
                )
            kept_directories.append(name)
        directory_names[:] = kept_directories
        for name in sorted(file_names):
            if name in excluded and directory_path == root:
                continue
            candidate = directory_path / name
            relative = candidate.relative_to(root).as_posix()
            metadata = candidate.lstat()
            if stat.S_ISLNK(metadata.st_mode):
                row = {
                    "path": relative,
                    "kind": "symlink",
                    "target": os.readlink(candidate),
                }
                resolved_target = candidate.resolve(strict=True)
                try:
                    resolved_target.relative_to(root)
                except ValueError:
                    target_metadata = resolved_target.stat()
                    if not _external_python_target_is_trusted(
                        candidate=candidate,
                        root=root,
                        resolved_target=resolved_target,
                        target_metadata=target_metadata,
                    ):
                        raise ComponentError(
                            "Telegram dependency environment has an unsafe external symlink"
                        )
                    row["resolved_target_sha256"] = _sha256(resolved_target)
                    row["resolved_target_mode"] = stat.S_IMODE(
                        target_metadata.st_mode
                    )
            elif stat.S_ISREG(metadata.st_mode):
                if stat.S_IMODE(metadata.st_mode) & 0o222:
                    raise ComponentError(
                        "Telegram dependency environment is not sealed read-only"
                    )
                row = {
                    "path": relative,
                    "kind": "file",
                    "size": metadata.st_size,
                    "sha256": _sha256(candidate),
                }
            else:
                raise ComponentError(
                    "Telegram dependency environment contains an unsafe file entry"
                )
            entries.append(row)
            digest.update(json.dumps(row, sort_keys=True).encode("utf-8"))
            digest.update(b"\0")
    return {
        "schema_version": SCHEMA_VERSION,
        "component": COMPONENT_NAME,
        "environment_digest": digest.hexdigest(),
        "entries": entries,
    }


def _seal_dependency_root(root: Path) -> None:
    for directory, directory_names, file_names in os.walk(
        root, topdown=False, followlinks=False
    ):
        directory_path = Path(directory)
        for name in file_names:
            candidate = directory_path / name
            metadata = candidate.lstat()
            if stat.S_ISLNK(metadata.st_mode):
                continue
            executable = bool(stat.S_IMODE(metadata.st_mode) & 0o111)
            candidate.chmod(0o555 if executable else 0o444)
        for name in directory_names:
            candidate = directory_path / name
            if not candidate.is_symlink():
                candidate.chmod(0o555)
        directory_path.chmod(0o555)


def _dependency_sync_environment(base: dict[str, str]) -> dict[str, str]:
    # pywhispercpp 1.3.3 forwards every inherited environment variable to
    # CMake as a command-line definition. Keep package builds independent from
    # owner paths and prevent unrelated application credentials reaching the
    # build process or its diagnostics.
    environment = {
        name: value
        for name, value in base.items()
        if name in DEPENDENCY_BUILD_ENVIRONMENT or name.startswith("LC_")
    }
    if (
        platform.system() == "Darwin"
        and platform.machine().strip().lower() in {"x86_64", "amd64"}
    ):
        # pywhispercpp publishes no macOS Intel wheel. Its 1.3.3 source build supports
        # NO_REPAIR=1 specifically to bypass a wheel-repair StopIteration after a
        # successful native compile.
        environment["NO_REPAIR"] = "1"
    return environment


def _remove_dependency_stage(stage: Path) -> None:
    if not os.path.lexists(stage):
        return
    if stage.is_symlink():
        stage.unlink()
        return
    for directory, directory_names, file_names in os.walk(
        stage, topdown=False, followlinks=False
    ):
        directory_path = Path(directory)
        for name in file_names:
            candidate = directory_path / name
            if not candidate.is_symlink():
                candidate.chmod(0o600)
        for name in directory_names:
            candidate = directory_path / name
            if not candidate.is_symlink():
                candidate.chmod(0o700)
        directory_path.chmod(0o700)
    shutil.rmtree(stage)


def _verify_dependency_runtime(python: Path) -> None:
    completed = subprocess.run(
        [
            str(python),
            "-c",
            (
                "import importlib.util;"
                "spec=importlib.util.find_spec('pywhispercpp');"
                "exec('from pywhispercpp.model import Model') if spec else None"
            ),
        ],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if completed.returncode != 0:
        raise ComponentError(
            "Telegram native transcription dependency validation failed: "
            + "\n".join(completed.stdout.splitlines()[-12:])
        )


def _sync_dependencies(
    store_root: Path,
    code_root: Path,
    dependency_digest: str,
) -> tuple[Path, bool]:
    venv_parent = store_root / "venv"
    _ensure_private_directory(venv_parent)
    venv_root = venv_parent / dependency_digest
    if venv_root.exists() or venv_root.is_symlink():
        return _verify_dependency_root(venv_root, dependency_digest), True
    stage = venv_parent / f".venv-stage.{secrets.token_hex(8)}"
    bot_root = (
        code_root
        / "viventium_v0_4"
        / "telegram-viventium"
        / "TelegramVivBot"
    )
    environment = _dependency_sync_environment(os.environ)
    environment["UV_PROJECT_ENVIRONMENT"] = str(stage)
    try:
        completed = subprocess.run(
            ["uv", "sync", "--frozen", "--no-install-project"],
            cwd=bot_root,
            env=environment,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if completed.returncode != 0:
            raise ComponentError(
                "Telegram runtime dependency sync failed: "
                + "\n".join(completed.stdout.splitlines()[-12:])
            )
        optional_requirements = (
            code_root
            / "viventium_v0_4"
            / "voice-gateway"
            / "requirements.mlx_audio_darwin.txt"
        )
        if platform.system() == "Darwin" and platform.machine().lower() in {
            "arm64",
            "aarch64",
        }:
            completed = subprocess.run(
                [
                    "uv",
                    "pip",
                    "install",
                    "--python",
                    str(stage / "bin" / "python"),
                    "--prerelease=allow",
                    "--requirement",
                    str(optional_requirements),
                ],
                cwd=bot_root,
                env=environment,
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            if completed.returncode != 0:
                raise ComponentError(
                    "Telegram optional voice dependency sync failed: "
                    + "\n".join(completed.stdout.splitlines()[-12:])
                )
        _verify_dependency_runtime(stage / "bin" / "python")
        _seal_dependency_root(stage)
        environment_manifest = _dependency_environment_manifest(stage)
        stage.chmod(0o755)
        _write_json_atomic(stage / DEPENDENCY_MANIFEST, environment_manifest)
        marker = {
            "schema_version": SCHEMA_VERSION,
            "component": COMPONENT_NAME,
            "dependency_digest": dependency_digest,
            "environment_digest": environment_manifest["environment_digest"],
        }
        _write_json_atomic(stage / DEPENDENCY_MARKER, marker)
        _seal_dependency_root(stage)
        try:
            os.rename(stage, venv_root)
        except FileExistsError:
            return _verify_dependency_root(venv_root, dependency_digest), True
        return _verify_dependency_root(venv_root, dependency_digest), False
    finally:
        _remove_dependency_stage(stage)


def _selection_payload(
    *,
    app_support: Path,
    code_root: Path,
    manifest: dict[str, Any],
    dependency_digest: str,
) -> dict[str, Any]:
    venv_root = (
        app_support
        / "runtime-components"
        / COMPONENT_NAME
        / "venv"
        / dependency_digest
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "component": COMPONENT_NAME,
        "code_digest": str(manifest["code_digest"]),
        "dependency_digest": dependency_digest,
        "code_root": str(code_root),
        "telegram_root": str(
            code_root / "viventium_v0_4" / "telegram-viventium"
        ),
        "execution_root": str(
            code_root
            / "viventium_v0_4"
            / "telegram-viventium"
            / "TelegramVivBot"
        ),
        "python": str(venv_root / "bin" / "python"),
        "compat_cli": str(code_root / "bin" / "viventium"),
        "compat_launcher": str(
            code_root / "viventium_v0_4" / "viventium-librechat-start.sh"
        ),
        "component_tool": str(
            code_root / "scripts" / "viventium" / "telegram_runtime_component.py"
        ),
        "handoff_helper": str(
            code_root / "scripts" / "viventium" / "telegram_poller_handoff.py"
        ),
    }


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    if not args.sync_dependencies:
        raise ComponentError(
            "Telegram runtime selection requires a complete synchronized dependency environment"
        )
    repo_root = _lexical(Path(args.repo_root))
    app_support = _lexical(Path(args.app_support_dir))
    selection_file = _contained(
        Path(args.selection_file),
        app_support,
        "Telegram runtime component selection",
    )
    _ensure_private_directory(app_support)
    _validate_existing_real_chain(selection_file.parent, "Telegram runtime selection")
    store_root = app_support / "runtime-components" / COMPONENT_NAME
    selected = _selected_sources(repo_root)
    manifest = _source_manifest(selected)
    with _component_lock(store_root):
        code_root, reused_code = _install_code(store_root, selected, manifest)
        dependency_digest = _dependency_digest(code_root)
        python, reused_dependencies = _sync_dependencies(
            store_root,
            code_root,
            dependency_digest,
        )
        payload = _selection_payload(
            app_support=app_support,
            code_root=code_root,
            manifest=manifest,
            dependency_digest=dependency_digest,
        )
        if Path(payload["python"]) != python:
            raise ComponentError("Telegram dependency selection is inconsistent")
        _write_json_atomic(selection_file, payload)
    return {
        **payload,
        "selection_file": str(selection_file),
        "reused_code": reused_code,
        "reused_dependencies": reused_dependencies,
    }


def _resolve_selection_payload(
    app_support: Path,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != SCHEMA_VERSION
        or payload.get("component") != COMPONENT_NAME
    ):
        raise ComponentError("Telegram runtime component selection is invalid")
    store_root = app_support / "runtime-components" / COMPONENT_NAME
    code_digest = str(payload.get("code_digest") or "")
    dependency_digest = str(payload.get("dependency_digest") or "")
    if (
        len(code_digest) != 64
        or len(dependency_digest) != 64
        or any(character not in "0123456789abcdef" for character in code_digest)
        or any(character not in "0123456789abcdef" for character in dependency_digest)
    ):
        raise ComponentError("Telegram runtime component selection has invalid digests")
    code_root = store_root / "code" / code_digest
    manifest_path = code_root / MANIFEST_NAME
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ComponentError("Telegram runtime component manifest is unavailable") from error
    if manifest.get("code_digest") != code_digest:
        raise ComponentError("Telegram runtime component digest does not match its manifest")
    _verify_code_root(code_root, manifest)
    python = _verify_dependency_root(
        store_root / "venv" / dependency_digest,
        dependency_digest,
    )
    expected = _selection_payload(
        app_support=app_support,
        code_root=code_root,
        manifest=manifest,
        dependency_digest=dependency_digest,
    )
    if payload != expected or Path(expected["python"]) != python:
        raise ComponentError("Telegram runtime component selection failed integrity verification")
    return payload


def _read_private_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(_read_private_component_file(path, expected_mode=0o600))
    except (OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ComponentError(f"{label} is unavailable or unsafe") from error
    if not isinstance(value, dict):
        raise ComponentError(f"{label} is invalid")
    return value


def resolve(args: argparse.Namespace) -> dict[str, Any]:
    app_support = _lexical(Path(args.app_support_dir))
    selection_file = _contained(
        Path(args.selection_file),
        app_support,
        "Telegram runtime component selection",
    )
    payload = _read_private_json(
        selection_file,
        "Telegram runtime component selection",
    )
    return _resolve_selection_payload(app_support, payload)


def _canonical_json_sha256(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _telegram_authority(app_support: Path) -> tuple[Path, dict[str, Any]]:
    canonical = app_support / "state" / "telegram-user-configs"
    authority_path = (
        app_support
        / "state"
        / "telegram-user-config-migration"
        / "authority.json"
    )
    authority = _read_private_json(
        authority_path,
        "Telegram preference authority ledger",
    )
    if (
        authority.get("schema_version") != 2
        or authority.get("kind")
        != "viventium-telegram-preference-authority"
        or authority.get("status") != "committed"
        or authority.get("authority") != "canonical-app-support"
        or _lexical(Path(str(authority.get("canonical_root") or "")))
        != canonical
    ):
        raise ComponentError("Telegram preference authority ledger is invalid")
    _validate_existing_real_chain(
        canonical,
        "Canonical Telegram preference root",
    )
    if canonical.exists():
        metadata = canonical.lstat()
        if (
            stat.S_ISLNK(metadata.st_mode)
            or not stat.S_ISDIR(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or stat.S_IMODE(metadata.st_mode) & 0o077
        ):
            raise ComponentError(
                "Canonical Telegram preference root is unsafe"
            )
    return canonical, authority


def _preference_authority(
    app_support: Path,
    requested_root: Path | None,
) -> tuple[Path, str]:
    canonical = app_support / "state" / "telegram-user-configs"
    requested = _lexical(requested_root) if requested_root is not None else canonical
    selection_path = (
        app_support
        / "state"
        / "telegram-user-config-migration"
        / "explicit-authority.json"
    )
    if selection_path.exists() or selection_path.is_symlink():
        selection = _read_private_json(
            selection_path,
            "Telegram preference root selection authority",
        )
        selected_root = _lexical(
            Path(str(selection.get("preference_root") or ""))
        )
        expected_generation = hashlib.sha256(
            ("explicit-authority\0" + str(selected_root)).encode("utf-8")
        ).hexdigest()
        if (
            selection.get("schema_version") != 2
            or selection.get("kind")
            != "viventium-telegram-explicit-preference-authority"
            or selection.get("status") != "committed"
            or selection.get("generation") != expected_generation
            or selected_root != requested
        ):
            raise ComponentError(
                "Telegram preference root selection authority is invalid"
            )
        selected_generation = expected_generation
    else:
        selected_generation = ""
    if requested == canonical:
        authority_path = (
            app_support
            / "state"
            / "telegram-user-config-migration"
            / "authority.json"
        )
        if not authority_path.exists() and not authority_path.is_symlink():
            # A first-hop rollback controller must be armable before the
            # successor commits preference authority. The predecessor already
            # uses this same canonical fallback when no legacy/custom root
            # exists, so this path does not retire or redirect user state.
            _validate_existing_real_chain(
                canonical,
                "Provisional canonical Telegram preference root",
            )
            if canonical.exists():
                metadata = canonical.lstat()
                if (
                    stat.S_ISLNK(metadata.st_mode)
                    or not stat.S_ISDIR(metadata.st_mode)
                    or metadata.st_uid != os.getuid()
                    # Older supported installs created this owner-controlled
                    # tree as 0755/0644.  It must be usable long enough to arm
                    # first-hop rollback before the stopped-writer migration
                    # hardens the tree to 0700/0600.  Writable legacy modes
                    # remain unsafe and fail closed.
                    or stat.S_IMODE(metadata.st_mode) & 0o022
                ):
                    raise ComponentError(
                        "Provisional canonical Telegram preference root is unsafe"
                    )
            return (
                canonical,
                "provisional-canonical:"
                + hashlib.sha256(str(canonical).encode("utf-8")).hexdigest(),
            )
        canonical, authority = _telegram_authority(app_support)
        generation = authority.get("generation")
        if not isinstance(generation, str):
            raise ComponentError(
                "Telegram preference authority generation is invalid"
            )
        return canonical, selected_generation or generation
    _validate_existing_real_chain(
        requested,
        "Explicit Telegram preference root",
    )
    metadata = requested.lstat()
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) & 0o022
    ):
        raise ComponentError("Explicit Telegram preference root is unsafe")
    return (
        requested,
        selected_generation
        or (
            "explicit:"
            + hashlib.sha256(str(requested).encode("utf-8")).hexdigest()
        ),
    )


def _transaction_identity(
    *,
    app_support: Path,
    transaction_kind: str,
    transaction_path: Path,
) -> dict[str, Any]:
    transaction = _lexical(transaction_path)
    if transaction_kind == "upgrade":
        _contained(
            transaction,
            app_support / "upgrade-backups",
            "Telegram recovery upgrade transaction",
        )
        ledger = _read_private_json(
            transaction / "ledger.json",
            "Telegram recovery upgrade ledger",
        )
        repositories = ledger.get("repositories")
        parent = (
            repositories[0]
            if isinstance(repositories, list)
            and repositories
            and isinstance(repositories[0], dict)
            else None
        )
        if (
            ledger.get("schema_version") != 1
            or _lexical(Path(str(ledger.get("transaction_path") or "")))
            != transaction
            or _lexical(Path(str(ledger.get("app_support_dir") or "")))
            != app_support
            or not isinstance(ledger.get("was_running"), bool)
            or not isinstance(parent, dict)
            or parent.get("name") != "parent"
            or not isinstance(parent.get("old_head"), str)
            or not isinstance(parent.get("expected_target"), str)
            or _lexical(Path(str(parent.get("path") or "")))
            != _lexical(Path(str(ledger.get("repo_root") or "")))
        ):
            raise ComponentError("Telegram recovery upgrade ledger is invalid")
        predecessor_identity = parent["old_head"]
        successor_identity = parent["expected_target"]
        if (
            len(predecessor_identity) != 40
            or any(
                character not in "0123456789abcdef"
                for character in predecessor_identity
            )
            or (
                successor_identity
                and (
                    len(successor_identity) != 40
                    or any(
                        character not in "0123456789abcdef"
                        for character in successor_identity
                    )
                )
            )
        ):
            raise ComponentError(
                "Telegram recovery upgrade source identity is invalid"
            )
        return {
            "transaction_kind": transaction_kind,
            "transaction_path": str(transaction),
            "predecessor_repo": str(
                _lexical(Path(str(ledger["repo_root"])))
            ),
            "predecessor_identity": predecessor_identity,
            "successor_identity": successor_identity,
            "was_running": ledger["was_running"],
            "ledger_status": ledger.get("status"),
        }
    if transaction_kind == "dev-runtime-activation":
        _contained(
            transaction,
            app_support / "state",
            "Telegram recovery activation transaction",
        )
        ledger = _read_private_json(
            transaction / "activation.json",
            "Telegram recovery activation ledger",
        )
        candidate_env = ledger.get("candidateEnv")
        if (
            ledger.get("schemaVersion") != 2
            or _lexical(Path(str(ledger.get("transactionDir") or "")))
            != transaction
            or _lexical(Path(str(ledger.get("appSupportDir") or "")))
            != app_support
            or not isinstance(ledger.get("wasRunning"), bool)
            or not isinstance(ledger.get("previousRepo"), str)
            or not isinstance(candidate_env, dict)
            or not isinstance(candidate_env.get("repoRoot"), str)
        ):
            raise ComponentError(
                "Telegram recovery activation ledger is invalid"
            )
        return {
            "transaction_kind": transaction_kind,
            "transaction_path": str(transaction),
            "predecessor_repo": str(
                _lexical(Path(str(ledger["previousRepo"])))
            ),
            "predecessor_identity": str(ledger["previousRepo"]),
            "successor_identity": str(candidate_env["repoRoot"]),
            "was_running": ledger["wasRunning"],
            "ledger_status": ledger.get("status"),
        }
    raise ComponentError("Telegram recovery transaction kind is unsupported")


def publish_recovery(args: argparse.Namespace) -> dict[str, Any]:
    app_support = _lexical(Path(args.app_support_dir))
    selection_file = _contained(
        Path(args.selection_file),
        app_support,
        "Telegram recovery component selection",
    )
    selection = _resolve_selection_payload(
        app_support,
        _read_private_json(
            selection_file,
            "Telegram recovery component selection",
        ),
    )
    preference_root, preference_generation = _preference_authority(
        app_support,
        Path(args.user_configs_root) if args.user_configs_root else None,
    )
    identity = _transaction_identity(
        app_support=app_support,
        transaction_kind=args.transaction_kind,
        transaction_path=Path(args.transaction_path),
    )
    if identity["ledger_status"] not in {
        "active",
        "rolled_back",
        "prepared",
        "publishing",
        "runtime_backed_up",
        "published",
        "binding_applied",
    }:
        raise ComponentError(
            "Telegram recovery transaction cannot be armed in its current state"
        )
    selection_sha256 = _canonical_json_sha256(selection)
    generation_id = hashlib.sha256(
        (
            identity["transaction_kind"]
            + "\0"
            + identity["transaction_path"]
            + "\0"
            + identity["predecessor_identity"]
            + "\0"
            + identity["successor_identity"]
            + "\0"
            + selection_sha256
        ).encode("utf-8")
    ).hexdigest()
    generation = {
        "schema_version": 1,
        "kind": RECOVERY_GENERATION_KIND,
        "status": "active",
        "generation_id": generation_id,
        "transaction_kind": identity["transaction_kind"],
        "transaction_path": identity["transaction_path"],
    }
    receipt = {
        "schema_version": 1,
        "kind": RECOVERY_KIND,
        "status": "armed",
        "generation_id": generation_id,
        "transaction_kind": identity["transaction_kind"],
        "transaction_path": identity["transaction_path"],
        "predecessor_repo": identity["predecessor_repo"],
        "predecessor_identity": identity["predecessor_identity"],
        "successor_identity": identity["successor_identity"],
        "was_running": identity["was_running"],
        "user_configs_root": str(preference_root),
        "preference_authority_generation": preference_generation,
        "selection_sha256": selection_sha256,
        "selection_file": str(selection_file),
        "selection": selection,
    }
    _write_json_atomic(app_support / RECOVERY_GENERATION, generation)
    _write_json_atomic(app_support / RECOVERY_RECEIPT, receipt)
    return {
        "status": "armed",
        "generation_id": generation_id,
        "receipt": str(app_support / RECOVERY_RECEIPT),
        "was_running": identity["was_running"],
    }


def resolve_recovery(args: argparse.Namespace) -> dict[str, Any]:
    app_support = _lexical(Path(args.app_support_dir))
    receipt = _read_private_json(
        app_support / RECOVERY_RECEIPT,
        "Telegram recovery receipt",
    )
    generation = _read_private_json(
        app_support / RECOVERY_GENERATION,
        "Telegram recovery generation",
    )
    selection = receipt.get("selection")
    selection_file_value = receipt.get("selection_file")
    if (
        receipt.get("schema_version") != 1
        or receipt.get("kind") != RECOVERY_KIND
        or receipt.get("status") != "armed"
        or not isinstance(receipt.get("generation_id"), str)
        or not isinstance(receipt.get("was_running"), bool)
        or not isinstance(selection, dict)
        or not isinstance(selection_file_value, str)
        or generation.get("schema_version") != 1
        or generation.get("kind") != RECOVERY_GENERATION_KIND
        or generation.get("status") != "active"
        or generation.get("generation_id") != receipt.get("generation_id")
        or generation.get("transaction_kind")
        != receipt.get("transaction_kind")
        or generation.get("transaction_path")
        != receipt.get("transaction_path")
        or _canonical_json_sha256(selection)
        != receipt.get("selection_sha256")
    ):
        raise ComponentError(
            "Telegram recovery receipt generation is invalid or retired"
        )
    selection_file = _contained(
        Path(selection_file_value),
        app_support,
        "Telegram recovery component selection",
    )
    current_selection = _read_private_json(
        selection_file,
        "Telegram recovery component selection",
    )
    if (
        current_selection != selection
        or _canonical_json_sha256(current_selection)
        != receipt.get("selection_sha256")
    ):
        raise ComponentError(
            "Telegram recovery component selection no longer matches"
        )
    resolved = _resolve_selection_payload(app_support, selection)
    preference_root, preference_generation = _preference_authority(
        app_support,
        Path(str(receipt.get("user_configs_root") or "")),
    )
    identity = _transaction_identity(
        app_support=app_support,
        transaction_kind=str(receipt.get("transaction_kind") or ""),
        transaction_path=Path(str(receipt.get("transaction_path") or "")),
    )
    for key in (
        "transaction_kind",
        "transaction_path",
        "predecessor_repo",
        "predecessor_identity",
        "successor_identity",
        "was_running",
    ):
        if receipt.get(key) != identity.get(key):
            raise ComponentError(
                "Telegram recovery receipt no longer matches its transaction"
            )
    if (
        receipt.get("user_configs_root") != str(preference_root)
        or receipt.get("preference_authority_generation")
        != preference_generation
    ):
        raise ComponentError(
            "Telegram recovery preference authority no longer matches"
        )
    status = identity["ledger_status"]
    if status == "rolled_back":
        disposition = "recovery"
    elif status in {
        "active",
        "committed",
        "prepared",
        "publishing",
        "runtime_backed_up",
        "published",
        "binding_applied",
        "core_committed",
    }:
        disposition = "passive"
    else:
        raise ComponentError(
            "Telegram recovery transaction status is unsupported"
        )
    return {
        **resolved,
        "disposition": disposition,
        "generation_id": receipt["generation_id"],
        "transaction_kind": receipt["transaction_kind"],
        "transaction_path": receipt["transaction_path"],
        "predecessor_repo": receipt["predecessor_repo"],
        "was_running": receipt["was_running"],
        "selection_file": str(selection_file),
        "user_configs_root": receipt["user_configs_root"],
    }


def clear_recovery(args: argparse.Namespace) -> dict[str, Any]:
    app_support = _lexical(Path(args.app_support_dir))
    receipt_path = app_support / RECOVERY_RECEIPT
    generation_path = app_support / RECOVERY_GENERATION
    if not receipt_path.exists() and not receipt_path.is_symlink():
        if generation_path.exists() or generation_path.is_symlink():
            generation = _read_private_json(
                generation_path,
                "Telegram recovery generation",
            )
            generation["status"] = "retired"
            _write_json_atomic(generation_path, generation)
        return {"status": "not_present"}
    receipt = _read_private_json(receipt_path, "Telegram recovery receipt")
    generation = _read_private_json(
        generation_path,
        "Telegram recovery generation",
    )
    if generation.get("generation_id") != receipt.get("generation_id"):
        raise ComponentError(
            "Telegram recovery generation cannot be retired safely"
        )
    generation["status"] = "retired"
    _write_json_atomic(generation_path, generation)
    receipt_path.unlink()
    descriptor = os.open(
        receipt_path.parent,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
    )
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    legacy_config_receipt = (
        app_support
        / "state"
        / "continuity"
        / "telegram-recovery-config-root.json"
    )
    if legacy_config_receipt.is_symlink():
        raise ComponentError(
            "Legacy Telegram recovery receipt is unsafe"
        )
    legacy_config_receipt.unlink(missing_ok=True)
    return {
        "status": "retired",
        "generation_id": receipt.get("generation_id"),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--repo-root", required=True)
    prepare_parser.add_argument("--app-support-dir", required=True)
    prepare_parser.add_argument("--selection-file", required=True)
    prepare_parser.add_argument("--sync-dependencies", action="store_true")
    resolve_parser = subparsers.add_parser("resolve")
    resolve_parser.add_argument("--app-support-dir", required=True)
    resolve_parser.add_argument("--selection-file", required=True)
    publish_parser = subparsers.add_parser("publish-recovery")
    publish_parser.add_argument("--app-support-dir", required=True)
    publish_parser.add_argument("--selection-file", required=True)
    publish_parser.add_argument(
        "--transaction-kind",
        required=True,
        choices=("upgrade", "dev-runtime-activation"),
    )
    publish_parser.add_argument("--transaction-path", required=True)
    publish_parser.add_argument("--user-configs-root")
    recovery_parser = subparsers.add_parser("resolve-recovery")
    recovery_parser.add_argument("--app-support-dir", required=True)
    clear_parser = subparsers.add_parser("clear-recovery")
    clear_parser.add_argument("--app-support-dir", required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        handlers = {
            "prepare": prepare,
            "resolve": resolve,
            "publish-recovery": publish_recovery,
            "resolve-recovery": resolve_recovery,
            "clear-recovery": clear_recovery,
        }
        payload = handlers[args.command](args)
    except (ComponentError, OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 4
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

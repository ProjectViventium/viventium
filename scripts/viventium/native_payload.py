#!/usr/bin/env python3
"""Immutable Native runtime payload verification and activation reference.

This module is intentionally independent from canonical configuration and App Support data. It is
used by release tooling and local clean-room QA while the final public bootstrap is compiled into a
signed macOS executable. Production verification fails closed unless an SSH-signed canonical
manifest and its pinned allowed-signers file are supplied. Unsigned artifacts require an explicit,
manifest-bound local-QA override.
"""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import tempfile
import unicodedata
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from typing import Callable, Iterator


MANIFEST_SCHEMA_VERSION = 1
MAX_MANIFEST_BYTES = 2 * 1024 * 1024
MAX_ARCHIVE_BYTES = 8 * 1024 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 16 * 1024 * 1024 * 1024
MAX_FILE_COUNT = 200_000
MIN_FREE_RESERVE_BYTES = 10 * 1024 * 1024 * 1024
RELEASE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SAFE_STAGING_CLEANUP_RE = re.compile(
    r"^(?:quarantine-|retired-)?[A-Za-z0-9][A-Za-z0-9._-]{0,159}\.[0-9a-f]{32}$"
)
SIGNING_IDENTITY = "releases@viventium.example"
SIGNING_NAMESPACE = "viventium-release"


class PayloadError(RuntimeError):
    pass


class VerifiedCandidate:
    def __init__(
        self, manifest_path: Path, manifest_bytes: bytes, payload: dict
    ) -> None:
        self.manifest_path = manifest_path
        self.manifest_bytes = manifest_bytes
        self.payload = payload
        self.release_id = payload["release_id"]
        self.sequence = payload["sequence"]
        self.node_version = payload["runtime"]["node"]
        self.data_schema_minimum = payload["runtime"]["data_schema"]["minimum"]
        self.data_schema_maximum = payload["runtime"]["data_schema"]["maximum"]
        self.manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()

    @property
    def release_key(self) -> str:
        return f"{self.release_id}-{self.manifest_sha256[:12]}"


def canonical_manifest_bytes(payload: dict) -> bytes:
    return (
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _filesystem_collision_key(raw: str) -> str:
    normalized = unicodedata.normalize("NFC", raw)
    return unicodedata.normalize("NFC", normalized.casefold())


def _require_dict(value: object, label: str) -> dict:
    if not isinstance(value, dict):
        raise PayloadError(f"{label} must be an object")
    return value


def _require_exact_keys(value: dict, expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise PayloadError(
            f"{label} keys are invalid (missing={missing}, extra={extra})"
        )


def _require_int(
    value: object, label: str, *, minimum: int = 0, maximum: int | None = None
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < minimum
        or (maximum is not None and value > maximum)
    ):
        suffix = f" and <= {maximum}" if maximum is not None else ""
        raise PayloadError(f"{label} must be an integer >= {minimum}{suffix}")
    return value


def _require_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise PayloadError(f"{label} must be a non-empty string")
    return value


def _version_tuple(raw: str) -> tuple[int, ...]:
    parts = raw.split(".")
    if not parts or any(not part.isdigit() for part in parts):
        raise PayloadError(f"invalid version: {raw}")
    return tuple(int(part) for part in parts)


def _safe_relative_path(raw: str, *, label: str = "archive") -> PurePosixPath:
    if (
        not raw
        or "\x00" in raw
        or "\\" in raw
        or raw.startswith("/")
        or len(raw) > 1024
    ):
        raise PayloadError(f"unsafe archive path: {raw!r}")
    path = PurePosixPath(raw)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise PayloadError(f"unsafe archive path: {raw!r}")
    if len(path.parts) == 0:
        raise PayloadError(f"unsafe {label} path: {raw!r}")
    return path


def _validate_manifest(payload: dict) -> None:
    _require_exact_keys(
        payload,
        {
            "schema_version",
            "release_id",
            "sequence",
            "channel",
            "local_qa",
            "platform",
            "artifact",
            "runtime",
            "files",
        },
        "manifest",
    )
    if payload["schema_version"] != MANIFEST_SCHEMA_VERSION:
        raise PayloadError(
            f"unsupported manifest schema: {payload['schema_version']!r}"
        )
    release_id = _require_string(payload["release_id"], "release_id")
    if not RELEASE_ID_RE.fullmatch(release_id):
        raise PayloadError("release_id contains unsupported characters")
    _require_int(payload["sequence"], "sequence", minimum=1, maximum=999_999_999)
    channel = _require_string(payload["channel"], "channel")
    if not isinstance(payload["local_qa"], bool):
        raise PayloadError("local_qa must be boolean")
    if channel not in {"stable", "local-qa"}:
        raise PayloadError(f"unsupported release channel: {channel}")
    if payload["local_qa"] is not (channel == "local-qa"):
        raise PayloadError("manifest channel and local_qa policy are inconsistent")

    target = _require_dict(payload["platform"], "platform")
    _require_exact_keys(target, {"os", "arch", "minimum_version"}, "platform")
    if target["os"] != "macos":
        raise PayloadError("only macOS Native payloads are supported")
    if target["arch"] not in {"arm64", "x86_64"}:
        raise PayloadError("unsupported payload architecture")
    _version_tuple(
        _require_string(target["minimum_version"], "platform.minimum_version")
    )

    artifact = _require_dict(payload["artifact"], "artifact")
    _require_exact_keys(
        artifact,
        {"filename", "sha256", "size", "uncompressed_size"},
        "artifact",
    )
    filename = _require_string(artifact["filename"], "artifact.filename")
    if Path(filename).name != filename or not filename.endswith(".zip"):
        raise PayloadError("artifact.filename must be one zip basename")
    if not SHA256_RE.fullmatch(str(artifact["sha256"])):
        raise PayloadError("artifact.sha256 must be a lowercase SHA-256 digest")
    artifact_size = _require_int(artifact["size"], "artifact.size", minimum=1)
    if artifact_size > MAX_ARCHIVE_BYTES:
        raise PayloadError("artifact exceeds the compressed size limit")
    unpacked_size = _require_int(
        artifact["uncompressed_size"], "artifact.uncompressed_size", minimum=1
    )
    if unpacked_size > MAX_UNCOMPRESSED_BYTES:
        raise PayloadError("artifact exceeds the uncompressed size limit")

    runtime = _require_dict(payload["runtime"], "runtime")
    _require_exact_keys(runtime, {"node", "data_schema"}, "runtime")
    node_version = _require_string(runtime["node"], "runtime.node")
    node_parts = _version_tuple(node_version)
    if not node_parts or node_parts[0] != 24:
        raise PayloadError("Native payload must declare a pinned Node 24 runtime")
    data_schema = _require_dict(runtime["data_schema"], "runtime.data_schema")
    _require_exact_keys(data_schema, {"minimum", "maximum"}, "runtime.data_schema")
    schema_min = _require_int(data_schema["minimum"], "runtime.data_schema.minimum")
    schema_max = _require_int(data_schema["maximum"], "runtime.data_schema.maximum")
    if schema_min > schema_max:
        raise PayloadError("runtime.data_schema minimum exceeds maximum")

    files = payload["files"]
    if not isinstance(files, list) or not files or len(files) > MAX_FILE_COUNT:
        raise PayloadError("files must be a non-empty bounded list")
    seen_paths: dict[str, tuple[str, str]] = {}
    total = 0
    for index, raw_entry in enumerate(files):
        entry = _require_dict(raw_entry, f"files[{index}]")
        _require_exact_keys(
            entry, {"path", "sha256", "size", "mode"}, f"files[{index}]"
        )
        raw_path = _require_string(entry["path"], f"files[{index}].path")
        path = _safe_relative_path(raw_path, label="manifest")
        for depth in range(1, len(path.parts) + 1):
            prefix = PurePosixPath(*path.parts[:depth]).as_posix()
            kind = "file" if depth == len(path.parts) else "directory"
            normalized = _filesystem_collision_key(prefix)
            prior = seen_paths.get(normalized)
            if prior is None:
                seen_paths[normalized] = (prefix, kind)
                continue
            prior_path, prior_kind = prior
            if prior_path != prefix or (kind == "file" and prior_kind == "file"):
                raise PayloadError(f"case-insensitive path collision: {raw_path}")
            if prior_kind != kind:
                raise PayloadError(f"file/directory path conflict: {raw_path}")
        if not SHA256_RE.fullmatch(str(entry["sha256"])):
            raise PayloadError(f"invalid file SHA-256: {raw_path}")
        size = _require_int(entry["size"], f"files[{index}].size")
        total += size
        if entry["mode"] not in {0o644, 0o755}:
            raise PayloadError(f"unsupported file mode: {raw_path}")
    if total != unpacked_size:
        raise PayloadError(
            "manifest file sizes do not match artifact.uncompressed_size"
        )


def _verify_ssh_signature(
    manifest_bytes: bytes,
    signature_path: Path,
    allowed_signers_path: Path,
) -> None:
    if (
        signature_path.is_symlink()
        or allowed_signers_path.is_symlink()
        or not signature_path.is_file()
        or not allowed_signers_path.is_file()
    ):
        raise PayloadError(
            "manifest signature and pinned allowed-signers file are required"
        )
    completed = subprocess.run(
        [
            "/usr/bin/ssh-keygen",
            "-Y",
            "verify",
            "-f",
            str(allowed_signers_path),
            "-I",
            SIGNING_IDENTITY,
            "-n",
            SIGNING_NAMESPACE,
            "-s",
            str(signature_path),
        ],
        input=manifest_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise PayloadError("manifest publisher signature verification failed")


def verify_manifest(
    manifest_path: Path,
    *,
    signature_path: Path | None = None,
    allowed_signers_path: Path | None = None,
    allow_unsigned_local_qa: bool = False,
    expected_arch: str | None = None,
    current_macos: str | None = None,
) -> VerifiedCandidate:
    manifest_path = Path(manifest_path)
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise PayloadError("manifest is not a regular file")
    if manifest_path.stat().st_size > MAX_MANIFEST_BYTES:
        raise PayloadError("manifest exceeds the size limit")
    manifest_bytes = manifest_path.read_bytes()
    try:
        payload = json.loads(manifest_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PayloadError("manifest is not valid UTF-8 JSON") from error
    if not isinstance(payload, dict):
        raise PayloadError("manifest must be a JSON object")
    _validate_manifest(payload)
    if manifest_bytes != canonical_manifest_bytes(payload):
        raise PayloadError("manifest must use canonical JSON encoding")

    if signature_path is not None or allowed_signers_path is not None:
        if signature_path is None or allowed_signers_path is None:
            raise PayloadError(
                "manifest signature and allowed-signers must be supplied together"
            )
        _verify_ssh_signature(
            manifest_bytes, Path(signature_path), Path(allowed_signers_path)
        )
        if payload["channel"] != "stable" or payload["local_qa"] is not False:
            raise PayloadError(
                "publisher signature is valid only for a stable production manifest"
            )
    elif allow_unsigned_local_qa:
        if payload["channel"] != "local-qa" or payload["local_qa"] is not True:
            raise PayloadError(
                "unsigned override is only valid for a local QA manifest"
            )
    else:
        raise PayloadError("publisher signature is required")

    target = payload["platform"]
    host_arch = expected_arch or platform.machine()
    if host_arch != target["arch"]:
        raise PayloadError(
            f"payload architecture {target['arch']} does not match host architecture {host_arch}"
        )
    host_version = current_macos or platform.mac_ver()[0]
    if not host_version:
        completed = subprocess.run(
            ["/usr/bin/sw_vers", "-productVersion"],
            check=False,
            capture_output=True,
            text=True,
        )
        host_version = completed.stdout.strip()
    if _version_tuple(host_version) < _version_tuple(target["minimum_version"]):
        raise PayloadError(
            f"payload requires macOS {target['minimum_version']} or newer; host is {host_version}"
        )

    return VerifiedCandidate(manifest_path, manifest_bytes, payload)


def verify_candidate(
    manifest_path: Path,
    artifact_path: Path,
    *,
    signature_path: Path | None = None,
    allowed_signers_path: Path | None = None,
    allow_unsigned_local_qa: bool = False,
    expected_arch: str | None = None,
    current_macos: str | None = None,
) -> VerifiedCandidate:
    candidate = verify_manifest(
        manifest_path,
        signature_path=signature_path,
        allowed_signers_path=allowed_signers_path,
        allow_unsigned_local_qa=allow_unsigned_local_qa,
        expected_arch=expected_arch,
        current_macos=current_macos,
    )
    artifact_path = Path(artifact_path)
    artifact = candidate.payload["artifact"]
    if artifact_path.is_symlink() or not artifact_path.is_file() or artifact_path.name != artifact["filename"]:
        raise PayloadError("artifact path does not match the manifest filename")
    if artifact_path.stat().st_size != artifact["size"]:
        raise PayloadError("artifact size does not match the manifest")
    if _sha256_file(artifact_path) != artifact["sha256"]:
        raise PayloadError("artifact SHA-256 does not match the manifest")
    return candidate


def _state_root(install_root: Path) -> Path:
    return install_root / "state" / "native-installer"


def _ensure_mutable_directory(path: Path, *, create: bool = True) -> None:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        if not create:
            raise PayloadError(f"mutable directory is unavailable: {path.name}")
        try:
            path.mkdir(mode=0o700)
            metadata = path.lstat()
        except (FileExistsError, OSError) as error:
            raise PayloadError(f"mutable directory is unsafe: {path.name}") from error
    except OSError as error:
        raise PayloadError(f"mutable directory is unsafe: {path.name}") from error
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != os.getuid()
    ):
        raise PayloadError(f"mutable directory is unsafe: {path.name}")
    if stat.S_IMODE(metadata.st_mode) & 0o077:
        os.chmod(path, 0o700)


def _open_mutable_file(path: Path, flags: int, mode: int) -> int:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        metadata = None
    except OSError as error:
        raise PayloadError(f"mutable installer file is unsafe: {path.name}") from error
    if metadata is not None and (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
    ):
        raise PayloadError(f"mutable installer file is unsafe: {path.name}")
    descriptor = -1
    try:
        descriptor = os.open(path, flags | getattr(os, "O_NOFOLLOW", 0), mode)
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or opened.st_uid != os.getuid():
            raise PayloadError(f"mutable installer file is unsafe: {path.name}")
        os.fchmod(descriptor, mode)
        return descriptor
    except Exception:
        if descriptor >= 0:
            os.close(descriptor)
        raise


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_bytes_fsync(path: Path, value: bytes, mode: int) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    _fsync_directory(path.parent)


def _append_journal(
    install_root: Path, event: str, candidate: VerifiedCandidate
) -> None:
    state_root = _state_root(install_root)
    _ensure_mutable_directory(state_root)
    record = {
        "schema": 1,
        "event": event,
        "releaseId": candidate.release_id,
        "sequence": candidate.sequence,
        "manifestSha256": candidate.manifest_sha256,
    }
    journal_path = state_root / "journal.ndjson"
    encoded = (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )
    descriptor = _open_mutable_file(
        journal_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600
    )
    try:
        os.write(descriptor, encoded)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    _fsync_directory(state_root)


def _zip_entry_kind(info: zipfile.ZipInfo) -> str:
    unix_mode = (info.external_attr >> 16) & 0xFFFF
    file_type = stat.S_IFMT(unix_mode)
    if info.is_dir() or info.filename.endswith("/"):
        return "directory"
    if file_type == stat.S_IFLNK:
        return "symlink"
    if file_type not in {0, stat.S_IFREG}:
        return "special"
    return "file"


def _validate_zip(
    candidate: VerifiedCandidate, archive: zipfile.ZipFile
) -> list[zipfile.ZipInfo]:
    infos = archive.infolist()
    if len(infos) > MAX_FILE_COUNT:
        raise PayloadError("archive has too many entries")
    expected = {entry["path"]: entry for entry in candidate.payload["files"]}
    seen_casefold: set[str] = set()
    actual_files: dict[str, zipfile.ZipInfo] = {}
    total = 0
    for info in infos:
        raw_path = info.filename[:-1] if info.filename.endswith("/") else info.filename
        path = _safe_relative_path(raw_path)
        folded = _filesystem_collision_key(path.as_posix())
        if folded in seen_casefold:
            raise PayloadError(f"case-insensitive path collision: {path.as_posix()}")
        seen_casefold.add(folded)
        if info.flag_bits & 0x1:
            raise PayloadError("encrypted zip entries are unsupported")
        kind = _zip_entry_kind(info)
        if kind == "symlink":
            raise PayloadError(f"archive symlink is forbidden: {path.as_posix()}")
        if kind == "special":
            raise PayloadError(f"archive special file is forbidden: {path.as_posix()}")
        if kind == "file":
            actual_files[path.as_posix()] = info
            total += info.file_size
            if total > MAX_UNCOMPRESSED_BYTES:
                raise PayloadError("archive exceeds the uncompressed size limit")
    if set(actual_files) != set(expected):
        raise PayloadError("archive file set does not match manifest")
    if total != candidate.payload["artifact"]["uncompressed_size"]:
        raise PayloadError("archive uncompressed size does not match manifest")
    for path, info in actual_files.items():
        if info.file_size != expected[path]["size"]:
            raise PayloadError(f"archive file size does not match manifest: {path}")
    return [actual_files[path] for path in sorted(actual_files)]


def _immutable_file_mode(logical_mode: int) -> int:
    return logical_mode & ~0o222


def _apply_manifest_modes(root: Path, manifest_files: dict[str, dict]) -> None:
    for relative_path, entry in manifest_files.items():
        path = root / relative_path
        os.chmod(path, _immutable_file_mode(entry["mode"]))
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def _make_directories_immutable(root: Path) -> None:
    directories = sorted(
        (path for path in root.rglob("*") if path.is_dir()),
        key=lambda path: len(path.parts),
        reverse=True,
    )
    # Verified public payload trees are intentionally immutable after activation.
    for directory in directories:
        os.chmod(directory, 0o555)  # nosec B103
    os.chmod(root, 0o555)  # nosec B103


def _fsync_tree_directories(root: Path) -> None:
    directories = sorted(
        (path for path in root.rglob("*") if path.is_dir()),
        key=lambda path: len(path.parts),
        reverse=True,
    )
    for directory in directories:
        _fsync_directory(directory)
    _fsync_directory(root)


def _verify_staged_release(
    candidate: VerifiedCandidate,
    release_path: Path,
    *,
    require_immutable_modes: bool = True,
) -> None:
    if release_path.is_symlink() or not release_path.is_dir():
        raise PayloadError("staged release must be a real directory")

    manifest_path = release_path / ".viventium-manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise PayloadError("staged release manifest is missing or unsafe")
    if manifest_path.read_bytes() != candidate.manifest_bytes:
        raise PayloadError("staged release manifest does not match verified candidate")

    manifest_files = {entry["path"]: entry for entry in candidate.payload["files"]}
    expected_files = set(manifest_files)
    expected_directories: set[str] = set()
    for relative_path in expected_files:
        for parent in PurePosixPath(relative_path).parents:
            if parent.as_posix() != ".":
                expected_directories.add(parent.as_posix())

    actual_files: dict[str, Path] = {}
    actual_directories: dict[str, Path] = {}
    for current_root, dirnames, filenames in os.walk(
        release_path, topdown=True, followlinks=False
    ):
        root = Path(current_root)
        if root != release_path:
            actual_directories[root.relative_to(release_path).as_posix()] = root
        for name in dirnames:
            path = root / name
            if path.is_symlink() or not path.is_dir():
                raise PayloadError(
                    f"staged release contains an unsafe directory: {name}"
                )
        for name in filenames:
            path = root / name
            relative_path = path.relative_to(release_path).as_posix()
            metadata = path.lstat()
            if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
                raise PayloadError(
                    f"staged release contains an unsafe file: {relative_path}"
                )
            if metadata.st_nlink != 1:
                raise PayloadError(
                    f"staged release contains a hard-linked file: {relative_path}"
                )
            if relative_path != ".viventium-manifest.json":
                actual_files[relative_path] = path

    unexpected_files = sorted(set(actual_files) - expected_files)
    missing_files = sorted(expected_files - set(actual_files))
    if unexpected_files:
        raise PayloadError(
            f"staged release contains unexpected files: {unexpected_files}"
        )
    if missing_files:
        raise PayloadError(f"staged release is missing manifest files: {missing_files}")
    unexpected_directories = sorted(set(actual_directories) - expected_directories)
    if unexpected_directories:
        raise PayloadError(
            f"staged release contains unexpected directories: {unexpected_directories}"
        )

    if require_immutable_modes:
        directories_to_check = {".": release_path, **actual_directories}
        for relative_path, path in directories_to_check.items():
            if stat.S_IMODE(path.stat().st_mode) != 0o555:
                raise PayloadError(
                    f"staged release directory mode is mutable: {relative_path}"
                )

        if stat.S_IMODE(manifest_path.stat().st_mode) != 0o444:
            raise PayloadError("staged release manifest mode is mutable")
    for relative_path, entry in manifest_files.items():
        path = actual_files[relative_path]
        metadata = path.stat()
        if metadata.st_size != entry["size"]:
            raise PayloadError(
                f"staged file size does not match manifest: {relative_path}"
            )
        if _sha256_file(path) != entry["sha256"]:
            raise PayloadError(
                f"staged file digest does not match manifest: {relative_path}"
            )
        if require_immutable_modes:
            expected_mode = _immutable_file_mode(entry["mode"])
            if stat.S_IMODE(metadata.st_mode) != expected_mode:
                raise PayloadError(
                    f"staged file mode is mutable or invalid: {relative_path}"
                )


def _pending_stage_path(install_root: Path) -> Path:
    return _state_root(install_root) / "pending-stage.json"


def _read_pending_stage(install_root: Path) -> dict | None:
    path = _pending_stage_path(install_root)
    payload = _read_json_state(
        path,
        expected_keys={
            "attemptName",
            "candidateReleaseKey",
            "manifestSha256",
            "phase",
            "schema",
        },
        label="pending stage",
    )
    if payload is None:
        return None
    if (
        payload["schema"] != 1
        or payload["phase"] not in {"prepared", "published"}
        or not isinstance(payload["manifestSha256"], str)
        or not SHA256_RE.fullmatch(payload["manifestSha256"])
    ):
        raise PayloadError("pending stage state is invalid")
    _safe_state_basename(payload["candidateReleaseKey"], label="pending stage")
    _safe_state_basename(payload["attemptName"], label="pending stage")
    return payload


def _write_pending_stage(
    install_root: Path,
    candidate: VerifiedCandidate,
    attempt_name: str,
    *,
    phase: str,
) -> None:
    _write_json_state(
        _pending_stage_path(install_root),
        {
            "attemptName": attempt_name,
            "candidateReleaseKey": candidate.release_key,
            "manifestSha256": candidate.manifest_sha256,
            "phase": phase,
            "schema": 1,
        },
    )


def _pending_stage_matches_candidate(
    payload: dict, candidate: VerifiedCandidate
) -> bool:
    return (
        payload["candidateReleaseKey"] == candidate.release_key
        and payload["manifestSha256"] == candidate.manifest_sha256
    )


def _quarantine_incomplete_stage(
    source: Path,
    staging_root: Path,
    candidate: VerifiedCandidate,
) -> Path:
    try:
        metadata = source.lstat()
    except OSError as error:
        raise PayloadError(
            "incomplete staged release is unsafe and cannot be quarantined"
        ) from error
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != os.getuid()
    ):
        raise PayloadError(
            "incomplete staged release is unsafe and cannot be quarantined"
        )
    quarantine = staging_root / f"quarantine-{candidate.release_key}.{uuid.uuid4().hex}"
    os.replace(source, quarantine)
    _fsync_directory(source.parent)
    if source.parent != staging_root:
        _fsync_directory(staging_root)
    return quarantine


def _existing_capacity_path(path: Path) -> Path:
    candidate = Path(path)
    while not candidate.exists() and candidate.parent != candidate:
        candidate = candidate.parent
    return candidate


def preflight_stage_capacity(
    candidate: VerifiedCandidate,
    install_root: Path,
    *,
    reserve_bytes: int = MIN_FREE_RESERVE_BYTES,
) -> int:
    unpacked_size = int(candidate.payload["artifact"]["uncompressed_size"])
    required = unpacked_size + reserve_bytes
    try:
        free = shutil.disk_usage(_existing_capacity_path(Path(install_root))).free
    except OSError as error:
        raise PayloadError("Native payload free disk space could not be verified") from error
    if free < required:
        raise PayloadError(
            "Native payload needs more free disk space before staging "
            f"(required={required}, available={free})"
        )
    return required


def _candidate_from_staged_release(release: Path) -> VerifiedCandidate:
    manifest = release / ".viventium-manifest.json"
    try:
        manifest_bytes = manifest.read_bytes()
        payload = json.loads(manifest_bytes)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PayloadError(f"unsafe release entry: {release.name}") from error
    if not isinstance(payload, dict):
        raise PayloadError(f"unsafe release entry: {release.name}")
    _validate_manifest(payload)
    if manifest_bytes != canonical_manifest_bytes(payload):
        raise PayloadError(f"unsafe release entry: {release.name}")
    candidate = VerifiedCandidate(manifest, manifest_bytes, payload)
    if candidate.release_key != release.name:
        raise PayloadError(f"unsafe release entry: {release.name}")
    _verify_staged_release(candidate, release)
    return candidate


def _make_verified_tree_removable(path: Path) -> None:
    files: list[Path] = []
    directories: list[Path] = []
    for current, child_directories, child_files in os.walk(
        path, topdown=True, followlinks=False
    ):
        current_path = Path(current)
        metadata = current_path.lstat()
        if (
            stat.S_ISLNK(metadata.st_mode)
            or not stat.S_ISDIR(metadata.st_mode)
            or metadata.st_uid != os.getuid()
        ):
            raise PayloadError(f"unsafe app-owned storage tree: {path.name}")
        directories.append(current_path)
        for name in [*child_directories, *child_files]:
            child = current_path / name
            child_metadata = child.lstat()
            if stat.S_ISLNK(child_metadata.st_mode) or child_metadata.st_uid != os.getuid():
                raise PayloadError(f"unsafe app-owned storage tree: {path.name}")
            if name in child_files:
                if (
                    not stat.S_ISREG(child_metadata.st_mode)
                    or child_metadata.st_nlink != 1
                ):
                    raise PayloadError(f"unsafe app-owned storage tree: {path.name}")
                files.append(child)
            elif not stat.S_ISDIR(child_metadata.st_mode):
                raise PayloadError(f"unsafe app-owned storage tree: {path.name}")
    for file_path in files:
        file_path.chmod(0o600)
    for directory in sorted(directories, key=lambda item: len(item.parts), reverse=True):
        directory.chmod(0o700)


def _remove_verified_tree(path: Path) -> None:
    _make_verified_tree_removable(path)
    shutil.rmtree(path)


def prune_install_storage(install_root: Path) -> None:
    """Retain only active + one rollback release and remove exact app-owned staging residue."""
    install_root = Path(install_root)
    releases_root = install_root / "releases"
    staging_root = install_root / "staging"
    _ensure_mutable_directory(install_root, create=False)
    _ensure_mutable_directory(releases_root, create=False)
    _ensure_mutable_directory(staging_root, create=False)
    with _exclusive_install_lock(install_root):
        if _read_pending_stage(install_root) is not None:
            raise PayloadError("unfinished staging transaction must be recovered before cleanup")
        active = _read_pointer(install_root / "active", releases_root)
        previous = _read_pointer(install_root / "previous", releases_root)
        retained = {
            path.resolve() for path in (active, previous) if path is not None
        }
        for release in sorted(releases_root.iterdir(), key=lambda item: item.name):
            try:
                metadata = release.lstat()
            except OSError as error:
                raise PayloadError(f"unsafe release entry: {release.name}") from error
            if (
                stat.S_ISLNK(metadata.st_mode)
                or not stat.S_ISDIR(metadata.st_mode)
                or metadata.st_uid != os.getuid()
            ):
                raise PayloadError(f"unsafe release entry: {release.name}")
            candidate = _candidate_from_staged_release(release)
            if release.resolve() in retained:
                continue
            retired = staging_root / f"retired-{candidate.release_key}.{uuid.uuid4().hex}"
            release.chmod(0o700)
            try:
                os.replace(release, retired)
            except Exception:
                with contextlib.suppress(OSError):
                    release.chmod(0o555)
                raise
            _fsync_directory(releases_root)
            _fsync_directory(staging_root)
            _remove_verified_tree(retired)
            _fsync_directory(staging_root)

        for residue in sorted(staging_root.iterdir(), key=lambda item: item.name):
            if not SAFE_STAGING_CLEANUP_RE.fullmatch(residue.name):
                raise PayloadError(f"unsafe staging entry: {residue.name}")
            _remove_verified_tree(residue)
            _fsync_directory(staging_root)


def stage_candidate(
    candidate: VerifiedCandidate,
    artifact_path: Path,
    install_root: Path,
) -> Path:
    install_root = Path(install_root)
    releases_root = install_root / "releases"
    staging_root = install_root / "staging"
    preflight_stage_capacity(candidate, install_root)
    if not install_root.exists() and not install_root.is_symlink():
        install_root.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    _ensure_mutable_directory(install_root)
    _ensure_mutable_directory(releases_root)
    _ensure_mutable_directory(staging_root)
    final_path = releases_root / candidate.release_key
    pending_path = _pending_stage_path(install_root)

    with _exclusive_install_lock(install_root):
        pending = _read_pending_stage(install_root)
        if pending is not None and not _pending_stage_matches_candidate(
            pending, candidate
        ):
            raise PayloadError(
                "unfinished staging transaction belongs to a different candidate"
            )

        if final_path.exists() or final_path.is_symlink():
            if pending is None:
                _verify_staged_release(candidate, final_path)
                return final_path
            try:
                _verify_staged_release(candidate, final_path)
            except PayloadError:
                try:
                    _verify_staged_release(
                        candidate,
                        final_path,
                        require_immutable_modes=False,
                    )
                except PayloadError:
                    _quarantine_incomplete_stage(final_path, staging_root, candidate)
                    _append_journal(
                        install_root, "incomplete_stage_quarantined", candidate
                    )
                else:
                    manifest_files = {
                        entry["path"]: entry for entry in candidate.payload["files"]
                    }
                    _apply_manifest_modes(final_path, manifest_files)
                    _make_directories_immutable(final_path)
                    _fsync_tree_directories(final_path)
                    _fsync_directory(releases_root)
                    _verify_staged_release(candidate, final_path)
                    _append_journal(
                        install_root, "interrupted_stage_complete", candidate
                    )
                    _clear_state(pending_path)
                    return final_path
            else:
                _append_journal(install_root, "interrupted_stage_complete", candidate)
                _clear_state(pending_path)
                return final_path

        if pending is not None:
            stale_attempt = staging_root / pending["attemptName"]
            if stale_attempt.exists() or stale_attempt.is_symlink():
                _quarantine_incomplete_stage(stale_attempt, staging_root, candidate)
                _append_journal(install_root, "incomplete_stage_quarantined", candidate)
            _clear_state(pending_path)

        attempt = staging_root / f"{candidate.release_key}.{uuid.uuid4().hex}"
        _write_pending_stage(
            install_root,
            candidate,
            attempt.name,
            phase="prepared",
        )
        attempt.mkdir(mode=0o700)
        _fsync_directory(staging_root)
        _append_journal(install_root, "stage_started", candidate)
        manifest_files = {entry["path"]: entry for entry in candidate.payload["files"]}
        try:
            with zipfile.ZipFile(artifact_path, "r") as archive:
                infos = _validate_zip(candidate, archive)
                for info in infos:
                    entry = manifest_files[info.filename]
                    relative = _safe_relative_path(info.filename)
                    destination = attempt.joinpath(*relative.parts)
                    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                    descriptor = os.open(
                        destination,
                        os.O_WRONLY
                        | os.O_CREAT
                        | os.O_EXCL
                        | getattr(os, "O_NOFOLLOW", 0),
                        0o600,
                    )
                    digest = hashlib.sha256()
                    written = 0
                    try:
                        with (
                            archive.open(info, "r") as source,
                            os.fdopen(descriptor, "wb") as target,
                        ):
                            descriptor = -1
                            while True:
                                chunk = source.read(1024 * 1024)
                                if not chunk:
                                    break
                                written += len(chunk)
                                if written > entry["size"]:
                                    raise PayloadError(
                                        f"archive expanded beyond declared size: {info.filename}"
                                    )
                                digest.update(chunk)
                                target.write(chunk)
                            target.flush()
                            os.fsync(target.fileno())
                    finally:
                        if descriptor >= 0:
                            os.close(descriptor)
                    if (
                        written != entry["size"]
                        or digest.hexdigest() != entry["sha256"]
                    ):
                        raise PayloadError(
                            f"extracted file digest does not match manifest: {info.filename}"
                        )
            _write_bytes_fsync(
                attempt / ".viventium-manifest.json",
                candidate.manifest_bytes,
                0o444,
            )
            _apply_manifest_modes(attempt, manifest_files)
            _fsync_tree_directories(attempt)
            os.replace(attempt, final_path)
            _fsync_directory(releases_root)
            _fsync_directory(staging_root)
            _write_pending_stage(
                install_root,
                candidate,
                attempt.name,
                phase="published",
            )
            _make_directories_immutable(final_path)
            _fsync_tree_directories(final_path)
            _verify_staged_release(candidate, final_path)
            _append_journal(install_root, "stage_complete", candidate)
            _clear_state(pending_path)
            return final_path
        except BaseException:
            if not final_path.exists():
                if (
                    attempt.exists()
                    and not attempt.is_symlink()
                    and attempt.parent.resolve() == staging_root.resolve()
                    and attempt.lstat().st_uid == os.getuid()
                ):
                    shutil.rmtree(attempt, ignore_errors=True)
                _fsync_directory(staging_root)
                _clear_state(pending_path)
            _append_journal(install_root, "stage_failed", candidate)
            raise


@contextlib.contextmanager
def _exclusive_install_lock(install_root: Path) -> Iterator[None]:
    install_root = Path(install_root)
    _ensure_mutable_directory(install_root)
    state_parent = install_root / "state"
    if state_parent.is_symlink():
        raise PayloadError("Native payload state root is unsafe")
    _ensure_mutable_directory(state_parent)
    state_root = _state_root(install_root)
    _ensure_mutable_directory(state_root)
    _fsync_directory(state_root)
    _fsync_directory(state_parent)
    _fsync_directory(install_root)
    _fsync_directory(install_root.parent)
    lock_path = state_root / "install.lock"
    descriptor = _open_mutable_file(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    with os.fdopen(descriptor, "a+b") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise PayloadError(
                "another Native payload transaction is active"
            ) from error
        yield


def _read_pointer(pointer: Path, releases_root: Path) -> Path | None:
    if not pointer.is_symlink():
        if pointer.exists():
            raise PayloadError(f"activation pointer is not a symlink: {pointer.name}")
        return None
    target = (pointer.parent / os.readlink(pointer)).resolve()
    try:
        target.relative_to(releases_root.resolve())
    except ValueError as error:
        raise PayloadError(
            f"activation pointer escapes releases root: {pointer.name}"
        ) from error
    if target.parent != releases_root.resolve() or not target.is_dir():
        raise PayloadError(f"activation pointer target is invalid: {pointer.name}")
    return target


def _atomic_pointer(pointer: Path, target: Path | None) -> None:
    temporary = pointer.parent / f".{pointer.name}-{uuid.uuid4().hex}"
    try:
        if target is None:
            pointer.unlink(missing_ok=True)
            _fsync_directory(pointer.parent)
            return
        relative_target = os.path.relpath(target, pointer.parent)
        os.symlink(relative_target, temporary)
        os.replace(temporary, pointer)
        _fsync_directory(pointer.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_text(path: Path, value: str) -> None:
    _ensure_mutable_directory(path.parent)
    descriptor, temporary_raw = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    temporary = Path(temporary_raw)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _write_json_state(path: Path, payload: dict) -> None:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    _atomic_text(path, encoded)


def _read_json_state(path: Path, *, expected_keys: set[str], label: str) -> dict | None:
    if path.is_symlink():
        raise PayloadError(f"{label} state is unsafe")
    try:
        metadata = path.stat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > 64 * 1024:
        raise PayloadError(f"{label} state is invalid")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PayloadError(f"{label} state is invalid") from error
    if not isinstance(payload, dict) or set(payload) != expected_keys:
        raise PayloadError(f"{label} state is invalid")
    return payload


def _clear_state(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return
    _fsync_directory(path.parent)


def _safe_state_basename(value: object, *, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value in {".", ".."}
        or Path(value).name != value
        or "/" in value
        or "\\" in value
    ):
        raise PayloadError(f"{label} state is invalid")
    return value


def _read_sequence_state(sequence_path: Path) -> tuple[int, str | None]:
    try:
        metadata = sequence_path.lstat()
        if (
            stat.S_ISLNK(metadata.st_mode)
            or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or metadata.st_size > 64 * 1024
        ):
            raise PayloadError("highest-sequence state is unsafe")
        raw = sequence_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return 0, None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        try:
            sequence = int(raw)
        except ValueError as error:
            raise PayloadError("highest-sequence state is invalid") from error
        if sequence < 0:
            raise PayloadError("highest-sequence state is invalid")
        return sequence, None
    if isinstance(payload, int) and not isinstance(payload, bool):
        if payload < 0:
            raise PayloadError("highest-sequence state is invalid")
        return payload, None
    if not isinstance(payload, dict) or set(payload) != {"manifestSha256", "sequence"}:
        raise PayloadError("highest-sequence state is invalid")
    sequence = payload.get("sequence")
    manifest_sha256 = payload.get("manifestSha256")
    if (
        isinstance(sequence, bool)
        or not isinstance(sequence, int)
        or sequence < 0
        or not isinstance(manifest_sha256, str)
        or not SHA256_RE.fullmatch(manifest_sha256)
    ):
        raise PayloadError("highest-sequence state is invalid")
    return sequence, manifest_sha256


def _write_sequence_state(sequence_path: Path, candidate: VerifiedCandidate) -> None:
    payload = {
        "manifestSha256": candidate.manifest_sha256,
        "sequence": candidate.sequence,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    _atomic_text(sequence_path, encoded)


def _pending_activation_path(install_root: Path) -> Path:
    return _state_root(install_root) / "pending-activation.json"


def _read_pending_activation(install_root: Path) -> dict | None:
    payload = _read_json_state(
        _pending_activation_path(install_root),
        expected_keys={
            "candidateReleaseKey",
            "manifestSha256",
            "phase",
            "priorReleaseKey",
            "schema",
        },
        label="pending activation",
    )
    if payload is None:
        return None
    prior_release_key = payload["priorReleaseKey"]
    if (
        payload["schema"] != 1
        or payload["phase"] not in {"prepared", "pointer_switched", "health_passed"}
        or not isinstance(payload["manifestSha256"], str)
        or not SHA256_RE.fullmatch(payload["manifestSha256"])
        or (prior_release_key is not None and not isinstance(prior_release_key, str))
    ):
        raise PayloadError("pending activation state is invalid")
    _safe_state_basename(payload["candidateReleaseKey"], label="pending activation")
    if prior_release_key is not None:
        _safe_state_basename(prior_release_key, label="pending activation")
    return payload


def _write_pending_activation(
    install_root: Path,
    candidate: VerifiedCandidate,
    prior: Path | None,
    *,
    phase: str,
) -> None:
    _write_json_state(
        _pending_activation_path(install_root),
        {
            "candidateReleaseKey": candidate.release_key,
            "manifestSha256": candidate.manifest_sha256,
            "phase": phase,
            "priorReleaseKey": prior.name if prior is not None else None,
            "schema": 1,
        },
    )


def _same_path(left: Path | None, right: Path | None) -> bool:
    if left is None or right is None:
        return left is right
    return left.resolve() == right.resolve()


def _recover_pending_activation(
    install_root: Path,
    releases_root: Path,
    candidate: VerifiedCandidate,
) -> bool:
    pending_path = _pending_activation_path(install_root)
    pending = _read_pending_activation(install_root)
    if pending is None:
        return False
    if (
        pending["candidateReleaseKey"] != candidate.release_key
        or pending["manifestSha256"] != candidate.manifest_sha256
    ):
        raise PayloadError(
            "unfinished activation transaction belongs to a different candidate"
        )

    candidate_release = releases_root / pending["candidateReleaseKey"]
    prior_release = (
        releases_root / pending["priorReleaseKey"]
        if pending["priorReleaseKey"] is not None
        else None
    )
    if prior_release is not None and (
        prior_release.is_symlink()
        or not prior_release.is_dir()
        or prior_release.parent.resolve() != releases_root.resolve()
    ):
        raise PayloadError("recorded prior release is unavailable or unsafe")

    active_pointer = install_root / "active"
    active = _read_pointer(active_pointer, releases_root)
    if pending["phase"] == "health_passed":
        if not _same_path(active, candidate_release):
            raise PayloadError(
                "active pointer changed after the recorded health result"
            )
        _verify_staged_release(candidate, candidate_release)
        _append_journal(
            install_root, "interrupted_health_passed_activation_complete", candidate
        )
        _clear_state(pending_path)
        return True

    if _same_path(active, candidate_release):
        _atomic_pointer(active_pointer, prior_release)
    elif not _same_path(active, prior_release):
        raise PayloadError(
            "active pointer changed during interrupted activation recovery"
        )
    if prior_release is not None:
        _atomic_pointer(install_root / "previous", prior_release)
    _append_journal(install_root, "interrupted_activation_rollback_complete", candidate)
    _clear_state(pending_path)
    return False


def activate_candidate(
    candidate: VerifiedCandidate,
    release_path: Path,
    install_root: Path,
    *,
    current_data_schema: int = 1,
    health_check: Callable[[Path], bool],
) -> Path:
    install_root = Path(install_root)
    release_path = Path(release_path)
    releases_root = install_root / "releases"
    _ensure_mutable_directory(releases_root, create=False)
    expected_release = releases_root / candidate.release_key
    if (
        release_path.resolve() != expected_release.resolve()
        or not release_path.is_dir()
    ):
        raise PayloadError(
            "candidate release path is not the verified immutable release"
        )
    with _exclusive_install_lock(install_root):
        if _recover_pending_activation(install_root, releases_root, candidate):
            return release_path
        _verify_staged_release(candidate, release_path)
        state_root = _state_root(install_root)
        sequence_path = state_root / "highest-sequence"
        highest_sequence, highest_manifest_sha256 = _read_sequence_state(sequence_path)
        if candidate.sequence < highest_sequence:
            raise PayloadError(
                f"manifest sequence {candidate.sequence} is replayed or downgraded from {highest_sequence}"
            )
        if candidate.sequence == highest_sequence:
            if highest_manifest_sha256 is None:
                raise PayloadError(
                    f"manifest sequence {candidate.sequence} has no recorded manifest identity"
                )
            if highest_manifest_sha256 != candidate.manifest_sha256:
                raise PayloadError(
                    f"manifest sequence {candidate.sequence} already belongs to a different manifest"
                )
        if (
            not candidate.data_schema_minimum
            <= current_data_schema
            <= candidate.data_schema_maximum
        ):
            raise PayloadError(
                f"data schema {current_data_schema} is incompatible with candidate range "
                f"{candidate.data_schema_minimum}..{candidate.data_schema_maximum}"
            )

        active_pointer = install_root / "active"
        previous_pointer = install_root / "previous"
        prior = _read_pointer(active_pointer, releases_root)
        if _same_path(prior, release_path):
            return release_path
        _write_pending_activation(
            install_root,
            candidate,
            prior,
            phase="prepared",
        )
        _append_journal(install_root, "activation_started", candidate)
        if candidate.sequence > highest_sequence:
            _write_sequence_state(sequence_path, candidate)
        pointer_switched = False
        health_passed = False
        try:
            if prior is not None:
                _atomic_pointer(previous_pointer, prior)
            _atomic_pointer(active_pointer, release_path)
            pointer_switched = True
            _write_pending_activation(
                install_root,
                candidate,
                prior,
                phase="pointer_switched",
            )
            _append_journal(install_root, "pointer_switched", candidate)

            healthy = False
            try:
                healthy = bool(health_check(release_path))
            except Exception:
                healthy = False
            if not healthy:
                raise PayloadError(
                    "candidate health check failed; last known-good pointer restored"
                )

            _write_pending_activation(
                install_root,
                candidate,
                prior,
                phase="health_passed",
            )
            health_passed = True
            _append_journal(install_root, "health_passed_activation_complete", candidate)
            _clear_state(_pending_activation_path(install_root))
            return release_path
        except BaseException:
            if pointer_switched and not health_passed:
                _atomic_pointer(active_pointer, prior)
                _append_journal(install_root, "health_failed_rollback_complete", candidate)
                _clear_state(_pending_activation_path(install_root))
            raise


def recover_interrupted_activation(
    candidate: VerifiedCandidate, install_root: Path
) -> Path | None:
    """Recover a candidate's pending activation and return the authoritative active release."""
    install_root = Path(install_root)
    releases_root = install_root / "releases"
    _ensure_mutable_directory(releases_root, create=False)
    with _exclusive_install_lock(install_root):
        _recover_pending_activation(install_root, releases_root, candidate)
        return _read_pointer(install_root / "active", releases_root)

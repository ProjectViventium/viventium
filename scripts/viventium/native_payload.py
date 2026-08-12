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
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from typing import Callable, Iterator


MANIFEST_SCHEMA_VERSION = 1
MAX_MANIFEST_BYTES = 2 * 1024 * 1024
MAX_ARCHIVE_BYTES = 8 * 1024 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 16 * 1024 * 1024 * 1024
MAX_FILE_COUNT = 200_000
RELEASE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SIGNING_IDENTITY = "releases@viventium.example"
SIGNING_NAMESPACE = "viventium-release"


class PayloadError(RuntimeError):
    pass


class VerifiedCandidate:
    def __init__(self, manifest_path: Path, manifest_bytes: bytes, payload: dict) -> None:
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
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
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


def _require_dict(value: object, label: str) -> dict:
    if not isinstance(value, dict):
        raise PayloadError(f"{label} must be an object")
    return value


def _require_exact_keys(value: dict, expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise PayloadError(f"{label} keys are invalid (missing={missing}, extra={extra})")


def _require_int(value: object, label: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise PayloadError(f"{label} must be an integer >= {minimum}")
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
    if not raw or "\x00" in raw or "\\" in raw or raw.startswith("/") or len(raw) > 1024:
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
        raise PayloadError(f"unsupported manifest schema: {payload['schema_version']!r}")
    release_id = _require_string(payload["release_id"], "release_id")
    if not RELEASE_ID_RE.fullmatch(release_id):
        raise PayloadError("release_id contains unsupported characters")
    _require_int(payload["sequence"], "sequence", minimum=1)
    _require_string(payload["channel"], "channel")
    if not isinstance(payload["local_qa"], bool):
        raise PayloadError("local_qa must be boolean")

    target = _require_dict(payload["platform"], "platform")
    _require_exact_keys(target, {"os", "arch", "minimum_version"}, "platform")
    if target["os"] != "macos":
        raise PayloadError("only macOS Native payloads are supported")
    if target["arch"] not in {"arm64", "x86_64"}:
        raise PayloadError("unsupported payload architecture")
    _version_tuple(_require_string(target["minimum_version"], "platform.minimum_version"))

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
    seen: set[str] = set()
    total = 0
    for index, raw_entry in enumerate(files):
        entry = _require_dict(raw_entry, f"files[{index}]")
        _require_exact_keys(entry, {"path", "sha256", "size", "mode"}, f"files[{index}]")
        raw_path = _require_string(entry["path"], f"files[{index}].path")
        path = _safe_relative_path(raw_path, label="manifest")
        normalized = path.as_posix().casefold()
        if normalized in seen:
            raise PayloadError(f"case-insensitive path collision: {raw_path}")
        seen.add(normalized)
        if not SHA256_RE.fullmatch(str(entry["sha256"])):
            raise PayloadError(f"invalid file SHA-256: {raw_path}")
        size = _require_int(entry["size"], f"files[{index}].size")
        total += size
        if entry["mode"] not in {0o644, 0o755}:
            raise PayloadError(f"unsupported file mode: {raw_path}")
    if total != unpacked_size:
        raise PayloadError("manifest file sizes do not match artifact.uncompressed_size")


def _verify_ssh_signature(
    manifest_bytes: bytes,
    signature_path: Path,
    allowed_signers_path: Path,
) -> None:
    if not signature_path.is_file() or not allowed_signers_path.is_file():
        raise PayloadError("manifest signature and pinned allowed-signers file are required")
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
    manifest_path = Path(manifest_path)
    artifact_path = Path(artifact_path)
    if not manifest_path.is_file():
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
            raise PayloadError("manifest signature and allowed-signers must be supplied together")
        _verify_ssh_signature(manifest_bytes, Path(signature_path), Path(allowed_signers_path))
    elif allow_unsigned_local_qa:
        if payload["channel"] != "local-qa" or payload["local_qa"] is not True:
            raise PayloadError("unsigned override is only valid for a local QA manifest")
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

    artifact = payload["artifact"]
    if not artifact_path.is_file() or artifact_path.name != artifact["filename"]:
        raise PayloadError("artifact path does not match the manifest filename")
    if artifact_path.stat().st_size != artifact["size"]:
        raise PayloadError("artifact size does not match the manifest")
    if _sha256_file(artifact_path) != artifact["sha256"]:
        raise PayloadError("artifact SHA-256 does not match the manifest")
    return VerifiedCandidate(manifest_path, manifest_bytes, payload)


def _state_root(install_root: Path) -> Path:
    return install_root / "state" / "native-installer"


def _append_journal(install_root: Path, event: str, candidate: VerifiedCandidate) -> None:
    state_root = _state_root(install_root)
    state_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    record = {
        "schema": 1,
        "event": event,
        "releaseId": candidate.release_id,
        "sequence": candidate.sequence,
        "manifestSha256": candidate.manifest_sha256,
    }
    journal_path = state_root / "journal.ndjson"
    encoded = (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    descriptor = os.open(journal_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(descriptor, encoded)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


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


def _validate_zip(candidate: VerifiedCandidate, archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
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
        folded = path.as_posix().casefold()
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


def _apply_manifest_modes(root: Path, manifest_files: dict[str, dict]) -> None:
    for relative_path, entry in manifest_files.items():
        os.chmod(root / relative_path, entry["mode"])


def _make_directories_immutable(root: Path) -> None:
    directories = sorted(
        (path for path in root.rglob("*") if path.is_dir()),
        key=lambda path: len(path.parts),
        reverse=True,
    )
    for directory in directories:
        os.chmod(directory, 0o555)
    os.chmod(root, 0o555)


def stage_candidate(
    candidate: VerifiedCandidate,
    artifact_path: Path,
    install_root: Path,
) -> Path:
    install_root = Path(install_root)
    releases_root = install_root / "releases"
    staging_root = install_root / "staging"
    install_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    releases_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    staging_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    final_path = releases_root / candidate.release_key
    if final_path.exists():
        stored_manifest = final_path / ".viventium-manifest.json"
        if stored_manifest.is_file() and stored_manifest.read_bytes() == candidate.manifest_bytes:
            return final_path
        raise PayloadError("immutable release path already exists with different content")

    attempt = staging_root / f"{candidate.release_key}.{uuid.uuid4().hex}"
    attempt.mkdir(mode=0o700)
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
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                    0o600,
                )
                digest = hashlib.sha256()
                written = 0
                try:
                    with archive.open(info, "r") as source, os.fdopen(descriptor, "wb") as target:
                        descriptor = -1
                        while True:
                            chunk = source.read(1024 * 1024)
                            if not chunk:
                                break
                            written += len(chunk)
                            if written > entry["size"]:
                                raise PayloadError(f"archive expanded beyond declared size: {info.filename}")
                            digest.update(chunk)
                            target.write(chunk)
                        target.flush()
                        os.fsync(target.fileno())
                finally:
                    if descriptor >= 0:
                        os.close(descriptor)
                if written != entry["size"] or digest.hexdigest() != entry["sha256"]:
                    raise PayloadError(f"extracted file digest does not match manifest: {info.filename}")
        (attempt / ".viventium-manifest.json").write_bytes(candidate.manifest_bytes)
        _apply_manifest_modes(attempt, manifest_files)
        os.replace(attempt, final_path)
        _make_directories_immutable(final_path)
        _append_journal(install_root, "stage_complete", candidate)
        return final_path
    except Exception:
        shutil.rmtree(attempt, ignore_errors=True)
        _append_journal(install_root, "stage_failed", candidate)
        raise


@contextlib.contextmanager
def _exclusive_install_lock(install_root: Path) -> Iterator[None]:
    state_root = _state_root(install_root)
    state_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock_path = state_root / "install.lock"
    with lock_path.open("a+b") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise PayloadError("another Native payload transaction is active") from error
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
        raise PayloadError(f"activation pointer escapes releases root: {pointer.name}") from error
    if target.parent != releases_root.resolve() or not target.is_dir():
        raise PayloadError(f"activation pointer target is invalid: {pointer.name}")
    return target


def _atomic_pointer(pointer: Path, target: Path | None) -> None:
    temporary = pointer.parent / f".{pointer.name}-{uuid.uuid4().hex}"
    try:
        if target is None:
            pointer.unlink(missing_ok=True)
            return
        relative_target = os.path.relpath(target, pointer.parent)
        os.symlink(relative_target, temporary)
        os.replace(temporary, pointer)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary_raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_raw)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


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
    expected_release = releases_root / candidate.release_key
    if release_path.resolve() != expected_release.resolve() or not release_path.is_dir():
        raise PayloadError("candidate release path is not the verified immutable release")
    stored_manifest = release_path / ".viventium-manifest.json"
    if not stored_manifest.is_file() or stored_manifest.read_bytes() != candidate.manifest_bytes:
        raise PayloadError("staged release manifest does not match verified candidate")

    with _exclusive_install_lock(install_root):
        state_root = _state_root(install_root)
        sequence_path = state_root / "highest-sequence"
        try:
            highest_sequence = int(sequence_path.read_text(encoding="utf-8").strip())
        except FileNotFoundError:
            highest_sequence = 0
        except ValueError as error:
            raise PayloadError("highest-sequence state is invalid") from error
        if candidate.sequence < highest_sequence:
            raise PayloadError(
                f"manifest sequence {candidate.sequence} is replayed or downgraded from {highest_sequence}"
            )
        if not candidate.data_schema_minimum <= current_data_schema <= candidate.data_schema_maximum:
            raise PayloadError(
                f"data schema {current_data_schema} is incompatible with candidate range "
                f"{candidate.data_schema_minimum}..{candidate.data_schema_maximum}"
            )

        active_pointer = install_root / "active"
        previous_pointer = install_root / "previous"
        prior = _read_pointer(active_pointer, releases_root)
        _append_journal(install_root, "activation_started", candidate)
        _atomic_text(sequence_path, f"{max(highest_sequence, candidate.sequence)}\n")
        if prior is not None:
            _atomic_pointer(previous_pointer, prior)
        _atomic_pointer(active_pointer, release_path)
        _append_journal(install_root, "pointer_switched", candidate)

        healthy = False
        try:
            healthy = bool(health_check(release_path))
        except Exception:
            healthy = False
        if not healthy:
            _atomic_pointer(active_pointer, prior)
            _append_journal(install_root, "health_failed_rollback_complete", candidate)
            raise PayloadError("candidate health check failed; last known-good pointer restored")

        _append_journal(install_root, "health_passed_activation_complete", candidate)
        return release_path

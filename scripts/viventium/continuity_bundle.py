#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import gzip
import hashlib
import json
import os
import re
import secrets
import shutil
import signal
import sqlite3
import stat
import subprocess
import tarfile
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import quote, urlsplit

SCHEMA_VERSION = 1
CONFIG_SCHEMA_VERSION = 1
MARKER_NAME = ".viventium-recoverable"
MARKER_VALUE = "v1"
MANIFEST_NAME = "recoverable-manifest.json"
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_ARTIFACT_BYTES = 64 * 1024 * 1024 * 1024
MAX_TOTAL_ARTIFACT_BYTES = 256 * 1024 * 1024 * 1024
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 256 * 1024 * 1024 * 1024
MAX_TOTAL_ARCHIVE_UNCOMPRESSED_BYTES = 512 * 1024 * 1024 * 1024
MAX_ARCHIVE_EXPANSION_RATIO = 500
MAX_ARCHIVE_MEMBERS = 100_000
MAX_TOTAL_ARCHIVE_MEMBERS = 200_000
MAX_ARCHIVE_PATH_BYTES = 1024
MAX_ARCHIVE_PATH_DEPTH = 32
ARCHIVE_MEMBER_METADATA_BYTES = 4096
MAX_CONFIG_BYTES = 4 * 1024 * 1024
MAX_CHANNEL_JSON_BYTES = 16 * 1024 * 1024
MAX_SCHEDULES_DATABASE_BYTES = 8 * 1024 * 1024 * 1024
MAX_MONGO_COLLECTIONS = 128
MAX_MONGO_DOCUMENTS = 50_000_000
MAX_MONGO_LINE_BYTES = 64 * 1024 * 1024
CONTINUITY_DISK_RESERVE_BYTES = 10 * 1024 * 1024 * 1024
CONTINUITY_TRANSACTION_OVERHEAD_BYTES = 16 * 1024 * 1024
MONGO_CAPTURE_ESTIMATE_MULTIPLIER = 4
MONGO_CLAIM_COLLECTION = "__viventium_restore_claim__"

MONGO_SAFE_COLLECTIONS = (
    "accessroles",
    "aclentries",
    "agents",
    "agentcategories",
    "assistants",
    "balances",
    "banners",
    "bookmarks",
    "conversationtags",
    "conversations",
    "feelingstates",
    "files",
    "groups",
    "memoryentries",
    "messages",
    "permissions",
    "presets",
    "projects",
    "promptgroups",
    "prompts",
    "roles",
    "sharedlinks",
    "transactions",
    "users",
)
MONGO_EXCLUDED_SECRET_COLLECTIONS = (
    "actions",
    "agentapikeys",
    "keys",
    "mcpservers",
    "pluginauths",
    "sessions",
    "tokens",
)
MONGO_USER_FIELDS = (
    "_id",
    "name",
    "username",
    "email",
    "emailVerified",
    "role",
    "provider",
    "avatar",
    "createdAt",
    "updatedAt",
    "viventiumVoiceRoute",
    "viventiumVoiceRouteState",
)
SENSITIVE_YAML_KEY = re.compile(
    r"(?:^|_)(?:api_?key|api_?hash|token|access_?token|refresh_?token|password|credentials?|authorization|cookie|private_?key|signing_?key|secret(?:_value)?|client_?secret|call_?session_?secret)(?:$|_)",
    re.IGNORECASE,
)
SENSITIVE_JSON_KEY = re.compile(
    r"^(?:api_?key|api_?hash|token|service_?token|auth_?token|bearer_?token|access_?token|refresh_?token|password|credentials?|authorization|cookie|set_?cookie|private_?key|signing_?key|secret(?:_value)?|client_?secret|call_?session_?secret)$",
    re.IGNORECASE,
)
SAFE_SECRET_REFERENCE = re.compile(r"^keychain://[A-Za-z0-9._/-]+$")
SAFE_PROFILE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
SAFE_MONGO_DATABASE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
SAFE_TRANSACTION_ID = re.compile(r"^[0-9a-f]{32}$")
YAML_MAPPING_KEY = re.compile(
    r"(?:^\s*(?:-\s*)?|[\{\[,]\s*)(['\"]?)([A-Za-z0-9_.-]+)\1\s*:"
)
YAML_LEADING_MAPPING = re.compile(
    r"^(\s*(?:-\s*)?)(['\"]?)([A-Za-z0-9_.-]+)\2(\s*:\s*)(.*)$"
)

DOMAIN_CONTRACTS: dict[str, set[tuple[str, str]]] = {
    "config": {("captured", "restore")},
    "mongo": {("captured", "restore")},
    "files": {("captured", "restore"), ("empty", "restore")},
    "schedules": {("captured", "restore"), ("empty", "restore")},
    "recall": {("rebuild_required", "rebuild_derived")},
    "auth": {("reauth_required", "reauth_required")},
    "channels": {
        ("captured", "restore"),
        ("empty", "restore"),
        ("reauth_required", "reauth_required"),
    },
}

METADATA_FILES = {
    MARKER_NAME,
    MANIFEST_NAME,
    "continuity-manifest.json",
}

ARTIFACT_CONTRACTS: dict[str, tuple[str, str, str, int]] = {
    "canonical_config": ("config", "application/yaml", "file_copy", 1),
    "mongo_archive": ("mongo", "application/gzip", "mongodump_archive", 1),
    "user_files_archive": ("files", "application/gzip", "archive", 1),
    "schedules_database": ("schedules", "application/vnd.sqlite3", "sqlite_backup", 1),
    "channel_state_archive": ("channels", "application/gzip", "archive", 1),
    "telegram_user_config": ("channels", "application/json", "file_copy", 1),
}


class RestoreTransactionError(RuntimeError):
    pass


class BundleValidationError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


def fail(code: str, detail: str) -> None:
    raise BundleValidationError(code, detail)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def lexical(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path.expanduser())))


def storage_anchor(path: Path) -> Path:
    """Return the closest existing ancestor used for filesystem capacity checks."""
    candidate = lexical(path)
    while not candidate.exists() and not candidate.is_symlink():
        if candidate.parent == candidate:
            break
        candidate = candidate.parent
    validate_path_chain(candidate)
    if not candidate.exists() or candidate.is_symlink():
        raise RestoreTransactionError("Continuity storage destination is unavailable")
    return candidate


def storage_device_id(path: Path) -> int:
    return int(storage_anchor(path).stat().st_dev)


def storage_capacity_plan(entries: list[tuple[Path, int]]) -> dict[int, dict[str, Any]]:
    """Group conservative new-byte requirements by destination filesystem."""
    plan: dict[int, dict[str, Any]] = {}
    for path, raw_bytes in entries:
        if isinstance(raw_bytes, bool) or not isinstance(raw_bytes, int) or raw_bytes < 0:
            raise RestoreTransactionError("Continuity storage estimate is invalid")
        device = storage_device_id(path)
        row = plan.setdefault(
            device,
            {
                "path": lexical(path),
                "payloadBytes": 0,
                "requiredBytes": CONTINUITY_DISK_RESERVE_BYTES,
            },
        )
        row["payloadBytes"] += raw_bytes
        row["requiredBytes"] += raw_bytes
    return plan


def require_storage_capacity(plan: dict[int, dict[str, Any]], operation: str) -> None:
    for device in sorted(plan):
        row = plan[device]
        required = int(row["requiredBytes"])
        path = Path(row["path"])
        if storage_device_id(path) != device:
            raise RestoreTransactionError("Continuity destination filesystem changed during preflight")
        available = int(shutil.disk_usage(storage_anchor(path)).free)
        if available < required:
            raise RestoreTransactionError(
                f"Insufficient disk space for {operation}: "
                f"at least {required} bytes must be free; {available} bytes are available"
            )


def require_storage_floor(path: Path, operation: str) -> None:
    require_storage_capacity(storage_capacity_plan([(path, 0)]), operation)


def validate_path_chain(path: Path, *, require_owner: bool = True) -> None:
    """Reject symlink traversal and non-user-owned existing entries."""
    candidate = lexical(path)
    current = Path(candidate.anchor)
    for part in candidate.parts[1:]:
        current /= part
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(metadata.st_mode):
            raise RestoreTransactionError("Viventium continuity path contains a symlink")
        if current != candidate and not stat.S_ISDIR(metadata.st_mode):
            raise RestoreTransactionError("Viventium continuity parent is not a directory")
        # System ancestors such as /private and /tmp are expected to be
        # root-owned. The selected Viventium endpoint itself must be owned by
        # the invoking user; owned trees are checked entry-by-entry below.
        if require_owner and current == candidate and metadata.st_uid != os.getuid():
            raise RestoreTransactionError("Viventium continuity path is not owned by the current user")


def contained(path: Path, root: Path, label: str) -> Path:
    candidate = lexical(path)
    boundary = lexical(root)
    try:
        candidate.relative_to(boundary)
    except ValueError as error:
        raise RestoreTransactionError(f"{label} escapes its Viventium-owned boundary") from error
    return candidate


def ensure_private_directory(path: Path) -> None:
    missing: list[Path] = []
    current = path
    while not current.exists() and not current.is_symlink():
        missing.append(current)
        if current.parent == current:
            break
        current = current.parent
    validate_path_chain(current)
    for directory in reversed(missing):
        directory.mkdir(mode=0o700)
        directory.chmod(0o700)
    validate_path_chain(path)
    metadata = path.lstat()
    if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.getuid():
        raise RestoreTransactionError("Viventium continuity directory is unsafe")
    path.chmod(0o700)


def write_atomic(path: Path, content: bytes, mode: int = 0o600) -> None:
    ensure_private_directory(path.parent)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        mode,
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        path.chmod(mode)
    finally:
        with contextlib.suppress(FileNotFoundError):
            temporary.unlink()


def write_json_atomic(path: Path, payload: dict[str, Any], mode: int = 0o600) -> None:
    write_atomic(path, (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8"), mode)


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    validate_path_chain(path)
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode):
        raise RestoreTransactionError("Generated runtime environment is unsafe")
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[key.strip()] = value
    return values


def normalize_secret_key(raw: str) -> str:
    """Canonicalize structured keys without guessing from values or prose."""
    normalized = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", str(raw))
    normalized = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", normalized)
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", normalized)
    return normalized.strip("_").lower()


def structured_key_is_sensitive(raw: str) -> bool:
    normalized = normalize_secret_key(raw)
    if SENSITIVE_JSON_KEY.fullmatch(normalized):
        return True
    parts = normalized.split("_") if normalized else []
    pairs = {
        ("api", "key"),
        ("api", "hash"),
        ("service", "token"),
        ("auth", "token"),
        ("bearer", "token"),
        ("access", "token"),
        ("refresh", "token"),
        ("session", "token"),
        ("oauth", "token"),
        ("id", "token"),
        ("set", "cookie"),
        ("private", "key"),
        ("signing", "key"),
        ("client", "secret"),
    }
    return any(tuple(parts[index : index + 2]) in pairs for index in range(len(parts) - 1))


TOOL_PAYLOAD_KEYS = {"tool_call", "tool_calls", "toolcall", "toolcalls"}
TOOL_SECRET_FIELDS = {"args", "arguments", "output", "result", "results"}


def structured_value_is_tool_payload(value: dict[Any, Any]) -> bool:
    value_type = value.get("type")
    normalized_type = normalize_secret_key(value_type) if isinstance(value_type, str) else ""
    normalized_keys = {normalize_secret_key(str(key)) for key in value}
    return normalized_type in TOOL_PAYLOAD_KEYS or bool(normalized_keys & TOOL_PAYLOAD_KEYS)


def sanitize_exported_structured_value(value: Any, *, tool_payload: bool = False) -> Any:
    if isinstance(value, dict):
        current_tool_payload = tool_payload or structured_value_is_tool_payload(value)
        return {
            key: sanitize_exported_structured_value(
                child,
                tool_payload=current_tool_payload
                or normalize_secret_key(str(key)) in TOOL_PAYLOAD_KEYS,
            )
            for key, child in value.items()
            if not structured_key_is_sensitive(str(key))
            and not (
                normalize_secret_key(str(key)) in TOOL_PAYLOAD_KEYS
                or (
                    current_tool_payload
                    and normalize_secret_key(str(key)) in TOOL_SECRET_FIELDS
                )
            )
        }
    if isinstance(value, list):
        return [
            sanitize_exported_structured_value(item, tool_payload=tool_payload)
            for item in value
        ]
    if isinstance(value, str) and value.lstrip().startswith(("{", "[")):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return value
        return json.dumps(
            sanitize_exported_structured_value(decoded, tool_payload=tool_payload),
            sort_keys=True,
            separators=(",", ":"),
        )
    return value


def yaml_secret_keys(raw_line: str) -> list[str]:
    if not raw_line.strip() or raw_line.lstrip().startswith("#"):
        return []
    return [
        match.group(2)
        for match in YAML_MAPPING_KEY.finditer(raw_line)
        if SENSITIVE_YAML_KEY.search(normalize_secret_key(match.group(2)))
    ]


def secret_scalar_is_excluded(raw_value: str) -> bool:
    clean = raw_value.strip()
    if not clean or clean in {"{}", "null", "~", "[]", "''", '""'}:
        return True
    without_comment = re.sub(r"[ \t]+#.*$", "", clean).strip()
    if without_comment in {"{}", "null", "~", "[]", "''", '""'}:
        return True
    return bool(SAFE_SECRET_REFERENCE.fullmatch(without_comment.strip('"\'')))


def redact_canonical_config(source: Path) -> tuple[bytes, list[str]]:
    """Preserve config choices and Keychain refs while removing inline secrets."""
    validate_path_chain(source)
    metadata = source.lstat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_CONFIG_BYTES:
        raise RestoreTransactionError("Canonical config is missing, unsafe, or too large")
    try:
        text = source.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise RestoreTransactionError("Canonical config is not readable UTF-8") from error
    if "\x00" in text:
        raise RestoreTransactionError("Canonical config contains invalid data")
    redacted: list[str] = []
    secret_paths: list[str] = []
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        secret_keys = yaml_secret_keys(raw_line)
        match = YAML_LEADING_MAPPING.match(raw_line)
        if not match:
            if secret_keys:
                raise RestoreTransactionError("Canonical config contains an unsupported inline secret layout")
            redacted.append(raw_line)
            continue
        prefix, quote, key, separator, value = match.groups()
        normalized = normalize_secret_key(key)
        is_secret = bool(SENSITIVE_YAML_KEY.search(normalized))
        if not is_secret:
            if secret_keys:
                raise RestoreTransactionError("Canonical config contains an unsupported inline secret layout")
            redacted.append(raw_line)
            continue
        if len(secret_keys) != 1 or secret_keys[0] != key:
            raise RestoreTransactionError("Canonical config contains an unsupported inline secret layout")
        clean = value.strip()
        if SAFE_SECRET_REFERENCE.fullmatch(clean.strip('"\'')):
            redacted.append(raw_line)
            continue
        if secret_scalar_is_excluded(clean):
            redacted.append(raw_line)
            continue
        if clean.startswith(("|", ">")):
            raise RestoreTransactionError("Canonical config contains an unsupported multiline secret")
        comment = "  # restore requires reauthentication"
        redacted.append(f"{prefix}{quote}{key}{quote}{separator}null{comment}")
        secret_paths.append(f"line:{line_number}:{key}")
    rendered = ("\n".join(redacted) + "\n").encode("utf-8")
    if len(rendered) > MAX_CONFIG_BYTES:
        raise RestoreTransactionError("Sanitized canonical config is too large")
    return rendered, secret_paths


def validate_sanitized_config(path: Path) -> int:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise RestoreTransactionError("Sanitized canonical config is unreadable") from error
    redacted_markers = 0
    for raw_line in text.splitlines():
        secret_keys = yaml_secret_keys(raw_line)
        if not secret_keys:
            continue
        match = YAML_LEADING_MAPPING.match(raw_line)
        if match is None or len(secret_keys) != 1 or secret_keys[0] != match.group(3):
            raise RestoreTransactionError("Sanitized canonical config contains an unsupported secret layout")
        if not secret_scalar_is_excluded(match.group(5)):
            raise RestoreTransactionError("Sanitized canonical config contains an inline authentication secret")
        if "# restore requires reauthentication" in match.group(5):
            redacted_markers += 1
    return redacted_markers


def require_regular_owned(path: Path, label: str) -> None:
    validate_path_chain(path)
    metadata = path.lstat()
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or stat.S_ISLNK(metadata.st_mode)
        or metadata.st_nlink != 1
    ):
        raise RestoreTransactionError(f"{label} is not a safe current-user regular file")


def validated_archive_path(name: str) -> PurePosixPath:
    relative = PurePosixPath(name)
    if (
        relative.is_absolute()
        or name != relative.as_posix()
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        raise RestoreTransactionError("Continuity archive contains an unsafe path")
    try:
        encoded = name.encode("utf-8")
    except UnicodeEncodeError as error:
        raise RestoreTransactionError("Continuity archive path is not valid UTF-8") from error
    if len(encoded) > MAX_ARCHIVE_PATH_BYTES:
        raise RestoreTransactionError("Continuity archive path byte length exceeds the restore bound")
    if len(relative.parts) > MAX_ARCHIVE_PATH_DEPTH:
        raise RestoreTransactionError("Continuity archive path depth exceeds the restore bound")
    return relative


def safe_tree_files(root: Path, *, archive_limits: bool = False) -> list[Path]:
    if not root.exists():
        return []
    validate_path_chain(root)
    metadata = root.lstat()
    if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.getuid():
        raise RestoreTransactionError("Continuity source directory is unsafe")
    files: list[Path] = []
    for current, directories, filenames in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        current_metadata = current_path.lstat()
        if stat.S_ISLNK(current_metadata.st_mode) or current_metadata.st_uid != os.getuid():
            raise RestoreTransactionError("Continuity source tree contains an unsafe directory")
        for name in [*directories, *filenames]:
            child = current_path / name
            child_metadata = child.lstat()
            if stat.S_ISLNK(child_metadata.st_mode) or child_metadata.st_uid != os.getuid():
                raise RestoreTransactionError("Continuity source tree contains a symlink or foreign entry")
        for name in filenames:
            child = current_path / name
            child_metadata = child.lstat()
            if not stat.S_ISREG(child_metadata.st_mode) or child_metadata.st_nlink != 1:
                raise RestoreTransactionError("Continuity source tree contains a special or hard-linked file")
            if archive_limits:
                if len(files) >= MAX_ARCHIVE_MEMBERS:
                    raise RestoreTransactionError(
                        "Continuity archive member count exceeds the capture bound"
                    )
                validated_archive_path(child.relative_to(root).as_posix())
            files.append(child)
    return sorted(files, key=lambda item: item.relative_to(root).as_posix())


def archive_capture_size_estimate(root: Path) -> int:
    """Conservatively bound the streamed tar+gzip output for a safe source tree."""
    tar_bytes = 1024
    for path in safe_tree_files(root, archive_limits=True):
        size = path.lstat().st_size
        # The writer constructs minimal TarInfo records, but PAX may still
        # need path metadata. Eight KiB per entry safely covers those headers
        # and padding on top of the rounded file body.
        tar_bytes += 8192 + ((size + 511) // 512) * 512
    # RFC 1951 stored-block overhead is bounded by five bytes per 16 KiB,
    # plus a small gzip header/trailer allowance.
    return tar_bytes + ((tar_bytes + 16_383) // 16_384) * 5 + 64


def capture_mongo_size_estimate(
    runtime: dict[str, str],
    app_support: Path,
    profile: str,
) -> int:
    """Use owned Mongo storage as a conservative logical-export working estimate when available."""
    explicit = runtime.get("VIVENTIUM_LOCAL_MONGO_DATA_PATH", "").strip()
    candidates = (
        [lexical(Path(explicit))]
        if explicit
        else [
            app_support / "state" / "runtime" / profile / "mongo-data",
            app_support / "state" / "mongo-data",
        ]
    )
    for candidate in candidates:
        if not candidate.is_dir():
            continue
        files = safe_tree_files(candidate)
        source_bytes = sum(path.lstat().st_size for path in files)
        return source_bytes * MONGO_CAPTURE_ESTIMATE_MULTIPLIER
    return 0


def capture_storage_capacity_plan(
    *,
    output_root: Path,
    sanitized_config_bytes: int,
    source_uploads: Path,
    schedule_path: Path,
    runtime: dict[str, str],
    app_support: Path,
    profile: str,
    mongo_logical_source_bytes: int = 0,
) -> dict[int, dict[str, Any]]:
    if (
        isinstance(mongo_logical_source_bytes, bool)
        or not isinstance(mongo_logical_source_bytes, int)
        or mongo_logical_source_bytes < 0
        or mongo_logical_source_bytes > MAX_TOTAL_ARTIFACT_BYTES
    ):
        raise RestoreTransactionError("Mongo storage estimate is invalid")
    estimated_bytes = CONTINUITY_TRANSACTION_OVERHEAD_BYTES + sanitized_config_bytes
    if source_uploads.is_dir():
        estimated_bytes += archive_capture_size_estimate(source_uploads)
    if schedule_path.is_file():
        require_regular_owned(schedule_path, "Schedule database")
        estimated_bytes += schedule_path.lstat().st_size
    estimated_bytes += max(
        capture_mongo_size_estimate(runtime, app_support, profile),
        mongo_logical_source_bytes * MONGO_CAPTURE_ESTIMATE_MULTIPLIER,
    )
    return storage_capacity_plan([(output_root, estimated_bytes)])


def archive_tree(source: Path, destination: Path) -> tuple[int, int]:
    files = safe_tree_files(source, archive_limits=True)
    ensure_private_directory(destination.parent)
    total_bytes = 0
    with tarfile.open(destination, "w:gz", format=tarfile.PAX_FORMAT, dereference=False) as archive:
        for path in files:
            relative = path.relative_to(source)
            before = path.lstat()
            descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            opened = os.fstat(descriptor)
            if (
                not stat.S_ISREG(opened.st_mode)
                or opened.st_uid != os.getuid()
                or opened.st_nlink != 1
                or (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino)
            ):
                os.close(descriptor)
                raise RestoreTransactionError("Continuity source changed during no-follow capture")
            info = tarfile.TarInfo(relative.as_posix())
            info.size = opened.st_size
            info.mode = stat.S_IMODE(opened.st_mode)
            info.mtime = int(opened.st_mtime)
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            total_bytes += opened.st_size
            with os.fdopen(descriptor, "rb") as handle:
                archive.addfile(info, handle)
    destination.chmod(0o600)
    return len(files), total_bytes


def sqlite_backup(source: Path, destination: Path) -> tuple[int, int]:
    require_regular_owned(source, "Schedule database")
    ensure_private_directory(destination.parent)
    try:
        source_connection = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
        destination_connection = sqlite3.connect(destination)
        source_connection.backup(destination_connection)
        result = destination_connection.execute("PRAGMA quick_check").fetchone()
        tables = int(
            destination_connection.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            ).fetchone()[0]
        )
        task_count = 0
        if destination_connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='scheduled_tasks'"
        ).fetchone()[0]:
            task_count = int(destination_connection.execute("SELECT COUNT(*) FROM scheduled_tasks").fetchone()[0])
    except sqlite3.Error as error:
        raise RestoreTransactionError("Schedule database backup failed integrity validation") from error
    finally:
        with contextlib.suppress(Exception):
            source_connection.close()
        with contextlib.suppress(Exception):
            destination_connection.close()
    if not result or result[0] != "ok":
        raise RestoreTransactionError("Schedule database backup failed integrity validation")
    destination.chmod(0o600)
    return tables, task_count


def local_mongo_uri(runtime: dict[str, str]) -> tuple[str, str]:
    port = runtime.get("VIVENTIUM_LOCAL_MONGO_PORT", "27117").strip()
    database = runtime.get("VIVENTIUM_LOCAL_MONGO_DB", "LibreChatViventium").strip()
    if not port.isdigit() or not (1 <= int(port) <= 65535) or not SAFE_MONGO_DATABASE.fullmatch(database):
        raise RestoreTransactionError("Generated local Mongo selection is unsafe")
    return f"mongodb://127.0.0.1:{port}/{database}", database


def validate_local_mongo_uri(uri: str) -> tuple[str, int]:
    parsed = urlsplit(uri)
    if (
        parsed.scheme != "mongodb"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.query
        or parsed.fragment
    ):
        raise RestoreTransactionError("Continuity Mongo adapter accepts only credential-free loopback URIs")
    database = parsed.path.lstrip("/")
    if not SAFE_MONGO_DATABASE.fullmatch(database):
        raise RestoreTransactionError("Continuity Mongo database selection is unsafe")
    try:
        port = parsed.port or 27017
    except ValueError as error:
        raise RestoreTransactionError("Continuity Mongo port is unsafe") from error
    if not 1 <= port <= 65535:
        raise RestoreTransactionError("Continuity Mongo port is unsafe")
    return database, port


def validate_target_mongo_data_path(path: Path, boundaries: tuple[Path, ...]) -> Path:
    candidate = lexical(path)
    validate_path_chain(candidate, require_owner=True)
    metadata = candidate.lstat()
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or metadata.st_mode & 0o077
    ):
        raise RestoreTransactionError(
            "Independent target Mongo data path must be an owner-only directory."
        )
    for boundary in boundaries:
        try:
            common = os.path.commonpath([str(candidate), str(boundary)])
        except ValueError as error:
            raise RestoreTransactionError(
                "Independent target Mongo data path cannot be compared safely."
            ) from error
        if common in {str(candidate), str(boundary)}:
            raise RestoreTransactionError(
                "Independent target Mongo data path overlaps another restore boundary."
            )
    return candidate


def run_checked(
    command: list[str],
    *,
    env: dict[str, str] | None = None,
    timeout: float = 1800.0,
) -> subprocess.CompletedProcess[str]:
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    try:
        stdout, stderr = process.communicate(timeout=max(1.0, min(float(timeout), 1800.0)))
    except subprocess.TimeoutExpired as error:
        with contextlib.suppress(ProcessLookupError):
            process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(ProcessLookupError):
                process.kill()
            process.wait()
        raise RestoreTransactionError("Continuity data-plane adapter timed out") from error
    except BaseException:
        with contextlib.suppress(ProcessLookupError):
            process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(ProcessLookupError):
                process.kill()
            process.wait()
        raise
    completed = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    if completed.returncode != 0:
        raise RestoreTransactionError("Continuity data-plane adapter failed")
    return completed


def mongo_collection_names(uri: str) -> set[str]:
    mongosh = shutil.which("mongosh")
    if not mongosh:
        raise RestoreTransactionError("mongosh is required for a complete logical Mongo snapshot")
    script = "EJSON.stringify(db.getCollectionNames().sort())"
    output = run_checked([mongosh, uri, "--quiet", "--norc", "--eval", script]).stdout.strip()
    try:
        parsed = json.loads(output.splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as error:
        raise RestoreTransactionError("Mongo collection inventory was unreadable") from error
    if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
        raise RestoreTransactionError("Mongo collection inventory was invalid")
    return set(parsed)


def node_mongo_adapter(repo_root: Path) -> tuple[str, Path] | None:
    adapter = Path(__file__).with_name("continuity_mongo.cjs")
    source_package = repo_root / "viventium_v0_4" / "LibreChat" / "package.json"
    source_modules = repo_root / "viventium_v0_4" / "LibreChat" / "node_modules"
    source_node = shutil.which("node")
    native_package = repo_root / "runtime" / "librechat" / "package.json"
    native_modules = repo_root / "runtime" / "librechat" / "node_modules"
    native_node = repo_root / "runtime" / "node" / "bin" / "node"
    if source_node and adapter.is_file() and source_package.is_file() and source_modules.is_dir():
        return source_node, adapter
    if (
        native_node.is_file()
        and os.access(native_node, os.X_OK)
        and adapter.is_file()
        and native_package.is_file()
        and native_modules.is_dir()
    ):
        return str(native_node), adapter
    return None


def run_node_mongo_adapter(
    repo_root: Path,
    command: str,
    uri: str,
    *,
    directory_flag: str | None = None,
    directory: Path | None = None,
    transaction_id: str | None = None,
    socket_path: Path | None = None,
) -> dict[str, Any]:
    selected = node_mongo_adapter(repo_root)
    if selected is None:
        raise RestoreTransactionError("Installed Node Mongo adapter is unavailable")
    node, adapter = selected
    argv = [
        node,
        str(adapter),
        command,
        "--repo-root",
        str(repo_root),
        "--uri",
        uri,
    ]
    if directory_flag and directory is not None:
        argv.extend([directory_flag, str(directory)])
    if transaction_id is not None:
        if not SAFE_TRANSACTION_ID.fullmatch(transaction_id):
            raise RestoreTransactionError("Restore transaction identifier is unsafe")
        argv.extend(["--transaction-id", transaction_id])
    if socket_path is not None:
        argv.extend(["--socket-path", str(socket_path)])
    completed = run_checked(argv)
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise RestoreTransactionError("Installed Node Mongo adapter returned unreadable status") from error
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        raise RestoreTransactionError("Installed Node Mongo adapter returned invalid status")
    return payload


def mongo_logical_source_size(
    uri: str,
    repo_root: Path,
    *,
    mongo_socket: Path | None = None,
) -> int:
    """Estimate allowlisted logical Mongo bytes before creating a capture attempt."""
    if mongo_socket is None:
        validate_local_mongo_uri(uri)
    elif uri != native_mongo_uri(mongo_socket):
        raise RestoreTransactionError("Native continuity Mongo socket binding is inconsistent")
    if node_mongo_adapter(repo_root) is not None:
        payload = run_node_mongo_adapter(
            repo_root,
            "estimate",
            uri,
            socket_path=mongo_socket,
        )
        estimated = payload.get("estimatedBytes")
    else:
        mongosh = shutil.which("mongosh")
        if not mongosh:
            return 0
        script = (
            "(() => { const allowed = "
            + json.dumps(list(MONGO_SAFE_COLLECTIONS))
            + "; const present = new Set(db.getCollectionNames()); let estimatedBytes = 0; "
            "for (const name of allowed) { if (!present.has(name)) continue; "
            "const stats = db.runCommand({collStats:name,scale:1}); "
            "const size = Number(stats.size); "
            "if (stats.ok !== 1 || !Number.isSafeInteger(size) || size < 0) "
            "throw new Error('invalid logical collection estimate'); estimatedBytes += size; "
            "if (!Number.isSafeInteger(estimatedBytes)) throw new Error('invalid logical database estimate'); } "
            "return EJSON.stringify({estimatedBytes}); })()"
        )
        output = run_checked([mongosh, uri, "--quiet", "--norc", "--eval", script]).stdout.strip()
        try:
            parsed = json.loads(output.splitlines()[-1])
        except (IndexError, json.JSONDecodeError) as error:
            raise RestoreTransactionError("Mongo storage estimate is invalid") from error
        estimated = parsed.get("estimatedBytes") if isinstance(parsed, dict) else None
    if (
        isinstance(estimated, bool)
        or not isinstance(estimated, int)
        or estimated < 0
        or estimated > MAX_TOTAL_ARTIFACT_BYTES
    ):
        raise RestoreTransactionError("Mongo storage estimate is invalid")
    return estimated


def native_mongo_uri(socket_path: Path, database: str = "LibreChat") -> str:
    if not socket_path.is_absolute() or not SAFE_MONGO_DATABASE.fullmatch(database):
        raise RestoreTransactionError("Native continuity Mongo selection is unsafe")
    return f"mongodb://{quote(str(socket_path), safe='')}/{database}"


def capture_mongo_logical(
    uri: str,
    destination: Path,
    repo_root: Path,
    *,
    mongo_socket: Path | None = None,
) -> list[dict[str, Any]]:
    if mongo_socket is None:
        validate_local_mongo_uri(uri)
    elif uri != native_mongo_uri(mongo_socket):
        raise RestoreTransactionError("Native continuity Mongo socket binding is inconsistent")
    ensure_private_directory(destination.parent)
    with tempfile.TemporaryDirectory(
        prefix=".viventium-mongo-export-",
        dir=destination.parent,
    ) as temporary:
        root = Path(temporary)
        if node_mongo_adapter(repo_root) is not None:
            payload = run_node_mongo_adapter(
                repo_root,
                "export",
                uri,
                directory_flag="--output-dir",
                directory=root,
                socket_path=mongo_socket,
            )
            ledger = payload.get("collections")
            if not isinstance(ledger, list):
                raise RestoreTransactionError("Installed Node Mongo adapter returned an invalid ledger")
            validate_mongo_logical_directory(root, ledger)
            archive_tree(root, destination)
            return ledger

        mongoexport = shutil.which("mongoexport")
        if not mongoexport:
            raise RestoreTransactionError(
                "Complete logical Mongo capture needs installed LibreChat dependencies or mongoexport"
            )
        present = mongo_collection_names(uri)
        ledger: list[dict[str, Any]] = []
        for collection in MONGO_SAFE_COLLECTIONS:
            if collection not in present:
                continue
            output = root / f"{len(ledger):03d}.jsonl"
            command = [
                mongoexport,
                "--uri",
                uri,
                "--collection",
                collection,
                "--out",
                str(output),
                "--jsonFormat",
                "canonical",
            ]
            if collection == "users":
                command.extend(["--fields", ",".join(MONGO_USER_FIELDS)])
            run_checked(command)
            require_regular_owned(output, "Logical Mongo collection export")
            count = 0
            sanitized_output = output.with_name(f".{output.name}.sanitized")
            with output.open("rb") as handle, sanitized_output.open("xb") as sanitized_handle:
                os.chmod(sanitized_output, 0o600)
                for line in handle:
                    if len(line) > MAX_MONGO_LINE_BYTES:
                        raise RestoreTransactionError("Logical Mongo document exceeds the restore bound")
                    if line.strip():
                        try:
                            payload = json.loads(line)
                        except json.JSONDecodeError as error:
                            raise RestoreTransactionError("Logical Mongo export contains invalid JSON") from error
                        if not isinstance(payload, dict):
                            raise RestoreTransactionError("Logical Mongo export contains a non-object document")
                        rendered = (
                            json.dumps(
                                sanitize_exported_structured_value(payload),
                                sort_keys=True,
                                separators=(",", ":"),
                            )
                            + "\n"
                        ).encode("utf-8")
                        if len(rendered) > MAX_MONGO_LINE_BYTES:
                            raise RestoreTransactionError("Sanitized Mongo document exceeds the restore bound")
                        sanitized_handle.write(rendered)
                        count += 1
                sanitized_handle.flush()
                os.fsync(sanitized_handle.fileno())
            os.replace(sanitized_output, output)
            ledger.append(
                {
                    "name": collection,
                    "path": output.name,
                    "documents": count,
                    "sha256": sha256_file(output),
                }
            )
        if len(ledger) > MAX_MONGO_COLLECTIONS or sum(item["documents"] for item in ledger) > MAX_MONGO_DOCUMENTS:
            raise RestoreTransactionError("Logical Mongo export exceeds the restore bound")
        write_json_atomic(root / "index.json", {"schemaVersion": 1, "collections": ledger})
        archive_tree(root, destination)
    return ledger


def validate_mongo_logical_directory(root: Path, ledger: list[dict[str, Any]]) -> None:
    index_path = root / "index.json"
    require_regular_owned(index_path, "Logical Mongo index")
    try:
        index_payload = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RestoreTransactionError("Logical Mongo index is invalid") from error
    if index_payload != {"schemaVersion": 1, "collections": ledger}:
        raise RestoreTransactionError("Logical Mongo index does not match the adapter ledger")
    expected = {"index.json"}
    for entry in ledger:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise RestoreTransactionError("Logical Mongo adapter ledger is invalid")
        expected.add(entry["path"])
    observed = {
        path.relative_to(root).as_posix()
        for path in safe_tree_files(root, archive_limits=True)
    }
    if observed != expected:
        raise RestoreTransactionError("Logical Mongo adapter emitted undeclared files")


def safe_tar_members_from_archive(
    archive: tarfile.TarFile,
    *,
    expected_members: int | None = None,
) -> list[tarfile.TarInfo]:
    if expected_members is not None and (
        isinstance(expected_members, bool)
        or not isinstance(expected_members, int)
        or expected_members < 0
        or expected_members > MAX_ARCHIVE_MEMBERS
    ):
        raise RestoreTransactionError(
            "Continuity archive declared member count exceeds the restore bound"
        )
    members: list[tarfile.TarInfo] = []
    seen: set[str] = set()
    seen_casefold: set[str] = set()
    for member in archive:
        if len(members) >= MAX_ARCHIVE_MEMBERS:
            raise RestoreTransactionError(
                "Continuity archive member count exceeds the restore bound"
            )
        validated_archive_path(member.name)
        folded = member.name.casefold()
        if member.name in seen or folded in seen_casefold:
            raise RestoreTransactionError("Continuity archive contains a colliding path")
        seen.add(member.name)
        seen_casefold.add(folded)
        if not member.isfile():
            raise RestoreTransactionError("Continuity archive contains a non-regular entry")
        if member.size > MAX_ARTIFACT_BYTES:
            raise RestoreTransactionError("Continuity archive member exceeds the restore bound")
        members.append(member)
    if expected_members is not None and len(members) != expected_members:
        raise RestoreTransactionError(
            "Continuity archive member count does not match the manifest"
        )
    return members


def safe_tar_members(
    path: Path,
    *,
    expected_members: int | None = None,
) -> list[tarfile.TarInfo]:
    try:
        archive = tarfile.open(path, "r:gz")
    except (tarfile.TarError, OSError) as error:
        raise RestoreTransactionError("Continuity archive is not a readable gzip tar") from error
    with archive:
        return safe_tar_members_from_archive(
            archive,
            expected_members=expected_members,
        )


def validate_mongo_logical_archive(path: Path, expected: list[dict[str, Any]]) -> int:
    if len(expected) > MAX_MONGO_COLLECTIONS:
        raise RestoreTransactionError("Logical Mongo collection ledger exceeds the restore bound")
    names: set[str] = set()
    expected_files = {"index.json"}
    total_documents = 0
    for entry in expected:
        if not isinstance(entry, dict):
            raise RestoreTransactionError("Logical Mongo collection ledger is invalid")
        name = entry.get("name")
        relative = entry.get("path")
        documents = entry.get("documents")
        checksum = entry.get("sha256")
        if (
            name not in MONGO_SAFE_COLLECTIONS
            or name in names
            or not isinstance(relative, str)
            or not re.fullmatch(r"[0-9]{3}[.]jsonl", relative)
            or not isinstance(documents, int)
            or isinstance(documents, bool)
            or documents < 0
            or not isinstance(checksum, str)
            or not re.fullmatch(r"[0-9a-f]{64}", checksum)
        ):
            raise RestoreTransactionError("Logical Mongo collection ledger is invalid")
        names.add(name)
        expected_files.add(relative)
        total_documents += documents
    if total_documents > MAX_MONGO_DOCUMENTS:
        raise RestoreTransactionError("Logical Mongo document ledger exceeds the restore bound")
    try:
        archive = tarfile.open(path, "r:gz")
    except (tarfile.TarError, OSError) as error:
        raise RestoreTransactionError("Logical Mongo archive is unreadable") from error
    with archive:
        members = safe_tar_members_from_archive(
            archive,
            expected_members=len(expected) + 1,
        )
        if {item.name for item in members} != expected_files:
            raise RestoreTransactionError("Logical Mongo archive files do not match the manifest")
        index_file = archive.extractfile("index.json")
        if index_file is None:
            raise RestoreTransactionError("Logical Mongo archive index is missing")
        try:
            index_payload = json.loads(index_file.read(MAX_MANIFEST_BYTES + 1))
        except json.JSONDecodeError as error:
            raise RestoreTransactionError("Logical Mongo archive index is invalid") from error
        if index_payload != {"schemaVersion": 1, "collections": expected}:
            raise RestoreTransactionError("Logical Mongo archive index does not match the manifest")
        for entry in expected:
            extracted = archive.extractfile(entry["path"])
            if extracted is None:
                raise RestoreTransactionError("Logical Mongo collection export is missing")
            digest = hashlib.sha256()
            count = 0
            for line in extracted:
                if len(line) > MAX_MONGO_LINE_BYTES:
                    raise RestoreTransactionError("Logical Mongo document exceeds the restore bound")
                digest.update(line)
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as error:
                    raise RestoreTransactionError("Logical Mongo collection contains invalid JSON") from error
                if not isinstance(payload, dict):
                    raise RestoreTransactionError("Logical Mongo collection contains a non-object document")
                if json_contains_exported_secret(payload):
                    raise RestoreTransactionError("Logical Mongo collection contains an exported authentication secret")
                count += 1
            if count != entry["documents"] or digest.hexdigest() != entry["sha256"]:
                raise RestoreTransactionError("Logical Mongo collection content does not match the manifest")
    return len(members)


def json_contains_exported_secret(value: Any, *, tool_payload: bool = False) -> bool:
    if isinstance(value, dict):
        current_tool_payload = tool_payload or structured_value_is_tool_payload(value)
        for key, child in value.items():
            normalized_key = normalize_secret_key(str(key))
            if structured_key_is_sensitive(str(key)) or normalized_key in TOOL_PAYLOAD_KEYS:
                empty = child is None or child == "" or child == [] or child == {}
                if not empty:
                    return True
            if current_tool_payload and normalized_key in TOOL_SECRET_FIELDS:
                empty = child is None or child == "" or child == [] or child == {}
                if not empty:
                    return True
            if json_contains_exported_secret(
                child,
                tool_payload=current_tool_payload or normalized_key in TOOL_PAYLOAD_KEYS,
            ):
                return True
    elif isinstance(value, list):
        return any(
            json_contains_exported_secret(item, tool_payload=tool_payload)
            for item in value
        )
    elif isinstance(value, str) and value.lstrip().startswith(("{", "[")):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return False
        return json_contains_exported_secret(decoded, tool_payload=tool_payload)
    return False


def artifact_record(
    root: Path,
    relative: str,
    domain: str,
    role: str,
    *,
    uncompressed_size: int | None = None,
) -> dict[str, Any]:
    expected_domain, media_type, method, schema_version = ARTIFACT_CONTRACTS[role]
    if domain != expected_domain:
        raise RestoreTransactionError("Continuity artifact domain is inconsistent")
    path = root / relative
    require_regular_owned(path, "Continuity artifact")
    row: dict[str, Any] = {
        "path": relative,
        "domain": domain,
        "role": role,
        "mediaType": media_type,
        "captureMethod": method,
        "schemaVersion": schema_version,
        "size": path.stat().st_size,
        "sha256": sha256_file(path),
    }
    if uncompressed_size is not None:
        row["uncompressedSize"] = uncompressed_size
    return row


def gzip_expanded_size(path: Path) -> int:
    expanded = 0
    with gzip.open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            expanded += len(chunk)
            if expanded > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
                raise RestoreTransactionError("Continuity archive exceeds its expansion bound")
    return expanded


def archive_member_metadata_size(member_count: int) -> int:
    if (
        isinstance(member_count, bool)
        or not isinstance(member_count, int)
        or member_count < 0
        or member_count > MAX_TOTAL_ARCHIVE_MEMBERS
    ):
        raise RestoreTransactionError("Continuity restore archive member metadata is invalid")
    return member_count * ARCHIVE_MEMBER_METADATA_BYTES


def restore_storage_capacity_plan(
    payload: dict[str, Any],
    *,
    target_parent: Path,
    uploads_parent: Path,
    target_mongo_data_path: Path | None,
) -> dict[int, dict[str, Any]]:
    """Plan peak restore bytes without trusting compression to save capacity."""
    artifacts = {item["role"]: item for item in payload["artifacts"]}

    def artifact_size(role: str, *, expanded: bool = False) -> int:
        row = artifacts.get(role)
        if row is None:
            return 0
        value = row.get("uncompressedSize") if expanded else row.get("size")
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise RestoreTransactionError("Continuity restore storage metadata is invalid")
        return value

    mongo_bytes = artifact_size("mongo_archive") + artifact_size(
        "mongo_archive", expanded=True
    )
    inventory = payload.get("inventory")
    if not isinstance(inventory, dict):
        raise RestoreTransactionError("Continuity restore inventory metadata is invalid")
    mongo_collections = inventory.get("mongoCollections")
    file_inventory = inventory.get("files")
    if not isinstance(mongo_collections, list) or not isinstance(file_inventory, dict):
        raise RestoreTransactionError("Continuity restore inventory metadata is invalid")
    mongo_metadata_bytes = archive_member_metadata_size(len(mongo_collections) + 1)
    file_metadata_bytes = archive_member_metadata_size(file_inventory.get("count"))
    target_bytes = (
        CONTINUITY_TRANSACTION_OVERHEAD_BYTES
        + artifact_size("canonical_config")
        + artifact_size("schedules_database")
        + mongo_bytes
        + mongo_metadata_bytes
    )
    if target_mongo_data_path is None:
        # The caller did not expose the database filesystem. Reserve a second
        # conservative Mongo footprint on the App Support filesystem rather
        # than assuming the unseen database volume has unlimited capacity.
        target_bytes += mongo_bytes
    entries: list[tuple[Path, int]] = [(target_parent, target_bytes)]
    if "user_files_archive" in artifacts:
        entries.append(
            (
                uploads_parent,
                artifact_size("user_files_archive")
                + artifact_size("user_files_archive", expanded=True)
                + file_metadata_bytes,
            )
        )
    if target_mongo_data_path is not None:
        # Mongo scratch and the independent database are both live at peak.
        # Count the conservative compressed+expanded footprint on each volume.
        entries.append((target_mongo_data_path, mongo_bytes))
    return storage_capacity_plan(entries)


def capture_bundle(
    *,
    repo_root: Path,
    app_support: Path,
    runtime_dir: Path,
    output_root: Path,
    uploads_dir: Path | None = None,
    mongo_uri: str | None = None,
    mongo_socket: Path | None = None,
    data_schema: int | None = None,
    release_identity: str | None = None,
) -> dict[str, Any]:
    repo_root = lexical(repo_root)
    app_support = lexical(app_support)
    runtime_dir = lexical(runtime_dir)
    output_root = lexical(output_root)
    validate_path_chain(repo_root)
    validate_path_chain(app_support)
    if not app_support.is_dir():
        raise RestoreTransactionError("Viventium App Support is missing")
    contained(runtime_dir, app_support, "Runtime directory")
    if output_root == app_support or app_support not in output_root.parents:
        raise RestoreTransactionError("Snapshot output root must be inside Viventium App Support")
    ensure_private_directory(output_root)
    runtime_env = parse_env(runtime_dir / "runtime.env")
    profile = runtime_env.get("VIVENTIUM_RUNTIME_PROFILE", "isolated").strip() or "isolated"
    if not SAFE_PROFILE.fullmatch(profile):
        raise RestoreTransactionError("Runtime profile selection is unsafe")
    source_config = app_support / "config.yaml"
    sanitized_config, redacted_config_fields = redact_canonical_config(source_config)
    default_schedule = app_support / "state" / "runtime" / profile / "scheduling" / "schedules.db"
    schedule_path = lexical(Path(runtime_env.get("SCHEDULING_DB_PATH") or default_schedule))
    contained(schedule_path, app_support, "Schedule database")
    source_uploads = lexical(
        uploads_dir if uploads_dir is not None else repo_root / "viventium_v0_4" / "LibreChat" / "uploads"
    )
    if uploads_dir is None:
        contained(source_uploads, repo_root, "LibreChat uploads")
    else:
        try:
            contained(source_uploads, repo_root, "LibreChat uploads")
        except RestoreTransactionError:
            contained(source_uploads, app_support, "LibreChat uploads")

    if mongo_socket is not None:
        mongo_socket = lexical(mongo_socket)
        contained(mongo_socket, runtime_dir, "Native Mongo socket")
        expected_uri = native_mongo_uri(mongo_socket)
        if mongo_uri != expected_uri:
            raise RestoreTransactionError("Native continuity Mongo socket binding is inconsistent")
        uri, source_database = expected_uri, "LibreChat"
    elif mongo_uri is None:
        uri, source_database = local_mongo_uri(runtime_env)
    else:
        source_database, _port = validate_local_mongo_uri(mongo_uri)
        uri = mongo_uri

    base_capacity_plan = capture_storage_capacity_plan(
        output_root=output_root,
        sanitized_config_bytes=len(sanitized_config),
        source_uploads=source_uploads,
        schedule_path=schedule_path,
        runtime=runtime_env,
        app_support=app_support,
        profile=profile,
    )
    require_storage_capacity(base_capacity_plan, "continuity capture")
    mongo_source_bytes = mongo_logical_source_size(
        uri,
        repo_root,
        mongo_socket=mongo_socket,
    )
    if mongo_source_bytes:
        require_storage_capacity(
            capture_storage_capacity_plan(
                output_root=output_root,
                sanitized_config_bytes=len(sanitized_config),
                source_uploads=source_uploads,
                schedule_path=schedule_path,
                runtime=runtime_env,
                app_support=app_support,
                profile=profile,
                mongo_logical_source_bytes=mongo_source_bytes,
            ),
            "continuity capture",
        )

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    snapshot = output_root / f"{timestamp}-complete-{uuid.uuid4().hex[:8]}"
    snapshot.mkdir(mode=0o700)
    incomplete = snapshot / ".viventium-incomplete"
    write_atomic(incomplete, b"capture-in-progress\n")
    try:
        config_target = snapshot / "config" / "config.yaml"
        write_atomic(config_target, sanitized_config)
        require_storage_floor(output_root, "continuity capture")
        mongo_target = snapshot / "mongo" / "logical-export.tar.gz"
        ensure_private_directory(mongo_target.parent)
        mongo_collections = capture_mongo_logical(
            uri,
            mongo_target,
            repo_root,
            mongo_socket=mongo_socket,
        )
        require_storage_floor(output_root, "continuity capture")

        artifacts = [artifact_record(snapshot, "config/config.yaml", "config", "canonical_config")]
        artifacts.append(
            artifact_record(
                snapshot,
                "mongo/logical-export.tar.gz",
                "mongo",
                "mongo_archive",
                uncompressed_size=gzip_expanded_size(mongo_target),
            )
        )
        file_paths: list[str] = []
        file_count = 0
        file_bytes = 0
        if source_uploads.is_dir() and safe_tree_files(source_uploads, archive_limits=True):
            uploads_target = snapshot / "files" / "librechat-uploads.tar.gz"
            file_count, file_bytes = archive_tree(source_uploads, uploads_target)
            require_storage_floor(output_root, "continuity capture")
            file_paths = ["files/librechat-uploads.tar.gz"]
            artifacts.append(
                artifact_record(
                    snapshot,
                    file_paths[0],
                    "files",
                    "user_files_archive",
                    uncompressed_size=gzip_expanded_size(uploads_target),
                )
            )

        schedule_paths: list[str] = []
        schedule_tables = 0
        schedule_tasks = 0
        if schedule_path.is_file():
            schedule_target = snapshot / "schedules" / "schedules.db"
            schedule_tables, schedule_tasks = sqlite_backup(schedule_path, schedule_target)
            require_storage_floor(output_root, "continuity capture")
            schedule_paths = ["schedules/schedules.db"]
            artifacts.append(
                artifact_record(snapshot, schedule_paths[0], "schedules", "schedules_database")
            )

        domains = [
            {"name": "config", "status": "captured", "policy": "restore", "artifacts": ["config/config.yaml"]},
            {"name": "mongo", "status": "captured", "policy": "restore", "artifacts": ["mongo/logical-export.tar.gz"]},
            {"name": "files", "status": "captured" if file_paths else "empty", "policy": "restore", "artifacts": file_paths},
            {"name": "schedules", "status": "captured" if schedule_paths else "empty", "policy": "restore", "artifacts": schedule_paths},
            {"name": "recall", "status": "rebuild_required", "policy": "rebuild_derived", "artifacts": []},
            {"name": "auth", "status": "reauth_required", "policy": "reauth_required", "artifacts": []},
            {"name": "channels", "status": "reauth_required", "policy": "reauth_required", "artifacts": []},
        ]
        runtime_selection: dict[str, Any] = {
            "profile": profile,
            "sourceDatabase": source_database,
            "generatedRuntimePolicy": "regenerate_from_canonical_config",
            "helperBindingPolicy": "regenerate_for_target_checkout",
        }
        if profile == "native":
            if (
                isinstance(data_schema, bool)
                or not isinstance(data_schema, int)
                or data_schema < 1
                or not isinstance(release_identity, str)
                or re.fullmatch(r"[0-9a-f]{40}", release_identity) is None
            ):
                raise RestoreTransactionError(
                    "Native snapshot requires a bound data schema and release identity"
                )
            runtime_selection["dataSchema"] = data_schema
            runtime_selection["sourceReleaseIdentity"] = release_identity
        manifest = {
            "schemaVersion": SCHEMA_VERSION,
            "bundleKind": "complete",
            "createdAt": iso_now(),
            "runtimeSelection": runtime_selection,
            "security": {
                "filesystemMode": "owner_only",
                "payloadEncryption": "not_self_encrypted_owner_only",
                "inlineConfigSecrets": "redacted",
                "providerCredentials": "excluded_reauthentication_required",
                "channelCredentials": "excluded_reauthentication_required",
                "mongoExcludedCollections": list(MONGO_EXCLUDED_SECRET_COLLECTIONS),
                "mongoUserAuthFields": "excluded_reauthentication_required",
                "redactedConfigFieldCount": len(redacted_config_fields),
            },
            "inventory": {
                "mongoCollections": mongo_collections,
                "files": {"count": file_count, "bytes": file_bytes},
                "schedules": {"tables": schedule_tables, "tasks": schedule_tasks},
                "recall": {"policy": "rebuild_from_restored_canonical_state"},
            },
            "domains": domains,
            "artifacts": artifacts,
        }
        write_json_atomic(snapshot / MANIFEST_NAME, manifest)
        write_atomic(snapshot / MARKER_NAME, (MARKER_VALUE + "\n").encode("utf-8"))
        incomplete.unlink()
        result = validate_bundle(snapshot)
        if not result["recoverable"]:
            raise RestoreTransactionError("Captured bundle did not pass semantic restore validation")
        return {"snapshotDir": str(snapshot), **result}
    except BaseException:
        with contextlib.suppress(Exception):
            if snapshot.exists():
                shutil.rmtree(snapshot)
        raise


def validate_artifact_content(
    path: Path,
    role: str,
    *,
    declared_uncompressed_size: int | None = None,
) -> None:
    if role == "canonical_config":
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            fail("invalid_config_artifact", "canonical config artifact is not readable UTF-8")
        if "\x00" in text:
            fail("invalid_config_artifact", "canonical config artifact contains invalid data")
        version_rows = [
            match
            for line in text.splitlines()
            if (match := re.fullmatch(r"version:[ \t]+([0-9]+)[ \t]*(?:#.*)?", line))
        ]
        if len(version_rows) != 1 or int(version_rows[0].group(1)) != CONFIG_SCHEMA_VERSION:
            fail("invalid_config_artifact", "canonical config artifact lacks one supported top-level version")
    elif role in {"mongo_archive", "user_files_archive", "channel_state_archive"}:
        if declared_uncompressed_size is None:
            fail("invalid_archive_contract", "archive artifact lacks a declared uncompressed size")
        expanded = 0
        try:
            with gzip.open(path, "rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    expanded += len(chunk)
                    if expanded > declared_uncompressed_size or expanded > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
                        fail("archive_expansion_limit", "archive expansion exceeds its validated limit")
        except (gzip.BadGzipFile, EOFError, OSError):
            fail("invalid_archive_artifact", "archive artifact is not an intact gzip stream")
        if expanded != declared_uncompressed_size:
            fail("archive_size_mismatch", "archive expansion does not match the manifest")
    elif role == "schedules_database":
        try:
            connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            result = connection.execute("PRAGMA quick_check").fetchone()
        except sqlite3.Error:
            fail("invalid_schedules_artifact", "schedule artifact is not a readable SQLite database")
        finally:
            if "connection" in locals():
                connection.close()
        if not result or result[0] != "ok":
            fail("invalid_schedules_artifact", "schedule artifact failed SQLite integrity checking")
    elif role == "telegram_user_config":
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            fail("invalid_channel_artifact", "Telegram channel artifact is not valid JSON")
        if not isinstance(payload, dict):
            fail("invalid_channel_artifact", "Telegram channel artifact must be a JSON object")


def validate_relative_path(raw: Any) -> PurePosixPath:
    if not isinstance(raw, str) or not raw or "\\" in raw or "\x00" in raw:
        fail("invalid_artifact_path", "artifact path must be a non-empty canonical POSIX path")
    path = PurePosixPath(raw)
    if path.is_absolute() or raw != path.as_posix():
        fail("invalid_artifact_path", "artifact path must be relative and canonical")
    if any(part in {"", ".", ".."} for part in path.parts):
        fail("invalid_artifact_path", "artifact path traversal is not allowed")
    if path.parts[0] in METADATA_FILES:
        fail("reserved_artifact_path", "bundle metadata cannot be declared as payload")
    return path


def read_manifest(root: Path) -> dict[str, Any]:
    manifest_path = root / MANIFEST_NAME
    try:
        metadata = manifest_path.lstat()
    except FileNotFoundError:
        fail("missing_manifest", "recoverable manifest is missing")
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        fail("unsafe_manifest", "recoverable manifest must be a regular file")
    if metadata.st_size > MAX_MANIFEST_BYTES:
        fail("manifest_too_large", "recoverable manifest exceeds the size limit")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        fail("invalid_manifest_json", "recoverable manifest is not valid UTF-8 JSON")
    if not isinstance(payload, dict):
        fail("invalid_manifest", "recoverable manifest must be a JSON object")
    return payload


def validate_marker(root: Path) -> None:
    marker = root / MARKER_NAME
    try:
        metadata = marker.lstat()
    except FileNotFoundError:
        fail("missing_recoverable_marker", "positive producer completeness marker is missing")
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        fail("unsafe_recoverable_marker", "recoverable marker must be a regular file")
    try:
        value = marker.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        fail("invalid_recoverable_marker", "recoverable marker is unreadable")
    if value != MARKER_VALUE:
        fail("invalid_recoverable_marker", "recoverable marker version is unsupported")


def validate_domains(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw_domains = payload.get("domains")
    if not isinstance(raw_domains, list):
        fail("invalid_domains", "domains must be an array")
    domains: dict[str, dict[str, Any]] = {}
    for raw_domain in raw_domains:
        if not isinstance(raw_domain, dict):
            fail("invalid_domain", "every domain must be an object")
        name = raw_domain.get("name")
        status_value = raw_domain.get("status")
        policy = raw_domain.get("policy")
        artifact_paths = raw_domain.get("artifacts")
        if not isinstance(name, str) or name not in DOMAIN_CONTRACTS:
            fail("unknown_domain", "manifest contains an unknown continuity domain")
        if name in domains:
            fail("duplicate_domain", "manifest contains a duplicate continuity domain")
        if (status_value, policy) not in DOMAIN_CONTRACTS[name]:
            fail("invalid_domain_contract", "domain status and restore policy do not match the schema")
        if not isinstance(artifact_paths, list) or not all(isinstance(item, str) for item in artifact_paths):
            fail("invalid_domain_artifacts", "domain artifact references must be a string array")
        if len(artifact_paths) != len(set(artifact_paths)):
            fail("duplicate_domain_artifact", "domain contains duplicate artifact references")
        if status_value == "captured" and not artifact_paths:
            fail("missing_required_artifact", "captured domain has no artifact")
        if status_value in {"empty", "rebuild_required", "reauth_required"} and artifact_paths:
            fail("unexpected_domain_artifact", "non-payload domain must not declare artifacts")
        domains[name] = raw_domain
    if set(domains) != set(DOMAIN_CONTRACTS):
        fail("incomplete_domains", "manifest does not cover every required continuity domain")
    return domains


def validate_artifacts(
    root: Path,
    payload: dict[str, Any],
    domains: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    raw_artifacts = payload.get("artifacts")
    if not isinstance(raw_artifacts, list):
        fail("invalid_artifacts", "artifacts must be an array")
    artifacts: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    seen_casefold: set[str] = set()
    by_domain: dict[str, set[str]] = {name: set() for name in domains}
    roles_by_domain: dict[str, list[str]] = {name: [] for name in domains}
    total_size = 0
    total_uncompressed_size = 0
    resolved_root = root.resolve(strict=True)
    for raw_artifact in raw_artifacts:
        if not isinstance(raw_artifact, dict):
            fail("invalid_artifact", "every artifact must be an object")
        relative = validate_relative_path(raw_artifact.get("path"))
        relative_text = relative.as_posix()
        casefolded = relative_text.casefold()
        if relative_text in seen_paths:
            fail("duplicate_artifact", "manifest contains a duplicate artifact path")
        if casefolded in seen_casefold:
            fail("artifact_case_collision", "artifact paths collide under case-insensitive filesystems")
        seen_paths.add(relative_text)
        seen_casefold.add(casefolded)
        domain = raw_artifact.get("domain")
        if not isinstance(domain, str) or domain not in domains:
            fail("invalid_artifact_domain", "artifact references an unknown continuity domain")
        role = raw_artifact.get("role")
        contract = ARTIFACT_CONTRACTS.get(role) if isinstance(role, str) else None
        if contract is None:
            fail("invalid_artifact_role", "artifact role is unsupported")
        expected_domain, expected_media_type, expected_method, expected_schema = contract
        if (
            domain != expected_domain
            or raw_artifact.get("mediaType") != expected_media_type
            or raw_artifact.get("captureMethod") != expected_method
            or not isinstance(raw_artifact.get("schemaVersion"), int)
            or isinstance(raw_artifact.get("schemaVersion"), bool)
            or raw_artifact.get("schemaVersion") != expected_schema
        ):
            fail("invalid_artifact_contract", "artifact metadata does not match its declared role")
        size = raw_artifact.get("size")
        checksum = raw_artifact.get("sha256")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            fail("invalid_artifact_size", "artifact size must be a non-negative integer")
        if size > MAX_ARTIFACT_BYTES:
            fail("artifact_size_limit", "artifact exceeds the validated size limit")
        role_size_limit = {
            "canonical_config": MAX_CONFIG_BYTES,
            "telegram_user_config": MAX_CHANNEL_JSON_BYTES,
            "schedules_database": MAX_SCHEDULES_DATABASE_BYTES,
        }.get(role)
        if role_size_limit is not None and size > role_size_limit:
            fail("artifact_size_limit", "artifact exceeds the role-specific size limit")
        total_size += size
        if total_size > MAX_TOTAL_ARTIFACT_BYTES:
            fail("bundle_size_limit", "bundle exceeds the validated total size limit")
        if not isinstance(checksum, str) or len(checksum) != 64:
            fail("invalid_artifact_checksum", "artifact checksum must be SHA-256")
        try:
            int(checksum, 16)
        except ValueError:
            fail("invalid_artifact_checksum", "artifact checksum must be SHA-256")
        artifact_path = root.joinpath(*relative.parts)
        try:
            metadata = artifact_path.lstat()
        except FileNotFoundError:
            fail("missing_artifact", "declared artifact is missing")
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            fail("unsafe_artifact_type", "artifacts must be regular non-symlink files")
        if metadata.st_nlink != 1:
            fail("unsafe_artifact_hardlink", "hard-linked artifacts are not accepted")
        try:
            artifact_path.resolve(strict=True).relative_to(resolved_root)
        except (OSError, ValueError):
            fail("artifact_escape", "artifact resolves outside the bundle root")
        if metadata.st_size != size:
            fail("artifact_size_mismatch", "artifact size does not match the manifest")
        if sha256_file(artifact_path) != checksum.lower():
            fail("artifact_checksum_mismatch", "artifact checksum does not match the manifest")
        declared_uncompressed_size: int | None = None
        if role in {"mongo_archive", "user_files_archive", "channel_state_archive"}:
            declared_uncompressed_size = raw_artifact.get("uncompressedSize")
            if (
                not isinstance(declared_uncompressed_size, int)
                or isinstance(declared_uncompressed_size, bool)
                or declared_uncompressed_size < 0
            ):
                fail("invalid_archive_contract", "archive uncompressed size must be a non-negative integer")
            if declared_uncompressed_size > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
                fail("archive_expansion_limit", "archive declaration exceeds the validated expansion limit")
            total_uncompressed_size += declared_uncompressed_size
            if total_uncompressed_size > MAX_TOTAL_ARCHIVE_UNCOMPRESSED_BYTES:
                fail("archive_expansion_limit", "bundle archive declarations exceed the validated total expansion limit")
            if size == 0 or declared_uncompressed_size > size * MAX_ARCHIVE_EXPANSION_RATIO:
                fail("archive_expansion_limit", "archive declaration exceeds the validated expansion ratio")
        validate_artifact_content(
            artifact_path,
            role,
            declared_uncompressed_size=declared_uncompressed_size,
        )
        by_domain[domain].add(relative_text)
        roles_by_domain[domain].append(role)
        artifacts.append(raw_artifact)
    for name, domain in domains.items():
        if set(domain["artifacts"]) != by_domain[name]:
            fail("domain_artifact_mismatch", "domain artifact references do not match artifact ownership")
    required_roles = {
        "config": ["canonical_config"],
        "mongo": ["mongo_archive"],
    }
    for domain, roles in required_roles.items():
        if roles_by_domain[domain] != roles:
            fail("missing_required_artifact_role", "required domain artifact role is missing or duplicated")
    if domains["schedules"]["status"] == "captured" and roles_by_domain["schedules"] != ["schedules_database"]:
        fail("invalid_schedules_artifacts", "captured schedules must contain one SQLite backup")
    if domains["schedules"]["status"] == "empty" and roles_by_domain["schedules"]:
        fail("unexpected_schedules_artifact", "empty schedules domain must not contain artifacts")
    if domains["files"]["status"] == "captured" and roles_by_domain["files"] != ["user_files_archive"]:
        fail("invalid_files_artifacts", "captured files must contain one bounded uploads archive")
    if domains["files"]["status"] == "empty" and roles_by_domain["files"]:
        fail("unexpected_files_artifact", "empty files domain must not contain artifacts")
    return artifacts


def validate_declared_files(root: Path, artifact_paths: set[str]) -> None:
    for current_root, directories, files in os.walk(root, topdown=True, followlinks=False):
        current = Path(current_root)
        for directory in directories:
            metadata = (current / directory).lstat()
            if stat.S_ISLNK(metadata.st_mode):
                fail("unsafe_bundle_symlink", "bundle directories must not be symlinks")
        for filename in files:
            path = current / filename
            relative = path.relative_to(root).as_posix()
            metadata = path.lstat()
            if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
                fail("unsafe_bundle_file", "bundle files must be regular non-symlink files")
            if relative not in METADATA_FILES and relative not in artifact_paths:
                fail("undeclared_bundle_file", "bundle contains an undeclared file")


def validate_owned_private_bundle(root: Path) -> None:
    for current_root, directories, files in os.walk(root, topdown=True, followlinks=False):
        current = Path(current_root)
        current_metadata = current.lstat()
        if (
            not stat.S_ISDIR(current_metadata.st_mode)
            or stat.S_ISLNK(current_metadata.st_mode)
            or current_metadata.st_uid != os.getuid()
            or stat.S_IMODE(current_metadata.st_mode) & 0o077
        ):
            raise RestoreTransactionError("Restore bundle directories must be current-user owner-only")
        for name in directories:
            child = current / name
            metadata = child.lstat()
            if stat.S_ISLNK(metadata.st_mode):
                raise RestoreTransactionError("Restore bundle contains a symlinked directory")
        for name in files:
            child = current / name
            metadata = child.lstat()
            if (
                not stat.S_ISREG(metadata.st_mode)
                or stat.S_ISLNK(metadata.st_mode)
                or metadata.st_uid != os.getuid()
                or metadata.st_nlink != 1
                or stat.S_IMODE(metadata.st_mode) & 0o077
            ):
                raise RestoreTransactionError("Restore bundle files must be current-user owner-only regular files")


def validate_bundle(root: Path, *, require_complete: bool = True) -> dict[str, Any]:
    try:
        root_metadata = root.lstat()
    except FileNotFoundError:
        fail("missing_bundle", "bundle directory does not exist")
    if stat.S_ISLNK(root_metadata.st_mode) or not stat.S_ISDIR(root_metadata.st_mode):
        fail("unsafe_bundle_root", "bundle root must be a real directory")
    validate_marker(root)
    payload = read_manifest(root)
    manifest_schema = payload.get("schemaVersion")
    if (
        not isinstance(manifest_schema, int)
        or isinstance(manifest_schema, bool)
        or manifest_schema != SCHEMA_VERSION
    ):
        fail("unsupported_schema", "recoverable manifest schema version is unsupported")
    bundle_kind = payload.get("bundleKind")
    if bundle_kind not in {"complete", "partial", "metadata-only"}:
        fail("invalid_bundle_kind", "bundle kind is unsupported")
    if require_complete and bundle_kind != "complete":
        fail("bundle_not_complete", "selected bundle is not declared complete")
    domains = validate_domains(payload)
    artifacts = validate_artifacts(root, payload, domains)
    validate_declared_files(root, {str(item["path"]) for item in artifacts})
    semantic_validation = "not_performed"
    restore_engine = "candidate_validation_only"
    inventory = payload.get("inventory")
    runtime_selection = payload.get("runtimeSelection")
    security = payload.get("security")
    if isinstance(inventory, dict) and isinstance(runtime_selection, dict) and isinstance(security, dict):
        profile = runtime_selection.get("profile")
        source_database = runtime_selection.get("sourceDatabase")
        if (
            not isinstance(profile, str)
            or not SAFE_PROFILE.fullmatch(profile)
            or not isinstance(source_database, str)
            or not SAFE_MONGO_DATABASE.fullmatch(source_database)
            or runtime_selection.get("generatedRuntimePolicy") != "regenerate_from_canonical_config"
            or runtime_selection.get("helperBindingPolicy") != "regenerate_for_target_checkout"
        ):
            fail("invalid_runtime_selection", "runtime selection metadata is invalid")
        if profile == "native":
            data_schema = runtime_selection.get("dataSchema")
            source_release = runtime_selection.get("sourceReleaseIdentity")
            if (
                isinstance(data_schema, bool)
                or not isinstance(data_schema, int)
                or data_schema < 1
                or not isinstance(source_release, str)
                or re.fullmatch(r"[0-9a-f]{40}", source_release) is None
            ):
                fail(
                    "invalid_runtime_selection",
                    "Native runtime selection lacks bound data-schema or release identity",
                )
        required_security = {
            "filesystemMode": "owner_only",
            "payloadEncryption": "not_self_encrypted_owner_only",
            "inlineConfigSecrets": "redacted",
            "providerCredentials": "excluded_reauthentication_required",
            "channelCredentials": "excluded_reauthentication_required",
            "mongoUserAuthFields": "excluded_reauthentication_required",
        }
        if any(security.get(key) != value for key, value in required_security.items()):
            fail("invalid_security_policy", "bundle security policy is missing or unsupported")
        if security.get("mongoExcludedCollections") != list(MONGO_EXCLUDED_SECRET_COLLECTIONS):
            fail("invalid_security_policy", "bundle secret-collection exclusions are incomplete")
        redacted_count = security.get("redactedConfigFieldCount")
        if (
            not isinstance(redacted_count, int)
            or isinstance(redacted_count, bool)
            or redacted_count < 0
            or redacted_count > MAX_CONFIG_BYTES
        ):
            fail("invalid_security_policy", "bundle redacted-secret count is invalid")
        config_artifact = next(item for item in artifacts if item.get("role") == "canonical_config")
        try:
            observed_redacted_count = validate_sanitized_config(root / str(config_artifact["path"]))
        except RestoreTransactionError as error:
            fail("invalid_config_secret_policy", str(error))
        if redacted_count != observed_redacted_count:
            fail("invalid_security_policy", "bundle redacted-secret count does not match canonical config")
        file_inventory = inventory.get("files")
        if (
            not isinstance(file_inventory, dict)
            or not isinstance(file_inventory.get("count"), int)
            or isinstance(file_inventory.get("count"), bool)
            or file_inventory["count"] < 0
            or file_inventory["count"] > MAX_ARCHIVE_MEMBERS
            or not isinstance(file_inventory.get("bytes"), int)
            or isinstance(file_inventory.get("bytes"), bool)
            or file_inventory["bytes"] < 0
            or file_inventory["bytes"] > MAX_TOTAL_ARTIFACT_BYTES
        ):
            fail("invalid_files_inventory", "file archive count/bytes are invalid")
        mongo_collections = inventory.get("mongoCollections")
        if not isinstance(mongo_collections, list):
            fail("invalid_mongo_inventory", "logical Mongo collection inventory is missing")
        mongo_artifacts = [item for item in artifacts if item.get("role") == "mongo_archive"]
        if len(mongo_artifacts) != 1:
            fail("invalid_mongo_inventory", "logical Mongo archive is missing or duplicated")
        try:
            total_archive_members = validate_mongo_logical_archive(
                root / str(mongo_artifacts[0]["path"]),
                mongo_collections,
            )
        except RestoreTransactionError as error:
            fail("invalid_mongo_archive", str(error))
        if total_archive_members > MAX_TOTAL_ARCHIVE_MEMBERS:
            fail("archive_member_limit", "bundle archive member count exceeds the restore bound")
        file_artifacts = [item for item in artifacts if item.get("role") == "user_files_archive"]
        observed_file_count = 0
        observed_file_bytes = 0
        for artifact in file_artifacts:
            try:
                members = safe_tar_members(
                    root / str(artifact["path"]),
                    expected_members=file_inventory["count"],
                )
            except RestoreTransactionError as error:
                fail("invalid_files_archive", str(error))
            observed_file_count += len(members)
            observed_file_bytes += sum(item.size for item in members)
            total_archive_members += len(members)
            if total_archive_members > MAX_TOTAL_ARCHIVE_MEMBERS:
                fail("archive_member_limit", "bundle archive member count exceeds the restore bound")
        if file_inventory != {
            "count": observed_file_count,
            "bytes": observed_file_bytes,
        }:
            fail("invalid_files_inventory", "file archive count/bytes do not match the manifest")
        for artifact in [item for item in artifacts if item.get("role") == "channel_state_archive"]:
            try:
                members = safe_tar_members(root / str(artifact["path"]))
            except RestoreTransactionError as error:
                fail("invalid_channels_archive", str(error))
            total_archive_members += len(members)
            if total_archive_members > MAX_TOTAL_ARCHIVE_MEMBERS:
                fail("archive_member_limit", "bundle archive member count exceeds the restore bound")
        schedule_artifacts = [item for item in artifacts if item.get("role") == "schedules_database"]
        observed_schedule_tables = 0
        observed_schedule_tasks = 0
        if schedule_artifacts:
            schedule_path = root / str(schedule_artifacts[0]["path"])
            try:
                connection = sqlite3.connect(f"file:{schedule_path}?mode=ro", uri=True)
                observed_schedule_tables = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
                    ).fetchone()[0]
                )
                if connection.execute(
                    "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='scheduled_tasks'"
                ).fetchone()[0]:
                    observed_schedule_tasks = int(
                        connection.execute("SELECT COUNT(*) FROM scheduled_tasks").fetchone()[0]
                    )
            except sqlite3.Error:
                fail("invalid_schedules_inventory", "schedule inventory cannot be read")
            finally:
                with contextlib.suppress(Exception):
                    connection.close()
        schedule_inventory = inventory.get("schedules")
        if (
            not isinstance(schedule_inventory, dict)
            or not isinstance(schedule_inventory.get("tables"), int)
            or isinstance(schedule_inventory.get("tables"), bool)
            or schedule_inventory["tables"] < 0
            or not isinstance(schedule_inventory.get("tasks"), int)
            or isinstance(schedule_inventory.get("tasks"), bool)
            or schedule_inventory["tasks"] < 0
        ):
            fail("invalid_schedules_inventory", "schedule counts are invalid")
        if schedule_inventory != {
            "tables": observed_schedule_tables,
            "tasks": observed_schedule_tasks,
        }:
            fail("invalid_schedules_inventory", "schedule count does not match the manifest")
        if inventory.get("recall") != {"policy": "rebuild_from_restored_canonical_state"}:
            fail("invalid_recall_inventory", "Recall inventory policy is unsupported")
        semantic_validation = "performed"
        restore_engine = "independent_target_transaction_v1"
    recoverable = bool(
        bundle_kind == "complete"
        and semantic_validation == "performed"
        and domains["recall"]["status"] == "rebuild_required"
        and domains["auth"]["status"] == "reauth_required"
        and domains["channels"]["status"] == "reauth_required"
    )
    return {
        "schemaVersion": SCHEMA_VERSION,
        "bundleKind": bundle_kind,
        "declaredComplete": bundle_kind == "complete",
        "recoverable": recoverable,
        "restoreEngine": restore_engine,
        "semanticValidation": semantic_validation,
        "artifactCount": len(artifacts),
        "domains": [
            {
                "name": name,
                "status": domains[name]["status"],
                "policy": domains[name]["policy"],
            }
            for name in DOMAIN_CONTRACTS
        ],
    }


def extract_regular_tar(
    path: Path,
    destination: Path,
    *,
    expected_members: int | None = None,
) -> None:
    try:
        archive = tarfile.open(path, "r:gz")
    except (tarfile.TarError, OSError) as error:
        raise RestoreTransactionError("Continuity archive is not a readable gzip tar") from error
    with archive:
        members = safe_tar_members_from_archive(
            archive,
            expected_members=expected_members,
        )
        ensure_private_directory(destination)
        for member in members:
            relative = validated_archive_path(member.name)
            target = destination.joinpath(*relative.parts)
            contained(target, destination, "Archive extraction")
            ensure_private_directory(target.parent)
            source = archive.extractfile(member)
            if source is None:
                raise RestoreTransactionError("Continuity archive member is unreadable")
            descriptor = os.open(
                target,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
            with os.fdopen(descriptor, "wb") as output:
                shutil.copyfileobj(source, output, length=1024 * 1024)
                output.flush()
                os.fsync(output.fileno())


def mongo_database_empty(
    uri: str,
    repo_root: Path,
    *,
    socket_path: Path | None = None,
) -> bool:
    if node_mongo_adapter(repo_root) is not None:
        payload = run_node_mongo_adapter(repo_root, "empty", uri, socket_path=socket_path)
        if not isinstance(payload.get("empty"), bool):
            raise RestoreTransactionError("Installed Node Mongo adapter returned invalid empty-state proof")
        return bool(payload["empty"])
    return len(mongo_collection_names(uri)) == 0


def mongo_claim_script(transaction_id: str) -> str:
    if not SAFE_TRANSACTION_ID.fullmatch(transaction_id):
        raise RestoreTransactionError("Restore transaction identifier is unsafe")
    return (
        "(() => { const id = " + json.dumps(transaction_id) + "; "
        f"const name = {json.dumps(MONGO_CLAIM_COLLECTION)}; "
        "if (db.getCollectionNames().length !== 0) throw new Error('target database is not empty'); "
        "db.createCollection(name); db.getCollection(name).insertOne({_id:id,schemaVersion:1,createdAt:new Date()}); "
        "if (db.getCollectionNames().length !== 1) { db.getCollection(name).drop(); "
        "throw new Error('target database changed while the restore claim was acquired'); } "
        "return {ok:1,claimed:true}; })()"
    )


def claim_mongo_database(
    uri: str,
    repo_root: Path,
    transaction_id: str,
    *,
    socket_path: Path | None = None,
) -> None:
    if node_mongo_adapter(repo_root) is not None:
        run_node_mongo_adapter(
            repo_root,
            "claim",
            uri,
            transaction_id=transaction_id,
            socket_path=socket_path,
        )
        return
    mongosh = shutil.which("mongosh")
    if not mongosh:
        raise RestoreTransactionError("mongosh is required to claim the isolated Mongo restore")
    run_checked([mongosh, uri, "--quiet", "--norc", "--eval", mongo_claim_script(transaction_id)])


def mongo_claim_check_script(transaction_id: str, action: str) -> str:
    if not SAFE_TRANSACTION_ID.fullmatch(transaction_id) or action not in {"drop", "release"}:
        raise RestoreTransactionError("Restore database claim operation is unsafe")
    missing = "return {ok:1,dropped:false};" if action == "drop" else "throw new Error('restore database claim is missing');"
    operation = "return db.dropDatabase();" if action == "drop" else "return {ok:1,released:db.getCollection(name).drop()};"
    return (
        "(() => { const id = " + json.dumps(transaction_id) + "; "
        f"const name = {json.dumps(MONGO_CLAIM_COLLECTION)}; "
        f"if (!db.getCollectionNames().includes(name)) {{ {missing} }} "
        "if (!db.getCollection(name).findOne({_id:id})) throw new Error('restore database is claimed by another transaction'); "
        f"{operation} }})()"
    )


def release_mongo_claim(
    uri: str,
    repo_root: Path,
    transaction_id: str,
    *,
    socket_path: Path | None = None,
) -> None:
    if node_mongo_adapter(repo_root) is not None:
        run_node_mongo_adapter(
            repo_root,
            "release",
            uri,
            transaction_id=transaction_id,
            socket_path=socket_path,
        )
        return
    mongosh = shutil.which("mongosh")
    if not mongosh:
        raise RestoreTransactionError("mongosh is required to release the isolated Mongo restore")
    run_checked(
        [mongosh, uri, "--quiet", "--norc", "--eval", mongo_claim_check_script(transaction_id, "release")]
    )


def drop_mongo_database(
    uri: str,
    repo_root: Path,
    transaction_id: str,
    *,
    socket_path: Path | None = None,
) -> None:
    if node_mongo_adapter(repo_root) is not None:
        run_node_mongo_adapter(
            repo_root,
            "drop",
            uri,
            transaction_id=transaction_id,
            socket_path=socket_path,
        )
        return
    mongosh = shutil.which("mongosh")
    if not mongosh:
        raise RestoreTransactionError("mongosh is required to roll back the isolated Mongo restore")
    run_checked(
        [mongosh, uri, "--quiet", "--norc", "--eval", mongo_claim_check_script(transaction_id, "drop")]
    )


def apply_mongo_logical(
    path: Path,
    ledger: list[dict[str, Any]],
    uri: str,
    scratch: Path,
    repo_root: Path,
    transaction_id: str,
    *,
    socket_path: Path | None = None,
) -> None:
    if socket_path is None:
        validate_local_mongo_uri(uri)
    elif uri != native_mongo_uri(socket_path):
        raise RestoreTransactionError("Native continuity Mongo socket binding is inconsistent")
    extract_regular_tar(path, scratch, expected_members=len(ledger) + 1)
    if node_mongo_adapter(repo_root) is not None:
        run_node_mongo_adapter(
            repo_root,
            "import",
            uri,
            directory_flag="--input-dir",
            directory=scratch,
            transaction_id=transaction_id,
            socket_path=socket_path,
        )
        return
    mongoimport = shutil.which("mongoimport")
    if not mongoimport:
        raise RestoreTransactionError(
            "Complete logical Mongo restore needs installed LibreChat dependencies or mongoimport"
        )
    for entry in ledger:
        if entry["documents"] == 0:
            continue
        run_checked(
            [
                mongoimport,
                "--uri",
                uri,
                "--collection",
                entry["name"],
                "--file",
                str(scratch / entry["path"]),
                "--jsonFormat",
                "canonical",
                "--mode",
                "insert",
            ]
        )


def restore_bundle(
    *,
    snapshot: Path,
    target_config_home: Path,
    target_repo_root: Path,
    target_mongo_uri: str,
    target_mongo_data_path: Path | None = None,
    fault_after: str | None = None,
) -> dict[str, Any]:
    snapshot = lexical(snapshot)
    target = lexical(target_config_home)
    target_repo = lexical(target_repo_root)
    validation = validate_bundle(snapshot)
    if not validation["recoverable"]:
        raise RestoreTransactionError("Selected bundle is not eligible for transactional restore")
    validate_path_chain(snapshot)
    validate_owned_private_bundle(snapshot)
    validate_path_chain(target.parent)
    validate_path_chain(target_repo)
    if not target_repo.is_dir():
        raise RestoreTransactionError("Independent target checkout is missing")
    for first, second, label in (
        (snapshot, target, "Snapshot and restore target"),
        (snapshot, target_repo, "Snapshot and target checkout"),
        (target, target_repo, "App Support target and target checkout"),
    ):
        try:
            common = os.path.commonpath([str(first), str(second)])
        except ValueError as error:
            raise RestoreTransactionError(f"{label} roots cannot be compared safely") from error
        if common in {str(first), str(second)}:
            raise RestoreTransactionError(f"{label} overlap")
    if target.exists() or target.is_symlink():
        raise RestoreTransactionError("Independent App Support target must not already exist")

    payload = read_manifest(snapshot)
    profile = str(payload["runtimeSelection"]["profile"])
    source_database = str(payload["runtimeSelection"]["sourceDatabase"])
    target_database, target_mongo_port = validate_local_mongo_uri(target_mongo_uri)
    if target_database == source_database:
        raise RestoreTransactionError("Independent restore must use a different Mongo database name")
    validated_mongo_data_path = None
    if target_mongo_data_path is not None:
        validated_mongo_data_path = validate_target_mongo_data_path(
            target_mongo_data_path,
            (snapshot, target, target_repo),
        )

    domains = {item["name"]: item for item in payload["domains"]}
    artifacts = {item["role"]: item for item in payload["artifacts"]}
    librechat_root = contained(target_repo / "viventium_v0_4" / "LibreChat", target_repo, "LibreChat target")
    if not librechat_root.is_dir():
        raise RestoreTransactionError("Independent target checkout lacks the LibreChat component")
    uploads_target = librechat_root / "uploads"
    if domains["files"]["status"] == "captured" and (uploads_target.exists() or uploads_target.is_symlink()):
        raise RestoreTransactionError("Independent target uploads directory must not already exist")

    require_storage_capacity(
        restore_storage_capacity_plan(
            payload,
            target_parent=target.parent,
            uploads_parent=librechat_root,
            target_mongo_data_path=validated_mongo_data_path,
        ),
        "continuity restore",
    )
    if not mongo_database_empty(target_mongo_uri, target_repo):
        raise RestoreTransactionError("Independent target Mongo database is not empty")

    transaction_id = uuid.uuid4().hex
    stage = target.parent / f".{target.name}.restore-stage.{transaction_id}"
    uploads_stage = librechat_root / f".uploads.restore-stage.{transaction_id}"
    mongo_scratch = target.parent / f".{target.name}.mongo-stage.{transaction_id}"
    journal = target.parent / f".{target.name}.restore-transaction.json"
    for candidate in (stage, uploads_stage, mongo_scratch, journal):
        if candidate.exists() or candidate.is_symlink():
            raise RestoreTransactionError("Independent restore staging path already exists")

    state = {
        "schemaVersion": 1,
        "transactionId": transaction_id,
        "phase": "preflight_complete",
        "targetCreated": False,
        "targetActivationPending": False,
        "uploadsCreated": False,
        "uploadsActivationPending": False,
        "mongoClaimPending": False,
        "mongoClaimed": False,
    }
    write_json_atomic(journal, state)
    previous_handlers: dict[int, Any] = {}
    commit_signals_deferred: list[int] = []

    def interrupt_handler(signum: int, _frame: Any) -> None:
        raise RestoreTransactionError(f"Restore interrupted by signal {signum}")

    def commit_signal_handler(signum: int, _frame: Any) -> None:
        # Once activation and scratch cleanup are complete, finish releasing
        # the database claim instead of creating an indeterminate half-commit.
        commit_signals_deferred.append(signum)

    for signum in (signal.SIGINT, signal.SIGTERM):
        previous_handlers[signum] = signal.getsignal(signum)
        signal.signal(signum, interrupt_handler)

    rollback_errors: list[str] = []
    try:
        state["mongoClaimPending"] = True
        write_json_atomic(journal, state)
        claim_mongo_database(target_mongo_uri, target_repo, transaction_id)
        state["mongoClaimed"] = True
        write_json_atomic(journal, state)

        ensure_private_directory(stage)
        config_source = snapshot / artifacts["canonical_config"]["path"]
        write_atomic(stage / "config.yaml", config_source.read_bytes())
        validate_artifact_content(stage / "config.yaml", "canonical_config")

        if domains["schedules"]["status"] == "captured":
            schedule_source = snapshot / artifacts["schedules_database"]["path"]
            schedule_target = stage / "state" / "runtime" / profile / "scheduling" / "schedules.db"
            ensure_private_directory(schedule_target.parent)
            shutil.copy2(schedule_source, schedule_target, follow_symlinks=False)
            schedule_target.chmod(0o600)
            validate_artifact_content(schedule_target, "schedules_database")

        continuity_dir = stage / "state" / "runtime" / profile / "continuity"
        ensure_private_directory(continuity_dir)
        write_json_atomic(
            continuity_dir / "recall-rebuild-required.json",
            {
                "schemaVersion": 1,
                "reason": "independent_restore_requires_derived_recall_rebuild",
                "createdAt": iso_now(),
            },
        )
        write_json_atomic(
            continuity_dir / "reauthentication-required.json",
            {
                "schemaVersion": 1,
                "providerCredentials": "reauth_required",
                "channelCredentials": "reauth_required",
                "browserSessions": "reauth_required",
                "userPasswords": "reset_required",
                "createdAt": iso_now(),
            },
        )
        runtime_selection = {
            "schemaVersion": 1,
            "profile": profile,
            "targetDatabase": target_database,
            "generatedRuntimePolicy": "regenerate_from_canonical_config",
            "helperBindingPolicy": "regenerate_for_target_checkout",
        }
        if validated_mongo_data_path is not None:
            write_atomic(
                stage / "state" / "continuity" / "restored-local-runtime-secret",
                (secrets.token_hex(32) + "\n").encode("ascii"),
            )
            runtime_selection.update(
                {
                    "schemaVersion": 2,
                    "targetMongoPort": target_mongo_port,
                    "targetMongoDataPath": str(validated_mongo_data_path),
                    "mongoPersistencePolicy": "target_owned_data_path",
                    "localRuntimeSecretPolicy": "regenerated_for_target",
                }
            )
        write_json_atomic(
            stage / "state" / "continuity" / "restored-runtime-selection.json",
            runtime_selection,
        )

        if domains["files"]["status"] == "captured":
            extract_regular_tar(
                snapshot / artifacts["user_files_archive"]["path"],
                uploads_stage,
                expected_members=payload["inventory"]["files"]["count"],
            )

        require_storage_floor(target.parent, "continuity restore")
        if domains["files"]["status"] == "captured":
            require_storage_floor(librechat_root, "continuity restore")

        state["phase"] = "filesystem_staged"
        write_json_atomic(journal, state)
        if fault_after == "filesystem_staged":
            raise RestoreTransactionError("Injected restore fault after filesystem staging")

        mongo_ledger = payload["inventory"]["mongoCollections"]
        # The empty target database is now transaction-claimed, so a
        # mid-collection failure can be rolled back without touching an
        # unclaimed database.
        apply_mongo_logical(
            snapshot / artifacts["mongo_archive"]["path"],
            mongo_ledger,
            target_mongo_uri,
            mongo_scratch,
            target_repo,
            transaction_id,
        )
        require_storage_floor(target.parent, "continuity restore")
        if validated_mongo_data_path is not None:
            require_storage_floor(validated_mongo_data_path, "continuity restore")
        state["phase"] = "mongo_restored"
        write_json_atomic(journal, state)
        if fault_after == "mongo_restored":
            raise RestoreTransactionError("Injected restore fault after Mongo restore")

        if domains["files"]["status"] == "captured":
            state["uploadsActivationPending"] = True
            write_json_atomic(journal, state)
            os.replace(uploads_stage, uploads_target)
            if fault_after == "uploads_renamed":
                raise RestoreTransactionError("Injected restore fault after uploads activation")
            state["uploadsCreated"] = True
            write_json_atomic(journal, state)
        state["targetActivationPending"] = True
        write_json_atomic(journal, state)
        os.replace(stage, target)
        if fault_after == "target_renamed":
            raise RestoreTransactionError("Injected restore fault after App Support activation")
        state["targetCreated"] = True
        state["phase"] = "activated"
        write_json_atomic(journal, state)
        if fault_after == "activated":
            raise RestoreTransactionError("Injected restore fault after activation")

        shutil.rmtree(mongo_scratch)
        state["phase"] = "commit_ready"
        write_json_atomic(journal, state)
        for signum in previous_handlers:
            signal.signal(signum, commit_signal_handler)
        release_mongo_claim(target_mongo_uri, target_repo, transaction_id)
        state["mongoClaimed"] = False
        # Releasing the database claim is the commit point. A stale private
        # journal is safer than trying to roll back after that point.
        with contextlib.suppress(Exception):
            journal.unlink()
        return {
            "restored": True,
            "recoverable": True,
            "runtimeProfile": profile,
            "mongoCollections": len(mongo_ledger),
            "filesRestored": domains["files"]["status"] == "captured",
            "schedulesRestored": domains["schedules"]["status"] == "captured",
            "recallRebuildRequired": True,
            "reauthenticationRequired": True,
            "commitSignalDeferred": bool(commit_signals_deferred),
        }
    except Exception:
        owns_target = bool(
            state.get("targetCreated")
            or (
                state.get("targetActivationPending")
                and target.exists()
                and not stage.exists()
            )
        )
        if owns_target and target.exists():
            try:
                shutil.rmtree(target)
            except Exception:
                rollback_errors.append("target")
        owns_uploads = bool(
            state.get("uploadsCreated")
            or (
                state.get("uploadsActivationPending")
                and uploads_target.exists()
                and not uploads_stage.exists()
            )
        )
        if owns_uploads and uploads_target.exists():
            try:
                shutil.rmtree(uploads_target)
            except Exception:
                rollback_errors.append("uploads")
        if state.get("mongoClaimPending") or state.get("mongoClaimed"):
            try:
                drop_mongo_database(target_mongo_uri, target_repo, transaction_id)
            except Exception:
                rollback_errors.append("mongo")
        for scratch in (stage, uploads_stage, mongo_scratch):
            if scratch.exists():
                with contextlib.suppress(Exception):
                    shutil.rmtree(scratch)
        if rollback_errors:
            state["phase"] = "rollback_incomplete"
            state["rollbackErrors"] = rollback_errors
            write_json_atomic(journal, state)
            raise RestoreTransactionError("Restore failed and automatic rollback was incomplete")
        with contextlib.suppress(FileNotFoundError):
            journal.unlink()
        raise
    finally:
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--snapshot-dir", required=True)
    validate_parser.add_argument("--allow-partial", action="store_true")
    validate_parser.add_argument("--json", action="store_true")
    capture_parser = subparsers.add_parser("capture")
    capture_parser.add_argument("--repo-root", required=True)
    capture_parser.add_argument("--app-support-dir", required=True)
    capture_parser.add_argument("--runtime-dir", required=True)
    capture_parser.add_argument("--output-root", required=True)
    capture_parser.add_argument("--uploads-dir")
    capture_parser.add_argument("--mongo-uri")
    capture_parser.add_argument("--json", action="store_true")
    restore_parser = subparsers.add_parser("restore")
    restore_parser.add_argument("--snapshot-dir", required=True)
    restore_parser.add_argument("--target-config-home", required=True)
    restore_parser.add_argument("--target-repo-root", required=True)
    restore_parser.add_argument("--target-mongo-uri", required=True)
    restore_parser.add_argument("--target-mongo-data-path")
    restore_parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.command == "capture":
        try:
            result = capture_bundle(
                repo_root=Path(args.repo_root),
                app_support=Path(args.app_support_dir),
                runtime_dir=Path(args.runtime_dir),
                output_root=Path(args.output_root),
                uploads_dir=Path(args.uploads_dir) if args.uploads_dir else None,
                mongo_uri=args.mongo_uri,
            )
        except (BundleValidationError, RestoreTransactionError, OSError, ValueError) as exc:
            payload = {"created": False, "error": type(exc).__name__, "message": str(exc)}
            if args.json:
                print(json.dumps(payload, sort_keys=True))
            else:
                print(f"Complete snapshot capture unavailable: {exc}")
            return 4
        if args.json:
            print(json.dumps({"created": True, **result}, sort_keys=True))
        else:
            print("Complete Viventium snapshot created and independently restorable.")
        return 0

    if args.command == "restore":
        try:
            result = restore_bundle(
                snapshot=Path(args.snapshot_dir),
                target_config_home=Path(args.target_config_home),
                target_repo_root=Path(args.target_repo_root),
                target_mongo_uri=args.target_mongo_uri,
                target_mongo_data_path=Path(args.target_mongo_data_path)
                if args.target_mongo_data_path
                else None,
            )
        except (BundleValidationError, RestoreTransactionError, OSError, ValueError) as exc:
            payload = {"restored": False, "error": type(exc).__name__, "message": str(exc)}
            if args.json:
                print(json.dumps(payload, sort_keys=True))
            else:
                print(f"Transactional restore failed: {exc}")
            return 4
        if args.json:
            print(json.dumps(result, sort_keys=True))
        else:
            print("Transactional restore completed; reconnect accounts and rebuild Recall before normal use.")
        return 0

    try:
        result = validate_bundle(
            Path(args.snapshot_dir).expanduser(),
            require_complete=not args.allow_partial,
        )
    except BundleValidationError as exc:
        result = {
            "valid": False,
            "recoverable": False,
            "error": exc.code,
            "message": exc.detail,
        }
        if args.json:
            print(json.dumps(result, sort_keys=True))
        else:
            print(f"Bundle validation failed: {exc.detail}")
        return 3

    result = {"valid": True, **result}
    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        if result["recoverable"]:
            print("Complete Viventium bundle structure, logical data, and independent-target restore contract validated.")
        else:
            print("Bundle structure and payload integrity validated; this legacy candidate is not restore-ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Journal, activate, and roll back source-install upgrades without losing local work."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import re
import shutil
import shlex
import signal
import stat
import subprocess
import sys
import tarfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


SCHEMA_VERSION = 1
ACTIVE_POINTER = Path("state/upgrade-transaction-active.json")
BACKUP_ROOT = Path("upgrade-backups")
MONGO_IMAGE_DEFAULT = "mongo:8.0.17"
MONGO_ENGINE_IDENTITY_RECEIPT = Path(
    "state/continuity/mongo-engine-identity.json"
)
MONGO_ENGINE_IDENTITY_SCHEMA_VERSION = 1
MONGO_ENGINE_IDENTITY_SURFACE_LABEL = "mongo-engine-identity"
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
LIBRECHAT_ENV_SURFACE_LABEL = "librechat-runtime-env"
HELPER_CONFIG_SURFACE_LABEL = "helper-config"
TELEGRAM_USER_CONFIG_SURFACE_LABEL = "telegram-user-configs"
TELEGRAM_PREFERENCE_AUTHORITY_KIND = "viventium-telegram-preference-authority"
TELEGRAM_PREFERENCE_AUTHORITY_SCHEMA_VERSION = 2
STATIC_PERSONALIZATION_SURFACE_LABELS = frozenset(
    {
        "telegram-codex-pairings",
        TELEGRAM_USER_CONFIG_SURFACE_LABEL,
    }
)
LIBRECHAT_PROTECTED_ENV_FIELDS = frozenset(
    {
        "CREDS_IV",
        "CREDS_KEY",
        "JWT_REFRESH_SECRET",
        "JWT_SECRET",
    }
)
LIBRECHAT_OWNER_SECRET_ENV_FIELDS = frozenset(
    {
        "AZURE_AI_FOUNDRY_API_KEY",
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_CLIENT_SECRET",
        "CODE_API_KEY",
        "COHERE_API_KEY",
        "FIRECRAWL_API_KEY",
        "GOOGLE_API_KEY",
        "GOOGLE_OAUTH_CLIENT_SECRET",
        "GROQ_API_KEY",
        "LIBRECHAT_CODE_API_KEY",
        "MEILI_MASTER_KEY",
        "MS365_MCP_CLIENT_SECRET",
        "OPENAI_API_KEY",
        "OPENROUTER_API_KEY",
        "PERPLEXITY_API_KEY",
        "SERPER_API_KEY",
        "XAI_API_KEY",
    }
)
# These are the fields that the source launcher deliberately reconciles from
# compiled runtime/config authority. Every other assignment in LibreChat/.env
# remains owner-controlled and must compare exactly at the commit boundary.
LIBRECHAT_MANAGED_ENV_FIELDS = frozenset(
    {
        "ALLOW_EMAIL_LOGIN",
        "ALLOW_REGISTRATION",
        "ALLOW_SOCIAL_LOGIN",
        "ALLOW_SOCIAL_REGISTRATION",
        "ALLOW_UNVERIFIED_EMAIL_LOGIN",
        "ASSISTANTS_MODELS",
        "AZURE_AI_FOUNDRY_API_KEY",
        "AZURE_OPENAI_API_INSTANCE_NAME",
        "AZURE_OPENAI_API_KEY",
        "CHECK_BALANCE",
        "CLIENT_URL",
        "CODE_API_KEY",
        "COHERE_API_KEY",
        "DEPLOYMENT_NAME",
        "DOMAIN_CLIENT",
        "DOMAIN_SERVER",
        "EMBEDDINGS_MODEL",
        "EMBEDDINGS_PROVIDER",
        "FIRECRAWL_API_KEY",
        "FIRECRAWL_API_URL",
        "FIRECRAWL_BASE_URL",
        "FIRECRAWL_VERSION",
        "GLASSHIVE_MCP_URL",
        "GLASSHIVE_OPERATOR_BASE_URL",
        "GOOGLE_API_KEY",
        "GOOGLE_OAUTH_CLIENT_ID",
        "GOOGLE_OAUTH_CLIENT_SECRET",
        "GROQ_API_KEY",
        "HOST",
        "INSTANCE_NAME",
        "LIBRECHAT_CODE_API_KEY",
        "LIBRECHAT_CODE_BASEURL",
        "MEILI_HOST",
        "MEILI_MASTER_KEY",
        "MEILI_NO_ANALYTICS",
        "MEILI_SYNC_THRESHOLD",
        "MONGO_URI",
        "MS365_MCP_CLIENT_ID",
        "MS365_MCP_CLIENT_SECRET",
        "MS365_MCP_SCOPE",
        "NO_INDEX",
        "OLLAMA_BASE_URL",
        "OPENAI_MODELS",
        "OPENROUTER_API_KEY",
        "PERPLEXITY_API_KEY",
        "PORT",
        "RAG_API_URL",
        "SEARCH",
        "SEARXNG_BASE_URL",
        "SEARXNG_INSTANCE_URL",
        "SERPER_API_KEY",
        "SKYVERN_APP_URL",
        "SKYVERN_BASE_URL",
        "START_BALANCE",
        "VITE_ALLOWED_HOSTS",
        "VIVENTIUM_ANTHROPIC_MODE",
        "VIVENTIUM_FOUNDRY_ANTHROPIC_REVERSE_PROXY",
        "VIVENTIUM_FRONTEND_PROXY_TARGET",
        "VIVENTIUM_RAG_EMBEDDINGS_MODEL",
        "VIVENTIUM_RAG_EMBEDDINGS_PROFILE",
        "VIVENTIUM_RAG_EMBEDDINGS_PROVIDER",
        "VIVENTIUM_REGISTRATION_APPROVAL",
        "XAI_API_KEY",
    }
)
ENV_ASSIGNMENT = re.compile(
    r"^[ \t]*(?:export[ \t]+)?([A-Za-z_][A-Za-z0-9_]*)[ \t]*=[ \t]*(.*)$"
)
HELPER_CONFIG_MANAGED_FIELDS = frozenset({"runtimeSupervision"})


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


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


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


def librechat_runtime_env_path(repo: Path) -> Path:
    target = contained(
        repo / "viventium_v0_4" / "LibreChat" / ".env",
        repo,
        "LibreChat runtime environment",
    )
    validate_chain(target, owned_from=repo)
    if target.is_symlink():
        raise UpgradeTransactionError("LibreChat runtime environment must not be a symlink")
    parent = target.parent
    if parent.exists():
        metadata = parent.lstat()
        if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.getuid():
            raise UpgradeTransactionError(
                "LibreChat runtime environment parent is not current-user-owned"
            )
    if target.exists():
        metadata = target.lstat()
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid():
            raise UpgradeTransactionError(
                "LibreChat runtime environment is not a current-user-owned regular file"
            )
    return target


def _assignment_digest(values: list[str]) -> dict[str, Any]:
    encoded = json.dumps(
        values,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "present": bool(values),
        "occurrences": len(values),
        "sha256": hashlib.sha256(encoded).hexdigest(),
    }


def _dotenv_quoted_value_complete(raw_value: str, quote: str) -> bool:
    escaped = False
    for character in raw_value[1:]:
        if quote == '"' and character == "\\" and not escaped:
            escaped = True
            continue
        if character == quote and not escaped:
            return True
        escaped = False
    return False


def _decode_dotenv_value(raw_value: str) -> str:
    value = raw_value.strip()
    if not value:
        return ""
    if value[0] in {"'", '"'}:
        quote = value[0]
        escaped = False
        closing_index: int | None = None
        for index, character in enumerate(value[1:], start=1):
            if quote == '"' and character == "\\" and not escaped:
                escaped = True
                continue
            if character == quote and not escaped:
                closing_index = index
                break
            escaped = False
        if closing_index is None:
            raise UpgradeTransactionError(
                "LibreChat runtime environment has an unterminated quoted value"
            )
        suffix = value[closing_index + 1 :].strip()
        if suffix and not suffix.startswith("#"):
            raise UpgradeTransactionError(
                "LibreChat runtime environment has trailing assignment data"
            )
        decoded = value[1:closing_index]
        if quote == '"':
            decoded = (
                decoded.replace("\\n", "\n")
                .replace("\\r", "\r")
                .replace("\\t", "\t")
                .replace('\\"', '"')
                .replace("\\\\", "\\")
            )
        return decoded
    comment = re.search(r"[ \t]+#", value)
    if comment is not None:
        value = value[: comment.start()].rstrip()
    return value


def _parse_dotenv_assignments(text: str) -> list[tuple[str, str]]:
    lines = text.splitlines()
    assignments: list[tuple[str, str]] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        index += 1
        if not stripped or stripped.startswith("#"):
            continue
        match = ENV_ASSIGNMENT.fullmatch(line)
        if match is None:
            raise UpgradeTransactionError(
                "LibreChat runtime environment contains an unparsed line"
            )
        key, raw_value = match.groups()
        if raw_value.startswith(("'", '"')):
            quote = raw_value[0]
            while not _dotenv_quoted_value_complete(raw_value, quote):
                if index >= len(lines):
                    raise UpgradeTransactionError(
                        "LibreChat runtime environment has an unterminated quoted value"
                    )
                raw_value += "\n" + lines[index]
                index += 1
        assignments.append((key, _decode_dotenv_value(raw_value)))
    return assignments


def librechat_env_semantic_manifest_from_bytes(contents: bytes) -> dict[str, Any]:
    protected_values = {key: [] for key in sorted(LIBRECHAT_PROTECTED_ENV_FIELDS)}
    owner_secret_values = {
        key: [] for key in sorted(LIBRECHAT_OWNER_SECRET_ENV_FIELDS)
    }
    managed_values: dict[str, list[str]] = {}
    unmanaged_values: dict[str, list[str]] = {}
    try:
        text = contents.decode("utf-8")
    except UnicodeDecodeError as error:
        raise UpgradeTransactionError(
            "LibreChat runtime environment is not valid UTF-8"
        ) from error
    for key, raw_value in _parse_dotenv_assignments(text):
        if key in LIBRECHAT_PROTECTED_ENV_FIELDS:
            protected_values[key].append(raw_value)
        elif key in LIBRECHAT_OWNER_SECRET_ENV_FIELDS:
            owner_secret_values[key].append(raw_value)
        elif key in LIBRECHAT_MANAGED_ENV_FIELDS:
            managed_values.setdefault(key, []).append(raw_value)
        else:
            unmanaged_values.setdefault(key, []).append(raw_value)
    return {
        "schema_version": 1,
        "exists": True,
        "file_sha256": hashlib.sha256(contents).hexdigest(),
        "protected_fields": {
            key: _assignment_digest(values)
            for key, values in protected_values.items()
        },
        "owner_secret_fields": {
            key: _assignment_digest(values)
            for key, values in owner_secret_values.items()
        },
        "managed_fields": {
            key: _assignment_digest(managed_values[key])
            for key in sorted(managed_values)
        },
        "unmanaged_fields": {
            key: _assignment_digest(unmanaged_values[key])
            for key in sorted(unmanaged_values)
        },
    }


def librechat_env_semantic_manifest(path: Path) -> dict[str, Any]:
    if not path.exists() and not path.is_symlink():
        return {
            "schema_version": 1,
            "exists": False,
            "file_sha256": "",
            "protected_fields": {
                key: _assignment_digest([])
                for key in sorted(LIBRECHAT_PROTECTED_ENV_FIELDS)
            },
            "owner_secret_fields": {
                key: _assignment_digest([])
                for key in sorted(LIBRECHAT_OWNER_SECRET_ENV_FIELDS)
            },
            "managed_fields": {},
            "unmanaged_fields": {},
        }
    validate_chain(path)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid():
            raise UpgradeTransactionError(
                "LibreChat runtime environment is not a current-user-owned regular file"
            )
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            contents = handle.read()
    finally:
        os.close(descriptor)
    return librechat_env_semantic_manifest_from_bytes(contents)


def compare_librechat_env_semantic_manifests(
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(before, dict) or before.get("schema_version") != 1:
        raise UpgradeTransactionError(
            "LibreChat environment continuity checkpoint is invalid"
        )
    if not isinstance(after, dict) or after.get("schema_version") != 1:
        raise UpgradeTransactionError(
            "LibreChat environment continuity live proof is invalid"
        )
    if before.get("exists") and not after.get("exists"):
        raise UpgradeTransactionError(
            "LibreChat environment continuity failed: owner environment disappeared"
        )
    before_protected = before.get("protected_fields")
    after_protected = after.get("protected_fields")
    if not isinstance(before_protected, dict) or not isinstance(after_protected, dict):
        raise UpgradeTransactionError(
            "LibreChat environment continuity protected-field proof is invalid"
        )
    for key in sorted(LIBRECHAT_PROTECTED_ENV_FIELDS):
        expected = before_protected.get(key)
        actual = after_protected.get(key)
        if not isinstance(expected, dict) or not isinstance(actual, dict):
            raise UpgradeTransactionError(
                "LibreChat environment continuity protected-field proof is invalid"
            )
        if expected.get("present") and expected != actual:
            raise UpgradeTransactionError(
                "LibreChat environment continuity failed: protected auth state changed"
            )
    before_unmanaged = before.get("unmanaged_fields")
    after_unmanaged = after.get("unmanaged_fields")
    if not isinstance(before_unmanaged, dict) or before_unmanaged != after_unmanaged:
        raise UpgradeTransactionError(
            "LibreChat environment continuity failed: owner-managed fields changed"
        )
    before_owner_secrets = before.get("owner_secret_fields")
    after_owner_secrets = after.get("owner_secret_fields")
    if not isinstance(before_owner_secrets, dict) or not isinstance(
        after_owner_secrets,
        dict,
    ):
        raise UpgradeTransactionError(
            "LibreChat environment continuity owner-secret proof is invalid"
        )
    for key in sorted(LIBRECHAT_OWNER_SECRET_ENV_FIELDS):
        expected = before_owner_secrets.get(key)
        actual = after_owner_secrets.get(key)
        if not isinstance(expected, dict) or not isinstance(actual, dict):
            raise UpgradeTransactionError(
                "LibreChat environment continuity owner-secret proof is invalid"
            )
        if expected.get("present") and expected != actual:
            raise UpgradeTransactionError(
                "LibreChat environment continuity failed: owner credential changed"
            )
    return {
        "verified": True,
        "before_file_sha256": str(before.get("file_sha256") or ""),
        "after_file_sha256": str(after.get("file_sha256") or ""),
        "exact_file_match": before.get("file_sha256") == after.get("file_sha256"),
        "protected_fields_preserved": True,
        "owner_secret_fields_preserved": True,
        "unmanaged_fields_preserved": True,
        "before_protected_field_digests": before_protected,
        "after_protected_field_digests": after_protected,
        "before_owner_secret_field_digests": before_owner_secrets,
        "after_owner_secret_field_digests": after_owner_secrets,
        "before_unmanaged_field_digests": before_unmanaged,
        "after_unmanaged_field_digests": after_unmanaged,
    }


def verify_librechat_env_continuity(ledger: dict[str, Any]) -> dict[str, Any]:
    matches = [
        surface
        for surface in ledger.get("surfaces", [])
        if surface.get("label") == LIBRECHAT_ENV_SURFACE_LABEL
    ]
    if len(matches) != 1:
        raise UpgradeTransactionError(
            "LibreChat environment continuity checkpoint is missing or ambiguous"
        )
    surface = matches[0]
    before = surface.get("semantic_manifest")
    current_path = librechat_runtime_env_path(Path(ledger["repo_root"]))
    after = librechat_env_semantic_manifest(current_path)
    return compare_librechat_env_semantic_manifests(before, after)


def helper_config_path(support: Path) -> Path:
    target = contained(
        support / "helper-config.json",
        support,
        "helper configuration",
    )
    validate_chain(target, owned_from=support)
    if target.is_symlink():
        raise UpgradeTransactionError("Helper configuration must not be a symlink")
    if target.exists():
        metadata = target.lstat()
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid():
            raise UpgradeTransactionError(
                "Helper configuration is not a current-user-owned regular file"
            )
    return target


def _json_value_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def helper_config_semantic_manifest(path: Path) -> dict[str, Any]:
    if not path.exists() and not path.is_symlink():
        return {
            "schema_version": 1,
            "exists": False,
            "file_sha256": "",
            "managed_fields": {},
            "protected_fields": {},
        }
    validate_chain(path)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid():
            raise UpgradeTransactionError(
                "Helper configuration is not a current-user-owned regular file"
            )
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            contents = handle.read()
    finally:
        os.close(descriptor)
    try:
        payload = json.loads(contents.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise UpgradeTransactionError("Helper configuration is invalid") from error
    if not isinstance(payload, dict):
        raise UpgradeTransactionError("Helper configuration must contain a JSON object")
    managed = {
        key: _json_value_digest(value)
        for key, value in payload.items()
        if key in HELPER_CONFIG_MANAGED_FIELDS
    }
    protected = {
        key: _json_value_digest(value)
        for key, value in payload.items()
        if key not in HELPER_CONFIG_MANAGED_FIELDS
    }
    return {
        "schema_version": 1,
        "exists": True,
        "file_sha256": hashlib.sha256(contents).hexdigest(),
        "managed_fields": {key: managed[key] for key in sorted(managed)},
        "protected_fields": {key: protected[key] for key in sorted(protected)},
    }


def compare_helper_config_semantic_manifests(
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(before, dict) or before.get("schema_version") != 1:
        raise UpgradeTransactionError(
            "Helper configuration continuity checkpoint is invalid"
        )
    if not isinstance(after, dict) or after.get("schema_version") != 1:
        raise UpgradeTransactionError(
            "Helper configuration continuity live proof is invalid"
        )
    if bool(before.get("exists")) != bool(after.get("exists")):
        raise UpgradeTransactionError(
            "Helper configuration continuity failed: configuration presence changed"
        )
    before_protected = before.get("protected_fields")
    after_protected = after.get("protected_fields")
    if not isinstance(before_protected, dict) or before_protected != after_protected:
        raise UpgradeTransactionError(
            "Helper configuration continuity failed: user preferences changed"
        )
    return {
        "verified": True,
        "before_file_sha256": str(before.get("file_sha256") or ""),
        "after_file_sha256": str(after.get("file_sha256") or ""),
        "exact_file_match": before.get("file_sha256") == after.get("file_sha256"),
        "protected_fields_preserved": True,
        "before_protected_field_digests": before_protected,
        "after_protected_field_digests": after_protected,
        "before_managed_field_digests": before.get("managed_fields", {}),
        "after_managed_field_digests": after.get("managed_fields", {}),
        "managed_fields_allowed_to_advance": sorted(HELPER_CONFIG_MANAGED_FIELDS),
    }


def verify_helper_config_continuity(ledger: dict[str, Any]) -> dict[str, Any]:
    matches = [
        surface
        for surface in ledger.get("surfaces", [])
        if surface.get("label") == HELPER_CONFIG_SURFACE_LABEL
    ]
    if len(matches) != 1:
        raise UpgradeTransactionError(
            "Helper configuration continuity checkpoint is missing or ambiguous"
        )
    surface = matches[0]
    before = surface.get("semantic_manifest")
    current_path = helper_config_path(Path(ledger["app_support_dir"]))
    after = helper_config_semantic_manifest(current_path)
    return compare_helper_config_semantic_manifests(before, after)


def verify_static_personalization_continuity(
    ledger: dict[str, Any],
) -> dict[str, Any]:
    proof: dict[str, Any] = {}
    for label in sorted(STATIC_PERSONALIZATION_SURFACE_LABELS):
        matches = [
            surface
            for surface in ledger.get("surfaces", [])
            if surface.get("label") == label
        ]
        if len(matches) != 1:
            raise UpgradeTransactionError(
                "Protected local personalization checkpoint is missing or ambiguous"
            )
        surface = matches[0]
        expected = surface.get("manifest")
        if not isinstance(expected, dict):
            raise UpgradeTransactionError(
                "Protected local personalization checkpoint is invalid"
            )
        actual = surface_manifest(
            Path(str(surface.get("path") or "")),
            allow_symlinks=bool(surface.get("allow_symlinks", False)),
        )
        if actual != expected:
            if label == TELEGRAM_USER_CONFIG_SURFACE_LABEL:
                try:
                    proof[label] = verify_telegram_preference_authority_handoff(
                        ledger=ledger,
                        surface=surface,
                        before=expected,
                        after=actual,
                    )
                except (FileNotFoundError, NotADirectoryError) as error:
                    # Ordinary pre-commit drift has no migration authority
                    # ledger. Keep the continuity failure generic and
                    # public-safe instead of leaking a private path through a
                    # raw filesystem exception.
                    raise UpgradeTransactionError(
                        "Upgrade protected local personalization changed before commit"
                    ) from error
                continue
            raise UpgradeTransactionError(
                "Upgrade protected local personalization changed before commit"
            )
        encoded = json.dumps(
            actual,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        proof[label] = {
            "verified": True,
            "kind": str(actual.get("kind") or ""),
            "manifest_sha256": hashlib.sha256(encoded).hexdigest(),
        }
    return proof


def _telegram_manifest_files(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    kind = manifest.get("kind")
    if kind == "absent":
        return {}
    if kind != "directory" or manifest.get("symlinks") not in (None, []):
        raise UpgradeTransactionError(
            "Telegram preference authority handoff has an unsafe surface"
        )
    files = manifest.get("files")
    if not isinstance(files, list):
        raise UpgradeTransactionError(
            "Telegram preference authority handoff manifest is invalid"
        )
    mapped: dict[str, dict[str, Any]] = {}
    for item in files:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("path"), str)
            or item["path"] in mapped
        ):
            raise UpgradeTransactionError(
                "Telegram preference authority handoff manifest is invalid"
            )
        mapped[item["path"]] = item
    return mapped


def _telegram_source_tree_digest(files: dict[str, dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for relative, item in sorted(files.items()):
        sha256 = item.get("sha256")
        if not isinstance(sha256, str):
            raise UpgradeTransactionError(
                "Telegram preference authority handoff source proof is invalid"
            )
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256.encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def _telegram_expected_merge(before: bytes | None, legacy: bytes) -> bytes:
    if before is None or before == legacy:
        return legacy
    try:
        before_value = json.loads(before)
        legacy_value = json.loads(legacy)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise UpgradeTransactionError(
            "Telegram preference authority handoff merge proof is invalid"
        ) from error
    if not isinstance(before_value, dict) or not isinstance(legacy_value, dict):
        raise UpgradeTransactionError(
            "Telegram preference authority handoff merge proof is invalid"
        )
    return (
        json.dumps(
            {**before_value, **legacy_value},
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _read_owner_regular(path: Path, label: str) -> bytes:
    validate_chain(path)
    metadata = path.lstat()
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or metadata.st_nlink != 1
    ):
        raise UpgradeTransactionError(f"{label} is not an owner-controlled regular file")
    return path.read_bytes()


def verify_telegram_preference_authority_handoff(
    *,
    ledger: dict[str, Any],
    surface: dict[str, Any],
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, Any]:
    """Accept only the exact crash-safe legacy-to-canonical preference transition."""
    support = lexical(Path(str(ledger.get("app_support_dir") or "")))
    canonical = contained(
        Path(str(surface.get("path") or "")),
        support,
        "canonical Telegram preferences",
    )
    expected_canonical = support / "state" / TELEGRAM_USER_CONFIG_SURFACE_LABEL
    if canonical != expected_canonical:
        raise UpgradeTransactionError(
            "Telegram preference authority handoff target is invalid"
        )
    state_root = support / "state" / "telegram-user-config-migration"
    authority_path = state_root / "authority.json"
    pending_path = state_root / "pending.json"
    if pending_path.exists() or pending_path.is_symlink():
        raise UpgradeTransactionError(
            "Telegram preference authority handoff is still pending"
        )
    try:
        authority = json.loads(
            _read_owner_regular(
                authority_path,
                "Telegram preference authority ledger",
            )
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise UpgradeTransactionError(
            "Telegram preference authority handoff ledger is unreadable"
        ) from error
    generation = authority.get("generation") if isinstance(authority, dict) else None
    roots = authority.get("retired_legacy_roots") if isinstance(authority, dict) else None
    operations = authority.get("operations") if isinstance(authority, dict) else None
    if (
        not isinstance(authority, dict)
        or authority.get("schema_version")
        != TELEGRAM_PREFERENCE_AUTHORITY_SCHEMA_VERSION
        or authority.get("kind") != TELEGRAM_PREFERENCE_AUTHORITY_KIND
        or authority.get("status") != "committed"
        or authority.get("authority") != "canonical-app-support"
        or lexical(Path(str(authority.get("canonical_root") or ""))) != canonical
        or not isinstance(generation, str)
        or not re.fullmatch(r"[0-9a-f]{64}", generation)
        or not isinstance(roots, list)
        or len(roots) != 1
        or not isinstance(roots[0], str)
        or not isinstance(operations, list)
    ):
        raise UpgradeTransactionError(
            "Telegram preference authority handoff ledger is invalid"
        )

    source = lexical(Path(roots[0]))
    source_manifest = surface_manifest(source)
    source_files = _telegram_manifest_files(source_manifest)
    if (
        authority.get("source_tree_sha256")
        != _telegram_source_tree_digest(source_files)
    ):
        raise UpgradeTransactionError(
            "Telegram preference authority handoff source changed"
        )

    before_files = _telegram_manifest_files(before)
    after_files = _telegram_manifest_files(after)
    changed_paths = {
        relative
        for relative in set(before_files) | set(after_files)
        if before_files.get(relative) != after_files.get(relative)
    }
    operation_map: dict[str, dict[str, Any]] = {}
    for operation in operations:
        if not isinstance(operation, dict) or not isinstance(operation.get("path"), str):
            raise UpgradeTransactionError(
                "Telegram preference authority handoff operation is invalid"
            )
        relative = Path(operation["path"])
        relative_text = relative.as_posix()
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or relative_text in operation_map
            or relative_text not in source_files
        ):
            raise UpgradeTransactionError(
                "Telegram preference authority handoff operation is invalid"
            )
        operation_map[relative_text] = operation
    if set(operation_map) != changed_paths:
        raise UpgradeTransactionError(
            "Telegram preference authority handoff contains an unproven change"
        )

    checkpoint_root = Path(str(surface.get("backup") or ""))
    for relative, operation in operation_map.items():
        before_item = before_files.get(relative)
        after_item = after_files.get(relative)
        source_item = source_files[relative]
        before_sha256 = before_item.get("sha256") if before_item else None
        if (
            after_item is None
            or operation.get("canonical_before_sha256") != before_sha256
            or operation.get("legacy_sha256") != source_item.get("sha256")
            or operation.get("canonical_after_sha256") != after_item.get("sha256")
            or after_item.get("mode") != 0o600
        ):
            raise UpgradeTransactionError(
                "Telegram preference authority handoff operation proof does not match"
            )
        before_value = (
            _read_owner_regular(
                checkpoint_root / relative,
                "Checkpointed Telegram preference",
            )
            if before_item is not None
            else None
        )
        legacy_value = _read_owner_regular(
            source / relative,
            "Legacy Telegram preference",
        )
        after_value = _read_owner_regular(
            canonical / relative,
            "Canonical Telegram preference",
        )
        expected_after = _telegram_expected_merge(before_value, legacy_value)
        if (
            hashlib.sha256(expected_after).hexdigest() != after_item.get("sha256")
            or after_value != expected_after
        ):
            raise UpgradeTransactionError(
                "Telegram preference authority handoff merge result is invalid"
            )
        backup = operation.get("backup")
        if before_item is None:
            if backup not in ("", None):
                raise UpgradeTransactionError(
                    "Telegram preference authority handoff backup proof is invalid"
                )
        else:
            if not isinstance(backup, str) or not backup:
                raise UpgradeTransactionError(
                    "Telegram preference authority handoff backup proof is missing"
                )
            backup_path = contained(
                support / backup,
                state_root / "backups" / generation / "canonical",
                "Telegram preference migration backup",
            )
            if _read_owner_regular(
                backup_path,
                "Telegram preference migration backup",
            ) != before_value:
                raise UpgradeTransactionError(
                    "Telegram preference authority handoff backup changed"
                )

    # A legacy file omitted from operations is valid only when it already
    # existed byte-identically in canonical state and remains unchanged.
    for relative, source_item in source_files.items():
        if relative in operation_map:
            continue
        if (
            before_files.get(relative) is None
            or before_files[relative].get("sha256") != source_item.get("sha256")
            or after_files.get(relative) != before_files[relative]
        ):
            raise UpgradeTransactionError(
                "Telegram preference authority handoff omitted source data"
            )

    before_directories = {
        item["path"]: item["mode"]
        for item in before.get("directories", [])
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }
    after_directories = {
        item["path"]: item["mode"]
        for item in after.get("directories", [])
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }
    if not set(before_directories).issubset(after_directories):
        raise UpgradeTransactionError(
            "Telegram preference authority handoff removed a directory"
        )
    for relative, mode in after_directories.items():
        previous_mode = before_directories.get(relative)
        if previous_mode is None and mode != 0o700:
            raise UpgradeTransactionError(
                "Telegram preference authority handoff created an unsafe directory"
            )
        if previous_mode is not None and mode not in {previous_mode, 0o700}:
            raise UpgradeTransactionError(
                "Telegram preference authority handoff changed a directory unexpectedly"
            )

    encoded = json.dumps(
        after,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "verified": True,
        "kind": str(after.get("kind") or ""),
        "manifest_sha256": hashlib.sha256(encoded).hexdigest(),
        "transition": "verified-authority-handoff",
        "generation": generation,
        "files_changed": len(operation_map),
    }


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
            "VIVENTIUM_INSTALL_MODE",
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


def validate_docker_image_id(value: str) -> str:
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
        raise UpgradeTransactionError("MongoDB container immutable image identity is unsafe")
    return value


def docker_storage_image(storage: dict[str, Any]) -> str:
    image_id = str(storage.get("image_id") or "")
    if image_id:
        return validate_docker_image_id(image_id)
    return validate_docker_image(str(storage.get("image") or ""))


def _process_field(pid: int, field: str) -> str:
    ps = shutil.which("ps") or "/bin/ps"
    try:
        result = subprocess.run(
            [ps, "-p", str(pid), "-o", f"{field}="],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5,
            text=True,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise UpgradeTransactionError(
            "Native MongoDB process identity could not be inspected"
        ) from error
    value = result.stdout.strip()
    if result.returncode != 0 or not value:
        raise UpgradeTransactionError(
            "Native MongoDB process identity could not be inspected"
        )
    return value


def _darwin_process_arguments(pid: int) -> list[str]:
    libc = ctypes.CDLL(None, use_errno=True)
    sysctl = libc.sysctl
    sysctl.argtypes = [
        ctypes.POINTER(ctypes.c_int),
        ctypes.c_uint,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_size_t),
        ctypes.c_void_p,
        ctypes.c_size_t,
    ]
    sysctl.restype = ctypes.c_int
    mib = (ctypes.c_int * 3)(1, 49, pid)
    size = ctypes.c_size_t(0)
    if sysctl(mib, 3, None, ctypes.byref(size), None, 0) != 0:
        raise UpgradeTransactionError(
            "Native MongoDB process arguments could not be inspected exactly"
        )
    if size.value < 4 or size.value > 8 * 1024 * 1024:
        raise UpgradeTransactionError("Native MongoDB process arguments are malformed")
    buffer = ctypes.create_string_buffer(size.value)
    if sysctl(mib, 3, buffer, ctypes.byref(size), None, 0) != 0:
        raise UpgradeTransactionError(
            "Native MongoDB process arguments could not be inspected exactly"
        )
    raw = buffer.raw[: size.value]
    argument_count = int.from_bytes(raw[:4], byteorder=sys.byteorder, signed=True)
    if argument_count <= 0 or argument_count > 65536:
        raise UpgradeTransactionError("Native MongoDB process arguments are malformed")
    cursor = raw.find(b"\0", 4)
    if cursor < 0:
        raise UpgradeTransactionError("Native MongoDB process arguments are malformed")
    cursor += 1
    while cursor < len(raw) and raw[cursor] == 0:
        cursor += 1
    arguments: list[str] = []
    while len(arguments) < argument_count and cursor < len(raw):
        terminator = raw.find(b"\0", cursor)
        if terminator < 0:
            break
        arguments.append(os.fsdecode(raw[cursor:terminator]))
        cursor = terminator + 1
    if len(arguments) != argument_count or not all(arguments):
        raise UpgradeTransactionError("Native MongoDB process arguments are malformed")
    return arguments


def _linux_process_arguments(pid: int) -> list[str]:
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError as error:
        raise UpgradeTransactionError(
            "Native MongoDB process arguments could not be inspected exactly"
        ) from error
    if not raw or not raw.endswith(b"\0"):
        raise UpgradeTransactionError("Native MongoDB process arguments are malformed")
    raw_arguments = raw.split(b"\0")[:-1]
    if not raw_arguments or any(not value for value in raw_arguments):
        raise UpgradeTransactionError("Native MongoDB process arguments are malformed")
    return [os.fsdecode(value) for value in raw_arguments]


def _process_arguments(pid: int) -> list[str]:
    if sys.platform == "darwin":
        return _darwin_process_arguments(pid)
    if sys.platform.startswith("linux"):
        return _linux_process_arguments(pid)
    raise UpgradeTransactionError(
        "Exact native MongoDB process argument inspection is unavailable"
    )


def inspect_native_mongo_process(pid: int) -> dict[str, Any]:
    try:
        os.kill(pid, 0)
    except OSError as error:
        raise UpgradeTransactionError("Recorded native MongoDB process is not running") from error
    started_at = _process_field(pid, "lstart")
    arguments = _process_arguments(pid)
    if not arguments:
        raise UpgradeTransactionError("Native MongoDB process arguments are missing")
    raw_executable = arguments[0]
    executable_candidate = (
        Path(raw_executable)
        if Path(raw_executable).is_absolute()
        else Path(shutil.which(raw_executable) or raw_executable)
    )
    try:
        executable = executable_candidate.resolve(strict=True)
        metadata = executable.stat()
    except (OSError, RuntimeError) as error:
        raise UpgradeTransactionError("Native MongoDB executable identity is unavailable") from error
    if not stat.S_ISREG(metadata.st_mode) or executable.name != "mongod":
        raise UpgradeTransactionError("Recorded native MongoDB PID is not a mongod process")
    try:
        version_result = subprocess.run(
            [str(executable), "--version"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            text=True,
            env={"PATH": os.environ.get("PATH", "")},
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise UpgradeTransactionError("Native MongoDB version identity is unavailable") from error
    version = next(
        (line.strip() for line in version_result.stdout.splitlines() if line.strip()),
        "",
    )
    if (
        version_result.returncode != 0
        or not version
        or len(version) > 512
        or any(ord(character) < 32 for character in version)
    ):
        raise UpgradeTransactionError("Native MongoDB version identity is unavailable")
    signature_verified = False
    signature_team_identifier = ""
    codesign = Path("/usr/bin/codesign")
    if codesign.is_file():
        verification = subprocess.run(
            [str(codesign), "--verify", "--strict", str(executable)],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            text=True,
        )
        signature_verified = verification.returncode == 0
        if signature_verified:
            details = subprocess.run(
                [str(codesign), "-dv", "--verbose=4", str(executable)],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=10,
                text=True,
            )
            match = re.search(
                r"^TeamIdentifier=([A-Za-z0-9.-]+)$",
                details.stderr,
                re.MULTILINE,
            )
            signature_team_identifier = match.group(1) if match else ""
    return {
        "pid": pid,
        "process_started_at": started_at,
        "executable": str(executable),
        "executable_sha256": sha256_file(executable),
        "arguments": arguments,
        "version": version,
        "code_signature_verified": signature_verified,
        "code_signature_team_identifier": signature_team_identifier,
    }


def native_mongo_dbpath(identity: dict[str, Any]) -> Path:
    raw_arguments = identity.get("arguments")
    if not isinstance(raw_arguments, list) or not all(
        isinstance(argument, str) for argument in raw_arguments
    ):
        raise UpgradeTransactionError("Native MongoDB process arguments are unavailable")
    candidates: list[str] = []
    for index, argument in enumerate(raw_arguments):
        if argument == "--dbpath":
            if index + 1 >= len(raw_arguments):
                raise UpgradeTransactionError("Native MongoDB dbpath argument is incomplete")
            candidates.append(raw_arguments[index + 1])
        elif argument.startswith("--dbpath="):
            candidates.append(argument.split("=", 1)[1])
    if len(candidates) != 1 or not candidates[0]:
        raise UpgradeTransactionError("Native MongoDB process has ambiguous database storage")
    return lexical(Path(candidates[0]))


def _path_has_durable_state(path: Path) -> bool:
    if not path.exists() and not path.is_symlink():
        return False
    validate_chain(path)
    if path.is_symlink() or not path.is_dir():
        raise UpgradeTransactionError("MongoDB data path is unsafe")
    try:
        next(path.iterdir())
    except StopIteration:
        return False
    except OSError as error:
        raise UpgradeTransactionError("MongoDB data path could not be inspected") from error
    return True


def _configured_native_data_path(
    support: Path,
    profile: str,
    explicit_data: str,
) -> Path:
    if explicit_data:
        return contained(Path(explicit_data), support, "MongoDB data path")
    profile_path = support / "state" / "runtime" / profile / "mongo-data"
    legacy_path = support / "state" / "mongo-data"
    if profile_path.is_dir():
        return profile_path
    if legacy_path.is_dir():
        return legacy_path
    return profile_path


def _docker_container_mongo_inventory(
    docker: str,
    *,
    container: str,
    profile: str,
    support: Path,
    explicit_data: str,
) -> dict[str, Any] | None:
    inspected = docker_command(docker, "container", "inspect", container, check=False)
    if inspected.returncode != 0:
        return None
    try:
        containers = json.loads(inspected.stdout.decode("utf-8"))
        if not isinstance(containers, list) or len(containers) != 1:
            raise ValueError("unexpected container count")
        container_info = containers[0]
        mounts = container_info["Mounts"]
        state = container_info["State"]
        configured_image = container_info["Config"]["Image"]
        image_id = container_info["Image"]
        running = state["Running"]
    except (
        IndexError,
        KeyError,
        TypeError,
        UnicodeDecodeError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        raise UpgradeTransactionError("MongoDB container storage inventory is unreadable") from error
    if not isinstance(running, bool):
        raise UpgradeTransactionError("MongoDB container runtime state is unreadable")
    matching = [item for item in mounts if item.get("Destination") == "/data/db"]
    if len(matching) != 1:
        raise UpgradeTransactionError("MongoDB container has ambiguous database storage")
    mount = matching[0]
    actual_image = validate_docker_image(str(configured_image))
    immutable_image = validate_docker_image_id(str(image_id))
    common = {
        "runtime_engine": "docker",
        "profile": profile,
        "image": actual_image,
        "image_id": immutable_image,
        "container_name": container,
        "container_running": running,
        "observed_from": "container_inspect",
    }
    if mount.get("Type") == "volume":
        return {
            "backend": "docker_named_volume",
            "volume_name": validate_docker_name(
                str(mount.get("Name") or ""),
                "MongoDB volume name",
            ),
            **common,
        }
    if mount.get("Type") == "bind":
        data_path = contained(
            Path(str(mount.get("Source") or "")),
            support,
            "MongoDB bind path",
        )
        if explicit_data and data_path != lexical(Path(explicit_data)):
            raise UpgradeTransactionError(
                "MongoDB container bind path differs from generated runtime configuration"
            )
        return {
            "backend": "app_support_bind",
            "path": str(data_path),
            **common,
        }
    raise UpgradeTransactionError("MongoDB container uses an unsupported storage backend")


def _observe_running_mongo_storage(
    support: Path,
    runtime_dir: Path,
) -> tuple[dict[str, Any] | None, list[tuple[str, Path]]]:
    values: dict[str, str] = {}
    for env_file in (runtime_dir / "runtime.env", runtime_dir / "runtime.local.env"):
        values.update(parse_runtime_env(env_file))
    profile = values.get("VIVENTIUM_RUNTIME_PROFILE", "isolated").strip().lower() or "isolated"
    if profile not in {"compat", "isolated", "native"}:
        raise UpgradeTransactionError("Active runtime profile has unknown MongoDB storage semantics")
    install_mode = values.get("VIVENTIUM_INSTALL_MODE", "").strip().lower()
    explicit_data = values.get("VIVENTIUM_LOCAL_MONGO_DATA_PATH", "").strip()
    extra_surfaces: list[tuple[str, Path]] = []
    configured_path = _configured_native_data_path(support, profile, explicit_data)
    container = validate_docker_name(
        values.get("VIVENTIUM_LOCAL_MONGO_CONTAINER", "viventium-mongodb"),
        "MongoDB container name",
    )
    volume = validate_docker_name(
        values.get("VIVENTIUM_LOCAL_MONGO_VOLUME", f"{container}-data"),
        "MongoDB volume name",
    )
    configured_image = validate_docker_image(values.get("MONGO_IMAGE", MONGO_IMAGE_DEFAULT))

    docker: str | None = None
    docker_inventory: dict[str, Any] | None = None
    try:
        docker = docker_ready()
    except UpgradeTransactionError:
        pass
    else:
        docker_inventory = _docker_container_mongo_inventory(
            docker,
            container=container,
            profile=profile,
            support=support,
            explicit_data=explicit_data,
        )

    native_inventory: dict[str, Any] | None = None
    native_pid_paths = (
        support / "state" / "native" / "mongod.pid",
        support / "state" / "runtime" / profile / "mongodb-native.pid",
    )
    observed_native: list[dict[str, Any]] = []
    for native_pid in native_pid_paths:
        if not (native_pid.exists() or native_pid.is_symlink()):
            continue
        validate_chain(native_pid, owned_from=support)
        if native_pid.is_symlink() or not native_pid.is_file():
            raise UpgradeTransactionError("Native MongoDB PID record is unsafe")
        try:
            pid = int(native_pid.read_text(encoding="utf-8").strip())
        except (OSError, UnicodeError, ValueError) as error:
            raise UpgradeTransactionError("Native MongoDB PID record is unreadable") from error
        if pid <= 0:
            raise UpgradeTransactionError("Native MongoDB PID record is invalid")
        try:
            identity = inspect_native_mongo_process(pid)
        except UpgradeTransactionError as error:
            if "is not running" not in str(error):
                raise
        else:
            data_path = contained(
                native_mongo_dbpath(identity),
                support,
                "Native MongoDB process data path",
            )
            if explicit_data and data_path != configured_path:
                raise UpgradeTransactionError(
                    "Native MongoDB dbpath differs from generated runtime configuration"
                )
            observed_native.append({
                "backend": "app_support_bind",
                "runtime_engine": "native",
                "profile": profile,
                "path": str(data_path),
                "observed_from": "running_native_pid",
                **identity,
            })
    native_pids = {item["pid"] for item in observed_native}
    if len(native_pids) > 1:
        raise UpgradeTransactionError(
            "Native MongoDB PID records identify different live processes"
        )
    if observed_native:
        native_inventory = observed_native[0]

    if (
        docker_inventory is not None
        and docker_inventory["container_running"]
        and native_inventory is not None
    ):
        raise UpgradeTransactionError(
            "Both Docker and native MongoDB runtimes appear active; storage identity is ambiguous"
        )
    if docker_inventory is not None and docker_inventory["container_running"]:
        inventory = docker_inventory
    elif native_inventory is not None:
        inventory = native_inventory
    elif docker_inventory is not None:
        inventory = docker_inventory
    else:
        inventory = None

    if inventory is not None:
        if inventory["backend"] == "app_support_bind":
            data_path = Path(str(inventory["path"]))
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
        return inventory, extra_surfaces

    return None, extra_surfaces


def mongo_engine_receipt_digest(payload: dict[str, Any]) -> str:
    canonical = {
        key: value
        for key, value in payload.items()
        if key != "receipt_sha256"
    }
    encoded = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _mongo_receipt_path(support: Path) -> Path:
    return contained(
        lexical(support) / MONGO_ENGINE_IDENTITY_RECEIPT,
        lexical(support),
        "MongoDB engine identity receipt",
    )


def _validate_existing_mongo_receipt_target(path: Path, support: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    try:
        validate_chain(path, owned_from=support)
    except UpgradeTransactionError as error:
        raise UpgradeTransactionError(
            "MongoDB engine identity receipt is unsafe"
        ) from error
    metadata = path.lstat()
    if path.is_symlink() or not stat.S_ISREG(metadata.st_mode):
        raise UpgradeTransactionError("MongoDB engine identity receipt is unsafe")
    if metadata.st_uid != os.getuid():
        raise UpgradeTransactionError(
            "MongoDB engine identity receipt is not owned by the current user"
        )
    if stat.S_IMODE(metadata.st_mode) != 0o600:
        raise UpgradeTransactionError(
            "MongoDB engine identity receipt must be owner-only"
        )


def _write_mongo_engine_receipt(
    support: Path,
    payload: dict[str, Any],
) -> dict[str, Any]:
    support = lexical(support)
    receipt = _mongo_receipt_path(support)
    _validate_existing_mongo_receipt_target(receipt, support)
    normalized = dict(payload)
    normalized["receipt_sha256"] = mongo_engine_receipt_digest(normalized)
    write_json_atomic(receipt, normalized, boundary=support)
    _fsync_directory(receipt.parent)
    return normalized


def _load_mongo_engine_receipt(
    support: Path,
) -> dict[str, Any] | None:
    support = lexical(support)
    receipt = _mongo_receipt_path(support)
    if not receipt.exists() and not receipt.is_symlink():
        return None
    _validate_existing_mongo_receipt_target(receipt, support)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(receipt, flags)
        with os.fdopen(descriptor, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise UpgradeTransactionError(
            "MongoDB engine identity receipt is unreadable"
        ) from error
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != MONGO_ENGINE_IDENTITY_SCHEMA_VERSION
        or not isinstance(payload.get("identity"), dict)
        or not isinstance(payload.get("clean_stopped"), bool)
        or not re.fullmatch(
            r"[0-9a-f]{64}",
            str(payload.get("receipt_sha256") or ""),
        )
        or payload["receipt_sha256"] != mongo_engine_receipt_digest(payload)
    ):
        raise UpgradeTransactionError(
            "MongoDB engine identity receipt failed integrity validation"
        )
    return payload


def _mongo_identity_static_view(identity: dict[str, Any]) -> dict[str, Any]:
    backend = str(identity.get("backend") or "")
    engine = str(identity.get("runtime_engine") or "")
    common = {
        "backend": backend,
        "runtime_engine": engine,
        "profile": str(identity.get("profile") or ""),
    }
    if backend == "app_support_bind":
        common["path"] = str(identity.get("path") or "")
    elif backend == "docker_named_volume":
        common["volume_name"] = str(identity.get("volume_name") or "")
    else:
        raise UpgradeTransactionError(
            "MongoDB engine identity receipt has an unsupported storage backend"
        )
    if engine == "docker":
        common.update(
            {
                "image": str(identity.get("image") or ""),
                "image_id": str(identity.get("image_id") or ""),
                "container_name": str(identity.get("container_name") or ""),
            }
        )
    elif engine == "native":
        common.update(
            {
                "executable": str(identity.get("executable") or ""),
                "executable_sha256": str(
                    identity.get("executable_sha256") or ""
                ),
                "arguments": identity.get("arguments"),
                "version": str(identity.get("version") or ""),
                "code_signature_verified": bool(
                    identity.get("code_signature_verified")
                ),
                "code_signature_team_identifier": str(
                    identity.get("code_signature_team_identifier") or ""
                ),
            }
        )
    else:
        raise UpgradeTransactionError(
            "MongoDB engine identity receipt has an unsupported runtime engine"
        )
    return common


def _mongo_bind_storage_anchor(
    path: Path,
    *,
    support: Path,
) -> dict[str, Any]:
    data_path = contained(path, support, "MongoDB receipt data path")
    validate_chain(data_path, owned_from=support)
    metadata = data_path.lstat()
    if (
        data_path.is_symlink()
        or not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != os.getuid()
    ):
        raise UpgradeTransactionError("MongoDB receipt data path is unsafe")
    anchor_names = {
        "WiredTiger",
        "WiredTiger.turtle",
        "WiredTiger.wt",
        "_mdb_catalog.wt",
        "storage.bson",
    }
    files: list[dict[str, Any]] = []
    for name in sorted(anchor_names):
        child = data_path / name
        if not child.exists() and not child.is_symlink():
            continue
        validate_chain(child, owned_from=support)
        child_metadata = child.lstat()
        if (
            child.is_symlink()
            or not stat.S_ISREG(child_metadata.st_mode)
            or child_metadata.st_uid != os.getuid()
        ):
            raise UpgradeTransactionError(
                "MongoDB storage identity anchor is unsafe"
            )
        files.append(
            {
                "name": name,
                "size": child_metadata.st_size,
                "sha256": sha256_file(child),
            }
        )
    if _path_has_durable_state(data_path) and not files:
        raise UpgradeTransactionError(
            "MongoDB storage identity markers are unavailable"
        )
    return {
        "kind": "bind-directory",
        "root_device": metadata.st_dev,
        "root_inode": metadata.st_ino,
        "files": files,
    }


def _docker_volume_anchor(
    identity: dict[str, Any],
) -> dict[str, Any]:
    volume = validate_docker_name(
        str(identity.get("volume_name") or ""),
        "MongoDB volume name",
    )
    try:
        docker = docker_ready()
    except UpgradeTransactionError as error:
        raise UpgradeTransactionError(
            "The recorded immutable Docker engine is unavailable"
        ) from error
    inspected = docker_command(
        docker,
        "volume",
        "inspect",
        volume,
        check=False,
    )
    if inspected.returncode != 0:
        raise UpgradeTransactionError(
            "The recorded MongoDB Docker volume is unavailable"
    )
    try:
        payload = json.loads(inspected.stdout.decode("utf-8"))
        if (
            not isinstance(payload, list)
            or len(payload) != 1
            or not isinstance(payload[0], dict)
            or payload[0].get("Name") != volume
        ):
            raise ValueError("unexpected Docker volume identity")
        record = payload[0]
    except (
        IndexError,
        TypeError,
        UnicodeDecodeError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        raise UpgradeTransactionError(
            "The recorded MongoDB Docker volume identity is unreadable"
        ) from error
    stable = {
        "name": volume,
        "driver": str(record.get("Driver") or ""),
        "scope": str(record.get("Scope") or ""),
        "labels": record.get("Labels") if isinstance(record.get("Labels"), dict) else {},
        "options": record.get("Options") if isinstance(record.get("Options"), dict) else {},
    }
    return {"kind": "docker-volume", **stable}


def _mongo_storage_anchor(
    identity: dict[str, Any],
    *,
    support: Path,
) -> dict[str, Any]:
    if identity.get("backend") == "app_support_bind":
        return _mongo_bind_storage_anchor(
            Path(str(identity.get("path") or "")),
            support=support,
        )
    if identity.get("backend") == "docker_named_volume":
        return _docker_volume_anchor(identity)
    raise UpgradeTransactionError(
        "MongoDB engine identity receipt has an unsupported storage backend"
    )


def _revalidate_native_receipt_engine(identity: dict[str, Any]) -> None:
    executable_raw = str(identity.get("executable") or "")
    if not executable_raw or not Path(executable_raw).is_absolute():
        raise UpgradeTransactionError(
            "The recorded native MongoDB engine is unavailable"
        )
    executable = lexical(Path(executable_raw))
    try:
        validate_chain(executable)
        metadata = executable.lstat()
    except (OSError, RuntimeError, UpgradeTransactionError) as error:
        raise UpgradeTransactionError(
            "The recorded native MongoDB engine is unavailable"
        ) from error
    expected_sha256 = str(identity.get("executable_sha256") or "")
    if (
        executable.is_symlink()
        or not stat.S_ISREG(metadata.st_mode)
        or executable.name != "mongod"
        or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256)
        or sha256_file(executable) != expected_sha256
    ):
        raise UpgradeTransactionError(
            "The recorded native MongoDB engine identity changed"
        )
    try:
        completed = subprocess.run(
            [str(executable), "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
            env={"PATH": os.environ.get("PATH", "")},
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise UpgradeTransactionError(
            "The recorded native MongoDB engine is unavailable"
        ) from error
    actual_version = next(
        (line.strip() for line in completed.stdout.splitlines() if line.strip()),
        "",
    )
    if completed.returncode != 0 or actual_version != identity.get("version"):
        raise UpgradeTransactionError(
            "The recorded native MongoDB engine version changed"
        )


def _revalidate_docker_receipt_engine(identity: dict[str, Any]) -> None:
    image_id = validate_docker_image_id(str(identity.get("image_id") or ""))
    try:
        docker = docker_ready()
    except UpgradeTransactionError as error:
        raise UpgradeTransactionError(
            "The recorded immutable Docker engine is unavailable"
        ) from error
    inspected = docker_command(
        docker,
        "image",
        "inspect",
        image_id,
        check=False,
    )
    if inspected.returncode != 0:
        raise UpgradeTransactionError(
            "The recorded immutable Docker engine is unavailable"
        )
    try:
        payload = json.loads(inspected.stdout.decode("utf-8"))
        if (
            not isinstance(payload, list)
            or len(payload) != 1
            or not isinstance(payload[0], dict)
            or payload[0].get("Id") != image_id
        ):
            raise ValueError("unexpected Docker image identity")
    except (
        UnicodeDecodeError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        raise UpgradeTransactionError(
            "The recorded immutable Docker engine identity is unreadable"
        ) from error


def _runtime_receipt_binding(
    support: Path,
    runtime_dir: Path,
) -> dict[str, str]:
    values: dict[str, str] = {}
    for env_file in (runtime_dir / "runtime.env", runtime_dir / "runtime.local.env"):
        values.update(parse_runtime_env(env_file))
    profile = (
        values.get("VIVENTIUM_RUNTIME_PROFILE", "isolated").strip().lower()
        or "isolated"
    )
    if profile not in {"compat", "isolated", "native"}:
        raise UpgradeTransactionError(
            "Active runtime profile has unknown MongoDB storage semantics"
        )
    container = validate_docker_name(
        values.get("VIVENTIUM_LOCAL_MONGO_CONTAINER", "viventium-mongodb"),
        "MongoDB container name",
    )
    volume = validate_docker_name(
        values.get("VIVENTIUM_LOCAL_MONGO_VOLUME", f"{container}-data"),
        "MongoDB volume name",
    )
    explicit_data = values.get("VIVENTIUM_LOCAL_MONGO_DATA_PATH", "").strip()
    return {
        "profile": profile,
        "container_name": container,
        "volume_name": volume,
        "configured_path": str(
            _configured_native_data_path(support, profile, explicit_data)
        ),
        "install_mode": values.get("VIVENTIUM_INSTALL_MODE", "").strip().lower(),
        "configured_image": validate_docker_image(
            values.get("MONGO_IMAGE", MONGO_IMAGE_DEFAULT)
        ),
        "explicit_data": explicit_data,
    }


def _validate_receipt_runtime_binding(
    identity: dict[str, Any],
    binding: dict[str, str],
) -> None:
    if identity.get("profile") != binding["profile"]:
        raise UpgradeTransactionError(
            "MongoDB engine identity receipt belongs to another runtime profile"
        )
    if identity.get("backend") == "app_support_bind":
        if lexical(Path(str(identity.get("path") or ""))) != lexical(
            Path(binding["configured_path"])
        ):
            raise UpgradeTransactionError(
                "MongoDB engine identity receipt belongs to another data path"
            )
    elif identity.get("backend") == "docker_named_volume":
        if identity.get("volume_name") != binding["volume_name"]:
            raise UpgradeTransactionError(
                "MongoDB engine identity receipt belongs to another Docker volume"
            )
    if (
        identity.get("runtime_engine") == "docker"
        and identity.get("container_name") != binding["container_name"]
    ):
        raise UpgradeTransactionError(
            "MongoDB engine identity receipt belongs to another container"
        )


def record_mongo_engine_identity(
    support: Path,
    runtime_dir: Path,
) -> dict[str, Any]:
    support = lexical(support)
    runtime_dir = contained(
        lexical(runtime_dir),
        support,
        "generated runtime",
    )
    inventory, _ = _observe_running_mongo_storage(support, runtime_dir)
    if inventory is None or (
        inventory.get("runtime_engine") == "docker"
        and inventory.get("container_running") is not True
    ):
        raise UpgradeTransactionError(
            "No directly observed running MongoDB engine is available"
        )
    binding = _runtime_receipt_binding(support, runtime_dir)
    _validate_receipt_runtime_binding(inventory, binding)
    payload = {
        "schema_version": MONGO_ENGINE_IDENTITY_SCHEMA_VERSION,
        "recorded_at": utc_stamp(),
        "sealed_at": "",
        "clean_stopped": False,
        "identity": inventory,
        "storage_anchor": None,
    }
    return _write_mongo_engine_receipt(support, payload)


def _validate_native_mongo_pid_file(
    path: Path,
    *,
    support: Path,
) -> dict[str, Any] | None:
    path = contained(lexical(path), support, "Native MongoDB PID record")
    if not path.exists() and not path.is_symlink():
        return None
    validate_chain(path, owned_from=support)
    metadata = path.lstat()
    if (
        path.is_symlink()
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
    ):
        raise UpgradeTransactionError("Native MongoDB PID record is unsafe")
    parent_metadata = path.parent.lstat()
    flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise UpgradeTransactionError("Native MongoDB PID record is unreadable") from error
    try:
        opened_metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(opened_metadata.st_mode)
            or opened_metadata.st_uid != os.getuid()
            or opened_metadata.st_dev != metadata.st_dev
            or opened_metadata.st_ino != metadata.st_ino
        ):
            raise UpgradeTransactionError("Native MongoDB PID record changed during validation")
        payload = os.read(descriptor, 128)
        if len(payload) == 128 and os.read(descriptor, 1):
            raise UpgradeTransactionError("Native MongoDB PID record is unreadable")
        recorded_pid = int(payload.decode("utf-8").strip())
    except (OSError, UnicodeError, ValueError) as error:
        raise UpgradeTransactionError("Native MongoDB PID record is unreadable") from error
    finally:
        os.close(descriptor)
    if recorded_pid <= 0:
        raise UpgradeTransactionError("Native MongoDB PID record is invalid")
    return {
        "path": path,
        "pid": recorded_pid,
        "device": metadata.st_dev,
        "inode": metadata.st_ino,
        "parent_device": parent_metadata.st_dev,
        "parent_inode": parent_metadata.st_ino,
    }


def _remove_validated_native_mongo_pid_file(
    record: dict[str, Any] | None,
    *,
    pid: int,
) -> bool:
    if record is None or record["pid"] != pid:
        return False
    path = Path(record["path"])
    parent_flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        parent_descriptor = os.open(path.parent, parent_flags)
    except OSError:
        return False
    try:
        parent_metadata = os.fstat(parent_descriptor)
        if (
            parent_metadata.st_dev != record["parent_device"]
            or parent_metadata.st_ino != record["parent_inode"]
        ):
            return False
        try:
            current_metadata = os.stat(
                path.name,
                dir_fd=parent_descriptor,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            return True
        if (
            not stat.S_ISREG(current_metadata.st_mode)
            or current_metadata.st_uid != os.getuid()
            or current_metadata.st_dev != record["device"]
            or current_metadata.st_ino != record["inode"]
        ):
            return False
        file_flags = (
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        try:
            file_descriptor = os.open(
                path.name,
                file_flags,
                dir_fd=parent_descriptor,
            )
        except OSError:
            return False
        try:
            opened_metadata = os.fstat(file_descriptor)
            if (
                opened_metadata.st_dev != record["device"]
                or opened_metadata.st_ino != record["inode"]
            ):
                return False
            payload = os.read(file_descriptor, 128)
            if len(payload) == 128 and os.read(file_descriptor, 1):
                return False
            if int(payload.decode("utf-8").strip()) != pid:
                return False
        except (OSError, UnicodeError, ValueError):
            return False
        finally:
            os.close(file_descriptor)
        try:
            os.unlink(path.name, dir_fd=parent_descriptor)
        except FileNotFoundError:
            return True
        os.fsync(parent_descriptor)
        return True
    finally:
        os.close(parent_descriptor)


def discard_stale_native_mongo_pid_file(
    support: Path,
    path: Path,
) -> dict[str, Any]:
    support = lexical(support)
    record = _validate_native_mongo_pid_file(path, support=support)
    if record is None:
        return {"removed": False, "pid": None}
    pid = int(record["pid"])
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        pass
    except OSError as error:
        raise UpgradeTransactionError(
            "Native MongoDB PID liveness could not be verified"
        ) from error
    else:
        raise UpgradeTransactionError(
            "Native MongoDB PID record still identifies a live process"
        )
    if not _remove_validated_native_mongo_pid_file(record, pid=pid):
        raise UpgradeTransactionError(
            "Native MongoDB stale PID record changed before cleanup"
        )
    return {"removed": True, "pid": pid}


def stop_recorded_native_mongo_engine(
    support: Path,
    runtime_dir: Path,
    *,
    pid_files: tuple[Path, ...] = (),
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    support = lexical(support)
    runtime_dir = contained(
        lexical(runtime_dir),
        support,
        "generated runtime",
    )
    payload = _load_mongo_engine_receipt(support)
    if payload is None:
        raise UpgradeTransactionError("MongoDB running engine receipt is missing")
    identity = payload["identity"]
    binding = _runtime_receipt_binding(support, runtime_dir)
    _validate_receipt_runtime_binding(identity, binding)
    if identity.get("runtime_engine") != "native":
        return payload
    if payload.get("clean_stopped") is True:
        return payload
    expected_process = {
        key: identity.get(key)
        for key in (
            "pid",
            "process_started_at",
            "executable",
            "executable_sha256",
            "arguments",
            "version",
            "code_signature_verified",
            "code_signature_team_identifier",
        )
    }
    pid = expected_process["pid"]
    if not isinstance(pid, int) or pid <= 0:
        raise UpgradeTransactionError(
            "MongoDB running engine receipt has an invalid native PID"
        )
    profile = str(identity.get("profile") or "")
    default_pid_files = (
        support / "state" / "native" / "mongod.pid",
        support / "state" / "runtime" / profile / "mongodb-native.pid",
    )
    validated_pid_records = [
        _validate_native_mongo_pid_file(
            pid_file,
            support=support,
        )
        for pid_file in dict.fromkeys((*default_pid_files, *pid_files))
    ]
    try:
        observed = inspect_native_mongo_process(pid)
    except UpgradeTransactionError as error:
        if "is not running" not in str(error):
            raise
    else:
        if observed != expected_process:
            raise UpgradeTransactionError(
                "Native MongoDB process identity changed before stop"
            )
        if native_mongo_dbpath(observed) != lexical(
            Path(str(identity.get("path") or ""))
        ):
            raise UpgradeTransactionError(
                "Native MongoDB process data path changed before stop"
            )
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError as error:
            raise UpgradeTransactionError(
                "Native MongoDB process could not be stopped"
            ) from error
        deadline = time.monotonic() + max(timeout_seconds, 0.1)
        while True:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            except OSError as error:
                raise UpgradeTransactionError(
                    "Native MongoDB process exit could not be verified"
                ) from error
            try:
                current_started_at = _process_field(pid, "lstart")
            except UpgradeTransactionError:
                break
            if current_started_at != expected_process["process_started_at"]:
                break
            if time.monotonic() >= deadline:
                raise UpgradeTransactionError(
                    "Native MongoDB process did not stop before the timeout"
                )
            time.sleep(0.1)
    for pid_record in validated_pid_records:
        _remove_validated_native_mongo_pid_file(pid_record, pid=pid)
    return payload


def seal_mongo_engine_identity(
    support: Path,
    runtime_dir: Path,
) -> dict[str, Any]:
    support = lexical(support)
    runtime_dir = contained(
        lexical(runtime_dir),
        support,
        "generated runtime",
    )
    payload = _load_mongo_engine_receipt(support)
    if payload is None:
        raise UpgradeTransactionError(
            "MongoDB running engine receipt is missing"
        )
    identity = payload["identity"]
    binding = _runtime_receipt_binding(support, runtime_dir)
    _validate_receipt_runtime_binding(identity, binding)
    observed, _ = _observe_running_mongo_storage(support, runtime_dir)
    if observed is not None:
        if (
            observed.get("runtime_engine") == "native"
            or observed.get("container_running") is True
        ):
            raise UpgradeTransactionError(
                "MongoDB engine is still running and cannot be sealed"
            )
        if _mongo_identity_static_view(observed) != _mongo_identity_static_view(
            identity
        ):
            raise UpgradeTransactionError(
                "MongoDB stopped engine identity changed before sealing"
            )
    sealed = dict(payload)
    sealed["sealed_at"] = utc_stamp()
    sealed["clean_stopped"] = True
    sealed["storage_anchor"] = _mongo_storage_anchor(
        identity,
        support=support,
    )
    return _write_mongo_engine_receipt(support, sealed)


def _stopped_mongo_inventory_from_receipt(
    support: Path,
    runtime_dir: Path,
) -> dict[str, Any] | None:
    payload = _load_mongo_engine_receipt(support)
    if payload is None:
        return None
    if payload.get("clean_stopped") is not True:
        raise UpgradeTransactionError(
            "MongoDB engine identity receipt does not prove a cleanly stopped engine"
        )
    identity = payload["identity"]
    binding = _runtime_receipt_binding(support, runtime_dir)
    _validate_receipt_runtime_binding(identity, binding)
    if identity.get("runtime_engine") == "native":
        _revalidate_native_receipt_engine(identity)
    elif identity.get("runtime_engine") == "docker":
        _revalidate_docker_receipt_engine(identity)
    else:
        raise UpgradeTransactionError(
            "MongoDB engine identity receipt has an unsupported runtime engine"
        )
    actual_anchor = _mongo_storage_anchor(identity, support=support)
    if actual_anchor != payload.get("storage_anchor"):
        raise UpgradeTransactionError(
            "MongoDB storage identity changed after its clean stop"
        )
    inventory = dict(identity)
    inventory["observed_from"] = "engine_identity_receipt"
    inventory["receipt_sha256"] = payload["receipt_sha256"]
    return inventory


def mongo_storage_inventory(
    support: Path,
    runtime_dir: Path,
) -> tuple[dict[str, Any], list[tuple[str, Path]]]:
    support = lexical(support)
    runtime_dir = contained(
        lexical(runtime_dir),
        support,
        "generated runtime",
    )
    binding = _runtime_receipt_binding(support, runtime_dir)
    inventory, extra_surfaces = _observe_running_mongo_storage(
        support,
        runtime_dir,
    )
    if inventory is None:
        inventory = _stopped_mongo_inventory_from_receipt(
            support,
            runtime_dir,
        )
    if inventory is not None:
        if inventory["backend"] == "app_support_bind":
            data_path = Path(str(inventory["path"]))
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
        return inventory, extra_surfaces

    configured_path = Path(binding["configured_path"])
    if _path_has_durable_state(configured_path):
        raise UpgradeTransactionError(
            "Existing MongoDB runtime engine cannot be proven from a running "
            "process/container or a clean engine receipt; restart the existing "
            "runtime, stop it cleanly, then retry"
        )
    docker: str | None = None
    try:
        docker = docker_ready()
    except UpgradeTransactionError:
        pass
    if docker is not None and docker_volume_exists(
        docker,
        binding["volume_name"],
    ):
        raise UpgradeTransactionError(
            "Existing MongoDB Docker volume has no exact immutable engine receipt; "
            "restart the existing runtime, stop it cleanly, then retry"
        )

    explicit_data = binding["explicit_data"]
    profile = binding["profile"]
    install_mode = binding["install_mode"]
    if explicit_data or profile in {"isolated", "native"} or install_mode != "docker":
        data_path = configured_path
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
            "runtime_engine": "native",
            "profile": profile,
            "path": str(data_path),
            "observed_from": "configured_empty_storage",
        }, extra_surfaces
    return {
        "backend": "docker_named_volume",
        "runtime_engine": "docker",
        "profile": profile,
        "volume_name": binding["volume_name"],
        "image": binding["configured_image"],
        "observed_from": "configured_empty_storage",
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
        (
            MONGO_ENGINE_IDENTITY_SURFACE_LABEL,
            _mongo_receipt_path(support),
            False,
        ),
        ("runtime-state", support / "state" / "runtime", False),
        ("bootstrap-python", support / "state" / "bootstrap-python", True),
        ("legacy-mongo-state", support / "state" / "mongo-data", False),
        ("native-data", support / "data", False),
        (HELPER_CONFIG_SURFACE_LABEL, helper_config_path(support), False),
        (
            "telegram-user-configs",
            support / "state" / "telegram-user-configs",
            False,
        ),
        (
            "telegram-codex-pairings",
            support / "state" / "telegram-codex" / "paired-users",
            False,
        ),
    ]
    candidates.extend((label, path, False) for label, path in (extra_surfaces or []))
    return candidates


def external_checkpoint_surface_candidates(repo: Path) -> list[tuple[str, Path]]:
    return [
        (
            LIBRECHAT_ENV_SURFACE_LABEL,
            librechat_runtime_env_path(repo),
        )
    ]


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
        record = {
            "label": label,
            "path": str(path),
            "backup": str(backup),
            "manifest": manifest,
            "allow_symlinks": allow_symlinks,
        }
        if label == LIBRECHAT_ENV_SURFACE_LABEL:
            record["semantic_manifest"] = librechat_env_semantic_manifest(backup)
        elif label == HELPER_CONFIG_SURFACE_LABEL:
            record["semantic_manifest"] = helper_config_semantic_manifest(backup)
        manifests.append(record)
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
    extra_surfaces.extend(external_checkpoint_surface_candidates(repo))
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
                docker_storage_image(storage_inventory),
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
            "telegram_preference_root": str(
                lexical(Path(args.telegram_preference_root))
            )
            if args.telegram_preference_root
            else "",
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
                "telegram_preference_root": str(
                    ledger.get("telegram_preference_root") or ""
                ),
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
    extra_surfaces.extend(
        external_checkpoint_surface_candidates(Path(ledger["repo_root"]))
    )
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
        image = docker_storage_image(storage_inventory)
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
        image = docker_storage_image(storage_inventory)
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
    image = docker_storage_image(storage)
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
    image = docker_storage_image(storage)
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
    ledger["librechat_env_continuity"] = verify_librechat_env_continuity(ledger)
    ledger["helper_config_continuity"] = verify_helper_config_continuity(ledger)
    ledger["static_personalization_continuity"] = (
        verify_static_personalization_continuity(ledger)
    )
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
                "telegram_preference_root": str(
                    ledger.get("telegram_preference_root") or ""
                ),
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
    begin.add_argument("--telegram-preference-root")
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

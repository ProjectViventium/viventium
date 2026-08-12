#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import sqlite3
import stat
from pathlib import Path, PurePosixPath
from typing import Any

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
MAX_CONFIG_BYTES = 4 * 1024 * 1024
MAX_CHANNEL_JSON_BYTES = 16 * 1024 * 1024
MAX_SCHEDULES_DATABASE_BYTES = 8 * 1024 * 1024 * 1024

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
    return {
        "schemaVersion": SCHEMA_VERSION,
        "bundleKind": bundle_kind,
        "declaredComplete": bundle_kind == "complete",
        # Structural, content, and checksum validation is necessary but cannot prove that
        # the not-yet-implemented public apply engine can recover an independent target.
        "recoverable": False,
        "restoreEngine": "not_implemented",
        "semanticValidation": "not_performed",
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--snapshot-dir", required=True)
    validate_parser.add_argument("--allow-partial", action="store_true")
    validate_parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

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
        print("Complete Viventium bundle structure and payload integrity validated; restore is not yet proven.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

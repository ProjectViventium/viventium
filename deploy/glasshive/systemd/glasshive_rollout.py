#!/usr/bin/env python3
"""Fail-closed, journaled GlassHive hosted release orchestration.

The public helper owns only the portable parts of a rollout: immutable release
verification, SQLite backup/rehearsal/restore, split-service lifecycle, local
readiness, and transaction recovery.  Deployment-specific state snapshots,
edge routing, and authenticated browser/MCP acceptance are explicit executable
adapter contracts.  They receive JSON on stdin and must return one bounded JSON
object on stdout; the helper never guesses cloud- or proxy-specific commands.
"""

from __future__ import annotations

import argparse
import fcntl
import grp
import hashlib
import json
import os
import posixpath
import pwd
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

HOSTED_MUTATION_LOCK = Path("/run/lock/glasshive-rollout.lock")
LINK_REF_SHARED_STATE_DIR_NAME = "link-refs-shared"
RUNTIME_LINK_REF_DATABASE_NAME = "link_refs.sqlite3"
LINK_REF_SHARED_GROUP = "glasshive-state"
PROVIDER_ACCOUNT_STATE_DIR_NAME = "provider_accounts"

MANIFEST_NAME = "glasshive-release.json"
RELEASE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
ALLOWED_ACTIVE_ENV_KEYS = {
    "DOCKER_HOST",
    "GLASSHIVE_AUTH_STATE_PATH",
    "GLASSHIVE_BACKGROUND_CONSUMERS_ENABLED",
    "GLASSHIVE_COMPONENT_REVISION",
    "GLASSHIVE_LINK_REF_STATE_PATH",
    "GLASSHIVE_LINK_REF_SHARED_GROUP",
    "GLASSHIVE_MCP_PORT",
    "GLASSHIVE_PARENT_REVISION",
    "GLASSHIVE_PROVIDER_ACCOUNT_HOME_ROOT",
    "GLASSHIVE_RECONCILE_ON_STARTUP",
    "GLASSHIVE_RELEASE_ID",
    "GLASSHIVE_RUNTIME_BASE_URL",
    "GLASSHIVE_RUNTIME_PORT",
    "GLASSHIVE_STATE_DIR",
    "GLASSHIVE_UI_PORT",
    "GLASSHIVE_WATCH_SESSION_STATE_PATH",
    "WPR_DB_PATH",
    "WPR_MCP_BASE_URL",
}
SECRET_KEY_FRAGMENTS = ("SECRET", "TOKEN", "PASSWORD", "PRIVATE", "CLIENT_KEY", "API_KEY")
GROUP_SERVICES = (
    "glasshive-ui.service",
    "glasshive-mcp.service",
    "glasshive-runtime.service",
)
START_SERVICES = tuple(reversed(GROUP_SERVICES))
ACCEPTANCE_CHECKS: dict[str, tuple[str, ...]] = {
    "candidate": (
        "authenticated_mcp_initialize",
        "browser_identity_flow",
        "designed_root",
        "runtime_release_provenance",
        "ui_release_provenance",
        "mcp_release_provenance",
        "token_scope_claim_exact",
        "token_audience_exact",
        "token_client_id_allowed",
        "token_tenant_and_subject_exact",
        "auth_callback_query_not_logged",
        "runtime_artifact_refs_writable",
        "cross_service_link_refs_resolvable",
        "provider_account_state_persisted",
    ),
    "preflight": (
        "authenticated_mcp_initialize",
        "browser_identity_flow",
        "designed_root",
        "public_jwks",
        "spoof_headers_overwritten",
        "runtime_not_public",
    ),
    "live": (
        "authenticated_mcp_initialize",
        "browser_identity_flow",
        "designed_root",
        "public_jwks",
        "root_to_glass_drive_bff",
        "auth_to_glass_drive_bff",
        "login_to_glass_drive_bff",
        "static_to_glass_drive_bff",
        "api_to_glass_drive_bff",
        "confirm_change_to_glass_drive_bff",
        "short_links_to_glass_drive_bff",
        "watch_to_glass_drive_bff",
        "desktop_to_glass_drive_bff",
        "novnc_websocket_to_glass_drive_bff",
        "runtime_ui_proxy_to_glass_drive_bff",
        "runtime_v1_proxy_to_glass_drive_bff",
        "favicon_to_glass_drive_bff",
        "health_to_glass_drive_bff",
        "all_browser_routes_same_release",
        "mcp_to_mcp_service",
        "mcp_metadata_to_mcp_service",
        "mcp_no_oauth2_proxy_html_redirect",
        "jwks_to_glass_drive_bff",
        "identity_header_families_scrubbed",
        "browser_csrf_header_preserved",
        "runtime_artifact_refs_writable",
        "cross_service_link_refs_resolvable",
        "provider_account_state_persisted",
        "runtime_not_public",
        "runtime_release_provenance",
        "ui_release_provenance",
        "mcp_release_provenance",
        "token_scope_claim_exact",
        "token_audience_exact",
        "token_client_id_allowed",
        "token_tenant_and_subject_exact",
        "auth_callback_query_not_logged",
    ),
    "rollback": (
        "authenticated_mcp_initialize",
        "browser_identity_flow",
        "designed_root",
        "public_jwks",
        "spoof_headers_overwritten",
        "provider_account_state_persisted",
        "runtime_not_public",
    ),
}


class RolloutError(RuntimeError):
    """A release gate failed and the helper must not claim success."""


def _open_mutation_lock(
    lock_path: Path,
    *,
    expected_uid: int | None = None,
):
    """Open the shared deployment lock without trusting its directory entry."""

    owner_uid = os.geteuid() if expected_uid is None else int(expected_uid)
    lock_path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(lock_path, flags, 0o600)
    except OSError as exc:
        raise RolloutError("GlassHive deployment lock could not be opened safely") from exc
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != owner_uid:
            raise RolloutError("GlassHive deployment lock has an unexpected owner or type")
        os.fchmod(descriptor, 0o600)
        return os.fdopen(descriptor, "r+", encoding="utf-8")
    except BaseException:
        os.close(descriptor)
        raise


class DatabaseConfig:
    def __init__(
        self,
        *,
        name: str,
        path: Path,
        env_name: str,
        candidate_relative: Path,
        invariants: list[dict[str, object]],
        post_migration_invariants: list[dict[str, object]] | None = None,
        allow_create_if_missing: bool = False,
        restore_mode: int = 0o660,
    ) -> None:
        self.name = name
        self.path = Path(path)
        self.env_name = env_name
        self.candidate_relative = Path(candidate_relative)
        self.invariants = invariants
        self.post_migration_invariants = list(post_migration_invariants or [])
        self.allow_create_if_missing = bool(allow_create_if_missing)
        self.restore_mode = int(restore_mode)


class RolloutConfig:
    def __init__(
        self,
        *,
        release_id: str,
        release_dir: Path,
        releases_root: Path,
        current_symlink: Path,
        runtime_active_env: Path,
        gateway_active_env: Path,
        state_dir: Path,
        transactions_dir: Path,
        candidate_ports: dict[str, int],
        expected: dict[str, object],
        databases: list[DatabaseConfig],
        ingress_adapter: Path,
        state_adapter: Path,
        acceptance_adapter: Path,
        runtime_user: str,
        candidate_state_root: Path | None = None,
        lock_file: Path | None = None,
        runtime_env_file: Path = Path("/etc/viventium/glasshive/runtime.env"),
        gateway_env_file: Path = Path("/etc/viventium/glasshive/gateway.env"),
        probe_timeout_sec: float = 60.0,
    ) -> None:
        self.release_id = release_id
        self.release_dir = Path(release_dir)
        self.releases_root = Path(releases_root)
        self.current_symlink = Path(current_symlink)
        self.runtime_active_env = Path(runtime_active_env)
        self.gateway_active_env = Path(gateway_active_env)
        self.state_dir = Path(state_dir)
        self.transactions_dir = Path(transactions_dir)
        self.candidate_state_root = Path(candidate_state_root) if candidate_state_root else self.state_dir / ".rollout-candidates"
        self.candidate_ports = dict(candidate_ports)
        self.expected = dict(expected)
        self.databases = list(databases)
        self.ingress_adapter = Path(ingress_adapter)
        self.state_adapter = Path(state_adapter)
        self.acceptance_adapter = Path(acceptance_adapter)
        self.runtime_user = runtime_user
        self.lock_file = Path(lock_file) if lock_file else self.transactions_dir / "rollout.lock"
        self.runtime_env_file = Path(runtime_env_file)
        self.gateway_env_file = Path(gateway_env_file)
        self.probe_timeout_sec = float(probe_timeout_sec)


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _canonical_json_sha256(value: object) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_write(
    path: Path,
    content: bytes,
    *,
    mode: int,
    owner: tuple[int, int] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, mode)
        if owner is not None:
            os.fchown(descriptor, owner[0], owner[1])
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _validate_identifier(value: str, *, field: str) -> str:
    if not IDENTIFIER_RE.fullmatch(str(value)):
        raise RolloutError(f"invalid SQLite identifier for {field}")
    return str(value)


def _quoted_identifier(value: str, *, field: str) -> str:
    return f'"{_validate_identifier(value, field=field)}"'


def _read_only_connection(path: Path) -> sqlite3.Connection:
    if not path.is_file() or path.is_symlink():
        raise RolloutError(f"SQLite database is missing or unsafe: {path}")
    uri = path.resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True, timeout=5)
    connection.execute("PRAGMA query_only=ON")
    return connection


def _database_health(connection: sqlite3.Connection) -> tuple[str, str, int]:
    quick_rows = [str(row[0]) for row in connection.execute("PRAGMA quick_check")]
    integrity_rows = [str(row[0]) for row in connection.execute("PRAGMA integrity_check")]
    foreign_rows = list(connection.execute("PRAGMA foreign_key_check"))
    quick = "ok" if quick_rows == ["ok"] else ";".join(quick_rows[:10])
    integrity = "ok" if integrity_rows == ["ok"] else ";".join(integrity_rows[:10])
    if quick != "ok" or integrity != "ok":
        raise RolloutError("SQLite integrity check failed")
    if foreign_rows:
        raise RolloutError(f"SQLite foreign key check found {len(foreign_rows)} violation(s)")
    return quick, integrity, len(foreign_rows)


def _identity_digest(
    connection: sqlite3.Connection,
    *,
    table: str,
    columns: Sequence[str],
) -> str:
    quoted_table = _quoted_identifier(table, field="table")
    quoted_columns = [_quoted_identifier(column, field="identity column") for column in columns]
    statement = f"SELECT {', '.join(quoted_columns)} FROM {quoted_table} ORDER BY {', '.join(quoted_columns)}"
    digest = hashlib.sha256()
    for row in connection.execute(statement):
        encoded = json.dumps(
            [None if value is None else str(value) for value in row],
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def inspect_database(path: Path, invariants: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Return public-safe integrity/count/identity evidence for one SQLite file."""

    with _read_only_connection(Path(path)) as connection:
        quick, integrity, foreign_count = _database_health(connection)
        master_rows = list(
            connection.execute(
                "SELECT type, name, COALESCE(sql, '') FROM sqlite_master "
                "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
            )
        )
        schema_hash = hashlib.sha256(
            json.dumps(master_rows, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        ).hexdigest()
        available_tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        schema_ledger: list[dict[str, object]] = []
        if "glasshive_schema_versions" in available_tables:
            for component, version in connection.execute(
                "SELECT component, version FROM glasshive_schema_versions ORDER BY component"
            ):
                schema_ledger.append({"component": str(component), "version": int(version)})
        tables: dict[str, object] = {}
        for raw in invariants:
            table = _validate_identifier(str(raw.get("table") or ""), field="table")
            if table not in available_tables:
                raise RolloutError(f"required invariant table is absent: {table}")
            raw_columns = raw.get("identity_columns")
            if not isinstance(raw_columns, list) or not raw_columns:
                raise RolloutError(f"invariant {table} requires identity_columns")
            columns = [_validate_identifier(str(item), field="identity column") for item in raw_columns]
            actual_columns = {
                str(row[1])
                for row in connection.execute(f"PRAGMA table_info({_quoted_identifier(table, field='table')})")
            }
            missing = sorted(set(columns) - actual_columns)
            if missing:
                raise RolloutError(f"invariant table {table} is missing identity columns")
            row_count = int(
                connection.execute(
                    f"SELECT COUNT(*) FROM {_quoted_identifier(table, field='table')}"
                ).fetchone()[0]
            )
            tables[table] = {
                "row_count": row_count,
                "identity_columns": columns,
                "identity_sha256": _identity_digest(connection, table=table, columns=columns),
            }
        return {
            "quick_check": quick,
            "integrity_check": integrity,
            "foreign_key_violations": foreign_count,
            "schema_sha256": schema_hash,
            "schema_ledger": schema_ledger,
            "tables": tables,
        }


def _sqlite_backup(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    try:
        with _read_only_connection(source) as source_connection:
            destination_connection = sqlite3.connect(temporary)
            try:
                source_connection.backup(destination_connection)
                destination_connection.commit()
            finally:
                destination_connection.close()
        os.chmod(temporary, 0o600)
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
        _fsync_directory(destination.parent)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def backup_and_restore_test(
    *,
    source: Path,
    backup: Path,
    restore_test: Path,
    invariants: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Use SQLite's online backup API, then restore that backup into another file and compare."""

    source_receipt = inspect_database(source, invariants)
    _sqlite_backup(source, backup)
    backup_receipt = inspect_database(backup, invariants)
    compare_migration_invariants(source_receipt, backup_receipt)
    _sqlite_backup(backup, restore_test)
    restored_receipt = inspect_database(restore_test, invariants)
    compare_migration_invariants(backup_receipt, restored_receipt)
    return backup_receipt


def compare_migration_invariants(before: Mapping[str, object], after: Mapping[str, object]) -> None:
    before_tables = before.get("tables")
    after_tables = after.get("tables")
    if not isinstance(before_tables, dict) or not isinstance(after_tables, dict):
        raise RolloutError("database invariant evidence is malformed")
    for table, expected in before_tables.items():
        actual = after_tables.get(table)
        if not isinstance(expected, dict) or not isinstance(actual, dict):
            raise RolloutError(f"migration invariant drift for table {table}")
        if expected.get("row_count") != actual.get("row_count"):
            raise RolloutError(f"migration invariant drift for table {table}: row count")
        if expected.get("identity_sha256") != actual.get("identity_sha256"):
            raise RolloutError(f"migration invariant drift for table {table}: owner/tenant sample")
    before_ledger = before.get("schema_ledger")
    after_ledger = after.get("schema_ledger")
    if isinstance(before_ledger, list) and isinstance(after_ledger, list):
        prior_versions = {
            str(item.get("component")): int(item.get("version", 0))
            for item in before_ledger
            if isinstance(item, dict)
        }
        current_versions = {
            str(item.get("component")): int(item.get("version", 0))
            for item in after_ledger
            if isinstance(item, dict)
        }
        for component, prior_version in prior_versions.items():
            if current_versions.get(component, -1) < prior_version:
                raise RolloutError(f"migration schema ledger regressed for component {component}")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_entries(release_dir: Path) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for path in sorted(release_dir.rglob("*"), key=lambda value: value.as_posix()):
        relative = path.relative_to(release_dir).as_posix()
        if relative == MANIFEST_NAME:
            continue
        metadata = path.lstat()
        if stat.S_ISLNK(metadata.st_mode):
            try:
                resolved = path.resolve(strict=True)
            except (OSError, RuntimeError) as exc:
                raise RolloutError(f"release contains an unresolved symlink: {relative}") from exc
            entry: dict[str, object] = {
                "path": relative,
                "type": "symlink",
                "target": os.readlink(path),
                "mode": stat.S_IMODE(metadata.st_mode),
            }
            if resolved.is_file():
                entry["resolved_type"] = "file"
                entry["resolved_size"] = resolved.stat().st_size
                entry["resolved_sha256"] = _file_sha256(resolved)
            elif resolved.is_dir():
                entry["resolved_type"] = "directory"
            else:
                raise RolloutError(f"release symlink has an unsupported target: {relative}")
            entries.append(entry)
        elif stat.S_ISDIR(metadata.st_mode):
            entries.append(
                {
                    "path": relative,
                    "type": "directory",
                    "mode": stat.S_IMODE(metadata.st_mode),
                }
            )
        elif stat.S_ISREG(metadata.st_mode):
            entries.append(
                {
                    "path": relative,
                    "type": "file",
                    "sha256": _file_sha256(path),
                    "size": metadata.st_size,
                    "mode": stat.S_IMODE(metadata.st_mode),
                }
            )
        else:
            raise RolloutError(f"release contains unsupported filesystem entry: {relative}")
    return entries


def write_release_manifest(
    release_dir: Path,
    *,
    release_id: str,
    parent_revision: str,
    glasshive_revision: str,
) -> dict[str, object]:
    if not RELEASE_ID_RE.fullmatch(release_id):
        raise RolloutError("invalid release id")
    if not re.fullmatch(r"[0-9a-f]{40}", parent_revision):
        raise RolloutError("invalid parent revision")
    if not re.fullmatch(r"[0-9a-f]{40}", glasshive_revision):
        raise RolloutError("invalid GlassHive revision")
    release_dir = Path(release_dir)
    manifest = {
        "schema_version": 1,
        "release_id": release_id,
        "parent_revision": parent_revision,
        "glasshive_revision": glasshive_revision,
        "entries": _manifest_entries(release_dir),
    }
    _atomic_write(release_dir / MANIFEST_NAME, _json_bytes(manifest), mode=0o444)
    return manifest


def _read_release_manifest(release_dir: Path) -> dict[str, object]:
    release_dir = Path(release_dir)
    manifest_path = release_dir / MANIFEST_NAME
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise RolloutError("release manifest is missing or unsafe")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RolloutError("release manifest is unreadable") from exc
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise RolloutError("release manifest schema is unsupported")
    release_id = manifest.get("release_id")
    if not isinstance(release_id, str) or not RELEASE_ID_RE.fullmatch(release_id):
        raise RolloutError("release manifest identity is invalid")
    return manifest


def read_release_identity(release_dir: Path) -> str:
    """Return a validated manifest identity without trusting raw JSON at the call site."""

    return str(_read_release_manifest(release_dir)["release_id"])


def release_provenance(release_dir: Path) -> dict[str, str]:
    release_id = read_release_identity(release_dir)
    manifest = verify_release_manifest(release_dir, expected_release_id=release_id)
    parent_revision = manifest.get("parent_revision")
    glasshive_revision = manifest.get("glasshive_revision")
    if not isinstance(parent_revision, str) or not re.fullmatch(r"[0-9a-f]{40}", parent_revision):
        raise RolloutError("release manifest parent revision is invalid")
    if not isinstance(glasshive_revision, str) or not re.fullmatch(r"[0-9a-f]{40}", glasshive_revision):
        raise RolloutError("release manifest GlassHive revision is invalid")
    return {
        "release_id": release_id,
        "parent_revision": parent_revision,
        "glasshive_revision": glasshive_revision,
    }


def verify_release_manifest(release_dir: Path, *, expected_release_id: str) -> dict[str, object]:
    release_dir = Path(release_dir)
    manifest = _read_release_manifest(release_dir)
    if manifest.get("release_id") != expected_release_id:
        raise RolloutError("release manifest identity mismatch")
    expected_entries = manifest.get("entries")
    if expected_entries != _manifest_entries(release_dir):
        raise RolloutError("release manifest content mismatch")
    return manifest


def validate_sealed_release(release_dir: Path) -> None:
    release_dir = Path(release_dir)
    for path in [release_dir, *release_dir.rglob("*")]:
        if path.is_symlink():
            continue
        metadata = path.stat()
        if metadata.st_uid != 0:
            raise RolloutError("staged release contains a non-root-owned entry")
        if stat.S_IMODE(metadata.st_mode) & 0o022:
            raise RolloutError("staged release contains a group/other-writable entry")


def _run_checked(command: Sequence[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        list(command),
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=600,
        check=False,
    )
    if result.returncode != 0:
        raise RolloutError(f"release staging command failed: {Path(command[0]).name}")
    return result


def _git_value(source: Path, *arguments: str) -> str:
    return _run_checked(["/usr/bin/git", *arguments], cwd=source).stdout.strip()


def _extract_validated_archive(bundle: tarfile.TarFile, destination: Path) -> None:
    """Extract a git archive without relying on version-specific tar filters."""

    members = bundle.getmembers()
    paths: set[tuple[str, ...]] = set()
    symlinks: set[tuple[str, ...]] = set()
    for member in members:
        raw_name = member.name
        normalized = PurePosixPath(raw_name)
        parts = normalized.parts
        if (
            not raw_name
            or normalized.is_absolute()
            or not parts
            or any(part in {"", ".", ".."} for part in parts)
            or str(normalized) != raw_name.rstrip("/")
        ):
            raise RolloutError("release archive contains an unsafe path")
        path_key = tuple(parts)
        if path_key in paths:
            raise RolloutError("release archive contains a duplicate path")
        paths.add(path_key)
        if not (member.isdir() or member.isreg() or member.issym()):
            raise RolloutError("release archive contains an unsupported entry")
        if member.issym():
            target = PurePosixPath(member.linkname)
            resolved_target = posixpath.normpath(
                posixpath.join(posixpath.dirname(raw_name), member.linkname)
            )
            if (
                not member.linkname
                or target.is_absolute()
                or resolved_target == ".."
                or resolved_target.startswith("../")
            ):
                raise RolloutError("release archive contains an unsafe symlink")
            symlinks.add(path_key)

    for path_key in paths:
        if any(path_key[:index] in symlinks for index in range(1, len(path_key))):
            raise RolloutError("release archive path traverses an archived symlink")

    destination.mkdir(parents=True, exist_ok=True)
    if sys.version_info >= (3, 12):
        bundle.extractall(destination, filter="fully_trusted")
    else:
        bundle.extractall(destination)


def _extract_git_archive(source: Path, revision: str, destination: Path) -> None:
    archive = destination.parent / f".{destination.name}.{uuid.uuid4().hex}.tar"
    try:
        _run_checked(
            ["/usr/bin/git", "archive", "--format=tar", f"--output={archive}", revision],
            cwd=source,
        )
        with tarfile.open(archive, "r:") as bundle:
            _extract_validated_archive(bundle, destination)
    finally:
        archive.unlink(missing_ok=True)


def _glasshive_lock_revision(source: Path) -> str:
    try:
        lock = json.loads((source / "components.lock.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RolloutError("components.lock.json is unreadable") from exc
    components = lock.get("components") if isinstance(lock, dict) else None
    if not isinstance(components, list):
        raise RolloutError("components.lock.json has no components")
    matches = [
        component
        for component in components
        if isinstance(component, dict)
        and component.get("name") == "GlassHive"
        and component.get("path") == "viventium_v0_4/GlassHive"
    ]
    if len(matches) != 1 or not re.fullmatch(r"[0-9a-f]{40}", str(matches[0].get("ref") or "")):
        raise RolloutError("components.lock.json has no exact GlassHive revision")
    return str(matches[0]["ref"])


def _validate_release_symlinks(release: Path, allowed_interpreter_root: Path) -> None:
    release_root = release.resolve()
    interpreter_root = allowed_interpreter_root.resolve()
    for path in release.rglob("*"):
        if not path.is_symlink():
            continue
        try:
            resolved = path.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise RolloutError(f"staged release contains an unresolved symlink: {path.relative_to(release)}") from exc
        if resolved == release_root or release_root in resolved.parents:
            continue
        if resolved == interpreter_root or interpreter_root in resolved.parents:
            metadata = resolved.stat()
            if (
                not resolved.is_file()
                or metadata.st_uid not in {0, os.geteuid()}
                or stat.S_IMODE(metadata.st_mode) & 0o022
            ):
                raise RolloutError("staged release interpreter target is mutable or unsafe")
            continue
        raise RolloutError(f"staged release symlink escapes approved roots: {path.relative_to(release)}")


def _relativize_editable_project_path(project: Path) -> Path:
    """Make one uv editable source path survive an atomic parent-directory rename."""

    project = Path(project)
    project_root = project.resolve()
    source = (project / "src").resolve()
    if not source.is_dir() or project_root not in source.parents:
        raise RolloutError("staged project has no safe source directory")
    site_roots = [
        candidate
        for candidate in (project / ".venv" / "lib").glob("python*/site-packages")
        if candidate.is_dir() and not candidate.is_symlink()
    ]
    if len(site_roots) != 1:
        raise RolloutError("staged project has no unique site-packages directory")
    site_root = site_roots[0].resolve()
    if project_root not in site_root.parents:
        raise RolloutError("staged project site-packages escapes the project")
    absolute_source = str(source)
    matches: list[Path] = []
    for path_file in sorted(site_root.glob("*.pth")):
        if not path_file.is_file() or path_file.is_symlink():
            continue
        try:
            content = path_file.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise RolloutError("staged project contains an unreadable path file") from exc
        if content in {absolute_source, f"{absolute_source}\n"}:
            matches.append(path_file)
    if len(matches) != 1:
        raise RolloutError("staged project must contain exactly one editable source path")
    relative_source = os.path.relpath(source, start=site_root)
    if Path(relative_source).is_absolute() or (site_root / relative_source).resolve() != source:
        raise RolloutError("staged project editable source path is not safely relocatable")
    _atomic_write(matches[0], f"{relative_source}\n".encode(), mode=0o600)
    return matches[0]


def _probe_relocated_project_imports(
    *, staging: Path, releases_root: Path, release_id: str
) -> None:
    """Physically relocate the candidate and import both owning packages."""

    probe = releases_root / f".relocation-probe-{release_id}-{uuid.uuid4().hex[:12]}"
    if probe.exists() or probe.is_symlink():
        raise RolloutError("release relocation probe destination already exists")
    os.replace(staging, probe)
    try:
        _fsync_directory(releases_root)
        glasshive = probe / "viventium_v0_4" / "GlassHive"
        for project, package_name in (
            (glasshive / "runtime_phase1", "workers_projects_runtime"),
            (glasshive / "frontends" / "glass-drive-ui", "glass_drive_ui"),
        ):
            _run_checked(
                [
                    str(project / ".venv" / "bin" / "python"),
                    "-B",
                    "-c",
                    f"import {package_name}",
                ],
                cwd=project,
            )
    finally:
        if probe.exists() or probe.is_symlink():
            if staging.exists() or staging.is_symlink():
                shutil.rmtree(probe, ignore_errors=True)
                raise RolloutError("release relocation probe could not restore staging safely")
            try:
                os.replace(probe, staging)
                _fsync_directory(releases_root)
            except OSError as exc:
                shutil.rmtree(probe, ignore_errors=True)
                raise RolloutError("release relocation probe could not restore staging") from exc


def _seal_release_tree(release: Path) -> None:
    for path in sorted(release.rglob("*"), key=lambda value: len(value.parts), reverse=True):
        if path.is_symlink():
            continue
        metadata = path.stat()
        if path.is_dir():
            os.chmod(path, 0o555)
        elif path.is_file():
            os.chmod(path, 0o555 if stat.S_IMODE(metadata.st_mode) & 0o111 else 0o444)
    os.chmod(release, 0o555)


def stage_release(
    *,
    source: Path,
    releases_root: Path,
    release_id: str,
    uv: Path,
    python: Path,
) -> dict[str, object]:
    """Build a minimal release only from clean, committed parent and GlassHive archives."""

    source = Path(source).resolve()
    releases_root = Path(releases_root).resolve()
    if not RELEASE_ID_RE.fullmatch(release_id):
        raise RolloutError("invalid release id")
    if not source.is_dir() or not (source / ".git").exists():
        raise RolloutError("release source must be a git checkout")
    uv = validate_adapter_path(Path(uv).resolve())
    python = Path(python).resolve()
    if not python.is_file() or python.is_symlink() or not os.access(python, os.X_OK):
        raise RolloutError("staging Python must be an executable regular file")
    parent_revision = _git_value(source, "rev-parse", "HEAD")
    if not re.fullmatch(r"[0-9a-f]{40}", parent_revision):
        raise RolloutError("parent checkout has no exact commit")
    if _git_value(source, "status", "--porcelain", "--untracked-files=normal"):
        raise RolloutError("parent checkout must be clean before release staging")
    glasshive_source = source / "viventium_v0_4" / "GlassHive"
    glasshive_revision = _git_value(glasshive_source, "rev-parse", "HEAD")
    if _git_value(glasshive_source, "status", "--porcelain", "--untracked-files=normal"):
        raise RolloutError("GlassHive checkout must be clean before release staging")
    if _glasshive_lock_revision(source) != glasshive_revision:
        raise RolloutError("parent GlassHive component pin does not match the nested commit")

    releases_root.mkdir(parents=True, exist_ok=True)
    destination = releases_root / release_id
    if destination.exists() or destination.is_symlink():
        raise RolloutError("release destination already exists")
    staging = releases_root / f".staging-{release_id}-{uuid.uuid4().hex[:12]}"
    staging.mkdir(mode=0o700)
    try:
        _extract_git_archive(source, parent_revision, staging)
        nested_destination = staging / "viventium_v0_4" / "GlassHive"
        if nested_destination.exists():
            if nested_destination.is_dir() and not nested_destination.is_symlink():
                shutil.rmtree(nested_destination)
            else:
                nested_destination.unlink()
        _extract_git_archive(glasshive_source, glasshive_revision, nested_destination)
        for project in (
            nested_destination / "runtime_phase1",
            nested_destination / "frontends" / "glass-drive-ui",
        ):
            if not (project / "uv.lock").is_file() or not (project / "pyproject.toml").is_file():
                raise RolloutError(f"staged project is missing its frozen dependency inputs: {project.name}")
            _run_checked(
                [
                    str(uv),
                    "venv",
                    "--relocatable",
                    "--python",
                    str(python),
                    ".venv",
                ],
                cwd=project,
            )
            _run_checked(
                [
                    str(uv),
                    "sync",
                    "--frozen",
                    "--no-dev",
                    "--link-mode",
                    "copy",
                    "--python",
                    str(project / ".venv" / "bin" / "python"),
                ],
                cwd=project,
            )
        required = (
            nested_destination / "runtime_phase1" / ".venv" / "bin" / "python",
            nested_destination / "runtime_phase1" / ".venv" / "bin" / "uvicorn",
            nested_destination / "frontends" / "glass-drive-ui" / ".venv" / "bin" / "uvicorn",
            staging / "deploy" / "glasshive" / "systemd" / "glasshive_rollout.py",
            staging / "deploy" / "glasshive" / "systemd" / "glasshive_rootless_docker_probe.py",
            staging / "deploy" / "glasshive" / "systemd" / "glasshive_ui_readiness_probe.py",
        )
        if any(not path.exists() for path in required):
            raise RolloutError("frozen release staging did not produce every required executable")
        _validate_release_symlinks(staging, python.parent.parent)
        for project in (
            nested_destination / "runtime_phase1",
            nested_destination / "frontends" / "glass-drive-ui",
        ):
            _relativize_editable_project_path(project)
        _probe_relocated_project_imports(
            staging=staging,
            releases_root=releases_root,
            release_id=release_id,
        )
        # Normalize file modes before hashing. Directories are sealed after the manifest is written.
        for path in staging.rglob("*"):
            if path.is_symlink() or not path.is_file():
                continue
            mode = stat.S_IMODE(path.stat().st_mode)
            os.chmod(path, 0o555 if mode & 0o111 else 0o444)
        for path in sorted(staging.rglob("*"), key=lambda value: len(value.parts), reverse=True):
            if path.is_dir() and not path.is_symlink():
                os.chmod(path, 0o555)
        manifest = write_release_manifest(
            staging,
            release_id=release_id,
            parent_revision=parent_revision,
            glasshive_revision=glasshive_revision,
        )
        verify_release_manifest(staging, expected_release_id=release_id)
        _seal_release_tree(staging)
        # Some filesystems require the renamed directory itself to remain owner-writable.
        # Its children stay sealed, and the unpublished root remains owner-only until the
        # atomic rename completes; seal the destination root immediately afterwards.
        os.chmod(staging, 0o700)
        os.replace(staging, destination)
        os.chmod(destination, 0o555)
        _fsync_directory(releases_root)
        verify_release_manifest(destination, expected_release_id=release_id)
        return manifest
    except BaseException:
        if staging.exists():
            for path in staging.rglob("*"):
                if not path.is_symlink():
                    try:
                        os.chmod(path, 0o700 if path.is_dir() else 0o600)
                    except OSError:
                        pass
            shutil.rmtree(staging, ignore_errors=True)
        raise


def validate_adapter_path(path: Path) -> Path:
    path = Path(path)
    try:
        metadata = path.lstat()
    except FileNotFoundError as exc:
        raise RolloutError(f"adapter is missing: {path}") from exc
    if stat.S_ISLNK(metadata.st_mode):
        raise RolloutError(f"adapter may not be a symlink: {path}")
    if not stat.S_ISREG(metadata.st_mode) or not os.access(path, os.X_OK):
        raise RolloutError(f"adapter is not an executable regular file: {path}")
    if stat.S_IMODE(metadata.st_mode) & 0o022:
        raise RolloutError(f"adapter is group/other writable: {path}")
    if metadata.st_uid not in {0, os.geteuid()}:
        raise RolloutError(f"adapter has an untrusted owner: {path}")
    if not path.is_absolute():
        raise RolloutError("adapter path must be absolute")
    return path


def _adapter_call(path: Path, *, action: str, payload: Mapping[str, object]) -> dict[str, object]:
    validate_adapter_path(path)
    request = {"schema_version": 1, "action": action, **dict(payload)}
    result = subprocess.run(
        [str(path)],
        input=json.dumps(request, separators=(",", ":")),
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )
    if result.returncode != 0:
        raise RolloutError(f"{action} adapter failed")
    if len(result.stdout.encode("utf-8")) > 65536:
        raise RolloutError(f"{action} adapter response is too large")
    try:
        response = json.loads(result.stdout)
    except ValueError as exc:
        raise RolloutError(f"{action} adapter returned invalid JSON") from exc
    if not isinstance(response, dict) or response.get("ok") is not True:
        raise RolloutError(f"{action} adapter did not attest success")
    return response


def _validate_acceptance_response(action: str, response: Mapping[str, object]) -> None:
    required = ACCEPTANCE_CHECKS.get(action)
    if required is None:
        raise RolloutError(f"unsupported acceptance action: {action}")
    checks = response.get("checks")
    if not isinstance(checks, dict):
        raise RolloutError(f"{action} acceptance response has no checks")
    for check in required:
        if checks.get(check) is not True:
            raise RolloutError(f"{action} acceptance is missing required check: {check}")


def run_acceptance_adapter(path: Path, *, action: str, payload: Mapping[str, object]) -> dict[str, object]:
    response = _adapter_call(path, action=action, payload=payload)
    _validate_acceptance_response(action, response)
    return response


def validate_ports(ports: Mapping[str, int]) -> dict[str, int]:
    if set(ports) != {"runtime", "mcp", "ui"}:
        raise RolloutError("ports must declare runtime, mcp, and ui")
    normalized = {name: int(value) for name, value in ports.items()}
    if any(value < 1024 or value > 65535 for value in normalized.values()):
        raise RolloutError("service ports must be unprivileged TCP ports")
    if len(set(normalized.values())) != 3:
        raise RolloutError("runtime, MCP, and UI ports must be distinct")
    return normalized


def validate_candidate_ports(candidate: Mapping[str, int], active: Mapping[str, int]) -> None:
    candidate_ports = validate_ports(candidate)
    active_ports = validate_ports(active)
    if set(candidate_ports.values()) & set(active_ports.values()):
        raise RolloutError("candidate ports overlap the active slot")


def _validate_active_environment_value(key: str, value: str) -> None:
    if not value or any(character.isspace() or character == "\0" for character in value):
        raise RolloutError(f"invalid active environment value for {key}")


def write_active_environment(path: Path, values: Mapping[str, str]) -> None:
    lines: list[str] = []
    for key in sorted(values):
        if key not in ALLOWED_ACTIVE_ENV_KEYS:
            if any(fragment in key.upper() for fragment in SECRET_KEY_FRAGMENTS):
                raise RolloutError("secret-bearing values are forbidden in active slot environments")
            raise RolloutError(f"unsupported active environment key: {key}")
        value = str(values[key])
        _validate_active_environment_value(key, value)
        lines.append(f"{key}={value}\n")
    path = Path(path)
    owner: tuple[int, int] | None = None
    if path.exists() and not path.is_symlink():
        metadata = path.stat()
        owner = (metadata.st_uid, metadata.st_gid)
    _atomic_write(path, "".join(lines).encode("utf-8"), mode=0o640, owner=owner)


def read_active_environment(path: Path) -> dict[str, str]:
    if not path.is_file() or path.is_symlink():
        raise RolloutError(f"active environment is missing or unsafe: {path}")
    values: dict[str, str] = {}
    for number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise RolloutError(f"invalid active environment line {number}")
        key, value = line.split("=", 1)
        if key not in ALLOWED_ACTIVE_ENV_KEYS or not value:
            raise RolloutError(f"invalid active environment key on line {number}")
        _validate_active_environment_value(key, value)
        values[key] = value
    return values


PREDECESSOR_RUNTIME_ENV_KEYS = frozenset(
    {
        "GLASSHIVE_PROVIDER_ACCOUNT_HOME_ROOT",
        "WPR_DB_PATH",
    }
)


def _read_selected_environment(
    path: Path,
    *,
    keys: frozenset[str],
) -> dict[str, str]:
    """Read only public path selectors from a potentially secret-bearing EnvironmentFile."""

    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise RolloutError(f"service environment is missing or unsafe: {path}")
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise RolloutError("service environment is unreadable") from exc
    for number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise RolloutError(f"invalid service environment line {number}")
        key, value = line.split("=", 1)
        if key not in keys:
            continue
        if key in values:
            raise RolloutError(f"duplicate service environment key on line {number}")
        _validate_active_environment_value(key, value)
        values[key] = value
    return values


def _validate_service_environment_file(
    path: Path,
    *,
    expected_gid: int,
    expected_uid: int = 0,
) -> None:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise RolloutError("service environment is missing or unsafe") from exc
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != expected_uid
            or metadata.st_gid != expected_gid
            or stat.S_IMODE(metadata.st_mode) & 0o022
        ):
            raise RolloutError("service environment has unsafe ownership or permissions")
    finally:
        os.close(descriptor)


def predecessor_runtime_environment(
    config: RolloutConfig,
    active_environment: Mapping[str, str],
) -> dict[str, str]:
    """Resolve the predecessor's systemd EnvironmentFile order without exposing secrets."""

    effective = _read_selected_environment(
        config.runtime_env_file,
        keys=PREDECESSOR_RUNTIME_ENV_KEYS,
    )
    for key in PREDECESSOR_RUNTIME_ENV_KEYS:
        value = str(active_environment.get(key) or "").strip()
        if value:
            _validate_active_environment_value(key, value)
            effective[key] = value
    return effective


def _ports_from_environments(runtime: Mapping[str, str], gateway: Mapping[str, str]) -> dict[str, int]:
    try:
        ports = {
            "runtime": int(runtime["GLASSHIVE_RUNTIME_PORT"]),
            "mcp": int(gateway["GLASSHIVE_MCP_PORT"]),
            "ui": int(gateway["GLASSHIVE_UI_PORT"]),
        }
    except (KeyError, ValueError) as exc:
        raise RolloutError("active slot environments do not declare valid ports") from exc
    return validate_ports(ports)


def _safe_child(root: Path, candidate: Path, *, field: str) -> Path:
    root = root.resolve()
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise RolloutError(f"{field} escapes its managed root") from exc
    return resolved


def _atomic_symlink(target: Path, link: Path) -> None:
    temporary = link.with_name(f".{link.name}.{uuid.uuid4().hex}.tmp")
    temporary.symlink_to(target)
    try:
        os.replace(temporary, link)
        _fsync_directory(link.parent)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _restore_file_exact(path: Path, content: bytes, mode: int) -> None:
    owner: tuple[int, int] | None = None
    if path.exists() and not path.is_symlink():
        metadata = path.stat()
        owner = (metadata.st_uid, metadata.st_gid)
    _atomic_write(path, content, mode=mode, owner=owner)


def _journal_write(transaction: Path, journal: dict[str, object], status: str, **updates: object) -> None:
    journal.update(updates)
    journal["status"] = status
    journal["updated_at_unix"] = time.time()
    _atomic_write(transaction / "journal.json", _json_bytes(journal), mode=0o600)


def _unfinished_transactions(root: Path) -> list[Path]:
    if not root.exists():
        return []
    unfinished: list[Path] = []
    for journal_path in sorted(root.glob("rollout-*/journal.json")):
        try:
            value = json.loads(journal_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            unfinished.append(journal_path.parent)
            continue
        if not isinstance(value, dict) or value.get("status") not in {"committed", "rolled_back"}:
            unfinished.append(journal_path.parent)
    return unfinished


def _database_open_pids(paths: Sequence[Path]) -> dict[str, list[int]]:
    proc = Path("/proc")
    if not proc.is_dir():
        raise RolloutError("/proc is required to prove SQLite writer quiescence")
    targets: dict[tuple[int, int], str] = {}
    entry_count = 0

    def add_target(candidate: Path, *, label: str) -> None:
        nonlocal entry_count
        entry_count += 1
        if entry_count > 100_000:
            raise RolloutError("state quiescence scan exceeded its bounded entry limit")
        try:
            metadata = candidate.lstat()
        except FileNotFoundError as exc:
            raise RolloutError("state changed while proving writer quiescence") from exc
        targets[(metadata.st_dev, metadata.st_ino)] = label

    for path in paths:
        if not path.exists():
            continue
        label = str(path)
        add_target(path, label=label)
        if path.is_dir() and not path.is_symlink():
            for root, directories, files in os.walk(path, followlinks=False):
                root_path = Path(root)
                safe_directories: list[str] = []
                for name in directories:
                    child = root_path / name
                    add_target(child, label=label)
                    if not child.is_symlink():
                        safe_directories.append(name)
                directories[:] = safe_directories
                for name in files:
                    add_target(root_path / name, label=label)
            continue
        for suffix in ("-wal", "-shm"):
            sidecar = Path(str(path) + suffix)
            if sidecar.exists():
                add_target(sidecar, label=label)
    matches: dict[str, list[int]] = {}
    for process in proc.iterdir():
        if not process.name.isdigit() or int(process.name) == os.getpid():
            continue
        descriptors = process / "fd"
        try:
            entries = list(descriptors.iterdir())
        except (FileNotFoundError, PermissionError):
            continue
        for descriptor in entries:
            try:
                metadata = descriptor.stat()
            except (FileNotFoundError, PermissionError):
                continue
            target = targets.get((metadata.st_dev, metadata.st_ino))
            if target:
                matches.setdefault(target, []).append(int(process.name))
    return {path: sorted(set(pids)) for path, pids in matches.items()}


def _http_json(
    url: str,
    *,
    method: str = "GET",
    body: bytes | None = None,
    headers: Mapping[str, str] | None = None,
    expected_status: int = 200,
) -> tuple[dict[str, object], Mapping[str, str]]:
    request = urllib.request.Request(url, data=body, method=method, headers=dict(headers or {}))
    try:
        response = urllib.request.urlopen(request, timeout=5)
        status = response.status
        response_headers = response.headers
        content = response.read(1024 * 1024)
    except urllib.error.HTTPError as exc:
        status = exc.code
        response_headers = exc.headers
        content = exc.read(1024 * 1024)
    except OSError as exc:
        raise RolloutError(f"readiness request failed for {url}") from exc
    if status != expected_status:
        raise RolloutError(f"readiness request returned {status} for {url}")
    try:
        parsed = json.loads(content or b"{}")
    except ValueError as exc:
        raise RolloutError(f"readiness response was not JSON for {url}") from exc
    if not isinstance(parsed, dict):
        raise RolloutError(f"readiness response was not an object for {url}")
    return parsed, response_headers


def validate_release_health_provenance(
    *,
    runtime: Mapping[str, object],
    ui: Mapping[str, object],
    mcp: Mapping[str, object],
    expected: Mapping[str, str],
) -> None:
    exact = dict(expected)
    if runtime.get("release") != exact:
        raise RolloutError("runtime release provenance does not match the staged manifest")
    if ui.get("release") != exact:
        raise RolloutError("UI release provenance does not match the staged manifest")
    nested_runtime = ui.get("runtime")
    if not isinstance(nested_runtime, dict) or nested_runtime.get("release") != exact:
        raise RolloutError("UI nested runtime provenance does not match the staged manifest")
    if mcp.get("release") != exact:
        raise RolloutError("MCP release provenance does not match the staged manifest")


def probe_local_group(*, ports: Mapping[str, int], expected: Mapping[str, object]) -> None:
    normalized = validate_ports(ports)
    runtime_url = f"http://127.0.0.1:{normalized['runtime']}"
    mcp_url = f"http://127.0.0.1:{normalized['mcp']}"
    ui_url = f"http://127.0.0.1:{normalized['ui']}"
    runtime, _ = _http_json(f"{runtime_url}/health")
    if runtime.get("status") != "ok":
        raise RolloutError("runtime health is not ok")
    ui, _ = _http_json(f"{ui_url}/health")
    nested = ui.get("runtime")
    if ui.get("status") != "ok" or not isinstance(nested, dict) or nested.get("status") != "ok":
        raise RolloutError("BFF or nested runtime health is not ok")
    mcp, _ = _http_json(f"{mcp_url}/health")
    if mcp.get("status") != "ok":
        raise RolloutError("MCP health is not ok")
    metadata, _ = _http_json(f"{mcp_url}/.well-known/oauth-protected-resource/mcp")
    if metadata.get("resource") != expected.get("mcp_resource"):
        raise RolloutError("MCP protected-resource metadata has the wrong resource")
    authorization_servers = metadata.get("authorization_servers")
    if not isinstance(authorization_servers, list) or expected.get("mcp_issuer") not in authorization_servers:
        raise RolloutError("MCP protected-resource metadata has the wrong issuer")
    expected_scopes = {str(item) for item in expected.get("mcp_scopes", [])}
    advertised_scopes = {str(item) for item in metadata.get("scopes_supported", [])}
    if expected_scopes != advertised_scopes:
        raise RolloutError("MCP protected-resource metadata has the wrong scopes")
    expected_provenance = expected.get("release_provenance")
    if expected_provenance is not None:
        if not isinstance(expected_provenance, dict):
            raise RolloutError("expected release provenance is malformed")
        validate_release_health_provenance(
            runtime=runtime,
            ui=ui,
            mcp=mcp,
            expected={str(key): str(value) for key, value in expected_provenance.items()},
        )
    initialize = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": "readiness",
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "glasshive-rollout", "version": "1"},
            },
        }
    ).encode("utf-8")
    _, challenge_headers = _http_json(
        f"{mcp_url}/mcp",
        method="POST",
        body=initialize,
        headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
        expected_status=401,
    )
    challenge = str(challenge_headers.get("WWW-Authenticate") or "")
    expected_metadata_url = str(expected.get("mcp_resource_metadata_url") or "")
    if "resource_metadata=" not in challenge or (expected_metadata_url and expected_metadata_url not in challenge):
        raise RolloutError("MCP initialize did not return the required protected-resource challenge")
    jwks, _ = _http_json(f"{ui_url}/.well-known/jwks.json")
    keys = jwks.get("keys")
    if not isinstance(keys, list) or not keys:
        raise RolloutError("BFF JWKS is empty")


class ProductionSystem:
    def __init__(self, config: RolloutConfig) -> None:
        self.config = config

    @staticmethod
    def _run(command: Sequence[str], *, expected: Sequence[int] = (0,)) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(command, text=True, capture_output=True, check=False, timeout=120)
        if result.returncode not in expected:
            raise RolloutError(f"service command failed: {Path(command[0]).name} {command[1] if len(command) > 1 else ''}")
        return result

    def rootless_probe(self) -> None:
        try:
            account = pwd.getpwnam(self.config.runtime_user)
        except KeyError as exc:
            raise RolloutError("runtime service user does not exist") from exc
        runuser = next((path for path in ("/usr/sbin/runuser", "/sbin/runuser") if Path(path).is_file()), None)
        docker = "/usr/bin/docker"
        if not runuser or not Path(docker).is_file():
            raise RolloutError("rootless Docker probe prerequisites are missing")
        socket = f"unix:///run/user/{account.pw_uid}/docker.sock"
        result = self._run(
            [
                runuser,
                "-u",
                self.config.runtime_user,
                "--",
                "/usr/bin/env",
                f"DOCKER_HOST={socket}",
                docker,
                "info",
                "--format",
                "{{json .SecurityOptions}}",
            ]
        )
        try:
            options = json.loads(result.stdout)
        except ValueError as exc:
            raise RolloutError("rootless Docker probe returned invalid SecurityOptions") from exc
        if not isinstance(options, list) or not any("rootless" in str(item).lower() for item in options):
            raise RolloutError("runtime Docker daemon is not rootless")

    def stop_group(self) -> None:
        self._run(["/usr/bin/systemctl", "stop", *GROUP_SERVICES])

    def _run_rootless_docker(self, arguments: Sequence[str]) -> subprocess.CompletedProcess[str]:
        try:
            account = pwd.getpwnam(self.config.runtime_user)
        except KeyError as exc:
            raise RolloutError("runtime service user does not exist") from exc
        runuser = next(
            (path for path in ("/usr/sbin/runuser", "/sbin/runuser") if Path(path).is_file()),
            None,
        )
        if not runuser or not Path("/usr/bin/docker").is_file():
            raise RolloutError("rootless Docker inspection prerequisites are missing")
        return self._run(
            [
                runuser,
                "-u",
                self.config.runtime_user,
                "--",
                "/usr/bin/env",
                f"DOCKER_HOST=unix:///run/user/{account.pw_uid}/docker.sock",
                "/usr/bin/docker",
                *arguments,
            ]
        )

    def _provider_account_bind_mounts(self, paths: Sequence[Path]) -> list[str]:
        roots = tuple(Path(path).resolve(strict=False) for path in paths)
        if not roots:
            return []
        listed = self._run_rootless_docker(
            ["ps", "-aq", "--filter", "name=^/wpr-"]
        )
        container_ids = [
            value.strip()
            for value in str(listed.stdout or "").splitlines()
            if value.strip()
        ]
        if any(
            not re.fullmatch(r"[0-9a-f]{12,64}", container_id)
            for container_id in container_ids
        ):
            raise RolloutError("rootless provider-container inspection returned an invalid id")
        if len(container_ids) > 4096:
            raise RolloutError("rootless provider-container inspection exceeded its bounded limit")
        matches: set[str] = set()
        for offset in range(0, len(container_ids), 128):
            inspected = self._run_rootless_docker(
                ["inspect", *container_ids[offset : offset + 128]]
            )
            try:
                payload = json.loads(inspected.stdout or "[]")
            except ValueError as exc:
                raise RolloutError("rootless provider-container inspection returned invalid JSON") from exc
            if not isinstance(payload, list):
                raise RolloutError("rootless provider-container inspection returned invalid data")
            if len(payload) != len(container_ids[offset : offset + 128]):
                raise RolloutError("rootless provider-container inspection returned incomplete data")
            requested_ids = container_ids[offset : offset + 128]
            for entry in payload:
                if not isinstance(entry, dict):
                    raise RolloutError("rootless provider-container inspection returned invalid data")
                inspected_id = str(entry.get("Id") or "")
                if not inspected_id or not any(
                    inspected_id.startswith(requested) or requested.startswith(inspected_id)
                    for requested in requested_ids
                ):
                    raise RolloutError("rootless provider-container inspection returned mismatched data")
                name = str(entry.get("Name") or "").lstrip("/")
                if not name.startswith("wpr-"):
                    continue
                container_state = entry.get("State")
                active_fields = ("Running", "Paused", "Restarting")
                if not isinstance(container_state, dict) or any(
                    not isinstance(container_state.get(field), bool)
                    for field in active_fields
                ):
                    raise RolloutError(
                        "rootless provider-container inspection returned invalid state data"
                    )
                if not any(container_state[field] for field in active_fields):
                    # Exited containers retain historical bind metadata, but have no
                    # process capable of mutating the provider tree.
                    continue
                mounts = entry.get("Mounts")
                if not isinstance(mounts, list):
                    raise RolloutError("rootless provider-container inspection omitted mount data")
                for mount in mounts:
                    if not isinstance(mount, dict) or str(mount.get("Type") or "") != "bind":
                        continue
                    source_value = str(mount.get("Source") or "")
                    source = Path(source_value)
                    if not source.is_absolute():
                        raise RolloutError("rootless provider-container inspection returned an unsafe mount")
                    resolved_source = source.resolve(strict=False)
                    if any(
                        resolved_source == root or resolved_source.is_relative_to(root)
                        for root in roots
                    ):
                        matches.add(name)
        return sorted(matches)

    def assert_stopped(
        self,
        database_paths: list[Path],
        *,
        provider_account_paths: Sequence[Path] = (),
    ) -> None:
        for service in GROUP_SERVICES:
            result = self._run(["/usr/bin/systemctl", "is-active", "--quiet", service], expected=(0, 3))
            if result.returncode == 0:
                raise RolloutError(f"service did not stop: {service}")
        if self._provider_account_bind_mounts(provider_account_paths):
            raise RolloutError(
                "state writer quiescence failed; a rootless provider-account bind mount remains"
            )
        open_pids = _database_open_pids([*database_paths, *provider_account_paths])
        if open_pids:
            raise RolloutError("state writer quiescence failed; a managed state path still has open descriptors")

    def prepare_shared_link_ref_state(self, state_dir: Path) -> Path:
        """Prepare the only SQLite state intentionally shared by runtime and gateway."""

        shared_directory_mode = 0o2770 if sys.platform.startswith("linux") else 0o770
        allowed_file_owners = {os.geteuid()}
        for service_user in (self.config.runtime_user, "glasshive-gateway"):
            try:
                allowed_file_owners.add(pwd.getpwnam(service_user).pw_uid)
            except KeyError:
                if service_user == self.config.runtime_user and service_user != pwd.getpwuid(os.geteuid()).pw_name:
                    raise RolloutError("runtime service user does not exist")
        try:
            state_gid = grp.getgrnam(LINK_REF_SHARED_GROUP).gr_gid
        except KeyError as exc:
            if self.config.runtime_user != pwd.getpwuid(os.geteuid()).pw_name:
                raise RolloutError("GlassHive state group does not exist") from exc
            # Portable unit tests use the invoking account in place of the hosted service identity.
            state_gid = os.getegid()
        parent_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        child_flags = parent_flags
        parent_fd = -1
        child_fd = -1
        try:
            parent_fd = os.open(state_dir, parent_flags)
            parent_metadata = os.fstat(parent_fd)
            if (
                not stat.S_ISDIR(parent_metadata.st_mode)
                or parent_metadata.st_uid != os.geteuid()
                or parent_metadata.st_gid != state_gid
                or stat.S_IMODE(parent_metadata.st_mode) != 0o770
            ):
                raise RolloutError("runtime state root has unexpected owner, group, type, or mode")
            try:
                os.mkdir(LINK_REF_SHARED_STATE_DIR_NAME, mode=0o770, dir_fd=parent_fd)
            except FileExistsError:
                pass
            child_fd = os.open(LINK_REF_SHARED_STATE_DIR_NAME, child_flags, dir_fd=parent_fd)
            child_metadata = os.fstat(child_fd)
            if (
                not stat.S_ISDIR(child_metadata.st_mode)
                or child_metadata.st_uid != os.geteuid()
            ):
                raise RolloutError("shared link-reference directory has unexpected owner or type")
            if child_metadata.st_gid != state_gid:
                os.fchown(child_fd, os.geteuid(), state_gid)
            os.fchmod(child_fd, shared_directory_mode)

            for name in (
                RUNTIME_LINK_REF_DATABASE_NAME,
                f"{RUNTIME_LINK_REF_DATABASE_NAME}-wal",
                f"{RUNTIME_LINK_REF_DATABASE_NAME}-shm",
            ):
                file_fd = -1
                try:
                    file_fd = os.open(
                        name,
                        os.O_RDWR
                        | (os.O_CREAT if name == RUNTIME_LINK_REF_DATABASE_NAME else 0)
                        | getattr(os, "O_NOFOLLOW", 0),
                        0o660,
                        dir_fd=child_fd,
                    )
                except FileNotFoundError:
                    continue
                try:
                    file_metadata = os.fstat(file_fd)
                    if (
                        not stat.S_ISREG(file_metadata.st_mode)
                        or file_metadata.st_uid not in allowed_file_owners
                    ):
                        raise RolloutError("shared link-reference state has unexpected owner or type")
                    if file_metadata.st_uid != os.geteuid() or file_metadata.st_gid != state_gid:
                        os.fchown(file_fd, os.geteuid(), state_gid)
                    os.fchmod(file_fd, 0o660)
                    os.fsync(file_fd)
                finally:
                    if file_fd >= 0:
                        os.close(file_fd)
            os.fsync(child_fd)
            os.fsync(parent_fd)
        except RolloutError:
            raise
        except OSError as exc:
            raise RolloutError("shared link-reference state could not be prepared safely") from exc
        finally:
            if child_fd >= 0:
                os.close(child_fd)
            if parent_fd >= 0:
                os.close(parent_fd)
        return shared_link_ref_state_path(state_dir)

    def start_group(self, *, phase: str) -> None:
        del phase
        self._run(["/usr/bin/systemctl", "start", *START_SERVICES])
        for service in START_SERVICES:
            self._run(["/usr/bin/systemctl", "is-active", "--quiet", service])

    def probe_group(self, *, phase: str, ports: dict[str, int], expected: dict[str, object]) -> None:
        probe_expected = dict(expected)
        if phase in {"rehearsal", "candidate-live"}:
            probe_expected["release_provenance"] = release_provenance(self.config.release_dir)
        deadline = time.monotonic() + self.config.probe_timeout_sec
        last_error: RolloutError | None = None
        while time.monotonic() < deadline:
            try:
                probe_local_group(ports=ports, expected=probe_expected)
                return
            except RolloutError as exc:
                last_error = exc
                time.sleep(0.5)
        raise RolloutError(f"three-service readiness timed out: {last_error}")


class ProductionAdapters:
    def __init__(self, config: RolloutConfig) -> None:
        self.config = config

    def call_state(self, action: str, payload: dict[str, object]) -> dict[str, object]:
        response = _adapter_call(self.config.state_adapter, action=action, payload=payload)
        required = f"{action}_id"
        if not SAFE_ID_RE.fullmatch(str(response.get(required) or "")):
            raise RolloutError(f"state adapter omitted {required}")
        return response

    def call_ingress(self, action: str, payload: dict[str, object]) -> dict[str, object]:
        response = _adapter_call(self.config.ingress_adapter, action=action, payload=payload)
        if action == "inspect" and not SAFE_ID_RE.fullmatch(str(response.get("snapshot_id") or "")):
            raise RolloutError("ingress inspect omitted snapshot_id")
        expected_release = str(payload.get("release_id") or payload.get("previous_release_id") or "")
        if expected_release and response.get("active_release_id") != expected_release:
            raise RolloutError("ingress adapter did not attest the expected complete release")
        route_contract = payload.get("route_contract")
        if isinstance(route_contract, dict):
            expected_digest = _canonical_json_sha256(route_contract)
            if response.get("route_contract_sha256") != expected_digest:
                raise RolloutError("ingress adapter did not attest the exact route contract")
        return response

    def call_acceptance(self, action: str, payload: dict[str, object]) -> dict[str, object]:
        return run_acceptance_adapter(self.config.acceptance_adapter, action=action, payload=payload)


def _validate_config(config: RolloutConfig, *, validate_adapters: bool) -> None:
    if not RELEASE_ID_RE.fullmatch(config.release_id):
        raise RolloutError("invalid release id")
    releases_root = config.releases_root.resolve()
    release = _safe_child(releases_root, config.release_dir, field="release directory")
    if release == releases_root or not release.is_dir():
        raise RolloutError("release directory is missing")
    if not config.current_symlink.is_symlink():
        raise RolloutError("current release pointer must be a symlink")
    previous = config.current_symlink.resolve()
    _safe_child(releases_root, previous, field="current release")
    if previous == release:
        raise RolloutError("candidate release is already current")
    validate_ports(config.candidate_ports)
    candidate_state_root = _safe_child(
        config.state_dir,
        config.candidate_state_root,
        field="candidate state root",
    )
    if candidate_state_root == config.state_dir.resolve():
        raise RolloutError("candidate state root must be below the managed state directory")
    if len(config.databases) < 2:
        raise RolloutError("runtime and authentication SQLite databases must both be declared")
    names: set[str] = set()
    env_names: set[str] = set()
    for database in config.databases:
        if not IDENTIFIER_RE.fullmatch(database.name) or database.name in names:
            raise RolloutError("database names must be unique identifiers")
        names.add(database.name)
        if database.env_name not in {"WPR_DB_PATH", "GLASSHIVE_AUTH_STATE_PATH"} or database.env_name in env_names:
            raise RolloutError("database environment bindings are missing or duplicated")
        env_names.add(database.env_name)
        _safe_child(config.state_dir, database.path, field=f"database {database.name}")
        if database.candidate_relative.is_absolute() or ".." in database.candidate_relative.parts:
            raise RolloutError("candidate database path must be relative and contained")
        if not database.invariants and not database.post_migration_invariants:
            raise RolloutError(f"database {database.name} requires invariant tables")
        if database.restore_mode not in {0o600, 0o660}:
            raise RolloutError("database restore mode must be 0600 or 0660")
    if env_names != {"WPR_DB_PATH", "GLASSHIVE_AUTH_STATE_PATH"}:
        raise RolloutError("runtime and authentication database bindings are required")
    for key in (
        "mcp_resource",
        "mcp_issuer",
        "mcp_scopes",
        "mcp_resource_metadata_url",
        "mcp_token_audiences",
        "mcp_token_scopes",
        "mcp_allowed_client_ids",
        "mcp_tenant_id",
        "mcp_principal_claim",
    ):
        if not config.expected.get(key):
            raise RolloutError(f"expected readiness contract is missing {key}")
    if validate_adapters:
        validate_sealed_release(release)
        validate_sealed_release(previous)
        fixed_paths = {
            "current_symlink": (config.current_symlink, Path("/opt/viventium/current")),
            "runtime_active_env": (
                config.runtime_active_env,
                Path("/etc/viventium/glasshive/runtime-active.env"),
            ),
            "gateway_active_env": (
                config.gateway_active_env,
                Path("/etc/viventium/glasshive/gateway-active.env"),
            ),
            "runtime_env_file": (
                config.runtime_env_file,
                Path("/etc/viventium/glasshive/runtime.env"),
            ),
            "gateway_env_file": (
                config.gateway_env_file,
                Path("/etc/viventium/glasshive/gateway.env"),
            ),
        }
        for field, (actual, required) in fixed_paths.items():
            if actual != required:
                raise RolloutError(f"{field} does not match the installed systemd unit contract")
        if config.current_symlink.lstat().st_uid != 0:
            raise RolloutError("current release pointer is not root owned")
        try:
            state_gid = grp.getgrnam("glasshive-state").gr_gid
            gateway_gid = grp.getgrnam("glasshive-gateway-secrets").gr_gid
        except KeyError as exc:
            raise RolloutError("GlassHive service groups are missing") from exc
        environment_groups = {
            config.runtime_env_file: state_gid,
            config.runtime_active_env: state_gid,
            config.gateway_env_file: gateway_gid,
            config.gateway_active_env: gateway_gid,
        }
        for environment_file, expected_gid in environment_groups.items():
            _validate_service_environment_file(
                environment_file,
                expected_gid=expected_gid,
            )
        validate_adapter_path(config.ingress_adapter)
        validate_adapter_path(config.state_adapter)
        validate_adapter_path(config.acceptance_adapter)
        if (
            not config.candidate_state_root.is_dir()
            or config.candidate_state_root.is_symlink()
            or stat.S_IMODE(config.candidate_state_root.stat().st_mode) & 0o007
        ):
            raise RolloutError("candidate state root must be a non-public managed directory")


def _candidate_payload(
    config: RolloutConfig,
    ports: Mapping[str, int],
    *,
    release_dir: Path | None = None,
) -> dict[str, object]:
    provenance = release_provenance(release_dir or config.release_dir)
    return {
        "release_id": provenance["release_id"],
        "release_provenance": provenance,
        "endpoints": {
            "runtime": f"http://127.0.0.1:{ports['runtime']}",
            "mcp": f"http://127.0.0.1:{ports['mcp']}/mcp",
            "mcp_health": f"http://127.0.0.1:{ports['mcp']}/health",
            "ui": f"http://127.0.0.1:{ports['ui']}",
        },
        "expected": config.expected,
    }


def ingress_route_contract(ports: Mapping[str, int]) -> dict[str, object]:
    normalized = validate_ports(ports)
    return {
        "schema_version": 1,
        "browser": {
            "exact_paths": [
                "/",
                "/auth",
                "/login",
                "/confirm-change",
                "/favicon.ico",
                "/health",
                "/static",
                "/ui",
                "/v1",
            ],
            "path_prefixes": [
                "/auth/",
                "/static/",
                "/api/",
                "/r/",
                "/watch/",
                "/desktop/",
                "/novnc/",
                "/ui/",
                "/v1/",
            ],
            "service": "glasshive-ui",
            "upstream": f"http://127.0.0.1:{normalized['ui']}",
            # The BFF validates this double-submit token.  An ingress adapter must
            # capture it before the deny-by-prefix scrub and restore only this
            # named header when proxying browser traffic.
            "preserve_client_headers": ["X-GlassHive-CSRF"],
            "websocket_path_prefixes": ["/novnc/"],
        },
        "mcp": {
            "exact_paths": ["/mcp", "/.well-known/oauth-protected-resource/mcp"],
            "service": "glasshive-mcp",
            "upstream": f"http://127.0.0.1:{normalized['mcp']}",
            "forbid_oauth2_proxy_html_redirect": True,
        },
        "jwks": {
            "exact_paths": ["/.well-known/jwks.json"],
            "service": "glasshive-ui",
            "upstream": f"http://127.0.0.1:{normalized['ui']}",
        },
        "private_upstreams": [f"http://127.0.0.1:{normalized['runtime']}"],
        "scrub_client_header_prefixes": ["X-Viventium-", "X-GlassHive-", "X-LibreChat-"],
    }


def _active_values(
    config: RolloutConfig,
    *,
    ports: Mapping[str, int],
    state_dir: Path,
    database_paths: Mapping[str, Path],
    background_consumers_enabled: bool,
    reconcile_on_startup: bool,
) -> tuple[dict[str, str], dict[str, str]]:
    runtime_user = config.runtime_user
    try:
        runtime_uid = pwd.getpwnam(runtime_user).pw_uid
    except KeyError:
        # Unit tests use a synthetic service identity; production preflight proves it exists.
        runtime_uid = 1234
    provenance = release_provenance(config.release_dir)
    environment_provenance = {
        "GLASSHIVE_COMPONENT_REVISION": provenance["glasshive_revision"],
        "GLASSHIVE_PARENT_REVISION": provenance["parent_revision"],
        "GLASSHIVE_RELEASE_ID": provenance["release_id"],
    }
    runtime = {
        **environment_provenance,
        "DOCKER_HOST": f"unix:///run/user/{runtime_uid}/docker.sock",
        "GLASSHIVE_BACKGROUND_CONSUMERS_ENABLED": "true" if background_consumers_enabled else "false",
        "GLASSHIVE_RECONCILE_ON_STARTUP": "true" if reconcile_on_startup else "false",
        "GLASSHIVE_RUNTIME_PORT": str(ports["runtime"]),
        "GLASSHIVE_STATE_DIR": str(state_dir),
        "GLASSHIVE_LINK_REF_STATE_PATH": str(shared_link_ref_state_path(state_dir)),
        "GLASSHIVE_LINK_REF_SHARED_GROUP": LINK_REF_SHARED_GROUP,
        "GLASSHIVE_PROVIDER_ACCOUNT_HOME_ROOT": str(provider_account_state_path(state_dir)),
        "WPR_DB_PATH": str(database_paths["WPR_DB_PATH"]),
    }
    gateway = {
        **environment_provenance,
        "GLASSHIVE_AUTH_STATE_PATH": str(database_paths["GLASSHIVE_AUTH_STATE_PATH"]),
        "GLASSHIVE_WATCH_SESSION_STATE_PATH": str(
            database_paths["GLASSHIVE_AUTH_STATE_PATH"].parent / "watch_sessions.sqlite3"
        ),
        "GLASSHIVE_MCP_PORT": str(ports["mcp"]),
        "GLASSHIVE_LINK_REF_STATE_PATH": str(shared_link_ref_state_path(state_dir)),
        "GLASSHIVE_LINK_REF_SHARED_GROUP": LINK_REF_SHARED_GROUP,
        "GLASSHIVE_RUNTIME_BASE_URL": f"http://127.0.0.1:{ports['runtime']}",
        "GLASSHIVE_UI_PORT": str(ports["ui"]),
        "WPR_MCP_BASE_URL": f"http://127.0.0.1:{ports['runtime']}",
    }
    return runtime, gateway


def shared_link_ref_state_path(state_dir: Path) -> Path:
    return (
        Path(state_dir)
        / LINK_REF_SHARED_STATE_DIR_NAME
        / RUNTIME_LINK_REF_DATABASE_NAME
    )


def provider_account_state_path(state_dir: Path) -> Path:
    return Path(state_dir) / PROVIDER_ACCOUNT_STATE_DIR_NAME


def _validated_provider_account_state_path(
    config: RolloutConfig,
    path: Path,
    *,
    field: str,
) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute() or candidate.name != PROVIDER_ACCOUNT_STATE_DIR_NAME:
        raise RolloutError(f"{field} is not a managed provider-account directory")
    resolved = _safe_child(config.state_dir, candidate, field=field)
    if resolved != candidate or resolved.name != PROVIDER_ACCOUNT_STATE_DIR_NAME:
        raise RolloutError(f"{field} contains an unsafe path indirection")
    if candidate.is_symlink() or (candidate.exists() and not candidate.is_dir()):
        raise RolloutError(f"{field} has an unsafe type")
    return resolved


def predecessor_provider_account_state_path(
    config: RolloutConfig,
    runtime_environment: Mapping[str, str],
) -> Path:
    explicit = str(
        runtime_environment.get("GLASSHIVE_PROVIDER_ACCOUNT_HOME_ROOT") or ""
    ).strip()
    if explicit:
        candidate = Path(explicit)
    else:
        database_value = str(runtime_environment.get("WPR_DB_PATH") or "").strip()
        database = Path(database_value)
        if not database.is_absolute():
            raise RolloutError("predecessor runtime database path is missing or unsafe")
        candidate = database.parent / PROVIDER_ACCOUNT_STATE_DIR_NAME
    return _validated_provider_account_state_path(
        config,
        candidate,
        field="predecessor provider-account home",
    )


def _provider_account_state_contract_for_path(
    config: RolloutConfig,
    path: Path,
) -> dict[str, object]:
    return {
        "path": str(path),
        "owner": config.runtime_user,
        "group": LINK_REF_SHARED_GROUP,
        "directory_mode": "0700",
        "contents": "directories_regular_files_only",
        "reject_hard_links": True,
        "preserve_numeric_uid_gid": True,
        "preserve_mode": True,
        "preserve_xattrs": True,
        "preserve_posix_acl": True,
        "preserve_absence": True,
    }


def provider_account_state_contract(
    config: RolloutConfig,
    state_dir: Path,
) -> dict[str, object]:
    return _provider_account_state_contract_for_path(
        config,
        provider_account_state_path(state_dir),
    )


def shared_link_ref_state_contract(config: RolloutConfig, state_dir: Path) -> dict[str, object]:
    return {
        "path": str(shared_link_ref_state_path(state_dir)),
        "directory_owner": "root",
        "allowed_file_owners": ["root", config.runtime_user, "glasshive-gateway"],
        "prepared_file_owner": "root",
        "group": LINK_REF_SHARED_GROUP,
        "directory_mode": "02770",
        "file_mode": "0660",
    }


def legacy_link_ref_state_paths(
    config: RolloutConfig,
    *,
    state_dir: Path | None = None,
    auth_database: Path | None = None,
) -> tuple[Path, ...]:
    resolved_state_dir = Path(state_dir) if state_dir is not None else config.state_dir
    resolved_auth_database = auth_database or next(
        (database.path for database in config.databases if database.env_name == "GLASSHIVE_AUTH_STATE_PATH"),
        config.state_dir / "gateway" / "auth.sqlite3",
    )
    return (
        resolved_auth_database.parent / RUNTIME_LINK_REF_DATABASE_NAME,
        resolved_state_dir / ".local" / "state" / "glasshive" / RUNTIME_LINK_REF_DATABASE_NAME,
        resolved_state_dir / "runtime-private" / RUNTIME_LINK_REF_DATABASE_NAME,
    )


def migrate_legacy_link_ref_state(
    destination: Path,
    legacy_paths: Sequence[Path],
    *,
    state_dir: Path,
) -> int:
    """Merge predecessor ref stores without changing exposed opaque ids."""

    required_columns = {"ref_id", "kind", "token", "target_url", "expires_at", "created_at"}
    copied = 0
    try:
        resolved_root = state_dir.resolve(strict=True)
        with sqlite3.connect(destination) as target:
            target.row_factory = sqlite3.Row
            target.execute(
                """
                CREATE TABLE IF NOT EXISTS signed_link_refs (
                    ref_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    token TEXT NOT NULL,
                    target_url TEXT NOT NULL DEFAULT '',
                    expires_at INTEGER NOT NULL,
                    created_at INTEGER NOT NULL,
                    payload_json TEXT NOT NULL DEFAULT '',
                    scope_key TEXT NOT NULL DEFAULT ''
                )
                """
            )
            target.execute(
                """
                CREATE TABLE IF NOT EXISTS link_ref_legacy_migrations (
                    source_path TEXT PRIMARY KEY,
                    migrated_at INTEGER NOT NULL
                )
                """
            )
            for legacy_path in legacy_paths:
                source = Path(legacy_path)
                if source == destination or not source.exists():
                    continue
                source_metadata = source.lstat()
                resolved_source = source.resolve(strict=True)
                if (
                    source.is_symlink()
                    or not stat.S_ISREG(source_metadata.st_mode)
                    or not resolved_source.is_relative_to(resolved_root)
                    or resolved_source != source.absolute()
                    or stat.S_IMODE(source_metadata.st_mode) & 0o007
                ):
                    raise RolloutError("legacy link-reference state has unsafe ownership or permissions")
                source_key = resolved_source.relative_to(resolved_root).as_posix()
                migrated = target.execute(
                    "SELECT 1 FROM link_ref_legacy_migrations WHERE source_path = ?",
                    (source_key,),
                ).fetchone()
                if migrated is not None:
                    continue
                with sqlite3.connect(f"{resolved_source.as_uri()}?mode=ro", uri=True) as legacy:
                    legacy.row_factory = sqlite3.Row
                    table = legacy.execute(
                        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'signed_link_refs'"
                    ).fetchone()
                    if table is None:
                        raise RolloutError("legacy link-reference state has an unexpected schema")
                    columns = {
                        str(row[1])
                        for row in legacy.execute("PRAGMA table_info(signed_link_refs)").fetchall()
                    }
                    if not required_columns.issubset(columns):
                        raise RolloutError("legacy link-reference state has an unexpected schema")
                    optional = [name for name in ("payload_json", "scope_key") if name in columns]
                    selected = [*sorted(required_columns), *optional]
                    rows = legacy.execute(
                        f"SELECT {', '.join(selected)} FROM signed_link_refs"
                    ).fetchall()
                    for row in rows:
                        ref_id = str(row["ref_id"] or "")
                        existing = target.execute(
                            """
                            SELECT kind, token, target_url, created_at, expires_at,
                                   payload_json, scope_key
                            FROM signed_link_refs
                            WHERE ref_id = ?
                            """,
                            (ref_id,),
                        ).fetchone()
                        core_identity = (
                            str(row["kind"] or ""),
                            str(row["token"] or ""),
                            str(row["target_url"] or ""),
                            int(row["created_at"]),
                        )
                        optional_identity = (
                            str(row["payload_json"] or "") if "payload_json" in columns else "",
                            str(row["scope_key"] or "") if "scope_key" in columns else "",
                        )
                        if existing is not None:
                            if tuple(existing[:4]) != core_identity:
                                raise RolloutError("legacy link-reference ids conflict across state stores")
                            merged_optional = list(existing[5:])
                            for index, incoming in enumerate(optional_identity):
                                current = str(merged_optional[index] or "")
                                if incoming and current and incoming != current:
                                    raise RolloutError("legacy link-reference ids conflict across state stores")
                                if incoming and not current:
                                    merged_optional[index] = incoming
                            if tuple(merged_optional) != tuple(existing[5:]):
                                target.execute(
                                    "UPDATE signed_link_refs SET payload_json = ?, scope_key = ? WHERE ref_id = ?",
                                    (*merged_optional, ref_id),
                                )
                            continue
                        target.execute(
                            """
                            INSERT INTO signed_link_refs
                            (ref_id, kind, token, target_url, expires_at, created_at, payload_json, scope_key)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                ref_id,
                                core_identity[0],
                                core_identity[1],
                                core_identity[2],
                                int(row["expires_at"]),
                                core_identity[3],
                                *optional_identity,
                            ),
                        )
                        copied += 1
                target.execute(
                    "INSERT INTO link_ref_legacy_migrations (source_path, migrated_at) VALUES (?, ?)",
                    (source_key, int(time.time())),
                )
            target.execute(
                "CREATE INDEX IF NOT EXISTS idx_signed_link_refs_expires_at ON signed_link_refs(expires_at)"
            )
            target.execute(
                "CREATE INDEX IF NOT EXISTS idx_signed_link_refs_scope_key ON signed_link_refs(scope_key)"
            )
    except RolloutError:
        raise
    except (OSError, sqlite3.Error, ValueError) as exc:
        raise RolloutError("legacy link-reference state could not be migrated safely") from exc
    return copied


def _restore_database(
    backup: Path,
    live: Path,
    invariants: Sequence[Mapping[str, object]],
    *,
    mode: int,
) -> None:
    inspect_database(backup, invariants)
    temporary = live.with_name(f".{live.name}.{uuid.uuid4().hex}.restore")
    _sqlite_backup(backup, temporary)
    inspect_database(temporary, invariants)
    for suffix in ("-wal", "-shm"):
        Path(str(live) + suffix).unlink(missing_ok=True)
    os.replace(temporary, live)
    os.chmod(live, mode)
    _fsync_directory(live.parent)


def _rollback(
    *,
    config: RolloutConfig,
    system: Any,
    adapters: Any,
    transaction: Path,
    journal: dict[str, object],
    previous_release: Path,
    previous_release_id: str,
    previous_ports: dict[str, int],
    runtime_env_bytes: bytes,
    runtime_env_mode: int,
    gateway_env_bytes: bytes,
    gateway_env_mode: int,
    backups: Mapping[str, Path],
    state_snapshot_ready: bool,
    state_clone_ready: bool,
    ingress_switched: bool,
    absent_before: set[str],
    predecessor_provider_account_home: Path,
) -> None:
    _journal_write(transaction, journal, "rolling_back")
    system.stop_group()
    canonical_provider_account_home = _validated_provider_account_state_path(
        config,
        provider_account_state_path(config.state_dir),
        field="canonical provider-account home",
    )
    provider_account_paths = {
        canonical_provider_account_home,
        predecessor_provider_account_home,
    }
    candidate_state_value = str(journal.get("candidate_state_dir") or "")
    if candidate_state_value:
        candidate_state = _safe_child(
            config.candidate_state_root,
            Path(candidate_state_value),
            field="candidate state directory",
        )
        provider_account_paths.add(provider_account_state_path(candidate_state))
    system.assert_stopped(
        [
            *(database.path for database in config.databases),
            shared_link_ref_state_path(config.state_dir),
        ],
        provider_account_paths=sorted(provider_account_paths),
    )
    if ingress_switched:
        adapters.call_ingress(
            "restore",
            {
                "previous_release_id": previous_release_id,
                "snapshot_id": str(journal.get("ingress_snapshot_id") or ""),
            },
        )
    if state_snapshot_ready:
        adapters.call_state(
            "restore",
            {
                "previous_release_id": previous_release_id,
                "snapshot_id": str(journal.get("state_snapshot_id") or ""),
                "live_state_dir": str(config.state_dir),
                "database_paths": [str(database.path) for database in config.databases],
                "shared_link_ref_state": shared_link_ref_state_contract(
                    config, config.state_dir
                ),
                "provider_account_state": provider_account_state_contract(
                    config, config.state_dir
                ),
                "predecessor_provider_account_state": (
                    _provider_account_state_contract_for_path(
                        config,
                        predecessor_provider_account_home,
                    )
                ),
                "provider_state_materialize_id": str(
                    journal.get("provider_state_materialize_id") or ""
                ),
            },
        )
    for database in config.databases:
        backup = backups.get(database.name)
        if backup and backup.is_file():
            _restore_database(
                backup,
                database.path,
                database.invariants,
                mode=database.restore_mode,
            )
        elif database.name in absent_before:
            for suffix in ("", "-wal", "-shm"):
                Path(str(database.path) + suffix).unlink(missing_ok=True)
            _fsync_directory(database.path.parent)
    _atomic_symlink(previous_release, config.current_symlink)
    _restore_file_exact(config.runtime_active_env, runtime_env_bytes, runtime_env_mode)
    _restore_file_exact(config.gateway_active_env, gateway_env_bytes, gateway_env_mode)
    system.start_group(phase="rollback")
    system.probe_group(phase="rollback", ports=previous_ports, expected=config.expected)
    adapters.call_acceptance(
        "rollback",
        _candidate_payload(config, previous_ports, release_dir=previous_release),
    )
    adapters.call_ingress(
        "status",
        {"previous_release_id": previous_release_id, "release_id": previous_release_id},
    )
    if state_clone_ready:
        adapters.call_state(
            "cleanup_clone",
            {
                "cleanup_clone_id": str(journal.get("state_clone_id") or ""),
                "candidate_state_dir": candidate_state_value,
            },
        )
    _journal_write(transaction, journal, "rolled_back")


def execute_rollout(
    config: RolloutConfig,
    *,
    system: Any | None = None,
    adapters: Any | None = None,
) -> dict[str, object]:
    """Execute one complete rehearsal/cutover transaction or restore the predecessor."""

    production = system is None or adapters is None
    if production and config.lock_file != HOSTED_MUTATION_LOCK:
        raise RolloutError(
            "hosted GlassHive rollout lock must be /run/lock/glasshive-rollout.lock"
        )
    _validate_config(config, validate_adapters=production)
    system = system or ProductionSystem(config)
    adapters = adapters or ProductionAdapters(config)
    config.transactions_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(config.transactions_dir, 0o700)
    unfinished = _unfinished_transactions(config.transactions_dir)
    if unfinished:
        raise RolloutError(f"unfinished rollout must be recovered first: {unfinished[0].name}")

    lock_handle = _open_mutation_lock(config.lock_file)
    try:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        lock_handle.close()
        raise RolloutError(
            "another GlassHive mutation holds the deployment lock; retry after it completes"
        ) from exc

    try:
        previous_release = config.current_symlink.resolve()
        previous_manifest = verify_release_manifest(
            previous_release,
            expected_release_id=read_release_identity(previous_release),
        )
        previous_release_id = str(previous_manifest["release_id"])
        verify_release_manifest(config.release_dir, expected_release_id=config.release_id)
        runtime_env_bytes = config.runtime_active_env.read_bytes()
        gateway_env_bytes = config.gateway_active_env.read_bytes()
        runtime_env_mode = stat.S_IMODE(config.runtime_active_env.stat().st_mode)
        gateway_env_mode = stat.S_IMODE(config.gateway_active_env.stat().st_mode)
        runtime_env = read_active_environment(config.runtime_active_env)
        gateway_env = read_active_environment(config.gateway_active_env)
        predecessor_provider_account_home = predecessor_provider_account_state_path(
            config,
            predecessor_runtime_environment(config, runtime_env),
        )
        canonical_provider_account_home = _validated_provider_account_state_path(
            config,
            provider_account_state_path(config.state_dir),
            field="canonical provider-account home",
        )
        previous_ports = _ports_from_environments(runtime_env, gateway_env)
        validate_candidate_ports(config.candidate_ports, previous_ports)

        system.rootless_probe()
        system.probe_group(phase="preflight", ports=previous_ports, expected=config.expected)
        ingress = adapters.call_ingress(
            "inspect",
            {"release_id": previous_release_id, "ports": previous_ports},
        )
        adapters.call_acceptance(
            "preflight",
            _candidate_payload(config, previous_ports, release_dir=previous_release),
        )

        transaction = config.transactions_dir / f"rollout-{int(time.time())}-{uuid.uuid4().hex[:12]}"
        transaction.mkdir(mode=0o700)
        journal: dict[str, object] = {
            "schema_version": 1,
            "release_id": config.release_id,
            "previous_release_id": previous_release_id,
            "previous_release": str(previous_release),
            "ingress_snapshot_id": str(ingress.get("snapshot_id") or ""),
            "runtime_active_env_mode": runtime_env_mode,
            "gateway_active_env_mode": gateway_env_mode,
            "predecessor_provider_account_home": str(
                predecessor_provider_account_home
            ),
            "created_at_unix": time.time(),
        }
        _journal_write(transaction, journal, "prepared")
        _atomic_write(transaction / "runtime-active.before", runtime_env_bytes, mode=0o600)
        _atomic_write(transaction / "gateway-active.before", gateway_env_bytes, mode=0o600)

        backups: dict[str, Path] = {}
        absent_before: set[str] = set()
        before_receipts: dict[str, dict[str, object]] = {}
        state_snapshot_ready = False
        state_clone_ready = False
        ingress_switched = False
        try:
            system.stop_group()
            system.assert_stopped(
                [
                    *(database.path for database in config.databases),
                    shared_link_ref_state_path(config.state_dir),
                ],
                provider_account_paths=sorted(
                    {
                        canonical_provider_account_home,
                        predecessor_provider_account_home,
                    }
                ),
            )
            _journal_write(transaction, journal, "live_stopped")

            state_snapshot = adapters.call_state(
                "snapshot",
                {
                    "release_id": previous_release_id,
                    "live_state_dir": str(config.state_dir),
                    "transaction_dir": str(transaction),
                    "database_paths": [str(database.path) for database in config.databases],
                    "shared_link_ref_state": shared_link_ref_state_contract(
                        config, config.state_dir
                    ),
                    "provider_account_state": provider_account_state_contract(
                        config, config.state_dir
                    ),
                    "predecessor_provider_account_state": (
                        _provider_account_state_contract_for_path(
                            config,
                            predecessor_provider_account_home,
                        )
                    ),
                },
            )
            state_snapshot_id = str(state_snapshot.get("snapshot_id") or "")
            if not state_snapshot_id:
                raise RolloutError("state adapter did not return a durable snapshot receipt")
            state_snapshot_ready = True
            journal["state_snapshot_id"] = state_snapshot_id
            _journal_write(transaction, journal, "state_snapshotted")
            provider_materialization = adapters.call_state(
                "materialize_live",
                {
                    "snapshot_id": str(journal.get("state_snapshot_id") or ""),
                    "source_provider_account_state": (
                        _provider_account_state_contract_for_path(
                            config,
                            predecessor_provider_account_home,
                        )
                    ),
                    "live_provider_account_state": provider_account_state_contract(
                        config,
                        config.state_dir,
                    ),
                    "source_present": predecessor_provider_account_home.is_dir(),
                    "live_present_before": canonical_provider_account_home.is_dir(),
                    "source_is_live": (
                        predecessor_provider_account_home
                        == canonical_provider_account_home
                    ),
                    "source_must_remain_unchanged": True,
                },
            )
            provider_state_materialize_id = str(
                provider_materialization.get("materialize_live_id") or ""
            )
            if not provider_state_materialize_id:
                raise RolloutError(
                    "state adapter did not return a provider-state materialization receipt"
                )
            journal["provider_state_materialize_id"] = provider_state_materialize_id
            _journal_write(transaction, journal, "provider_state_materialized")
            if (
                not canonical_provider_account_home.is_dir()
                or canonical_provider_account_home.is_symlink()
            ):
                raise RolloutError(
                    "state adapter did not materialize safe live provider-account state"
                )
            shared_ref_state = system.prepare_shared_link_ref_state(config.state_dir)
            migrate_legacy_link_ref_state(
                shared_ref_state,
                legacy_link_ref_state_paths(config),
                state_dir=config.state_dir,
            )

            for database in config.databases:
                if not database.path.exists() and database.allow_create_if_missing:
                    absent_before.add(database.name)
                    before_receipts[database.name] = {
                        "absent_before": True,
                        "schema_ledger": [],
                        "tables": {},
                    }
                    continue
                backup = transaction / "backup" / f"{database.name}.sqlite3"
                restore_test = transaction / "restore-test" / f"{database.name}.sqlite3"
                before_receipts[database.name] = backup_and_restore_test(
                    source=database.path,
                    backup=backup,
                    restore_test=restore_test,
                    invariants=database.invariants,
                )
                backups[database.name] = backup
            journal["databases_absent_before"] = sorted(absent_before)
            _atomic_write(transaction / "database-before.json", _json_bytes(before_receipts), mode=0o600)
            journal["database_backups_verified"] = True
            _journal_write(transaction, journal, "backup_verified")

            candidate_state = _safe_child(
                config.candidate_state_root,
                config.candidate_state_root / transaction.name,
                field="candidate state directory",
            )
            journal["candidate_state_dir"] = str(candidate_state)
            _journal_write(transaction, journal, "state_clone_attempted")
            state_clone_ready = True
            state_clone = adapters.call_state(
                "clone",
                {
                    "snapshot_id": str(journal.get("state_snapshot_id") or ""),
                    "live_state_dir": str(config.state_dir),
                    "candidate_state_dir": str(candidate_state),
                    "database_paths": [str(database.path) for database in config.databases],
                    "candidate_databases": [
                        {
                            "relative": database.candidate_relative.as_posix(),
                            "access": "runtime" if database.env_name == "WPR_DB_PATH" else "gateway_only",
                        }
                        for database in config.databases
                    ],
                    "live_provider_account_state": provider_account_state_contract(
                        config, config.state_dir
                    ),
                    "candidate_provider_account_state": provider_account_state_contract(
                        config, candidate_state
                    ),
                },
            )
            journal["state_clone_id"] = str(state_clone.get("clone_id") or "")
            if not candidate_state.is_dir() or candidate_state.is_symlink():
                raise RolloutError("state adapter did not materialize a safe candidate state directory")
            candidate_provider_account_home = provider_account_state_path(
                candidate_state
            )
            if (
                not candidate_provider_account_home.is_dir()
                or candidate_provider_account_home.is_symlink()
            ):
                raise RolloutError(
                    "state adapter did not materialize candidate provider-account state"
                )
            candidate_databases: dict[str, Path] = {}
            for database in config.databases:
                candidate_path = _safe_child(
                    candidate_state,
                    candidate_state / database.candidate_relative,
                    field=f"candidate database {database.name}",
                )
                if not candidate_path.parent.is_dir() or candidate_path.parent.is_symlink():
                    raise RolloutError("state adapter did not prepare the candidate database parent")
                if database.name not in absent_before:
                    _sqlite_backup(backups[database.name], candidate_path)
                candidate_databases[database.env_name] = candidate_path
            candidate_shared_ref_state = system.prepare_shared_link_ref_state(candidate_state)
            migrate_legacy_link_ref_state(
                candidate_shared_ref_state,
                legacy_link_ref_state_paths(
                    config,
                    state_dir=candidate_state,
                    auth_database=candidate_databases["GLASSHIVE_AUTH_STATE_PATH"],
                ),
                state_dir=candidate_state,
            )
            clone_seal = adapters.call_state(
                "seal_clone",
                {
                    "clone_id": str(journal.get("state_clone_id") or ""),
                    "candidate_state_dir": str(candidate_state),
                    "databases": [
                        {
                            "name": database.name,
                            "path": str(candidate_databases[database.env_name]),
                            "mode": f"{database.restore_mode:04o}",
                            "access": "runtime" if database.env_name == "WPR_DB_PATH" else "gateway_only",
                            "may_create": database.name in absent_before,
                        }
                        for database in config.databases
                    ],
                    "shared_link_ref_state": shared_link_ref_state_contract(
                        config, candidate_state
                    ),
                    "provider_account_state": provider_account_state_contract(
                        config, candidate_state
                    ),
                },
            )
            journal["state_seal_id"] = str(clone_seal.get("seal_clone_id") or "")

            rehearsal_runtime, rehearsal_gateway = _active_values(
                config,
                ports=config.candidate_ports,
                state_dir=candidate_state,
                database_paths=candidate_databases,
                # A rehearsal clone validates migrations/readiness only. Executing a
                # copied durable queue, schedule, callback, or reaper here would repeat
                # side effects when live starts.
                background_consumers_enabled=False,
                reconcile_on_startup=False,
            )
            _atomic_symlink(config.release_dir, config.current_symlink)
            write_active_environment(config.runtime_active_env, rehearsal_runtime)
            write_active_environment(config.gateway_active_env, rehearsal_gateway)
            _journal_write(transaction, journal, "rehearsal_prepared")
            system.start_group(phase="rehearsal")
            system.probe_group(phase="rehearsal", ports=config.candidate_ports, expected=config.expected)
            adapters.call_acceptance("candidate", _candidate_payload(config, config.candidate_ports))
            system.stop_group()
            system.assert_stopped(
                [
                    *candidate_databases.values(),
                    shared_link_ref_state_path(candidate_state),
                ],
                provider_account_paths=[
                    provider_account_state_path(candidate_state)
                ],
            )

            after_receipts: dict[str, dict[str, object]] = {}
            for database in config.databases:
                receipt = inspect_database(
                    candidate_databases[database.env_name],
                    [*database.invariants, *database.post_migration_invariants],
                )
                compare_migration_invariants(before_receipts[database.name], receipt)
                after_receipts[database.name] = receipt
            _atomic_write(transaction / "database-rehearsal.json", _json_bytes(after_receipts), mode=0o600)
            _journal_write(transaction, journal, "rehearsal_passed")

            live_databases = {database.env_name: database.path for database in config.databases}
            live_runtime, live_gateway = _active_values(
                config,
                ports=config.candidate_ports,
                state_dir=config.state_dir,
                database_paths=live_databases,
                background_consumers_enabled=True,
                reconcile_on_startup=True,
            )
            write_active_environment(config.runtime_active_env, live_runtime)
            write_active_environment(config.gateway_active_env, live_gateway)
            _journal_write(transaction, journal, "candidate_live_prepared")
            system.start_group(phase="candidate-live")
            system.probe_group(phase="candidate-live", ports=config.candidate_ports, expected=config.expected)
            for database in config.databases:
                live_receipt = inspect_database(
                    database.path,
                    [*database.invariants, *database.post_migration_invariants],
                )
                compare_migration_invariants(before_receipts[database.name], live_receipt)
            _journal_write(transaction, journal, "candidate_live_ready")

            _journal_write(transaction, journal, "ingress_switch_attempted")
            ingress_switched = True
            route_contract = ingress_route_contract(config.candidate_ports)
            adapters.call_ingress(
                "switch",
                {
                    "release_id": config.release_id,
                    "previous_release_id": previous_release_id,
                    "previous_snapshot_id": str(journal.get("ingress_snapshot_id") or ""),
                    "ports": config.candidate_ports,
                    "route_contract": route_contract,
                },
            )
            _journal_write(transaction, journal, "ingress_switched")
            adapters.call_acceptance("live", _candidate_payload(config, config.candidate_ports))
            adapters.call_ingress(
                "status",
                {
                    "release_id": config.release_id,
                    "ports": config.candidate_ports,
                    "route_contract": route_contract,
                },
            )
            state_commit = adapters.call_state(
                "commit",
                {
                    "snapshot_id": str(journal.get("state_snapshot_id") or ""),
                    "release_id": config.release_id,
                    "backup_dir": str(transaction / "backup"),
                    "shared_link_ref_state": shared_link_ref_state_contract(
                        config, config.state_dir
                    ),
                    "provider_account_state": provider_account_state_contract(
                        config, config.state_dir
                    ),
                },
            )
            journal["state_commit_id"] = str(state_commit.get("commit_id") or "")
            adapters.call_state(
                "cleanup_clone",
                {
                    "clone_id": str(journal.get("state_clone_id") or ""),
                    "candidate_state_dir": str(candidate_state),
                },
            )
            _journal_write(transaction, journal, "committed")
            return {
                "status": "committed",
                "release_id": config.release_id,
                "previous_release_id": previous_release_id,
                "transaction_id": transaction.name,
            }
        except BaseException as original:
            try:
                _rollback(
                    config=config,
                    system=system,
                    adapters=adapters,
                    transaction=transaction,
                    journal=journal,
                    previous_release=previous_release,
                    previous_release_id=previous_release_id,
                    previous_ports=previous_ports,
                    runtime_env_bytes=runtime_env_bytes,
                    runtime_env_mode=runtime_env_mode,
                    gateway_env_bytes=gateway_env_bytes,
                    gateway_env_mode=gateway_env_mode,
                    backups=backups,
                    state_snapshot_ready=state_snapshot_ready,
                    state_clone_ready=state_clone_ready,
                    ingress_switched=ingress_switched,
                    absent_before=absent_before,
                    predecessor_provider_account_home=(
                        predecessor_provider_account_home
                    ),
                )
            # Recovery must also journal failures raised while handling process-loss signals.
            except BaseException as rollback_error:  # noqa: BLE001
                _journal_write(transaction, journal, "rollback_failed", failure_class=type(rollback_error).__name__)
                raise RolloutError(
                    f"rollout failed and rollback is incomplete; recover {transaction.name}: {rollback_error}"
                ) from original
            if isinstance(original, RolloutError):
                raise
            raise RolloutError(f"rollout failed and predecessor was restored: {type(original).__name__}") from original
    finally:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
        lock_handle.close()


def _recover_rollout_locked(
    config: RolloutConfig,
    *,
    transaction_id: str,
    system: Any | None = None,
    adapters: Any | None = None,
) -> dict[str, object]:
    """Retry predecessor restoration after process loss or an incomplete rollback."""

    if not re.fullmatch(r"rollout-[0-9]+-[0-9a-f]{12}", transaction_id):
        raise RolloutError("invalid rollout transaction id")
    production = system is None or adapters is None
    if production:
        validate_adapter_path(config.ingress_adapter)
        validate_adapter_path(config.state_adapter)
        validate_adapter_path(config.acceptance_adapter)
    system = system or ProductionSystem(config)
    adapters = adapters or ProductionAdapters(config)
    transaction = _safe_child(
        config.transactions_dir,
        config.transactions_dir / transaction_id,
        field="rollout transaction",
    )
    journal_path = transaction / "journal.json"
    try:
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RolloutError("rollout journal is unreadable") from exc
    if not isinstance(journal, dict) or journal.get("schema_version") != 1:
        raise RolloutError("rollout journal schema is unsupported")
    if journal.get("status") in {"committed", "rolled_back"}:
        raise RolloutError("rollout transaction is already terminal")
    if journal.get("release_id") != config.release_id:
        raise RolloutError("rollout journal does not match the requested release")
    previous_release_id = str(journal.get("previous_release_id") or "")
    previous_release = Path(str(journal.get("previous_release") or ""))
    _safe_child(config.releases_root, previous_release, field="previous release")
    verify_release_manifest(previous_release, expected_release_id=previous_release_id)
    runtime_before = transaction / "runtime-active.before"
    gateway_before = transaction / "gateway-active.before"
    runtime_env_bytes = runtime_before.read_bytes()
    gateway_env_bytes = gateway_before.read_bytes()
    previous_ports = _ports_from_environments(
        read_active_environment(runtime_before),
        read_active_environment(gateway_before),
    )
    predecessor_provider_account_home_value = str(
        journal.get("predecessor_provider_account_home") or ""
    )
    if predecessor_provider_account_home_value:
        predecessor_provider_account_home = _validated_provider_account_state_path(
            config,
            Path(predecessor_provider_account_home_value),
            field="predecessor provider-account home",
        )
    else:
        if production:
            if config.runtime_env_file != Path("/etc/viventium/glasshive/runtime.env"):
                raise RolloutError(
                    "runtime_env_file does not match the installed systemd unit contract"
                )
            try:
                state_gid = grp.getgrnam("glasshive-state").gr_gid
            except KeyError as exc:
                raise RolloutError("GlassHive service groups are missing") from exc
            _validate_service_environment_file(
                config.runtime_env_file,
                expected_gid=state_gid,
            )
        predecessor_provider_account_home = predecessor_provider_account_state_path(
            config,
            predecessor_runtime_environment(
                config,
                read_active_environment(runtime_before),
            ),
        )
    backups = {
        database.name: transaction / "backup" / f"{database.name}.sqlite3"
        for database in config.databases
    }
    absent_before = {
        str(item) for item in journal.get("databases_absent_before", []) if isinstance(item, str)
    }
    database_backups_verified = bool(journal.get("database_backups_verified")) or (
        transaction / "database-before.json"
    ).is_file()
    if database_backups_verified:
        missing = [
            name for name, path in backups.items() if name not in absent_before and not path.is_file()
        ]
        if missing:
            raise RolloutError("verified database backup is missing; recovery remains blocked")
    status = str(journal.get("status") or "")
    ingress_attempted = status in {
        "ingress_switch_attempted",
        "ingress_switched",
        "rolling_back",
        "rollback_failed",
    }
    _rollback(
        config=config,
        system=system,
        adapters=adapters,
        transaction=transaction,
        journal=journal,
        previous_release=previous_release,
        previous_release_id=previous_release_id,
        previous_ports=previous_ports,
        runtime_env_bytes=runtime_env_bytes,
        runtime_env_mode=int(journal.get("runtime_active_env_mode") or 0o640),
        gateway_env_bytes=gateway_env_bytes,
        gateway_env_mode=int(journal.get("gateway_active_env_mode") or 0o640),
        backups=backups,
        state_snapshot_ready=bool(journal.get("state_snapshot_id")),
        state_clone_ready=bool(journal.get("candidate_state_dir")),
        ingress_switched=ingress_attempted,
        absent_before=absent_before,
        predecessor_provider_account_home=predecessor_provider_account_home,
    )
    return {
        "status": "rolled_back",
        "release_id": config.release_id,
        "previous_release_id": previous_release_id,
        "transaction_id": transaction_id,
    }


def recover_rollout(
    config: RolloutConfig,
    *,
    transaction_id: str,
    system: Any | None = None,
    adapters: Any | None = None,
) -> dict[str, object]:
    production = system is None or adapters is None
    if production and config.lock_file != HOSTED_MUTATION_LOCK:
        raise RolloutError(
            "hosted GlassHive rollout lock must be /run/lock/glasshive-rollout.lock"
        )
    lock_handle = _open_mutation_lock(config.lock_file)
    try:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        lock_handle.close()
        raise RolloutError(
            "another GlassHive mutation holds the deployment lock; retry after it completes"
        ) from exc
    try:
        return _recover_rollout_locked(
            config,
            transaction_id=transaction_id,
            system=system,
            adapters=adapters,
        )
    finally:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
        lock_handle.close()


def _database_from_json(value: Mapping[str, object]) -> DatabaseConfig:
    invariants = value.get("invariants")
    if not isinstance(invariants, list):
        raise RolloutError("database invariants must be a list")
    raw_mode = str(value.get("restore_mode") or "0660")
    if not re.fullmatch(r"0?[0-7]{3}", raw_mode):
        raise RolloutError("database restore_mode must be an octal mode")
    post_migration = value.get("post_migration_invariants", [])
    if not isinstance(post_migration, list):
        raise RolloutError("database post_migration_invariants must be a list")
    return DatabaseConfig(
        name=str(value.get("name") or ""),
        path=Path(str(value.get("path") or "")),
        env_name=str(value.get("env_name") or ""),
        candidate_relative=Path(str(value.get("candidate_relative") or "")),
        invariants=[dict(item) for item in invariants if isinstance(item, dict)],
        post_migration_invariants=[dict(item) for item in post_migration if isinstance(item, dict)],
        allow_create_if_missing=value.get("allow_create_if_missing") is True,
        restore_mode=int(raw_mode, 8),
    )


def config_from_json(path: Path) -> RolloutConfig:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RolloutError("rollout configuration is unreadable") from exc
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise RolloutError("rollout configuration schema is unsupported")
    databases = value.get("databases")
    if not isinstance(databases, list):
        raise RolloutError("rollout databases must be a list")
    return RolloutConfig(
        release_id=str(value.get("release_id") or ""),
        release_dir=Path(str(value.get("release_dir") or "")),
        releases_root=Path(str(value.get("releases_root") or "")),
        current_symlink=Path(str(value.get("current_symlink") or "")),
        runtime_active_env=Path(str(value.get("runtime_active_env") or "")),
        gateway_active_env=Path(str(value.get("gateway_active_env") or "")),
        state_dir=Path(str(value.get("state_dir") or "")),
        transactions_dir=Path(str(value.get("transactions_dir") or "")),
        candidate_state_root=(
            Path(str(value.get("candidate_state_root"))) if value.get("candidate_state_root") else None
        ),
        candidate_ports={str(key): int(item) for key, item in dict(value.get("candidate_ports") or {}).items()},
        expected=dict(value.get("expected") or {}),
        databases=[_database_from_json(item) for item in databases if isinstance(item, dict)],
        ingress_adapter=Path(str(value.get("ingress_adapter") or "")),
        state_adapter=Path(str(value.get("state_adapter") or "")),
        acceptance_adapter=Path(str(value.get("acceptance_adapter") or "")),
        runtime_user=str(value.get("runtime_user") or "glasshive-runtime"),
        lock_file=Path(str(value["lock_file"])) if value.get("lock_file") else None,
        runtime_env_file=Path(str(value.get("runtime_env_file") or "/etc/viventium/glasshive/runtime.env")),
        gateway_env_file=Path(str(value.get("gateway_env_file") or "/etc/viventium/glasshive/gateway.env")),
        probe_timeout_sec=float(value.get("probe_timeout_sec") or 60),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    deploy = subparsers.add_parser("deploy", help="rehearse, cut over, and verify one release")
    deploy.add_argument("--config", type=Path, required=True)
    recover = subparsers.add_parser("recover", help="restore the predecessor from an incomplete journal")
    recover.add_argument("--config", type=Path, required=True)
    recover.add_argument("--transaction-id", required=True)
    stage = subparsers.add_parser("stage", help="stage a clean committed release with frozen environments")
    stage.add_argument("--source", type=Path, required=True)
    stage.add_argument("--releases-root", type=Path, required=True)
    stage.add_argument("--release-id", required=True)
    stage.add_argument("--uv", type=Path, required=True)
    stage.add_argument("--python", type=Path, required=True)
    verify = subparsers.add_parser("verify-release", help="verify an immutable staged release")
    verify.add_argument("--release-dir", type=Path, required=True)
    verify.add_argument("--release-id", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        if arguments.command == "stage":
            manifest = stage_release(
                source=arguments.source,
                releases_root=arguments.releases_root,
                release_id=arguments.release_id,
                uv=arguments.uv,
                python=arguments.python,
            )
            print(
                json.dumps(
                    {
                        "ok": True,
                        "release_id": manifest["release_id"],
                        "parent_revision": manifest["parent_revision"],
                        "glasshive_revision": manifest["glasshive_revision"],
                    },
                    sort_keys=True,
                )
            )
            return 0
        if arguments.command == "verify-release":
            manifest = verify_release_manifest(arguments.release_dir, expected_release_id=arguments.release_id)
            print(json.dumps({"ok": True, "release_id": manifest["release_id"]}, sort_keys=True))
            return 0
        if os.geteuid() != 0:
            raise RolloutError("hosted deployment must run as root")
        config = config_from_json(arguments.config)
        if arguments.command == "recover":
            receipt = recover_rollout(config, transaction_id=arguments.transaction_id)
        else:
            receipt = execute_rollout(config)
        print(json.dumps(receipt, sort_keys=True))
        return 0
    except RolloutError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

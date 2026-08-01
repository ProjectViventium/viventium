#!/usr/bin/env python3
"""Reconcile the local RAG PostgreSQL role without replacing persisted PGDATA.

The official PostgreSQL image consumes POSTGRES_PASSWORD only while initializing an
empty data directory. Viventium therefore owns a separate, stable machine-local
credential and reconciles the existing application role over the container's local
Unix socket before the RAG API starts.

No secret is accepted on the command line, emitted to stdout/stderr, or written to
the migration receipt. The only durable secret is the owner-only credential file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import stat
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


POSTGRES_DATABASE = "mydatabase"
POSTGRES_ROLE = "myuser"
POSTGRES_DATA_DESTINATION = "/var/lib/postgresql/data"
COMPOSE_SERVICE = "vectordb"
EXPECTED_LEGACY_RELATIONS = {
    ("public", "langchain_pg_collection", "r"),
    ("public", "langchain_pg_embedding", "r"),
}
ALLOWED_EXTENSIONS = {"plpgsql", "vector"}
HEX_SECRET_RE = re.compile(r"[0-9a-f]{64}")
DECIMAL_RE = re.compile(r"[0-9]+")


class MigrationError(RuntimeError):
    """A public-safe, secret-free migration failure."""


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


class DockerRunner(Protocol):
    def run(
        self,
        args: list[str],
        *,
        input_text: str | None = None,
        env: dict[str, str] | None = None,
    ) -> CommandResult: ...


class SubprocessDocker:
    def run(
        self,
        args: list[str],
        *,
        input_text: str | None = None,
        env: dict[str, str] | None = None,
    ) -> CommandResult:
        completed = subprocess.run(
            ["docker", *args],
            input=input_text,
            text=True,
            capture_output=True,
            check=False,
            env={**os.environ, **(env or {})},
            timeout=600,
        )
        return CommandResult(
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    def stream_stdout_digest(
        self,
        args: list[str],
        *,
        input_text: str,
    ) -> StreamDigestResult:
        digest = hashlib.sha256()
        row_count = 0
        saw_bytes = False
        last_byte = b""
        with tempfile.TemporaryFile() as stderr_file:
            process = subprocess.Popen(
                ["docker", *args],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=stderr_file,
            )
            assert process.stdin is not None
            assert process.stdout is not None
            process.stdin.write(input_text.encode("utf-8"))
            process.stdin.close()
            for chunk in iter(lambda: process.stdout.read(1024 * 1024), b""):
                saw_bytes = True
                last_byte = chunk[-1:]
                row_count += chunk.count(b"\n")
                digest.update(chunk)
            returncode = process.wait(timeout=600)
            stderr_file.seek(0)
            stderr = stderr_file.read().decode("utf-8", errors="replace")
        if saw_bytes and last_byte != b"\n":
            row_count += 1
        return StreamDigestResult(
            returncode=returncode,
            row_count=row_count,
            sha256=digest.hexdigest(),
            stderr=stderr,
        )


@dataclass(frozen=True)
class ClusterIdentity:
    server_version_num: int
    system_identifier: str
    database_oid: str
    role_oid: str
    schema_class: str
    schema_sha256: str
    row_fingerprints: dict[str, dict[str, object]]


@dataclass(frozen=True)
class MigrationResult:
    status: str
    credential_path: Path
    receipt_path: Path


@dataclass(frozen=True)
class StreamDigestResult:
    returncode: int
    row_count: int
    sha256: str
    stderr: str


def _reject_symlink_components(path: Path, label: str) -> None:
    absolute = path.absolute()
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current = current / part
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(metadata.st_mode):
            raise MigrationError(f"{label} must not contain symlinks")


def _require_regular_file(path: Path, label: str, *, owner_only: bool = False) -> None:
    _reject_symlink_components(path, label)
    try:
        metadata = path.lstat()
    except FileNotFoundError as error:
        raise MigrationError(f"{label} is missing") from error
    if not stat.S_ISREG(metadata.st_mode):
        raise MigrationError(f"{label} must be a regular file")
    if metadata.st_uid != os.getuid():
        raise MigrationError(f"{label} has unsafe ownership")
    if owner_only and stat.S_IMODE(metadata.st_mode) != 0o600:
        raise MigrationError(f"{label} must use owner-only permissions")


def _prepare_state_dir(state_dir: Path) -> None:
    if not state_dir.is_absolute():
        raise MigrationError("RAG PostgreSQL state directory must be absolute")
    _reject_symlink_components(state_dir, "RAG PostgreSQL state directory")
    try:
        state_dir.mkdir(parents=True, mode=0o700, exist_ok=True)
    except OSError as error:
        raise MigrationError("RAG PostgreSQL state directory could not be created") from error
    try:
        metadata = state_dir.lstat()
    except OSError as error:
        raise MigrationError("RAG PostgreSQL state directory is unavailable") from error
    if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.getuid():
        raise MigrationError("RAG PostgreSQL state directory has unsafe ownership")
    if stat.S_IMODE(metadata.st_mode) & 0o077:
        raise MigrationError("RAG PostgreSQL state directory must be owner-only")


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_json_write(path: Path, payload: dict[str, object]) -> None:
    data = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}-{secrets.token_hex(6)}")
    descriptor = -1
    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        os.write(descriptor, data)
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        os.replace(temporary, path)
        os.chmod(path, 0o600)
        _fsync_directory(path.parent)
    except OSError as error:
        raise MigrationError("RAG PostgreSQL migration state could not be persisted") from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _read_json_file(path: Path, label: str) -> dict[str, object]:
    _require_regular_file(path, label, owner_only=True)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise MigrationError(f"{label} is invalid") from error
    if not isinstance(payload, dict):
        raise MigrationError(f"{label} is invalid")
    return payload


def _load_or_create_credential(state_dir: Path, receipt_path: Path) -> tuple[Path, str]:
    credential_path = state_dir / "postgres-password"
    if credential_path.exists() or credential_path.is_symlink():
        _require_regular_file(
            credential_path,
            "RAG PostgreSQL credential file",
            owner_only=True,
        )
        try:
            value = credential_path.read_text(encoding="ascii").strip()
        except (OSError, UnicodeError) as error:
            raise MigrationError("RAG PostgreSQL credential file is invalid") from error
        if not HEX_SECRET_RE.fullmatch(value):
            raise MigrationError("RAG PostgreSQL credential file is invalid")
        return credential_path, value

    if receipt_path.exists() or receipt_path.is_symlink():
        raise MigrationError(
            "RAG PostgreSQL credential file is missing while a migration receipt exists"
        )

    value = secrets.token_hex(32)
    descriptor = -1
    try:
        descriptor = os.open(
            credential_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        os.write(descriptor, (value + "\n").encode("ascii"))
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        _fsync_directory(state_dir)
    except FileExistsError:
        return _load_or_create_credential(state_dir, receipt_path)
    except OSError as error:
        raise MigrationError("RAG PostgreSQL credential file could not be created") from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)

    return credential_path, value


def _compose_args(project_name: str, compose_file: Path, *tail: str) -> list[str]:
    return [
        "compose",
        "--project-name",
        project_name,
        "-f",
        str(compose_file),
        *tail,
    ]


def _run_required(
    docker: DockerRunner,
    args: list[str],
    *,
    failure_message: str,
    input_text: str | None = None,
    env: dict[str, str] | None = None,
) -> str:
    result = docker.run(args, input_text=input_text, env=env)
    if result.returncode != 0:
        raise MigrationError(failure_message)
    return result.stdout.strip()


def _single_container_id(raw: str) -> str:
    identifiers = [line.strip() for line in raw.splitlines() if line.strip()]
    if len(identifiers) != 1 or not re.fullmatch(r"[A-Za-z0-9_.:-]+", identifiers[0]):
        raise MigrationError("RAG PostgreSQL Compose container identity is unavailable")
    return identifiers[0]


def _validate_pgdata_path(pgdata_path: Path, pgdata_path_mode: str) -> str:
    if not pgdata_path.is_absolute():
        raise MigrationError("RAG PostgreSQL PGDATA path must be absolute")
    if pgdata_path_mode == "host":
        _reject_symlink_components(pgdata_path, "RAG PostgreSQL PGDATA path")
        try:
            metadata = pgdata_path.lstat()
        except FileNotFoundError as error:
            raise MigrationError("RAG PostgreSQL PGDATA path is missing") from error
        if not stat.S_ISDIR(metadata.st_mode):
            raise MigrationError("RAG PostgreSQL PGDATA path must be a directory")
        return str(pgdata_path.resolve())
    if pgdata_path_mode == "daemon":
        value = str(pgdata_path)
        if (
            not value.startswith("/var/lib/viventium/")
            or value in {"/var/lib/viventium", "/var/lib/viventium/"}
            or any(character in value for character in ("\n", "\r", "\t", ":"))
            or "//" in value
            or "/./" in value
            or "/../" in value
            or value.endswith(("/.", "/.."))
        ):
            raise MigrationError(
                "RAG PostgreSQL daemon PGDATA path is outside the owned namespace"
            )
        return value
    raise MigrationError("RAG PostgreSQL PGDATA mode must be host or daemon")


def _load_json_output(raw: str, label: str) -> dict[str, object] | list[object]:
    try:
        payload = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as error:
        raise MigrationError(f"{label} is invalid") from error
    if not isinstance(payload, (dict, list)):
        raise MigrationError(f"{label} is invalid")
    return payload


def _validate_container_provenance(
    docker: DockerRunner,
    *,
    container_id: str,
    project_name: str,
    expected_pgdata_source: str,
) -> None:
    mounts_raw = _run_required(
        docker,
        ["inspect", "--format", "{{json .Mounts}}", container_id],
        failure_message="RAG PostgreSQL container mount inspection failed",
    )
    mounts = _load_json_output(mounts_raw, "RAG PostgreSQL container mount inventory")
    if not isinstance(mounts, list):
        raise MigrationError("RAG PostgreSQL container mount inventory is invalid")
    matching_mounts = [
        mount
        for mount in mounts
        if isinstance(mount, dict)
        and mount.get("Destination") == POSTGRES_DATA_DESTINATION
    ]
    if len(matching_mounts) != 1:
        raise MigrationError("RAG PostgreSQL PGDATA mount is missing or ambiguous")
    mount = matching_mounts[0]
    if mount.get("Type") != "bind" or mount.get("Source") != expected_pgdata_source:
        raise MigrationError("RAG PostgreSQL PGDATA mount does not match the selected runtime")

    labels_raw = _run_required(
        docker,
        ["inspect", "--format", "{{json .Config.Labels}}", container_id],
        failure_message="RAG PostgreSQL container label inspection failed",
    )
    labels = _load_json_output(labels_raw, "RAG PostgreSQL container label inventory")
    if not isinstance(labels, dict):
        raise MigrationError("RAG PostgreSQL container label inventory is invalid")
    if (
        labels.get("com.docker.compose.project") != project_name
        or labels.get("com.docker.compose.service") != COMPOSE_SERVICE
    ):
        raise MigrationError("RAG PostgreSQL container is not owned by the selected Compose project")


def _postgres_ready_retries() -> int:
    raw_retries = os.environ.get("VIVENTIUM_RAG_POSTGRES_READY_RETRIES", "60")
    try:
        retries = int(raw_retries)
    except ValueError:
        retries = 60
    if not 1 <= retries <= 600:
        retries = 60
    return retries


def _wait_for_postgres(docker: DockerRunner, container_id: str) -> None:
    retries = _postgres_ready_retries()
    for attempt in range(retries):
        result = docker.run(
            [
                "exec",
                "--user",
                "postgres",
                container_id,
                "pg_isready",
                "--username",
                POSTGRES_ROLE,
                "--dbname",
                POSTGRES_DATABASE,
                "--timeout",
                "2",
            ]
        )
        if result.returncode == 0:
            return
        if attempt + 1 < retries:
            time.sleep(1)
    raise MigrationError("RAG PostgreSQL did not become ready for identity inspection")


IDENTITY_SQL = f"""
SELECT json_build_object(
  'serverVersionNum', current_setting('server_version_num')::integer,
  'systemIdentifier', (SELECT system_identifier::text FROM pg_control_system()),
  'databaseOid', (SELECT oid::text FROM pg_database WHERE datname = '{POSTGRES_DATABASE}'),
  'databaseOwner', (
    SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname = '{POSTGRES_DATABASE}'
  ),
  'roleOid', (SELECT oid::text FROM pg_roles WHERE rolname = '{POSTGRES_ROLE}'),
  'roleCanLogin', (SELECT rolcanlogin FROM pg_roles WHERE rolname = '{POSTGRES_ROLE}')
)::text;
""".lstrip()


SCHEMA_SQL = """
SELECT json_build_object(
  'relationInventory',
  COALESCE(
    (
      SELECT json_agg(
        json_build_object('schema', schema_name, 'name', relation_name, 'kind', relation_kind)
        ORDER BY schema_name, relation_name, relation_kind
      )
      FROM (
        SELECT n.nspname AS schema_name, c.relname AS relation_name, c.relkind::text AS relation_kind
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
          AND n.nspname NOT LIKE 'pg_toast%'
          AND c.relkind IN ('r', 'p', 'v', 'm', 'f', 'S')
      ) relations
    ),
    '[]'::json
  ),
  'extensions',
  COALESCE(
    (SELECT json_agg(extname ORDER BY extname) FROM pg_extension),
    '[]'::json
  ),
  'columnInventory',
  COALESCE(
    (
      SELECT json_agg(
        json_build_object(
          'schema', table_schema,
          'relation', table_name,
          'ordinal', ordinal_position,
          'name', column_name,
          'typeSchema', udt_schema,
          'typeName', udt_name,
          'nullable', is_nullable,
          'default', column_default
        )
        ORDER BY table_schema, table_name, ordinal_position
      )
      FROM information_schema.columns
      WHERE table_schema = 'public'
        AND table_name IN ('langchain_pg_collection', 'langchain_pg_embedding')
    ),
    '[]'::json
  ),
  'indexInventory',
  COALESCE(
    (
      SELECT json_agg(
        json_build_object(
          'schema', schemaname,
          'relation', tablename,
          'name', indexname,
          'definition', indexdef
        )
        ORDER BY schemaname, tablename, indexname
      )
      FROM pg_indexes
      WHERE schemaname = 'public'
        AND tablename IN ('langchain_pg_collection', 'langchain_pg_embedding')
    ),
    '[]'::json
  ),
  'constraintInventory',
  COALESCE(
    (
      SELECT json_agg(
        json_build_object(
          'schema', n.nspname,
          'relation', c.relname,
          'name', constraint_record.conname,
          'type', constraint_record.contype::text,
          'definition', pg_get_constraintdef(constraint_record.oid, true)
        )
        ORDER BY n.nspname, c.relname, constraint_record.conname
      )
      FROM pg_constraint constraint_record
      JOIN pg_class c ON c.oid = constraint_record.conrelid
      JOIN pg_namespace n ON n.oid = c.relnamespace
      WHERE n.nspname = 'public'
        AND c.relname IN ('langchain_pg_collection', 'langchain_pg_embedding')
    ),
    '[]'::json
  )
)::text AS "relationInventory";
""".lstrip()


COLLECTION_ROWS_SQL = """
-- RAG_COLLECTION_ROWS
COPY (
  SELECT row_to_json(ordered_row)::text
  FROM (
    SELECT *
    FROM public.langchain_pg_collection
    ORDER BY uuid
  ) AS ordered_row
) TO STDOUT WITH (FORMAT text);
""".lstrip()


EMBEDDING_ROWS_SQL = """
-- RAG_EMBEDDING_ROWS
COPY (
  SELECT row_to_json(ordered_row)::text
  FROM (
    SELECT *
    FROM public.langchain_pg_embedding
    ORDER BY uuid
  ) AS ordered_row
) TO STDOUT WITH (FORMAT text);
""".lstrip()


def _psql_args(container_id: str, database: str) -> list[str]:
    return [
            "exec",
            "--user",
            "postgres",
            "-i",
            container_id,
            "psql",
            "--no-psqlrc",
            "--no-align",
            "--tuples-only",
            "--quiet",
            "--set",
            "ON_ERROR_STOP=1",
            "--username",
            POSTGRES_ROLE,
            "--dbname",
            database,
    ]


def _psql(
    docker: DockerRunner,
    *,
    container_id: str,
    database: str,
    sql: str,
    failure_message: str,
    retries: int = 1,
) -> str:
    args = _psql_args(container_id, database)
    for attempt in range(retries):
        result = docker.run(args, input_text=sql)
        if result.returncode == 0:
            return result.stdout.strip()
        if attempt + 1 < retries:
            time.sleep(1)
    raise MigrationError(failure_message)


def _psql_stream_digest(
    docker: DockerRunner,
    *,
    container_id: str,
    database: str,
    sql: str,
    failure_message: str,
) -> dict[str, object]:
    args = _psql_args(container_id, database)
    streaming = getattr(docker, "stream_stdout_digest", None)
    if callable(streaming):
        result = streaming(args, input_text=sql)
    else:
        completed = docker.run(args, input_text=sql)
        encoded = completed.stdout.encode("utf-8")
        row_count = encoded.count(b"\n")
        if encoded and not encoded.endswith(b"\n"):
            row_count += 1
        result = StreamDigestResult(
            returncode=completed.returncode,
            row_count=row_count,
            sha256=hashlib.sha256(encoded).hexdigest(),
            stderr=completed.stderr,
        )
    if result.returncode != 0:
        raise MigrationError(failure_message)
    return {
        "rowCount": result.row_count,
        "sha256": result.sha256,
    }


def _empty_row_fingerprint() -> dict[str, object]:
    return {
        "rowCount": 0,
        "sha256": hashlib.sha256(b"").hexdigest(),
    }


def _inspect_row_fingerprints(
    docker: DockerRunner,
    *,
    container_id: str,
    schema_class: str,
) -> dict[str, dict[str, object]]:
    if schema_class == "fresh":
        return {
            "langchain_pg_collection": _empty_row_fingerprint(),
            "langchain_pg_embedding": _empty_row_fingerprint(),
        }
    return {
        "langchain_pg_collection": _psql_stream_digest(
            docker,
            container_id=container_id,
            database=POSTGRES_DATABASE,
            sql=COLLECTION_ROWS_SQL,
            failure_message="RAG PostgreSQL collection row fingerprint failed",
        ),
        "langchain_pg_embedding": _psql_stream_digest(
            docker,
            container_id=container_id,
            database=POSTGRES_DATABASE,
            sql=EMBEDDING_ROWS_SQL,
            failure_message="RAG PostgreSQL embedding row fingerprint failed",
        ),
    }


def _inspect_cluster(docker: DockerRunner, container_id: str) -> ClusterIdentity:
    identity: dict[str, object] | None = None
    expected_identity_keys = {
        "serverVersionNum",
        "systemIdentifier",
        "databaseOid",
        "databaseOwner",
        "roleOid",
        "roleCanLogin",
    }
    retries = _postgres_ready_retries()
    for attempt in range(retries):
        try:
            identity_raw = _psql(
                docker,
                container_id=container_id,
                database="postgres",
                sql=IDENTITY_SQL,
                failure_message="RAG PostgreSQL database identity inspection failed",
            )
        except MigrationError:
            if attempt + 1 < retries:
                time.sleep(1)
                continue
            raise
        candidate = _load_json_output(identity_raw, "RAG PostgreSQL database identity")
        if not isinstance(candidate, dict) or set(candidate) != expected_identity_keys:
            raise MigrationError("RAG PostgreSQL database identity is invalid")

        server_version_num = candidate.get("serverVersionNum")
        system_identifier = candidate.get("systemIdentifier")
        if (
            not isinstance(server_version_num, int)
            or isinstance(server_version_num, bool)
            or not 150000 <= server_version_num < 160000
            or not isinstance(system_identifier, str)
            or not DECIMAL_RE.fullmatch(system_identifier)
        ):
            raise MigrationError("RAG PostgreSQL database identity is not recognized")

        database_oid = candidate.get("databaseOid")
        database_owner = candidate.get("databaseOwner")
        role_oid = candidate.get("roleOid")
        role_can_login = candidate.get("roleCanLogin")
        if None in (database_oid, database_owner, role_oid, role_can_login):
            if attempt + 1 < retries:
                time.sleep(1)
                continue
            raise MigrationError("RAG PostgreSQL database identity is not recognized")
        if (
            not isinstance(database_oid, str)
            or not DECIMAL_RE.fullmatch(database_oid)
            or database_owner != POSTGRES_ROLE
            or not isinstance(role_oid, str)
            or not DECIMAL_RE.fullmatch(role_oid)
            or role_can_login is not True
        ):
            raise MigrationError("RAG PostgreSQL database identity is not recognized")
        identity = candidate
        break
    if identity is None:
        raise MigrationError("RAG PostgreSQL database identity is not recognized")

    server_version_num = int(identity["serverVersionNum"])
    system_identifier = str(identity["systemIdentifier"])
    database_oid = str(identity["databaseOid"])
    role_oid = str(identity["roleOid"])

    schema_raw = _psql(
        docker,
        container_id=container_id,
        database=POSTGRES_DATABASE,
        sql=SCHEMA_SQL,
        failure_message="RAG PostgreSQL schema inspection failed",
        retries=_postgres_ready_retries(),
    )
    schema = _load_json_output(schema_raw, "RAG PostgreSQL schema inventory")
    expected_schema_keys = {
        "relationInventory",
        "extensions",
        "columnInventory",
        "indexInventory",
        "constraintInventory",
    }
    if not isinstance(schema, dict) or set(schema) != expected_schema_keys:
        raise MigrationError("RAG PostgreSQL schema inventory is invalid")
    raw_relations = schema.get("relationInventory")
    raw_extensions = schema.get("extensions")
    raw_columns = schema.get("columnInventory")
    raw_indexes = schema.get("indexInventory")
    raw_constraints = schema.get("constraintInventory")
    if not all(
        isinstance(value, list)
        for value in (
            raw_relations,
            raw_extensions,
            raw_columns,
            raw_indexes,
            raw_constraints,
        )
    ):
        raise MigrationError("RAG PostgreSQL schema inventory is invalid")

    relations: set[tuple[str, str, str]] = set()
    for relation in raw_relations:
        if (
            not isinstance(relation, dict)
            or set(relation) != {"schema", "name", "kind"}
            or not all(isinstance(relation.get(key), str) for key in ("schema", "name", "kind"))
        ):
            raise MigrationError("RAG PostgreSQL schema inventory is invalid")
        relations.add(
            (
                str(relation["schema"]),
                str(relation["name"]),
                str(relation["kind"]),
            )
        )
    if len(relations) != len(raw_relations):
        raise MigrationError("RAG PostgreSQL schema inventory is invalid")

    extensions = set()
    for extension in raw_extensions:
        if not isinstance(extension, str):
            raise MigrationError("RAG PostgreSQL schema inventory is invalid")
        extensions.add(extension)
    if len(extensions) != len(raw_extensions) or not extensions <= ALLOWED_EXTENSIONS:
        raise MigrationError("RAG PostgreSQL schema is not a recognized Viventium RAG schema")

    if not relations:
        schema_class = "fresh"
    elif relations == EXPECTED_LEGACY_RELATIONS and "vector" in extensions:
        schema_class = "legacy-rag"
    else:
        raise MigrationError("RAG PostgreSQL schema is not a recognized Viventium RAG schema")

    schema_sha256 = hashlib.sha256(
        json.dumps(
            schema,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    row_fingerprints = _inspect_row_fingerprints(
        docker,
        container_id=container_id,
        schema_class=schema_class,
    )
    return ClusterIdentity(
        server_version_num=server_version_num,
        system_identifier=system_identifier,
        database_oid=database_oid,
        role_oid=role_oid,
        schema_class=schema_class,
        schema_sha256=schema_sha256,
        row_fingerprints=row_fingerprints,
    )


def _receipt_payload(
    *,
    project_name: str,
    pgdata_path: str,
    pgdata_path_mode: str,
    identity: ClusterIdentity,
    credential_sha256: str,
    verified_before_and_after_role_change: bool,
) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "status": "ready",
        "projectName": project_name,
        "composeService": COMPOSE_SERVICE,
        "pgdataPath": pgdata_path,
        "pgdataPathMode": pgdata_path_mode,
        "credentialSha256": credential_sha256,
        "continuityProof": {
            "verifiedBeforeAndAfterRoleChange": verified_before_and_after_role_change,
            "schemaSha256": identity.schema_sha256,
            "rows": identity.row_fingerprints,
        },
        "cluster": {
            "serverMajor": identity.server_version_num // 10000,
            "systemIdentifier": identity.system_identifier,
            "databaseName": POSTGRES_DATABASE,
            "databaseOid": identity.database_oid,
            "databaseOwner": POSTGRES_ROLE,
            "roleName": POSTGRES_ROLE,
            "roleOid": identity.role_oid,
            "schemaClass": identity.schema_class,
        },
    }


def _validate_existing_state(
    path: Path,
    label: str,
    expected: dict[str, object],
    *,
    allow_schema_promotion: bool = False,
    allow_continuity_refresh: bool = False,
) -> dict[str, object] | None:
    if not path.exists() and not path.is_symlink():
        return None
    actual = _read_json_file(path, label)
    comparable = dict(actual)
    comparable.pop("completedAtUnix", None)
    expected_comparable = dict(expected)
    if allow_continuity_refresh:
        comparable.pop("continuityProof", None)
        expected_comparable.pop("continuityProof", None)
    if comparable != expected_comparable and allow_schema_promotion:
        actual_cluster = comparable.get("cluster")
        expected_cluster = expected_comparable.get("cluster")
        if isinstance(actual_cluster, dict) and isinstance(expected_cluster, dict):
            promoted_cluster = dict(actual_cluster)
            if (
                promoted_cluster.get("schemaClass") == "fresh"
                and expected_cluster.get("schemaClass") == "legacy-rag"
            ):
                promoted_cluster["schemaClass"] = "legacy-rag"
                promoted = {**comparable, "cluster": promoted_cluster}
                if promoted == expected_comparable:
                    return actual
    if comparable != expected_comparable:
        raise MigrationError(f"{label} does not match the selected RAG PostgreSQL cluster")
    return actual


def _stop_if_started_here(
    docker: DockerRunner,
    *,
    compose_prefix: list[str],
    started_here: bool,
) -> None:
    if not started_here:
        return
    docker.run([*compose_prefix, "stop", COMPOSE_SERVICE])


def migrate_rag_postgres(
    *,
    compose_file: Path,
    project_name: str,
    pgdata_path: Path,
    pgdata_path_mode: str,
    state_dir: Path,
    docker: DockerRunner | None = None,
) -> MigrationResult:
    """Adopt or reconcile one recognized Viventium RAG PostgreSQL cluster."""

    docker = docker or SubprocessDocker()
    compose_file = compose_file.absolute()
    pgdata_path = pgdata_path.absolute()
    state_dir = state_dir.absolute()
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}", project_name):
        raise MigrationError("RAG PostgreSQL Compose project name is invalid")
    _require_regular_file(compose_file, "RAG PostgreSQL Compose file")
    expected_pgdata_source = _validate_pgdata_path(pgdata_path, pgdata_path_mode)
    _prepare_state_dir(state_dir)

    receipt_path = state_dir / "migration-receipt.json"
    pending_path = state_dir / "migration-pending.json"
    credential_path, credential = _load_or_create_credential(state_dir, receipt_path)
    credential_sha256 = hashlib.sha256(credential.encode("ascii")).hexdigest()

    compose_prefix = _compose_args(project_name, compose_file)
    initial_container_raw = _run_required(
        docker,
        [*compose_prefix, "ps", "-q", COMPOSE_SERVICE],
        failure_message="RAG PostgreSQL Compose state inspection failed",
    )
    started_here = not bool(initial_container_raw.strip())

    try:
        _run_required(
            docker,
            [*compose_prefix, "up", "-d", COMPOSE_SERVICE],
            env={"POSTGRES_PASSWORD": credential},
            failure_message="RAG PostgreSQL vector database startup failed",
        )
        container_raw = _run_required(
            docker,
            [*compose_prefix, "ps", "-q", COMPOSE_SERVICE],
            failure_message="RAG PostgreSQL Compose container lookup failed",
        )
        container_id = _single_container_id(container_raw)
        _validate_container_provenance(
            docker,
            container_id=container_id,
            project_name=project_name,
            expected_pgdata_source=expected_pgdata_source,
        )
        _wait_for_postgres(docker, container_id)
        identity = _inspect_cluster(docker, container_id)
        pending_receipt = _receipt_payload(
            project_name=project_name,
            pgdata_path=expected_pgdata_source,
            pgdata_path_mode=pgdata_path_mode,
            identity=identity,
            credential_sha256=credential_sha256,
            verified_before_and_after_role_change=False,
        )
        existing_receipt = _validate_existing_state(
            receipt_path,
            "RAG PostgreSQL migration receipt",
            pending_receipt,
            allow_schema_promotion=True,
            allow_continuity_refresh=True,
        )
        _validate_existing_state(
            pending_path,
            "RAG PostgreSQL pending migration journal",
            pending_receipt,
        )
        _atomic_json_write(pending_path, pending_receipt)

        alter_sql = f"ALTER ROLE {POSTGRES_ROLE} WITH LOGIN PASSWORD '{credential}';\n"
        _psql(
            docker,
            container_id=container_id,
            database="postgres",
            sql=alter_sql,
            failure_message="RAG PostgreSQL credential reconciliation failed",
        )

        after_identity = _inspect_cluster(docker, container_id)
        before_cluster = (
            identity.server_version_num,
            identity.system_identifier,
            identity.database_oid,
            identity.role_oid,
            identity.schema_class,
            identity.schema_sha256,
        )
        after_cluster = (
            after_identity.server_version_num,
            after_identity.system_identifier,
            after_identity.database_oid,
            after_identity.role_oid,
            after_identity.schema_class,
            after_identity.schema_sha256,
        )
        if before_cluster != after_cluster:
            raise MigrationError(
                "RAG PostgreSQL cluster or schema continuity changed during role reconciliation"
            )
        if identity.row_fingerprints != after_identity.row_fingerprints:
            raise MigrationError(
                "RAG PostgreSQL row continuity changed during role reconciliation"
            )
        completed_receipt = _receipt_payload(
            project_name=project_name,
            pgdata_path=expected_pgdata_source,
            pgdata_path_mode=pgdata_path_mode,
            identity=after_identity,
            credential_sha256=credential_sha256,
            verified_before_and_after_role_change=True,
        )
        existing_comparable = dict(existing_receipt or {})
        existing_comparable.pop("completedAtUnix", None)
        if existing_receipt is None or existing_comparable != completed_receipt:
            completed_state = {
                **completed_receipt,
                "completedAtUnix": int(time.time()),
            }
            _atomic_json_write(receipt_path, completed_state)
        try:
            pending_path.unlink()
            _fsync_directory(state_dir)
        except FileNotFoundError:
            pass
    except MigrationError:
        _stop_if_started_here(
            docker,
            compose_prefix=compose_prefix,
            started_here=started_here,
        )
        raise

    return MigrationResult(
        status="ready",
        credential_path=credential_path,
        receipt_path=receipt_path,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Reconcile the owner-local Viventium RAG PostgreSQL credential."
    )
    parser.add_argument("--compose-file", required=True, type=Path)
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--pgdata-path", required=True, type=Path)
    parser.add_argument(
        "--pgdata-path-mode",
        required=True,
        choices=("host", "daemon"),
    )
    parser.add_argument("--state-dir", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = migrate_rag_postgres(
            compose_file=args.compose_file,
            project_name=args.project_name,
            pgdata_path=args.pgdata_path,
            pgdata_path_mode=args.pgdata_path_mode,
            state_dir=args.state_dir,
        )
    except MigrationError as error:
        print(f"rag-postgres-migration: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"status": result.status}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

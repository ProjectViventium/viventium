#!/usr/bin/env python3
"""Provision and destroy one exact synthetic GlassHive local-QA fixture."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping

from scripts.viventium import local_qa_runtime_control as _identity_safe_files
from workers_projects_runtime.store import Store


CONTRACT_VERSION = 1
PRIVATE_INPUT_MAX_BYTES = 16 * 1024
PRIVATE_RECEIPT_MAX_BYTES = 16 * 1024
ARTIFACT_MAX_BYTES = 64 * 1024
CASE_IDS = frozenset({"PWK-UC-016", "PWK-UC-017"})
HASH_PATTERN = re.compile(r"^sha256:[a-f0-9]{64}$")
NAMESPACE_PATTERN = re.compile(r"^[a-f0-9]{32}$")
ID_PATTERN = re.compile(r"^[A-Za-z0-9_:-]{8,160}$")
PROVISION_FIELDS = frozenset(
    {
        "artifactId",
        "caseId",
        "contractVersion",
        "expiresAt",
        "idempotencyKey",
        "namespace",
        "originRef",
        "ownerId",
        "requestDigest",
        "scopeKind",
    }
)
DESTROY_FIELDS = PROVISION_FIELDS | frozenset(
    {"projectId", "runId", "workId", "workerId"}
)
OWNER_ATTESTATION_FIELD = "ownerAttestation"
FIXTURE_SECRET_ENV = "VIVENTIUM_GLASSHIVE_QA_FIXTURE_SECRET"


class FixtureError(RuntimeError):
    """Reject unsafe fixture work without exposing private input."""


class ArtifactCleanupError(FixtureError):
    """Report the recoverable outcome of an identity-safe artifact cleanup."""

    def __init__(self, outcome: str) -> None:
        super().__init__("operation_failed")
        self.outcome = outcome


class PrivateArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        raise FixtureError("operation_failed")


class DuplicateJsonKeyError(ValueError):
    pass


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJsonKeyError("duplicate JSON key")
        result[key] = value
    return result


def _reject_duplicate_options(argv: Iterable[str]) -> None:
    seen: set[str] = set()
    for argument in argv:
        if not argument.startswith("--"):
            continue
        option = argument.split("=", 1)[0]
        if option in seen:
            raise FixtureError("operation_failed")
        seen.add(option)


def _fd_identity(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_size,
        metadata.st_mode,
        metadata.st_uid,
        metadata.st_nlink,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _validate_fd(descriptor: int, *, writable: bool = False) -> os.stat_result:
    if isinstance(descriptor, bool) or descriptor < 3:
        raise FixtureError("operation_failed")
    try:
        os.set_blocking(descriptor, False)
        metadata = os.fstat(descriptor)
    except OSError as exc:
        raise FixtureError("operation_failed") from exc
    if (
        not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) != 0o600
        or metadata.st_nlink != 1
    ):
        raise FixtureError("operation_failed")
    if not writable and metadata.st_size > PRIVATE_INPUT_MAX_BYTES:
        raise FixtureError("operation_failed")
    return metadata


def _read_request(descriptor: int) -> dict[str, object]:
    before = _validate_fd(descriptor)
    if before.st_size < 2:
        raise FixtureError("operation_failed")
    try:
        os.lseek(descriptor, 0, os.SEEK_SET)
        first_raw = os.read(descriptor, PRIVATE_INPUT_MAX_BYTES + 1)
        middle = os.fstat(descriptor)
        os.lseek(descriptor, 0, os.SEEK_SET)
        second_raw = os.read(descriptor, PRIVATE_INPUT_MAX_BYTES + 1)
        after = os.fstat(descriptor)
        first_digest = hashlib.sha256(first_raw).digest()
        second_digest = hashlib.sha256(second_raw).digest()
        if (
            len(first_raw) > PRIVATE_INPUT_MAX_BYTES
            or len(second_raw) > PRIVATE_INPUT_MAX_BYTES
            or len(first_raw) != before.st_size
            or len(second_raw) != after.st_size
            or _fd_identity(before) != _fd_identity(middle)
            or _fd_identity(middle) != _fd_identity(after)
            or first_digest != second_digest
            or first_raw != second_raw
        ):
            raise FixtureError("operation_failed")
        payload = json.loads(
            second_raw.decode("utf-8"), object_pairs_hook=_unique_object
        )
    except (OSError, UnicodeError, json.JSONDecodeError, DuplicateJsonKeyError) as exc:
        raise FixtureError("operation_failed") from exc
    if not isinstance(payload, dict):
        raise FixtureError("operation_failed")
    return payload


def _write_receipt(descriptor: int, payload: Mapping[str, object]) -> None:
    _validate_fd(descriptor, writable=True)
    raw = (json.dumps(dict(payload), sort_keys=True, separators=(",", ":")) + "\n").encode()
    if len(raw) > PRIVATE_RECEIPT_MAX_BYTES:
        raise FixtureError("operation_failed")
    try:
        os.lseek(descriptor, 0, os.SEEK_SET)
        os.ftruncate(descriptor, 0)
        written = os.write(descriptor, raw)
        os.fsync(descriptor)
    except OSError as exc:
        raise FixtureError("operation_failed") from exc
    if written != len(raw):
        raise FixtureError("operation_failed")


def _clean(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise FixtureError("operation_failed")
    result = value.strip()
    if not ID_PATTERN.fullmatch(result):
        raise FixtureError("operation_failed")
    return result


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds")


def _parse_time(value: object) -> datetime:
    if not isinstance(value, str):
        raise FixtureError("operation_failed")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise FixtureError("operation_failed") from exc
    if parsed.tzinfo is None or value != _iso(parsed):
        raise FixtureError("operation_failed")
    return parsed.astimezone(timezone.utc)


def _validate_common(
    request: Mapping[str, object], *, fields: frozenset[str]
) -> dict[str, str]:
    supplied = set(request)
    selected_owner = supplied == set(fields) | {OWNER_ATTESTATION_FIELD}
    if (
        (
            supplied != set(fields)
            and supplied != set(fields) | {OWNER_ATTESTATION_FIELD}
        )
        or request.get("contractVersion") != CONTRACT_VERSION
    ):
        raise FixtureError("operation_failed")
    case_id = str(request.get("caseId") or "")
    namespace = str(request.get("namespace") or "")
    owner_id = _clean(request.get("ownerId"), "ownerId")
    expires_at = request.get("expiresAt")
    _parse_time(expires_at)
    artifact_id = str(request.get("artifactId") or "")
    request_digest = str(request.get("requestDigest") or "")
    legacy_owner = owner_id == f"qa_owner_{namespace}"
    if (
        case_id not in CASE_IDS
        or not NAMESPACE_PATTERN.fullmatch(namespace)
        or not HASH_PATTERN.fullmatch(request_digest)
        or not artifact_id.startswith("artifact_sha256:")
        or len(artifact_id) != len("artifact_sha256:") + 64
        or any(character not in "0123456789abcdef" for character in artifact_id[16:])
    ):
        raise FixtureError("operation_failed")
    if selected_owner:
        secret = str(os.environ.get(FIXTURE_SECRET_ENV, "") or "")
        unsigned = {
            key: request[key]
            for key in sorted(supplied - {OWNER_ATTESTATION_FIELD})
        }
        canonical = json.dumps(unsigned, sort_keys=True, separators=(",", ":"))
        expected = "sha256:" + hmac.new(
            secret.encode("utf-8"),
            ("glasshive-fixture-owner-v1\0" + canonical).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if (
            request.get("scopeKind") != "selected_synthetic_account_qa"
            or legacy_owner
            or not secret
            or not hmac.compare_digest(
                str(request.get(OWNER_ATTESTATION_FIELD) or ""), expected
            )
        ):
            raise FixtureError("operation_failed")
    elif request.get("scopeKind") != "synthetic_local_qa" or not legacy_owner:
        raise FixtureError("operation_failed")
    return {
        "artifactId": artifact_id,
        "caseId": case_id,
        "expiresAt": expires_at,
        "idempotencyKey": _clean(request.get("idempotencyKey"), "idempotencyKey"),
        "namespace": namespace,
        "originRef": _clean(request.get("originRef"), "originRef"),
        "ownerId": owner_id,
        "requestDigest": request_digest,
    }


def _db_path() -> Path:
    raw = str(os.environ.get("WPR_DB_PATH", "") or "").strip()
    if not raw:
        raise FixtureError("operation_failed")
    try:
        exact = Path(raw).expanduser().resolve(strict=True)
        metadata = exact.stat()
    except (OSError, RuntimeError) as exc:
        raise FixtureError("operation_failed") from exc
    if (
        not exact.is_absolute()
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) != 0o600
        or metadata.st_nlink != 1
    ):
        raise FixtureError("operation_failed")
    return exact


def _fixture_ref(namespace: str) -> str:
    return "pwk_fixture_sha256:" + hashlib.sha256(namespace.encode()).hexdigest()


def _artifact_path(db_path: Path, namespace: str) -> Path:
    return db_path.parent / "local-qa-fixtures" / namespace / "artifact.txt"


def _prepare_artifact(path: Path, namespace: str) -> int:
    path.parent.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.parent.mkdir(mode=0o700, exist_ok=True)
    os.chmod(path.parent.parent, 0o700)
    os.chmod(path.parent, 0o700)
    if path.exists() or path.is_symlink():
        metadata = path.lstat()
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or stat.S_IMODE(metadata.st_mode) != 0o600
            or metadata.st_nlink != 1
        ):
            raise FixtureError("operation_failed")
        return metadata.st_size
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        payload = f"Synthetic Parallel Work fixture {namespace}\n".encode()
        if os.write(descriptor, payload) != len(payload):
            raise FixtureError("operation_failed")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return len(payload)


def _cleanup_artifact(path: Path) -> str:
    try:
        snapshot = _identity_safe_files._read_private_file_snapshot(
            path,
            label="synthetic fixture artifact",
            max_bytes=ARTIFACT_MAX_BYTES,
        )
    except ValueError as exc:
        if path.exists() or path.is_symlink():
            raise ArtifactCleanupError("artifact_invalid") from exc
        return "absent"
    try:
        return _identity_safe_files._unlink_private_file_snapshot(
            path,
            snapshot,
            label="synthetic fixture artifact",
            max_bytes=ARTIFACT_MAX_BYTES,
        )
    except _identity_safe_files.PrivateFileRemovalError as exc:
        raise ArtifactCleanupError(exc.outcome) from exc
    except (OSError, RuntimeError, ValueError) as exc:
        raise ArtifactCleanupError("artifact_invalid") from exc


def provision(request: Mapping[str, object]) -> tuple[dict[str, object], dict[str, object]]:
    values = _validate_common(request, fields=PROVISION_FIELDS)
    db_path = _db_path()
    store = Store(db_path)
    record = store.reserve_delegation(
        tenant_id="local",
        owner_id=values["ownerId"],
        idempotency_key=values["idempotencyKey"],
        request_digest=values["requestDigest"],
        origin_ref=values["originRef"],
        title="Synthetic Parallel Work local-QA fixture",
        goal="Exercise one deterministic installed local-QA boundary.",
        instruction="Synthetic local-QA fixture. Do not perform external work.",
        origin_surface="workbench",
        worker_name="Synthetic local-QA worker",
        worker_role="deterministic fixture",
        profile="codex-cli",
        backend="local",
        runtime="local",
        model="synthetic",
        execution_mode="docker",
    )
    work_id = str(record.get("work_ref") or "")
    project_id = str(record.get("project_id") or "")
    worker_id = str(record.get("worker_id") or "")
    run_id = str(record.get("current_run_id") or record.get("initial_run_id") or "")
    if not all(ID_PATTERN.fullmatch(value) for value in (work_id, project_id, worker_id, run_id)):
        raise FixtureError("operation_failed")
    current = store.get_delegation(
        work_id,
        tenant_id="local",
        owner_id=values["ownerId"],
    )
    if (
        not current
        or str(current.get("project_id") or "") != project_id
        or str(current.get("worker_id") or "") != worker_id
        or str(current.get("current_run_id") or "") != run_id
    ):
        raise FixtureError("operation_failed")
    if store.update_run(run_id, state="paused") is None:
        raise FixtureError("operation_failed")
    artifact_path = _artifact_path(db_path, values["namespace"])
    size_bytes = _prepare_artifact(artifact_path, values["namespace"])
    if store.update_worker(worker_id, workspace_dir=str(artifact_path.parent)) is None:
        raise FixtureError("operation_failed")
    fingerprint = "sha256:" + values["artifactId"].removeprefix("artifact_sha256:")
    store.record_artifact_trace(
        run_id=run_id,
        tenant_id="local",
        owner_id=values["ownerId"],
        artifact_refs={
            "available": True,
            "refs": [
                {
                    "artifactRef": values["artifactId"],
                    "fingerprint": fingerprint,
                    "kind": "text",
                    "state": "ready",
                    "sizeBytes": size_bytes,
                }
            ],
            "overflowCount": 0,
        },
    )
    private = {
        "artifactId": values["artifactId"],
        "caseId": values["caseId"],
        "namespace": values["namespace"],
        "ownerId": values["ownerId"],
        "projectId": project_id,
        "runId": run_id,
        "workId": work_id,
        "workerId": worker_id,
    }
    public = {
        "contractVersion": CONTRACT_VERSION,
        "fixtureRef": _fixture_ref(values["namespace"]),
        "operation": "provision",
        "status": "ready",
    }
    return private, public


def _exact_one(connection, query: str, parameters: tuple[str, ...]) -> bool:
    rows = connection.execute(query, parameters).fetchall()
    if len(rows) > 1:
        raise FixtureError("operation_failed")
    return len(rows) == 1


def _table_columns(connection, table: str) -> frozenset[str]:
    return frozenset(str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})"))


def _delete_where(
    connection,
    table: str,
    where: str,
    parameters: tuple[object, ...],
    *,
    required: frozenset[str],
) -> int:
    if not required.issubset(_table_columns(connection, table)):
        return 0
    return connection.execute(
        f"DELETE FROM {table} WHERE {where}", parameters
    ).rowcount


def _reject_cross_scope(
    connection,
    table: str,
    anchor: str,
    anchor_parameters: tuple[object, ...],
    exact: str,
    exact_parameters: tuple[object, ...],
    *,
    required: frozenset[str],
) -> None:
    if not required.issubset(_table_columns(connection, table)):
        return
    row = connection.execute(
        f"SELECT 1 FROM {table} WHERE ({anchor}) AND NOT ({exact}) LIMIT 1",
        (*anchor_parameters, *exact_parameters),
    ).fetchone()
    if row is not None:
        raise FixtureError("operation_failed")


def _drop_delete_guards(connection, table: str) -> list[str]:
    rows = connection.execute(
        "SELECT name, sql FROM sqlite_master WHERE type = 'trigger' AND tbl_name = ?",
        (table,),
    ).fetchall()
    definitions = [str(row[1]) for row in rows if row[1] and "append_only_delete" in str(row[0])]
    for row in rows:
        if row[1] and "append_only_delete" in str(row[0]):
            connection.execute(f'DROP TRIGGER "{str(row[0]).replace(chr(34), chr(34) * 2)}"')
    return definitions


def _restore_delete_guards(connection, definitions: Iterable[str]) -> None:
    for definition in definitions:
        connection.execute(definition)


def _reject_unknown_foreign_key_dependents(
    connection,
    *,
    known_tables: frozenset[str],
    project_id: str,
    worker_id: str,
    run_id: str,
    work_id: str,
) -> None:
    identities = {
        ("projects", "project_id"): project_id,
        ("workers", "worker_id"): worker_id,
        ("runs", "run_id"): run_id,
        ("delegations", "work_ref"): work_id,
    }
    tables = [
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    ]
    for table in tables:
        if table in known_tables:
            continue
        for foreign_key in connection.execute(f"PRAGMA foreign_key_list({table})"):
            target = (str(foreign_key[2]), str(foreign_key[4]))
            value = identities.get(target)
            if value is None:
                continue
            column = str(foreign_key[3]).replace('"', '""')
            if connection.execute(
                f'SELECT 1 FROM "{table.replace(chr(34), chr(34) * 2)}" '
                f'WHERE "{column}" = ? LIMIT 1',
                (value,),
            ).fetchone() is not None:
                raise FixtureError("operation_failed")


def destroy(request: Mapping[str, object]) -> dict[str, object]:
    values = _validate_common(request, fields=DESTROY_FIELDS)
    project_id = _clean(request.get("projectId"), "projectId")
    worker_id = _clean(request.get("workerId"), "workerId")
    work_id = _clean(request.get("workId"), "workId")
    run_id = _clean(request.get("runId"), "runId")
    db_path = _db_path()
    store = Store(db_path)
    with store._connect() as connection:  # Installed Store owns schema and connection policy.
        connection.execute("BEGIN IMMEDIATE")
        found = (
            _exact_one(
                connection,
                "SELECT 1 FROM projects WHERE project_id = ? AND owner_id = ? AND tenant_id = 'local'",
                (project_id, values["ownerId"]),
            ),
            _exact_one(
                connection,
                "SELECT 1 FROM workers WHERE worker_id = ? AND project_id = ? AND owner_id = ?",
                (worker_id, project_id, values["ownerId"]),
            ),
            _exact_one(
                connection,
                "SELECT 1 FROM runs WHERE run_id = ? AND worker_id = ? AND project_id = ?",
                (run_id, worker_id, project_id),
            ),
            _exact_one(
                connection,
                "SELECT 1 FROM delegations WHERE work_ref = ? AND owner_id = ? AND project_id = ? AND worker_id = ? AND current_run_id = ?",
                (work_id, values["ownerId"], project_id, worker_id, run_id),
            ),
        )
        if any(found) and not all(found):
            connection.execute("ROLLBACK")
            raise FixtureError("operation_failed")
        known_tables = frozenset(
            {
                "projects", "workers", "runs", "delegations", "work_trace_events",
                "events", "run_attempts", "capacity_attempts", "host_run_leases",
                "provider_liveness_events", "provider_route_health_events",
                "provider_route_health", "callback_outbox", "callback_trace_events",
                "terminal_callback_reconciliations", "terminal_callback_results",
                "terminal_callback_result_attempts", "active_work_action_uses",
                "run_action_uses", "lifecycle_operation_effects",
                "capability_grant_revocations", "scheduled_runs", "provider_sessions",
                "provider_session_visible_admissions", "provider_requests",
                "provider_activity", "provider_stop_tombstones",
            }
        )
        _reject_unknown_foreign_key_dependents(
            connection,
            known_tables=known_tables,
            project_id=project_id,
            worker_id=worker_id,
            run_id=run_id,
            work_id=work_id,
        )
        _reject_cross_scope(
            connection, "host_run_leases", "run_id = ?", (run_id,),
            "run_id = ? AND worker_id = ? AND owner_id = ?",
            (run_id, worker_id, values["ownerId"]),
            required=frozenset({"run_id", "worker_id", "owner_id"}),
        )
        _reject_cross_scope(
            connection, "callback_outbox", "run_id = ?", (run_id,),
            "run_id = ? AND worker_id = ? AND project_id = ?",
            (run_id, worker_id, project_id),
            required=frozenset({"run_id", "worker_id", "project_id"}),
        )
        _reject_cross_scope(
            connection, "active_work_action_uses", "work_ref = ?", (work_id,),
            "work_ref = ? AND owner_id = ?", (work_id, values["ownerId"]),
            required=frozenset({"work_ref", "owner_id"}),
        )
        trace_guards = _drop_delete_guards(connection, "work_trace_events")
        callback_trace_guards = _drop_delete_guards(connection, "callback_trace_events")
        session_ids: list[str] = []
        if {"session_id", "project_id", "worker_id", "owner_id"}.issubset(
            _table_columns(connection, "provider_sessions")
        ):
            _reject_cross_scope(
                connection, "provider_sessions",
                "project_id = ? OR worker_id = ?", (project_id, worker_id),
                "project_id = ? AND worker_id = ? AND owner_id = ?",
                (project_id, worker_id, values["ownerId"]),
                required=frozenset({"session_id", "project_id", "worker_id", "owner_id"}),
            )
            session_ids = [
                str(row[0]) for row in connection.execute(
                    "SELECT session_id FROM provider_sessions WHERE project_id = ? AND worker_id = ? AND owner_id = ?",
                    (project_id, worker_id, values["ownerId"]),
                )
            ]
        request_ids = []
        if {"request_id", "run_id", "owner_id"}.issubset(
            _table_columns(connection, "provider_requests")
        ):
            _reject_cross_scope(
                connection, "provider_requests", "run_id = ?", (run_id,),
                "run_id = ? AND owner_id = ?", (run_id, values["ownerId"]),
                required=frozenset({"run_id", "owner_id"}),
            )
            request_ids = [
                str(row[0]) for row in connection.execute(
                    "SELECT request_id FROM provider_requests WHERE run_id = ? AND owner_id = ?",
                    (run_id, values["ownerId"]),
                )
            ]
            if session_ids:
                placeholders = ",".join("?" for _ in session_ids)
                cross_scope = connection.execute(
                    f"SELECT 1 FROM provider_requests WHERE session_id IN ({placeholders}) "
                    "AND (owner_id != ? OR COALESCE(run_id, '') NOT IN ('', ?)) LIMIT 1",
                    (*session_ids, values["ownerId"], run_id),
                ).fetchone()
                if cross_scope is not None:
                    raise FixtureError("operation_failed")
                request_ids.extend(
                    str(row[0]) for row in connection.execute(
                        f"SELECT request_id FROM provider_requests WHERE session_id IN ({placeholders})",
                        session_ids,
                    )
                )
                request_ids = list(dict.fromkeys(request_ids))
        removed: dict[str, int] = {}
        if request_ids and {"request_id"}.issubset(_table_columns(connection, "provider_activity")):
            placeholders = ",".join("?" for _ in request_ids)
            removed["providerActivity"] = connection.execute(
                f"DELETE FROM provider_activity WHERE request_id IN ({placeholders})", request_ids
            ).rowcount
        removed["providerLivenessEvents"] = _delete_where(
            connection, "provider_liveness_events", "run_id = ?", (run_id,),
            required=frozenset({"run_id"}),
        )
        removed["callbackTraceEvents"] = _delete_where(
            connection, "callback_trace_events", "run_id = ?", (run_id,),
            required=frozenset({"run_id"}),
        )
        for table, key in (
            ("terminal_callback_result_attempts", "terminalCallbackResultAttempts"),
            ("terminal_callback_results", "terminalCallbackResults"),
            ("terminal_callback_reconciliations", "terminalCallbackReconciliations"),
            ("provider_route_health_events", "providerRouteHealthEvents"),
        ):
            removed[key] = _delete_where(
                connection, table, "run_id = ?", (run_id,), required=frozenset({"run_id"})
            )
        removed["providerRequests"] = 0
        if request_ids and {"request_id"}.issubset(_table_columns(connection, "provider_requests")):
            placeholders = ",".join("?" for _ in request_ids)
            removed["providerRequests"] = connection.execute(
                f"DELETE FROM provider_requests WHERE request_id IN ({placeholders})",
                request_ids,
            ).rowcount
        removed["providerSessionAdmissions"] = 0
        if session_ids and {"session_id"}.issubset(
            _table_columns(connection, "provider_session_visible_admissions")
        ):
            placeholders = ",".join("?" for _ in session_ids)
            removed["providerSessionAdmissions"] = connection.execute(
                f"DELETE FROM provider_session_visible_admissions WHERE session_id IN ({placeholders})",
                session_ids,
            ).rowcount
        removed["providerSessions"] = 0
        if session_ids:
            placeholders = ",".join("?" for _ in session_ids)
            removed["providerSessions"] = connection.execute(
                f"DELETE FROM provider_sessions WHERE session_id IN ({placeholders})",
                session_ids,
            ).rowcount
        removed["providerRouteHealth"] = _delete_where(
            connection, "provider_route_health", "owner_id = ? AND last_run_id = ?",
            (values["ownerId"], run_id), required=frozenset({"owner_id", "last_run_id"}),
        )
        removed["providerStopTombstones"] = _delete_where(
            connection, "provider_stop_tombstones",
            "owner_id = ? AND base_idempotency_key = ?",
            (values["ownerId"], values["idempotencyKey"]),
            required=frozenset({"owner_id", "base_idempotency_key"}),
        )
        removed["callbacks"] = _delete_where(
            connection, "callback_outbox",
            "project_id = ? AND worker_id = ? AND (run_id = ? OR run_id IS NULL)",
            (project_id, worker_id, run_id),
            required=frozenset({"project_id", "worker_id", "run_id"}),
        )
        removed["activeWorkActions"] = _delete_where(
            connection, "active_work_action_uses", "work_ref = ? AND owner_id = ?",
            (work_id, values["ownerId"]), required=frozenset({"work_ref", "owner_id"}),
        )
        removed["runActions"] = _delete_where(
            connection, "run_action_uses", "owner_id = ? AND worker_id = ? AND project_id = ? AND (source_run_id = ? OR new_run_id = ?)",
            (values["ownerId"], worker_id, project_id, run_id, run_id),
            required=frozenset({"owner_id", "worker_id", "project_id", "source_run_id", "new_run_id"}),
        )
        for table, key, where, parameters, required in (
            ("capability_grant_revocations", "grantRevocations", "worker_id = ? AND run_id = ? AND work_ref = ?", (worker_id, run_id, work_id), frozenset({"worker_id", "run_id", "work_ref"})),
            ("lifecycle_operation_effects", "lifecycleEffects", "worker_id = ? AND (run_id = ? OR run_id = '')", (worker_id, run_id), frozenset({"worker_id", "run_id"})),
            ("scheduled_runs", "scheduledRuns", "worker_id = ? AND project_id = ?", (worker_id, project_id), frozenset({"worker_id", "project_id"})),
            ("host_run_leases", "hostRunLeases", "run_id = ? AND worker_id = ? AND owner_id = ?", (run_id, worker_id, values["ownerId"]), frozenset({"run_id", "worker_id", "owner_id"})),
            ("capacity_attempts", "capacityAttempts", "run_id = ?", (run_id,), frozenset({"run_id"})),
            ("run_attempts", "runAttempts", "run_id = ?", (run_id,), frozenset({"run_id"})),
        ):
            removed[key] = _delete_where(
                connection, table, where, parameters, required=required
            )
        removed_trace = connection.execute(
            "DELETE FROM work_trace_events WHERE run_id = ? AND work_ref = ? AND owner_id = ?",
            (run_id, work_id, values["ownerId"]),
        ).rowcount
        removed_events = connection.execute(
            "DELETE FROM events WHERE project_id = ? AND worker_id = ? AND (run_id = ? OR run_id IS NULL)",
            (project_id, worker_id, run_id),
        ).rowcount
        removed_delegations = connection.execute(
            "DELETE FROM delegations WHERE work_ref = ? AND owner_id = ?",
            (work_id, values["ownerId"]),
        ).rowcount
        removed_runs = connection.execute(
            "DELETE FROM runs WHERE run_id = ? AND worker_id = ? AND project_id = ?",
            (run_id, worker_id, project_id),
        ).rowcount
        removed_workers = connection.execute(
            "DELETE FROM workers WHERE worker_id = ? AND project_id = ? AND owner_id = ?",
            (worker_id, project_id, values["ownerId"]),
        ).rowcount
        removed_projects = connection.execute(
            "DELETE FROM projects WHERE project_id = ? AND owner_id = ?",
            (project_id, values["ownerId"]),
        ).rowcount
        _restore_delete_guards(connection, callback_trace_guards)
        _restore_delete_guards(connection, trace_guards)
        connection.execute("COMMIT")
    artifact = _artifact_path(db_path, values["namespace"])
    _cleanup_artifact(artifact)
    for directory in (artifact.parent, artifact.parent.parent):
        try:
            directory.rmdir()
        except OSError:
            pass
    return {
        "contractVersion": CONTRACT_VERSION,
        "fixtureRef": _fixture_ref(values["namespace"]),
        "operation": "destroy",
        "removed": {
            **removed,
            "delegations": removed_delegations,
            "events": removed_events,
            "projects": removed_projects,
            "runs": removed_runs,
            "traceEvents": removed_trace,
            "workers": removed_workers,
        },
        "status": "clean",
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = PrivateArgumentParser(allow_abbrev=False)
    parser.add_argument("operation", choices=("provision", "destroy"))
    parser.add_argument("--input-fd", type=int, required=True)
    parser.add_argument("--receipt-fd", type=int)
    values = list(argv) if argv is not None else sys.argv[1:]
    try:
        _reject_duplicate_options(values)
        args = parser.parse_args(values)
        request = _read_request(args.input_fd)
        if args.operation == "provision":
            if args.receipt_fd is None:
                raise FixtureError("operation_failed")
            private, public = provision(request)
            _write_receipt(args.receipt_fd, private)
        else:
            if args.receipt_fd is not None:
                raise FixtureError("operation_failed")
            public = destroy(request)
    except Exception:
        sys.stderr.write('{"error":"fixture_operation_failed"}\n')
        return 2
    sys.stdout.write(json.dumps(public, sort_keys=True, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import hashlib
import hmac
import importlib.util
import json
import os
import secrets
import shlex
import sqlite3
import sys
import types
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from qa_control_test_support import write_artifact_identity


ROOT = Path(__file__).resolve().parents[2]
PARENT = ROOT / "scripts" / "viventium" / "glasshive_qa_parent_control.py"
FIXTURE = ROOT / "scripts" / "viventium" / "glasshive_qa_fixture.py"
CLI = ROOT / "bin" / "viventium"
NESTED = (
    ROOT
    / "viventium_v0_4"
    / "GlassHive"
    / "runtime_phase1"
    / "src"
    / "workers_projects_runtime"
    / "local_qa_control.py"
)

CASE_BOUNDARIES = {
    "PWK-UC-016": (
        "provider_auth_missing",
        "provider_quota_cooldown_fallback",
        "provider_unavailable",
        "provider_internal_retry_threshold",
        "declared_long_fresh_then_stale",
        "maximum_capacity_overflow",
        "measured_memory_4_3_gib_vs_5_gib",
        "last_reservation_competition",
        "low_disk",
    ),
    "PWK-UC-017": (
        "callback_transport_interruption",
        "claimed_queue_stall",
        "admitted_queue_stall",
        "status_refresh_timeout_race",
        "expired_sender_lease_race",
        "duplicate_callback_replay",
        "artifact_link_expired",
        "artifact_unavailable_restart_recovery",
    ),
}


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_fixture(name: str, store_type: type[object] | None = None):
    class UnusedStore:
        def __init__(self, _path: str) -> None:
            raise AssertionError("fixture Store access was not expected")

    package_name = "workers_projects_runtime"
    store_name = f"{package_name}.store"
    package = types.ModuleType(package_name)
    package.__path__ = []
    store_module = types.ModuleType(store_name)
    store_module.Store = store_type or UnusedStore
    missing = object()
    previous_package = sys.modules.get(package_name, missing)
    previous_store = sys.modules.get(store_name, missing)
    sys.modules[package_name] = package
    sys.modules[store_name] = store_module
    try:
        return load(FIXTURE, name)
    finally:
        if previous_package is missing:
            sys.modules.pop(package_name, None)
        else:
            sys.modules[package_name] = previous_package
        if previous_store is missing:
            sys.modules.pop(store_name, None)
        else:
            sys.modules[store_name] = previous_store


def fixture_request(expires_at: object) -> dict[str, object]:
    namespace = "a" * 32
    return {
        "artifactId": "artifact_sha256:" + "b" * 64,
        "caseId": "PWK-UC-016",
        "contractVersion": 1,
        "expiresAt": expires_at,
        "idempotencyKey": "qa_idem_" + "c" * 64,
        "namespace": namespace,
        "originRef": "qa_origin_" + namespace,
        "ownerId": "qa_owner_" + namespace,
        "requestDigest": "sha256:" + "d" * 64,
        "scopeKind": "synthetic_local_qa",
    }


def private_state(case_id: str) -> tuple[dict[str, object], dict[str, object]]:
    suffix = secrets.token_hex(16)
    state: dict[str, object] = {
        "artifactId": f"artifact_sha256:{secrets.token_hex(32)}",
        "caseId": case_id,
        "ownerId": f"qa_owner_{suffix}",
        "runId": f"qa_run_{suffix}",
        "workId": f"qa_work_{suffix}",
    }
    session: dict[str, object] = {
        "artifactIdentityDigest": "sha256:" + "a" * 64,
        "caseId": case_id,
        "caseToken": secrets.token_urlsafe(32),
        "componentArtifactDigest": "sha256:" + "b" * 64,
        "mode": case_id.lower().replace("-", "_"),
        "sessionRef": f"qa_session_{suffix}",
    }
    return state, session


def signed_owner_scope(
    parent: object,
    session: dict[str, object],
    *,
    secret: str,
    owner_id: str = "synthetic-owner-id",
    email: str = "worker@example.com",
    role: str = "USER",
    issued_at_ms: int = 1787500800000,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "caseId": session["caseId"],
        "contractVersion": 1,
        "expiresAtMs": issued_at_ms + 30_000,
        "issuedAtMs": issued_at_ms,
        "nonce": "a" * 32,
        "ownerEmail": email,
        "ownerId": owner_id,
        "ownerRole": role,
        "sessionRef": session["sessionRef"],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    payload["attestation"] = "sha256:" + hmac.new(
        secret.encode(),
        ("glasshive-selected-owner-scope-v1\0" + canonical).encode(),
        hashlib.sha256,
    ).hexdigest()
    return payload


def seed_control_fixture(database: Path, state: dict[str, object]) -> None:
    owner_id = str(state["ownerId"])
    work_id = str(state["workId"])
    run_id = str(state["runId"])
    artifact_id = str(state["artifactId"])
    identity = hashlib.sha256(f"{owner_id}\0{work_id}".encode()).hexdigest()
    project_id = "qa_project_" + identity[:32]
    worker_id = "qa_worker_" + identity[32:]
    payload = json.dumps(
        {
            "artifactRefs": {
                "available": True,
                "overflowCount": 0,
                "refs": [
                    {
                        "artifactRef": artifact_id,
                        "fingerprint": "sha256:" + artifact_id.removeprefix("artifact_sha256:"),
                        "kind": "text",
                        "sizeBytes": 1,
                        "state": "ready",
                    }
                ],
            },
            "observedAt": "2026-08-23T16:00:00.000+00:00",
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE projects (
                project_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, owner_id TEXT NOT NULL
            );
            CREATE TABLE workers (
                worker_id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
                tenant_id TEXT NOT NULL, owner_id TEXT NOT NULL,
                role TEXT NOT NULL, model TEXT NOT NULL
            );
            CREATE TABLE runs (
                run_id TEXT PRIMARY KEY, worker_id TEXT NOT NULL,
                project_id TEXT NOT NULL, tenant_id TEXT NOT NULL,
                instruction TEXT NOT NULL
            );
            CREATE TABLE delegations (
                work_ref TEXT PRIMARY KEY, tenant_id TEXT NOT NULL,
                owner_id TEXT NOT NULL, idempotency_key TEXT NOT NULL,
                origin_ref TEXT NOT NULL, title TEXT NOT NULL,
                origin_surface TEXT NOT NULL, project_id TEXT NOT NULL,
                worker_id TEXT NOT NULL, initial_run_id TEXT NOT NULL,
                current_run_id TEXT NOT NULL
            );
            CREATE TABLE work_trace_events (
                run_id TEXT NOT NULL, work_ref TEXT NOT NULL,
                tenant_id TEXT NOT NULL, owner_id TEXT NOT NULL,
                sequence INTEGER NOT NULL, event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            """
        )
        connection.execute(
            "INSERT INTO projects VALUES (?, 'local', ?)", (project_id, owner_id)
        )
        connection.execute(
            "INSERT INTO workers VALUES (?, ?, 'local', ?, 'deterministic fixture', 'synthetic')",
            (worker_id, project_id, owner_id),
        )
        connection.execute(
            "INSERT INTO runs VALUES (?, ?, ?, 'local', ?)",
            (
                run_id,
                worker_id,
                project_id,
                "Synthetic local-QA fixture. Do not perform external work.",
            ),
        )
        connection.execute(
            "INSERT INTO delegations VALUES (?, 'local', ?, ?, ?, ?, 'workbench', ?, ?, ?, ?)",
            (
                work_id,
                owner_id,
                "qa_idem_" + identity,
                "qa_origin_" + identity[:32],
                "Synthetic Parallel Work local-QA fixture",
                project_id,
                worker_id,
                run_id,
                run_id,
            ),
        )
        connection.execute(
            "INSERT INTO work_trace_events VALUES (?, ?, 'local', ?, 1, 'artifact.observed', ?)",
            (run_id, work_id, owner_id, payload),
        )
    database.chmod(0o600)


def test_root_parent_catalog_matches_the_nested_installed_contract() -> None:
    parent = load(PARENT, "glasshive_qa_parent_catalog")
    nested = load(NESTED, "glasshive_nested_local_qa_catalog")

    assert parent.CASE_BOUNDARIES == CASE_BOUNDARIES
    assert parent.CASE_BOUNDARIES == nested.SUPPORTED_FAULTS
    assert parent.CASE_MODES == nested.CASE_MODES
    assert parent.RUN_SCOPED_BOUNDARIES == nested.RUN_SCOPED_FAULTS
    assert parent.RUN_SCOPED_BOUNDARIES == frozenset(
        boundary
        for boundaries in CASE_BOUNDARIES.values()
        for boundary in boundaries
    )
    assert parent.ARTIFACT_SCOPED_BOUNDARIES == nested.ARTIFACT_SCOPED_FAULTS


@pytest.mark.parametrize(
    ("mutation", "value"),
    [
        ("ownerId", "different-synthetic-owner"),
        ("ownerEmail", "owner@example.com"),
        ("ownerRole", "ADMIN"),
        ("sessionRef", "qa_session_different"),
        ("expiresAtMs", 1787500799999),
    ],
)
def test_selected_fixture_owner_scope_is_signed_non_admin_synthetic_and_fresh(
    mutation: str, value: object
) -> None:
    parent = load(PARENT, f"glasshive_parent_selected_owner_{mutation}")
    _state, session = private_state("PWK-UC-016")
    session["expiresAt"] = "2026-08-23T16:01:00.000+00:00"
    secret = "synthetic-owner-scope-signing-secret"
    valid = signed_owner_scope(parent, session, secret=secret)

    checked = parent._verify_selected_owner_scope(
        valid,
        session=session,
        signing_secret=secret,
        now=datetime(2026, 8, 23, 16, 0, tzinfo=timezone.utc),
    )
    assert checked == {
        "ownerEmail": "worker@example.com",
        "ownerId": "synthetic-owner-id",
        "ownerRole": "USER",
    }

    forged = dict(valid)
    forged[mutation] = value
    with pytest.raises(parent.ParentControlError):
        parent._verify_selected_owner_scope(
            forged,
            session=session,
            signing_secret=secret,
            now=datetime(2026, 8, 23, 16, 0, tzinfo=timezone.utc),
        )


def test_selected_fixture_owner_requires_parent_attestation_for_exact_generated_scope(
    tmp_path: Path,
) -> None:
    parent = load(PARENT, "glasshive_parent_selected_owner_control")
    nested = load(NESTED, "glasshive_nested_selected_owner_control")
    state, session = private_state("PWK-UC-016")
    state["ownerId"] = "synthetic-owner-id"
    database = tmp_path / "runtime.sqlite3"
    seed_control_fixture(database, state)
    document = parent._control_document(
        operation="arm",
        state=state,
        session=session,
        boundary="provider_auth_missing",
        ttl_seconds=60,
    )
    plane = nested.LocalQAControlPlane(
        database,
        environment={
            "VIVENTIUM_GLASSHIVE_LOCAL_QA_MODE": "pwk_uc_016",
            "VIVENTIUM_LOCAL_QA_CASE_ID": "PWK-UC-016",
            "VIVENTIUM_LOCAL_QA_CASE_TOKEN": session["caseToken"],
            "VIVENTIUM_LOCAL_QA_SESSION_REF": session["sessionRef"],
            "VIVENTIUM_LOCAL_QA_CANDIDATE_DIGEST": session[
                "artifactIdentityDigest"
            ],
            "VIVENTIUM_LOCAL_QA_COMPONENT_ARTIFACT_DIGEST": session[
                "componentArtifactDigest"
            ],
        },
        clock=lambda: datetime(2026, 8, 23, 16, 0, tzinfo=timezone.utc),
    )

    result = plane.arm(document)
    assert result["status"] == "armed"
    assert document["scopeKind"] == "selected_synthetic_account_qa"
    assert str(document["fixtureAttestation"]).startswith("sha256:")

    forged = dict(document)
    forged["ownerId"] = "different-synthetic-owner"
    with pytest.raises(nested.LocalQAControlError):
        plane.arm(forged)


def test_parent_uses_only_private_fd_nested_module_commands() -> None:
    source = PARENT.read_text(encoding="utf-8")

    assert '"-m", "workers_projects_runtime.local_qa_control"' in source
    assert '"--input-fd"' in source
    assert "--input-file" not in source
    assert "--owner-id" not in source
    assert "--work-id" not in source
    assert "--run-id" not in source
    assert "--artifact-id" not in source
    assert "--case-token" not in source
    assert "WPR_DB_PATH" in source


@pytest.mark.parametrize(
    ("case_id", "boundary"),
    [
        (case_id, boundary)
        for case_id, boundaries in CASE_BOUNDARIES.items()
        for boundary in boundaries
    ],
)
def test_every_root_boundary_builds_one_exact_candidate_bound_private_request(
    case_id: str, boundary: str
) -> None:
    parent = load(PARENT, f"glasshive_parent_shape_{case_id}_{boundary}")
    state, session = private_state(case_id)

    document = parent._control_document(
        operation="arm",
        state=state,
        session=session,
        boundary=boundary,
        ttl_seconds=60,
    )

    assert set(document) == {
        "artifactId",
        "boundary",
        "candidateDigest",
        "caseId",
        "caseToken",
        "componentArtifactDigest",
        "contractVersion",
        "ownerId",
        "parameters",
        "runId",
        "scopeKind",
        "sessionRef",
        "ttlSeconds",
        "workId",
    }
    assert document["candidateDigest"] == session["artifactIdentityDigest"]
    assert document["componentArtifactDigest"] == session["componentArtifactDigest"]
    assert document["runId"] == (
        state["runId"] if boundary in parent.RUN_SCOPED_BOUNDARIES else ""
    )
    assert document["artifactId"] == (
        state["artifactId"] if boundary in parent.ARTIFACT_SCOPED_BOUNDARIES else ""
    )


def test_root_projects_candidate_and_measured_service_digest_to_the_component(
    tmp_path: Path,
) -> None:
    parent = load(PARENT, "glasshive_parent_artifact_authority")
    state, session = private_state("PWK-UC-016")
    del state
    database = tmp_path / "runtime.sqlite3"
    database.write_bytes(b"sqlite")
    database.chmod(0o600)
    runtime_env = tmp_path / "runtime.env"
    runtime_env.write_text(
        "\n".join(
            (
                f"VIVENTIUM_GLASSHIVE_LOCAL_QA_MODE={session['mode']}",
                f"VIVENTIUM_LOCAL_QA_CASE_ID={session['caseId']}",
                f"VIVENTIUM_LOCAL_QA_CASE_TOKEN={session['caseToken']}",
                f"VIVENTIUM_LOCAL_QA_SESSION_REF={session['sessionRef']}",
                "VIVENTIUM_LOCAL_QA_COMPONENT_ARTIFACT_DIGEST="
                f"{session['componentArtifactDigest']}",
                f"WPR_DB_PATH={database}",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    runtime_env.chmod(0o600)

    authority, selected_database = parent._runtime_authority(runtime_env, session)

    assert selected_database == database.resolve()
    assert authority["VIVENTIUM_LOCAL_QA_CANDIDATE_DIGEST"] == session[
        "artifactIdentityDigest"
    ]
    assert authority["VIVENTIUM_LOCAL_QA_COMPONENT_ARTIFACT_DIGEST"] == session[
        "componentArtifactDigest"
    ]
    serialized = json.dumps(authority, sort_keys=True)
    assert str(database) not in serialized


def test_root_rejects_symlinked_database_and_writable_parent_components(
    tmp_path: Path,
) -> None:
    parent = load(PARENT, "glasshive_parent_database_path_security")
    real = tmp_path / "real.sqlite3"
    sqlite3.connect(real).close()
    real.chmod(0o600)
    linked = tmp_path / "linked.sqlite3"
    linked.symlink_to(real)

    with pytest.raises(parent.ParentControlError):
        parent._database_path(str(linked))

    unsafe_parent = tmp_path / "unsafe"
    unsafe_parent.mkdir(mode=0o700)
    unsafe_database = unsafe_parent / "runtime.sqlite3"
    sqlite3.connect(unsafe_database).close()
    unsafe_database.chmod(0o600)
    unsafe_parent.chmod(0o733)
    try:
        with pytest.raises(parent.ParentControlError):
            parent._database_path(str(unsafe_database))
    finally:
        unsafe_parent.chmod(0o700)


def test_root_rejects_database_replacement_during_private_child_invocation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent = load(PARENT, "glasshive_parent_database_invocation_race")
    state, session = private_state("PWK-UC-017")
    database = tmp_path / "runtime.sqlite3"
    sqlite3.connect(database).close()
    database.chmod(0o600)
    _path, database_identity = parent._database_path_identity(str(database))

    def replace_database(**_kwargs: object):
        size = database.stat().st_size
        database.replace(tmp_path / "displaced.sqlite3")
        database.write_bytes(b"x" * size)
        database.chmod(0o600)
        return {}, None

    monkeypatch.setattr(parent, "_run_private_json", replace_database)

    with pytest.raises(parent.ParentControlError):
        parent._invoke_control(
            operation="query",
            document={},
            state=state,
            session=session,
            installed_root=ROOT,
            db_path=database,
            authority={},
            database_identity=database_identity,
        )


def test_root_private_child_input_is_a_linked_owner_only_regular_fd(
    tmp_path: Path,
) -> None:
    parent = load(PARENT, "glasshive_parent_private_fd")
    private_marker = secrets.token_urlsafe(32)
    child = (
        "import json,os,stat,sys;"
        "fd=int(sys.argv[sys.argv.index('--input-fd')+1]);"
        "s=os.fstat(fd);"
        "print(json.dumps({'regular':stat.S_ISREG(s.st_mode),"
        "'mode':stat.S_IMODE(s.st_mode),'links':s.st_nlink,'owner':s.st_uid==os.getuid()}))"
    )

    public, private = parent._run_private_json(
        argv=[sys.executable, "-c", child],
        cwd=tmp_path,
        env=os.environ.copy(),
        document={"private": private_marker},
        private_values=(private_marker,),
    )

    assert private is None
    assert public == {"regular": True, "mode": 0o600, "links": 1, "owner": True}


def test_root_parent_errors_and_timestamps_are_bounded_canonical_and_redacted(
    capsys: pytest.CaptureFixture[str],
) -> None:
    parent = load(PARENT, "glasshive_parent_bounded_cli")
    private_marker = secrets.token_urlsafe(32)

    assert parent.main(
        [
            "arm",
            "--boundary",
            private_marker,
            "--boundary=" + private_marker,
        ]
    ) == 2
    captured = capsys.readouterr()

    assert captured.out == ""
    assert captured.err == '{"error":"operation_failed"}\n'
    assert private_marker not in captured.err
    assert parent._iso(
        datetime(2026, 8, 23, 12, 0, 0, 123456, tzinfo=timezone.utc)
    ) == "2026-08-23T12:00:00.123+00:00"


@pytest.mark.parametrize(
    "timestamp",
    (
        "2026-08-23T12:00:00+00:00",
        "2026-08-23T12:00:00.123456+00:00",
        "2026-08-23T12:00:00.123Z",
        "2026-08-23T08:00:00.123-04:00",
    ),
)
def test_root_parent_rejects_every_noncanonical_timestamp(timestamp: str) -> None:
    parent = load(PARENT, "glasshive_parent_timestamp_" + secrets.token_hex(4))

    with pytest.raises(parent.ParentControlError):
        parent._parse_time(timestamp)


def test_cleanup_remains_available_after_the_exact_session_expires(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    actual_python = Path(sys.executable).resolve(strict=True)
    trusted_python = tmp_path / "trusted-python"
    trusted_python.write_text(
        f"#!/bin/sh\nexec {shlex.quote(str(actual_python))} \"$@\"\n",
        encoding="utf-8",
    )
    trusted_python.chmod(0o700)
    parent = load(PARENT, "glasshive_parent_expired_cleanup")
    monkeypatch.setattr(parent.sys, "executable", str(trusted_python))
    assert parent._python_binary() == str(trusted_python.resolve(strict=True))
    session_control = load(
        ROOT / "scripts" / "viventium" / "local_qa_runtime_control.py",
        "glasshive_parent_expired_session",
    )
    started = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)
    installed_root = ROOT
    artifact_identity = tmp_path / "artifact-identity.json"
    write_artifact_identity(installed_root, artifact_identity)
    request_path = tmp_path / "local-qa-request.json"
    request_path.write_text(
        json.dumps(
            {"contractVersion": 1, "mode": "local-qa", "requested": True},
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    request_path.chmod(0o600)
    session_path = tmp_path / "active.json"
    session_control.activate_session(
        state_path=session_path,
        installed_root=installed_root,
        artifact_identity_path=artifact_identity,
        local_qa_request_path=request_path,
        case_id="PWK-UC-017",
        expires_in_seconds=60,
        now=started,
    )
    session = session_control._read_state(session_path)
    namespace = secrets.token_hex(16)
    parent_state_path = tmp_path / "glasshive-parent.json"
    parent._write_private_json(
        parent_state_path,
        {
            "artifactId": "artifact_sha256:" + secrets.token_hex(32),
            "artifactIdentityDigest": session["artifactIdentityDigest"],
            "caseId": session["caseId"],
            "componentArtifactDigest": session["componentArtifactDigest"],
            "contractVersion": 1,
            "controlArtifactDigest": parent._control_artifact_digest(installed_root),
            "createdAt": session["startedAt"],
            "expiresAt": session["expiresAt"],
            "fixtureRef": "pwk_fixture_sha256:" + secrets.token_hex(32),
            "idempotencyKey": "qa_idem_" + secrets.token_hex(32),
            "installedRootHash": session["installedRootHash"],
            "namespace": namespace,
            "originRef": "qa_origin_" + namespace,
            "ownerId": "qa_owner_" + namespace,
            "projectId": "qa_project_" + namespace,
            "requestDigest": "sha256:" + secrets.token_hex(32),
            "runId": "qa_run_" + namespace,
            "sessionRef": session["sessionRef"],
            "status": "ready",
            "workId": "qa_work_" + namespace,
            "workerId": "qa_worker_" + namespace,
        },
    )
    database = tmp_path / "runtime.sqlite3"
    sqlite3.connect(database).close()
    database.chmod(0o600)
    runtime_env = tmp_path / "runtime.env"
    runtime_env.write_text(
        "\n".join(
            (
                f"VIVENTIUM_GLASSHIVE_LOCAL_QA_MODE={session['mode']}",
                f"VIVENTIUM_LOCAL_QA_CASE_ID={session['caseId']}",
                f"VIVENTIUM_LOCAL_QA_CASE_TOKEN={session['caseToken']}",
                f"VIVENTIUM_LOCAL_QA_SESSION_REF={session['sessionRef']}",
                "VIVENTIUM_LOCAL_QA_COMPONENT_ARTIFACT_DIGEST="
                f"{session['componentArtifactDigest']}",
                f"WPR_DB_PATH={database}",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    runtime_env.chmod(0o600)

    def destroy_fixture(**kwargs: object):
        state = kwargs["state"]
        assert isinstance(state, dict)
        return (
            {
                "contractVersion": 1,
                "fixtureRef": state["fixtureRef"],
                "operation": "destroy",
                "removed": {},
                "status": "clean",
            },
            None,
        )

    monkeypatch.setattr(parent, "_invoke_fixture", destroy_fixture)

    result = parent.cleanup_fixture(
        parent_state_path=parent_state_path,
        session_state_path=session_path,
        installed_root=installed_root,
        artifact_identity_path=artifact_identity,
        local_qa_request_path=request_path,
        runtime_env_path=runtime_env,
        now=started + timedelta(seconds=61),
    )

    assert result["status"] == "clean"
    assert not parent_state_path.exists()


def test_cleanup_uses_current_measured_digests_after_artifact_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent = load(PARENT, "glasshive_parent_replaced_artifact_cleanup")
    state, session = private_state("PWK-UC-017")
    session.update(
        {
            "expiresAt": "2026-08-23T12:01:00.000+00:00",
            "installedRootHash": "sha256:" + "e" * 64,
        }
    )
    state.update(
        {
            "artifactIdentityDigest": session["artifactIdentityDigest"],
            "componentArtifactDigest": session["componentArtifactDigest"],
            "expiresAt": session["expiresAt"],
            "installedRootHash": session["installedRootHash"],
            "sessionRef": session["sessionRef"],
            "status": "ready",
        }
    )
    current_candidate = "sha256:" + "c" * 64
    current_component = "sha256:" + "d" * 64
    database = tmp_path / "runtime.sqlite3"
    database_identity = ((1, 2, 3, 4, 5, 1), ())

    class SessionModule:
        @staticmethod
        def _require_local_qa_request(_path: Path) -> None:
            return None

        @staticmethod
        def _artifact_digests(_path: Path, _root: Path) -> tuple[str, str]:
            return current_candidate, current_component

    monkeypatch.setattr(parent, "_session_module", lambda: SessionModule)
    monkeypatch.setattr(parent, "_raw_session", lambda _path: session)
    monkeypatch.setattr(parent, "_state", lambda _path: state)
    monkeypatch.setattr(parent, "_root_hash", lambda _path: session["installedRootHash"])
    monkeypatch.setattr(
        parent,
        "_parse_runtime_env",
        lambda _path: {
            "VIVENTIUM_GLASSHIVE_LOCAL_QA_MODE": session["mode"],
            "VIVENTIUM_LOCAL_QA_CASE_ID": session["caseId"],
            "VIVENTIUM_LOCAL_QA_CASE_TOKEN": session["caseToken"],
            "VIVENTIUM_LOCAL_QA_COMPONENT_ARTIFACT_DIGEST": session[
                "componentArtifactDigest"
            ],
            "VIVENTIUM_LOCAL_QA_SESSION_REF": session["sessionRef"],
            "WPR_DB_PATH": str(database),
        },
    )
    monkeypatch.setattr(
        parent,
        "_database_path_identity",
        lambda _raw: (database, database_identity),
    )

    _state, _session, authority, selected_database, selected_identity = (
        parent._common_cleanup(
            parent_state_path=tmp_path / "parent.json",
            session_state_path=tmp_path / "session.json",
            installed_root=tmp_path,
            artifact_identity_path=tmp_path / "artifact.json",
            local_qa_request_path=tmp_path / "request.json",
            runtime_env_path=tmp_path / "runtime.env",
        )
    )

    assert authority["VIVENTIUM_LOCAL_QA_CANDIDATE_DIGEST"] == current_candidate
    assert (
        authority["VIVENTIUM_LOCAL_QA_COMPONENT_ARTIFACT_DIGEST"]
        == current_component
    )
    assert selected_database == database
    assert selected_identity == database_identity


def test_cleanup_rejects_same_size_parent_state_mutation_before_fixture_delete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent = load(PARENT, "glasshive_parent_cleanup_identity_race")
    session_control = load(
        ROOT / "scripts" / "viventium" / "local_qa_runtime_control.py",
        "glasshive_parent_cleanup_identity_session",
    )
    started = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)
    artifact_identity = tmp_path / "artifact-identity.json"
    write_artifact_identity(ROOT, artifact_identity)
    request_path = tmp_path / "local-qa-request.json"
    request_path.write_text(
        json.dumps(
            {"contractVersion": 1, "mode": "local-qa", "requested": True},
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    request_path.chmod(0o600)
    session_path = tmp_path / "active.json"
    session_control.activate_session(
        state_path=session_path,
        installed_root=ROOT,
        artifact_identity_path=artifact_identity,
        local_qa_request_path=request_path,
        case_id="PWK-UC-017",
        expires_in_seconds=60,
        now=started,
    )
    session = session_control._read_state(session_path)
    namespace = secrets.token_hex(16)
    parent_state_path = tmp_path / "glasshive-parent.json"
    state = {
        "artifactId": "artifact_sha256:" + secrets.token_hex(32),
        "artifactIdentityDigest": session["artifactIdentityDigest"],
        "caseId": session["caseId"],
        "componentArtifactDigest": session["componentArtifactDigest"],
        "contractVersion": 1,
        "controlArtifactDigest": parent._control_artifact_digest(ROOT),
        "createdAt": session["startedAt"],
        "expiresAt": session["expiresAt"],
        "fixtureRef": "pwk_fixture_sha256:" + secrets.token_hex(32),
        "idempotencyKey": "qa_idem_" + secrets.token_hex(32),
        "installedRootHash": session["installedRootHash"],
        "namespace": namespace,
        "originRef": "qa_origin_" + namespace,
        "ownerId": "qa_owner_" + namespace,
        "projectId": "qa_project_" + namespace,
        "requestDigest": "sha256:" + secrets.token_hex(32),
        "runId": "qa_run_" + namespace,
        "sessionRef": session["sessionRef"],
        "status": "ready",
        "workId": "qa_work_" + namespace,
        "workerId": "qa_worker_" + namespace,
    }
    parent._write_private_json(parent_state_path, state)
    database = tmp_path / "runtime.sqlite3"
    sqlite3.connect(database).close()
    database.chmod(0o600)
    runtime_env = tmp_path / "runtime.env"
    runtime_env.write_text(
        "\n".join(
            (
                f"VIVENTIUM_GLASSHIVE_LOCAL_QA_MODE={session['mode']}",
                f"VIVENTIUM_LOCAL_QA_CASE_ID={session['caseId']}",
                f"VIVENTIUM_LOCAL_QA_CASE_TOKEN={session['caseToken']}",
                f"VIVENTIUM_LOCAL_QA_SESSION_REF={session['sessionRef']}",
                "VIVENTIUM_LOCAL_QA_COMPONENT_ARTIFACT_DIGEST="
                f"{session['componentArtifactDigest']}",
                f"WPR_DB_PATH={database}",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    runtime_env.chmod(0o600)
    fixture_called = False

    def mutate_after_control(**_kwargs: object) -> dict[str, object]:
        mutated = dict(state)
        original_digest = str(mutated["requestDigest"])
        mutated["requestDigest"] = original_digest[:-1] + (
            "0" if original_digest[-1] != "0" else "1"
        )
        parent._write_private_json(parent_state_path, mutated)
        return {
            "artifactReplacementCleared": 0,
            "caseId": state["caseId"],
            "contractVersion": 1,
            "expiredControls": 0,
            "operation": "cleanup",
            "removedAuditEvents": 0,
            "removedControls": 0,
            "status": "clean",
        }

    def forbid_fixture(**_kwargs: object):
        nonlocal fixture_called
        fixture_called = True
        raise AssertionError("fixture deletion must not start")

    monkeypatch.setattr(parent, "_invoke_control", mutate_after_control)
    monkeypatch.setattr(parent, "_invoke_fixture", forbid_fixture)

    with pytest.raises(parent.ParentControlError):
        parent.cleanup_fixture(
            parent_state_path=parent_state_path,
            session_state_path=session_path,
            installed_root=ROOT,
            artifact_identity_path=artifact_identity,
            local_qa_request_path=request_path,
            runtime_env_path=runtime_env,
            now=started + timedelta(seconds=61),
        )

    assert not fixture_called
    assert parent_state_path.exists()


def test_root_private_fd_runs_arm_query_clear_cleanup_against_the_real_component(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actual_python = Path(sys.executable).resolve(strict=True)
    trusted_python = tmp_path / "trusted-python"
    trusted_python.write_text(
        f"#!/bin/sh\nexec {shlex.quote(str(actual_python))} \"$@\"\n",
        encoding="utf-8",
    )
    trusted_python.chmod(0o700)
    parent = load(PARENT, "glasshive_parent_real_component_flow")
    monkeypatch.setattr(parent.sys, "executable", str(trusted_python))
    assert parent._python_binary() == str(trusted_python.resolve(strict=True))
    state, session = private_state("PWK-UC-017")
    database = tmp_path / "runtime.sqlite3"
    seed_control_fixture(database, state)
    authority = {
        "VIVENTIUM_GLASSHIVE_LOCAL_QA_MODE": str(session["mode"]),
        "VIVENTIUM_LOCAL_QA_CANDIDATE_DIGEST": str(
            session["artifactIdentityDigest"]
        ),
        "VIVENTIUM_LOCAL_QA_CASE_ID": str(session["caseId"]),
        "VIVENTIUM_LOCAL_QA_CASE_TOKEN": str(session["caseToken"]),
        "VIVENTIUM_LOCAL_QA_COMPONENT_ARTIFACT_DIGEST": str(
            session["componentArtifactDigest"]
        ),
        "VIVENTIUM_LOCAL_QA_SESSION_REF": str(session["sessionRef"]),
    }
    boundary = "callback_transport_interruption"
    arm_document = parent._control_document(
        operation="arm",
        state=state,
        session=session,
        boundary=boundary,
        ttl_seconds=60,
    )

    armed = parent._invoke_control(
        operation="arm",
        document=arm_document,
        state=state,
        session=session,
        installed_root=ROOT,
        db_path=database,
        authority=authority,
    )
    queried = parent._invoke_control(
        operation="query",
        document=parent._control_document(
            operation="query", state=state, session=session
        ),
        state=state,
        session=session,
        installed_root=ROOT,
        db_path=database,
        authority=authority,
    )
    cleared = parent._invoke_control(
        operation="clear",
        document=parent._control_document(
            operation="clear",
            state=state,
            session=session,
            control_ref=str(armed["controlRef"]),
        ),
        state=state,
        session=session,
        installed_root=ROOT,
        db_path=database,
        authority=authority,
    )
    cleaned = parent._invoke_control(
        operation="cleanup",
        document=parent._control_document(
            operation="cleanup", state=state, session=session
        ),
        state=state,
        session=session,
        installed_root=ROOT,
        db_path=database,
        authority=authority,
    )

    assert armed["status"] == "armed"
    assert queried["count"] == 1
    assert cleared["status"] == "cleared"
    assert cleaned["removedControls"] == 1
    serialized = json.dumps([armed, queried, cleared, cleaned], sort_keys=True)
    for private_value in (
        session["caseToken"],
        session["sessionRef"],
        state["ownerId"],
        state["workId"],
        state["runId"],
        state["artifactId"],
        database,
    ):
        assert str(private_value) not in serialized


def test_fixture_selected_owner_requires_parent_secret_attestation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = load_fixture("glasshive_fixture_selected_owner")
    secret = "synthetic-fixture-parent-secret"
    request = fixture_request("2026-08-23T12:00:00.123+00:00")
    request["ownerId"] = "synthetic-owner-id"
    request["scopeKind"] = "selected_synthetic_account_qa"
    canonical = json.dumps(request, sort_keys=True, separators=(",", ":"))
    request["ownerAttestation"] = "sha256:" + hmac.new(
        secret.encode(),
        ("glasshive-fixture-owner-v1\0" + canonical).encode(),
        hashlib.sha256,
    ).hexdigest()
    monkeypatch.setenv(fixture.FIXTURE_SECRET_ENV, secret)

    validated = fixture._validate_common(request, fields=fixture.PROVISION_FIELDS)
    assert validated["ownerId"] == "synthetic-owner-id"

    forged = dict(request)
    forged["ownerId"] = "different-synthetic-owner"
    with pytest.raises(fixture.FixtureError):
        fixture._validate_common(forged, fields=fixture.PROVISION_FIELDS)
    monkeypatch.delenv(fixture.FIXTURE_SECRET_ENV)
    with pytest.raises(fixture.FixtureError):
        fixture._validate_common(request, fields=fixture.PROVISION_FIELDS)


def test_fixture_expires_at_uses_only_the_exact_canonical_timestamp_boundary(
    tmp_path: Path,
) -> None:
    fixture = load_fixture("glasshive_fixture_timestamp_boundary")
    canonical = "2026-08-23T12:00:00.123+00:00"

    validated = fixture._validate_common(
        fixture_request(canonical), fields=fixture.PROVISION_FIELDS
    )

    assert validated["expiresAt"] == canonical
    for invalid in (
        "2026-08-23T12:00:00+00:00",
        "2026-08-23T12:00:00.123456+00:00",
        "2026-08-23T12:00:00.123Z",
        "2026-08-23T08:00:00.123-04:00",
        "2026-13-23T12:00:00.123+00:00",
        None,
        1,
        "x" * fixture.PRIVATE_INPUT_MAX_BYTES,
    ):
        with pytest.raises(fixture.FixtureError):
            fixture._validate_common(
                fixture_request(invalid), fields=fixture.PROVISION_FIELDS
            )

    encoded = json.dumps(
        fixture_request(canonical), sort_keys=True, separators=(",", ":")
    )
    marker = f'"expiresAt":"{canonical}"'
    duplicate_path = tmp_path / "duplicate-expires-at.json"
    duplicate_path.write_text(
        encoded.replace(marker, f"{marker},{marker}"), encoding="utf-8"
    )
    duplicate_path.chmod(0o600)
    descriptor = os.open(
        duplicate_path,
        os.O_RDONLY | getattr(os, "O_NONBLOCK", 0),
    )
    try:
        with pytest.raises(fixture.FixtureError):
            fixture._read_request(descriptor)
    finally:
        os.close(descriptor)

    oversized_path = tmp_path / "oversized-expires-at.json"
    oversized_path.write_bytes(
        b'{"expiresAt":"' + b"x" * fixture.PRIVATE_INPUT_MAX_BYTES + b'"}'
    )
    oversized_path.chmod(0o600)
    descriptor = os.open(
        oversized_path,
        os.O_RDONLY | getattr(os, "O_NONBLOCK", 0),
    )
    try:
        with pytest.raises(fixture.FixtureError):
            fixture._read_request(descriptor)
    finally:
        os.close(descriptor)


def test_fixture_private_fd_rejects_same_inode_same_size_content_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = load_fixture("glasshive_fixture_fd_identity")
    request_path = tmp_path / "fixture-request.json"
    original = json.dumps(
        fixture_request("2026-08-23T12:00:00.123+00:00"),
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    replacement = original.replace(b'"PWK-UC-016"', b'"PWK-UC-017"')
    assert len(replacement) == len(original)
    request_path.write_bytes(original)
    request_path.chmod(0o600)
    descriptor = os.open(
        request_path,
        os.O_RDONLY | getattr(os, "O_NONBLOCK", 0),
    )
    before = os.fstat(descriptor)
    original_read = fixture.os.read
    mutated = False

    def raced_read(opened: int, size: int) -> bytes:
        nonlocal mutated
        raw = original_read(opened, size)
        if opened == descriptor and not mutated:
            request_path.write_bytes(replacement)
            request_path.chmod(0o600)
            mutated = True
        return raw

    monkeypatch.setattr(fixture.os, "read", raced_read)
    try:
        with pytest.raises(fixture.FixtureError):
            fixture._read_request(descriptor)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)

    assert mutated
    assert (before.st_dev, before.st_ino, before.st_size) == (
        after.st_dev,
        after.st_ino,
        after.st_size,
    )
    assert request_path.read_bytes() == replacement


def test_fixture_artifact_cleanup_final_swap_deletes_neither_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "runtime.sqlite3"
    namespace = "e" * 32
    owner_id = "qa_owner_" + namespace
    project_id = "qa_project_" + namespace
    worker_id = "qa_worker_" + namespace
    work_id = "qa_work_" + namespace
    run_id = "qa_run_" + namespace

    class FixtureStore:
        def __init__(self, path: str) -> None:
            self.path = path

        @contextmanager
        def _connect(self):
            connection = sqlite3.connect(self.path)
            try:
                yield connection
            finally:
                connection.close()

    fixture = load_fixture("glasshive_fixture_artifact_unlink_race", FixtureStore)
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE projects (project_id TEXT, owner_id TEXT, tenant_id TEXT);
            CREATE TABLE workers (worker_id TEXT, project_id TEXT, owner_id TEXT);
            CREATE TABLE runs (run_id TEXT, worker_id TEXT, project_id TEXT);
            CREATE TABLE delegations (
                work_ref TEXT, owner_id TEXT, project_id TEXT,
                worker_id TEXT, current_run_id TEXT
            );
            CREATE TABLE work_trace_events (run_id TEXT, work_ref TEXT, owner_id TEXT);
            CREATE TABLE events (project_id TEXT, worker_id TEXT, run_id TEXT);
            """
        )
        connection.execute(
            "INSERT INTO projects VALUES (?, ?, 'local')", (project_id, owner_id)
        )
        connection.execute(
            "INSERT INTO workers VALUES (?, ?, ?)",
            (worker_id, project_id, owner_id),
        )
        connection.execute(
            "INSERT INTO runs VALUES (?, ?, ?)", (run_id, worker_id, project_id)
        )
        connection.execute(
            "INSERT INTO delegations VALUES (?, ?, ?, ?, ?)",
            (work_id, owner_id, project_id, worker_id, run_id),
        )
        connection.execute(
            "INSERT INTO work_trace_events VALUES (?, ?, ?)",
            (run_id, work_id, owner_id),
        )
    database.chmod(0o600)
    values = {
        "artifactId": "artifact_sha256:" + "f" * 64,
        "caseId": "PWK-UC-017",
        "expiresAt": "2026-08-23T12:00:00.123+00:00",
        "idempotencyKey": "qa_idem_" + "1" * 64,
        "namespace": namespace,
        "originRef": "qa_origin_" + namespace,
        "ownerId": owner_id,
        "requestDigest": "sha256:" + "2" * 64,
    }
    request = {
        "projectId": project_id,
        "runId": run_id,
        "workId": work_id,
        "workerId": worker_id,
    }
    monkeypatch.setenv("WPR_DB_PATH", str(database))
    monkeypatch.setattr(
        fixture,
        "_validate_common",
        lambda _request, *, fields: dict(values),
    )
    artifact = fixture._artifact_path(database, namespace)
    artifact.parent.mkdir(mode=0o700, parents=True)
    original = b"Synthetic fixture artifact\n"
    replacement = b"Replacement fixture bytes!\n"
    assert len(replacement) == len(original)
    artifact.write_bytes(original)
    artifact.chmod(0o600)
    displaced = artifact.with_name("original-artifact.txt")
    raced = False

    def swap_public_name() -> None:
        nonlocal raced
        if raced:
            return
        artifact.replace(displaced)
        artifact.write_bytes(replacement)
        artifact.chmod(0o600)
        raced = True

    original_path_unlink = fixture.Path.unlink

    def raced_path_unlink(path: Path, *args: object, **kwargs: object) -> None:
        if path == artifact:
            swap_public_name()
        original_path_unlink(path, *args, **kwargs)

    monkeypatch.setattr(fixture.Path, "unlink", raced_path_unlink)
    identity_safe_files = getattr(fixture, "_identity_safe_files", None)
    if identity_safe_files is not None:
        original_rename = identity_safe_files._rename_noreplace

        def raced_rename(
            source: str,
            destination: str,
            *,
            source_dir_fd: int,
            destination_dir_fd: int,
        ) -> None:
            if source == artifact.name:
                swap_public_name()
            original_rename(
                source,
                destination,
                source_dir_fd=source_dir_fd,
                destination_dir_fd=destination_dir_fd,
            )

        monkeypatch.setattr(identity_safe_files, "_rename_noreplace", raced_rename)

    with pytest.raises(fixture.FixtureError) as caught:
        fixture.destroy(request)

    assert raced
    assert getattr(caught.value, "outcome", "") == "replacement_restored"
    assert displaced.read_bytes() == original
    assert artifact.read_bytes() == replacement


def test_fixture_helper_uses_the_installed_store_and_exact_compare_delete() -> None:
    source = FIXTURE.read_text(encoding="utf-8")

    assert "from workers_projects_runtime.store import Store" in source
    assert "reserve_delegation(" in source
    assert "record_artifact_trace(" in source
    assert "DELETE FROM delegations" in source
    assert "DELETE FROM runs" in source
    assert "DELETE FROM workers" in source
    assert "DELETE FROM projects" in source
    assert "WHERE work_ref = ? AND owner_id = ?" in source
    assert "WHERE run_id = ? AND worker_id = ? AND project_id = ?" in source


def test_fixture_destroy_removes_exact_run_dependents_in_foreign_key_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "runtime.sqlite3"
    namespace = "6" * 32
    owner_id = "qa_owner_" + namespace
    project_id = "qa_project_" + namespace
    worker_id = "qa_worker_" + namespace
    work_id = "qa_work_" + namespace
    run_id = "qa_run_" + namespace
    attempt_id = "qa_attempt_" + namespace
    lease_id = "qa_lease_" + namespace

    class FixtureStore:
        def __init__(self, path: str) -> None:
            self.path = path

        @contextmanager
        def _connect(self):
            connection = sqlite3.connect(self.path)
            connection.execute("PRAGMA foreign_keys = ON")
            try:
                yield connection
            finally:
                connection.close()

    fixture = load_fixture("glasshive_fixture_fk_cleanup", FixtureStore)
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(
            """
            CREATE TABLE projects (project_id TEXT PRIMARY KEY, owner_id TEXT, tenant_id TEXT);
            CREATE TABLE workers (
              worker_id TEXT PRIMARY KEY, project_id TEXT, owner_id TEXT,
              FOREIGN KEY(project_id) REFERENCES projects(project_id)
            );
            CREATE TABLE runs (
              run_id TEXT PRIMARY KEY, worker_id TEXT, project_id TEXT,
              FOREIGN KEY(worker_id) REFERENCES workers(worker_id),
              FOREIGN KEY(project_id) REFERENCES projects(project_id)
            );
            CREATE TABLE run_attempts (
              attempt_id TEXT PRIMARY KEY, run_id TEXT,
              FOREIGN KEY(run_id) REFERENCES runs(run_id)
            );
            CREATE TABLE host_run_leases (
              lease_id TEXT PRIMARY KEY, owner_id TEXT, worker_id TEXT, run_id TEXT,
              FOREIGN KEY(worker_id) REFERENCES workers(worker_id),
              FOREIGN KEY(run_id) REFERENCES runs(run_id)
            );
            CREATE TABLE provider_liveness_events (
              event_ref TEXT PRIMARY KEY, run_id TEXT, attempt_id TEXT,
              FOREIGN KEY(run_id) REFERENCES runs(run_id),
              FOREIGN KEY(attempt_id) REFERENCES run_attempts(attempt_id)
            );
            CREATE TABLE callback_outbox (
              callback_id TEXT PRIMARY KEY, project_id TEXT, worker_id TEXT, run_id TEXT,
              FOREIGN KEY(project_id) REFERENCES projects(project_id),
              FOREIGN KEY(worker_id) REFERENCES workers(worker_id)
            );
            CREATE TABLE active_work_action_uses (
              action_use_id TEXT PRIMARY KEY, owner_id TEXT, work_ref TEXT
            );
            CREATE TABLE delegations (
              work_ref TEXT PRIMARY KEY, owner_id TEXT, project_id TEXT,
              worker_id TEXT, current_run_id TEXT,
              FOREIGN KEY(project_id) REFERENCES projects(project_id),
              FOREIGN KEY(worker_id) REFERENCES workers(worker_id),
              FOREIGN KEY(current_run_id) REFERENCES runs(run_id)
            );
            CREATE TABLE work_trace_events (run_id TEXT, work_ref TEXT, owner_id TEXT);
            CREATE TABLE events (project_id TEXT, worker_id TEXT, run_id TEXT);
            """
        )
        connection.execute("INSERT INTO projects VALUES (?, ?, 'local')", (project_id, owner_id))
        connection.execute("INSERT INTO workers VALUES (?, ?, ?)", (worker_id, project_id, owner_id))
        connection.execute("INSERT INTO runs VALUES (?, ?, ?)", (run_id, worker_id, project_id))
        connection.execute("INSERT INTO run_attempts VALUES (?, ?)", (attempt_id, run_id))
        connection.execute(
            "INSERT INTO host_run_leases VALUES (?, ?, ?, ?)",
            (lease_id, owner_id, worker_id, run_id),
        )
        connection.execute(
            "INSERT INTO provider_liveness_events VALUES (?, ?, ?)",
            ("qa_liveness_" + namespace, run_id, attempt_id),
        )
        connection.execute(
            "INSERT INTO callback_outbox VALUES (?, ?, ?, ?)",
            ("qa_callback_" + namespace, project_id, worker_id, run_id),
        )
        connection.execute(
            "INSERT INTO delegations VALUES (?, ?, ?, ?, ?)",
            (work_id, owner_id, project_id, worker_id, run_id),
        )
        connection.execute(
            "INSERT INTO active_work_action_uses VALUES (?, ?, ?)",
            ("qa_action_" + namespace, owner_id, work_id),
        )
        connection.execute("INSERT INTO work_trace_events VALUES (?, ?, ?)", (run_id, work_id, owner_id))
        connection.execute(
            "INSERT INTO projects VALUES ('qa_project_unrelated', 'qa_owner_unrelated', 'local')"
        )
        connection.execute(
            "INSERT INTO workers VALUES ('qa_worker_unrelated', 'qa_project_unrelated', 'qa_owner_unrelated')"
        )
        connection.execute(
            "INSERT INTO callback_outbox VALUES ('qa_callback_cross_scope', ?, 'qa_worker_unrelated', ?)",
            (project_id, run_id),
        )
    database.chmod(0o600)
    monkeypatch.setenv("WPR_DB_PATH", str(database))
    monkeypatch.setattr(
        fixture,
        "_validate_common",
        lambda _request, *, fields: {
            "artifactId": "artifact_sha256:" + "f" * 64,
            "caseId": "PWK-UC-016",
            "expiresAt": "2026-08-23T12:00:00.123+00:00",
            "idempotencyKey": "qa_idem_" + "1" * 64,
            "namespace": namespace,
            "originRef": "qa_origin_" + namespace,
            "ownerId": owner_id,
            "requestDigest": "sha256:" + "2" * 64,
        },
    )

    request = {
        "projectId": project_id,
        "runId": run_id,
        "workId": work_id,
        "workerId": worker_id,
    }
    with pytest.raises(fixture.FixtureError):
        fixture.destroy(request)
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM runs WHERE run_id = ?", (run_id,)).fetchone()[0] == 1
        connection.execute("DELETE FROM callback_outbox WHERE callback_id = 'qa_callback_cross_scope'")

    result = fixture.destroy(request)

    assert result["status"] == "clean"
    with sqlite3.connect(database) as connection:
        for table in (
            "provider_liveness_events",
            "active_work_action_uses",
            "callback_outbox",
            "host_run_leases",
            "run_attempts",
            "delegations",
            "runs",
        ):
            assert connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM workers").fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM workers WHERE worker_id = 'qa_worker_unrelated'"
        ).fetchone()[0] == 1


def test_public_cli_has_a_closed_glasshive_argument_matrix() -> None:
    source = CLI.read_text(encoding="utf-8")
    usage = source.split("Usage:", 1)[1].split("USAGE", 1)[0]

    for command in (
        "prepare-glasshive --case-id",
        "arm-glasshive --boundary",
        "query-glasshive [--boundary",
        "clear-glasshive [--boundary",
        "cleanup-glasshive",
    ):
        assert command in usage

    branch = source.rsplit("      prepare-glasshive)", 1)[1].split(
        "      inject-release-claim|restore-release-claim)", 1
    )[0]
    assert '"$@"' not in branch
    assert "qa_glasshive_user_args" in branch
    for forbidden in (
        "--parent-state",
        "--session-state",
        "--installed-root",
        "--artifact-identity",
        "--runtime-env",
        "--owner-id",
        "--work-id",
        "--run-id",
        "--artifact-id",
        "--case-token",
    ):
        assert forbidden not in branch


def test_public_cli_clear_has_a_glasshive_fixture_gate() -> None:
    source = CLI.read_text(encoding="utf-8")
    clear_branch = source.rsplit("      clear)", 1)[1].split("      *)", 1)[0]

    assert "glasshive_qa_parent_control.py" in clear_branch
    assert "clear-gate" in clear_branch
    assert "fixture and controls" in clear_branch


def test_qa_ownership_and_docs_reference_the_root_contract() -> None:
    owners = (ROOT / "qa" / "release-test-owners.yaml").read_text(encoding="utf-8")
    cases = (ROOT / "qa" / "parallel-orchestrator" / "cases.md").read_text(
        encoding="utf-8"
    )
    feature = (
        ROOT / "docs" / "requirements_and_learnings" / "55_Parallel_Work_Orchestration.md"
    ).read_text(encoding="utf-8")
    qa_map = (
        ROOT / "docs" / "requirements_and_learnings" / "45_Runtime_Feature_QA_Map.md"
    ).read_text(encoding="utf-8")

    test_path = "tests/release/test_glasshive_qa_parent_control.py"
    assert test_path in owners
    assert test_path in cases
    assert "prepare-glasshive" in feature
    assert "arm-glasshive" in feature
    assert "test_glasshive_qa_parent_control.py" in qa_map


def test_no_tracked_example_contains_private_glasshive_scope() -> None:
    for path in (PARENT, FIXTURE):
        source = path.read_text(encoding="utf-8")
        assert "/Users/" not in source
        assert "Library/Application Support/Viventium" not in source
        assert "example-owner-id" not in source
        assert "example-work-id" not in source
        assert "example-run-id" not in source
        assert "example-artifact-id" not in source
        assert "print(exc" not in source
        assert "capture_output=True" not in source

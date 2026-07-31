from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path

import pytest

from scripts.viventium import rag_postgres_migration


REPO_ROOT = Path(__file__).resolve().parents[2]
LAUNCHER_PATH = REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh"


LEGACY_RELATIONS = [
    {"schema": "public", "name": "langchain_pg_collection", "kind": "r"},
    {"schema": "public", "name": "langchain_pg_embedding", "kind": "r"},
]


class FakeDocker:
    def __init__(
        self,
        *,
        pgdata_path: Path,
        relations: list[dict[str, str]] | None = None,
        database_owner: str | None = "myuser",
        role_oid: str | None = "16384",
        database_oid: str | None = "16385",
        mount_source: str | None = None,
        fail_alter: bool = False,
        drift_after_alter: bool = False,
        readiness_failures: int = 0,
        identity_failures: int = 0,
    ) -> None:
        self.pgdata_path = pgdata_path
        self.relations = LEGACY_RELATIONS if relations is None else relations
        self.database_owner = database_owner
        self.role_oid = role_oid
        self.database_oid = database_oid
        self.mount_source = mount_source or str(pgdata_path)
        self.fail_alter = fail_alter
        self.drift_after_alter = drift_after_alter
        self.readiness_failures = readiness_failures
        self.identity_failures = identity_failures
        self.calls: list[dict[str, object]] = []
        self.alter_inputs: list[str] = []
        self.initial_container_id = ""
        self.started = False
        self.alter_completed = False

    def run(
        self,
        args: list[str],
        *,
        input_text: str | None = None,
        env: dict[str, str] | None = None,
    ) -> rag_postgres_migration.CommandResult:
        self.calls.append({"args": args, "input": input_text, "env": env})

        if args[:1] == ["compose"] and args[-3:] == ["ps", "-q", "vectordb"]:
            container_id = "rag-vectordb" if self.started else self.initial_container_id
            return rag_postgres_migration.CommandResult(
                returncode=0,
                stdout=container_id + ("\n" if container_id else ""),
                stderr="",
            )
        if args[:1] == ["compose"] and args[-3:] == ["up", "-d", "vectordb"]:
            self.started = True
            return rag_postgres_migration.CommandResult(0, "", "")
        if args[:1] == ["compose"] and args[-2:] == ["stop", "vectordb"]:
            return rag_postgres_migration.CommandResult(0, "", "")
        if args[:1] == ["inspect"] and "Mounts" in args[-2]:
            return rag_postgres_migration.CommandResult(
                0,
                json.dumps(
                    [
                        {
                            "Type": "bind",
                            "Source": self.mount_source,
                            "Destination": "/var/lib/postgresql/data",
                        }
                    ]
                )
                + "\n",
                "",
            )
        if args[:1] == ["inspect"] and "Labels" in args[-2]:
            return rag_postgres_migration.CommandResult(
                0,
                json.dumps(
                    {
                        "com.docker.compose.project": "qa-rag",
                        "com.docker.compose.service": "vectordb",
                    }
                )
                + "\n",
                "",
            )
        if args[:1] == ["exec"] and input_text is None and "pg_isready" in args:
            if self.readiness_failures > 0:
                self.readiness_failures -= 1
                return rag_postgres_migration.CommandResult(1, "", "not ready")
            return rag_postgres_migration.CommandResult(0, "accepting connections\n", "")
        if args[:1] == ["exec"] and input_text and "pg_control_system" in input_text:
            if self.identity_failures > 0:
                self.identity_failures -= 1
                return rag_postgres_migration.CommandResult(1, "", "server restarted")
            return rag_postgres_migration.CommandResult(
                0,
                json.dumps(
                    {
                        "serverVersionNum": 150015,
                        "systemIdentifier": "7412345678901234567",
                        "databaseOid": self.database_oid,
                        "databaseOwner": self.database_owner,
                        "roleOid": self.role_oid,
                        "roleCanLogin": True if self.role_oid else None,
                    }
                )
                + "\n",
                "",
            )
        if args[:1] == ["exec"] and input_text and "relationInventory" in input_text:
            return rag_postgres_migration.CommandResult(
                0,
                json.dumps(
                    {
                        "relationInventory": self.relations,
                        "extensions": ["plpgsql", "vector"]
                        if self.relations
                        else ["plpgsql"],
                        "columnInventory": [],
                        "indexInventory": [],
                        "constraintInventory": [],
                    }
                )
                + "\n",
                "",
            )
        if args[:1] == ["exec"] and input_text and "RAG_COLLECTION_ROWS" in input_text:
            rows = ['{"name":"synthetic","uuid":"00000000-0000-0000-0000-000000000001"}']
            if self.alter_completed and self.drift_after_alter:
                rows = [
                    '{"name":"same-count-content-drift",'
                    '"uuid":"00000000-0000-0000-0000-000000000001"}'
                ]
            return rag_postgres_migration.CommandResult(
                0,
                "\n".join(rows) + "\n",
                "",
            )
        if args[:1] == ["exec"] and input_text and "RAG_EMBEDDING_ROWS" in input_text:
            return rag_postgres_migration.CommandResult(
                0,
                (
                    '{"cmetadata":{"scope":"public-safe-qa"},'
                    '"collection_id":"00000000-0000-0000-0000-000000000001",'
                    '"custom_id":"synthetic-document","embedding":"[1,2,3]",'
                    '"uuid":"00000000-0000-0000-0000-000000000002"}\n'
                ),
                "",
            )
        if args[:1] == ["exec"] and input_text and "ALTER ROLE" in input_text:
            self.alter_inputs.append(input_text)
            if self.fail_alter:
                return rag_postgres_migration.CommandResult(
                    1,
                    "",
                    f"synthetic failure echoed {input_text}",
                )
            self.alter_completed = True
            return rag_postgres_migration.CommandResult(0, "ALTER ROLE\n", "")

        raise AssertionError(f"Unexpected docker command: {args!r}")


@pytest.fixture()
def migration_paths(tmp_path: Path) -> tuple[Path, Path, Path]:
    compose_file = tmp_path / "rag.yml"
    compose_file.write_text("services:\n  vectordb: {}\n", encoding="utf-8")
    pgdata_path = tmp_path / "rag-pgdata"
    pgdata_path.mkdir()
    state_dir = tmp_path / "state" / "rag-postgres"
    return compose_file, pgdata_path, state_dir


def _run_migration(
    *,
    compose_file: Path,
    pgdata_path: Path,
    state_dir: Path,
    docker: FakeDocker,
) -> rag_postgres_migration.MigrationResult:
    return rag_postgres_migration.migrate_rag_postgres(
        compose_file=compose_file,
        project_name="qa-rag",
        pgdata_path=pgdata_path,
        pgdata_path_mode="host",
        state_dir=state_dir,
        docker=docker,
    )


def test_legacy_pgdata_migration_preserves_schema_and_writes_only_redacted_state(
    migration_paths: tuple[Path, Path, Path],
) -> None:
    compose_file, pgdata_path, state_dir = migration_paths
    docker = FakeDocker(pgdata_path=pgdata_path)

    result = _run_migration(
        compose_file=compose_file,
        pgdata_path=pgdata_path,
        state_dir=state_dir,
        docker=docker,
    )

    password = result.credential_path.read_text(encoding="ascii").strip()
    assert len(password) == 64
    assert set(password) <= set("0123456789abcdef")
    assert stat.S_IMODE(result.credential_path.stat().st_mode) == 0o600

    receipt_text = result.receipt_path.read_text(encoding="utf-8")
    receipt = json.loads(receipt_text)
    assert password not in receipt_text
    assert receipt["schemaVersion"] == 1
    assert receipt["status"] == "ready"
    assert receipt["cluster"]["systemIdentifier"] == "7412345678901234567"
    assert receipt["credentialSha256"] == hashlib.sha256(password.encode("ascii")).hexdigest()
    proof = receipt["continuityProof"]
    assert proof["verifiedBeforeAndAfterRoleChange"] is True
    assert proof["schemaSha256"]
    assert proof["rows"]["langchain_pg_collection"]["rowCount"] == 1
    assert proof["rows"]["langchain_pg_collection"]["sha256"]
    assert proof["rows"]["langchain_pg_embedding"]["rowCount"] == 1
    assert proof["rows"]["langchain_pg_embedding"]["sha256"]
    assert "synthetic-document" not in receipt_text
    assert "public-safe-qa" not in receipt_text
    assert not (state_dir / "migration-pending.json").exists()

    assert docker.alter_inputs == [
        f"ALTER ROLE myuser WITH LOGIN PASSWORD '{password}';\n"
    ]
    assert all(
        "--username" in call["args"]
        and call["args"][call["args"].index("--username") + 1] == "myuser"
        for call in docker.calls
        if call["args"][:1] == ["exec"] and "psql" in call["args"]
    )
    assert all(
        forbidden not in "\n".join(docker.alter_inputs).upper()
        for forbidden in ("DROP TABLE", "TRUNCATE", "DELETE FROM", "UPDATE LANGCHAIN")
    )
    compose_up = next(
        call
        for call in docker.calls
        if call["args"][-3:] == ["up", "-d", "vectordb"]
    )
    assert compose_up["env"]["POSTGRES_PASSWORD"] == password


def test_row_fingerprint_drift_during_role_reconciliation_fails_closed(
    migration_paths: tuple[Path, Path, Path],
) -> None:
    compose_file, pgdata_path, state_dir = migration_paths
    docker = FakeDocker(pgdata_path=pgdata_path, drift_after_alter=True)

    with pytest.raises(
        rag_postgres_migration.MigrationError,
        match="row continuity changed",
    ):
        _run_migration(
            compose_file=compose_file,
            pgdata_path=pgdata_path,
            state_dir=state_dir,
            docker=docker,
        )

    assert docker.alter_inputs
    assert (state_dir / "migration-pending.json").is_file()
    assert not (state_dir / "migration-receipt.json").exists()


def test_rerun_reuses_the_same_credential_and_receipt_identity(
    migration_paths: tuple[Path, Path, Path],
) -> None:
    compose_file, pgdata_path, state_dir = migration_paths
    first_docker = FakeDocker(pgdata_path=pgdata_path)
    first = _run_migration(
        compose_file=compose_file,
        pgdata_path=pgdata_path,
        state_dir=state_dir,
        docker=first_docker,
    )
    first_password = first.credential_path.read_text(encoding="ascii")
    first_receipt = first.receipt_path.read_bytes()

    second_docker = FakeDocker(pgdata_path=pgdata_path)
    second = _run_migration(
        compose_file=compose_file,
        pgdata_path=pgdata_path,
        state_dir=state_dir,
        docker=second_docker,
    )

    assert second.credential_path.read_text(encoding="ascii") == first_password
    assert second.receipt_path.read_bytes() == first_receipt
    assert first_password.strip() in second_docker.alter_inputs[0]


@pytest.mark.parametrize(
    "relations",
    [
        [{"schema": "public", "name": "unrelated_customer_table", "kind": "r"}],
        [LEGACY_RELATIONS[0]],
        [
            *LEGACY_RELATIONS,
            {"schema": "private", "name": "foreign_table", "kind": "r"},
        ],
    ],
)
def test_unknown_or_partial_pgdata_fails_closed_before_role_mutation(
    migration_paths: tuple[Path, Path, Path],
    relations: list[dict[str, str]],
) -> None:
    compose_file, pgdata_path, state_dir = migration_paths
    docker = FakeDocker(pgdata_path=pgdata_path, relations=relations)

    with pytest.raises(
        rag_postgres_migration.MigrationError,
        match="recognized Viventium RAG schema",
    ):
        _run_migration(
            compose_file=compose_file,
            pgdata_path=pgdata_path,
            state_dir=state_dir,
            docker=docker,
        )

    assert docker.alter_inputs == []
    assert not (state_dir / "migration-receipt.json").exists()


@pytest.mark.parametrize(
    ("database_owner", "role_oid", "database_oid"),
    [
        (None, "16384", "16385"),
        ("other_user", "16384", "16385"),
        ("myuser", None, "16385"),
        ("myuser", "16384", None),
    ],
)
def test_missing_or_foreign_database_identity_fails_closed(
    migration_paths: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    database_owner: str | None,
    role_oid: str | None,
    database_oid: str | None,
) -> None:
    compose_file, pgdata_path, state_dir = migration_paths
    docker = FakeDocker(
        pgdata_path=pgdata_path,
        database_owner=database_owner,
        role_oid=role_oid,
        database_oid=database_oid,
    )
    monkeypatch.setenv("VIVENTIUM_RAG_POSTGRES_READY_RETRIES", "1")

    with pytest.raises(rag_postgres_migration.MigrationError, match="database identity"):
        _run_migration(
            compose_file=compose_file,
            pgdata_path=pgdata_path,
            state_dir=state_dir,
            docker=docker,
        )

    assert docker.alter_inputs == []


def test_mount_mismatch_fails_closed_and_restores_initial_stopped_state(
    migration_paths: tuple[Path, Path, Path],
) -> None:
    compose_file, pgdata_path, state_dir = migration_paths
    docker = FakeDocker(
        pgdata_path=pgdata_path,
        mount_source=str(pgdata_path.parent / "foreign-pgdata"),
    )

    with pytest.raises(rag_postgres_migration.MigrationError, match="PGDATA mount"):
        _run_migration(
            compose_file=compose_file,
            pgdata_path=pgdata_path,
            state_dir=state_dir,
            docker=docker,
        )

    assert docker.alter_inputs == []
    assert any(call["args"][-2:] == ["stop", "vectordb"] for call in docker.calls)


def test_pending_journal_recovers_after_interruption_without_rotating_secret(
    migration_paths: tuple[Path, Path, Path],
) -> None:
    compose_file, pgdata_path, state_dir = migration_paths
    failed_docker = FakeDocker(pgdata_path=pgdata_path, fail_alter=True)

    with pytest.raises(
        rag_postgres_migration.MigrationError,
        match="credential reconciliation failed",
    ) as error:
        _run_migration(
            compose_file=compose_file,
            pgdata_path=pgdata_path,
            state_dir=state_dir,
            docker=failed_docker,
        )
    password = (state_dir / "postgres-password").read_text(encoding="ascii").strip()
    assert password not in str(error.value)
    assert (state_dir / "migration-pending.json").is_file()
    assert not (state_dir / "migration-receipt.json").exists()

    recovered_docker = FakeDocker(pgdata_path=pgdata_path)
    recovered = _run_migration(
        compose_file=compose_file,
        pgdata_path=pgdata_path,
        state_dir=state_dir,
        docker=recovered_docker,
    )

    assert recovered.credential_path.read_text(encoding="ascii").strip() == password
    assert not (state_dir / "migration-pending.json").exists()
    assert recovered.receipt_path.is_file()


def test_receipt_without_credential_fails_before_starting_docker(
    migration_paths: tuple[Path, Path, Path],
) -> None:
    compose_file, pgdata_path, state_dir = migration_paths
    state_dir.mkdir(parents=True, mode=0o700)
    (state_dir / "migration-receipt.json").write_text(
        json.dumps({"schemaVersion": 1, "status": "ready"}),
        encoding="utf-8",
    )
    os.chmod(state_dir / "migration-receipt.json", 0o600)
    docker = FakeDocker(pgdata_path=pgdata_path)

    with pytest.raises(
        rag_postgres_migration.MigrationError,
        match="credential file is missing",
    ):
        _run_migration(
            compose_file=compose_file,
            pgdata_path=pgdata_path,
            state_dir=state_dir,
            docker=docker,
        )

    assert docker.calls == []


def test_fresh_empty_pgdata_is_adopted_without_legacy_schema(
    migration_paths: tuple[Path, Path, Path],
) -> None:
    compose_file, pgdata_path, state_dir = migration_paths
    docker = FakeDocker(pgdata_path=pgdata_path, relations=[])

    result = _run_migration(
        compose_file=compose_file,
        pgdata_path=pgdata_path,
        state_dir=state_dir,
        docker=docker,
    )

    assert result.status == "ready"
    assert docker.alter_inputs


def test_receipt_allows_only_the_normal_fresh_to_initialized_schema_transition(
    migration_paths: tuple[Path, Path, Path],
) -> None:
    compose_file, pgdata_path, state_dir = migration_paths
    fresh_docker = FakeDocker(pgdata_path=pgdata_path, relations=[])
    fresh = _run_migration(
        compose_file=compose_file,
        pgdata_path=pgdata_path,
        state_dir=state_dir,
        docker=fresh_docker,
    )
    fresh_receipt = json.loads(fresh.receipt_path.read_text(encoding="utf-8"))
    assert fresh_receipt["cluster"]["schemaClass"] == "fresh"

    initialized_docker = FakeDocker(pgdata_path=pgdata_path, relations=LEGACY_RELATIONS)
    initialized = _run_migration(
        compose_file=compose_file,
        pgdata_path=pgdata_path,
        state_dir=state_dir,
        docker=initialized_docker,
    )
    initialized_receipt = json.loads(initialized.receipt_path.read_text(encoding="utf-8"))
    assert initialized_receipt["cluster"]["schemaClass"] == "legacy-rag"
    assert (
        initialized.credential_path.read_bytes()
        == fresh.credential_path.read_bytes()
    )

    regressed_docker = FakeDocker(pgdata_path=pgdata_path, relations=[])
    with pytest.raises(
        rag_postgres_migration.MigrationError,
        match="receipt does not match",
    ):
        _run_migration(
            compose_file=compose_file,
            pgdata_path=pgdata_path,
            state_dir=state_dir,
            docker=regressed_docker,
        )
    assert regressed_docker.alter_inputs == []


def test_postgres_readiness_is_retried_before_cluster_inspection(
    migration_paths: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    compose_file, pgdata_path, state_dir = migration_paths
    docker = FakeDocker(pgdata_path=pgdata_path, readiness_failures=2)
    monkeypatch.setattr(rag_postgres_migration.time, "sleep", lambda _seconds: None)

    result = _run_migration(
        compose_file=compose_file,
        pgdata_path=pgdata_path,
        state_dir=state_dir,
        docker=docker,
    )

    readiness_calls = [
        call
        for call in docker.calls
        if call["args"][:1] == ["exec"] and "pg_isready" in call["args"]
    ]
    assert result.status == "ready"
    assert len(readiness_calls) == 3


def test_fresh_image_restart_race_retries_the_identity_query(
    migration_paths: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    compose_file, pgdata_path, state_dir = migration_paths
    docker = FakeDocker(pgdata_path=pgdata_path, relations=[], identity_failures=2)
    monkeypatch.setattr(rag_postgres_migration.time, "sleep", lambda _seconds: None)

    result = _run_migration(
        compose_file=compose_file,
        pgdata_path=pgdata_path,
        state_dir=state_dir,
        docker=docker,
    )

    identity_calls = [
        call
        for call in docker.calls
        if call["args"][:1] == ["exec"]
        and isinstance(call["input"], str)
        and "pg_control_system" in call["input"]
    ]
    assert result.status == "ready"
    # Two failed preflight attempts, the successful baseline, and the required
    # post-ALTER identity/schema/row continuity verification.
    assert len(identity_calls) == 4


def test_launcher_reconciles_rag_postgres_before_full_rag_compose_start() -> None:
    source = LAUNCHER_PATH.read_text(encoding="utf-8")
    assert "prepare_rag_postgres_credentials() {" in source
    function_block = source.split("prepare_rag_postgres_credentials() {", 1)[1].split(
        "prepare_rag_document_route_path() {", 1
    )[0]
    start_block = source.split("_start_rag_api_locked() {", 1)[1].split(
        "start_rag_api() {", 1
    )[0]

    assert "$VIVENTIUM_CORE_DIR/scripts/viventium/rag_postgres_migration.py" in function_block
    assert "--compose-file" in function_block
    assert "--project-name" in function_block
    assert "--pgdata-path" in function_block
    assert "--pgdata-path-mode" in function_block
    assert "VIVENTIUM_RAG_POSTGRES_STATE_DIR" in function_block
    assert 'IFS= read -r postgres_password <"$credential_file"' in function_block
    assert "export POSTGRES_PASSWORD" in function_block
    assert "upsert_env_kv" not in function_block
    assert "prepare_rag_postgres_credentials" in start_block
    assert start_block.index("prepare_rag_postgres_credentials") < start_block.index(
        "local rag_compose_up_timeout"
    )


def test_launcher_never_logs_or_persists_the_rag_postgres_password() -> None:
    source = LAUNCHER_PATH.read_text(encoding="utf-8")
    function_block = source.split("prepare_rag_postgres_credentials() {", 1)[1].split(
        "prepare_rag_document_route_path() {", 1
    )[0]

    assert 'printf \'%s\\n\' "$postgres_password"' not in function_block
    assert 'echo "$postgres_password"' not in function_block
    assert 'upsert_env_kv "$LIBRECHAT_RUNTIME_ENV_FILE" "POSTGRES_PASSWORD"' not in source

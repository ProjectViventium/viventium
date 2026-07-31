from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import pytest

from scripts.viventium import rag_postgres_migration


pytestmark = pytest.mark.skipif(
    os.environ.get("VIVENTIUM_RUN_DOCKER_RAG_MIGRATION_QA") != "1",
    reason="set VIVENTIUM_RUN_DOCKER_RAG_MIGRATION_QA=1 for disposable Docker QA",
)


PGVECTOR_IMAGE = "pgvector/pgvector:0.8.0-pg15-trixie"
RAG_API_IMAGE = (
    "registry.librechat.ai/danny-avila/librechat-rag-api-dev:latest"
    "@sha256:c3e1a05bdd576b5000fa0e8a84a476e9858fa9219b2b5d78432ddce12c9fcf23"
)


def _run(
    args: list[str],
    *,
    input_text: str | None = None,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        input=input_text,
        text=True,
        capture_output=True,
        check=check,
        env={**os.environ, **(env or {})},
        timeout=180,
    )


def _compose(
    compose_file: Path,
    project_name: str,
    *tail: str,
    password: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return _run(
        [
            "docker",
            "compose",
            "--project-name",
            project_name,
            "-f",
            str(compose_file),
            *tail,
        ],
        env={"POSTGRES_PASSWORD": password},
        check=check,
    )


def _container_id(compose_file: Path, project_name: str, password: str) -> str:
    completed = _compose(
        compose_file,
        project_name,
        "ps",
        "-q",
        "vectordb",
        password=password,
    )
    container_id = completed.stdout.strip()
    assert container_id
    return container_id


def _local_psql(container_id: str, database: str, sql: str) -> str:
    completed = _run(
        [
            "docker",
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
            "myuser",
            "--dbname",
            database,
        ],
        input_text=sql,
    )
    return completed.stdout.strip()


def _tcp_password_probe(project_name: str, password: str) -> int:
    completed = _run(
        [
            "docker",
            "run",
            "--rm",
            "-i",
            "--network",
            f"{project_name}_default",
            "--entrypoint",
            "sh",
            PGVECTOR_IMAGE,
            "-c",
            (
                "IFS= read -r PGPASSWORD; export PGPASSWORD; "
                "exec psql --no-psqlrc --no-align --tuples-only --quiet "
                "--host vectordb --username myuser --dbname mydatabase "
                "--command 'SELECT 1'"
            ),
        ],
        input_text=password + "\n",
        check=False,
    )
    return completed.returncode


def test_disposable_legacy_pgdata_keeps_vector_rows_and_adopts_stable_password(
    tmp_path: Path,
) -> None:
    compose_file = tmp_path / "rag-migration-compose.yml"
    pgdata_path = tmp_path / "rag-pgdata"
    state_dir = tmp_path / "state" / "rag-postgres"
    project_name = f"viventium-rag-migration-qa-{os.getpid()}"
    legacy_password = "legacy-synthetic-password"
    pgdata_path.mkdir()
    compose_file.write_text(
        f"""
services:
  vectordb:
    image: {PGVECTOR_IMAGE}
    environment:
      POSTGRES_DB: mydatabase
      POSTGRES_USER: myuser
      POSTGRES_PASSWORD: ${{POSTGRES_PASSWORD}}
    healthcheck:
      test: ['CMD-SHELL', 'pg_isready -U myuser -d mydatabase']
      interval: 1s
      timeout: 2s
      retries: 60
    volumes:
      - type: bind
        source: {pgdata_path}
        target: /var/lib/postgresql/data
""".lstrip(),
        encoding="utf-8",
    )

    try:
        _compose(
            compose_file,
            project_name,
            "up",
            "-d",
            "--wait",
            "vectordb",
            password=legacy_password,
        )
        legacy_container = _container_id(compose_file, project_name, legacy_password)
        _local_psql(
            legacy_container,
            "mydatabase",
            """
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE langchain_pg_collection (
  uuid uuid PRIMARY KEY,
  name text NOT NULL
);
CREATE TABLE langchain_pg_embedding (
  uuid uuid PRIMARY KEY,
  collection_id uuid NOT NULL REFERENCES langchain_pg_collection(uuid),
  custom_id text,
  cmetadata jsonb,
  embedding vector(3)
);
INSERT INTO langchain_pg_collection(uuid, name)
VALUES ('00000000-0000-0000-0000-000000000001', 'synthetic');
INSERT INTO langchain_pg_embedding(uuid, collection_id, custom_id, cmetadata, embedding)
VALUES (
  '00000000-0000-0000-0000-000000000002',
  '00000000-0000-0000-0000-000000000001',
  'synthetic-document',
  '{"scope":"public-safe-qa"}',
  '[1,2,3]'
);
""".lstrip(),
        )
        original_system_identifier = _local_psql(
            legacy_container,
            "postgres",
            "SELECT system_identifier FROM pg_control_system();\n",
        )
        assert _local_psql(
            legacy_container,
            "mydatabase",
            "SELECT count(*) FROM langchain_pg_embedding;\n",
        ) == "1"
        _compose(
            compose_file,
            project_name,
            "down",
            password=legacy_password,
        )

        result = rag_postgres_migration.migrate_rag_postgres(
            compose_file=compose_file,
            project_name=project_name,
            pgdata_path=pgdata_path,
            pgdata_path_mode="host",
            state_dir=state_dir,
        )
        migrated_container = _container_id(
            compose_file,
            project_name,
            result.credential_path.read_text(encoding="ascii").strip(),
        )
        stable_password = result.credential_path.read_text(encoding="ascii").strip()

        assert (
            _local_psql(
                migrated_container,
                "postgres",
                "SELECT system_identifier FROM pg_control_system();\n",
            )
            == original_system_identifier
        )
        assert _local_psql(
            migrated_container,
            "mydatabase",
            "SELECT count(*) FROM langchain_pg_embedding;\n",
        ) == "1"
        assert _tcp_password_probe(project_name, stable_password) == 0
        assert _tcp_password_probe(project_name, legacy_password) != 0

        rerun = rag_postgres_migration.migrate_rag_postgres(
            compose_file=compose_file,
            project_name=project_name,
            pgdata_path=pgdata_path,
            pgdata_path_mode="host",
            state_dir=state_dir,
        )
        assert rerun.credential_path.read_text(encoding="ascii").strip() == stable_password
        assert _local_psql(
            migrated_container,
            "mydatabase",
            "SELECT count(*) FROM langchain_pg_embedding;\n",
        ) == "1"

        _local_psql(
            migrated_container,
            "mydatabase",
            "CREATE TABLE unrelated_foreign_table(id integer PRIMARY KEY);\n",
        )
        with pytest.raises(
            rag_postgres_migration.MigrationError,
            match="recognized Viventium RAG schema",
        ):
            rag_postgres_migration.migrate_rag_postgres(
                compose_file=compose_file,
                project_name=project_name,
                pgdata_path=pgdata_path,
                pgdata_path_mode="host",
                state_dir=state_dir,
            )
        assert _local_psql(
            migrated_container,
            "mydatabase",
            "SELECT count(*) FROM langchain_pg_embedding;\n",
        ) == "1"
    finally:
        _compose(
            compose_file,
            project_name,
            "down",
            "--remove-orphans",
            password=legacy_password,
            check=False,
        )


def test_pinned_rag_api_initializes_only_the_recognized_relation_set(
    tmp_path: Path,
) -> None:
    compose_file = tmp_path / "rag-image-schema-compose.yml"
    pgdata_path = tmp_path / "rag-pgdata"
    state_dir = tmp_path / "state" / "rag-postgres"
    project_name = f"viventium-rag-image-schema-qa-{os.getpid()}"
    pgdata_path.mkdir()
    compose_file.write_text(
        f"""
services:
  vectordb:
    image: {PGVECTOR_IMAGE}
    environment:
      POSTGRES_DB: mydatabase
      POSTGRES_USER: myuser
      POSTGRES_PASSWORD: ${{POSTGRES_PASSWORD}}
    healthcheck:
      test: ['CMD-SHELL', 'pg_isready -U myuser -d mydatabase']
      interval: 1s
      timeout: 2s
      retries: 60
    volumes:
      - type: bind
        source: {pgdata_path}
        target: /var/lib/postgresql/data
  rag_api:
    image: {RAG_API_IMAGE}
    environment:
      DB_HOST: vectordb
      DB_PORT: 5432
      POSTGRES_DB: mydatabase
      POSTGRES_USER: myuser
      POSTGRES_PASSWORD: ${{POSTGRES_PASSWORD}}
      OPENAI_API_KEY: synthetic-not-a-real-key
    depends_on:
      vectordb:
        condition: service_healthy
""".lstrip(),
        encoding="utf-8",
    )

    try:
        result = rag_postgres_migration.migrate_rag_postgres(
            compose_file=compose_file,
            project_name=project_name,
            pgdata_path=pgdata_path,
            pgdata_path_mode="host",
            state_dir=state_dir,
        )
        stable_password = result.credential_path.read_text(encoding="ascii").strip()
        _compose(
            compose_file,
            project_name,
            "up",
            "-d",
            "rag_api",
            password=stable_password,
        )
        container_id = _container_id(compose_file, project_name, stable_password)

        relation_names: set[str] = set()
        for _attempt in range(30):
            output = _local_psql(
                container_id,
                "mydatabase",
                """
SELECT n.nspname || '.' || c.relname
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
  AND n.nspname NOT LIKE 'pg_toast%'
  AND c.relkind IN ('r', 'p', 'v', 'm', 'f', 'S')
ORDER BY 1;
""".lstrip(),
            )
            relation_names = set(output.splitlines()) if output else set()
            if relation_names:
                break
            time.sleep(1)

        assert relation_names == {
            "public.langchain_pg_collection",
            "public.langchain_pg_embedding",
        }
        _compose(
            compose_file,
            project_name,
            "stop",
            "rag_api",
            password=stable_password,
        )
        promoted = rag_postgres_migration.migrate_rag_postgres(
            compose_file=compose_file,
            project_name=project_name,
            pgdata_path=pgdata_path,
            pgdata_path_mode="host",
            state_dir=state_dir,
        )
        assert promoted.credential_path.read_text(encoding="ascii").strip() == stable_password
    finally:
        _compose(
            compose_file,
            project_name,
            "down",
            "--remove-orphans",
            password="synthetic-cleanup-value",
            check=False,
        )

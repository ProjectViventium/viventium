from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
RAG_COMPOSE = REPO_ROOT / "viventium_v0_4" / "LibreChat" / "rag.yml"


def test_rag_compose_caps_local_resource_defaults() -> None:
    compose_text = RAG_COMPOSE.read_text(encoding="utf-8")
    compose = yaml.safe_load(compose_text)

    assert "image: pgvector/pgvector:0.8.0-pg15-trixie" in compose_text
    assert "image: registry.librechat.ai/danny-avila/librechat-rag-api-dev:latest" in compose_text

    assert "mem_limit: ${VIVENTIUM_RAG_VECTORDB_MEM_LIMIT:-512m}" in compose_text
    assert "cpus: ${VIVENTIUM_RAG_VECTORDB_CPUS:-0.50}" in compose_text
    assert "pids_limit: ${VIVENTIUM_RAG_VECTORDB_PIDS_LIMIT:-96}" in compose_text

    assert "mem_limit: ${VIVENTIUM_RAG_API_MEM_LIMIT:-1536m}" in compose_text
    assert "cpus: ${VIVENTIUM_RAG_API_CPUS:-1.00}" in compose_text
    assert "pids_limit: ${VIVENTIUM_RAG_API_PIDS_LIMIT:-160}" in compose_text
    assert (
        "VIVENTIUM_RAG_OLLAMA_KEEP_ALIVE_SECONDS="
        "${VIVENTIUM_RAG_OLLAMA_KEEP_ALIVE_SECONDS:-300}" in compose_text
    )

    for service_name in ("vectordb", "rag_api"):
        logging_options = compose["services"][service_name]["logging"]["options"]
        assert logging_options["max-size"] == "${VIVENTIUM_RAG_LOG_MAX_SIZE:-5m}"
        assert logging_options["max-file"] == "${VIVENTIUM_RAG_LOG_MAX_FILE:-3}"
    assert "127.0.0.1:${VIVENTIUM_RAG_VECTORDB_HOST_PORT:-5433}:5432" in compose[
        "services"
    ]["vectordb"]["ports"]
    assert "127.0.0.1:${RAG_PORT:-8000}:${RAG_PORT:-8000}" in compose["services"][
        "rag_api"
    ]["ports"]


def test_rag_compose_document_override_is_portable_and_keeps_selected_tree_default() -> None:
    compose_text = RAG_COMPOSE.read_text(encoding="utf-8")
    compose = yaml.safe_load(compose_text)
    volumes = compose["services"]["rag_api"]["volumes"]

    expected = {
        "type": "bind",
        "source": (
            "${VIVENTIUM_RAG_DOCUMENT_ROUTE_PATH:-"
            "./viventium/rag_api_overrides/app/routes/document_routes.py}"
        ),
        "target": "/app/app/routes/document_routes.py",
        "read_only": True,
    }
    assert expected in volumes
    assert "/" + "Users" + "/" not in compose_text
    assert "/Volumes/" not in compose_text


def test_rag_compose_pgdata_uses_portable_long_bind_syntax() -> None:
    compose_text = RAG_COMPOSE.read_text(encoding="utf-8")
    compose = yaml.safe_load(compose_text)

    assert {
        "type": "bind",
        "source": "${VIVENTIUM_RAG_PGDATA_PATH:-./.rag-pgdata}",
        "target": "/var/lib/postgresql/data",
    } in compose["services"]["vectordb"]["volumes"]
    assert "host-owned by default" in compose_text
    assert "daemon-owned" in compose_text

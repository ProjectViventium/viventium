from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
FIRECRAWL_COMPOSE = (
    REPO_ROOT / "viventium_v0_4" / "docker" / "firecrawl" / "docker-compose.yml"
)
SEARXNG_COMPOSE = (
    REPO_ROOT / "viventium_v0_4" / "docker" / "searxng" / "docker-compose.yml"
)


def test_firecrawl_local_compose_uses_single_user_resource_defaults() -> None:
    compose_text = FIRECRAWL_COMPOSE.read_text(encoding="utf-8")

    assert "rabbitmq:3-management" not in compose_text
    assert "image: rabbitmq:3-alpine" in compose_text
    assert 'shm_size: "256m"' in compose_text
    assert "LOGGING_LEVEL=${FIRECRAWL_LOG_LEVEL:-warn}" in compose_text
    assert (
        "firecrawl-api" in compose_text
        and "mem_limit: ${FIRECRAWL_API_MEM_LIMIT:-1536m}" in compose_text
    )
    assert (
        "firecrawl-playwright" in compose_text
        and "mem_limit: ${FIRECRAWL_PLAYWRIGHT_MEM_LIMIT:-768m}" in compose_text
    )
    assert "firecrawl-redis" in compose_text and "mem_limit: 128m" in compose_text
    assert "firecrawl-rabbitmq" in compose_text and "mem_limit: 256m" in compose_text
    assert "firecrawl-postgres" in compose_text and "mem_limit: 256m" in compose_text
    assert 'max-size: "${FIRECRAWL_LOG_MAX_SIZE:-5m}"' in compose_text
    assert 'max-file: "${FIRECRAWL_LOG_MAX_FILE:-3}"' in compose_text
    assert "cpus: ${FIRECRAWL_API_CPUS:-0.80}" in compose_text
    assert "cpus: ${FIRECRAWL_PLAYWRIGHT_CPUS:-0.65}" in compose_text
    assert "pids_limit: ${FIRECRAWL_API_PIDS_LIMIT:-256}" in compose_text
    assert "pids_limit: ${FIRECRAWL_PLAYWRIGHT_PIDS_LIMIT:-192}" in compose_text


def test_searxng_local_compose_caps_resource_defaults() -> None:
    compose_text = SEARXNG_COMPOSE.read_text(encoding="utf-8")

    assert "mem_limit: ${SEARXNG_VALKEY_MEM_LIMIT:-128m}" in compose_text
    assert "mem_limit: ${SEARXNG_MEM_LIMIT:-384m}" in compose_text
    assert "cpus: ${SEARXNG_VALKEY_CPUS:-0.20}" in compose_text
    assert "cpus: ${SEARXNG_CPUS:-0.50}" in compose_text
    assert "pids_limit: ${SEARXNG_VALKEY_PIDS_LIMIT:-64}" in compose_text
    assert "pids_limit: ${SEARXNG_PIDS_LIMIT:-128}" in compose_text
    assert 'max-size: "1m"' in compose_text
    assert 'max-file: "1"' in compose_text

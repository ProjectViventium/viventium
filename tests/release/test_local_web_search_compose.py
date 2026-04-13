from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
FIRECRAWL_COMPOSE = (
    REPO_ROOT / "viventium_v0_4" / "docker" / "firecrawl" / "docker-compose.yml"
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

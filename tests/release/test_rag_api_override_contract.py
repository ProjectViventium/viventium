from __future__ import annotations

import os
from pathlib import Path
import subprocess

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
OVERRIDE_PATH = (
    REPO_ROOT
    / "viventium_v0_4"
    / "LibreChat"
    / "viventium"
    / "rag_api_overrides"
    / "app"
    / "routes"
    / "document_routes.py"
)
LAUNCHER_PATH = REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh"
RAG_COMPOSE_PATH = REPO_ROOT / "viventium_v0_4" / "LibreChat" / "rag.yml"


def test_rag_override_uses_config_compatibility_fallback_for_embedding_chunk_size() -> None:
    source = OVERRIDE_PATH.read_text(encoding="utf-8")
    import_block = source.split("from app.config import (", 1)[1].split(")\n", 1)[0]

    assert "import app.config as rag_config" in source
    assert "EMBEDDINGS_CHUNK_SIZE = getattr(" in source
    assert '"EMBEDDINGS_CHUNK_SIZE"' in source
    assert '"EMBEDDING_BATCH_SIZE"' in source
    assert "EMBEDDINGS_CHUNK_SIZE" not in import_block


def test_rag_override_caps_ollama_embedding_keep_alive() -> None:
    source = OVERRIDE_PATH.read_text(encoding="utf-8")

    assert "VIVENTIUM_RAG_OLLAMA_KEEP_ALIVE_SECONDS_ENV" in source
    assert "DEFAULT_VIVENTIUM_RAG_OLLAMA_KEEP_ALIVE_SECONDS = 300" in source
    assert "configure_ollama_embedding_keep_alive()" in source
    assert "embedding_function.keep_alive = keep_alive_seconds" in source
    assert "Negative %s=%s would keep Ollama models resident indefinitely" in source


def test_launcher_recreates_rag_sidecar_when_host_port_binding_is_missing() -> None:
    source = LAUNCHER_PATH.read_text(encoding="utf-8")

    assert "rag_api_container_needs_recreate()" in source
    assert 'docker port "$container_id" "${port}/tcp"' in source
    assert "Local RAG API container is missing the expected localhost:${rag_port} port binding" in source
    assert "rag_compose_args+=(--force-recreate rag_api)" in source


def test_rag_health_returns_real_503_instead_of_fastapi_tuple_body() -> None:
    source = OVERRIDE_PATH.read_text(encoding="utf-8")
    health_block = source.split('@router.get("/health")', 1)[1].split(
        '@router.get("/documents"', 1
    )[0]

    assert "from fastapi.responses import JSONResponse" in source
    assert "async def health_check(request: Request):" in health_block
    assert "VIVENTIUM_HEALTH_PROBE_FILE_ID" in health_block
    assert "get_filtered_ids" in health_block
    assert "JSONResponse(" in health_block
    assert "status_code=status.HTTP_503_SERVICE_UNAVAILABLE" in health_block
    assert 'return {"status": "DOWN"}, 503' not in health_block


def test_rag_health_does_not_expose_internal_exception_details() -> None:
    source = OVERRIDE_PATH.read_text(encoding="utf-8")
    health_block = source.split('@router.get("/health")', 1)[1].split(
        '@router.get("/documents"', 1
    )[0]

    assert 'content={"status": "DOWN", "error": str(e)}' not in health_block
    assert '"error": "vector_store_unavailable"' in health_block


def _rag_ping_result(payload: str) -> subprocess.CompletedProcess[str]:
    source = LAUNCHER_PATH.read_text(encoding="utf-8")
    start = source.index("rag_api_http_ping() {")
    end = source.index("\n}\n\nrag_api_container_needs_recreate()", start) + 3
    function_source = source[start:end]
    script = f"""
set +e
PYTHON_BIN={subprocess.list2cmdline(['/usr/bin/python3'])}
curl() {{ printf '%s' "$RAG_PAYLOAD"; }}
{function_source}
rag_api_http_ping 8000
"""
    return subprocess.run(
        ["/bin/bash", "-c", script],
        text=True,
        capture_output=True,
        env={**os.environ, "RAG_PAYLOAD": payload},
        check=False,
    )


def _launcher_slice(start_marker: str, end_marker: str) -> str:
    source = LAUNCHER_PATH.read_text(encoding="utf-8")
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[start:end]


def test_launcher_rag_ping_requires_semantic_up_status() -> None:
    assert _rag_ping_result('{"status":"UP"}').returncode == 0
    assert _rag_ping_result('{"status":"DOWN"}').returncode != 0
    assert _rag_ping_result('[{"status":"DOWN"},503]').returncode != 0
    assert _rag_ping_result('not-json').returncode != 0


def test_rag_compose_waits_for_vectordb_readiness() -> None:
    payload = yaml.safe_load(RAG_COMPOSE_PATH.read_text(encoding="utf-8"))
    services = payload["services"]

    assert "healthcheck" in services["vectordb"]
    assert "pg_isready" in " ".join(services["vectordb"]["healthcheck"]["test"])
    assert services["rag_api"]["depends_on"]["vectordb"]["condition"] == "service_healthy"
    assert "healthcheck" in services["rag_api"]


def test_launcher_serializes_rag_compose_and_stops_on_phantom_state() -> None:
    source = LAUNCHER_PATH.read_text(encoding="utf-8")

    assert "acquire_rag_compose_lock()" in source
    assert 'mkdir "$lock_dir"' in source
    assert "rag_compose_lock_age_seconds()" in source
    assert "VIVENTIUM_RAG_COMPOSE_LOCK_STALE_GRACE_SECONDS" in source
    assert "release_rag_compose_lock" in source
    assert "rag_api_compose_state()" in source
    assert 'VIVENTIUM_RAG_COMPOSE_PROJECT_NAME:-viventium-rag' in source
    assert 'docker compose --project-name "$VIVENTIUM_RAG_COMPOSE_PROJECT_NAME"' in source
    assert 'printf \'phantom\\n\'' in source
    assert "RAG_COMPOSE_UNRECOVERABLE_EXIT" in source
    assert "Docker engine/Compose state is inconsistent" in source
    assert "occupied by an unhealthy service outside the expected Compose binding" in source
    assert "healthy but is not owned by the expected Compose project" in source
    assert 'if [[ "$rag_compose_status" -eq "$RAG_COMPOSE_UNRECOVERABLE_EXIT" ]]' in source


def test_launcher_rag_lock_serializes_and_reclaims_dead_owner(tmp_path: Path) -> None:
    lock_block = _launcher_slice(
        "RAG_COMPOSE_UNRECOVERABLE_EXIT=75",
        "rag_api_http_ping() {",
    )
    script = f"""
set -euo pipefail
VIVENTIUM_APP_SUPPORT_ROOT="$LOCK_ROOT"
VIVENTIUM_RAG_COMPOSE_LOCK_DIR="$LOCK_ROOT/rag-compose.lock"
VIVENTIUM_RAG_COMPOSE_LOCK_STALE_GRACE_SECONDS=1
GUARD="$LOCK_ROOT/guard"
{lock_block}

worker() {{
  acquire_rag_compose_lock 10
  mkdir "$GUARD"
  sleep 0.05
  rmdir "$GUARD"
  release_rag_compose_lock
}}

pids=""
for _index in 1 2 3; do
  worker &
  pids="$pids $!"
done
for worker_pid in $pids; do
  wait "$worker_pid"
done
[[ ! -d "$VIVENTIUM_RAG_COMPOSE_LOCK_DIR" ]]

(
  acquire_rag_compose_lock 1
) &
crashed_owner=$!
wait "$crashed_owner"
recorded_owner="$(cat "$VIVENTIUM_RAG_COMPOSE_LOCK_DIR/pid")"
[[ "$recorded_owner" == "$crashed_owner" ]]
sleep 1
acquire_rag_compose_lock 2
release_rag_compose_lock
[[ ! -d "$VIVENTIUM_RAG_COMPOSE_LOCK_DIR" ]]
"""
    completed = subprocess.run(
        ["/bin/bash", "-c", script],
        text=True,
        capture_output=True,
        env={**os.environ, "LOCK_ROOT": str(tmp_path)},
        check=False,
        timeout=15,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_launcher_rag_compose_state_classification_is_behavioral(tmp_path: Path) -> None:
    state_function = _launcher_slice(
        "rag_api_compose_state() {",
        "rag_api_container_needs_recreate() {",
    )
    (tmp_path / "rag.yml").write_text("services: {}\n", encoding="utf-8")
    script = f"""
set -euo pipefail
LIBRECHAT_DIR="$STATE_ROOT"
VIVENTIUM_RAG_COMPOSE_PROJECT_NAME="viventium-rag"
{state_function}

docker() {{
  if [[ "$1" == "compose" ]]; then
    if [[ "$DOCKER_MODE" == "compose_error" ]]; then
      return 2
    fi
    if [[ "$DOCKER_MODE" != "absent" ]]; then
      printf 'container-id\n'
    fi
    return 0
  fi
  if [[ "$1" == "inspect" ]]; then
    [[ "$DOCKER_MODE" != "phantom" ]]
    return
  fi
  if [[ "$1" == "port" ]]; then
    if [[ "$DOCKER_MODE" == "binding_mismatch" ]]; then
      printf '127.0.0.1:8999\n'
    else
      printf '127.0.0.1:8110\n'
    fi
    return 0
  fi
  return 1
}}

for DOCKER_MODE in compose_error absent phantom binding_mismatch ready; do
  printf '%s=%s\n' "$DOCKER_MODE" "$(rag_api_compose_state "$STATE_ROOT/rag.yml" 8110)"
done
"""
    completed = subprocess.run(
        ["/bin/bash", "-c", script],
        text=True,
        capture_output=True,
        env={**os.environ, "STATE_ROOT": str(tmp_path)},
        check=False,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert completed.stdout.splitlines() == [
        "compose_error=compose_error",
        "absent=absent",
        "phantom=phantom",
        "binding_mismatch=binding_mismatch",
        "ready=ready",
    ]


def test_launcher_rag_phantom_state_returns_unrecoverable_exit(tmp_path: Path) -> None:
    start_function = _launcher_slice(
        "_start_rag_api_locked() {",
        "start_rag_api() {",
    )
    (tmp_path / "rag.yml").write_text("services: {}\n", encoding="utf-8")
    script = f"""
set +e
START_RAG_API=true
SKIP_LIBRECHAT=false
LIBRECHAT_DIR="$STATE_ROOT"
VIVENTIUM_RAG_API_PORT=8110
VIVENTIUM_RAG_COMPOSE_PROJECT_NAME=viventium-rag
RAG_COMPOSE_UNRECOVERABLE_EXIT=75
RESTART_DOCKER_SERVICES=false
docker() {{ return 0; }}
ensure_docker_daemon_for_service() {{ return 0; }}
ensure_ollama_for_rag() {{ return 0; }}
ensure_ollama_embedding_model_for_rag() {{ return 0; }}
rag_api_compose_state() {{ printf 'phantom\n'; }}
log_error() {{ :; }}
log_info() {{ :; }}
log_warn() {{ :; }}
{start_function}
_start_rag_api_locked
status=$?
printf '%s\n' "$status"
exit 0
"""
    completed = subprocess.run(
        ["/bin/bash", "-c", script],
        text=True,
        capture_output=True,
        env={**os.environ, "STATE_ROOT": str(tmp_path)},
        check=False,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert completed.stdout.strip() == "75"

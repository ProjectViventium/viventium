from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "viventium_v0_4" / "viventium-librechat-start.sh"
DOCKER_COMPOSE = ROOT / "viventium_v0_4" / "LibreChat" / "docker-compose.yml"
NATIVE_RUNTIME = ROOT / "scripts" / "viventium" / "native_runtime.py"


def test_source_launcher_owns_a_dedicated_sandpack_origin() -> None:
    source = LAUNCHER.read_text(encoding="utf-8")

    assert "PROFILE_SANDPACK_BUNDLER_PORT=3191" in source
    assert "PROFILE_SANDPACK_BUNDLER_PORT=3091" in source
    assert (
        'export VIVENTIUM_SANDPACK_BUNDLER_PORT="${VIVENTIUM_SANDPACK_BUNDLER_PORT:-${SANDPACK_BUNDLER_LISTEN_PORT:-$PROFILE_SANDPACK_BUNDLER_PORT}}"'
        in source
    )
    assert (
        'export SANDPACK_BUNDLER_LISTEN_HOST="${SANDPACK_BUNDLER_LISTEN_HOST:-127.0.0.1}"'
        in source
    )
    assert 'export SANDPACK_BUNDLER_LISTEN_PORT="$VIVENTIUM_SANDPACK_BUNDLER_PORT"' in source
    assert (
        'export SANDPACK_BUNDLER_URL="${SANDPACK_BUNDLER_URL:-http://127.0.0.1:${VIVENTIUM_SANDPACK_BUNDLER_PORT}/}"'
        in source
    )
    assert (
        'export SANDPACK_STATIC_BUNDLER_URL="${SANDPACK_STATIC_BUNDLER_URL:-$SANDPACK_BUNDLER_URL}"'
        in source
    )
    assert "librechat_sandpack_healthy() {" in source
    assert 'api_pids="$(find_port_listener_pids "$LC_API_PORT")"' in source
    assert 'sandpack_pids="$(find_port_listener_pids "$VIVENTIUM_SANDPACK_BUNDLER_PORT")"' in source
    assert 'librechat_api_http_healthy && librechat_sandpack_healthy' in source
    assert 'kill_port_listeners "$VIVENTIUM_SANDPACK_BUNDLER_PORT" "$LIBRECHAT_DIR"' in source
    assert (
        'wait_for_http "${SANDPACK_BUNDLER_URL}index.html" "Isolated browser artifact runtime"'
        in source
    )
    assert 'Isolated browser runtime:${NC}' in source
    assert '[[ ! -f "$LIBRECHAT_DIR/client/dist/sandpack-bundler/index.html" ]]' in source
    assert "grep -Fq 'IS_ONPREM:\"true\"'" in source


def test_docker_maps_the_api_owned_sandpack_listener() -> None:
    source = DOCKER_COMPOSE.read_text(encoding="utf-8")

    assert '${SANDPACK_BUNDLER_PORT:-3081}:${SANDPACK_BUNDLER_PORT:-3081}' in source
    assert "dockerfile: Dockerfile.multi" in source
    assert "target: api-build" in source
    assert "registry.librechat.ai/danny-avila/librechat-dev:latest" not in source
    assert "SANDPACK_BUNDLER_LISTEN_HOST=0.0.0.0" in source
    assert "SANDPACK_BUNDLER_LISTEN_PORT=${SANDPACK_BUNDLER_PORT:-3081}" in source
    assert "SANDPACK_BUNDLER_URL=${SANDPACK_BUNDLER_URL:-http://localhost:3081/}" in source
    assert "SANDPACK_STATIC_BUNDLER_URL=${SANDPACK_STATIC_BUNDLER_URL:-http://localhost:3081/}" in source


def test_native_sets_only_public_urls_and_keeps_listener_owned_by_proxy() -> None:
    source = NATIVE_RUNTIME.read_text(encoding="utf-8")
    fixed_env = source.split("NATIVE_FIXED_ENV = {", 1)[1].split("}\n", 1)[0]

    assert '"SANDPACK_BUNDLER_URL": "http://127.0.0.1:3191/"' in fixed_env
    assert '"SANDPACK_STATIC_BUNDLER_URL": "http://127.0.0.1:3191/"' in fixed_env
    assert "SANDPACK_BUNDLER_LISTEN_PORT" not in fixed_env

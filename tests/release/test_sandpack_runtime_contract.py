from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import subprocess
import threading
import time

import pytest


ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "viventium_v0_4" / "viventium-librechat-start.sh"
DOCKER_COMPOSE = ROOT / "viventium_v0_4" / "LibreChat" / "docker-compose.yml"
NATIVE_RUNTIME = ROOT / "scripts" / "viventium" / "native_runtime.py"


@pytest.fixture
def sandpack_health_server():
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            mode = self.path.split("/")[1]
            marker = b'IS_ONPREM:"true"\n' if mode != "missing" else b"no marker\n"
            tail = b"artifact-content\n" * 131072
            self.send_response(503 if mode == "http-error" else 200)
            self.send_header("Content-Length", str(len(marker) + len(tail)))
            self.end_headers()
            try:
                self.wfile.write(marker)
                self.wfile.flush()
                # A marker may arrive before the rest of an HTTP response. Health must read both.
                time.sleep(0.02)
                if mode == "truncated":
                    self.close_connection = True
                    return
                self.wfile.write(tail)
            except (BrokenPipeError, ConnectionResetError):
                pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def run_sandpack_health(url):
    source = LAUNCHER.read_text(encoding="utf-8")
    function = "librechat_sandpack_healthy() {" + source.split(
        "librechat_sandpack_healthy() {", 1
    )[1].split("\n}\n", 1)[0] + "\n}\n"
    script = (
        "set -euo pipefail\n"
        + function
        + '\nfind_port_listener_pids() { printf "42\\n"; }\n'
        + 'LC_API_PORT=1\nVIVENTIUM_SANDPACK_BUNDLER_PORT=2\n'
        + 'SANDPACK_BUNDLER_URL="$1/"\n'
        + "if librechat_sandpack_healthy; then exit 0; else exit 1; fi\n"
    )
    return subprocess.run(
        ["bash", "-c", script, "health-contract", url],
        capture_output=True,
        text=True,
        timeout=5,
    )


def test_sandpack_health_consumes_a_healthy_response_under_pipefail(sandpack_health_server):
    result = run_sandpack_health(f"{sandpack_health_server}/healthy")
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("mode", ["missing", "http-error", "truncated"])
def test_sandpack_health_rejects_unhealthy_responses_under_pipefail(sandpack_health_server, mode):
    result = run_sandpack_health(f"{sandpack_health_server}/{mode}")
    assert result.returncode != 0


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
    assert "grep -F 'IS_ONPREM:\"true\"' >/dev/null" in source


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

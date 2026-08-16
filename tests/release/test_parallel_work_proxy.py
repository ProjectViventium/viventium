from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROXY_SOURCE = ROOT / "viventium_v0_4" / "docker" / "parallel-work-proxy" / "proxy.py"
PROXY_DOCKERFILE = ROOT / "viventium_v0_4" / "docker" / "parallel-work-proxy" / "Dockerfile"
PROXY_COMPOSE = ROOT / "viventium_v0_4" / "docker" / "parallel-work-proxy" / "compose.yml"
START_SCRIPT = ROOT / "viventium_v0_4" / "viventium-librechat-start.sh"


def _proxy_module():
    spec = importlib.util.spec_from_file_location("parallel_work_proxy", PROXY_SOURCE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parallel_work_proxy_allows_only_the_exact_role_routes():
    module = _proxy_module()

    assert module.route_for("provider", "/openai/v1/responses") == (
        "/api/viventium/glasshive/providers/openai/v1/responses"
    )
    assert module.route_for("provider", "/anthropic/v1/messages") == (
        "/api/viventium/glasshive/providers/anthropic/v1/messages"
    )
    assert module.route_for("broker", "/mcp") == (
        "/api/viventium/glasshive/capabilities/mcp"
    )
    assert module.route_for("provider", "/openai/v1/files") is None
    assert module.route_for("provider", "http://outside.example/v1/responses") is None
    assert module.route_for("broker", "/api/viventium/glasshive/providers/openai/v1/responses") is None


def test_parallel_work_proxy_forwards_only_reviewed_request_headers():
    module = _proxy_module()

    projected = module.forward_headers(
        {
            "Authorization": "Bearer synthetic-run-grant",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "Anthropic-Version": "2023-06-01",
            "Anthropic-Beta": "synthetic-beta",
            "Cookie": "must-not-forward",
            "X-Forwarded-For": "must-not-forward",
            "Host": "must-not-forward",
        },
        content_length=17,
    )

    assert projected == {
        "Authorization": "Bearer synthetic-run-grant",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "Anthropic-Version": "2023-06-01",
        "Anthropic-Beta": "synthetic-beta",
        "Content-Length": "17",
    }


def test_parallel_work_proxy_uses_explicit_close_framing_for_streamed_responses():
    source = PROXY_SOURCE.read_text(encoding="utf-8")

    assert 'self.send_header("Connection", "close")' in source
    assert "self.close_connection = True" in source


def test_parallel_work_proxy_image_is_nonroot_and_healthchecked():
    dockerfile = PROXY_DOCKERFILE.read_text(encoding="utf-8")

    assert "USER glasshive" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert 'ENTRYPOINT ["python", "/app/proxy.py"]' in dockerfile
    assert "COPY proxy.py /app/proxy.py" in dockerfile


def test_parallel_work_proxy_compose_is_hardened_and_has_no_host_ports():
    compose = PROXY_COMPOSE.read_text(encoding="utf-8")

    assert "provider-egress:" in compose
    assert "capability-broker:" in compose
    assert compose.count("read_only: true") == 2
    assert compose.count("- ALL") >= 2
    assert compose.count("no-new-privileges:true") == 2
    assert "ports:" not in compose
    assert "host.docker.internal:host-gateway" in compose
    assert "internal: true" in compose
    assert "VIVENTIUM_PARALLEL_PROXY_ROLE: provider" in compose
    assert "VIVENTIUM_PARALLEL_PROXY_ROLE: broker" in compose
    assert "VIVENTIUM_PARALLEL_PROXY_UPSTREAM: http://host.docker.internal:${VIVENTIUM_LC_API_PORT}" in compose


def test_parallel_work_broker_proxy_has_the_only_reviewed_host_egress_path():
    compose = PROXY_COMPOSE.read_text(encoding="utf-8")
    broker_service = compose.split("  capability-broker:", 1)[1].split(
        "\nnetworks:", 1
    )[0]

    assert "      egress: {}" in broker_service


def test_launcher_provisions_parallel_proxy_substrate_before_glasshive_runtime():
    launcher = START_SCRIPT.read_text(encoding="utf-8")

    assert "start_parallel_work_proxy_substrate()" in launcher
    start_glasshive = launcher.index("start_glasshive()")
    proxy_call = launcher.index("start_parallel_work_proxy_substrate", start_glasshive)
    runtime_call = launcher.index("uv run uvicorn workers_projects_runtime.api:app", start_glasshive)
    assert proxy_call < runtime_call


def test_launcher_recognizes_compose_up_after_global_project_options():
    launcher = START_SCRIPT.read_text(encoding="utf-8")

    assert '"--project-name"|"-p"|"--file"|"-f"' in launcher
    assert '[[ "$compose_command" == "up" ]]' in launcher
    assert 'timeout_seconds="$compose_up_timeout"' in launcher

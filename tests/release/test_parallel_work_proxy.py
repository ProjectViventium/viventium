from __future__ import annotations

import importlib.util
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROXY_SOURCE = ROOT / "viventium_v0_4" / "docker" / "parallel-work-proxy" / "proxy.py"
PROXY_DOCKERFILE = ROOT / "viventium_v0_4" / "docker" / "parallel-work-proxy" / "Dockerfile"
PROXY_COMPOSE = ROOT / "viventium_v0_4" / "docker" / "parallel-work-proxy" / "compose.yml"
START_SCRIPT = ROOT / "viventium_v0_4" / "viventium-librechat-start.sh"
GLASSHIVE_PROVIDER_SOURCE = (
    ROOT
    / "viventium_v0_4"
    / "GlassHive"
    / "runtime_phase1"
    / "src"
    / "workers_projects_runtime"
    / "conversation_provider.py"
)


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
    assert module.route_for("provider", "/anthropic/v1/messages?beta=true") == (
        "/api/viventium/glasshive/providers/anthropic/v1/messages"
    )
    assert module.route_for("broker", "/mcp") == (
        "/api/viventium/glasshive/capabilities/mcp"
    )
    assert module.route_for("provider", "/openai/v1/files") is None
    assert module.route_for("provider", "/anthropic/v1/messages?beta=false") is None
    assert module.route_for("provider", "/anthropic/v1/messages?beta=true&extra=1") is None
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


def test_parallel_work_proxy_keeps_request_limits_role_scoped():
    module = _proxy_module()
    mib = 1024 * 1024

    assert module.request_body_allowed("provider", 15 * mib) is True
    assert module.request_body_allowed("provider", 15 * mib + 1) is False
    assert module.request_body_allowed("broker", 2 * mib) is True
    assert module.request_body_allowed("broker", 2 * mib + 1) is False


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


def test_launcher_configures_proxy_before_main_and_builds_substrate_in_background():
    launcher = START_SCRIPT.read_text(encoding="utf-8")
    start_glasshive = launcher.index("start_glasshive()")
    runtime_start = launcher[start_glasshive:].split("\n}", 1)[0]
    assert runtime_start.index("configure_parallel_work_proxy_substrate") < runtime_start.index(
        "uv run uvicorn workers_projects_runtime.api:create_app --factory"
    )
    assert "start_parallel_work_proxy_substrate" not in runtime_start
    queued = launcher.split("queue_optional_services_parallel_with_librechat() {", 1)[1].split("\n}", 1)[0]
    assert "queue_parallel_optional_start" in queued
    assert "start_parallel_work_proxy_substrate" in queued


def test_launcher_sets_glasshive_request_head_limit_for_context_headers():
    launcher = START_SCRIPT.read_text(encoding="utf-8")
    provider = GLASSHIVE_PROVIDER_SOURCE.read_text(encoding="utf-8")

    provider_limit = re.search(
        r"^HTTP_REQUEST_HEAD_MAX_BYTES = (?P<count>\d+) \* 1024$",
        provider,
        re.MULTILINE,
    )
    launcher_limit = re.search(
        r'^GLASSHIVE_HTTP_REQUEST_HEAD_MIN_BYTES=(?P<count>\d+)$',
        launcher,
        re.MULTILINE,
    )
    assert provider_limit is not None
    assert launcher_limit is not None
    assert int(launcher_limit.group("count")) == int(provider_limit.group("count")) * 1024
    assert 'GLASSHIVE_HTTP_REQUEST_HEAD_MAX_BYTES="${GLASSHIVE_HTTP_REQUEST_HEAD_MAX_BYTES:-$GLASSHIVE_HTTP_REQUEST_HEAD_MIN_BYTES}"' in launcher
    start_glasshive = launcher.index("start_glasshive()")
    start_glasshive_source = launcher[start_glasshive:].split("\n}", 1)[0]
    runtime_call = start_glasshive_source.split(
        "uv run uvicorn workers_projects_runtime.api:create_app --factory",
        1,
    )[1].split("&", 1)[0]
    validation = start_glasshive_source.index(
        '[[ ! "$GLASSHIVE_HTTP_REQUEST_HEAD_MAX_BYTES" =~ ^(0|[1-9][0-9]*)$ ]]'
    )
    assert '10#$GLASSHIVE_HTTP_REQUEST_HEAD_MAX_BYTES < GLASSHIVE_HTTP_REQUEST_HEAD_MIN_BYTES' in start_glasshive_source
    assert validation < start_glasshive_source.index(
        "uv run uvicorn workers_projects_runtime.api:create_app --factory"
    )
    assert "--http h11" in runtime_call
    assert '--h11-max-incomplete-event-size "$GLASSHIVE_HTTP_REQUEST_HEAD_MAX_BYTES"' in runtime_call


def test_launcher_recognizes_compose_up_after_global_project_options():
    launcher = START_SCRIPT.read_text(encoding="utf-8")

    assert '"--project-name"|"-p"|"--file"|"-f"' in launcher
    assert '[[ "$compose_command" == "up" ]]' in launcher
    assert 'timeout_seconds="$compose_up_timeout"' in launcher

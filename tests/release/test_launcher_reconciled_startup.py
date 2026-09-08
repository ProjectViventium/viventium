"""Startup carries saved latency improvements without bypassing current ownership gates."""
from pathlib import Path
import re
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "viventium_v0_4/viventium-librechat-start.sh"


def function(source: str, name: str) -> str:
    match = re.search(rf"^{name}\(\) \{{\n.*?^\}}\n", source, re.M | re.S)
    assert match
    return match.group()


def shell(code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["bash", "-c", "set -uo pipefail\n" + code], text=True, capture_output=True, timeout=10)


@pytest.mark.parametrize("diagnostic", [
    "[viventium] Failed to create the dedicated Parallel Work Redis container",
    "error during build: optional proxy image",
    "npm error Lifecycle script build failed in optional tooling",
])
def test_typed_startup_contract_ignores_optional_errors_until_core_exits(tmp_path, diagnostic):
    log = tmp_path / "launch.log"
    log.write_text("[viventium] STARTUP_CONTRACT: core-handoff-v1\n" + diagnostic + "\n")
    owner = function((ROOT / "bin/viventium").read_text(), "launch_log_indicates_startup_failure")
    result = shell(f'''{owner}
if launch_log_indicates_startup_failure '{log}'; then exit 10; fi
printf '%s\\n' '[viventium] FATAL_STARTUP: launcher exited before core handoff (status 1)' >> '{log}'
launch_log_indicates_startup_failure '{log}'
''')
    assert result.returncode == 0, result.stderr


def test_typed_contract_survives_long_optional_logs(tmp_path):
    log = tmp_path / "launch.log"
    log.write_text("[viventium] STARTUP_CONTRACT: core-handoff-v1\n" + "optional progress\n" * 20000 + "Build failed in optional tooling\n")
    owner = function((ROOT / "bin/viventium").read_text(), "launch_log_indicates_startup_failure")
    result = shell(f"{owner}\nlaunch_log_indicates_startup_failure '{log}'")
    assert result.returncode == 1, result.stderr


def test_core_fatal_receipt_is_only_emitted_before_handoff():
    cleanup = function(LAUNCHER.read_text(), "cleanup")
    result = shell(f'''{cleanup}
detached_start_requested() {{ return 0; }}
log_error() {{ printf '%s\\n' "$*"; }}
STARTUP_HANDOFF_COMPLETE=false
false; cleanup
STARTUP_HANDOFF_COMPLETE=true
false; cleanup
''')
    assert result.returncode == 0, result.stderr
    assert result.stdout.count("FATAL_STARTUP:") == 1
    assert "status 1" in result.stdout


def test_parent_endpoint_selection_is_pinned_before_background_workers():
    source = LAUNCHER.read_text()
    prepare = function(source, "prepare_optional_mcp_endpoint_overrides")
    result = shell(f'''{prepare}
START_GOOGLE_MCP=true
GOOGLE_MCP_PORT=8111
GOOGLE_MCP_PORT_WAS_DEFAULT=true
GOOGLE_MCP_URLS_WERE_DEFAULT=true
MS365_MCP_CALLBACK_PORT=8112
CODE_INTERPRETER_PORT=8000
START_MS365_MCP=false
port_in_use() {{ return 0; }}
google_mcp_ready() {{ return 1; }}
find_free_port() {{ printf 8113; }}
refresh_google_mcp_urls() {{ GOOGLE_WORKSPACE_MCP_URL="http://localhost:$GOOGLE_MCP_PORT/mcp"; }}
log_warn() {{ :; }}
prepare_optional_mcp_endpoint_overrides
printf '%s:%s:%s' "$GOOGLE_MCP_PORT" "$GOOGLE_WORKSPACE_MCP_URL" "$OPTIONAL_MCP_ENDPOINTS_PREPARED"
''')
    assert result.returncode == 0, result.stderr
    assert result.stdout == "8113:http://localhost:8113/mcp:true"
    google = function(source, "start_google_workspace_mcp")
    ms365 = function(source, "start_ms365_mcp")
    assert '"$OPTIONAL_MCP_ENDPOINTS_PREPARED" != "true"' in google
    assert 'Prepared MS365 MCP port $base_port became occupied before startup' in ms365


def test_initial_optional_work_blocks_recovery_only_while_running():
    owner = function(LAUNCHER.read_text(), "parallel_optional_starts_running")
    result = shell(f'''{owner}
sleep 0.1 &
pid=$!
PARALLEL_OPTIONAL_START_PIDS=("$pid")
parallel_optional_starts_running || exit 10
wait "$pid"
if parallel_optional_starts_running; then exit 11; fi
''')
    assert result.returncode == 0, result.stderr


def test_canonical_uploads_and_full_glasshive_gate_precede_consumers():
    source = LAUNCHER.read_text()
    startup = source[source.index('# MCP Servers\n# ----------------------------'):]
    assert startup.index('prepare_canonical_uploads_before_parallel_services || exit 1') < startup.index('if ! start_glasshive; then') < startup.index('queue_optional_services_parallel_with_librechat')
    owner = function(source, 'start_glasshive')
    assert 'GLASSHIVE_SERVICE_TOPOLOGY' in owner
    assert 'if ! wait_for_glasshive_stack_ready; then' in owner
    assert 'stop_candidate_glasshive_stack' in owner
    assert 'start_parallel_work_proxy_substrate' not in owner
    assert 'configure_parallel_work_proxy_substrate' in owner


@pytest.mark.parametrize("configured,healthy,expected", [("true", "false", 1), ("true", "true", 0), ("false", "false", 0)])
def test_main_readiness_requires_configured_glasshive_identity(configured, healthy, expected):
    owner = function((ROOT / "bin/viventium").read_text(), "all_user_surfaces_healthy")
    result = shell(f"""{owner}
assign_runtime_ports() {{ :; }}
api_surface_healthy() {{ return 0; }}
frontend_surface_healthy() {{ return 0; }}
sandpack_runtime_required() {{ return 1; }}
express_install_experience() {{ return 0; }}
runtime_env_true() {{ [[ {configured} == true ]]; }}
glasshive_runtime_surface_healthy() {{ [[ {healthy} == true ]]; }}
all_user_surfaces_healthy
""")
    assert result.returncode == expected, result.stderr

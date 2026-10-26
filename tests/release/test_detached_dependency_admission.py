"""Detached admission preserves a serving Core when only a dependency needs attention."""
from __future__ import annotations

import os
import re
import shlex
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "bin/viventium"


def cli_function(name: str) -> str:
    source = CLI.read_text()
    start = source.index(name + "() {\n")
    tail = source[start:]
    boundary = re.search(r"\n[A-Za-z_][A-Za-z_0-9]*\(\) \{\n", tail)
    assert boundary is not None
    return tail[:boundary.start()] + "\n"


def detached_launch_function() -> str:
    return cli_function("launch_stack_detached")


@pytest.fixture
def admission_run(tmp_path: Path):
    config = tmp_path / "config.yaml"
    config.write_text("version: 1\n")
    support = tmp_path / "support"
    support.mkdir(mode=0o700)
    effects = tmp_path / "effects.txt"
    flags = tmp_path / "flags.txt"
    preamble = f'''
APP_SUPPORT_DIR={shlex.quote(str(support))}
CONFIG_FILE={shlex.quote(str(config))}
REPO_ROOT={shlex.quote(str(tmp_path / 'repository'))}
LOCK_FILE={shlex.quote(str(tmp_path / 'components.lock.json'))}
RUNTIME_DIR={shlex.quote(str(support / 'runtime'))}
FIXTURE_EFFECTS={shlex.quote(str(effects))}
FIXTURE_FLAGS={shlex.quote(str(flags))}
PYTHON_BIN=record_child_submission
VIVENTIUM_DETACHED_START=false
VIVENTIUM_SUCCESSOR_VALIDATION_MODE=
VIVENTIUM_RUNTIME_PROFILE=isolated
USE_REDIS=true
USE_REDIS_STREAMS=true
ensure_app_support_layout() {{ :; }}
value_is_true() {{ [[ "$1" == true || "$1" == 1 ]]; }}
helper_runtime_intent_allows_start() {{ return 0; }}
initialize_telegram_user_config_authority() {{ return 0; }}
user_surface_healthy() {{ [[ "$FIXTURE_USER_READY" == 1 ]]; }}
runtime_optional_surfaces_healthy() {{ [[ "$FIXTURE_OPTIONAL_READY" == 1 ]]; }}
postcommit_api_finalization_ready() {{ return 0; }}
runtime_start_claim_active() {{ [[ "$FIXTURE_START_CLAIM" == 1 ]]; }}
detached_launch_process_group_running() {{ [[ "$FIXTURE_SERVING_GROUP" == 1 ]]; }}
runtime_owned_recovery_needed() {{ [[ "$FIXTURE_MISSING_LOCAL_OWNER" == 1 ]]; }}
is_stack_running() {{ return 0; }}
stop_stack_for_upgrade() {{ printf 'stop\\n' >> "$FIXTURE_EFFECTS"; }}
capture_detached_start_log_offset() {{ DETACHED_START_LOG_OFFSET=0; }}
record_child_submission() {{ printf 'submit\\n' >> "$FIXTURE_EFFECTS"; return 77; }}
'''

    def run(*, optional_ready: bool = False, start_claim: bool = False,
            serving_group: bool = False, missing_local_owner: bool = False, user_ready: bool = True,
            google_owner: str | None = None, google_enabled: bool = True):
        effects.write_text("")
        owner = ""
        if google_owner is not None:
            owner = cli_function("runtime_owned_recovery_needed") + r'''
assign_runtime_ports() { api_port=10001 frontend_port=10002 playground_port=10003; }
runtime_port_listening() { return 0; }
express_install_experience() { return 0; }
telegram_recovery_owner_missing() { return 1; }
runtime_env_true() { [[ "$1" == START_GOOGLE_MCP && "$FIXTURE_GOOGLE_ENABLED" == 1 ]]; }
read_generated_env_value() { printf '%s\n' "${2:-}"; }
runtime_pid_file_running() {
  [[ "$1" == google_workspace_mcp.pid && "$2" == true ]] || exit 90
  [[ "$FIXTURE_GOOGLE_OWNER" == owned ]]
}
'''
        script = "set -Eeuo pipefail\n" + detached_launch_function() + preamble + owner + r'''
if launch_stack_detached; then result=0; else result=$?; fi
printf '%s/%s\n' "$USE_REDIS" "$USE_REDIS_STREAMS" > "$FIXTURE_FLAGS"
exit "$result"
'''
        result = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=10,
            env={**os.environ, "FIXTURE_OPTIONAL_READY": str(int(optional_ready)),
                 "FIXTURE_START_CLAIM": str(int(start_claim)),
                 "FIXTURE_SERVING_GROUP": str(int(serving_group)),
                 "FIXTURE_MISSING_LOCAL_OWNER": str(int(missing_local_owner)),
                 "FIXTURE_GOOGLE_OWNER": google_owner or "",
                 "FIXTURE_GOOGLE_ENABLED": str(int(google_enabled)),
                 "FIXTURE_USER_READY": str(int(user_ready))})
        assert "command not found" not in result.stderr
        assert flags.read_text().strip() == "true/true", "Admission must retain the configured Redis mode"
        return result, effects.read_text().splitlines()

    return run


@pytest.mark.parametrize("serving_group", [False, True], ids=["no-serving-receipt", "existing-serving-receipt"])
@pytest.mark.parametrize("user_ready", [False, True], ids=["protocol-unready", "protocol-ready"])
def test_dependency_attention_does_not_stop_or_resubmit_a_healthy_core(
    admission_run, serving_group: bool, user_ready: bool,
) -> None:
    result, effects = admission_run(serving_group=serving_group, user_ready=user_ready)
    assert effects == [], "A dependency outage alone must not submit canonical start --restart"
    assert result.returncode == 0, result.stderr


def test_missing_local_service_owner_retains_the_existing_repair_submission(admission_run) -> None:
    result, effects = admission_run(missing_local_owner=True)
    assert effects == ["submit"]
    assert result.returncode == 1, "The controlled child submission fails without creating a real process"


def test_a_current_startup_claim_prevents_another_submission(admission_run) -> None:
    result, effects = admission_run(start_claim=True)
    assert result.returncode == 0, result.stderr
    assert effects == []
    assert "already starting" in result.stdout


def test_healthy_enabled_surfaces_remain_already_running(admission_run) -> None:
    result, effects = admission_run(optional_ready=True)
    assert result.returncode == 0, result.stderr
    assert effects == []
    assert "already running" in result.stdout


@pytest.mark.parametrize("serving_group", [False, True], ids=["no-serving-receipt", "existing-serving-receipt"])
@pytest.mark.parametrize("owner,enabled,repair", [
    ("missing", True, True), ("owned", True, False),
    ("foreign", True, True), ("missing", False, False),
])
def test_google_process_loss_uses_existing_repair_but_dependency_attention_does_not(
    admission_run, serving_group: bool, owner: str, enabled: bool, repair: bool,
) -> None:
    result, effects = admission_run(serving_group=serving_group, google_owner=owner, google_enabled=enabled)
    expected = (["stop"] if serving_group else []) + ["submit"] if repair else []
    assert effects == expected
    assert result.returncode == (1 if repair else 0), result.stderr
    if repair:
        assert "google_mcp_owner_missing" in result.stdout

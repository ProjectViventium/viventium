"""Native restart reuses its selected database owner without starting optional services."""

import hashlib
import shlex
import subprocess
from pathlib import Path

import pytest

from test_native_stack_helpers import extract_shell_function


ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "viventium_v0_4/viventium-librechat-start.sh"
NATIVE = ROOT / "scripts/viventium/native_stack.sh"


def run_readiness(tmp_path, *, mode="native", skip_docker=True, local=True,
                  restart=True, owner_fails=False, source=None):
    data = tmp_path / "selected runtime" / "mongo-data"
    data.mkdir(parents=True)
    anchor = data / "WiredTiger"
    anchor.write_bytes(b"existing-selected-database")
    digest = hashlib.sha256(anchor.read_bytes()).hexdigest()
    ready, calls = tmp_path / "ready", tmp_path / "calls"
    ready.touch()
    owner = tmp_path / "repo/scripts/viventium/native_stack.sh"
    owner.parent.mkdir(parents=True)
    native = NATIVE.read_text()
    start_case = native.split('  start)\n', 1)[1].split('  stop)\n', 1)[0]
    owner.write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        'NATIVE_STACK_SKIP_LIVEKIT="${VIVENTIUM_NATIVE_STACK_SKIP_LIVEKIT:-0}"\n'
        'NATIVE_STACK_SKIP_MEILI="${VIVENTIUM_NATIVE_STACK_SKIP_MEILI:-0}"\n'
        + extract_shell_function(native, "validate_native_livekit_startup")
        + extract_shell_function(native, "start_livekit")
        + 'start_mongo() { printf "native-owner:%s:%s\\n" "$VIVENTIUM_APP_SUPPORT_DIR" "$VIVENTIUM_LOCAL_MONGO_DATA_PATH" >> "$CALLS"; '
          'test -f "$VIVENTIUM_LOCAL_MONGO_DATA_PATH/WiredTiger"; '
          'test "$OWNER_FAILS" = false; touch "$READY"; }\n'
        + 'run_mongo_engine_identity() { printf "owner-receipt:%s\\n" "$1" >> "$CALLS"; }\n'
        + 'start_meili() { printf "unexpected-meili\\n" >> "$CALLS"; return 90; }\n'
        + 'case "${1:-}" in\n  start)\n' + start_case + 'esac\n'
    )
    owner.chmod(0o700)
    values = {
        "VIVENTIUM_CORE_DIR": tmp_path / "repo",
        "VIVENTIUM_APP_SUPPORT_ROOT": tmp_path / "support",
        "VIVENTIUM_LOCAL_MONGO_DATA_PATH": data,
        "VIVENTIUM_INSTALL_MODE": mode,
        "SKIP_DOCKER": str(skip_docker).lower(),
        "LOCAL": str(local).lower(),
        "OWNER_FAILS": str(owner_fails).lower(),
        "MONGO_URI": "mongodb://127.0.0.1:32117/selected-db",
        "MONGO_HOST": "127.0.0.1", "MONGO_PORT": "32117",
        "READY": ready, "CALLS": calls,
    }
    setup = "\n".join(f"export {key}={shlex.quote(str(value))}" for key, value in values.items())
    function = extract_shell_function(source or LAUNCHER.read_text(), "ensure_mongodb_ready")
    result = subprocess.run([
        "bash", "-c", "set -euo pipefail\n" + setup + "\n"
        'resolve_mongo_connection() { MONGO_IS_LOCAL="$LOCAL"; }\n'
        'mongo_ping() { test -f "$READY"; }\n'
        'ensure_local_mongo_replica_set() { printf "replica-ready\\n" >> "$CALLS"; }\n'
        'record_mongo_engine_identity() { printf "launcher-receipt\\n" >> "$CALLS"; }\n'
        'start_local_mongodb_container() { printf "docker-owner\\n" >> "$CALLS"; touch "$READY"; }\n'
        'start_local_mongodb_native() { printf "legacy-fallback\\n" >> "$CALLS"; return 91; }\n'
        'log_error() { printf "%s\\n" "$*"; }\nlog_success() { :; }\n'
        'sleep() { :; }\n' + function
        + ('rm "$READY"\n' if restart else "")
        + "ensure_mongodb_ready\n",
    ], text=True, capture_output=True, timeout=10)
    assert hashlib.sha256(anchor.read_bytes()).hexdigest() == digest
    return result, calls.read_text().splitlines() if calls.exists() else []


@pytest.mark.parametrize("skip_docker", [True, False])
def test_native_restart_restores_same_selected_database_owner_with_optional_services_off(tmp_path, skip_docker):
    result, calls = run_readiness(tmp_path, skip_docker=skip_docker)
    assert result.returncode == 0, result.stderr
    assert sum(line.startswith("native-owner:") for line in calls) == 1
    assert calls.count("owner-receipt:record-mongo-engine") == 1
    assert calls[-2:] == ["replica-ready", "launcher-receipt"]
    assert all("selected runtime/mongo-data" in line for line in calls if line.startswith("native-owner:"))
    assert "docker-owner" not in calls and "legacy-fallback" not in calls
    assert "unexpected-meili" not in calls
    assert "Skipping native LiveKit during early bootstrap" in result.stdout


def test_reachable_native_mongo_is_reused_without_another_owner_start(tmp_path):
    result, calls = run_readiness(tmp_path, restart=False)
    assert result.returncode == 0
    assert calls == ["replica-ready", "launcher-receipt"]


def test_native_owner_failure_cannot_fall_back_to_another_engine(tmp_path):
    result, calls = run_readiness(tmp_path, owner_fails=True)
    assert result.returncode != 0
    assert sum(line.startswith("native-owner:") for line in calls) == 1
    assert "docker-owner" not in calls and "legacy-fallback" not in calls


def test_docker_install_still_honors_skip_docker(tmp_path):
    result, calls = run_readiness(tmp_path, mode="docker")
    assert result.returncode != 0
    assert "--skip-docker is enabled" in result.stdout
    assert calls == []


def test_docker_install_keeps_its_existing_container_start_path(tmp_path):
    result, calls = run_readiness(tmp_path, mode="docker", skip_docker=False)
    assert result.returncode == 0
    assert calls == ["docker-owner", "replica-ready", "launcher-receipt"]


@pytest.mark.parametrize("mode", ["native", "docker"])
def test_unreachable_external_mongo_does_not_start_a_local_engine(tmp_path, mode):
    result, calls = run_readiness(tmp_path, mode=mode, local=False)
    assert result.returncode != 0
    assert calls == []
    assert "non-local host" in result.stdout

from __future__ import annotations

import os
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "viventium_v0_4" / "viventium-librechat-start.sh"


def launcher_source() -> str:
    return LAUNCHER.read_text(encoding="utf-8")


def shell_function(source: str, name: str, next_name: str) -> str:
    start = source.index(f"{name}() {{")
    end = source.index(f"{next_name}() {{", start)
    return source[start:end]


def run_existing_parallel_redis_check(**overrides: str) -> subprocess.CompletedProcess[str]:
    source = launcher_source()
    body = shell_function(
        source,
        "ensure_parallel_work_redis_ready",
        "start_local_mongodb_container",
    )
    harness = r'''
set -u
is_truthy() {
  case "$1" in
    1|true|TRUE|yes|YES|on|ON) return 0 ;;
    *) return 1 ;;
  esac
}
log_error() { printf 'ERROR:%s\n' "$*" >&2; }
log_success() { :; }
ensure_docker_daemon_for_service() { return 0; }
docker_daemon_ready() { return 0; }
port_in_use() { return 1; }
docker() {
  printf 'DOCKER_CALL' >&2
  printf ' %q' "$@" >&2
  printf '\n' >&2
  case "$1" in
    ps)
      printf 'redis-container-id\n'
      ;;
    inspect)
      case "$3" in
        *viventium.service*) printf 'parallel-work-redis\n' ;;
        *viventium.stack*) printf 'viventium_v0_4\n' ;;
        *viventium.profile*) printf 'isolated\n' ;;
        *viventium.contract*) printf 'parallel-work-redis-v1\n' ;;
        *Config.Image*) printf '%s\n' "$FAKE_IMAGE" ;;
        *Config.Cmd*) printf '%s\n' "$FAKE_COMMAND" ;;
        *RestartPolicy.Name*) printf '%s\n' "$FAKE_RESTART_POLICY" ;;
        *Mounts*)
          if [[ "$3" == *'.RW'* ]]; then
            printf '%s|%s|%s\n' "$FAKE_VOLUME_SOURCE" "$FAKE_VOLUME_TYPE" "$FAKE_VOLUME_RW"
          else
            printf '%s\n' "$FAKE_VOLUME_SOURCE"
          fi
          ;;
        *State.Running*) printf 'true\n' ;;
        *) return 97 ;;
      esac
      ;;
    port)
      printf '127.0.0.1:46379\n'
      ;;
    exec)
      if [[ "${3:-}" == "sh" ]]; then
        [[ "$FAKE_VOLUME_WRITABLE" == "true" ]]
      elif [[ "${3:-}" == "redis-cli" && "${4:-}" == "--raw" && "${5:-}" == "CONFIG" ]]; then
        case "${7:-}" in
          appendonly) printf 'appendonly\n%s\n' "$FAKE_APPENDONLY" ;;
          appendfsync) printf 'appendfsync\n%s\n' "$FAKE_APPENDFSYNC" ;;
          *) return 96 ;;
        esac
      elif [[ "${3:-}" == "redis-cli" && "${4:-}" == "ping" ]]; then
        printf 'PONG\n'
      else
        return 95
      fi
      ;;
    start) return 0 ;;
    *) return 94 ;;
  esac
}
VIVENTIUM_PARALLEL_WORK_AVAILABLE=true
USE_REDIS=true
USE_REDIS_STREAMS=true
REDIS_URI=redis://127.0.0.1:46379
DOCKER_BIN=/usr/bin/docker
SKIP_DOCKER=false
PARALLEL_REDIS_CONTAINER_NAME=viventium-parallel-redis-isolated
PARALLEL_REDIS_VOLUME_NAME=viventium-parallel-redis-isolated-data
PARALLEL_REDIS_IMAGE=redis:7-alpine
VIVENTIUM_RUNTIME_PROFILE=isolated
PARALLEL_REDIS_STARTED_BY_SCRIPT=false
''' + body + "\nensure_parallel_work_redis_ready\n"
    fixture = {
        "FAKE_IMAGE": "redis:7-alpine",
        "FAKE_COMMAND": '["redis-server","--appendonly","yes","--appendfsync","everysec"]',
        "FAKE_RESTART_POLICY": "unless-stopped",
        "FAKE_VOLUME_SOURCE": "viventium-parallel-redis-isolated-data",
        "FAKE_VOLUME_TYPE": "volume",
        "FAKE_VOLUME_RW": "true",
        "FAKE_VOLUME_WRITABLE": "true",
        "FAKE_APPENDONLY": "yes",
        "FAKE_APPENDFSYNC": "everysec",
    }
    fixture.update(overrides)
    return subprocess.run(
        ["bash", "-c", harness],
        check=False,
        capture_output=True,
        env={**os.environ, **fixture},
        text=True,
        timeout=5,
    )


def test_parallel_work_redis_uses_one_owned_persistent_loopback_container() -> None:
    source = launcher_source()
    body = shell_function(
        source,
        "ensure_parallel_work_redis_ready",
        "start_local_mongodb_container",
    )

    assert 'VIVENTIUM_PARALLEL_REDIS_CONTAINER:-viventium-parallel-redis-${VIVENTIUM_RUNTIME_PROFILE}' in source
    assert 'VIVENTIUM_PARALLEL_REDIS_VOLUME:-${PARALLEL_REDIS_CONTAINER_NAME}-data' in source
    assert 'PARALLEL_REDIS_IMAGE="${VIVENTIUM_PARALLEL_REDIS_IMAGE:-redis:7-alpine}"' in source
    assert 'name=^/${PARALLEL_REDIS_CONTAINER_NAME}$' in body
    assert 'viventium.service=parallel-work-redis' in body
    assert 'viventium.profile=${VIVENTIUM_RUNTIME_PROFILE}' in body
    assert 'viventium.contract=parallel-work-redis-v1' in body
    assert '-p "127.0.0.1:${parallel_redis_port}:6379"' in body
    assert '-v "${PARALLEL_REDIS_VOLUME_NAME}:/data"' in body
    assert "redis-server --appendonly yes --appendfsync everysec" in body
    assert 'docker exec "$PARALLEL_REDIS_CONTAINER_NAME" redis-cli ping' in body
    assert "firecrawl" not in body.lower()
    assert "searxng" not in body.lower()


def test_parallel_work_redis_rejects_nonlocal_or_secret_bearing_uri_and_wrong_owner() -> None:
    source = launcher_source()
    body = shell_function(
        source,
        "ensure_parallel_work_redis_ready",
        "start_local_mongodb_container",
    )

    assert r'^redis://127\.0\.0\.1:([1-9][0-9]{0,4})$' in body
    assert 'redis_service_label" != "parallel-work-redis"' in body
    assert 'redis_stack_label" != "viventium_v0_4"' in body
    assert 'redis_profile_label" != "$VIVENTIUM_RUNTIME_PROFILE"' in body
    assert 'redis_contract_label" != "parallel-work-redis-v1"' in body
    assert "Refusing to reuse Redis container" in body
    assert "return 1" in body


def test_parallel_work_redis_reuses_only_an_exact_durable_runtime() -> None:
    result = run_existing_parallel_redis_check()

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "override",
    [
        {"FAKE_IMAGE": "redis:latest"},
        {"FAKE_COMMAND": '["redis-server","--appendonly","no","--appendfsync","everysec"]'},
        {"FAKE_RESTART_POLICY": "no"},
        {"FAKE_VOLUME_SOURCE": "unrelated-volume"},
        {"FAKE_VOLUME_TYPE": "bind"},
        {"FAKE_VOLUME_RW": "false"},
        {"FAKE_VOLUME_WRITABLE": "false"},
        {"FAKE_APPENDONLY": "no"},
        {"FAKE_APPENDFSYNC": "always"},
    ],
    ids=[
        "image",
        "declared-command",
        "restart-policy",
        "volume-name",
        "volume-type",
        "volume-read-only",
        "volume-write-probe",
        "live-appendonly",
        "live-appendfsync",
    ],
)
def test_parallel_work_redis_rejects_owned_container_runtime_drift(
    override: dict[str, str],
) -> None:
    result = run_existing_parallel_redis_check(**override)

    assert result.returncode != 0
    assert "DOCKER_CALL rm" not in result.stderr
    assert "DOCKER_CALL run" not in result.stderr


def test_parallel_work_redis_is_verified_before_librechat_and_failure_stops_startup() -> None:
    source = launcher_source()
    call = 'if ! ensure_parallel_work_redis_ready; then'
    call_index = source.index(call)
    librechat_index = source.index("# LibreChat\n# ----------------------------", call_index)

    assert source.index('VIVENTIUM_PARALLEL_WORK_AVAILABLE:-false', call_index - 500) < call_index
    assert call_index < librechat_index
    failure_block = source[call_index : source.index("fi", call_index) + 2]
    assert 'log_error "Parallel Work Redis is required for LibreChat startup"' in failure_block
    assert "exit 1" in failure_block


def test_parallel_work_redis_flags_and_container_are_not_shared_with_other_services() -> None:
    source = launcher_source()
    body = shell_function(
        source,
        "ensure_parallel_work_redis_ready",
        "start_local_mongodb_container",
    )

    assert 'is_truthy "${USE_REDIS:-false}"' in body
    assert 'is_truthy "${USE_REDIS_STREAMS:-false}"' in body
    assert 'VIVENTIUM_PARALLEL_WORK_AVAILABLE:-false' in source
    assert "docker volume rm" not in source


def test_one_shot_user_default_reconciliation_does_not_open_redis_clients() -> None:
    source = launcher_source()
    body = shell_function(
        source,
        "reconcile_viventium_user_defaults",
        "ensure_code_interpreter_env",
    )

    assert 'USE_REDIS=false USE_REDIS_STREAMS=false node "$reconcile_script"' in body
    assert (
        "USE_REDIS=false USE_REDIS_STREAMS=false "
        "node scripts/viventium-sync-local-search.js"
    ) in source
    librechat_launcher = (
        ROOT / "viventium_v0_4" / "LibreChat" / "viventium-start.sh"
    ).read_text(encoding="utf-8")
    assert (
        'USE_REDIS=false USE_REDIS_STREAMS=false node "$sync_script"'
        in librechat_launcher
    )
    assert 'USE_REDIS=false USE_REDIS_STREAMS=false REDIS_URI=""' not in source

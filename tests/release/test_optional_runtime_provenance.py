from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OPENCLAW_BRIDGE = ROOT / "viventium_v0_4" / "MCPs" / "openclaw-bridge"
OPENCLAW_VERSION = "2026.7.1-2"
OPENCLAW_INTEGRITY = (
    "sha512-ycF3yPcbjN6bUPeaUx6Mh6vze1hQWoD3CT/wWcmD7a8xaHHHRUaAlaq+lFxMHf1ssEgODVAwjlzYqp2twkYZ7g=="
)
OPENCLAW_LOCK_SHA256 = "e025a05ef3d268747dc293ef54876471d067f22644a8fa26a9139b7d1fe4fbc3"
SKYVERN_IMAGES = {
    "postgres@sha256:f1341c01408dc7278e9d365ed4f860cd3f87dd16b4464ac326fc0f422083a579",
    "public.ecr.aws/skyvern/skyvern@sha256:ad58d950f1c8cc3bc2d442228f701243b80b84494f11bbb066347ed034006e77",
    "public.ecr.aws/skyvern/skyvern-ui@sha256:fe43d2b11476e5d24b98b40ff9d88a1bdb89888f4ab8103336205fb204d5ef07",
}
LIVEKIT_IMAGE = (
    "livekit/livekit-server:v1.13.4@"
    "sha256:189f7c81b704a36642bc5c7e2d3e1ae83744627c11978a23a251bf19fbec64e0"
)
LIVEKIT_SOURCE_COMMIT = "0b3fd288e3ef3263ec475ba0d78cf3ad77459981"


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _extract_javascript_logging_calls(source: str) -> list[str]:
    """Return complete console/logger calls without treating ordinary service arguments as logs."""
    call_start = re.compile(
        r"\b(?:console|logger)\.(?:trace|debug|info|warn|error|log)(?:\?\.)?\s*\("
    )
    calls: list[str] = []
    for match in call_start.finditer(source):
        depth = 1
        quote: str | None = None
        escaped = False
        cursor = match.end()
        while cursor < len(source) and depth:
            character = source[cursor]
            if quote is not None:
                if escaped:
                    escaped = False
                elif character == "\\":
                    escaped = True
                elif character == quote:
                    quote = None
            elif character in ("'", '"', "`"):
                quote = character
            elif character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
            cursor += 1
        if depth:
            raise AssertionError(f"Unterminated JavaScript logging call at offset {match.start()}")
        calls.append(source[match.start() : cursor])
    return calls


def _extract_shell_function(text: str, name: str) -> str:
    lines = text.splitlines()
    start = next(
        (index for index, line in enumerate(lines) if line.strip() == f"{name}() {{"),
        None,
    )
    if start is None:
        raise AssertionError(f"Missing shell function: {name}")
    collected: list[str] = []
    depth = 0
    for line in lines[start:]:
        collected.append(line)
        depth += line.count("{")
        depth -= line.count("}")
        if depth == 0:
            break
    return "\n".join(collected) + "\n"


def _livekit_startup_block() -> str:
    launcher = _read("viventium_v0_4/viventium-librechat-start.sh")
    return launcher.split("# LiveKit server (Docker)", maxsplit=1)[1].split(
        "# Prepare the local LibreChat runtime files", maxsplit=1
    )[0]


def _livekit_selector_defs() -> str:
    launcher = _read("viventium_v0_4/viventium-librechat-start.sh")
    return "\n".join(
        (
            _extract_shell_function(
                launcher, "livekit_container_has_configured_http_port"
            ),
            _extract_shell_function(launcher, "livekit_runtime_container_ids"),
        )
    )


def _runtime_stop_selector_defs() -> str:
    launcher = _read("viventium_v0_4/viventium-librechat-start.sh")
    return "\n".join(
        _extract_shell_function(launcher, name)
        for name in (
            "read_detached_launch_process_group",
            "process_start_identity",
            "runtime_process_group_receipt_valid",
            "pid_matches_recorded_runtime_process_group",
            "canonical_app_support_root",
            "runtime_stop_requires_process_group",
            "pid_matches_runtime_stop_identity",
            "read_pid_cwd",
            "normalize_scope_path",
            "path_is_trashed_checkout",
            "scope_component_signature",
            "pid_matches_trashed_scope_variant",
            "pid_matches_scope",
            "find_scope_pattern_pids",
        )
    )


def _runtime_group_stop_defs() -> str:
    launcher = _read("viventium_v0_4/viventium-librechat-start.sh")
    return "\n".join(
        _extract_shell_function(launcher, name)
        for name in (
            "kill_pids",
            "current_process_group_id",
            "read_detached_launch_process_group",
            "process_start_identity",
            "canonical_app_support_root",
            "runtime_stop_requires_process_group",
            "runtime_process_group_receipt_valid",
            "runtime_process_group_pids",
            "clear_detached_launch_process_group",
            "authorize_runtime_process_group_stop",
            "kill_recorded_detached_launch_process_group",
        )
    )


def test_shared_checkout_stop_selector_is_bound_to_recorded_runtime_group(
    tmp_path: Path,
) -> None:
    shared_checkout = tmp_path / "shared-checkout"
    shared_checkout.mkdir()
    runner = shared_checkout / "shared-runtime-probe.sh"
    runner.write_text("#!/usr/bin/env bash\nsleep 120\n", encoding="utf-8")
    runner.chmod(0o755)

    runtime_a = tmp_path / "runtime-a"
    runtime_b = tmp_path / "runtime-b"
    pgid_file = runtime_a / "state" / "runtime" / "isolated" / "detached-launch.pgid"
    pgid_file.parent.mkdir(parents=True)

    process_a = subprocess.Popen(
        [str(runner)],
        cwd=shared_checkout,
        start_new_session=True,
    )
    process_b = subprocess.Popen(
        [str(runner)],
        cwd=shared_checkout,
        start_new_session=True,
    )
    pgid_file.write_text(f"{process_a.pid}\n", encoding="utf-8")
    members_file = pgid_file.with_name("detached-launch.members")
    process_start = subprocess.run(
        ["ps", "-p", str(process_a.pid), "-o", "lstart="],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    members_file.write_text(f"{process_a.pid}\t{process_start}\n", encoding="utf-8")

    try:
        time.sleep(0.1)
        script = f"""
set -euo pipefail
DETACHED_LAUNCH_PGID_FILE={str(pgid_file)!r}
DETACHED_LAUNCH_MEMBERS_FILE={str(members_file)!r}
VIVENTIUM_APP_SUPPORT_ROOT={str(runtime_a)!r}
HOME={str(tmp_path / "home")!r}
{_runtime_stop_selector_defs()}
find_scope_pattern_pids shared-runtime-probe {str(shared_checkout)!r}
"""
        completed = subprocess.run(
            ["bash", "-lc", script],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
        )

        assert completed.stdout.strip() == str(process_a.pid)
        assert process_a.poll() is None
        assert process_b.poll() is None

        members_file.write_text(
            f"{process_a.pid}\tstale process start identity\n",
            encoding="utf-8",
        )
        stale_completed = subprocess.run(
            ["bash", "-lc", script],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        assert stale_completed.stdout.strip() == ""
        members_file.write_text(
            f"{process_a.pid}\t{process_start}\n",
            encoding="utf-8",
        )

        stop_script = f"""
set -euo pipefail
DETACHED_LAUNCH_PGID_FILE={str(pgid_file)!r}
DETACHED_LAUNCH_MEMBERS_FILE={str(members_file)!r}
VIVENTIUM_APP_SUPPORT_ROOT={str(runtime_a)!r}
HOME={str(tmp_path / "home")!r}
log_warn() {{ :; }}
log_error() {{ printf '%s\\n' "$*" >&2; }}
{_runtime_group_stop_defs()}
kill_recorded_detached_launch_process_group
"""
        subprocess.run(
            ["bash", "-lc", stop_script],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        process_a.wait(timeout=5)
        assert process_b.poll() is None
        assert not pgid_file.exists()
        assert not members_file.exists()
    finally:
        for process in (process_a, process_b):
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)


def test_noncanonical_stop_without_runtime_group_fails_closed(tmp_path: Path) -> None:
    launcher = _read("viventium_v0_4/viventium-librechat-start.sh")
    functions = "\n".join(
        _extract_shell_function(launcher, name)
        for name in (
            "read_detached_launch_process_group",
            "process_start_identity",
            "runtime_process_group_receipt_valid",
            "pid_matches_recorded_runtime_process_group",
            "canonical_app_support_root",
            "runtime_stop_requires_process_group",
            "pid_matches_runtime_stop_identity",
        )
    )
    app_support = tmp_path / "isolated-app-support"
    pgid_file = app_support / "state" / "runtime" / "isolated" / "detached-launch.pgid"

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                f"DETACHED_LAUNCH_PGID_FILE={str(pgid_file)!r}\n"
                f"DETACHED_LAUNCH_MEMBERS_FILE={str(pgid_file.with_name('detached-launch.members'))!r}\n"
                f"VIVENTIUM_APP_SUPPORT_ROOT={str(app_support)!r}\n"
                f"HOME={str(tmp_path / 'home')!r}\n"
                f"{functions}"
                "pid_matches_runtime_stop_identity $$\n"
            ),
        ],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0


def test_detached_group_receipt_survives_launcher_leader_exit(tmp_path: Path) -> None:
    app_support = tmp_path / "isolated-app-support"
    runtime_state = app_support / "state" / "runtime" / "isolated"
    runtime_state.mkdir(parents=True)
    pgid_file = runtime_state / "detached-launch.pgid"
    members_file = runtime_state / "detached-launch.members"
    child_pid_file = tmp_path / "child.pid"
    launcher = tmp_path / "short-lived-launcher.sh"
    launcher.write_text(
        (
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "trap '' HUP\n"
            "sleep 120 &\n"
            "child_pid=$!\n"
            "disown \"$child_pid\" 2>/dev/null || true\n"
            f"printf '%s\\n' \"$child_pid\" > {str(child_pid_file)!r}\n"
        ),
        encoding="utf-8",
    )
    launcher.chmod(0o755)
    leader = subprocess.Popen([str(launcher)], start_new_session=True)
    child_pid = 0

    try:
        leader.wait(timeout=5)
        for _ in range(50):
            if child_pid_file.exists():
                child_pid = int(child_pid_file.read_text(encoding="utf-8").strip())
                break
            time.sleep(0.02)
        assert child_pid > 0
        child_pgid = subprocess.run(
            ["ps", "-p", str(child_pid), "-o", "pgid="],
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
        assert child_pgid == str(leader.pid)
        child_start = subprocess.run(
            ["ps", "-p", str(child_pid), "-o", "lstart="],
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
        pgid_file.write_text(f"{leader.pid}\n", encoding="utf-8")
        members_file.write_text(f"{child_pid}\t{child_start}\n", encoding="utf-8")

        stop_script = f"""
set -euo pipefail
DETACHED_LAUNCH_PGID_FILE={str(pgid_file)!r}
DETACHED_LAUNCH_MEMBERS_FILE={str(members_file)!r}
VIVENTIUM_APP_SUPPORT_ROOT={str(app_support)!r}
HOME={str(tmp_path / "home")!r}
log_warn() {{ :; }}
log_error() {{ printf '%s\\n' "$*" >&2; }}
{_runtime_group_stop_defs()}
runtime_process_group_receipt_valid
kill_recorded_detached_launch_process_group
"""
        subprocess.run(
            ["bash", "-lc", stop_script],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        stopped = subprocess.run(
            ["ps", "-p", str(child_pid)],
            check=False,
            capture_output=True,
        )
        assert stopped.returncode != 0
    finally:
        if child_pid:
            subprocess.run(["kill", "-TERM", str(child_pid)], check=False)


def test_restart_stops_predecessor_before_recording_successor_group() -> None:
    launcher = _read("viventium_v0_4/viventium-librechat-start.sh")
    restart = launcher.index('if [[ "$RESTART_SERVICES" == "true" ]]; then')
    stop = launcher.index("  stop_running_services", restart)
    successor = launcher.index(
        "# Preserve the predecessor receipt through restart cleanup",
        stop,
    )
    record = launcher.index("record_detached_launch_process_group", successor)
    final_refresh = launcher.rindex("record_detached_launch_process_group_members")
    detached_exit = launcher.rindex(
        '  log_success "Detached launch submitted; services will keep warming in the background"'
    )

    assert restart < stop < successor < record
    assert final_refresh < detached_exit


def test_noncanonical_start_restart_and_stop_preserve_global_docker(
    tmp_path: Path,
) -> None:
    launcher = _read("viventium_v0_4/viventium-librechat-start.sh")
    functions = "\n".join(
        _extract_shell_function(launcher, name)
        for name in (
            "canonical_app_support_root",
            "runtime_stop_requires_process_group",
            "protect_noncanonical_runtime_from_global_docker_mutation",
        )
    )
    app_support = tmp_path / "isolated-app-support"
    script = f"""
set -euo pipefail
HOME={str(tmp_path / "home")!r}
VIVENTIUM_APP_SUPPORT_ROOT={str(app_support)!r}
SKIP_DOCKER=false
RESTART_DOCKER_SERVICES=true
GLOBAL_DOCKER_CLEANUP_ALLOWED=true
START_MS365_MCP=true
START_RAG_API=true
START_CODE_INTERPRETER=true
START_SKYVERN=true
START_FIRECRAWL=true
START_SEARXNG=true
log_warn() {{ :; }}
{functions}
protect_noncanonical_runtime_from_global_docker_mutation
printf '%s\\n' \
  "$SKIP_DOCKER" \
  "$RESTART_DOCKER_SERVICES" \
  "$GLOBAL_DOCKER_CLEANUP_ALLOWED" \
  "$START_MS365_MCP" \
  "$START_RAG_API" \
  "$START_CODE_INTERPRETER" \
  "$START_SKYVERN" \
  "$START_FIRECRAWL" \
  "$START_SEARXNG"
"""
    completed = subprocess.run(
        ["bash", "-lc", script],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    stop_services = launcher[
        launcher.index("stop_running_services() {") :
        launcher.index("cleanup_stale_containers() {")
    ]

    assert completed.stdout.splitlines() == [
        "false",
        "false",
        "false",
        "false",
        "false",
        "false",
        "false",
        "false",
        "false",
    ]
    assert "protect_noncanonical_runtime_from_global_docker_mutation" in stop_services
    assert (
        'if [[ "$GLOBAL_DOCKER_CLEANUP_ALLOWED" == "true" && "$SKIP_DOCKER" != "true" ]] &&'
        in stop_services
    )
    protection = launcher.index(
        "\nprotect_noncanonical_runtime_from_global_docker_mutation\n"
    )
    stop_only = launcher.index('if [[ "$STOP_ONLY" == "true" ]]', protection)
    stale_cleanup = launcher.index("\ncleanup_stale_containers\n", stop_only)
    assert protection < stop_only < stale_cleanup
    assert (
        'if [[ "$GLOBAL_DOCKER_CLEANUP_ALLOWED" != "true" ]]; then'
        in _extract_shell_function(launcher, "cleanup_stale_containers")
    )
    for function_name in (
        "start_local_mongodb_container",
        "start_local_meilisearch_container",
    ):
        container_bootstrap = _extract_shell_function(launcher, function_name)
        ownership_gate = container_bootstrap.index(
            'if [[ "$GLOBAL_DOCKER_CLEANUP_ALLOWED" != "true" ]]; then'
        )
        first_docker_mutation = min(
            index
            for needle in ("docker start", "docker run")
            if (index := container_bootstrap.find(needle)) >= 0
        )
        assert ownership_gate < first_docker_mutation
    meili_recycle = _extract_shell_function(
        launcher,
        "restart_viventium_owned_meilisearch_listener",
    )
    assert (
        'if [[ "$GLOBAL_DOCKER_CLEANUP_ALLOWED" == "true" ]] &&'
        in meili_recycle
    )
    assert meili_recycle.index(
        'if [[ "$GLOBAL_DOCKER_CLEANUP_ALLOWED" == "true" ]] &&'
    ) < meili_recycle.index(
        'existing=$(docker ps -aq --filter "name=^/${MEILI_CONTAINER_NAME}$"'
    )


def test_noncanonical_stop_ignores_unowned_shared_mongo_port(tmp_path: Path) -> None:
    launcher = _read("viventium_v0_4/viventium-librechat-start.sh")
    prepare = _extract_shell_function(
        launcher,
        "prepare_mongo_engine_identity_for_stop",
    )
    native_pid = tmp_path / "alternate-native-mongo.pid"
    script = f"""
set -euo pipefail
GLOBAL_DOCKER_CLEANUP_ALLOWED=false
MONGO_ENGINE_IDENTITY_PREPARED=false
MONGO_NATIVE_PID_FILE={str(native_pid)!r}
MONGO_PORT=27117
MONGO_CONTAINER_NAME=viventium-mongodb-isolated
MONGO_IS_LOCAL=true
resolve_mongo_connection() {{ MONGO_IS_LOCAL=true; }}
record_mongo_engine_identity() {{ return 1; }}
port_has_listener() {{ return 0; }}
docker_daemon_ready() {{
  printf 'forbidden Docker probe\\n' >&2
  return 1
}}
docker() {{
  printf 'forbidden Docker mutation\\n' >&2
  return 1
}}
log_error() {{ printf '%s\\n' "$*" >&2; }}
{prepare}
prepare_mongo_engine_identity_for_stop
printf '%s\\n' "$MONGO_ENGINE_IDENTITY_PREPARED"
"""
    completed = subprocess.run(
        ["bash", "-lc", script],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert completed.stdout.strip() == "false"
    assert "forbidden" not in completed.stderr


def test_fully_crashed_runtime_clears_stale_group_receipt(tmp_path: Path) -> None:
    app_support = tmp_path / "isolated-app-support"
    runtime_state = app_support / "state" / "runtime" / "isolated"
    runtime_state.mkdir(parents=True)
    pgid_file = runtime_state / "detached-launch.pgid"
    members_file = runtime_state / "detached-launch.members"
    pgid_file.write_text("987654\n", encoding="utf-8")
    members_file.write_text(
        "987654\tMon Jan  1 00:00:00 2001\n",
        encoding="utf-8",
    )

    script = f"""
set -euo pipefail
DETACHED_LAUNCH_PGID_FILE={str(pgid_file)!r}
DETACHED_LAUNCH_MEMBERS_FILE={str(members_file)!r}
VIVENTIUM_APP_SUPPORT_ROOT={str(app_support)!r}
HOME={str(tmp_path / "home")!r}
RUNTIME_STOP_AUTHORIZED_PGID=""
log_warn() {{ :; }}
log_error() {{ printf '%s\\n' "$*" >&2; }}
{_runtime_group_stop_defs()}
authorize_runtime_process_group_stop
"""
    subprocess.run(
        ["bash", "-lc", script],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert not pgid_file.exists()
    assert not members_file.exists()


def test_authorized_stop_survives_last_recorded_member_exit(tmp_path: Path) -> None:
    app_support = tmp_path / "isolated-app-support"
    runtime_state = app_support / "state" / "runtime" / "isolated"
    runtime_state.mkdir(parents=True)
    pgid_file = runtime_state / "detached-launch.pgid"
    members_file = runtime_state / "detached-launch.members"
    child_pid_file = tmp_path / "child.pid"
    launcher = tmp_path / "runtime-leader.sh"
    launcher.write_text(
        (
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "trap '' HUP\n"
            "sleep 120 &\n"
            "child_pid=$!\n"
            f"printf '%s\\n' \"$child_pid\" > {str(child_pid_file)!r}\n"
            "wait \"$child_pid\"\n"
        ),
        encoding="utf-8",
    )
    launcher.chmod(0o755)
    leader = subprocess.Popen([str(launcher)], start_new_session=True)
    child_pid = 0

    try:
        for _ in range(50):
            if child_pid_file.exists():
                child_pid = int(child_pid_file.read_text(encoding="utf-8").strip())
                break
            time.sleep(0.02)
        assert child_pid > 0
        leader_start = subprocess.run(
            ["ps", "-p", str(leader.pid), "-o", "lstart="],
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
        pgid_file.write_text(f"{leader.pid}\n", encoding="utf-8")
        members_file.write_text(
            f"{leader.pid}\t{leader_start}\n",
            encoding="utf-8",
        )

        stop_script = f"""
set -euo pipefail
DETACHED_LAUNCH_PGID_FILE={str(pgid_file)!r}
DETACHED_LAUNCH_MEMBERS_FILE={str(members_file)!r}
VIVENTIUM_APP_SUPPORT_ROOT={str(app_support)!r}
HOME={str(tmp_path / "home")!r}
RUNTIME_STOP_AUTHORIZED_PGID=""
log_warn() {{ :; }}
log_error() {{ printf '%s\\n' "$*" >&2; }}
{_runtime_group_stop_defs()}
authorize_runtime_process_group_stop
kill -TERM {leader.pid}
for _attempt in $(seq 1 50); do
  leader_state="$(ps -p {leader.pid} -o state= 2>/dev/null | tr -d '[:space:]' || true)"
  [[ -z "$leader_state" || "$leader_state" == Z* ]] && break
  sleep 0.02
done
kill_recorded_detached_launch_process_group
"""
        subprocess.run(
            ["bash", "-lc", stop_script],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        leader.wait(timeout=5)
        stopped = subprocess.run(
            ["ps", "-p", str(child_pid)],
            check=False,
            capture_output=True,
        )
        assert stopped.returncode != 0
        assert not pgid_file.exists()
        assert not members_file.exists()
    finally:
        if leader.poll() is None:
            leader.terminate()
            leader.wait(timeout=5)
        if child_pid:
            subprocess.run(["kill", "-TERM", str(child_pid)], check=False)


def test_openclaw_reviewed_runtime_lock_is_exact() -> None:
    package_path = OPENCLAW_BRIDGE / "openclaw-runtime-lock" / "package.json"
    lock_path = OPENCLAW_BRIDGE / "openclaw-runtime-lock" / "package-lock.json"
    package = json.loads(package_path.read_text(encoding="utf-8"))
    lock = json.loads(lock_path.read_text(encoding="utf-8"))

    assert hashlib.sha256(lock_path.read_bytes()).hexdigest() == OPENCLAW_LOCK_SHA256
    assert package["version"] == OPENCLAW_VERSION
    assert package["overrides"] == {"fast-uri": "3.1.3"}
    assert package["dependencies"]["openclaw"].endswith(
        f"/openclaw-{OPENCLAW_VERSION}.tgz"
    )
    assert lock["packages"]["node_modules/openclaw"]["integrity"] == OPENCLAW_INTEGRITY
    assert lock["packages"]["node_modules/openclaw"]["version"] == OPENCLAW_VERSION
    assert lock["packages"]["node_modules/fast-uri"]["version"] == "3.1.3"


def test_every_openclaw_consumer_fails_closed_on_the_reviewed_runtime() -> None:
    dockerfile_path = "viventium_v0_4/MCPs/openclaw-bridge/Dockerfile"
    compose_path = "viventium_v0_4/MCPs/openclaw-bridge/docker-compose.yml"
    e2b_path = "viventium_v0_4/MCPs/openclaw-bridge/e2b_runtime.py"
    manager_path = "viventium_v0_4/MCPs/openclaw-bridge/openclaw_manager.py"
    launcher_path = "viventium_v0_4/viventium-openclaw-bridge-start.sh"
    guidance_paths = (
        "viventium_v0_4/MCPs/openclaw-bridge/README.md",
        "viventium_v0_4/MCPs/openclaw-bridge/validate.sh",
        "viventium_v0_4/MCPs/openclaw-bridge/tests/e2e_setup.py",
        "docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md",
    )
    relative_paths = (dockerfile_path, compose_path, e2b_path, manager_path, launcher_path)
    sources = {path: _read(path) for path in (*relative_paths, *guidance_paths)}
    combined = "\n".join(sources.values())

    assert "openclaw@latest" not in combined
    assert "2026.2.9" not in combined
    assert "npm install -g" not in combined

    dockerfile = sources[dockerfile_path]
    assert OPENCLAW_VERSION in dockerfile
    assert "OPENCLAW_DISABLE_BONJOUR=1" in dockerfile
    assert "FASTMCP_CHECK_FOR_UPDATES=off" in dockerfile
    assert "npm ci --omit=dev" in dockerfile
    assert "openclaw-runtime-lock" in dockerfile
    assert "COPY requirements.txt requirements.lock" in dockerfile
    assert "pip install --no-cache-dir --require-hashes -r requirements.lock" in dockerfile
    assert "e2b_runtime.py vm_registry.py vm_control.py" in dockerfile
    assert "22.23.1" in dockerfile
    assert "python:3.12.13-slim-bookworm@sha256:" in dockerfile

    compose = sources[compose_path]
    assert "OPENCLAW_RUNTIME=${OPENCLAW_RUNTIME:-e2b}" in compose
    assert "OPENCLAW_DISABLE_BONJOUR=1" in compose
    assert "FASTMCP_CHECK_FOR_UPDATES=off" in compose
    assert "127.0.0.1:${OPENCLAW_BRIDGE_PORT:-8086}:8086" in compose
    assert "OPENCLAW_BRIDGE_SECRET:?" in compose

    e2b = sources[e2b_path]
    assert OPENCLAW_VERSION in e2b
    assert OPENCLAW_LOCK_SHA256 in e2b
    assert "OPENCLAW_DISABLE_BONJOUR=1" in e2b
    assert 'OPENCLAW_E2B_RUNTIME_ROOT = "/opt/viventium/openclaw-runtime"' in e2b
    assert 'OPENCLAW_LOCK={shlex.quote(f"{OPENCLAW_E2B_RUNTIME_ROOT}/package-lock.json")}' in e2b
    assert 'OPENCLAW_BIN={shlex.quote(f"{OPENCLAW_E2B_RUNTIME_ROOT}/node_modules/.bin/openclaw")}' in e2b

    manager = sources[manager_path]
    assert OPENCLAW_VERSION in manager
    assert 'OPENCLAW_DISABLE_BONJOUR = "1"' in manager
    assert 'os.environ.get("OPENCLAW_RUNTIME", "e2b")' in manager
    assert "OPENCLAW_ALLOW_DIRECT_HOST_EXEC" in manager
    assert '"OPENCLAW_RUNTIME_ALLOW_FALLBACK", "false"' in manager
    assert 'raise ValueError("OPENCLAW_RUNTIME must be direct or e2b")' in manager

    launcher = sources[launcher_path]
    assert OPENCLAW_VERSION in launcher
    assert 'OPENCLAW_REQUIRED_NODE_VERSION="22.23.1"' in launcher
    assert "nodejs.org/dist/v${OPENCLAW_REQUIRED_NODE_VERSION}" in launcher
    assert "ef28d8fab2c0e4314522d4bb1b7173270aa3937e93b92cb7de79c112ac1fa953" in launcher
    assert "b8da981b8a0b1241b70249204916da76c63573ddf5814dbd2d1e41069105cb81" in launcher
    assert OPENCLAW_LOCK_SHA256 in launcher
    assert "export OPENCLAW_DISABLE_BONJOUR=1" in launcher
    assert "export FASTMCP_CHECK_FOR_UPDATES=off" in launcher
    assert "npm ci --omit=dev" in launcher
    assert "OPENCLAW_RUNTIME_LOCK_DIR" in launcher
    assert "OPENCLAW_PYTHON_LOCK_SHA256" in launcher
    assert "pip install --disable-pip-version-check --require-hashes" in launcher
    assert "pip3 install" not in launcher
    assert 'OPENCLAW_ISOLATION_TIER:-e2b' in launcher
    native_start = _extract_shell_function(launcher, "start_native")
    assert "ensure_bridge_secret" in native_start


def test_openclaw_launch_output_never_prints_secret_prefixes() -> None:
    launcher = _read("viventium_v0_4/viventium-openclaw-bridge-start.sh")
    manager = _read("viventium_v0_4/MCPs/openclaw-bridge/openclaw_manager.py")
    assert "ANTHROPIC_API_KEY:0:" not in launcher
    assert 'Anthropic Key:    ${GREEN}Configured${NC}' in launcher
    assert '" ".join(cmd)' not in manager


def test_voice_launcher_never_prints_secret_or_provider_key_prefixes() -> None:
    launcher = _read("viventium_v0_4/viventium-librechat-start.sh")

    assert "_secret_mask" not in launcher
    assert "VIVENTIUM_CALL_SESSION_SECRET:0:" not in launcher
    for variable in (
        "OPENAI_API_KEY",
        "ELEVEN_API_KEY",
        "ELEVEN_API_KEY_FINAL",
        "XAI_API_KEY",
        "CARTESIA_API_KEY",
    ):
        assert f"${{{variable}:0:" not in launcher


def test_voice_call_diagnostics_never_emit_user_or_session_payloads() -> None:
    route = _read("viventium_v0_4/LibreChat/api/server/routes/viventium/calls.js")
    service = _read(
        "viventium_v0_4/LibreChat/api/server/services/viventium/CallSessionService.js"
    )
    button = _read("viventium_v0_4/LibreChat/client/src/components/Viventium/CallButton.tsx")

    assert "console." not in route
    assert "console." not in button
    diagnostic_calls = "\n".join(
        call
        for source in (route, service, button)
        for call in _extract_javascript_logging_calls(source)
    )
    assert "logger." in diagnostic_calls
    diagnostic_calls = diagnostic_calls.replace(
        "hasConversationId: typeof conversationId === 'string' && conversationId !== 'new'",
        "hasConversationId: [presence-only]",
    ).replace(
        "hasAgentId: typeof agentId === 'string' && agentId.length > 0",
        "hasAgentId: [presence-only]",
    )
    for forbidden in (
        "req.",
        "session.",
        "userId",
        "agentId",
        "callSessionId",
        "conversationId",
        "roomName",
        "Session created:",
        "Response:",
    ):
        assert forbidden not in diagnostic_calls


def test_skyvern_runtime_images_are_immutable() -> None:
    compose = _read("viventium_v0_4/docker/skyvern/docker-compose.yml")
    for image in SKYVERN_IMAGES:
        assert f"image: {image}" in compose
    assert "postgres:14-alpine" not in compose
    assert "public.ecr.aws/skyvern/skyvern:latest" not in compose
    assert "public.ecr.aws/skyvern/skyvern-ui:latest" not in compose


def test_livekit_runtime_image_is_immutable_and_release_locked() -> None:
    launcher = _read("viventium_v0_4/viventium-librechat-start.sh")
    manifest = json.loads(_read("release/optional-runtime-components.json"))
    livekit = manifest["livekit_server"]

    assert livekit["version"] == "v1.13.4"
    assert livekit["source_commit"] == LIVEKIT_SOURCE_COMMIT
    assert livekit["image"] == LIVEKIT_IMAGE
    assert livekit["publisher_signature"] == "not_provided"
    assert livekit["provenance"] == "slsa-v1-per-platform"
    assert LIVEKIT_IMAGE in launcher
    assert '"viventium.livekit.image=${LIVEKIT_SERVER_IMAGE}"' in launcher
    assert '"viventium.livekit.source=${LIVEKIT_SERVER_SOURCE_COMMIT}"' in launcher
    assert "docker image inspect livekit/livekit-server" not in launcher
    assert "elif ! docker image inspect" not in launcher
    assert "\n              livekit/livekit-server\n" not in launcher


def _run_legacy_voice_launcher(
    tmp_path: Path,
    *args: str,
    include_canonical: bool = True,
) -> subprocess.CompletedProcess[str]:
    launcher_dir = tmp_path / "viventium_v0_4"
    launcher_dir.mkdir(exist_ok=True)
    legacy_launcher = launcher_dir / "viventium-start-all.sh"
    legacy_launcher.write_text(
        _read("viventium_v0_4/viventium-start-all.sh"),
        encoding="utf-8",
    )
    legacy_launcher.chmod(0o755)

    capture_path = tmp_path / "canonical-args.txt"
    capture_path.unlink(missing_ok=True)
    canonical_launcher = launcher_dir / "viventium-librechat-start.sh"
    if include_canonical:
        canonical_launcher.write_text(
            "#!/bin/bash\nprintf '%s\\n' \"$@\" > \"$VIVENTIUM_LEGACY_LAUNCHER_CAPTURE\"\n",
            encoding="utf-8",
        )
        canonical_launcher.chmod(0o755)

    return subprocess.run(
        [str(legacy_launcher), *args],
        cwd=tmp_path,
        env={
            **os.environ,
            "VIVENTIUM_LEGACY_LAUNCHER_CAPTURE": str(capture_path),
        },
        check=False,
        capture_output=True,
        text=True,
    )


def test_legacy_voice_launcher_delegates_to_locked_modern_runtime(tmp_path: Path) -> None:
    launcher = _read("viventium_v0_4/viventium-start-all.sh")

    completed = _run_legacy_voice_launcher(tmp_path)
    captured = (tmp_path / "canonical-args.txt").read_text(encoding="utf-8").splitlines()

    assert completed.returncode == 0, completed.stderr
    assert captured == ["--modern-playground"]

    completed = _run_legacy_voice_launcher(tmp_path, "--no-playground")
    captured = (tmp_path / "canonical-args.txt").read_text(encoding="utf-8").splitlines()

    assert completed.returncode == 0, completed.stderr
    assert captured == ["--modern-playground", "--skip-playground"]
    assert "viventium-librechat-start.sh" in launcher
    assert "livekit/livekit-server" not in launcher
    assert "docker run" not in launcher
    assert "npm install" not in launcher
    assert "npm ci" not in launcher
    assert "cat >>" not in launcher
    assert "pkill" not in launcher
    assert "LiveKit Agents Playground" not in launcher


def test_active_voice_guide_names_the_modern_playground_as_the_default() -> None:
    voice_guide = _read("viventium_v0_4/docs/VOICE_CALLS.md")

    assert "Viventium Modern Playground (`agent-starter-react`)" in voice_guide
    assert "The Viventium Modern Playground connects" in voice_guide
    assert "design intentionally opens the LiveKit Agents Playground" not in voice_guide
    assert "The LiveKit Agents Playground connects" not in voice_guide


def test_active_feature_docs_name_modern_playground_as_default() -> None:
    no_response = _read("docs/requirements_and_learnings/21_No_Response_Feature.md")
    citations = _read("docs/requirements_and_learnings/08_Citation_Rendering.md")

    assert "Viventium Modern Playground (`agent-starter-react`)" in no_response
    assert "LiveKit Agents Playground" not in no_response
    assert "LiveKit Playground UI" not in no_response
    assert "Modern playground sanitization (`agent-starter-react`, default)" in citations
    assert (
        "Classic playground sanitization (`agents-playground`, explicit opt-in fallback)"
        in citations
    )
    assert "Viventium Modern Playground chat display (default browser voice UI)" in citations


def test_legacy_voice_launcher_rejects_dependency_mutation_flags(tmp_path: Path) -> None:
    for flag in ("--build", "--clean", "--install-deps"):
        completed = _run_legacy_voice_launcher(tmp_path, flag)

        assert completed.returncode != 0
        assert "no longer supported" in completed.stderr
        assert "viventium-librechat-start.sh" in completed.stderr
        assert not (tmp_path / "canonical-args.txt").exists()


def test_legacy_voice_launcher_fails_closed_on_unknown_option_or_missing_owner(
    tmp_path: Path,
) -> None:
    unknown_root = tmp_path / "unknown"
    unknown_root.mkdir()
    completed = _run_legacy_voice_launcher(unknown_root, "--classic-playground")

    assert completed.returncode != 0
    assert "unknown legacy launcher option" in completed.stderr
    assert not (unknown_root / "canonical-args.txt").exists()

    missing_root = tmp_path / "missing"
    missing_root.mkdir()
    completed = _run_legacy_voice_launcher(missing_root, include_canonical=False)

    assert completed.returncode != 0
    assert "canonical Viventium launcher is missing or not executable" in completed.stderr
    assert not (missing_root / "canonical-args.txt").exists()


def test_native_livekit_never_executes_an_unverified_path_binary() -> None:
    launcher = _read("viventium_v0_4/viventium-librechat-start.sh")
    native_stack = _read("scripts/viventium/native_stack.sh")
    cli = _read("bin/viventium")
    startup = _livekit_startup_block()

    assert "livekit_native_binary_path" not in launcher
    assert "start_native_livekit_fallback" not in launcher
    assert "command -v livekit-server" not in launcher
    assert "command -v livekit" not in launcher
    assert "ensure_livekit_binary" not in native_stack
    assert "command -v livekit-server" not in native_stack
    assert "command -v livekit" not in native_stack
    assert "Native LiveKit startup is not a verified release path" in native_stack
    native_start_case = native_stack.split('  start)', maxsplit=1)[1].split(
        "    ;;", maxsplit=1
    )[0]
    assert native_start_case.index("validate_native_livekit_startup") < native_start_case.index(
        "start_mongo"
    )
    assert "VIVENTIUM_NATIVE_STACK_SKIP_LIVEKIT=1" in cli
    assert "VIVENTIUM_INSTALL_MODE" not in startup
    assert "require_cmd docker" in startup
    assert '"$LIVEKIT_SERVER_IMAGE"' in startup
    assert "using external LiveKit if available" not in startup
    assert "refusing to treat it as LiveKit" in startup
    assert "Configured LiveKit endpoint did not respond" in startup
    assert startup.index("Configured LiveKit endpoint did not respond") < startup.index(
        "require_cmd docker"
    )
    assert (
        "Voice needs the exact Viventium LiveKit Docker runtime or a deliberately configured "
        "external LiveKit endpoint."
    ) in launcher
    assert "Use --skip-livekit to start without Voice." in launcher


def test_native_no_docker_path_fails_before_path_livekit_can_run(tmp_path: Path) -> None:
    marker = tmp_path / "path-livekit-ran"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_livekit = fake_bin / "livekit-server"
    fake_livekit.write_text(
        f"#!/bin/sh\ntouch '{marker}'\n",
        encoding="utf-8",
    )
    fake_livekit.chmod(0o755)
    script = f"""
set -u
SKIP_LIVEKIT=false
SKIP_DOCKER=true
LIVEKIT_API_HOST_WAS_CONFIGURED=true
LIVEKIT_API_HOST=http://127.0.0.1:17880
wait_for_http() {{ return 1; }}
log_error() {{ printf '%s\n' "$*"; }}
log_success() {{ printf '%s\n' "$*"; }}
{_livekit_startup_block()}
"""
    completed = subprocess.run(
        ["/bin/bash", "-c", script],
        cwd=ROOT,
        env={**os.environ, "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}"},
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    assert not marker.exists()
    assert "Voice needs the exact Viventium LiveKit Docker runtime" in completed.stdout
    assert "Use --skip-livekit to start without Voice" in completed.stdout


def test_skip_docker_rejects_an_implicit_default_livekit_listener(tmp_path: Path) -> None:
    probe_marker = tmp_path / "endpoint-probed"
    script = f"""
set -u
SKIP_LIVEKIT=false
SKIP_DOCKER=true
LIVEKIT_API_HOST_WAS_CONFIGURED=false
LIVEKIT_API_HOST=http://127.0.0.1:17880
wait_for_http() {{ touch '{probe_marker}'; return 0; }}
log_error() {{ printf '%s\n' "$*"; }}
log_success() {{ printf '%s\n' "$*"; }}
{_livekit_startup_block()}
"""
    completed = subprocess.run(
        ["/bin/bash", "-c", script],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    assert not probe_marker.exists()
    assert "No external LiveKit endpoint was configured" in completed.stdout


def test_compiler_generated_local_livekit_endpoint_starts_locked_runtime_when_cold(
    tmp_path: Path,
) -> None:
    launcher = _read("viventium_v0_4/viventium-librechat-start.sh")
    ownership_def = _extract_shell_function(
        launcher, "livekit_api_host_is_managed_local"
    )
    compiler_path = ROOT / "scripts" / "viventium" / "config_compiler.py"
    spec = importlib.util.spec_from_file_location(
        "viventium_config_compiler", compiler_path
    )
    assert spec is not None and spec.loader is not None
    compiler = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(compiler)
    config = compiler.load_yaml(ROOT / "config.minimal.example.yaml")
    runtime_env = compiler.render_runtime_env(
        config, compiler.build_agent_assignments(config)
    )
    livekit_http_port = runtime_env["LIVEKIT_HTTP_PORT"]
    livekit_api_host = runtime_env["LIVEKIT_API_HOST"]
    assert livekit_api_host == f"http://localhost:{livekit_http_port}"

    docker_log = tmp_path / "docker.log"
    state_root = tmp_path / "state"
    script = f"""
set -u
SKIP_LIVEKIT=false
SKIP_DOCKER=false
LIVEKIT_HTTP_PORT={livekit_http_port}
LIVEKIT_TCP_PORT=17881
LIVEKIT_UDP_PORT=17882
LIVEKIT_API_HOST={livekit_api_host!r}
LIVEKIT_API_HOST_WAS_CONFIGURED=true
VIVENTIUM_RUNTIME_PROFILE=isolated
VIVENTIUM_STATE_ROOT='{state_root}'
VIVENTIUM_LIVEKIT_RUNTIME_OWNER=synthetic-owner
LIVEKIT_NODE_IP=127.0.0.1
LIVEKIT_SERVER_VERSION=v1.13.4
LIVEKIT_SERVER_SOURCE_COMMIT='{LIVEKIT_SOURCE_COMMIT}'
LIVEKIT_SERVER_IMAGE='{LIVEKIT_IMAGE}'
LIVEKIT_STARTED_BY_SCRIPT=false
LIVEKIT_CONTAINER_ID=''
LIVEKIT_TURN_DOMAIN=''
LIVEKIT_TURN_TLS_PORT=''
LIVEKIT_TURN_CERT_FILE=''
LIVEKIT_TURN_KEY_FILE=''
RED=''
GREEN=''
YELLOW=''
CYAN=''
NC=''
curl() {{ return 1; }}
require_cmd() {{ :; }}
docker_daemon_ready() {{ return 0; }}
docker() {{
  printf '%s\\n' "$*" >>'{docker_log}'
  if [[ "$1" == "run" ]]; then printf 'locked-container-id\\n'; fi
}}
port_in_use() {{ return 1; }}
write_livekit_config() {{ : >"$1"; }}
wait_for_http() {{ return 0; }}
livekit_managed_container_matches_release() {{ return 0; }}
log_error() {{ printf '%s\\n' "$*"; }}
log_success() {{ printf '%s\\n' "$*"; }}
log_warn() {{ printf '%s\\n' "$*"; }}
request_docker_desktop_launch() {{ :; }}
{ownership_def}
{_livekit_selector_defs()}
if livekit_api_host_is_managed_local "$LIVEKIT_API_HOST"; then
  LIVEKIT_API_HOST_WAS_CONFIGURED=false
fi
{_livekit_startup_block()}
"""
    completed = subprocess.run(
        ["/bin/bash", "-c", script],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    commands = docker_log.read_text(encoding="utf-8")
    assert "run -d" in commands
    assert LIVEKIT_IMAGE in commands
    assert f"viventium.livekit.image={LIVEKIT_IMAGE}" in commands
    assert f"viventium.livekit.source={LIVEKIT_SOURCE_COMMIT}" in commands
    assert "Configured LiveKit endpoint did not respond" not in completed.stdout


def test_unhealthy_configured_livekit_fails_before_docker_fallback(tmp_path: Path) -> None:
    launcher = _read("viventium_v0_4/viventium-librechat-start.sh")
    ownership_def = _extract_shell_function(
        launcher, "livekit_api_host_is_managed_local"
    )
    docker_marker = tmp_path / "docker-ran"
    script = f"""
set -u
SKIP_LIVEKIT=false
SKIP_DOCKER=false
LIVEKIT_HTTP_PORT=17880
LIVEKIT_API_HOST=http://127.0.0.1:17880
LIVEKIT_API_HOST_WAS_CONFIGURED=false
curl() {{ return 1; }}
docker() {{ touch '{docker_marker}'; return 1; }}
log_error() {{ printf '%s\n' "$*"; }}
log_success() {{ printf '%s\n' "$*"; }}
{ownership_def}
if ! livekit_api_host_is_managed_local "$LIVEKIT_API_HOST"; then
  LIVEKIT_API_HOST_WAS_CONFIGURED=true
fi
{_livekit_startup_block()}
"""
    completed = subprocess.run(
        ["/bin/bash", "-c", script],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    assert not docker_marker.exists()
    assert "Configured LiveKit endpoint did not respond" in completed.stdout
    assert "refusing an implicit runtime fallback" in completed.stdout


def test_unconfigured_livekit_port_collision_is_preserved_and_rejected(tmp_path: Path) -> None:
    listener_marker = tmp_path / "unrelated-listener"
    listener_marker.write_text("preserve", encoding="utf-8")
    docker_log = tmp_path / "docker.log"
    script = f"""
set -u
SKIP_LIVEKIT=false
SKIP_DOCKER=false
LIVEKIT_API_HOST_WAS_CONFIGURED=false
LIVEKIT_API_HOST=http://127.0.0.1:17880
VIVENTIUM_RUNTIME_PROFILE=isolated
VIVENTIUM_LIVEKIT_RUNTIME_OWNER=synthetic-owner
LIVEKIT_HTTP_PORT=17880
require_cmd() {{ :; }}
docker_daemon_ready() {{ return 0; }}
docker() {{ printf '%s\n' "$*" >>'{docker_log}'; }}
port_in_use() {{ return 0; }}
log_error() {{ printf '%s\n' "$*"; }}
log_success() {{ printf '%s\n' "$*"; }}
log_warn() {{ printf '%s\n' "$*"; }}
{_livekit_selector_defs()}
{_livekit_startup_block()}
"""
    completed = subprocess.run(
        ["/bin/bash", "-c", script],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    assert listener_marker.read_text(encoding="utf-8") == "preserve"
    assert "refusing to treat it as LiveKit" in completed.stdout
    assert "run -d" not in docker_log.read_text(encoding="utf-8")


def test_stale_managed_livekit_container_is_never_silently_reused() -> None:
    launcher = _read("viventium_v0_4/viventium-librechat-start.sh")
    assert "livekit_managed_container_matches_release" in launcher
    assert "Replacing stale managed LiveKit container" in launcher
    assert 'docker rm -f "$EXISTING"' in launcher


def test_livekit_release_identity_requires_image_and_source_labels() -> None:
    launcher = _read("viventium_v0_4/viventium-librechat-start.sh")
    function_def = _extract_shell_function(
        launcher, "livekit_managed_container_matches_release"
    )
    script = f"""
set -euo pipefail
LIVEKIT_SERVER_IMAGE='{LIVEKIT_IMAGE}'
LIVEKIT_SERVER_SOURCE_COMMIT='{LIVEKIT_SOURCE_COMMIT}'
LIVEKIT_HTTP_PORT=17880
MOCK_SOURCE='{LIVEKIT_SOURCE_COMMIT}'
MOCK_HTTP_PORT="$LIVEKIT_HTTP_PORT"
docker() {{
  case "$3" in
    *Config.Image*) printf '%s\\n' "$LIVEKIT_SERVER_IMAGE" ;;
    *viventium.livekit.image*) printf '%s\\n' "$LIVEKIT_SERVER_IMAGE" ;;
    *viventium.livekit.source*) printf '%s\\n' "$MOCK_SOURCE" ;;
    *viventium.livekit.http-port*) printf '%s\\n' "$MOCK_HTTP_PORT" ;;
    *) return 1 ;;
  esac
}}
livekit_container_has_configured_http_port() {{ return 0; }}
{function_def}
livekit_managed_container_matches_release exact && printf 'exact\\n'
MOCK_SOURCE='stale-source'
if livekit_managed_container_matches_release stale; then
  printf 'unsafe-reuse\\n'
else
  printf 'rejected\\n'
fi
MOCK_SOURCE='{LIVEKIT_SOURCE_COMMIT}'
MOCK_HTTP_PORT=27880
if livekit_managed_container_matches_release stale-port; then
  printf 'unsafe-port-reuse\\n'
else
  printf 'port-rejected\\n'
fi
"""
    completed = subprocess.run(
        ["bash", "-lc", script],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert completed.stdout.splitlines() == ["exact", "rejected", "port-rejected"]


def test_livekit_runtime_owner_identity_is_stable_and_path_private() -> None:
    launcher = _read("viventium_v0_4/viventium-librechat-start.sh")
    function_def = _extract_shell_function(launcher, "livekit_runtime_owner_id")
    script = f"""
set -euo pipefail
{function_def}
first="$(livekit_runtime_owner_id /tmp/viventium-a/state)"
repeat="$(livekit_runtime_owner_id /tmp/viventium-a/state)"
second="$(livekit_runtime_owner_id /tmp/viventium-b/state)"
printf '%s\\n%s\\n%s\\n' "$first" "$repeat" "$second"
"""
    completed = subprocess.run(
        ["bash", "-lc", script],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    first, repeat, second = completed.stdout.splitlines()
    assert first == repeat
    assert first != second
    assert len(first) == 64
    assert all(character in "0123456789abcdef" for character in first)
    assert "/tmp/" not in completed.stdout


def test_livekit_runtime_selector_never_adopts_another_runtime_owner() -> None:
    launcher = _read("viventium_v0_4/viventium-librechat-start.sh")
    selector_defs = _livekit_selector_defs()
    script = f"""
set -euo pipefail
VIVENTIUM_RUNTIME_PROFILE=isolated
VIVENTIUM_LIVEKIT_RUNTIME_OWNER=owner-a
LIVEKIT_HTTP_PORT=17880
GLOBAL_DOCKER_CLEANUP_ALLOWED=true
docker() {{
  if [[ "$1" == "ps" ]]; then
    case "$*" in
      *"label=viventium.runtime-owner=owner-a"*) printf 'owned-a\\n' ;;
      *"label=viventium.runtime-owner=owner-c"*) : ;;
      *"name=^/viventium-livekit-isolated-"*)
        printf 'foreign-b\\nunrelated-matching\\nlegacy-matching\\nlegacy-other-port\\n'
        ;;
      *) : ;;
    esac
    return 0
  fi
  if [[ "$1" == "inspect" ]]; then
    case "$*" in
      *viventium.runtime-owner*foreign-b) printf 'owner-b\\n' ;;
      *viventium.runtime-owner*) printf '\\n' ;;
      *viventium.stack*legacy-matching|*viventium.stack*legacy-other-port)
        printf 'viventium_v0_4\\n'
        ;;
      *viventium.service*legacy-matching|*viventium.service*legacy-other-port)
        printf 'livekit\\n'
        ;;
      *viventium.profile*legacy-matching|*viventium.profile*legacy-other-port)
        printf 'isolated\\n'
        ;;
      *) printf '\\n' ;;
    esac
    return 0
  fi
  if [[ "$1" == "port" ]]; then
    case "$2" in
      unrelated-matching) printf '0.0.0.0:17880\\n' ;;
      legacy-matching) printf '0.0.0.0:17880\\n' ;;
      legacy-other-port) printf '0.0.0.0:27880\\n' ;;
      *) return 1 ;;
    esac
    return 0
  fi
  return 1
}}
{selector_defs}
printf 'owner-a:\\n'
livekit_runtime_container_ids running
printf 'owner-c-legacy:\\n'
VIVENTIUM_LIVEKIT_RUNTIME_OWNER=owner-c
livekit_runtime_container_ids running
printf 'owner-c-noncanonical:\\n'
GLOBAL_DOCKER_CLEANUP_ALLOWED=false
livekit_runtime_container_ids running
"""
    completed = subprocess.run(
        ["bash", "-lc", script],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert completed.stdout.splitlines() == [
        "owner-a:",
        "owned-a",
        "owner-c-legacy:",
        "legacy-matching",
        "owner-c-noncanonical:",
    ]


def test_livekit_stop_and_stale_cleanup_are_runtime_owner_scoped() -> None:
    launcher = _read("viventium_v0_4/viventium-librechat-start.sh")
    stop_services = launcher[
        launcher.index("stop_running_services() {") :
        launcher.index("cleanup_stale_containers() {")
    ]
    stale_cleanup = _extract_shell_function(launcher, "cleanup_stale_containers")
    startup = _livekit_startup_block()

    assert "livekit_runtime_container_ids running" in stop_services
    assert "livekit_runtime_container_ids exited" in stale_cleanup
    assert "livekit_runtime_container_ids running" in startup
    assert '--label "viventium.runtime-owner=${VIVENTIUM_LIVEKIT_RUNTIME_OWNER}"' in startup
    assert (
        'livekit_containers="$(livekit_runtime_container_ids running)"'
        in stop_services
    )
    global_stop_guard = stop_services.index(
        'if [[ "$GLOBAL_DOCKER_CLEANUP_ALLOWED" == "true"'
    )
    exact_owner_stop = stop_services.index(
        'livekit_containers="$(livekit_runtime_container_ids running)"'
    )
    native_stop = stop_services.index("stop_recorded_native_mongo_engine")
    assert global_stop_guard < exact_owner_stop < native_stop

    exact_owner_stale = stale_cleanup.index(
        'livekit_stale="$(livekit_runtime_container_ids exited)"'
    )
    global_stale_return = stale_cleanup.index(
        'if [[ "$GLOBAL_DOCKER_CLEANUP_ALLOWED" != "true" ]]; then'
    )
    assert exact_owner_stale < global_stale_return

    failure_cleanup = _extract_shell_function(launcher, "cleanup")
    global_failure_guard = failure_cleanup.index(
        'if [[ "$GLOBAL_DOCKER_CLEANUP_ALLOWED" == "true"'
    )
    exact_owner_failure = failure_cleanup.index(
        'if [[ "$SKIP_DOCKER" != "true" && "$LIVEKIT_STARTED_BY_SCRIPT" == "true"'
    )
    native_failure_cleanup = failure_cleanup.index(
        "stop_recorded_native_mongo_engine"
    )
    assert global_failure_guard < exact_owner_failure < native_failure_cleanup


def test_optional_launchers_reference_existing_owning_docs() -> None:
    for relative in (
        "viventium_v0_4/viventium-openclaw-bridge-start.sh",
        "viventium_v0_4/viventium-skyvern-start.sh",
        "viventium_v0_4/docker/skyvern/docker-compose.yml",
    ):
        source = _read(relative)
        for line in source.splitlines():
            if "Documentation: docs/" not in line:
                continue
            target = line.split("Documentation:", 1)[1].strip()
            assert (ROOT / target).is_file(), f"{relative} points to missing {target}"

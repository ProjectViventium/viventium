from __future__ import annotations

import subprocess
from pathlib import Path
import shlex
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
NATIVE_STACK_PATH = REPO_ROOT / "scripts" / "viventium" / "native_stack.sh"
CLI_PATH = REPO_ROOT / "bin" / "viventium"


def extract_shell_function(text: str, name: str) -> str:
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.strip() == f"{name}() {{":
            start = index
            break
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


def test_easy_install_missing_mongodb_hint_uses_supported_preflight_flag() -> None:
    script_text = NATIVE_STACK_PATH.read_text(encoding="utf-8")
    function_def = extract_shell_function(script_text, "verify_express_mongod_binary")

    assert "bin/viventium preflight --apply" in function_def
    assert "bin/viventium preflight --fix" not in function_def


def test_configure_easy_install_applies_missing_prerequisites_before_success() -> None:
    cli_text = CLI_PATH.read_text(encoding="utf-8")
    function_def = extract_shell_function(cli_text, "ensure_configured_prerequisites")

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                "express_install_experience() { return 0; }\n"
                "run_preflight() { printf 'preflight:%s\\n' \"$1\"; }\n"
                f"{function_def}"
                "ensure_configured_prerequisites\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert "preflight:apply" in completed.stdout
    command_cases = cli_text.split('case "$COMMAND" in', 1)[1]
    configure_section = command_cases.split("  configure|wizard)", 1)[1].split(
        "  bootstrap-components)", 1
    )[0]
    assert configure_section.index("compile_config") < configure_section.index(
        "ensure_configured_prerequisites"
    )


def test_express_native_can_skip_meilisearch_without_changing_stop_cleanup() -> None:
    script_text = NATIVE_STACK_PATH.read_text(encoding="utf-8")
    start_case = script_text.split("case \"${1:-}\" in", 1)[1].split("  stop)", 1)[0]
    stop_case = script_text.split("  stop)", 1)[1].split("    ;;", 1)[0]

    assert 'NATIVE_STACK_SKIP_MEILI="${VIVENTIUM_NATIVE_STACK_SKIP_MEILI:-0}"' in script_text
    assert 'if [[ "$NATIVE_STACK_SKIP_MEILI" != "1" ]]; then' in start_case
    assert "start_meili" in start_case
    assert (
        'stop_pid_file_if_matches "$MEILI_PID_FILE" "Meilisearch" '
        "meili_process_matches_expected"
    ) in stop_case


def test_native_mongo_stop_requires_a_fresh_running_engine_receipt() -> None:
    script_text = NATIVE_STACK_PATH.read_text(encoding="utf-8")
    function_def = extract_shell_function(
        script_text,
        "stop_recorded_native_mongo_engine",
    )

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                "MONGO_PID_FILE='/tmp/synthetic-mongod.pid'\n"
                "run_mongo_engine_identity() { printf 'identity:%s\\n' \"$*\"; }\n"
                f"{function_def}"
                "MONGO_ENGINE_IDENTITY_PREPARED=false\n"
                "stop_recorded_native_mongo_engine\n"
                "MONGO_ENGINE_IDENTITY_PREPARED=true\n"
                "stop_recorded_native_mongo_engine\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert completed.stdout.splitlines() == [
        "identity:stop-recorded-native-engine --pid-file /tmp/synthetic-mongod.pid"
    ]


def test_livekit_meta_matches_expected_accepts_matching_runtime_meta(tmp_path: Path) -> None:
    script_text = NATIVE_STACK_PATH.read_text(encoding="utf-8")
    function_def = extract_shell_function(script_text, "livekit_meta_matches_expected")
    meta_file = tmp_path / "livekit.runtime.env"
    meta_file.write_text(
        "\n".join(
            [
                "LIVEKIT_NODE_IP=192.0.2.10",
                "LIVEKIT_HTTP_PORT=7888",
                "LIVEKIT_TCP_PORT=7889",
                "LIVEKIT_UDP_PORT=7890",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                f"LIVEKIT_META_FILE='{meta_file}'\n"
                "LIVEKIT_NODE_IP='192.0.2.10'\n"
                "LIVEKIT_HTTP_PORT='7888'\n"
                "LIVEKIT_TCP_PORT='7889'\n"
                "LIVEKIT_UDP_PORT='7890'\n"
                "LIVEKIT_TURN_DOMAIN=''\n"
                "LIVEKIT_TURN_TLS_PORT=''\n"
                "LIVEKIT_TURN_CERT_FILE=''\n"
                "LIVEKIT_TURN_KEY_FILE=''\n"
                f"{function_def}"
                "if livekit_meta_matches_expected; then printf 'match\\n'; else printf 'mismatch\\n'; fi\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert completed.stdout.strip() == "match"


def test_detect_livekit_node_ip_prefers_lan_interface_address() -> None:
    script_text = NATIVE_STACK_PATH.read_text(encoding="utf-8")
    function_def = extract_shell_function(script_text, "detect_livekit_node_ip")

    completed = subprocess.run(
        [
            "bash",
            "-lc",
                (
                    "set -euo pipefail\n"
                    "unset LIVEKIT_NODE_IP\n"
                    "route() { printf '   interface: en7\\n'; }\n"
                "ipconfig() {\n"
                "  if [[ \"$1\" == \"getifaddr\" && \"$2\" == \"en7\" ]]; then\n"
                "    printf '192.0.2.10\\n'\n"
                "    return 0\n"
                "  fi\n"
                "  return 1\n"
                "}\n"
                f"{function_def}"
                "detect_livekit_node_ip\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert completed.stdout.strip() == "192.0.2.10"


def test_detect_livekit_node_ip_falls_back_to_loopback() -> None:
    script_text = NATIVE_STACK_PATH.read_text(encoding="utf-8")
    function_def = extract_shell_function(script_text, "detect_livekit_node_ip")

    completed = subprocess.run(
        [
            "bash",
            "-lc",
                (
                    "set -euo pipefail\n"
                    "unset LIVEKIT_NODE_IP\n"
                    "route() { return 1; }\n"
                "ipconfig() { return 1; }\n"
                "hostname() { return 1; }\n"
                f"{function_def}"
                "detect_livekit_node_ip\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert completed.stdout.strip() == "127.0.0.1"


def test_ensure_soft_open_file_limit_raises_low_soft_limit() -> None:
    script_text = NATIVE_STACK_PATH.read_text(encoding="utf-8")
    function_def = extract_shell_function(script_text, "ensure_soft_open_file_limit")

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                "soft_limit=256\n"
                "ulimit() {\n"
                "  if [[ \"$#\" -eq 1 && \"$1\" == \"-n\" ]]; then printf '%s\\n' \"$soft_limit\"; return 0; fi\n"
                "  if [[ \"$#\" -eq 1 && \"$1\" == \"-Hn\" ]]; then printf 'unlimited\\n'; return 0; fi\n"
                "  if [[ \"$#\" -eq 2 && \"$1\" == \"-Sn\" ]]; then soft_limit=\"$2\"; return 0; fi\n"
                "  return 1\n"
                "}\n"
                f"{function_def}"
                "ensure_soft_open_file_limit 65536 >/tmp/out\n"
                "cat /tmp/out\n"
                "printf 'soft=%s\\n' \"$soft_limit\"\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert "Raised max open files soft limit to 65536" in completed.stdout
    assert "soft=65536" in completed.stdout


def test_ensure_soft_open_file_limit_is_noop_when_already_high() -> None:
    script_text = NATIVE_STACK_PATH.read_text(encoding="utf-8")
    function_def = extract_shell_function(script_text, "ensure_soft_open_file_limit")

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                "soft_limit=65536\n"
                "ulimit() {\n"
                "  if [[ \"$#\" -eq 1 && \"$1\" == \"-n\" ]]; then printf '%s\\n' \"$soft_limit\"; return 0; fi\n"
                "  if [[ \"$#\" -eq 1 && \"$1\" == \"-Hn\" ]]; then printf 'unlimited\\n'; return 0; fi\n"
                "  if [[ \"$#\" -eq 2 && \"$1\" == \"-Sn\" ]]; then soft_limit=\"$2\"; return 0; fi\n"
                "  return 1\n"
                "}\n"
                f"{function_def}"
                "ensure_soft_open_file_limit 65536 >/tmp/out\n"
                "cat /tmp/out\n"
                "printf 'soft=%s\\n' \"$soft_limit\"\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert completed.stdout.strip() == "soft=65536"


def test_mongo_listener_data_dir_reads_the_running_server_dbpath() -> None:
    script_text = NATIVE_STACK_PATH.read_text(encoding="utf-8")
    function_def = extract_shell_function(script_text, "mongo_listener_data_dir")

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                "MONGO_HOST='127.0.0.1'\n"
                "MONGO_PORT='27117'\n"
                "mongosh() { printf '/tmp/viventium-mongo-data\\n'; }\n"
                f"{function_def}"
                "mongo_listener_data_dir\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert completed.stdout.strip() == "/tmp/viventium-mongo-data"


def test_mongo_listener_matches_only_the_configured_data_dir(tmp_path: Path) -> None:
    script_text = NATIVE_STACK_PATH.read_text(encoding="utf-8")
    function_names = [
        "canonical_existing_dir",
        "mongo_listener_matches_expected",
    ]
    defs = "".join(extract_shell_function(script_text, name) for name in function_names)
    expected_dir = tmp_path / "expected"
    foreign_dir = tmp_path / "foreign"
    expected_dir.mkdir()
    foreign_dir.mkdir()

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                f"MONGO_DATA_DIR='{expected_dir}'\n"
                f"{defs}"
                f"mongo_listener_data_dir() {{ printf '{foreign_dir}\\n'; }}\n"
                "if mongo_listener_matches_expected; then printf 'match\\n'; else printf 'mismatch\\n'; fi\n"
                f"mongo_listener_data_dir() {{ printf '{expected_dir}\\n'; }}\n"
                "if mongo_listener_matches_expected; then printf 'match\\n'; else printf 'mismatch\\n'; fi\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert completed.stdout.strip().splitlines() == ["mismatch", "match"]


def test_start_mongo_refuses_a_listener_with_unexpected_persistence_identity() -> None:
    script_text = NATIVE_STACK_PATH.read_text(encoding="utf-8")
    function_def = extract_shell_function(script_text, "start_mongo")

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                "MONGO_PORT='27117'\n"
                "MONGO_PID_FILE='/tmp/viventium-synthetic-mongod.pid'\n"
                "port_listening() { return 0; }\n"
                "resolve_unique_listener_pid() { printf '222\\n'; }\n"
                "mongo_process_matches_expected() { return 0; }\n"
                "mongo_listener_matches_expected() { return 1; }\n"
                f"{function_def}"
                "start_mongo\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert "refusing to use an unexpected persistence store" in completed.stderr


def test_start_mongo_reuses_a_listener_with_matching_persistence_identity() -> None:
    script_text = NATIVE_STACK_PATH.read_text(encoding="utf-8")
    function_def = extract_shell_function(script_text, "start_mongo")

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                "MONGO_PORT='27117'\n"
                "MONGO_PID_FILE='/tmp/viventium-synthetic-mongod.pid'\n"
                "port_listening() { return 0; }\n"
                "resolve_unique_listener_pid() { printf '222\\n'; }\n"
                "mongo_process_matches_expected() { return 0; }\n"
                "mongo_listener_matches_expected() { return 0; }\n"
                "write_pid() { :; }\n"
                f"{function_def}"
                "start_mongo\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert "verified configured persistence identity" in completed.stdout


def test_express_mongo_binary_selection_never_falls_back_to_homebrew(tmp_path: Path) -> None:
    script_text = NATIVE_STACK_PATH.read_text(encoding="utf-8")
    function_def = extract_shell_function(script_text, "select_mongod_binary")
    brew_marker = tmp_path / "brew-called"

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                "VIVENTIUM_INSTALL_EXPERIENCE='express'\n"
                "MONGODB_NATIVE_BINARY='/missing/pinned/mongod'\n"
                f"BREW_MARKER='{brew_marker}'\n"
                "verify_express_mongod_binary() { return 1; }\n"
                "ensure_brew_pkg() { printf called >\"$BREW_MARKER\"; return 0; }\n"
                f"{function_def}"
                "if select_mongod_binary >/tmp/mongod-selection.out 2>/tmp/mongod-selection.err; then\n"
                "  printf 'selection=unexpected-success\\n'\n"
                "else\n"
                "  printf 'selection=failed-closed\\n'\n"
                "fi\n"
                "if [[ -e \"$BREW_MARKER\" ]]; then printf 'brew=called\\n'; else printf 'brew=not-called\\n'; fi\n"
                "cat /tmp/mongod-selection.err\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert "selection=failed-closed" in completed.stdout
    assert "brew=not-called" in completed.stdout
    assert "pinned MongoDB" in completed.stdout


def test_livekit_meta_matches_expected_rejects_node_ip_drift(tmp_path: Path) -> None:
    script_text = NATIVE_STACK_PATH.read_text(encoding="utf-8")
    function_def = extract_shell_function(script_text, "livekit_meta_matches_expected")
    meta_file = tmp_path / "livekit.runtime.env"
    meta_file.write_text(
        "\n".join(
            [
                "LIVEKIT_NODE_IP=127.0.0.1",
                "LIVEKIT_HTTP_PORT=7888",
                "LIVEKIT_TCP_PORT=7889",
                "LIVEKIT_UDP_PORT=7890",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                f"LIVEKIT_META_FILE='{meta_file}'\n"
                "LIVEKIT_NODE_IP='192.0.2.10'\n"
                "LIVEKIT_HTTP_PORT='7888'\n"
                "LIVEKIT_TCP_PORT='7889'\n"
                "LIVEKIT_UDP_PORT='7890'\n"
                f"{function_def}"
                "if livekit_meta_matches_expected; then printf 'match\\n'; else printf 'mismatch\\n'; fi\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert completed.stdout.strip() == "mismatch"


def test_managed_livekit_listener_pid_requires_installer_managed_config_path() -> None:
    script_text = NATIVE_STACK_PATH.read_text(encoding="utf-8")
    listener_def = extract_shell_function(script_text, "managed_livekit_listener_pid")
    process_def = extract_shell_function(script_text, "process_command_line")
    command_match_def = extract_shell_function(script_text, "livekit_command_matches_expected")

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                "LIVEKIT_PID_FILE='/tmp/does-not-exist'\n"
                "LIVEKIT_CFG_FILE='/tmp/viventium/livekit/livekit.yaml'\n"
                "pgrep() { printf '4242\\n'; }\n"
                "ps() { printf '/usr/local/bin/livekit-server --config /tmp/other/livekit.yaml --node-ip 127.0.0.1\\n'; }\n"
                f"{process_def}"
                f"{command_match_def}"
                f"{listener_def}"
                "if managed_livekit_listener_pid >/tmp/out 2>/dev/null; then cat /tmp/out; else printf 'unmanaged\\n'; fi\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert completed.stdout.strip() == "unmanaged"


def test_start_livekit_fails_before_an_unverified_path_binary_can_run(tmp_path: Path) -> None:
    script_text = NATIVE_STACK_PATH.read_text(encoding="utf-8")
    function_names = [
        "native_livekit_start_requested",
        "validate_native_livekit_startup",
        "start_livekit",
    ]
    defs = "".join(extract_shell_function(script_text, name) for name in function_names)
    marker = tmp_path / "path-livekit-ran"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_livekit = fake_bin / "livekit-server"
    fake_livekit.write_text(f"#!/bin/sh\ntouch '{marker}'\n", encoding="utf-8")
    fake_livekit.chmod(0o755)

    completed = subprocess.run(
        [
            "/bin/bash",
            "-c",
            (
                "set -euo pipefail\n"
                "VOICE_ENABLED='true'\n"
                "NATIVE_STACK_SKIP_LIVEKIT='0'\n"
                f"{defs}"
                "start_livekit\n"
            ),
        ],
        cwd=REPO_ROOT,
        env={"PATH": f"{fake_bin}:/usr/bin:/bin"},
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 1
    assert not marker.exists()
    assert "Native LiveKit startup is not a verified release path" in completed.stderr
    assert "exact Docker runtime or a configured external endpoint" in completed.stderr


def test_start_livekit_skip_cleanly_delegates_to_the_release_launcher() -> None:
    script_text = NATIVE_STACK_PATH.read_text(encoding="utf-8")
    defs = "".join(
        extract_shell_function(script_text, name)
        for name in (
            "native_livekit_start_requested",
            "validate_native_livekit_startup",
            "start_livekit",
        )
    )

    completed = subprocess.run(
        [
            "/bin/bash",
            "-c",
            (
                "set -euo pipefail\n"
                "VOICE_ENABLED='true'\n"
                "NATIVE_STACK_SKIP_LIVEKIT='1'\n"
                f"{defs}"
                "start_livekit\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0
    assert "launcher will own LiveKit startup" in completed.stdout
    assert completed.stderr == ""


def test_native_stop_refuses_a_stale_pid_that_fails_runtime_identity(tmp_path: Path) -> None:
    script_text = NATIVE_STACK_PATH.read_text(encoding="utf-8")
    function_def = extract_shell_function(script_text, "stop_pid_file_if_matches")
    pid_file = tmp_path / "native.pid"
    pid_file.write_text("4242\n", encoding="utf-8")

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                f"PID_FILE='{pid_file}'\n"
                "kill() { return 0; }\n"
                "process_matches() { return 1; }\n"
                "stop_pid() { printf 'killed:%s\\n' \"$1\"; }\n"
                f"{function_def}"
                "stop_pid_file_if_matches \"$PID_FILE\" 'Synthetic service' process_matches\n"
                "if [[ -f \"$PID_FILE\" ]]; then printf 'pid-file=present\\n'; else printf 'pid-file=removed\\n'; fi\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert "killed:" not in completed.stdout
    assert "Skipping stale Synthetic service PID 4242" in completed.stderr
    assert "pid-file=removed" in completed.stdout


def test_native_identity_reads_full_argv_and_rejects_a_foreign_runtime(tmp_path: Path) -> None:
    script_text = NATIVE_STACK_PATH.read_text(encoding="utf-8")
    function_names = [
        "process_command_line",
        "process_executable_identity",
        "process_executable_basename_matches",
        "mongo_executable_matches_expected",
        "command_line_has_option_value",
        "canonical_existing_dir",
        "mongo_process_matches_expected",
        "meili_process_matches_expected",
    ]
    defs = "".join(extract_shell_function(script_text, name) for name in function_names)
    selected_root = tmp_path / "selected runtime"
    # Keep the foreign data dirs prefixed by the selected dirs to prove
    # ownership checks compare complete argument values, not path substrings.
    selected_mongo = selected_root / "mongo-data"
    selected_meili = selected_root / "meili-data"
    foreign_mongo = Path(f"{selected_mongo}-foreign")
    foreign_meili = Path(f"{selected_meili}-foreign")
    for path in (selected_mongo, selected_meili, foreign_mongo, foreign_meili):
        path.mkdir(parents=True)

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                f"MONGO_DATA_DIR={shlex.quote(str(selected_mongo))}\n"
                "MONGO_PORT='32117'\n"
                f"MEILI_DATA_DIR={shlex.quote(str(selected_meili))}\n"
                "MEILI_HOST='127.0.0.1'\n"
                "MEILI_PORT='12700'\n"
                f"SELECTED_MONGO={shlex.quote(str(selected_mongo))}\n"
                f"SELECTED_MEILI={shlex.quote(str(selected_meili))}\n"
                f"FOREIGN_MONGO={shlex.quote(str(foreign_mongo))}\n"
                f"FOREIGN_MEILI={shlex.quote(str(foreign_meili))}\n"
                "ps() {\n"
                "  if [[ \" $* \" != *' -ww '* ]]; then\n"
                "    printf '/opt/viventium/bin/native-service --identity-output-truncated\\n'\n"
                "    return 0\n"
                "  fi\n"
                "  case \" $* \" in\n"
                "    *' -o comm= '*) printf '/opt/homebrew/bi\\n' ;;\n"
                "    *' -o ucomm= '*)\n"
                "      case \" $* \" in\n"
                "        *' -p 10'* ) printf 'mongod\\n' ;;\n"
                "        *' -p 20'* ) printf 'meilisearch\\n' ;;\n"
                "      esac\n"
                "      ;;\n"
                "    *' -p 101 '*) printf '/opt/viventium/bin/mongod --bind_ip 127.0.0.1 --port 32117 --dbpath %s --logpath /tmp/mongod.log\\n' \"$SELECTED_MONGO\" ;;\n"
                "    *' -p 102 '*) printf '/opt/viventium/bin/mongod --bind_ip 127.0.0.1 --port 32117 --dbpath %s --logpath /tmp/mongod.log\\n' \"$FOREIGN_MONGO\" ;;\n"
                "    *' -p 201 '*) printf '/opt/viventium/bin/meilisearch --http-addr 127.0.0.1:12700 --master-key synthetic --db-path %s --no-analytics\\n' \"$SELECTED_MEILI\" ;;\n"
                "    *' -p 202 '*) printf '/opt/viventium/bin/meilisearch --http-addr 127.0.0.1:12700 --master-key synthetic --db-path %s --no-analytics\\n' \"$FOREIGN_MEILI\" ;;\n"
                "  esac\n"
                "}\n"
                f"{defs}"
                "for pair in 'mongo_process_matches_expected 101 selected-mongo' 'mongo_process_matches_expected 102 foreign-mongo' 'meili_process_matches_expected 201 selected-meili' 'meili_process_matches_expected 202 foreign-meili'; do\n"
                "  set -- $pair\n"
                "  if \"$1\" \"$2\"; then printf '%s=match\\n' \"$3\"; else printf '%s=mismatch\\n' \"$3\"; fi\n"
                "done\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert completed.stdout.strip().splitlines() == [
        "selected-mongo=match",
        "foreign-mongo=mismatch",
        "selected-meili=match",
        "foreign-meili=mismatch",
    ]


def test_native_matchers_reject_reused_pid_lookalikes_and_livekit_prefixes(
    tmp_path: Path,
) -> None:
    script_text = NATIVE_STACK_PATH.read_text(encoding="utf-8")
    function_names = [
        "process_command_line",
        "process_executable_identity",
        "process_executable_basename_matches",
        "mongo_executable_matches_expected",
        "command_line_has_option_value",
        "canonical_existing_dir",
        "mongo_process_matches_expected",
        "meili_process_matches_expected",
        "livekit_command_matches_expected",
    ]
    defs = "".join(extract_shell_function(script_text, name) for name in function_names)
    mongo_data = tmp_path / "selected runtime" / "mongo-data"
    meili_data = tmp_path / "selected runtime" / "meili-data"
    livekit_config = tmp_path / "selected runtime" / "livekit" / "livekit.yaml"
    mongo_data.mkdir(parents=True)
    meili_data.mkdir(parents=True)
    livekit_config.parent.mkdir(parents=True)

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                f"MONGO_DATA_DIR={shlex.quote(str(mongo_data))}\n"
                "MONGO_PORT='32117'\n"
                f"MEILI_DATA_DIR={shlex.quote(str(meili_data))}\n"
                "MEILI_HOST='127.0.0.1'\n"
                "MEILI_PORT='12700'\n"
                f"LIVEKIT_CFG_FILE={shlex.quote(str(livekit_config))}\n"
                "LIVEKIT_NODE_IP='192.0.2.10'\n"
                "VIVENTIUM_INSTALL_EXPERIENCE='legacy'\n"
                "MONGODB_NATIVE_BINARY='/opt/viventium/pinned/mongod'\n"
                "ps() {\n"
                "  case \" $* \" in\n"
                "    *' -o comm= '*) printf '/opt/homebrew/bi\\n' ;;\n"
                "    *' -o ucomm= '*)\n"
                "      case \" $* \" in\n"
                "        *' -p 301 '*) printf 'mongod-wrapper\\n' ;;\n"
                "        *' -p 302 '*) printf 'meilisearch-helper\\n' ;;\n"
                "        *' -p 303 '*) printf 'mongod\\n' ;;\n"
                "        *' -p 400 '*) printf 'livekit-server\\n' ;;\n"
                "        *' -p 401 '*) printf 'livekit-server-helper\\n' ;;\n"
                "        *' -p 402 '*) printf 'livekit-server\\n' ;;\n"
                "        *' -p 403 '*) printf 'livekit-server\\n' ;;\n"
                "      esac\n"
                "      ;;\n"
                "    *' -o command= '*)\n"
                "      case \" $* \" in\n"
                "        *' -p 301 '*) printf '/opt/synthetic/mongod-wrapper --port 32117 --dbpath %s\\n' \"$MONGO_DATA_DIR\" ;;\n"
                "        *' -p 302 '*) printf '/opt/synthetic/meilisearch-helper --http-addr 127.0.0.1:12700 --db-path %s\\n' \"$MEILI_DATA_DIR\" ;;\n"
                "        *' -p 303 '*) printf '/opt/homebrew/bin/mongod --port 32117 --dbpath %s\\n' \"$MONGO_DATA_DIR\" ;;\n"
                "        *' -p 400 '*) printf '/opt/synthetic/livekit-server --config %s --node-ip 192.0.2.10\\n' \"$LIVEKIT_CFG_FILE\" ;;\n"
                "        *' -p 401 '*) printf '/opt/synthetic/livekit-server-helper --config %s --node-ip 192.0.2.10\\n' \"$LIVEKIT_CFG_FILE\" ;;\n"
                "        *' -p 402 '*) printf '/opt/synthetic/livekit-server --config %s-foreign --node-ip 192.0.2.10\\n' \"$LIVEKIT_CFG_FILE\" ;;\n"
                "        *' -p 403 '*) printf '/opt/synthetic/livekit-server --config %s --node-ipv6 192.0.2.10\\n' \"$LIVEKIT_CFG_FILE\" ;;\n"
                "      esac\n"
                "      ;;\n"
                "  esac\n"
                "}\n"
                f"{defs}"
                "if VIVENTIUM_INSTALL_EXPERIENCE=express mongo_process_matches_expected 303; then printf 'mongo-wrong-pinned-binary=match\\n'; else printf 'mongo-wrong-pinned-binary=mismatch\\n'; fi\n"
                "for pair in 'mongo_process_matches_expected 301 mongo-lookalike' 'meili_process_matches_expected 302 meili-lookalike' 'livekit_command_matches_expected 400 livekit-selected' 'livekit_command_matches_expected 401 livekit-lookalike' 'livekit_command_matches_expected 402 livekit-config-prefix' 'livekit_command_matches_expected 403 livekit-option-lookalike'; do\n"
                "  set -- $pair\n"
                "  if \"$1\" \"$2\"; then printf '%s=match\\n' \"$3\"; else printf '%s=mismatch\\n' \"$3\"; fi\n"
                "done\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert completed.stdout.strip().splitlines() == [
        "mongo-wrong-pinned-binary=mismatch",
        "mongo-lookalike=mismatch",
        "meili-lookalike=mismatch",
        "livekit-selected=match",
        "livekit-lookalike=mismatch",
        "livekit-config-prefix=mismatch",
        "livekit-option-lookalike=mismatch",
    ]


def test_unique_listener_pid_requires_exactly_one_process() -> None:
    script_text = NATIVE_STACK_PATH.read_text(encoding="utf-8")
    function_def = extract_shell_function(script_text, "resolve_unique_listener_pid")

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                "lsof() {\n"
                "  case \" $* \" in\n"
                "    *' -iTCP:1001 '*) printf '41\\n' ;;\n"
                "    *' -iTCP:1002 '*) printf '41\\n42\\n' ;;\n"
                "    *' -iTCP:1003 '*) printf '41\\n41\\n' ;;\n"
                "  esac\n"
                "}\n"
                f"{function_def}"
                "for port in 1000 1001 1002 1003; do\n"
                "  if pid=\"$(resolve_unique_listener_pid \"$port\" 2>/dev/null)\"; then printf '%s=%s\\n' \"$port\" \"$pid\"; else printf '%s=refused\\n' \"$port\"; fi\n"
                "done\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert completed.stdout.strip().splitlines() == [
        "1000=refused",
        "1001=41",
        "1002=refused",
        "1003=41",
    ]


def test_express_executable_path_uses_one_primary_lsof_text_image(tmp_path: Path) -> None:
    script_text = NATIVE_STACK_PATH.read_text(encoding="utf-8")
    function_names = [
        "canonical_existing_path",
        "process_executable_path",
        "mongo_executable_matches_expected",
    ]
    defs = "".join(extract_shell_function(script_text, name) for name in function_names)
    pinned_binary = tmp_path / "runtime tools" / "mongodb" / "bin" / "mongod"
    foreign_binary = tmp_path / "foreign runtime" / "bin" / "mongod"
    pinned_binary.parent.mkdir(parents=True)
    foreign_binary.parent.mkdir(parents=True)
    pinned_binary.write_text("synthetic\n", encoding="utf-8")
    foreign_binary.write_text("synthetic\n", encoding="utf-8")

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                "VIVENTIUM_INSTALL_EXPERIENCE='express'\n"
                f"MONGODB_NATIVE_BINARY={shlex.quote(str(pinned_binary))}\n"
                f"PINNED_BINARY={shlex.quote(str(pinned_binary))}\n"
                f"FOREIGN_BINARY={shlex.quote(str(foreign_binary))}\n"
                "lsof() {\n"
                "  case \" $* \" in\n"
                "    *' -p 501 '*) printf 'p501\\nftxt\\nn%s\\nftxt\\nn/usr/lib/dyld\\n' \"$PINNED_BINARY\" ;;\n"
                "    *' -p 502 '*) printf 'p502\\nftxt\\nn%s\\nftxt\\nn/usr/lib/dyld\\n' \"$FOREIGN_BINARY\" ;;\n"
                "    *' -p 503 '*) printf 'p503\\n' ;;\n"
                "    *' -p 504 '*) printf 'p504\\nftxt\\nn%s\\np999\\nftxt\\nn%s\\n' \"$PINNED_BINARY\" \"$FOREIGN_BINARY\" ;;\n"
                "  esac\n"
                "}\n"
                f"{defs}"
                "for pid in 501 502 503 504; do\n"
                "  if mongo_executable_matches_expected \"$pid\"; then printf '%s=match\\n' \"$pid\"; else printf '%s=mismatch\\n' \"$pid\"; fi\n"
                "done\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert completed.stdout.strip().splitlines() == [
        "501=match",
        "502=mismatch",
        "503=mismatch",
        "504=mismatch",
    ]


def test_express_executable_path_fails_closed_without_lsof(tmp_path: Path) -> None:
    script_text = NATIVE_STACK_PATH.read_text(encoding="utf-8")
    function_names = [
        "canonical_existing_path",
        "process_executable_path",
        "mongo_executable_matches_expected",
    ]
    defs = "".join(extract_shell_function(script_text, name) for name in function_names)
    pinned_binary = tmp_path / "mongodb" / "mongod"
    pinned_binary.parent.mkdir()
    pinned_binary.write_text("synthetic\n", encoding="utf-8")

    completed = subprocess.run(
        [
            "/bin/bash",
            "-lc",
            (
                "set -euo pipefail\n"
                "VIVENTIUM_INSTALL_EXPERIENCE='express'\n"
                f"MONGODB_NATIVE_BINARY={shlex.quote(str(pinned_binary))}\n"
                f"{defs}"
                "PATH='/nonexistent'\n"
                "if mongo_executable_matches_expected 501; then printf 'match\\n'; else printf 'mismatch\\n'; fi\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert completed.stdout.strip() == "mismatch"


def test_start_mongo_adopts_unique_exact_listener_over_stale_pid(tmp_path: Path) -> None:
    script_text = NATIVE_STACK_PATH.read_text(encoding="utf-8")
    defs = "".join(
        extract_shell_function(script_text, name) for name in ("write_pid", "start_mongo")
    )
    pid_file = tmp_path / "mongod.pid"
    pid_file.write_text("111\n", encoding="utf-8")

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                "MONGO_PORT='32117'\n"
                f"MONGO_PID_FILE={shlex.quote(str(pid_file))}\n"
                "VIVENTIUM_INSTALL_EXPERIENCE='legacy'\n"
                "port_listening() { return 0; }\n"
                "resolve_unique_listener_pid() { printf '222\\n'; }\n"
                "mongo_process_matches_expected() { [[ \"$1\" == '222' ]]; }\n"
                "mongo_listener_matches_expected() { [[ \"$1\" == '222' ]]; }\n"
                f"{defs}"
                "start_mongo\n"
                "printf 'pid=%s\\n' \"$(tr -d '[:space:]' <\"$MONGO_PID_FILE\")\"\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    assert "pid=222" in completed.stdout
    assert "adopted listener PID 222" in completed.stdout


@pytest.mark.parametrize(
    ("listener_status", "identity_status", "expected_status", "expected_pid"),
    [
        (0, 0, 0, "222"),
        (0, 1, 1, "111"),
        (1, 0, 1, "111"),
    ],
)
def test_start_meili_adopts_only_one_exact_listener(
    tmp_path: Path,
    listener_status: int,
    identity_status: int,
    expected_status: int,
    expected_pid: str,
) -> None:
    script_text = NATIVE_STACK_PATH.read_text(encoding="utf-8")
    defs = "".join(
        extract_shell_function(script_text, name) for name in ("write_pid", "start_meili")
    )
    pid_file = tmp_path / f"meilisearch-{listener_status}-{identity_status}.pid"
    pid_file.write_text("111\n", encoding="utf-8")

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                "MEILI_PORT='12700'\n"
                f"MEILI_PID_FILE={shlex.quote(str(pid_file))}\n"
                "port_listening() { return 0; }\n"
                f"resolve_unique_listener_pid() {{ if [[ '{listener_status}' == '0' ]]; then printf '222\\n'; else return 1; fi; }}\n"
                f"meili_process_matches_expected() {{ return {identity_status}; }}\n"
                f"{defs}"
                "start_meili\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )

    assert (completed.returncode == 0) is (expected_status == 0)
    assert pid_file.read_text(encoding="utf-8").strip() == expected_pid
    if expected_status == 0:
        assert "adopted listener PID 222" in completed.stdout
    else:
        assert "refusing" in completed.stderr


def test_native_stop_validates_each_runtime_process_before_killing() -> None:
    script_text = NATIVE_STACK_PATH.read_text(encoding="utf-8")
    stop_case = script_text.split("case \"${1:-}\" in", 1)[1].split("  stop)", 1)[1].split("    ;;", 1)[0]

    assert 'stop_pid_file_if_matches "$LIVEKIT_PID_FILE" "LiveKit" livekit_command_matches_expected' in script_text
    assert 'stop_pid_file_if_matches "$MEILI_PID_FILE" "Meilisearch" meili_process_matches_expected' in stop_case
    assert "prepare_native_mongo_engine_identity_for_stop" in stop_case
    assert "stop_recorded_native_mongo_engine" in stop_case
    assert "seal_native_mongo_engine_identity_after_stop" in stop_case

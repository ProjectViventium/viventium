from __future__ import annotations

import subprocess
from pathlib import Path


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
    assert 'stop_pid_file "$MEILI_PID_FILE" "Meilisearch"' in stop_case


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
                "port_listening() { return 0; }\n"
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
                "port_listening() { return 0; }\n"
                "mongo_listener_matches_expected() { return 0; }\n"
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

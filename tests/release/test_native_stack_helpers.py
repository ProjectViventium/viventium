from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
NATIVE_STACK_PATH = REPO_ROOT / "scripts" / "viventium" / "native_stack.sh"


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

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                "LIVEKIT_HTTP_PORT='7888'\n"
                "LIVEKIT_CFG_FILE='/tmp/viventium/livekit/livekit.yaml'\n"
                "listener_pid() { printf '4242\\n'; }\n"
                "ps() { printf '/usr/local/bin/livekit-server --config /tmp/other/livekit.yaml --node-ip 127.0.0.1\\n'; }\n"
                f"{process_def}"
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


def test_start_livekit_restarts_managed_listener_when_runtime_meta_drifted(tmp_path: Path) -> None:
    script_text = NATIVE_STACK_PATH.read_text(encoding="utf-8")
    function_names = [
        "start_livekit",
        "write_livekit_runtime_meta",
    ]
    defs = "".join(extract_shell_function(script_text, name) for name in function_names)

    cfg_dir = tmp_path / "livekit"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg_file = cfg_dir / "livekit.yaml"
    meta_file = tmp_path / "livekit.runtime.env"
    pid_file = tmp_path / "livekit.pid"
    log_file = tmp_path / "livekit.log"

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                "VOICE_ENABLED='true'\n"
                "LIVEKIT_HTTP_PORT='7888'\n"
                "LIVEKIT_TCP_PORT='7889'\n"
                "LIVEKIT_UDP_PORT='7890'\n"
                "LIVEKIT_NODE_IP='192.0.2.10'\n"
                "LIVEKIT_API_KEY='viventium-local'\n"
                "LIVEKIT_API_SECRET='secret'\n"
                f"LIVEKIT_CFG_FILE='{cfg_file}'\n"
                f"LIVEKIT_META_FILE='{meta_file}'\n"
                f"LIVEKIT_PID_FILE='{pid_file}'\n"
                f"LIVEKIT_LOG_FILE='{log_file}'\n"
                "port_listening() { return 0; }\n"
                "managed_livekit_listener_pid() { printf '4242\\n'; }\n"
                "livekit_meta_matches_expected() { return 1; }\n"
                "livekit_command_matches_expected() { return 1; }\n"
                "stop_pid() { printf 'stopped:%s\\n' \"$1\"; }\n"
                "ensure_livekit_binary() { printf '/usr/local/bin/livekit-server\\n'; }\n"
                "wait_for_port() { printf 'waited:%s\\n' \"$1\"; }\n"
                "write_pid() { printf 'pid-written\\n'; }\n"
                "nohup() { printf 'nohup:%s\\n' \"$*\"; }\n"
                f"{defs}"
                "start_livekit\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    stdout = completed.stdout
    assert "Restarting LiveKit on 7888 to apply updated network/runtime config" in stdout
    assert "stopped:4242" in stdout
    assert "waited:7888" in stdout
    assert meta_file.read_text(encoding="utf-8").strip().splitlines() == [
        "LIVEKIT_NODE_IP=192.0.2.10",
        "LIVEKIT_HTTP_PORT=7888",
        "LIVEKIT_TCP_PORT=7889",
        "LIVEKIT_UDP_PORT=7890",
    ]

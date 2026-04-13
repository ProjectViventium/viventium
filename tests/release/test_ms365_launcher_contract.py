from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
START_SCRIPT_PATH = REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh"


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


def test_ms365_restart_reclaims_non_viventium_listener_before_reuse() -> None:
    script_text = START_SCRIPT_PATH.read_text(encoding="utf-8")

    ownership_helper = extract_shell_function(script_text, "ms365_port_listener_is_viventium_owned")
    start_ms365 = extract_shell_function(script_text, "start_ms365_mcp")

    assert 'docker ps -q --filter "name=^/viventium_ms365_mcp$"' in ownership_helper
    assert 'pid_matches_scope "$pid" "$ROOT_DIR/MCPs/ms-365-mcp-server"' in ownership_helper
    assert 'pid_matches_scope "$pid" "$LEGACY_V0_3_DIR"' in ownership_helper

    assert 'if ! ms365_port_listener_is_viventium_owned "$base_port"; then' in start_ms365
    assert 'kill_port_listeners "$base_port"' in start_ms365
    assert "non-Viventium listener" in start_ms365

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_shared_port_probe_uses_socket_health_checks() -> None:
    common_text = (REPO_ROOT / "scripts" / "viventium" / "common.sh").read_text(
        encoding="utf-8"
    )
    launcher_text = (REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh").read_text(
        encoding="utf-8"
    )
    native_stack_text = (REPO_ROOT / "scripts" / "viventium" / "native_stack.sh").read_text(
        encoding="utf-8"
    )
    bin_text = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")

    assert "viventium_port_listener_active() {" in common_text
    assert "socket.getaddrinfo(" in common_text
    assert "sock.connect_ex(sockaddr) == 0" in common_text
    assert 'host="${VIVENTIUM_PORT_CHECK_HOST:-localhost}"' in common_text
    assert 'timeout_seconds="${VIVENTIUM_PORT_CHECK_TIMEOUT_SECONDS:-1}"' in common_text
    assert 'source "$VIVENTIUM_CORE_DIR/scripts/viventium/common.sh"' in launcher_text
    assert 'viventium_port_listener_active "$port"' in launcher_text
    assert 'viventium_port_listener_active "$port"' in native_stack_text
    assert 'viventium_port_listener_active "$port"' in bin_text


def test_launcher_no_longer_requires_lsof_for_runtime_control() -> None:
    launcher_text = (REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh").read_text(
        encoding="utf-8"
    )

    assert "query_tcp_listener_pids() {" not in launcher_text
    assert 'require_cmd lsof' not in launcher_text
    assert 'Port $port is in use but no safe scope was provided; skipping direct port-based stop' in launcher_text
    assert 'Stopping scoped processes that may own port $port' in launcher_text
    assert 'if [[ "${MONGO_IS_LOCAL:-false}" == "true" ]] && [[ -n "${MONGO_PORT:-}" ]]; then' in launcher_text
    assert 'VIVENTIUM_PORT_CHECK_HOST="$MONGO_HOST" viventium_port_listener_active "$MONGO_PORT"' in launcher_text
    assert 'timeout=timeout_seconds' in launcher_text
    assert 'mongosh "$uri" --eval "db.runCommand({ping:1})" --quiet >/dev/null 2>&1' not in launcher_text

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh"
SCHEDULER_SERVER = (
    REPO_ROOT
    / "viventium_v0_4/LibreChat/viventium/MCPs/scheduling-cortex/scheduling_cortex/server.py"
)


def test_modern_playground_next_dev_binds_explicitly_to_loopback() -> None:
    source = LAUNCHER.read_text(encoding="utf-8")

    assert 'exec "./node_modules/.bin/next" dev -H 127.0.0.1 -p "$PLAYGROUND_PORT"' in source
    assert 'exec npx next dev -H 127.0.0.1 -p "$PLAYGROUND_PORT"' in source
    assert 'exec "./node_modules/.bin/next" dev -p "$PLAYGROUND_PORT"' not in source
    assert 'exec npx next dev -p "$PLAYGROUND_PORT"' not in source


def test_scheduling_cortex_binds_explicitly_to_loopback() -> None:
    launcher = LAUNCHER.read_text(encoding="utf-8")
    server = SCHEDULER_SERVER.read_text(encoding="utf-8")

    assert '--host 127.0.0.1 --port "$SCHEDULING_MCP_PORT"' in launcher
    assert 'os.getenv("SCHEDULER_HOST", "127.0.0.1")' in server
    assert 'os.getenv("SCHEDULER_HOST", "0.0.0.0")' not in server

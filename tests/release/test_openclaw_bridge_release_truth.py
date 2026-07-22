from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BRIDGE_README = ROOT / "viventium_v0_4" / "MCPs" / "openclaw-bridge" / "README.md"
BRIDGE_MANAGER = ROOT / "viventium_v0_4" / "MCPs" / "openclaw-bridge" / "openclaw_manager.py"
BRIDGE_LAUNCHER = ROOT / "viventium_v0_4" / "viventium-openclaw-bridge-start.sh"


def test_openclaw_bridge_docs_name_e2b_as_the_default_runtime() -> None:
    readme = BRIDGE_README.read_text(encoding="utf-8")
    manager = BRIDGE_MANAGER.read_text(encoding="utf-8")

    assert "E2B adapter (default" in readme
    assert "Direct adapter (explicit" in readme
    assert "default direct" not in manager


def test_openclaw_bridge_does_not_claim_unshipped_librechat_client_wiring() -> None:
    readme = BRIDGE_README.read_text(encoding="utf-8")
    launcher = BRIDGE_LAUNCHER.read_text(encoding="utf-8")

    assert "standalone lab surface" in readme
    assert "does not register this bridge as a LibreChat MCP client" in readme
    assert "Find 'openclaw-bridge'" not in launcher
    assert "does not register this bridge in LibreChat" in launcher

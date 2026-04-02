from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APP_PATH = ROOT / "viventium_v0_4" / "LibreChat" / "client" / "src" / "App.jsx"
RECONCILE_SCRIPT_PATH = (
    ROOT / "viventium_v0_4" / "LibreChat" / "scripts" / "viventium-reconcile-user-defaults.js"
)


def test_react_query_devtools_are_opt_in_only() -> None:
    source = APP_PATH.read_text(encoding="utf-8")

    assert "VITE_ENABLE_REACT_QUERY_DEVTOOLS" in source
    assert "toLowerCase() === 'true'" in source
    assert "showReactQueryDevtools ? (" in source
    assert "<ReactQueryDevtools initialIsOpen={false} position=\"top-right\" />" in source


def test_viventium_user_defaults_reconcile_script_is_shipped() -> None:
    source = RECONCILE_SCRIPT_PATH.read_text(encoding="utf-8")

    assert "buildMissingConversationRecallUpdate" in source
    assert "personalization.conversation_recall" in source

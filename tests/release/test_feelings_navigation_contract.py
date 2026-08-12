from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SIDE_NAV = (
    REPO_ROOT
    / "viventium_v0_4"
    / "LibreChat"
    / "client"
    / "src"
    / "hooks"
    / "Nav"
    / "useSideNavLinks.ts"
)
ACCOUNT_MENU = (
    REPO_ROOT
    / "viventium_v0_4"
    / "LibreChat"
    / "client"
    / "src"
    / "components"
    / "Nav"
    / "AccountSettings.tsx"
)


def test_feelings_is_discoverable_from_both_navigation_surfaces_with_one_gate() -> None:
    side_nav = SIDE_NAV.read_text(encoding="utf-8")
    account_menu = ACCOUNT_MENU.read_text(encoding="utf-8")

    for source in (side_nav, account_menu):
        assert "startupConfig?.viventiumFeelingsAvailable !== false" in source
        assert "navigate('/feelings')" in source
        assert "com_nav_feelings" in source

    assert "Feelings discovery in ordinary chat controls" in side_nav
    assert "=== VIVENTIUM START ===" in side_nav
    assert "=== VIVENTIUM END ===" in side_nav

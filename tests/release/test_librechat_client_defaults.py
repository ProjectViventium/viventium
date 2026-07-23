from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APP_PATH = ROOT / "viventium_v0_4" / "LibreChat" / "client" / "src" / "App.jsx"
RECONCILE_SCRIPT_PATH = (
    ROOT / "viventium_v0_4" / "LibreChat" / "scripts" / "viventium-reconcile-user-defaults.js"
)
SETTINGS_PATH = (
    ROOT / "viventium_v0_4" / "LibreChat" / "client" / "src" / "components" / "Nav" / "Settings.tsx"
)
ACCOUNT_MENU_PATH = (
    ROOT
    / "viventium_v0_4"
    / "LibreChat"
    / "client"
    / "src"
    / "components"
    / "Nav"
    / "AccountSettings.tsx"
)
ACCOUNT_TAB_PATH = (
    ROOT
    / "viventium_v0_4"
    / "LibreChat"
    / "client"
    / "src"
    / "components"
    / "Nav"
    / "SettingsTabs"
    / "Account"
    / "Account.tsx"
)
DATA_PROVIDER_CONFIG_PATH = (
    ROOT
    / "viventium_v0_4"
    / "LibreChat"
    / "packages"
    / "data-provider"
    / "src"
    / "config.ts"
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


def test_connected_channels_have_a_direct_settings_destination() -> None:
    settings = SETTINGS_PATH.read_text(encoding="utf-8")
    account_menu = ACCOUNT_MENU_PATH.read_text(encoding="utf-8")
    account_tab = ACCOUNT_TAB_PATH.read_text(encoding="utf-8")
    data_provider = DATA_PROVIDER_CONFIG_PATH.read_text(encoding="utf-8")

    assert "CHANNELS = 'channels'" in data_provider
    assert "SettingsTabValues.CHANNELS" in settings
    assert "<ConnectedChannels />" in settings
    assert "openSettings(SettingsTabValues.CHANNELS)" in account_menu
    assert "com_nav_connected_channels" in account_menu
    assert "<ConnectedChannels />" not in account_tab

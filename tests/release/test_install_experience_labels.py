import json
import re
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_user_facing_install_copy_uses_easy_and_custom_settings_names() -> None:
    source_paths = (
        REPO_ROOT / "bin/viventium",
        REPO_ROOT / "install.sh",
        REPO_ROOT / "scripts/viventium/brain_readiness.py",
        REPO_ROOT / "scripts/viventium/install_summary.py",
        REPO_ROOT / "scripts/viventium/installer_ui.py",
        REPO_ROOT / "scripts/viventium/native_stack.sh",
        REPO_ROOT / "scripts/viventium/preflight.py",
        REPO_ROOT / "scripts/viventium/doctor.sh",
        REPO_ROOT / "scripts/viventium/install_macos_helper.sh",
        REPO_ROOT / "scripts/viventium/wizard.py",
        REPO_ROOT / "apps/macos/ViventiumHelper/Sources/ViventiumHelper/ViventiumHelperApp.swift",
        REPO_ROOT / "viventium_v0_4/viventium-librechat-start.sh",
        REPO_ROOT / "qa/installer-resilience/scripts/express-native-browser-qa.cjs",
        REPO_ROOT / "README.md",
    )
    source = "\n".join(path.read_text(encoding="utf-8") for path in source_paths)

    assert "Easy Install" in source
    assert "Custom Settings Install" in source
    assert re.search(r"\bExpress\b", source) is None
    for obsolete_label in (
        "Express Install",
        "Advanced Setup",
        "Advanced setup",
        "Disabled by Express",
        "Express startup",
        "starting Express",
        "Express will not",
        "deferred by Express",
    ):
        assert obsolete_label not in source
    assert re.search(r"\bexpress\s+(?:install|setup|startup)\b", source, re.IGNORECASE) is None
    assert re.search(r"\badvanced\s+(?:install|setup)\b", source, re.IGNORECASE) is None


def test_active_requirement_and_qa_contracts_use_current_install_names() -> None:
    active_paths = [
        REPO_ROOT / "docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md",
        REPO_ROOT / "docs/requirements_and_learnings/10_Open_Source_Web_Search.md",
        REPO_ROOT / "docs/requirements_and_learnings/40_Public_Private_Boundaries_and_License_Matrix.md",
        REPO_ROOT / "docs/requirements_and_learnings/45_Runtime_Feature_QA_Map.md",
        *sorted((REPO_ROOT / "qa").glob("**/cases.md")),
    ]
    content = "\n".join(path.read_text(encoding="utf-8") for path in active_paths)

    assert re.search(r"\bExpress\b", content) is None

    for obsolete_public_phrase in (
        "Express Install",
        "Advanced Install",
        "Advanced Setup",
        "Advanced setup",
        "Express preflight",
        "Express Rich Brain Readiness",
        "Express Native",
        "Express-native",
        "Express deliberately",
        "Express install",
        "Express setup",
        "Advanced/Lab",
    ):
        assert obsolete_public_phrase not in content


def test_easy_install_web_search_contract_is_deferred_not_first_run_guided() -> None:
    contract = (
        REPO_ROOT / "docs/requirements_and_learnings/39_Installer_and_Config_Compiler.md"
    ).read_text(encoding="utf-8")

    assert "Web Search is deferred until after Easy Install reaches a working first answer" in contract
    assert "Web Search is guided in Easy Install" not in contract


def test_easy_install_browser_qa_requires_synthetic_identity_and_stable_api_key_ui() -> None:
    source = (
        REPO_ROOT / "qa/installer-resilience/scripts/express-native-browser-qa.cjs"
    ).read_text(encoding="utf-8")

    assert 'EMAIL.endsWith(".invalid")' in source
    assert "VIVENTIUM_QA_EMAIL must use a synthetic .invalid address" in source
    assert 'name: "Use OpenAI API key"' in source
    assert 'page.locator("form#f")' in source
    assert 'input[name="confirm_password"]' in source
    assert 'name: "Create admin"' in source
    assert "await page.waitForURL((url) => !url.searchParams.has(\"setup\")" in source
    assert "Connect OpenAI Account" not in source
    assert "/api/connected-accounts/openai/start" not in source


def test_easy_install_qa_fixture_uses_stable_browser_account_handoff() -> None:
    fixture = json.loads(
        (
            REPO_ROOT
            / "qa/installer-resilience/fixtures/express-native-clean.json"
        ).read_text(encoding="utf-8")
    )

    assert fixture["install"]["experience"] == "express"
    assert fixture["llm"]["activation"]["auth_mode"] == "user_provided"
    assert fixture["llm"]["primary"]["auth_mode"] == "user_provided"
    assert all(
        node.get("auth_mode") != "connected_account"
        for node in fixture["llm"].values()
        if isinstance(node, dict)
    )


def test_internal_install_experience_contract_remains_backward_compatible() -> None:
    schema = (REPO_ROOT / "config.schema.yaml").read_text(encoding="utf-8")
    compiler = (REPO_ROOT / "scripts/viventium/config_compiler.py").read_text(encoding="utf-8")
    startup_config = (
        REPO_ROOT / "viventium_v0_4/LibreChat/api/server/routes/config.js"
    ).read_text(encoding="utf-8")

    assert "enum: [express, custom]" in schema
    assert 'experience not in {"", "express", "custom"}' in compiler
    assert "['express', 'custom', 'legacy']" in startup_config


def test_public_front_door_maps_easy_and_custom_labels_to_existing_config_values() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    minimal = yaml.safe_load((REPO_ROOT / "config.minimal.example.yaml").read_text(encoding="utf-8"))
    full = yaml.safe_load((REPO_ROOT / "config.full.example.yaml").read_text(encoding="utf-8"))

    assert "Easy Install (Recommended)" in readme
    assert "Custom Settings Install" in readme
    assert "./install.sh" in readme
    assert minimal["install"]["experience"] == "express"
    assert full["install"]["experience"] == "custom"


def test_runtime_install_experience_readers_share_legacy_default() -> None:
    launcher = (
        REPO_ROOT / "viventium_v0_4/viventium-librechat-start.sh"
    ).read_text(encoding="utf-8")
    compiler = (REPO_ROOT / "scripts/viventium/config_compiler.py").read_text(encoding="utf-8")
    native_stack = (REPO_ROOT / "scripts/viventium/native_stack.sh").read_text(encoding="utf-8")

    assert 'VIVENTIUM_INSTALL_EXPERIENCE:-legacy' in launcher
    assert 'config.get("install", {}).get("experience") or "legacy"' in compiler
    assert 'VIVENTIUM_INSTALL_EXPERIENCE:-legacy' in native_stack


def test_runtime_startup_never_reports_user_provided_sentinels_as_configured_keys() -> None:
    launcher = (
        REPO_ROOT / "viventium_v0_4/viventium-librechat-start.sh"
    ).read_text(encoding="utf-8")

    assert '"${OPENAI_API_KEY}" != "user_provided"' in launcher
    assert '"${GROQ_API_KEY}" != "user_provided"' in launcher
    assert '"${XAI_API_KEY}" != "user_provided"' in launcher
    assert '"${CARTESIA_API_KEY}" != "user_provided"' in launcher
    assert '"${ELEVEN_API_KEY_FINAL}" != "user_provided"' in launcher
    assert "Connect in Settings > Account > Connected Accounts" in launcher
    assert 'LiveKit API Key:   ${GREEN}${LIVEKIT_API_KEY}' not in launcher


def test_prebuilt_helper_binary_contains_no_retired_install_labels() -> None:
    binary = REPO_ROOT / "apps/macos/ViventiumHelper/prebuilt/ViventiumHelper-universal"
    payload = binary.read_bytes()

    for retired_label in (
        b"Express Install",
        b"Express installation",
        b"Advanced Install",
        b"Advanced installation",
        b"Advanced Setup",
    ):
        assert retired_label not in payload

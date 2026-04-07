from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WIZARD_PATH = REPO_ROOT / "scripts" / "viventium" / "wizard.py"


def load_wizard_module():
    spec = importlib.util.spec_from_file_location("viventium_wizard", WIZARD_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_store_keychain_secret_returns_none_on_failure(monkeypatch, capsys) -> None:
    wizard = load_wizard_module()

    def fail(*_args, **_kwargs):
        raise subprocess.CalledProcessError(
            36,
            ["security", "add-generic-password"],
            stderr="User interaction is not allowed.",
        )

    monkeypatch.setattr(wizard.subprocess, "run", fail)

    assert wizard.store_keychain_secret("viventium/test_secret", "value") is None
    captured = capsys.readouterr()
    assert "failed to store viventium/test_secret in macOS Keychain" in captured.err
    assert "keeping it in local config state" in captured.err


def test_build_secret_node_prefers_keychain_ref_when_available(monkeypatch) -> None:
    wizard = load_wizard_module()
    monkeypatch.setattr(
        wizard,
        "store_keychain_secret",
        lambda service, _value: f"keychain://{service}",
    )

    assert wizard.build_secret_node("viventium/openai_api_key", "secret") == {
        "secret_ref": "keychain://viventium/openai_api_key"
    }


def test_normalize_preset_keeps_local_secret_values_when_keychain_write_fails(monkeypatch) -> None:
    wizard = load_wizard_module()
    monkeypatch.setattr(wizard, "store_keychain_secret", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(wizard.secrets, "token_hex", lambda _nbytes: "generated-call-secret")

    config = {
        "version": 1,
        "runtime": {},
        "llm": {
            "activation": {
                "provider": "groq",
                "secret_value": "groq-secret",
            },
            "primary": {
                "provider": "openai",
                "secret_value": "openai-secret",
            },
            "secondary": {
                "provider": "anthropic",
                "secret_value": "anthropic-secret",
            },
            "extra_provider_keys": {
                "x_ai": "xai-secret",
            },
        },
        "voice": {
            "stt_provider": "assemblyai",
            "stt": {"secret_value": "assemblyai-secret"},
            "tts_provider": "elevenlabs",
            "tts": {"secret_value": "elevenlabs-secret"},
        },
        "integrations": {
            "telegram": {"enabled": True, "secret_value": "telegram-secret"},
            "telegram_codex": {"enabled": True, "secret_value": "telegram-codex-secret"},
            "google_workspace": {
                "enabled": True,
                "client_secret": {"secret_value": "google-client-secret"},
                "refresh_token": {"secret_value": "google-refresh-token"},
            },
            "ms365": {
                "enabled": True,
                "client_secret": {"secret_value": "ms365-client-secret"},
            },
            "skyvern": {
                "enabled": True,
                "api_key": {"secret_value": "skyvern-secret"},
            },
        },
    }

    normalized = wizard.normalize_preset(config)

    assert normalized["llm"]["activation"]["secret_value"] == "groq-secret"
    assert "secret_ref" not in normalized["llm"]["activation"]
    assert normalized["llm"]["primary"]["secret_value"] == "openai-secret"
    assert normalized["llm"]["secondary"]["secret_value"] == "anthropic-secret"
    assert normalized["llm"]["extra_provider_keys"]["x_ai"] == "xai-secret"
    assert normalized["integrations"]["telegram"]["secret_value"] == "telegram-secret"
    assert normalized["integrations"]["telegram_codex"]["secret_value"] == "telegram-codex-secret"
    assert normalized["voice"]["stt"]["secret_value"] == "assemblyai-secret"
    assert normalized["voice"]["tts"]["secret_value"] == "elevenlabs-secret"
    assert normalized["voice"]["provider_keys"]["assemblyai"]["secret_value"] == "assemblyai-secret"
    assert normalized["voice"]["provider_keys"]["elevenlabs"]["secret_value"] == "elevenlabs-secret"
    assert normalized["integrations"]["google_workspace"]["client_secret"]["secret_value"] == "google-client-secret"
    assert normalized["integrations"]["google_workspace"]["refresh_token"]["secret_value"] == "google-refresh-token"
    assert normalized["integrations"]["ms365"]["client_secret"]["secret_value"] == "ms365-client-secret"
    assert normalized["integrations"]["skyvern"]["api_key"]["secret_value"] == "skyvern-secret"
    assert normalized["runtime"]["call_session_secret"]["secret_value"] == "generated-call-secret"
    assert normalized["runtime"]["personalization"]["default_conversation_recall"] is False


def test_build_base_config_matches_easy_install_defaults() -> None:
    wizard = load_wizard_module()

    config = wizard.build_base_config(
        install_mode="native",
        primary_provider="openai",
        auth_mode="connected_account",
        secondary_provider="none",
    )

    assert config["runtime"]["personalization"]["default_conversation_recall"] is False
    assert config["runtime"]["network"]["remote_call_mode"] == "disabled"
    assert config["runtime"]["auth"]["allow_registration"] is True
    assert config["runtime"]["auth"]["allow_password_reset"] is False
    assert config["integrations"]["code_interpreter"]["enabled"] is False
    assert config["integrations"]["web_search"]["enabled"] is False
    assert config["integrations"]["web_search"]["search_provider"] == "searxng"
    assert config["integrations"]["web_search"]["scraper_provider"] == "firecrawl"
    assert config["llm"]["primary"]["auth_mode"] == "connected_account"
    assert "fast_llm_provider" not in config["voice"]


def test_normalize_preset_preserves_dormant_voice_provider_keys(monkeypatch) -> None:
    wizard = load_wizard_module()
    monkeypatch.setattr(wizard, "store_keychain_secret", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(wizard.secrets, "token_hex", lambda _nbytes: "generated-call-secret")

    config = {
        "version": 1,
        "runtime": {},
        "llm": {
            "activation": {
                "provider": "groq",
                "secret_value": "groq-secret",
            },
            "primary": {
                "provider": "openai",
                "secret_value": "openai-secret",
            },
            "secondary": {
                "provider": "anthropic",
                "secret_value": "anthropic-secret",
            },
            "extra_provider_keys": {},
        },
        "voice": {
            "mode": "local",
            "stt_provider": "whisper_local",
            "tts_provider": "local_chatterbox_turbo_mlx_8bit",
            "provider_keys": {
                "assemblyai": "assemblyai-secret",
                "cartesia": {"secret_value": "cartesia-secret"},
            },
        },
        "integrations": {},
    }

    normalized = wizard.normalize_preset(config)

    assert normalized["voice"]["provider_keys"]["assemblyai"]["secret_value"] == "assemblyai-secret"
    assert normalized["voice"]["provider_keys"]["cartesia"]["secret_value"] == "cartesia-secret"


def test_validate_non_interactive_integrations_rejects_disabled_telegram_secret() -> None:
    wizard = load_wizard_module()

    config = {
        "integrations": {
            "telegram": {
                "enabled": False,
                "secret_value": "telegram-secret",
            }
        }
    }

    try:
        wizard.validate_non_interactive_integrations(config)
    except SystemExit as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected disabled Telegram secret to fail loudly")

    assert "integrations.telegram.enabled is false" in message
    assert "allow_disabled_secret: true" in message


def test_validate_non_interactive_integrations_allows_explicit_dormant_telegram_secret() -> None:
    wizard = load_wizard_module()

    config = {
        "integrations": {
            "telegram": {
                "enabled": False,
                "allow_disabled_secret": True,
                "secret_value": "telegram-secret",
            }
        }
    }

    wizard.validate_non_interactive_integrations(config)


def test_normalize_preset_backfills_wing_mode_for_local_voice(monkeypatch) -> None:
    wizard = load_wizard_module()
    monkeypatch.setattr(wizard, "store_keychain_secret", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(wizard.secrets, "token_hex", lambda _nbytes: "generated-call-secret")

    config = {
        "version": 1,
        "runtime": {},
        "llm": {
            "activation": {
                "provider": "groq",
                "secret_value": "groq-secret",
            },
            "primary": {
                "provider": "openai",
                "secret_value": "openai-secret",
            },
            "secondary": {
                "provider": "none",
                "auth_mode": "disabled",
            },
        },
        "voice": {
            "mode": "local",
            "stt_provider": "whisper_local",
            "tts_provider": "local_chatterbox_turbo_mlx_8bit",
        },
    }

    normalized = wizard.normalize_preset(config)

    assert normalized["voice"]["wing_mode"]["default_enabled"] is False


class _FakeWizardUI:
    def __init__(
        self,
        *,
        selects: list[str],
        passwords: list[str] | None = None,
        texts: list[str] | None = None,
        confirms: list[bool] | None = None,
    ) -> None:
        self.select_values = list(selects)
        self.password_values = list(passwords or [])
        self.text_values = list(texts or [])
        self.confirm_values = list(confirms or [])
        self.notes: list[str] = []
        self.errors: list[str] = []
        self.sections: list[tuple[str, str, str]] = []
        self.select_calls: list[list[tuple[str, str, str]]] = []

    def print_section(self, title: str, message: str, style: str = "cyan") -> None:
        self.sections.append((title, message, style))

    def print_note(self, message: str) -> None:
        self.notes.append(message)

    def print_error(self, message: str) -> None:
        self.errors.append(message)

    def select(self, _prompt: str, options, default: str | None = None) -> str:
        self.select_calls.append([(option.value, option.label, option.note) for option in options])
        if not self.select_values:
            if default is None:
                raise AssertionError("No fake select value provided")
            return default
        return self.select_values.pop(0)

    def password(self, _prompt: str, allow_empty: bool = False) -> str:
        if self.password_values:
            return self.password_values.pop(0)
        return "" if allow_empty else ""

    def text(self, _prompt: str, default: str = "", allow_empty: bool = True) -> str:
        if self.text_values:
            return self.text_values.pop(0)
        return default if allow_empty else default

    def confirm(self, _prompt: str, default: bool = False) -> bool:
        if self.confirm_values:
            return self.confirm_values.pop(0)
        return default

    def checkbox(self, _prompt: str, _options) -> list[str]:
        return []


def test_prompt_web_search_without_docker_explains_local_auto_install() -> None:
    wizard = load_wizard_module()
    config = wizard.build_base_config(
        install_mode="native",
        primary_provider="openai",
        auth_mode="connected_account",
        secondary_provider="none",
    )
    deferred: list[str] = []
    ui = _FakeWizardUI(selects=["searxng", "firecrawl"])

    wizard.prompt_web_search(
        ui,
        config,
        deferred,
        easy=True,
        docker_installed=False,
    )

    web_search = config["integrations"]["web_search"]
    assert web_search["enabled"] is True
    assert web_search["search_provider"] == "searxng"
    assert web_search["scraper_provider"] == "firecrawl"
    assert any("install Docker Desktop during preflight" in note for note in ui.notes)
    assert any("configure local SearXNG automatically" in note for note in ui.notes)
    assert any("configure local Firecrawl automatically" in note for note in ui.notes)
    first_select_labels = [label for _value, label, _note in ui.select_calls[0]]
    second_select_labels = [label for _value, label, _note in ui.select_calls[1]]
    assert "Local SearXNG (install Docker automatically)" in first_select_labels
    assert "Local Firecrawl (install Docker automatically)" in second_select_labels


def test_prompt_web_search_firecrawl_api_explains_hosted_path() -> None:
    wizard = load_wizard_module()
    config = wizard.build_base_config(
        install_mode="native",
        primary_provider="openai",
        auth_mode="connected_account",
        secondary_provider="none",
    )
    deferred: list[str] = []
    ui = _FakeWizardUI(
        selects=["serper", "firecrawl_api"],
        passwords=["serper-secret", "firecrawl-secret"],
        texts=["https://api.firecrawl.dev"],
    )

    wizard.prompt_web_search(
        ui,
        config,
        deferred,
        easy=True,
        docker_installed=False,
    )

    web_search = config["integrations"]["web_search"]
    assert web_search["enabled"] is True
    assert web_search["search_provider"] == "serper"
    assert web_search["scraper_provider"] == "firecrawl_api"
    assert any("Serper powers live web search results without Docker." in note for note in ui.notes)
    assert any("Firecrawl fetches the full page content behind search results" in note for note in ui.notes)
    assert any("serper.dev/api-keys" in note for note in ui.notes)
    assert any("docs.firecrawl.dev/introduction#api-key" in note for note in ui.notes)


def test_prompt_web_search_with_docker_warns_when_firecrawl_memory_is_low() -> None:
    wizard = load_wizard_module()
    config = wizard.build_base_config(
        install_mode="native",
        primary_provider="openai",
        auth_mode="connected_account",
        secondary_provider="none",
    )
    ui = _FakeWizardUI(selects=[])

    wizard.prompt_web_search(
        ui,
        config,
        [],
        easy=True,
        docker_installed=True,
        docker_memory_bytes=3 * 1024 * 1024 * 1024,
    )

    assert any("lighter local Firecrawl profile" in note for note in ui.notes)
    assert any("prefer Firecrawl API" in note for note in ui.notes)


def test_prompt_telegram_reprompts_until_botfather_token_looks_valid(monkeypatch) -> None:
    wizard = load_wizard_module()
    config = wizard.build_base_config(
        install_mode="native",
        primary_provider="openai",
        auth_mode="connected_account",
        secondary_provider="none",
    )
    deferred: list[str] = []
    ui = _FakeWizardUI(
        selects=[],
        passwords=[
            "not-a-telegram-token",
            "123456789:Valid_botfather_token_value_ABCDEFGH",
        ],
    )

    monkeypatch.setattr(
        wizard,
        "build_secret_node",
        lambda _service, value: {"secret_value": value},
    )

    wizard.prompt_telegram(ui, config, deferred, easy=True)

    telegram = config["integrations"]["telegram"]
    assert telegram["enabled"] is True
    assert telegram["secret_value"] == "123456789:Valid_botfather_token_value_ABCDEFGH"
    assert any("BotFather format" in error for error in ui.errors)


def test_configure_advanced_setup_limits_primary_provider_to_foundation_models(monkeypatch) -> None:
    wizard = load_wizard_module()
    ui = _FakeWizardUI(selects=["native", "openai", "connected_account", "none"], passwords=["groq-test"])

    monkeypatch.setattr(wizard, "docker_desktop_installed", lambda: False)
    monkeypatch.setattr(wizard, "print_feature_overview", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(wizard, "prompt_voice_settings", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(wizard, "prompt_web_search", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(wizard, "prompt_google_workspace", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(wizard, "prompt_ms365", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(wizard, "prompt_skyvern", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(wizard, "prompt_telegram", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(wizard, "prompt_telegram_codex", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(wizard, "prompt_remote_access", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(wizard, "build_secret_node", lambda service, value: {"service": service, "secret_value": value})
    monkeypatch.setattr(wizard, "ensure_generated_secret", lambda *_args, **_kwargs: None)

    config, deferred = wizard.configure_advanced_setup(ui)

    primary_options = [value for value, _label, _note in ui.select_calls[1]]
    auth_options = [value for value, _label, _note in ui.select_calls[2]]

    assert primary_options == ["openai", "anthropic"]
    assert auth_options == ["connected_account", "api_key"]
    assert config["llm"]["primary"]["provider"] == "openai"
    assert config["llm"]["primary"]["auth_mode"] == "connected_account"
    assert deferred


def test_prompt_remote_access_derives_public_surface_urls_from_app_hostname() -> None:
    wizard = load_wizard_module()
    config = wizard.build_base_config(
        install_mode="native",
        primary_provider="openai",
        auth_mode="connected_account",
        secondary_provider="none",
    )
    ui = _FakeWizardUI(selects=["public_browser"], texts=["app.example.com"])

    wizard.prompt_remote_access(ui, config)

    network = config["runtime"]["network"]
    assert network["remote_call_mode"] == "custom_domain"
    assert network["public_client_origin"] == "https://app.example.com"
    assert network["public_api_origin"] == "https://api.app.example.com"
    assert network["public_playground_origin"] == "https://playground.app.example.com"
    assert network["public_livekit_url"] == "wss://livekit.app.example.com"


def test_prompt_remote_access_uses_temporary_public_url_when_hostname_is_blank() -> None:
    wizard = load_wizard_module()
    config = wizard.build_base_config(
        install_mode="native",
        primary_provider="openai",
        auth_mode="connected_account",
        secondary_provider="none",
    )
    ui = _FakeWizardUI(selects=["public_browser"], texts=[""])

    wizard.prompt_remote_access(ui, config)

    network = config["runtime"]["network"]
    assert network["remote_call_mode"] == "custom_domain"
    assert network["public_client_origin"] == ""
    assert any("temporary outside URL" in note for note in ui.notes)


def test_prompt_browser_auth_controls_sets_remote_browser_auth_flags() -> None:
    wizard = load_wizard_module()
    config = wizard.build_base_config(
        install_mode="native",
        primary_provider="openai",
        auth_mode="connected_account",
        secondary_provider="none",
    )
    wizard.apply_remote_access_choice(config, remote_call_mode="custom_domain", public_app_hostname="app.example.com")
    ui = _FakeWizardUI(selects=[], confirms=[False, False])

    wizard.prompt_browser_auth_controls(ui, config)

    assert config["runtime"]["auth"]["allow_registration"] is False
    assert config["runtime"]["auth"]["allow_password_reset"] is False
    assert any("leave browser sign-up on until you create it" in note for note in ui.notes)
    assert any("one-time reset link locally" in note for note in ui.notes)

from __future__ import annotations

from pathlib import Path

from app.config import load_config


def test_load_config_supports_generated_file_overrides(tmp_path, monkeypatch):
    runtime_root = tmp_path / "runtime"
    home_root = tmp_path / "home"
    service_env = tmp_path / "service-env" / "telegram-codex.env"
    service_env.parent.mkdir(parents=True, exist_ok=True)
    service_env.write_text(
        "TELEGRAM_CODEX_BOT_TOKEN=test-token\nTELEGRAM_CODEX_BOT_USERNAME=viv_codex_bot\n",
        encoding="utf-8",
    )

    projects_path = tmp_path / "telegram-codex" / "projects.yaml"
    projects_path.parent.mkdir(parents=True, exist_ok=True)
    projects_path.write_text(
        """
default_project: viventium_core
projects:
  viventium_core:
    path: /tmp/workspace
""".strip(),
        encoding="utf-8",
    )

    settings_path = tmp_path / "telegram-codex" / "settings.yaml"
    settings_path.write_text(
        f"""
bot:
  env_file: {service_env}
  private_chat_only: true
runtime:
  logs_dir: {runtime_root / "logs"}
  sessions_path: {runtime_root / "state" / "chat_sessions.json"}
  paired_users_path: {runtime_root / "state" / "paired_users.json"}
  pending_pairs_path: {runtime_root / "state" / "pair_tokens.json"}
projects:
  registry_file: {projects_path}
""".strip(),
        encoding="utf-8",
    )

    monkeypatch.setenv("VIVENTIUM_TELEGRAM_CODEX_SETTINGS_FILE", str(settings_path))
    monkeypatch.setenv("VIVENTIUM_TELEGRAM_CODEX_PROJECTS_FILE", str(projects_path))
    monkeypatch.setenv("VIVENTIUM_TELEGRAM_CODEX_ENV_FILE", str(service_env))
    monkeypatch.setenv("HOME", str(home_root))

    config = load_config(root=Path("/tmp/unused-root"))

    assert config.bot.token == "test-token"
    assert config.bot.username == "viv_codex_bot"
    assert config.runtime.project_registry_path == projects_path.resolve()
    assert config.runtime.paired_users_path.name == "viv_codex_bot.json"
    assert config.runtime.paired_users_path != (runtime_root / "state" / "paired_users.json").resolve()
    assert (runtime_root / "state" / "paired_users.json").resolve() in config.runtime.paired_users_migration_sources


def test_load_config_respects_custom_paired_users_path(tmp_path, monkeypatch):
    custom_paired_users_path = tmp_path / "custom" / "paired.json"
    service_env = tmp_path / "service-env" / "telegram-codex.env"
    service_env.parent.mkdir(parents=True, exist_ok=True)
    service_env.write_text(
        "TELEGRAM_CODEX_BOT_TOKEN=test-token\nTELEGRAM_CODEX_BOT_USERNAME=viv_codex_bot\n",
        encoding="utf-8",
    )

    projects_path = tmp_path / "telegram-codex" / "projects.yaml"
    projects_path.parent.mkdir(parents=True, exist_ok=True)
    projects_path.write_text(
        """
default_project: viventium_core
projects:
  viventium_core:
    path: /tmp/workspace
""".strip(),
        encoding="utf-8",
    )

    settings_path = tmp_path / "telegram-codex" / "settings.yaml"
    settings_path.write_text(
        f"""
bot:
  env_file: {service_env}
runtime:
  paired_users_path: {custom_paired_users_path}
projects:
  registry_file: {projects_path}
""".strip(),
        encoding="utf-8",
    )

    monkeypatch.setenv("VIVENTIUM_TELEGRAM_CODEX_SETTINGS_FILE", str(settings_path))
    monkeypatch.setenv("VIVENTIUM_TELEGRAM_CODEX_PROJECTS_FILE", str(projects_path))
    monkeypatch.setenv("VIVENTIUM_TELEGRAM_CODEX_ENV_FILE", str(service_env))

    config = load_config(root=Path("/tmp/unused-root"))

    assert config.runtime.paired_users_path == custom_paired_users_path.resolve()
    assert config.runtime.paired_users_migration_sources == ()

from __future__ import annotations

import importlib.util
import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL_SUMMARY_PATH = REPO_ROOT / "scripts" / "viventium" / "install_summary.py"


def load_install_summary_module():
    spec = importlib.util.spec_from_file_location("viventium_install_summary", INSTALL_SUMMARY_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_service_rows_treats_localhost_api_health_as_running(monkeypatch) -> None:
    install_summary = load_install_summary_module()

    config = {
        "runtime": {"ports": {"lc_frontend_port": 3190, "lc_api_port": 3180, "playground_port": 3300}},
        "llm": {"primary": {"auth_mode": "connected_account"}},
        "voice": {"mode": "local"},
        "integrations": {},
    }

    def fake_http_ok(url: str) -> bool:
        return url in {
            "http://localhost:3190",
            "http://localhost:3180/api/health",
            "http://localhost:3300",
        }

    monkeypatch.setattr(install_summary, "http_ok", fake_http_ok)
    monkeypatch.setattr(install_summary, "local_network_host", lambda: None)

    rows = install_summary.build_service_rows(config, {}, probe_live=True)
    service_status = {name: status for name, status, _detail in rows}

    assert service_status["LibreChat Frontend"] == "Running"
    assert service_status["LibreChat API"] == "Running"
    assert service_status["Modern Playground"] == "Running"


def test_build_service_rows_accepts_ipv4_loopback_when_localhost_probe_fails(monkeypatch) -> None:
    install_summary = load_install_summary_module()

    config = {
        "runtime": {"ports": {"lc_frontend_port": 3190, "lc_api_port": 3180, "playground_port": 3300}},
        "llm": {"primary": {"auth_mode": "connected_account"}},
        "voice": {"mode": "local"},
        "integrations": {},
    }

    def fake_http_ok(url: str) -> bool:
        return url in {
            "http://127.0.0.1:3190",
            "http://127.0.0.1:3180/api/health",
            "http://127.0.0.1:3300",
        }

    monkeypatch.setattr(install_summary, "http_ok", fake_http_ok)
    monkeypatch.setattr(install_summary, "local_network_host", lambda: None)

    rows = install_summary.build_service_rows(config, {}, probe_live=True)
    service_status = {name: status for name, status, _detail in rows}

    assert service_status["LibreChat Frontend"] == "Running"
    assert service_status["LibreChat API"] == "Running"
    assert service_status["Modern Playground"] == "Running"


def test_build_service_rows_marks_invalid_telegram_bridge_as_misconfigured(monkeypatch, tmp_path: Path) -> None:
    install_summary = load_install_summary_module()

    config = {
        "runtime": {
            "profile": "isolated",
            "ports": {"lc_frontend_port": 3190, "lc_api_port": 3180, "playground_port": 3300},
        },
        "llm": {"primary": {"auth_mode": "connected_account"}},
        "voice": {"mode": "local"},
        "integrations": {
            "telegram": {"enabled": True},
        },
    }
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir(parents=True)

    def fake_http_ok(url: str) -> bool:
        return url in {
            "http://localhost:3190",
            "http://localhost:3180/api/health",
            "http://localhost:3300",
        }

    monkeypatch.setattr(install_summary, "http_ok", fake_http_ok)
    monkeypatch.setattr(install_summary, "local_network_host", lambda: None)

    rows = install_summary.build_service_rows(
        config,
        {
            "BOT_TOKEN": "not-a-telegram-token",
            "VIVENTIUM_RUNTIME_PROFILE": "isolated",
        },
        runtime_dir=runtime_dir,
        probe_live=True,
    )
    services = {name: (status, detail) for name, status, detail in rows}

    telegram_status, telegram_detail = services["Telegram Bridge"]
    assert telegram_status == "Misconfigured"
    assert "BotFather token" in telegram_detail


def test_build_service_rows_marks_running_telegram_bridge_from_pid_file(monkeypatch, tmp_path: Path) -> None:
    install_summary = load_install_summary_module()

    config = {
        "runtime": {
            "profile": "isolated",
            "ports": {"lc_frontend_port": 3190, "lc_api_port": 3180, "playground_port": 3300},
        },
        "llm": {"primary": {"auth_mode": "connected_account"}},
        "voice": {"mode": "local"},
        "integrations": {
            "telegram": {"enabled": True},
        },
    }
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir(parents=True)
    runtime_root = tmp_path / "state" / "runtime" / "isolated"
    runtime_root.mkdir(parents=True)
    (runtime_root / "telegram_bot.pid").write_text(str(os.getpid()), encoding="utf-8")

    def fake_http_ok(url: str) -> bool:
        return url in {
            "http://localhost:3190",
            "http://localhost:3180/api/health",
            "http://localhost:3300",
        }

    monkeypatch.setattr(install_summary, "http_ok", fake_http_ok)
    monkeypatch.setattr(install_summary, "local_network_host", lambda: None)

    rows = install_summary.build_service_rows(
        config,
        {
            "BOT_TOKEN": "123456789:Valid_botfather_token_value_ABCDEFGH",
            "VIVENTIUM_RUNTIME_PROFILE": "isolated",
        },
        runtime_dir=runtime_dir,
        probe_live=True,
    )
    services = {name: (status, detail) for name, status, detail in rows}

    telegram_status, telegram_detail = services["Telegram Bridge"]
    assert telegram_status == "Running"
    assert "Polling Telegram bridge" in telegram_detail


def test_build_service_rows_marks_pending_telegram_bridge_as_starting(monkeypatch, tmp_path: Path) -> None:
    install_summary = load_install_summary_module()

    config = {
        "runtime": {
            "profile": "isolated",
            "ports": {"lc_frontend_port": 3190, "lc_api_port": 3180, "playground_port": 3300},
        },
        "llm": {"primary": {"auth_mode": "connected_account"}},
        "voice": {"mode": "local"},
        "integrations": {
            "telegram": {"enabled": True},
        },
    }
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir(parents=True)
    runtime_root = tmp_path / "state" / "runtime" / "isolated"
    runtime_root.mkdir(parents=True)
    (runtime_root / "telegram_bot_deferred.pending").write_text("pending\n", encoding="utf-8")

    def fake_http_ok(url: str) -> bool:
        return url in {
            "http://localhost:3190",
            "http://localhost:3180/api/health",
            "http://localhost:3300",
        }

    monkeypatch.setattr(install_summary, "http_ok", fake_http_ok)
    monkeypatch.setattr(install_summary, "local_network_host", lambda: None)

    rows = install_summary.build_service_rows(
        config,
        {
            "BOT_TOKEN": "123456789:Valid_botfather_token_value_ABCDEFGH",
            "VIVENTIUM_RUNTIME_PROFILE": "isolated",
        },
        runtime_dir=runtime_dir,
        probe_live=True,
    )
    services = {name: (status, detail) for name, status, detail in rows}

    telegram_status, telegram_detail = services["Telegram Bridge"]
    assert telegram_status == "Starting"
    assert "Waiting for LibreChat API" in telegram_detail


def test_build_service_rows_warns_when_local_firecrawl_needs_more_docker_memory(monkeypatch) -> None:
    install_summary = load_install_summary_module()

    config = {
        "runtime": {"ports": {"lc_frontend_port": 3190, "lc_api_port": 3180, "playground_port": 3300}},
        "llm": {"primary": {"auth_mode": "connected_account"}},
        "voice": {"mode": "local"},
        "integrations": {
            "web_search": {
                "enabled": True,
                "search_provider": "searxng",
                "scraper_provider": "firecrawl",
            }
        },
    }

    def fake_http_ok(url: str) -> bool:
        return url in {
            "http://localhost:3190",
            "http://localhost:3180/api/health",
            "http://localhost:3300",
        }

    monkeypatch.setattr(install_summary, "http_ok", fake_http_ok)
    monkeypatch.setattr(install_summary, "port_open", lambda _port: False)
    monkeypatch.setattr(install_summary, "local_network_host", lambda: None)
    monkeypatch.setattr(
        install_summary,
        "docker_total_memory_bytes",
        lambda: 3 * 1024 * 1024 * 1024,
    )

    rows = install_summary.build_service_rows(
        config,
        {
            "START_SEARXNG": "true",
            "SEARXNG_INSTANCE_URL": "http://localhost:8082",
            "START_FIRECRAWL": "true",
            "FIRECRAWL_API_URL": "http://localhost:3003",
        },
        probe_live=True,
    )
    services = {name: (status, detail) for name, status, detail in rows}

    firecrawl_status, firecrawl_detail = services["Firecrawl"]
    assert firecrawl_status == "Needs Docker RAM"
    assert "3.0 GB" in firecrawl_detail
    assert "Firecrawl API" in firecrawl_detail


def test_build_setup_later_rows_mentions_ollama_for_conversation_recall() -> None:
    install_summary = load_install_summary_module()

    config = {
        "runtime": {
            "personalization": {"default_conversation_recall": False},
            "retrieval": {
                "embeddings": {
                    "provider": "ollama",
                    "model": "qwen3-embedding:0.6b",
                    "profile": "medium",
                }
            },
        },
        "integrations": {},
    }

    rows = install_summary.build_setup_later_rows(config)
    later = {name: detail for name, detail in rows}

    assert (
        later["Conversation Recall"]
        == "Docker Desktop and Ollama if you want local recall; first start pulls qwen3-embedding:0.6b"
    )


def test_build_next_steps_mentions_optional_shell_init(monkeypatch) -> None:
    install_summary = load_install_summary_module()

    config = {
        "runtime": {"ports": {"lc_frontend_port": 3190}},
        "llm": {"primary": {"auth_mode": "connected_account"}},
        "voice": {"mode": "local"},
        "integrations": {},
    }

    monkeypatch.setattr(install_summary, "local_network_host", lambda: "192.168.1.44")

    steps = install_summary.build_next_steps(config, {})

    assert any("bin/viventium shell-init" in step for step in steps)
    assert any("viventium" in step and "viv" in step for step in steps)
    assert any("192.168.1.44:3190" in step for step in steps)


def test_build_next_steps_prioritizes_connected_accounts_when_no_foundation_api_keys(monkeypatch) -> None:
    install_summary = load_install_summary_module()

    config = {
        "runtime": {"ports": {"lc_frontend_port": 3190}},
        "llm": {
            "primary": {"provider": "openai", "auth_mode": "connected_account"},
            "secondary": {"provider": "none", "auth_mode": "disabled"},
            "extra_provider_keys": {},
        },
        "voice": {"mode": "local"},
        "integrations": {},
    }

    monkeypatch.setattr(install_summary, "local_network_host", lambda: None)

    steps = install_summary.build_next_steps(config, {})
    notice = install_summary.build_connected_accounts_notice(config)

    assert "Settings -> Connected Accounts" in notice
    assert "OpenAI" in notice
    assert all("Connected Accounts" not in step for step in steps)


def test_build_service_rows_uses_live_public_network_state_for_remote_access(monkeypatch, tmp_path: Path) -> None:
    install_summary = load_install_summary_module()

    config = {
        "runtime": {
            "profile": "isolated",
            "network": {"remote_call_mode": "custom_domain"},
            "ports": {"lc_frontend_port": 3190, "lc_api_port": 3180, "playground_port": 3300},
        },
        "llm": {"primary": {"auth_mode": "connected_account"}},
        "voice": {"mode": "local"},
        "integrations": {},
    }
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir(parents=True)
    state_root = tmp_path / "state" / "runtime" / "isolated"
    state_root.mkdir(parents=True)
    (state_root / "public-network.json").write_text(
        '{"public_client_url":"https://app.example.test"}',
        encoding="utf-8",
    )

    monkeypatch.setattr(install_summary, "http_ok", lambda _url: True)
    monkeypatch.setattr(install_summary, "local_network_host", lambda: None)

    rows = install_summary.build_service_rows(
        config,
        {},
        runtime_dir=runtime_dir,
        probe_live=True,
    )
    services = {name: (status, detail) for name, status, detail in rows}

    remote_status, remote_detail = services["Remote Access"]
    assert remote_status == "Running"
    assert "https://app.example.test" in remote_detail


def test_build_service_rows_reports_action_required_when_remote_access_state_saved_an_error(
    monkeypatch, tmp_path: Path
) -> None:
    install_summary = load_install_summary_module()

    config = {
        "runtime": {
            "profile": "isolated",
            "network": {"remote_call_mode": "public_https_edge"},
            "ports": {"lc_frontend_port": 3190, "lc_api_port": 3180, "playground_port": 3300},
        },
        "llm": {"primary": {"auth_mode": "connected_account"}},
        "voice": {"mode": "local"},
        "integrations": {},
    }
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir(parents=True)
    state_root = tmp_path / "state" / "runtime" / "isolated"
    state_root.mkdir(parents=True)
    (state_root / "public-network.json").write_text(
        '{"provider":"public_https_edge","last_error":"Router already forwards TCP 80 to 10.88.111.46:50779"}',
        encoding="utf-8",
    )

    monkeypatch.setattr(install_summary, "http_ok", lambda _url: True)
    monkeypatch.setattr(install_summary, "local_network_host", lambda: None)

    rows = install_summary.build_service_rows(
        config,
        {"VIVENTIUM_PUBLIC_CLIENT_URL": "https://app.example.test"},
        runtime_dir=runtime_dir,
        probe_live=True,
    )
    services = {name: (status, detail) for name, status, detail in rows}

    remote_status, remote_detail = services["Remote Access"]
    assert remote_status == "Action Required"
    assert "Router already forwards TCP 80" in remote_detail
    assert "https://app.example.test" not in remote_detail


def test_build_service_rows_reports_auth_posture() -> None:
    install_summary = load_install_summary_module()

    config = {
        "runtime": {
            "auth": {
                "allow_registration": False,
                "allow_password_reset": False,
            },
            "ports": {"lc_frontend_port": 3190, "lc_api_port": 3180, "playground_port": 3300},
        },
        "llm": {"primary": {"auth_mode": "connected_account"}},
        "voice": {"mode": "local"},
        "integrations": {},
    }

    rows = install_summary.build_service_rows(config, {}, probe_live=False)
    services = {name: (status, detail) for name, status, detail in rows}

    assert services["Account Sign-up"] == ("Closed", "Only existing accounts can sign in")
    assert "password-reset-link" in services["Password Reset"][1]


def test_build_next_steps_prefers_live_public_network_state(monkeypatch, tmp_path: Path) -> None:
    install_summary = load_install_summary_module()

    config = {
        "runtime": {
            "profile": "isolated",
            "network": {"remote_call_mode": "custom_domain"},
            "ports": {"lc_frontend_port": 3190},
        },
        "llm": {"primary": {"auth_mode": "connected_account"}},
        "voice": {"mode": "local"},
        "integrations": {},
    }
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir(parents=True)
    state_root = tmp_path / "state" / "runtime" / "isolated"
    state_root.mkdir(parents=True)
    (state_root / "public-network.json").write_text(
        '{"public_client_url":"https://app.example.test"}',
        encoding="utf-8",
    )

    monkeypatch.setattr(install_summary, "local_network_host", lambda: None)

    steps = install_summary.build_next_steps(config, {}, runtime_dir)

    assert any("https://app.example.test" in step for step in steps)
    assert any("password-reset-link" in step for step in steps)


def test_build_next_steps_prioritizes_remote_access_recovery_when_public_edge_failed(
    monkeypatch, tmp_path: Path
) -> None:
    install_summary = load_install_summary_module()

    config = {
        "runtime": {
            "profile": "isolated",
            "network": {"remote_call_mode": "public_https_edge"},
            "ports": {"lc_frontend_port": 3190},
        },
        "llm": {"primary": {"auth_mode": "connected_account"}},
        "voice": {"mode": "local"},
        "integrations": {},
    }
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir(parents=True)
    state_root = tmp_path / "state" / "runtime" / "isolated"
    state_root.mkdir(parents=True)
    (state_root / "public-network.json").write_text(
        '{"provider":"public_https_edge","last_error":"Router already forwards TCP 80 to 10.88.111.46:50779"}',
        encoding="utf-8",
    )

    monkeypatch.setattr(install_summary, "local_network_host", lambda: None)

    steps = install_summary.build_next_steps(
        config,
        {"VIVENTIUM_PUBLIC_CLIENT_URL": "https://app.example.test"},
        runtime_dir,
    )

    assert any("Remote access could not start on this run." in step for step in steps)
    assert any("bin/viventium start" in step for step in steps)
    assert all("Outside your local network, open [cyan]https://app.example.test[/cyan]." != step for step in steps)


def test_build_next_steps_skips_connected_accounts_priority_when_foundation_api_key_exists(monkeypatch) -> None:
    install_summary = load_install_summary_module()

    config = {
        "runtime": {"ports": {"lc_frontend_port": 3190}},
        "llm": {
            "primary": {
                "provider": "openai",
                "auth_mode": "api_key",
                "secret_value": "openai-test",
            },
            "secondary": {"provider": "none", "auth_mode": "disabled"},
            "extra_provider_keys": {},
        },
        "voice": {"mode": "local"},
        "integrations": {},
    }

    monkeypatch.setattr(install_summary, "local_network_host", lambda: None)

    steps = install_summary.build_next_steps(config, {})
    notice = install_summary.build_connected_accounts_notice(config)

    assert notice is None
    assert all("Connected Accounts" not in step for step in steps)


def test_build_next_steps_clarifies_native_installs_use_processes(monkeypatch) -> None:
    install_summary = load_install_summary_module()

    config = {
        "install": {"mode": "native"},
        "runtime": {"ports": {"lc_frontend_port": 3190}},
        "llm": {"primary": {"provider": "openai", "auth_mode": "api_key", "secret_value": "openai-test"}},
        "voice": {"mode": "local"},
        "integrations": {},
    }

    monkeypatch.setattr(install_summary, "local_network_host", lambda: None)

    steps = install_summary.build_next_steps(config, {})

    assert any("local background processes" in step for step in steps)

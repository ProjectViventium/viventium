from __future__ import annotations

import importlib.util
import os
import sqlite3
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL_SUMMARY_PATH = REPO_ROOT / "scripts" / "viventium" / "install_summary.py"
VALID_TELEGRAM_TOKEN = "123456789:" + "telegram_test_fixture_" + "ABCDEFGH"


def load_install_summary_module():
    spec = importlib.util.spec_from_file_location("viventium_install_summary", INSTALL_SUMMARY_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_http_ok_prefers_curl_when_available(monkeypatch) -> None:
    install_summary = load_install_summary_module()
    calls: list[list[str]] = []

    monkeypatch.setattr(install_summary.shutil, "which", lambda command: "/usr/bin/curl" if command == "curl" else None)

    def fake_run(args, **_kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(install_summary.subprocess, "run", fake_run)
    monkeypatch.setattr(install_summary.urllib.request, "urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("urllib fallback should not run when curl succeeds")))

    assert install_summary.http_ok("http://localhost:3180/api/health") is True
    assert calls == [["/usr/bin/curl", "-fsS", "-o", "/dev/null", "--max-time", "2", "http://localhost:3180/api/health"]]


def test_http_endpoint_reachable_treats_auth_challenge_as_alive(monkeypatch) -> None:
    install_summary = load_install_summary_module()

    monkeypatch.setattr(install_summary, "http_status", lambda _url: 401)

    assert install_summary.http_endpoint_reachable("http://localhost:6274/mcp") is True


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
                "http://127.0.0.1:3300/api/health",
        }

    monkeypatch.setattr(install_summary, "http_ok", fake_http_ok)
    monkeypatch.setattr(install_summary, "local_network_host", lambda: None)

    rows = install_summary.build_service_rows(config, {}, probe_live=True)
    service_status = {name: status for name, status, _detail in rows}

    assert service_status["LibreChat Frontend"] == "Running"
    assert service_status["LibreChat API"] == "Running"
    assert service_status["Modern Playground"] == "Running"


def test_build_service_rows_marks_mcp_running_on_auth_challenge(monkeypatch, tmp_path: Path) -> None:
    install_summary = load_install_summary_module()

    config = {
        "runtime": {"profile": "isolated", "ports": {"lc_frontend_port": 3190, "lc_api_port": 3180, "playground_port": 3300}},
        "llm": {"primary": {"auth_mode": "connected_account"}},
        "voice": {"mode": "local"},
        "integrations": {
            "google_workspace": {"enabled": True},
            "ms365": {"enabled": True},
        },
    }
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir(parents=True)
    state_root = tmp_path / "state" / "runtime" / "isolated"
    state_root.mkdir(parents=True)
    (state_root / "stack-owner.json").write_text('{"command":"start"}\n', encoding="utf-8")

    monkeypatch.setattr(
        install_summary,
        "http_ok",
        lambda url: url
        in {
            "http://localhost:3190",
            "http://localhost:3180/api/health",
            "http://localhost:3300",
        },
    )
    monkeypatch.setattr(install_summary, "http_status", lambda url: 401 if url.endswith("/mcp") else None)
    monkeypatch.setattr(install_summary, "local_network_host", lambda: None)

    rows = install_summary.build_service_rows(
        config,
        {
            "GOOGLE_WORKSPACE_MCP_URL": "http://localhost:8111/mcp",
            "MS365_MCP_SERVER_URL": "http://localhost:6274/mcp",
            "START_GOOGLE_MCP": "true",
            "START_MS365_MCP": "true",
            "VIVENTIUM_RUNTIME_PROFILE": "isolated",
        },
        runtime_dir=runtime_dir,
        probe_live=True,
    )
    services = {name: (status, detail) for name, status, detail in rows}

    assert services["Google Workspace MCP"] == ("Running", "http://localhost:8111/mcp")
    assert services["Microsoft 365 MCP"] == ("Running", "http://localhost:6274/mcp")


def test_build_service_rows_marks_started_mcp_action_required_after_startup(
    monkeypatch, tmp_path: Path
) -> None:
    install_summary = load_install_summary_module()

    config = {
        "runtime": {"profile": "isolated", "ports": {"lc_frontend_port": 3190, "lc_api_port": 3180, "playground_port": 3300}},
        "llm": {"primary": {"auth_mode": "connected_account"}},
        "voice": {"mode": "local"},
        "integrations": {"ms365": {"enabled": True}},
    }
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir(parents=True)
    state_root = tmp_path / "state" / "runtime" / "isolated"
    state_root.mkdir(parents=True)
    (state_root / "stack-owner.json").write_text('{"command":"start"}\n', encoding="utf-8")

    monkeypatch.setattr(
        install_summary,
        "http_ok",
        lambda url: url
        in {
            "http://localhost:3190",
            "http://localhost:3180/api/health",
            "http://localhost:3300",
        },
    )
    monkeypatch.setattr(install_summary, "http_status", lambda _url: None)
    monkeypatch.setattr(install_summary, "local_network_host", lambda: None)

    rows = install_summary.build_service_rows(
        config,
        {
            "MS365_MCP_SERVER_URL": "http://localhost:6274/mcp",
            "START_MS365_MCP": "true",
            "VIVENTIUM_RUNTIME_PROFILE": "isolated",
        },
        runtime_dir=runtime_dir,
        probe_live=True,
    )
    services = {name: (status, detail) for name, status, detail in rows}

    assert services["Microsoft 365 MCP"][0] == "Action Required"
    assert "Endpoint not reachable" in services["Microsoft 365 MCP"][1]


def test_build_service_rows_marks_started_mcp_starting_while_cli_lock_is_active(
    monkeypatch, tmp_path: Path
) -> None:
    install_summary = load_install_summary_module()

    config = {
        "runtime": {"profile": "isolated", "ports": {"lc_frontend_port": 3190, "lc_api_port": 3180, "playground_port": 3300}},
        "llm": {"primary": {"auth_mode": "connected_account"}},
        "voice": {"mode": "local"},
        "integrations": {"ms365": {"enabled": True}},
    }
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir(parents=True)
    state_root = tmp_path / "state" / "runtime" / "isolated"
    state_root.mkdir(parents=True)
    (state_root / "stack-owner.json").write_text('{"command":"start"}\n', encoding="utf-8")
    lock_dir = tmp_path / "state" / "cli-operation.lock"
    lock_dir.mkdir(parents=True)
    (lock_dir / "pid").write_text(str(os.getpid()), encoding="utf-8")
    (lock_dir / "process_command").write_text(
        install_summary.process_command_line(os.getpid()),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        install_summary,
        "http_ok",
        lambda url: url
        in {
            "http://localhost:3190",
            "http://localhost:3180/api/health",
            "http://localhost:3300",
        },
    )
    monkeypatch.setattr(install_summary, "http_status", lambda _url: None)
    monkeypatch.setattr(install_summary, "local_network_host", lambda: None)

    rows = install_summary.build_service_rows(
        config,
        {
            "MS365_MCP_SERVER_URL": "http://localhost:6274/mcp",
            "START_MS365_MCP": "true",
            "VIVENTIUM_RUNTIME_PROFILE": "isolated",
        },
        runtime_dir=runtime_dir,
        probe_live=True,
    )
    services = {name: (status, detail) for name, status, detail in rows}

    assert services["Microsoft 365 MCP"][0] == "Starting"
    assert "Waiting for" in services["Microsoft 365 MCP"][1]


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
            "BOT_TOKEN": VALID_TELEGRAM_TOKEN,
            "VIVENTIUM_RUNTIME_PROFILE": "isolated",
        },
        runtime_dir=runtime_dir,
        probe_live=True,
    )
    services = {name: (status, detail) for name, status, detail in rows}

    telegram_status, telegram_detail = services["Telegram Bridge"]
    assert telegram_status == "Running"
    assert "Polling Telegram bridge" in telegram_detail


def test_build_service_rows_marks_running_telegram_bridge_with_dead_api_as_issue(monkeypatch, tmp_path: Path) -> None:
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
            "http://localhost:3300",
        }

    monkeypatch.setattr(install_summary, "http_ok", fake_http_ok)
    monkeypatch.setattr(install_summary, "local_network_host", lambda: None)

    rows = install_summary.build_service_rows(
        config,
        {
            "BOT_TOKEN": VALID_TELEGRAM_TOKEN,
            "VIVENTIUM_LIBRECHAT_ORIGIN": "http://127.0.0.1:3180",
            "VIVENTIUM_RUNTIME_PROFILE": "isolated",
        },
        runtime_dir=runtime_dir,
        probe_live=True,
    )
    services = {name: (status, detail) for name, status, detail in rows}

    telegram_status, telegram_detail = services["Telegram Bridge"]
    assert telegram_status == "Running with issues"
    assert "LibreChat API is unreachable" in telegram_detail
    assert "Telegram cannot start new chats" in telegram_detail


def test_build_service_rows_marks_running_telegram_conflict_as_issue(monkeypatch, tmp_path: Path) -> None:
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
    logs_root = runtime_root / "logs"
    logs_root.mkdir(parents=True)
    pid_file = runtime_root / "telegram_bot.pid"
    pid_file.write_text(str(os.getpid()), encoding="utf-8")
    (logs_root / "telegram_bot.log").write_text(
        "telegram.error.Conflict: terminated by other getUpdates request; make sure that only one bot instance is running\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(install_summary, "http_ok", lambda _url: True)
    monkeypatch.setattr(install_summary, "local_network_host", lambda: None)

    rows = install_summary.build_service_rows(
        config,
        {
            "BOT_TOKEN": VALID_TELEGRAM_TOKEN,
            "VIVENTIUM_RUNTIME_PROFILE": "isolated",
        },
        runtime_dir=runtime_dir,
        probe_live=True,
    )
    services = {name: (status, detail) for name, status, detail in rows}

    telegram_status, telegram_detail = services["Telegram Bridge"]
    assert telegram_status == "Running with issues"
    assert "polling conflict" in telegram_detail
    assert "getUpdates" not in telegram_detail


def test_build_service_rows_ignores_telegram_conflict_before_latest_recovery(
    monkeypatch, tmp_path: Path
) -> None:
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
    logs_root = runtime_root / "logs"
    logs_root.mkdir(parents=True)
    pid_file = runtime_root / "telegram_bot.pid"
    pid_file.write_text(str(os.getpid()), encoding="utf-8")
    (logs_root / "telegram_bot.log").write_text(
        "\n".join(
            [
                "telegram.error.Conflict: terminated by other getUpdates request",
                "Starting polling mode with timeout=30s",
                "Application started",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(install_summary, "http_ok", lambda _url: True)
    monkeypatch.setattr(install_summary, "local_network_host", lambda: None)

    rows = install_summary.build_service_rows(
        config,
        {
            "BOT_TOKEN": VALID_TELEGRAM_TOKEN,
            "VIVENTIUM_RUNTIME_PROFILE": "isolated",
        },
        runtime_dir=runtime_dir,
        probe_live=True,
    )
    services = {name: (status, detail) for name, status, detail in rows}

    telegram_status, telegram_detail = services["Telegram Bridge"]
    assert telegram_status == "Running"
    assert telegram_detail == "Polling Telegram bridge on this Mac"


def test_build_service_rows_marks_running_telegram_auth_error_as_issue(
    monkeypatch, tmp_path: Path
) -> None:
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
    logs_root = runtime_root / "logs"
    logs_root.mkdir(parents=True)
    pid_file = runtime_root / "telegram_bot.pid"
    pid_file.write_text(str(os.getpid()), encoding="utf-8")
    (logs_root / "telegram_bot.log").write_text(
        "OpenAI connected-account refresh failed while processing a Telegram reply\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(install_summary, "http_ok", lambda _url: True)
    monkeypatch.setattr(install_summary, "local_network_host", lambda: None)

    rows = install_summary.build_service_rows(
        config,
        {
            "BOT_TOKEN": VALID_TELEGRAM_TOKEN,
            "VIVENTIUM_RUNTIME_PROFILE": "isolated",
        },
        runtime_dir=runtime_dir,
        probe_live=True,
    )
    services = {name: (status, detail) for name, status, detail in rows}

    telegram_status, telegram_detail = services["Telegram Bridge"]
    assert telegram_status == "Running with issues"
    assert "authentication failure" in telegram_detail
    assert "connected-account refresh failed" not in telegram_detail


def test_build_service_rows_marks_stopped_telegram_auth_error_as_action_required(
    monkeypatch, tmp_path: Path
) -> None:
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
    logs_root = tmp_path / "state" / "runtime" / "isolated" / "logs"
    logs_root.mkdir(parents=True)
    (logs_root / "telegram_bot.log").write_text(
        "provider credentials rejected while processing a Telegram reply\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(install_summary, "http_ok", lambda _url: True)
    monkeypatch.setattr(install_summary, "local_network_host", lambda: None)

    rows = install_summary.build_service_rows(
        config,
        {
            "BOT_TOKEN": VALID_TELEGRAM_TOKEN,
            "VIVENTIUM_RUNTIME_PROFILE": "isolated",
        },
        runtime_dir=runtime_dir,
        probe_live=True,
    )
    services = {name: (status, detail) for name, status, detail in rows}

    telegram_status, telegram_detail = services["Telegram Bridge"]
    assert telegram_status == "Action Required"
    assert "authentication failure" in telegram_detail
    assert "credentials rejected" not in telegram_detail


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
            "BOT_TOKEN": VALID_TELEGRAM_TOKEN,
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
        later["Conversation Recall/RAG"]
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

    monkeypatch.setattr(install_summary, "local_network_host", lambda: "198.51.100.44")

    steps = install_summary.build_next_steps(config, {})

    assert any("bin/viventium shell-init" in step for step in steps)
    assert any("viventium" in step and "viv" in step for step in steps)
    assert any("198.51.100.44:3190" in step for step in steps)


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


def test_build_connected_accounts_notice_matches_anthropic_only_foundation_contract() -> None:
    install_summary = load_install_summary_module()

    config = {
        "runtime": {"ports": {"lc_frontend_port": 3190}},
        "llm": {
            "primary": {"provider": "anthropic", "auth_mode": "connected_account"},
            "secondary": {"provider": "none", "auth_mode": "disabled"},
            "extra_provider_keys": {},
        },
        "voice": {"mode": "local"},
        "integrations": {},
    }

    notice = install_summary.build_connected_accounts_notice(config)

    assert "Anthropic" in notice
    assert "OpenAI" not in notice


def test_build_connected_accounts_notice_mentions_workspace_accounts_when_enabled() -> None:
    install_summary = load_install_summary_module()

    config = {
        "runtime": {"ports": {"lc_frontend_port": 3190}},
        "llm": {
            "primary": {
                "provider": "openai",
                "auth_mode": "api_key",
                "secret_ref": "openai-key",
            },
            "secondary": {"provider": "none", "auth_mode": "disabled"},
            "extra_provider_keys": {},
        },
        "voice": {"mode": "local"},
        "integrations": {
            "google_workspace": {"enabled": True},
            "ms365": {"enabled": True},
        },
    }

    notice = install_summary.build_connected_accounts_notice(config)

    assert "Google Workspace" in notice
    assert "Microsoft 365" in notice
    assert "Activation can succeed" in notice


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
    (state_root / "stack-owner.json").write_text('{"command":"start"}\n', encoding="utf-8")

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
        '{"provider":"public_https_edge","last_error":"Router already forwards TCP 80 to 192.0.2.44:50779"}',
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


def test_build_service_rows_treats_missing_core_surfaces_as_configured_after_recorded_stop(
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
    (state_root / "stack-owner.json").write_text('{"command":"stop"}\n', encoding="utf-8")

    monkeypatch.setattr(install_summary, "http_ok", lambda _url: False)
    monkeypatch.setattr(install_summary, "local_network_host", lambda: None)

    rows = install_summary.build_service_rows(
        config,
        {},
        runtime_dir=runtime_dir,
        probe_live=True,
    )
    services = {name: (status, detail) for name, status, detail in rows}
    heading, intro, table_title = install_summary.resolve_summary_heading(
        True,
        rows,
        install_summary.stack_expected_live(config, {}, runtime_dir),
    )

    assert services["LibreChat Frontend"][0] == "Configured"
    assert services["LibreChat API"][0] == "Configured"
    assert services["Modern Playground"][0] == "Configured"
    assert services["Remote Access"][0] == "Configured"
    assert heading == "Viventium is configured"
    assert table_title == "Configured Services"
    assert "Start the stack" in intro


def test_build_service_rows_warns_when_status_runs_from_different_checkout(
    monkeypatch, tmp_path: Path
) -> None:
    install_summary = load_install_summary_module()

    config = {
        "runtime": {
            "profile": "isolated",
            "ports": {"lc_frontend_port": 3190, "lc_api_port": 3180, "playground_port": 3300},
        },
        "llm": {"primary": {"auth_mode": "connected_account"}},
        "voice": {"mode": "disabled"},
        "integrations": {},
    }
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir(parents=True)
    state_root = tmp_path / "state" / "runtime" / "isolated"
    state_root.mkdir(parents=True)
    owner_repo = tmp_path / "live-checkout"
    current_repo = tmp_path / "review-checkout"
    owner_repo.mkdir()
    current_repo.mkdir()
    (state_root / "stack-owner.json").write_text(
        f'{{"command":"start","repoRoot":"{owner_repo}"}}\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(install_summary, "http_ok", lambda _url: False)
    monkeypatch.setattr(install_summary, "local_network_host", lambda: None)

    rows = install_summary.build_service_rows(
        config,
        {},
        runtime_dir=runtime_dir,
        repo_root=current_repo,
        probe_live=True,
    )
    services = {name: (status, detail) for name, status, detail in rows}

    checkout_status, checkout_detail = services["Runtime Checkout"]
    assert checkout_status == "Different Checkout"
    assert "live-checkout" in checkout_detail
    assert "review-checkout" in checkout_detail


def test_build_service_rows_marks_conversation_recall_action_required_after_startup_window(
    monkeypatch, tmp_path: Path
) -> None:
    install_summary = load_install_summary_module()

    config = {
        "runtime": {
            "profile": "isolated",
            "personalization": {"default_conversation_recall": True},
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
    (state_root / "stack-owner.json").write_text('{"command":"start"}\n', encoding="utf-8")

    monkeypatch.setattr(install_summary, "http_ok", lambda _url: False)
    monkeypatch.setattr(install_summary, "local_network_host", lambda: None)

    rows = install_summary.build_service_rows(
        config,
        {"RAG_API_URL": "http://localhost:8110"},
        runtime_dir=runtime_dir,
        probe_live=True,
    )
    services = {name: (status, detail) for name, status, detail in rows}

    assert services["Conversation Recall"] == ("Action Required", "http://localhost:8110")


def test_build_service_rows_marks_conversation_recall_starting_during_cli_operation(
    monkeypatch, tmp_path: Path
) -> None:
    install_summary = load_install_summary_module()

    config = {
        "runtime": {
            "profile": "isolated",
            "personalization": {"default_conversation_recall": True},
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
    (state_root / "stack-owner.json").write_text('{"command":"start"}\n', encoding="utf-8")

    monkeypatch.setattr(install_summary, "http_ok", lambda _url: False)
    monkeypatch.setattr(install_summary, "local_network_host", lambda: None)
    monkeypatch.setattr(install_summary, "cli_operation_running", lambda _runtime_dir: True)

    rows = install_summary.build_service_rows(
        config,
        {"RAG_API_URL": "http://localhost:8110"},
        runtime_dir=runtime_dir,
        probe_live=True,
    )
    services = {name: (status, detail) for name, status, detail in rows}

    assert services["Conversation Recall"] == ("Starting", "http://localhost:8110")


def test_stale_start_supervisor_lock_does_not_keep_services_in_starting_state(
    monkeypatch, tmp_path: Path
) -> None:
    install_summary = load_install_summary_module()

    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir(parents=True)
    lock_dir = tmp_path / "state" / "cli-operation.lock"
    lock_dir.mkdir(parents=True)
    pid_path = lock_dir / "pid"
    command_path = lock_dir / "command"
    pid_path.write_text(f"{os.getpid()}\n", encoding="utf-8")
    command_path.write_text("start\n", encoding="utf-8")
    old_time = 1_700_000_000
    os.utime(pid_path, (old_time, old_time))
    os.utime(command_path, (old_time, old_time))

    monkeypatch.setenv("VIVENTIUM_CLI_STARTUP_WINDOW_SECONDS", "60")

    assert install_summary.cli_operation_running(runtime_dir) is False


def test_stale_non_start_cli_lock_still_counts_as_running(
    monkeypatch, tmp_path: Path
) -> None:
    install_summary = load_install_summary_module()

    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir(parents=True)
    lock_dir = tmp_path / "state" / "cli-operation.lock"
    lock_dir.mkdir(parents=True)
    pid_path = lock_dir / "pid"
    command_path = lock_dir / "command"
    pid_path.write_text(f"{os.getpid()}\n", encoding="utf-8")
    command_path.write_text("upgrade\n", encoding="utf-8")
    (lock_dir / "process_command").write_text(
        install_summary.process_command_line(os.getpid()),
        encoding="utf-8",
    )
    old_time = 1_700_000_000
    os.utime(pid_path, (old_time, old_time))
    os.utime(command_path, (old_time, old_time))

    monkeypatch.setenv("VIVENTIUM_CLI_STARTUP_WINDOW_SECONDS", "60")

    assert install_summary.cli_operation_running(runtime_dir) is True


def test_cli_operation_running_rejects_reused_pid_with_mismatched_fingerprint(tmp_path: Path) -> None:
    install_summary = load_install_summary_module()

    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir(parents=True)
    lock_dir = tmp_path / "state" / "cli-operation.lock"
    lock_dir.mkdir(parents=True)
    (lock_dir / "pid").write_text(f"{os.getpid()}\n", encoding="utf-8")
    (lock_dir / "command").write_text("install\n", encoding="utf-8")
    (lock_dir / "process_command").write_text("stale-viventium-process-fingerprint\n", encoding="utf-8")

    assert install_summary.cli_operation_running(runtime_dir) is False


def test_build_service_rows_marks_conversation_recall_running_from_health_endpoint(
    monkeypatch, tmp_path: Path
) -> None:
    install_summary = load_install_summary_module()

    config = {
        "runtime": {
            "profile": "isolated",
            "personalization": {"default_conversation_recall": True},
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
    (state_root / "stack-owner.json").write_text('{"command":"start"}\n', encoding="utf-8")

    def fake_http_ok(url: str) -> bool:
        return url == "http://localhost:8110/health"

    monkeypatch.setattr(install_summary, "http_ok", fake_http_ok)
    monkeypatch.setattr(install_summary, "local_network_host", lambda: None)

    rows = install_summary.build_service_rows(
        config,
        {"RAG_API_URL": "http://localhost:8110"},
        runtime_dir=runtime_dir,
        probe_live=True,
    )
    services = {name: (status, detail) for name, status, detail in rows}

    assert services["Conversation Recall"] == ("Running", "http://localhost:8110")


def test_resolve_summary_heading_reports_live_startup_when_stack_should_be_live(
    monkeypatch, tmp_path: Path
) -> None:
    install_summary = load_install_summary_module()

    config = {
        "runtime": {
            "profile": "isolated",
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
    (state_root / "stack-owner.json").write_text('{"command":"start"}\n', encoding="utf-8")

    def fake_http_ok(url: str) -> bool:
        return url in {
            "http://localhost:3180/api/health",
            "http://localhost:3300",
        }

    monkeypatch.setattr(install_summary, "http_ok", fake_http_ok)
    monkeypatch.setattr(install_summary, "local_network_host", lambda: None)

    rows = install_summary.build_service_rows(
        config,
        {},
        runtime_dir=runtime_dir,
        probe_live=True,
    )
    heading, intro, table_title = install_summary.resolve_summary_heading(
        True,
        rows,
        install_summary.stack_expected_live(config, {}, runtime_dir),
    )

    services = {name: (status, detail) for name, status, detail in rows}
    assert services["LibreChat Frontend"][0] == "Starting"
    assert services["LibreChat API"][0] == "Running"
    assert services["Modern Playground"][0] == "Running"
    assert heading == "Viventium is still starting"
    assert "live surfaces" in intro
    assert table_title == "Live Services"


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
        "llm": {"primary": {"provider": "openai", "auth_mode": "connected_account"}},
        "voice": {"mode": "local"},
        "integrations": {},
    }

    rows = install_summary.build_service_rows(config, {}, probe_live=False)
    services = {name: (status, detail) for name, status, detail in rows}

    assert services["Primary AI"] == (
        "Action Required",
        "Connect OpenAI in Settings > Account > Connected Accounts",
    )
    assert services["Account Sign-up"] == ("Closed", "Only existing accounts can sign in")
    assert "password-reset-link" in services["Password Reset"][1]


def test_build_service_rows_does_not_report_connect_openai_when_account_route_is_configured() -> None:
    install_summary = load_install_summary_module()

    config = {
        "runtime": {
            "auth": {
                "allow_registration": False,
                "allow_password_reset": False,
            },
            "ports": {"lc_frontend_port": 3190, "lc_api_port": 3180, "playground_port": 3300},
        },
        "llm": {"primary": {"provider": "openai", "auth_mode": "connected_account"}},
        "voice": {"mode": "local"},
        "integrations": {},
    }
    runtime_env = {
        "VIVENTIUM_LOCAL_SUBSCRIPTION_AUTH": "true",
        "VIVENTIUM_OPENAI_AUTH_MODE": "connected_account",
    }

    rows = install_summary.build_service_rows(config, runtime_env, probe_live=False)
    services = {name: (status, detail) for name, status, detail in rows}

    status, detail = services["Primary AI"]
    assert status == "Configured"
    assert "Connect OpenAI" not in detail
    assert "account-scoped route configured" in detail


def test_build_service_rows_finds_repo_local_telegram_pid_files(monkeypatch, tmp_path: Path) -> None:
    install_summary = load_install_summary_module()

    config = {
        "runtime": {
            "profile": "isolated",
            "ports": {"lc_frontend_port": 3190, "lc_api_port": 3180, "playground_port": 3300},
        },
        "llm": {"primary": {"provider": "openai", "auth_mode": "connected_account"}},
        "voice": {"mode": "local"},
        "integrations": {
            "telegram": {"enabled": True},
            "telegram_codex": {"enabled": True},
        },
    }
    runtime_env = {
        "BOT_TOKEN": VALID_TELEGRAM_TOKEN,
        "TELEGRAM_CODEX_BOT_TOKEN": VALID_TELEGRAM_TOKEN,
    }
    runtime_dir = tmp_path / "app-support" / "runtime"
    runtime_dir.mkdir(parents=True)
    stale_state = tmp_path / "app-support" / "state" / "runtime" / "isolated"
    stale_state.mkdir(parents=True)
    (stale_state / "telegram_bot.pid").write_text("111\n", encoding="utf-8")
    (stale_state / "telegram_codex.pid").write_text("222\n", encoding="utf-8")

    repo_root = tmp_path / "checkout"
    repo_state = repo_root / ".viventium" / "runtime" / "isolated"
    repo_state.mkdir(parents=True)
    bot_pid = repo_state / "telegram_bot.pid"
    codex_pid = repo_state / "telegram_codex.pid"
    bot_pid.write_text("333\n", encoding="utf-8")
    codex_pid.write_text("444\n", encoding="utf-8")

    def fake_pid_running(path: Path) -> bool:
        return path in {bot_pid, codex_pid}

    monkeypatch.setattr(install_summary, "http_ok", lambda _url: True)
    monkeypatch.setattr(install_summary, "local_network_host", lambda: None)
    monkeypatch.setattr(install_summary, "pid_file_process_running", fake_pid_running)

    rows = install_summary.build_service_rows(
        config,
        runtime_env,
        runtime_dir=runtime_dir,
        repo_root=repo_root,
        probe_live=True,
    )
    services = {name: (status, detail) for name, status, detail in rows}

    assert services["Telegram Bridge"] == ("Running", "Polling Telegram bridge on this Mac")
    assert services["Telegram Codex"] == ("Running", "Polling Telegram Codex on this Mac")


def test_build_service_rows_reports_bootstrap_only_registration_mode() -> None:
    install_summary = load_install_summary_module()

    config = {
        "runtime": {
            "auth": {
                "allow_registration": True,
                "bootstrap_registration_once": True,
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

    assert services["Account Sign-up"] == (
        "Bootstrap Only",
        "Browser sign-up stays open only until the first account is created, then closes automatically",
    )


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
        '{"provider":"public_https_edge","last_error":"Router already forwards TCP 80 to 192.0.2.44:50779"}',
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


def test_build_next_steps_mentions_bootstrap_only_registration_mode(monkeypatch) -> None:
    install_summary = load_install_summary_module()

    config = {
        "runtime": {
            "auth": {
                "allow_registration": True,
                "bootstrap_registration_once": True,
            },
            "ports": {"lc_frontend_port": 3190},
        },
        "llm": {"primary": {"auth_mode": "connected_account"}},
        "voice": {"mode": "local"},
        "integrations": {},
    }

    monkeypatch.setattr(install_summary, "local_network_host", lambda: None)

    steps = install_summary.build_next_steps(config, {})

    assert any("closes automatically after the first account is created" in step for step in steps)


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


def test_resolve_summary_heading_reports_starting_until_core_surfaces_are_live() -> None:
    install_summary = load_install_summary_module()

    heading, intro, table_title = install_summary.resolve_summary_heading(
        True,
        [
            ("LibreChat Frontend", "Starting", "http://localhost:3190"),
            ("LibreChat API", "Running", "http://localhost:3180/api"),
            ("Modern Playground", "Running", "http://localhost:3300"),
        ],
        True,
    )

    assert heading == "Viventium is still starting"
    assert "still warming up" in intro
    assert table_title == "Live Services"


def test_resolve_summary_heading_reports_ready_once_core_surfaces_are_live() -> None:
    install_summary = load_install_summary_module()

    heading, intro, table_title = install_summary.resolve_summary_heading(
        True,
        [
            ("LibreChat Frontend", "Running", "http://localhost:3190"),
            ("LibreChat API", "Running", "http://localhost:3180/api"),
            ("Modern Playground", "Running", "http://localhost:3300"),
        ],
        True,
    )

    assert heading == "Viventium is ready"
    assert "live surfaces" in intro
    assert table_title == "Live Services"


def test_resolve_summary_heading_reports_attention_when_enabled_surface_is_broken() -> None:
    install_summary = load_install_summary_module()

    heading, intro, table_title = install_summary.resolve_summary_heading(
        True,
        [
            ("LibreChat Frontend", "Running", "http://localhost:3190"),
            ("LibreChat API", "Running", "http://localhost:3180/api"),
            ("Modern Playground", "Running", "http://localhost:3300"),
            ("Conversation Recall", "Action Required", "http://localhost:8110"),
        ],
        True,
    )

    assert heading == "Viventium needs attention"
    assert "not healthy" in intro
    assert table_title == "Live Services"


def test_resolve_summary_heading_reports_attention_for_running_with_issues() -> None:
    install_summary = load_install_summary_module()

    heading, intro, table_title = install_summary.resolve_summary_heading(
        True,
        [
            ("LibreChat Frontend", "Running", "http://localhost:3190"),
            ("LibreChat API", "Running", "http://localhost:3180/api"),
            ("Modern Playground", "Running", "http://localhost:3300"),
            (
                "Telegram Bridge",
                "Running with issues",
                "Recent Telegram polling conflict detected.",
            ),
        ],
        True,
    )

    assert heading == "Viventium needs attention"
    assert "not healthy" in intro
    assert table_title == "Live Services"


def test_build_service_rows_reports_status_bar_helper_not_running(
    monkeypatch, tmp_path: Path
) -> None:
    install_summary = load_install_summary_module()

    config = {
        "runtime": {
            "profile": "isolated",
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
    (state_root / "stack-owner.json").write_text('{"command":"start"}\n', encoding="utf-8")
    (tmp_path / "helper-config.json").write_text(
        '{"showInStatusBar": true, "repoRoot": "/path/to/viventium"}\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(install_summary.sys, "platform", "darwin")
    monkeypatch.setattr(install_summary, "http_ok", lambda _url: True)
    monkeypatch.setattr(install_summary, "local_network_host", lambda: None)
    monkeypatch.setattr(install_summary, "process_running_by_name", lambda _name: False)

    rows = install_summary.build_service_rows(
        config,
        {},
        runtime_dir=runtime_dir,
        probe_live=True,
    )
    services = {name: (status, detail) for name, status, detail in rows}

    assert services["macOS Status Bar Helper"][0] == "Action Required"
    assert "not running" in services["macOS Status Bar Helper"][1]


def test_build_service_rows_reports_default_nightly_routines() -> None:
    install_summary = load_install_summary_module()

    config = {
        "runtime": {
            "ports": {"lc_frontend_port": 3190, "lc_api_port": 3180, "playground_port": 3300},
            "prompt_workbench": {
                "enabled": True,
                "seed_nightly": {"enabled": True, "active": True, "executor": "glasshive_host"},
            },
            "memory_hardening": {"enabled": True, "schedule": "0 3 * * *"},
        },
        "llm": {"primary": {"auth_mode": "connected_account"}},
        "voice": {"mode": "local"},
        "integrations": {"glasshive": {"enabled": True}},
    }
    runtime_env = {
        "START_GLASSHIVE": "true",
        "GLASSHIVE_OPERATOR_BASE_URL": "http://127.0.0.1:8780",
        "GLASSHIVE_DEFAULT_WORKER_PROFILE": "claude-code",
        "START_PROMPT_WORKBENCH": "true",
        "VIVENTIUM_PROMPT_WORKBENCH_PORT": "8781",
        "VIVENTIUM_MEMORY_HARDENING_ENABLED": "true",
    }

    rows = install_summary.build_service_rows(config, runtime_env, probe_live=False)
    services = {name: (status, detail) for name, status, detail in rows}

    assert services["GlassHive"] == (
        "Configured",
        "http://127.0.0.1:8780 | default worker: claude-code",
    )
    assert services["Prompt Workbench"] == ("Configured", "http://localhost:8781")
    assert services["Nightly Reflection"] == (
        "Active",
        "03:00 local Workbench schedule via glasshive_host; seeded for the first resolved local admin user",
    )
    assert services["Memory Hardening"] == (
        "Scheduled",
        "0 3 * * * local; all memory-enabled users unless scoped in config; dry-run-first on",
    )
    assert services["Transcript Ingest"] == (
        "Needs setup",
        "Choose a folder with bin/viventium transcripts source set <folder>; empty means pending, not failed",
    )


def test_build_service_rows_reports_scheduler_health_and_sanitized_ledger(
    monkeypatch, tmp_path: Path
) -> None:
    install_summary = load_install_summary_module()

    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir(parents=True)
    db_path = tmp_path / "scheduler.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE scheduled_tasks (
              id TEXT PRIMARY KEY,
              active INTEGER,
              last_status TEXT,
              last_delivery_outcome TEXT,
              last_delivery_at TEXT,
              next_run_at TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO scheduled_tasks (
              id, active, last_status, last_delivery_outcome, last_delivery_at, next_run_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "synthetic-task",
                1,
                "success",
                "sent",
                "2026-05-31T10:00:00Z",
                "2026-06-01T10:00:00Z",
            ),
        )

    config = {
        "runtime": {"ports": {"lc_frontend_port": 3190, "lc_api_port": 3180, "playground_port": 3300}},
        "llm": {"primary": {"auth_mode": "connected_account"}},
        "voice": {"mode": "local"},
        "integrations": {},
    }
    runtime_env = {
        "START_SCHEDULING_MCP": "true",
        "SCHEDULING_MCP_URL": "http://localhost:7110/mcp",
        "SCHEDULING_DB_PATH": str(db_path),
    }

    monkeypatch.setattr(install_summary, "http_ok", lambda url: url == "http://localhost:7110/health")
    monkeypatch.setattr(install_summary, "local_network_host", lambda: None)

    rows = install_summary.build_service_rows(
        config,
        runtime_env,
        runtime_dir=runtime_dir,
        probe_live=True,
    )
    services = {name: (status, detail) for name, status, detail in rows}

    assert services["Scheduler"][0] == "Running"
    assert "1 active / 1 total" in services["Scheduler"][1]
    assert "last status success" in services["Scheduler"][1]
    assert "delivery sent" in services["Scheduler"][1]
    assert "synthetic-task" not in services["Scheduler"][1]


def test_build_service_rows_marks_scheduler_running_with_ledger_issue(
    monkeypatch, tmp_path: Path
) -> None:
    install_summary = load_install_summary_module()

    db_path = tmp_path / "scheduler.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE scheduled_tasks (
              id TEXT PRIMARY KEY,
              active INTEGER,
              last_status TEXT,
              last_delivery_outcome TEXT,
              last_delivery_at TEXT,
              next_run_at TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO scheduled_tasks (
              id, active, last_status, last_delivery_outcome, last_delivery_at, next_run_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "synthetic-task",
                1,
                "error",
                "failed",
                "2026-05-31T10:00:00Z",
                "2026-06-01T10:00:00Z",
            ),
        )

    config = {
        "runtime": {"ports": {"lc_frontend_port": 3190, "lc_api_port": 3180, "playground_port": 3300}},
        "llm": {"primary": {"auth_mode": "connected_account"}},
        "voice": {"mode": "local"},
        "integrations": {},
    }

    monkeypatch.setattr(install_summary, "http_ok", lambda url: url == "http://localhost:7110/health")
    monkeypatch.setattr(install_summary, "local_network_host", lambda: None)

    rows = install_summary.build_service_rows(
        config,
        {
            "START_SCHEDULING_MCP": "true",
            "SCHEDULING_MCP_URL": "http://localhost:7110/mcp",
            "SCHEDULING_DB_PATH": str(db_path),
        },
        probe_live=True,
    )
    services = {name: (status, detail) for name, status, detail in rows}

    assert services["Scheduler"][0] == "Running with issues"
    assert "last status error" in services["Scheduler"][1]
    assert "delivery failed" in services["Scheduler"][1]


def test_build_brain_setup_rows_reports_guided_and_lab_postures() -> None:
    install_summary = load_install_summary_module()

    config = {
        "runtime": {
            "personalization": {"default_conversation_recall": False},
            "memory_hardening": {"transcripts": {"source_dir": ""}},
            "network": {"remote_call_mode": "disabled"},
        },
        "llm": {
            "primary": {"provider": "openai", "auth_mode": "connected_account"},
            "secondary": {"provider": "none", "auth_mode": "disabled"},
        },
        "voice": {"mode": "disabled"},
        "integrations": {
            "web_search": {"enabled": False},
            "telegram": {"enabled": False},
            "telegram_codex": {"enabled": False},
            "google_workspace": {"enabled": False},
            "ms365": {"enabled": False},
            "code_interpreter": {"enabled": False},
            "skyvern": {"enabled": False},
            "openclaw": {"enabled": False},
        },
    }

    rows = install_summary.build_brain_setup_rows(config, {})
    states = {name: (state, action) for name, state, action in rows}

    assert states["Primary AI"][0] == "Needs setup"
    assert states["Transcript Ingest"][0] == "Needs setup"
    assert states["Conversation Recall/RAG"][0] == "Needs setup"
    assert states["WhatsApp"][0] == "Not available"
    assert states["Code Interpreter"][0] == "Disabled by choice"
    assert states["Skyvern"][0] == "Disabled by choice"
    assert states["OpenClaw"][0] == "Disabled by choice"
    assert states["Remote Access"][0] == "Disabled by choice"


def test_build_brain_setup_rows_does_not_call_connected_account_route_ready() -> None:
    install_summary = load_install_summary_module()

    config = {
        "runtime": {"personalization": {"default_conversation_recall": False}},
        "llm": {"primary": {"provider": "openai", "auth_mode": "connected_account"}},
        "voice": {"mode": "local"},
        "integrations": {},
    }
    runtime_env = {
        "VIVENTIUM_LOCAL_SUBSCRIPTION_AUTH": "true",
        "VIVENTIUM_OPENAI_AUTH_MODE": "connected_account",
    }

    rows = install_summary.build_brain_setup_rows(config, runtime_env)
    states = {name: (state, action) for name, state, action in rows}

    assert states["Primary AI"][0] == "Needs setup"
    assert "Connected Accounts" in states["Primary AI"][1]


def test_build_connected_accounts_notice_still_prompts_for_connected_account_route() -> None:
    install_summary = load_install_summary_module()

    config = {
        "runtime": {},
        "llm": {"primary": {"provider": "openai", "auth_mode": "connected_account"}},
        "voice": {"mode": "local"},
        "integrations": {},
    }
    runtime_env = {
        "VIVENTIUM_LOCAL_SUBSCRIPTION_AUTH": "true",
        "VIVENTIUM_OPENAI_AUTH_MODE": "connected_account",
    }

    notice = install_summary.build_connected_accounts_notice(config, runtime_env)

    assert notice is not None
    assert "Connect" in notice
    assert "OpenAI" in notice


def test_macos_helper_status_reports_hidden_when_status_bar_is_disabled(
    monkeypatch, tmp_path: Path
) -> None:
    install_summary = load_install_summary_module()
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir(parents=True)
    (tmp_path / "helper-config.json").write_text('{"showInStatusBar": false}\n', encoding="utf-8")

    monkeypatch.setattr(install_summary.sys, "platform", "darwin")

    assert install_summary.macos_helper_status(
        runtime_dir=runtime_dir,
        probe_live=True,
        stack_should_be_live=True,
    ) == (
        "macOS Status Bar Helper",
        "Hidden",
        "Configured to stay out of the macOS status bar",
    )


def test_macos_helper_status_reports_running_when_helper_process_exists(
    monkeypatch, tmp_path: Path
) -> None:
    install_summary = load_install_summary_module()
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir(parents=True)
    (tmp_path / "helper-config.json").write_text('{"showInStatusBar": true}\n', encoding="utf-8")

    monkeypatch.setattr(install_summary.sys, "platform", "darwin")
    monkeypatch.setattr(install_summary, "process_running_by_name", lambda _name: True)

    assert install_summary.macos_helper_status(
        runtime_dir=runtime_dir,
        probe_live=True,
        stack_should_be_live=True,
    ) == (
        "macOS Status Bar Helper",
        "Running",
        "Status bar menu is active",
    )


def test_macos_helper_status_reports_configured_when_not_live(
    monkeypatch, tmp_path: Path
) -> None:
    install_summary = load_install_summary_module()
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir(parents=True)
    (tmp_path / "helper-config.json").write_text('{"showInStatusBar": true}\n', encoding="utf-8")

    monkeypatch.setattr(install_summary.sys, "platform", "darwin")
    monkeypatch.setattr(install_summary, "process_running_by_name", lambda _name: False)

    assert install_summary.macos_helper_status(
        runtime_dir=runtime_dir,
        probe_live=False,
        stack_should_be_live=True,
    ) == (
        "macOS Status Bar Helper",
        "Configured",
        "Launch Viventium when you want the status bar menu active",
    )

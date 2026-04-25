from __future__ import annotations

import copy
import json
import os
import platform
import subprocess
import sys
import importlib.util
from pathlib import Path

import pytest
import yaml


def build_valid_telegram_token(bot_id: str, suffix: str) -> str:
    token_body = "telegram" + "_test_" + "fixture_" + suffix
    return f"{bot_id}:{token_body}"


VALID_TELEGRAM_TOKEN = build_valid_telegram_token("123456789", "ABCDEFGH")
VALID_TELEGRAM_CODEX_TOKEN = build_valid_telegram_token("987654321", "HGFEDCBA")
VALID_TELEGRAM_EXISTING_TOKEN = build_valid_telegram_token("246813579", "QRSTUVWX")

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_OF_TRUTH_AGENTS_BUNDLE = (
    REPO_ROOT
    / "viventium_v0_4"
    / "LibreChat"
    / "viventium"
    / "source_of_truth"
    / "local.viventium-agents.yaml"
)
SOURCE_OF_TRUTH_LIBRECHAT_YAML = (
    REPO_ROOT
    / "viventium_v0_4"
    / "LibreChat"
    / "viventium"
    / "source_of_truth"
    / "local.librechat.yaml"
)
CONFIG_COMPILER_SPEC = importlib.util.spec_from_file_location(
    "viventium_config_compiler",
    REPO_ROOT / "scripts/viventium/config_compiler.py",
)
assert CONFIG_COMPILER_SPEC and CONFIG_COMPILER_SPEC.loader
config_compiler = importlib.util.module_from_spec(CONFIG_COMPILER_SPEC)
CONFIG_COMPILER_SPEC.loader.exec_module(config_compiler)


def write_config(path: Path, payload: dict) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def load_source_of_truth_agents_bundle() -> dict:
    return yaml.safe_load(SOURCE_OF_TRUTH_AGENTS_BUNDLE.read_text(encoding="utf-8"))


def load_source_of_truth_librechat_yaml() -> dict:
    return yaml.safe_load(SOURCE_OF_TRUTH_LIBRECHAT_YAML.read_text(encoding="utf-8"))


def source_of_truth_built_in_agent_map() -> dict[str, str]:
    bundle = load_source_of_truth_agents_bundle()
    agents = [bundle.get("mainAgent", {})] + list(bundle.get("backgroundAgents", []))
    return {
        str(agent.get("name") or "").strip(): str(agent.get("id") or "").strip()
        for agent in agents
        if isinstance(agent, dict)
        and agent.get("missing") is not True
        and str(agent.get("name") or "").strip()
        and str(agent.get("id") or "").strip()
    }


def test_memory_hardening_rejects_non_launch_ready_openai_model() -> None:
    with pytest.raises(SystemExit, match="openai_model must stay in launch-ready"):
        config_compiler.resolve_memory_hardening_settings(
            {
                "runtime": {
                    "memory_hardening": {
                        "openai_model": "gpt-5.5",
                    }
                }
            }
        )


def test_config_compiler_minimal(tmp_path: Path) -> None:
    config = {
        "version": 1,
        "install": {"mode": "docker"},
        "runtime": {
            "log_level": "info",
            "profile": "isolated",
            "call_session_secret": {"secret_value": "call-session-test"},
            "network": {"remote_call_mode": "auto"},
        },
        "llm": {
            "activation": {
                "provider": "groq",
                "auth_mode": "api_key",
                "secret_value": "groq-test",
            },
            "primary": {
                "provider": "openai",
                "auth_mode": "api_key",
                "secret_value": "openai-test",
            },
            "secondary": {"provider": "none", "auth_mode": "disabled"},
            "extra_provider_keys": {},
        },
        "voice": {
            "mode": "disabled",
            "stt_provider": "whisper_local",
            "tts_provider": "browser",
            "wing_mode": {
                "default_enabled": True,
                "prompt": "Custom wing prompt from config.",
            },
        },
        "integrations": {
            "telegram": {"enabled": False},
            "google_workspace": {"enabled": False},
            "ms365": {"enabled": False},
            "skyvern": {"enabled": False},
            "openclaw": {"enabled": False},
        },
    }
    config_path = tmp_path / "config.yaml"
    output_dir = tmp_path / "out"
    write_config(config_path, config)

    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/viventium/config_compiler.py"),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        cwd=REPO_ROOT,
    )

    runtime_env = (output_dir / "runtime.env").read_text(encoding="utf-8")
    librechat_yaml = yaml.safe_load((output_dir / "librechat.yaml").read_text(encoding="utf-8"))
    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))

    assert "GROQ_API_KEY=groq-test" in runtime_env
    assert "OPENAI_API_KEY=openai-test" in runtime_env
    assert "VIVENTIUM_VOICE_ENABLED=false" in runtime_env
    assert "VIVENTIUM_VOICE_FAST_LLM_PROVIDER=" not in runtime_env
    assert "VIVENTIUM_CALL_SESSION_SECRET=call-session-test" in runtime_env
    assert "VIVENTIUM_TELEGRAM_SECRET=call-session-test" in runtime_env
    assert "VIVENTIUM_CORTEX_FOLLOWUP_GRACE_S=30" in runtime_env
    assert "VIVENTIUM_VOICE_FOLLOWUP_GRACE_S=30" in runtime_env
    assert "VIVENTIUM_TELEGRAM_FOLLOWUP_GRACE_S=30" in runtime_env
    assert "VIVENTIUM_LIBRECHAT_ORIGIN=http://localhost:3180" in runtime_env
    assert "VIVENTIUM_TELEGRAM_AGENT_ID=agent_viventium_main_95aeb3" in runtime_env
    assert "VIVENTIUM_REMOTE_CALL_MODE=disabled" in runtime_env
    assert "VIVENTIUM_MAIN_AGENT_ID=agent_viventium_main_95aeb3" in runtime_env
    assert "VIVENTIUM_LOCAL_SUBSCRIPTION_AUTH=true" in runtime_env
    assert "VIVENTIUM_DEFAULT_CONVERSATION_RECALL=false" in runtime_env
    assert "VIVENTIUM_MEMORY_HARDENING_ENABLED=false" in runtime_env
    assert "VIVENTIUM_MEMORY_HARDENING_SCHEDULE='0 5 * * *'" in runtime_env
    assert "VIVENTIUM_MEMORY_HARDENING_LOOKBACK_DAYS=7" in runtime_env
    assert "VIVENTIUM_MEMORY_HARDENING_MIN_USER_IDLE_MINUTES=60" in runtime_env
    assert "VIVENTIUM_MEMORY_HARDENING_MAX_CHANGES_PER_USER=3" in runtime_env
    assert "VIVENTIUM_MEMORY_HARDENING_MAX_INPUT_CHARS=500000" in runtime_env
    assert "VIVENTIUM_MEMORY_HARDENING_REQUIRE_FULL_LOOKBACK=true" in runtime_env
    assert "VIVENTIUM_MEMORY_HARDENING_DRY_RUN_FIRST=true" in runtime_env
    assert "VIVENTIUM_MEMORY_HARDENING_PROVIDER_PROFILE=launch_ready_only" in runtime_env
    assert "VIVENTIUM_MEMORY_HARDENING_ANTHROPIC_MODEL=claude-opus-4-7" in runtime_env
    assert "VIVENTIUM_MEMORY_HARDENING_OPENAI_MODEL=gpt-5.4" in runtime_env
    assert "VIVENTIUM_BUILTIN_AGENT_PUBLIC_ROLE=owner" in runtime_env
    assert "START_RAG_API=false" in runtime_env
    assert "EMBEDDINGS_PROVIDER=ollama" in runtime_env
    assert "EMBEDDINGS_MODEL=qwen3-embedding:0.6b" in runtime_env
    assert "OLLAMA_BASE_URL=http://host.docker.internal:11434" in runtime_env
    assert "VIVENTIUM_RAG_EMBEDDINGS_PROVIDER=ollama" in runtime_env
    assert "VIVENTIUM_RAG_EMBEDDINGS_MODEL=qwen3-embedding:0.6b" in runtime_env
    assert "VIVENTIUM_RAG_EMBEDDINGS_PROFILE=medium" in runtime_env
    assert "START_CODE_INTERPRETER=false" in runtime_env
    assert "START_GLASSHIVE=false" in runtime_env
    assert "GLASSHIVE_DEFAULT_LAUNCH_SURFACE=" not in runtime_env
    assert "GLASSHIVE_SHOW_LIVE_TERMINAL_IN_DESKTOP=" not in runtime_env
    assert "START_SEARXNG=false" in runtime_env
    assert "START_FIRECRAWL=false" in runtime_env
    assert "VIVENTIUM_WEB_SEARCH_ENABLED=false" in runtime_env
    assert "WPR_IDLE_DESKTOP_PRIME_BROWSER=" not in runtime_env
    assert "LIBRECHAT_CODE_BASEURL=" not in runtime_env
    assert "LIBRECHAT_CODE_API_KEY=" not in runtime_env
    assert "CODE_API_KEY=" not in runtime_env
    assert "SEARXNG_INSTANCE_URL=" not in runtime_env
    assert "FIRECRAWL_API_KEY=" not in runtime_env
    assert "FIRECRAWL_API_URL=" not in runtime_env
    assert "VIVENTIUM_WING_MODE_DEFAULT_ENABLED=true" in runtime_env
    assert "VIVENTIUM_SHADOW_MODE_DEFAULT_ENABLED=true" in runtime_env
    assert "VIVENTIUM_WING_MODE_PROMPT='Custom wing prompt from config.'" in runtime_env
    assert "VIVENTIUM_SHADOW_MODE_PROMPT='Custom wing prompt from config.'" in runtime_env
    assert "ANTHROPIC_API_KEY=user_provided" in runtime_env
    assert "GOOGLE_API_KEY=user_provided" in runtime_env
    assert "GOOGLE_KEY=user_provided" in runtime_env
    assert "OPENROUTER_API_KEY=user_provided" in runtime_env
    assert "PERPLEXITY_API_KEY=user_provided" in runtime_env
    assert "XAI_API_KEY=user_provided" in runtime_env
    assert 'SCHEDULING_MCP_URL=http://localhost:7110/mcp' in runtime_env
    assert librechat_yaml["interface"]["defaultAgent"] == "agent_viventium_main_95aeb3"
    assert librechat_yaml["endpoints"]["agents"]["defaultId"] == "agent_viventium_main_95aeb3"
    assert librechat_yaml["endpoints"]["agents"]["capabilities"]
    assert "execute_code" not in librechat_yaml["endpoints"]["agents"]["capabilities"]
    assert librechat_yaml["endpoints"]["agents"]["recursionLimit"] == 2000
    assert librechat_yaml["interface"]["runCode"] is False
    assert librechat_yaml["memory"]["disabled"] is False
    assert librechat_yaml["memory"]["personalize"] is True
    assert librechat_yaml["memory"]["agent"]["provider"] == "openai"
    assert librechat_yaml["memory"]["agent"]["model"] == "gpt-5.4"
    assert (
        librechat_yaml["viventium"]["conversation_recall"]["prompt"]
        == load_source_of_truth_librechat_yaml()["viventium"]["conversation_recall"]["prompt"]
    )
    assert librechat_yaml["balance"]["enabled"] is False
    assert librechat_yaml["speech"]["tts"] == {}
    assert librechat_yaml["speech"]["stt"] == {}
    assert librechat_yaml["modelSpecs"]["list"][0]["name"] == "viventium"
    assert librechat_yaml["modelSpecs"]["list"][0]["default"] is True
    assert librechat_yaml["modelSpecs"]["list"][0]["preset"]["agent_id"] == "agent_viventium_main_95aeb3"
    assert librechat_yaml["modelSpecs"]["list"][0]["iconURL"] == "/assets/logo.svg"
    built_in_agents = {
        item["label"]: item["preset"]["agent_id"]
        for item in librechat_yaml["modelSpecs"]["list"]
        if item.get("preset", {}).get("endpoint") == "agents"
    }
    assert built_in_agents == source_of_truth_built_in_agent_map()
    assert "azureOpenAI" not in librechat_yaml["endpoints"]
    assert librechat_yaml["endpoints"]["anthropic"]["titleEndpoint"] == "anthropic"
    assert librechat_yaml["endpoints"]["anthropic"]["titleModel"] == "claude-sonnet-4-6"
    assert all(
        item.get("preset", {}).get("endpoint") != "azureOpenAI"
        for item in librechat_yaml["modelSpecs"]["list"]
    )
    assert any(item["name"] == "viventium" for item in librechat_yaml["modelSpecs"]["list"])
    assert set(librechat_yaml["modelSpecs"]["addedEndpoints"]) >= {
        "agents",
        "anthropic",
        "google",
        "groq",
        "xai",
        "perplexity",
        "openrouter",
        "openAI",
        "custom",
    }
    custom_names = [endpoint["name"] for endpoint in librechat_yaml["endpoints"]["custom"]]
    assert custom_names == ["perplexity", "xai", "openrouter", "groq"]
    assert librechat_yaml["version"] == "1.3.6"
    assert "webSearch" not in librechat_yaml
    assert librechat_yaml["mcpServers"]["scheduling-cortex"]["url"] == "${SCHEDULING_MCP_URL}"
    assert "glasshive-workers-projects" not in librechat_yaml["mcpServers"]
    assert librechat_yaml["mcpServers"]["sequential-thinking"]["command"] == "npx"
    assert summary["primary_provider"] == "openai"


def test_glasshive_enabled_requires_config_and_runtime_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    missing_dir = tmp_path / "missing-glasshive"
    monkeypatch.setattr(config_compiler, "GLASSHIVE_RUNTIME_DIR", missing_dir)

    assert config_compiler.glasshive_enabled({"integrations": {}}) is False
    assert config_compiler.glasshive_enabled({"integrations": {"glasshive": {"enabled": True}}}) is False

    runtime_dir = tmp_path / "runtime_phase1"
    runtime_dir.mkdir(parents=True)
    monkeypatch.setattr(config_compiler, "GLASSHIVE_RUNTIME_DIR", runtime_dir)

    assert config_compiler.glasshive_enabled({"integrations": {"glasshive": {"enabled": False}}}) is False
    assert config_compiler.glasshive_enabled({"integrations": {"glasshive": {"enabled": True}}}) is True


def test_render_runtime_env_emits_glasshive_launch_env_only_when_enabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runtime_dir = tmp_path / "runtime_phase1"
    runtime_dir.mkdir(parents=True)
    monkeypatch.setattr(config_compiler, "GLASSHIVE_RUNTIME_DIR", runtime_dir)

    base_config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "log_level": "info",
            "profile": "isolated",
            "call_session_secret": {"secret_value": "call-session-test"},
            "personalization": {"default_conversation_recall": False},
        },
        "llm": {
            "activation": {"provider": "groq", "auth_mode": "api_key", "secret_value": "groq-test"},
            "primary": {"provider": "openai", "auth_mode": "api_key", "secret_value": "openai-test"},
            "secondary": {"provider": "none", "auth_mode": "disabled"},
            "extra_provider_keys": {},
        },
        "voice": {"mode": "disabled"},
        "integrations": {
            "telegram": {"enabled": False},
            "google_workspace": {"enabled": False},
            "ms365": {"enabled": False},
            "skyvern": {"enabled": False},
            "openclaw": {"enabled": False},
        },
        "agents": {},
    }

    disabled_env = config_compiler.render_runtime_env(base_config, config_compiler.build_agent_assignments(base_config))
    assert "GLASSHIVE_DEFAULT_LAUNCH_SURFACE" not in disabled_env
    assert "GLASSHIVE_SHOW_LIVE_TERMINAL_IN_DESKTOP" not in disabled_env
    assert "WPR_IDLE_DESKTOP_PRIME_BROWSER" not in disabled_env

    enabled_config = copy.deepcopy(base_config)
    enabled_config["integrations"]["glasshive"] = {"enabled": True}
    enabled_env = config_compiler.render_runtime_env(enabled_config, config_compiler.build_agent_assignments(enabled_config))
    assert enabled_env["GLASSHIVE_DEFAULT_LAUNCH_SURFACE"] == "desktop"
    assert enabled_env["GLASSHIVE_SHOW_LIVE_TERMINAL_IN_DESKTOP"] == "true"
    assert enabled_env["WPR_IDLE_DESKTOP_PRIME_BROWSER"] == "true"


def test_config_compiler_compile_phase_ignores_stale_generated_source_override(tmp_path: Path) -> None:
    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "log_level": "info",
            "profile": "isolated",
            "call_session_secret": {"secret_value": "call-session-test"},
            "personalization": {"default_conversation_recall": True},
        },
        "llm": {
            "activation": {
                "provider": "groq",
                "auth_mode": "api_key",
                "secret_value": "groq-test",
            },
            "primary": {
                "provider": "openai",
                "auth_mode": "api_key",
                "secret_value": "openai-test",
            },
            "secondary": {"provider": "none", "auth_mode": "disabled"},
            "extra_provider_keys": {},
        },
        "voice": {"mode": "disabled", "stt_provider": "whisper_local", "tts_provider": "browser"},
        "integrations": {
            "telegram": {"enabled": False},
            "google_workspace": {"enabled": False},
            "ms365": {"enabled": False},
            "skyvern": {"enabled": False},
            "openclaw": {"enabled": False},
        },
    }
    config_path = tmp_path / "config.yaml"
    output_dir = tmp_path / "out"
    stale_generated = tmp_path / "stale-generated-librechat.yaml"
    write_config(config_path, config)
    stale_generated.write_text(
        yaml.safe_dump(
            {
                "version": "1.3.6",
                "viventium": {
                    "configVersion": 1,
                    "no_response": {"prompt": "NO RESPONSE TAG"},
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["VIVENTIUM_LIBRECHAT_SOURCE_PHASE"] = "compile"
    env["VIVENTIUM_LIBRECHAT_SOURCE_OF_TRUTH"] = str(stale_generated)
    env.pop("VIVENTIUM_LIBRECHAT_PRIVATE_SOURCE_OF_TRUTH", None)

    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/viventium/config_compiler.py"),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )

    librechat_yaml = yaml.safe_load((output_dir / "librechat.yaml").read_text(encoding="utf-8"))
    assert librechat_yaml["viventium"]["conversation_recall"]["prompt"] == (
        load_source_of_truth_librechat_yaml()["viventium"]["conversation_recall"]["prompt"]
    )


def test_config_compiler_ignores_legacy_fast_voice_llm_provider(tmp_path: Path) -> None:
    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "log_level": "info",
            "profile": "isolated",
            "call_session_secret": {"secret_value": "call-session-test"},
        },
        "llm": {
            "activation": {
                "provider": "groq",
                "auth_mode": "api_key",
                "secret_value": "groq-test",
            },
            "primary": {
                "provider": "openai",
                "auth_mode": "api_key",
                "secret_value": "openai-test",
            },
            "secondary": {"provider": "none", "auth_mode": "disabled"},
            "extra_provider_keys": {
                "x_ai": "xai-test",
            },
        },
        "voice": {
            "mode": "local",
            "stt_provider": "whisper_local",
            "tts_provider": "browser",
            "fast_llm_provider": "x_ai",
        },
        "integrations": {
            "telegram": {"enabled": False},
            "google_workspace": {"enabled": False},
            "ms365": {"enabled": False},
            "skyvern": {"enabled": False},
            "openclaw": {"enabled": False},
        },
    }
    config_path = tmp_path / "config.yaml"
    output_dir = tmp_path / "out"
    write_config(config_path, config)

    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/viventium/config_compiler.py"),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        cwd=REPO_ROOT,
    )

    runtime_env = (output_dir / "runtime.env").read_text(encoding="utf-8")

    assert "VIVENTIUM_TTS_PROVIDER=openai" in runtime_env
    assert "VIVENTIUM_VOICE_FAST_LLM_PROVIDER=" not in runtime_env


def test_render_librechat_yaml_preserves_defaults_and_overlays_compiled_memory_assignment() -> None:
    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "profile": "isolated",
            "call_session_secret": {"secret_value": "call-session-test"},
        },
        "llm": {
            "activation": {
                "provider": "groq",
                "auth_mode": "api_key",
                "secret_value": "groq-test",
            },
            "primary": {
                "provider": "openai",
                "auth_mode": "api_key",
                "secret_value": "openai-test",
            },
            "secondary": {"provider": "none", "auth_mode": "disabled"},
            "extra_provider_keys": {},
        },
        "voice": {"mode": "disabled"},
        "integrations": {
            "telegram": {"enabled": False},
            "google_workspace": {"enabled": False},
            "ms365": {"enabled": False},
            "skyvern": {"enabled": False},
            "openclaw": {"enabled": False},
        },
    }
    assignments = config_compiler.build_agent_assignments(config)
    env = config_compiler.render_runtime_env(config, assignments)
    yaml_text = config_compiler.render_librechat_yaml(config, assignments, env)
    librechat_yaml = yaml.safe_load(yaml_text)

    assert librechat_yaml["memory"]["disabled"] is False
    assert librechat_yaml["memory"]["agent"]["provider"] == "openai"
    assert librechat_yaml["memory"]["agent"]["model"] == "gpt-5.4"
    assert librechat_yaml["endpoints"]["anthropic"]["titleEndpoint"] == "anthropic"
    assert librechat_yaml["endpoints"]["anthropic"]["titleModel"] == "claude-sonnet-4-6"
    assert librechat_yaml["viventium"]["background_cortices"]["activation_format"]["brew_begin_tag"]
    assert librechat_yaml["balance"]["enabled"] is False
    assert librechat_yaml["balance"]["startBalance"] == 200000
    assert "webSearch" not in librechat_yaml


def test_build_agent_assignments_openai_only_uses_current_gpt5_profile() -> None:
    config = {
        "llm": {
            "primary": {
                "provider": "openai",
                "auth_mode": "api_key",
                "secret_value": "openai-test",
            },
            "secondary": {"provider": "none", "auth_mode": "disabled"},
            "extra_provider_keys": {},
        }
    }

    assignments = config_compiler.build_agent_assignments(config)

    assert assignments["conscious"] == ("openai", "gpt-5.4")
    assert assignments["background_analysis"] == ("openai", "gpt-5.4")
    assert assignments["red_team"] == ("openai", "gpt-5.4")
    assert assignments["productivity"] == ("openai", "gpt-5.4")
    assert assignments["support"] == ("openai", "gpt-5.4")
    assert assignments["memory"] == ("openai", "gpt-5.4")


def test_build_agent_assignments_anthropic_only_uses_current_claude47_profile() -> None:
    config = {
        "llm": {
            "primary": {
                "provider": "anthropic",
                "auth_mode": "api_key",
                "secret_value": "anthropic-test",
            },
            "secondary": {"provider": "none", "auth_mode": "disabled"},
            "extra_provider_keys": {},
        }
    }

    assignments = config_compiler.build_agent_assignments(config)

    assert assignments["conscious"] == ("anthropic", "claude-opus-4-7")
    assert assignments["background_analysis"] == ("anthropic", "claude-sonnet-4-6")
    assert assignments["red_team"] == ("anthropic", "claude-opus-4-7")
    assert assignments["deep_research"] == ("anthropic", "claude-opus-4-7")
    assert assignments["productivity"] == ("anthropic", "claude-sonnet-4-6")
    assert assignments["emotional_resonance"] == ("anthropic", "claude-sonnet-4-6")
    assert assignments["strategic_planning"] == ("anthropic", "claude-opus-4-7")
    assert assignments["memory"] == ("anthropic", "claude-sonnet-4-6")


def test_build_agent_assignments_requires_openai_or_anthropic_foundation() -> None:
    config = {
        "llm": {
            "primary": {
                "provider": "x_ai",
                "auth_mode": "api_key",
                "secret_value": "xai-test",
            },
            "secondary": {"provider": "none", "auth_mode": "disabled"},
            "extra_provider_keys": {},
        }
    }

    with pytest.raises(SystemExit, match="At least one of OpenAI or Anthropic"):
        config_compiler.build_agent_assignments(config)


def test_config_compiler_full_run_requires_openai_or_anthropic_foundation(tmp_path: Path) -> None:
    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "log_level": "info",
            "profile": "isolated",
            "call_session_secret": {"secret_value": "call-session-test"},
        },
        "llm": {
            "activation": {
                "provider": "groq",
                "auth_mode": "api_key",
                "secret_value": "groq-test",
            },
            "primary": {
                "provider": "x_ai",
                "auth_mode": "api_key",
                "secret_value": "xai-test",
            },
            "secondary": {"provider": "none", "auth_mode": "disabled"},
            "extra_provider_keys": {},
        },
        "voice": {"mode": "disabled"},
        "integrations": {
            "telegram": {"enabled": False},
            "google_workspace": {"enabled": False},
            "ms365": {"enabled": False},
            "skyvern": {"enabled": False},
            "openclaw": {"enabled": False},
        },
    }
    config_path = tmp_path / "config.yaml"
    output_dir = tmp_path / "out"
    write_config(config_path, config)

    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/viventium/config_compiler.py"),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode != 0
    assert "At least one of OpenAI or Anthropic must be configured" in completed.stderr


def test_config_compiler_full_run_requires_groq_credential(tmp_path: Path) -> None:
    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "log_level": "info",
            "profile": "isolated",
            "call_session_secret": {"secret_value": "call-session-test"},
        },
        "llm": {
            "activation": {
                "provider": "groq",
                "auth_mode": "api_key",
                "secret_value": "",
            },
            "primary": {
                "provider": "openai",
                "auth_mode": "api_key",
                "secret_value": "openai-test",
            },
            "secondary": {"provider": "none", "auth_mode": "disabled"},
            "extra_provider_keys": {},
        },
        "voice": {"mode": "disabled"},
        "integrations": {
            "telegram": {"enabled": False},
            "google_workspace": {"enabled": False},
            "ms365": {"enabled": False},
            "skyvern": {"enabled": False},
            "openclaw": {"enabled": False},
        },
    }
    config_path = tmp_path / "config.yaml"
    output_dir = tmp_path / "out"
    write_config(config_path, config)

    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/viventium/config_compiler.py"),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode != 0
    assert "Missing required Groq credential." in completed.stderr


def test_render_runtime_env_exports_explicit_background_role_assignments() -> None:
    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "profile": "isolated",
            "call_session_secret": {"secret_value": "call-session-test"},
        },
        "llm": {
            "activation": {
                "provider": "groq",
                "auth_mode": "api_key",
                "secret_value": "groq-test",
            },
            "primary": {
                "provider": "openai",
                "auth_mode": "api_key",
                "secret_value": "openai-test",
            },
            "secondary": {"provider": "anthropic", "auth_mode": "api_key", "secret_value": "anthropic-test"},
            "extra_provider_keys": {},
        },
        "voice": {"mode": "disabled"},
        "integrations": {
            "telegram": {"enabled": False},
            "google_workspace": {"enabled": False},
            "ms365": {"enabled": False},
            "skyvern": {"enabled": False},
            "openclaw": {"enabled": False},
        },
    }

    assignments = config_compiler.build_agent_assignments(config)
    env = config_compiler.render_runtime_env(config, assignments)

    assert env["VIVENTIUM_CORTEX_BACKGROUND_ANALYSIS_LLM_PROVIDER"] == "anthropic"
    assert env["VIVENTIUM_CORTEX_BACKGROUND_ANALYSIS_LLM_MODEL"] == "claude-sonnet-4-6"
    assert env["VIVENTIUM_CORTEX_RED_TEAM_LLM_PROVIDER"] == "openai"
    assert env["VIVENTIUM_CORTEX_RED_TEAM_LLM_MODEL"] == "gpt-5.4"
    assert env["VIVENTIUM_CORTEX_PRODUCTIVITY_LLM_PROVIDER"] == "openai"
    assert env["VIVENTIUM_CORTEX_PRODUCTIVITY_LLM_MODEL"] == "gpt-5.4"
    assert env["VIVENTIUM_CORTEX_SUPPORT_LLM_PROVIDER"] == "anthropic"
    assert env["VIVENTIUM_CORTEX_SUPPORT_LLM_MODEL"] == "claude-sonnet-4-6"
    assert env["VIVENTIUM_BACKGROUND_ACTIVATION_PROVIDER"] == "groq"
    assert env["VIVENTIUM_BACKGROUND_ACTIVATION_MODEL"] == "meta-llama/llama-4-scout-17b-16e-instruct"


def test_build_agent_assignments_use_current_generation_models() -> None:
    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "profile": "isolated",
            "call_session_secret": {"secret_value": "call-session-test"},
        },
        "llm": {
            "activation": {
                "provider": "groq",
                "auth_mode": "api_key",
                "secret_value": "groq-test",
            },
            "primary": {
                "provider": "openai",
                "auth_mode": "api_key",
                "secret_value": "openai-test",
            },
            "secondary": {
                "provider": "anthropic",
                "auth_mode": "api_key",
                "secret_value": "anthropic-test",
            },
            "extra_provider_keys": {},
        },
        "voice": {"mode": "disabled"},
        "integrations": {
            "telegram": {"enabled": False},
            "google_workspace": {"enabled": False},
            "ms365": {"enabled": False},
            "skyvern": {"enabled": False},
            "openclaw": {"enabled": False},
        },
    }

    assignments = config_compiler.build_agent_assignments(config)

    assert assignments["conscious"] == ("anthropic", "claude-opus-4-7")
    assert assignments["background_analysis"] == ("anthropic", "claude-sonnet-4-6")
    assert assignments["confirmation_bias"] == ("anthropic", "claude-sonnet-4-6")
    assert assignments["red_team"] == ("openai", "gpt-5.4")
    assert assignments["deep_research"] == ("openai", "gpt-5.4")
    assert assignments["productivity"] == ("openai", "gpt-5.4")
    assert assignments["parietal"] == ("openai", "gpt-5.4")
    assert assignments["pattern_recognition"] == ("anthropic", "claude-sonnet-4-6")
    assert assignments["emotional_resonance"] == ("anthropic", "claude-sonnet-4-6")
    assert assignments["strategic_planning"] == ("anthropic", "claude-opus-4-7")
    assert assignments["support"] == ("anthropic", "claude-sonnet-4-6")
    assert assignments["memory"] == ("anthropic", "claude-sonnet-4-6")

def test_build_agent_assignments_memory_prefers_anthropic_when_available() -> None:
    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "profile": "isolated",
            "call_session_secret": {"secret_value": "call-session-test"},
        },
        "llm": {
            "activation": {
                "provider": "groq",
                "auth_mode": "api_key",
                "secret_value": "groq-test",
            },
            "primary": {
                "provider": "anthropic",
                "auth_mode": "api_key",
                "secret_value": "anthropic-test",
            },
            "secondary": {
                "provider": "openai",
                "auth_mode": "api_key",
                "secret_value": "openai-test",
            },
            "extra_provider_keys": {},
        },
        "voice": {"mode": "disabled"},
        "integrations": {
            "telegram": {"enabled": False},
            "google_workspace": {"enabled": False},
            "ms365": {"enabled": False},
            "skyvern": {"enabled": False},
            "openclaw": {"enabled": False},
        },
    }

    assignments = config_compiler.build_agent_assignments(config)

    assert assignments["memory"] == ("anthropic", "claude-sonnet-4-6")


def test_build_agent_assignments_limits_anthropic_opus_background_usage() -> None:
    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "profile": "isolated",
            "call_session_secret": {"secret_value": "call-session-test"},
        },
        "llm": {
            "activation": {
                "provider": "groq",
                "auth_mode": "api_key",
                "secret_value": "groq-test",
            },
            "primary": {
                "provider": "anthropic",
                "auth_mode": "connected_account",
            },
            "secondary": {"provider": "none", "auth_mode": "disabled"},
            "extra_provider_keys": {},
        },
        "voice": {"mode": "disabled"},
        "integrations": {
            "telegram": {"enabled": False},
            "google_workspace": {"enabled": False},
            "ms365": {"enabled": False},
            "skyvern": {"enabled": False},
            "openclaw": {"enabled": False},
        },
    }

    assignments = config_compiler.build_agent_assignments(config)

    opus_roles = {
        role
        for role, assignment in assignments.items()
        if assignment == ("anthropic", "claude-opus-4-7") and role != "conscious"
    }

    assert opus_roles == {"red_team", "deep_research", "strategic_planning"}


def test_build_agent_assignments_do_not_promote_xai_into_main_agent_when_foundation_exists() -> None:
    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "profile": "isolated",
            "call_session_secret": {"secret_value": "call-session-test"},
        },
        "llm": {
            "activation": {
                "provider": "groq",
                "auth_mode": "api_key",
                "secret_value": "groq-test",
            },
            "primary": {
                "provider": "x_ai",
                "auth_mode": "api_key",
                "secret_value": "xai-test",
            },
            "secondary": {
                "provider": "openai",
                "auth_mode": "api_key",
                "secret_value": "openai-test",
            },
            "extra_provider_keys": {},
        },
        "voice": {"mode": "disabled"},
        "integrations": {
            "telegram": {"enabled": False},
            "google_workspace": {"enabled": False},
            "ms365": {"enabled": False},
            "skyvern": {"enabled": False},
            "openclaw": {"enabled": False},
        },
    }

    assignments = config_compiler.build_agent_assignments(config)

    assert assignments["conscious"] == ("openai", "gpt-5.4")
    assert assignments["memory"] == ("openai", "gpt-5.4")


def test_render_runtime_env_uses_llama_4_scout_for_background_activation_defaults() -> None:
    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "profile": "isolated",
            "call_session_secret": {"secret_value": "call-session-test"},
        },
        "llm": {
            "activation": {
                "provider": "groq",
                "auth_mode": "api_key",
                "secret_value": "groq-test",
            },
            "primary": {
                "provider": "openai",
                "auth_mode": "api_key",
                "secret_value": "openai-test",
            },
            "secondary": {"provider": "none", "auth_mode": "disabled"},
            "extra_provider_keys": {},
        },
        "voice": {"mode": "disabled"},
        "integrations": {
            "telegram": {"enabled": False},
            "google_workspace": {"enabled": False},
            "ms365": {"enabled": False},
            "skyvern": {"enabled": False},
            "openclaw": {"enabled": False},
        },
    }

    assignments = config_compiler.build_agent_assignments(config)
    env = config_compiler.render_runtime_env(config, assignments)

    assert env["VIVENTIUM_CORTEX_CONFIRMATION_BIAS_ACTIVATION_LLM_MODEL"] == (
        "meta-llama/llama-4-scout-17b-16e-instruct"
    )
    assert env["VIVENTIUM_CORTEX_DEEP_RESEARCH_ACTIVATION_LLM_MODEL"] == (
        "meta-llama/llama-4-scout-17b-16e-instruct"
    )
    assert env["VIVENTIUM_CORTEX_PARIETAL_CORTEX_ACTIVATION_LLM_MODEL"] == (
        "meta-llama/llama-4-scout-17b-16e-instruct"
    )
    assert env["OTUC_ACTIVATION_LLM"] == "meta-llama/llama-4-scout-17b-16e-instruct"


def test_config_compiler_enables_code_interpreter_when_requested(tmp_path: Path) -> None:
    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "profile": "isolated",
            "call_session_secret": {"secret_value": "call-session-test"},
        },
        "llm": {
            "activation": {
                "provider": "groq",
                "auth_mode": "api_key",
                "secret_value": "groq-test",
            },
            "primary": {
                "provider": "openai",
                "auth_mode": "api_key",
                "secret_value": "openai-test",
            },
            "secondary": {"provider": "none", "auth_mode": "disabled"},
            "extra_provider_keys": {},
        },
        "voice": {"mode": "disabled"},
        "integrations": {
            "code_interpreter": {"enabled": True},
            "telegram": {"enabled": False},
            "google_workspace": {"enabled": False},
            "ms365": {"enabled": False},
            "skyvern": {"enabled": False},
            "openclaw": {"enabled": False},
        },
    }
    config_path = tmp_path / "config.yaml"
    output_dir = tmp_path / "out"
    write_config(config_path, config)

    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/viventium/config_compiler.py"),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        cwd=REPO_ROOT,
    )

    runtime_env = (output_dir / "runtime.env").read_text(encoding="utf-8")
    librechat_yaml = yaml.safe_load((output_dir / "librechat.yaml").read_text(encoding="utf-8"))

    assert "START_CODE_INTERPRETER=true" in runtime_env
    assert "LIBRECHAT_CODE_BASEURL=http://localhost:8101" in runtime_env
    assert "LIBRECHAT_CODE_API_KEY=viventium-local-code-access" in runtime_env
    assert "CODE_API_KEY=viventium-local-code-access" in runtime_env
    assert librechat_yaml["interface"]["runCode"] is True
    assert "execute_code" in librechat_yaml["endpoints"]["agents"]["capabilities"]
    assert "webSearch" not in librechat_yaml
    assert "azureOpenAI" not in librechat_yaml["endpoints"]
    assert "azureOpenAI" not in librechat_yaml["speech"]["tts"]
    assert "azureOpenAI" not in librechat_yaml["speech"]["stt"]


def test_build_model_specs_includes_the_shipped_built_in_agent_roster() -> None:
    model_specs = config_compiler.build_model_specs("agent_viventium_main_95aeb3")
    built_in_agents = {
        entry["label"]: entry["preset"]["agent_id"]
        for entry in model_specs.get("list", [])
        if entry.get("preset", {}).get("endpoint") == "agents"
    }
    assert built_in_agents == source_of_truth_built_in_agent_map()
    assert set(model_specs["addedEndpoints"]) >= {
        "agents",
        "anthropic",
        "google",
        "groq",
        "xai",
        "perplexity",
        "openrouter",
        "openAI",
    }


def test_merge_model_specs_injects_viventium_fallback_when_missing() -> None:
    merged = config_compiler.merge_model_specs(
        existing={"list": [{"name": "gpt-4o", "preset": {"endpoint": "openAI", "model": "gpt-4o"}}]},
        generated={"prioritize": False, "addedEndpoints": ["agents"]},
        default_main_agent_id="agent_viventium_main_95aeb3",
    )
    entries = merged.get("list", [])
    assert entries[0]["name"] == "viventium"
    assert entries[0]["default"] is True
    assert entries[0]["iconURL"] == "/assets/logo.svg"
    assert entries[0]["preset"]["endpoint"] == "agents"
    assert entries[0]["preset"]["agent_id"] == "agent_viventium_main_95aeb3"


def test_prune_unavailable_source_defaults_preserves_anthropic_for_connected_accounts() -> None:
    payload = {
        "modelSpecs": {
            "list": [
                {
                    "name": "claude-sonnet-4-6",
                    "label": "Claude Sonnet 4 6",
                    "preset": {"endpoint": "anthropic", "model": "claude-sonnet-4-6"},
                },
                {
                    "name": "viventium",
                    "preset": {"endpoint": "agents", "agent_id": "agent_viventium_main_95aeb3"},
                },
            ],
            "addedEndpoints": ["agents", "anthropic", "openAI"],
        },
        "endpoints": {"anthropic": {"summaryModel": "claude-sonnet-4-6"}},
    }
    preserved = config_compiler.prune_unavailable_source_defaults(
        payload,
        {
            "ANTHROPIC_API_KEY": "user_provided",
            "VIVENTIUM_LOCAL_SUBSCRIPTION_AUTH": "true",
        },
    )
    assert "anthropic" in preserved["modelSpecs"]["addedEndpoints"]
    assert any(
        entry.get("preset", {}).get("endpoint") == "anthropic"
        for entry in preserved["modelSpecs"]["list"]
    )
    assert "anthropic" in preserved["endpoints"]


def test_prune_unavailable_source_defaults_prunes_unusable_anthropic_direct_entries() -> None:
    payload = {
        "modelSpecs": {
            "list": [
                {
                    "name": "claude-sonnet-4-6",
                    "label": "Claude Sonnet 4 6",
                    "preset": {"endpoint": "anthropic", "model": "claude-sonnet-4-6"},
                },
                {
                    "name": "viventium",
                    "preset": {"endpoint": "agents", "agent_id": "agent_viventium_main_95aeb3"},
                },
            ],
            "addedEndpoints": ["agents", "anthropic", "openAI"],
        },
        "endpoints": {"anthropic": {"summaryModel": "claude-sonnet-4-6"}},
    }
    pruned = config_compiler.prune_unavailable_source_defaults(
        payload,
        {"ANTHROPIC_API_KEY": ""},
    )
    assert "anthropic" not in pruned["modelSpecs"]["addedEndpoints"]
    assert all(
        entry.get("preset", {}).get("endpoint") != "anthropic"
        for entry in pruned["modelSpecs"]["list"]
    )
    assert "anthropic" not in pruned["endpoints"]


def test_prune_unavailable_source_defaults_preserves_current_explicit_anthropic_models() -> None:
    payload = {
        "modelSpecs": {
            "list": [
                {
                    "name": "claude-sonnet-4-6",
                    "label": "Claude Sonnet 4 6",
                    "preset": {"endpoint": "anthropic", "model": "claude-sonnet-4-6"},
                },
                {
                    "name": "claude-opus-4-7",
                    "label": "Claude Opus 4 7",
                    "preset": {"endpoint": "anthropic", "model": "claude-opus-4-7"},
                },
            ]
        },
        "endpoints": {"anthropic": {"summaryModel": "claude-sonnet-4-6"}},
    }
    normalized = config_compiler.prune_unavailable_source_defaults(
        payload,
        {"ANTHROPIC_API_KEY": "anthropic-test"},
    )
    assert [entry["name"] for entry in normalized["modelSpecs"]["list"]] == [
        "claude-sonnet-4-6",
        "claude-opus-4-7",
    ]
    assert normalized["modelSpecs"]["list"][0]["label"] == "Claude Sonnet 4 6"
    assert normalized["modelSpecs"]["list"][1]["label"] == "Claude Opus 4 7"
    assert normalized["endpoints"]["anthropic"]["summaryModel"] == "claude-sonnet-4-6"


def test_source_of_truth_built_in_agent_avatars_use_portable_asset_paths() -> None:
    bundle = load_source_of_truth_agents_bundle()
    avatar_paths = [
        bundle.get("mainAgent", {}).get("avatar", {}).get("filepath"),
        *[
            agent.get("avatar", {}).get("filepath")
            for agent in bundle.get("backgroundAgents", [])
        ],
    ]
    avatar_paths = [path for path in avatar_paths if path]

    if avatar_paths:
        assert all(not path.startswith("/images/") for path in avatar_paths)
        assert all(
            not path.startswith("/") or path.startswith("/assets/")
            for path in avatar_paths
        )


def test_config_compiler_preserves_explicit_cloudflare_quick_tunnel(tmp_path: Path) -> None:
    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "profile": "isolated",
            "call_session_secret": {"secret_value": "call-session-test"},
            "network": {"remote_call_mode": "cloudflare_quick_tunnel"},
        },
        "llm": {
            "activation": {
                "provider": "groq",
                "auth_mode": "api_key",
                "secret_value": "groq-test",
            },
            "primary": {
                "provider": "openai",
                "auth_mode": "api_key",
                "secret_value": "openai-test",
            },
            "secondary": {"provider": "none", "auth_mode": "disabled"},
            "extra_provider_keys": {},
        },
        "voice": {"mode": "local"},
        "integrations": {
            "telegram": {"enabled": False},
            "google_workspace": {"enabled": False},
            "ms365": {"enabled": False},
            "skyvern": {"enabled": False},
            "openclaw": {"enabled": False},
        },
    }
    config_path = tmp_path / "config.yaml"
    output_dir = tmp_path / "out"
    write_config(config_path, config)

    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/viventium/config_compiler.py"),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        cwd=REPO_ROOT,
    )

    runtime_env = (output_dir / "runtime.env").read_text(encoding="utf-8")
    assert "VIVENTIUM_REMOTE_CALL_MODE=cloudflare_quick_tunnel" in runtime_env


@pytest.mark.parametrize(
    ("remote_call_mode", "expected"),
    [
        ("tailscale_tailnet_https", "VIVENTIUM_REMOTE_CALL_MODE=tailscale_tailnet_https"),
        ("netbird_selfhosted_mesh", "VIVENTIUM_REMOTE_CALL_MODE=netbird_selfhosted_mesh"),
        ("public_https_edge", "VIVENTIUM_REMOTE_CALL_MODE=public_https_edge"),
        ("custom_domain", "VIVENTIUM_REMOTE_CALL_MODE=public_https_edge"),
    ],
)
def test_config_compiler_preserves_supported_remote_mesh_modes(
    tmp_path: Path, remote_call_mode: str, expected: str
) -> None:
    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "profile": "isolated",
            "call_session_secret": {"secret_value": "call-session-test"},
            "network": {
                "remote_call_mode": remote_call_mode,
                "public_client_origin": "https://app.example.test",
                "public_api_origin": "https://app.example.test:8443",
                "public_playground_origin": "https://app.example.test:3443",
                "public_livekit_url": "wss://app.example.test:7443",
                "livekit_node_ip": "100.80.40.20",
            },
        },
        "llm": {
            "activation": {
                "provider": "groq",
                "auth_mode": "api_key",
                "secret_value": "groq-test",
            },
            "primary": {
                "provider": "openai",
                "auth_mode": "api_key",
                "secret_value": "openai-test",
            },
            "secondary": {"provider": "none", "auth_mode": "disabled"},
            "extra_provider_keys": {},
        },
        "voice": {"mode": "local"},
        "integrations": {
            "telegram": {"enabled": False},
            "google_workspace": {"enabled": False},
            "ms365": {"enabled": False},
            "skyvern": {"enabled": False},
            "openclaw": {"enabled": False},
        },
    }
    config_path = tmp_path / "config.yaml"
    output_dir = tmp_path / "out"
    write_config(config_path, config)

    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/viventium/config_compiler.py"),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        cwd=REPO_ROOT,
    )

    runtime_env = (output_dir / "runtime.env").read_text(encoding="utf-8")
    assert expected in runtime_env
    assert "VIVENTIUM_PUBLIC_CLIENT_URL=https://app.example.test" in runtime_env
    assert "VIVENTIUM_PUBLIC_SERVER_URL=https://app.example.test:8443" in runtime_env
    assert "VIVENTIUM_PUBLIC_PLAYGROUND_URL=https://app.example.test:3443" in runtime_env
    assert "VIVENTIUM_PUBLIC_LIVEKIT_URL=wss://app.example.test:7443" in runtime_env
    assert "LIVEKIT_NODE_IP=100.80.40.20" in runtime_env


def test_config_compiler_renders_runtime_auth_controls(tmp_path: Path) -> None:
    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "profile": "isolated",
            "auth": {
                "allow_registration": False,
                "bootstrap_registration_once": True,
                "allow_password_reset": False,
            },
            "call_session_secret": {"secret_value": "call-session-test"},
        },
        "llm": {
            "activation": {
                "provider": "groq",
                "auth_mode": "api_key",
                "secret_value": "groq-test",
            },
            "primary": {
                "provider": "openai",
                "auth_mode": "api_key",
                "secret_value": "openai-test",
            },
            "secondary": {"provider": "none", "auth_mode": "disabled"},
            "extra_provider_keys": {},
        },
        "voice": {"mode": "local"},
        "integrations": {
            "telegram": {"enabled": False},
            "google_workspace": {"enabled": False},
            "ms365": {"enabled": False},
            "skyvern": {"enabled": False},
            "openclaw": {"enabled": False},
        },
    }
    config_path = tmp_path / "config.yaml"
    output_dir = tmp_path / "out"
    write_config(config_path, config)

    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/viventium/config_compiler.py"),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        cwd=REPO_ROOT,
    )

    runtime_env = (output_dir / "runtime.env").read_text(encoding="utf-8")
    assert "ALLOW_REGISTRATION=false" in runtime_env
    assert "VIVENTIUM_BOOTSTRAP_REGISTRATION_ONCE=true" in runtime_env
    assert "ALLOW_PASSWORD_RESET=false" in runtime_env


def test_resolve_voice_settings_keeps_local_first_stt_on_intel_even_when_openai_key_exists(
    monkeypatch,
) -> None:
    monkeypatch.setattr(config_compiler.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(config_compiler.platform, "machine", lambda: "x86_64")

    config = {
        "llm": {
            "primary": {
                "provider": "openai",
                "auth_mode": "api_key",
                "secret_value": "openai-test",
            },
            "secondary": {"provider": "none", "auth_mode": "disabled"},
            "extra_provider_keys": {},
        },
        "voice": {
            "mode": "local",
        },
    }

    result = config_compiler.resolve_voice_settings(config)
    assert result["stt_provider"] == "whisper_local"


def test_config_compiler_with_integrations_and_voice(tmp_path: Path) -> None:
    config = {
        "version": 1,
        "install": {"mode": "docker"},
        "runtime": {
            "log_level": "info",
            "profile": "isolated",
            "call_session_secret": {"secret_value": "call-secret-2"},
        },
        "llm": {
            "activation": {
                "provider": "groq",
                "auth_mode": "api_key",
                "secret_value": "groq-test",
            },
            "primary": {
                "provider": "openai",
                "auth_mode": "api_key",
                "secret_value": "openai-test",
            },
            "secondary": {
                "provider": "anthropic",
                "auth_mode": "api_key",
                "secret_value": "anthropic-test",
            },
            "extra_provider_keys": {
                "x_ai": "xai-test",
            },
        },
        "voice": {
            "mode": "hosted",
            "stt_provider": "assemblyai",
            "stt": {"secret_value": "assemblyai-test"},
            "tts_provider": "elevenlabs",
            "tts": {"secret_value": "elevenlabs-test"},
            "fast_llm_provider": "x_ai",
        },
        "integrations": {
            "telegram": {"enabled": True, "secret_value": VALID_TELEGRAM_TOKEN},
            "telegram_codex": {
                "enabled": True,
                "secret_value": VALID_TELEGRAM_CODEX_TOKEN,
                "bot_username": "viv_codex_bot",
                "private_chat_only": True,
            },
            "google_workspace": {
                "enabled": True,
                "client_id": "google-client-id",
                "client_secret": {"secret_value": "google-secret"},
                "refresh_token": {"secret_value": "google-refresh"},
            },
            "ms365": {
                "enabled": True,
                "client_id": "ms365-client-id",
                "tenant_id": "ms365-tenant-id",
                "business_email": "ops@example.com",
                "client_secret": {"secret_value": "ms365-secret"},
            },
            "skyvern": {
                "enabled": True,
                "api_key": {"secret_value": "skyvern-secret"},
                "base_url": "http://localhost:8200",
            },
            "openclaw": {"enabled": True},
        },
    }
    config_path = tmp_path / "config.yaml"
    output_dir = tmp_path / "out"
    write_config(config_path, config)

    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/viventium/config_compiler.py"),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        cwd=REPO_ROOT,
    )

    runtime_env = (output_dir / "runtime.env").read_text(encoding="utf-8")
    librechat_yaml = yaml.safe_load((output_dir / "librechat.yaml").read_text(encoding="utf-8"))

    assert "ASSEMBLYAI_API_KEY=assemblyai-test" in runtime_env
    assert "ELEVENLABS_API_KEY=elevenlabs-test" in runtime_env
    assert "ELEVEN_API_KEY=elevenlabs-test" in runtime_env
    assert "XAI_API_KEY=xai-test" in runtime_env
    assert f"BOT_TOKEN={VALID_TELEGRAM_TOKEN}" in runtime_env
    assert "VIVENTIUM_TELEGRAM_SECRET=call-secret-2" in runtime_env
    assert "VIVENTIUM_LIBRECHAT_ORIGIN=http://localhost:3180" in runtime_env
    assert "VIVENTIUM_TELEGRAM_AGENT_ID=agent_viventium_main_95aeb3" in runtime_env
    assert "START_TELEGRAM_CODEX=true" in runtime_env
    assert f"TELEGRAM_CODEX_BOT_TOKEN={VALID_TELEGRAM_CODEX_TOKEN}" in runtime_env
    assert "TELEGRAM_CODEX_BOT_USERNAME=viv_codex_bot" in runtime_env
    assert "GOOGLE_CLIENT_ID=google-client-id" in runtime_env
    assert "GOOGLE_CLIENT_SECRET=google-secret" in runtime_env
    assert "GOOGLE_REFRESH_TOKEN=google-refresh" in runtime_env
    assert "MS365_MCP_CLIENT_ID=ms365-client-id" in runtime_env
    assert "MS365_MCP_CLIENT_SECRET=ms365-secret" in runtime_env
    assert "MS365_MCP_TENANT_ID=ms365-tenant-id" in runtime_env
    assert "MS365_BUSINESS_EMAIL=ops@example.com" in runtime_env
    assert "SKYVERN_API_KEY=skyvern-secret" in runtime_env
    assert "SKYVERN_BASE_URL=http://localhost:8200" in runtime_env
    assert any(endpoint["name"] == "xai" for endpoint in librechat_yaml["endpoints"]["custom"])
    assert librechat_yaml["mcpServers"]["google_workspace"]["url"] == "${GOOGLE_WORKSPACE_MCP_URL}"
    assert librechat_yaml["mcpServers"]["ms-365"]["url"] == "${MS365_MCP_SERVER_URL}"

    telegram_codex_settings = yaml.safe_load(
        (output_dir / "telegram-codex" / "settings.yaml").read_text(encoding="utf-8")
    )
    telegram_codex_projects = yaml.safe_load(
        (output_dir / "telegram-codex" / "projects.yaml").read_text(encoding="utf-8")
    )
    telegram_env = (output_dir / "service-env" / "telegram.config.env").read_text(encoding="utf-8")
    telegram_codex_env = (output_dir / "service-env" / "telegram-codex.env").read_text(encoding="utf-8")

    assert telegram_codex_settings["bot"]["private_chat_only"] is True
    assert telegram_codex_settings["transcription"]["language"] == "en"
    assert telegram_codex_settings["runtime"]["stable_pairing_root"].endswith("state/telegram-codex/paired-users")
    assert telegram_codex_settings["runtime"]["legacy_paired_users_path"].endswith(
        "state/runtime/isolated/telegram-codex/state/paired_users.json"
    )
    assert telegram_codex_projects["default_project"] == "viventium_core"
    assert "telegram_codex" in telegram_codex_projects["projects"]
    assert f"BOT_TOKEN={VALID_TELEGRAM_TOKEN}" in telegram_env
    assert "VIVENTIUM_TELEGRAM_AGENT_ID=agent_viventium_main_95aeb3" in telegram_env
    assert "VIVENTIUM_LIBRECHAT_ORIGIN=http://localhost:3180" in telegram_env
    assert "VIVENTIUM_TELEGRAM_SECRET=call-secret-2" in telegram_env
    assert f"TELEGRAM_CODEX_BOT_TOKEN={VALID_TELEGRAM_CODEX_TOKEN}" in telegram_codex_env


def test_config_compiler_emits_voice_turn_handling_env_overrides(tmp_path: Path) -> None:
    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "log_level": "info",
            "profile": "isolated",
            "call_session_secret": {"secret_value": "call-session-test"},
            "network": {"remote_call_mode": "auto"},
        },
        "llm": {
            "activation": {
                "provider": "groq",
                "auth_mode": "api_key",
                "secret_value": "groq-test",
            },
            "primary": {
                "provider": "openai",
                "auth_mode": "api_key",
                "secret_value": "openai-test",
            },
            "secondary": {"provider": "none", "auth_mode": "disabled"},
            "extra_provider_keys": {},
        },
        "voice": {
            "mode": "hosted",
            "stt_provider": "assemblyai",
            "stt": {
                "secret_value": "assemblyai-test",
                "end_of_turn_confidence_threshold": 0.31,
                "min_end_of_turn_silence_when_confident_ms": 240,
                "max_turn_silence_ms": 1500,
                "format_turns": True,
                "vad_min_speech_s": 0.12,
                "vad_min_silence_s": 0.72,
                "vad_activation_threshold": 0.33,
            },
            "tts_provider": "cartesia",
            "tts": {"secret_value": "cartesia-test"},
            "turn_detection": "turn_detector",
            "turn_handling": {
                "min_interruption_duration_s": 0.4,
                "min_interruption_words": 2,
                "min_endpointing_delay_s": 0.2,
                "max_endpointing_delay_s": 2.1,
                "false_interruption_timeout_s": 1.8,
                "resume_false_interruption": True,
                "min_consecutive_speech_delay_s": 0.25,
            },
            "worker": {
                "initialize_process_timeout_s": 55,
                "idle_processes": 2,
                "load_threshold": 0.82,
                "job_memory_warn_mb": 1600,
                "job_memory_limit_mb": 2400,
                "prewarm_local_tts": False,
            },
        },
        "integrations": {
            "telegram": {"enabled": False},
            "google_workspace": {"enabled": False},
            "ms365": {"enabled": False},
            "skyvern": {"enabled": False},
            "openclaw": {"enabled": False},
        },
    }
    config_path = tmp_path / "config.yaml"
    output_dir = tmp_path / "out"
    write_config(config_path, config)

    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/viventium/config_compiler.py"),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        cwd=REPO_ROOT,
    )

    runtime_env = (output_dir / "runtime.env").read_text(encoding="utf-8")

    assert "VIVENTIUM_TURN_DETECTION=turn_detector" in runtime_env
    assert "VIVENTIUM_VOICE_MIN_INTERRUPTION_DURATION_S=0.4" in runtime_env
    assert "VIVENTIUM_VOICE_MIN_INTERRUPTION_WORDS=2" in runtime_env
    assert "VIVENTIUM_VOICE_MIN_ENDPOINTING_DELAY_S=0.2" in runtime_env
    assert "VIVENTIUM_VOICE_MAX_ENDPOINTING_DELAY_S=2.1" in runtime_env
    assert "VIVENTIUM_VOICE_FALSE_INTERRUPTION_TIMEOUT_S=1.8" in runtime_env
    assert "VIVENTIUM_VOICE_RESUME_FALSE_INTERRUPTION=true" in runtime_env
    assert "VIVENTIUM_VOICE_MIN_CONSECUTIVE_SPEECH_DELAY_S=0.25" in runtime_env
    assert "VIVENTIUM_VOICE_INITIALIZE_PROCESS_TIMEOUT_S=55" in runtime_env
    assert "VIVENTIUM_VOICE_IDLE_PROCESSES=2" in runtime_env
    assert "VIVENTIUM_VOICE_WORKER_LOAD_THRESHOLD=0.82" in runtime_env
    assert "VIVENTIUM_VOICE_JOB_MEMORY_WARN_MB=1600" in runtime_env
    assert "VIVENTIUM_VOICE_JOB_MEMORY_LIMIT_MB=2400" in runtime_env
    assert "VIVENTIUM_VOICE_PREWARM_LOCAL_TTS=false" in runtime_env
    assert "VIVENTIUM_ASSEMBLYAI_END_OF_TURN_CONFIDENCE_THRESHOLD=0.31" in runtime_env
    assert "VIVENTIUM_ASSEMBLYAI_MIN_END_OF_TURN_SILENCE_WHEN_CONFIDENT_MS=240" in runtime_env
    assert "VIVENTIUM_ASSEMBLYAI_MAX_TURN_SILENCE_MS=1500" in runtime_env
    assert "VIVENTIUM_ASSEMBLYAI_FORMAT_TURNS=true" in runtime_env
    assert "VIVENTIUM_STT_VAD_MIN_SPEECH=0.12" in runtime_env
    assert "VIVENTIUM_STT_VAD_MIN_SILENCE=0.72" in runtime_env
    assert "VIVENTIUM_STT_VAD_ACTIVATION=0.33" in runtime_env


def test_config_compiler_emits_background_followup_window_override(tmp_path: Path) -> None:
    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "log_level": "info",
            "profile": "isolated",
            "background_followup_window_s": 45,
            "call_session_secret": {"secret_value": "call-session-test"},
            "network": {"remote_call_mode": "auto"},
        },
        "llm": {
            "activation": {
                "provider": "groq",
                "auth_mode": "api_key",
                "secret_value": "groq-test",
            },
            "primary": {
                "provider": "openai",
                "auth_mode": "api_key",
                "secret_value": "openai-test",
            },
            "secondary": {"provider": "none", "auth_mode": "disabled"},
            "extra_provider_keys": {},
        },
        "voice": {
            "mode": "local",
            "stt_provider": "whisper_local",
            "tts_provider": "browser",
        },
        "integrations": {
            "telegram": {"enabled": False},
            "google_workspace": {"enabled": False},
            "ms365": {"enabled": False},
            "skyvern": {"enabled": False},
            "openclaw": {"enabled": False},
        },
    }
    config_path = tmp_path / "config.yaml"
    output_dir = tmp_path / "out"
    write_config(config_path, config)

    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/viventium/config_compiler.py"),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        cwd=REPO_ROOT,
    )

    runtime_env = (output_dir / "runtime.env").read_text(encoding="utf-8")

    assert "VIVENTIUM_CORTEX_FOLLOWUP_GRACE_S=45" in runtime_env
    assert "VIVENTIUM_VOICE_FOLLOWUP_GRACE_S=45" in runtime_env
    assert "VIVENTIUM_TELEGRAM_FOLLOWUP_GRACE_S=45" in runtime_env


def test_config_compiler_emits_assemblyai_turn_detection_defaults_when_unset(tmp_path: Path) -> None:
    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "log_level": "info",
            "profile": "isolated",
            "call_session_secret": {"secret_value": "call-session-test"},
            "network": {"remote_call_mode": "auto"},
        },
        "llm": {
            "activation": {
                "provider": "groq",
                "auth_mode": "api_key",
                "secret_value": "groq-test",
            },
            "primary": {
                "provider": "openai",
                "auth_mode": "api_key",
                "secret_value": "openai-test",
            },
            "secondary": {"provider": "none", "auth_mode": "disabled"},
            "extra_provider_keys": {},
        },
        "voice": {
            "mode": "hosted",
            "stt_provider": "assemblyai",
            "stt": {"secret_value": "assemblyai-test"},
            "tts_provider": "cartesia",
            "tts": {"secret_value": "cartesia-test"},
        },
        "integrations": {
            "telegram": {"enabled": False},
            "google_workspace": {"enabled": False},
            "ms365": {"enabled": False},
            "skyvern": {"enabled": False},
            "openclaw": {"enabled": False},
        },
    }
    config_path = tmp_path / "config.yaml"
    output_dir = tmp_path / "out"
    write_config(config_path, config)

    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/viventium/config_compiler.py"),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        cwd=REPO_ROOT,
    )

    runtime_env = (output_dir / "runtime.env").read_text(encoding="utf-8")

    assert "VIVENTIUM_ASSEMBLYAI_END_OF_TURN_CONFIDENCE_THRESHOLD=0.01" in runtime_env
    assert "VIVENTIUM_ASSEMBLYAI_MIN_END_OF_TURN_SILENCE_WHEN_CONFIDENT_MS=100" in runtime_env
    assert "VIVENTIUM_ASSEMBLYAI_MAX_TURN_SILENCE_MS=1000" in runtime_env


def test_config_compiler_emits_assemblyai_turn_detection_defaults_for_override_paths(
    tmp_path: Path,
) -> None:
    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "log_level": "info",
            "profile": "isolated",
            "call_session_secret": {"secret_value": "call-session-test"},
            "network": {"remote_call_mode": "auto"},
        },
        "llm": {
            "activation": {
                "provider": "groq",
                "auth_mode": "api_key",
                "secret_value": "groq-test",
            },
            "primary": {
                "provider": "openai",
                "auth_mode": "api_key",
                "secret_value": "openai-test",
            },
            "secondary": {"provider": "none", "auth_mode": "disabled"},
            "extra_provider_keys": {},
        },
        "voice": {
            "mode": "hosted",
            "stt_provider": "whisper_local",
            "tts_provider": "cartesia",
            "tts": {"secret_value": "cartesia-test"},
        },
        "integrations": {
            "telegram": {"enabled": False},
            "google_workspace": {"enabled": False},
            "ms365": {"enabled": False},
            "skyvern": {"enabled": False},
            "openclaw": {"enabled": False},
        },
    }
    config_path = tmp_path / "config.yaml"
    output_dir = tmp_path / "out"
    write_config(config_path, config)

    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/viventium/config_compiler.py"),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        cwd=REPO_ROOT,
    )

    runtime_env = (output_dir / "runtime.env").read_text(encoding="utf-8")

    assert "VIVENTIUM_ASSEMBLYAI_END_OF_TURN_CONFIDENCE_THRESHOLD=0.01" in runtime_env
    assert "VIVENTIUM_ASSEMBLYAI_MIN_END_OF_TURN_SILENCE_WHEN_CONFIDENT_MS=100" in runtime_env
    assert "VIVENTIUM_ASSEMBLYAI_MAX_TURN_SILENCE_MS=1000" in runtime_env


def test_config_compiler_renders_structured_telegram_bot_api_settings(tmp_path: Path) -> None:
    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "log_level": "info",
            "profile": "isolated",
            "call_session_secret": {"secret_value": "call-secret-telegram-bot-api"},
        },
        "llm": {
            "activation": {
                "provider": "groq",
                "auth_mode": "api_key",
                "secret_value": "groq-test",
            },
            "primary": {
                "provider": "openai",
                "auth_mode": "api_key",
                "secret_value": "openai-test",
            },
            "secondary": {"provider": "none", "auth_mode": "disabled"},
            "extra_provider_keys": {},
        },
        "voice": {
            "mode": "disabled",
            "stt_provider": "whisper_local",
            "tts_provider": "browser",
        },
        "integrations": {
            "telegram": {
                "enabled": True,
                "secret_value": VALID_TELEGRAM_TOKEN,
                "bot_api_origin": "http://127.0.0.1:8081",
                "bot_api_base_url": "",
                "bot_api_base_file_url": "",
            },
            "google_workspace": {"enabled": False},
            "ms365": {"enabled": False},
            "skyvern": {"enabled": False},
            "openclaw": {"enabled": False},
        },
    }
    config_path = tmp_path / "config.yaml"
    output_dir = tmp_path / "out"
    write_config(config_path, config)

    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/viventium/config_compiler.py"),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        cwd=REPO_ROOT,
    )

    runtime_env = (output_dir / "runtime.env").read_text(encoding="utf-8")
    telegram_env = (output_dir / "service-env" / "telegram.config.env").read_text(encoding="utf-8")

    assert "VIVENTIUM_TELEGRAM_MAX_FILE_SIZE=10485760" in runtime_env
    assert "VIVENTIUM_TELEGRAM_BOT_API_ORIGIN=http://127.0.0.1:8081" in runtime_env
    assert "VIVENTIUM_TELEGRAM_BOT_API_ORIGIN=http://127.0.0.1:8081" in telegram_env
    assert "VIVENTIUM_TELEGRAM_BOT_API_BASE_URL" not in runtime_env
    assert "VIVENTIUM_TELEGRAM_BOT_API_BASE_FILE_URL" not in runtime_env


def test_config_compiler_renders_managed_local_telegram_bot_api_settings(tmp_path: Path) -> None:
    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "log_level": "info",
            "profile": "isolated",
            "call_session_secret": {"secret_value": "call-secret-telegram-local-bot-api"},
        },
        "llm": {
            "activation": {
                "provider": "groq",
                "auth_mode": "api_key",
                "secret_value": "groq-test",
            },
            "primary": {
                "provider": "openai",
                "auth_mode": "api_key",
                "secret_value": "openai-test",
            },
            "secondary": {"provider": "none", "auth_mode": "disabled"},
            "extra_provider_keys": {},
        },
        "voice": {
            "mode": "disabled",
            "stt_provider": "whisper_local",
            "tts_provider": "browser",
        },
        "integrations": {
            "telegram": {
                "enabled": True,
                "secret_value": VALID_TELEGRAM_TOKEN,
                "local_bot_api": {
                    "enabled": True,
                    "host": "127.0.0.1",
                    "port": 8084,
                    "api_id": "telegram-api-id-test",
                    "api_hash": "telegram-api-hash-test",
                },
            },
            "google_workspace": {"enabled": False},
            "ms365": {"enabled": False},
            "skyvern": {"enabled": False},
            "openclaw": {"enabled": False},
        },
    }
    config_path = tmp_path / "config.yaml"
    output_dir = tmp_path / "out"
    write_config(config_path, config)

    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/viventium/config_compiler.py"),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        cwd=REPO_ROOT,
    )

    runtime_env = (output_dir / "runtime.env").read_text(encoding="utf-8")
    telegram_env = (output_dir / "service-env" / "telegram.config.env").read_text(encoding="utf-8")

    assert "VIVENTIUM_TELEGRAM_LOCAL_BOT_API_ENABLED=true" in runtime_env
    assert "VIVENTIUM_TELEGRAM_LOCAL_BOT_API_HOST=127.0.0.1" in runtime_env
    assert "VIVENTIUM_TELEGRAM_LOCAL_BOT_API_PORT=8084" in runtime_env
    assert "VIVENTIUM_TELEGRAM_LOCAL_BOT_API_API_ID=telegram-api-id-test" in runtime_env
    assert "VIVENTIUM_TELEGRAM_LOCAL_BOT_API_API_HASH=telegram-api-hash-test" in runtime_env
    assert "VIVENTIUM_TELEGRAM_BOT_API_ORIGIN=http://127.0.0.1:8084" in runtime_env
    assert "VIVENTIUM_TELEGRAM_MAX_FILE_SIZE=104857600" in runtime_env
    assert "VIVENTIUM_TELEGRAM_LOCAL_BOT_API_ENABLED=true" in telegram_env
    assert "VIVENTIUM_TELEGRAM_BOT_API_ORIGIN=http://127.0.0.1:8084" in telegram_env
    assert "VIVENTIUM_TELEGRAM_MAX_FILE_SIZE=104857600" in telegram_env


def test_config_compiler_rejects_conflicting_managed_and_explicit_telegram_bot_api_settings(
    tmp_path: Path,
) -> None:
    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {"profile": "isolated"},
        "llm": {
            "activation": {
                "provider": "groq",
                "auth_mode": "api_key",
                "secret_value": "groq-test",
            },
            "primary": {
                "provider": "openai",
                "auth_mode": "api_key",
                "secret_value": "openai-test",
            },
            "secondary": {"provider": "none", "auth_mode": "disabled"},
            "extra_provider_keys": {},
        },
        "voice": {"mode": "disabled", "stt_provider": "whisper_local", "tts_provider": "browser"},
        "integrations": {
            "telegram": {
                "enabled": True,
                "secret_value": VALID_TELEGRAM_TOKEN,
                "bot_api_origin": "http://127.0.0.1:9999",
                "local_bot_api": {
                    "enabled": True,
                    "api_id": "telegram-api-id-test",
                    "api_hash": "telegram-api-hash-test",
                },
            },
            "google_workspace": {"enabled": False},
            "ms365": {"enabled": False},
            "skyvern": {"enabled": False},
            "openclaw": {"enabled": False},
        },
    }
    config_path = tmp_path / "config.yaml"
    output_dir = tmp_path / "out"
    write_config(config_path, config)

    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/viventium/config_compiler.py"),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ],
        check=False,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 1
    combined_output = completed.stdout + completed.stderr
    assert "integrations.telegram.local_bot_api.enabled cannot be combined" in combined_output


def test_config_compiler_rejects_invalid_enabled_telegram_token(tmp_path: Path) -> None:
    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "log_level": "info",
            "profile": "isolated",
            "call_session_secret": {"secret_value": "call-secret-2"},
        },
        "llm": {
            "activation": {
                "provider": "groq",
                "auth_mode": "api_key",
                "secret_value": "groq-test",
            },
            "primary": {
                "provider": "openai",
                "auth_mode": "api_key",
                "secret_value": "openai-test",
            },
            "secondary": {
                "provider": "none",
                "auth_mode": "disabled",
            },
            "extra_provider_keys": {},
        },
        "voice": {
            "mode": "local",
            "stt_provider": "whisper_local",
            "tts_provider": "local_chatterbox_turbo_mlx_8bit",
        },
        "integrations": {
            "telegram": {"enabled": True, "secret_value": "not-a-telegram-token"},
            "telegram_codex": {"enabled": False},
        },
    }
    config_path = tmp_path / "config.yaml"
    output_dir = tmp_path / "out"
    write_config(config_path, config)

    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/viventium/config_compiler.py"),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ],
        check=False,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    combined_output = f"{completed.stdout}\n{completed.stderr}"
    assert "integrations.telegram is enabled" in combined_output
    assert "BotFather format" in combined_output


def test_config_compiler_exports_dormant_voice_provider_keys_for_precall_selection(
    tmp_path: Path,
) -> None:
    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "log_level": "info",
            "profile": "isolated",
            "call_session_secret": {"secret_value": "call-secret"},
        },
        "llm": {
            "activation": {
                "provider": "groq",
                "auth_mode": "api_key",
                "secret_value": "groq-test",
            },
            "primary": {
                "provider": "openai",
                "auth_mode": "api_key",
                "secret_value": "openai-test",
            },
            "secondary": {
                "provider": "anthropic",
                "auth_mode": "api_key",
                "secret_value": "anthropic-test",
            },
            "extra_provider_keys": {},
        },
        "voice": {
            "mode": "local",
            "stt_provider": "whisper_local",
            "tts_provider": "local_chatterbox_turbo_mlx_8bit",
            "tts_provider_fallback": "openai",
            "provider_keys": {
                "assemblyai": {"secret_value": "assemblyai-dormant"},
                "cartesia": {"secret_value": "cartesia-dormant"},
                "elevenlabs": {"secret_value": "elevenlabs-dormant"},
            },
        },
        "integrations": {},
    }
    config_path = tmp_path / "config.yaml"
    output_dir = tmp_path / "out"
    write_config(config_path, config)

    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/viventium/config_compiler.py"),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        cwd=REPO_ROOT,
    )

    runtime_env = (output_dir / "runtime.env").read_text(encoding="utf-8")

    assert "VIVENTIUM_STT_PROVIDER=whisper_local" in runtime_env
    if platform.system() == "Darwin" and platform.machine().lower() in {"arm64", "aarch64"}:
        assert "VIVENTIUM_TTS_PROVIDER=local_chatterbox_turbo_mlx_8bit" in runtime_env
        assert "VIVENTIUM_TTS_PROVIDER_FALLBACK=openai" in runtime_env
    else:
        assert "VIVENTIUM_TTS_PROVIDER=openai" in runtime_env
        assert "VIVENTIUM_TTS_PROVIDER_FALLBACK=" not in runtime_env
    assert "ASSEMBLYAI_API_KEY=assemblyai-dormant" in runtime_env
    assert "CARTESIA_API_KEY=cartesia-dormant" in runtime_env
    assert "ELEVENLABS_API_KEY=elevenlabs-dormant" in runtime_env
    assert "ELEVEN_API_KEY=elevenlabs-dormant" in runtime_env


def test_config_compiler_disables_rag_bootstrap_when_conversation_recall_default_is_off(tmp_path: Path) -> None:
    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "log_level": "info",
            "profile": "isolated",
            "call_session_secret": {"secret_value": "call-secret-off"},
            "personalization": {"default_conversation_recall": False},
        },
        "llm": {
            "activation": {
                "provider": "groq",
                "auth_mode": "api_key",
                "secret_value": "groq-test",
            },
            "primary": {
                "provider": "openai",
                "auth_mode": "api_key",
                "secret_value": "openai-test",
            },
            "secondary": {"provider": "none", "auth_mode": "disabled"},
            "extra_provider_keys": {},
        },
        "voice": {"mode": "disabled", "stt_provider": "whisper_local", "tts_provider": "browser"},
        "integrations": {
            "telegram": {"enabled": False},
            "google_workspace": {"enabled": False},
            "ms365": {"enabled": False},
            "skyvern": {"enabled": False},
            "openclaw": {"enabled": False},
        },
    }
    config_path = tmp_path / "config.yaml"
    output_dir = tmp_path / "out"
    write_config(config_path, config)

    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/viventium/config_compiler.py"),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        cwd=REPO_ROOT,
    )

    runtime_env = (output_dir / "runtime.env").read_text(encoding="utf-8")

    assert "VIVENTIUM_DEFAULT_CONVERSATION_RECALL=false" in runtime_env
    assert "START_RAG_API=false" in runtime_env


def test_config_compiler_respects_explicit_retrieval_embeddings_override(tmp_path: Path) -> None:
    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "log_level": "info",
            "profile": "isolated",
            "call_session_secret": {"secret_value": "call-secret-off"},
            "retrieval": {
                "embeddings": {
                    "provider": "openai",
                    "model": "text-embedding-3-small",
                    "profile": "custom",
                }
            },
        },
        "llm": {
            "activation": {
                "provider": "groq",
                "auth_mode": "api_key",
                "secret_value": "groq-test",
            },
            "primary": {
                "provider": "openai",
                "auth_mode": "api_key",
                "secret_value": "openai-test",
            },
            "secondary": {"provider": "none", "auth_mode": "disabled"},
            "extra_provider_keys": {},
        },
        "voice": {"mode": "disabled", "stt_provider": "whisper_local", "tts_provider": "browser"},
        "integrations": {
            "telegram": {"enabled": False},
            "google_workspace": {"enabled": False},
            "ms365": {"enabled": False},
            "skyvern": {"enabled": False},
            "openclaw": {"enabled": False},
        },
    }
    config_path = tmp_path / "config.yaml"
    output_dir = tmp_path / "out"
    write_config(config_path, config)

    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/viventium/config_compiler.py"),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        cwd=REPO_ROOT,
    )

    runtime_env = (output_dir / "runtime.env").read_text(encoding="utf-8")

    assert "EMBEDDINGS_PROVIDER=openai" in runtime_env
    assert "EMBEDDINGS_MODEL=text-embedding-3-small" in runtime_env
    assert "VIVENTIUM_RAG_EMBEDDINGS_PROVIDER=openai" in runtime_env
    assert "VIVENTIUM_RAG_EMBEDDINGS_MODEL=text-embedding-3-small" in runtime_env
    assert "VIVENTIUM_RAG_EMBEDDINGS_PROFILE=custom" in runtime_env
    assert "OLLAMA_BASE_URL=" not in runtime_env


def test_config_compiler_enables_connected_accounts_gate_for_openai_and_anthropic(tmp_path: Path) -> None:
    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "log_level": "info",
            "profile": "isolated",
            "call_session_secret": {"secret_value": "call-secret-connected"},
        },
        "llm": {
            "activation": {
                "provider": "groq",
                "auth_mode": "api_key",
                "secret_value": "groq-test",
            },
            "primary": {
                "provider": "openai",
                "auth_mode": "connected_account",
            },
            "secondary": {
                "provider": "anthropic",
                "auth_mode": "api_key",
                "secret_value": "anthropic-test",
            },
            "extra_provider_keys": {},
        },
        "voice": {"mode": "disabled", "stt_provider": "whisper_local", "tts_provider": "browser"},
        "integrations": {
            "telegram": {"enabled": False},
            "google_workspace": {"enabled": False},
            "ms365": {"enabled": False},
            "skyvern": {"enabled": False},
            "openclaw": {"enabled": False},
        },
    }
    config_path = tmp_path / "config.yaml"
    output_dir = tmp_path / "out"
    write_config(config_path, config)

    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/viventium/config_compiler.py"),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        cwd=REPO_ROOT,
    )

    runtime_env = (output_dir / "runtime.env").read_text(encoding="utf-8")
    librechat_yaml = yaml.safe_load((output_dir / "librechat.yaml").read_text(encoding="utf-8"))

    assert "VIVENTIUM_LOCAL_SUBSCRIPTION_AUTH=true" in runtime_env
    assert "VIVENTIUM_DEFAULT_CONVERSATION_RECALL=false" in runtime_env
    assert "VIVENTIUM_OPENAI_AUTH_MODE=connected_account" in runtime_env
    assert "ANTHROPIC_API_KEY=anthropic-test" in runtime_env
    assert librechat_yaml["memory"]["agent"]["provider"] == "anthropic"
    assert librechat_yaml["memory"]["agent"]["model"] == "claude-sonnet-4-6"
    assert librechat_yaml["endpoints"]["anthropic"]["titleEndpoint"] == "anthropic"
    assert librechat_yaml["endpoints"]["anthropic"]["titleModel"] == "claude-sonnet-4-6"


def test_render_librechat_yaml_uses_connected_anthropic_for_memory_when_no_other_foundation_exists() -> None:
    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "profile": "isolated",
            "call_session_secret": {"secret_value": "call-session-test"},
        },
        "llm": {
            "activation": {
                "provider": "groq",
                "auth_mode": "api_key",
                "secret_value": "groq-test",
            },
            "primary": {
                "provider": "anthropic",
                "auth_mode": "connected_account",
            },
            "secondary": {"provider": "none", "auth_mode": "disabled"},
            "extra_provider_keys": {},
        },
        "voice": {"mode": "disabled"},
        "integrations": {
            "telegram": {"enabled": False},
            "google_workspace": {"enabled": False},
            "ms365": {"enabled": False},
            "skyvern": {"enabled": False},
            "openclaw": {"enabled": False},
        },
    }

    assignments = config_compiler.build_agent_assignments(config)
    env = config_compiler.render_runtime_env(config, assignments)
    librechat_yaml = yaml.safe_load(config_compiler.render_librechat_yaml(config, assignments, env))

    assert librechat_yaml["memory"]["agent"]["provider"] == "anthropic"
    assert librechat_yaml["memory"]["agent"]["model"] == "claude-sonnet-4-6"
    assert librechat_yaml["endpoints"]["anthropic"]["titleEndpoint"] == "anthropic"
    assert librechat_yaml["endpoints"]["anthropic"]["titleModel"] == "claude-sonnet-4-6"


def test_render_librechat_yaml_uses_connected_openai_for_memory_when_no_other_foundation_exists() -> None:
    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "profile": "isolated",
            "call_session_secret": {"secret_value": "call-session-test"},
        },
        "llm": {
            "activation": {
                "provider": "groq",
                "auth_mode": "api_key",
                "secret_value": "groq-test",
            },
            "primary": {
                "provider": "openai",
                "auth_mode": "connected_account",
            },
            "secondary": {"provider": "none", "auth_mode": "disabled"},
            "extra_provider_keys": {},
        },
        "voice": {"mode": "disabled"},
        "integrations": {
            "telegram": {"enabled": False},
            "google_workspace": {"enabled": False},
            "ms365": {"enabled": False},
            "skyvern": {"enabled": False},
            "openclaw": {"enabled": False},
        },
    }

    assignments = config_compiler.build_agent_assignments(config)
    env = config_compiler.render_runtime_env(config, assignments)
    librechat_yaml = yaml.safe_load(config_compiler.render_librechat_yaml(config, assignments, env))

    assert env["VIVENTIUM_OPENAI_AUTH_MODE"] == "connected_account"
    assert librechat_yaml["memory"]["agent"]["provider"] == "openai"
    assert librechat_yaml["memory"]["agent"]["model"] == "gpt-5.4"


def test_config_compiler_falls_back_to_existing_runtime_env_when_keychain_secret_is_missing(
    tmp_path: Path,
) -> None:
    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "log_level": "info",
            "profile": "isolated",
            "call_session_secret": {"secret_ref": "keychain://viventium/call_session_secret"},
        },
        "llm": {
            "activation": {
                "provider": "groq",
                "auth_mode": "api_key",
                "secret_ref": "keychain://viventium/groq_api_key",
            },
            "primary": {
                "provider": "openai",
                "auth_mode": "api_key",
                "secret_ref": "keychain://viventium/openai_api_key",
            },
            "secondary": {"provider": "none", "auth_mode": "disabled"},
            "extra_provider_keys": {},
        },
        "voice": {"mode": "disabled", "stt_provider": "whisper_local", "tts_provider": "browser"},
        "integrations": {
            "telegram": {"enabled": True, "secret_ref": "keychain://viventium/telegram_bot_token"},
            "google_workspace": {"enabled": False},
            "ms365": {"enabled": False},
            "skyvern": {"enabled": False},
            "openclaw": {"enabled": False},
        },
    }
    config_path = tmp_path / "config.yaml"
    output_dir = tmp_path / "out"
    existing_runtime_env = tmp_path / "runtime.env"
    bin_dir = tmp_path / "bin"
    write_config(config_path, config)
    bin_dir.mkdir(parents=True, exist_ok=True)
    existing_runtime_env.write_text(
        "\n".join(
            [
                "GROQ_API_KEY=groq-existing",
                "OPENAI_API_KEY=openai-existing",
                f"BOT_TOKEN={VALID_TELEGRAM_EXISTING_TOKEN}",
                "VIVENTIUM_CALL_SESSION_SECRET=call-secret-existing",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (bin_dir / "security").write_text(
        "#!/usr/bin/env bash\nexit 44\n",
        encoding="utf-8",
    )
    (bin_dir / "security").chmod(0o755)

    env = os.environ.copy()
    env["VIVENTIUM_ENV_FILE"] = str(existing_runtime_env)
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    for key in ("GROQ_API_KEY", "OPENAI_API_KEY", "BOT_TOKEN"):
        env.pop(key, None)

    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/viventium/config_compiler.py"),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )

    runtime_env = (output_dir / "runtime.env").read_text(encoding="utf-8")

    assert "GROQ_API_KEY=groq-existing" in runtime_env
    assert "OPENAI_API_KEY=openai-existing" in runtime_env
    assert f"BOT_TOKEN={VALID_TELEGRAM_EXISTING_TOKEN}" in runtime_env
    assert "VIVENTIUM_CALL_SESSION_SECRET=call-secret-existing" in runtime_env


def test_config_compiler_prefers_real_optional_provider_keys_over_placeholders(tmp_path: Path) -> None:
    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "log_level": "info",
            "profile": "isolated",
            "call_session_secret": {"secret_value": "call-secret-optional"},
        },
        "llm": {
            "activation": {
                "provider": "groq",
                "auth_mode": "api_key",
                "secret_value": "groq-test",
            },
            "primary": {
                "provider": "openai",
                "auth_mode": "api_key",
                "secret_value": "openai-test",
            },
            "secondary": {"provider": "none", "auth_mode": "disabled"},
            "extra_provider_keys": {
                "google": "google-key-real",
                "openrouter": "openrouter-real",
                "perplexity": "perplexity-real",
                "x_ai": "xai-real",
            },
        },
        "voice": {"mode": "disabled", "stt_provider": "whisper_local", "tts_provider": "browser"},
        "integrations": {
            "telegram": {"enabled": False},
            "google_workspace": {"enabled": False},
            "ms365": {"enabled": False},
            "skyvern": {"enabled": False},
            "openclaw": {"enabled": False},
        },
    }
    config_path = tmp_path / "config.yaml"
    output_dir = tmp_path / "out"
    write_config(config_path, config)

    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/viventium/config_compiler.py"),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        cwd=REPO_ROOT,
    )

    runtime_env = (output_dir / "runtime.env").read_text(encoding="utf-8")
    assert "GOOGLE_API_KEY=google-key-real" in runtime_env
    assert "GOOGLE_KEY=google-key-real" in runtime_env
    assert "OPENROUTER_API_KEY=openrouter-real" in runtime_env
    assert "PERPLEXITY_API_KEY=perplexity-real" in runtime_env
    assert "XAI_API_KEY=xai-real" in runtime_env


def test_config_compiler_omits_websearch_bundle_when_feature_is_disabled(tmp_path: Path) -> None:
    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "log_level": "info",
            "profile": "isolated",
            "call_session_secret": {"secret_value": "call-secret-websearch"},
        },
        "llm": {
            "activation": {
                "provider": "groq",
                "auth_mode": "api_key",
                "secret_value": "groq-test",
            },
            "primary": {
                "provider": "openai",
                "auth_mode": "api_key",
                "secret_value": "openai-test",
            },
            "secondary": {"provider": "none", "auth_mode": "disabled"},
            "extra_provider_keys": {},
        },
        "voice": {"mode": "disabled", "stt_provider": "whisper_local", "tts_provider": "browser"},
        "integrations": {
            "telegram": {"enabled": False},
            "google_workspace": {"enabled": False},
            "ms365": {"enabled": False},
            "skyvern": {"enabled": False},
            "openclaw": {"enabled": False},
        },
    }
    config_path = tmp_path / "config.yaml"
    output_dir = tmp_path / "out"
    write_config(config_path, config)

    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/viventium/config_compiler.py"),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        cwd=REPO_ROOT,
    )

    generated_path = output_dir / "librechat.generated.yaml"
    if not generated_path.is_file():
        generated_path = output_dir / "librechat.yaml"
    generated = generated_path.read_text(encoding="utf-8")
    assert "${SEARXNG_INSTANCE_URL}" not in generated
    assert "${SERPER_API_KEY}" not in generated
    assert "${FIRECRAWL_API_KEY}" not in generated
    assert "${COHERE_API_KEY}" not in generated


def test_config_compiler_emits_websearch_bundle_when_feature_is_enabled(tmp_path: Path) -> None:
    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "log_level": "info",
            "profile": "isolated",
            "call_session_secret": {"secret_value": "call-secret-websearch-enabled"},
        },
        "llm": {
            "activation": {
                "provider": "groq",
                "auth_mode": "api_key",
                "secret_value": "groq-test",
            },
            "primary": {
                "provider": "openai",
                "auth_mode": "api_key",
                "secret_value": "openai-test",
            },
            "secondary": {"provider": "none", "auth_mode": "disabled"},
            "extra_provider_keys": {},
        },
        "voice": {"mode": "disabled", "stt_provider": "whisper_local", "tts_provider": "browser"},
        "integrations": {
            "web_search": {"enabled": True},
            "telegram": {"enabled": False},
            "google_workspace": {"enabled": False},
            "ms365": {"enabled": False},
            "skyvern": {"enabled": False},
            "openclaw": {"enabled": False},
        },
    }
    config_path = tmp_path / "config.yaml"
    output_dir = tmp_path / "out"
    write_config(config_path, config)

    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/viventium/config_compiler.py"),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        cwd=REPO_ROOT,
    )

    runtime_env = (output_dir / "runtime.env").read_text(encoding="utf-8")
    librechat_yaml = yaml.safe_load((output_dir / "librechat.yaml").read_text(encoding="utf-8"))

    assert "START_SEARXNG=true" in runtime_env
    assert "START_FIRECRAWL=true" in runtime_env
    assert "VIVENTIUM_WEB_SEARCH_ENABLED=true" in runtime_env
    assert "SEARXNG_INSTANCE_URL=http://localhost:8082" in runtime_env
    assert "FIRECRAWL_API_KEY=viventium-local-firecrawl-access" in runtime_env
    assert librechat_yaml["webSearch"]["searchProvider"] == "searxng"
    assert librechat_yaml["webSearch"]["scraperProvider"] == "firecrawl"


def test_config_compiler_supports_serper_and_firecrawl_api_web_search(tmp_path: Path) -> None:
    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "log_level": "info",
            "profile": "isolated",
            "call_session_secret": {"secret_value": "call-session-test"},
        },
        "llm": {
            "activation": {
                "provider": "groq",
                "auth_mode": "api_key",
                "secret_value": "groq-test",
            },
            "primary": {
                "provider": "openai",
                "auth_mode": "api_key",
                "secret_value": "openai-test",
            },
            "secondary": {"provider": "none", "auth_mode": "disabled"},
            "extra_provider_keys": {},
        },
        "voice": {"mode": "disabled", "stt_provider": "whisper_local", "tts_provider": "browser"},
        "integrations": {
            "web_search": {
                "enabled": True,
                "search_provider": "serper",
                "serper_api_key": {"secret_value": "serper-test"},
                "scraper_provider": "firecrawl_api",
                "firecrawl_api_key": {"secret_value": "firecrawl-test"},
                "firecrawl_api_url": "https://api.firecrawl.dev",
            },
            "telegram": {"enabled": False},
            "google_workspace": {"enabled": False},
            "ms365": {"enabled": False},
            "skyvern": {"enabled": False},
            "openclaw": {"enabled": False},
        },
    }
    config_path = tmp_path / "config.yaml"
    output_dir = tmp_path / "out"
    write_config(config_path, config)

    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/viventium/config_compiler.py"),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        cwd=REPO_ROOT,
    )

    runtime_env = (output_dir / "runtime.env").read_text(encoding="utf-8")
    librechat_yaml = yaml.safe_load((output_dir / "librechat.yaml").read_text(encoding="utf-8"))

    assert "START_SEARXNG=false" in runtime_env
    assert "START_FIRECRAWL=false" in runtime_env
    assert "VIVENTIUM_WEB_SEARCH_ENABLED=true" in runtime_env
    assert "SERPER_API_KEY=serper-test" in runtime_env
    assert "FIRECRAWL_API_KEY=firecrawl-test" in runtime_env
    assert "FIRECRAWL_API_URL=https://api.firecrawl.dev" in runtime_env
    assert "SEARXNG_INSTANCE_URL=" not in runtime_env
    assert librechat_yaml["webSearch"]["searchProvider"] == "serper"
    assert librechat_yaml["webSearch"]["scraperProvider"] == "firecrawl"


def test_config_compiler_runtime_port_overrides(tmp_path: Path) -> None:
    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "log_level": "info",
            "profile": "isolated",
            "call_session_secret": {"secret_value": "call-secret-ports"},
            "ports": {
                "lc_api_port": 5180,
                "lc_frontend_port": 5190,
                "playground_port": 5300,
                "mongo_port": 29117,
                "meili_port": 7901,
                "google_mcp_port": 9111,
                "scheduling_mcp_port": 8110,
                "rag_api_port": 9310,
                "skyvern_api_port": 9400,
                "skyvern_ui_port": 9480,
                "livekit_http_port": 8988,
                "livekit_tcp_port": 8989,
                "livekit_udp_port": 8990,
            },
        },
        "llm": {
            "activation": {
                "provider": "groq",
                "auth_mode": "api_key",
                "secret_value": "groq-test",
            },
            "primary": {
                "provider": "openai",
                "auth_mode": "api_key",
                "secret_value": "openai-test",
            },
            "secondary": {"provider": "none", "auth_mode": "disabled"},
            "extra_provider_keys": {},
        },
        "voice": {"mode": "disabled", "stt_provider": "whisper_local", "tts_provider": "browser"},
        "integrations": {
            "telegram": {"enabled": False},
            "google_workspace": {"enabled": True, "client_id": "google-client-id"},
            "ms365": {"enabled": True, "client_id": "ms365-client-id"},
            "skyvern": {"enabled": False},
            "openclaw": {"enabled": False},
        },
    }
    config_path = tmp_path / "config.yaml"
    output_dir = tmp_path / "out"
    write_config(config_path, config)

    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/viventium/config_compiler.py"),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        cwd=REPO_ROOT,
    )

    runtime_env = (output_dir / "runtime.env").read_text(encoding="utf-8")
    librechat_yaml = yaml.safe_load((output_dir / "librechat.yaml").read_text(encoding="utf-8"))

    assert "VIVENTIUM_LC_API_PORT=5180" in runtime_env
    assert "VIVENTIUM_LC_FRONTEND_PORT=5190" in runtime_env
    assert "VIVENTIUM_PLAYGROUND_PORT=5300" in runtime_env
    assert "VIVENTIUM_PLAYGROUND_URL=http://localhost:5300" in runtime_env
    assert "VIVENTIUM_LOCAL_MONGO_PORT=29117" in runtime_env
    assert "VIVENTIUM_LOCAL_MEILI_PORT=7901" in runtime_env
    assert "LIVEKIT_HTTP_PORT=8988" in runtime_env
    assert "LIVEKIT_TCP_PORT=8989" in runtime_env
    assert "LIVEKIT_UDP_PORT=8990" in runtime_env
    assert "SCHEDULING_MCP_URL=http://localhost:8110/mcp" in runtime_env
    assert "GOOGLE_WORKSPACE_MCP_URL=http://localhost:9111/mcp" in runtime_env
    assert librechat_yaml["mcpServers"]["google_workspace"]["oauth"]["redirect_uri"] == (
        "http://localhost:5180/api/mcp/google_workspace/oauth/callback"
    )
    assert librechat_yaml["mcpServers"]["ms-365"]["oauth"]["redirect_uri"] == (
        "http://localhost:5180/api/mcp/ms-365/oauth/callback"
    )


def test_config_compiler_imports_legacy_private_env_passthrough(tmp_path: Path) -> None:
    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "log_level": "info",
            "profile": "isolated",
            "call_session_secret": {"secret_value": "call-secret"},
            "extra_env": {
                "AZURE_OPENAI_API_INSTANCE_NAME": "explicit-instance",
            },
        },
        "llm": {
            "activation": {
                "provider": "groq",
                "auth_mode": "api_key",
                "secret_value": "groq-test",
            },
            "primary": {
                "provider": "openai",
                "auth_mode": "api_key",
                "secret_value": "openai-test",
            },
            "secondary": {"provider": "none", "auth_mode": "disabled"},
            "extra_provider_keys": {},
        },
        "voice": {"mode": "disabled", "stt_provider": "whisper_local", "tts_provider": "browser"},
        "integrations": {
            "telegram": {"enabled": False},
            "google_workspace": {"enabled": False},
            "ms365": {"enabled": False},
            "skyvern": {"enabled": False},
            "openclaw": {"enabled": False},
        },
    }
    config_path = tmp_path / "config.yaml"
    output_dir = tmp_path / "out"
    canonical_env = tmp_path / "librechat.env"
    write_config(config_path, config)
    canonical_env.write_text(
        "\n".join(
            [
                "AZURE_AI_FOUNDRY_API_KEY=foundry-test",
                "AZURE_OPENAI_API_INSTANCE_NAME=canonical-instance",
                "AZURE_OPENAI_API_KEY=azure-openai-test",
                "VIVENTIUM_FOUNDRY_ANTHROPIC_REVERSE_PROXY=https://example.invalid/anthropic/v1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    env = dict(os.environ)
    env["VIVENTIUM_LIBRECHAT_CANONICAL_ENV_FILE"] = str(canonical_env)

    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/viventium/config_compiler.py"),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )

    runtime_env = (output_dir / "runtime.env").read_text(encoding="utf-8")
    assert "AZURE_AI_FOUNDRY_API_KEY=foundry-test" in runtime_env
    assert "AZURE_OPENAI_API_KEY=azure-openai-test" in runtime_env
    assert "VIVENTIUM_FOUNDRY_ANTHROPIC_REVERSE_PROXY=https://example.invalid/anthropic/v1" in runtime_env
    assert "AZURE_OPENAI_API_INSTANCE_NAME=explicit-instance" in runtime_env


def test_config_compiler_local_voice_browser_maps_to_stable_gateway_tts(tmp_path: Path) -> None:
    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "log_level": "info",
            "profile": "compat",
            "call_session_secret": {"secret_value": "call-secret-local"},
        },
        "llm": {
            "activation": {
                "provider": "groq",
                "auth_mode": "api_key",
                "secret_value": "groq-test",
            },
            "primary": {
                "provider": "openai",
                "auth_mode": "api_key",
                "secret_value": "openai-test",
            },
            "secondary": {"provider": "none", "auth_mode": "disabled"},
            "extra_provider_keys": {},
        },
        "voice": {
            "mode": "local",
            "stt_provider": "whisper_local",
            "tts_provider": "browser",
            "fast_llm_provider": "x_ai",
        },
        "integrations": {
            "telegram": {"enabled": False},
            "google_workspace": {"enabled": False},
            "ms365": {"enabled": False},
            "skyvern": {"enabled": False},
            "openclaw": {"enabled": False},
        },
    }
    config_path = tmp_path / "config.yaml"
    output_dir = tmp_path / "out"
    write_config(config_path, config)

    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/viventium/config_compiler.py"),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        cwd=REPO_ROOT,
    )

    runtime_env = (output_dir / "runtime.env").read_text(encoding="utf-8")

    assert "VIVENTIUM_TTS_PROVIDER=openai" in runtime_env
    assert "TTS_PROVIDER_PRIMARY=openai" in runtime_env
    assert "VIVENTIUM_OPENAI_TTS_MODEL=gpt-4o-mini-tts" in runtime_env
    assert "VIVENTIUM_OPENAI_TTS_VOICE=coral" in runtime_env
    assert "VIVENTIUM_OPENAI_TTS_INSTRUCTIONS=" in runtime_env
    assert "VIVENTIUM_OPENAI_TTS_SPEED=1.12" in runtime_env
    assert "TTS_MODEL=gpt-4o-mini-tts" in runtime_env


def test_config_compiler_local_voice_local_automatic_uses_local_tts_when_supported(tmp_path: Path) -> None:
    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "log_level": "info",
            "profile": "compat",
            "call_session_secret": {"secret_value": "call-secret-local-auto"},
        },
        "llm": {
            "activation": {
                "provider": "groq",
                "auth_mode": "api_key",
                "secret_value": "groq-test",
            },
            "primary": {
                "provider": "openai",
                "auth_mode": "api_key",
                "secret_value": "openai-test",
            },
            "secondary": {"provider": "none", "auth_mode": "disabled"},
            "extra_provider_keys": {},
        },
        "voice": {
            "mode": "local",
            "stt_provider": "whisper_local",
            "tts_provider": "local_automatic",
            "fast_llm_provider": "x_ai",
        },
        "integrations": {
            "telegram": {"enabled": False},
            "google_workspace": {"enabled": False},
            "ms365": {"enabled": False},
            "skyvern": {"enabled": False},
            "openclaw": {"enabled": False},
        },
    }
    config_path = tmp_path / "config.yaml"
    output_dir = tmp_path / "out"
    write_config(config_path, config)

    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/viventium/config_compiler.py"),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        cwd=REPO_ROOT,
    )

    runtime_env = (output_dir / "runtime.env").read_text(encoding="utf-8")

    if platform.system() == "Darwin" and platform.machine().lower() in {"arm64", "aarch64"}:
        assert "VIVENTIUM_TTS_PROVIDER=local_chatterbox_turbo_mlx_8bit" in runtime_env
        assert "VIVENTIUM_TTS_PROVIDER_FALLBACK=openai" in runtime_env
        assert "TTS_PROVIDER_PRIMARY=local_chatterbox_turbo_mlx_8bit" in runtime_env
        assert "TTS_PROVIDER_FALLBACK=openai" in runtime_env
    else:
        assert "VIVENTIUM_TTS_PROVIDER=openai" in runtime_env
        assert "TTS_PROVIDER_PRIMARY=openai" in runtime_env
    assert "VIVENTIUM_OPENAI_TTS_MODEL=gpt-4o-mini-tts" in runtime_env
    assert "VIVENTIUM_OPENAI_TTS_VOICE=coral" in runtime_env
    assert "VIVENTIUM_OPENAI_TTS_INSTRUCTIONS=" in runtime_env
    assert "VIVENTIUM_OPENAI_TTS_SPEED=1.12" in runtime_env
    assert "TTS_MODEL=gpt-4o-mini-tts" in runtime_env


def test_config_compiler_allows_custom_openai_tts_voice_and_speed(tmp_path: Path) -> None:
    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "log_level": "info",
            "profile": "compat",
            "call_session_secret": {"secret_value": "call-secret-local-custom-openai-tts"},
        },
        "llm": {
            "activation": {
                "provider": "groq",
                "auth_mode": "api_key",
                "secret_value": "groq-test",
            },
            "primary": {
                "provider": "openai",
                "auth_mode": "api_key",
                "secret_value": "openai-test",
            },
            "secondary": {"provider": "none", "auth_mode": "disabled"},
            "extra_provider_keys": {},
        },
        "voice": {
            "mode": "local",
            "stt_provider": "whisper_local",
            "tts_provider": "browser",
            "fast_llm_provider": "x_ai",
            "tts": {
                "voice": "alloy",
                "speed": 1.22,
            },
        },
        "integrations": {
            "telegram": {"enabled": False},
            "google_workspace": {"enabled": False},
            "ms365": {"enabled": False},
            "skyvern": {"enabled": False},
            "openclaw": {"enabled": False},
        },
    }
    config_path = tmp_path / "config.yaml"
    output_dir = tmp_path / "out"
    write_config(config_path, config)

    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/viventium/config_compiler.py"),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        cwd=REPO_ROOT,
    )

    runtime_env = (output_dir / "runtime.env").read_text(encoding="utf-8")

    assert "VIVENTIUM_OPENAI_TTS_VOICE=alloy" in runtime_env
    assert "VIVENTIUM_OPENAI_TTS_SPEED=1.22" in runtime_env


def test_config_compiler_explicit_local_chatterbox_provider_falls_back_on_unsupported_hosts(
    tmp_path: Path,
) -> None:
    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "log_level": "info",
            "profile": "compat",
            "call_session_secret": {"secret_value": "call-secret-explicit-local-chatterbox"},
        },
        "llm": {
            "activation": {
                "provider": "groq",
                "auth_mode": "api_key",
                "secret_value": "groq-test",
            },
            "primary": {
                "provider": "openai",
                "auth_mode": "api_key",
                "secret_value": "openai-test",
            },
            "secondary": {"provider": "none", "auth_mode": "disabled"},
            "extra_provider_keys": {},
        },
        "voice": {
            "mode": "local",
            "stt_provider": "whisper_local",
            "tts_provider": "local_chatterbox_turbo_mlx_8bit",
            "tts_provider_fallback": "openai",
            "fast_llm_provider": "x_ai",
        },
        "integrations": {
            "telegram": {"enabled": False},
            "google_workspace": {"enabled": False},
            "ms365": {"enabled": False},
            "skyvern": {"enabled": False},
            "openclaw": {"enabled": False},
        },
    }
    config_path = tmp_path / "config.yaml"
    output_dir = tmp_path / "out"
    write_config(config_path, config)

    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/viventium/config_compiler.py"),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        cwd=REPO_ROOT,
    )

    runtime_env = (output_dir / "runtime.env").read_text(encoding="utf-8")

    if platform.system() == "Darwin" and platform.machine().lower() in {"arm64", "aarch64"}:
        assert "VIVENTIUM_TTS_PROVIDER=local_chatterbox_turbo_mlx_8bit" in runtime_env
        assert "VIVENTIUM_TTS_PROVIDER_FALLBACK=openai" in runtime_env
    else:
        assert "VIVENTIUM_TTS_PROVIDER=openai" in runtime_env
        assert "TTS_PROVIDER_PRIMARY=openai" in runtime_env
        assert "VIVENTIUM_TTS_PROVIDER_FALLBACK=" not in runtime_env


def test_config_compiler_resolves_string_telegram_enablement_consistently(tmp_path: Path) -> None:
    base_config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "log_level": "info",
            "profile": "isolated",
            "call_session_secret": {"secret_value": "call-secret"},
        },
        "llm": {
            "activation": {
                "provider": "groq",
                "auth_mode": "api_key",
                "secret_value": "groq-test",
            },
            "primary": {
                "provider": "openai",
                "auth_mode": "api_key",
                "secret_value": "openai-test",
            },
            "secondary": {"provider": "none", "auth_mode": "disabled"},
            "extra_provider_keys": {},
        },
        "voice": {"mode": "disabled", "stt_provider": "whisper_local", "tts_provider": "browser"},
        "integrations": {
            "telegram": {"enabled": "false", "secret_value": VALID_TELEGRAM_TOKEN},
            "google_workspace": {"enabled": False},
            "ms365": {"enabled": False},
            "skyvern": {"enabled": False},
            "openclaw": {"enabled": False},
        },
    }

    config_false = tmp_path / "config-false.yaml"
    output_false = tmp_path / "out-false"
    write_config(config_false, base_config)
    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/viventium/config_compiler.py"),
            "--config",
            str(config_false),
            "--output-dir",
            str(output_false),
        ],
        check=True,
        cwd=REPO_ROOT,
    )
    runtime_env_false = (output_false / "runtime.env").read_text(encoding="utf-8")
    assert "START_TELEGRAM=false" in runtime_env_false
    assert f"BOT_TOKEN={VALID_TELEGRAM_TOKEN}" not in runtime_env_false

    base_config["integrations"]["telegram"]["enabled"] = "true"
    config_true = tmp_path / "config-true.yaml"
    output_true = tmp_path / "out-true"
    write_config(config_true, base_config)
    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/viventium/config_compiler.py"),
            "--config",
            str(config_true),
            "--output-dir",
            str(output_true),
        ],
        check=True,
        cwd=REPO_ROOT,
    )
    runtime_env_true = (output_true / "runtime.env").read_text(encoding="utf-8")
    assert "START_TELEGRAM=true" in runtime_env_true
    assert f"BOT_TOKEN={VALID_TELEGRAM_TOKEN}" in runtime_env_true

from __future__ import annotations

import copy
import json
import os
import platform
import subprocess
import sys
import importlib.util
import stat
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
START_SCRIPT = REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh"


def write_config(path: Path, payload: dict) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def minimal_compile_config() -> dict:
    return {
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


def load_source_of_truth_agents_bundle() -> dict:
    return config_compiler.resolve_source_prompt_refs(
        yaml.safe_load(SOURCE_OF_TRUTH_AGENTS_BUNDLE.read_text(encoding="utf-8"))
    )


def load_source_of_truth_librechat_yaml() -> dict:
    return config_compiler.resolve_source_prompt_refs(
        yaml.safe_load(SOURCE_OF_TRUTH_LIBRECHAT_YAML.read_text(encoding="utf-8"))
    )


def test_source_prompt_refs_fail_closed_when_registry_is_missing() -> None:
    with pytest.raises(SystemExit, match="source YAML contains promptRef entries"):
        config_compiler.resolve_source_prompt_refs({"instructions": {"promptRef": "main.identity"}}, {})


def test_source_prompt_refs_allow_plain_values_when_registry_is_missing() -> None:
    assert config_compiler.resolve_source_prompt_refs({"instructions": "plain"}, {}) == {
        "instructions": "plain"
    }


def test_runtime_env_defaults_to_modern_playground_and_keeps_classic_opt_in() -> None:
    config = minimal_compile_config()
    assignments = config_compiler.build_agent_assignments(config)
    env = config_compiler.render_runtime_env(config, assignments)

    assert env["PLAYGROUND_VARIANT"] == "modern"
    assert env["VIVENTIUM_PLAYGROUND_VARIANT"] == "modern"

    classic_config = copy.deepcopy(config)
    classic_config["runtime"]["playground_variant"] = "classic"
    classic_env = config_compiler.render_runtime_env(
        classic_config,
        config_compiler.build_agent_assignments(classic_config),
    )

    assert classic_env["PLAYGROUND_VARIANT"] == "classic"
    assert classic_env["VIVENTIUM_PLAYGROUND_VARIANT"] == "classic"

    invalid_config = copy.deepcopy(config)
    invalid_config["runtime"]["playground_variant"] = "old-playground"
    invalid_env = config_compiler.render_runtime_env(
        invalid_config,
        config_compiler.build_agent_assignments(invalid_config),
    )

    assert invalid_env["PLAYGROUND_VARIANT"] == "modern"
    assert invalid_env["VIVENTIUM_PLAYGROUND_VARIANT"] == "modern"


def test_prompt_workbench_sidecar_compiles_as_explicit_runtime_opt_in() -> None:
    config = minimal_compile_config()
    disabled_env = config_compiler.render_runtime_env(config, config_compiler.build_agent_assignments(config))

    assert disabled_env["VIVENTIUM_PROMPT_WORKBENCH_ENABLED"] == "false"
    assert disabled_env["START_PROMPT_WORKBENCH"] == "false"

    config["runtime"]["prompt_workbench"] = {
        "enabled": True,
        "seed_nightly": {"enabled": True, "active": True, "executor": "glasshive_host"},
    }
    enabled_env = config_compiler.render_runtime_env(config, config_compiler.build_agent_assignments(config))

    assert enabled_env["VIVENTIUM_PROMPT_WORKBENCH_ENABLED"] == "true"
    assert enabled_env["START_PROMPT_WORKBENCH"] == "true"
    assert enabled_env["VIVENTIUM_PROMPT_WORKBENCH_SEED_NIGHTLY_ENABLED"] == "true"
    assert enabled_env["VIVENTIUM_PROMPT_WORKBENCH_SEED_NIGHTLY_ACTIVE"] == "true"
    assert enabled_env["VIVENTIUM_PROMPT_WORKBENCH_SEED_NIGHTLY_EXECUTOR"] == "glasshive_host"


def test_memory_hardening_explicit_provider_controls_cli_provider() -> None:
    config = minimal_compile_config()
    config["runtime"]["memory_hardening"] = {"enabled": True, "provider": "anthropic"}

    env = config_compiler.render_runtime_env(config, config_compiler.build_agent_assignments(config))

    assert env["VIVENTIUM_MEMORY_HARDENING_ENABLED"] == "true"
    assert env["VIVENTIUM_MEMORY_HARDENING_CONFIGURED_PROVIDER"] == "anthropic"
    assert env["VIVENTIUM_MEMORY_HARDENING_PROVIDER"] == "anthropic"


def test_livrechat_openid_auth_compiles_env_yaml_and_service_env(tmp_path: Path) -> None:
    config = minimal_compile_config()
    config["runtime"]["auth"] = {
        "allow_email_login": False,
        "allow_registration": False,
        "openid": {
            "enabled": True,
            "client_id": "entra-client-id",
            "client_secret": {"secret_value": "entra-client-secret"},
            "issuer": "https://login.microsoftonline.com/tenant/v2.0/",
            "session_secret": {"secret_value": "openid-session-secret"},
            "scope": "openid profile email",
            "callback_url": "/oauth/openid/callback",
            "button_label": "Continue with Example Entra ID",
            "use_pkce": True,
            "email_claim": "preferred_username",
        },
    }

    assignments = config_compiler.build_agent_assignments(config)
    env = config_compiler.render_runtime_env(config, assignments)
    librechat_yaml = yaml.safe_load(config_compiler.render_librechat_yaml(config, assignments, env))

    assert env["ALLOW_SOCIAL_LOGIN"] == "true"
    assert env["ALLOW_EMAIL_LOGIN"] == "false"
    assert env["OPENID_CLIENT_ID"] == "entra-client-id"
    assert env["OPENID_CLIENT_SECRET"] == "entra-client-secret"
    assert env["OPENID_ISSUER"] == "https://login.microsoftonline.com/tenant/v2.0"
    assert env["OPENID_SESSION_SECRET"] == "openid-session-secret"
    assert env["OPENID_USE_PKCE"] == "true"
    assert env["OPENID_EMAIL_CLAIM"] == "preferred_username"
    assert librechat_yaml["registration"]["socialLogins"] == ["openid"]

    config_compiler.render_service_envs(tmp_path, env)
    service_env = (tmp_path / "service-env" / "librechat.env").read_text(encoding="utf-8")
    assert "OPENID_CLIENT_ID=entra-client-id" in service_env
    assert "OPENID_CLIENT_SECRET=entra-client-secret" in service_env
    assert "OPENID_SESSION_SECRET=openid-session-secret" in service_env
    assert "ALLOW_EMAIL_LOGIN=false" in service_env


def test_livrechat_openid_auth_fails_closed_when_enabled_without_secret() -> None:
    config = minimal_compile_config()
    config["runtime"]["auth"] = {
        "openid": {
            "enabled": True,
            "client_id": "entra-client-id",
            "issuer": "https://login.microsoftonline.com/tenant/v2.0",
            "session_secret": {"secret_value": "openid-session-secret"},
        },
    }

    with pytest.raises(SystemExit, match="runtime.auth.openid.enabled requires"):
        config_compiler.render_runtime_env(config, config_compiler.build_agent_assignments(config))


def test_launcher_treats_classic_playground_as_explicit_opt_in_only() -> None:
    script = START_SCRIPT.read_text(encoding="utf-8")

    assert 'PLAYGROUND_VARIANT="${PLAYGROUND_VARIANT:-modern}"' in script
    assert 'PLAYGROUND_VARIANT="$(normalize_cli_arg "$PLAYGROUND_VARIANT" | tr' in script
    assert 'if [[ "$PLAYGROUND_VARIANT" != "classic" ]]; then' in script
    assert 'PLAYGROUND_VARIANT="modern"' in script
    assert '--classic-playground) PLAYGROUND_VARIANT="classic"; shift ;;' in script


def test_launcher_starts_prompt_workbench_only_when_enabled_and_without_token_logs() -> None:
    script = START_SCRIPT.read_text(encoding="utf-8")

    assert "--skip-prompt-workbench" in script
    assert 'START_PROMPT_WORKBENCH="${START_PROMPT_WORKBENCH:-${VIVENTIUM_PROMPT_WORKBENCH_ENABLED:-false}}"' in script
    assert "start_prompt_workbench_sidecar" in script
    assert "start_prompt_workbench_watchdog" in script
    assert "stop_prompt_workbench_if_managed" in script
    assert "prompt_workbench_user_stopped" in script
    assert "VIVENTIUM_PROMPT_WORKBENCH_MANAGED_BY_STACK=1" in script
    assert '"$VIVENTIUM_CORE_DIR/bin/viventium" prompt-workbench start' in script
    assert ">/dev/null 2>>\"$PROMPT_WORKBENCH_WATCHDOG_LOG_FILE\"" in script
    assert "bin/viventium prompt-workbench open" in script


def test_direct_launcher_regenerates_canonical_runtime_before_loading_env() -> None:
    script = START_SCRIPT.read_text(encoding="utf-8")

    assert "regenerate_canonical_runtime_env_if_needed" in script
    assert 'VIVENTIUM_CANONICAL_ENV_LOCK_EXISTING_KEYS:-}" == "1"' in script
    assert 'VIVENTIUM_LIBRECHAT_SOURCE_PHASE="compile"' in script
    assert 'VIVENTIUM_LIBRECHAT_SOURCE_OF_TRUTH=""' in script
    assert '"$PYTHON_BIN" "$compiler" --config "$canonical_config_file" --output-dir "$canonical_runtime_dir"' in script
    assert script.index("regenerate_canonical_runtime_env_if_needed\n# === VIVENTIUM END ===") < script.index(
        "# Load .env first, then .env.local"
    )


def test_launcher_keeps_glasshive_state_under_runtime_state_root() -> None:
    script = START_SCRIPT.read_text(encoding="utf-8")
    start_index = script.index("start_glasshive() {")
    function_body = script[start_index : script.index("start_ms365_mcp() {", start_index)]

    assert 'local glasshive_state_dir="${GLASSHIVE_STATE_DIR:-$VIVENTIUM_STATE_ROOT/glasshive}"' in function_body
    assert 'export GLASSHIVE_STATE_DIR="$glasshive_state_dir"' in function_body
    assert 'export WPR_DB_PATH="${WPR_DB_PATH:-$glasshive_state_dir/runtime_phase1.db}"' in function_body
    assert function_body.index('export WPR_DB_PATH="${WPR_DB_PATH:-$glasshive_state_dir/runtime_phase1.db}"') < function_body.index(
        "uv run uvicorn workers_projects_runtime.api:app"
    )


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


XAI_CURRENT_DEFAULT_MODELS = [
    "grok-4.3",
    "grok-4.20-non-reasoning",
    "grok-4.20-multi-agent-0309",
    "grok-4.20-0309-reasoning",
]

XAI_RETIRED_MODEL_IDS = {
    "grok-4-1-fast-reasoning",
    "grok-4-1-fast-non-reasoning",
    "grok-4-fast-reasoning",
    "grok-4-fast-non-reasoning",
    "grok-4-0709",
    "grok-code-fast-1",
    "grok-3",
    "grok-imagine-image-pro",
}


def custom_endpoint(endpoints: list[dict], name: str) -> dict:
    for endpoint in endpoints:
        if endpoint.get("name") == name:
            return endpoint
    raise AssertionError(f"missing custom endpoint {name!r}")


def test_memory_hardening_rejects_non_launch_ready_openai_model() -> None:
    with pytest.raises(SystemExit, match="openai_model must stay in launch-ready"):
        config_compiler.resolve_memory_hardening_settings(
            {
                "runtime": {
                    "memory_hardening": {
                        "openai_model": "gpt-5.4",
                    }
                }
            }
        )


def test_build_custom_endpoints_xai_defaults_to_grok_43() -> None:
    xai = custom_endpoint(config_compiler.build_custom_endpoints(), "xai")
    models = xai["models"]["default"]

    assert models[:4] == XAI_CURRENT_DEFAULT_MODELS
    assert not any("experimental-beta-0304" in model for model in models)
    assert xai["titleModel"] == "grok-4.3"
    assert xai["summaryModel"] == "grok-4.3"
    assert xai["titleModel"] not in XAI_RETIRED_MODEL_IDS
    assert xai["summaryModel"] not in XAI_RETIRED_MODEL_IDS


def test_source_of_truth_candidates_reject_generated_app_support_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_support_root = tmp_path / "Library" / "Application Support" / "Viventium"
    generated_source = app_support_root / "runtime" / "local.librechat.yaml"
    generated_source.parent.mkdir(parents=True)
    generated_source.write_text("version: test\n", encoding="utf-8")
    monkeypatch.setattr(config_compiler, "APP_SUPPORT_VIVENTIUM_DIR", app_support_root)
    monkeypatch.setattr(config_compiler, "SOURCE_OF_TRUTH_LIBRECHAT_YAML", tmp_path / "missing.yaml")
    monkeypatch.setenv("VIVENTIUM_LIBRECHAT_SOURCE_OF_TRUTH", str(generated_source))

    with pytest.raises(SystemExit, match="Generated App Support runtime files"):
        config_compiler.resolve_source_of_truth_librechat_yaml_candidates()


def test_prompt_bundle_drift_check_passes_for_matching_live_bundle(tmp_path: Path) -> None:
    live_bundle = tmp_path / "prompt-bundle.json"
    payload = config_compiler.build_prompt_bundle()
    live_bundle.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

    report = config_compiler.check_prompt_bundle_drift(live_bundle_path=live_bundle)

    assert report["status"] == "ok"
    assert report["drift_count"] == 0
    assert report["diff"] == {"added": [], "removed": [], "changed": []}


def test_prompt_bundle_candidates_include_local_state_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_root = tmp_path / "state" / "runtime" / "isolated"
    monkeypatch.setenv("VIVENTIUM_STATE_ROOT", str(state_root))

    candidates = config_compiler.default_live_prompt_bundle_candidates()

    assert (state_root / "prompt-bundle.json").resolve() in candidates


def test_prompt_bundle_candidates_include_runtime_profile_state_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_support_root = tmp_path / "app-support" / "Viventium"
    monkeypatch.setattr(config_compiler, "APP_SUPPORT_VIVENTIUM_DIR", app_support_root)
    monkeypatch.setenv("VIVENTIUM_RUNTIME_PROFILE", "qa-profile")

    candidates = config_compiler.default_live_prompt_bundle_candidates()

    assert (
        config_compiler.REPO_ROOT / ".viventium" / "runtime" / "qa-profile" / "prompt-bundle.json"
    ).resolve() in candidates
    assert (
        app_support_root / "state" / "runtime" / "qa-profile" / "prompt-bundle.json"
    ).resolve() in candidates


def test_prompt_bundle_drift_check_fails_closed_on_stale_live_bundle(tmp_path: Path) -> None:
    live_bundle = tmp_path / "prompt-bundle.json"
    payload = copy.deepcopy(config_compiler.build_prompt_bundle())
    first_prompt_id = sorted(payload["prompts"])[0]
    payload["prompts"][first_prompt_id]["content_hash"] = "stalehash"
    live_bundle.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

    report = config_compiler.check_prompt_bundle_drift(live_bundle_path=live_bundle)
    reviewed = config_compiler.check_prompt_bundle_drift(
        live_bundle_path=live_bundle,
        compare_reviewed=True,
    )

    assert report["status"] == "blocked"
    assert report["reason"] == "prompt_bundle_drift"
    assert first_prompt_id in report["diff"]["changed"]
    assert reviewed["status"] == "reviewed_drift"


def test_prompt_bundle_drift_check_blocks_when_no_live_bundle(tmp_path: Path) -> None:
    report = config_compiler.check_prompt_bundle_drift(live_bundle_path=tmp_path / "missing.json")

    assert report["status"] == "blocked"
    assert report["reason"] == "no_live_prompt_bundle_found"


def test_runtime_config_drift_check_passes_for_matching_live_config(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    write_config(config_path, minimal_compile_config())
    live_payload = config_compiler.render_current_librechat_config(
        config_path=config_path,
        output_dir=runtime_dir,
    )
    live_path = runtime_dir / "librechat.yaml"
    live_path.write_text(yaml.safe_dump(live_payload, sort_keys=False), encoding="utf-8")

    report = config_compiler.check_runtime_config_drift(
        config_path=config_path,
        live_runtime_config_path=live_path,
    )

    assert report["status"] == "ok"
    assert report["drift_count"] == 0
    assert report["diff"]["live_vs_compiled"] == {
        "added": [],
        "removed": [],
        "changed": [],
        "drift_count": 0,
    }
    assert "section_hashes" in report["compiled_now"]
    assert "mcpServers" in report["compiled_now"]["section_hashes"]


def test_runtime_config_drift_check_fails_closed_on_stale_live_config(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir()
    write_config(config_path, minimal_compile_config())
    live_payload = config_compiler.render_current_librechat_config(
        config_path=config_path,
        output_dir=runtime_dir,
    )
    live_payload["viventium"]["primaryProvider"] = "stale-provider"
    live_path = runtime_dir / "librechat.yaml"
    live_path.write_text(yaml.safe_dump(live_payload, sort_keys=False), encoding="utf-8")

    report = config_compiler.check_runtime_config_drift(
        config_path=config_path,
        live_runtime_config_path=live_path,
    )
    reviewed = config_compiler.check_runtime_config_drift(
        config_path=config_path,
        live_runtime_config_path=live_path,
        compare_reviewed=True,
    )

    assert report["status"] == "blocked"
    assert report["reason"] == "runtime_config_drift"
    assert "viventium" in report["diff"]["live_vs_compiled"]["changed"]
    assert reviewed["status"] == "reviewed_drift"


def test_runtime_config_drift_check_blocks_when_no_live_config(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    write_config(config_path, minimal_compile_config())

    report = config_compiler.check_runtime_config_drift(
        config_path=config_path,
        live_runtime_config_path=tmp_path / "missing-librechat.yaml",
    )

    assert report["status"] == "blocked"
    assert report["reason"] == "no_live_runtime_config_found"


def test_source_template_xai_endpoint_uses_current_stable_models() -> None:
    source = load_source_of_truth_librechat_yaml()
    xai = custom_endpoint(source["endpoints"]["custom"], "xai")
    models = xai["models"]["default"]

    assert models[:4] == XAI_CURRENT_DEFAULT_MODELS
    assert not any("experimental-beta-0304" in model for model in models)
    assert XAI_RETIRED_MODEL_IDS.isdisjoint(models)
    assert xai["titleModel"] == "grok-4.3"
    assert xai["summaryModel"] == "grok-4.3"


def test_rendered_librechat_yaml_xai_endpoint_uses_grok_43_after_source_template_merge() -> None:
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
    librechat_yaml = yaml.safe_load(config_compiler.render_librechat_yaml(config, assignments, env))
    xai = custom_endpoint(librechat_yaml["endpoints"]["custom"], "xai")
    models = xai["models"]["default"]

    assert models[:4] == XAI_CURRENT_DEFAULT_MODELS
    assert XAI_RETIRED_MODEL_IDS.isdisjoint({xai["titleModel"], xai["summaryModel"]})
    assert xai["titleModel"] == "grok-4.3"
    assert xai["summaryModel"] == "grok-4.3"


def test_rendered_librechat_yaml_exposes_grok_43_in_model_specs() -> None:
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
    librechat_yaml = yaml.safe_load(config_compiler.render_librechat_yaml(config, assignments, env))
    grok_spec = next(
        item for item in librechat_yaml["modelSpecs"]["list"] if item.get("name") == "grok-4.3"
    )

    assert grok_spec["label"] == "Grok 4.3"
    assert grok_spec["group"] == "xai"
    assert grok_spec["preset"]["endpoint"] == "xai"
    assert grok_spec["preset"]["model"] == "grok-4.3"


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
    librechat_env = (output_dir / "service-env" / "librechat.env").read_text(encoding="utf-8")
    librechat_yaml = yaml.safe_load((output_dir / "librechat.yaml").read_text(encoding="utf-8"))
    prompt_bundle = json.loads((output_dir / "prompt-bundle.json").read_text(encoding="utf-8"))
    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))

    assert "GROQ_API_KEY=groq-test" in runtime_env
    assert "OPENAI_API_KEY=openai-test" in runtime_env
    assert "VIVENTIUM_VOICE_ENABLED=false" in runtime_env
    assert "PLAYGROUND_VARIANT=modern" in runtime_env
    assert "VIVENTIUM_PLAYGROUND_VARIANT=modern" in runtime_env
    assert "VIVENTIUM_VOICE_FAST_LLM_PROVIDER=" not in runtime_env
    assert "VIVENTIUM_CALL_SESSION_SECRET=call-session-test" in runtime_env
    assert "VIVENTIUM_TELEGRAM_SECRET=call-session-test" in runtime_env
    assert "VIVENTIUM_CORTEX_FOLLOWUP_GRACE_S=30" in runtime_env
    assert "VIVENTIUM_VOICE_FOLLOWUP_GRACE_S=30" in runtime_env
    assert "VIVENTIUM_TELEGRAM_FOLLOWUP_GRACE_S=30" in runtime_env
    assert "VIVENTIUM_WEB_GLASSHIVE_TIMEOUT_S=600" in runtime_env
    assert "VIVENTIUM_VOICE_GLASSHIVE_TIMEOUT_S=600" in runtime_env
    assert "VIVENTIUM_TELEGRAM_GLASSHIVE_TIMEOUT_S=600" in runtime_env
    assert "VIVENTIUM_CORTEX_PHASE_A_NOTICE_MODE=any_activated_on_voice" in runtime_env
    assert "VIVENTIUM_CORTEX_PHASE_A_NOTICE_MODE=any_activated_on_voice" in librechat_env
    assert "VIVENTIUM_VOICE_BACKGROUND_AGENT_DETECTION_ASYNC=true" in librechat_env
    assert "VIVENTIUM_TEXT_BACKGROUND_AGENT_DETECTION_ASYNC=false" in librechat_env
    assert "VIVENTIUM_VOICE_PHASE_A_AWAIT_MS=690" in librechat_env
    assert "VIVENTIUM_TEXT_PHASE_A_AWAIT_MS=1300" in librechat_env
    assert "VIVENTIUM_VOICE_PHASE_A_ASYNC_ALLOW_TOOL_HOLD=true" in librechat_env
    assert "VIVENTIUM_VOICE_LOG_LATENCY=1" in librechat_env
    assert "VIVENTIUM_LIBRECHAT_ORIGIN=http://127.0.0.1:3180" in runtime_env
    assert "VIVENTIUM_TELEGRAM_AGENT_ID=agent_viventium_main_95aeb3" in runtime_env
    assert "VIVENTIUM_REMOTE_CALL_MODE=disabled" in runtime_env
    assert "VIVENTIUM_MAIN_AGENT_ID=agent_viventium_main_95aeb3" in runtime_env
    assert "VIVENTIUM_LOCAL_SUBSCRIPTION_AUTH=true" in runtime_env
    assert "VIVENTIUM_DEFAULT_CONVERSATION_RECALL=false" in runtime_env
    assert "VIVENTIUM_MEMORY_HARDENING_ENABLED=false" in runtime_env
    assert "VIVENTIUM_MEMORY_HARDENING_SCHEDULE='0 3 * * *'" in runtime_env
    assert "VIVENTIUM_MEMORY_HARDENING_LOOKBACK_DAYS=7" in runtime_env
    assert "VIVENTIUM_MEMORY_HARDENING_MIN_USER_IDLE_MINUTES=60" in runtime_env
    assert "VIVENTIUM_MEMORY_HARDENING_MAX_CHANGES_PER_USER=3" in runtime_env
    assert "VIVENTIUM_MEMORY_HARDENING_MAX_INPUT_CHARS=500000" in runtime_env
    assert "VIVENTIUM_MEMORY_HARDENING_REQUIRE_FULL_LOOKBACK=true" in runtime_env
    assert "VIVENTIUM_MEMORY_HARDENING_DRY_RUN_FIRST=true" in runtime_env
    assert "VIVENTIUM_MEMORY_HARDENING_MIN_APPLY_INTERVAL_SECONDS=300" in runtime_env
    assert "VIVENTIUM_MEMORY_HARDENING_PROVIDER_PROFILE=launch_ready_only" in runtime_env
    assert "VIVENTIUM_MEMORY_HARDENING_PROVIDER=openai" in runtime_env
    assert "VIVENTIUM_MEMORY_HARDENING_MODEL=gpt-5.5" in runtime_env
    assert "VIVENTIUM_MEMORY_HARDENING_EFFORT=xhigh" in runtime_env
    assert "VIVENTIUM_MEMORY_HARDENING_ANTHROPIC_MODEL=claude-opus-4-7" in runtime_env
    assert "VIVENTIUM_MEMORY_HARDENING_ANTHROPIC_EFFORT=xhigh" in runtime_env
    assert "VIVENTIUM_MEMORY_HARDENING_OPENAI_MODEL=gpt-5.5" in runtime_env
    assert "VIVENTIUM_MEMORY_HARDENING_OPENAI_REASONING_EFFORT=xhigh" in runtime_env
    assert "VIVENTIUM_MEMORY_TRANSCRIPTS_DIR=" in runtime_env
    assert "VIVENTIUM_MEMORY_TRANSCRIPTS_IGNORE_GLOBS=" in runtime_env
    assert "VIVENTIUM_MEMORY_TRANSCRIPTS_MAX_FILES_PER_RUN=20" in runtime_env
    assert "VIVENTIUM_MEMORY_TRANSCRIPTS_MIN_FILES_PER_RUN=5" in runtime_env
    assert "VIVENTIUM_MEMORY_TRANSCRIPTS_MAX_BATCHES_PER_INVOCATION=1" in runtime_env
    assert "VIVENTIUM_MEMORY_TRANSCRIPTS_MAX_CHARS_PER_FILE=500000" in runtime_env
    assert "VIVENTIUM_MEMORY_TRANSCRIPTS_SUMMARY_MAX_CHARS=32000" in runtime_env
    assert "VIVENTIUM_MEMORY_TRANSCRIPTS_STABLE_EVIDENCE_MAX_AGE_DAYS=90" in runtime_env
    assert f"VIVENTIUM_PROMPT_BUNDLE_PATH={output_dir / 'prompt-bundle.json'}" in runtime_env
    assert "VIVENTIUM_PROMPT_FRAME_FILE_LOG=0" in runtime_env
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
    assert "GLASSHIVE_OPERATOR_BASE_URL=" not in runtime_env
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
    assert "GROQ_API_KEY=groq-test" in runtime_env
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
    assert prompt_bundle["prompt_count"] >= 50
    assert "main.conscious_agent" in prompt_bundle["prompts"]
    assert prompt_bundle["prompts"]["main.identity"]["content_hash"]
    assert summary["prompt_registry"]["prompt_count"] == prompt_bundle["prompt_count"]
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
    assert librechat_yaml["endpoints"]["anthropic"]["titleModel"] == "claude-sonnet-4-5"
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
    app_support_root = tmp_path / "app-support" / "Viventium"
    codex_bin = tmp_path / "bin" / "codex"
    claude_bin = tmp_path / "bin" / "claude"
    codex_bin.parent.mkdir(parents=True)
    codex_bin.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    claude_bin.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    codex_bin.chmod(0o755)
    claude_bin.chmod(0o755)
    monkeypatch.setattr(config_compiler, "GLASSHIVE_RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(config_compiler, "APP_SUPPORT_VIVENTIUM_DIR", app_support_root)
    monkeypatch.setattr(
        config_compiler.shutil,
        "which",
        lambda name: str({"codex": codex_bin, "claude": claude_bin}.get(name, "")) or None,
    )

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
    assert "GLASSHIVE_OPERATOR_BASE_URL" not in disabled_env
    assert "GLASSHIVE_DEFAULT_LAUNCH_SURFACE" not in disabled_env
    assert "GLASSHIVE_SHOW_LIVE_TERMINAL_IN_DESKTOP" not in disabled_env
    assert "WPR_IDLE_DESKTOP_PRIME_BROWSER" not in disabled_env

    default_host_config = copy.deepcopy(base_config)
    default_host_config["integrations"]["glasshive"] = {"enabled": True}
    default_host_env = config_compiler.render_runtime_env(
        default_host_config,
        config_compiler.build_agent_assignments(default_host_config),
    )
    assert default_host_env["GLASSHIVE_HOST_WORKERS_ENABLED"] == "true"
    assert default_host_env["WPR_HOST_WORKSPACE_ROOT"] == "~/viventium"
    assert default_host_env["WPR_DEFAULT_EXECUTION_MODE"] == "host"

    disabled_host_config = copy.deepcopy(base_config)
    disabled_host_config["integrations"]["glasshive"] = {
        "enabled": True,
        "host_worker": {
            "enabled": False,
            "default_execution_mode": "host",
        },
    }
    disabled_host_env = config_compiler.render_runtime_env(
        disabled_host_config,
        config_compiler.build_agent_assignments(disabled_host_config),
    )
    assert disabled_host_env["GLASSHIVE_HOST_WORKERS_ENABLED"] == "false"
    assert disabled_host_env["WPR_DEFAULT_EXECUTION_MODE"] == "docker"
    disabled_host_mcp = config_compiler.build_mcp_servers(disabled_host_config, {"lc_api_port": 3080}, "agent-main")
    assert disabled_host_mcp["glasshive-workers-projects"]["serverInstructions"] is True

    enabled_config = copy.deepcopy(base_config)
    enabled_config["integrations"]["glasshive"] = {
        "enabled": True,
        "host_worker": {
            "enabled": True,
            "workspace_root": "~/viventium-workers",
            "default_execution_mode": "host",
            "mentions": {"codex": "@codex", "claude": "@claude", "openclaw": "@openclaw"},
            "destructive_confirmation": {"enabled": True},
            "advisory_reviewer": {"enabled": False, "mode": "review_final"},
            "prompt_visibility": {"enabled": True},
        },
    }
    enabled_env = config_compiler.render_runtime_env(enabled_config, config_compiler.build_agent_assignments(enabled_config))
    assert enabled_env["GLASSHIVE_DEFAULT_LAUNCH_SURFACE"] == "desktop"
    assert enabled_env["GLASSHIVE_OPERATOR_BASE_URL"] == "http://127.0.0.1:8780"
    assert enabled_env["GLASSHIVE_SHOW_LIVE_TERMINAL_IN_DESKTOP"] == "true"
    assert enabled_env["WPR_IDLE_DESKTOP_PRIME_BROWSER"] == "true"
    assert enabled_env["GLASSHIVE_HOST_WORKERS_ENABLED"] == "true"
    assert enabled_env["WPR_HOST_WORKSPACE_ROOT"] == "~/viventium-workers"
    assert enabled_env["WPR_DEFAULT_EXECUTION_MODE"] == "host"
    assert enabled_env["WPR_HOST_DESTRUCTIVE_CONFIRMATION"] == "true"
    assert enabled_env["WPR_HOST_MENTION_CODEX"] == "@codex"
    assert enabled_env["WPR_HOST_CODEX_CLI_AVAILABLE"] == "true"
    assert enabled_env["WPR_HOST_CLAUDE_CLI_AVAILABLE"] == "true"
    assert enabled_env["WPR_HOST_OPENCLAW_CLI_AVAILABLE"] == "false"
    assert enabled_env["WPR_CODEX_BIN"] == str(codex_bin)
    assert enabled_env["WPR_CLAUDE_CODE_BIN"] == str(claude_bin)
    assert "WPR_OPENCLAW_BIN" not in enabled_env
    assert enabled_env["WPR_DB_PATH"] == str(
        app_support_root / "state" / "runtime" / "isolated" / "glasshive" / "runtime_phase1.db"
    )
    assert enabled_env["WPR_LIBRECHAT_UPLOADS_ROOT"].endswith("viventium_v0_4/LibreChat/uploads")
    assert enabled_env["WPR_BOOTSTRAP_SOURCE_ROOTS"] == enabled_env["WPR_LIBRECHAT_UPLOADS_ROOT"]
    assert enabled_env["VIVENTIUM_GLASSHIVE_CALLBACK_URL"].endswith("/api/viventium/glasshive/callback")
    assert enabled_env["VIVENTIUM_GLASSHIVE_CALLBACK_SECRET"] == config_compiler.scoped_secret(
        "call-session-test", "glasshive-callback"
    )
    assert enabled_env["VIVENTIUM_GLASSHIVE_CALLBACK_SECRET"] != enabled_env["VIVENTIUM_CALL_SESSION_SECRET"]
    mcp_servers = config_compiler.build_mcp_servers(enabled_config, {"lc_api_port": 3080}, "agent-main")
    glasshive_headers = mcp_servers["glasshive-workers-projects"]["headers"]
    assert glasshive_headers["X-Viventium-Conversation-Id"] == "{{LIBRECHAT_BODY_CONVERSATIONID}}"
    assert glasshive_headers["X-Viventium-Parent-Message-Id"] == "{{LIBRECHAT_BODY_PARENTMESSAGEID}}"
    assert glasshive_headers["X-Viventium-Message-Id"] == "{{LIBRECHAT_BODY_MESSAGEID}}"
    assert glasshive_headers["X-Viventium-Surface"] == "{{LIBRECHAT_BODY_VIVENTIUMSURFACE}}"
    assert glasshive_headers["X-Viventium-Input-Mode"] == "{{LIBRECHAT_BODY_VIVENTIUMINPUTMODE}}"
    assert glasshive_headers["X-Viventium-Stream-Id"] == "{{LIBRECHAT_BODY_VIVENTIUMSTREAMID}}"
    assert glasshive_headers["X-Viventium-Telegram-Chat-Id"] == "{{LIBRECHAT_BODY_VIVENTIUMTELEGRAMCHATID}}"
    assert glasshive_headers["X-Viventium-Telegram-User-Id"] == "{{LIBRECHAT_BODY_VIVENTIUMTELEGRAMUSERID}}"
    assert glasshive_headers["X-Viventium-Telegram-Message-Id"] == "{{LIBRECHAT_BODY_VIVENTIUMTELEGRAMMESSAGEID}}"
    assert glasshive_headers["X-Viventium-Request-Files"] == "{{LIBRECHAT_BODY_FILES_JSON_B64}}"
    assert glasshive_headers["X-Viventium-Tool-Resources"] == "{{LIBRECHAT_BODY_TOOL_RESOURCES_JSON_B64}}"


def test_render_runtime_env_uses_codex_app_bundle_when_shell_path_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_dir = tmp_path / "runtime_phase1"
    runtime_dir.mkdir(parents=True)
    app_cli = tmp_path / "Codex.app" / "Contents" / "Resources" / "codex"
    app_cli.parent.mkdir(parents=True)
    app_cli.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    app_cli.chmod(0o755)
    monkeypatch.setattr(config_compiler, "GLASSHIVE_RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(config_compiler, "CODEX_APP_CLI", app_cli)
    monkeypatch.setattr(config_compiler.shutil, "which", lambda _name: None)

    config = minimal_compile_config()
    config["integrations"]["glasshive"] = {"enabled": True}

    env = config_compiler.render_runtime_env(config, config_compiler.build_agent_assignments(config))

    assert env["GLASSHIVE_HOST_WORKERS_ENABLED"] == "true"
    assert env["WPR_HOST_CODEX_CLI_AVAILABLE"] == "true"
    assert env["WPR_CODEX_BIN"] == str(app_cli)


def test_render_runtime_env_discovers_codex_app_bundle_from_user_app_search_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_dir = tmp_path / "runtime_phase1"
    runtime_dir.mkdir(parents=True)
    app_root = tmp_path / "Applications"
    app_cli = app_root / "Codex.app" / "Contents" / "Resources" / "codex"
    app_cli.parent.mkdir(parents=True)
    app_cli.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    app_cli.chmod(0o755)
    monkeypatch.setenv("VIVENTIUM_CODEX_APP_DIRS", str(app_root))
    monkeypatch.setattr(config_compiler, "GLASSHIVE_RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(config_compiler.shutil, "which", lambda _name: None)

    config = minimal_compile_config()
    config["integrations"]["glasshive"] = {"enabled": True}

    env = config_compiler.render_runtime_env(config, config_compiler.build_agent_assignments(config))

    assert env["GLASSHIVE_HOST_WORKERS_ENABLED"] == "true"
    assert env["WPR_HOST_CODEX_CLI_AVAILABLE"] == "true"
    assert env["WPR_CODEX_BIN"] == str(app_cli)


def test_glasshive_azure_enterprise_vm_docker_compiles_cloud_safe_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runtime_dir = tmp_path / "runtime_phase1"
    runtime_dir.mkdir(parents=True)
    monkeypatch.setattr(config_compiler, "GLASSHIVE_RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(config_compiler.shutil, "which", lambda _name: None)

    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "log_level": "info",
            "profile": "isolated",
            "call_session_secret": {"secret_value": "call-session-test"},
            "network": {"public_api_origin": "https://api.enterprise.example.com"},
            "personalization": {"default_conversation_recall": False},
            "extra_env": {
                "OPENAI_BASE_URL": "https://api.openai.example/v1",
                "ANTHROPIC_BASE_URL": "https://api.anthropic.example",
                "PORTKEY_API_KEY": {"secret_value": "portkey-test"},
                "PORTKEY_BASE_URL": "https://api.portkey.ai/v1",
                "PORTKEY_VIRTUAL_KEY": {"secret_value": "portkey-vk-test"},
            },
        },
        "llm": {
            "activation": {"provider": "groq", "auth_mode": "api_key", "secret_value": "groq-test"},
            "primary": {"provider": "openai", "auth_mode": "api_key", "secret_value": "openai-test"},
            "secondary": {"provider": "anthropic", "auth_mode": "api_key", "secret_value": "anthropic-test"},
            "extra_provider_keys": {"openai": "older-openai-test"},
            "model_overrides": {"openai": {"default": "gpt-5.2-chat"}},
        },
        "voice": {"mode": "disabled"},
        "integrations": {
            "telegram": {"enabled": False},
            "google_workspace": {"enabled": False},
            "ms365": {"enabled": False},
            "skyvern": {"enabled": False},
            "openclaw": {"enabled": False},
            "glasshive": {
                "enabled": True,
                "deployment_mode": "azure_enterprise_vm_docker",
                "mcp_url": "https://glasshive.enterprise.example.com/mcp",
                "operator_base_url": "https://glasshive-ui.enterprise.example.com",
                "enterprise": {
                    "artifact_base_url": "https://glasshive-api.enterprise.example.com",
                    "tenant_id": "tenant-alpha",
                    "uploads_root": "/mnt/librechat/uploads",
                    "bootstrap_source_roots": ["/mnt/librechat/uploads"],
                    "auth": {
                        "mode": "first_party_assertion",
                        "service_token": {"secret_value": "service-token-test"},
                    },
                    "idle": {"terminate_after_seconds": 900, "reaper_interval_seconds": 30},
                    "quotas": {
                        "max_active_workers_per_user": 2,
                        "max_active_workers_per_tenant": 8,
                        "max_workspaces_per_user": 15,
                        "max_workspaces_per_tenant": 60,
                    },
                    "provider_env": {"allowlist": ["OPENAI_API_KEY", "OPENAI_BASE_URL", "ANTHROPIC_API_KEY", "PORTKEY_API_KEY"]},
                    "artifact_download_max_bytes": 1048576,
                    "oauth": {
                        "enabled": True,
                        "authorization_url": "https://login.example.com/authorize",
                        "token_url": "https://login.example.com/token",
                        "client_id": "${GLASSHIVE_OAUTH_CLIENT_ID}",
                        "client_secret": "${GLASSHIVE_OAUTH_CLIENT_SECRET}",
                    },
                },
            },
        },
        "agents": {},
    }

    assignments = config_compiler.build_agent_assignments(config)
    env = config_compiler.render_runtime_env(config, assignments)

    assert env["GLASSHIVE_MCP_URL"] == "https://glasshive.enterprise.example.com/mcp"
    assert env["GLASSHIVE_OPERATOR_BASE_URL"] == "https://glasshive-ui.enterprise.example.com"
    assert env["GLASSHIVE_ARTIFACT_BASE_URL"] == "https://glasshive-api.enterprise.example.com"
    assert env["GLASSHIVE_ENTERPRISE_MODE"] == "true"
    assert env["GLASSHIVE_AUTH_MODE"] == "first_party_assertion"
    assert env["GLASSHIVE_ENTERPRISE_TENANT_ID"] == "tenant-alpha"
    assert env["GLASSHIVE_SIGNED_LINK_SECRET"] == config_compiler.scoped_secret(
        "call-session-test",
        "glasshive-signed-link:tenant-alpha",
    )
    assert env["GLASSHIVE_SIGNED_LINK_SECRET"] != env["WPR_API_TOKEN"]
    assert env["GLASSHIVE_HOST_WORKERS_ENABLED"] == "false"
    assert env["WPR_DEFAULT_EXECUTION_MODE"] == "docker"
    assert "WPR_DB_PATH" not in env
    assert env["WPR_API_TOKEN"] == "service-token-test"
    assert env["GLASSHIVE_MCP_SERVICE_TOKEN"] == "service-token-test"
    assert env["OPENAI_API_KEY"] == "openai-test"
    assert env["OPENAI_BASE_URL"] == "https://api.openai.example/v1"
    assert env["OPENAI_REVERSE_PROXY"] == "https://api.openai.example/v1"
    assert env["OPENAI_MODELS"] == "gpt-5.2-chat"
    assert env["WPR_MODEL_CODEX_CLI"] == "gpt-5.2-chat"
    assert env["WPR_MODEL_OPENCLAW_CODEX"] == "gpt-5.2-chat"
    assert env["WPR_OPENCLAW_USE_CUSTOM_PROVIDER"] == "1"
    assert env["WPR_OPENCLAW_WIRE_API"] == "openai-completions"
    assert env["ANTHROPIC_API_KEY"] == "anthropic-test"
    assert env["ANTHROPIC_BASE_URL"] == "https://api.anthropic.example"
    assert env["ANTHROPIC_REVERSE_PROXY"] == "https://api.anthropic.example"
    assert env["WPR_CLAUDE_CODE_USE_API_KEY"] == "1"
    assert env["PORTKEY_API_KEY"] == "portkey-test"
    assert env["PORTKEY_BASE_URL"] == "https://api.portkey.ai/v1"
    assert env["PORTKEY_VIRTUAL_KEY"] == "portkey-vk-test"
    assert env["VIVENTIUM_OPENAI_AUTH_MODE"] == "api_key"
    assert env["VIVENTIUM_ANTHROPIC_AUTH_MODE"] == "api_key"
    assert env["VIVENTIUM_ALLOW_RUNTIME_MODEL_OVERRIDES"] == "true"
    assert assignments["deep_research"] == ("openai", "gpt-5.2-chat")
    assert env["WPR_LIBRECHAT_UPLOADS_ROOT"] == "/mnt/librechat/uploads"
    assert env["WPR_BOOTSTRAP_SOURCE_ROOTS"] == "/mnt/librechat/uploads"
    assert env["GLASSHIVE_IDLE_TERMINATE_AFTER_S"] == "900"
    assert env["GLASSHIVE_IDLE_REAPER_INTERVAL_S"] == "30"
    assert env["GLASSHIVE_MAX_ACTIVE_WORKERS_PER_USER"] == "2"
    assert env["GLASSHIVE_MAX_ACTIVE_WORKERS_PER_TENANT"] == "8"
    assert env["GLASSHIVE_MAX_WORKSPACES_PER_USER"] == "15"
    assert env["GLASSHIVE_MAX_WORKSPACES_PER_TENANT"] == "60"
    assert env["GLASSHIVE_ARTIFACT_DOWNLOAD_MAX_BYTES"] == "1048576"
    assert env["VIVENTIUM_GLASSHIVE_CALLBACK_URL"] == "https://api.enterprise.example.com/api/viventium/glasshive/callback"

    servers = config_compiler.build_mcp_servers(config, {"lc_api_port": 3080}, "agent-main")
    glasshive = servers["glasshive-workers-projects"]
    assert glasshive["url"] == "${GLASSHIVE_MCP_URL}"
    assert glasshive["timeout"] == config_compiler.DEFAULT_GLASSHIVE_MCP_TRANSPORT_TIMEOUT_MS
    assert glasshive["timeout"] >= (
        config_compiler.DEFAULT_GLASSHIVE_MCP_BLOCKING_WAIT_MAX_SEC * 1000
        + config_compiler.DEFAULT_GLASSHIVE_MCP_TRANSPORT_TIMEOUT_BUFFER_SEC * 1000
    )
    assert "X-WPR-Token" not in glasshive["headers"]
    assert glasshive["headers"]["X-Viventium-Tenant-Id"] == "tenant-alpha"
    assert glasshive["headers"]["X-Viventium-User-Id"] == "{{LIBRECHAT_USER_ID}}"
    assert glasshive["headers"]["X-Viventium-User-Email"] == "{{LIBRECHAT_USER_EMAIL}}"
    assert glasshive["headers"]["X-Viventium-User-Role"] == "{{LIBRECHAT_USER_ROLE}}"
    assert glasshive["requiresOAuth"] is True
    assert glasshive["oauth"]["authorization_url"] == "https://login.example.com/authorize"
    assert glasshive["oauth"]["redirect_uri"] == (
        "https://api.enterprise.example.com/api/mcp/glasshive-workers-projects/oauth/callback"
    )
    librechat_yaml = yaml.safe_load(config_compiler.render_librechat_yaml(config, assignments, env))
    assert "glasshive.enterprise.example.com" in librechat_yaml["mcpSettings"]["allowedDomains"]
    assert "glasshive-ui.enterprise.example.com" in librechat_yaml["mcpSettings"]["allowedDomains"]
    assert "glasshive-api.enterprise.example.com" in librechat_yaml["mcpSettings"]["allowedDomains"]


def test_glasshive_azure_enterprise_local_simulation_compiles_matching_ports(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_dir = tmp_path / "runtime_phase1"
    runtime_dir.mkdir(parents=True)
    monkeypatch.setattr(config_compiler, "GLASSHIVE_RUNTIME_DIR", runtime_dir)

    config = minimal_compile_config()
    config["integrations"]["glasshive"] = {
        "enabled": True,
        "deployment_mode": "azure_enterprise_vm_docker",
        "mcp_url": "http://glasshive.localtest.me:8877/mcp",
        "operator_base_url": "http://glasshive.localtest.me:8875",
        "enterprise": {
            "tenant_id": "tenant-local-sim",
            "auth": {
                "mode": "first_party_assertion",
                "service_token": {"secret_value": "service-token-test"},
            },
        },
    }

    env = config_compiler.render_runtime_env(config, config_compiler.build_agent_assignments(config))

    assert env["GLASSHIVE_MCP_URL"] == "http://glasshive.localtest.me:8877/mcp"
    assert env["GLASSHIVE_OPERATOR_BASE_URL"] == "http://glasshive.localtest.me:8875"
    assert env["GLASSHIVE_MCP_PORT"] == "8877"
    assert env["GLASSHIVE_UI_PORT"] == "8875"
    assert env["GLASSHIVE_SIGNED_LINK_SECRET"] == config_compiler.scoped_secret(
        "call-session-test",
        "glasshive-signed-link:tenant-local-sim",
    )
    assert env["GLASSHIVE_SIGNED_LINK_SECRET"] != env["WPR_API_TOKEN"]


def test_glasshive_azure_enterprise_rejects_signed_link_secret_equal_to_service_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_dir = tmp_path / "runtime_phase1"
    runtime_dir.mkdir(parents=True)
    monkeypatch.setattr(config_compiler, "GLASSHIVE_RUNTIME_DIR", runtime_dir)

    config = minimal_compile_config()
    config["integrations"]["glasshive"] = {
        "enabled": True,
        "deployment_mode": "azure_enterprise_vm_docker",
        "mcp_url": "https://glasshive.enterprise.example.com/mcp",
        "operator_base_url": "https://glasshive.enterprise.example.com",
        "enterprise": {
            "tenant_id": "tenant-alpha",
            "signed_link_secret": {"secret_value": "same-secret"},
            "auth": {
                "mode": "first_party_assertion",
                "service_token": {"secret_value": "same-secret"},
            },
        },
    }

    with pytest.raises(SystemExit, match="signed_link_secret must differ from the service token"):
        config_compiler.render_runtime_env(config, config_compiler.build_agent_assignments(config))


def test_glasshive_azure_enterprise_client_header_token_delivery_is_explicit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_dir = tmp_path / "runtime_phase1"
    runtime_dir.mkdir(parents=True)
    monkeypatch.setattr(config_compiler, "GLASSHIVE_RUNTIME_DIR", runtime_dir)
    config = minimal_compile_config()
    config["runtime"]["network"] = {"public_api_origin": "https://api.enterprise.example.com"}
    config["integrations"]["glasshive"] = {
        "enabled": True,
        "deployment_mode": "azure_enterprise_vm_docker",
        "mcp_url": "https://glasshive.enterprise.example.com/mcp",
        "operator_base_url": "https://glasshive.enterprise.example.com",
        "enterprise": {
            "tenant_id": "tenant-alpha",
            "auth": {
                "mode": "first_party_assertion",
                "service_token_delivery": "client_header",
                "service_token": {"secret_value": "service-token-test"},
            },
        },
    }

    servers = config_compiler.build_mcp_servers(config, {"lc_api_port": 3080}, "agent-main")

    assert servers["glasshive-workers-projects"]["headers"]["X-WPR-Token"] == "${GLASSHIVE_MCP_SERVICE_TOKEN}"


def test_glasshive_azure_enterprise_rejects_localhost_cloud_urls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runtime_dir = tmp_path / "runtime_phase1"
    runtime_dir.mkdir(parents=True)
    monkeypatch.setattr(config_compiler, "GLASSHIVE_RUNTIME_DIR", runtime_dir)

    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {"profile": "isolated", "call_session_secret": {"secret_value": "call-session-test"}},
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
            "glasshive": {
                "enabled": True,
                "deployment_mode": "azure_enterprise_vm_docker",
                "mcp_url": "http://127.0.0.1:8767/mcp",
                "operator_base_url": "https://glasshive.enterprise.example.com",
            },
        },
        "agents": {},
    }

    with pytest.raises(SystemExit, match="non-localhost"):
        config_compiler.render_runtime_env(config, config_compiler.build_agent_assignments(config))


def test_glasshive_azure_enterprise_rejects_localhost_oauth_redirect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime_dir = tmp_path / "runtime_phase1"
    runtime_dir.mkdir(parents=True)
    monkeypatch.setattr(config_compiler, "GLASSHIVE_RUNTIME_DIR", runtime_dir)

    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "profile": "isolated",
            "call_session_secret": {"secret_value": "call-session-test"},
            "network": {"public_api_origin": "https://api.enterprise.example.com"},
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
            "glasshive": {
                "enabled": True,
                "deployment_mode": "azure_enterprise_vm_docker",
                "mcp_url": "https://glasshive.enterprise.example.com/mcp",
                "operator_base_url": "https://glasshive.enterprise.example.com",
                "enterprise": {
                    "tenant_id": "tenant-alpha",
                    "auth": {"service_token": {"secret_value": "service-token-test"}},
                    "oauth": {
                        "enabled": True,
                        "authorization_url": "https://login.example.com/authorize",
                        "token_url": "https://login.example.com/token",
                        "redirect_uri": "http://localhost:3080/api/mcp/glasshive-workers-projects/oauth/callback",
                    },
                },
            },
        },
        "agents": {},
    }

    with pytest.raises(SystemExit, match="enterprise.oauth.redirect_uri"):
        config_compiler.build_mcp_servers(config, {"lc_api_port": 3080}, "agent-main")


def test_mcp_server_instructions_own_scheduling_and_glasshive_cognition(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runtime_dir = tmp_path / "runtime_phase1"
    runtime_dir.mkdir(parents=True)
    monkeypatch.setattr(config_compiler, "GLASSHIVE_RUNTIME_DIR", runtime_dir)
    monkeypatch.setattr(
        config_compiler.shutil,
        "which",
        lambda name: f"/usr/local/bin/{name}" if name in {"codex", "claude"} else None,
    )

    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "profile": "isolated",
            "call_session_secret": {"secret_value": "call-session-test"},
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
            "google_workspace": {"enabled": True},
            "ms365": {"enabled": True},
            "skyvern": {"enabled": False},
            "openclaw": {"enabled": False},
            "glasshive": {"enabled": True},
        },
        "agents": {},
    }

    servers = config_compiler.build_mcp_servers(config, {"lc_api_port": 3080}, "agent-main")
    scheduling = servers["scheduling-cortex"]["serverInstructions"]
    glasshive = servers["glasshive-workers-projects"]["serverInstructions"]
    ms365 = servers["ms-365"]["serverInstructions"].lower()
    google_workspace = servers["google_workspace"]["serverInstructions"].lower()

    assert scheduling is True
    assert glasshive is True
    assert servers["scheduling-cortex"]["viventiumTrustedServerInstructions"] is True
    assert servers["glasshive-workers-projects"]["viventiumTrustedServerInstructions"] is True
    assert servers["glasshive-workers-projects"]["timeout"] == 1860000

    for instructions, product_phrase, other_provider in [
        (ms365, "microsoft 365 owns authenticated outlook mail", "google workspace"),
        (google_workspace, "google workspace owns authenticated gmail", "microsoft 365"),
    ]:
        for phrase in [
            product_phrase,
            "default to read-only inspection",
            "explicitly asks",
            "auth is missing/expired",
            "do not fabricate",
            "prevent duplicates",
            "structured ids/metadata",
            "user-facing verified results",
            "do not branch on prompt text",
            other_provider,
        ]:
            assert phrase in instructions


def test_source_of_truth_mcp_instructions_match_prompt_architecture_contract() -> None:
    source = load_source_of_truth_librechat_yaml()
    servers = source["mcpServers"]

    scheduling = servers["scheduling-cortex"]["serverInstructions"]
    glasshive = servers["glasshive-workers-projects"]["serverInstructions"]
    ms365 = servers["ms-365"]["serverInstructions"].lower()
    google_workspace = servers["google_workspace"]["serverInstructions"].lower()

    assert scheduling is True
    assert glasshive is True
    assert servers["scheduling-cortex"]["viventiumTrustedServerInstructions"] is True
    assert servers["glasshive-workers-projects"]["viventiumTrustedServerInstructions"] is True

    for instructions in [ms365, google_workspace]:
        assert "default to read-only inspection" in instructions
        assert "auth is missing/expired" in instructions
        assert "prevent duplicates" in instructions
        assert "do not fabricate" in instructions
        assert "do not branch on prompt text" in instructions


def test_source_of_truth_exposes_glasshive_native_scheduler_and_followup_tools() -> None:
    expected_tools = {
        "workspace_launch_mcp_glasshive-workers-projects",
        "workspace_status_mcp_glasshive-workers-projects",
        "workspace_wait_mcp_glasshive-workers-projects",
        "workspace_continue_mcp_glasshive-workers-projects",
        "workspace_artifacts_mcp_glasshive-workers-projects",
        "workspace_artifact_download_mcp_glasshive-workers-projects",
        "workspace_preferences_get_mcp_glasshive-workers-projects",
        "workspace_preferences_set_mcp_glasshive-workers-projects",
        "workspace_schedule_mcp_glasshive-workers-projects",
        "worker_schedule_mcp_glasshive-workers-projects",
        "worker_schedules_mcp_glasshive-workers-projects",
    }

    agents_bundle = load_source_of_truth_agents_bundle()
    main_agent = agents_bundle["mainAgent"]
    assert expected_tools.issubset(set(main_agent["tools"]))
    assert "Use GlassHive MCP scheduling tools" in main_agent["instructions"]
    assert "Never claim a GlassHive schedule exists unless" in main_agent["instructions"]

    glasshive_policy = next(
        server
        for server in agents_bundle["config"]["viventium"]["background_cortices"]["activation_policy"][
            "direct_action_mcp_servers"
        ]
        if server["server"] == "glasshive-workers-projects"
    )
    assert expected_tools.issubset(set(glasshive_policy["tool_names"]))

    librechat_source = load_source_of_truth_librechat_yaml()
    glasshive_lc_policy = next(
        server
        for server in librechat_source["viventium"]["background_cortices"]["activation_policy"][
            "direct_action_mcp_servers"
        ]
        if server["server"] == "glasshive-workers-projects"
    )
    assert expected_tools.issubset(set(glasshive_lc_policy["tool_names"]))


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
                "x_ai": "synthetic_xai_test",
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
    librechat_env = (output_dir / "service-env" / "librechat.env").read_text(encoding="utf-8")

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
    assert librechat_yaml["endpoints"]["anthropic"]["titleModel"] == "claude-sonnet-4-5"
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
    assert assignments["background_analysis"] == ("anthropic", "claude-sonnet-4-5")
    assert assignments["red_team"] == ("anthropic", "claude-opus-4-7")
    assert assignments["deep_research"] == ("anthropic", "claude-opus-4-7")
    assert assignments["productivity"] == ("anthropic", "claude-sonnet-4-5")
    assert assignments["emotional_resonance"] == ("anthropic", "claude-sonnet-4-5")
    assert assignments["strategic_planning"] == ("anthropic", "claude-opus-4-7")
    assert assignments["memory"] == ("anthropic", "claude-sonnet-4-5")


def test_build_agent_assignments_requires_openai_or_anthropic_foundation() -> None:
    config = {
        "llm": {
            "primary": {
                "provider": "x_ai",
                "auth_mode": "api_key",
                "secret_value": "synthetic_xai_test",
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
                "secret_value": "synthetic_xai_test",
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


def test_config_compiler_full_run_requires_groq_activation_credential(tmp_path: Path) -> None:
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
    assert "Missing required Groq activation credential." in completed.stderr


def test_config_compiler_full_run_accepts_default_groq_activation_without_xai(tmp_path: Path) -> None:
    config = minimal_compile_config()
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
    assert "GROQ_API_KEY=groq-test" in runtime_env
    assert "XAI_API_KEY=xai-test" not in runtime_env


def test_config_compiler_full_run_accepts_explicit_xai_activation_override(tmp_path: Path) -> None:
    config = minimal_compile_config()
    config["llm"]["activation"] = {
        "provider": "xai",
        "auth_mode": "api_key",
        "secret_value": "xai-test",
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
    assert "XAI_API_KEY=xai-test" in runtime_env
    assert "GROQ_API_KEY=" not in runtime_env
    assert "VIVENTIUM_BACKGROUND_ACTIVATION_PROVIDER=xai" in runtime_env
    assert "VIVENTIUM_BACKGROUND_ACTIVATION_MODEL=grok-4.20-non-reasoning" in runtime_env


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
    assert env["VIVENTIUM_CORTEX_BACKGROUND_ANALYSIS_LLM_MODEL"] == "claude-sonnet-4-5"
    assert env["VIVENTIUM_CORTEX_RED_TEAM_LLM_PROVIDER"] == "openai"
    assert env["VIVENTIUM_CORTEX_RED_TEAM_LLM_MODEL"] == "gpt-5.4"
    assert env["VIVENTIUM_CORTEX_PRODUCTIVITY_LLM_PROVIDER"] == "openai"
    assert env["VIVENTIUM_CORTEX_PRODUCTIVITY_LLM_MODEL"] == "gpt-5.4"
    assert env["VIVENTIUM_CORTEX_SUPPORT_LLM_PROVIDER"] == "anthropic"
    assert env["VIVENTIUM_CORTEX_SUPPORT_LLM_MODEL"] == "claude-sonnet-4-5"
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
    assert assignments["background_analysis"] == ("anthropic", "claude-sonnet-4-5")
    assert assignments["confirmation_bias"] == ("anthropic", "claude-sonnet-4-5")
    assert assignments["red_team"] == ("openai", "gpt-5.4")
    assert assignments["deep_research"] == ("openai", "gpt-5.4")
    assert assignments["productivity"] == ("openai", "gpt-5.4")
    assert assignments["parietal"] == ("openai", "gpt-5.4")
    assert assignments["pattern_recognition"] == ("anthropic", "claude-sonnet-4-5")
    assert assignments["emotional_resonance"] == ("anthropic", "claude-sonnet-4-5")
    assert assignments["strategic_planning"] == ("anthropic", "claude-opus-4-7")
    assert assignments["support"] == ("anthropic", "claude-sonnet-4-5")
    assert assignments["memory"] == ("anthropic", "claude-sonnet-4-5")


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

    assert assignments["memory"] == ("anthropic", "claude-sonnet-4-5")


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
                "secret_value": "synthetic_xai_test",
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
                    "name": "claude-sonnet-4-5",
                    "label": "Claude Sonnet 4.5",
                    "preset": {"endpoint": "anthropic", "model": "claude-sonnet-4-5"},
                },
                {
                    "name": "viventium",
                    "preset": {"endpoint": "agents", "agent_id": "agent_viventium_main_95aeb3"},
                },
            ],
            "addedEndpoints": ["agents", "anthropic", "openAI"],
        },
        "endpoints": {"anthropic": {"summaryModel": "claude-sonnet-4-5"}},
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
                    "name": "claude-sonnet-4-5",
                    "label": "Claude Sonnet 4.5",
                    "preset": {"endpoint": "anthropic", "model": "claude-sonnet-4-5"},
                },
                {
                    "name": "viventium",
                    "preset": {"endpoint": "agents", "agent_id": "agent_viventium_main_95aeb3"},
                },
            ],
            "addedEndpoints": ["agents", "anthropic", "openAI"],
        },
        "endpoints": {"anthropic": {"summaryModel": "claude-sonnet-4-5"}},
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
                    "name": "claude-sonnet-4-5",
                    "label": "Claude Sonnet 4.5",
                    "preset": {"endpoint": "anthropic", "model": "claude-sonnet-4-5"},
                },
                {
                    "name": "claude-opus-4-7",
                    "label": "Claude Opus 4 7",
                    "preset": {"endpoint": "anthropic", "model": "claude-opus-4-7"},
                },
            ]
        },
        "endpoints": {"anthropic": {"summaryModel": "claude-sonnet-4-5"}},
    }
    normalized = config_compiler.prune_unavailable_source_defaults(
        payload,
        {"ANTHROPIC_API_KEY": "anthropic-test"},
    )
    assert [entry["name"] for entry in normalized["modelSpecs"]["list"]] == [
        "claude-sonnet-4-5",
        "claude-opus-4-7",
    ]
    assert normalized["modelSpecs"]["list"][0]["label"] == "Claude Sonnet 4.5"
    assert normalized["modelSpecs"]["list"][1]["label"] == "Claude Opus 4 7"
    assert normalized["endpoints"]["anthropic"]["summaryModel"] == "claude-sonnet-4-5"


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
                "connected_accounts_return_origin": "http://localhost:3190/",
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
    assert "VIVENTIUM_CONNECTED_ACCOUNTS_RETURN_ORIGIN=http://localhost:3190" in runtime_env


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
                "x_ai": "synthetic_xai_test",
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
    assert "XAI_API_KEY=synthetic_xai_test" in runtime_env
    assert f"BOT_TOKEN={VALID_TELEGRAM_TOKEN}" in runtime_env
    assert "VIVENTIUM_TELEGRAM_SECRET=call-secret-2" in runtime_env
    assert "VIVENTIUM_LIBRECHAT_ORIGIN=http://127.0.0.1:3180" in runtime_env
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
    expected_local_whisper_model = "small" if platform.machine().lower() == "x86_64" else "large-v3-turbo"
    assert telegram_codex_settings["transcription"]["model_name"] == expected_local_whisper_model
    assert telegram_codex_settings["runtime"]["stable_pairing_root"].endswith("state/telegram-codex/paired-users")
    assert telegram_codex_settings["runtime"]["legacy_paired_users_path"].endswith(
        "state/runtime/isolated/telegram-codex/state/paired_users.json"
    )
    assert telegram_codex_projects["default_project"] == "viventium_core"
    assert "telegram_codex" in telegram_codex_projects["projects"]
    assert f"BOT_TOKEN={VALID_TELEGRAM_TOKEN}" in telegram_env
    assert "VIVENTIUM_TELEGRAM_AGENT_ID=agent_viventium_main_95aeb3" in telegram_env
    assert "VIVENTIUM_LIBRECHAT_ORIGIN=http://127.0.0.1:3180" in telegram_env
    assert "VIVENTIUM_TELEGRAM_SECRET=call-secret-2" in telegram_env
    assert f"TELEGRAM_CODEX_BOT_TOKEN={VALID_TELEGRAM_CODEX_TOKEN}" in telegram_codex_env


@pytest.mark.parametrize("stt_model", ["base.en", "large-v3-turbo"])
def test_config_compiler_emits_local_voice_stt_model_override(tmp_path: Path, stt_model: str) -> None:
    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "log_level": "info",
            "profile": "isolated",
            "call_session_secret": {"secret_value": "call-secret-stt-model"},
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
            "stt_model": stt_model,
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

    assert "VIVENTIUM_STT_PROVIDER=whisper_local" in runtime_env
    assert f"VIVENTIUM_STT_MODEL={stt_model}" in runtime_env


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
                "model": "universal-streaming-multilingual",
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
                "aec_warmup_duration_s": 0.75,
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
    assert "VIVENTIUM_VOICE_AEC_WARMUP_DURATION_S=0.75" in runtime_env
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
    assert "VIVENTIUM_ASSEMBLYAI_STT_MODEL=universal-streaming-multilingual" in runtime_env
    assert "VIVENTIUM_STT_VAD_MIN_SPEECH=0.12" in runtime_env
    assert "VIVENTIUM_STT_VAD_MIN_SILENCE=0.72" in runtime_env
    assert "VIVENTIUM_STT_VAD_ACTIVATION=0.33" in runtime_env
    assert "VIVENTIUM_CARTESIA_API_VERSION=2026-03-01" in runtime_env
    assert "VIVENTIUM_CARTESIA_MODEL_ID=sonic-3" in runtime_env
    assert "VIVENTIUM_CARTESIA_VOICE_ID=e8e5fffb-252c-436d-b842-8879b84445b6" in runtime_env
    assert "VIVENTIUM_CARTESIA_SAMPLE_RATE=44100" in runtime_env
    assert "VIVENTIUM_CARTESIA_MAX_BUFFER_DELAY_MS=120" in runtime_env


def test_config_compiler_emits_cartesia_sonic3_voice_options(tmp_path: Path) -> None:
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
            "tts": {
                "secret_value": "cartesia-test",
                "model_id": "sonic-3",
                "voice": {
                    "mode": "id",
                    "id": "6ccbfb76-1fc6-48f7-b71d-91ac6298247b",
                },
                "speed": 1,
                "volume": 1,
                "emotion": "calm",
                "language": "en",
                "api_version": "2026-03-01",
                "sample_rate": 44100,
                "max_buffer_delay_ms": 80,
                "segment_silence_ms": 40,
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

    assert "VIVENTIUM_CARTESIA_API_VERSION=2026-03-01" in runtime_env
    assert "VIVENTIUM_CARTESIA_MODEL_ID=sonic-3" in runtime_env
    assert "VIVENTIUM_CARTESIA_VOICE_ID=6ccbfb76-1fc6-48f7-b71d-91ac6298247b" in runtime_env
    assert "VIVENTIUM_CARTESIA_SPEED=1" in runtime_env
    assert "VIVENTIUM_CARTESIA_VOLUME=1" in runtime_env
    assert "VIVENTIUM_CARTESIA_EMOTION=calm" in runtime_env
    assert "VIVENTIUM_CARTESIA_LANGUAGE=en" in runtime_env
    assert "VIVENTIUM_CARTESIA_SAMPLE_RATE=44100" in runtime_env
    assert "VIVENTIUM_CARTESIA_MAX_BUFFER_DELAY_MS=80" in runtime_env
    assert "VIVENTIUM_CARTESIA_SEGMENT_SILENCE_MS=40" in runtime_env


def test_config_compiler_rejects_non_sonic3_cartesia_model(tmp_path: Path) -> None:
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
            "tts": {"secret_value": "cartesia-test", "model_id": "sonic-2"},
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

    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/viventium/config_compiler.py"),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert result.returncode != 0
    assert "Cartesia voice calls support only model_id 'sonic-3'" in (
        result.stdout + result.stderr
    )


def test_config_compiler_emits_background_followup_window_override(tmp_path: Path) -> None:
    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "log_level": "info",
            "profile": "isolated",
            "background_followup_window_s": 45,
            "glasshive_followup_timeout_s": 900,
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
    librechat_env = (output_dir / "service-env" / "librechat.env").read_text(encoding="utf-8")

    assert "VIVENTIUM_CORTEX_FOLLOWUP_GRACE_S=45" in runtime_env
    assert "VIVENTIUM_VOICE_FOLLOWUP_GRACE_S=45" in runtime_env
    assert "VIVENTIUM_TELEGRAM_FOLLOWUP_GRACE_S=45" in runtime_env
    assert "VIVENTIUM_WEB_GLASSHIVE_TIMEOUT_S=900" in runtime_env
    assert "VIVENTIUM_VOICE_GLASSHIVE_TIMEOUT_S=900" in runtime_env
    assert "VIVENTIUM_TELEGRAM_GLASSHIVE_TIMEOUT_S=900" in runtime_env
    assert "VIVENTIUM_CORTEX_PHASE_A_NOTICE_MODE=any_activated_on_voice" in runtime_env
    assert "VIVENTIUM_VOICE_BACKGROUND_AGENT_DETECTION_ASYNC=true" in runtime_env
    assert "VIVENTIUM_TEXT_BACKGROUND_AGENT_DETECTION_ASYNC=false" in runtime_env
    assert "VIVENTIUM_VOICE_PHASE_A_AWAIT_MS=690" in runtime_env
    assert "VIVENTIUM_TEXT_PHASE_A_AWAIT_MS=1300" in runtime_env
    assert "VIVENTIUM_VOICE_PHASE_A_ASYNC_ALLOW_TOOL_HOLD=true" in runtime_env
    assert "VIVENTIUM_VOICE_LOG_LATENCY=1" in runtime_env
    assert "VIVENTIUM_CORTEX_PHASE_A_NOTICE_MODE=any_activated_on_voice" in librechat_env
    assert "VIVENTIUM_VOICE_BACKGROUND_AGENT_DETECTION_ASYNC=true" in librechat_env
    assert "VIVENTIUM_TEXT_BACKGROUND_AGENT_DETECTION_ASYNC=false" in librechat_env
    assert "VIVENTIUM_VOICE_PHASE_A_AWAIT_MS=690" in librechat_env
    assert "VIVENTIUM_TEXT_PHASE_A_AWAIT_MS=1300" in librechat_env
    assert "VIVENTIUM_VOICE_PHASE_A_ASYNC_ALLOW_TOOL_HOLD=true" in librechat_env
    assert "VIVENTIUM_VOICE_LOG_LATENCY=1" in librechat_env


def test_config_compiler_rejects_invalid_glasshive_followup_timeout(tmp_path: Path) -> None:
    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "log_level": "info",
            "profile": "isolated",
            "glasshive_followup_timeout_s": 0,
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

    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/viventium/config_compiler.py"),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert result.returncode != 0
    assert "runtime.glasshive_followup_timeout_s must be between 30 and 86400" in (
        result.stdout + result.stderr
    )


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
    assert "VIVENTIUM_ASSEMBLYAI_STT_MODEL=u3-rt-pro" in runtime_env


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
    assert "VIVENTIUM_TELEGRAM_STT_PROVIDER=whisper_local" in telegram_env
    assert "VIVENTIUM_TELEGRAM_LOCAL_BOT_API_ENABLED=true" in telegram_env
    assert "VIVENTIUM_TELEGRAM_BOT_API_ORIGIN=http://127.0.0.1:8084" in telegram_env
    assert "VIVENTIUM_TELEGRAM_MAX_FILE_SIZE=104857600" in telegram_env
    telegram_env_mode = stat.S_IMODE((output_dir / "service-env" / "telegram.config.env").stat().st_mode)
    runtime_env_mode = stat.S_IMODE((output_dir / "runtime.env").stat().st_mode)
    librechat_env_mode = stat.S_IMODE((output_dir / "service-env" / "librechat.env").stat().st_mode)
    assert telegram_env_mode == 0o600
    assert runtime_env_mode == 0o600
    assert librechat_env_mode == 0o600


@pytest.mark.parametrize("voice_stt_provider", ["whisper_local", "pywhispercpp", "local"])
def test_config_compiler_inherits_local_voice_stt_for_telegram_when_not_overridden(
    tmp_path: Path,
    voice_stt_provider: str,
) -> None:
    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "log_level": "info",
            "profile": "isolated",
            "call_session_secret": {
                "secret_value": f"call-secret-telegram-stt-default-{voice_stt_provider}"
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
        "voice": {
            "mode": "local",
            "stt_provider": voice_stt_provider,
            "tts_provider": "browser",
        },
        "integrations": {
            "telegram": {
                "enabled": True,
                "secret_value": VALID_TELEGRAM_TOKEN,
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

    telegram_env = (output_dir / "service-env" / "telegram.config.env").read_text(encoding="utf-8")

    assert f"VIVENTIUM_TELEGRAM_STT_PROVIDER={voice_stt_provider}" in telegram_env
    assert "VIVENTIUM_TELEGRAM_STT_PROVIDER=openai" not in telegram_env
    assert "VIVENTIUM_TELEGRAM_STT_PROVIDER=assemblyai" not in telegram_env


def test_config_compiler_allows_explicit_telegram_stt_provider_override(tmp_path: Path) -> None:
    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "log_level": "info",
            "profile": "isolated",
            "call_session_secret": {"secret_value": "call-secret-telegram-stt"},
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
            "telegram": {
                "enabled": True,
                "secret_value": VALID_TELEGRAM_TOKEN,
                "stt_provider": "whisper_local",
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

    telegram_env = (output_dir / "service-env" / "telegram.config.env").read_text(encoding="utf-8")

    assert "VIVENTIUM_TELEGRAM_STT_PROVIDER=whisper_local" in telegram_env


def test_config_compiler_inherits_hosted_voice_stt_for_telegram_when_not_overridden(
    tmp_path: Path,
) -> None:
    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "log_level": "info",
            "profile": "isolated",
            "call_session_secret": {"secret_value": "call-secret-telegram-stt-hosted"},
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
            "tts_provider": "browser",
        },
        "integrations": {
            "telegram": {
                "enabled": True,
                "secret_value": VALID_TELEGRAM_TOKEN,
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

    telegram_env = (output_dir / "service-env" / "telegram.config.env").read_text(encoding="utf-8")

    assert "VIVENTIUM_TELEGRAM_STT_PROVIDER=assemblyai" in telegram_env


def test_config_compiler_rejects_unknown_telegram_stt_provider(tmp_path: Path) -> None:
    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "log_level": "info",
            "profile": "isolated",
            "call_session_secret": {"secret_value": "call-secret-telegram-stt-invalid"},
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
            "telegram": {
                "enabled": True,
                "secret_value": VALID_TELEGRAM_TOKEN,
                "stt_provider": "whispr_local",
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
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert "integrations.telegram.stt_provider must be one of" in (
        completed.stderr + completed.stdout
    )


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
                "xai": {"secret_value": "synthetic_xai_dormant"},
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
    assert "VIVENTIUM_XAI_TTS_API_KEY=synthetic_xai_dormant" in runtime_env
    assert "GROQ_API_KEY=groq-test" in runtime_env


def test_config_compiler_normalizes_xai_tts_alias_and_prefers_tts_secret(tmp_path: Path) -> None:
    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "log_level": "info",
            "profile": "isolated",
            "call_session_secret": {"secret_value": "call_secret_xai_tts"},
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
            "secondary": {"provider": "none", "auth_mode": "api_key", "secret_value": ""},
            "extra_provider_keys": {"x_ai": "synthetic_xai_llm"},
        },
        "voice": {
            "mode": "hosted",
            "stt_provider": "openai",
            "tts_provider": "x_ai",
            "tts": {
                "secret_value": "synthetic_xai_tts",
                "voice_id": "Eve",
                "language": "en",
                "xai": {
                    "optimize_streaming_latency": 1,
                    "output_format": {
                        "codec": "mp3",
                        "sample_rate": 44100,
                        "bit_rate": 128000,
                    }
                },
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
    telegram_env = (output_dir / "service-env" / "telegram.config.env").read_text(encoding="utf-8")

    assert "VIVENTIUM_TTS_PROVIDER=xai" in runtime_env
    assert "VIVENTIUM_XAI_TTS_API=tts" in runtime_env
    assert "VIVENTIUM_XAI_TTS_WS_URL=wss://api.x.ai/v1/tts" in runtime_env
    assert "VIVENTIUM_XAI_VOICE=Eve" in runtime_env
    assert "VIVENTIUM_XAI_LANGUAGE=en" in runtime_env
    assert "VIVENTIUM_XAI_TTS_OPTIMIZE_STREAMING_LATENCY=1" in runtime_env
    assert "VIVENTIUM_XAI_TTS_API_KEY=synthetic_xai_tts" in runtime_env
    assert "XAI_API_KEY=synthetic_xai_llm" in runtime_env
    assert "VIVENTIUM_XAI_TTS_API_KEY=synthetic_xai_tts" in telegram_env
    assert "XAI_API_KEY=synthetic_xai_llm" in telegram_env
    assert "VIVENTIUM_XAI_TTS_API_URL=https://api.x.ai/v1/tts" in telegram_env
    assert "VIVENTIUM_XAI_VOICE=Eve" in telegram_env
    assert "VIVENTIUM_XAI_LANGUAGE=en" in telegram_env
    assert "VIVENTIUM_XAI_SAMPLE_RATE=24000" in telegram_env
    assert "VIVENTIUM_XAI_TTS_OPTIMIZE_STREAMING_LATENCY=1" in telegram_env
    assert "VIVENTIUM_XAI_TTS_CODEC=mp3" in telegram_env
    assert "VIVENTIUM_XAI_TTS_SAMPLE_RATE=44100" in telegram_env
    assert "VIVENTIUM_XAI_TTS_BIT_RATE=128000" in telegram_env


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
    librechat_env = (output_dir / "service-env" / "librechat.env").read_text(encoding="utf-8")

    assert "VIVENTIUM_DEFAULT_CONVERSATION_RECALL=false" in runtime_env
    assert "START_RAG_API=false" in runtime_env


def test_config_compiler_starts_rag_when_transcript_source_is_configured(tmp_path: Path) -> None:
    config = {
        "version": 1,
        "install": {"mode": "native"},
        "runtime": {
            "log_level": "info",
            "profile": "isolated",
            "call_session_secret": {"secret_value": "call-secret-transcripts"},
            "personalization": {"default_conversation_recall": False},
            "memory_hardening": {
                "operator_user_email": "qa@example.com",
                "min_apply_interval_seconds": 600,
                "transcripts": {
                    "source_dir": "/path/to/transcripts",
                    "ignore_globs": ["_index.json", "state/**"],
                    "max_files_per_run": 12,
                    "min_files_per_run": 6,
                    "max_batches_per_invocation": 2,
                    "max_chars_per_file": 200000,
                    "summary_max_chars": 28000,
                    "reference_memory_max_chars": 18000,
                    "reference_messages_max_chars": 22000,
                    "stable_evidence_max_age_days": 45,
                    "rag_mode": "detailed_summary_only",
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
    librechat_env = (output_dir / "service-env" / "librechat.env").read_text(encoding="utf-8")

    assert "VIVENTIUM_DEFAULT_CONVERSATION_RECALL=false" in runtime_env
    assert "START_RAG_API=true" in runtime_env
    assert "RAG_API_URL=http://localhost:8110" in runtime_env
    assert "VIVENTIUM_MEMORY_HARDENING_USER_EMAIL=qa@example.com" in runtime_env
    assert "VIVENTIUM_MEMORY_HARDENING_MIN_APPLY_INTERVAL_SECONDS=600" in runtime_env
    assert "VIVENTIUM_MEMORY_TRANSCRIPTS_DIR=/path/to/transcripts" in runtime_env
    assert "VIVENTIUM_MEMORY_TRANSCRIPTS_IGNORE_GLOBS='_index.json,state/**'" in runtime_env
    assert "VIVENTIUM_MEMORY_TRANSCRIPTS_MAX_FILES_PER_RUN=12" in runtime_env
    assert "VIVENTIUM_MEMORY_TRANSCRIPTS_MIN_FILES_PER_RUN=6" in runtime_env
    assert "VIVENTIUM_MEMORY_TRANSCRIPTS_MAX_BATCHES_PER_INVOCATION=2" in runtime_env
    assert "VIVENTIUM_MEMORY_TRANSCRIPTS_MAX_CHARS_PER_FILE=200000" in runtime_env
    assert "VIVENTIUM_MEMORY_TRANSCRIPTS_SUMMARY_MAX_CHARS=28000" in runtime_env
    assert "VIVENTIUM_MEMORY_TRANSCRIPTS_REFERENCE_MEMORY_MAX_CHARS=18000" in runtime_env
    assert "VIVENTIUM_MEMORY_TRANSCRIPTS_REFERENCE_MESSAGES_MAX_CHARS=22000" in runtime_env
    assert "VIVENTIUM_MEMORY_TRANSCRIPTS_STABLE_EVIDENCE_MAX_AGE_DAYS=45" in runtime_env
    assert "VIVENTIUM_MEMORY_TRANSCRIPTS_RAG_MODE=detailed_summary_only" in runtime_env
    assert "VIVENTIUM_MEMORY_HARDENING_USER_EMAIL=qa@example.com" in librechat_env
    assert "VIVENTIUM_MEMORY_HARDENING_MIN_APPLY_INTERVAL_SECONDS=600" in librechat_env
    assert "RAG_API_URL=http://localhost:8110" in librechat_env
    assert "VIVENTIUM_MEMORY_TRANSCRIPTS_DIR=/path/to/transcripts" in librechat_env
    assert "VIVENTIUM_MEMORY_TRANSCRIPTS_IGNORE_GLOBS='_index.json,state/**'" in librechat_env
    assert "VIVENTIUM_MEMORY_TRANSCRIPTS_MAX_FILES_PER_RUN=12" in librechat_env
    assert "VIVENTIUM_MEMORY_TRANSCRIPTS_MIN_FILES_PER_RUN=6" in librechat_env
    assert "VIVENTIUM_MEMORY_TRANSCRIPTS_MAX_BATCHES_PER_INVOCATION=2" in librechat_env
    assert "VIVENTIUM_MEMORY_TRANSCRIPTS_MAX_CHARS_PER_FILE=200000" in librechat_env
    assert "VIVENTIUM_MEMORY_TRANSCRIPTS_SUMMARY_MAX_CHARS=28000" in librechat_env
    assert "VIVENTIUM_MEMORY_TRANSCRIPTS_STABLE_EVIDENCE_MAX_AGE_DAYS=45" in librechat_env
    assert "VIVENTIUM_MEMORY_TRANSCRIPTS_RAG_MODE=detailed_summary_only" in librechat_env


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
    assert "OPENAI_MODELS=" not in runtime_env
    assert "ANTHROPIC_API_KEY=anthropic-test" in runtime_env
    assert "VIVENTIUM_MEMORY_HARDENING_PROVIDER=anthropic" in runtime_env
    assert "VIVENTIUM_MEMORY_HARDENING_MODEL=claude-opus-4-7" in runtime_env
    assert "VIVENTIUM_MEMORY_HARDENING_EFFORT=xhigh" in runtime_env
    assert librechat_yaml["memory"]["agent"]["provider"] == "anthropic"
    assert librechat_yaml["memory"]["agent"]["model"] == "claude-sonnet-4-5"
    assert librechat_yaml["endpoints"]["anthropic"]["titleEndpoint"] == "anthropic"
    assert librechat_yaml["endpoints"]["anthropic"]["titleModel"] == "claude-sonnet-4-5"


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
    assert librechat_yaml["memory"]["agent"]["model"] == "claude-sonnet-4-5"
    assert librechat_yaml["endpoints"]["anthropic"]["titleEndpoint"] == "anthropic"
    assert librechat_yaml["endpoints"]["anthropic"]["titleModel"] == "claude-sonnet-4-5"


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
    assert env["VIVENTIUM_MEMORY_HARDENING_PROVIDER"] == "openai"
    assert env["VIVENTIUM_MEMORY_HARDENING_MODEL"] == "gpt-5.5"
    assert env["VIVENTIUM_MEMORY_HARDENING_EFFORT"] == "xhigh"
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
                "provider": "xai",
                "auth_mode": "api_key",
                "secret_ref": "keychain://viventium/x_ai_api_key",
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
                "XAI_API_KEY=xai-existing",
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
    for key in ("XAI_API_KEY", "OPENAI_API_KEY", "BOT_TOKEN"):
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

    assert "XAI_API_KEY=xai-existing" in runtime_env
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
                "x_ai": "synthetic_xai_real",
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
    assert "XAI_API_KEY=synthetic_xai_real" in runtime_env


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
    assert librechat_yaml["mcpServers"]["ms-365"]["oauth"]["client_id"] == "${MS365_MCP_CLIENT_ID}"
    assert librechat_yaml["mcpServers"]["ms-365"]["oauth"]["client_secret"] == ""


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

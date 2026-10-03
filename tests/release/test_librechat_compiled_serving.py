"""Compiled serving profile for source installs (`runtime.librechat_serve_mode: compiled`).

A source install serves LibreChat through its development servers by default. The compiled
profile runs the production API and serves the built client bundle on the same ports, with the
explicit Cortex delivery slot the production API requires. Native payloads own their own serving.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh"
BUILD_HELPER = REPO_ROOT / "scripts" / "viventium" / "librechat_build.sh"
LIBRECHAT = REPO_ROOT / "viventium_v0_4" / "LibreChat"

CONFIG_COMPILER_SPEC = importlib.util.spec_from_file_location(
    "viventium_config_compiler_compiled_serving",
    REPO_ROOT / "scripts" / "viventium" / "config_compiler.py",
)
config_compiler = importlib.util.module_from_spec(CONFIG_COMPILER_SPEC)
assert CONFIG_COMPILER_SPEC.loader is not None
sys.modules[CONFIG_COMPILER_SPEC.name] = config_compiler
CONFIG_COMPILER_SPEC.loader.exec_module(config_compiler)


def minimal_config() -> dict:
    return {
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
            "google_workspace": {"enabled": False},
            "ms365": {"enabled": False},
            "skyvern": {"enabled": False},
            "openclaw": {"enabled": False},
        },
    }


def render(config: dict) -> dict[str, str]:
    return config_compiler.render_runtime_env(config, config_compiler.build_agent_assignments(config))


def extract_shell_function(text: str, name: str) -> str:
    lines = text.splitlines()
    start = next(index for index, line in enumerate(lines) if line.strip() == f"{name}() {{")
    collected: list[str] = []
    depth = 0
    for line in lines[start:]:
        collected.append(line)
        depth += line.count("{") - line.count("}")
        if depth == 0:
            break
    return "\n".join(collected) + "\n"


def test_compiled_serving_is_opt_in_and_binds_a_stable_delivery_slot(tmp_path, monkeypatch) -> None:
    config = minimal_config()
    monkeypatch.setenv("VIVENTIUM_APP_SUPPORT_DIR", str(tmp_path / "support-a"))

    development = render(config)
    # The default emits nothing new: existing installs compile byte-identical runtime envs.
    assert "VIVENTIUM_LIBRECHAT_SERVE_MODE" not in development
    assert "VIVENTIUM_RUNTIME_SLOT_ID" not in development
    config["runtime"]["librechat_serve_mode"] = "development"
    assert render(config) == development

    config["runtime"]["librechat_serve_mode"] = "compiled"
    compiled = render(config)
    slot = compiled["VIVENTIUM_RUNTIME_SLOT_ID"]
    assert compiled["VIVENTIUM_LIBRECHAT_SERVE_MODE"] == "compiled"
    assert re.fullmatch(r"source-[0-9a-f]{32}", slot)
    assert {key: value for key, value in compiled.items() if key not in {
        "VIVENTIUM_LIBRECHAT_SERVE_MODE",
        "VIVENTIUM_RUNTIME_SLOT_ID",
    }} == development
    # Restarts of the same install reclaim their own claims: the slot is stable.
    assert render(config)["VIVENTIUM_RUNTIME_SLOT_ID"] == slot

    # Another install, or another API port on this install, is a distinct slot.
    monkeypatch.setenv("VIVENTIUM_APP_SUPPORT_DIR", str(tmp_path / "support-b"))
    assert render(config)["VIVENTIUM_RUNTIME_SLOT_ID"] != slot
    monkeypatch.setenv("VIVENTIUM_APP_SUPPORT_DIR", str(tmp_path / "support-a"))
    config["runtime"]["ports"] = {"lc_api_port": 3480}
    assert render(config)["VIVENTIUM_RUNTIME_SLOT_ID"] != slot


def test_native_payloads_never_receive_source_serving_or_its_slot(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VIVENTIUM_APP_SUPPORT_DIR", str(tmp_path / "support"))
    config = minimal_config()
    config["runtime"]["librechat_serve_mode"] = "compiled"

    native = config_compiler.render_native_runtime_env(config, render(config))

    assert "VIVENTIUM_LIBRECHAT_SERVE_MODE" not in native
    assert "VIVENTIUM_RUNTIME_SLOT_ID" not in native


@pytest.mark.parametrize("value", ["production", "dev", "compiled-bundle"])
def test_unknown_serve_modes_are_refused(value: str) -> None:
    config = minimal_config()
    config["runtime"]["librechat_serve_mode"] = value

    with pytest.raises(SystemExit, match="runtime.librechat_serve_mode"):
        render(config)


def test_schema_declares_the_serve_mode_enum() -> None:
    schema = yaml.safe_load((REPO_ROOT / "config.schema.yaml").read_text(encoding="utf-8"))
    serve_mode = schema["properties"]["runtime"]["properties"]["librechat_serve_mode"]

    assert serve_mode["enum"] == ["development", "compiled"]


@pytest.mark.parametrize(
    ("value", "compiled"),
    [("compiled", True), ("COMPILED", True), ("development", False), ("", False), ("other", False)],
)
def test_launcher_selects_compiled_serving_only_for_the_compiled_value(value: str, compiled: bool) -> None:
    helper = extract_shell_function(BUILD_HELPER.read_text(encoding="utf-8"), "librechat_serves_compiled")
    result = subprocess.run(
        ["bash", "-c", f"{helper}\nlibrechat_serves_compiled"],
        env={"PATH": "/usr/bin:/bin", "VIVENTIUM_LIBRECHAT_SERVE_MODE": value},
        check=False,
    )

    assert (result.returncode == 0) is compiled


@pytest.mark.parametrize(
    ("serve_mode", "expected"),
    [("compiled", "run backend"), ("development", "run backend:dev")],
)
def test_watchdog_restart_starts_the_backend_of_the_selected_profile(
    tmp_path, serve_mode: str, expected: str
) -> None:
    launcher = LAUNCHER.read_text(encoding="utf-8")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    npm_calls = tmp_path / "npm-calls"
    (fake_bin / "npm").write_text(f'#!/bin/bash\nprintf "%s\\n" "$*" >> "{npm_calls}"\n', encoding="utf-8")
    (fake_bin / "npm").chmod(0o755)
    kills = tmp_path / "kills"
    librechat_dir = tmp_path / "LibreChat"
    librechat_dir.mkdir()
    script = "\n".join(
        [
            'SKIP_LIBRECHAT=false; LC_API_PORT=1; VIVENTIUM_SANDPACK_BUNDLER_PORT=2',
            "USE_LIBRECHAT_WRAPPER=false",
            f'LIBRECHAT_DIR="{librechat_dir}"',
            f'LIBRECHAT_API_WATCHDOG_LOG_FILE="{tmp_path / "watchdog.log"}"',
            "log_warn() { :; }",
            "load_local_qa_runtime_control() { :; }",
            "kill_port_listeners() { :; }",
            f'kill_by_pattern_scoped() {{ printf "%s\\n" "$1" >> "{kills}"; }}',
            "port_has_listener() { return 1; }",
            extract_shell_function(BUILD_HELPER.read_text(encoding="utf-8"), "librechat_serves_compiled"),
            extract_shell_function(launcher, "restart_detached_librechat_backend"),
            "restart_detached_librechat_backend",
            "wait",
        ]
    )

    subprocess.run(
        ["bash", "-c", script],
        env={"PATH": f"{fake_bin}:/usr/bin:/bin", "VIVENTIUM_LIBRECHAT_SERVE_MODE": serve_mode},
        check=True,
        timeout=20,
    )
    deadline = time.monotonic() + 5
    while not npm_calls.exists() and time.monotonic() < deadline:
        time.sleep(0.05)

    assert npm_calls.read_text(encoding="utf-8").splitlines() == [expected]
    # Either profile's backend processes are stopped before the restart.
    stopped = kills.read_text(encoding="utf-8").splitlines()
    assert "npm run backend:dev" in stopped
    assert "npm run backend" in stopped
    assert "cross-env NODE_ENV=production node api/server/index.js" in stopped


def test_direct_start_and_stop_cover_the_compiled_profile() -> None:
    launcher = LAUNCHER.read_text(encoding="utf-8")

    backend_start = launcher.index("        if librechat_serves_compiled; then\n          npm run backend &")
    assert launcher.index("        else\n          npm run backend:dev &", backend_start) > backend_start
    assert (
        'npm run serve:compiled -- --host "$librechat_dev_host" --port "$LC_FRONTEND_PORT" --strictPort'
        in launcher
    )
    # The development servers stay the default branch.
    assert 'npm run dev -- --host "$librechat_dev_host" --port "$LC_FRONTEND_PORT"' in launcher
    # The same direct path prepares fresh build outputs before either server starts.
    direct = launcher.index("prepare_librechat_build_outputs || exit 1")
    assert direct < backend_start

    stop = extract_shell_function(launcher, "stop_running_services")
    for pattern in (
        "npm run backend",
        "cross-env NODE_ENV=production node api/server/index.js",
        "npm run serve:compiled",
        "vite preview",
    ):
        assert f'kill_by_pattern_scoped "{pattern}" "$LIBRECHAT_DIR"' in stop


def test_librechat_wrapper_and_scripts_serve_compiled_output() -> None:
    wrapper = (LIBRECHAT / "viventium-start.sh").read_text(encoding="utf-8")
    client_scripts = json.loads((LIBRECHAT / "client" / "package.json").read_text(encoding="utf-8"))[
        "scripts"
    ]
    root_scripts = json.loads((LIBRECHAT / "package.json").read_text(encoding="utf-8"))["scripts"]

    assert client_scripts["serve:compiled"] == "cross-env NODE_ENV=production vite preview"
    assert root_scripts["backend"] == "cross-env NODE_ENV=production node api/server/index.js"
    assert "BACKEND_NPM_SCRIPT=backend\n" in wrapper
    assert "FRONTEND_NPM_SCRIPT=serve:compiled\n" in wrapper
    assert "FRONTEND_PORT_POLICY=--strictPort\n" in wrapper
    assert 'npm run "$BACKEND_NPM_SCRIPT"' in wrapper
    assert 'npm run "$FRONTEND_NPM_SCRIPT" -- --host "${HOST}" --port "$LC_FRONTEND_PORT" $FRONTEND_PORT_POLICY' in wrapper
    # A compiled start never serves a bundle older than its client inputs.
    freshness = wrapper.index('elif [ "$LIBRECHAT_SERVE_MODE" = compiled ] && newer_source=$(find_newer_source "client/dist/index.html"')
    assert wrapper.index("build_client_bundle || exit 1", freshness) > freshness
    for source in ('"client/src"', '"client/package.json"', '"packages/client/dist"', '"packages/data-provider/dist"'):
        assert source in wrapper[freshness : wrapper.index("# === VIVENTIUM END ===", freshness)]
    result = subprocess.run(["bash", "-n", str(LIBRECHAT / "viventium-start.sh")], check=False)
    assert result.returncode == 0


@pytest.mark.parametrize(
    ("runtime_env", "expected"),
    [
        (
            "VIVENTIUM_LIBRECHAT_SERVE_MODE=compiled\n",
            "serve_mode=compiled backend_script=backend frontend_script=serve:compiled",
        ),
        (
            "VIVENTIUM_LOG_LEVEL=info\n",
            "serve_mode=development backend_script=backend:dev frontend_script=dev",
        ),
    ],
)
def test_direct_wrapper_start_takes_its_serving_profile_from_the_runtime_env(
    tmp_path, runtime_env: str, expected: str
) -> None:
    runtime = tmp_path / "runtime"
    (runtime / "service-env").mkdir(parents=True)
    (runtime / "runtime.env").write_text(runtime_env, encoding="utf-8")

    # A direct start that has only the generated runtime env: nothing exported by a launcher.
    result = subprocess.run(
        ["bash", str(LIBRECHAT / "viventium-start.sh"), "--print-serve-plan"],
        env={
            "PATH": "/usr/bin:/bin",
            "HOME": str(tmp_path),
            "VIVENTIUM_ENV_FILE": str(runtime / "runtime.env"),
        },
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines()[-1] == expected


def test_wrapper_selects_serving_only_after_every_supported_env_source() -> None:
    wrapper = (LIBRECHAT / "viventium-start.sh").read_text(encoding="utf-8")
    selection = wrapper.index("LIBRECHAT_SERVE_MODE=development\n")

    assert wrapper.count("LIBRECHAT_SERVE_MODE=development\n") == 1
    assert wrapper.index('load_env_file_preserving_existing "$explicit_env_file"') < selection
    assert wrapper.index('load_env_file_preserving_existing "$generated_env_file"') < selection
    assert wrapper.index("done < .env") < selection

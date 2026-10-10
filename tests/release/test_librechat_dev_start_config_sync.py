from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
LIBRECHAT_START_PATH = REPO_ROOT / "viventium_v0_4" / "LibreChat" / "viventium-start.sh"
FULL_STACK_LAUNCHER_PATH = REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh"


def test_direct_librechat_dev_start_syncs_source_of_truth_config() -> None:
    launcher_text = LIBRECHAT_START_PATH.read_text(encoding="utf-8")

    assert "sync_viventium_librechat_config() {" in launcher_text
    assert 'viventium/source_of_truth/local.librechat.yaml' in launcher_text
    assert 'local target_config="$PROJECT_DIR/librechat.yaml"' in launcher_text
    assert 'cmp -s "$source_config" "$target_config"' in launcher_text
    assert 'grep -q "promptRef:" "$source_config"' in launcher_text
    assert "Viventium prompt registry compiler is required" in launcher_text
    assert "sync_viventium_librechat_config" in launcher_text


def test_direct_librechat_dev_start_remains_valid_bash() -> None:
    subprocess.run(["bash", "-n", str(LIBRECHAT_START_PATH)], check=True)


def test_direct_librechat_dev_start_preserves_explicitly_empty_runtime_values(
    tmp_path: Path,
) -> None:
    launcher_text = LIBRECHAT_START_PATH.read_text(encoding="utf-8")
    function_source = (
        "load_env_file_preserving_existing() {"
        + launcher_text.split("load_env_file_preserving_existing() {", 1)[1].split(
            "\n}", 1
        )[0]
        + "\n}"
    )
    env_file = tmp_path / "generated.env"
    env_file.write_text(
        "EXPLICIT_EMPTY=canonical-value\n"
        "EXISTING_VALUE=canonical-value\n"
        "MISSING_VALUE=canonical-value\n",
        encoding="utf-8",
    )
    probe = subprocess.run(
        [
            "bash",
            "-c",
            function_source
            + '\nEXPLICIT_EMPTY=""\n'
            + 'EXISTING_VALUE="caller-value"\n'
            + 'load_env_file_preserving_existing "$1" "test" >/dev/null\n'
            + "printf '%s|%s|%s' \"${EXPLICIT_EMPTY+x}:${EXPLICIT_EMPTY}\" "
            + '"$EXISTING_VALUE" "$MISSING_VALUE"\n',
            "bash",
            str(env_file),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert probe.stdout == "x:|caller-value|canonical-value"


def test_direct_librechat_dev_start_explicit_runtime_root_is_a_shell_isolation_boundary(
    tmp_path: Path,
) -> None:
    launcher_text = LIBRECHAT_START_PATH.read_text(encoding="utf-8")
    loader_sequence = (
        "load_env_file_preserving_existing() {"
        + launcher_text.split("load_env_file_preserving_existing() {", 1)[1].split(
            "# === VIVENTIUM START ===\n# Feature: Keep direct LibreChat dev starts aligned",
            1,
        )[0]
    )
    explicit_runtime_env = tmp_path / "sibling-runtime.env"
    explicit_runtime_env.write_text(
        "RAG_API_URL=''\nMONGO_URI=mongodb://sibling.invalid/test\n",
        encoding="utf-8",
    )
    sibling_service_env = tmp_path / "service-env" / "librechat.env"
    sibling_service_env.parent.mkdir()
    sibling_service_env.write_text(
        "RAG_API_URL=http://sibling-service.invalid\n"
        "OPENID_ISSUER=https://sibling-issuer.invalid\n",
        encoding="utf-8",
    )
    fake_home = tmp_path / "home"
    installed_env = (
        fake_home
        / "Library"
        / "Application Support"
        / "Viventium"
        / "runtime"
        / "service-env"
        / "librechat.env"
    )
    installed_env.parent.mkdir(parents=True)
    installed_env.write_text(
        "RAG_API_URL=http://installed.invalid\n"
        "MONGO_URI=mongodb://installed.invalid/test\n"
        "PRODUCTION_ONLY=must-not-cross\n",
        encoding="utf-8",
    )
    component_dir = tmp_path / "component"
    component_dir.mkdir()
    (component_dir / ".env").write_text(
        "RAG_API_URL=http://component.invalid\n"
        "MONGO_URI=mongodb://component.invalid/test\n"
        "COMPONENT_ONLY=must-not-cross\n",
        encoding="utf-8",
    )
    probe = subprocess.run(
        [
            "bash",
            "-c",
            loader_sequence
            + "\nprintf '%s|%s|%s|%s|%s' "
            + "\"${RAG_API_URL+x}:${RAG_API_URL}\" \"$MONGO_URI\" "
            + "\"$OPENID_ISSUER\" \"${PRODUCTION_ONLY+x}\" \"${COMPONENT_ONLY+x}\"\n",
        ],
        cwd=component_dir,
        env={
            "HOME": str(fake_home),
            "PATH": "/usr/bin:/bin",
            "PYTHON_BIN": sys.executable,
            "VIVENTIUM_ENV_FILE": str(explicit_runtime_env),
        },
        check=True,
        capture_output=True,
        text=True,
    )

    assert probe.stdout.endswith(
        "x:|mongodb://sibling.invalid/test|https://sibling-issuer.invalid||"
    )


def test_direct_librechat_dev_start_without_explicit_runtime_keeps_fallback_loading(
    tmp_path: Path,
) -> None:
    launcher_text = LIBRECHAT_START_PATH.read_text(encoding="utf-8")
    loader_sequence = (
        "load_env_file_preserving_existing() {"
        + launcher_text.split("load_env_file_preserving_existing() {", 1)[1].split(
            "# === VIVENTIUM START ===\n# Feature: Keep direct LibreChat dev starts aligned",
            1,
        )[0]
    )
    fake_home = tmp_path / "home"
    installed_env = (
        fake_home
        / "Library"
        / "Application Support"
        / "Viventium"
        / "runtime"
        / "service-env"
        / "librechat.env"
    )
    installed_env.parent.mkdir(parents=True)
    installed_env.write_text(
        "SOURCE_ORDER=installed\nINSTALLED_ONLY=installed-value\n",
        encoding="utf-8",
    )
    component_dir = tmp_path / "component"
    component_dir.mkdir()
    (component_dir / ".env").write_text(
        "SOURCE_ORDER=component\nCOMPONENT_ONLY=component-value\n",
        encoding="utf-8",
    )
    probe = subprocess.run(
        [
            "bash",
            "-c",
            loader_sequence
            + "\nprintf '%s|%s|%s' \"$SOURCE_ORDER\" \"$INSTALLED_ONLY\" \"$COMPONENT_ONLY\"\n",
        ],
        cwd=component_dir,
        env={
            "HOME": str(fake_home),
            "PATH": "/usr/bin:/bin",
            "PYTHON_BIN": sys.executable,
        },
        check=True,
        capture_output=True,
        text=True,
    )

    assert probe.stdout.endswith("installed|installed-value|component-value")


def test_direct_librechat_dev_start_compiles_prompt_registry_bundle() -> None:
    launcher_text = LIBRECHAT_START_PATH.read_text(encoding="utf-8")

    assert "ensure_viventium_prompt_bundle() {" in launcher_text
    assert "scripts/viventium/prompt_registry.py" in launcher_text
    assert 'PYTHON_BIN="${VIVENTIUM_PYTHON_BIN:-${PYTHON_BIN:-python3}}"' in launcher_text
    assert '"$PROMPT_REGISTRY_PYTHON" "$prompt_registry_script" --json-out "$target"' in launcher_text
    assert (
        '"$PROMPT_REGISTRY_PYTHON" - "$source_config" "$target_config" "$prompt_registry_script"'
        in launcher_text
    )
    assert 'export VIVENTIUM_PROMPT_BUNDLE_PATH="$target"' in launcher_text
    assert "ensure_viventium_prompt_bundle" in launcher_text


def test_full_stack_launcher_compiles_prompt_registry_bundle() -> None:
    launcher_text = FULL_STACK_LAUNCHER_PATH.read_text(encoding="utf-8")

    assert "scripts/viventium/prompt_registry.py" in launcher_text
    assert "ensure_python_requirements_file" in launcher_text
    assert "scripts/viventium/requirements-installer.txt" in launcher_text
    assert '"$PYTHON_BIN" "$prompt_registry_script" --json-out "$prompt_bundle_target"' in launcher_text
    assert 'export VIVENTIUM_PROMPT_BUNDLE_PATH="$prompt_bundle_target"' in launcher_text
    assert "Prompt registry bundle generated at $prompt_bundle_target" in launcher_text
    subprocess.run(["bash", "-n", str(FULL_STACK_LAUNCHER_PATH)], check=True)


def test_full_stack_launcher_binds_librechat_host_deterministically() -> None:
    launcher_text = FULL_STACK_LAUNCHER_PATH.read_text(encoding="utf-8")

    assert "HOST=127.0.0.1" in launcher_text
    assert 'upsert_env_kv "$env_file" "HOST" "127.0.0.1"' in launcher_text
    assert 'export HOST="127.0.0.1"' in launcher_text
    subprocess.run(["bash", "-n", str(FULL_STACK_LAUNCHER_PATH)], check=True)


def test_compiled_config_start_preserves_compiler_ownership(tmp_path: Path) -> None:
    """The normal launcher must not call the template-rewriting wrapper for compiled config."""
    launcher = FULL_STACK_LAUNCHER_PATH.read_text(encoding="utf-8")
    selector = launcher.split("  USE_LIBRECHAT_WRAPPER=false", 1)[1].split(
        '\n  if [[ "$USE_LIBRECHAT_WRAPPER" == "true" ]]; then', 1
    )[0]
    (tmp_path / "viventium-start.sh").write_text("#!/bin/sh\nexit 0\n")
    for generated, expected in [("1", "false"), ("true", "false"), ("0", "true"), ("false", "true")]:
        probe = subprocess.run(
            ["bash", "-c", '''
truthy_env_value() { [[ "$1" == 1 || "$1" == true ]]; }
detached_start_requested() { return 1; }
should_rebuild_librechat_packages() { return 1; }
log_info() { :; }
log_warn() { :; }
mongosh() { :; }
LIBRECHAT_DIR="$1"
VIVENTIUM_USE_GENERATED_LIBRECHAT_YAML="$2"
LIBRECHAT_BACKEND_ALREADY_RUNNING=false
LIBRECHAT_FRONTEND_ALREADY_RUNNING=false
LIBRECHAT_BACKEND_START_BLOCKED=false
LIBRECHAT_FRONTEND_START_BLOCKED=false
USE_LIBRECHAT_WRAPPER=false
''' + selector + '\nprintf "%s" "$USE_LIBRECHAT_WRAPPER"\n', "bash", str(tmp_path), generated],
            capture_output=True, text=True, check=True,
        )
        assert probe.stdout == expected, (generated, probe.stdout)


@pytest.mark.parametrize(
    "mode",
    [
        "selected_reuse",
        "selected_missing_config",
        "selected_missing_bundle",
        "selected_missing_selected_owner",
        "legacy_unset",
        "legacy_false",
    ],
)
def test_full_stack_renderer_preserves_selected_compiler_artifacts(
    tmp_path: Path, mode: str
) -> None:
    launcher = FULL_STACK_LAUNCHER_PATH.read_text(encoding="utf-8")
    truthy = "truthy_env_value() {" + launcher.split("truthy_env_value() {", 1)[1].split(
        "\n}\n", 1
    )[0] + "\n}\n"
    renderer = "render_librechat_config() {" + launcher.split(
        "render_librechat_config() {", 1
    )[1].split("\nupsert_env_kv() {", 1)[0]

    public_root = tmp_path / "public"
    component = (
        tmp_path / "owned" / "source" / "LibreChat"
        if mode.startswith("selected")
        else public_root / "viventium_v0_4" / "LibreChat"
    )
    component.mkdir(parents=True)
    logs = tmp_path / "logs"
    logs.mkdir()
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    registry = public_root / "scripts" / "viventium" / "prompt_registry.py"
    registry.parent.mkdir(parents=True)
    registry.write_text(
        "import json,sys,yaml\n"
        "from pathlib import Path\n"
        "def load_and_resolve_prompt_refs(value):return value\n"
        'if __name__=="__main__":'
        'Path(sys.argv[2]).write_text(json.dumps({"legacy_registry_called":True}))\n',
        encoding="utf-8",
    )
    (component / "librechat.yaml").write_text(
        "version: 1.3.0\n"
        "endpoints:\n  custom:\n    - name: legacy-template\n"
        'mcpServers:\n  fixture:\n    url: "${SCHEDULING_MCP_URL}"\n',
        encoding="utf-8",
    )
    compiled = runtime / "librechat.yaml"
    compiled.write_text(
        "version: 1.3.0\nendpoints:\n  custom:\n    - name: compiled-model\n",
        encoding="utf-8",
    )
    bundle = runtime / "prompt-bundle.json"
    bundle.write_text('{"prompt_count":97,"compiled_fixture":true}\n', encoding="utf-8")
    compiled_before, bundle_before = compiled.read_bytes(), bundle.read_bytes()
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "PYTHON_BIN": sys.executable,
        "VIVENTIUM_CORE_DIR": str(public_root),
        "LIBRECHAT_DIR": str(component),
        "LOG_ROOT": str(logs),
        "SCHEDULING_MCP_URL": "https://scheduling.invalid/mcp",
        "VIVENTIUM_PROMPT_BUNDLE_PATH": str(bundle),
    }
    if mode.startswith("selected"):
        env.update(
            VIVENTIUM_USE_GENERATED_LIBRECHAT_YAML="1",
            LIBRECHAT_LOCAL_SOURCE_OF_TRUTH=str(compiled),
        )
    elif mode == "legacy_false":
        env["VIVENTIUM_USE_GENERATED_LIBRECHAT_YAML"] = "false"
    if mode == "selected_missing_config":
        compiled.unlink()
    if mode == "selected_missing_bundle":
        bundle.unlink()
    if mode == "selected_missing_selected_owner":
        env.pop("LIBRECHAT_LOCAL_SOURCE_OF_TRUTH")
    probe = subprocess.run(
        [
            "bash",
            "-c",
            truthy + renderer + "\n"
            "log_info(){ :; };log_warn(){ :; };log_error(){ :; };\n"
            "render_librechat_config\nrc=$?\n"
            'printf "PROBE_STATUS=%s\\nPROBE_CONFIG=%s\\n" "$rc" "${CONFIG_PATH:-}"\n'
            'exit "$rc"\n',
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    facts = dict(
        line.split("=", 1)
        for line in probe.stdout.splitlines()
        if line.startswith("PROBE_")
    )
    generated = logs / "librechat.generated.yaml"
    if mode == "selected_reuse":
        assert probe.returncode == 0, probe.stderr
        assert facts["PROBE_CONFIG"] == str(compiled)
        assert compiled.read_bytes() == compiled_before
        assert bundle.read_bytes() == bundle_before
        assert not generated.exists()
    elif mode.startswith("selected_missing"):
        assert probe.returncode == 1, probe.stderr
        assert not facts.get("PROBE_CONFIG")
        assert not generated.exists()
    else:
        assert probe.returncode == 0, probe.stderr
        assert facts["PROBE_CONFIG"] == str(generated)
        assert "https://scheduling.invalid/mcp" in generated.read_text(encoding="utf-8")
        assert json.loads(bundle.read_text(encoding="utf-8"))["legacy_registry_called"] is True

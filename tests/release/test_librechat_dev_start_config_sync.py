from __future__ import annotations

import subprocess
from pathlib import Path


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


def test_direct_librechat_dev_start_compiles_prompt_registry_bundle() -> None:
    launcher_text = LIBRECHAT_START_PATH.read_text(encoding="utf-8")

    assert "resolve_prompt_registry_python() {" in launcher_text
    assert '"$candidate" -c "import yaml"' in launcher_text
    assert 'PROMPT_REGISTRY_PYTHON="$(resolve_prompt_registry_python)"' in launcher_text
    assert "ensure_viventium_prompt_bundle() {" in launcher_text
    assert "scripts/viventium/prompt_registry.py" in launcher_text
    assert '"$PROMPT_REGISTRY_PYTHON" "$prompt_registry_script" --json-out "$target"' in launcher_text
    assert 'export VIVENTIUM_PROMPT_BUNDLE_PATH="$target"' in launcher_text
    assert "ensure_viventium_prompt_bundle" in launcher_text


def test_full_stack_launcher_compiles_prompt_registry_bundle() -> None:
    launcher_text = FULL_STACK_LAUNCHER_PATH.read_text(encoding="utf-8")

    assert "scripts/viventium/prompt_registry.py" in launcher_text
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
            "# === VIVENTIUM START ===\n# Feature: Reuse Viventium's validated Python",
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
            "# === VIVENTIUM START ===\n# Feature: Reuse Viventium's validated Python",
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
        env={"HOME": str(fake_home), "PATH": "/usr/bin:/bin"},
        check=True,
        capture_output=True,
        text=True,
    )

    assert probe.stdout.endswith("installed|installed-value|component-value")

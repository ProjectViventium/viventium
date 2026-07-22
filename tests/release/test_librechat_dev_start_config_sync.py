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

    assert "ensure_viventium_prompt_bundle() {" in launcher_text
    assert "scripts/viventium/prompt_registry.py" in launcher_text
    assert 'PYTHON_BIN="${VIVENTIUM_PYTHON_BIN:-${PYTHON_BIN:-python3}}"' in launcher_text
    assert '"$PYTHON_BIN" "$prompt_registry_script" --json-out "$target"' in launcher_text
    assert '"$PYTHON_BIN" - "$source_config" "$target_config" "$prompt_registry_script"' in launcher_text
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

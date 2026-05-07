from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
LIBRECHAT_START_PATH = REPO_ROOT / "viventium_v0_4" / "LibreChat" / "viventium-start.sh"


def test_direct_librechat_dev_start_syncs_source_of_truth_config() -> None:
    launcher_text = LIBRECHAT_START_PATH.read_text(encoding="utf-8")

    assert "sync_viventium_librechat_config() {" in launcher_text
    assert 'viventium/source_of_truth/local.librechat.yaml' in launcher_text
    assert 'local target_config="$PROJECT_DIR/librechat.yaml"' in launcher_text
    assert 'cmp -s "$source_config" "$target_config"' in launcher_text
    assert 'cp "$source_config" "$target_config"' in launcher_text
    assert "sync_viventium_librechat_config" in launcher_text


def test_direct_librechat_dev_start_remains_valid_bash() -> None:
    subprocess.run(["bash", "-n", str(LIBRECHAT_START_PATH)], check=True)

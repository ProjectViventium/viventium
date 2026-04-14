from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
LAUNCHER_PATH = REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh"


def test_launcher_rebuild_contract_covers_api_source_freshness() -> None:
    launcher_text = LAUNCHER_PATH.read_text(encoding="utf-8")

    assert "find_librechat_source_newer_than_dist() {" in launcher_text
    assert '"$LIBRECHAT_DIR/packages/api/dist/index.js"' in launcher_text
    assert '"$LIBRECHAT_DIR/packages/api/src"' in launcher_text
    assert '"$LIBRECHAT_DIR/packages/api/rollup.config.js"' in launcher_text
    assert '"$LIBRECHAT_DIR/packages/api/package.json"' in launcher_text

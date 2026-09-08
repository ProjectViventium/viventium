from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
LAUNCHER_PATH = REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh"


def test_launcher_rebuild_contract_covers_api_source_freshness() -> None:
    launcher_text = LAUNCHER_PATH.read_text(encoding="utf-8") + (
        REPO_ROOT / "scripts/viventium/librechat_build.sh"
    ).read_text(encoding="utf-8")

    assert "find_librechat_source_newer_than_dist() {" in launcher_text
    assert '"$LIBRECHAT_DIR/packages/api/dist/index.js"' in launcher_text
    assert '"$LIBRECHAT_DIR/packages/api/src"' in launcher_text
    assert '"$LIBRECHAT_DIR/packages/api/rollup.config.js"' in launcher_text
    assert '"$LIBRECHAT_DIR/packages/api/package.json"' in launcher_text


def test_launcher_uses_librechats_declared_npm_for_dependency_installs() -> None:
    launcher_text = LAUNCHER_PATH.read_text(encoding="utf-8") + (
        REPO_ROOT / "scripts/viventium/librechat_build.sh"
    ).read_text(encoding="utf-8")

    assert "run_librechat_npm() {" in launcher_text
    assert "corepack npm \"$@\"" in launcher_text
    assert "run_librechat_npm ci" in launcher_text
    assert "run_librechat_npm install" in launcher_text


def test_direct_start_prepares_sandpack_even_when_bundles_are_current(tmp_path) -> None:
    import subprocess

    owner = REPO_ROOT / "scripts/viventium/librechat_build.sh"
    script = r"""
source "$1"
ensure_librechat_server_packages_ready() { return 0; }
should_rebuild_librechat_client_bundle() { return 1; }
should_rebuild_librechat_client_package() { return 1; }
node() { printf '%s\n' "$1" > "$PROBE"; return "$PREPARE_STATUS"; }
prepare_librechat_build_outputs
"""
    for status in (0, 7):
        probe = tmp_path / f"prepare-{status}"
        result = subprocess.run(
            ["bash", "-c", script, "test", str(owner)],
            env={"PATH": "/usr/bin:/bin", "LIBRECHAT_DIR": str(tmp_path),
                 "PROBE": str(probe), "PREPARE_STATUS": str(status)},
            capture_output=True, text=True,
        )
        assert probe.read_text().strip() == str(tmp_path / "client/scripts/prepare-local-sandpack-bundler.cjs")
        assert result.returncode == (0 if status == 0 else 1)

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
BOOTSTRAP_COMPONENTS_SPEC = importlib.util.spec_from_file_location(
    "viventium_bootstrap_components",
    REPO_ROOT / "scripts/viventium/bootstrap_components.py",
)
assert BOOTSTRAP_COMPONENTS_SPEC and BOOTSTRAP_COMPONENTS_SPEC.loader
bootstrap_components = importlib.util.module_from_spec(BOOTSTRAP_COMPONENTS_SPEC)
BOOTSTRAP_COMPONENTS_SPEC.loader.exec_module(bootstrap_components)


def make_component(path: str) -> dict[str, str]:
    return {
        "name": "LibreChat",
        "origin": "https://github.com/ProjectViventium/viventium-librechat.git",
        "ref": "main",
        "path": path,
    }


def test_clone_or_update_component_accepts_bootable_vendored_checkout(tmp_path: Path) -> None:
    target_dir = tmp_path / "viventium_v0_4" / "LibreChat"
    target_dir.mkdir(parents=True)
    (target_dir / "package.json").write_text('{"name":"librechat"}\n', encoding="utf-8")

    result = bootstrap_components.clone_or_update_component(
        tmp_path,
        make_component("viventium_v0_4/LibreChat"),
        update_existing=True,
    )

    assert result == f"kept vendored checkout for LibreChat -> {target_dir}"


def test_validate_component_accepts_bootable_vendored_checkout(tmp_path: Path) -> None:
    target_dir = tmp_path / "viventium_v0_4" / "LibreChat"
    target_dir.mkdir(parents=True)
    (target_dir / "api" / "server").mkdir(parents=True)
    (target_dir / "api" / "server" / "index.js").write_text("// bootable\n", encoding="utf-8")

    result = bootstrap_components.validate_component(
        tmp_path,
        make_component("viventium_v0_4/LibreChat"),
    )

    assert result == f"validated vendored checkout for LibreChat -> {target_dir}"


def test_validate_component_rejects_non_git_non_bootable_path(tmp_path: Path) -> None:
    target_dir = tmp_path / "viventium_v0_4" / "LibreChat"
    target_dir.mkdir(parents=True)
    (target_dir / "README.txt").write_text("not enough to bootstrap\n", encoding="utf-8")

    with pytest.raises(SystemExit, match="Existing path is not a git repo"):
        bootstrap_components.validate_component(
            tmp_path,
            make_component("viventium_v0_4/LibreChat"),
        )

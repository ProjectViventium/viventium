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


def make_component(path: str, name: str = "LibreChat") -> dict[str, str]:
    return {
        "name": name,
        "origin": f"https://github.com/ProjectViventium/{name}.git",
        "ref": "main",
        "path": path,
    }


def default_voice_components() -> list[dict[str, str]]:
    return [
        make_component("viventium_v0_4/LibreChat", "LibreChat"),
        make_component("viventium_v0_4/agents-playground", "agents-playground"),
        make_component("viventium_v0_4/agent-starter-react", "agent-starter-react"),
        make_component("viventium_v0_4/google_workspace_mcp", "google_workspace_mcp"),
    ]


def selected_component_names(config: dict) -> set[str]:
    return {
        component["name"]
        for component in bootstrap_components.select_components(default_voice_components(), config)
    }


def test_select_components_without_config_uses_public_modern_playground_default() -> None:
    names = selected_component_names({})

    assert names == {"LibreChat", "agent-starter-react"}


def test_select_components_defaults_to_modern_playground_for_voice_enabled_runtime() -> None:
    names = selected_component_names({"voice": {"mode": "local"}, "runtime": {}})

    assert names == {"LibreChat", "agent-starter-react"}


def test_select_components_keeps_classic_playground_opt_in_only() -> None:
    names = selected_component_names(
        {"voice": {"mode": "local"}, "runtime": {"playground_variant": "classic"}}
    )

    assert names == {"LibreChat", "agents-playground"}


def test_select_components_skips_playgrounds_when_voice_is_disabled() -> None:
    names = selected_component_names(
        {"voice": {"mode": "disabled"}, "runtime": {"playground_variant": "classic"}}
    )

    assert names == {"LibreChat"}


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

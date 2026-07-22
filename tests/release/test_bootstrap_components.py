from __future__ import annotations

import importlib.util
import json
import subprocess
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
UPGRADE_CHECK_SPEC = importlib.util.spec_from_file_location(
    "viventium_upgrade_check_for_bootstrap_tests",
    REPO_ROOT / "scripts/viventium/upgrade_check.py",
)
assert UPGRADE_CHECK_SPEC and UPGRADE_CHECK_SPEC.loader
upgrade_check = importlib.util.module_from_spec(UPGRADE_CHECK_SPEC)
UPGRADE_CHECK_SPEC.loader.exec_module(upgrade_check)


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
        make_component("viventium_v0_4/GlassHive", "GlassHive"),
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


def test_select_components_fetches_glasshive_when_enabled() -> None:
    names = selected_component_names(
        {
            "voice": {"mode": "local"},
            "runtime": {"playground_variant": "modern"},
            "integrations": {"glasshive": {"enabled": True}},
        }
    )

    assert names == {"LibreChat", "agent-starter-react", "GlassHive"}


def test_select_components_skips_glasshive_when_disabled() -> None:
    names = selected_component_names(
        {
            "voice": {"mode": "local"},
            "runtime": {"playground_variant": "modern"},
            "integrations": {"glasshive": {"enabled": False}},
        }
    )

    assert names == {"LibreChat", "agent-starter-react"}


@pytest.mark.parametrize(
    "body",
    [
        "voice: {mode: disabled}\n",
        "voice: &voice_defaults\n  mode: disabled\n",
        "integrations:\n  glasshive: {enabled: true}\n",
        "integrations:\n  glasshive:\n    enabled:\n      unexpected: true\n",
        "---\nvoice:\n  mode: disabled\n---\nintegrations:\n  glasshive:\n    enabled: true\n",
    ],
)
def test_component_selection_unsupported_yaml_fails_closed_in_inspector_and_bootstrap(
    tmp_path: Path,
    body: str,
) -> None:
    config = tmp_path / "config.yaml"
    config.write_text(body, encoding="utf-8")

    with pytest.raises(ValueError):
        upgrade_check.load_component_selection_config(config)
    with pytest.raises(ValueError):
        bootstrap_components.load_config(config)


def test_component_selection_supported_yaml_has_one_shared_result(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text(
        "voice:\n"
        "  mode: disabled\n"
        "runtime:\n"
        "  playground_variant: classic\n"
        "integrations:\n"
        "  glasshive:\n"
        "    enabled: true\n",
        encoding="utf-8",
    )

    inspected = upgrade_check.load_component_selection_config(config)
    bootstrapped = bootstrap_components.load_config(config)

    assert inspected == bootstrapped
    assert selected_component_names(inspected) == selected_component_names(bootstrapped)


def test_config_without_selection_fields_preserves_mutating_yaml_defaults(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text("version: 1\ninstall:\n  mode: native\n", encoding="utf-8")

    inspected = upgrade_check.load_component_selection_config(config)
    bootstrapped = bootstrap_components.load_config(config)

    assert inspected == bootstrapped == {}
    assert selected_component_names(inspected) == {"LibreChat"}
    assert selected_component_names(bootstrapped) == {"LibreChat"}


def test_absent_config_selects_the_same_components_for_inspector_and_bootstrap(tmp_path: Path) -> None:
    components = default_voice_components()
    expected_names = {
        component["name"]
        for component in bootstrap_components.select_components(
            components,
            bootstrap_components.load_config(None),
        )
    }
    lock_components = [
        {
            **component,
            "ref": f"{index + 1:x}" * 40,
        }
        for index, component in enumerate(components)
    ]
    (tmp_path / "components.lock.json").write_text(
        json.dumps({"components": lock_components}) + "\n",
        encoding="utf-8",
    )

    blockers, refresh_required = upgrade_check.component_alignment(tmp_path)

    assert blockers == []
    assert {item["name"] for item in refresh_required} == expected_names


def test_missing_component_selection_config_fails_closed_in_both_paths(tmp_path: Path) -> None:
    missing_config = tmp_path / "missing-config.yaml"
    (tmp_path / "components.lock.json").write_text(
        '{"components": []}\n',
        encoding="utf-8",
    )

    with pytest.raises(OSError):
        bootstrap_components.load_config(missing_config)

    blockers, refresh_required = upgrade_check.component_alignment(
        tmp_path,
        missing_config,
    )
    assert refresh_required == []
    assert blockers == [
        {
            "actual": "FileNotFoundError",
            "expected": "valid component selection config",
            "name": "config.yaml",
            "status": "component_selection_failed",
        }
    ]


def test_inspector_blocks_missing_checkout_without_a_locked_origin(tmp_path: Path) -> None:
    expected_ref = "1" * 40
    (tmp_path / "components.lock.json").write_text(
        '{"components": [{"name": "LibreChat", "path": "component", '
        f'"ref": "{expected_ref}"}}]}}\n',
        encoding="utf-8",
    )

    blockers, refresh_required = upgrade_check.component_alignment(tmp_path)

    assert refresh_required == []
    assert blockers == [
        {
            "actual": "",
            "expected": expected_ref,
            "name": "LibreChat",
            "path": "component",
            "status": "invalid_origin",
        }
    ]


def test_component_origin_identity_normalizes_supported_github_transports() -> None:
    https_identity = bootstrap_components.canonical_repository_identity(
        "https://github.com/ProjectViventium/viventium-librechat.git"
    )

    assert https_identity == bootstrap_components.canonical_repository_identity(
        "git@github.com:ProjectViventium/viventium-librechat.git"
    )
    assert https_identity == bootstrap_components.canonical_repository_identity(
        "ssh://git@github.com/ProjectViventium/viventium-librechat.git"
    )
    assert (
        bootstrap_components.canonical_repository_identity(
            "https://github.com/ProjectViventium/viventium-librechat.git?unexpected=1"
        )
        is None
    )


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


def test_bootstrap_rejects_unrelated_component_origin_before_fetch_or_checkout(
    tmp_path: Path,
) -> None:
    expected_source = tmp_path / "expected-source"
    expected_source.mkdir()
    subprocess.run(["git", "init"], cwd=expected_source, check=True, capture_output=True)
    (expected_source / "expected.txt").write_text("expected\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=expected_source, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Viventium QA",
            "-c",
            "user.email=qa@example.invalid",
            "commit",
            "-m",
            "expected",
        ],
        cwd=expected_source,
        check=True,
        capture_output=True,
    )
    expected_ref = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=expected_source,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    unrelated_origin = tmp_path / "unrelated.git"
    subprocess.run(
        ["git", "init", "--bare", str(unrelated_origin)],
        check=True,
        capture_output=True,
    )
    target_dir = tmp_path / "component"
    target_dir.mkdir()
    subprocess.run(["git", "init"], cwd=target_dir, check=True, capture_output=True)
    (target_dir / "local.txt").write_text("unrelated local checkout\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=target_dir, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Viventium QA",
            "-c",
            "user.email=qa@example.invalid",
            "commit",
            "-m",
            "unrelated",
        ],
        cwd=target_dir,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "remote", "add", "origin", str(unrelated_origin)],
        cwd=target_dir,
        check=True,
    )
    original_head = bootstrap_components.current_head(target_dir)

    with pytest.raises(SystemExit, match="unrelated origin"):
        bootstrap_components.clone_or_update_component(
            tmp_path,
            {
                "name": "LibreChat",
                "origin": str(expected_source),
                "ref": expected_ref,
                "path": "component",
            },
            update_existing=True,
        )

    assert bootstrap_components.current_head(target_dir) == original_head
    assert subprocess.run(
        ["git", "remote"],
        cwd=target_dir,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines() == ["origin"]


def test_local_source_clone_preserves_locked_origin_for_future_validation(tmp_path: Path) -> None:
    source_root = tmp_path / "source-root"
    source_repo = source_root / "component"
    source_repo.mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=source_repo, check=True, capture_output=True)
    (source_repo / "component.txt").write_text("component\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=source_repo, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Viventium QA",
            "-c",
            "user.email=qa@example.invalid",
            "commit",
            "-m",
            "component",
        ],
        cwd=source_repo,
        check=True,
        capture_output=True,
    )
    expected_ref = bootstrap_components.current_head(source_repo)
    locked_origin = "https://github.com/ProjectViventium/LibreChat.git"
    destination_root = tmp_path / "destination"
    destination_root.mkdir()
    component = bootstrap_components.apply_local_origin_overrides(
        [
            {
                "name": "LibreChat",
                "origin": locked_origin,
                "ref": expected_ref,
                "path": "component",
            }
        ],
        source_root,
    )[0]

    bootstrap_components.clone_or_update_component(
        destination_root,
        component,
        update_existing=True,
    )

    target_dir = destination_root / "component"
    actual_origin = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=target_dir,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert actual_origin == locked_origin
    assert bootstrap_components.validate_component(destination_root, component).startswith(
        "validated"
    )

from __future__ import annotations

import importlib.util
import hashlib
import json
import subprocess
import sys
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
REPO_PATH_SAFETY_SPEC = importlib.util.spec_from_file_location(
    "viventium_repo_path_safety",
    REPO_ROOT / "scripts/viventium/repo_path_safety.py",
)
assert REPO_PATH_SAFETY_SPEC and REPO_PATH_SAFETY_SPEC.loader
repo_path_safety = importlib.util.module_from_spec(REPO_PATH_SAFETY_SPEC)
REPO_PATH_SAFETY_SPEC.loader.exec_module(repo_path_safety)
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


def make_local_component_source(path: Path) -> str:
    path.mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    (path / "component.txt").write_text("component\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
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
        cwd=path,
        check=True,
        capture_output=True,
    )
    return bootstrap_components.current_head(path)


def default_voice_components() -> list[dict[str, str]]:
    return [
        make_component("viventium_v0_4/LibreChat", "LibreChat"),
        make_component("viventium_v0_4/agents-playground", "agents-playground"),
        make_component("viventium_v0_4/agent-starter-react", "agent-starter-react"),
        make_component("viventium_v0_4/Viventium-Health", "Viventium-Health"),
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

    assert names == {"LibreChat", "agent-starter-react", "Viventium-Health"}


def test_select_components_defaults_to_modern_playground_for_voice_enabled_runtime() -> None:
    names = selected_component_names({"voice": {"mode": "local"}, "runtime": {}})

    assert names == {"LibreChat", "agent-starter-react", "Viventium-Health"}


def test_select_components_keeps_classic_playground_opt_in_only() -> None:
    names = selected_component_names(
        {"voice": {"mode": "local"}, "runtime": {"playground_variant": "classic"}}
    )

    assert names == {"LibreChat", "agents-playground", "Viventium-Health"}


def test_select_components_skips_playgrounds_when_voice_is_disabled() -> None:
    names = selected_component_names(
        {"voice": {"mode": "disabled"}, "runtime": {"playground_variant": "classic"}}
    )

    assert names == {"LibreChat", "Viventium-Health"}


def test_select_components_fetches_glasshive_when_enabled() -> None:
    names = selected_component_names(
        {
            "voice": {"mode": "local"},
            "runtime": {"playground_variant": "modern"},
            "integrations": {"glasshive": {"enabled": True}},
        }
    )

    assert names == {"LibreChat", "agent-starter-react", "Viventium-Health", "GlassHive"}


@pytest.mark.parametrize("validate_only", [False, True])
@pytest.mark.parametrize("link_level", ["component", "ancestor"])
def test_component_root_symlink_escape_is_rejected_before_git_or_file_mutation(
    tmp_path: Path,
    validate_only: bool,
    link_level: str,
) -> None:
    repo = tmp_path / "repo"
    external = tmp_path / "external"
    repo.mkdir()
    external.mkdir()
    if link_level == "ancestor":
        (repo / "viventium_v0_4").symlink_to(
            external,
            target_is_directory=True,
        )
    else:
        (repo / "viventium_v0_4").mkdir()
        (repo / "viventium_v0_4" / "LibreChat").symlink_to(
            external,
            target_is_directory=True,
        )
    component = make_component("viventium_v0_4/LibreChat")

    with pytest.raises(SystemExit, match="unsafe linked component path"):
        if validate_only:
            bootstrap_components.validate_component(repo, component)
        else:
            bootstrap_components.clone_or_update_component(
                repo,
                component,
                update_existing=True,
            )

    assert list(external.iterdir()) == []


def test_repo_source_file_rejects_internal_parent_symlink_escape(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    librechat = repo / "viventium_v0_4" / "LibreChat"
    (librechat / "viventium").mkdir(parents=True)
    external = tmp_path / "external"
    external.mkdir()
    bundle = external / "local.viventium-agents.yaml"
    bundle.write_text("mainAgent: []\n", encoding="utf-8")
    linked_parent = librechat / "viventium" / "source_of_truth"
    linked_parent.symlink_to(external, target_is_directory=True)

    with pytest.raises(
        repo_path_safety.RepoPathSafetyError,
        match="linked path component",
    ):
        repo_path_safety.validate_regular_file_under_repo(
            repo,
            linked_parent / bundle.name,
            label="agent bundle",
        )


def test_select_components_skips_glasshive_when_disabled() -> None:
    names = selected_component_names(
        {
            "voice": {"mode": "local"},
            "runtime": {"playground_variant": "modern"},
            "integrations": {"glasshive": {"enabled": False}},
        }
    )

    assert names == {"LibreChat", "agent-starter-react", "Viventium-Health"}


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
    assert selected_component_names(inspected) == {"LibreChat", "Viventium-Health"}
    assert selected_component_names(bootstrapped) == {"LibreChat", "Viventium-Health"}


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
    expected_ref = make_local_component_source(source_repo)
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


def test_missing_component_clone_failure_is_atomic_across_retries(tmp_path: Path) -> None:
    source_repo = tmp_path / "source"
    make_local_component_source(source_repo)
    destination_root = tmp_path / "destination"
    destination_root.mkdir()
    target_dir = destination_root / "component"
    component = {
        "name": "LibreChat",
        "origin": str(source_repo),
        "ref": "f" * 40,
        "path": "component",
    }

    for _attempt in range(2):
        with pytest.raises(subprocess.CalledProcessError):
            bootstrap_components.clone_or_update_component(
                destination_root,
                component,
                update_existing=True,
                prefer_existing_checkout_head=True,
            )

        assert not target_dir.exists()
        assert list(destination_root.glob(".component.viventium-bootstrap-*")) == []


def test_missing_component_clone_publishes_only_exact_clean_pin(tmp_path: Path) -> None:
    source_repo = tmp_path / "source"
    expected_ref = make_local_component_source(source_repo)
    destination_root = tmp_path / "destination"
    destination_root.mkdir()
    component = {
        "name": "LibreChat",
        "origin": str(source_repo),
        "ref": expected_ref,
        "path": "component",
    }

    bootstrap_components.clone_or_update_component(
        destination_root,
        component,
        update_existing=True,
        prefer_existing_checkout_head=True,
    )

    target_dir = destination_root / "component"
    assert bootstrap_components.current_head(target_dir) == expected_ref
    assert not bootstrap_components.repo_is_dirty(target_dir)
    assert list(destination_root.glob(".component.viventium-bootstrap-*")) == []


def test_missing_component_publish_never_replaces_concurrent_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_repo = tmp_path / "source"
    expected_ref = make_local_component_source(source_repo)
    destination_root = tmp_path / "destination"
    destination_root.mkdir()
    target_dir = destination_root / "component"
    component = {
        "name": "LibreChat",
        "origin": str(source_repo),
        "ref": expected_ref,
        "path": "component",
    }
    real_publish = bootstrap_components.atomic_rename_no_replace
    concurrent_inode = 0

    def publish_after_concurrent_target(source: Path, destination: Path) -> None:
        nonlocal concurrent_inode
        destination.mkdir()
        (destination / "owner.txt").write_text("concurrent owner\n", encoding="utf-8")
        concurrent_inode = destination.stat().st_ino
        real_publish(source, destination)

    monkeypatch.setattr(
        bootstrap_components,
        "atomic_rename_no_replace",
        publish_after_concurrent_target,
    )

    with pytest.raises(FileExistsError):
        bootstrap_components.clone_or_update_component(
            destination_root,
            component,
            update_existing=True,
            prefer_existing_checkout_head=True,
        )

    assert target_dir.stat().st_ino == concurrent_inode
    assert (target_dir / "owner.txt").read_text(encoding="utf-8") == "concurrent owner\n"
    assert not (target_dir / "component.txt").exists()
    assert list(destination_root.glob(".component.viventium-bootstrap-*")) == []


def test_strict_pin_validation_rejects_dirty_and_wrong_clean_branch_heads(
    tmp_path: Path,
) -> None:
    source_repo = tmp_path / "source"
    expected_ref = make_local_component_source(source_repo)
    target_dir = tmp_path / "component"
    subprocess.run(
        ["git", "clone", str(source_repo), str(target_dir)],
        check=True,
        capture_output=True,
    )
    component = {
        "name": "LibreChat",
        "origin": str(source_repo),
        "ref": expected_ref,
        "path": "component",
    }

    assert bootstrap_components.validate_component(
        tmp_path,
        component,
        strict_pinned=True,
    ).startswith("validated")

    (target_dir / "dirty.txt").write_text("dirty\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="dirty"):
        bootstrap_components.validate_component(
            tmp_path,
            component,
            prefer_existing_checkout_head=True,
            strict_pinned=True,
        )
    (target_dir / "dirty.txt").unlink()

    (target_dir / "component.txt").write_text("new head\n", encoding="utf-8")
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
            "wrong head",
        ],
        cwd=target_dir,
        check=True,
        capture_output=True,
    )
    with pytest.raises(SystemExit, match="not pinned"):
        bootstrap_components.validate_component(
            tmp_path,
            component,
            prefer_existing_checkout_head=True,
            strict_pinned=True,
        )


def test_bootstrap_rejects_config_changed_from_activation_digest(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text(
        "integrations:\n  ms365:\n    enabled: false\n",
        encoding="utf-8",
    )
    expected_digest = hashlib.sha256(config.read_bytes()).hexdigest()
    config.write_text(
        "integrations:\n  ms365:\n    enabled: true\n",
        encoding="utf-8",
    )
    (tmp_path / "components.lock.json").write_text(
        '{"components": []}\n',
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/viventium/bootstrap_components.py"),
            "--repo-root",
            str(tmp_path),
            "--lock-file",
            "components.lock.json",
            "--config",
            str(config),
            "--validate-only",
            "--strict-pinned",
            "--expected-config-sha256",
            expected_digest,
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode != 0
    assert "changed during component activation" in completed.stderr


def test_alignment_rejects_config_changed_from_activation_digest(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text(
        "integrations:\n  ms365:\n    enabled: false\n",
        encoding="utf-8",
    )
    expected_digest = hashlib.sha256(config.read_bytes()).hexdigest()
    config.write_text(
        "integrations:\n  ms365:\n    enabled: true\n",
        encoding="utf-8",
    )
    (tmp_path / "components.lock.json").write_text(
        '{"components": []}\n',
        encoding="utf-8",
    )

    blockers, refresh_required = upgrade_check.component_alignment(
        tmp_path,
        config,
        expected_config_sha256=expected_digest,
    )

    assert refresh_required == []
    assert blockers == [
        {
            "actual": "",
            "expected": "unchanged activation config",
            "name": "config.yaml",
            "status": "config_changed_during_activation",
        }
    ]

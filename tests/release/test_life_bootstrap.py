from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_SPEC = importlib.util.spec_from_file_location(
    "viventium_life_bootstrap",
    REPO_ROOT / "scripts" / "viventium" / "life_bootstrap.py",
)
assert MODULE_SPEC and MODULE_SPEC.loader
life_bootstrap = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(life_bootstrap)


def test_canonical_projects_template_is_tracked_for_clean_installs() -> None:
    expected = (
        "templates/life-v0.01/Projects/README.md",
        "templates/life-v0.01/Projects/_template/README.md",
        "templates/life-v0.01/Projects/_template/evidence/README.md",
        "templates/life-v0.01/Projects/_template/research/README.md",
        "templates/life-v0.01/Projects/_template/analysis/README.md",
        "templates/life-v0.01/Projects/_template/decisions/README.md",
        "templates/life-v0.01/Projects/_template/plans/README.md",
        "templates/life-v0.01/Projects/_template/artifacts/README.md",
        "templates/life-v0.01/Projects/_template/history/README.md",
    )

    for relative_path in expected:
        assert (REPO_ROOT / relative_path).is_file()
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", relative_path],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        assert tracked.returncode == 0, f"clean installs would omit {relative_path}"


def test_life_bootstrap_is_additive_idempotent_and_excludes_harness_scaffolding(
    tmp_path: Path,
) -> None:
    life_dir = tmp_path / "Documents" / "Viventium" / "Life"
    state_file = tmp_path / "App Support" / "state" / "life-bootstrap.json"

    first = life_bootstrap.bootstrap_life(
        template_dir=life_bootstrap.DEFAULT_TEMPLATE_DIR,
        life_dir=life_dir,
        state_file=state_file,
    )

    assert (life_dir / "AGENTS.md").is_file()
    assert (life_dir / "CURRENT.md").is_file()
    assert (life_dir / "Self" / "README.md").is_file()
    assert (life_dir / "Projects" / "_template" / "README.md").is_file()
    assert not (life_dir / "CLAUDE.md").exists()
    assert not (life_dir / "CODEX.md").exists()
    assert not (life_dir / ".git").exists()
    assert not (life_dir / "Workspaces" / "_mission-template").exists()
    assert not (life_dir / "99_System" / "night-runs").exists()
    assert not (life_dir / "99_System" / "receipts").exists()
    assert state_file.is_file()
    assert not state_file.is_relative_to(life_dir)
    assert first["created_files"]

    personalized = "# My current reality\n\nKeep this exact text.\n"
    (life_dir / "CURRENT.md").write_text(personalized, encoding="utf-8")
    second = life_bootstrap.bootstrap_life(
        template_dir=life_bootstrap.DEFAULT_TEMPLATE_DIR,
        life_dir=life_dir,
        state_file=state_file,
    )

    assert (life_dir / "CURRENT.md").read_text(encoding="utf-8") == personalized
    assert second["created_files"] == []
    assert "CURRENT.md" in second["preserved_files"]
    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert state["template_version"] == life_bootstrap.TEMPLATE_VERSION
    assert state["template_sha256"]
    assert stat.S_IMODE(life_dir.stat().st_mode) == 0o700
    assert stat.S_IMODE((life_dir / "AGENTS.md").stat().st_mode) == 0o600
    assert stat.S_IMODE(state_file.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(state_file.stat().st_mode) == 0o600


def test_life_bootstrap_repairs_only_missing_items_in_a_partial_personalized_tree(
    tmp_path: Path,
) -> None:
    life_dir = tmp_path / "Life"
    life_dir.mkdir()
    (life_dir / "AGENTS.md").write_text("personal agent rules\n", encoding="utf-8")
    (life_dir / "Self").mkdir()
    (life_dir / "Self" / "private.md").write_text("private\n", encoding="utf-8")

    result = life_bootstrap.bootstrap_life(
        template_dir=life_bootstrap.DEFAULT_TEMPLATE_DIR,
        life_dir=life_dir,
        state_file=tmp_path / "state.json",
    )

    assert (life_dir / "AGENTS.md").read_text(encoding="utf-8") == "personal agent rules\n"
    assert (life_dir / "Self" / "private.md").read_text(encoding="utf-8") == "private\n"
    assert (life_dir / "Self" / "README.md").is_file()
    assert "AGENTS.md" in result["preserved_files"]


def test_runtime_env_value_reads_compiled_life_path_without_executing_shell(tmp_path: Path) -> None:
    runtime_env = tmp_path / "runtime.env"
    runtime_env.write_text(
        "UNRELATED=value\nVIVENTIUM_LIFE_DIR='/safe/path with spaces/Life'\n",
        encoding="utf-8",
    )

    assert (
        life_bootstrap.runtime_env_value(runtime_env, "VIVENTIUM_LIFE_DIR")
        == "/safe/path with spaces/Life"
    )


def test_life_bootstrap_skips_dangling_destination_symlinks(tmp_path: Path) -> None:
    template = tmp_path / "template"
    template.mkdir()
    (template / "AGENTS.md").write_text("canonical\n", encoding="utf-8")
    life_dir = tmp_path / "Life"
    life_dir.mkdir()
    escaped = tmp_path / "must-not-be-created.md"
    os.symlink(escaped, life_dir / "AGENTS.md")

    result = life_bootstrap.bootstrap_life(
        template_dir=template,
        life_dir=life_dir,
        state_file=tmp_path / "state" / "life.json",
    )

    assert not escaped.exists()
    assert result["skipped_symlinks"] == ["AGENTS.md"]


def test_life_bootstrap_rejects_a_symlink_root_or_regular_file(tmp_path: Path) -> None:
    template = tmp_path / "template"
    template.mkdir()
    real_life = tmp_path / "real-life"
    real_life.mkdir()
    symlink_life = tmp_path / "symlink-life"
    os.symlink(real_life, symlink_life)

    with pytest.raises(ValueError, match="must not be a symbolic link"):
        life_bootstrap.bootstrap_life(
            template_dir=template,
            life_dir=symlink_life,
            state_file=tmp_path / "state-symlink.json",
        )

    regular_file = tmp_path / "life-file"
    regular_file.write_text("personal content\n", encoding="utf-8")
    with pytest.raises(FileExistsError):
        life_bootstrap.bootstrap_life(
            template_dir=template,
            life_dir=regular_file,
            state_file=tmp_path / "state-file.json",
        )


def test_life_bootstrap_rejects_a_symlink_in_the_destination_ancestor_chain(
    tmp_path: Path,
) -> None:
    real_parent = tmp_path / "real-parent"
    real_parent.mkdir()
    linked_parent = tmp_path / "linked-parent"
    os.symlink(real_parent, linked_parent)

    with pytest.raises(ValueError, match="symbolic link ancestor"):
        life_bootstrap.bootstrap_life(
            template_dir=life_bootstrap.DEFAULT_TEMPLATE_DIR,
            life_dir=linked_parent / "Viventium" / "Life",
            state_file=tmp_path / "state-ancestor-symlink.json",
        )

    assert not (real_parent / "Viventium").exists()


def test_public_cli_treats_life_bootstrap_as_non_fatal() -> None:
    cli = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    function_body = cli.split("bootstrap_life() {", 1)[1].split("\n}", 1)[0]

    assert "|| life_bootstrap_status=$?" in function_body
    assert "Warning: canonical LIFE bootstrap could not complete" in function_body
    assert function_body.rstrip().endswith("return 0")

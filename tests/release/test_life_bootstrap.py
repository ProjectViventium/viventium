from __future__ import annotations

import importlib.util
import json
import os
import shlex
import stat
import subprocess
import sys
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
    template_root = life_bootstrap.DEFAULT_TEMPLATE_DIR.relative_to(REPO_ROOT)
    expected = tuple(
        (template_root / relative).as_posix()
        for relative in (
            "Projects/README.md",
            "Projects/_template/README.md",
            "Projects/_template/evidence/README.md",
            "Projects/_template/research/README.md",
            "Projects/_template/analysis/README.md",
            "Projects/_template/decisions/README.md",
            "Projects/_template/plans/README.md",
            "Projects/_template/artifacts/README.md",
            "Projects/_template/history/README.md",
        )
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


def test_runtime_env_value_round_trips_compiler_shell_quoting(tmp_path: Path) -> None:
    runtime_env = tmp_path / "runtime.env"
    life_dir = tmp_path / "Owner's Life\\Archive"
    runtime_env.write_text(
        f"VIVENTIUM_LIFE_DIR={shlex.quote(str(life_dir))}\n",
        encoding="utf-8",
    )

    assert (
        life_bootstrap.runtime_env_value(runtime_env, "VIVENTIUM_LIFE_DIR")
        == str(life_dir)
    )


def test_runtime_env_value_rejects_multiple_shell_words(tmp_path: Path) -> None:
    runtime_env = tmp_path / "runtime.env"
    runtime_env.write_text(
        "VIVENTIUM_LIFE_DIR=/safe/first /unsafe/second\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="exactly one shell word"):
        life_bootstrap.runtime_env_value(runtime_env, "VIVENTIUM_LIFE_DIR")


def test_life_bootstrap_defaults_to_canonical_folder_without_provider_config(
    tmp_path: Path,
) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    runtime_env = tmp_path / "runtime.env"
    runtime_env.write_text("START_GLASSHIVE=false\n", encoding="utf-8")
    state_file = tmp_path / "app-support" / "state" / "life-bootstrap.json"

    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "viventium" / "life_bootstrap.py"),
            "--runtime-env",
            str(runtime_env),
            "--state-file",
            str(state_file),
        ],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "HOME": str(fake_home)},
    )

    life_dir = fake_home / "Documents" / "Viventium" / "Life"
    assert completed.returncode == 0, completed.stderr
    assert (life_dir / "AGENTS.md").is_file()
    assert json.loads(state_file.read_text(encoding="utf-8"))["life_dir"] == str(
        life_dir
    )


def test_life_bootstrap_reports_symlink_loops_without_a_traceback(
    tmp_path: Path,
) -> None:
    first = tmp_path / "loop-a"
    second = tmp_path / "loop-b"
    os.symlink(second, first)
    os.symlink(first, second)
    runtime_env = tmp_path / "runtime.env"
    runtime_env.write_text(
        f"VIVENTIUM_LIFE_DIR={shlex.quote(str(first / 'Life'))}\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "viventium" / "life_bootstrap.py"),
            "--runtime-env",
            str(runtime_env),
            "--state-file",
            str(tmp_path / "state" / "life-bootstrap.json"),
        ],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "HOME": str(tmp_path)},
    )

    assert completed.returncode == 2
    assert "LIFE bootstrap failed:" in completed.stderr
    assert "Traceback" not in completed.stderr


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


def test_life_bootstrap_accepts_icloud_documents_symlink_inside_home(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_home = tmp_path / "home"
    icloud_documents = (
        fake_home
        / "Library"
        / "Mobile Documents"
        / "com~apple~CloudDocs"
        / "Documents"
    )
    icloud_documents.mkdir(parents=True)
    fake_home.mkdir(exist_ok=True)
    os.symlink(icloud_documents, fake_home / "Documents")
    monkeypatch.setenv("HOME", str(fake_home))

    result = life_bootstrap.bootstrap_life(
        template_dir=life_bootstrap.DEFAULT_TEMPLATE_DIR,
        life_dir=fake_home / "Documents" / "Viventium" / "Life",
        state_file=tmp_path / "state-icloud.json",
    )

    resolved_life = icloud_documents / "Viventium" / "Life"
    assert (resolved_life / "AGENTS.md").is_file()
    assert result["life_dir"] == str(resolved_life)
    assert result["conflicts"] == []


def test_life_bootstrap_preserves_conflicts_continues_and_writes_receipt(
    tmp_path: Path,
) -> None:
    template = tmp_path / "template"
    (template / "Self").mkdir(parents=True)
    (template / "Self" / "README.md").write_text("template self\n", encoding="utf-8")
    (template / "Zed").mkdir()
    (template / "Zed" / "README.md").write_text("template zed\n", encoding="utf-8")
    life_dir = tmp_path / "Life"
    life_dir.mkdir()
    (life_dir / "Self").write_text("personal file\n", encoding="utf-8")
    state_file = tmp_path / "state" / "life.json"

    result = life_bootstrap.bootstrap_life(
        template_dir=template,
        life_dir=life_dir,
        state_file=state_file,
    )

    assert (life_dir / "Self").read_text(encoding="utf-8") == "personal file\n"
    assert (life_dir / "Zed" / "README.md").read_text(encoding="utf-8") == (
        "template zed\n"
    )
    assert result["conflicts"]
    assert result["conflicts"][0]["path"] == "Self"
    assert json.loads(state_file.read_text(encoding="utf-8"))["conflicts"] == result[
        "conflicts"
    ]


def test_public_cli_treats_life_bootstrap_as_non_fatal() -> None:
    cli = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    function_body = cli.split("bootstrap_life() {", 1)[1].split("\n}", 1)[0]

    assert "|| life_bootstrap_status=$?" in function_body
    assert "--if-configured" not in function_body
    assert "Warning: canonical LIFE bootstrap could not complete" in function_body
    assert "canonical LIFE bootstrap is required by the enabled GlassHive runtime" in function_body
    assert "rerun bin/viventium configure or start" in function_body
    assert 'return "$life_bootstrap_status"' in function_body
    assert function_body.rstrip().endswith("return 0")


def test_normal_start_bootstraps_life_after_compile_and_before_runtime_start() -> None:
    cli = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    start = cli.rsplit("  start)", 1)[1].split("  stop)", 1)[0]

    compile_index = start.index("    compile_config\n")
    life_index = start.index("      bootstrap_life\n", compile_index)
    runtime_index = start.index("    prepare_runtime_exports\n", life_index)

    assert compile_index < life_index < runtime_index
    life_guard = start[start.rfind("if [[", compile_index, life_index) : life_index]
    assert 'VIVENTIUM_SUCCESSOR_VALIDATION_MODE:-}" != "quiesced"' in life_guard


def test_postcommit_life_failure_does_not_skip_protected_finalization() -> None:
    cli = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    upgrade = cli.rsplit("  upgrade|update)", 1)[1].split("  configure|wizard)", 1)[0]

    commit_index = upgrade.index("    upgrade_transaction_commit\n")
    capture_index = upgrade.index(
        "    bootstrap_life || postcommit_life_bootstrap_status=$?\n",
        commit_index,
    )
    runtime_finalize_index = upgrade.index(
        "    if ! finalize_quiesced_upgrade_session_after_commit; then",
        capture_index,
    )
    uploads_finalize_index = upgrade.index(
        "    if ! finalize_deferred_uploads_after_upgrade_commit; then",
        runtime_finalize_index,
    )
    life_failure_index = upgrade.index(
        '    if [[ "$postcommit_life_bootstrap_status" -ne 0 ]]; then',
        uploads_finalize_index,
    )

    assert capture_index < runtime_finalize_index < uploads_finalize_index < life_failure_index

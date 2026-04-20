from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_private_repo_resolution_avoids_parent_directory_globs() -> None:
    gitignore_text = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    cli_text = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")
    common_text = (REPO_ROOT / "scripts" / "viventium" / "common.sh").read_text(encoding="utf-8")
    assert "/private-companion-repo/" in gitignore_text
    assert "/.private-companion-repo/" in gitignore_text
    assert "/enterprise-deployment-repo/" in gitignore_text
    assert "/.enterprise-deployment-repo/" in gitignore_text
    assert '"$workspace_root"/*private-companion-repo*' not in cli_text
    assert '"$workspace_root"/*private-companion-repo*' not in common_text
    assert '"$repo_root/private-companion-repo"' in common_text
    assert '"$repo_root/.private-companion-repo"' in common_text
    assert '"$workspace_root/private-companion-repo"' in common_text
    assert '"$workspace_root/.private-companion-repo"' in common_text
    assert "path_is_git_repo_root()" in common_text
    assert "discover_workspace_repo_dir()" in common_text

    for script in [
        REPO_ROOT / "viventium_v0_4" / "viventium-skyvern-start.sh",
        REPO_ROOT / "viventium_v0_4" / "viventium-local-state-snapshot.sh",
    ]:
        text = script.read_text(encoding="utf-8")
        assert '"$workspace_root"/*private-companion-repo*' not in text
        assert "discover_private_repo_dir" in text
        assert 'source "$COMMON_SH"' in text or 'source "$VIVENTIUM_CORE_DIR/scripts/viventium/common.sh"' in text
        if script.name == "viventium-skyvern-start.sh":
            assert 'if [[ -n "$VIVENTIUM_PRIVATE_REPO_DIR" ]]; then' in text

    librechat_launcher = (REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh").read_text(
        encoding="utf-8"
    )
    assert '"$workspace_root"/*private-companion-repo*' not in librechat_launcher
    assert 'source "$VIVENTIUM_CORE_DIR/scripts/viventium/common.sh"' in librechat_launcher
    assert "if ! declare -F discover_workspace_repo_dir >/dev/null 2>&1; then" in librechat_launcher
    assert 'VIVENTIUM_DEPLOY_REPO_DIR="$VIVENTIUM_CORE_DIR/enterprise-deployment-repo"' not in librechat_launcher
    assert 'if [[ -n "$VIVENTIUM_PRIVATE_REPO_DIR" ]]; then' in librechat_launcher
    assert 'LIBRECHAT_PRIVATE_CONFIG_DIR="${VIVENTIUM_PRIVATE_CURATED_DIR:-$VIVENTIUM_PRIVATE_REPO_DIR/curated}/configs/librechat"' not in librechat_launcher


def test_private_yaml_validation_is_bounded_and_fail_open() -> None:
    cli_text = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")

    assert 'VIVENTIUM_PRIVATE_YAML_VALIDATE_TIMEOUT_SECONDS' in cli_text
    assert 'raise TimeoutError("timed out while reading YAML")' in cli_text
    assert "signal.alarm(timeout_seconds)" in cli_text
    assert "Warning: ignoring unreadable or invalid private LibreChat source-of-truth YAML" in cli_text
    assert "Warning: ignoring unreadable or invalid private Viventium agents bundle" in cli_text


def test_private_launcher_compat_loading_is_bounded_and_fail_open() -> None:
    launcher_text = (REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh").read_text(
        encoding="utf-8"
    )

    assert "text_file_is_readable_with_timeout()" in launcher_text
    assert 'raise TimeoutError("timed out while reading text file")' in launcher_text
    assert "Warning: ignoring unreadable private launcher compat file" in launcher_text


def test_discover_private_repo_dir_rejects_non_git_directory(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    repo_root = workspace_root / "viventium"
    private_dir = repo_root / "private-companion-repo"
    private_dir.mkdir(parents=True)

    result = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"source {shlex.quote(str(REPO_ROOT / 'scripts' / 'viventium' / 'common.sh'))} && "
                f"discover_private_repo_dir {shlex.quote(str(workspace_root))} {shlex.quote(str(repo_root))}"
            ),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert result.stdout.strip() == ""


def test_discover_private_repo_dir_accepts_git_worktree_root(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    repo_root = workspace_root / "viventium"
    companion_root = workspace_root / "private-companion-repo"
    repo_root.mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.name", "Public Tester"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.email", "public@example.com"], cwd=repo_root, check=True)
    (repo_root / "README.md").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "worktree", "add", "-b", "companion-test", str(companion_root), "HEAD"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )

    result = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"source {shlex.quote(str(REPO_ROOT / 'scripts' / 'viventium' / 'common.sh'))} && "
                f"discover_private_repo_dir {shlex.quote(str(workspace_root))} {shlex.quote(str(repo_root))}"
            ),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "HOME": str(tmp_path / 'home')},
    )

    assert result.returncode == 0
    assert result.stdout.strip() == str(companion_root)

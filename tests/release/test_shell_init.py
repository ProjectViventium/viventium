from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SHELL_INIT_PATH = REPO_ROOT / "scripts" / "viventium" / "shell_init.py"
CLI_PATH = REPO_ROOT / "bin" / "viventium"


def load_shell_init_module():
    spec = importlib.util.spec_from_file_location("viventium_shell_init", SHELL_INIT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_recommend_one_liner_targets_zsh_profile_and_both_commands(
    tmp_path: Path,
    monkeypatch,
) -> None:
    shell_init = load_shell_init_module()
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    target_path = REPO_ROOT / "bin" / "viventium"
    profile_path = shell_init.default_profile_path("zsh", home_dir)

    command = shell_init.recommend_one_liner(target_path, "zsh", profile_path)

    assert "ln -sfn " in command
    assert '"$HOME/.local/bin/viventium"' in command
    assert '"$HOME/.local/bin/viv"' in command
    assert '"$HOME/.zshrc"' in command
    assert 'export PATH="$HOME/.local/bin:$PATH"' in command


def test_apply_shell_init_is_idempotent(tmp_path: Path) -> None:
    shell_init = load_shell_init_module()
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    profile_path = shell_init.default_profile_path("zsh", home_dir)
    target_path = REPO_ROOT / "bin" / "viventium"

    created_paths, added_line = shell_init.apply_shell_init(target_path, "zsh", profile_path, home_dir)
    created_paths_second, added_line_second = shell_init.apply_shell_init(
        target_path,
        "zsh",
        profile_path,
        home_dir,
    )

    assert added_line is True
    assert added_line_second is False
    assert [path.name for path in created_paths] == ["viventium", "viv"]
    assert [path.name for path in created_paths_second] == ["viventium", "viv"]
    for command_name in ("viventium", "viv"):
        link_path = home_dir / ".local" / "bin" / command_name
        assert link_path.is_symlink()
        assert link_path.resolve() == target_path.resolve()

    profile_lines = profile_path.read_text(encoding="utf-8").splitlines()
    assert profile_lines.count('export PATH="$HOME/.local/bin:$PATH"') == 1


def test_cli_help_runs_from_symlinked_viv_path(tmp_path: Path) -> None:
    symlink_path = tmp_path / "viv"
    symlink_path.symlink_to(CLI_PATH)

    env = os.environ.copy()
    env["HOME"] = str(tmp_path / "home")
    result = subprocess.run(
        [str(symlink_path), "help"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "bin/viventium <command>" in result.stdout
    assert "shell-init" in result.stdout


def test_shell_init_print_command_cli_uses_requested_profile(tmp_path: Path) -> None:
    target_path = REPO_ROOT / "bin" / "viventium"
    custom_profile = tmp_path / ".custom-shell-profile"
    result = subprocess.run(
        [
            sys.executable,
            str(SHELL_INIT_PATH),
            "--target",
            str(target_path),
            "--profile",
            str(custom_profile),
            "--print-command",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert str(custom_profile) in result.stdout
    assert '"$HOME/.local/bin/viv"' in result.stdout
    assert '"$HOME/.local/bin/viventium"' in result.stdout

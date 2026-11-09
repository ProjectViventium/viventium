from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


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
    assert '"$HOME"/.zshrc' in command
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


@pytest.mark.parametrize("profile_in_home", [True, False])
def test_shell_init_print_command_cli_uses_requested_profile(tmp_path: Path, profile_in_home: bool) -> None:
    target_path = REPO_ROOT / "bin" / "viventium"
    home = tmp_path / "home"
    home.mkdir()
    custom_profile = (home if profile_in_home else tmp_path) / ".custom-shell-profile"
    result = subprocess.run(
        [
            str(CLI_PATH),
            "shell-init",
            "--profile",
            str(custom_profile),
            "--print-command",
        ],
        env={**os.environ, "HOME": str(home), "SHELL": "/bin/sh"},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    applied = subprocess.run(
        ["/bin/sh", "-c", result.stdout],
        env={**os.environ, "HOME": str(home), "SHELL": "/bin/sh"}, capture_output=True, text=True,
    )
    assert applied.returncode == 0, applied.stderr
    assert custom_profile.read_text().splitlines() == ['export PATH="$HOME/.local/bin:$PATH"']
    for name in ("viv", "viventium"):
        assert (home / ".local/bin" / name).resolve() == target_path.resolve()
    assert str(home) not in result.stdout
    assert '"$HOME/.local/bin/viv"' in result.stdout
    assert '"$HOME/.local/bin/viventium"' in result.stdout


@pytest.mark.parametrize("shell", ["bash", "zsh"])
@pytest.mark.parametrize("profile_name", [
    "profile$(printf _expanded_)", "profile`printf _expanded_`",
    'profile"quote', r"profile\backslash", "profile!literal", "profile'quote",
])
def test_printed_shell_setup_preserves_profile_filename_as_data(
    tmp_path: Path, shell: str, profile_name: str,
) -> None:
    if not shutil.which(shell):
        pytest.skip(f"shell setup QA NOT RUN: {shell} executable is unavailable")
    home = tmp_path / "home"
    home.mkdir()
    profile = home / profile_name
    env = {**os.environ, "HOME": str(home)}
    printed = subprocess.run(
        [sys.executable, str(SHELL_INIT_PATH), "--target", str(CLI_PATH),
         "--shell", shell, "--profile", str(profile),
         "--print-command"],
        env=env, capture_output=True, text=True, check=True,
    )
    for _ in range(2):
        applied = subprocess.run(
            [shell, "-c", printed.stdout], cwd=tmp_path, env=env,
            capture_output=True, text=True,
        )
        assert applied.returncode == 0, applied.stderr
    assert profile.read_text().splitlines() == ['export PATH="$HOME/.local/bin:$PATH"']
    for name in ("viv", "viventium"):
        assert (home / ".local/bin" / name).resolve() == CLI_PATH.resolve()


def test_fish_source_command_preserves_literal_profile_name(tmp_path: Path, monkeypatch) -> None:
    fish = shutil.which("fish")
    if not fish:
        pytest.skip("fish source-command QA NOT RUN: fish executable is unavailable")
    monkeypatch.setenv("HOME", str(tmp_path))
    profile = tmp_path / 'profile`literal`$"\\path'
    profile.write_text("printf literal-profile-loaded\\n\n")
    command = load_shell_init_module().source_command("fish", profile)
    result = subprocess.run([fish, "-c", command], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "literal-profile-loaded"


@pytest.mark.parametrize("shell", ["bash", "zsh"])
def test_interactive_shell_setup_keeps_history_metacharacters_literal(tmp_path, monkeypatch, shell):
    if os.name != "posix" or not shutil.which(shell):
        pytest.skip(f"interactive shell QA NOT RUN: {shell} is unavailable")
    import pty
    import select
    import signal
    import termios
    import time

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    profile = home / "profile!99999999'quote"
    command = load_shell_init_module().recommend_one_liner(CLI_PATH, shell, profile)
    env = {"PATH": os.environ["PATH"], "HOME": str(home), "ZDOTDIR": str(home),
           "HISTFILE": "/dev/null", "TERM": "dumb", "PS1": "__READY__ ", "PS2": "__MORE__ "}
    master, slave = pty.openpty()
    settings = termios.tcgetattr(slave)
    settings[3] &= ~termios.ECHO
    termios.tcsetattr(slave, termios.TCSANOW, settings)
    args = [shell, "--noprofile", "--norc", "-i"] if shell == "bash" else [shell, "-f", "-i"]
    process = subprocess.Popen(args, stdin=slave, stdout=slave, stderr=slave,
                               env=env, cwd=tmp_path, start_new_session=True)
    os.close(slave)

    def read_until(marker):
        output = b""
        deadline = time.monotonic() + 10
        while marker not in output:
            assert process.poll() is None and time.monotonic() < deadline, output.decode(errors="replace")
            if select.select([master], [], [], 0.1)[0]:
                output += os.read(master, 65536)
        return output

    try:
        history = "set -H" if shell == "bash" else "setopt BANG_HIST"
        os.write(master, f"{history}\nprintf '__HISTORY_READY__\\n'\n".encode())
        read_until(b"__HISTORY_READY__")
        for index in range(2):
            marker = f"__APPLIED_{index}__"
            os.write(master, f"{command}\nprintf '{marker}\\n'\n".encode())
            output = read_until(marker.encode())
            assert profile.is_file(), output.decode(errors="replace")
        assert profile.read_text().splitlines() == ['export PATH="$HOME/.local/bin:$PATH"']
        for name in ("viv", "viventium"):
            assert (home / ".local/bin" / name).resolve() == CLI_PATH.resolve()
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)
        os.close(master)

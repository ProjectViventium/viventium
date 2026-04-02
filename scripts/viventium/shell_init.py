#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shlex
import sys
from pathlib import Path
from typing import Final


COMMAND_NAMES: Final[tuple[str, str]] = ("viventium", "viv")
POSIX_PATH_EXPORT_LINE: Final[str] = 'export PATH="$HOME/.local/bin:$PATH"'
FISH_PATH_EXPORT_LINE: Final[str] = 'fish_add_path -m "$HOME/.local/bin"'


def normalize_shell_name(value: str | None) -> str:
    raw = Path(value or "").name.strip().lower()
    if raw.startswith("zsh"):
        return "zsh"
    if raw.startswith("bash"):
        return "bash"
    if raw.startswith("fish"):
        return "fish"
    if raw:
        return raw
    return "sh"


def default_profile_path(shell_name: str, home_dir: Path) -> Path:
    if shell_name == "zsh":
        return home_dir / ".zshrc"
    if shell_name == "bash":
        return home_dir / ".bashrc"
    if shell_name == "fish":
        return home_dir / ".config" / "fish" / "config.fish"
    return home_dir / ".profile"


def path_export_line(shell_name: str) -> str:
    if shell_name == "fish":
        return FISH_PATH_EXPORT_LINE
    return POSIX_PATH_EXPORT_LINE


def source_command(shell_name: str, profile_path: Path) -> str:
    quoted_profile = shell_quoted_path(profile_path)
    if shell_name in {"zsh", "bash", "fish"}:
        return f"source {quoted_profile}"
    return f". {quoted_profile}"


def profile_parent_dirs(shell_name: str) -> list[str]:
    if shell_name == "fish":
        return ['"$HOME/.config/fish"']
    return []


def home_aware_path(path: Path) -> str:
    home_dir = Path.home().expanduser().resolve()
    resolved_path = path.expanduser().resolve()
    try:
        relative_path = resolved_path.relative_to(home_dir)
    except ValueError:
        return str(resolved_path)
    if not relative_path.parts:
        return "$HOME"
    return f"$HOME/{relative_path.as_posix()}"


def shell_quoted_path(path: Path) -> str:
    rendered = home_aware_path(path)
    if rendered.startswith("$HOME/") or rendered == "$HOME":
        return f'"{rendered}"'
    return shlex.quote(rendered)


def recommend_one_liner(target_path: Path, shell_name: str, profile_path: Path) -> str:
    quoted_target = shlex.quote(str(target_path))
    quoted_profile = shell_quoted_path(profile_path)
    export_line = shlex.quote(path_export_line(shell_name))
    mkdir_args = ['"$HOME/.local/bin"', *profile_parent_dirs(shell_name)]
    mkdir_step = f"mkdir -p {' '.join(mkdir_args)}"
    link_steps = [
        f'ln -sfn {quoted_target} "$HOME/.local/bin/{command_name}"'
        for command_name in COMMAND_NAMES
    ]
    profile_step = (
        f"{{ grep -qxF {export_line} {quoted_profile} || echo {export_line} >> {quoted_profile}; }}"
    )
    return " && ".join([mkdir_step, *link_steps, profile_step, source_command(shell_name, profile_path)])


def ensure_profile_line(profile_path: Path, line: str) -> bool:
    existing_text = profile_path.read_text(encoding="utf-8") if profile_path.is_file() else ""
    existing_lines = existing_text.splitlines()
    if line in existing_lines:
        return False
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    if existing_text and not existing_text.endswith("\n"):
        existing_text += "\n"
    profile_path.write_text(f"{existing_text}{line}\n", encoding="utf-8")
    return True


def install_links(target_path: Path, home_dir: Path) -> list[Path]:
    local_bin = home_dir / ".local" / "bin"
    local_bin.mkdir(parents=True, exist_ok=True)
    created_paths: list[Path] = []
    for command_name in COMMAND_NAMES:
        link_path = local_bin / command_name
        if link_path.exists() or link_path.is_symlink():
            link_path.unlink()
        link_path.symlink_to(target_path)
        created_paths.append(link_path)
    return created_paths


def apply_shell_init(
    target_path: Path,
    shell_name: str,
    profile_path: Path,
    home_dir: Path,
) -> tuple[list[Path], bool]:
    created_paths = install_links(target_path, home_dir)
    added_line = ensure_profile_line(profile_path, path_export_line(shell_name))
    return created_paths, added_line


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Print or apply the optional shell setup that makes `viventium` and `viv` "
            "available from any folder."
        )
    )
    parser.add_argument(
        "--target",
        required=True,
        help="Absolute path to the checkout-local bin/viventium entrypoint.",
    )
    parser.add_argument(
        "--shell",
        help="Shell name to target (defaults to the current SHELL environment).",
    )
    parser.add_argument(
        "--profile",
        help="Shell profile to update instead of the default file for the detected shell.",
    )
    parser.add_argument(
        "--print-command",
        action="store_true",
        help="Print only the one-line shell command.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the shell integration immediately instead of only printing it.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    target_path = Path(args.target).expanduser().resolve()
    if not target_path.is_file():
        raise SystemExit(f"Target CLI entrypoint not found: {target_path}")

    shell_name = normalize_shell_name(args.shell or os.environ.get("SHELL"))
    home_dir = Path.home().expanduser().resolve()
    profile_path = (
        Path(args.profile).expanduser().resolve()
        if args.profile
        else default_profile_path(shell_name, home_dir)
    )
    command = recommend_one_liner(target_path, shell_name, profile_path)

    if args.apply:
        created_paths, added_line = apply_shell_init(target_path, shell_name, profile_path, home_dir)
        print("Viventium shell integration is ready.")
        print(f"- Commands: {', '.join(command_path.name for command_path in created_paths)}")
        print(f"- Profile: {profile_path}")
        print("- PATH line: " + ("added" if added_line else "already present"))
        print(f"- Open a new shell, or run: {source_command(shell_name, profile_path)}")
        return 0

    if args.print_command:
        print(command)
        return 0

    print("Run this once to use `viventium` and `viv` from any folder:")
    print(command)
    print("")
    print(f"Profile target: {profile_path}")
    print("Tip: rerun this after moving the repo checkout so the command links stay current.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

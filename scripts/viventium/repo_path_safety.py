#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import stat
from pathlib import Path


class RepoPathSafetyError(ValueError):
    pass


def validate_regular_file_under_repo(
    repo_root: Path,
    candidate: Path,
    *,
    label: str,
) -> Path:
    root = repo_root.expanduser().absolute()
    path = candidate.expanduser().absolute()
    if root.is_symlink() or not root.is_dir():
        raise RepoPathSafetyError("repository root is not a safe directory")
    try:
        relative = path.relative_to(root)
    except ValueError as error:
        raise RepoPathSafetyError(f"{label} is outside the repository") from error

    current = root
    for part in relative.parts:
        current /= part
        try:
            metadata = os.lstat(current)
        except FileNotFoundError as error:
            raise RepoPathSafetyError(f"{label} is unavailable") from error
        if stat.S_ISLNK(metadata.st_mode):
            raise RepoPathSafetyError(f"{label} has a linked path component")
        if current == path:
            if not stat.S_ISREG(metadata.st_mode):
                raise RepoPathSafetyError(f"{label} is not a regular file")
        elif not stat.S_ISDIR(metadata.st_mode):
            raise RepoPathSafetyError(
                f"{label} has a non-directory path component"
            )

    resolved_root = root.resolve(strict=True)
    resolved_path = path.resolve(strict=True)
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as error:
        raise RepoPathSafetyError(f"{label} resolves outside the repository") from error
    return resolved_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a repository-owned regular source file without linked ancestors."
    )
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--label", default="repository source file")
    args = parser.parse_args()
    try:
        validate_regular_file_under_repo(
            args.repo_root,
            args.file,
            label=args.label,
        )
    except (OSError, RepoPathSafetyError) as error:
        parser.exit(1, f"Unsafe repository source path: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

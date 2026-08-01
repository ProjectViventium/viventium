#!/usr/bin/env python3
"""Additively bootstrap the canonical per-user Viventium LIFE folder."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


TEMPLATE_VERSION = "life-v0.01-provider-v1"
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TEMPLATE_DIR = REPO_ROOT / "templates" / "life-v0.01"
DEFAULT_LIFE_DIR = Path.home() / "Documents" / "Viventium" / "Life"
DEFAULT_STATE_FILE = (
    Path.home()
    / "Library"
    / "Application Support"
    / "Viventium"
    / "state"
    / "life-bootstrap.json"
)
EXCLUDED_NAMES = {".git", "CLAUDE.md", "CODEX.md"}
EXCLUDED_PREFIXES = {
    Path("Workspaces/_mission-template"),
    Path("99_System/night-runs"),
    Path("99_System/receipts"),
}


def _is_excluded(relative_path: Path) -> bool:
    if any(part in EXCLUDED_NAMES for part in relative_path.parts):
        return True
    return any(
        relative_path == prefix or prefix in relative_path.parents
        for prefix in EXCLUDED_PREFIXES
    )


def _template_entries(template_dir: Path) -> Iterable[tuple[Path, Path]]:
    for source in sorted(template_dir.rglob("*")):
        relative = source.relative_to(template_dir)
        if _is_excluded(relative):
            continue
        if source.is_symlink():
            continue
        yield source, relative


def _template_digest(template_dir: Path) -> str:
    digest = hashlib.sha256()
    for source, relative in _template_entries(template_dir):
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        if source.is_file():
            digest.update(source.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def runtime_env_value(path: Path, key: str) -> str:
    if not path.is_file():
        return ""
    prefix = f"{key}="
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.startswith(prefix):
            continue
        value = raw_line[len(prefix) :].strip()
        words = shlex.split(value, comments=False, posix=True)
        if len(words) != 1:
            raise ValueError(
                f"{key} in {path} must contain exactly one shell word"
            )
        return words[0]
    return ""


def _first_symlink_component(path: Path) -> Path | None:
    """Return the first symlink in an absolute destination path without resolving it."""

    absolute = Path(os.path.abspath(path))
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        if current.is_symlink():
            return current
    return None


def bootstrap_life(
    *,
    template_dir: Path,
    life_dir: Path,
    state_file: Path,
) -> dict[str, object]:
    template_dir = template_dir.expanduser().resolve(strict=True)
    life_dir = Path(os.path.abspath(life_dir.expanduser()))
    symlink_component = _first_symlink_component(life_dir)
    if symlink_component:
        if symlink_component == life_dir:
            raise ValueError(f"LIFE root must not be a symbolic link: {life_dir}")
        resolved_life_dir = life_dir.resolve()
        resolved_home = Path.home().expanduser().resolve()
        if not resolved_life_dir.is_relative_to(resolved_home):
            raise ValueError(
                "LIFE path has a symbolic link ancestor that resolves outside "
                f"the current user's home: {symlink_component}"
            )
        life_dir = resolved_life_dir
    else:
        life_dir = life_dir.resolve()
    if not template_dir.is_dir():
        raise ValueError(f"LIFE template is not a directory: {template_dir}")

    life_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    life_dir.chmod(0o700)
    created_files: list[str] = []
    preserved_files: list[str] = []
    skipped_symlinks: list[str] = []
    conflicts: list[dict[str, str]] = []
    created_directories = 0
    for source, relative in _template_entries(template_dir):
        destination = life_dir / relative
        relative_parents = [life_dir / parent for parent in reversed(relative.parents) if parent != Path(".")]
        if destination.is_symlink() or any(parent.is_symlink() for parent in relative_parents):
            skipped_symlinks.append(relative.as_posix())
            continue
        try:
            if source.is_dir():
                if destination.exists() and not destination.is_dir():
                    conflicts.append(
                        {
                            "path": relative.as_posix(),
                            "reason": "personalized file blocks template directory",
                        }
                    )
                    continue
                if not destination.exists():
                    destination.mkdir(mode=0o700, parents=True, exist_ok=True)
                    destination.chmod(0o700)
                    created_directories += 1
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                if destination.is_file():
                    preserved_files.append(relative.as_posix())
                else:
                    conflicts.append(
                        {
                            "path": relative.as_posix(),
                            "reason": "personalized directory blocks template file",
                        }
                    )
                continue
            shutil.copyfile(source, destination)
            destination.chmod(0o600)
            created_files.append(relative.as_posix())
        except OSError as error:
            conflicts.append(
                {
                    "path": relative.as_posix(),
                    "reason": f"{type(error).__name__}: {error.strerror or 'filesystem error'}",
                }
            )

    record = {
        "schema_version": 1,
        "template_version": TEMPLATE_VERSION,
        "template_sha256": _template_digest(template_dir),
        "life_dir": str(life_dir),
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "created_files": created_files,
        "preserved_files": preserved_files,
        "skipped_symlinks": skipped_symlinks,
        "conflicts": conflicts,
        "created_directories": created_directories,
        "excluded": sorted(path.as_posix() for path in EXCLUDED_PREFIXES)
        + sorted(EXCLUDED_NAMES),
    }
    state_file = state_file.expanduser()
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.parent.chmod(0o700)
    temporary = state_file.with_name(f".{state_file.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    os.replace(temporary, state_file)
    state_file.chmod(0o600)
    return record


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-dir", type=Path, default=DEFAULT_TEMPLATE_DIR)
    parser.add_argument("--life-dir", type=Path)
    parser.add_argument("--runtime-env", type=Path)
    parser.add_argument("--state-file", type=Path, default=DEFAULT_STATE_FILE)
    parser.add_argument(
        "--if-configured",
        action="store_true",
        help="Exit successfully without changes unless VIVENTIUM_LIFE_DIR exists in --runtime-env.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        configured = (
            runtime_env_value(args.runtime_env, "VIVENTIUM_LIFE_DIR")
            if args.runtime_env
            else ""
        )
        if args.if_configured and not configured and args.life_dir is None:
            return 0
        life_dir = args.life_dir or (
            Path(configured) if configured else DEFAULT_LIFE_DIR
        )
        record = bootstrap_life(
            template_dir=args.template_dir,
            life_dir=Path(life_dir),
            state_file=args.state_file,
        )
    except (OSError, RuntimeError, ValueError) as error:
        print(f"LIFE bootstrap failed: {error}", file=sys.stderr)
        return 2
    print(
        "LIFE ready: "
        f"{record['life_dir']} "
        f"({len(record['created_files'])} files added, {len(record['preserved_files'])} preserved)"
    )
    if record["conflicts"]:
        conflict_paths = ", ".join(
            str(conflict["path"]) for conflict in record["conflicts"][:8]
        )
        remainder = len(record["conflicts"]) - min(len(record["conflicts"]), 8)
        suffix = f" (+{remainder} more)" if remainder else ""
        print(
            "LIFE preserved personalized conflicts and could not add every template "
            f"item: {conflict_paths}{suffix}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Build or verify a deterministic manifest for one staged Native component tree."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
from pathlib import Path, PurePosixPath


class ComponentManifestError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_tree_records(
    root: Path,
) -> tuple[int, list[dict[str, object]], list[dict[str, object]]]:
    if root.is_symlink() or not root.is_dir():
        raise ComponentManifestError("Native component root must be a real directory")
    resolved = root.resolve(strict=True)
    root_mode = stat.S_IMODE(root.stat().st_mode)
    directories: list[dict[str, object]] = []
    records: list[dict[str, object]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        metadata = path.lstat()
        if stat.S_ISDIR(metadata.st_mode):
            if path.is_symlink():
                raise ComponentManifestError("Native component tree contains a symlink")
            directories.append(
                {
                    "mode": stat.S_IMODE(metadata.st_mode),
                    "path": path.relative_to(root).as_posix(),
                }
            )
            continue
        if path.is_symlink():
            raise ComponentManifestError("Native component tree contains a symlink")
        if not stat.S_ISREG(metadata.st_mode):
            raise ComponentManifestError("Native component tree contains an unsafe entry")
        try:
            path.resolve(strict=True).relative_to(resolved)
        except ValueError as error:
            raise ComponentManifestError("Native component tree escapes its root") from error
        records.append(
            {
                "mode": stat.S_IMODE(metadata.st_mode),
                "path": path.relative_to(root).as_posix(),
                "sha256": sha256_file(path),
                "size": metadata.st_size,
            }
        )
    if not records:
        raise ComponentManifestError("Native component tree is empty")
    return root_mode, directories, records


def tree_digest(
    root_mode: int,
    directories: list[dict[str, object]],
    records: list[dict[str, object]],
) -> str:
    encoded = json.dumps(
        {"directories": directories, "files": records, "root_mode": root_mode},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_manifest(
    root: Path,
    *,
    name: str,
    component: dict[str, str],
) -> dict[str, object]:
    if not re.fullmatch(r"[a-z][a-z0-9-]*", name):
        raise ComponentManifestError("Native component name is invalid")
    if not isinstance(component, dict) or any(
        not isinstance(key, str) or not isinstance(value, str) or not value
        for key, value in component.items()
    ):
        raise ComponentManifestError("Native component policy projection is invalid")
    root_mode, directories, records = canonical_tree_records(root)
    return {
        "schema_version": 1,
        "component": {"name": name, **dict(sorted(component.items()))},
        "directories": directories,
        "files": records,
        "root_mode": root_mode,
        "tree_sha256": tree_digest(root_mode, directories, records),
    }


def manifest_file(root: Path, relative: object) -> Path:
    if not isinstance(relative, str):
        raise ComponentManifestError("Native component manifest contains an invalid path")
    value = PurePosixPath(relative)
    if value.is_absolute() or not value.parts or any(part in {"", ".", ".."} for part in value.parts):
        raise ComponentManifestError("Native component manifest contains an unsafe path")
    path = root.joinpath(*value.parts)
    if path.is_symlink() or not path.is_file():
        raise ComponentManifestError(f"Native component file is missing: {relative}")
    try:
        path.resolve(strict=True).relative_to(root.resolve(strict=True))
    except ValueError as error:
        raise ComponentManifestError("Native component manifest escapes its root") from error
    return path


def verify(root: Path, manifest_path: Path, *, expected_name: str | None = None) -> dict[str, object]:
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ComponentManifestError("Native component manifest is unavailable")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ComponentManifestError("Native component manifest is invalid") from error
    component = manifest.get("component")
    directories = manifest.get("directories")
    files = manifest.get("files")
    if (
        manifest.get("schema_version") != 1
        or not isinstance(component, dict)
        or not isinstance(component.get("name"), str)
        or (expected_name is not None and component.get("name") != expected_name)
        or not isinstance(directories, list)
        or not isinstance(files, list)
        or not files
    ):
        raise ComponentManifestError("Native component manifest schema is invalid")
    root_mode = manifest.get("root_mode")
    if root_mode != stat.S_IMODE(root.stat().st_mode):
        raise ComponentManifestError("Native component root mode mismatch")
    seen_directories: set[str] = set()
    normalized_directories: list[dict[str, object]] = []
    for record in directories:
        if not isinstance(record, dict):
            raise ComponentManifestError("Native component manifest contains an invalid directory")
        relative = record.get("path")
        if not isinstance(relative, str):
            raise ComponentManifestError("Native component manifest contains an invalid directory path")
        value = PurePosixPath(relative)
        if value.is_absolute() or not value.parts or any(part in {"", ".", ".."} for part in value.parts):
            raise ComponentManifestError("Native component manifest contains an unsafe directory path")
        path = root.joinpath(*value.parts)
        if (
            relative in seen_directories
            or path.is_symlink()
            or not path.is_dir()
            or record.get("mode") != stat.S_IMODE(path.stat().st_mode)
        ):
            raise ComponentManifestError(f"Native component directory mismatch: {relative}")
        try:
            path.resolve(strict=True).relative_to(root.resolve(strict=True))
        except ValueError as error:
            raise ComponentManifestError("Native component directory escapes its root") from error
        seen_directories.add(relative)
        normalized_directories.append(dict(record))
    seen: set[str] = set()
    normalized: list[dict[str, object]] = []
    for record in files:
        if not isinstance(record, dict):
            raise ComponentManifestError("Native component manifest contains an invalid record")
        relative = record.get("path")
        path = manifest_file(root, relative)
        metadata = path.stat()
        expected_digest = record.get("sha256")
        if (
            relative in seen
            or not isinstance(expected_digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", expected_digest)
            or record.get("size") != metadata.st_size
            or record.get("mode") != stat.S_IMODE(metadata.st_mode)
            or sha256_file(path) != expected_digest
        ):
            raise ComponentManifestError(f"Native component record mismatch: {relative}")
        seen.add(relative)
        normalized.append(dict(record))
    actual_root_mode, actual_directories, actual_records = canonical_tree_records(root)
    if (
        root_mode != actual_root_mode
        or normalized_directories != actual_directories
        or normalized != actual_records
    ):
        raise ComponentManifestError("Native component manifest does not cover the exact tree")
    expected_tree = manifest.get("tree_sha256")
    if (
        not isinstance(expected_tree, str)
        or tree_digest(root_mode, normalized_directories, normalized) != expected_tree
    ):
        raise ComponentManifestError("Native component tree digest mismatch")
    return manifest


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--root", type=Path, required=True)
    value.add_argument("--manifest", type=Path, required=True)
    value.add_argument("--expected-name")
    return value


if __name__ == "__main__":
    args = parser().parse_args()
    try:
        verify(args.root.resolve(), args.manifest.resolve(), expected_name=args.expected_name)
    except (ComponentManifestError, OSError, TypeError, ValueError) as error:
        print(f"Native component manifest verification failed: {error}", file=__import__("sys").stderr)
        raise SystemExit(1)
    print(json.dumps({"status": "ok"}, sort_keys=True, separators=(",", ":")))

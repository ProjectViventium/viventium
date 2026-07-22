#!/usr/bin/env python3
"""Fail closed when a Native candidate contains producer-local or secret material."""

from __future__ import annotations

import argparse
import json
import re
import stat
import sys
from pathlib import Path


class PublicSafetyError(RuntimeError):
    pass


FORBIDDEN_DIRECTORY_NAMES = {".cache", "__pycache__"}
FORBIDDEN_FILE_SUFFIXES = ("-audit.json", ".log", ".pyc", ".pyo")
OWNED_SURFACES = (
    Path("payload/apps"),
    Path("payload/bin"),
    Path("payload/release-metadata"),
    Path("payload/runtime/defaults"),
    Path("payload/runtime/scripts"),
    Path("bootstrap"),
)
THIRD_PARTY_RUNTIME_SURFACES = (
    Path("bootstrap/ViventiumBootstrap.app/Contents/Resources/runtime"),
)
CUSTOMIZED_RUNTIME_SURFACES = (
    Path("payload/runtime/librechat"),
)
PRIVATE_PATH_PATTERNS = (
    ("private absolute path", re.compile(rb"/(?:Users|home)/[^/\x00\s\"']+/")),
    ("private temporary path", re.compile(rb"/(?:private/)?var/folders/")),
)
SECRET_PATTERNS = (
    ("high-confidence secret", re.compile(rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b")),
    ("high-confidence secret", re.compile(rb"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    ("high-confidence secret", re.compile(rb"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("high-confidence secret", re.compile(rb"-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----")),
)
CHUNK_SIZE = 1024 * 1024
OVERLAP_SIZE = 512


def candidate_files(root: Path) -> list[Path]:
    if root.is_symlink() or not root.is_dir():
        raise PublicSafetyError("candidate root must be a real directory")
    if not (root / "payload").is_dir() or not (root / "bootstrap").is_dir():
        raise PublicSafetyError("candidate root is incomplete")
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        try:
            metadata = path.lstat()
        except OSError as error:
            raise PublicSafetyError(f"candidate changed while scanning: {relative}") from error
        if stat.S_ISLNK(metadata.st_mode):
            raise PublicSafetyError(f"forbidden symlink artifact: {relative}")
        if stat.S_ISDIR(metadata.st_mode):
            continue
        if not stat.S_ISREG(metadata.st_mode):
            raise PublicSafetyError(f"forbidden non-regular artifact: {relative}")
        files.append(path)
    return files


def is_owned_surface(relative: Path) -> bool:
    in_owned_surface = any(
        relative == surface or surface in relative.parents for surface in OWNED_SURFACES
    )
    in_third_party_runtime = any(
        relative == surface or surface in relative.parents
        for surface in THIRD_PARTY_RUNTIME_SURFACES
    )
    return in_owned_surface and not in_third_party_runtime


def should_scan_generic_patterns(relative: Path) -> bool:
    if is_owned_surface(relative):
        return True
    for surface in CUSTOMIZED_RUNTIME_SURFACES:
        if relative != surface and surface not in relative.parents:
            continue
        customized_relative = relative.relative_to(surface)
        # Dependency packages carry their own documentation, fixtures and source maps.
        # The assembler verifies their exact graph separately; generic path/secret
        # patterns apply to the customized app and compiled output around them.
        return "node_modules" not in customized_relative.parts
    return False


def scan_patterns(path: Path, patterns: tuple[tuple[str, re.Pattern[bytes]], ...]) -> set[str]:
    labels: set[str] = set()
    tail = b""
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK_SIZE):
            data = tail + chunk
            labels.update(label for label, pattern in patterns if pattern.search(data))
            tail = data[-OVERLAP_SIZE:]
    return labels


def scan_exact_prefixes(path: Path, prefixes: tuple[bytes, ...]) -> bool:
    if not prefixes:
        return False
    overlap = max(len(prefix) for prefix in prefixes) - 1
    tail = b""
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK_SIZE):
            data = tail + chunk
            if any(prefix in data for prefix in prefixes):
                return True
            tail = data[-overlap:] if overlap else b""
    return False


def verify(root: Path, forbidden_prefixes: list[str]) -> dict[str, object]:
    root = root.absolute()
    files = candidate_files(root)
    prefixes = tuple(
        prefix.rstrip("/").encode("utf-8")
        for prefix in forbidden_prefixes
        if prefix.strip().rstrip("/")
    )
    findings: list[str] = []
    scanned_bytes = 0
    for path in files:
        relative = path.relative_to(root)
        scanned_bytes += path.stat().st_size
        if any(part in FORBIDDEN_DIRECTORY_NAMES for part in relative.parts) or relative.name.endswith(
            FORBIDDEN_FILE_SUFFIXES
        ):
            findings.append(f"forbidden artifact path: {relative.as_posix()}")
        if scan_exact_prefixes(path, prefixes):
            findings.append(f"forbidden producer prefix: {relative.as_posix()}")
        if should_scan_generic_patterns(relative):
            for label in sorted(scan_patterns(path, PRIVATE_PATH_PATTERNS + SECRET_PATTERNS)):
                findings.append(f"{label}: {relative.as_posix()}")

    if findings:
        raise PublicSafetyError("\n".join(sorted(set(findings))))
    return {
        "files": len(files),
        "scanned_bytes": scanned_bytes,
        "status": "pass",
    }


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--candidate-root", type=Path, required=True)
    value.add_argument(
        "--forbid-prefix",
        action="append",
        default=[],
        help="Exact producer-local path prefix to reject in every artifact byte",
    )
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        result = verify(args.candidate_root, args.forbid_prefix)
    except (OSError, PublicSafetyError) as error:
        print(f"Native public-safety verification failed:\n{error}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

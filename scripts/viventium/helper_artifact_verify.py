#!/usr/bin/env python3
"""Read-only verification for the shipped macOS helper artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path


SOURCE_FILES = (
    Path("Package.swift"),
    Path("Sources/ViventiumHelper/ViventiumHelperApp.swift"),
    Path("Sources/ViventiumHelper/Resources/Info.plist"),
)
SHA256 = re.compile(r"^[0-9a-f]{64}$")


class HelperArtifactError(RuntimeError):
    pass


def require_owned_regular(path: Path, label: str) -> None:
    try:
        metadata = path.lstat()
    except FileNotFoundError as error:
        raise HelperArtifactError(f"{label} is missing") from error
    if (
        path.is_symlink()
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.getuid()
    ):
        raise HelperArtifactError(f"{label} is not an owner-controlled regular file")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def helper_source_hash(package_dir: Path) -> str:
    digest = hashlib.sha256()
    for relative in SOURCE_FILES:
        path = package_dir / relative
        require_owned_regular(path, f"helper source {relative.as_posix()}")
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def read_digest(path: Path, label: str) -> str:
    require_owned_regular(path, label)
    value = path.read_text(encoding="utf-8").strip().lower()
    if not SHA256.fullmatch(value):
        raise HelperArtifactError(f"{label} is not a SHA-256 digest")
    return value


def verify_architectures(binary: Path) -> list[str]:
    if sys.platform != "darwin":
        return []
    completed = subprocess.run(
        ["/usr/bin/lipo", "-archs", str(binary)],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    architectures = completed.stdout.split()
    if completed.returncode != 0 or set(architectures) != {"arm64", "x86_64"}:
        raise HelperArtifactError(
            "shipped helper is not the required arm64/x86_64 universal artifact"
        )
    return sorted(architectures)


def verify(package_dir: Path) -> dict[str, object]:
    package_dir = Path(os.path.abspath(os.path.expanduser(str(package_dir))))
    metadata = package_dir.lstat()
    if (
        package_dir.is_symlink()
        or not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != os.getuid()
    ):
        raise HelperArtifactError("helper package directory is unsafe")

    prebuilt = package_dir / "prebuilt"
    binary = prebuilt / "ViventiumHelper-universal"
    source_digest_path = prebuilt / "source.sha256"
    binary_digest_path = prebuilt / "binary.sha256"
    require_owned_regular(binary, "shipped helper binary")
    if not os.access(binary, os.X_OK):
        raise HelperArtifactError("shipped helper binary is not executable")

    expected_source = read_digest(source_digest_path, "helper source digest")
    actual_source = helper_source_hash(package_dir)
    if expected_source != actual_source:
        raise HelperArtifactError("helper source digest does not match the shipped sources")

    expected_binary = read_digest(binary_digest_path, "helper binary digest")
    actual_binary = sha256_file(binary)
    if expected_binary != actual_binary:
        raise HelperArtifactError("helper binary digest does not match the shipped artifact")

    return {
        "schemaVersion": 1,
        "status": "ok",
        "sourceSha256": actual_source,
        "binarySha256": actual_binary,
        "architectures": verify_architectures(binary),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = verify(args.package_dir)
    except (HelperArtifactError, OSError, UnicodeError, subprocess.SubprocessError) as error:
        print(f"Viventium helper artifact verification failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

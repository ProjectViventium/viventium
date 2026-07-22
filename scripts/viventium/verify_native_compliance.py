#!/usr/bin/env python3
"""Fail closed unless an exact payload carries its required compliance bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path, PurePosixPath

from generate_native_compliance import (
    ComplianceError,
    browser_inventory,
    scan_package_record,
)
from verify_native_component_manifest import verify as verify_component_manifest


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def payload_file(payload: Path, relative: object) -> Path:
    if not isinstance(relative, str):
        raise RuntimeError("Native license scan contains an invalid path")
    value = PurePosixPath(relative)
    if value.is_absolute() or not value.parts or ".." in value.parts:
        raise RuntimeError("Native license scan contains an unsafe path")
    path = payload.joinpath(*value.parts)
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f"Native license file is missing: {relative}")
    try:
        path.resolve(strict=True).relative_to(payload)
    except ValueError as error:
        raise RuntimeError("Native license scan escapes the payload") from error
    return path


def locked_js_paths(payload: Path) -> set[str]:
    root = payload / "runtime" / "librechat"
    lock = json.loads((root / "package-lock.json").read_text(encoding="utf-8"))
    records = lock.get("packages")
    if lock.get("lockfileVersion") not in (2, 3) or not isinstance(records, dict):
        raise RuntimeError("Native LibreChat package-lock graph is invalid")
    paths = {"runtime/librechat"}
    for relative, record in records.items():
        if relative == "":
            continue
        if not isinstance(relative, str) or not isinstance(record, dict):
            raise RuntimeError("Native LibreChat package-lock graph is invalid")
        value = PurePosixPath(relative)
        if value.is_absolute() or ".." in value.parts:
            raise RuntimeError("Native LibreChat package-lock graph contains an unsafe path")
        metadata = root.joinpath(*value.parts) / "package.json"
        if metadata.is_file():
            paths.add(f"runtime/librechat/{relative}")
    return paths


def verify(payload: Path) -> None:
    payload = payload.resolve(strict=True)
    metadata = payload / "release-metadata"
    paths = {
        "sbom": metadata / "native-sbom.spdx.json",
        "notices": metadata / "native-third-party-notices.txt",
        "scan": metadata / "native-license-scan.json",
    }
    if any(path.is_symlink() or not path.is_file() or path.stat().st_size == 0 for path in paths.values()):
        raise RuntimeError("Native compliance bundle is incomplete")
    sbom = json.loads(paths["sbom"].read_text(encoding="utf-8"))
    scan = json.loads(paths["scan"].read_text(encoding="utf-8"))
    if sbom.get("spdxVersion") != "SPDX-2.3" or not isinstance(sbom.get("packages"), list):
        raise RuntimeError("Native SPDX SBOM is invalid")
    if scan.get("schema_version") != 1 or scan.get("status") != "pass":
        raise RuntimeError("Native license scan has unresolved review items")
    required = {"Node.js", "Python standalone runtime", "MongoDB Community Server", "LibreChat"}
    names = {package.get("name") for package in scan.get("packages", []) if isinstance(package, dict)}
    if not required <= names:
        raise RuntimeError("Native license scan omits a bundled runtime")
    if any(not package.get("allowed") for package in scan["packages"]):
        raise RuntimeError("Native license scan contains unapproved licenses")
    build = json.loads((metadata / "build.json").read_text(encoding="utf-8"))
    python_component = build.get("components", {}).get("python", "")
    if isinstance(python_component, dict):
        python_component = python_component.get("version", "")
    python_version = str(python_component)
    version_match = re.fullmatch(r"(\d+)\.(\d+)\.\d+", python_version)
    if version_match is None:
        raise RuntimeError("Native build metadata has an invalid Python version")
    python_minor = f"{version_match.group(1)}.{version_match.group(2)}"
    required_paths = {
        "runtime/node/LICENSE",
        f"runtime/python/lib/python{python_minor}/LICENSE.txt",
        "runtime/mongodb/LICENSE-Community.txt",
        "runtime/mongodb/THIRD-PARTY-NOTICES",
        "runtime/librechat/LICENSE",
    }
    inventoried_paths: set[str] = set()
    for package in scan["packages"]:
        if not isinstance(package, dict):
            raise RuntimeError("Native license scan contains an invalid package")
        relative_paths = package.get("license_files")
        hashes = package.get("license_file_sha256")
        if (
            not isinstance(relative_paths, list)
            or not relative_paths
            or not isinstance(hashes, dict)
            or package.get("notice_present") is not True
        ):
            raise RuntimeError("Native license scan omits license hashes")
        if set(relative_paths) != set(hashes):
            raise RuntimeError("Native license path and hash inventories disagree")
        for relative in relative_paths:
            path = payload_file(payload, relative)
            expected = hashes.get(relative)
            if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
                raise RuntimeError("Native license scan contains an invalid digest")
            if sha256_file(path) != expected:
                raise RuntimeError(f"Native license hash mismatch: {relative}")
            inventoried_paths.add(relative)
    if not required_paths <= inventoried_paths:
        raise RuntimeError("Native license scan omits a required component license path")
    python_root = payload / "runtime" / "python"
    forbidden_python_surfaces = (
        python_root / "bin" / "pip",
        python_root / "bin" / "pip3",
        python_root / "lib" / f"python{python_minor}" / "site-packages",
        python_root / "lib" / f"python{python_minor}" / "ensurepip",
        python_root / "lib" / f"python{python_minor}" / "venv",
    )
    if any(path.exists() or path.is_symlink() for path in forbidden_python_surfaces):
        raise RuntimeError("Native Python runtime contains an unneeded package-manager surface")
    if any(path.suffix in {".pyc", ".pyo"} for path in python_root.rglob("*")):
        raise RuntimeError("Native Python runtime contains generated bytecode")
    python_manifest = metadata / "python-runtime-manifest.json"
    verified_python = verify_component_manifest(
        python_root,
        python_manifest,
        expected_name="python",
    )
    if verified_python.get("component") != {"name": "python", **build["components"]["python"]}:
        raise RuntimeError("Native Python component manifest does not match build policy")
    inventory_scopes = {
        package.get("inventory_scope")
        for package in scan["packages"]
        if isinstance(package, dict)
    }
    if not inventory_scopes <= {"physical-runtime", "compiled-browser"}:
        raise RuntimeError("Native license scan contains an unsupported inventory scope")
    scanned_js_paths = [
        package.get("path")
        for package in scan["packages"]
        if package.get("inventory_scope") == "physical-runtime"
        and isinstance(package.get("path"), str)
        and (
            package["path"] == "runtime/librechat"
            or package["path"].startswith("runtime/librechat/")
        )
    ]
    if len(scanned_js_paths) != len(set(scanned_js_paths)):
        raise RuntimeError("Native license scan duplicates a physical JavaScript package path")
    if set(scanned_js_paths) != locked_js_paths(payload):
        raise RuntimeError("Native license scan does not match the physical package-lock graph")
    scanned_browser = [
        package
        for package in scan["packages"]
        if package.get("inventory_scope") == "compiled-browser"
    ]
    expected_browser = [
        scan_package_record(payload, package)
        for package in browser_inventory(payload)
    ]
    if scanned_browser != expected_browser:
        raise RuntimeError("Native license scan does not match the compiled browser closure")
    notices_digest = scan.get("notices_sha256")
    if not isinstance(notices_digest, str) or sha256_file(paths["notices"]) != notices_digest:
        raise RuntimeError("Native consolidated notices hash mismatch")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--payload-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        verify(args.payload_root.resolve())
    except (
        ComplianceError,
        OSError,
        KeyError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
        RuntimeError,
    ) as error:
        print(f"Native compliance verification failed: {error}", file=__import__("sys").stderr)
        raise SystemExit(1)

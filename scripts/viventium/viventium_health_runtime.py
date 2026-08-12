#!/usr/bin/env python3
"""Build and inspect the private, self-contained Viventium-Health runtime."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import uuid
import venv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


COMPONENT_NAME = "Viventium-Health"
RUNTIME_SCHEMA_VERSION = 1


class HealthRuntimeError(RuntimeError):
    """Raised when the private health runtime cannot be built safely."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _private_dir(path: Path) -> None:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.chmod(0o700)


def _component_entry(repo_root: Path) -> dict[str, Any]:
    try:
        payload = json.loads((repo_root / "components.lock.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HealthRuntimeError("components.lock.json is unavailable or invalid") from exc
    for row in payload.get("components") or []:
        if isinstance(row, dict) and row.get("name") == COMPONENT_NAME:
            return row
    raise HealthRuntimeError("Viventium-Health is not registered in components.lock.json")


def _package_source(repo_root: Path, entry: dict[str, Any]) -> Path:
    component_path = repo_root / str(entry.get("path") or "")
    source = component_path / "src" / "viventium_health"
    if not (component_path / "pyproject.toml").is_file() or not (source / "__main__.py").is_file():
        raise HealthRuntimeError("the pinned Viventium-Health component is not bootstrapped")
    resolved_component = component_path.resolve()
    resolved_source = source.resolve()
    if resolved_component not in resolved_source.parents:
        raise HealthRuntimeError("the Viventium-Health package source escapes its component root")
    return resolved_source


def _verify_component_checkout(repo_root: Path, entry: dict[str, Any]) -> None:
    component_path = repo_root / str(entry.get("path") or "")
    if not (component_path / ".git").exists():
        raise HealthRuntimeError(
            "the Viventium-Health checkout has no git metadata to verify its parent lock pin"
        )
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=component_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    expected = str(entry.get("ref") or "").strip()
    if not expected or head != expected:
        raise HealthRuntimeError("the Viventium-Health checkout does not match its parent lock pin")
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--", "pyproject.toml", "src/viventium_health"],
        cwd=component_path,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if dirty:
        raise HealthRuntimeError("the Viventium-Health package source has uncommitted changes")


def _package_hash(source: Path) -> str:
    digest = hashlib.sha256()
    if any(path.is_symlink() for path in source.rglob("*")):
        raise HealthRuntimeError("the Viventium-Health package contains an unsupported symlink")
    files = sorted(path for path in source.rglob("*.py") if path.is_file() and not path.is_symlink())
    if not files:
        raise HealthRuntimeError("the Viventium-Health package has no Python sources")
    for path in files:
        relative = path.relative_to(source).as_posix().encode("utf-8")
        body = path.read_bytes()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(len(body).to_bytes(8, "big"))
        digest.update(body)
    return digest.hexdigest()


def _venv_python(runtime_dir: Path) -> Path:
    return runtime_dir / ("Scripts" if os.name == "nt" else "bin") / (
        "python.exe" if os.name == "nt" else "python"
    )


def _purelib(runtime_dir: Path) -> Path:
    python = _venv_python(runtime_dir)
    result = subprocess.run(
        [str(python), "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"],
        check=True,
        capture_output=True,
        text=True,
    )
    path = Path(result.stdout.strip())
    if runtime_dir.resolve() not in path.resolve().parents:
        raise HealthRuntimeError("the health runtime resolved an unsafe site-packages directory")
    return path


def _copy_package(source: Path, destination: Path) -> None:
    def ignore(_directory: str, names: list[str]) -> set[str]:
        return {name for name in names if name == "__pycache__" or name.endswith((".pyc", ".pyo"))}

    shutil.copytree(source, destination, ignore=ignore)
    for path in destination.rglob("*"):
        if path.is_symlink():
            raise HealthRuntimeError("the health package contains an unsupported symlink")
        path.chmod(0o700 if path.is_dir() else 0o600)
    destination.chmod(0o700)


def _write_wrapper(runtime_dir: Path) -> Path:
    bin_dir = runtime_dir / ("Scripts" if os.name == "nt" else "bin")
    if os.name == "nt":
        raise HealthRuntimeError("the installed health runtime currently supports macOS/Linux only")
    wrapper = bin_dir / "viventium-health"
    wrapper.write_text(
        "#!/bin/sh\n"
        "set -eu\n"
        "runtime_bin=$(CDPATH= cd -- \"$(dirname -- \"$0\")\" && pwd)\n"
        "exec \"$runtime_bin/python\" -m viventium_health \"$@\"\n",
        encoding="utf-8",
    )
    wrapper.chmod(0o700)
    return wrapper


def _write_manifest(runtime_dir: Path, payload: dict[str, Any]) -> None:
    path = runtime_dir / "manifest.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    path.chmod(0o600)


def _matching_runtime_manifest(
    runtime_dir: Path,
    *,
    component_ref: str,
    package_sha256: str,
) -> dict[str, Any] | None:
    executable = runtime_dir / "bin" / "viventium-health"
    manifest_path = runtime_dir / "manifest.json"
    if runtime_dir.is_symlink() or not executable.is_file() or not os.access(executable, os.X_OK):
        return None
    try:
        if stat.S_IMODE(runtime_dir.stat().st_mode) != 0o700:
            return None
        if stat.S_IMODE(executable.stat().st_mode) != 0o700:
            return None
        if stat.S_IMODE(manifest_path.stat().st_mode) != 0o600:
            return None
    except OSError:
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(manifest, dict):
        return None
    if manifest.get("schemaVersion") != RUNTIME_SCHEMA_VERSION:
        return None
    if manifest.get("component") != COMPONENT_NAME:
        return None
    if manifest.get("componentRef") != component_ref:
        return None
    if manifest.get("packageSha256") != package_sha256:
        return None
    installed_packages = list(
        (runtime_dir / "lib").glob("python*/site-packages/viventium_health")
    )
    if len(installed_packages) != 1:
        return None
    try:
        if _package_hash(installed_packages[0]) != package_sha256:
            return None
    except (HealthRuntimeError, OSError):
        return None
    return manifest


def install_runtime(*, repo_root: Path, app_support_dir: Path) -> dict[str, Any]:
    repo_root = repo_root.expanduser().resolve()
    app_support_dir = app_support_dir.expanduser().resolve()
    entry = _component_entry(repo_root)
    _verify_component_checkout(repo_root, entry)
    source = _package_source(repo_root, entry)
    component_ref = str(entry.get("ref") or "")
    package_sha256 = _package_hash(source)
    health_root = app_support_dir / "health"
    _private_dir(health_root)
    target = health_root / "runtime"
    current_manifest = _matching_runtime_manifest(
        target,
        component_ref=component_ref,
        package_sha256=package_sha256,
    )
    if current_manifest is not None:
        return {"status": "ready", **current_manifest}
    staging = health_root / f".runtime.install-{uuid.uuid4().hex}"
    backup = health_root / f".runtime.previous-{uuid.uuid4().hex}"
    moved_existing = False
    try:
        venv.EnvBuilder(with_pip=False, clear=True, symlinks=True).create(staging)
        staging.chmod(0o700)
        purelib = _purelib(staging)
        _copy_package(source, purelib / "viventium_health")
        wrapper = _write_wrapper(staging)
        version = subprocess.run(
            [str(wrapper), "--version"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        manifest = {
            "schemaVersion": RUNTIME_SCHEMA_VERSION,
            "component": COMPONENT_NAME,
            "componentRef": component_ref,
            "packageSha256": package_sha256,
            "packageVersion": version.removeprefix("viventium-health "),
            "pythonVersion": ".".join(str(part) for part in sys.version_info[:3]),
            "installedAt": _utc_now(),
        }
        _write_manifest(staging, manifest)
        if target.exists():
            os.replace(target, backup)
            moved_existing = True
        os.replace(staging, target)
        if moved_existing:
            shutil.rmtree(backup)
        return {"status": "installed", **manifest}
    except Exception:
        if moved_existing and not target.exists() and backup.exists():
            os.replace(backup, target)
        raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)
        if target.exists():
            shutil.rmtree(backup, ignore_errors=True)


def runtime_status(*, app_support_dir: Path) -> dict[str, Any]:
    runtime = app_support_dir.expanduser() / "health" / "runtime"
    executable = runtime / "bin" / "viventium-health"
    manifest_path = runtime / "manifest.json"
    if not executable.is_file() or not os.access(executable, os.X_OK) or not manifest_path.is_file():
        return {
            "status": "missing",
            "executable": executable.is_file() and os.access(executable, os.X_OK),
            "manifest": manifest_path.is_file(),
            "componentRef": None,
        }
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "status": "invalid",
            "executable": True,
            "manifest": False,
            "componentRef": None,
        }
    return {
        "status": "ready",
        "executable": True,
        "manifest": True,
        "componentRef": manifest.get("componentRef"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Install or inspect the private Viventium-Health runtime")
    parser.add_argument("action", choices=("install", "status"))
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--app-support-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.action == "install":
            if args.repo_root is None:
                parser.error("install requires --repo-root")
            payload = install_runtime(repo_root=args.repo_root, app_support_dir=args.app_support_dir)
        else:
            payload = runtime_status(app_support_dir=args.app_support_dir)
        print(json.dumps(payload, sort_keys=True))
        return 0 if payload["status"] in {"installed", "ready"} else 1
    except (HealthRuntimeError, OSError, subprocess.SubprocessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

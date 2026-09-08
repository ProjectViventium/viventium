#!/usr/bin/env python3
"""Assemble an exact relocatable macOS Native payload candidate."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import tarfile
import tomllib
from pathlib import Path, PurePosixPath

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bootstrap_components import load_lockfile  # noqa: E402
from helper_bundle_transaction import owner_marker_bytes  # noqa: E402
from native_runtime import RuntimeError_ as NativeRuntimeError, helper_owner, load_native_runtime_env  # noqa: E402
from stage_native_component import StagingError, stage_component  # noqa: E402
from verify_native_macos_compatibility import is_macho  # noqa: E402
from verify_native_component_manifest import (  # noqa: E402
    ComponentManifestError,
    build_manifest as build_component_manifest,
)


class AssemblyError(RuntimeError):
    pass


EXCLUDED_NAMES = {
    ".DS_Store",
    ".cache",
    ".git",
    ".github",
    ".npmrc",
    ".pnpm-store",
    ".pytest_cache",
    ".turbo",
    ".venv",
    ".yarn",
    "__pycache__",
    "coverage",
    "e2e",
    "playwright-report",
    "test-results",
}
SECRET_NAMES = {
    ".env",
    ".env.local",
    "librechat.env",
    "librechat.owner.env",
    "runtime.env",
    "runtime.local.env",
    "id_rsa",
    "id_ed25519",
}
SECRET_DIRECTORY_NAMES = {"service-env"}
SANDPACK_INDEX_SHA256 = "ace51687532a2e9cbfcc11d790bc96b250c477cfa3545ab285915b9eca8e7aa6"
SANDPACK_ON_PREM_MARKER = b'IS_ONPREM:"true"'


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_real_directory(path: Path, label: str) -> Path:
    if path.is_symlink() or not path.is_dir():
        raise AssemblyError(f"{label} must be a real directory")
    return path.resolve()


def should_exclude(path: Path) -> bool:
    return path.name in EXCLUDED_NAMES or path.name.endswith(
        (".log", ".tmp", ".pyc", ".pyo", "-audit.json")
    )


def is_librechat_development_source(relative: Path) -> bool:
    if "node_modules" in relative.parts:
        return False
    return (
        relative == Path("librechat.example.yaml")
        or Path("client/src") == relative
        or Path("client/src") in relative.parents
        or any(part in {"test", "tests", "__tests__"} for part in relative.parts)
        or (relative.suffix in {".js", ".jsx", ".ts", ".tsx", ".cjs", ".mjs"}
            and relative.stem.endswith((".test", ".spec")))
    )


def copy_safe(
    source: Path,
    destination: Path,
    *,
    boundary: Path,
    source_date_epoch: int,
    active: tuple[Path, ...] = (),
    customized_librechat: bool = False,
) -> None:
    if source.name in SECRET_DIRECTORY_NAMES:
        raise AssemblyError(f"secret-shaped input directory is forbidden: {source.name}")
    if source.name in SECRET_NAMES:
        raise AssemblyError(f"secret-shaped input is forbidden: {source.name}")
    if should_exclude(source) or (
        customized_librechat and is_librechat_development_source(source.relative_to(boundary))
    ):
        return
    try:
        metadata = source.lstat()
    except OSError as error:
        raise AssemblyError("source changed during assembly") from error
    if stat.S_ISLNK(metadata.st_mode):
        try:
            target = source.resolve(strict=True)
            target.relative_to(boundary)
        except (OSError, ValueError) as error:
            raise AssemblyError("source contains an escaping or broken symlink") from error
        if target in active:
            raise AssemblyError("source contains a symlink cycle")
        copy_safe(
            target,
            destination,
            boundary=boundary,
            source_date_epoch=source_date_epoch,
            active=(*active, target),
            customized_librechat=customized_librechat,
        )
        return
    if stat.S_ISDIR(metadata.st_mode):
        destination.mkdir(parents=True, exist_ok=True)
        destination.chmod(0o755)
        for child in sorted(source.iterdir(), key=lambda item: item.name):
            copy_safe(
                child,
                destination / child.name,
                boundary=boundary,
                source_date_epoch=source_date_epoch,
                active=active,
                customized_librechat=customized_librechat,
            )
        os.utime(destination, (source_date_epoch, source_date_epoch), follow_symlinks=False)
        return
    if not stat.S_ISREG(metadata.st_mode):
        raise AssemblyError("source contains a non-regular file")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination, follow_symlinks=False)
    destination.chmod(0o755 if metadata.st_mode & 0o111 else 0o644)
    os.utime(destination, (source_date_epoch, source_date_epoch), follow_symlinks=False)


def write_file(path: Path, content: str, mode: int, source_date_epoch: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(mode)
    os.utime(path, (source_date_epoch, source_date_epoch), follow_symlinks=False)


def read_components(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AssemblyError("Native component policy is unavailable or invalid") from error
    if payload.get("schema_version") != 1:
        raise AssemblyError("Native component policy schema is unsupported")
    return payload


def validate_native_compiled_defaults(compiled: Path, *, packaged_native_bodies: bool = False) -> None:
    """Reject provider advertisements for runtimes absent from the Native payload."""

    config_path = compiled / "config.yaml"
    try:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as error:
        raise AssemblyError("Native compiled default is unavailable or invalid: config.yaml") from error
    glasshive = (config.get("integrations") or {}).get("glasshive") or {}
    enabled_paths = {
        "integrations.glasshive.enabled": glasshive.get("enabled"),
        "integrations.glasshive.provider.enabled": (
            glasshive.get("provider") or {}
        ).get("enabled"),
        "integrations.glasshive.host_worker.enabled": (
            glasshive.get("host_worker") or {}
        ).get("enabled"),
    }
    enabled = next((path for path, value in enabled_paths.items() if value is True), "")
    if enabled and not packaged_native_bodies:
        raise AssemblyError(f"Native compiled defaults enable unavailable GlassHive runtime: {enabled}")

    forbidden_markers = () if packaged_native_bodies else ("glasshive-harness", "glasshive-workers-projects")
    for name in (
        "config.yaml",
        "librechat.yaml",
        "prompt-bundle.json",
        "native-runtime.env",
        "viventium-agents.yaml",
    ):
        path = compiled / name
        try:
            body = path.read_text(encoding="utf-8").lower()
        except OSError as error:
            raise AssemblyError(f"Native compiled default is unavailable: {name}") from error
        leaked = next((marker for marker in forbidden_markers if marker in body), "")
        if leaked:
            raise AssemblyError(
                f"Native compiled defaults advertise unavailable GlassHive runtime: {name}"
            )


def is_lower_hex(value: object, length: int) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and all(character in "0123456789abcdef" for character in value)
    )


def selected_component_pin(repo: Path, name: str) -> str:
    """Resolve source selection from the same parent lock used by bootstrap."""
    try:
        lock = load_lockfile(repo / "components.lock.json")
        records = lock.get("components") if isinstance(lock, dict) else None
        if not isinstance(records, list):
            raise ValueError("missing components")
        pins = [record.get("ref") for record in records if isinstance(record, dict) and record.get("name") == name]
        if len(pins) != 1 or not is_lower_hex(pins[0], 40):
            raise ValueError("invalid exact selection")
    except (OSError, ValueError) as error:
        raise AssemblyError(f"{name} parent component pin is invalid") from error
    return str(pins[0])


def release_component_manifest(
    components: dict[str, object], arch: str, repo: Path
) -> dict[str, dict[str, str]]:
    # Source selection belongs to components.lock.json; build.json freezes that
    # choice in each immutable artifact. Binary policy holds publisher digests.
    if "librechat" in components:
        raise AssemblyError("Native source pins belong only in components.lock.json")
    manifest: dict[str, dict[str, str]] = {
        "librechat": {"commit": selected_component_pin(repo, "LibreChat")}
    }
    for name in ("mongodb", "node", "python"):
        component = components.get(name)
        if not isinstance(component, dict):
            raise AssemblyError(f"Native {name} component policy is invalid")
        version = component.get("version")
        architectures = component.get("architectures")
        architecture = architectures.get(arch) if isinstance(architectures, dict) else None
        digest = architecture.get("sha256") if isinstance(architecture, dict) else None
        if not isinstance(version, str) or not version.strip():
            raise AssemblyError(f"Native {name} component version is invalid")
        if not is_lower_hex(digest, 64):
            raise AssemblyError(f"Native {name} {arch} component digest is invalid")
        manifest[name] = {
            "archive_sha256": str(digest),
            "version": version,
        }
        if name == "python":
            license_source = component.get("license_source")
            license_commit = (
                license_source.get("commit") if isinstance(license_source, dict) else None
            )
            license_digest = (
                license_source.get("sha256") if isinstance(license_source, dict) else None
            )
            if not is_lower_hex(license_commit, 40) or not is_lower_hex(license_digest, 64):
                raise AssemblyError("Native Python license-source policy is invalid")
            manifest[name]["license_source_commit"] = str(license_commit)
            manifest[name]["license_source_sha256"] = str(license_digest)
    return manifest


def command_output(command: list[str]) -> str:
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        raise AssemblyError("candidate component validation failed")
    return completed.stdout + completed.stderr


def run_glasshive_build(command: list[str], *, env: dict[str, str]) -> None:
    completed = subprocess.run(command, env=env, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        # Build logs can contain local cache paths or registry credentials. The failed
        # command can be rerun in the build workspace; do not publish its environment.
        raise AssemblyError("GlassHive locked dependency build failed")


def stage_glasshive(
    repo: Path, source: Path, python: Path, uv: Path, output: Path, *, source_date_epoch: int,
    local_qa_worktree: bool = False,
) -> dict[str, str]:
    """Package the selected first-party source and its existing production lock."""
    source = ensure_real_directory(source, "GlassHive source")
    pin = selected_component_pin(repo, "GlassHive")
    paths = (
        "LICENSE", "runtime_phase1/pyproject.toml", "runtime_phase1/uv.lock",
        "runtime_phase1/src", "runtime_phase1/workstation-requirements.lock",
        "runtime_phase1/runtime_locks",
    )
    actual = command_output(["git", "-C", str(source), "rev-parse", "HEAD"]).strip()
    dirty = command_output(["git", "-C", str(source), "status", "--porcelain", "--untracked-files=all", "--", *paths])
    if actual != pin or (dirty and not local_qa_worktree):
        raise AssemblyError("GlassHive source differs from the selected parent pin")
    for path, label in ((python, "Python"), (uv, "uv build tool")):
        if not path.is_file() or not os.access(path, os.X_OK):
            raise AssemblyError(f"GlassHive {label} is unavailable")
    if output.exists():
        raise AssemblyError("GlassHive staging output already exists")
    selection = ["--cached", "--others", "--exclude-standard"] if local_qa_worktree else []
    tracked = sorted(set(command_output(["git", "-C", str(source), "ls-files", *selection, "--", *paths]).splitlines()))
    source_digest = hashlib.sha256()
    for relative in tracked:
        destination = relative.removeprefix("runtime_phase1/")
        copy_safe(source / relative, output / destination, boundary=source, source_date_epoch=source_date_epoch)
        source_digest.update(relative.encode("utf-8") + b"\0" + sha256_file(output / destination).encode("ascii") + b"\n")
    for relative in ("LICENSE", "pyproject.toml", "uv.lock", "workstation-requirements.lock", "src/workers_projects_runtime/api.py"):
        if not (output / relative).is_file():
            raise AssemblyError("GlassHive selected source is incomplete")
    requirements = output / "requirements.txt"
    with tempfile.TemporaryDirectory(prefix=".glasshive-build-", dir=output.parent) as raw:
        build = Path(raw)
        env = {
            "HOME": str(build), "PATH": "/usr/bin:/bin", "LANG": "en_US.UTF-8",
            "UV_CACHE_DIR": str(build / "cache"), "UV_PYTHON_DOWNLOADS": "never",
        }
        run_glasshive_build([
            str(uv), "export", "--locked", "--no-config", "--no-dev", "--no-emit-project",
            "--no-annotate", "--no-header", "--project", str(output),
            "--python", str(python), "--output-file", str(requirements),
        ], env=env)
        dependencies = build / "site-packages"
        run_glasshive_build([
            str(uv), "pip", "sync", "--no-config", "--require-hashes", "--only-binary", ":all:",
            "--strict", "--python", str(python), "--target", str(dependencies), str(requirements),
        ], env=env)
        # Console-script shebangs name the build interpreter. Native invokes modules
        # with its bundled Python and never ships those non-relocatable wrappers.
        shutil.rmtree(dependencies / "bin", ignore_errors=True)
        copy_safe(dependencies, output / "site-packages", boundary=dependencies, source_date_epoch=source_date_epoch)
    os.utime(requirements, (source_date_epoch, source_date_epoch))
    project = tomllib.loads((output / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    return {
        "commit": pin, "version": str(project["version"]),
        "uv_lock_sha256": sha256_file(output / "uv.lock"),
        "requirements_sha256": sha256_file(requirements),
        "source_kind": "local-qa-worktree" if local_qa_worktree else "component-pin",
        "source_tree_sha256": source_digest.hexdigest(),
    }


def stage_scheduling(repo: Path, python: Path, uv: Path, output: Path, *, source_date_epoch: int, local_qa_worktree: bool) -> dict[str, str]:
    """Package the existing LibreChat-owned scheduler and its production lock."""
    source = repo / "viventium_v0_4/LibreChat"
    relative_root = "viventium/MCPs/scheduling-cortex"
    pin = selected_component_pin(repo, "LibreChat")
    actual = command_output(["git", "-C", str(source), "rev-parse", "HEAD"]).strip()
    contract = "viventium/source_of_truth/scheduled_failure_contract.v1.json"
    dirty = command_output(["git", "-C", str(source), "status", "--porcelain", "--untracked-files=all", "--", relative_root, contract, "LICENSE"])
    if actual != pin or (dirty and not local_qa_worktree):
        raise AssemblyError("Scheduling source differs from the selected LibreChat pin")
    if output.exists():
        raise AssemblyError("Scheduling staging output already exists")
    paths = [f"{relative_root}/{name}" for name in ("pyproject.toml", "uv.lock", "scheduling_cortex")]
    selection = ["--cached", "--others", "--exclude-standard"] if local_qa_worktree else []
    tracked = sorted(set(command_output(["git", "-C", str(source), "ls-files", *selection, "--", *paths]).splitlines()))
    digest = hashlib.sha256()
    for relative in tracked:
        destination = output / relative.removeprefix(relative_root + "/")
        copy_safe(source / relative, destination, boundary=source, source_date_epoch=source_date_epoch)
        digest.update(relative.encode() + b"\0" + sha256_file(destination).encode() + b"\n")
    for relative, destination in (("LICENSE", output / "LICENSE"),
                                  (contract, output / "viventium_v0_4/LibreChat" / contract)):
        copy_safe(source / relative, destination, boundary=source, source_date_epoch=source_date_epoch)
        digest.update(relative.encode() + b"\0" + sha256_file(destination).encode() + b"\n")
    if not (output / "scheduling_cortex/server.py").is_file():
        raise AssemblyError("Scheduling source is incomplete")
    # Preserve the existing installed helper component layout for scheduler
    # prompts and periphery. Only selected code/registry sources are packaged.
    support_trees = (
        (repo / "viventium_v0_4/shared", output / "shared", {".py"}),
        (repo / "viventium_v0_4/prompt-workbench/backend/prompt_workbench",
         output / "viventium_v0_4/prompt-workbench/backend/prompt_workbench", {".py"}),
        (source / "viventium/source_of_truth/prompts",
         output / "viventium_v0_4/LibreChat/viventium/source_of_truth/prompts", {".md", ".yaml", ".yml"}),
    )
    for origin, destination_root, suffixes in support_trees:
        for item in sorted(origin.rglob("*")):
            if not item.is_file() or item.suffix not in suffixes or "__pycache__" in item.parts or "tests" in item.parts:
                continue
            destination = destination_root / item.relative_to(origin)
            copy_safe(item, destination, boundary=repo, source_date_epoch=source_date_epoch)
            digest.update(item.relative_to(repo).as_posix().encode() + b"\0" + sha256_file(destination).encode() + b"\n")
    for origin, destination in (
        (repo / "LICENSE", output / "LICENSE-VIVENTIUM"),
        (repo / "scripts/viventium/prompt_registry.py", output / "scripts/viventium/prompt_registry.py"),
        *((source / f"viventium/source_of_truth/{name}", output / f"viventium_v0_4/LibreChat/viventium/source_of_truth/{name}")
          for name in ("local.viventium-agents.yaml", "local.librechat.yaml")),
    ):
        copy_safe(origin, destination, boundary=repo, source_date_epoch=source_date_epoch)
        digest.update(origin.relative_to(repo).as_posix().encode() + b"\0" + sha256_file(destination).encode() + b"\n")
    requirements = output / "requirements.txt"
    with tempfile.TemporaryDirectory(prefix=".scheduling-build-", dir=output.parent) as raw:
        build = Path(raw)
        env = {"HOME": str(build), "PATH": "/usr/bin:/bin", "LANG": "en_US.UTF-8",
               "UV_CACHE_DIR": str(build / "cache"), "UV_PYTHON_DOWNLOADS": "never"}
        run_glasshive_build([str(uv), "export", "--locked", "--no-config", "--no-dev", "--no-emit-project",
                            "--no-annotate", "--no-header", "--project", str(output), "--python", str(python),
                            "--output-file", str(requirements)], env=env)
        dependencies = build / "site-packages"
        run_glasshive_build([str(uv), "pip", "sync", "--no-config", "--require-hashes", "--only-binary", ":all:",
                            "--strict", "--python", str(python), "--target", str(dependencies), str(requirements)], env=env)
        shutil.rmtree(dependencies / "bin", ignore_errors=True)
        copy_safe(dependencies, output / "site-packages", boundary=dependencies, source_date_epoch=source_date_epoch)
    os.utime(requirements, (source_date_epoch, source_date_epoch))
    project = tomllib.loads((output / "pyproject.toml").read_text())["project"]
    return {"commit": pin, "version": str(project["version"]), "uv_lock_sha256": sha256_file(output / "uv.lock"),
            "requirements_sha256": sha256_file(requirements), "source_tree_sha256": digest.hexdigest(),
            "source_kind": "local-qa-worktree" if local_qa_worktree else "component-pin"}


def stage_native_body(
    repo: Path, archive: Path, output: Path, policy: dict[str, object], arch: str, *, source_date_epoch: int,
) -> dict[str, object]:
    """Stage a complete pinned publisher package; runtime needs no package manager."""
    architectures = policy.get("architectures")
    architecture = architectures.get(arch) if isinstance(architectures, dict) else None
    if not isinstance(architecture, dict) or not is_lower_hex(architecture.get("sha256"), 64):
        raise AssemblyError("Native body archive policy is invalid")
    if archive.is_symlink() or not archive.is_file() or output.exists():
        raise AssemblyError("Native body input or output is unsafe")

    def relative_path(value: object) -> Path:
        if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
            raise AssemblyError("Native body contains an unsafe path")
        if any(part in {"", ".", ".."} for part in value.split("/")) or PurePosixPath(value).is_absolute():
            raise AssemblyError("Native body contains an unsafe path")
        return Path(*PurePosixPath(value).parts)

    required = architecture.get("required_files")
    notices = policy.get("license_files")
    if not isinstance(required, list) or not required or not isinstance(notices, list) or not notices:
        raise AssemblyError("Native body executable and notice policy is incomplete")
    executable = relative_path(architecture.get("executable"))
    required_paths = [relative_path(value) for value in [*required, *notices, "package.json"]]
    with archive.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != architecture["sha256"]:
            raise AssemblyError("Native body archive digest differs from publisher policy")
        stream.seek(0)
        try:
            with tarfile.open(fileobj=stream, mode="r:gz") as bundle:
                seen: set[str] = set()
                total = 0
                for member in bundle:
                    parts = relative_path(member.name).parts
                    if parts[0] != "package" or len(parts) < 2 or not member.isfile():
                        raise AssemblyError("Native body archive must contain only regular package files")
                    relative = Path(*parts[1:])
                    if str(relative) in seen or len(seen) >= 4096 or not 0 <= member.size <= 512 * 1024 * 1024:
                        raise AssemblyError("Native body archive entries are invalid or excessive")
                    seen.add(str(relative)); total += member.size
                    if total > 2 * 1024 * 1024 * 1024:
                        raise AssemblyError("Native body archive exceeds its size bound")
                    source = bundle.extractfile(member)
                    if source is None:
                        raise AssemblyError("Native body archive file is unavailable")
                    target = output / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with target.open("xb") as destination:
                        shutil.copyfileobj(source, destination, 1024 * 1024)
                    target.chmod(0o755 if member.mode & 0o111 else 0o644)
                    os.utime(target, (source_date_epoch, source_date_epoch))
        except (OSError, tarfile.TarError) as error:
            raise AssemblyError("Native body archive could not be staged safely") from error
        stream.seek(0)
        if hashlib.file_digest(stream, "sha256").hexdigest() != digest:
            raise AssemblyError("Native body archive changed during staging")
    additional_notices = policy.get("additional_notices", [])
    if not isinstance(additional_notices, list):
        raise AssemblyError("Native body supplemental notice policy is invalid")
    for notice in additional_notices:
        if not isinstance(notice, dict) or not is_lower_hex(notice.get("sha256"), 64):
            raise AssemblyError("Native body supplemental notice policy is invalid")
        source = repo / relative_path(notice.get("source"))
        try:
            source.resolve(strict=True).relative_to(repo.resolve(strict=True))
            if source.is_symlink() or sha256_file(source) != notice["sha256"]:
                raise AssemblyError("Native body notice differs from its source policy")
        except (OSError, ValueError) as error:
            raise AssemblyError("Native body notice is unavailable or escapes its source") from error
        destination = output / relative_path(notice.get("destination"))
        if destination.exists():
            raise AssemblyError("Native body supplemental notice would replace package bytes")
        copy_safe(source, destination, boundary=repo, source_date_epoch=source_date_epoch)
    if any(not (output / relative).is_file() for relative in required_paths) or not os.access(output / executable, os.X_OK):
        raise AssemblyError("Native body executable, companion or notices are incomplete")
    try:
        metadata = json.loads((output / "package.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise AssemblyError("Native body package identity is invalid") from error
    if not isinstance(metadata, dict) or metadata.get("name") != architecture.get("package_name") or metadata.get("version") != architecture.get("package_version"):
        raise AssemblyError("Native body package identity differs from publisher policy")
    tree = hashlib.sha256()
    for path in sorted(output.rglob("*")):
        if path.is_file():
            tree.update(str(path.relative_to(output)).encode() + b"\0" + sha256_file(path).encode() + b"\n")
    return {
        "version": policy["version"], "archive_sha256": digest,
        "package_name": metadata["name"], "package_version": metadata["version"],
        "executable": str(executable), "executable_sha256": sha256_file(output / executable),
        "source_tree_sha256": tree.hexdigest(), "license": policy["license"], "license_files": notices,
    }


def validate_candidate_inputs(args: argparse.Namespace, components: dict[str, object]) -> None:
    versions = {name: str(components[name]["version"]) for name in ("node", "python", "mongodb")}
    expected = {
        "node": f"v{versions['node']}",
        "python": f"Python {versions['python']}",
        "mongodb": f"v{versions['mongodb']}",
    }
    commands = {
        "node": [str(args.node_root / "bin" / "node"), "--version"],
        "python": [str(args.python_root / "bin" / "python3"), "--version"],
        "mongodb": [str(args.mongodb_root / "bin" / "mongod"), "--version"],
    }
    for name, command in commands.items():
        if expected[name] not in command_output(command):
            raise AssemblyError(f"candidate {name} version does not match public policy")
        description = command_output(["/usr/bin/file", command[0]])
        if args.arch not in description:
            raise AssemblyError(f"candidate {name} architecture does not match runner")
    for app in (args.helper_app, args.bootstrap_app):
        executables = list((app / "Contents" / "MacOS").glob("*"))
        if len(executables) != 1 or args.arch not in command_output(["/usr/bin/file", str(executables[0])]):
            raise AssemblyError("candidate app architecture does not match runner")


def validate_built_librechat(root: Path) -> None:
    compliance = root / "client" / "dist-compliance"
    required = (
        root / "package.json",
        root / "package-lock.json",
        root / "api" / "server" / "index.js",
        root / "client" / "dist" / "index.html",
        compliance / "module-closure.json",
        compliance / "manifest.json",
        root / "client" / "scripts" / "collect-browser-compliance.cjs",
        root / "client" / "third_party" / "browser-compliance" / "overrides.json",
        root / "packages" / "api" / "dist",
        root / "node_modules",
        root / "scripts" / "viventium-seed-agents.js",
        root / "scripts" / "viventium-reconcile-user-defaults.js",
        root / "viventium" / "source_of_truth" / "local.viventium-agents.yaml",
        root / "viventium" / "source_of_truth" / "managed-agent-baseline-migration.json",
    )
    if any(not path.exists() for path in required):
        raise AssemblyError("built LibreChat runtime or browser compliance closure is incomplete")
    if not any((root / "node_modules").iterdir()):
        raise AssemblyError("built LibreChat production dependencies are empty")
    if (compliance / "blockers.json").exists():
        raise AssemblyError("built LibreChat browser compliance still has unresolved blockers")
    try:
        closure = json.loads((compliance / "module-closure.json").read_text(encoding="utf-8"))
        manifest = json.loads((compliance / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AssemblyError("built LibreChat browser compliance metadata is invalid") from error
    closure_paths = closure.get("packageLockPaths")
    manifest_packages = manifest.get("packages")
    if (
        closure.get("schemaVersion") != 1
        or manifest.get("schemaVersion") != 1
        or not isinstance(closure_paths, list)
        or not isinstance(manifest_packages, list)
        or closure_paths
        != [
            package.get("lockPath") if isinstance(package, dict) else None
            for package in manifest_packages
        ]
    ):
        raise AssemblyError("built LibreChat browser compliance closure and manifest disagree")


def validate_sandpack_runtime(root: Path, *, mode: str) -> str:
    index = root / "client" / "dist" / "sandpack-bundler" / "index.html"
    try:
        metadata = index.lstat()
        body = index.read_bytes()
    except OSError as error:
        raise AssemblyError("built LibreChat isolated artifact runtime is unavailable") from error
    digest = hashlib.sha256(body).hexdigest()
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise AssemblyError("built LibreChat isolated artifact runtime must be a regular file")
    if SANDPACK_ON_PREM_MARKER not in body:
        raise AssemblyError("built LibreChat isolated artifact runtime is not in on-prem mode")
    if mode == "candidate" and digest != SANDPACK_INDEX_SHA256:
        raise AssemblyError("candidate isolated artifact runtime does not match public policy")
    return digest


def macho_paths(root: Path) -> list[str]:
    # Share the compatibility verifier's detector instead of starting one host
    # process for every source, license, and dependency file in the payload.
    paths = [path.relative_to(root).as_posix() for path in sorted(root.rglob("*")) if path.is_file() and is_macho(path)]
    app = "apps/Viventium.app"
    paths = [path for path in paths if not path.startswith(f"{app}/")]
    paths.sort(key=lambda value: (-value.count("/"), value))
    paths.append(app)
    return paths


def stage_redis(archive: Path, output: Path, policy: dict, arch: str, *, source_date_epoch: int) -> dict:
    """Build the pinned upstream Redis for the target Mac, without guest build tools."""
    with archive.open("rb") as source:
        archive_bytes = source.read(64 * 1024 * 1024 + 1)
    if len(archive_bytes) > 64 * 1024 * 1024:
        raise AssemblyError("Redis source archive exceeds its size bound")
    digest = hashlib.sha256(archive_bytes).hexdigest()
    if digest != policy["source"]["sha256"]:
        raise AssemblyError("Redis source differs from publisher policy")
    if sys.platform != "darwin" or arch not in {"arm64", "x86_64"}:
        raise AssemblyError("Native Redis requires a macOS producer and supported target architecture")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".redis-build-", dir=output.parent) as raw:
        build = Path(raw)
        prefix = f"redis-{policy['version']}"
        with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:gz") as bundle:
            members = bundle.getmembers()
            if len(members) > 20000 or sum(member.size for member in members) > 100 * 1024 * 1024:
                raise AssemblyError("Redis source archive exceeds its size bound")
            for member in members:
                parts = PurePosixPath(member.name).parts
                if not parts or parts[0] != prefix or ".." in parts or not (member.isfile() or member.isdir()):
                    raise AssemblyError("Redis source archive contains an unsafe entry")
            bundle.extractall(build, members=members, filter="data")
        source_root = build / prefix
        environment = {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "LANG": "C",
                       "MACOSX_DEPLOYMENT_TARGET": "15.0", "SOURCE_DATE_EPOCH": str(source_date_epoch)}
        command = ["/usr/bin/make", "-j", "6", "MALLOC=libc", "BUILD_TLS=no",
                   f"CC=/usr/bin/clang -arch {arch} -mmacosx-version-min=15.0", "redis-server", "redis-cli"]
        result = subprocess.run(command, cwd=source_root, env=environment, capture_output=True, timeout=600)
        if result.returncode != 0:
            raise AssemblyError("Pinned Redis source did not build for the selected Mac architecture")
        for name in ("redis-server", "redis-cli"):
            executable = source_root / "src" / name
            subprocess.run(["/usr/bin/strip", "-S", str(executable)], check=True, capture_output=True)
            copy_safe(executable, output / "bin" / name, boundary=source_root, source_date_epoch=source_date_epoch)
        for relative in ("COPYING", "deps/hiredis/COPYING", "deps/lua/COPYRIGHT", "deps/linenoise/linenoise.h",
                         "deps/hdr_histogram/LICENSE.txt", "deps/hdr_histogram/COPYING.txt", "deps/fpconv/LICENSE.txt"):
            copy_safe(source_root / relative, output / "licenses" / relative, boundary=source_root, source_date_epoch=source_date_epoch)
    return {"version": policy["version"], "license": policy["license"], "source": policy["source"],
            "arch": arch, "deployment_target": "15.0", "build": "upstream-make-libc-no-tls",
            "executable_sha256": hashlib.sha256((output / "bin/redis-server").read_bytes()).hexdigest()}


def stage_sequential_thinking(repo: Path, node: Path, output: Path, policy: dict, *, source_date_epoch: int) -> dict:
    source = repo / "release/native-payload/sequential-thinking"
    lock = json.loads((source / "package-lock.json").read_text())
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".sequential-build-", dir=output.parent) as raw:
        build = Path(raw)
        for name in ("package.json", "package-lock.json"):
            shutil.copyfile(source / name, build / name)
        environment = {"PATH": f"{node / 'bin'}:/usr/bin:/bin", "HOME": str(build / "home"),
                       "npm_config_cache": str(build / "cache"), "LANG": "C"}
        result = subprocess.run([str(node / "bin/node"), str(node / "lib/node_modules/npm/bin/npm-cli.js"),
                                 "ci", "--omit=dev", "--ignore-scripts", "--no-audit", "--no-fund"],
                                cwd=build, env=environment, capture_output=True, timeout=180)
        if result.returncode != 0:
            raise AssemblyError("Locked Sequential Thinking dependency installation failed")
        for name in ("package.json", "package-lock.json", "node_modules"):
            copy_safe(build / name, output / name, boundary=build, source_date_epoch=source_date_epoch)
    relative = "node_modules/@modelcontextprotocol/server-sequential-thinking"
    if not (output / relative / "dist/index.js").is_file():
        raise AssemblyError("Bundled Sequential Thinking entrypoint is missing")
    notice = policy["notice"]
    notice_path = repo / notice["source"]
    if hashlib.sha256(notice_path.read_bytes()).hexdigest() != notice["sha256"]:
        raise AssemblyError("Sequential Thinking publisher notice differs from exact source policy")
    copy_safe(notice_path, output / relative / notice["destination"], boundary=repo, source_date_epoch=source_date_epoch)
    return {"version": lock["packages"][relative]["version"],
            "lock_sha256": hashlib.sha256((source / "package-lock.json").read_bytes()).hexdigest(),
            "upstream_revision": policy["upstream_revision"], "notice_sha256": notice["sha256"],
            "entrypoint": f"{relative}/dist/index.js"}


def stage_bootstrap_scripts(repo: Path, bootstrap: Path, *, source_date_epoch: int) -> None:
    """Bind installer modules to the same source selection as the payload verifier."""
    for name in ("native_payload.py", "install_native_payload.py"):
        copy_safe(repo / "scripts/viventium" / name,
                  bootstrap / "Contents/Resources/scripts" / name,
                  boundary=repo, source_date_epoch=source_date_epoch)


def assemble(args: argparse.Namespace) -> dict[str, object]:
    if getattr(args, "glasshive_local_qa_worktree", False) and args.mode != "local-qa":
        raise AssemblyError("GlassHive worktree input is restricted to local QA")
    repo = ensure_real_directory(args.repo_root, "repository root")
    librechat = ensure_real_directory(args.librechat_root, "LibreChat root")
    node = ensure_real_directory(args.node_root, "Node root")
    python = ensure_real_directory(args.python_root, "Python root")
    mongodb = ensure_real_directory(args.mongodb_root, "MongoDB root")
    helper = ensure_real_directory(args.helper_app, "helper app")
    bootstrap = ensure_real_directory(args.bootstrap_app, "bootstrap app")
    compiled = ensure_real_directory(args.compiled_config_root, "compiled config root")
    for name in ("librechat.yaml", "prompt-bundle.json", "native-runtime.env", "viventium-agents.yaml"):
        if not (compiled / name).is_file():
            raise AssemblyError("compiler-produced canonical config is incomplete")
    if not (getattr(args, "codex_archive", None) or getattr(args, "claude_code_archive", None)):
        validate_native_compiled_defaults(compiled)
    output = args.output_dir.resolve()
    if output.exists():
        raise AssemblyError("output directory already exists")
    if not args.source_commit or len(args.source_commit) != 40 or any(c not in "0123456789abcdef" for c in args.source_commit):
        raise AssemblyError("source commit must be a lowercase full SHA-1")
    if args.source_date_epoch < 315532800:
        raise AssemblyError("source date epoch is outside the supported range")
    validate_built_librechat(librechat)
    try:
        load_native_runtime_env(compiled / "native-runtime.env")
    except NativeRuntimeError as error:
        raise AssemblyError(str(error)) from error
    components = read_components(args.components)
    component_manifest = release_component_manifest(components, args.arch, repo)
    if args.mode == "candidate":
        if not (repo / "release" / "native-payload" / "mongodb-redistribution-approved").is_file():
            raise AssemblyError("MongoDB redistribution approval is required for a distributable candidate")
        validate_candidate_inputs(args, components)
    sandpack_index_sha256 = validate_sandpack_runtime(librechat, mode=args.mode)

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".native-assembly-", dir=output.parent) as temporary_raw:
        candidate = Path(temporary_raw) / "candidate"
        payload = candidate / "payload"
        for component, source in (
            ("node", node),
            ("python", python),
            ("mongodb", mongodb),
        ):
            try:
                stage_component(
                    component,
                    source,
                    payload / "runtime" / component,
                    source_date_epoch=args.source_date_epoch,
                )
            except StagingError as error:
                raise AssemblyError(str(error)) from error

        if args.glasshive_root is not None:
            if args.uv is None:
                raise AssemblyError("GlassHive staging requires an explicit uv build tool")
            component_manifest["glasshive"] = stage_glasshive(
                repo, args.glasshive_root, python / "bin" / "python3", args.uv,
                payload / "runtime" / "glasshive", source_date_epoch=args.source_date_epoch,
                local_qa_worktree=getattr(args, "glasshive_local_qa_worktree", False),
            )

        body_archives = {
            "codex-cli": getattr(args, "codex_archive", None),
            "claude-code": getattr(args, "claude_code_archive", None),
        }
        packaged_bodies = {}
        if any(body_archives.values()):
            if args.glasshive_root is None or not all(body_archives.values()):
                raise AssemblyError("Native harness requires GlassHive and both configured provider body packages")
            policies = components.get("native_bodies")
            if not isinstance(policies, dict) or set(policies) != set(body_archives):
                raise AssemblyError("Native provider body policy is incomplete")
            for profile, archive in body_archives.items():
                packaged_bodies[profile] = stage_native_body(
                    repo, archive, payload / "runtime/native-bodies" / profile, policies[profile], args.arch,
                    source_date_epoch=args.source_date_epoch,
                )
            component_manifest["glasshive"]["native_bodies"] = packaged_bodies
        validate_native_compiled_defaults(compiled, packaged_native_bodies=bool(packaged_bodies))
        native_config = yaml.safe_load((compiled / "config.yaml").read_text())
        native_servers = (yaml.safe_load((compiled / "librechat.yaml").read_text()) or {}).get("mcpServers", {})
        if "sequential-thinking" in native_servers:
            component_manifest["sequential-thinking"] = stage_sequential_thinking(
                repo, node, payload / "runtime/sequential-thinking", components["sequential-thinking"],
                source_date_epoch=args.source_date_epoch)
        native_env = load_native_runtime_env(compiled / "native-runtime.env")
        if native_env.get("VIVENTIUM_PARALLEL_WORK_AVAILABLE") == "true":
            if getattr(args, "redis_archive", None) is None:
                raise AssemblyError("Native parallel work requires the pinned Redis source archive")
            component_manifest["redis"] = stage_redis(
                args.redis_archive, payload / "runtime/redis", components["redis"], args.arch,
                source_date_epoch=args.source_date_epoch)
        if native_config.get("integrations", {}).get("scheduling_cortex", {}).get("enabled"):
            if args.uv is None:
                raise AssemblyError("Scheduling staging requires an explicit uv build tool")
            component_manifest["scheduling"] = stage_scheduling(
                repo, python / "bin/python3", args.uv, payload / "runtime/scheduling",
                source_date_epoch=args.source_date_epoch, local_qa_worktree=args.mode == "local-qa")

        copies = (
            (librechat, payload / "runtime" / "librechat"),
            (helper, payload / "apps" / "Viventium.app"),
            (bootstrap, candidate / "bootstrap" / "ViventiumBootstrap.app"),
        )
        for source, destination in copies:
            copy_safe(
                source,
                destination,
                boundary=source,
                source_date_epoch=args.source_date_epoch,
                customized_librechat=source == librechat,
            )

        stage_bootstrap_scripts(repo, candidate / "bootstrap/ViventiumBootstrap.app",
                                source_date_epoch=args.source_date_epoch)

        bootstrap_python = (
            candidate
            / "bootstrap"
            / "ViventiumBootstrap.app"
            / "Contents"
            / "Resources"
            / "runtime"
            / "python"
        )
        if bootstrap_python.exists() or bootstrap_python.is_symlink():
            if bootstrap_python.is_symlink() or not bootstrap_python.is_dir():
                raise AssemblyError("bootstrap embedded Python path is unsafe")
            shutil.rmtree(bootstrap_python)
        try:
            stage_component(
                "python",
                python,
                bootstrap_python,
                source_date_epoch=args.source_date_epoch,
            )
        except StagingError as error:
            raise AssemblyError(str(error)) from error

        try:
            payload_python_manifest = build_component_manifest(
                payload / "runtime" / "python",
                name="python",
                component=component_manifest["python"],
            )
            bootstrap_python_manifest = build_component_manifest(
                bootstrap_python,
                name="python",
                component=component_manifest["python"],
            )
        except ComponentManifestError as error:
            raise AssemblyError(str(error)) from error
        if payload_python_manifest != bootstrap_python_manifest:
            raise AssemblyError("payload and Bootstrap Python component trees disagree")
        python_manifest_content = (
            json.dumps(payload_python_manifest, sort_keys=True, separators=(",", ":"))
            + "\n"
        )
        write_file(
            payload / "release-metadata" / "python-runtime-manifest.json",
            python_manifest_content,
            0o644,
            args.source_date_epoch,
        )
        write_file(
            candidate
            / "bootstrap"
            / "ViventiumBootstrap.app"
            / "Contents"
            / "Resources"
            / "python-runtime-manifest.json",
            python_manifest_content,
            0o644,
            args.source_date_epoch,
        )

        copy_safe(repo / "templates/life-v0.01", payload / "templates/life-v0.01",
                  boundary=repo, source_date_epoch=args.source_date_epoch)
        script_sources = {
            repo / "viventium_v0_4" / "shared" / "compiled_prompt_contract.py": payload / "runtime" / "shared" / "compiled_prompt_contract.py",
            repo / "scripts" / "viventium" / "life_bootstrap.py": payload / "runtime" / "scripts" / "life_bootstrap.py",
            repo / "scripts" / "viventium" / "life_setup.py": payload / "runtime" / "scripts" / "life_setup.py",
            repo / "scripts" / "viventium" / "config_settings.py": payload / "runtime" / "scripts" / "config_settings.py",
            repo / "scripts" / "viventium" / "native_payload.py": payload / "runtime" / "scripts" / "native_payload.py",
            repo / "scripts" / "viventium" / "native_runtime.py": payload / "runtime" / "scripts" / "native_runtime.py",
            repo / "scripts" / "viventium" / "native_process_guard.py": payload / "runtime" / "scripts" / "native_process_guard.py",
            repo / "scripts" / "viventium" / "continuity_bundle.py": payload / "runtime" / "scripts" / "continuity_bundle.py",
            repo / "scripts" / "viventium" / "continuity_mongo.cjs": payload / "runtime" / "scripts" / "continuity_mongo.cjs",
            repo / "scripts" / "viventium" / "native_first_admin_recovery.js": payload / "runtime" / "scripts" / "native_first_admin_recovery.js",
            repo / "scripts" / "viventium" / "native_mongodb_replica.js": payload / "runtime" / "scripts" / "native_mongodb_replica.js",
            repo / "scripts" / "viventium" / "native_scheduling_server.py": payload / "runtime" / "scripts" / "native_scheduling_server.py",
            repo / "scripts" / "viventium" / "native_verify_agent.js": payload / "runtime" / "scripts" / "native_verify_agent.js",
            repo / "scripts" / "viventium" / "native_runtime_proxy.js": payload / "runtime" / "proxy.js",
            repo / "scripts" / "viventium" / "native_cli.sh": payload / "bin" / "viventium",
        }
        for source, destination in script_sources.items():
            copy_safe(source, destination, boundary=repo, source_date_epoch=args.source_date_epoch)
        entrypoint = repo / "scripts" / "viventium" / "native_entrypoint.sh"
        for command in (
            "install",
            "start",
            "stop",
            "registration-close",
            "status",
            "health",
            "doctor",
            "configure",
            "password-reset-link",
            "provider-auth",
            "upgrade",
            "snapshot",
            "restore",
            "uninstall",
            "schema",
            "parallel-work-identity",
        ):
            destination = payload / "bin" / f"viventium-native-{command}"
            copy_safe(
                entrypoint,
                destination,
                boundary=repo,
                source_date_epoch=args.source_date_epoch,
            )
            destination.chmod(0o755)

        default_config = compiled / "config.yaml"
        copy_safe(
            default_config,
            payload / "runtime" / "defaults" / "config.yaml",
            boundary=compiled,
            source_date_epoch=args.source_date_epoch,
        )
        for name in ("librechat.yaml", "prompt-bundle.json", "native-runtime.env", "viventium-agents.yaml"):
            copy_safe(
                compiled / name,
                payload / "runtime" / "defaults" / name,
                boundary=compiled,
                source_date_epoch=args.source_date_epoch,
            )
        # Signed helper inputs already own this resource. Preserve their bytes;
        # an unsigned CI envelope receives the same canonical marker before signing.
        assembled_helper = payload / "apps" / "Viventium.app"
        marker = assembled_helper / "Contents/Resources/viventium-owner.json"
        if marker.exists():
            if helper_owner(assembled_helper) is None:
                raise AssemblyError("Helper ownership marker is invalid")
        else:
            if (assembled_helper / "Contents/_CodeSignature/CodeResources").exists():
                raise AssemblyError("Signed helper is missing its ownership marker")
            write_file(marker, owner_marker_bytes("ai.viventium.helper").decode("utf-8"),
                       0o644, args.source_date_epoch)

        metadata = {
            "arch": args.arch,
            "components": component_manifest,
            "mode": args.mode,
            "data_schema": {
                "minimum": args.data_schema_minimum,
                "maximum": args.data_schema_maximum,
                "target": args.data_schema_target,
            },
            "source_commit": args.source_commit,
            "source_date_epoch": args.source_date_epoch,
            "sandpack_index_sha256": sandpack_index_sha256,
        }
        write_file(
            payload / "release-metadata" / "build.json",
            json.dumps(metadata, sort_keys=True, separators=(",", ":")) + "\n",
            0o644,
            args.source_date_epoch,
        )
        write_file(
            payload / "release-metadata" / "apple-code-paths.txt",
            "\n".join(macho_paths(payload)) + "\n",
            0o644,
            args.source_date_epoch,
        )
        write_file(
            payload / "release-metadata" / "apple-staple-paths.txt",
            "apps/Viventium.app\n",
            0o644,
            args.source_date_epoch,
        )
        for directory in sorted(candidate.rglob("*"), reverse=True):
            if directory.is_dir():
                directory.chmod(0o755)
                os.utime(directory, (args.source_date_epoch, args.source_date_epoch), follow_symlinks=False)
        os.replace(candidate, output)

    files = [path for path in output.rglob("*") if path.is_file()]
    return {
        "arch": args.arch,
        "bootstrap_files": sum(1 for path in files if "bootstrap" in path.parts),
        "payload_files": sum(1 for path in files if "payload" in path.parts),
        "output": str(output),
    }


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    for name in ("repo-root", "librechat-root", "node-root", "python-root", "mongodb-root", "helper-app", "bootstrap-app", "compiled-config-root", "output-dir"):
        value.add_argument(f"--{name}", type=Path, required=True)
    value.add_argument(
        "--components",
        type=Path,
        default=Path("release/native-payload/components.json"),
    )
    value.add_argument("--arch", choices=("arm64", "x86_64"), required=True)
    value.add_argument("--glasshive-root", type=Path)
    value.add_argument("--redis-archive", type=Path, help="Pinned upstream Redis source for durable Native parallel work")
    value.add_argument("--codex-archive", type=Path, help="Exact publisher package pinned by Native component policy")
    value.add_argument("--claude-code-archive", type=Path, help="Exact publisher package pinned by Native component policy")
    value.add_argument("--glasshive-local-qa-worktree", action="store_true", help="Include reviewed uncommitted GlassHive source only in a local QA payload")
    value.add_argument("--uv", type=Path)
    value.add_argument("--source-commit", required=True)
    value.add_argument("--source-date-epoch", type=int, required=True)
    value.add_argument("--mode", choices=("local-qa", "candidate"), required=True)
    value.add_argument("--data-schema-minimum", type=int, default=1)
    value.add_argument("--data-schema-maximum", type=int, default=1)
    value.add_argument("--data-schema-target", type=int, default=1)
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if not (
            1 <= args.data_schema_minimum
            <= args.data_schema_target
            <= args.data_schema_maximum
        ):
            raise AssemblyError("Native data schema range/target is invalid")
        result = assemble(args)
    except (AssemblyError, OSError, KeyError, TypeError, ValueError) as error:
        print(f"Native payload assembly failed: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

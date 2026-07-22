#!/usr/bin/env python3
"""Assemble an exact relocatable macOS Native payload candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from stage_native_component import StagingError, stage_component  # noqa: E402
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
    ".yarn",
    "__pycache__",
    "coverage",
    "e2e",
    "playwright-report",
    "test-results",
}
SECRET_NAMES = {".env", "id_rsa", "id_ed25519"}
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


def copy_safe(
    source: Path,
    destination: Path,
    *,
    boundary: Path,
    source_date_epoch: int,
    active: tuple[Path, ...] = (),
) -> None:
    if should_exclude(source):
        return
    if source.name in SECRET_NAMES:
        raise AssemblyError(f"secret-shaped input is forbidden: {source.name}")
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


def is_lower_hex(value: object, length: int) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and all(character in "0123456789abcdef" for character in value)
    )


def release_component_manifest(
    components: dict[str, object], arch: str
) -> dict[str, dict[str, str]]:
    librechat = components.get("librechat")
    if not isinstance(librechat, dict) or not is_lower_hex(librechat.get("commit"), 40):
        raise AssemblyError("Native LibreChat component commit is invalid")

    manifest: dict[str, dict[str, str]] = {
        "librechat": {"commit": str(librechat["commit"])}
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
    paths: list[str] = []
    file_tool = Path("/usr/bin/file")
    if file_tool.is_file():
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            completed = subprocess.run(
                [str(file_tool), "-b", str(path)], check=False, capture_output=True, text=True
            )
            if completed.returncode == 0 and "Mach-O" in completed.stdout:
                paths.append(path.relative_to(root).as_posix())
    app = "apps/Viventium.app"
    paths = [path for path in paths if not path.startswith(f"{app}/")]
    paths.sort(key=lambda value: (-value.count("/"), value))
    paths.append(app)
    return paths


def assemble(args: argparse.Namespace) -> dict[str, object]:
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
    output = args.output_dir.resolve()
    if output.exists():
        raise AssemblyError("output directory already exists")
    if not args.source_commit or len(args.source_commit) != 40 or any(c not in "0123456789abcdef" for c in args.source_commit):
        raise AssemblyError("source commit must be a lowercase full SHA-1")
    if args.source_date_epoch < 315532800:
        raise AssemblyError("source date epoch is outside the supported range")
    validate_built_librechat(librechat)
    components = read_components(args.components)
    component_manifest = release_component_manifest(components, args.arch)
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
            )

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

        script_sources = {
            repo / "scripts" / "viventium" / "native_runtime.py": payload / "runtime" / "scripts" / "native_runtime.py",
            repo / "scripts" / "viventium" / "native_process_guard.py": payload / "runtime" / "scripts" / "native_process_guard.py",
            repo / "scripts" / "viventium" / "continuity_bundle.py": payload / "runtime" / "scripts" / "continuity_bundle.py",
            repo / "scripts" / "viventium" / "continuity_mongo.cjs": payload / "runtime" / "scripts" / "continuity_mongo.cjs",
            repo / "scripts" / "viventium" / "native_first_admin_recovery.js": payload / "runtime" / "scripts" / "native_first_admin_recovery.js",
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
            "upgrade",
            "snapshot",
            "restore",
            "uninstall",
            "schema",
        ):
            destination = payload / "bin" / f"viventium-native-{command}"
            copy_safe(
                entrypoint,
                destination,
                boundary=repo,
                source_date_epoch=args.source_date_epoch,
            )
            destination.chmod(0o755)

        default_config = repo / "config.minimal.example.yaml"
        copy_safe(
            default_config,
            payload / "runtime" / "defaults" / "config.yaml",
            boundary=repo,
            source_date_epoch=args.source_date_epoch,
        )
        for name in ("librechat.yaml", "prompt-bundle.json", "native-runtime.env", "viventium-agents.yaml"):
            copy_safe(
                compiled / name,
                payload / "runtime" / "defaults" / name,
                boundary=compiled,
                source_date_epoch=args.source_date_epoch,
            )
        write_file(
            payload / "apps" / "Viventium.app" / "Contents" / "Resources" / "viventium-owner.json",
            json.dumps(
                {
                    "product": "ai.viventium.helper",
                    "schema_version": 1,
                    "source_commit": args.source_commit,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
            0o644,
            args.source_date_epoch,
        )

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

#!/usr/bin/env python3
"""Verify selected Native components and refresh their measured bytes after signing."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tomllib
from pathlib import Path

import yaml

from assemble_native_payload import release_component_manifest, selected_component_pin
from generate_native_compliance import json_object, safe_owned_file, sha256_file, atomic_write as write_atomic
from native_runtime import load_native_runtime_env
from verify_native_component_manifest import build_manifest, verify


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def verify_component_policy(payload: Path, repo: Path, arch: str, *, signed_bytes: bool = True) -> dict:
    metadata = json_object(payload / "release-metadata/build.json", "Native build metadata")
    policy = json_object(repo / "release/native-payload/components.json", "Native component policy")
    components = metadata.get("components")
    require(metadata.get("arch") == arch and metadata.get("mode") == "candidate",
            "Native candidate architecture or mode differs from release policy")
    require(isinstance(components, dict), "Native component metadata is invalid")
    base = release_component_manifest(policy, arch, repo)
    require(all(components.get(name) == record for name, record in base.items()),
            "Native base components differ from architecture-specific policy")
    optional_roots = {"glasshive": "glasshive", "redis": "redis", "scheduling": "scheduling",
                      "sequential-thinking": "sequential-thinking"}
    require(not set(components) - set(base) - set(optional_roots), "Native component metadata has an unknown component")
    for name, relative in optional_roots.items():
        require((name in components) == (payload / "runtime" / relative).is_dir(),
                f"Native {name} physical inventory differs from metadata")

    defaults = payload / "runtime/defaults"
    config = yaml.safe_load(safe_owned_file(defaults, "config.yaml", "Native defaults").read_text()) or {}
    chat = yaml.safe_load(safe_owned_file(defaults, "librechat.yaml", "Native defaults").read_text()) or {}
    environment = load_native_runtime_env(defaults / "native-runtime.env")
    integrations = config.get("integrations", {})
    glasshive = integrations.get("glasshive", {})
    harness_required = any((glasshive.get("enabled"), glasshive.get("provider", {}).get("enabled"),
                            glasshive.get("host_worker", {}).get("enabled")))
    required = {"glasshive"} if harness_required else set()
    if integrations.get("scheduling_cortex", {}).get("enabled"):
        required.add("scheduling")
    if environment.get("VIVENTIUM_PARALLEL_WORK_AVAILABLE") == "true":
        required.add("redis")
    if "sequential-thinking" in chat.get("mcpServers", {}):
        required.add("sequential-thinking")
    require(required <= set(components), "Native defaults advertise a missing packaged component")

    for name, owner in (("glasshive", "GlassHive"), ("scheduling", "LibreChat")):
        if name not in components:
            continue
        record = components[name]
        root = payload / "runtime" / name
        project = tomllib.loads(safe_owned_file(root, "pyproject.toml", name).read_text())["project"]
        require(record.get("commit") == selected_component_pin(repo, owner)
                and record.get("source_kind") == "component-pin"
                and record.get("version") == project["version"], f"Native {name} source selection differs from policy")
        for key, relative in (("uv_lock_sha256", "uv.lock"), ("requirements_sha256", "requirements.txt")):
            require(record.get(key) == sha256_file(safe_owned_file(root, relative, name)),
                    f"Native {name} locked dependencies differ from metadata")

    bodies = components.get("glasshive", {}).get("native_bodies", {})
    body_root = payload / "runtime/native-bodies"
    require(not harness_required or bool(bodies), "Native harness provider bodies are missing")
    require(bool(bodies) == body_root.is_dir(), "Native provider body metadata differs from physical inventory")
    if bodies:
        require(set(bodies) == set(policy["native_bodies"]) == {path.name for path in body_root.iterdir()},
                "Native provider body inventory differs from selected policy")
        for name, body in bodies.items():
            selected = policy["native_bodies"][name]
            binary = selected["architectures"][arch]
            expected = {"version": selected["version"], "archive_sha256": binary["sha256"],
                        "package_name": binary["package_name"], "package_version": binary["package_version"],
                        "executable": binary["executable"], "license": selected["license"],
                        "license_files": selected["license_files"]}
            require(all(body.get(key) == value for key, value in expected.items()),
                    f"Native {name} publisher selection differs from policy")
            root = body_root / name
            package = json_object(safe_owned_file(root, "package.json", name), name)
            require(package.get("name") == binary["package_name"] and package.get("version") == binary["package_version"],
                    f"Native {name} package identity differs from policy")
            for relative in [*binary["required_files"], *selected["license_files"]]:
                safe_owned_file(root, relative, name)
            if signed_bytes:
                require(body.get("executable_sha256") == sha256_file(safe_owned_file(root, binary["executable"], name)),
                        f"Native {name} executable inventory is stale")

    if "redis" in components:
        redis = components["redis"]
        require(all(redis.get(key) == policy["redis"][key] for key in ("version", "license", "source"))
                and redis.get("arch") == arch, "Native Redis publisher selection differs from policy")
        if signed_bytes:
            require(redis.get("executable_sha256") == sha256_file(safe_owned_file(payload, "runtime/redis/bin/redis-server", "Redis")),
                    "Native Redis executable inventory is stale")
    if "sequential-thinking" in components:
        sequential = components["sequential-thinking"]
        selected = policy["sequential-thinking"]
        root = payload / "runtime/sequential-thinking"
        expected_lock = sha256_file(repo / "release/native-payload/sequential-thinking/package-lock.json")
        require(sequential.get("lock_sha256") == expected_lock == sha256_file(safe_owned_file(root, "package-lock.json", "Sequential Thinking"))
                and sequential.get("upstream_revision") == selected["upstream_revision"]
                and sequential.get("notice_sha256") == selected["notice"]["sha256"],
                "Native Sequential Thinking source selection differs from policy")
        safe_owned_file(root, sequential.get("entrypoint"), "Sequential Thinking")
    return metadata


def refresh_signed_metadata(payload: Path, bootstrap: Path, repo: Path, arch: str) -> None:
    """Keep publisher/source identities; remeasure only the signed runtime outputs."""
    metadata = verify_component_policy(payload, repo, arch, signed_bytes=False)
    components = metadata["components"]
    for name, body in components.get("glasshive", {}).get("native_bodies", {}).items():
        body["executable_sha256"] = sha256_file(safe_owned_file(payload / "runtime/native-bodies" / name,
                                                              body["executable"], name))
    if "redis" in components:
        components["redis"]["executable_sha256"] = sha256_file(safe_owned_file(payload, "runtime/redis/bin/redis-server", "Redis"))
    python_root = payload / "runtime/python"
    bootstrap_python = bootstrap / "Contents/Resources/runtime/python"
    require(python_root.is_dir() and not python_root.is_symlink()
            and bootstrap_python.is_dir() and not bootstrap_python.is_symlink(),
            "Native Python signing inputs are unsafe")
    # Sign once, then copy the exact Python bytes into Bootstrap before its outer seal.
    # Separate signing timestamps would otherwise produce two different runtime trees.
    manifest = build_manifest(python_root, name="python", component=components["python"])
    build_manifest(bootstrap_python, name="python", component=components["python"])
    shutil.copytree(python_root, bootstrap_python, dirs_exist_ok=True)
    require(manifest == build_manifest(bootstrap_python, name="python", component=components["python"]),
            "Native payload and Bootstrap Python differ after signing")
    serialized = json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n"
    for destination in (payload / "release-metadata/python-runtime-manifest.json",
                        bootstrap / "Contents/Resources/python-runtime-manifest.json"):
        write_atomic(destination, serialized)
    write_atomic(payload / "release-metadata/build.json", json.dumps(metadata, sort_keys=True, separators=(",", ":")) + "\n")
    verify(python_root, payload / "release-metadata/python-runtime-manifest.json", expected_name="python")
    verify(bootstrap_python, bootstrap / "Contents/Resources/python-runtime-manifest.json", expected_name="python")
    verify_component_policy(payload, repo, arch)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--payload-root", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--arch", choices=("arm64", "x86_64"), required=True)
    parser.add_argument("--bootstrap-app", type=Path)
    parser.add_argument("--refresh-after-signing", action="store_true")
    args = parser.parse_args()
    try:
        if args.refresh_after_signing:
            require(args.bootstrap_app is not None, "Bootstrap is required to refresh signed inventories")
            refresh_signed_metadata(args.payload_root, args.bootstrap_app, args.repo_root, args.arch)
        else:
            verify_component_policy(args.payload_root, args.repo_root, args.arch)
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, yaml.YAMLError) as error:
        print(f"Native release metadata verification failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

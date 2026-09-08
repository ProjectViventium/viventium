from __future__ import annotations

import copy
import importlib.util
import json
import os
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def put(path: Path, contents: str | bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(contents if isinstance(contents, bytes) else contents.encode())
    return path


def fixture(tmp_path, monkeypatch, arch="arm64"):
    monkeypatch.syspath_prepend(str(ROOT / "scripts/viventium"))
    spec = importlib.util.spec_from_file_location("native_release_metadata", ROOT / "scripts/viventium/verify_native_release_metadata.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    from native_runtime import NATIVE_FIXED_ENV
    repo, payload, bootstrap = (tmp_path / name for name in ("repo", "payload", "Bootstrap.app"))
    policy = json.loads((ROOT / "release/native-payload/components.json").read_text())
    put(repo / "release/native-payload/components.json", json.dumps(policy))
    put(repo / "components.lock.json", json.dumps({"components": [{"name": "LibreChat", "ref": "a" * 40}, {"name": "GlassHive", "ref": "b" * 40}]}))
    put(payload / "runtime/defaults/config.yaml", "integrations:\n  glasshive:\n    enabled: true\n  scheduling_cortex:\n    enabled: true\n")
    put(payload / "runtime/defaults/librechat.yaml", "mcpServers:\n  sequential-thinking: {}\n")
    put(payload / "runtime/defaults/native-runtime.env", "".join(f"{key}={value}\n" for key, value in {**NATIVE_FIXED_ENV, "VIVENTIUM_PARALLEL_WORK_AVAILABLE": "true"}.items()))
    components = module.release_component_manifest(policy, arch, repo)
    for name, commit in (("glasshive", "b" * 40), ("scheduling", "a" * 40)):
        root = payload / "runtime" / name
        put(root / "pyproject.toml", '[project]\nversion = "1.0.0"\n')
        lock = put(root / "uv.lock", "synthetic pinned lock\n")
        requirements = put(root / "requirements.txt", "synthetic export\n")
        components[name] = {"commit": commit, "version": "1.0.0", "source_kind": "component-pin",
                            "uv_lock_sha256": module.sha256_file(lock), "requirements_sha256": module.sha256_file(requirements)}
    bodies = {}
    for name, selected in policy["native_bodies"].items():
        binary = selected["architectures"][arch]
        root = payload / "runtime/native-bodies" / name
        for relative in [*binary["required_files"], *selected["license_files"]]:
            put(root / relative, f"synthetic {name} {relative}\n")
        put(root / "package.json", json.dumps({"name": binary["package_name"], "version": binary["package_version"]}))
        bodies[name] = {"version": selected["version"], "archive_sha256": binary["sha256"],
                        "package_name": binary["package_name"], "package_version": binary["package_version"],
                        "executable": binary["executable"], "license": selected["license"], "license_files": selected["license_files"],
                        "source_tree_sha256": "c" * 64,
                        "executable_sha256": module.sha256_file(root / binary["executable"])}
    components["glasshive"]["native_bodies"] = bodies
    redis = put(payload / "runtime/redis/bin/redis-server", "synthetic Redis before signing\n")
    components["redis"] = {**{key: policy["redis"][key] for key in ("version", "license", "source")},
                            "arch": arch, "executable_sha256": module.sha256_file(redis)}
    source_lock = ROOT / "release/native-payload/sequential-thinking/package-lock.json"
    put(repo / "release/native-payload/sequential-thinking/package-lock.json", source_lock.read_bytes())
    put(payload / "runtime/sequential-thinking/package-lock.json", source_lock.read_bytes())
    entrypoint = "node_modules/@modelcontextprotocol/server-sequential-thinking/dist/index.js"
    put(payload / "runtime/sequential-thinking" / entrypoint, "synthetic server\n")
    components["sequential-thinking"] = {"entrypoint": entrypoint, "lock_sha256": module.sha256_file(source_lock),
        "upstream_revision": policy["sequential-thinking"]["upstream_revision"],
        "notice_sha256": policy["sequential-thinking"]["notice"]["sha256"]}
    put(payload / "runtime/python/bin/python3", "synthetic Python before signing\n")
    shutil.copytree(payload / "runtime/python", bootstrap / "Contents/Resources/runtime/python")
    metadata = {"arch": arch, "mode": "candidate", "source_commit": "d" * 40, "components": components}
    put(payload / "release-metadata/build.json", json.dumps(metadata))
    manifest = module.build_manifest(payload / "runtime/python", name="python", component=components["python"])
    for path in (payload / "release-metadata/python-runtime-manifest.json", bootstrap / "Contents/Resources/python-runtime-manifest.json"):
        put(path, json.dumps(manifest))
    return module, repo, payload, bootstrap, metadata


@pytest.mark.parametrize("arch", ["arm64", "x86_64"])
def test_full_native_candidate_is_verified_against_base_and_selected_extensions(tmp_path, monkeypatch, arch):
    module, repo, payload, _, metadata = fixture(tmp_path, monkeypatch, arch)
    policy = json.loads((repo / "release/native-payload/components.json").read_text())
    assert metadata["components"] != module.release_component_manifest(policy, arch, repo)
    assert module.verify_component_policy(payload, repo, arch) == metadata


@pytest.mark.parametrize("failure", ["base-architecture", "source-pin", "source-worktree", "missing-redis", "provider-archive", "provider-companion", "unknown-component"])
def test_native_release_rejects_changed_selection_or_incomplete_payload(tmp_path, monkeypatch, failure):
    module, repo, payload, _, metadata = fixture(tmp_path, monkeypatch)
    components = metadata["components"]
    if failure == "base-architecture": components["node"]["archive_sha256"] = "0" * 64
    elif failure == "source-pin": components["glasshive"]["commit"] = "0" * 40
    elif failure == "source-worktree": components["scheduling"]["source_kind"] = "local-qa-worktree"
    elif failure == "missing-redis":
        del components["redis"]
        shutil.rmtree(payload / "runtime/redis")
    elif failure == "provider-archive": components["glasshive"]["native_bodies"]["codex-cli"]["archive_sha256"] = "0" * 64
    elif failure == "provider-companion":
        root = payload / "runtime/native-bodies/codex-cli"
        companion = next(root.rglob("codex-code-mode-host"))
        companion.unlink()
    else: components["unselected-runtime"] = {}
    put(payload / "release-metadata/build.json", json.dumps(metadata))
    with pytest.raises((ValueError, RuntimeError)):
        module.verify_component_policy(payload, repo, "arm64")


def test_post_sign_refresh_updates_runtime_hashes_and_identical_python_without_rewriting_provenance(tmp_path, monkeypatch):
    module, repo, payload, bootstrap, original = fixture(tmp_path, monkeypatch)
    from generate_native_compliance import ComplianceError, native_body_inventory
    from verify_native_component_manifest import ComponentManifestError
    for name, body in original["components"]["glasshive"]["native_bodies"].items():
        path = payload / "runtime/native-bodies" / name / body["executable"]
        path.write_bytes(path.read_bytes() + b"synthetic signature\n")
    for relative in ("runtime/redis/bin/redis-server", "runtime/python/bin/python3"):
        path = payload / relative
        path.write_bytes(path.read_bytes() + b"synthetic signature\n")
    with pytest.raises(ValueError, match="stale"):
        module.verify_component_policy(payload, repo, "arm64")
    with pytest.raises(ComplianceError, match="executable differs"):
        native_body_inventory(payload, original["components"])
    with pytest.raises(ComponentManifestError):
        module.verify(payload / "runtime/python", payload / "release-metadata/python-runtime-manifest.json")
    module.refresh_signed_metadata(payload, bootstrap, repo, "arm64")
    final = module.verify_component_policy(payload, repo, "arm64")
    expected = copy.deepcopy(original)
    for name in final["components"]["glasshive"]["native_bodies"]:
        expected["components"]["glasshive"]["native_bodies"][name]["executable_sha256"] = final["components"]["glasshive"]["native_bodies"][name]["executable_sha256"]
    expected["components"]["redis"]["executable_sha256"] = final["components"]["redis"]["executable_sha256"]
    assert final == expected
    assert native_body_inventory(payload, final["components"])
    assert (payload / "runtime/python/bin/python3").read_bytes() == (bootstrap / "Contents/Resources/runtime/python/bin/python3").read_bytes()
    assert (payload / "release-metadata/python-runtime-manifest.json").read_bytes() == (bootstrap / "Contents/Resources/python-runtime-manifest.json").read_bytes()


def test_native_release_refresh_precedes_bootstrap_seal_and_skips_python_resigning():
    workflow = (ROOT / ".github/workflows/native-payload-release.yml").read_text()
    sign_payload = workflow.index('done < "$payload_root/release-metadata/apple-code-paths.txt"')
    refresh = workflow.index('--refresh-after-signing')
    sign_bootstrap = workflow.index('done < "${work_root}/bootstrap-code-paths.txt"')
    notarize_bootstrap = workflow.index('notarytool submit "${work_root}/pre-staple-bootstrap.zip"')
    assert sign_payload < refresh < sign_bootstrap < notarize_bootstrap
    assert 'path.is_relative_to(python_root)' in workflow[refresh:sign_bootstrap]


def test_native_signing_arguments_work_with_nounset_for_binary_and_helper(tmp_path):
    workflow = (ROOT / ".github/workflows/native-payload-release.yml").read_text()
    end = workflow.index('done < "$payload_root/release-metadata/apple-code-paths.txt"')
    start = workflow.rindex("          while IFS= read -r relative_path; do", 0, end)
    loop = workflow[start:end] + '          done < "$payload_root/release-metadata/apple-code-paths.txt"'
    put(tmp_path / "release-metadata/apple-code-paths.txt", "runtime/node/bin/node\napps/Viventium.app\n")
    result = subprocess.run(
        ["/bin/bash", "-c", "set -eu\n" + textwrap.dedent(loop).replace("/usr/bin/codesign", "/bin/echo")],
        env={**os.environ, "payload_root": str(tmp_path), "identity_hash": "synthetic-identity"},
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    binary, helper = result.stdout.splitlines()
    assert "--sign synthetic-identity" in binary and "--entitlements" not in binary
    assert "--sign synthetic-identity" in helper
    assert "--entitlements apps/macos/ViventiumHelper/ViventiumHelper.entitlements" in helper

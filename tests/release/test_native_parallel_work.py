from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from test_native_payload import load_module, write_candidate


REPO_ROOT = Path(__file__).resolve().parents[2]


def installed_runtime(tmp_path, monkeypatch):
    scripts = REPO_ROOT / "scripts/viventium"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location("native_runtime_under_test", scripts / "native_runtime.py")
    runtime = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runtime)
    payload = load_module()
    metadata = {"source_commit": "1" * 40, "mode": "local-qa",
                "data_schema": {"minimum": 1, "maximum": 1, "target": 1}}
    manifest, artifact, _ = write_candidate(tmp_path, files={
        "release-metadata/build.json": json.dumps(metadata).encode(),
        "runtime/product.txt": b"measured installed code",
    })
    candidate = payload.verify_candidate(manifest, artifact, allow_unsigned_local_qa=True,
                                         current_macos="26.5")
    root = payload.stage_candidate(candidate, artifact, tmp_path / "install")
    support = tmp_path / "support"
    runtime.ensure_support_directories(support, "runtime", "state")
    runtime.write_atomic(support / "state/native-runtime.json", json.dumps({
        "schema_version": 1, "installation_id": "2" * 32, "release_root": str(root),
        "local_qa": False,
    }))
    runtime.write_atomic(support / "state/native-first-admin.json", json.dumps({
        "schema_version": 1, "status": "closed", "admin_user_id": "3" * 24,
    }))
    for service in runtime.NATIVE_PARALLEL_SERVICES:
        runtime.write_atomic(runtime.pid_path(support, service), json.dumps({"service": service, "pid": 100}))
    monkeypatch.setattr(runtime, "release_root", lambda: root)
    monkeypatch.setattr(runtime, "owned_service_pid", lambda service, support, root: 100)
    return runtime, root, support


def test_native_parallel_identity_uses_installed_manifest_without_source_git(tmp_path, monkeypatch):
    runtime, root, support = installed_runtime(tmp_path, monkeypatch)
    proof = runtime.native_parallel_work_identity(support)
    assert proof["localQa"] is True
    assert proof["contractVersion"] == 1
    assert set(proof) == {"contractVersion", "localQa", "candidateDigest", "installedArtifactDigest", "runtimeOwnerBindingHash"}
    assert all(proof[name].startswith("sha256:") for name in proof if name.endswith(("Digest", "Hash")))
    assert str(root) not in json.dumps(proof) and str(support) not in json.dumps(proof)


@pytest.mark.parametrize("change", ["stale_install", "unsafe_state", "other_owner", "owner_open", "dead_service", "tampered_code"])
def test_native_parallel_identity_rejects_invalid_installed_authority(tmp_path, monkeypatch, change):
    runtime, root, support = installed_runtime(tmp_path, monkeypatch)
    if change == "stale_install":
        monkeypatch.setattr(runtime, "release_root", lambda: root.parent / "other")
    elif change == "unsafe_state":
        (support / "state/native-runtime.json").chmod(0o644)
    elif change == "other_owner":
        owner = support / "state/native-first-admin.json"
        owner.unlink()
        owner.symlink_to(support / "state/native-runtime.json")
    elif change == "owner_open":
        runtime.write_atomic(support / "state/native-first-admin.json", json.dumps({"schema_version": 1, "status": "open"}))
    elif change == "dead_service":
        monkeypatch.setattr(runtime, "owned_service_pid", lambda service, support, root: None if service == "redis" else 100)
    else:
        code = root / "runtime/product.txt"
        code.chmod(0o644)
        code.write_bytes(b"unverified replacement")
        code.chmod(0o444)
    with pytest.raises(runtime.RuntimeError_):
        runtime.native_parallel_work_identity(support)


def test_native_parallel_identity_rejects_restart_during_measurement(tmp_path, monkeypatch):
    runtime, root, support = installed_runtime(tmp_path, monkeypatch)
    calls = 0
    def changed_service(service, support, root):
        nonlocal calls
        calls += 1
        if calls > len(runtime.NATIVE_PARALLEL_SERVICES):
            runtime.write_atomic(runtime.pid_path(support, service), json.dumps({"service": service, "pid": 101}))
        return 101
    monkeypatch.setattr(runtime, "owned_service_pid", changed_service)
    with pytest.raises(runtime.RuntimeError_, match="ownership changed"):
        runtime.native_parallel_work_identity(support)


def test_native_parallel_work_typescript_consumer():
    import shutil
    import subprocess
    node = shutil.which("node")
    if not node or not (REPO_ROOT / "viventium_v0_4/LibreChat/node_modules/typescript").is_dir():
        pytest.skip("LibreChat Node dependencies are required for its native consumer checks")
    subprocess.run([node, "--test", str(Path(__file__).with_name("test_native_parallel_work_consumer.cjs"))],
                   cwd=REPO_ROOT, check=True, capture_output=True, text=True, timeout=60)

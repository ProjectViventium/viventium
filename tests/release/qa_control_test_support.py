from __future__ import annotations

import importlib.util
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RELEASE_GATE = ROOT / "scripts/viventium/parallel_work_release_gate.py"


def _load_release_gate():
    spec = importlib.util.spec_from_file_location(
        "parallel_work_release_gate_for_qa_control_tests", RELEASE_GATE
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_artifact_identity(installed: Path, identity: Path) -> dict[str, object]:
    manifest = installed / "scripts/viventium/parallel_work_runtime_artifact_manifest.json"
    if not manifest.exists():
        relative = "viventium_v0_4/LibreChat/api/server/services/viventium/LocalQaCortexFaultService.js"
        service = installed / relative
        service.parent.mkdir(parents=True, exist_ok=True)
        service.write_text(
            "module.exports = Object.freeze({ candidate: 1 });\n", encoding="utf-8"
        )
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(
            json.dumps(
                {
                    "contractVersion": 1,
                    "entries": [
                        {"kind": "file", "path": relative, "trackedOnly": False}
                    ],
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    release_gate = _load_release_gate()
    manifest_digest, running_digest = release_gate._runtime_service_artifact_digests(
        installed
    )
    assert manifest_digest and running_digest
    readiness = {
        key: hashlib.sha256(f"test-readiness:{key}".encode("utf-8")).hexdigest()
        for key in release_gate.READINESS_IDENTITY_HASH_KEYS
    }
    payload: dict[str, object] = {
        "contractVersion": 1,
        "readiness": readiness,
        "source": {
            "revision": "1" * 40,
            "clean": True,
            "worktreeHash": "2" * 64,
            "componentsLockSha256": "3" * 64,
        },
        "nestedComponents": [
            {
                "name": "LibreChat",
                "pin": "4" * 40,
                "revision": "4" * 40,
                "clean": True,
                "worktreeHash": "5" * 64,
            }
        ],
        "prebuiltHelper": {
            "sourceDeclaredSha256": "6" * 64,
            "sourceMeasuredSha256": "6" * 64,
            "binaryDeclaredSha256": "7" * 64,
            "binaryMeasuredSha256": "7" * 64,
            "binaryExecutable": True,
        },
        "installed": {
            "rootRevision": "8" * 40,
            "componentsLockSha256": "9" * 64,
            "nestedRevisionsHash": "a" * 64,
            "prebuiltSourceSha256": "b" * 64,
            "prebuiltBinarySha256": "c" * 64,
            "promptBundleSha256": "d" * 64,
            "runtimeEnvSha256": "e" * 64,
            "libreChatConfigSha256": "f" * 64,
            "frontendBuildSha256": "0" * 64,
            "apiBuildSha256": "1" * 64,
            "runningServiceSha256": running_digest,
            "runtimeServiceManifestSha256": manifest_digest,
            "runtimeOwnerExecutableSha256": "2" * 64,
            "ownerCommandContractSha256": "3" * 64,
        },
    }
    identity.parent.mkdir(parents=True, exist_ok=True)
    identity.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(identity, 0o600)
    return payload

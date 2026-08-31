from __future__ import annotations

import importlib.util
import json
import os
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from qa_control_test_support import write_artifact_identity

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "viventium" / "release_claim_qa_fault.py"
SESSION_SCRIPT = ROOT / "scripts" / "viventium" / "local_qa_runtime_control.py"
CLI = ROOT / "bin" / "viventium"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _healthy() -> dict[str, object]:
    return {
        "contractVersion": 1,
        "promptLayers": {
            "contractVersion": 1,
            "producerScope": "viventium.prompt_registry.v1",
            "status": "verified",
            "unknownLayerCount": 0,
            "unknownLayerNames": [],
            "promptCount": 4,
            "layerCount": 2,
            "layerNames": ["dynamic", "static"],
            "registryHash": "a" * 64,
        },
        "storagePressure": {
            "version": 1,
            "status": "healthy",
            "usedPercent": 40.0,
            "availableBytes": 80_000_000_000,
            "thresholdPercent": 95.0,
            "warningMarginPercent": 10.0,
        },
    }


def _session(tmp_path: Path, case_id: str = "REL-UC-004"):
    control = _load(SESSION_SCRIPT, "local_qa_runtime_control_for_release_fault")
    installed = tmp_path / "installed"
    installed.mkdir()
    session = tmp_path / "runtime" / "local-qa" / "active.json"
    identity = tmp_path / "runtime" / "parallel-work-artifact-identity.json"
    write_artifact_identity(installed, identity)
    request = tmp_path / "runtime" / "parallel-work-local-qa-request.json"
    request.write_text(
        '{"contractVersion":1,"mode":"local-qa","requested":true}\n',
        encoding="utf-8",
    )
    os.chmod(request, 0o600)
    now = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)
    control.activate_session(
        state_path=session,
        installed_root=installed,
        artifact_identity_path=identity,
        local_qa_request_path=request,
        case_id=case_id,
        expires_in_seconds=900,
        now=now,
        token_bytes=lambda size: b"z" * size,
    )
    return installed, identity, session, now


def test_apply_injects_typed_faults_without_consuming_disk(tmp_path: Path) -> None:
    module = _load(SCRIPT, "release_claim_qa_fault")
    installed, identity, session, now = _session(tmp_path)
    readiness = tmp_path / "runtime" / "parallel-work-readiness-facts.json"
    readiness.parent.mkdir(exist_ok=True)
    original = _healthy()
    readiness.write_text(json.dumps(original), encoding="utf-8")
    backup = tmp_path / "runtime" / "local-qa" / "release-claim-backup.json"

    result = module.apply_faults(
        session_state=session,
        installed_root=installed,
        artifact_identity_path=identity,
        readiness_path=readiness,
        backup_path=backup,
        now=now,
    )
    injected = json.loads(readiness.read_text(encoding="utf-8"))

    assert result["applied"] is True
    assert result["diskBytesWritten"] < 20_000
    assert injected["promptLayers"]["status"] == "mismatch"
    assert injected["promptLayers"]["registryHash"] != "a" * 64
    assert injected["storagePressure"] == {
        "version": 1,
        "status": "critical",
        "usedPercent": 96.0,
        "availableBytes": 4_300_000_000,
        "thresholdPercent": 95.0,
        "warningMarginPercent": 10.0,
        "reason": "local_qa_threshold_injection",
    }
    assert stat.S_IMODE(readiness.stat().st_mode) == 0o600
    assert stat.S_IMODE(backup.stat().st_mode) == 0o600
    assert str(installed) not in backup.read_text(encoding="utf-8")


def test_restore_is_exact_and_refuses_concurrent_change(tmp_path: Path) -> None:
    module = _load(SCRIPT, "release_claim_qa_fault_restore")
    installed, identity, session, now = _session(tmp_path)
    readiness = tmp_path / "runtime" / "parallel-work-readiness-facts.json"
    readiness.parent.mkdir(exist_ok=True)
    original = _healthy()
    readiness.write_text(json.dumps(original), encoding="utf-8")
    backup = tmp_path / "runtime" / "local-qa" / "release-claim-backup.json"
    module.apply_faults(
        session_state=session,
        installed_root=installed,
        artifact_identity_path=identity,
        readiness_path=readiness,
        backup_path=backup,
        now=now,
    )

    restored = module.restore_faults(
        session_state=session,
        installed_root=installed,
        artifact_identity_path=identity,
        readiness_path=readiness,
        backup_path=backup,
        now=now,
    )
    assert restored["restored"] is True
    assert json.loads(readiness.read_text(encoding="utf-8")) == original
    assert not backup.exists()

    module.apply_faults(
        session_state=session,
        installed_root=installed,
        artifact_identity_path=identity,
        readiness_path=readiness,
        backup_path=backup,
        now=now,
    )
    readiness.write_text(json.dumps({"concurrent": True}), encoding="utf-8")
    with pytest.raises(ValueError, match="changed after injection"):
        module.restore_faults(
            session_state=session,
            installed_root=installed,
            artifact_identity_path=identity,
            readiness_path=readiness,
            backup_path=backup,
            now=now,
        )


def test_apply_requires_exact_active_rel004_session(tmp_path: Path) -> None:
    module = _load(SCRIPT, "release_claim_qa_fault_wrong_case")
    installed, identity, session, now = _session(tmp_path, "TR-026")
    readiness = tmp_path / "runtime" / "parallel-work-readiness-facts.json"
    readiness.parent.mkdir(exist_ok=True)
    readiness.write_text(json.dumps(_healthy()), encoding="utf-8")
    backup = tmp_path / "runtime" / "local-qa" / "release-claim-backup.json"

    with pytest.raises(ValueError, match="REL-UC-004"):
        module.apply_faults(
            session_state=session,
            installed_root=installed,
            artifact_identity_path=identity,
            readiness_path=readiness,
            backup_path=backup,
            now=now,
        )


def test_cli_wires_apply_and_restore_under_qa_control() -> None:
    text = CLI.read_text(encoding="utf-8")
    assert "inject-release-claim" in text
    assert "restore-release-claim" in text
    assert "release_claim_qa_fault.py" in text

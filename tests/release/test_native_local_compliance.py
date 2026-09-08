from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

import pytest


@pytest.mark.parametrize("mode,approved,allowed", [
    ("local-qa", False, True), ("candidate", False, False),
    (None, False, False), ("unknown", False, False), ("candidate", True, True),
])
def test_compliance_inventory_keeps_redistribution_approval_at_release_boundary(
    tmp_path, monkeypatch, mode, approved, allowed
):
    root = Path(__file__).resolve().parents[2]
    scripts = root / "scripts/viventium"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location("native_compliance_boundary", scripts / "generate_native_compliance.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    payload = tmp_path / "payload"
    metadata = payload / "release-metadata"
    metadata.mkdir(parents=True)
    (metadata / "build.json").write_text(json.dumps({
        "mode": mode, "arch": "arm64", "source_commit": "a" * 40, "source_date_epoch": 1788508800
    }))
    approval = tmp_path / "approval"
    if approved:
        approval.write_text("Synthetic release-authority fixture\n")
    args = argparse.Namespace(payload_root=payload, output_dir=metadata,
                              mongodb_redistribution_approved=approval if approved else None)
    monkeypatch.setattr(module, "inventory", lambda _payload: [])
    if not allowed:
        with pytest.raises(module.ComplianceError, match="redistribution approval"):
            module.generate(args)
        assert not (metadata / "native-license-scan.json").exists()
        return
    module.generate(args)
    scan = json.loads((metadata / "native-license-scan.json").read_text())
    assert scan["redistribution_approval"] == ("recorded" if approved else "not_recorded_local_qa")

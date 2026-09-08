from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load_owner(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts/viventium" / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("change", ["none", "life_changed", "life_missing", "life_symlink"])
def test_helper_consumers_share_canonical_source_contract(tmp_path: Path, monkeypatch, change: str):
    canonical = load_owner("helper_artifact_verify")
    upgrade = load_owner("upgrade_check")
    gate = load_owner("parallel_work_release_gate")
    helper = tmp_path / "apps/macos/ViventiumHelper"
    for relative in canonical.SOURCE_FILES:
        path = helper / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"source:{relative}\n", encoding="utf-8")
    expected = canonical.helper_source_hash(helper)
    prebuilt = helper / "prebuilt"
    prebuilt.mkdir()
    binary = prebuilt / "ViventiumHelper-universal"
    binary.write_bytes(b"fixture executable")
    binary.chmod(0o755)
    (prebuilt / "source.sha256").write_text(expected + "\n")
    (prebuilt / "binary.sha256").write_text(hashlib.sha256(binary.read_bytes()).hexdigest() + "\n")
    monkeypatch.setattr(upgrade, "_is_universal_macos_binary", lambda path: True)
    life = helper / "Sources/ViventiumHelper/LifeSetup.swift"
    if change == "life_changed":
        life.write_text("changed source\n")
    elif change == "life_missing":
        life.unlink()
    elif change == "life_symlink":
        target = tmp_path / "other-source.swift"
        target.write_bytes(life.read_bytes())
        life.unlink()
        life.symlink_to(target)
    assert upgrade.helper_needs_rebuild(tmp_path) is (change != "none")
    if change in {"life_missing", "life_symlink"}:
        assert gate._helper_source_hash(helper) == ""
    else:
        assert gate._helper_source_hash(helper) == canonical.helper_source_hash(helper)

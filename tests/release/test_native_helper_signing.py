from __future__ import annotations

import json
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys

import pytest
import test_native_payload_assembler as owner


BUILDER = owner.REPO_ROOT / "scripts/viventium/build_native_payload.py"
pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="macOS code-signing contract")


def signed_helper(app: Path) -> bytes:
    executable = app / "Contents/MacOS/Viventium"
    executable.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile("/usr/bin/true", executable)
    executable.chmod(0o755)
    (app / "Contents/Info.plist").write_bytes(plistlib.dumps({
        "CFBundleIdentifier": "ai.viventium.helper",
        "CFBundleExecutable": "Viventium",
        "CFBundlePackageType": "APPL",
    }))
    marker = b'{"product":"ai.viventium.helper","schema_version":1}\n'
    owner.file(app / "Contents/Resources/viventium-owner.json", marker.decode())
    subprocess.run(["/usr/bin/codesign", "--force", "--sign", "-", str(app)],
                   check=True, capture_output=True)
    return marker


def test_complete_assembly_preserves_signed_helper_resources(tmp_path: Path) -> None:
    inputs = owner.fixture_inputs(tmp_path)
    signed_helper(inputs["helper"])
    before = owner.tree_digest(inputs["helper"])
    output = tmp_path / "candidate"
    result = owner.run_assembler(tmp_path, inputs, output)
    assert result.returncode == 0, result.stderr
    helper = output / "payload/apps/Viventium.app"
    verified = subprocess.run(["/usr/bin/codesign", "--verify", "--deep", "--strict", str(helper)],
                              capture_output=True, text=True)
    assert verified.returncode == 0, verified.stderr
    assert owner.tree_digest(helper) == before
    metadata = json.loads((output / "payload/release-metadata/build.json").read_text())
    assert metadata["source_commit"] == "a" * 40


def test_archive_builder_rejects_post_sign_mutation_before_publication(tmp_path: Path) -> None:
    payload = tmp_path / "payload"
    helper = payload / "apps/Viventium.app"
    marker = signed_helper(helper)
    resource = helper / "Contents/Resources/viventium-owner.json"
    resource.write_bytes(marker.rstrip() + b" \n")
    output = tmp_path / "artifacts"
    command = [sys.executable, str(BUILDER), "--payload-root", str(payload),
               "--output-dir", str(output), "--release-id", "signature-fixture", "--sequence", "1",
               "--channel", "local-qa", "--arch", "arm64", "--node-version", "24.16.0",
               "--minimum-macos", "15.0", "--source-date-epoch", "1700000000",
               "--data-schema-minimum", "1", "--data-schema-maximum", "1"]
    failed = subprocess.run(command, capture_output=True, text=True)
    assert failed.returncode != 0
    assert "signature is invalid" in failed.stderr
    assert not output.exists()
    resource.write_bytes(marker)
    passed = subprocess.run(command, capture_output=True, text=True)
    assert passed.returncode == 0, passed.stderr


def test_unsigned_ci_envelope_gets_canonical_marker_before_signing(tmp_path: Path) -> None:
    inputs = owner.fixture_inputs(tmp_path)
    output = tmp_path / "candidate"
    result = owner.run_assembler(tmp_path, inputs, output)
    assert result.returncode == 0, result.stderr
    marker = output / "payload/apps/Viventium.app/Contents/Resources/viventium-owner.json"
    assert marker.read_bytes() == b'{"product":"ai.viventium.helper","schema_version":1}\n'

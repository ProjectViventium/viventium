from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
BUILDER = REPO_ROOT / "scripts" / "viventium" / "build_native_payload.py"
NATIVE_PAYLOAD = REPO_ROOT / "scripts" / "viventium" / "native_payload.py"


def load_native_payload():
    spec = importlib.util.spec_from_file_location("native_payload", NATIVE_PAYLOAD)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_payload_root(root: Path) -> None:
    (root / "bin").mkdir(parents=True)
    (root / "app").mkdir()
    health = root / "bin" / "viventium-native-health"
    health.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    health.chmod(0o755)
    data = root / "app" / "version.txt"
    data.write_text("0.4.0\n", encoding="utf-8")
    data.chmod(0o644)

    compressible = root / "app" / "compressible.dat"
    compressible.write_bytes(b"viventium-native-payload\n" * 4096)
    compressible.chmod(0o644)


def run_builder(payload_root: Path, output_dir: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(BUILDER),
            "--payload-root",
            str(payload_root),
            "--output-dir",
            str(output_dir),
            "--release-id",
            "0.4.0",
            "--sequence",
            "40",
            "--arch",
            "arm64",
            "--node-version",
            "24.16.0",
            "--minimum-macos",
            "13.0",
            "--data-schema-minimum",
            "1",
            "--data-schema-maximum",
            "1",
            "--source-date-epoch",
            "1700000000",
            *extra,
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_local_qa_builder_is_deterministic_and_emits_verifiable_unsigned_artifact(
    tmp_path: Path,
) -> None:
    payload_root = tmp_path / "payload"
    write_payload_root(payload_root)
    first_output = tmp_path / "first"
    second_output = tmp_path / "second"

    first = run_builder(payload_root, first_output, "--channel", "local-qa")
    second = run_builder(payload_root, second_output, "--channel", "local-qa")

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    first_summary = json.loads(first.stdout)
    second_summary = json.loads(second.stdout)
    first_artifact = first_output / first_summary["artifact"]
    second_artifact = second_output / second_summary["artifact"]
    first_manifest = first_output / first_summary["manifest"]
    second_manifest = second_output / second_summary["manifest"]
    assert first_artifact.read_bytes() == second_artifact.read_bytes()
    assert first_manifest.read_bytes() == second_manifest.read_bytes()
    assert first_summary["signature"] is None

    manifest_payload = json.loads(first_manifest.read_text(encoding="utf-8"))
    assert manifest_payload["channel"] == "local-qa"
    assert manifest_payload["local_qa"] is True
    assert [entry["path"] for entry in manifest_payload["files"]] == [
        "app/compressible.dat",
        "app/version.txt",
        "bin/viventium-native-health",
    ]
    with zipfile.ZipFile(first_artifact) as archive:
        assert archive.namelist() == [
            "app/compressible.dat",
            "app/version.txt",
            "bin/viventium-native-health",
        ]
        assert {info.compress_type for info in archive.infolist()} == {
            zipfile.ZIP_DEFLATED
        }
        compressible_info = archive.getinfo("app/compressible.dat")
        assert compressible_info.compress_size < compressible_info.file_size // 10
        assert {info.date_time for info in archive.infolist()} == {
            (2023, 11, 14, 22, 13, 20)
        }

    native_payload = load_native_payload()
    verified = native_payload.verify_candidate(
        first_manifest,
        first_artifact,
        allow_unsigned_local_qa=True,
        expected_arch="arm64",
        current_macos="13.0",
    )
    assert verified.sequence == 40


def test_local_qa_artifact_runs_the_verified_stage_activate_health_path(
    tmp_path: Path,
) -> None:
    payload_root = tmp_path / "payload"
    write_payload_root(payload_root)
    output_dir = tmp_path / "output"

    completed = run_builder(payload_root, output_dir, "--channel", "local-qa")

    assert completed.returncode == 0, completed.stderr
    summary = json.loads(completed.stdout)
    native_payload = load_native_payload()
    candidate = native_payload.verify_candidate(
        output_dir / summary["manifest"],
        output_dir / summary["artifact"],
        allow_unsigned_local_qa=True,
        expected_arch="arm64",
        current_macos="13.0",
    )
    install_root = tmp_path / "install"
    staged = native_payload.stage_candidate(
        candidate,
        output_dir / summary["artifact"],
        install_root,
    )
    active = native_payload.activate_candidate(
        candidate,
        staged,
        install_root,
        health_check=lambda release: subprocess.run(
            [str(release / "bin" / "viventium-native-health")],
            check=False,
        ).returncode
        == 0,
    )

    assert active == staged
    assert (install_root / "active").resolve() == staged.resolve()
    assert (active / "app" / "version.txt").read_text(encoding="utf-8") == "0.4.0\n"


def test_stable_builder_fails_closed_without_manifest_signing_authority(
    tmp_path: Path,
) -> None:
    payload_root = tmp_path / "payload"
    write_payload_root(payload_root)
    output_dir = tmp_path / "output"

    completed = run_builder(payload_root, output_dir, "--channel", "stable")

    assert completed.returncode != 0
    assert "stable channel requires --manifest-signing-key" in completed.stderr
    assert not output_dir.exists() or not any(output_dir.iterdir())


def test_builder_refuses_to_replace_an_existing_artifact_set(tmp_path: Path) -> None:
    payload_root = tmp_path / "payload"
    write_payload_root(payload_root)
    output_dir = tmp_path / "output"
    first = run_builder(payload_root, output_dir, "--channel", "local-qa")
    assert first.returncode == 0, first.stderr
    before = {
        path.name: path.read_bytes()
        for path in output_dir.iterdir()
        if path.is_file()
    }
    (payload_root / "app" / "version.txt").write_text("changed\n", encoding="utf-8")

    second = run_builder(payload_root, output_dir, "--channel", "local-qa")

    assert second.returncode != 0
    assert "output directory already exists" in second.stderr
    assert {
        path.name: path.read_bytes()
        for path in output_dir.iterdir()
        if path.is_file()
    } == before


@pytest.mark.skipif(shutil.which("ssh-keygen") is None, reason="OpenSSH is unavailable")
def test_stable_builder_signs_canonical_manifest_for_pinned_allowed_signer(
    tmp_path: Path,
) -> None:
    payload_root = tmp_path / "payload"
    write_payload_root(payload_root)
    output_dir = tmp_path / "output"
    signing_key = tmp_path / "release-signing-key"
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(signing_key)],
        check=True,
    )

    completed = run_builder(
        payload_root,
        output_dir,
        "--channel",
        "stable",
        "--manifest-signing-key",
        str(signing_key),
    )

    assert completed.returncode == 0, completed.stderr
    summary = json.loads(completed.stdout)
    manifest = output_dir / summary["manifest"]
    artifact = output_dir / summary["artifact"]
    signature = output_dir / summary["signature"]
    assert signature.is_file()
    allowed_signers = tmp_path / "allowed_signers"
    public_key = signing_key.with_suffix(".pub").read_text(encoding="utf-8").strip()
    native_payload = load_native_payload()
    allowed_signers.write_text(
        f"{native_payload.SIGNING_IDENTITY} {public_key}\n",
        encoding="utf-8",
    )
    verified = native_payload.verify_candidate(
        manifest,
        artifact,
        signature_path=signature,
        allowed_signers_path=allowed_signers,
        expected_arch="arm64",
        current_macos="13.0",
    )
    assert verified.payload["channel"] == "stable"
    assert verified.payload["local_qa"] is False


@pytest.mark.parametrize("unsafe_kind", ["symlink", "root_symlink", "mutable_mode"])
def test_builder_rejects_unsafe_payload_input(
    tmp_path: Path,
    unsafe_kind: str,
) -> None:
    payload_root = tmp_path / "payload"
    write_payload_root(payload_root)
    if unsafe_kind == "symlink":
        (payload_root / "linked").symlink_to("app/version.txt")
        expected = "symlink"
    elif unsafe_kind == "root_symlink":
        actual_root = tmp_path / "actual-payload"
        payload_root.rename(actual_root)
        payload_root.symlink_to(actual_root, target_is_directory=True)
        expected = "real directory"
    else:
        (payload_root / "app" / "version.txt").chmod(0o664)
        expected = "mode"

    completed = run_builder(
        payload_root,
        tmp_path / "output",
        "--channel",
        "local-qa",
    )

    assert completed.returncode != 0
    assert expected in completed.stderr.lower()


def test_builder_does_not_echo_signing_key_path_on_failure(tmp_path: Path) -> None:
    payload_root = tmp_path / "payload"
    write_payload_root(payload_root)
    secret_named_key = tmp_path / "do-not-echo-secret-key-name"
    secret_named_key.write_text("not a private key\n", encoding="utf-8")

    completed = run_builder(
        payload_root,
        tmp_path / "output",
        "--channel",
        "stable",
        "--manifest-signing-key",
        str(secret_named_key),
    )

    assert completed.returncode != 0
    assert str(secret_named_key) not in completed.stderr

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import stat
import subprocess
import zipfile
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "viventium" / "native_payload.py"


def load_module():
    spec = importlib.util.spec_from_file_location("native_payload", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_candidate(
    root: Path,
    *,
    release_id: str = "0.4.0-qa.1",
    sequence: int = 1,
    files: dict[str, bytes] | None = None,
) -> tuple[Path, Path, dict]:
    files = files or {
        "bin/viventium": b"#!/bin/sh\nexit 0\n",
        "app/version.txt": release_id.encode("utf-8") + b"\n",
    }
    artifact = root / f"{release_id}.zip"
    with zipfile.ZipFile(artifact, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, data in files.items():
            info = zipfile.ZipInfo(path)
            info.external_attr = (0o100755 if path.startswith("bin/") else 0o100644) << 16
            archive.writestr(info, data)

    payload = {
        "schema_version": 1,
        "release_id": release_id,
        "sequence": sequence,
        "channel": "local-qa",
        "local_qa": True,
        "platform": {"os": "macos", "arch": "arm64", "minimum_version": "14.0"},
        "artifact": {
            "filename": artifact.name,
            "sha256": sha256(artifact.read_bytes()),
            "size": artifact.stat().st_size,
            "uncompressed_size": sum(len(data) for data in files.values()),
        },
        "runtime": {
            "node": "24.18.0",
            "data_schema": {"minimum": 1, "maximum": 1},
        },
        "files": [
            {
                "path": path,
                "sha256": sha256(data),
                "size": len(data),
                "mode": 0o755 if path.startswith("bin/") else 0o644,
            }
            for path, data in sorted(files.items())
        ],
    }
    manifest = root / f"{release_id}.manifest.json"
    manifest.write_bytes(load_module().canonical_manifest_bytes(payload))
    return manifest, artifact, payload


def test_unsigned_manifest_fails_closed_without_explicit_local_qa_override(tmp_path: Path) -> None:
    module = load_module()
    manifest, artifact, _payload = write_candidate(tmp_path)

    with pytest.raises(module.PayloadError, match="signature is required"):
        module.verify_candidate(manifest, artifact)

    verified = module.verify_candidate(
        manifest,
        artifact,
        allow_unsigned_local_qa=True,
        expected_arch="arm64",
        current_macos="26.5",
    )
    assert verified.release_id == "0.4.0-qa.1"
    assert verified.node_version == "24.18.0"


def test_unsigned_override_rejects_manifest_that_is_not_explicitly_local_qa(tmp_path: Path) -> None:
    module = load_module()
    manifest, artifact, payload = write_candidate(tmp_path)
    payload["channel"] = "stable"
    payload["local_qa"] = False
    manifest.write_bytes(module.canonical_manifest_bytes(payload))

    with pytest.raises(module.PayloadError, match="only valid for a local QA manifest"):
        module.verify_candidate(manifest, artifact, allow_unsigned_local_qa=True)


def test_publisher_signature_accepts_exact_manifest_and_rejects_tampering(tmp_path: Path) -> None:
    module = load_module()
    manifest, artifact, _payload = write_candidate(tmp_path)
    private_key = tmp_path / "release-signing-key"
    subprocess.run(
        ["/usr/bin/ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(private_key)],
        check=True,
    )
    subprocess.run(
        [
            "/usr/bin/ssh-keygen",
            "-Y",
            "sign",
            "-f",
            str(private_key),
            "-n",
            module.SIGNING_NAMESPACE,
            str(manifest),
        ],
        check=True,
        capture_output=True,
    )
    signature = Path(f"{manifest}.sig")
    allowed_signers = tmp_path / "allowed_signers"
    public_key = Path(f"{private_key}.pub").read_text(encoding="utf-8").strip()
    allowed_signers.write_text(
        f"{module.SIGNING_IDENTITY} {public_key}\n",
        encoding="utf-8",
    )

    verified = module.verify_candidate(
        manifest,
        artifact,
        signature_path=signature,
        allowed_signers_path=allowed_signers,
    )
    assert verified.release_id == "0.4.0-qa.1"

    signature.write_bytes(signature.read_bytes().replace(b"A", b"B", 1))
    with pytest.raises(module.PayloadError, match="signature verification failed"):
        module.verify_candidate(
            manifest,
            artifact,
            signature_path=signature,
            allowed_signers_path=allowed_signers,
        )


def test_candidate_rejects_noncanonical_manifest_and_corrupt_archive(tmp_path: Path) -> None:
    module = load_module()
    manifest, artifact, payload = write_candidate(tmp_path)
    manifest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(module.PayloadError, match="canonical JSON"):
        module.verify_candidate(manifest, artifact, allow_unsigned_local_qa=True)

    manifest.write_bytes(module.canonical_manifest_bytes(payload))
    artifact.write_bytes(artifact.read_bytes() + b"corrupt")
    with pytest.raises(module.PayloadError, match="size does not match"):
        module.verify_candidate(manifest, artifact, allow_unsigned_local_qa=True)


@pytest.mark.parametrize(
    "host_arch,host_version,error",
    [
        ("x86_64", "26.5", "architecture"),
        ("arm64", "13.6", "requires macOS"),
    ],
)
def test_candidate_enforces_platform_contract(
    tmp_path: Path,
    host_arch: str,
    host_version: str,
    error: str,
) -> None:
    module = load_module()
    manifest, artifact, _payload = write_candidate(tmp_path)

    with pytest.raises(module.PayloadError, match=error):
        module.verify_candidate(
            manifest,
            artifact,
            allow_unsigned_local_qa=True,
            expected_arch=host_arch,
            current_macos=host_version,
        )


@pytest.mark.parametrize("hostile_path", ["../escape", "/absolute", "a/../../escape", "a\\escape"])
def test_staging_rejects_hostile_archive_paths(tmp_path: Path, hostile_path: str) -> None:
    module = load_module()
    manifest, artifact, payload = write_candidate(tmp_path, files={"safe.txt": b"safe"})
    with zipfile.ZipFile(artifact, "a") as archive:
        archive.writestr(hostile_path, b"hostile")
    payload["artifact"].update(
        sha256=sha256(artifact.read_bytes()),
        size=artifact.stat().st_size,
        uncompressed_size=11,
    )
    payload["files"].append(
        {"path": hostile_path, "sha256": sha256(b"hostile"), "size": 7, "mode": 0o644}
    )
    manifest.write_bytes(module.canonical_manifest_bytes(payload))
    with pytest.raises(module.PayloadError, match="unsafe archive path"):
        verified = module.verify_candidate(manifest, artifact, allow_unsigned_local_qa=True)
        module.stage_candidate(verified, artifact, tmp_path / "install")

    assert not (tmp_path / "escape").exists()


def test_staging_rejects_symlinks_case_collisions_and_unlisted_files(tmp_path: Path) -> None:
    module = load_module()
    install_root = tmp_path / "install"

    manifest, artifact, payload = write_candidate(tmp_path, files={"safe.txt": b"safe"})
    with zipfile.ZipFile(artifact, "a") as archive:
        link = zipfile.ZipInfo("link")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(link, "safe.txt")
    payload["artifact"].update(
        sha256=sha256(artifact.read_bytes()),
        size=artifact.stat().st_size,
        uncompressed_size=12,
    )
    payload["files"].append(
        {"path": "link", "sha256": sha256(b"safe.txt"), "size": 8, "mode": 0o644}
    )
    manifest.write_bytes(module.canonical_manifest_bytes(payload))
    verified = module.verify_candidate(manifest, artifact, allow_unsigned_local_qa=True)
    with pytest.raises(module.PayloadError, match="symlink"):
        module.stage_candidate(verified, artifact, install_root)

    collision_root = tmp_path / "collision"
    collision_root.mkdir()
    manifest, artifact, _payload = write_candidate(
        collision_root,
        files={"Readme": b"one", "README": b"two"},
    )
    with pytest.raises(module.PayloadError, match="case-insensitive path collision"):
        verified = module.verify_candidate(manifest, artifact, allow_unsigned_local_qa=True)
        module.stage_candidate(verified, artifact, install_root)

    extra_root = tmp_path / "extra"
    extra_root.mkdir()
    manifest, artifact, payload = write_candidate(extra_root, files={"safe.txt": b"safe"})
    with zipfile.ZipFile(artifact, "a") as archive:
        archive.writestr("unlisted.txt", b"extra")
    payload["artifact"].update(
        sha256=sha256(artifact.read_bytes()),
        size=artifact.stat().st_size,
        uncompressed_size=4,
    )
    manifest.write_bytes(module.canonical_manifest_bytes(payload))
    verified = module.verify_candidate(manifest, artifact, allow_unsigned_local_qa=True)
    with pytest.raises(module.PayloadError, match="does not match manifest"):
        module.stage_candidate(verified, artifact, install_root)


def test_activation_is_atomic_journaled_and_rolls_back_failed_health(tmp_path: Path) -> None:
    module = load_module()
    install_root = tmp_path / "install"

    first_root = tmp_path / "first"
    first_root.mkdir()
    manifest, artifact, _payload = write_candidate(first_root, release_id="0.4.0-qa.1", sequence=1)
    first = module.verify_candidate(manifest, artifact, allow_unsigned_local_qa=True)
    first_release = module.stage_candidate(first, artifact, install_root)
    activated = module.activate_candidate(first, first_release, install_root, health_check=lambda _path: True)
    assert activated == first_release
    assert (install_root / "active").resolve() == first_release.resolve()
    assert not (install_root / "previous").exists()

    second_root = tmp_path / "second"
    second_root.mkdir()
    manifest, artifact, _payload = write_candidate(second_root, release_id="0.4.0-qa.2", sequence=2)
    second = module.verify_candidate(manifest, artifact, allow_unsigned_local_qa=True)
    second_release = module.stage_candidate(second, artifact, install_root)

    with pytest.raises(module.PayloadError, match="health check failed"):
        module.activate_candidate(
            second,
            second_release,
            install_root,
            health_check=lambda _path: False,
        )

    assert (install_root / "active").resolve() == first_release.resolve()
    assert (install_root / "previous").resolve() == first_release.resolve()
    assert not any(path.name.startswith(".active-") for path in install_root.iterdir())
    records = [
        json.loads(line)
        for line in (install_root / "state" / "native-installer" / "journal.ndjson")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert [record["event"] for record in records][-3:] == [
        "activation_started",
        "pointer_switched",
        "health_failed_rollback_complete",
    ]
    assert all(str(tmp_path) not in json.dumps(record) for record in records)


def test_replay_and_incompatible_data_schema_fail_before_activation(tmp_path: Path) -> None:
    module = load_module()
    install_root = tmp_path / "install"
    state_root = install_root / "state" / "native-installer"
    state_root.mkdir(parents=True)
    (state_root / "highest-sequence").write_text("5\n", encoding="utf-8")
    manifest, artifact, _payload = write_candidate(tmp_path, sequence=4)
    verified = module.verify_candidate(manifest, artifact, allow_unsigned_local_qa=True)
    release = module.stage_candidate(verified, artifact, install_root)

    with pytest.raises(module.PayloadError, match="replayed or downgraded"):
        module.activate_candidate(verified, release, install_root, health_check=lambda _path: True)

    (state_root / "highest-sequence").write_text("0\n", encoding="utf-8")
    with pytest.raises(module.PayloadError, match="data schema 2"):
        module.activate_candidate(
            verified,
            release,
            install_root,
            current_data_schema=2,
            health_check=lambda _path: True,
        )

    assert not (install_root / "active").exists()


def test_staging_never_writes_to_app_support_data_tree(tmp_path: Path) -> None:
    module = load_module()
    install_root = tmp_path / "runtime-payloads"
    app_support = tmp_path / "Application Support" / "Viventium"
    sentinel = app_support / "state" / "personal-db.sentinel"
    sentinel.parent.mkdir(parents=True)
    sentinel.write_text("do-not-change\n", encoding="utf-8")
    before = sentinel.read_bytes()
    before_stat = sentinel.stat()

    manifest, artifact, _payload = write_candidate(tmp_path)
    verified = module.verify_candidate(manifest, artifact, allow_unsigned_local_qa=True)
    module.stage_candidate(verified, artifact, install_root)

    assert sentinel.read_bytes() == before
    assert sentinel.stat().st_mtime_ns == before_stat.st_mtime_ns
    assert os.path.commonpath([install_root, app_support]) == str(tmp_path)

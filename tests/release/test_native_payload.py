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
    channel: str = "local-qa",
    local_qa: bool = True,
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
            info.external_attr = (
                0o100755 if path.startswith("bin/") else 0o100644
            ) << 16
            archive.writestr(info, data)

    payload = {
        "schema_version": 1,
        "release_id": release_id,
        "sequence": sequence,
        "channel": channel,
        "local_qa": local_qa,
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


def sign_manifest(module, root: Path, manifest: Path) -> tuple[Path, Path]:
    private_key = root / "release-signing-key"
    subprocess.run(
        [
            "/usr/bin/ssh-keygen",
            "-q",
            "-t",
            "ed25519",
            "-N",
            "",
            "-f",
            str(private_key),
        ],
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
    allowed_signers = root / "allowed_signers"
    public_key = Path(f"{private_key}.pub").read_text(encoding="utf-8").strip()
    allowed_signers.write_text(
        f"{module.SIGNING_IDENTITY} {public_key}\n",
        encoding="utf-8",
    )
    return signature, allowed_signers


def test_unsigned_manifest_fails_closed_without_explicit_local_qa_override(
    tmp_path: Path,
) -> None:
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


def test_unsigned_override_rejects_manifest_that_is_not_explicitly_local_qa(
    tmp_path: Path,
) -> None:
    module = load_module()
    manifest, artifact, payload = write_candidate(tmp_path)
    payload["channel"] = "stable"
    payload["local_qa"] = False
    manifest.write_bytes(module.canonical_manifest_bytes(payload))

    with pytest.raises(module.PayloadError, match="only valid for a local QA manifest"):
        module.verify_candidate(manifest, artifact, allow_unsigned_local_qa=True)


def test_publisher_signature_accepts_exact_manifest_and_rejects_tampering(
    tmp_path: Path,
) -> None:
    module = load_module()
    manifest, artifact, _payload = write_candidate(
        tmp_path,
        release_id="1.0.0",
        channel="stable",
        local_qa=False,
    )
    signature, allowed_signers = sign_manifest(module, tmp_path, manifest)

    verified = module.verify_candidate(
        manifest,
        artifact,
        signature_path=signature,
        allowed_signers_path=allowed_signers,
        expected_arch="arm64",
        current_macos="26.5",
    )
    assert verified.release_id == "1.0.0"

    signature.write_bytes(signature.read_bytes().replace(b"A", b"B", 1))
    with pytest.raises(module.PayloadError, match="signature verification failed"):
        module.verify_candidate(
            manifest,
            artifact,
            signature_path=signature,
            allowed_signers_path=allowed_signers,
            expected_arch="arm64",
            current_macos="26.5",
        )


def test_signed_manifest_is_verified_before_the_large_artifact_download(
    tmp_path: Path,
) -> None:
    module = load_module()
    manifest, _artifact, payload = write_candidate(
        tmp_path,
        release_id="1.0.0",
        channel="stable",
        local_qa=False,
    )
    signature, allowed_signers = sign_manifest(module, tmp_path, manifest)

    candidate = module.verify_manifest(
        manifest,
        signature_path=signature,
        allowed_signers_path=allowed_signers,
        expected_arch="arm64",
        current_macos="26.5",
    )

    assert candidate.payload["artifact"]["size"] == payload["artifact"]["size"]
    assert candidate.payload["artifact"]["uncompressed_size"] == payload["artifact"]["uncompressed_size"]


def test_publisher_signature_rejects_local_qa_channel_as_production(
    tmp_path: Path,
) -> None:
    module = load_module()
    manifest, artifact, _payload = write_candidate(tmp_path)
    signature, allowed_signers = sign_manifest(module, tmp_path, manifest)

    with pytest.raises(module.PayloadError, match="production manifest"):
        module.verify_candidate(
            manifest,
            artifact,
            signature_path=signature,
            allowed_signers_path=allowed_signers,
        )


@pytest.mark.parametrize(
    "channel,local_qa",
    [
        ("nightly", False),
        ("stable", True),
        ("local-qa", False),
    ],
)
def test_manifest_rejects_unknown_or_inconsistent_channel_policy(
    tmp_path: Path,
    channel: str,
    local_qa: bool,
) -> None:
    module = load_module()
    manifest, artifact, _payload = write_candidate(
        tmp_path,
        channel=channel,
        local_qa=local_qa,
    )

    with pytest.raises(module.PayloadError, match="channel"):
        module.verify_candidate(manifest, artifact, allow_unsigned_local_qa=True)


def test_manifest_rejects_unbounded_release_sequence(tmp_path: Path) -> None:
    module = load_module()
    manifest, artifact, _payload = write_candidate(tmp_path, sequence=1_000_000_000)

    with pytest.raises(module.PayloadError, match="sequence"):
        module.verify_candidate(manifest, artifact, allow_unsigned_local_qa=True)


def test_candidate_rejects_noncanonical_manifest_and_corrupt_archive(
    tmp_path: Path,
) -> None:
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


@pytest.mark.parametrize(
    "hostile_path", ["../escape", "/absolute", "a/../../escape", "a\\escape"]
)
def test_staging_rejects_hostile_archive_paths(
    tmp_path: Path, hostile_path: str
) -> None:
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
        verified = module.verify_candidate(
            manifest, artifact, allow_unsigned_local_qa=True
        )
        module.stage_candidate(verified, artifact, tmp_path / "install")

    assert not (tmp_path / "escape").exists()


def test_staging_rejects_symlinks_case_collisions_and_unlisted_files(
    tmp_path: Path,
) -> None:
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
        verified = module.verify_candidate(
            manifest, artifact, allow_unsigned_local_qa=True
        )
        module.stage_candidate(verified, artifact, install_root)

    extra_root = tmp_path / "extra"
    extra_root.mkdir()
    manifest, artifact, payload = write_candidate(
        extra_root, files={"safe.txt": b"safe"}
    )
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


def test_manifest_rejects_unicode_normalization_path_collisions(tmp_path: Path) -> None:
    module = load_module()
    manifest, artifact, _payload = write_candidate(
        tmp_path,
        files={"caf\u00e9.txt": b"one", "cafe\u0301.txt": b"two"},
    )

    with pytest.raises(module.PayloadError, match="case-insensitive path collision"):
        module.verify_candidate(manifest, artifact, allow_unsigned_local_qa=True)


@pytest.mark.parametrize(
    "files",
    [
        {"Data/one.txt": b"one", "data/two.txt": b"two"},
        {"caf\u00e9/one.txt": b"one", "cafe\u0301/two.txt": b"two"},
    ],
)
def test_manifest_rejects_case_or_unicode_collisions_in_parent_directories(
    tmp_path: Path,
    files: dict[str, bytes],
) -> None:
    module = load_module()
    manifest, artifact, _payload = write_candidate(tmp_path, files=files)

    with pytest.raises(module.PayloadError, match="case-insensitive path collision"):
        module.verify_candidate(manifest, artifact, allow_unsigned_local_qa=True)


def test_manifest_rejects_file_directory_path_conflicts(tmp_path: Path) -> None:
    module = load_module()
    manifest, artifact, _payload = write_candidate(
        tmp_path,
        files={"data": b"file", "data/nested.txt": b"nested"},
    )

    with pytest.raises(module.PayloadError, match="file/directory path conflict"):
        module.verify_candidate(manifest, artifact, allow_unsigned_local_qa=True)


def test_staged_files_are_read_only_while_manifest_modes_remain_logical(
    tmp_path: Path,
) -> None:
    module = load_module()
    manifest, artifact, _payload = write_candidate(tmp_path)
    verified = module.verify_candidate(manifest, artifact, allow_unsigned_local_qa=True)
    release = module.stage_candidate(verified, artifact, tmp_path / "install")

    assert stat.S_IMODE((release / "bin" / "viventium").stat().st_mode) == 0o555
    assert stat.S_IMODE((release / "app" / "version.txt").stat().st_mode) == 0o444
    assert stat.S_IMODE((release / ".viventium-manifest.json").stat().st_mode) == 0o444
    stored = json.loads(
        (release / ".viventium-manifest.json").read_text(encoding="utf-8")
    )
    assert {entry["mode"] for entry in stored["files"]} == {0o644, 0o755}
    assert module.stage_candidate(verified, artifact, tmp_path / "install") == release

    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["files"][0]["mode"] = 0o444
    manifest.write_bytes(module.canonical_manifest_bytes(payload))
    with pytest.raises(module.PayloadError, match="unsupported file mode"):
        module.verify_candidate(manifest, artifact, allow_unsigned_local_qa=True)


@pytest.mark.parametrize("hostile_child", ["releases", "staging", "state"])
def test_staging_rejects_symlinked_mutable_roots_without_touching_external_target(
    tmp_path: Path, hostile_child: str
) -> None:
    module = load_module()
    manifest, artifact, _payload = write_candidate(tmp_path)
    verified = module.verify_candidate(manifest, artifact, allow_unsigned_local_qa=True)
    install_root = tmp_path / "install"
    install_root.mkdir()
    external = tmp_path / "external"
    external.mkdir()
    sentinel = external / "sentinel.txt"
    sentinel.write_text("untouched\n", encoding="utf-8")
    (install_root / hostile_child).symlink_to(external, target_is_directory=True)

    with pytest.raises(module.PayloadError, match="unsafe"):
        module.stage_candidate(verified, artifact, install_root)

    assert sentinel.read_text(encoding="utf-8") == "untouched\n"
    assert sorted(path.name for path in external.iterdir()) == ["sentinel.txt"]


@pytest.mark.parametrize("hostile_file", ["install.lock", "journal.ndjson"])
def test_staging_rejects_symlinked_installer_files_without_writing_external_target(
    tmp_path: Path, hostile_file: str
) -> None:
    module = load_module()
    manifest, artifact, _payload = write_candidate(tmp_path)
    verified = module.verify_candidate(manifest, artifact, allow_unsigned_local_qa=True)
    install_root = tmp_path / "install"
    state_root = install_root / "state" / "native-installer"
    state_root.mkdir(parents=True)
    external = tmp_path / "external.txt"
    external.write_text("untouched\n", encoding="utf-8")
    (state_root / hostile_file).symlink_to(external)

    with pytest.raises(module.PayloadError, match="unsafe"):
        module.stage_candidate(verified, artifact, install_root)

    assert external.read_text(encoding="utf-8") == "untouched\n"


def test_stage_retry_finishes_release_interrupted_after_publish(
    tmp_path: Path, monkeypatch
) -> None:
    module = load_module()
    manifest, artifact, _payload = write_candidate(tmp_path)
    verified = module.verify_candidate(manifest, artifact, allow_unsigned_local_qa=True)
    install_root = tmp_path / "install"
    original_make_immutable = module._make_directories_immutable
    interrupted = False

    def interrupt_once(release_path: Path) -> None:
        nonlocal interrupted
        if not interrupted:
            interrupted = True
            raise KeyboardInterrupt("synthetic interruption after release publish")
        original_make_immutable(release_path)

    monkeypatch.setattr(module, "_make_directories_immutable", interrupt_once)
    with pytest.raises(KeyboardInterrupt, match="synthetic interruption"):
        module.stage_candidate(verified, artifact, install_root)

    release = install_root / "releases" / verified.release_key
    assert release.is_dir()
    assert stat.S_IMODE(release.stat().st_mode) == 0o700

    assert module.stage_candidate(verified, artifact, install_root) == release
    assert stat.S_IMODE(release.stat().st_mode) == 0o555
    assert not (
        install_root / "state" / "native-installer" / "pending-stage.json"
    ).exists()


def test_stage_cancel_before_publish_removes_owned_attempt_and_pending_state(
    tmp_path: Path, monkeypatch
) -> None:
    module = load_module()
    manifest, artifact, _payload = write_candidate(tmp_path)
    verified = module.verify_candidate(manifest, artifact, allow_unsigned_local_qa=True)
    install_root = tmp_path / "install"

    def interrupt_before_extraction(_candidate, _archive):
        raise KeyboardInterrupt("synthetic cancellation before extraction")

    monkeypatch.setattr(module, "_validate_zip", interrupt_before_extraction)
    with pytest.raises(KeyboardInterrupt, match="synthetic cancellation"):
        module.stage_candidate(verified, artifact, install_root)

    assert list((install_root / "staging").iterdir()) == []
    assert not (install_root / "releases" / verified.release_key).exists()
    assert not (
        install_root / "state" / "native-installer" / "pending-stage.json"
    ).exists()


def test_stage_retry_quarantines_tampered_incomplete_release_before_reextracting(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = load_module()
    manifest, artifact, _payload = write_candidate(tmp_path)
    verified = module.verify_candidate(manifest, artifact, allow_unsigned_local_qa=True)
    install_root = tmp_path / "install"
    original_make_immutable = module._make_directories_immutable
    interrupted = False

    def interrupt_once(release_path: Path) -> None:
        nonlocal interrupted
        if not interrupted:
            interrupted = True
            raise KeyboardInterrupt("synthetic interruption after release publish")
        original_make_immutable(release_path)

    monkeypatch.setattr(module, "_make_directories_immutable", interrupt_once)
    with pytest.raises(KeyboardInterrupt, match="synthetic interruption"):
        module.stage_candidate(verified, artifact, install_root)

    release = install_root / "releases" / verified.release_key
    tampered_file = release / "app" / "version.txt"
    tampered_file.chmod(0o644)
    tampered_file.write_bytes(b"tampered-but-same-size\n")

    assert module.stage_candidate(verified, artifact, install_root) == release
    assert (release / "app" / "version.txt").read_bytes() == b"0.4.0-qa.1\n"
    quarantined = list(
        (install_root / "staging").glob(f"quarantine-{verified.release_key}.*")
    )
    assert len(quarantined) == 1
    assert (
        quarantined[0] / "app" / "version.txt"
    ).read_bytes() == b"tampered-but-same-size\n"


@pytest.mark.parametrize("mutation", ["content", "unexpected"])
def test_activation_and_stage_reuse_reject_mutated_release_tree(
    tmp_path: Path,
    mutation: str,
) -> None:
    module = load_module()
    manifest, artifact, _payload = write_candidate(tmp_path)
    verified = module.verify_candidate(manifest, artifact, allow_unsigned_local_qa=True)
    install_root = tmp_path / "install"
    release = module.stage_candidate(verified, artifact, install_root)

    if mutation == "content":
        target = release / "app" / "version.txt"
        target.chmod(0o644)
        target.write_bytes(b"x" * target.stat().st_size)
        expected_error = "digest"
    else:
        release.chmod(0o755)
        (release / "unexpected.txt").write_text("unexpected\n", encoding="utf-8")
        expected_error = "unexpected"

    with pytest.raises(module.PayloadError, match=expected_error):
        module.stage_candidate(verified, artifact, install_root)
    with pytest.raises(module.PayloadError, match=expected_error):
        module.activate_candidate(
            verified, release, install_root, health_check=lambda _path: True
        )


def test_stage_reuse_rejects_broken_symlink_at_final_release_path(
    tmp_path: Path,
) -> None:
    module = load_module()
    manifest, artifact, _payload = write_candidate(tmp_path)
    verified = module.verify_candidate(manifest, artifact, allow_unsigned_local_qa=True)
    install_root = tmp_path / "install"
    release = module.stage_candidate(verified, artifact, install_root)
    preserved_release = release.with_name(f"{release.name}.preserved")
    release.rename(preserved_release)
    release.symlink_to("missing-release", target_is_directory=True)

    with pytest.raises(module.PayloadError, match="real directory"):
        module.stage_candidate(verified, artifact, install_root)

    assert release.is_symlink()
    assert preserved_release.is_dir()


def test_activation_is_atomic_journaled_and_rolls_back_failed_health(
    tmp_path: Path,
) -> None:
    module = load_module()
    install_root = tmp_path / "install"

    first_root = tmp_path / "first"
    first_root.mkdir()
    manifest, artifact, _payload = write_candidate(
        first_root, release_id="0.4.0-qa.1", sequence=1
    )
    first = module.verify_candidate(manifest, artifact, allow_unsigned_local_qa=True)
    first_release = module.stage_candidate(first, artifact, install_root)
    activated = module.activate_candidate(
        first, first_release, install_root, health_check=lambda _path: True
    )
    assert activated == first_release
    assert (install_root / "active").resolve() == first_release.resolve()
    assert not (install_root / "previous").exists()

    second_root = tmp_path / "second"
    second_root.mkdir()
    manifest, artifact, _payload = write_candidate(
        second_root, release_id="0.4.0-qa.2", sequence=2
    )
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


def test_activation_rolls_back_pointer_when_cancel_interrupts_health_check(tmp_path: Path) -> None:
    module = load_module()
    install_root = tmp_path / "install"
    first_root = tmp_path / "first"
    first_root.mkdir()
    manifest, artifact, _payload = write_candidate(
        first_root, release_id="0.4.0-cancel.1", sequence=1
    )
    first = module.verify_candidate(manifest, artifact, allow_unsigned_local_qa=True)
    first_release = module.stage_candidate(first, artifact, install_root)
    module.activate_candidate(first, first_release, install_root, health_check=lambda _path: True)

    second_root = tmp_path / "second"
    second_root.mkdir()
    manifest, artifact, _payload = write_candidate(
        second_root, release_id="0.4.0-cancel.2", sequence=2
    )
    second = module.verify_candidate(manifest, artifact, allow_unsigned_local_qa=True)
    second_release = module.stage_candidate(second, artifact, install_root)

    def interrupt(_path: Path) -> bool:
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        module.activate_candidate(second, second_release, install_root, health_check=interrupt)

    assert (install_root / "active").resolve() == first_release.resolve()
    assert not (install_root / "state" / "native-installer" / "pending-activation.json").exists()


def test_activation_cancel_after_pointer_switch_restores_prior_immediately(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = load_module()
    install_root = tmp_path / "install"

    first_root = tmp_path / "first"
    first_root.mkdir()
    manifest, artifact, _payload = write_candidate(
        first_root, release_id="0.4.0-qa.1", sequence=1
    )
    first = module.verify_candidate(manifest, artifact, allow_unsigned_local_qa=True)
    first_release = module.stage_candidate(first, artifact, install_root)
    module.activate_candidate(
        first, first_release, install_root, health_check=lambda _path: True
    )

    second_root = tmp_path / "second"
    second_root.mkdir()
    manifest, artifact, _payload = write_candidate(
        second_root, release_id="0.4.0-qa.2", sequence=2
    )
    second = module.verify_candidate(manifest, artifact, allow_unsigned_local_qa=True)
    second_release = module.stage_candidate(second, artifact, install_root)

    original_append_journal = module._append_journal
    interrupted = False
    health_calls = 0

    def interrupt_after_pointer_switch(root: Path, event: str, candidate) -> None:
        nonlocal interrupted
        original_append_journal(root, event, candidate)
        if event == "pointer_switched" and not interrupted:
            interrupted = True
            raise KeyboardInterrupt("synthetic interruption before health result")

    def health_was_not_reached(_path: Path) -> bool:
        nonlocal health_calls
        health_calls += 1
        return True

    monkeypatch.setattr(module, "_append_journal", interrupt_after_pointer_switch)
    with pytest.raises(KeyboardInterrupt, match="synthetic interruption"):
        module.activate_candidate(
            second,
            second_release,
            install_root,
            health_check=health_was_not_reached,
        )

    assert health_calls == 0
    assert (install_root / "active").resolve() == first_release.resolve()
    assert (install_root / "previous").resolve() == first_release.resolve()
    assert not (
        install_root / "state" / "native-installer" / "pending-activation.json"
    ).exists()

    with pytest.raises(module.PayloadError, match="health check failed"):
        module.activate_candidate(
            second,
            second_release,
            install_root,
            health_check=lambda _path: False,
        )

    assert (install_root / "active").resolve() == first_release.resolve()
    assert (install_root / "previous").resolve() == first_release.resolve()
    assert not (
        install_root / "state" / "native-installer" / "pending-activation.json"
    ).exists()
    records = [
        json.loads(line)
        for line in (install_root / "state" / "native-installer" / "journal.ndjson")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert "health_failed_rollback_complete" in [
        record["event"] for record in records
    ]


def test_activation_retry_restores_prior_before_rejecting_damaged_candidate(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = load_module()
    install_root = tmp_path / "install"

    first_root = tmp_path / "first"
    first_root.mkdir()
    manifest, artifact, _payload = write_candidate(
        first_root, release_id="0.4.0-qa.1", sequence=1
    )
    first = module.verify_candidate(manifest, artifact, allow_unsigned_local_qa=True)
    first_release = module.stage_candidate(first, artifact, install_root)
    module.activate_candidate(
        first, first_release, install_root, health_check=lambda _path: True
    )

    second_root = tmp_path / "second"
    second_root.mkdir()
    manifest, artifact, _payload = write_candidate(
        second_root, release_id="0.4.0-qa.2", sequence=2
    )
    second = module.verify_candidate(manifest, artifact, allow_unsigned_local_qa=True)
    second_release = module.stage_candidate(second, artifact, install_root)

    original_append_journal = module._append_journal
    interrupted = False

    def interrupt_after_pointer_switch(root: Path, event: str, candidate) -> None:
        nonlocal interrupted
        original_append_journal(root, event, candidate)
        if event == "pointer_switched" and not interrupted:
            interrupted = True
            raise KeyboardInterrupt("synthetic interruption before health result")

    monkeypatch.setattr(module, "_append_journal", interrupt_after_pointer_switch)
    with pytest.raises(KeyboardInterrupt, match="synthetic interruption"):
        module.activate_candidate(
            second,
            second_release,
            install_root,
            health_check=lambda _path: True,
        )

    damaged_file = second_release / "app" / "version.txt"
    damaged_file.chmod(0o644)
    damaged_file.write_bytes(b"damaged\n")
    with pytest.raises(module.PayloadError, match="digest|size"):
        module.activate_candidate(
            second,
            second_release,
            install_root,
            health_check=lambda _path: True,
        )

    assert (install_root / "active").resolve() == first_release.resolve()
    assert not (
        install_root / "state" / "native-installer" / "pending-activation.json"
    ).exists()


def test_activation_retry_finishes_durable_health_pass_without_replacing_previous(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = load_module()
    install_root = tmp_path / "install"

    first_root = tmp_path / "first"
    first_root.mkdir()
    manifest, artifact, _payload = write_candidate(
        first_root, release_id="0.4.0-qa.1", sequence=1
    )
    first = module.verify_candidate(manifest, artifact, allow_unsigned_local_qa=True)
    first_release = module.stage_candidate(first, artifact, install_root)
    module.activate_candidate(
        first, first_release, install_root, health_check=lambda _path: True
    )

    second_root = tmp_path / "second"
    second_root.mkdir()
    manifest, artifact, _payload = write_candidate(
        second_root, release_id="0.4.0-qa.2", sequence=2
    )
    second = module.verify_candidate(manifest, artifact, allow_unsigned_local_qa=True)
    second_release = module.stage_candidate(second, artifact, install_root)

    original_append_journal = module._append_journal
    interrupted = False

    def interrupt_after_health_pass(root: Path, event: str, candidate) -> None:
        nonlocal interrupted
        original_append_journal(root, event, candidate)
        if event == "health_passed_activation_complete" and not interrupted:
            interrupted = True
            raise KeyboardInterrupt(
                "synthetic interruption after durable health result"
            )

    monkeypatch.setattr(module, "_append_journal", interrupt_after_health_pass)
    with pytest.raises(KeyboardInterrupt, match="synthetic interruption"):
        module.activate_candidate(
            second,
            second_release,
            install_root,
            health_check=lambda _path: True,
        )

    assert (install_root / "active").resolve() == second_release.resolve()
    assert (install_root / "previous").resolve() == first_release.resolve()

    def health_must_not_repeat(_path: Path) -> bool:
        raise AssertionError("durably successful activation reran its health check")

    assert (
        module.activate_candidate(
            second,
            second_release,
            install_root,
            health_check=health_must_not_repeat,
        )
        == second_release
    )
    assert (install_root / "active").resolve() == second_release.resolve()
    assert (install_root / "previous").resolve() == first_release.resolve()
    assert not (
        install_root / "state" / "native-installer" / "pending-activation.json"
    ).exists()


def test_reactivating_active_candidate_is_idempotent_and_preserves_previous(
    tmp_path: Path,
) -> None:
    module = load_module()
    install_root = tmp_path / "install"

    first_root = tmp_path / "first"
    first_root.mkdir()
    manifest, artifact, _payload = write_candidate(
        first_root, release_id="0.4.0-qa.1", sequence=1
    )
    first = module.verify_candidate(manifest, artifact, allow_unsigned_local_qa=True)
    first_release = module.stage_candidate(first, artifact, install_root)
    module.activate_candidate(
        first, first_release, install_root, health_check=lambda _path: True
    )

    second_root = tmp_path / "second"
    second_root.mkdir()
    manifest, artifact, _payload = write_candidate(
        second_root, release_id="0.4.0-qa.2", sequence=2
    )
    second = module.verify_candidate(manifest, artifact, allow_unsigned_local_qa=True)
    second_release = module.stage_candidate(second, artifact, install_root)
    module.activate_candidate(
        second, second_release, install_root, health_check=lambda _path: True
    )

    def health_must_not_repeat(_path: Path) -> bool:
        raise AssertionError("already-active candidate reran its health check")

    assert (
        module.activate_candidate(
            second,
            second_release,
            install_root,
            health_check=health_must_not_repeat,
        )
        == second_release
    )
    assert (install_root / "active").resolve() == second_release.resolve()
    assert (install_root / "previous").resolve() == first_release.resolve()


def test_replay_and_incompatible_data_schema_fail_before_activation(
    tmp_path: Path,
) -> None:
    module = load_module()
    install_root = tmp_path / "install"
    state_root = install_root / "state" / "native-installer"
    state_root.mkdir(parents=True)
    (state_root / "highest-sequence").write_text("5\n", encoding="utf-8")
    manifest, artifact, _payload = write_candidate(tmp_path, sequence=4)
    verified = module.verify_candidate(manifest, artifact, allow_unsigned_local_qa=True)
    release = module.stage_candidate(verified, artifact, install_root)

    with pytest.raises(module.PayloadError, match="replayed or downgraded"):
        module.activate_candidate(
            verified, release, install_root, health_check=lambda _path: True
        )

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


def test_equal_sequence_allows_identical_retry_and_rejects_different_manifest(
    tmp_path: Path,
) -> None:
    module = load_module()
    install_root = tmp_path / "install"

    first_root = tmp_path / "first"
    first_root.mkdir()
    manifest, artifact, _payload = write_candidate(first_root, sequence=7)
    first = module.verify_candidate(manifest, artifact, allow_unsigned_local_qa=True)
    first_release = module.stage_candidate(first, artifact, install_root)

    with pytest.raises(module.PayloadError, match="health check failed"):
        module.activate_candidate(
            first, first_release, install_root, health_check=lambda _path: False
        )
    assert (
        module.activate_candidate(
            first,
            first_release,
            install_root,
            health_check=lambda _path: True,
        )
        == first_release
    )

    fork_root = tmp_path / "fork"
    fork_root.mkdir()
    manifest, artifact, _payload = write_candidate(
        fork_root,
        release_id="0.4.0-qa.fork",
        sequence=7,
    )
    fork = module.verify_candidate(manifest, artifact, allow_unsigned_local_qa=True)
    fork_release = module.stage_candidate(fork, artifact, install_root)
    with pytest.raises(module.PayloadError, match="different manifest"):
        module.activate_candidate(
            fork, fork_release, install_root, health_check=lambda _path: True
        )

    assert (install_root / "active").resolve() == first_release.resolve()


def test_atomic_state_and_pointer_updates_fsync_containing_directories(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_module()
    synced: list[Path] = []
    monkeypatch.setattr(
        module, "_fsync_directory", lambda path: synced.append(Path(path))
    )

    state_path = tmp_path / "state" / "highest-sequence"
    module._atomic_text(state_path, "1\n")
    target = tmp_path / "releases" / "release-1"
    target.mkdir(parents=True)
    pointer = tmp_path / "active"
    module._atomic_pointer(pointer, target)
    module._atomic_pointer(pointer, None)

    assert synced == [state_path.parent, tmp_path, tmp_path]


def test_install_lock_fsyncs_transaction_state_hierarchy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_module()
    synced: list[Path] = []
    monkeypatch.setattr(
        module, "_fsync_directory", lambda path: synced.append(Path(path))
    )
    install_root = tmp_path / "install"

    with module._exclusive_install_lock(install_root):
        pass

    state_root = install_root / "state" / "native-installer"
    assert synced == [state_root, state_root.parent, install_root, tmp_path]


def test_staging_uses_install_lock_and_rejects_symlinked_transaction_state(
    tmp_path: Path,
) -> None:
    module = load_module()
    manifest, artifact, _payload = write_candidate(tmp_path)
    verified = module.verify_candidate(manifest, artifact, allow_unsigned_local_qa=True)
    install_root = tmp_path / "install"

    with module._exclusive_install_lock(install_root):
        with pytest.raises(module.PayloadError, match="transaction is active"):
            module.stage_candidate(verified, artifact, install_root)

    symlink_install_root = tmp_path / "symlink-install"
    symlink_install_root.mkdir()
    external_state = tmp_path / "external-state"
    external_state.mkdir()
    state_parent = symlink_install_root / "state"
    state_parent.symlink_to(external_state, target_is_directory=True)
    with pytest.raises(module.PayloadError, match="state root is unsafe"):
        module.stage_candidate(verified, artifact, symlink_install_root)
    assert not (external_state / "native-installer").exists()


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


def test_staging_refuses_low_disk_before_creating_an_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()
    manifest, artifact, _payload = write_candidate(
        tmp_path, files={"payload.bin": b"x" * 4096}
    )
    verified = module.verify_candidate(
        manifest, artifact, allow_unsigned_local_qa=True
    )
    install_root = tmp_path / "install"

    usage = type(
        "Usage",
        (),
        {
            "total": 1 << 40,
            "used": 1,
            "free": verified.payload["artifact"]["uncompressed_size"]
            + module.MIN_FREE_RESERVE_BYTES
            - 1,
        },
    )()
    monkeypatch.setattr(module.shutil, "disk_usage", lambda _path: usage)

    with pytest.raises(module.PayloadError, match="free disk space"):
        module.stage_candidate(verified, artifact, install_root)

    assert not (install_root / "staging").exists()
    assert not (install_root / "releases").exists()


def test_retention_keeps_only_active_and_previous_verified_releases(tmp_path: Path) -> None:
    module = load_module()
    install_root = tmp_path / "install"
    releases: list[Path] = []

    for sequence in range(1, 4):
        candidate_root = tmp_path / f"candidate-{sequence}"
        candidate_root.mkdir()
        manifest, artifact, _payload = write_candidate(
            candidate_root,
            release_id=f"0.4.0-qa.{sequence}",
            sequence=sequence,
        )
        candidate = module.verify_candidate(
            manifest, artifact, allow_unsigned_local_qa=True
        )
        release = module.stage_candidate(candidate, artifact, install_root)
        module.activate_candidate(
            candidate, release, install_root, health_check=lambda _path: True
        )
        releases.append(release)

    module.prune_install_storage(install_root)

    assert not releases[0].exists()
    assert releases[1].is_dir()
    assert releases[2].is_dir()
    assert (install_root / "active").resolve() == releases[2].resolve()
    assert (install_root / "previous").resolve() == releases[1].resolve()


def test_retention_never_follows_an_unowned_release_symlink(tmp_path: Path) -> None:
    module = load_module()
    install_root = tmp_path / "install"
    releases_root = install_root / "releases"
    staging_root = install_root / "staging"
    releases_root.mkdir(parents=True)
    staging_root.mkdir()
    external = tmp_path / "personal"
    external.mkdir()
    sentinel = external / "keep.txt"
    sentinel.write_text("keep\n", encoding="utf-8")
    (releases_root / "foreign").symlink_to(external, target_is_directory=True)

    with pytest.raises(module.PayloadError, match="unsafe release entry"):
        module.prune_install_storage(install_root)

    assert sentinel.read_text(encoding="utf-8") == "keep\n"
    assert external.is_dir()

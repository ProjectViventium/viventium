from __future__ import annotations

import gzip
import importlib.util
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "viventium" / "personal_account_qa_recovery.py"
SPEC = importlib.util.spec_from_file_location("personal_account_qa_recovery", MODULE_PATH)
assert SPEC and SPEC.loader
recovery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recovery)

OWNER_ID = "owner_0123456789abcdef"
HEX_A = "a" * 64
HEX_B = "b" * 64
PREIMAGE = {
    "kind": "schedule",
    "ownerId": OWNER_ID,
    "resourceId": "schedule-1",
    "revision": 0,
    "updatedAt": "2026-08-25T15:00:00.000Z",
    "payload": {"active": False, "prompt": "synthetic fixture only"},
}
PREIMAGE_STATE_SHA256 = recovery.cleanup_state_sha256(PREIMAGE)
RESOURCE_ID_HASH = "sha256:" + recovery.sha256_bytes(b"schedule-1")
REVIEW_BINDING_SHA256 = HEX_A
REVIEW_SET_SHA256 = recovery.sha256_value(
    [
        {
            "kind": "schedule",
            "resourceIdHash": RESOURCE_ID_HASH,
            "stateSha256": PREIMAGE_STATE_SHA256,
            "reviewBindingSha256": REVIEW_BINDING_SHA256,
        }
    ]
)


def write_source_bundle(root: Path) -> None:
    root.mkdir(mode=0o700)
    (root / "mongo.archive.gz").write_bytes(gzip.compress(b"synthetic-owner-mongo-archive"))

    connection = sqlite3.connect(root / "schedules.db")
    connection.execute(
        "CREATE TABLE scheduled_tasks ("
        "id TEXT PRIMARY KEY, user_id TEXT NOT NULL, prompt TEXT, "
        "updated_at TEXT NOT NULL, cleanup_revision INTEGER NOT NULL DEFAULT 0)"
    )
    connection.execute(
        "INSERT INTO scheduled_tasks "
        "(id, user_id, prompt, updated_at, cleanup_revision) VALUES (?, ?, ?, ?, ?)",
        (
            "schedule-1",
            OWNER_ID,
            "synthetic private preimage",
            PREIMAGE["updatedAt"],
            PREIMAGE["revision"],
        ),
    )
    connection.commit()
    connection.close()

    preimages = {
        "contractVersion": 1,
        "ownerScopeHash": recovery.owner_scope_hash(OWNER_ID),
        "reviewSetSha256": REVIEW_SET_SHA256,
        "items": [
            {
                "kind": "schedule",
                "resourceIdHash": RESOURCE_ID_HASH,
                "stateSha256": PREIMAGE_STATE_SHA256,
                "reviewBindingSha256": REVIEW_BINDING_SHA256,
                "preimage": PREIMAGE,
            }
        ],
    }
    (root / "item-preimages.json").write_text(
        json.dumps(preimages, sort_keys=True), encoding="utf-8"
    )
    for path in root.iterdir():
        path.chmod(0o600)


def verified_mongo_restore(
    kind: str,
    artifact: Path,
    owner_scope_hash: str,
    review_set_sha256: str = REVIEW_SET_SHA256,
    target_bindings: tuple[dict[str, object], ...] = (),
) -> dict[str, object]:
    assert kind == "mongo_archive"
    assert gzip.decompress(artifact.read_bytes()) == b"synthetic-owner-mongo-archive"
    mongo_targets = [target for target in target_bindings if target["kind"] != "schedule"]
    return {
        "status": "verified",
        "ownerScopeHash": owner_scope_hash,
        "recordCount": 3,
        "restoredStateSha256": HEX_B,
        "method": "isolated_namespace_restore_and_compare",
        "reviewSetSha256": review_set_sha256,
        "exactTargetCount": len(mongo_targets),
        "targetSetSha256": recovery.restore_target_set_sha256(mongo_targets),
    }


def fixed_now() -> datetime:
    return datetime(2026, 8, 25, 16, 0, 0, tzinfo=timezone.utc)


def test_cleanup_state_hash_has_a_cross_runtime_unicode_and_number_vector() -> None:
    state = {
        "kind": "message",
        "ownerId": "owner-1",
        "resourceId": "message-1",
        "revision": 3,
        "updatedAt": "2026-08-25T15:00:00.000Z",
        "payload": {
            "text": "café 🐝",
            "scores": [1, 1.5, 0.000001, 9007199254740992],
            "ok": True,
            "none": None,
        },
    }

    assert recovery.cleanup_state_sha256(state) == (
        "3b4ca5e0525dc422efcedeabcca98b49fd1650fe47d57251bb5e360be490d63e"
    )


def test_creates_private_owner_bound_atomic_recovery_bundle(tmp_path: Path) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "private-backups"
    write_source_bundle(source)

    receipt = recovery.create_recovery_bundle(
        source_root=source,
        destination_root=destination,
        owner_id=OWNER_ID,
        review_set_sha256=REVIEW_SET_SHA256,
        public_roots=[REPO_ROOT],
        mongo_restore_verifier=verified_mongo_restore,
        now=fixed_now,
    )

    bundle = destination / receipt["backupId"]
    manifest = json.loads((bundle / "recoverable-manifest.json").read_text(encoding="utf-8"))
    assert receipt["status"] == "verified"
    assert receipt["ownerScopeHash"] == recovery.owner_scope_hash(OWNER_ID)
    assert receipt["restoreVerification"] == "verified"
    assert receipt["receiptSha256"] == recovery.sha256_value(
        {key: value for key, value in receipt.items() if key != "receiptSha256"}
    )
    assert manifest["ownerScopeHash"] == receipt["ownerScopeHash"]
    assert OWNER_ID not in json.dumps(manifest)
    assert manifest["reviewSetSha256"] == REVIEW_SET_SHA256
    assert manifest["immutablePublication"] is True
    assert {artifact["kind"] for artifact in manifest["artifacts"]} == {
        "mongo_archive",
        "scheduler_snapshot",
        "item_preimages",
    }
    assert recovery.verify_recovery_bundle(
        bundle,
        owner_id=OWNER_ID,
        review_set_sha256=REVIEW_SET_SHA256,
        public_roots=[REPO_ROOT],
    )["status"] == "verified"
    assert oct(bundle.stat().st_mode & 0o777) == "0o500"
    assert all(oct(path.stat().st_mode & 0o777) == "0o400" for path in bundle.iterdir())
    assert not any(path.name.startswith(".staging-") for path in destination.iterdir())


def test_publication_renames_a_traversable_staging_directory_before_sealing_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "private-backups"
    write_source_bundle(source)
    observed_modes: list[int] = []
    real_rename = recovery.os.rename

    def inspect_rename(source_path: Path, destination_path: Path) -> None:
        observed_modes.append(Path(source_path).stat().st_mode & 0o777)
        real_rename(source_path, destination_path)

    monkeypatch.setattr(recovery.os, "rename", inspect_rename)

    receipt = recovery.create_recovery_bundle(
        source_root=source,
        destination_root=destination,
        owner_id=OWNER_ID,
        review_set_sha256=REVIEW_SET_SHA256,
        public_roots=[REPO_ROOT],
        mongo_restore_verifier=verified_mongo_restore,
        now=fixed_now,
    )

    bundle = destination / str(receipt["backupId"])
    assert observed_modes == [0o700]
    assert bundle.stat().st_mode & 0o777 == 0o500


def test_publication_failure_after_rename_removes_the_incomplete_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "private-backups"
    write_source_bundle(source)
    real_open = recovery.os.open

    failed = False

    def fail_destination_fsync_open(
        path: object, flags: int, *args: object, **kwargs: object
    ) -> int:
        nonlocal failed
        if Path(path) == destination and not failed and kwargs.get("dir_fd") is None:
            failed = True
            raise OSError("synthetic directory fsync failure")
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(recovery.os, "open", fail_destination_fsync_open)

    with pytest.raises(OSError, match="synthetic directory fsync failure"):
        recovery.create_recovery_bundle(
            source_root=source,
            destination_root=destination,
            owner_id=OWNER_ID,
            review_set_sha256=REVIEW_SET_SHA256,
            public_roots=[REPO_ROOT],
            mongo_restore_verifier=verified_mongo_restore,
            now=fixed_now,
        )

    assert destination.is_dir()
    assert list(destination.iterdir()) == []


def test_rejects_destination_inside_public_repository(tmp_path: Path) -> None:
    source = tmp_path / "source"
    write_source_bundle(source)

    with pytest.raises(ValueError, match="backup_destination_inside_public_root"):
        recovery.create_recovery_bundle(
            source_root=source,
            destination_root=REPO_ROOT / ".private-backup-test",
            owner_id=OWNER_ID,
            review_set_sha256=REVIEW_SET_SHA256,
            public_roots=[REPO_ROOT],
            mongo_restore_verifier=verified_mongo_restore,
            now=fixed_now,
        )


def test_rejects_owner_mismatched_preimages_before_publication(tmp_path: Path) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "private-backups"
    write_source_bundle(source)
    payload = json.loads((source / "item-preimages.json").read_text(encoding="utf-8"))
    payload["ownerScopeHash"] = "sha256:" + HEX_B
    (source / "item-preimages.json").write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="preimages_owner_mismatch"):
        recovery.create_recovery_bundle(
            source_root=source,
            destination_root=destination,
            owner_id=OWNER_ID,
            review_set_sha256=REVIEW_SET_SHA256,
            public_roots=[REPO_ROOT],
            mongo_restore_verifier=verified_mongo_restore,
            now=fixed_now,
        )

    assert not destination.exists() or list(destination.iterdir()) == []


def test_rejects_unverified_mongo_restore(tmp_path: Path) -> None:
    source = tmp_path / "source"
    write_source_bundle(source)

    def failed_restore(
        _kind: str,
        _artifact: Path,
        _owner_scope_hash: str,
        _review_set_sha256: str,
        _target_bindings: tuple[dict[str, object], ...],
    ) -> dict[str, object]:
        return {"status": "failed"}

    with pytest.raises(ValueError, match="mongo_restore_not_verified"):
        recovery.create_recovery_bundle(
            source_root=source,
            destination_root=tmp_path / "private-backups",
            owner_id=OWNER_ID,
            review_set_sha256=REVIEW_SET_SHA256,
            public_roots=[REPO_ROOT],
            mongo_restore_verifier=failed_restore,
            now=fixed_now,
        )


def test_rejects_mongo_restore_for_a_different_review_set(tmp_path: Path) -> None:
    source = tmp_path / "source"
    write_source_bundle(source)

    def wrong_binding(*args) -> dict[str, object]:
        receipt = verified_mongo_restore(*args)
        receipt["reviewSetSha256"] = HEX_B
        return receipt

    with pytest.raises(ValueError, match="mongo_restore_review_set_mismatch"):
        recovery.create_recovery_bundle(
            source_root=source,
            destination_root=tmp_path / "private-backups",
            owner_id=OWNER_ID,
            review_set_sha256=REVIEW_SET_SHA256,
            public_roots=[REPO_ROOT],
            mongo_restore_verifier=wrong_binding,
            now=fixed_now,
        )


def test_rejects_scheduler_snapshot_missing_the_reviewed_target(tmp_path: Path) -> None:
    source = tmp_path / "source"
    write_source_bundle(source)
    with sqlite3.connect(source / "schedules.db") as connection:
        connection.execute("DELETE FROM scheduled_tasks WHERE id = ?", ("schedule-1",))

    with pytest.raises(ValueError, match="scheduler_restore_target_missing"):
        recovery.create_recovery_bundle(
            source_root=source,
            destination_root=tmp_path / "private-backups",
            owner_id=OWNER_ID,
            review_set_sha256=REVIEW_SET_SHA256,
            public_roots=[REPO_ROOT],
            mongo_restore_verifier=verified_mongo_restore,
            now=fixed_now,
        )


def test_tampered_artifact_fails_restore_verification(tmp_path: Path) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "private-backups"
    write_source_bundle(source)
    receipt = recovery.create_recovery_bundle(
        source_root=source,
        destination_root=destination,
        owner_id=OWNER_ID,
        review_set_sha256=REVIEW_SET_SHA256,
        public_roots=[REPO_ROOT],
        mongo_restore_verifier=verified_mongo_restore,
        now=fixed_now,
    )
    bundle = destination / receipt["backupId"]
    artifact = bundle / "mongo.archive.gz"
    artifact.chmod(0o600)
    artifact.write_bytes(gzip.compress(b"tampered"))
    artifact.chmod(0o400)

    with pytest.raises(ValueError, match="artifact_sha256_mismatch"):
        recovery.verify_recovery_bundle(
            bundle,
            owner_id=OWNER_ID,
            review_set_sha256=REVIEW_SET_SHA256,
            public_roots=[REPO_ROOT],
        )


def test_existing_bundle_is_never_overwritten(tmp_path: Path) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "private-backups"
    write_source_bundle(source)
    receipt = recovery.create_recovery_bundle(
        source_root=source,
        destination_root=destination,
        owner_id=OWNER_ID,
        review_set_sha256=REVIEW_SET_SHA256,
        public_roots=[REPO_ROOT],
        mongo_restore_verifier=verified_mongo_restore,
        now=fixed_now,
    )
    manifest = destination / receipt["backupId"] / "recoverable-manifest.json"
    before = manifest.read_bytes()

    with pytest.raises(FileExistsError):
        recovery.create_recovery_bundle(
            source_root=source,
            destination_root=destination,
            owner_id=OWNER_ID,
            review_set_sha256=REVIEW_SET_SHA256,
            public_roots=[REPO_ROOT],
            mongo_restore_verifier=verified_mongo_restore,
            now=fixed_now,
        )

    assert manifest.read_bytes() == before


def test_source_symlinks_are_rejected(tmp_path: Path) -> None:
    source = tmp_path / "source"
    write_source_bundle(source)
    original = source / "mongo.archive.gz"
    outside = tmp_path / "outside.gz"
    outside.write_bytes(original.read_bytes())
    original.unlink()
    original.symlink_to(outside)

    with pytest.raises(ValueError, match="source_artifact_not_regular"):
        recovery.create_recovery_bundle(
            source_root=source,
            destination_root=tmp_path / "private-backups",
            owner_id=OWNER_ID,
            review_set_sha256=REVIEW_SET_SHA256,
            public_roots=[REPO_ROOT],
            mongo_restore_verifier=verified_mongo_restore,
            now=fixed_now,
        )


def test_source_root_symlink_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "source"
    write_source_bundle(source)
    linked_source = tmp_path / "linked-source"
    linked_source.symlink_to(source, target_is_directory=True)

    with pytest.raises(ValueError, match="source_bundle_symlink"):
        recovery.create_recovery_bundle(
            source_root=linked_source,
            destination_root=tmp_path / "private-backups",
            owner_id=OWNER_ID,
            review_set_sha256=REVIEW_SET_SHA256,
            public_roots=[REPO_ROOT],
            mongo_restore_verifier=verified_mongo_restore,
            now=fixed_now,
        )


def test_destination_symlink_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "source"
    write_source_bundle(source)
    destination_target = tmp_path / "destination-target"
    destination_target.mkdir(mode=0o700)
    destination_link = tmp_path / "destination-link"
    destination_link.symlink_to(destination_target, target_is_directory=True)

    with pytest.raises(ValueError, match="backup_destination_symlink"):
        recovery.create_recovery_bundle(
            source_root=source,
            destination_root=destination_link,
            owner_id=OWNER_ID,
            review_set_sha256=REVIEW_SET_SHA256,
            public_roots=[REPO_ROOT],
            mongo_restore_verifier=verified_mongo_restore,
            now=fixed_now,
        )


def test_source_artifacts_must_be_owner_only(tmp_path: Path) -> None:
    source = tmp_path / "source"
    write_source_bundle(source)
    (source / "item-preimages.json").chmod(0o644)

    with pytest.raises(ValueError, match="source_artifact_permissions_not_private"):
        recovery.create_recovery_bundle(
            source_root=source,
            destination_root=tmp_path / "private-backups",
            owner_id=OWNER_ID,
            review_set_sha256=REVIEW_SET_SHA256,
            public_roots=[REPO_ROOT],
            mongo_restore_verifier=verified_mongo_restore,
            now=fixed_now,
        )


def test_bundle_symlink_and_loose_manifest_permissions_are_rejected(tmp_path: Path) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "private-backups"
    write_source_bundle(source)
    receipt = recovery.create_recovery_bundle(
        source_root=source,
        destination_root=destination,
        owner_id=OWNER_ID,
        review_set_sha256=REVIEW_SET_SHA256,
        public_roots=[REPO_ROOT],
        mongo_restore_verifier=verified_mongo_restore,
        now=fixed_now,
    )
    bundle = destination / receipt["backupId"]
    linked_bundle = tmp_path / "linked-bundle"
    linked_bundle.symlink_to(bundle, target_is_directory=True)

    with pytest.raises(ValueError, match="backup_bundle_symlink"):
        recovery.verify_recovery_bundle(
            linked_bundle,
            owner_id=OWNER_ID,
            review_set_sha256=REVIEW_SET_SHA256,
            public_roots=[REPO_ROOT],
        )

    manifest = bundle / "recoverable-manifest.json"
    manifest.chmod(0o644)
    with pytest.raises(ValueError, match="backup_manifest_permissions_not_private"):
        recovery.verify_recovery_bundle(
            bundle,
            owner_id=OWNER_ID,
            review_set_sha256=REVIEW_SET_SHA256,
            public_roots=[REPO_ROOT],
        )


def test_bundle_receipt_is_public_safe(tmp_path: Path) -> None:
    source = tmp_path / "source"
    write_source_bundle(source)
    receipt = recovery.create_recovery_bundle(
        source_root=source,
        destination_root=tmp_path / "private-backups",
        owner_id=OWNER_ID,
        review_set_sha256=REVIEW_SET_SHA256,
        public_roots=[REPO_ROOT],
        mongo_restore_verifier=verified_mongo_restore,
        now=fixed_now,
    )

    serialized = json.dumps(receipt)
    assert OWNER_ID not in serialized
    assert str(tmp_path) not in serialized
    assert "synthetic private preimage" not in serialized
    assert set(receipt) == {
        "contractVersion",
        "backupId",
        "ownerScopeHash",
        "reviewSetSha256",
        "manifestSha256",
        "artifactSetSha256",
        "restoreVerification",
        "status",
        "createdAt",
        "receiptSha256",
    }


def test_rejects_preimage_content_that_does_not_match_reviewed_state(tmp_path: Path) -> None:
    source = tmp_path / "source"
    write_source_bundle(source)
    payload = json.loads((source / "item-preimages.json").read_text(encoding="utf-8"))
    payload["items"][0]["preimage"] = {"private": "changed after review"}
    (source / "item-preimages.json").write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="preimage_state_mismatch"):
        recovery.create_recovery_bundle(
            source_root=source,
            destination_root=tmp_path / "private-backups",
            owner_id=OWNER_ID,
            review_set_sha256=REVIEW_SET_SHA256,
            public_roots=[REPO_ROOT],
            mongo_restore_verifier=verified_mongo_restore,
            now=fixed_now,
        )


def test_rejects_preimage_whose_embedded_owner_does_not_match_bundle_owner(tmp_path: Path) -> None:
    source = tmp_path / "source"
    write_source_bundle(source)
    payload = json.loads((source / "item-preimages.json").read_text(encoding="utf-8"))
    payload["items"][0]["preimage"]["ownerId"] = "other-owner"
    payload["items"][0]["stateSha256"] = recovery.cleanup_state_sha256(
        payload["items"][0]["preimage"]
    )
    payload["reviewSetSha256"] = recovery.sha256_value(
        [
            {
                "kind": payload["items"][0]["kind"],
                "resourceIdHash": payload["items"][0]["resourceIdHash"],
                "stateSha256": payload["items"][0]["stateSha256"],
                "reviewBindingSha256": payload["items"][0]["reviewBindingSha256"],
            }
        ]
    )
    (source / "item-preimages.json").write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="preimage_owner_mismatch"):
        recovery.create_recovery_bundle(
            source_root=source,
            destination_root=tmp_path / "private-backups",
            owner_id=OWNER_ID,
            review_set_sha256=payload["reviewSetSha256"],
            public_roots=[REPO_ROOT],
            mongo_restore_verifier=verified_mongo_restore,
            now=fixed_now,
        )


def test_rejects_preimage_set_that_does_not_match_reviewed_targets(tmp_path: Path) -> None:
    source = tmp_path / "source"
    write_source_bundle(source)
    payload = json.loads((source / "item-preimages.json").read_text(encoding="utf-8"))
    payload["items"][0]["reviewBindingSha256"] = "c" * 64
    (source / "item-preimages.json").write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="preimages_review_set_mismatch"):
        recovery.create_recovery_bundle(
            source_root=source,
            destination_root=tmp_path / "private-backups",
            owner_id=OWNER_ID,
            review_set_sha256=REVIEW_SET_SHA256,
            public_roots=[REPO_ROOT],
            mongo_restore_verifier=verified_mongo_restore,
            now=fixed_now,
        )


@pytest.mark.parametrize("owner_id", ["*", "all", "../owner", "owner with spaces"])
def test_recovery_rejects_unsafe_owner_ids(tmp_path: Path, owner_id: str) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "private-backups"
    write_source_bundle(source)

    with pytest.raises(ValueError, match="owner_id_invalid"):
        recovery.create_recovery_bundle(
            source_root=source,
            destination_root=destination,
            owner_id=owner_id,
            review_set_sha256=REVIEW_SET_SHA256,
            public_roots=[REPO_ROOT],
            mongo_restore_verifier=verified_mongo_restore,
            now=fixed_now,
        )

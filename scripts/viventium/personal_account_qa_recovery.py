#!/usr/bin/env python3
"""Create and verify a private recovery bundle for reviewed synthetic-QA cleanup.

The module never reads a live account or database. An operator must first capture the exact
owner-scoped artifacts into a private source directory. This module validates those artifacts,
performs restore-oriented checks, and atomically publishes an owner-bound, read-only bundle
outside public repositories. Cleanup execution is intentionally out of scope.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import shutil
import sqlite3
import stat
import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable


CONTRACT_VERSION = 1
HEX_256 = re.compile(r"[0-9a-f]{64}")
SAFE_BACKUP_ID = re.compile(r"backup-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{12}")
SAFE_OPAQUE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,159}")
MANIFEST_NAME = "recoverable-manifest.json"
SOURCE_ARTIFACTS = (
    ("mongo_archive", "mongo.archive.gz"),
    ("scheduler_snapshot", "schedules.db"),
    ("item_preimages", "item-preimages.json"),
)

MongoRestoreVerifier = Callable[
    [str, Path, str, str, tuple[dict[str, object], ...]], dict[str, object]
]
STATE_HASH_PREFIX = "viventium.cleanup.state.v1|"
MAX_SAFE_INTEGER = (1 << 53) - 1


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_value(value: object) -> str:
    return sha256_bytes(canonical_json(value).encode("utf-8"))


def _encode_cleanup_state(value: object) -> str:
    """Encode JSON data identically in Python and JavaScript before hashing."""

    if value is None:
        return "n;"
    if isinstance(value, bool):
        return "b1;" if value else "b0;"
    if isinstance(value, int):
        if -MAX_SAFE_INTEGER <= value <= MAX_SAFE_INTEGER:
            return f"i{value};"
        try:
            value = float(value)
        except OverflowError as exc:
            raise ValueError("cleanup_state_number_invalid") from exc
    if isinstance(value, float):
        if value != value or value in {float("inf"), float("-inf")}:
            return "n;"
        if value.is_integer() and -MAX_SAFE_INTEGER <= value <= MAX_SAFE_INTEGER:
            return f"i{int(value)};"
        return f"f{struct.pack('>d', value).hex()};"
    if isinstance(value, str):
        payload = value.encode("utf-8")
        return f"s{len(payload)}:{payload.hex()};"
    if isinstance(value, list):
        return f"a{len(value)}[" + "".join(_encode_cleanup_state(item) for item in value) + "]"
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise ValueError("cleanup_state_object_key_invalid")
        keys = sorted(value, key=lambda key: key.encode("utf-8"))
        return (
            f"o{len(keys)}{{"
            + "".join(
                _encode_cleanup_state(key) + _encode_cleanup_state(value[key]) for key in keys
            )
            + "}"
        )
    raise ValueError("cleanup_state_value_invalid")


def cleanup_state_sha256(value: object) -> str:
    encoded = STATE_HASH_PREFIX + _encode_cleanup_state(value)
    return sha256_bytes(encoded.encode("ascii"))


def restore_target_set_sha256(targets: Iterable[dict[str, object]]) -> str:
    return sha256_value(
        sorted(
            (
                {
                    "kind": str(target["kind"]),
                    "resourceIdHash": str(target["resourceIdHash"]),
                    "stateSha256": str(target["stateSha256"]),
                }
                for target in targets
            ),
            key=lambda target: (target["kind"], target["resourceIdHash"]),
        )
    )


def owner_scope_hash(owner_id: str) -> str:
    normalized = str(owner_id or "").strip()
    if (
        not SAFE_OPAQUE_ID.fullmatch(normalized)
        or normalized in {"all", "*", ".", ".."}
    ):
        raise ValueError("owner_id_invalid")
    return "sha256:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _require_sha256(value: object, label: str) -> str:
    text = str(value or "")
    if not HEX_256.fullmatch(text):
        raise ValueError(f"{label}_invalid")
    return text


def _resolved(path: Path) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _assert_outside_public_roots(path: Path, public_roots: Iterable[Path]) -> None:
    resolved = _resolved(path)
    for public_root in public_roots:
        if _is_within(resolved, _resolved(public_root)):
            raise ValueError("backup_destination_inside_public_root")


def _assert_regular_source(path: Path) -> None:
    try:
        metadata = path.lstat()
    except FileNotFoundError as exc:
        raise ValueError("source_artifact_missing") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise ValueError("source_artifact_not_regular")


def _assert_owner_only(path: Path, label: str) -> None:
    metadata = path.lstat()
    if metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) & 0o077:
        raise ValueError(f"{label}_permissions_not_private")


def _assert_raw_path_not_symlink(path: Path, label: str) -> None:
    raw = Path(path).expanduser()
    try:
        metadata = raw.lstat()
    except FileNotFoundError:
        return
    if stat.S_ISLNK(metadata.st_mode):
        raise ValueError(f"{label}_symlink")


def _read_json(path: Path, label: str, limit: int = 32 * 1024 * 1024) -> dict[str, Any]:
    _assert_regular_source(path)
    if path.stat().st_size > limit:
        raise ValueError(f"{label}_too_large")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label}_invalid") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label}_invalid")
    return payload


def _validate_preimages(
    path: Path,
    expected_owner_scope_hash: str,
    review_set_sha256: str,
) -> dict[str, object]:
    payload = _read_json(path, "preimages")
    if payload.get("contractVersion") != CONTRACT_VERSION:
        raise ValueError("preimages_contract_unsupported")
    if payload.get("ownerScopeHash") != expected_owner_scope_hash:
        raise ValueError("preimages_owner_mismatch")
    if payload.get("reviewSetSha256") != review_set_sha256:
        raise ValueError("preimages_review_set_mismatch")
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("preimages_empty")
    seen: set[tuple[str, str]] = set()
    private_targets: list[dict[str, object]] = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("preimage_item_invalid")
        if set(item) != {
            "kind",
            "resourceIdHash",
            "stateSha256",
            "reviewBindingSha256",
            "preimage",
        }:
            raise ValueError("preimage_item_fields_invalid")
        kind = str(item.get("kind") or "")
        resource_hash = str(item.get("resourceIdHash") or "")
        if kind not in {"schedule", "conversation", "message", "memory"}:
            raise ValueError("preimage_kind_invalid")
        if not resource_hash.startswith("sha256:"):
            raise ValueError("preimage_resource_hash_invalid")
        _require_sha256(resource_hash.removeprefix("sha256:"), "preimage_resource_hash")
        state_sha256 = _require_sha256(item.get("stateSha256"), "preimage_state_sha256")
        review_binding_sha256 = _require_sha256(
            item.get("reviewBindingSha256"), "preimage_review_binding_sha256"
        )
        if "preimage" not in item:
            raise ValueError("preimage_payload_missing")
        if cleanup_state_sha256(item["preimage"]) != state_sha256:
            raise ValueError("preimage_state_mismatch")
        preimage = item["preimage"]
        if not isinstance(preimage, dict) or set(preimage) != {
            "kind",
            "ownerId",
            "resourceId",
            "revision",
            "updatedAt",
            "payload",
        }:
            raise ValueError("preimage_source_shape_invalid")
        if preimage["kind"] != kind:
            raise ValueError("preimage_kind_mismatch")
        owner_id = str(preimage["ownerId"] or "")
        if owner_scope_hash(owner_id) != expected_owner_scope_hash:
            raise ValueError("preimage_owner_mismatch")
        resource_id = str(preimage["resourceId"] or "")
        if not SAFE_OPAQUE_ID.fullmatch(resource_id) or resource_id in {"all", "*", ".", ".."}:
            raise ValueError("preimage_resource_id_invalid")
        if "sha256:" + sha256_bytes(resource_id.encode("utf-8")) != resource_hash:
            raise ValueError("preimage_resource_mismatch")
        revision = preimage["revision"]
        if type(revision) is not int or revision < 0:
            raise ValueError("preimage_revision_invalid")
        updated_at = str(preimage["updatedAt"] or "")
        try:
            parsed_updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("preimage_updated_at_invalid") from exc
        if (
            not updated_at.endswith("Z")
            or parsed_updated_at.utcoffset() is None
            or parsed_updated_at.utcoffset().total_seconds() != 0
        ):
            raise ValueError("preimage_updated_at_invalid")
        identity = (kind, resource_hash)
        if identity in seen:
            raise ValueError("preimage_duplicate")
        seen.add(identity)
        private_targets.append(
            {
                "kind": kind,
                "resourceId": resource_id,
                "resourceIdHash": resource_hash,
                "revision": revision,
                "updatedAt": updated_at,
                "stateSha256": state_sha256,
            }
        )
    calculated_review_set_sha256 = sha256_value(
        sorted(
            (
                {
                    "kind": item["kind"],
                    "resourceIdHash": item["resourceIdHash"],
                    "stateSha256": item["stateSha256"],
                    "reviewBindingSha256": item["reviewBindingSha256"],
                }
                for item in items
            ),
            key=lambda item: (item["kind"], item["resourceIdHash"]),
        )
    )
    if calculated_review_set_sha256 != review_set_sha256:
        raise ValueError("preimages_review_set_mismatch")
    return {
        "status": "verified",
        "method": "canonical_preimage_parse_and_owner_binding",
        "itemCount": len(items),
        "ownerScopeHash": expected_owner_scope_hash,
        "restoredStateSha256": sha256_value(
            [
                {
                    "kind": item["kind"],
                    "resourceIdHash": item["resourceIdHash"],
                    "stateSha256": item["stateSha256"],
                }
                for item in items
            ]
        ),
        "_privateTargetBindings": private_targets,
    }


def _verify_scheduler_snapshot(
    path: Path,
    owner_id: str,
    expected_owner_hash: str,
    target_bindings: tuple[dict[str, object], ...],
) -> dict[str, object]:
    _assert_regular_source(path)
    try:
        connection = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        table = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='scheduled_tasks'"
        ).fetchone()
        if not table:
            raise ValueError("scheduler_table_missing")
        columns = {
            str(row[1])
            for row in connection.execute("PRAGMA table_info(scheduled_tasks)").fetchall()
        }
        if not {"id", "user_id", "updated_at", "cleanup_revision"}.issubset(columns):
            raise ValueError("scheduler_restore_schema_unverified")
        row_count = int(
            connection.execute(
                "SELECT COUNT(*) FROM scheduled_tasks WHERE user_id = ?", (owner_id,)
            ).fetchone()[0]
        )
        for target in target_bindings:
            row = connection.execute(
                "SELECT updated_at, cleanup_revision FROM scheduled_tasks "
                "WHERE id = ? AND user_id = ?",
                (target["resourceId"], owner_id),
            ).fetchone()
            if row is None:
                raise ValueError("scheduler_restore_target_missing")
            if (
                str(row[0]) != str(target["updatedAt"])
                or int(row[1]) != int(target["revision"])
            ):
                raise ValueError("scheduler_restore_target_state_mismatch")
    except sqlite3.Error as exc:
        raise ValueError("scheduler_restore_not_verified") from exc
    finally:
        if "connection" in locals():
            connection.close()
    if not integrity or integrity[0] != "ok":
        raise ValueError("scheduler_restore_not_verified")
    return {
        "status": "verified",
        "method": "read_only_sqlite_restore_integrity_and_owner_query",
        "ownerScopeHash": expected_owner_hash,
        "recordCount": row_count,
        "exactTargetCount": len(target_bindings),
        "targetSetSha256": restore_target_set_sha256(target_bindings),
        "integrityCheck": "ok",
    }


def _validate_mongo_restore_receipt(
    receipt: object,
    expected_owner_hash: str,
    review_set_sha256: str,
    target_bindings: tuple[dict[str, object], ...],
) -> dict[str, object]:
    if not isinstance(receipt, dict) or receipt.get("status") != "verified":
        raise ValueError("mongo_restore_not_verified")
    if receipt.get("ownerScopeHash") != expected_owner_hash:
        raise ValueError("mongo_restore_owner_mismatch")
    if receipt.get("method") != "isolated_namespace_restore_and_compare":
        raise ValueError("mongo_restore_method_unverified")
    if receipt.get("reviewSetSha256") != review_set_sha256:
        raise ValueError("mongo_restore_review_set_mismatch")
    if receipt.get("targetSetSha256") != restore_target_set_sha256(target_bindings):
        raise ValueError("mongo_restore_target_set_mismatch")
    if receipt.get("exactTargetCount") != len(target_bindings):
        raise ValueError("mongo_restore_target_count_mismatch")
    count = receipt.get("recordCount")
    if type(count) is not int or count < 0:
        raise ValueError("mongo_restore_count_invalid")
    _require_sha256(receipt.get("restoredStateSha256"), "mongo_restored_state_sha256")
    return {
        "status": "verified",
        "method": receipt["method"],
        "ownerScopeHash": expected_owner_hash,
        "recordCount": count,
        "restoredStateSha256": receipt["restoredStateSha256"],
        "reviewSetSha256": review_set_sha256,
        "exactTargetCount": len(target_bindings),
        "targetSetSha256": restore_target_set_sha256(target_bindings),
    }


def _artifact_entry(kind: str, filename: str, path: Path, restore: dict[str, object]) -> dict[str, object]:
    payload = path.read_bytes()
    return {
        "kind": kind,
        "path": filename,
        "bytes": len(payload),
        "sha256": sha256_bytes(payload),
        "restore": restore,
    }


def _copy_private(source: Path, destination: Path) -> None:
    _assert_regular_source(source)
    with source.open("rb") as source_handle, destination.open("xb") as destination_handle:
        shutil.copyfileobj(source_handle, destination_handle, length=1024 * 1024)
        destination_handle.flush()
        os.fsync(destination_handle.fileno())
    destination.chmod(0o600)


def _backup_id(now: datetime, expected_owner_hash: str, review_set_sha256: str) -> str:
    timestamp = now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = sha256_value(
        {
            "contractVersion": CONTRACT_VERSION,
            "ownerScopeHash": expected_owner_hash,
            "reviewSetSha256": review_set_sha256,
            "createdAt": now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
    )[:12]
    return f"backup-{timestamp}-{suffix}"


def create_recovery_bundle(
    *,
    source_root: Path,
    destination_root: Path,
    owner_id: str,
    review_set_sha256: str,
    public_roots: Iterable[Path],
    mongo_restore_verifier: MongoRestoreVerifier,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> dict[str, object]:
    """Validate, rehearse, and atomically publish one owner-scoped recovery bundle."""

    review_digest = _require_sha256(review_set_sha256, "review_set_sha256")
    owner_hash = owner_scope_hash(owner_id)
    _assert_raw_path_not_symlink(source_root, "source_bundle")
    _assert_raw_path_not_symlink(destination_root, "backup_destination")
    source = _resolved(source_root)
    destination = _resolved(destination_root)
    _assert_outside_public_roots(destination, public_roots)
    if not source.is_dir():
        raise ValueError("source_bundle_not_directory")
    _assert_owner_only(source, "source_bundle")
    if destination.exists():
        if not destination.is_dir():
            raise ValueError("backup_destination_not_directory")
        _assert_owner_only(destination, "backup_destination")
    else:
        destination.mkdir(parents=True, mode=0o700)

    created_at = now().astimezone(timezone.utc)
    backup_id = _backup_id(created_at, owner_hash, review_digest)
    if not SAFE_BACKUP_ID.fullmatch(backup_id):
        raise ValueError("backup_id_invalid")
    final_root = destination / backup_id
    if final_root.exists():
        raise FileExistsError(backup_id)
    staging = destination / f".staging-{backup_id}-{os.getpid()}"
    staging.mkdir(mode=0o700)
    published = False

    try:
        for _kind, filename in SOURCE_ARTIFACTS:
            _assert_regular_source(source / filename)
            _assert_owner_only(source / filename, "source_artifact")
            _copy_private(source / filename, staging / filename)

        mongo_path = staging / "mongo.archive.gz"
        try:
            gzip.decompress(mongo_path.read_bytes())
        except (gzip.BadGzipFile, EOFError, OSError) as exc:
            raise ValueError("mongo_archive_crc_invalid") from exc

        preimages_restore = _validate_preimages(
            staging / "item-preimages.json", owner_hash, review_digest
        )
        private_targets = tuple(preimages_restore.pop("_privateTargetBindings"))
        mongo_targets = tuple(
            target for target in private_targets if target["kind"] != "schedule"
        )
        schedule_targets = tuple(
            target for target in private_targets if target["kind"] == "schedule"
        )
        mongo_restore = _validate_mongo_restore_receipt(
            mongo_restore_verifier(
                "mongo_archive",
                mongo_path,
                owner_hash,
                review_digest,
                mongo_targets,
            ),
            owner_hash,
            review_digest,
            mongo_targets,
        )
        scheduler_restore = _verify_scheduler_snapshot(
            staging / "schedules.db", owner_id, owner_hash, schedule_targets
        )
        restores = {
            "mongo_archive": mongo_restore,
            "scheduler_snapshot": scheduler_restore,
            "item_preimages": preimages_restore,
        }
        artifacts = [
            _artifact_entry(kind, filename, staging / filename, restores[kind])
            for kind, filename in SOURCE_ARTIFACTS
        ]
        artifact_set_sha256 = sha256_value(artifacts)
        manifest = {
            "contractVersion": CONTRACT_VERSION,
            "backupId": backup_id,
            "ownerScopeHash": owner_hash,
            "reviewSetSha256": review_digest,
            "createdAt": created_at.isoformat().replace("+00:00", "Z"),
            "privateBoundary": "outside_public_repository_owner_only",
            "immutablePublication": True,
            "restoreVerification": "verified",
            "artifactSetSha256": artifact_set_sha256,
            "artifacts": artifacts,
        }
        manifest_path = staging / MANIFEST_NAME
        with manifest_path.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        manifest_path.chmod(0o600)
        manifest_sha256 = sha256_bytes(manifest_path.read_bytes())

        for path in staging.iterdir():
            path.chmod(0o400)
        os.rename(staging, final_root)
        published = True
        final_root.chmod(0o500)
        directory_fd = os.open(destination, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except Exception:
        cleanup_root = final_root if published else staging
        if cleanup_root.exists():
            cleanup_root.chmod(0o700)
            for path in cleanup_root.iterdir():
                path.chmod(0o600)
            shutil.rmtree(cleanup_root)
        raise

    receipt = {
        "contractVersion": CONTRACT_VERSION,
        "backupId": backup_id,
        "ownerScopeHash": owner_hash,
        "reviewSetSha256": review_digest,
        "manifestSha256": manifest_sha256,
        "artifactSetSha256": artifact_set_sha256,
        "restoreVerification": "verified",
        "status": "verified",
        "createdAt": created_at.isoformat().replace("+00:00", "Z"),
    }
    return {**receipt, "receiptSha256": sha256_value(receipt)}


def verify_recovery_bundle(
    bundle_root: Path,
    *,
    owner_id: str,
    review_set_sha256: str,
    public_roots: Iterable[Path],
) -> dict[str, object]:
    """Verify publication safety, hashes, and stored restore receipts without applying data."""

    _assert_raw_path_not_symlink(bundle_root, "backup_bundle")
    bundle = _resolved(bundle_root)
    _assert_outside_public_roots(bundle, public_roots)
    if not bundle.is_dir():
        raise ValueError("backup_bundle_not_directory")
    if bundle.stat().st_uid != os.getuid() or bundle.stat().st_mode & 0o077:
        raise ValueError("backup_permissions_not_private")
    manifest_path = bundle / MANIFEST_NAME
    _assert_regular_source(manifest_path)
    _assert_owner_only(manifest_path, "backup_manifest")
    manifest = _read_json(manifest_path, "recovery_manifest", limit=1024 * 1024)
    owner_hash = owner_scope_hash(owner_id)
    review_digest = _require_sha256(review_set_sha256, "review_set_sha256")
    if manifest.get("contractVersion") != CONTRACT_VERSION:
        raise ValueError("backup_contract_unsupported")
    if manifest.get("backupId") != bundle.name or not SAFE_BACKUP_ID.fullmatch(bundle.name):
        raise ValueError("backup_id_mismatch")
    if manifest.get("ownerScopeHash") != owner_hash:
        raise ValueError("backup_owner_mismatch")
    if manifest.get("reviewSetSha256") != review_digest:
        raise ValueError("backup_review_set_mismatch")
    if manifest.get("privateBoundary") != "outside_public_repository_owner_only":
        raise ValueError("backup_private_boundary_unverified")
    if manifest.get("immutablePublication") is not True:
        raise ValueError("backup_immutability_unverified")
    if manifest.get("restoreVerification") != "verified":
        raise ValueError("backup_restore_unverified")

    preimages_restore = _validate_preimages(
        bundle / "item-preimages.json", owner_hash, review_digest
    )
    private_targets = tuple(preimages_restore.pop("_privateTargetBindings"))
    mongo_targets = tuple(target for target in private_targets if target["kind"] != "schedule")
    schedule_targets = tuple(target for target in private_targets if target["kind"] == "schedule")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != len(SOURCE_ARTIFACTS):
        raise ValueError("backup_artifact_set_invalid")
    expected = {kind: filename for kind, filename in SOURCE_ARTIFACTS}
    seen: set[str] = set()
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            raise ValueError("backup_artifact_invalid")
        kind = str(artifact.get("kind") or "")
        filename = str(artifact.get("path") or "")
        if kind in seen or expected.get(kind) != filename or Path(filename).name != filename:
            raise ValueError("backup_artifact_identity_invalid")
        seen.add(kind)
        path = bundle / filename
        _assert_regular_source(path)
        if path.stat().st_mode & 0o077:
            raise ValueError("backup_artifact_permissions_not_private")
        payload = path.read_bytes()
        if artifact.get("sha256") != sha256_bytes(payload):
            raise ValueError("artifact_sha256_mismatch")
        if artifact.get("bytes") != len(payload):
            raise ValueError("artifact_size_mismatch")
        restore = artifact.get("restore")
        if not isinstance(restore, dict) or restore.get("status") != "verified":
            raise ValueError("artifact_restore_unverified")
        if restore.get("ownerScopeHash") != owner_hash:
            raise ValueError("artifact_restore_owner_mismatch")
        if kind == "mongo_archive":
            _validate_mongo_restore_receipt(
                restore,
                owner_hash,
                review_digest,
                mongo_targets,
            )
            try:
                gzip.decompress(payload)
            except (gzip.BadGzipFile, EOFError, OSError) as exc:
                raise ValueError("mongo_archive_crc_invalid") from exc
        elif kind == "scheduler_snapshot":
            current_restore = _verify_scheduler_snapshot(
                path, owner_id, owner_hash, schedule_targets
            )
            if any(restore.get(key) != value for key, value in current_restore.items()):
                raise ValueError("scheduler_restore_receipt_mismatch")
        elif kind == "item_preimages":
            if any(restore.get(key) != value for key, value in preimages_restore.items()):
                raise ValueError("preimages_restore_receipt_mismatch")

    if seen != set(expected):
        raise ValueError("backup_artifact_set_invalid")
    artifact_set_sha256 = sha256_value(artifacts)
    if manifest.get("artifactSetSha256") != artifact_set_sha256:
        raise ValueError("artifact_set_sha256_mismatch")
    receipt = {
        "contractVersion": CONTRACT_VERSION,
        "backupId": bundle.name,
        "ownerScopeHash": owner_hash,
        "reviewSetSha256": review_digest,
        "manifestSha256": sha256_bytes(manifest_path.read_bytes()),
        "artifactSetSha256": artifact_set_sha256,
        "restoreVerification": "verified",
        "status": "verified",
        "createdAt": manifest.get("createdAt"),
    }
    return {**receipt, "receiptSha256": sha256_value(receipt)}

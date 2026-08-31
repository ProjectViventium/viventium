#!/usr/bin/env python3
"""Build a public-safe, non-executing plan for reviewed synthetic-QA cleanup.

This module has no database, HTTP, subprocess, or filesystem mutation capability. It accepts a
private reviewed manifest, validates owner/review/recovery bindings, and emits only hashes, counts,
product API templates, blockers, and ordered cleanup requirements. A separate explicitly approved
operator must capture the backup, supply the reviewed manifest, and execute product operations.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import stat
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


CONTRACT_VERSION = 1
HEX_256 = re.compile(r"[0-9a-f]{64}")
SAFE_OPAQUE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,159}")
SAFE_BACKUP_ID = re.compile(r"backup-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{12}")
REQUIRED_CAPABILITIES = (
    "ownerAuthenticatedProductApi",
    "revisionSafeMemoryMutation",
    "revisionSafeConversationTombstone",
    "revisionSafeMessageTombstone",
    "revisionSafeScheduleTombstone",
    "searchReconciliationReceipt",
    "recallRebuildReceipt",
    "delayedNonceSweep",
)
TOP_LEVEL_FIELDS = {
    "contractVersion",
    "owner",
    "operation",
    "backup",
    "capabilities",
    "items",
}
OWNER_FIELDS = {"id", "bindingSource", "adminVerified"}
OPERATION_FIELDS = {"id", "runNonce", "preparedAt", "notBefore"}
BACKUP_FIELDS = {"kind", "ownerId", "recoveryReceipt"}
RECOVERY_RECEIPT_FIELDS = {
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
BASE_ITEM_FIELDS = {"kind", "ownerId", "resourceId", "provenance", "review"}
EXACT_STATE_FIELDS = {
    "expectedRevision",
    "expectedUpdatedAt",
    "stateSha256",
    "preimageSha256",
}
ITEM_FIELDS = {
    "schedule": BASE_ITEM_FIELDS | EXACT_STATE_FIELDS | {"active"},
    "conversation": BASE_ITEM_FIELDS
    | EXACT_STATE_FIELDS
    | {"contentScope", "messageCount", "typedSyntheticMessageCount"},
    "message": BASE_ITEM_FIELDS | EXACT_STATE_FIELDS | {"conversationId", "parentScope"},
    "memory": BASE_ITEM_FIELDS | EXACT_STATE_FIELDS | {"contentScope"},
}
REVIEW_FIELDS = {
    "classification",
    "reviewerRole",
    "reviewedAt",
    "evidenceSha256",
    "bindingSha256",
}
PROVENANCE_FIELDS = {
    "structured_qa_run": {"kind", "runNonce"},
    "reviewed_legacy_synthetic_marker": {"kind", "markerDigest"},
}


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _text_sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def owner_scope_hash(owner_id: str) -> str:
    return "sha256:" + _text_sha(_require_safe_id(owner_id, "owner_id"))


def _require_object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label}_must_be_object")
    return value


def _require_exact_fields(value: dict[str, Any], fields: set[str], label: str) -> None:
    if set(value) - fields:
        raise ValueError(f"unexpected_{label}_fields")


def _require_sha256(value: object, label: str) -> str:
    text = str(value or "")
    if not HEX_256.fullmatch(text):
        raise ValueError(f"{label}_invalid")
    return text


def _require_safe_id(value: object, label: str) -> str:
    text = str(value or "")
    if not SAFE_OPAQUE_ID.fullmatch(text) or text in {"all", "*", ".", ".."}:
        raise ValueError(f"unsafe_{label}")
    return text


def _review_payload(item: dict[str, Any]) -> dict[str, Any]:
    review = item.get("review") if isinstance(item.get("review"), dict) else {}
    return {
        "classification": review.get("classification"),
        "reviewerRole": review.get("reviewerRole"),
        "reviewedAt": review.get("reviewedAt"),
        "evidenceSha256": review.get("evidenceSha256"),
    }


def review_binding_digest(owner_id: str, item: dict[str, Any]) -> str:
    """Bind a human review to one exact owner, target, revision, and provenance record."""

    immutable_item = {key: value for key, value in item.items() if key != "review"}
    return _sha(
        {
            "contractVersion": CONTRACT_VERSION,
            "ownerId": owner_id,
            "item": immutable_item,
            "review": _review_payload(item),
        }
    )


def _validate_owner(manifest: dict[str, Any]) -> str:
    owner = _require_object(manifest.get("owner"), "owner")
    _require_exact_fields(owner, OWNER_FIELDS, "owner")
    owner_id = _require_safe_id(owner.get("id"), "owner_id")
    if owner.get("bindingSource") != "authenticated_owner_scoped_product_session":
        raise ValueError("owner_binding_source_unverified")
    if owner.get("adminVerified") is not True:
        raise ValueError("owner_admin_unverified")
    return owner_id


def _parse_utc(value: object, label: str) -> datetime:
    text = str(value or "")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{label}_invalid") from exc
    if not text.endswith("Z") or parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
        raise ValueError(f"{label}_invalid")
    return parsed


def _review_set_digest(items: list[dict[str, Any]]) -> str:
    return _sha(
        sorted(
            (
                {
                    "kind": item["kind"],
                    "resourceIdHash": "sha256:" + _text_sha(item["resourceId"]),
                    "stateSha256": item["stateSha256"],
                    "reviewBindingSha256": item["review"]["bindingSha256"],
                }
                for item in items
            ),
            key=lambda value: (value["kind"], value["resourceIdHash"]),
        )
    )


def _backup_blockers(
    manifest: dict[str, Any], owner_id: str, review_set_sha256: str
) -> tuple[list[str], dict[str, Any]]:
    backup = _require_object(manifest.get("backup"), "backup")
    _require_exact_fields(backup, BACKUP_FIELDS, "backup")
    if backup.get("ownerId") != owner_id:
        raise ValueError("backup_owner_mismatch")

    blockers: list[str] = []
    if backup.get("kind") != "private_recoverable_bundle":
        blockers.append("recoverable_backup_missing")
    receipt = _require_object(backup.get("recoveryReceipt"), "recovery_receipt")
    _require_exact_fields(receipt, RECOVERY_RECEIPT_FIELDS, "recovery_receipt")
    if receipt.get("contractVersion") != CONTRACT_VERSION:
        raise ValueError("backup_contract_unsupported")
    if not SAFE_BACKUP_ID.fullmatch(str(receipt.get("backupId") or "")):
        raise ValueError("backup_id_invalid")
    if receipt.get("ownerScopeHash") != owner_scope_hash(owner_id):
        raise ValueError("backup_owner_scope_mismatch")
    if receipt.get("reviewSetSha256") != review_set_sha256:
        raise ValueError("backup_review_set_mismatch")
    for field in ("manifestSha256", "artifactSetSha256", "receiptSha256"):
        _require_sha256(receipt.get(field), f"backup_{field}")
    _parse_utc(receipt.get("createdAt"), "backup_created_at")
    supplied_receipt_sha = str(receipt["receiptSha256"])
    expected_receipt_sha = _sha(
        {key: value for key, value in receipt.items() if key != "receiptSha256"}
    )
    if not hmac.compare_digest(supplied_receipt_sha, expected_receipt_sha):
        raise ValueError("backup_receipt_hash_mismatch")
    if receipt.get("restoreVerification") != "verified" or receipt.get("status") != "verified":
        blockers.append("backup_restore_unverified")
    return blockers, receipt


def _validate_operation(manifest: dict[str, Any]) -> dict[str, Any]:
    operation = _require_object(manifest.get("operation"), "operation")
    _require_exact_fields(operation, OPERATION_FIELDS, "operation")
    operation_id = _require_safe_id(operation.get("id"), "cleanup_operation_id")
    run_nonce = _require_safe_id(operation.get("runNonce"), "cleanup_run_nonce")
    prepared_at = _parse_utc(operation.get("preparedAt"), "cleanup_prepared_at")
    not_before = _parse_utc(operation.get("notBefore"), "cleanup_not_before")
    if (not_before - prepared_at).total_seconds() < 900:
        raise ValueError("cleanup_sweep_delay_too_short")
    return {
        "operationId": operation_id,
        "runNonce": run_nonce,
        "operationIdHash": "sha256:" + _text_sha(operation_id),
        "runNonceHash": "sha256:" + _text_sha(run_nonce),
        "notBefore": str(operation["notBefore"]),
    }


def _validate_capabilities(manifest: dict[str, Any]) -> list[str]:
    capabilities = _require_object(manifest.get("capabilities"), "capabilities")
    _require_exact_fields(capabilities, set(REQUIRED_CAPABILITIES), "capabilities")
    return [
        f"capability_unavailable:{name}"
        for name in REQUIRED_CAPABILITIES
        if capabilities.get(name) is not True
    ]


def _validate_provenance(item: dict[str, Any]) -> None:
    provenance = _require_object(item.get("provenance"), "provenance")
    kind = provenance.get("kind")
    if kind not in PROVENANCE_FIELDS:
        raise ValueError("synthetic_provenance_unverified")
    _require_exact_fields(provenance, PROVENANCE_FIELDS[kind], "provenance")
    if kind == "structured_qa_run":
        _require_safe_id(provenance.get("runNonce"), "run_nonce")
    else:
        _require_sha256(provenance.get("markerDigest"), "marker_digest")


def _validate_review(item: dict[str, Any], owner_id: str) -> None:
    review = _require_object(item.get("review"), "review")
    _require_exact_fields(review, REVIEW_FIELDS, "review")
    if review.get("classification") != "confirmed_synthetic_qa":
        raise ValueError("item_not_confirmed_synthetic")
    if review.get("reviewerRole") != "owner":
        raise ValueError("item_not_owner_reviewed")
    reviewed_at = str(review.get("reviewedAt") or "")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", reviewed_at):
        raise ValueError("review_timestamp_invalid")
    try:
        datetime.strptime(reviewed_at, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ValueError("review_timestamp_invalid") from exc
    _require_sha256(review.get("evidenceSha256"), "review_evidence_sha256")
    binding = _require_sha256(review.get("bindingSha256"), "review_binding_sha256")
    if not hmac.compare_digest(binding, review_binding_digest(owner_id, item)):
        raise ValueError("review_binding_mismatch")


def _validate_item(item_value: object, owner_id: str) -> dict[str, Any]:
    item = _require_object(item_value, "item")
    kind = str(item.get("kind") or "")
    allowed = ITEM_FIELDS.get(kind)
    if allowed is None:
        raise ValueError("unsupported_cleanup_target_kind")
    _require_exact_fields(item, allowed, "item")
    if item.get("ownerId") != owner_id:
        raise ValueError("item_owner_mismatch")
    _require_safe_id(item.get("resourceId"), "resource_id")
    _validate_provenance(item)
    _validate_review(item, owner_id)

    revision = item.get("expectedRevision")
    if type(revision) is not int or revision < 0:
        raise ValueError(f"{kind}_revision_required")
    _parse_utc(item.get("expectedUpdatedAt"), f"{kind}_updated_at")
    state_sha256 = _require_sha256(item.get("stateSha256"), f"{kind}_state_sha256")
    preimage_sha256 = _require_sha256(
        item.get("preimageSha256"), f"{kind}_preimage_sha256"
    )
    if not hmac.compare_digest(state_sha256, preimage_sha256):
        raise ValueError(f"{kind}_preimage_state_mismatch")

    if kind == "schedule":
        if not isinstance(item.get("active"), bool):
            raise ValueError("schedule_active_state_required")
    elif kind == "conversation":
        if item.get("contentScope") != "fully_synthetic":
            raise ValueError("conversation_not_fully_synthetic")
        count = item.get("messageCount")
        typed_count = item.get("typedSyntheticMessageCount")
        if (
            type(count) is not int
            or count < 1
            or type(typed_count) is not int
            or typed_count != count
        ):
            raise ValueError("conversation_message_proof_incomplete")
    elif kind == "message":
        _require_safe_id(item.get("conversationId"), "conversation_id")
        if item.get("parentScope") not in {
            "mixed_preserve_parent",
            "fully_synthetic_parent",
        }:
            raise ValueError("message_parent_preservation_unverified")
    elif kind == "memory":
        if item.get("contentScope") != "fully_synthetic":
            raise ValueError("memory_content_scope_unverified")
    return item


def _target_hash(owner_id: str, item: dict[str, Any]) -> str:
    return "sha256:" + _sha(
        {"ownerId": owner_id, "kind": item["kind"], "resourceId": item["resourceId"]}
    )


def _base_operation(
    owner_id: str,
    owner_hash: str,
    item: dict[str, Any],
    operation_binding: dict[str, Any],
    backup_receipt_sha256: str,
    review_set_sha256: str,
    plan_sha256: str,
) -> dict[str, Any]:
    operation = {
        "ownerHash": owner_hash,
        "targetHash": _target_hash(owner_id, item),
        "targetKind": item["kind"],
        "transport": "owner_authenticated_product_api",
        "operationIdHash": operation_binding["operationIdHash"],
        "runNonceHash": operation_binding["runNonceHash"],
        "backupReceiptSha256": backup_receipt_sha256,
        "reviewSetSha256": review_set_sha256,
        "planSha256": plan_sha256,
        "expectedRevision": item["expectedRevision"],
        "expectedUpdatedAt": item["expectedUpdatedAt"],
        "stateSha256": item["stateSha256"],
        "preimageSha256": item["preimageSha256"],
        "reviewBindingSha256": item["review"]["bindingSha256"],
    }
    provenance = item["provenance"]
    operation["syntheticMarker"] = provenance["kind"]
    if provenance["kind"] == "structured_qa_run":
        operation["sourceRunNonceHash"] = "sha256:" + _text_sha(provenance["runNonce"])
    else:
        operation["sourceMarkerHash"] = "sha256:" + provenance["markerDigest"]
    return operation


def _mutation_operation(
    owner_id: str,
    owner_hash: str,
    item: dict[str, Any],
    operation_binding: dict[str, Any],
    backup_receipt_sha256: str,
    review_set_sha256: str,
    plan_sha256: str,
) -> dict[str, Any]:
    operation = _base_operation(
        owner_id,
        owner_hash,
        item,
        operation_binding,
        backup_receipt_sha256,
        review_set_sha256,
        plan_sha256,
    )
    kind = item["kind"]
    if kind == "schedule":
        operation.update(
            {
                "method": "POST",
                "operation": "revision_safe_tombstone",
                "requiredCapability": "revisionSafeScheduleTombstone",
                "expectedRevision": item["expectedRevision"],
                "successReceipt": "newer_owner_bound_schedule_tombstone_revision",
            }
        )
    elif kind == "conversation":
        operation.update(
            {
                "method": "POST",
                "operation": "revision_safe_tombstone",
                "requiredCapability": "revisionSafeConversationTombstone",
                "expectedRevision": item["expectedRevision"],
                "successReceipt": "newer_owner_conversation_tombstone_with_messages_hidden",
            }
        )
    elif kind == "message":
        operation.update(
            {
                "method": "POST",
                "operation": "revision_safe_tombstone",
                "requiredCapability": "revisionSafeMessageTombstone",
                "expectedRevision": item["expectedRevision"],
                "parentHash": "sha256:"
                + _sha({"ownerHash": owner_hash, "conversationId": item["conversationId"]}),
                "successReceipt": "newer_owner_message_tombstone_parent_preserved",
            }
        )
    elif kind == "memory":
        operation.update(
            {
                "method": "DELETE",
                "operation": "revision_safe_tombstone",
                "requiredCapability": "revisionSafeMemoryMutation",
                "endpoint": "/api/memories/entries/{key}?revision={expectedRevision}",
                "expectedRevision": item["expectedRevision"],
                "successReceipt": "newer_memory_tombstone_revision",
            }
        )
    return operation


def _empty_phases() -> list[dict[str, Any]]:
    return [
        {"phase": phase, "operations": []}
        for phase in (
            "verify_private_recovery",
            "stop_confirmed_synthetic_producers",
            "revalidate_owner_and_revisions",
            "apply_owner_authenticated_product_mutations",
            "reconcile_derived_search_and_recall",
            "verify_immediate_zero_residue",
            "delayed_nonce_sweep",
        )
    ]


def _backup_procedure() -> dict[str, Any]:
    return {
        "privateBoundary": "separate_private_repository_or_owner_only_backup_directory",
        "capture": [
            {
                "tool": "mongodump",
                "arguments": [
                    "--config=<private-0600-config>",
                    "--archive=<private-bundle>/mongo.archive.gz",
                    "--gzip",
                    "--readPreference=primary",
                ],
            },
            {
                "tool": "sqlite3",
                "method": "online .backup",
                "source": "<private-runtime-scheduler-db>",
                "destination": "<private-bundle>/schedules.db",
            },
            {
                "tool": "item-preimage-export",
                "scope": "exact reviewed owner-bound target ids only",
                "contentVisibility": "private_backup_only",
            },
        ],
        "verify": [
            "sha256 every artifact",
            "restore Mongo archive into an isolated temporary namespace and compare owner-bound state",
            "sqlite3 <snapshot> PRAGMA integrity_check returns ok",
            "item preimage count and owner binding match reviewed manifest",
        ],
        "restore": {
            "target": "isolated_recovery_target_only",
            "liveTargetRestoreForbidden": True,
            "restoredRecallPolicy": "block_until_sanitation_reapplied_and_derived_state_rebuilt",
        },
    }


def build_cleanup_plan(manifest_value: object) -> dict[str, Any]:
    manifest = _require_object(manifest_value, "manifest")
    _require_exact_fields(manifest, TOP_LEVEL_FIELDS, "manifest")
    if manifest.get("contractVersion") != CONTRACT_VERSION:
        raise ValueError("unsupported_contract_version")
    owner_id = _validate_owner(manifest)
    operation_binding = _validate_operation(manifest)

    item_values = manifest.get("items")
    if not isinstance(item_values, list) or not item_values:
        raise ValueError("reviewed_cleanup_items_required")
    items = [_validate_item(item, owner_id) for item in item_values]
    seen: set[tuple[str, str]] = set()
    for item in items:
        identity = (item["kind"], item["resourceId"])
        if identity in seen:
            raise ValueError("duplicate_cleanup_target")
        seen.add(identity)
    deleted_conversation_ids = {
        item["resourceId"] for item in items if item["kind"] == "conversation"
    }
    for conversation in (item for item in items if item["kind"] == "conversation"):
        children = [
            item
            for item in items
            if item["kind"] == "message"
            and item["conversationId"] == conversation["resourceId"]
        ]
        if (
            len(children) != conversation["messageCount"]
            or any(child["parentScope"] != "fully_synthetic_parent" for child in children)
        ):
            raise ValueError("conversation_reviewed_child_set_incomplete")
    if any(
        item["kind"] == "message"
        and item["conversationId"] not in deleted_conversation_ids
        and item["parentScope"] != "mixed_preserve_parent"
        for item in items
    ):
        raise ValueError("message_parent_preservation_unverified")
    structured_run_nonces = {
        item["provenance"]["runNonce"]
        for item in items
        if item["provenance"]["kind"] == "structured_qa_run"
    }
    if structured_run_nonces and structured_run_nonces != {operation_binding["runNonce"]}:
        raise ValueError("cleanup_operation_nonce_source_mismatch")

    review_set_sha256 = _review_set_digest(items)
    backup_blockers, backup_receipt = _backup_blockers(
        manifest, owner_id, review_set_sha256
    )
    blockers = backup_blockers + _validate_capabilities(manifest)
    if any(item["kind"] == "schedule" and item["active"] for item in items):
        blockers.append("active_schedule_requires_deactivation_revalidation_and_new_backup")
    owner_hash = owner_scope_hash(owner_id)
    target_set_sha256 = _sha(
        sorted(
            ({"kind": item["kind"], "resourceId": item["resourceId"]} for item in items),
            key=lambda value: (value["kind"], value["resourceId"]),
        )
    )
    plan_sha256 = _sha(
        {
            "contractVersion": CONTRACT_VERSION,
            "ownerScopeHash": owner_hash,
            "operationIdHash": operation_binding["operationIdHash"],
            "runNonceHash": operation_binding["runNonceHash"],
            "notBefore": operation_binding["notBefore"],
            "backupReceiptSha256": backup_receipt["receiptSha256"],
            "reviewSetSha256": review_set_sha256,
            "targetSetSha256": target_set_sha256,
        }
    )
    phases = _empty_phases()
    phases[0]["operations"] = [
        {
            "transport": "local_read_only_verification",
            "action": "verify_private_recoverable_bundle_and_exact_owner_preimages",
            "ownerHash": owner_hash,
            "backupReceiptSha256": backup_receipt["receiptSha256"],
            "reviewSetSha256": review_set_sha256,
        }
    ]
    if not blockers:
        phases[2]["operations"] = [
            {
                **_base_operation(
                    owner_id,
                    owner_hash,
                    item,
                    operation_binding,
                    backup_receipt["receiptSha256"],
                    review_set_sha256,
                    plan_sha256,
                ),
                "method": "GET",
                "action": "refetch_exact_owner_target_and_compare_review_binding",
            }
            for item in items
        ]
        mutation_order = {"message": 0, "memory": 1, "schedule": 2, "conversation": 3}
        phases[3]["operations"] = [
            _mutation_operation(
                owner_id,
                owner_hash,
                item,
                operation_binding,
                backup_receipt["receiptSha256"],
                review_set_sha256,
                plan_sha256,
            )
            for item in sorted(
                items,
                key=lambda value: (mutation_order[value["kind"]], value["resourceId"]),
            )
        ]
        phases[4]["operations"] = [
            {
                "transport": "authenticated_product_service",
                "action": "wait_for_meili_deletion_receipts_then_verify_owner_scoped_absence",
                "ownerHash": owner_hash,
                "targetSetSha256": target_set_sha256,
                "requiredReceipt": "searchReconciliationReceipt",
            },
            {
                "transport": "authenticated_product_service",
                "action": "refresh_owner_conversation_recall_then_verify_corpus_and_vectors",
                "ownerHash": owner_hash,
                "targetSetSha256": target_set_sha256,
                "requiredReceipt": "recallRebuildReceipt",
            },
        ]
        phases[5]["operations"] = [
            {
                "transport": "owner_authenticated_read_only_product_api",
                "action": (
                    "verify_exact_targets_absent_or_revision_tombstoned_and_"
                    "genuine_baselines_unchanged"
                ),
                "ownerHash": owner_hash,
                "targetSetSha256": target_set_sha256,
                "targetCount": len(items),
            }
        ]
        nonce_hashes = sorted(
            {
                "sha256:"
                + (
                    _text_sha(item["provenance"]["runNonce"])
                    if item["provenance"]["kind"] == "structured_qa_run"
                    else item["provenance"]["markerDigest"]
                )
                for item in items
            }
        )
        phases[6]["operations"] = [
            {
                "transport": "owner_authenticated_read_only_product_api",
                "action": (
                    "delayed_exact_nonce_and_target_sweep_across_canonical_"
                    "search_vector_and_recall_surfaces"
                ),
                "ownerHash": owner_hash,
                "notBefore": operation_binding["notBefore"],
                "runNonceHash": operation_binding["runNonceHash"],
                "targetSetSha256": target_set_sha256,
                "nonceOrMarkerHashes": nonce_hashes,
                "successReceipt": "zero_residue_and_genuine_baselines_unchanged",
            }
        ]

    return {
        "contractVersion": CONTRACT_VERSION,
        "status": "BLOCKED" if blockers else "PREPARED_NOT_EXECUTED",
        "executionAuthorized": False,
        "blockers": sorted(blockers),
        "ownerBinding": {
            "declaredForPlanning": True,
            "verified": False,
            "verificationRequiredAtExecution": True,
            "ownerHash": owner_hash,
            "source": "authenticated_owner_scoped_product_session",
        },
        "operationBinding": {
            "ownerScopeHash": owner_hash,
            "operationIdHash": operation_binding["operationIdHash"],
            "runNonceHash": operation_binding["runNonceHash"],
            "notBefore": operation_binding["notBefore"],
            "planSha256": plan_sha256,
            "backupReceiptSha256": backup_receipt["receiptSha256"],
            "reviewSetSha256": review_set_sha256,
            "targetSetSha256": target_set_sha256,
        },
        "inventory": dict(sorted(Counter(item["kind"] for item in items).items())),
        "preservationPolicy": [
            "real_personal",
            "health",
            "feelings",
            "whoop",
            "continuity",
            "business",
            "unreviewed_or_mixed_parent_content",
        ],
        "backupProcedure": _backup_procedure(),
        "mutationPolicy": {
            "atomicity": "per_item_revision_or_owner_guarded",
            "crossStore": "journaled_fail_stop_with_verified_compensation",
            "globalTransactionClaimed": False,
        },
        "phases": phases,
    }


def _load_private_manifest(path: Path) -> object:
    raw_path = path.expanduser()
    raw_metadata = raw_path.lstat()
    if stat.S_ISLNK(raw_metadata.st_mode) or not stat.S_ISREG(raw_metadata.st_mode):
        raise ValueError("private_manifest_must_be_regular_file")
    path = raw_path.resolve(strict=True)
    repository = Path(__file__).resolve().parents[2]
    if path == repository or repository in path.parents:
        raise ValueError("private_manifest_must_be_outside_public_repository")
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode):
        raise ValueError("private_manifest_must_be_regular_file")
    if metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) & 0o077:
        raise ValueError("private_manifest_permissions_must_be_owner_only")
    if metadata.st_size > 2_000_000:
        raise ValueError("private_manifest_too_large")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("private_manifest_invalid") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        plan = build_cleanup_plan(_load_private_manifest(args.manifest))
    except (OSError, ValueError) as exc:
        print(canonical_json({"status": "REFUSED", "reason": str(exc)}))
        return 2
    print(canonical_json(plan))
    return 3 if plan["status"] == "BLOCKED" else 0


if __name__ == "__main__":
    sys.exit(main())

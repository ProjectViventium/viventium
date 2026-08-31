from __future__ import annotations

import importlib.util
import ast
import json
from copy import deepcopy
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "viventium" / "personal_account_qa_cleanup_plan.py"
OWNER_ID = "owner_0123456789abcdef"
SHA = "a" * 64


def load_module():
    spec = importlib.util.spec_from_file_location("personal_account_qa_cleanup_plan", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


planner = load_module()


def reviewed(item: dict) -> dict:
    candidate = deepcopy(item)
    candidate.setdefault("expectedUpdatedAt", "2026-08-25T19:55:00Z")
    candidate.setdefault("stateSha256", SHA)
    candidate.setdefault("preimageSha256", SHA)
    candidate["review"] = {
        "classification": "confirmed_synthetic_qa",
        "reviewerRole": "owner",
        "reviewedAt": "2026-08-25T20:00:00Z",
        "evidenceSha256": SHA,
        "bindingSha256": "",
    }
    candidate["review"]["bindingSha256"] = planner.review_binding_digest(OWNER_ID, candidate)
    return candidate


def valid_manifest() -> dict:
    manifest = {
        "contractVersion": 1,
        "owner": {
            "id": OWNER_ID,
            "bindingSource": "authenticated_owner_scoped_product_session",
            "adminVerified": True,
        },
        "operation": {
            "id": "cleanup-operation-1",
            "runNonce": "cleanup-nonce-1",
            "preparedAt": "2026-08-25T20:00:00Z",
            "notBefore": "2026-08-25T20:15:00Z",
        },
        "capabilities": {
            "ownerAuthenticatedProductApi": True,
            "revisionSafeMemoryMutation": True,
            "revisionSafeConversationTombstone": True,
            "revisionSafeMessageTombstone": True,
            "revisionSafeScheduleTombstone": True,
            "searchReconciliationReceipt": True,
            "recallRebuildReceipt": True,
            "delayedNonceSweep": True,
        },
        "items": [
            reviewed(
                {
                    "kind": "schedule",
                    "ownerId": OWNER_ID,
                    "resourceId": "schedule_synthetic_01",
                    "active": False,
                    "expectedRevision": 3,
                    "provenance": {
                        "kind": "reviewed_legacy_synthetic_marker",
                        "markerDigest": SHA,
                    },
                }
            ),
            reviewed(
                {
                    "kind": "conversation",
                    "ownerId": OWNER_ID,
                    "resourceId": "conversation_synthetic_01",
                    "contentScope": "fully_synthetic",
                    "expectedRevision": 5,
                    "messageCount": 1,
                    "typedSyntheticMessageCount": 1,
                    "provenance": {
                        "kind": "structured_qa_run",
                        "runNonce": "cleanup-nonce-1",
                    },
                }
            ),
            reviewed(
                {
                    "kind": "message",
                    "ownerId": OWNER_ID,
                    "resourceId": "message_synthetic_01",
                    "conversationId": "conversation_synthetic_01",
                    "parentScope": "fully_synthetic_parent",
                    "expectedRevision": 2,
                    "provenance": {
                        "kind": "structured_qa_run",
                        "runNonce": "cleanup-nonce-1",
                    },
                }
            ),
            reviewed(
                {
                    "kind": "memory",
                    "ownerId": OWNER_ID,
                    "resourceId": "memory_key_synthetic_01",
                    "contentScope": "fully_synthetic",
                    "expectedRevision": 4,
                    "provenance": {
                        "kind": "reviewed_legacy_synthetic_marker",
                        "markerDigest": "d" * 64,
                    },
                }
            ),
            reviewed(
                {
                    "kind": "memory",
                    "ownerId": OWNER_ID,
                    "resourceId": "memory_key_mixed_01",
                    "contentScope": "fully_synthetic",
                    "expectedRevision": 7,
                    "provenance": {
                        "kind": "reviewed_legacy_synthetic_marker",
                        "markerDigest": "f" * 64,
                    },
                }
            ),
        ],
    }
    review_set_sha256 = planner._review_set_digest(manifest["items"])
    receipt = {
        "contractVersion": 1,
        "backupId": "backup-20260825T200000Z-0123456789ab",
        "ownerScopeHash": planner.owner_scope_hash(OWNER_ID),
        "reviewSetSha256": review_set_sha256,
        "manifestSha256": "b" * 64,
        "artifactSetSha256": "c" * 64,
        "restoreVerification": "verified",
        "status": "verified",
        "createdAt": "2026-08-25T20:00:00Z",
    }
    receipt["receiptSha256"] = planner._sha(receipt)
    manifest["backup"] = {
        "kind": "private_recoverable_bundle",
        "ownerId": OWNER_ID,
        "recoveryReceipt": receipt,
    }
    return manifest


def test_builds_owner_bound_non_executing_product_api_plan() -> None:
    plan = planner.build_cleanup_plan(valid_manifest())

    assert plan["status"] == "PREPARED_NOT_EXECUTED"
    assert plan["executionAuthorized"] is False
    assert plan["ownerBinding"] == {
        "declaredForPlanning": True,
        "verified": False,
        "verificationRequiredAtExecution": True,
        "ownerHash": planner.owner_scope_hash(OWNER_ID),
        "source": "authenticated_owner_scoped_product_session",
    }
    assert plan["inventory"] == {
        "conversation": 1,
        "memory": 2,
        "message": 1,
        "schedule": 1,
    }
    assert [phase["phase"] for phase in plan["phases"]] == [
        "verify_private_recovery",
        "stop_confirmed_synthetic_producers",
        "revalidate_owner_and_revisions",
        "apply_owner_authenticated_product_mutations",
        "reconcile_derived_search_and_recall",
        "verify_immediate_zero_residue",
        "delayed_nonce_sweep",
    ]
    operations = [operation for phase in plan["phases"] for operation in phase["operations"]]
    assert all(operation["transport"] != "direct_database_delete" for operation in operations)
    assert any(
        operation.get("endpoint")
        == "/api/memories/entries/{key}?revision={expectedRevision}"
        for operation in operations
    )
    assert any(
        operation.get("requiredCapability") == "revisionSafeMessageTombstone"
        for operation in operations
    )
    assert any(
        operation.get("requiredCapability") == "revisionSafeConversationTombstone"
        for operation in operations
    )
    assert any(
        operation.get("requiredCapability") == "revisionSafeScheduleTombstone"
        for operation in operations
    )
    assert not any(
        operation.get("endpoint") == "/api/messages/{conversationId}/{messageId}"
        for operation in operations
    )
    assert not any(operation.get("endpoint") == "/api/convos" for operation in operations)


def test_public_plan_never_contains_owner_or_resource_ids() -> None:
    manifest = valid_manifest()
    plan_text = planner.canonical_json(planner.build_cleanup_plan(manifest))

    assert OWNER_ID not in plan_text
    for item in manifest["items"]:
        assert item["resourceId"] not in plan_text
        assert item.get("conversationId", "not-present") not in plan_text


def test_missing_recoverable_backup_blocks_all_mutation_phases() -> None:
    manifest = valid_manifest()
    receipt = manifest["backup"]["recoveryReceipt"]
    receipt["restoreVerification"] = "failed"
    receipt["receiptSha256"] = planner._sha(
        {key: value for key, value in receipt.items() if key != "receiptSha256"}
    )

    plan = planner.build_cleanup_plan(manifest)

    assert plan["status"] == "BLOCKED"
    assert "backup_restore_unverified" in plan["blockers"]
    assert all(
        not phase["operations"]
        for phase in plan["phases"]
        if phase["phase"] != "verify_private_recovery"
    )


@pytest.mark.parametrize(
    "capability",
    [
        "ownerAuthenticatedProductApi",
        "revisionSafeMemoryMutation",
        "revisionSafeConversationTombstone",
        "revisionSafeMessageTombstone",
        "revisionSafeScheduleTombstone",
        "searchReconciliationReceipt",
        "recallRebuildReceipt",
        "delayedNonceSweep",
    ],
)
def test_missing_required_capability_fails_closed(capability: str) -> None:
    manifest = valid_manifest()
    manifest["capabilities"][capability] = False

    plan = planner.build_cleanup_plan(manifest)

    assert plan["status"] == "BLOCKED"
    assert f"capability_unavailable:{capability}" in plan["blockers"]


def test_rejects_owner_mismatch() -> None:
    manifest = valid_manifest()
    manifest["items"][0]["ownerId"] = "different_owner"

    with pytest.raises(ValueError, match="item_owner_mismatch"):
        planner.build_cleanup_plan(manifest)


def test_rejects_unreviewed_candidate() -> None:
    manifest = valid_manifest()
    manifest["items"][0]["review"]["classification"] = "possible_synthetic"

    with pytest.raises(ValueError, match="item_not_confirmed_synthetic"):
        planner.build_cleanup_plan(manifest)


def test_rejects_stale_or_substituted_review_binding() -> None:
    manifest = valid_manifest()
    manifest["items"][0]["active"] = True

    with pytest.raises(ValueError, match="review_binding_mismatch"):
        planner.build_cleanup_plan(manifest)


def test_rejects_mixed_conversation_deletion() -> None:
    manifest = valid_manifest()
    item = manifest["items"][1]
    item["contentScope"] = "mixed_preserve_parent"
    item["review"]["bindingSha256"] = planner.review_binding_digest(OWNER_ID, item)

    with pytest.raises(ValueError, match="conversation_not_fully_synthetic"):
        planner.build_cleanup_plan(manifest)


def test_rejects_partial_conversation_proof() -> None:
    manifest = valid_manifest()
    item = manifest["items"][1]
    item["typedSyntheticMessageCount"] = 0
    item["review"]["bindingSha256"] = planner.review_binding_digest(OWNER_ID, item)

    with pytest.raises(ValueError, match="conversation_message_proof_incomplete"):
        planner.build_cleanup_plan(manifest)


def test_rejects_memory_mutation_without_revision() -> None:
    manifest = valid_manifest()
    item = manifest["items"][3]
    del item["expectedRevision"]
    item["review"]["bindingSha256"] = planner.review_binding_digest(OWNER_ID, item)

    with pytest.raises(ValueError, match="memory_revision_required"):
        planner.build_cleanup_plan(manifest)


def test_rejects_mixed_memory_to_preserve_genuine_content() -> None:
    manifest = valid_manifest()
    item = manifest["items"][4]
    item["contentScope"] = "mixed_preserve_genuine"
    item["review"]["bindingSha256"] = planner.review_binding_digest(OWNER_ID, item)

    with pytest.raises(ValueError, match="memory_content_scope_unverified"):
        planner.build_cleanup_plan(manifest)


def test_rejects_duplicate_target() -> None:
    manifest = valid_manifest()
    manifest["items"].append(deepcopy(manifest["items"][0]))

    with pytest.raises(ValueError, match="duplicate_cleanup_target"):
        planner.build_cleanup_plan(manifest)


def test_requires_every_fully_synthetic_conversation_child_as_an_exact_reviewed_target() -> None:
    manifest = valid_manifest()
    del manifest["items"][2]

    with pytest.raises(ValueError, match="conversation_reviewed_child_set_incomplete"):
        planner.build_cleanup_plan(manifest)


def test_orders_reviewed_child_messages_before_their_conversation_tombstone() -> None:
    plan = planner.build_cleanup_plan(valid_manifest())
    mutations = next(
        phase["operations"]
        for phase in plan["phases"]
        if phase["phase"] == "apply_owner_authenticated_product_mutations"
    )
    kinds = [operation["targetKind"] for operation in mutations]

    assert kinds.index("message") < kinds.index("conversation")


def test_rejects_private_freeform_fields_in_manifest() -> None:
    manifest = valid_manifest()
    manifest["items"][0]["title"] = "private synthetic title"

    with pytest.raises(ValueError, match="unexpected_item_fields"):
        planner.build_cleanup_plan(manifest)


def test_rejects_wildcard_or_path_like_target_ids() -> None:
    manifest = valid_manifest()
    manifest["items"][0]["resourceId"] = "../../all"
    manifest["items"][0]["review"]["bindingSha256"] = planner.review_binding_digest(
        OWNER_ID, manifest["items"][0]
    )

    with pytest.raises(ValueError, match="unsafe_resource_id"):
        planner.build_cleanup_plan(manifest)


def test_active_schedule_blocks_cleanup_until_a_new_inactive_snapshot_and_backup_exist() -> None:
    manifest = valid_manifest()
    item = manifest["items"][0]
    item["active"] = True
    item["review"]["bindingSha256"] = planner.review_binding_digest(OWNER_ID, item)
    review_set_sha256 = planner._review_set_digest(manifest["items"])
    receipt = manifest["backup"]["recoveryReceipt"]
    receipt["reviewSetSha256"] = review_set_sha256
    receipt["receiptSha256"] = planner._sha(
        {key: value for key, value in receipt.items() if key != "receiptSha256"}
    )

    plan = planner.build_cleanup_plan(manifest)

    assert plan["status"] == "BLOCKED"
    assert "active_schedule_requires_deactivation_revalidation_and_new_backup" in plan["blockers"]
    assert all(
        not phase["operations"]
        for phase in plan["phases"]
        if phase["phase"] != "verify_private_recovery"
    )


def test_plan_declares_compensating_journal_not_false_global_transaction() -> None:
    plan = planner.build_cleanup_plan(valid_manifest())

    assert plan["mutationPolicy"] == {
        "atomicity": "per_item_revision_or_owner_guarded",
        "crossStore": "journaled_fail_stop_with_verified_compensation",
        "globalTransactionClaimed": False,
    }


def test_plan_binds_real_recovery_receipt_and_exact_reviewed_source_state() -> None:
    manifest = valid_manifest()
    plan = planner.build_cleanup_plan(manifest)
    binding = plan["operationBinding"]
    mutations = next(
        phase["operations"]
        for phase in plan["phases"]
        if phase["phase"] == "apply_owner_authenticated_product_mutations"
    )

    assert binding["backupReceiptSha256"] == manifest["backup"]["recoveryReceipt"][
        "receiptSha256"
    ]
    assert binding["runNonceHash"] == "sha256:" + planner._text_sha(
        manifest["operation"]["runNonce"]
    )
    assert binding["ownerScopeHash"] == planner.owner_scope_hash(OWNER_ID)
    assert all(operation["planSha256"] == binding["planSha256"] for operation in mutations)
    assert all(len(operation["targetHash"]) == len("sha256:") + 64 for operation in mutations)
    assert all(operation["stateSha256"] == operation["preimageSha256"] for operation in mutations)
    assert all(operation["expectedUpdatedAt"].endswith("Z") for operation in mutations)


def test_tampered_recovery_receipt_fails_closed() -> None:
    manifest = valid_manifest()
    manifest["backup"]["recoveryReceipt"]["artifactSetSha256"] = "d" * 64

    with pytest.raises(ValueError, match="backup_receipt_hash_mismatch"):
        planner.build_cleanup_plan(manifest)


def test_changed_review_set_cannot_reuse_an_older_backup() -> None:
    manifest = valid_manifest()
    item = manifest["items"][0]
    item["stateSha256"] = "e" * 64
    item["preimageSha256"] = "e" * 64
    item["review"]["bindingSha256"] = planner.review_binding_digest(OWNER_ID, item)

    with pytest.raises(ValueError, match="backup_review_set_mismatch"):
        planner.build_cleanup_plan(manifest)


def test_rejects_preimage_that_does_not_match_reviewed_state() -> None:
    manifest = valid_manifest()
    item = manifest["items"][0]
    item["preimageSha256"] = "e" * 64
    item["review"]["bindingSha256"] = planner.review_binding_digest(OWNER_ID, item)

    with pytest.raises(ValueError, match="schedule_preimage_state_mismatch"):
        planner.build_cleanup_plan(manifest)


def test_delayed_sweep_cannot_be_scheduled_early() -> None:
    manifest = valid_manifest()
    manifest["operation"]["notBefore"] = "2026-08-25T20:14:59Z"

    with pytest.raises(ValueError, match="cleanup_sweep_delay_too_short"):
        planner.build_cleanup_plan(manifest)


def test_operation_nonce_must_match_every_structured_qa_target() -> None:
    manifest = valid_manifest()
    item = manifest["items"][1]
    item["provenance"]["runNonce"] = "different-qa-run"
    item["review"]["bindingSha256"] = planner.review_binding_digest(OWNER_ID, item)

    with pytest.raises(ValueError, match="cleanup_operation_nonce_source_mismatch"):
        planner.build_cleanup_plan(manifest)


def test_backup_procedure_requires_a_real_isolated_restore_not_a_fake_dry_run() -> None:
    procedure = planner.canonical_json(planner.build_cleanup_plan(valid_manifest())["backupProcedure"])

    assert "isolated temporary namespace" in procedure
    assert "--dryRun" not in procedure


@pytest.mark.parametrize("kind", ["schedule", "conversation", "message", "memory"])
def test_boolean_revision_is_not_accepted_as_an_integer(kind: str) -> None:
    manifest = valid_manifest()
    item = next(candidate for candidate in manifest["items"] if candidate["kind"] == kind)
    item["expectedRevision"] = True
    item["review"]["bindingSha256"] = planner.review_binding_digest(OWNER_ID, item)

    with pytest.raises(ValueError, match=f"{kind}_revision_required|memory_revision_required"):
        planner.build_cleanup_plan(manifest)


def test_private_manifest_loader_rejects_symlink(tmp_path: Path) -> None:
    target = tmp_path / "manifest.json"
    target.write_text(json.dumps(valid_manifest()), encoding="utf-8")
    target.chmod(0o600)
    link = tmp_path / "manifest-link.json"
    link.symlink_to(target)

    with pytest.raises(ValueError, match="private_manifest_must_be_regular_file"):
        planner._load_private_manifest(link)


def test_cli_does_not_echo_unknown_private_field_names(tmp_path: Path, capsys) -> None:
    manifest = valid_manifest()
    private_key = "private-user-text-must-not-echo"
    manifest[private_key] = True
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    path.chmod(0o600)

    assert planner.main(["--manifest", str(path)]) == 2
    output = capsys.readouterr().out
    assert private_key not in output
    assert '"status":"REFUSED"' in output


def test_module_has_no_cleanup_execution_dependencies() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }

    assert not imports & {"subprocess", "pymongo", "requests", "urllib", "sqlite3", "socket"}
    assert "MongoClient(" not in source
    assert "deleteMany(" not in source

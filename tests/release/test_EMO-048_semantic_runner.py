from __future__ import annotations

import base64
import copy
import hashlib
import hmac
import importlib.util
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = ROOT / "qa" / "emotional-cortex" / "scripts" / "run_emo_uc_048.py"
NOW = datetime(2026, 8, 25, 12, 30, tzinfo=timezone.utc)
START = NOW - timedelta(minutes=20)
BOUNDARIES = (
    "cortex_ledger_first_write",
    "web_replay_persistence",
    "web_redis_publish_ack",
    "telegram_promoted_parent_presentation",
)


def _load_runner():
    spec = importlib.util.spec_from_file_location("emo_uc_048_semantic_runner_test", RUNNER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _iso(offset_seconds: int) -> str:
    return (START + timedelta(seconds=offset_seconds)).isoformat(timespec="milliseconds")


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _scope_hash(label: str, value: str) -> str:
    return "sha256:" + _sha(f"{label}\0{value}")


def _js_hash(value: object) -> str:
    return _sha(json.dumps(value, separators=(",", ":"), ensure_ascii=False))


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _event(
    transition: str,
    offset: int,
    *,
    attempt: int,
    generation: int,
    claim_token: str = "",
    reason: str = "",
    surface: str = "",
    receipt_hash: str = "",
    runtime_epoch: str = "",
    claimed_offset: int | None = None,
) -> dict[str, object]:
    main_claim_offsets = {1: 90, 2: 170, 3: 250}
    exact_claim_offset = claimed_offset or main_claim_offsets.get(generation)
    claimed_at = _iso(exact_claim_offset) if exact_claim_offset is not None else None
    lease_expires_at = (
        _iso(exact_claim_offset + 120) if exact_claim_offset is not None else None
    )
    return {
        "attemptNumber": attempt,
        "claimGeneration": generation,
        "claimToken": claim_token,
        "claimedAt": claimed_at,
        "eventAt": _iso(offset),
        "leaseExpiresAt": lease_expires_at,
        "reason": reason,
        "receiptHash": receipt_hash,
        "recoveryAttemptNumber": 0,
        "retryEligibleAt": None,
        "runtimeEpoch": runtime_epoch,
        "runtimeSlot": "slot_" + "7" * 24 if generation > 0 else "",
        "surface": surface,
        "transition": transition,
    }


def _process(service: str, checkpoint: int) -> dict[str, object]:
    stable = checkpoint if service == "librechat-core" else 0
    pid = 4000 + stable if service == "librechat-core" else 5000
    return {
        "executablePath": f"/opt/viventium/{service}",
        "executableSha256": "sha256:" + ("4" if service == "librechat-core" else "5") * 64,
        "pid": pid,
        "startedAt": _iso(5 + checkpoint * 60 if service == "librechat-core" else 5),
        "startMarker": "sha256:" + _sha(f"{service}:{stable}"),
    }


def _ack(
    state: dict[str, object], service: str, checkpoint: int, acknowledged_at: str
) -> dict[str, object]:
    unsigned = {
        "acknowledgedAt": acknowledged_at,
        "artifactIdentityDigest": state["artifactIdentityDigest"],
        "caseId": state["caseId"],
        "componentArtifactDigest": state["componentArtifactDigest"],
        "contractVersion": 1,
        "installedRootHash": state["installedRootHash"],
        "processIdentity": _process(service, checkpoint),
        "serviceId": service,
        "sessionRef": state["sessionRef"],
    }
    token = base64.urlsafe_b64decode(str(state["caseToken"]) + "=")
    proof = hmac.new(token, _canonical(unsigned).encode(), hashlib.sha256).hexdigest()
    return {**unsigned, "proof": "hmac-sha256:" + proof}


class CaseFixture:
    def __init__(self, tmp_path: Path):
        self.root = tmp_path / "private-evidence"
        self.root.mkdir(mode=0o700)
        self.manifest_path = self.root / "capture.json"
        self.receipt_path = self.root / "derived-receipt.json"
        self.docs: dict[str, object] = {}
        token = base64.urlsafe_b64encode(b"k" * 32).decode().rstrip("=")
        self.state: dict[str, object] = {
            "artifactIdentityDigest": "sha256:" + "a" * 64,
            "caseId": "EMO-UC-048",
            "caseToken": token,
            "componentArtifactDigest": "sha256:" + "b" * 64,
            "contractVersion": 1,
            "expiresAt": _iso(3600),
            "installedRootHash": "sha256:" + "c" * 64,
            "mode": "emo_uc_048",
            "modeVariable": "VIVENTIUM_LOCAL_QA_MODE",
            "sessionRef": "qa_" + _sha(token)[:24],
            "startedAt": _iso(0),
        }
        self.owner_id = "1" * 24
        namespace = "2" * 32
        self.conversation_id = f"emo_uc_048_conversation_{namespace}"
        self.parent_id = f"emo_uc_048_parent_{namespace}"
        self.fixture_ref = "emo048_fixture_" + "3" * 24
        self.cortex_id = "emotional-resonance-cortex"
        self.insight = "  A subtle signal: keep the exact words — café.  "
        self.insight_hash = _sha(self.insight)
        identity_hash = _sha(
            "\0".join(
                [self.owner_id, self.parent_id, self.cortex_id, self.insight_hash]
            )
        )
        self.delivery_key = "cortex_insight:" + identity_hash
        self.delivery_id = "cidl_" + identity_hash[:24]
        self.message_id = "emo048_followup_" + "4" * 24

        self.completion = {
            "caseId": "EMO-UC-048",
            "completedAt": _iso(20),
            "completionId": "emo048_completion_" + "5" * 24,
            "conversationId": self.conversation_id,
            "cortexId": self.cortex_id,
            "cortexName": "Emotional Resonance",
            "insight": self.insight,
            "messageRevision": 1,
            "ownerId": self.owner_id,
            "parentMessageId": self.parent_id,
            "persistence": {
                "deliveryPending": True,
                "durableAcceptance": "outbox",
                "graphResultHashes": [self.insight_hash],
                "outboxErrorCode": "cortex_insight_delivery_ledger_write_failed",
                "outboxPending": True,
            },
            "streamId": "emo048_stream_1",
            "surface": "telegram",
        }

        self.controls = self._controls()
        self.restart_record, self.live_status = self._restarts()
        self.persistence, self.presentation = self._persistence_and_presentation()
        self.visibility = self._visibility()
        self.terminal = self._terminal()
        self.docs = {
            "completion-record": self.completion,
            "fault-controls": self.controls,
            "restart-acknowledgements": self.restart_record,
            "persistence-ledger": self.persistence,
            "presentation-records": self.presentation,
            "visibility-records": self.visibility,
            "terminal-outcome": self.terminal,
        }
        self.entries: list[dict[str, str]] = []
        for evidence_id, kind in (
            ("completion-record", "completion_record"),
            ("fault-controls", "fault_controls"),
            ("restart-acknowledgements", "restart_acknowledgements"),
            ("persistence-ledger", "persistence_ledger"),
            ("presentation-records", "presentation_records"),
            ("visibility-records", "visibility_records"),
            ("terminal-outcome", "terminal_outcome"),
        ):
            self._write_json_evidence(evidence_id, kind)
        for evidence_id, kind, payload in (
            ("web-settled", "browser_screenshot", b"synthetic browser settled fixture"),
            ("web-replayed", "browser_screenshot", b"synthetic browser replay fixture"),
            ("telegram-settled", "telegram_screenshot", b"synthetic telegram settled fixture"),
            ("telegram-replayed", "telegram_screenshot", b"synthetic telegram replay fixture"),
        ):
            path = self.root / f"{evidence_id}.png"
            path.write_bytes(payload)
            path.chmod(0o600)
            self.entries.append(
                {
                    "id": evidence_id,
                    "kind": kind,
                    "path": path.name,
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }
            )
        self.capture: dict[str, object] = {
            "capturedAt": _iso(900),
            "caseId": "EMO-UC-048",
            "contractVersion": 1,
            "evidence": self.entries,
            "fixtureRef": self.fixture_ref,
        }
        self._write_manifest()

    def _controls(self) -> dict[str, object]:
        rows: list[dict[str, object]] = []
        consumed_offsets = {
            "cortex_ledger_first_write": 25,
            "web_replay_persistence": 100,
            "web_redis_publish_ack": 101,
            "telegram_promoted_parent_presentation": 180,
        }
        for index, boundary in enumerate(BOUNDARIES):
            armed_at = _iso(10 + index)
            consumed_at = _iso(consumed_offsets[boundary])
            rows.append(
                {
                    "armedAt": armed_at,
                    "audit": [
                        {"at": armed_at, "event": "armed", "sequence": 1},
                        {"at": consumed_at, "event": "consumed", "sequence": 2},
                    ],
                    "boundary": boundary,
                    "consumedAt": consumed_at,
                    "controlId": f"emo048_{boundary.replace('_', '-')}",
                    "conversationScopeHash": _scope_hash(
                        "conversation", self.conversation_id
                    ),
                    "expiresAt": _iso(1200),
                    "ownerScopeHash": _scope_hash("owner", self.owner_id),
                    "parentScopeHash": _scope_hash("parent", self.parent_id),
                    "purgeAt": _iso(2400),
                    "state": "consumed",
                    "syntheticScope": True,
                }
            )
        return {
            "caseId": "EMO-UC-048",
            "controls": rows,
            "fixtureRef": self.fixture_ref,
            "sessionRef": self.state["sessionRef"],
        }

    def _restarts(self) -> tuple[dict[str, object], dict[str, object]]:
        checkpoints = []
        ids = (
            "initial",
            "after-ledger-fault",
            "after-web-faults",
            "after-telegram-fault",
        )
        for index, checkpoint_id in enumerate(ids):
            observed_at = _iso(40 + index * 80)
            checkpoints.append(
                {
                    "coreRuntimeEpoch": f"boot_epoch_{index}",
                    "id": checkpoint_id,
                    "observedAt": observed_at,
                    "services": [
                        _ack(self.state, "librechat-core", index, observed_at),
                        _ack(self.state, "telegram-bot", index, observed_at),
                    ],
                }
            )
        final_services = checkpoints[-1]["services"]
        digest = "sha256:" + _sha(_canonical(final_services))
        live_status = {
            "acknowledgedServices": ["librechat-core", "telegram-bot"],
            "caseId": "EMO-UC-048",
            "expiresAt": self.state["expiresAt"],
            "missingServices": [],
            "mode": "emo_uc_048",
            "requiredServices": ["librechat-core", "telegram-bot"],
            "restartState": "ready",
            "serviceAckDigest": digest,
            "sessionRef": self.state["sessionRef"],
        }
        return (
            {
                "caseId": "EMO-UC-048",
                "checkpoints": checkpoints,
                "sessionRef": self.state["sessionRef"],
            },
            live_status,
        )

    def _row(
        self,
        events: list[dict[str, object]],
        *,
        status: str,
        attempt: int,
        generation: int,
        presented: list[str],
        receipt_hashes: list[str],
    ) -> dict[str, object]:
        persisted = any(event["transition"] == "persisted" for event in events)
        return {
            "attemptNumber": attempt,
            "claimGeneration": generation,
            "claimToken": "",
            "claimedAt": None,
            "conversationId": self.conversation_id,
            "cortexId": self.cortex_id,
            "deliveryId": self.delivery_id,
            "deliveryKey": self.delivery_key,
            "dropReason": "",
            "droppedAt": None,
            "events": copy.deepcopy(events),
            "graphResultHash": self.insight_hash,
            "insight": self.insight,
            "insightHash": self.insight_hash,
            "leaseExpiresAt": None,
            "messageRevision": 1,
            "parentMessageId": self.parent_id,
            "persistedAt": _iso(92) if persisted else None,
            "persistedMessageId": self.message_id if persisted else "",
            "persistenceStatus": "persisted" if persisted else "pending",
            "presentationReceiptHashes": list(receipt_hashes),
            "presentedSurfaces": list(presented),
            "requiredSurfaces": ["web", "telegram"],
            "sentAt": events[-1]["eventAt"] if status == "sent" else None,
            "status": status,
            "streamId": "emo048_stream_1",
            "surface": "telegram",
            "userId": self.owner_id,
        }

    def _persistence_and_presentation(
        self,
    ) -> tuple[dict[str, object], dict[str, object]]:
        claim_1 = "cidl_claim_generation_1"
        claim_2 = "cidl_claim_generation_2"
        claim_3 = "cidl_claim_generation_3"
        lease_2 = "cidl_presentation_lease_2"
        lease_3 = "cidl_presentation_lease_3"
        web_ref = f"durable-replay:{self.message_id}:1"
        telegram_ref = "telegram:synthetic-chat:synthetic-message"
        web_receipt = _js_hash(
            {
                "messageId": self.message_id,
                "presentationRef": web_ref,
                "revision": 1,
                "surface": "web",
                "claimToken": claim_2,
                "claimGeneration": 2,
                "graphResultHash": self.insight_hash,
                "presentationLeaseToken": lease_2,
            }
        )
        telegram_receipt = _js_hash(
            {
                "messageId": self.message_id,
                "presentationRef": telegram_ref,
                "revision": 1,
                "surface": "telegram",
                "claimToken": claim_3,
                "claimGeneration": 3,
                "graphResultHash": self.insight_hash,
                "presentationLeaseToken": lease_3,
            }
        )
        sent_receipt = _js_hash(
            {
                "messageId": self.message_id,
                "presentationReceiptHashes": sorted([web_receipt, telegram_receipt]),
                "revision": 1,
            }
        )
        events = [
            _event("pending", 80, attempt=0, generation=0),
            _event(
                "claimed",
                90,
                attempt=1,
                generation=1,
                claim_token=claim_1,
                runtime_epoch="boot_epoch_1",
            ),
            _event(
                "persisted",
                92,
                attempt=1,
                generation=1,
                claim_token=claim_1,
                receipt_hash=_js_hash(
                    {"messageId": self.message_id, "revision": 1, "stage": "persistence"}
                ),
                runtime_epoch="boot_epoch_1",
            ),
            _event(
                "failure",
                105,
                attempt=1,
                generation=1,
                claim_token=claim_1,
                reason="presentation_failed",
                runtime_epoch="boot_epoch_1",
            ),
            _event(
                "claimed",
                170,
                attempt=2,
                generation=2,
                claim_token=claim_2,
                runtime_epoch="boot_epoch_2",
            ),
            _event(
                "presented",
                175,
                attempt=2,
                generation=2,
                claim_token=claim_2,
                surface="web",
                receipt_hash=web_receipt,
                runtime_epoch="boot_epoch_2",
            ),
            _event(
                "failure",
                185,
                attempt=2,
                generation=2,
                claim_token=claim_2,
                reason="presentation_failed",
                runtime_epoch="boot_epoch_2",
            ),
            _event(
                "claimed",
                250,
                attempt=3,
                generation=3,
                claim_token=claim_3,
                runtime_epoch="boot_epoch_3",
            ),
            _event(
                "presented",
                255,
                attempt=3,
                generation=3,
                claim_token=claim_3,
                surface="telegram",
                receipt_hash=telegram_receipt,
                runtime_epoch="boot_epoch_3",
            ),
            _event(
                "sent",
                256,
                attempt=3,
                generation=3,
                claim_token=claim_3,
                receipt_hash=sent_receipt,
                runtime_epoch="boot_epoch_3",
            ),
        ]
        outbox = {
            "conversationId": self.conversation_id,
            "cortexId": self.cortex_id,
            "graphResultHash": self.insight_hash,
            "insight": self.insight,
            "insightHash": self.insight_hash,
            "messageRevision": 1,
            "outboxKey": self.delivery_key,
            "parentMessageId": self.parent_id,
            "replayAttempts": 0,
            "streamId": "emo048_stream_1",
            "surface": "telegram",
            "userId": self.owner_id,
        }
        after_web = self._row(
            events[:4],
            status="pending",
            attempt=1,
            generation=1,
            presented=[],
            receipt_hashes=[],
        )
        after_telegram = self._row(
            events[:7],
            status="pending",
            attempt=2,
            generation=2,
            presented=["web"],
            receipt_hashes=[web_receipt],
        )
        settled = self._row(
            events,
            status="sent",
            attempt=3,
            generation=3,
            presented=["web", "telegram"],
            receipt_hashes=[web_receipt, telegram_receipt],
        )
        snapshots = [
            {
                "checkpointId": "initial",
                "ledger": [],
                "outbox": [outbox],
                "phase": "after-ledger-fault",
                "recordedAt": _iso(30),
            },
            {
                "checkpointId": "after-ledger-fault",
                "ledger": [after_web],
                "outbox": [],
                "phase": "after-web-faults",
                "recordedAt": _iso(110),
            },
            {
                "checkpointId": "after-web-faults",
                "ledger": [after_telegram],
                "outbox": [],
                "phase": "after-telegram-fault",
                "recordedAt": _iso(190),
            },
            {
                "checkpointId": "after-telegram-fault",
                "ledger": [settled],
                "outbox": [],
                "phase": "settled",
                "recordedAt": _iso(260),
            },
            {
                "checkpointId": "after-telegram-fault",
                "ledger": [copy.deepcopy(settled)],
                "outbox": [],
                "phase": "replayed",
                "recordedAt": _iso(280),
            },
        ]
        records = [
            {
                "claimGeneration": 2,
                "graphResultHash": self.insight_hash,
                "messageId": self.message_id,
                "messageRevision": 1,
                "presentationClaimToken": claim_2,
                "presentationGeneration": 2,
                "presentationLeaseToken": lease_2,
                "presentationRef": web_ref,
                "receiptHash": web_receipt,
                "surface": "web",
                "target": "durable_replay_store",
            },
            {
                "claimGeneration": 3,
                "graphResultHash": self.insight_hash,
                "messageId": self.message_id,
                "messageRevision": 1,
                "presentationClaimToken": claim_3,
                "presentationGeneration": 3,
                "presentationLeaseToken": lease_3,
                "presentationRef": telegram_ref,
                "receiptHash": telegram_receipt,
                "surface": "telegram",
                "target": "promoted_parent_acknowledgement",
            },
        ]
        return (
            {
                "caseId": "EMO-UC-048",
                "deliveryId": self.delivery_id,
                "graphResultHash": self.insight_hash,
                "snapshots": snapshots,
            },
            {
                "caseId": "EMO-UC-048",
                "deliveryId": self.delivery_id,
                "records": records,
            },
        )

    def _visibility(self) -> dict[str, object]:
        generation = {"web": 2, "telegram": 3}
        evidence = {
            ("settled", "web"): "web-settled",
            ("replayed", "web"): "web-replayed",
            ("settled", "telegram"): "telegram-settled",
            ("replayed", "telegram"): "telegram-replayed",
        }
        observations = []
        for phase in ("settled", "replayed"):
            for surface in ("web", "telegram"):
                observations.append(
                    {
                        "count": 1,
                        "deliveryId": self.delivery_id,
                        "exactInsight": self.insight,
                        "graphResultHash": self.insight_hash,
                        "messageId": self.message_id,
                        "messageRevision": 1,
                        "phase": phase,
                        "presentationGeneration": generation[surface],
                        "screenshotEvidenceId": evidence[(phase, surface)],
                        "surface": surface,
                    }
                )
        return {
            "caseId": "EMO-UC-048",
            "deliveryId": self.delivery_id,
            "observations": observations,
        }

    def _terminal(self) -> dict[str, object]:
        insight = "Exact terminal negative insight."
        insight_hash = _sha(insight)
        cortex_id = "emotional-resonance-terminal-probe"
        identity_hash = _sha(
            "\0".join([self.owner_id, self.parent_id, cortex_id, insight_hash])
        )
        delivery_id = "cidl_" + identity_hash[:24]
        events = [
            _event("pending", 300, attempt=0, generation=0),
            _event(
                "claimed",
                301,
                attempt=1,
                generation=1,
                claim_token="cidl_terminal_claim",
                runtime_epoch="boot_epoch_3",
                claimed_offset=301,
            ),
            _event(
                "dropped",
                302,
                attempt=1,
                generation=1,
                claim_token="cidl_terminal_claim",
                reason="conversation_moved_on",
                runtime_epoch="boot_epoch_3",
                claimed_offset=301,
            ),
        ]
        row = {
            "attemptNumber": 1,
            "claimGeneration": 1,
            "claimToken": "",
            "claimedAt": None,
            "conversationId": self.conversation_id,
            "cortexId": cortex_id,
            "deliveryId": delivery_id,
            "deliveryKey": "cortex_insight:" + identity_hash,
            "dropReason": "conversation_moved_on",
            "droppedAt": _iso(302),
            "events": events,
            "graphResultHash": insight_hash,
            "insight": insight,
            "insightHash": insight_hash,
            "leaseExpiresAt": None,
            "messageRevision": 1,
            "parentMessageId": self.parent_id,
            "persistedAt": None,
            "persistedMessageId": "",
            "persistenceStatus": "pending",
            "presentationReceiptHashes": [],
            "presentedSurfaces": [],
            "requiredSurfaces": ["web", "telegram"],
            "sentAt": None,
            "status": "dropped",
            "streamId": "emo048_terminal_stream",
            "surface": "telegram",
            "userId": self.owner_id,
        }
        return {
            "caseId": "EMO-UC-048",
            "completion": {
                "conversationId": self.conversation_id,
                "cortexId": cortex_id,
                "insight": insight,
                "messageRevision": 1,
                "ownerId": self.owner_id,
                "parentMessageId": self.parent_id,
                "streamId": "emo048_terminal_stream",
                "surface": "telegram",
            },
            "presentationRecords": [],
            "replayed": {"ledger": [copy.deepcopy(row)], "outbox": []},
            "settled": {"ledger": [row], "outbox": []},
            "visibleCounts": {"telegram": 0, "web": 0},
        }

    def _write_json_evidence(self, evidence_id: str, kind: str) -> None:
        path = self.root / f"{evidence_id}.json"
        raw = (json.dumps(self.docs[evidence_id], indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode()
        path.write_bytes(raw)
        path.chmod(0o600)
        self.entries.append(
            {
                "id": evidence_id,
                "kind": kind,
                "path": path.name,
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )

    def _write_manifest(self) -> None:
        raw = (json.dumps(self.capture, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode()
        self.manifest_path.write_bytes(raw)
        self.manifest_path.chmod(0o600)

    def rewrite(self, evidence_id: str) -> None:
        entry = next(item for item in self.entries if item["id"] == evidence_id)
        path = self.root / entry["path"]
        raw = (json.dumps(self.docs[evidence_id], indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode()
        path.write_bytes(raw)
        path.chmod(0o600)
        entry["sha256"] = hashlib.sha256(raw).hexdigest()
        self._write_manifest()


@pytest.fixture
def case(tmp_path: Path) -> CaseFixture:
    return CaseFixture(tmp_path)


def _verify(case: CaseFixture, **overrides):
    runner = _load_runner()
    arguments = {
        "capture_path": case.manifest_path,
        "evidence_root": case.root,
        "session_state": case.state,
        "live_status": case.live_status,
        "live_controls": case.controls,
        "receipt_path": case.receipt_path,
        "now": NOW,
    }
    arguments.update(overrides)
    return runner.verify_capture(**arguments)


def test_valid_capture_derives_pass_and_private_receipt(case: CaseFixture) -> None:
    result = _verify(case)

    assert result["status"] == "PASS"
    assert result["failureCodes"] == []
    assert {check["id"] for check in result["checks"]} == {
        "active-local-qa-authority",
        "all-four-fault-boundaries",
        "exact-insight-identity",
        "restart-service-acknowledgements",
        "append-only-persistence-ledger",
        "exact-presentation-receipts",
        "exactly-once-linked-visibility",
        "typed-terminal-outcome",
    }
    receipt = json.loads(case.receipt_path.read_text())
    assert receipt["status"] == "PASS"
    assert receipt["caseId"] == "EMO-UC-048"
    assert receipt["surface"] == "telegram"
    assert set(receipt) == {
        "caseId",
        "contractVersion",
        "evidence",
        "runAt",
        "status",
        "surface",
        "verifier",
    }
    assert receipt["verifier"] == {
        "id": "emo048-semantic-v1",
        "manifest": "capture.json",
    }
    assert stat_mode(case.receipt_path) == 0o600
    rendered = json.dumps(result, sort_keys=True)
    assert case.insight not in rendered
    assert case.owner_id not in rendered
    assert str(case.root) not in rendered


def stat_mode(path: Path) -> int:
    return path.stat().st_mode & 0o777


def test_capture_cannot_declare_its_own_status(case: CaseFixture) -> None:
    case.capture["status"] = "PASS"
    case._write_manifest()

    result = _verify(case)

    assert result == {
        "caseId": "EMO-UC-048",
        "checks": [],
        "failureCodes": ["capture-contract-invalid"],
        "status": "BLOCKED",
    }
    assert not case.receipt_path.exists()


def test_registered_adapter_rederives_pass_and_rejects_result_tampering(
    case: CaseFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = _load_runner()
    monkeypatch.setattr(
        runner,
        "probe_live_authority",
        lambda: (case.state, case.live_status, case.controls),
    )
    manifest = json.loads(case.manifest_path.read_text())

    result = runner.assess_manifest(
        manifest,
        evidence_root=case.root,
        expected_candidate_digest="8" * 64,
        expected_artifact_digest="9" * 64,
        installed_owner_proven=True,
        now=NOW,
    )
    derived = runner.receipt_manifest(result=result)

    assert derived["status"] == "PASS"
    assert set(derived) == {
        "caseId",
        "contractVersion",
        "evidence",
        "runAt",
        "status",
        "surface",
    }
    result["status"] = "FAIL"
    with pytest.raises(ValueError, match="derived PASS is invalid"):
        runner.receipt_manifest(result=result)


def test_registered_adapter_requires_installed_owner_binding(
    case: CaseFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = _load_runner()
    monkeypatch.setattr(
        runner,
        "probe_live_authority",
        lambda: (case.state, case.live_status, case.controls),
    )

    with pytest.raises(ValueError, match="installed candidate binding is invalid"):
        runner.assess_manifest(
            json.loads(case.manifest_path.read_text()),
            evidence_root=case.root,
            expected_candidate_digest="8" * 64,
            expected_artifact_digest="9" * 64,
            installed_owner_proven=False,
            now=NOW,
        )


@pytest.mark.parametrize("boundary", BOUNDARIES)
def test_every_fault_boundary_must_have_one_consumed_audit(
    case: CaseFixture, boundary: str
) -> None:
    controls = case.docs["fault-controls"]
    assert isinstance(controls, dict)
    controls["controls"] = [
        row for row in controls["controls"] if row["boundary"] != boundary
    ]
    case.rewrite("fault-controls")
    case.controls = copy.deepcopy(controls)

    result = _verify(case, live_controls=case.controls)

    assert result["status"] == "FAIL"
    assert "fault-boundaries-invalid" in result["failureCodes"]


@pytest.mark.parametrize(
    ("evidence_id", "mutate"),
    [
        (
            "persistence-ledger",
            lambda document: document["snapshots"][0]["outbox"][0].__setitem__(
                "insight", "normalized instead of exact"
            ),
        ),
        (
            "persistence-ledger",
            lambda document: document["snapshots"][2]["ledger"][0].__setitem__(
                "graphResultHash", "0" * 64
            ),
        ),
        (
            "presentation-records",
            lambda document: document["records"][0].__setitem__(
                "messageId", "different-message"
            ),
        ),
        (
            "visibility-records",
            lambda document: document["observations"][0].__setitem__(
                "exactInsight", "different visible text"
            ),
        ),
    ],
)
def test_identity_must_match_at_every_boundary(
    case: CaseFixture, evidence_id: str, mutate
) -> None:
    mutate(case.docs[evidence_id])
    case.rewrite(evidence_id)

    result = _verify(case)

    assert result["status"] == "FAIL"
    assert set(result["failureCodes"]) & {
        "insight-identity-invalid",
        "persistence-ledger-invalid",
        "presentation-records-invalid",
        "visibility-invalid",
    }


def test_restart_checkpoints_require_fresh_core_process_and_valid_hmac(
    case: CaseFixture,
) -> None:
    restart = case.docs["restart-acknowledgements"]
    assert isinstance(restart, dict)
    checkpoints = restart["checkpoints"]
    checkpoints[2]["services"][0]["processIdentity"] = copy.deepcopy(
        checkpoints[1]["services"][0]["processIdentity"]
    )
    case.rewrite("restart-acknowledgements")

    result = _verify(case)

    assert result["status"] == "FAIL"
    assert "restart-acknowledgements-invalid" in result["failureCodes"]


def test_live_service_ack_digest_must_match_final_checkpoint(case: CaseFixture) -> None:
    status = {**case.live_status, "serviceAckDigest": "sha256:" + "0" * 64}

    result = _verify(case, live_status=status)

    assert result["status"] == "BLOCKED"
    assert "live-authority-mismatch" in result["failureCodes"]


def test_ledger_history_must_be_append_only_and_replay_a_noop(case: CaseFixture) -> None:
    persistence = case.docs["persistence-ledger"]
    assert isinstance(persistence, dict)
    persistence["snapshots"][-1]["ledger"][0]["events"].append(
        copy.deepcopy(persistence["snapshots"][-1]["ledger"][0]["events"][-1])
    )
    case.rewrite("persistence-ledger")

    result = _verify(case)

    assert result["status"] == "FAIL"
    assert "persistence-ledger-invalid" in result["failureCodes"]


def test_ledger_events_must_keep_the_exact_claim_fence(case: CaseFixture) -> None:
    persistence = case.docs["persistence-ledger"]
    assert isinstance(persistence, dict)
    for snapshot in persistence["snapshots"][1:]:
        snapshot["ledger"][0]["events"][2]["claimedAt"] = _iso(91)
    case.rewrite("persistence-ledger")

    result = _verify(case)

    assert result["status"] == "FAIL"
    assert "persistence-ledger-invalid" in result["failureCodes"]


def test_presentation_receipt_hash_is_recomputed_not_trusted(case: CaseFixture) -> None:
    presentation = case.docs["presentation-records"]
    assert isinstance(presentation, dict)
    presentation["records"][1]["presentationLeaseToken"] = "forged-lease"
    case.rewrite("presentation-records")

    result = _verify(case)

    assert result["status"] == "FAIL"
    assert "presentation-records-invalid" in result["failureCodes"]


def test_each_linked_surface_must_show_exactly_one_item_after_replay(
    case: CaseFixture,
) -> None:
    visibility = case.docs["visibility-records"]
    assert isinstance(visibility, dict)
    visibility["observations"][-1]["count"] = 2
    case.rewrite("visibility-records")

    result = _verify(case)

    assert result["status"] == "FAIL"
    assert "visibility-invalid" in result["failureCodes"]


def test_terminal_negative_requires_one_typed_drop_and_no_presentation(
    case: CaseFixture,
) -> None:
    terminal = case.docs["terminal-outcome"]
    assert isinstance(terminal, dict)
    terminal["visibleCounts"]["telegram"] = 1
    case.rewrite("terminal-outcome")

    result = _verify(case)

    assert result["status"] == "FAIL"
    assert "terminal-outcome-invalid" in result["failureCodes"]


def test_evidence_digest_and_private_path_are_measured(case: CaseFixture) -> None:
    entry = next(item for item in case.entries if item["id"] == "completion-record")
    entry["sha256"] = "0" * 64
    case._write_manifest()

    result = _verify(case)

    assert result["status"] == "BLOCKED"
    assert result["failureCodes"] == ["evidence-invalid"]


def test_cli_uses_live_probe_and_never_accepts_status_argument(
    case: CaseFixture, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    runner = _load_runner()
    monkeypatch.setattr(
        runner,
        "probe_live_authority",
        lambda: (case.state, case.live_status, case.controls),
    )
    monkeypatch.setattr(runner, "_utc_now", lambda: NOW)

    exit_code = runner.main(
        [
            "--capture",
            str(case.manifest_path),
            "--evidence-root",
            str(case.root),
            "--receipt",
            str(case.receipt_path),
        ]
    )
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert output["status"] == "PASS"
    assert case.insight not in json.dumps(output)
    assert (
        runner.main(
            [
                "--capture",
                str(case.manifest_path),
                "--evidence-root",
                str(case.root),
                "--receipt",
                str(case.receipt_path),
                "--status",
                "PASS",
            ]
        )
        == 2
    )
    error = capsys.readouterr().err
    assert "PASS" not in error
    assert str(case.manifest_path) not in error


def test_live_probe_failure_is_blocked_without_a_receipt(
    case: CaseFixture, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    runner = _load_runner()

    def unavailable():
        raise ValueError("private runtime path must not leak")

    monkeypatch.setattr(runner, "probe_live_authority", unavailable)
    case.receipt_path.unlink(missing_ok=True)

    exit_code = runner.main(
        [
            "--capture",
            str(case.manifest_path),
            "--evidence-root",
            str(case.root),
            "--receipt",
            str(case.receipt_path),
        ]
    )
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert output["status"] == "BLOCKED"
    assert output["failureCodes"] == ["live-authority-unavailable"]
    assert not case.receipt_path.exists()

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT.joinpath(
    "qa", "parallel-orchestrator", "scripts", "run_pwk_uc_019_installed_journey.cjs"
)
FIXTURES = ROOT.joinpath(
    "qa", "parallel-orchestrator", "scripts", "run_pwk_uc_019_installed_journey.test.cjs"
)
VERIFIER = ROOT.joinpath(
    "qa", "parallel-orchestrator", "scripts", "installed_journey_qa.py"
)


def _load_verifier():
    spec = importlib.util.spec_from_file_location("pwk_installed_journey_qa", VERIFIER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _signed_native_attestations(
    unsigned: list[dict[str, object]],
) -> list[dict[str, object]]:
    script = r"""
const crypto = require('node:crypto');
const fs = require('node:fs');
const payloads = JSON.parse(fs.readFileSync(0, 'utf8'));
const canonical = (value) => Array.isArray(value)
  ? '[' + value.map(canonical).join(',') + ']'
  : value && typeof value === 'object'
    ? '{' + Object.keys(value).sort().map((key) => JSON.stringify(key) + ':' + canonical(value[key])).join(',') + '}'
    : JSON.stringify(value);
const keys = {
  'core.native_receipt': crypto.generateKeyPairSync('ed25519'),
  'glasshive.native_provider_receipt': crypto.generateKeyPairSync('ed25519'),
};
const results = payloads.map((payload) => {
  const pair = keys[payload.producer];
  const publicDer = pair.publicKey.export({type: 'spki', format: 'der'});
  payload.keyId = crypto.createHash('sha256').update(publicDer).digest('hex');
  const proof = 'ed25519:' + crypto.sign(null, Buffer.from(canonical(payload)), pair.privateKey).toString('base64url');
  return {publicKeySpki: publicDer.toString('base64url'), attestation: {...payload, proof}};
});
process.stdout.write(JSON.stringify(results));
"""
    result = subprocess.run(
        ["node", "-e", script],
        input=json.dumps(unsigned),
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(result.stdout)


def test_pwk_uc_019_dry_run_is_inert_and_never_release_ready(tmp_path: Path) -> None:
    unused = tmp_path / "must-not-be-created"
    result = subprocess.run(
        ["node", str(RUNNER), "--dry-run"],
        cwd=ROOT,
        env={"PATH": os.environ.get("PATH", ""), "VIVENTIUM_QA_PRIVATE_DIR": str(unused)},
        capture_output=True,
        text=True,
        check=True,
    )

    payload = json.loads(result.stdout)
    assert payload["caseId"] == "PWK-UC-019"
    assert payload["status"] == "DRY_RUN"
    assert payload["releaseLabel"] == "PRE-GATE / NOT READY"
    assert payload["releaseReady"] is False
    assert payload["receiptEligible"] is False
    assert payload["sideEffects"] is False
    assert payload["launchesBrowser"] is False
    assert payload["invokesModels"] is False
    assert not unused.exists()


def test_pwk_uc_019_fixture_suite_proves_capability_and_security_behavior() -> None:
    result = subprocess.run(
        ["node", "--no-warnings", "--test", str(FIXTURES)],
        cwd=ROOT,
        env={"PATH": os.environ.get("PATH", "")},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "fail 0" in result.stdout


def test_pwk_uc_019_semantic_verifier_covers_all_25_guards_and_cleanup() -> None:
    verifier = _load_verifier()
    required = verifier.CASE_CHECKS["PWK-UC-019"]

    assert len(required) == 25
    assert required == {
        "installed-identity",
        "audible-call",
        "linked-chat",
        "active-work-ui",
        "telegram-attachment-ingress",
        "exact-input-hashes-and-order",
        "memory-and-recall",
        "connected-or-broker-tool",
        "two-distinct-missions",
        "main-responsive-quick-turn",
        "spoken-steer-a-only",
        "hangup-and-reconnect",
        "callback-delivery-once",
        "two-distinct-artifacts",
        "two-headed-browser-windows",
        "passive-wing-denial",
        "listen-only-denial",
        "redacted-end-to-end-trace",
        "request-pinned-feelings-parity",
        "native-provider-receipts",
        "configured-provider-fallback-truth",
        "authorized-browser-computer-parity",
        "owner-scoped-connected-account-permissions",
        "queue-message-worker-reuse",
        "synthetic-owner-zero-residue",
    }
    assert verifier.CASE_EVIDENCE_MINIMUMS["PWK-UC-019"]["cleanup_receipt"] == 1
    assert verifier.CHECK_EVIDENCE_KINDS["synthetic-owner-zero-residue"] == {
        "cleanup_receipt"
    }


def test_pwk_uc_019_python_verifier_checks_native_signatures_and_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verifier = _load_verifier()
    node_path = subprocess.run(
        ["node", "-p", "process.execPath"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    monkeypatch.setenv("VIVENTIUM_QA_NODE_EXECUTABLE", node_path)
    now = datetime.now(timezone.utc)
    now_ms = int(now.timestamp() * 1000)
    owner = _hash("synthetic-owner")
    capsule = _hash("request-pinned-feelings")
    provider = _hash("configured-provider")
    model = _hash("configured-model")
    works = [_hash("work-a"), _hash("work-b")]
    runs = [_hash("run-a"), _hash("run-b")]
    runtime = {
        "works": {work: {} for work in works},
        "runs": {
            run: {"workRefHash": work} for run, work in zip(runs, works, strict=True)
        },
    }

    def unsigned(actor: str, ordinal: int | None) -> dict[str, object]:
        is_worker = ordinal is not None
        return {
            "contractVersion": 1,
            "producer": (
                "glasshive.native_provider_receipt"
                if is_worker
                else "core.native_receipt"
            ),
            "keyId": "replaced-by-signer",
            "actor": actor,
            "ownerRefHash": owner,
            "surface": "voice",
            "workRefHash": works[ordinal] if is_worker else None,
            "runRefHash": runs[ordinal] if is_worker else None,
            "snapshotHash": capsule,
            "nativeRequestSha256": _hash(f"request-{ordinal}"),
            "providerAttemptRefHash": _hash(f"attempt-{ordinal}"),
            "providerRefHash": provider,
            "modelRefHash": model,
            "capsuleOccurrenceCount": 1,
            "issuedAtMs": now_ms - 1000,
            "expiresAtMs": now_ms + 60000,
        }

    records = _signed_native_attestations(
        [unsigned("main", None), unsigned("worker", 0), unsigned("worker", 1)]
    )
    route_truth = {
        "originSurface": "voice",
        "configured": [{"providerRefHash": provider, "modelRefHash": model}],
        "attempts": [
            {
                "providerRefHash": provider,
                "modelRefHash": model,
                "outcome": "used",
                "observed": True,
                "fallback": False,
            }
        ],
    }
    verifier._native_producer_attestation_proof(
        records,
        owner=owner,
        origin="voice",
        feelings_capsule=capsule,
        runtime=runtime,
        route_receipt={
            "modelRefHash": model,
            "providerAttemptRefHash": _hash("attempt-None"),
        },
        route_truth=route_truth,
        now=now,
    )
    forged = json.loads(json.dumps(records))
    forged[0]["attestation"]["ownerRefHash"] = _hash("another-owner")
    with pytest.raises(ValueError, match="attestation"):
        verifier._native_producer_attestation_proof(
            forged,
            owner=owner,
            origin="voice",
            feelings_capsule=capsule,
            runtime=runtime,
            route_receipt={
                "modelRefHash": model,
                "providerAttemptRefHash": _hash("attempt-None"),
            },
            route_truth=route_truth,
            now=now,
        )

    cleanup = [
        {
            "kind": "cleanup_receipt",
            "_payload": {
                "ownerRefHash": owner,
                "zeroResidue": True,
                "completedAt": now.isoformat(),
            },
        }
    ]
    verifier._cleanup_proof(cleanup, case_id="PWK-UC-019", owner=owner, now=now)
    cleanup[0]["_payload"]["zeroResidue"] = False
    with pytest.raises(ValueError, match="zero residue"):
        verifier._cleanup_proof(
            cleanup, case_id="PWK-UC-019", owner=owner, now=now
        )


def test_pwk_uc_019_requires_genuine_installed_native_capability_and_surface_receipts() -> None:
    source = RUNNER.read_text(encoding="utf-8")

    for required in (
        "createEphemeralBrowserSession",
        "assertEphemeralSessionSafety",
        "assessRuntimeOverlap",
        "assessTerminalDeliveries",
        "assessFeelingsParity",
        "assessRouteParity",
        "assessCapabilityParity",
        "assessAttachmentParity",
        "assessControlParity",
        "assessVoiceJourney",
        "assessSurfaceDenials",
        "assessArtifactParity",
        "assessImmutableTrace",
        "cleanupSyntheticResidue",
        "installed_journey_qa.py",
        "native_provider_receipt",
        "saved_memory",
        "conversation_recall",
        "connected_account",
        "selectedByModel",
        "passive_wing",
        "listen_only",
        "headless: false",
        "readOnly: true",
    ):
        assert required in source, required


def test_pwk_uc_019_hard_gates_owner_privacy_consent_and_sky_desktop_auth() -> None:
    source = RUNNER.read_text(encoding="utf-8")

    for required in (
        "VIVENTIUM_QA_ALLOW_PWK_UC_019",
        "VIVENTIUM_QA_ALLOW_SYNTHETIC_FIXTURES",
        "VIVENTIUM_QA_ALLOW_LOCAL_JWT",
        "VIVENTIUM_QA_ALLOW_PWK_UC_019_COMPUTER",
        "VIVENTIUM_QA_OWNER_EMAIL",
        "VIVENTIUM_QA_EMAIL",
        "VIVENTIUM_QA_ALLOW_COORDINATED_RESTART",
        "personal_owner_account_refused",
        "synthetic_cleanup_residue_detected",
        "authenticateParentComputerAuthority",
        "assertProductionDesktopAuthority",
        "assertTrustedComputerAdapter",
        "observeTrustedComputer",
        "desktopAuthority",
        "unitTestHarness",
        "telegramUserId",
        "telegramChatId",
        "accountLabel",
        "chatLabel",
        "@oai/sky",
        "get_app_state",
        "press_key",
        "0o700",
        "0o600",
    ):
        assert required in source, required

    forbidden = (
        "at least 20 seconds",
        "both with the light resource class",
        "VIVENTIUM_QA_PASSWORD",
        "localStorage.setItem",
        "recentChat",
        "conversationHistory",
        "@oai/sky.do_action",
        "createHmac",
        "desktopAdapterSecret",
    )
    assert all(item not in source for item in forbidden)


def test_pwk_uc_019_denies_unapproved_live_execution_before_installed_access() -> None:
    result = subprocess.run(
        ["node", str(RUNNER), "--live"],
        cwd=ROOT,
        env={"PATH": os.environ.get("PATH", "")},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    payload = json.loads(result.stdout)
    assert payload["caseId"] == "PWK-UC-019"
    assert payload["status"] == "BLOCKED"
    assert payload["releaseReady"] is False

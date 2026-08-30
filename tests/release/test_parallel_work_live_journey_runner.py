from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT.joinpath(
    "qa", "parallel-orchestrator", "scripts", "run_installed_parallel_work_journey.cjs"
)
RUNNER_TESTS = ROOT.joinpath(
    "qa", "parallel-orchestrator", "scripts", "run_installed_parallel_work_journey.test.cjs"
)


def test_installed_journey_is_an_executable_user_trigger_not_the_existing_verifier() -> None:
    source = RUNNER.read_text(encoding="utf-8")

    assert "executeInstalledJourney" in source
    assert "submitParallelRequest" in source
    assert "submitAndObserve" in source
    assert "waitForConcurrentWorkers" in source
    assert "steerFirstWorker" in source
    assert "openArtifactWindows" in source
    assert "headless: false" in source
    assert "page.waitForResponse" in source
    assert '"/api/auth/refresh"' in source
    assert "node:sqlite" in source
    assert "readOnly: true" in source
    assert "runtime_invoked_at" in source
    assert "host_run_leases" in source
    assert "callback_outbox" in source
    assert "active_work_action_uses" in source


def test_installed_journey_fails_closed_for_identity_privacy_and_missing_native_telegram() -> None:
    source = RUNNER.read_text(encoding="utf-8")

    for required in (
        "VIVENTIUM_QA_ALLOW_INSTALLED_PARALLEL_WORK",
        "VIVENTIUM_QA_ALLOW_DIAGNOSTIC_CANDIDATE",
        "VIVENTIUM_QA_OWNER_EMAIL",
        "VIVENTIUM_QA_ALLOW_LOCAL_JWT",
        "VIVENTIUM_QA_EMAIL",
        "JWT_SECRET",
        "JWT_REFRESH_SECRET",
        "createEphemeralBrowserSession",
        "personal_owner_account_refused",
        "admin_account_refused",
        "private_evidence_must_stay_outside_repository",
        "installed_candidate_identity_unproven",
        "telegram_native_revision_proof_unavailable",
        "diagnostic_candidate_requires_explicit_opt_in",
        "diagnostic_active_runtime_identity_unproven",
        "diagnostic_candidate_cannot_close_release_gate",
        "PRE-GATE / NOT READY",
    ):
        assert required in source

    assert "0o700" in source
    assert "0o600" in source
    assert "releaseReady: false" in source
    assert "receiptEligible: false" in source
    assert "updatedAt" not in source
    assert "VIVENTIUM_QA_PASSWORD" not in source
    assert "localStorage.setItem" not in source
    assert "maxRedirects: 0" in source


def test_installed_journey_dry_run_has_zero_live_side_effects(tmp_path: Path) -> None:
    nonexistent = tmp_path / "must-not-be-created"
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "VIVENTIUM_QA_PRIVATE_DIR": str(nonexistent),
    }
    result = subprocess.run(
        ["node", str(RUNNER), "--dry-run"],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=True,
    )

    payload = json.loads(result.stdout)
    assert payload["caseId"] == "PWK-UC-014"
    assert payload["status"] == "DRY_RUN"
    assert payload["sideEffects"] is False
    assert payload["launchesBrowser"] is False
    assert payload["invokesModels"] is False
    assert not nonexistent.exists()


def test_installed_journey_rejects_unapproved_live_execution_before_database_access() -> None:
    result = subprocess.run(
        ["node", str(RUNNER), "--live"],
        cwd=ROOT,
        env={"PATH": os.environ.get("PATH", "")},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "missing_required_argument" in result.stderr


def test_installed_journey_fixture_suite_covers_runtime_truth_and_owner_isolation() -> None:
    result = subprocess.run(
        ["node", "--no-warnings", "--test", str(RUNNER_TESTS)],
        cwd=ROOT,
        env={"PATH": os.environ.get("PATH", "")},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "fail 0" in result.stdout


def test_installed_runner_covers_each_exact_catalog_case_without_generic_reuse() -> None:
    source = RUNNER.read_text(encoding="utf-8")

    for case_id, scenario in {
        "PWK-UC-014": "original-parallel-html",
        "PWK-UC-015": "restart-continuity",
        "PWK-UC-016": "capacity-provider-recovery",
        "PWK-UC-017": "callback-artifact-recovery",
        "PWK-UC-018": "owner-artifact-isolation",
    }.items():
        assert case_id in source
        assert scenario in source

    for required in (
        "--case",
        "runRestartContinuityJourney",
        "runCapacityProviderRecoveryJourney",
        "runCallbackArtifactRecoveryJourney",
        "runOwnerArtifactIsolationJourney",
        "assertRestartReadiness",
        "assertAuthenticatedRestartStatus",
        "restart_case_service_acknowledgements_unsupported",
        "deriveAtomicReservationAttempts",
        "deriveQueueTimeoutTransitions",
        "signScopedCallbackPayload",
        "signed_cross_owner_callback_was_not_denied_by_owner_binding",
        "VIVENTIUM_QA_ALLOW_COORDINATED_RESTART",
        "VIVENTIUM_QA_ALLOW_GLASSHIVE_FAULTS",
        "qa-control",
        "prepare-glasshive",
        "cleanup-glasshive",
    ):
        assert required in source

    for method in (
        "runRestartContinuityJourney",
        "runCapacityProviderRecoveryJourney",
        "runCallbackArtifactRecoveryJourney",
        "runOwnerArtifactIsolationJourney",
    ):
        assert f"async {method}(" in source


def test_installed_runner_never_restarts_services_without_external_operator_action() -> None:
    source = RUNNER.read_text(encoding="utf-8")

    assert "restart_operator_readiness_proof_unavailable" in source
    assert "externally_coordinated_restart_not_observed" in source
    assert "service_restart_process_change_unproven" in source
    assert '"dev-runtime", "activate-current"' not in source
    assert '"stop"' not in source


def test_original_user_request_never_manufactures_runtime_overlap() -> None:
    source = RUNNER.read_text(encoding="utf-8")

    forbidden = (
        "keep each actual runtime active",
        "at least 20 seconds",
        "both with the light resource class",
        "Start both immediately",
    )
    assert all(value not in source for value in forbidden)


def test_fault_proof_uses_real_durable_records_instead_of_imaginary_runtime_fields() -> None:
    source = RUNNER.read_text(encoding="utf-8")

    assert "local_qa_fault_controls" in source
    assert "preDispatchFailureCode" in source
    assert "reservedMemoryBytes" in source
    assert "run.capacity_reservation_race" not in source
    assert "payload.previousState" not in source
    assert "payload.waitState" not in source

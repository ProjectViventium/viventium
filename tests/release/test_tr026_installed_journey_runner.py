from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
QA_OWNER = ROOT / "qa/telegram-runtime/cases.md"
QA_CASE = "TR-026"
RUNNER = ROOT / "qa/telegram-runtime/scripts/run_tr026_installed_journey.cjs"
NODE_TESTS = ROOT / "qa/telegram-runtime/scripts/run_tr026_installed_journey.test.cjs"
VERIFIER = ROOT / "qa/telegram-runtime/scripts/tr026_installed_journey_semantic_verifier.py"


def run_node(*arguments: str, environment: dict[str, str] | None = None):
    return subprocess.run(
        ["node", str(RUNNER), *arguments],
        cwd=ROOT,
        env={"PATH": os.environ.get("PATH", ""), **(environment or {})},
        text=True,
        capture_output=True,
        check=False,
        timeout=20,
    )


def test_runner_explicitly_belongs_to_the_existing_telegram_runtime_tr026_case() -> None:
    assert f"## Case {QA_CASE}: Rapid Segments Supersede One Unfinished Reply" in QA_OWNER.read_text(
        encoding="utf-8"
    )
    assert RUNNER.parent == QA_OWNER.parent / "scripts"


def test_runner_is_a_real_installed_telegram_trigger_separate_from_semantic_verifier() -> None:
    assert RUNNER != VERIFIER
    source = RUNNER.read_text(encoding="utf-8")

    for required in (
        "executeInstalledJourney",
        "createInstalledDriver",
        "probeTelegramIdentity",
        "sendTelegramSegment",
        "observeTrustedIngress",
        "buildArmScope",
        "armTelegramRace",
        "observeRapidRevision",
        "observePostCommitControl",
        "assessWorkersUnaffected",
        "auditTelegramRace",
        "verifyIndependentEvidence",
        "tr026_installed_journey_semantic_verifier.py",
        "assertComputerDesktopDriver",
        "assertOwnerScopedTelegramChatBinding",
        "assertIndependentObserverReady",
        "@oai/sky",
        "authenticateParentComputerAuthority",
        "readOwnerBoundComputerState",
        "performOwnerBoundComputerAction",
        "telegram.send_text",
        "telegram.reopen_conversation",
        "viventiumtelegramingressevents",
        "telegramChatBinding",
        "node:sqlite",
        "readOnly: true",
    ):
        assert required in source


def test_runner_requires_independent_consents_exact_owner_scope_and_authentic_280ms_control() -> None:
    source = RUNNER.read_text(encoding="utf-8")

    for required in (
        "VIVENTIUM_QA_ALLOW_TR026_INSTALLED_JOURNEY",
        "VIVENTIUM_QA_ALLOW_TR026_TELEGRAM_MUTATION",
        "VIVENTIUM_QA_ALLOW_TR026_RUNTIME_RESTART",
        "VIVENTIUM_QA_OWNER_EMAIL",
        "VIVENTIUM_QA_OWNER_TELEGRAM_USER_ID",
        "VIVENTIUM_QA_OWNER_TELEGRAM_CHAT_ID",
        "personal_owner_account_refused",
        "personal_telegram_account_refused",
        "personal_telegram_chat_refused",
        "trusted_telegram_ingress_binding_invalid",
        "qa-control",
        "activate",
        "arm-telegram-race",
        "audit-telegram-race",
        "cleanup-telegram-race",
        "--allow-protected-folder",
        "--allow-dirty-local-testing",
        "runtime_restart_dirty_checkout_protection_required",
        "staleSourceSequence",
        "sourceSequence",
        "updateId",
        "280",
        "source_order_superseded",
    ):
        assert required in source


def test_runner_fails_closed_and_cannot_fabricate_database_writes_messages_or_receipts() -> None:
    source = RUNNER.read_text(encoding="utf-8")

    for required in (
        "independent_installed_evidence_producer_unavailable",
        "independent_semantic_verifier_evidence_unavailable",
        "computer_plugin_desktop_driver_unavailable",
        "original_telegram_user_messages_missing",
        "emoji_leading_revised_reply_required",
        "stale_first_reply_visible",
        "post_commit_normal_follow_up_unproven",
        "two_owner_scoped_workers_affected",
        "releaseReady: false",
        "receiptEligible: false",
        "0o700",
        "0o600",
    ):
        assert required in source

    for forbidden in (
        "insertOne(",
        "insertMany(",
        "updateOne(",
        "updateMany(",
        "deleteOne(",
        "deleteMany(",
        "findOneAndUpdate(",
        "sendMessage(",
        "api.telegram.org",
        "osascript",
        "AppleScript",
        "System Events",
        "screencapture",
        "keystroke",
        "AXPress",
        "xdotool",
        "robotjs",
        "--receipt-manifest",
        "receipt_manifest(",
        "_proof(",
        "caseToken:",
    ):
        assert forbidden not in source


def test_dry_run_is_inert_and_does_not_create_private_state(tmp_path: Path) -> None:
    untouched = tmp_path / "must-not-exist"
    completed = run_node(
        "--dry-run", environment={"VIVENTIUM_QA_PRIVATE_DIR": str(untouched)}
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["caseId"] == "TR-026"
    assert payload["status"] == "DRY_RUN"
    assert payload["sideEffects"] is False
    assert payload["accessesDatabase"] is False
    assert payload["sendsTelegramMessages"] is False
    assert payload["restartsRuntime"] is False
    assert payload["receiptEligible"] is False
    assert not untouched.exists()


def test_missing_consent_blocks_before_installed_services_evidence_or_mutation(
    tmp_path: Path,
) -> None:
    untouched = tmp_path / "must-not-exist"
    completed = run_node("--evidence-root", str(untouched))

    assert completed.returncode == 2
    payload = json.loads(completed.stdout)
    assert payload["caseId"] == "TR-026"
    assert payload["status"] == "BLOCKED"
    assert payload["blocker"] == "local_qa_opt_in_required"
    assert payload["releaseReady"] is False
    assert payload["receiptEligible"] is False
    assert str(tmp_path) not in completed.stdout
    assert str(ROOT) not in completed.stdout
    assert not untouched.exists()


def test_each_partial_consent_is_rejected_before_private_evidence_access(
    tmp_path: Path,
) -> None:
    untouched = tmp_path / "must-not-exist"
    cases = (
        (
            ["--local-qa"],
            {},
            "installed_journey_opt_in_required",
        ),
        (
            ["--local-qa"],
            {"VIVENTIUM_QA_ALLOW_TR026_INSTALLED_JOURNEY": "1"},
            "telegram_mutation_consent_required",
        ),
        (
            ["--local-qa", "--allow-telegram-mutation"],
            {
                "VIVENTIUM_QA_ALLOW_TR026_INSTALLED_JOURNEY": "1",
                "VIVENTIUM_QA_ALLOW_TR026_TELEGRAM_MUTATION": "1",
            },
            "runtime_restart_consent_required",
        ),
    )

    for arguments, environment, blocker in cases:
        completed = run_node(
            *arguments, "--evidence-root", str(untouched), environment=environment
        )

        assert completed.returncode == 2
        payload = json.loads(completed.stdout)
        assert payload["status"] == "BLOCKED"
        assert payload["blocker"] == blocker
        assert str(tmp_path) not in completed.stdout
        assert not untouched.exists()


def test_missing_private_scenario_is_typed_blocked_without_active_service_access(
    tmp_path: Path,
) -> None:
    evidence = tmp_path / "private"
    evidence.mkdir(mode=0o700)
    environment = {
        "VIVENTIUM_QA_ALLOW_TR026_INSTALLED_JOURNEY": "1",
        "VIVENTIUM_QA_ALLOW_TR026_TELEGRAM_MUTATION": "1",
        "VIVENTIUM_QA_ALLOW_TR026_RUNTIME_RESTART": "1",
    }
    completed = run_node(
        "--local-qa",
        "--allow-telegram-mutation",
        "--allow-runtime-restart",
        "--evidence-root",
        str(evidence),
        environment=environment,
    )

    assert completed.returncode == 2
    payload = json.loads(completed.stdout)
    assert payload["status"] == "BLOCKED"
    assert payload["blocker"] == "scenario_unavailable"
    assert str(evidence) not in completed.stdout
    assert list(evidence.iterdir()) == []


def test_node_fixture_suite_proves_fail_closed_binding_without_real_execution() -> None:
    completed = subprocess.run(
        ["node", "--no-warnings", "--test", str(NODE_TESTS)],
        cwd=ROOT,
        env={"PATH": os.environ.get("PATH", "")},
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "fail 0" in completed.stdout

import os
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "qa/glasshive-core-provider/evals/run-agent-builder-provider-qa.cjs"
QUALITY_MATRIX = ROOT / "qa/glasshive-core-provider/evals/run-quality-performance-matrix.mjs"
GLASSHIVE_REQUIREMENTS = (
    ROOT / "docs/requirements_and_learnings/48_GlassHive_Workstation_Sandbox_Runtime.md"
)


def test_browser_qa_rejects_endpoint_errors_and_title_fallback() -> None:
    source = HARNESS.read_text(encoding="utf-8")

    assert "noEndpointUiErrors" in source
    assert "conversationTitleGenerated" in source
    assert "visibleUiErrors" in source
    assert "endpointUiErrors.length === 0" in source
    assert 'label.toLowerCase() !== "memory error"' in source
    assert "endpointUiErrors," in source
    assert "conversation?.title !== prompt" in source
    assert "VIVENTIUM_QA_USER_HASH" in source


def test_browser_qa_requires_exactly_one_phase_b_run_and_at_most_one_visible_follow_up() -> None:
    source = HARNESS.read_text(encoding="utf-8")

    assert "phaseBResolvedOnMainGlassHiveSession" in source
    assert 'outcome: phaseBMessages.length === 1 ? "persisted" : "suppressed"' in source
    assert "phaseBMessages.length <= 1" in source
    assert "completedRequestDelta(providerState, mainProviderStateBeforeCortex) >= 2" in source


def test_browser_qa_cleans_exact_synthetic_conversations_after_early_failure() -> None:
    source = HARNESS.read_text(encoding="utf-8")

    assert "cleanupConversationPrompts" in source
    assert "$in: [...cleanupConversationPrompts]" in source
    assert "createdAt: { $gte: qaStartedAt }" in source


def test_quality_matrix_separates_like_for_like_quality_from_native_capability() -> None:
    source = QUALITY_MATRIX.read_text(encoding="utf-8")

    assert "const commonRepetitions = 3" in source
    assert "performanceBudgetsMs" in source
    assert "commonCases" in source
    assert "capabilityCases" in source
    assert '"not_supported"' in source
    assert "commonQualityPass" in source
    assert "nativeCapabilityPass" in source
    assert "VIVENTIUM_QA_MATRIX_PROVIDERS" in source
    assert "runSafely" in source
    assert "providerBlockers" in source
    assert "executed: false" in source


def test_glasshive_installer_docs_match_the_core_provider_first_run_contract() -> None:
    source = GLASSHIVE_REQUIREMENTS.read_text(encoding="utf-8")

    assert "GlassHive is **not part of the minimum public first-run contract**" not in source
    assert "core GlassHive provider and host runtime are enabled by default" in source
    assert "Custom configurations may explicitly disable GlassHive" in source


@pytest.mark.skipif(
    os.environ.get("VIVENTIUM_QA_RUN_BROWSER") != "1",
    reason="real installed-runtime browser QA requires explicit local opt-in",
)
def test_real_installed_agent_builder_provider_qa() -> None:
    completed = subprocess.run(
        ["node", str(HARNESS)],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
        timeout=15 * 60,
        env={**os.environ, "VIVENTIUM_QA_ALLOW_LOCAL_STATE": "1"},
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr

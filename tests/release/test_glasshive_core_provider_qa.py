import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


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


def test_native_default_compiles_without_advertising_glasshive(tmp_path: Path) -> None:
    config = yaml.safe_load(
        (ROOT / "config.minimal.example.yaml").read_text(encoding="utf-8")
    )
    assert config["install"]["mode"] == "native"
    assert config["integrations"]["glasshive"]["enabled"] is False

    config_path = tmp_path / "native-config.yaml"
    output_dir = tmp_path / "compiled"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/viventium/config_compiler.py"),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=ROOT,
        check=True,
    )

    librechat = yaml.safe_load(
        (output_dir / "librechat.yaml").read_text(encoding="utf-8")
    )
    agents = yaml.safe_load(
        (output_dir / "viventium-agents.yaml").read_text(encoding="utf-8")
    )
    custom_endpoints = librechat.get("endpoints", {}).get("custom", [])
    assert all(endpoint.get("name") != "glasshive-harness" for endpoint in custom_endpoints)
    assert (
        librechat.get("viventium", {})
        .get("consciousAgent", {})
        .get("provider")
        != "glasshive-harness"
    )
    assert agents.get("mainAgent", {}).get("provider") != "glasshive-harness"
    for artifact in (
        "librechat.yaml",
        "prompt-bundle.json",
        "native-runtime.env",
        "viventium-agents.yaml",
    ):
        body = (output_dir / artifact).read_text(encoding="utf-8").lower()
        assert "glasshive-harness" not in body
        assert "glasshive-workers-projects" not in body

    assembler_spec = importlib.util.spec_from_file_location(
        "native_payload_assembler",
        ROOT / "scripts/viventium/assemble_native_payload.py",
    )
    assert assembler_spec and assembler_spec.loader
    assembler = importlib.util.module_from_spec(assembler_spec)
    assembler_spec.loader.exec_module(assembler)
    assembler.validate_native_compiled_defaults(output_dir)

    source = GLASSHIVE_REQUIREMENTS.read_text(encoding="utf-8")
    assert "source/Docker installs that select GlassHive" in source
    assert "Easy Install Native payload does not" in source


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

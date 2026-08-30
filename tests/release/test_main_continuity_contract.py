from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "viventium" / "main_continuity_contract.py"


def _module():
    spec = importlib.util.spec_from_file_location("main_continuity_contract", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_main_continuity_contract_is_complete_and_generated_view_is_current():
    module = _module()
    contract = module.load_contract()
    expected = module.render(contract)
    assert module.GENERATED.read_text(encoding="utf-8") == expected


def test_main_continuity_contract_keeps_private_task_identifiers_out_of_public_source():
    forbidden_prefix = "codex://threads/"
    for path in (
        ROOT / "docs" / "requirements_and_learnings" / "56_Main_Continuity_Kernel.md",
        ROOT / "qa" / "main-continuity" / "contract.v1.json",
        ROOT / "qa" / "main-continuity" / "generated-coverage.md",
    ):
        assert forbidden_prefix not in path.read_text(encoding="utf-8")


def test_main_continuity_contract_requires_candidate_artifact_identity_per_case():
    module = _module()
    contract = module.load_contract()
    candidate = copy.deepcopy(contract)
    candidate["qaCases"][0].pop("candidateArtifactRefs")

    with pytest.raises(ValueError, match="Candidate/artifact identity is required"):
        module.validate_contract(candidate)


def test_main_continuity_contract_rejects_live_support_with_only_automated_evidence():
    module = _module()
    contract = module.load_contract()
    candidate = copy.deepcopy(contract)
    case = next(item for item in candidate["qaCases"] if item["id"] == "MC-001")
    case["candidateArtifactRefs"] = ["MC-CAND-PRE-P0-AUTOMATED-2026-08-21"]

    with pytest.raises(ValueError, match="PASS-LIVE support requires a live candidate identity"):
        module.validate_contract(candidate)


def test_main_continuity_contract_rejects_qualified_overall_results():
    module = _module()
    contract = module.load_contract()
    candidate = copy.deepcopy(contract)
    candidate["qaCases"][0]["result"] = "PASS-LIVE"

    with pytest.raises(ValueError, match="Invalid QA result"):
        module.validate_contract(candidate)


def test_main_continuity_contract_requires_explicit_overall_results():
    module = _module()
    contract = module.load_contract()
    candidate = copy.deepcopy(contract)
    candidate["qaCases"][0].pop("result")

    with pytest.raises(ValueError, match="Invalid QA result"):
        module.validate_contract(candidate)


def test_main_continuity_contract_requires_not_run_catalog_date():
    module = _module()
    contract = module.load_contract()
    candidate = copy.deepcopy(contract)
    case = next(item for item in candidate["qaCases"] if item["id"] == "MC-003")
    case.pop("catalogedOn")

    with pytest.raises(ValueError, match="immutable catalogedOn"):
        module.validate_contract(candidate)


def test_main_continuity_contract_rejects_not_run_with_exercised_candidate():
    module = _module()
    contract = module.load_contract()
    candidate = copy.deepcopy(contract)
    case = next(item for item in candidate["qaCases"] if item["id"] == "MC-003")
    case["candidateArtifactRefs"] = ["MC-CAND-HISTORICAL-LIVE-2026-08-20"]

    with pytest.raises(ValueError, match="NOT RUN case must use only not-run identity"):
        module.validate_contract(candidate)


def test_main_continuity_contract_requires_complete_final_source_identity():
    module = _module()
    contract = module.load_contract()
    candidate = copy.deepcopy(contract)
    candidate["candidateArtifacts"].append(
        {
            "id": "MC-CAND-INCOMPLETE-FINAL",
            "evidenceClass": "final-source-live",
            "artifactIdentity": "Latest runtime was exercised.",
        }
    )

    with pytest.raises(ValueError, match="Final-source identity is incomplete"):
        module.validate_contract(candidate)

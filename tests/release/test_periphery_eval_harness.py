from __future__ import annotations

import importlib.util
import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "qa" / "periphery-nightly-insights" / "scripts" / "run-periphery-evals.py"
SPEC = importlib.util.spec_from_file_location("viventium_periphery_evals", SCRIPT)
assert SPEC and SPEC.loader
periphery_evals = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(periphery_evals)


def _snapshot() -> dict:
    return {
        "snapshotRef": "snapshot:20990101T000000Z-abc123abc123",
        "memories": [],
        "conversations": [
            {
                "sourceRef": "conversation:111111111111111111111111",
                "messages": [
                    {"sourceRef": "message:111111111111111111111112", "text": "Synthetic evidence"}
                ],
            }
        ],
        "schedules": [],
        "scratchpads": [],
        "recentRuns": [],
    }


def _sidecar() -> dict:
    source_ref = "message:111111111111111111111112"
    return {
        "schemaVersion": 2,
        "snapshotRef": "snapshot:20990101T000000Z-abc123abc123",
        "sourceRefs": [source_ref],
        "observations": [{"kind": "observation", "summary": "Synthetic", "sourceRefs": [source_ref]}],
        "risks": [],
        "blindSpots": [],
        "opportunityCosts": [],
        "opportunities": [],
        "whatWouldMakeThisWrong": [],
        "whenToSurface": [],
        "proposedActions": [],
        "memoryProposalRefs": [],
    }


def test_periphery_eval_grader_accepts_resolvable_claims() -> None:
    result = periphery_evals.grade_artifact(
        sidecar=_sidecar(),
        markdown="Synthetic private markdown",
        snapshot=_snapshot(),
        expected={"requireGroundedClaims": True, "minimumInsightCount": 0},
    )

    assert result["passed"] is True
    assert result["groundedClaimCount"] == 1
    assert result["ungroundedClaimCount"] == 0


def test_periphery_eval_grader_rejects_unresolvable_claim_and_private_path() -> None:
    sidecar = _sidecar()
    sidecar["observations"][0]["sourceRefs"] = ["message:999999999999999999999999"]
    result = periphery_evals.grade_artifact(
        sidecar=sidecar,
        markdown="Synthetic path /Users/example/private",
        snapshot=_snapshot(),
        expected={"requireGroundedClaims": True, "minimumInsightCount": 0},
    )

    assert result["passed"] is False
    assert "ungrounded_claims" in result["issues"]
    assert "absolute_path_leak" in result["issues"]


def test_periphery_eval_grader_rejects_verbatim_private_evidence_copy() -> None:
    snapshot = _snapshot()
    private_text = "Synthetic private evidence that must be paraphrased rather than copied into an artifact."
    snapshot["conversations"][0]["messages"][0]["text"] = private_text
    sidecar = _sidecar()
    sidecar["observations"][0]["summary"] = private_text

    result = periphery_evals.grade_artifact(
        sidecar=sidecar,
        markdown="Synthetic private markdown",
        snapshot=snapshot,
        expected={"requireGroundedClaims": True, "minimumInsightCount": 0},
    )

    assert result["passed"] is False
    assert result["rawEvidenceCopyCount"] == 1
    assert "raw_evidence_copy" in result["issues"]


def test_periphery_eval_grader_checks_required_refs_and_bounded_urgency() -> None:
    sidecar = _sidecar()
    sidecar["severity"] = "high"
    sidecar["timeSensitivity"] = "high"
    result = periphery_evals.grade_artifact(
        sidecar=sidecar,
        markdown="Synthetic private markdown",
        snapshot=_snapshot(),
        expected={
            "requiredTopLevelSourceRefs": ["conversation:111111111111111111111111"],
            "allowedTimeSensitivity": ["none", "low"],
            "allowedSeverity": ["none", "low", "medium"],
        },
    )

    assert result["passed"] is False
    assert "missing_required_source_ref" in result["issues"]
    assert "time_sensitivity_out_of_bounds" in result["issues"]
    assert "severity_out_of_bounds" in result["issues"]


def test_periphery_eval_harness_classifies_structured_model_failures() -> None:
    usage_stdout = "\n".join(
        [
            json.dumps({"type": "thread.started", "thread_id": "synthetic"}),
            json.dumps(
                {
                    "type": "turn.failed",
                    "error": {"message": "You've hit your usage limit. Try again later."},
                }
            ),
        ]
    )

    assert periphery_evals.model_failure_class(usage_stdout, "", 1) == "usage_limit"
    assert periphery_evals.model_failure_class("", "HTTP 429 rate limit", 1) == "rate_limited"
    assert periphery_evals.model_failure_class("", "timeout after 30s", 124) == "timeout"
    assert periphery_evals.model_failure_class("", "unexpected failure", 1) == "model_run_failed"


def test_periphery_eval_bank_dry_run_is_public_safe(tmp_path: Path) -> None:
    env = dict(os.environ)
    env["VIVENTIUM_PRIVATE_USER_DATA_DIR"] = str(tmp_path / "private")
    completed = subprocess.run(
        [str(SCRIPT)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["caseCount"] == 6
    assert payload["passedCount"] == 6
    assert "/Users/" not in completed.stdout
    assert "Synthetic launch planning" not in completed.stdout

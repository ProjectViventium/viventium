from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "qa/emotional-cortex/scripts/run_emo_installed_journey.cjs"
FIXTURES = ROOT / "qa/emotional-cortex/scripts/run_emo_installed_journey.test.cjs"


@pytest.mark.parametrize(
    ("case_id", "verifier"),
    [
        ("EMO-UC-047", "run_emo_uc_047.py"),
        ("EMO-UC-048", "run_emo_uc_048.py"),
    ],
)
def test_emotional_installed_dry_run_is_inert_and_case_bound(
    tmp_path: Path, case_id: str, verifier: str
) -> None:
    private_evidence = tmp_path / "must-not-be-created"
    result = subprocess.run(
        ["node", str(RUNNER), f"--case={case_id}", "--dry-run"],
        cwd=ROOT,
        env={
            "PATH": os.environ.get("PATH", ""),
            "VIVENTIUM_QA_PRIVATE_DIR": str(private_evidence),
        },
        capture_output=True,
        text=True,
        check=True,
    )

    payload = json.loads(result.stdout)
    assert payload["caseId"] == case_id
    assert payload["status"] == "DRY_RUN"
    assert payload["independentVerifier"] == verifier
    assert payload["releaseLabel"] == "PRE-GATE / NOT READY"
    assert payload["releaseReady"] is False
    assert payload["receiptEligible"] is False
    assert payload["sideEffects"] is False
    assert payload["invokesModels"] is False
    assert payload["opensBrowser"] is False
    assert payload["mutatesAccount"] is False
    assert payload["restartsRuntime"] is False
    assert not private_evidence.exists()


@pytest.mark.parametrize("case_id", ["EMO-UC-047", "EMO-UC-048"])
def test_emotional_installed_live_run_requires_explicit_consent_before_access(
    tmp_path: Path, case_id: str
) -> None:
    private_evidence = tmp_path / "must-not-be-created"
    result = subprocess.run(
        ["node", str(RUNNER), f"--case={case_id}", "--live"],
        cwd=ROOT,
        env={
            "PATH": os.environ.get("PATH", ""),
            "VIVENTIUM_QA_PRIVATE_DIR": str(private_evidence),
        },
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    payload = json.loads(result.stdout)
    assert payload["caseId"] == case_id
    assert payload["status"] == "BLOCKED"
    assert payload["blocker"] == "installed_emotional_journey_requires_explicit_opt_in"
    assert payload["releaseLabel"] == "PRE-GATE / NOT READY"
    assert payload["releaseReady"] is False
    assert payload["receiptEligible"] is False
    assert not private_evidence.exists()


def test_emotional_installed_journey_runs_all_executable_security_regressions() -> None:
    result = subprocess.run(
        ["node", "--no-warnings", "--test", str(FIXTURES)],
        cwd=ROOT,
        env={"PATH": os.environ.get("PATH", "")},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    count = re.search(r"^ℹ tests (\d+)$", result.stdout, flags=re.MULTILINE)
    assert count is not None, result.stdout
    assert int(count.group(1)) >= 56
    assert re.search(r"^ℹ fail 0$", result.stdout, flags=re.MULTILINE)

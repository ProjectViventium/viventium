from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "qa/prompt-workbench/scripts/run_installed_prompt_workbench_journey.cjs"
NODE_TESTS = (
    ROOT / "qa/prompt-workbench/scripts/run_installed_prompt_workbench_journey.test.cjs"
)
QA_OWNER = ROOT / "qa/prompt-workbench/cases.md"


def test_prompt_workbench_installed_journey_direct_suite_passes() -> None:
    completed = subprocess.run(
        ["node", "--test", str(NODE_TESTS)],
        cwd=ROOT,
        env={"PATH": os.environ.get("PATH", "")},
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "fail 0" in completed.stdout


def test_prompt_workbench_installed_journey_blocks_before_local_access_without_consent(
    tmp_path: Path,
) -> None:
    isolated_home = tmp_path / "isolated-home"
    isolated_home.mkdir()
    completed = subprocess.run(
        ["node", str(RUNNER)],
        cwd=ROOT,
        env={"HOME": str(isolated_home), "PATH": os.environ.get("PATH", "")},
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )

    assert completed.returncode == 1
    payload = json.loads(completed.stderr)
    assert payload == {
        "schemaVersion": 1,
        "status": "blocked",
        "releaseEligible": False,
        "candidateMode": "PRE-GATE / NOT READY",
        "blocker": "explicit_local_qa_authorization_required",
    }
    assert list(isolated_home.iterdir()) == []


def test_runner_is_owned_and_not_claimed_installed() -> None:
    cases = QA_OWNER.read_text(encoding="utf-8")
    heading = "## PW-049 Complete Installed Prompt Workbench Journey"

    assert heading in cases
    section = cases.split(heading, 1)[1]
    assert "tests/release/test_prompt_workbench_installed_journey_runner.py" in cases
    assert "Last Run: PARTIAL 2026-08-27." in section


def test_browser_history_check_waits_for_the_reloaded_api_result() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    method = source.split("async assertEvalHistoryAfterReload(runId)", 1)[1].split(
        "async securityReport()", 1
    )[0]

    assert re.search(
        r"getByText\(runId,\s*\{ exact: true \}\).*?waitFor\(\{\s*state: \"visible\"",
        method,
        flags=re.DOTALL,
    )


def test_browser_journey_names_the_required_deterministic_ui_gates() -> None:
    source = RUNNER.read_text(encoding="utf-8")

    for required in (
        "frames_health_unverified",
        "failed_save_buffer_not_retained",
        "continuity_failed_save_reload_mismatch",
        "Hide prompt flow sidebar",
        "Show prompt flow sidebar",
        "Workbench settings",
        'getByRole("radio", { name: "Light"',
        'getByRole("radio", { name: "Dark"',
        "[1512, 1024, 320]",
    ):
        assert required in source

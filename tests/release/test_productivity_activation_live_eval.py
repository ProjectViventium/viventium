from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
EVAL_SCRIPT = (
    REPO_ROOT
    / "viventium_v0_4"
    / "LibreChat"
    / "scripts"
    / "run-productivity-activation-evals.js"
)


@pytest.mark.skipif(
    os.getenv("VIVENTIUM_RUN_LIVE_ACTIVATION_EVALS") != "1",
    reason="live activation evals are opt-in",
)
def test_live_productivity_activation_eval_passes(tmp_path: Path) -> None:
    result = subprocess.run(
        ["node", str(EVAL_SCRIPT), f"--output-dir={tmp_path}"],
        cwd=REPO_ROOT / "viventium_v0_4" / "LibreChat",
        capture_output=True,
        text=True,
        check=False,
    )

    report_path = tmp_path / "productivity-activation-eval.json"
    assert report_path.exists(), (
        "live activation eval did not produce a JSON report\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    summary = report["summary"]
    result_count = int(summary["resultCount"])
    pass_count = int(summary["passCount"])
    fail_count = int(summary["failCount"])
    unavailable_count = int(summary["unavailableCount"])
    primary_outage_count = int(summary.get("primaryOutageCount", 0))

    assert result_count > 0, "live activation eval produced no scenarios"

    if fail_count > 0:
        pytest.fail(
            "live activation eval returned wrong activation decisions\n"
            f"summary={summary}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )

    if pass_count == result_count:
        assert result.returncode == 0, (
            "live activation eval reported all-pass summary but exited non-zero\n"
            f"summary={summary}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
        return

    if pass_count > 0 and unavailable_count > 0:
        pytest.xfail(
            "live activation eval recovered via fallbacks but still saw provider outage(s); "
            f"primary_outage_count={primary_outage_count}, summary={summary}"
        )

    if unavailable_count == result_count:
        pytest.skip(
            "live activation eval could not reach any classifier provider; "
            f"summary={summary}"
        )

    assert result.returncode == 0, (
        "live activation eval returned a mixed result that does not match expected pass/fail/outage handling\n"
        f"summary={summary}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )

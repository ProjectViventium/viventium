#!/usr/bin/env python3
"""Run a public-safe live GlassHive wait/continue smoke.

This harness intentionally uses a real worker profile and provider-backed CLI. It is not part of
the default deterministic test suite. Run it when local credentials are available and a small live
provider call is acceptable.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[3]
RUNTIME_ROOT = REPO_ROOT / "viventium_v0_4" / "GlassHive" / "runtime_phase1"
sys.path.insert(0, str(RUNTIME_ROOT / "src"))

from workers_projects_runtime.api import create_app  # noqa: E402


TERMINAL_STATES = {"completed", "failed", "cancelled", "interrupted"}
FIRST_MARKER = "GLASSHIVE_LIVE_WAIT_SMOKE"
CONTINUE_MARKER = "GLASSHIVE_LIVE_CONTINUE_SMOKE"


def _wait_for_run(client: TestClient, run_id: str, timeout_sec: float, poll_sec: float) -> tuple[dict[str, Any], list[str]]:
    deadline = time.time() + timeout_sec
    states: list[str] = []
    state: dict[str, Any] = {}
    while time.time() < deadline:
        response = client.get(f"/v1/runs/{run_id}")
        response.raise_for_status()
        state = response.json()
        current = str(state.get("state") or "")
        states.append(current)
        if current in TERMINAL_STATES:
            return state, states
        time.sleep(poll_sec)
    response = client.get(f"/v1/runs/{run_id}")
    response.raise_for_status()
    state = response.json()
    states.append(str(state.get("state") or ""))
    return state, states


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="codex-cli", choices=["codex-cli", "claude-code", "openclaw-general"])
    parser.add_argument("--execution-mode", default="host", choices=["host", "docker"])
    parser.add_argument("--effort", default="high")
    parser.add_argument("--delay-seconds", type=int, default=35)
    parser.add_argument("--first-timeout-sec", type=float, default=240.0)
    parser.add_argument("--continue-timeout-sec", type=float, default=240.0)
    parser.add_argument("--poll-sec", type=float, default=5.0)
    args = parser.parse_args()

    os.environ.setdefault("GLASSHIVE_ALLOWED_WORKER_PROFILES", "codex-cli,claude-code,openclaw-general")
    os.environ.setdefault("GLASSHIVE_HOST_RUN_TIMEOUT_SEC", str(max(args.first_timeout_sec, args.continue_timeout_sec)))

    root = Path(tempfile.mkdtemp(prefix="glasshive-live-wait-"))
    unique_suffix = uuid.uuid4().hex[:8]
    client = TestClient(create_app(str(root / "runtime.db"), runtime_backend="openclaw"))
    project = client.post(
        "/v1/projects",
        json={
            "owner_id": "public-smoke-user",
            "title": f"Public-safe live wait continue smoke {unique_suffix}",
            "goal": "Exercise provider-backed run status and continuation without private data.",
            "default_worker_profile": args.profile,
        },
    ).json()
    worker = client.post(
        f"/v1/projects/{project['project_id']}/workers",
        json={
            "owner_id": "public-smoke-user",
            "name": f"Live Wait Worker {unique_suffix}",
            "role": "qa",
            "profile": args.profile,
            "execution_mode": args.execution_mode,
        },
    ).json()

    instruction = (
        "Public-safe QA smoke. Use shell commands if useful. Wait about "
        f"{args.delay_seconds} seconds before finalizing so status polling observes an active run. "
        f"Create artifacts/live-wait.md with marker {FIRST_MARKER}, then finish with "
        "FINAL REPORT: created artifacts/live-wait.md. Do not browse the web."
    )
    first = client.post(
        f"/v1/workers/{worker['worker_id']}/assign",
        json={"instruction": instruction, "effort": args.effort},
    ).json()
    first_state, first_states = _wait_for_run(client, first["run_id"], args.first_timeout_sec, args.poll_sec)

    artifact = Path(worker["workspace_dir"]) / "artifacts" / "live-wait.md"
    first_text = first_state.get("output_text") or ""
    artifact_text_after_first = artifact.read_text(encoding="utf-8", errors="replace") if artifact.exists() else ""
    first_passed = (
        first_state.get("state") == "completed"
        and artifact.exists()
        and FIRST_MARKER in artifact_text_after_first
    )

    continue_state: dict[str, Any] = {}
    continue_states: list[str] = []
    continue_passed = False
    if first_passed:
        cont = client.post(
            f"/v1/workers/{worker['worker_id']}/message",
            json={
                "message": (
                    "Continue in the same workspace. Append a section named Continuation to "
                    f"artifacts/live-wait.md with marker {CONTINUE_MARKER}, then FINAL REPORT: "
                    "continuation updated artifacts/live-wait.md."
                )
            },
        ).json()
        continue_state, continue_states = _wait_for_run(
            client,
            cont["run_id"],
            args.continue_timeout_sec,
            args.poll_sec,
        )
        artifact_text = artifact.read_text(encoding="utf-8", errors="replace") if artifact.exists() else ""
        continue_passed = continue_state.get("state") == "completed" and CONTINUE_MARKER in artifact_text

    evidence_path = Path(worker["workspace_dir"]) / "glasshive-run" / "evidence.json"
    evidence: dict[str, Any] = {}
    if evidence_path.exists():
        try:
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            evidence = {"parse_error": True}

    evidence_worker = evidence.get("worker") if isinstance(evidence.get("worker"), dict) else {}
    summary = {
        "schema": "glasshive.live-provider-wait-continue-smoke.v1",
        "profile": args.profile,
        "execution_mode": args.execution_mode,
        "effort": args.effort,
        "first_run_state": first_state.get("state"),
        "first_run_failure_class": first_state.get("failure_class"),
        "first_observed_states": list(dict.fromkeys(first_states)),
        "first_artifact_exists": artifact.exists(),
        "first_artifact_has_marker": FIRST_MARKER in artifact_text_after_first,
        "first_output_has_marker": FIRST_MARKER in first_text,
        "continue_run_state": continue_state.get("state"),
        "continue_run_failure_class": continue_state.get("failure_class"),
        "continue_observed_states": list(dict.fromkeys(continue_states)),
        "continue_artifact_has_marker": continue_passed,
        "evidence_status": ((evidence.get("evidence_result") or {}).get("status") if evidence else None),
        "evidence_profile": evidence_worker.get("profile"),
        "evidence_execution_mode": evidence_worker.get("execution_mode"),
        "workspace_temp_name": root.name,
        "passed": bool(first_passed and continue_passed),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

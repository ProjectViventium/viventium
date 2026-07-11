#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
WORKBENCH_BACKEND = ROOT / "viventium_v0_4" / "prompt-workbench" / "backend"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(WORKBENCH_BACKEND) not in sys.path:
    sys.path.insert(0, str(WORKBENCH_BACKEND))

from prompt_workbench.periphery_contract import (  # noqa: E402
    NIGHTLY_PROMPT_TEMPLATE,
    PERIPHERY_CONTENT_FIELDS,
)

CASE_BANK = ROOT / "qa" / "periphery-nightly-insights" / "evals" / "cases.json"
INSIGHT_FIELDS = ("risks", "blindSpots", "opportunityCosts", "opportunities")
CLAIM_FIELDS = (
    "observations",
    "risks",
    "blindSpots",
    "opportunityCosts",
    "opportunities",
    "whatWouldMakeThisWrong",
    "proposedActions",
)

def _sha(value: str, length: int = 24) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def _private_eval_root() -> Path:
    configured = os.getenv("VIVENTIUM_PRIVATE_USER_DATA_DIR", "").strip()
    base = Path(configured).expanduser() if configured else Path.home() / "Library" / "Application Support" / "Viventium" / "private-user-data"
    root = base / "prompt-workbench" / "periphery-evals"
    root.mkdir(parents=True, exist_ok=True)
    os.chmod(root, 0o700)
    return root


def _load_cases() -> list[dict[str, Any]]:
    payload = json.loads(CASE_BANK.read_text(encoding="utf-8"))
    cases = payload.get("cases") if isinstance(payload, dict) else None
    if not isinstance(cases, list) or not cases:
        raise ValueError("Periphery eval bank has no cases")
    return [case for case in cases if isinstance(case, dict)]


def _source_refs(snapshot: dict[str, Any]) -> set[str]:
    refs: set[str] = set()
    for key in ("memories", "schedules", "scratchpads", "recentRuns"):
        for item in snapshot.get(key) or []:
            if isinstance(item, dict) and item.get("sourceRef"):
                refs.add(str(item["sourceRef"]))
    for conversation in snapshot.get("conversations") or []:
        if not isinstance(conversation, dict):
            continue
        if conversation.get("sourceRef"):
            refs.add(str(conversation["sourceRef"]))
        for message in conversation.get("messages") or []:
            if isinstance(message, dict) and message.get("sourceRef"):
                refs.add(str(message["sourceRef"]))
    return refs


def _private_evidence_texts(snapshot: dict[str, Any]) -> set[str]:
    text_fields = {"text", "content", "value", "prompt", "promptText", "instruction", "instructions"}
    values: set[str] = set()

    def visit(value: Any, key: str = "") -> None:
        if isinstance(value, dict):
            for child_key, child_value in value.items():
                visit(child_value, str(child_key))
            return
        if isinstance(value, list):
            for child in value:
                visit(child, key)
            return
        if key not in text_fields or not isinstance(value, str):
            return
        normalized = " ".join(value.split()).casefold()
        if len(normalized) >= 32:
            values.add(normalized)

    visit(snapshot)
    return values


def grade_artifact(
    *,
    sidecar: dict[str, Any],
    markdown: str,
    snapshot: dict[str, Any],
    expected: dict[str, Any],
) -> dict[str, Any]:
    issues: list[str] = []
    known_refs = _source_refs(snapshot)
    top_refs = sidecar.get("sourceRefs")
    if sidecar.get("schemaVersion") != 2:
        issues.append("schema_version")
    if sidecar.get("snapshotRef") != snapshot.get("snapshotRef"):
        issues.append("snapshot_ref")
    if not isinstance(top_refs, list) or any(ref not in known_refs for ref in top_refs):
        issues.append("unresolvable_top_level_refs")
        top_refs = []
    required_refs = {
        str(ref) for ref in expected.get("requiredTopLevelSourceRefs") or [] if str(ref).strip()
    }
    if not required_refs.issubset(set(top_refs)):
        issues.append("missing_required_source_ref")
    allowed_time_sensitivity = {
        str(value).lower() for value in expected.get("allowedTimeSensitivity") or []
    }
    if allowed_time_sensitivity and str(sidecar.get("timeSensitivity") or "").lower() not in allowed_time_sensitivity:
        issues.append("time_sensitivity_out_of_bounds")
    allowed_severity = {str(value).lower() for value in expected.get("allowedSeverity") or []}
    if allowed_severity and str(sidecar.get("severity") or "").lower() not in allowed_severity:
        issues.append("severity_out_of_bounds")
    for field in PERIPHERY_CONTENT_FIELDS:
        if not isinstance(sidecar.get(field), list):
            issues.append(f"invalid_type:{field}")
    grounded = 0
    ungrounded = 0
    top_ref_set = set(top_refs)
    for field in CLAIM_FIELDS:
        for claim in sidecar.get(field) or []:
            if not isinstance(claim, dict):
                ungrounded += 1
                continue
            claim_refs = claim.get("sourceRefs")
            kind = str(claim.get("kind") or "").lower()
            if kind in {"no_result", "missing_prerequisite"} and claim_refs == []:
                grounded += 1
            elif isinstance(claim_refs, list) and claim_refs and all(ref in top_ref_set for ref in claim_refs):
                grounded += 1
            else:
                ungrounded += 1
    if expected.get("requireGroundedClaims") and ungrounded:
        issues.append("ungrounded_claims")

    insight_count = sum(len(sidecar.get(field) or []) for field in INSIGHT_FIELDS)
    if insight_count < int(expected.get("minimumInsightCount") or 0):
        issues.append("missing_material_insight")
    if expected.get("expectNoResult"):
        observations = sidecar.get("observations") or []
        honest_no_result = (
            insight_count == 0
            and bool(observations)
            and all(
                isinstance(item, dict)
                and str(item.get("kind") or "").lower() in {"no_result", "missing_prerequisite"}
                for item in observations
            )
        )
        if not honest_no_result:
            issues.append("dishonest_no_result")

    combined = (json.dumps(sidecar, sort_keys=True, default=str) + "\n" + markdown).lower()
    normalized_output = " ".join(combined.split()).casefold()
    raw_copy_count = sum(
        1 for evidence_text in _private_evidence_texts(snapshot) if evidence_text in normalized_output
    )
    if raw_copy_count:
        issues.append("raw_evidence_copy")
    for term in expected.get("forbiddenTerms") or []:
        if str(term).lower() in combined:
            issues.append(f"forbidden_term:{_sha(str(term), 12)}")
    if re.search(r"(?:/users/|/home/|/private/var/|/var/folders/)", combined):
        issues.append("absolute_path_leak")
    return {
        "passed": not issues,
        "issues": sorted(set(issues)),
        "insightCount": insight_count,
        "groundedClaimCount": grounded,
        "ungroundedClaimCount": ungrounded,
        "rawEvidenceCopyCount": raw_copy_count,
        "sourceRefCount": len(top_refs),
        "artifactHash": _sha(json.dumps(sidecar, sort_keys=True, default=str), 32),
    }


def _project_case(case: dict[str, Any], case_root: Path) -> tuple[dict[str, Any], str]:
    snapshot = json.loads(json.dumps(case["snapshot"]))
    generated_at = datetime.now(timezone.utc)
    snapshot_id = generated_at.strftime("%Y%m%dT%H%M%SZ") + f"-{_sha(str(case['id']), 12)}"
    snapshot["schemaVersion"] = 1
    snapshot["snapshotRef"] = f"snapshot:{snapshot_id}"
    snapshot["generatedAt"] = generated_at.isoformat().replace("+00:00", "Z")
    snapshot.setdefault("reasoningLenses", [])
    snapshot.setdefault(
        "evidenceContract",
        {
            "citation": "Use sourceRef values exactly for every non-trivial claim.",
            "uncertainty": "Separate observations, inferences, and hypotheses. No evidence means no result.",
            "privacy": "Do not copy raw conversations into sidecar metadata.",
        },
    )
    scheduled_dir = case_root / "scheduled-prompt"
    my_folder = case_root / "my-folder"
    scheduled_dir.mkdir(parents=True)
    my_folder.mkdir(parents=True)
    (scheduled_dir / "periphery-snapshot.json").write_text(
        json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (scheduled_dir / "run-context.json").write_text(
        json.dumps(
            {
                "scheduledRunRef": {"runId": f"eval-{case['id']}", "taskId": "synthetic-eval"},
                "snapshotRef": snapshot["snapshotRef"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    manifest = {
        "snapshotRef": snapshot["snapshotRef"],
        "status": snapshot.get("status"),
        "missingPrerequisites": snapshot.get("missingPrerequisites") or [],
        "sourceRefCount": len(_source_refs(snapshot)),
    }
    prompt = NIGHTLY_PROMPT_TEMPLATE.replace(
        "{{local.viventium.my_folder}}", str(my_folder)
    ).replace("{{viventium.periphery.snapshot}}", json.dumps(manifest, sort_keys=True))
    return snapshot, prompt


def _latest_artifact(case_root: Path) -> tuple[dict[str, Any], str] | None:
    sidecars = sorted((case_root / "my-folder" / "periphery" / "risk_radar").glob("*/*/*.json"))
    if not sidecars:
        return None
    sidecar_path = sidecars[-1]
    try:
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        markdown = sidecar_path.with_suffix(".md").read_text(encoding="utf-8")
    except (OSError, json.JSONDecodeError):
        return None
    return (sidecar, markdown) if isinstance(sidecar, dict) else None


def model_failure_class(stdout: str, stderr: str, return_code: int) -> str:
    if return_code == 124:
        return "timeout"
    messages: list[str] = []
    for line in str(stdout or "").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        message = event.get("message")
        error = event.get("error")
        if isinstance(error, dict):
            message = error.get("message") or message
        if isinstance(message, str):
            messages.append(message)
    combined = " ".join([*messages, str(stderr or "")]).casefold()
    if "usage limit" in combined or "usage quota" in combined:
        return "usage_limit"
    if "rate limit" in combined or "status 429" in combined or "http 429" in combined:
        return "rate_limited"
    if "unauthorized" in combined or "authentication" in combined or "invalid token" in combined:
        return "authentication_failed"
    return "model_run_failed"


def _run_live_case(
    case: dict[str, Any],
    *,
    run_root: Path,
    model: str,
    effort: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    case_root = run_root / str(case["id"])
    case_root.mkdir(parents=True)
    snapshot, prompt = _project_case(case, case_root)
    started = time.monotonic()
    command = [
        "codex",
        "exec",
        "--ignore-user-config",
        "--json",
        "--skip-git-repo-check",
        "-C",
        str(case_root),
        "-m",
        model,
        "-c",
        f'model_reasoning_effort="{effort}"',
        "-s",
        "workspace-write",
        "-",
    ]
    try:
        completed = subprocess.run(
            command,
            input=prompt,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        return_code = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as exc:
        return_code = 124
        stdout = str(exc.stdout or "")
        stderr = f"timeout after {timeout_seconds}s"
    (case_root / "codex.stdout.private.jsonl").write_text(stdout, encoding="utf-8")
    (case_root / "codex.stderr.private.log").write_text(stderr, encoding="utf-8")
    os.chmod(case_root / "codex.stdout.private.jsonl", 0o600)
    os.chmod(case_root / "codex.stderr.private.log", 0o600)
    artifact = _latest_artifact(case_root)
    if return_code != 0 or not artifact:
        failure_class = model_failure_class(stdout, stderr, return_code) if return_code else "artifact_missing"
        return {
            "caseId": case["id"],
            "passed": False,
            "issues": [failure_class],
            "failureClass": failure_class,
            "returnCode": return_code,
            "durationSeconds": round(time.monotonic() - started, 2),
            "artifactHash": None,
        }
    sidecar, markdown = artifact
    grade = grade_artifact(
        sidecar=sidecar,
        markdown=markdown,
        snapshot=snapshot,
        expected=case.get("expect") or {},
    )
    proposal_files = list((case_root / "my-folder").glob("*memory*proposal*.json"))
    if proposal_files:
        grade["passed"] = False
        grade["issues"] = sorted(set([*grade["issues"], "unexpected_memory_proposal"]))
    return {
        "caseId": case["id"],
        "returnCode": return_code,
        "durationSeconds": round(time.monotonic() - started, 2),
        **grade,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Viventium periphery snapshot and artifact evals")
    parser.add_argument("--live", action="store_true", help="Run exact-model cases through Codex CLI")
    parser.add_argument("--case", action="append", default=[], help="Run only the named case (repeatable)")
    parser.add_argument("--model", default="gpt-5.6-sol")
    parser.add_argument("--effort", default="xhigh")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    cases = _load_cases()
    if args.case:
        requested = set(args.case)
        cases = [case for case in cases if case.get("id") in requested]
        missing = requested - {str(case.get("id")) for case in cases}
        if missing:
            raise SystemExit(f"Unknown eval case(s): {', '.join(sorted(missing))}")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + _sha(str(time.time_ns()), 8)
    run_root = _private_eval_root() / run_id
    run_root.mkdir(parents=True)
    os.chmod(run_root, 0o700)
    if args.live:
        results = [
            _run_live_case(
                case,
                run_root=run_root,
                model=args.model,
                effort=args.effort,
                timeout_seconds=args.timeout_seconds,
            )
            for case in cases
        ]
    else:
        results = [
            {"caseId": case["id"], "passed": True, "issues": [], "status": "ready"}
            for case in cases
        ]
    summary = {
        "schemaVersion": 1,
        "runId": run_id,
        "live": bool(args.live),
        "model": args.model,
        "effort": args.effort,
        "caseCount": len(results),
        "passedCount": sum(1 for result in results if result.get("passed")),
        "failedCount": sum(1 for result in results if not result.get("passed")),
        "results": results,
    }
    private_result_path = run_root / "result.public-safe.json"
    private_result_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(private_result_path, 0o600)
    if args.output:
        output_path = Path(args.output).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))
    return 0 if summary["failedCount"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

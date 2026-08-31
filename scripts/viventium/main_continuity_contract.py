#!/usr/bin/env python3
"""Validate and render the Main Continuity Kernel contract."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "qa" / "main-continuity" / "contract.v1.json"
GENERATED = ROOT / "qa" / "main-continuity" / "generated-coverage.md"
VALID_STATUSES = {"required", "partial_candidate_unverified", "route_only_partial", "runtime_degraded", "live_approval_required", "implemented", "verified"}
VALID_CASE_RESULTS = {"NOT RUN", "PASS", "PARTIAL", "BLOCKED", "FAIL"}
VALID_SUPPORTING_RESULTS = {"PASS-LIVE", "PASS-AUTOMATED"}
VALID_EVIDENCE_CLASSES = {
    "not-run",
    "historical-live",
    "pre-final-live",
    "final-source-live",
    "historical-automated",
    "pre-final-automated",
    "final-source-automated",
}


def validate_contract(value: dict) -> dict:
    if value.get("schemaVersion") != 1 or value.get("contractId") != "main-continuity-v1":
        raise ValueError("Unsupported Main Continuity contract identity")
    requirements = value.get("requirements")
    cases = value.get("qaCases")
    candidates = value.get("candidateArtifacts")
    if not isinstance(requirements, list) or not requirements:
        raise ValueError("Contract must declare requirements")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Contract must declare QA cases")
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("Contract must declare candidate/artifact identities")

    candidate_ids = [str(item.get("id") or "") for item in candidates]
    if len(candidate_ids) != len(set(candidate_ids)) or any(
        not item.startswith("MC-CAND-") for item in candidate_ids
    ):
        raise ValueError("Candidate/artifact IDs must be unique MC-CAND-* values")
    candidate_by_id: dict[str, dict] = {}
    for candidate in candidates:
        candidate_id = str(candidate.get("id") or "")
        evidence_class = str(candidate.get("evidenceClass") or "")
        artifact_identity = str(candidate.get("artifactIdentity") or "").strip()
        if evidence_class not in VALID_EVIDENCE_CLASSES:
            raise ValueError(f"Invalid evidence class for {candidate_id}")
        if not artifact_identity:
            raise ValueError(f"Candidate/artifact identity is required for {candidate_id}")
        if "codex://threads/" in artifact_identity or "/Users/" in artifact_identity:
            raise ValueError(f"Private candidate/artifact identity in {candidate_id}")
        if evidence_class.startswith("final-source-"):
            required_terms = ("LibreChat HEAD", "GlassHive HEAD", "dirty-tree", "activated")
            if any(term not in artifact_identity for term in required_terms):
                raise ValueError(f"Final-source identity is incomplete for {candidate_id}")
        candidate_by_id[candidate_id] = candidate

    case_ids = [str(item.get("id") or "") for item in cases]
    if len(case_ids) != len(set(case_ids)) or any(not item.startswith("MC-") for item in case_ids):
        raise ValueError("QA case IDs must be unique MC-* values")
    requirement_ids = [str(item.get("id") or "") for item in requirements]
    if len(requirement_ids) != len(set(requirement_ids)) or any(not item.startswith("MCK-") for item in requirement_ids):
        raise ValueError("Requirement IDs must be unique MCK-* values")
    referenced: set[str] = set()
    for requirement in requirements:
        if requirement.get("implementationStatus") not in VALID_STATUSES:
            raise ValueError(f"Invalid status for {requirement.get('id')}")
        if not requirement.get("sourceRefs") or not requirement.get("owners") or not requirement.get("expected"):
            raise ValueError(f"Incomplete trace for {requirement.get('id')}")
        for case_id in requirement.get("qaCases") or []:
            if case_id not in case_ids:
                raise ValueError(f"Unknown QA case {case_id} in {requirement.get('id')}")
            referenced.add(case_id)
    missing = sorted(set(case_ids) - referenced)
    if missing:
        raise ValueError(f"QA cases without requirements: {', '.join(missing)}")
    for case in cases:
        result = str(case.get("result") or "")
        if result not in VALID_CASE_RESULTS:
            raise ValueError(f"Invalid QA result for {case.get('id')}")
        supporting_result = str(case.get("supportingResult") or "")
        if supporting_result and supporting_result not in VALID_SUPPORTING_RESULTS:
            raise ValueError(f"Invalid supporting result for {case.get('id')}")
        if result != "NOT RUN" and not str(case.get("lastRun") or "").strip():
            raise ValueError(f"Dated QA evidence is required for {case.get('id')}")

        candidate_refs = case.get("candidateArtifactRefs")
        if not isinstance(candidate_refs, list) or not candidate_refs:
            raise ValueError(f"Candidate/artifact identity is required for {case.get('id')}")
        if len(candidate_refs) != len(set(candidate_refs)):
            raise ValueError(f"Duplicate candidate/artifact identity for {case.get('id')}")
        unknown_candidates = sorted(set(candidate_refs) - set(candidate_by_id))
        if unknown_candidates:
            raise ValueError(
                f"Unknown candidate/artifact identity for {case.get('id')}: "
                + ", ".join(unknown_candidates)
            )
        evidence_classes = {
            str(candidate_by_id[candidate_id]["evidenceClass"])
            for candidate_id in candidate_refs
        }
        if result == "NOT RUN":
            if evidence_classes != {"not-run"}:
                raise ValueError(f"NOT RUN case must use only not-run identity: {case.get('id')}")
            if supporting_result:
                raise ValueError(f"NOT RUN case cannot carry a supporting pass: {case.get('id')}")
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(case.get("catalogedOn") or "")):
                raise ValueError(f"NOT RUN case needs immutable catalogedOn: {case.get('id')}")
            continue
        if "not-run" in evidence_classes:
            raise ValueError(f"Recorded result cannot use not-run identity: {case.get('id')}")
        if supporting_result == "PASS-LIVE" and not any(
            item.endswith("-live") for item in evidence_classes
        ):
            raise ValueError(f"PASS-LIVE support requires a live candidate identity: {case.get('id')}")
        if supporting_result == "PASS-AUTOMATED" and not any(
            item.endswith("-automated") for item in evidence_classes
        ):
            raise ValueError(
                f"PASS-AUTOMATED support requires an automated candidate identity: {case.get('id')}"
            )
    return value


def load_contract() -> dict:
    return validate_contract(json.loads(CONTRACT.read_text(encoding="utf-8")))


def render(value: dict) -> str:
    candidate_by_id = {
        candidate["id"]: candidate for candidate in value["candidateArtifacts"]
    }
    requirement_by_case: dict[str, list[str]] = {}
    for requirement in value["requirements"]:
        for case_id in requirement["qaCases"]:
            requirement_by_case.setdefault(case_id, []).append(requirement["id"])
    lines = [
        "# Main Continuity Generated Coverage",
        "",
        "Generated from `contract.v1.json`. Do not edit by hand.",
        "",
        "## Requirements",
        "",
        "| ID | Requirement | Status | Owners | QA cases |",
        "| --- | --- | --- | --- | --- |",
    ]
    for requirement in value["requirements"]:
        lines.append(
            "| {id} | {title} | {status} | {owners} | {cases} |".format(
                id=requirement["id"],
                title=requirement["title"],
                status=requirement["implementationStatus"],
                owners="<br>".join(f"`{item}`" for item in requirement["owners"]),
                cases=", ".join(requirement["qaCases"]),
            )
        )
    lines.extend(
        [
            "",
            "## Candidate and artifact identities",
            "",
            "| ID | Evidence class | Public-safe artifact identity |",
            "| --- | --- | --- |",
        ]
    )
    for candidate in value["candidateArtifacts"]:
        lines.append(
            "| {id} | {evidence_class} | {artifact_identity} |".format(
                id=candidate["id"],
                evidence_class=candidate["evidenceClass"],
                artifact_identity=candidate["artifactIdentity"],
            )
        )
    lines.extend(
        [
            "",
            "## Acceptance cases",
            "",
            "| ID | Surface | Case | Requirements | Expected | Candidate/artifact | Supporting layer | Last run |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for case in value["qaCases"]:
        result = str(case["result"])
        supporting_result = str(case.get("supportingResult") or "—")
        last_run = str(case.get("lastRun") or "").strip()
        if result == "NOT RUN":
            rendered_run = f"NOT RUN — cataloged {case['catalogedOn']}"
        else:
            rendered_run = f"{result} — {last_run}"
        lines.append(
            "| {id} | {surface} | {name} | {requirements} | {expected} | {candidates} | {supporting_result} | {last_run} |".format(
                id=case["id"],
                surface=case["surface"],
                name=case["name"],
                requirements=", ".join(requirement_by_case[case["id"]]),
                expected=case["expected"],
                candidates="<br>".join(
                    "`{}` ({})".format(
                        candidate_id,
                        candidate_by_id[candidate_id]["evidenceClass"],
                    )
                    for candidate_id in case["candidateArtifactRefs"]
                ),
                supporting_result=supporting_result,
                last_run=rendered_run,
            )
        )
    lines.extend(
        [
            "",
            "`NOT RUN` is intentional until a dated exact-candidate report supplies fresh evidence.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    command = sys.argv[1] if len(sys.argv) > 1 else "check"
    value = load_contract()
    expected = render(value)
    if command == "generate":
        GENERATED.write_text(expected, encoding="utf-8")
        return 0
    if command == "check":
        if not GENERATED.exists() or GENERATED.read_text(encoding="utf-8") != expected:
            print("Main Continuity generated coverage is stale", file=sys.stderr)
            return 1
        return 0
    print("usage: main_continuity_contract.py [generate|check]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

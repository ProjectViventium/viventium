from __future__ import annotations

import hashlib
import json
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from prompt_workbench import installed_journey  # noqa: E402


SOURCE_HASH = "a" * 16
ARTIFACT_HASH = "b" * 64
MAIN_AGENT = "synthetic-main-agent"
SPECIALIST_AGENT = "synthetic-specialist-agent"


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _seal_lineage(lineage: dict[str, Any]) -> None:
    lineage.pop("manifestHash", None)
    lineage["manifestHash"] = _hash(
        json.dumps(lineage, sort_keys=True, separators=(",", ":"))
    )


def _prompt(prompt_id: str) -> dict[str, Any]:
    return {
        "id": prompt_id,
        "contentHash": _hash(f"content:{prompt_id}"),
        "bodyHash": _hash(f"body:{prompt_id}"),
        "includeCount": 0,
    }


def _lineage(
    cases: list[str],
    *,
    prompt_id: str,
    target: dict[str, str] | None = None,
) -> dict[str, Any]:
    prompt = _prompt(prompt_id)
    lineage: dict[str, Any] = {
        "schemaVersion": 1,
        "familyIds": ["synthetic-family"],
        "caseIds": cases,
        "rootPromptIds": [prompt_id],
        "promptDependencies": [
            {
                "id": prompt_id,
                "kind": "prompt",
                "status": "available",
                "direct": True,
                "contentHash": prompt["contentHash"],
                "bodyHash": prompt["bodyHash"],
                "renderedHash": _hash(f"rendered:{prompt_id}"),
            }
        ],
        "runtimeContextDependencies": [],
        "includeEdges": [],
        "promptCount": 1,
        "runtimeContextCount": 0,
    }
    if target is not None:
        lineage["executionTarget"] = target
    _seal_lineage(lineage)
    return lineage


def _fixture(kind: str = "main") -> dict[str, dict[str, Any]]:
    now = datetime.now(timezone.utc)
    run_id = f"{now.strftime('%Y%m%dT%H%M%SZ')}-0123456789ab"
    main_provider = "synthetic-main-provider"
    main_model = "synthetic-main-model"
    prompt_id = {
        "main": "main.identity",
        "specialist": "cortex.synthetic.execution",
        "activation": "cortex.synthetic.activation",
    }[kind]
    case_ids = ["synthetic-required", "synthetic-forbidden"]
    family: dict[str, Any] = {
        "id": "synthetic-family",
        "promptRefs": [prompt_id],
        "semanticJudge": kind != "activation",
        "cases": [
            {
                "id": case_ids[0],
                "promptRefs": [prompt_id],
                "required_activations": ["first"] if kind == "activation" else [],
                "allowed_activations": ["first"] if kind == "activation" else [],
            },
            {
                "id": case_ids[1],
                "promptRefs": [prompt_id],
                "required_activations": [],
                "allowed_activations": [],
            },
        ],
    }
    agent_id = SPECIALIST_AGENT if kind == "specialist" else MAIN_AGENT
    row: dict[str, Any] = {
        "id": run_id,
        "live": True,
        "createdAt": now.isoformat(),
        "candidateSourceHash": SOURCE_HASH,
        "returnCode": 0,
        "selectedCaseCount": len(case_ids),
        "selectedCaseIds": case_ids,
        "resultCount": len(case_ids),
        "lineageManifest": _lineage(case_ids, prompt_id=prompt_id),
        "semanticJudgeRequired": kind != "activation",
        "runnerSummary": {
            "status": "completed_full_semantic_passed",
            "completedCount": len(case_ids),
            "resultCount": len(case_ids),
            "failedCount": 0,
            "semanticJudgedCount": len(case_ids),
            "semanticPassedCount": len(case_ids),
        },
        "executionRoute": {
            "status": "verified",
            "artifactSha256": ARTIFACT_HASH,
            "requestedProvider": main_provider,
            "requestedModel": main_model,
            "requestedEffort": "medium",
            "effectiveProvider": main_provider,
            "effectiveModel": main_model,
            "effectiveEffort": "medium",
            "fallbackUsed": False,
            "fallbackAuthorized": False,
            "fallbackReason": "none",
            "configuredProvider": main_provider,
            "configuredModel": main_model,
            "configuredProviderHash": _hash(main_provider),
            "configuredModelHash": _hash(main_model),
            "observedProviderHash": _hash(main_provider),
            "observedModelHash": _hash(main_model),
            "completedCaseCount": len(case_ids),
            "caseEvidence": [
                {
                    "caseId": case_id,
                    "agentIdHash": _hash(agent_id),
                    "semanticJudged": True,
                    "semanticPassed": True,
                }
                for case_id in case_ids
            ],
        },
    }
    scheduled_run = {"status": "completed", "triggerKind": "scheduled"}
    prompts = [
        _prompt("main.identity"),
        _prompt("surface.wing"),
        _prompt("scheduler.consciousness_continuity_opportunity"),
        _prompt("cortex.synthetic.execution"),
        _prompt("cortex.synthetic.activation"),
    ]
    payloads: dict[str, dict[str, Any]] = {
        "/api/auth/status": {
            "authenticated": True,
            "admin": True,
            "method": "local_loopback_admin",
        },
        "/api/build-version": {
            "available": True,
            "indexHash": SOURCE_HASH,
            "entryAssets": ["/assets/synthetic.js"],
            "backend": {
                "loadedSourceHash": SOURCE_HASH,
                "currentSourceHash": SOURCE_HASH,
                "sourceCurrent": True,
            },
            "frontend": {
                "receiptAvailable": True,
                "schemaVersion": 1,
                "receiptFrontendInputHash": "c" * 64,
                "currentFrontendInputHash": "c" * 64,
                "receiptBuiltAssetHash": "d" * 64,
                "currentBuiltAssetHash": "d" * 64,
                "receiptBuiltFileCount": 1,
                "currentBuiltFileCount": 1,
                "sourceCurrent": True,
                "assetsCurrent": True,
                "receiptValid": True,
            },
        },
        "/api/frames": {
            "frames": [],
            "health": {
                "status": "empty",
                "source": "synthetic_runtime_logs",
                "reason": "no_matching_frames",
                "filesScanned": 1,
                "invalidEventCount": 0,
                "truncatedReadCount": 0,
                "releaseEvidence": False,
            },
        },
        "/api/prompts": {
            "prompts": prompts,
            "flow": {"nodes": [{"id": "main.identity"}]},
        },
        "/api/prompts/main.identity/workbench-context": {
            "delivery": {"kind": "managed_agent", "state": "synced"},
            "sync": {"state": "synced", "sourceHash": SOURCE_HASH, "liveHash": SOURCE_HASH},
        },
        "/api/prompts/surface.wing/workbench-context": {
            "delivery": {"kind": "compiled_runtime", "state": "synced"},
            "runtimePromptBundle": {
                "status": "ok",
                "promptState": "synced",
                "liveBundleAvailable": True,
            },
        },
        "/api/prompts/scheduler.consciousness_continuity_opportunity/workbench-context": {
            "delivery": {"kind": "compiled_runtime", "state": "synced"},
            "runtimePromptBundle": {
                "status": "ok",
                "promptState": "synced",
                "liveBundleAvailable": True,
            },
        },
        "/api/drafts": {"drafts": []},
        "/api/evals": {"caseCount": len(case_ids), "families": [family]},
        "/api/evals/execution-route": {
            "provider": main_provider,
            "model": main_model,
            "effort": "medium",
            "fallbacks": [],
        },
        "/api/evals/runs": {"runs": [row]},
        "/api/scheduled-prompts?readOnly=true": {
            "scheduledPrompts": [
                {
                    "id": "synthetic-continuity",
                    "sourcePromptId": "scheduler.consciousness_continuity_opportunity",
                    "active": True,
                    "latestScheduledRun": scheduled_run,
                },
                {
                    "id": "synthetic-nightly",
                    "templateId": installed_journey.NIGHTLY_TEMPLATE_ID,
                    "active": True,
                    "latestScheduledRun": scheduled_run,
                },
            ]
        },
        "/api/scheduled-prompts/synthetic-continuity/runs?readOnly=true": {
            "runs": [scheduled_run]
        },
        "/api/scheduled-prompts/synthetic-nightly/runs?readOnly=true": {
            "runs": [scheduled_run]
        },
        "/api/cognitive-integrity": {
            "schemaVersion": 3,
            "status": "ok",
            "blockingChecks": [],
            "checks": {
                name: {"status": "ok"}
                for name in installed_journey.REQUIRED_COGNITIVE_CHECKS
            },
        },
    }

    if kind == "specialist":
        target = {
            "mode": "direct_background_agent",
            "agentId": SPECIALIST_AGENT,
            "promptRef": prompt_id,
        }
        family.update({"runner": "background_execution", "executionTarget": target})
        row.update(
            {
                "family": family["id"],
                "executionTarget": target,
                "lineageManifest": _lineage(case_ids, prompt_id=prompt_id, target=target),
            }
        )
        payloads["/api/evals/execution-route?family=synthetic-family"] = {
            "kind": "background_execution",
            "family": family["id"],
            "agentId": SPECIALIST_AGENT,
            "promptRef": prompt_id,
            "provider": main_provider,
            "model": main_model,
            "effort": "medium",
            "fallbacks": [],
        }

    if kind == "activation":
        repetitions = 2
        targets = [
            {
                "key": "first",
                "agentId": "synthetic-first-agent",
                "promptRef": prompt_id,
            },
            {
                "key": "second",
                "agentId": "synthetic-second-agent",
                "promptRef": prompt_id,
            },
        ]
        family.update({"runner": "background_activation", "activationTargets": targets})
        configured_targets = [
            {
                "targetKey": "first",
                "provider": "first-provider",
                "model": "first-model",
                "effort": "low",
                "fallbacks": [
                    {
                        "provider": "approved-fallback",
                        "model": "fallback-model",
                        "effort": "high",
                    }
                ],
            },
            {
                "targetKey": "second",
                "provider": "second-provider",
                "model": "second-model",
                "effort": "none",
                "fallbacks": [],
            },
        ]
        evidence: list[dict[str, Any]] = []
        for case in family["cases"]:
            for target in configured_targets:
                target_key = target["targetKey"]
                required = target_key in case["required_activations"]
                allowed = target_key in case["allowed_activations"]
                for repetition in range(1, repetitions + 1):
                    evidence.append(
                        {
                            "caseId": case["id"],
                            "targetKey": target_key,
                            "repetition": repetition,
                            "required": required,
                            "allowed": allowed,
                            "actual": required,
                            "passed": True,
                            "requestedProvider": target["provider"],
                            "requestedModel": target["model"],
                            "requestedEffort": target["effort"],
                            "effectiveProvider": target["provider"],
                            "effectiveModel": target["model"],
                            "effectiveEffort": target["effort"],
                            "fallbackReason": "none",
                            "primaryFailureVerified": False,
                        }
                    )
        result_count = len(evidence)
        row.update(
            {
                "family": family["id"],
                "resultCount": result_count,
                "runnerSummary": {
                    "status": "passed",
                    "selectedCaseCount": len(case_ids),
                    "selectedTargetCount": len(targets),
                    "repetitions": repetitions,
                    "resultCount": result_count,
                    "completedCount": result_count,
                    "passCount": result_count,
                    **{
                        field: 0
                        for field in installed_journey.ACTIVATION_QUALITY_FAILURE_FIELDS
                    },
                },
                "executionRoute": {
                    "status": "verified",
                    "artifactSha256": ARTIFACT_HASH,
                    "completedCaseCount": result_count,
                    "caseEvidence": evidence,
                    "routes": [
                        {
                            "targetKey": target["targetKey"],
                            "requestedProvider": target["provider"],
                            "requestedModel": target["model"],
                            "requestedEffort": target["effort"],
                            "configuredProvider": target["provider"],
                            "configuredModel": target["model"],
                            "effectiveProvider": target["provider"],
                            "effectiveModel": target["model"],
                            "effectiveEffort": target["effort"],
                            "fallbackUsed": False,
                            "fallbackAuthorized": False,
                            "fallbackReason": "none",
                        }
                        for target in configured_targets
                    ],
                },
            }
        )
        payloads["/api/evals/execution-route?family=synthetic-family"] = {
            "kind": "background_activation",
            "family": family["id"],
            "targets": configured_targets,
        }

    return payloads


def _inspect(payloads: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return installed_journey.inspect_installed_workbench(
        "http://127.0.0.1:8781",
        fetch=lambda path, _timeout: payloads[path],
    )


@pytest.mark.parametrize("kind", ("main", "specialist", "activation"))
def test_authentic_current_case_evidence_is_accepted(kind: str) -> None:
    report = _inspect(_fixture(kind))

    assert report["status"] == "pass"
    assert report["counts"]["verifiedEvalCaseCount"] == 2


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("id", None),
        ("id", "../../synthetic-private-run"),
        ("id", "20260825T160000Z-ABCDEF012345"),
        ("candidateSourceHash", None),
        ("candidateSourceHash", "c" * 16),
        ("candidateSourceHash", "A" * 16),
    ),
)
def test_rejects_missing_unsafe_or_unbound_run_identity(field: str, value: Any) -> None:
    payloads = _fixture()
    row = payloads["/api/evals/runs"]["runs"][0]
    if value is None:
        row.pop(field)
    else:
        row[field] = value

    report = _inspect(payloads)

    assert report["status"] == "blocked"
    assert "exact_model_route_not_verified" in report["blockingChecks"]


@pytest.mark.parametrize("digest", (None, "b" * 63, "B" * 64, "z" * 64))
def test_rejects_missing_or_noncanonical_execution_artifact_digest(digest: Any) -> None:
    payloads = _fixture()
    route = payloads["/api/evals/runs"]["runs"][0]["executionRoute"]
    if digest is None:
        route.pop("artifactSha256")
    else:
        route["artifactSha256"] = digest

    assert _inspect(payloads)["status"] == "blocked"


@pytest.mark.parametrize(
    "change",
    (
        "missing",
        "duplicate",
        "unknown",
        "semantic_unjudged",
        "semantic_failed",
        "malformed_agent_hash",
        "mixed_agents",
    ),
)
def test_rejects_forged_exact_summary_without_complete_semantic_case_evidence(
    change: str,
) -> None:
    payloads = _fixture()
    evidence = payloads["/api/evals/runs"]["runs"][0]["executionRoute"]["caseEvidence"]
    if change == "missing":
        evidence.pop()
    elif change == "duplicate":
        evidence[1]["caseId"] = evidence[0]["caseId"]
    elif change == "unknown":
        evidence[1]["caseId"] = "synthetic-never-executed"
    elif change == "semantic_unjudged":
        evidence[1]["semanticJudged"] = False
    elif change == "semantic_failed":
        evidence[1]["semanticPassed"] = False
    elif change == "malformed_agent_hash":
        evidence[0]["agentIdHash"] = "A" * 16
    else:
        evidence[1]["agentIdHash"] = _hash("another-agent")

    assert _inspect(payloads)["status"] == "blocked"


def test_rejects_specialist_evidence_created_by_the_main_agent() -> None:
    payloads = _fixture("specialist")
    for evidence in payloads["/api/evals/runs"]["runs"][0]["executionRoute"]["caseEvidence"]:
        evidence["agentIdHash"] = _hash(MAIN_AGENT)

    assert _inspect(payloads)["status"] == "blocked"


@pytest.mark.parametrize("field", ("contentHash", "bodyHash"))
def test_rejects_resealed_lineage_when_prompt_source_has_changed(field: str) -> None:
    payloads = _fixture("specialist")
    lineage = payloads["/api/evals/runs"]["runs"][0]["lineageManifest"]
    lineage["promptDependencies"][0][field] = "c" * 16
    _seal_lineage(lineage)

    assert _inspect(payloads)["status"] == "blocked"


def test_rejects_resealed_lineage_missing_the_specialist_prompt_dependency() -> None:
    payloads = _fixture("specialist")
    lineage = payloads["/api/evals/runs"]["runs"][0]["lineageManifest"]
    lineage.update({"rootPromptIds": [], "promptDependencies": [], "promptCount": 0})
    _seal_lineage(lineage)

    assert _inspect(payloads)["status"] == "blocked"


@pytest.mark.parametrize(
    "change",
    (
        "registry_content_changed",
        "registry_body_changed",
        "missing_root_reference",
        "unknown_dependency",
        "wrong_direct_flag",
        "missing_required_include",
        "malformed_rendered_hash",
    ),
)
def test_rejects_resealed_lineage_not_bound_to_the_current_prompt_catalog(
    change: str,
) -> None:
    payloads = _fixture("specialist")
    family = payloads["/api/evals"]["families"][0]
    lineage = payloads["/api/evals/runs"]["runs"][0]["lineageManifest"]
    dependency = lineage["promptDependencies"][0]
    registry_prompt = next(
        prompt
        for prompt in payloads["/api/prompts"]["prompts"]
        if prompt["id"] == dependency["id"]
    )

    if change == "registry_content_changed":
        registry_prompt["contentHash"] = "c" * 16
    elif change == "registry_body_changed":
        registry_prompt["bodyHash"] = "c" * 16
    elif change == "missing_root_reference":
        family["promptRefs"] = []
        for case in family["cases"]:
            case["promptRefs"] = []
    elif change == "unknown_dependency":
        dependency["id"] = "cortex.synthetic.missing"
    elif change == "wrong_direct_flag":
        dependency["direct"] = False
    elif change == "missing_required_include":
        registry_prompt["includeCount"] = 1
    else:
        dependency["renderedHash"] = "INVALID"
    _seal_lineage(lineage)

    assert _inspect(payloads)["status"] == "blocked"


@pytest.mark.parametrize("field", ("semanticJudgedCount", "semanticPassedCount"))
@pytest.mark.parametrize("value", (0, 1, 3, True))
def test_rejects_forged_semantic_aggregates_when_case_verdicts_disagree(
    field: str,
    value: Any,
) -> None:
    payloads = _fixture()
    payloads["/api/evals/runs"]["runs"][0]["runnerSummary"][field] = value

    assert _inspect(payloads)["status"] == "blocked"


def test_accepts_a_nonsemantic_exact_run_without_inventing_judge_verdicts() -> None:
    payloads = _fixture()
    family = payloads["/api/evals"]["families"][0]
    row = payloads["/api/evals/runs"]["runs"][0]
    family["semanticJudge"] = False
    row["semanticJudgeRequired"] = False
    row["runnerSummary"].pop("semanticJudgedCount")
    row["runnerSummary"].pop("semanticPassedCount")
    for evidence in row["executionRoute"]["caseEvidence"]:
        evidence.update({"semanticJudged": False, "semanticPassed": False})

    assert _inspect(payloads)["status"] == "pass"


@pytest.mark.parametrize(
    "change",
    (
        "missing",
        "duplicate",
        "wrong_case",
        "wrong_target",
        "zero_repetition",
        "overflow_repetition",
        "required_forged",
        "allowed_forged",
        "required_false_negative",
        "forbidden_false_positive",
        "passed_false",
        "wrong_provider",
        "wrong_model",
        "unverified_primary_failure",
        "malformed_primary_failure",
    ),
)
def test_rejects_incorrect_duplicate_or_unauthenticated_activation_decisions(
    change: str,
) -> None:
    payloads = _fixture("activation")
    route = payloads["/api/evals/runs"]["runs"][0]["executionRoute"]
    evidence = route["caseEvidence"]
    required = next(item for item in evidence if item["required"])
    forbidden = next(item for item in evidence if not item["allowed"])
    if change == "missing":
        evidence.pop()
    elif change == "duplicate":
        evidence[-1] = deepcopy(evidence[0])
    elif change == "wrong_case":
        evidence[0]["caseId"] = "synthetic-never-executed"
    elif change == "wrong_target":
        evidence[0]["targetKey"] = "synthetic-never-configured"
    elif change == "zero_repetition":
        evidence[0]["repetition"] = 0
    elif change == "overflow_repetition":
        evidence[0]["repetition"] = 3
    elif change == "required_forged":
        required["required"] = False
    elif change == "allowed_forged":
        forbidden["allowed"] = True
    elif change == "required_false_negative":
        required["actual"] = False
    elif change == "forbidden_false_positive":
        forbidden["actual"] = True
    elif change == "passed_false":
        evidence[0]["passed"] = False
    elif change == "wrong_provider":
        evidence[0]["effectiveProvider"] = "synthetic-unauthorized"
    elif change == "wrong_model":
        evidence[0]["effectiveModel"] = "synthetic-unauthorized"
    elif change == "unverified_primary_failure":
        required.update(
            {
                "effectiveProvider": "approved-fallback",
                "effectiveModel": "fallback-model",
                "primaryFailureVerified": False,
            }
        )
        route["routes"][0].update(
            {
                "effectiveProvider": "approved-fallback",
                "effectiveModel": "fallback-model",
                "fallbackUsed": True,
                "fallbackAuthorized": True,
            }
        )
    else:
        evidence[0]["primaryFailureVerified"] = "true"

    assert _inspect(payloads)["status"] == "blocked"


@pytest.mark.parametrize(
    "change",
    (
        "missing_required_catalog",
        "missing_allowed_catalog",
        "required_not_allowed",
        "unknown_allowed_target",
        "duplicate_required_target",
        "duplicate_allowed_target",
        "missing_declared_target",
        "duplicate_declared_target",
    ),
)
def test_rejects_activation_expectations_not_bound_to_the_current_case_catalog(
    change: str,
) -> None:
    payloads = _fixture("activation")
    family = payloads["/api/evals"]["families"][0]
    case = family["cases"][0]
    if change == "missing_required_catalog":
        case.pop("required_activations")
    elif change == "missing_allowed_catalog":
        case.pop("allowed_activations")
    elif change == "required_not_allowed":
        case["allowed_activations"] = []
    elif change == "unknown_allowed_target":
        case["allowed_activations"].append("unconfigured-target")
    elif change == "duplicate_required_target":
        case["required_activations"].append("first")
    elif change == "duplicate_allowed_target":
        case["allowed_activations"].append("first")
    elif change == "missing_declared_target":
        family["activationTargets"].pop()
    else:
        family["activationTargets"][1]["key"] = "first"

    report = _inspect(payloads)

    assert report["status"] == "blocked"


@pytest.mark.parametrize("actual", (False, True))
def test_accepts_either_documented_decision_for_an_optional_allowed_target(
    actual: bool,
) -> None:
    payloads = _fixture("activation")
    family = payloads["/api/evals"]["families"][0]
    family["cases"][1]["allowed_activations"] = ["second"]
    for evidence in payloads["/api/evals/runs"]["runs"][0]["executionRoute"][
        "caseEvidence"
    ]:
        if evidence["caseId"] == "synthetic-forbidden" and evidence["targetKey"] == "second":
            evidence.update({"allowed": True, "actual": actual})

    assert _inspect(payloads)["status"] == "pass"


def test_accepts_only_a_configured_fallback_after_a_verified_primary_failure() -> None:
    payloads = _fixture("activation")
    route = payloads["/api/evals/runs"]["runs"][0]["executionRoute"]
    for evidence in route["caseEvidence"]:
        if evidence["targetKey"] == "first":
            evidence.update(
                {
                    "effectiveProvider": "approved-fallback",
                    "effectiveModel": "fallback-model",
                    "effectiveEffort": "high",
                    "fallbackReason": "provider_timeout",
                    "primaryFailureVerified": True,
                }
            )
    route["routes"][0].update(
        {
            "effectiveProvider": "approved-fallback",
            "effectiveModel": "fallback-model",
            "effectiveEffort": "high",
            "fallbackUsed": True,
            "fallbackAuthorized": True,
            "fallbackReason": "provider_timeout",
        }
    )

    assert _inspect(payloads)["status"] == "pass"


def test_accepts_a_primary_retry_after_a_verified_earlier_primary_failure() -> None:
    payloads = _fixture("activation")
    payloads["/api/evals/runs"]["runs"][0]["executionRoute"]["caseEvidence"][0][
        "primaryFailureVerified"
    ] = True

    assert _inspect(payloads)["status"] == "pass"

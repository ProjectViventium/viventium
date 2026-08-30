from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable

from .auth import strict_loopback_origin


REQUIRED_PROMPTS = (
    "main.identity",
    "surface.wing",
    "scheduler.consciousness_continuity_opportunity",
)
NIGHTLY_TEMPLATE_ID = "workbench_nightly_subconscious_thought_formation_v1"
MAX_EVAL_EVIDENCE_AGE_SECONDS = 36 * 60 * 60
SUCCESSFUL_EVAL_STATES = frozenset({"completed_full", "completed_full_semantic_passed"})
EVAL_QUALITY_FAILURE_FIELDS = (
    "failedCount",
    "semanticFailedCount",
    "semanticJudgeUnavailableCount",
    "duplicateResponseQualityFailureCount",
    "unresolvedAsyncQualityFailureCount",
)
ACTIVATION_QUALITY_FAILURE_FIELDS = (
    "failureCount",
    "failedCaseRunCount",
    "falsePositiveCount",
    "falseNegativeCount",
    "unavailableCount",
    "unavailableRequiredCount",
    "timeoutOrProviderErrorCount",
    "inconsistentDecisionCount",
    "semanticInconsistentDecisionCount",
)
REQUIRED_COGNITIVE_CHECKS = frozenset(
    {
        "runtimeConfigDrift",
        "promptBundleDrift",
        "sourceProviderCapabilityTransport",
        "liveProviderCapabilityTransport",
        "sourceMemoryExposure",
        "liveMemoryExposure",
        "glasshiveHostWorkerRuntime",
        "workbenchNightly",
        "workbenchHealthContext",
        "workbenchConsciousnessContinuity",
        "qaTestAccount",
        "qaAccountSavedMemoryReadRuntime",
        "qaAccountImmediateMemoryWriterRuntime",
        "conversationRecallRuntime",
        "memoryHardening",
    }
)
FetchJson = Callable[[str, float], dict[str, Any]]


class _RejectRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request: Any, response: Any, code: int, message: str, headers: Any, new_url: str) -> None:
        raise urllib.error.HTTPError(request.full_url, code, "Workbench proof rejects redirects", headers, response)


def _frontend_receipt_is_current(frontend: Any) -> bool:
    if not isinstance(frontend, dict):
        return False
    receipt_input_hash = frontend.get("receiptFrontendInputHash")
    current_input_hash = frontend.get("currentFrontendInputHash")
    receipt_asset_hash = frontend.get("receiptBuiltAssetHash")
    current_asset_hash = frontend.get("currentBuiltAssetHash")
    receipt_file_count = frontend.get("receiptBuiltFileCount")
    current_file_count = frontend.get("currentBuiltFileCount")
    return bool(
        frontend.get("receiptAvailable") is True
        and frontend.get("schemaVersion") == 1
        and frontend.get("sourceCurrent") is True
        and frontend.get("assetsCurrent") is True
        and frontend.get("receiptValid") is True
        and all(
            isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)
            for value in (
                receipt_input_hash,
                current_input_hash,
                receipt_asset_hash,
                current_asset_hash,
            )
        )
        and receipt_input_hash == current_input_hash
        and receipt_asset_hash == current_asset_hash
        and isinstance(receipt_file_count, int)
        and not isinstance(receipt_file_count, bool)
        and receipt_file_count > 0
        and receipt_file_count == current_file_count
    )


def _frames_health_blocker(payload: Any) -> str | None:
    if not isinstance(payload, dict) or not isinstance(payload.get("frames"), list):
        return "frames_health_unverified"
    health = payload.get("health")
    if not isinstance(health, dict):
        return "frames_health_unverified"
    status = health.get("status")
    if status == "degraded":
        return "frames_health_degraded"
    if status == "unavailable":
        return "frames_health_unavailable"
    if status not in {"ok", "empty"}:
        return "frames_health_unverified"
    if (
        not isinstance(health.get("source"), str)
        or not health["source"]
        or not isinstance(health.get("reason"), str)
        or health.get("releaseEvidence") is not False
        or any(
            not isinstance(health.get(field), int)
            or isinstance(health.get(field), bool)
            or health[field] < 0
            for field in ("filesScanned", "invalidEventCount", "truncatedReadCount")
        )
    ):
        return "frames_health_unverified"
    return None


def _local_fetch(origin: str) -> FetchJson:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _RejectRedirects())

    def fetch(path: str, timeout: float) -> dict[str, Any]:
        if not path.startswith("/api/"):
            raise ValueError("Workbench proof accepts API paths only")
        request = urllib.request.Request(
            f"{origin}{path}",
            headers={"Accept": "application/json"},
            method="GET",
        )
        with opener.open(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Workbench proof requires object responses")
        return payload

    return fetch


def _current_verified_run(
    row: dict[str, Any],
    configured_route: dict[str, Any] | None,
    required_case_ids: frozenset[str],
    case_catalog: dict[str, dict[str, Any]],
    family_route: Callable[[str], dict[str, Any] | None],
    *,
    installed_source_hash: str,
    prompt_catalog: dict[str, dict[str, Any]],
) -> bool:
    route = row.get("executionRoute")
    summary = row.get("runnerSummary")
    selected_ids = row.get("selectedCaseIds")
    run_id = row.get("id")
    if (
        row.get("live") is not True
        or not isinstance(run_id, str)
        or not re.fullmatch(r"[0-9]{8}T[0-9]{6}Z-[0-9a-f]{12}", run_id)
        or not isinstance(installed_source_hash, str)
        or not re.fullmatch(r"[0-9a-f]{16}", installed_source_hash)
        or row.get("candidateSourceHash") != installed_source_hash
        or not isinstance(row.get("returnCode"), int)
        or isinstance(row.get("returnCode"), bool)
        or row.get("returnCode") != 0
        or not isinstance(route, dict)
        or route.get("status") != "verified"
        or not isinstance(route.get("artifactSha256"), str)
        or not re.fullmatch(r"[0-9a-f]{64}", route["artifactSha256"])
        or not isinstance(selected_ids, list)
        or not selected_ids
        or any(not isinstance(case_id, str) or not case_id for case_id in selected_ids)
        or len(set(selected_ids)) != len(selected_ids)
        or not set(selected_ids).issubset(required_case_ids)
        or not isinstance(summary, dict)
    ):
        return False

    entries = [case_catalog[case_id] for case_id in selected_ids]
    lineage = row.get("lineageManifest")
    family_ids = sorted({entry["familyId"] for entry in entries})
    expected_prompt_ids = sorted(
        {
            prompt_id
            for entry in entries
            for prompt_id in entry.get("promptRefs", frozenset())
        }
    )
    if (
        not isinstance(lineage, dict)
        or lineage.get("schemaVersion") != 1
        or lineage.get("caseIds") != selected_ids
        or lineage.get("familyIds") != family_ids
        or lineage.get("rootPromptIds") != expected_prompt_ids
        or not isinstance(lineage.get("promptDependencies"), list)
        or not isinstance(lineage.get("runtimeContextDependencies"), list)
        or not isinstance(lineage.get("includeEdges"), list)
        or lineage.get("promptCount") != len(lineage["promptDependencies"])
        or lineage.get("runtimeContextCount") != len(lineage["runtimeContextDependencies"])
        or any(
            not isinstance(dependency, dict) or dependency.get("status") == "unknown_contract"
            for dependency in lineage["runtimeContextDependencies"]
        )
    ):
        return False
    prompt_dependencies: dict[str, dict[str, Any]] = {}
    for dependency in lineage["promptDependencies"]:
        if not isinstance(dependency, dict):
            return False
        dependency_id = dependency.get("id")
        current_prompt = prompt_catalog.get(dependency_id) if isinstance(dependency_id, str) else None
        if (
            not isinstance(dependency_id, str)
            or not dependency_id
            or dependency_id in prompt_dependencies
            or not isinstance(current_prompt, dict)
            or dependency.get("kind") != "prompt"
            or dependency.get("status") != "available"
            or dependency.get("direct") is not (dependency_id in expected_prompt_ids)
            or not isinstance(dependency.get("renderedHash"), str)
            or not re.fullmatch(r"[0-9a-f]{16}", dependency["renderedHash"])
            or any(
                not isinstance(dependency.get(field), str)
                or not re.fullmatch(r"[0-9a-f]{16}", dependency[field])
                or dependency[field] != current_prompt.get(field)
                for field in ("contentHash", "bodyHash")
            )
        ):
            return False
        prompt_dependencies[dependency_id] = dependency
    if not set(expected_prompt_ids).issubset(prompt_dependencies):
        return False
    include_edges: set[tuple[str, str]] = set()
    for edge in lineage["includeEdges"]:
        if not isinstance(edge, dict):
            return False
        source = edge.get("from")
        target = edge.get("to")
        if (
            not isinstance(source, str)
            or not isinstance(target, str)
            or source == target
            or source not in prompt_dependencies
            or target not in prompt_dependencies
            or edge.get("kind") != "includes"
            or (source, target) in include_edges
        ):
            return False
        include_edges.add((source, target))
    for dependency_id in prompt_dependencies:
        include_count = prompt_catalog[dependency_id].get("includeCount")
        if (
            not isinstance(include_count, int)
            or isinstance(include_count, bool)
            or include_count < 0
            or include_count
            != sum(1 for source, _target in include_edges if source == dependency_id)
        ):
            return False
    reachable_prompts = set(expected_prompt_ids)
    while True:
        expanded = reachable_prompts | {
            target for source, target in include_edges if source in reachable_prompts
        }
        if expanded == reachable_prompts:
            break
        reachable_prompts = expanded
    if reachable_prompts != set(prompt_dependencies):
        return False
    manifest_hash = lineage.get("manifestHash")
    if not isinstance(manifest_hash, str) or not re.fullmatch(r"[0-9a-f]{16}", manifest_hash):
        return False
    unsigned_lineage = {key: value for key, value in lineage.items() if key != "manifestHash"}
    try:
        expected_manifest_hash = hashlib.sha256(
            json.dumps(unsigned_lineage, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:16]
    except (TypeError, ValueError):
        return False
    if manifest_hash != expected_manifest_hash:
        return False

    specialized = {entry["familyId"] for entry in entries if entry["runner"]}
    if specialized:
        if len(specialized) != 1 or len({entry["familyId"] for entry in entries}) != 1:
            return False
        family_id = next(iter(specialized))
        kind = entries[0]["runner"]
        if row.get("family") != family_id or kind not in {"background_execution", "background_activation"}:
            return False
        configured_route = family_route(family_id)
        if (
            not isinstance(configured_route, dict)
            or configured_route.get("kind") != kind
            or configured_route.get("family") != family_id
        ):
            return False
    else:
        kind = "main"
        if not isinstance(configured_route, dict):
            return False

    selected_count = len(selected_ids)
    selected_case_count = row.get("selectedCaseCount")
    if (
        not isinstance(selected_case_count, int)
        or isinstance(selected_case_count, bool)
        or selected_case_count != selected_count
    ):
        return False

    if kind == "background_activation":
        if summary.get("status") != "passed":
            return False
        targets = configured_route.get("targets")
        if not isinstance(targets, list) or not targets:
            return False
        configured_targets: dict[str, dict[str, Any]] = {}
        for target in targets:
            if not isinstance(target, dict):
                return False
            key = target.get("targetKey")
            if not isinstance(key, str) or not key or key in configured_targets:
                return False
            if not all(
                isinstance(target.get(field), str) and bool(target[field])
                for field in ("provider", "model")
            ):
                return False
            fallbacks = target.get("fallbacks") or []
            if not isinstance(fallbacks, list):
                return False
            seen_routes = {(target["provider"], target["model"])}
            for fallback in fallbacks:
                if (
                    not isinstance(fallback, dict)
                    or not isinstance(fallback.get("provider"), str)
                    or not fallback["provider"]
                    or not isinstance(fallback.get("model"), str)
                    or not fallback["model"]
                    or (fallback["provider"], fallback["model"]) in seen_routes
                ):
                    return False
                seen_routes.add((fallback["provider"], fallback["model"]))
            configured_targets[key] = target
        if any(
            entry.get("activationTargetKeys") != frozenset(configured_targets)
            for entry in entries
        ):
            return False
        repetitions = summary.get("repetitions")
        if not isinstance(repetitions, int) or isinstance(repetitions, bool) or repetitions < 1:
            return False
        expected_results = selected_count * len(configured_targets) * repetitions
        expected_counts = (
            (summary.get("selectedCaseCount"), selected_count),
            (summary.get("selectedTargetCount"), len(configured_targets)),
            (row.get("resultCount"), expected_results),
            (summary.get("resultCount"), expected_results),
            (summary.get("completedCount"), expected_results),
            (summary.get("passCount"), expected_results),
            (route.get("completedCaseCount"), expected_results),
        )
        if any(
            not isinstance(value, int) or isinstance(value, bool) or value != expected
            for value, expected in expected_counts
        ):
            return False
        for field in ACTIVATION_QUALITY_FAILURE_FIELDS:
            value = summary.get(field)
            if not isinstance(value, int) or isinstance(value, bool) or value != 0:
                return False
        observed_routes = route.get("routes")
        if not isinstance(observed_routes, list) or not observed_routes:
            return False
        observed_targets: set[str] = set()
        observed_variants: set[tuple[str, str, str]] = set()
        for observed in observed_routes:
            if not isinstance(observed, dict):
                return False
            target_key = observed.get("targetKey")
            if not isinstance(target_key, str) or not target_key:
                return False
            current = configured_targets.get(target_key)
            if current is None:
                return False
            primary = (current.get("provider"), current.get("model"))
            if (
                observed.get("configuredProvider"),
                observed.get("configuredModel"),
            ) != primary:
                return False
            effective = (observed.get("effectiveProvider"), observed.get("effectiveModel"))
            fallbacks = {
                (fallback.get("provider"), fallback.get("model"))
                for fallback in current.get("fallbacks") or []
                if isinstance(fallback, dict)
            }
            uses_fallback = effective != primary
            if effective not in {primary, *fallbacks}:
                return False
            if (
                observed.get("fallbackUsed") is not uses_fallback
                or observed.get("fallbackAuthorized") is not uses_fallback
            ):
                return False
            variant = (str(target_key), str(effective[0]), str(effective[1]))
            if variant in observed_variants:
                return False
            observed_variants.add(variant)
            observed_targets.add(str(target_key))
        if observed_targets != set(configured_targets):
            return False
        evidence_rows = route.get("caseEvidence")
        if not isinstance(evidence_rows, list) or len(evidence_rows) != expected_results:
            return False
        expected_decisions = {
            (case_id, target_key, repetition)
            for case_id in selected_ids
            for target_key in configured_targets
            for repetition in range(1, repetitions + 1)
        }
        seen_decisions: set[tuple[str, str, int]] = set()
        evidenced_variants: set[tuple[str, str, str]] = set()
        for evidence in evidence_rows:
            if not isinstance(evidence, dict):
                return False
            case_id = evidence.get("caseId")
            target_key = evidence.get("targetKey")
            repetition = evidence.get("repetition")
            if (
                not isinstance(case_id, str)
                or case_id not in selected_ids
                or not isinstance(target_key, str)
                or target_key not in configured_targets
                or not isinstance(repetition, int)
                or isinstance(repetition, bool)
                or not 1 <= repetition <= repetitions
            ):
                return False
            decision = (case_id, target_key, repetition)
            if decision not in expected_decisions or decision in seen_decisions:
                return False
            seen_decisions.add(decision)
            catalog_case = case_catalog[case_id]
            required = target_key in catalog_case.get("requiredActivations", frozenset())
            allowed = target_key in catalog_case.get("allowedActivations", frozenset())
            actual = evidence.get("actual")
            if (
                evidence.get("required") is not required
                or evidence.get("allowed") is not allowed
                or not isinstance(actual, bool)
                or evidence.get("passed") is not True
                or (required and not actual)
                or (actual and not allowed)
            ):
                return False
            current = configured_targets[target_key]
            effective = (evidence.get("effectiveProvider"), evidence.get("effectiveModel"))
            primary = (current["provider"], current["model"])
            allowed_routes = {
                primary,
                *{
                    (fallback["provider"], fallback["model"])
                    for fallback in current.get("fallbacks") or []
                },
            }
            uses_fallback = effective != primary
            primary_failure_verified = evidence.get("primaryFailureVerified")
            if (
                effective not in allowed_routes
                or not isinstance(primary_failure_verified, bool)
                or (uses_fallback and primary_failure_verified is not True)
            ):
                return False
            variant = (target_key, str(effective[0]), str(effective[1]))
            if variant not in observed_variants:
                return False
            evidenced_variants.add(variant)
        if seen_decisions != expected_decisions or evidenced_variants != observed_variants:
            return False
    else:
        if (
            summary.get("status") not in SUCCESSFUL_EVAL_STATES
            or route.get("configuredProvider") != configured_route.get("provider")
            or route.get("configuredModel") != configured_route.get("model")
        ):
            return False
        if kind == "background_execution":
            target = row.get("executionTarget")
            declared = entries[0].get("executionTarget")
            if (
                not isinstance(target, dict)
                or not isinstance(declared, dict)
                or target.get("agentId") != declared.get("agentId")
                or target.get("promptRef") != declared.get("promptRef")
                or target.get("agentId") != configured_route.get("agentId")
                or target.get("promptRef") != configured_route.get("promptRef")
                or lineage.get("executionTarget") != target
                or target.get("promptRef") not in prompt_dependencies
                or target.get("promptRef") not in expected_prompt_ids
                or any(
                    dependency.get("id") == "runtime.feelings.current_state"
                    for dependency in lineage["runtimeContextDependencies"]
                )
            ):
                return False
        for value in (
            row.get("resultCount"),
            summary.get("completedCount"),
            summary.get("resultCount"),
            route.get("completedCaseCount"),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value != selected_count:
                return False
        for field in EVAL_QUALITY_FAILURE_FIELDS:
            value = summary.get(field, 0)
            if not isinstance(value, int) or isinstance(value, bool) or value != 0:
                return False
        for configured, observed, source_key in (
            ("configuredProviderHash", "observedProviderHash", "provider"),
            ("configuredModelHash", "observedModelHash", "model"),
        ):
            value = route.get(configured)
            expected = hashlib.sha256(str(configured_route.get(source_key) or "").encode("utf-8")).hexdigest()[:16]
            if (
                not isinstance(value, str)
                or not re.fullmatch(r"[0-9a-f]{16}", value)
                or value != route.get(observed)
                or value != expected
            ):
                return False
        evidence_rows = route.get("caseEvidence")
        if not isinstance(evidence_rows, list) or len(evidence_rows) != selected_count:
            return False
        evidenced_case_ids: set[str] = set()
        evidenced_agent_ids: set[str] = set()
        semantic_judged = 0
        semantic_passed = 0
        for evidence in evidence_rows:
            if not isinstance(evidence, dict):
                return False
            case_id = evidence.get("caseId")
            agent_hash = evidence.get("agentIdHash")
            judged = evidence.get("semanticJudged")
            passed = evidence.get("semanticPassed")
            if (
                not isinstance(case_id, str)
                or case_id not in selected_ids
                or case_id in evidenced_case_ids
                or not isinstance(agent_hash, str)
                or not re.fullmatch(r"[0-9a-f]{16}", agent_hash)
                or not isinstance(judged, bool)
                or not isinstance(passed, bool)
                or (passed and not judged)
                or (judged and not passed)
                or (
                    (kind == "background_execution" or case_catalog[case_id]["semanticJudgeRequired"])
                    and (not judged or not passed)
                )
            ):
                return False
            evidenced_case_ids.add(case_id)
            evidenced_agent_ids.add(agent_hash)
            semantic_judged += int(judged)
            semantic_passed += int(passed)
        if evidenced_case_ids != set(selected_ids) or len(evidenced_agent_ids) != 1:
            return False
        if kind == "background_execution":
            expected_agent_hash = hashlib.sha256(
                str(configured_route["agentId"]).encode("utf-8")
            ).hexdigest()[:16]
            if evidenced_agent_ids != {expected_agent_hash}:
                return False
        for field, expected in (
            ("semanticJudgedCount", semantic_judged),
            ("semanticPassedCount", semantic_passed),
        ):
            value = summary.get(field, 0)
            if not isinstance(value, int) or isinstance(value, bool) or value != expected:
                return False

    required_semantic_judge = kind == "background_execution" or any(
        entry["semanticJudgeRequired"] for entry in entries
    )
    if required_semantic_judge and row.get("semanticJudgeRequired") is not True:
        return False
    if row.get("semanticJudgeRequired") is True and any(
        not isinstance(summary.get(field), int)
        or isinstance(summary.get(field), bool)
        or summary.get(field) != selected_count
        for field in ("semanticJudgedCount", "semanticPassedCount")
    ):
        return False
    try:
        created = datetime.fromisoformat(str(row.get("createdAt") or "").replace("Z", "+00:00"))
        run_created = datetime.strptime(run_id[:16], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return False
    if created.tzinfo is None or abs((created.astimezone(timezone.utc) - run_created).total_seconds()) > 300:
        return False
    age = (datetime.now(timezone.utc) - created.astimezone(timezone.utc)).total_seconds()
    return -300 <= age <= MAX_EVAL_EVIDENCE_AGE_SECONDS


def inspect_installed_workbench(origin: str, *, fetch: FetchJson | None = None) -> dict[str, Any]:
    origin = strict_loopback_origin(origin)
    transport = fetch or _local_fetch(origin)
    blocking: list[str] = []
    counts: dict[str, int] = {}

    def fail(reason: str) -> None:
        if reason not in blocking:
            blocking.append(reason)

    def read(path: str, reason: str, *, timeout: float = 8.0) -> dict[str, Any] | None:
        try:
            payload = transport(path, timeout)
        except (OSError, TimeoutError, ValueError, UnicodeError, json.JSONDecodeError):
            fail(reason)
            return None
        if not isinstance(payload, dict):
            fail(reason)
            return None
        return payload

    def result() -> dict[str, Any]:
        return {
            "schemaVersion": 1,
            "status": "blocked" if blocking else "pass",
            "blockingChecks": sorted(blocking),
            "counts": counts,
        }

    authentication = read("/api/auth/status", "loopback_administrator_unavailable")
    if (
        not authentication
        or authentication.get("authenticated") is not True
        or authentication.get("admin") is not True
        or authentication.get("method") != "local_loopback_admin"
    ):
        fail("loopback_administrator_unavailable")
        return result()

    build = read("/api/build-version", "installed_build_unavailable")
    installed_source_hash = ""
    if build:
        backend = build.get("backend")
        if build.get("available") is not True or not build.get("entryAssets"):
            fail("installed_frontend_build_unavailable")
        if not _frontend_receipt_is_current(build.get("frontend")):
            fail("installed_frontend_build_receipt_invalid")
        if not isinstance(backend, dict) or backend.get("sourceCurrent") is not True:
            fail("installed_backend_source_stale")
        elif (
            not isinstance(backend.get("loadedSourceHash"), str)
            or not re.fullmatch(r"[0-9a-f]{16}", backend["loadedSourceHash"])
            or backend.get("loadedSourceHash") != backend.get("currentSourceHash")
        ):
            fail("installed_backend_source_stale")
        else:
            installed_source_hash = backend["loadedSourceHash"]
    if "installed_backend_source_stale" in blocking or "installed_build_unavailable" in blocking:
        # Older servers ignore unknown query parameters, so a stale server cannot certify that
        # schedule listing will honor its non-mutating projection. Never probe it further.
        return result()

    frames_payload = read("/api/frames", "frames_health_unavailable")
    if frames_payload is not None:
        frames_blocker = _frames_health_blocker(frames_payload)
        if frames_blocker:
            fail(frames_blocker)
        else:
            counts["frameCount"] = len(frames_payload["frames"])

    registry = read("/api/prompts", "prompt_registry_unavailable")
    available_prompts: set[str] = set()
    prompt_catalog: dict[str, dict[str, Any]] = {}
    if registry:
        prompts = registry.get("prompts")
        if not isinstance(prompts, list):
            fail("prompt_registry_invalid")
        else:
            for prompt in prompts:
                if not isinstance(prompt, dict):
                    fail("prompt_registry_invalid")
                    continue
                prompt_id = prompt.get("id")
                if not isinstance(prompt_id, str) or not prompt_id or prompt_id in prompt_catalog:
                    fail("prompt_registry_invalid")
                    continue
                prompt_catalog[prompt_id] = prompt
            available_prompts = set(prompt_catalog)
            counts["promptCount"] = len(available_prompts)
            if not set(REQUIRED_PROMPTS).issubset(available_prompts):
                fail("required_prompt_registry_entries_missing")
        flow = registry.get("flow")
        if not isinstance(flow, dict) or not isinstance(flow.get("nodes"), list) or not flow["nodes"]:
            fail("prompt_registry_graph_unavailable")

    for prompt_id in REQUIRED_PROMPTS:
        if prompt_id not in available_prompts:
            continue
        context = read(
            f"/api/prompts/{urllib.parse.quote(prompt_id, safe='.')}/workbench-context",
            "prompt_lineage_unavailable",
        )
        if not context:
            continue
        delivery = context.get("delivery")
        if not isinstance(delivery, dict) or delivery.get("state") != "synced":
            fail("prompt_source_compiled_live_lineage_mismatch")
            continue
        if delivery.get("kind") == "managed_agent":
            sync = context.get("sync")
            if (
                not isinstance(sync, dict)
                or sync.get("state") != "synced"
                or not sync.get("sourceHash")
                or sync.get("sourceHash") != sync.get("liveHash")
            ):
                fail("managed_prompt_live_lineage_mismatch")
        elif delivery.get("kind") == "compiled_runtime":
            bundle = context.get("runtimePromptBundle")
            if (
                not isinstance(bundle, dict)
                or bundle.get("status") != "ok"
                or bundle.get("promptState") != "synced"
                or bundle.get("liveBundleAvailable") is not True
            ):
                fail("compiled_prompt_live_lineage_mismatch")
        else:
            fail("prompt_delivery_owner_unavailable")

    draft_payload = read("/api/drafts", "draft_history_unavailable")
    if draft_payload:
        drafts = draft_payload.get("drafts")
        if not isinstance(drafts, list):
            fail("draft_history_invalid")
        else:
            counts["draftCount"] = len(drafts)
            counts["activeDraftCount"] = sum(
                1 for draft in drafts if isinstance(draft, dict) and draft.get("status") == "draft"
            )
            if counts["activeDraftCount"]:
                fail("pending_source_or_eval_drafts")

    eval_bank = read("/api/evals", "eval_registry_unavailable")
    required_case_ids: frozenset[str] = frozenset()
    case_catalog: dict[str, dict[str, Any]] = {}
    if eval_bank:
        case_count = eval_bank.get("caseCount")
        if not isinstance(case_count, int) or isinstance(case_count, bool) or case_count < 1:
            fail("eval_registry_empty")
        else:
            counts["evalCaseCount"] = case_count
            families = eval_bank.get("families")
            case_ids: list[str] = []
            valid_catalog = isinstance(families, list) and bool(families)
            if valid_catalog:
                for family in families:
                    if not isinstance(family, dict) or not isinstance(family.get("cases"), list):
                        valid_catalog = False
                        break
                    family_id = family.get("id")
                    if not isinstance(family_id, str) or not family_id:
                        valid_catalog = False
                        break
                    runner = str(family.get("runner") or "")
                    if runner not in {"", "background_execution", "background_activation"}:
                        valid_catalog = False
                        break
                    family_prompt_refs = family.get("promptRefs") or family.get("prompt_refs") or []
                    if not isinstance(family_prompt_refs, list) or any(
                        not isinstance(prompt_id, str) or not prompt_id
                        for prompt_id in family_prompt_refs
                    ):
                        valid_catalog = False
                        break
                    activation_target_keys: frozenset[str] = frozenset()
                    if runner == "background_activation":
                        targets = family.get("activationTargets") or family.get("activation_targets") or []
                        if not isinstance(targets, list) or not targets:
                            valid_catalog = False
                            break
                        declared_keys = [
                            target.get("key")
                            for target in targets
                            if isinstance(target, dict)
                        ]
                        if (
                            len(declared_keys) != len(targets)
                            or any(not isinstance(key, str) or not key for key in declared_keys)
                            or len(set(declared_keys)) != len(declared_keys)
                        ):
                            valid_catalog = False
                            break
                        activation_target_keys = frozenset(declared_keys)
                    for case in family["cases"]:
                        case_id = case.get("id") if isinstance(case, dict) else None
                        if not isinstance(case_id, str) or not case_id:
                            valid_catalog = False
                            break
                        case_prompt_refs = case.get("promptRefs") or case.get("prompt_refs") or []
                        if not isinstance(case_prompt_refs, list) or any(
                            not isinstance(prompt_id, str) or not prompt_id
                            for prompt_id in case_prompt_refs
                        ):
                            valid_catalog = False
                            break
                        required_activations: frozenset[str] = frozenset()
                        allowed_activations: frozenset[str] = frozenset()
                        if runner == "background_activation":
                            required = case.get("required_activations")
                            allowed = case.get("allowed_activations")
                            if (
                                not isinstance(required, list)
                                or not isinstance(allowed, list)
                                or any(not isinstance(key, str) or not key for key in required + allowed)
                                or len(set(required)) != len(required)
                                or len(set(allowed)) != len(allowed)
                                or not set(required).issubset(allowed)
                                or not set(allowed).issubset(activation_target_keys)
                            ):
                                valid_catalog = False
                                break
                            required_activations = frozenset(required)
                            allowed_activations = frozenset(allowed)
                        case_ids.append(case_id)
                        case_catalog[case_id] = {
                            "familyId": family_id,
                            "runner": runner,
                            "semanticJudgeRequired": (
                                family.get("semanticJudge") is True
                                or case.get("semanticJudge") is True
                            ),
                            "executionTarget": family.get("executionTarget"),
                            "promptRefs": frozenset(family_prompt_refs + case_prompt_refs),
                            "activationTargetKeys": activation_target_keys,
                            "requiredActivations": required_activations,
                            "allowedActivations": allowed_activations,
                        }
                    if not valid_catalog:
                        break
            if not valid_catalog or len(case_ids) != case_count or len(set(case_ids)) != case_count:
                fail("eval_registry_invalid")
            else:
                required_case_ids = frozenset(case_ids)
    configured_route = read("/api/evals/execution-route", "configured_execution_route_unavailable")
    family_routes: dict[str, dict[str, Any] | None] = {}

    def configured_family_route(family_id: str) -> dict[str, Any] | None:
        if family_id not in family_routes:
            family_routes[family_id] = read(
                f"/api/evals/execution-route?family={urllib.parse.quote(family_id, safe='')}",
                "configured_execution_route_unavailable",
            )
        return family_routes[family_id]

    run_payload = read("/api/evals/runs", "eval_history_unavailable")
    if run_payload:
        rows = run_payload.get("runs")
        verified = [
            row
            for row in rows or []
            if isinstance(row, dict)
            and _current_verified_run(
                row,
                configured_route,
                required_case_ids,
                case_catalog,
                configured_family_route,
                installed_source_hash=installed_source_hash,
                prompt_catalog=prompt_catalog,
            )
        ]
        verified_case_ids = {
            case_id
            for row in verified
            for case_id in row["selectedCaseIds"]
        }
        counts["verifiedLiveEvalCount"] = len(verified)
        counts["verifiedEvalCaseCount"] = len(verified_case_ids)
        if not verified:
            fail("exact_model_route_not_verified")
        elif verified_case_ids != required_case_ids:
            fail("required_eval_coverage_incomplete")

    schedule_payload = read("/api/scheduled-prompts?readOnly=true", "schedule_registry_unavailable")
    if schedule_payload:
        schedules = schedule_payload.get("scheduledPrompts")
        if not isinstance(schedules, list):
            fail("schedule_registry_invalid")
        else:
            counts["scheduleCount"] = len(schedules)
            for label, field, expected in (
                ("continuity", "sourcePromptId", "scheduler.consciousness_continuity_opportunity"),
                ("nightly", "templateId", NIGHTLY_TEMPLATE_ID),
            ):
                matches = [
                    row
                    for row in schedules
                    if isinstance(row, dict) and row.get(field) == expected and row.get("active") is True
                ]
                if len(matches) != 1:
                    fail(f"{label}_active_schedule_invalid")
                    continue
                row = matches[0]
                latest = row.get("latestScheduledRun")
                if not isinstance(latest, dict) or latest.get("status") not in {"completed", "success"}:
                    fail(f"{label}_latest_scheduled_run_failed")
                elif latest.get("triggerKind") != "scheduled":
                    fail(f"{label}_scheduled_provenance_invalid")
                schedule_id = str(row.get("id") or "")
                if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", schedule_id):
                    fail(f"{label}_run_history_unavailable")
                    continue
                history = read(
                    f"/api/scheduled-prompts/{urllib.parse.quote(schedule_id, safe='')}/runs?readOnly=true",
                    f"{label}_run_history_unavailable",
                )
                if history is not None and (
                    not isinstance(history.get("runs"), list)
                    or not history["runs"]
                    or not any(
                        isinstance(run, dict)
                        and run.get("status") in {"completed", "success"}
                        and run.get("triggerKind") == "scheduled"
                        for run in history["runs"]
                    )
                ):
                    fail(f"{label}_run_history_unavailable")

    cognitive = read("/api/cognitive-integrity", "cognitive_integrity_unavailable", timeout=14.0)
    if cognitive:
        blocked_checks = cognitive.get("blockingChecks")
        counts["cognitiveBlockingCheckCount"] = len(blocked_checks) if isinstance(blocked_checks, list) else 0
        checks = cognitive.get("checks")
        if (
            cognitive.get("status") != "ok"
            or not isinstance(cognitive.get("schemaVersion"), int)
            or cognitive["schemaVersion"] < 3
            or not isinstance(blocked_checks, list)
            or counts["cognitiveBlockingCheckCount"]
            or not isinstance(checks, dict)
            or not REQUIRED_COGNITIVE_CHECKS.issubset(checks)
            or any(
                not isinstance(value, dict) or value.get("status") != "ok"
                for value in checks.values()
            )
        ):
            fail("cognitive_integrity_blocked")
    return result()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only installed Prompt Workbench proof")
    parser.add_argument("--origin", default="http://127.0.0.1:8781")
    parser.add_argument("--allow-local-qa", action="store_true")
    args = parser.parse_args(argv)
    if not args.allow_local_qa:
        parser.error("--allow-local-qa is required before any local request")
    try:
        report = inspect_installed_workbench(args.origin)
    except ValueError:
        report = {"schemaVersion": 1, "status": "blocked", "blockingChecks": ["invalid_loopback_origin"], "counts": {}}
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

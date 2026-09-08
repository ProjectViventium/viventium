from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .paths import (
    ACTIVATION_MODEL_EVAL_SCRIPT,
    EXACT_MODEL_EVAL_SCRIPT,
    NATIVE_SURFACE_EVAL_SCRIPT,
    PROMPT_BANK_PATH,
    REPO_ROOT,
    workbench_private_root,
)
from .prompt_service import load_eval_bank
from .promptfoo_adapter import prompt_bank_to_promptfoo
from .redaction import redact_credential_assignments
from . import drafts


RUNTIME_CONTEXT_CONTRACTS: dict[str, dict[str, str]] = {
    "runtime.feelings.current_state": {
        "id": "runtime.feelings.current_state",
        "kind": "runtime_context",
        "tag": "viventium_feeling_state",
        "lifecycle": "request_scoped",
        "owner": "feelings_runtime",
        "valuePolicy": "private_value_not_recorded",
        "roleContract": "eligible conscious/speaking synthesis context; not specialist-worker demeanor",
    }
}

NATIVE_SURFACE_COMPLETION_SURFACES = {
    "telegram": "telegram",
    "voice": "voice",
    "wing": "voice",
    "listen_only": "voice",
    "scheduler": "workbench",
}
NATIVE_SURFACES = frozenset(NATIVE_SURFACE_COMPLETION_SURFACES)

RUNNER_SUMMARY_COUNT_FIELDS = {
    "selectedCaseCount",
    "selectedTargetCount",
    "repetitions",
    "resultCount",
    "completedCount",
    "passCount",
    "failureCount",
    "failedCount",
    "failedCaseRunCount",
    "falsePositiveCount",
    "falseNegativeCount",
    "unavailableCount",
    "unavailableRequiredCount",
    "timeoutOrProviderErrorCount",
    "inconsistentDecisionCount",
    "semanticInconsistentDecisionCount",
    "semanticJudgedCount",
    "semanticPassedCount",
    "semanticFailedCount",
    "semanticJudgeUnavailableCount",
    "duplicateResponseQualityFailureCount",
    "unresolvedAsyncQualityFailureCount",
}
RUNNER_SUMMARY_QUALITY_LIST_COUNTS = {
    "duplicateResponseQualityFailures": "duplicateResponseQualityFailureCount",
    "unresolvedAsyncQualityFailures": "unresolvedAsyncQualityFailureCount",
}

PUBLIC_RUN_FIELDS = frozenset(
    {
        "id",
        "mode",
        "returnCode",
        "resultCount",
        "selectedCaseCount",
        "cases",
        "createdAt",
        "live",
        "maxCases",
        "family",
        "surface",
        "promptId",
        "promptHash",
        "selectedCaseIds",
        "lineageManifest",
        "executionTarget",
        "executionRoute",
        "semanticJudgeRequired",
        "runnerSummary",
        "timeoutSeconds",
        "command",
        "stdoutTail",
        "stderrTail",
        "candidateSourceHash",
    }
)
PUBLIC_ROUTE_FIELDS = frozenset(
    {
        "status",
        "reason",
        "requestedProvider",
        "requestedModel",
        "requestedEffort",
        "effectiveProvider",
        "effectiveModel",
        "effectiveEffort",
        "fallbackUsed",
        "fallbackAuthorized",
        "fallbackReason",
        "configuredProvider",
        "configuredModel",
        "configuredProviderHash",
        "configuredModelHash",
        "observedProviderHash",
        "observedModelHash",
        "completedCaseCount",
        "artifactSha256",
        "routes",
        "caseEvidence",
        "routeExecution",
    }
)
PUBLIC_ROUTE_VARIANT_FIELDS = frozenset(
    {
        "targetKey",
        "requestedProvider",
        "requestedModel",
        "requestedEffort",
        "configuredProvider",
        "configuredModel",
        "effectiveProvider",
        "effectiveModel",
        "effectiveEffort",
        "fallbackUsed",
        "fallbackAuthorized",
        "fallbackReason",
    }
)
PUBLIC_CASE_EVIDENCE_FIELDS = frozenset(
    {
        "caseId",
        "agentIdHash",
        "requestIdentityHash",
        "surface",
        "completionSurface",
        "completionExpected",
        "semanticJudged",
        "semanticPassed",
        "targetKey",
        "repetition",
        "required",
        "allowed",
        "actual",
        "passed",
        "requestedProvider",
        "requestedModel",
        "requestedEffort",
        "effectiveProvider",
        "effectiveModel",
        "effectiveEffort",
        "fallbackReason",
        "primaryFailureVerified",
    }
)

TYPED_FALLBACK_REASONS = frozenset(
    {
        "provider_access_denied",
        "provider_auth_missing",
        "provider_connected_account_reconnect_required",
        "provider_error",
        "provider_invalid_response",
        "provider_network",
        "provider_quota_exhausted",
        "provider_quota_or_billing",
        "provider_rate_limited",
        "provider_response_deadline_exceeded",
        "provider_response_failed",
        "provider_server_error",
        "provider_temporarily_unavailable",
        "provider_timeout",
        "provider_unauthorized",
    }
)


def _live_eval_timeout_seconds(max_cases: int, runner: Path) -> int:
    if runner == ACTIVATION_MODEL_EVAL_SCRIPT:
        return 600
    # One exact-model case can consume two 120 s main-model attempts plus a 120 s semantic
    # judge. Preserve that per-case cleanup margin across a selected suite; the previous
    # one-hour cap killed healthy 30-case runs before they could write their evidence.
    return max(420, min(14_400, max(1, max_cases) * 420))


def _activation_eval_timeout_ms() -> int:
    raw = (os.getenv("VIVENTIUM_CORTEX_LATE_DETECT_TIMEOUT_MS") or "6000").strip()
    try:
        value = int(raw)
    except ValueError:
        value = 6000
    return max(1000, min(60_000, value))


def eval_bank_summary() -> dict[str, Any]:
    bank = load_eval_bank()
    families = bank.get("families") or []
    case_count = sum(len(family.get("cases") or []) for family in families)
    return {
        "version": bank.get("version"),
        "scope": bank.get("scope"),
        "familyCount": len(families),
        "caseCount": case_count,
        "families": [_public_family(family) for family in families],
    }


def evals_for_prompt(prompt_id: str) -> dict[str, Any]:
    families = []
    case_count = 0
    for family in eval_bank_summary().get("families") or []:
        if prompt_id not in set(family.get("promptRefs") or []):
            continue
        cases = family.get("cases") or []
        case_count += len(cases)
        families.append(family)
    return {"promptId": prompt_id, "familyCount": len(families), "caseCount": case_count, "families": families}


def run_exact_model_eval(
    *,
    max_cases: int = 1,
    live: bool = False,
    family: str | None = None,
    surface: str | None = None,
    prompt_id: str | None = None,
    case_ids: list[str] | None = None,
) -> dict[str, Any]:
    drafts.assert_no_active_blocking_drafts(
        "Eval preview",
        prompt_id=prompt_id,
        include_eval_drafts=True,
        all_prompt_drafts=live or prompt_id in {None, "main.conscious_agent"},
    )
    requested_case_ids = _normalize_case_ids(case_ids)
    effective_max_cases = len(requested_case_ids) if requested_case_ids else max_cases
    bank = load_eval_bank()
    selected = _selected_eval_cases(
        bank,
        family=family,
        surface=surface,
        prompt_id=prompt_id,
        case_ids=requested_case_ids,
        max_cases=effective_max_cases,
    )
    selected_case_ids = [str(row["case"].get("id") or "") for row in selected]
    missing_case_ids = [case_id for case_id in requested_case_ids if case_id not in selected_case_ids]
    if missing_case_ids:
        raise ValueError(
            "Explicit eval case IDs do not match the current family, surface, or prompt filters: "
            + ", ".join(missing_case_ids)
        )
    selected_surfaces = {
        str(row["case"].get("surface") or "web").strip() or "web" for row in selected
    }
    effective_surface = surface
    if live and len(selected_surfaces) == 1 and not effective_surface:
        selected_surface = next(iter(selected_surfaces))
        if selected_surface in NATIVE_SURFACES:
            effective_surface = selected_surface
    semantic_judge_required = any(
        row["family"].get("semanticJudge") is True
        or row["case"].get("semanticJudge") is True
        for row in selected
    )
    execution_target = _background_execution_target(
        bank, family, selected=selected
    )
    semantic_judge_required = semantic_judge_required or execution_target is not None
    lineage_manifest = _eval_lineage_manifest(
        selected, execution_target=execution_target
    )
    run_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:12]}"
    output_dir = workbench_private_root() / "eval-runs" / run_id
    output_dir.mkdir(parents=True, exist_ok=False)
    prompt_hash = _prompt_hash(prompt_id)
    if not live:
        cases = [
            {
                "family": row["family"].get("id"),
                "case": row["case"].get("id"),
                "surface": row["case"].get("surface"),
            }
            for row in selected
        ]
        record = {
            "id": run_id,
            "mode": "synthetic-no-live-preview",
            "returnCode": 0,
            "resultCount": len(cases),
            "selectedCaseCount": len(cases),
            "cases": cases,
            "stdoutTail": "Synthetic no-live eval preview loaded the prompt bank and selected cases without live model execution.",
            "stderrTail": "",
            "outputDir": str(output_dir),
            "createdAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "live": False,
            "maxCases": effective_max_cases,
            "family": family,
            "surface": surface,
            "promptId": prompt_id,
            "promptHash": prompt_hash,
            "selectedCaseIds": [case["case"] for case in cases],
            "lineageManifest": lineage_manifest,
            "executionTarget": execution_target,
            "semanticJudgeRequired": semantic_judge_required,
        }
        (output_dir / "workbench-run.json").write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return _public_run_record(record)
    runner = _eval_runner(
        bank=bank,
        family=family,
        prompt_id=prompt_id,
        selected=selected,
    )
    cmd = [
        "node",
        str(runner),
        f"--prompt-bank={PROMPT_BANK_PATH}",
        f"--output-dir={output_dir}",
        f"--public-report={output_dir / 'public-safe-report.md'}",
        f"--max-cases={effective_max_cases}",
        "--run-live" if live else "--no-live",
    ]
    if family:
        cmd.append(f"--family={family}")
    if requested_case_ids:
        cmd.append(f"--case-ids={','.join(requested_case_ids)}")
    if effective_surface:
        cmd.append(f"--surface={effective_surface}")
    if prompt_id and _runner_accepts_prompt_filter(
        runner=runner,
        bank=bank,
        family=family,
        prompt_id=prompt_id,
    ):
        cmd.append(f"--prompt-id={prompt_id}")
    if execution_target and execution_target.get("agentId"):
        cmd.append(f"--agent-id={execution_target['agentId']}")
    if execution_target or semantic_judge_required:
        # Direct specialist cases use qualitative evidence/uncertainty rubrics. A transport-only
        # completion would not evaluate the behavior the selected eval contract claims to measure.
        cmd.append("--semantic-judge")
    child_env: dict[str, str] | None = None
    if runner in {EXACT_MODEL_EVAL_SCRIPT, NATIVE_SURFACE_EVAL_SCRIPT}:
        # A live run is an explicit action from the authenticated, loopback-only Workbench.
        # Let the selected canonical harness mint short-lived local QA authority without storing
        # or forwarding a password. Both harnesses reject this path in CI and production.
        if runner == EXACT_MODEL_EVAL_SCRIPT:
            cmd.append("--local-jwt-fallback")
        child_env = os.environ.copy()
        child_env["VIVENTIUM_QA_ALLOW_LOCAL_JWT"] = "1"
    elif runner == ACTIVATION_MODEL_EVAL_SCRIPT:
        # Activation evals must exercise the same identity-aware classifier and fallback chain as
        # the runtime. The runner resolves the configurable QA selector from its inherited env and
        # refuses owner/admin selection; missing QA config is a visible failed run.
        cmd.extend(
            [
                "--qa-user-context",
                "--with-fallbacks",
                f"--timeout-ms={_activation_eval_timeout_ms()}",
            ]
        )
        child_env = os.environ.copy()
    timeout_seconds = _live_eval_timeout_seconds(effective_max_cases, runner)
    try:
        result = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
            env=child_env,
        )
        return_code = result.returncode
        stdout = result.stdout
        stderr = result.stderr
    except subprocess.TimeoutExpired as error:
        return_code = 124
        stdout = error.stdout or ""
        stderr = f"Exact-model eval timed out after {timeout_seconds} seconds."
    if isinstance(stdout, bytes):
        stdout = stdout.decode("utf-8", errors="replace")
    if isinstance(stderr, bytes):
        stderr = stderr.decode("utf-8", errors="replace")
    runner_summary = _public_runner_summary(stdout)
    if runner in {
        EXACT_MODEL_EVAL_SCRIPT,
        NATIVE_SURFACE_EVAL_SCRIPT,
        ACTIVATION_MODEL_EVAL_SCRIPT,
    }:
        try:
            artifact_name = {
                EXACT_MODEL_EVAL_SCRIPT: "exact-model-eval.json",
                NATIVE_SURFACE_EVAL_SCRIPT: "native-surface-playwright-qa.json",
                ACTIVATION_MODEL_EVAL_SCRIPT: "activation-model-eval.json",
            }[runner]
            artifact = json.loads((output_dir / artifact_name).read_text(encoding="utf-8"))
            canonical_summary = artifact.get("summary") if isinstance(artifact, dict) else None
            if isinstance(canonical_summary, dict):
                runner_summary = _public_runner_summary(json.dumps(canonical_summary))
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError):
            pass
    if runner == EXACT_MODEL_EVAL_SCRIPT and (execution_target or {}).get("mode") == "worker_source_replay":
        execution_route = _worker_source_execution_route(output_dir, selected=selected)
    elif runner == EXACT_MODEL_EVAL_SCRIPT:
        execution_route = _exact_model_execution_route(
            output_dir,
            execution_target=execution_target,
            selected_case_ids=selected_case_ids,
            semantic_judge_required=semantic_judge_required,
        )
    elif runner == NATIVE_SURFACE_EVAL_SCRIPT:
        execution_route = _native_surface_execution_route(
            output_dir,
            execution_target=execution_target,
            selected_case_ids=selected_case_ids,
            requested_surface=effective_surface,
            semantic_judge_required=semantic_judge_required,
        )
    elif runner == ACTIVATION_MODEL_EVAL_SCRIPT:
        selected_family = family or str((selected[0]["family"] if selected else {}).get("id") or "")
        execution_route = _activation_model_execution_route(
            output_dir,
            bank=bank,
            family_id=selected_family,
            selected_case_ids=selected_case_ids,
        )
    else:
        execution_route = None
    if execution_route and execution_route.get("status") != "verified" and return_code == 0:
        return_code = 1
        runner_summary = {
            **(runner_summary or {}),
            "status": "blocked",
            "blockedReason": str(execution_route.get("reason") or "configured_execution_route_mismatch"),
        }
    actual_result_count = (
        runner_summary.get("resultCount")
        if runner_summary and isinstance(runner_summary.get("resultCount"), int)
        else len(selected)
    )
    record = {
        "id": run_id,
        "command": _safe_command(cmd, private_paths=(output_dir,)),
        "returnCode": return_code,
        "stdoutTail": _sanitize_output(stdout[-4000:], private_paths=(output_dir,)),
        "stderrTail": _sanitize_output(stderr[-4000:], private_paths=(output_dir,)),
        "timeoutSeconds": timeout_seconds,
        "outputDir": str(output_dir),
        "createdAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "live": live,
        "maxCases": effective_max_cases,
        "family": family,
        "surface": effective_surface,
        "promptId": prompt_id,
        "promptHash": prompt_hash,
        "selectedCaseIds": [str(row["case"].get("id") or "") for row in selected],
        "selectedCaseCount": len(selected),
        "resultCount": actual_result_count,
        "runnerSummary": runner_summary,
        "lineageManifest": lineage_manifest,
        "executionTarget": execution_target,
        "executionRoute": execution_route,
        "semanticJudgeRequired": semantic_judge_required,
        "candidateSourceHash": _workbench_candidate_source_hash(),
    }
    (output_dir / "workbench-run.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return _public_run_record(record)


def _selected_eval_cases(
    bank: dict[str, Any],
    *,
    family: str | None,
    surface: str | None,
    prompt_id: str | None,
    case_ids: list[str] | None,
    max_cases: int,
) -> list[dict[str, dict[str, Any]]]:
    selected: list[dict[str, dict[str, Any]]] = []
    explicit_case_ids = set(case_ids or [])
    for family_row in bank.get("families") or []:
        if not isinstance(family_row, dict):
            continue
        if family and family_row.get("id") != family:
            continue
        family_prompt_refs = _prompt_refs(family_row)
        for case in family_row.get("cases") or []:
            if not isinstance(case, dict):
                continue
            if explicit_case_ids and str(case.get("id") or "") not in explicit_case_ids:
                continue
            if surface and case.get("surface") != surface:
                continue
            # An explicitly selected family is the execution target. Otherwise the selected prompt
            # filters the bank to families/cases that actually declare it as a dependency.
            if (
                prompt_id
                and not family
                and prompt_id not in family_prompt_refs
                and prompt_id not in _prompt_refs(case)
            ):
                continue
            selected.append({"family": family_row, "case": case})
            if len(selected) >= max(1, max_cases):
                return selected
    return selected


def _normalize_case_ids(case_ids: list[str] | None) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_case_id in case_ids or []:
        case_id = str(raw_case_id).strip()
        if not case_id or case_id in seen:
            continue
        if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}", case_id):
            raise ValueError("Eval case IDs may contain only letters, numbers, dot, colon, underscore, or hyphen")
        seen.add(case_id)
        normalized.append(case_id)
    if len(normalized) > 100:
        raise ValueError("At most 100 explicit eval case IDs may be selected")
    return normalized


def _eval_lineage_manifest(
    selected: list[dict[str, dict[str, Any]]],
    *,
    execution_target: dict[str, str] | None = None,
) -> dict[str, Any]:
    from . import prompt_service
    from scripts.viventium.prompt_registry import load_prompt_registry

    family_ids: set[str] = set()
    case_ids: list[str] = []
    root_prompt_ids: set[str] = set()
    runtime_context_ids: set[str] = set()
    for row in selected:
        family = row["family"]
        case = row["case"]
        family_ids.add(str(family.get("id") or ""))
        case_ids.append(str(case.get("id") or ""))
        root_prompt_ids.update(_prompt_refs(family))
        root_prompt_ids.update(_prompt_refs(case))
        runtime_context_ids.update(_runtime_context_refs(family))
        runtime_context_ids.update(_runtime_context_refs(case))
        fixture = case.get("fixture") or {}
        if isinstance(fixture, dict) and "feelings" in fixture:
            runtime_context_ids.add("runtime.feelings.current_state")
    if execution_target and str(execution_target.get("promptRef") or "").strip():
        root_prompt_ids.add(str(execution_target["promptRef"]).strip())

    registry = load_prompt_registry(prompt_service.PROMPTS_ROOT)
    prompt_dependencies: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, str]] = []

    def visit(prompt_id: str, *, direct: bool) -> None:
        existing = prompt_dependencies.get(prompt_id)
        if existing:
            if direct:
                existing["direct"] = True
            return
        entry = registry.get(prompt_id)
        if not entry:
            prompt_dependencies[prompt_id] = {
                "id": prompt_id,
                "kind": "prompt",
                "status": "missing",
                "direct": direct,
            }
            return
        try:
            rendered = prompt_service._render_prompt_preview(prompt_id, registry)
            rendered_hash = _sha(rendered)
        except Exception:
            rendered_hash = None
        delivery = prompt_service.prompt_delivery_contract(prompt_id, entry.metadata)
        prompt_dependencies[prompt_id] = {
            "id": prompt_id,
            "kind": "prompt",
            "status": "available",
            "direct": direct,
            "path": prompt_service.relative_to_repo(entry.path),
            "contentHash": entry.content_hash,
            "bodyHash": _sha(entry.body),
            "renderedHash": rendered_hash,
            "deliveryKind": delivery["kind"],
            "deliveryTarget": delivery["target"],
        }
        for include_id in entry.metadata.get("includes") or []:
            include = str(include_id)
            edges.append({"from": prompt_id, "to": include, "kind": "includes"})
            visit(include, direct=False)

    for prompt_id in sorted(root_prompt_ids):
        visit(prompt_id, direct=True)

    runtime_dependencies: list[dict[str, Any]] = []
    for context_id in sorted(runtime_context_ids):
        contract = RUNTIME_CONTEXT_CONTRACTS.get(context_id)
        if not contract:
            runtime_dependencies.append(
                {
                    "id": context_id,
                    "kind": "runtime_context",
                    "status": "unknown_contract",
                }
            )
            continue
        public_contract: dict[str, Any] = dict(contract)
        public_contract["contractHash"] = _sha(
            json.dumps(contract, sort_keys=True, separators=(",", ":"))
        )
        runtime_dependencies.append(public_contract)

    manifest: dict[str, Any] = {
        "schemaVersion": 1,
        "familyIds": sorted(item for item in family_ids if item),
        "caseIds": [item for item in case_ids if item],
        "rootPromptIds": sorted(root_prompt_ids),
        "promptDependencies": sorted(
            prompt_dependencies.values(), key=lambda row: str(row.get("id") or "")
        ),
        "runtimeContextDependencies": runtime_dependencies,
        "includeEdges": sorted(
            edges,
            key=lambda row: (row["from"], row["to"]),
        ),
    }
    if execution_target:
        manifest["executionTarget"] = execution_target
    manifest["promptCount"] = len(manifest["promptDependencies"])
    manifest["runtimeContextCount"] = len(runtime_dependencies)
    manifest["manifestHash"] = _sha(
        json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    )
    return manifest


def _background_execution_target(
    bank: dict[str, Any],
    family_id: str | None,
    *,
    selected: list[dict[str, dict[str, Any]]],
) -> dict[str, str] | None:
    worker_families = [row["family"] for row in selected if row["family"].get("runner") == "worker_source"]
    if worker_families:
        if len(worker_families) != len(selected) or len({row.get("id") for row in worker_families}) != 1:
            raise ValueError("Worker source replay requires one isolated family")
        worker_family = worker_families[0]
        target = worker_family.get("executionTarget") or {}
        prompt_ref = str(target.get("promptRef") or "")
        if not prompt_ref.startswith("worker.") or prompt_ref not in _prompt_refs(worker_family):
            raise ValueError("Worker source replay requires a declared worker promptRef")
        return {"mode": "worker_source_replay", "promptRef": prompt_ref}
    candidate_ids = (
        {family_id}
        if family_id
        else {
            str(row["family"].get("id") or "")
            for row in selected
            if row["family"].get("runner") == "background_execution"
        }
    )
    candidate_ids.discard("")
    if not candidate_ids:
        return None
    families = [
        row
        for row in bank.get("families") or []
        if isinstance(row, dict)
        and row.get("id") in candidate_ids
        and row.get("runner") == "background_execution"
    ]
    if len(families) > 1:
        raise ValueError(
            "Select one background execution family so Workbench can target one specialist agent"
        )
    family = next(
        (
            row for row in families
        ),
        None,
    )
    if not family:
        return None
    target = family.get("executionTarget") or family.get("execution_target")
    if not isinstance(target, dict):
        raise ValueError(
            "Background execution eval requires a structured executionTarget"
        )
    agent_id = str(target.get("agentId") or target.get("agent_id") or "").strip()
    prompt_ref = str(
        target.get("promptRef") or target.get("prompt_ref") or ""
    ).strip()
    if not agent_id or not prompt_ref or prompt_ref not in _prompt_refs(family):
        raise ValueError(
            "Background execution eval requires a structured executionTarget with an agentId and declared promptRef"
        )
    return {
        "mode": "direct_background_agent",
        "agentId": agent_id,
        "promptRef": prompt_ref,
    }


def _prompt_refs(row: dict[str, Any]) -> set[str]:
    return {
        str(item)
        for item in (row.get("promptRefs") or row.get("prompt_refs") or [])
        if str(item)
    }


def _runtime_context_refs(row: dict[str, Any]) -> set[str]:
    return {
        str(item)
        for item in (
            row.get("runtimeContextRefs")
            or row.get("runtime_context_refs")
            or []
        )
        if str(item)
    }


def _sha(value: str, length: int = 16) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def _route_effort(value: Any) -> str:
    effort = str(value or "").strip().lower()
    return effort if re.fullmatch(r"[a-z0-9][a-z0-9._:-]{0,31}", effort) else ""


def _configured_activation_effort(provider: str, model: str) -> str:
    """Mirror BackgroundCortexService.configuredActivationReasoningEffort exactly."""

    normalized_provider = str(provider or "").strip().lower()
    normalized_model = str(model or "").strip().lower()
    if normalized_provider == "groq" and normalized_model.startswith("openai/gpt-oss-"):
        return "low"
    if normalized_provider == "groq" and normalized_model.startswith("qwen/qwen3.6-"):
        return "none"
    return "provider_default"


def _agent_route(agent: dict[str, Any]) -> dict[str, Any] | None:
    provider = str(agent.get("provider") or agent.get("endpoint") or "").strip()
    parameters = agent.get("model_parameters")
    parameters = parameters if isinstance(parameters, dict) else {}
    model = str(agent.get("model") or parameters.get("model") or "").strip()
    effort = _route_effort(
        agent.get("reasoning_effort")
        or agent.get("effort")
        or parameters.get("reasoning_effort")
        or parameters.get("effort")
    )
    if not provider or not model or not effort:
        return None
    fallbacks: list[dict[str, str]] = []
    fallback_parameters = agent.get("fallback_llm_model_parameters")
    fallback_parameters = fallback_parameters if isinstance(fallback_parameters, dict) else {}
    fallback_provider = str(agent.get("fallback_llm_provider") or "").strip()
    fallback_model = str(
        agent.get("fallback_llm_model") or fallback_parameters.get("model") or ""
    ).strip()
    if fallback_provider or fallback_model or fallback_parameters:
        fallback_effort = _route_effort(
            agent.get("fallback_reasoning_effort")
            or fallback_parameters.get("reasoning_effort")
            or fallback_parameters.get("effort")
        )
        if not fallback_provider or not fallback_model or not fallback_effort:
            return None
        fallbacks.append(
            {
                "provider": fallback_provider,
                "model": fallback_model,
                "effort": fallback_effort,
            }
        )
    return {
        "provider": provider,
        "model": model,
        "effort": effort,
        "fallbacks": fallbacks,
    }


def _configured_execution_route(execution_target: dict[str, str] | None) -> dict[str, Any] | None:
    from . import prompt_service

    try:
        bundle = prompt_service.source_agents_bundle()
    except (OSError, ValueError, TypeError):
        return None
    if execution_target:
        target_id = str(execution_target.get("agentId") or "")
        agent = next(
            (
                row
                for row in bundle.get("backgroundAgents") or []
                if isinstance(row, dict) and str(row.get("id") or "") == target_id
            ),
            None,
        )
    else:
        agent = bundle.get("mainAgent")
    if not isinstance(agent, dict):
        return None
    return _agent_route(agent)


def _configured_execution_agent_hash(execution_target: dict[str, str] | None) -> str | None:
    from . import prompt_service

    try:
        bundle = prompt_service.source_agents_bundle()
    except (OSError, ValueError, TypeError):
        return None
    if execution_target:
        target_id = str(execution_target.get("agentId") or "")
        agent = next(
            (
                row
                for row in bundle.get("backgroundAgents") or []
                if isinstance(row, dict) and str(row.get("id") or "") == target_id
            ),
            None,
        )
    else:
        agent = bundle.get("mainAgent")
    agent_id = str((agent or {}).get("id") or "").strip() if isinstance(agent, dict) else ""
    return _sha(agent_id) if agent_id else None


def _configured_family_execution_route(family_id: str) -> dict[str, Any] | None:
    from . import prompt_service

    requested = str(family_id or "").strip()
    if not requested:
        return None
    try:
        bank = load_eval_bank()
        family = next(
            (
                row
                for row in bank.get("families") or []
                if isinstance(row, dict) and str(row.get("id") or "") == requested
            ),
            None,
        )
    except (OSError, UnicodeError, ValueError, TypeError):
        return None
    if not isinstance(family, dict):
        return None

    runner = str(family.get("runner") or "")
    if runner == "background_execution":
        target = family.get("executionTarget") or family.get("execution_target")
        agent_id = str((target or {}).get("agentId") or "").strip() if isinstance(target, dict) else ""
        prompt_ref = str((target or {}).get("promptRef") or "").strip() if isinstance(target, dict) else ""
        configured = _configured_execution_route(target) if agent_id and prompt_ref else None
        if configured is None:
            return None
        return {
            "kind": "background_execution",
            "family": requested,
            "agentId": agent_id,
            "promptRef": prompt_ref,
            **configured,
        }

    if runner != "background_activation":
        configured = _configured_execution_route(None)
        return {"kind": "main", "family": requested, **configured} if configured else None

    try:
        bundle = prompt_service.source_agents_bundle()
    except (OSError, UnicodeError, ValueError, TypeError):
        return None
    main = bundle.get("mainAgent") if isinstance(bundle, dict) else None
    cortex_rows = main.get("background_cortices") if isinstance(main, dict) else None
    cortices = {
        str(row.get("agent_id") or ""): row.get("activation")
        for row in cortex_rows or []
        if isinstance(row, dict) and isinstance(row.get("activation"), dict)
    }
    declared = family.get("activationTargets") or family.get("activation_targets")
    if not isinstance(declared, list) or not declared:
        return None
    targets: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for item in declared:
        if not isinstance(item, dict):
            return None
        target_key = str(item.get("key") or "").strip()
        agent_id = str(item.get("agentId") or item.get("agent_id") or "").strip()
        configured = cortices.get(agent_id)
        if not target_key or target_key in seen_keys or not isinstance(configured, dict):
            return None
        provider = str(configured.get("provider") or "").strip()
        model = str(configured.get("model") or "").strip()
        if not provider or not model:
            return None
        effort = _configured_activation_effort(provider, model)
        fallbacks: list[dict[str, str]] = []
        seen_routes = {(provider, model, effort)}
        for fallback in configured.get("fallbacks") or []:
            if not isinstance(fallback, dict):
                return None
            fallback_provider = str(fallback.get("provider") or "").strip()
            fallback_model = str(fallback.get("model") or "").strip()
            fallback_effort = _configured_activation_effort(
                fallback_provider, fallback_model
            )
            route = (fallback_provider, fallback_model, fallback_effort)
            if not fallback_provider or not fallback_model or route in seen_routes:
                return None
            seen_routes.add(route)
            fallbacks.append(
                {
                    "provider": fallback_provider,
                    "model": fallback_model,
                    "effort": fallback_effort,
                }
            )
        targets.append(
            {
                "targetKey": target_key,
                "provider": provider,
                "model": model,
                "effort": effort,
                "fallbacks": fallbacks,
            }
        )
        seen_keys.add(target_key)
    return {
        "kind": "background_activation",
        "family": requested,
        "targets": sorted(targets, key=lambda row: str(row["targetKey"])),
    }


def _route_triple(route: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(route.get("provider") or "").strip(),
        str(route.get("model") or "").strip(),
        _route_effort(route.get("effort")),
    )


def _configured_route_variants(configured: dict[str, Any]) -> list[dict[str, Any]]:
    return [configured, *(configured.get("fallbacks") or [])]


def _validate_observed_lineage(
    configured: dict[str, Any],
    *,
    requested_provider_hash: str,
    requested_model_hash: str,
    requested_effort: str,
    effective_provider_hash: str,
    effective_model_hash: str,
    effective_effort: str,
    fallback_used: Any,
    fallback_reason: str,
) -> tuple[dict[str, Any] | None, str | None]:
    primary_provider, primary_model, primary_effort = _route_triple(configured)
    if (
        requested_provider_hash != _sha(primary_provider)
        or requested_model_hash != _sha(primary_model)
        or requested_effort != primary_effort
    ):
        return None, "configured_execution_route_mismatch"
    variants = {
        (_sha(provider), _sha(model), effort): {
            "provider": provider,
            "model": model,
            "effort": effort,
        }
        for provider, model, effort in map(
            _route_triple, _configured_route_variants(configured)
        )
        if provider and model and effort
    }
    effective_key = (
        effective_provider_hash,
        effective_model_hash,
        effective_effort,
    )
    effective = variants.get(effective_key)
    if effective is None:
        return None, "configured_execution_route_mismatch"
    actual_fallback = effective_key != (
        _sha(primary_provider),
        _sha(primary_model),
        primary_effort,
    )
    normalized_reason = str(fallback_reason or "").strip().lower()
    if not isinstance(fallback_used, bool) or fallback_used is not actual_fallback:
        return None, "fallback_lineage_mismatch"
    if actual_fallback:
        if normalized_reason not in TYPED_FALLBACK_REASONS:
            return None, "fallback_reason_missing"
    elif normalized_reason != "none":
        return None, "fallback_reason_mismatch"
    return (
        {
            "requestedProvider": primary_provider,
            "requestedModel": primary_model,
            "requestedEffort": primary_effort,
            "effectiveProvider": effective["provider"],
            "effectiveModel": effective["model"],
            "effectiveEffort": effective["effort"],
            "fallbackUsed": actual_fallback,
            "fallbackAuthorized": actual_fallback,
            "fallbackReason": normalized_reason,
        },
        None,
    )


def _configured_worker_route(slot: str) -> dict[str, str]:
    if slot not in {"primary", "fallback"}:
        raise ValueError("invalid_worker_route_slot")
    profile = os.environ.get("GLASSHIVE_DEFAULT_WORKER_PROFILE" if slot == "primary" else "GLASSHIVE_DEFAULT_FALLBACK_WORKER_PROFILE", "")
    fields = {
        "codex-cli": ("WPR_MODEL_CODEX_CLI", "WPR_CODEX_CLI_REASONING_EFFORT"),
        "claude-code": ("WPR_MODEL_CLAUDE_CODE", "WPR_CLAUDE_CODE_EFFORT"),
    }.get(profile)
    if not fields or not all(os.environ.get(field) for field in fields):
        raise ValueError("configured_native_worker_route_unavailable")
    return {"slot": slot, "profile": profile, "provider": "glasshive-harness",
            "model": profile + ":" + os.environ[fields[0]], "nativeModel": os.environ[fields[0]],
            "effort": os.environ[fields[1]], "access": "full"}


def _worker_source_execution_route(output_dir: Path, *, selected: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate source replay separately; never fabricate a Main runtime frame."""
    def invalid(reason: str) -> dict[str, Any]:
        return {"status": "unverified", "reason": reason, "mode": "worker_source_replay"}
    try:
        payload = json.loads((output_dir / "exact-model-eval.json").read_text())
    except (OSError, ValueError):
        return invalid("execution_artifact_unavailable")
    rows = payload.get("liveResults") or []
    if payload.get("kind") != "worker_source_replay" or len(rows) != len(selected):
        return invalid("execution_case_coverage_unverified")
    source_hash = str(payload.get("sourceSnapshotSha256") or "")
    if not re.fullmatch(r"[0-9a-f]{64}", source_hash) or not payload.get("sourceFiles"):
        return invalid("worker_source_lineage_missing")
    evidence = []
    for expected, row in zip(selected, rows):
        case = expected["case"]
        if row.get("caseId") != case.get("id") or row.get("status") != "completed":
            return invalid("execution_case_coverage_unverified")
        try:
            route = _configured_worker_route((case.get("fixture") or {}).get("workerSource", {}).get("route", "primary"))
        except ValueError as error:
            return invalid(str(error))
        observed = row.get("observedRoute") or {}
        if row.get("requestedRoute") != route or any(observed.get(key) != value for key, value in route.items()):
            return invalid("native_worker_route_mismatch")
        identity = str(row.get("requestIdentityHash") or "")
        instructions = str(row.get("instructionsSha256") or "")
        if (not re.fullmatch(r"[0-9a-f]{64}", identity) or row.get("observedRequestIdentityHash") != identity
            or not re.fullmatch(r"[0-9a-f]{64}", instructions) or observed.get("instructionsSha256") != instructions
            or observed.get("nativeTools") is not True or observed.get("state") != "completed"):
            return invalid("native_worker_source_evidence_mismatch")
        audit = row.get("nativeAudit") or {}
        if not audit.get("stdoutHash") or not isinstance(row.get("nativeCalls"), list):
            return invalid("native_worker_tool_audit_missing")
        judge = row.get("semanticJudge") or {}
        if judge.get("status") != "judged" or judge.get("pass") is not True or not judge.get("rawHash") or not judge.get("attemptCount"):
            return invalid("semantic_judgment_unverified")
        evidence.append({"caseId": case["id"], "configuredRoute": route, "runIdHash": observed.get("runIdHash"), "instructionsSha256": instructions})
    return {"status": "verified", "mode": "worker_source_replay", "sourceSnapshotSha256": source_hash, "caseEvidence": evidence,
            "scope": "Native model source replay; actual mission/app/file acceptance remains separate"}


def _exact_model_execution_route(
    output_dir: Path,
    *,
    execution_target: dict[str, str] | None,
    selected_case_ids: list[str] | None = None,
    semantic_judge_required: bool = False,
) -> dict[str, Any]:
    configured = _configured_execution_route(execution_target)
    if not configured:
        return {"status": "unverified", "reason": "configured_execution_route_unavailable"}
    provider_hash = _sha(configured["provider"])
    model_hash = _sha(configured["model"])
    result: dict[str, Any] = {
        "requestedProvider": configured["provider"],
        "requestedModel": configured["model"],
        "requestedEffort": configured["effort"],
        "configuredProvider": configured["provider"],
        "configuredModel": configured["model"],
        "configuredProviderHash": provider_hash,
        "configuredModelHash": model_hash,
    }
    try:
        artifact_bytes = (output_dir / "exact-model-eval.json").read_bytes()
        payload = json.loads(artifact_bytes.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {"status": "unverified", **result, "reason": "execution_artifact_unavailable"}
    rows = payload.get("liveResults") if isinstance(payload, dict) else None
    completed = [row for row in rows or [] if isinstance(row, dict) and row.get("status") == "completed"]
    if not completed:
        safe_failure_reasons = {
            "execution_request_identity_unavailable",
            "execution_surface_mismatch",
            "execution_surface_unavailable",
            "multiple_execution_surfaces_observed",
        }
        observed_failure_reasons = {
            str(row.get("error") or "")
            for row in rows or []
            if isinstance(row, dict) and str(row.get("error") or "") in safe_failure_reasons
        }
        if len(observed_failure_reasons) == 1:
            return {
                "status": "unverified",
                **result,
                "reason": next(iter(observed_failure_reasons)),
            }
        return {"status": "unverified", **result, "reason": "completed_execution_unavailable"}

    observed: dict[tuple[str, str, str, bool, str], dict[str, Any]] = {}
    case_evidence: list[dict[str, Any]] = []
    expected_agent_hash = (
        _sha(str(execution_target.get("agentId") or ""))
        if isinstance(execution_target, dict)
        else ""
    )
    summary = payload.get("summary") if isinstance(payload, dict) else None
    arguments = payload.get("args") if isinstance(payload, dict) else None
    if selected_case_ids is not None:
        declared_agent_hash = str((arguments or {}).get("agentIdHash") or "")
        summarized_agent_hash = str((summary or {}).get("agentIdHash") or "")
        if (
            not re.fullmatch(r"[0-9a-f]{16}", declared_agent_hash)
            or declared_agent_hash != summarized_agent_hash
            or (expected_agent_hash and declared_agent_hash != expected_agent_hash)
        ):
            return {"status": "unverified", **result, "reason": "execution_agent_identity_mismatch"}
        expected_agent_hash = declared_agent_hash
        if len(completed) != len(selected_case_ids):
            return {"status": "unverified", **result, "reason": "execution_case_coverage_unverified"}
    for row in completed:
        request_identity_hash = str(row.get("requestIdentityHash") or "")
        observed_request_identity_hash = str(row.get("observedRequestIdentityHash") or "")
        if (
            not re.fullmatch(r"[0-9a-f]{16}", request_identity_hash)
            or observed_request_identity_hash != request_identity_hash
        ):
            return {"status": "unverified", **result, "reason": "execution_request_identity_mismatch"}
        evidence = row.get("promptFrameEvidenceForJudge")
        if isinstance(evidence, str):
            try:
                evidence = json.loads(evidence)
            except json.JSONDecodeError:
                evidence = None
        frames = evidence.get("prompt_frames") if isinstance(evidence, dict) else None
        relevant = [
            frame
            for frame in frames or []
            if isinstance(frame, dict)
            and frame.get("prompt_family") in {"main_run_create", "main_runtime"}
            and frame.get("request_identity_hash") == request_identity_hash
        ]
        if not relevant:
            return {"status": "unverified", **result, "reason": "execution_request_identity_mismatch"}
        route_frames = [frame for frame in relevant if frame.get("source") == "runtime_route_log"]
        frame = (route_frames or relevant)[-1] if relevant else None
        observed_provider = str((frame or {}).get("provider_hash") or "").removeprefix("h")
        observed_model = str((frame or {}).get("model_hash") or "").removeprefix("h")
        requested_provider = str(
            (frame or {}).get("requested_provider_hash") or ""
        ).removeprefix("h")
        requested_model = str(
            (frame or {}).get("requested_model_hash") or ""
        ).removeprefix("h")
        requested_effort = _route_effort((frame or {}).get("requested_effort"))
        effective_effort = _route_effort((frame or {}).get("effective_effort"))
        fallback_used = (frame or {}).get("fallback_used")
        fallback_reason = str((frame or {}).get("fallback_reason") or "").strip().lower()
        if not re.fullmatch(r"[0-9a-f]{16}", observed_provider) or not re.fullmatch(
            r"[0-9a-f]{16}", observed_model
        ) or not re.fullmatch(r"[0-9a-f]{16}", requested_provider) or not re.fullmatch(
            r"[0-9a-f]{16}", requested_model
        ) or not requested_effort or not effective_effort:
            return {"status": "unverified", **result, "reason": "execution_route_evidence_unavailable"}
        lineage, lineage_error = _validate_observed_lineage(
            configured,
            requested_provider_hash=requested_provider,
            requested_model_hash=requested_model,
            requested_effort=requested_effort,
            effective_provider_hash=observed_provider,
            effective_model_hash=observed_model,
            effective_effort=effective_effort,
            fallback_used=fallback_used,
            fallback_reason=fallback_reason,
        )
        if lineage is None:
            return {"status": "mismatch", **result, "reason": lineage_error}
        observed[
            (
                observed_provider,
                observed_model,
                effective_effort,
                bool(fallback_used),
                fallback_reason,
            )
        ] = lineage
        if selected_case_ids is not None:
            case_id = str(row.get("caseId") or "")
            if case_id not in selected_case_ids or any(item["caseId"] == case_id for item in case_evidence):
                return {"status": "unverified", **result, "reason": "execution_case_coverage_unverified"}
            observed_agent_hash = str(
                (frame or {}).get("agent_id_hash")
                or (frame or {}).get("agentIdHash")
                or ""
            ).removeprefix("h")
            if observed_agent_hash != expected_agent_hash:
                return {"status": "unverified", **result, "reason": "execution_agent_identity_mismatch"}
            judge = row.get("semanticJudge")
            judged = isinstance(judge, dict) and judge.get("status") == "judged"
            passed = judged and judge.get("pass") is True
            if semantic_judge_required:
                judge_model_hash = str((summary or {}).get("judgeModelHash") or "")
                attempts = (judge or {}).get("attemptCount")
                raw_hash = str((judge or {}).get("rawHash") or "")
                if (
                    not passed
                    or not re.fullmatch(r"[0-9a-f]{16}", judge_model_hash)
                    or judge_model_hash != str((arguments or {}).get("judgeModelHash") or "")
                    or not isinstance(attempts, int)
                    or isinstance(attempts, bool)
                    or attempts < 1
                    or not re.fullmatch(r"[0-9a-f]{16}", raw_hash)
                ):
                    return {"status": "unverified", **result, "reason": "semantic_judge_verdict_unverified"}
            case_evidence.append(
                {
                    "caseId": case_id,
                    "agentIdHash": observed_agent_hash,
                    "requestIdentityHash": request_identity_hash,
                    "semanticJudged": judged,
                    "semanticPassed": passed,
                }
            )

    if len(observed) != 1:
        return {"status": "mismatch", **result, "reason": "multiple_execution_routes_observed"}
    observed_provider, observed_model, _effort, _fallback, _reason = next(iter(observed))
    lineage = next(iter(observed.values()))
    result.update(
        {
            **lineage,
            "observedProviderHash": observed_provider,
            "observedModelHash": observed_model,
            "completedCaseCount": len(completed),
        }
    )
    if selected_case_ids is not None:
        result["artifactSha256"] = hashlib.sha256(artifact_bytes).hexdigest()
        result["caseEvidence"] = case_evidence
    return {"status": "verified", **result}


def _native_surface_execution_route(
    output_dir: Path,
    *,
    execution_target: dict[str, str] | None,
    selected_case_ids: list[str],
    requested_surface: str | None,
    semantic_judge_required: bool,
) -> dict[str, Any]:
    configured = _configured_execution_route(execution_target)
    expected_agent_hash = _configured_execution_agent_hash(execution_target)
    if not configured or not re.fullmatch(r"[0-9a-f]{16}", expected_agent_hash or ""):
        return {"status": "unverified", "reason": "configured_execution_identity_unavailable"}
    provider_hash = _sha(configured["provider"])
    model_hash = _sha(configured["model"])
    result: dict[str, Any] = {
        "requestedProvider": configured["provider"],
        "requestedModel": configured["model"],
        "requestedEffort": configured["effort"],
        "configuredProvider": configured["provider"],
        "configuredModel": configured["model"],
        "configuredProviderHash": provider_hash,
        "configuredModelHash": model_hash,
    }
    artifact_path = output_dir / "native-surface-playwright-qa.json"
    try:
        artifact_bytes = artifact_path.read_bytes()
        payload = json.loads(artifact_bytes.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {"status": "unverified", **result, "reason": "native_execution_artifact_unavailable"}
    if not isinstance(payload, dict):
        return {"status": "unverified", **result, "reason": "native_execution_artifact_invalid"}

    summary = payload.get("summary")
    arguments = payload.get("args")
    selection = payload.get("selection")
    cleanup = payload.get("cleanup")
    browser_probe = payload.get("browserProbe")
    rows = payload.get("cases")
    expected_surface = str(requested_surface or "").strip()
    if (
        not expected_surface
        or not isinstance(summary, dict)
        or not isinstance(arguments, dict)
        or not isinstance(selection, dict)
        or not isinstance(cleanup, dict)
        or not isinstance(browser_probe, dict)
        or not isinstance(rows, list)
    ):
        return {"status": "unverified", **result, "reason": "native_execution_contract_missing"}
    if (
        str(arguments.get("agentIdHash") or "") != expected_agent_hash
        or str(arguments.get("surface") or "") != expected_surface
        or selection.get("selectedCaseIds") != selected_case_ids
        or selection.get("selectedCaseCount") != len(selected_case_ids)
        or str(selection.get("requestedSurface") or "") != expected_surface
    ):
        return {"status": "unverified", **result, "reason": "native_execution_selection_mismatch"}
    expected_status = (
        "completed_with_semantic_native_surface_evidence"
        if semantic_judge_required
        else "completed_native_surface_evidence_without_semantic_judge"
    )
    accepted_statuses = {expected_status}
    if not semantic_judge_required:
        accepted_statuses.add("completed_with_semantic_native_surface_evidence")
    if (
        summary.get("status") not in accepted_statuses
        or summary.get("browserOk") is not True
        or summary.get("cleanupOk") is not True
        or summary.get("selectedCoverageOk") is not True
        or summary.get("completionEvidenceOk") is not True
        or summary.get("selectedCaseCount") != len(selected_case_ids)
        or summary.get("resultCount") != len(selected_case_ids)
        or summary.get("completedCount") != len(selected_case_ids)
        or summary.get("failedCount") != 0
        or cleanup.get("ok") is not True
        or cleanup.get("status") != "complete"
        or browser_probe.get("ok") is not True
    ):
        return {"status": "unverified", **result, "reason": "native_execution_summary_unverified"}
    if semantic_judge_required and (
        summary.get("semanticRequired") is not True
        or summary.get("semanticJudgedCount") != len(selected_case_ids)
        or summary.get("semanticPassedCount") != len(selected_case_ids)
        or summary.get("semanticFailedCount") != 0
    ):
        return {"status": "unverified", **result, "reason": "semantic_judge_verdict_unverified"}
    if len(rows) != len(selected_case_ids):
        return {"status": "unverified", **result, "reason": "execution_case_coverage_unverified"}

    case_evidence: list[dict[str, Any]] = []
    seen_case_ids: set[str] = set()
    observed_routes: dict[tuple[str, str, str, bool, str], dict[str, Any]] = {}
    expected_completion_surface = NATIVE_SURFACE_COMPLETION_SURFACES.get(expected_surface)
    completion_expected = expected_surface != "listen_only"
    if not expected_completion_surface:
        return {"status": "unverified", **result, "reason": "native_execution_surface_unsupported"}
    for row in rows:
        if not isinstance(row, dict):
            return {"status": "unverified", **result, "reason": "native_case_evidence_invalid"}
        case_id = str(row.get("caseId") or "")
        request_hash = str(row.get("requestIdentityHash") or "")
        agent_hash = str(row.get("actualCompletionAgentIdHash") or "")
        provider_hashes = row.get("completionProviderHashes")
        model_hashes = row.get("completionModelHashes")
        private = row.get("private")
        frames = private.get("completionFrames") if isinstance(private, dict) else None
        if (
            case_id not in selected_case_ids
            or case_id in seen_case_ids
            or row.get("status") != "completed"
            or row.get("surface") != expected_surface
            or row.get("requestedSurface") != expected_surface
            or row.get("requestedCompletionSurface") != expected_completion_surface
            or row.get("observedCompletionSurface")
            != (expected_completion_surface if completion_expected else "none")
            or row.get("completionExpected") is not completion_expected
            or row.get("completionSurfaceVerified") is not True
            or not re.fullmatch(r"[0-9a-f]{16}", request_hash)
            or not isinstance(frames, list)
        ):
            return {"status": "unverified", **result, "reason": "native_case_evidence_unverified"}
        if completion_expected:
            if agent_hash != expected_agent_hash or not frames:
                return {
                    "status": "unverified",
                    **result,
                    "reason": "native_case_evidence_unverified",
                }
            frame_lineages: dict[
                tuple[str, str, str, bool, str], dict[str, Any]
            ] = {}
            for frame in frames:
                if (
                    not isinstance(frame, dict)
                    or frame.get("prompt_family") not in {"main_run_create", "main_runtime"}
                    or frame.get("surface") != expected_completion_surface
                    or frame.get("agent_id_hash") != expected_agent_hash
                    or frame.get("request_identity_hash") != request_hash
                ):
                    return {
                        "status": "unverified",
                        **result,
                        "reason": "native_request_bound_frame_unverified",
                    }
                lineage, lineage_error = _validate_observed_lineage(
                    configured,
                    requested_provider_hash=_sha(
                        str(frame.get("requested_provider") or "")
                    ),
                    requested_model_hash=_sha(str(frame.get("requested_model") or "")),
                    requested_effort=_route_effort(frame.get("requested_effort")),
                    effective_provider_hash=_sha(
                        str(frame.get("effective_provider") or frame.get("provider") or "")
                    ),
                    effective_model_hash=_sha(
                        str(frame.get("effective_model") or frame.get("model") or "")
                    ),
                    effective_effort=_route_effort(frame.get("effective_effort")),
                    fallback_used=frame.get("fallback_used"),
                    fallback_reason=str(frame.get("fallback_reason") or ""),
                )
                if lineage is None:
                    return {"status": "mismatch", **result, "reason": lineage_error}
                route_key = (
                    _sha(lineage["effectiveProvider"]),
                    _sha(lineage["effectiveModel"]),
                    lineage["effectiveEffort"],
                    lineage["fallbackUsed"],
                    lineage["fallbackReason"],
                )
                frame_lineages[route_key] = lineage
            if len(frame_lineages) != 1:
                return {
                    "status": "unverified",
                    **result,
                    "reason": "multiple_execution_routes_observed",
                }
            route_key, lineage = next(iter(frame_lineages.items()))
            if (
                provider_hashes != [route_key[0]]
                or model_hashes != [route_key[1]]
                or row.get("requestedProviderHashes") != [provider_hash]
                or row.get("requestedModelHashes") != [model_hash]
                or row.get("requestedEfforts") != [configured["effort"]]
                or row.get("effectiveEfforts") != [lineage["effectiveEffort"]]
                or row.get("fallbackUsed") is not lineage["fallbackUsed"]
                or row.get("fallbackReasons") != [lineage["fallbackReason"]]
            ):
                return {
                    "status": "unverified",
                    **result,
                    "reason": "native_case_evidence_unverified",
                }
            if row.get("completionFrameCount") != len(frames):
                return {
                    "status": "unverified",
                    **result,
                    "reason": "native_completion_frame_count_mismatch",
                }
            observed_routes[route_key] = lineage
        elif (
            agent_hash != "not_applicable"
            or provider_hashes != []
            or model_hashes != []
            or row.get("requestedProviderHashes") != []
            or row.get("requestedModelHashes") != []
            or row.get("requestedEfforts") != []
            or row.get("effectiveEfforts") != []
            or row.get("fallbackUsed") is not False
            or row.get("fallbackReasons") != []
            or frames
            or row.get("completionFrameCount") != 0
        ):
            return {
                "status": "unverified",
                **result,
                "reason": "native_suppressed_completion_evidence_invalid",
            }
        judged = row.get("semanticJudged") is True
        passed = row.get("semanticPass") is True
        judge = row.get("judge")
        if semantic_judge_required and (
            not judged
            or not passed
            or not isinstance(judge, dict)
            or judge.get("verdict") != "pass"
            or not re.fullmatch(r"[0-9a-f]{16}", str(judge.get("responseHash") or ""))
        ):
            return {"status": "unverified", **result, "reason": "semantic_judge_verdict_unverified"}
        seen_case_ids.add(case_id)
        case_evidence.append(
            {
                "caseId": case_id,
                "agentIdHash": agent_hash,
                "requestIdentityHash": request_hash,
                "surface": expected_surface,
                "completionSurface": expected_completion_surface,
                "completionExpected": completion_expected,
                "semanticJudged": judged,
                "semanticPassed": passed,
            }
        )
    if seen_case_ids != set(selected_case_ids) or len(observed_routes) > 1:
        return {"status": "unverified", **result, "reason": "execution_case_coverage_unverified"}
    route_result: dict[str, Any] = {
        "routeExecution": "suppressed_by_surface_contract",
        "effectiveProvider": configured["provider"],
        "effectiveModel": configured["model"],
        "effectiveEffort": configured["effort"],
        "fallbackUsed": False,
        "fallbackAuthorized": False,
        "fallbackReason": "none",
    }
    if completion_expected:
        if len(observed_routes) != 1:
            return {"status": "unverified", **result, "reason": "execution_route_evidence_unavailable"}
        observed_provider, observed_model, _effort, _fallback, _reason = next(
            iter(observed_routes)
        )
        lineage = next(iter(observed_routes.values()))
        route_result = {
            **lineage,
            "routeExecution": "executed",
            "observedProviderHash": observed_provider,
            "observedModelHash": observed_model,
        }
    return {
        "status": "verified",
        **result,
        **route_result,
        "completedCaseCount": len(rows),
        "artifactSha256": hashlib.sha256(artifact_bytes).hexdigest(),
        "routes": sorted(str(value) for value in summary.get("routes") or []),
        "caseEvidence": sorted(case_evidence, key=lambda item: selected_case_ids.index(item["caseId"])),
    }


def _activation_model_execution_route(
    output_dir: Path,
    *,
    bank: dict[str, Any],
    family_id: str,
    selected_case_ids: list[str] | None = None,
) -> dict[str, Any]:
    try:
        artifact_bytes = (output_dir / "activation-model-eval.json").read_bytes()
        payload = json.loads(artifact_bytes.decode("utf-8"))
    except (OSError, ValueError, TypeError, UnicodeError, json.JSONDecodeError):
        return {"status": "unverified", "reason": "activation_execution_artifact_unavailable"}

    family = next(
        (
            row
            for row in bank.get("families") or []
            if isinstance(row, dict) and str(row.get("id") or "") == family_id
        ),
        None,
    )
    target_rows = (family or {}).get("activationTargets") or (family or {}).get("activation_targets") or []
    targets = {
        str(row.get("key") or ""): str(row.get("agentId") or row.get("agent_id") or "")
        for row in target_rows
        if isinstance(row, dict)
    }
    configured_family = _configured_family_execution_route(family_id)
    configured_targets = {
        str(row.get("targetKey") or ""): row
        for row in (configured_family or {}).get("targets") or []
        if isinstance(row, dict)
    }
    if (
        not targets
        or (configured_family or {}).get("kind") != "background_activation"
        or set(configured_targets) != set(targets)
    ):
        return {"status": "unverified", "reason": "activation_configured_target_unavailable"}
    results = payload.get("results") if isinstance(payload, dict) else None
    completed = [
        row
        for row in results or []
        if isinstance(row, dict) and isinstance(row.get("actual"), bool) and not row.get("error")
    ]
    if not completed:
        return {"status": "unverified", "reason": "activation_completed_execution_unavailable"}

    routes: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    case_evidence: list[dict[str, Any]] = []
    observed_decisions: set[tuple[str, str, int]] = set()
    for row in completed:
        target_key = str(row.get("targetKey") or "")
        configured = configured_targets.get(target_key)
        if not isinstance(configured, dict):
            return {"status": "unverified", "reason": "activation_configured_target_unavailable"}
        primary_provider = str(configured.get("provider") or "")
        primary_model = str(configured.get("model") or "")
        primary_effort = _route_effort(configured.get("effort"))
        observed_provider = str(row.get("providerUsed") or "")
        observed_model = str(row.get("modelUsed") or "")
        observed_effort = _route_effort(row.get("effortUsed"))
        requested_provider = str(row.get("requestedProvider") or "")
        requested_model = str(row.get("requestedModel") or "")
        requested_effort = _route_effort(row.get("requestedEffort"))
        effective_provider = str(row.get("effectiveProvider") or "")
        effective_model = str(row.get("effectiveModel") or "")
        effective_effort = _route_effort(row.get("effectiveEffort"))
        fallback_reason = str(row.get("fallbackReason") or "").strip().lower()
        if (
            not observed_effort
            or not requested_effort
            or not effective_effort
            or effective_provider != observed_provider
            or effective_model != observed_model
            or effective_effort != observed_effort
        ):
            return {"status": "unverified", "reason": "execution_effort_lineage_missing"}
        lineage, lineage_error = _validate_observed_lineage(
            configured,
            requested_provider_hash=_sha(requested_provider),
            requested_model_hash=_sha(requested_model),
            requested_effort=requested_effort,
            effective_provider_hash=_sha(observed_provider),
            effective_model_hash=_sha(observed_model),
            effective_effort=observed_effort,
            fallback_used=(
                observed_provider,
                observed_model,
                observed_effort,
            )
            != (primary_provider, primary_model, primary_effort),
            fallback_reason=fallback_reason,
        )
        if lineage is None:
            return {"status": "mismatch", "reason": lineage_error}
        attempts = row.get("providerAttempts")
        if not isinstance(attempts, list):
            return {"status": "unverified", "reason": "activation_provider_completion_unverified"}
        completed_attempt_index = next(
            (
                index
                for index, attempt in enumerate(attempts or [])
                if isinstance(attempt, dict)
                and attempt.get("status") == "completed"
                and attempt.get("provider") == observed_provider
                and attempt.get("model") == observed_model
                and _route_effort(attempt.get("effort")) == observed_effort
            ),
            None,
        )
        if completed_attempt_index is None:
            return {"status": "unverified", "reason": "activation_provider_completion_unverified"}
        completed_attempt = attempts[completed_attempt_index]
        fallback_used = lineage["fallbackUsed"]
        if (
            str(completed_attempt.get("fallbackReason") or "").strip().lower()
            != fallback_reason
            or completed_attempt.get("source") != ("fallback" if fallback_used else "primary")
        ):
            return {"status": "mismatch", "reason": "fallback_lineage_mismatch"}
        if fallback_used:
            prior_reason = next(
                (
                    str((attempt.get("error") or {}).get("class") or "")
                    .strip()
                    .lower()
                    for attempt in reversed(attempts[:completed_attempt_index])
                    if isinstance(attempt, dict)
                    and isinstance(attempt.get("error"), dict)
                    and str((attempt.get("error") or {}).get("class") or "").strip()
                ),
                "",
            )
            if prior_reason != fallback_reason:
                return {"status": "mismatch", "reason": "fallback_reason_mismatch"}
        primary_failure_verified = any(
            isinstance(attempt, dict)
            and attempt.get("provider") == primary_provider
            and attempt.get("model") == primary_model
            and _route_effort(attempt.get("effort")) == primary_effort
            and attempt.get("status")
            in {"error", "failed", "timeout", "unavailable", "skipped_unhealthy"}
            for attempt in (attempts or [])[:completed_attempt_index]
        )
        if selected_case_ids is not None:
            case_id = str(row.get("caseId") or "")
            repetition = row.get("repetition")
            required = row.get("required")
            allowed_decision = row.get("allowed")
            actual = row.get("actual")
            passed = row.get("pass")
            if (
                case_id not in selected_case_ids
                or not isinstance(repetition, int)
                or isinstance(repetition, bool)
                or repetition < 1
                or not isinstance(required, bool)
                or not isinstance(allowed_decision, bool)
                or not isinstance(actual, bool)
                or not isinstance(passed, bool)
            ):
                return {"status": "unverified", "reason": "activation_decision_evidence_unavailable"}
            key = (case_id, target_key, repetition)
            if key in observed_decisions:
                return {"status": "unverified", "reason": "activation_decision_duplicate"}
            observed_decisions.add(key)
            expected_pass = actual if required else allowed_decision or not actual
            if passed is not True or expected_pass is not True:
                return {"status": "mismatch", "reason": "activation_decision_incorrect"}
            if fallback_used and not primary_failure_verified:
                return {"status": "unverified", "reason": "activation_primary_failure_unverified"}
            case_evidence.append(
                {
                    "caseId": case_id,
                    "targetKey": target_key,
                    "repetition": repetition,
                    "required": required,
                    "allowed": allowed_decision,
                    "actual": actual,
                    "passed": passed,
                    "requestedProvider": primary_provider,
                    "requestedModel": primary_model,
                    "requestedEffort": primary_effort,
                    "effectiveProvider": observed_provider,
                    "effectiveModel": observed_model,
                    "effectiveEffort": observed_effort,
                    "fallbackReason": fallback_reason,
                    "primaryFailureVerified": primary_failure_verified,
                }
            )
        routes[(target_key, observed_provider, observed_model, observed_effort, fallback_reason)] = {
            "targetKey": target_key,
            **lineage,
            "configuredProvider": primary_provider,
            "configuredModel": primary_model,
        }
    result = {
        "status": "verified",
        "completedCaseCount": len(completed),
        "routes": sorted(routes.values(), key=lambda row: str(row["targetKey"])),
    }
    if selected_case_ids is not None:
        result["artifactSha256"] = hashlib.sha256(artifact_bytes).hexdigest()
        result["caseEvidence"] = case_evidence
    return result


def _public_runner_summary(stdout: str) -> dict[str, Any] | None:
    """Keep only aggregate eval evidence; never copy paths or private artifacts into the UI."""

    text = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", stdout)
    parsed: dict[str, Any] | None = None
    for start in reversed([match.start() for match in re.finditer(r"[\[{]", text)]):
        try:
            candidate = json.loads(text[start:].strip())
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict):
            parsed = candidate
            break
    if not parsed:
        return None

    public: dict[str, Any] = {}
    for key in ("status", "blockedReason"):
        value = parsed.get(key)
        if isinstance(value, str) and value:
            public[key] = _sanitize_output(value)
    for key in RUNNER_SUMMARY_COUNT_FIELDS:
        value = parsed.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            public[key] = value
    for list_key, count_key in RUNNER_SUMMARY_QUALITY_LIST_COUNTS.items():
        value = parsed.get(list_key)
        if not isinstance(value, list):
            continue
        derived_count = len(value)
        if count_key in public and public[count_key] != derived_count:
            public["status"] = "blocked"
            public["blockedReason"] = "runner_summary_quality_count_mismatch"
            continue
        public[count_key] = derived_count
    return public or None


def _eval_runner(
    *,
    bank: dict[str, Any],
    family: str | None,
    prompt_id: str | None,
    selected: list[dict[str, dict[str, Any]]] | None = None,
) -> Path:
    families = bank.get("families") or []
    if family:
        selected_family = next((row for row in families if row.get("id") == family), None)
        if selected_family and selected_family.get("runner") == "background_activation":
            return ACTIVATION_MODEL_EVAL_SCRIPT
    if prompt_id:
        for row in families:
            if row.get("runner") != "background_activation":
                continue
            if prompt_id in set(row.get("promptRefs") or row.get("prompt_refs") or []):
                return ACTIVATION_MODEL_EVAL_SCRIPT
    selected_surfaces = {
        str(row.get("case", {}).get("surface") or "web") for row in selected or []
    }
    if len(selected_surfaces) == 1 and next(iter(selected_surfaces), "web") in NATIVE_SURFACES:
        return NATIVE_SURFACE_EVAL_SCRIPT
    return EXACT_MODEL_EVAL_SCRIPT


def _runner_accepts_prompt_filter(
    *, runner: Path, bank: dict[str, Any], family: str | None, prompt_id: str
) -> bool:
    if runner != ACTIVATION_MODEL_EVAL_SCRIPT:
        if not family:
            return True
        selected = next(
            (
                row
                for row in bank.get("families") or []
                if isinstance(row, dict) and row.get("id") == family
            ),
            None,
        )
        if not selected:
            return False
        refs = _prompt_refs(selected)
        for case in selected.get("cases") or []:
            if isinstance(case, dict):
                refs.update(_prompt_refs(case))
        return prompt_id in refs
    for row in bank.get("families") or []:
        if row.get("runner") != "background_activation":
            continue
        if family and row.get("id") != family:
            continue
        target_refs = {
            str(target.get("promptRef") or target.get("prompt_ref") or "")
            for target in row.get("activationTargets") or row.get("activation_targets") or []
            if isinstance(target, dict)
        }
        if prompt_id in target_refs:
            return True
    return False


def get_eval_run(run_id: str) -> dict[str, Any]:
    path = workbench_private_root() / "eval-runs" / run_id / "workbench-run.json"
    if not path.exists():
        raise FileNotFoundError(f"Unknown eval run: {run_id}")
    return _public_run_record(json.loads(path.read_text(encoding="utf-8")))


def list_eval_runs(limit: int = 12) -> list[dict[str, Any]]:
    root = workbench_private_root() / "eval-runs"
    if not root.exists():
        return []
    rows = []
    for path in sorted(root.glob("*/workbench-run.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            rows.append(_public_run_record(json.loads(path.read_text(encoding="utf-8"))))
        except json.JSONDecodeError:
            continue
        if len(rows) >= limit:
            break
    return rows


def list_eval_runs_for_prompt(prompt_id: str, limit: int = 8) -> list[dict[str, Any]]:
    rows = []
    for run in list_eval_runs(limit=50):
        manifest_prompts = {
            str(row.get("id") or "")
            for row in (
                (run.get("lineageManifest") or {}).get("promptDependencies") or []
            )
            if isinstance(row, dict)
        }
        if (
            run.get("promptId") == prompt_id
            or prompt_id in manifest_prompts
        ):
            rows.append(run)
        if len(rows) >= limit:
            break
    return rows


def create_eval_case_draft(
    *,
    family_id: str,
    case_id: str,
    updated_case: dict[str, Any],
    create: bool = False,
    reason: str = "",
) -> dict[str, Any]:
    if not re.match(r"^[A-Za-z0-9_.-]+$", case_id):
        raise ValueError("Eval case id may only contain letters, numbers, underscores, dots, and dashes")
    bank = load_eval_bank()
    target_family: dict[str, Any] | None = None
    target_index: int | None = None
    for family in bank.get("families") or []:
        if family.get("id") != family_id:
            continue
        target_family = family
        for index, case in enumerate(family.get("cases") or []):
            if case.get("id") == case_id:
                target_index = index
                break
        break
    if not target_family:
        raise ValueError(f"Unknown eval family: {family_id}")
    if create and target_index is not None:
        raise ValueError(f"Eval case already exists: {family_id}/{case_id}")
    if not create and target_index is None:
        raise ValueError(f"Unknown eval case: {family_id}/{case_id}")

    if create:
        merged = _new_eval_case(case_id, updated_case)
    else:
        current_case = dict((target_family.get("cases") or [])[target_index or 0])
        merged = dict(current_case)
        merged.update(updated_case)
        merged["id"] = case_id
        if merged == current_case:
            raise ValueError("No changes detected; edit the eval case before saving a draft.")

    original_text = PROMPT_BANK_PATH.read_text(encoding="utf-8")
    new_text = _replace_eval_case_text(
        original_text,
        family_id=family_id,
        case_id=case_id,
        case=merged,
        create=create,
    )
    return drafts.create_file_draft(
        target_path=PROMPT_BANK_PATH,
        new_text=new_text,
        kind="eval-edit",
        reason=reason or f"Workbench eval {'create' if create else 'edit'} for {family_id}/{case_id}",
    )


def promptfoo_config(prompt_id: str) -> dict[str, Any]:
    return prompt_bank_to_promptfoo(load_eval_bank(), prompt_id=prompt_id)


def _public_family(family: dict[str, Any]) -> dict[str, Any]:
    row = dict(family)
    prompt_refs = [str(item) for item in (row.get("promptRefs") or row.get("prompt_refs") or [])]
    row["promptRefs"] = sorted(set(prompt_refs))
    cases = []
    for case in row.get("cases") or []:
        public_case = dict(case)
        case_refs = [str(item) for item in (public_case.get("promptRefs") or public_case.get("prompt_refs") or [])]
        public_case["promptRefs"] = sorted(set(prompt_refs + case_refs))
        cases.append(public_case)
    row["cases"] = cases
    return row


def _new_eval_case(case_id: str, updated_case: dict[str, Any]) -> dict[str, Any]:
    surface = str(updated_case.get("surface") or "").strip()
    prompt = str(updated_case.get("prompt") or "").strip()
    rubric = updated_case.get("rubric") or []
    if not surface:
        raise ValueError("New eval cases need a surface.")
    if not prompt:
        raise ValueError("New eval cases need a prompt.")
    if not isinstance(rubric, list) or not [item for item in rubric if str(item).strip()]:
        raise ValueError("New eval cases need at least one rubric item.")
    row: dict[str, Any] = {
        "id": case_id,
        "surface": surface,
        "prompt": prompt,
        "rubric": [str(item).strip() for item in rubric if str(item).strip()],
    }
    expected_decision = str(updated_case.get("expected_decision") or "").strip()
    expected_surface = str(updated_case.get("expected_surface") or "").strip()
    if expected_surface:
        row["expected_surface"] = expected_surface
    elif expected_decision:
        row["expected_decision"] = expected_decision
    return row


def _replace_eval_case_text(
    text: str,
    *,
    family_id: str,
    case_id: str,
    case: dict[str, Any],
    create: bool,
) -> str:
    families_start, families_end = _find_json_array(text, "families", 0, len(text))
    for family_start, family_end in _iter_json_objects(text, families_start, families_end):
        family = json.loads(text[family_start:family_end])
        if family.get("id") != family_id:
            continue
        cases_start, cases_end = _find_json_array(text, "cases", family_start, family_end)
        case_indent = _infer_child_object_indent(text, cases_start, cases_end)
        rendered_case = _format_json_block(case, indent=case_indent)
        if create:
            insert_pos = _last_non_ws_before(text, cases_end - 1) + 1
            if _array_has_objects(text, cases_start, cases_end):
                return text[:insert_pos] + ",\n" + rendered_case + text[insert_pos:]
            closing_indent = _line_indent(text, cases_end)
            return text[: cases_start + 1] + "\n" + rendered_case + "\n" + closing_indent + text[cases_end:]
        for case_start, case_end in _iter_json_objects(text, cases_start, cases_end):
            existing = json.loads(text[case_start:case_end])
            if existing.get("id") == case_id:
                replacement = _format_json_block(case, indent=_line_indent(text, case_start))
                return text[:case_start] + replacement + text[case_end:]
        raise ValueError(f"Unknown eval case: {family_id}/{case_id}")
    raise ValueError(f"Unknown eval family: {family_id}")


def _find_json_array(text: str, key: str, start: int, end: int) -> tuple[int, int]:
    pattern = re.compile(rf'"{re.escape(key)}"\s*:')
    match = pattern.search(text, start, end)
    if not match:
        raise ValueError(f"Could not locate eval bank key: {key}")
    index = match.end()
    while index < end and text[index].isspace():
        index += 1
    if index >= end or text[index] != "[":
        raise ValueError(f"Eval bank key is not an array: {key}")
    return index, _matching_delimiter(text, index, "[", "]") + 1


def _iter_json_objects(text: str, array_start: int, array_end: int):
    index = array_start + 1
    while index < array_end - 1:
        if text[index] == "{":
            object_end = _matching_delimiter(text, index, "{", "}") + 1
            yield index, object_end
            index = object_end
            continue
        index += 1


def _matching_delimiter(text: str, start: int, open_char: str, close_char: str) -> int:
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            continue
        if char == open_char:
            depth += 1
        elif char == close_char:
            depth -= 1
            if depth == 0:
                return index
    raise ValueError("Unbalanced eval bank JSON")


def _format_json_block(value: dict[str, Any], *, indent: str) -> str:
    return "\n".join(indent + line for line in json.dumps(value, indent=2, ensure_ascii=False).splitlines())


def _infer_child_object_indent(text: str, array_start: int, array_end: int) -> str:
    for object_start, _ in _iter_json_objects(text, array_start, array_end):
        return _line_indent(text, object_start)
    return _line_indent(text, array_start) + "  "


def _line_indent(text: str, index: int) -> str:
    line_start = text.rfind("\n", 0, index) + 1
    return text[line_start:index].split(text[index : index + 1] or " ", 1)[0]


def _last_non_ws_before(text: str, index: int) -> int:
    cursor = index - 1
    while cursor >= 0 and text[cursor].isspace():
        cursor -= 1
    return cursor


def _array_has_objects(text: str, array_start: int, array_end: int) -> bool:
    return any(True for _ in _iter_json_objects(text, array_start, array_end))


def _public_run_record(record: dict[str, Any]) -> dict[str, Any]:
    public = {key: value for key, value in record.items() if key in PUBLIC_RUN_FIELDS}
    output_dir = str(record.get("outputDir", "") or "")
    public["privateOutputAvailable"] = bool(output_dir)
    public["artifactName"] = Path(output_dir).name if output_dir else None
    summary = public.get("runnerSummary")
    if isinstance(summary, dict):
        public["runnerSummary"] = _public_runner_summary(json.dumps(summary))
    route = public.get("executionRoute")
    if isinstance(route, dict):
        public_route = {key: value for key, value in route.items() if key in PUBLIC_ROUTE_FIELDS}
        _retain_typed_fallback_reason(public_route)
        for field, allowed in (
            ("routes", PUBLIC_ROUTE_VARIANT_FIELDS),
            ("caseEvidence", PUBLIC_CASE_EVIDENCE_FIELDS),
        ):
            if isinstance(public_route.get(field), list):
                projected_items = [
                    {key: value for key, value in item.items() if key in allowed}
                    for item in public_route[field]
                    if isinstance(item, dict)
                ]
                for item in projected_items:
                    _retain_typed_fallback_reason(item)
                public_route[field] = projected_items
        public["executionRoute"] = public_route
    manifest = public.get("lineageManifest")
    if isinstance(manifest, dict):
        public_manifest = dict(manifest)
        dependencies = public_manifest.get("promptDependencies")
        if isinstance(dependencies, list):
            public_manifest["promptDependencies"] = []
            for dependency in dependencies:
                if not isinstance(dependency, dict):
                    continue
                safe_dependency = {
                    key: value
                    for key, value in dependency.items()
                    if key
                    in {
                        "id",
                        "kind",
                        "status",
                        "direct",
                        "path",
                        "contentHash",
                        "bodyHash",
                        "renderedHash",
                        "deliveryKind",
                        "deliveryTarget",
                    }
                }
                if str(safe_dependency.get("path") or "").startswith("/"):
                    safe_dependency.pop("path", None)
                public_manifest["promptDependencies"].append(safe_dependency)
        public["lineageManifest"] = public_manifest
    if "command" in public:
        public["command"] = _safe_command(
            [str(item) for item in public.get("command") or []],
            private_paths=((Path(output_dir),) if output_dir else ()),
        )
    private_paths = (Path(output_dir),) if output_dir else ()
    public["stdoutTail"] = _sanitize_output(
        str(public.get("stdoutTail") or ""), private_paths=private_paths
    )
    public["stderrTail"] = _sanitize_output(
        str(public.get("stderrTail") or ""), private_paths=private_paths
    )
    return public


def _retain_typed_fallback_reason(record: dict[str, Any]) -> None:
    if "fallbackReason" not in record:
        return
    reason = str(record.get("fallbackReason") or "").strip().lower()
    if reason == "none" or reason in TYPED_FALLBACK_REASONS:
        record["fallbackReason"] = reason
    else:
        record.pop("fallbackReason", None)


def _prompt_hash(prompt_id: str | None) -> str | None:
    if not prompt_id:
        return None
    try:
        from . import prompt_service

        rendered_hash = prompt_service.render_prompt_payload(prompt_id).get("renderedHash")
        if rendered_hash:
            return str(rendered_hash)
    except Exception:
        pass
    try:
        from . import prompt_service

        detail = prompt_service.get_prompt(prompt_id)
        return str(detail.get("contentHash") or detail.get("bodyHash") or "")
    except Exception:
        return None


def _redact_private_paths(text: str, private_paths: tuple[Path, ...] = ()) -> str:
    values = {str(Path.home()), str(workbench_private_root())}
    values.update(str(Path(path).expanduser().resolve(strict=False)) for path in private_paths)
    for value in sorted((item for item in values if item), key=len, reverse=True):
        text = text.replace(value, "<private>")
    return text


def _safe_command(
    cmd: list[str], *, private_paths: tuple[Path, ...] = ()
) -> list[str]:
    return [
        _redact_private_paths(item, private_paths) if isinstance(item, str) else item
        for item in cmd
    ]


def _workbench_candidate_source_hash() -> str | None:
    import sys

    app_module = sys.modules.get("prompt_workbench.app")
    boot_hash = getattr(app_module, "_BACKEND_BOOT_SOURCE_HASH", None)
    if isinstance(boot_hash, str) and re.fullmatch(r"[0-9a-f]{16}", boot_hash):
        return boot_hash
    digest = hashlib.sha256()
    try:
        for source in sorted(Path(__file__).parent.glob("*.py")):
            digest.update(source.name.encode("utf-8"))
            digest.update(b"\0")
            digest.update(source.read_bytes())
    except OSError:
        return None
    return digest.hexdigest()[:16]


def _sanitize_output(text: str, *, private_paths: tuple[Path, ...] = ()) -> str:
    import re
    from scripts.viventium.prompt_registry import PRIVATE_PATTERN_RULES

    text = re.sub(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", "<email>", text, flags=re.I)
    text = re.sub(r'("userId"\s*:\s*")[0-9a-f]{12,32}(")', r'\1<user-id>\2', text, flags=re.I)
    text = redact_credential_assignments(text)
    for label, pattern in PRIVATE_PATTERN_RULES:
        text = pattern.sub(f"<{label}>", text)
    return _redact_private_paths(text, private_paths)

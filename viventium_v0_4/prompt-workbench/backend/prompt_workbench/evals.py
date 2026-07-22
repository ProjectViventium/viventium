from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import (
    ACTIVATION_MODEL_EVAL_SCRIPT,
    EXACT_MODEL_EVAL_SCRIPT,
    PROMPT_BANK_PATH,
    REPO_ROOT,
    workbench_private_root,
)
from .prompt_service import load_eval_bank
from .promptfoo_adapter import prompt_bank_to_promptfoo
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

RUNNER_SUMMARY_COUNT_FIELDS = {
    "resultCount",
    "completedCount",
    "failedCount",
    "semanticJudgedCount",
    "semanticPassedCount",
    "semanticFailedCount",
    "semanticJudgeUnavailableCount",
    "duplicateResponseQualityFailureCount",
    "unresolvedAsyncQualityFailureCount",
}


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
    semantic_judge_required = any(
        row["family"].get("semanticJudge") is True
        or row["case"].get("semanticJudge") is True
        for row in selected
    )
    execution_target = _background_execution_target(
        bank, family, selected=selected
    )
    lineage_manifest = _eval_lineage_manifest(
        selected, execution_target=execution_target
    )
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = workbench_private_root() / "eval-runs" / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
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
    runner = _eval_runner(bank=bank, family=family, prompt_id=prompt_id)
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
    if surface:
        cmd.append(f"--surface={surface}")
    if prompt_id and _runner_accepts_prompt_filter(
        runner=runner,
        bank=bank,
        family=family,
        prompt_id=prompt_id,
    ):
        cmd.append(f"--prompt-id={prompt_id}")
    if execution_target:
        cmd.append(f"--agent-id={execution_target['agentId']}")
    if execution_target or semantic_judge_required:
        # Direct specialist cases use qualitative evidence/uncertainty rubrics. A transport-only
        # completion would not evaluate the behavior the selected eval contract claims to measure.
        cmd.append("--semantic-judge")
    child_env: dict[str, str] | None = None
    if runner == EXACT_MODEL_EVAL_SCRIPT:
        # A live run is an explicit action from the authenticated, loopback-only Workbench.
        # Let the canonical harness mint its short-lived local QA token without storing or
        # forwarding a password. The harness still rejects this path in CI and production.
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
        "surface": surface,
        "promptId": prompt_id,
        "promptHash": prompt_hash,
        "selectedCaseIds": [str(row["case"].get("id") or "") for row in selected],
        "selectedCaseCount": len(selected),
        "resultCount": actual_result_count,
        "runnerSummary": runner_summary,
        "lineageManifest": lineage_manifest,
        "executionTarget": execution_target,
        "semanticJudgeRequired": semantic_judge_required,
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
    return public or None


def _eval_runner(
    *, bank: dict[str, Any], family: str | None, prompt_id: str | None
) -> Path:
    families = bank.get("families") or []
    if family:
        selected = next((row for row in families if row.get("id") == family), None)
        if selected and selected.get("runner") == "background_activation":
            return ACTIVATION_MODEL_EVAL_SCRIPT
    if prompt_id:
        for row in families:
            if row.get("runner") != "background_activation":
                continue
            if prompt_id in set(row.get("promptRefs") or row.get("prompt_refs") or []):
                return ACTIVATION_MODEL_EVAL_SCRIPT
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
    public = dict(record)
    output_dir = str(public.pop("outputDir", "") or "")
    public["privateOutputAvailable"] = bool(output_dir)
    public["artifactName"] = Path(output_dir).name if output_dir else None
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


def _sanitize_output(text: str, *, private_paths: tuple[Path, ...] = ()) -> str:
    import re
    from scripts.viventium.prompt_registry import PRIVATE_PATTERN_RULES

    text = re.sub(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", "<email>", text, flags=re.I)
    text = re.sub(r'("userId"\s*:\s*")[0-9a-f]{12,32}(")', r'\1<user-id>\2', text, flags=re.I)
    for label, pattern in PRIVATE_PATTERN_RULES:
        text = pattern.sub(f"<{label}>", text)
    return _redact_private_paths(text, private_paths)

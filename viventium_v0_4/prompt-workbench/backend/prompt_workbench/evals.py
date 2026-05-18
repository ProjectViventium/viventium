from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import EXACT_MODEL_EVAL_SCRIPT, PROMPT_BANK_PATH, REPO_ROOT, workbench_private_root
from .prompt_service import load_eval_bank
from .promptfoo_adapter import prompt_bank_to_promptfoo
from . import drafts


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
) -> dict[str, Any]:
    drafts.assert_no_active_blocking_drafts(
        "Eval preview",
        prompt_id=prompt_id,
        include_eval_drafts=True,
        all_prompt_drafts=live or prompt_id in {None, "main.conscious_agent"},
    )
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = workbench_private_root() / "eval-runs" / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    prompt_hash = _prompt_hash(prompt_id)
    if not live:
        bank = load_eval_bank()
        filtered_cases = []
        for family_row in bank.get("families") or []:
            if family and family_row.get("id") != family:
                continue
            for case in family_row.get("cases") or []:
                if surface and case.get("surface") != surface:
                    continue
                filtered_cases.append(
                    {"family": family_row.get("id"), "case": case.get("id"), "surface": case.get("surface")}
                )
        cases = filtered_cases[:max_cases]
        record = {
            "id": run_id,
            "mode": "synthetic-no-live-preview",
            "returnCode": 0,
            "resultCount": len(cases),
            "cases": cases,
            "stdoutTail": "Synthetic no-live eval preview loaded the prompt bank and selected cases without live model execution.",
            "stderrTail": "",
            "outputDir": str(output_dir),
            "createdAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "live": False,
            "maxCases": max_cases,
            "family": family,
            "surface": surface,
            "promptId": prompt_id,
            "promptHash": prompt_hash,
            "selectedCaseIds": [case["case"] for case in cases],
        }
        (output_dir / "workbench-run.json").write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return _public_run_record(record)
    cmd = [
        "node",
        str(EXACT_MODEL_EVAL_SCRIPT),
        f"--prompt-bank={PROMPT_BANK_PATH}",
        f"--output-dir={output_dir}",
        f"--public-report={output_dir / 'public-safe-report.md'}",
        f"--max-cases={max_cases}",
        "--run-live" if live else "--no-live",
    ]
    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        timeout=180,
        check=False,
    )
    record = {
        "id": run_id,
        "command": _safe_command(cmd),
        "returnCode": result.returncode,
        "stdoutTail": _sanitize_output(result.stdout[-4000:]),
        "stderrTail": _sanitize_output(result.stderr[-4000:]),
        "outputDir": str(output_dir),
        "createdAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "live": live,
        "maxCases": max_cases,
        "family": family,
        "surface": surface,
        "promptId": prompt_id,
        "promptHash": prompt_hash,
    }
    (output_dir / "workbench-run.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return _public_run_record(record)


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
        if run.get("promptId") == prompt_id or (prompt_id == "main.conscious_agent" and not run.get("promptId")):
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
    if "main.conscious_agent" not in prompt_refs:
        prompt_refs.append("main.conscious_agent")
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
        public["command"] = _safe_command([str(item) for item in public.get("command") or []])
    public["stdoutTail"] = _sanitize_output(str(public.get("stdoutTail") or ""))
    public["stderrTail"] = _sanitize_output(str(public.get("stderrTail") or ""))
    return public


def _prompt_hash(prompt_id: str | None) -> str | None:
    if not prompt_id:
        return None
    try:
        from . import prompt_service

        return str(prompt_service.render_prompt_payload(prompt_id).get("renderedHash") or "")
    except Exception:
        return None


def _safe_command(cmd: list[str]) -> list[str]:
    return [
        item.replace(str(Path.home()), "~") if isinstance(item, str) else item
        for item in cmd
    ]


def _sanitize_output(text: str) -> str:
    import re
    from scripts.viventium.prompt_registry import PRIVATE_PATTERN_RULES

    text = re.sub(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", "<email>", text, flags=re.I)
    text = re.sub(r'("userId"\s*:\s*")[0-9a-f]{12,32}(")', r'\1<user-id>\2', text, flags=re.I)
    for label, pattern in PRIVATE_PATTERN_RULES:
        text = pattern.sub(f"<{label}>", text)
    return text.replace(str(Path.home()), "~")

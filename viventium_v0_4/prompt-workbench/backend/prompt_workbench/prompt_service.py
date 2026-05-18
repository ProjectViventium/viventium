from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from .paths import AGENTS_SOURCE_PATH, LIBRECHAT_ROOT, PROMPT_WORKBENCH_QA_COVERAGE_PATH, PROMPTS_ROOT, relative_to_repo

from scripts.viventium.prompt_registry import (
    DEFAULT_PROMPT_ROOT,
    VARIABLE_RE,
    build_prompt_bundle,
    load_prompt_registry,
    render_prompt,
)


def prompt_bundle() -> dict[str, Any]:
    return build_prompt_bundle(PROMPTS_ROOT)


def list_prompts() -> list[dict[str, Any]]:
    bundle = prompt_bundle()
    prompts = []
    for prompt_id, prompt in sorted((bundle.get("prompts") or {}).items()):
        metadata = prompt.get("metadata") or {}
        prompts.append(
            {
                "id": prompt_id,
                "path": prompt.get("path"),
                "family": _family_for_prompt(prompt_id, metadata),
                "ownerLayer": metadata.get("owner_layer"),
                "target": metadata.get("target"),
                "version": metadata.get("version"),
                "status": metadata.get("status"),
                "safetyClass": metadata.get("safety_class"),
                "contentHash": prompt.get("content_hash"),
                "bodyHash": prompt.get("body_hash"),
                "includeCount": len(metadata.get("includes") or []),
                "charCount": len(str(prompt.get("body") or "")),
            }
        )
    return prompts


def get_prompt(prompt_id: str) -> dict[str, Any]:
    registry = load_prompt_registry(PROMPTS_ROOT)
    entry = registry[prompt_id]
    rendered = render_prompt(prompt_id, registry)
    body = entry.body
    return {
        "id": prompt_id,
        "path": relative_to_repo(entry.path),
        "text": entry.path.read_text(encoding="utf-8"),
        "metadata": entry.metadata,
        "body": body,
        "rendered": rendered,
        "contentHash": entry.content_hash,
        "bodyHash": _sha(body),
        "variables": sorted(set(VARIABLE_RE.findall(rendered))),
        "includes": [str(item) for item in (entry.metadata.get("includes") or [])],
        "dependents": _dependents(prompt_id, registry),
        "gitHistory": git_history(entry.path),
    }


def workbench_context(prompt_id: str) -> dict[str, Any]:
    registry = load_prompt_registry(PROMPTS_ROOT)
    entry = registry[prompt_id]
    from . import drafts, evals, sync_engine

    sync_status = sync_engine.get_status()
    sync_row = next((row for row in sync_status.get("agents") or [] if row.get("sourcePromptId") == prompt_id), None)
    return {
        "promptId": prompt_id,
        "path": relative_to_repo(entry.path),
        "contentHash": entry.content_hash,
        "bodyHash": _sha(entry.body),
        "drafts": _prompt_context_drafts(drafts, prompt_id),
        "gitHistory": git_history(entry.path, limit=8),
        "linkedEvals": evals.evals_for_prompt(prompt_id),
        "evalRuns": evals.list_eval_runs_for_prompt(prompt_id, limit=8),
        "qaCoverage": qa_coverage_for_prompt(prompt_id),
        "sync": sync_row,
    }


def _prompt_context_drafts(drafts_module: Any, prompt_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for draft in drafts_module.list_drafts(prompt_id=prompt_id, limit=20):
        draft_id = str(draft.get("id") or "")
        if draft_id:
            seen.add(draft_id)
        rows.append(draft)
    for draft in drafts_module.list_drafts(limit=20):
        draft_id = str(draft.get("id") or "")
        if draft.get("kind") != "eval-edit" or draft_id in seen:
            continue
        rows.append(draft)
        if draft_id:
            seen.add(draft_id)
    return rows[:20]


def render_prompt_payload(prompt_id: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    registry = load_prompt_registry(PROMPTS_ROOT)
    rendered = render_prompt(prompt_id, registry, variables=variables or {})
    return {
        "id": prompt_id,
        "rendered": rendered,
        "renderedHash": _sha(rendered),
        "variables": sorted(set(VARIABLE_RE.findall(rendered))),
    }


def source_agents_bundle() -> dict[str, Any]:
    from scripts.viventium.prompt_registry import load_and_resolve_prompt_refs

    source = yaml.safe_load(AGENTS_SOURCE_PATH.read_text(encoding="utf-8"))
    return load_and_resolve_prompt_refs(source, DEFAULT_PROMPT_ROOT)


def flow_graph() -> dict[str, list[dict[str, Any]]]:
    prompts = list_prompts()
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    for prompt in prompts:
        prompt_id = prompt["id"]
        nodes.append(
            {
                "id": prompt_id,
                "type": "prompt",
                "data": {
                    "label": prompt_id,
                    "family": prompt["family"],
                    "hash": prompt.get("contentHash"),
                },
            }
        )
    registry = load_prompt_registry(PROMPTS_ROOT)
    for prompt_id, entry in registry.items():
        for include_id in entry.metadata.get("includes") or []:
            edges.append(
                {
                    "id": f"{prompt_id}->{include_id}",
                    "source": prompt_id,
                    "target": str(include_id),
                    "label": "includes",
                }
            )
    return {"nodes": nodes, "edges": edges}


def git_history(path: Path, limit: int = 8) -> list[dict[str, Any]]:
    import subprocess

    cwd = LIBRECHAT_ROOT if LIBRECHAT_ROOT in path.parents else path.parents[0]
    try:
        git_path = str(path.resolve().relative_to(cwd.resolve()))
    except ValueError:
        git_path = str(path)
    try:
        output = subprocess.check_output(
            [
                "git",
                "log",
                f"--max-count={limit}",
                "--date=short",
                "--pretty=format:%h%x09%ad%x09%s",
                "--",
                git_path,
            ],
            cwd=cwd,
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
    except Exception:
        return []
    rows: list[dict[str, str]] = []
    for line in output.splitlines():
        parts = line.split("\t", 2)
        if len(parts) == 3:
            patch = git_patch_for_commit(parts[0], path, cwd=cwd, git_path=git_path)
            rows.append({"commit": parts[0], "date": parts[1], "subject": parts[2], "patch": patch, "changeSummary": _patch_stats(patch)})
    return rows


def git_patch_for_commit(commit: str, path: Path, *, cwd: Path | None = None, git_path: str | None = None) -> str:
    import subprocess

    cwd = cwd or (LIBRECHAT_ROOT if LIBRECHAT_ROOT in path.parents else path.parents[0])
    if git_path is None:
        try:
            git_path = str(path.resolve().relative_to(cwd.resolve()))
        except ValueError:
            git_path = str(path)
    try:
        patch = subprocess.check_output(
            [
                "git",
                "show",
                "--format=",
                "--find-renames",
                "--unified=8",
                commit,
                "--",
                git_path,
            ],
            cwd=cwd,
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
    except Exception:
        return ""
    return _sanitize_patch_paths(patch)


def qa_coverage_for_prompt(prompt_id: str) -> list[dict[str, Any]]:
    if not PROMPT_WORKBENCH_QA_COVERAGE_PATH.exists():
        return []
    try:
        coverage = yaml.safe_load(PROMPT_WORKBENCH_QA_COVERAGE_PATH.read_text(encoding="utf-8")) or {}
    except Exception:
        return []
    rows = []
    for row in coverage.get("cases") or []:
        applies_to = row.get("appliesTo")
        applies = applies_to == "all"
        if isinstance(applies_to, list):
            applies = prompt_id in applies_to or "all" in applies_to
        if applies:
            rows.append({
                "id": row.get("id"),
                "title": row.get("title"),
                "source": row.get("source"),
                "lastRun": str(row.get("lastRun")) if row.get("lastRun") is not None else None,
            })
    return rows


def load_eval_bank() -> dict[str, Any]:
    from .paths import PROMPT_BANK_PATH

    return json.loads(PROMPT_BANK_PATH.read_text(encoding="utf-8"))


def _family_for_prompt(prompt_id: str, metadata: dict[str, Any]) -> str:
    if prompt_id.startswith("main."):
        return "Main"
    if prompt_id.startswith("surface."):
        return "Surface"
    if prompt_id.startswith("cortex."):
        return "Cortex"
    if prompt_id.startswith("mcp."):
        return "MCP"
    if prompt_id.startswith("memory."):
        return "Memory"
    if "follow_up" in prompt_id:
        return "Follow-up"
    owner = str(metadata.get("owner_layer") or "").lower()
    if "eval" in owner:
        return "Eval"
    return "Other"


def _dependents(prompt_id: str, registry: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for candidate_id, entry in registry.items():
        includes = [str(item) for item in (entry.metadata.get("includes") or [])]
        if prompt_id in includes:
            result.append(candidate_id)
    return sorted(result)


def _sha(value: str, length: int = 16) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def _sanitize_patch_paths(patch: str) -> str:
    return patch.replace(str(LIBRECHAT_ROOT), "LibreChat").replace(str(PROMPTS_ROOT), "prompts")


def _patch_stats(patch: str) -> dict[str, int | str]:
    additions = 0
    deletions = 0
    for line in patch.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            additions += 1
        elif line.startswith("-"):
            deletions += 1
    label = "no file diff"
    if additions and deletions:
        label = f"{additions} added, {deletions} removed"
    elif additions:
        label = f"{additions} added"
    elif deletions:
        label = f"{deletions} removed"
    return {"additions": additions, "deletions": deletions, "label": label}

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from .paths import AGENTS_SOURCE_PATH, LIBRECHAT_ROOT, LIBRECHAT_SOURCE_PATH, PROMPT_WORKBENCH_QA_COVERAGE_PATH, PROMPTS_ROOT, relative_to_repo

from scripts.viventium.prompt_registry import (
    DEFAULT_PROMPT_ROOT,
    PromptRegistryError,
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
    rendered = _render_prompt_preview(prompt_id, registry)
    body = entry.body
    history = git_history(entry.path)
    working_tree_changed = any(row.get("workingTree") for row in history)
    working_tree_base_text = git_text_at_head(entry.path) if working_tree_changed else None
    if working_tree_changed and working_tree_base_text is None:
        working_tree_base_text = ""
    return {
        "id": prompt_id,
        "path": relative_to_repo(entry.path),
        "text": entry.path.read_text(encoding="utf-8"),
        "workingTreeBaseText": working_tree_base_text,
        "workingTreeChanged": working_tree_changed,
        "metadata": entry.metadata,
        "body": body,
        "rendered": rendered,
        "contentHash": entry.content_hash,
        "bodyHash": _sha(body),
        "variables": sorted(set(VARIABLE_RE.findall(rendered))),
        "includes": [str(item) for item in (entry.metadata.get("includes") or [])],
        "dependents": _dependents(prompt_id, registry),
        "gitHistory": history,
    }


def get_prompt_revision(prompt_id: str, revision: str) -> dict[str, Any]:
    registry = load_prompt_registry(PROMPTS_ROOT)
    entry = registry[prompt_id]
    normalized_revision = normalize_prompt_revision(revision)
    text = git_text_at_revision(entry.path, normalized_revision)
    if text is None:
        raise KeyError(f"Prompt revision not found: {prompt_id}@{normalized_revision}")
    return {
        "promptId": prompt_id,
        "revision": normalized_revision,
        "path": relative_to_repo(entry.path),
        "text": text,
    }


def workbench_context(prompt_id: str) -> dict[str, Any]:
    registry = load_prompt_registry(PROMPTS_ROOT)
    entry = registry[prompt_id]
    from . import drafts, evals, sync_engine

    sync_status = sync_engine.get_status()
    delivery = prompt_delivery_contract(prompt_id, entry.metadata)
    sync_row = _sync_row_for_prompt(
        prompt_id,
        delivery=delivery,
        sync_rows=sync_status.get("agents") or [],
    )
    runtime_bundle = (
        runtime_prompt_bundle_status(prompt_id)
        if delivery["kind"] == "compiled_runtime"
        else None
    )
    delivery["state"] = (
        sync_row.get("state")
        if sync_row
        else (runtime_bundle or {}).get("promptState") or "not-mapped"
    )
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
        "delivery": delivery,
        "runtimePromptBundle": runtime_bundle,
        "relatedConfig": related_config_for_prompt(prompt_id),
    }


def prompt_delivery_contract(
    prompt_id: str, metadata: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Describe the real delivery owner without claiming current runtime state."""

    if metadata is None:
        metadata = load_prompt_registry(PROMPTS_ROOT)[prompt_id].metadata
    target = str(metadata.get("target") or "")
    managed = (
        target in {"main.instructions", "main.instructions.section"}
        or target.startswith("mainAgent.")
        or target.startswith("backgroundAgents.")
        or target.startswith("handoffAgents.")
    )
    if managed:
        return {
            "kind": "managed_agent",
            "label": "Managed agent record",
            "statusSource": "agent_sync",
            "target": target,
        }
    return {
        "kind": "compiled_runtime",
        "label": "Compiled runtime prompt bundle",
        "statusSource": "prompt_bundle_drift",
        "target": target,
    }


def _sync_row_for_prompt(
    prompt_id: str,
    *,
    delivery: dict[str, Any],
    sync_rows: list[dict[str, Any]],
) -> dict[str, Any] | None:
    exact = next(
        (row for row in sync_rows if row.get("sourcePromptId") == prompt_id), None
    )
    if exact or delivery.get("kind") != "managed_agent":
        return exact
    if str(delivery.get("target") or "") in {
        "main.instructions",
        "main.instructions.section",
    }:
        return next(
            (
                row
                for row in sync_rows
                if row.get("sourcePromptId") == "main.conscious_agent"
            ),
            None,
        )
    return None


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


def runtime_prompt_bundle_status(prompt_id: str) -> dict[str, Any]:
    """Public-safe source-vs-compiled prompt bundle status for runtime-owned prompts."""

    try:
        from scripts.viventium.config_compiler import check_prompt_bundle_drift

        report = check_prompt_bundle_drift()
    except Exception:
        return {
            "status": "error",
            "reason": "prompt_bundle_drift_check_failed",
            "promptState": "unknown",
            "promptAffected": False,
            "liveBundleAvailable": False,
            "driftCount": None,
        }

    diff = report.get("diff") if isinstance(report, dict) else {}
    added = _string_set((diff or {}).get("added"))
    removed = _string_set((diff or {}).get("removed"))
    changed = _string_set((diff or {}).get("changed"))
    affected = prompt_id in added or prompt_id in removed or prompt_id in changed
    status = str(report.get("status") or "unknown")
    reason = str(report.get("reason") or "unknown")
    prompt_state = "unknown"
    if status == "ok":
        prompt_state = "synced"
    elif reason == "no_live_prompt_bundle_found":
        prompt_state = "bundle-unavailable"
    elif prompt_id in added:
        prompt_state = "source-only"
    elif prompt_id in removed:
        prompt_state = "live-only"
    elif prompt_id in changed:
        prompt_state = "drift"
    elif int(report.get("drift_count") or 0) > 0:
        prompt_state = "other-drift"

    return {
        "status": status,
        "reason": reason,
        "promptState": prompt_state,
        "promptAffected": affected,
        "liveBundleAvailable": bool((report.get("live") or {}).get("prompt_count")),
        "driftCount": report.get("drift_count"),
        "candidateCount": report.get("candidate_count"),
        "sourcePromptCount": (report.get("source") or {}).get("prompt_count"),
        "livePromptCount": (report.get("live") or {}).get("prompt_count"),
        "compareReviewed": bool(report.get("compare_reviewed")),
    }


def _string_set(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {str(item) for item in value}


def render_prompt_payload(prompt_id: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    registry = load_prompt_registry(PROMPTS_ROOT)
    rendered = render_prompt(prompt_id, registry, variables=variables or {})
    return {
        "id": prompt_id,
        "rendered": rendered,
        "renderedHash": _sha(rendered),
        "variables": sorted(set(VARIABLE_RE.findall(rendered))),
    }


def _render_prompt_preview(prompt_id: str, registry: dict[str, Any]) -> str:
    """Render inspectable templates without requiring runtime-only variables."""

    variables = _preview_variables_for_prompt(prompt_id, registry)
    try:
        return render_prompt(prompt_id, registry, variables=variables)
    except PromptRegistryError:
        if variables:
            raise
        return render_prompt(prompt_id, registry)


def _preview_variables_for_prompt(prompt_id: str, registry: dict[str, Any], seen: set[str] | None = None) -> dict[str, Any]:
    seen = seen or set()
    if prompt_id in seen:
        return {}
    entry = registry[prompt_id]
    seen.add(prompt_id)
    variables: dict[str, Any] = {}
    for include_id in entry.metadata.get("includes") or []:
        _merge_preview_variables(variables, _preview_variables_for_prompt(str(include_id), registry, seen))
    for key in VARIABLE_RE.findall(entry.body):
        _assign_preview_variable(variables, key)
    return variables


def _assign_preview_variable(variables: dict[str, Any], key: str) -> None:
    current = variables
    segments = key.split(".")
    for segment in segments[:-1]:
        nested = current.get(segment)
        if not isinstance(nested, dict):
            nested = {}
            current[segment] = nested
        current = nested
    current[segments[-1]] = "{{" + key + "}}"


def _merge_preview_variables(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _merge_preview_variables(target[key], value)
        else:
            target[key] = value


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


def git_history(path: Path, limit: int = 8, *, include_patch: bool = True) -> list[dict[str, Any]]:
    import subprocess

    cwd = LIBRECHAT_ROOT if LIBRECHAT_ROOT in path.parents else path.parents[0]
    try:
        git_path = str(path.resolve().relative_to(cwd.resolve()))
    except ValueError:
        git_path = str(path)
    rows: list[dict[str, Any]] = []
    if include_patch:
        working_tree_patch = git_working_tree_patch(path, cwd=cwd, git_path=git_path)
        if working_tree_patch:
            rows.append(
                {
                    "commit": "working-tree",
                    "date": "uncommitted",
                    "subject": "Uncommitted source changes",
                    "patch": working_tree_patch,
                    "changeSummary": _patch_stats(working_tree_patch),
                    "workingTree": True,
                }
            )
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
            encoding="utf-8",
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
    except Exception:
        return rows
    for line in output.splitlines():
        parts = line.split("\t", 2)
        if len(parts) == 3:
            patch = git_patch_for_commit(parts[0], path, cwd=cwd, git_path=git_path) if include_patch else ""
            row: dict[str, Any] = {"commit": parts[0], "date": parts[1], "subject": parts[2]}
            if include_patch:
                row.update({"patch": patch, "changeSummary": _patch_stats(patch)})
            rows.append(row)
    return rows


def git_working_tree_patch(path: Path, *, cwd: Path | None = None, git_path: str | None = None) -> str:
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
                "diff",
                "HEAD",
                "--find-renames",
                "--unified=8",
                "--",
                git_path,
            ],
            cwd=cwd,
            encoding="utf-8",
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
    except Exception:
        return ""
    if not patch and git_untracked(path, cwd=cwd, git_path=git_path):
        patch = git_untracked_patch(path, cwd=cwd, git_path=git_path)
    return _sanitize_patch_paths(patch)


def git_untracked(path: Path, *, cwd: Path | None = None, git_path: str | None = None) -> bool:
    import subprocess

    cwd = cwd or (LIBRECHAT_ROOT if LIBRECHAT_ROOT in path.parents else path.parents[0])
    if git_path is None:
        try:
            git_path = str(path.resolve().relative_to(cwd.resolve()))
        except ValueError:
            git_path = str(path)
    try:
        output = subprocess.check_output(
            ["git", "ls-files", "--others", "--exclude-standard", "--", git_path],
            cwd=cwd,
            encoding="utf-8",
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
    except Exception:
        return False
    return any(line == git_path for line in output.splitlines())


def git_untracked_patch(path: Path, *, cwd: Path | None = None, git_path: str | None = None) -> str:
    import subprocess

    cwd = cwd or (LIBRECHAT_ROOT if LIBRECHAT_ROOT in path.parents else path.parents[0])
    if git_path is None:
        try:
            git_path = str(path.resolve().relative_to(cwd.resolve()))
        except ValueError:
            git_path = str(path)
    try:
        completed = subprocess.run(
            ["git", "diff", "--no-index", "--find-renames", "--unified=8", "--", "/dev/null", git_path],
            cwd=cwd,
            encoding="utf-8",
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
    except Exception:
        return ""
    if completed.returncode not in {0, 1}:
        return ""
    return completed.stdout


def git_text_at_head(path: Path, *, cwd: Path | None = None, git_path: str | None = None) -> str | None:
    import subprocess

    cwd = cwd or (LIBRECHAT_ROOT if LIBRECHAT_ROOT in path.parents else path.parents[0])
    if git_path is None:
        try:
            git_path = str(path.resolve().relative_to(cwd.resolve()))
        except ValueError:
            git_path = str(path)
    try:
        return subprocess.check_output(
            ["git", "show", f"HEAD:{git_path}"],
            cwd=cwd,
            encoding="utf-8",
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
    except Exception:
        return None


def normalize_prompt_revision(revision: str) -> str:
    value = (revision or "").strip()
    if value == "working-tree-base":
        return "HEAD"
    if value == "HEAD" or re.fullmatch(r"[0-9a-fA-F]{7,40}", value):
        return value
    raise ValueError("Unsupported prompt revision. Choose a git history entry from this prompt.")


def git_text_at_revision(path: Path, revision: str, *, cwd: Path | None = None, git_path: str | None = None) -> str | None:
    import subprocess

    cwd = cwd or (LIBRECHAT_ROOT if LIBRECHAT_ROOT in path.parents else path.parents[0])
    if git_path is None:
        try:
            git_path = str(path.resolve().relative_to(cwd.resolve()))
        except ValueError:
            git_path = str(path)
    try:
        return subprocess.check_output(
            ["git", "show", f"{revision}:{git_path}"],
            cwd=cwd,
            encoding="utf-8",
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
    except Exception:
        return None


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
            encoding="utf-8",
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


def related_config_for_prompt(prompt_id: str) -> list[dict[str, Any]]:
    """Public-safe config surfaces that materially affect a prompt family."""

    registry = _safe_yaml(PROMPTS_ROOT / "registry.yaml")
    related = registry.get("related_config", {}) if isinstance(registry.get("related_config"), dict) else {}
    prompt_refs = (related.get("prompts") or {}).get(prompt_id) or []
    ref_catalog = related.get("refs") or {}
    rows: list[dict[str, Any]] = []
    if not isinstance(prompt_refs, list) or not isinstance(ref_catalog, dict):
        return rows
    for ref_id in prompt_refs:
        ref = ref_catalog.get(str(ref_id))
        if isinstance(ref, dict):
            row = _related_config_row(str(ref_id), ref)
            if row:
                rows.append(row)
    return rows


def _related_config_row(ref_id: str, ref: dict[str, Any]) -> dict[str, Any] | None:
    source_path = _config_source_path(str(ref.get("path") or ""))
    if not source_path:
        return None
    source_kind = str(ref.get("source") or "")
    server = str(ref.get("server") or "")
    source = _safe_yaml(source_path)
    items: list[str] = []
    if source_kind == "agents.direct_action_mcp_server":
        server_config = _direct_action_server_config(source, server)
        if not server_config:
            return None
        items = [
            f"{len(server_config.get('tool_names') or [])} owned tools",
            "background cortices defer to this owner for execution/status",
            "uses structured owner metadata, not schedule-name or prompt-text matching",
        ]
    elif source_kind == "agents.main_agent_tools":
        tools = [str(tool) for tool in (source.get("mainAgent", {}).get("tools") or []) if server and server in str(tool)]
        if not tools:
            return None
        items = [f"{len(tools)} main-agent tools enabled", *tools[:5], *([] if len(tools) <= 5 else [f"{len(tools) - 5} more tools"])]
    elif source_kind == "librechat.mcp_server":
        server_config = (source.get("mcpServers", {}) or {}).get(server, {})
        if not isinstance(server_config, dict) or not server_config:
            return None
        items = [
            f"type: {server_config.get('type')}",
            f"chat menu: {_yes_no(server_config.get('chatMenu'))}",
            f"server instructions: {_yes_no(server_config.get('serverInstructions'))}",
            f"trusted instructions: {_yes_no(server_config.get('viventiumTrustedServerInstructions'))}",
            f"timeout: {server_config.get('timeout')} ms",
            f"headers configured: {len(server_config.get('headers') or {})}",
        ]
    else:
        return None
    return {
        "id": ref_id.replace(".", "-").replace("_", "-"),
        "title": str(ref.get("title") or ref_id),
        "path": relative_to_repo(source_path),
        "selector": str(ref.get("selector") or ""),
        "summary": str(ref.get("summary") or ""),
        "status": "source",
        "items": items,
        "gitHistory": _config_history(source_path),
    }


def _config_source_path(path_name: str) -> Path | None:
    paths = {
        "local.viventium-agents.yaml": AGENTS_SOURCE_PATH,
        "local.librechat.yaml": LIBRECHAT_SOURCE_PATH,
    }
    return paths.get(path_name)


def _direct_action_server_config(source: dict[str, Any], server: str) -> dict[str, Any]:
    direct_action_servers = (
        source
        .get("config", {})
        .get("viventium", {})
        .get("background_cortices", {})
        .get("activation_policy", {})
        .get("direct_action_mcp_servers", [])
    )
    if not isinstance(direct_action_servers, list):
        return {}
    for row in direct_action_servers:
        if isinstance(row, dict) and row.get("server") == server:
            return row
    return {}


def _safe_yaml(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _config_history(path: Path) -> list[dict[str, Any]]:
    rows = []
    for row in git_history(path, limit=4, include_patch=False):
        rows.append(
            {
                "commit": row.get("commit"),
                "date": row.get("date"),
                "subject": row.get("subject"),
            }
        )
    return rows


def _yes_no(value: Any) -> str:
    return "yes" if bool(value) else "no"


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

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .import_mapper import create_import_live_draft
from .paths import AGENT_SYNC_SCRIPT, LIBRECHAT_ROOT, REPO_ROOT, workbench_private_root
from .prompt_service import source_agents_bundle
from . import drafts

LIVE_TEXT_CACHE: dict[str, str] = {}


SYNC_STATES = {"synced", "live-ahead", "source-ahead", "conflict"}


def classify_sync_state(
    *,
    source_hash: str,
    live_hash: str | None,
    ledger_record: dict[str, Any] | None,
) -> str:
    if not live_hash:
        return "source-ahead"
    if source_hash == live_hash:
        return "synced"
    if not ledger_record:
        return "conflict"

    source_changed = source_hash != ledger_record.get("sourceHash")
    live_changed = live_hash != ledger_record.get("liveHash")
    if source_changed and live_changed:
        return "conflict"
    if live_changed:
        return "live-ahead"
    if source_changed:
        return "source-ahead"
    return "conflict"


def get_status(*, private_root: Path | None = None) -> dict[str, Any]:
    ledger = load_ledger(private_root=private_root)
    source = source_agents_bundle()
    live = load_latest_live_bundle()
    live_artifact = Path(str(live.get("_artifactPath"))) if isinstance(live, dict) and live.get("_artifactPath") else None
    ledger_file = ledger_path(private_root=private_root)
    rows = _agent_rows(source=source, live=live, ledger=ledger)
    counts = {state: 0 for state in SYNC_STATES}
    for row in rows:
        counts[row["state"]] += 1
    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sourceCommit": _git_commit(),
        "liveArtifactAvailable": live_artifact is not None,
        "liveArtifactName": live_artifact.name if live_artifact else None,
        "ledgerAvailable": ledger_file.exists(),
        "counts": counts,
        "agents": rows,
    }


def pull_live(env: str = "local") -> dict[str, Any]:
    return run_agent_sync(["pull", f"--env={env}"])


def push_live_dry_run(env: str = "local") -> dict[str, Any]:
    drafts.assert_no_active_blocking_drafts("Push dry-run", all_prompt_drafts=True)
    status = get_status()
    result = run_agent_sync(["push", f"--env={env}", "--prompts-only", "--dry-run"])
    result["reviewToken"] = _review_token(result)
    _persist_dry_run(result, source_hashes=_source_hash_snapshot(status))
    return result


def push_live_reviewed(*, review_token: str, env: str = "local") -> dict[str, Any]:
    drafts.assert_no_active_blocking_drafts("Reviewed push", all_prompt_drafts=True)
    reviewed = _load_dry_run_by_token(review_token)
    if not reviewed:
        raise ValueError("Review token does not match a stored dry-run; run and review dry-run again")
    status = get_status()
    counts = status.get("counts") or {}
    blocked = int(counts.get("live-ahead") or 0) + int(counts.get("conflict") or 0)
    if blocked:
        raise ValueError("Live drift still needs review; resolve live-ahead/conflict rows before reviewed push")
    moved = _source_hash_drift_since_dry_run(reviewed, status)
    if moved:
        labels = ", ".join(moved[:3])
        suffix = "..." if len(moved) > 3 else ""
        raise ValueError(f"Source changed since the stored dry-run for {labels}{suffix}; run Push dry-run again")
    result = run_agent_sync(["push", f"--env={env}", "--prompts-only", "--compare-reviewed"])
    refresh_ledger_after_reconcile(private_root=None)
    _mark_dry_run_used(review_token)
    return result


def import_live_draft(agent_id: str, prompt_id: str | None = None, *, private_root: Path | None = None) -> dict[str, Any]:
    status = get_status(private_root=private_root)
    row = next((item for item in status["agents"] if item.get("agentId") == agent_id), None)
    if not row:
        raise ValueError(f"Unknown managed agent id: {agent_id}")
    if not row.get("liveTextAvailable"):
        raise ValueError("Live instructions are unavailable; run pull-live/compare first")
    target_prompt_id = prompt_id or row.get("sourcePromptId") or "main.conscious_agent"
    live_text = LIVE_TEXT_CACHE.get(agent_id) or _live_text_from_latest_bundle(agent_id) or ""
    draft = create_import_live_draft(prompt_id=target_prompt_id, live_text=live_text, private_root=private_root)
    draft["agentId"] = agent_id
    return draft


def refresh_ledger_after_reconcile(*, private_root: Path | None = None) -> dict[str, Any]:
    status = get_status(private_root=private_root)
    records: dict[str, Any] = {}
    for row in status.get("agents") or []:
        records[row["agentId"]] = {
            "agentId": row["agentId"],
            "sourcePromptId": row.get("sourcePromptId"),
            "sourceCommit": status.get("sourceCommit"),
            "sourceHash": row.get("sourceHash"),
            "renderedHash": row.get("sourceHash"),
            "liveHash": row.get("liveHash"),
            "liveAgentVersion": row.get("liveAgentVersion"),
            "updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "evalRunIds": [],
        }
    ledger = {"version": 1, "records": records}
    path = ledger_path(private_root=private_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    path.chmod(0o600)
    return {
        "status": "updated",
        "recordCount": len(records),
        "ledgerAvailable": True,
        "ledgerName": path.name,
    }


def load_ledger(*, private_root: Path | None = None) -> dict[str, Any]:
    path = ledger_path(private_root=private_root)
    if not path.exists():
        return {"version": 1, "records": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"version": 1, "records": {}}


def ledger_path(*, private_root: Path | None = None) -> Path:
    root = private_root or workbench_private_root()
    return root / "sync-ledger.json"


def run_agent_sync(args: list[str]) -> dict[str, Any]:
    cmd = ["node", str(AGENT_SYNC_SCRIPT), *args]
    result = subprocess.run(
        cmd,
        cwd=LIBRECHAT_ROOT,
        text=True,
        capture_output=True,
        timeout=180,
        check=False,
        env={**os.environ},
    )
    parsed = _extract_json(result.stdout)
    return {
        "command": _safe_command(cmd),
        "returnCode": result.returncode,
        "stdoutTail": _sanitize_output(result.stdout[-6000:]),
        "stderrTail": _sanitize_output(result.stderr[-6000:]),
        "parsed": _sanitize_json(parsed),
    }


def load_latest_live_bundle() -> dict[str, Any] | None:
    runs_root = REPO_ROOT / ".viventium" / "artifacts" / "agents-sync" / "runs"
    if not runs_root.exists():
        return None
    candidates = sorted(runs_root.glob("*/viventium-agents.yaml"), key=lambda path: path.stat().st_mtime, reverse=True)
    for candidate in candidates:
        try:
            loaded = yaml.safe_load(candidate.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(loaded, dict):
            loaded["_artifactPath"] = str(candidate)
            return loaded
    return None


def _agent_rows(*, source: dict[str, Any], live: dict[str, Any] | None, ledger: dict[str, Any]) -> list[dict[str, Any]]:
    records = ledger.get("records") or {}
    rows: list[dict[str, Any]] = []

    main_source = source.get("mainAgent") or {}
    live_main = (live or {}).get("mainAgent") or {}
    rows.append(
        _row_for_agent(
            agent_id=str(main_source.get("id") or live_main.get("id") or ""),
            label=str(main_source.get("name") or live_main.get("name") or "Viventium"),
            source_prompt_id="main.conscious_agent",
            source_instructions=str(main_source.get("instructions") or ""),
            live_instructions=str(live_main.get("instructions") or ""),
            live_version=live_main.get("version") or live_main.get("__v"),
            records=records,
        )
    )

    source_agents = {
        str(agent.get("id") or agent.get("agent_id")): agent
        for agent in _background_agents(source)
    }
    live_agents = {
        str(agent.get("id") or agent.get("agent_id")): agent
        for agent in _background_agents(live or {})
    }
    for agent_id in sorted(set(source_agents) | set(live_agents)):
        if not agent_id or agent_id == "None":
            continue
        source_agent = source_agents.get(agent_id) or {}
        live_agent = live_agents.get(agent_id) or {}
        prompt_id = _source_prompt_id_for_background_agent(agent_id, source_agent)
        rows.append(
            _row_for_agent(
                agent_id=agent_id,
                label=str(source_agent.get("name") or live_agent.get("name") or agent_id),
                source_prompt_id=prompt_id,
                source_instructions=str(source_agent.get("instructions") or ""),
                live_instructions=str(live_agent.get("instructions") or ""),
                live_version=live_agent.get("version") or live_agent.get("__v"),
                records=records,
            )
        )
    return rows


def _background_agents(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """Read the canonical source shape while retaining legacy artifact compatibility."""

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for key in ("backgroundAgents", "agents"):
        for candidate in bundle.get(key) or []:
            if not isinstance(candidate, dict):
                continue
            agent_id = str(candidate.get("id") or candidate.get("agent_id") or "")
            if not agent_id or agent_id in seen:
                continue
            seen.add(agent_id)
            rows.append(candidate)
    return rows


def _row_for_agent(
    *,
    agent_id: str,
    label: str,
    source_prompt_id: str | None,
    source_instructions: str,
    live_instructions: str,
    live_version: Any,
    records: dict[str, Any],
) -> dict[str, Any]:
    source_hash = _sha(source_instructions)
    live_hash = _sha(live_instructions) if live_instructions else None
    if agent_id and live_instructions:
        LIVE_TEXT_CACHE[agent_id] = live_instructions
    state = classify_sync_state(
        source_hash=source_hash,
        live_hash=live_hash,
        ledger_record=records.get(agent_id),
    )
    return {
        "agentId": agent_id,
        "label": label,
        "sourcePromptId": source_prompt_id,
        "sourceHash": source_hash,
        "liveHash": live_hash,
        "state": state,
        "liveAgentVersion": live_version,
        "sourceChars": len(source_instructions),
        "liveChars": len(live_instructions),
        "liveTextAvailable": bool(live_instructions),
    }


def _source_prompt_id_for_background_agent(
    agent_id: str, agent: dict[str, Any]
) -> str | None:
    from scripts.viventium.prompt_registry import load_prompt_registry, render_prompt

    try:
        registry = load_prompt_registry()
    except Exception:
        return None

    target_candidates = {
        f"backgroundAgents.{agent_id}.instructions",
        f"agents.{agent_id}.instructions",
    }
    for prompt_id, entry in registry.items():
        if str(entry.metadata.get("target") or "") in target_candidates:
            return prompt_id

    instructions = agent.get("instructions")
    if not isinstance(instructions, str) or not instructions.strip():
        return None
    try:
        normalized = instructions.strip()
        for prompt_id in sorted(registry):
            try:
                rendered = render_prompt(prompt_id, registry).strip()
            except Exception:
                continue
            if rendered == normalized:
                return prompt_id
    except Exception:
        pass
    return None


def _live_text_from_latest_bundle(agent_id: str) -> str | None:
    live = load_latest_live_bundle()
    if not live:
        return None
    main = live.get("mainAgent") or {}
    if str(main.get("id") or "") == agent_id:
        return str(main.get("instructions") or "")
    for agent in _background_agents(live):
        if str(agent.get("id") or agent.get("agent_id") or "") == agent_id:
            return str(agent.get("instructions") or "")
    return None


def _sha(value: str, length: int = 16) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short=12", "HEAD"],
            cwd=REPO_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=10,
        ).strip()
    except Exception:
        return "unknown"


def _extract_json(stdout: str) -> Any:
    text = _strip_ansi(stdout)
    for start in reversed([match.start() for match in re.finditer(r"[\[{]", text)]):
        candidate = text[start:].strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)


def _redact_private_paths(text: str, private_paths: tuple[Path, ...] = ()) -> str:
    values = {str(Path.home()), str(workbench_private_root())}
    values.update(str(Path(path).expanduser().resolve(strict=False)) for path in private_paths)
    for value in sorted((item for item in values if item), key=len, reverse=True):
        text = text.replace(value, "<private>")
    return text


def _sanitize_output(text: str, *, private_paths: tuple[Path, ...] = ()) -> str:
    from scripts.viventium.prompt_registry import PRIVATE_PATTERN_RULES

    text = re.sub(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", "<email>", text, flags=re.I)
    text = re.sub(r'("userId"\s*:\s*")[0-9a-f]{12,32}(")', r'\1<user-id>\2', text, flags=re.I)
    for label, pattern in PRIVATE_PATTERN_RULES:
        text = pattern.sub(f"<{label}>", text)
    return _redact_private_paths(text, private_paths)


def _sanitize_json(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            if key in {"instructions"}:
                continue
            if key in {"userId", "_id", "conversationId", "messageId"}:
                sanitized[key] = f"<{key}>"
                continue
            sanitized[key] = _sanitize_json(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_json(item) for item in value]
    if isinstance(value, str):
        return _sanitize_output(value)
    return value


def _safe_command(
    cmd: list[str], *, private_paths: tuple[Path, ...] = ()
) -> list[str]:
    return [_redact_private_paths(item, private_paths) for item in cmd]


def _review_token(result: dict[str, Any]) -> str:
    payload = json.dumps(result.get("parsed") or result.get("stdoutTail") or "", sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def _dry_runs_dir() -> Path:
    path = workbench_private_root() / "dry-runs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _persist_dry_run(result: dict[str, Any], *, source_hashes: dict[str, str] | None = None) -> None:
    token = str(result["reviewToken"])
    record = {
        "token": token,
        "createdAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "used": False,
        "sourceHashes": source_hashes or {},
        "result": result,
    }
    path = _dry_runs_dir() / f"{token}.json"
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    path.chmod(0o600)


def _load_dry_run_by_token(review_token: str) -> dict[str, Any] | None:
    path = _dry_runs_dir() / f"{review_token}.json"
    if not path.exists():
        return None
    record = json.loads(path.read_text(encoding="utf-8"))
    if record.get("used"):
        return None
    return record


def _mark_dry_run_used(review_token: str) -> None:
    path = _dry_runs_dir() / f"{review_token}.json"
    if not path.exists():
        return
    record = json.loads(path.read_text(encoding="utf-8"))
    record["used"] = True
    record["usedAt"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    path.chmod(0o600)


def _source_hash_snapshot(status: dict[str, Any]) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for row in status.get("agents") or []:
        agent_id = str(row.get("agentId") or "")
        source_hash = str(row.get("sourceHash") or "")
        if agent_id and source_hash:
            snapshot[agent_id] = source_hash
    return snapshot


def _source_hash_drift_since_dry_run(reviewed: dict[str, Any], status: dict[str, Any]) -> list[str]:
    expected = reviewed.get("sourceHashes") or {}
    if not isinstance(expected, dict) or not expected:
        return []
    current = _source_hash_snapshot(status)
    moved: list[str] = []
    labels_by_agent = {
        str(row.get("agentId") or ""): str(row.get("label") or row.get("agentId") or "")
        for row in status.get("agents") or []
    }
    for agent_id, source_hash in expected.items():
        if current.get(str(agent_id)) != source_hash:
            moved.append(labels_by_agent.get(str(agent_id)) or str(agent_id))
    return moved

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .paths import AGENTS_SOURCE_PATH, LIBRECHAT_ROOT, LIBRECHAT_SOURCE_PATH, PROMPTS_ROOT, REPO_ROOT

from scripts.viventium.prompt_registry import load_and_resolve_prompt_refs
from scheduling_cortex.dispatch import dispatch_task
from scheduling_cortex.scheduler import compute_next_run
from scheduling_cortex.storage import ScheduleStorage, StorageConfig
from scheduling_cortex.utils import to_utc_iso


PLACEHOLDER_RE = re.compile(r"{{\s*([^{}]+?)\s*}}")
BACKGROUND_AGENTS_FUNCTION = "viventium.background_agents.get_list(agent_name, system_prompt)"
NIGHTLY_TEMPLATE_ID = "workbench_nightly_subconscious_thought_formation_v1"
NIGHTLY_MISFIRE_POLICY = {"mode": "catch_up", "max_late_s": 12 * 60 * 60}
MEMORY_WRITE_MODES = {"off", "propose", "apply_governed"}
EXECUTORS = {"glasshive_host", "viventium_agent"}
GLASSHIVE_WORKER_STRATEGIES = {"same_worker", "new_worker_each_run"}
USER_SCHEDULE_PREFIX = "user_schedule:"
PERIPHERY_REQUIRED_FIELDS = (
    "schemaVersion",
    "moduleId",
    "generatedAt",
    "scheduledRunRef",
    "sourceRefs",
    "confidence",
    "severity",
    "timeSensitivity",
    "ttl",
    "staleAfter",
    "observations",
    "risks",
    "blindSpots",
    "opportunityCosts",
    "opportunities",
    "whatWouldMakeThisWrong",
    "whenToSurface",
    "proposedActions",
    "memoryProposalRefs",
)
PERIPHERY_CONTENT_FIELDS = (
    "observations",
    "risks",
    "blindSpots",
    "opportunityCosts",
    "opportunities",
    "whatWouldMakeThisWrong",
    "whenToSurface",
    "proposedActions",
    "memoryProposalRefs",
)
_MANUAL_RUN_LOCKS: dict[str, threading.Lock] = {}
_MANUAL_RUN_LOCKS_GUARD = threading.Lock()

NIGHTLY_PROMPT_TEMPLATE = """study {{user}} memories from the perspective of each of the Viventium Background agent's and update your scratchpad in case you come up with thoughts, realizations, ideas, plans, anything you think is worth jotting down and concluding.

You may follow {{memory_agent.system_prompt}} and prepare governed memory proposals for {{user.memories}} to help Viventium's brain naturally become aware of anything important. Do not directly edit MongoDB or memory database tables. If this scheduled prompt is configured for apply_governed memory mode, route memory changes only through Viventium/LibreChat governed memory methods and policy.

You may also just use your own personal / private scratchpad as yyyymmddHHmm.md file in {{local.viventium.my_folder}}

Private periphery artifact: write one risk_radar artifact for this run. Use the folder shown in {{local.viventium.my_folder}} and write paired .md and .json files under:
periphery/risk_radar/YYYY/MM/YYYYMMDDTHHMMSSZ.risk_radar.md
periphery/risk_radar/YYYY/MM/YYYYMMDDTHHMMSSZ.risk_radar.json

The JSON sidecar must include: schemaVersion, moduleId, generatedAt, scheduledRunRef, sourceRefs, confidence, severity, timeSensitivity, ttl, staleAfter, observations, risks, blindSpots, opportunityCosts, opportunities, whatWouldMakeThisWrong, whenToSurface, proposedActions, memoryProposalRefs.
Use moduleId "risk_radar". Keep it concise and evidence-first; mark hypotheses as hypotheses and unsupported thoughts as unsupported. If there is no strong evidence, write a short no-result artifact with empty arrays and one observation explaining the low signal or missing prerequisite. Do not add a saved-memory key for periphery, do not inject this artifact into the main chat prompt, and do not copy raw private conversations into the sidecar.


# user = {{user}}
# you can access this user's recent conversations, account memories, schedules, etc all on the local viventium db = {{local.viventium.database}}
# memories = {{user.memories}}
# Viventium Background Cortices / agents instructions to analyze based off: {{viventium.background_agents.get_list(agent_name, system_prompt)}}
"""


def _sha(value: str, length: int = 16) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def _private_rendered_marker(rendered_hash: str) -> str:
    return f"<private-rendered-prompt hash=\"{rendered_hash}\" />"


def _private_snapshot_marker(snapshot_hash: str) -> str:
    return json.dumps(
        {
            "kind": "private-variable-snapshot",
            "hash": snapshot_hash,
            "privateDetail": f"private://scheduled-prompt-variable-snapshot/{snapshot_hash}",
        },
        sort_keys=True,
    )


def _utc_now() -> str:
    return to_utc_iso(datetime.now(timezone.utc))


def _scheduling_db_path() -> str:
    return os.getenv(
        "SCHEDULING_DB_PATH",
        str(Path.home() / "Library" / "Application Support" / "Viventium" / "state" / "runtime" / "isolated" / "scheduling" / "schedules.db"),
    )


def storage() -> ScheduleStorage:
    db_path = _scheduling_db_path()
    os.environ.setdefault("SCHEDULING_DB_PATH", db_path)
    mirror_path = os.getenv("SCHEDULING_DB_MIRROR_PATH")
    return ScheduleStorage(StorageConfig(db_path=db_path, mirror_db_path=mirror_path))


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except OSError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _memory_agent_system_prompt() -> str:
    config = _load_yaml(LIBRECHAT_SOURCE_PATH)
    memory = config.get("memory") if isinstance(config.get("memory"), dict) else {}
    agent = memory.get("agent") if isinstance(memory.get("agent"), dict) else {}
    instructions = agent.get("instructions")
    return str(instructions or "").strip()


def _background_agents() -> list[dict[str, Any]]:
    config = _load_yaml(AGENTS_SOURCE_PATH)
    agents = config.get("backgroundAgents")
    if not isinstance(agents, list):
        return []
    rows: list[dict[str, Any]] = []
    for agent in agents:
        if not isinstance(agent, dict):
            continue
        name = str(agent.get("name") or agent.get("id") or "Background Agent").strip()
        instructions_value = agent.get("instructions")
        try:
            resolved = load_and_resolve_prompt_refs(instructions_value, PROMPTS_ROOT)
        except Exception:
            resolved = instructions_value
        rows.append({"agent_name": name, "system_prompt": str(resolved or "").strip()})
    return rows


def _query_mongo_json(script: str) -> Any:
    port = os.getenv("VIVENTIUM_MONGO_PORT") or os.getenv("MONGO_PORT") or "27117"
    db_name = os.getenv("MONGO_DB_NAME") or os.getenv("MONGO_DB") or "LibreChatViventium"
    cmd = ["mongosh", "--quiet", f"mongodb://127.0.0.1:{port}/{db_name}", "--eval", script]
    try:
        completed = subprocess.run(cmd, text=True, capture_output=True, timeout=8, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    text = completed.stdout.strip()
    if not text:
        return None
    try:
        return json.loads(text.splitlines()[-1])
    except json.JSONDecodeError:
        return None


def _user_context(user_id: str, email: str | None = None) -> dict[str, Any]:
    script = (
        "const userId = " + json.dumps(str(user_id or "")) + ";"
        "const email = " + json.dumps(str(email or "")) + ";"
        "let selector = null;"
        "if (email) { selector = {email}; }"
        "else if (userId && !['local-admin','test-admin'].includes(userId)) {"
        "  selector = ObjectId.isValid(userId) ? {_id:ObjectId(userId)} : {_id:userId};"
        "}"
        "const user = selector ? db.users.findOne(selector) : null;"
        "if (!user) { print(JSON.stringify(null)); } else {"
        "const prefs = user.personalization || {};"
        "print(JSON.stringify({_id:String(user._id), email:user.email||'', name:user.name||'', role:user.role||'', memories:user.memories!==false && prefs.memories!==false}));"
        "}"
    )
    result = _query_mongo_json(script)
    if isinstance(result, dict):
        return result
    return {
        "_id": user_id or "local-user",
        "email": email or "",
        "role": "unresolved",
        "memories": "unresolved",
        "resolutionStatus": "mongo_unavailable",
    }


def _user_memories(user_id: str, email: str | None = None) -> list[dict[str, Any]]:
    user = _user_context(user_id, email)
    if user.get("resolutionStatus"):
        return [
            {
                "resolutionStatus": user.get("resolutionStatus"),
                "message": "User memory lookup unavailable because the local user snapshot could not be resolved.",
            }
        ]
    user_id_value = user.get("_id")
    if not user_id_value:
        return []
    script = (
        "const userId = " + json.dumps(str(user_id_value)) + ";"
        "const objectId = ObjectId.isValid(userId) ? ObjectId(userId) : null;"
        "const query = objectId ? {$or:[{userId:objectId},{userId:userId},{user:userId}]} : {$or:[{userId:userId},{user:userId}]};"
        "const rows = db.memoryentries.find(query, {_id:1,key:1,value:1,text:1,type:1,tokenCount:1,updatedAt:1,updated_at:1}).sort({updated_at:-1,updatedAt:-1}).limit(100).toArray();"
        "print(JSON.stringify(rows.map(r => ({key:r.key||r.type||'', value:r.value||r.text||'', tokenCount:r.tokenCount||null, updatedAt:r.updatedAt||r.updated_at||null}))));"
    )
    result = _query_mongo_json(script)
    return result if isinstance(result, list) else [{"resolutionStatus": "mongo_unavailable", "message": "Memory lookup unavailable in this local context."}]


def _memory_write_mode(value: Any) -> str:
    mode = str(value or "off").strip()
    if mode not in MEMORY_WRITE_MODES:
        raise ValueError(f"memoryWriteMode must be one of: {', '.join(sorted(MEMORY_WRITE_MODES))}")
    return mode


def _executor(value: Any) -> str:
    executor = str(value or "glasshive_host").strip()
    if executor not in EXECUTORS:
        raise ValueError(f"executor must be one of: {', '.join(sorted(EXECUTORS))}")
    return executor


def _default_glasshive_worker_profile() -> str:
    return (os.getenv("GLASSHIVE_DEFAULT_WORKER_PROFILE") or "codex-cli").strip() or "codex-cli"


def _worker_strategy(value: Any) -> str:
    strategy = str(value or "same_worker").strip()
    if strategy not in GLASSHIVE_WORKER_STRATEGIES:
        raise ValueError(
            f"glasshiveWorkerStrategy must be one of: {', '.join(sorted(GLASSHIVE_WORKER_STRATEGIES))}"
        )
    return strategy


def _conversation_policy(value: Any) -> str:
    policy = str(value or "new").strip()
    if policy not in {"new", "same"}:
        raise ValueError("conversationPolicy must be either new or same")
    return policy


def _channel_for_executor(executor: str, value: Any) -> Any:
    if executor == "glasshive_host":
        return "workbench"
    if isinstance(value, list):
        cleaned = [str(item).strip() for item in value if str(item or "").strip()]
        return cleaned or "librechat"
    channel = str(value or "librechat").strip()
    return channel or "librechat"


def _database_context() -> dict[str, Any]:
    return {
        "kind": "viventium-local-context",
        "access_policy": "server-side snapshots only; GlassHive workers must not receive raw Mongo credentials",
        "database_name": os.getenv("MONGO_DB_NAME") or "LibreChatViventium",
        "collections": ["users", "conversations", "messages", "memoryentries", "scheduled_tasks"],
        "memory_writeback": "Use governed LibreChat/Viventium memory methods or write proposals; never direct-write memory collections.",
    }


def _glasshive_my_folder(user_id: str) -> str:
    base = Path(
        os.getenv("VIVENTIUM_LOCAL_MACHINE_GLASSHIVE_ROOT")
        or (Path.home() / "viventium" / "local_machine_glasshive")
    ).expanduser()
    safe_user = re.sub(r"[^A-Za-z0-9_.-]+", "-", user_id or "local-user").strip("-") or "local-user"
    path = base / safe_user / "my_folder"
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def variable_registry() -> dict[str, Any]:
    variables = [
        {"name": "user", "kind": "object", "wrapper": "user", "description": "Current Viventium user profile snapshot."},
        {"name": "user.memories", "kind": "json", "wrapper": "user.memories", "description": "Current user memory snapshot, resolved server-side."},
        {"name": "memory_agent.system_prompt", "kind": "markdown", "wrapper": "memory_agent.system_prompt", "description": "LibreChat memory agent rules from local.librechat.yaml."},
        {"name": "local.viventium.database", "kind": "json", "wrapper": "local.viventium.database", "description": "Governed local database context without credentials."},
        {"name": "local.viventium.local_machine_glasshive.my_folder", "kind": "path", "wrapper": "local.viventium.local_machine_glasshive.my_folder", "description": "Private GlassHive continuity folder for this user."},
        {"name": "local.viventium.my_folder", "kind": "path", "wrapper": "local.viventium.my_folder", "description": "Alias for the GlassHive private continuity folder."},
    ]
    functions = [
        {
            "name": BACKGROUND_AGENTS_FUNCTION,
            "kind": "function",
            "wrapper": "viventium.background_agents.get_list",
            "description": "Allowlisted resolver for background agent names and system prompts.",
            "arguments": ["agent_name", "system_prompt"],
        }
    ]
    return {"variables": variables, "functions": functions}


def nightly_prompt_template() -> dict[str, Any]:
    default_timezone = (
        os.getenv("VIVENTIUM_DEFAULT_TIMEZONE")
        or os.getenv("TZ")
        or "America/Toronto"
    )
    return {
        "id": NIGHTLY_TEMPLATE_ID,
        "title": "Subconscious Deep Thought",
        "subtitle": "Nightly subconscious thought formation",
        "promptText": NIGHTLY_PROMPT_TEMPLATE,
        "schedule": {"type": "daily", "time": "03:00", "timezone": default_timezone},
        "active": False,
        "memoryWriteMode": "propose",
    }


def _should_reconcile_builtin_nightly_schedule(current: Any, desired: dict[str, Any]) -> bool:
    if not isinstance(current, dict):
        return True
    if current == desired:
        return False
    return current.get("type") == "daily" and current.get("time") == "03:00"


def _format_value(value: Any, kind: str) -> str:
    if kind == "json" or isinstance(value, (dict, list)):
        return json.dumps(value, indent=2, sort_keys=True)
    return str(value)


def _wrap(name: str, value: Any, kind: str) -> str:
    tag = name.split("(")[0]
    body = _format_value(value, kind)
    return f"<{tag}>\n{body}\n</{tag}>"


def _resolve_placeholder(name: str, user_id: str, email: str | None = None) -> tuple[Any, str, str]:
    key = name.strip()
    if key == "user":
        return _user_context(user_id, email), "json", "user"
    if key == "user.memories":
        return _user_memories(user_id, email), "json", "user.memories"
    if key == "memory_agent.system_prompt":
        return _memory_agent_system_prompt(), "markdown", "memory_agent.system_prompt"
    if key == "local.viventium.database":
        return _database_context(), "json", "local.viventium.database"
    if key in {"local.viventium.local_machine_glasshive.my_folder", "local.viventium.my_folder"}:
        return _glasshive_my_folder(user_id), "path", key
    if key == BACKGROUND_AGENTS_FUNCTION:
        return _background_agents(), "json", "viventium.background_agents.get_list"
    raise ValueError(f"Unsupported scheduled prompt variable: {key}")


def render_variables(prompt_text: str, *, user_id: str, email: str | None = None) -> dict[str, Any]:
    snapshots: list[dict[str, Any]] = []

    def replace(match: re.Match[str]) -> str:
        name = match.group(1).strip()
        value, kind, wrapper = _resolve_placeholder(name, user_id, email)
        rendered = _wrap(wrapper, value, kind)
        snapshots.append(
            {
                "placeholder": name,
                "wrapper": wrapper,
                "kind": kind,
                "hash": _sha(_format_value(value, kind)),
                "value": value,
                "rendered": rendered,
            }
        )
        return rendered

    rendered = PLACEHOLDER_RE.sub(replace, prompt_text)
    snapshot = {"resolvedAt": _utc_now(), "userId": user_id, "items": snapshots}
    snapshot_json = json.dumps(snapshot, indent=2, sort_keys=True)
    return {
        "rendered": rendered,
        "renderedHash": _sha(rendered),
        "variableSnapshot": snapshot,
        "variableSnapshotJson": snapshot_json,
        "variableSnapshotHash": _sha(snapshot_json),
    }


def _schedule_next(schedule: dict[str, Any]) -> str | None:
    next_run = compute_next_run(schedule, datetime.now(timezone.utc), None)
    return to_utc_iso(next_run) if next_run else None


def _version_number(definition_id: str) -> int:
    latest = storage().latest_scheduled_prompt_version(definition_id)
    return int((latest or {}).get("version_number") or 0) + 1


def _workspace_alias(definition_id: str) -> str:
    return f"workbench-scheduled-{definition_id[:12]}"


def _workspace_root() -> str:
    return os.getenv("WPR_HOST_WORKSPACE_ROOT") or str(REPO_ROOT)


def _task_metadata(definition: dict[str, Any], version: dict[str, Any], render_payload: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(definition.get("metadata") or {})
    execution = metadata.get("execution") if isinstance(metadata.get("execution"), dict) else {}
    executor = str(execution.get("executor") or "glasshive_host")
    worker_strategy = str(execution.get("glasshive_worker_strategy") or "same_worker")
    metadata["workbench_scheduled_prompt"] = {
        "definition_id": definition["id"],
        "version_id": version["id"],
        "title": definition["title"],
        "template_id": definition.get("template_id"),
        "source_prompt_id": definition.get("source_prompt_id"),
        "rendered_hash": render_payload["renderedHash"],
        "variable_snapshot_hash": render_payload["variableSnapshotHash"],
        "variable_snapshot_pointer": f"private://scheduled-prompt-variable-snapshot/{render_payload['variableSnapshotHash']}",
        "memory_write_mode": definition.get("memory_write_mode") or "off",
        "workspace_alias": definition.get("workspace_alias") or _workspace_alias(definition["id"]),
        "workspace_root": _workspace_root(),
        "my_folder": definition.get("my_folder") or _glasshive_my_folder(definition["user_id"]),
        "executor": executor,
        "glasshive_worker_strategy": worker_strategy,
        "execution_profile": str(execution.get("execution_profile") or _default_glasshive_worker_profile()),
        "execution_mode": str(execution.get("execution_mode") or "host"),
    }
    if definition.get("template_id") == NIGHTLY_TEMPLATE_ID:
        metadata["misfire_policy"] = dict(NIGHTLY_MISFIRE_POLICY)
    return metadata


def _ensure_builtin_nightly_task_policy(row: dict[str, Any]) -> None:
    if row.get("template_id") != NIGHTLY_TEMPLATE_ID or not row.get("task_id"):
        return
    store = storage()
    task = store.get_task(str(row["user_id"]), str(row["task_id"]))
    if not task:
        return
    metadata = task.get("metadata") if isinstance(task.get("metadata"), dict) else {}
    if metadata.get("misfire_policy") == NIGHTLY_MISFIRE_POLICY:
        return
    patched_metadata = dict(metadata)
    patched_metadata["misfire_policy"] = dict(NIGHTLY_MISFIRE_POLICY)
    store.update_task(
        str(row["user_id"]),
        str(row["task_id"]),
        {
            "metadata": patched_metadata,
            "updated_at": _utc_now(),
            "updated_by": "agent:prompt-workbench",
            "updated_source": "startup-reconcile",
        },
    )


def _user_schedule_id(task_id: str) -> str:
    return f"{USER_SCHEDULE_PREFIX}{task_id}"


def _is_user_schedule_id(value: str) -> bool:
    return value.startswith(USER_SCHEDULE_PREFIX)


def _task_id_from_user_schedule_id(value: str) -> str:
    return value.removeprefix(USER_SCHEDULE_PREFIX)


def _title_from_task(task: dict[str, Any]) -> str:
    metadata = task.get("metadata") if isinstance(task.get("metadata"), dict) else {}
    for key in ("workbench_title", "title", "template_id"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    prompt = re.sub(r"\s+", " ", str(task.get("prompt") or "")).strip()
    if not prompt:
        return "User-level scheduled prompt"
    return prompt[:72] + ("..." if len(prompt) > 72 else "")


def _task_run_summary(task: dict[str, Any]) -> str:
    outcome = str(task.get("last_delivery_outcome") or "").strip()
    reason = str(task.get("last_delivery_reason") or "").strip()
    if outcome and reason:
        return _safe_summary(f"{outcome}: {reason}")
    if outcome:
        return _safe_summary(outcome)
    if reason:
        return _safe_summary(reason)
    status = str(task.get("last_status") or "").strip()
    return _safe_summary(status) if status else ""


def _safe_summary(value: str, *, limit: int = 220) -> str:
    text = re.sub(r"\s+", " ", value or "").strip()
    text = re.sub(r"mongodb(?:\+srv)?:\/\/[^\s`'\"<>]+", "<mongo-uri>", text, flags=re.I)
    text = re.sub(r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}", "Bearer <redacted>", text, flags=re.I)
    text = re.sub(r"https?:\/\/[^\s`'\"<>)]*", "<url>", text, flags=re.I)
    text = re.sub(r"(?:/Users|/home|/private/var|/var/folders)/[^\s`'\"<>]+", "<local-path>", text)
    return text[:limit] + ("..." if len(text) > limit else "")


def _private_detail_pointer(path_value: Any) -> str | None:
    path = str(path_value or "").strip()
    if not path:
        return None
    return f"private://scheduled-prompt-run/{_sha(path, length=24)}"


def _manual_run_lock(key: str) -> threading.Lock:
    with _MANUAL_RUN_LOCKS_GUARD:
        lock = _MANUAL_RUN_LOCKS.get(key)
        if not lock:
            lock = threading.Lock()
            _MANUAL_RUN_LOCKS[key] = lock
        return lock


def _is_recent_manual_task_run(task: dict[str, Any], *, seconds: int = 30) -> bool:
    value = str(task.get("last_run_at") or "").strip()
    if not value:
        return False
    try:
        run_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return (datetime.now(timezone.utc) - run_at).total_seconds() < seconds


def _public_task_run(task: dict[str, Any]) -> dict[str, Any] | None:
    status = str(task.get("last_status") or "").strip()
    if not status:
        return None
    run_time = task.get("last_run_at") or task.get("last_delivery_at") or task.get("updated_at")
    return {
        "runId": f"task-run:{task.get('id')}:{run_time or ''}",
        "taskId": task.get("id"),
        "definitionId": None,
        "versionId": None,
        "dueAt": task.get("next_run_at"),
        "startedAt": task.get("last_run_at"),
        "completedAt": task.get("last_delivery_at"),
        "status": status,
        "executor": task.get("executor") or "viventium_agent",
        "renderedHash": None,
        "variableSnapshotHash": None,
        "glasshiveProjectId": None,
        "glasshiveWorkerId": None,
        "glasshiveRunId": None,
        "resultSummary": _task_run_summary(task),
        "errorClass": _safe_summary(str(task.get("last_error") or "")) if status in {"error", "failed"} else None,
        "privateDetailPointer": None,
        "updatedAt": task.get("updated_at"),
    }


def _public_task_schedule(task: dict[str, Any]) -> dict[str, Any]:
    schedule = task.get("schedule") if isinstance(task.get("schedule"), dict) else {}
    recent_run = _public_task_run(task)
    return {
        "id": _user_schedule_id(str(task.get("id") or "")),
        "taskId": task.get("id"),
        "userId": task.get("user_id"),
        "title": _title_from_task(task),
        "sourcePromptId": None,
        "templateId": None,
        "promptText": task.get("prompt") or "",
        "schedule": schedule,
        "timezone": schedule.get("timezone"),
        "active": bool(task.get("active")),
        "channel": task.get("channel"),
        "executor": task.get("executor") or "viventium_agent",
        "conversationPolicy": task.get("conversation_policy") or "new",
        "memoryWriteMode": "off",
        "myFolder": None,
        "workspaceRoot": None,
        "workspaceAlias": None,
        "executionProfile": None,
        "executionMode": None,
        "glasshiveWorkerStrategy": None,
        "nextRunAt": task.get("next_run_at"),
        "lastStatus": task.get("last_status"),
        "latestVersion": None,
        "recentRuns": [recent_run] if recent_run else [],
        "sourceKind": "user_schedule",
        "sourceLabel": "User-level schedule",
        "createdAt": task.get("created_at"),
        "updatedAt": task.get("updated_at"),
    }


def _public_definition(definition: dict[str, Any]) -> dict[str, Any]:
    task = storage().get_task(definition["user_id"], definition["task_id"]) if definition.get("task_id") else None
    version = storage().latest_scheduled_prompt_version(definition["id"])
    runs = storage().list_scheduled_prompt_runs(definition_id=definition["id"], limit=5)
    task_metadata = (task or {}).get("metadata") if isinstance((task or {}).get("metadata"), dict) else {}
    workbench_metadata = task_metadata.get("workbench_scheduled_prompt") if isinstance(task_metadata.get("workbench_scheduled_prompt"), dict) else {}
    definition_metadata = definition.get("metadata") if isinstance(definition.get("metadata"), dict) else {}
    execution = definition_metadata.get("execution") if isinstance(definition_metadata.get("execution"), dict) else {}
    executor = (task or {}).get("executor") or execution.get("executor") or "glasshive_host"
    return {
        "id": definition["id"],
        "taskId": definition.get("task_id"),
        "userId": definition.get("user_id"),
        "title": definition.get("title"),
        "sourcePromptId": definition.get("source_prompt_id"),
        "templateId": definition.get("template_id"),
        "promptText": definition.get("prompt_text"),
        "schedule": definition.get("schedule"),
        "timezone": definition.get("timezone"),
        "active": bool(definition.get("active")),
        "channel": (task or {}).get("channel") or execution.get("channel"),
        "executor": executor,
        "conversationPolicy": (task or {}).get("conversation_policy") or execution.get("conversation_policy") or "new",
        "memoryWriteMode": definition.get("memory_write_mode"),
        "myFolder": definition.get("my_folder"),
        "workspaceRoot": workbench_metadata.get("workspace_root") or execution.get("workspace_root") or _workspace_root(),
        "workspaceAlias": definition.get("workspace_alias") or workbench_metadata.get("workspace_alias"),
        "executionProfile": workbench_metadata.get("execution_profile") or execution.get("execution_profile") or (_default_glasshive_worker_profile() if executor == "glasshive_host" else "main Viventium"),
        "executionMode": workbench_metadata.get("execution_mode") or execution.get("execution_mode") or ("host" if executor == "glasshive_host" else "scheduler delivery"),
        "glasshiveWorkerStrategy": workbench_metadata.get("glasshive_worker_strategy") or execution.get("glasshive_worker_strategy") or "same_worker",
        "nextRunAt": (task or {}).get("next_run_at"),
        "lastStatus": (task or {}).get("last_status"),
        "latestVersion": _public_version(version) if version else None,
        "recentRuns": [_public_run(run) for run in runs],
        "sourceKind": "workbench_definition",
        "sourceLabel": "Workbench private prompt",
        "createdAt": definition.get("created_at"),
        "updatedAt": definition.get("updated_at"),
    }


def _public_version(version: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": version.get("id"),
        "versionNumber": version.get("version_number"),
        "renderedHash": version.get("rendered_hash"),
        "variableSnapshotHash": version.get("variable_snapshot_hash"),
        "createdAt": version.get("created_at"),
    }


def _public_run(run: dict[str, Any]) -> dict[str, Any]:
    return {
        "runId": run.get("run_id"),
        "taskId": run.get("task_id"),
        "definitionId": run.get("definition_id"),
        "versionId": run.get("version_id"),
        "dueAt": run.get("due_at"),
        "startedAt": run.get("started_at"),
        "completedAt": run.get("completed_at"),
        "status": run.get("status"),
        "executor": run.get("executor"),
        "renderedHash": run.get("rendered_hash"),
        "variableSnapshotHash": run.get("variable_snapshot_hash"),
        "glasshiveProjectId": run.get("glasshive_project_id"),
        "glasshiveWorkerId": run.get("glasshive_worker_id"),
        "glasshiveRunId": run.get("glasshive_run_id"),
        "resultSummary": _safe_summary(str(run.get("result_summary") or "")),
        "errorClass": run.get("error_class"),
        "privateDetailPointer": _private_detail_pointer(run.get("private_detail_path")),
        "updatedAt": run.get("updated_at"),
    }


def _is_inflight_run(run: dict[str, Any] | None) -> bool:
    if not run:
        return False
    return str(run.get("status") or "").strip() in {"dispatching", "queued", "running"}


def _is_recent_scheduled_prompt_run(run: dict[str, Any] | None, *, seconds: int = 30) -> bool:
    if not run:
        return False
    value = str(run.get("started_at") or run.get("created_at") or "").strip()
    if not value:
        return False
    try:
        run_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return (datetime.now(timezone.utc) - run_at).total_seconds() < seconds


def _coalesced_manual_run_response(run: dict[str, Any]) -> dict[str, Any]:
    return {
        "coalesced": True,
        "dispatch": {
            "delivery": {
                "outcome": "queued",
                "reason": "manual_run_already_inflight",
                "generated_text": None,
            }
        },
        "run": _public_run(run),
    }


def list_scheduled_prompts(user_id: str | None = None) -> dict[str, Any]:
    store = storage()
    rows = store.list_scheduled_prompt_definitions(user_id=user_id)
    definition_task_ids = {str(row.get("task_id")) for row in rows if row.get("task_id")}
    public_rows = [_public_definition(row) for row in rows]
    if user_id:
        for task in store.list_tasks(user_id=user_id, limit=200):
            if str(task.get("id")) in definition_task_ids:
                continue
            public_rows.append(_public_task_schedule(task))
    public_rows.sort(key=lambda row: str(row.get("updatedAt") or row.get("createdAt") or ""), reverse=True)
    return {"scheduledPrompts": public_rows}


def create_scheduled_prompt(payload: dict[str, Any], *, user_id: str, email: str | None = None) -> dict[str, Any]:
    now = _utc_now()
    definition_id = f"sp_{uuid.uuid4().hex}"
    schedule = payload.get("schedule") if isinstance(payload.get("schedule"), dict) else {"type": "daily", "time": "03:00", "timezone": payload.get("timezone") or "UTC"}
    timezone_name = str(schedule.get("timezone") or payload.get("timezone") or "UTC")
    prompt_text = str(payload.get("promptText") or payload.get("prompt") or NIGHTLY_PROMPT_TEMPLATE).strip() + "\n"
    title = str(payload.get("title") or "Scheduled prompt").strip()
    my_folder = _glasshive_my_folder(user_id)
    executor = _executor(payload.get("executor"))
    channel = _channel_for_executor(executor, payload.get("channel"))
    conversation_policy = _conversation_policy(payload.get("conversationPolicy") or payload.get("conversation_policy"))
    worker_strategy = _worker_strategy(payload.get("glasshiveWorkerStrategy") or payload.get("glasshive_worker_strategy"))
    execution_metadata = {
        "executor": executor,
        "channel": channel,
        "conversation_policy": conversation_policy,
        "glasshive_worker_strategy": worker_strategy,
        "execution_profile": _default_glasshive_worker_profile() if executor == "glasshive_host" else "main Viventium",
        "execution_mode": "host" if executor == "glasshive_host" else "scheduler delivery",
        "workspace_root": _workspace_root(),
    }
    definition = {
        "id": definition_id,
        "user_id": user_id,
        "task_id": None,
        "title": title,
        "source_prompt_id": payload.get("sourcePromptId"),
        "template_id": payload.get("templateId"),
        "prompt_text": prompt_text,
        "schedule": schedule,
        "timezone": timezone_name,
        "active": 1 if payload.get("active") else 0,
        "memory_write_mode": _memory_write_mode(payload.get("memoryWriteMode")),
        "workspace_alias": _workspace_alias(definition_id),
        "my_folder": my_folder,
        "metadata": {"execution": execution_metadata},
        "created_at": now,
        "updated_at": now,
    }
    render_payload = render_variables(prompt_text, user_id=user_id, email=email)
    version = {
        "id": f"spv_{uuid.uuid4().hex}",
        "definition_id": definition_id,
        "version_number": 1,
        "prompt_text": prompt_text,
        "rendered_text": _private_rendered_marker(render_payload["renderedHash"]),
        "rendered_hash": render_payload["renderedHash"],
        "variable_snapshot_json": _private_snapshot_marker(render_payload["variableSnapshotHash"]),
        "variable_snapshot_hash": render_payload["variableSnapshotHash"],
        "created_at": now,
    }
    task_id = str(uuid.uuid4())
    definition["task_id"] = task_id
    task = {
        "id": task_id,
        "user_id": user_id,
        "agent_id": os.getenv("VIVENTIUM_MAIN_AGENT_ID") or "prompt-workbench",
        "prompt": prompt_text,
        "schedule": schedule,
        "channel": channel,
        "executor": executor,
        "conversation_policy": conversation_policy,
        "conversation_id": None,
        "last_conversation_id": None,
        "active": definition["active"],
        "created_by": "agent:prompt-workbench",
        "created_source": "user",
        "created_at": now,
        "updated_at": now,
        "updated_by": "agent:prompt-workbench",
        "updated_source": "user",
        "last_run_at": None,
        "next_run_at": _schedule_next(schedule),
        "last_status": None,
        "last_error": None,
        "last_delivery_outcome": None,
        "last_delivery_reason": None,
        "last_delivery_at": None,
        "last_generated_text": None,
        "last_delivery": None,
        "metadata": _task_metadata(definition, version, render_payload),
    }
    store = storage()
    store.create_scheduled_prompt_definition(definition)
    store.create_scheduled_prompt_version(version)
    store.create_task(task)
    return _public_definition(definition)


def update_scheduled_prompt(definition_id: str, payload: dict[str, Any], *, user_id: str, email: str | None = None) -> dict[str, Any]:
    store = storage()
    if _is_user_schedule_id(definition_id):
        task_id = _task_id_from_user_schedule_id(definition_id)
        task = store.get_task(user_id, task_id)
        if not task:
            raise KeyError(definition_id)
        updates: dict[str, Any] = {
            "updated_at": _utc_now(),
            "updated_by": "agent:prompt-workbench",
            "updated_source": "user",
        }
        metadata = task.get("metadata") if isinstance(task.get("metadata"), dict) else {}
        if "title" in payload:
            metadata = {**metadata, "workbench_title": str(payload.get("title") or "").strip()}
            updates["metadata"] = metadata
        if "promptText" in payload:
            updates["prompt"] = str(payload.get("promptText") or "").strip()
        if "schedule" in payload and isinstance(payload.get("schedule"), dict):
            updates["schedule"] = payload["schedule"]
            updates["next_run_at"] = _schedule_next(payload["schedule"])
        if "active" in payload:
            updates["active"] = 1 if payload.get("active") else 0
        updated_task = store.update_task(user_id, task_id, updates)
        if not updated_task:
            raise KeyError(definition_id)
        return _public_task_schedule(updated_task)

    existing = store.get_scheduled_prompt_definition(definition_id)
    if not existing:
        raise KeyError(definition_id)
    if existing.get("user_id") != user_id:
        raise PermissionError("scheduled prompt belongs to another user")

    updated_definition = dict(existing)
    changed_prompt = False
    updates: dict[str, Any] = {"updated_at": _utc_now()}
    metadata = existing.get("metadata") if isinstance(existing.get("metadata"), dict) else {}
    execution = metadata.get("execution") if isinstance(metadata.get("execution"), dict) else {}
    if "title" in payload:
        updates["title"] = str(payload.get("title") or "").strip()
        updated_definition["title"] = updates["title"]
    if "promptText" in payload:
        updates["prompt_text"] = str(payload.get("promptText") or "").strip() + "\n"
        updated_definition["prompt_text"] = updates["prompt_text"]
        changed_prompt = True
    if "schedule" in payload and isinstance(payload.get("schedule"), dict):
        updates["schedule"] = payload["schedule"]
        updates["timezone"] = str(payload["schedule"].get("timezone") or existing.get("timezone") or "UTC")
        updated_definition["schedule"] = updates["schedule"]
        updated_definition["timezone"] = updates["timezone"]
    if "active" in payload:
        updates["active"] = 1 if payload.get("active") else 0
        updated_definition["active"] = bool(payload.get("active"))
    if "memoryWriteMode" in payload:
        updates["memory_write_mode"] = _memory_write_mode(payload.get("memoryWriteMode"))
        updated_definition["memory_write_mode"] = updates["memory_write_mode"]
    if "executor" in payload:
        execution["executor"] = _executor(payload.get("executor"))
    if "channel" in payload:
        execution["channel"] = _channel_for_executor(str(execution.get("executor") or (storage().get_task(str(existing["user_id"]), str(existing["task_id"])) or {}).get("executor") or "glasshive_host"), payload.get("channel"))
    if "conversationPolicy" in payload or "conversation_policy" in payload:
        execution["conversation_policy"] = _conversation_policy(payload.get("conversationPolicy") or payload.get("conversation_policy"))
    if "glasshiveWorkerStrategy" in payload or "glasshive_worker_strategy" in payload:
        execution["glasshive_worker_strategy"] = _worker_strategy(payload.get("glasshiveWorkerStrategy") or payload.get("glasshive_worker_strategy"))
    if execution:
        executor = _executor(execution.get("executor"))
        execution["channel"] = _channel_for_executor(executor, execution.get("channel"))
        execution["conversation_policy"] = _conversation_policy(execution.get("conversation_policy"))
        execution["glasshive_worker_strategy"] = _worker_strategy(execution.get("glasshive_worker_strategy"))
        execution["execution_profile"] = _default_glasshive_worker_profile() if executor == "glasshive_host" else "main Viventium"
        execution["execution_mode"] = "host" if executor == "glasshive_host" else "scheduler delivery"
        execution["workspace_root"] = _workspace_root()
        metadata = {**metadata, "execution": execution}
        updates["metadata"] = metadata
        updated_definition["metadata"] = metadata

    patched_definition = store.update_scheduled_prompt_definition(definition_id, updates) or updated_definition
    render_payload = render_variables(str(patched_definition.get("prompt_text") or ""), user_id=user_id, email=email)
    latest_version = store.latest_scheduled_prompt_version(definition_id)
    if changed_prompt or not latest_version or latest_version.get("rendered_hash") != render_payload["renderedHash"]:
        latest_version = {
            "id": f"spv_{uuid.uuid4().hex}",
            "definition_id": definition_id,
            "version_number": _version_number(definition_id),
            "prompt_text": patched_definition["prompt_text"],
            "rendered_text": _private_rendered_marker(render_payload["renderedHash"]),
            "rendered_hash": render_payload["renderedHash"],
            "variable_snapshot_json": _private_snapshot_marker(render_payload["variableSnapshotHash"]),
            "variable_snapshot_hash": render_payload["variableSnapshotHash"],
            "created_at": _utc_now(),
        }
        store.create_scheduled_prompt_version(latest_version)

    task_updates = {
        "prompt": str(patched_definition.get("prompt_text") or ""),
        "active": 1 if patched_definition.get("active") else 0,
        "metadata": _task_metadata(patched_definition, latest_version, render_payload),
        "updated_at": _utc_now(),
        "updated_by": "agent:prompt-workbench",
        "updated_source": "user",
    }
    task_metadata = task_updates["metadata"]
    task_execution = task_metadata.get("execution") if isinstance(task_metadata.get("execution"), dict) else {}
    task_executor = _executor(task_execution.get("executor"))
    task_updates["executor"] = task_executor
    task_updates["channel"] = _channel_for_executor(task_executor, task_execution.get("channel"))
    task_updates["conversation_policy"] = _conversation_policy(task_execution.get("conversation_policy"))
    if task_updates["conversation_policy"] == "new":
        task_updates["conversation_id"] = None
    if "schedule" in payload:
        task_updates["schedule"] = patched_definition["schedule"]
        task_updates["next_run_at"] = _schedule_next(patched_definition["schedule"])
    store.update_task(str(patched_definition["user_id"]), str(patched_definition["task_id"]), task_updates)
    return _public_definition(patched_definition)


def delete_scheduled_prompt(definition_id: str, *, user_id: str) -> dict[str, Any]:
    store = storage()
    if _is_user_schedule_id(definition_id):
        return {"success": store.delete_task(user_id, _task_id_from_user_schedule_id(definition_id))}
    definition = store.get_scheduled_prompt_definition(definition_id)
    if not definition:
        return {"success": False}
    if definition.get("user_id") != user_id:
        raise PermissionError("scheduled prompt belongs to another user")
    task_id = definition.get("task_id")
    if task_id:
        store.delete_task(str(definition["user_id"]), str(task_id))
    return {"success": store.delete_scheduled_prompt_definition(definition_id)}


def manual_run(
    definition_id: str,
    *,
    user_id: str,
    confirm_user_level_delivery: bool = False,
) -> dict[str, Any]:
    lock_key = f"{user_id}:{definition_id}"
    lock = _manual_run_lock(lock_key)
    lock.acquire()
    try:
        return _manual_run_locked(
            definition_id,
            user_id=user_id,
            confirm_user_level_delivery=confirm_user_level_delivery,
        )
    finally:
        lock.release()


def _manual_run_locked(
    definition_id: str,
    *,
    user_id: str,
    confirm_user_level_delivery: bool = False,
) -> dict[str, Any]:
    store = storage()
    if _is_user_schedule_id(definition_id):
        if not confirm_user_level_delivery:
            raise ValueError("User-level Viventium schedules require explicit delivery confirmation before manual run")
        task_id = _task_id_from_user_schedule_id(definition_id)
        task = store.get_task(user_id, task_id)
        if not task:
            raise KeyError(definition_id)
        if str(task.get("last_status") or "").strip() == "running" or _is_recent_manual_task_run(task):
            run = _public_task_run(task)
            return {
                "coalesced": True,
                "dispatch": {"delivery": {"outcome": "queued", "reason": "manual_run_already_inflight"}},
                "run": run,
            }
        now = datetime.now(timezone.utc)
        now_iso = to_utc_iso(now)
        store.update_task(
            user_id,
            task_id,
            {"last_run_at": now_iso, "last_status": "running", "last_error": None, "updated_at": now_iso},
        )
        task_for_dispatch = {**task, "next_run_at": now_iso}
        try:
            result = dispatch_task(task_for_dispatch)
            delivery = result.get("delivery") if isinstance(result, dict) else {}
            delivery = delivery if isinstance(delivery, dict) else {}
            next_run = compute_next_run(task.get("schedule") or {}, now, now)
            updates = {
                "last_run_at": now_iso,
                "last_status": "success",
                "last_error": None,
                "updated_at": now_iso,
                "last_delivery_at": now_iso,
                "last_delivery_outcome": delivery.get("outcome") or "sent",
                "last_delivery_reason": delivery.get("reason") or "manual_run",
                "last_generated_text": delivery.get("generated_text") if isinstance(delivery.get("generated_text"), str) else None,
                "last_delivery": delivery or {"outcome": "sent", "reason": "manual_run", "generated_text": None},
                "next_run_at": to_utc_iso(next_run) if next_run else None,
            }
            updated_task = store.update_task(user_id, task_id, updates) or task
            return {"dispatch": result, "run": _public_task_run(updated_task)}
        except Exception as exc:
            store.update_task(
                user_id,
                task_id,
                {
                    "last_status": "error",
                    "last_error": str(exc),
                    "updated_at": now_iso,
                    "last_delivery_at": now_iso,
                    "last_delivery_outcome": "failed",
                    "last_delivery_reason": str(exc),
                    "last_generated_text": None,
                    "last_delivery": {"outcome": "failed", "reason": str(exc), "generated_text": None},
                },
            )
            raise

    definition = store.get_scheduled_prompt_definition(definition_id)
    if not definition:
        raise KeyError(definition_id)
    if definition.get("user_id") != user_id:
        raise PermissionError("scheduled prompt belongs to another user")
    task = store.get_task(str(definition["user_id"]), str(definition["task_id"]))
    if not task:
        raise KeyError(str(definition.get("task_id")))
    recent = store.list_scheduled_prompt_runs(definition_id=definition_id, limit=5)
    inflight = next((run for run in recent if _is_inflight_run(run) or _is_recent_scheduled_prompt_run(run)), None)
    if inflight:
        return _coalesced_manual_run_response(inflight)
    if str(task.get("executor") or "glasshive_host").strip() != "glasshive_host":
        return _manual_run_workbench_viventium_agent(store, definition, task)
    task = dict(task)
    task["next_run_at"] = _utc_now()
    result = dispatch_task(task)
    runs = store.list_scheduled_prompt_runs(definition_id=definition_id, limit=1)
    return {"dispatch": result, "run": _public_run(runs[0]) if runs else None}


def _manual_run_workbench_viventium_agent(
    store: ScheduleStorage,
    definition: dict[str, Any],
    task: dict[str, Any],
) -> dict[str, Any]:
    now_iso = _utc_now()
    latest_version = store.latest_scheduled_prompt_version(str(definition["id"]))
    metadata = task.get("metadata") if isinstance(task.get("metadata"), dict) else {}
    wb = metadata.get("workbench_scheduled_prompt") if isinstance(metadata.get("workbench_scheduled_prompt"), dict) else {}
    run_id = f"sp_run_{uuid.uuid4().hex}"
    store.create_scheduled_prompt_run(
        {
            "run_id": run_id,
            "task_id": str(task.get("id") or ""),
            "definition_id": definition.get("id"),
            "user_id": str(definition.get("user_id") or task.get("user_id") or ""),
            "version_id": (latest_version or {}).get("id") or wb.get("version_id"),
            "due_at": str(task.get("next_run_at") or now_iso),
            "started_at": now_iso,
            "completed_at": None,
            "status": "running",
            "executor": "viventium_agent",
            "rendered_hash": wb.get("rendered_hash") or (latest_version or {}).get("rendered_hash"),
            "variable_snapshot_hash": wb.get("variable_snapshot_hash") or (latest_version or {}).get("variable_snapshot_hash"),
            "glasshive_project_id": None,
            "glasshive_worker_id": None,
            "glasshive_run_id": None,
            "result_summary": "Viventium agent manual run started.",
            "error_class": None,
            "private_detail_path": None,
            "callback_payload_json": None,
            "created_at": now_iso,
            "updated_at": now_iso,
        }
    )
    task_for_dispatch = dict(task)
    task_for_dispatch["next_run_at"] = now_iso
    try:
        result = dispatch_task(task_for_dispatch)
        delivery = result.get("delivery") if isinstance(result, dict) else {}
        delivery = delivery if isinstance(delivery, dict) else {}
        refreshed_task = store.get_task(str(definition["user_id"]), str(definition["task_id"])) or task
        refreshed_metadata = refreshed_task.get("metadata") if isinstance(refreshed_task.get("metadata"), dict) else {}
        refreshed_wb = refreshed_metadata.get("workbench_scheduled_prompt") if isinstance(refreshed_metadata.get("workbench_scheduled_prompt"), dict) else {}
        refreshed_version = store.latest_scheduled_prompt_version(str(definition["id"]))
        summary_parts = [str(delivery.get("outcome") or "sent"), str(delivery.get("reason") or "manual_run")]
        updated = store.update_scheduled_prompt_run(
            run_id,
            {
                "status": "completed",
                "completed_at": _utc_now(),
                "version_id": (refreshed_version or {}).get("id") or refreshed_wb.get("version_id"),
                "rendered_hash": refreshed_wb.get("rendered_hash") or (refreshed_version or {}).get("rendered_hash"),
                "variable_snapshot_hash": refreshed_wb.get("variable_snapshot_hash") or (refreshed_version or {}).get("variable_snapshot_hash"),
                "result_summary": _safe_summary(": ".join(part for part in summary_parts if part)),
                "error_class": None,
                "updated_at": _utc_now(),
            },
        )
        return {"dispatch": result, "run": _public_run(updated or store.get_scheduled_prompt_run(run_id))}
    except Exception as exc:
        updated = store.update_scheduled_prompt_run(
            run_id,
            {
                "status": "failed",
                "completed_at": _utc_now(),
                "result_summary": _safe_summary(str(exc)),
                "error_class": exc.__class__.__name__,
                "updated_at": _utc_now(),
            },
        )
        if updated:
            _public_run(updated)
        raise


def list_runs(definition_id: str, *, user_id: str) -> dict[str, Any]:
    if _is_user_schedule_id(definition_id):
        task = storage().get_task(user_id, _task_id_from_user_schedule_id(definition_id))
        if not task:
            raise KeyError(definition_id)
        run = _public_task_run(task)
        return {"runs": [run] if run else []}
    definition = storage().get_scheduled_prompt_definition(definition_id)
    if not definition:
        raise KeyError(definition_id)
    if definition.get("user_id") != user_id:
        raise PermissionError("scheduled prompt belongs to another user")
    runs = storage().list_scheduled_prompt_runs(definition_id=definition_id)
    return {"runs": [_public_run(run) for run in runs]}


def _definition_for_periphery(definition_id: str, user_id: str) -> dict[str, Any]:
    if _is_user_schedule_id(definition_id):
        raise ValueError("User-level schedules do not use Workbench periphery artifact files")
    definition = storage().get_scheduled_prompt_definition(definition_id)
    if not definition:
        raise KeyError(definition_id)
    if definition.get("user_id") != user_id:
        raise PermissionError("scheduled prompt belongs to another user")
    return definition


def _periphery_root(my_folder: str | None) -> Path | None:
    if not my_folder:
        return None
    root = Path(my_folder).expanduser() / "periphery"
    return root if root.is_dir() else None


def _relative_posix(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        return path.name


def _periphery_files(my_folder: str | None) -> tuple[Path | None, list[Path]]:
    root = _periphery_root(my_folder)
    if not root:
        return None, []
    try:
        resolved_root = root.resolve()
    except OSError:
        return root, []
    paths: list[Path] = []
    for path in root.glob("*/*/*/*.json"):
        try:
            if not path.is_file():
                continue
            path.resolve().relative_to(resolved_root)
        except (OSError, ValueError):
            continue
        paths.append(path)
    return root, sorted(paths, key=lambda item: item.stat().st_mtime if item.exists() else 0, reverse=True)[:100]


def _periphery_invalid(path: Path, root: Path, reason: str, *, missing_fields: list[str] | None = None) -> dict[str, Any]:
    result = {
        "fileName": path.name,
        "relativePath": _relative_posix(path, root),
        "reason": reason,
    }
    if missing_fields:
        result["missingFields"] = missing_fields[:12]
    return result


def _periphery_content_counts(payload: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for field in PERIPHERY_CONTENT_FIELDS:
        value = payload.get(field)
        if isinstance(value, list):
            counts[field] = len(value)
        elif value:
            counts[field] = 1
        else:
            counts[field] = 0
    return counts


def _periphery_artifact_id(path: Path, root: Path) -> str:
    return _sha(_relative_posix(path, root), length=24)


def _load_periphery_artifact(path: Path, root: Path) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    try:
        relative_parts = path.resolve().relative_to(root.resolve()).parts
    except (OSError, ValueError):
        return None, _periphery_invalid(path, root, "outside_periphery_root")
    if len(relative_parts) < 4:
        return None, _periphery_invalid(path, root, "invalid_path_shape")
    module_from_path = str(relative_parts[0])
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        return None, _periphery_invalid(path, root, "unreadable")
    except json.JSONDecodeError:
        return None, _periphery_invalid(path, root, "invalid_json")
    if not isinstance(payload, dict):
        return None, _periphery_invalid(path, root, "invalid_payload")

    missing = [field for field in PERIPHERY_REQUIRED_FIELDS if field not in payload]
    if missing:
        return None, _periphery_invalid(path, root, "missing_required_fields", missing_fields=missing)
    module_id = str(payload.get("moduleId") or "").strip()
    if not re.fullmatch(r"[a-z][a-z0-9_-]{1,63}", module_id):
        return None, _periphery_invalid(path, root, "invalid_module_id")
    if module_id != module_from_path:
        return None, _periphery_invalid(path, root, "module_path_mismatch")

    markdown_path = path.with_suffix(".md")
    try:
        stat = path.stat()
        modified = datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()
    except OSError:
        modified = None
    scheduled_run_ref = payload.get("scheduledRunRef")
    scheduled_run_ref_hash = None
    if scheduled_run_ref:
        scheduled_run_ref_hash = _sha(json.dumps(scheduled_run_ref, sort_keys=True, default=str), length=24)
    source_refs = payload.get("sourceRefs")
    return {
        "artifactId": _periphery_artifact_id(path, root),
        "moduleId": module_id,
        "sidecarFileName": path.name,
        "markdownFileName": markdown_path.name,
        "relativePath": _relative_posix(path, root),
        "markdownRelativePath": _relative_posix(markdown_path, root),
        "markdownExists": markdown_path.is_file(),
        "generatedAt": str(payload.get("generatedAt") or ""),
        "updatedAt": modified,
        "confidence": _safe_summary(str(payload.get("confidence") or ""), limit=80),
        "severity": _safe_summary(str(payload.get("severity") or ""), limit=80),
        "timeSensitivity": _safe_summary(str(payload.get("timeSensitivity") or ""), limit=80),
        "ttl": _safe_summary(str(payload.get("ttl") or ""), limit=80),
        "staleAfter": str(payload.get("staleAfter") or ""),
        "sourceRefCount": len(source_refs) if isinstance(source_refs, list) else 0,
        "scheduledRunRefHash": scheduled_run_ref_hash,
        "contentCounts": _periphery_content_counts(payload),
    }, None


def list_periphery_artifacts(definition_id: str, *, user_id: str) -> dict[str, Any]:
    definition = _definition_for_periphery(definition_id, user_id)
    root, paths = _periphery_files(definition.get("my_folder"))
    artifacts: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []
    if root:
        for path in paths:
            artifact, error = _load_periphery_artifact(path, root)
            if artifact:
                artifacts.append(artifact)
            if error:
                invalid.append(error)
    return {
        "artifacts": artifacts,
        "invalidArtifacts": invalid,
        "contract": (
            "Write private periphery artifacts as paired .md/.json files under "
            "my_folder/periphery/<moduleId>/YYYY/MM/. The API returns metadata only; "
            "markdown bodies, source refs, and raw insight text stay private."
        ),
    }


def _proposal_files(my_folder: str | None) -> list[Path]:
    if not my_folder:
        return []
    root = Path(my_folder).expanduser()
    if not root.is_dir():
        return []
    paths: list[Path] = []
    for path in root.glob("*.json"):
        name = path.name.lower()
        if "proposal" in name and "memory" in name:
            paths.append(path)
    return sorted(paths, key=lambda item: item.stat().st_mtime if item.exists() else 0, reverse=True)[:25]


def _proposal_id(path: Path) -> str:
    return _sha(str(path.resolve()), length=24)


def _load_proposal(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    actions = payload if isinstance(payload, list) else payload.get("actions") if isinstance(payload, dict) else None
    if not isinstance(actions, list):
        return None
    cleaned: list[dict[str, Any]] = []
    for item in actions:
        if not isinstance(item, dict):
            continue
        action = str(item.get("action") or item.get("type") or "").strip()
        key = str(item.get("key") or "").strip()
        value = item.get("value") if isinstance(item.get("value"), str) else ""
        if action not in {"set", "delete"} or not key:
            continue
        cleaned.append(
            {
                "action": action,
                "key": key,
                "valueHash": _sha(value) if action == "set" else None,
                "valuePreview": (value[:240] + ("..." if len(value) > 240 else "")) if action == "set" else "",
                "reason": str(item.get("reason") or "").strip()[:240],
            }
        )
    try:
        stat = path.stat()
        modified = datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()
    except OSError:
        modified = None
    return {
        "proposalId": _proposal_id(path),
        "fileName": path.name,
        "updatedAt": modified,
        "actionCount": len(cleaned),
        "actions": cleaned,
    }


def _definition_for_proposals(definition_id: str, user_id: str) -> dict[str, Any]:
    if _is_user_schedule_id(definition_id):
        raise ValueError("User-level schedules do not use Workbench memory proposal files")
    definition = storage().get_scheduled_prompt_definition(definition_id)
    if not definition:
        raise KeyError(definition_id)
    if definition.get("user_id") != user_id:
        raise PermissionError("scheduled prompt belongs to another user")
    return definition


def list_memory_proposals(definition_id: str, *, user_id: str) -> dict[str, Any]:
    definition = _definition_for_proposals(definition_id, user_id)
    proposals = [
        proposal
        for proposal in (_load_proposal(path) for path in _proposal_files(definition.get("my_folder")))
        if proposal
    ]
    return {
        "proposals": proposals,
        "contract": "Write structured proposal JSON files named memory-proposals-*.json under my_folder.",
    }


def apply_memory_proposal(
    definition_id: str,
    proposal_id: str,
    *,
    user_id: str,
    apply: bool = False,
) -> dict[str, Any]:
    definition = _definition_for_proposals(definition_id, user_id)
    match = next((path for path in _proposal_files(definition.get("my_folder")) if _proposal_id(path) == proposal_id), None)
    if not match:
        raise KeyError(proposal_id)
    script = LIBRECHAT_ROOT / "scripts" / "viventium-memory-proposal-apply.js"
    if not script.exists():
        raise RuntimeError("Governed memory proposal helper is unavailable")
    cmd = [
        "node",
        str(script),
        "--proposal",
        str(match),
        "--user-id",
        user_id,
        "--json",
        "--apply" if apply else "--dry-run",
    ]
    completed = subprocess.run(
        cmd,
        cwd=str(LIBRECHAT_ROOT),
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    output = completed.stdout.strip() or "{}"
    try:
        payload = json.loads(output)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Governed memory proposal helper returned invalid JSON") from exc
    if completed.returncode not in {0, 2}:
        reason = (completed.stderr or completed.stdout or "memory proposal apply failed").strip()
        raise RuntimeError(_safe_summary(reason))
    return {
        "proposalId": proposal_id,
        "applied": bool(apply and payload.get("ok")),
        "result": payload,
    }


def seed_nightly_prompt(
    *,
    user_id: str,
    email: str | None = None,
    active: bool = False,
    executor: str | None = None,
) -> dict[str, Any]:
    rows = storage().list_scheduled_prompt_definitions(user_id=user_id)
    template = nightly_prompt_template()
    if executor:
        template["executor"] = _executor(executor)
    for row in rows:
        if row.get("template_id") == NIGHTLY_TEMPLATE_ID:
            updates: dict[str, Any] = {}
            if str(row.get("title") or "").strip() != template["title"]:
                updates["title"] = template["title"]
            if str(row.get("prompt_text") or "").strip() != NIGHTLY_PROMPT_TEMPLATE.strip():
                updates["promptText"] = NIGHTLY_PROMPT_TEMPLATE
            if _should_reconcile_builtin_nightly_schedule(row.get("schedule"), template["schedule"]):
                updates["schedule"] = template["schedule"]
            if active and not row.get("active"):
                updates["active"] = True
            if executor and _public_definition(row).get("executor") != template["executor"]:
                updates["executor"] = template["executor"]
            if updates:
                return update_scheduled_prompt(str(row["id"]), updates, user_id=user_id, email=email)
            _ensure_builtin_nightly_task_policy(row)
            return _public_definition(row)
    return create_scheduled_prompt(
        {**template, "templateId": NIGHTLY_TEMPLATE_ID, "active": active},
        user_id=user_id,
        email=email,
    )

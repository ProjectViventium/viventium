from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .paths import workbench_private_root


SNAPSHOT_SCHEMA_VERSION = 1
MODEL_SNAPSHOT_FILE = "model"
FULL_SNAPSHOT_FILE = "full"
MANIFEST_FILE = "manifest"
STRUCTURED_QUARANTINE_LABELS = {"qa", "test", "synthetic", "eval"}
MAX_CONVERSATIONS = 120
MAX_MESSAGES = 2500
MAX_MESSAGES_PER_CONVERSATION = 80
MAX_MESSAGE_CHARS = 6_000
MAX_MODEL_CONVERSATION_CHARS = 1_200_000
MAX_MEMORY_CHARS = 12_000
MAX_MODEL_MEMORY_CHARS = 500_000
MAX_SCRATCHPADS = 80
MAX_SCRATCHPAD_CHARS = 12_000
MAX_TOTAL_SCRATCHPAD_CHARS = 160_000
SNAPSHOT_RETENTION_COUNT = 14
MAX_HEALTH_RECORD_SUMMARIES = 120
MAX_HEALTH_RECORDS = 18
MAX_HEALTH_RECORD_BYTES = 65_536
MAX_TOTAL_HEALTH_CHARS = 384_000
HEALTH_COMMAND_TIMEOUT_SECONDS = 12


def _sha(value: str, *, length: int = 24) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def _utc_iso(value: datetime | None = None) -> str:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _empty_health_evidence(
    status: str,
    *,
    missing: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "provider": "whoop",
        "missingPrerequisites": list(missing or []),
        "latestRun": None,
        "records": [],
        "counts": {
            "runsInspected": 0,
            "recordSummariesInspected": 0,
            "recordsIncluded": 0,
            "recordsTruncated": 0,
            "recordReadFailures": 0,
        },
    }


def _run_health_json(
    command: str,
    arguments: list[str],
    *,
    runner: Callable[..., Any],
) -> dict[str, Any] | None:
    try:
        completed = runner(
            [command, *arguments],
            text=True,
            capture_output=True,
            timeout=HEALTH_COMMAND_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if int(getattr(completed, "returncode", 1)) != 0:
        return None
    try:
        payload = json.loads(str(getattr(completed, "stdout", "") or ""))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _select_health_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in records:
        record_id = str(row.get("record_id") or "")
        resource = str(row.get("resource") or "unknown").strip().lower()
        if not re.fullmatch(r"[0-9a-f]{32}", record_id):
            continue
        if row.get("status") != 200 or row.get("error"):
            continue
        grouped.setdefault(resource, []).append(row)

    selected: list[dict[str, Any]] = []
    depth = 0
    resources = sorted(grouped)
    while len(selected) < MAX_HEALTH_RECORDS:
        added = False
        for resource in resources:
            rows = grouped[resource]
            if depth >= len(rows):
                continue
            selected.append(rows[depth])
            added = True
            if len(selected) >= MAX_HEALTH_RECORDS:
                break
        if not added:
            break
        depth += 1
    return selected


def collect_health_evidence(
    *,
    command: str | None = None,
    runner: Callable[..., Any] = subprocess.run,
) -> dict[str, Any]:
    """Read a bounded, exact-content projection from the read-only health CLI."""

    resolved_command = str(
        command
        or os.getenv("VIVENTIUM_HEALTH_COMMAND")
        or (
            Path.home()
            / "Library"
            / "Application Support"
            / "Viventium"
            / "health"
            / "runtime"
            / "bin"
            / "viventium-health"
        )
    )
    if runner is subprocess.run and not Path(resolved_command).is_file():
        return _empty_health_evidence(
            "unavailable",
            missing=["viventium_health_runtime"],
        )

    runs_payload = _run_health_json(
        resolved_command,
        ["runs", "--provider", "whoop", "--limit", "3"],
        runner=runner,
    )
    records_payload = _run_health_json(
        resolved_command,
        [
            "records",
            "--provider",
            "whoop",
            "--limit",
            str(MAX_HEALTH_RECORD_SUMMARIES),
        ],
        runner=runner,
    )
    if runs_payload is None or records_payload is None:
        return _empty_health_evidence(
            "unavailable",
            missing=["viventium_health_archive_reader"],
        )

    runs = [row for row in runs_payload.get("runs") or [] if isinstance(row, dict)]
    summaries = [row for row in records_payload.get("records") or [] if isinstance(row, dict)]
    latest_run: dict[str, Any] | None = None
    if runs:
        raw = runs[0]
        private_id = str(raw.get("run_id") or "")
        latest_run = {
            "sourceRef": _source_ref("health", f"run:{private_id}"),
            "privateLocator": private_id,
            "provider": "whoop",
            "startedAt": raw.get("started_at"),
            "finishedAt": raw.get("finished_at"),
            "status": str(raw.get("status") or "incomplete"),
            "requestedStart": raw.get("requested_start"),
            "requestedEnd": raw.get("requested_end"),
            "resources": [str(value) for value in raw.get("resources") or []],
            "resourceResults": dict(raw.get("resource_results") or {}),
        }

    records: list[dict[str, Any]] = []
    failures = 0
    truncated = 0
    total_chars = 0
    for summary in _select_health_records(summaries):
        remaining = MAX_TOTAL_HEALTH_CHARS - total_chars
        if remaining <= 0:
            break
        record_id = str(summary["record_id"])
        chunk = _run_health_json(
            resolved_command,
            ["read", record_id, "--offset", "0", "--max-bytes", str(MAX_HEALTH_RECORD_BYTES)],
            runner=runner,
        )
        if (
            chunk is None
            or chunk.get("integrity_matches") is not True
            or str(chunk.get("record_id") or "") != record_id
        ):
            failures += 1
            continue
        content = str(chunk.get("data") or "")[:remaining]
        complete = bool(chunk.get("complete")) and len(content) == len(str(chunk.get("data") or ""))
        if not complete:
            truncated += 1
        total_chars += len(content)
        records.append(
            {
                "sourceRef": _source_ref("health", f"record:{record_id}"),
                "privateLocator": record_id,
                "provider": "whoop",
                "resource": str(chunk.get("resource") or summary.get("resource") or "unknown"),
                "fetchedAt": chunk.get("fetched_at") or summary.get("fetched_at"),
                "responseStatus": chunk.get("status"),
                "byteLength": int(chunk.get("total_bytes") or summary.get("byte_length") or 0),
                "sha256": str(chunk.get("sha256") or summary.get("sha256") or ""),
                "encoding": str(chunk.get("encoding") or "unknown"),
                "contentComplete": complete,
                "content": content,
            }
        )

    latest_status = str((latest_run or {}).get("status") or "")
    missing: list[str] = []
    status = "complete" if records else "empty"
    if latest_status in {"partial", "failed", "incomplete"}:
        status = "degraded"
        missing.append("whoop_pull_incomplete")
    if failures:
        status = "degraded"
        missing.append("health_record_read_failure")
    elif truncated and status == "complete":
        status = "partial"
    return {
        "status": status,
        "provider": "whoop",
        "missingPrerequisites": sorted(set(missing)),
        "latestRun": latest_run,
        "records": records,
        "counts": {
            "runsInspected": len(runs),
            "recordSummariesInspected": len(summaries),
            "recordsIncluded": len(records),
            "recordsTruncated": truncated,
            "recordReadFailures": failures,
        },
    }


def _user_snapshot_root(user_id: str) -> Path:
    root = workbench_private_root() / "periphery-snapshots" / _sha(str(user_id), length=32)
    root.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(root, 0o700)
    except OSError:
        pass
    return root


def _write_private_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{uuid.uuid4().hex}")
    try:
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
            encoding="utf-8",
        )
        os.chmod(temporary, 0o600)
        temporary.replace(path)
        os.chmod(path, 0o600)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _prune_snapshots(root: Path, *, keep: int = SNAPSHOT_RETENTION_COUNT) -> int:
    manifests = sorted(root.glob(f"*.{MANIFEST_FILE}.json"), key=lambda path: path.name, reverse=True)
    removed = 0
    for manifest_path in manifests[keep:]:
        snapshot_id = manifest_path.name.removesuffix(f".{MANIFEST_FILE}.json")
        for suffix in (FULL_SNAPSHOT_FILE, MODEL_SNAPSHOT_FILE, MANIFEST_FILE):
            candidate = root / f"{snapshot_id}.{suffix}.json"
            try:
                candidate.unlink()
                removed += 1
            except FileNotFoundError:
                pass
    return removed


def _labels_path(user_id: str) -> Path:
    return _user_snapshot_root(user_id) / "corpus-labels.json"


def write_labels(user_id: str, payload: dict[str, Any]) -> Path:
    normalized = dict(payload)
    normalized.setdefault("schemaVersion", 1)
    _write_private_json(_labels_path(user_id), normalized)
    return _labels_path(user_id)


def _load_labels(user_id: str) -> dict[str, Any]:
    path = _labels_path(user_id)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"schemaVersion": 1, "conversations": {}, "messages": {}, "scratchpads": {}}
    if not isinstance(payload, dict):
        return {"schemaVersion": 1, "conversations": {}, "messages": {}, "scratchpads": {}}
    payload.setdefault("conversations", {})
    payload.setdefault("messages", {})
    payload.setdefault("scratchpads", {})
    return payload


def _source_ref(kind: str, private_locator: Any) -> str:
    return f"{kind}:{_sha(str(private_locator), length=24)}"


def _clean_text(value: Any, *, limit: int = 24_000) -> str:
    if isinstance(value, str):
        text = value
    elif value is None:
        return ""
    else:
        try:
            text = json.dumps(value, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            text = str(value)
    return text[:limit]


def _mongo_snapshot_script(user_id: str, email: str | None) -> str:
    return f"""
/* periphery_snapshot_v1 */
const requestedUserId = {json.dumps(str(user_id or ""))};
const requestedEmail = {json.dumps(str(email or ""))};
let selector = null;
if (requestedEmail) selector = {{email: requestedEmail}};
else if (requestedUserId) selector = ObjectId.isValid(requestedUserId) ? {{_id:ObjectId(requestedUserId)}} : {{_id:requestedUserId}};
const user = selector ? db.users.findOne(selector, {{_id:1,email:1,name:1}}) : null;
if (!user) {{ print(JSON.stringify(null)); }} else {{
  const uid = String(user._id);
  const oid = ObjectId.isValid(uid) ? ObjectId(uid) : null;
  const ownership = oid
    ? {{$or:[{{user:oid}},{{user:uid}},{{userId:oid}},{{userId:uid}}]}}
    : {{$or:[{{user:uid}},{{userId:uid}}]}};
  const conversations = db.conversations.find(ownership, {{_id:1,conversationId:1,title:1,tags:1,createdAt:1,updatedAt:1,metadata:1}})
    .sort({{updatedAt:-1,createdAt:-1}}).limit({MAX_CONVERSATIONS}).toArray();
  const conversationIds = conversations.map(c => String(c.conversationId || c._id));
  const messages = conversationIds.length
    ? db.messages.find({{$and:[ownership,{{conversationId:{{$in:conversationIds}}}}]}}, {{_id:1,messageId:1,conversationId:1,sender:1,role:1,isCreatedByUser:1,text:1,content:1,createdAt:1,updatedAt:1,unfinished:1,error:1,expiredAt:1,metadata:1}})
        .sort({{createdAt:-1,_id:-1}}).limit({MAX_MESSAGES}).toArray()
    : [];
  const grouped = {{}};
  for (const message of messages) {{
    const key = String(message.conversationId || '');
    if (!grouped[key]) grouped[key] = [];
    const viv = message.metadata && message.metadata.viventium || {{}};
    grouped[key].push({{
      id:String(message.messageId || message._id),
      role:message.role || (message.isCreatedByUser ? 'user' : (message.sender || 'assistant')),
      text:typeof message.text === 'string' ? message.text : (typeof message.content === 'string' ? message.content : JSON.stringify(message.content || '')),
      createdAt:message.createdAt || message.updatedAt || null,
      unfinished:message.unfinished === true,
      error:message.error === true,
      expiredAt:message.expiredAt || null,
      qaRun:viv.qaRun === true,
      memoryEligible:viv.memoryEligible !== false
    }});
  }}
  for (const key of Object.keys(grouped)) {{
    grouped[key].sort((left, right) => {{
      const leftTime = new Date(left.createdAt || 0).getTime();
      const rightTime = new Date(right.createdAt || 0).getTime();
      if (leftTime !== rightTime) return leftTime - rightTime;
      return String(left.id).localeCompare(String(right.id));
    }});
  }}
  const memories = db.memoryentries.find(ownership, {{_id:1,key:1,type:1,value:1,text:1,tokenCount:1,updatedAt:1,updated_at:1}})
    .sort({{updated_at:-1,updatedAt:-1}}).limit(200).toArray();
  print(JSON.stringify({{
    user:{{id:uid,email:user.email || '',name:user.name || ''}},
    counts:{{
      conversations:db.conversations.countDocuments(ownership),
      messages:db.messages.countDocuments(ownership),
      memories:db.memoryentries.countDocuments(ownership)
    }},
    memories:memories.map(m => ({{id:String(m._id),key:m.key || m.type || '',value:m.value || m.text || '',tokenCount:m.tokenCount || null,updatedAt:m.updatedAt || m.updated_at || null}})),
    conversations:conversations.map(c => ({{id:String(c.conversationId || c._id),title:c.title || '',tags:Array.isArray(c.tags) ? c.tags : [],createdAt:c.createdAt || null,updatedAt:c.updatedAt || c.createdAt || null,messages:grouped[String(c.conversationId || c._id)] || []}}))
  }}));
}}
""".strip()


def _label_for_conversation(raw: dict[str, Any], labels: dict[str, Any]) -> dict[str, Any]:
    raw_id = str(raw.get("id") or "")
    overrides = labels.get("conversations") if isinstance(labels.get("conversations"), dict) else {}
    override = overrides.get(raw_id) if isinstance(overrides.get(raw_id), dict) else None
    if override:
        return {
            "label": str(override.get("label") or "reviewed"),
            "include": bool(override.get("include", True)),
            "reason": str(override.get("reason") or "private reviewed label"),
            "source": "private_override",
        }
    tags = {str(tag).strip().lower() for tag in raw.get("tags") or [] if str(tag).strip()}
    matched = sorted(tags & STRUCTURED_QUARANTINE_LABELS)
    if matched:
        return {
            "label": matched[0],
            "include": False,
            "reason": "structured conversation tag",
            "source": "structured_metadata",
        }
    return {"label": "unreviewed", "include": True, "reason": "", "source": "default"}


def _message_record(raw: dict[str, Any], labels: dict[str, Any]) -> dict[str, Any]:
    private_id = str(raw.get("id") or _sha(json.dumps(raw, sort_keys=True, default=str)))
    overrides = labels.get("messages") if isinstance(labels.get("messages"), dict) else {}
    override = overrides.get(private_id) if isinstance(overrides.get(private_id), dict) else {}
    structured_include = not any(
        (
            raw.get("qaRun") is True,
            raw.get("memoryEligible") is False,
            raw.get("unfinished") is True,
            raw.get("error") is True,
            bool(raw.get("expiredAt")),
        )
    )
    include = bool(override.get("include", structured_include))
    return {
        "sourceRef": _source_ref("message", private_id),
        "privateLocator": private_id,
        "role": str(raw.get("role") or "unknown"),
        "text": _clean_text(raw.get("text"), limit=MAX_MESSAGE_CHARS),
        "createdAt": raw.get("createdAt"),
        "include": include,
        "label": {
            "label": str(override.get("label") or ("unreviewed" if include else "structured_exclusion")),
            "source": "private_override" if override else "structured_metadata",
        },
        "exclusionReason": str(override.get("reason") or ("structured_message_metadata" if not include else "")),
    }


def _conversation_records(mongo_payload: dict[str, Any], labels: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    message_count = 0
    for raw in (mongo_payload.get("conversations") or [])[:MAX_CONVERSATIONS]:
        if not isinstance(raw, dict):
            continue
        private_id = str(raw.get("id") or _sha(json.dumps(raw, sort_keys=True, default=str)))
        label = _label_for_conversation(raw, labels)
        available_messages = [message for message in raw.get("messages") or [] if isinstance(message, dict)]
        remaining = max(0, MAX_MESSAGES - message_count)
        take = min(MAX_MESSAGES_PER_CONVERSATION, remaining)
        selected_messages = available_messages[-take:] if take else []
        messages = [_message_record(message, labels) for message in selected_messages]
        message_count += len(messages)
        records.append(
            {
                "sourceRef": _source_ref("conversation", private_id),
                "privateLocator": private_id,
                "title": _clean_text(raw.get("title"), limit=1000),
                "tags": [str(tag) for tag in raw.get("tags") or []],
                "createdAt": raw.get("createdAt"),
                "updatedAt": raw.get("updatedAt"),
                "label": label,
                "messages": messages,
            }
        )
    return records


def _memory_records(mongo_payload: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for raw in mongo_payload.get("memories") or []:
        if not isinstance(raw, dict):
            continue
        private_id = str(raw.get("id") or raw.get("key") or _sha(json.dumps(raw, sort_keys=True, default=str)))
        records.append(
            {
                "sourceRef": _source_ref("memory", private_id),
                "privateLocator": private_id,
                "key": _clean_text(raw.get("key"), limit=240),
                "value": _clean_text(raw.get("value"), limit=MAX_MEMORY_CHARS),
                "tokenCount": raw.get("tokenCount"),
                "updatedAt": raw.get("updatedAt"),
            }
        )
    return records


def _scratchpad_records(my_folder: str | None, labels: dict[str, Any]) -> list[dict[str, Any]]:
    if not my_folder:
        return []
    root = Path(my_folder).expanduser()
    if not root.is_dir():
        return []
    overrides = labels.get("scratchpads") if isinstance(labels.get("scratchpads"), dict) else {}
    records: list[dict[str, Any]] = []
    total_chars = 0
    candidates = sorted(
        root.rglob("*"),
        key=lambda item: item.stat().st_mtime if item.is_file() else 0,
        reverse=True,
    )
    for path in candidates:
        if len(records) >= MAX_SCRATCHPADS:
            break
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError:
            continue
        if not path.is_file() or path.is_symlink() or relative.startswith("periphery/"):
            continue
        if path.match("memory-proposals-*.json"):
            continue
        if path.suffix.lower() not in {".md", ".txt", ".json"}:
            continue
        try:
            stat = path.stat()
        except (OSError, UnicodeDecodeError):
            continue
        remaining_chars = max(0, MAX_TOTAL_SCRATCHPAD_CHARS - total_chars)
        content_limit = min(MAX_SCRATCHPAD_CHARS, remaining_chars)
        try:
            content = path.read_text(encoding="utf-8")[:content_limit] if content_limit else ""
        except (OSError, UnicodeDecodeError):
            content = ""
        total_chars += len(content)
        override = overrides.get(relative) if isinstance(overrides.get(relative), dict) else {}
        label = {
            "label": str(override.get("label") or "unreviewed"),
            "include": bool(override.get("include", True)),
            "reason": str(override.get("reason") or ""),
            "source": "private_override" if override else "default",
        }
        records.append(
            {
                "sourceRef": _source_ref("scratchpad", relative),
                "relativePath": relative,
                "updatedAt": _utc_iso(datetime.fromtimestamp(stat.st_mtime, timezone.utc)),
                "content": content,
                "contentOmitted": content_limit == 0,
                "label": label,
            }
        )
    return records


def _schedule_records(user_id: str, schedule_store: Any | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if schedule_store is None:
        return [], []
    schedules: list[dict[str, Any]] = []
    runs: list[dict[str, Any]] = []
    try:
        tasks = schedule_store.list_tasks(user_id=user_id, limit=100)
    except Exception:
        return [], []
    for task in tasks:
        task_id = str(task.get("id") or "")
        metadata = task.get("metadata") if isinstance(task.get("metadata"), dict) else {}
        title = str(metadata.get("workbench_title") or metadata.get("title") or "scheduled task")
        schedules.append(
            {
                "sourceRef": _source_ref("schedule", task_id),
                "title": title,
                "prompt": _clean_text(task.get("prompt"), limit=8000),
                "schedule": task.get("schedule"),
                "active": bool(task.get("active")),
                "nextRunAt": task.get("next_run_at"),
                "lastStatus": task.get("last_status"),
            }
        )
    try:
        definitions = schedule_store.list_scheduled_prompt_definitions(user_id=user_id)
        for definition in definitions:
            for run in schedule_store.list_scheduled_prompt_runs(definition_id=str(definition.get("id") or ""), limit=10):
                run_id = str(run.get("run_id") or "")
                runs.append(
                    {
                        "sourceRef": _source_ref("run", run_id),
                        "status": run.get("status"),
                        "startedAt": run.get("started_at"),
                        "completedAt": run.get("completed_at"),
                        "errorClass": run.get("error_class"),
                    }
                )
    except Exception:
        pass
    runs.sort(key=lambda row: str(row.get("startedAt") or ""), reverse=True)
    return schedules, runs[:50]


def _model_conversation(record: dict[str, Any]) -> dict[str, Any] | None:
    if not bool((record.get("label") or {}).get("include", True)):
        return None
    messages = [
        {key: value for key, value in message.items() if key not in {"privateLocator", "include", "label", "exclusionReason"}}
        for message in record.get("messages") or []
        if message.get("include")
    ]
    return {
        "sourceRef": record["sourceRef"],
        "title": record.get("title"),
        "tags": record.get("tags"),
        "createdAt": record.get("createdAt"),
        "updatedAt": record.get("updatedAt"),
        "messages": messages,
    }


def _model_memory(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key != "privateLocator"}


def _model_scratchpad(record: dict[str, Any]) -> dict[str, Any] | None:
    if not bool((record.get("label") or {}).get("include", True)):
        return None
    return {key: value for key, value in record.items() if key != "label"}


def _model_health_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    latest_run = evidence.get("latestRun")
    model_latest = (
        {key: value for key, value in latest_run.items() if key != "privateLocator"}
        if isinstance(latest_run, dict)
        else None
    )
    model_records = [
        {key: value for key, value in row.items() if key != "privateLocator"}
        for row in evidence.get("records") or []
        if isinstance(row, dict)
    ]
    return {
        "status": str(evidence.get("status") or "unavailable"),
        "provider": str(evidence.get("provider") or "whoop"),
        "missingPrerequisites": list(evidence.get("missingPrerequisites") or []),
        "latestRun": model_latest,
        "records": model_records,
        "counts": dict(evidence.get("counts") or {}),
        "interpretationContract": {
            "measurementTime": "Use measurement times inside provider content; fetchedAt is archive acquisition time.",
            "vendorScores": "Treat proprietary scores as vendor observations, not clinical measurements.",
            "causality": "Associations may be hypotheses only; do not claim diagnosis or causation.",
        },
    }


def _write_life_health_projection(
    evidence: dict[str, Any],
    *,
    generated_at: str,
    snapshot_ref: str,
) -> Path | None:
    configured = str(os.getenv("VIVENTIUM_LIFE_HEALTH_DIR") or "").strip()
    if not configured:
        return None
    root = Path(configured).expanduser()
    if root.exists() and (not root.is_dir() or root.is_symlink()):
        return None
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    root.chmod(0o700)
    records = [row for row in evidence.get("records") or [] if isinstance(row, dict)]
    latest_run = evidence.get("latestRun") if isinstance(evidence.get("latestRun"), dict) else {}
    fetched_values = sorted(
        str(row.get("fetchedAt")) for row in records if str(row.get("fetchedAt") or "").strip()
    )
    projection = {
        "schemaVersion": 1,
        "kind": "viventium-health-connector-status",
        "provider": str(evidence.get("provider") or "whoop"),
        "generatedAt": generated_at,
        "status": str(evidence.get("status") or "unavailable"),
        "missingPrerequisites": list(evidence.get("missingPrerequisites") or []),
        "latestRun": {
            "startedAt": latest_run.get("startedAt"),
            "finishedAt": latest_run.get("finishedAt"),
            "status": latest_run.get("status"),
            "resources": list(latest_run.get("resources") or []),
            "resourceResults": dict(latest_run.get("resourceResults") or {}),
        }
        if latest_run
        else None,
        "latestRecordFetchedAt": fetched_values[-1] if fetched_values else None,
        "recordSummariesInspected": int(
            (evidence.get("counts") or {}).get("recordSummariesInspected") or 0
        ),
        "recordsIncluded": int((evidence.get("counts") or {}).get("recordsIncluded") or 0),
        "resourcesIncluded": sorted(
            {str(row.get("resource") or "unknown") for row in records}
        ),
        "snapshotRefHash": _sha(snapshot_ref, length=24),
        "rawEvidence": "private_viventium_health_archive",
        "correlationSurface": "prompt_workbench_health_context",
    }
    path = root / "connector-status.json"
    _write_private_json(path, projection)
    return path


def create_snapshot(
    *,
    user_id: str,
    email: str | None,
    my_folder: str | None,
    query_mongo_json: Callable[[str], Any],
    schedule_store: Any | None = None,
    lenses: list[dict[str, Any]] | None = None,
    now: datetime | None = None,
    include_health: bool = False,
    health_reader: Callable[[], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    generated_at = _utc_iso(now)
    labels = _load_labels(user_id)
    mongo_payload = query_mongo_json(_mongo_snapshot_script(user_id, email))
    mongo_available = isinstance(mongo_payload, dict) and isinstance(mongo_payload.get("user"), dict)
    if not mongo_available:
        mongo_payload = {"user": {}, "counts": {}, "memories": [], "conversations": []}

    memories = _memory_records(mongo_payload)
    conversations = _conversation_records(mongo_payload, labels)
    scratchpads = _scratchpad_records(my_folder, labels)
    schedules, runs = _schedule_records(user_id, schedule_store)
    health_evidence = (
        (health_reader or collect_health_evidence)()
        if include_health
        else None
    )
    model_conversations: list[dict[str, Any]] = []
    conversation_chars = 0
    for row in conversations:
        item = _model_conversation(row)
        if not item:
            continue
        bounded_messages: list[dict[str, Any]] = []
        for message in item.get("messages") or []:
            chars = len(str(message.get("text") or ""))
            if conversation_chars + chars > MAX_MODEL_CONVERSATION_CHARS:
                break
            bounded_messages.append(message)
            conversation_chars += chars
        item["messages"] = bounded_messages
        model_conversations.append(item)
        if conversation_chars >= MAX_MODEL_CONVERSATION_CHARS:
            break
    model_memories: list[dict[str, Any]] = []
    memory_chars = 0
    for row in memories:
        item = _model_memory(row)
        chars = len(str(item.get("value") or ""))
        if memory_chars + chars > MAX_MODEL_MEMORY_CHARS:
            break
        model_memories.append(item)
        memory_chars += chars
    model_scratchpads = [item for item in (_model_scratchpad(row) for row in scratchpads) if item]
    status = "complete" if mongo_available else "degraded"
    missing = [] if mongo_available else ["mongo"]
    if health_evidence and str(health_evidence.get("status") or "") in {
        "unavailable",
        "degraded",
        "partial",
    }:
        status = "degraded"
        health_missing = list(health_evidence.get("missingPrerequisites") or [])
        missing.extend(health_missing or ["health_evidence"])
    missing = sorted(set(missing))

    model_payload: dict[str, Any] = {
        "schemaVersion": SNAPSHOT_SCHEMA_VERSION,
        "snapshotRef": "pending",
        "generatedAt": generated_at,
        "status": status,
        "missingPrerequisites": missing,
        "evidenceContract": {
            "citation": "Use sourceRef values exactly for every non-trivial claim.",
            "uncertainty": "Separate observations, inferences, and hypotheses. No evidence means no result.",
            "privacy": "Do not copy raw conversation text into public or sidecar metadata.",
        },
        "reasoningLenses": lenses or [],
        "memories": model_memories,
        "conversations": model_conversations,
        "schedules": schedules,
        "scratchpads": model_scratchpads,
        "recentRuns": runs,
    }
    if health_evidence is not None:
        model_payload["healthEvidence"] = _model_health_evidence(health_evidence)
    model_hash = _sha(json.dumps(model_payload, sort_keys=True, default=str), length=12)
    stamp = re.sub(r"[^0-9TZ]", "", generated_at.split(".")[0])
    snapshot_id = f"{stamp}-{model_hash}"
    snapshot_ref = f"snapshot:{snapshot_id}"
    model_payload["snapshotRef"] = snapshot_ref

    source_refs: set[str] = set()
    for memory in model_payload["memories"]:
        source_refs.add(str(memory["sourceRef"]))
    for conversation in model_payload["conversations"]:
        source_refs.add(str(conversation["sourceRef"]))
        source_refs.update(str(message["sourceRef"]) for message in conversation.get("messages") or [])
    for collection in (model_payload["schedules"], model_payload["scratchpads"], model_payload["recentRuns"]):
        source_refs.update(str(item["sourceRef"]) for item in collection)
    model_health = model_payload.get("healthEvidence")
    if isinstance(model_health, dict):
        latest_health_run = model_health.get("latestRun")
        if isinstance(latest_health_run, dict) and latest_health_run.get("sourceRef"):
            source_refs.add(str(latest_health_run["sourceRef"]))
        source_refs.update(
            str(item["sourceRef"])
            for item in model_health.get("records") or []
            if isinstance(item, dict) and item.get("sourceRef")
        )

    counts = {
        "conversationsAvailable": int((mongo_payload.get("counts") or {}).get("conversations") or len(conversations)),
        "conversationsSelected": len(conversations),
        "conversationsIncluded": len(model_conversations),
        "conversationsExcluded": len(conversations) - len(model_conversations),
        "messagesIncluded": sum(len(row.get("messages") or []) for row in model_conversations),
        "memoriesIncluded": len(model_memories),
        "schedulesIncluded": len(schedules),
        "scratchpadsIncluded": len(model_scratchpads),
        "scratchpadsExcluded": len(scratchpads) - len(model_scratchpads),
        "recentRunsIncluded": len(runs),
        "reasoningLensesIncluded": len(lenses or []),
    }
    if health_evidence is not None:
        counts.update(
            {
                "healthRecordSummariesInspected": int(
                    (health_evidence.get("counts") or {}).get("recordSummariesInspected") or 0
                ),
                "healthRecordsIncluded": int(
                    (health_evidence.get("counts") or {}).get("recordsIncluded") or 0
                ),
            }
        )
    manifest = {
        "schemaVersion": SNAPSHOT_SCHEMA_VERSION,
        "snapshotRef": snapshot_ref,
        "snapshotId": snapshot_id,
        "generatedAt": generated_at,
        "status": status,
        "missingPrerequisites": missing,
        "counts": counts,
        "sourceRefCount": len(source_refs),
        "contentHash": _sha(json.dumps(model_payload, sort_keys=True, default=str), length=32),
        "labelsHash": _sha(json.dumps(labels, sort_keys=True, default=str), length=16),
        "retention": {"maxSnapshots": SNAPSHOT_RETENTION_COUNT},
    }
    if health_evidence is not None:
        manifest["healthEvidence"] = {
            "status": str(health_evidence.get("status") or "unavailable"),
            "provider": str(health_evidence.get("provider") or "whoop"),
            "missingPrerequisites": list(health_evidence.get("missingPrerequisites") or []),
            "counts": dict(health_evidence.get("counts") or {}),
        }
    full_payload = {
        "schemaVersion": SNAPSHOT_SCHEMA_VERSION,
        "snapshotRef": snapshot_ref,
        "generatedAt": generated_at,
        "status": status,
        "user": mongo_payload.get("user") or {},
        "sourceCounts": mongo_payload.get("counts") or {},
        "memories": memories,
        "conversations": conversations,
        "schedules": schedules,
        "scratchpads": scratchpads,
        "recentRuns": runs,
    }
    if health_evidence is not None:
        full_payload["healthEvidence"] = health_evidence

    root = _user_snapshot_root(user_id)
    full_path = root / f"{snapshot_id}.{FULL_SNAPSHOT_FILE}.json"
    model_path = root / f"{snapshot_id}.{MODEL_SNAPSHOT_FILE}.json"
    manifest_path = root / f"{snapshot_id}.{MANIFEST_FILE}.json"
    _write_private_json(full_path, full_payload)
    _write_private_json(model_path, model_payload)
    _write_private_json(manifest_path, manifest)
    _write_private_json(root / "latest.json", manifest)
    if health_evidence is not None:
        _write_private_json(root / "latest.health-context.json", manifest)
    if health_evidence is not None:
        _write_life_health_projection(
            health_evidence,
            generated_at=generated_at,
            snapshot_ref=snapshot_ref,
        )
    _prune_snapshots(root)
    model_json = json.dumps(model_payload, indent=2, sort_keys=True, default=str)
    return {
        "manifest": manifest,
        "modelSnapshotJson": model_json,
        "fullSnapshotPath": str(full_path),
        "modelSnapshotPath": str(model_path),
        "manifestPath": str(manifest_path),
    }


def preview_snapshot(user_id: str, *, include_health: bool = False, **_: Any) -> dict[str, Any]:
    name = "latest.health-context.json" if include_health else "latest.json"
    path = _user_snapshot_root(user_id) / name
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "schemaVersion": SNAPSHOT_SCHEMA_VERSION,
            "status": "not_created",
            "snapshotRef": None,
            "generatedAt": None,
            "missingPrerequisites": [],
            "counts": {},
            "sourceRefCount": 0,
        }
    return payload if isinstance(payload, dict) else {"status": "not_created"}


def load_model_snapshot(user_id: str, snapshot_ref: str) -> dict[str, Any] | None:
    snapshot_id = str(snapshot_ref or "").removeprefix("snapshot:")
    if not re.fullmatch(r"[0-9TZ]+-[a-f0-9]{12}", snapshot_id):
        return None
    path = _user_snapshot_root(user_id) / f"{snapshot_id}.{MODEL_SNAPSHOT_FILE}.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def snapshot_source_refs(user_id: str, snapshot_ref: str) -> set[str]:
    payload = load_model_snapshot(user_id, snapshot_ref)
    if not payload:
        return set()
    refs: set[str] = set()
    for key in ("memories", "schedules", "scratchpads", "recentRuns"):
        refs.update(str(item.get("sourceRef")) for item in payload.get(key) or [] if item.get("sourceRef"))
    for conversation in payload.get("conversations") or []:
        if conversation.get("sourceRef"):
            refs.add(str(conversation["sourceRef"]))
        refs.update(str(item.get("sourceRef")) for item in conversation.get("messages") or [] if item.get("sourceRef"))
    health = payload.get("healthEvidence")
    if isinstance(health, dict):
        latest_run = health.get("latestRun")
        if isinstance(latest_run, dict) and latest_run.get("sourceRef"):
            refs.add(str(latest_run["sourceRef"]))
        refs.update(
            str(item.get("sourceRef"))
            for item in health.get("records") or []
            if isinstance(item, dict) and item.get("sourceRef")
        )
    return refs

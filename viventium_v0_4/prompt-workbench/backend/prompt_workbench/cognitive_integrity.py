from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import REPO_ROOT

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.viventium.config_compiler import (
    APP_SUPPORT_VIVENTIUM_DIR,
    check_prompt_bundle_drift,
    check_runtime_config_drift,
    default_live_runtime_config_candidates,
    load_live_runtime_config,
    load_source_of_truth_librechat_yaml,
)

from . import scheduled_prompts


MEMORY_RECEIPT_MAX_AGE_SECONDS = 36 * 60 * 60
NIGHTLY_RECEIPT_MAX_AGE_SECONDS = 36 * 60 * 60
RECALL_HEALTH_TIMEOUT_SECONDS = 2


CONTROL_PLANE_MAP: tuple[dict[str, str], ...] = (
    {
        "key": "provider_capability_transport",
        "owner": "compiled LibreChat provider capability registry + signed GlassHive broker",
        "trigger": "each initialized Agent turn",
        "evidence": "resolved host tools in signed grant and MCP tools/list",
    },
    {
        "key": "saved_memory_exposure",
        "owner": "memory storage policy + memory.readProfile",
        "trigger": "each Agent initialization",
        "evidence": "governed keys delivered whole or with a model-visible omission boundary",
    },
    {
        "key": "saved_memory_runtime_health",
        "owner": "LibreChat per-user read and immediate-writer health receipts",
        "trigger": "each attempted saved-memory read/write path",
        "evidence": "privacy-safe read/writer receipt joined to the configured QA identity",
    },
    {
        "key": "conversation_recall",
        "owner": "LibreChat file_search + recall runtime health/freshness gate",
        "trigger": "opted-in Agent initialization and model-controlled tool call",
        "evidence": "source/vector provenance and explicit inconclusive degraded result",
    },
    {
        "key": "workbench_nightly",
        "owner": "Prompt Workbench definition + Scheduler + GlassHive callback ledger",
        "trigger": "managed local nightly schedule",
        "evidence": "one active definition and latest scheduled delivery state, distinct from manual recovery",
    },
    {
        "key": "qa_test_account",
        "owner": "canonical runtime.extra_env selector + local non-admin LibreChat account",
        "trigger": "Prompt Workbench live eval or local native-surface QA",
        "evidence": "explicit selector resolves to exactly one non-admin account before model work",
    },
    {
        "key": "glasshive_host_worker_runtime",
        "owner": "compiled runtime.env + GlassHive host-worker prerequisite discovery",
        "trigger": "compile/restart and every host-worker preflight",
        "evidence": "enabled Codex runtime features have executable sibling companions at the invocation path",
    },
    {
        "key": "memory_hardening",
        "owner": "local LaunchAgent and memory-hardening run ledger",
        "trigger": "03:00 local direct wrapper",
        "evidence": "schedule receipt, execution tuple, and latest run state",
    },
    {
        "key": "codex_observer",
        "owner": "optional Codex automation",
        "trigger": "independent scheduled observation",
        "evidence": "reads this report; never owns or mutates product schedules",
    },
)


def _runtime_env_values() -> dict[str, str]:
    runtime_env = APP_SUPPORT_VIVENTIUM_DIR / "runtime" / "runtime.env"
    values: dict[str, str] = {}
    if not runtime_env.is_file():
        return values
    try:
        lines = runtime_env.read_text(encoding="utf-8").splitlines()
    except OSError:
        return values
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


def _safe_runtime_drift(config_path: Path) -> dict[str, Any]:
    if not config_path.is_file():
        return {"status": "blocked", "reason": "canonical_config_missing", "driftCount": None}
    try:
        report = check_runtime_config_drift(config_path=config_path)
    except Exception:
        return {"status": "error", "reason": "runtime_drift_check_failed", "driftCount": None}
    diff = (report.get("diff") or {}).get("live_vs_compiled") or {}
    return {
        "status": report.get("status"),
        "reason": report.get("reason"),
        "driftCount": report.get("drift_count"),
        "changedSections": sorted(str(item) for item in (diff.get("changed") or [])),
        "addedSections": sorted(str(item) for item in (diff.get("added") or [])),
        "removedSections": sorted(str(item) for item in (diff.get("removed") or [])),
    }


def _safe_prompt_drift() -> dict[str, Any]:
    try:
        report = check_prompt_bundle_drift()
    except Exception:
        return {"status": "error", "reason": "prompt_bundle_drift_check_failed", "driftCount": None}
    return {
        "status": report.get("status"),
        "reason": report.get("reason"),
        "driftCount": report.get("drift_count"),
        "sourcePromptCount": (report.get("source") or {}).get("prompt_count"),
        "livePromptCount": (report.get("live") or {}).get("prompt_count"),
    }


def _provider_and_memory_contract(config: dict[str, Any] | None) -> dict[str, Any]:
    payload = config or {}
    capability = (
        (((payload.get("endpoints") or {}).get("agents") or {}).get("providerCapabilities") or {}).get(
            "glasshive-harness"
        )
        or {}
    )
    memory_present = isinstance(payload.get("memory"), dict)
    memory = payload.get("memory") if memory_present else {}
    read_profile_present = isinstance(memory.get("readProfile"), dict)
    read_profile = memory.get("readProfile") if read_profile_present else {}
    storage_key_limits = memory.get("keyLimits") or {}
    read_key_limits = read_profile.get("keyLimits") or {}
    memory_reasons: list[str] = []
    storage_token_limit = int(memory.get("tokenLimit") or 0)
    read_token_limit = int(read_profile.get("tokenLimit") or 0)
    if not memory_present:
        memory_reasons.append("memory_config_missing")
    if memory_present and storage_token_limit <= 0:
        memory_reasons.append("storage_token_limit_missing_or_invalid")
    if memory_present and not read_profile_present:
        memory_reasons.append("memory_read_profile_missing")
    if read_profile_present and read_token_limit <= 0:
        memory_reasons.append("read_token_limit_missing_or_invalid")
    if storage_token_limit > 0 and read_token_limit < storage_token_limit:
        memory_reasons.append("read_total_below_storage_total")
    for key, storage_limit in storage_key_limits.items():
        if int(read_key_limits.get(key) or 0) < int(storage_limit or 0):
            memory_reasons.append(f"read_key_below_storage:{key}")
    capability_reasons: list[str] = []
    if capability.get("worker_native_tools") is not True:
        capability_reasons.append("worker_native_tools_not_declared")
    if capability.get("host_tools_transport") != "broker_mcp":
        capability_reasons.append("host_tools_transport_not_broker_mcp")
    if "file_search" not in (capability.get("host_tools") or []):
        capability_reasons.append("file_search_not_permitted")
    if "native_tools" in capability:
        capability_reasons.append("ambiguous_native_tools_field_present")
    return {
        "providerCapabilityTransport": {
            "status": "ok" if not capability_reasons else "blocked",
            "reasons": capability_reasons,
            "transport": capability.get("host_tools_transport"),
            "hostTools": sorted(str(item) for item in (capability.get("host_tools") or [])),
        },
        "memoryExposure": {
            "status": "ok" if not memory_reasons else "blocked",
            "reasons": memory_reasons,
            "storageTokenLimit": memory.get("tokenLimit") if memory_present else None,
            "readTokenLimit": read_profile.get("tokenLimit") if read_profile_present else None,
        },
    }


def _live_contract() -> dict[str, Any] | None:
    live_path = next((path for path in default_live_runtime_config_candidates() if path.is_file()), None)
    if not live_path:
        return None
    try:
        return load_live_runtime_config(live_path)
    except Exception:
        return None


def _memory_hardening_status() -> dict[str, Any]:
    try:
        completed = subprocess.run(
            [str(REPO_ROOT / "bin" / "viventium"), "memory-harden", "status", "--json"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        payload = json.loads(completed.stdout) if completed.returncode == 0 else {}
    except Exception:
        payload = {}
    schedule = payload.get("schedule_health") if isinstance(payload, dict) else {}
    latest = payload.get("latest_run") if isinstance(payload, dict) else {}
    healthy = bool((schedule or {}).get("healthy")) and str((latest or {}).get("status")) in {
        "success",
        "skipped",
    }
    return {
        "status": "ok" if healthy else "blocked",
        "scheduleState": (schedule or {}).get("state"),
        "latestRunStatus": (latest or {}).get("status"),
        "missedExpectedWindow": (schedule or {}).get("missed_expected_window"),
        "executionMismatch": (schedule or {}).get("execution_mismatch"),
    }


def _runtime_codex_worker_status() -> dict[str, Any]:
    values = _runtime_env_values()
    if not values:
        return {"status": "blocked", "reasons": ["runtime_env_missing"]}
    configured_binary = values.get("WPR_CODEX_BIN", "")
    if not configured_binary:
        return {"status": "blocked", "reasons": ["codex_binary_not_compiled"]}
    invoked_text = shutil.which(configured_binary) or configured_binary
    invoked = Path(invoked_text).expanduser()
    if not invoked.is_file() or not os.access(invoked, os.X_OK):
        return {"status": "blocked", "reasons": ["codex_binary_not_executable"]}
    try:
        completed = subprocess.run(
            [str(invoked), "features", "list"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception:
        completed = None
    if completed is None or completed.returncode != 0:
        return {"status": "blocked", "reasons": ["codex_feature_probe_failed"]}
    features: dict[str, bool] = {}
    for line in completed.stdout.splitlines():
        columns = line.split()
        if len(columns) >= 3:
            features[columns[0]] = columns[-1].lower() == "true"
    if not features or "code_mode_host" not in features:
        return {"status": "blocked", "reasons": ["codex_feature_probe_unparseable"]}
    code_mode_host_enabled = features.get("code_mode_host", False)
    companion = invoked.parent / "codex-code-mode-host"
    companion_ready = companion.is_file() and os.access(companion, os.X_OK)
    reasons: list[str] = []
    if code_mode_host_enabled and not companion_ready:
        reasons.append("enabled_code_mode_host_companion_missing_at_invocation_path")
    return {
        "status": "ok" if not reasons else "blocked",
        "reasons": reasons,
        "codeModeHostEnabled": code_mode_host_enabled,
        "companionReady": companion_ready,
        "binaryInvocation": "symlink" if invoked.is_symlink() else "canonical_or_wrapper",
    }


def _qa_test_account_status() -> dict[str, Any]:
    values = _runtime_env_values()
    email = values.get("VIVENTIUM_QA_EMAIL", "").strip()
    if not email:
        return {
            "status": "blocked",
            "reasons": ["qa_test_account_not_configured"],
            "selectorConfigured": False,
        }
    mongo_port = values.get("VIVENTIUM_LOCAL_MONGO_PORT", "27117").strip() or "27117"
    mongo_db = values.get("VIVENTIUM_LOCAL_MONGO_DB", "LibreChatViventium").strip() or "LibreChatViventium"
    script = (
        "const email="
        + json.dumps(email)
        + "; const rows=db.users.find({email},{_id:1,role:1}).limit(2).toArray();"
        + " print(JSON.stringify({count:rows.length,role:rows[0]?rows[0].role:'',"
        + "userId:rows[0]?String(rows[0]._id):''}));"
    )
    try:
        completed = subprocess.run(
            ["mongosh", "--quiet", f"mongodb://127.0.0.1:{mongo_port}/{mongo_db}"],
            input=script,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        payload = {}
        if completed.returncode == 0:
            for line in reversed(completed.stdout.splitlines()):
                json_start = line.find("{")
                if json_start < 0:
                    continue
                try:
                    payload = json.loads(line[json_start:])
                    break
                except json.JSONDecodeError:
                    continue
    except Exception:
        payload = {}
    count = int(payload.get("count") or 0)
    role = str(payload.get("role") or "").upper()
    user_id = str(payload.get("userId") or "")
    reasons: list[str] = []
    if count != 1:
        reasons.append("qa_test_account_selector_must_resolve_exactly_once")
    if role == "ADMIN":
        reasons.append("qa_test_account_must_be_non_admin")
    elif count == 1 and role not in {"USER", ""}:
        reasons.append("qa_test_account_role_unsupported")
    return {
        "status": "ok" if not reasons else "blocked",
        "reasons": reasons,
        "selectorConfigured": True,
        "accountCount": count,
        "role": role or None,
        "accountHash": hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:24]
        if count == 1 and user_id
        else None,
    }


def _parse_timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _memory_continuity_runtime_status(
    user_hash: str | None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    observed_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)

    def read_receipt(path_key: str) -> dict[str, Any]:
        if not user_hash:
            return {
                "status": "blocked",
                "reason": "qa_identity_unavailable",
                "scope": "configured_qa_test_account",
            }
        receipt_path = (
            APP_SUPPORT_VIVENTIUM_DIR
            / "state"
            / "memory-continuity-health"
            / f"{user_hash}.{path_key}.json"
        )
        try:
            payload = json.loads(receipt_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {
                "status": "blocked",
                "reason": "no_runtime_receipt",
                "scope": "configured_qa_test_account",
            }
        receipt_status = str(payload.get("status") or "").strip().lower()
        updated_at = _parse_timestamp(payload.get("updatedAt"))
        age_seconds = (
            (observed_at - updated_at).total_seconds() if updated_at is not None else None
        )
        reason = payload.get("reason") or "invalid_runtime_receipt"
        status = "ok" if receipt_status == "ok" else "blocked"
        if receipt_status == "ok" and updated_at is None:
            status = "blocked"
            reason = "runtime_receipt_timestamp_invalid"
        elif receipt_status == "ok" and age_seconds is not None and age_seconds < -300:
            status = "blocked"
            reason = "runtime_receipt_from_future"
        elif (
            receipt_status == "ok"
            and age_seconds is not None
            and age_seconds > MEMORY_RECEIPT_MAX_AGE_SECONDS
        ):
            status = "blocked"
            reason = "runtime_receipt_stale"
        elif receipt_status == "ok" and path_key == "writer":
            writer_provider = str(payload.get("provider") or "").strip().lower()
            writer_model = str(payload.get("model") or "").strip()
            writer_effort = str(payload.get("effort") or "").strip()
            effort_required = writer_provider in {"openai", "openai_api", "openai-api", "codex"}
            if not writer_provider or not writer_model or (effort_required and not writer_effort):
                status = "blocked"
                reason = "writer_execution_tuple_incomplete"
        return {
            "status": status,
            "reason": reason,
            "updatedAt": payload.get("updatedAt"),
            "ageSeconds": int(age_seconds) if age_seconds is not None else None,
            "provider": payload.get("provider"),
            "model": payload.get("model"),
            "effort": payload.get("effort"),
            "scope": "configured_qa_test_account",
        }

    return {
        "savedMemoryRead": read_receipt("read"),
        "immediateMemoryWriter": read_receipt("writer"),
    }


def _nightly_status(user_id: str, *, now: datetime | None = None) -> dict[str, Any]:
    observed_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    try:
        rows = scheduled_prompts.list_scheduled_prompts(
            user_id=user_id or None,
            read_only=True,
        ).get("scheduledPrompts") or []
    except Exception:
        rows = []
    nightlies = [row for row in rows if row.get("templateId") == scheduled_prompts.NIGHTLY_TEMPLATE_ID]
    active = [row for row in nightlies if row.get("active") is True]
    row = active[0] if len(active) == 1 else nightlies[0] if nightlies else {}
    recent_runs = row.get("recentRuns") if isinstance(row.get("recentRuns"), list) else []
    latest_run = recent_runs[0] if recent_runs and isinstance(recent_runs[0], dict) else {}
    unknown_runs = [
        run
        for run in recent_runs
        if isinstance(run, dict)
        and str(run.get("triggerKind") or "").lower() not in {"manual", "scheduled"}
    ]
    projected_scheduled = row.get("latestScheduledRun")
    projected_manual = row.get("latestManualRun")
    # Only the storage projection can certify scheduler provenance. Recent rows may be legacy or
    # caller-labelled and remain useful diagnostics, but they cannot make the health gate green.
    latest_scheduled = (
        projected_scheduled
        if isinstance(projected_scheduled, dict) and projected_scheduled
        else {}
    )
    latest_manual = (
        projected_manual
        if isinstance(projected_manual, dict) and projected_manual
        else {}
    )
    scheduled_status = str(latest_scheduled.get("status") or "").strip().lower()
    diagnostic_status = scheduled_status or str(row.get("lastStatus") or "").strip().lower()
    failed_latest_run = scheduled_status in {
        "error",
        "failed",
        "cancelled",
        "timed_out",
        "timeout",
    }
    diagnostic_failure = diagnostic_status in {
        "error",
        "failed",
        "cancelled",
        "timed_out",
        "timeout",
    }
    definition_healthy = len(nightlies) == 1 and len(active) == 1
    reasons: list[str] = []
    if len(nightlies) != 1:
        reasons.append("nightly_definition_count_invalid")
    if len(active) != 1:
        reasons.append("nightly_active_count_invalid")
    if not latest_scheduled:
        reasons.append("scheduled_run_not_observed")
    elif str(latest_scheduled.get("triggerKind") or "").strip().lower() != "scheduled":
        reasons.append("scheduled_run_provenance_invalid")
    elif str(latest_scheduled.get("triggerSource") or "").strip().lower() != "scheduler_loop":
        reasons.append("scheduled_run_source_invalid")
    scheduled_at = _parse_timestamp(
        latest_scheduled.get("startedAt") or latest_scheduled.get("dueAt")
    )
    scheduled_age_seconds = (
        (observed_at - scheduled_at).total_seconds() if scheduled_at is not None else None
    )
    if latest_scheduled and scheduled_at is None:
        reasons.append("scheduled_run_timestamp_invalid")
    elif latest_scheduled and scheduled_age_seconds is not None:
        if scheduled_age_seconds < -300:
            reasons.append("scheduled_run_from_future")
        elif scheduled_age_seconds > NIGHTLY_RECEIPT_MAX_AGE_SECONDS:
            reasons.append("scheduled_run_stale")
    if failed_latest_run:
        reasons.append("latest_scheduled_run_failed")
    elif latest_scheduled and scheduled_status not in {"completed", "success"}:
        reasons.append("latest_scheduled_run_not_successful")
    status = "ok" if definition_healthy and not reasons else "blocked"
    manual_at = _parse_timestamp(latest_manual.get("startedAt"))
    manual_recovery_after_failure = bool(
        failed_latest_run
        and manual_at is not None
        and scheduled_at is not None
        and manual_at > scheduled_at
        and str(latest_manual.get("status") or "").strip().lower() in {"completed", "success"}
    )
    return {
        "status": status,
        "reasons": reasons,
        "definitionCount": len(nightlies),
        "activeCount": len(active),
        "lastStatus": latest_scheduled.get("status") or row.get("lastStatus"),
        "latestAnyStatus": latest_run.get("status") or row.get("lastStatus"),
        "latestScheduledStatus": latest_scheduled.get("status"),
        "latestScheduledAt": latest_scheduled.get("startedAt"),
        "latestManualStatus": latest_manual.get("status"),
        "latestManualAt": latest_manual.get("startedAt"),
        "manualRecoveryAfterScheduledFailure": manual_recovery_after_failure,
        "latestRunFailure": failed_latest_run or (not latest_scheduled and diagnostic_failure),
        "scheduledAgeSeconds": int(scheduled_age_seconds)
        if scheduled_age_seconds is not None
        else None,
        "lastErrorClass": latest_scheduled.get("errorClass")
        or (unknown_runs[0].get("errorClass") if unknown_runs else None)
        or row.get("lastErrorClass"),
        "executor": row.get("executor"),
        "executionProfile": row.get("executionProfile"),
    }


def _conversation_recall_runtime_status() -> dict[str, Any]:
    values = _runtime_env_values()
    rag_api_url = str(values.get("RAG_API_URL") or "").strip().rstrip("/")
    if not rag_api_url:
        return {"status": "blocked", "reason": "recall_runtime_unconfigured"}
    rebuild_marker = str(values.get("VIVENTIUM_RECALL_REBUILD_REQUIRED_FILE") or "").strip()
    if rebuild_marker:
        try:
            if Path(rebuild_marker).expanduser().exists():
                return {"status": "blocked", "reason": "recall_rebuild_required"}
        except OSError:
            return {"status": "blocked", "reason": "recall_rebuild_marker_unreadable"}
    try:
        with urllib.request.urlopen(
            f"{rag_api_url}/health",
            timeout=RECALL_HEALTH_TIMEOUT_SECONDS,
        ) as response:
            status_code = int(getattr(response, "status", 0) or 0)
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return {
            "status": "blocked",
            "reason": "recall_health_http_error",
            "httpStatus": int(exc.code),
        }
    except (OSError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError):
        return {"status": "blocked", "reason": "recall_health_unavailable"}
    if not isinstance(payload, dict):
        return {
            "status": "blocked",
            "reason": "recall_health_invalid_payload",
            "httpStatus": status_code,
        }
    declared_status = str(payload.get("status") or "").strip().upper()
    healthy = status_code == 200 and declared_status == "UP"
    return {
        "status": "ok" if healthy else "blocked",
        "reason": "healthy" if healthy else "recall_health_unhealthy",
        "httpStatus": status_code,
        "declaredStatus": declared_status or None,
    }


def cognitive_integrity_report(*, user_id: str) -> dict[str, Any]:
    canonical_config = APP_SUPPORT_VIVENTIUM_DIR / "config.yaml"
    runtime_drift = _safe_runtime_drift(canonical_config)
    prompt_drift = _safe_prompt_drift()
    source_contract = _provider_and_memory_contract(load_source_of_truth_librechat_yaml())
    live_config = _live_contract()
    live_contract = _provider_and_memory_contract(live_config) if live_config else {
        "providerCapabilityTransport": {"status": "blocked", "reasons": ["live_config_missing"]},
        "memoryExposure": {"status": "blocked", "reasons": ["live_config_missing"]},
    }
    qa_test_account = _qa_test_account_status()
    memory_runtime = _memory_continuity_runtime_status(qa_test_account.get("accountHash"))
    checks = {
        "runtimeConfigDrift": runtime_drift,
        "promptBundleDrift": prompt_drift,
        "sourceProviderCapabilityTransport": source_contract["providerCapabilityTransport"],
        "liveProviderCapabilityTransport": live_contract["providerCapabilityTransport"],
        "sourceMemoryExposure": source_contract["memoryExposure"],
        "liveMemoryExposure": live_contract["memoryExposure"],
        "glasshiveHostWorkerRuntime": _runtime_codex_worker_status(),
        "workbenchNightly": _nightly_status(user_id),
        "qaTestAccount": qa_test_account,
        "qaAccountSavedMemoryReadRuntime": memory_runtime["savedMemoryRead"],
        "qaAccountImmediateMemoryWriterRuntime": memory_runtime["immediateMemoryWriter"],
        "conversationRecallRuntime": _conversation_recall_runtime_status(),
        "memoryHardening": _memory_hardening_status(),
    }
    blocking = [
        key
        for key, value in checks.items()
        if value.get("status") != "ok"
    ]
    return {
        "schemaVersion": 3,
        "status": "ok" if not blocking else "blocked",
        "blockingChecks": blocking,
        "controlPlanes": list(CONTROL_PLANE_MAP),
        "checks": checks,
        "observers": [
            {
                "key": "codexObserver",
                "status": "observer_only",
                "reason": "optional_external_observer_not_a_product_control_plane",
            }
        ],
    }

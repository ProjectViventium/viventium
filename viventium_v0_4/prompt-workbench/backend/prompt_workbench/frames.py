from __future__ import annotations

import json
import os
import re
import stat
from datetime import datetime
from pathlib import Path
from typing import Any

from .paths import LIBRECHAT_ROOT


TRACE_MARKER = "[PromptFrameTraceTelemetry] "
CORE_LOGS_ROOT = LIBRECHAT_ROOT / "api" / "logs"
MAX_TRACE_LOG_FILES = 4
MAX_TRACE_LOG_READ_BYTES = 8 * 1024 * 1024
MAX_TRACE_LINE_BYTES = 8192
PROMPT_TRACE_LAYERS = (
    "main_instructions",
    "global_no_response",
    "memory_context",
    "viventium_feeling_state",
    "conversation_recall",
    "surface_prompt",
    "mcp_server_instructions",
    "tool_schemas",
    "background_context",
    "cortex_activation",
    "cortex_execution",
    "followup",
    "time_context",
    "unknown",
)
PROMPT_TRACE_SOURCE_HASHES = (
    "agent_source",
    "librechat_source",
    "compiled_runtime_config",
    "live_installed_runtime_config",
    "compiler_version",
)

_TRACE_V1_KEYS = frozenset(
    {
        "version",
        "time",
        "family",
        "surface",
        "provider",
        "model",
        "agent_id_hash",
        "request_identity_hash",
        "auth_class",
        "layer_tokens",
        "layer_hashes",
        "source_hashes",
        "flags",
        "decision",
        "mcp_instruction_source_counts",
        "voice_provider_control_marker_counts",
        "unknown_layer_count",
        "unknown_layer_set_hash",
    }
)
_TRACE_V2_ONLY_KEYS = frozenset(
    {
        "requested_provider",
        "requested_model",
        "requested_effort",
        "effective_effort",
        "fallback_used",
        "fallback_reason",
    }
)
_TRACE_V2_KEYS = _TRACE_V1_KEYS | _TRACE_V2_ONLY_KEYS
_FAMILIES = frozenset(
    {
        "main_assembly",
        "main_runtime",
        "main_run_create",
        "cortex_activation",
        "cortex_execution",
        "phase_b_followup",
        "unknown",
    }
)
_SURFACES = frozenset(
    {"web", "telegram", "voice", "workbench", "scheduler", "playground", "unknown"}
)
_AUTH_CLASSES = frozenset({"user_runtime", "connected_account_runtime", "unknown"})
_FLAG_BOOLEAN_KEYS = frozenset(
    {
        "voice_mode",
        "wing_mode",
        "listen_only",
        "primary_response_mode",
        "has_abort_signal",
        "productivity_context_isolated",
        "has_request_files",
        "no_response_injected",
        "use_voice_model",
        "ephemeral_agent",
        "telegram_surface",
        "playground_surface",
        "has_user_mcp_auth_map",
        "background_cortices_enabled",
        "tool_cortex_hold_wanted",
    }
)
_FLAG_NUMBER_KEYS = frozenset({"agent_count", "tool_count", "activated_cortex_count"})
_FLAG_HASH_KEYS = frozenset({"input_mode_hash"})
_DECISION_BOOLEAN_KEYS = frozenset(
    {"should_respond", "should_follow_up", "no_response", "tool_cortex_hold_wanted"}
)
_DECISION_NUMBER_KEYS = frozenset(
    {
        "confidence",
        "activation_count",
        "activated_count",
        "visible_insight_count",
        "silent_count",
        "error_count",
        "raw_insight_count",
        "deduped_insight_count",
    }
)
_DECISION_HASH_KEYS = frozenset({"status_hash", "decision_hash", "reason_code_hash"})
_MCP_COUNT_KEYS = frozenset({"server_fetched", "config_inline", "missing"})
_VOICE_COUNT_KEYS = frozenset(
    {"break_tags", "prosody_tags", "say_as_tags", "emotion_tags", "total"}
)
_HASH = re.compile(r"^[0-9a-f]{16}$")
_TRACE_IDENTITY = re.compile(r"^(?:[0-9a-f]{16}|missing)$")
_TRACE_ROUTE = re.compile(r"^h(?:[0-9a-f]{16}|missing)$")
_SOURCE_HASH = re.compile(r"^(?:[0-9a-f]{8,64}|missing)$")
_LAYER_HASH = re.compile(r"^(?:[0-9a-f]{16}|none|missing)$")
_UNKNOWN_HASH = re.compile(r"^(?:[0-9a-f]{16}|none)$")
_ROUTE_EFFORT = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,31}$")
_FALLBACK_REASONS = frozenset(
    {
        "none",
        "missing",
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
_TIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$")
_LOG_NAME = re.compile(r"^debug-\d{4}-\d{2}-\d{2}\.log(?:\.\d+)?$")
_TRACE_LINE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z debug: "
    + re.escape(TRACE_MARKER)
    + r"(?P<payload>.*)$"
)


def _strict_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate_json_key")
        value[key] = item
    return value


def _bounded_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and 0 <= value <= 1_000_000_000
    )


def _exact_numeric_map(value: object, keys: frozenset[str] | tuple[str, ...]) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == set(keys)
        and all(_bounded_number(item) for item in value.values())
    )


def _exact_hash_map(value: object, keys: tuple[str, ...], pattern: re.Pattern[str]) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == set(keys)
        and all(isinstance(item, str) and pattern.fullmatch(item) for item in value.values())
    )


def _typed_scalar_map(
    value: object,
    *,
    boolean_keys: frozenset[str],
    number_keys: frozenset[str],
    hash_keys: frozenset[str],
) -> bool:
    if not isinstance(value, dict):
        return False
    allowed = boolean_keys | number_keys | hash_keys
    if not set(value).issubset(allowed):
        return False
    return all(
        (key in boolean_keys and isinstance(item, bool))
        or (key in number_keys and _bounded_number(item))
        or (key in hash_keys and isinstance(item, str) and _HASH.fullmatch(item))
        for key, item in value.items()
    )


def _valid_trace(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    version = value.get("version")
    if isinstance(version, bool) or version not in (1, 2):
        return False
    expected_keys = _TRACE_V1_KEYS if version == 1 else _TRACE_V2_KEYS
    if set(value) != expected_keys:
        return False
    if version == 2:
        for key in ("requested_provider", "requested_model"):
            if not isinstance(value.get(key), str) or not _TRACE_ROUTE.fullmatch(value[key]):
                return False
        for key in ("requested_effort", "effective_effort"):
            if not isinstance(value.get(key), str) or not _ROUTE_EFFORT.fullmatch(value[key]):
                return False
        fallback_used = value.get("fallback_used")
        fallback_reason = value.get("fallback_reason")
        if not isinstance(fallback_used, bool) or fallback_reason not in _FALLBACK_REASONS:
            return False
        if fallback_used and fallback_reason == "none":
            return False
        if not fallback_used and fallback_reason not in {"none", "missing"}:
            return False
    if not isinstance(value.get("time"), str) or not _TIME.fullmatch(value["time"]):
        return False
    try:
        datetime.fromisoformat(value["time"].removesuffix("Z") + "+00:00")
    except ValueError:
        return False
    if value.get("family") not in _FAMILIES or value.get("surface") not in _SURFACES:
        return False
    if value.get("auth_class") not in _AUTH_CLASSES:
        return False
    if not isinstance(value.get("provider"), str) or not _TRACE_ROUTE.fullmatch(value["provider"]):
        return False
    if not isinstance(value.get("model"), str) or not _TRACE_ROUTE.fullmatch(value["model"]):
        return False
    for key in ("agent_id_hash", "request_identity_hash"):
        if not isinstance(value.get(key), str) or not _TRACE_IDENTITY.fullmatch(value[key]):
            return False
    if not _exact_numeric_map(value.get("layer_tokens"), PROMPT_TRACE_LAYERS):
        return False
    if not _exact_hash_map(value.get("layer_hashes"), PROMPT_TRACE_LAYERS, _LAYER_HASH):
        return False
    if not _exact_hash_map(value.get("source_hashes"), PROMPT_TRACE_SOURCE_HASHES, _SOURCE_HASH):
        return False
    if not _typed_scalar_map(
        value.get("flags"),
        boolean_keys=_FLAG_BOOLEAN_KEYS,
        number_keys=_FLAG_NUMBER_KEYS,
        hash_keys=_FLAG_HASH_KEYS,
    ):
        return False
    if not _typed_scalar_map(
        value.get("decision"),
        boolean_keys=_DECISION_BOOLEAN_KEYS,
        number_keys=_DECISION_NUMBER_KEYS,
        hash_keys=_DECISION_HASH_KEYS,
    ):
        return False
    if not _exact_numeric_map(value.get("mcp_instruction_source_counts"), _MCP_COUNT_KEYS):
        return False
    if not _exact_numeric_map(value.get("voice_provider_control_marker_counts"), _VOICE_COUNT_KEYS):
        return False
    unknown_count = value.get("unknown_layer_count")
    if (
        not isinstance(unknown_count, int)
        or isinstance(unknown_count, bool)
        or not 0 <= unknown_count <= 128
    ):
        return False
    unknown_hash = value.get("unknown_layer_set_hash")
    if not isinstance(unknown_hash, str) or not _UNKNOWN_HASH.fullmatch(unknown_hash):
        return False
    return (unknown_count == 0 and unknown_hash == "none") or (
        unknown_count > 0 and unknown_hash != "none"
    )


def _project_trace(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "time": value["time"],
        "surface": value["surface"],
        "family": value["family"],
        "provider": value["provider"],
        "model": value["model"],
        "layer_hashes": dict(value["layer_hashes"]),
        "layer_tokens": dict(value["layer_tokens"]),
        "decision": dict(value["decision"]),
    }


def _trusted_file_stat(value: os.stat_result) -> bool:
    return (
        stat.S_ISREG(value.st_mode)
        and value.st_nlink == 1
        and value.st_uid == os.geteuid()
        and not value.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
    )


def _open_trusted_log_root(logs_root: Path) -> int | None:
    nofollow = getattr(os, "O_NOFOLLOW", None)
    directory = getattr(os, "O_DIRECTORY", None)
    if nofollow is None or directory is None:
        return None
    before = logs_root.lstat()
    if (
        not stat.S_ISDIR(before.st_mode)
        or logs_root.is_symlink()
        or before.st_uid != os.geteuid()
        or before.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
    ):
        return None
    descriptor = os.open(logs_root, os.O_RDONLY | nofollow | directory)
    after = os.fstat(descriptor)
    if (
        not stat.S_ISDIR(after.st_mode)
        or after.st_uid != os.geteuid()
        or after.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
        or before.st_dev != after.st_dev
        or before.st_ino != after.st_ino
    ):
        os.close(descriptor)
        return None
    return descriptor


def _read_tail(
    path: Path,
    *,
    root_fd: int | None = None,
) -> tuple[list[str], bool] | None:
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None:
        return None
    before = (
        os.stat(path.name, dir_fd=root_fd, follow_symlinks=False)
        if root_fd is not None
        else path.lstat()
    )
    if not _trusted_file_stat(before):
        return None
    descriptor = os.open(
        path.name if root_fd is not None else path,
        os.O_RDONLY | nofollow,
        dir_fd=root_fd,
    )
    try:
        after = os.fstat(descriptor)
        if (
            not _trusted_file_stat(after)
            or before.st_dev != after.st_dev
            or before.st_ino != after.st_ino
        ):
            return None
        truncated = after.st_size > MAX_TRACE_LOG_READ_BYTES
        start = max(0, after.st_size - MAX_TRACE_LOG_READ_BYTES)
        os.lseek(descriptor, start, os.SEEK_SET)
        chunks: list[bytes] = []
        remaining = MAX_TRACE_LOG_READ_BYTES
        while remaining > 0:
            chunk = os.read(descriptor, min(64 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
    finally:
        os.close(descriptor)
    lines = b"".join(chunks).decode("utf-8", errors="replace").splitlines()
    if truncated and lines:
        lines = lines[1:]
    return lines, truncated


def _trusted_log_files(
    logs_root: Path,
    *,
    root_fd: int | None = None,
) -> tuple[list[Path], bool]:
    try:
        names = os.listdir(root_fd) if root_fd is not None else os.listdir(logs_root)
        candidates: list[tuple[int, Path]] = []
        unsafe_match = False
        for name in names:
            if not _LOG_NAME.fullmatch(name):
                continue
            candidate = logs_root / name
            candidate_stat = (
                os.stat(name, dir_fd=root_fd, follow_symlinks=False)
                if root_fd is not None
                else candidate.lstat()
            )
            if not _trusted_file_stat(candidate_stat):
                unsafe_match = True
                continue
            candidates.append((candidate_stat.st_mtime_ns, candidate))
        candidates.sort(key=lambda item: item[0], reverse=True)
        return [candidate for _, candidate in candidates[:MAX_TRACE_LOG_FILES]], not unsafe_match
    except OSError:
        return [], False


def recent_frame_snapshot(
    limit: int = 80,
    *,
    logs_root: Path | None = None,
) -> dict[str, Any]:
    root = logs_root or CORE_LOGS_ROOT
    try:
        root_fd = _open_trusted_log_root(root)
    except OSError:
        root_fd = None
    if root_fd is None:
        files, trusted = [], False
    else:
        files, trusted = _trusted_log_files(root, root_fd=root_fd)
    if not files:
        if root_fd is not None:
            os.close(root_fd)
        return {
            "frames": [],
            "health": {
                "status": "unavailable",
                "source": "core_rotated_metadata_log",
                "reason": "trusted_log_unavailable",
                "filesScanned": 0,
                "invalidEventCount": 0,
                "truncatedReadCount": 0,
                "releaseEvidence": False,
            },
        }

    projected: list[dict[str, Any]] = []
    invalid = 0
    truncated_reads = 0
    bounded_limit = max(1, min(int(limit), 200))
    try:
        for log_file in files:
            try:
                read_result = _read_tail(log_file, root_fd=root_fd)
            except OSError:
                read_result = None
            if read_result is None:
                trusted = False
                continue
            lines, truncated = read_result
            truncated_reads += int(truncated)
            for line in reversed(lines):
                trace_match = _TRACE_LINE.fullmatch(line)
                if trace_match is None:
                    continue
                encoded = trace_match.group("payload")
                if not encoded or len(encoded.encode("utf-8")) > MAX_TRACE_LINE_BYTES:
                    invalid += 1
                    continue
                try:
                    payload = json.loads(encoded, object_pairs_hook=_strict_json_object)
                except (json.JSONDecodeError, ValueError):
                    invalid += 1
                    continue
                if not _valid_trace(payload):
                    invalid += 1
                    continue
                if len(projected) < bounded_limit:
                    projected.append(_project_trace(payload))
    finally:
        os.close(root_fd)

    if not trusted:
        status = "degraded" if projected else "unavailable"
        reason = "trusted_log_rejected" if projected else "trusted_log_unavailable"
    elif invalid:
        status, reason = "degraded", "invalid_trace_events"
    elif projected:
        status, reason = "ok", "none"
    else:
        status, reason = "empty", "no_trace_events"
    return {
        "frames": projected,
        "health": {
            "status": status,
            "source": "core_rotated_metadata_log",
            "reason": reason,
            "filesScanned": len(files),
            "invalidEventCount": invalid,
            "truncatedReadCount": truncated_reads,
            "releaseEvidence": False,
        },
    }


def recent_frames(limit: int = 80) -> list[dict[str, Any]]:
    return recent_frame_snapshot(limit)["frames"]

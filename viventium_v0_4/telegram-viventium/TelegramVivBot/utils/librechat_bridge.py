# === VIVENTIUM START ===
# Feature: Telegram LibreChat Bridge
#
# Purpose:
# - Route Telegram messages through LibreChat Agents (same brain as web UI).
# - Authenticate via shared secret (no user JWT in the bot).
# - Stream responses over SSE.
#
# Added: 2026-01-13
# === VIVENTIUM END ===

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import logging
import math
import os
import re
import sqlite3
import time
import urllib.parse
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, Optional

import httpx
try:
    from utils.librechat_http import (
        async_client_options_for_url as _async_client_options_for_url,
    )
except ModuleNotFoundError:
    from TelegramVivBot.utils.librechat_http import (
        async_client_options_for_url as _async_client_options_for_url,
    )
# === VIVENTIUM START ===
# Feature: Markdown → Telegram HTML conversion (replaces fragile MarkdownV2).
try:
    from utils.telegram_html import markdown_to_html, strip_html_tags
except ModuleNotFoundError:
    from TelegramVivBot.utils.telegram_html import markdown_to_html, strip_html_tags
try:
    from utils.telegram_chunks import split_telegram_html
except ModuleNotFoundError:
    from TelegramVivBot.utils.telegram_chunks import split_telegram_html
try:
    from utils.voice import normalize_delivery_disposition
except ModuleNotFoundError:
    from TelegramVivBot.utils.voice import normalize_delivery_disposition
try:
    from utils.orchestration import default_callback_store_path
except ModuleNotFoundError:
    from TelegramVivBot.utils.orchestration import default_callback_store_path
# Legacy MarkdownV2 import kept only for backward compat if needed.
try:
    from md2tgmd.src.md2tgmd import escape as md2tgmd_escape
except ModuleNotFoundError:
    try:
        from TelegramVivBot.md2tgmd.src.md2tgmd import escape as md2tgmd_escape
    except ModuleNotFoundError:
        md2tgmd_escape = None
# === VIVENTIUM END ===

logger = logging.getLogger(__name__)
TELEGRAM_CALLBACK_INTERRUPTED_NOTICE = (
    "I couldn't finish delivering that response. Please try again."
)


@dataclass(frozen=True)
class LibreChatSession:
    stream_id: str
    conversation_id: str
    voice_route: Optional[dict[str, Any]] = None
    logical_turn_id: str = ""
    revision: Optional[int] = None
    superseded: bool = False
    delivery_disposition_required: bool = False
    input_pending: bool = False
    input_claim: Optional[dict[str, Any]] = None
    input_presentation: Optional[dict[str, Any]] = None


# === VIVENTIUM START ===
# Feature: Telegram account linking signal
class TelegramLinkRequired(Exception):
    def __init__(self, link_url: str, message: Optional[str] = None) -> None:
        self.link_url = link_url
        self.message = message or "Link your Viventium account to use Telegram."
        super().__init__(self.message)
# === VIVENTIUM END ===


class _GlassHiveDeliveryAuthorizationLost(RuntimeError):
    def __init__(self, message: str, *, transport_started: bool) -> None:
        super().__init__(message)
        self.transport_started = transport_started


class _CortexDeliveryAuthorizationLost(RuntimeError):
    pass


class _TelegramPollDeliveryStale(RuntimeError):
    pass


class _CortexTelegramAckStore:
    """Private durable outbox for Telegram receipts that Core has not accepted yet."""

    def __init__(self, path: Optional[Path] = None, *, retry_delay_s: float = 5.0) -> None:
        configured = str(os.getenv("VIVENTIUM_TELEGRAM_CORTEX_ACK_STORE_PATH") or "").strip()
        self.path = (
            Path(path)
            if path is not None
            else Path(configured).expanduser()
            if configured
            else default_callback_store_path().with_name("cortex-delivery-acks.sqlite3")
        )
        self.retry_delay_s = max(0.0, float(retry_delay_s))
        self.ttl_s = 604800.0

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.path.parent, 0o700)
        try:
            descriptor = os.open(
                self.path,
                os.O_CREAT | os.O_EXCL | os.O_RDWR | getattr(os, "O_CLOEXEC", 0),
                0o600,
            )
        except FileExistsError:
            pass
        else:
            os.close(descriptor)
        os.chmod(self.path, 0o600)
        connection = sqlite3.connect(str(self.path), timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS cortex_telegram_ack_outbox (
              ack_key TEXT PRIMARY KEY,
              payload_json TEXT NOT NULL,
              attempts INTEGER NOT NULL DEFAULT 0,
              next_attempt_at REAL NOT NULL,
              expires_at REAL NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS cortex_telegram_ack_due_idx "
            "ON cortex_telegram_ack_outbox(next_attempt_at, expires_at)"
        )
        connection.execute("CREATE TABLE IF NOT EXISTS telegram_memory_poll_cursor "
                           "(scope TEXT NOT NULL, stream_id TEXT NOT NULL, payload_json TEXT NOT NULL, "
                           "PRIMARY KEY(scope, stream_id))")
        connection.commit()
        for suffix in ("-wal", "-shm"):
            sidecar = Path(f"{self.path}{suffix}")
            if sidecar.exists():
                os.chmod(sidecar, 0o600)
        return connection

    def enqueue(self, payload: dict[str, Any]) -> str:
        payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        ack_key = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
        now = time.time()
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM cortex_telegram_ack_outbox WHERE expires_at <= ?",
                (now,),
            )
            connection.execute(
                """
                INSERT INTO cortex_telegram_ack_outbox
                  (ack_key, payload_json, attempts, next_attempt_at, expires_at)
                VALUES (?, ?, 0, ?, ?)
                ON CONFLICT(ack_key) DO UPDATE SET
                  payload_json = excluded.payload_json,
                  expires_at = MAX(expires_at, excluded.expires_at)
                """,
                (ack_key, payload_json, now + self.retry_delay_s, now + self.ttl_s),
            )
        return ack_key

    def due(self, limit: int = 25) -> list[tuple[str, dict[str, Any]]]:
        now = time.time()
        bounded_limit = max(1, min(int(limit), 100))
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM cortex_telegram_ack_outbox WHERE expires_at <= ?",
                (now,),
            )
            rows = connection.execute(
                """
                SELECT ack_key, payload_json
                FROM cortex_telegram_ack_outbox
                WHERE next_attempt_at <= ?
                ORDER BY next_attempt_at, ack_key
                LIMIT ?
                """,
                (now, bounded_limit),
            ).fetchall()
            if rows:
                connection.executemany(
                    """
                    UPDATE cortex_telegram_ack_outbox
                    SET attempts = attempts + 1, next_attempt_at = ?
                    WHERE ack_key = ?
                    """,
                    [(now + self.retry_delay_s, row["ack_key"]) for row in rows],
                )
        return [(row["ack_key"], json.loads(row["payload_json"])) for row in rows]

    def mark_done(self, ack_key: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM cortex_telegram_ack_outbox WHERE ack_key = ?",
                (str(ack_key),),
            )

    def pending_count(self) -> int:
        with self._connect() as connection:
            return int(
                connection.execute("SELECT COUNT(*) FROM cortex_telegram_ack_outbox").fetchone()[0]
            )

    def save_memory_poll(self, scope: str, stream_id: str, payload: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute("INSERT INTO telegram_memory_poll_cursor VALUES (?, ?, ?) "
                               "ON CONFLICT(scope, stream_id) DO UPDATE SET payload_json=excluded.payload_json",
                               (scope, stream_id, json.dumps(payload, separators=(",", ":"))))

    def pending_memory_polls(self, scope: str) -> list[tuple[str, dict[str, Any]]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT stream_id, payload_json FROM telegram_memory_poll_cursor "
                                      "WHERE scope=? ORDER BY stream_id", (scope,)).fetchall()
        return [(row["stream_id"], json.loads(row["payload_json"])) for row in rows]

    def finish_memory_poll(self, scope: str, stream_id: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM telegram_memory_poll_cursor WHERE scope=? AND stream_id=?", (scope, stream_id))


# === VIVENTIUM START ===
# Feature: LibreChat-aligned citation cleanup for Telegram.
_CITATION_COMPOSITE_RE = re.compile(
    r"(?:\\ue200|ue200|\ue200).*?(?:\\ue201|ue201|\ue201)",
    re.IGNORECASE,
)
_CITATION_STANDALONE_RE = re.compile(
    r"(?:\\ue202|ue202|\ue202)turn\d+[A-Za-z]+\d+",
    re.IGNORECASE,
)
_CITATION_CLEANUP_RE = re.compile(
    r"(?:\\ue2(?:00|01|02|03|04|06)|ue2(?:00|01|02|03|04|06)|[\ue200-\ue206])",
    re.IGNORECASE,
)
_BRACKET_CITATION_RE = re.compile(r"\[(\d{1,3})\](?=\s|$)")
_MARKDOWN_CODE_SPAN_RE = re.compile(r"```[\s\S]*?```|`[^`\n]*`")
_EM_DASH_RE = re.compile("—")
_EM_DASH_OPENERS = "\"'“‘([{"
# Voice-control markup is model-authored text for expressive TTS. It must not be
# shown to Telegram users when a voice-routed response is displayed as text.
_VOICE_SPEAK_RE = re.compile(r"</?speak[^>]*>", re.IGNORECASE)
_VOICE_EMOTION_SELF_CLOSING_RE = re.compile(
    r'<emotion\s+value=["\']?[^"\'>]+["\']?\s*/>',
    re.IGNORECASE,
)
_VOICE_EMOTION_WRAP_RE = re.compile(
    r'<emotion\s+value=["\']?[^"\'>]+["\']?\s*>([\s\S]*?)</emotion>',
    re.IGNORECASE,
)
_VOICE_BREAK_RE = re.compile(r'<break\s+time=["\']?[^"\'>]+["\']?\s*/>', re.IGNORECASE)
_VOICE_SPEED_RE = re.compile(r'<speed\s+ratio=["\']?[^"\'>]+["\']?\s*/>', re.IGNORECASE)
_VOICE_VOLUME_RE = re.compile(r'<volume\s+ratio=["\']?[^"\'>]+["\']?\s*/>', re.IGNORECASE)
_VOICE_SPELL_RE = re.compile(r"<spell>([\s\S]*?)</spell>", re.IGNORECASE)
_VOICE_BRACKET_RE = re.compile(r"\[([A-Za-z][A-Za-z' -]{1,40})\]")
_XAI_TTS_CAPABILITIES_PATH = (
    Path(__file__).resolve().parents[3] / "shared" / "voice" / "xai_tts_capabilities.json"
)


def _load_xai_wrapping_tag_names() -> tuple[str, ...]:
    try:
        with _XAI_TTS_CAPABILITIES_PATH.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        tags = ((payload or {}).get("speech_tags") or {}).get("wrapping") or []
        return tuple(
            str(tag).strip().lower()
            for tag in tags
            if isinstance(tag, str) and str(tag).strip()
        )
    except Exception:
        return (
            "soft",
            "whisper",
            "loud",
            "build-intensity",
            "decrease-intensity",
            "higher-pitch",
            "lower-pitch",
            "slow",
            "fast",
            "sing-song",
            "singing",
            "laugh-speak",
            "emphasis",
        )


_XAI_WRAPPING_TAG_NAMES = _load_xai_wrapping_tag_names()
_XAI_TAG_PATTERN = "|".join(re.escape(tag) for tag in _XAI_WRAPPING_TAG_NAMES)
_VOICE_XAI_WRAPPER_RE = re.compile(
    r"<(?P<tag>%s)>(?P<text>[\s\S]*?)</(?P=tag)>" % _XAI_TAG_PATTERN,
    re.IGNORECASE,
)
_VOICE_XAI_ANGLE_TAG_RE = re.compile(r"</?(?:%s)\s*>" % _XAI_TAG_PATTERN, re.IGNORECASE)
_VOICE_XAI_BRACKET_TAG_RE = re.compile(r"\[\s*/?\s*(?:%s)\s*\]" % _XAI_TAG_PATTERN, re.IGNORECASE)
_TOOL_TRANSCRIPT_LINE_RE = re.compile(
    r"^\s*Tool:\s+(?P<body>.*)$",
    re.IGNORECASE,
)
_TOOL_XML_INVOKE_BLOCK_RE = re.compile(
    r"<(?:invoke|tool_call)\b[^>]*>[\s\S]*?</(?:invoke|tool_call)>",
    re.IGNORECASE,
)
_TOOL_JSON_FENCE_RE = re.compile(
    r"```(?:json|tool|tool_call)?\s*\n\s*\{[\s\S]*?\"(?:tool_call|tool|arguments|args)\"[\s\S]*?\}\s*```",
    re.IGNORECASE,
)
_GLASSHIVE_MCP_SERVER_TOKEN = "_mcp_glasshive-workers-projects"
_GLASSHIVE_RAW_TOOL_NAMES = {
    "metrics_summary",
    "projects_list",
    "run_get",
    "worker_create",
    "worker_delegate_once",
    "worker_desktop_action",
    "worker_find_or_resume",
    "worker_get",
    "worker_interrupt",
    "worker_live",
    "worker_message",
    "worker_pause",
    "worker_resume",
    "worker_run",
    "worker_takeover",
    "worker_terminate",
    "workers_list",
    "workspace_artifact_download",
    "workspace_artifacts",
    "workspace_continue",
    "workspace_launch",
    "workspace_pause",
    "workspace_preferences_get",
    "workspace_preferences_set",
    "workspace_resume",
    "workspace_schedule",
    "workspace_status",
    "workspace_terminate",
    "workspace_wait",
}
_GLASSHIVE_RAW_TOOL_TOKEN_RE = re.compile(r"\b[A-Za-z0-9_.-]+\b")
# === VIVENTIUM END ===

# === VIVENTIUM START ===
# Feature: Minimal MarkdownV2 escaping for bot-authored follow-ups.
_MARKDOWN_V2_ESCAPE_RE = re.compile(r"([_*\[\]()~`>#+\-=|{}.!])")
_MARKDOWN_V2_ESCAPED_RE = re.compile(r"(\\[_*\[\]()~`>#+\-=|{}.!])")
_MARKDOWN_V2_UNESCAPE_RE = re.compile(r"\\([_*\[\]()~`>#+\-=|{}.!])")
# === VIVENTIUM END ===
# === VIVENTIUM START ===
# Feature: Cortex part detection for DB-backed follow-up polling.
_CORTEX_PART_TYPES = {"cortex_activation", "cortex_brewing", "cortex_insight"}
_ACTIVE_CORTEX_STATUSES = {"activating", "brewing"}
_TERMINAL_CORTEX_FOLLOWUP_DECISION_RESULTS = {"suppressed", "empty", "skipped"}
_GLASSHIVE_MCP_SERVER = "glasshive-workers-projects"
_TERMINAL_GLASSHIVE_CALLBACK_EVENTS = {
    "run.completed",
    "run.failed",
    "run.cancelled",
    "run.interrupted",
    "checkpoint.ready",
    "takeover.requested",
    "artifact.created",
}
_CLAIM_AUTHORIZED_GLASSHIVE_ATTENTION_EVENTS = {
    "run.needs_input",
    "run.blocked",
}
# === VIVENTIUM END ===


def terminal_cortex_followup_decision(decision: Any) -> Optional[dict[str, Any]]:
    if not isinstance(decision, dict):
        return None
    result = str(decision.get("result") or "").strip().lower()
    if result in _TERMINAL_CORTEX_FOLLOWUP_DECISION_RESULTS:
        return decision
    return None

# === VIVENTIUM START ===
# Feature: No-response tag ({NTA}) suppression for passive/background follow-ups.
import sys
from pathlib import Path

_SHARED_PATH = Path(__file__).resolve().parents[3] / "shared"  # .../viventium_v0_4/shared
if str(_SHARED_PATH) not in sys.path:
    sys.path.insert(0, str(_SHARED_PATH))

from delivery_controls import (
    parse_delivery_controls,
    strip_delivery_controls_for_preview,
    strip_incomplete_control_suffix,
)

try:
    from no_response import NO_RESPONSE_TAG, is_no_response_only, strip_trailing_nta
    from insights import format_insights_fallback_text
except Exception:
    NO_RESPONSE_TAG = "{NTA}"
    _NO_RESPONSE_TAG_RE = re.compile(r"^\s*\{\s*NTA\s*\}\s*$", re.IGNORECASE)
    _NO_RESPONSE_PHRASES = {
        "nothing new to add.",
        "nothing new to add",
        "nothing to add.",
        "nothing to add",
    }
    _NO_RESPONSE_VARIANT_MAX_LEN = 200
    _NO_RESPONSE_VARIANT_RE = re.compile(
        r"^\s*nothing\s+(?:new\s+)?to\s+add"
        r"(?:\s*(?:\(\s*)?(?:right\s+now|for\s+now|at\s+this\s+time|at\s+the\s+moment|currently|so\s+far|yet|today)(?:\s*\))?)?"
        r"(?:\s*,?\s*(?:sorry|thanks|thank\s+you))?"
        r"\s*[.!?]*\s*$",
        re.IGNORECASE,
    )

    def is_no_response_only(text: Optional[str]) -> bool:
        if not isinstance(text, str):
            return False
        trimmed = text.strip()
        if not trimmed:
            return False
        if _NO_RESPONSE_TAG_RE.match(trimmed):
            return True
        lowered = trimmed.lower()
        if lowered in _NO_RESPONSE_PHRASES:
            return True
        if len(trimmed) <= _NO_RESPONSE_VARIANT_MAX_LEN and _NO_RESPONSE_VARIANT_RE.match(trimmed):
            return True
        return False

    _TRAILING_NTA_RE_FALLBACK = re.compile(r"\s*\{\s*NTA\s*\}\s*$", re.IGNORECASE)

    def strip_trailing_nta(text: Optional[str]) -> str:
        if not isinstance(text, str):
            return text or ""
        if is_no_response_only(text):
            return text
        return _TRAILING_NTA_RE_FALLBACK.sub("", text).rstrip()

    def format_insights_fallback_text(
        insights: Optional[list[dict[str, Any]]],
        *,
        voice_mode: bool = False,
    ) -> str:
        if not insights:
            return ""
        texts: list[str] = []
        for item in insights:
            if not isinstance(item, dict):
                continue
            text = item.get("insight")
            if not isinstance(text, str):
                continue
            cleaned = text.strip()
            if cleaned:
                texts.append(cleaned)
        if not texts:
            return ""
        return " ".join(texts) if voice_mode else "\n\n".join(texts)

# === VIVENTIUM END ===


def sanitize_telegram_text(
    text: str,
    *,
    preserve_delivery_controls: bool = False,
    streaming_preview: bool = False,
) -> str:
    if not text:
        return ""
    if preserve_delivery_controls:
        cleaned = text
    else:
        delivery_source = (
            strip_incomplete_control_suffix(text) if streaming_preview else text
        )
        delivery_plan = parse_delivery_controls(delivery_source)
        has_delivery_controls = bool(
            delivery_plan.skip_voice_count
            or delivery_plan.message_break_count
            or delivery_plan.merged_break_count
        )
        if delivery_source != text or has_delivery_controls:
            cleaned = delivery_plan.clean_text
        else:
            cleaned = text
    cleaned = _strip_tool_transcript_lines(cleaned)
    cleaned = _TOOL_XML_INVOKE_BLOCK_RE.sub(
        lambda match: "" if _contains_glasshive_raw_tool_name(match.group(0)) else match.group(0),
        cleaned,
    )
    cleaned = _TOOL_JSON_FENCE_RE.sub(
        lambda match: "" if _contains_glasshive_raw_tool_name(match.group(0)) else match.group(0),
        cleaned,
    )
    cleaned = _CITATION_COMPOSITE_RE.sub(" ", cleaned)
    cleaned = _CITATION_STANDALONE_RE.sub(" ", cleaned)
    cleaned = _CITATION_CLEANUP_RE.sub(" ", cleaned)
    cleaned = _BRACKET_CITATION_RE.sub(" ", cleaned)
    cleaned = _apply_outside_markdown_code(cleaned, _normalize_em_dashes_for_telegram)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned


def _contains_glasshive_raw_tool_name(text: str) -> bool:
    lowered = text.lower()
    if _GLASSHIVE_MCP_SERVER_TOKEN in lowered:
        return True
    return any(
        match.group(0).lower() in _GLASSHIVE_RAW_TOOL_NAMES
        for match in _GLASSHIVE_RAW_TOOL_TOKEN_RE.finditer(text)
    )


def _strip_tool_transcript_lines(text: str) -> str:
    kept: list[str] = []
    for line in text.splitlines(keepends=True):
        body = line[:-1] if line.endswith("\n") else line
        if body.endswith("\r"):
            body = body[:-1]
        match = _TOOL_TRANSCRIPT_LINE_RE.match(body)
        if match and _contains_glasshive_raw_tool_name(match.group("body")):
            continue
        kept.append(line)
    return "".join(kept)


def strip_voice_control_tags_for_display(text: str) -> str:
    if not text:
        return ""
    cleaned = _VOICE_SPEAK_RE.sub("", text)
    cleaned = _VOICE_EMOTION_WRAP_RE.sub(r"\1", cleaned)
    cleaned = _VOICE_EMOTION_SELF_CLOSING_RE.sub("", cleaned)
    cleaned = _VOICE_BREAK_RE.sub("", cleaned)
    cleaned = _VOICE_SPEED_RE.sub("", cleaned)
    cleaned = _VOICE_VOLUME_RE.sub("", cleaned)
    cleaned = _VOICE_SPELL_RE.sub(r"\1", cleaned)
    while True:
        updated = _VOICE_XAI_WRAPPER_RE.sub(lambda match: match.group("text") or "", cleaned)
        if updated == cleaned:
            break
        cleaned = updated
    cleaned = _VOICE_XAI_ANGLE_TAG_RE.sub("", cleaned)
    cleaned = _VOICE_XAI_BRACKET_TAG_RE.sub("", cleaned)
    cleaned = _VOICE_BRACKET_RE.sub(_strip_voice_bracket_marker, cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned.strip()


def apply_structured_delivery_controls(text: str, delivery_controls: Any) -> str:
    """Rebuild transport-only controls from clean persisted Phase B metadata."""
    if not isinstance(text, str) or not isinstance(delivery_controls, dict):
        return text
    segments = delivery_controls.get("segments")
    clean_segments = (
        [segment for segment in segments if isinstance(segment, str) and segment.strip()]
        if isinstance(segments, list)
        else []
    )
    rebuilt = "\n{MSG_BREAK}\n".join(clean_segments) if clean_segments else text
    if delivery_controls.get("skipVoice") is True:
        rebuilt = f"{rebuilt}\n{{SKIP_VOICE}}"
    return rebuilt


def _strip_voice_bracket_marker(match: re.Match[str]) -> str:
    marker = match.group(1).strip()
    if not marker:
        return match.group(0)
    if marker != marker.lower():
        return match.group(0)
    if any(char.isdigit() for char in marker):
        return match.group(0)
    words = [word for word in marker.split() if word]
    if len(words) > 3:
        return match.group(0)
    alpha_count = sum(1 for char in marker if char.isalpha())
    if alpha_count < 3 or alpha_count > 24:
        return match.group(0)
    return ""


def sanitize_telegram_display_text(text: str) -> str:
    return strip_voice_control_tags_for_display(sanitize_telegram_text(text))


def _apply_outside_markdown_code(text: str, transform: Callable[[str], str]) -> str:
    if not text:
        return ""
    parts: list[str] = []
    last_index = 0
    for match in _MARKDOWN_CODE_SPAN_RE.finditer(text):
        parts.append(transform(text[last_index:match.start()]))
        parts.append(match.group(0))
        last_index = match.end()
    parts.append(transform(text[last_index:]))
    return "".join(parts)


def _normalize_em_dashes_for_telegram(text: str) -> str:
    if "—" not in text:
        return text

    parts: list[str] = []
    last_index = 0
    for match in _EM_DASH_RE.finditer(text):
        dash_index = match.start()
        segment = text[last_index:dash_index].rstrip(" \t")
        if segment:
            parts.append(segment)

        next_index = match.end()
        while next_index < len(text) and text[next_index] in " \t":
            next_index += 1

        lookahead_index = next_index
        while lookahead_index < len(text) and text[lookahead_index] in _EM_DASH_OPENERS:
            lookahead_index += 1

        prev_has_space = dash_index > 0 and text[dash_index - 1] in " \t"
        next_has_space = dash_index + 1 < len(text) and text[dash_index + 1] in " \t"
        next_char = text[lookahead_index] if lookahead_index < len(text) else ""
        replacement = ", " if prev_has_space or next_has_space or next_char.isupper() else " "
        parts.append(replacement)
        last_index = next_index

    parts.append(text[last_index:])
    return "".join(parts)


# === VIVENTIUM START ===
def _escape_markdown_v2(text: str) -> str:
    if not text:
        return ""
    return _MARKDOWN_V2_ESCAPE_RE.sub(r"\\\1", text)

def _looks_markdown_v2_escaped(text: str) -> bool:
    if not text:
        return False
    return len(_MARKDOWN_V2_ESCAPED_RE.findall(text)) >= 3


def _strip_markdown(text: str) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"```[\s\S]*?```", " ", text)
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
    cleaned = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", cleaned)
    cleaned = re.sub(r"[\*_~]+", "", cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = _MARKDOWN_V2_UNESCAPE_RE.sub(r"\1", cleaned)
    return cleaned.strip()
# === VIVENTIUM END ===

# === VIVENTIUM START ===
# Feature: Convert standard Markdown to Telegram HTML (robust replacement for MarkdownV2).
# MarkdownV2 required 17 characters to be perfectly escaped — any miss caused total parse failure.
# HTML only needs 3 (<, >, &) and degrades gracefully on edge cases.
def render_telegram_markdown(
    text: str,
    *,
    strip_voice_markup: bool = False,
    streaming_preview: bool = False,
) -> str:
    cleaned = sanitize_telegram_text(text, streaming_preview=streaming_preview)
    if strip_voice_markup:
        cleaned = strip_voice_control_tags_for_display(cleaned)
    if not cleaned:
        return ""
    return markdown_to_html(cleaned)
# === VIVENTIUM END ===


def _iter_sse_events_from_text(buffer: str) -> tuple[list[dict[str, str]], str]:
    events: list[dict[str, str]] = []
    while True:
        sep = buffer.find("\n\n")
        if sep < 0:
            return events, buffer
        block = buffer[:sep]
        buffer = buffer[sep + 2 :]

        event_name: Optional[str] = None
        data_lines: list[str] = []
        for raw_line in block.splitlines():
            line = raw_line.strip("\r")
            if not line:
                continue
            if line.startswith("event:"):
                event_name = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data_lines.append(line[len("data:") :].lstrip())

        if event_name is None:
            event_name = "message"
        events.append({"event": event_name, "data": "\n".join(data_lines)})


async def iter_sse_json_events(
    *,
    chunk_iter: AsyncIterator[bytes],
    max_buffer_bytes: int = 2_000_000,
) -> AsyncIterator[dict[str, Any]]:
    buf = ""
    async for chunk in chunk_iter:
        if not chunk:
            continue
        buf += chunk.decode("utf-8", errors="ignore")
        if len(buf) > max_buffer_bytes:
            buf = buf[-max_buffer_bytes:]

        events, buf = _iter_sse_events_from_text(buf)
        for ev in events:
            data = ev.get("data")
            if not data:
                continue
            # Telegram gateway wraps all internal events inside "event: message",
            # but keep this parser flexible for direct SSE events too.
            if ev.get("event") not in ("message", "error", "attachment"):
                continue
            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                if ev.get("event") == "error":
                    payload = {"error": data}
                else:
                    continue
            if isinstance(payload, dict):
                if ev.get("event") != "message":
                    payload["_sse_event"] = ev.get("event")
                yield payload


def extract_text_deltas(payload: dict[str, Any]) -> list[str]:
    out: list[str] = []

    text = payload.get("text")
    if isinstance(text, str) and text:
        out.append(sanitize_telegram_text(text, preserve_delivery_controls=True))
        return out

    event = payload.get("event")
    if event != "on_message_delta":
        return out

    data = payload.get("data")
    if not isinstance(data, dict):
        return out

    delta = data.get("delta")
    if not isinstance(delta, dict):
        return out

    content = delta.get("content")
    parts: list[Any]
    if isinstance(content, list):
        parts = content
    elif isinstance(content, dict):
        parts = [content]
    else:
        return out

    for part in parts:
        if not isinstance(part, dict):
            continue
        ptext = part.get("text")
        if isinstance(ptext, str) and ptext:
            out.append(sanitize_telegram_text(ptext, preserve_delivery_controls=True))
            continue
        if isinstance(ptext, dict):
            val = ptext.get("value")
            if isinstance(val, str) and val:
                out.append(sanitize_telegram_text(val, preserve_delivery_controls=True))

    return out


# === VIVENTIUM START ===
# Feature: Attachment extraction for Telegram (files/images generated in LibreChat).
def _is_file_attachment_payload(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    file_id = value.get("file_id")
    filepath = value.get("filepath")
    if isinstance(file_id, str) and file_id.strip():
        return True
    if isinstance(filepath, str) and filepath.strip():
        return True
    return False


# === VIVENTIUM START ===
# Feature: Durable saved-memory receipt for Telegram.
# Purpose: Main's prose never proves a save. The detached memory writer persists a structured
# receipt on the response message, the follow-up poll projects it as `memoryReceipt`, and this
# renders exactly that truth once per turn: saved keys, a typed failure, or a partial apply.
# === VIVENTIUM END ===
_MEMORY_RECEIPT_FAILURE_TEXT = {
    **dict.fromkeys(
        ("usage_limit_reached", "insufficient_quota", "billing_hard_limit_reached", "provider_quota_exhausted"),
        "{provider} usage limit reached. Check usage or wait for the limit to reset.",
    ),
    **dict.fromkeys(
        ("provider_auth", "provider_auth_missing", "provider_unauthorized", "authentication_error"),
        "{provider} needs sign-in. Reconnect it in Connected Accounts.",
    ),
    **dict.fromkeys(
        ("provider_rate_limited", "rate_limit_exceeded", "rate_limit_error",
         "provider_temporarily_unavailable", "server_is_overloaded"),
        "{provider} is temporarily unavailable. Try again shortly.",
    ),
    "provider_access_denied": "{provider} denied access. Check the account's access.",
    "provider_unavailable": "{provider} could not save memory. Try again later.",
    "writer_unavailable": "No memory writer was available.",
    "writer_exception": "The memory writer failed.",
    "writer_interrupted": "The save did not finish.",
    "writer_recovery_not_safe": "The source, settings, access, or memory changed before the save could resume.",
    "memory_error": "The memory update could not be saved.",
}


def format_memory_receipt_text(receipt: Any) -> str:
    """Render public fields from LibreChat's receipt projection, never raw error payloads."""

    if not isinstance(receipt, dict):
        return ""
    status = str(receipt.get("status") or "").strip().lower()
    raw_keys = receipt.get("keys")
    keys = [
        str(key).strip()
        for key in (raw_keys if isinstance(raw_keys, list) else [])
        if str(key).strip()
    ]
    if status == "saved":
        return "🧠 Saved to memory: " + ", ".join(keys[:12]) if keys else ""
    if status not in {"failed", "partial", "uncertain"}:
        return ""

    raw_failures = receipt.get("failures")
    failures = [item for item in raw_failures if isinstance(item, dict)] if isinstance(raw_failures, list) else []
    if not failures:
        failures = [{"errorType": receipt.get("errorType")}]
    reasons = []
    for failure in failures:
        error_type = str(failure.get("errorType") or "").strip().lower()
        template = _MEMORY_RECEIPT_FAILURE_TEXT.get(error_type) or "Memory could not be saved. Try again."
        # The host derives this label from its provider registry; it never forwards a raw error label.
        provider = failure.get("providerLabel")
        provider = provider if isinstance(provider, str) and failure.get("provider") else "Provider"
        reasons.append(template.format(provider=provider))

    heading = "⚠️ Not saved to memory."
    if status == "partial":
        saved = f" (saved: {', '.join(keys[:12])})" if keys else ""
        heading = f"⚠️ Memory only partially saved{saved}."
    elif status == "uncertain":
        heading = "⚠️ Memory saving was interrupted."
    if status in {"partial", "uncertain"}:
        reasons.append("Some changes may already be saved. Check Memories before retrying.")
    return "\n".join([heading, *reasons])


def extract_attachments(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract attachment objects from either streamed 'attachment' events or final payloads."""
    out: list[dict[str, Any]] = []

    # Direct SSE attachment events: event: attachment; data: {...}
    if payload.get("_sse_event") == "attachment":
        candidate = {k: v for k, v in payload.items() if k != "_sse_event"}
        if _is_file_attachment_payload(candidate):
            out.append(candidate)
        return out

    # Streamed attachment events from GenerationJobManager: { event: "attachment", data: {...} }
    if payload.get("event") == "attachment":
        data = payload.get("data")
        if _is_file_attachment_payload(data):
            out.append(data)
        elif isinstance(data, list):
            out.extend([item for item in data if _is_file_attachment_payload(item)])
        return out

    # Final payload may embed attachments under responseMessage (message shape).
    if not payload.get("final"):
        return out

    response = payload.get("responseMessage")
    if isinstance(response, dict):
        attachments = response.get("attachments")
        if isinstance(attachments, list):
            out.extend([item for item in attachments if _is_file_attachment_payload(item)])

    # Some payload variants may include attachments at the top-level.
    attachments = payload.get("attachments")
    if isinstance(attachments, list):
        out.extend([item for item in attachments if _is_file_attachment_payload(item)])

    return out


def extract_delivery_disposition(
    payload: dict[str, Any],
    *,
    required: bool = False,
) -> dict[str, Any]:
    """Validate final-response delivery metadata for the Telegram adapter."""

    candidate: Any = None
    present = False
    containers: list[Any] = [payload]
    response_message = payload.get("responseMessage")
    if isinstance(response_message, dict):
        containers.append(response_message)
    for container in containers:
        metadata = container.get("metadata") if isinstance(container, dict) else None
        viventium = metadata.get("viventium") if isinstance(metadata, dict) else None
        if isinstance(viventium, dict) and "deliveryDisposition" in viventium:
            candidate = viventium.get("deliveryDisposition")
            present = True
            break

    candidate_required = bool(
        isinstance(candidate, dict) and candidate.get("required") is True
    )
    effective_required = bool(required or candidate_required)
    normalized = normalize_delivery_disposition(candidate)
    if required and normalized is not None and normalized["required"] is not True:
        normalized = None
    return {
        "type": "delivery_disposition",
        "delivery_disposition": normalized,
        "required": effective_required,
        "present": present,
    }


def _normalize_voice_route(payload: Any) -> Optional[dict[str, Any]]:
    if not isinstance(payload, dict):
        return None

    normalized: dict[str, Any] = {}
    for modality in ("stt", "tts"):
        value = payload.get(modality)
        if not isinstance(value, dict):
            continue
        provider = value.get("provider")
        variant = value.get("variant")
        provider_text = provider.strip() if isinstance(provider, str) else ""
        variant_text = variant.strip() if isinstance(variant, str) else ""
        if provider_text or variant_text:
            normalized[modality] = {
                "provider": provider_text or None,
                "variant": variant_text or None,
            }

    return normalized or None
# === VIVENTIUM END ===


def extract_cortex_insight(payload: dict[str, Any]) -> Optional[dict[str, Any]]:
    if payload.get("event") != "on_cortex_update":
        return None
    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    if data.get("status") != "complete":
        return None
    insight = data.get("insight")
    if not insight:
        return None
    return data


# === VIVENTIUM START ===
# Feature: Cortex follow-up event handling for Telegram.
def extract_cortex_followup(payload: dict[str, Any]) -> Optional[str]:
    if payload.get("event") != "on_cortex_followup":
        return None
    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    text = data.get("text")
    if isinstance(text, str) and text.strip():
        return sanitize_telegram_text(text)
    return None


def extract_cortex_followup_delivery(payload: dict[str, Any]) -> Optional[dict[str, Any]]:
    text = extract_cortex_followup(payload)
    data = payload.get("data")
    if not text or not isinstance(data, dict):
        return None
    logical_turn_id = data.get("logicalTurnId")
    logical_turn_revision = data.get("logicalTurnRevision")
    presentation = data.get("cortexPresentation")
    if (
        not isinstance(logical_turn_id, str)
        or not logical_turn_id.strip()
        or not isinstance(logical_turn_revision, int)
        or isinstance(logical_turn_revision, bool)
        or logical_turn_revision < 1
        or not isinstance(presentation, dict)
    ):
        return None
    required_strings = (
        "ownerId",
        "messageId",
        "parentMessageId",
        "claimToken",
        "presentationLeaseToken",
    )
    if any(
        not isinstance(presentation.get(key), str) or not presentation[key].strip()
        for key in required_strings
    ):
        return None
    if any(
        not isinstance(presentation.get(key), int)
        or isinstance(presentation[key], bool)
        or presentation[key] < 1
        for key in ("revision", "generation")
    ):
        return None
    delivery_ids = presentation.get("deliveryIds")
    delivery_receipts = presentation.get("deliveryReceipts")
    if (
        not isinstance(delivery_ids, list)
        or not 1 <= len(delivery_ids) <= 32
        or any(not isinstance(value, str) or not value.strip() for value in delivery_ids)
        or len(set(delivery_ids)) != len(delivery_ids)
        or not isinstance(delivery_receipts, list)
        or len(delivery_receipts) != len(delivery_ids)
    ):
        return None
    sorted_ids = sorted(delivery_ids)
    normalized_receipts = sorted(
        (
            {
                "deliveryId": receipt.get("deliveryId") if isinstance(receipt, dict) else None,
                "graphResultHash": (
                    str(receipt.get("graphResultHash") or "").strip().lower()
                    if isinstance(receipt, dict)
                    else ""
                ),
            }
            for receipt in delivery_receipts
        ),
        key=lambda receipt: str(receipt["deliveryId"] or ""),
    )
    if any(
        receipt["deliveryId"] != sorted_ids[index]
        or not re.fullmatch(r"[a-f0-9]{64}", receipt["graphResultHash"])
        for index, receipt in enumerate(normalized_receipts)
    ):
        return None
    normalized_presentation = {
        **presentation,
        "deliveryIds": sorted_ids,
        "deliveryReceipts": normalized_receipts,
    }
    return {
        **data,
        "text": text,
        "logicalTurnId": logical_turn_id.strip(),
        "cortexPresentation": normalized_presentation,
    }
# === VIVENTIUM END ===


# === VIVENTIUM START ===
# Feature: Cortex part extraction helpers for follow-up polling.
def extract_cortex_parts(content: Any) -> list[dict[str, Any]]:
    if not isinstance(content, list):
        return []
    return [
        part
        for part in content
        if isinstance(part, dict) and part.get("type") in _CORTEX_PART_TYPES
    ]


def _extract_tool_call_name(part: Any) -> str:
    if not isinstance(part, dict):
        return ""
    tool_call = part.get("tool_call") or part.get("toolCall") or part.get("tool") or part
    if not isinstance(tool_call, dict):
        return ""
    candidates = [
        tool_call.get("name"),
        (tool_call.get("function") or {}).get("name") if isinstance(tool_call.get("function"), dict) else None,
        tool_call.get("toolName"),
        part.get("name"),
        (part.get("function") or {}).get("name") if isinstance(part.get("function"), dict) else None,
        part.get("toolName"),
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return ""


def _is_glasshive_tool_name(name: str) -> bool:
    if not name:
        return False
    parts = name.split("_mcp_", 1)
    return len(parts) == 2 and parts[1] == _GLASSHIVE_MCP_SERVER


def _iter_tool_call_parts(value: Any):
    if isinstance(value, list):
        for item in value:
            yield from _iter_tool_call_parts(item)
        return
    if not isinstance(value, dict):
        return
    if value.get("type") == "tool_call":
        yield value
    for child in value.values():
        if isinstance(child, (dict, list)):
            yield from _iter_tool_call_parts(child)


def payload_has_glasshive_tool_call(payload: dict[str, Any]) -> bool:
    for part in _iter_tool_call_parts(payload):
        if _is_glasshive_tool_name(_extract_tool_call_name(part)):
            return True
    return False


def glasshive_callback_is_terminal(latest: dict[str, Any]) -> bool:
    event = str(latest.get("event") or "").strip()
    return not event or event in _TERMINAL_GLASSHIVE_CALLBACK_EVENTS


def has_active_cortex(parts: list[dict[str, Any]]) -> bool:
    return any(part.get("status") in _ACTIVE_CORTEX_STATUSES for part in parts)


def extract_completed_cortex_insights(parts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    insights: list[dict[str, Any]] = []
    for part in parts:
        if part.get("type") != "cortex_insight":
            continue
        if part.get("status") != "complete":
            continue
        insight = part.get("insight")
        if not isinstance(insight, str) or not insight.strip():
            continue
        insights.append(
            {
                "cortex_id": part.get("cortex_id") or part.get("cortexId") or "",
                "cortex_name": part.get("cortex_name") or part.get("cortexName") or "Background Insight",
                "insight": insight.strip(),
            }
        )
    return insights


def extract_response_message_id(payload: dict[str, Any]) -> str:
    if not payload.get("final"):
        return ""
    response = payload.get("responseMessage")
    if isinstance(response, dict):
        message_id = response.get("messageId")
        if isinstance(message_id, str) and message_id:
            return message_id
    message_id = payload.get("responseMessageId")
    if isinstance(message_id, str) and message_id:
        return message_id
    return ""


def extract_telegram_delivery_message_ids(value: Any) -> list[str]:
    candidates: list[Any] = []
    if isinstance(value, dict):
        for key in (
            "telegramMessageIds",
            "telegram_message_ids",
            "messageIds",
            "message_ids",
        ):
            if key in value:
                raw = value.get(key)
                candidates.extend(raw if isinstance(raw, (list, tuple, set)) else [raw])
        if value.get("message_id") is not None:
            candidates.append(value.get("message_id"))
    elif isinstance(value, (list, tuple, set)):
        candidates.extend(value)
    elif getattr(value, "message_id", None) is not None:
        candidates.append(getattr(value, "message_id"))
    return list(
        dict.fromkeys(
            str(candidate).strip()[:256]
            for candidate in candidates
            if candidate is not None and str(candidate).strip()
        )
    )[:32]
# === VIVENTIUM END ===


# === VIVENTIUM START ===
# Feature: Canonical-response replacement detection for Telegram follow-up polling.
_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_followup_compare_text(text: Any) -> str:
    if not isinstance(text, str):
        return ""
    cleaned = strip_trailing_nta(text).strip()
    if not cleaned:
        return ""
    return _WHITESPACE_RE.sub(" ", cleaned)


def _normalize_stream_delivery_compare_text(text: Any) -> str:
    if not isinstance(text, str):
        return ""
    return _normalize_followup_compare_text(sanitize_telegram_text(text))


def _prepare_followup_delivery_text(text: Any) -> str:
    if not isinstance(text, str):
        return ""
    return strip_trailing_nta(text).strip()
# === VIVENTIUM END ===


def extract_final_response_text(payload: dict[str, Any]) -> str:
    if not payload.get("final"):
        return ""
    parts: list[str] = []
    response = payload.get("responseMessage")
    if isinstance(response, dict):
        text = response.get("text")
        if isinstance(text, str) and text.strip():
            parts.append(sanitize_telegram_text(text, preserve_delivery_controls=True))
        if not parts:
            parts.extend(
                _collect_text_parts(
                    response.get("content"),
                    preserve_delivery_controls=True,
                )
            )
    if not parts:
        text = payload.get("text")
        if isinstance(text, str) and text.strip():
            parts.append(sanitize_telegram_text(text, preserve_delivery_controls=True))
    return "".join(parts).strip()


def _parse_positive_float(value: str, fallback: float) -> float:
    try:
        num = float(value)
        if num > 0 and num != float("inf"):
            return num
    except Exception:
        pass
    return fallback


_MAX_AUTOMATIC_FOLLOWUP_WINDOW_S = 86_400.0


def _parse_optional_followup_window(value: str) -> Optional[float]:
    """Parse an explicit automatic-listener window without inventing a fallback."""
    if not value:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed) or parsed < 0 or parsed > _MAX_AUTOMATIC_FOLLOWUP_WINDOW_S:
        return None
    return parsed


def _parse_non_negative_int(value: str, fallback: int) -> int:
    try:
        num = int(value)
        if num >= 0:
            return num
    except Exception:
        pass
    return fallback


def _parse_bool_env(value: str, fallback: bool) -> bool:
    lowered = (value or "").strip().lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    return fallback


@asynccontextmanager
async def _noop_async_context() -> AsyncIterator[None]:
    yield


# === VIVENTIUM START ===
# Feature: Structured Telegram stream-error presentation.
# Purpose: Prefer LibreChat's typed public error class over brittle inspection of human-facing
# text, while retaining legacy text classification for older stream payloads.
_STRUCTURED_STREAM_ERROR_MESSAGES = {
    "stream_expired": "Response stream expired during reconnect. Please send the message again.",
    "provider_billing": "Provider billing issue. Please check Plans & Billing.",
    "provider_connected_account_reconnect_required": (
        "Model connection needs reconnect. Open Viventium in the browser and reconnect the AI provider, then retry."
    ),
    "provider_unauthorized": (
        "Model connection needs reconnect. Open Viventium in the browser and reconnect the AI provider, then retry."
    ),
    "provider_auth_missing": (
        "The configured model provider authentication is unavailable. Open Viventium in the browser, reconnect the AI provider, then retry."
    ),
    "provider_access_denied": "The model provider denied access to this request.",
    "provider_rate_limited": "The model provider rate-limited this request. Please try again shortly.",
    "provider_quota_exhausted": (
        "The selected model provider quota is exhausted. Try again after the reset or use the configured fallback."
    ),
    "provider_response_deadline_exceeded": (
        "The model response exceeded this turn's configured deadline and was stopped. Please retry the turn."
    ),
    "provider_temporarily_unavailable": (
        "The model provider is temporarily unavailable. Please try again shortly."
    ),
    "context_length_exceeded": "The request was too large for the model context.",
    "mcp_tool_failure": "Tool connection error. Please retry.",
    "tool_failure": "Tool connection error. Please retry.",
    "late_stream_termination": "The model stream ended before a response was available.",
    "local_retrieval_timeout": (
        "Local retrieval timed out before the model response could be completed."
    ),
    "post_stream_finalization": (
        "The response completed, but post-response finalization failed."
    ),
    "tool_cortex_deferred_main_response": "Background work is still finishing this response.",
    "recoverable_provider_error": (
        "The model provider hit a recoverable issue before returning a result."
    ),
    "source_context_unavailable": (
        "The conversation context could not be preserved. Please retry this turn."
    ),
    "completion_error": "The model provider could not complete this request.",
}

_FOLLOWUP_RECOVERABLE_ERROR_CLASSES = {
    "completion_error",
    "late_stream_termination",
    "local_retrieval_timeout",
    "post_stream_finalization",
    "recoverable_provider_error",
    "tool_cortex_deferred_main_response",
}


def _stream_error_message(error: Optional[str], *, error_class: Optional[str] = None) -> str:
    normalized_error_class = str(error_class or "").strip().lower()
    if normalized_error_class:
        if normalized_error_class == "provider_connected_account_reconnect_required" and error:
            return sanitize_telegram_text(error)
        return _STRUCTURED_STREAM_ERROR_MESSAGES.get(
            normalized_error_class,
            _STRUCTURED_STREAM_ERROR_MESSAGES["completion_error"],
        )
    fallback = (os.getenv("VIVENTIUM_TELEGRAM_STREAM_ERROR_MESSAGE") or "").strip()
    if fallback:
        return fallback
    if error:
        lowered = error.lower()
        if (
            "404 not found" in lowered
            or "stream not found" in lowered
            or "generation job does not exist or has expired" in lowered
            or "failed to subscribe to stream" in lowered
        ):
            return "Response stream expired during reconnect. Please send the message again."
        if "credit balance is too low" in lowered or "plans & billing" in lowered:
            return "Provider billing issue. Please check Plans & Billing."
        if (
            "connected account needs reconnect" in lowered
            or "connected-account needs reconnect" in lowered
            or "provider_connected_account_reconnect_required" in lowered
            or (
                "configured fallback model could not start" in lowered
                and "reconnect" in lowered
            )
        ):
            return sanitize_telegram_text(error)
        if (
            "token_expired" in lowered
            or "provided authentication token is expired" in lowered
            or "model_authentication" in lowered
            or "invalid authentication credentials" in lowered
            or "authentication_error" in lowered
            or "provider_unauthorized" in lowered
            or "provider credentials" in lowered
            or "credentials were rejected" in lowered
            or "unauthorized provider credentials" in lowered
        ):
            return "Model connection needs reconnect. Open Viventium in the browser and reconnect the AI provider, then retry."
        if (
            "rate-limited" in lowered
            or "rate limited" in lowered
            or "rate_limit" in lowered
            or "rate limit" in lowered
            or "429" in lowered
        ):
            return "The model provider rate-limited this request. Please try again shortly."
        if "tool" in lowered or "mcp" in lowered or "oauth" in lowered:
            return "Tool connection error. Please retry."
    return "Connection error. Please retry."


# === VIVENTIUM END ===


def _bridge_error_event(
    message: str,
    *,
    speak: bool = False,
    error_class: Optional[str] = None,
    recoverable: bool = False,
) -> dict[str, Any]:
    event: dict[str, Any] = {"type": "bridge_error", "text": message, "speak": speak}
    if error_class:
        event["error_class"] = str(error_class)
    if recoverable:
        event["recoverable"] = True
    return event


# === VIVENTIUM START: retry only the typed pre-ingress Parallel Work readiness receipt ===
def _parallel_work_not_ready_start_error(error: Exception) -> bool:
    if not isinstance(error, httpx.HTTPStatusError):
        return False
    if getattr(error.response, "status_code", None) != 503:
        return False
    try:
        payload = error.response.json()
    except Exception:
        return False
    return bool(
        isinstance(payload, dict)
        and payload.get("code") == "PARALLEL_WORK_NOT_READY"
        and payload.get("retryable") is True
    )


def _start_chat_error_safe_to_retry(error: Exception) -> bool:
    return isinstance(
        error,
        (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout),
    ) or _parallel_work_not_ready_start_error(error)


def _start_chat_error_message(error: Exception) -> str:
    if _parallel_work_not_ready_start_error(error):
        return "Parallel work is still starting. This Telegram request was not accepted; please retry in a moment."

    if _start_chat_error_safe_to_retry(error):
        return "Viventium's local API is starting or unavailable. Please retry in a moment."

    if isinstance(error, httpx.ReadTimeout):
        return "Viventium's local API did not answer Telegram in time. Please retry."

    if isinstance(error, httpx.TimeoutException):
        return "Viventium's local API timed out while handling Telegram. Please retry."

    if isinstance(error, httpx.HTTPStatusError):
        status_code = getattr(error.response, "status_code", None)
        try:
            payload = error.response.json()
        except Exception:
            payload = None
        if (
            isinstance(payload, dict)
            and payload.get("attachmentProcessingError") is True
            and isinstance(payload.get("error"), str)
            and payload["error"].strip()
        ):
            return sanitize_telegram_text(payload["error"].strip())
        if status_code in {401, 403}:
            return "Telegram is not authorized to reach Viventium. Check the local Telegram bridge configuration."
        if status_code == 404:
            return "Viventium's Telegram route is unavailable. Restart or update Viventium, then retry."
        if status_code in {502, 503, 504}:
            return "Viventium's local API is starting or recovering. Please retry in a moment."
        if isinstance(status_code, int) and status_code >= 500:
            return "Viventium's local API reported a server error. Please retry."
        if isinstance(status_code, int):
            return f"Viventium's local API returned HTTP {status_code}. Please retry."

    return "Viventium could not start this Telegram turn. Please retry."
# === VIVENTIUM END ===


def _empty_response_message(error_context: Optional[str] = None) -> str:
    fallback = (os.getenv("VIVENTIUM_TELEGRAM_EMPTY_RESPONSE_MESSAGE") or "").strip()
    if fallback:
        return sanitize_telegram_text(fallback)
    if error_context:
        return f"No response received ({error_context}). Please retry."
    return "No response received. Please retry."


# === VIVENTIUM START ===
# Feature: Extract error information from final payload for better diagnostics.
# Added: 2026-02-01
def extract_final_error(payload: dict[str, Any]) -> Optional[str]:
    """Extract error message from a final payload if present."""
    # Check top-level error field
    error = payload.get("error")
    if isinstance(error, dict):
        msg = error.get("message")
        if isinstance(msg, str) and msg.strip():
            return msg.strip()
    if isinstance(error, str) and error.strip():
        return error.strip()

    # Check responseMessage.error field
    response = payload.get("responseMessage")
    if isinstance(response, dict):
        if response.get("error"):
            err_msg = response.get("errorMessage")
            if isinstance(err_msg, str) and err_msg.strip():
                return err_msg.strip()
            return "Agent error"

        # Some LibreChat error paths emit a content part of type "error" instead of
        # setting responseMessage.error / top-level error. Treat that as an explicit
        # error signal so Telegram doesn't produce an empty response.
        content = response.get("content")
        if isinstance(content, list):
            for part in content:
                if not isinstance(part, dict):
                    continue
                if part.get("type") != "error":
                    continue
                raw = part.get("error")
                if isinstance(raw, str) and raw.strip():
                    return raw.strip()
                if isinstance(raw, dict):
                    inner = raw.get("message")
                    if isinstance(inner, str) and inner.strip():
                        return inner.strip()
                return "Agent error"

    return None


def extract_final_error_class(payload: dict[str, Any]) -> str:
    """Extract the trusted structural error class without inferring intent from prose."""

    for key in ("error_class", "errorClass", "error_code", "errorCode", "code"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower()

    error = payload.get("error")
    if isinstance(error, dict):
        for key in ("error_class", "errorClass", "class", "code"):
            value = error.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip().lower()

    response = payload.get("responseMessage")
    if not isinstance(response, dict):
        return ""
    for key in ("error_class", "errorClass", "error_code", "errorCode", "code"):
        value = response.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    content = response.get("content")
    if isinstance(content, list):
        for part in content:
            if not isinstance(part, dict) or part.get("type") != "error":
                continue
            for key in ("error_class", "errorClass", "error_code", "errorCode", "code"):
                value = part.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip().lower()
    return ""


def _diagnose_empty_response(payload: dict[str, Any]) -> str:
    """Diagnose why a final response is empty and return a context string."""
    response = payload.get("responseMessage")
    if not response:
        return "no responseMessage"

    if not isinstance(response, dict):
        return f"responseMessage is {type(response).__name__}"

    content = response.get("content")
    text = response.get("text")

    if response.get("error"):
        err_msg = response.get("errorMessage") or "unknown"
        return f"agent error: {err_msg}"

    if content is None and text is None:
        return "empty content"

    if isinstance(content, list) and len(content) == 0:
        return "empty content array"

    if isinstance(content, list):
        types = [p.get("type") for p in content if isinstance(p, dict)]
        if types and "text" not in types:
            return f"content types: {','.join(str(t) for t in types[:3])}"

    return "unparseable format"
# === VIVENTIUM END ===


# === VIVENTIUM START ===
# Feature: Suppress false Telegram empty-response fallbacks for deferred LibreChat finals.
# Why:
# - Some local Telegram turns finalize with only internal parts (`think`, `tool_call`,
#   `cortex_*`) while the user-visible answer is persisted shortly after as a follow-up
#   or canonical replacement.
# - Treating that state as a terminal empty reply causes Telegram to emit
#   "No response received. Please retry." even though the assistant is still working.
_DEFERRED_FINAL_SIGNAL_TYPES = {"tool_call", "cortex_activation", "cortex_brewing", "cortex_insight"}
_DEFERRED_FINAL_ALLOWED_TYPES = _DEFERRED_FINAL_SIGNAL_TYPES | {"think"}


def _is_deferred_internal_final(payload: dict[str, Any]) -> bool:
    if not payload.get("final"):
        return False

    response = payload.get("responseMessage")
    if not isinstance(response, dict):
        return False

    text = response.get("text")
    if isinstance(text, str) and text.strip():
        return False

    content = response.get("content")
    if not isinstance(content, list) or len(content) == 0:
        return False

    saw_signal = False
    for part in content:
        if part is None:
            continue
        if not isinstance(part, dict):
            return False
        part_type = part.get("type")
        if part_type == "text":
            if _collect_text_parts(part):
                return False
            return False
        if part_type not in _DEFERRED_FINAL_ALLOWED_TYPES:
            return False
        if part_type in _DEFERRED_FINAL_SIGNAL_TYPES:
            saw_signal = True

    if response.get("unfinished") is True:
        return True

    return saw_signal
# === VIVENTIUM END ===


def _collect_text_parts(
    content: Any,
    *,
    preserve_delivery_controls: bool = False,
) -> list[str]:
    parts: list[str] = []

    def sanitize(value: str) -> str:
        return sanitize_telegram_text(
            value,
            preserve_delivery_controls=preserve_delivery_controls,
        )

    if isinstance(content, str):
        if content:
            parts.append(sanitize(content))
        return parts
    if isinstance(content, dict):
        if content.get("type") == "text":
            text = content.get("text")
            if isinstance(text, str) and text:
                parts.append(sanitize(text))
                return parts
            if isinstance(text, dict):
                val = text.get("value")
                if isinstance(val, str) and val:
                    parts.append(sanitize(val))
                    return parts
        text = content.get("text")
        if isinstance(text, str) and text:
            parts.append(sanitize(text))
        elif isinstance(text, dict):
            val = text.get("value")
            if isinstance(val, str) and val:
                parts.append(sanitize(val))
        else:
            val = content.get("value")
            if isinstance(val, str) and val:
                parts.append(sanitize(val))
        return parts
    if isinstance(content, list):
        for item in content:
            if isinstance(item, str):
                if item:
                    parts.append(sanitize(item))
                continue
            if not isinstance(item, dict):
                continue
            if item.get("type") not in (None, "text"):
                continue
            text = item.get("text")
            if isinstance(text, str) and text:
                parts.append(sanitize(text))
                continue
            if isinstance(text, dict):
                val = text.get("value")
                if isinstance(val, str) and val:
                    parts.append(sanitize(val))
                    continue
            val = item.get("value")
            if isinstance(val, str) and val:
                parts.append(sanitize(val))
        return parts
    return parts


def _build_stream_timeout(read_timeout_s: float) -> httpx.Timeout:
    return httpx.Timeout(
        connect=10.0,
        read=read_timeout_s,
        write=10.0,
        pool=10.0,
    )


class LibreChatBridge:
    def __init__(
        self,
        *,
        get_conversation_id: Callable[[str], str],
        set_conversation_id: Callable[[str, str], None],
        get_conversation_state: Optional[Callable[[str], dict[str, str]]] = None,
        get_agent_id: Optional[Callable[[str], str]] = None,
        set_agent_id: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        self.base_url = (os.getenv("VIVENTIUM_LIBRECHAT_ORIGIN", "http://127.0.0.1:3180") or "").strip().rstrip("/")
        self.secret = (
            os.getenv("VIVENTIUM_TELEGRAM_SECRET")
            or os.getenv("VIVENTIUM_CALL_SESSION_SECRET")
            or ""
        ).strip()
        self.default_agent_id = (os.getenv("VIVENTIUM_TELEGRAM_AGENT_ID") or "").strip()
        self.include_insights = (os.getenv("VIVENTIUM_TELEGRAM_INCLUDE_CORTEX_INSIGHTS") or "").strip() == "1"
        self.allow_insight_fallback = (
            (os.getenv("VIVENTIUM_TELEGRAM_INSIGHT_FALLBACK") or "").strip() == "1"
        )
        self.max_retries = _parse_non_negative_int(
            (os.getenv("VIVENTIUM_TELEGRAM_SSE_MAX_RETRIES") or "").strip(),
            1,
        )
        self.retry_delay_s = _parse_positive_float(
            (os.getenv("VIVENTIUM_TELEGRAM_SSE_RETRY_DELAY_S") or "").strip(),
            0.5,
        )
        self.start_chat_connect_retries = _parse_non_negative_int(
            (os.getenv("VIVENTIUM_TELEGRAM_CHAT_START_CONNECT_RETRIES") or "").strip(),
            1,
        )
        self.start_chat_connect_retry_delay_s = _parse_positive_float(
            (os.getenv("VIVENTIUM_TELEGRAM_CHAT_START_CONNECT_RETRY_DELAY_S") or "").strip(),
            0.75,
        )
        # === VIVENTIUM START ===
        # Feature: One config-owned automatic follow-up window across Telegram listeners.
        # Reason: The raw SSE listener and DB-backed poller previously invented separate implicit
        # 180s/210s lifetimes. Supported installs now use the compiler-owned background follow-up
        # window. Legacy insight env is accepted only when the canonical value is absent.
        canonical_followup_raw = (
            os.getenv("VIVENTIUM_TELEGRAM_FOLLOWUP_GRACE_S") or ""
        ).strip()
        legacy_insight_grace_raw = (
            os.getenv("VIVENTIUM_TELEGRAM_INSIGHT_GRACE_S") or ""
        ).strip()
        using_legacy_insight_window = False
        if canonical_followup_raw:
            configured_followup_window_s = _parse_optional_followup_window(
                canonical_followup_raw
            )
            if configured_followup_window_s is None:
                logger.warning(
                    "Invalid VIVENTIUM_TELEGRAM_FOLLOWUP_GRACE_S; automatic Telegram follow-up listeners are disabled"
                )
                configured_followup_window_s = 0.0
        elif legacy_insight_grace_raw:
            configured_followup_window_s = _parse_optional_followup_window(
                legacy_insight_grace_raw
            )
            if configured_followup_window_s is None:
                logger.warning(
                    "Invalid deprecated VIVENTIUM_TELEGRAM_INSIGHT_GRACE_S; automatic Telegram follow-up listeners are disabled"
                )
                configured_followup_window_s = 0.0
            else:
                using_legacy_insight_window = True
                logger.warning(
                    "VIVENTIUM_TELEGRAM_INSIGHT_GRACE_S is deprecated; configure runtime.background_followup_window_s instead"
                )
        else:
            configured_followup_window_s = 0.0

        configured_total_raw = (
            os.getenv("VIVENTIUM_TELEGRAM_FOLLOWUP_TIMEOUT_S") or ""
        ).strip()
        if configured_followup_window_s <= 0:
            configured_total_s = 0.0
        elif configured_total_raw:
            configured_total_s = _parse_optional_followup_window(configured_total_raw)
            if configured_total_s is None:
                logger.warning(
                    "Invalid VIVENTIUM_TELEGRAM_FOLLOWUP_TIMEOUT_S; using the canonical follow-up window"
                )
                configured_total_s = configured_followup_window_s
        elif using_legacy_insight_window:
            legacy_total_raw = (
                os.getenv("VIVENTIUM_TELEGRAM_INSIGHT_MAX_S") or ""
            ).strip()
            configured_total_s = _parse_optional_followup_window(legacy_total_raw)
            if configured_total_s is None:
                configured_total_s = configured_followup_window_s
        else:
            configured_total_s = configured_followup_window_s

        if configured_followup_window_s > 0:
            configured_total_s = max(configured_total_s, configured_followup_window_s)

        # Keep the historical attribute names as internal compatibility aliases. They no longer
        # own defaults or extend a compiler-configured follow-up window.
        self.insight_grace_s = configured_followup_window_s
        self.insight_max_s = configured_total_s
        self.followup_grace_s = configured_followup_window_s
        self.followup_timeout_s = configured_total_s

        # Feature: DB-backed follow-up polling (LibreChat parity).
        self.followup_interval_s = _parse_positive_float(
            (os.getenv("VIVENTIUM_TELEGRAM_FOLLOWUP_INTERVAL_S") or "").strip(),
            1.5,
        )
        self.glasshive_timeout_s = _parse_positive_float(
            (os.getenv("VIVENTIUM_TELEGRAM_GLASSHIVE_TIMEOUT_S") or "").strip(),
            600.0,
        )
        self.glasshive_delivery_poll_s = _parse_positive_float(
            (os.getenv("VIVENTIUM_TELEGRAM_GLASSHIVE_DELIVERY_POLL_S") or "").strip(),
            5.0,
        )
        self.glasshive_delivery_max_backoff_s = _parse_positive_float(
            (
                os.getenv("VIVENTIUM_TELEGRAM_GLASSHIVE_DELIVERY_MAX_BACKOFF_S")
                or ""
            ).strip(),
            60.0,
        )
        self.glasshive_delivery_batch_size = max(
            1,
            min(
                _parse_non_negative_int(
                    (os.getenv("VIVENTIUM_TELEGRAM_GLASSHIVE_DELIVERY_BATCH_SIZE") or "").strip(),
                    10,
                ),
                25,
            ),
        )
        self.glasshive_delivery_lease_ms = max(
            5_000,
            min(
                _parse_non_negative_int(
                    (os.getenv("VIVENTIUM_TELEGRAM_GLASSHIVE_DELIVERY_LEASE_MS") or "").strip(),
                    600_000,
                ),
                600_000,
            ),
        )
        if self.glasshive_timeout_s < 1.0:
            self.glasshive_timeout_s = 1.0
        # === VIVENTIUM END ===
        self._get_conversation_id = get_conversation_id
        self._set_conversation_id = set_conversation_id
        self._get_conversation_state = get_conversation_state
        self._conversation_generations: dict[str, str] = {}
        self._get_agent_id = get_agent_id
        self._set_agent_id = set_agent_id
        self.on_message_callback: Optional[Callable[..., Awaitable[None]]] = None
        self.on_retraction_callback: Optional[Callable[[int, str], Awaitable[None]]] = None
        self._insight_tasks: set[asyncio.Task] = set()
        self._insight_seen: dict[str, set[str]] = {}
        self._insight_refs: dict[str, int] = {}
        # === VIVENTIUM START ===
        # Feature: Keep Telegram follow-ups aligned with every live LibreChat stream.
        # Reason: Rapid independent Telegram turns may overlap. A newer source event must not
        # discard the older turn's auth identity or late cortex/worker delivery state.
        self._active_stream_by_chat: dict[str, set[str]] = {}
        self._stream_final_events: dict[str, asyncio.Event] = {}
        self._pending_followups: dict[str, str] = {}
        self._pending_stream_errors: dict[str, dict[str, str]] = {}
        self._insight_task_by_stream: dict[str, asyncio.Task] = {}
        self._response_message_ids: dict[str, str] = {}
        self._conversation_by_stream: dict[str, str] = {}
        self._followup_task_by_stream: dict[str, asyncio.Task] = {}
        self._followup_sent: set[str] = set()
        # Durable saved-memory receipts already surfaced for a stream (one receipt per turn).
        self._memory_receipt_sent: set[str] = set()
        self._memory_receipt_pending: set[str] = set()
        self._memory_poll_cursors: set[str] = set()
        self._memory_poll_chat: dict[str, str] = {}
        self._memory_delivery_state: dict[str, str] = {}
        self._stream_text_hash_by_stream: dict[str, str] = {}
        self._followup_send_lock_by_stream: dict[str, asyncio.Lock] = {}
        self._stream_identity: dict[str, dict[str, Any]] = {}
        self._cortex_seen_by_stream: dict[str, bool] = {}
        self._glasshive_seen_by_stream: set[str] = set()
        self._stream_text_by_stream: dict[str, str] = {}
        self._brief_main_reply_by_stream: dict[str, bool] = {}
        self._voice_route_by_chat: dict[str, dict[str, Any]] = {}
        self._voice_route_by_stream: dict[str, dict[str, Any]] = {}
        self._delivery_disposition_required_by_stream: dict[str, bool] = {}
        self._glasshive_delivery_dispatcher_task: Optional[asyncio.Task] = None
        self._glasshive_delivery_dispatcher_id = f"tg-{uuid.uuid4().hex[:12]}"
        self._cortex_ack_store = _CortexTelegramAckStore()
        self._cortex_ack_dispatcher_task: Optional[asyncio.Task] = None
        # === VIVENTIUM END ===
        # === VIVENTIUM START ===
        # Feature: Receptive same-chat Main intake.
        # Purpose: Core source-order and presentation acknowledgement own ordered revisions. The
        # bridge must admit a newer Telegram segment while the prior provider stream is still open;
        # otherwise Main, steer, and revision input all wait behind provider latency.
        # Legacy full-stream serialization remains an explicit diagnostic option only.
        self.serialize_per_chat = _parse_bool_env(
            (os.getenv("VIVENTIUM_TELEGRAM_SERIALIZE_PER_CHAT") or "").strip(),
            False,
        )
        # Preserve one lock per active Telegram chat.
        self._chat_locks: dict[str, asyncio.Lock] = {}
        self._trace_enabled = (os.getenv("VIVENTIUM_TELEGRAM_TRACE") or "").strip() == "1"
        # === VIVENTIUM END ===

        if not self.base_url:
            logger.warning("LibreChatBridge missing VIVENTIUM_LIBRECHAT_ORIGIN")
        if not self.secret:
            logger.warning("LibreChatBridge missing VIVENTIUM_TELEGRAM_SECRET")

    def set_on_message_callback(self, callback: Callable[..., Awaitable[None]]):
        self.on_message_callback = callback

    def set_on_retraction_callback(
        self,
        callback: Callable[[int, str], Awaitable[None]],
    ) -> None:
        self.on_retraction_callback = callback

    async def _retract_cortex_presentation_refs(self, presentation_refs: list[str]) -> None:
        if not self.on_retraction_callback:
            logger.warning("Cortex Telegram retraction callback is unavailable")
            return
        for presentation_ref in presentation_refs:
            match = re.fullmatch(r"telegram:([^:]+):([^:]+)", str(presentation_ref or ""))
            if not match:
                continue
            try:
                await self.on_retraction_callback(int(match.group(1)), match.group(2))
            except Exception as exc:
                logger.warning("Cortex Telegram retraction failed: %s", type(exc).__name__)

    async def _settle_cortex_acknowledgement(
        self,
        ack_key: str,
        payload: dict[str, Any],
    ) -> str:
        status = await self.ack_delivery_status(
            payload["logical_turn_id"],
            payload["revision"],
            payload["state"],
            payload.get("presentation_ref") or "",
            payload.get("presentation_refs") or None,
            cortex_presentation=payload.get("cortex_presentation"),
        )
        if status == "recorded":
            self._cortex_ack_store.mark_done(ack_key)
            return status
        if status in {"conflict", "stale_revision", "stale_source_order", "not_found"}:
            await self._retract_cortex_presentation_refs(payload.get("presentation_refs") or [])
            self._cortex_ack_store.mark_done(ack_key)
        return status

    async def _drain_cortex_acknowledgements(self, *, limit: int = 25) -> int:
        rows = self._cortex_ack_store.due(limit)
        for ack_key, payload in rows:
            try:
                await self._settle_cortex_acknowledgement(ack_key, payload)
            except Exception as exc:
                logger.warning("Cortex Telegram acknowledgement retry failed: %s", type(exc).__name__)
        return len(rows)

    def start_cortex_ack_dispatcher(self) -> None:
        if self._cortex_ack_dispatcher_task and not self._cortex_ack_dispatcher_task.done():
            return
        self._cortex_ack_dispatcher_task = asyncio.create_task(
            self._run_cortex_ack_dispatcher(),
            name="cortex-telegram-ack-dispatcher",
        )
        self._track_task(self._cortex_ack_dispatcher_task)

    def stop_cortex_ack_dispatcher(self) -> None:
        task = self._cortex_ack_dispatcher_task
        if task and not task.done():
            task.cancel()
        self._cortex_ack_dispatcher_task = None

    async def _run_cortex_ack_dispatcher(self) -> None:
        while True:
            try:
                await self._dispatch_cortex_delivery_cycle()
                await asyncio.sleep(2.0)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Cortex Telegram acknowledgement dispatcher failed: %s", type(exc).__name__)
                await asyncio.sleep(2.0)

    @staticmethod
    def _validate_cortex_authority(
        payload: Any,
        *,
        require_presentation: bool,
        expected_claim: Optional[dict[str, Any]] = None,
    ) -> Optional[dict[str, Any]]:
        if not isinstance(payload, dict):
            return None
        claim_keys = {
            "ownerId",
            "messageId",
            "parentMessageId",
            "revision",
            "generation",
            "deliveryIds",
            "deliveryReceipts",
            "claimToken",
            "surface",
        }
        required_keys = claim_keys | ({"presentationLeaseToken"} if require_presentation else set())
        if set(payload) != required_keys or payload.get("surface") != "telegram":
            return None
        for key in ("ownerId", "messageId", "parentMessageId", "claimToken"):
            value = payload.get(key)
            if not isinstance(value, str) or not value.strip() or len(value) > 256:
                return None
        for key in ("revision", "generation"):
            value = payload.get(key)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                return None
        delivery_ids = payload.get("deliveryIds")
        receipts = payload.get("deliveryReceipts")
        if (
            not isinstance(delivery_ids, list)
            or not delivery_ids
            or len(delivery_ids) > 25
            or any(not isinstance(value, str) or not value or len(value) > 256 for value in delivery_ids)
            or delivery_ids != sorted(set(delivery_ids))
            or not isinstance(receipts, list)
            or len(receipts) != len(delivery_ids)
        ):
            return None
        normalized_receipts: list[dict[str, str]] = []
        for index, receipt in enumerate(receipts):
            if not isinstance(receipt, dict) or set(receipt) != {"deliveryId", "graphResultHash"}:
                return None
            delivery_id = receipt.get("deliveryId")
            graph_hash = receipt.get("graphResultHash")
            if (
                delivery_id != delivery_ids[index]
                or not isinstance(graph_hash, str)
                or not re.fullmatch(r"[a-f0-9]{64}", graph_hash)
            ):
                return None
            normalized_receipts.append(
                {"deliveryId": delivery_id, "graphResultHash": graph_hash}
            )
        if require_presentation:
            lease_token = payload.get("presentationLeaseToken")
            if not isinstance(lease_token, str) or not lease_token or len(lease_token) > 256:
                return None
        if expected_claim is not None:
            expected = LibreChatBridge._validate_cortex_authority(
                expected_claim,
                require_presentation=False,
            )
            if expected is None:
                return None
            for key in claim_keys:
                if payload.get(key) != expected.get(key):
                    return None
        return {
            **payload,
            "deliveryIds": list(delivery_ids),
            "deliveryReceipts": normalized_receipts,
        }

    @classmethod
    def _validate_cortex_delivery(cls, payload: Any) -> Optional[dict[str, Any]]:
        required_keys = {
            "deliveryId",
            "streamId",
            "telegramChatId",
            "telegramUserId",
            "telegramMessageId",
            "telegramMessageThreadId",
            "sourceSequence",
            "text",
            "logicalTurnId",
            "logicalTurnRevision",
            "cortexClaim",
        }
        if not isinstance(payload, dict) or set(payload) != required_keys:
            return None
        claim = cls._validate_cortex_authority(
            payload.get("cortexClaim"),
            require_presentation=False,
        )
        source_sequence = payload.get("sourceSequence")
        logical_revision = payload.get("logicalTurnRevision")
        thread_id = payload.get("telegramMessageThreadId")
        if (
            claim is None
            or not isinstance(payload.get("deliveryId"), str)
            or payload.get("deliveryId") not in claim["deliveryIds"]
            or not isinstance(payload.get("streamId"), str)
            or not payload.get("streamId")
            or len(payload.get("streamId")) > 256
            or not isinstance(payload.get("telegramChatId"), str)
            or not re.fullmatch(r"-?[1-9][0-9]*", payload.get("telegramChatId"))
            or not isinstance(payload.get("telegramUserId"), str)
            or not re.fullmatch(r"[1-9][0-9]*", payload.get("telegramUserId"))
            or not isinstance(payload.get("telegramMessageId"), str)
            or not re.fullmatch(r"[1-9][0-9]*", payload.get("telegramMessageId"))
            or not isinstance(thread_id, str)
            or (thread_id != "" and not re.fullmatch(r"[1-9][0-9]*", thread_id))
            or not isinstance(source_sequence, int)
            or isinstance(source_sequence, bool)
            or source_sequence < 1
            or str(source_sequence) != payload.get("telegramMessageId")
            or not isinstance(payload.get("text"), str)
            or not payload.get("text").strip()
            or not isinstance(payload.get("logicalTurnId"), str)
            or not payload.get("logicalTurnId")
            or not isinstance(logical_revision, int)
            or isinstance(logical_revision, bool)
            or logical_revision < 1
        ):
            return None
        return {**payload, "cortexClaim": claim}

    async def _claim_cortex_deliveries(self, *, limit: int = 10) -> list[dict[str, Any]]:
        if not self.base_url or not self.secret:
            return []
        url = f"{self.base_url}/api/viventium/telegram/cortex/deliveries/claim"
        payload = {
            "limit": max(1, min(int(limit or 1), 25)),
            "leaseMs": 120_000,
        }
        timeout = httpx.Timeout(10.0, connect=5.0, read=10.0, write=5.0, pool=5.0)
        async with httpx.AsyncClient(
            timeout=timeout,
            **_async_client_options_for_url(url),
        ) as client:
            response = await client.post(
                url,
                json=payload,
                headers={"X-VIVENTIUM-TELEGRAM-SECRET": self.secret},
            )
        if response.status_code != 200:
            raise RuntimeError(f"Cortex Telegram delivery claim failed ({response.status_code})")
        data = response.json()
        deliveries = data.get("deliveries") if isinstance(data, dict) else None
        if not isinstance(deliveries, list):
            return []
        validated = []
        for delivery in deliveries:
            exact = self._validate_cortex_delivery(delivery)
            if exact is None:
                logger.warning("Cortex Telegram dispatcher rejected a malformed claim")
                continue
            validated.append(exact)
        return validated

    async def _authorize_cortex_delivery(
        self,
        delivery: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        claim = self._validate_cortex_authority(
            delivery.get("cortexClaim"),
            require_presentation=False,
        )
        current = delivery.get("cortexPresentation") or claim
        current_is_presentation = isinstance(current, dict) and "presentationLeaseToken" in current
        current_authority = self._validate_cortex_authority(
            current,
            require_presentation=current_is_presentation,
            expected_claim=claim,
        )
        if claim is None or current_authority is None:
            return None
        url = f"{self.base_url}/api/viventium/telegram/cortex/deliveries/authorize"
        timeout = httpx.Timeout(10.0, connect=5.0, read=10.0, write=5.0, pool=5.0)
        async with httpx.AsyncClient(
            timeout=timeout,
            **_async_client_options_for_url(url),
        ) as client:
            response = await client.post(
                url,
                json={"cortexClaim": current_authority, "leaseMs": 120_000},
                headers={"X-VIVENTIUM-TELEGRAM-SECRET": self.secret},
            )
        if response.status_code == 409:
            return None
        if response.status_code != 200:
            raise RuntimeError(
                f"Cortex Telegram delivery authorization failed ({response.status_code})"
            )
        data = response.json()
        presentation = data.get("cortexPresentation") if isinstance(data, dict) else None
        exact = self._validate_cortex_authority(
            presentation,
            require_presentation=True,
            expected_claim=claim,
        )
        if (
            exact is None
            or (
                current_is_presentation
                and exact.get("presentationLeaseToken")
                != current_authority.get("presentationLeaseToken")
            )
        ):
            return None
        return exact

    async def _mark_cortex_delivery_status(
        self,
        delivery: dict[str, Any],
        status: str,
    ) -> bool:
        if status not in {"failed", "suppressed", "delivery_unknown"}:
            return False
        claim = self._validate_cortex_authority(
            delivery.get("cortexClaim"),
            require_presentation=False,
        )
        presentation = self._validate_cortex_authority(
            delivery.get("cortexPresentation"),
            require_presentation=True,
            expected_claim=claim,
        )
        if claim is None or (status == "delivery_unknown" and presentation is None):
            return False
        payload: dict[str, Any] = {"status": status}
        if presentation is not None:
            payload["cortexPresentation"] = presentation
        else:
            payload["cortexClaim"] = claim
        url = f"{self.base_url}/api/viventium/telegram/cortex/deliveries/status"
        timeout = httpx.Timeout(10.0, connect=5.0, read=10.0, write=5.0, pool=5.0)
        async with httpx.AsyncClient(
            timeout=timeout,
            **_async_client_options_for_url(url),
        ) as client:
            response = await client.post(
                url,
                json=payload,
                headers={"X-VIVENTIUM-TELEGRAM-SECRET": self.secret},
            )
        if response.status_code == 409:
            return False
        if response.status_code != 200:
            raise RuntimeError(
                f"Cortex Telegram delivery status update failed ({response.status_code})"
            )
        return True

    async def _cortex_delivery_is_current(self, delivery: dict[str, Any]) -> bool:
        try:
            return await self.source_order_is_current(
                telegram_user_id=delivery["telegramUserId"],
                telegram_chat_id=delivery["telegramChatId"],
                telegram_message_thread_id=delivery["telegramMessageThreadId"],
                source_sequence=delivery["sourceSequence"],
            )
        except Exception as exc:
            logger.warning(
                "Cortex Telegram dispatch source-order check failed closed: %s",
                type(exc).__name__,
            )
            return False

    async def _deliver_cortex_delivery(self, delivery: dict[str, Any]) -> bool:
        exact = self._validate_cortex_delivery(delivery)
        if exact is None:
            return False
        if is_no_response_only(exact["text"]):
            await self._mark_cortex_delivery_status(exact, "suppressed")
            return True
        if not await self._cortex_delivery_is_current(exact):
            await self._mark_cortex_delivery_status(exact, "suppressed")
            return False

        stream_id = exact["streamId"]
        previous_identity = self._stream_identity.get(stream_id)
        previous_identity_copy = dict(previous_identity) if isinstance(previous_identity, dict) else None
        self._set_stream_identity(
            stream_id=stream_id,
            telegram_chat_id=exact["telegramChatId"],
            telegram_user_id=exact["telegramUserId"],
            telegram_username=(previous_identity_copy or {}).get("telegram_username", ""),
            voice_mode=(previous_identity_copy or {}).get("voice_mode") == "1",
            input_mode=(previous_identity_copy or {}).get("input_mode", ""),
            voice_route=(previous_identity_copy or {}).get("voice_route"),
            telegram_message_id=exact["telegramMessageId"],
            telegram_message_thread_id=exact["telegramMessageThreadId"],
            logical_turn_id=exact["logicalTurnId"],
            logical_turn_revision=exact["logicalTurnRevision"],
        )
        transport_authorized = False

        async def authorize_before_side_effect() -> bool:
            nonlocal transport_authorized
            if not await self._cortex_delivery_is_current(exact):
                raise _TelegramPollDeliveryStale()
            presentation = await self._authorize_cortex_delivery(exact)
            if presentation is None:
                raise _CortexDeliveryAuthorizationLost(
                    "cortex_telegram_delivery_authorization_lost"
                )
            exact["cortexPresentation"] = presentation
            transport_authorized = True
            return True

        try:
            sent = await self._send_followup_text_once(
                exact["telegramChatId"],
                exact["text"],
                stream_id=stream_id,
                cortex_delivery=exact,
                enforce_order_fence=True,
                authorize_before_side_effect=authorize_before_side_effect,
            )
            if sent:
                return True
            await self._mark_cortex_delivery_status(
                exact,
                "delivery_unknown" if transport_authorized else "failed",
            )
            return False
        except _TelegramPollDeliveryStale:
            await self._mark_cortex_delivery_status(
                exact,
                "delivery_unknown" if transport_authorized else "suppressed",
            )
            return False
        except Exception as exc:
            logger.warning("Cortex Telegram durable delivery failed: %s", type(exc).__name__)
            await self._mark_cortex_delivery_status(
                exact,
                "delivery_unknown" if transport_authorized else "failed",
            )
            return False
        finally:
            if previous_identity_copy is None:
                self._stream_identity.pop(stream_id, None)
            else:
                self._stream_identity[stream_id] = previous_identity_copy

    async def _dispatch_cortex_delivery_cycle(self) -> int:
        self._resume_memory_polls()
        await self._drain_cortex_acknowledgements()
        deliveries = await self._claim_cortex_deliveries(limit=10)
        for delivery in deliveries:
            await self._deliver_cortex_delivery(delivery)
        return len(deliveries)

    # === VIVENTIUM START ===
    # Feature: Durable GlassHive Telegram delivery dispatcher.
    # Purpose: Deliver callbacks that arrive after the original request poller exits
    # or after the Telegram bridge restarts.
    def start_glasshive_delivery_dispatcher(self) -> None:
        if self._glasshive_delivery_dispatcher_task and not self._glasshive_delivery_dispatcher_task.done():
            return
        if not self.base_url or not self.secret:
            logger.warning("GlassHive delivery dispatcher disabled: missing LibreChat origin or Telegram secret")
            return
        self._glasshive_delivery_dispatcher_task = asyncio.create_task(
            self._run_glasshive_delivery_dispatcher(),
            name="glasshive-telegram-delivery-dispatcher",
        )
        self._track_task(self._glasshive_delivery_dispatcher_task)

    def stop_glasshive_delivery_dispatcher(self) -> None:
        task = self._glasshive_delivery_dispatcher_task
        if task and not task.done():
            task.cancel()
        self._glasshive_delivery_dispatcher_task = None

    def _glasshive_delivery_attempt_timeout_s(self) -> float:
        lease_s = max(float(self.glasshive_delivery_lease_ms) / 1000.0, 1.0)
        return max(1.0, min(30.0, lease_s / 2.0))

    async def _deliver_glasshive_delivery_bounded(
        self,
        delivery: dict[str, Any],
    ) -> bool:
        try:
            return await asyncio.wait_for(
                self._deliver_glasshive_delivery(delivery),
                timeout=self._glasshive_delivery_attempt_timeout_s(),
            )
        except asyncio.TimeoutError:
            transport_authorized = isinstance(delivery.get("dispatchPermit"), dict) or bool(
                delivery.get("claimAuthorizedTransportStarted")
            )
            status = "delivery_unknown" if transport_authorized else "failed"
            detail = (
                "GlassHive callback delivery timed out after Telegram transport authorization"
                if transport_authorized
                else "GlassHive callback delivery timed out before Telegram transport authorization"
            )
            try:
                await self._mark_glasshive_delivery_status(
                    delivery,
                    status,
                    **({"reason": detail} if transport_authorized else {"error": detail}),
                )
            except Exception as exc:
                logger.warning(
                    "GlassHive timed-out delivery status could not be recorded: %s",
                    exc,
                )
            return False

    async def _run_glasshive_delivery_dispatcher(self) -> None:
        interval_s = max(self.glasshive_delivery_poll_s, 1.0)
        max_backoff_s = max(self.glasshive_delivery_max_backoff_s, interval_s)
        consecutive_failures = 0
        while True:
            try:
                claimed = await self._claim_glasshive_deliveries(limit=self.glasshive_delivery_batch_size)
                if consecutive_failures:
                    logger.info(
                        "GlassHive delivery dispatcher dependency recovered after %s failed attempt(s)",
                        consecutive_failures,
                    )
                    consecutive_failures = 0
                if not claimed:
                    await asyncio.sleep(interval_s)
                    continue
                for delivery in claimed:
                    await self._deliver_glasshive_delivery_bounded(delivery)
            except asyncio.CancelledError:
                return
            except Exception as exc:
                consecutive_failures += 1
                retry_s = min(
                    max_backoff_s,
                    interval_s * (2 ** min(consecutive_failures - 1, 10)),
                )
                if consecutive_failures == 1:
                    logger.warning(
                        "GlassHive delivery dispatcher dependency unavailable; "
                        "retrying with capped backoff: %s",
                        exc,
                    )
                await asyncio.sleep(retry_s)

    async def _claim_glasshive_deliveries(
        self,
        *,
        limit: int = 10,
        callback_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        if not self.base_url or not self.secret:
            return []
        url = f"{self.base_url}/api/viventium/telegram/glasshive/deliveries/claim"
        headers = {"X-VIVENTIUM-TELEGRAM-SECRET": self.secret}
        payload: dict[str, Any] = {
            "limit": max(1, min(int(limit or 1), 25)),
            "leaseMs": self.glasshive_delivery_lease_ms,
            "dispatcherId": self._glasshive_delivery_dispatcher_id,
        }
        if callback_id:
            payload["callbackId"] = callback_id
        timeout = httpx.Timeout(10.0, connect=5.0, read=10.0, write=5.0, pool=5.0)
        async with httpx.AsyncClient(
            timeout=timeout,
            **_async_client_options_for_url(url),
        ) as client:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code != 200:
                raise RuntimeError(f"GlassHive delivery claim failed ({response.status_code})")
            data = response.json()
        deliveries = data.get("deliveries") if isinstance(data, dict) else None
        return [item for item in deliveries if isinstance(item, dict)] if isinstance(deliveries, list) else []

    async def _mark_glasshive_delivery_status(
        self,
        delivery: dict[str, Any],
        status: str,
        *,
        error: str = "",
        reason: str = "",
    ) -> bool:
        delivery_id = str(delivery.get("deliveryId") or "").strip()
        claim_id = str(delivery.get("claimId") or "").strip()
        if not delivery_id or not claim_id:
            return False
        url = f"{self.base_url}/api/viventium/telegram/glasshive/deliveries/{urllib.parse.quote(delivery_id)}/status"
        headers = {"X-VIVENTIUM-TELEGRAM-SECRET": self.secret}
        payload = {"claimId": claim_id, "status": status}
        dispatch_permit = delivery.get("dispatchPermit")
        if status in {"sent", "delivery_unknown"} and isinstance(dispatch_permit, dict):
            payload["dispatchPermit"] = dispatch_permit
        if status == "sent":
            message_ids = extract_telegram_delivery_message_ids(
                delivery.get("telegramSentMessageIds")
            )
            if message_ids:
                payload["telegramMessageIds"] = message_ids
        if error:
            payload["error"] = error[:1000]
        if reason:
            payload["reason"] = reason[:1000]
        timeout = httpx.Timeout(10.0, connect=5.0, read=10.0, write=5.0, pool=5.0)
        async with httpx.AsyncClient(
            timeout=timeout,
            **_async_client_options_for_url(url),
        ) as client:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code == 409:
                logger.warning("GlassHive delivery claim was lost before status=%s", status)
                return False
            if response.status_code != 200:
                raise RuntimeError(f"GlassHive delivery status update failed ({response.status_code})")
        return True

    async def _authorize_glasshive_delivery(
        self,
        delivery: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        delivery_id = str(delivery.get("deliveryId") or "").strip()
        claim_id = str(delivery.get("claimId") or "").strip()
        if not delivery_id or not claim_id:
            return None
        url = (
            f"{self.base_url}/api/viventium/telegram/glasshive/deliveries/"
            f"{urllib.parse.quote(delivery_id)}/authorize"
        )
        timeout = httpx.Timeout(10.0, connect=5.0, read=10.0, write=5.0, pool=5.0)
        async with httpx.AsyncClient(
            timeout=timeout,
            **_async_client_options_for_url(url),
        ) as client:
            response = await client.post(
                url,
                json={
                    "claimId": claim_id,
                    "leaseMs": min(self.glasshive_delivery_lease_ms, 300_000),
                },
                headers={"X-VIVENTIUM-TELEGRAM-SECRET": self.secret},
            )
        if response.status_code == 409:
            return None
        if response.status_code != 200:
            raise RuntimeError(f"GlassHive delivery authorization failed ({response.status_code})")
        data = response.json()
        permit = data.get("permit") if isinstance(data, dict) else None
        return self._validate_glasshive_dispatch_permit(permit, delivery)

    @staticmethod
    def _glasshive_dispatch_permit_expiry(
        permit: dict[str, Any],
    ) -> Optional[datetime]:
        raw_expiry = permit.get("expiresAt")
        if not isinstance(raw_expiry, str) or not raw_expiry.strip():
            return None
        normalized = raw_expiry.strip()
        if normalized.endswith("Z"):
            normalized = f"{normalized[:-1]}+00:00"
        try:
            expiry = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if expiry.tzinfo is None:
            return None
        return expiry.astimezone(timezone.utc)

    def _validate_glasshive_dispatch_permit(
        self,
        payload: Any,
        delivery: dict[str, Any],
        *,
        previous: Optional[dict[str, Any]] = None,
    ) -> Optional[dict[str, Any]]:
        if not isinstance(payload, dict):
            return None
        required_keys = {
            "deliveryId",
            "claimId",
            "surface",
            "permitId",
            "permitGeneration",
            "expiresAt",
            "resultRevision",
            "resultDigest",
        }
        permit_id = payload.get("permitId")
        generation = payload.get("permitGeneration")
        revision = payload.get("resultRevision")
        digest = payload.get("resultDigest")
        if (
            set(payload) != required_keys
            or payload.get("deliveryId") != str(delivery.get("deliveryId") or "").strip()
            or payload.get("claimId") != str(delivery.get("claimId") or "").strip()
            or payload.get("surface") != "telegram"
            or not isinstance(permit_id, str)
            or not permit_id
            or len(permit_id) > 256
            or not isinstance(generation, int)
            or isinstance(generation, bool)
            or generation < 1
            or not isinstance(revision, int)
            or isinstance(revision, bool)
            or revision < 1
            or not isinstance(digest, str)
            or len(digest) != 71
            or not digest.startswith("sha256:")
            or any(character not in "0123456789abcdef" for character in digest[7:])
        ):
            return None
        expiry = self._glasshive_dispatch_permit_expiry(payload)
        if expiry is None or expiry <= datetime.now(timezone.utc):
            return None
        if previous is None:
            return dict(payload)
        previous_expiry = self._glasshive_dispatch_permit_expiry(previous)
        if (
            previous_expiry is None
            or permit_id != previous.get("permitId")
            or generation != previous.get("permitGeneration")
            or revision != previous.get("resultRevision")
            or digest != previous.get("resultDigest")
            or expiry <= previous_expiry
        ):
            return None
        return dict(payload)

    async def _renew_glasshive_delivery(
        self,
        delivery: dict[str, Any],
        permit: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        delivery_id = str(delivery.get("deliveryId") or "").strip()
        claim_id = str(delivery.get("claimId") or "").strip()
        url = (
            f"{self.base_url}/api/viventium/telegram/glasshive/deliveries/"
            f"{urllib.parse.quote(delivery_id)}/renew"
        )
        timeout = httpx.Timeout(10.0, connect=5.0, read=10.0, write=5.0, pool=5.0)
        async with httpx.AsyncClient(
            timeout=timeout,
            **_async_client_options_for_url(url),
        ) as client:
            response = await client.post(
                url,
                json={
                    "claimId": claim_id,
                    "dispatchPermit": permit,
                    "leaseMs": min(self.glasshive_delivery_lease_ms, 300_000),
                },
                headers={"X-VIVENTIUM-TELEGRAM-SECRET": self.secret},
            )
        if response.status_code == 409:
            return None
        if response.status_code != 200:
            raise RuntimeError(f"GlassHive delivery renewal failed ({response.status_code})")
        data = response.json()
        renewed = data.get("permit") if isinstance(data, dict) else None
        return self._validate_glasshive_dispatch_permit(
            renewed,
            delivery,
            previous=permit,
        )

    async def _release_glasshive_delivery(
        self,
        delivery: dict[str, Any],
        permit: dict[str, Any],
    ) -> bool:
        delivery_id = str(delivery.get("deliveryId") or "").strip()
        claim_id = str(delivery.get("claimId") or "").strip()
        if not delivery_id or not claim_id:
            return False
        url = (
            f"{self.base_url}/api/viventium/telegram/glasshive/deliveries/"
            f"{urllib.parse.quote(delivery_id)}/release"
        )
        timeout = httpx.Timeout(10.0, connect=5.0, read=10.0, write=5.0, pool=5.0)
        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                **_async_client_options_for_url(url),
            ) as client:
                response = await client.post(
                    url,
                    json={"claimId": claim_id, "dispatchPermit": permit},
                    headers={"X-VIVENTIUM-TELEGRAM-SECRET": self.secret},
                )
            return response.status_code == 200
        except Exception as exc:
            logger.warning("GlassHive Telegram permit release failed: %s", exc)
            return False

    async def _send_glasshive_with_permit(
        self,
        delivery: dict[str, Any],
        chat_id: str,
        text: str,
        permit: dict[str, Any],
    ) -> tuple[Any, dict[str, Any]]:
        permit_holder = {"value": permit}
        permit_lock = asyncio.Lock()
        authorized_side_effects = 0
        first_side_effect_authorized = asyncio.Event()
        renewal_interval_s = max(
            0.01,
            min(15.0, self.glasshive_delivery_lease_ms / 3000.0),
        )

        async def renew_before_next_side_effect() -> bool:
            nonlocal authorized_side_effects
            async with permit_lock:
                try:
                    renewed = await self._renew_glasshive_delivery(
                        delivery,
                        permit_holder["value"],
                    )
                except Exception as exc:
                    raise _GlassHiveDeliveryAuthorizationLost(
                        str(exc),
                        transport_started=authorized_side_effects > 0,
                    ) from exc
                if not renewed:
                    raise _GlassHiveDeliveryAuthorizationLost(
                        "glasshive_delivery_authorization_lost",
                        transport_started=authorized_side_effects > 0,
                    )
                permit_holder["value"] = renewed
                delivery["dispatchPermit"] = renewed
                authorized_side_effects += 1
                first_side_effect_authorized.set()
            return True

        send_task = asyncio.create_task(
            self._send_followup_text(
                chat_id,
                text,
                return_receipt=True,
                before_side_effect=renew_before_next_side_effect,
            )
        )

        async def keep_authorized() -> None:
            await first_side_effect_authorized.wait()
            while True:
                await asyncio.sleep(renewal_interval_s)
                async with permit_lock:
                    renewed = await self._renew_glasshive_delivery(
                        delivery,
                        permit_holder["value"],
                    )
                    if not renewed:
                        raise _GlassHiveDeliveryAuthorizationLost(
                            "glasshive_delivery_authorization_lost",
                            transport_started=authorized_side_effects > 0,
                        )
                    permit_holder["value"] = renewed
                    delivery["dispatchPermit"] = renewed

        renewal_task = asyncio.create_task(keep_authorized())
        try:
            done, _ = await asyncio.wait(
                {send_task, renewal_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if renewal_task in done:
                renewal_task.result()
            return await send_task, permit_holder["value"]
        finally:
            if not send_task.done():
                send_task.cancel()
                await asyncio.gather(send_task, return_exceptions=True)
            renewal_task.cancel()
            await asyncio.gather(renewal_task, return_exceptions=True)

    async def _claim_glasshive_delivery_for_callback(
        self,
        latest: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        callback_id = str(latest.get("callbackId") or latest.get("callback_id") or "").strip()
        if not callback_id:
            return None
        claimed = await self._claim_glasshive_deliveries(limit=1, callback_id=callback_id)
        return claimed[0] if claimed else None

    @staticmethod
    def _glasshive_attention_delivery_uses_claim(delivery: dict[str, Any]) -> bool:
        event = delivery.get("event")
        delivery_id = delivery.get("deliveryId")
        claim_id = delivery.get("claimId")
        terminal_result_key = delivery.get("terminalCallbackResultKey")
        return (
            isinstance(event, str)
            and event in _CLAIM_AUTHORIZED_GLASSHIVE_ATTENTION_EVENTS
            and isinstance(delivery_id, str)
            and bool(delivery_id.strip())
            and isinstance(claim_id, str)
            and bool(claim_id.strip())
            and terminal_result_key == ""
            and "workerCompletionPresentation" in delivery
            and delivery.get("workerCompletionPresentation") is None
        )

    async def _deliver_claim_authorized_glasshive_attention(
        self,
        delivery: dict[str, Any],
        chat_id: str,
        text: str,
    ) -> bool:
        delivery["claimAuthorizedTransportStarted"] = True
        try:
            result = await self._send_followup_text(
                chat_id,
                text,
                return_receipt=True,
            )
            sent = bool(result.get("sent")) if isinstance(result, dict) else bool(result)
            message_ids = (
                extract_telegram_delivery_message_ids(result)
                if isinstance(result, dict)
                else []
            )
            if sent and message_ids:
                delivery["telegramSentMessageIds"] = message_ids
                settled = await self._mark_glasshive_delivery_status(delivery, "sent")
                return settled is not False
            if sent:
                await self._mark_glasshive_delivery_status(
                    delivery,
                    "delivery_unknown",
                    reason="telegram_receipt_missing_after_send",
                )
                return False
            await self._mark_glasshive_delivery_status(
                delivery,
                "failed",
                error="Telegram send returned false",
            )
            return False
        except Exception as exc:
            await self._mark_glasshive_delivery_status(
                delivery,
                "delivery_unknown",
                reason=f"telegram_send_outcome_unknown:{str(exc)[:200]}",
            )
            return False

    async def _deliver_glasshive_delivery(self, delivery: dict[str, Any]) -> bool:
        chat_id = str(delivery.get("telegramChatId") or "").strip()
        text = str(delivery.get("fullText") or delivery.get("text") or "").strip()
        if not chat_id or not text:
            await self._mark_glasshive_delivery_status(
                delivery,
                "suppressed",
                reason="missing Telegram chat id or text",
            )
            return False
        if is_no_response_only(text):
            await self._mark_glasshive_delivery_status(delivery, "suppressed", reason="{NTA}")
            return True
        if self._glasshive_attention_delivery_uses_claim(delivery):
            return await self._deliver_claim_authorized_glasshive_attention(
                delivery,
                chat_id,
                text,
            )
        try:
            permit = await self._authorize_glasshive_delivery(delivery)
        except Exception as exc:
            await self._mark_glasshive_delivery_status(
                delivery,
                "failed",
                error=f"Telegram authorization failed: {str(exc)[:200]}",
            )
            return False
        if not permit:
            return False
        delivery["dispatchPermit"] = permit
        try:
            result, final_permit = await self._send_glasshive_with_permit(
                delivery, chat_id, text, permit
            )
            delivery["dispatchPermit"] = final_permit
            sent = bool(result.get("sent")) if isinstance(result, dict) else bool(result)
            message_ids = (
                extract_telegram_delivery_message_ids(result)
                if isinstance(result, dict)
                else []
            )
            if sent and message_ids:
                delivery["telegramSentMessageIds"] = message_ids
                settled = await self._mark_glasshive_delivery_status(delivery, "sent")
                return settled is not False
            if sent:
                await self._mark_glasshive_delivery_status(
                    delivery,
                    "delivery_unknown",
                    reason="telegram_receipt_missing_after_send",
                )
                return False
            await self._release_glasshive_delivery(delivery, delivery["dispatchPermit"])
            delivery.pop("dispatchPermit", None)
            await self._mark_glasshive_delivery_status(
                delivery, "failed", error="Telegram send returned false"
            )
            return False
        except _GlassHiveDeliveryAuthorizationLost as exc:
            if not exc.transport_started:
                await self._release_glasshive_delivery(
                    delivery,
                    delivery["dispatchPermit"],
                )
                delivery.pop("dispatchPermit", None)
                await self._mark_glasshive_delivery_status(
                    delivery,
                    "failed",
                    error=f"Telegram pre-send authorization failed: {str(exc)[:200]}",
                )
                return False
            await self._mark_glasshive_delivery_status(
                delivery,
                "delivery_unknown",
                reason=f"telegram_send_outcome_unknown:{str(exc)[:200]}",
            )
            return False
        except Exception as exc:
            await self._mark_glasshive_delivery_status(
                delivery,
                "delivery_unknown",
                reason=f"telegram_send_outcome_unknown:{str(exc)[:200]}",
            )
            return False
    # === VIVENTIUM END ===

    def get_cached_voice_route(self, chat_id: str) -> Optional[dict[str, Any]]:
        normalized_chat_id = str(chat_id or "").strip()
        if not normalized_chat_id:
            return None
        route = self._voice_route_by_chat.get(normalized_chat_id)
        if isinstance(route, dict):
            return route
        return None

    # === VIVENTIUM START ===
    # Feature: Telegram saved-voice-route parity.
    # Purpose: The bridge uses a per-user conversation key for history, while
    # Telegram delivery uses the raw chat id. Cache the resolved route under
    # every stable key so final/proactive TTS cannot drift to process defaults.
    def _cache_voice_route(self, voice_route: Optional[dict[str, Any]], *keys: object) -> None:
        if not isinstance(voice_route, dict):
            return
        for key in keys:
            normalized_key = str(key or "").strip()
            if normalized_key:
                self._voice_route_by_chat[normalized_key] = voice_route
    # === VIVENTIUM END ===

    # === VIVENTIUM START ===
    def _trace(self, message: str, *args: Any) -> None:
        if self._trace_enabled:
            logger.info(message, *args)
    # === VIVENTIUM END ===

    # === VIVENTIUM START ===
    # Feature: Active stream tracking + ordering for follow-ups.
    # Also: Resolve Telegram chat IDs for composite convo keys and track cortex activity to avoid premature exits.
    def _get_stream_final_event(self, stream_id: str) -> asyncio.Event:
        event = self._stream_final_events.get(stream_id)
        if event is None:
            event = asyncio.Event()
            self._stream_final_events[stream_id] = event
        return event

    def _mark_stream_final(self, stream_id: str) -> None:
        self._get_stream_final_event(stream_id).set()

    async def _await_stream_final(self, stream_id: str, timeout_s: float) -> bool:
        event = self._get_stream_final_event(stream_id)
        if event.is_set():
            return True
        try:
            await asyncio.wait_for(event.wait(), timeout=max(timeout_s, 0.1))
            return True
        except asyncio.TimeoutError:
            return False

    def _is_stream_active(self, chat_id: str, stream_id: str) -> bool:
        return stream_id in self._active_stream_by_chat.get(chat_id, set())

    def _set_active_stream(self, chat_id: str, stream_id: str) -> None:
        streams = self._active_stream_by_chat.setdefault(chat_id, set())
        streams.add(stream_id)

    def _clear_active_stream(self, chat_id: str, stream_id: str) -> None:
        streams = self._active_stream_by_chat.get(chat_id)
        if not streams:
            return
        streams.discard(stream_id)
        if not streams:
            self._active_stream_by_chat.pop(chat_id, None)

    def _cancel_insight_task(self, stream_id: str) -> None:
        task = self._insight_task_by_stream.pop(stream_id, None)
        if task and not task.done():
            task.cancel()

    def _cancel_followup_task(self, stream_id: str) -> None:
        task = self._followup_task_by_stream.pop(stream_id, None)
        if task and not task.done():
            task.cancel()

    def _mark_followup_sent(self, stream_id: str) -> None:
        self._followup_sent.add(stream_id)
        if stream_id in self._memory_poll_cursors:
            self._save_memory_poll(stream_id)

    def _has_followup_sent(self, stream_id: str) -> bool:
        return stream_id in self._followup_sent

    def _remember_stream_text(self, stream_id: str, text: str, *, brief_main_reply: bool) -> None:
        normalized = _normalize_stream_delivery_compare_text(text)
        if normalized:
            self._stream_text_by_stream[stream_id] = normalized
            self._stream_text_hash_by_stream[stream_id] = hashlib.sha256(normalized.encode()).hexdigest()
        else:
            self._stream_text_by_stream.pop(stream_id, None)
            self._stream_text_hash_by_stream.pop(stream_id, None)
        if brief_main_reply:
            self._brief_main_reply_by_stream[stream_id] = True
        else:
            self._brief_main_reply_by_stream.pop(stream_id, None)

    def _should_send_canonical_text(self, stream_id: str, canonical_text: Any) -> bool:
        canonical = _normalize_stream_delivery_compare_text(canonical_text)
        if not canonical or is_no_response_only(canonical):
            return False

        streamed = self._stream_text_by_stream.get(stream_id, "")
        if canonical == streamed or hashlib.sha256(canonical.encode()).hexdigest() == self._stream_text_hash_by_stream.get(stream_id):
            return False

        if not streamed and stream_id not in self._stream_text_hash_by_stream:
            return True

        return self._brief_main_reply_by_stream.get(stream_id, False)

    def _matches_streamed_text(self, stream_id: str, text: Any) -> bool:
        candidate = _normalize_stream_delivery_compare_text(text)
        if not candidate:
            return False
        return (candidate == self._stream_text_by_stream.get(stream_id, "")
                or hashlib.sha256(candidate.encode()).hexdigest() == self._stream_text_hash_by_stream.get(stream_id))

    async def _emit_followup_once(
        self,
        *,
        stream_id: Optional[str],
        emit: Callable[[], Awaitable[bool]],
    ) -> bool:
        # === VIVENTIUM START ===
        # Feature: Phase A/B follow-up race guard.
        # Root cause: both SSE listener and DB poll path could pass an early dedupe check,
        # yield, then each deliver follow-up text/insights.
        # Fix: per-stream lock + check-and-mark in one critical section.
        # === VIVENTIUM END ===
        if not stream_id:
            return bool(await emit())
        lock = self._followup_send_lock_by_stream.get(stream_id)
        if lock is None:
            lock = asyncio.Lock()
            self._followup_send_lock_by_stream[stream_id] = lock
        async with lock:
            if self._has_followup_sent(stream_id):
                return False
            sent = bool(await emit())
            if sent:
                self._mark_followup_sent(stream_id)
            return sent

    def _poll_delivery_authority(
        self,
        stream_id: Optional[str],
        cortex_delivery: Optional[dict[str, Any]] = None,
    ) -> Optional[dict[str, Any]]:
        identity = self._stream_identity.get(stream_id or "", {})
        logical_turn_id = str(identity.get("logical_turn_id") or "").strip()
        raw_revision = identity.get("logical_turn_revision")
        if cortex_delivery:
            delivery_turn_id = str(cortex_delivery.get("logicalTurnId") or "").strip()
            delivery_revision = cortex_delivery.get("logicalTurnRevision")
            if logical_turn_id and delivery_turn_id != logical_turn_id:
                return None
            if raw_revision is not None and delivery_revision != raw_revision:
                return None
            logical_turn_id = delivery_turn_id
            raw_revision = delivery_revision
        try:
            source_sequence = int(identity.get("presentation_source_sequence") or identity.get("telegram_message_id"))
            logical_turn_revision = int(raw_revision)
        except (TypeError, ValueError):
            return None
        raw_thread_id = str(identity.get("telegram_message_thread_id") or "").strip()
        try:
            thread_id = int(raw_thread_id) if raw_thread_id else 0
        except (TypeError, ValueError):
            return None
        if (
            source_sequence <= 0
            or logical_turn_revision <= 0
            or isinstance(raw_revision, bool)
            or not logical_turn_id
            or not str(identity.get("telegram_user_id") or "").strip()
            or not str(identity.get("telegram_chat_id") or "").strip()
            or (raw_thread_id and thread_id <= 0)
        ):
            return None
        return {
            "telegram_user_id": identity["telegram_user_id"],
            "telegram_chat_id": identity["telegram_chat_id"],
            "telegram_message_thread_id": raw_thread_id,
            "source_sequence": source_sequence,
            "logical_turn_id": logical_turn_id,
            "logical_turn_revision": logical_turn_revision,
        }

    async def _poll_delivery_is_current(self, authority: dict[str, Any]) -> bool:
        try:
            return await self.source_order_is_current(
                telegram_user_id=authority["telegram_user_id"],
                telegram_chat_id=authority["telegram_chat_id"],
                telegram_message_thread_id=authority["telegram_message_thread_id"],
                source_sequence=authority["source_sequence"],
            )
        except Exception as exc:
            logger.warning(
                "Telegram poll delivery source-order check failed closed: %s",
                type(exc).__name__,
            )
            return False

    async def _record_poll_delivery_state(
        self,
        *,
        authority: dict[str, Any],
        state: str,
        presentation_refs: list[str],
        cortex_delivery: Optional[dict[str, Any]],
    ) -> str:
        payload = {
            "logical_turn_id": authority["logical_turn_id"],
            "revision": authority["logical_turn_revision"],
            "state": state,
            "presentation_ref": presentation_refs[-1],
            "presentation_refs": presentation_refs,
            "cortex_presentation": (
                cortex_delivery.get("cortexPresentation")
                if state == "committed" and cortex_delivery
                else None
            ),
        }
        ack_key = self._cortex_ack_store.enqueue(payload)
        return await self._settle_cortex_acknowledgement(ack_key, payload)

    async def _send_poll_delivery(
        self,
        chat_id: str,
        text: str,
        *,
        stream_id: Optional[str],
        cortex_delivery: Optional[dict[str, Any]],
        authorize_before_side_effect: Optional[Callable[[], Awaitable[bool]]] = None,
    ) -> bool:
        authority = self._poll_delivery_authority(stream_id, cortex_delivery)
        if authority is None:
            logger.warning("Telegram poll delivery suppressed without complete turn authority")
            return False
        if not await self._poll_delivery_is_current(authority):
            return False

        async def ensure_current_before_transport() -> bool:
            if not await self._poll_delivery_is_current(authority):
                raise _TelegramPollDeliveryStale()
            if authorize_before_side_effect is not None:
                await authorize_before_side_effect()
            return True

        receipt = await self._send_followup_text(
            chat_id,
            text,
            stream_id=stream_id,
            return_receipt=True,
            before_side_effect=ensure_current_before_transport,
        )
        message_ids = (
            receipt.get("message_ids")
            if isinstance(receipt, dict) and receipt.get("sent") is True
            else []
        )
        target_chat_id = self._resolve_telegram_chat_id(
            chat_id=chat_id,
            stream_id=stream_id,
        )
        if target_chat_id is None or not message_ids:
            if isinstance(receipt, dict) and receipt.get("stale") is True:
                return False
            raise RuntimeError("Telegram poll delivery returned no exact presentation receipt")
        presentation_refs = [
            f"telegram:{target_chat_id}:{message_id}"
            for message_id in message_ids
            if str(message_id).strip()
        ]
        if not presentation_refs:
            raise RuntimeError("Telegram poll delivery returned no exact presentation receipt")
        transport_reported_stale = (
            isinstance(receipt, dict) and receipt.get("stale") is True
        )
        if transport_reported_stale or not await self._poll_delivery_is_current(authority):
            await self._retract_cortex_presentation_refs(presentation_refs)
            status = await self._record_poll_delivery_state(
                authority=authority,
                state="partial_removed",
                presentation_refs=presentation_refs,
                cortex_delivery=cortex_delivery,
            )
            if status != "recorded":
                logger.warning(
                    "Telegram stale poll delivery acknowledgement was not recorded: %s",
                    status,
                )
            return False
        status = await self._record_poll_delivery_state(
            authority=authority,
            state="committed",
            presentation_refs=presentation_refs,
            cortex_delivery=cortex_delivery,
        )
        if status != "recorded":
            logger.warning(
                "Telegram poll delivery acknowledgement was not recorded: %s",
                status,
            )
        if status in {
            "conflict",
            "stale_revision",
            "stale_source_order",
            "not_found",
        }:
            removal_status = await self._record_poll_delivery_state(
                authority=authority,
                state="partial_removed",
                presentation_refs=presentation_refs,
                cortex_delivery=cortex_delivery,
            )
            if removal_status != "recorded":
                logger.warning(
                    "Telegram retracted poll delivery acknowledgement was not recorded: %s",
                    removal_status,
                )
            return False
        return True

    async def _send_followup_text_once(
        self,
        chat_id: str,
        text: str,
        *,
        stream_id: Optional[str],
        cortex_delivery: Optional[dict[str, Any]] = None,
        enforce_order_fence: bool = False,
        authorize_before_side_effect: Optional[Callable[[], Awaitable[bool]]] = None,
    ) -> bool:
        async def _emit() -> bool:
            if enforce_order_fence:
                return await self._send_poll_delivery(
                    chat_id,
                    text,
                    stream_id=stream_id,
                    cortex_delivery=cortex_delivery,
                    authorize_before_side_effect=authorize_before_side_effect,
                )
            if not cortex_delivery:
                return bool(
                    await self._send_followup_text(chat_id, text, stream_id=stream_id)
                )
            receipt = await self._send_followup_text(
                chat_id,
                text,
                stream_id=stream_id,
                return_receipt=True,
            )
            message_ids = (
                receipt.get("message_ids")
                if isinstance(receipt, dict) and receipt.get("sent") is True
                else []
            )
            target_chat_id = self._resolve_telegram_chat_id(
                chat_id=chat_id,
                stream_id=stream_id,
            )
            if target_chat_id is None or not message_ids:
                raise RuntimeError("Cortex Telegram delivery returned no exact presentation receipt")
            presentation_refs = [
                f"telegram:{target_chat_id}:{message_id}"
                for message_id in message_ids
                if str(message_id).strip()
            ]
            payload = {
                "logical_turn_id": cortex_delivery["logicalTurnId"],
                "revision": cortex_delivery["logicalTurnRevision"],
                "state": "committed",
                "presentation_ref": presentation_refs[-1],
                "presentation_refs": presentation_refs,
                "cortex_presentation": cortex_delivery["cortexPresentation"],
            }
            ack_key = self._cortex_ack_store.enqueue(payload)
            status = await self._settle_cortex_acknowledgement(ack_key, payload)
            if status != "recorded":
                logger.warning(
                    "Cortex Telegram presentation acknowledgement was not recorded: %s",
                    status,
                )
            return status not in {
                "conflict",
                "stale_revision",
                "stale_source_order",
                "not_found",
            }

        return await self._emit_followup_once(stream_id=stream_id, emit=_emit)

    async def _send_pending_insights_once(
        self,
        chat_id: str,
        insights: list[dict[str, Any]],
        *,
        stream_id: Optional[str],
        enforce_order_fence: bool = True,
    ) -> bool:
        voice_mode = self._stream_voice_mode(stream_id)
        text = self._format_pending_insights(insights, voice_mode=voice_mode)
        if not text:
            return False
        return await self._send_followup_text_once(
            chat_id,
            text,
            stream_id=stream_id,
            enforce_order_fence=enforce_order_fence,
        )

    def _set_stream_identity(
        self,
        *,
        stream_id: str,
        telegram_chat_id: str,
        telegram_user_id: str,
        telegram_username: str,
        voice_mode: Optional[bool] = None,
        input_mode: str = "",
        voice_route: Optional[dict[str, Any]] = None,
        telegram_message_id: Any = "",
        telegram_message_thread_id: Any = "",
        logical_turn_id: str = "",
        logical_turn_revision: Optional[int] = None,
        input_presentation: Optional[dict[str, Any]] = None,
    ) -> None:
        self._stream_identity[stream_id] = {
            "telegram_chat_id": telegram_chat_id,
            "telegram_user_id": telegram_user_id,
            "telegram_username": telegram_username,
            "voice_mode": "1" if voice_mode else "",
            "input_mode": input_mode or "",
            "voice_route": voice_route or None,
            "telegram_message_id": str(telegram_message_id or ""),
            "telegram_message_thread_id": str(telegram_message_thread_id or ""),
            "logical_turn_id": str(logical_turn_id or ""),
            "logical_turn_revision": logical_turn_revision,
            "presentation_source_sequence": (input_presentation or {}).get("presentationSourceSequence"),
        }

    def _get_identity_params(self, stream_id: str) -> dict[str, str]:
        identity = self._stream_identity.get(stream_id, {})
        params: dict[str, str] = {}
        chat_id = identity.get("telegram_chat_id") or ""
        user_id = identity.get("telegram_user_id") or ""
        username = identity.get("telegram_username") or ""
        if chat_id:
            params["telegramChatId"] = chat_id
        if user_id:
            params["telegramUserId"] = user_id
        if username:
            params["telegramUsername"] = username
        return params

    def _stream_voice_mode(self, stream_id: Optional[str]) -> bool:
        if not stream_id:
            return False
        identity = self._stream_identity.get(stream_id, {})
        return identity.get("voice_mode") == "1"

    def _stream_input_mode(self, stream_id: Optional[str]) -> str:
        if not stream_id:
            return ""
        identity = self._stream_identity.get(stream_id, {})
        return identity.get("input_mode") or ""

    def _stream_voice_route(self, stream_id: Optional[str]) -> Optional[dict[str, Any]]:
        if not stream_id:
            return None
        identity = self._stream_identity.get(stream_id, {})
        voice_route = identity.get("voice_route")
        return voice_route if isinstance(voice_route, dict) else None

    # Resolve Telegram chat id from composite convo keys or stored identity.
    # Needed because convo_id includes user/thread suffixes which break int() in follow-up delivery.
    def _resolve_telegram_chat_id(self, *, chat_id: str, stream_id: Optional[str]) -> Optional[int]:
        identity = self._stream_identity.get(stream_id or "", {}) if stream_id else {}
        candidate = identity.get("telegram_chat_id") or chat_id
        if isinstance(candidate, int):
            return candidate
        if not isinstance(candidate, str):
            return None
        raw = candidate.strip()
        if not raw:
            return None
        try:
            return int(raw)
        except ValueError:
            if ":" in raw:
                prefix = raw.split(":", 1)[0]
                try:
                    return int(prefix)
                except ValueError:
                    pass
        logger.warning(
            "LibreChatBridge unable to resolve Telegram chat id: chat_id=%s stream_id=%s",
            chat_id,
            stream_id,
        )
        return None

    async def _deliver_callback(
        self,
        target_chat_id: int,
        message: str,
        *,
        parse_mode: Optional[str] = None,
        preference_convo_id: Optional[str] = None,
        raw_message: Optional[str] = None,
        stream_id: Optional[str] = None,
        return_receipt: bool = False,
        before_side_effect: Optional[Callable[[], Awaitable[bool]]] = None,
    ) -> Any:
        if not self.on_message_callback:
            return False
        # === VIVENTIUM START ===
        # Feature: Proactive follow-up voice parity.
        # Purpose: Apply existing voice preference gate + TTS for callback delivery.
        voice_audio: Optional[bytes] = None
        convo_id = preference_convo_id or str(target_chat_id)
        voice_route = self._stream_voice_route(stream_id) or self.get_cached_voice_route(str(target_chat_id))
        voice_text = (
            raw_message
            if isinstance(raw_message, str) and raw_message.strip()
            else message
        )
        delivery_plan = parse_delivery_controls(voice_text)
        voice_text = delivery_plan.clean_text
        if isinstance(raw_message, str) and raw_message.strip():
            message = render_telegram_markdown(voice_text, strip_voice_markup=True)
            parse_mode = "HTML"
        else:
            message = strip_delivery_controls_for_preview(message)
        should_send_voice = False
        model_skip_effective = False
        if voice_text and convo_id:
            try:
                from config import Users  # local import to avoid circular dependency
                from utils.tts import synthesize_speech
                from utils.voice import should_send_voice_reply

                always_voice = Users.get_config(convo_id, "ALWAYS_VOICE_RESPONSE")
                voice_responses_enabled = Users.get_config(convo_id, "VOICE_RESPONSES_ENABLED")
                should_send_voice = should_send_voice_reply(
                    voice_note_detected=False,
                    always_voice=always_voice,
                    voice_enabled=voice_responses_enabled,
                    text=voice_text,
                )
                model_skip_effective = bool(delivery_plan.skip_voice and should_send_voice)
                if delivery_plan.skip_voice:
                    should_send_voice = False
                if should_send_voice:
                    voice_audio = await synthesize_speech(
                        voice_text,
                        convo_id,
                        voice_route=voice_route,
                    )
            except Exception as exc:
                logger.warning("Failed proactive voice synthesis, falling back to text: %s", exc)
        logger.info(
            "[TG_VOICE] proactive gate send=%s voice_decision=%s model_skip_requested=%s "
            "model_skip_effective=%s tts_avoided_chars=%s msg_breaks=%s segments=%s "
            "segment_merge=%s",
            int(bool(should_send_voice)),
            (
                "skipped_model"
                if model_skip_effective
                else ("sent" if should_send_voice else "disabled_user")
            ),
            int(bool(delivery_plan.skip_voice)),
            int(model_skip_effective),
            len(voice_text) if model_skip_effective else 0,
            delivery_plan.message_break_count,
            len(delivery_plan.segments),
            delivery_plan.merged_break_count,
        )
        # === VIVENTIUM END ===

        async def _invoke_callback(
            payload: str,
            *,
            payload_parse_mode: Optional[str],
            payload_voice_audio: Optional[bytes],
        ) -> Any:
            if return_receipt:
                callback_parameters = inspect.signature(self.on_message_callback).parameters
                accepts_kwargs = any(
                    parameter.kind is inspect.Parameter.VAR_KEYWORD
                    for parameter in callback_parameters.values()
                )
                callback_kwargs: dict[str, Any] = {}
                if accepts_kwargs or "parse_mode" in callback_parameters:
                    callback_kwargs["parse_mode"] = payload_parse_mode
                if accepts_kwargs or "voice_audio" in callback_parameters:
                    callback_kwargs["voice_audio"] = payload_voice_audio
                identity = self._stream_identity.get(stream_id or "", {})
                raw_thread_id = str(identity.get("telegram_message_thread_id") or "").strip()
                if raw_thread_id.isdigit() and int(raw_thread_id) > 0:
                    if accepts_kwargs or "message_thread_id" in callback_parameters:
                        callback_kwargs["message_thread_id"] = int(raw_thread_id)
                if before_side_effect is not None and (
                    accepts_kwargs or "before_side_effect" in callback_parameters
                ):
                    callback_kwargs["before_side_effect"] = before_side_effect
                elif before_side_effect is not None:
                    await before_side_effect()
                if asyncio.iscoroutinefunction(self.on_message_callback):
                    return await self.on_message_callback(
                        target_chat_id,
                        payload,
                        **callback_kwargs,
                    )
                return self.on_message_callback(
                    target_chat_id,
                    payload,
                    **callback_kwargs,
                )
            if asyncio.iscoroutinefunction(self.on_message_callback):
                try:
                    return await self.on_message_callback(
                        target_chat_id,
                        payload,
                        parse_mode=payload_parse_mode,
                        voice_audio=payload_voice_audio,
                    )
                except TypeError:
                    try:
                        return await self.on_message_callback(
                            target_chat_id,
                            payload,
                            parse_mode=payload_parse_mode,
                        )
                    except TypeError:
                        return await self.on_message_callback(target_chat_id, payload)
            else:
                try:
                    return self.on_message_callback(
                        target_chat_id,
                        payload,
                        parse_mode=payload_parse_mode,
                        voice_audio=payload_voice_audio,
                    )
                except TypeError:
                    try:
                        return self.on_message_callback(
                            target_chat_id,
                            payload,
                            parse_mode=payload_parse_mode,
                        )
                    except TypeError:
                        return self.on_message_callback(target_chat_id, payload)

        try:
            delivered_message_ids: list[str] = []
            # === VIVENTIUM START ===
            # Feature: Chunk proactive follow-up text before callback delivery.
            # Purpose: Telegram rejects oversized messages; split long follow-ups while
            # preserving existing HTML formatting behavior for each chunk. When
            # proactive voice is enabled, keep text canonical and attach audio only
            # to the final chunk so users do not receive duplicate voice notes.
            if isinstance(raw_message, str) and raw_message.strip():
                payloads = [
                    chunk
                    for segment in delivery_plan.segments
                    for chunk in split_telegram_html(
                        render_telegram_markdown(segment, strip_voice_markup=True),
                        limit=3500,
                    )
                    if chunk.strip()
                ]
                payload_parse_mode = "HTML"
            else:
                payloads = [
                    chunk
                    for chunk in split_telegram_html(message, limit=3500)
                    if chunk.strip()
                ]
                payload_parse_mode = parse_mode

            if not payloads:
                if return_receipt:
                    return {"sent": False, "message_ids": []}
                return False

            last_index = len(payloads) - 1
            for index, payload in enumerate(payloads):
                callback_result = await _invoke_callback(
                    payload,
                    payload_parse_mode=payload_parse_mode,
                    payload_voice_audio=voice_audio if index == last_index else None,
                )
                if callback_result is False:
                    if return_receipt:
                        return {"sent": False, "message_ids": list(dict.fromkeys(delivered_message_ids))[:32]}
                    return False
                delivered_message_ids.extend(
                    extract_telegram_delivery_message_ids(callback_result)
                )
            if return_receipt:
                return {
                    "sent": True,
                    "message_ids": list(dict.fromkeys(delivered_message_ids))[:32],
                }
            return True
            # === VIVENTIUM END ===
        except _GlassHiveDeliveryAuthorizationLost:
            raise
        except _TelegramPollDeliveryStale:
            if return_receipt:
                return {
                    "sent": bool(delivered_message_ids),
                    "message_ids": list(dict.fromkeys(delivered_message_ids))[:32],
                    "stale": True,
                }
            return False
        except Exception as exc:
            logger.warning("Failed to deliver Telegram callback: %s", exc)
            if return_receipt:
                raise
            try:
                await _invoke_callback(
                    TELEGRAM_CALLBACK_INTERRUPTED_NOTICE,
                    payload_parse_mode=None,
                    payload_voice_audio=None,
                )
            except Exception as notice_exc:
                logger.warning(
                    "Failed to deliver Telegram callback interruption notice: %s",
                    notice_exc,
                )
            return False

    # Track cortex activity seen on SSE so DB polling doesn't exit before persistence catches up.
    def _mark_cortex_seen(self, stream_id: str) -> None:
        self._cortex_seen_by_stream[stream_id] = True

    def _has_cortex_seen(self, stream_id: str) -> bool:
        return self._cortex_seen_by_stream.get(stream_id, False)

    def _mark_glasshive_seen(self, stream_id: str) -> None:
        self._glasshive_seen_by_stream.add(stream_id)

    def _has_glasshive_seen(self, stream_id: str) -> bool:
        return stream_id in self._glasshive_seen_by_stream

    def _has_active_background_tasks(self, stream_id: str) -> bool:
        followup_task = self._followup_task_by_stream.get(stream_id)
        if followup_task and not followup_task.done():
            return True
        insight_task = self._insight_task_by_stream.get(stream_id)
        if insight_task and not insight_task.done():
            return True
        return False
    # === VIVENTIUM END ===

    def capture_conversation_state(self, convo_id: str) -> dict[str, str]:
        """Capture once before preparation so reset cannot move an older source into a new chat."""
        chat_id = str(convo_id)
        if self._get_conversation_state:
            state = self._get_conversation_state(chat_id)
            if (not isinstance(state, dict)
                    or not isinstance(state.get("conversation_id"), str)
                    or not re.fullmatch(r"[a-f0-9]{64}", str(state.get("generation") or ""))):
                raise RuntimeError("Invalid Telegram conversation state")
            return dict(state)
        return {
            "conversation_id": self._get_conversation_id(chat_id) or "",
            "generation": self._conversation_generations.setdefault(chat_id, uuid.uuid4().hex + uuid.uuid4().hex),
        }

    def reset(self, convo_id: str, system_prompt: Optional[str] = None) -> None:
        _ = system_prompt
        chat_id = str(convo_id)
        self._set_conversation_id(chat_id, "")
        self._conversation_generations[chat_id] = uuid.uuid4().hex + uuid.uuid4().hex

    def _track_task(self, task: asyncio.Task) -> None:
        self._insight_tasks.add(task)

        def _done(t: asyncio.Task) -> None:
            self._insight_tasks.discard(t)
            try:
                exc = t.exception()
            except asyncio.CancelledError:
                return
            if exc:
                logger.warning("LibreChatBridge insight task failed: %s", exc)

        task.add_done_callback(_done)

    def _retain_insight_seen(self, stream_id: str) -> set[str]:
        seen = self._insight_seen.get(stream_id)
        if seen is None:
            seen = set()
            self._insight_seen[stream_id] = seen
        self._insight_refs[stream_id] = self._insight_refs.get(stream_id, 0) + 1
        return seen

    def _release_insight_seen(self, stream_id: str) -> None:
        refs = self._insight_refs.get(stream_id)
        if refs is None:
            return
        refs -= 1
        if refs <= 0:
            self._insight_refs.pop(stream_id, None)
            self._insight_seen.pop(stream_id, None)
        else:
            self._insight_refs[stream_id] = refs

    def _should_emit_insight(self, stream_id: str, insight: dict[str, Any]) -> bool:
        key = self._insight_key(insight)
        if not key:
            return False
        seen = self._insight_seen.get(stream_id)
        if seen is None:
            seen = self._retain_insight_seen(stream_id)
            self._release_insight_seen(stream_id)
        if key in seen:
            return False
        seen.add(key)
        return True

    # === VIVENTIUM START ===
    def _get_chat_lock(self, chat_id: str) -> asyncio.Lock:
        lock = self._chat_locks.get(chat_id)
        if lock is None:
            lock = asyncio.Lock()
            self._chat_locks[chat_id] = lock
        return lock

    # === VIVENTIUM START ===
    # Feature: Optional timing logs for Telegram -> LibreChat bridge.
    def _timing_enabled(self) -> bool:
        return (os.getenv("VIVENTIUM_TELEGRAM_TIMING_ENABLED") or "").strip() == "1"

    def _timing_log(self, trace_id: str, step: str, start_ts: float, extra: Optional[str] = None) -> None:
        if not self._timing_enabled():
            return
        elapsed_ms = (time.monotonic() - start_ts) * 1000.0
        if extra:
            logger.info("[TG_TIMING][bridge] trace=%s step=%s ms=%.1f %s", trace_id, step, elapsed_ms, extra)
        else:
            logger.info("[TG_TIMING][bridge] trace=%s step=%s ms=%.1f", trace_id, step, elapsed_ms)
    # === VIVENTIUM END ===

    async def _await_insight_task(self, task: Optional[asyncio.Task]) -> None:
        if not task:
            return
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=max(self.insight_max_s, 1.0))
        except asyncio.TimeoutError:
            task.cancel()
        except Exception as exc:
            logger.warning("LibreChatBridge insight wait failed: %s", exc)
    # === VIVENTIUM END ===

    async def ask_stream_async(self, text: str, convo_id: str, **kwargs) -> AsyncIterator[Any]:
        chat_id = str(convo_id)
        conversation_state = kwargs.get("conversation_state") or self.capture_conversation_state(chat_id)
        if (not isinstance(conversation_state, dict)
                or not isinstance(conversation_state.get("conversation_id"), str)
                or not re.fullmatch(r"[a-f0-9]{64}", str(conversation_state.get("generation") or ""))):
            raise ValueError("Invalid Telegram source conversation state")
        # === VIVENTIUM START ===
        # Feature: Pass Telegram identity for per-user linking and auth.
        # === VIVENTIUM END ===
        telegram_chat_id_value = kwargs.get("telegram_chat_id") or kwargs.get("telegramChatId")
        telegram_chat_id = telegram_chat_id_value or chat_id
        telegram_user_id = kwargs.get("telegram_user_id") or kwargs.get("telegramUserId") or ""
        telegram_username = kwargs.get("telegram_username") or kwargs.get("telegramUsername") or ""
        telegram_message_id = kwargs.get("telegram_message_id") or kwargs.get("telegramMessageId") or ""
        telegram_message_thread_id = kwargs.get("telegram_message_thread_id")
        if telegram_message_thread_id is None:
            telegram_message_thread_id = kwargs.get("telegramMessageThreadId")
        if telegram_message_thread_id is None:
            telegram_message_thread_id = ""
        telegram_update_id = kwargs.get("telegram_update_id") or kwargs.get("telegramUpdateId") or ""
        source_event_id = kwargs.get("source_event_id") or kwargs.get("sourceEventId") or ""
        provided_source_order_scope = kwargs.get("source_order_scope")
        if provided_source_order_scope is None:
            provided_source_order_scope = kwargs.get("sourceOrderScope")
        # === VIVENTIUM START ===
        # Feature: Voice mode metadata for surface-specific formatting.
        voice_mode = kwargs.get("voice_mode")
        if voice_mode is None:
            voice_mode = kwargs.get("voiceMode")
        input_mode = kwargs.get("input_mode") or kwargs.get("inputMode") or ""
        audio_requested = kwargs.get("audio_requested")
        if audio_requested is None:
            audio_requested = kwargs.get("telegramAudioRequested")
        if audio_requested is None:
            audio_requested = kwargs.get("audioRequested")
        # Feature: File upload support for vision models.
        files = kwargs.get("files") or None
        # Feature: Time context - pass message timestamp for scheduling awareness.
        message_timestamp = kwargs.get("message_timestamp") or kwargs.get("messageTimestamp") or None
        # Feature: Timezone context for accurate local time formatting.
        client_timezone = kwargs.get("client_timezone") or kwargs.get("clientTimezone") or None
        # Feature: Optional trace id for timing/log correlation.
        trace_id = kwargs.get("trace_id") or kwargs.get("traceId") or ""
        reply_context = kwargs.get("reply_context") or kwargs.get("replyContextV1") or None
        input_claim = kwargs.get("input_claim")
        input_claims = kwargs.get("input_claims")
        input_recovery = kwargs.get("input_recovery")
        # === VIVENTIUM END ===
        source_surface = str(kwargs.get("surface") or "telegram").strip().lower()
        if source_surface not in {"telegram", "web", "voice", "workbench"}:
            yield _bridge_error_event(
                "Telegram message order could not be verified. Please retry.",
                speak=False,
            )
            return
        try:
            normalized_source_sequence = int(telegram_message_id)
        except (TypeError, ValueError):
            normalized_source_sequence = 0
        raw_thread_id = str(telegram_message_thread_id).strip()
        try:
            normalized_thread_id = int(raw_thread_id) if raw_thread_id else 0
        except (TypeError, ValueError):
            normalized_thread_id = -1
        source_order_scope = str(provided_source_order_scope or "")
        valid_source_identity = bool(
            telegram_user_id
            and telegram_chat_id_value
            and normalized_source_sequence > 0
            and (not raw_thread_id or normalized_thread_id > 0)
        )
        source_event_id = str(source_event_id or "")
        if source_surface == "telegram" and not valid_source_identity:
            yield _bridge_error_event(
                "Telegram message order could not be verified. Please retry.",
                speak=False,
            )
            return
        if source_surface != "telegram":
            source_order_scope = ""
            source_event_id = ""
        elif bool(source_order_scope) != bool(source_event_id):
            yield _bridge_error_event(
                "Telegram message order could not be verified. Please retry.",
                speak=False,
            )
            return
        elif source_order_scope and (
            not re.fullmatch(r"[a-f0-9]{64}", source_order_scope)
            or not re.fullmatch(r"[a-f0-9]{64}", source_event_id)
        ):
            yield _bridge_error_event(
                "Telegram message order could not be verified. Please retry.",
                speak=False,
            )
            return
        if source_surface == "telegram" and not source_order_scope:
            try:
                observation = await self.observe_source_order(
                    telegram_user_id=telegram_user_id,
                    telegram_chat_id=telegram_chat_id,
                    telegram_message_thread_id=telegram_message_thread_id,
                    source_sequence=telegram_message_id,
                )
            except TelegramLinkRequired:
                raise
            except Exception as exc:
                logger.error(
                    "LibreChatBridge source-order observation failed before chat admission: %s",
                    type(exc).__name__,
                )
                yield _bridge_error_event(
                    "Telegram message order could not be verified. Please retry.",
                    speak=False,
                )
                return
            if observation["stale"]:
                yield {"type": "superseded", "reason": "stale_source_order"}
                return
            source_order_scope = str(observation.get("source_order_scope") or "")
            source_event_id = str(observation.get("source_event_id") or "")
            if not re.fullmatch(r"[a-f0-9]{64}", source_order_scope) or not re.fullmatch(
                r"[a-f0-9]{64}", source_event_id
            ):
                yield _bridge_error_event(
                    "Telegram message order could not be verified. Please retry.",
                    speak=False,
                )
                return
        lock: Optional[asyncio.Lock] = self._get_chat_lock(chat_id) if self.serialize_per_chat else None
        # === VIVENTIUM START ===
        # Core normally owns source order. Explicit legacy serialization is diagnostic-only.
        # === VIVENTIUM END ===
        if lock and lock.locked():
            self._trace("LibreChatBridge waiting for prior run: chat_id=%s", chat_id)
        run_guard = lock if lock is not None else _noop_async_context()
        async with run_guard:
            if self.capture_conversation_state(chat_id)["generation"] != conversation_state["generation"]:
                yield {"type": "superseded", "reason": "conversation_reset"}
                return
            session = None
            conversation_id = conversation_state["conversation_id"] or "new"
            agent_id = self.default_agent_id
            if self._get_agent_id:
                stored_agent_id = self._get_agent_id(chat_id)
                if stored_agent_id:
                    agent_id = stored_agent_id

            if not self.base_url or not self.secret:
                yield "Telegram bridge is not configured. Please check VIVENTIUM_TELEGRAM_SECRET and VIVENTIUM_LIBRECHAT_ORIGIN."
                return

            try:
                # === VIVENTIUM START ===
                # Pass files for vision model support
                chat_start_ts = time.monotonic()
                start_kwargs = {
                    "text": text,
                    "conversation_id": conversation_id,
                    "conversation_generation": conversation_state["generation"],
                    "agent_id": agent_id,
                    "telegram_chat_id": str(telegram_chat_id),
                    "telegram_user_id": str(telegram_user_id),
                    "telegram_username": str(telegram_username),
                    "telegram_message_id": str(telegram_message_id) if telegram_message_id is not None else "",
                    "telegram_update_id": str(telegram_update_id) if telegram_update_id is not None else "",
                    "preference_convo_id": chat_id,
                    "voice_mode": voice_mode,
                    "input_mode": input_mode,
                    "files": files,
                    "message_timestamp": message_timestamp,
                    "client_timezone": client_timezone,
                    "trace_id": trace_id,
                }
                if audio_requested is not None:
                    start_kwargs["audio_requested"] = audio_requested
                if source_event_id:
                    start_kwargs["source_event_id"] = str(source_event_id)
                if source_order_scope:
                    start_kwargs["source_order_scope"] = source_order_scope
                if telegram_message_thread_id:
                    start_kwargs["telegram_message_thread_id"] = str(
                        telegram_message_thread_id
                    )
                if reply_context:
                    start_kwargs["reply_context"] = reply_context
                if input_claim:
                    start_kwargs["input_claim"] = input_claim
                if input_claims:
                    start_kwargs["input_claims"] = input_claims
                if input_recovery:
                    data = await self.continue_input(input_recovery)
                    session = self._session_from_chat_response(data, conversation_id, resume_retained=True)
                else:
                    session = await self._start_chat_with_connect_retry(**start_kwargs)
                if trace_id:
                    self._timing_log(trace_id, "lc_chat_http", chat_start_ts)
                # === VIVENTIUM END ===
            except TelegramLinkRequired:
                raise
            except Exception as exc:
                logger.error(
                    "LibreChatBridge failed to start chat: type=%s status=%s",
                    type(exc).__name__,
                    getattr(getattr(exc, "response", None), "status_code", ""),
                )
                yield _bridge_error_event(_start_chat_error_message(exc), speak=False)
                return
            if not session:
                return

            if session.input_pending:
                yield {"type": "input_pending", "input_claim": session.input_claim}
                return
            if session.input_presentation:
                yield {"type": "input_presentation", "input_presentation": session.input_presentation}
            if session.superseded:
                yield {"type": "superseded", "reason": "stale_source_order"}
                return

            if session.logical_turn_id:
                yield {
                    "type": "logical_turn",
                    "logical_turn_id": session.logical_turn_id,
                    "revision": session.revision,
                }

            self._trace(
                "LibreChatBridge session start: chat_id=%s stream_id=%s conversation_id=%s agent_id=%s include_insights=%s",
                chat_id,
                session.stream_id,
                session.conversation_id,
                agent_id or "default",
                self.include_insights,
            )
            # === VIVENTIUM START ===
            # Track identity for stream/auth follow-ups.
            # === VIVENTIUM END ===
            self._set_stream_identity(
                stream_id=session.stream_id,
                telegram_chat_id=str(telegram_chat_id),
                telegram_user_id=str(telegram_user_id),
                telegram_username=str(telegram_username),
                voice_mode=voice_mode,
                input_mode=input_mode,
                voice_route=session.voice_route,
                telegram_message_id=telegram_message_id,
                telegram_message_thread_id=telegram_message_thread_id,
                logical_turn_id=session.logical_turn_id,
                logical_turn_revision=session.revision,
                input_presentation=session.input_presentation,
            )
            self._set_active_stream(chat_id, session.stream_id)
            if session.conversation_id:
                self._conversation_by_stream[session.stream_id] = session.conversation_id
            if session.voice_route:
                self._voice_route_by_stream[session.stream_id] = session.voice_route
                self._cache_voice_route(
                    session.voice_route,
                    chat_id,
                    telegram_chat_id,
                    session.conversation_id,
                )
            self._delivery_disposition_required_by_stream[session.stream_id] = bool(
                session.delivery_disposition_required
            )
            insight_task: Optional[asyncio.Task] = None
            if (
                self.on_message_callback
                and self.insight_grace_s > 0
                and self.insight_max_s > 0
            ):
                insight_task = asyncio.create_task(
                    self._listen_for_insights(stream_id=session.stream_id, chat_id=chat_id),
                )
                self._insight_task_by_stream[session.stream_id] = insight_task
                self._track_task(insight_task)

            if (session.conversation_id and session.conversation_id != conversation_id
                    and self.capture_conversation_state(chat_id)["generation"] == conversation_state["generation"]):
                self._set_conversation_id(chat_id, session.conversation_id)
                if agent_id and self._set_agent_id:
                    self._set_agent_id(chat_id, agent_id)

            self._retain_insight_seen(session.stream_id)
            try:
                async for chunk in self._stream_response(session.stream_id, chat_id, trace_id=trace_id):
                    if chunk:
                        yield chunk
            finally:
                # === VIVENTIUM START ===
                # Do not block Telegram responses while insights finish in the background.
                self._release_insight_seen(session.stream_id)
                if insight_task:
                    waiter = asyncio.create_task(self._await_insight_task(insight_task))
                    self._track_task(waiter)
                if session and not self._has_active_background_tasks(session.stream_id):
                    self._stream_identity.pop(session.stream_id, None)
                    self._cortex_seen_by_stream.pop(session.stream_id, None)
                    self._glasshive_seen_by_stream.discard(session.stream_id)
                    self._voice_route_by_stream.pop(session.stream_id, None)
                if session:
                    self._delivery_disposition_required_by_stream.pop(
                        session.stream_id,
                        None,
                    )
                # === VIVENTIUM END ===

    async def _start_chat_with_connect_retry(self, **kwargs: Any) -> Optional[LibreChatSession]:
        for attempt in range(self.start_chat_connect_retries + 1):
            try:
                return await self._start_chat(**kwargs)
            except TelegramLinkRequired:
                raise
            except Exception as exc:
                if (
                    attempt >= self.start_chat_connect_retries
                    or not _start_chat_error_safe_to_retry(exc)
                ):
                    raise
                logger.warning(
                    "LibreChatBridge retrying start chat after pre-ingress connection failure: type=%s attempt=%s/%s",
                    type(exc).__name__,
                    attempt + 1,
                    self.start_chat_connect_retries + 1,
                )
                if self.start_chat_connect_retry_delay_s > 0:
                    await asyncio.sleep(self.start_chat_connect_retry_delay_s)
        return None

    async def _start_chat(
        self,
        *,
        text: str,
        conversation_id: str,
        agent_id: str,
        telegram_chat_id: str,
        telegram_user_id: str,
        telegram_username: str,
        telegram_message_id: str,
        telegram_update_id: str,
        preference_convo_id: Optional[str],
        voice_mode: Optional[bool],
        input_mode: str,
        telegram_message_thread_id: str = "",
        source_event_id: str = "",
        source_order_scope: str = "",
        conversation_generation: str = "",
        audio_requested: Optional[bool] = None,
        files: Optional[list] = None,  # === VIVENTIUM: File upload support ===
        message_timestamp: Optional[str] = None,  # === VIVENTIUM: Time context support ===
        client_timezone: Optional[str] = None,  # === VIVENTIUM: Timezone context support ===
        trace_id: Optional[str] = None,  # === VIVENTIUM: Timing/log correlation ===
        reply_context: Optional[dict[str, Any]] = None,
        input_claim: Optional[dict[str, Any]] = None,
        input_claims: Optional[list[dict[str, Any]]] = None,
    ) -> Optional[LibreChatSession]:
        payload: Dict[str, Any] = {
            "text": text,
            "conversationId": conversation_id,
            "telegramChatId": telegram_chat_id,
        }
        if agent_id:
            payload["agentId"] = agent_id
        # === VIVENTIUM START ===
        # Feature: Pass Telegram identity for per-user auth/linking.
        # === VIVENTIUM END ===
        if telegram_user_id:
            payload["telegramUserId"] = telegram_user_id
        if telegram_username:
            payload["telegramUsername"] = telegram_username
        if telegram_message_id:
            payload["telegramMessageId"] = telegram_message_id
        if telegram_message_thread_id:
            payload["telegramMessageThreadId"] = telegram_message_thread_id
        if telegram_update_id:
            payload["telegramUpdateId"] = telegram_update_id
        if source_event_id:
            payload["sourceEventId"] = source_event_id
        if source_order_scope:
            payload["sourceOrderScope"] = source_order_scope
        if conversation_generation:
            payload["conversationGeneration"] = conversation_generation
        if reply_context:
            payload["replyContextV1"] = reply_context
        if input_claim:
            payload["inputClaim"] = self._input_identity(input_claim)["inputClaim"]
        if input_claims:
            payload["inputClaims"] = [self._input_identity(claim)["inputClaim"] for claim in input_claims]
        # === VIVENTIUM START ===
        # Feature: Opportunistic voice preference sync for scheduler parity.
        pref_convo_id = preference_convo_id or telegram_chat_id
        try:
            from config import Users  # local import to avoid circular dependency
            payload["alwaysVoiceResponse"] = bool(
                Users.get_config(pref_convo_id, "ALWAYS_VOICE_RESPONSE")
            )
            payload["voiceResponsesEnabled"] = bool(
                Users.get_config(pref_convo_id, "VOICE_RESPONSES_ENABLED")
            )
        except Exception:
            # Keep chat path resilient; scheduler will use defaults when unavailable.
            pass
        # === VIVENTIUM END ===
        # === VIVENTIUM START ===
        # Feature: Voice/text surface hints for LibreChat prompt handling.
        # Updated 2026-03-30: The LibreChat Telegram route now resolves the effective
        # per-user voice route server-side and injects `voiceProvider` there, so the bot
        # only needs to pass the voice-mode flag and other surface metadata here.
        if voice_mode is not None:
            payload["voiceMode"] = bool(voice_mode)
        if audio_requested is not None:
            payload["telegramAudioRequested"] = bool(audio_requested)
        if input_mode:
            payload["viventiumInputMode"] = input_mode
        # Feature: File upload for vision model support.
        if files:
            payload["files"] = files
            logger.info(f"[VIVENTIUM] Bridge sending {len(files)} file(s) to LibreChat")
        # Feature: Time context for scheduling awareness.
        if message_timestamp:
            payload["clientTimestamp"] = message_timestamp
        if client_timezone:
            payload["clientTimezone"] = client_timezone
        # Feature: Trace id for timing/log correlation across services.
        if trace_id:
            payload["traceId"] = trace_id
        # === VIVENTIUM END ===

        headers = {"X-VIVENTIUM-TELEGRAM-SECRET": self.secret}
        chat_url = f"{self.base_url}/api/viventium/telegram/chat"

        timeout_s = _parse_positive_float(os.getenv("VIVENTIUM_TELEGRAM_CHAT_TIMEOUT_S", ""), 120.0)
        timeout = httpx.Timeout(timeout_s, connect=10.0, read=timeout_s, write=timeout_s, pool=10.0)
        async with httpx.AsyncClient(
            timeout=timeout,
            **_async_client_options_for_url(chat_url),
        ) as client:
            resp = await client.post(chat_url, json=payload, headers=headers)
            if resp.status_code not in {200, 202}:
                link_payload = None
                try:
                    link_payload = resp.json()
                except Exception:
                    link_payload = None
                if isinstance(link_payload, dict) and link_payload.get("linkRequired") and link_payload.get("linkUrl"):
                    raise TelegramLinkRequired(
                        link_payload.get("linkUrl", ""),
                        link_payload.get("message") or "Link your Viventium account to use Telegram.",
                    )
                request = getattr(resp, "request", httpx.Request("POST", chat_url))
                raise httpx.HTTPStatusError(
                    f"LibreChat chat failed ({resp.status_code})",
                    request=request,
                    response=resp,
                )
            data = resp.json()

        return self._session_from_chat_response(data, conversation_id, resume_retained=bool(input_claim))

    def _session_from_chat_response(self, data, conversation_id, *, resume_retained=False):
        if (isinstance(data, dict) and data.get("code") == "source_input_pending"
                and data.get("pending") is True):
            return LibreChatSession(stream_id="", conversation_id=data.get("conversationId") or conversation_id,
                                    input_pending=True, input_claim=data.get("inputClaim"))
        if (
            isinstance(data, dict)
            and data.get("code") == "source_order_superseded"
            and data.get("superseded") is True
        ):
            return LibreChatSession(
                stream_id="",
                conversation_id=conversation_id,
                superseded=True,
            )

        if isinstance(data, dict) and data.get("duplicate") is True and not resume_retained:
            self._trace(
                "LibreChatBridge duplicate ingress acknowledged: conversation_id=%s",
                data.get("conversationId") or conversation_id,
            )
            return None

        stream_id = data.get("streamId")
        conversation_id = data.get("conversationId")
        voice_route = _normalize_voice_route(data.get("voiceRoute"))
        logical_turn_id = str(
            data.get("logical_turn_id") or data.get("logicalTurnId") or ""
        ).strip()
        raw_revision = data.get("revision")
        try:
            revision = int(raw_revision) if raw_revision is not None else None
        except (TypeError, ValueError):
            revision = None
        required_key = None
        for candidate_key in (
            "deliveryDispositionRequired",
            "delivery_disposition_required",
        ):
            if candidate_key in data:
                required_key = candidate_key
                break
        if required_key is None:
            delivery_disposition_required = False
        else:
            raw_required = data.get(required_key)
            delivery_disposition_required = (
                raw_required if type(raw_required) is bool else True
            )
        if not isinstance(stream_id, str) or not stream_id:
            raise RuntimeError("LibreChat response missing streamId")
        if not isinstance(conversation_id, str) or not conversation_id:
            conversation_id = ""

        return LibreChatSession(
            stream_id=stream_id,
            conversation_id=conversation_id,
            voice_route=voice_route,
            logical_turn_id=logical_turn_id,
            revision=revision,
            delivery_disposition_required=delivery_disposition_required,
            input_claim=data.get("inputClaim"),
            input_presentation=data.get("inputPresentation"),
        )

    async def ack_delivery(
        self,
        logical_turn_id: str,
        revision: int,
        state: str,
        presentation_ref: str = "",
        presentation_refs: Optional[list[str]] = None,
        *,
        effect_ref: str = "",
    ) -> bool:
        """Best-effort acknowledgement to an optional generic core lifecycle endpoint."""

        return (
            await self.ack_delivery_status(
                logical_turn_id,
                revision,
                state,
                presentation_ref,
                presentation_refs,
                effect_ref=effect_ref,
            )
            == "recorded"
        )

    async def observe_source_order(
        self,
        *,
        telegram_user_id: Any,
        telegram_chat_id: Any,
        telegram_message_thread_id: Any,
        source_sequence: Any,
        input: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Advance Core's authenticated Telegram source watermark before other awaits."""

        try:
            normalized_sequence = int(source_sequence)
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid Telegram source sequence") from exc
        if normalized_sequence <= 0 or not self.base_url or not self.secret:
            raise RuntimeError("Telegram source-order authority is unavailable")
        payload = {
            "telegramUserId": str(telegram_user_id or ""),
            "telegramChatId": str(telegram_chat_id or ""),
            "telegramMessageThreadId": str(telegram_message_thread_id or ""),
            "sourceSequence": normalized_sequence,
        }
        if input is not None:
            payload["input"] = input
        headers = {"X-VIVENTIUM-TELEGRAM-SECRET": self.secret}
        url = f"{self.base_url}/api/viventium/telegram/source-order"
        timeout = httpx.Timeout(10.0, connect=5.0, read=10.0, write=5.0, pool=5.0)
        async with httpx.AsyncClient(
            timeout=timeout,
            **_async_client_options_for_url(url),
        ) as client:
            response = await client.post(url, json=payload, headers=headers)
        if not 200 <= int(response.status_code) < 300:
            try:
                body = response.json()
            except Exception:
                body = {}
            if isinstance(body, dict) and body.get("linkRequired") and body.get("linkUrl"):
                raise TelegramLinkRequired(
                    body.get("linkUrl", ""),
                    body.get("message") or "Link your Viventium account to use Telegram.",
                )
            request = getattr(response, "request", httpx.Request("POST", url))
            raise httpx.HTTPStatusError(
                f"Telegram source-order observation failed ({response.status_code})",
                request=request,
                response=response,
            )
        body = response.json()
        if not isinstance(body, dict) or body.get("observed") is not True:
            raise RuntimeError("Telegram source-order authority returned an invalid response")
        durability = body.get("durability")
        replica_safe = body.get("replicaSafe")
        if durability not in {"process", "durable"} or not isinstance(replica_safe, bool):
            raise RuntimeError("Telegram source-order authority omitted its durability capability")
        latest = int(body.get("latestSourceSequence"))
        source_order_scope = str(body.get("sourceOrderScope") or "")
        source_event_id = str(body.get("sourceEventId") or "")
        if not re.fullmatch(r"[a-f0-9]{64}", source_order_scope) or not re.fullmatch(
            r"[a-f0-9]{64}", source_event_id
        ):
            raise RuntimeError("Telegram source-order authority omitted its trusted scope")
        return {
            "latest_source_sequence": latest,
            "observed_at": int(body.get("observedAt") or 0),
            "stale": bool(body.get("stale")) or normalized_sequence < latest,
            "durability": durability,
            "replica_safe": replica_safe,
            "source_order_scope": source_order_scope,
            "source_event_id": source_event_id,
            "input": body.get("input"),
        }

    async def _input_request(self, operation, payload):
        url = f"{self.base_url}/api/viventium/telegram/inputs/{operation}"
        timeout_s = 120.0 if operation == "continue" else 10.0
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_s, connect=5.0),
                                     **_async_client_options_for_url(url)) as client:
            response = await client.post(url, json=payload,
                                        headers={"X-VIVENTIUM-TELEGRAM-SECRET": self.secret})
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict):
            raise RuntimeError("Invalid Telegram input receipt")
        return body

    @staticmethod
    def _input_identity(claim):
        return {key: claim[key] for key in (
            "telegramUserId", "telegramChatId", "telegramMessageThreadId",
            "sourceSequence", "conversationId", "conversationGeneration",
        ) if key in claim} | {"inputClaim": {
            "sourceEventId": claim["sourceEventId"], "claimToken": claim["claimToken"],
        }}

    async def claim_inputs(self, *, limit=1):
        result = await self._input_request("claim", {"limit": limit})
        inputs = result.get("inputs")
        if not isinstance(inputs, list):
            raise RuntimeError("Telegram input recovery omitted its claims")
        return inputs

    async def continue_input(self, claim):
        return await self._input_request("continue", self._input_identity(claim))

    async def input_status(self, claim, state, *, failure_code=""):
        payload = self._input_identity(claim) | {"state": state}
        if failure_code:
            payload["failureCode"] = failure_code
        return await self._input_request("status", payload)

    async def source_order_is_current(self, **kwargs) -> bool:
        observation = await self.observe_source_order(**kwargs)
        return not observation["stale"]

    async def ack_delivery_status(
        self,
        logical_turn_id: str,
        revision: int,
        state: str,
        presentation_ref: str = "",
        presentation_refs: Optional[list[str]] = None,
        *,
        effect_ref: str = "",
        cortex_presentation: Optional[dict[str, Any]] = None,
    ) -> str:
        """Return enough lifecycle truth to retract a final that became stale in transit."""

        endpoint = (os.getenv("VIVENTIUM_DELIVERY_ACK_ENDPOINT") or "").strip()
        adapter_secret = (
            os.getenv("VIVENTIUM_TELEGRAM_INTERACTION_ADAPTER_SECRET") or ""
        ).strip()
        if not endpoint or not adapter_secret or not logical_turn_id:
            return "unavailable"
        try:
            normalized_revision = int(revision)
        except (TypeError, ValueError):
            return "unavailable"
        url = (
            endpoint
            if endpoint.startswith(("http://", "https://"))
            else f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        )
        payload = {
            "logical_turn_id": str(logical_turn_id),
            "revision": normalized_revision,
            "state": str(state),
        }
        if presentation_ref:
            payload["presentation_ref"] = str(presentation_ref)
        if presentation_refs:
            payload["presentation_refs"] = [str(value) for value in presentation_refs if value]
        effect_id = str(effect_ref or "").strip()[:160]
        if state == "committed" and effect_id:
            payload["effect_ref"] = effect_id
        if cortex_presentation:
            payload["cortex_presentation"] = cortex_presentation
        headers = {"x-viventium-adapter-secret": adapter_secret}
        timeout = httpx.Timeout(10.0, connect=5.0, read=10.0, write=10.0, pool=5.0)
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                async with httpx.AsyncClient(
                    timeout=timeout,
                    **_async_client_options_for_url(url),
                ) as client:
                    response = await client.post(url, json=payload, headers=headers)
            except Exception as exc:
                if attempt + 1 >= max_attempts:
                    logger.debug(
                        "Delivery acknowledgement unavailable after retries: %s",
                        type(exc).__name__,
                    )
                    return "unavailable"
                await asyncio.sleep(0.2 * (attempt + 1))
                continue
            status_code = int(response.status_code)
            if 200 <= status_code < 300:
                try:
                    body = response.json()
                except Exception:
                    body = {}
                return "recorded" if body.get("acknowledged") is True else "unavailable"
            try:
                body = response.json()
            except Exception:
                body = {}
            error = body.get("error") if isinstance(body, dict) else None
            if error in {"stale_revision", "stale_source_order", "conflict", "not_found"}:
                return str(error)
            retryable = status_code in {408, 425, 429} or status_code >= 500
            if not retryable or attempt + 1 >= max_attempts:
                return "unavailable"
            await asyncio.sleep(0.2 * (attempt + 1))
        return "unavailable"

    async def _stream_response(
        self,
        stream_id: str,
        chat_id: str,
        *,
        trace_id: Optional[str] = None,
    ) -> AsyncIterator[Any]:
        headers = {"X-VIVENTIUM-TELEGRAM-SECRET": self.secret}
        url = f"{self.base_url}/api/viventium/telegram/stream/{stream_id}"
        if trace_id:
            url = f"{url}?traceId={urllib.parse.quote(str(trace_id))}"

        self._trace("LibreChatBridge stream open: chat_id=%s stream_id=%s", chat_id, stream_id)
        # === VIVENTIUM START ===
        # Feature: Timing for stream open/first event.
        stream_start_ts = time.monotonic()
        if trace_id:
            self._timing_log(trace_id, "lc_stream_open", stream_start_ts)
        first_event_logged = False
        # === VIVENTIUM END ===
        # Ensure completion marker exists so follow-ups can wait on main response.
        self._get_stream_final_event(stream_id)
        emitted_text = False
        emitted_attachments = False
        emitted_logical_turn = False
        stream_text_parts: list[str] = []
        for attempt in range(self.max_retries + 1):
            # === VIVENTIUM START ===
            # Feature: Include Telegram identity for auth on stream resumes.
            # === VIVENTIUM END ===
            params = self._get_identity_params(stream_id)
            if attempt > 0:
                params["resume"] = "true"
            params = params or None
            if attempt > 0:
                await asyncio.sleep(self.retry_delay_s)

            try:
                read_timeout_s = _parse_positive_float(
                    (os.getenv("VIVENTIUM_TELEGRAM_SSE_READ_TIMEOUT_S") or "").strip(),
                    720.0,
                )
                timeout = _build_stream_timeout(read_timeout_s)
                async with httpx.AsyncClient(
                    timeout=timeout,
                    **_async_client_options_for_url(url),
                ) as client:
                    async with client.stream("GET", url, headers=headers, params=params) as resp:
                        resp.raise_for_status()

                        async for payload in iter_sse_json_events(chunk_iter=resp.aiter_bytes()):
                            if not emitted_logical_turn:
                                logical_turn_id = str(
                                    payload.get("logical_turn_id")
                                    or payload.get("logicalTurnId")
                                    or ""
                                ).strip()
                                if logical_turn_id:
                                    raw_revision = payload.get("revision")
                                    try:
                                        revision = int(raw_revision) if raw_revision is not None else None
                                    except (TypeError, ValueError):
                                        revision = None
                                    emitted_logical_turn = True
                                    yield {
                                        "type": "logical_turn",
                                        "logical_turn_id": logical_turn_id,
                                        "revision": revision,
                                    }
                            if payload.get("sync"):
                                continue

                            if payload.get("_sse_event") == "error":
                                err = payload.get("error")
                                self._trace(
                                    "LibreChatBridge stream error event: chat_id=%s stream_id=%s error=%s",
                                    chat_id,
                                    stream_id,
                                    err,
                                )
                                self._mark_stream_final(stream_id)
                                yield _bridge_error_event(
                                    _stream_error_message(str(err) if err else None),
                                    speak=False,
                                )
                                return

                            # === VIVENTIUM START ===
                            # Feature: Track cortex activity to keep DB follow-up polling alive.
                            if payload.get("event") in ("on_cortex_update", "on_cortex_followup"):
                                self._mark_cortex_seen(stream_id)
                            # === VIVENTIUM END ===

                            if payload_has_glasshive_tool_call(payload):
                                self._mark_glasshive_seen(stream_id)

                            if payload.get("final") and payload.get("superseded") is True:
                                self._mark_stream_final(stream_id)
                                yield {
                                    "type": "superseded",
                                    "logical_turn_id": str(
                                        payload.get("logical_turn_id")
                                        or payload.get("logicalTurnId")
                                        or ""
                                    ).strip(),
                                    "revision": payload.get("revision"),
                                }
                                return

                            # === VIVENTIUM START ===
                            # Feature: Surface streamed attachments to Telegram (images/files).
                            attachments = extract_attachments(payload)
                            if attachments and (payload.get("event") == "attachment" or payload.get("_sse_event") == "attachment"):
                                for attachment in attachments:
                                    emitted_attachments = True
                                    yield {"type": "attachment", "attachment": attachment}
                                continue
                            # === VIVENTIUM END ===

                            # === VIVENTIUM START ===
                            # Cortex insights are handled by the dedicated insight listener.
                            # === VIVENTIUM END ===

                            if payload.get("final"):
                                had_pre_final_text = emitted_text
                                self._trace(
                                    "LibreChatBridge stream final: chat_id=%s stream_id=%s emitted=%s",
                                    chat_id,
                                    stream_id,
                                    emitted_text or emitted_attachments,
                                )
                                if trace_id:
                                    self._timing_log(trace_id, "lc_stream_final", stream_start_ts)
                                self._mark_stream_final(stream_id)
                                response_message_id = extract_response_message_id(payload)
                                if response_message_id:
                                    self._response_message_ids[stream_id] = response_message_id

                                durable_receipt = payload.get("durableEffectReceipt")
                                effect_ref = (
                                    str(durable_receipt.get("effect_ref") or "").strip()[:160]
                                    if isinstance(durable_receipt, dict)
                                    else ""
                                )
                                if effect_ref:
                                    yield {"type": "durable_effect", "effect_ref": effect_ref}

                                final_error = extract_final_error(payload)
                                final_error_class = extract_final_error_class(payload)
                                final_text = extract_final_response_text(payload)
                                final_attachments = extract_attachments(payload)
                                has_final_attachments = len(final_attachments) > 0
                                deferred_internal_final = _is_deferred_internal_final(payload)
                                response_payload = payload.get("responseMessage")
                                response_content = (
                                    response_payload.get("content")
                                    if isinstance(response_payload, dict)
                                    else None
                                )
                                final_cortex_parts = extract_cortex_parts(response_content)

                                # === VIVENTIUM START ===
                                # Feature: Recover structured pre-follow-up completion failures.
                                # Purpose: A typed recoverable final with durable response identity may be
                                # replaced by the existing Main/cortex follow-up. Keep the failure pending
                                # instead of committing a false Telegram connection bubble.
                                if final_error:
                                    public_error = _stream_error_message(
                                        final_error,
                                        error_class=final_error_class or None,
                                    )
                                    can_recover_in_followup = bool(
                                        response_message_id
                                        and final_error_class in _FOLLOWUP_RECOVERABLE_ERROR_CLASSES
                                        and (final_cortex_parts or deferred_internal_final)
                                    )
                                    if can_recover_in_followup:
                                        self._mark_cortex_seen(stream_id)
                                        self._pending_stream_errors[stream_id] = {
                                            "error_class": final_error_class,
                                            "message": public_error,
                                        }
                                        if self._schedule_followup_poll(stream_id, chat_id):
                                            yield _bridge_error_event(
                                                "",
                                                speak=False,
                                                error_class=final_error_class,
                                                recoverable=True,
                                            )
                                            return
                                        self._pending_stream_errors.pop(stream_id, None)

                                    logger.warning(
                                        "LibreChatBridge final error: chat_id=%s stream_id=%s class=%s",
                                        chat_id,
                                        stream_id,
                                        final_error_class or "unstructured",
                                    )
                                    yield _bridge_error_event(
                                        public_error,
                                        speak=False,
                                        error_class=final_error_class or None,
                                    )
                                    return
                                # === VIVENTIUM END ===

                                # A saved-memory write scheduled for this turn finishes after the
                                # stream closed; the typed anchor arms the same bounded poll so its
                                # durable receipt can surface (never Main's prose).
                                memory_writer_scheduled = payload.get("memoryWriterScheduled") is True
                                if memory_writer_scheduled:
                                    self._memory_receipt_pending.add(stream_id)
                                    self._memory_poll_cursors.add(stream_id)
                                    self._save_memory_poll(stream_id, chat_id)
                                if response_message_id and (
                                    self._has_cortex_seen(stream_id)
                                    or self._has_glasshive_seen(stream_id)
                                    or deferred_internal_final
                                    or memory_writer_scheduled
                                ):
                                    self._schedule_followup_poll(stream_id, chat_id)
                                if deferred_internal_final:
                                    self._mark_cortex_seen(stream_id)

                                if final_text and not emitted_text:
                                    stream_text_parts.append(final_text)
                                    emitted_text = True
                                    self._remember_stream_text(
                                        stream_id,
                                        "".join(stream_text_parts),
                                        brief_main_reply=(
                                            not had_pre_final_text
                                            and bool(_normalize_followup_compare_text(final_text))
                                            and len(_normalize_followup_compare_text(final_text)) <= 80
                                            and not emitted_attachments
                                            and not has_final_attachments
                                        ),
                                    )
                                    yield final_text
                                elif stream_text_parts:
                                    self._remember_stream_text(
                                        stream_id,
                                        "".join(stream_text_parts),
                                        brief_main_reply=False,
                                    )
                                if (
                                    not emitted_text
                                    and not final_text
                                    and not emitted_attachments
                                    and not has_final_attachments
                                ):
                                    diagnosis = _diagnose_empty_response(payload)
                                    if deferred_internal_final or self._has_glasshive_seen(stream_id):
                                        self._trace(
                                            "LibreChatBridge pending follow-up final: chat_id=%s stream_id=%s diagnosis=%s keys=%s",
                                            chat_id,
                                            stream_id,
                                            diagnosis,
                                            sorted(payload.keys()),
                                        )
                                    else:
                                        # === VIVENTIUM START ===
                                        # Feature: Enhanced diagnostics for true empty responses.
                                        # Added: 2026-02-01
                                        logger.warning(
                                            "LibreChatBridge final empty: chat_id=%s stream_id=%s diagnosis=%s keys=%s",
                                            chat_id,
                                            stream_id,
                                            diagnosis,
                                            sorted(payload.keys()),
                                        )
                                        self._trace(
                                            "LibreChatBridge final empty: chat_id=%s stream_id=%s keys=%s diagnosis=%s",
                                            chat_id,
                                            stream_id,
                                            sorted(payload.keys()),
                                            diagnosis,
                                        )
                                        yield _empty_response_message(diagnosis)
                                        # === VIVENTIUM END ===
                                disposition_event = extract_delivery_disposition(
                                    payload,
                                    required=self._delivery_disposition_required_by_stream.get(
                                        stream_id,
                                        False,
                                    ),
                                )
                                if (
                                    disposition_event["required"]
                                    or disposition_event["present"]
                                ):
                                    yield disposition_event
                                # === VIVENTIUM START ===
                                # Feature: Emit any final attachments after the main text.
                                final_memory_notice = format_memory_receipt_text(payload.get("memoryReceipt"))
                                if final_memory_notice and stream_id not in self._memory_receipt_sent:
                                    yield "\n\n" + final_memory_notice
                                    self._memory_receipt_sent.add(stream_id)
                                for attachment in final_attachments:
                                    emitted_attachments = True
                                    yield {"type": "attachment", "attachment": attachment}
                                # === VIVENTIUM END ===
                                return

                            # Authored snapshots are replaceable presentation, never final text
                            # or delivery ACK evidence. The authenticated Core stream owns identity.
                            if payload.get("preview") is True:
                                if (payload.get("type") == "text"
                                        and isinstance(payload.get("text"), str)
                                        and payload.get("messageId")):
                                    yield {"type": "assistant_preview", "text": sanitize_telegram_text(
                                        payload["text"], preserve_delivery_controls=False)}
                                continue

                            deltas = extract_text_deltas(payload)
                            for delta in deltas:
                                if delta:
                                    if trace_id and not first_event_logged:
                                        self._timing_log(trace_id, "lc_stream_first_event", stream_start_ts)
                                        first_event_logged = True
                                    stream_text_parts.append(delta)
                                    emitted_text = True
                                    self._remember_stream_text(
                                        stream_id,
                                        "".join(stream_text_parts),
                                        brief_main_reply=False,
                                    )
                                    yield delta

                return
            except Exception as exc:
                logger.warning("LibreChatBridge stream error (attempt %s/%s): %s", attempt + 1, self.max_retries + 1, exc)
                if attempt >= self.max_retries:
                    yield _bridge_error_event(_stream_error_message(str(exc)), speak=False)
                    self._mark_stream_final(stream_id)
                    return

    # === VIVENTIUM START ===
    # Feature: DB-backed follow-up polling to mirror LibreChat UI.
    def _schedule_followup_poll(self, stream_id: str, chat_id: str) -> bool:
        if not self.on_message_callback:
            return False
        if self.followup_timeout_s <= 0 and not self._has_glasshive_seen(stream_id) and stream_id not in self._memory_receipt_pending:
            return False
        if self._has_followup_sent(stream_id) and stream_id not in self._memory_receipt_pending:
            return False
        existing = self._followup_task_by_stream.get(stream_id)
        if existing and not existing.done():
            return True
        task = asyncio.create_task(self._poll_for_followup(stream_id=stream_id, chat_id=chat_id))
        self._followup_task_by_stream[stream_id] = task
        self._track_task(task)
        return True

    async def _send_pending_stream_error_once(self, stream_id: str, chat_id: str) -> bool:
        pending = self._pending_stream_errors.get(stream_id)
        if not isinstance(pending, dict):
            return False
        message = str(pending.get("message") or "").strip()
        if not message:
            return False
        sent = await self._send_followup_text_once(
            chat_id,
            message,
            stream_id=stream_id,
            enforce_order_fence=True,
        )
        if sent:
            self._pending_stream_errors.pop(stream_id, None)
        return sent

    async def _fetch_followup_state(
        self,
        *,
        message_id: str,
        conversation_id: Optional[str],
        stream_id: str,
    ) -> Optional[dict[str, Any]]:
        if not message_id:
            return None
        headers = {"X-VIVENTIUM-TELEGRAM-SECRET": self.secret}
        url = f"{self.base_url}/api/viventium/telegram/cortex/{message_id}"
        # === VIVENTIUM START ===
        # Feature: Include Telegram identity for auth on follow-up polling.
        # === VIVENTIUM END ===
        params: dict[str, str] = self._get_identity_params(stream_id)
        if conversation_id:
            params["conversationId"] = conversation_id
        timeout = httpx.Timeout(connect=10.0, read=10.0, write=10.0, pool=10.0)
        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                **_async_client_options_for_url(url),
            ) as client:
                resp = await client.get(url, headers=headers, params=params)
                if resp.status_code == 200:
                    payload = resp.json()
                    if isinstance(payload, dict):
                        return payload
                    return None
                if resp.status_code in (401, 403):
                    logger.warning("LibreChatBridge follow-up poll unauthorized: %s", resp.status_code)
                    return None
                if resp.status_code != 404:
                    logger.warning(
                        "LibreChatBridge follow-up poll failed: %s %s",
                        resp.status_code,
                        resp.text,
                    )
        except Exception as exc:
            logger.warning("LibreChatBridge follow-up poll error: %s", exc)
        return None

    async def _fetch_glasshive_state(
        self,
        *,
        message_id: str,
        conversation_id: Optional[str],
        stream_id: str,
    ) -> Optional[dict[str, Any]]:
        if not message_id or self.glasshive_timeout_s <= 0:
            return None
        headers = {"X-VIVENTIUM-TELEGRAM-SECRET": self.secret}
        url = f"{self.base_url}/api/viventium/telegram/glasshive/{message_id}"
        params: dict[str, str] = self._get_identity_params(stream_id)
        if conversation_id:
            params["conversationId"] = conversation_id
        timeout = httpx.Timeout(connect=10.0, read=10.0, write=10.0, pool=10.0)
        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                **_async_client_options_for_url(url),
            ) as client:
                resp = await client.get(url, headers=headers, params=params)
                if resp.status_code == 200:
                    payload = resp.json()
                    if isinstance(payload, dict):
                        return payload
                    return None
                if resp.status_code in (401, 403):
                    logger.warning("LibreChatBridge GlassHive poll unauthorized: %s", resp.status_code)
                    return None
                if resp.status_code != 404:
                    logger.warning(
                        "LibreChatBridge GlassHive poll failed: %s %s",
                        resp.status_code,
                        resp.text,
                    )
        except Exception as exc:
            logger.warning("LibreChatBridge GlassHive poll error: %s", exc)
        return None

    def _memory_poll_scope(self) -> str:
        # Bind private cursors to the exact Core/bot connection without persisting its secret.
        return hashlib.sha256((self.base_url + "\0" + self.secret).encode()).hexdigest()

    def _save_memory_poll(self, stream_id: str, chat_id: Optional[str] = None) -> None:
        if chat_id:
            self._memory_poll_chat[stream_id] = chat_id
        identity = self._stream_identity.get(stream_id, {})
        if not identity.get("telegram_user_id") or not identity.get("telegram_chat_id"):
            return
        self._cortex_ack_store.save_memory_poll(self._memory_poll_scope(), stream_id, {
            "chat_id": self._memory_poll_chat.get(stream_id, identity["telegram_chat_id"]),
            "message_id": self._response_message_ids.get(stream_id, ""),
            "conversation_id": self._conversation_by_stream.get(stream_id, ""),
            "identity": {key: identity.get(key) for key in (
                "telegram_chat_id", "telegram_user_id", "telegram_message_id",
                "telegram_message_thread_id", "logical_turn_id", "logical_turn_revision",
                "presentation_source_sequence")},
            "followup_sent": self._has_followup_sent(stream_id),
            "memory_sent": stream_id in self._memory_receipt_sent,
            "delivery_state": self._memory_delivery_state.get(stream_id, "pending"),
            "stream_text_hash": self._stream_text_hash_by_stream.get(stream_id, ""),
            "brief_main_reply": self._brief_main_reply_by_stream.get(stream_id, False),
            "glasshive_seen": self._has_glasshive_seen(stream_id),
        })

    def _resume_memory_polls(self) -> None:
        if not self.on_message_callback:
            return
        for stream_id, cursor in self._cortex_ack_store.pending_memory_polls(self._memory_poll_scope()):
            task = self._followup_task_by_stream.get(stream_id)
            if task and not task.done():
                continue
            if cursor.get("delivery_state") in {"sending", "delivery_unknown"}:
                # A process can die after Telegram accepted the send. There is no Telegram
                # idempotency token: retain uncertainty instead of blindly sending it twice.
                if cursor.get("delivery_state") == "sending":
                    cursor["delivery_state"] = "delivery_unknown"
                    self._cortex_ack_store.save_memory_poll(self._memory_poll_scope(), stream_id, cursor)
                    logger.warning("Saved-memory receipt delivery acknowledgement is unknown: stream_id=%s", stream_id)
                continue
            identity = cursor.get("identity")
            if not isinstance(identity, dict) or not cursor.get("message_id"):
                continue
            self._stream_identity[stream_id] = identity
            self._response_message_ids[stream_id] = cursor["message_id"]
            self._conversation_by_stream[stream_id] = cursor.get("conversation_id")
            self._memory_poll_cursors.add(stream_id)
            self._memory_poll_chat[stream_id] = cursor["chat_id"]
            self._memory_delivery_state[stream_id] = cursor.get("delivery_state", "pending")
            if cursor.get("memory_sent"):
                self._memory_receipt_sent.add(stream_id)
            else:
                self._memory_receipt_pending.add(stream_id)
            if cursor.get("followup_sent"):
                self._followup_sent.add(stream_id)
            if cursor.get("stream_text_hash"):
                self._stream_text_hash_by_stream[stream_id] = cursor["stream_text_hash"]
            if cursor.get("brief_main_reply"):
                self._brief_main_reply_by_stream[stream_id] = True
            if cursor.get("glasshive_seen"):
                self._mark_glasshive_seen(stream_id)
            self._schedule_followup_poll(stream_id=stream_id, chat_id=cursor["chat_id"])

    async def _poll_memory_receipt(self, stream_id: str, chat_id: str, state: Any) -> None:
        receipt = state.get("memoryReceipt") if isinstance(state, dict) else None
        if not isinstance(receipt, dict) or stream_id in self._memory_receipt_sent:
            return
        status = receipt.get("status")
        if status == "pending":
            self._memory_receipt_pending.add(stream_id)
            self._memory_poll_cursors.add(stream_id)
            self._save_memory_poll(stream_id, chat_id)
            return
        if status == "unchanged":
            self._memory_receipt_sent.add(stream_id)
            self._memory_receipt_pending.discard(stream_id)
            self._memory_delivery_state[stream_id] = "sent"
            self._save_memory_poll(stream_id, chat_id)
            return
        text = format_memory_receipt_text(receipt)
        if not text or self._memory_delivery_state.get(stream_id) == "delivery_unknown":
            return
        self._memory_receipt_pending.add(stream_id)
        self._memory_poll_cursors.add(stream_id)
        self._memory_delivery_state[stream_id] = "sending"
        self._save_memory_poll(stream_id, chat_id)
        try:
            result = await self._send_followup_text(chat_id, text, stream_id=stream_id, return_receipt=True)
            sent = (isinstance(result, dict) and result.get("sent") is True
                    and bool(result.get("message_ids")))
            refused = result is False or (isinstance(result, dict) and result.get("sent") is False and not result.get("message_ids"))
        except Exception:
            sent, refused = False, False
        if sent:
            self._memory_receipt_sent.add(stream_id)
            self._memory_receipt_pending.discard(stream_id)
            self._memory_delivery_state[stream_id] = "sent"
        elif refused:
            self._memory_delivery_state[stream_id] = "pending"
        else:
            self._memory_delivery_state[stream_id] = "delivery_unknown"
            self._memory_receipt_pending.discard(stream_id)
            logger.warning("Saved-memory receipt delivery acknowledgement is unknown: stream_id=%s", stream_id)
        self._save_memory_poll(stream_id, chat_id)

    async def _poll_for_followup(self, *, stream_id: str, chat_id: str) -> None:
        message_id = self._response_message_ids.get(stream_id, "")
        conversation_id = self._conversation_by_stream.get(stream_id)
        poll_glasshive = self._has_glasshive_seen(stream_id)
        timeout_s = (
            max(self.followup_timeout_s, self.glasshive_timeout_s, 1.0)
            if poll_glasshive
            else max(self.followup_timeout_s, 1.0)
        )
        interval_s = max(self.followup_interval_s, 0.25)
        grace_s = max(self.followup_grace_s, 0.0)
        started_at = time.monotonic()
        grace_start: Optional[float] = None
        saw_active = False
        last_parts: list[dict[str, Any]] = []
        pending_glasshive_callback: Optional[dict[str, Any]] = None
        pending_glasshive_text = ""
        pending_glasshive_duplicate = False

        try:
            if not self.on_message_callback:
                return
            if not message_id:
                return
            while time.monotonic() - started_at < timeout_s:
                state = await self._fetch_followup_state(
                    message_id=message_id, conversation_id=conversation_id, stream_id=stream_id,
                )
                await self._poll_memory_receipt(stream_id, chat_id, state)
                if self._has_followup_sent(stream_id):
                    if stream_id in self._memory_receipt_pending:
                        await asyncio.sleep(interval_s)
                        continue
                    return

                if poll_glasshive:
                    glasshive_state = await self._fetch_glasshive_state(
                        message_id=message_id,
                        conversation_id=conversation_id,
                        stream_id=stream_id,
                    )
                    if isinstance(glasshive_state, dict):
                        latest = glasshive_state.get("latest")
                        if isinstance(latest, dict):
                            text = latest.get("text")
                            if isinstance(text, str) and text.strip() and glasshive_callback_is_terminal(latest):
                                callback_id = str(
                                    latest.get("callbackId") or latest.get("callback_id") or ""
                                ).strip()
                                if self._matches_streamed_text(stream_id, text):
                                    delivery = await self._claim_glasshive_delivery_for_callback(latest)
                                    if delivery:
                                        await self._mark_glasshive_delivery_status(
                                            delivery,
                                            "suppressed",
                                            reason="already_streamed",
                                        )
                                        self._mark_followup_sent(stream_id)
                                        self._cancel_insight_task(stream_id)
                                        if stream_id in self._memory_receipt_pending:
                                            await asyncio.sleep(interval_s)
                                            continue
                                        return
                                    if callback_id:
                                        pending_glasshive_callback = latest
                                        pending_glasshive_text = text
                                        pending_glasshive_duplicate = True
                                        await asyncio.sleep(self.followup_interval_s)
                                        continue
                                    self._trace(
                                        "LibreChatBridge GlassHive callback suppressed as already streamed without durable callback id: chat_id=%s stream_id=%s",
                                        chat_id,
                                        stream_id,
                                    )
                                    self._mark_followup_sent(stream_id)
                                    self._cancel_insight_task(stream_id)
                                    if stream_id in self._memory_receipt_pending:
                                        await asyncio.sleep(interval_s)
                                        continue
                                    return
                                delivery = await self._claim_glasshive_delivery_for_callback(latest)
                                if delivery:
                                    sent = await self._deliver_glasshive_delivery_bounded(delivery)
                                else:
                                    if callback_id:
                                        pending_glasshive_callback = latest
                                        pending_glasshive_text = text
                                        pending_glasshive_duplicate = False
                                        # The callback message can become visible milliseconds
                                        # before the durable surface-delivery row is committed.
                                        # For callback-id-bearing worker results, wait for the
                                        # ledger row/dispatcher instead of legacy-sending and
                                        # risking a duplicate Telegram message.
                                        await asyncio.sleep(self.followup_interval_s)
                                        continue
                                    if is_no_response_only(text):
                                        self._mark_followup_sent(stream_id)
                                        self._cancel_insight_task(stream_id)
                                        if stream_id in self._memory_receipt_pending:
                                            await asyncio.sleep(interval_s)
                                            continue
                                        return
                                    sent = await self._send_followup_text_once(
                                        chat_id,
                                        text,
                                        stream_id=stream_id,
                                        enforce_order_fence=True,
                                    )
                                if sent:
                                    self._mark_followup_sent(stream_id)
                                    self._cancel_insight_task(stream_id)
                                if stream_id in self._memory_receipt_pending:
                                    await asyncio.sleep(interval_s)
                                    continue
                                return

                parts: list[dict[str, Any]] = []
                if isinstance(state, dict):
                    parts = extract_cortex_parts(state.get("cortexParts"))
                    if parts:
                        self._mark_cortex_seen(stream_id)
                        last_parts = parts
                    follow_up = state.get("followUp")
                    if isinstance(follow_up, dict):
                        text = follow_up.get("text")
                        if isinstance(text, str) and text.strip():
                            text = apply_structured_delivery_controls(
                                text,
                                follow_up.get("deliveryControls"),
                            )
                            # === VIVENTIUM START ===
                            # Feature: Treat {NTA} (or equivalent) as an intentional silent follow-up.
                            if is_no_response_only(text):
                                self._trace(
                                    "LibreChatBridge follow-up suppressed (no-response): chat_id=%s stream_id=%s",
                                    chat_id,
                                    stream_id,
                                )
                                self._mark_followup_sent(stream_id)
                                self._cancel_insight_task(stream_id)
                                if stream_id in self._memory_receipt_pending:
                                    await asyncio.sleep(interval_s)
                                    continue
                                return
                            # === VIVENTIUM END ===
                            sent = await self._send_followup_text_once(
                                chat_id,
                                text,
                                stream_id=stream_id,
                                enforce_order_fence=True,
                            )
                            # Prevent insight fallback after a merged follow-up is finalized.
                            if sent:
                                self._cancel_insight_task(stream_id)
                            if stream_id in self._memory_receipt_pending:
                                await asyncio.sleep(interval_s)
                                continue
                            return

                    canonical_text = state.get("canonicalText")
                    if self._should_send_canonical_text(stream_id, canonical_text):
                        sent = await self._send_followup_text_once(
                            chat_id,
                            _prepare_followup_delivery_text(canonical_text),
                            stream_id=stream_id,
                            enforce_order_fence=True,
                        )
                        if sent:
                            self._cancel_insight_task(stream_id)
                        if stream_id in self._memory_receipt_pending:
                            await asyncio.sleep(interval_s)
                            continue
                        return

                    followup_decision = terminal_cortex_followup_decision(
                        state.get("followUpDecision")
                    )
                    if followup_decision is not None:
                        self._trace(
                            "LibreChatBridge follow-up decision terminal: chat_id=%s stream_id=%s result=%s reason=%s llm_result=%s strategy=%s",
                            chat_id,
                            stream_id,
                            followup_decision.get("result") or "",
                            followup_decision.get("suppressionReason") or "none",
                            followup_decision.get("llmResult") or "",
                            followup_decision.get("selectedStrategy") or "",
                        )
                        self._mark_followup_sent(stream_id)
                        self._cancel_insight_task(stream_id)
                        if stream_id in self._memory_receipt_pending:
                            await asyncio.sleep(interval_s)
                            continue
                        return

                    # A GlassHive worker callback can arrive without any cortex parts. Keep polling
                    # until the configured timeout instead of treating "no cortex" as terminal.

                active = has_active_cortex(last_parts)
                if active:
                    saw_active = True
                    grace_start = None
                else:
                    if parts and not saw_active:
                        saw_active = True
                    if saw_active:
                        if grace_start is None:
                            grace_start = time.monotonic()
                        elif (time.monotonic() - grace_start) >= grace_s:
                            sent_insight = False
                            if self.allow_insight_fallback:
                                insights = extract_completed_cortex_insights(last_parts)
                                if insights:
                                    sent_insight = await self._send_pending_insights_once(
                                        chat_id,
                                        insights,
                                        stream_id=stream_id,
                                    )
                            if not sent_insight:
                                await self._send_pending_stream_error_once(stream_id, chat_id)
                            if stream_id in self._memory_receipt_pending:
                                await asyncio.sleep(interval_s)
                                continue
                            return

                await asyncio.sleep(interval_s)

            if (
                pending_glasshive_callback
                and pending_glasshive_text.strip()
                and not self._has_followup_sent(stream_id)
            ):
                delivery = await self._claim_glasshive_delivery_for_callback(pending_glasshive_callback)
                if pending_glasshive_duplicate:
                    if delivery:
                        await self._mark_glasshive_delivery_status(
                            delivery,
                            "suppressed",
                            reason="already_streamed",
                        )
                    sent = True
                elif delivery:
                    sent = await self._deliver_glasshive_delivery_bounded(delivery)
                elif is_no_response_only(pending_glasshive_text):
                    sent = True
                else:
                    logger.warning(
                        "LibreChatBridge GlassHive callback %s had no claimable durable delivery row before timeout; unfenced legacy send suppressed",
                        pending_glasshive_callback.get("callbackId")
                        or pending_glasshive_callback.get("callback_id")
                        or "unknown",
                    )
                    sent = True
                if sent:
                    self._mark_followup_sent(stream_id)
                    self._cancel_insight_task(stream_id)
                    return

            if self.allow_insight_fallback:
                insights = extract_completed_cortex_insights(last_parts)
                if insights:
                    sent = await self._send_pending_insights_once(
                        chat_id,
                        insights,
                        stream_id=stream_id,
                    )
                    if sent:
                        return
            await self._send_pending_stream_error_once(stream_id, chat_id)
        except asyncio.CancelledError:
            return
        finally:
            self._followup_task_by_stream.pop(stream_id, None)
            insight_task = self._insight_task_by_stream.get(stream_id)
            if stream_id in self._memory_receipt_pending or self._memory_delivery_state.get(stream_id) == "delivery_unknown":
                self._save_memory_poll(stream_id, chat_id)
            elif not insight_task or insight_task.done():
                self._cortex_ack_store.finish_memory_poll(self._memory_poll_scope(), stream_id)
                self._memory_poll_cursors.discard(stream_id)
                self._memory_poll_chat.pop(stream_id, None)
                self._memory_delivery_state.pop(stream_id, None)
                self._stream_text_hash_by_stream.pop(stream_id, None)
                self._pending_followups.pop(stream_id, None)
                self._pending_stream_errors.pop(stream_id, None)
                self._stream_final_events.pop(stream_id, None)
                self._response_message_ids.pop(stream_id, None)
                self._conversation_by_stream.pop(stream_id, None)
                self._followup_sent.discard(stream_id)
                self._memory_receipt_sent.discard(stream_id)
                self._followup_send_lock_by_stream.pop(stream_id, None)
                self._cortex_seen_by_stream.pop(stream_id, None)
                self._glasshive_seen_by_stream.discard(stream_id)
                self._stream_text_by_stream.pop(stream_id, None)
                self._brief_main_reply_by_stream.pop(stream_id, None)
                self._stream_identity.pop(stream_id, None)
                self._clear_active_stream(chat_id, stream_id)
    # === VIVENTIUM END ===

    async def _listen_for_insights(self, *, stream_id: str, chat_id: str) -> None:
        if not self.on_message_callback:
            return
        if self.insight_grace_s <= 0 or self.insight_max_s <= 0:
            return
        if not self._is_stream_active(chat_id, stream_id):
            return

        headers = {"X-VIVENTIUM-TELEGRAM-SECRET": self.secret}
        url = f"{self.base_url}/api/viventium/telegram/stream/{stream_id}"
        grace_s = max(self.insight_grace_s, 1.0)
        max_total_s = max(self.insight_max_s, grace_s)
        linger_ms = int(grace_s * 1000)
        # === VIVENTIUM START ===
        # Feature: Include Telegram identity for auth on insight streaming.
        # === VIVENTIUM END ===
        base_params = self._get_identity_params(stream_id)
        base_params.update({"linger": "true", "lingerMs": str(linger_ms)})
        started_at = time.monotonic()
        final_deadline: Optional[float] = None
        pending_insights: list[dict[str, Any]] = []
        followup_sent = False
        self._retain_insight_seen(stream_id)

        self._trace(
            "LibreChatBridge insight stream open: chat_id=%s stream_id=%s grace_s=%.1f max_total_s=%.1f",
            chat_id,
            stream_id,
            grace_s,
            max_total_s,
        )
        try:
            for attempt in range(self.max_retries + 1):
                try:
                    read_timeout_s = _parse_positive_float(
                        (os.getenv("VIVENTIUM_TELEGRAM_SSE_READ_TIMEOUT_S") or "").strip(),
                        max_total_s + 10.0,
                    )
                    timeout = _build_stream_timeout(read_timeout_s)
                    request_params = dict(base_params)
                    if attempt > 0:
                        request_params["resume"] = "true"
                    async with httpx.AsyncClient(
                        timeout=timeout,
                        **_async_client_options_for_url(url),
                    ) as client:
                        async with client.stream("GET", url, headers=headers, params=request_params) as resp:
                            resp.raise_for_status()

                            async for payload in iter_sse_json_events(chunk_iter=resp.aiter_bytes()):
                                if not self._is_stream_active(chat_id, stream_id):
                                    return
                                now = time.monotonic()
                                if now - started_at >= max_total_s:
                                    if pending_insights and not followup_sent and self.allow_insight_fallback:
                                        sent = await self._send_pending_insights_once(
                                            chat_id,
                                            pending_insights,
                                            stream_id=stream_id,
                                        )
                                        if sent:
                                            self._cancel_followup_task(stream_id)
                                    return
                                if final_deadline is not None and now >= final_deadline:
                                    if pending_insights and not followup_sent and self.allow_insight_fallback:
                                        sent = await self._send_pending_insights_once(
                                            chat_id,
                                            pending_insights,
                                            stream_id=stream_id,
                                        )
                                        if sent:
                                            self._cancel_followup_task(stream_id)
                                    return

                                if payload.get("sync"):
                                    await self._emit_resume_insights(payload, chat_id, stream_id)
                                    continue

                                if payload.get("_sse_event") == "error":
                                    return

                                # === VIVENTIUM START ===
                                # Feature: Track cortex activity to prevent premature polling exit.
                                if payload.get("event") in ("on_cortex_update", "on_cortex_followup"):
                                    self._mark_cortex_seen(stream_id)
                                # === VIVENTIUM END ===

                                # === VIVENTIUM START ===
                                # Prefer a single merged follow-up event over per-cortex updates.
                                followup_delivery = extract_cortex_followup_delivery(payload)
                                followup_text = extract_cortex_followup(payload)
                                if followup_text:
                                    if self._has_followup_sent(stream_id):
                                        return
                                    # === VIVENTIUM START ===
                                    # Feature: Suppress passive "nothing to add" follow-ups.
                                    if is_no_response_only(followup_text):
                                        self._trace(
                                            "LibreChatBridge follow-up suppressed (no-response): chat_id=%s stream_id=%s",
                                            chat_id,
                                            stream_id,
                                        )
                                        self._mark_followup_sent(stream_id)
                                        self._cancel_followup_task(stream_id)
                                        followup_sent = True
                                        return
                                    # === VIVENTIUM END ===
                                    self._trace(
                                        "LibreChatBridge follow-up event: chat_id=%s stream_id=%s length=%s",
                                        chat_id,
                                        stream_id,
                                        len(followup_text),
                                    )
                                    self._pending_followups[stream_id] = followup_text
                                    await self._await_stream_final(stream_id, grace_s)
                                    if not self._is_stream_active(chat_id, stream_id):
                                        return
                                    sent = await self._send_followup_text_once(
                                        chat_id,
                                        followup_text,
                                        stream_id=stream_id,
                                        cortex_delivery=followup_delivery,
                                        enforce_order_fence=True,
                                    )
                                    if sent:
                                        self._cancel_followup_task(stream_id)
                                        followup_sent = True
                                    return
                                # === VIVENTIUM END ===

                                if payload.get("final"):
                                    if final_deadline is None:
                                        final_deadline = now + grace_s
                                    continue

                                if payload.get("event") == "on_cortex_update" and final_deadline is not None:
                                    final_deadline = now + grace_s

                                # === VIVENTIUM START ===
                                insight = extract_cortex_insight(payload)
                                if insight and self._should_emit_insight(stream_id, insight):
                                    pending_insights.append(insight)
                                    self._trace(
                                        "LibreChatBridge insight queued: chat_id=%s stream_id=%s count=%s",
                                        chat_id,
                                        stream_id,
                                        len(pending_insights),
                                    )
                                # === VIVENTIUM END ===

                                if final_deadline is not None and now >= final_deadline and pending_insights:
                                    if self.allow_insight_fallback:
                                        sent = await self._send_pending_insights_once(
                                            chat_id,
                                            pending_insights,
                                            stream_id=stream_id,
                                        )
                                        if sent:
                                            self._cancel_followup_task(stream_id)
                                    return
                    if pending_insights and not followup_sent and self.allow_insight_fallback:
                        sent = await self._send_pending_insights_once(
                            chat_id,
                            pending_insights,
                            stream_id=stream_id,
                        )
                        if sent:
                            self._cancel_followup_task(stream_id)
                    return
                except Exception as exc:
                    response = getattr(exc, "response", None)
                    status_code = getattr(response, "status_code", None)
                    if status_code in (401, 403, 404):
                        self._trace(
                            "LibreChatBridge insight stream closed: chat_id=%s stream_id=%s status=%s",
                            chat_id,
                            stream_id,
                            status_code,
                        )
                        return
                    logger.warning(
                        "LibreChatBridge insight stream error (attempt %s/%s): %s",
                        attempt + 1,
                        self.max_retries + 1,
                        exc,
                    )
                    if attempt >= self.max_retries:
                        return
                    await asyncio.sleep(self.retry_delay_s)
        finally:
            self._insight_task_by_stream.pop(stream_id, None)
            self._pending_followups.pop(stream_id, None)
            followup_task = self._followup_task_by_stream.get(stream_id)
            if (not followup_task or followup_task.done()) and stream_id not in self._memory_poll_cursors:
                self._stream_final_events.pop(stream_id, None)
                self._response_message_ids.pop(stream_id, None)
                self._conversation_by_stream.pop(stream_id, None)
                self._followup_sent.discard(stream_id)
                self._memory_receipt_sent.discard(stream_id)
                self._followup_send_lock_by_stream.pop(stream_id, None)
                self._cortex_seen_by_stream.pop(stream_id, None)
                self._glasshive_seen_by_stream.discard(stream_id)
                self._stream_text_by_stream.pop(stream_id, None)
                self._brief_main_reply_by_stream.pop(stream_id, None)
                self._clear_active_stream(chat_id, stream_id)
            self._release_insight_seen(stream_id)

    def _insight_key(self, insight: dict[str, Any]) -> str:
        cortex_id = insight.get("cortex_id") or insight.get("cortexId") or ""
        text = insight.get("insight") or ""
        if not text:
            return ""
        return f"{cortex_id}:{text.strip()}"

    async def _emit_resume_insights(
        self,
        payload: dict[str, Any],
        chat_id: str,
        stream_id: str,
    ) -> None:
        resume_state = payload.get("resumeState")
        if not isinstance(resume_state, dict):
            return
        aggregated = resume_state.get("aggregatedContent")
        if not isinstance(aggregated, list):
            return
        # === VIVENTIUM START ===
        pending: list[dict[str, Any]] = []
        saw_cortex = False
        for part in aggregated:
            if not isinstance(part, dict):
                continue
            if part.get("type") != "cortex_insight":
                continue
            saw_cortex = True
            insight = part.get("insight")
            if not isinstance(insight, str) or not insight.strip():
                continue
            cortex_id = part.get("cortex_id") or part.get("cortexId") or ""
            cortex_name = part.get("cortex_name") or part.get("cortexName") or "Background Insight"
            data = {
                "cortex_id": cortex_id,
                "cortex_name": cortex_name,
                "status": part.get("status") or "complete",
                "insight": insight,
            }
            if self._should_emit_insight(stream_id, data):
                pending.append(data)
        if saw_cortex:
            self._mark_cortex_seen(stream_id)
        if pending:
            self._trace(
                "LibreChatBridge resume insights: chat_id=%s stream_id=%s count=%s",
                chat_id,
                stream_id,
                len(pending),
            )
            sent = await self._send_pending_insights_once(chat_id, pending, stream_id=stream_id)
            if sent:
                self._cancel_followup_task(stream_id)
        # === VIVENTIUM END ===

    # === VIVENTIUM START ===
    # Feature: Resolve Telegram chat IDs for insight delivery (composite convo IDs safe).
    async def _send_insight(
        self,
        chat_id: str,
        insight: dict[str, Any],
        *,
        stream_id: Optional[str] = None,
    ) -> None:
        text = insight.get("insight") or ""
        if not isinstance(text, str) or not text.strip():
            return

        prefix = (os.getenv("VIVENTIUM_TELEGRAM_INSIGHT_PREFIX") or "").strip()
        if prefix:
            raw_message = f"{prefix} {text.strip()}"
        else:
            # Human-like delivery: never surface internal cortex names/labels to the user.
            raw_message = text.strip()

        # === VIVENTIUM NOTE ===
        # Fix: Always render HTML for text display, even when input was voice.
        # Voice-note input should not degrade follow-up text readability.
        message = render_telegram_markdown(raw_message)
        parse_mode = "HTML"
        # === VIVENTIUM NOTE END ===
        if not message:
            return
        target_chat_id = self._resolve_telegram_chat_id(chat_id=chat_id, stream_id=stream_id)
        if target_chat_id is None:
            return
        await self._deliver_callback(
            target_chat_id,
            message,
            parse_mode=parse_mode,
            preference_convo_id=str(chat_id),
            raw_message=raw_message,
            stream_id=stream_id,
        )
    # === VIVENTIUM END ===

    # === VIVENTIUM START ===
    # Feature: Telegram insight batching and follow-up delivery
    # NOTE: Returns raw markdown; caller handles MarkdownV2 conversion via _send_followup_text.
    def _format_pending_insights(self, insights: list[dict[str, Any]], *, voice_mode: bool) -> str:
        # Parity with server-side follow-up fallback: surface only the insight text itself.
        return format_insights_fallback_text(insights, voice_mode=voice_mode)

    async def _send_pending_insights(
        self,
        chat_id: str,
        insights: list[dict[str, Any]],
        *,
        stream_id: Optional[str] = None,
    ) -> None:
        voice_mode = self._stream_voice_mode(stream_id)
        text = self._format_pending_insights(insights, voice_mode=voice_mode)
        if not text:
            return
        self._trace(
            "LibreChatBridge sending pending insights: chat_id=%s count=%s",
            chat_id,
            len(insights),
        )
        # Human-like delivery: no system-notification preambles.
        message = text
        await self._send_followup_text(chat_id, message, stream_id=stream_id)

    async def _send_followup_text(
        self,
        chat_id: str,
        text: str,
        *,
        stream_id: Optional[str] = None,
        return_receipt: bool = False,
        before_side_effect: Optional[Callable[[], Awaitable[bool]]] = None,
    ) -> Any:
        if not text:
            return False
        # === VIVENTIUM START ===
        # Feature: No-response tag ({NTA}) should never be delivered to Telegram users.
        if is_no_response_only(text):
            return False
        # === VIVENTIUM END ===
        # === VIVENTIUM NOTE ===
        # Fix: Always render HTML for text display, even when input was voice.
        message = render_telegram_markdown(text)
        parse_mode = "HTML"
        # === VIVENTIUM NOTE END ===
        if not message:
            return False
        target_chat_id = self._resolve_telegram_chat_id(chat_id=chat_id, stream_id=stream_id)
        if target_chat_id is None:
            return False
        self._trace(
            "LibreChatBridge sending follow-up: chat_id=%s length=%s",
            chat_id,
            len(message),
        )
        return await self._deliver_callback(
            target_chat_id,
            message,
            parse_mode=parse_mode,
            preference_convo_id=str(chat_id),
            raw_message=text,
            stream_id=stream_id,
            return_receipt=return_receipt,
            before_side_effect=before_side_effect,
        )
    # === VIVENTIUM END ===

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
from contextlib import asynccontextmanager
import json
import logging
import os
import re
import time
import urllib.parse
from dataclasses import dataclass
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, Optional

import httpx
# === VIVENTIUM START ===
# Feature: Markdown → Telegram HTML conversion (replaces fragile MarkdownV2).
try:
    from utils.telegram_html import markdown_to_html, strip_html_tags
except ModuleNotFoundError:
    from TelegramVivBot.utils.telegram_html import markdown_to_html, strip_html_tags
try:
    from utils.telegram_chunks import split_telegram_text
except ModuleNotFoundError:
    from TelegramVivBot.utils.telegram_chunks import split_telegram_text
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


@dataclass(frozen=True)
class LibreChatSession:
    stream_id: str
    conversation_id: str
    voice_route: Optional[dict[str, Any]] = None


# === VIVENTIUM START ===
# Feature: Telegram account linking signal
class TelegramLinkRequired(Exception):
    def __init__(self, link_url: str, message: Optional[str] = None) -> None:
        self.link_url = link_url
        self.message = message or "Link your Viventium account to use Telegram."
        super().__init__(self.message)
# === VIVENTIUM END ===


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
# === VIVENTIUM END ===

# === VIVENTIUM START ===
# Feature: No-response tag ({NTA}) suppression for passive/background follow-ups.
import sys
from pathlib import Path

_SHARED_PATH = Path(__file__).resolve().parents[3] / "shared"  # .../viventium_v0_4/shared
if str(_SHARED_PATH) not in sys.path:
    sys.path.insert(0, str(_SHARED_PATH))

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


def sanitize_telegram_text(text: str) -> str:
    if not text:
        return ""
    cleaned = _CITATION_COMPOSITE_RE.sub(" ", text)
    cleaned = _CITATION_STANDALONE_RE.sub(" ", cleaned)
    cleaned = _CITATION_CLEANUP_RE.sub(" ", cleaned)
    cleaned = _BRACKET_CITATION_RE.sub(" ", cleaned)
    cleaned = _apply_outside_markdown_code(cleaned, _normalize_em_dashes_for_telegram)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned


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
def render_telegram_markdown(text: str) -> str:
    cleaned = sanitize_telegram_text(text)
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
        out.append(sanitize_telegram_text(text))
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
            out.append(sanitize_telegram_text(ptext))
            continue
        if isinstance(ptext, dict):
            val = ptext.get("value")
            if isinstance(val, str) and val:
                out.append(sanitize_telegram_text(val))

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
            parts.append(sanitize_telegram_text(text))
        if not parts:
            parts.extend(_collect_text_parts(response.get("content")))
    if not parts:
        text = payload.get("text")
        if isinstance(text, str) and text.strip():
            parts.append(sanitize_telegram_text(text))
    return "".join(parts).strip()


def _parse_positive_float(value: str, fallback: float) -> float:
    try:
        num = float(value)
        if num > 0 and num != float("inf"):
            return num
    except Exception:
        pass
    return fallback


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


def _stream_error_message(error: Optional[str]) -> str:
    fallback = (os.getenv("VIVENTIUM_TELEGRAM_STREAM_ERROR_MESSAGE") or "").strip()
    if fallback:
        return fallback
    if error:
        lowered = error.lower()
        if "credit balance is too low" in lowered or "plans & billing" in lowered:
            return "Provider billing issue. Please check Plans & Billing."
        if "connected account needs reconnect" in lowered:
            return sanitize_telegram_text(error)
        if "tool" in lowered or "mcp" in lowered or "oauth" in lowered:
            return "Tool connection error. Please retry."
    return "Connection error. Please retry."


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


def _collect_text_parts(content: Any) -> list[str]:
    parts: list[str] = []
    if isinstance(content, str):
        if content:
            parts.append(sanitize_telegram_text(content))
        return parts
    if isinstance(content, dict):
        if content.get("type") == "text":
            text = content.get("text")
            if isinstance(text, str) and text:
                parts.append(sanitize_telegram_text(text))
                return parts
            if isinstance(text, dict):
                val = text.get("value")
                if isinstance(val, str) and val:
                    parts.append(sanitize_telegram_text(val))
                    return parts
        text = content.get("text")
        if isinstance(text, str) and text:
            parts.append(sanitize_telegram_text(text))
        elif isinstance(text, dict):
            val = text.get("value")
            if isinstance(val, str) and val:
                parts.append(sanitize_telegram_text(val))
        else:
            val = content.get("value")
            if isinstance(val, str) and val:
                parts.append(sanitize_telegram_text(val))
        return parts
    if isinstance(content, list):
        for item in content:
            if isinstance(item, str):
                if item:
                    parts.append(sanitize_telegram_text(item))
                continue
            if not isinstance(item, dict):
                continue
            if item.get("type") not in (None, "text"):
                continue
            text = item.get("text")
            if isinstance(text, str) and text:
                parts.append(sanitize_telegram_text(text))
                continue
            if isinstance(text, dict):
                val = text.get("value")
                if isinstance(val, str) and val:
                    parts.append(sanitize_telegram_text(val))
                    continue
            val = item.get("value")
            if isinstance(val, str) and val:
                parts.append(sanitize_telegram_text(val))
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
        get_agent_id: Optional[Callable[[str], str]] = None,
        set_agent_id: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        self.base_url = (os.getenv("VIVENTIUM_LIBRECHAT_ORIGIN", "http://localhost:3180") or "").strip().rstrip("/")
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
        self.insight_grace_s = _parse_positive_float(
            (os.getenv("VIVENTIUM_TELEGRAM_INSIGHT_GRACE_S") or "").strip(),
            180.0,
        )
        self.insight_max_s = _parse_positive_float(
            (os.getenv("VIVENTIUM_TELEGRAM_INSIGHT_MAX_S") or "").strip(),
            self.insight_grace_s + 30.0,
        )
        if self.insight_max_s < self.insight_grace_s:
            self.insight_max_s = self.insight_grace_s
        # === VIVENTIUM START ===
        # Feature: DB-backed follow-up polling (LibreChat parity).
        self.followup_interval_s = _parse_positive_float(
            (os.getenv("VIVENTIUM_TELEGRAM_FOLLOWUP_INTERVAL_S") or "").strip(),
            1.5,
        )
        self.followup_grace_s = _parse_positive_float(
            (os.getenv("VIVENTIUM_TELEGRAM_FOLLOWUP_GRACE_S") or "").strip(),
            8.0,
        )
        self.followup_timeout_s = _parse_positive_float(
            (os.getenv("VIVENTIUM_TELEGRAM_FOLLOWUP_TIMEOUT_S") or "").strip(),
            self.insight_max_s,
        )
        if self.followup_timeout_s < self.followup_grace_s:
            self.followup_timeout_s = self.followup_grace_s
        # === VIVENTIUM END ===
        self._get_conversation_id = get_conversation_id
        self._set_conversation_id = set_conversation_id
        self._get_agent_id = get_agent_id
        self._set_agent_id = set_agent_id
        self.on_message_callback: Optional[Callable[..., Awaitable[None]]] = None
        self._insight_tasks: set[asyncio.Task] = set()
        self._insight_seen: dict[str, set[str]] = {}
        self._insight_refs: dict[str, int] = {}
        # === VIVENTIUM START ===
        # Feature: Keep Telegram follow-ups aligned with the active LibreChat stream.
        # Reason: Track stream state + cortex activity so DB polling does not stop before follow-ups persist.
        self._active_stream_by_chat: dict[str, str] = {}
        self._stream_final_events: dict[str, asyncio.Event] = {}
        self._pending_followups: dict[str, str] = {}
        self._insight_task_by_stream: dict[str, asyncio.Task] = {}
        self._response_message_ids: dict[str, str] = {}
        self._conversation_by_stream: dict[str, str] = {}
        self._followup_task_by_stream: dict[str, asyncio.Task] = {}
        self._followup_sent: set[str] = set()
        self._followup_send_lock_by_stream: dict[str, asyncio.Lock] = {}
        self._stream_identity: dict[str, dict[str, Any]] = {}
        self._cortex_seen_by_stream: dict[str, bool] = {}
        self._stream_text_by_stream: dict[str, str] = {}
        self._brief_main_reply_by_stream: dict[str, bool] = {}
        self._voice_route_by_chat: dict[str, dict[str, Any]] = {}
        self._voice_route_by_stream: dict[str, dict[str, Any]] = {}
        # === VIVENTIUM END ===
        # === VIVENTIUM START ===
        # Feature: Optional per-chat serialization (disable for OpenClaw-style responsiveness).
        self.serialize_per_chat = _parse_bool_env(
            (os.getenv("VIVENTIUM_TELEGRAM_SERIALIZE_PER_CHAT") or "").strip(),
            False,
        )
        # Preserve lock map for optional serialized mode.
        self._chat_locks: dict[str, asyncio.Lock] = {}
        self._trace_enabled = (os.getenv("VIVENTIUM_TELEGRAM_TRACE") or "").strip() == "1"
        # === VIVENTIUM END ===

        if not self.base_url:
            logger.warning("LibreChatBridge missing VIVENTIUM_LIBRECHAT_ORIGIN")
        if not self.secret:
            logger.warning("LibreChatBridge missing VIVENTIUM_TELEGRAM_SECRET")

    def set_on_message_callback(self, callback: Callable[..., Awaitable[None]]):
        self.on_message_callback = callback

    def get_cached_voice_route(self, chat_id: str) -> Optional[dict[str, Any]]:
        normalized_chat_id = str(chat_id or "").strip()
        if not normalized_chat_id:
            return None
        route = self._voice_route_by_chat.get(normalized_chat_id)
        if isinstance(route, dict):
            return route
        return None

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
        return self._active_stream_by_chat.get(chat_id) == stream_id

    def _set_active_stream(self, chat_id: str, stream_id: str) -> None:
        previous = self._active_stream_by_chat.get(chat_id)
        if previous and previous != stream_id:
            self._trace(
                "LibreChatBridge replacing active stream: chat_id=%s old_stream=%s new_stream=%s",
                chat_id,
                previous,
                stream_id,
            )
            self._cancel_insight_task(previous)
            self._cancel_followup_task(previous)
            self._pending_followups.pop(previous, None)
            self._response_message_ids.pop(previous, None)
            self._conversation_by_stream.pop(previous, None)
            self._followup_sent.discard(previous)
            self._followup_send_lock_by_stream.pop(previous, None)
            self._stream_identity.pop(previous, None)
            self._cortex_seen_by_stream.pop(previous, None)
            self._stream_text_by_stream.pop(previous, None)
            self._brief_main_reply_by_stream.pop(previous, None)
            self._voice_route_by_stream.pop(previous, None)
        self._active_stream_by_chat[chat_id] = stream_id

    def _clear_active_stream(self, chat_id: str, stream_id: str) -> None:
        if self._active_stream_by_chat.get(chat_id) == stream_id:
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

    def _has_followup_sent(self, stream_id: str) -> bool:
        return stream_id in self._followup_sent

    def _remember_stream_text(self, stream_id: str, text: str, *, brief_main_reply: bool) -> None:
        normalized = _normalize_followup_compare_text(text)
        if normalized:
            self._stream_text_by_stream[stream_id] = normalized
        else:
            self._stream_text_by_stream.pop(stream_id, None)
        if brief_main_reply:
            self._brief_main_reply_by_stream[stream_id] = True
        else:
            self._brief_main_reply_by_stream.pop(stream_id, None)

    def _should_send_canonical_text(self, stream_id: str, canonical_text: Any) -> bool:
        canonical = _normalize_followup_compare_text(canonical_text)
        if not canonical or is_no_response_only(canonical):
            return False

        streamed = self._stream_text_by_stream.get(stream_id, "")
        if canonical == streamed:
            return False

        if not streamed:
            return True

        return self._brief_main_reply_by_stream.get(stream_id, False)

    async def _emit_followup_once(
        self,
        *,
        stream_id: Optional[str],
        emit: Callable[[], Awaitable[None]],
    ) -> bool:
        # === VIVENTIUM START ===
        # Feature: Phase A/B follow-up race guard.
        # Root cause: both SSE listener and DB poll path could pass an early dedupe check,
        # yield, then each deliver follow-up text/insights.
        # Fix: per-stream lock + check-and-mark in one critical section.
        # === VIVENTIUM END ===
        if not stream_id:
            await emit()
            return True
        lock = self._followup_send_lock_by_stream.get(stream_id)
        if lock is None:
            lock = asyncio.Lock()
            self._followup_send_lock_by_stream[stream_id] = lock
        async with lock:
            if self._has_followup_sent(stream_id):
                return False
            await emit()
            self._mark_followup_sent(stream_id)
            return True

    async def _send_followup_text_once(
        self,
        chat_id: str,
        text: str,
        *,
        stream_id: Optional[str],
    ) -> bool:
        async def _emit() -> None:
            await self._send_followup_text(chat_id, text, stream_id=stream_id)

        return await self._emit_followup_once(stream_id=stream_id, emit=_emit)

    async def _send_pending_insights_once(
        self,
        chat_id: str,
        insights: list[dict[str, Any]],
        *,
        stream_id: Optional[str],
    ) -> bool:
        async def _emit() -> None:
            await self._send_pending_insights(chat_id, insights, stream_id=stream_id)

        return await self._emit_followup_once(stream_id=stream_id, emit=_emit)

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
    ) -> None:
        self._stream_identity[stream_id] = {
            "telegram_chat_id": telegram_chat_id,
            "telegram_user_id": telegram_user_id,
            "telegram_username": telegram_username,
            "voice_mode": "1" if voice_mode else "",
            "input_mode": input_mode or "",
            "voice_route": voice_route or None,
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
    ) -> None:
        if not self.on_message_callback:
            return
        # === VIVENTIUM START ===
        # Feature: Proactive follow-up voice parity.
        # Purpose: Apply existing voice preference gate + TTS for callback delivery.
        voice_audio: Optional[bytes] = None
        convo_id = preference_convo_id or str(target_chat_id)
        voice_route = self._stream_voice_route(stream_id) or self.get_cached_voice_route(str(target_chat_id))
        if message and convo_id:
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
                    text=message,
                )
                if should_send_voice:
                    voice_audio = await synthesize_speech(message, convo_id, voice_route=voice_route)
            except Exception as exc:
                logger.warning("Failed proactive voice synthesis, falling back to text: %s", exc)
        # === VIVENTIUM END ===

        async def _invoke_callback(
            payload: str,
            *,
            payload_parse_mode: Optional[str],
            payload_voice_audio: Optional[bytes],
        ) -> None:
            if asyncio.iscoroutinefunction(self.on_message_callback):
                try:
                    await self.on_message_callback(
                        target_chat_id,
                        payload,
                        parse_mode=payload_parse_mode,
                        voice_audio=payload_voice_audio,
                    )
                except TypeError:
                    try:
                        await self.on_message_callback(
                            target_chat_id,
                            payload,
                            parse_mode=payload_parse_mode,
                        )
                    except TypeError:
                        await self.on_message_callback(target_chat_id, payload)
            else:
                try:
                    self.on_message_callback(
                        target_chat_id,
                        payload,
                        parse_mode=payload_parse_mode,
                        voice_audio=payload_voice_audio,
                    )
                except TypeError:
                    try:
                        self.on_message_callback(
                            target_chat_id,
                            payload,
                            parse_mode=payload_parse_mode,
                        )
                    except TypeError:
                        self.on_message_callback(target_chat_id, payload)

        try:
            # === VIVENTIUM START ===
            # Feature: Chunk proactive follow-up text before callback delivery.
            # Purpose: Telegram rejects oversized messages; split long follow-ups while
            # preserving existing HTML formatting behavior for each chunk. When
            # proactive voice is enabled, keep text canonical and attach audio only
            # to the final chunk so users do not receive duplicate voice notes.
            if (
                parse_mode == "HTML"
                and isinstance(raw_message, str)
                and raw_message.strip()
            ):
                chunks = split_telegram_text(raw_message)
                if len(chunks) > 1:
                    last_index = len(chunks) - 1
                    for index, chunk in enumerate(chunks):
                        await _invoke_callback(
                            render_telegram_markdown(chunk),
                            payload_parse_mode="HTML",
                            payload_voice_audio=voice_audio if index == last_index else None,
                        )
                    return
            # === VIVENTIUM END ===
            await _invoke_callback(
                message,
                payload_parse_mode=parse_mode,
                payload_voice_audio=voice_audio,
            )
        except Exception as exc:
            logger.warning("Failed to deliver Telegram callback: %s", exc)

    # Track cortex activity seen on SSE so DB polling doesn't exit before persistence catches up.
    def _mark_cortex_seen(self, stream_id: str) -> None:
        self._cortex_seen_by_stream[stream_id] = True

    def _has_cortex_seen(self, stream_id: str) -> bool:
        return self._cortex_seen_by_stream.get(stream_id, False)

    def _has_active_background_tasks(self, stream_id: str) -> bool:
        followup_task = self._followup_task_by_stream.get(stream_id)
        if followup_task and not followup_task.done():
            return True
        insight_task = self._insight_task_by_stream.get(stream_id)
        if insight_task and not insight_task.done():
            return True
        return False
    # === VIVENTIUM END ===

    def reset(self, convo_id: str, system_prompt: Optional[str] = None) -> None:
        _ = system_prompt
        try:
            self._set_conversation_id(str(convo_id), "")
        except Exception:
            logger.debug("Failed to reset LibreChat conversation id for %s", convo_id)

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
        # === VIVENTIUM START ===
        # Feature: Pass Telegram identity for per-user linking and auth.
        # === VIVENTIUM END ===
        telegram_chat_id = (
            kwargs.get("telegram_chat_id")
            or kwargs.get("telegramChatId")
            or chat_id
        )
        telegram_user_id = kwargs.get("telegram_user_id") or kwargs.get("telegramUserId") or ""
        telegram_username = kwargs.get("telegram_username") or kwargs.get("telegramUsername") or ""
        telegram_message_id = kwargs.get("telegram_message_id") or kwargs.get("telegramMessageId") or ""
        telegram_update_id = kwargs.get("telegram_update_id") or kwargs.get("telegramUpdateId") or ""
        # === VIVENTIUM START ===
        # Feature: Voice mode metadata for surface-specific formatting.
        voice_mode = kwargs.get("voice_mode")
        if voice_mode is None:
            voice_mode = kwargs.get("voiceMode")
        input_mode = kwargs.get("input_mode") or kwargs.get("inputMode") or ""
        # Feature: File upload support for vision models.
        files = kwargs.get("files") or None
        # Feature: Time context - pass message timestamp for scheduling awareness.
        message_timestamp = kwargs.get("message_timestamp") or kwargs.get("messageTimestamp") or None
        # Feature: Timezone context for accurate local time formatting.
        client_timezone = kwargs.get("client_timezone") or kwargs.get("clientTimezone") or None
        # Feature: Optional trace id for timing/log correlation.
        trace_id = kwargs.get("trace_id") or kwargs.get("traceId") or ""
        # === VIVENTIUM END ===
        lock: Optional[asyncio.Lock] = self._get_chat_lock(chat_id) if self.serialize_per_chat else None
        # === VIVENTIUM START ===
        # Serialize per-chat requests only when explicitly enabled.
        # === VIVENTIUM END ===
        if lock and lock.locked():
            self._trace("LibreChatBridge waiting for prior run: chat_id=%s", chat_id)
        run_guard = lock if lock is not None else _noop_async_context()
        async with run_guard:
            session = None
            conversation_id = self._get_conversation_id(chat_id) or "new"
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
                session = await self._start_chat(
                    text=text,
                    conversation_id=conversation_id,
                    agent_id=agent_id,
                    telegram_chat_id=str(telegram_chat_id),
                    telegram_user_id=str(telegram_user_id),
                    telegram_username=str(telegram_username),
                    telegram_message_id=str(telegram_message_id) if telegram_message_id is not None else "",
                    telegram_update_id=str(telegram_update_id) if telegram_update_id is not None else "",
                    preference_convo_id=chat_id,
                    voice_mode=voice_mode,
                    input_mode=input_mode,
                    files=files,
                    message_timestamp=message_timestamp,
                    client_timezone=client_timezone,
                    trace_id=trace_id,
                )
                if trace_id:
                    self._timing_log(trace_id, "lc_chat_http", chat_start_ts)
                # === VIVENTIUM END ===
            except TelegramLinkRequired:
                raise
            except Exception as exc:
                logger.error("LibreChatBridge failed to start chat: %s", exc)
                yield "Failed to reach Viventium. Please retry."
                return
            if not session:
                return

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
            )
            self._set_active_stream(chat_id, session.stream_id)
            if session.conversation_id:
                self._conversation_by_stream[session.stream_id] = session.conversation_id
            if session.voice_route:
                self._voice_route_by_stream[session.stream_id] = session.voice_route
                self._voice_route_by_chat[chat_id] = session.voice_route
            insight_task: Optional[asyncio.Task] = None
            if self.on_message_callback:
                insight_task = asyncio.create_task(
                    self._listen_for_insights(stream_id=session.stream_id, chat_id=chat_id),
                )
                self._insight_task_by_stream[session.stream_id] = insight_task
                self._track_task(insight_task)

            if session.conversation_id and session.conversation_id != conversation_id:
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
                    self._voice_route_by_stream.pop(session.stream_id, None)
                # === VIVENTIUM END ===

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
        files: Optional[list] = None,  # === VIVENTIUM: File upload support ===
        message_timestamp: Optional[str] = None,  # === VIVENTIUM: Time context support ===
        client_timezone: Optional[str] = None,  # === VIVENTIUM: Timezone context support ===
        trace_id: Optional[str] = None,  # === VIVENTIUM: Timing/log correlation ===
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
        if telegram_update_id:
            payload["telegramUpdateId"] = telegram_update_id
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
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(chat_url, json=payload, headers=headers)
            if resp.status_code != 200:
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
                raise RuntimeError(f"LibreChat chat failed ({resp.status_code}): {resp.text}")
            data = resp.json()

        if isinstance(data, dict) and data.get("duplicate") is True:
            self._trace(
                "LibreChatBridge duplicate ingress acknowledged: chat_id=%s conversation_id=%s",
                telegram_chat_id,
                data.get("conversationId") or conversation_id,
            )
            return None

        stream_id = data.get("streamId")
        conversation_id = data.get("conversationId")
        voice_route = _normalize_voice_route(data.get("voiceRoute"))
        if not isinstance(stream_id, str) or not stream_id:
            raise RuntimeError("LibreChat response missing streamId")
        if not isinstance(conversation_id, str) or not conversation_id:
            conversation_id = ""

        return LibreChatSession(
            stream_id=stream_id,
            conversation_id=conversation_id,
            voice_route=voice_route,
        )

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
                    120.0,
                )
                timeout = _build_stream_timeout(read_timeout_s)
                async with httpx.AsyncClient(timeout=timeout) as client:
                    async with client.stream("GET", url, headers=headers, params=params) as resp:
                        resp.raise_for_status()

                        async for payload in iter_sse_json_events(chunk_iter=resp.aiter_bytes()):
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
                                yield _stream_error_message(str(err) if err else None)
                                return

                            # === VIVENTIUM START ===
                            # Feature: Track cortex activity to keep DB follow-up polling alive.
                            if payload.get("event") in ("on_cortex_update", "on_cortex_followup"):
                                self._mark_cortex_seen(stream_id)
                            # === VIVENTIUM END ===

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
                                    self._schedule_followup_poll(stream_id, chat_id)

                                # === VIVENTIUM START ===
                                # Feature: Check for explicit errors in final payload before treating as empty.
                                # Added: 2026-02-01
                                final_error = extract_final_error(payload)
                                if final_error:
                                    logger.warning(
                                        "LibreChatBridge final error: chat_id=%s stream_id=%s error=%s",
                                        chat_id,
                                        stream_id,
                                        final_error,
                                    )
                                    yield _stream_error_message(final_error)
                                    return
                                # === VIVENTIUM END ===

                                final_text = extract_final_response_text(payload)
                                final_attachments = extract_attachments(payload)
                                has_final_attachments = len(final_attachments) > 0
                                deferred_internal_final = _is_deferred_internal_final(payload)
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
                                    if deferred_internal_final:
                                        self._trace(
                                            "LibreChatBridge deferred final: chat_id=%s stream_id=%s diagnosis=%s keys=%s",
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
                                # === VIVENTIUM START ===
                                # Feature: Emit any final attachments after the main text.
                                for attachment in final_attachments:
                                    emitted_attachments = True
                                    yield {"type": "attachment", "attachment": attachment}
                                # === VIVENTIUM END ===
                                return

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
                    yield _stream_error_message(str(exc))
                    self._mark_stream_final(stream_id)
                    return

    # === VIVENTIUM START ===
    # Feature: DB-backed follow-up polling to mirror LibreChat UI.
    def _schedule_followup_poll(self, stream_id: str, chat_id: str) -> None:
        if not self.on_message_callback:
            return
        if self._has_followup_sent(stream_id):
            return
        existing = self._followup_task_by_stream.get(stream_id)
        if existing and not existing.done():
            return
        task = asyncio.create_task(self._poll_for_followup(stream_id=stream_id, chat_id=chat_id))
        self._followup_task_by_stream[stream_id] = task
        self._track_task(task)

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
            async with httpx.AsyncClient(timeout=timeout) as client:
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

    async def _poll_for_followup(self, *, stream_id: str, chat_id: str) -> None:
        message_id = self._response_message_ids.get(stream_id, "")
        conversation_id = self._conversation_by_stream.get(stream_id)
        timeout_s = max(self.followup_timeout_s, 1.0)
        interval_s = max(self.followup_interval_s, 0.25)
        grace_s = max(self.followup_grace_s, 0.0)
        started_at = time.monotonic()
        grace_start: Optional[float] = None
        saw_active = False
        last_parts: list[dict[str, Any]] = []

        try:
            if not self.on_message_callback or not self._is_stream_active(chat_id, stream_id):
                return
            if not message_id:
                return
            while time.monotonic() - started_at < timeout_s:
                if not self._is_stream_active(chat_id, stream_id):
                    return
                if self._has_followup_sent(stream_id):
                    return

                state = await self._fetch_followup_state(
                    message_id=message_id,
                    conversation_id=conversation_id,
                    stream_id=stream_id,
                )
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
                                return
                            # === VIVENTIUM END ===
                            sent = await self._send_followup_text_once(
                                chat_id,
                                text,
                                stream_id=stream_id,
                            )
                            # Prevent insight fallback after a merged follow-up is finalized.
                            if sent:
                                self._cancel_insight_task(stream_id)
                            return

                    canonical_text = state.get("canonicalText")
                    if self._should_send_canonical_text(stream_id, canonical_text):
                        sent = await self._send_followup_text_once(
                            chat_id,
                            _prepare_followup_delivery_text(canonical_text),
                            stream_id=stream_id,
                        )
                        if sent:
                            self._cancel_insight_task(stream_id)
                        return

                if isinstance(state, dict) and not parts and not saw_active and not self._has_cortex_seen(stream_id):
                    return

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
                            if self.allow_insight_fallback:
                                insights = extract_completed_cortex_insights(last_parts)
                                if insights:
                                    await self._send_pending_insights_once(
                                        chat_id,
                                        insights,
                                        stream_id=stream_id,
                                    )
                            return

                await asyncio.sleep(interval_s)

            if self.allow_insight_fallback:
                insights = extract_completed_cortex_insights(last_parts)
                if insights:
                    await self._send_pending_insights_once(
                        chat_id,
                        insights,
                        stream_id=stream_id,
                    )
        except asyncio.CancelledError:
            return
        finally:
            self._followup_task_by_stream.pop(stream_id, None)
            insight_task = self._insight_task_by_stream.get(stream_id)
            if not insight_task or insight_task.done():
                self._pending_followups.pop(stream_id, None)
                self._stream_final_events.pop(stream_id, None)
                self._response_message_ids.pop(stream_id, None)
                self._conversation_by_stream.pop(stream_id, None)
                self._followup_sent.discard(stream_id)
                self._followup_send_lock_by_stream.pop(stream_id, None)
                self._cortex_seen_by_stream.pop(stream_id, None)
                self._stream_text_by_stream.pop(stream_id, None)
                self._brief_main_reply_by_stream.pop(stream_id, None)
                self._stream_identity.pop(stream_id, None)
                self._clear_active_stream(chat_id, stream_id)
    # === VIVENTIUM END ===

    async def _listen_for_insights(self, *, stream_id: str, chat_id: str) -> None:
        if not self.on_message_callback:
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
                    async with httpx.AsyncClient(timeout=timeout) as client:
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
            if not followup_task or followup_task.done():
                self._stream_final_events.pop(stream_id, None)
                self._response_message_ids.pop(stream_id, None)
                self._conversation_by_stream.pop(stream_id, None)
                self._followup_sent.discard(stream_id)
                self._followup_send_lock_by_stream.pop(stream_id, None)
                self._cortex_seen_by_stream.pop(stream_id, None)
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
    ) -> None:
        if not text:
            return
        # === VIVENTIUM START ===
        # Feature: No-response tag ({NTA}) should never be delivered to Telegram users.
        if is_no_response_only(text):
            return
        # === VIVENTIUM END ===
        # === VIVENTIUM NOTE ===
        # Fix: Always render HTML for text display, even when input was voice.
        message = render_telegram_markdown(text)
        parse_mode = "HTML"
        # === VIVENTIUM NOTE END ===
        if not message:
            return
        target_chat_id = self._resolve_telegram_chat_id(chat_id=chat_id, stream_id=stream_id)
        if target_chat_id is None:
            return
        self._trace(
            "LibreChatBridge sending follow-up: chat_id=%s length=%s",
            chat_id,
            len(message),
        )
        await self._deliver_callback(
            target_chat_id,
            message,
            parse_mode=parse_mode,
            preference_convo_id=str(chat_id),
            raw_message=text,
            stream_id=stream_id,
        )
    # === VIVENTIUM END ===

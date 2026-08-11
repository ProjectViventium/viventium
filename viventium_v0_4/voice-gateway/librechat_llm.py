# === VIVENTIUM START ===
# Feature: LibreChat Voice Calls - LibreChat-backed LLM for LiveKit Agents
# Added: 2026-01-08
#
# Purpose:
# - Implement `livekit.agents.llm.LLM` by proxying to LibreChat `/api/viventium/voice/*`.
# - Allows LiveKit `AgentSession` to treat LibreChat as the LLM while still using LiveKit STT/TTS.
# === VIVENTIUM END ===

from __future__ import annotations

import asyncio
import heapq
import json
import logging
import math
import os
import re
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import quote, urlparse

import aiohttp

logger = logging.getLogger("voice-gateway.librechat_llm")


class _NonRetryableVoiceIngressError(RuntimeError):
    pass


class _RetryableVoiceIngressError(RuntimeError):
    pass
GLASSHIVE_MCP_SERVER = "glasshive-workers-projects"
from livekit.agents import llm
from livekit.agents.llm import ChatChunk, ChatContext, ChoiceDelta
from livekit.agents.llm.tool_context import FunctionTool, RawFunctionTool, ToolChoice
from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS, NOT_GIVEN, APIConnectOptions, NotGivenOr

from sse import (
    # === VIVENTIUM START ===
    extract_cortex_message_id,
    # === VIVENTIUM END ===
    extract_cortex_insight,
    extract_raw_text_deltas,
    iter_sse_json_events,
    sanitize_voice_delta_text,
    sanitize_voice_followup_text,
    sanitize_voice_tts_text,
    strip_voice_control_tags,
    VoiceControlDisplayFilter,
)
from speaker_segments import SPEAKER_CONTEXT_EXTRA_KEY
from voice_hop_trace import VoiceHopTrace

# === VIVENTIUM START ===
# Feature: No-response tag ({NTA}) suppression for voice-call main responses.
#
# Purpose:
# - LibreChat can intentionally return `{NTA}` (or strict variants) for "say nothing".
# - LiveKit voice calls should not speak or display this internal marker.
_SHARED_PATH = Path(__file__).resolve().parent.parent / "shared"  # .../viventium_v0_4/shared
if str(_SHARED_PATH) not in sys.path:
    sys.path.insert(0, str(_SHARED_PATH))

try:
    from no_response import is_no_response_only, strip_inline_nta
except Exception:
    _NO_RESPONSE_TAG_RE = re.compile(r"^\\s*\\{\\s*NTA\\s*\\}\\s*$", re.IGNORECASE)

    def is_no_response_only(text: Optional[str]) -> bool:
        if not isinstance(text, str):
            return False
        trimmed = text.strip()
        if not trimmed:
            return False
        return bool(_NO_RESPONSE_TAG_RE.match(trimmed))

    def strip_inline_nta(text: Optional[str]) -> str:
        if not isinstance(text, str):
            return text or ""
        cleaned = re.sub(r"\\{\\s*NTA\\s*\\}", " ", text, flags=re.IGNORECASE)
        cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
        cleaned = re.sub(r"\s+\n", "\n", cleaned)
        cleaned = re.sub(r"\n\s+", "\n", cleaned)
        return cleaned.strip()


_NO_RESPONSE_PREFIX_MAX_CHARS = 256
_NO_RESPONSE_TAIL_WORDS = {
    "right",
    "now",
    "for",
    "at",
    "this",
    "time",
    "the",
    "moment",
    "currently",
    "so",
    "far",
    "yet",
    "today",
    "sorry",
    "thanks",
    "thank",
    "you",
}

def _normalize_no_response_word(word: str) -> str:
    # Keep it ASCII-only; words in no-response variants are English.
    return re.sub(r"[^a-z]+", "", (word or "").lower())


def _is_possible_no_response_prefix(text: str) -> bool:
    """
    Return True if the current partial output *could still* end up being a strict no-response-only
    message, so we should keep buffering deltas (avoid `{NTA}` flashing in UI/TTS).
    """
    trimmed = (text or "").strip()
    if not trimmed:
        return True
    if len(trimmed) > _NO_RESPONSE_PREFIX_MAX_CHARS:
        return False

    compact = "".join(ch for ch in trimmed.lower() if not ch.isspace())
    if compact.startswith("{"):
        # Buffer only while it's still consistent with `{NTA}` (ignore whitespace).
        return all(ch in {"{", "}", "n", "t", "a"} for ch in compact)

    words = trimmed.split()
    if not words:
        return True

    w0 = _normalize_no_response_word(words[0])
    if w0 != "nothing":
        return False

    if len(words) == 1:
        return True

    w1 = _normalize_no_response_word(words[1])
    if not w1:
        return True

    idx = 1
    if w1 == "new":
        idx += 1
        if len(words) <= idx:
            return True
        w_next = _normalize_no_response_word(words[idx])
        if w_next != "to":
            return False
        idx += 1
    elif w1 == "to":
        idx += 1
    else:
        return False

    if len(words) <= idx:
        return True
    w_add = _normalize_no_response_word(words[idx])
    if w_add != "add":
        return False

    for extra in words[idx + 1 :]:
        w = _normalize_no_response_word(extra)
        if not w:
            continue
        if w not in _NO_RESPONSE_TAIL_WORDS:
            return False

    return True


def _should_debug_voice_markup() -> bool:
    return (os.getenv("VIVENTIUM_VOICE_DEBUG_TTS", "") or "").strip() == "1"


def _debug_text(text: str, *, max_len: int = 500) -> str:
    snippet = (text or "").replace("\n", "\\n").replace("\r", "\\r")
    if len(snippet) > max_len:
        return snippet[:max_len] + "..."
    return snippet


def _debug_text_json(text: str) -> str:
    return json.dumps(text or "", ensure_ascii=False)


def _summarize_error_for_log(error: str) -> str:
    text = error or ""
    summary: list[str] = []
    status_match = re.search(r"\b([45]\d{2})\b", text)
    if status_match:
        summary.append(f"status={status_match.group(1)}")

    json_start = text.find("{")
    if json_start >= 0:
        try:
            payload = json.loads(text[json_start:])
            if isinstance(payload, dict):
                outer_type = payload.get("type")
                if isinstance(outer_type, str) and outer_type.strip():
                    summary.append(f"type={outer_type.strip()}")
                inner = payload.get("error")
                if isinstance(inner, dict):
                    inner_type = inner.get("type")
                    if isinstance(inner_type, str) and inner_type.strip():
                        summary.append(f"error_type={inner_type.strip()}")
                    inner_code = inner.get("code")
                    if isinstance(inner_code, str) and inner_code.strip():
                        summary.append(f"error_code={inner_code.strip()}")
        except Exception:
            pass

    if summary:
        return " ".join(summary)
    return _debug_text(text, max_len=120)


class _NoResponseStreamGuard:
    """
    Buffers initial deltas that might form a no-response-only output, so `{NTA}` doesn't flash.

    We only suppress at the end once we can confidently classify the full response as no-response-only.
    """

    def __init__(self) -> None:
        self._buffer: list[str] = []
        self._buffer_text = ""
        self._emitting = False

    def feed(self, delta: str) -> list[str]:
        if self._emitting:
            cleaned = strip_inline_nta(delta, preserve_outer_whitespace=True)
            return [cleaned] if cleaned else []

        self._buffer.append(delta)
        self._buffer_text += delta

        if not _is_possible_no_response_prefix(self._buffer_text):
            self._emitting = True
            cleaned = strip_inline_nta(self._buffer_text, preserve_outer_whitespace=True)
            self._buffer = []
            self._buffer_text = ""
            return [cleaned] if cleaned else []

        return []

    def finalize(self, full_text: str) -> tuple[bool, list[str]]:
        if is_no_response_only(full_text):
            return True, []
        if self._emitting:
            return False, []
        # Not a no-response-only output; flush anything we buffered.
        self._emitting = True
        cleaned = strip_inline_nta(self._buffer_text)
        self._buffer = []
        self._buffer_text = ""
        return False, ([cleaned] if cleaned else [])


# === VIVENTIUM START ===
# Feature: Voice TTS chunk boundary guard.
#
# Purpose:
# - TTS providers may synthesize tiny streamed deltas as their own utterances.
# - A single-character first delta like "I" can sound like "EEE"; a later standalone "." can sound
#   like "dot". Buffer phrase-sized chunks and drop orphan punctuation that arrives after the
#   phrase it was meant to punctuate has already been sent to TTS.
class _VoiceTtsDeltaBuffer:
    _CLOSING_PUNCTUATION = "\"'”’)]}"

    def __init__(
        self,
        *,
        min_first_chars: int = 10,
        max_chars: int = 48,
        sanitize_chunk: Optional[Callable[[str], str]] = None,
    ) -> None:
        self._buffer = ""
        self._has_emitted = False
        self._last_emitted_text = ""
        self._min_first_chars = max(1, min_first_chars)
        self._max_chars = max(self._min_first_chars, max_chars)
        self._sanitize_chunk = sanitize_chunk

    @staticmethod
    def _is_orphan_punctuation(text: str) -> bool:
        stripped = (text or "").strip()
        punctuation = ".,!?;:…"
        closers = _VoiceTtsDeltaBuffer._CLOSING_PUNCTUATION
        return (
            bool(stripped)
            and any(ch in punctuation for ch in stripped)
            and all(ch in punctuation or ch in closers for ch in stripped)
        )

    @classmethod
    def _terminal_candidate(cls, text: str) -> str:
        candidate = (text or "").strip()
        while candidate and candidate[-1] in cls._CLOSING_PUNCTUATION:
            candidate = candidate[:-1].rstrip()
        return candidate

    @classmethod
    def _ends_with_terminal(cls, text: str) -> bool:
        candidate = cls._terminal_candidate(text)
        if not candidate:
            return False
        if candidate[-1] == "." and len(candidate) >= 2 and candidate[-2].isdigit():
            # Hold digit-dot tails long enough to see whether the next delta is a decimal/version
            # continuation instead of sentence punctuation.
            return False
        return candidate[-1] in ".!?;:"

    @staticmethod
    def _has_short_unclosed_quote_tail(text: str) -> bool:
        speech_text = strip_voice_control_tags(text)
        stripped = speech_text.strip()
        if not stripped:
            return False

        curly_open = stripped.rfind("“")
        curly_close = stripped.rfind("”")
        if curly_open > curly_close:
            last_open = curly_open
        elif stripped.count('"') % 2:
            last_open = stripped.rfind('"')
        else:
            return False

        tail = stripped[last_open + 1 :].strip()
        return bool(tail) and len(tail) <= 24

    @staticmethod
    def _ends_inside_non_speech_artifact(text: str) -> bool:
        if not text or text[-1:].isspace():
            return False
        tail = text.rsplit(maxsplit=1)[-1]
        lowered_tail = tail.lower()
        if lowered_tail.startswith(("http://", "https://", "www.")):
            return not bool(re.search(r"\.[A-Za-z]{2,}(?:/[^\s]*)?[.!?,;:]?$", tail))
        if "@" in tail and re.search(r"[\w.+-]+@[\w.-]*$", tail):
            return not bool(re.search(r"@[\w.-]+\.[A-Za-z]{2,}[.!?,;:]?$", tail))
        if re.search(r"\[[^\]\n]*\]\([^)\s]*$", text):
            return True
        if text.count("```") % 2:
            return True
        if re.search(r"`[^`\n]*$", text):
            return True
        if re.search(r"<[A-Za-z][^>\n]*$", text):
            return True
        return False

    def _has_short_unterminated_post_terminal_tail(self, text: str) -> bool:
        speech_text = strip_voice_control_tags(text)
        stripped = speech_text.strip()
        if not stripped or stripped[-1] in ".!?;:":
            return False

        last_terminal = -1
        for match in re.finditer(r"[.!?;:]", stripped):
            idx = match.start()
            if (
                match.group(0) == "."
                and idx > 0
                and idx + 1 < len(stripped)
                and stripped[idx - 1].isdigit()
                and stripped[idx + 1].isdigit()
            ):
                continue
            last_terminal = idx

        if last_terminal < 0:
            return False

        tail = stripped[last_terminal + 1 :].strip()
        return bool(tail) and len(tail) <= self._min_first_chars + 8

    def _should_flush(self, text: str) -> bool:
        return self._flush_split_index(text) is not None

    def _find_safe_max_split_index(self, text: str) -> Optional[int]:
        if not text:
            return None

        candidates = [
            match.end()
            for match in re.finditer(r"\s+", text)
            if match.end() >= self._min_first_chars and match.end() < len(text)
        ]
        if not candidates:
            return None

        preferred = [idx for idx in candidates if idx <= self._max_chars]
        if preferred:
            return max(preferred)
        return min(candidates)

    def _flush_split_index(self, text: str) -> Optional[int]:
        speech_text = strip_voice_control_tags(text)
        stripped = speech_text.strip()
        if not stripped:
            return None
        if self._has_emitted and self._is_orphan_punctuation(stripped):
            return None
        if self._ends_inside_non_speech_artifact(text):
            return None
        if len(stripped) >= 4 and self._ends_with_terminal(stripped):
            return len(text)
        if len(stripped) >= self._min_first_chars + 8 and text[-1:].isspace():
            # A delayed terminal mark often arrives as the next tiny token (`?`, `!`, or `.`).
            # Do not flush a short second sentence before its punctuation can attach.
            if (
                self._has_short_unterminated_post_terminal_tail(text)
                or self._has_short_unclosed_quote_tail(text)
            ):
                return None
            return self._find_safe_max_split_index(text) or len(text)
        if len(stripped) >= self._max_chars:
            return self._find_safe_max_split_index(text)
        return None

    def _drop_leading_orphan_punctuation(self, text: str) -> str:
        if not text or not self._last_emitted_text:
            return text

        match = re.match(r"^(\s*)([.,!?;:…]+)(\s*)", text)
        if not match:
            return text

        remaining = text[match.end() :]
        if not remaining:
            return ""

        previous = self._last_emitted_text.rstrip()
        if (
            previous[-1:].isdigit()
            and remaining[:1].isdigit()
            and "." in match.group(2)
        ):
            return text

        if not self._last_emitted_text[-1:].isspace() and not remaining[:1].isspace():
            return f" {remaining}"
        return remaining

    def _repair_boundary(self, text: str) -> str:
        if not text or not self._last_emitted_text:
            return text
        if self._last_emitted_text[-1:].isspace():
            return text
        if text[:1].isspace():
            return text
        previous = self._last_emitted_text.rstrip()
        if not previous:
            return text
        # Streaming providers may split "sentence. Next" as "sentence." + "Next".
        # Repair only sentence-boundary joins so mid-word token chunks stay untouched.
        if previous[-1] in ".!?;:" and re.match(r"[A-Za-z0-9\"'([]", text[:1]):
            return f" {text}"
        return text

    def _mark_emitted(self, text: str) -> str:
        repaired = self._repair_boundary(text)
        self._last_emitted_text += repaired
        return repaired

    def _prepare_output(self, text: str) -> str:
        out = self._drop_leading_orphan_punctuation(text)
        if self._sanitize_chunk is not None and out:
            out = self._sanitize_chunk(out)
            out = self._drop_leading_orphan_punctuation(out)
        if not out or self._is_orphan_punctuation(out):
            return ""
        return out

    def feed(self, delta: str) -> list[str]:
        if not delta:
            return []
        self._buffer += delta
        emitted: list[str] = []
        while True:
            split_index = self._flush_split_index(self._buffer)
            if split_index is None or split_index <= 0:
                break
            out = self._buffer[:split_index]
            self._buffer = self._buffer[split_index:]
            out = self._prepare_output(out)
            if not out:
                continue
            self._has_emitted = True
            emitted.append(self._mark_emitted(out))
        return emitted

    def finalize(self) -> list[str]:
        if not self._buffer:
            return []
        out = self._buffer
        self._buffer = ""
        out = self._prepare_output(out)
        if not out:
            return []
        self._has_emitted = True
        return [self._mark_emitted(out)]
# === VIVENTIUM END ===


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
    return len(parts) == 2 and parts[1] == GLASSHIVE_MCP_SERVER


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


def _payload_has_glasshive_tool_call(payload: dict[str, Any]) -> bool:
    for part in _iter_tool_call_parts(payload):
        if _is_glasshive_tool_name(_extract_tool_call_name(part)):
            return True
    return False


@dataclass(frozen=True)
class LibreChatAuth:
    call_session_id: str
    call_secret: str
    job_id: Optional[str] = None
    worker_id: Optional[str] = None


def _extract_last_user_text(chat_ctx: ChatContext) -> str:
    for item in reversed(chat_ctx.items):
        if getattr(item, "type", None) != "message":
            continue
        if getattr(item, "role", None) != "user":
            continue
        # livekit-agents ChatMessage.content is a list of ChatContent where
        # ChatContent is Union[ImageContent, AudioContent, str]. For text, it's `str`.
        content = getattr(item, "content", None)
        if isinstance(content, str) and content.strip():
            return content.strip()
        if isinstance(content, list):
            parts: list[str] = []
            for c in content:
                if isinstance(c, str) and c.strip():
                    parts.append(c)
            text = "".join(parts).strip()
            if text:
                return text
    return ""


def _extract_last_user_speaker_context(chat_ctx: ChatContext) -> dict[str, Any]:
    for item in reversed(chat_ctx.items):
        if getattr(item, "type", None) != "message" or getattr(item, "role", None) != "user":
            continue
        extra = getattr(item, "extra", None)
        context = extra.get(SPEAKER_CONTEXT_EXTRA_KEY) if isinstance(extra, dict) else None
        if not isinstance(context, dict):
            return {}
        segments = context.get("speakerSegments")
        revisions = context.get("speakerSegmentRevisions")
        return {
            "speakerSegments": segments if isinstance(segments, list) else [],
            "speakerSegmentRevisions": revisions if isinstance(revisions, list) else [],
            "speakerLabel": str(context.get("speakerLabel") or "room"),
            "ownerParticipantIdentity": str(context.get("ownerParticipantIdentity") or ""),
            "ownerTrackSid": str(context.get("ownerTrackSid") or ""),
            "utteranceEndAtMs": context.get("utteranceEndAtMs"),
        }
    return {}


def _extract_final_response_text(final_event: dict[str, Any]) -> str:
    """
    Extract assistant text from a LibreChat `final: true` SSE payload.
    """
    resp = final_event.get("responseMessage")
    if not isinstance(resp, dict):
        return ""
    content = resp.get("content")
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for part in content:
        if not isinstance(part, dict):
            continue
        if part.get("type") == "error":
            raw = part.get("error")
            msg = ""
            if isinstance(raw, str) and raw.strip():
                msg = raw.strip()
            elif isinstance(raw, dict):
                inner = raw.get("message")
                if isinstance(inner, str) and inner.strip():
                    msg = inner.strip()
            # Voice should not read raw stack traces or auth strings aloud; map to a generic UX message.
            logger.warning(
                "[LibreChatLLM] Final response contained error content; using voice-safe fallback (%s)",
                _summarize_error_for_log(msg or "voice generation error"),
            )
            return sanitize_voice_followup_text(_select_stream_error_message(msg or "voice generation error"))
        if part.get("type") != "text":
            continue
        t = part.get("text")
        if isinstance(t, str) and t:
            parts.append(
                sanitize_voice_followup_text(t, preserve_leading_space=len(parts) > 0)
            )
        elif isinstance(t, dict):
            v = t.get("value")
            if isinstance(v, str) and v:
                parts.append(
                    sanitize_voice_followup_text(v, preserve_leading_space=len(parts) > 0)
                )
    return "".join(parts).strip()


def _extract_resume_state_text(event: dict[str, Any]) -> str:
    """Return the raw persisted assistant text used to dedupe a resumed SSE stream."""
    resume_state = event.get("resumeState")
    if not isinstance(resume_state, dict):
        return ""
    content = resume_state.get("aggregatedContent")
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for part in content:
        if not isinstance(part, dict) or part.get("type") != "text":
            continue
        text = part.get("text")
        if isinstance(text, str):
            parts.append(text)
        elif isinstance(text, dict) and isinstance(text.get("value"), str):
            parts.append(text["value"])
    return "".join(parts)


def _extract_final_response_message_id(final_event: dict[str, Any]) -> str:
    """
    Extract the canonical assistant messageId from a LibreChat `final: true` SSE payload.
    """
    resp = final_event.get("responseMessage")
    if not isinstance(resp, dict):
        return ""
    message_id = resp.get("messageId")
    if isinstance(message_id, str) and message_id.strip():
        return message_id.strip()
    return ""


def _parse_positive_float(value: str, fallback: float) -> float:
    try:
        n = float(value)
        if n > 0 and n != float("inf"):
            return n
    except Exception:
        pass
    return fallback

# === VIVENTIUM START ===
# Voice stream retry/error helpers (configurable via env).
def _parse_non_negative_int(value: str, fallback: int) -> int:
    try:
        n = int(value)
        if n >= 0:
            return n
    except Exception:
        pass
    return fallback


def _get_voice_sse_retry_config() -> tuple[int, float]:
    max_retries = _parse_non_negative_int(
        os.getenv("VIVENTIUM_VOICE_SSE_MAX_RETRIES", "").strip(),
        2,
    )
    retry_delay_s = _parse_positive_float(
        os.getenv("VIVENTIUM_VOICE_SSE_RETRY_DELAY_S", "").strip(),
        0.5,
    )
    return max_retries, retry_delay_s


def _select_stream_error_message(error: Optional[str]) -> str:
    tool_message = os.getenv("VIVENTIUM_VOICE_TOOL_ERROR_MESSAGE", "").strip()
    stream_message = os.getenv("VIVENTIUM_VOICE_STREAM_ERROR_MESSAGE", "").strip()
    auth_message = os.getenv("VIVENTIUM_VOICE_AUTH_ERROR_MESSAGE", "").strip()
    rate_limit_message = os.getenv("VIVENTIUM_VOICE_RATE_LIMIT_ERROR_MESSAGE", "").strip()
    if not tool_message:
        tool_message = "I'm having trouble reaching your tools right now. Please try again."
    if not stream_message:
        stream_message = "I'm having trouble reaching the service right now. Please try again."
    if not auth_message:
        auth_message = (
            "The selected voice-call model needs a valid connected account or API key. "
            "Reconnect it in Settings, then retry."
        )
    if not rate_limit_message:
        rate_limit_message = (
            "The selected voice-call model hit a provider rate limit. "
            "Choose a fallback model in Agent Builder or wait for the limit to reset."
        )
    if error:
        lowered = error.lower()
        if "mcp" in lowered or "tool" in lowered:
            return tool_message
        if (
            "rate_limit" in lowered
            or "rate limit" in lowered
            or "too many requests" in lowered
            or "temporarily overloaded" in lowered
            or "temporarily unavailable" in lowered
            or "server_is_overloaded" in lowered
            or "servers are currently overloaded" in lowered
            or " 429 " in f" {lowered} "
            or " 503 " in f" {lowered} "
            or " 529 " in f" {lowered} "
        ):
            return rate_limit_message
        if (
            "authentication" in lowered
            or "credential" in lowered
            or "unauthorized" in lowered
            or " 401 " in f" {lowered} "
            or " 403 " in f" {lowered} "
        ):
            return auth_message
    return stream_message


def _extract_stream_error(payload: dict[str, Any]) -> Optional[str]:
    if payload.get("_sse_event") != "error":
        return None
    err = payload.get("error")
    if isinstance(err, str) and err.strip():
        return err.strip()
    return "voice stream error"
# === VIVENTIUM END ===


_VOICE_TASK_STATES = {
    "queued",
    "running",
    "needs_input",
    "recovering",
    "cancelling",
    "completed",
    "failed",
    "cancelled_confirmed",
    "cancelled_unenforceable",
}
_VOICE_TASK_SUPPRESSING_STATES = {
    "cancelling",
    "cancelled_confirmed",
    "cancelled_unenforceable",
}
_VOICE_TASK_TERMINAL_STATES = {
    "completed",
    "failed",
    "cancelled_confirmed",
    "cancelled_unenforceable",
}
_VOICE_TASK_EVENT_TYPES = {
    "state",
    "snapshot",
    "progress",
    "source",
    "needs_input",
    "result",
    "error",
}


def _extract_voice_task_sync(
    payload: dict[str, Any],
    *,
    expected_call_session_id: str,
) -> Optional[dict[str, Any]]:
    event_type = payload.get("event") or payload.get("type") or payload.get("_sse_event")
    if event_type != "voice_task_sync":
        return None
    if set(payload) != {
        "version",
        "callSessionId",
        "state",
        "emittedAt",
        "_sse_event",
    }:
        return None
    if payload.get("version") != 1 or isinstance(payload.get("version"), bool):
        return None
    if payload.get("callSessionId") != expected_call_session_id:
        return None
    if not _bounded_string(
        payload.get("callSessionId"),
        maximum=160,
        required=True,
    ):
        return None
    if payload.get("state") != "synchronized":
        return None
    emitted_at = payload.get("emittedAt")
    if not _bounded_string(emitted_at, maximum=64, required=True):
        return None
    try:
        parsed_emitted_at = datetime.fromisoformat(
            str(emitted_at).replace("Z", "+00:00")
        )
    except ValueError:
        return None
    if parsed_emitted_at.tzinfo is None or parsed_emitted_at.utcoffset() != timezone.utc.utcoffset(
        parsed_emitted_at
    ):
        return None
    return {
        "version": 1,
        "callSessionId": expected_call_session_id,
        "state": "synchronized",
        "emittedAt": emitted_at,
    }


@dataclass
class _TaskEventCursor:
    latest_sequence: int
    updated_at: float
    terminal: bool = False


class _VoiceTaskEventGate:
    """Bounded per-task ordering and suppression barrier shared by every output path."""

    def __init__(
        self,
        *,
        max_tasks: int = 4_096,
        ttl_s: float = 86_400.0,
        suppression_ttl_s: float = 86_400.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max_tasks = max(int(max_tasks), 1)
        self._ttl_s = max(float(ttl_s), 1.0)
        self._suppression_ttl_s = max(float(suppression_ttl_s), 86_400.0)
        self._clock = clock
        self._by_task: dict[str, _TaskEventCursor] = {}
        # Cancellation is a safety barrier, not an ordering cursor. Keep it in
        # an independent 24-hour tombstone map so ordinary task churn cannot
        # evict an accepted cancellation while the call/task may still replay.
        self._suppression_tombstones: dict[str, float] = {}
        self._suppression_expiry_heap: list[tuple[float, str]] = []

    def _install_suppression(self, task_id: str, now: float) -> None:
        if task_id in self._suppression_tombstones:
            return
        expires_at = now + self._suppression_ttl_s
        self._suppression_tombstones[task_id] = expires_at
        heapq.heappush(self._suppression_expiry_heap, (expires_at, task_id))

    def accept(self, event: dict[str, Any]) -> bool:
        task_id = str(event.get("taskId") or "").strip()
        sequence = event.get("sequence")
        state = str(event.get("state") or "")
        if (
            not task_id
            or not isinstance(sequence, int)
            or isinstance(sequence, bool)
            or sequence < 0
        ):
            return False
        now = self._clock()
        self._prune(now)
        if task_id in self._suppression_tombstones and state not in (
            _VOICE_TASK_SUPPRESSING_STATES | _VOICE_TASK_TERMINAL_STATES
        ):
            return False
        cursor = self._by_task.get(task_id)
        if cursor is not None:
            if sequence <= cursor.latest_sequence:
                return False
            if cursor.terminal and state not in _VOICE_TASK_TERMINAL_STATES:
                return False
        else:
            cursor = _TaskEventCursor(latest_sequence=-1, updated_at=now)
            self._by_task[task_id] = cursor

        # Install the barrier before returning control to any publisher/speech handler.
        cursor.latest_sequence = sequence
        cursor.updated_at = now
        if state in _VOICE_TASK_SUPPRESSING_STATES:
            self._install_suppression(task_id, now)
        if state in _VOICE_TASK_TERMINAL_STATES:
            cursor.terminal = True
        self._prune(now)
        return True

    def mark_cancel_accepted(self, task_id: str) -> None:
        normalized = (task_id or "").strip()
        if not normalized:
            return
        now = self._clock()
        self._prune(now)
        self._install_suppression(normalized, now)
        self._prune(now)

    def is_suppressed(self, task_id: str) -> bool:
        normalized = (task_id or "").strip()
        if not normalized:
            return False
        self._prune(self._clock())
        return normalized in self._suppression_tombstones

    def _prune(self, now: float) -> None:
        expired = [
            task_id
            for task_id, cursor in self._by_task.items()
            if now - cursor.updated_at > self._ttl_s
        ]
        for task_id in expired:
            self._by_task.pop(task_id, None)
        while (
            self._suppression_expiry_heap
            and self._suppression_expiry_heap[0][0] < now
        ):
            expires_at, task_id = heapq.heappop(self._suppression_expiry_heap)
            if self._suppression_tombstones.get(task_id) == expires_at:
                self._suppression_tombstones.pop(task_id, None)
        while len(self._by_task) > self._max_tasks:
            oldest_task_id = min(
                self._by_task,
                key=lambda task_id: self._by_task[task_id].updated_at,
            )
            self._by_task.pop(oldest_task_id, None)


def _bounded_string(
    value: Any,
    *,
    maximum: int,
    required: bool = False,
) -> bool:
    return isinstance(value, str) and (bool(value.strip()) or not required) and len(value) <= maximum


def _valid_voice_task_source(source: Any) -> bool:
    if not isinstance(source, dict):
        return False
    allowed = {"id": 160, "title": 200, "provider": 80, "url": 1_000}
    if not any(_bounded_string(source.get(key), maximum=limit, required=True) for key, limit in allowed.items()):
        return False
    structurally_valid = all(
        key in allowed and _bounded_string(value, maximum=allowed[key])
        for key, value in source.items()
    )
    if not structurally_valid:
        return False
    if "url" in source:
        parsed = urlparse(source["url"])
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return False
    return True


def _extract_voice_task_event(
    payload: dict[str, Any],
    *,
    expected_call_session_id: str = "",
) -> Optional[dict[str, Any]]:
    event_type = payload.get("event") or payload.get("type") or payload.get("_sse_event")
    if event_type != "voice_task_event":
        return None
    task_event = payload.get("voiceTaskEvent")
    if not isinstance(task_event, dict):
        return None
    if task_event.get("version") != 1:
        return None
    if not _bounded_string(task_event.get("eventId"), maximum=160, required=True):
        return None
    if not _bounded_string(task_event.get("taskId"), maximum=160, required=True):
        return None
    if not _bounded_string(task_event.get("callSessionId"), maximum=160, required=True):
        return None
    if expected_call_session_id and task_event.get("callSessionId") != expected_call_session_id:
        return None
    if task_event.get("state") not in _VOICE_TASK_STATES:
        return None
    if task_event.get("type") not in _VOICE_TASK_EVENT_TYPES:
        return None
    if (
        not isinstance(task_event.get("sequence"), int)
        or isinstance(task_event.get("sequence"), bool)
        or task_event["sequence"] < 0
    ):
        return None
    emitted_at = task_event.get("emittedAt")
    if not _bounded_string(emitted_at, maximum=64, required=True):
        return None
    try:
        parsed_emitted_at = datetime.fromisoformat(str(emitted_at).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed_emitted_at.tzinfo is None:
        return None
    if not isinstance(task_event.get("cancellable"), bool):
        return None
    if not isinstance(task_event.get("retryable"), bool):
        return None
    owner = task_event.get("owner")
    if (
        not isinstance(owner, dict)
        or not _bounded_string(owner.get("kind"), maximum=80, required=True)
        or any(key not in {"kind", "id"} for key in owner)
        or ("id" in owner and not _bounded_string(owner.get("id"), maximum=160))
    ):
        return None
    for key, maximum in (
        ("conversationId", 160),
        ("turnId", 160),
        ("streamId", 160),
        ("parentTaskId", 160),
        ("phase", 80),
        ("label", 160),
        ("detail", 500),
        ("resultMessageId", 160),
    ):
        if key in task_event and not _bounded_string(task_event.get(key), maximum=maximum):
            return None
    source = task_event.get("source")
    if source is not None and not _valid_voice_task_source(source):
        return None
    sources = task_event.get("sources")
    if sources is not None and (
        not isinstance(sources, list)
        or len(sources) > 32
        or any(not _valid_voice_task_source(item) for item in sources)
    ):
        return None
    needs_input = task_event.get("needsInput")
    if needs_input is not None and (
        not isinstance(needs_input, dict)
        or set(needs_input) - {"prompt", "inputType"}
        or not _bounded_string(needs_input.get("prompt"), maximum=300, required=True)
        or needs_input.get("inputType") not in {"text", "choice", "confirm"}
    ):
        return None
    error = task_event.get("error")
    if error is not None and (
        not isinstance(error, dict)
        or set(error) - {"code", "message", "retryable"}
        or not _bounded_string(error.get("code"), maximum=80, required=True)
        or not _bounded_string(error.get("message"), maximum=300, required=True)
        or (
            "retryable" in error
            and not isinstance(error.get("retryable"), bool)
        )
    ):
        return None
    progress = task_event.get("progress")
    if progress is not None:
        valid_progress = isinstance(progress, dict)
        current = progress.get("current") if isinstance(progress, dict) else None
        total = progress.get("total") if isinstance(progress, dict) else None
        valid_progress = bool(
            valid_progress
            and isinstance(current, (int, float))
            and not isinstance(current, bool)
            and isinstance(total, (int, float))
            and not isinstance(total, bool)
            and math.isfinite(float(current))
            and math.isfinite(float(total))
            and 0 <= float(current) <= float(total)
            and float(total) > 0
            and (
                "unit" not in progress
                or (
                    isinstance(progress.get("unit"), str)
                    and len(progress.get("unit")) <= 40
                )
            )
        )
        if not valid_progress:
            return None
    return task_event


def format_insights_for_direct_speech(insights: list[dict[str, Any]]) -> str:
    """
    Deterministically format cortex insights for voice output (no extra LLM call).
    This avoids the voice playground diverging from LibreChat's DB truth.
    """
    # === VIVENTIUM START ===
    # Keep voice UX configurable; avoid hardcoded preambles or labels.
    preamble = (os.getenv("VIVENTIUM_VOICE_INSIGHT_PREAMBLE", "") or "").strip()
    include_names = (os.getenv("VIVENTIUM_VOICE_INSIGHT_INCLUDE_CORTEX_NAME", "") or "").strip()
    include_names = include_names == "1"
    # === VIVENTIUM END ===

    lines: list[str] = []
    for insight_obj in insights:
        if not isinstance(insight_obj, dict):
            continue
        name = insight_obj.get("cortex_name") or "Background Analysis"
        text = insight_obj.get("insight") or ""
        if not isinstance(text, str):
            continue
        # === VIVENTIUM START ===
        # Ensure follow-up speech removes plans/URLs/emails/markdown artifacts.
        clean = sanitize_voice_followup_text(text)
        # === VIVENTIUM END ===
        if not clean:
            continue
        # Keep it speakable; avoid extremely long monologues.
        if len(clean) > 700:
            clean = clean[:700].rstrip() + "..."
        if include_names and isinstance(name, str) and name.strip():
            lines.append(f"{name.strip()}: {clean}")
        else:
            lines.append(clean)

    if not lines:
        return ""

    if preamble:
        return f"{preamble} {' '.join(lines)}"
    return " ".join(lines)


def _should_log_latency() -> bool:
    return (os.getenv("VIVENTIUM_VOICE_LOG_LATENCY", "") or "").strip() == "1"


def _voice_abort_timeout_s() -> float:
    raw = (os.getenv("VIVENTIUM_VOICE_ABORT_TIMEOUT_S", "") or "").strip()
    try:
        value = float(raw) if raw else 2.0
    except ValueError:
        value = 2.0
    return max(0.25, min(value, 10.0))


async def _abort_librechat_voice_stream(
    *,
    session: aiohttp.ClientSession,
    origin: str,
    stream_id: str,
    headers: dict[str, str],
    request_id: str,
    started_at: float,
    reason: str,
    log_latency: bool,
) -> None:
    abort_url = f"{origin}/api/viventium/voice/stream/{stream_id}/abort"
    try:
        async with session.post(
            abort_url,
            headers=headers,
            json={"reason": reason},
            timeout=aiohttp.ClientTimeout(total=_voice_abort_timeout_s()),
        ) as resp:
            if resp.status >= 400:
                body = await resp.text()
                logger.warning(
                    "[LibreChatLLM] Voice abort failed status=%s request_id=%s stream_id=%s body=%s",
                    resp.status,
                    request_id,
                    stream_id,
                    _summarize_error_for_log(body),
                )
                return
            if log_latency:
                logger.info(
                    "[VoiceLatency] abort_post_ms=%s request_id=%s stream_id=%s reason=%s",
                    int((time.time() - started_at) * 1000),
                    request_id,
                    stream_id,
                    reason,
                )
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.warning(
            "[LibreChatLLM] Voice abort request failed request_id=%s stream_id=%s error=%s",
            request_id,
            stream_id,
            _summarize_error_for_log(str(exc)),
        )


async def _shielded_abort_librechat_voice_stream(**kwargs: Any) -> None:
    abort_task = asyncio.create_task(_abort_librechat_voice_stream(**kwargs))
    try:
        await asyncio.shield(abort_task)
    except asyncio.CancelledError:
        current_task = asyncio.current_task()
        if current_task is not None and hasattr(current_task, "uncancel"):
            while current_task.cancelling():
                current_task.uncancel()
        try:
            await asyncio.shield(abort_task)
        finally:
            raise


class LibreChatLLM(llm.LLM):
    """
    A LiveKit Agents LLM implementation backed by LibreChat's voice gateway endpoints.
    """

    def __init__(
        self,
        *,
        origin: str,
        auth: LibreChatAuth,
        timeout_s: float = 120.0,
        voice_mode: bool = True,
        voice_provider: str = "cartesia",
        voice_accepts_inline_controls: bool = False,
        followup_handler: Optional[Callable[..., None]] = None,
        task_event_handler: Optional[Callable[[dict[str, Any]], Any]] = None,
        task_cancel_handler: Optional[Callable[[str, dict[str, Any]], Any]] = None,
        model_output_handler: Optional[Callable[[str], Any]] = None,
        is_participant_connected: Optional[Callable[[], bool]] = None,
        participant_reconnect_grace_s: float = 60.0,
    ) -> None:
        super().__init__()
        self._origin = origin.rstrip("/")
        self._auth = auth
        self._timeout_s = float(timeout_s)
        self._voice_mode = bool(voice_mode)
        self._voice_provider = voice_provider or "cartesia"
        self._voice_accepts_inline_controls = bool(voice_accepts_inline_controls)
        self._followup_handler = followup_handler
        self._task_event_handler = task_event_handler
        self._task_cancel_handler = task_cancel_handler
        self._model_output_handler = model_output_handler
        self._is_participant_connected = is_participant_connected
        self._participant_reconnect_grace_s = max(
            0.0, float(participant_reconnect_grace_s)
        )
        self._task_cancel_results: dict[str, dict[str, Any]] = {}
        self._task_cancel_lock = asyncio.Lock()
        self._sent_speaker_revisions: dict[tuple[str, int], None] = {}
        self._sent_speaker_session_states: dict[tuple[Any, ...], None] = {}
        self._speaker_revision_lock = asyncio.Lock()
        self._speaker_delivery_tasks: set[asyncio.Task[dict[str, Any]]] = set()
        self._speaker_delivery_closing = False
        self._sent_ambient_segments: dict[tuple[str, int], None] = {}
        self._ambient_ingress_lock = asyncio.Lock()
        self._current_trace_id = ""
        self._current_trace: Optional[VoiceHopTrace] = None
        self._traces_by_id: dict[str, VoiceHopTrace] = {}
        self._task_id_by_trace_id: dict[str, str] = {}
        self._summarized_trace_ids: dict[str, None] = {}
        self._trace_finalizers: dict[str, asyncio.TimerHandle] = {}
        self._background_continuations: set[asyncio.Task[None]] = set()
        self._continuations_by_task: dict[str, set[asyncio.Task[None]]] = {}
        self._seen_task_events: dict[tuple[Any, ...], None] = {}
        self._task_event_gate = _VoiceTaskEventGate()
        self._call_task_event_stream_task: Optional[asyncio.Task[None]] = None
        self._call_task_event_stream_session: Optional[aiohttp.ClientSession] = None
        self._call_task_event_stream_handshake: Optional[asyncio.Future[bool]] = None
        self._call_task_event_stream_health_handler: Optional[
            Callable[[dict[str, Any]], Any]
        ] = None
        self._call_task_event_stream_health: dict[str, Any] = {
            "version": 1,
            "callSessionId": self._auth.call_session_id,
            "state": "idle",
            "status": None,
            "retryable": False,
        }
        self._call_state_session: Optional[aiohttp.ClientSession] = None

    def is_participant_connected(self) -> bool:
        """Report whether the backend-claimed owner identity is currently in the room."""
        if self._is_participant_connected is None:
            return True
        try:
            return bool(self._is_participant_connected())
        except Exception:
            logger.warning(
                "[LibreChatLLM] Participant-state check failed; suppressing unaddressed speech",
                exc_info=True,
            )
            return False

    async def wait_for_participant_reconnect(self) -> bool:
        if self.is_participant_connected():
            return True
        deadline = time.monotonic() + self._participant_reconnect_grace_s
        while time.monotonic() < deadline:
            await asyncio.sleep(min(0.05, max(0.0, deadline - time.monotonic())))
            if self.is_participant_connected():
                return True
        return self.is_participant_connected()

    @property
    def current_trace_id(self) -> str:
        return self._current_trace_id

    @staticmethod
    def _remember_bounded_keys(
        target: dict[tuple[str, int], None],
        keys: Any,
        *,
        max_entries: int = 8_192,
    ) -> None:
        for key in keys:
            target[key] = None
        while len(target) > max_entries:
            target.pop(next(iter(target)))

    def record_current_trace_hop(self, hop: str, timestamp_ms: float) -> None:
        trace = self._current_trace
        if trace is None:
            return
        if trace.record(hop, timestamp_ms):
            logger.info("[VoiceHop] %s", trace.log_payload(hop))

    def register_trace(self, trace: VoiceHopTrace) -> None:
        self._current_trace_id = trace.correlation_id
        self._current_trace = trace
        self._traces_by_id[trace.correlation_id] = trace
        while len(self._traces_by_id) > 128:
            expired_id = next(iter(self._traces_by_id))
            self._traces_by_id.pop(expired_id)
            self._task_id_by_trace_id.pop(expired_id, None)

    def bind_trace_task(self, correlation_id: str, task_id: str) -> None:
        if correlation_id in self._traces_by_id and (task_id or "").strip():
            self._task_id_by_trace_id[correlation_id] = task_id.strip()

    def task_id_for_trace(self, correlation_id: str) -> str:
        return self._task_id_by_trace_id.get((correlation_id or "").strip(), "")

    def record_next_trace_hop(self, hop: str, timestamp_ms: float) -> str:
        """Correlate ordered single-session TTS/playout metrics without using transcript text."""
        if hop not in {"tts_first_byte", "audio_output"}:
            return ""
        for correlation_id, trace in self._traces_by_id.items():
            if correlation_id in self._summarized_trace_ids or trace.has(hop):
                continue
            if hop == "tts_first_byte" and not trace.has("first_model_token"):
                continue
            if hop == "audio_output" and not trace.has("tts_first_byte"):
                continue
            if trace.record(hop, timestamp_ms):
                logger.info("[VoiceHop] %s", trace.log_payload(hop))
                if hop == "audio_output":
                    self.finalize_trace_terminal(trace)
                return correlation_id
        return ""

    def log_current_trace_terminal_if_ready(self) -> None:
        trace = self._current_trace
        if (
            trace is None
            or trace.correlation_id in self._summarized_trace_ids
            or not trace.has("tts_first_byte")
            or not trace.has("audio_output")
        ):
            return
        self.finalize_trace_terminal(trace)

    def finalize_trace_terminal(
        self, trace: VoiceHopTrace
    ) -> Optional[dict[str, Any]]:
        finalizer = self._trace_finalizers.pop(trace.correlation_id, None)
        if finalizer is not None:
            finalizer.cancel()
        if trace.correlation_id in self._summarized_trace_ids:
            return None
        self._summarized_trace_ids[trace.correlation_id] = None
        while len(self._summarized_trace_ids) > 512:
            self._summarized_trace_ids.pop(next(iter(self._summarized_trace_ids)))
        summary = trace.terminal_summary(
            {
                "utterance_end->gateway_dispatch": 250.0,
                "gateway_dispatch->agent_start": 250.0,
                "tool_start->tool_end": 5_000.0,
                "tool_end->first_model_token": 1_000.0,
                "first_model_token->tts_first_byte": 1_500.0,
                "tts_first_byte->audio_output": 300.0,
            }
        )
        logger.info(
            "[VoiceHop] %s",
            json.dumps(summary, separators=(",", ":"), sort_keys=True),
        )
        return summary

    def schedule_trace_terminal(
        self, trace: VoiceHopTrace, *, grace_s: float = 5.0
    ) -> None:
        if trace.correlation_id in self._summarized_trace_ids:
            return

        if trace.correlation_id in self._trace_finalizers:
            return

        def _finalize_after_grace() -> None:
            self._trace_finalizers.pop(trace.correlation_id, None)
            self.finalize_trace_terminal(trace)

        self._trace_finalizers[trace.correlation_id] = (
            asyncio.get_running_loop().call_later(
                max(float(grace_s), 0.0),
                _finalize_after_grace,
            )
        )

    @staticmethod
    def _record_tool_hops_from_event(
        trace: VoiceHopTrace, event: dict[str, Any], *, timestamp_ms: float
    ) -> None:
        task_event = _extract_voice_task_event(event)
        if task_event is not None:
            phase = str(task_event.get("phase") or "")
            state = str(task_event.get("state") or "")
            if phase == "tool" and state in {"queued", "running", "recovering"}:
                if trace.record("tool_start", timestamp_ms):
                    logger.info("[VoiceHop] %s", trace.log_payload("tool_start"))
            elif trace.has("tool_start") and not trace.has("tool_end") and (
                phase == "tool_completed"
                or state
                in {
                    "completed",
                    "failed",
                    "cancelled_confirmed",
                    "cancelled_unenforceable",
                }
            ):
                if trace.record("tool_end", timestamp_ms):
                    logger.info("[VoiceHop] %s", trace.log_payload("tool_end"))
        event_type = event.get("event") or event.get("_sse_event")
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        step_details = (
            data.get("stepDetails") if isinstance(data.get("stepDetails"), dict) else {}
        )
        if event_type == "on_run_step" and (
            data.get("type") == "tool_calls"
            or step_details.get("type") == "tool_calls"
        ):
            status = data.get("status")
            if status in {None, "queued", "in_progress", "running"}:
                if trace.record("tool_start", timestamp_ms):
                    logger.info("[VoiceHop] %s", trace.log_payload("tool_start"))
            elif status in {"completed", "failed", "cancelled"}:
                if trace.record("tool_end", timestamp_ms):
                    logger.info("[VoiceHop] %s", trace.log_payload("tool_end"))
        elif (
            event_type == "on_run_step_completed"
            and trace.has("tool_start")
            and not trace.has("tool_end")
        ):
            if trace.record("tool_end", timestamp_ms):
                logger.info("[VoiceHop] %s", trace.log_payload("tool_end"))

    @property
    def model(self) -> str:
        return "librechat"

    @property
    def provider(self) -> str:
        return "viventium"

    def set_followup_handler(
        self, handler: Optional[Callable[..., None]]
    ) -> None:
        self._followup_handler = handler

    def set_task_event_handler(
        self, handler: Optional[Callable[[dict[str, Any]], Any]]
    ) -> None:
        self._task_event_handler = handler

    def set_task_cancel_handler(
        self, handler: Optional[Callable[[str, dict[str, Any]], Any]]
    ) -> None:
        self._task_cancel_handler = handler

    def set_call_task_event_stream_health_handler(
        self,
        handler: Optional[Callable[[dict[str, Any]], Any]],
    ) -> None:
        self._call_task_event_stream_health_handler = handler

    @property
    def call_task_event_stream_health(self) -> dict[str, Any]:
        return dict(self._call_task_event_stream_health)

    async def _report_call_task_event_stream_health(
        self,
        state: str,
        *,
        status: Optional[int] = None,
        retryable: bool = False,
    ) -> None:
        health = {
            "version": 1,
            "callSessionId": self._auth.call_session_id,
            "state": state,
            "status": status,
            "retryable": bool(retryable),
        }
        self._call_task_event_stream_health = health
        logger.info(
            "[VoiceTask] call_stream_health callSessionId=%s state=%s status=%s retryable=%s",
            self._auth.call_session_id,
            state,
            status,
            bool(retryable),
        )
        handler = self._call_task_event_stream_health_handler
        if handler is None:
            return
        try:
            result = handler(dict(health))
            if asyncio.iscoroutine(result):
                await result
        except Exception:
            # Health telemetry/control failures must fail the speech plane closed
            # at the worker handler, but may not tear down the authoritative SSE.
            logger.exception(
                "[VoiceTask] call_stream_health_handler_failed callSessionId=%s state=%s",
                self._auth.call_session_id,
                state,
            )

    def is_task_output_suppressed(self, task_id: str) -> bool:
        return self._task_event_gate.is_suppressed(task_id)

    def set_model_output_handler(
        self, handler: Optional[Callable[[str], Any]]
    ) -> None:
        self._model_output_handler = handler

    async def _relay_task_event_once(self, task_event: dict[str, Any]) -> bool:
        validated = _extract_voice_task_event(
            {"event": "voice_task_event", "voiceTaskEvent": task_event},
            expected_call_session_id=self._auth.call_session_id,
        )
        if validated is None:
            return False
        task_event = validated
        if not self._task_event_gate.accept(task_event):
            return False
        event_id = str(task_event.get("eventId") or "").strip()
        key: tuple[Any, ...] = (
            ("event", event_id)
            if event_id
            else (
                "sequence",
                task_event.get("taskId"),
                task_event.get("sequence"),
                task_event.get("state"),
            )
        )
        if key in self._seen_task_events:
            return False
        self._seen_task_events[key] = None
        while len(self._seen_task_events) > 4096:
            self._seen_task_events.pop(next(iter(self._seen_task_events)))
        if self._task_event_handler is not None:
            handler_result = self._task_event_handler(task_event)
            if asyncio.iscoroutine(handler_result):
                await handler_result
        return True

    def start_call_task_event_stream(
        self,
        *,
        reconnect_min_s: float = 0.25,
        reconnect_max_s: float = 5.0,
    ) -> Optional[asyncio.Task[None]]:
        """Start one call-lifetime authoritative task-event subscription.

        The normal generation SSE ends with the parent turn. This separate stream
        keeps child GlassHive tasks, retries, sources, and terminal snapshots live
        for the full claimed call without polling or consuming model/TTS deltas.
        """
        current = self._call_task_event_stream_task
        if current is not None and not current.done():
            return current
        if not all(
            (
                self._auth.call_session_id,
                self._auth.call_secret,
                self._auth.job_id,
                self._auth.worker_id,
            )
        ):
            logger.error(
                "[VoiceTask] call_stream_not_started callSessionId=%s reason=missing_job_auth",
                self._auth.call_session_id,
            )
            return None
        lower = min(max(float(reconnect_min_s), 0.01), 30.0)
        upper = min(max(float(reconnect_max_s), lower), 30.0)
        self._call_task_event_stream_handshake = (
            asyncio.get_running_loop().create_future()
        )
        task = asyncio.create_task(
            self._run_call_task_event_stream(
                reconnect_min_s=lower,
                reconnect_max_s=upper,
            ),
            name=f"viventium-call-task-events:{self._auth.call_session_id}",
        )
        self._call_task_event_stream_task = task

        def _consume(completed: asyncio.Task[None]) -> None:
            if self._call_task_event_stream_task is completed:
                self._call_task_event_stream_task = None
            if completed.cancelled():
                return
            try:
                completed.exception()
            except Exception:
                logger.warning(
                    "[VoiceTask] call_stream_cleanup_failed callSessionId=%s",
                    self._auth.call_session_id,
                    exc_info=True,
                )

        task.add_done_callback(_consume)
        return task

    async def wait_call_task_event_stream_ready(self, *, timeout_s: float) -> bool:
        handshake = self._call_task_event_stream_handshake
        if handshake is None:
            return False
        try:
            return bool(
                await asyncio.wait_for(
                    asyncio.shield(handshake),
                    timeout=max(float(timeout_s), 0.01),
                )
            )
        except asyncio.TimeoutError:
            return False

    async def _run_call_task_event_stream(
        self,
        *,
        reconnect_min_s: float,
        reconnect_max_s: float,
    ) -> None:
        url = f"{self._origin}/api/viventium/voice/tasks/events"
        headers = {
            "Accept": "text/event-stream",
            "X-VIVENTIUM-CALL-SESSION": self._auth.call_session_id,
            "X-VIVENTIUM-CALL-SECRET": self._auth.call_secret,
            "X-VIVENTIUM-JOB-ID": str(self._auth.job_id),
            "X-VIVENTIUM-WORKER-ID": str(self._auth.worker_id),
        }
        params = {"callSessionId": self._auth.call_session_id}
        delay_s = reconnect_min_s
        session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(
                total=None,
                connect=min(self._timeout_s, 10.0),
                sock_read=45.0,
            )
        )
        self._call_task_event_stream_session = session
        try:
            while True:
                received_valid_event = False
                try:
                    await self._report_call_task_event_stream_health(
                        "connecting",
                        retryable=True,
                    )
                    async with session.get(
                        url,
                        headers=headers,
                        params=params,
                    ) as response:
                        if response.status < 200 or response.status >= 300:
                            # Exact job ownership/auth failures cannot recover on this
                            # worker. Transient provider/load failures may reconnect.
                            if response.status < 500 and response.status != 429:
                                logger.warning(
                                    "[VoiceTask] call_stream_rejected callSessionId=%s status=%s reconnect=false",
                                    self._auth.call_session_id,
                                    response.status,
                                )
                                await self._report_call_task_event_stream_health(
                                    "terminal",
                                    status=response.status,
                                    retryable=False,
                                )
                                handshake = self._call_task_event_stream_handshake
                                if handshake is not None and not handshake.done():
                                    handshake.set_result(False)
                                return
                            logger.warning(
                                "[VoiceTask] call_stream_unavailable callSessionId=%s status=%s reconnect=true",
                                self._auth.call_session_id,
                                response.status,
                            )
                            await self._report_call_task_event_stream_health(
                                "disconnected",
                                status=response.status,
                                retryable=True,
                            )
                        else:
                            # Headers authenticate the stream, but the backend may
                            # still be replaying paginated durable snapshots.
                            await self._report_call_task_event_stream_health(
                                "syncing",
                                status=response.status,
                                retryable=False,
                            )
                            synchronized = False
                            async for event in iter_sse_json_events(content=response.content):
                                sync = _extract_voice_task_sync(
                                    event,
                                    expected_call_session_id=self._auth.call_session_id,
                                )
                                if sync is not None:
                                    if synchronized:
                                        continue
                                    synchronized = True
                                    received_valid_event = True
                                    await self._report_call_task_event_stream_health(
                                        "connected",
                                        status=response.status,
                                        retryable=False,
                                    )
                                    handshake = self._call_task_event_stream_handshake
                                    if handshake is not None and not handshake.done():
                                        handshake.set_result(True)
                                    continue
                                task_event = _extract_voice_task_event(
                                    event,
                                    expected_call_session_id=self._auth.call_session_id,
                                )
                                if task_event is None:
                                    continue
                                received_valid_event = True
                                await self._relay_task_event_once(task_event)
                            await self._report_call_task_event_stream_health(
                                "disconnected",
                                retryable=True,
                            )
                    if received_valid_event:
                        delay_s = reconnect_min_s
                except asyncio.CancelledError:
                    raise
                except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                    logger.warning(
                        "[VoiceTask] call_stream_disconnected callSessionId=%s error=%s reconnect=true",
                        self._auth.call_session_id,
                        type(exc).__name__,
                    )
                    await self._report_call_task_event_stream_health(
                        "disconnected",
                        retryable=True,
                    )
                except Exception as exc:
                    logger.error(
                        "[VoiceTask] call_stream_terminated callSessionId=%s error=%s reconnect=false",
                        self._auth.call_session_id,
                        type(exc).__name__,
                    )
                    await self._report_call_task_event_stream_health(
                        "terminal",
                        retryable=False,
                    )
                    return
                await asyncio.sleep(delay_s)
                delay_s = min(delay_s * 2.0, reconnect_max_s)
        finally:
            handshake = self._call_task_event_stream_handshake
            if handshake is not None and not handshake.done():
                handshake.set_result(False)
            if self._call_task_event_stream_session is session:
                self._call_task_event_stream_session = None
            if not getattr(session, "closed", False):
                await session.close()

    async def stop_call_task_event_stream(self) -> None:
        task = self._call_task_event_stream_task
        self._call_task_event_stream_task = None
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        session = self._call_task_event_stream_session
        self._call_task_event_stream_session = None
        if session is not None and not getattr(session, "closed", False):
            await session.close()
        await self._report_call_task_event_stream_health(
            "stopped",
            retryable=False,
        )

    def _start_task_continuation(
        self,
        *,
        stream_id: str,
        task_id: str,
        headers: dict[str, str],
        request_id: str,
        pending_insights: list[dict[str, Any]],
        saw_cortex_event: bool,
        saw_glasshive_tool_call: bool,
        cortex_message_id: str,
        hop_trace: VoiceHopTrace,
    ) -> None:
        task = asyncio.create_task(
            self._continue_task_stream(
                stream_id=stream_id,
                task_id=task_id,
                headers=headers,
                request_id=request_id,
                pending_insights=list(pending_insights),
                saw_cortex_event=saw_cortex_event,
                saw_glasshive_tool_call=saw_glasshive_tool_call,
                cortex_message_id=cortex_message_id,
                hop_trace=hop_trace,
            )
        )
        self._background_continuations.add(task)
        self._continuations_by_task.setdefault(task_id, set()).add(task)

        def _discard(completed: asyncio.Task[None]) -> None:
            self._background_continuations.discard(completed)
            task_set = self._continuations_by_task.get(task_id)
            if task_set is not None:
                task_set.discard(completed)
                if not task_set:
                    self._continuations_by_task.pop(task_id, None)

        task.add_done_callback(_discard)

    async def _continue_task_stream(
        self,
        *,
        stream_id: str,
        task_id: str,
        headers: dict[str, str],
        request_id: str,
        pending_insights: list[dict[str, Any]],
        saw_cortex_event: bool,
        saw_glasshive_tool_call: bool,
        cortex_message_id: str,
        hop_trace: VoiceHopTrace,
    ) -> None:
        final_event: Optional[dict[str, Any]] = None
        suppress_task_output = False
        sse_url = f"{self._origin}/api/viventium/voice/stream/{stream_id}"
        max_retries, retry_delay_s = _get_voice_sse_retry_config()
        attempts = 0
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self._timeout_s)
            ) as session:
                while attempts <= max_retries and final_event is None:
                    try:
                        async with session.get(
                            sse_url,
                            headers=headers,
                            params={"resume": "true"},
                        ) as response:
                            if response.status >= 400:
                                break
                            async for event in iter_sse_json_events(content=response.content):
                                self._record_tool_hops_from_event(
                                    hop_trace,
                                    event,
                                    timestamp_ms=time.time() * 1000.0,
                                )
                                if event.get("sync"):
                                    continue
                                task_event = _extract_voice_task_event(
                                    event,
                                    expected_call_session_id=self._auth.call_session_id,
                                )
                                if task_event is not None:
                                    await self._relay_task_event_once(task_event)
                                    if (
                                        task_event.get("taskId") == task_id
                                        and task_event.get("state")
                                        in _VOICE_TASK_SUPPRESSING_STATES
                                    ):
                                        suppress_task_output = True
                                    continue
                                if _payload_has_glasshive_tool_call(event):
                                    saw_glasshive_tool_call = True
                                message_id_candidate = extract_cortex_message_id(event)
                                if message_id_candidate:
                                    cortex_message_id = message_id_candidate
                                if event.get("event") in (
                                    "on_cortex_update",
                                    "on_cortex_followup",
                                ):
                                    saw_cortex_event = True
                                    insight = extract_cortex_insight(event)
                                    if insight:
                                        pending_insights.append(insight)
                                    continue
                                if event.get("final"):
                                    final_event = event
                                    break
                        if final_event is not None:
                            break
                    except (aiohttp.ClientError, asyncio.TimeoutError):
                        pass
                    attempts += 1
                    if attempts <= max_retries:
                        await asyncio.sleep(retry_delay_s)

            message_id = (
                _extract_final_response_message_id(final_event)
                if final_event is not None
                else ""
            ) or cortex_message_id
            if (
                message_id
                and self._followup_handler
                and not suppress_task_output
                and not self.is_task_output_suppressed(task_id)
            ):
                self._followup_handler(
                    message_id,
                    pending_insights,
                    "",
                    cortex_expected=saw_cortex_event,
                    glasshive_expected=saw_glasshive_tool_call,
                )
            logger.info(
                "[VoiceTask] detached_continuation_finished callSessionId=%s requestId=%s streamId=%s taskId=%s final=%s attempts=%s",
                self._auth.call_session_id,
                request_id,
                stream_id,
                task_id,
                bool(final_event),
                attempts + 1,
            )
        except asyncio.CancelledError:
            logger.info(
                "[VoiceTask] detached_continuation_cancelled callSessionId=%s requestId=%s streamId=%s taskId=%s",
                self._auth.call_session_id,
                request_id,
                stream_id,
                task_id,
            )
            raise

    async def wait_for_background_continuations(self, *, timeout_s: float = 5.0) -> None:
        tasks = list(self._background_continuations)
        if not tasks:
            return
        await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=max(float(timeout_s), 0.01),
        )

    async def close_background_continuations(self) -> None:
        await self.stop_call_task_event_stream()
        self._speaker_delivery_closing = True
        speaker_tasks = list(self._speaker_delivery_tasks)
        if speaker_tasks:
            _done, pending = await asyncio.wait(speaker_tasks, timeout=0.5)
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
        for finalizer in self._trace_finalizers.values():
            finalizer.cancel()
        self._trace_finalizers.clear()
        tasks = list(self._background_continuations)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        call_state_session = self._call_state_session
        self._call_state_session = None
        if call_state_session is not None and not getattr(call_state_session, "closed", False):
            await call_state_session.close()

    async def get_call_state(self) -> Optional[dict[str, Any]]:
        """Read one strict authoritative state over a reused bounded HTTP connection."""
        headers = {
            "X-VIVENTIUM-CALL-SESSION": self._auth.call_session_id,
            "X-VIVENTIUM-CALL-SECRET": self._auth.call_secret,
        }
        if self._auth.job_id:
            headers["X-VIVENTIUM-JOB-ID"] = self._auth.job_id
        if self._auth.worker_id:
            headers["X-VIVENTIUM-WORKER-ID"] = self._auth.worker_id
        url = (
            f"{self._origin}/api/viventium/voice/call-sessions/"
            f"{quote(self._auth.call_session_id, safe='')}/state"
        )
        started_at = time.monotonic()
        try:
            session = self._call_state_session
            if session is None or getattr(session, "closed", False):
                session = aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=min(self._timeout_s, 0.2))
                )
                self._call_state_session = session
            async with session.get(url, headers=headers) as resp:
                if resp.status >= 400:
                    logger.warning(
                        "[VoiceMode] state_unavailable callSessionId=%s status=%s durationMs=%.3f",
                        self._auth.call_session_id,
                        resp.status,
                        (time.monotonic() - started_at) * 1000.0,
                    )
                    return None
                payload = await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, TypeError) as exc:
            logger.warning(
                "[VoiceMode] state_lookup_failed callSessionId=%s error=%s durationMs=%.3f",
                self._auth.call_session_id,
                type(exc).__name__,
                (time.monotonic() - started_at) * 1000.0,
            )
            return None
        if not isinstance(payload, dict):
            return None
        response_call_session_id = payload.get("callSessionId")
        revision = payload.get("revision")
        updated_at = payload.get("updatedAt")
        status = payload.get("status")
        try:
            parsed_updated_at = datetime.fromisoformat(
                str(updated_at).replace("Z", "+00:00")
            )
        except (TypeError, ValueError):
            parsed_updated_at = None
        if (
            payload.get("version") != 1
            or response_call_session_id != self._auth.call_session_id
            or not isinstance(revision, int)
            or isinstance(revision, bool)
            or revision < 0
            or parsed_updated_at is None
            or parsed_updated_at.tzinfo is None
            or not isinstance(status, str)
            or status not in {
                "created",
                "connecting",
                "listening",
                "speaking",
                "working",
                "needs_input",
                "degraded",
                "ended",
                "failed",
            }
        ):
            logger.warning(
                "[VoiceMode] state_rejected callSessionId=%s reason=invalid_contract",
                self._auth.call_session_id,
            )
            return None
        mode = payload.get("mode")
        if mode in {"call", "wing", "listen_only"}:
            return {
                "version": 1,
                "callSessionId": self._auth.call_session_id,
                "mode": str(mode),
                "status": status,
                "revision": revision,
                "updatedAt": updated_at,
            }
        return None

    async def get_call_mode(self) -> Optional[str]:
        """Compatibility projection for callers that only need the active mode."""
        state = await self.get_call_state()
        if state is None or state.get("status") in {"ended", "failed"}:
            return None
        return str(state["mode"])

    async def cancel_task(self, task_id: str, *, reason: str = "user_requested") -> dict[str, Any]:
        """Explicitly cancel one authoritative backend task, idempotently.

        LiveKit TTS interruption and stream disposal intentionally do not call this method.
        """
        normalized_task_id = (task_id or "").strip()
        if not normalized_task_id:
            raise ValueError("task_id is required")
        async with self._task_cancel_lock:
            cached = self._task_cancel_results.get(normalized_task_id)
            if cached is not None:
                return cached
            headers = {
                "Content-Type": "application/json",
                "X-VIVENTIUM-CALL-SESSION": self._auth.call_session_id,
                "X-VIVENTIUM-CALL-SECRET": self._auth.call_secret,
            }
            if self._auth.job_id:
                headers["X-VIVENTIUM-JOB-ID"] = self._auth.job_id
            if self._auth.worker_id:
                headers["X-VIVENTIUM-WORKER-ID"] = self._auth.worker_id
            url = (
                f"{self._origin}/api/viventium/voice/tasks/"
                f"{quote(normalized_task_id, safe='')}/cancel"
            )
            started_at = time.monotonic()
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=min(self._timeout_s, 10.0))
            ) as session:
                async with session.post(
                    url,
                    headers=headers,
                    json={"reason": reason or "user_requested"},
                ) as resp:
                    if resp.status >= 400:
                        body = await resp.text()
                        raise RuntimeError(
                            f"LibreChat voice task cancel failed: {resp.status} "
                            f"{_summarize_error_for_log(body)}"
                        )
                    result = await resp.json()
                    if not isinstance(result, dict):
                        result = {"version": 1, "taskId": normalized_task_id, "state": "cancelling"}
            self._task_cancel_results[normalized_task_id] = result
            while len(self._task_cancel_results) > 4_096:
                self._task_cancel_results.pop(next(iter(self._task_cancel_results)))
            self._task_event_gate.mark_cancel_accepted(normalized_task_id)
            for continuation in list(
                self._continuations_by_task.get(normalized_task_id, set())
            ):
                continuation.cancel()
            if self._task_cancel_handler is not None:
                handler_result = self._task_cancel_handler(normalized_task_id, result)
                if asyncio.iscoroutine(handler_result):
                    await handler_result
            logger.info(
                "[VoiceTask] explicit_cancel_requested callSessionId=%s taskId=%s durationMs=%.3f",
                self._auth.call_session_id,
                normalized_task_id,
                (time.monotonic() - started_at) * 1000.0,
            )
            return result

    async def post_speaker_segment_revisions(
        self,
        revisions: list[dict[str, Any]],
        *,
        session_state: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Persist call-wide safety state first, then bounded idempotent revision pages."""
        valid = [
            item
            for item in revisions
            if isinstance(item, dict)
            and item.get("version") == 1
            and item.get("callSessionId") == self._auth.call_session_id
            and isinstance(item.get("segmentId"), str)
            and isinstance(item.get("revision"), int)
            and not isinstance(item.get("revision"), bool)
        ]
        if not valid and session_state is None:
            return {"version": 1, "accepted": [], "ignored": []}
        async with self._speaker_revision_lock:
            unsent = [
                item
                for item in valid
                if (item["segmentId"], item["revision"])
                not in self._sent_speaker_revisions
            ]
            if not unsent and session_state is None:
                return {"version": 1, "accepted": [], "ignored": []}
            headers = {
                "Content-Type": "application/json",
                "X-VIVENTIUM-CALL-SESSION": self._auth.call_session_id,
                "X-VIVENTIUM-CALL-SECRET": self._auth.call_secret,
            }
            if self._auth.job_id:
                headers["X-VIVENTIUM-JOB-ID"] = self._auth.job_id
            if self._auth.worker_id:
                headers["X-VIVENTIUM-WORKER-ID"] = self._auth.worker_id
            started_at = time.monotonic()
            shared_revisions = [
                item
                for item in unsent
                if item.get("speaker", {}).get("actorTrust")
                == "shared_mic_unverified"
            ]
            if shared_revisions and session_state is None:
                first_speaker = shared_revisions[0].get("speaker", {})
                session_state = {
                    "version": 1,
                    "callSessionId": self._auth.call_session_id,
                    "revision": 1,
                    "attributionState": "shared_mic_unverified",
                    "detectedAt": datetime.now(timezone.utc).isoformat().replace(
                        "+00:00", "Z"
                    ),
                    **(
                        {
                            "sourceTrackSid": str(first_speaker.get("trackSid")),
                            "sharedTrackSids": [str(first_speaker.get("trackSid"))],
                        }
                        if first_speaker.get("trackSid")
                        else {}
                    ),
                    **(
                        {
                            "sourceParticipantIdentity": str(
                                first_speaker.get("participantIdentity")
                            ),
                            "sharedParticipantIdentities": [
                                str(first_speaker.get("participantIdentity"))
                            ],
                        }
                        if first_speaker.get("participantIdentity")
                        else {}
                    ),
                }

            accepted: list[str] = []
            ignored: list[str] = []
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=min(self._timeout_s, 10.0))
            ) as session:
                if session_state is not None:
                    await self._persist_speaker_session_state(
                        session=session,
                        headers=headers,
                        state=session_state,
                    )
                if not unsent:
                    return {"version": 1, "accepted": [], "ignored": []}
                for page in self._speaker_revision_pages(unsent):
                    body = {
                        "speakerSegmentRevisions": page,
                        "ownerParticipantIdentity": str(
                            page[0].get("speaker", {}).get("participantIdentity") or ""
                        ),
                        "ownerTrackSid": str(
                            page[0].get("speaker", {}).get("trackSid") or ""
                        ),
                    }
                    result = await self._post_voice_json_with_retry(
                        session=session,
                        url=(
                            f"{self._origin}/api/viventium/voice/"
                            "speaker-segments/revisions"
                        ),
                        headers=headers,
                        body=body,
                        operation="speaker revision",
                    )
                    accepted.extend(
                        item for item in result.get("accepted", []) if isinstance(item, str)
                    )
                    ignored.extend(
                        item for item in result.get("ignored", []) if isinstance(item, str)
                    )
                    self._remember_bounded_keys(
                        self._sent_speaker_revisions,
                        (
                            (item["segmentId"], item["revision"])
                            for item in page
                        ),
                    )
            logger.info(
                "[VoiceSpeaker] revisions_persisted callSessionId=%s count=%s pages=%s durationMs=%.3f",
                self._auth.call_session_id,
                len(unsent),
                len(self._speaker_revision_pages(unsent)),
                (time.monotonic() - started_at) * 1000.0,
            )
            return {"version": 1, "accepted": accepted, "ignored": ignored}

    def queue_speaker_segment_revisions(
        self,
        revisions: list[dict[str, Any]],
        *,
        session_state: Optional[dict[str, Any]] = None,
    ) -> asyncio.Task[dict[str, Any]]:
        """Supervise retrying delivery so late safety revisions survive caller interruption."""
        async def _deliver_for_call_lifetime() -> dict[str, Any]:
            retry_round = 0
            while True:
                try:
                    return await self.post_speaker_segment_revisions(
                        revisions,
                        session_state=session_state,
                    )
                except _NonRetryableVoiceIngressError:
                    raise
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    if self._speaker_delivery_closing:
                        raise
                    retry_round += 1
                    logger.warning(
                        "[VoiceSpeaker] revision_delivery_retry callSessionId=%s round=%s error=%s memoryFailClosed=true",
                        self._auth.call_session_id,
                        retry_round,
                        type(exc).__name__,
                    )
                    await asyncio.sleep(min(0.25 * (2 ** min(retry_round, 5)), 5.0))

        task = asyncio.create_task(_deliver_for_call_lifetime())
        self._speaker_delivery_tasks.add(task)

        def _delivery_finished(completed: asyncio.Task[dict[str, Any]]) -> None:
            self._speaker_delivery_tasks.discard(completed)
            if completed.cancelled():
                return
            try:
                completed.result()
            except Exception as exc:
                logger.warning(
                    "[VoiceSpeaker] revision_delivery_failed callSessionId=%s error=%s memoryFailClosed=true",
                    self._auth.call_session_id,
                    type(exc).__name__,
                )

        task.add_done_callback(_delivery_finished)
        return task

    @staticmethod
    def _speaker_revision_pages(
        revisions: list[dict[str, Any]],
        *,
        max_items: int = 64,
        max_bytes: int = 128_000,
    ) -> list[list[dict[str, Any]]]:
        pages: list[list[dict[str, Any]]] = []
        current: list[dict[str, Any]] = []
        for item in revisions:
            candidate = [*current, item]
            candidate_size = len(
                json.dumps(
                    {"speakerSegmentRevisions": candidate},
                    ensure_ascii=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            )
            if current and (len(candidate) > max_items or candidate_size >= max_bytes):
                pages.append(current)
                current = [item]
            else:
                current = candidate
        if current:
            pages.append(current)
        return pages

    async def _persist_speaker_session_state(
        self,
        *,
        session: aiohttp.ClientSession,
        headers: dict[str, str],
        state: dict[str, Any],
    ) -> None:
        valid_state = (
            isinstance(state, dict)
            and state.get("version") == 1
            and state.get("callSessionId") == self._auth.call_session_id
            and isinstance(state.get("revision"), int)
            and not isinstance(state.get("revision"), bool)
            and state.get("revision") >= 1
            and state.get("attributionState") == "shared_mic_unverified"
            and isinstance(state.get("detectedAt"), str)
            and bool(state.get("detectedAt").strip())
        )
        if not valid_state:
            raise ValueError("invalid SpeakerSessionStateV1 shared-mic tombstone")
        shared_track_sids = tuple(
            sorted(
                {
                    value.strip()
                    for value in state.get("sharedTrackSids", [])
                    if isinstance(value, str) and value.strip()
                }
            )
        )
        source_track_sid = str(state.get("sourceTrackSid") or "").strip()
        shared_participant_identities = tuple(
            sorted(
                {
                    value.strip()
                    for value in state.get("sharedParticipantIdentities", [])
                    if isinstance(value, str) and value.strip()
                }
            )
        )
        source_participant_identity = str(
            state.get("sourceParticipantIdentity") or ""
        ).strip()
        key = (
            self._auth.call_session_id,
            int(state["revision"]),
            shared_track_sids,
            source_track_sid,
            shared_participant_identities,
            source_participant_identity,
        )
        if key in self._sent_speaker_session_states:
            return
        await self._post_voice_json_with_retry(
            session=session,
            url=f"{self._origin}/api/viventium/voice/speaker-session-state",
            headers=headers,
            body=state,
            operation="speaker session state",
        )
        self._remember_bounded_keys(self._sent_speaker_session_states, [key])

    async def _post_voice_json_with_retry(
        self,
        *,
        session: aiohttp.ClientSession,
        url: str,
        headers: dict[str, str],
        body: dict[str, Any],
        operation: str,
    ) -> dict[str, Any]:
        last_error: Optional[BaseException] = None
        for attempt in range(3):
            try:
                async with session.post(url, headers=headers, json=body) as resp:
                    if resp.status >= 500:
                        if attempt < 2:
                            await asyncio.sleep(0.1 * (2**attempt))
                            continue
                        error_body = await resp.text()
                        raise _RetryableVoiceIngressError(
                            f"LibreChat {operation} temporarily unavailable: {resp.status} "
                            f"{_summarize_error_for_log(error_body)}"
                        )
                    if resp.status >= 400:
                        error_body = await resp.text()
                        raise _NonRetryableVoiceIngressError(
                            f"LibreChat {operation} post failed: {resp.status} "
                            f"{_summarize_error_for_log(error_body)}"
                        )
                    parsed = await resp.json()
                    return parsed if isinstance(parsed, dict) else {}
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                last_error = exc
                if attempt < 2:
                    await asyncio.sleep(0.1 * (2**attempt))
                    continue
        if last_error is not None:
            raise last_error
        raise RuntimeError(f"LibreChat {operation} post failed")

    async def post_ambient_transcript(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Persist guest-track speech as bounded, idempotent soft evidence only."""
        raw_segments = payload.get("segments")
        segments = [
            item
            for item in (raw_segments if isinstance(raw_segments, list) else [])[:32]
            if isinstance(item, dict)
            and item.get("version") == 1
            and item.get("callSessionId") == self._auth.call_session_id
            and isinstance(item.get("segmentId"), str)
            and isinstance(item.get("revision"), int)
        ]
        if not segments:
            return {"version": 1, "accepted": [], "ignored": []}
        async with self._ambient_ingress_lock:
            unsent = [
                item
                for item in segments
                if (item["segmentId"], item["revision"]) not in self._sent_ambient_segments
            ]
            if not unsent:
                return {"version": 1, "accepted": [], "ignored": []}
            bounded_segments: list[dict[str, Any]] = []
            total_chars = 0
            for item in unsent:
                item_chars = len(str(item.get("text") or ""))
                if total_chars + item_chars > 64_000:
                    break
                bounded_segments.append(item)
                total_chars += item_chars
            if not bounded_segments:
                raise ValueError("ambient transcript exceeds bounded request size")
            ingress_kind = str(payload.get("ingressKind") or "ambient_participant")
            if ingress_kind not in {"ambient_participant", "listen_only_owner"}:
                raise ValueError("unsupported ambient ingress kind")
            mode = str(payload.get("mode") or "call")
            if mode not in {"call", "wing", "listen_only"}:
                mode = "call"
            body = {
                "version": 1,
                "callSessionId": self._auth.call_session_id,
                "ingressKind": ingress_kind,
                "segments": bounded_segments,
            }
            if ingress_kind == "ambient_participant":
                body["mode"] = mode
            for optional_key in ("conversationId", "turnId"):
                value = payload.get(optional_key)
                if isinstance(value, str) and value.strip():
                    body[optional_key] = value.strip()
            headers = {
                "Content-Type": "application/json",
                "X-VIVENTIUM-CALL-SESSION": self._auth.call_session_id,
                "X-VIVENTIUM-CALL-SECRET": self._auth.call_secret,
            }
            if self._auth.job_id:
                headers["X-VIVENTIUM-JOB-ID"] = self._auth.job_id
            if self._auth.worker_id:
                headers["X-VIVENTIUM-WORKER-ID"] = self._auth.worker_id
            url = f"{self._origin}/api/viventium/voice/ambient-transcript"
            started_at = time.monotonic()
            result: dict[str, Any] = {}
            for attempt in range(2):
                try:
                    async with aiohttp.ClientSession(
                        timeout=aiohttp.ClientTimeout(total=min(self._timeout_s, 10.0))
                    ) as session:
                        async with session.post(url, headers=headers, json=body) as resp:
                            if resp.status >= 500 and attempt == 0:
                                await asyncio.sleep(0.1)
                                continue
                            if resp.status >= 400:
                                error_body = await resp.text()
                                raise RuntimeError(
                                    f"LibreChat ambient ingress failed: {resp.status} "
                                    f"{_summarize_error_for_log(error_body)}"
                                )
                            parsed = await resp.json()
                            result = parsed if isinstance(parsed, dict) else {}
                            break
                except (aiohttp.ClientError, asyncio.TimeoutError):
                    if attempt == 0:
                        await asyncio.sleep(0.1)
                        continue
                    raise
            self._remember_bounded_keys(
                self._sent_ambient_segments,
                (
                    (item["segmentId"], item["revision"])
                    for item in bounded_segments
                ),
            )
            logger.info(
                "[VoiceSpeaker] ambient_persisted callSessionId=%s segments=%s chars=%s durationMs=%.3f",
                self._auth.call_session_id,
                len(bounded_segments),
                total_chars,
                (time.monotonic() - started_at) * 1000.0,
            )
            return result or {
                "version": 1,
                "accepted": [item["segmentId"] for item in bounded_segments],
                "ignored": [],
            }

    # === VIVENTIUM START ===
    # Feature: allow worker to override voice provider after TTS fallbacks.
    def set_voice_provider(
        self,
        provider: str,
        *,
        accepts_inline_voice_controls: Optional[bool] = None,
    ) -> None:
        value = (provider or "").strip()
        if value:
            self._voice_provider = value
        if accepts_inline_voice_controls is not None:
            self._voice_accepts_inline_controls = bool(accepts_inline_voice_controls)
    # === VIVENTIUM END ===

    def chat(
        self,
        *,
        chat_ctx: ChatContext,
        tools: list[FunctionTool | RawFunctionTool] | None = None,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
        parallel_tool_calls: NotGivenOr[bool] = NOT_GIVEN,
        tool_choice: NotGivenOr[ToolChoice] = NOT_GIVEN,
        extra_kwargs: NotGivenOr[dict[str, Any]] = NOT_GIVEN,
    ) -> llm.LLMStream:
        if tools:
            # Voice gateway does not currently support function tools from LiveKit -> LibreChat.
            # LibreChat tools are handled server-side by its agents pipeline, so we ignore them.
            tools = []

        return _LibreChatLLMStream(
            self,
            chat_ctx=chat_ctx,
            tools=[],
            conn_options=conn_options,
            origin=self._origin,
            auth=self._auth,
            timeout_s=self._timeout_s,
        )


class _LibreChatLLMStream(llm.LLMStream):
    def __init__(
        self,
        llm_impl: LibreChatLLM,
        *,
        chat_ctx: ChatContext,
        tools: list[FunctionTool | RawFunctionTool],
        conn_options: APIConnectOptions,
        origin: str,
        auth: LibreChatAuth,
        timeout_s: float,
    ) -> None:
        super().__init__(llm_impl, chat_ctx=chat_ctx, tools=tools, conn_options=conn_options)
        # === VIVENTIUM START ===
        # Feature: retain parent LLM config for voiceMode payloads.
        self._llm_impl = llm_impl
        # === VIVENTIUM END ===
        self._origin = origin
        self._auth = auth
        self._timeout_s = timeout_s
        self._request_id = f"lc_{uuid.uuid4().hex[:12]}"

    async def _run(self) -> None:
        user_text = _extract_last_user_text(self._chat_ctx)
        speaker_context = _extract_last_user_speaker_context(self._chat_ctx)
        speaker_post_context = {
            key: value
            for key, value in speaker_context.items()
            if key != "utteranceEndAtMs"
        }
        hop_trace = VoiceHopTrace(
            correlation_id=self._request_id,
            call_session_id=self._auth.call_session_id,
        )
        self._llm_impl.register_trace(hop_trace)
        utterance_end_ms = speaker_context.get("utteranceEndAtMs")
        if isinstance(utterance_end_ms, (int, float)):
            hop_trace.record("utterance_end", float(utterance_end_ms))
            logger.info("[VoiceHop] %s", hop_trace.log_payload("utterance_end"))

        if not user_text:
            # Nothing to do; emit no tokens.
            return

        headers = {
            "Content-Type": "application/json",
            "X-VIVENTIUM-CALL-SESSION": self._auth.call_session_id,
            "X-VIVENTIUM-CALL-SECRET": self._auth.call_secret,
            "X-VIVENTIUM-REQUEST-ID": self._request_id,
        }
        if self._auth.job_id:
            headers["X-VIVENTIUM-JOB-ID"] = self._auth.job_id
        if self._auth.worker_id:
            headers["X-VIVENTIUM-WORKER-ID"] = self._auth.worker_id

        chat_url = f"{self._origin}/api/viventium/voice/chat"
        stream_id: Optional[str] = None
        task_id: Optional[str] = None
        final_event: Optional[dict[str, Any]] = None
        stream_error: Optional[str] = None
        pending_insights: list[dict[str, Any]] = []
        saw_cortex_event = False
        saw_glasshive_tool_call = False
        cortex_message_id = ""

        log_latency = _should_log_latency()
        started_at = time.time()
        post_sent_at: Optional[float] = None
        first_token_at: Optional[float] = None

        timeout = aiohttp.ClientTimeout(total=self._timeout_s)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                # 1) Start resumable generation
                hop_trace.record("gateway_dispatch", time.time() * 1000.0)
                logger.info("[VoiceHop] %s", hop_trace.log_payload("gateway_dispatch"))
                async with session.post(
                    chat_url,
                    headers=headers,
                    json={
                        "text": user_text,
                        "streamId": self._request_id,
                        "voiceMode": self._llm_impl._voice_mode,
                        "voiceProvider": self._llm_impl._voice_provider,
                        # Normalize cumulative/snapshot-shaped text at LibreChat's stream boundary
                        # before SSE fan-out, resumable storage, and Mongo aggregation.
                        "viventiumTextDeltaMode": "auto",
                        # Ensure surface-aware prompt rules apply for voice calls.
                        "viventiumInputMode": "voice_call",
                        "viventiumSurface": "voice",
                        **speaker_post_context,
                    },
                ) as resp:
                    if resp.status >= 400:
                        body = await resp.text()
                        raise RuntimeError(f"LibreChat voice chat failed: {resp.status} {body}")
                    payload = await resp.json()
                    # === VIVENTIUM START ===
                    # Feature: Listen-Only Mode
                    # Purpose: The voice route can save the transcript and intentionally return no
                    # stream; LiveKit should emit no assistant tokens or TTS.
                    if payload.get("listenOnly") is True or payload.get("status") == "listen_only":
                        if log_latency:
                            logger.info(
                                "[VoiceLatency] listen_only_saved_ms=%s request_id=%s stream_id=%s",
                                int((time.time() - started_at) * 1000),
                                self._request_id,
                                payload.get("streamId") or "",
                            )
                        return
                    # === VIVENTIUM END ===
                    stream_id = payload.get("streamId")
                    task_id_value = payload.get("taskId")
                    if isinstance(task_id_value, str) and task_id_value.strip():
                        task_id = task_id_value.strip()
                        self._llm_impl.bind_trace_task(self._request_id, task_id)
                    hop_trace.record("agent_start", time.time() * 1000.0)
                    logger.info("[VoiceHop] %s", hop_trace.log_payload("agent_start"))
                    post_sent_at = time.time()
                    if log_latency:
                        logger.info(
                            "[VoiceLatency] chat_post_ms=%s request_id=%s stream_id=%s",
                            int((post_sent_at - started_at) * 1000),
                            self._request_id,
                            stream_id or "",
                        )

                if not isinstance(stream_id, str) or not stream_id:
                    raise RuntimeError("LibreChat voice chat returned no streamId")

                # 2) Subscribe to SSE stream and forward message deltas
                sse_url = f"{self._origin}/api/viventium/voice/stream/{stream_id}"

                saw_any_tokens = False
                first = True
                # === VIVENTIUM START ===
                max_retries, retry_delay_s = _get_voice_sse_retry_config()
                # === VIVENTIUM END ===

                # Track cortex insights that arrive during streaming (background cortices)
                suppress_task_output = False

                def _output_is_suppressed() -> bool:
                    return bool(
                        suppress_task_output
                        or (task_id and self._llm_impl.is_task_output_suppressed(task_id))
                    )
                collected_response: list[str] = []
                collected_raw_response: list[str] = []
                # === VIVENTIUM START ===
                # Guard against `{NTA}` flashing during streaming.
                no_response_guard = _NoResponseStreamGuard()
                tts_delta_buffer = _VoiceTtsDeltaBuffer(
                    sanitize_chunk=lambda text: sanitize_voice_tts_text(
                        text,
                        preserve_leading_space=text[:1].isspace(),
                        preserve_trailing_space=text[-1:].isspace(),
                        allow_voice_controls=self._llm_impl._voice_accepts_inline_controls,
                    )
                )
                debug_display_filter = VoiceControlDisplayFilter()
                # === VIVENTIUM END ===
                # === VIVENTIUM START ===
                # Keep the canonical assistant messageId from cortex updates as a follow-up fallback.
                # === VIVENTIUM END ===

                disconnected_speech: list[str] = []

                def emit_chat_delta(content: str) -> None:
                    nonlocal first
                    if not content or _output_is_suppressed():
                        return
                    if _should_debug_voice_markup():
                        logger.info(
                            "[VoiceMarkup] tts_emit chunk_json=%s",
                            _debug_text_json(content),
                        )
                    cd = ChoiceDelta(
                        role="assistant" if first else None,
                        content=content,
                    )
                    first = False
                    self._event_ch.send_nowait(ChatChunk(id=self._request_id, delta=cd))

                def send_chat_delta(content: str) -> None:
                    if not content:
                        return
                    if _output_is_suppressed():
                        disconnected_speech.clear()
                        return
                    if not self._llm_impl.is_participant_connected():
                        disconnected_speech.append(content)
                        return
                    if disconnected_speech:
                        content = "".join(disconnected_speech) + content
                        disconnected_speech.clear()
                    emit_chat_delta(content)

                async def flush_disconnected_speech() -> None:
                    if not disconnected_speech:
                        return
                    if _output_is_suppressed():
                        disconnected_speech.clear()
                        return
                    if not self._llm_impl.is_participant_connected():
                        reconnected = await self._llm_impl.wait_for_participant_reconnect()
                        if not reconnected:
                            logger.info(
                                "[LibreChatLLM] Reconnect grace expired; persisted voice response was not replayed"
                            )
                            disconnected_speech.clear()
                            return
                    if _output_is_suppressed():
                        disconnected_speech.clear()
                        return
                    content = "".join(disconnected_speech)
                    disconnected_speech.clear()
                    emit_chat_delta(content)

                async def process_text_delta(raw_delta: str) -> None:
                    nonlocal saw_any_tokens, first_token_at
                    collected_raw_response.append(raw_delta)
                    if _output_is_suppressed():
                        return
                    delta = sanitize_voice_delta_text(raw_delta)
                    if not delta:
                        return
                    if _should_debug_voice_markup():
                        display_delta = debug_display_filter.feed(delta)
                        logger.info(
                            "[VoiceMarkup] llm_delta stream_delta_json=%s tts_delta_json=%s display_delta_json=%s",
                            _debug_text_json(raw_delta),
                            _debug_text_json(delta),
                            _debug_text_json(display_delta),
                        )
                    saw_any_tokens = True
                    if first_token_at is None:
                        first_token_at = time.time()
                        hop_trace.record("first_model_token", first_token_at * 1000.0)
                        logger.info(
                            "[VoiceHop] %s",
                            hop_trace.log_payload("first_model_token"),
                        )
                        if task_id and self._llm_impl._model_output_handler is not None:
                            output_result = self._llm_impl._model_output_handler(task_id)
                            if asyncio.iscoroutine(output_result):
                                await output_result
                        if log_latency:
                            logger.info(
                                "[VoiceLatency] ttft_ms=%s request_id=%s stream_id=%s",
                                int((first_token_at - started_at) * 1000),
                                self._request_id,
                                stream_id,
                            )
                    collected_response.append(delta)
                    for emit_delta in no_response_guard.feed(delta):
                        if not emit_delta:
                            continue
                        for buffered_delta in tts_delta_buffer.feed(emit_delta):
                            send_chat_delta(buffered_delta)

                # === VIVENTIUM START ===
                attempts = 0
                while True:
                    try:
                        if log_latency:
                            logger.info(
                                "[VoiceLatency] stream_subscribe_attempt_ms=%s request_id=%s stream_id=%s attempt=%s",
                                int((time.time() - started_at) * 1000),
                                self._request_id,
                                stream_id,
                                attempts + 1,
                            )
                        async with session.get(
                            sse_url,
                            headers=headers,
                            params={"resume": "true"},
                        ) as sse_resp:
                            if sse_resp.status >= 400:
                                body = await sse_resp.text()
                                stream_error = f"LibreChat voice stream failed: {sse_resp.status} {body}"
                                logger.warning(
                                    "[LibreChatLLM] Voice stream HTTP error status=%s request_id=%s stream_id=%s attempt=%s",
                                    sse_resp.status,
                                    self._request_id,
                                    stream_id,
                                    attempts + 1,
                                )
                                break

                            async for event in iter_sse_json_events(content=sse_resp.content):
                                self._llm_impl._record_tool_hops_from_event(
                                    hop_trace,
                                    event,
                                    timestamp_ms=time.time() * 1000.0,
                                )
                                stream_error = _extract_stream_error(event)
                                if stream_error:
                                    break

                                if event.get("sync"):
                                    resumed_text = _extract_resume_state_text(event)
                                    collected_text = "".join(collected_raw_response)
                                    if resumed_text.startswith(collected_text):
                                        missing_text = resumed_text[len(collected_text) :]
                                        if missing_text:
                                            await process_text_delta(missing_text)
                                    elif resumed_text:
                                        logger.warning(
                                            "[LibreChatLLM] Resume state diverged from consumed voice text; refusing duplicate replay"
                                        )
                                    continue

                                task_event = _extract_voice_task_event(
                                    event,
                                    expected_call_session_id=self._auth.call_session_id,
                                )
                                if task_event is not None:
                                    event_task_id = task_event["taskId"].strip()
                                    if task_id is None:
                                        task_id = event_task_id
                                    await self._llm_impl._relay_task_event_once(task_event)
                                    if (
                                        event_task_id == task_id
                                        and task_event["state"] in _VOICE_TASK_SUPPRESSING_STATES
                                    ):
                                        suppress_task_output = True
                                        logger.info(
                                            "[VoiceTask] output_suppression_enabled callSessionId=%s requestId=%s streamId=%s taskId=%s state=%s",
                                            self._auth.call_session_id,
                                            self._request_id,
                                            stream_id,
                                            task_id,
                                            task_event["state"],
                                        )
                                    continue

                                if _payload_has_glasshive_tool_call(event):
                                    saw_glasshive_tool_call = True

                                if event.get("final"):
                                    final_event = event
                                    break

                                # === VIVENTIUM START ===
                                # Capture canonical messageId from any cortex update event.
                                message_id_candidate = extract_cortex_message_id(event)
                                if message_id_candidate:
                                    cortex_message_id = message_id_candidate
                                # === VIVENTIUM END ===

                                # === VIVENTIUM START ===
                                # Fix: Skip ALL on_cortex_update events from the text delta path.
                                # Updated: 2026-02-24
                                #
                                # Why: extract_cortex_insight() only captures status="complete" events
                                # and `continue`s. But "activating"/"brewing" cortex events that have
                                # a "text" field (status label) would fall through to text delta
                                # extraction, which matches any payload with a "text" key,
                                # causing cortex status labels to be spoken via TTS.
                                # Additionally, on_cortex_followup events must not be treated as
                                # text deltas either — follow-up delivery is handled by the poller.
                                #
                                # Fix: Guard all cortex event types before the text delta extraction.
                                cortex_event_type = event.get("event", "")
                                if cortex_event_type in ("on_cortex_update", "on_cortex_followup"):
                                    saw_cortex_event = True
                                    # Still capture completed insights for the follow-up poller.
                                    insight = extract_cortex_insight(event)
                                    if insight:
                                        logger.info(
                                            "[LibreChatLLM] Captured cortex insight from %s during streaming",
                                            insight.get("cortex_name", "unknown"),
                                        )
                                        pending_insights.append(insight)
                                    continue
                                # === VIVENTIUM END ===

                                for raw_delta in extract_raw_text_deltas(event):
                                    await process_text_delta(raw_delta)

                            if stream_error or final_event:
                                break

                        if stream_error or final_event:
                            break

                        attempts += 1
                        if attempts > max_retries:
                            stream_error = "voice stream closed before completion"
                            break
                        await asyncio.sleep(retry_delay_s)
                    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                        attempts += 1
                        if attempts > max_retries:
                            stream_error = str(e)
                            break
                        await asyncio.sleep(retry_delay_s)
                # === VIVENTIUM END ===

                # Fallback: if LibreChat didn't stream any deltas, emit the final response text (if any)
                if not _output_is_suppressed() and not saw_any_tokens and final_event:
                    text = _extract_final_response_text(final_event)
                    if text and not is_no_response_only(text):
                        collected_response.append(text)
                        send_chat_delta(text)
                # === VIVENTIUM START ===
                if stream_error and not _output_is_suppressed():
                    logger.warning(
                        "[LibreChatLLM] Voice stream error request_id=%s stream_id=%s error=%s",
                        self._request_id,
                        stream_id,
                        stream_error,
                    )
                    fallback = _select_stream_error_message(stream_error)
                    fallback = sanitize_voice_followup_text(fallback)
                    if fallback:
                        collected_response.append(fallback)
                        # Drop any buffered `{NTA}` deltas if we hit a stream error.
                        no_response_guard = _NoResponseStreamGuard()
                        tts_delta_buffer = _VoiceTtsDeltaBuffer(
                            sanitize_chunk=lambda text: sanitize_voice_tts_text(
                                text,
                                preserve_leading_space=text[:1].isspace(),
                                preserve_trailing_space=text[-1:].isspace(),
                                allow_voice_controls=self._llm_impl._voice_accepts_inline_controls,
                            )
                        )
                        send_chat_delta(fallback)
                # === VIVENTIUM END ===

                completed_at = time.time()
                if log_latency:
                    logger.info(
                        "[VoiceLatency] stream_done_ms=%s request_id=%s stream_id=%s final_event=%s stream_error=%s token_events=%s",
                        int((completed_at - started_at) * 1000),
                        self._request_id,
                        stream_id,
                        bool(final_event),
                        bool(stream_error),
                        saw_any_tokens,
                    )

                # === VIVENTIUM START ===
                # Flush any buffered deltas now that we have the full response classification.
                full_response_text = "".join(collected_response)
                if _should_debug_voice_markup() and full_response_text:
                    logger.info(
                        "[VoiceMarkup] llm_full tts_text_json=%s display_text_json=%s",
                        _debug_text_json(full_response_text),
                        _debug_text_json(strip_voice_control_tags(full_response_text)),
                    )
                suppressed, pending_emit = no_response_guard.finalize(full_response_text)
                if not suppressed and not _output_is_suppressed():
                    for emit_delta in pending_emit:
                        if not emit_delta:
                            continue
                        for buffered_delta in tts_delta_buffer.feed(emit_delta):
                            send_chat_delta(buffered_delta)
                    for buffered_delta in tts_delta_buffer.finalize():
                        send_chat_delta(buffered_delta)
                await flush_disconnected_speech()
                # === VIVENTIUM END ===

                # Fire-and-forget insight follow-up. Never block the main response.
                # === VIVENTIUM START ===
                # Ensure follow-up polling still schedules when the final event is missing.
                message_id = ""
                if final_event:
                    message_id = _extract_final_response_message_id(final_event)
                if not message_id:
                    message_id = cortex_message_id
                if (
                    message_id
                    and self._llm_impl._followup_handler
                    and not _output_is_suppressed()
                ):
                    try:
                        if log_latency:
                            logger.info(
                                "[VoiceLatency] followup_schedule_ms=%s request_id=%s stream_id=%s message_id=%s cortex_expected=%s pending_insights=%s glasshive_expected=%s",
                                int((time.time() - started_at) * 1000),
                                self._request_id,
                                stream_id,
                                message_id,
                                saw_cortex_event,
                                len(pending_insights),
                                saw_glasshive_tool_call,
                            )
                        self._llm_impl._followup_handler(
                            message_id,
                            pending_insights,
                            "".join(collected_response).strip(),
                            cortex_expected=saw_cortex_event,
                            glasshive_expected=saw_glasshive_tool_call,
                        )
                    except Exception as e:
                        logger.warning("[LibreChatLLM] follow-up handler failed: %s", e)
                # === VIVENTIUM END ===
            except asyncio.CancelledError:
                if stream_id and task_id and final_event is None:
                    self._llm_impl._start_task_continuation(
                        stream_id=stream_id,
                        task_id=task_id,
                        headers=dict(headers),
                        request_id=self._request_id,
                        pending_insights=pending_insights,
                        saw_cortex_event=saw_cortex_event,
                        saw_glasshive_tool_call=saw_glasshive_tool_call,
                        cortex_message_id=cortex_message_id,
                        hop_trace=hop_trace,
                    )
                logger.info(
                    "[VoiceTask] stream_consumer_interrupted callSessionId=%s requestId=%s streamId=%s backendTaskPreserved=true",
                    self._auth.call_session_id,
                    self._request_id,
                    stream_id or "",
                )
                raise
            finally:
                self._llm_impl.schedule_trace_terminal(hop_trace)
                if stream_id and final_event is None:
                    logger.info(
                        "[VoiceTask] stream_closed_without_final callSessionId=%s requestId=%s streamId=%s backendTaskPreserved=true",
                        self._auth.call_session_id,
                        self._request_id,
                        stream_id,
                    )

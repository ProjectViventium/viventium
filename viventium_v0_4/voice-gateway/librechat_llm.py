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
import logging
import os
import re
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

import aiohttp

logger = logging.getLogger("voice-gateway.librechat_llm")
from livekit.agents import llm
from livekit.agents.llm import ChatChunk, ChatContext, ChoiceDelta
from livekit.agents.llm.tool_context import FunctionTool, RawFunctionTool, ToolChoice
from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS, NOT_GIVEN, APIConnectOptions, NotGivenOr

from sse import (
    # === VIVENTIUM START ===
    extract_cortex_message_id,
    # === VIVENTIUM END ===
    extract_cortex_insight,
    extract_text_deltas,
    iter_sse_json_events,
    sanitize_voice_followup_text,
)

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
# === VIVENTIUM END ===


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
    if not tool_message:
        tool_message = "I'm having trouble reaching your tools right now. Please try again."
    if not stream_message:
        stream_message = "I'm having trouble reaching the service right now. Please try again."
    if error:
        lowered = error.lower()
        if "mcp" in lowered or "tool" in lowered or "oauth" in lowered:
            return tool_message
    return stream_message


def _extract_stream_error(payload: dict[str, Any]) -> Optional[str]:
    if payload.get("_sse_event") != "error":
        return None
    err = payload.get("error")
    if isinstance(err, str) and err.strip():
        return err.strip()
    return "voice stream error"
# === VIVENTIUM END ===


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
        followup_handler: Optional[Callable[[str, list[dict[str, Any]], str], None]] = None,
    ) -> None:
        super().__init__()
        self._origin = origin.rstrip("/")
        self._auth = auth
        self._timeout_s = float(timeout_s)
        self._voice_mode = bool(voice_mode)
        self._voice_provider = voice_provider or "cartesia"
        self._followup_handler = followup_handler

    @property
    def model(self) -> str:
        return "librechat"

    @property
    def provider(self) -> str:
        return "viventium"

    def set_followup_handler(
        self, handler: Optional[Callable[[str, list[dict[str, Any]], str], None]]
    ) -> None:
        self._followup_handler = handler

    # === VIVENTIUM START ===
    # Feature: allow worker to override voice provider after TTS fallbacks.
    def set_voice_provider(self, provider: str) -> None:
        value = (provider or "").strip()
        if value:
            self._voice_provider = value
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

        log_latency = _should_log_latency()
        started_at = time.time()
        post_sent_at: Optional[float] = None
        first_token_at: Optional[float] = None

        timeout = aiohttp.ClientTimeout(total=self._timeout_s)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # 1) Start resumable generation
            async with session.post(
                chat_url,
                headers=headers,
                json={
                    "text": user_text,
                    "voiceMode": self._llm_impl._voice_mode,
                    "voiceProvider": self._llm_impl._voice_provider,
                    # Ensure surface-aware prompt rules apply for voice calls.
                    "viventiumInputMode": "voice_call",
                    "viventiumSurface": "voice",
                },
            ) as resp:
                if resp.status >= 400:
                    body = await resp.text()
                    raise RuntimeError(f"LibreChat voice chat failed: {resp.status} {body}")
                payload = await resp.json()
                stream_id = payload.get("streamId")
                post_sent_at = time.time()
                if log_latency:
                    logger.info(
                        "[VoiceLatency] chat_post_ms=%s request_id=%s",
                        int((post_sent_at - started_at) * 1000),
                        self._request_id,
                    )

            if not isinstance(stream_id, str) or not stream_id:
                raise RuntimeError("LibreChat voice chat returned no streamId")

            # 2) Subscribe to SSE stream and forward message deltas
            sse_url = f"{self._origin}/api/viventium/voice/stream/{stream_id}"

            saw_any_tokens = False
            first = True
            final_event: Optional[dict[str, Any]] = None
            # === VIVENTIUM START ===
            stream_error: Optional[str] = None
            max_retries, retry_delay_s = _get_voice_sse_retry_config()
            # === VIVENTIUM END ===

            # Track cortex insights that arrive during streaming (background cortices)
            pending_insights: list[dict[str, Any]] = []
            collected_response: list[str] = []
            # === VIVENTIUM START ===
            # Guard against `{NTA}` flashing during streaming.
            no_response_guard = _NoResponseStreamGuard()
            # === VIVENTIUM END ===
            # === VIVENTIUM START ===
            # Keep the canonical assistant messageId from cortex updates as a follow-up fallback.
            cortex_message_id = ""
            # === VIVENTIUM END ===

            # === VIVENTIUM START ===
            attempts = 0
            while True:
                try:
                    async with session.get(
                        sse_url,
                        headers=headers,
                        params={"resume": "true"},
                    ) as sse_resp:
                        if sse_resp.status >= 400:
                            body = await sse_resp.text()
                            stream_error = f"LibreChat voice stream failed: {sse_resp.status} {body}"
                            break

                        async for event in iter_sse_json_events(content=sse_resp.content):
                            stream_error = _extract_stream_error(event)
                            if stream_error:
                                break

                            if event.get("sync"):
                                continue

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
                            # a "text" field (status label) would fall through to
                            # extract_text_deltas() which matches any payload with a "text" key,
                            # causing cortex status labels to be spoken via TTS.
                            # Additionally, on_cortex_followup events must not be treated as
                            # text deltas either — follow-up delivery is handled by the poller.
                            #
                            # Fix: Guard all cortex event types before the text delta extraction.
                            cortex_event_type = event.get("event", "")
                            if cortex_event_type in ("on_cortex_update", "on_cortex_followup"):
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

                            for delta in extract_text_deltas(event):
                                if not delta:
                                    continue
                                saw_any_tokens = True
                                if first_token_at is None:
                                    first_token_at = time.time()
                                    if log_latency:
                                        logger.info(
                                            "[VoiceLatency] ttft_ms=%s request_id=%s",
                                            int((first_token_at - started_at) * 1000),
                                            self._request_id,
                                        )
                                collected_response.append(delta)
                                # === VIVENTIUM START ===
                                # Suppress `{NTA}` from being spoken/rendered by buffering until decision.
                                for emit_delta in no_response_guard.feed(delta):
                                    if not emit_delta:
                                        continue
                                    cd = ChoiceDelta(
                                        role="assistant" if first else None,
                                        content=emit_delta,
                                    )
                                    first = False
                                    self._event_ch.send_nowait(
                                        ChatChunk(id=self._request_id, delta=cd)
                                    )
                                # === VIVENTIUM END ===

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
            if not saw_any_tokens and final_event:
                text = _extract_final_response_text(final_event)
                if text and not is_no_response_only(text):
                    collected_response.append(text)
                    self._event_ch.send_nowait(
                        ChatChunk(
                            id=self._request_id,
                            delta=ChoiceDelta(role="assistant", content=text),
                        ),
                    )
            # === VIVENTIUM START ===
            if stream_error:
                logger.warning("[LibreChatLLM] Voice stream error: %s", stream_error)
                fallback = _select_stream_error_message(stream_error)
                fallback = sanitize_voice_followup_text(fallback)
                if fallback:
                    cd = ChoiceDelta(
                        role="assistant" if first else None,
                        content=fallback,
                    )
                    collected_response.append(fallback)
                    # Drop any buffered `{NTA}` deltas if we hit a stream error.
                    no_response_guard = _NoResponseStreamGuard()
                    self._event_ch.send_nowait(ChatChunk(id=self._request_id, delta=cd))
            # === VIVENTIUM END ===

            completed_at = time.time()
            if log_latency:
                logger.info(
                    "[VoiceLatency] stream_done_ms=%s request_id=%s",
                    int((completed_at - started_at) * 1000),
                    self._request_id,
                )

            # === VIVENTIUM START ===
            # Flush any buffered deltas now that we have the full response classification.
            full_response_text = "".join(collected_response)
            suppressed, pending_emit = no_response_guard.finalize(full_response_text)
            if not suppressed:
                for emit_delta in pending_emit:
                    if not emit_delta:
                        continue
                    cd = ChoiceDelta(role="assistant" if first else None, content=emit_delta)
                    first = False
                    self._event_ch.send_nowait(ChatChunk(id=self._request_id, delta=cd))
            # === VIVENTIUM END ===

            # Fire-and-forget insight follow-up. Never block the main response.
            # === VIVENTIUM START ===
            # Ensure follow-up polling still schedules when the final event is missing.
            message_id = ""
            if final_event:
                message_id = _extract_final_response_message_id(final_event)
            if not message_id:
                message_id = cortex_message_id
            if message_id and self._llm_impl._followup_handler:
                try:
                    self._llm_impl._followup_handler(
                        message_id,
                        pending_insights,
                        "".join(collected_response).strip(),
                    )
                except Exception as e:
                    logger.warning("[LibreChatLLM] follow-up handler failed: %s", e)
            # === VIVENTIUM END ===

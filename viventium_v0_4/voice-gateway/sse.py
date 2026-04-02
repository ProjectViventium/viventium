# === VIVENTIUM START ===
# Feature: LibreChat Voice Calls - Voice Gateway SSE utilities
# Added: 2026-01-08
# Updated: 2026-01-09 - Added cortex insight extraction for proactive speech
#
# Purpose:
# - Minimal SSE parser for LibreChat's `/api/viventium/voice/stream/:streamId` endpoint.
# - Extract assistant text deltas from the streamed event payloads.
# - Extract cortex insights for proactive speech delivery.
# === VIVENTIUM END ===

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
import os
import re

_SHARED_PATH = Path(__file__).resolve().parent.parent / "shared"
if str(_SHARED_PATH) not in os.sys.path:
    os.sys.path.insert(0, str(_SHARED_PATH))

try:
    from no_response import strip_inline_nta
except Exception:
    def strip_inline_nta(text: Optional[str]) -> str:
        if not isinstance(text, str):
            return text or ""
        cleaned = re.sub(r"\{\s*NTA\s*\}", " ", text, flags=re.IGNORECASE)
        cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
        cleaned = re.sub(r"\s+\n", "\n", cleaned)
        cleaned = re.sub(r"\n\s+", "\n", cleaned)
        return cleaned.strip()


@dataclass(frozen=True)
class SSEEvent:
    event: str
    data: str


# === VIVENTIUM START ===
# Feature: Voice gateway citation cleanup (literal + Unicode markers).
# Keep regex patterns aligned with LibreChat client citations.
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
# === VIVENTIUM START ===
# Feature: Voice follow-up sanitization for speech (URLs, emails, lists, markdown).
_URL_RE = re.compile(r"\bhttps?://\S+|\bwww\.\S+")
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")
_CODE_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)
_HEADING_RE = re.compile(r"(?m)^\s{0,3}#{1,6}\s+")
_LIST_PREFIX_RE = re.compile(r"(?m)^\s*(?:[-*+]|\d+[.)]|\u2022)\s+")
_PLAN_PREFIX_RE = re.compile(r"(?im)^\s*(?:structured\s+)?(?:plan|steps?)\s*:\s*")
_TABLE_ROW_RE = re.compile(r"(?m)^\s*[|:\\-\\s]+$")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_TOOL_DIRECTIVE_PREFIX_RE = re.compile(
    r"(?i)^(use|list|fetch|pull|query|find|locate|get|retrieve|search|open|check|"
    r"identify|summarize|return|provide|select|collect)\b"
)
_TOOL_DIRECTIVE_KEYWORDS_RE = re.compile(
    r"(?i)\b("
    r"ms365|microsoft 365|folder id|receiveddatetime|body preview|bodypreview|"
    r"subject|from|message id|messageid|conversation id|conversationid|"
    r"calendar view|start of day|end of day|inbox|calendar|email|messages?|events?"
    r")\b"
)
_INLINE_NTA_DELTA_RE = re.compile(r"\{\s*NTA\s*\}", re.IGNORECASE)
# === VIVENTIUM END ===
# === VIVENTIUM END ===


def sanitize_voice_text(text: str) -> str:
    if not text:
        return ""
    # === VIVENTIUM START ===
    # Preserve leading spaces across streaming chunks; trim later on full assembly.
    cleaned = _CITATION_COMPOSITE_RE.sub(" ", text)
    cleaned = _CITATION_STANDALONE_RE.sub(" ", cleaned)
    cleaned = _CITATION_CLEANUP_RE.sub(" ", cleaned)
    cleaned = _BRACKET_CITATION_RE.sub(" ", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned
    # === VIVENTIUM END ===


# === VIVENTIUM START ===
# Feature: Voice follow-up sanitization for speech output (no plans/URLs/emails/markdown).
# Updated 2026-02-22: Strip voice control tags (SSML + bracket nonverbals) before
# speech. Follow-up text from the LLM may contain emotion/SSML tags that would be
# spoken literally by non-Cartesia TTS providers or even by Cartesia if emotion
# parsing doesn't apply to follow-up utterances.
def sanitize_voice_followup_text(text: str, *, preserve_leading_space: bool = False) -> str:
    if not text:
        return ""
    # Preserve leading whitespace for streamed deltas so words don't concatenate.
    leading_space = preserve_leading_space and text[:1].isspace()
    # Strip voice control tags before other sanitization — follow-up speech should
    # not contain raw <emotion/>, <break/>, [laughter], etc.
    cleaned = strip_voice_control_tags(text)
    cleaned = strip_inline_nta(cleaned)
    cleaned = sanitize_voice_text(cleaned)
    if not cleaned:
        return ""
    cleaned = cleaned.replace("\\n", "\n").replace("\\r", "\r")
    cleaned = _CODE_BLOCK_RE.sub(" ", cleaned)
    cleaned = _MARKDOWN_LINK_RE.sub(r"\1", cleaned)
    cleaned = _URL_RE.sub(" link available ", cleaned)
    cleaned = _EMAIL_RE.sub(" email available ", cleaned)
    cleaned = cleaned.replace("`", "")
    cleaned = _HEADING_RE.sub("", cleaned)
    cleaned = _PLAN_PREFIX_RE.sub("", cleaned)
    cleaned = _LIST_PREFIX_RE.sub("", cleaned)
    cleaned = _TABLE_ROW_RE.sub(" ", cleaned)
    cleaned = re.sub(r"\(\s*\)", "", cleaned)
    cleaned = re.sub(r"\s*[\r\n]+\s*", " ", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    # Ensure space after sentence-ending punctuation when followed by uppercase letter.
    # This handles cases where LLM output lacks proper spacing (e.g., "sentence1.Sentence2").
    cleaned = re.sub(r"([.!?])([A-Z])", r"\1 \2", cleaned)
    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(cleaned) if s.strip()]
    if sentences:
        filtered: list[str] = []
        for sentence in sentences:
            if _TOOL_DIRECTIVE_PREFIX_RE.match(sentence) and _TOOL_DIRECTIVE_KEYWORDS_RE.search(sentence):
                continue
            filtered.append(sentence)
        cleaned = " ".join(filtered).strip()
    else:
        cleaned = cleaned.strip()
    if preserve_leading_space and leading_space and cleaned:
        cleaned = " " + cleaned
    return cleaned
# === VIVENTIUM END ===


# === VIVENTIUM START ===
# Feature: Strip Cartesia SSML tags + bracket nonverbal markers for non-expressive TTS providers.
#
# Purpose: When FallbackTTS routes to a provider that does not support Cartesia
# SSML (e.g., ElevenLabs, OpenAI), strip structural XML tags AND bracket-form
# nonverbal markers so they are not spoken literally.
#
# Updated 2026-02-22: Also strip bracket nonverbal markers ([laughter], [sigh], etc.)
# during same-turn fallback. Previous design assumed prompt update happens immediately,
# but during the one-turn fallback gap the LLM may have already generated Cartesia-style
# bracket tokens that non-expressive providers would speak literally as words.
_VCT_SPEAK_TAG_RE = re.compile(r"</?speak[^>]*>", re.IGNORECASE)
_VCT_EMOTION_SELF_CLOSING_RE = re.compile(
    r"<emotion\s+value=[\"']?[^\"'>]+[\"']?\s*/>", re.IGNORECASE
)
_VCT_EMOTION_WRAPPER_RE = re.compile(
    r"<emotion\s+value=[\"']?[^\"'>]+[\"']?\s*>(.*?)</emotion>",
    re.IGNORECASE | re.DOTALL,
)
# Cartesia SSML tags beyond emotion: <break>, <speed>, <volume>, <spell>
_VCT_BREAK_TAG_RE = re.compile(r"<break\s+time=[\"']?[^\"'>]+[\"']?\s*/>", re.IGNORECASE)
_VCT_SPEED_TAG_RE = re.compile(r"<speed\s+ratio=[\"']?[^\"'>]+[\"']?\s*/>", re.IGNORECASE)
_VCT_VOLUME_TAG_RE = re.compile(r"<volume\s+ratio=[\"']?[^\"'>]+[\"']?\s*/>", re.IGNORECASE)
_VCT_SPELL_TAG_RE = re.compile(r"<spell>(.*?)</spell>", re.IGNORECASE | re.DOTALL)
# Bracket nonverbal markers: [laughter], [sigh], [gasp], [whisper], [breath], [hmm] and common variants.
# Keep aligned with surfacePrompts.js _DISPLAY_BRACKET_NONVERBAL_RE and xAI prompt markers.
_VCT_BRACKET_NONVERBAL_RE = re.compile(
    r"\["
    r"(?:laugh(?:ter)?|giggle|chuckle|soft laugh|gentle laugh|quiet laugh|nervous laugh|"
    r"awkward laugh|light laugh|"
    r"sigh|gentle sigh|soft sigh|"
    r"breath|breath in|breath out|inhale|exhale|"
    r"gasp|whisper|hmm|hm)"
    r"\]",
    re.IGNORECASE,
)


def strip_voice_control_tags(text: str) -> str:
    """Strip Cartesia SSML tags and bracket nonverbal markers from text.

    For use when synthesizing text through providers that do not support
    Cartesia-specific SSML (e.g., ElevenLabs, OpenAI TTS).
    Preserves inner text for wrapper-form tags (<emotion>, <spell>).
    """
    if not text:
        return ""
    cleaned = _VCT_SPEAK_TAG_RE.sub("", text)
    cleaned = _VCT_EMOTION_SELF_CLOSING_RE.sub("", cleaned)
    cleaned = _VCT_EMOTION_WRAPPER_RE.sub(lambda m: m.group(1) or "", cleaned)
    cleaned = _VCT_BREAK_TAG_RE.sub("", cleaned)
    cleaned = _VCT_SPEED_TAG_RE.sub("", cleaned)
    cleaned = _VCT_VOLUME_TAG_RE.sub("", cleaned)
    cleaned = _VCT_SPELL_TAG_RE.sub(lambda m: m.group(1) or "", cleaned)
    cleaned = _VCT_BRACKET_NONVERBAL_RE.sub("", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned
# === VIVENTIUM END ===


# === VIVENTIUM START ===
# Feature: Voice delta sanitization for streaming chunks (preserve whitespace).
#
# Purpose:
# - The voice/chat pipeline consumes token deltas. Stripping each chunk can cause missing spaces
#   across boundaries (e.g., "quietand", "{NTA}{NTA}").
# - Keep per-delta cleanup minimal and whitespace-preserving; apply heavier sanitization on
#   full follow-up messages (see sanitize_voice_followup_text).
def sanitize_voice_delta_text(text: str) -> str:
    if not text:
        return ""
    cleaned = sanitize_voice_text(text)
    cleaned = _INLINE_NTA_DELTA_RE.sub(" ", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    # Defensive: sometimes streamed JSON carries escaped newlines as literal backslash sequences.
    return cleaned.replace("\\n", "\n").replace("\\r", "\r")
# === VIVENTIUM END ===


def _iter_sse_events_from_text(buffer: str) -> tuple[list[SSEEvent], str]:
    """
    Parse complete SSE event blocks from `buffer`.

    Returns: (events, remainder_buffer)
    """
    events: list[SSEEvent] = []
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
        events.append(SSEEvent(event=event_name, data="\n".join(data_lines)))


async def iter_sse_json_events(
    *,
    content: Any,
    max_buffer_bytes: int = 2_000_000,
) -> AsyncIterator[dict[str, Any]]:
    """
    Yield parsed JSON payloads from an aiohttp response `.content`.

    LibreChat uses `event: message` and `data: {json}`.
    """
    buf = ""
    async for chunk in content.iter_any():
        if not chunk:
            continue
        buf += chunk.decode("utf-8", errors="ignore")
        if len(buf) > max_buffer_bytes:
            # Prevent unbounded growth if server sends malformed SSE.
            buf = buf[-max_buffer_bytes:]

        events, buf = _iter_sse_events_from_text(buf)
        for ev in events:
            if not ev.data:
                continue
            # === VIVENTIUM START ===
            # Handle LibreChat SSE error events so callers can surface failures.
            if ev.event not in ("message", "error"):
                continue
            try:
                payload = json.loads(ev.data)
            except json.JSONDecodeError:
                if ev.event == "error":
                    payload = {"error": ev.data}
                else:
                    continue
            if isinstance(payload, dict):
                if ev.event != "message":
                    payload["_sse_event"] = ev.event
                yield payload
            # === VIVENTIUM END ===


def extract_text_deltas(payload: dict[str, Any]) -> list[str]:
    """
    Extract assistant text deltas from a LibreChat SSE payload.

    Handles:
    - `{ type, text }` legacy/alternate chunks
    - `{ event: 'on_message_delta', data: { delta: { content: [...] }}}`
    """
    out: list[str] = []

    # Legacy: direct content deltas
    text = payload.get("text")
    if isinstance(text, str) and text:
        out.append(sanitize_voice_delta_text(text))
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
        # Typical shape: { type: 'text', text: '...' }
        ptext = part.get("text")
        if isinstance(ptext, str) and ptext:
            out.append(sanitize_voice_delta_text(ptext))
            continue
        # Defensive: sometimes nested { text: { value: '...' } }
        if isinstance(ptext, dict):
            val = ptext.get("value")
            if isinstance(val, str) and val:
                out.append(sanitize_voice_delta_text(val))

    return out


def extract_cortex_insight(payload: dict[str, Any]) -> Optional[dict[str, Any]]:
    """
    Extract a completed cortex insight from an on_cortex_update event.

    Returns insight dict when status='complete', None otherwise.

    LibreChat emits cortex events as:
    {
      event: 'on_cortex_update',
      data: {
        cortex_name: 'confirmation_bias',
        status: 'activating' | 'brewing' | 'complete' | 'error',
        insight: '...',  // Only present when status='complete'
        ...
      }
    }
    """
    event = payload.get("event")
    if event != "on_cortex_update":
        return None

    data = payload.get("data")
    if not isinstance(data, dict):
        return None

    status = data.get("status")
    if status != "complete":
        return None

    insight = data.get("insight")
    if not insight:
        return None

    return {
        "cortex_name": data.get("cortex_name", "background"),
        "cortex_id": data.get("cortex_id"),
        "insight": insight,
        "run_id": data.get("runId"),
    }


# === VIVENTIUM START ===
# Feature: Capture canonical messageId from cortex updates for follow-up polling.
def extract_cortex_message_id(payload: dict[str, Any]) -> Optional[str]:
    """
    Extract canonicalMessageId from on_cortex_update events.

    This lets the voice gateway schedule DB follow-up polling even if the
    main stream ends before the final event is delivered.
    """
    if payload.get("event") != "on_cortex_update":
        return None
    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    message_id = data.get("canonicalMessageId")
    if isinstance(message_id, str) and message_id.strip():
        return message_id.strip()
    return None
# === VIVENTIUM END ===


def format_insight_speech_prompt(insights: list[dict[str, Any]], recent_response: Optional[str] = None) -> str:
    """
    Format cortex insights for natural speech delivery.

    This mirrors viventium_v1's format_subconscious_update_prompt() to create
    a natural "aha moment" where the agent shares insights as if they just
    occurred to them.
    """
    if not insights:
        return ""

    # Build summary of all insights
    summary_lines: list[str] = []
    for insight_obj in insights:
        cortex_name = insight_obj.get("cortex_name", "background")
        insight_text = insight_obj.get("insight", "")
        if isinstance(insight_text, str) and insight_text.strip():
            # Clean up the insight text for speech
            clean_text = sanitize_voice_followup_text(insight_text)
            if len(clean_text) > 500:
                clean_text = clean_text[:500] + "..."
            if clean_text:
                summary_lines.append(f"- From {cortex_name}: {clean_text}")

    if not summary_lines:
        return ""

    summary_text = "\n".join(summary_lines)

    # Frame as natural background insights surfacing (generic, non-neuroscience)
    # === VIVENTIUM START ===
    # Feature: Voice follow-up prompt rules (override via env).
    voice_rules = (os.getenv("VIVENTIUM_VOICE_FOLLOWUP_RULES", "") or "").strip()
    if not voice_rules:
        voice_rules = "\n".join(
            [
                "VOICE FOLLOW-UP RULES:",
                "- Speak naturally in short sentences.",
                "- Do not output planning steps or numbered lists.",
                "- Do not include tool instructions or API field names.",
                "- Do not read URLs or email addresses aloud; offer to send details.",
                "- Use natural language for dates/times (no raw timestamps).",
                "- Keep it to 1-3 sentences unless the user asked for more detail.",
            ]
        )
    # === VIVENTIUM END ===
    if recent_response:
        prompt = f"""Right after you spoke, some additional background insights surfaced:

{voice_rules}

BACKGROUND INSIGHTS:
{summary_text}

These insights surfaced as you continued thinking about the conversation.

If they add something meaningful to what you just said, continue speaking naturally - as if these thoughts just occurred to you mid-conversation.
If you already covered this comprehensively, there's no need to repeat yourself - just say something brief like "Actually, that's about it."

Respond naturally, as a continuation of your previous thought."""
    else:
        prompt = f"""As you've been thinking about the conversation, some additional insights have surfaced:

{voice_rules}

BACKGROUND INSIGHTS:
{summary_text}

These insights surfaced as you continued processing the conversation.

Share them naturally as a continuation of the ongoing conversation - like you just had an "aha" moment.
Keep it conversational and concise."""

    return prompt

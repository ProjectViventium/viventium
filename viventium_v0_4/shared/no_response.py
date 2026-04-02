# === VIVENTIUM START ===
# Feature: No Response Tag ({NTA})
#
# Purpose:
# - Provide a shared, strict definition for the "no response" marker used in passive/background modes.
# - Keep exact-match checks to avoid suppressing legitimate content that mentions the tag.
#
# Added: 2026-02-07
# === VIVENTIUM END ===

from __future__ import annotations

import re
from typing import Optional

NO_RESPONSE_TAG = "{NTA}"

# Accept whitespace variants like "{ NTA }" and case variants like "{nta}".
_NO_RESPONSE_TAG_RE = re.compile(r"^\s*\{\s*NTA\s*\}\s*$", re.IGNORECASE)
_INLINE_NO_RESPONSE_TAG_RE = re.compile(r"\{\s*NTA\s*\}", re.IGNORECASE)

# Match a trailing {NTA} at the end of a response (after content).
# The model sometimes generates content then appends {NTA}, violating the
# "output ONLY that token" rule. Strip the tag so it doesn't leak to the user.
_TRAILING_NTA_RE = re.compile(r"\s*\{\s*NTA\s*\}\s*$", re.IGNORECASE)

# Legacy/noisy phrases observed in exported conversations; normalize them to {NTA} when the entire output.
_NO_RESPONSE_PHRASES = {
    "nothing new to add.",
    "nothing new to add",
    "nothing to add.",
    "nothing to add",
}

_NO_RESPONSE_VARIANT_MAX_LEN = 200
# Accept short, "no-response-only" variants like "Nothing new to add for now."
# Must be the entire message (not a prefix), to avoid suppressing real content.
_NO_RESPONSE_VARIANT_RE = re.compile(
    r"^\s*nothing\s+(?:new\s+)?to\s+add"
    r"(?:\s*(?:\(\s*)?(?:right\s+now|for\s+now|at\s+this\s+time|at\s+the\s+moment|currently|so\s+far|yet|today)(?:\s*\))?)?"
    r"(?:\s*,?\s*(?:sorry|thanks|thank\s+you))?"
    r"\s*[.!?]*\s*$",
    re.IGNORECASE,
)


def is_no_response_tag(text: Optional[str]) -> bool:
    if not isinstance(text, str):
        return False
    return bool(_NO_RESPONSE_TAG_RE.match(text))


def contains_no_response_tag(text: Optional[str]) -> bool:
    if not isinstance(text, str):
        return False
    return bool(_INLINE_NO_RESPONSE_TAG_RE.search(text))


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


def normalize_no_response_text(text: Optional[str]) -> str:
    if is_no_response_only(text):
        return NO_RESPONSE_TAG
    if isinstance(text, str):
        return text
    return ""


def strip_inline_nta(text: Optional[str], *, preserve_outer_whitespace: bool = False) -> str:
    """Strip inline {NTA} tags from mixed-content text.

    Purpose:
    - If the model violates the "ONLY {NTA}" rule and includes real content too,
      preserve the real content while preventing the raw marker from leaking into
      UI, chat logs, or TTS output.
    """
    if not isinstance(text, str):
        return text or ""
    leading_whitespace = preserve_outer_whitespace and text[:1].isspace()
    trailing_whitespace = preserve_outer_whitespace and text[-1:].isspace()
    cleaned = _INLINE_NO_RESPONSE_TAG_RE.sub(" ", text)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+\n", "\n", cleaned)
    cleaned = re.sub(r"\n\s+", "\n", cleaned)
    if preserve_outer_whitespace:
        cleaned = cleaned.strip()
        if not cleaned:
            return ""
        if leading_whitespace:
            cleaned = " " + cleaned.lstrip()
        if trailing_whitespace:
            cleaned = cleaned.rstrip() + " "
        return cleaned
    return cleaned.strip()


def strip_trailing_nta(text: Optional[str]) -> str:
    """Strip a trailing {NTA} tag from a response that also contains content.

    When the model writes content and then appends {NTA} (violating the
    "output ONLY that token" instruction), this prevents the raw tag from
    leaking into the visible message delivered to the user.

    If the entire text IS {NTA} (no content), returns it unchanged so
    is_no_response_only() can still match for suppression.
    """
    if not isinstance(text, str):
        return text or ""
    if is_no_response_only(text):
        return text
    return strip_inline_nta(_TRAILING_NTA_RE.sub("", text).rstrip())

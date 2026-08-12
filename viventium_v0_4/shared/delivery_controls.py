"""Shared model-authored delivery-control grammar for messaging adapters."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional


DELIVERY_CONTROL_VERSION = "2026-07-22.1"
SKIP_VOICE_TOKEN = "{SKIP_VOICE}"
MESSAGE_BREAK_TOKEN = "{MSG_BREAK}"
DEFAULT_MAX_MESSAGE_BREAKS = 2
_CONTROL_LINE_RE = re.compile(
    r"^\s*\{\s*(SKIP_VOICE|MSG_BREAK)\s*\}\s*$", re.IGNORECASE
)
_CONTROL_PREFIXES = (SKIP_VOICE_TOKEN, MESSAGE_BREAK_TOKEN)


@dataclass(frozen=True)
class DeliveryControls:
    contract_version: str
    clean_text: str
    segments: tuple[str, ...]
    skip_voice: bool
    skip_voice_count: int
    message_break_count: int
    merged_break_count: int


def _fence_marker(line: str) -> str:
    match = re.match(r"^\s*(```+|~~~+)", str(line or ""))
    return match.group(1)[0] if match else ""


def parse_delivery_controls(
    text: Optional[str], *, max_message_breaks: int = DEFAULT_MAX_MESSAGE_BREAKS
) -> DeliveryControls:
    value = text.replace("\r\n", "\n").replace("\r", "\n") if isinstance(text, str) else ""
    segments: list[str] = []
    current: list[str] = []
    fence = ""
    skip_voice = False
    skip_voice_count = 0
    message_break_count = 0
    merged_break_count = 0
    safe_max_breaks = max(0, int(max_message_breaks or 0))

    for line in value.split("\n"):
        marker = _fence_marker(line)
        protected_line = bool(fence) or bool(re.match(r"^\s*>", line))
        control = None if protected_line else _CONTROL_LINE_RE.match(line)

        if control:
            name = control.group(1).upper()
            if name == "SKIP_VOICE":
                skip_voice = True
                skip_voice_count += 1
                continue

            current_text = "\n".join(current).strip()
            if current_text and message_break_count < safe_max_breaks:
                segments.append(current_text)
                current = []
                message_break_count += 1
            else:
                merged_break_count += 1
                if current_text:
                    current.append("")
            continue

        current.append(line)
        if marker:
            fence = "" if fence == marker else (fence or marker)

    final_segment = "\n".join(current).strip()
    if final_segment:
        segments.append(final_segment)

    return DeliveryControls(
        contract_version=DELIVERY_CONTROL_VERSION,
        clean_text="\n\n".join(segments),
        segments=tuple(segments),
        skip_voice=skip_voice,
        skip_voice_count=skip_voice_count,
        message_break_count=message_break_count,
        merged_break_count=merged_break_count,
    )


def strip_incomplete_control_suffix(text: Optional[str]) -> str:
    value = text.replace("\r\n", "\n").replace("\r", "\n") if isinstance(text, str) else ""
    lines = value.split("\n")
    candidate = (lines[-1] if lines else "").strip()
    if not candidate or candidate.startswith(">"):
        return value

    fence = ""
    for line in lines[:-1]:
        marker = _fence_marker(line)
        if marker:
            fence = "" if fence == marker else (fence or marker)
    if fence:
        return value

    compact = re.sub(r"\s+", "", candidate).upper()
    incomplete = any(
        2 <= len(compact) < len(token) and token.startswith(compact)
        for token in _CONTROL_PREFIXES
    )
    return "\n".join(lines[:-1]).rstrip() if incomplete else value


def strip_delivery_controls_for_preview(text: Optional[str]) -> str:
    return parse_delivery_controls(strip_incomplete_control_suffix(text)).clean_text

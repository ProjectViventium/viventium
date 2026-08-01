# === VIVENTIUM START ===
# Feature: Telegram rendered-message chunking
#
# Purpose:
# - Split rendered Telegram HTML only after Markdown and delivery-control parsing.
# - Preserve valid formatting and enforce Telegram's post-entity UTF-16 limit.
#
# Added: 2026-03-08
# === VIVENTIUM END ===

from __future__ import annotations

import html
import re

MAX_TELEGRAM_TEXT_UNITS = 4000
_HTML_TOKEN_RE = re.compile(r"(<[^>]+>|&(?:#\d+|#x[0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]+);)")
_HTML_START_TAG_RE = re.compile(r"^<([A-Za-z0-9-]+)(?:\s[^>]*)?>$")
_HTML_END_TAG_RE = re.compile(r"^</([A-Za-z0-9-]+)\s*>$")
_TEXT_ATOM_RE = re.compile(r"\n\n|\n|[^\S\n]+|[^\s]+")
_VOID_HTML_TAGS = {"br"}


def telegram_text_units(rendered_html: str) -> int:
    """Return Telegram's post-entity UTF-16 text length for rendered HTML."""
    visible = re.sub(r"<[^>]+>", "", rendered_html or "")
    visible = html.unescape(visible)
    return len(visible.encode("utf-16-le")) // 2


def _split_plain_atom(atom: str, limit: int) -> list[str]:
    if not atom:
        return []
    pieces: list[str] = []
    current: list[str] = []
    current_units = 0
    for character in atom:
        units = len(character.encode("utf-16-le")) // 2
        if current and current_units + units > limit:
            pieces.append("".join(current))
            current = []
            current_units = 0
        current.append(character)
        current_units += units
    if current:
        pieces.append("".join(current))
    return pieces


def split_telegram_html(
    rendered_html: str,
    limit: int = MAX_TELEGRAM_TEXT_UNITS,
    *,
    max_chunks: int | None = None,
) -> list[str]:
    """Split rendered Telegram HTML without breaking tags, entities, or limits."""
    if not rendered_html:
        return []
    if limit < 1:
        raise ValueError("Telegram chunk limit must be positive")
    if max_chunks is not None and max_chunks < 1:
        raise ValueError("Telegram max_chunks must be positive")
    if telegram_text_units(rendered_html) <= limit:
        return [rendered_html]

    chunks: list[str] = []
    open_tags: list[tuple[str, str]] = []
    parts: list[str] = []
    current_units = 0

    def current_html() -> str:
        closing = "".join(f"</{name}>" for name, _ in reversed(open_tags))
        return "".join(parts) + closing

    def flush() -> bool:
        nonlocal parts, current_units
        if current_units > 0:
            chunks.append(current_html())
        parts = [start_tag for _, start_tag in open_tags]
        current_units = 0
        return max_chunks is not None and len(chunks) >= max_chunks

    for token in _HTML_TOKEN_RE.split(rendered_html):
        if not token:
            continue

        end_match = _HTML_END_TAG_RE.match(token)
        if end_match:
            name = end_match.group(1).lower()
            if open_tags and open_tags[-1][0] == name:
                parts.append(token)
                open_tags.pop()
            elif any(tag_name == name for tag_name, _ in open_tags):
                matching_index = max(
                    index
                    for index, (tag_name, _) in enumerate(open_tags)
                    if tag_name == name
                )
                nested = open_tags[matching_index + 1 :]
                parts.extend(f"</{tag_name}>" for tag_name, _ in reversed(nested))
                parts.append(token)
                parts.extend(start_tag for _, start_tag in nested)
                open_tags = open_tags[:matching_index] + nested
            continue

        start_match = _HTML_START_TAG_RE.match(token)
        if start_match:
            parts.append(token)
            name = start_match.group(1).lower()
            if name not in _VOID_HTML_TAGS and not token.rstrip().endswith("/>"):
                open_tags.append((name, token))
            continue

        atoms = (
            [token]
            if token.startswith("&") and token.endswith(";")
            else _TEXT_ATOM_RE.findall(token)
        )
        for atom in atoms:
            if not atom:
                continue
            atom_units = telegram_text_units(atom)
            atom_pieces = (
                [atom]
                if atom_units <= limit
                else _split_plain_atom(atom, limit)
            )
            for piece in atom_pieces:
                piece_units = telegram_text_units(piece)
                if current_units and current_units + piece_units > limit:
                    if flush():
                        return chunks
                parts.append(piece)
                current_units += piece_units
                if current_units > limit:
                    raise ValueError(
                        "Unable to split Telegram HTML within the configured limit"
                    )

    flush()
    return chunks


def first_telegram_html_chunk(
    rendered_html: str,
    limit: int = MAX_TELEGRAM_TEXT_UNITS,
) -> str:
    """Return only the reversible first streaming-preview chunk in linear time."""

    chunks = split_telegram_html(rendered_html, limit, max_chunks=1)
    return chunks[0] if chunks else ""

# === VIVENTIUM START ===
# Feature: Telegram proactive follow-up chunking
#
# Purpose:
# - Split long proactive follow-up text into Telegram-safe chunks before delivery.
# - Prefer paragraph/sentence boundaries so follow-ups remain readable when they
#   exceed Telegram's practical message length.
#
# Added: 2026-03-08
# === VIVENTIUM END ===

from __future__ import annotations

MAX_TELEGRAM_TEXT_CHARS = 3500


def split_telegram_text(text: str, limit: int = MAX_TELEGRAM_TEXT_CHARS) -> list[str]:
    if not text:
        return []

    cleaned = text.strip()
    if not cleaned:
        return []
    if len(cleaned) <= limit:
        return [cleaned]

    chunks: list[str] = []
    remaining = cleaned
    min_boundary = max(1, limit // 2)

    while len(remaining) > limit:
        split_at = remaining.rfind("\n\n", 0, limit)
        if split_at < min_boundary:
            split_at = remaining.rfind("\n", 0, limit)
        if split_at < min_boundary:
            split_at = remaining.rfind(". ", 0, limit)
            if split_at >= min_boundary:
                split_at += 1
        if split_at < min_boundary:
            split_at = remaining.rfind(" ", 0, limit)
        if split_at < 1:
            split_at = limit

        chunk = remaining[:split_at].strip()
        if chunk:
            chunks.append(chunk)
        remaining = remaining[split_at:].strip()

    if remaining:
        chunks.append(remaining)

    return chunks

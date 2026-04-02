# === VIVENTIUM START ===
# Shared utilities for formatting background-cortex insights across Python services.
#
# Why this exists:
# - We need parity across Telegram bridge + Scheduling Cortex dispatch.
# - User-facing output must be human-like: no system notification preambles, and no internal cortex labels.
# - docs/requirements_and_learnings/01_Key_Principles.md (runtime-generated UX strings must be fixed in runtime).
#
# Added: 2026-02-12
# === VIVENTIUM END ===

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional


def format_insights_fallback_text(
    insights: Optional[Iterable[Dict[str, Any]]],
    *,
    voice_mode: bool = False,
) -> str:
    """
    Format raw cortex insights for user delivery when the primary LLM follow-up synthesis is unavailable.

    Design rules:
    - No "Background insights finished/completed" preambles.
    - No cortex/agent labels (internal identifiers).
    - Only surface the insight text itself.
    - Voice mode: join with spaces; text mode: separate by paragraphs.
    """
    if not insights:
        return ""

    texts: List[str] = []
    for item in insights:
        if not isinstance(item, dict):
            continue
        text = item.get("insight")
        if not isinstance(text, str):
            continue
        cleaned = text.strip()
        if not cleaned:
            continue
        texts.append(cleaned)

    if not texts:
        return ""

    return " ".join(texts) if voice_mode else "\n\n".join(texts)


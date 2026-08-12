"""Shared, registry-owned prompt contract for scheduled model runs."""

from __future__ import annotations


SCHEDULER_RUN_ENVELOPE_PROMPT_ID = "scheduler.run_envelope"
CONSCIOUSNESS_CONTINUITY_OPPORTUNITY_PROMPT_ID = (
    "scheduler.consciousness_continuity_opportunity"
)
SCHEDULED_RUN_CONTEXT_PLACEHOLDER = "{{scheduled_run_context}}"
SCHEDULED_RUN_CONTEXT_HEADER = "## Scheduled Run Context (Deterministic)"
SCHEDULER_RUN_ENVELOPE_TEMPLATE = """<!--viv_internal:brew_begin-->
## Background Processing (Brewing)
This is a scheduled self-prompt (for example: morning briefing, wake cycle, reminder, or passive check), not a new user scheduling request.
If background agents are activated and still brewing, and the real user-visible answer should wait for their insights, output exactly {NTA}.
If you can already give a complete stable answer without waiting, answer normally.
For live external facts such as weather, news, markets, web facts, calendar, email, tasks, current-day plans, or connected-account facts, include them only when a verified tool/cortex result or the deterministic scheduled-run context below supports the claim; otherwise omit that section instead of guessing, inferring from memory, or apologizing about missing data.
Do not mention internal mechanics or talk about scheduling.

## Scheduled Run Context (Deterministic)
{{scheduled_run_context}}"""


def render_scheduler_run_envelope(scheduled_run_context: str) -> str:
    """Render the scheduler envelope from an already sanitized factual context block."""

    context = str(scheduled_run_context or "").strip()
    if not context:
        raise ValueError("scheduled run context must not be empty")
    return SCHEDULER_RUN_ENVELOPE_TEMPLATE.replace(
        SCHEDULED_RUN_CONTEXT_PLACEHOLDER,
        context,
    )

"""Compiled registry-owned prompt contract for scheduled model runs."""

from __future__ import annotations

import re
from typing import Any

from compiled_prompt_contract import CompiledPromptError, compose_compiled_prompt, load_compiled_prompts

SCHEDULER_RUN_ENVELOPE_PROMPT_ID = "scheduler.run_envelope"
CONSCIOUSNESS_CONTINUITY_OPPORTUNITY_PROMPT_ID = (
    "scheduler.consciousness_continuity_opportunity"
)
SCHEDULED_RUN_CONTEXT_PLACEHOLDER = "{{scheduled_run_context}}"
SCHEDULED_RUN_CONTEXT_HEADER = "## Scheduled Run Context (Deterministic)"
_VARIABLE_RE = re.compile(r"{{\s*([A-Za-z0-9_.-]+)\s*}}")


class SchedulerPromptError(ValueError):
    def __init__(self, failure_class: str):
        super().__init__(failure_class)
        self.failure_class = failure_class
        self.failure_retryable = False


def load_scheduler_prompts() -> dict[str, Any]:
    """Read one generated bundle per composition; never fall back to source or stale policy."""
    try:
        return load_compiled_prompts()
    except CompiledPromptError as error:
        raise SchedulerPromptError(error.failure_class) from None


def render_scheduler_prompt(
    prompt_id: str,
    *,
    prompts: dict[str, Any] | None = None,
    scheduled_run_context: str = "",
) -> str:
    """Consume the existing compiled body/includes contract with its one runtime variable."""
    entries = load_scheduler_prompts() if prompts is None else prompts

    def substitute(match: re.Match[str]) -> str:
        if match.group(1) != "scheduled_run_context" or not scheduled_run_context:
            raise SchedulerPromptError("required_prompt_invalid")
        return scheduled_run_context

    try:
        text = compose_compiled_prompt(prompt_id, entries)
    except CompiledPromptError as error:
        raise SchedulerPromptError(error.failure_class) from None
    if (
        prompt_id == SCHEDULER_RUN_ENVELOPE_PROMPT_ID
        and _VARIABLE_RE.findall(text).count("scheduled_run_context") != 1
    ):
        raise SchedulerPromptError("required_prompt_invalid")
    return _VARIABLE_RE.sub(substitute, text)


def render_scheduler_run_envelope(
    scheduled_run_context: str, *, prompts: dict[str, Any] | None = None
) -> str:
    context = str(scheduled_run_context or "").strip()
    if not context:
        raise ValueError("scheduled run context must not be empty")
    return render_scheduler_prompt(
        SCHEDULER_RUN_ENVELOPE_PROMPT_ID,
        prompts=prompts,
        scheduled_run_context=context,
    )

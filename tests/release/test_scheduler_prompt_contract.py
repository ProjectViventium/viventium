from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PROMPT_ROOT = (
    REPO_ROOT / "viventium_v0_4" / "LibreChat" / "viventium" / "source_of_truth" / "prompts"
)
SHARED_ROOT = REPO_ROOT / "viventium_v0_4" / "shared"
if str(SHARED_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_ROOT))

from scripts.viventium.prompt_registry import load_prompt_registry, render_prompt
from scheduler_prompt_contract import (
    SCHEDULER_RUN_ENVELOPE_PROMPT_ID,
    render_scheduler_run_envelope,
)


def test_shared_scheduler_envelope_matches_registered_prompt() -> None:
    context = "- scheduled_due_at_utc: 2026-08-10T13:00:00Z"
    registered = render_prompt(
        SCHEDULER_RUN_ENVELOPE_PROMPT_ID,
        load_prompt_registry(PROMPT_ROOT),
        variables={"scheduled_run_context": context},
    )

    assert render_scheduler_run_envelope(context) == registered.strip()


def test_shared_scheduler_envelope_requires_deterministic_context() -> None:
    try:
        render_scheduler_run_envelope("  ")
    except ValueError as exc:
        assert "scheduled run context" in str(exc).lower()
    else:
        raise AssertionError("empty scheduled run context must fail closed")

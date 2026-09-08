from __future__ import annotations

import sys
import json
import shutil
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
PROMPT_ROOT = (
    REPO_ROOT / "viventium_v0_4" / "LibreChat" / "viventium" / "source_of_truth" / "prompts"
)
SHARED_ROOT = REPO_ROOT / "viventium_v0_4" / "shared"
if str(SHARED_ROOT) not in sys.path:
    sys.path.insert(0, str(SHARED_ROOT))

from scripts.viventium.prompt_registry import build_prompt_bundle, load_prompt_registry, render_prompt
from scheduler_prompt_contract import (
    SCHEDULER_RUN_ENVELOPE_PROMPT_ID,
    render_scheduler_run_envelope,
)


@pytest.fixture(autouse=True)
def compiled_scheduler_bundle(tmp_path, monkeypatch):
    path = tmp_path / "prompt-bundle.json"
    path.write_text(json.dumps(build_prompt_bundle(PROMPT_ROOT)))
    monkeypatch.setenv("VIVENTIUM_PROMPT_BUNDLE_PATH", str(path))


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


def test_scheduler_emits_saved_compiled_source_and_same_path_replacement(tmp_path, monkeypatch):
    source_root = tmp_path / "prompts"
    shutil.copytree(PROMPT_ROOT / "scheduler", source_root / "scheduler")
    source = source_root / "scheduler" / "run_envelope.md"
    original = source.read_text()
    bundle_path = tmp_path / "prompt-bundle.json"
    monkeypatch.setenv("VIVENTIUM_PROMPT_BUNDLE_PATH", str(bundle_path))
    context = "- scheduled_due_at_utc: 2026-09-05T12:00:00Z"
    for addition in ("Synthetic revision one.", "Synthetic revision two.", ""):
        source.write_text(original + "\n" + addition + "\n")
        bundle_path.write_text(json.dumps(build_prompt_bundle(source_root)))
        expected = render_prompt(
            SCHEDULER_RUN_ENVELOPE_PROMPT_ID,
            load_prompt_registry(source_root),
            variables={"scheduled_run_context": context},
        ).strip()
        assert render_scheduler_run_envelope(context) == expected
    assert "Synthetic revision" not in render_scheduler_run_envelope(context)


@pytest.mark.parametrize("contents", [None, "not-json", "{}"])
def test_scheduler_missing_or_invalid_compiled_bundle_fails_truthfully(tmp_path, monkeypatch, contents):
    bundle_path = tmp_path / "broken-prompt-bundle.json"
    if contents is not None:
        bundle_path.write_text(contents)
    monkeypatch.setenv("VIVENTIUM_PROMPT_BUNDLE_PATH", str(bundle_path))
    with pytest.raises(ValueError, match="prompt_bundle_unavailable|required_prompt_invalid"):
        render_scheduler_run_envelope("- scheduled_due_at_utc: 2026-09-05T12:00:00Z")


def test_scheduler_unconfigured_bundle_is_a_typed_nonretryable_failure(monkeypatch):
    monkeypatch.delenv("VIVENTIUM_PROMPT_BUNDLE_PATH")
    with pytest.raises(ValueError) as error:
        render_scheduler_run_envelope("- schedule_timezone: UTC")
    assert error.value.failure_class == "prompt_bundle_unavailable"
    assert error.value.failure_retryable is False


@pytest.mark.parametrize("body", ["No context", "{{unknown}}", "{{scheduled_run_context}} {{scheduled_run_context}}"])
def test_scheduler_rejects_loss_or_duplication_of_typed_context(tmp_path, monkeypatch, body):
    bundle = build_prompt_bundle(PROMPT_ROOT)
    bundle["prompts"][SCHEDULER_RUN_ENVELOPE_PROMPT_ID]["body"] = body
    path = tmp_path / "invalid-context.json"
    path.write_text(json.dumps(bundle))
    monkeypatch.setenv("VIVENTIUM_PROMPT_BUNDLE_PATH", str(path))
    with pytest.raises(ValueError, match="required_prompt_invalid"):
        render_scheduler_run_envelope("- schedule_timezone: UTC")


def test_scheduler_rejects_cyclic_compiled_includes(tmp_path, monkeypatch):
    bundle = build_prompt_bundle(PROMPT_ROOT)
    bundle["prompts"][SCHEDULER_RUN_ENVELOPE_PROMPT_ID]["metadata"]["includes"] = [
        SCHEDULER_RUN_ENVELOPE_PROMPT_ID
    ]
    path = tmp_path / "cycle.json"
    path.write_text(json.dumps(bundle))
    monkeypatch.setenv("VIVENTIUM_PROMPT_BUNDLE_PATH", str(path))
    with pytest.raises(ValueError, match="required_prompt_invalid"):
        render_scheduler_run_envelope("- schedule_timezone: UTC")

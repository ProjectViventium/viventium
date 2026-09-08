"""Read and render the existing compiled prompt body/includes contract."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

VARIABLE_RE = re.compile(r"{{\s*([A-Za-z0-9_.-]+)\s*}}")


class CompiledPromptError(ValueError):
    def __init__(self, failure_class: str):
        super().__init__(failure_class)
        self.failure_class = failure_class
        self.failure_retryable = False


def load_compiled_prompts() -> dict[str, Any]:
    """Read the configured bundle; never fall back to source or stale policy."""
    path = os.environ.get("VIVENTIUM_PROMPT_BUNDLE_PATH", "").strip()
    if not path:
        raise CompiledPromptError("prompt_bundle_unavailable")
    try:
        bundle = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        raise CompiledPromptError("prompt_bundle_unavailable") from None
    if not isinstance(bundle, dict) or not isinstance(bundle.get("prompts"), dict):
        raise CompiledPromptError("required_prompt_invalid")
    return bundle["prompts"]


def compose_compiled_prompt(prompt_id: str, prompts: dict[str, Any]) -> str:
    def compose(current_id: str, stack: tuple[str, ...] = ()) -> str:
        entry = prompts.get(current_id)
        if current_id in stack or not isinstance(entry, dict):
            raise CompiledPromptError("required_prompt_invalid")
        body, metadata = entry.get("body"), entry.get("metadata")
        if not isinstance(body, str) or not isinstance(metadata, dict):
            raise CompiledPromptError("required_prompt_invalid")
        includes = metadata.get("includes") or []
        if not isinstance(includes, list) or not all(isinstance(item, str) for item in includes):
            raise CompiledPromptError("required_prompt_invalid")
        parts = [compose(item, (*stack, current_id)).strip() for item in includes]
        parts.append(body.strip())
        return "\n\n".join(parts).strip()

    text = compose(prompt_id)
    if not text:
        raise CompiledPromptError("required_prompt_invalid")
    return text


def render_compiled_prompt(
    prompt_id: str,
    *,
    prompts: dict[str, Any] | None = None,
    variables: dict[str, str] | None = None,
) -> str:
    entries = load_compiled_prompts() if prompts is None else prompts

    def substitute(match: re.Match[str]) -> str:
        value = (variables or {}).get(match.group(1))
        if not isinstance(value, str) or not value:
            raise CompiledPromptError("required_prompt_invalid")
        return value

    return VARIABLE_RE.sub(substitute, compose_compiled_prompt(prompt_id, entries))

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .drafts import create_file_draft
from .paths import PROMPTS_ROOT, relative_to_repo

from scripts.viventium.prompt_registry import load_prompt_registry, render_prompt


@dataclass(frozen=True)
class SectionCandidate:
    prompt_id: str
    old_section: str
    new_section: str


def derive_single_section_replacement(
    source_full: str,
    live_full: str,
    sections: list[tuple[str, str]],
) -> SectionCandidate | None:
    """Return the one included section whose replacement exactly explains live_full.

    This intentionally handles only clean one-section edits. Multi-section edits and
    whitespace-ambiguous edits must go to manual review instead of guessing.
    """

    candidates: list[SectionCandidate] = []
    for prompt_id, old_section in sections:
        index = source_full.find(old_section)
        if index < 0:
            continue
        prefix = source_full[:index]
        suffix = source_full[index + len(old_section) :]
        if live_full.startswith(prefix) and live_full.endswith(suffix):
            new_section = live_full[len(prefix) : len(live_full) - len(suffix)]
            if new_section != old_section:
                candidates.append(SectionCandidate(prompt_id, old_section, new_section))
    if len(candidates) == 1:
        return candidates[0]
    return None


def create_import_live_draft(
    *,
    prompt_id: str,
    live_text: str,
    private_root: Path | None = None,
) -> dict[str, Any]:
    registry = load_prompt_registry(PROMPTS_ROOT)
    entry = registry[prompt_id]
    includes = [str(item) for item in (entry.metadata.get("includes") or [])]
    source_full = render_prompt(prompt_id, registry).rstrip()
    clean_live = live_text.rstrip()

    sections = [
        (include_id, render_prompt(include_id, registry).rstrip())
        for include_id in includes
        if include_id in registry
    ]
    if not sections:
        sections = [(prompt_id, source_full)]

    candidate = derive_single_section_replacement(source_full, clean_live, sections)
    if not candidate:
        return {
            "status": "requires_manual_target",
            "reason": "Live edit did not map cleanly to exactly one managed prompt section.",
            "candidatePromptIds": [prompt for prompt, _ in sections],
        }

    target_entry = registry[candidate.prompt_id]
    new_file_text = _replace_prompt_body(target_entry.path, candidate.new_section.rstrip() + "\n")
    draft = create_file_draft(
        target_path=target_entry.path,
        new_text=new_file_text,
        kind="live-import",
        reason=f"Import live edit into {candidate.prompt_id}",
        private_root=private_root,
    )
    draft["status"] = "draft"
    draft["mappedPromptId"] = candidate.prompt_id
    return draft


def _replace_prompt_body(path: Path, new_body: str) -> str:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"Prompt is missing frontmatter: {relative_to_repo(path)}")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ValueError(f"Prompt frontmatter is not closed: {relative_to_repo(path)}")
    frontmatter = text[: end + len("\n---\n")]
    return frontmatter + new_body.rstrip() + "\n"

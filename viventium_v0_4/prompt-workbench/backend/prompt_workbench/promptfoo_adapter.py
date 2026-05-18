from __future__ import annotations

from typing import Any


def prompt_bank_to_promptfoo(prompt_bank: dict[str, Any], *, prompt_id: str) -> dict[str, Any]:
    """Export the public synthetic bank to a Promptfoo-compatible config.

    Promptfoo is a secondary adapter here. Viventium's canonical prompt/eval source
    remains the checked-in prompt bank and exact-model runner.
    """

    tests: list[dict[str, Any]] = []
    for family in prompt_bank.get("families") or []:
        family_id = family.get("id")
        for case in family.get("cases") or []:
            tests.append(
                {
                    "vars": {
                        "input": case.get("prompt", ""),
                        "surface": case.get("surface", ""),
                        "family": family_id,
                        "case_id": case.get("id", ""),
                    },
                    "assert": [
                        {"type": "contains-any", "value": _assertion_terms(case)}
                    ],
                    "metadata": {
                        "family": family_id,
                        "case_id": case.get("id", ""),
                        "prompt_id": prompt_id,
                    },
                }
            )
    return {
        "description": "Viventium Prompt Workbench synthetic adapter",
        "prompts": [f"{{{{input}}}}\n\n# Prompt under test: {prompt_id}"],
        "providers": ["echo"],
        "tests": tests,
    }


def _assertion_terms(case: dict[str, Any]) -> list[str]:
    rubric = case.get("rubric") or []
    terms: list[str] = []
    for item in rubric:
        words = [word.strip(".,:;()[]{}").lower() for word in str(item).split()]
        terms.extend(word for word in words if len(word) > 6)
    return sorted(set(terms))[:8] or ["viventium"]

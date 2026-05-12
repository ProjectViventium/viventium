from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
QA_ROOT = ROOT / "qa"

NON_FEATURE_QA_DIRS = {"_templates", "results"}

REQUIRED_LOOP_PHRASE = (
    "supporting evidence, not substitutes for any required visible-UI, detail-state, persistence, or "
    "wording step"
)

PUBLIC_SAFE_TERMS = [
    "account identifiers",
    "conversation IDs",
    "message IDs",
    "session/call IDs",
    "Telegram chat IDs",
    "Mongo `_id` values",
    "stack traces with private paths",
    "raw runtime dumps",
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _normalized(path: Path) -> str:
    return re.sub(r"\s+", " ", _read(path))


def _feature_dirs() -> list[Path]:
    return sorted(
        path
        for path in QA_ROOT.iterdir()
        if path.is_dir() and path.name not in NON_FEATURE_QA_DIRS
    )


def _migration_features() -> set[str]:
    text = _read(QA_ROOT / "_migration.md")
    features: set[str] = set()
    for match in re.finditer(r"^\|\s+`([^`]+)`\s+\|", text, flags=re.MULTILINE):
        if match.group(1) != "Feature":
            features.add(match.group(1))
    return features


def test_qa_contract_files_and_templates_exist() -> None:
    required_paths = [
        QA_ROOT / "README.md",
        QA_ROOT / "_migration.md",
        QA_ROOT / "_templates" / "README.md",
        QA_ROOT / "_templates" / "feature-readme.md",
        QA_ROOT / "_templates" / "cases.md",
        QA_ROOT / "_templates" / "run-report.md",
        QA_ROOT / "results" / "README.md",
    ]
    for path in required_paths:
        assert path.exists(), f"Missing QA operating-contract file: {path}"


def test_user_grade_qa_loop_disallows_backend_only_substitution() -> None:
    paths = [
        ROOT / "AGENTS.md",
        ROOT / "docs" / "requirements_and_learnings" / "01_Key_Principles.md",
        QA_ROOT / "README.md",
        QA_ROOT / "_templates" / "run-report.md",
    ]
    for path in paths:
        assert REQUIRED_LOOP_PHRASE in _normalized(path), f"Missing substitution guard in {path}"

    qa_readme = _read(QA_ROOT / "README.md")
    assert "Playwright CLI or an equivalent real-browser harness" in qa_readme
    assert "Skipping the visible browser step is not acceptable" in qa_readme


def test_public_safe_qa_evidence_terms_stay_in_sync() -> None:
    paths = [
        QA_ROOT / "README.md",
        QA_ROOT / "results" / "README.md",
        QA_ROOT / "_templates" / "run-report.md",
        ROOT / "docs" / "requirements_and_learnings" / "01_Key_Principles.md",
    ]
    for path in paths:
        text = _normalized(path)
        for term in PUBLIC_SAFE_TERMS:
            assert term in text, f"Missing public-safety term {term!r} in {path}"


def test_legacy_qa_folder_gaps_are_tracked() -> None:
    migration_features = _migration_features()
    assert migration_features, "Expected qa/_migration.md to list legacy QA folders"

    missing_readme_or_cases = {
        path.name
        for path in _feature_dirs()
        if not (path / "README.md").exists() or not (path / "cases.md").exists()
    }
    assert missing_readme_or_cases <= migration_features


def test_background_agent_browser_loop_case_entrypoint_is_pinned() -> None:
    cases_text = _read(QA_ROOT / "background_agents" / "cases.md")
    for phrase in [
        "real browser prompt/action",
        "activated background agents are visible by name",
        "expanded cards show why/result/status/error details",
        "stored `messages.content` cortex parts match",
        "the main answer does not claim background work has not started",
    ]:
        assert phrase in cases_text

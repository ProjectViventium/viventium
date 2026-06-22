from __future__ import annotations

import re
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
QA_ROOT = REPO_ROOT / "qa"
QA_RESULTS = QA_ROOT / "results"
FEATURE_QA_ROOT = QA_ROOT / "glasshive_deep_research"
PUBLIC_DOC_DIRS = [
    REPO_ROOT / "viventium_v0_4" / "GlassHive" / "research" / "phase1",
]
PUBLIC_DOC_FILES = [
    REPO_ROOT
    / "docs"
    / "requirements_and_learnings"
    / "48_GlassHive_Workstation_Sandbox_Runtime.md",
]


def qa_public_evidence_roots() -> list[Path]:
    roots = [QA_RESULTS]
    roots.extend(path for path in sorted(QA_ROOT.glob("*/reports")) if path.is_dir())
    roots.extend(path for path in sorted(QA_ROOT.glob("*/scripts")) if path.is_dir())
    if FEATURE_QA_ROOT.is_dir():
        roots.append(FEATURE_QA_ROOT)
    roots.extend(path for path in PUBLIC_DOC_DIRS if path.is_dir())

    deduped: list[Path] = []
    seen: set[Path] = set()
    for path in roots:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            deduped.append(path)
    return deduped


def public_evidence_files() -> list[Path]:
    return [path for path in PUBLIC_DOC_FILES if path.is_file()]


def is_git_ignored(path: Path) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "--quiet", str(path.relative_to(REPO_ROOT))],
        cwd=REPO_ROOT,
        check=False,
    )
    return result.returncode == 0


PRIVATE_PATTERNS = {
    "local_home_path": re.compile(r"/Users/[^/\s\"']+"),
    "personal_email": re.compile(
        r"\b[A-Za-z0-9._%+-]+@(?!example\.com\b|viventium\.local\b|localhost\b)"
        r"[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        re.IGNORECASE,
    ),
    "openai_api_key": re.compile(r"\bsk-[A-Za-z0-9._=-]{8,}"),
    "provider_request_id": re.compile(r"\breq_[A-Za-z0-9_-]{8,}"),
    "bearer_token": re.compile(r"\bBearer\s+[A-Za-z0-9._=-]{10,}", re.IGNORECASE),
    "glasshive_signed_query": re.compile(r"\bgh_(?:token|sig|exp|kind)\s*=", re.IGNORECASE),
    "glasshive_runtime_id": re.compile(r"\b(?:prj|wrk|run)_[0-9A-Fa-f]{8,}\b"),
}


def iter_public_evidence_files() -> list[Path]:
    files: list[Path] = []
    for root in qa_public_evidence_roots():
        if not root.exists():
            continue
        files.extend(path for path in sorted(root.rglob("*")) if path.is_file())
    files.extend(public_evidence_files())
    return files


def test_tracked_qa_results_do_not_contain_private_runtime_identifiers() -> None:
    offenders: list[str] = []
    for path in iter_public_evidence_files():
        if path.name == "README.md" and FEATURE_QA_ROOT.resolve() not in path.resolve().parents:
            continue
        if is_git_ignored(path):
            continue
        if path.suffix.lower() not in {".md", ".json", ".txt", ".yaml", ".yml", ".py", ".js", ".cjs"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for label, pattern in PRIVATE_PATTERNS.items():
            if pattern.search(text):
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{label}")

    assert offenders == []

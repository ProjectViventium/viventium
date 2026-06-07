from __future__ import annotations

import re
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
QA_ROOT = REPO_ROOT / "qa"
QA_RESULTS = QA_ROOT / "results"


def qa_public_evidence_roots() -> list[Path]:
    roots = [QA_RESULTS]
    roots.extend(path for path in sorted(QA_ROOT.glob("*/reports")) if path.is_dir())
    return roots


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
}


def test_tracked_qa_results_do_not_contain_private_runtime_identifiers() -> None:
    offenders: list[str] = []
    for root in qa_public_evidence_roots():
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.name == "README.md":
                continue
            if is_git_ignored(path):
                continue
            if path.suffix.lower() not in {".md", ".json", ".txt", ".yaml", ".yml"}:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for label, pattern in PRIVATE_PATTERNS.items():
                if pattern.search(text):
                    offenders.append(f"{path.relative_to(REPO_ROOT)}:{label}")

    assert offenders == []

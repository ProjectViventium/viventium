from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

# Build the banned tokens from fragments so this guard file does not become its own violation.
FORBIDDEN_PROJECT_MARKERS = re.compile(
    r"\b" + "AI" + r"TP\b|"
    r"\b" + "Pano" + r"rad\b|"
    r"\b" + "ai" + "tp" + r"\.ai\b|"
    r"\b" + "pano" + "rad" + r"\.ai\b",
    re.IGNORECASE,
)

SKIP_DIRS = {
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    ".next",
    ".next-viventium-dev",
    "coverage",
}

SKIP_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".pdf",
    ".zip",
    ".gz",
    ".tgz",
    ".tar",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".bson",
    ".wt",
}


def should_skip(path: Path) -> bool:
    if any(part in SKIP_DIRS for part in path.parts):
        return True
    return path.suffix.lower() in SKIP_SUFFIXES


def tracked_files(repo: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "-C", str(repo), "ls-files"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [repo / line for line in result.stdout.splitlines() if line]


def tracked_repos() -> list[Path]:
    repos = [ROOT]
    for relative in ("viventium_v0_4/LibreChat", "viventium_v0_4/GlassHive"):
        candidate = ROOT / relative
        if (candidate / ".git").exists():
            repos.append(candidate)
    return repos


def test_tracked_public_files_have_no_cross_project_markers() -> None:
    hits: list[str] = []
    for repo in tracked_repos():
        for path in tracked_files(repo):
            if not path.is_file() or should_skip(path):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if FORBIDDEN_PROJECT_MARKERS.search(text):
                hits.append(str(path.relative_to(ROOT)))

    assert not hits, "Cross-project markers found in tracked Viventium files: " + ", ".join(
        sorted(hits)
    )

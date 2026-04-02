from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER = REPO_ROOT / "git-helper.sh"


def run_helper(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(HELPER), *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_git_helper_list_includes_public_repo_catalog() -> None:
    result = run_helper("list")

    assert result.returncode == 0, result.stderr
    assert "main|.|https://github.com/ProjectViventium/viventium.git" in result.stdout
    assert "LibreChat|viventium_v0_4/LibreChat|https://github.com/ProjectViventium/viventium-librechat.git" in result.stdout
    assert "GlassHive|viventium_v0_4/GlassHive|https://github.com/ProjectViventium/GlassHive.git" in result.stdout


def test_git_helper_push_dry_run_defaults_to_main_only() -> None:
    result = run_helper("push", "-b", "main", "-m", "Dry run", "--dry-run")

    assert result.returncode == 0, result.stderr
    assert "[main]" in result.stdout
    assert "[LibreChat]" not in result.stdout


def test_git_helper_push_dry_run_supports_explicit_repo_selection() -> None:
    result = run_helper(
        "push",
        "-b",
        "main",
        "-m",
        "Dry run",
        "--dry-run",
        "--repo",
        "LibreChat",
        "--repos",
        "google_workspace_mcp,GlassHive",
    )

    assert result.returncode == 0, result.stderr
    assert "[main]" not in result.stdout
    assert "[LibreChat]" in result.stdout
    assert "[google_workspace_mcp]" in result.stdout
    assert "[GlassHive]" in result.stdout


def test_git_helper_unknown_repo_selector_fails_helpfully() -> None:
    result = run_helper("status", "--repo", "not-a-real-repo", "--dry-run")

    assert result.returncode != 0
    assert "Unknown repo selector(s): not-a-real-repo." in result.stderr
    assert "Available repos:" in result.stderr

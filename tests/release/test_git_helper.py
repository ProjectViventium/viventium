from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER = REPO_ROOT / "git-helper.sh"
STAGED_SAFETY = (
    REPO_ROOT / "scripts" / "viventium" / "verify_staged_public_safety.py"
)


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
    main_line = next(
        (
            line
            for line in result.stdout.splitlines()
            if line.startswith("main|.|")
        ),
        "",
    )
    assert main_line, result.stdout
    assert main_line.removesuffix(".git") == (
        "main|.|https://github.com/ProjectViventium/viventium"
    )
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


def init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    return repo


def run_staged_safety(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(STAGED_SAFETY), "--repo", str(repo)],
        check=False,
        capture_output=True,
        text=True,
    )


def test_staged_public_safety_rejects_owner_and_runtime_env_paths(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path)
    for relative in (
        "runtime.env",
        "nested/runtime.local.env",
        "runtime/service-env/librechat.owner.env",
        "state/upgrade-backups/tx/successor-bridge/librechat-runtime-env",
        "state/dev-runtime-activation.synthetic/snapshots/candidate-librechat.env",
        "state/dev-runtime-activation.synthetic/snapshots/accepted-librechat.env",
        "viventium_v0_4/LibreChat/.env.viventium-private-synthetic/owner.env",
        "viventium_v0_4/LibreChat/.env.viventium-retired-env-synthetic",
    ):
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("WEAK_SENTINEL=value\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "-f", relative], check=True)

    completed = run_staged_safety(repo)

    assert completed.returncode != 0
    assert "forbidden staged environment path" in completed.stderr
    assert "WEAK_SENTINEL" not in completed.stderr


def test_gitignore_excludes_complete_dev_runtime_activation_transactions() -> None:
    for relative in (
        "state/dev-runtime-activation.synthetic/activation.json",
        "state/dev-runtime-activation.synthetic/snapshots/candidate-librechat.env",
        "state/dev-runtime-activation.synthetic/snapshots/accepted-librechat.env",
    ):
        completed = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "check-ignore", "-q", relative],
            check=False,
        )
        assert completed.returncode == 0, relative


def test_staged_public_safety_rejects_high_confidence_secret_content(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path)
    source = repo / "safe-name.txt"
    source.write_text(
        "token=" + "sk-" + "proj-" + "abcdefghijklmnopqrstuvwxyz123456\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(repo), "add", "safe-name.txt"], check=True)

    completed = run_staged_safety(repo)

    assert completed.returncode != 0
    assert "private or secret content" in completed.stderr
    assert "abcdefghijklmnopqrstuvwxyz" not in completed.stderr


def test_staged_public_safety_rejects_private_home_email_and_embedded_credentials(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path)
    source = repo / "safe-name.txt"
    private_home = "/" + "Users" + "/" + "private-owner" + "/Documents/context.txt"
    private_email = "private.owner" + "@" + "confidential.internal"
    credential_url = (
        "https://" + "operator:private-password" + "@confidential.internal/api"
    )
    source.write_text(
        "\n".join((private_home, private_email, credential_url)) + "\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(repo), "add", "safe-name.txt"], check=True)

    completed = run_staged_safety(repo)

    assert completed.returncode != 0
    assert "private or secret content" in completed.stderr
    assert "private-owner" not in completed.stderr
    assert "private.owner" not in completed.stderr
    assert "private-password" not in completed.stderr


def test_staged_public_safety_allows_reserved_synthetic_identifiers(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path)
    source = repo / "synthetic-fixtures.txt"
    source.write_text(
        "\n".join(
            (
                "qa@example.com",
                "owner@viventium.example",
                "git@github.com",
                "https://user:synthetic-password@example.test/api",
                "http://user:synthetic-password@127.0.0.1:3190/health",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(repo), "add", "synthetic-fixtures.txt"], check=True)

    completed = run_staged_safety(repo)

    assert completed.returncode == 0, completed.stderr


def test_git_helper_runs_staged_safety_before_commit() -> None:
    source = HELPER.read_text(encoding="utf-8")
    verify = source.index("verify_staged_public_safety.py")
    commit = source.index('git -C "$path" commit -m "$message"')
    assert verify < commit


def test_generated_owner_environment_paths_are_ignored_by_default() -> None:
    paths = (
        "synthetic/runtime.env",
        "synthetic/runtime.local.env",
        "synthetic/service-env/librechat.owner.env",
        "synthetic/librechat.env",
        "synthetic/upgrade-backups/tx/successor-bridge/librechat-runtime-env",
    )
    completed = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "check-ignore", "--no-index", *paths],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    for path in paths:
        assert path in completed.stdout

from __future__ import annotations

import hashlib
import subprocess
import pytest
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
    assert "xPerfect|viventium_v0_4/xPerfect|https://github.com/xPerfectAI/xPerfect.git" in result.stdout


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
        "google_workspace_mcp,xPerfect",
    )

    assert result.returncode == 0, result.stderr
    assert "[main]" not in result.stdout
    assert "[LibreChat]" in result.stdout
    assert "[google_workspace_mcp]" in result.stdout
    assert "[xPerfect]" in result.stdout


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


def run_staged_safety(repo: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(STAGED_SAFETY), "--repo", str(repo), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize("relative", [
    "Life/private-fixture.txt",
    "assets/lIfE/private-fixture.txt",
    Path("qa", "Life", "private-fixture.md").as_posix(),
    Path("qa", "life", "other.yaml").as_posix(),
    Path("qa", "life", "cases.yaml.bak").as_posix(),
    Path("qa", "life", "reports", "synthetic.md").as_posix(),
    Path("qa", "life", "nested", "cases.yaml").as_posix(),
])
def test_personal_workspace_is_ignored_and_force_add_is_rejected(
    tmp_path: Path, relative: str,
) -> None:
    repo = init_repo(tmp_path)
    (repo / relative).parent.mkdir(parents=True)
    (repo / relative).write_text("harmless-looking bytes")
    (repo / ".gitignore").write_bytes((REPO_ROOT / ".gitignore").read_bytes())
    subprocess.run(["git", "-C", str(repo), "check-ignore", "-q", relative], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "-f", relative], check=True)
    checked = run_staged_safety(repo)
    assert checked.returncode == 2
    assert "Personal workspace data" in checked.stderr
    assert relative not in checked.stderr


def test_canonical_life_case_inventory_is_public_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = init_repo(tmp_path)
    relative = "qa/life/cases.yaml"
    source = repo / relative
    source.parent.mkdir(parents=True)
    source.write_text("schemaVersion: 1\n", encoding="utf-8")
    (repo / ".gitignore").write_bytes((REPO_ROOT / ".gitignore").read_bytes())
    monkeypatch.setenv("VIVENTIUM_LIFE_DIR", str(tmp_path / "private-workspace"))
    ignored = subprocess.run(
        ["git", "-C", str(repo), "check-ignore", "--no-index", "--quiet", relative],
        check=False,
    )
    assert ignored.returncode == 1
    subprocess.run(["git", "-C", str(repo), "add", relative], check=True)
    checked = run_staged_safety(repo)
    assert checked.returncode == 0, checked.stderr


@pytest.mark.parametrize("ignore_case", [False, True])
def test_case_alias_of_public_life_source_is_rejected(
    tmp_path: Path, ignore_case: bool,
) -> None:
    repo = init_repo(tmp_path)
    relative = Path("qa", "Life", "cases.yaml").as_posix()
    source = repo / relative
    source.parent.mkdir(parents=True)
    source.write_text("Synthetic private fixture.\n", encoding="utf-8")
    (repo / ".gitignore").write_bytes((REPO_ROOT / ".gitignore").read_bytes())
    git = ["git", "-C", str(repo), "-c", f"core.ignorecase={str(ignore_case).lower()}"]
    ignored = subprocess.run(
        [*git, "check-ignore", "--no-index", "--quiet", relative], check=False,
    )
    # Git folds exact exceptions on case-insensitive filesystems; the source guard does not.
    assert ignored.returncode == (1 if ignore_case else 0)
    subprocess.run([*git, "add", "--force", relative], check=True)
    checked = run_staged_safety(repo)
    assert checked.returncode == 2
    assert "Personal workspace data" in checked.stderr
    assert relative not in checked.stderr


def test_personal_workspace_symlink_metadata_is_rejected(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    (repo / "shortcut").symlink_to("../Life/private-fixture.txt")
    subprocess.run(["git", "-C", str(repo), "add", "shortcut"], check=True)
    checked = run_staged_safety(repo)
    assert checked.returncode == 2
    assert "Personal workspace metadata" in checked.stderr
    assert "private-fixture" not in checked.stderr


def test_renamed_identity_bytes_and_lfs_pointer_cannot_be_staged(tmp_path: Path, monkeypatch) -> None:
    repo = init_repo(tmp_path)
    life = tmp_path / "private-folder"
    identity = life / "Self/Identity"
    identity.mkdir(parents=True)
    secret = b"synthetic personal bytes with no path marker"
    (identity / "source.bin").write_bytes(secret)
    monkeypatch.setenv("VIVENTIUM_LIFE_DIR", str(life))
    digest = hashlib.sha256(secret).hexdigest()
    for data in (
        secret,
        f"version https://hawser.github.com/spec/v1\r\noid sha256:{digest}\r\nsize {len(secret)}\r\n".encode(),
    ):
        (repo / "asset.bin").write_bytes(data)
        subprocess.run(["git", "-C", str(repo), "add", "asset.bin"], check=True)
        checked = run_staged_safety(repo)
        assert checked.returncode == 2
        assert "Private identity bytes" in checked.stderr
        assert digest not in checked.stderr


def test_outgoing_check_catches_metadata_in_commit_later_deleted(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    git = ["git", "-C", str(repo), "-c", "user.name=Fixture", "-c", "user.email=qa@example.com",
           "-c", "core.hooksPath=/dev/null"]
    subprocess.run([*git, "commit", "--allow-empty", "-qm", "public baseline"], check=True)
    subprocess.run([*git, "update-ref", "refs/remotes/origin/main", "HEAD"], check=True)
    source = repo / "report.txt"
    source.write_text("file:%2f%2f%2fhome%2fsynthetic%2f" + "Life%2fprivate-fixture.txt")
    subprocess.run([*git, "add", source.name], check=True)
    assert run_staged_safety(repo).returncode == 2
    subprocess.run([*git, "commit", "-qm", "local first commit"], check=True)
    subprocess.run([*git, "rm", "-q", source.name], check=True)
    subprocess.run([*git, "commit", "-qm", "local removal"], check=True)
    assert run_staged_safety(repo).returncode == 0
    checked = run_staged_safety(repo, "--outgoing-ref", "HEAD")
    assert checked.returncode == 2
    assert "outgoing history" in checked.stderr
    assert "private-fixture" not in checked.stderr


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
        "claude/synthetic-session/harness-prompt.md",
        "codex/synthetic-session/project-definition.md",
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


@pytest.mark.parametrize("harness", ["claude", "codex"])
def test_staged_public_safety_rejects_private_session_prose_without_a_secret(
    tmp_path: Path, harness: str,
) -> None:
    repo = init_repo(tmp_path)
    relative = f"{harness}/synthetic-session/harness-prompt.md"
    source = repo / relative
    source.parent.mkdir(parents=True)
    source.write_text("Private operator instructions without a token.\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", relative], check=True)

    completed = run_staged_safety(repo)

    assert completed.returncode != 0
    assert "forbidden staged private session path" in completed.stderr
    assert "Private operator instructions" not in completed.stderr


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


@pytest.mark.parametrize("relative,payload", [
    ("report.txt", "token=" + "sk-" + "proj-" + "abcdefghijklmnopqrstuvwxyz123456"),
    ("nested/runtime.env", "WEAK_SENTINEL=value"),
    (Path("qa", "model.private.json").as_posix(), "{\"synthetic_private_run\":true}"),
    (Path("qa", "model-private.json").as_posix(), "{\"synthetic_private_run\":true}"),
    ("codex/fixture/prompt.md", "Synthetic private session text"),
])
def test_outgoing_rejects_forbidden_content_even_after_removal(
    tmp_path: Path, relative: str, payload: str,
) -> None:
    repo = init_repo(tmp_path)
    commands = ["git", "-C", str(repo), "-c", "user.name=Fixture",
                "-c", "user.email=qa@example.com", "-c", "core.hooksPath=/dev/null"]
    subprocess.run([*commands, "commit", "--allow-empty", "-qm", "public baseline"], check=True)
    subprocess.run([*commands, "update-ref", "refs/remotes/origin/main", "HEAD"], check=True)
    source = repo / relative
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(payload, encoding="utf-8")
    subprocess.run([*commands, "add", "-f", relative], check=True)
    subprocess.run([*commands, "commit", "-qm", "synthetic local addition"], check=True)
    subprocess.run([*commands, "rm", "-q", relative], check=True)
    subprocess.run([*commands, "commit", "-qm", "synthetic local removal"], check=True)
    assert run_staged_safety(repo).returncode == 0
    result = run_staged_safety(repo, "--outgoing-ref", "HEAD")
    assert result.returncode == 2
    assert "outgoing" in result.stderr
    assert payload not in result.stderr


def test_outgoing_allows_public_synthetic_content_and_noreply_identity(tmp_path: Path) -> None:
    repo = init_repo(tmp_path)
    commands = ["git", "-C", str(repo), "-c", "user.name=Fixture",
                "-c", "user.email=12345+fixture@users.noreply.github.com",
                "-c", "core.hooksPath=/dev/null"]
    subprocess.run([*commands, "commit", "--allow-empty", "-qm", "public baseline"], check=True)
    subprocess.run([*commands, "update-ref", "refs/remotes/origin/main", "HEAD"], check=True)
    (repo / "guide.md").write_text("qa@example.com\nhttps://service.example.test\n", encoding="utf-8")
    subprocess.run([*commands, "add", "guide.md"], check=True)
    subprocess.run([*commands, "commit", "-qm", "Add synthetic guide"], check=True)
    result = run_staged_safety(repo, "--outgoing-ref", "HEAD")
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("relative", [
    Path("qa", "model.private.json").as_posix(),
    Path("qa", "model-private.json").as_posix(),
])
def test_staged_rejects_private_evidence_names(tmp_path: Path, relative: str) -> None:
    repo = init_repo(tmp_path)
    source = repo / relative
    source.parent.mkdir(parents=True)
    source.write_text("{\"synthetic_private_run\":true}", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", relative], check=True)
    result = run_staged_safety(repo)
    assert result.returncode == 2
    assert "forbidden staged" in result.stderr

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PUBLIC_ORIGIN_PREFIX = "https://github.com/ProjectViventium/"
FULL_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_public_component_manifest_uses_projectviventium_origins() -> None:
    payload = load_json(REPO_ROOT / "devops" / "git" / "repos.json")
    invalid = {
        entry["path"]: entry["origin"]
        for entry in payload["repos"]
        if str(entry.get("path", "")).startswith("viventium_v0_4/")
        and not str(entry.get("origin", "")).startswith(PUBLIC_ORIGIN_PREFIX)
    }

    assert invalid == {}


def test_components_lock_matches_public_component_manifest_origins() -> None:
    repos_payload = load_json(REPO_ROOT / "devops" / "git" / "repos.json")
    lock_payload = load_json(REPO_ROOT / "components.lock.json")

    origin_by_path = {entry["path"]: entry["origin"] for entry in repos_payload["repos"]}
    mismatched = {
        entry["path"]: {
            "lock_origin": entry["origin"],
            "manifest_origin": origin_by_path.get(entry["path"]),
        }
        for entry in lock_payload["components"]
        if origin_by_path.get(entry["path"]) != entry["origin"]
    }

    assert mismatched == {}


def test_components_lock_uses_full_commit_shas_for_public_components() -> None:
    lock_payload = load_json(REPO_ROOT / "components.lock.json")

    invalid = {
        entry["path"]: entry["ref"]
        for entry in lock_payload["components"]
        if str(entry.get("origin", "")).startswith(PUBLIC_ORIGIN_PREFIX)
        and not FULL_GIT_SHA_RE.fullmatch(str(entry.get("ref", "")))
    }

    assert invalid == {}


def test_components_lock_covers_all_public_v0_4_manifest_components() -> None:
    repos_payload = load_json(REPO_ROOT / "devops" / "git" / "repos.json")
    lock_payload = load_json(REPO_ROOT / "components.lock.json")

    expected_paths = {
        entry["path"]
        for entry in repos_payload["repos"]
        if str(entry.get("path", "")).startswith("viventium_v0_4/")
    }
    locked_paths = {entry["path"] for entry in lock_payload["components"]}

    assert expected_paths == locked_paths


def write_fake_git(path: Path) -> None:
    path.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "$*" >> "$FAKE_GIT_LOG"
if [[ "$*" == *" remote get-url origin" ]]; then
  printf '%s\\n' "$FAKE_GIT_ORIGIN"
fi
if [[ "$*" == *" status --porcelain --untracked-files=no" ]]; then
  printf '%s' "${FAKE_GIT_STATUS:-}"
fi
if [[ "$*" == *" rev-parse HEAD" ]] || [[ "$*" == *" rev-parse refs/remotes/origin/"* ]]; then
  printf '%s\n' "${FAKE_GIT_RESOLVED_SHA:-1111111111111111111111111111111111111111}"
fi
""",
        encoding="utf-8",
    )
    path.chmod(0o755)


def test_bootstrap_refuses_to_mutate_existing_checkout_with_unrelated_origin(tmp_path: Path) -> None:
    bootstrap = tmp_path / "install.sh"
    shutil.copy2(REPO_ROOT / "install.sh", bootstrap)
    install_dir = tmp_path / "existing"
    (install_dir / ".git").mkdir(parents=True)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    git_log = tmp_path / "git.log"
    write_fake_git(fake_bin / "git")

    completed = subprocess.run(
        ["bash", str(bootstrap)],
        cwd=tmp_path,
        env={
            **os.environ,
            "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
            "HOME": str(tmp_path / "home"),
            "VIVENTIUM_INSTALL_DIR": str(install_dir),
            "FAKE_GIT_LOG": str(git_log),
            "FAKE_GIT_ORIGIN": "https://github.com/example/unrelated-project.git",
        },
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "Refusing to update an existing checkout with an unexpected origin" in completed.stderr
    assert "remote get-url origin" in git_log.read_text(encoding="utf-8")
    assert " fetch " not in f" {git_log.read_text(encoding='utf-8')} "
    assert " checkout " not in f" {git_log.read_text(encoding='utf-8')} "
    assert " pull " not in f" {git_log.read_text(encoding='utf-8')} "


def test_bootstrap_accepts_equivalent_projectviventium_ssh_origin_before_update(tmp_path: Path) -> None:
    bootstrap = tmp_path / "install.sh"
    shutil.copy2(REPO_ROOT / "install.sh", bootstrap)
    install_dir = tmp_path / "existing"
    (install_dir / ".git").mkdir(parents=True)
    (install_dir / "bin").mkdir()
    cli_log = tmp_path / "cli.log"
    cli = install_dir / "bin" / "viventium"
    cli.write_text(
        "#!/usr/bin/env bash\nprintf '%s\\n' \"$*\" > \"$FAKE_CLI_LOG\"\n",
        encoding="utf-8",
    )
    cli.chmod(0o755)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    git_log = tmp_path / "git.log"
    write_fake_git(fake_bin / "git")

    completed = subprocess.run(
        ["bash", str(bootstrap), "--no-start"],
        cwd=tmp_path,
        env={
            **os.environ,
            "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
            "HOME": str(tmp_path / "home"),
            "VIVENTIUM_INSTALL_DIR": str(install_dir),
            "FAKE_GIT_LOG": str(git_log),
            "FAKE_GIT_ORIGIN": "git@github.com:ProjectViventium/viventium.git",
            "FAKE_CLI_LOG": str(cli_log),
        },
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    calls = git_log.read_text(encoding="utf-8")
    assert "remote get-url origin" in calls
    assert "fetch origin main" in calls
    assert "checkout main" in calls
    assert "pull --ff-only origin main" in calls
    assert cli_log.read_text(encoding="utf-8").strip() == "install --no-start"


def test_bootstrap_refuses_dirty_tracked_existing_checkout_before_update_or_cli(tmp_path: Path) -> None:
    bootstrap = tmp_path / "install.sh"
    shutil.copy2(REPO_ROOT / "install.sh", bootstrap)
    install_dir = tmp_path / "existing"
    (install_dir / ".git").mkdir(parents=True)
    (install_dir / "bin").mkdir()
    cli_log = tmp_path / "cli.log"
    cli = install_dir / "bin" / "viventium"
    cli.write_text(
        "#!/usr/bin/env bash\nprintf '%s\\n' \"$*\" > \"$FAKE_CLI_LOG\"\n",
        encoding="utf-8",
    )
    cli.chmod(0o755)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    git_log = tmp_path / "git.log"
    write_fake_git(fake_bin / "git")

    completed = subprocess.run(
        ["bash", str(bootstrap), "--no-start"],
        cwd=tmp_path,
        env={
            **os.environ,
            "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
            "HOME": str(tmp_path / "home"),
            "VIVENTIUM_INSTALL_DIR": str(install_dir),
            "FAKE_GIT_LOG": str(git_log),
            "FAKE_GIT_ORIGIN": "https://github.com/ProjectViventium/viventium.git",
            "FAKE_GIT_STATUS": " M bin/viventium\n",
            "FAKE_CLI_LOG": str(cli_log),
        },
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "Refusing to update an existing checkout with tracked changes" in completed.stderr
    calls = git_log.read_text(encoding="utf-8")
    assert "status --porcelain --untracked-files=no" in calls
    assert " fetch " not in f" {calls} "
    assert " checkout " not in f" {calls} "
    assert " pull " not in f" {calls} "
    assert not cli_log.exists()


def test_bootstrap_refuses_clean_local_commit_ahead_of_requested_origin(tmp_path: Path) -> None:
    remote = tmp_path / "remote.git"
    seed = tmp_path / "seed"
    install_dir = tmp_path / "existing"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True, text=True)
    subprocess.run(["git", "init", "-b", "main", str(seed)], check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.name", "Viventium QA"], cwd=seed, check=True)
    subprocess.run(["git", "config", "user.email", "qa@example.invalid"], cwd=seed, check=True)
    (seed / "bin").mkdir()
    seed_cli = seed / "bin" / "viventium"
    seed_cli.write_text(
        "#!/usr/bin/env bash\nprintf '%s\\n' remote > \"$FAKE_CLI_LOG\"\n",
        encoding="utf-8",
    )
    seed_cli.chmod(0o755)
    subprocess.run(["git", "add", "bin/viventium"], cwd=seed, check=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=seed, check=True, capture_output=True, text=True)
    subprocess.run(["git", "remote", "add", "origin", str(remote)], cwd=seed, check=True)
    subprocess.run(["git", "push", "-u", "origin", "main"], cwd=seed, check=True, capture_output=True, text=True)
    subprocess.run(["git", "clone", "--branch", "main", str(remote), str(install_dir)], check=True, capture_output=True, text=True)

    subprocess.run(["git", "config", "user.name", "Viventium QA"], cwd=install_dir, check=True)
    subprocess.run(["git", "config", "user.email", "qa@example.invalid"], cwd=install_dir, check=True)
    installed_cli = install_dir / "bin" / "viventium"
    installed_cli.write_text(
        "#!/usr/bin/env bash\nprintf '%s\\n' local-ahead > \"$FAKE_CLI_LOG\"\n",
        encoding="utf-8",
    )
    installed_cli.chmod(0o755)
    subprocess.run(["git", "add", "bin/viventium"], cwd=install_dir, check=True)
    subprocess.run(
        ["git", "commit", "-m", "local ahead"],
        cwd=install_dir,
        check=True,
        capture_output=True,
        text=True,
    )

    bootstrap = tmp_path / "install.sh"
    shutil.copy2(REPO_ROOT / "install.sh", bootstrap)
    cli_log = tmp_path / "cli.log"
    completed = subprocess.run(
        ["bash", str(bootstrap), "--no-start"],
        cwd=tmp_path,
        env={
            **os.environ,
            "HOME": str(tmp_path / "home"),
            "VIVENTIUM_REPO_URL": str(remote),
            "VIVENTIUM_INSTALL_DIR": str(install_dir),
            "VIVENTIUM_REPO_BRANCH": "main",
            "FAKE_CLI_LOG": str(cli_log),
        },
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "does not exactly match the requested origin branch" in completed.stderr
    assert not cli_log.exists()

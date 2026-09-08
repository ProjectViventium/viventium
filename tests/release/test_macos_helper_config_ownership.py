"""Preserved helper config ownership must compare physical paths.

macOS `/tmp` is a symlink to `/private/tmp`. The helper stores the logical root it was handed while
the runtime resolves the physical one, so a lexical comparison refused ownership of the very runtime
that armed it ("Preserved helper config does not own this runtime") and persistent helper recovery
stayed unarmed after every activation.
"""

from __future__ import annotations

import json
import shlex
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "viventium" / "install_macos_helper.sh"


def _extract_shell_function(text: str, name: str) -> str:
    lines = text.splitlines()
    start = next(index for index, line in enumerate(lines) if line.strip() == f"{name}() {{")
    depth = 0
    collected: list[str] = []
    for line in lines[start:]:
        collected.append(line)
        depth += line.count("{")
        depth -= line.count("}")
        if depth == 0:
            break
    return "\n".join(collected) + "\n"


def _run_verify(tmp_path: Path, configured_repo: Path, expected_repo: Path) -> subprocess.CompletedProcess[str]:
    app_support = tmp_path / "app-support"
    app_support.mkdir(exist_ok=True)
    config = tmp_path / "helper-config.json"
    config.write_text(
        json.dumps({"repoRoot": str(configured_repo), "appSupportDir": str(app_support)}),
        encoding="utf-8",
    )
    config.chmod(0o600)
    function = _extract_shell_function(SCRIPT.read_text(encoding="utf-8"), "verify_preserved_helper_config")
    script = (
        "set -euo pipefail\n"
        "resolve_repo_python() { command -v python3; }\n"
        f"HELPER_CONFIG_FILE={shlex.quote(str(config))}\n"
        f"HELPER_RUNTIME_REPO_ROOT={shlex.quote(str(expected_repo))}\n"
        f"APP_SUPPORT_DIR={shlex.quote(str(app_support))}\n"
        f"{function}"
        "verify_preserved_helper_config\n"
    )
    return subprocess.run(["bash", "-c", script], text=True, capture_output=True, check=False)


def test_preserved_helper_config_owns_runtime_through_a_symlinked_root(tmp_path: Path) -> None:
    physical_repo = tmp_path / "physical" / "repo"
    physical_repo.mkdir(parents=True)
    logical_parent = tmp_path / "logical"
    logical_parent.symlink_to(tmp_path / "physical", target_is_directory=True)
    logical_repo = logical_parent / "repo"

    completed = _run_verify(tmp_path, configured_repo=logical_repo, expected_repo=physical_repo)

    assert completed.returncode == 0, completed.stderr
    assert "does not own this runtime" not in completed.stderr


def test_preserved_helper_config_still_refuses_a_different_runtime(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    other = tmp_path / "other"
    other.mkdir()

    completed = _run_verify(tmp_path, configured_repo=other, expected_repo=repo)

    assert completed.returncode != 0
    assert "does not own this runtime" in completed.stderr


def test_preserved_helper_config_refuses_a_symlinked_config_file(tmp_path: Path) -> None:
    # The symlink check must inspect the path as handed over; resolving it first would hide the link.
    repo = tmp_path / "repo"
    repo.mkdir()
    app_support = tmp_path / "app-support"
    app_support.mkdir()
    real_config = tmp_path / "real-helper-config.json"
    real_config.write_text(
        json.dumps({"repoRoot": str(repo), "appSupportDir": str(app_support)}),
        encoding="utf-8",
    )
    real_config.chmod(0o600)
    link = tmp_path / "helper-config.json"
    link.symlink_to(real_config)
    function = _extract_shell_function(SCRIPT.read_text(encoding="utf-8"), "verify_preserved_helper_config")
    script = (
        "set -euo pipefail\n"
        "resolve_repo_python() { command -v python3; }\n"
        f"HELPER_CONFIG_FILE={shlex.quote(str(link))}\n"
        f"HELPER_RUNTIME_REPO_ROOT={shlex.quote(str(repo))}\n"
        f"APP_SUPPORT_DIR={shlex.quote(str(app_support))}\n"
        f"{function}"
        "verify_preserved_helper_config\n"
    )
    completed = subprocess.run(["bash", "-c", script], text=True, capture_output=True, check=False)
    assert completed.returncode != 0

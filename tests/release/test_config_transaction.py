from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
TRANSACTION_SCRIPT = REPO_ROOT / "scripts" / "viventium" / "config_transaction.py"
CLI = REPO_ROOT / "bin" / "viventium"


def extract_shell_function(text: str, name: str) -> str:
    lines = text.splitlines()
    start = next(
        index
        for index, line in enumerate(lines)
        if line.strip() == f"{name}() {{"
    )
    collected: list[str] = []
    depth = 0
    for line in lines[start:]:
        collected.append(line)
        depth += line.count("{")
        depth -= line.count("}")
        if depth == 0:
            break
    return "\n".join(collected) + "\n"


def run_transaction(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(TRANSACTION_SCRIPT), *args],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def transaction_args(app_support: Path, *args: str) -> tuple[str, ...]:
    return (*args, "--app-support-dir", str(app_support))


def replace_secret_references_with_synthetic_values(node: object) -> None:
    if isinstance(node, dict):
        if "secret_ref" in node:
            node.pop("secret_ref")
            node["secret_value"] = "synthetic-non-secret"
        for value in node.values():
            replace_secret_references_with_synthetic_values(value)
    elif isinstance(node, list):
        for value in node:
            replace_secret_references_with_synthetic_values(value)


def test_prepare_merges_input_over_existing_without_dropping_unknown_fields(tmp_path: Path) -> None:
    existing = tmp_path / "existing.yaml"
    incoming = tmp_path / "incoming.yaml"
    candidate = tmp_path / "candidate.yaml"
    existing.write_text(
        yaml.safe_dump(
            {
                "runtime": {
                    "profile": "isolated",
                    "auth": {"allow_registration": False},
                    "future_runtime_field": {"preserve_me": True},
                },
                "integrations": {"telegram": {"enabled": True}},
                "future_top_level": {"owner_choice": "keep"},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    incoming.write_text(
        yaml.safe_dump(
            {
                "runtime": {"profile": "compat"},
                "integrations": {"telegram": {"enabled": False}},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    result = run_transaction(
        "prepare",
        "--existing",
        str(existing),
        "--input",
        str(incoming),
        "--output",
        str(candidate),
        "--app-support-dir",
        str(tmp_path),
    )

    assert result.returncode == 0, result.stderr
    payload = yaml.safe_load(candidate.read_text(encoding="utf-8"))
    assert payload["runtime"]["profile"] == "compat"
    assert payload["runtime"]["auth"]["allow_registration"] is False
    assert payload["runtime"]["future_runtime_field"] == {"preserve_me": True}
    assert payload["integrations"]["telegram"]["enabled"] is False
    assert payload["future_top_level"] == {"owner_choice": "keep"}


def test_apply_creates_private_backup_and_atomic_candidate_copy(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    candidate = tmp_path / "candidate.yaml"
    backup_dir = tmp_path / "backups"
    config.write_text("runtime:\n  profile: isolated\n", encoding="utf-8")
    config.chmod(0o600)
    candidate.write_text("runtime:\n  profile: compat\n", encoding="utf-8")

    result = run_transaction(
        "apply",
        "--candidate",
        str(candidate),
        "--config",
        str(config),
        "--backup-dir",
        str(backup_dir),
        "--app-support-dir",
        str(tmp_path),
    )

    assert result.returncode == 0, result.stderr
    status = json.loads(result.stdout)
    backup = Path(status["backup_path"])
    assert status["had_existing"] is True
    assert yaml.safe_load(config.read_text(encoding="utf-8"))["runtime"]["profile"] == "compat"
    assert backup.read_text(encoding="utf-8") == "runtime:\n  profile: isolated\n"
    assert backup.stat().st_mode & 0o777 == 0o600
    assert backup_dir.stat().st_mode & 0o777 == 0o700
    assert config.stat().st_mode & 0o777 == 0o600
    assert not list(tmp_path.glob(".config.yaml.*.tmp"))


def test_rollback_restores_prior_config_atomically(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    candidate = tmp_path / "candidate.yaml"
    backup_dir = tmp_path / "backups"
    config.write_text("owner: preserved\n", encoding="utf-8")
    candidate.write_text("owner: changed\n", encoding="utf-8")

    applied = run_transaction(
        "apply",
        "--candidate",
        str(candidate),
        "--config",
        str(config),
        "--backup-dir",
        str(backup_dir),
        "--app-support-dir",
        str(tmp_path),
    )
    assert applied.returncode == 0, applied.stderr
    status = json.loads(applied.stdout)

    rolled_back = run_transaction(
        "rollback",
        "--config",
        str(config),
        "--backup",
        status["backup_path"],
        "--had-existing",
        "true",
        "--app-support-dir",
        str(tmp_path),
    )

    assert rolled_back.returncode == 0, rolled_back.stderr
    assert config.read_text(encoding="utf-8") == "owner: preserved\n"
    assert config.stat().st_mode & 0o777 == 0o600


def test_apply_refuses_symlinked_config_without_reading_or_changing_external_file(tmp_path: Path) -> None:
    app_support = tmp_path / "support"
    app_support.mkdir(mode=0o700)
    external = tmp_path / "external-private.yaml"
    external.write_text("private: sentinel\n", encoding="utf-8")
    config = app_support / "config.yaml"
    config.symlink_to(external)
    candidate = app_support / "candidate.yaml"
    candidate.write_text("runtime:\n  profile: isolated\n", encoding="utf-8")

    result = run_transaction(
        "apply",
        "--candidate",
        str(candidate),
        "--config",
        str(config),
        "--backup-dir",
        str(app_support / "backups"),
        "--app-support-dir",
        str(app_support),
    )

    assert result.returncode != 0
    assert external.read_text(encoding="utf-8") == "private: sentinel\n"
    assert not (app_support / "backups").exists()
    assert "private: sentinel" not in result.stdout + result.stderr


def test_apply_refuses_symlinked_backup_directory_without_chmod_or_copy(tmp_path: Path) -> None:
    app_support = tmp_path / "support"
    app_support.mkdir(mode=0o700)
    external = tmp_path / "external-backups"
    external.mkdir(mode=0o755)
    sentinel = external / "sentinel"
    sentinel.write_text("preserved", encoding="utf-8")
    backup_dir = app_support / "backups"
    backup_dir.symlink_to(external, target_is_directory=True)
    config = app_support / "config.yaml"
    config.write_text("owner: preserved\n", encoding="utf-8")
    candidate = app_support / "candidate.yaml"
    candidate.write_text("owner: changed\n", encoding="utf-8")

    result = run_transaction(
        "apply",
        "--candidate",
        str(candidate),
        "--config",
        str(config),
        "--backup-dir",
        str(backup_dir),
        "--app-support-dir",
        str(app_support),
    )

    assert result.returncode != 0
    assert config.read_text(encoding="utf-8") == "owner: preserved\n"
    assert sentinel.read_text(encoding="utf-8") == "preserved"
    assert external.stat().st_mode & 0o777 == 0o755


def test_prepare_refuses_symlinked_candidate_and_symlinked_parent_chain(tmp_path: Path) -> None:
    app_support = tmp_path / "support"
    app_support.mkdir(mode=0o700)
    incoming = tmp_path / "incoming.yaml"
    incoming.write_text("runtime:\n  profile: isolated\n", encoding="utf-8")
    external_file = tmp_path / "external-candidate.yaml"
    external_file.write_text("preserved\n", encoding="utf-8")
    candidate = app_support / "candidate.yaml"
    candidate.symlink_to(external_file)

    candidate_result = run_transaction(
        "prepare",
        "--input",
        str(incoming),
        "--output",
        str(candidate),
        "--app-support-dir",
        str(app_support),
    )

    assert candidate_result.returncode != 0
    assert external_file.read_text(encoding="utf-8") == "preserved\n"

    external_dir = tmp_path / "external-dir"
    external_dir.mkdir()
    linked_parent = app_support / "linked"
    linked_parent.symlink_to(external_dir, target_is_directory=True)
    parent_result = run_transaction(
        "prepare",
        "--input",
        str(incoming),
        "--output",
        str(linked_parent / "candidate.yaml"),
        "--app-support-dir",
        str(app_support),
    )

    assert parent_result.returncode != 0
    assert not (external_dir / "candidate.yaml").exists()


def test_apply_refuses_paths_outside_lexical_app_support_boundary(tmp_path: Path) -> None:
    app_support = tmp_path / "support"
    app_support.mkdir(mode=0o700)
    external_config = tmp_path / "external-config.yaml"
    external_config.write_text("owner: preserved\n", encoding="utf-8")
    candidate = app_support / "candidate.yaml"
    candidate.write_text("owner: changed\n", encoding="utf-8")

    result = run_transaction(
        "apply",
        "--candidate",
        str(candidate),
        "--config",
        str(external_config),
        "--backup-dir",
        str(app_support / "backups"),
        "--app-support-dir",
        str(app_support),
    )

    assert result.returncode != 0
    assert external_config.read_text(encoding="utf-8") == "owner: preserved\n"


def test_cli_headless_paths_use_candidate_instead_of_direct_canonical_output() -> None:
    source = CLI.read_text(encoding="utf-8")

    assert "prepare_config_candidate" in source
    assert "apply_config_candidate" in source
    assert "rollback_config_candidate" in source
    assert 'WIZARD_ARGS=(--output "$CONFIG_CANDIDATE_FILE")' in source
    assert 'scripts/viventium/config_transaction.py' in source
    candidate_path = (
        'ensure_config_candidate_components "$CONFIG_CANDIDATE_FILE"'
    )
    compiler_path = (
        '"$PYTHON_BIN" "$REPO_ROOT/scripts/viventium/config_compiler.py"'
    )
    candidate_function = extract_shell_function(
        source,
        "prepare_config_candidate",
    )
    assert candidate_function.index(candidate_path) < candidate_function.index(
        compiler_path
    )


def test_missing_fresh_clone_agent_bundle_bootstraps_candidate_components_before_compile(
    tmp_path: Path,
) -> None:
    source = CLI.read_text(encoding="utf-8")
    function = extract_shell_function(
        source,
        "ensure_config_candidate_components",
    )
    repo = tmp_path / "repo"
    (repo / "scripts" / "viventium").mkdir(parents=True)
    candidate = tmp_path / "candidate.yaml"
    candidate.write_text(
        "version: 1\ninstall:\n  mode: native\n",
        encoding="utf-8",
    )
    lock_file = repo / "components.lock.json"
    lock_file.write_text('{"version":1,"components":[]}\n', encoding="utf-8")
    calls = tmp_path / "bootstrap-calls"
    fake_python = tmp_path / "fake-python"
    fake_python.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "if [[ \"${1:-}\" == *repo_path_safety.py ]]; then exit 0; fi\n"
        f"printf '%s\\n' \"$*\" >> {str(calls)!r}\n"
        "mkdir -p \"$TEST_REPO/viventium_v0_4/LibreChat/viventium/source_of_truth\"\n"
        "printf 'mainAgent: []\\n' > "
        "\"$TEST_REPO/viventium_v0_4/LibreChat/viventium/source_of_truth/"
        "local.viventium-agents.yaml\"\n",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                f"REPO_ROOT={str(repo)!r}\n"
                f"LOCK_FILE={str(lock_file)!r}\n"
                f"PYTHON_BIN={str(fake_python)!r}\n"
                f"TEST_REPO={str(repo)!r}\n"
                "export TEST_REPO\n"
                "refresh_repo_python() { :; }\n"
                f"{function}"
                f"ensure_config_candidate_components {str(candidate)!r}\n"
                f"ensure_config_candidate_components {str(candidate)!r}\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    recorded = calls.read_text(encoding="utf-8").splitlines()
    assert len(recorded) == 2
    for call in recorded:
        assert "--repo-root" in call
        assert f"--config {candidate}" in call
        assert "--lock-file" in call


def test_partial_candidate_component_bootstrap_retries_even_after_bundle_appears(
    tmp_path: Path,
) -> None:
    source = CLI.read_text(encoding="utf-8")
    function = extract_shell_function(
        source,
        "ensure_config_candidate_components",
    )
    repo = tmp_path / "repo"
    (repo / "scripts" / "viventium").mkdir(parents=True)
    candidate = tmp_path / "candidate.yaml"
    candidate.write_text(
        "version: 1\n"
        "integrations:\n"
        "  glasshive:\n"
        "    enabled: true\n",
        encoding="utf-8",
    )
    lock_file = repo / "components.lock.json"
    lock_file.write_text('{"version":1,"components":[]}\n', encoding="utf-8")
    calls = tmp_path / "bootstrap-calls"
    fake_python = tmp_path / "fake-python"
    fake_python.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "if [[ \"${1:-}\" == *repo_path_safety.py ]]; then exit 0; fi\n"
        f"printf 'call\\n' >> {str(calls)!r}\n"
        "mkdir -p \"$TEST_REPO/viventium_v0_4/LibreChat/viventium/source_of_truth\"\n"
        "printf 'mainAgent: []\\n' > "
        "\"$TEST_REPO/viventium_v0_4/LibreChat/viventium/source_of_truth/"
        "local.viventium-agents.yaml\"\n"
        f"if [[ $(wc -l < {str(calls)!r}) -eq 1 ]]; then exit 9; fi\n",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -uo pipefail\n"
                f"REPO_ROOT={str(repo)!r}\n"
                f"LOCK_FILE={str(lock_file)!r}\n"
                f"PYTHON_BIN={str(fake_python)!r}\n"
                f"TEST_REPO={str(repo)!r}\n"
                "export TEST_REPO\n"
                "refresh_repo_python() { :; }\n"
                f"{function}"
                "first=0\n"
                f"ensure_config_candidate_components {str(candidate)!r} || first=$?\n"
                "second=0\n"
                f"ensure_config_candidate_components {str(candidate)!r} || second=$?\n"
                "printf '%s|%s\\n' \"$first\" \"$second\"\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip().endswith("1|0")
    assert calls.read_text(encoding="utf-8").splitlines() == ["call", "call"]


def test_candidate_component_bootstrap_rejects_internal_agent_bundle_parent_symlink(
    tmp_path: Path,
) -> None:
    source = CLI.read_text(encoding="utf-8")
    function = extract_shell_function(
        source,
        "ensure_config_candidate_components",
    )
    repo = tmp_path / "repo"
    scripts = repo / "scripts" / "viventium"
    scripts.mkdir(parents=True)
    (scripts / "repo_path_safety.py").write_bytes(
        (REPO_ROOT / "scripts" / "viventium" / "repo_path_safety.py").read_bytes()
    )
    (scripts / "bootstrap_components.py").write_text(
        "#!/usr/bin/env python3\nraise SystemExit(0)\n",
        encoding="utf-8",
    )
    candidate = tmp_path / "candidate.yaml"
    candidate.write_text("version: 1\n", encoding="utf-8")
    lock_file = repo / "components.lock.json"
    lock_file.write_text('{"version":1,"components":[]}\n', encoding="utf-8")
    librechat = repo / "viventium_v0_4" / "LibreChat"
    (librechat / "viventium").mkdir(parents=True)
    external = tmp_path / "external-source-of-truth"
    external.mkdir()
    (external / "local.viventium-agents.yaml").write_text(
        "mainAgent: []\n",
        encoding="utf-8",
    )
    (librechat / "viventium" / "source_of_truth").symlink_to(
        external,
        target_is_directory=True,
    )

    completed = subprocess.run(
        [
            "bash",
            "-lc",
            (
                "set -euo pipefail\n"
                f"REPO_ROOT={str(repo)!r}\n"
                f"LOCK_FILE={str(lock_file)!r}\n"
                f"PYTHON_BIN={sys.executable!r}\n"
                "refresh_repo_python() { :; }\n"
                f"{function}"
                f"ensure_config_candidate_components {str(candidate)!r}\n"
            ),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "unsafe linked path" in completed.stderr
    assert (
        external / "local.viventium-agents.yaml"
    ).read_text(encoding="utf-8") == "mainAgent: []\n"


def test_headless_configure_preserves_existing_fields_and_compiles_candidate(tmp_path: Path) -> None:
    home = tmp_path / "home"
    app_support = home / "Library" / "Application Support" / "Viventium"
    config = app_support / "config.yaml"
    runtime = app_support / "runtime"
    app_support.mkdir(parents=True)

    existing = yaml.safe_load((REPO_ROOT / "config.minimal.example.yaml").read_text(encoding="utf-8"))
    replace_secret_references_with_synthetic_values(existing)
    existing["runtime"]["memory_hardening"]["enabled"] = False
    existing["runtime"]["future_runtime_field"] = {"preserve_me": True}
    existing["future_top_level"] = {"owner_choice": "keep"}
    config.write_text(yaml.safe_dump(existing, sort_keys=False), encoding="utf-8")

    incoming = tmp_path / "incoming.yaml"
    incoming.write_text("runtime:\n  log_level: debug\n", encoding="utf-8")
    env = {
        **os.environ,
        "HOME": str(home),
        "VIVENTIUM_APP_SUPPORT_DIR": str(app_support),
        "VIVENTIUM_CONFIG_FILE": str(config),
        "VIVENTIUM_RUNTIME_DIR": str(runtime),
        "VIVENTIUM_PYTHON_BIN": sys.executable,
    }

    result = subprocess.run(
        [str(CLI), "configure", "--headless", "--config-input", str(incoming)],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    updated = yaml.safe_load(config.read_text(encoding="utf-8"))
    assert updated["runtime"]["log_level"] == "debug"
    assert updated["runtime"]["future_runtime_field"] == {"preserve_me": True}
    assert updated["future_top_level"] == {"owner_choice": "keep"}
    assert (runtime / "runtime.env").is_file()
    backups = list((app_support / "state" / "config-backups").glob("config-*.yaml"))
    assert len(backups) == 1
    assert yaml.safe_load(backups[0].read_text(encoding="utf-8"))["runtime"]["log_level"] == "info"
    assert not list((app_support / "state" / "config-candidates").glob("attempt.*"))


def test_headless_configure_validation_failure_leaves_canonical_config_unchanged(tmp_path: Path) -> None:
    home = tmp_path / "home"
    app_support = home / "Library" / "Application Support" / "Viventium"
    config = app_support / "config.yaml"
    runtime = app_support / "runtime"
    app_support.mkdir(parents=True)

    existing = yaml.safe_load((REPO_ROOT / "config.minimal.example.yaml").read_text(encoding="utf-8"))
    replace_secret_references_with_synthetic_values(existing)
    existing["runtime"]["memory_hardening"]["enabled"] = False
    existing["future_top_level"] = {"owner_choice": "keep"}
    config.write_text(yaml.safe_dump(existing, sort_keys=False), encoding="utf-8")
    before = config.read_bytes()

    incoming = tmp_path / "invalid.yaml"
    incoming.write_text(
        "integrations:\n"
        "  telegram_codex:\n"
        "    enabled: false\n"
        "    secret_value: synthetic-dormant-token\n",
        encoding="utf-8",
    )
    env = {
        **os.environ,
        "HOME": str(home),
        "VIVENTIUM_APP_SUPPORT_DIR": str(app_support),
        "VIVENTIUM_CONFIG_FILE": str(config),
        "VIVENTIUM_RUNTIME_DIR": str(runtime),
        "VIVENTIUM_PYTHON_BIN": sys.executable,
    }

    result = subprocess.run(
        [str(CLI), "configure", "--headless", "--config-input", str(incoming)],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "Traceback" not in result.stderr
    assert "Config candidate was not created" in result.stderr
    assert config.read_bytes() == before
    assert not any(runtime.iterdir())
    assert not (app_support / "state" / "config-backups").exists()
    assert not list((app_support / "state" / "config-candidates").glob("attempt.*"))

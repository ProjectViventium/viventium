from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER_PATH = REPO_ROOT / "scripts" / "viventium" / "viventium_health_runtime.py"


def load_installer():
    spec = importlib.util.spec_from_file_location("viventium_health_runtime", INSTALLER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def health_lock_entry() -> dict:
    payload = json.loads((REPO_ROOT / "components.lock.json").read_text(encoding="utf-8"))
    return next(row for row in payload["components"] if row["name"] == "Viventium-Health")


def test_health_component_pin_matches_the_reviewed_component_head() -> None:
    entry = health_lock_entry()
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT / entry["path"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    assert entry["ref"] == head


def test_health_runtime_installer_rejects_component_pin_drift() -> None:
    installer = load_installer()
    entry = {**health_lock_entry(), "ref": "0" * 40}

    with pytest.raises(installer.HealthRuntimeError, match="lock pin"):
        installer._verify_component_checkout(REPO_ROOT, entry)


def test_health_runtime_installer_rejects_unverifiable_component_source(tmp_path: Path) -> None:
    installer = load_installer()
    entry = {**health_lock_entry(), "path": "component-without-git"}
    component = tmp_path / entry["path"]
    (component / "src" / "viventium_health").mkdir(parents=True)

    with pytest.raises(installer.HealthRuntimeError, match="no git metadata"):
        installer._verify_component_checkout(tmp_path, entry)


def test_health_runtime_package_hash_rejects_symlinks(tmp_path: Path) -> None:
    installer = load_installer()
    source = tmp_path / "source"
    source.mkdir()
    outside = tmp_path / "outside.py"
    outside.write_text("PRIVATE = True\n", encoding="utf-8")
    (source / "linked.py").symlink_to(outside)

    with pytest.raises(installer.HealthRuntimeError, match="unsupported symlink"):
        installer._package_hash(source)


def test_health_runtime_install_is_private_self_contained_and_reads_empty_archive(
    tmp_path: Path,
) -> None:
    installer = load_installer()
    app_support = tmp_path / "Application Support" / "Viventium"

    installed = installer.install_runtime(repo_root=REPO_ROOT, app_support_dir=app_support)

    executable = app_support / "health" / "runtime" / "bin" / "viventium-health"
    assert installed["status"] == "installed"
    assert executable.is_file()
    assert stat.S_IMODE(executable.stat().st_mode) == 0o700
    version = subprocess.run(
        [str(executable), "--version"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert version.stdout.strip() == "viventium-health 0.1.0"

    state_root = app_support / "health-state"
    listed = subprocess.run(
        [str(executable), "--root", str(state_root), "runs", "--provider", "whoop"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(listed.stdout) == {"runs": []}
    assert stat.S_IMODE(state_root.stat().st_mode) == 0o700

    manifest = json.loads(
        (app_support / "health" / "runtime" / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["componentRef"] == health_lock_entry()["ref"]
    assert manifest["packageSha256"]
    assert "repoRoot" not in manifest
    assert "sourcePath" not in manifest


def test_health_runtime_reinstall_preserves_archive_and_replaces_runtime(tmp_path: Path) -> None:
    installer = load_installer()
    app_support = tmp_path / "Viventium"
    installer.install_runtime(repo_root=REPO_ROOT, app_support_dir=app_support)
    evidence = app_support / "health" / "archive" / "keep.body.json"
    evidence.parent.mkdir(parents=True)
    evidence.write_bytes(b'{"private":"evidence"}\n')
    os.chmod(evidence, 0o600)
    stale = app_support / "health" / "runtime" / "stale.txt"
    stale.write_text("old\n", encoding="utf-8")
    manifest_path = app_support / "health" / "runtime" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["packageSha256"] = "corrupt"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = installer.install_runtime(repo_root=REPO_ROOT, app_support_dir=app_support)

    assert result["status"] == "installed"
    assert evidence.read_bytes() == b'{"private":"evidence"}\n'
    assert not stale.exists()
    assert not list((app_support / "health").glob(".runtime.install-*"))
    assert not list((app_support / "health").glob(".runtime.previous-*"))


def test_health_runtime_install_reuses_matching_artifact_without_rebuild(tmp_path: Path) -> None:
    installer = load_installer()
    app_support = tmp_path / "Viventium"
    first = installer.install_runtime(repo_root=REPO_ROOT, app_support_dir=app_support)
    executable = app_support / "health" / "runtime" / "bin" / "viventium-health"
    first_inode = executable.stat().st_ino

    second = installer.install_runtime(repo_root=REPO_ROOT, app_support_dir=app_support)

    assert first["status"] == "installed"
    assert second["status"] == "ready"
    assert second["installedAt"] == first["installedAt"]
    assert executable.stat().st_ino == first_inode


def test_health_runtime_install_rebuilds_a_tampered_installed_package(tmp_path: Path) -> None:
    installer = load_installer()
    app_support = tmp_path / "Viventium"
    installer.install_runtime(repo_root=REPO_ROOT, app_support_dir=app_support)
    package_files = list(
        (app_support / "health" / "runtime" / "lib").glob(
            "python*/site-packages/viventium_health/__init__.py"
        )
    )
    assert len(package_files) == 1
    package_files[0].write_text("__version__ = 'tampered'\n", encoding="utf-8")

    result = installer.install_runtime(repo_root=REPO_ROOT, app_support_dir=app_support)

    assert result["status"] == "installed"
    assert package_files[0].read_text(encoding="utf-8") != "__version__ = 'tampered'\n"


def test_health_runtime_status_fails_closed_when_artifact_is_missing(tmp_path: Path) -> None:
    installer = load_installer()

    status = installer.runtime_status(app_support_dir=tmp_path / "Viventium")

    assert status == {
        "status": "missing",
        "executable": False,
        "manifest": False,
        "componentRef": None,
    }


def test_public_cli_materializes_and_runs_the_health_component(tmp_path: Path) -> None:
    app_support = tmp_path / "Viventium"
    env = os.environ.copy()
    env["VIVENTIUM_APP_SUPPORT_DIR"] = str(app_support)
    env["VIVENTIUM_DISABLE_ACTIVE_CHECKOUT_REEXEC"] = "1"

    result = subprocess.run(
        [str(REPO_ROOT / "bin" / "viventium"), "health", "--version"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "viventium-health 0.1.0"
    assert (app_support / "health" / "runtime" / "manifest.json").is_file()


def test_public_cli_health_help_advertises_full_history_import() -> None:
    result = subprocess.run(
        [str(REPO_ROOT / "bin" / "viventium"), "health", "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr
    assert "health pull whoop --all-history" in result.stdout
    assert "health import whoop-evidence" in result.stdout
    assert "--all-history cannot be combined with --lookback-days" in result.stdout


def test_installed_health_runtime_serves_only_bounded_read_tools(tmp_path: Path) -> None:
    installer = load_installer()
    app_support = tmp_path / "Viventium"
    installer.install_runtime(repo_root=REPO_ROOT, app_support_dir=app_support)
    executable = app_support / "health" / "runtime" / "bin" / "viventium-health"
    state_root = app_support / "health-state"
    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "release-qa", "version": "1"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    ]

    result = subprocess.run(
        [str(executable), "--root", str(state_root), "mcp"],
        input="".join(json.dumps(message) + "\n" for message in messages),
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    responses = [json.loads(line) for line in result.stdout.splitlines()]
    tools = responses[1]["result"]["tools"]
    assert {tool["name"] for tool in tools} == {
        "health_list_runs",
        "health_list_records",
        "health_read_image",
        "health_read_record",
    }
    assert all("pull" not in tool["name"] and "delete" not in tool["name"] for tool in tools)


def test_install_upgrade_and_start_paths_reconcile_health_runtime_after_bootstrap() -> None:
    source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")

    assert source.count("ensure_viventium_health_runtime") >= 5
    assert "bootstrap_components\n    ensure_viventium_health_runtime" in source
    assert "bootstrap_components_upgrade_checked\n    ensure_viventium_health_runtime" in source
    assert "bootstrap_components --prefer-existing-checkout-head\n    ensure_viventium_health_runtime" in source

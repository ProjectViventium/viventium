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


@pytest.fixture
def pinned_health_repo(tmp_path: Path) -> tuple[Path, str]:
    repo_root = tmp_path / "repo"
    component = repo_root / "component"
    package = component / "src" / "viventium_health"
    package.mkdir(parents=True)
    (component / "pyproject.toml").write_text(
        "[project]\nname = 'viventium-health'\nversion = '0.1.0'\n",
        encoding="utf-8",
    )
    (package / "__init__.py").write_text("__version__ = '0.1.0'\n", encoding="utf-8")
    (package / "__main__.py").write_text(
        "import sys\n"
        "if sys.argv[1:] == ['--version']:\n"
        "    print('viventium-health 0.1.0')\n"
        "else:\n"
        "    raise SystemExit(2)\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q"], cwd=component, check=True)
    subprocess.run(["git", "add", "pyproject.toml", "src"], cwd=component, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Viventium Release Tests",
            "-c",
            "user.email=release-tests@example.com",
            "commit",
            "-qm",
            "synthetic health component",
        ],
        cwd=component,
        check=True,
    )
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=component,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    (repo_root / "components.lock.json").write_text(
        json.dumps(
            {
                "components": [
                    {
                        "name": "Viventium-Health",
                        "path": "component",
                        "origin": "https://example.com/viventium-health.git",
                        "ref": head,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return repo_root, head


def test_health_component_lock_is_public_and_immutable() -> None:
    entry = health_lock_entry()

    assert entry["path"] == "viventium_v0_4/Viventium-Health"
    assert entry["origin"] == "https://github.com/ProjectViventium/Viventium-Health.git"
    assert len(entry["ref"]) == 40


def test_health_runtime_installer_accepts_bootstrap_validated_branch_source(
    pinned_health_repo: tuple[Path, str],
) -> None:
    installer = load_installer()
    repo_root, _ = pinned_health_repo
    entry = {**installer._component_entry(repo_root), "ref": "0" * 40}

    verification = installer._verify_component_checkout(repo_root, entry)

    assert verification["sourceVerification"] == "bootstrap_validated_git"
    assert verification["lockRef"] == "0" * 40
    assert len(verification["sourceRevision"]) == 40


def test_health_runtime_installer_accepts_bootable_vendored_component_source(tmp_path: Path) -> None:
    installer = load_installer()
    entry = {**health_lock_entry(), "path": "component-without-git"}
    component = tmp_path / entry["path"]
    package = component / "src" / "viventium_health"
    package.mkdir(parents=True)
    (component / "pyproject.toml").write_text("[project]\nname='viventium-health'\n", encoding="utf-8")
    (package / "__main__.py").write_text("raise SystemExit(0)\n", encoding="utf-8")

    verification = installer._verify_component_checkout(tmp_path, entry)

    assert verification == {
        "sourceVerification": "bootstrap_validated_vendored",
        "sourceRevision": None,
        "lockRef": entry["ref"],
    }


def test_health_runtime_installer_records_dirty_bootstrap_validated_source(
    pinned_health_repo: tuple[Path, str],
) -> None:
    installer = load_installer()
    repo_root, _ = pinned_health_repo
    package_init = repo_root / "component" / "src" / "viventium_health" / "__init__.py"
    package_init.write_text("__version__ = '0.1.0-local'\n", encoding="utf-8")

    verification = installer._verify_component_checkout(
        repo_root,
        installer._component_entry(repo_root),
    )

    assert verification["sourceVerification"] == "bootstrap_validated_dirty_git"


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
    pinned_health_repo: tuple[Path, str],
) -> None:
    installer = load_installer()
    repo_root, component_ref = pinned_health_repo
    app_support = tmp_path / "Application Support" / "Viventium"

    installed = installer.install_runtime(repo_root=repo_root, app_support_dir=app_support)

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

    manifest = json.loads(
        (app_support / "health" / "runtime" / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["componentRef"] == component_ref
    assert manifest["lockRef"] == component_ref
    assert manifest["sourceRevision"] == component_ref
    assert manifest["sourceVerification"] == "pinned_git"
    assert manifest["packageSha256"]
    assert "repoRoot" not in manifest
    assert "sourcePath" not in manifest


def test_health_runtime_reinstall_preserves_archive_and_replaces_runtime(
    tmp_path: Path,
    pinned_health_repo: tuple[Path, str],
) -> None:
    installer = load_installer()
    repo_root, _ = pinned_health_repo
    app_support = tmp_path / "Viventium"
    installer.install_runtime(repo_root=repo_root, app_support_dir=app_support)
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

    result = installer.install_runtime(repo_root=repo_root, app_support_dir=app_support)

    assert result["status"] == "installed"
    assert evidence.read_bytes() == b'{"private":"evidence"}\n'
    assert not stale.exists()
    assert not list((app_support / "health").glob(".runtime.install-*"))
    assert not list((app_support / "health").glob(".runtime.previous-*"))


def test_health_runtime_install_reuses_matching_artifact_without_rebuild(
    tmp_path: Path,
    pinned_health_repo: tuple[Path, str],
) -> None:
    installer = load_installer()
    repo_root, _ = pinned_health_repo
    app_support = tmp_path / "Viventium"
    first = installer.install_runtime(repo_root=repo_root, app_support_dir=app_support)
    executable = app_support / "health" / "runtime" / "bin" / "viventium-health"
    first_inode = executable.stat().st_ino

    second = installer.install_runtime(repo_root=repo_root, app_support_dir=app_support)

    assert first["status"] == "installed"
    assert second["status"] == "ready"
    assert second["installedAt"] == first["installedAt"]
    assert executable.stat().st_ino == first_inode


def test_health_runtime_install_rebuilds_a_tampered_installed_package(
    tmp_path: Path,
    pinned_health_repo: tuple[Path, str],
) -> None:
    installer = load_installer()
    repo_root, _ = pinned_health_repo
    app_support = tmp_path / "Viventium"
    installer.install_runtime(repo_root=repo_root, app_support_dir=app_support)
    package_files = list(
        (app_support / "health" / "runtime" / "lib").glob(
            "python*/site-packages/viventium_health/__init__.py"
        )
    )
    assert len(package_files) == 1
    package_files[0].write_text("__version__ = 'tampered'\n", encoding="utf-8")

    result = installer.install_runtime(repo_root=repo_root, app_support_dir=app_support)

    assert result["status"] == "installed"
    assert package_files[0].read_text(encoding="utf-8") != "__version__ = 'tampered'\n"


def test_health_runtime_install_hashes_non_python_package_assets(
    tmp_path: Path,
    pinned_health_repo: tuple[Path, str],
) -> None:
    installer = load_installer()
    repo_root, _ = pinned_health_repo
    source_asset = repo_root / "component" / "src" / "viventium_health" / "schema.json"
    source_asset.write_text('{"schema":1}\n', encoding="utf-8")
    app_support = tmp_path / "Viventium"
    installer.install_runtime(repo_root=repo_root, app_support_dir=app_support)
    installed_assets = list(
        (app_support / "health" / "runtime" / "lib").glob(
            "python*/site-packages/viventium_health/schema.json"
        )
    )
    assert len(installed_assets) == 1
    installed_assets[0].write_text('{"schema":"tampered"}\n', encoding="utf-8")

    result = installer.install_runtime(repo_root=repo_root, app_support_dir=app_support)

    assert result["status"] == "installed"
    assert installed_assets[0].read_text(encoding="utf-8") == '{"schema":1}\n'


def test_health_runtime_install_rebuilds_when_wrapper_python_is_dead(
    tmp_path: Path,
    pinned_health_repo: tuple[Path, str],
) -> None:
    installer = load_installer()
    repo_root, _ = pinned_health_repo
    app_support = tmp_path / "Viventium"
    installer.install_runtime(repo_root=repo_root, app_support_dir=app_support)
    runtime = app_support / "health" / "runtime"
    python = runtime / "bin" / "python"
    python.unlink()
    python.symlink_to(runtime / "missing-python")

    assert installer.runtime_status(app_support_dir=app_support)["status"] == "invalid"

    rebuilt = installer.install_runtime(repo_root=repo_root, app_support_dir=app_support)

    assert rebuilt["status"] == "installed"
    assert installer.runtime_status(app_support_dir=app_support)["status"] == "ready"


def test_health_runtime_install_recovers_interrupted_swap(
    tmp_path: Path,
    pinned_health_repo: tuple[Path, str],
) -> None:
    installer = load_installer()
    repo_root, _ = pinned_health_repo
    app_support = tmp_path / "Viventium"
    installer.install_runtime(repo_root=repo_root, app_support_dir=app_support)
    health_root = app_support / "health"
    runtime = health_root / "runtime"
    backup = health_root / ".runtime.previous-interrupted"
    os.replace(runtime, backup)
    stale = health_root / ".runtime.install-interrupted"
    stale.mkdir(mode=0o700)

    recovered = installer.install_runtime(repo_root=repo_root, app_support_dir=app_support)

    assert recovered["status"] == "ready"
    assert runtime.is_dir()
    assert not backup.exists()
    assert not stale.exists()


def test_health_runtime_status_fails_closed_when_artifact_is_missing(tmp_path: Path) -> None:
    installer = load_installer()

    status = installer.runtime_status(app_support_dir=tmp_path / "Viventium")

    assert status == {
        "status": "missing",
        "executable": False,
        "manifest": False,
        "componentRef": None,
    }


def test_install_upgrade_and_start_paths_reconcile_health_runtime_after_bootstrap() -> None:
    source = (REPO_ROOT / "bin" / "viventium").read_text(encoding="utf-8")

    assert source.count("ensure_viventium_health_runtime") >= 5
    assert (
        "bootstrap_components\n"
        '    CURRENT_INSTALL_STAGE="health-runtime"\n'
        '    write_install_stage "$CURRENT_INSTALL_STAGE"\n'
        "    ensure_viventium_health_runtime"
    ) in source
    assert "bootstrap_components_upgrade_checked\n    ensure_viventium_health_runtime" in source
    assert "bootstrap_components --prefer-existing-checkout-head\n    ensure_viventium_health_runtime" in source
    assert 'CURRENT_INSTALL_STAGE="health-runtime"' in source
    assert 'if [[ "$BOOTSTRAP_VALIDATE_ONLY" != "1" ]]' in source

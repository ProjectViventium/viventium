from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
BUNDLE_SCRIPT = REPO_ROOT / "scripts" / "viventium" / "continuity_bundle.py"
RESTORE_SCRIPT = REPO_ROOT / "scripts" / "viventium" / "restore.sh"


def load_bundle_module():
    spec = importlib.util.spec_from_file_location("viventium_continuity_bundle", BUNDLE_SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def artifact_row(root: Path, relative: str, domain: str, role: str) -> dict:
    contracts = {
        "canonical_config": ("application/yaml", "file_copy"),
        "mongo_archive": ("application/gzip", "mongodump_archive"),
        "user_files_archive": ("application/gzip", "archive"),
        "schedules_database": ("application/vnd.sqlite3", "sqlite_backup"),
        "channel_state_archive": ("application/gzip", "archive"),
    }
    path = root / relative
    media_type, method = contracts[role]
    row = {
        "path": relative,
        "domain": domain,
        "role": role,
        "mediaType": media_type,
        "captureMethod": method,
        "schemaVersion": 1,
        "size": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    if media_type == "application/gzip":
        try:
            row["uncompressedSize"] = len(gzip.decompress(path.read_bytes()))
        except (gzip.BadGzipFile, EOFError):
            row["uncompressedSize"] = len(b"synthetic-mongodump-archive")
    return row


def make_complete_bundle(root: Path, *, kind: str = "complete") -> Path:
    root.mkdir(parents=True)
    (root / ".viventium-recoverable").write_text("v1\n", encoding="utf-8")
    config = root / "config" / "config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text("version: 1\ninstall:\n  mode: native\n", encoding="utf-8")
    mongo = root / "mongo" / "viventium.archive.gz"
    mongo.parent.mkdir(parents=True)
    mongo.write_bytes(gzip.compress(b"synthetic-mongodump-archive"))
    schedules = root / "schedules" / "schedules.db"
    schedules.parent.mkdir(parents=True)
    connection = sqlite3.connect(schedules)
    connection.execute("CREATE TABLE scheduled_tasks (id TEXT PRIMARY KEY, active INTEGER NOT NULL)")
    connection.execute("INSERT INTO scheduled_tasks (id, active) VALUES ('synthetic-task', 1)")
    connection.commit()
    connection.close()
    artifacts = [
        artifact_row(root, "config/config.yaml", "config", "canonical_config"),
        artifact_row(root, "mongo/viventium.archive.gz", "mongo", "mongo_archive"),
        artifact_row(root, "schedules/schedules.db", "schedules", "schedules_database"),
    ]
    payload = {
        "schemaVersion": 1,
        "bundleKind": kind,
        "createdAt": "2026-07-19T00:00:00Z",
        "domains": [
            {"name": "config", "status": "captured", "policy": "restore", "artifacts": ["config/config.yaml"]},
            {"name": "mongo", "status": "captured", "policy": "restore", "artifacts": ["mongo/viventium.archive.gz"]},
            {"name": "files", "status": "empty", "policy": "restore", "artifacts": []},
            {"name": "schedules", "status": "captured", "policy": "restore", "artifacts": ["schedules/schedules.db"]},
            {"name": "recall", "status": "rebuild_required", "policy": "rebuild_derived", "artifacts": []},
            {"name": "auth", "status": "reauth_required", "policy": "reauth_required", "artifacts": []},
            {"name": "channels", "status": "empty", "policy": "restore", "artifacts": []},
        ],
        "artifacts": artifacts,
    }
    (root / "recoverable-manifest.json").write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )
    return root


def rewrite_manifest(root: Path, mutator) -> None:
    path = root / "recoverable-manifest.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    mutator(payload)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_complete_bundle_validates_structure_without_claiming_restore_proof(tmp_path: Path) -> None:
    bundle = load_bundle_module()
    root = make_complete_bundle(tmp_path / "bundle")

    result = bundle.validate_bundle(root)

    assert result["declaredComplete"] is True
    assert result["recoverable"] is False
    assert result["restoreEngine"] == "not_implemented"
    assert result["semanticValidation"] == "not_performed"
    assert result["bundleKind"] == "complete"
    assert result["artifactCount"] == 3
    assert [domain["name"] for domain in result["domains"]] == list(bundle.DOMAIN_CONTRACTS)


def test_canonical_config_version_is_independent_from_bundle_schema_version(tmp_path: Path) -> None:
    bundle = load_bundle_module()
    root = make_complete_bundle(tmp_path / "bundle")
    bundle.SCHEMA_VERSION = 2

    bundle.validate_artifact_content(root / "config" / "config.yaml", "canonical_config")


def test_bundle_requires_positive_marker_and_complete_kind(tmp_path: Path) -> None:
    bundle = load_bundle_module()
    root = make_complete_bundle(tmp_path / "bundle", kind="partial")
    (root / ".viventium-recoverable").unlink()

    with pytest.raises(bundle.BundleValidationError, match="positive producer completeness marker") as missing:
        bundle.validate_bundle(root)
    assert missing.value.code == "missing_recoverable_marker"

    (root / ".viventium-recoverable").write_text("v1\n", encoding="utf-8")
    with pytest.raises(bundle.BundleValidationError, match="not declared complete") as partial:
        bundle.validate_bundle(root)
    assert partial.value.code == "bundle_not_complete"


def test_bundle_requires_every_domain_once(tmp_path: Path) -> None:
    bundle = load_bundle_module()
    root = make_complete_bundle(tmp_path / "bundle")
    rewrite_manifest(root, lambda payload: payload["domains"].pop())

    with pytest.raises(bundle.BundleValidationError) as missing:
        bundle.validate_bundle(root)
    assert missing.value.code == "incomplete_domains"

    root = make_complete_bundle(tmp_path / "duplicate")
    rewrite_manifest(root, lambda payload: payload["domains"].append(dict(payload["domains"][0])))
    with pytest.raises(bundle.BundleValidationError) as duplicate:
        bundle.validate_bundle(root)
    assert duplicate.value.code == "duplicate_domain"


def test_bundle_rejects_checksum_size_and_content_spoofing(tmp_path: Path) -> None:
    bundle = load_bundle_module()
    root = make_complete_bundle(tmp_path / "checksum")
    (root / "config" / "config.yaml").write_text("version: broken\n", encoding="utf-8")
    with pytest.raises(bundle.BundleValidationError) as checksum:
        bundle.validate_bundle(root)
    assert checksum.value.code in {"artifact_size_mismatch", "artifact_checksum_mismatch"}

    root = make_complete_bundle(tmp_path / "content")
    mongo = root / "mongo" / "viventium.archive.gz"
    mongo.write_bytes(b"not-gzip")
    rewrite_manifest(
        root,
        lambda payload: payload["artifacts"].__setitem__(
            1,
            artifact_row(root, "mongo/viventium.archive.gz", "mongo", "mongo_archive"),
        ),
    )
    with pytest.raises(bundle.BundleValidationError) as content:
        bundle.validate_bundle(root)
    assert content.value.code == "invalid_archive_artifact"

    root = make_complete_bundle(tmp_path / "truncated-gzip")
    mongo = root / "mongo" / "viventium.archive.gz"
    mongo.write_bytes(gzip.compress(b"synthetic-mongodump-archive")[:-2])
    rewrite_manifest(
        root,
        lambda payload: payload["artifacts"].__setitem__(
            1,
            artifact_row(root, "mongo/viventium.archive.gz", "mongo", "mongo_archive"),
        ),
    )
    with pytest.raises(bundle.BundleValidationError) as truncated:
        bundle.validate_bundle(root)
    assert truncated.value.code == "invalid_archive_artifact"


def test_bundle_rejects_boolean_versions_and_gzip_bomb_declarations(tmp_path: Path) -> None:
    bundle = load_bundle_module()
    boolean_schema = make_complete_bundle(tmp_path / "boolean-schema")
    rewrite_manifest(boolean_schema, lambda payload: payload.__setitem__("schemaVersion", True))
    with pytest.raises(bundle.BundleValidationError) as schema_error:
        bundle.validate_bundle(boolean_schema)
    assert schema_error.value.code == "unsupported_schema"

    boolean_artifact_schema = make_complete_bundle(tmp_path / "boolean-artifact")
    rewrite_manifest(
        boolean_artifact_schema,
        lambda payload: payload["artifacts"][0].__setitem__("schemaVersion", True),
    )
    with pytest.raises(bundle.BundleValidationError) as artifact_error:
        bundle.validate_bundle(boolean_artifact_schema)
    assert artifact_error.value.code == "invalid_artifact_contract"

    bomb = make_complete_bundle(tmp_path / "bomb")
    rewrite_manifest(
        bomb,
        lambda payload: payload["artifacts"][1].__setitem__("uncompressedSize", 10**15),
    )
    with pytest.raises(bundle.BundleValidationError) as bomb_error:
        bundle.validate_bundle(bomb)
    assert bomb_error.value.code == "archive_expansion_limit"

    boolean_config = make_complete_bundle(tmp_path / "boolean-config")
    config_path = boolean_config / "config" / "config.yaml"
    config_path.write_text("version: true\ninstall:\n  mode: native\n", encoding="utf-8")
    rewrite_manifest(
        boolean_config,
        lambda payload: payload["artifacts"].__setitem__(
            0,
            artifact_row(boolean_config, "config/config.yaml", "config", "canonical_config"),
        ),
    )
    with pytest.raises(bundle.BundleValidationError) as config_error:
        bundle.validate_bundle(boolean_config)
    assert config_error.value.code == "invalid_config_artifact"


def test_bundle_rejects_traversal_case_collision_symlink_hardlink_and_undeclared_file(tmp_path: Path) -> None:
    bundle = load_bundle_module()
    traversal = make_complete_bundle(tmp_path / "traversal")
    rewrite_manifest(
        traversal,
        lambda payload: payload["artifacts"][0].__setitem__("path", "../config.yaml"),
    )
    with pytest.raises(bundle.BundleValidationError) as traversal_error:
        bundle.validate_bundle(traversal)
    assert traversal_error.value.code == "invalid_artifact_path"

    collision = make_complete_bundle(tmp_path / "collision")
    rewrite_manifest(
        collision,
        lambda payload: payload["artifacts"].append(
            {
                **payload["artifacts"][0],
                "path": "Config/config.yaml",
            }
        ),
    )
    with pytest.raises(bundle.BundleValidationError) as collision_error:
        bundle.validate_bundle(collision)
    assert collision_error.value.code == "artifact_case_collision"

    symlink = make_complete_bundle(tmp_path / "symlink")
    config = symlink / "config" / "config.yaml"
    target = symlink / "config" / "real.yaml"
    target.write_bytes(config.read_bytes())
    config.unlink()
    config.symlink_to(target.name)
    with pytest.raises(bundle.BundleValidationError) as symlink_error:
        bundle.validate_bundle(symlink)
    assert symlink_error.value.code == "unsafe_artifact_type"

    hardlink = make_complete_bundle(tmp_path / "hardlink")
    os.link(hardlink / "config" / "config.yaml", hardlink / "config" / "linked.yaml")
    with pytest.raises(bundle.BundleValidationError) as hardlink_error:
        bundle.validate_bundle(hardlink)
    assert hardlink_error.value.code == "unsafe_artifact_hardlink"

    undeclared = make_complete_bundle(tmp_path / "undeclared")
    (undeclared / "private-token.txt").write_text("must not be ignored\n", encoding="utf-8")
    with pytest.raises(bundle.BundleValidationError) as undeclared_error:
        bundle.validate_bundle(undeclared)
    assert undeclared_error.value.code == "undeclared_bundle_file"


def test_restore_refuses_arbitrary_markerless_directory_before_target_mutation(tmp_path: Path) -> None:
    source = tmp_path / "arbitrary"
    target = tmp_path / "target"
    source.mkdir()
    (source / "anything.txt").write_text("not a bundle\n", encoding="utf-8")

    result = subprocess.run(
        [
            str(RESTORE_SCRIPT),
            "--target-config-home",
            str(target),
            "--snapshot-dir",
            str(source),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 3
    assert "positive producer completeness marker is missing" in result.stderr
    assert "before creating or changing target state" in result.stderr
    assert not target.exists()
    assert str(tmp_path) not in result.stdout
    assert str(tmp_path) not in result.stderr


def test_verified_bundle_refuses_partial_apply_without_mutating_target(tmp_path: Path) -> None:
    source = make_complete_bundle(tmp_path / "bundle")
    target = tmp_path / "target"
    runtime = target / "runtime"
    runtime.mkdir(parents=True)
    (runtime / "runtime.env").write_text(
        "VIVENTIUM_RUNTIME_PROFILE=isolated\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            str(RESTORE_SCRIPT),
            "--target-config-home",
            str(target),
            "--snapshot-dir",
            str(source),
            "--mark-recall-stale",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    marker = target / "state" / "runtime" / "isolated" / "continuity" / "recall-rebuild-required.json"
    assert result.returncode == 4
    assert not marker.exists()
    assert (runtime / "runtime.env").read_text(encoding="utf-8") == "VIVENTIUM_RUNTIME_PROFILE=isolated\n"
    assert "target state was not changed" in result.stderr
    assert str(tmp_path) not in result.stdout
    assert str(tmp_path) not in result.stderr


def test_restore_validate_only_accepts_verified_bundle_without_target_creation(tmp_path: Path) -> None:
    source = make_complete_bundle(tmp_path / "bundle")
    target = tmp_path / "target"

    result = subprocess.run(
        [
            str(RESTORE_SCRIPT),
            "--target-config-home",
            str(target),
            "--snapshot-dir",
            str(source),
            "--validate-only",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "validation passed" in result.stdout
    assert "target state was not changed" in result.stdout
    assert "independent recovery is not proven" in result.stdout
    assert not target.exists()
    assert str(tmp_path) not in result.stdout
    assert str(tmp_path) not in result.stderr


def test_restore_validate_only_supports_python_path_with_spaces(tmp_path: Path) -> None:
    source = make_complete_bundle(tmp_path / "bundle")
    target = tmp_path / "target"
    python_dir = tmp_path / "python runtime"
    python_dir.mkdir()
    python_path = python_dir / "python interpreter"
    python_path.symlink_to(sys.executable)

    result = subprocess.run(
        [
            str(RESTORE_SCRIPT),
            "--target-config-home",
            str(target),
            "--snapshot-dir",
            str(source),
            "--validate-only",
        ],
        cwd=REPO_ROOT,
        env={**os.environ, "VIVENTIUM_PYTHON_BIN": str(python_path)},
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "validation passed" in result.stdout
    assert not target.exists()
    assert str(tmp_path) not in result.stdout
    assert str(tmp_path) not in result.stderr


def test_bundle_validator_runs_with_python_standard_library_only(tmp_path: Path) -> None:
    source = make_complete_bundle(tmp_path / "bundle")

    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            str(BUNDLE_SCRIPT),
            "validate",
            "--snapshot-dir",
            str(source),
            "--json",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["valid"] is True
    assert payload["recoverable"] is False
    assert payload["semanticValidation"] == "not_performed"


def test_restore_rejects_source_target_overlap_before_mutation(tmp_path: Path) -> None:
    target = tmp_path / "target"
    source = make_complete_bundle(target / "snapshots" / "bundle")

    result = subprocess.run(
        [
            str(RESTORE_SCRIPT),
            "--target-config-home",
            str(target),
            "--snapshot-dir",
            str(source),
            "--validate-only",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 3
    assert "overlap" in result.stderr
    assert not (target / "state").exists()
    assert str(tmp_path) not in result.stdout
    assert str(tmp_path) not in result.stderr


def test_bundle_cli_reports_only_sanitized_validation_codes(tmp_path: Path) -> None:
    root = tmp_path / "private-bundle-name"
    root.mkdir()

    result = subprocess.run(
        [sys.executable, str(BUNDLE_SCRIPT), "validate", "--snapshot-dir", str(root), "--json"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 3
    assert payload["error"] == "missing_recoverable_marker"
    assert str(tmp_path) not in result.stdout
    assert str(tmp_path) not in result.stderr

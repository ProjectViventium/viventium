from __future__ import annotations

import gzip
import hashlib
import importlib.util
import io
import json
import os
import re
import sqlite3
import subprocess
import sys
import tarfile
import time
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
BUNDLE_SCRIPT = REPO_ROOT / "scripts" / "viventium" / "continuity_bundle.py"
MONGO_ADAPTER = REPO_ROOT / "scripts" / "viventium" / "continuity_mongo.cjs"
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


def write_tar_gz(destination: Path, files: dict[str, bytes]) -> int:
    source_root = destination.parent / f".{destination.name}.source"
    source_root.mkdir(parents=True)
    for relative, content in files.items():
        path = source_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    with tarfile.open(destination, "w:gz", format=tarfile.PAX_FORMAT) as archive:
        for relative in sorted(files):
            archive.add(source_root / relative, arcname=relative, recursive=False)
    expanded = len(gzip.decompress(destination.read_bytes()))
    for path in sorted(source_root.rglob("*"), reverse=True):
        path.unlink() if path.is_file() else path.rmdir()
    source_root.rmdir()
    return expanded


def write_empty_tar_gz(destination: Path, names: list[str]) -> int:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(destination, "w:gz", format=tarfile.PAX_FORMAT) as archive:
        for name in names:
            member = tarfile.TarInfo(name)
            member.size = 0
            member.mode = 0o600
            archive.addfile(member, io.BytesIO())
    return len(gzip.decompress(destination.read_bytes()))


def make_restore_ready_bundle(root: Path, *, include_files: bool = True) -> Path:
    root.mkdir(parents=True)
    (root / ".viventium-recoverable").write_text("v1\n", encoding="utf-8")
    config = root / "config" / "config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text(
        "version: 1\ninstall:\n  mode: native\nllm:\n  primary:\n    secret_ref: keychain://viventium/openai_api_key\n",
        encoding="utf-8",
    )
    mongo = root / "mongo" / "logical-export.tar.gz"
    mongo.parent.mkdir(parents=True)
    collections = [
        {
            "name": "messages",
            "path": "000.jsonl",
            "documents": 1,
            "sha256": hashlib.sha256(b'{"_id":{"$oid":"000000000000000000000001"},"text":"synthetic"}\n').hexdigest(),
        },
        {
            "name": "users",
            "path": "001.jsonl",
            "documents": 1,
            "sha256": hashlib.sha256(b'{"_id":{"$oid":"000000000000000000000002"},"email":"qa@example.invalid"}\n').hexdigest(),
        },
    ]
    mongo_expanded = write_tar_gz(
        mongo,
        {
            "000.jsonl": b'{"_id":{"$oid":"000000000000000000000001"},"text":"synthetic"}\n',
            "001.jsonl": b'{"_id":{"$oid":"000000000000000000000002"},"email":"qa@example.invalid"}\n',
            "index.json": (json.dumps({"schemaVersion": 1, "collections": collections}, indent=2, sort_keys=True) + "\n").encode(),
        },
    )
    schedules = root / "schedules" / "schedules.db"
    schedules.parent.mkdir(parents=True)
    connection = sqlite3.connect(schedules)
    connection.execute("CREATE TABLE scheduled_tasks (id TEXT PRIMARY KEY, active INTEGER NOT NULL)")
    connection.execute("INSERT INTO scheduled_tasks (id, active) VALUES ('synthetic-task', 1)")
    connection.commit()
    connection.close()
    files_paths: list[str] = []
    files_expanded = 0
    if include_files:
        uploads = root / "files" / "librechat-uploads.tar.gz"
        uploads.parent.mkdir(parents=True)
        files_expanded = write_tar_gz(uploads, {"synthetic-user/document.txt": b"synthetic file\n"})
        files_paths = ["files/librechat-uploads.tar.gz"]

    artifacts = [
        artifact_row(root, "config/config.yaml", "config", "canonical_config"),
        artifact_row(root, "mongo/logical-export.tar.gz", "mongo", "mongo_archive"),
        artifact_row(root, "schedules/schedules.db", "schedules", "schedules_database"),
    ]
    artifacts[1]["uncompressedSize"] = mongo_expanded
    if include_files:
        artifacts.append(artifact_row(root, files_paths[0], "files", "user_files_archive"))
        artifacts[-1]["uncompressedSize"] = files_expanded
    manifest = {
        "schemaVersion": 1,
        "bundleKind": "complete",
        "createdAt": "2026-07-20T00:00:00Z",
        "runtimeSelection": {
            "profile": "isolated",
            "sourceDatabase": "SourceViventium",
            "generatedRuntimePolicy": "regenerate_from_canonical_config",
            "helperBindingPolicy": "regenerate_for_target_checkout",
        },
        "security": {
            "filesystemMode": "owner_only",
            "payloadEncryption": "not_self_encrypted_owner_only",
            "inlineConfigSecrets": "redacted",
            "providerCredentials": "excluded_reauthentication_required",
            "channelCredentials": "excluded_reauthentication_required",
            "mongoExcludedCollections": [
                "actions",
                "agentapikeys",
                "keys",
                "mcpservers",
                "pluginauths",
                "sessions",
                "tokens",
            ],
            "mongoUserAuthFields": "excluded_reauthentication_required",
            "redactedConfigFieldCount": 0,
        },
        "inventory": {
            "mongoCollections": collections,
            "files": {"count": 1 if include_files else 0, "bytes": 15 if include_files else 0},
            "schedules": {"tables": 1, "tasks": 1},
            "recall": {"policy": "rebuild_from_restored_canonical_state"},
        },
        "domains": [
            {"name": "config", "status": "captured", "policy": "restore", "artifacts": ["config/config.yaml"]},
            {"name": "mongo", "status": "captured", "policy": "restore", "artifacts": ["mongo/logical-export.tar.gz"]},
            {"name": "files", "status": "captured" if include_files else "empty", "policy": "restore", "artifacts": files_paths},
            {"name": "schedules", "status": "captured", "policy": "restore", "artifacts": ["schedules/schedules.db"]},
            {"name": "recall", "status": "rebuild_required", "policy": "rebuild_derived", "artifacts": []},
            {"name": "auth", "status": "reauth_required", "policy": "reauth_required", "artifacts": []},
            {"name": "channels", "status": "reauth_required", "policy": "reauth_required", "artifacts": []},
        ],
        "artifacts": artifacts,
    }
    (root / "recoverable-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    for path in root.rglob("*"):
        path.chmod(0o700 if path.is_dir() else 0o600)
    root.chmod(0o700)
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
    assert result["restoreEngine"] == "candidate_validation_only"
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
    assert "Target state was not changed" in result.stderr
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
    assert "not independently restore-ready" in result.stdout
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


def make_fake_mongo_tools(root: Path) -> tuple[Path, Path]:
    root.mkdir()
    log = root / "adapter.log"
    mongosh = root / "mongosh"
    mongosh.write_text(
        "#!/bin/sh\n"
        "case \"$*\" in\n"
        "  *dropDatabase*) printf 'drop\\n' >> \"$VIVENTIUM_FAKE_MONGO_LOG\"; printf '{\"ok\":1}\\n' ;;\n"
        "  *collStats*) printf '{\"estimatedBytes\":%s}\\n' \"${VIVENTIUM_FAKE_MONGO_ESTIMATED_BYTES:-0}\" ;;\n"
        "  *) printf '%s\\n' \"${VIVENTIUM_FAKE_MONGO_COLLECTIONS:-[]}\" ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    mongoimport = root / "mongoimport"
    mongoimport.write_text(
        "#!/bin/sh\n"
        "collection=''\n"
        "while [ $# -gt 0 ]; do\n"
        "  if [ \"$1\" = '--collection' ]; then collection=$2; shift 2; else shift; fi\n"
        "done\n"
        "if [ -n \"${VIVENTIUM_FAKE_MONGOIMPORT_SLEEP:-}\" ]; then printf 'start:%s\\n' \"$collection\" >> \"$VIVENTIUM_FAKE_MONGO_LOG\"; sleep \"$VIVENTIUM_FAKE_MONGOIMPORT_SLEEP\"; fi\n"
        "printf 'import:%s\\n' \"$collection\" >> \"$VIVENTIUM_FAKE_MONGO_LOG\"\n",
        encoding="utf-8",
    )
    mongosh.chmod(0o755)
    mongoimport.chmod(0o755)
    mongoexport = root / "mongoexport"
    mongoexport.write_text(
        "#!/bin/sh\n"
        "collection=''\n"
        "output=''\n"
        "while [ $# -gt 0 ]; do\n"
        "  case \"$1\" in\n"
        "    --collection) collection=$2; shift 2 ;;\n"
        "    --out) output=$2; shift 2 ;;\n"
        "    *) shift ;;\n"
        "  esac\n"
        "done\n"
        "case \"$collection\" in\n"
        "  messages) printf '%s\\n' '{\"_id\":{\"$oid\":\"000000000000000000000001\"},\"text\":\"synthetic\"}' > \"$output\" ;;\n"
        "  users) printf '%s\\n' '{\"_id\":{\"$oid\":\"000000000000000000000002\"},\"email\":\"qa@example.invalid\"}' > \"$output\" ;;\n"
        "  *) : > \"$output\" ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    mongoexport.chmod(0o755)
    return root, log


def test_restore_ready_bundle_has_typed_complete_inventory_and_semantic_proof(tmp_path: Path) -> None:
    bundle = load_bundle_module()
    root = make_restore_ready_bundle(tmp_path / "bundle")

    result = bundle.validate_bundle(root)

    assert result["recoverable"] is True
    assert result["semanticValidation"] == "performed"
    assert result["restoreEngine"] == "independent_target_transaction_v1"
    assert {item["name"]: item["status"] for item in result["domains"]} == {
        "config": "captured",
        "mongo": "captured",
        "files": "captured",
        "schedules": "captured",
        "recall": "rebuild_required",
        "auth": "reauth_required",
        "channels": "reauth_required",
    }


def test_canonical_config_capture_redacts_inline_secrets_and_keeps_keychain_references(tmp_path: Path) -> None:
    bundle = load_bundle_module()
    source = tmp_path / "config.yaml"
    source.write_text(
        "version: 1\n"
        "llm:\n"
        "  primary:\n"
        "    api_key: synthetic-secret-must-not-survive\n"
        "    secret_ref: keychain://viventium/openai_api_key\n"
        "runtime:\n"
        "  extra_env:\n"
        "    SERVICE_TOKEN: another-synthetic-secret\n",
        encoding="utf-8",
    )

    rendered, redacted = bundle.redact_canonical_config(source)
    text = rendered.decode()

    assert "synthetic-secret-must-not-survive" not in text
    assert "another-synthetic-secret" not in text
    assert "keychain://viventium/openai_api_key" in text
    assert len(redacted) == 2


def test_config_secret_policy_handles_quoted_camel_case_and_rejects_inline_maps(tmp_path: Path) -> None:
    bundle = load_bundle_module()
    source = tmp_path / "config.yaml"
    source.write_text(
        "version: 1\n"
        "providers:\n"
        "  - 'clientSecret': synthetic-client-secret\n"
        "    apiKey: keychain://viventium/provider_api_key\n",
        encoding="utf-8",
    )

    rendered, redacted = bundle.redact_canonical_config(source)
    text = rendered.decode()

    assert "synthetic-client-secret" not in text
    assert "'clientSecret': null" in text
    assert "keychain://viventium/provider_api_key" in text
    assert len(redacted) == 1

    source.write_text(
        "version: 1\nproviders: {apiKey: synthetic-inline-secret}\n",
        encoding="utf-8",
    )
    with pytest.raises(bundle.RestoreTransactionError, match="inline secret layout"):
        bundle.redact_canonical_config(source)


def test_semantic_validator_rejects_forged_inline_config_secret_and_boolean_counts(tmp_path: Path) -> None:
    bundle = load_bundle_module()
    root = make_restore_ready_bundle(tmp_path / "secret")
    config = root / "config" / "config.yaml"
    config.write_text("version: 1\nprovider:\n  apiKey: synthetic-inline-secret\n", encoding="utf-8")
    rewrite_manifest(
        root,
        lambda payload: payload["artifacts"].__setitem__(
            0,
            artifact_row(root, "config/config.yaml", "config", "canonical_config"),
        ),
    )

    with pytest.raises(bundle.BundleValidationError) as secret_error:
        bundle.validate_bundle(root)
    assert secret_error.value.code == "invalid_config_secret_policy"

    root = make_restore_ready_bundle(tmp_path / "boolean-count")
    rewrite_manifest(root, lambda payload: payload["inventory"]["files"].__setitem__("count", True))
    with pytest.raises(bundle.BundleValidationError) as count_error:
        bundle.validate_bundle(root)
    assert count_error.value.code == "invalid_files_inventory"


def test_archive_member_limit_accepts_exact_cap_and_rejects_cap_plus_one_zero_byte_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = load_bundle_module()
    monkeypatch.setattr(bundle, "MAX_ARCHIVE_MEMBERS", 3)
    exact = tmp_path / "exact.tar.gz"
    over = tmp_path / "over.tar.gz"
    write_empty_tar_gz(exact, ["000", "001", "002"])
    write_empty_tar_gz(over, ["000", "001", "002", "003"])

    assert len(bundle.safe_tar_members(exact, expected_members=3)) == 3
    with pytest.raises(bundle.RestoreTransactionError, match="member count"):
        bundle.safe_tar_members(over)


@pytest.mark.parametrize(
    ("name", "byte_limit", "depth_limit", "message"),
    [
        ("pax-name-that-is-too-long", 12, 8, "path byte"),
        ("one/two/three", 1024, 2, "path depth"),
    ],
)
def test_archive_member_limit_rejects_overlong_or_deep_pax_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    byte_limit: int,
    depth_limit: int,
    message: str,
) -> None:
    bundle = load_bundle_module()
    monkeypatch.setattr(bundle, "MAX_ARCHIVE_PATH_BYTES", byte_limit)
    monkeypatch.setattr(bundle, "MAX_ARCHIVE_PATH_DEPTH", depth_limit)
    archive = tmp_path / "bounded-pax.tar.gz"
    write_empty_tar_gz(archive, [name])

    with pytest.raises(bundle.RestoreTransactionError, match=message):
        bundle.safe_tar_members(archive)


def test_declared_file_count_over_archive_cap_fails_before_archive_traversal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = load_bundle_module()
    root = make_restore_ready_bundle(tmp_path / "bundle")
    monkeypatch.setattr(bundle, "MAX_ARCHIVE_MEMBERS", 3)
    rewrite_manifest(
        root,
        lambda payload: payload["inventory"]["files"].__setitem__("count", 4),
    )

    with pytest.raises(bundle.BundleValidationError) as error:
        bundle.validate_bundle(root)
    assert error.value.code == "invalid_files_inventory"


def test_total_archive_member_limit_applies_across_all_bundle_archives(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = load_bundle_module()
    root = make_restore_ready_bundle(tmp_path / "bundle")
    monkeypatch.setattr(bundle, "MAX_ARCHIVE_MEMBERS", 3)
    monkeypatch.setattr(bundle, "MAX_TOTAL_ARCHIVE_MEMBERS", 3)

    with pytest.raises(bundle.BundleValidationError) as error:
        bundle.validate_bundle(root)
    assert error.value.code == "archive_member_limit"


def test_extraction_rechecks_archive_limits_before_creating_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = load_bundle_module()
    monkeypatch.setattr(bundle, "MAX_ARCHIVE_MEMBERS", 2)
    archive = tmp_path / "mutable.tar.gz"
    destination = tmp_path / "restored"
    write_empty_tar_gz(archive, ["first", "second"])
    assert len(bundle.safe_tar_members(archive, expected_members=2)) == 2

    write_empty_tar_gz(archive, ["first", "second", "third"])
    with pytest.raises(bundle.RestoreTransactionError, match="member count"):
        bundle.extract_regular_tar(archive, destination, expected_members=2)
    assert not destination.exists()


def test_semantic_validator_rejects_provider_secret_smuggled_in_safe_collection(tmp_path: Path) -> None:
    bundle = load_bundle_module()
    root = make_restore_ready_bundle(tmp_path / "bundle")
    archive = root / "mongo" / "logical-export.tar.gz"
    secret_line = b'{"_id":{"$oid":"000000000000000000000001"},"api_key":"synthetic-leak"}\n'
    manifest = json.loads((root / "recoverable-manifest.json").read_text(encoding="utf-8"))
    manifest["inventory"]["mongoCollections"][0]["documents"] = 1
    manifest["inventory"]["mongoCollections"][0]["sha256"] = hashlib.sha256(secret_line).hexdigest()
    expanded = write_tar_gz(
        archive,
        {
            "000.jsonl": secret_line,
            "001.jsonl": b'{"_id":{"$oid":"000000000000000000000002"},"email":"qa@example.invalid"}\n',
            "index.json": (
                json.dumps(
                    {"schemaVersion": 1, "collections": manifest["inventory"]["mongoCollections"]},
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            ).encode(),
        },
    )
    mongo_artifact = next(item for item in manifest["artifacts"] if item["role"] == "mongo_archive")
    mongo_artifact["size"] = archive.stat().st_size
    mongo_artifact["sha256"] = hashlib.sha256(archive.read_bytes()).hexdigest()
    mongo_artifact["uncompressedSize"] = expanded
    (root / "recoverable-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(bundle.BundleValidationError) as error:
        bundle.validate_bundle(root)
    assert error.value.code == "invalid_mongo_archive"


@pytest.mark.parametrize(
    "secret_key",
    [
        "api-key",
        "API.Key",
        "api key",
        "clientSecret",
        "CLIENT/SECRET",
        "set-cookie",
        "Authorization",
        "refresh.token",
        "openAIApiKey",
        "sessionToken",
        "oauthToken",
        "credentials",
    ],
)
def test_structured_secret_filter_rejects_separator_and_case_variants_in_nested_tool_results(
    secret_key: str,
) -> None:
    bundle = load_bundle_module()
    payload = {
        "toolCall": {
            "result": [
                {"nested": {secret_key: "synthetic-secret-must-not-survive"}},
            ]
        }
    }
    assert bundle.json_contains_exported_secret(payload) is True


def test_structured_secret_filter_preserves_non_secret_tool_result_metadata() -> None:
    bundle = load_bundle_module()
    payload = {
        "metadata": {
            "tokenCount": 42,
            "passwordPolicy": "required",
            "authorizationStatus": "not_connected",
            "output": "synthetic public result",
        }
    }
    assert bundle.json_contains_exported_secret(payload) is False

    sanitized = bundle.sanitize_exported_structured_value(
        {
            "result": {
                "provider.api-key.value": "synthetic-secret",
                "output": "keep",
            },
            "arguments": '{"refresh token":"synthetic-secret-2","query":"keep"}',
        }
    )
    rendered = json.dumps(sanitized, sort_keys=True)
    assert "synthetic-secret" not in rendered
    assert "keep" in rendered


def test_structured_secret_validator_rejects_json_encoded_tool_arguments() -> None:
    bundle = load_bundle_module()
    payload = {
        "toolCall": {
            "arguments": '{"query":"keep","nested":{"CLIENT/SECRET":"synthetic-leak"}}',
        }
    }

    assert bundle.json_contains_exported_secret(payload) is True


def test_node_export_adapter_recursively_removes_structured_secrets_from_tool_content() -> None:
    script = (
        "const a=require(process.argv[1]);"
        "const p={safe:'keep',toolCall:{result:{'API.Key':'leak1',openAIApiKey:'leak2',"
        "sessionToken:'leak3',oauthToken:'leak4',credentials:'leak5',safe:'keep'},"
        "arguments:JSON.stringify({'client secret':'leak6',query:'keep'})}};"
        "process.stdout.write(JSON.stringify(a.sanitizeExportDocument(p)));"
    )
    result = subprocess.run(
        ["node", "-e", script, str(MONGO_ADAPTER)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "leak" not in result.stdout
    assert "keep" in result.stdout


def test_tool_result_plaintext_is_never_treated_as_a_safe_complete_export() -> None:
    bundle = load_bundle_module()
    payload = {
        "toolCall": {
            "result": {
                "output": "Authorization" + ": Bearer " + "synthetic-secret-must-not-survive",
            }
        }
    }

    assert bundle.json_contains_exported_secret(payload) is True


def test_transactional_restore_to_empty_independent_target_restores_all_canonical_surfaces(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = load_bundle_module()
    source = make_restore_ready_bundle(tmp_path / "bundle")
    tools, log = make_fake_mongo_tools(tmp_path / "fake-bin")
    monkeypatch.setenv("PATH", f"{tools}:{os.environ['PATH']}")
    monkeypatch.setenv("VIVENTIUM_FAKE_MONGO_LOG", str(log))
    target_repo = tmp_path / "fresh-checkout"
    (target_repo / "viventium_v0_4" / "LibreChat").mkdir(parents=True)
    target = tmp_path / "independent-app-support"
    mongo_data = tmp_path / "independent-mongo-data"
    mongo_data.mkdir(mode=0o700)

    result = bundle.restore_bundle(
        snapshot=source,
        target_config_home=target,
        target_repo_root=target_repo,
        target_mongo_uri="mongodb://127.0.0.1:27117/RestoredViventium",
        target_mongo_data_path=mongo_data,
    )

    assert result["restored"] is True
    assert (target / "config.yaml").is_file()
    assert (
        target / "state" / "runtime" / "isolated" / "scheduling" / "schedules.db"
    ).is_file()
    assert (
        target / "state" / "runtime" / "isolated" / "continuity" / "recall-rebuild-required.json"
    ).is_file()
    reauth = json.loads(
        (
            target
            / "state"
            / "runtime"
            / "isolated"
            / "continuity"
            / "reauthentication-required.json"
        ).read_text(encoding="utf-8")
    )
    assert reauth["providerCredentials"] == "reauth_required"
    assert reauth["channelCredentials"] == "reauth_required"
    runtime_selection = json.loads(
        (target / "state" / "continuity" / "restored-runtime-selection.json").read_text(
            encoding="utf-8"
        )
    )
    assert runtime_selection["schemaVersion"] == 2
    assert runtime_selection["targetMongoPort"] == 27117
    assert runtime_selection["targetMongoDataPath"] == str(mongo_data)
    assert runtime_selection["mongoPersistencePolicy"] == "target_owned_data_path"
    assert runtime_selection["localRuntimeSecretPolicy"] == "regenerated_for_target"
    local_runtime_secret = target / "state" / "continuity" / "restored-local-runtime-secret"
    assert re.fullmatch(r"[0-9a-f]{64}\n", local_runtime_secret.read_text(encoding="ascii"))
    assert (local_runtime_secret.stat().st_mode & 0o777) == 0o600
    assert (target_repo / "viventium_v0_4" / "LibreChat" / "uploads" / "synthetic-user" / "document.txt").is_file()
    restored_directories = [target, *[path for path in target.rglob("*") if path.is_dir()]]
    assert all((path.stat().st_mode & 0o777) == 0o700 for path in restored_directories)
    restored_files = [path for path in target.rglob("*") if path.is_file()]
    assert all((path.stat().st_mode & 0o777) == 0o600 for path in restored_files)
    assert log.read_text(encoding="utf-8").splitlines() == ["import:messages", "import:users"]
    assert not list(tmp_path.glob(".*restore-transaction.json"))


def test_transaction_rolls_back_mongo_files_and_app_support_after_post_import_fault(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = load_bundle_module()
    source = make_restore_ready_bundle(tmp_path / "bundle")
    tools, log = make_fake_mongo_tools(tmp_path / "fake-bin")
    monkeypatch.setenv("PATH", f"{tools}:{os.environ['PATH']}")
    monkeypatch.setenv("VIVENTIUM_FAKE_MONGO_LOG", str(log))
    target_repo = tmp_path / "fresh-checkout"
    (target_repo / "viventium_v0_4" / "LibreChat").mkdir(parents=True)
    target = tmp_path / "independent-app-support"

    with pytest.raises(bundle.RestoreTransactionError, match="Injected restore fault"):
        bundle.restore_bundle(
            snapshot=source,
            target_config_home=target,
            target_repo_root=target_repo,
            target_mongo_uri="mongodb://127.0.0.1:27117/RestoredViventium",
            fault_after="mongo_restored",
        )

    assert not target.exists()
    assert not (target_repo / "viventium_v0_4" / "LibreChat" / "uploads").exists()
    assert log.read_text(encoding="utf-8").splitlines() == ["import:messages", "import:users", "drop"]
    assert not list(tmp_path.glob(".*restore-transaction.json"))


def test_transaction_rolls_back_already_activated_filesystem_roots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = load_bundle_module()
    source = make_restore_ready_bundle(tmp_path / "bundle")
    tools, log = make_fake_mongo_tools(tmp_path / "fake-bin")
    monkeypatch.setenv("PATH", f"{tools}:{os.environ['PATH']}")
    monkeypatch.setenv("VIVENTIUM_FAKE_MONGO_LOG", str(log))
    target_repo = tmp_path / "fresh-checkout"
    (target_repo / "viventium_v0_4" / "LibreChat").mkdir(parents=True)
    target = tmp_path / "independent-app-support"

    with pytest.raises(bundle.RestoreTransactionError, match="Injected restore fault"):
        bundle.restore_bundle(
            snapshot=source,
            target_config_home=target,
            target_repo_root=target_repo,
            target_mongo_uri="mongodb://127.0.0.1:27117/RestoredViventium",
            fault_after="activated",
        )

    assert not target.exists()
    assert not (target_repo / "viventium_v0_4" / "LibreChat" / "uploads").exists()
    assert log.read_text(encoding="utf-8").splitlines() == ["import:messages", "import:users", "drop"]


@pytest.mark.parametrize("fault_after", ["uploads_renamed", "target_renamed"])
def test_transaction_rolls_back_a_root_renamed_immediately_before_state_update(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault_after: str
) -> None:
    bundle = load_bundle_module()
    source = make_restore_ready_bundle(tmp_path / "bundle")
    tools, log = make_fake_mongo_tools(tmp_path / "fake-bin")
    monkeypatch.setenv("PATH", f"{tools}:{os.environ['PATH']}")
    monkeypatch.setenv("VIVENTIUM_FAKE_MONGO_LOG", str(log))
    target_repo = tmp_path / "fresh-checkout"
    (target_repo / "viventium_v0_4" / "LibreChat").mkdir(parents=True)
    target = tmp_path / "independent-app-support"

    with pytest.raises(bundle.RestoreTransactionError, match="Injected restore fault"):
        bundle.restore_bundle(
            snapshot=source,
            target_config_home=target,
            target_repo_root=target_repo,
            target_mongo_uri="mongodb://127.0.0.1:27117/RestoredViventium",
            fault_after=fault_after,
        )

    assert not target.exists()
    assert not (target_repo / "viventium_v0_4" / "LibreChat" / "uploads").exists()
    assert log.read_text(encoding="utf-8").splitlines() == ["import:messages", "import:users", "drop"]
    assert not list(tmp_path.glob(".*restore-transaction.json"))


def test_sigterm_interrupts_active_import_then_rolls_back_owned_state(tmp_path: Path) -> None:
    source = make_restore_ready_bundle(tmp_path / "bundle")
    tools, log = make_fake_mongo_tools(tmp_path / "fake-bin")
    mongoimport = tools / "mongoimport"
    mongoimport.write_text(
        "#!/usr/bin/env python3\n"
        "import os, pathlib, sys, time\n"
        "name = sys.argv[sys.argv.index('--collection') + 1]\n"
        "log = pathlib.Path(os.environ['VIVENTIUM_FAKE_MONGO_LOG'])\n"
        "with log.open('a', encoding='utf-8') as handle:\n"
        "    handle.write(f'start:{name}\\n')\n"
        "    handle.flush()\n"
        "time.sleep(30)\n",
        encoding="utf-8",
    )
    mongoimport.chmod(0o755)
    target_repo = tmp_path / "fresh-checkout"
    (target_repo / "viventium_v0_4" / "LibreChat").mkdir(parents=True)
    target = tmp_path / "independent-app-support"
    env = {
        **os.environ,
        "PATH": f"{tools}:{os.environ['PATH']}",
        "VIVENTIUM_FAKE_MONGO_LOG": str(log),
    }
    process = subprocess.Popen(
        [
            sys.executable,
            str(BUNDLE_SCRIPT),
            "restore",
            "--snapshot-dir",
            str(source),
            "--target-config-home",
            str(target),
            "--target-repo-root",
            str(target_repo),
            "--target-mongo-uri",
            "mongodb://127.0.0.1:27117/RestoredViventium",
        ],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if log.exists() and "start:messages" in log.read_text(encoding="utf-8"):
            break
        time.sleep(0.02)
    else:
        process.kill()
        process.wait()
        raise AssertionError("restore did not reach the synthetic import boundary")

    process.terminate()
    stdout, stderr = process.communicate(timeout=10)

    assert process.returncode == 4, (stdout, stderr)
    assert not target.exists()
    assert not (target_repo / "viventium_v0_4" / "LibreChat" / "uploads").exists()
    assert log.read_text(encoding="utf-8").splitlines() == ["start:messages", "drop"]
    assert not list(tmp_path.glob(".*restore-transaction.json"))


def test_restore_refuses_existing_app_support_before_any_mongo_import(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = load_bundle_module()
    source = make_restore_ready_bundle(tmp_path / "bundle")
    tools, log = make_fake_mongo_tools(tmp_path / "fake-bin")
    monkeypatch.setenv("PATH", f"{tools}:{os.environ['PATH']}")
    monkeypatch.setenv("VIVENTIUM_FAKE_MONGO_LOG", str(log))
    target_repo = tmp_path / "fresh-checkout"
    (target_repo / "viventium_v0_4" / "LibreChat").mkdir(parents=True)
    target = tmp_path / "personal-app-support"
    target.mkdir()
    sentinel = target / "do-not-touch.txt"
    sentinel.write_text("personal\n", encoding="utf-8")

    with pytest.raises(bundle.RestoreTransactionError, match="must not already exist"):
        bundle.restore_bundle(
            snapshot=source,
            target_config_home=target,
            target_repo_root=target_repo,
            target_mongo_uri="mongodb://127.0.0.1:27117/RestoredViventium",
        )

    assert sentinel.read_text(encoding="utf-8") == "personal\n"
    assert not log.exists()


def test_restore_refuses_app_support_and_checkout_overlap_before_mongo_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = load_bundle_module()
    source = make_restore_ready_bundle(tmp_path / "bundle")
    tools, log = make_fake_mongo_tools(tmp_path / "fake-bin")
    monkeypatch.setenv("PATH", f"{tools}:{os.environ['PATH']}")
    monkeypatch.setenv("VIVENTIUM_FAKE_MONGO_LOG", str(log))
    target_repo = tmp_path / "fresh-checkout"
    (target_repo / "viventium_v0_4" / "LibreChat").mkdir(parents=True)

    with pytest.raises(bundle.RestoreTransactionError, match="App Support target and target checkout overlap"):
        bundle.restore_bundle(
            snapshot=source,
            target_config_home=target_repo / "app-support",
            target_repo_root=target_repo,
            target_mongo_uri="mongodb://127.0.0.1:27117/RestoredViventium",
        )

    assert not (target_repo / "app-support").exists()
    assert not log.exists()


def test_restore_refuses_non_private_bundle_permissions_before_mongo_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = load_bundle_module()
    source = make_restore_ready_bundle(tmp_path / "bundle")
    (source / "recoverable-manifest.json").chmod(0o644)
    tools, log = make_fake_mongo_tools(tmp_path / "fake-bin")
    monkeypatch.setenv("PATH", f"{tools}:{os.environ['PATH']}")
    monkeypatch.setenv("VIVENTIUM_FAKE_MONGO_LOG", str(log))
    target_repo = tmp_path / "fresh-checkout"
    (target_repo / "viventium_v0_4" / "LibreChat").mkdir(parents=True)

    with pytest.raises(bundle.RestoreTransactionError, match="owner-only"):
        bundle.restore_bundle(
            snapshot=source,
            target_config_home=tmp_path / "independent-app-support",
            target_repo_root=target_repo,
            target_mongo_uri="mongodb://127.0.0.1:27117/RestoredViventium",
        )

    assert not log.exists()


def test_complete_capture_adapter_builds_restore_ready_bundle_without_exporting_secrets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = load_bundle_module()
    tools, _ = make_fake_mongo_tools(tmp_path / "fake-bin")
    monkeypatch.setenv("PATH", f"{tools}:{os.environ['PATH']}")
    monkeypatch.setenv("VIVENTIUM_FAKE_MONGO_COLLECTIONS", '["messages","users","tokens"]')
    repo = tmp_path / "repo"
    uploads = repo / "viventium_v0_4" / "LibreChat" / "uploads" / "synthetic-user"
    uploads.mkdir(parents=True)
    (uploads / "artifact.txt").write_text("synthetic upload\n", encoding="utf-8")
    app_support = tmp_path / "app-support"
    runtime = app_support / "runtime"
    runtime.mkdir(parents=True)
    (app_support / "config.yaml").write_text(
        "version: 1\ninstall:\n  mode: native\nllm:\n  primary:\n    api_key: synthetic-must-not-export\n",
        encoding="utf-8",
    )
    schedule = app_support / "state" / "runtime" / "isolated" / "scheduling" / "schedules.db"
    schedule.parent.mkdir(parents=True)
    connection = sqlite3.connect(schedule)
    connection.execute("CREATE TABLE scheduled_tasks (id TEXT PRIMARY KEY, active INTEGER NOT NULL)")
    connection.execute("INSERT INTO scheduled_tasks VALUES ('synthetic-task', 1)")
    connection.commit()
    connection.close()
    (runtime / "runtime.env").write_text(
        "VIVENTIUM_RUNTIME_PROFILE=isolated\n"
        "VIVENTIUM_LOCAL_MONGO_PORT=27117\n"
        "VIVENTIUM_LOCAL_MONGO_DB=SourceViventium\n"
        f"SCHEDULING_DB_PATH={schedule}\n",
        encoding="utf-8",
    )
    output_root = app_support / "snapshots"

    result = bundle.capture_bundle(
        repo_root=repo,
        app_support=app_support,
        runtime_dir=runtime,
        output_root=output_root,
    )
    snapshot = Path(result["snapshotDir"])
    manifest = json.loads((snapshot / "recoverable-manifest.json").read_text(encoding="utf-8"))

    assert result["recoverable"] is True
    assert [item["name"] for item in manifest["inventory"]["mongoCollections"]] == ["messages", "users"]
    assert "tokens" in manifest["security"]["mongoExcludedCollections"]
    assert manifest["security"]["redactedConfigFieldCount"] == 1
    assert "synthetic-must-not-export" not in (snapshot / "config" / "config.yaml").read_text(encoding="utf-8")
    assert (snapshot.stat().st_mode & 0o777) == 0o700
    assert not (snapshot / ".viventium-incomplete").exists()


def test_capture_refuses_low_disk_before_creating_snapshot_or_contacting_mongo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = load_bundle_module()
    repo = tmp_path / "repo"
    (repo / "viventium_v0_4" / "LibreChat").mkdir(parents=True)
    app_support = tmp_path / "app-support"
    runtime = app_support / "runtime"
    runtime.mkdir(parents=True)
    (app_support / "config.yaml").write_text(
        "version: 1\ninstall:\n  mode: native\n",
        encoding="utf-8",
    )
    (runtime / "runtime.env").write_text(
        "VIVENTIUM_RUNTIME_PROFILE=isolated\n"
        "VIVENTIUM_LOCAL_MONGO_PORT=27117\n"
        "VIVENTIUM_LOCAL_MONGO_DB=SourceViventium\n",
        encoding="utf-8",
    )
    output_root = app_support / "snapshots"
    mongo_contacted = False

    def fail_if_mongo_contacted(*_args, **_kwargs):
        nonlocal mongo_contacted
        mongo_contacted = True
        raise AssertionError("low-disk preflight must run before Mongo capture")

    monkeypatch.setattr(bundle, "capture_mongo_logical", fail_if_mongo_contacted)
    monkeypatch.setattr(
        bundle.shutil,
        "disk_usage",
        lambda _path: type(
            "DiskUsage",
            (),
            {
                "total": bundle.CONTINUITY_DISK_RESERVE_BYTES,
                "used": 1,
                "free": bundle.CONTINUITY_DISK_RESERVE_BYTES - 1,
            },
        )(),
    )

    with pytest.raises(bundle.RestoreTransactionError, match="Insufficient disk space for continuity capture"):
        bundle.capture_bundle(
            repo_root=repo,
            app_support=app_support,
            runtime_dir=runtime,
            output_root=output_root,
        )

    assert mongo_contacted is False
    assert not list(output_root.glob("*-complete-*"))


def test_capture_removes_incomplete_snapshot_when_disk_floor_drops_between_phases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = load_bundle_module()
    repo = tmp_path / "repo"
    (repo / "viventium_v0_4" / "LibreChat").mkdir(parents=True)
    app_support = tmp_path / "app-support"
    runtime = app_support / "runtime"
    runtime.mkdir(parents=True)
    (app_support / "config.yaml").write_text(
        "version: 1\ninstall:\n  mode: native\n",
        encoding="utf-8",
    )
    (runtime / "runtime.env").write_text(
        "VIVENTIUM_RUNTIME_PROFILE=isolated\n"
        "VIVENTIUM_LOCAL_MONGO_PORT=27117\n"
        "VIVENTIUM_LOCAL_MONGO_DB=SourceViventium\n",
        encoding="utf-8",
    )
    output_root = app_support / "snapshots"
    observations = 0

    def changing_disk_usage(_path):
        nonlocal observations
        observations += 1
        free = (
            bundle.CONTINUITY_DISK_RESERVE_BYTES + 1024 * 1024 * 1024
            if observations == 1
            else bundle.CONTINUITY_DISK_RESERVE_BYTES - 1
        )
        return type(
            "DiskUsage",
            (),
            {"total": free + 1, "used": 1, "free": free},
        )()

    monkeypatch.setattr(bundle.shutil, "disk_usage", changing_disk_usage)
    monkeypatch.setattr(
        bundle,
        "capture_mongo_logical",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("disk floor must stop capture before Mongo export")
        ),
    )

    with pytest.raises(bundle.RestoreTransactionError, match="Insufficient disk space for continuity capture"):
        bundle.capture_bundle(
            repo_root=repo,
            app_support=app_support,
            runtime_dir=runtime,
            output_root=output_root,
        )

    assert observations == 2
    assert not list(output_root.glob("*-complete-*"))


def test_capture_capacity_plan_counts_known_inputs_mongo_working_estimate_and_reserve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = load_bundle_module()
    output_root = tmp_path / "output"
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    (uploads / "synthetic.txt").write_bytes(b"upload-bytes")
    schedule = tmp_path / "schedules.db"
    schedule.write_bytes(b"schedule-bytes")
    mongo_data = tmp_path / "mongo-data"
    mongo_data.mkdir()
    (mongo_data / "storage.wt").write_bytes(b"mongo-storage-bytes")
    monkeypatch.setattr(bundle, "storage_device_id", lambda _path: 4)

    plan = bundle.capture_storage_capacity_plan(
        output_root=output_root,
        sanitized_config_bytes=123,
        source_uploads=uploads,
        schedule_path=schedule,
        runtime={"VIVENTIUM_LOCAL_MONGO_DATA_PATH": str(mongo_data)},
        app_support=tmp_path,
        profile="isolated",
    )

    expected_payload = (
        bundle.CONTINUITY_TRANSACTION_OVERHEAD_BYTES
        + 123
        + bundle.archive_capture_size_estimate(uploads)
        + schedule.stat().st_size
        + mongo_data.joinpath("storage.wt").stat().st_size
        * bundle.MONGO_CAPTURE_ESTIMATE_MULTIPLIER
    )
    assert plan[4]["payloadBytes"] == expected_payload
    assert plan[4]["requiredBytes"] == expected_payload + bundle.CONTINUITY_DISK_RESERVE_BYTES


def test_mongo_logical_size_estimate_uses_bounded_product_adapter_stats(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = load_bundle_module()
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(bundle, "node_mongo_adapter", lambda _repo: ("node", tmp_path / "adapter"))

    def fake_adapter(repo_root, command, uri, **_kwargs):
        calls.append((command, uri))
        return {"ok": True, "estimatedBytes": 987654}

    monkeypatch.setattr(bundle, "run_node_mongo_adapter", fake_adapter)

    assert bundle.mongo_logical_source_size(
        "mongodb://127.0.0.1:27117/SourceViventium",
        tmp_path / "repo",
    ) == 987654
    assert calls == [("estimate", "mongodb://127.0.0.1:27117/SourceViventium")]


@pytest.mark.parametrize("invalid", [True, -1, 256 * 1024 * 1024 * 1024 + 1])
def test_mongo_logical_size_estimate_rejects_invalid_or_unbounded_adapter_stats(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, invalid
) -> None:
    bundle = load_bundle_module()
    monkeypatch.setattr(bundle, "node_mongo_adapter", lambda _repo: ("node", tmp_path / "adapter"))
    monkeypatch.setattr(
        bundle,
        "run_node_mongo_adapter",
        lambda *_args, **_kwargs: {"ok": True, "estimatedBytes": invalid},
    )

    with pytest.raises(bundle.RestoreTransactionError, match="Mongo storage estimate is invalid"):
        bundle.mongo_logical_source_size(
            "mongodb://127.0.0.1:27117/SourceViventium",
            tmp_path / "repo",
        )


def test_node_mongo_estimator_counts_only_allowlisted_collections() -> None:
    script = (
        "const a=require(process.argv[1]);"
        "const db={listCollections:()=>({toArray:async()=>[{name:'messages'},{name:'tokens'}]}),"
        "command:async({collStats})=>({size:collStats==='messages'?321:999999})};"
        "a.estimateLogicalBytes(db).then((value)=>process.stdout.write(String(value)));"
    )

    result = subprocess.run(
        ["node", "-e", script, str(MONGO_ADAPTER)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "321"


def test_restore_capacity_plan_counts_compressed_expanded_and_reserve_per_filesystem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = load_bundle_module()
    snapshot = make_restore_ready_bundle(tmp_path / "bundle")
    payload = json.loads((snapshot / "recoverable-manifest.json").read_text(encoding="utf-8"))
    target_parent = tmp_path / "target-volume"
    uploads_parent = tmp_path / "repo-volume"
    mongo_data = tmp_path / "mongo-volume"
    for path in (target_parent, uploads_parent, mongo_data):
        path.mkdir()

    def device_for(path: Path) -> int:
        path = Path(path)
        if path == uploads_parent:
            return 2
        if path == mongo_data:
            return 3
        return 1

    monkeypatch.setattr(bundle, "storage_device_id", device_for)
    plan = bundle.restore_storage_capacity_plan(
        payload,
        target_parent=target_parent,
        uploads_parent=uploads_parent,
        target_mongo_data_path=mongo_data,
    )

    artifacts = {item["role"]: item for item in payload["artifacts"]}
    mongo_bytes = artifacts["mongo_archive"]["size"] + artifacts["mongo_archive"]["uncompressedSize"]
    uploads_bytes = (
        artifacts["user_files_archive"]["size"]
        + artifacts["user_files_archive"]["uncompressedSize"]
        + payload["inventory"]["files"]["count"] * bundle.ARCHIVE_MEMBER_METADATA_BYTES
    )
    mongo_metadata_bytes = (
        len(payload["inventory"]["mongoCollections"]) + 1
    ) * bundle.ARCHIVE_MEMBER_METADATA_BYTES
    target_bytes = (
        bundle.CONTINUITY_TRANSACTION_OVERHEAD_BYTES
        + artifacts["canonical_config"]["size"]
        + artifacts["schedules_database"]["size"]
        + mongo_bytes
        + mongo_metadata_bytes
    )

    assert plan[1]["payloadBytes"] == target_bytes
    assert plan[1]["requiredBytes"] == target_bytes + bundle.CONTINUITY_DISK_RESERVE_BYTES
    assert plan[2]["payloadBytes"] == uploads_bytes
    assert plan[2]["requiredBytes"] == uploads_bytes + bundle.CONTINUITY_DISK_RESERVE_BYTES
    assert plan[3]["payloadBytes"] == mongo_bytes
    assert plan[3]["requiredBytes"] == mongo_bytes + bundle.CONTINUITY_DISK_RESERVE_BYTES


def test_restore_capacity_plan_aggregates_shared_filesystem_with_one_reserve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = load_bundle_module()
    snapshot = make_restore_ready_bundle(tmp_path / "bundle")
    payload = json.loads((snapshot / "recoverable-manifest.json").read_text(encoding="utf-8"))
    common = tmp_path / "common-volume"
    common.mkdir()
    monkeypatch.setattr(bundle, "storage_device_id", lambda _path: 7)

    plan = bundle.restore_storage_capacity_plan(
        payload,
        target_parent=common,
        uploads_parent=common,
        target_mongo_data_path=common,
    )

    assert set(plan) == {7}
    assert plan[7]["requiredBytes"] == (
        plan[7]["payloadBytes"] + bundle.CONTINUITY_DISK_RESERVE_BYTES
    )


def test_restore_capacity_plan_reserves_unseen_mongo_database_footprint_on_target_volume(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = load_bundle_module()
    snapshot = make_restore_ready_bundle(tmp_path / "bundle", include_files=False)
    payload = json.loads((snapshot / "recoverable-manifest.json").read_text(encoding="utf-8"))
    common = tmp_path / "common-volume"
    common.mkdir()
    monkeypatch.setattr(bundle, "storage_device_id", lambda _path: 8)

    plan = bundle.restore_storage_capacity_plan(
        payload,
        target_parent=common,
        uploads_parent=common,
        target_mongo_data_path=None,
    )

    mongo = next(item for item in payload["artifacts"] if item["role"] == "mongo_archive")
    mongo_bytes = mongo["size"] + mongo["uncompressedSize"]
    mongo_metadata_bytes = (
        len(payload["inventory"]["mongoCollections"]) + 1
    ) * bundle.ARCHIVE_MEMBER_METADATA_BYTES
    non_mongo_bytes = (
        bundle.CONTINUITY_TRANSACTION_OVERHEAD_BYTES
        + next(item["size"] for item in payload["artifacts"] if item["role"] == "canonical_config")
        + next(item["size"] for item in payload["artifacts"] if item["role"] == "schedules_database")
    )
    assert plan[8]["payloadBytes"] == non_mongo_bytes + (2 * mongo_bytes) + mongo_metadata_bytes


def test_restore_refuses_low_disk_before_target_journal_or_mongo_inspection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = load_bundle_module()
    source = make_restore_ready_bundle(tmp_path / "bundle")
    target_repo = tmp_path / "fresh-checkout"
    (target_repo / "viventium_v0_4" / "LibreChat").mkdir(parents=True)
    target = tmp_path / "independent-app-support"
    mongo_inspected = False

    def fail_if_mongo_inspected(*_args, **_kwargs):
        nonlocal mongo_inspected
        mongo_inspected = True
        raise AssertionError("low-disk preflight must run before target Mongo inspection")

    monkeypatch.setattr(bundle, "mongo_database_empty", fail_if_mongo_inspected)
    monkeypatch.setattr(bundle, "storage_device_id", lambda _path: 1)
    monkeypatch.setattr(
        bundle.shutil,
        "disk_usage",
        lambda _path: type(
            "DiskUsage",
            (),
            {
                "total": bundle.CONTINUITY_DISK_RESERVE_BYTES,
                "used": 1,
                "free": bundle.CONTINUITY_DISK_RESERVE_BYTES - 1,
            },
        )(),
    )

    with pytest.raises(bundle.RestoreTransactionError, match="Insufficient disk space for continuity restore"):
        bundle.restore_bundle(
            snapshot=source,
            target_config_home=target,
            target_repo_root=target_repo,
            target_mongo_uri="mongodb://127.0.0.1:27117/RestoredViventium",
        )

    assert mongo_inspected is False
    assert not target.exists()
    assert not (target_repo / "viventium_v0_4" / "LibreChat" / "uploads").exists()
    assert not list(tmp_path.glob(".*restore-transaction.json"))


def test_restore_rolls_back_owned_state_when_disk_floor_drops_after_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = load_bundle_module()
    source = make_restore_ready_bundle(tmp_path / "bundle")
    tools, log = make_fake_mongo_tools(tmp_path / "fake-bin")
    monkeypatch.setenv("PATH", f"{tools}:{os.environ['PATH']}")
    monkeypatch.setenv("VIVENTIUM_FAKE_MONGO_LOG", str(log))
    target_repo = tmp_path / "fresh-checkout"
    (target_repo / "viventium_v0_4" / "LibreChat").mkdir(parents=True)
    target = tmp_path / "independent-app-support"
    observations = 0

    def changing_disk_usage(_path):
        nonlocal observations
        observations += 1
        free = (
            bundle.CONTINUITY_DISK_RESERVE_BYTES + 1024 * 1024 * 1024
            if observations == 1
            else bundle.CONTINUITY_DISK_RESERVE_BYTES - 1
        )
        return type(
            "DiskUsage",
            (),
            {"total": free + 1, "used": 1, "free": free},
        )()

    monkeypatch.setattr(bundle, "storage_device_id", lambda _path: 1)
    monkeypatch.setattr(bundle.shutil, "disk_usage", changing_disk_usage)

    with pytest.raises(bundle.RestoreTransactionError, match="Insufficient disk space for continuity restore"):
        bundle.restore_bundle(
            snapshot=source,
            target_config_home=target,
            target_repo_root=target_repo,
            target_mongo_uri="mongodb://127.0.0.1:27117/RestoredViventium",
        )

    assert observations == 2
    assert not target.exists()
    assert not (target_repo / "viventium_v0_4" / "LibreChat" / "uploads").exists()
    assert not list(tmp_path.glob(".*restore-transaction.json"))
    assert log.read_text(encoding="utf-8").splitlines() == ["drop"]


def test_product_owned_node_mongo_adapter_is_secret_excluding_and_loopback_only() -> None:
    source = MONGO_ADAPTER.read_text(encoding="utf-8")

    assert "createRequire(packageJson)" in source
    assert "projection: Object.fromEntries(USER_FIELDS" in source
    assert "'messages'" in source
    assert "'memoryentries'" in source
    assert "'agents'" in source
    assert "'assistants'" in source
    assert "'projects'" in source
    assert "'promptgroups'" in source
    assert "'sharedlinks'" in source
    assert "  'toolcalls'," not in source
    assert "'accessroles'" in source
    assert "'aclentries'" in source
    assert "'users'" in source
    assert "'tokens'" not in source
    assert "'sessions'" not in source
    assert "'pluginauths'" not in source
    assert "url.username" in source
    assert "url.password" in source
    assert "127.0.0.1" in source
    assert "target database is not empty" in source
    assert "assertClaim" in source
    assert "CLAIM_COLLECTION" in source
    assert "collStats" in source
    assert "estimatedBytes" in source

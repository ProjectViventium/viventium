from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = REPO_ROOT / "scripts" / "viventium" / "uploads_migration.py"
LAUNCHER_PATH = REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh"
LIBRECHAT_ROOT = REPO_ROOT / "viventium_v0_4" / "LibreChat"


def load_migration_module():
    spec = importlib.util.spec_from_file_location("viventium_uploads_migration", MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_librechat_ignores_canonical_uploads_compatibility_symlink() -> None:
    rules = (LIBRECHAT_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()

    assert "uploads/" in rules
    assert "/uploads" in rules


def make_layout(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    app_support = tmp_path / "Library" / "Application Support" / "Viventium"
    librechat = tmp_path / "checkout" / "viventium_v0_4" / "LibreChat"
    legacy = librechat / "uploads"
    canonical = app_support / "data" / "uploads"
    app_support.mkdir(parents=True, mode=0o700)
    librechat.mkdir(parents=True)
    return app_support, librechat, legacy, canonical


def write_synthetic_uploads(legacy: Path) -> None:
    nested = legacy / "synthetic-user" / "conversation"
    nested.mkdir(parents=True)
    (nested / "artifact.txt").write_bytes(b"synthetic upload payload\n")
    (legacy / "empty-folder").mkdir()


def test_migration_moves_legacy_tree_to_app_support_and_is_idempotent(tmp_path: Path) -> None:
    migration = load_migration_module()
    app_support, librechat, legacy, canonical = make_layout(tmp_path)
    write_synthetic_uploads(legacy)
    before = migration.fingerprint_tree(legacy)

    result = migration.migrate_uploads(
        app_support_dir=app_support,
        librechat_dir=librechat,
    )

    assert result["status"] == "migrated"
    assert legacy.is_symlink()
    assert os.readlink(legacy) == str(canonical)
    assert canonical.is_dir()
    assert migration.fingerprint_tree(canonical) == before
    assert (canonical / "synthetic-user" / "conversation" / "artifact.txt").read_bytes() == (
        b"synthetic upload payload\n"
    )
    receipt = app_support / "state" / "continuity" / "uploads-migration" / "receipt.json"
    assert receipt.is_file()
    assert receipt.stat().st_mode & 0o777 == 0o600
    assert "synthetic-user" not in receipt.read_text(encoding="utf-8")
    assert not (
        app_support / "state" / "continuity" / "uploads-migration" / "transaction.json"
    ).exists()

    after = migration.migrate_uploads(
        app_support_dir=app_support,
        librechat_dir=librechat,
    )
    assert after["status"] == "already_migrated"
    assert after["fingerprint"] == result["fingerprint"]


def test_populated_legacy_tree_is_not_moved_before_outer_upgrade_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = load_migration_module()
    app_support, librechat, legacy, canonical = make_layout(tmp_path)
    write_synthetic_uploads(legacy)
    before = migration.fingerprint_tree(legacy)
    transaction = app_support / "upgrade-backups" / "upgrade-synthetic"
    transaction.mkdir(parents=True)
    pointer = app_support / "state" / "upgrade-transaction-active.json"
    pointer.parent.mkdir(parents=True)
    pointer.write_text(
        json.dumps({"schema_version": 1, "transaction_path": str(transaction)}),
        encoding="utf-8",
    )
    pointer.chmod(0o600)
    fake_transaction = SimpleNamespace(
        SCHEMA_VERSION=1,
        lexical=lambda path: Path(os.path.abspath(path)),
        validate_chain=lambda *_args, **_kwargs: None,
        load_ledger=lambda _transaction: {
            "status": "active",
            "stage": "candidate_activated",
            "repo_root": str(tmp_path / "checkout"),
        },
    )
    monkeypatch.setitem(sys.modules, "upgrade_transaction", fake_transaction)

    result = migration.migrate_uploads(
        app_support_dir=app_support,
        librechat_dir=librechat,
    )

    assert result["status"] == "deferred_until_outer_commit"
    assert migration.fingerprint_tree(legacy) == before
    assert legacy.is_dir() and not legacy.is_symlink()
    assert not canonical.exists()
    assert not (app_support / "state" / "continuity" / "uploads-migration").exists()


def test_migration_fails_closed_instead_of_merging_two_populated_roots(tmp_path: Path) -> None:
    migration = load_migration_module()
    app_support, librechat, legacy, canonical = make_layout(tmp_path)
    write_synthetic_uploads(legacy)
    canonical.mkdir(parents=True)
    (canonical / "canonical-only.txt").write_text("preserve canonical\n", encoding="utf-8")

    with pytest.raises(migration.MigrationError, match="both contain files"):
        migration.migrate_uploads(
            app_support_dir=app_support,
            librechat_dir=librechat,
        )

    assert not legacy.is_symlink()
    assert (legacy / "synthetic-user" / "conversation" / "artifact.txt").is_file()
    assert (canonical / "canonical-only.txt").read_text(encoding="utf-8") == "preserve canonical\n"


def test_migration_rejects_symlinks_hardlinks_wrong_owner_and_bounds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = load_migration_module()

    app_support, librechat, legacy, _canonical = make_layout(tmp_path / "symlink")
    outside = tmp_path / "outside"
    outside.mkdir()
    legacy.symlink_to(outside, target_is_directory=True)
    with pytest.raises(migration.MigrationError, match="symlink"):
        migration.migrate_uploads(app_support_dir=app_support, librechat_dir=librechat)

    app_support, librechat, legacy, _canonical = make_layout(tmp_path / "hardlink")
    legacy.mkdir()
    anchor = tmp_path / "anchor.txt"
    anchor.write_text("synthetic\n", encoding="utf-8")
    os.link(anchor, legacy / "linked.txt")
    with pytest.raises(migration.MigrationError, match="hardlink"):
        migration.migrate_uploads(app_support_dir=app_support, librechat_dir=librechat)

    app_support, librechat, legacy, _canonical = make_layout(tmp_path / "owner")
    write_synthetic_uploads(legacy)
    actual_uid = os.getuid()
    monkeypatch.setattr(migration.os, "getuid", lambda: actual_uid + 1)
    with pytest.raises(migration.MigrationError, match="owner"):
        migration.migrate_uploads(app_support_dir=app_support, librechat_dir=librechat)
    monkeypatch.undo()

    app_support, librechat, legacy, _canonical = make_layout(tmp_path / "bounds")
    legacy.mkdir()
    (legacy / "one.txt").write_text("one", encoding="utf-8")
    (legacy / "two.txt").write_text("two", encoding="utf-8")
    monkeypatch.setattr(migration, "MAX_FILE_COUNT", 1)
    with pytest.raises(migration.MigrationError, match="file-count"):
        migration.migrate_uploads(app_support_dir=app_support, librechat_dir=librechat)


def test_interrupted_activation_recovers_from_journal_without_overwrite(tmp_path: Path) -> None:
    migration = load_migration_module()
    app_support, librechat, legacy, canonical = make_layout(tmp_path)
    write_synthetic_uploads(legacy)
    original = migration.fingerprint_tree(legacy)
    journal = app_support / "state" / "continuity" / "uploads-migration" / "transaction.json"

    with pytest.raises(migration.InjectedCrash):
        migration.migrate_uploads(
            app_support_dir=app_support,
            librechat_dir=librechat,
            fault_after="target_activated",
        )

    assert journal.is_file()
    assert canonical.is_dir()
    assert not legacy.is_symlink()

    result = migration.migrate_uploads(
        app_support_dir=app_support,
        librechat_dir=librechat,
    )

    assert result["status"] == "migrated"
    assert legacy.is_symlink()
    assert migration.fingerprint_tree(canonical) == original
    assert not journal.exists()
    assert not list(canonical.parent.glob(".uploads.migration-*"))
    assert not list(librechat.glob(".uploads.migration-*"))


def test_interrupted_committed_cleanup_recovers_forward_without_data_loss(
    tmp_path: Path,
) -> None:
    migration = load_migration_module()
    app_support, librechat, legacy, canonical = make_layout(tmp_path)
    write_synthetic_uploads(legacy)
    original = migration.fingerprint_tree(legacy)

    with pytest.raises(migration.InjectedCrash):
        migration.migrate_uploads(
            app_support_dir=app_support,
            librechat_dir=librechat,
            fault_after="committed",
        )

    assert legacy.is_symlink()
    assert migration.fingerprint_tree(canonical) == original
    result = migration.migrate_uploads(
        app_support_dir=app_support,
        librechat_dir=librechat,
    )
    assert result["status"] == "already_migrated"
    assert migration.fingerprint_tree(canonical) == original
    assert not list(canonical.parent.glob(".uploads.migration-*"))
    assert not list(librechat.glob(".uploads.migration-*"))


def test_source_mutation_during_copy_rolls_back_without_losing_predecessor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = load_migration_module()
    app_support, librechat, legacy, canonical = make_layout(tmp_path)
    write_synthetic_uploads(legacy)
    original_copy = migration.copy_tree_no_follow

    def copy_then_mutate(source: Path, destination: Path) -> None:
        original_copy(source, destination)
        (source / "late-write.txt").write_text("late write\n", encoding="utf-8")

    monkeypatch.setattr(migration, "copy_tree_no_follow", copy_then_mutate)
    with pytest.raises(migration.MigrationError, match="changed during migration"):
        migration.migrate_uploads(
            app_support_dir=app_support,
            librechat_dir=librechat,
        )

    assert not legacy.is_symlink()
    assert (legacy / "late-write.txt").is_file()
    assert not canonical.exists()


def test_launcher_migrates_only_before_starting_a_stopped_librechat_backend() -> None:
    source = LAUNCHER_PATH.read_text(encoding="utf-8")

    assert "migrate_canonical_uploads_before_librechat_start() {" in source
    helper = source.index("migrate_canonical_uploads_before_librechat_start() {")
    migration_cli = source.index('uploads_migration.py"', helper)
    stopped_guard = source.index('"$LIBRECHAT_BACKEND_ALREADY_RUNNING" != "true"', migration_cli)
    call = source.index("migrate_canonical_uploads_before_librechat_start", stopped_guard)
    env_render = source.index("ensure_librechat_env", call)
    assert helper < migration_cli < stopped_guard < call < env_render
    assert '--canonical-root "${VIVENTIUM_LIBRECHAT_UPLOADS_ROOT' in source


def test_cli_summary_never_emits_upload_names_or_contents(tmp_path: Path, capsys) -> None:
    migration = load_migration_module()
    app_support, librechat, legacy, _canonical = make_layout(tmp_path)
    write_synthetic_uploads(legacy)

    exit_code = migration.main(
        [
            "--app-support-dir",
            str(app_support),
            "--librechat-dir",
            str(librechat),
        ]
    )

    output = capsys.readouterr().out
    payload = json.loads(output)
    assert exit_code == 0
    assert payload["status"] == "migrated"
    assert "synthetic-user" not in output
    assert "synthetic upload payload" not in output


def test_executable_cli_migrates_an_isolated_source_fixture(tmp_path: Path) -> None:
    app_support, librechat, legacy, canonical = make_layout(tmp_path)
    write_synthetic_uploads(legacy)

    completed = subprocess.run(
        [
            sys.executable,
            str(MIGRATION_PATH),
            "--app-support-dir",
            str(app_support),
            "--librechat-dir",
            str(librechat),
            "--canonical-root",
            str(canonical),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["status"] == "migrated"
    assert legacy.is_symlink()
    assert (canonical / "synthetic-user" / "conversation" / "artifact.txt").is_file()
    assert "synthetic-user" not in completed.stdout
    assert "synthetic upload payload" not in completed.stdout

from __future__ import annotations

import concurrent.futures
import importlib.util
import json
import os
import subprocess
import sys
import threading
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


def test_shared_checkout_preserves_other_runtime_link_and_isolates_canonical_roots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = load_migration_module()
    shared_checkout = tmp_path / "checkout" / "viventium_v0_4" / "LibreChat"
    shared_checkout.mkdir(parents=True)
    legacy = shared_checkout / "uploads"

    first_support = tmp_path / "runtime-a" / "Viventium"
    first_support.mkdir(parents=True, mode=0o700)
    first_canonical = first_support / "data" / "uploads"
    write_synthetic_uploads(legacy)
    migration.migrate_uploads(
        app_support_dir=first_support,
        librechat_dir=shared_checkout,
    )
    first_only = first_canonical / "runtime-a-only.txt"
    first_only.write_text("runtime a remains isolated\n", encoding="utf-8")
    first_before = first_only.read_bytes()
    first_target = os.readlink(legacy)

    second_support = tmp_path / "runtime-b" / "Viventium"
    second_support.mkdir(parents=True, mode=0o700)
    second_canonical = second_support / "data" / "uploads"
    original_fingerprint_tree = migration.fingerprint_tree

    def reject_cross_runtime_enumeration(root: Path) -> dict:
        if migration.lexical(root) == migration.lexical(first_canonical):
            raise AssertionError("the second runtime followed the first runtime's uploads link")
        return original_fingerprint_tree(root)

    monkeypatch.setattr(migration, "fingerprint_tree", reject_cross_runtime_enumeration)

    result = migration.migrate_uploads(
        app_support_dir=second_support,
        librechat_dir=shared_checkout,
    )

    assert result["status"] == "other_runtime_compatibility_preserved"
    assert legacy.is_symlink()
    assert os.readlink(legacy) == first_target
    assert first_only.read_bytes() == first_before
    assert second_canonical.is_dir()
    assert second_canonical.stat().st_mode & 0o777 == 0o700
    assert not (second_canonical / "runtime-a-only.txt").exists()
    second_receipt = (
        second_support / "state" / "continuity" / "uploads-migration" / "receipt.json"
    )
    second_receipt_payload = json.loads(second_receipt.read_text(encoding="utf-8"))
    assert second_receipt_payload["legacyCompatibility"] == (
        "other_runtime_exact_symlink_preserved"
    )
    assert second_receipt_payload["observedLinkTargetSha256"] == migration.hash_path_identity(
        first_canonical
    )
    second_receipt_before = second_receipt.read_bytes()

    (second_canonical / "runtime-b-only.txt").write_text(
        "runtime b remains isolated\n",
        encoding="utf-8",
    )
    assert not (first_canonical / "runtime-b-only.txt").exists()
    repeated = migration.migrate_uploads(
        app_support_dir=second_support,
        librechat_dir=shared_checkout,
    )
    assert repeated["status"] == "other_runtime_compatibility_preserved"
    assert second_receipt.read_bytes() == second_receipt_before

    fresh_checkout = tmp_path / "fresh-checkout" / "viventium_v0_4" / "LibreChat"
    fresh_checkout.mkdir(parents=True)
    with pytest.raises(migration.InjectedCrash):
        migration.migrate_uploads(
            app_support_dir=second_support,
            librechat_dir=fresh_checkout,
            fault_after="link_activated",
        )
    recovered = migration.migrate_uploads(
        app_support_dir=second_support,
        librechat_dir=fresh_checkout,
    )
    assert recovered["status"] == "initialized"
    assert (fresh_checkout / "uploads").is_symlink()
    assert os.readlink(fresh_checkout / "uploads") == str(second_canonical)
    assert (second_canonical / "runtime-b-only.txt").read_text(encoding="utf-8") == (
        "runtime b remains isolated\n"
    )


def test_shared_checkout_rejects_unreceipted_other_runtime_symlink(tmp_path: Path) -> None:
    migration = load_migration_module()
    shared_checkout = tmp_path / "checkout" / "viventium_v0_4" / "LibreChat"
    shared_checkout.mkdir(parents=True)
    legacy = shared_checkout / "uploads"
    unrecognized_support = tmp_path / "unrecognized" / "Viventium"
    unrecognized_canonical = unrecognized_support / "data" / "uploads"
    unrecognized_canonical.mkdir(parents=True)
    legacy.symlink_to(unrecognized_canonical, target_is_directory=True)
    current_support = tmp_path / "current" / "Viventium"
    current_support.mkdir(parents=True, mode=0o700)

    with pytest.raises(migration.MigrationError, match="unexpected symlink"):
        migration.migrate_uploads(
            app_support_dir=current_support,
            librechat_dir=shared_checkout,
        )

    assert legacy.is_symlink()
    assert os.readlink(legacy) == str(unrecognized_canonical)
    assert not (current_support / "data" / "uploads").exists()


def test_simultaneous_first_starts_reconcile_the_winning_runtime_link(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = load_migration_module()
    shared_checkout = tmp_path / "checkout" / "viventium_v0_4" / "LibreChat"
    shared_checkout.mkdir(parents=True)
    app_support_roots = [
        tmp_path / "runtime-a" / "Viventium",
        tmp_path / "runtime-b" / "Viventium",
    ]
    for app_support in app_support_roots:
        app_support.mkdir(parents=True, mode=0o700)

    symlink_barrier = threading.Barrier(2)
    real_symlink = migration.os.symlink

    def simultaneous_symlink(*args, **kwargs):
        symlink_barrier.wait(timeout=5)
        return real_symlink(*args, **kwargs)

    monkeypatch.setattr(migration.os, "symlink", simultaneous_symlink)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                migration.migrate_uploads,
                app_support_dir=app_support,
                librechat_dir=shared_checkout,
            )
            for app_support in app_support_roots
        ]
        results = [future.result(timeout=10) for future in futures]

    legacy = shared_checkout / "uploads"
    canonical_roots = [root / "data" / "uploads" for root in app_support_roots]
    assert legacy.is_symlink()
    assert Path(os.readlink(legacy)) in canonical_roots
    assert {result["status"] for result in results} == {
        "initialized",
        "other_runtime_compatibility_preserved",
    }
    for app_support, canonical in zip(app_support_roots, canonical_roots, strict=True):
        assert canonical.is_dir()
        receipt = (
            app_support
            / "state"
            / "continuity"
            / "uploads-migration"
            / "receipt.json"
        )
        assert receipt.is_file()


def test_staggered_shared_checkout_start_waits_for_winner_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = load_migration_module()
    shared_checkout = tmp_path / "checkout" / "viventium_v0_4" / "LibreChat"
    shared_checkout.mkdir(parents=True)
    first_support = tmp_path / "runtime-a" / "Viventium"
    second_support = tmp_path / "runtime-b" / "Viventium"
    first_support.mkdir(parents=True, mode=0o700)
    second_support.mkdir(parents=True, mode=0o700)
    first_receipt = (
        first_support / "state" / "continuity" / "uploads-migration" / "receipt.json"
    )
    link_visible = threading.Event()
    allow_receipt = threading.Event()
    loser_waiting = threading.Event()
    real_write_json_atomic = migration.write_json_atomic
    real_wait = migration.wait_for_recognized_other_runtime_link

    def delayed_winner_receipt(path: Path, payload: dict) -> None:
        if path == first_receipt and payload.get("legacyCompatibility") == "exact_symlink":
            link_visible.set()
            assert allow_receipt.wait(timeout=5)
        real_write_json_atomic(path, payload)

    def observed_wait(*, legacy: Path, canonical: Path) -> Path:
        loser_waiting.set()
        return real_wait(legacy=legacy, canonical=canonical)

    monkeypatch.setattr(migration, "write_json_atomic", delayed_winner_receipt)
    monkeypatch.setattr(
        migration,
        "wait_for_recognized_other_runtime_link",
        observed_wait,
    )
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        winner = executor.submit(
            migration.migrate_uploads,
            app_support_dir=first_support,
            librechat_dir=shared_checkout,
        )
        assert link_visible.wait(timeout=5)
        loser = executor.submit(
            migration.migrate_uploads,
            app_support_dir=second_support,
            librechat_dir=shared_checkout,
        )
        assert loser_waiting.wait(timeout=5)
        allow_receipt.set()
        results = [winner.result(timeout=10), loser.result(timeout=10)]

    assert {result["status"] for result in results} == {
        "initialized",
        "other_runtime_compatibility_preserved",
    }
    assert (first_support / "data" / "uploads").is_dir()
    assert (second_support / "data" / "uploads").is_dir()


def test_same_app_support_concurrent_starts_are_serialized(
    tmp_path: Path,
) -> None:
    migration = load_migration_module()
    app_support, librechat, _legacy, canonical = make_layout(tmp_path)
    start_barrier = threading.Barrier(2)

    def start() -> dict:
        start_barrier.wait(timeout=5)
        return migration.migrate_uploads(
            app_support_dir=app_support,
            librechat_dir=librechat,
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(start) for _ in range(2)]
        results = [future.result(timeout=10) for future in futures]

    assert {result["status"] for result in results} == {
        "initialized",
        "already_migrated",
    }
    assert canonical.is_dir()
    assert (librechat / "uploads").is_symlink()
    lock_path = (
        app_support / "state" / "continuity" / "uploads-migration" / "migration.lock"
    )
    assert lock_path.is_file()
    assert lock_path.stat().st_mode & 0o777 == 0o600


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

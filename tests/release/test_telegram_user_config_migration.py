from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import stat
import subprocess
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "viventium" / "telegram_user_config_migration.py"
LAUNCHER = REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh"
CLI = REPO_ROOT / "bin" / "viventium"
HELPER_INSTALLER = REPO_ROOT / "scripts" / "viventium" / "install_macos_helper.sh"


def _load_migration_module():
    spec = importlib.util.spec_from_file_location(
        "telegram_user_config_migration_under_test",
        SCRIPT,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _ensure_private_root(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--ensure-private-root",
            str(path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def _extract_shell_function(source: str, name: str) -> str:
    lines = source.splitlines()
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


def _legacy_root(repo: Path) -> Path:
    return (
        repo
        / "viventium_v0_4"
        / "telegram-viventium"
        / "TelegramVivBot"
        / "user_configs"
    )


def _run(
    repo: Path,
    support: Path,
    *,
    env: dict[str, str] | None = None,
    active_config_root: Path | bool | None = None,
    writer_stopped: bool = True,
    observe_real_processes: bool = False,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(SCRIPT),
        "--repo-root",
        str(repo),
        "--app-support-dir",
        str(support),
    ]
    if active_config_root is None:
        active_config_root = _legacy_root(repo)
    if isinstance(active_config_root, Path):
        command.extend(["--active-config-root", str(active_config_root)])
    if writer_stopped:
        command.append("--writer-stopped")
    run_env = {**os.environ, **(env or {})}
    if not observe_real_processes:
        fake_bin = support.parent / ".qa-process-bin"
        fake_bin.mkdir(parents=True, exist_ok=True)
        fake_ps = fake_bin / "ps"
        fake_ps.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        fake_ps.chmod(0o755)
        run_env["PATH"] = (
            f"{fake_bin}{os.pathsep}{run_env.get('PATH', '')}"
        )
    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        env=run_env,
    )


def _tree_fingerprint(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.exists():
        return digest.hexdigest()
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def test_migration_copies_legacy_preferences_exactly_and_is_idempotent(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    support = tmp_path / "app-support"
    legacy = _legacy_root(repo)
    legacy.mkdir(parents=True)
    source = b'{"UNKNOWN_PERSONALIZATION":{"kept":true},"LONG_TEXT":false}\n'
    (legacy / "synthetic-user.json").write_bytes(source)
    source_before = _tree_fingerprint(legacy)

    first = _run(repo, support)

    assert first.returncode == 0, first.stderr
    assert json.loads(first.stdout)["status"] == "migrated"
    canonical = support / "state" / "telegram-user-configs"
    assert (canonical / "synthetic-user.json").read_bytes() == source
    assert _tree_fingerprint(legacy) == source_before
    receipt = (
        support
        / "state"
        / "telegram-user-config-migration"
        / "authority.json"
    )
    receipt_before = receipt.read_bytes()
    canonical_before = _tree_fingerprint(canonical)

    second = _run(repo, support)

    assert second.returncode == 0, second.stderr
    assert json.loads(second.stdout)["status"] == "canonical-authoritative"
    assert receipt.read_bytes() == receipt_before
    assert _tree_fingerprint(canonical) == canonical_before
    assert _tree_fingerprint(legacy) == source_before


def test_existing_canonical_preferences_harden_legacy_modes_without_byte_drift(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    support = tmp_path / "app-support"
    repo.mkdir()
    canonical = support / "state" / "telegram-user-configs"
    nested = canonical / "nested"
    nested.mkdir(parents=True, mode=0o755)
    canonical.chmod(0o755)
    nested.chmod(0o755)
    preference = nested / "global.json"
    preference.write_bytes(b'{"personalization":"preserved"}\n')
    preference.chmod(0o644)
    before = _tree_fingerprint(canonical)
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    fake_ps = fake_bin / "ps"
    fake_ps.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_ps.chmod(0o755)
    isolated_process_env = {
        "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
    }

    first = _run(
        repo,
        support,
        active_config_root=canonical,
        env=isolated_process_env,
    )

    assert first.returncode == 0, first.stderr
    assert json.loads(first.stdout)["status"] == (
        "canonical-authority-initialized"
    )
    assert _tree_fingerprint(canonical) == before
    assert stat.S_IMODE(canonical.stat().st_mode) == 0o700
    assert stat.S_IMODE(nested.stat().st_mode) == 0o700
    assert stat.S_IMODE(preference.stat().st_mode) == 0o600

    second = _run(
        repo,
        support,
        active_config_root=canonical,
        env=isolated_process_env,
        writer_stopped=False,
    )

    assert second.returncode == 0, second.stderr
    assert json.loads(second.stdout)["status"] == "canonical-authoritative"
    assert _tree_fingerprint(canonical) == before


def test_canonical_permission_hardening_is_descriptor_bound_and_no_follow() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    function = source.split(
        "def _harden_canonical_tree(",
        1,
    )[1].split("\ndef _merged_value(", 1)[0]

    assert "dir_fd=directory_descriptor" in function
    assert "follow_symlinks=False" in function
    assert 'getattr(os, "O_NOFOLLOW", 0)' in function
    assert "os.fchmod(" in function
    assert ".chmod(" not in function
    assert ".stat()" not in function


def test_conflict_preserves_active_legacy_values_and_backs_up_canonical(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    support = tmp_path / "app-support"
    legacy = _legacy_root(repo)
    canonical = support / "state" / "telegram-user-configs"
    legacy.mkdir(parents=True)
    canonical.mkdir(parents=True)
    legacy_value = {
        "ACTIVE_LEGACY_VALUE": "preserve-me",
        "SHARED": "legacy-wins",
    }
    canonical_value = {
        "CANONICAL_ONLY": "also-preserve-me",
        "SHARED": "older-canonical",
    }
    legacy_bytes = (json.dumps(legacy_value) + "\n").encode()
    canonical_bytes = (json.dumps(canonical_value) + "\n").encode()
    (legacy / "global.json").write_bytes(legacy_bytes)
    (canonical / "global.json").write_bytes(canonical_bytes)

    migrated = _run(repo, support)

    assert migrated.returncode == 0, migrated.stderr
    merged = json.loads((canonical / "global.json").read_text(encoding="utf-8"))
    assert merged == {
        "ACTIVE_LEGACY_VALUE": "preserve-me",
        "CANONICAL_ONLY": "also-preserve-me",
        "SHARED": "legacy-wins",
    }
    assert (legacy / "global.json").read_bytes() == legacy_bytes
    backups = list(
        (
            support
            / "state"
            / "telegram-user-config-migration"
            / "backups"
        ).rglob("*")
    )
    backups = [path for path in backups if path.is_file()]
    assert len(backups) == 1
    assert backups[0].read_bytes() == canonical_bytes


def test_migration_preserves_explicit_custom_directory(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    support = tmp_path / "app-support"
    legacy = _legacy_root(repo)
    legacy.mkdir(parents=True)
    (legacy / "global.json").write_text('{"legacy":true}\n', encoding="utf-8")
    explicit = tmp_path / "operator-owned-config"
    explicit.mkdir()
    (explicit / "global.json").write_text('{"explicit":true}\n', encoding="utf-8")

    completed = _run(
        repo,
        support,
        env={"VIVENTIUM_TELEGRAM_USER_CONFIGS_DIR": str(explicit)},
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["status"] == "explicit-override-preserved"
    assert not (support / "state" / "telegram-user-configs").exists()
    assert (explicit / "global.json").read_text(encoding="utf-8") == (
        '{"explicit":true}\n'
    )
    selection_authority = (
        support
        / "state"
        / "telegram-user-config-migration"
        / "explicit-authority.json"
    )
    authority_payload = json.loads(selection_authority.read_text(encoding="utf-8"))
    assert authority_payload == {
        "schema_version": 2,
        "kind": "viventium-telegram-explicit-preference-authority",
        "status": "committed",
        "generation": hashlib.sha256(
            ("explicit-authority\0" + str(explicit)).encode("utf-8")
        ).hexdigest(),
        "preference_root": str(explicit),
    }
    durable_discovery = _run(
        repo,
        support,
        env={"VIVENTIUM_TELEGRAM_USER_CONFIGS_DIR": ""},
        active_config_root=explicit,
    )
    assert durable_discovery.returncode == 0, durable_discovery.stderr
    assert json.loads(durable_discovery.stdout)["status"] == (
        "explicit-override-preserved"
    )
    assert not (support / "state" / "telegram-user-configs").exists()
    assert (explicit / "global.json").read_text(encoding="utf-8") == (
        '{"explicit":true}\n'
    )

    resolver = _extract_shell_function(
        CLI.read_text(encoding="utf-8"),
        "resolve_predecessor_telegram_user_config_root",
    )
    command = (
        "set -euo pipefail\n"
        f"REPO_ROOT={shlex.quote(str(repo))}\n"
        f"APP_SUPPORT_DIR={shlex.quote(str(support))}\n"
        f"PYTHON_BIN={shlex.quote(sys.executable)}\n"
        f"{resolver}"
        'resolve_predecessor_telegram_user_config_root "$REPO_ROOT"\n'
    )
    environment = dict(os.environ)
    environment.pop("VIVENTIUM_TELEGRAM_USER_CONFIGS_DIR", None)
    environment.pop("VIVENTIUM_PRIVATE_CURATED_DIR", None)
    environment.pop("VIVENTIUM_PRIVATE_MIRROR_DIR", None)
    cold_start = subprocess.run(
        ["bash", "-c", command],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert cold_start.returncode == 0, cold_start.stderr
    assert Path(cold_start.stdout.strip()) == explicit


def test_established_other_checkout_fails_closed_until_writer_is_stopped(
    tmp_path: Path,
) -> None:
    current_repo = tmp_path / "current-checkout"
    previous_repo = tmp_path / "established-checkout"
    support = tmp_path / "app-support"
    current_repo.mkdir()
    established = _legacy_root(previous_repo)
    established.mkdir(parents=True)
    value = b'{"checkout":"established","personalization":"preserve"}\n'
    (established / "global.json").write_bytes(value)

    refused = _run(
        current_repo,
        support,
        active_config_root=established,
        writer_stopped=False,
    )

    assert refused.returncode != 0
    assert "writer must be stopped" in refused.stderr.lower()
    assert not (
        support / "state" / "telegram-user-config-migration" / "authority.json"
    ).exists()
    assert not (support / "state" / "telegram-user-configs").exists()
    assert (established / "global.json").read_bytes() == value

    migrated = _run(
        current_repo,
        support,
        active_config_root=established,
        writer_stopped=True,
    )

    assert migrated.returncode == 0, migrated.stderr
    assert json.loads(migrated.stdout)["status"] == "migrated"
    assert (
        support / "state" / "telegram-user-configs" / "global.json"
    ).read_bytes() == value
    assert (established / "global.json").read_bytes() == value


def test_durably_observed_missing_preference_root_fails_closed(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "current-checkout"
    support = tmp_path / "app-support"
    repo.mkdir()
    missing = _legacy_root(tmp_path / "established-checkout")

    completed = _run(
        repo,
        support,
        active_config_root=missing,
        writer_stopped=True,
    )

    assert completed.returncode != 0
    assert "active" in completed.stderr.lower()
    assert "unavailable" in completed.stderr.lower()
    assert not (
        support
        / "state"
        / "telegram-user-config-migration"
        / "authority.json"
    ).exists()
    assert not (support / "state" / "telegram-user-configs").exists()


def test_cli_resolver_prefers_established_checkout_over_stale_canonical_fallback(
    tmp_path: Path,
) -> None:
    current_repo = tmp_path / "current-checkout"
    previous_repo = tmp_path / "established-checkout"
    support = tmp_path / "app-support"
    current_repo.mkdir()
    established = _legacy_root(previous_repo)
    established.mkdir(parents=True)
    (established / "global.json").write_text(
        '{"authority":"established"}\n',
        encoding="utf-8",
    )
    canonical = support / "state" / "telegram-user-configs"
    canonical.mkdir(parents=True)
    (canonical / "global.json").write_text(
        '{"authority":"stale-canonical"}\n',
        encoding="utf-8",
    )
    active_checkout = support / "state" / "active-checkout.json"
    active_checkout.write_text(
        json.dumps({"repoRoot": str(previous_repo)}) + "\n",
        encoding="utf-8",
    )
    active_checkout.chmod(0o600)
    resolver = _extract_shell_function(
        CLI.read_text(encoding="utf-8"),
        "resolve_predecessor_telegram_user_config_root",
    )
    command = (
        "set -euo pipefail\n"
        f"REPO_ROOT={shlex.quote(str(current_repo))}\n"
        f"APP_SUPPORT_DIR={shlex.quote(str(support))}\n"
        f"PYTHON_BIN={shlex.quote(sys.executable)}\n"
        f"{resolver}"
        'resolve_predecessor_telegram_user_config_root "$REPO_ROOT"\n'
    )
    environment = dict(os.environ)
    environment.pop("VIVENTIUM_TELEGRAM_USER_CONFIGS_DIR", None)
    environment.pop("VIVENTIUM_PRIVATE_CURATED_DIR", None)
    environment.pop("VIVENTIUM_PRIVATE_MIRROR_DIR", None)

    resolved = subprocess.run(
        ["bash", "-c", command],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert resolved.returncode == 0, resolved.stderr
    assert Path(resolved.stdout.strip()) == established


def test_cli_resolver_preserves_missing_established_checkout_as_fail_closed_signal(
    tmp_path: Path,
) -> None:
    current_repo = tmp_path / "current-checkout"
    previous_repo = tmp_path / "established-checkout"
    support = tmp_path / "app-support"
    current_repo.mkdir()
    active_checkout = support / "state" / "active-checkout.json"
    active_checkout.parent.mkdir(parents=True)
    active_checkout.write_text(
        json.dumps({"repoRoot": str(previous_repo)}) + "\n",
        encoding="utf-8",
    )
    active_checkout.chmod(0o600)
    resolver = _extract_shell_function(
        CLI.read_text(encoding="utf-8"),
        "resolve_predecessor_telegram_user_config_root",
    )
    command = (
        "set -euo pipefail\n"
        f"REPO_ROOT={shlex.quote(str(current_repo))}\n"
        f"APP_SUPPORT_DIR={shlex.quote(str(support))}\n"
        f"PYTHON_BIN={shlex.quote(sys.executable)}\n"
        f"{resolver}"
        'resolve_predecessor_telegram_user_config_root "$REPO_ROOT"\n'
    )
    environment = dict(os.environ)
    environment.pop("VIVENTIUM_TELEGRAM_USER_CONFIGS_DIR", None)
    environment.pop("VIVENTIUM_PRIVATE_CURATED_DIR", None)
    environment.pop("VIVENTIUM_PRIVATE_MIRROR_DIR", None)

    resolved = subprocess.run(
        ["bash", "-c", command],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert resolved.returncode == 0, resolved.stderr
    assert Path(resolved.stdout.strip()) == _legacy_root(previous_repo)


def test_canonical_user_edit_survives_every_later_migration(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    support = tmp_path / "app-support"
    legacy = _legacy_root(repo)
    legacy.mkdir(parents=True)
    (legacy / "global.json").write_text('{"choice":"legacy"}\n', encoding="utf-8")

    first = _run(repo, support)
    assert first.returncode == 0, first.stderr

    canonical = support / "state" / "telegram-user-configs" / "global.json"
    canonical.write_text('{"choice":"new-user-edit"}\n', encoding="utf-8")
    edited = canonical.read_bytes()
    second = _run(repo, support)

    assert second.returncode == 0, second.stderr
    assert json.loads(second.stdout)["status"] == "canonical-authoritative"
    assert canonical.read_bytes() == edited


def test_empty_first_install_commits_canonical_authority(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    support = tmp_path / "app-support"
    repo.mkdir()

    initialized = _run(
        repo,
        support,
        active_config_root=False,
        writer_stopped=False,
    )

    assert initialized.returncode == 0, initialized.stderr
    assert json.loads(initialized.stdout)["status"] == (
        "canonical-authority-initialized"
    )
    stale = _legacy_root(repo)
    stale.mkdir(parents=True)
    (stale / "global.json").write_text('{"choice":"stale"}\n', encoding="utf-8")
    rerun = _run(repo, support)
    assert rerun.returncode == 0, rerun.stderr
    assert json.loads(rerun.stdout)["status"] == "canonical-authoritative"
    assert not (
        support / "state" / "telegram-user-configs" / "global.json"
    ).exists()


def test_retired_legacy_root_is_not_reimported_after_checkout_relocation(
    tmp_path: Path,
) -> None:
    first_repo = tmp_path / "first-repo"
    second_repo = tmp_path / "relocated-repo"
    support = tmp_path / "app-support"
    first_legacy = _legacy_root(first_repo)
    second_legacy = _legacy_root(second_repo)
    first_legacy.mkdir(parents=True)
    second_legacy.mkdir(parents=True)
    (first_legacy / "global.json").write_text(
        '{"choice":"first-active"}\n', encoding="utf-8"
    )
    (second_legacy / "global.json").write_text(
        '{"choice":"stale-relocated"}\n', encoding="utf-8"
    )

    first = _run(first_repo, support)
    assert first.returncode == 0, first.stderr
    canonical = support / "state" / "telegram-user-configs" / "global.json"
    canonical.write_text('{"choice":"canonical-edit"}\n', encoding="utf-8")
    before = canonical.read_bytes()

    second = _run(
        second_repo,
        support,
        active_config_root=second_legacy,
    )

    assert second.returncode == 0, second.stderr
    assert json.loads(second.stdout)["status"] == "canonical-authoritative"
    assert canonical.read_bytes() == before


def test_exact_proven_alternate_predecessor_root_is_migrated(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    support = tmp_path / "app-support"
    default_legacy = _legacy_root(repo)
    alternate = (
        repo
        / "viventium_v0_4"
        / "telegram-viventium"
        / "user_configs"
    )
    default_legacy.mkdir(parents=True)
    alternate.mkdir(parents=True)
    (default_legacy / "global.json").write_text(
        '{"choice":"inactive-default"}\n', encoding="utf-8"
    )
    (alternate / "global.json").write_text(
        '{"choice":"proven-active-alternate"}\n', encoding="utf-8"
    )

    migrated = _run(repo, support, active_config_root=alternate)

    assert migrated.returncode == 0, migrated.stderr
    canonical = support / "state" / "telegram-user-configs" / "global.json"
    assert json.loads(canonical.read_text(encoding="utf-8")) == {
        "choice": "proven-active-alternate"
    }


def test_unknown_first_migration_authority_fails_without_mutation(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    support = tmp_path / "app-support"
    legacy = _legacy_root(repo)
    canonical = support / "state" / "telegram-user-configs"
    legacy.mkdir(parents=True)
    canonical.mkdir(parents=True)
    (legacy / "global.json").write_text('{"authority":"legacy"}\n', encoding="utf-8")
    (canonical / "global.json").write_text(
        '{"authority":"canonical"}\n', encoding="utf-8"
    )
    before = _tree_fingerprint(support)

    completed = _run(
        repo,
        support,
        active_config_root=False,
    )

    assert completed.returncode != 0
    assert "authority" in completed.stderr.lower()
    assert _tree_fingerprint(support) == before


def test_interrupted_multi_file_migration_resumes_from_durable_journal(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    support = tmp_path / "app-support"
    legacy = _legacy_root(repo)
    legacy.mkdir(parents=True)
    (legacy / "one.json").write_text('{"value":1}\n', encoding="utf-8")
    (legacy / "two.json").write_text('{"value":2}\n', encoding="utf-8")

    interrupted = _run(
        repo,
        support,
        env={"VIVENTIUM_QA_TELEGRAM_MIGRATION_INTERRUPT_AFTER": "1"},
    )

    assert interrupted.returncode != 0
    state = support / "state" / "telegram-user-config-migration"
    assert (state / "pending.json").is_file()
    resumed = _run(repo, support)

    assert resumed.returncode == 0, resumed.stderr
    assert json.loads(resumed.stdout)["status"] == "migrated"
    assert not (state / "pending.json").exists()
    assert (support / "state" / "telegram-user-configs" / "one.json").is_file()
    assert (support / "state" / "telegram-user-configs" / "two.json").is_file()


def test_resume_revalidates_and_replays_cursor_prefix_after_outer_restore(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    support = tmp_path / "app-support"
    legacy = _legacy_root(repo)
    legacy.mkdir(parents=True)
    values = {
        "one.json": b'{"value":1}\n',
        "two.json": b'{"value":2}\n',
    }
    for name, value in values.items():
        (legacy / name).write_bytes(value)

    interrupted = _run(
        repo,
        support,
        env={"VIVENTIUM_QA_TELEGRAM_MIGRATION_INTERRUPT_AFTER": "2"},
    )

    assert interrupted.returncode != 0
    state = support / "state" / "telegram-user-config-migration"
    pending = json.loads((state / "pending.json").read_text(encoding="utf-8"))
    assert pending["next_index"] == 1
    canonical = support / "state" / "telegram-user-configs"
    shutil.rmtree(canonical)

    resumed = _run(repo, support)

    assert resumed.returncode == 0, resumed.stderr
    assert json.loads(resumed.stdout)["status"] == "migrated"
    for name, value in values.items():
        assert (canonical / name).read_bytes() == value
        assert (legacy / name).read_bytes() == value
    assert not (state / "pending.json").exists()
    assert (state / "authority.json").is_file()


def test_interrupted_migration_refuses_changed_legacy_source(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    support = tmp_path / "app-support"
    legacy = _legacy_root(repo)
    legacy.mkdir(parents=True)
    source = legacy / "global.json"
    source.write_text('{"value":"before"}\n', encoding="utf-8")
    interrupted = _run(
        repo,
        support,
        env={"VIVENTIUM_QA_TELEGRAM_MIGRATION_INTERRUPT_AFTER": "1"},
    )
    assert interrupted.returncode != 0
    source.write_text('{"value":"newer-surviving-writer"}\n', encoding="utf-8")

    resumed = _run(repo, support)

    assert resumed.returncode != 0
    assert "legacy" in resumed.stderr.lower()
    assert not (
        support
        / "state"
        / "telegram-user-config-migration"
        / "authority.json"
    ).exists()


def test_active_telegram_writer_blocks_before_journal_or_canonical_write(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    support = tmp_path / "app-support"
    legacy = _legacy_root(repo)
    legacy.mkdir(parents=True)
    (legacy / "global.json").write_text('{"value":"legacy"}\n', encoding="utf-8")
    marker = legacy.parent / "bot.py"
    marker.write_text("# synthetic writer identity\n", encoding="utf-8")
    fake_bin = tmp_path / "active-writer-bin"
    fake_bin.mkdir()
    fake_ps = fake_bin / "ps"
    fake_ps.write_text(
        (
            "#!/bin/sh\n"
            f"printf '%s\\n' '4242 {os.getuid()} "
            f"{shlex.quote(sys.executable)} {shlex.quote(str(marker))}'\n"
        ),
        encoding="utf-8",
    )
    fake_ps.chmod(0o755)
    completed = _run(
        repo,
        support,
        observe_real_processes=True,
        env={
            "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
        },
    )

    assert completed.returncode != 0
    assert "writer" in completed.stderr.lower()
    state = support / "state" / "telegram-user-config-migration"
    assert not (state / "pending.json").exists()
    assert not (state / "authority.json").exists()
    assert not (support / "state" / "telegram-user-configs").exists()


def test_unrelated_runtime_writer_does_not_block_canonical_authority_recheck(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    support = tmp_path / "app-support"
    repo.mkdir()
    canonical = support / "state" / "telegram-user-configs"

    initialized = _run(
        repo,
        support,
        active_config_root=False,
        writer_stopped=False,
    )
    assert initialized.returncode == 0, initialized.stderr
    canonical.mkdir(parents=True)

    unrelated_bot = (
        tmp_path
        / "other-app-support"
        / "runtime-components"
        / "telegram-viventium"
        / "TelegramVivBot"
        / "bot.py"
    )
    unrelated_bot.parent.mkdir(parents=True)
    unrelated_bot.write_text("# unrelated synthetic writer\n", encoding="utf-8")
    fake_bin = tmp_path / "unrelated-writer-bin"
    fake_bin.mkdir()
    fake_ps = fake_bin / "ps"
    fake_ps.write_text(
        (
            "#!/bin/sh\n"
            f"printf '%s\\n' '4242 {os.getuid()} "
            f"{shlex.quote(sys.executable)} {shlex.quote(str(unrelated_bot))}'\n"
        ),
        encoding="utf-8",
    )
    fake_ps.chmod(0o755)

    checked = _run(
        repo,
        support,
        active_config_root=canonical,
        observe_real_processes=True,
        env={
            "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
        },
    )

    assert checked.returncode == 0, checked.stderr
    assert json.loads(checked.stdout)["status"] == "canonical-authoritative"


def test_committed_authority_wins_if_cleanup_was_interrupted(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    support = tmp_path / "app-support"
    legacy = _legacy_root(repo)
    legacy.mkdir(parents=True)
    (legacy / "global.json").write_text('{"choice":"legacy"}\n', encoding="utf-8")

    interrupted = _run(
        repo,
        support,
        env={"VIVENTIUM_QA_TELEGRAM_MIGRATION_INTERRUPT_AFTER_AUTHORITY": "1"},
    )

    assert interrupted.returncode != 0
    state = support / "state" / "telegram-user-config-migration"
    assert (state / "authority.json").is_file()
    assert (state / "pending.json").is_file()
    canonical = support / "state" / "telegram-user-configs" / "global.json"
    canonical.write_text('{"choice":"post-commit-user-edit"}\n', encoding="utf-8")
    edited = canonical.read_bytes()

    recovered = _run(repo, support)

    assert recovered.returncode == 0, recovered.stderr
    assert json.loads(recovered.stdout)["status"] == "canonical-authoritative"
    assert canonical.read_bytes() == edited
    assert not (state / "pending.json").exists()


def test_migration_outputs_are_private_and_lock_symlink_is_rejected(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    support = tmp_path / "app-support"
    legacy = _legacy_root(repo)
    legacy.mkdir(parents=True)
    (legacy / "global.json").write_text('{"private":true}\n', encoding="utf-8")

    completed = _run(repo, support)
    assert completed.returncode == 0, completed.stderr
    state = support / "state" / "telegram-user-config-migration"
    canonical = support / "state" / "telegram-user-configs" / "global.json"
    assert stat.S_IMODE(state.stat().st_mode) == 0o700
    assert stat.S_IMODE(canonical.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(canonical.stat().st_mode) == 0o600
    assert stat.S_IMODE((state / "authority.json").stat().st_mode) == 0o600

    (state / "migration.lock").unlink()
    outside = tmp_path / "outside-lock"
    outside.touch()
    (state / "migration.lock").symlink_to(outside)
    rejected = _run(repo, support)
    assert rejected.returncode != 0
    assert "lock" in rejected.stderr.lower() or "symlink" in rejected.stderr.lower()


def test_migration_rejects_symlinked_legacy_file_without_canonical_write(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    support = tmp_path / "app-support"
    legacy = _legacy_root(repo)
    legacy.mkdir(parents=True)
    outside = tmp_path / "outside.json"
    outside.write_text('{"private":true}\n', encoding="utf-8")
    (legacy / "global.json").symlink_to(outside)

    completed = _run(repo, support)

    assert completed.returncode != 0
    assert "symlink" in completed.stderr.lower()
    assert not (support / "state" / "telegram-user-configs").exists()


def test_runtime_and_entrypoints_bind_migration_before_installed_launch() -> None:
    launcher = LAUNCHER.read_text(encoding="utf-8")
    cli = CLI.read_text(encoding="utf-8")
    helper = HELPER_INSTALLER.read_text(encoding="utf-8")

    assert (
        'TELEGRAM_USER_CONFIGS_DIR="${VIVENTIUM_TELEGRAM_USER_CONFIGS_DIR:-'
        '$VIVENTIUM_APP_SUPPORT_ROOT/state/telegram-user-configs}"'
    ) in launcher
    assert "migrate_telegram_user_configs" in cli
    assert "migrate_telegram_user_configs" not in helper
    migration_position = cli.rindex('migrate_telegram_user_configs "$REPO_ROOT"')
    stop_position = cli.rfind("stop_stack_for_upgrade", 0, migration_position)
    assert 0 <= stop_position < migration_position


def test_launcher_creates_and_hardens_private_telegram_preference_root(
    tmp_path: Path,
) -> None:
    launcher = LAUNCHER.read_text(encoding="utf-8")
    canonical = tmp_path / "app-support" / "state" / "telegram-user-configs"

    created = _ensure_private_root(canonical)
    assert created.returncode == 0, created.stderr
    assert stat.S_IMODE(canonical.stat().st_mode) == 0o700

    canonical.chmod(0o755)
    hardened = _ensure_private_root(canonical)
    assert hardened.returncode == 0, hardened.stderr
    assert stat.S_IMODE(canonical.stat().st_mode) == 0o700
    assert 'local helper="$VIVENTIUM_CORE_DIR/scripts/viventium/' in launcher
    assert 'telegram_user_config_migration.py"' in launcher
    assert '--ensure-private-root "$target"' in launcher
    function = _extract_shell_function(
        launcher,
        "ensure_private_telegram_user_configs_dir",
    )
    assert "mkdir -p" not in function
    assert "chmod " not in function


def test_launcher_rejects_symlinked_telegram_preference_root(
    tmp_path: Path,
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir(mode=0o755)
    outside.chmod(0o755)
    canonical = tmp_path / "telegram-user-configs"
    canonical.symlink_to(outside, target_is_directory=True)

    rejected = _ensure_private_root(canonical)

    assert rejected.returncode != 0
    assert "symlink" in rejected.stderr
    assert stat.S_IMODE(outside.stat().st_mode) == 0o755


def test_private_root_rejects_symlinked_ancestor_without_mutating_target(
    tmp_path: Path,
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir(mode=0o755)
    outside.chmod(0o755)
    sentinel = outside / "sentinel.txt"
    sentinel.write_text("unchanged\n", encoding="utf-8")
    alias = tmp_path / "app-support-alias"
    alias.symlink_to(outside, target_is_directory=True)

    rejected = _ensure_private_root(alias / "state" / "telegram-user-configs")

    assert rejected.returncode != 0
    assert "symlink" in rejected.stderr or "unsafe" in rejected.stderr
    assert sentinel.read_text(encoding="utf-8") == "unchanged\n"
    assert stat.S_IMODE(outside.stat().st_mode) == 0o755
    assert not (outside / "state").exists()


def test_private_root_chmod_is_descriptor_bound_during_name_swap(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_migration_module()
    canonical = tmp_path / "app-support" / "state" / "telegram-user-configs"
    canonical.mkdir(parents=True)
    canonical.chmod(0o755)
    detached = canonical.with_name("telegram-user-configs-detached")
    outside = tmp_path / "outside"
    outside.mkdir(mode=0o755)
    outside.chmod(0o755)
    real_fchmod = module.os.fchmod
    swapped = False

    def swap_name_then_fchmod(descriptor: int, mode: int) -> None:
        nonlocal swapped
        if not swapped:
            swapped = True
            canonical.rename(detached)
            canonical.symlink_to(outside, target_is_directory=True)
        real_fchmod(descriptor, mode)

    monkeypatch.setattr(module.os, "fchmod", swap_name_then_fchmod)

    with pytest.raises(module.MigrationError, match="changed"):
        module.ensure_private_preference_root(canonical)

    assert stat.S_IMODE(outside.stat().st_mode) == 0o755
    assert stat.S_IMODE(detached.stat().st_mode) == 0o700

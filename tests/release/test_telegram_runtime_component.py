from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import types

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
COMPONENT_TOOL = (
    REPO_ROOT / "scripts" / "viventium" / "telegram_runtime_component.py"
)
LAUNCHER = REPO_ROOT / "viventium_v0_4" / "viventium-librechat-start.sh"
CLI = REPO_ROOT / "bin" / "viventium"
HELPER_INSTALLER = REPO_ROOT / "scripts" / "viventium" / "install_macos_helper.sh"


def _load_component_module():
    spec = importlib.util.spec_from_file_location(
        "telegram_runtime_component_under_test",
        COMPONENT_TOOL,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_intel_macos_dependency_sync_disables_broken_sdist_wheel_repair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_component_module()
    monkeypatch.setattr(module.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(module.platform, "machine", lambda: "x86_64")

    environment = module._dependency_sync_environment(
        {
            "PATH": "/synthetic/bin",
            "TMPDIR": "/synthetic/tmp",
            "PRESERVED": "no",
            "HOME": '/synthetic/home with spaces & triple-quote-"""',
            "OPENAI_API_KEY": "must-not-reach-a-package-build",
        }
    )

    assert environment["PATH"] == "/synthetic/bin"
    assert environment["TMPDIR"] == "/synthetic/tmp"
    assert environment["NO_REPAIR"] == "1"
    assert "PRESERVED" not in environment
    assert "HOME" not in environment
    assert "OPENAI_API_KEY" not in environment


def test_non_intel_dependency_sync_does_not_inherit_wheel_repair_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_component_module()
    monkeypatch.setattr(module.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(module.platform, "machine", lambda: "arm64")

    environment = module._dependency_sync_environment(
        {
            "PATH": "/synthetic/bin",
            "LANG": "en_US.UTF-8",
            "PRESERVED": "no",
            "NO_REPAIR": "owner-shell-value",
        }
    )

    assert environment == {
        "PATH": "/synthetic/bin",
        "LANG": "en_US.UTF-8",
    }


def test_optional_dependency_install_uses_the_curated_build_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_component_module()
    repo = tmp_path / "repo"
    store = tmp_path / "store"
    _make_runtime_repo(repo)
    monkeypatch.setattr(module.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(module.platform, "machine", lambda: "arm64")
    monkeypatch.setenv("HOME", '/synthetic/home with spaces & triple-quote-"""')
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-reach-a-package-build")
    calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_run(command: list[str], **kwargs: object) -> types.SimpleNamespace:
        calls.append((command, kwargs))
        if command[:2] == ["uv", "sync"]:
            environment = kwargs["env"]
            assert isinstance(environment, dict)
            stage = Path(environment["UV_PROJECT_ENVIRONMENT"])
            python = stage / "bin" / "python"
            python.parent.mkdir(parents=True)
            python.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            python.chmod(0o755)
        return types.SimpleNamespace(returncode=0, stdout="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    module._sync_dependencies(store, repo, "a" * 64)

    optional_call = next(
        kwargs for command, kwargs in calls if command[:3] == ["uv", "pip", "install"]
    )
    optional_environment = optional_call["env"]
    assert isinstance(optional_environment, dict)
    assert "HOME" not in optional_environment
    assert "OPENAI_API_KEY" not in optional_environment


def test_sealed_dependency_stage_cleanup_is_recoverable(tmp_path: Path) -> None:
    module = _load_component_module()
    stage = tmp_path / ".venv-stage.synthetic"
    nested = stage / "lib" / "python" / "site-packages"
    nested.mkdir(parents=True)
    _write(nested / "package.py", "SYNTHETIC = True\n")
    module._seal_dependency_root(stage)

    module._remove_dependency_stage(stage)

    assert not stage.exists()


@pytest.mark.parametrize(
    ("owner", "group", "mode", "expected"),
    [
        (0, 0, 0o775, True),
        (0, 80, 0o775, False),
        (0, 0, 0o777, False),
        (os.getuid(), os.getgid(), 0o755, True),
        (
            os.getuid(),
            os.getgid(),
            0o775,
            os.getuid() == 0 and os.getgid() == 0,
        ),
    ],
)
def test_external_python_target_permission_policy(
    tmp_path: Path,
    owner: int,
    group: int,
    mode: int,
    expected: bool,
) -> None:
    module = _load_component_module()
    environment = tmp_path / "environment"
    candidate = environment / "bin" / "python"
    resolved_target = tmp_path / "managed-python"
    candidate.parent.mkdir(parents=True)
    resolved_target.write_bytes(b"synthetic-python")
    resolved_target.chmod(0o555)
    metadata = types.SimpleNamespace(
        st_mode=stat.S_IFREG | mode,
        st_uid=owner,
        st_gid=group,
    )

    assert (
        module._external_python_target_is_trusted(
            candidate=candidate,
            root=environment,
            resolved_target=resolved_target,
            target_metadata=metadata,
        )
        is expected
    )


def _write(path: Path, text: str = "synthetic\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_runtime_repo(root: Path) -> None:
    bot = root / "viventium_v0_4" / "telegram-viventium" / "TelegramVivBot"
    _write(
        bot / "pyproject.toml",
        (
            "[project]\n"
            'name = "synthetic-telegram"\n'
            'version = "0.0.0"\n'
            'requires-python = ">=3.11"\n'
            "dependencies = []\n"
        ),
    )
    _write(bot / "bot.py", "print('synthetic telegram')\n")
    _write(bot / "config.py", "SYNTHETIC = True\n")
    _write(bot / "utils" / "__init__.py", "")
    _write(bot / "utils" / "singleton.py", "SYNTHETIC = True\n")
    _write(bot / "aient" / "aient" / "__init__.py", "")
    _write(bot / "md2tgmd" / "setup.py", "from setuptools import setup\nsetup()\n")
    _write(bot / "md2tgmd" / "src" / "md2tgmd.py", "SYNTHETIC = True\n")

    shared = root / "viventium_v0_4" / "shared"
    _write(shared / "__init__.py", "")
    _write(shared / "no_response.py", "SYNTHETIC = True\n")
    _write(shared / "voice" / "tts_provider_capabilities.json", "{}\n")
    _write(shared / "voice" / "cartesia_sonic3_capabilities.json", "{}\n")
    _write(shared / "voice" / "xai_tts_capabilities.json", "{}\n")

    voice = root / "viventium_v0_4" / "voice-gateway"
    _write(voice / "local_chatterbox_config.py", "SYNTHETIC = True\n")
    _write(voice / "mlx_chatterbox_tts.py", "SYNTHETIC = True\n")
    _write(voice / "sse.py", "SYNTHETIC = True\n")
    _write(
        voice / "requirements.mlx_audio_darwin.txt",
        "# no optional packages in the synthetic fixture\n",
    )
    subprocess.run(
        ["uv", "lock"],
        cwd=bot,
        check=True,
        capture_output=True,
        text=True,
    )

    # These are deliberately private/generated and must never enter a component.
    _write(root / "viventium_v0_4" / "telegram-viventium" / "config.env", "TOKEN=private\n")
    _write(bot / ".env", "TOKEN=private\n")
    _write(bot / "user_configs" / "user.json", '{"private":true}\n')
    _write(bot / ".venv" / "private-source-venv", "do not copy\n")
    _write(bot / "__pycache__" / "bot.pyc", "do not copy\n")
    _write(root / "viventium_v0_4" / "shared" / "tests" / "private.py", "do not copy\n")
    _write(root / "viventium_v0_4" / "voice-gateway" / "tests" / "private.py", "do not copy\n")


def _prepare(
    repo: Path,
    app_support: Path,
    selection: Path,
    *,
    sync_dependencies: bool = True,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(COMPONENT_TOOL),
        "prepare",
        "--repo-root",
        str(repo),
        "--app-support-dir",
        str(app_support),
        "--selection-file",
        str(selection),
    ]
    if sync_dependencies:
        command.append("--sync-dependencies")
    return subprocess.run(command, check=False, capture_output=True, text=True)


def test_component_prepare_is_content_addressed_and_public_code_only(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    app_support = tmp_path / "app-support"
    selection = app_support / "state" / "candidate" / "runtime" / "components" / "telegram.json"
    _make_runtime_repo(repo)

    first = _prepare(repo, app_support, selection)
    assert first.returncode == 0, first.stderr
    first_payload = json.loads(first.stdout)
    selected = json.loads(selection.read_text(encoding="utf-8"))
    code_root = Path(selected["code_root"])
    telegram_root = Path(selected["telegram_root"])

    assert first_payload["code_digest"] == selected["code_digest"]
    assert code_root.is_relative_to(app_support / "runtime-components")
    assert telegram_root == code_root / "viventium_v0_4" / "telegram-viventium"
    assert (telegram_root / "TelegramVivBot" / "bot.py").is_file()
    assert (code_root / "viventium_v0_4" / "shared" / "no_response.py").is_file()
    assert (
        code_root / "viventium_v0_4" / "voice-gateway" / "local_chatterbox_config.py"
    ).is_file()
    assert Path(selected["compat_launcher"]) == (
        code_root / "viventium_v0_4" / "viventium-librechat-start.sh"
    )
    assert Path(selected["component_tool"]) == (
        code_root / "scripts" / "viventium" / "telegram_runtime_component.py"
    )
    assert Path(selected["handoff_helper"]) == (
        code_root / "scripts" / "viventium" / "telegram_poller_handoff.py"
    )
    assert Path(selected["compat_cli"]) == code_root / "bin" / "viventium"
    for component_path in (
        Path(selected["compat_launcher"]),
        Path(selected["component_tool"]),
        Path(selected["handoff_helper"]),
        Path(selected["compat_cli"]),
    ):
        assert stat.S_IMODE(component_path.stat().st_mode) in {0o600, 0o700}
        assert component_path.stat().st_mode & 0o077 == 0
    assert not (telegram_root / "config.env").exists()
    assert not (telegram_root / "TelegramVivBot" / ".env").exists()
    assert not (telegram_root / "TelegramVivBot" / "user_configs").exists()
    assert not (telegram_root / "TelegramVivBot" / ".venv").exists()
    assert not (telegram_root / "TelegramVivBot" / "__pycache__").exists()
    assert not (code_root / "viventium_v0_4" / "shared" / "tests").exists()
    assert not (code_root / "viventium_v0_4" / "voice-gateway" / "tests").exists()

    second = _prepare(repo, app_support, selection)
    assert second.returncode == 0, second.stderr
    second_payload = json.loads(second.stdout)
    assert second_payload["code_digest"] == first_payload["code_digest"]
    assert second_payload["code_root"] == first_payload["code_root"]
    assert second_payload["reused_code"] is True


def test_component_resolve_rejects_mode_drift(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    app_support = tmp_path / "app-support"
    selection = app_support / "runtime" / "components" / "telegram.json"
    _make_runtime_repo(repo)
    prepared = _prepare(repo, app_support, selection)
    assert prepared.returncode == 0, prepared.stderr
    selected = json.loads(selection.read_text(encoding="utf-8"))
    component_tool = Path(selected["component_tool"])
    component_tool.chmod(0o644)

    resolved = subprocess.run(
        [
            sys.executable,
            str(COMPONENT_TOOL),
            "resolve",
            "--app-support-dir",
            str(app_support),
            "--selection-file",
            str(selection),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert resolved.returncode != 0
    assert "integrity verification" in resolved.stderr


def _write_private_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    path.chmod(0o600)


def test_recovery_receipt_is_transaction_bound_passive_then_rolled_back(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    app_support = tmp_path / "app-support"
    selection = app_support / "runtime" / "components" / "telegram.json"
    _make_runtime_repo(repo)
    prepared = _prepare(repo, app_support, selection)
    assert prepared.returncode == 0, prepared.stderr
    selected = json.loads(selection.read_text(encoding="utf-8"))
    transaction = app_support / "upgrade-backups" / "upgrade-synthetic"
    ledger_path = transaction / "ledger.json"
    ledger = {
        "schema_version": 1,
        "transaction_path": str(transaction),
        "app_support_dir": str(app_support),
        "repo_root": str(repo),
        "status": "active",
        "was_running": False,
        "repositories": [
            {
                "name": "parent",
                "path": str(repo),
                "old_head": "a" * 40,
                "expected_target": "b" * 40,
            }
        ],
    }
    _write_private_json(ledger_path, ledger)
    canonical = app_support / "state" / "telegram-user-configs"
    canonical.mkdir(parents=True, mode=0o700)
    authority = {
        "schema_version": 2,
        "kind": "viventium-telegram-preference-authority",
        "status": "committed",
        "authority": "canonical-app-support",
        "generation": "c" * 64,
        "canonical_root": str(canonical),
        "retired_legacy_roots": [],
        "source_tree_sha256": "d" * 64,
        "operations": [],
    }
    _write_private_json(
        app_support
        / "state"
        / "telegram-user-config-migration"
        / "authority.json",
        authority,
    )
    component_tool = Path(selected["component_tool"])

    published = subprocess.run(
        [
            sys.executable,
            str(component_tool),
            "publish-recovery",
            "--app-support-dir",
            str(app_support),
            "--selection-file",
            str(selection),
            "--transaction-kind",
            "upgrade",
            "--transaction-path",
            str(transaction),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert published.returncode == 0, published.stderr
    receipt = (
        app_support / "state" / "continuity" / "telegram-recovery-active.json"
    )
    assert receipt.stat().st_mode & 0o077 == 0

    passive = subprocess.run(
        [
            sys.executable,
            str(component_tool),
            "resolve-recovery",
            "--app-support-dir",
            str(app_support),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert passive.returncode == 0, passive.stderr
    assert json.loads(passive.stdout)["disposition"] == "passive"

    ledger["status"] = "rolled_back"
    _write_private_json(ledger_path, ledger)
    recovery = subprocess.run(
        [
            sys.executable,
            str(component_tool),
            "resolve-recovery",
            "--app-support-dir",
            str(app_support),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert recovery.returncode == 0, recovery.stderr
    recovery_payload = json.loads(recovery.stdout)
    assert recovery_payload["disposition"] == "recovery"
    assert recovery_payload["was_running"] is False
    assert recovery_payload["user_configs_root"] == str(canonical)
    assert recovery_payload["selection_file"] == str(selection)
    launcher_style_resolution = subprocess.run(
        [
            sys.executable,
            str(component_tool),
            "resolve",
            "--app-support-dir",
            str(app_support),
            "--selection-file",
            recovery_payload["selection_file"],
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert launcher_style_resolution.returncode == 0, (
        launcher_style_resolution.stderr
    )

    ledger["status"] = "committed"
    _write_private_json(ledger_path, ledger)
    committed = subprocess.run(
        [
            sys.executable,
            str(component_tool),
            "resolve-recovery",
            "--app-support-dir",
            str(app_support),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert committed.returncode == 0, committed.stderr
    assert json.loads(committed.stdout)["disposition"] == "passive"


def test_recovery_receipt_allows_readonly_legacy_modes_before_first_commit(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    app_support = tmp_path / "app-support"
    selection = app_support / "runtime" / "components" / "telegram.json"
    _make_runtime_repo(repo)
    prepared = _prepare(repo, app_support, selection)
    assert prepared.returncode == 0, prepared.stderr
    selected = json.loads(selection.read_text(encoding="utf-8"))
    transaction = app_support / "upgrade-backups" / "upgrade-synthetic"
    ledger_path = transaction / "ledger.json"
    ledger = {
        "schema_version": 1,
        "transaction_path": str(transaction),
        "app_support_dir": str(app_support),
        "repo_root": str(repo),
        "status": "active",
        "was_running": True,
        "repositories": [
            {
                "name": "parent",
                "path": str(repo),
                "old_head": "a" * 40,
                "expected_target": "b" * 40,
            }
        ],
    }
    _write_private_json(ledger_path, ledger)
    canonical = app_support / "state" / "telegram-user-configs"
    canonical.mkdir(parents=True, mode=0o755)
    preference = canonical / "global.json"
    preference.write_bytes(b'{"personalization":"preserved"}\n')
    preference.chmod(0o644)
    preference_before = preference.read_bytes()
    component_tool = Path(selected["component_tool"])

    published = subprocess.run(
        [
            sys.executable,
            str(component_tool),
            "publish-recovery",
            "--app-support-dir",
            str(app_support),
            "--selection-file",
            str(selection),
            "--transaction-kind",
            "upgrade",
            "--transaction-path",
            str(transaction),
            "--user-configs-root",
            str(canonical),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert published.returncode == 0, published.stderr
    assert not (
        app_support
        / "state"
        / "telegram-user-config-migration"
        / "authority.json"
    ).exists()
    ledger["status"] = "rolled_back"
    _write_private_json(ledger_path, ledger)
    resolved = subprocess.run(
        [
            sys.executable,
            str(component_tool),
            "resolve-recovery",
            "--app-support-dir",
            str(app_support),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert resolved.returncode == 0, resolved.stderr
    payload = json.loads(resolved.stdout)
    assert payload["disposition"] == "recovery"
    assert payload["user_configs_root"] == str(canonical)
    assert preference.read_bytes() == preference_before
    assert stat.S_IMODE(canonical.stat().st_mode) == 0o755
    assert stat.S_IMODE(preference.stat().st_mode) == 0o644


def test_recovery_receipt_replay_fails_after_retirement(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    app_support = tmp_path / "app-support"
    selection = app_support / "runtime" / "components" / "telegram.json"
    _make_runtime_repo(repo)
    prepared = _prepare(repo, app_support, selection)
    assert prepared.returncode == 0, prepared.stderr
    selected = json.loads(selection.read_text(encoding="utf-8"))
    transaction = app_support / "upgrade-backups" / "upgrade-synthetic"
    _write_private_json(
        transaction / "ledger.json",
        {
            "schema_version": 1,
            "transaction_path": str(transaction),
            "app_support_dir": str(app_support),
            "repo_root": str(repo),
            "status": "rolled_back",
            "was_running": True,
            "repositories": [
                {
                    "name": "parent",
                    "path": str(repo),
                    "old_head": "a" * 40,
                    "expected_target": "b" * 40,
                }
            ],
        },
    )
    canonical = app_support / "state" / "telegram-user-configs"
    canonical.mkdir(parents=True, mode=0o700)
    _write_private_json(
        app_support
        / "state"
        / "telegram-user-config-migration"
        / "authority.json",
        {
            "schema_version": 2,
            "kind": "viventium-telegram-preference-authority",
            "status": "committed",
            "authority": "canonical-app-support",
            "generation": "c" * 64,
            "canonical_root": str(canonical),
            "retired_legacy_roots": [],
            "source_tree_sha256": "d" * 64,
            "operations": [],
        },
    )
    component_tool = Path(selected["component_tool"])
    publish = subprocess.run(
        [
            sys.executable,
            str(component_tool),
            "publish-recovery",
            "--app-support-dir",
            str(app_support),
            "--selection-file",
            str(selection),
            "--transaction-kind",
            "upgrade",
            "--transaction-path",
            str(transaction),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert publish.returncode == 0, publish.stderr
    receipt_path = (
        app_support / "state" / "continuity" / "telegram-recovery-active.json"
    )
    replay = receipt_path.read_bytes()
    retired = subprocess.run(
        [
            sys.executable,
            str(component_tool),
            "clear-recovery",
            "--app-support-dir",
            str(app_support),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert retired.returncode == 0, retired.stderr
    receipt_path.write_bytes(replay)
    receipt_path.chmod(0o600)

    resolved = subprocess.run(
        [
            sys.executable,
            str(component_tool),
            "resolve-recovery",
            "--app-support-dir",
            str(app_support),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert resolved.returncode != 0
    assert "retired" in resolved.stderr.lower() or "generation" in resolved.stderr.lower()


def test_recovery_preserves_explicit_custom_preference_root(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    app_support = tmp_path / "app-support"
    selection = app_support / "runtime" / "components" / "telegram.json"
    custom_preferences = tmp_path / "operator-preferences"
    custom_preferences.mkdir(mode=0o700)
    (custom_preferences / "global.json").write_text(
        '{"custom":"preserved"}\n',
        encoding="utf-8",
    )
    _make_runtime_repo(repo)
    prepared = _prepare(repo, app_support, selection)
    assert prepared.returncode == 0, prepared.stderr
    selected = json.loads(selection.read_text(encoding="utf-8"))
    transaction = app_support / "upgrade-backups" / "upgrade-synthetic"
    _write_private_json(
        transaction / "ledger.json",
        {
            "schema_version": 1,
            "transaction_path": str(transaction),
            "app_support_dir": str(app_support),
            "repo_root": str(repo),
            "status": "rolled_back",
            "was_running": True,
            "repositories": [
                {
                    "name": "parent",
                    "path": str(repo),
                    "old_head": "a" * 40,
                    "expected_target": "b" * 40,
                }
            ],
        },
    )
    component_tool = Path(selected["component_tool"])

    published = subprocess.run(
        [
            sys.executable,
            str(component_tool),
            "publish-recovery",
            "--app-support-dir",
            str(app_support),
            "--selection-file",
            str(selection),
            "--transaction-kind",
            "upgrade",
            "--transaction-path",
            str(transaction),
            "--user-configs-root",
            str(custom_preferences),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert published.returncode == 0, published.stderr
    resolved = subprocess.run(
        [
            sys.executable,
            str(component_tool),
            "resolve-recovery",
            "--app-support-dir",
            str(app_support),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert resolved.returncode == 0, resolved.stderr
    payload = json.loads(resolved.stdout)
    assert payload["disposition"] == "recovery"
    assert payload["user_configs_root"] == str(custom_preferences)
    assert (custom_preferences / "global.json").read_text(encoding="utf-8") == (
        '{"custom":"preserved"}\n'
    )


def test_dependency_manifest_binds_external_python_symlink_content(
    tmp_path: Path,
) -> None:
    module = _load_component_module()
    environment = tmp_path / "environment"
    executable = tmp_path / "managed-python"
    (environment / "bin").mkdir(parents=True)
    executable.write_bytes(b"synthetic-python-v1")
    executable.chmod(0o555)
    (environment / "bin" / "python").symlink_to(executable)
    (environment / "bin").chmod(0o555)
    environment.chmod(0o555)

    first = module._dependency_environment_manifest(environment)
    executable.chmod(0o755)
    executable.write_bytes(b"synthetic-python-v2")
    executable.chmod(0o555)
    second = module._dependency_environment_manifest(environment)

    assert first["environment_digest"] != second["environment_digest"]
    python_entry = next(
        entry for entry in first["entries"] if entry["path"] == "bin/python"
    )
    assert python_entry["resolved_target_sha256"] == hashlib.sha256(
        b"synthetic-python-v1"
    ).hexdigest()


def test_component_prepare_fails_closed_on_existing_bundle_tamper(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    app_support = tmp_path / "app-support"
    selection = app_support / "runtime" / "components" / "telegram.json"
    _make_runtime_repo(repo)
    prepared = _prepare(repo, app_support, selection)
    assert prepared.returncode == 0, prepared.stderr
    selected = json.loads(selection.read_text(encoding="utf-8"))
    bot = Path(selected["telegram_root"]) / "TelegramVivBot" / "bot.py"
    bot.write_text("tampered\n", encoding="utf-8")

    repeated = _prepare(repo, app_support, selection)

    assert repeated.returncode != 0
    assert "existing Telegram runtime component failed integrity verification" in repeated.stderr


def test_component_ignores_untracked_allowed_suffix_files_in_git_checkout(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    app_support = tmp_path / "app-support"
    selection = app_support / "runtime" / "components" / "telegram.json"
    _make_runtime_repo(repo)
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "config", "user.name", "Synthetic QA"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "synthetic@example.invalid"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "commit", "-m", "synthetic fixture"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    untracked = (
        repo
        / "viventium_v0_4"
        / "telegram-viventium"
        / "TelegramVivBot"
        / "private_untracked.py"
    )
    _write(untracked, "PRIVATE = True\n")

    prepared = _prepare(repo, app_support, selection)

    assert prepared.returncode == 0, prepared.stderr
    selected = json.loads(selection.read_text(encoding="utf-8"))
    assert not (
        Path(selected["telegram_root"])
        / "TelegramVivBot"
        / "private_untracked.py"
    ).exists()


def test_component_prepare_rejects_unsafe_source_and_selection_paths(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    app_support = tmp_path / "app-support"
    _make_runtime_repo(repo)
    source_bot = repo / "viventium_v0_4" / "telegram-viventium" / "TelegramVivBot" / "bot.py"
    source_bot.unlink()
    source_bot.symlink_to(repo / "viventium_v0_4" / "shared" / "no_response.py")

    symlinked = _prepare(
        repo,
        app_support,
        app_support / "runtime" / "components" / "telegram.json",
    )
    outside = _prepare(repo, app_support, tmp_path / "outside" / "telegram.json")

    assert symlinked.returncode != 0
    assert "symlink" in symlinked.stderr.lower()
    assert outside.returncode != 0
    assert "outside App Support" in outside.stderr


def test_component_refuses_to_publish_without_complete_dependencies(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    app_support = tmp_path / "app-support"
    selection = app_support / "runtime" / "components" / "telegram.json"
    _make_runtime_repo(repo)

    prepared = _prepare(
        repo,
        app_support,
        selection,
        sync_dependencies=False,
    )

    assert prepared.returncode != 0
    assert "complete synchronized dependency environment" in prepared.stderr
    assert not selection.exists()


def test_component_dependency_environment_is_content_addressed(
    tmp_path: Path,
) -> None:
    if not shutil.which("uv"):
        pytest.skip("uv is required for Telegram runtime component dependency acceptance")
    repo = tmp_path / "repo"
    app_support = tmp_path / "app-support"
    selection = app_support / "runtime" / "components" / "telegram.json"
    _make_runtime_repo(repo)
    (
        repo
        / "viventium_v0_4"
        / "telegram-viventium"
        / "TelegramVivBot"
        / "uv.lock"
    ).unlink()
    shutil.rmtree(
        repo
        / "viventium_v0_4"
        / "telegram-viventium"
        / "TelegramVivBot"
        / ".venv"
    )
    subprocess.run(
        ["uv", "lock"],
        cwd=repo / "viventium_v0_4" / "telegram-viventium" / "TelegramVivBot",
        check=True,
        capture_output=True,
        text=True,
    )

    prepared = _prepare(
        repo,
        app_support,
        selection,
        sync_dependencies=True,
    )

    assert prepared.returncode == 0, prepared.stderr
    selected = json.loads(selection.read_text(encoding="utf-8"))
    python = Path(selected["python"])
    assert python.is_file()
    assert python.is_relative_to(app_support / "runtime-components")
    resolved = subprocess.run(
        [
            sys.executable,
            str(COMPONENT_TOOL),
            "resolve",
            "--app-support-dir",
            str(app_support),
            "--selection-file",
            str(selection),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert resolved.returncode == 0, resolved.stderr
    assert json.loads(resolved.stdout)["python"] == str(python)


def test_component_dependency_environment_detects_added_or_changed_files(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    app_support = tmp_path / "app-support"
    selection = app_support / "runtime" / "components" / "telegram.json"
    _make_runtime_repo(repo)
    prepared = _prepare(repo, app_support, selection)
    assert prepared.returncode == 0, prepared.stderr
    selected = json.loads(selection.read_text(encoding="utf-8"))
    dependency_root = Path(selected["python"]).parent.parent
    manifest = dependency_root / ".viventium-dependency-manifest.json"
    before = manifest.read_bytes()

    for _ in range(2):
        resolved = subprocess.run(
            [
                sys.executable,
                str(COMPONENT_TOOL),
                "resolve",
                "--app-support-dir",
                str(app_support),
                "--selection-file",
                str(selection),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        assert resolved.returncode == 0, resolved.stderr
    assert manifest.read_bytes() == before

    site_packages = next((dependency_root / "lib").glob("python*/site-packages"))
    site_packages.chmod(0o755)
    _write(site_packages / "unexpected_runtime_mutation.py", "MUTATED = True\n")
    added = subprocess.run(
        [
            sys.executable,
            str(COMPONENT_TOOL),
            "resolve",
            "--app-support-dir",
            str(app_support),
            "--selection-file",
            str(selection),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert added.returncode != 0
    assert (
        "integrity verification" in added.stderr
        or "not sealed read-only" in added.stderr
    )

    (site_packages / "unexpected_runtime_mutation.py").unlink()
    site_packages.chmod(0o555)
    pyvenv = dependency_root / "pyvenv.cfg"
    pyvenv.chmod(0o644)
    pyvenv.write_text("tampered\n", encoding="utf-8")
    changed = subprocess.run(
        [
            sys.executable,
            str(COMPONENT_TOOL),
            "resolve",
            "--app-support-dir",
            str(app_support),
            "--selection-file",
            str(selection),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert changed.returncode != 0
    assert (
        "integrity verification" in changed.stderr
        or "not sealed read-only" in changed.stderr
    )


def test_optional_voice_requirements_advance_dependency_identity(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    app_support = tmp_path / "app-support"
    selection = app_support / "runtime" / "components" / "telegram.json"
    _make_runtime_repo(repo)

    first = _prepare(repo, app_support, selection)
    assert first.returncode == 0, first.stderr
    first_payload = json.loads(first.stdout)
    (
        repo
        / "viventium_v0_4"
        / "voice-gateway"
        / "requirements.mlx_audio_darwin.txt"
    ).write_text("# different optional dependency fixture\n", encoding="utf-8")

    second = _prepare(repo, app_support, selection)
    assert second.returncode == 0, second.stderr
    second_payload = json.loads(second.stdout)

    assert second_payload["code_digest"] != first_payload["code_digest"]
    assert second_payload["dependency_digest"] != first_payload["dependency_digest"]


def test_runtime_wiring_prepares_candidate_before_publication_and_start() -> None:
    cli = CLI.read_text(encoding="utf-8")
    helper = HELPER_INSTALLER.read_text(encoding="utf-8")
    launcher = LAUNCHER.read_text(encoding="utf-8")

    activation_start = cli.index("\n    activate-current)")
    activation = cli[
        activation_start :
        cli.index("remove_dev_runtime_activation_transaction", activation_start)
    ]
    assert activation.index("stage_telegram_runtime_component") < activation.index(
        "dev_runtime_activation_tool publish"
    )
    activation_before_begin = activation[: activation.index("dev_runtime_activation_tool begin-new")]
    assert 'prepare_telegram_runtime_component "$previous_repo" "$RUNTIME_DIR"' not in (
        activation_before_begin
    )

    upgrade_start = cli.index("\n  upgrade|update)")
    upgrade = cli[
        upgrade_start :
        cli.index("\n  configure|wizard)", upgrade_start)
    ]
    assert upgrade.index("stage_telegram_runtime_component") < upgrade.index(
        "upgrade_transaction_activate_candidate"
    )
    upgrade_mutation = upgrade[upgrade.index("UPGRADE_AUDIT_TIMESTAMP") :]
    upgrade_before_begin = upgrade_mutation[
        : upgrade_mutation.index("upgrade_transaction_begin")
    ]
    assert 'prepare_telegram_runtime_component "$REPO_ROOT" "$RUNTIME_DIR"' not in (
        upgrade_before_begin
    )
    assert "prepare_telegram_runtime_component" in helper
    assert "TELEGRAM_COMPONENT_SELECTION_FILE" in launcher
    assert "VIVENTIUM_TELEGRAM_EXECUTION_ROOT" in launcher
    assert 'exec "$telegram_python_path" bot.py' in launcher
    assert "load_telegram_predecessor_recovery_component" in cli
    assert "VIVENTIUM_DETACHED_COMPAT_LAUNCHER" in cli
    assert (
        'TELEGRAM_COMPONENT_TOOL="${VIVENTIUM_TELEGRAM_COMPONENT_TOOL:-'
        '$VIVENTIUM_CORE_DIR/scripts/viventium/telegram_runtime_component.py}"'
    ) in launcher
    telegram_start = launcher[
        launcher.index("start_telegram_bot() {") :
        launcher.index("start_telegram_codex() {")
    ]
    assert "telegram_installed_component_required=true" in telegram_start
    assert "Detached Telegram runtime component selection is missing or unsafe" in telegram_start
    assert telegram_start.index(
        "Detached Telegram runtime component selection is missing or unsafe"
    ) < telegram_start.index("telegram_dir=$(resolve_telegram_dir)")
    assert (
        'if [[ "$telegram_use_installed_component" != "true" ]] &&\n'
        "    host_supports_local_chatterbox_mlx"
    ) in launcher

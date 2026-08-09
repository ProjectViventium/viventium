from __future__ import annotations

import importlib.util
import fcntl
import os
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "deploy/glasshive/systemd/glasshive_auth_admin.py"
SPEC = importlib.util.spec_from_file_location("glasshive_auth_admin", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
admin = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(admin)


def test_hosted_admin_wrapper_uses_absolute_system_interpreter():
    assert SCRIPT.read_text(encoding="utf-8").splitlines()[0] == "#!/usr/bin/python3"


def _synthetic_release(tmp_path: Path) -> tuple[Path, Path]:
    release = tmp_path / "releases/release-test"
    script = release / "deploy/glasshive/systemd/glasshive_auth_admin.py"
    script.parent.mkdir(parents=True)
    script.write_text("# synthetic installed wrapper\n", encoding="utf-8")
    (release / "glasshive-release.json").write_text("{}\n", encoding="utf-8")
    python_path = (
        release
        / "viventium_v0_4/GlassHive/frontends/glass-drive-ui/.venv/bin/python"
    )
    python_path.parent.mkdir(parents=True)
    python_path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    python_path.chmod(0o755)
    return script, python_path


def test_hosted_admin_command_uses_exact_release_gateway_identity_and_environments(
    tmp_path,
    monkeypatch,
):
    script, python_path = _synthetic_release(tmp_path)
    systemd_run = tmp_path / "systemd-run"
    systemd_run.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    systemd_run.chmod(0o755)
    gateway_env = tmp_path / "gateway.env"
    active_env = tmp_path / "gateway-active.env"
    gateway_env.write_text("GLASSHIVE_HUMAN_AUTH_MODE=oidc\n", encoding="utf-8")
    active_env.write_text("GLASSHIVE_RELEASE_ID=release-test\n", encoding="utf-8")
    monkeypatch.setattr(admin, "SYSTEMD_RUN", systemd_run)
    monkeypatch.setattr(admin, "GATEWAY_ENV", gateway_env)
    monkeypatch.setattr(admin, "GATEWAY_ACTIVE_ENV", active_env)

    command = admin._systemd_command(script_path=script)

    assert command[-5:] == [
        str(python_path),
        "-m",
        "glass_drive_ui.auth_admin",
        "preapprove-oidc",
        "--stdin-json",
    ]
    assert "--uid=glasshive-gateway" in command
    assert "--gid=glasshive-state" in command
    assert f"--property=EnvironmentFile={gateway_env}" in command
    assert f"--property=EnvironmentFile={active_env}" in command
    assert "--property=ReadWritePaths=/var/lib/glasshive" in command
    assert all("subject" not in value and "email" not in value for value in command)


def test_hosted_admin_wrapper_returns_oneshot_result_without_reading_private_stdin(
    tmp_path,
    monkeypatch,
):
    expected = ["/usr/bin/systemd-run", "--", "python", "-m", "admin"]
    observed: list[list[str]] = []
    mutation_lock = admin._mutation_lock
    monkeypatch.setattr(admin.os, "geteuid", lambda: 0)
    monkeypatch.setattr(
        admin,
        "_mutation_lock",
        lambda: mutation_lock(tmp_path / "rollout.lock", expected_uid=os.getuid()),
    )
    monkeypatch.setattr(admin, "_systemd_command", lambda: expected)
    monkeypatch.setattr(
        admin.subprocess,
        "run",
        lambda command, check: observed.append(command) or SimpleNamespace(returncode=7),
    )

    assert admin.main(["preapprove-oidc", "--stdin-json"]) == 7
    assert observed == [expected]


def test_hosted_admin_wrapper_requires_root(monkeypatch, capsys):
    monkeypatch.setattr(admin.os, "geteuid", lambda: 501)

    assert admin.main(["preapprove-oidc", "--stdin-json"]) == 2
    assert "requires root" in capsys.readouterr().err


def test_hosted_admin_and_rollout_share_a_bidirectional_mutation_lock(tmp_path):
    lock_path = tmp_path / "rollout.lock"
    with admin._mutation_lock(lock_path):
        competing = os.open(lock_path, os.O_RDWR)
        try:
            with pytest.raises(BlockingIOError):
                fcntl.flock(competing, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            os.close(competing)

    rollout_holder = os.open(lock_path, os.O_RDWR)
    try:
        fcntl.flock(rollout_holder, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(admin.AdminBusyError, match="rollout is in progress"):
            with admin._mutation_lock(lock_path):
                pass
    finally:
        fcntl.flock(rollout_holder, fcntl.LOCK_UN)
        os.close(rollout_holder)

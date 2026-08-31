from __future__ import annotations

import importlib.util
import json
import os
import re
import stat
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from qa_control_test_support import write_artifact_identity as _write_artifact_identity

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "viventium" / "local_qa_runtime_control.py"
CLI = ROOT / "bin" / "viventium"
LAUNCHER = ROOT / "viventium_v0_4" / "viventium-librechat-start.sh"


def write_artifact_identity(installed: Path, identity: Path) -> dict[str, object]:
    payload = _write_artifact_identity(installed, identity)
    payload.setdefault(
        "readiness",
        {
            "factsSha256": "4" * 64,
            "storagePolicySha256": "5" * 64,
            "storageMeasurementSha256": "6" * 64,
        },
    )
    identity.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(identity, 0o600)
    return payload


def load_module():
    spec = importlib.util.spec_from_file_location("local_qa_runtime_control", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _activate(module, tmp_path: Path, case_id: str = "TR-026"):
    installed = tmp_path / "installed"
    installed.mkdir(exist_ok=True)
    ack_helper = installed / "scripts" / "viventium" / "local_qa_service_ack.py"
    ack_helper.parent.mkdir(parents=True)
    ack_helper.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    ack_helper.chmod(0o755)
    state = tmp_path / "runtime" / "local-qa" / "active.json"
    identity = tmp_path / "runtime" / "parallel-work-artifact-identity.json"
    write_artifact_identity(installed, identity)
    request = tmp_path / "runtime" / "parallel-work-local-qa-request.json"
    request.write_text(
        '{"contractVersion":1,"mode":"local-qa","requested":true}\n',
        encoding="utf-8",
    )
    os.chmod(request, 0o600)
    now = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)
    result = module.activate_session(
        state_path=state,
        installed_root=installed,
        artifact_identity_path=identity,
        local_qa_request_path=request,
        case_id=case_id,
        expires_in_seconds=900,
        now=now,
        token_bytes=lambda size: b"x" * size,
    )
    return installed, identity, state, now, result


def test_activate_is_private_candidate_bound_and_redacted(tmp_path: Path) -> None:
    module = load_module()
    installed, _identity, state, _, result = _activate(module, tmp_path)
    payload = json.loads(state.read_text(encoding="utf-8"))

    assert result == {
        "caseId": "TR-026",
        "expiresAt": "2026-08-23T12:15:00.000+00:00",
        "mode": "tr-026",
        "sessionRef": payload["sessionRef"],
    }
    assert re.fullmatch(r"qa_[a-f0-9]{24}", payload["sessionRef"])
    assert payload["installedRootHash"].startswith("sha256:")
    assert payload["artifactIdentityDigest"].startswith("sha256:")
    assert str(installed) not in state.read_text(encoding="utf-8")
    assert "caseToken" in payload
    assert payload["caseToken"] not in json.dumps(result)
    assert stat.S_IMODE(state.stat().st_mode) == 0o600
    assert stat.S_IMODE(state.parent.stat().st_mode) == 0o700


@pytest.mark.parametrize(
    ("case_id", "expected"),
    [
        ("TR-026", "VIVENTIUM_TELEGRAM_LOCAL_QA_MODE=tr-026"),
        ("EMO-UC-047", "VIVENTIUM_LOCAL_QA_MODE=emo_uc_047"),
        ("EMO-UC-048", "VIVENTIUM_LOCAL_QA_MODE=emo_uc_048"),
        ("MPV-061", "VIVENTIUM_LOCAL_QA_MODE=mpv_061"),
        ("PWK-UC-015", "VIVENTIUM_LOCAL_QA_MODE=pwk_uc_015"),
        ("PWK-UC-016", "VIVENTIUM_GLASSHIVE_LOCAL_QA_MODE=pwk_uc_016"),
        ("PWK-UC-017", "VIVENTIUM_GLASSHIVE_LOCAL_QA_MODE=pwk_uc_017"),
        ("REL-UC-004", "VIVENTIUM_RELEASE_LOCAL_QA_MODE=rel_uc_004"),
    ],
)
def test_emit_shell_projects_only_the_exact_case_mode(
    tmp_path: Path, case_id: str, expected: str
) -> None:
    module = load_module()
    installed, identity, state, now, _ = _activate(module, tmp_path, case_id)

    output = module.emit_shell_exports(
        state_path=state,
        installed_root=installed,
        artifact_identity_path=identity,
        local_qa_request_path=state.parent.parent
        / "parallel-work-local-qa-request.json",
        now=now + timedelta(seconds=1),
    )

    assert expected in output
    assert "VIVENTIUM_LOCAL_QA_CASE_TOKEN=" in output
    assert "VIVENTIUM_LOCAL_QA_SESSION_REF=" in output
    assert "VIVENTIUM_LOCAL_QA_COMPONENT_ARTIFACT_DIGEST=sha256:" in output
    assert str(installed) not in output
    assert "export " in output


@pytest.mark.parametrize("case_id", ["PWK-UC-016", "PWK-UC-017", "MPV-061"])
def test_candidate_bound_cases_project_the_exact_session_candidate_and_never_ambient(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case_id: str
) -> None:
    module = load_module()
    installed, identity, state, now, _ = _activate(module, tmp_path, case_id)
    payload = json.loads(state.read_text(encoding="utf-8"))
    ambient = "sha256:" + "f" * 64
    monkeypatch.setenv("VIVENTIUM_LOCAL_QA_CANDIDATE_DIGEST", ambient)

    output = module.emit_shell_exports(
        state_path=state,
        installed_root=installed,
        artifact_identity_path=identity,
        local_qa_request_path=state.parent.parent
        / "parallel-work-local-qa-request.json",
        now=now + timedelta(seconds=1),
    )

    assert (
        "VIVENTIUM_LOCAL_QA_CANDIDATE_DIGEST=" + str(payload["artifactIdentityDigest"])
    ) in output
    assert ambient not in output


def test_non_glasshive_session_never_projects_a_candidate_digest(
    tmp_path: Path,
) -> None:
    module = load_module()
    installed, identity, state, now, _ = _activate(module, tmp_path, "TR-026")

    output = module.emit_shell_exports(
        state_path=state,
        installed_root=installed,
        artifact_identity_path=identity,
        local_qa_request_path=state.parent.parent
        / "parallel-work-local-qa-request.json",
        now=now + timedelta(seconds=1),
    )

    assert "VIVENTIUM_LOCAL_QA_CANDIDATE_DIGEST" not in output


def test_require_restart_ready_fails_closed_until_every_case_service_is_live(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()
    installed, identity, state, now, _ = _activate(module, tmp_path, "TR-026")
    request = state.parent.parent / "parallel-work-local-qa-request.json"
    waiting = {
        "restartState": "waiting",
        "requiredServices": ["librechat-core", "telegram-bot"],
        "acknowledgedServices": ["librechat-core"],
        "missingServices": ["telegram-bot"],
        "serviceAckDigest": "",
    }
    monkeypatch.setattr(
        module,
        "_service_ack_module",
        lambda: SimpleNamespace(restart_status=lambda *args, **kwargs: waiting),
    )
    with pytest.raises(ValueError, match="restart acknowledgement"):
        module.require_restart_ready(
            state_path=state,
            installed_root=installed,
            artifact_identity_path=identity,
            local_qa_request_path=request,
            now=now + timedelta(seconds=1),
        )

    ready = {
        **waiting,
        "restartState": "ready",
        "acknowledgedServices": ["librechat-core", "telegram-bot"],
        "missingServices": [],
        "serviceAckDigest": "sha256:" + "f" * 64,
    }
    monkeypatch.setattr(
        module,
        "_service_ack_module",
        lambda: SimpleNamespace(restart_status=lambda *args, **kwargs: ready),
    )
    result = module.require_restart_ready(
        state_path=state,
        installed_root=installed,
        artifact_identity_path=identity,
        local_qa_request_path=request,
        now=now + timedelta(seconds=1),
    )
    assert result["caseId"] == "TR-026"
    assert result["restartState"] == "ready"
    assert result["serviceAckDigest"] == "sha256:" + "f" * 64


def test_emit_fails_closed_for_expiry_candidate_mismatch_or_open_permissions(
    tmp_path: Path,
) -> None:
    module = load_module()
    installed, identity, state, now, _ = _activate(module, tmp_path)

    with pytest.raises(ValueError, match="expired"):
        module.emit_shell_exports(
            state_path=state,
            installed_root=installed,
            artifact_identity_path=identity,
            local_qa_request_path=state.parent.parent
            / "parallel-work-local-qa-request.json",
            now=now + timedelta(minutes=16),
        )

    other = tmp_path / "other"
    other.mkdir()
    with pytest.raises(ValueError, match="candidate"):
        module.emit_shell_exports(
            state_path=state,
            installed_root=other,
            artifact_identity_path=identity,
            local_qa_request_path=state.parent.parent
            / "parallel-work-local-qa-request.json",
            now=now + timedelta(seconds=1),
        )

    os.chmod(state, 0o644)
    with pytest.raises(ValueError, match="session state is invalid"):
        module.emit_shell_exports(
            state_path=state,
            installed_root=installed,
            artifact_identity_path=identity,
            local_qa_request_path=state.parent.parent
            / "parallel-work-local-qa-request.json",
            now=now + timedelta(seconds=1),
        )


def test_unknown_case_and_duplicate_activation_fail_closed(tmp_path: Path) -> None:
    module = load_module()
    installed = tmp_path / "installed"
    installed.mkdir()
    state = tmp_path / "runtime" / "local-qa" / "active.json"
    identity = tmp_path / "runtime" / "parallel-work-artifact-identity.json"
    identity.parent.mkdir(parents=True, exist_ok=True)
    identity.write_text('{"contractVersion":1}\n', encoding="utf-8")
    request = tmp_path / "runtime" / "parallel-work-local-qa-request.json"
    request.write_text(
        '{"contractVersion":1,"mode":"local-qa","requested":true}\n',
        encoding="utf-8",
    )
    os.chmod(identity, 0o600)
    os.chmod(request, 0o600)
    now = datetime(2026, 8, 23, 12, 0, tzinfo=timezone.utc)

    with pytest.raises(ValueError, match="supported"):
        module.activate_session(
            state_path=state,
            installed_root=installed,
            artifact_identity_path=identity,
            local_qa_request_path=request,
            case_id="PWK-UC-999",
            expires_in_seconds=900,
            now=now,
        )

    _, identity, _, _, _ = _activate(module, tmp_path)
    with pytest.raises(ValueError, match="already active"):
        module.activate_session(
            state_path=state,
            installed_root=installed,
            artifact_identity_path=identity,
            local_qa_request_path=request,
            case_id="EMO-UC-048",
            expires_in_seconds=900,
            now=now,
        )


def test_clear_requires_the_exact_redacted_session_reference(tmp_path: Path) -> None:
    module = load_module()
    _, _, state, _, result = _activate(module, tmp_path)

    with pytest.raises(ValueError, match="reference"):
        module.clear_session(state_path=state, session_ref="qa_wrong")
    assert state.exists()

    cleared = module.clear_session(
        state_path=state, session_ref=str(result["sessionRef"])
    )
    assert cleared == {"cleared": True, "sessionRef": result["sessionRef"]}
    assert not state.exists()


def test_cli_and_launcher_expose_the_control_without_enabling_it_by_default() -> None:
    cli_text = CLI.read_text(encoding="utf-8")
    launcher_text = LAUNCHER.read_text(encoding="utf-8")

    assert "qa-control" in cli_text
    assert "local_qa_runtime_control.py" in cli_text
    assert "local-qa/active.json" in cli_text
    assert "local_qa_runtime_control.py" in launcher_text
    assert "VIVENTIUM_TELEGRAM_LOCAL_QA_MODE" in launcher_text
    assert "VIVENTIUM_LOCAL_QA_CASE_TOKEN" in launcher_text
    local_qa_block = launcher_text.split("# Installed local-QA fault controls", 1)[
        1
    ].split("# === VIVENTIUM END ===", 1)[0]
    assert "unset VIVENTIUM_LOCAL_QA_CANDIDATE_DIGEST" in local_qa_block
    assert "VIVENTIUM_LOCAL_QA_MODE" not in os.environ


def test_private_read_rejects_same_size_in_place_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()
    private_file = tmp_path / "private.json"
    original = b'{"requested":true}\n'
    replacement = b'{"requested":null}\n'
    assert len(original) == len(replacement)
    private_file.write_bytes(original)
    private_file.chmod(0o600)
    original_read = module.os.read
    mutated = False

    def mutate_after_read(descriptor: int, size: int) -> bytes:
        nonlocal mutated
        chunk = original_read(descriptor, size)
        if chunk and not mutated:
            private_file.write_bytes(replacement)
            private_file.chmod(0o600)
            mutated = True
        return chunk

    monkeypatch.setattr(module.os, "read", mutate_after_read)

    with pytest.raises(ValueError, match="invalid"):
        module._read_private_file(private_file, label="private file", max_bytes=1024)


def test_private_read_rejects_same_size_path_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()
    private_file = tmp_path / "private.json"
    displaced = tmp_path / "displaced.json"
    original = b'{"requested":true}\n'
    replacement = b'{"requested":null}\n'
    private_file.write_bytes(original)
    private_file.chmod(0o600)
    original_read = module.os.read
    replaced = False

    def replace_after_read(descriptor: int, size: int) -> bytes:
        nonlocal replaced
        chunk = original_read(descriptor, size)
        if chunk and not replaced:
            private_file.rename(displaced)
            private_file.write_bytes(replacement)
            private_file.chmod(0o600)
            replaced = True
        return chunk

    monkeypatch.setattr(module.os, "read", replace_after_read)

    with pytest.raises(ValueError, match="invalid"):
        module._read_private_file(private_file, label="private file", max_bytes=1024)


def test_private_read_accepts_stable_inode_when_only_timestamp_changes_between_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()
    private_file = tmp_path / "private.json"
    raw = b'{"requested":true}\n'
    private_file.write_bytes(raw)
    private_file.chmod(0o600)
    original_open = module._open_private_path
    opens = 0

    def touch_before_second_open(path: Path, *, label: str, max_bytes: int):
        nonlocal opens
        opens += 1
        if opens == 2:
            timestamp = private_file.stat().st_mtime_ns + 1_000_000_000
            os.utime(private_file, ns=(timestamp, timestamp))
        return original_open(path, label=label, max_bytes=max_bytes)

    monkeypatch.setattr(module, "_open_private_path", touch_before_second_open)

    assert (
        module._read_private_file(private_file, label="private file", max_bytes=1024)
        == raw
    )


def test_private_read_accepts_stable_parent_when_only_timestamp_changes_between_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()
    private_file = tmp_path / "private.json"
    raw = b'{"requested":true}\n'
    private_file.write_bytes(raw)
    private_file.chmod(0o600)
    original_open = module._open_private_path
    opens = 0

    def touch_parent_before_second_open(path: Path, *, label: str, max_bytes: int):
        nonlocal opens
        opens += 1
        if opens == 2:
            timestamp = private_file.parent.stat().st_mtime_ns + 1_000_000_000
            os.utime(private_file.parent, ns=(timestamp, timestamp))
        return original_open(path, label=label, max_bytes=max_bytes)

    monkeypatch.setattr(module, "_open_private_path", touch_parent_before_second_open)

    assert (
        module._read_private_file(private_file, label="private file", max_bytes=1024)
        == raw
    )


def test_session_clear_rejects_same_size_path_replacement_before_unlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()
    _installed, _identity, state, _now, result = _activate(module, tmp_path, "TR-026")
    displaced = tmp_path / "displaced-session.json"
    original_unlink = module._unlink_private_file_snapshot

    def replace_before_unlink(
        path: Path,
        snapshot: object,
        *,
        label: str,
        max_bytes: int,
    ) -> None:
        original = path.read_bytes()
        replacement = original.replace(b'"TR-026"', b'"XR-014"')
        assert len(replacement) == len(original)
        path.replace(displaced)
        path.write_bytes(replacement)
        path.chmod(0o600)
        original_unlink(
            path,
            snapshot,
            label=label,
            max_bytes=max_bytes,
        )

    monkeypatch.setattr(module, "_unlink_private_file_snapshot", replace_before_unlink)

    with pytest.raises(ValueError):
        module.clear_session(
            state_path=state,
            session_ref=str(result["sessionRef"]),
        )

    assert state.exists()
    assert displaced.exists()


def test_private_state_fifo_rejects_without_blocking(tmp_path: Path) -> None:
    module = load_module()
    fifo_path = tmp_path / "private-state.fifo"
    os.mkfifo(fifo_path, mode=0o600)
    started = datetime.now(timezone.utc)

    with pytest.raises(ValueError, match="invalid"):
        module._read_private_file(
            fifo_path,
            label="private state",
            max_bytes=module.SESSION_STATE_MAX_BYTES,
        )

    assert (datetime.now(timezone.utc) - started).total_seconds() < 0.75


def test_session_clear_final_unlink_swap_deletes_neither_wrong_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_module()
    _installed, _identity, state, _now, result = _activate(module, tmp_path, "TR-026")
    original = state.read_bytes()
    replacement = original.replace(b'"TR-026"', b'"XR-014"')
    assert len(replacement) == len(original)
    displaced = tmp_path / "original-session.json"
    raced = False

    def swap_public_name() -> None:
        nonlocal raced
        if raced:
            return
        state.replace(displaced)
        state.write_bytes(replacement)
        state.chmod(0o600)
        raced = True

    original_unlink = module.os.unlink

    def raced_unlink(
        path: str | bytes | os.PathLike[str], *, dir_fd: int | None = None
    ) -> None:
        if path == state.name:
            swap_public_name()
        original_unlink(path, dir_fd=dir_fd)

    monkeypatch.setattr(module.os, "unlink", raced_unlink)
    if hasattr(module, "_rename_noreplace"):
        original_rename = module._rename_noreplace

        def raced_rename(
            source: str,
            destination: str,
            *,
            source_dir_fd: int,
            destination_dir_fd: int,
        ) -> None:
            if source == state.name:
                swap_public_name()
            original_rename(
                source,
                destination,
                source_dir_fd=source_dir_fd,
                destination_dir_fd=destination_dir_fd,
            )

        monkeypatch.setattr(module, "_rename_noreplace", raced_rename)

    with pytest.raises(ValueError) as caught:
        module.clear_session(
            state_path=state,
            session_ref=str(result["sessionRef"]),
        )

    assert raced
    assert getattr(caught.value, "outcome", "") == "replacement_restored"
    assert displaced.read_bytes() == original
    assert state.read_bytes() == replacement


def test_private_read_rejects_a_writable_parent_component(tmp_path: Path) -> None:
    module = load_module()
    unsafe_parent = tmp_path / "unsafe"
    unsafe_parent.mkdir(mode=0o700)
    private_file = unsafe_parent / "private.json"
    private_file.write_text('{"requested":true}\n', encoding="utf-8")
    private_file.chmod(0o600)
    unsafe_parent.chmod(0o733)
    try:
        with pytest.raises(ValueError, match="invalid"):
            module._read_private_file(
                private_file, label="private file", max_bytes=1024
            )
    finally:
        unsafe_parent.chmod(0o700)


def test_script_cli_never_prints_case_token(tmp_path: Path) -> None:
    installed = tmp_path / "installed"
    installed.mkdir()
    state = tmp_path / "runtime" / "local-qa" / "active.json"
    identity = tmp_path / "runtime" / "parallel-work-artifact-identity.json"
    write_artifact_identity(installed, identity)
    request = tmp_path / "runtime" / "parallel-work-local-qa-request.json"
    request.write_text(
        '{"contractVersion":1,"mode":"local-qa","requested":true}\n',
        encoding="utf-8",
    )
    os.chmod(request, 0o600)
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "activate",
            "--state",
            str(state),
            "--installed-root",
            str(installed),
            "--artifact-identity",
            str(identity),
            "--local-qa-request",
            str(request),
            "--case-id",
            "TR-026",
            "--expires-in-seconds",
            "900",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(state.read_text(encoding="utf-8"))
    assert payload["caseToken"] not in result.stdout
    assert payload["caseToken"] not in result.stderr


def test_artifact_identity_change_invalidates_the_session(tmp_path: Path) -> None:
    module = load_module()
    installed, identity, state, now, _ = _activate(module, tmp_path)
    identity.write_text(
        '{"contractVersion":1,"fixture":"candidate-b"}\n', encoding="utf-8"
    )

    with pytest.raises(ValueError, match="artifact identity"):
        module.emit_shell_exports(
            state_path=state,
            installed_root=installed,
            artifact_identity_path=identity,
            local_qa_request_path=state.parent.parent
            / "parallel-work-local-qa-request.json",
            now=now,
        )


def test_disabled_local_qa_request_invalidates_the_session(tmp_path: Path) -> None:
    module = load_module()
    installed, identity, state, now, _ = _activate(module, tmp_path)
    request = state.parent.parent / "parallel-work-local-qa-request.json"
    request.write_text(
        '{"contractVersion":1,"mode":"local-qa","requested":false}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="explicit local-QA request"):
        module.emit_shell_exports(
            state_path=state,
            installed_root=installed,
            artifact_identity_path=identity,
            local_qa_request_path=request,
            now=now,
        )


def test_duplicate_keys_fail_closed_in_request_and_session_state(
    tmp_path: Path,
) -> None:
    module = load_module()
    installed, identity, state, now, _ = _activate(module, tmp_path)
    request = state.parent.parent / "parallel-work-local-qa-request.json"

    request.write_text(
        '{"contractVersion":1,"mode":"local-qa","requested":true,"requested":true}\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="explicit local-QA request"):
        module.active_session(
            state_path=state,
            installed_root=installed,
            artifact_identity_path=identity,
            local_qa_request_path=request,
            now=now + timedelta(seconds=1),
        )

    request.write_text(
        '{"contractVersion":1,"mode":"local-qa","requested":true}\n',
        encoding="utf-8",
    )
    raw_state = state.read_text(encoding="utf-8")
    state.write_text(
        raw_state.replace(
            '  "caseId": "TR-026",',
            '  "caseId": "TR-026",\n  "caseId": "TR-026",',
            1,
        ),
        encoding="utf-8",
    )
    os.chmod(state, 0o600)
    with pytest.raises(ValueError, match="session state is invalid"):
        module.active_session(
            state_path=state,
            installed_root=installed,
            artifact_identity_path=identity,
            local_qa_request_path=request,
            now=now + timedelta(seconds=1),
        )


def test_local_control_cli_rejects_duplicate_options_without_echo(capsys) -> None:
    module = load_module()
    private_value = "private-" + os.urandom(12).hex()

    assert (
        module.main(
            [
                "clear",
                "--state",
                "/tmp/first",
                "--state",
                private_value,
                "--session-ref",
                "qa_" + "a" * 24,
            ]
        )
        == 2
    )
    captured = capsys.readouterr()
    assert private_value not in captured.out
    assert private_value not in captured.err
    assert captured.out == ""
    assert json.loads(captured.err) == {"error": "operation_failed"}


def test_public_cli_parses_activate_and_clear_arguments_without_passthrough() -> None:
    source = CLI.read_text(encoding="utf-8")
    qa_branch = source.rsplit("  qa-control)", 1)[1].split("  release-check)", 1)[0]
    activate_branch = qa_branch.split("      activate)", 1)[1].split(
        "      status)", 1
    )[0]
    clear_branch = qa_branch.rsplit("      clear)", 1)[1]

    assert "qa_activate_user_args=()" in activate_branch
    assert "qa_activate_case_seen" in activate_branch
    assert "qa_activate_expiry_seen" in activate_branch
    assert '"${@:2}"' not in activate_branch
    assert '"${qa_activate_user_args[@]}"' in activate_branch

    assert "qa_clear_user_args=()" in clear_branch
    assert "qa_clear_session_ref_seen" in clear_branch
    assert '"${@:2}"' not in clear_branch
    assert '"${qa_clear_user_args[@]}"' in clear_branch
